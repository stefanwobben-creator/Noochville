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
| `/inbox` | `render_inbox` | `nooch_village/views/inbox.py` |
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
| `proj_add` | `cockpit2.py:1054` |
| `artefact_add` | `cockpit2.py:1082` |
| `artefact_edit` | `cockpit2.py:1123` |
| `artefact_archive` | `cockpit2.py:1147` |
| `proj_status` | `cockpit2.py:1167` |
| `proj_done` | `cockpit2.py:1185` |
| `proj_archive` | `cockpit2.py:1207` |
| `proj_unarchive` | `cockpit2.py:1217` |
| `proj_delete` | `cockpit2.py:1227` |
| `proj_edit` | `cockpit2.py:1254` |
| `proj_comment` | `cockpit2.py:1267` |
| `proj_rename` | `cockpit2.py:1277` |
| `proj_describe` | `cockpit2.py:1288` |
| `proj_doc_edit` | `cockpit2.py:1321` |
| `proj_regen_doc` | `cockpit2.py:1299` |
| `proj_settrekker` | `cockpit2.py:1334` |
| `proj_setowner` | `cockpit2.py:1371` |
| `proj_approve` | `cockpit2.py:1390` |
| `proj_discard` | `cockpit2.py:1401` |
| `proj_setlabel` | `cockpit2.py:1412` |
| `proj_setimpact` | `cockpit2.py:1427` |
| `proj_seteffort` | `cockpit2.py:1446` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1469` |
| `proj_setprivate` | `cockpit2.py:1493` |
| `proj_setdue` | `cockpit2.py:1504` |
| `attach_add` | `cockpit2.py:1515` |
| `attach_remove` | `cockpit2.py:1526` |
| `react_add` | `cockpit2.py:1536` |
| `feed_edit` | `cockpit2.py:1546` |
| `feed_remove` | `cockpit2.py:1556` |
| `wall_outcome` | `cockpit2.py:2149` |
| `notif_read` | `cockpit2.py:2247` |
| `notif_processed` | `cockpit2.py:2252` |
| `notif_outcome` | `cockpit2.py:2277` |
| `notif_klaar` | `cockpit2.py:2263` |
| `notif_delete` | `cockpit2.py:2257` |
| `notif_archive` | `cockpit2.py:2355` |
| `ai_reply` | `cockpit2.py:1565` |
| `proj_feed` | `cockpit2.py:1576` |
| `checklist_add` | `cockpit2.py:1606` |
| `checklist_remove` | `cockpit2.py:1617` |
| `check_add` | `cockpit2.py:1665` |
| `check_accept` | `cockpit2.py:1682` |
| `check_toggle` | `cockpit2.py:1692` |
| `check_remove` | `cockpit2.py:1702` |
| `role_assign` | `cockpit2.py:1712` |
| `role_unassign` | `cockpit2.py:1730` |
| `role_focus` | `cockpit2.py:1749` |
| `radar_approve` | `cockpit2.py:1782` |
| `radar_dismiss` | `cockpit2.py:1786` |
| `aitask_add` | `cockpit2.py:1790` |
| `aitask_remove` | `cockpit2.py:1816` |
| `persona_skill_add` | `cockpit2.py:1833` |
| `rov2_add` | `cockpit2.py:1848` |
| `rov2_add_to_group` | `cockpit2.py:1860` |
| `rov2_remove` | `cockpit2.py:1872` |
| `rov2_remove_group` | `cockpit2.py:1887` |
| `rov2_setkind` | `cockpit2.py:1905` |
| `rov2_consent` | `cockpit2.py:1918` |
| `rov2_end` | `cockpit2.py:1940` |
| `wo_open` | `cockpit2.py:1964` |
| `wo_close` | `cockpit2.py:1974` |
| `wo_presence` | `cockpit2.py:1990` |
| `wo_present_all` | `cockpit2.py:2001` |
| `wo_ag_add` | `cockpit2.py:2013` |
| `wo_ag_remove` | `cockpit2.py:2025` |
| `wo_ag_note` | `cockpit2.py:2035` |
| `wo_ag_reopen` | `cockpit2.py:2047` |
| `wo_ag_resolve` | `cockpit2.py:2123` |
| `wo_checkout` | `cockpit2.py:2360` |
| `noochie_send` | `cockpit2.py:2372` |
| `noochie_reset` | `cockpit2.py:2398` |
| `noochie_ctx` | `cockpit2.py:2405` |
| `cl_add` | `cockpit2.py:2412` |
| `cl_report` | `cockpit2.py:2430` |
| `cl_remove` | `cockpit2.py:2445` |
| `m_add_kpi` | `cockpit2.py:2455` |
| `m_add_from_def` | `cockpit2.py:2487` |
| `def_add` | `cockpit2.py:2502` |
| `catalog_publish` | `cockpit2.py:2524` |
| `def_amend` | `cockpit2.py:2550` |
| `m_add_link` | `cockpit2.py:2592` |
| `m_sample` | `cockpit2.py:2603` |
| `m_remove` | `cockpit2.py:2613` |
| `m_pin` | `cockpit2.py:2623` |
| `m_unpin` | `cockpit2.py:2634` |
| `tile_add` | `cockpit2.py:2672` |
| `indicator_activate` | `cockpit2.py:2644` |
| `tile_remove` | `cockpit2.py:2706` |
| `rov2_set` | `cockpit2.py:2716` |
| `rov2_acc_add` | `cockpit2.py:2716` |
| `rov2_acc_remove` | `cockpit2.py:2716` |
| `rov2_dom_add` | `cockpit2.py:2716` |
| `rov2_dom_remove` | `cockpit2.py:2716` |
| `backlog_add` | `cockpit2.py:2748` |
| `backlog_update_staat` | `cockpit2.py:2760` |
| `backlog_update_prioriteit` | `cockpit2.py:2772` |
| `person_edit` | `cockpit2.py:2784` |
| `person_remove` | `cockpit2.py:2801` |
| `lk_mute` | `cockpit2.py:2822` |


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
_29 routes · 100 dispatch-acties · 22 stores._
