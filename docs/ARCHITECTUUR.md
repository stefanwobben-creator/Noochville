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
| `proj_add` | `cockpit2.py:950` |
| `artefact_add` | `cockpit2.py:978` |
| `artefact_edit` | `cockpit2.py:1019` |
| `artefact_archive` | `cockpit2.py:1043` |
| `proj_status` | `cockpit2.py:1063` |
| `proj_done` | `cockpit2.py:1081` |
| `proj_archive` | `cockpit2.py:1103` |
| `proj_unarchive` | `cockpit2.py:1113` |
| `proj_delete` | `cockpit2.py:1123` |
| `proj_edit` | `cockpit2.py:1150` |
| `proj_comment` | `cockpit2.py:1163` |
| `proj_rename` | `cockpit2.py:1173` |
| `proj_describe` | `cockpit2.py:1184` |
| `proj_doc_edit` | `cockpit2.py:1217` |
| `proj_regen_doc` | `cockpit2.py:1195` |
| `proj_settrekker` | `cockpit2.py:1230` |
| `proj_setowner` | `cockpit2.py:1267` |
| `proj_approve` | `cockpit2.py:1286` |
| `proj_discard` | `cockpit2.py:1297` |
| `proj_setlabel` | `cockpit2.py:1308` |
| `proj_setimpact` | `cockpit2.py:1323` |
| `proj_seteffort` | `cockpit2.py:1342` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1365` |
| `proj_setprivate` | `cockpit2.py:1389` |
| `proj_setdue` | `cockpit2.py:1400` |
| `attach_add` | `cockpit2.py:1411` |
| `attach_remove` | `cockpit2.py:1422` |
| `react_add` | `cockpit2.py:1432` |
| `feed_edit` | `cockpit2.py:1442` |
| `feed_remove` | `cockpit2.py:1452` |
| `wall_outcome` | `cockpit2.py:2045` |
| `mention_to_task` | `cockpit2.py:2141` |
| `notif_read` | `cockpit2.py:2187` |
| `notif_processed` | `cockpit2.py:2192` |
| `notif_archive` | `cockpit2.py:2197` |
| `ai_reply` | `cockpit2.py:1461` |
| `proj_feed` | `cockpit2.py:1472` |
| `checklist_add` | `cockpit2.py:1502` |
| `checklist_remove` | `cockpit2.py:1513` |
| `check_add` | `cockpit2.py:1561` |
| `check_accept` | `cockpit2.py:1578` |
| `check_toggle` | `cockpit2.py:1588` |
| `check_remove` | `cockpit2.py:1598` |
| `role_assign` | `cockpit2.py:1608` |
| `role_unassign` | `cockpit2.py:1626` |
| `role_focus` | `cockpit2.py:1645` |
| `radar_approve` | `cockpit2.py:1678` |
| `radar_dismiss` | `cockpit2.py:1682` |
| `aitask_add` | `cockpit2.py:1686` |
| `aitask_remove` | `cockpit2.py:1712` |
| `persona_skill_add` | `cockpit2.py:1729` |
| `rov2_add` | `cockpit2.py:1744` |
| `rov2_add_to_group` | `cockpit2.py:1756` |
| `rov2_remove` | `cockpit2.py:1768` |
| `rov2_remove_group` | `cockpit2.py:1783` |
| `rov2_setkind` | `cockpit2.py:1801` |
| `rov2_consent` | `cockpit2.py:1814` |
| `rov2_end` | `cockpit2.py:1836` |
| `wo_open` | `cockpit2.py:1860` |
| `wo_close` | `cockpit2.py:1870` |
| `wo_presence` | `cockpit2.py:1886` |
| `wo_present_all` | `cockpit2.py:1897` |
| `wo_ag_add` | `cockpit2.py:1909` |
| `wo_ag_remove` | `cockpit2.py:1921` |
| `wo_ag_note` | `cockpit2.py:1931` |
| `wo_ag_reopen` | `cockpit2.py:1943` |
| `wo_ag_resolve` | `cockpit2.py:2019` |
| `wo_checkout` | `cockpit2.py:2202` |
| `noochie_send` | `cockpit2.py:2214` |
| `noochie_reset` | `cockpit2.py:2240` |
| `noochie_ctx` | `cockpit2.py:2247` |
| `cl_add` | `cockpit2.py:2254` |
| `cl_report` | `cockpit2.py:2272` |
| `cl_remove` | `cockpit2.py:2287` |
| `m_add_kpi` | `cockpit2.py:2297` |
| `m_add_from_def` | `cockpit2.py:2329` |
| `def_add` | `cockpit2.py:2344` |
| `catalog_publish` | `cockpit2.py:2366` |
| `def_amend` | `cockpit2.py:2392` |
| `m_add_link` | `cockpit2.py:2434` |
| `m_sample` | `cockpit2.py:2445` |
| `m_remove` | `cockpit2.py:2455` |
| `m_pin` | `cockpit2.py:2465` |
| `m_unpin` | `cockpit2.py:2476` |
| `tile_add` | `cockpit2.py:2514` |
| `indicator_activate` | `cockpit2.py:2486` |
| `tile_remove` | `cockpit2.py:2548` |
| `rov2_set` | `cockpit2.py:2558` |
| `rov2_acc_add` | `cockpit2.py:2558` |
| `rov2_acc_remove` | `cockpit2.py:2558` |
| `rov2_dom_add` | `cockpit2.py:2558` |
| `rov2_dom_remove` | `cockpit2.py:2558` |
| `backlog_add` | `cockpit2.py:2590` |
| `backlog_update_staat` | `cockpit2.py:2602` |
| `backlog_update_prioriteit` | `cockpit2.py:2614` |
| `person_edit` | `cockpit2.py:2626` |
| `person_remove` | `cockpit2.py:2643` |
| `lk_mute` | `cockpit2.py:2664` |


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
_28 routes · 98 dispatch-acties · 22 stores._
