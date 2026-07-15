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
| `proj_add` | `cockpit2.py:1053` |
| `artefact_add` | `cockpit2.py:1081` |
| `artefact_edit` | `cockpit2.py:1122` |
| `artefact_archive` | `cockpit2.py:1146` |
| `proj_status` | `cockpit2.py:1166` |
| `proj_done` | `cockpit2.py:1184` |
| `proj_archive` | `cockpit2.py:1206` |
| `proj_unarchive` | `cockpit2.py:1216` |
| `proj_delete` | `cockpit2.py:1226` |
| `proj_edit` | `cockpit2.py:1253` |
| `proj_comment` | `cockpit2.py:1266` |
| `proj_rename` | `cockpit2.py:1276` |
| `proj_describe` | `cockpit2.py:1287` |
| `proj_doc_edit` | `cockpit2.py:1320` |
| `proj_regen_doc` | `cockpit2.py:1298` |
| `proj_settrekker` | `cockpit2.py:1333` |
| `proj_setowner` | `cockpit2.py:1370` |
| `proj_approve` | `cockpit2.py:1389` |
| `proj_discard` | `cockpit2.py:1400` |
| `proj_setlabel` | `cockpit2.py:1411` |
| `proj_setimpact` | `cockpit2.py:1426` |
| `proj_seteffort` | `cockpit2.py:1445` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1468` |
| `proj_setprivate` | `cockpit2.py:1492` |
| `proj_setdue` | `cockpit2.py:1503` |
| `attach_add` | `cockpit2.py:1514` |
| `attach_remove` | `cockpit2.py:1525` |
| `react_add` | `cockpit2.py:1535` |
| `feed_edit` | `cockpit2.py:1545` |
| `feed_remove` | `cockpit2.py:1555` |
| `wall_outcome` | `cockpit2.py:2148` |
| `notif_read` | `cockpit2.py:2249` |
| `notif_processed` | `cockpit2.py:2254` |
| `notif_done` | `cockpit2.py:2259` |
| `notif_archive` | `cockpit2.py:2266` |
| `ai_reply` | `cockpit2.py:1564` |
| `proj_feed` | `cockpit2.py:1575` |
| `checklist_add` | `cockpit2.py:1605` |
| `checklist_remove` | `cockpit2.py:1616` |
| `check_add` | `cockpit2.py:1664` |
| `check_accept` | `cockpit2.py:1681` |
| `check_toggle` | `cockpit2.py:1691` |
| `check_remove` | `cockpit2.py:1701` |
| `role_assign` | `cockpit2.py:1711` |
| `role_unassign` | `cockpit2.py:1729` |
| `role_focus` | `cockpit2.py:1748` |
| `radar_approve` | `cockpit2.py:1781` |
| `radar_dismiss` | `cockpit2.py:1785` |
| `aitask_add` | `cockpit2.py:1789` |
| `aitask_remove` | `cockpit2.py:1815` |
| `persona_skill_add` | `cockpit2.py:1832` |
| `rov2_add` | `cockpit2.py:1847` |
| `rov2_add_to_group` | `cockpit2.py:1859` |
| `rov2_remove` | `cockpit2.py:1871` |
| `rov2_remove_group` | `cockpit2.py:1886` |
| `rov2_setkind` | `cockpit2.py:1904` |
| `rov2_consent` | `cockpit2.py:1917` |
| `rov2_end` | `cockpit2.py:1939` |
| `wo_open` | `cockpit2.py:1963` |
| `wo_close` | `cockpit2.py:1973` |
| `wo_presence` | `cockpit2.py:1989` |
| `wo_present_all` | `cockpit2.py:2000` |
| `wo_ag_add` | `cockpit2.py:2012` |
| `wo_ag_remove` | `cockpit2.py:2024` |
| `wo_ag_note` | `cockpit2.py:2034` |
| `wo_ag_reopen` | `cockpit2.py:2046` |
| `wo_ag_resolve` | `cockpit2.py:2122` |
| `wo_checkout` | `cockpit2.py:2271` |
| `noochie_send` | `cockpit2.py:2283` |
| `noochie_reset` | `cockpit2.py:2309` |
| `noochie_ctx` | `cockpit2.py:2316` |
| `cl_add` | `cockpit2.py:2323` |
| `cl_report` | `cockpit2.py:2341` |
| `cl_remove` | `cockpit2.py:2356` |
| `m_add_kpi` | `cockpit2.py:2366` |
| `m_add_from_def` | `cockpit2.py:2398` |
| `def_add` | `cockpit2.py:2413` |
| `catalog_publish` | `cockpit2.py:2435` |
| `def_amend` | `cockpit2.py:2461` |
| `m_add_link` | `cockpit2.py:2503` |
| `m_sample` | `cockpit2.py:2514` |
| `m_remove` | `cockpit2.py:2524` |
| `m_pin` | `cockpit2.py:2534` |
| `m_unpin` | `cockpit2.py:2545` |
| `tile_add` | `cockpit2.py:2583` |
| `indicator_activate` | `cockpit2.py:2555` |
| `tile_remove` | `cockpit2.py:2617` |
| `rov2_set` | `cockpit2.py:2627` |
| `rov2_acc_add` | `cockpit2.py:2627` |
| `rov2_acc_remove` | `cockpit2.py:2627` |
| `rov2_dom_add` | `cockpit2.py:2627` |
| `rov2_dom_remove` | `cockpit2.py:2627` |
| `backlog_add` | `cockpit2.py:2659` |
| `backlog_update_staat` | `cockpit2.py:2671` |
| `backlog_update_prioriteit` | `cockpit2.py:2683` |
| `person_edit` | `cockpit2.py:2695` |
| `person_remove` | `cockpit2.py:2712` |
| `lk_mute` | `cockpit2.py:2733` |


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
