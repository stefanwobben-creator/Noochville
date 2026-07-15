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
| `proj_add` | `cockpit2.py:1077` |
| `artefact_add` | `cockpit2.py:1105` |
| `artefact_edit` | `cockpit2.py:1146` |
| `artefact_archive` | `cockpit2.py:1170` |
| `proj_status` | `cockpit2.py:1190` |
| `proj_done` | `cockpit2.py:1208` |
| `proj_archive` | `cockpit2.py:1230` |
| `proj_unarchive` | `cockpit2.py:1240` |
| `proj_delete` | `cockpit2.py:1250` |
| `proj_edit` | `cockpit2.py:1277` |
| `proj_comment` | `cockpit2.py:1290` |
| `proj_rename` | `cockpit2.py:1300` |
| `proj_describe` | `cockpit2.py:1311` |
| `proj_doc_edit` | `cockpit2.py:1344` |
| `proj_regen_doc` | `cockpit2.py:1322` |
| `proj_settrekker` | `cockpit2.py:1357` |
| `proj_setowner` | `cockpit2.py:1394` |
| `proj_approve` | `cockpit2.py:1413` |
| `proj_discard` | `cockpit2.py:1424` |
| `proj_setlabel` | `cockpit2.py:1435` |
| `proj_setimpact` | `cockpit2.py:1450` |
| `proj_seteffort` | `cockpit2.py:1469` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1492` |
| `proj_setprivate` | `cockpit2.py:1516` |
| `proj_setdue` | `cockpit2.py:1527` |
| `attach_add` | `cockpit2.py:1538` |
| `attach_remove` | `cockpit2.py:1549` |
| `react_add` | `cockpit2.py:1559` |
| `feed_edit` | `cockpit2.py:1569` |
| `feed_remove` | `cockpit2.py:1579` |
| `wall_outcome` | `cockpit2.py:2172` |
| `notif_read` | `cockpit2.py:2270` |
| `notif_processed` | `cockpit2.py:2275` |
| `notif_outcome` | `cockpit2.py:2384` |
| `notif_klaar` | `cockpit2.py:2370` |
| `notif_delete` | `cockpit2.py:2280` |
| `notif_add` | `cockpit2.py:2354` |
| `notif_archive` | `cockpit2.py:2471` |
| `metrics2_fav` | `cockpit2.py:2286` |
| `metrics2_unfav` | `cockpit2.py:2296` |
| `metrics2_form` | `cockpit2.py:2301` |
| `metrics2_dim` | `cockpit2.py:2307` |
| `metrics2_compare` | `cockpit2.py:2314` |
| `metrics2_formula` | `cockpit2.py:2339` |
| `source_activate` | `cockpit2.py:2322` |
| `source_deactivate` | `cockpit2.py:2331` |
| `ai_reply` | `cockpit2.py:1588` |
| `proj_feed` | `cockpit2.py:1599` |
| `checklist_add` | `cockpit2.py:1629` |
| `checklist_remove` | `cockpit2.py:1640` |
| `check_add` | `cockpit2.py:1688` |
| `check_accept` | `cockpit2.py:1705` |
| `check_toggle` | `cockpit2.py:1715` |
| `check_remove` | `cockpit2.py:1725` |
| `role_assign` | `cockpit2.py:1735` |
| `role_unassign` | `cockpit2.py:1753` |
| `role_focus` | `cockpit2.py:1772` |
| `radar_approve` | `cockpit2.py:1805` |
| `radar_dismiss` | `cockpit2.py:1809` |
| `aitask_add` | `cockpit2.py:1813` |
| `aitask_remove` | `cockpit2.py:1839` |
| `persona_skill_add` | `cockpit2.py:1856` |
| `rov2_add` | `cockpit2.py:1871` |
| `rov2_add_to_group` | `cockpit2.py:1883` |
| `rov2_remove` | `cockpit2.py:1895` |
| `rov2_remove_group` | `cockpit2.py:1910` |
| `rov2_setkind` | `cockpit2.py:1928` |
| `rov2_consent` | `cockpit2.py:1941` |
| `rov2_end` | `cockpit2.py:1963` |
| `wo_open` | `cockpit2.py:1987` |
| `wo_close` | `cockpit2.py:1997` |
| `wo_presence` | `cockpit2.py:2013` |
| `wo_present_all` | `cockpit2.py:2024` |
| `wo_ag_add` | `cockpit2.py:2036` |
| `wo_ag_remove` | `cockpit2.py:2048` |
| `wo_ag_note` | `cockpit2.py:2058` |
| `wo_ag_reopen` | `cockpit2.py:2070` |
| `wo_ag_resolve` | `cockpit2.py:2146` |
| `wo_checkout` | `cockpit2.py:2476` |
| `noochie_send` | `cockpit2.py:2488` |
| `noochie_reset` | `cockpit2.py:2514` |
| `noochie_ctx` | `cockpit2.py:2521` |
| `cl_add` | `cockpit2.py:2528` |
| `cl_report` | `cockpit2.py:2546` |
| `cl_remove` | `cockpit2.py:2561` |
| `m_add_kpi` | `cockpit2.py:2571` |
| `m_add_from_def` | `cockpit2.py:2603` |
| `def_add` | `cockpit2.py:2618` |
| `catalog_publish` | `cockpit2.py:2640` |
| `def_amend` | `cockpit2.py:2666` |
| `m_add_link` | `cockpit2.py:2708` |
| `m_sample` | `cockpit2.py:2719` |
| `m_remove` | `cockpit2.py:2729` |
| `m_pin` | `cockpit2.py:2739` |
| `m_unpin` | `cockpit2.py:2750` |
| `tile_add` | `cockpit2.py:2788` |
| `indicator_activate` | `cockpit2.py:2760` |
| `tile_remove` | `cockpit2.py:2822` |
| `rov2_set` | `cockpit2.py:2832` |
| `rov2_acc_add` | `cockpit2.py:2832` |
| `rov2_acc_remove` | `cockpit2.py:2832` |
| `rov2_dom_add` | `cockpit2.py:2832` |
| `rov2_dom_remove` | `cockpit2.py:2832` |
| `backlog_add` | `cockpit2.py:2864` |
| `backlog_update_staat` | `cockpit2.py:2876` |
| `backlog_update_prioriteit` | `cockpit2.py:2888` |
| `person_edit` | `cockpit2.py:2900` |
| `person_remove` | `cockpit2.py:2917` |
| `lk_mute` | `cockpit2.py:2938` |


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
_31 routes · 109 dispatch-acties · 22 stores._
