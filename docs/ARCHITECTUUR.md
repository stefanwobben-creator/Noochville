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
| `/catalogus_koppelen` | `render_catalogus_koppelen` | `nooch_village/views/catalog_koppelen.py` |
| `/kpi_new` | `render_kpi_composer` | `nooch_village/views/metrics.py` |
| `/noochie` | `render_noochie` | `nooch_village/views/noochie.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → regel

De POST-acties uit de `dispatch()`-keten (cockpit2.py). Elke actie is één `if/elif action == "…"`-tak; het regelnummer wijst naar het begin ervan.

| Actie | cockpit2.py:regel |
|---|---|
| `proj_add` | `cockpit2.py:586` |
| `artefact_add` | `cockpit2.py:609` |
| `artefact_edit` | `cockpit2.py:645` |
| `artefact_archive` | `cockpit2.py:664` |
| `proj_status` | `cockpit2.py:679` |
| `proj_done` | `cockpit2.py:692` |
| `proj_archive` | `cockpit2.py:697` |
| `proj_unarchive` | `cockpit2.py:702` |
| `proj_delete` | `cockpit2.py:707` |
| `proj_edit` | `cockpit2.py:717` |
| `proj_comment` | `cockpit2.py:725` |
| `proj_rename` | `cockpit2.py:730` |
| `proj_describe` | `cockpit2.py:736` |
| `proj_settrekker` | `cockpit2.py:742` |
| `proj_setowner` | `cockpit2.py:749` |
| `proj_approve` | `cockpit2.py:762` |
| `proj_discard` | `cockpit2.py:768` |
| `proj_setlabel` | `cockpit2.py:774` |
| `proj_setprivate` | `cockpit2.py:780` |
| `proj_setdue` | `cockpit2.py:786` |
| `attach_add` | `cockpit2.py:792` |
| `attach_remove` | `cockpit2.py:798` |
| `react_add` | `cockpit2.py:803` |
| `feed_edit` | `cockpit2.py:808` |
| `feed_remove` | `cockpit2.py:813` |
| `ai_reply` | `cockpit2.py:817` |
| `proj_feed` | `cockpit2.py:823` |
| `checklist_add` | `cockpit2.py:838` |
| `checklist_remove` | `cockpit2.py:844` |
| `check_add` | `cockpit2.py:849` |
| `check_toggle` | `cockpit2.py:855` |
| `check_remove` | `cockpit2.py:860` |
| `role_assign` | `cockpit2.py:865` |
| `role_unassign` | `cockpit2.py:878` |
| `role_focus` | `cockpit2.py:892` |
| `aitask_add` | `cockpit2.py:906` |
| `aitask_remove` | `cockpit2.py:927` |
| `persona_skill_add` | `cockpit2.py:939` |
| `rov2_add` | `cockpit2.py:949` |
| `rov2_add_to_group` | `cockpit2.py:956` |
| `rov2_remove` | `cockpit2.py:963` |
| `rov2_remove_group` | `cockpit2.py:973` |
| `rov2_setkind` | `cockpit2.py:986` |
| `rov2_consent` | `cockpit2.py:994` |
| `rov2_end` | `cockpit2.py:1011` |
| `wo_open` | `cockpit2.py:1030` |
| `wo_close` | `cockpit2.py:1035` |
| `wo_presence` | `cockpit2.py:1052` |
| `wo_present_all` | `cockpit2.py:1058` |
| `wo_ag_add` | `cockpit2.py:1065` |
| `wo_ag_remove` | `cockpit2.py:1072` |
| `wo_ag_note` | `cockpit2.py:1077` |
| `wo_ag_reopen` | `cockpit2.py:1084` |
| `wo_ag_resolve` | `cockpit2.py:1092` |
| `wo_checkout` | `cockpit2.py:1129` |
| `noochie_send` | `cockpit2.py:1135` |
| `noochie_reset` | `cockpit2.py:1156` |
| `noochie_ctx` | `cockpit2.py:1158` |
| `cl_add` | `cockpit2.py:1160` |
| `cl_report` | `cockpit2.py:1173` |
| `cl_remove` | `cockpit2.py:1183` |
| `m_add_kpi` | `cockpit2.py:1188` |
| `m_add_from_def` | `cockpit2.py:1215` |
| `def_add` | `cockpit2.py:1225` |
| `catalog_publish` | `cockpit2.py:1242` |
| `def_amend` | `cockpit2.py:1263` |
| `m_add_link` | `cockpit2.py:1300` |
| `m_sample` | `cockpit2.py:1306` |
| `m_remove` | `cockpit2.py:1311` |
| `m_pin` | `cockpit2.py:1316` |
| `m_unpin` | `cockpit2.py:1322` |
| `tile_add` | `cockpit2.py:1327` |
| `tile_remove` | `cockpit2.py:1353` |
| `backlog_add` | `cockpit2.py:1385` |
| `backlog_update_staat` | `cockpit2.py:1392` |
| `backlog_update_prioriteit` | `cockpit2.py:1399` |
| `person_edit` | `cockpit2.py:1406` |
| `person_remove` | `cockpit2.py:1418` |
| `person_add` | `cockpit2.py:1739` |
| `person_reset_password` | `cockpit2.py:1742` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `seen` | `SeenStore` | `artefact_seen.json` |
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
_22 routes · 80 dispatch-acties · 19 stores._
