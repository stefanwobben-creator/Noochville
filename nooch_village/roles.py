"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import time
from datetime import date
from nooch_village.inhabitant import Inhabitant
from nooch_village.event_bus import Event


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
        self.bus.subscribe("dag_begint", self._morning_pulse)
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
        self.bus.subscribe("dag_begint", self._on_dag_begint)
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
        self.bus.subscribe("keyword_proposed", self._on_proposal)
        self.bus.subscribe("human_keyword_verdict", self._on_human_verdict)

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
