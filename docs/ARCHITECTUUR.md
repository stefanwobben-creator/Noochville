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
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:614` |
| `artefact_add` | `cockpit2.py:642` |
| `artefact_edit` | `cockpit2.py:683` |
| `artefact_archive` | `cockpit2.py:707` |
| `proj_status` | `cockpit2.py:727` |
| `proj_done` | `cockpit2.py:745` |
| `proj_archive` | `cockpit2.py:755` |
| `proj_unarchive` | `cockpit2.py:765` |
| `proj_delete` | `cockpit2.py:775` |
| `proj_edit` | `cockpit2.py:790` |
| `proj_comment` | `cockpit2.py:803` |
| `proj_rename` | `cockpit2.py:813` |
| `proj_describe` | `cockpit2.py:824` |
| `proj_settrekker` | `cockpit2.py:835` |
| `proj_setowner` | `cockpit2.py:847` |
| `proj_approve` | `cockpit2.py:865` |
| `proj_discard` | `cockpit2.py:876` |
| `proj_setlabel` | `cockpit2.py:887` |
| `proj_setprivate` | `cockpit2.py:898` |
| `proj_setdue` | `cockpit2.py:909` |
| `attach_add` | `cockpit2.py:920` |
| `attach_remove` | `cockpit2.py:931` |
| `react_add` | `cockpit2.py:941` |
| `feed_edit` | `cockpit2.py:951` |
| `feed_remove` | `cockpit2.py:961` |
| `ai_reply` | `cockpit2.py:970` |
| `proj_feed` | `cockpit2.py:981` |
| `checklist_add` | `cockpit2.py:1001` |
| `checklist_remove` | `cockpit2.py:1012` |
| `check_add` | `cockpit2.py:1022` |
| `check_toggle` | `cockpit2.py:1033` |
| `check_remove` | `cockpit2.py:1043` |
| `role_assign` | `cockpit2.py:1053` |
| `role_unassign` | `cockpit2.py:1071` |
| `role_focus` | `cockpit2.py:1090` |
| `aitask_add` | `cockpit2.py:1109` |
| `aitask_remove` | `cockpit2.py:1135` |
| `persona_skill_add` | `cockpit2.py:1152` |
| `rov2_add` | `cockpit2.py:1167` |
| `rov2_add_to_group` | `cockpit2.py:1179` |
| `rov2_remove` | `cockpit2.py:1191` |
| `rov2_remove_group` | `cockpit2.py:1206` |
| `rov2_setkind` | `cockpit2.py:1224` |
| `rov2_consent` | `cockpit2.py:1237` |
| `rov2_end` | `cockpit2.py:1259` |
| `wo_open` | `cockpit2.py:1283` |
| `wo_close` | `cockpit2.py:1293` |
| `wo_presence` | `cockpit2.py:1315` |
| `wo_present_all` | `cockpit2.py:1326` |
| `wo_ag_add` | `cockpit2.py:1338` |
| `wo_ag_remove` | `cockpit2.py:1350` |
| `wo_ag_note` | `cockpit2.py:1360` |
| `wo_ag_reopen` | `cockpit2.py:1372` |
| `wo_ag_resolve` | `cockpit2.py:1385` |
| `wo_checkout` | `cockpit2.py:1427` |
| `noochie_send` | `cockpit2.py:1438` |
| `noochie_reset` | `cockpit2.py:1464` |
| `noochie_ctx` | `cockpit2.py:1471` |
| `cl_add` | `cockpit2.py:1478` |
| `cl_report` | `cockpit2.py:1496` |
| `cl_remove` | `cockpit2.py:1511` |
| `m_add_kpi` | `cockpit2.py:1521` |
| `m_add_from_def` | `cockpit2.py:1553` |
| `def_add` | `cockpit2.py:1568` |
| `catalog_publish` | `cockpit2.py:1590` |
| `def_amend` | `cockpit2.py:1616` |
| `m_add_link` | `cockpit2.py:1658` |
| `m_sample` | `cockpit2.py:1669` |
| `m_remove` | `cockpit2.py:1679` |
| `m_pin` | `cockpit2.py:1689` |
| `m_unpin` | `cockpit2.py:1700` |
| `tile_add` | `cockpit2.py:1710` |
| `tile_remove` | `cockpit2.py:1741` |
| `rov2_set` | `cockpit2.py:1751` |
| `rov2_acc_add` | `cockpit2.py:1751` |
| `rov2_acc_remove` | `cockpit2.py:1751` |
| `rov2_dom_add` | `cockpit2.py:1751` |
| `rov2_dom_remove` | `cockpit2.py:1751` |
| `backlog_add` | `cockpit2.py:1783` |
| `backlog_update_staat` | `cockpit2.py:1795` |
| `backlog_update_prioriteit` | `cockpit2.py:1807` |
| `person_edit` | `cockpit2.py:1819` |
| `person_remove` | `cockpit2.py:1836` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `sources` | `SourceStatusStore` | `sources.json` |
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
_24 routes · 83 dispatch-acties · 19 stores._
