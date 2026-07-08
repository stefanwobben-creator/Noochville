# Codebase-staat — losse eindjes (2026-07-08)

Read-only inventarisatie (code + docs). Vier categorieën, meest-relevant eerst. Géén wijzigingen.

---

## 1. ONAF — begonnen, niet voltooid

| bestand:regel | wat | waarom ONAF |
|---|---|---|
| `roles.py:1664-1690` | `advise_metrics` = hardcoded dict `_METRIC_ADVICE`; `# TODO: vervang later door een LLM-stap die strategy/goals meeleest`. `context` binnengehaald maar bewust ongebruikt. | STATE.md noemt dit "de enige echte functionele stub in productie". |
| `inhabitant.py:849-855` | `run_project` default → retourneert vaste marker `"stub:done"`. Enige override (`roles.py:433-437`) handelt **alleen** `scope.kind=="discovery"` af. | Élk niet-discovery project valt terug op de stub → project-executie is grotendeels een no-op. |
| `backfill.py:45-51, 82-85` | Fase-1-guard: `raise BackfillError("… alleen daily-frequentie (fase 1); … komt later")`. | Weekly (maandagen) + monthly (1e v.d. maand) = bewuste seam, nog niet gebouwd. |
| `attachments.py:21` | `TODO: later scope_tags: list[str] toevoegen voor querybare scope.` | Kleine geplande uitbreiding. |
| docs `STATE.md:282+` | "Openstaande ontwerpschuld": werkoverleg-metrics zonder SSOT (catalog 6 vs pulldown 9, 4 gedrifte plekken); "Brok 11 — dispatch splitsen (uitgesteld)"; **werkoverleg geen automatische trigger** (`WerkoverlegStore.open()` alleen via HTTP-klik). | Ontwerpschuld benoemd, niet in code. |
| docs `ONTWERP_projecten_metrics.md:174`, `ONTWERP_execution_contract.md:54/89`, `ontwerp_governance_ritueel.md:3`, `ontwerp_kennislaag.md:3`, `ONTWERP_backlog_builder.md:60`, `ONTWERP_prikbord_kanban.md:3`, `ONTWERP_poc_glassfrog.md:28/92`, `CHECKLIST_glassfrog_schermen.md:82` | Diverse "nog te bouwen" / "concept, niet geïmplementeerd" (o.a. gap-judgment role-birth C-cases, means-gap reject-lifecycle, skill-rol-koppeling, glassfrog Notes/Metrics/Checklists-UI). | Ontwerp beschreven, code (deels) afwezig. |

## 2. SLAPEND — gebouwd + correct, nooit gevoed/geactiveerd

| bestand:regel | wat | waarom SLAPEND |
|---|---|---|
| `monitoring.py` + `roles.py:124` | MonitoringStore, gevuld via `_on_advice_ready` (keep-verdicts). | Wacht op de eerste project-advies→keep-flow. (ijkpunt, bevestigd.) |
| `werkoverleg.py:169` → `observations.py:264` | `werk_tevredenheid_day`-live-pad (check-out 0-10 → snapshot). | Wacht op een echte check-out-score; **structureel** ook geen auto-trigger voor het overleg (zie STATE.md). 1 historisch punt via inhaal. |
| `village.py:129/133/146` + `meetcatalog.py:43-45` | gdelt / shopify / semanticscholar geregistreerd maar `inactive`. | Bewust uit (rate-limit / geen creds / monthly te grof). Uit ≠ kapot. |
| `skills_impl/shopify_sales.py:205-297` | Stub-modus (`_stub_result`, `shopify_stub`/`payload["stub"]`) draait alleen zonder live token + expliciete aanvraag. | In de normale flow nooit geactiveerd. |
| `village.py:133` (+ `skills_impl/trends_categorie.py:43`) | `trends_categorie` geregistreerd; **in Scope 1 (sluitpakket) gedeactiveerd** + reeksen opgeruimd. | Nu bewust uit. Skill-code blijft (deactiveren ≠ verwijderen). |

## 3. STUK — zou moeten werken maar faalt/levert niets

