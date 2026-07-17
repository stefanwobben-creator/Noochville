"""Gespecialiseerde inwoners met eigen gedrag bovenop de generieke Inhabitant."""
from __future__ import annotations
import hashlib, os, json, time
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from nooch_village.util import atomic_write_json, run_bounded, is_due


def _should_fire_daily(now, last_day, fire_hh: int, fire_mm: int) -> bool:
    """Vuur de dagcyclus zodra de LOKALE tijd het vaste kloktijdstip (fire_hh:fire_mm) heeft bereikt
    en we die kalenderdag nog niet gevuurd hebben. `last_day` = de laatst-gevuurde datum (persistent),
    zodat een restart/deploy niet dubbel vuurt en het volgende moment niet verschuift; miste de server
    04:32 (was down), dan vuurt hij de dag alsnog éénmaal bij de eerste tick erna."""
    if now.date().isoformat() == last_day:
        return False
    return (now.hour, now.minute) >= (fire_hh, fire_mm)
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
            # De dure LLM-duiding (proza) draait wekelijks; de data (tension, last_pulse, raw json)
            # blijft dagelijks. Zo bouw je elke dag historie op maar bespaar je dagelijks LLM-verbruik.
            prose = self._field_note_prose_due()
            note = self.use_skill("field_note",
                                  {"plausible": plausible, "trends": trends, "prose": prose})

            self._log_pulse_metrics(plausible)
            self._collect_daily_observations()             # generiek: elke actieve bron → observaties
            self._sense_dead_sources()                     # dood-overgang (fresh→stale) → spanning
            self._surface_locale(plausible)

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

    def _surface_locale(self, plausible: dict) -> None:
        """Duid de bezoekersdata per locale (Plausible country-breakdown). De capaciteit zit al
        in plausible_stats; deze stap ontsluit 'm zodat de accountability 'bezoekersdata per
        locale duiden' echt wordt uitgevoerd, en publiceert het als signaal voor Noochie."""
        countries = (plausible or {}).get("countries") or []
        rows = [{"locale": (c.get("country") or c.get("name") or "?"),
                 "visitors": c.get("visitors", 0)} for c in countries if isinstance(c, dict)]
        if not rows:
            return
        top = rows[:6]
        self.log.info("📍 bezoekers per locale: %s",
                      ", ".join(f"{r['locale']} {r['visitors']}" for r in top))
        self.bus.publish(Event("locale_insight", {"by": self.id, "countries": rows[:10]}, self.id))

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

    def _field_note_prose_due(self) -> bool:
        """Wekelijkse cadans voor de LLM-proza van de Field Note (zuinig). De dagelijkse data draait
        sowieso; alleen de dure duiding is gepoort. `field_note_interval_seconds` = 0 → elke puls (oud
        gedrag). De stempel wordt gezet zodra de proza aan de beurt is."""
        interval = float(self.context.settings.get("field_note_interval_seconds", "604800") or 604800)
        if interval <= 0:
            return True
        state_path = os.path.join(self.context.data_dir, "field_note_prose_last.json")
        try:
            last = float(json.load(open(state_path)).get("ts", 0))
        except Exception:
            last = 0.0
        now = time.time()
        if is_due(last, now, interval):
            try:
                with open(state_path, "w") as f:
                    json.dump({"ts": now}, f)
            except Exception:
                pass
            return True
        self.log.info("⏭️ Field Note-proza overgeslagen (wekelijkse cadans nog niet verstreken)")
        return False

    def _log_pulse_metrics(self, plausible: dict) -> None:
        """Log de UTM-kanaal-metrics (visitors_via_*) uit de puls — kanaaldata heeft géén eigen
        DataSourceSkill/collector-pad, dus die schrijft de rol hier weg.

        REFERENCE, DON'T COPY: de rol dupliceert GEEN canonieke waarden meer. De gemonitorde-metric-lijst
        (MonitoringStore, gevuld via `_on_advice_ready` uit Noochie's keep-verdicts) bewaart alleen WELKE
        metrics een rol volgt — een lijst verwijzingen. De waarden zelf leest een rol-view/signaleringslaag
        straks via referentie uit de canonieke reeksen (plausible_visitors_day etc.) die de generieke
        collector schrijft; hier wordt dus GEEN tweede waarde-kopie onder role_id weggeschreven. (Vóór deze
        refactor schreef een Stap-9-tak de rauwe metric-waarde onder role_id — een kopie, verwijderd.)

        DATUMLABEL + IDEMPOTENTIE: de visitors_via_*-waarden zijn een 7-daags Plausible-aggregaat, per puls
        ververst. Gelabeld met de LAATST-COMPLETE dag (UTC gisteren) en via record_daily weggeschreven —
        één waarde per dag (dedup op (role_id, metric, bron, datum); nooit de lopende, onvolledige dag).
        """
        obs = getattr(self.context, "observations", None)
        if obs is None:
            return
        datum = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()   # laatst-complete dag (UTC)
        pulse_dict = dict(_extract_pulse_metrics(plausible))
        for key, value in pulse_dict.items():
            if key.startswith("visitors_via_"):
                obs.record_daily(self.id, key, value, bron="plausible", datum=datum)
        # De losse dagwaarden per bron (visitors/pageviews/visit_duration/shopify/gsc) lopen via de
        # generieke collector (_collect_daily_observations); een rol die metrics "volgt" leest die
        # canonieke reeksen via referentie (MonitoringStore = curatie-lijst), zonder ze te kopiëren.

    def _collect_daily_observations(self) -> None:
        """Generieke dag-observatie-collector: elke ACTIEVE DataSourceSkill schrijft z'n gedeclareerde
        velden weg onder `<source>_<field>_day`. Niets per bron/veld hardcoded; fail-closed."""
        from nooch_village.collector import collect_daily_observations
        obs = getattr(self.context, "observations", None)
        sources = getattr(self.context, "sources", None)
        if obs is None or sources is None or self.registry is None:
            return
        try:
            written = collect_daily_observations(self.registry, sources, obs, self.context)
            if written:
                self.log.info("dag-observaties geschreven: %s", written)
            # Contract-healthcheck (meetcatalogus): ongecatalogiseerde reeks of niet-vullende ACTIEVE family
            # → luid signaal. Bewust-inactieve bronnen zwijgen. Nooit blokkerend voor de puls.
            try:
                from nooch_village.meetcatalog import healthcheck
                for sig in healthcheck(obs):
                    self.log.warning("🩺 meetcatalogus-signaal: %s", sig)
            except Exception as exc:
                self.log.warning("meetcatalogus-healthcheck faalde: %s", exc)
        except Exception as exc:
            self.log.warning("dag-observatie-collector faalde: %s", exc)

    def _sense_dead_sources(self) -> None:
        """Senst op de OVERGANG van 'recente data' naar 'dood' (fresh→stale uit indicator_freshness):
        publiceert per overgang een `source_died`-event; de Village schrijft er generiek een means-gap
        voor in de human_inbox. Dedup + kind-aware drempel zitten in de sensor. Fail-closed."""
        import os
        from nooch_village.deadsource import DeadSourceState, sense_dead_sources
        if getattr(self.context, "observations", None) is None or self.registry is None:
            return
        state = DeadSourceState(os.path.join(self.context.data_dir, "deadsource_state.json"))

        def emit(source, field, last_datum, days_ago, cadans):
            self.bus.publish(Event("source_died", {
                "source": source, "field": field, "last_datum": last_datum,
                "days_ago": days_ago, "cadans": cadans, "by": self.id}, self.id))
        try:
            died = sense_dead_sources(self.registry, self.context, state, emit)
            if died:
                self.log.info("dode-bron-overgangen gesensed: %s", died)
        except Exception as exc:
            self.log.warning("dode-bron-sensor faalde: %s", exc)

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
        from nooch_village.skills_impl.trends import _geo_to_locale
        lib = self.context.library
        locale = _geo_to_locale(trends.get("geo", ""))   # taalvak uit de geo van de run
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
                        "locale": locale,
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
                    "locale": row.get("locale", ""),   # taalvak uit het site-domein
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
        # Seed-opleving: zoek de actuele nieuws-aanleiding (RSS) parallel aan Harry's duiding.
        self.react("seed_surge_sensed", self._explain_surge)

    def _explain_surge(self, event: Event) -> None:
        """Zoek de waarschijnlijke nieuws-AANLEIDING voor een seed-verschuiving: breed Google
        News op de kale term (geen schoen-/merkfilter), daarna kiest de LLM uit de top de kop die
        de stijging/daling het best verklaart (regelgeving > studie > incident > aandacht > markt).
        Bewaart 'm in de seed-surge-store + publiceert seed_surge_explanation. Fail-closed."""
        import os as _os
        term = (event.data.get("term") or "").strip()
        if not term:
            return
        from nooch_village import web_read
        key = (self.context.settings.get("serpapi_api_key", "")
               or _os.environ.get("SERPAPI_API_KEY", ""))
        items = web_read.serpapi_news(term, key, num=10)
        if not items:
            self.log.info("📰 geen nieuws-aanleiding gevonden voor '%s'", term)
            return
        top = self._pick_news_driver(term, items)
        expl = {"title": top.get("title", ""), "link": top.get("link", ""),
                "date": top.get("date", "")}
        try:
            from nooch_village.seed_surge_store import SeedSurges
            SeedSurges(os.path.join(self.context.data_dir,
                                    "seed_surges.json")).set_explanation(term, expl)
        except Exception as e:
            self.log.info("kon seed-verklaring niet opslaan: %s", e)
        self.log.info("📰 mogelijke aanleiding voor '%s': %s", term, expl["title"][:70])
        self.bus.publish(Event("seed_surge_explanation",
                               {"by": self.id, "term": term, **expl}, self.id))

    def _pick_news_driver(self, term: str, items: list[dict]) -> dict:
        """LLM kiest uit de koppen de waarschijnlijke aanleiding (regelgeving > onderzoek >
        incident > aandacht > markt; negeer losse vermeldingen). Fail-closed → nieuwste (eerste)."""
        import re
        from nooch_village.llm import reason
        top = items[:8]
        lines = "\n".join(
            f"{i + 1}. {it.get('title', '')} ({it.get('source', '')}, {it.get('date', '')})"
            for i, it in enumerate(top))
        prompt = (
            f"De zoekinteresse in '{term}' is recent verschoven. Welke kop verklaart die "
            f"verschuiving het waarschijnlijkst? Weeg op aanleiding-kracht: regelgeving/beleid > "
            f"onderzoek/rapport > incident/gebeurtenis > aandacht/cultuur > markt. Negeer losse "
            f"vermeldingen.\n\n{lines}\n\n"
            f"Antwoord met ALLEEN het nummer (1-{len(top)}).")
        out = reason(prompt, call_site="news_driver_pick")
        if out:
            m = re.search(r"\d+", out)
            if m:
                idx = int(m.group()) - 1
                if 0 <= idx < len(top):
                    return top[idx]
        return top[0]                                     # fail-closed: nieuwste/relevantste

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
            self._run_community_listening()
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

    def _news_store(self):
        from nooch_village.competitor_news_store import CompetitorNews
        return CompetitorNews(os.path.join(self.context.data_dir, "competitor_news.json"))

    def _run_news(self, monitored: list[str]) -> None:
        self.log.info("🔭 concurrent-scan gestart (%d merken)", len(monitored))
        res = self.use_skill("competitor_news", {"brands": monitored} if monitored else {})
        if not res.get("ok"):
            self.log.warning("⚠️ concurrent-scan mislukt: %s", res.get("error"))
            self.bus.publish(Event("competitor_pulse_completed",
                {"by": self.id, "ok": False, "error": res.get("error")}, self.id))
            return
        items = res.get("items", [])
        try:                                              # per-merk laatste nieuws voor de cockpit
            self._news_store().update(items)
        except Exception as e:
            self.log.info("kon concurrent-nieuws niet opslaan: %s", e)
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
        """Spot kandidaat-concurrenten en zet ze (deduped) in de store voor jouw oordeel.

        OPT-IN: de auto-discovery via SerpAPI-listicles draait alleen als er expliciet een `discover_query`
        (het onderwerp/de categorie) in de config staat. Standaard komen concurrenten uit de gecureerde
        Inoreader-feed, niet uit een ongecureerde scrape — die scrape was de bron van de merk-ruis. Geen
        `discover_query` → stil overslaan (geen puls-ruis), zodat de feed de bron blijft."""
        if "competitor_discover" not in self.dna.skills:
            return
        if not str((getattr(self.context, "settings", {}) or {}).get("discover_query", "")).strip():
            return                                            # geen onderwerp geconfigureerd → discovery uit
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
        country = self.context.settings.get("ke_country", "").strip()   # leeg = global
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

    def _run_community_listening(self) -> None:
        """Billy Buzz: verzamel gebruikerservaringen (YouTube + Bluesky, Reddit inactief) over een
        onderwerp als observaties en post een wall-samenvatting op de eigen rol-notes. Gegate op DNA
        (skill via governance toegekend); zonder grant doet deze puls niets. Grounded: geen kansen-taal."""
        if "community_listening" not in self.dna.skills:
            return
        set_id = self.context.settings.get("buzz_query_set", "barefoot_ervaringen")
        res = self.use_skill("community_listening", {"query_set_id": set_id})
        if not res.get("ok"):
            self.log.info("🎧 community_listening overgeslagen: %s",
                          res.get("error") or res.get("refuse"))
            return
        count = int(res.get("new", 0) or 0)
        self.bus.publish(Event("buzz.observations.new",
            {"by": self.id, "count": count, "counts": res.get("counts", {}),
             "query_set_id": set_id}, self.id))
        self.log.info("🎧 community_listening [%s]: %s", set_id, res.get("summary", ""))
        if count:                                     # alleen bij nieuw materiaal een wall-post
            self._post_buzz_wall(set_id)

    def _post_buzz_wall(self, set_id: str) -> None:
        """Vat de opvallendste rijen over platforms heen samen en post ze als note-artefact op de rol.
        Geen normalisatie (YT-likes vs Bluesky-likes = appels/peren): top-3 YouTube + top-2 Bluesky op
        eigen score, aangevuld tot 5 als één bron leeg is. Elk punt krijgt een platform-prefix, bij
        YouTube de videotitel, en eindigt op de permalink. Parafrase van de LLM (persona-toon), zonder
        LLM een grounded terugval op het fragment — geen verzonnen inhoud, geen kansen-taal."""
        store = getattr(self.context, "buzz_observations", None)
        att = getattr(self.context, "att", None)
        if store is None or att is None:
            return
        rows = self._buzz_top(store, set_id)
        if not rows:
            return
        label = self._buzz_set_label(set_id)
        bullets = self._buzz_bullets(rows, label)
        if not bullets:
            self.log.info("🎧 geen wall-punten met link — niets gepost")
            return
        from datetime import date
        body = f"Wat er speelt over {label} (top {len(bullets)}, YouTube + Bluesky):\n\n" + "\n".join(bullets)
        if len(body) > 4000:                          # body-cap: bewust weigeren i.p.v. stil afkappen
            self.log.warning("🎧 wall-samenvatting >4000 tekens — niet gepost (splits de set of kort de fragmenten in)")
            return
        title = f"Community-observaties — {label} ({date.today().isoformat()})"
        att.add(anchor=self.id, kind="note", title=title, body=body,
                actor_id=(self.record.persona_id or ""), actor_type="persona",
                change_note=f"community_listening puls ({set_id})")
        self.log.info("🎧 wall-samenvatting (%d punten) gepost op %s → notes", len(bullets), self.id)

    def _buzz_top(self, store, set_id: str) -> list[dict]:
        """Top-3 YouTube + top-2 Bluesky (op eigen score, met permalink), aangevuld tot 5 uit de
        overige bronnen als één platform niet levert. Nooit normaliseren tussen platforms."""
        def _linked(rows):
            return [r for r in rows if (r.get("permalink") or "").strip()]
        rows = _linked(store.top_by_score(set_id, limit=3, platform="youtube")) + \
            _linked(store.top_by_score(set_id, limit=2, platform="bluesky"))
        if len(rows) < 5:
            seen = {r["permalink"] for r in rows}
            for r in _linked(store.top_by_score(set_id, limit=12)):
                if r["permalink"] not in seen:
                    rows.append(r)
                    seen.add(r["permalink"])
                if len(rows) >= 5:
                    break
        return rows[:5]

    def _buzz_set_label(self, set_id: str) -> str:
        qs = getattr(self.context, "buzz_query_sets", None)
        rec = qs.get(set_id) if qs is not None else None
        return (rec or {}).get("label") or set_id

    _BUZZ_PREFIX = {"youtube": "[YouTube]", "bluesky": "[Bluesky]", "reddit": "[Reddit]"}

    def _buzz_bullets(self, rows: list[dict], label: str) -> list[str]:
        """Bouw per rij één bullet met platform-prefix (bij YouTube de videotitel) die eindigt op de
        permalink. De parafrase komt uit de LLM (genummerd, in rij-volgorde); de permalink hangen we
        deterministisch aan zodat elk punt gegarandeerd een werkende link draagt. Fail-closed:
        geen/onvolledig LLM-antwoord → de rij valt terug op zijn feitelijke fragment (grounded)."""
        import re
        paraphrases: dict[int, str] = {}
        try:
            from nooch_village.llm import reason
            from nooch_village.personas import persona_prompt, PersonaStore
            persona = None
            if getattr(self.record, "persona_id", None):
                try:
                    persona = PersonaStore(
                        os.path.join(self.context.data_dir, "personas.json")).get(self.record.persona_id)
                except Exception:
                    persona = None
            listing = "\n".join(
                f"{i + 1}. [{r.get('platform','?')}] "
                + (f"video “{r.get('context_title','')}” — "
                   if r.get('platform') == 'youtube' and r.get('context_title') else "")
                + f"(score {r.get('score',0)}) {(r.get('fragment') or r.get('title') or '').strip()}"
                for i, r in enumerate(rows))
            prompt = (
                (persona_prompt(persona) + "\n\n" if persona else "") +
                f"Hieronder staan community-reacties (YouTube-comments en Bluesky-posts) over {label}. "
                f"Schrijf per item ÉÉN korte, feitelijke parafrase (max 20 woorden) van wat er staat. "
                f"Geen kansen-taal ('dit is een kans voor…'), geen advies, geen oordeel — alleen wat er "
                f"staat. Antwoord met genummerde regels 1..{len(rows)}, één regel per item, in dezelfde "
                f"volgorde.\n\n{listing}")
            out = reason(prompt, call_site="buzz_wall_summary") or ""
            for line in out.splitlines():
                m = re.match(r"\s*(\d+)[.):]\s*(.+)", line)
                if m:
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(rows):
                        paraphrases[idx] = m.group(2).strip().strip('"')
        except Exception as e:
            self.log.info("🎧 LLM-parafrase overgeslagen (%s) — feitelijke fragmenten", e)
        bullets = []
        for i, r in enumerate(rows):
            text = paraphrases.get(i) or (r.get("fragment") or r.get("title") or "").strip()[:140]
            if not text:
                continue
            prefix = self._BUZZ_PREFIX.get(r.get("platform"), f"[{r.get('platform','?')}]")
            ctx = (r.get("context_title") or "").strip()
            mid = f' “{ctx}” —' if (r.get("platform") == "youtube" and ctx) else " —"
            bullets.append(f"- {prefix} {text}{mid} {r['permalink']}")
        return bullets

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
        from nooch_village.skills_impl.keywords_everywhere import opportunity_score
        kw = res["keywords"][0]
        vol = int(kw.get("vol", 0) or 0)
        comp = float(kw.get("competition", 0) or 0)
        # Kans bij goedkeuren zonder GSC = volle upside (we ranken nog niet); enrich_volumes
        # verfijnt later met onze echte positie. competition = Google Ads-druk, los infoveld.
        opp = opportunity_score(vol)
        self.log.info("📐 KE: '%s' → volume %d/mnd · ad-concurrentie %.2f · kans %s",
                      word, vol, comp, opp)
        return {**demand, "volume": vol, "competition": comp,
                "opportunity": opp, "ke_country": self._ke_country()}

    def _ke_country(self) -> str:
        return self.context.settings.get("ke_country", "").strip()   # leeg = global

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
        self._last_beat: float = 0.0
        self._first_ring: bool = True
        self._interval: float = float(self.context.settings.get("heartbeat_seconds", 0) or 0)
        # Vast kloktijdstip voor dag_begint (config, centraal in settings.ini).
        raw = str(self.context.settings.get("dag_begint_time", "04:32")).strip()
        try:
            hh, mm = raw.split(":")
            self._fire_hh, self._fire_mm = int(hh), int(mm)
        except Exception:
            self._fire_hh, self._fire_mm = 4, 32
        # Tijdzone EXPLICIET uit config (IANA, via stdlib zoneinfo), los van de server-tz — Nooch zit
        # in Spanje. Ongeldige/ontbrekende zone → None = val terug op server-lokale tijd (fail-soft).
        tz_name = str(self.context.settings.get("dag_begint_tz", "Europe/Madrid")).strip()
        try:
            self._tz = ZoneInfo(tz_name) if tz_name else None
        except Exception:
            self._tz = None
        # Laatst-gevuurde datum persistent → restart/deploy vuurt niet dubbel en verschuift niet.
        self._last_day: str | None = self._load_last_day()

    def _last_day_path(self) -> str:
        return os.path.join(self.context.data_dir, "timekeeper_last_day.json")

    def _load_last_day(self):
        try:
            with open(self._last_day_path()) as f:
                return json.load(f).get("last_day")
        except Exception:
            return None

    def _save_last_day(self) -> None:
        try:
            atomic_write_json(self._last_day_path(), {"last_day": self._last_day})
        except Exception:
            pass

    def tick(self) -> None:
        if self._interval > 0:                        # demo/test: relatieve hartslag (heartbeat_seconds)
            now = time.time()
            if now - self._last_beat >= self._interval:
                self._last_beat = now
                self._ring("demo-puls", date.today())
            return
        # productie: één keer per kalenderdag op het vaste kloktijdstip in de GECONFIGUREERDE tijdzone
        # (dag_begint_tz), niet de server-tz. _should_fire_daily + de persist-datum rekenen hiertegen.
        now_local = datetime.now(self._tz)
        if _should_fire_daily(now_local, self._last_day, self._fire_hh, self._fire_mm):
            self._last_day = now_local.date().isoformat()
            self._save_last_day()
            self._ring(self._last_day, now_local.date())

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
        # Autonoom: van een GOEDGEKEURD high_potential GSC-keyword een onderzoeksproject maken.
        self.react("keyword_decided", self._on_keyword_decided)
        # Restbundel legen bij de dagelijkse hartslag, zodat niets blijft hangen.
        self.react("dag_begint", self._flush_groundings)
        # Seed-oplevingen (door enrich gesignaleerd) academisch duiden.
        self.react("dag_begint", self._investigate_seed_surges)
        # Sid's dagelijkse trend-re-index (raadsvoorstel): elke dag uit zichzelf, één run per
        # echte dag. Staand zintuig, geen deliverable-project → pulse-hook, net als de tijdgeest-puls.
        self.react("dag_begint", self._trend_reindex_pulse)
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

    def _trend_reindex_pulse(self, event: Event) -> None:
        """Sid's dagelijkse trend-re-index (taak 2). Idempotent per echte dag: draait één keer,
        ook als dag_begint onverhoopt tweemaal vuurt. Signalen → keyword_proposed (de bestaande
        curate/grounding-lus = de curate-hand-off); escalate → zichtbaar naar de founder (taak 3).
        Alleen-lezen naar buiten: de skill haalt Trends-data op, schrijft enkel zijn eigen
        append-only bestanden en levert termen aan de Librarian; koopt/verstuurt niets."""
        import datetime, json, os
        today = datetime.date.today().isoformat()
        marker = os.path.join(self.context.data_dir, "trend_reindex_last_day.json")
        try:                                                   # same-day-guard (persistent vangnet)
            if json.load(open(marker)).get("last_day") == today:
                return
        except Exception:
            pass
        result = self.use_skill("trend_reindex", {})
        if not isinstance(result, dict) or result.get("error"):
            self.log.warning("trend_reindex: geen bruikbaar resultaat (%s)",
                             (result or {}).get("error") if isinstance(result, dict) else result)
            return
        # Markeer de dag pas ná een geslaagde aanroep (fail-closed: een gefaalde run mag morgen opnieuw).
        try:
            from nooch_village.util import atomic_write_json
            atomic_write_json(marker, {"last_day": today})
        except Exception:
            pass
        esc = result.get("escalate")
        if esc:
            self._notify_founder("", f"📉 Sid's trend-re-index kon niet draaien: "
                                 f"{esc.get('reason', 'onbekende reden')} — "
                                 f"beoordeel via python -m nooch_village.inbox")
            return
        signals = result.get("signals") or []
        lib = getattr(self.context, "library", None)
        for row in signals:                                    # curate-hand-off via de bestaande lus
            _publish_keyword_proposed(
                self.bus, self.id, row["term"],
                demand={"signal": "positive", "source": "trend_reindex",
                        "direction": "stijgend", "signal_type": row.get("signal_type"),
                        "index_latest": row.get("index_latest")},
                library=lib)
        self.log.info("📊 trend-re-index: %d geëvalueerd, %d signaal(en), watchlist=%d",
                      len(result.get("evaluated") or []), len(signals),
                      len(result.get("watchlist") or []))

    def _investigate_seed_surges(self, event: Event) -> None:
        """Een seed met een aanhoudende recente opleving (door enrich gesignaleerd) vraagt om
        een verklaring. Harry grondt de term academisch (zijn grounding-tak → keyword_evidence)
        en markeert de opleving als onderzocht. Spanning → duiding, mens-zichtbaar in de kennislaag."""
        from nooch_village.seed_surge_store import SeedSurges
        store = SeedSurges(os.path.join(self.context.data_dir, "seed_surges.json"))
        for s in store.pending():
            term = s.get("term", "")
            if not term:
                continue
            direction = s.get("direction", "stijgend")
            self.log.info("🔬 seed-verschuiving '%s' (%s) → academische duiding gezocht",
                          term, direction)
            # breed signaal: de scout zoekt parallel de nieuws-aanleiding (RSS)
            self.bus.publish(Event("seed_surge_sensed",
                                   {"by": self.id, "term": term, "direction": direction,
                                    "locale": s.get("locale", "")}, self.id))
            self._on_keyword_proposed(Event("keyword_proposed", {
                "word": term,
                "demand": {"source": "seed_surge", "direction": direction,
                           "locale": s.get("locale", ""), "pct": s.get("pct")},
            }, self.id))
            store.mark_investigated(term)

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

    # ── Autonoom onderzoeksproject van een goedgekeurd high_potential GSC-keyword ──────────
    _KW_RESEARCH_ORIGIN = "keyword_research"
    _BRANDED_DEFAULT = "nooch,noech,nootch,noogh,nooches"     # merk-varianten; komma-gescheiden, lowercase
    _KW_RESEARCH_SCOPE = ("Onderzoek naar '{kw}': patenten, wetenschappelijke studies "
                          "en culturele trend in kaart gebracht")

    def _on_keyword_decided(self, event: Event) -> None:
        """Reageer op keyword_decided: maak — fail-closed — een onderzoeksproject in TOEKOMST voor een
        zojuist GOEDGEKEURD high_potential GSC-keyword. Herkomst komt NIET uit de event-payload (die
        draagt geen demand) maar uit de library-evidence. Geen dubbel project (dedup over álle statussen),
        en niet boven het open-plafond. Elke ontbrekende schakel → geen project + één debug-logregel."""
        if event.data.get("status") != "approved":
            return                                                   # forbidden/known/... stil negeren
        word = (event.data.get("word") or "").strip()
        lib = getattr(self.context, "library", None)
        ledger = getattr(self.context, "projects", None)
        if not word or lib is None or ledger is None:
            return
        # Herkomst-check uit de library: alleen GSC + high_potential. Fail-closed bij ontbreken.
        evidence = (lib.status(word) or {}).get("evidence") or {}
        if evidence.get("source") != "gsc" or evidence.get("bucket") != "high_potential":
            self.log.debug("kw-research: '%s' overgeslagen — geen gsc/high_potential-evidence", word)
            return
        # Merkqueries (nooch-varianten e.d.) blijven approved in de library (correct voor SEO), maar
        # spawnen géén onderzoeksproject → stil overslaan. Config-geschakeld; lege lijst = filter uit.
        branded = [t.strip() for t in
                   (self.context.settings.get("branded_tokens", self._BRANDED_DEFAULT) or "").lower().split(",")
                   if t.strip()]
        wl = word.lower()
        if any(t in wl for t in branded):
            self.log.debug("branded keyword overgeslagen: %s", word)
            return
        kw = word.lower()
        projects = ledger.all()
        # Dedup over ALLE statussen (ook DONE) op keyword-veld + origin.
        if any(p.get("origin") == self._KW_RESEARCH_ORIGIN and (p.get("keyword") or "").lower() == kw
               for p in projects):
            self.log.debug("kw-research: '%s' bestaat al — geen dubbel project", word)
            return
        # Plafond: max N OPEN (niet-DONE) keyword_research-projecten. Vol → niet aanmaken, geen wachtrij.
        limit = int(self.context.settings.get("keyword_research_open_limit", "5"))
        open_n = sum(1 for p in projects
                     if p.get("origin") == self._KW_RESEARCH_ORIGIN and p.get("status") != "done")
        if open_n >= limit:
            self.log.info("kw-research: plafond bereikt (%d/%d open) — '%s' niet aangemaakt", open_n, limit, word)
            return
        pid = ledger.create(self.id, self._KW_RESEARCH_SCOPE.format(kw=word), "role",
                            status="future", origin=self._KW_RESEARCH_ORIGIN, keyword=word)
        self.log.info("🔬 autonoom onderzoeksproject in TOEKOMST voor '%s' (pid=%s)", word, pid)

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
        llm_out = llm_reason(prompt, call_site="distill_assessment")
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
        out = llm_reason(prompt, call_site="distill_batch")
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
        if low.startswith("bevinding") and ":" in line:
            v = line.split(":", 1)[1].strip().strip("* ").strip()
            if v:
                findings.append(v)
        elif (low.startswith("vraag") or low.startswith("reflectievraag")
              or low.startswith("suggestie")) and ":" in line and not vraag:
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
            from nooch_village.scope_nudge import match_project_to_role
            roster = self._scope_roster(records)
            if not roster:
                return
            done = 0
            for p in projects.active():
                if done >= self._MAX_NUDGES_PER_PULSE:
                    break
                pid, owner = p.get("id"), p.get("owner")
                text = self._project_text(p)
                if not pid or not text:
                    continue
                cand = [r for r in roster if r["role_id"] != owner]     # niet de eigenaar nudgen
                m = match_project_to_role(text, cand, name=self.id)
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
            if done:
                self.log.info("🔔 Noochie nudgde %d scope-match(es) proactief", done)
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
            f"Je bent Noochie, de missiestem van Nooch.earth. Scherp, nuchter, en je kijkt naar "
            f"het GEHEEL: verkeer, markt, missie-afstemming, kansen en risico's.\n"
            f"Missie: {_NOOCHIE_MISSION}\n\n"
            f"Field Note van vandaag:\n{field_note}\n\n"
            "Regels:\n"
            "- Baseer je UITSLUITEND op wat in de Field Note staat. Verzin geen namen, partners "
            "of cijfers; weet je iets niet, schrijf het niet op.\n"
            "- Elke bevinding is ÉÉN volledige, bondige zin (max ~25 woorden). Geen halve zinnen.\n"
            "- Sluit af met één scherpe REFLECTIEVRAAG aan de oprichter die hem aan het denken zet "
            "(geen actie die hij waarschijnlijk al doet).\n\n"
            "Antwoord exact zo:\n"
            "BEVINDING: <één volledige zin>\n"
            "BEVINDING: <één volledige zin>\n"
            "BEVINDING: <één volledige zin>\n"
            "VRAAG: <één reflectievraag>\n"
            "VERDICT: ok\n"
            "REASON: <één zin>\n\n"
            "(gebruik VERDICT: niet_ok als de aanbevolen richting botst met of de missie mist)"
        )
        result = reason(prompt, call_site="noochie_weigh_in") or "(geen LLM beschikbaar)"
        verdict, reason_text = parse_verdict_reason(result, frozenset({"ok", "niet_ok"}))
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
        result = reason(prompt, call_site="noochie_reflect")
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
