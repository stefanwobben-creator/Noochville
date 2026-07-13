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
| `proj_add` | `cockpit2.py:769` |
| `artefact_add` | `cockpit2.py:797` |
| `artefact_edit` | `cockpit2.py:838` |
| `artefact_archive` | `cockpit2.py:862` |
| `proj_status` | `cockpit2.py:882` |
| `proj_done` | `cockpit2.py:900` |
| `proj_archive` | `cockpit2.py:922` |
| `proj_unarchive` | `cockpit2.py:932` |
| `proj_delete` | `cockpit2.py:942` |
| `proj_edit` | `cockpit2.py:969` |
| `proj_comment` | `cockpit2.py:982` |
| `proj_rename` | `cockpit2.py:992` |
| `proj_describe` | `cockpit2.py:1003` |
| `proj_doc_edit` | `cockpit2.py:1014` |
| `proj_settrekker` | `cockpit2.py:1027` |
| `proj_setowner` | `cockpit2.py:1064` |
| `proj_approve` | `cockpit2.py:1083` |
| `proj_discard` | `cockpit2.py:1094` |
| `proj_setlabel` | `cockpit2.py:1105` |
| `proj_setimpact` | `cockpit2.py:1120` |
| `proj_seteffort` | `cockpit2.py:1139` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1162` |
| `proj_setprivate` | `cockpit2.py:1186` |
| `proj_setdue` | `cockpit2.py:1197` |
| `attach_add` | `cockpit2.py:1208` |
| `attach_remove` | `cockpit2.py:1219` |
| `react_add` | `cockpit2.py:1229` |
| `feed_edit` | `cockpit2.py:1239` |
| `feed_remove` | `cockpit2.py:1249` |
| `wall_outcome` | `cockpit2.py:1820` |
| `ai_reply` | `cockpit2.py:1258` |
| `proj_feed` | `cockpit2.py:1269` |
| `checklist_add` | `cockpit2.py:1299` |
| `checklist_remove` | `cockpit2.py:1310` |
| `check_add` | `cockpit2.py:1358` |
| `check_accept` | `cockpit2.py:1375` |
| `check_toggle` | `cockpit2.py:1385` |
| `check_remove` | `cockpit2.py:1395` |
| `role_assign` | `cockpit2.py:1405` |
| `role_unassign` | `cockpit2.py:1423` |
| `role_focus` | `cockpit2.py:1442` |
| `aitask_add` | `cockpit2.py:1461` |
| `aitask_remove` | `cockpit2.py:1487` |
| `persona_skill_add` | `cockpit2.py:1504` |
| `rov2_add` | `cockpit2.py:1519` |
| `rov2_add_to_group` | `cockpit2.py:1531` |
| `rov2_remove` | `cockpit2.py:1543` |
| `rov2_remove_group` | `cockpit2.py:1558` |
| `rov2_setkind` | `cockpit2.py:1576` |
| `rov2_consent` | `cockpit2.py:1589` |
| `rov2_end` | `cockpit2.py:1611` |
| `wo_open` | `cockpit2.py:1635` |
| `wo_close` | `cockpit2.py:1645` |
| `wo_presence` | `cockpit2.py:1661` |
| `wo_present_all` | `cockpit2.py:1672` |
| `wo_ag_add` | `cockpit2.py:1684` |
| `wo_ag_remove` | `cockpit2.py:1696` |
| `wo_ag_note` | `cockpit2.py:1706` |
| `wo_ag_reopen` | `cockpit2.py:1718` |
| `wo_ag_resolve` | `cockpit2.py:1794` |
| `wo_checkout` | `cockpit2.py:1916` |
| `noochie_send` | `cockpit2.py:1928` |
| `noochie_reset` | `cockpit2.py:1954` |
| `noochie_ctx` | `cockpit2.py:1961` |
| `cl_add` | `cockpit2.py:1968` |
| `cl_report` | `cockpit2.py:1986` |
| `cl_remove` | `cockpit2.py:2001` |
| `m_add_kpi` | `cockpit2.py:2011` |
| `m_add_from_def` | `cockpit2.py:2043` |
| `def_add` | `cockpit2.py:2058` |
| `catalog_publish` | `cockpit2.py:2080` |
| `def_amend` | `cockpit2.py:2106` |
| `m_add_link` | `cockpit2.py:2148` |
| `m_sample` | `cockpit2.py:2159` |
| `m_remove` | `cockpit2.py:2169` |
| `m_pin` | `cockpit2.py:2179` |
| `m_unpin` | `cockpit2.py:2190` |
| `tile_add` | `cockpit2.py:2228` |
| `indicator_activate` | `cockpit2.py:2200` |
| `tile_remove` | `cockpit2.py:2262` |
| `rov2_set` | `cockpit2.py:2272` |
| `rov2_acc_add` | `cockpit2.py:2272` |
| `rov2_acc_remove` | `cockpit2.py:2272` |
| `rov2_dom_add` | `cockpit2.py:2272` |
| `rov2_dom_remove` | `cockpit2.py:2272` |
| `backlog_add` | `cockpit2.py:2304` |
| `backlog_update_staat` | `cockpit2.py:2316` |
| `backlog_update_prioriteit` | `cockpit2.py:2328` |
| `person_edit` | `cockpit2.py:2340` |
| `person_remove` | `cockpit2.py:2357` |
| `lk_mute` | `cockpit2.py:2378` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `evidence` | `EvidenceLedger` | `evidence_ledger.jsonl` |
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
_25 routes · 91 dispatch-acties · 21 stores._
