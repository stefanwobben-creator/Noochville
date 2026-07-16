# NoochVille — Architectuur-vindkaart

> **Automatisch gegenereerd** door `nooch_village/arch_map.py`. NIET handmatig bewerken —
> draai `python -m nooch_village.arch_map` en commit. De guard-test
> `tests/test_architectuur.py` faalt zodra dit bestand verouderd is (nieuwe route/actie/store
> zonder regenereren). Zie de regel hierover in `CLAUDE.md`.

## (a) Route → handler → view

De GET-routes uit `do_GET` (cockpit2.py) en de view die ze renderen. `(inline)` = geen aparte `render_*`, de response wordt in cockpit2 zelf opgebouwd.

| Route | Handler | View-bestand |
|---|---|---|
| `/login` | `(inline)` | `cockpit2.py` |
| `/logout` | `(inline)` | `cockpit2.py` |
| `/wachtwoord` | `(inline)` | `cockpit2.py` |
| `/snake` | `render_snake_page` | `nooch_village/snake.py` |
| `/context` | `(inline)` | `cockpit2.py` |
| `/epic/frame` | `(inline)` | `cockpit2.py` |
| `/` | `(inline)` | `cockpit2.py` |
| `/index.html` | `(inline)` | `cockpit2.py` |
| `/node` | `render_node` | `nooch_village/views/overview.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/inzichten` | `render_kennislaag` | `nooch_village/views/kennislaag.py` |
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
| `/woordenschat` | `render_woordenschat` | `nooch_village/views/woordenschat.py` |
| `/belofte` | `render_belofte` | `nooch_village/views/belofte.py` |
| `/metrics2` | `render_metrics2` | `nooch_village/views/metrics2.py` |
| `/inbox/verwerk` | `render_verwerk` | `nooch_village/views/inbox.py` |
| `/catalog` | `render_catalog` | `nooch_village/views/catalog.py` |
| `/catalogus_koppelen` | `(inline)` | `cockpit2.py` |
| `/kpi_new` | `render_kpi_composer` | `nooch_village/views/metrics.py` |
| `/noochie` | `render_noochie` | `nooch_village/views/noochie.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/livekit-presence` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:1086` |
| `artefact_add` | `cockpit2.py:1114` |
| `artefact_edit` | `cockpit2.py:1155` |
| `artefact_archive` | `cockpit2.py:1179` |
| `proj_status` | `cockpit2.py:1199` |
| `proj_done` | `cockpit2.py:1217` |
| `proj_archive` | `cockpit2.py:1239` |
| `proj_unarchive` | `cockpit2.py:1249` |
| `proj_delete` | `cockpit2.py:1259` |
| `proj_edit` | `cockpit2.py:1286` |
| `proj_comment` | `cockpit2.py:1299` |
| `proj_rename` | `cockpit2.py:1309` |
| `proj_describe` | `cockpit2.py:1320` |
| `proj_doc_edit` | `cockpit2.py:1353` |
| `proj_regen_doc` | `cockpit2.py:1331` |
| `proj_settrekker` | `cockpit2.py:1366` |
| `proj_setowner` | `cockpit2.py:1403` |
| `proj_approve` | `cockpit2.py:1422` |
| `proj_discard` | `cockpit2.py:1433` |
| `proj_setlabel` | `cockpit2.py:1444` |
| `proj_setimpact` | `cockpit2.py:1459` |
| `proj_seteffort` | `cockpit2.py:1478` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1501` |
| `proj_setprivate` | `cockpit2.py:1525` |
| `proj_setdue` | `cockpit2.py:1536` |
| `attach_add` | `cockpit2.py:1547` |
| `attach_remove` | `cockpit2.py:1558` |
| `react_add` | `cockpit2.py:1568` |
| `feed_edit` | `cockpit2.py:1578` |
| `feed_remove` | `cockpit2.py:1588` |
| `wall_outcome` | `cockpit2.py:2181` |
| `notif_read` | `cockpit2.py:2279` |
| `notif_processed` | `cockpit2.py:2284` |
| `notif_outcome` | `cockpit2.py:2431` |
| `notif_klaar` | `cockpit2.py:2417` |
| `notif_delete` | `cockpit2.py:2289` |
| `notif_add` | `cockpit2.py:2401` |
| `notif_archive` | `cockpit2.py:2518` |
| `metrics2_fav` | `cockpit2.py:2295` |
| `metrics2_unfav` | `cockpit2.py:2305` |
| `metrics2_form` | `cockpit2.py:2310` |
| `metrics2_dim` | `cockpit2.py:2316` |
| `metrics2_compare` | `cockpit2.py:2323` |
| `metrics2_formula` | `cockpit2.py:2386` |
| `source_activate` | `cockpit2.py:2369` |
| `source_deactivate` | `cockpit2.py:2378` |
| `link_pursue` | `cockpit2.py:2350` |
| `link_ignore` | `cockpit2.py:2360` |
| `acc_check` | `cockpit2.py:2331` |
| `ai_reply` | `cockpit2.py:1597` |
| `proj_feed` | `cockpit2.py:1608` |
| `checklist_add` | `cockpit2.py:1638` |
| `checklist_remove` | `cockpit2.py:1649` |
| `check_add` | `cockpit2.py:1697` |
| `check_accept` | `cockpit2.py:1714` |
| `check_toggle` | `cockpit2.py:1724` |
| `check_remove` | `cockpit2.py:1734` |
| `role_assign` | `cockpit2.py:1744` |
| `role_unassign` | `cockpit2.py:1762` |
| `role_focus` | `cockpit2.py:1781` |
| `radar_approve` | `cockpit2.py:1814` |
| `radar_dismiss` | `cockpit2.py:1818` |
| `aitask_add` | `cockpit2.py:1822` |
| `aitask_remove` | `cockpit2.py:1848` |
| `persona_skill_add` | `cockpit2.py:1865` |
| `rov2_add` | `cockpit2.py:1880` |
| `rov2_add_to_group` | `cockpit2.py:1892` |
| `rov2_remove` | `cockpit2.py:1904` |
| `rov2_remove_group` | `cockpit2.py:1919` |
| `rov2_setkind` | `cockpit2.py:1937` |
| `rov2_consent` | `cockpit2.py:1950` |
| `rov2_end` | `cockpit2.py:1972` |
| `wo_open` | `cockpit2.py:1996` |
| `wo_close` | `cockpit2.py:2006` |
| `wo_presence` | `cockpit2.py:2022` |
| `wo_present_all` | `cockpit2.py:2033` |
| `wo_ag_add` | `cockpit2.py:2045` |
| `wo_ag_remove` | `cockpit2.py:2057` |
| `wo_ag_note` | `cockpit2.py:2067` |
| `wo_ag_reopen` | `cockpit2.py:2079` |
| `wo_ag_resolve` | `cockpit2.py:2155` |
| `wo_checkout` | `cockpit2.py:2523` |
| `noochie_send` | `cockpit2.py:2535` |
| `noochie_reset` | `cockpit2.py:2561` |
| `noochie_ctx` | `cockpit2.py:2568` |
| `cl_add` | `cockpit2.py:2575` |
| `cl_report` | `cockpit2.py:2593` |
| `cl_remove` | `cockpit2.py:2608` |
| `m_add_kpi` | `cockpit2.py:2618` |
| `m_add_from_def` | `cockpit2.py:2650` |
| `def_add` | `cockpit2.py:2665` |
| `catalog_publish` | `cockpit2.py:2687` |
| `def_amend` | `cockpit2.py:2713` |
| `m_add_link` | `cockpit2.py:2755` |
| `m_sample` | `cockpit2.py:2766` |
| `m_remove` | `cockpit2.py:2776` |
| `m_pin` | `cockpit2.py:2786` |
| `m_unpin` | `cockpit2.py:2797` |
| `tile_add` | `cockpit2.py:2835` |
| `indicator_activate` | `cockpit2.py:2807` |
| `tile_remove` | `cockpit2.py:2869` |
| `rov2_set` | `cockpit2.py:2879` |
| `rov2_acc_add` | `cockpit2.py:2879` |
| `rov2_acc_remove` | `cockpit2.py:2879` |
| `rov2_dom_add` | `cockpit2.py:2879` |
| `rov2_dom_remove` | `cockpit2.py:2879` |
| `backlog_add` | `cockpit2.py:2911` |
| `backlog_update_staat` | `cockpit2.py:2923` |
| `backlog_update_prioriteit` | `cockpit2.py:2935` |
| `person_edit` | `cockpit2.py:2947` |
| `person_remove` | `cockpit2.py:2964` |
| `lk_mute` | `cockpit2.py:2985` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `evidence` | `EvidenceLedger` | `evidence_ledger.jsonl` |
| `sources` | `SourceStatusStore` | `sources.json` |
| `personas` | `PersonaStore` | `personas.json` |
| `projects` | `ProjectLedger` | `projects.json` |
| `deliverables` | `DeliverableStore` | `deliverables.json` |
| `ai` | `AITaskStore` | `ai_tasks.json` |
| `match` | `ai_match.MatchCache` | `ai_match_cache.json` |
| `notif` | `NotifStore` | `notifications.json` |
| `agenda` | `Agenda` | `roloverleg_agenda.json` |
| `noochie` | `NoochieStore` | `noochie.json` |
| `checklists` | `ChecklistStore` | `checklists.json` |
| `metrics` | `MetricStore` | `metrics.json` |
| `defs` | `DefinitionStore` | `definitions.json` |
| `werk` | `WerkoverlegStore` | `werkoverleg.json` |
| `strategies` | `StrategyStore` | `strategies.json` |
| `backlog` | `BacklogStore` | `backlog.json` |
| `radar` | `RadarStore` | `radar.json` |


---
_36 routes · 112 dispatch-acties · 22 stores._
