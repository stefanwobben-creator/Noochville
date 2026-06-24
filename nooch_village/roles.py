"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import hashlib, os, json, time
from datetime import date
from nooch_village.util import atomic_write_json, run_bounded, is_due
from nooch_village.mission import ANCHOR_PURPOSE as _NOOCHIE_MISSION
from nooch_village.inhabitant import Inhabitant
from nooch_village.event_bus import Event
from nooch_village.governance import Gate, proposal_from_dict, proposal_to_dict
from nooch_village.insight import Insight
from nooch_village.insight_ingest import insight_from_grounding


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
            try:
                plausible = self.use_skill("plausible_stats", {"period": "7d"})
            except Exception as exc:                       # Plausible mag de note niet blokkeren
                self.log.warning("plausible_stats faalde: %s", exc)
                plausible = {"error": str(exc)}

            # Trends: betrouwbaar via SerpApi, maar zuinig (wekelijks) en nooit op het
            # kritieke pad. Buiten de cadans of bij een fout gaat de note gewoon door.
            trends = self._maybe_trends()
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

    def _maybe_trends(self) -> dict:
        """Trends best-effort via SerpApi, zuinig (wekelijkse cadans) en bounded.

        Buiten de cadans: niets ophalen, geen credits, een nette {error}-dict die
        field_note opvangt. Binnen de cadans: SerpApi met harde tijdslimiet; de
        last-run-stempel wordt alleen gezet bij succes, zodat een fout volgende puls
        opnieuw mag proberen.
        """
        interval = float(self.context.settings.get("serpapi_interval_seconds", "604800"))
        state_path = os.path.join(self.context.data_dir, "serpapi_trends_last.json")
        try:
            last = float(json.load(open(state_path)).get("ts", 0))
        except Exception:
            last = 0.0

        now = time.time()
        if not is_due(last, now, interval):
            self.log.info("⏭️ Trends overgeslagen (wekelijkse cadans nog niet verstreken)")
            return {"error": "trends deze puls overgeslagen (cadans)", "keywords": {}, "rows": []}

        budget = float(self.context.settings.get("trends_time_budget_seconds", "30"))
        trends = _bounded_trends(
            lambda: self.use_skill("serpapi_trends", {"geos": [""], "date": "today 3-m"}),
            budget, self.log,
        )
        if "error" not in trends:
            try:
                with open(state_path, "w") as f:
                    json.dump({"ts": now}, f)
            except Exception:
                pass
        return trends

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
            for related in kw_data.get("rising_related") or []:
                term = related["query"] if isinstance(related, dict) else related
                value = related.get("value", 0) if isinstance(related, dict) else 0
                if lib.status(term) is not None:
                    continue
                candidates.append({
                    "label": term,
                    "description": f"opkomende zoekterm gerelateerd aan missie-keyword {related.get('_parent', parent_kw) if isinstance(related, dict) else parent_kw}",
                    "_value": value,
                    "_parent": parent_kw,
                    "_rising": True,
                    "_breakout": related.get("breakout", False) if isinstance(related, dict) else False,
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
                        "source": "google_trends_rising" if action.get("_rising") else "google_trends_related",
                        "breakout": action.get("_breakout", False),
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
                 "bucket_counts": result.get("bucket_counts", {}),
                 "boodschap": f"GSC-ronde: {result.get('total', 0)} queries opgehaald"}, self.id))
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
            # Geen volume-meting hier: de KeywordsEverywhere-verrijking is gecentraliseerd
            # bij de Librarian, zodat élke bron (GSC, SerpAPI-Trends, ngram) gelijk profiteert.
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


