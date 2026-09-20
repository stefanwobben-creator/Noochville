from __future__ import annotations
import threading, logging, uuid, re, os, time
from nooch_village.event_bus import EventBus, Event
from nooch_village.inbox import Inbox
from nooch_village.models import Task, Response, Record, Tension
from nooch_village.skills import SkillRegistry
from nooch_village.triage_engine import TriageContext, classify as _triage_classify


def _persona_ladder(context, role_id: str, call_site: str) -> str | None:
    """De modelvoorkeur van de persona op deze rol, of None voor de dorpsladder.

    Fail-soft: een kapotte voorkeur mag een LLM-aanroep nooit blokkeren — dan valt hij
    gewoon terug op het bestaande gedrag."""
    try:
        from nooch_village.llm_keuze import llm_voorkeur
        return llm_voorkeur(context, role_id, call_site)
    except Exception:
        return None


def _founder_rol() -> str:
    """Het adres van laatste toevlucht. Eén plek, want twee plekken die het founder-id kennen is
    hoe een verhuizing op de ene wel en op de andere niet landt."""
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    return FOUNDER_ROLE_ID


class Inhabitant(threading.Thread):
    """Eén rol per inwoner (leaf). Doet zelf werk via zijn skills."""

    def __init__(self, record: Record, bus: EventBus, registry: SkillRegistry, context):
        super().__init__(daemon=True, name=record.id)
        self.record = record
        self.id = record.id
        self.dna = record.definition
        self.bus = bus                 # geinjecteerd, geen global
        self.registry = registry
        self.context = context
        self.inbox = Inbox(self.id)
        self._stop_event = threading.Event()
        self.log = logging.getLogger(f"village.{self.id}")
        self._last_reflect: float = 0.0
        # Productie: wekelijks; demo/test: reflect_interval_seconds=0 → altijd
        self._reflect_interval: float = float(
            self.context.settings.get("reflect_interval_seconds", str(7 * 24 * 3600)))
        self._setup_events()
        # Parkeer-klep: elke dag kijken of een geblokkeerd project van mij weer open kan. Universeel
        # gewired (niet in _setup_events, dat subklassen overschrijven). Voorbereiden en uitvoeren
        # zat hier ook in en is weg — zie _tend_projects.
        self.react("dag_begint", self._tend_projects)
        # Periodieke skills (nu: de wekelijkse claim-zelfscan van compliance). Meelopen op de
        # dagpuls; de skill kent zijn eigen ritme en de DNA-grant is de poort. Generiek gehouden:
        # een skill-naam hier hardcoderen zou hem voor elke andere rol een dode capability maken.
        self.react("dag_begint", self._run_pulse_skills)
        # `project_activated` heeft hier geen handler meer (19 sept 2026). Een bord-drag naar ACTIEF
        # liet de rol het project voorbereiden en uitvoeren; die machinerie is weg. Slepen naar
        # ACTIEF is vanaf nu puur een menselijke statuswijziging — het werk doet een mens, en wat er
        # moet gebeuren borgt hij in de wiki. Het event blijft bestaan voor de board-watch zelf.

    def _setup_events(self) -> None:
        """Koppel dag_begint aan _maybe_reflect. Rollen met een eigen pulsgate overschrijven dit."""
        self.react("dag_begint", self._maybe_reflect)

    @property
    def display_name(self) -> str:
        """Geeft de persona-naam als die gezet is, anders de rol-id."""
        return self.record.persona or self.id

    # --- buitenkant: van buiten ben ik gewoon een rol ---
    def capabilities(self) -> list[str]:
        return list(self.dna.skills)

    def deliver(self, task: Task) -> None:
        self.inbox.deliver(task)

    def ask(self, capability: str, payload: dict) -> str:
        rid = uuid.uuid4().hex
        self.bus.publish(Event("help_requested",
            {"request_id": rid, "capability": capability, "payload": payload, "from": self.id}, self.id))
        return rid

    # --- spelregel 5: rol-vraagt-rol om een accountability (dorpsbreed) ---
    def offer(self, accountability_key: str, handler) -> None:
        """Bied een accountability aan die elke andere rol mag aanvragen (spelregel 5).
        De eerste aanbieding abonneert op accountability_requested; de handler draait dan
        op de eigen thread van deze inwoner (via react)."""
        if not hasattr(self, "_offered"):
            self._offered: dict = {}
            self.react("accountability_requested", self._on_accountability_requested)
        self._offered[accountability_key] = handler

    def _on_accountability_requested(self, event: Event) -> None:
        if event.data.get("target") != self.id:
            return                                  # niet aan mij gericht
        key = event.data.get("accountability")
        handler = getattr(self, "_offered", {}).get(key)
        if handler is None:
            self.sense_tension(
                f"Gevraagd om accountability '{key}' die ik niet aanbied; "
                f"verzoeker: {event.data.get('from', '?')}", kind="operational")
            return
        self.log.info("📨 verzoek van %s: voer accountability '%s' uit",
                      event.data.get("from", "?"), key)
        result = handler(event.data.get("payload", {}))
        # Sluit de generieke offer→complete-lus: elke AANGEBODEN accountability meldt af met een
        # completion-event, zodat een wachter (bv. de ask_accountability-CLI) altijd antwoord krijgt —
        # ook als de handler geen eigen, specifiek event publiceert (voorheen deed alleen nl_corpus dat,
        # waardoor elke andere accountability eeuwig op 'geen antwoord' bleef staan).
        self.bus.publish(Event("accountability_check_completed", {
            "target":         self.id,
            "accountability": key,
            "from":           event.data.get("from", "?"),
            "result":         result if isinstance(result, dict) else {},
            "ok":             True,
        }, self.id))

    def propose_close(self, gap_key: str, reason: str) -> None:
        """Stel voor een inbox-item (met deze gap_key) te sluiten omdat ik de accountability nu
        dek: "ik dek dit nu, voorstel tot sluiten". De mens bevestigt met één klik; ik sluit
        nooit zelf — dat zou de dichtgeklapte lus zijn (het systeem dat z'n eigen huiswerk
        beoordeelt)."""
        self.bus.publish(Event("resolution_proposed",
            {"gap_key": gap_key, "reason": reason, "from": self.id}, self.id))

    def ask_accountability(self, target_role: str, accountability_key: str,
                           payload: dict | None = None) -> None:
        """Vraag een andere rol een van diens accountabilities op te pakken (spelregel 5).
        Geen commando: de rol-eigenaar beslist zelf of hij het doet of er een spanning van maakt.
        Een mens-bemenste rol (bv. de founder in the_source) is gewoon een van de vragers."""
        self.bus.publish(Event("accountability_requested", {
            "target":         target_role,
            "accountability": accountability_key,
            "payload":        payload or {},
            "from":           self.id,
        }, self.id))

    def sense_tension(self, description: str, kind: str = "operational",
                      evidence: dict | None = None) -> None:
        """Sens een spanning: logt naar het audittrail én triageert voor dispatch.

        evidence: optioneel verifieerbaar herhalingsbewijs uit het logboek
        (observaties/first_seen), zodat de poort echte feiten leest, geen woord."""
        tension = Tension(sensed_by=self.id, description=description, kind=kind,
                          evidence=evidence)
        self.bus.publish(Event("tension_sensed",
            {"by": self.id, "description": description, "kind": kind}, self.id))
        self.triage(tension)

    # ── Triage ─────────────────────────────────────────────────────────────────

    def triage(self, tension: Tension) -> None:
        """Classificeer en routeer een spanning via TriageEngine (dunne facade).

        1. Structureel/terugkerend  → Proposal via proposal_raised (governance-engine)
        2. Eigen werk               → zelf doen (al in uitvoering)
        3. Andere rol               → routeer via help_requested of broadcast
        4. Geen passende rol        → tactisch proberen; matchmaker escaleert naar mens
        """
        desc  = tension.description
        desc_l = desc.lower()

        llm = self._classify_llm(desc)
        ctx = TriageContext(
            role_id=self.id,
            purpose=self.dna.purpose,
            accountabilities=self.dna.accountabilities,
            domains=getattr(self.dna, "domains", []),
            records=getattr(self.context, "records", None),
        )
        result = _triage_classify(desc_l, ctx, llm_result=llm)

        if result.classification == "structureel":
            # Ging naar `_raise_governance_proposal` → voorstel → G0-G4 → Facilitator. Die hele
            # keten is weg (BLOK A, 19 sept 2026): een inwoner schrijft geen governance-voorstellen
            # meer. De classificatie zelf blijft staan en reist mee in `tension_triaged` hieronder,
            # zodat een mens in het spoor nog kan zien dát dit als structureel werd gelezen.
            self.log.info("🏛️ structurele spanning (geen voorstel meer): %s", desc[:120])
        elif result.classification == "eigen-werk":
            self._do_own_work(tension)
        elif result.classification.startswith("andere-rol:"):
            self._route_to_role(tension, result.target_role_id, result.target_capability)
        else:
            self._try_tactical_or_escalate(tension)

        self.bus.publish(Event("tension_triaged", {
            "by": self.id,
            "description": desc[:80],
            "classification": result.classification,
        }, self.id))

    def _do_own_work(self, tension: Tension) -> None:
        """De spanning valt binnen mijn eigen rol — wordt hier al opgepakt."""
        self.log.info("🔧 spanning in eigen scope (%s) → geen aparte actie", self.id)

    def _route_to_role(self, tension: Tension, role_id: str, capability: str | None) -> None:
        """Routeer naar een andere rol die beter bij de spanning past."""
        if capability:
            self.ask(capability, {"description": tension.description, "from": self.id})
            self.log.info("🔀 spanning gerouteerd → %s via '%s'", role_id, capability)
        else:
            self.bus.publish(Event("tension_routed", {
                "from": self.id, "to": role_id,
                "description": tension.description[:80],
            }, self.id))
            self.log.info("🔀 spanning gerouteerd → %s (broadcast)", role_id)

    def _try_tactical_or_escalate(self, tension: Tension) -> None:
        """Geen passende rol gevonden. Probeer tactisch; matchmaker escaleert naar mens."""
        self.log.info("🔀 geen passende rol → tactisch via help_requested")
        self.ask("assistance", {
            "description": tension.description,
            "from": self.id,
            "context": "geen passende rol gevonden in het dorp",
        })

    def _classify_llm(self, desc: str) -> str | None:
        """Optionele LLM-classificatie. Geeft 'structural','own',<rol_id>,'tactical' of None."""
        from nooch_village.llm import reason
        records = getattr(self.context, "records", None)
        if records is None:
            return None
        roster = "\n".join(
            f"- {r.id}: {', '.join(r.definition.accountabilities[:3])}"
            for r in records.all() if not r.archived and r.id != self.id
        )
        prompt = (
            f"Jouw rol ({self.id}): {self.dna.purpose}\n"
            f"Jouw accountabilities: {', '.join(self.dna.accountabilities)}\n"
            f"Andere rollen:\n{roster}\n\n"
            f"Gevoelde spanning: \"{desc}\"\n\n"
            "Classificeer op EXACT ÉÉN regel (eerste match wint):\n"
            "STRUCTURAL  — terugkerend, governance-structuur ontbreekt of niemand bezit het\n"
            "OWN         — eenmalig werk dat binnen mijn eigen rol valt\n"
            "OTHER:<id>  — werk dat bij een andere bestaande rol past (geef de rol-id)\n"
            "TACTICAL    — eenmalig werk, geen passende rol"
        )
        out = reason(prompt, call_site="classify_tension",
                     ladder=_persona_ladder(self.context, self.id, "classify_tension"))
        if not out:
            return None
        out_l = out.strip().lower().split("\n")[0]
        if out_l.startswith("structural"):
            return "structural"
        if out_l.startswith("own"):
            return "own"
        if out_l.startswith("other:"):
            return out_l[6:].strip()
        if out_l.startswith("tactical"):
            return "tactical"
        return None

    # ── Periodieke reflectie ────────────────────────────────────────────────────

    def _maybe_reflect(self, event: Event) -> None:
        """Reflecteer periodiek, niet bij elke dag_begint-puls.

        `_sense_redundancy` en `_opportunity_reflex` hingen hier ook aan; allebei weg met de
        sensing-cluster (BLOK A, 19 sept 2026). Wat overblijft is `_reflect`, en die is op
        `Inhabitant` een lege stub — alleen `Noochie` vult hem, en die schrijft naar het log."""
        now = time.time()
        if self._reflect_interval > 0 and now - self._last_reflect < self._reflect_interval:
            return
        self._last_reflect = now
        self._reflect()

    def _reflect(self) -> None:
        """Periodieke zelf-reflectie: vergelijk missie/doelen en eigen capaciteit.

        Subklassen overschrijven dit voor hun specifieke gaten.
        HARDE GRENS: produceer UITSLUITEND spanningen en voorstellen.
        Schrijf nooit nieuwe code, start nooit nieuwe externe verbindingen.
        Alles wat capaciteit uitbreidt is mens-gated activatie.
        """

    # ── Project-afhandeling ─────────────────────────────────────────────────────

    # Wat hier ooit stond: voorbereiden (DEEL A) en uitvoeren (DEEL B) van een project door de rol
    # zelf. Allebei weg op 19 sept 2026. Een project heeft geen AI-uitvoerder meer; wat overblijft
    # is de parkeer-klep hieronder, die alleen iets terugzet op het bord voor een mens.

    def _tend_projects(self, event: "Event | None" = None) -> None:
        """Dagelijks kijken of een GEPARKEERD project van mij weer open kan. Meer niet.

        Hier zat tot 19 september 2026 ook de uitvoering: ACTIEF → checklist voorbereiden en
        afwerken. Die hele motor is weg (BLOK A). Wat overblijft is de parkeer-klep, en die is
        nog steeds de moeite: een geblokkeerd project werd anders nooit meer bekeken, en het
        terugzetten naar LOPEND is precies het signaal dat een MENS op het bord moet zien.
        Het heropenen is nu de hele actie — er volgt geen uitvoering meer op."""
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            return
        # Heropenen zodra de VASTGELEGDE blokkade weg is — niet zodra de items er runnable
        # uitzien, want die schijn ontstaat door `reset_item_fails`.
        from nooch_village.park_klep import heropen
        for p in ledger.by_status("blocked"):
            if p.get("owner") == self.id:
                heropen(ledger, p)

    def _missing_required(self, skill: str, payload: dict) -> list[str]:
        """Verplichte payload-velden (skill.required_payload) die ontbreken of leeg zijn. Leeg = geen
        validatie mogelijk (skill onbekend of geen required_payload) → fail-soft (item blijft uitvoerbaar)."""
        from nooch_village.skills import ontbrekende_velden
        obj = self.registry.get(skill) if self.registry else None
        req = tuple(getattr(obj, "required_payload", ()) or ()) if obj is not None else ()
        return ontbrekende_velden(req, payload)                   # begrijpt ook de of-of-vorm

    def _payload_issues(self, skill: str, payload: dict) -> list[str]:
        """Grondings-poort op de payload: laat de skill (indien ze dat kan via validate_payload) haar
        VERWIJZENDE velden aarden tegen de werkelijkheid — bestaat de query-set / het merk / de
        deliverable echt? Een verzonnen verwijzing → een reden, waardoor het item niet-uitvoerbaar wordt
        i.p.v. live te sterven. Skills zonder validate_payload → geen extra check (fail-soft, ongewijzigd).
        Een kapotte validator mag de prep nooit breken.

        Eerst de CONFIGURATIE: een skill zonder sleutel is nooit uitvoerbaar, wat de payload ook
        zegt (zie `_config_ontbreekt`)."""
        config = self._config_ontbreekt(skill)
        if config:
            return [config]
        obj = self.registry.get(skill) if self.registry else None
        vp = getattr(obj, "validate_payload", None)
        if not callable(vp):
            return []
        try:
            return list(vp(payload if isinstance(payload, dict) else {}, self.context) or [])
        except Exception as e:
            self.log.warning("payload-grondingscheck faalde voor %s: %s", skill, e)
            return []

    def _config_ontbreekt(self, skill: str) -> str:
        """Is deze skill in DIT dorp te draaien? Geeft de reden terug als zijn sleutels ontbreken,
        anders "".

        GEMETEN AANLEIDING (skill-review 12-09-2026): shopify_sales werd vijf keer gepland zonder
        SHOPIFY_TOKEN in .env, en elke keer stond er "⚠️ niet gelukt (fout, poging n)" op de wall —
        de planner ziet alleen description en input_schema, `is_configured` bereikte alleen de
        collector en de bronnen-view. Nu telt dezelfde vraag op twee momenten: de catalogus voor de
        planner laat de skill weg, en een gepland item wordt 'niet uitvoerbaar' met de sleutelnaam
        als reden, zodat de mens weet wat hij moet invullen.

        Fail-soft in elke tak: een skill zonder `is_configured`, zonder `required_env`, of een
        context zonder settings → "" (uitvoerbaar, precies zoals voorheen)."""
        obj = self.registry.get(skill) if self.registry else None
        if obj is None:
            return ""
        vereist = tuple(getattr(obj, "required_env", ()) or ())
        check = getattr(obj, "is_configured", None)
        if not vereist or not callable(check):
            return ""
        try:
            if check(self.context):
                return ""
        except Exception as e:                            # noqa: BLE001 — een kapotte check blokkeert niets
            self.log.warning("configuratiecheck faalde voor %s: %s", skill, e)
            return ""
        # Een skill met een of-of-eis (Shopify: token óf client-id+secret) zegt zelf wat er mist;
        # de platte sleutellijst zou dan "SHOPIFY_STORE missing" melden terwijl de store er staat.
        hint = str(getattr(obj, "config_hint", "") or "").strip()
        return f"{skill} is not configured in this village ({hint or (' / '.join(vereist) + ' missing in .env')})"

    # ── Meldingen ───────────────────────────────────────────────────────────────────────────
    def _notify_rol(self, rol_id: str, project_id: str, snippet: str) -> None:
        """Heads-up naar EEN ROL. `_notify_founder` is hier de bijzondere geval van.

        De hardwire zat in de enige meldweg van de pulslus: elke `headsup` ging naar
        FOUNDER_ROLE_ID, ook als het werk aantoonbaar bij iemand anders hoorde. Een rol als adres
        (en niet een persoon) overleeft bovendien een wisseling van vervuller."""
        if not rol_id:
            return
        # Een ROL als adres blijft het uitgangspunt; `signaal` zoekt er de mens bij die hem
        # vervult, of valt terug op de founder. Zo overleeft de melding nog steeds een wisseling
        # van vervuller, maar komt hij wél aan bij iemand die hem leest.
        from nooch_village import signaal
        if not signaal.stuur_op_pad(self.context.data_dir, "role", rol_id, snippet, by=self.id,
                                    herkomst={"project": project_id} if project_id else None):
            self.log.warning("melding aan '%s' kwam nergens aan", rol_id)

    def _notify_founder(self, project_id: str, snippet: str) -> None:
        """Heads-up naar de founder-rol. Het bijzondere geval van `_notify_rol`.

        GEEN EIGEN CAP. De store bewaart de volledige tekst en leidt zelf de preview af (#389).
        Hier nog eens afkappen zou die reparatie op het HOOFDKANAAL van de daemon naar de founder
        ongedaan maken — en dat is precies waar de langste spanningen langs komen.

        GEEN EIGEN STORE-BOUW. De ratchet in `test_notif_poort` telt de plekken die een NotifStore
        construeren, en die telling ving deze methode terecht: twee bouwplekken voor één kanaal is
        hoe een reparatie op de ene wel en op de andere niet landt."""
        from nooch_village.human_inbox import FOUNDER_ROLE_ID
        self._notify_rol(FOUNDER_ROLE_ID, project_id, snippet)

    def _periodieke_skills(self) -> list[str]:
        """Skills die uit zichzelf op de dagpuls meelopen, uit `settings`. De skill bewaakt
        zélf zijn ritme (dag, week, maand) — deze laag kent alleen 'draai mee met de puls'."""
        rauw = self.context.settings.get("pulse_skills", "claims_site_scan")
        return [s.strip() for s in str(rauw).split(",") if s.strip()]

    def _run_pulse_skills(self, event) -> None:
        """Laat de periodieke skills meelopen op de dagpuls. Twee poorten, allebei bewust:

        1. **DNA-grant** — alleen een rol die de skill via governance kreeg, draait hem. Zonder
           grant gebeurt hier niets; dat is de capaciteitspoort uit CLAUDE.md.
        2. **De skill zelf** — die kent zijn eigen periode en geeft `skipped` terug als hij deze
           periode al draaide. Zo blijft deze laag ritme-loos en werkt hij voor dag én week.

        De skill bepaalt ook wat de mens moet zien: `escalate` (er ging iets mis) of `headsup`
        (er is iets gevonden dat aandacht vraagt). Alles wat hier staat is generiek — geen
        skill-specifieke kennis, anders wordt elke skill een dode capability voor elke andere rol."""
        gegrant = set(self.capabilities())
        telling = {"gedraaid": 0, "overgeslagen": 0, "geen_grant": 0, "gemeld": 0, "fout": 0}
        for naam in self._periodieke_skills():
            # TOESTAND 3 — NIET GEDRAAID, GEEN GRANT. Alleen TELLEN, hier geen signaal.
            #
            # DIT IS DE PLEK WAAR EEN DROGE RUN ME REDDE. Eerst meldde deze tak per rol een
            # capaciteitsgat. Dat zijn 31 rollen × 2 pulse-skills = 62 meldingen per puls, voor de
            # normaalste zaak van de wereld: de Copywriter hóórt geen claims-scan te draaien.
            # Precies de 135 vastgelopen-project-notificaties opnieuw (zie CONVENTIES).
            #
            # "Deze rol heeft de grant niet" is rust. Het echte gat is "GEEN ENKELE rol heeft hem" —
            # en dat weet een rol niet over zichzelf. Die check staat op dorpsniveau
            # (`village._meld_verweesde_pulse_skills`), draait één keer per puls, en dedupliceert.
            if naam not in gegrant:
                telling["geen_grant"] += 1
                continue
            uitslag = self.use_skill(naam, {})
            if not isinstance(uitslag, dict):
                telling["fout"] += 1
                self.log.warning("⏱ periodieke skill '%s' gaf geen uitslag terug (%s) — "
                                 "niet te onderscheiden van niets gevonden, dus gemeld",
                                 naam, type(uitslag).__name__)
                continue
            # TOESTAND 1 — OVERGESLAGEN DOOR ZIJN EIGEN RITME. Log-only: er is niets mis. Maar de
            # REDEN moet erbij, anders leest een maandelijkse skill die vandaag niet aan de beurt
            # is er hetzelfde uit als een skill die stuk is.
            if uitslag.get("skipped"):
                telling["overgeslagen"] += 1
                self.log.info("⏱ periodieke skill '%s' overgeslagen — %s", naam,
                              uitslag.get("reden") or uitslag.get("reason")
                              or "ritme zegt: deze periode al gedaan")
                continue
            escalatie = uitslag.get("escalate")
            if escalatie or not uitslag.get("ok", True):
                telling["fout"] += 1
                reden = (escalatie or {}).get("reason") or uitslag.get("error") or "onbekende fout"
                self.log.warning("⏱ periodieke skill '%s' kon niet draaien: %s", naam, reden)
                self._notify_founder("", f"⏱ '{naam}' kon niet draaien: {reden}")
                continue
            # TOESTAND 2 — GEDRAAID. Met of zonder vondst; allebei log-only, en allebei expliciet.
            headsup = uitslag.get("headsup")
            telling["gedraaid"] += 1
            if headsup:
                telling["gemeld"] += 1
                # DE SKILL MAG ZIJN ONTVANGER NOEMEN. Zonder dat ging élke headsup naar de founder,
                # ook als het werk aantoonbaar bij iemand anders hoorde. Noemt hij er geen, dan
                # blijft de founder het adres — het gedrag van vóór deze regel.
                self._notify_rol(str(uitslag.get("ontvanger") or "")
                                 or _founder_rol(), "", str(headsup))
            self.log.info("⏱ periodieke skill '%s' gedraaid — %s", naam,
                          headsup if headsup else "niets gevonden")
        # EEN NUL MOET ZICHZELF VERKLAREN. Zonder deze regel is "geen notificaties vandaag" niet te
        # onderscheiden van "de puls draaide niet" — en dan verzint de lezer een verklaring.
        if any(telling.values()):
            self.log.info("⏱ pulsbalans %s: %d gedraaid (%d gemeld), %d overgeslagen door ritme, "
                          "%d niet van deze rol, %d fout", self.id,
                          telling["gedraaid"], telling["gemeld"], telling["overgeslagen"],
                          telling["geen_grant"], telling["fout"])
        return telling

    def _payload_opnieuw(self, skill: str, tekst: str, schema: str, mist: list, huidig: dict):
        """Leid de payload opnieuw af uit de item-tekst + het input_schema van de skill."""
        from nooch_village.llm import reason as llm_reason
        import json as _json
        prompt = (
            "Je vult de invoer (payload) voor één skill-aanroep in NoochVille (Nooch.earth, duurzame "
            "veganistische schoenen). Een eerdere poging was onvolledig.\n\n"
            f"SKILL: {skill}\n"
            f"INPUT-VORM (input_schema): {schema or '(geen schema — leid af uit de taak)'}\n"
            f"DE TAAK: {tekst}\n"
            f"HUIDIGE PAYLOAD: {_json.dumps(huidig, ensure_ascii=False)[:500]}\n"
            f"ONTBREEKT: {', '.join(mist) or '(onbekend — vul de hele payload opnieuw)'}\n\n"
            "Vul de ontbrekende velden uit de taaktekst. Verzin GEEN identifiers, URL's, merknamen of "
            "id's die niet in de taak staan — laat een veld liever leeg dan het te raden.\n"
            "Antwoord UITSLUITEND met het JSON-object van de payload.")
        raw = llm_reason(prompt, call_site="payload_herstel", json_mode=True, max_tokens=700)
        if not raw:
            return None
        s = str(raw)
        try:
            return _json.loads(s[s.find("{"):s.rfind("}") + 1])
        except (ValueError, IndexError):
            return None

    # ── Wat telt als resultaat? ──────────────────────────────────────────────────────────────
    # Hiervóór stonden hier drie allowlists (_LIST_KEYS/_TEXT_KEYS/_METRIC_KEYS): een skill moest
    # zijn uitvoer in een sleutel stoppen die toevallig in die lijsten stond, anders las een
    # geslaagde run als "leeg". Dat is drie keer misgegaan — projectverzoek (pid/titel),
    # claims_check (bevindingen) en content_check — en kostte 87 weggegooide resultaten. Een
    # allowlist die elke nieuwe skill een gezegende sleutelnaam laat raden, is stille koppeling.
    #
    # Nu andersom: alles wat GEEN metadata is en substantie draagt, telt. Zo hoeft geen enkele
    # nieuwe skill nog iets te raden.

    # Sleutels die over de RUN gaan, niet over de UITKOMST. Een resultaat dat alleen deze bevat is
    # geen resultaat. Bewust ruim: liever een sleutel te veel als metadata dan een lege deliverable
    # die als "gelukt" boekt — dat is de fout aan de andere kant, en die is even duur.
    _META_KEYS = frozenset({
        "ok", "error", "no_data", "reason", "reden", "redenen", "status", "skipped", "escalate",
        "headsup", "refuse", "toelichting",
        "week", "at", "ts", "datum", "day", "maand", "versie", "version", "id", "skill", "source",
        "bron", "locale", "corpus", "query", "term", "vraag_id", "role_id", "project_id",
        "gescand", "overgeslagen", "nieuw", "volledig", "vastgelopen", "force", "estimated",
        # Skill-review 12-09-2026: de ECHO VAN DE INVOER en de RUN-ADMINISTRATIE wonnen bij elf
        # skills van de (lege) uitkomst — competitor_news toonde de vier merknamen die de planner
        # zelf meegaf als "4 results", gsc de site-id, keywords_everywhere "eur", gsc_report een
        # bestandspad. Wat de mens erin stopte of wat de run over zichzelf zegt, is geen resultaat.
        "queries", "brands", "brand", "topic", "onderwerp", "word", "naam",
        "url", "site", "site_id", "period", "periode", "window", "window_days", "windows",
        "timeframe", "strategie", "strategy", "geo", "geos", "taal", "land",
        "path", "pad", "today", "date", "generated_at", "currency", "data_source",
        "credits_remaining", "aard", "naar", "kind", "gevonden_via", "zoekwijze", "gezocht",
        "candidates_source", "engine", "motor", "notif_id",
        "year_start", "year_end", "year", "jaar", "base_year",
    })
    # Sleutelnamen die per definitie een TELLER zijn: een getal daarin is geen bevinding maar een
    # samenvatting van bevindingen die elders staan.
    _TELLER_KEYS = frozenset({
        "total", "totaal", "count", "counts", "aantal", "n", "treffers", "calls", "tokens",
        "rood", "oranje", "groen", "escaleren", "gedekt", "evaluated",
        "guides", "scanned", "new", "bekend", "event_count", "pages", "paginas", "gelezen",
        "total_new", "bytes", "status_code", "fetch_failed", "credits", "hits_total",
    })
    _TRIVIALE_TEKST = frozenset({"", "-", "n/a", "geen", "none", "null", "ok"})
    # Alleen voor de OPMAAK van de note, niet voor de detectie: een dict onder deze sleutels is een
    # meetreeks (datum → waarde) en leest beter als metriek dan als lijstje. Dit is geen allowlist
    # in de oude zin — een skill die hier niet in staat wordt nog steeds gewoon herkend, hij krijgt
    # alleen de generieke opmaak.
    _METRIC_HINTS = frozenset({"values", "value", "series", "results", "reeks", "metingen"})

    @classmethod
    def _draagt_inhoud(cls, sleutel: str, waarde) -> bool:
        """Draagt deze (sleutel, waarde) substantiële inhoud, of is het run-administratie?"""
        if sleutel in cls._META_KEYS or sleutel.startswith("_"):
            return False
        if isinstance(waarde, bool) or waarde is None:
            return False                                  # een vlag is een status, geen uitkomst
        if isinstance(waarde, (list, tuple, set, dict)):
            return cls._verzameling_draagt_inhoud(waarde)
        if isinstance(waarde, str):
            return waarde.strip().lower() not in cls._TRIVIALE_TEKST
        if isinstance(waarde, (int, float)):
            return sleutel not in cls._TELLER_KEYS        # score: 88 telt, total: 5 niet
        return True                                       # onbekend type met een waarde: inhoud

    @classmethod
    def _verzameling_draagt_inhoud(cls, waarde) -> bool:
        """Een lijst of dict is pas inhoud als er iets IN zit dat inhoud is.

        Skill-review 12-09-2026, twee gemeten vormen van "vol maar leeg":
        - een lijst rijen die elk `no_data`/`error` melden (ngram, google_trends: elke term een
          time-out → 48 runs 'gelukt' zonder één cijfer);
        - een dict waarvan alle waarden None of leeg zijn (trends_categorie `values`, een lege
          bucket-telling).
        Beide lazen als 'gelukt' en werden afgevinkt. Een rij die zelf zegt dat er niets is, is
        geen bevinding — en een dict vol None's evenmin."""
        if not waarde:
            return False
        if isinstance(waarde, dict):
            return any(cls._elementaire_inhoud(v) for v in waarde.values())
        return any(cls._elementaire_inhoud(v) for v in waarde)

    @classmethod
    def _elementaire_inhoud(cls, v) -> bool:
        """Draagt dit ELEMENT van een verzameling inhoud? Een dict-rij die zichzelf als leeg of fout
        aanmerkt niet; een lege/None-waarde niet; al het andere wel (een string, een getal, een
        gevulde rij)."""
        if v is None or isinstance(v, bool):
            return False
        if isinstance(v, dict):
            if v.get("no_data") or v.get("error"):
                return False
            return any(x not in (None, "", [], {}) for x in v.values())
        if isinstance(v, (list, tuple, set)):
            return len(v) > 0
        if isinstance(v, str):
            return bool(v.strip())
        if isinstance(v, (int, float)):
            return v != 0                                 # een telling van louter nullen is niets
        return True

    @classmethod
    def _classify_result(cls, result):
        """Normaliseer de fail-conventies naar één uitkomst: ('gelukt'|'leeg'|'fout', archetype).

        `archetype` = (vorm, sleutel) bij succes — de sleutel is AUDITEERBAAR: hij staat in de
        logregel en in de deliverable-note, zodat je bij twijfel kunt zien wélke inhoud geteld is
        (zelfde gedachte als de Kroniek: laat zien waar iets vandaan komt).

        Expliciete signalen blijven leidend: `error`/`ok:False` → fout, `no_data` → leeg. Dat is de
        manier waarop een skill zélf zegt wat er is gebeurd, en die wint van elke heuristiek."""
        if not isinstance(result, dict):
            return "fout", None
        if result.get("error") or result.get("ok") is False:
            return "fout", None
        if result.get("no_data"):
            return "leeg", None
        # De rijkste inhoud wint: een lijst met tien records zegt meer dan een los getal, en bij
        # gelijke vorm de grootste (anders wint 'pid' van 'titel' puur op sleutelvolgorde). Bij
        # écht gelijk de eerste in sleutelvolgorde, zodat de keuze reproduceerbaar blijft.
        beste, beste_score = None, (-1, -1)
        for sleutel, waarde in result.items():
            if not cls._draagt_inhoud(sleutel, waarde):
                continue
            if isinstance(waarde, dict):
                vorm = "metric" if sleutel in cls._METRIC_HINTS else "dictlist"
                rang, omvang = 3, len(waarde)
            elif isinstance(waarde, (list, tuple, set)):
                vorm, rang, omvang = "list", 3, len(waarde)
            elif isinstance(waarde, str):
                vorm, rang, omvang = "text", 2, len(waarde)
            else:
                vorm, rang, omvang = "metric", 1, 0
            if (rang, omvang) > beste_score:
                beste, beste_score = (vorm, sleutel), (rang, omvang)
        if beste is None:
            return "leeg", None                           # niets substantieels → eerlijk leeg
        return "gelukt", beste


    # --- het werk ---

    def _execute_skill(self, capability: str, payload: dict) -> tuple[bool, object]:
        """Voer een skill uit en geef (ok, resultaat) terug.

        Gedeelde kern voor handle() en use_skill(); valideert registry maar
        NIET DNA — dat doet de aanroeper.
        """
        skill = self.registry.get(capability)
        if skill is None:
            return False, f"skill '{capability}' niet geregistreerd"
        try:
            # De draaistaat noteert de aanroep zelf (de registry heeft `run` omwikkeld); hier zetten
            # we alleen het label, want alleen de aanroeper weet wie hij is. Zonder dit staat er in
            # de staat wél dát de skill draaide, maar niet door wie — en juist dat is de vraag zodra
            # je gaat snoeien.
            from nooch_village import draaistaat
            with draaistaat.aanroeper(self.id):
                return True, skill.run(payload, self.context)
        except Exception as e:
            from nooch_village.sleutelmasker import masker
            # Gemaskeerd, want een requests-fout draagt de URL mét sleutel en dit is de tekst die
            # als `error` op de wall en in de Kroniek belandt (skill-review 12-09-2026).
            self.log.error("skill '%s' faalde: %s", capability, masker(e))
            return False, masker(e)

    # ── De middelen-poort ────────────────────────────────────────────────────

    def _skill_links_active(self) -> bool:
        """Staat de koppelingslaag aan als UITVOERINGSwaarheid? (settings: skill_links_active)"""
        settings = getattr(self.context, "settings", None) or {}
        return str(settings.get("skill_links_active", "0")).strip().lower() in ("1", "true", "yes", "ja")

    def effective_skills(self) -> set[str]:
        """De skills die deze rol daadwerkelijk mag voeren: DNA ∪ koppelingen ∪ rugzakken.

        Het DNA is altijd de vloer — geen enkele laag hierboven neemt ooit iets af.

        - **koppelingen** (achter `skill_links_active`): een middel dat aan één accountability
          van deze rol hangt.
        - **rugzakken** (`config/rugzakken.json`): cirkelbrede capaciteit. Elke rol mag erbij;
          dát is het punt. Een rol onderscheidt zich niet door zijn gereedschap maar door zijn
          domein, en die scheiding wordt hieronder bewaakt door `_domein_weigering` — die draait
          NA deze functie en is absoluut. Een rugzak kan de domeinpoort dus niet omzeilen; hij
          verruimt alleen de set die de poort daarna nog beoordeelt.

        Fail-soft: een context zonder `rugzakken` (de meeste tests, en elke oudere caller) gedraagt
        zich exact als voorheen.
        """
        # HET ANTWOORD STAAT IN `skillset`, NIET HIER. Het woonde als methode op deze klasse, en het
        # cockpit heeft geen Inwoner — dus wie het daar nodig had schreef het over, en liep uit de
        # pas. Drie keer inmiddels (zie skillset.py). Nu is de Inwoner één van de aanroepers.
        from nooch_village import skillset
        return skillset.effectief(self.dna.skills, rol_id=self.id, context=self.context)

    def _domein_weigering(self, capability: str) -> str:
        """Verdediging in de diepte: een skill die BESLIST in een domein wordt geweigerd voor
        een rol zonder dat domein — óók als hij per ongeluk in het DNA of in een koppeling
        staat, en ongeacht de vlag-stand. De domeinregel is absoluut, geen policy-omweg.

        Geeft de reden terug ("" = toegestaan).
        """
        from nooch_village import skill_meta
        domein = skill_meta.schrijft_in_domein(capability)
        if not domein:
            return ""
        if domein.lower() in {d.lower() for d in (self.dna.domains or [])}:
            return ""
        return (f"'{capability}' beslist in het domein '{domein}'; '{self.id}' houdt dat domein "
                f"niet. Alleen de domeinhouder mag dit middel voeren")

    def _weiger(self, capability: str) -> str | None:
        """De volledige poort. Geeft een foutmelding terug, of None als het mag."""
        if capability not in self.effective_skills():
            # Luid, niet stil: een miss is bijna altijd een dode feature (de skill wordt
            # aangeroepen maar nooit gegrant). Stil falen heeft verband_voorstel en curate
            # maandenlang onzichtbaar dood gehouden.
            self.log.warning(
                "⚠️ dode capability: '%s' roept skill '%s' aan, maar voert hem niet (%s). "
                "Grant via governance óf koppel het middel op de accountability.",
                self.id, capability, sorted(self.effective_skills()))
            return f"'{self.id}' heeft skill '{capability}' niet in zijn DNA"
        reden = self._domein_weigering(capability)
        if reden:
            self.log.warning("⛔ domeinpoort: %s", reden)
            return reden
        return None

    def handle(self, task: Task) -> Response:
        fout = self._weiger(task.capability)
        if fout:
            return Response(success=False, error=fout)
        ok, result = self._execute_skill(task.capability, task.payload)
        if ok:
            return Response(success=True, data=result)
        return Response(success=False, error=result)

    def use_skill(self, capability: str, payload: dict) -> dict:
        """Zelf een eigen skill gebruiken (voor zelf-geinitieerd werk, niet via de matchmaker)."""
        fout = self._weiger(capability)
        if fout:
            return {"error": fout}
        ok, result = self._execute_skill(capability, payload)
        if ok:
            return result
        return {"error": result}

    def referenced_capabilities(self) -> set[str]:
        """Alle skills die deze rol via een use_skill-aanroep met letterlijke naam
        gebruikt, statisch afgeleid uit de broncode van de klasse-MRO. Basis voor
        de dode-skill-audit."""
        import inspect
        found: set[str] = set()
        for cls in type(self).__mro__:
            if cls.__module__ == "builtins" or cls is threading.Thread:
                continue
            try:
                src = inspect.getsource(cls)
            except (OSError, TypeError):
                continue
            found.update(re.findall(r'use_skill\(\s*["\']([^"\']+)["\']', src))
        return found

    def dormant_capabilities(self) -> set[str]:
        """Skills die de rol aanroept maar niet voert: dode features.
        Leeg = gezond. Niet-leeg = grant ontbreekt, koppeling ontbreekt, of de aanroep is dood.
        Telt gekoppelde middelen mee zodra skill_links_active aan staat."""
        return self.referenced_capabilities() - self.effective_skills()

    def tick(self) -> None:
        """Hartslag-hook: wordt elke cyclus aangeroepen. Default niets.
        Inwoners die zichzelf wakker maken (zoals TimeKeeper) overschrijven dit."""
        pass

    def react(self, event_name: str, handler, *, drop_if_busy: bool = False) -> None:
        """Abonneer op een event en laat het werk op de eigen thread draaien.
        De wrapper keert meteen terug; de handler draait asynchroon via de inbox.
        drop_if_busy=True: gooi het event weg als _busy=True (geen queue-opbouw)."""
        def _enqueue(event: Event) -> None:
            if drop_if_busy and getattr(self, "_busy", False):
                return
            def _job(e=event):
                try:
                    handler(e)
                finally:
                    # Puls-hartslag (generiek, dead man's switch): elke rol die op dag_begint
                    # reageert laat vanzelf een marker na — óók als de handler struikelt, want
                    # de puls BEREIKTE de rol (dat is wat de watchdog op afwezigheid toetst).
                    if event_name == "dag_begint":
                        self._record_heartbeat(e)
            self.inbox.enqueue(_job)
        self.bus.subscribe(event_name, _enqueue)

    def _record_heartbeat(self, event) -> None:
        """Schrijf een dag_begint-hartslag voor deze rol. De dag komt uit de event-`label` (de
        Madrid-kalenderdag die TimeKeeper meestuurt), zodat hij exact matcht met de watchdog.
        Fail-soft: een schrijffout mag de puls nooit breken."""
        try:
            import datetime
            from nooch_village.pulse_watchdog import HeartbeatStore
            day = (getattr(event, "data", {}) or {}).get("label") or datetime.date.today().isoformat()
            HeartbeatStore(os.path.join(self.context.data_dir, "pulse_heartbeat.json")).beat(
                self.id, day, datetime.datetime.now().isoformat(timespec="seconds"))
        except Exception:
            pass

    def run(self) -> None:
        self.log.info("ontwaakt [source=%s] | purpose=%s | skills=%s",
                      self.record.source, self.dna.purpose, self.dna.skills)
        dormant = self.dormant_capabilities()
        if dormant:
            self.log.warning(
                "⚠️ dode capabilities bij ontwaken: '%s' roept %s aan zonder grant. "
                "Grant via governance, koppel het middel op de accountability, of verwijder de aanroep.",
                self.id, sorted(dormant))
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as e:
                self.log.error("tick faalde: %s", e)
            item = self.inbox.take(timeout=0.5)
            if item is None:
                continue
            if isinstance(item, Task):
                self.log.info("taak ontvangen: %s", item.capability)
                resp = self.handle(item)
                self.bus.publish(Event("task_completed", {
                    "task_id": item.id, "by": self.id, "capability": item.capability,
                    "success": resp.success, "data": resp.data, "error": resp.error,
                    "request_id": item.request_id}, self.id))
            else:  # event-job: callable die de handler met het event aanroept
                try:
                    item()
                except Exception as e:
                    self.log.error("event-handler faalde: %s", e)
            self.inbox.done()

    def reload(self, record: Record) -> None:
        """Governance gaf me een nieuw record (bv. extra accountability/skill)."""
        self.record = record
        self.dna = record.definition
        self.log.info("DNA herladen (v%s) | skills=%s", record.version, self.dna.skills)

    def stop(self) -> None:
        self._stop_event.set()


class Circle(Inhabitant):
    """Van buiten een rol, van binnen een dorp. Heeft geen handen: delegeert."""

    def __init__(self, record, bus, registry, context, inner_bus=None):
        super().__init__(record, bus, registry, context)
        self.inner_bus = inner_bus or EventBus(name=record.id)
        self.members: dict[str, Inhabitant] = {}

    def add_member(self, inhabitant: Inhabitant) -> None:
        self.members[inhabitant.id] = inhabitant

    def capabilities(self) -> list[str]:
        caps = set(self.dna.skills)
        for m in self.members.values():
            caps.update(m.capabilities())          # later: cureren via Lead Link
        return sorted(caps)

    def handle(self, task: Task) -> Response:
        for m in self.members.values():            # delegeren, niet zelf uitvoeren
            if task.capability in m.capabilities():
                m.deliver(task)
                return Response(success=True, data={"delegated_to": m.id})
        return Response(success=False, error=f"cirkel '{self.id}' heeft geen member voor '{task.capability}'")

    def start(self) -> None:
        for m in self.members.values():
            m.start()
        super().start()

    def stop(self) -> None:
        for m in self.members.values():
            m.stop()
        super().stop()
