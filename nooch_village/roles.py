"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import hashlib, os, json, time
from datetime import date
from nooch_village.util import atomic_write_json
from nooch_village.mission import ANCHOR_PURPOSE as _NOOCHIE_MISSION
from nooch_village.inhabitant import Inhabitant
from nooch_village.event_bus import Event
from nooch_village.governance import Gate, proposal_from_dict, proposal_to_dict


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


def cadence_events(d) -> list[str]:
    """Pure helper: geeft de event-namen die op datum d gepubliceerd moeten worden.

    Altijd: dag_begint. Bovendien:
      maand_begint    — op dag 1 van elke maand
      kwartaal_begint — op dag 1 van jan/apr/jul/okt
    """
    events = ["dag_begint"]
    if d.day == 1:
        events.append("maand_begint")
        if d.month in (1, 4, 7, 10):
            events.append("kwartaal_begint")
    return events


class WebsiteWatcherWorker(Inhabitant):
    """Hoort de ochtendbel en voert zelf zijn groei-puls uit: echte data ophalen,
    duiden tegen de missie, en een Field Note schrijven. Senst een spanning bij verval."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.react("project_advice_ready", self._on_advice_ready)
        self._busy = False

    def _setup_events(self) -> None:
        # Alle dag_begint-werk loopt via _morning_pulse: geen zelfstandige _maybe_reflect-subscriptie.
        self.react("dag_begint", self._morning_pulse, drop_if_busy=True)

    def _on_advice_ready(self, event: Event) -> None:
        """Ontvang advies van Noochie: voeg keep-metrics toe aan het monitoring-overzicht
        en completeer het project. Geen voorstel, geen gate, geen inbox.
        """
        pid    = event.data.get("project_id")
        advice = event.data.get("advice", [])
        if not pid:
            return
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            return
        project = ledger.get(pid)
        if project is None or project.get("owner") != self.id:
            return
        keep = [a["metric"] for a in advice if a.get("verdict") == "keep"]
        monitoring = getattr(self.context, "monitoring", None)
        if monitoring is not None and keep:
            monitoring.add_metrics(self.id, keep)
        outcome = "monitoring: " + ", ".join(sorted(keep)) if keep else "monitoring: (leeg)"
        ledger.complete(pid, outcome)
        self.log.info("📊 monitoring bijgewerkt: %s", keep)

    def _morning_pulse(self, event: Event) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            self.log.info("☀️ groei-puls gestart")
            plausible = self.use_skill("plausible_stats", {"period": "7d"})
            trends = self.use_skill("google_trends", {})
            note = self.use_skill("field_note", {"plausible": plausible, "trends": trends})

            self._log_pulse_metrics(plausible)

            self._propose_related(trends)
            self._sense_goal_gap(plausible)

            if note.get("tension"):
                self.sense_tension(note.get("reason", "Verval gedetecteerd in de groei-puls"),
                                   kind="operational")
            self.bus.publish(Event("pulse_completed",
                {"by": self.id, "note_path": note.get("path"), "tension": note.get("tension")}, self.id))
            self.log.info("📝 Field Note klaar -> %s", note.get("path"))
        finally:
            self._busy = False
        self._maybe_reflect(None)
        self._scan_queued_projects(None)

    def _log_pulse_metrics(self, plausible: dict) -> None:
        """Log de metrics die in het monitoring-overzicht staan én in de puls aanwezig zijn."""
        obs        = getattr(self.context, "observations", None)
        monitoring = getattr(self.context, "monitoring",   None)
        if obs is None:
            return
        monitored   = monitoring.get_metrics(self.id) if monitoring else []
        pulse_dict  = dict(_extract_pulse_metrics(plausible))
        for metric in monitored:
            if metric in pulse_dict:
                obs.record(self.id, metric, pulse_dict[metric])

    def _sense_goal_gap(self, plausible: dict) -> None:
        """Vergelijk werkelijke bezoekerstrend met de run-rate die actieve doelen vereisen.

        Twee signalen:
        1. Theorie-gat  — doel-metriek (bijv. pairs_sold) is niet meetbaar in de puls;
                          eenmalig sensen, daarna elke 14 dagen opnieuw.
        2. Off-pace     — bezoekerstrend 3+ pulsen consistent dalend terwijl doel nadert;
                          eenmalig sensen, daarna pas na 7 dagen opnieuw.
        Bij een enkele ruis-hobbel geen spanning: minimum 3 opeenvolgende dalende pulsen.
        """
        strategy_data = getattr(self.context, "strategy", None) or {}
        goals = [g for g in strategy_data.get("goals", []) if g.get("active")]
        if not goals:
            return

        visitors = (plausible.get("results", {}).get("visitors") or {}).get("value")

        # Schrijf huidige pulse naar geschiedenis (rolling log)
        history_path = os.path.join(self.context.data_dir, "pulse_history.jsonl")
        with open(history_path, "a") as f:
            f.write(json.dumps({"ts": time.time(), "visitors_7d": visitors}) + "\n")

        # Laad recente geschiedenis (max 10 pulsen)
        history = []
        with open(history_path) as f:
            for line in f:
                try:
                    history.append(json.loads(line.strip()))
                except Exception:
                    pass
        history = history[-10:]

        # Laad/maak gap-state voor deduplicatie
        state_path = os.path.join(self.context.data_dir, "goal_state.json")
        try:
            with open(state_path) as f:
                state = json.load(f)
        except Exception:
            state = {}

        today = date.today().isoformat()
        changed = False

        for goal in goals:
            goal_id = goal["id"]
            metric  = goal.get("metric", "")
            target  = goal.get("target", 0)
            unit    = goal.get("unit", "")
            wend    = goal.get("window_end", "")

            # Signaal 1 — theorie-gat
            if metric not in ("visitors", "pageviews"):
                key  = f"theory_gap_{goal_id}"
                last = state.get(key)
                days_since = None
                if last:
                    from datetime import date as _d
                    days_since = (_d.fromisoformat(today) - _d.fromisoformat(last)).days
                if last is None or (days_since is not None and days_since >= 14):
                    self.sense_tension(
                        f"Doel '{goal_id}' vereist meting van '{metric}' "
                        f"(target: {target} {unit} voor {wend}), maar de puls meet "
                        f"alleen bezoekers. De koppeling van bezoekersdata naar "
                        f"daadwerkelijke '{metric}' ontbreekt in de puls.",
                        kind="operational",
                    )
                    state[key] = today
                    changed = True
                    self.log.info("🎯 theorie-gat gesensed voor doel '%s'", goal_id)

            # Signaal 2 — off-pace bezoekerstrend
            v_list = [h["visitors_7d"] for h in history if h.get("visitors_7d") is not None]
            if len(v_list) >= 3:
                last3 = v_list[-3:]
                structureel_dalend = all(last3[i] > last3[i + 1] for i in range(len(last3) - 1))
                if structureel_dalend:
                    key  = f"offpace_{goal_id}"
                    last = state.get(key)
                    days_since = None
                    if last:
                        from datetime import date as _d
                        days_since = (_d.fromisoformat(today) - _d.fromisoformat(last)).days
                    if last is None or (days_since is not None and days_since >= 7):
                        self.sense_tension(
                            f"Bezoekerstrend structureel dalend over {len(last3)} pulsen "
                            f"({last3[0]}→{last3[-1]}): off-pace tegen doel '{goal_id}' "
                            f"({target} {unit} voor {wend}). Positieve bezoekersgroei is "
                            f"vereist als basis voor het verkoopdoel.",
                            kind="operational",
                        )
                        state[key] = today
                        changed = True
                        self.log.info("📉 off-pace spanning gesensed voor doel '%s'", goal_id)

        if changed:
            atomic_write_json(state_path, state)

    def _propose_related(self, trends: dict) -> None:
        from nooch_village.intent import prioritize
        lib = self.context.library
        candidates = []
        for parent_kw, kw_data in (trends.get("keywords") or {}).items():
            for related in kw_data.get("top_related") or []:
                term = related["query"] if isinstance(related, dict) else related
                value = related.get("value", 0) if isinstance(related, dict) else 0
                if lib.status(term) is not None:
                    continue
                candidates.append({
                    "label": term,
                    "description": f"organisch verkeer via missie-keyword {term} op nooch.earth",
                    "_value": value,
                    "_parent": parent_kw,
                })
        ranked = prioritize(candidates, self.context)
        proposed = 0
        for action in ranked:
            if action["dropped"]:
                self.log.info("⏭️ keyword '%s' afgevallen: %s", action["label"], action["drop_reason"])
                continue
            published = _publish_keyword_proposed(
                self.bus, self.id, action["label"],
                demand={"signal": "positive", "interest": action.get("_value", 0),
                        "source": "google_trends_related",
                        "parent_keyword": action.get("_parent", "")},
                library=lib,
            )
            if published:
                proposed += 1
        if proposed:
            self.log.info("🔍 %d kandidaat-woorden doorgestuurd (gerangschikt op doelbijdrage)", proposed)

    # ── Project-werk ───────────────────────────────────────────────────────────

    def run_project(self, project: dict) -> str | None:
        scope = project.get("scope") or {}
        if isinstance(scope, dict) and scope.get("kind") == "discovery":
            return self._run_discovery(project, scope)
        return super().run_project(project)

    def _run_discovery(self, project: dict, scope: dict) -> None:
        pid       = project["id"]
        skill_name = scope.get("skill", "")
        skill     = self.registry.get(skill_name)
        catalog   = skill.available_metrics() if skill is not None and hasattr(skill, "available_metrics") else []
        self.bus.publish(Event("project_discovery_ready",
                               {"project_id": pid, "catalog": catalog}, self.id))
        ledger = getattr(self.context, "projects", None)
        if ledger is not None:
            ledger.block(pid, "noochie")
        self.log.info("📋 discovery '%s': %d metrics, geblokkeerd op noochie", skill_name, len(catalog))
        return None


class TrendsWorker(Inhabitant):
    """Luistert op dag_begint, haalt GSC-queries op en stuurt high_potential-woorden
    die nog niet in de bibliotheek staan door als keyword_proposed naar de Librarian.
    Schrijft wekelijks een GSC-nota met zoekopdracht-analyse en rankings."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._busy = False
        self._nota_interval = float(
            self.context.settings.get("gsc_nota_interval_seconds", str(7 * 24 * 3600)))
        self._last_nota: float = 0.0

    def _setup_events(self) -> None:
        self.react("dag_begint", self._on_dag_begint, drop_if_busy=True)

    def _on_dag_begint(self, event: Event) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            self.log.info("🔎 GSC-puls gestart")
            result = self.use_skill("gsc_performance", {})
            if "error" in result:
                self.log.warning("⚠️ GSC-puls mislukt: %s", result["error"])
                self.bus.publish(Event("gsc_pulse_completed",
                    {"by": self.id, "ok": False, "error": result["error"]}, self.id))
                return
            self.log.info("📊 %d queries opgehaald (%s)", result.get("total", 0),
                          result.get("bucket_counts", {}))
            self._propose_from_gsc(result)
            self._maybe_write_nota(result)
            self.bus.publish(Event("gsc_pulse_completed",
                {"by": self.id, "ok": True,
                 "total": result.get("total", 0),
                 "bucket_counts": result.get("bucket_counts", {})}, self.id))
        finally:
            self._busy = False
        self._maybe_reflect(None)

    def _maybe_write_nota(self, result: dict) -> None:
        now = time.time()
        if self._nota_interval > 0 and now - self._last_nota < self._nota_interval:
            return
        self._last_nota = now
        r = self.use_skill("gsc_report", result)
        path = r.get("path", "?")
        self.log.info("📋 GSC-nota geschreven → %s", path)
        self.bus.publish(Event("gsc_nota_written", {"by": self.id, "path": path}, self.id))

    def _propose_from_gsc(self, result: dict) -> None:
        lib = self.context.library
        proposed = 0
        for row in result.get("rows", []):
            if row["bucket"] != "high_potential":
                continue
            published = _publish_keyword_proposed(
                self.bus, self.id, row["query"],
                demand={
                    "signal": "positive",
                    "interest": row["impressions"],
                    "source": "gsc",
                    "position": row["position"],
                    "bucket": row["bucket"],
                    "impressions": row["impressions"],
                    "clicks": row["clicks"],
                },
                library=lib,
            )
            if published:
                proposed += 1
        if proposed:
            self.log.info("🔍 %d GSC high_potential kandidaten doorgestuurd naar de Librarian", proposed)
        else:
            self.log.info("ℹ️ Geen nieuwe high_potential kandidaten (alles al bekend of geen data)")