class ConcurrentScout(Inhabitant):
    """Observeert de duurzame-sneakermarkt: monitort strategisch nieuws van directe
    concurrenten (funding, lanceringen, B-Corp, materiaalinnovatie) en voedt het dorp.

    Schrijft elke puls een field report en publiceert per NIEUW bericht een competitor_signal
    (dat Noochie in het bulletin verwerkt). Bij missie-relevante zetten senst hij één
    gebundelde spanning. Dedup via data/competitor_seen.json zodat 'elke puls' geen ruis geeft.
    Cureert of beslist nooit; hij observeert en signaleert."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._busy = False
        self.react("dag_begint", self._on_pulse, drop_if_busy=True)

    def _on_pulse(self, event: Event) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            store = self._brands_store()
            monitored = self._monitored_brands(store)
            self._run_news(monitored)
            self._run_discovery(monitored, store)
            self._run_linkbuilding(monitored)
            self._run_market_interest(monitored, store)
        finally:
            self._busy = False

    def _brands_store(self):
        store = getattr(self.context, "competitors", None)
        if store is not None:
            return store                                 # gedeelde store (village-breed)
        from nooch_village.competitor_brands import CompetitorBrands
        return CompetitorBrands(os.path.join(self.context.data_dir, "competitor_brands.json"))

    def _monitored_brands(self, store) -> list[str]:
        """Vaste merken (settings) + door de mens bevestigde ontdekkingen."""
        raw = (self.context.settings.get("competitor_brands", "") or "")
        settings_brands = [b.strip() for b in raw.split(",") if b.strip()]
        return list(dict.fromkeys(settings_brands + store.confirmed()))

    def _run_news(self, monitored: list[str]) -> None:
        self.log.info("🔭 concurrent-scan gestart (%d merken)", len(monitored))
        res = self.use_skill("competitor_news", {"brands": monitored} if monitored else {})
        if not res.get("ok"):
            self.log.warning("⚠️ concurrent-scan mislukt: %s", res.get("error"))
            self.bus.publish(Event("competitor_pulse_completed",
                {"by": self.id, "ok": False, "error": res.get("error")}, self.id))
            return
        items = res.get("items", [])
        seen = self._load_seen()
        new_items = [it for it in items if it.get("link") and it["link"] not in seen]
        for it in new_items:                              # signalen → bulletin (Noochie)
            self.bus.publish(Event("competitor_signal",
                {"by": self.id, "brand": it["brand"], "title": it["title"],
                 "link": it["link"], "date": it["date"]}, self.id))
        mission_hits = [it for it in new_items if self._is_mission_relevant(it["title"])]
        if mission_hits:                                  # één gebundelde spanning, geen flood
            merken = ", ".join(sorted({it["brand"] for it in mission_hits}))
            self.sense_tension(
                f"{len(mission_hits)} nieuwe missie-relevante concurrent-zet(ten) bij "
                f"{merken}; zie {os.path.basename(res.get('path', '') or '')}",
                kind="operational")
        self._save_seen(seen | {it["link"] for it in new_items})
        self.log.info("🔭 concurrent-scan: %d nieuw / %d totaal, %d missie-relevant → %s",
                      len(new_items), res.get("total", 0), len(mission_hits), res.get("path"))
        self.bus.publish(Event("competitor_pulse_completed",
            {"by": self.id, "ok": True, "new": len(new_items),
             "total": res.get("total", 0), "mission_relevant": len(mission_hits),
             "path": res.get("path")}, self.id))

    def _run_discovery(self, monitored: list[str], store) -> None:
        """Spot kandidaat-concurrenten en zet ze (deduped) in de store voor jouw oordeel."""
        if "competitor_discover" not in self.dna.skills:
            return
        res = self.use_skill("competitor_discover", {"brands": monitored})
        if not res.get("ok"):
            self.log.info("🔮 ontdekking overgeslagen: %s", res.get("error"))
            return
        added = 0
        for c in res.get("candidates", []):
            if store.add_candidate(c.get("brand", ""), c.get("article", ""), c.get("link", "")):
                added += 1
                self.bus.publish(Event("competitor_candidate",
                    {"by": self.id, "brand": c.get("brand", ""),
                     "article": c.get("article", ""), "link": c.get("link", "")}, self.id))
        if added:
            self.log.info("🔮 %d nieuwe kandidaat-concurrent(en) gespot — wacht op jouw oordeel", added)

    def _run_linkbuilding(self, monitored: list[str]) -> None:
        """Spot gidsen/lijstjes waar Nooch in vermeld wil worden; zet ze (deduped) in de
        doelwit-store met prioriteit (concurrenten-zonder-Nooch = hoog)."""
        if "linkbuilding_targets" not in self.dna.skills:
            return
        res = self.use_skill("linkbuilding_targets", {"brands": monitored})
        if not res.get("ok"):
            self.log.info("🔗 linkbuilding overgeslagen: %s", res.get("error"))
            return
        from nooch_village.link_targets import LinkTargets
        store = LinkTargets(os.path.join(self.context.data_dir, "linkbuilding_targets.json"))
        added, hoog = 0, 0
        for t in res.get("targets", []):
            if store.add_candidate(t.get("link", ""), t.get("title", ""),
                                   t.get("source", ""), t.get("priority", "onbekend")):
                added += 1
                hoog += 1 if t.get("priority") == "hoog" else 0
                self.bus.publish(Event("linkbuilding_target", {"by": self.id, **t}, self.id))
        if added:
            self.log.info("🔗 %d nieuw linkbuilding-doelwit(ten) gespot (%d hoog) — wacht op jouw oordeel",
                          added, hoog)

    def _run_market_interest(self, monitored: list[str], store) -> None:
        """Consument van de gedeelde concurrent-store: meet het zoekvolume van de bevestigde
        concurrenten met KeywordsEverywhere (marktinteresse). Faalt closed."""
        if "keywords_everywhere" not in self.dna.skills:
            return
        targets = (store.confirmed() or monitored)[:25]   # bevestigde concurrenten, anders vaste set
        if not targets:
            return
        country = (self.context.settings.get("ke_country", "nl") or "nl").strip()
        res = self.use_skill("keywords_everywhere", {"kw": targets, "country": country})
        if not isinstance(res, dict) or "error" in res or "keywords" not in res:
            self.log.info("📊 marktinteresse overgeslagen: %s",
                          res.get("error") if isinstance(res, dict) else res)
            return
        vols = {k.get("keyword", ""): int(k.get("vol", 0) or 0) for k in res["keywords"]}
        ranked = sorted(vols.items(), key=lambda kv: -kv[1])
        self.log.info("📊 marktinteresse concurrenten: %s",
                      ", ".join(f"{b} {v}/mnd" for b, v in ranked[:8]))
        self.bus.publish(Event("competitor_interest", {"by": self.id, "volumes": vols}, self.id))

    def _is_mission_relevant(self, title: str) -> bool:
        from nooch_village.skills_impl.competitor_news import _MISSION_THEMES
        t = (title or "").lower()
        return any(theme in t for theme in _MISSION_THEMES)

    def _seen_path(self) -> str:
        return os.path.join(self.context.data_dir, "competitor_seen.json")

    def _load_seen(self) -> set:
        try:
            return set(json.load(open(self._seen_path())).get("links", []))
        except Exception:
            return set()

    def _save_seen(self, links: set) -> None:
        try:
            with open(self._seen_path(), "w") as f:
                json.dump({"links": sorted(links)[-2000:]}, f)   # cap tegen onbeperkte groei
        except Exception as exc:
            self.log.warning("kon competitor_seen niet opslaan: %s", exc)


class Librarian(Inhabitant):
    """Hoeder van de woordenschat. Bezit het DOMEIN (de bibliotheek): anderen lezen vrij,
    alleen de Librarian cureert. Beoordeelt kandidaat-woorden tegen de missie en escaleert
    de twijfelgevallen naar een mens."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.react("keyword_proposed",      self._on_proposal)
        self.react("human_keyword_verdict", self._on_human_verdict)
        self.react("keyword_evidence",      self._on_evidence)
        self.react("child_evidence",        self._on_child_evidence)
        self.react("insight_proposed",      self._on_insight_proposed)
        self.react("dag_eindigt",           self._on_dag_eindigt)

    def _on_insight_proposed(self, event: Event) -> None:
        """Enige schrijfweg naar de kennislaag: cureer fuzzy input tot atomaire, Engelse
        kaartjes en schrijf ze weg. De Librarian is domein-eigenaar (regel 7); kwaliteit
        (Engels, atomair, compleet, gelinkt) wordt hier op één plek afgedwongen."""
        fuzzy = (event.data.get("fuzzy") or event.data.get("text") or "").strip()
        if not fuzzy:
            return
        source = event.data.get("source") or event.data.get("from", "curator")
        res = self.use_skill("curate", {
            "fuzzy": fuzzy, "source": source,
            "source_date": event.data.get("source_date"),
        })
        cards = res.get("cards", [])
        if not cards:
            self.log.info("🗂️ curate: geen geldige kaartjes uit input van %s", source)
            return
        from nooch_village.ingest import ingest_insights
        r = ingest_insights(self.context.notes, cards)
        self.log.info("🗂️ gecureerd: %d kaartje(s) toegevoegd, %d link(s) (van %s)",
                      len(r["added"]), r["linked"], source)
        self.bus.publish(Event("cards_curated",
            {"by": self.id, "added": r["added"], "from": source}, self.id))

    def _enrich_volume(self, word: str, demand: dict) -> dict:
        """Centrale KeywordsEverywhere-verrijking vóór de beoordeling: hang échte
        zoekvraag (volume) aan de demand, zodat élke bron (GSC, SerpAPI-Trends, ngram)
        gelijk op volume kan auto-approven. Faalt closed: bron leverde al volume, of geen
        key/skill → demand onveranderd (kandidaat beoordeelt zoals voorheen)."""
        if demand.get("volume") or demand.get("vol"):
            return demand                               # bron gaf al volume
        if not word or "keywords_everywhere" not in self.dna.skills:
            return demand
        res = self.use_skill("keywords_everywhere",
                             {"kw": [word], "country": self._ke_country()})
        if not isinstance(res, dict) or "error" in res or not res.get("keywords"):
            reason = res.get("error") if isinstance(res, dict) else res
            self.log.info("📐 KE niet beschikbaar (%s) — '%s' zonder volume beoordeeld", reason, word)
            return demand
        vol = int(res["keywords"][0].get("vol", 0) or 0)
        self.log.info("📐 KE: '%s' → volume %d/mnd", word, vol)
        return {**demand, "volume": vol, "ke_country": self._ke_country()}

    def _ke_country(self) -> str:
        return (self.context.settings.get("ke_country", "nl") or "nl").strip()

    def _on_proposal(self, event: Event) -> None:
        word = event.data.get("word")
        demand = dict(event.data.get("demand", {}))     # kopie: we verrijken 'm centraal
        proposer = event.data.get("from", "?")
        self.log.info("📥 kandidaat van %s: '%s'", proposer, word)

        demand = self._enrich_volume(word, demand)
        v = self.use_skill("keyword_review", {"word": word, "demand": demand})
        decision = v.get("decision")
        reason = v.get("reason", "")
        lib = self.context.library

        # Vorm 2: raadpleeg bestaande kennis over verwante woorden (zichtbaar, stuurt het oordeel niet)
        notes = getattr(self.context, "notes", None)
        if notes is not None:
            verwant = notes.relevant_for(word, limit=3)
            if verwant:
                woorden = ", ".join(f"'{n.word}'" for n in verwant)
                self.log.info("📚 bij beoordeling van '%s' vond ik %d verwante kaartje(s): %s",
                              word, len(verwant), woorden)

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
        """Ontvangt wetenschappelijk bewijs van Harry Hemp of een andere grounding-inwoner.

        Als het woord al 'escalated' is (geen beslissing mogelijk zonder bewijs),
        herbeoordeelt de Librarian het nu met de opgehaalde evidentie.
        """
        word       = event.data.get("word", "")
        evidence   = event.data.get("evidence", [])
        assessment = event.data.get("assessment", "")
        source     = event.data.get("from", "harry_hemp")
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
                    rationale=f"{reason} [{source}: {assessment[:80]}]",
                    evidence=enriched, by=self.id)
                self.log.info("✅ herzien → goedgekeurd na evidentie van '%s': '%s'", source, word)
                self.bus.publish(Event("keyword_decided",
                    {"word": word, "status": "approved", "reason": reason,
                     "via": source}, self.id))
            elif decision == "reject":
                self.context.library.curate(
                    word, "forbidden", rationale=reason, by=self.id)
                self.log.info("⛔ herzien → afgewezen na evidentie van '%s': '%s'", source, word)
                self.bus.publish(Event("keyword_decided",
                    {"word": word, "status": "forbidden", "reason": reason,
                     "via": source}, self.id))
            else:
                self.log.info("🔖 evidentie genoteerd; '%s' blijft escalated", word)
        else:
            status = (existing or {}).get("status", "onbekend")
            self.log.info("🔖 evidentie genoteerd voor '%s' (status: %s)", word, status)

        concept_id = self.context.lexicon.concept_for_word(word)
        kaartje = insight_from_grounding(word, assessment, evidence, concept_id)
        if kaartje is not None:
            try:
                self.context.notes.add(kaartje)
            except ValueError:
                # kaart bestaat al: verrijk in plaats van weggooien (vorm 1)
                verrijkt = self.context.notes.enrich(kaartje.id, nieuwe_reference=kaartje.reference)
                if verrijkt is not None:
                    self.log.info("🌱 kaart voor '%s' verrijkt: %dde grounding",
                                  word, verrijkt.grounding_count)
            else:
                self.log.info("🗂️  kaartje vastgelegd voor '%s' (concept=%s)",
                              word, concept_id or "geen")

    def _on_child_evidence(self, event: Event) -> None:
        """Ontvang waaróm-onderzoek van de scientist en schrijf het kind-kaartje plus
        de geboren-uit-link. De Librarian cureert de kennis; de scientist onderzoekt.
        Fail-closed: zonder parent_id of vraag gebeurt er niets."""
        parent_id  = event.data.get("parent_id")
        vraag      = event.data.get("vraag", "")
        evidence   = event.data.get("evidence", [])
        assessment = event.data.get("assessment", "")
        if not parent_id or not vraag:
            return
        self._write_child_card(parent_id, vraag, evidence, assessment)

    def _write_child_card(self, parent_id: str, vraag: str,
                          evidence: list[dict], assessment: str) -> Insight | None:
        """Schrijf een kind-kaartje uit waaróm-onderzoek en koppel het aan de
        trend-kaart (geboren-uit). Atomair (Ahrens): een nieuw, eigen kaartje voor
        een nieuw feit, niet het trend-kaartje verdikken. Bestaat het kind-kaartje al
        (dezelfde vraag), dan verrijken in plaats van dupliceren (vorm 1). De link
        wordt altijd gelegd (idempotent). Concept-koppeling blijft None: een concept
        wordt door emergentie verdiend, niet bij geboorte toegekend. Fail-closed:
        geen notes-store of geen assessment levert geen kaartje (None)."""
        notes = getattr(self.context, "notes", None)
        if notes is None:
            return None
        kind = insight_from_grounding(vraag, assessment, evidence, concept_id=None)
        if kind is None:
            return None
        try:
            notes.add(kind)
            self.log.info("🌱 kind-kaartje uit waaróm-onderzoek: '%s'", vraag[:50])
        except ValueError:
            verrijkt = notes.enrich(kind.id, nieuwe_reference=kind.reference)
            if verrijkt is not None:
                kind = verrijkt
                self.log.info("🌱 kind-kaartje verrijkt: %dde grounding",
                              verrijkt.grounding_count)
        notes.link(kind.id, parent_id)   # geboren-uit: kind wijst naar de trend-kaart
        return kind

    def _on_dag_eindigt(self, event: Event) -> None:
        """Dag-afsluitende reflectie: zoek kaart-paren via relevant_for, vraag per paar
        (max 3) een LLM-oordeel via verband_voorstel. Bij bevestigd verband: sense_tension
        + human_decision_needed. Fail-closed: geen LLM of geen skill → geen voorstel."""
        notes = getattr(self.context, "notes", None)
        if notes is None:
            return
        kaarten = [n for n in notes.all() if n.word]
        if len(kaarten) < 2:
            return

        gezien: set[frozenset] = set()
        paren: list[tuple[Insight, Insight]] = []
        for kaart in kaarten:
            verwant = notes.relevant_for(kaart.word, limit=3)
            for ander in verwant:
                sleutel = frozenset({kaart.id, ander.id})
                if kaart.id == ander.id or sleutel in gezien:
                    continue
                gezien.add(sleutel)
                paren.append((kaart, ander))

        if not paren:
            self.log.info("🔗 dag-reflectie: geen kandidaat-verbanden")
            return

        self.log.info("🔗 dag-reflectie: %d kandidaat-verband(en) gevonden", len(paren))
        for a, b in paren[:3]:
            uitslag = self.use_skill("verband_voorstel", {
                "kaart_a": {"word": a.word, "claim": a.claim},
                "kaart_b": {"word": b.word, "claim": b.claim},
            })
            if uitslag.get("verband"):
                claim = uitslag["claim"]
                self.log.info("🔗 verband voorgesteld: '%s' ↔ '%s' → %s", a.word, b.word, claim)
                self.sense_tension(
                    f"Voorgesteld verband tussen '{a.word}' en '{b.word}': {claim}",
                    kind="governance")
                self.bus.publish(Event("human_decision_needed", {
                    "topic": "verband",
                    "kaart_a_id": a.id, "kaart_b_id": b.id,
                    "voorstel_claim": claim,
                    "reason": f"verband tussen '{a.word}' en '{b.word}'",
                }, self.id))


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
            self.log.info("🌙 dag_eindigt (%s)", label)
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


