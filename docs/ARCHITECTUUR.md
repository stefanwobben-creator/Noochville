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
| `proj_add` | `cockpit2.py:627` |
| `artefact_add` | `cockpit2.py:655` |
| `artefact_edit` | `cockpit2.py:696` |
| `artefact_archive` | `cockpit2.py:720` |
| `proj_status` | `cockpit2.py:740` |
| `proj_done` | `cockpit2.py:758` |
| `proj_archive` | `cockpit2.py:769` |
| `proj_unarchive` | `cockpit2.py:779` |
| `proj_delete` | `cockpit2.py:789` |
| `proj_edit` | `cockpit2.py:804` |
| `proj_comment` | `cockpit2.py:817` |
| `proj_rename` | `cockpit2.py:827` |
| `proj_describe` | `cockpit2.py:838` |
| `proj_settrekker` | `cockpit2.py:849` |
| `proj_setowner` | `cockpit2.py:886` |
| `proj_approve` | `cockpit2.py:905` |
| `proj_discard` | `cockpit2.py:916` |
| `proj_setlabel` | `cockpit2.py:927` |
| `proj_setimpact` | `cockpit2.py:942` |
| `proj_agendeer_verzwakt` | `cockpit2.py:961` |
| `proj_setprivate` | `cockpit2.py:985` |
| `proj_setdue` | `cockpit2.py:996` |
| `attach_add` | `cockpit2.py:1007` |
| `attach_remove` | `cockpit2.py:1018` |
| `react_add` | `cockpit2.py:1028` |
| `feed_edit` | `cockpit2.py:1038` |
| `feed_remove` | `cockpit2.py:1048` |
| `ai_reply` | `cockpit2.py:1057` |
| `proj_feed` | `cockpit2.py:1068` |
| `checklist_add` | `cockpit2.py:1088` |
| `checklist_remove` | `cockpit2.py:1099` |
| `check_add` | `cockpit2.py:1109` |
| `check_toggle` | `cockpit2.py:1120` |
| `check_remove` | `cockpit2.py:1130` |
| `role_assign` | `cockpit2.py:1140` |
| `role_unassign` | `cockpit2.py:1158` |
| `role_focus` | `cockpit2.py:1177` |
| `aitask_add` | `cockpit2.py:1196` |
| `aitask_remove` | `cockpit2.py:1222` |
| `persona_skill_add` | `cockpit2.py:1239` |
| `rov2_add` | `cockpit2.py:1254` |
| `rov2_add_to_group` | `cockpit2.py:1266` |
| `rov2_remove` | `cockpit2.py:1278` |
| `rov2_remove_group` | `cockpit2.py:1293` |
| `rov2_setkind` | `cockpit2.py:1311` |
| `rov2_consent` | `cockpit2.py:1324` |
| `rov2_end` | `cockpit2.py:1346` |
| `wo_open` | `cockpit2.py:1370` |
| `wo_close` | `cockpit2.py:1380` |
| `wo_presence` | `cockpit2.py:1402` |
| `wo_present_all` | `cockpit2.py:1413` |
| `wo_ag_add` | `cockpit2.py:1425` |
| `wo_ag_remove` | `cockpit2.py:1437` |
| `wo_ag_note` | `cockpit2.py:1447` |
| `wo_ag_reopen` | `cockpit2.py:1459` |
| `wo_ag_resolve` | `cockpit2.py:1472` |
| `wo_checkout` | `cockpit2.py:1514` |
| `noochie_send` | `cockpit2.py:1525` |
| `noochie_reset` | `cockpit2.py:1551` |
| `noochie_ctx` | `cockpit2.py:1558` |
| `cl_add` | `cockpit2.py:1565` |
| `cl_report` | `cockpit2.py:1583` |
| `cl_remove` | `cockpit2.py:1598` |
| `m_add_kpi` | `cockpit2.py:1608` |
| `m_add_from_def` | `cockpit2.py:1640` |
| `def_add` | `cockpit2.py:1655` |
| `catalog_publish` | `cockpit2.py:1677` |
| `def_amend` | `cockpit2.py:1703` |
| `m_add_link` | `cockpit2.py:1745` |
| `m_sample` | `cockpit2.py:1756` |
| `m_remove` | `cockpit2.py:1766` |
| `m_pin` | `cockpit2.py:1776` |
| `m_unpin` | `cockpit2.py:1787` |
| `tile_add` | `cockpit2.py:1825` |
| `indicator_activate` | `cockpit2.py:1797` |
| `tile_remove` | `cockpit2.py:1859` |
| `rov2_set` | `cockpit2.py:1869` |
| `rov2_acc_add` | `cockpit2.py:1869` |
| `rov2_acc_remove` | `cockpit2.py:1869` |
| `rov2_dom_add` | `cockpit2.py:1869` |
| `rov2_dom_remove` | `cockpit2.py:1869` |
| `backlog_add` | `cockpit2.py:1901` |
| `backlog_update_staat` | `cockpit2.py:1913` |
| `backlog_update_prioriteit` | `cockpit2.py:1925` |
| `person_edit` | `cockpit2.py:1937` |
| `person_remove` | `cockpit2.py:1954` |


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
_24 routes · 86 dispatch-acties · 19 stores._