class Librarian(Inhabitant):
    """Hoeder van de woordenschat. Bezit het DOMEIN (de bibliotheek): anderen lezen vrij,
    alleen de Librarian cureert. Beoordeelt kandidaat-woorden tegen de missie en escaleert
    de twijfelgevallen naar een mens."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.react("keyword_proposed",    self._on_proposal)
        self.react("human_keyword_verdict", self._on_human_verdict)
        self.react("keyword_evidence",    self._on_evidence)

    def _on_proposal(self, event: Event) -> None:
        word = event.data.get("word")
        demand = event.data.get("demand", {})
        proposer = event.data.get("from", "?")
        self.log.info("📥 kandidaat van %s: '%s'", proposer, word)

        v = self.use_skill("keyword_review", {"word": word, "demand": demand})
        decision = v.get("decision")
        reason = v.get("reason", "")
        lib = self.context.library

        if decision == "known":
            self.log.info("ℹ️ '%s' al bekend: %s", word, v.get("status"))
            self.bus.publish(Event("keyword_decided",
                {"word": word, "status": v.get("status"), "reason": "al vastgelegd in bibliotheek"},
                self.id))
            return
        if decision == "approve":
            lib.curate(word, "approved", rationale=reason, evidence=demand, by=self.id)
            self.log.info("✅ goedgekeurd: '%s' (%s)", word, reason)
            self.bus.publish(Event("keyword_decided",
                {"word": word, "status": "approved", "reason": reason}, self.id))
        elif decision == "reject":
            lib.curate(word, "forbidden", rationale=reason, by=self.id)
            self.log.info("⛔ afgewezen: '%s' (%s)", word, reason)
            self.bus.publish(Event("keyword_decided",
                {"word": word, "status": "forbidden", "reason": reason}, self.id))
        else:  # escalate
            lib.curate(word, "escalated", rationale=reason, evidence=demand, by=self.id)
            self.log.info("🙋 escaleert naar mens: '%s' (%s)", word, reason)
            self.sense_tension(f"Woordkeuze '{word}' vraagt menselijk oordeel: {reason}", kind="governance")
            self.bus.publish(Event("human_decision_needed",
                {"topic": "keyword", "word": word, "reason": reason, "demand": demand}, self.id))

    def _on_human_verdict(self, event: Event) -> None:
        word = event.data.get("word")
        decision = event.data.get("decision", "avoid")    # approved | forbidden | avoid
        reason = event.data.get("reason", "menselijk besluit")
        self.context.library.curate(word, decision, rationale=reason, by="human")
        self.log.info("👤 mens besliste over '%s': %s (%s)", word, decision, reason)
        self.bus.publish(Event("keyword_decided",
            {"word": word, "status": decision, "reason": reason, "by": "human"}, self.id))

    def _on_evidence(self, event: Event) -> None:
        """Ontvangt wetenschappelijk bewijs van de KennisScout.

        Als het woord al 'escalated' is (geen beslissing mogelijk zonder bewijs),
        herbeoordeelt de Librarian het nu met de opgehaalde evidentie.
        """
        word       = event.data.get("word", "")
        evidence   = event.data.get("evidence", [])
        assessment = event.data.get("assessment", "")
        if not word:
            return
        self.log.info("📚 evidentie ontvangen voor '%s': %d bron(nen)", word, len(evidence))

        existing = self.context.library.status(word)
        if existing and existing.get("status") == "escalated" and evidence:
            # Herbeoordeel met verrijkte demand
            enriched = {**(event.data.get("original_demand", {})),
                        "evidence_count": len(evidence),
                        "assessment":     assessment}
            v = self.use_skill("keyword_review", {"word": word, "demand": enriched})
            decision = v.get("decision")
            reason   = v.get("reason", "")
            if decision == "approve":
                self.context.library.curate(
                    word, "approved",
                    rationale=f"{reason} [KennisScout: {assessment[:80]}]",
                    evidence=enriched, by=self.id)
                self.log.info("✅ herzien → goedgekeurd na KennisScout-evidentie: '%s'", word)
                self.bus.publish(Event("keyword_decided",
                    {"word": word, "status": "approved", "reason": reason,
                     "via": "kennis_scout"}, self.id))
            elif decision == "reject":
                self.context.library.curate(
                    word, "forbidden", rationale=reason, by=self.id)
                self.log.info("⛔ herzien → afgewezen na KennisScout-evidentie: '%s'", word)
                self.bus.publish(Event("keyword_decided",
                    {"word": word, "status": "forbidden", "reason": reason,
                     "via": "kennis_scout"}, self.id))
            else:
                self.log.info("🔖 evidentie genoteerd; '%s' blijft escalated", word)
        else:
            status = (existing or {}).get("status", "onbekend")
            self.log.info("🔖 evidentie genoteerd voor '%s' (status: %s)", word, status)


class Facilitator(Inhabitant):
    """Bewaakt de geldigheid van governance-voorstellen zonder inhoudelijk te oordelen.
    Draait de poort G0-G4 en beslist adopt-by-default of escaleren naar de mens.
    Integreert bezwaren NOOIT automatisch: alleen de mens kan dat doen.
    Verzorgt ook de dagcyclus-cadans (dag_begint, dag_eindigt, maand_begint, kwartaal_begint)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ── governance-poort ──────────────────────────────────────────
        self._gate = Gate()
        self.react("proposal_raised", self._on_proposal_raised)
        # ── dagcyclus-cadans ──────────────────────────────────────────
        self._last_day: str | None = None
        self._last_beat: float = 0.0
        self._first_ring: bool = True
        self._interval: float = float(self.context.settings.get("heartbeat_seconds", 0) or 0)

    def tick(self) -> None:
        today = date.today()
        now = time.time()
        if self._interval > 0:
            if now - self._last_beat >= self._interval:
                self._last_beat = now
                self._ring("demo-puls", today)
            return
        if today.isoformat() != self._last_day:
            self._last_day = today.isoformat()
            self._ring(today.isoformat(), today)

    def _ring(self, label: str, today) -> None:
        if not self._first_ring:
            self.bus.publish(Event("dag_eindigt", {"label": label}, self.id))
        self._first_ring = False
        for name in cadence_events(today):
            self.log.info("🔔 %s (%s)", name, label)
            self.bus.publish(Event(name, {"label": label}, self.id))

    def _on_proposal_raised(self, event: Event) -> None:
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