class HarryHemp(Inhabitant):
    """The Scientist: combineert tijdgeest-observatie (ngram) en academische grounding
    in één inwoner met twee herkenbaar afgescheiden taken.

    Tijdgeest-puls-tak:
      Volgt de lange culturele taalverschuiving via Google Books Ngram Viewer.
      Publiceert stijgende termen als keyword_proposed en sluit de dag af met
      tijdgeest_pulse_completed. Roept _maybe_reflect aan na elke puls.

    Grounding-tak:
      Ontvangt keyword_proposed (van zichzelf of van anderen) en grondt de term
      in academische literatuur (OpenAlex, Semantic Scholar, OpenLibrary).
      Publiceert keyword_evidence. Beslist en cureert nooit zelf.

    Eigen termen worden ook gegrond: Harry publiceert keyword_proposed (puls) én
    consumeert het (grounding). De _busy_terms-dedup voorkomt dat dit een lus wordt:
    zodra een term al in _busy_terms zit, wordt een tweede keyword_proposed voor
    diezelfde term gedropt. Omdat _on_keyword_proposed geen keyword_proposed terug
    publiceert, is er geen echte terugkoppeling — elke term doorloopt de lus precies
    één keer.

    persona "Harry Hemp".
    """

    _SHIFT_THRESHOLD = 2   # minimaal N termen in dezelfde richting voor broadcast

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ── tijdgeest-puls-state ──────────────────────────────────────────────
        self._last_pulse: float = 0.0
        self._busy = False
        self._pulse_interval = float(
            self.context.settings.get("tijdgeest_interval_seconds", str(7 * 24 * 3600)))
        self.react("tijdgeest_pulse", self._run_pulse)   # handmatig triggerable
        # ── grounding-state ───────────────────────────────────────────────────
        self._busy_terms: set[str] = set()
        # Bundeling: verzamel inkomende termen en grond ze in één LLM-call. Default 1
        # = direct gronden per term (ongewijzigd gedrag). >1 = bundelen (minder calls).
        self._batch_size = max(1, int(
            self.context.settings.get("grounding_batch_size", "1")))
        self._pending_groundings: list[dict] = []
        self.react("keyword_proposed", self._on_keyword_proposed)
        # Restbundel legen bij de dagelijkse hartslag, zodat niets blijft hangen.
        self.react("dag_begint", self._flush_groundings)
        # ── spelregel 5: bied de NL-dekkingscheck aan op verzoek (modus a+b) ──
        self.offer("nl_corpus_coverage", self._on_nl_corpus_request)

    def _setup_events(self) -> None:
        # Geen dag_begint → _maybe_reflect; de puls roept _maybe_reflect zelf
        # aan na afloop zodat de interval-check niet op elke dag_begint vuurt.
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

    # ── tijdgeest-puls-tak ────────────────────────────────────────────────────

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

            # Lange-boog-analyse: structurele co-beweging/substitutie tussen missietermen.
            self._report_correlations(rows)

            # Voortzetting voorbij de ngram-cutoff via gekalibreerde OpenAlex-proxy.
            arcs = self._extend_arcs(rows, int(result.get("year_start", 1980)))

            # NL-corpus-dekking (modus c, autonoom): meld alleen wat ontbreekt.
            missing = self._check_nl_corpus(rows)

            # Ik dek dit nu → stel voor te sluiten; de mens bevestigt.
            if arcs:   # minstens één vertrouwde voortzetting → de 2019-cutoff is gedekt
                self.propose_close("ngram_2019_cutoff",
                                   "gedekt via de gekalibreerde OpenAlex-voortzetting")
            self._settle_nl_corpus(rows, missing)

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
                "rows":      rows,
                "terms":     terms,
            }, self.id))
        finally:
            self._busy = False
        self._maybe_reflect(None)
        self._deepen_trends()

    def _report_correlations(self, rows) -> list[dict]:
        """Rapporteer de sterkste co-beweging en substitutie tussen missietermen over de
        lange boog (per locale). De berekening is puur (ngram_correlate); hier alleen
        loggen en als observatie publiceren. Geen besluit, geen API-call."""
        from nooch_village.ngram_correlate import findings_from_rows
        bevindingen = findings_from_rows(rows)
        for b in bevindingen:
            teken = "🔗 co-beweging" if b["label"] == "co-beweging" else "↔️ substitutie"
            self.log.info("%s [%s]: '%s' ~ '%s' (r=%.2f, %d jaar)",
                          teken, b["locale"], b["a"], b["b"], b["r"], b["n"])
        if bevindingen:
            self.bus.publish(Event("tijdgeest_correlatie",
                                   {"by": self.id, "bevindingen": bevindingen}, self.id))
        return bevindingen

    # Corpus-eindjaren: de ngram-data houdt hier echt op (anker voor de voortzetting).
    _CORPUS_END = {26: 2019, 10: 2012}   # EN-corpus 2019, NL-corpus 2012

    def _extend_arcs(self, rows, year_start: int) -> list[dict]:
        """Zet de lange boog voorbij de ngram-cutoff voort via een gekalibreerde OpenAlex-proxy.

        Per term: ngram-reeks t/m het corpus-eindjaar (anker), OpenAlex relatieve aandacht per
        jaar (zelfde skill, mode='yearly'), kalibreer over de overlap, en bouw de voortzetting
        alléén als de correlatie sterk genoeg is. Transparant gelabeld als proxy met de gemeten r.
        Fail-closed: een OpenAlex-fout slaat alleen die term over."""
        from nooch_village.ngram_correlate import years_dict, assess_continuation
        reports: list[dict] = []
        for r in rows:
            ts = r.get("timeseries")
            if r.get("no_data") or not ts:
                continue
            anchor = self._CORPUS_END.get(r.get("corpus"))
            if anchor is None:
                continue
            ngram_years = {y: v for y, v in years_dict(ts, year_start).items() if y <= anchor}
            try:
                oa = self.use_skill("openalex_evidence",
                                    {"term": r["term"], "locale": r.get("locale"),
                                     "mode": "yearly"})
            except Exception as exc:
                self.log.warning("OpenAlex-voortzetting '%s' faalde: %s", r["term"], exc)
                continue
            series = oa.get("series") or {}
            # JSON-grenzen kunnen jaren als string teruggeven; normaliseer naar int.
            series = {int(y): v for y, v in series.items()}
            if not series:
                continue
            res = assess_continuation(ngram_years, series, anchor)
            cal = res["calibration"]
            if res["trusted"]:
                tot = max(res["arc"])
                self.log.info("📈 '%s': boog voortgezet t/m %d via OpenAlex-proxy "
                              "(kalibratie r=%.2f over %d jaar)",
                              r["term"], tot, cal["r"], cal["n"])
                reports.append({"term": r["term"], "locale": r.get("locale"),
                                "calibration": cal, "arc": res["arc"]})
            else:
                reden = ("te weinig overlap" if cal.get("insufficient")
                         else f"zwakke kalibratie (r={cal.get('r')})")
                self.log.info("⚠️ '%s': OpenAlex-voortzetting niet vertrouwd (%s)",
                              r["term"], reden)
        if reports:
            self.bus.publish(Event("tijdgeest_voortzetting",
                                   {"by": self.id, "reports": reports}, self.id))
        return reports

    def _check_nl_corpus(self, rows) -> list[str]:
        """Dynamische NL-corpus-dekkingscheck (regel 6: zoek en meld, niet garandeer).
        Stil tenzij hij iets vindt — een proactieve waarnemer die z'n mond houdt tot er wat is."""
        from nooch_village.ngram_correlate import uncovered_nl_terms, label_uncovered
        missing = uncovered_nl_terms(rows)
        if missing:
            labeled = label_uncovered(missing)
            sterk = [x["term"] for x in labeled if x["signaal"] == "sterk"]
            self.log.info("🇳🇱 NL-corpus mist %d term(en); sterk signaal (los woord): %s",
                          len(missing), sterk or "geen")
            self.bus.publish(Event("nl_corpus_gap",
                                   {"by": self.id, "terms": missing, "labeled": labeled},
                                   self.id))
        return missing

    def _settle_nl_corpus(self, rows, missing) -> None:
        """nl_corpus_coverage afhandelen met oordeel, niet als stempel.

        De oorspronkelijke vraag ("valideer de NL-dekking en documenteer ontbrekende
        kernbegrippen") is nu gedekt: Harry valideert. Dus voorstel tot sluiten. MAAR als de
        validatie échte culturele woorden mist, is het corpus onbruikbaar, en dat is een
        scherper, nieuw gat dat Harry opwerpt in plaats van stil te sluiten. De rol mag dus
        "ja, sluit de vraag, maar hier is het echte probleem" zeggen."""
        if not any(r.get("locale") == "nl" for r in rows):
            return                                  # geen NL gevalideerd → niets te zeggen
        self.propose_close(
            "nl_corpus_coverage",
            "ik valideer en documenteer de NL-dekking nu (modus c + op verzoek)")
        from nooch_village.ngram_correlate import label_uncovered
        sterk = [x["term"] for x in label_uncovered(missing) if x["signaal"] == "sterk"]
        if sterk:
            self._report_means_gap(
                "nl_corpus_bron_onbruikbaar",
                "accountability: structureel alternatieve NL-cultuurbron evalueren — het ngram "
                f"NL-corpus (10, 2012) mist doodgewone missiewoorden ({', '.join(sterk[:5])}); "
                "onbruikbaar voor lange-boog-analyse. Kandidaat: Delpher (KB), of NL bewust "
                "buiten scope.")

    def _on_nl_corpus_request(self, payload) -> None:
        """Op verzoek (spelregel 5, modus a+b): draai een verse NL-dekkingscheck.
        Modus c gebruikt de puls-rijen; hier is er niets bij de hand, dus halen we ze op."""
        result = self.use_skill("ngram_culture", payload or {})
        if "error" in result:
            self.log.warning("NL-dekkingscheck op verzoek mislukt: %s", result["error"])
            self.bus.publish(Event("nl_corpus_check_completed",
                                   {"by": self.id, "ok": False, "error": result["error"]}, self.id))
            return
        missing = self._check_nl_corpus(result.get("rows", []))
        self.log.info("📋 NL-dekkingscheck op verzoek: %d ontbrekende term(en)", len(missing))
        self.bus.publish(Event("nl_corpus_check_completed",
                               {"by": self.id, "ok": True, "terms": missing}, self.id))

    # ── grounding-tak ─────────────────────────────────────────────────────────

    def _on_keyword_proposed(self, event: Event) -> None:
        word   = event.data.get("word", "").strip()
        demand = event.data.get("demand", {})
        locale = demand.get("locale", "")
        if not word or word in self._busy_terms:
            return
        self._busy_terms.add(word)
        self._pending_groundings.append({"word": word, "locale": locale, "demand": demand})
        if len(self._pending_groundings) >= self._batch_size:
            self._flush_groundings()

    def _flush_groundings(self, event: Event | None = None) -> None:
        """Grond de verzamelde termen. Eén term → het bestaande pad (_distill); meerdere
        → één gebundelde LLM-call (_distill_batch). Per term wordt keyword_evidence
        gepubliceerd. Fail-closed: een term zonder oordeel krijgt de fallback-duiding."""
        if not self._pending_groundings:
            return
        batch = self._pending_groundings
        self._pending_groundings = []
        try:
            for it in batch:
                self.log.info("🔬 gronden: '%s' (locale=%s)", it["word"], it["locale"] or "?")
                it["evidence"] = self._gather_evidence(it["word"], it["locale"], limit=3)

            if len(batch) == 1:
                it = batch[0]
                assessments = {it["word"]:
                               self._distill(it["word"], it["locale"], it["evidence"], it["demand"])}
            else:
                self.log.info("🔬 gebundelde grounding van %d termen in één call", len(batch))
                assessments = self._distill_batch(batch)

            for it in batch:
                word = it["word"]
                self.bus.publish(Event("keyword_evidence", {
                    "word":            word,
                    "locale":          it["locale"],
                    "evidence":        it["evidence"],
                    "assessment":      assessments.get(word, ""),
                    "from":            self.id,
                    "original_demand": it["demand"],
                }, self.id))
                self.log.info("📚 evidentie gepubliceerd voor '%s': %d bron(nen)",
                              word, len(it["evidence"]))
        finally:
            for it in batch:
                self._busy_terms.discard(it["word"])

    def _gather_evidence(self, query: str, locale: str = "", limit: int = 3) -> list[dict]:
        """Zoek academisch bewijs voor een zoekstring (een term óf een onderzoeksvraag)
        via Harry's bestaande grounding-skills: OpenAlex en Semantic Scholar. Geeft de
        gevonden hits terug. Fouten en geen-data worden per bron gelogd en leveren
        simpelweg minder hits (fail-closed per bron, geen verzinsels)."""
        evidence: list[dict] = []

        works = self.use_skill("openalex_evidence",
                               {"term": query, "locale": locale, "limit": limit})
        if "error" in works:
            self.log.warning("⚠️ OpenAlex: %s", works["error"])
        elif works.get("no_data"):
            self.log.info("ℹ️ OpenAlex: geen werken voor '%s'", query)
        else:
            evidence.extend(works.get("hits", []))

        papers = self.use_skill("semscholar_tldr",
                                {"term": query, "locale": locale, "limit": limit})
        if "error" in papers:
            self.log.warning("⚠️ Semantic Scholar: %s", papers["error"])
        elif papers.get("no_data"):
            self.log.info("ℹ️ Semantic Scholar: geen papers voor '%s'", query)
        else:
            evidence.extend(papers.get("hits", []))

        return evidence

    def _research_question(self, vraag: str, locale: str = "") -> tuple[list[dict], str]:
        """Onderzoek een afgeleide waaróm-vraag met dezelfde grounding-skills als een term.
        Geeft (evidence, assessment) terug; de assessment is een beknopte duiding van wat
        de bronnen zeggen (of dat er niets gevonden is). Schrijft niets weg en publiceert
        niets: het kind-kaartje plus de link naar de trend-kaart volgen in een aparte stap."""
        evidence = self._gather_evidence(vraag, locale)
        assessment = self._distill(vraag, locale, evidence, demand={})
        return evidence, assessment

    def _deepen_trends(self) -> None:
        """Verdiep bevestigde trend-kaartjes tot één hop diep.

        Kiest met select_for_deepening welke trends mogen (emergentie + diepte +
        dagbudget), leidt per trend één waaróm-vraag af (onderzoeksvraag-skill),
        onderzoekt die met de grounding-skills, en publiceert child_evidence zodat de
        Librarian er een kind-kaartje van schrijft. Schrijft zelf niets weg: kennis
        cureren is het domein van de Librarian."""
        from nooch_village.emergence import select_for_deepening
        notes = getattr(self.context, "notes", None)
        if notes is None:
            return
        budget = int(self.context.settings.get("deepen_budget", 2) or 0)
        for trend in select_for_deepening(notes.all(), budget):
            if not trend.word:
                continue
            res = self.use_skill("onderzoeksvraag",
                                 {"kaart": {"word": trend.word, "claim": trend.claim}})
            vraag = res.get("vraag")
            if not vraag:
                continue
            evidence, assessment = self._research_question(vraag)
            self.bus.publish(Event("child_evidence", {
                "parent_id":  trend.id,
                "vraag":      vraag,
                "evidence":   evidence,
                "assessment": assessment,
                "from":       self.id,
            }, self.id))
            self.log.info("🌱 waaróm onderzocht voor '%s': %s", trend.word, vraag[:50])

    def _fallback_assessment(self, word: str, locale: str, evidence: list[dict]) -> str:
        """Deterministische duiding zonder LLM (geen bron, of LLM niet beschikbaar).
        Gedeeld door _distill (één woord) en _distill_batch (bundel), zodat bundeling
        nooit een woord verliest: in het ergste geval krijgt elk woord deze samenvatting."""
        if not evidence:
            return (f"No academic sources found for '{word}' "
                    f"(locale={locale or 'unknown'}; v1: OpenAlex + Semantic Scholar).")
        titels = "; ".join(e.get("title", "?")[:60] for e in evidence[:3])
        return f"{len(evidence)} source(s) found for '{word}': {titels}."

    def _distill(self, word: str, locale: str,
                 evidence: list[dict], demand: dict) -> str:
        """Destilleer gevonden evidentie tot een beknopte relevantie-duiding.

        Citeer UITSLUITEND bronnen die in `evidence` staan. Fabriceer geen titels,
        auteurs, abstracten of DOI's die niet daadwerkelijk zijn opgehaald.
        """
        if not evidence:
            return self._fallback_assessment(word, locale, evidence)

        bron_regels: list[str] = []
        for e in evidence[:5]:
            jaar  = e.get("year") or "?"
            tldr  = e.get("tldr", "")
            bron_regels.append(
                f"- {e.get('title','?')} ({jaar}) [{e.get('source','?')}]"
                + (f"\n  tldr: {tldr}" if tldr else ""))

        from nooch_village.llm import reason as llm_reason
        prompt = (
            f"Assessment requested for the term '{word}' (locale: {locale or '?'}) "
            f"for Nooch.earth (sustainable shoes, no plastic, no leather).\n"
            f"Sources found ({len(evidence)}):\n" + "\n".join(bron_regels) + "\n\n"
            f"In at most 2 sentences: (1) the substantive/scientific relevance of '{word}', "
            f"(2) whether the sources support or contradict the mission claim. "
            f"Base your answer ONLY on the sources above. Do not invent titles or authors. "
            f"If you cannot assess it, say so explicitly."
        )
        from nooch_village.language import instruction
        # Knowledge-layer output is ALWAYS English, regardless of the term's locale.
        prompt = prompt + "\n" + instruction()
        llm_out = llm_reason(prompt)
        if llm_out:
            return llm_out.strip()

        return self._fallback_assessment(word, locale, evidence)

    def _distill_batch(self, items: list[dict]) -> dict:
        """Beoordeel meerdere termen in ÉÉN LLM-call (bundeling: minder verzoeken tegen
        de rate-limit). items: [{"word","locale","evidence"}]. Geeft {word: assessment}.

        Fail-closed: geen of onparseerbare LLM-output → per woord de deterministische
        fallback, zodat bundeling nooit een woord verliest. Citeert uitsluitend de
        meegegeven bronnen; output is altijd Engels (kennislaag-werktaal)."""
        if not items:
            return {}
        blokken = []
        for it in items:
            ev = it.get("evidence") or []
            bronnen = "; ".join(
                f"{e.get('title','?')[:60]} ({e.get('year','?')})" for e in ev[:5]
            ) or "(no sources)"
            blokken.append(
                f'- term "{it["word"]}" (locale: {it.get("locale") or "?"}): {bronnen}')

        from nooch_village.llm import reason as llm_reason
        from nooch_village.language import instruction
        prompt = (
            "Assess each term below for Nooch.earth (sustainable shoes, no plastic, no "
            "leather). For each term, in at most 2 sentences: its substantive relevance "
            "and whether the sources support or contradict the mission claim. Use ONLY "
            "the listed sources; do not invent titles or authors.\n\n"
            + "\n".join(blokken) +
            '\n\nReturn ONLY a JSON object mapping each exact term string to its '
            "assessment string, no prose, no code fences.\n" + instruction()
        )
        out = llm_reason(prompt)
        parsed: dict = {}
        if out:
            import json, re
            cleaned = re.sub(r"```(?:json)?", "", out).strip()
            s, e = cleaned.find("{"), cleaned.rfind("}")
            if s != -1 and e != -1 and e > s:
                try:
                    data = json.loads(cleaned[s:e + 1])
                    if isinstance(data, dict):
                        parsed = {k: str(v).strip() for k, v in data.items()
                                  if str(v).strip()}
                except (ValueError, TypeError):
                    parsed = {}

        result: dict = {}
        for it in items:
            w = it["word"]
            result[w] = parsed.get(w) or self._fallback_assessment(
                w, it.get("locale", ""), it.get("evidence") or [])
        return result

    # ── reflectie ─────────────────────────────────────────────────────────────

    def _reflect(self) -> None:
        """Geen hardcoded zelf-gaten meer; beide zijn opgelost en nu dynamisch.

        ngram_2019_cutoff  → opgelost via de gekalibreerde OpenAlex-voortzetting (_extend_arcs).
        nl_corpus_coverage → nu dynamisch: _check_nl_corpus leest per puls (modus c) welke
        NL-termen het corpus echt mist, en is op verzoek opvraagbaar via spelregel 5
        (_on_nl_corpus_request). Geen vaste klacht meer, maar zoeken-en-melden (regel 6).
        """
        return


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
        "gsc_pulse_completed",
        "competitor_signal",
        "linkbuilding_target",
        "competitor_interest",
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


