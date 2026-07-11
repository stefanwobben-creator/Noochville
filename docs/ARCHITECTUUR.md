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
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:746` |
| `artefact_add` | `cockpit2.py:774` |
| `artefact_edit` | `cockpit2.py:815` |
| `artefact_archive` | `cockpit2.py:839` |
| `proj_status` | `cockpit2.py:859` |
| `proj_done` | `cockpit2.py:877` |
| `proj_archive` | `cockpit2.py:888` |
| `proj_unarchive` | `cockpit2.py:898` |
| `proj_delete` | `cockpit2.py:908` |
| `proj_edit` | `cockpit2.py:930` |
| `proj_comment` | `cockpit2.py:943` |
| `proj_rename` | `cockpit2.py:953` |
| `proj_describe` | `cockpit2.py:964` |
| `proj_settrekker` | `cockpit2.py:975` |
| `proj_setowner` | `cockpit2.py:1012` |
| `proj_approve` | `cockpit2.py:1031` |
| `proj_discard` | `cockpit2.py:1042` |
| `proj_setlabel` | `cockpit2.py:1053` |
| `proj_setimpact` | `cockpit2.py:1068` |
| `proj_seteffort` | `cockpit2.py:1087` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1110` |
| `proj_setprivate` | `cockpit2.py:1134` |
| `proj_setdue` | `cockpit2.py:1145` |
| `attach_add` | `cockpit2.py:1156` |
| `attach_remove` | `cockpit2.py:1167` |
| `react_add` | `cockpit2.py:1177` |
| `feed_edit` | `cockpit2.py:1187` |
| `feed_remove` | `cockpit2.py:1197` |
| `wall_outcome` | `cockpit2.py:1765` |
| `ai_reply` | `cockpit2.py:1206` |
| `proj_feed` | `cockpit2.py:1217` |
| `checklist_add` | `cockpit2.py:1244` |
| `checklist_remove` | `cockpit2.py:1255` |
| `check_add` | `cockpit2.py:1303` |
| `check_accept` | `cockpit2.py:1320` |
| `check_toggle` | `cockpit2.py:1330` |
| `check_remove` | `cockpit2.py:1340` |
| `role_assign` | `cockpit2.py:1350` |
| `role_unassign` | `cockpit2.py:1368` |
| `role_focus` | `cockpit2.py:1387` |
| `aitask_add` | `cockpit2.py:1406` |
| `aitask_remove` | `cockpit2.py:1432` |
| `persona_skill_add` | `cockpit2.py:1449` |
| `rov2_add` | `cockpit2.py:1464` |
| `rov2_add_to_group` | `cockpit2.py:1476` |
| `rov2_remove` | `cockpit2.py:1488` |
| `rov2_remove_group` | `cockpit2.py:1503` |
| `rov2_setkind` | `cockpit2.py:1521` |
| `rov2_consent` | `cockpit2.py:1534` |
| `rov2_end` | `cockpit2.py:1556` |
| `wo_open` | `cockpit2.py:1580` |
| `wo_close` | `cockpit2.py:1590` |
| `wo_presence` | `cockpit2.py:1606` |
| `wo_present_all` | `cockpit2.py:1617` |
| `wo_ag_add` | `cockpit2.py:1629` |
| `wo_ag_remove` | `cockpit2.py:1641` |
| `wo_ag_note` | `cockpit2.py:1651` |
| `wo_ag_reopen` | `cockpit2.py:1663` |
| `wo_ag_resolve` | `cockpit2.py:1739` |
| `wo_checkout` | `cockpit2.py:1861` |
| `noochie_send` | `cockpit2.py:1873` |
| `noochie_reset` | `cockpit2.py:1899` |
| `noochie_ctx` | `cockpit2.py:1906` |
| `cl_add` | `cockpit2.py:1913` |
| `cl_report` | `cockpit2.py:1931` |
| `cl_remove` | `cockpit2.py:1946` |
| `m_add_kpi` | `cockpit2.py:1956` |
| `m_add_from_def` | `cockpit2.py:1988` |
| `def_add` | `cockpit2.py:2003` |
| `catalog_publish` | `cockpit2.py:2025` |
| `def_amend` | `cockpit2.py:2051` |
| `m_add_link` | `cockpit2.py:2093` |
| `m_sample` | `cockpit2.py:2104` |
| `m_remove` | `cockpit2.py:2114` |
| `m_pin` | `cockpit2.py:2124` |
| `m_unpin` | `cockpit2.py:2135` |
| `tile_add` | `cockpit2.py:2173` |
| `indicator_activate` | `cockpit2.py:2145` |
| `tile_remove` | `cockpit2.py:2207` |
| `rov2_set` | `cockpit2.py:2217` |
| `rov2_acc_add` | `cockpit2.py:2217` |
| `rov2_acc_remove` | `cockpit2.py:2217` |
| `rov2_dom_add` | `cockpit2.py:2217` |
| `rov2_dom_remove` | `cockpit2.py:2217` |
| `backlog_add` | `cockpit2.py:2249` |
| `backlog_update_staat` | `cockpit2.py:2261` |
| `backlog_update_prioriteit` | `cockpit2.py:2273` |
| `person_edit` | `cockpit2.py:2285` |
| `person_remove` | `cockpit2.py:2302` |
| `lk_mute` | `cockpit2.py:2323` |


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
| `deliverables` | `DeliverableStore` | `deliverables.json` |
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
_25 routes · 90 dispatch-acties · 20 stores._
