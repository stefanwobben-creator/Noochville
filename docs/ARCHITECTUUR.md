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
| `proj_add` | `cockpit2.py:618` |
| `artefact_add` | `cockpit2.py:646` |
| `artefact_edit` | `cockpit2.py:687` |
| `artefact_archive` | `cockpit2.py:711` |
| `proj_status` | `cockpit2.py:731` |
| `proj_done` | `cockpit2.py:749` |
| `proj_archive` | `cockpit2.py:759` |
| `proj_unarchive` | `cockpit2.py:769` |
| `proj_delete` | `cockpit2.py:779` |
| `proj_edit` | `cockpit2.py:794` |
| `proj_comment` | `cockpit2.py:807` |
| `proj_rename` | `cockpit2.py:817` |
| `proj_describe` | `cockpit2.py:828` |
| `proj_settrekker` | `cockpit2.py:839` |
| `proj_setowner` | `cockpit2.py:851` |
| `proj_approve` | `cockpit2.py:869` |
| `proj_discard` | `cockpit2.py:880` |
| `proj_setlabel` | `cockpit2.py:891` |
| `proj_setimpact` | `cockpit2.py:906` |
| `proj_agendeer_verzwakt` | `cockpit2.py:925` |
| `proj_setprivate` | `cockpit2.py:949` |
| `proj_setdue` | `cockpit2.py:960` |
| `attach_add` | `cockpit2.py:971` |
| `attach_remove` | `cockpit2.py:982` |
| `react_add` | `cockpit2.py:992` |
| `feed_edit` | `cockpit2.py:1002` |
| `feed_remove` | `cockpit2.py:1012` |
| `ai_reply` | `cockpit2.py:1021` |
| `proj_feed` | `cockpit2.py:1032` |
| `checklist_add` | `cockpit2.py:1052` |
| `checklist_remove` | `cockpit2.py:1063` |
| `check_add` | `cockpit2.py:1073` |
| `check_toggle` | `cockpit2.py:1084` |
| `check_remove` | `cockpit2.py:1094` |
| `role_assign` | `cockpit2.py:1104` |
| `role_unassign` | `cockpit2.py:1122` |
| `role_focus` | `cockpit2.py:1141` |
| `aitask_add` | `cockpit2.py:1160` |
| `aitask_remove` | `cockpit2.py:1186` |
| `persona_skill_add` | `cockpit2.py:1203` |
| `rov2_add` | `cockpit2.py:1218` |
| `rov2_add_to_group` | `cockpit2.py:1230` |
| `rov2_remove` | `cockpit2.py:1242` |
| `rov2_remove_group` | `cockpit2.py:1257` |
| `rov2_setkind` | `cockpit2.py:1275` |
| `rov2_consent` | `cockpit2.py:1288` |
| `rov2_end` | `cockpit2.py:1310` |
| `wo_open` | `cockpit2.py:1334` |
| `wo_close` | `cockpit2.py:1344` |
| `wo_presence` | `cockpit2.py:1366` |
| `wo_present_all` | `cockpit2.py:1377` |
| `wo_ag_add` | `cockpit2.py:1389` |
| `wo_ag_remove` | `cockpit2.py:1401` |
| `wo_ag_note` | `cockpit2.py:1411` |
| `wo_ag_reopen` | `cockpit2.py:1423` |
| `wo_ag_resolve` | `cockpit2.py:1436` |
| `wo_checkout` | `cockpit2.py:1478` |
| `noochie_send` | `cockpit2.py:1489` |
| `noochie_reset` | `cockpit2.py:1515` |
| `noochie_ctx` | `cockpit2.py:1522` |
| `cl_add` | `cockpit2.py:1529` |
| `cl_report` | `cockpit2.py:1547` |
| `cl_remove` | `cockpit2.py:1562` |
| `m_add_kpi` | `cockpit2.py:1572` |
| `m_add_from_def` | `cockpit2.py:1604` |
| `def_add` | `cockpit2.py:1619` |
| `catalog_publish` | `cockpit2.py:1641` |
| `def_amend` | `cockpit2.py:1667` |
| `m_add_link` | `cockpit2.py:1709` |
| `m_sample` | `cockpit2.py:1720` |
| `m_remove` | `cockpit2.py:1730` |
| `m_pin` | `cockpit2.py:1740` |
| `m_unpin` | `cockpit2.py:1751` |
| `tile_add` | `cockpit2.py:1761` |
| `tile_remove` | `cockpit2.py:1792` |
| `rov2_set` | `cockpit2.py:1802` |
| `rov2_acc_add` | `cockpit2.py:1802` |
| `rov2_acc_remove` | `cockpit2.py:1802` |
| `rov2_dom_add` | `cockpit2.py:1802` |
| `rov2_dom_remove` | `cockpit2.py:1802` |
| `backlog_add` | `cockpit2.py:1834` |
| `backlog_update_staat` | `cockpit2.py:1846` |
| `backlog_update_prioriteit` | `cockpit2.py:1858` |
| `person_edit` | `cockpit2.py:1870` |
| `person_remove` | `cockpit2.py:1887` |


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
