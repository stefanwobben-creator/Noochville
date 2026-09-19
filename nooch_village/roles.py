"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import hashlib, os, json, time
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from nooch_village.util import atomic_write_json, run_bounded, is_due


from nooch_village.mission import ANCHOR_PURPOSE as _NOOCHIE_MISSION
from nooch_village.inhabitant import _persona_ladder, Inhabitant
from nooch_village.event_bus import Event
from nooch_village.governance import Gate, proposal_from_dict, proposal_to_dict
from nooch_village.insight import Insight
# De dagcadans is INFRASTRUCTUUR en woont in `dagcyclus.py` — zie de kop daar: hij zat hier,
# in een rol, en toen die rol sliep stond het dorp drie dagen stil. Deze twee namen blijven
# hier alleen als doorverwijzing, zodat bestaande imports niet stil iets anders gaan betekenen.
from nooch_village.dagcyclus import cadence_events, should_fire_daily


def _bounded_trends(fetch_fn, budget: float, log=None) -> dict:
    """Haal Google Trends best-effort op, met een harde tijdslimiet.

    Levert de skill-output als die binnen `budget` seconden klaar is; anders een
    {"error": ...}-dict die field_note netjes opvangt. Zo is de dagelijkse Field Note
    nooit gegijzeld door een trage of rate-limited Trends-call.
    """
    ok, res = run_bounded(fetch_fn, budget)
    if ok:
        return res
    reden = "tijdslimiet overschreden" if res is None else str(res)
    if log is not None:
        log.warning("google_trends best-effort overgeslagen: %s", reden)
    return {"error": f"google_trends: {reden}", "keywords": {}, "rows": []}


def _extract_pulse_metrics(plausible: dict) -> list[tuple[str, float]]:
    """Extraheer numerieke metrics uit een plausible-resultaat.

    Retourneert (metric_name, value)-tuples voor aanwezige, niet-None waarden.
    Verzint niets: ontbrekende of fout-resultaten geven een lege lijst.
    """
    results = plausible.get("results", {}) if isinstance(plausible, dict) else {}
    out = []
    for key in ("visitors", "pageviews"):
        v = (results.get(key) or {}).get("value")
        if v is not None:
            try:
                out.append((key, float(v)))
            except (TypeError, ValueError):
                pass
    for row in plausible.get("utm_sources", []) if isinstance(plausible, dict) else []:
        src = (row.get("utm_source") or "").strip()
        v = row.get("visitors")
        if src and v is not None:
            try:
                out.append((f"visitors_via_{src}", float(v)))
            except (TypeError, ValueError):
                pass
    return out


def _publish_keyword_proposed(bus, from_id: str, word: str, demand: dict, library) -> bool:
    """Dedupliceer en publiceer een keyword_proposed-event.

    Controleert of het woord al bekend is in de bibliotheek (élke status blokkeert).
    Retourneert True als het event gepubliceerd is.
    """
    if library is not None and library.status(word) is not None:
        return False
    bus.publish(Event("keyword_proposed", {"word": word, "demand": demand, "from": from_id}, from_id))
    return True










