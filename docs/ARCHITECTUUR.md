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
| `proj_agendeer_verzwakt` | `cockpit2.py:1037` |
| `proj_setprivate` | `cockpit2.py:1061` |
| `proj_setdue` | `cockpit2.py:1072` |
| `attach_add` | `cockpit2.py:1083` |
| `attach_remove` | `cockpit2.py:1094` |
| `react_add` | `cockpit2.py:1104` |
| `feed_edit` | `cockpit2.py:1114` |
| `feed_remove` | `cockpit2.py:1124` |
| `ai_reply` | `cockpit2.py:1133` |
| `proj_feed` | `cockpit2.py:1144` |
| `checklist_add` | `cockpit2.py:1171` |
| `checklist_remove` | `cockpit2.py:1182` |
| `check_add` | `cockpit2.py:1222` |
| `check_accept` | `cockpit2.py:1238` |
| `check_toggle` | `cockpit2.py:1248` |
| `check_remove` | `cockpit2.py:1258` |
| `role_assign` | `cockpit2.py:1268` |
| `role_unassign` | `cockpit2.py:1286` |
| `role_focus` | `cockpit2.py:1305` |
| `aitask_add` | `cockpit2.py:1324` |
| `aitask_remove` | `cockpit2.py:1350` |
| `persona_skill_add` | `cockpit2.py:1367` |
| `rov2_add` | `cockpit2.py:1382` |
| `rov2_add_to_group` | `cockpit2.py:1394` |
| `rov2_remove` | `cockpit2.py:1406` |
| `rov2_remove_group` | `cockpit2.py:1421` |
| `rov2_setkind` | `cockpit2.py:1439` |
| `rov2_consent` | `cockpit2.py:1452` |
| `rov2_end` | `cockpit2.py:1474` |
| `wo_open` | `cockpit2.py:1498` |
| `wo_close` | `cockpit2.py:1508` |
| `wo_presence` | `cockpit2.py:1530` |
| `wo_present_all` | `cockpit2.py:1541` |
| `wo_ag_add` | `cockpit2.py:1553` |
| `wo_ag_remove` | `cockpit2.py:1565` |
| `wo_ag_note` | `cockpit2.py:1575` |
| `wo_ag_reopen` | `cockpit2.py:1587` |
| `wo_ag_resolve` | `cockpit2.py:1600` |
| `wo_checkout` | `cockpit2.py:1642` |
| `noochie_send` | `cockpit2.py:1653` |
| `noochie_reset` | `cockpit2.py:1679` |
| `noochie_ctx` | `cockpit2.py:1686` |
| `cl_add` | `cockpit2.py:1693` |
| `cl_report` | `cockpit2.py:1711` |
| `cl_remove` | `cockpit2.py:1726` |
| `m_add_kpi` | `cockpit2.py:1736` |
| `m_add_from_def` | `cockpit2.py:1768` |
| `def_add` | `cockpit2.py:1783` |
| `catalog_publish` | `cockpit2.py:1805` |
| `def_amend` | `cockpit2.py:1831` |
| `m_add_link` | `cockpit2.py:1873` |
| `m_sample` | `cockpit2.py:1884` |
| `m_remove` | `cockpit2.py:1894` |
| `m_pin` | `cockpit2.py:1904` |
| `m_unpin` | `cockpit2.py:1915` |
| `tile_add` | `cockpit2.py:1953` |
| `indicator_activate` | `cockpit2.py:1925` |
| `tile_remove` | `cockpit2.py:1987` |
| `rov2_set` | `cockpit2.py:1997` |
| `rov2_acc_add` | `cockpit2.py:1997` |
| `rov2_acc_remove` | `cockpit2.py:1997` |
| `rov2_dom_add` | `cockpit2.py:1997` |
| `rov2_dom_remove` | `cockpit2.py:1997` |
| `backlog_add` | `cockpit2.py:2029` |
| `backlog_update_staat` | `cockpit2.py:2041` |
| `backlog_update_prioriteit` | `cockpit2.py:2053` |
| `person_edit` | `cockpit2.py:2065` |
| `person_remove` | `cockpit2.py:2082` |


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
_24 routes · 87 dispatch-acties · 19 stores._
