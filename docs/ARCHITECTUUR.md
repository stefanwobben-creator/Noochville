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
| `proj_add` | `cockpit2.py:622` |
| `artefact_add` | `cockpit2.py:650` |
| `artefact_edit` | `cockpit2.py:691` |
| `artefact_archive` | `cockpit2.py:715` |
| `proj_status` | `cockpit2.py:735` |
| `proj_done` | `cockpit2.py:753` |
| `proj_archive` | `cockpit2.py:763` |
| `proj_unarchive` | `cockpit2.py:773` |
| `proj_delete` | `cockpit2.py:783` |
| `proj_edit` | `cockpit2.py:798` |
| `proj_comment` | `cockpit2.py:811` |
| `proj_rename` | `cockpit2.py:821` |
| `proj_describe` | `cockpit2.py:832` |
| `proj_settrekker` | `cockpit2.py:843` |
| `proj_setowner` | `cockpit2.py:855` |
| `proj_approve` | `cockpit2.py:873` |
| `proj_discard` | `cockpit2.py:884` |
| `proj_setlabel` | `cockpit2.py:895` |
| `proj_setimpact` | `cockpit2.py:910` |
| `proj_agendeer_verzwakt` | `cockpit2.py:929` |
| `proj_setprivate` | `cockpit2.py:953` |
| `proj_setdue` | `cockpit2.py:964` |
| `attach_add` | `cockpit2.py:975` |
| `attach_remove` | `cockpit2.py:986` |
| `react_add` | `cockpit2.py:996` |
| `feed_edit` | `cockpit2.py:1006` |
| `feed_remove` | `cockpit2.py:1016` |
| `ai_reply` | `cockpit2.py:1025` |
| `proj_feed` | `cockpit2.py:1036` |
| `checklist_add` | `cockpit2.py:1056` |
| `checklist_remove` | `cockpit2.py:1067` |
| `check_add` | `cockpit2.py:1077` |
| `check_toggle` | `cockpit2.py:1088` |
| `check_remove` | `cockpit2.py:1098` |
| `role_assign` | `cockpit2.py:1108` |
| `role_unassign` | `cockpit2.py:1126` |
| `role_focus` | `cockpit2.py:1145` |
| `aitask_add` | `cockpit2.py:1164` |
| `aitask_remove` | `cockpit2.py:1190` |
| `persona_skill_add` | `cockpit2.py:1207` |
| `rov2_add` | `cockpit2.py:1222` |
| `rov2_add_to_group` | `cockpit2.py:1234` |
| `rov2_remove` | `cockpit2.py:1246` |
| `rov2_remove_group` | `cockpit2.py:1261` |
| `rov2_setkind` | `cockpit2.py:1279` |
| `rov2_consent` | `cockpit2.py:1292` |
| `rov2_end` | `cockpit2.py:1314` |
| `wo_open` | `cockpit2.py:1338` |
| `wo_close` | `cockpit2.py:1348` |
| `wo_presence` | `cockpit2.py:1370` |
| `wo_present_all` | `cockpit2.py:1381` |
| `wo_ag_add` | `cockpit2.py:1393` |
| `wo_ag_remove` | `cockpit2.py:1405` |
| `wo_ag_note` | `cockpit2.py:1415` |
| `wo_ag_reopen` | `cockpit2.py:1427` |
| `wo_ag_resolve` | `cockpit2.py:1440` |
| `wo_checkout` | `cockpit2.py:1482` |
| `noochie_send` | `cockpit2.py:1493` |
| `noochie_reset` | `cockpit2.py:1519` |
| `noochie_ctx` | `cockpit2.py:1526` |
| `cl_add` | `cockpit2.py:1533` |
| `cl_report` | `cockpit2.py:1551` |
| `cl_remove` | `cockpit2.py:1566` |
| `m_add_kpi` | `cockpit2.py:1576` |
| `m_add_from_def` | `cockpit2.py:1608` |
| `def_add` | `cockpit2.py:1623` |
| `catalog_publish` | `cockpit2.py:1645` |
| `def_amend` | `cockpit2.py:1671` |
| `m_add_link` | `cockpit2.py:1713` |
| `m_sample` | `cockpit2.py:1724` |
| `m_remove` | `cockpit2.py:1734` |
| `m_pin` | `cockpit2.py:1744` |
| `m_unpin` | `cockpit2.py:1755` |
| `tile_add` | `cockpit2.py:1793` |
| `indicator_activate` | `cockpit2.py:1765` |
| `tile_remove` | `cockpit2.py:1827` |
| `rov2_set` | `cockpit2.py:1837` |
| `rov2_acc_add` | `cockpit2.py:1837` |
| `rov2_acc_remove` | `cockpit2.py:1837` |
| `rov2_dom_add` | `cockpit2.py:1837` |
| `rov2_dom_remove` | `cockpit2.py:1837` |
| `backlog_add` | `cockpit2.py:1869` |
| `backlog_update_staat` | `cockpit2.py:1881` |
| `backlog_update_prioriteit` | `cockpit2.py:1893` |
| `person_edit` | `cockpit2.py:1905` |
| `person_remove` | `cockpit2.py:1922` |


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