class Facilitator(Inhabitant):
    """Bewaakt de geldigheid van governance-voorstellen zonder inhoudelijk te oordelen.
    Draait de poort G0-G4 en beslist adopt-by-default of escaleren naar de mens.
    Integreert bezwaren NOOIT automatisch: alleen de mens kan dat doen.

    DE DAGCADANS ZAT HIER, EN DAT WAS EEN FOUT. `dag_begint`, `dag_eindigt`, `maand_begint` en
    `kwartaal_begint` werden gepubliceerd vanuit deze rol. Toen de afslanking van 28 augustus 2026
    `facilitator` slapend legde, luidde niemand meer de bel en stond het dorp drie dagen stil —
    zonder foutmelding, want er faalde niets; er tikte alleen niets meer.

    Een hartslag hoort niet af te hangen van een deelnemer: over een rol mag het dorp besluiten,
    over zijn klok niet. De cadans woont daarom in `dagcyclus.Dagcyclus`, naast de rollen in plaats
    van erin. Deze rol mag hierna gewoon slapen.

    DE POORT IS HIER OOK WEG (6 september 2026), en om exact dezelfde reden. `_on_proposal_raised`
    draaide G0-G4 en was in productie de ENIGE luisteraar op `proposal_raised`. Zolang dat zo was,
    kon niemand deze rol archiveren of verslapen zonder dat élk governance-voorstel stil bleef
    liggen. Dezelfde weeffout als de klok, één laag dieper: over een rol mag het dorp besluiten,
    over de REGELS WAARMEE het besluit niet.

    De poort woont nu in `governance.GovernanceGate`, naast de Secretary. Wat hier overblijft is een
    lege rol, en dat is met opzet zichtbaar gelaten: archiveren is een governance-handeling, geen
    commit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _on_proposal_raised_HISTORISCH(self, event: Event) -> None:
        proposal = proposal_from_dict(event.data["proposal"])
        self.log.info("📋 voorstel ontvangen van '%s': %s %s",
                      proposal.proposer_role, proposal.change.kind.value,
                      proposal.change.role_id or "")

        passed, gate_name, gate_reason = self._gate.check(
            proposal, self.context.records, self.context)

        if not passed and gate_name == "G0":
            # G0-fout: structureel ongeldig, terug naar proposer — geen menselijk oordeel
            self.log.warning("❌ G0 ongeldig: %s", gate_reason)
            self.bus.publish(Event("proposal_invalid", {
                "proposal_id": proposal.id,
                "proposer_role": proposal.proposer_role,
                "gate": "G0",
                "reason": gate_reason,
            }, self.id))
            return

        if not passed:
            # G1-G4: escaleren naar mens
            proposal.status = "escalated"
            proposal.escalation_gate = gate_name
            proposal.escalation_reason = gate_reason
            self.log.warning("🙋 escaleert naar mens (poort %s): %s", gate_name, gate_reason)
            # Sla op bij Secretary zodat governance_verdict het kan ophalen
            self.bus.publish(Event("_store_pending_proposal",
                                   {"proposal": proposal_to_dict(proposal)}, self.id))
            self.bus.publish(Event("governance_review_requested", {
                "proposal_id": proposal.id,
                "proposal": proposal_to_dict(proposal),
                "gate": gate_name,
                "reason": gate_reason,
                "trigger_example": proposal.trigger_example,
            }, self.id))
            return

        # Alles slaagt → direct aannemen
        proposal.status = "adopted"
        self.log.info("✅ voorstel aangenomen via poort (alle G0-G4 geslaagd)")
        self.bus.publish(Event("proposal_gate_passed",
                               {"proposal": proposal_to_dict(proposal)}, self.id))




# ── Metric-advies (deterministisch placeholder voor latere LLM-stap) ───────
# v1-regel: keep als de metric een bekende groei-indicator of doelkoppeling
# heeft. Bij onbekende metrics: fail-closed naar skip.
# TODO: vervang later door een LLM-stap die de strategy/goals meeleest.

_METRIC_ADVICE: dict[str, tuple[str, str]] = {
    "visitors":       ("keep", "Directe indicator voor organisch bereik — kern groeidoel."),
    "pageviews":      ("keep", "Meet content-engagement; proxy voor missie-verspreiding."),
    "bounce_rate":    ("skip", "Geen actief groeidoel op dit moment; herintroduceren bij conversie-focus."),
    "visit_duration": ("skip", "Informatief maar niet gekoppeld aan een actief doel."),
}
_DEFAULT_METRIC_ADVICE = ("skip", "Geen bekende doelkoppeling — sla over tot verder onderzoek.")


def advise_metrics(catalog: list[str], context) -> list[dict]:
    """Geeft per metric een keep/skip + rationale.

    Pure functie: deterministisch en reproduceerbaar.
    context is gereserveerd voor de toekomstige LLM-variant (nu ongebruikt).
    """
    result = []
    for metric in catalog:
        verdict, rationale = _METRIC_ADVICE.get(metric, _DEFAULT_METRIC_ADVICE)
        result.append({"metric": metric, "verdict": verdict, "rationale": rationale})
    return result


def _clip(s: str, n: int) -> str:
    """Knip op een woordgrens met ellipsis, nooit midden in een woord."""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n].rstrip()
    sp = cut.rfind(" ")
    if sp > n * 0.6:                                       # alleen terug naar spatie als zinnig
        cut = cut[:sp]
    return cut.rstrip(" ,;:") + "…"


def _parse_noochie_report(text: str) -> tuple[list[str], str]:
    """Haal tot 3 BEVINDING-regels en de reflectievraag (VRAAG, terugval SUGGESTIE) uit
    Noochie's antwoord. Robuust tegen markdown-bold en opsomtekens. Retourneert (findings, vraag)."""
    findings: list[str] = []
    vraag = ""
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("*-•# ").strip()
        low = line.lower()
        # Beide talen: de prompt vraagt Engels, maar een model dat terugvalt op Nederlands mag de
        # bevindingen niet laten verdwijnen — dan blijft er een leeg dagrapport over zonder fout.
        if (low.startswith("bevinding") or low.startswith("finding")) and ":" in line:
            v = line.split(":", 1)[1].strip().strip("* ").strip()
            if v:
                findings.append(v)
        elif (low.startswith("vraag") or low.startswith("reflectievraag")
              or low.startswith("suggestie") or low.startswith("question")
              or low.startswith("reflection")) and ":" in line and not vraag:
            vraag = line.split(":", 1)[1].strip().strip("* ").strip()
    return findings[:3], vraag


