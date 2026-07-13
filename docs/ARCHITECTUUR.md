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
| `proj_add` | `cockpit2.py:805` |
| `artefact_add` | `cockpit2.py:833` |
| `artefact_edit` | `cockpit2.py:874` |
| `artefact_archive` | `cockpit2.py:898` |
| `proj_status` | `cockpit2.py:918` |
| `proj_done` | `cockpit2.py:936` |
| `proj_archive` | `cockpit2.py:958` |
| `proj_unarchive` | `cockpit2.py:968` |
| `proj_delete` | `cockpit2.py:978` |
| `proj_edit` | `cockpit2.py:1005` |
| `proj_comment` | `cockpit2.py:1018` |
| `proj_rename` | `cockpit2.py:1028` |
| `proj_describe` | `cockpit2.py:1039` |
| `proj_doc_edit` | `cockpit2.py:1072` |
| `proj_regen_doc` | `cockpit2.py:1050` |
| `proj_settrekker` | `cockpit2.py:1085` |
| `proj_setowner` | `cockpit2.py:1122` |
| `proj_approve` | `cockpit2.py:1141` |
| `proj_discard` | `cockpit2.py:1152` |
| `proj_setlabel` | `cockpit2.py:1163` |
| `proj_setimpact` | `cockpit2.py:1178` |
| `proj_seteffort` | `cockpit2.py:1197` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1220` |
| `proj_setprivate` | `cockpit2.py:1244` |
| `proj_setdue` | `cockpit2.py:1255` |
| `attach_add` | `cockpit2.py:1266` |
| `attach_remove` | `cockpit2.py:1277` |
| `react_add` | `cockpit2.py:1287` |
| `feed_edit` | `cockpit2.py:1297` |
| `feed_remove` | `cockpit2.py:1307` |
| `wall_outcome` | `cockpit2.py:1900` |
| `ai_reply` | `cockpit2.py:1316` |
| `proj_feed` | `cockpit2.py:1327` |
| `checklist_add` | `cockpit2.py:1357` |
| `checklist_remove` | `cockpit2.py:1368` |
| `check_add` | `cockpit2.py:1416` |
| `check_accept` | `cockpit2.py:1433` |
| `check_toggle` | `cockpit2.py:1443` |
| `check_remove` | `cockpit2.py:1453` |
| `role_assign` | `cockpit2.py:1463` |
| `role_unassign` | `cockpit2.py:1481` |
| `role_focus` | `cockpit2.py:1500` |
| `radar_approve` | `cockpit2.py:1533` |
| `radar_dismiss` | `cockpit2.py:1537` |
| `aitask_add` | `cockpit2.py:1541` |
| `aitask_remove` | `cockpit2.py:1567` |
| `persona_skill_add` | `cockpit2.py:1584` |
| `rov2_add` | `cockpit2.py:1599` |
| `rov2_add_to_group` | `cockpit2.py:1611` |
| `rov2_remove` | `cockpit2.py:1623` |
| `rov2_remove_group` | `cockpit2.py:1638` |
| `rov2_setkind` | `cockpit2.py:1656` |
| `rov2_consent` | `cockpit2.py:1669` |
| `rov2_end` | `cockpit2.py:1691` |
| `wo_open` | `cockpit2.py:1715` |
| `wo_close` | `cockpit2.py:1725` |
| `wo_presence` | `cockpit2.py:1741` |
| `wo_present_all` | `cockpit2.py:1752` |
| `wo_ag_add` | `cockpit2.py:1764` |
| `wo_ag_remove` | `cockpit2.py:1776` |
| `wo_ag_note` | `cockpit2.py:1786` |
| `wo_ag_reopen` | `cockpit2.py:1798` |
| `wo_ag_resolve` | `cockpit2.py:1874` |
| `wo_checkout` | `cockpit2.py:1996` |
| `noochie_send` | `cockpit2.py:2008` |
| `noochie_reset` | `cockpit2.py:2034` |
| `noochie_ctx` | `cockpit2.py:2041` |
| `cl_add` | `cockpit2.py:2048` |
| `cl_report` | `cockpit2.py:2066` |
| `cl_remove` | `cockpit2.py:2081` |
| `m_add_kpi` | `cockpit2.py:2091` |
| `m_add_from_def` | `cockpit2.py:2123` |
| `def_add` | `cockpit2.py:2138` |
| `catalog_publish` | `cockpit2.py:2160` |
| `def_amend` | `cockpit2.py:2186` |
| `m_add_link` | `cockpit2.py:2228` |
| `m_sample` | `cockpit2.py:2239` |
| `m_remove` | `cockpit2.py:2249` |
| `m_pin` | `cockpit2.py:2259` |
| `m_unpin` | `cockpit2.py:2270` |
| `tile_add` | `cockpit2.py:2308` |
| `indicator_activate` | `cockpit2.py:2280` |
| `tile_remove` | `cockpit2.py:2342` |
| `rov2_set` | `cockpit2.py:2352` |
| `rov2_acc_add` | `cockpit2.py:2352` |
| `rov2_acc_remove` | `cockpit2.py:2352` |
| `rov2_dom_add` | `cockpit2.py:2352` |
| `rov2_dom_remove` | `cockpit2.py:2352` |
| `backlog_add` | `cockpit2.py:2384` |
| `backlog_update_staat` | `cockpit2.py:2396` |
| `backlog_update_prioriteit` | `cockpit2.py:2408` |
| `person_edit` | `cockpit2.py:2420` |
| `person_remove` | `cockpit2.py:2437` |
| `lk_mute` | `cockpit2.py:2458` |


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
_27 routes · 94 dispatch-acties · 22 stores._
