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
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:580` |
| `artefact_add` | `cockpit2.py:608` |
| `artefact_edit` | `cockpit2.py:649` |
| `artefact_archive` | `cockpit2.py:673` |
| `proj_status` | `cockpit2.py:693` |
| `proj_done` | `cockpit2.py:711` |
| `proj_archive` | `cockpit2.py:721` |
| `proj_unarchive` | `cockpit2.py:731` |
| `proj_delete` | `cockpit2.py:741` |
| `proj_edit` | `cockpit2.py:756` |
| `proj_comment` | `cockpit2.py:769` |
| `proj_rename` | `cockpit2.py:779` |
| `proj_describe` | `cockpit2.py:790` |
| `proj_settrekker` | `cockpit2.py:801` |
| `proj_setowner` | `cockpit2.py:813` |
| `proj_approve` | `cockpit2.py:831` |
| `proj_discard` | `cockpit2.py:842` |
| `proj_setlabel` | `cockpit2.py:853` |
| `proj_setprivate` | `cockpit2.py:864` |
| `proj_setdue` | `cockpit2.py:875` |
| `attach_add` | `cockpit2.py:886` |
| `attach_remove` | `cockpit2.py:897` |
| `react_add` | `cockpit2.py:907` |
| `feed_edit` | `cockpit2.py:917` |
| `feed_remove` | `cockpit2.py:927` |
| `ai_reply` | `cockpit2.py:936` |
| `proj_feed` | `cockpit2.py:947` |
| `checklist_add` | `cockpit2.py:967` |
| `checklist_remove` | `cockpit2.py:978` |
| `check_add` | `cockpit2.py:988` |
| `check_toggle` | `cockpit2.py:999` |
| `check_remove` | `cockpit2.py:1009` |
| `role_assign` | `cockpit2.py:1019` |
| `role_unassign` | `cockpit2.py:1037` |
| `role_focus` | `cockpit2.py:1056` |
| `aitask_add` | `cockpit2.py:1075` |
| `aitask_remove` | `cockpit2.py:1101` |
| `persona_skill_add` | `cockpit2.py:1118` |
| `rov2_add` | `cockpit2.py:1133` |
| `rov2_add_to_group` | `cockpit2.py:1145` |
| `rov2_remove` | `cockpit2.py:1157` |
| `rov2_remove_group` | `cockpit2.py:1172` |
| `rov2_setkind` | `cockpit2.py:1190` |
| `rov2_consent` | `cockpit2.py:1203` |
| `rov2_end` | `cockpit2.py:1225` |
| `wo_open` | `cockpit2.py:1249` |
| `wo_close` | `cockpit2.py:1259` |
| `wo_presence` | `cockpit2.py:1281` |
| `wo_present_all` | `cockpit2.py:1292` |
| `wo_ag_add` | `cockpit2.py:1304` |
| `wo_ag_remove` | `cockpit2.py:1316` |
| `wo_ag_note` | `cockpit2.py:1326` |
| `wo_ag_reopen` | `cockpit2.py:1338` |
| `wo_ag_resolve` | `cockpit2.py:1351` |
| `wo_checkout` | `cockpit2.py:1393` |
| `noochie_send` | `cockpit2.py:1404` |
| `noochie_reset` | `cockpit2.py:1430` |
| `noochie_ctx` | `cockpit2.py:1437` |
| `cl_add` | `cockpit2.py:1444` |
| `cl_report` | `cockpit2.py:1462` |
| `cl_remove` | `cockpit2.py:1477` |
| `m_add_kpi` | `cockpit2.py:1487` |
| `m_add_from_def` | `cockpit2.py:1519` |
| `def_add` | `cockpit2.py:1534` |
| `catalog_publish` | `cockpit2.py:1556` |
| `def_amend` | `cockpit2.py:1582` |
| `m_add_link` | `cockpit2.py:1624` |
| `m_sample` | `cockpit2.py:1635` |
| `m_remove` | `cockpit2.py:1645` |
| `m_pin` | `cockpit2.py:1655` |
| `m_unpin` | `cockpit2.py:1666` |
| `tile_add` | `cockpit2.py:1676` |
| `tile_remove` | `cockpit2.py:1707` |
| `rov2_set` | `cockpit2.py:1717` |
| `rov2_acc_add` | `cockpit2.py:1717` |
| `rov2_acc_remove` | `cockpit2.py:1717` |
| `rov2_dom_add` | `cockpit2.py:1717` |
| `rov2_dom_remove` | `cockpit2.py:1717` |
| `backlog_add` | `cockpit2.py:1749` |
| `backlog_update_staat` | `cockpit2.py:1761` |
| `backlog_update_prioriteit` | `cockpit2.py:1773` |
| `person_edit` | `cockpit2.py:1785` |
| `person_remove` | `cockpit2.py:1802` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `personas` | `PersonaStore` | `personas.json` |
| `projects` | `ProjectLedger` | `projects.json` |
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


---
_23 routes · 83 dispatch-acties · 18 stores._