class Noochie(Inhabitant):
    """Belichaamt de missie, bepleit en genereert creatieve governance-voorstellen.
    Schrijft ook het dagelijkse dorpsbulletin (bulletin-mandaat geabsorbeerd van Ronnie).
    Reageert op de Field Note en reflecteert periodiek met een nieuw voorstel."""

    # ── bulletin-mandaat (afsplitsbaar blok, geabsorbeerd van Ronnie) ────────
    _TRACK = (
        "dag_begint",
        "pulse_completed",
        "keyword_decided",
        "governance_changed",
        "tension_sensed",
        "means_gap_sensed",
        "tijdgeest_pulse_completed",
        "keyword_proposed",
        "gsc_pulse_completed",
        "competitor_signal",
        "linkbuilding_target",
        "competitor_interest",
        "locale_insight",
        "project_completed",
        "project_awaiting_review",
    )

    _MAX_NUDGES_PER_PULSE = 5          # dek-plafond: Noochie overspoelt de borden niet met nudges

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ── missie-werk ───────────────────────────────────────────────────────
        self.react("pulse_completed", self._on_pulse_completed)
        self.react("pulse_completed", self._nudge_scope_matches)   # Level 3: proactief de juiste rol wijzen
        self.react("project_discovery_ready", self._on_discovery_ready)
        # ── bulletin-mandaat ──────────────────────────────────────────────────
        self._events_today: list[dict] = []
        for name in self._TRACK:
            self.react(name, self._collect_event)
        self.react("dag_eindigt", self._on_dag_eindigt)

    def _on_discovery_ready(self, event: Event) -> None:
        """Ontvang de menukaart van een discovery-project en produceer een advies.

        Publiceert project_advice_ready met {project_id, advice} en geeft
        het project terug aan de eigenaar (blocked_on → owner).
        Maakt GEEN governance-voorstel en raakt GEEN record aan.
        """
        pid     = event.data.get("project_id")
        catalog = event.data.get("catalog", [])
        if not pid:
            return
        advice = advise_metrics(catalog, self.context)
        self.bus.publish(Event("project_advice_ready",
                               {"project_id": pid, "advice": advice}, self.id))
        ledger = getattr(self.context, "projects", None)
        if ledger is not None:
            project = ledger.get(pid)
            owner   = (project or {}).get("owner", "website_watcher")
            ledger.block(pid, owner)
        self.log.info("🎯 discovery-advies: %d metrics beoordeeld, project terug bij eigenaar", len(advice))

    # ── Level 3: proactieve scope-nudge (optie 1 — alleen wijzen, de rol beslist) ────────────────
    def _scope_roster(self, records) -> list:
        """De roster voor de match: niet-gearchiveerde rollen (geen cirkels, niet Noochie zelf) MÉT
        skills, elk met naam + accountabilities + skills. Zonder skills → weglaten (kan niets concreets)."""
        from nooch_village import org
        out = []
        for r in records.all():
            if getattr(r, "archived", False) or r.id == self.id or org.is_circle(r):
                continue
            sk = list(getattr(r.definition, "skills", []) or [])
            if not sk:
                continue
            out.append({"role_id": r.id,
                        "name": getattr(r.definition, "name", "") or r.id.split("__")[-1],
                        "accountabilities": list(getattr(r.definition, "accountabilities", []) or []),
                        "skills": sk})
        return out

    @staticmethod
    def _project_text(p: dict) -> str:
        """Scope + omschrijving + laatste dialoog van een project → context voor de match."""
        recent = " | ".join(str(m.get("text", "")) for m in (p.get("log") or [])[-5:])
        return f"{p.get('scope', '')}. {p.get('description', '') or ''}. Dialoog: {recent}".strip()

    def _notify_role(self, role_id: str, pid: str) -> None:
        """Notificatie aan de genudgede rol, zodat de nudge de rol ook echt bereikt (fail-soft)."""
        try:
            import os
            from nooch_village.notifications import NotifStore
            NotifStore(os.path.join(self.context.data_dir, "notifications.json")).add(
                "role", role_id, pid, by="noochie", snippet="scope-nudge: dit lijkt binnen jouw scope")
        except Exception:
            pass

    def _nudge_scope_matches(self, event: Event = None) -> None:
        """Loop actieve projecten langs; waar één rol (niet de eigenaar, niet Noochie) het project binnen
        haar accountabilities ÉN skill heeft, plaats een nudge-comment + notificatie. ALLEEN wijzen (optie
        1): Noochie maakt zelf geen taken. Hard: de skill moet in het DNA (afgedwongen in scope_nudge).
        Gededupt per (project, rol), gedekt op _MAX_NUDGES_PER_PULSE. Fail-closed: elke fout → geen nudge."""
        projects = getattr(self.context, "projects", None)
        records = getattr(self.context, "records", None)
        if projects is None or records is None:
            return
        try:
            from nooch_village.scope_nudge import invoer_vinger, match_project_to_role
            roster = self._scope_roster(records)
            if not roster:
                return
            done, gevraagd, overgeslagen = 0, 0, 0
            for p in projects.active():
                if done >= self._MAX_NUDGES_PER_PULSE:
                    break
                pid, owner = p.get("id"), p.get("owner")
                text = self._project_text(p)
                if not pid or not text:
                    continue
                # POORT 1 — een rol die dit project al genudged kreeg, kan er niets meer opleveren.
                # Deze check stond ACHTER de call; hier haalt hij kandidaten weg vóór de call, en
                # blijft er niets over, dan hoeft het model niet gebeld te worden.
                al = set(p.get("scope_nudges") or [])
                cand = [r for r in roster                                # niet de eigenaar nudgen
                        if r["role_id"] != owner and r["role_id"] not in al]
                if not cand:
                    overgeslagen += 1
                    continue
                # POORT 2 — de vloer. Dezelfde tekst en dezelfde kandidaten geven hetzelfde antwoord;
                # gemeten verandert er per dag 2% van de actieve projecten (7 van de 332). Dit is de
                # vorm van `kennis_dedup`: deterministisch waar het kan, het model voor de rest.
                vinger = invoer_vinger(text, cand)
                if vinger and projects.scope_nudge_checked(pid) == vinger:
                    overgeslagen += 1
                    continue
                m, beantwoord = match_project_to_role(text, cand, name=self.id, met_status=True)
                gevraagd += 1
                # FAIL-OPEN: alleen onthouden als het MODEL sprak. Een 'geen match' is een oordeel,
                # 'geen model' is een storing — die vastleggen zou de nudge voor dit project stilzetten
                # tot iemand het aanraakt.
                if beantwoord:
                    projects.mark_scope_nudge_checked(pid, vinger)
                # De poort hierboven is een KOSTENFILTER (bespaart de call); deze is de GARANTIE
                # (geen tweede nudge). Ze zeggen hetzelfde en dat is hier de bedoeling: de filter
                # leunt op de machine-check in `match_project_to_role`, en die staat in een andere
                # module. Zakt die ooit weg, dan vangt deze regel het — een dubbele nudge is voor de
                # ontvanger niet te onderscheiden van een nieuwe vraag.
                if not m or projects.already_scope_nudged(pid, m["role_id"]):
                    continue
                naam = m["name"] or m["role_id"]
                projects.add_feed_entry(
                    pid, f"@{naam}, dit lijkt binnen jouw scope (skill: {m['skill']}). Oppakken?",
                    kind="comment", author_type="persona",
                    author_id=getattr(self.record, "persona_id", "") or "")
                projects.mark_scope_nudge(pid, m["role_id"])
                self._notify_role(m["role_id"], pid)
                done += 1
            if done or gevraagd or overgeslagen:
                self.log.info("🔔 Noochie: %d nudge(s) · %d model-vraag/vragen · %d overgeslagen "
                              "door de vloer", done, gevraagd, overgeslagen)
        except Exception as e:
            self.log.debug("scope-nudge overgeslagen (fail-closed): %s", e)

    def _on_pulse_completed(self, event: Event) -> None:
        note_path = event.data.get("note_path")
        if not (note_path and os.path.exists(note_path)):
            return
        note = open(note_path).read()
        self._weigh_in(note)

    def _weigh_in(self, field_note: str) -> None:
        """Leest de Field Note door een missie-lens en senst spanning als er drift is.

        Deduplicatie: dezelfde reason-tekst wordt niet opnieuw als spanning gesensed
        totdat Noochie een nieuwe unieke beoordeling produceert.
        """
        from nooch_village.llm import reason
        from nooch_village.coherence import parse_verdict_reason
        prompt = (
            f"You are Noochie, the mission voice of Nooch.earth. Sharp, level-headed, and you look "
            f"at the WHOLE: traffic, market, mission alignment, opportunities and risks.\n"
            f"Mission: {_NOOCHIE_MISSION}\n\n"
            f"Today's Field Note:\n{field_note}\n\n"
            "Rules:\n"
            "- Base yourself ONLY on what is in the Field Note. Invent no names, partners or "
            "figures; if you do not know something, do not write it.\n"
            "- Every finding is ONE complete, concise sentence (max ~25 words). No fragments.\n"
            "- Close with one sharp REFLECTION QUESTION to the founder that makes him think "
            "(not an action he is probably already taking).\n\n"
            "Answer exactly like this:\n"
            "FINDING: <one complete sentence>\n"
            "FINDING: <one complete sentence>\n"
            "FINDING: <one complete sentence>\n"
            "QUESTION: <one reflection question>\n"
            "VERDICT: ok\n"
            "REASON: <one sentence>\n\n"
            "(use VERDICT: off_mission if the recommended direction clashes with or misses the mission)"
        )
        result = reason(prompt, call_site="noochie_weigh_in",
                        ladder=_persona_ladder(self.context, self.id, "noochie_weigh_in")
                        ) or "(geen LLM beschikbaar)"
        # Beide talen geldig, één interne waarde. De prompt vraagt sinds 06-09-2026 `off_mission`,
        # maar `niet_ok` blijft de waarde die hieronder wordt vergeleken ÉN die in het dagrapport
        # wordt opgeslagen (`_persist_daily`). Zou ik de interne waarde meevertalen, dan gaan de
        # bestaande rapporten in de cockpit een onbekend oordeel dragen — een migratie voor niets.
        verdict, reason_text = parse_verdict_reason(
            result, frozenset({"ok", "niet_ok", "off_mission"}))
        if verdict == "off_mission":
            verdict = "niet_ok"
        findings, question = _parse_noochie_report(result)

        if verdict == "ok":
            self.log.info("🎯 Missie-alignment: ok (%s)", reason_text)
        elif verdict == "niet_ok":
            self.log.info("🎯 Missie-alignment: niet_ok (%s)", reason_text)
            h = hashlib.sha256(reason_text.encode()).hexdigest()[:16]
            if getattr(self, "_last_weigh_hash", None) != h:
                self._last_weigh_hash = h
                self.sense_tension(reason_text, kind="operational")
            else:
                self.log.info("🎯 missie-lens ongewijzigd — spanning niet herhaald")
        else:  # unparseable
            self.log.info("🎯 Missie-alignment: onverstaanbaar antwoord — fail-closed als niet_ok")
            h = hashlib.sha256(result.encode()).hexdigest()[:16]
            if getattr(self, "_last_weigh_hash", None) != h:
                self._last_weigh_hash = h
                self.sense_tension(result, kind="operational")
            else:
                self.log.info("🎯 missie-lens ongewijzigd — spanning niet herhaald")

        self.bus.publish(Event("noochie_weighed_in", {"oordeel": result}, self.id))
        self._persist_daily(verdict, reason_text or result, findings, question)

    def _persist_daily(self, verdict: str, tekst: str,
                       findings: list[str] | None = None, question: str = "") -> None:
        """Bewaar Noochie's dag-rapport (3 bevindingen + 1 reflectievraag) voor de cockpit."""
        import time as _time
        path = os.path.join(self.context.data_dir, "noochie_daily.json")
        try:
            from nooch_village.util import atomic_write_json
            atomic_write_json(path, {
                "date": _time.strftime("%Y-%m-%d"),
                "verdict": verdict or "onbekend",
                "findings": [_clip(f, 320) for f in (findings or [])][:3],
                "question": _clip(question, 320),
                "oordeel": (tekst or "").strip()[:300],   # back-compat
            })
        except Exception as e:
            self.log.info("kon Noochie-dagrapport niet opslaan: %s", e)

    def _reflect(self) -> None:
        """Genereert periodiek één creatief voorstel. LOG-ONLY sinds 19 september 2026.

        Dit escaleerde via `_sense_gap` naar een spanning in de human inbox. Die aanroep is hier
        weg; de methode zelf zit nog op `Inhabitant` en valt met de rest van de sensing-cluster.
        Wat overblijft is het voorstel zelf, en dat gaat naar het log.

        EERLIJK OVER WAT DIT NU IS: één LLM-call per reflectie-interval waarvan de uitkomst
        nergens anders landt dan in een logregel. Leest niemand dat log, dan hoort deze hele
        methode weg — houd hem niet omdat hij er staat. Noochie slaapt op dit moment, dus hij
        draait nergens; deze code bestaat opdat hij bij het wekken niet stukloopt."""
        from nooch_village.llm import reason
        prompt = (
            f"You are Noochie, the idea engine of Nooch.earth.\n"
            f"Mission: {_NOOCHIE_MISSION}\n\n"
            "Formulate one concrete tension the village should pick up to serve the mission "
            "better. Actionable with content, SEO or governance — no advertising. "
            "Max 3 sentences. Format: 'The village lacks [what]. [Proposal] would help because "
            "[reason]. This advice flips if [condition under which another route is better].' "
            "Answer in English."
        )
        result = reason(prompt, call_site="noochie_reflect")
        if not result:
            return
        # De hash blijft: hij maakt in het log zichtbaar of dit hetzelfde voorstel is als de
        # vorige keer. Er is geen store meer die hem onthoudt, en dus ook geen dedup-belofte.
        h = hashlib.sha256(result.encode()).hexdigest()[:16]
        self.log.info("💡 Noochie-voorstel [%s]: %s", h, " ".join(result.split())[:300])

    # ── bulletin-mandaat (afsplitsbaar blok) ──────────────────────────────────

    def _collect_event(self, event: Event) -> None:
        self._events_today.append({
            "name": event.name,
            "by":   event.data.get("by", event.sender),
            "note": event.data.get("boodschap", "") or event.data.get("note_path", ""),
            "project_id": event.data.get("project_id", ""),   # voor project_completed → scope-lookup bij dag-einde
        })

    # Bulletin-werkwoord per levenscyclus-event: afgerond én wacht-op-review (review-gate) op één regel.
    _BULLETIN_VERBS = {"project_completed": "rondde af", "project_awaiting_review": "wacht op review"}

    def _enrich_completions(self, events: list) -> list:
        """Geef levenscyclus-events een leesbare regel: '<owner> rondde af: <scope>' (Done) of
        '<owner> wacht op review: <scope>' (checklist af, review-gate). Scope + owner komen UIT de ledger
        op project_id (records/ledger = de waarheid; de payload draagt bewust geen scope). Project
        onvindbaar in de ledger → regel overslaan (fail-closed), geen crash."""
        ledger = getattr(self.context, "projects", None)
        out = []
        for e in events:
            verb = self._BULLETIN_VERBS.get(e.get("name"))
            if verb is None:
                out.append(e)
                continue
            pid = e.get("project_id") or ""
            p = ledger.get(pid) if (ledger is not None and pid) else None
            if not p:
                continue                                    # onvindbaar → regel overslaan
            sc = p.get("scope")
            scope = sc if isinstance(sc, str) else ((sc.get("goal") or sc.get("title") or "")
                                                    if isinstance(sc, dict) else str(sc))
            out.append({**e, "note": f"{self._owner_label(p.get('owner', ''))} {verb}: {scope}"})
        return out

    def _owner_label(self, owner_id: str) -> str:
        """Leesbare naam van een rol (records = waarheid), terugvallend op het id."""
        recs = getattr(self.context, "records", None)
        if recs is not None and owner_id:
            r = recs.get(owner_id)
            nm = getattr(getattr(r, "definition", None), "name", "") if r else ""
            if nm:
                return nm
        return owner_id or "?"

    def _on_dag_eindigt(self, event: Event) -> None:
        """Schrijf het dagbulletin op basis van de events en de Field Note van vandaag."""
        events = self._enrich_completions(list(self._events_today))
        self._events_today.clear()

        datum = date.today().isoformat()
        field_note_path = os.path.join(
            self.context.data_dir, "output", f"field_note_{datum}.md"
        )
        field_note = ""
        if os.path.exists(field_note_path):
            try:
                with open(field_note_path, encoding="utf-8") as fh:
                    field_note = fh.read()
            except OSError:
                pass

        result = self.use_skill("bulletin_schrijven", {
            "events":     events,
            "datum":      datum,
            "field_note": field_note,
        })

        if "error" in result:
            self.log.warning("⚠️ bulletin niet geschreven: %s", result["error"])
            return
        if result.get("no_data"):
            # Een dag zonder events (in de praktijk: een herstart halverwege de dag, want
            # `dag_begint` wordt altijd verzameld) — de skill schrijft dan bewust niets (scope 57).
            self.log.info("📋 geen bulletin: %s", result.get("reason", "geen events"))
            return

        self.bus.publish(Event("bulletin_geschreven",
                               {"path": result["path"], "by": self.id,
                                "event_count": result.get("event_count", 0)}, self.id))
        self.log.info("📋 bulletin gepubliceerd: %s", result["path"])