class TijdgeestWachter(Inhabitant):
    """Volgt de lange culturele taalverschuiving via Google Books Ngram Viewer.
    Observeert en voedt WebsiteWatcherWorker en Librarian via events.
    Claimt het lexicon-domein NIET — de Librarian cureert; de TijdgeestWachter voedt."""

    _SHIFT_THRESHOLD = 2   # minimaal N termen in dezelfde richting voor een broadcast

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_pulse: float = 0.0
        self._busy = False
        # Productie: wekelijks. Demo/test: tijdgeest_interval_seconds=0 → altijd.
        self._pulse_interval = float(
            self.context.settings.get("tijdgeest_interval_seconds", str(7 * 24 * 3600)))
        self.react("tijdgeest_pulse", self._run_pulse)   # handmatig triggerable

    def _setup_events(self) -> None:
        self.react("dag_begint", self._maybe_pulse, drop_if_busy=True)

    def _maybe_pulse(self, event: Event) -> None:
        """Reageert op de dagelijkse hartslag maar runt alleen als het tijd is."""
        now = time.time()
        if self._pulse_interval > 0 and now - self._last_pulse < self._pulse_interval:
            return
        if self._busy:
            return
        self._last_pulse = now
        self._run_pulse(event)

    def _reflect(self) -> None:
        """Reflecteert op de structurele limieten van de ngram_culture-databron.

        Produceer UITSLUITEND means-gap-items — nooit governance-voorstellen of API-aanroepen.
        Uitbreiding van capaciteit is mens-gated; de inbox is de persistente trace.
        """
        # Data stopt in 2019 — structureel bekende limiet, eenmalig naar inbox
        self._report_means_gap(
            "ngram_2019_cutoff",
            "accountability: aanvullende recente bron voor tijdgeest-observaties periodiek "
            "evalueren en aan de mens rapporteren — "
            "de ngram_culture-databron stopt in 2019 en misloopt daarmee 7 jaar culturele "
            "verschuiving (2019-2026); geen enkele puls kan recente verschuivingen signaleren",
        )
        # NL corpus verouderd — eenmalig naar inbox
        self._report_means_gap(
            "nl_corpus_coverage",
            "accountability: NL corpus dekking periodiek valideren en ontbrekende "
            "kernbegrippen documenteren — "
            "meerdere Nederlandse termen (bijv. 'consument') worden niet gevonden in het "
            "NL corpus 10 (2012); het corpus is verouderd en dekt moderne missie-terminologie "
            "onvoldoende af",
        )

    def _run_pulse(self, event) -> None:
        if self._busy:
            return
        self._busy = True
        payload = event.data if event and hasattr(event, "data") else {}
        try:
            self.log.info("🌊 tijdgeest-puls gestart")
            result = self.use_skill("ngram_culture", payload)

            if "error" in result:
                self.log.warning("⚠️ ngram-puls mislukt: %s", result["error"])
                self.bus.publish(Event("tijdgeest_pulse_completed",
                    {"by": self.id, "ok": False, "error": result["error"]}, self.id))
                return

            # Verwerk locale-bewuste rows (nieuw) of legacy terms-dict (compat)
            rows  = result.get("rows", [])
            terms = result.get("terms", {})

            if rows:
                stijgend = list(dict.fromkeys(
                    r["term"] for r in rows
                    if not r.get("no_data")
                    and r.get("signal", {}).get("direction") == "stijgend"
                ))
                dalend = list(dict.fromkeys(
                    r["term"] for r in rows
                    if not r.get("no_data")
                    and r.get("signal", {}).get("direction") == "dalend"
                ))
            else:
                stijgend = [t for t, d in terms.items()
                            if d.get("signal", {}).get("direction") == "stijgend"]
                dalend   = [t for t, d in terms.items()
                            if d.get("signal", {}).get("direction") == "dalend"]

            self.log.info("📈 stijgend: %s | 📉 dalend: %s", stijgend, dalend)

            # Stijgende termen aanbieden aan de Librarian (niet zelf curating)
            lib = getattr(self.context, "library", None)
            row_by_term = {r["term"]: r for r in rows} if rows else {}
            for term in stijgend:
                row  = row_by_term.get(term, {})
                freq = row.get("freq_last") or (terms.get(term) or {}).get("freq_last")
                _publish_keyword_proposed(
                    self.bus, self.id, term,
                    demand={
                        "signal":    "positive",
                        "source":    "ngram_culture",
                        "direction": "stijgend",
                        "locale":    row.get("locale"),
                        "concept":   row.get("concept"),
                        "freq_last": freq,
                    },
                    library=lib,
                )

            # Broadcast bij opvallende culturele verschuiving
            if len(stijgend) >= self._SHIFT_THRESHOLD or len(dalend) >= self._SHIFT_THRESHOLD:
                self.bus.publish(Event("tijdgeest_signaal", {
                    "by":       self.id,
                    "stijgend": stijgend,
                    "dalend":   dalend,
                    "boodschap": (
                        f"{len(stijgend)} termen cultureel stijgend "
                        f"({', '.join(stijgend[:3])}), "
                        f"{len(dalend)} dalend ({', '.join(dalend[:3])})"
                    ),
                }, self.id))
                self.log.info("📢 tijdgeest-signaal uitgezonden")

            self.bus.publish(Event("tijdgeest_pulse_completed", {
                "by":        self.id,
                "ok":        True,
                "stijgend":  stijgend,
                "dalend":    dalend,
                "term_count": len(rows) if rows else len(terms),
                "rows":      rows,    # locale-bewust (nieuw)
                "terms":     terms,   # backward compat
            }, self.id))
        finally:
            self._busy = False
        self._maybe_reflect(None)


