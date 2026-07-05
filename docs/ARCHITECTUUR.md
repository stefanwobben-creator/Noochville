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


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:582` |
| `artefact_add` | `cockpit2.py:610` |
| `artefact_edit` | `cockpit2.py:651` |
| `artefact_archive` | `cockpit2.py:675` |
| `proj_status` | `cockpit2.py:695` |
| `proj_done` | `cockpit2.py:713` |
| `proj_archive` | `cockpit2.py:723` |
| `proj_unarchive` | `cockpit2.py:733` |
| `proj_delete` | `cockpit2.py:743` |
| `proj_edit` | `cockpit2.py:758` |
| `proj_comment` | `cockpit2.py:771` |
| `proj_rename` | `cockpit2.py:781` |
| `proj_describe` | `cockpit2.py:792` |
| `proj_settrekker` | `cockpit2.py:803` |
| `proj_setowner` | `cockpit2.py:815` |
| `proj_approve` | `cockpit2.py:833` |
| `proj_discard` | `cockpit2.py:844` |
| `proj_setlabel` | `cockpit2.py:855` |
| `proj_setprivate` | `cockpit2.py:866` |
| `proj_setdue` | `cockpit2.py:877` |
| `attach_add` | `cockpit2.py:888` |
| `attach_remove` | `cockpit2.py:899` |
| `react_add` | `cockpit2.py:909` |
| `feed_edit` | `cockpit2.py:919` |
| `feed_remove` | `cockpit2.py:929` |
| `ai_reply` | `cockpit2.py:938` |
| `proj_feed` | `cockpit2.py:949` |
| `checklist_add` | `cockpit2.py:969` |
| `checklist_remove` | `cockpit2.py:980` |
| `check_add` | `cockpit2.py:990` |
| `check_toggle` | `cockpit2.py:1001` |
| `check_remove` | `cockpit2.py:1011` |
| `role_assign` | `cockpit2.py:1021` |
| `role_unassign` | `cockpit2.py:1039` |
| `role_focus` | `cockpit2.py:1058` |
| `aitask_add` | `cockpit2.py:1077` |
| `aitask_remove` | `cockpit2.py:1103` |
| `persona_skill_add` | `cockpit2.py:1120` |
| `rov2_add` | `cockpit2.py:1135` |
| `rov2_add_to_group` | `cockpit2.py:1147` |
| `rov2_remove` | `cockpit2.py:1159` |
| `rov2_remove_group` | `cockpit2.py:1174` |
| `rov2_setkind` | `cockpit2.py:1192` |
| `rov2_consent` | `cockpit2.py:1205` |
| `rov2_end` | `cockpit2.py:1227` |
| `wo_open` | `cockpit2.py:1251` |
| `wo_close` | `cockpit2.py:1261` |
| `wo_presence` | `cockpit2.py:1283` |
| `wo_present_all` | `cockpit2.py:1294` |
| `wo_ag_add` | `cockpit2.py:1306` |
| `wo_ag_remove` | `cockpit2.py:1318` |
| `wo_ag_note` | `cockpit2.py:1328` |
| `wo_ag_reopen` | `cockpit2.py:1340` |
| `wo_ag_resolve` | `cockpit2.py:1353` |
| `wo_checkout` | `cockpit2.py:1395` |
| `noochie_send` | `cockpit2.py:1406` |
| `noochie_reset` | `cockpit2.py:1432` |
| `noochie_ctx` | `cockpit2.py:1439` |
| `cl_add` | `cockpit2.py:1446` |
| `cl_report` | `cockpit2.py:1464` |
| `cl_remove` | `cockpit2.py:1479` |
| `m_add_kpi` | `cockpit2.py:1489` |
| `m_add_from_def` | `cockpit2.py:1521` |
| `def_add` | `cockpit2.py:1536` |
| `catalog_publish` | `cockpit2.py:1558` |
| `def_amend` | `cockpit2.py:1584` |
| `m_add_link` | `cockpit2.py:1626` |
| `m_sample` | `cockpit2.py:1637` |
| `m_remove` | `cockpit2.py:1647` |
| `m_pin` | `cockpit2.py:1657` |
| `m_unpin` | `cockpit2.py:1668` |
| `tile_add` | `cockpit2.py:1678` |
| `tile_remove` | `cockpit2.py:1709` |
| `rov2_set` | `cockpit2.py:1719` |
| `rov2_acc_add` | `cockpit2.py:1719` |
| `rov2_acc_remove` | `cockpit2.py:1719` |
| `rov2_dom_add` | `cockpit2.py:1719` |
| `rov2_dom_remove` | `cockpit2.py:1719` |
| `backlog_add` | `cockpit2.py:1751` |
| `backlog_update_staat` | `cockpit2.py:1763` |
| `backlog_update_prioriteit` | `cockpit2.py:1775` |
| `person_edit` | `cockpit2.py:1787` |
| `person_remove` | `cockpit2.py:1804` |


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
_22 routes · 83 dispatch-acties · 19 stores._
