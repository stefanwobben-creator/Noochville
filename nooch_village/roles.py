"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import os, json, time
from datetime import date
from nooch_village.inhabitant import Inhabitant
from nooch_village.event_bus import Event
from nooch_village.governance import Gate, proposal_from_dict, proposal_to_dict


class TimeKeeper(Inhabitant):
    """De dorpsomroeper. Roept elke nieuwe dag 'dag_begint' om op het marktplein.
    Voor de demo kun je via settings['heartbeat_seconds'] een snelle hartslag zetten."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_day = None
        self._last_beat = 0.0
        # demo-modus: elke N seconden i.p.v. één keer per dag
        self._interval = float(self.context.settings.get("heartbeat_seconds", 0) or 0)

    def tick(self) -> None:
        now = time.time()
        if self._interval > 0:
            if now - self._last_beat >= self._interval:
                self._last_beat = now
                self._ring("demo-puls")
            return
        today = date.today().isoformat()
        if today != self._last_day:
            self._last_day = today
            self._ring(today)

    def _ring(self, label: str) -> None:
        self.log.info("🔔 dag_begint (%s)", label)
        self.bus.publish(Event("dag_begint", {"label": label}, self.id))


class GrowthAnalyst(Inhabitant):
    """Hoort de ochtendbel en voert zelf zijn groei-puls uit: echte data ophalen,
    duiden tegen de missie, en een Field Note schrijven. Senst een spanning bij verval."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.react("dag_begint", self._morning_pulse)
        self._busy = False

    def _morning_pulse(self, event: Event) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            self.log.info("☀️ groei-puls gestart")
            plausible = self.use_skill("plausible_stats", {"period": "7d"})
            trends = self.use_skill("google_trends", {})
            note = self.use_skill("field_note", {"plausible": plausible, "trends": trends})

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
            with open(state_path, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

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
            self.bus.publish(Event("keyword_proposed", {
                "word": action["label"],
                "demand": {"signal": "positive", "interest": action.get("_value", 0),
                           "source": "google_trends_related",
                           "parent_keyword": action.get("_parent", "")},
                "from": self.id,
            }, self.id))
            proposed += 1
        if proposed:
            self.log.info("🔍 %d kandidaat-woorden doorgestuurd (gerangschikt op doelbijdrage)", proposed)


class PerformanceScout(Inhabitant):
    """Luistert op dag_begint, haalt GSC-queries op en stuurt high_potential-woorden
    die nog niet in de bibliotheek staan door als keyword_proposed naar de Librarian."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.react("dag_begint", self._on_dag_begint)
        self._busy = False

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
            self.bus.publish(Event("gsc_pulse_completed",
                {"by": self.id, "ok": True,
                 "total": result.get("total", 0),
                 "bucket_counts": result.get("bucket_counts", {})}, self.id))
        finally:
            self._busy = False

    def _propose_from_gsc(self, result: dict) -> None:
        lib = self.context.library
        proposed = 0
        for row in result.get("rows", []):
            if row["bucket"] != "high_potential":
                continue
            term = row["query"]
            if lib.status(term) is not None:  # elke bekende status, ook 'escalated'
                continue
            self.bus.publish(Event("keyword_proposed", {
                "word": term,
                "demand": {
                    "signal": "positive",
                    "interest": row["impressions"],
                    "source": "gsc",
                    "position": row["position"],
                    "bucket": row["bucket"],
                    "impressions": row["impressions"],
                    "clicks": row["clicks"],
                },
                "from": self.id,
            }, self.id))
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
        self.react("keyword_proposed", self._on_proposal)
        self.react("human_keyword_verdict", self._on_human_verdict)

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


class Facilitator(Inhabitant):
    """Bewaakt de geldigheid van governance-voorstellen zonder inhoudelijk te oordelen.
    Draait de poort G0-G4 en beslist adopt-by-default of escaleren naar de mens.
    Integreert bezwaren NOOIT automatisch: alleen de mens kan dat doen."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gate = Gate()
        self.react("proposal_raised", self._on_proposal_raised)

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
    Observeert en voedt GrowthAnalyst en Librarian via events.
    Claimt het lexicon-domein NIET — de Librarian cureert; de TijdgeestWachter voedt."""

    _SHIFT_THRESHOLD = 2   # minimaal N termen in dezelfde richting voor een broadcast

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_pulse: float = 0.0
        self._busy = False
        # Productie: wekelijks. Demo/test: tijdgeest_interval_seconds=0 → altijd.
        self._pulse_interval = float(
            self.context.settings.get("tijdgeest_interval_seconds", str(7 * 24 * 3600)))
        self.react("dag_begint",      self._maybe_pulse)
        self.react("tijdgeest_pulse", self._run_pulse)   # handmatig triggerable

    def _maybe_pulse(self, event: Event) -> None:
        """Reageert op de dagelijkse hartslag maar runt alleen als het tijd is."""
        now = time.time()
        if self._pulse_interval > 0 and now - self._last_pulse < self._pulse_interval:
            return
        if self._busy:
            return
        self._last_pulse = now
        self._run_pulse(event)

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

            terms = result.get("terms", {})
            stijgend = [t for t, d in terms.items()
                        if d.get("signal", {}).get("direction") == "stijgend"]
            dalend   = [t for t, d in terms.items()
                        if d.get("signal", {}).get("direction") == "dalend"]

            self.log.info("📈 stijgend: %s | 📉 dalend: %s", stijgend, dalend)

            # Stijgende termen aanbieden aan de Librarian (niet zelf curating)
            lib = getattr(self.context, "library", None)
            for term in stijgend:
                if lib and lib.status(term) is not None:
                    continue  # Librarian heeft al een oordeel
                self.bus.publish(Event("keyword_proposed", {
                    "word": term,
                    "demand": {
                        "signal":    "positive",
                        "source":    "ngram_culture",
                        "direction": "stijgend",
                        "freq_last": terms[term].get("freq_last"),
                    },
                    "from": self.id,
                }, self.id))

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
                "term_count": len(terms),
                "terms":     terms,   # volledige details voor observability
            }, self.id))
        finally:
            self._busy = False
