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
| `proj_add` | `cockpit2.py:804` |
| `artefact_add` | `cockpit2.py:832` |
| `artefact_edit` | `cockpit2.py:873` |
| `artefact_archive` | `cockpit2.py:897` |
| `proj_status` | `cockpit2.py:917` |
| `proj_done` | `cockpit2.py:935` |
| `proj_archive` | `cockpit2.py:957` |
| `proj_unarchive` | `cockpit2.py:967` |
| `proj_delete` | `cockpit2.py:977` |
| `proj_edit` | `cockpit2.py:1004` |
| `proj_comment` | `cockpit2.py:1017` |
| `proj_rename` | `cockpit2.py:1027` |
| `proj_describe` | `cockpit2.py:1038` |
| `proj_doc_edit` | `cockpit2.py:1071` |
| `proj_regen_doc` | `cockpit2.py:1049` |
| `proj_settrekker` | `cockpit2.py:1084` |
| `proj_setowner` | `cockpit2.py:1121` |
| `proj_approve` | `cockpit2.py:1140` |
| `proj_discard` | `cockpit2.py:1151` |
| `proj_setlabel` | `cockpit2.py:1162` |
| `proj_setimpact` | `cockpit2.py:1177` |
| `proj_seteffort` | `cockpit2.py:1196` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1219` |
| `proj_setprivate` | `cockpit2.py:1243` |
| `proj_setdue` | `cockpit2.py:1254` |
| `attach_add` | `cockpit2.py:1265` |
| `attach_remove` | `cockpit2.py:1276` |
| `react_add` | `cockpit2.py:1286` |
| `feed_edit` | `cockpit2.py:1296` |
| `feed_remove` | `cockpit2.py:1306` |
| `wall_outcome` | `cockpit2.py:1899` |
| `ai_reply` | `cockpit2.py:1315` |
| `proj_feed` | `cockpit2.py:1326` |
| `checklist_add` | `cockpit2.py:1356` |
| `checklist_remove` | `cockpit2.py:1367` |
| `check_add` | `cockpit2.py:1415` |
| `check_accept` | `cockpit2.py:1432` |
| `check_toggle` | `cockpit2.py:1442` |
| `check_remove` | `cockpit2.py:1452` |
| `role_assign` | `cockpit2.py:1462` |
| `role_unassign` | `cockpit2.py:1480` |
| `role_focus` | `cockpit2.py:1499` |
| `radar_approve` | `cockpit2.py:1532` |
| `radar_dismiss` | `cockpit2.py:1536` |
| `aitask_add` | `cockpit2.py:1540` |
| `aitask_remove` | `cockpit2.py:1566` |
| `persona_skill_add` | `cockpit2.py:1583` |
| `rov2_add` | `cockpit2.py:1598` |
| `rov2_add_to_group` | `cockpit2.py:1610` |
| `rov2_remove` | `cockpit2.py:1622` |
| `rov2_remove_group` | `cockpit2.py:1637` |
| `rov2_setkind` | `cockpit2.py:1655` |
| `rov2_consent` | `cockpit2.py:1668` |
| `rov2_end` | `cockpit2.py:1690` |
| `wo_open` | `cockpit2.py:1714` |
| `wo_close` | `cockpit2.py:1724` |
| `wo_presence` | `cockpit2.py:1740` |
| `wo_present_all` | `cockpit2.py:1751` |
| `wo_ag_add` | `cockpit2.py:1763` |
| `wo_ag_remove` | `cockpit2.py:1775` |
| `wo_ag_note` | `cockpit2.py:1785` |
| `wo_ag_reopen` | `cockpit2.py:1797` |
| `wo_ag_resolve` | `cockpit2.py:1873` |
| `wo_checkout` | `cockpit2.py:1995` |
| `noochie_send` | `cockpit2.py:2007` |
| `noochie_reset` | `cockpit2.py:2033` |
| `noochie_ctx` | `cockpit2.py:2040` |
| `cl_add` | `cockpit2.py:2047` |
| `cl_report` | `cockpit2.py:2065` |
| `cl_remove` | `cockpit2.py:2080` |
| `m_add_kpi` | `cockpit2.py:2090` |
| `m_add_from_def` | `cockpit2.py:2122` |
| `def_add` | `cockpit2.py:2137` |
| `catalog_publish` | `cockpit2.py:2159` |
| `def_amend` | `cockpit2.py:2185` |
| `m_add_link` | `cockpit2.py:2227` |
| `m_sample` | `cockpit2.py:2238` |
| `m_remove` | `cockpit2.py:2248` |
| `m_pin` | `cockpit2.py:2258` |
| `m_unpin` | `cockpit2.py:2269` |
| `tile_add` | `cockpit2.py:2307` |
| `indicator_activate` | `cockpit2.py:2279` |
| `tile_remove` | `cockpit2.py:2341` |
| `rov2_set` | `cockpit2.py:2351` |
| `rov2_acc_add` | `cockpit2.py:2351` |
| `rov2_acc_remove` | `cockpit2.py:2351` |
| `rov2_dom_add` | `cockpit2.py:2351` |
| `rov2_dom_remove` | `cockpit2.py:2351` |
| `backlog_add` | `cockpit2.py:2383` |
| `backlog_update_staat` | `cockpit2.py:2395` |
| `backlog_update_prioriteit` | `cockpit2.py:2407` |
| `person_edit` | `cockpit2.py:2419` |
| `person_remove` | `cockpit2.py:2436` |
| `lk_mute` | `cockpit2.py:2457` |


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
_26 routes · 94 dispatch-acties · 22 stores._
