"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import time
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

            if note.get("tension"):
                self.sense_tension(note.get("reason", "Verval gedetecteerd in de groei-puls"),
                                   kind="operational")
            self.bus.publish(Event("pulse_completed",
                {"by": self.id, "note_path": note.get("path"), "tension": note.get("tension")}, self.id))
            self.log.info("📝 Field Note klaar -> %s", note.get("path"))
        finally:
            self._busy = False

    def _propose_related(self, trends: dict) -> None:
        lib = self.context.library
        proposed = 0
        for parent_kw, kw_data in (trends.get("keywords") or {}).items():
            for related in kw_data.get("top_related") or []:
                term = related["query"] if isinstance(related, dict) else related
                value = related.get("value", 0) if isinstance(related, dict) else 0
                if lib.status(term) is not None:  # elke bekende status, ook 'escalated'
                    continue
                self.bus.publish(Event("keyword_proposed", {
                    "word": term,
                    "demand": {"signal": "positive", "interest": value,
                               "source": "google_trends_related", "parent_keyword": parent_kw},
                    "from": self.id,
                }, self.id))
                proposed += 1
        if proposed:
            self.log.info("🔍 %d nieuwe kandidaat-woorden doorgestuurd naar de Librarian", proposed)


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