class KennisScout(Inhabitant):
    """Grondt kandidaat-termen in academische literatuur (v1: OpenAlex + Semantic Scholar).

    Termen komen uit het lexicon — via keyword_proposed-events van TijdgeestWachter,
    WebsiteWatcherWorker of TrendsWorker, die hun woorden op hun beurt uit het Lexicon halen.
    De KennisScout haalt evidentie op, destilleert een duiding en publiceert keyword_evidence.

    Signaleert alleen — beslist en cureert nooit zelf.
    OpenLibrary voltekst-grounding is gepland voor v2.

    Harde grens (_reflect):
      Produceer UITSLUITEND spanningen en voorstellen — nooit nieuwe code of API-calls
      buiten de eigen skills-lijst. Uitbreiding van capaciteit is mens-gated activatie.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.react("keyword_proposed", self._on_keyword_proposed)
        self._busy_terms: set[str] = set()

    def _on_keyword_proposed(self, event: Event) -> None:
        word   = event.data.get("word", "").strip()
        demand = event.data.get("demand", {})
        locale = demand.get("locale", "")   # locale volgt de term uit het Lexicon
        if not word or word in self._busy_terms:
            return
        self._busy_terms.add(word)
        try:
            self.log.info("🔬 gronden: '%s' (locale=%s)", word, locale or "?")
            evidence: list[dict] = []

            # OpenAlex — academische werken, gesorteerd op citaties
            works = self.use_skill("openalex_evidence",
                                   {"term": word, "locale": locale, "limit": 3})
            if "error" in works:
                self.log.warning("⚠️ OpenAlex: %s", works["error"])
            elif works.get("no_data"):
                self.log.info("ℹ️ OpenAlex: geen werken voor '%s'", word)
            else:
                evidence.extend(works.get("hits", []))

            # Semantic Scholar — papers met tldr-samenvatting
            papers = self.use_skill("semscholar_tldr",
                                    {"term": word, "locale": locale, "limit": 3})
            if "error" in papers:
                self.log.warning("⚠️ Semantic Scholar: %s", papers["error"])
            elif papers.get("no_data"):
                self.log.info("ℹ️ Semantic Scholar: geen papers voor '%s'", word)
            else:
                evidence.extend(papers.get("hits", []))

            # OpenLibrary — boek-evidentie (duurzaamheidscanon, voltekst)
            books = self.use_skill("openlibrary_search_inside",
                                   {"term": word, "limit": 3})
            if "error" in books:
                self.log.warning("⚠️ OpenLibrary: %s", books["error"])
            elif not books.get("hits"):
                self.log.info("ℹ️ OpenLibrary: geen boeken voor '%s'", word)
            else:
                evidence.extend(books.get("hits", []))

            assessment = self._distill(word, locale, evidence, demand)

            self.bus.publish(Event("keyword_evidence", {
                "word":            word,
                "locale":          locale,
                "evidence":        evidence,
                "assessment":      assessment,
                "from":            self.id,
                "original_demand": demand,
            }, self.id))
            self.log.info("📚 evidentie gepubliceerd voor '%s': %d bron(nen)", word, len(evidence))
        finally:
            self._busy_terms.discard(word)

    def _distill(self, word: str, locale: str,
                 evidence: list[dict], demand: dict) -> str:
        """Destilleer gevonden evidentie tot een beknopte relevantie-duiding.

        Citeer UITSLUITEND bronnen die in `evidence` staan. Fabriceer geen titels,
        auteurs, abstracten of DOI's die niet daadwerkelijk zijn opgehaald.
        """
        if not evidence:
            return (f"Geen academische bronnen gevonden voor '{word}' "
                    f"(locale={locale or 'onbekend'}, v1: OpenAlex + Semantic Scholar).")

        bron_regels: list[str] = []
        for e in evidence[:5]:
            jaar  = e.get("year") or "?"
            tldr  = e.get("tldr", "")
            bron_regels.append(
                f"- {e.get('title','?')} ({jaar}) [{e.get('source','?')}]"
                + (f"\n  tldr: {tldr}" if tldr else ""))

        from nooch_village.llm import reason as llm_reason
        prompt = (
            f"Duiding gevraagd voor term '{word}' (locale: {locale or '?'}) "
            f"voor Nooch.earth (duurzame schoenen, geen plastic, geen leer).\n"
            f"Gevonden bronnen ({len(evidence)}):\n" + "\n".join(bron_regels) + "\n\n"
            f"Geef in maximaal 2 zinnen: (1) wat de inhoudelijke/wetenschappelijke relevantie "
            f"is van '{word}', (2) of de bronnen de missie-claim ondersteunen of tegenspreken. "
            f"Baseer je ALLEEN op de bovenstaande bronnen. "
            f"Verzin geen andere titels of auteurs. "
            f"Als je het niet kunt beoordelen, zeg dat expliciet."
        )
        llm_out = llm_reason(prompt)
        if llm_out:
            return llm_out.strip()

        # Fallback zonder LLM — alleen namen van écht opgehaalde bronnen
        titels = "; ".join(e.get("title", "?")[:60] for e in evidence[:3])
        return f"{len(evidence)} bron(nen) gevonden voor '{word}': {titels}."

    def _reflect(self) -> None:
        """Periodieke reflectie op de dekking van de twee v1-databronnen.

        Produceer UITSLUITEND means-gap-items — nooit governance-voorstellen of API-calls.
        Elke uitbreiding van capaciteit vereist menselijke goedkeuring en handmatige
        registratie in SkillRegistry + CLASS_MAP (v2: OpenLibrary voltekst).
        """
        # v1-limiet: OpenLibrary voltekst-grounding ontbreekt → inbox (eenmalig)
        self._report_means_gap(
            "openlibrary_v2",
            "accountability: OpenLibrary voltekst-grounding evalueren en toevoegen als v2 — "
            "v1 grondt uitsluitend in academische literatuur (OpenAlex, Semantic Scholar); "
            "boek-evidentie (bijv. duurzaamheidscanon) ontbreekt daardoor volledig",
        )
        # semscholar_no_key: geen toestandssensing — sens pas als de rate-limit geraakt wordt.


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
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ── missie-werk ───────────────────────────────────────────────────────
        self.react("pulse_completed", self._on_pulse_completed)
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
            f"Je bent Noochie, de missiestem van Nooch.earth. Scherp en nuchter.\n"
            f"Missie: {_NOOCHIE_MISSION}\n\n"
            f"Field Note van vandaag:\n{field_note}\n\n"
            "Toets de aanbevolen actie aan de missie. Klopt hij?\n\n"
            "Antwoord met precies dit formaat:\n"
            "VERDICT: ok\n"
            "REASON: <één zin>\n\n"
            "of:\n"
            "VERDICT: niet_ok\n"
            "REASON: <één zin over wat botst of mist>"
        )
        result = reason(prompt) or "(geen LLM beschikbaar)"
        verdict, reason_text = parse_verdict_reason(result, frozenset({"ok", "niet_ok"}))

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

    def _reflect(self) -> None:
        """Genereert periodiek één creatief voorstel als spanning richting de mens.

        Deduplicatie: de inhoud-hash van het voorstel wordt bijgehouden in
        reflect_noochie.json (via _sense_gap). Pas bij een nieuw uniek voorstel
        (andere hash) én min_count=2 wordt er een spanning gesensed — ook in
        demo-modus (reflect_interval_seconds=0). force=True is verwijderd zodat
        Noochie de inbox niet overspoelt.
        """
        from nooch_village.llm import reason
        prompt = (
            f"Je bent Noochie, ideeënmotor van Nooch.earth.\n"
            f"Missie: {_NOOCHIE_MISSION}\n\n"
            "Formuleer één concrete spanning die het dorp zou moeten oppakken om de missie "
            "beter te dienen. Uitvoerbaar met content, SEO of governance — geen advertising. "
            "Max 3 zinnen. Formaat: 'Het dorp mist [wat]. [Voorstel] zou helpen omdat [reden]. "
            "Dit advies kantelt als [voorwaarde waaronder een andere route beter is].'"
        )
        result = reason(prompt)
        if not result:
            return
        h = hashlib.sha256(result.encode()).hexdigest()[:16]
        gap_key = f"creatief_voorstel_{h}"
        self._sense_gap(gap_key, result, kind="governance", min_count=2)

    # ── bulletin-mandaat (afsplitsbaar blok) ──────────────────────────────────

    def _collect_event(self, event: Event) -> None:
        self._events_today.append({
            "name": event.name,
            "by":   event.data.get("by", event.sender),
            "note": event.data.get("boodschap", "") or event.data.get("note_path", ""),
        })

    def _on_dag_eindigt(self, event: Event) -> None:
        """Schrijf het dagbulletin op basis van de events en de Field Note van vandaag."""
        events = list(self._events_today)
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

        self.bus.publish(Event("bulletin_geschreven",
                               {"path": result["path"], "by": self.id,
                                "event_count": result.get("event_count", 0)}, self.id))
        self.log.info("📋 bulletin gepubliceerd: %s", result["path"])