| bestand:regel | wat | waarom STUK |
|---|---|---|
| ~~`cli.py:248` (`ask_accountability`)~~ **[OPGELOST 2026-07-08]** | Abonneerde op `accountability_check_completed` dat nergens werd gepubliceerd. **Fix:** `_on_accountability_requested` publiceert dat event nu generiek na élke aangeboden accountability (met het handler-resultaat). De offer→complete-lus is nu compleet. | ~~Voor élke andere accountability nooit een completion.~~ Opgelost: elke aangeboden accountability meldt nu af. |
| `governance.py:309` | `_on_legacy_amendment` luistert op **`propose_amendment`** ("legacy/backward compat"); dat event wordt nergens meer gepubliceerd. | Dode luister-tak — vuurt nooit. |
| `cli.py:186-192` | Insight-migratie: `classify()` in `except Exception: pass` → stille val naar "niet-geclassificeerd". | Milde stille slikker (eenmalig migratiepad, verbergt een LLM-fout). |
| `tests/test_project_feed.py:80` | `@pytest.mark.xfail("notificatie-aggregatie op /person is deferred; person-view is read-only placeholder")`. | Uitgezette test = deferred feature (overlapt met de /person-xfail in ONAF/roadmap). |
| `tests/test_util.py:48` | `pytest.skip("proces kan altijd lezen (root)")`. | Benigne, omgevingsafhankelijk — geen echte breuk. |

*Positief: Trends anker-ratio (het vroegere STUK-voorbeeld) is gefixt; de andere `except: pass`-plekken
(`roles.py:208`, `trends.py:345`, `keyword_scheduler.py:34`, `noochie.py:30`) zijn state/config-fallbacks,
geen fout-verbergers.*

## 4. DOOD — bestaat nog, nergens (functioneel) gebruikt

| bestand:regel | wat | waarom DOOD |
|---|---|---|
| `skills_impl/stooq.py` (`StooqIndexSkill`) | Vervangen door AlphaVantage (Stooq zat achter een JS-challenge). Nog geïnstantieerd in `village.py:132` ("gedeactiveerd"), maar `SOURCE="stooq"` staat **niet** in de meetcatalogus en `stooq_symbols` wordt nergens geconfigureerd. | Verwijderde-feature-rest die alleen nog in de registry hangt. |

*False-positive-checks (bewust NIET dood): **Serpstat** — geen enkele referentie meer (volledig weg).
**Trends anker-ratio** — doc markeert het expliciet als "verworpen ontwerp". **OpenAlex `/concepts`-aggregaat**
— in code vervangen door de `works?filter=…`-flow (`openalex.py:118/175`, `kind="flux"`); doc gemarkeerd.
Config-sleutels `trends_anchor`/`trends_terms`/`openalex_dimension_max`/`openalex_query` — 0 reads én weg uit
settings.ini. `deadsource.py`, `arch_map.py`, `snake.py` e.a. — aantoonbaar aangeroepen, niet dood.*

---

## Prioriteringssuggestie

**Blokkeert een feature (fixen levert iets op):**
1. `cli.py:248` **ask_accountability** — de generieke accountability offer→complete-lus is half af (alleen `nl_corpus_coverage` werkt); élke andere accountability hangt. Blokkeert de accountability-check als algemeen mechanisme.
2. `inhabitant.py:849` **run_project** — niet-discovery projecten zijn no-ops (`stub:done`). Blokkeert echte project-executie; de projecten-laag doet nu weinig.
3. **werkoverleg auto-trigger** (STATE.md) + `werk_tevredenheid` — zonder trigger/ingevulde check-out blijft de tevredenheidsreeks structureel leeg (nu 1 inhaal-punt). Klein maar concreet.
4. `roles.py:1667` **advise_metrics → LLM** — de keep/skip-curatie is nu een hardcoded 4-metric-dict; de hele MonitoringStore-lus hangt hierachter. Upgrade ontsluit de reference-consumptie.

**Puur opruiming (geen functionele impact, veilig weg):**
5. `skills_impl/stooq.py` + de registratie in `village.py:132` — dode index-skill-rest verwijderen.
6. `governance.py:309` **`propose_amendment`** legacy-handler — dode luister-tak verwijderen.
7. Docs-hygiëne: de vele `ONTWERP_*.md`/`STATE.md`-openstaande-punten consolideren in één roadmap i.p.v. verspreid.

**Bewust laten (geen actie):** gdelt/shopify/semanticscholar (gelabeld inactief), shopify-stub, trends_categorie (Scope 1 uit), backfill fase-1-guard (seam met duidelijke error).
