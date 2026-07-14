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
| `proj_add` | `cockpit2.py:927` |
| `artefact_add` | `cockpit2.py:955` |
| `artefact_edit` | `cockpit2.py:996` |
| `artefact_archive` | `cockpit2.py:1020` |
| `proj_status` | `cockpit2.py:1040` |
| `proj_done` | `cockpit2.py:1058` |
| `proj_archive` | `cockpit2.py:1080` |
| `proj_unarchive` | `cockpit2.py:1090` |
| `proj_delete` | `cockpit2.py:1100` |
| `proj_edit` | `cockpit2.py:1127` |
| `proj_comment` | `cockpit2.py:1140` |
| `proj_rename` | `cockpit2.py:1150` |
| `proj_describe` | `cockpit2.py:1161` |
| `proj_doc_edit` | `cockpit2.py:1194` |
| `proj_regen_doc` | `cockpit2.py:1172` |
| `proj_settrekker` | `cockpit2.py:1207` |
| `proj_setowner` | `cockpit2.py:1244` |
| `proj_approve` | `cockpit2.py:1263` |
| `proj_discard` | `cockpit2.py:1274` |
| `proj_setlabel` | `cockpit2.py:1285` |
| `proj_setimpact` | `cockpit2.py:1300` |
| `proj_seteffort` | `cockpit2.py:1319` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1342` |
| `proj_setprivate` | `cockpit2.py:1366` |
| `proj_setdue` | `cockpit2.py:1377` |
| `attach_add` | `cockpit2.py:1388` |
| `attach_remove` | `cockpit2.py:1399` |
| `react_add` | `cockpit2.py:1409` |
| `feed_edit` | `cockpit2.py:1419` |
| `feed_remove` | `cockpit2.py:1429` |
| `wall_outcome` | `cockpit2.py:2022` |
| `mention_to_task` | `cockpit2.py:2118` |
| `ai_reply` | `cockpit2.py:1438` |
| `proj_feed` | `cockpit2.py:1449` |
| `checklist_add` | `cockpit2.py:1479` |
| `checklist_remove` | `cockpit2.py:1490` |
| `check_add` | `cockpit2.py:1538` |
| `check_accept` | `cockpit2.py:1555` |
| `check_toggle` | `cockpit2.py:1565` |
| `check_remove` | `cockpit2.py:1575` |
| `role_assign` | `cockpit2.py:1585` |
| `role_unassign` | `cockpit2.py:1603` |
| `role_focus` | `cockpit2.py:1622` |
| `radar_approve` | `cockpit2.py:1655` |
| `radar_dismiss` | `cockpit2.py:1659` |
| `aitask_add` | `cockpit2.py:1663` |
| `aitask_remove` | `cockpit2.py:1689` |
| `persona_skill_add` | `cockpit2.py:1706` |
| `rov2_add` | `cockpit2.py:1721` |
| `rov2_add_to_group` | `cockpit2.py:1733` |
| `rov2_remove` | `cockpit2.py:1745` |
| `rov2_remove_group` | `cockpit2.py:1760` |
| `rov2_setkind` | `cockpit2.py:1778` |
| `rov2_consent` | `cockpit2.py:1791` |
| `rov2_end` | `cockpit2.py:1813` |
| `wo_open` | `cockpit2.py:1837` |
| `wo_close` | `cockpit2.py:1847` |
| `wo_presence` | `cockpit2.py:1863` |
| `wo_present_all` | `cockpit2.py:1874` |
| `wo_ag_add` | `cockpit2.py:1886` |
| `wo_ag_remove` | `cockpit2.py:1898` |
| `wo_ag_note` | `cockpit2.py:1908` |
| `wo_ag_reopen` | `cockpit2.py:1920` |
| `wo_ag_resolve` | `cockpit2.py:1996` |
| `wo_checkout` | `cockpit2.py:2164` |
| `noochie_send` | `cockpit2.py:2176` |
| `noochie_reset` | `cockpit2.py:2202` |
| `noochie_ctx` | `cockpit2.py:2209` |
| `cl_add` | `cockpit2.py:2216` |
| `cl_report` | `cockpit2.py:2234` |
| `cl_remove` | `cockpit2.py:2249` |
| `m_add_kpi` | `cockpit2.py:2259` |
| `m_add_from_def` | `cockpit2.py:2291` |
| `def_add` | `cockpit2.py:2306` |
| `catalog_publish` | `cockpit2.py:2328` |
| `def_amend` | `cockpit2.py:2354` |
| `m_add_link` | `cockpit2.py:2396` |
| `m_sample` | `cockpit2.py:2407` |
| `m_remove` | `cockpit2.py:2417` |
| `m_pin` | `cockpit2.py:2427` |
| `m_unpin` | `cockpit2.py:2438` |
| `tile_add` | `cockpit2.py:2476` |
| `indicator_activate` | `cockpit2.py:2448` |
| `tile_remove` | `cockpit2.py:2510` |
| `rov2_set` | `cockpit2.py:2520` |
| `rov2_acc_add` | `cockpit2.py:2520` |
| `rov2_acc_remove` | `cockpit2.py:2520` |
| `rov2_dom_add` | `cockpit2.py:2520` |
| `rov2_dom_remove` | `cockpit2.py:2520` |
| `backlog_add` | `cockpit2.py:2552` |
| `backlog_update_staat` | `cockpit2.py:2564` |
| `backlog_update_prioriteit` | `cockpit2.py:2576` |
| `person_edit` | `cockpit2.py:2588` |
| `person_remove` | `cockpit2.py:2605` |
| `lk_mute` | `cockpit2.py:2626` |


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
_27 routes · 95 dispatch-acties · 22 stores._