class ContentStrategist(Inhabitant):
    """Model C: spot autonoom content-waardige clusters en stel ze voor; op goedkeuring
    van de mens draft hij. Elke tekst gaat via een mens. Schrijft zelf niets publiek weg,
    levert suggesties en drafts in de inbox (via events naar de Village)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # base _setup_events houdt dag_begint → _maybe_reflect; hier komt het spotten erbij
        self.react("dag_begint", self._spot_content)
        self.react("content_suggestion_approved", self._on_suggestion_approved)

    def _spot_content(self, event) -> None:
        """Op de dag-cadans: spot content-waardige clusters en stel ze voor. De inbox
        dedupt op seed, dus dezelfde kans komt niet dubbel. Begrensd door content_budget."""
        notes = getattr(self.context, "notes", None)
        if notes is None:
            return
        budget = int(self.context.settings.get("content_budget", 2) or 0)
        for seed in notes.content_seeds(budget):
            cluster = notes.cluster(seed.id)
            self.bus.publish(Event("content_opportunity", {
                "seed_id":     seed.id,
                "cluster_ids": [c.id for c in cluster],
                "reason":      f"bevestigd cluster rond '{seed.word or seed.id}'",
                "by":          self.id,
            }, self.id))
            self.log.info("✍️ content-kans gespot: '%s' (%d kaartjes)",
                          seed.id, len(cluster))

    def _on_suggestion_approved(self, event: Event) -> None:
        """De mens keurde een content-suggestie goed → draft. Bouw het cluster, schrijf
        een volledige eerste draft (content_schrijven), en publiceer 'm naar de inbox. De
        mens herschrijft daarna. Fail-closed: geen seed/cluster/LLM → geen draft."""
        notes = getattr(self.context, "notes", None)
        seed_id = event.data.get("seed_id")
        if notes is None or not seed_id:
            return
        cluster = notes.cluster(seed_id)
        if not cluster:
            return
        cards = [{"id": c.id, "word": c.word, "claim": c.claim,
                  "status": getattr(c.status, "value", str(c.status))} for c in cluster]
        kind = event.data.get("kind", "blog")
        res = self.use_skill("content_schrijven", {
            "cards":           cards,
            "kind":            kind,
            "audience":        event.data.get("audience", ""),
            "desired_outcome": event.data.get("desired_outcome", ""),
        })
        text = res.get("text")
        if not text:
            self.log.info("✍️ geen draft voor '%s' (geen LLM of materiaal)", seed_id)
            return
        self.bus.publish(Event("content_draft_ready", {
            "seed_id":           seed_id,
            "kind":              kind,
            "text":              text,
            "claim_insight_ids": res.get("claim_insight_ids", []),
            "by":                self.id,
        }, self.id))
        self.log.info("✍️ draft klaar voor '%s' (%s)", seed_id, kind)
