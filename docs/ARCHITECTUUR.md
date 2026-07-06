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
| `proj_setimpact` | `cockpit2.py:901` |
| `proj_agendeer_verzwakt` | `cockpit2.py:920` |
| `proj_setprivate` | `cockpit2.py:944` |
| `proj_setdue` | `cockpit2.py:955` |
| `attach_add` | `cockpit2.py:966` |
| `attach_remove` | `cockpit2.py:977` |
| `react_add` | `cockpit2.py:987` |
| `feed_edit` | `cockpit2.py:997` |
| `feed_remove` | `cockpit2.py:1007` |
| `ai_reply` | `cockpit2.py:1016` |
| `proj_feed` | `cockpit2.py:1027` |
| `checklist_add` | `cockpit2.py:1047` |
| `checklist_remove` | `cockpit2.py:1058` |
| `check_add` | `cockpit2.py:1068` |
| `check_toggle` | `cockpit2.py:1079` |
| `check_remove` | `cockpit2.py:1089` |
| `role_assign` | `cockpit2.py:1099` |
| `role_unassign` | `cockpit2.py:1117` |
| `role_focus` | `cockpit2.py:1136` |
| `aitask_add` | `cockpit2.py:1155` |
| `aitask_remove` | `cockpit2.py:1181` |
| `persona_skill_add` | `cockpit2.py:1198` |
| `rov2_add` | `cockpit2.py:1213` |
| `rov2_add_to_group` | `cockpit2.py:1225` |
| `rov2_remove` | `cockpit2.py:1237` |
| `rov2_remove_group` | `cockpit2.py:1252` |
| `rov2_setkind` | `cockpit2.py:1270` |
| `rov2_consent` | `cockpit2.py:1283` |
| `rov2_end` | `cockpit2.py:1305` |
| `wo_open` | `cockpit2.py:1329` |
| `wo_close` | `cockpit2.py:1339` |
| `wo_presence` | `cockpit2.py:1361` |
| `wo_present_all` | `cockpit2.py:1372` |
| `wo_ag_add` | `cockpit2.py:1384` |
| `wo_ag_remove` | `cockpit2.py:1396` |
| `wo_ag_note` | `cockpit2.py:1406` |
| `wo_ag_reopen` | `cockpit2.py:1418` |
| `wo_ag_resolve` | `cockpit2.py:1431` |
| `wo_checkout` | `cockpit2.py:1473` |
| `noochie_send` | `cockpit2.py:1484` |
| `noochie_reset` | `cockpit2.py:1510` |
| `noochie_ctx` | `cockpit2.py:1517` |
| `cl_add` | `cockpit2.py:1524` |
| `cl_report` | `cockpit2.py:1542` |
| `cl_remove` | `cockpit2.py:1557` |
| `m_add_kpi` | `cockpit2.py:1567` |
| `m_add_from_def` | `cockpit2.py:1599` |
| `def_add` | `cockpit2.py:1614` |
| `catalog_publish` | `cockpit2.py:1636` |
| `def_amend` | `cockpit2.py:1662` |
| `m_add_link` | `cockpit2.py:1704` |
| `m_sample` | `cockpit2.py:1715` |
| `m_remove` | `cockpit2.py:1725` |
| `m_pin` | `cockpit2.py:1735` |
| `m_unpin` | `cockpit2.py:1746` |
| `tile_add` | `cockpit2.py:1756` |
| `tile_remove` | `cockpit2.py:1787` |
| `rov2_set` | `cockpit2.py:1797` |
| `rov2_acc_add` | `cockpit2.py:1797` |
| `rov2_acc_remove` | `cockpit2.py:1797` |
| `rov2_dom_add` | `cockpit2.py:1797` |
| `rov2_dom_remove` | `cockpit2.py:1797` |
| `backlog_add` | `cockpit2.py:1829` |
| `backlog_update_staat` | `cockpit2.py:1841` |
| `backlog_update_prioriteit` | `cockpit2.py:1853` |
| `person_edit` | `cockpit2.py:1865` |
| `person_remove` | `cockpit2.py:1882` |


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
_24 routes · 85 dispatch-acties · 19 stores._
