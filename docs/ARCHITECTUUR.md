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
| `proj_add` | `cockpit2.py:703` |
| `artefact_add` | `cockpit2.py:731` |
| `artefact_edit` | `cockpit2.py:772` |
| `artefact_archive` | `cockpit2.py:796` |
| `proj_status` | `cockpit2.py:816` |
| `proj_done` | `cockpit2.py:834` |
| `proj_archive` | `cockpit2.py:845` |
| `proj_unarchive` | `cockpit2.py:855` |
| `proj_delete` | `cockpit2.py:865` |
| `proj_edit` | `cockpit2.py:880` |
| `proj_comment` | `cockpit2.py:893` |
| `proj_rename` | `cockpit2.py:903` |
| `proj_describe` | `cockpit2.py:914` |
| `proj_settrekker` | `cockpit2.py:925` |
| `proj_setowner` | `cockpit2.py:962` |
| `proj_approve` | `cockpit2.py:981` |
| `proj_discard` | `cockpit2.py:992` |
| `proj_setlabel` | `cockpit2.py:1003` |
| `proj_setimpact` | `cockpit2.py:1018` |
| `proj_seteffort` | `cockpit2.py:1037` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1060` |
| `proj_setprivate` | `cockpit2.py:1084` |
| `proj_setdue` | `cockpit2.py:1095` |
| `attach_add` | `cockpit2.py:1106` |
| `attach_remove` | `cockpit2.py:1117` |
| `react_add` | `cockpit2.py:1127` |
| `feed_edit` | `cockpit2.py:1137` |
| `feed_remove` | `cockpit2.py:1147` |
| `wall_outcome` | `cockpit2.py:1712` |
| `ai_reply` | `cockpit2.py:1156` |
| `proj_feed` | `cockpit2.py:1167` |
| `checklist_add` | `cockpit2.py:1194` |
| `checklist_remove` | `cockpit2.py:1205` |
| `check_add` | `cockpit2.py:1245` |
| `check_accept` | `cockpit2.py:1261` |
| `check_toggle` | `cockpit2.py:1271` |
| `check_remove` | `cockpit2.py:1281` |
| `role_assign` | `cockpit2.py:1291` |
| `role_unassign` | `cockpit2.py:1309` |
| `role_focus` | `cockpit2.py:1328` |
| `aitask_add` | `cockpit2.py:1347` |
| `aitask_remove` | `cockpit2.py:1373` |
| `persona_skill_add` | `cockpit2.py:1390` |
| `rov2_add` | `cockpit2.py:1405` |
| `rov2_add_to_group` | `cockpit2.py:1417` |
| `rov2_remove` | `cockpit2.py:1429` |
| `rov2_remove_group` | `cockpit2.py:1444` |
| `rov2_setkind` | `cockpit2.py:1462` |
| `rov2_consent` | `cockpit2.py:1475` |
| `rov2_end` | `cockpit2.py:1497` |
| `wo_open` | `cockpit2.py:1521` |
| `wo_close` | `cockpit2.py:1531` |
| `wo_presence` | `cockpit2.py:1553` |
| `wo_present_all` | `cockpit2.py:1564` |
| `wo_ag_add` | `cockpit2.py:1576` |
| `wo_ag_remove` | `cockpit2.py:1588` |
| `wo_ag_note` | `cockpit2.py:1598` |
| `wo_ag_reopen` | `cockpit2.py:1610` |
| `wo_ag_resolve` | `cockpit2.py:1686` |
| `wo_checkout` | `cockpit2.py:1808` |
| `noochie_send` | `cockpit2.py:1820` |
| `noochie_reset` | `cockpit2.py:1846` |
| `noochie_ctx` | `cockpit2.py:1853` |
| `cl_add` | `cockpit2.py:1860` |
| `cl_report` | `cockpit2.py:1878` |
| `cl_remove` | `cockpit2.py:1893` |
| `m_add_kpi` | `cockpit2.py:1903` |
| `m_add_from_def` | `cockpit2.py:1935` |
| `def_add` | `cockpit2.py:1950` |
| `catalog_publish` | `cockpit2.py:1972` |
| `def_amend` | `cockpit2.py:1998` |
| `m_add_link` | `cockpit2.py:2040` |
| `m_sample` | `cockpit2.py:2051` |
| `m_remove` | `cockpit2.py:2061` |
| `m_pin` | `cockpit2.py:2071` |
| `m_unpin` | `cockpit2.py:2082` |
| `tile_add` | `cockpit2.py:2120` |
| `indicator_activate` | `cockpit2.py:2092` |
| `tile_remove` | `cockpit2.py:2154` |
| `rov2_set` | `cockpit2.py:2164` |
| `rov2_acc_add` | `cockpit2.py:2164` |
| `rov2_acc_remove` | `cockpit2.py:2164` |
| `rov2_dom_add` | `cockpit2.py:2164` |
| `rov2_dom_remove` | `cockpit2.py:2164` |
| `backlog_add` | `cockpit2.py:2196` |
| `backlog_update_staat` | `cockpit2.py:2208` |
| `backlog_update_prioriteit` | `cockpit2.py:2220` |
| `person_edit` | `cockpit2.py:2232` |
| `person_remove` | `cockpit2.py:2249` |


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
_24 routes · 89 dispatch-acties · 19 stores._
