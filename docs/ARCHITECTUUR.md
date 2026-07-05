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
| `proj_add` | `cockpit2.py:584` |
| `artefact_add` | `cockpit2.py:612` |
| `artefact_edit` | `cockpit2.py:653` |
| `artefact_archive` | `cockpit2.py:677` |
| `proj_status` | `cockpit2.py:697` |
| `proj_done` | `cockpit2.py:715` |
| `proj_archive` | `cockpit2.py:725` |
| `proj_unarchive` | `cockpit2.py:735` |
| `proj_delete` | `cockpit2.py:745` |
| `proj_edit` | `cockpit2.py:760` |
| `proj_comment` | `cockpit2.py:773` |
| `proj_rename` | `cockpit2.py:783` |
| `proj_describe` | `cockpit2.py:794` |
| `proj_settrekker` | `cockpit2.py:805` |
| `proj_setowner` | `cockpit2.py:817` |
| `proj_approve` | `cockpit2.py:835` |
| `proj_discard` | `cockpit2.py:846` |
| `proj_setlabel` | `cockpit2.py:857` |
| `proj_setprivate` | `cockpit2.py:868` |
| `proj_setdue` | `cockpit2.py:879` |
| `attach_add` | `cockpit2.py:890` |
| `attach_remove` | `cockpit2.py:901` |
| `react_add` | `cockpit2.py:911` |
| `feed_edit` | `cockpit2.py:921` |
| `feed_remove` | `cockpit2.py:931` |
| `ai_reply` | `cockpit2.py:940` |
| `proj_feed` | `cockpit2.py:951` |
| `checklist_add` | `cockpit2.py:971` |
| `checklist_remove` | `cockpit2.py:982` |
| `check_add` | `cockpit2.py:992` |
| `check_toggle` | `cockpit2.py:1003` |
| `check_remove` | `cockpit2.py:1013` |
| `role_assign` | `cockpit2.py:1023` |
| `role_unassign` | `cockpit2.py:1041` |
| `role_focus` | `cockpit2.py:1060` |
| `aitask_add` | `cockpit2.py:1079` |
| `aitask_remove` | `cockpit2.py:1105` |
| `persona_skill_add` | `cockpit2.py:1122` |
| `rov2_add` | `cockpit2.py:1137` |
| `rov2_add_to_group` | `cockpit2.py:1149` |
| `rov2_remove` | `cockpit2.py:1161` |
| `rov2_remove_group` | `cockpit2.py:1176` |
| `rov2_setkind` | `cockpit2.py:1194` |
| `rov2_consent` | `cockpit2.py:1207` |
| `rov2_end` | `cockpit2.py:1229` |
| `wo_open` | `cockpit2.py:1253` |
| `wo_close` | `cockpit2.py:1263` |
| `wo_presence` | `cockpit2.py:1285` |
| `wo_present_all` | `cockpit2.py:1296` |
| `wo_ag_add` | `cockpit2.py:1308` |
| `wo_ag_remove` | `cockpit2.py:1320` |
| `wo_ag_note` | `cockpit2.py:1330` |
| `wo_ag_reopen` | `cockpit2.py:1342` |
| `wo_ag_resolve` | `cockpit2.py:1355` |
| `wo_checkout` | `cockpit2.py:1397` |
| `noochie_send` | `cockpit2.py:1408` |
| `noochie_reset` | `cockpit2.py:1434` |
| `noochie_ctx` | `cockpit2.py:1441` |
| `cl_add` | `cockpit2.py:1448` |
| `cl_report` | `cockpit2.py:1466` |
| `cl_remove` | `cockpit2.py:1481` |
| `m_add_kpi` | `cockpit2.py:1491` |
| `m_add_from_def` | `cockpit2.py:1523` |
| `def_add` | `cockpit2.py:1538` |
| `catalog_publish` | `cockpit2.py:1560` |
| `def_amend` | `cockpit2.py:1586` |
| `m_add_link` | `cockpit2.py:1628` |
| `m_sample` | `cockpit2.py:1639` |
| `m_remove` | `cockpit2.py:1649` |
| `m_pin` | `cockpit2.py:1659` |
| `m_unpin` | `cockpit2.py:1670` |
| `tile_add` | `cockpit2.py:1680` |
| `tile_remove` | `cockpit2.py:1711` |
| `rov2_set` | `cockpit2.py:1721` |
| `rov2_acc_add` | `cockpit2.py:1721` |
| `rov2_acc_remove` | `cockpit2.py:1721` |
| `rov2_dom_add` | `cockpit2.py:1721` |
| `rov2_dom_remove` | `cockpit2.py:1721` |
| `backlog_add` | `cockpit2.py:1753` |
| `backlog_update_staat` | `cockpit2.py:1765` |
| `backlog_update_prioriteit` | `cockpit2.py:1777` |
| `person_edit` | `cockpit2.py:1789` |
| `person_remove` | `cockpit2.py:1806` |


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
_23 routes · 83 dispatch-acties · 19 stores._
