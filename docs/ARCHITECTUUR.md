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
| `proj_add` | `cockpit2.py:751` |
| `artefact_add` | `cockpit2.py:779` |
| `artefact_edit` | `cockpit2.py:820` |
| `artefact_archive` | `cockpit2.py:844` |
| `proj_status` | `cockpit2.py:864` |
| `proj_done` | `cockpit2.py:882` |
| `proj_archive` | `cockpit2.py:904` |
| `proj_unarchive` | `cockpit2.py:914` |
| `proj_delete` | `cockpit2.py:924` |
| `proj_edit` | `cockpit2.py:951` |
| `proj_comment` | `cockpit2.py:964` |
| `proj_rename` | `cockpit2.py:974` |
| `proj_describe` | `cockpit2.py:985` |
| `proj_doc_edit` | `cockpit2.py:996` |
| `proj_settrekker` | `cockpit2.py:1009` |
| `proj_setowner` | `cockpit2.py:1046` |
| `proj_approve` | `cockpit2.py:1065` |
| `proj_discard` | `cockpit2.py:1076` |
| `proj_setlabel` | `cockpit2.py:1087` |
| `proj_setimpact` | `cockpit2.py:1102` |
| `proj_seteffort` | `cockpit2.py:1121` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1144` |
| `proj_setprivate` | `cockpit2.py:1168` |
| `proj_setdue` | `cockpit2.py:1179` |
| `attach_add` | `cockpit2.py:1190` |
| `attach_remove` | `cockpit2.py:1201` |
| `react_add` | `cockpit2.py:1211` |
| `feed_edit` | `cockpit2.py:1221` |
| `feed_remove` | `cockpit2.py:1231` |
| `wall_outcome` | `cockpit2.py:1799` |
| `ai_reply` | `cockpit2.py:1240` |
| `proj_feed` | `cockpit2.py:1251` |
| `checklist_add` | `cockpit2.py:1278` |
| `checklist_remove` | `cockpit2.py:1289` |
| `check_add` | `cockpit2.py:1337` |
| `check_accept` | `cockpit2.py:1354` |
| `check_toggle` | `cockpit2.py:1364` |
| `check_remove` | `cockpit2.py:1374` |
| `role_assign` | `cockpit2.py:1384` |
| `role_unassign` | `cockpit2.py:1402` |
| `role_focus` | `cockpit2.py:1421` |
| `aitask_add` | `cockpit2.py:1440` |
| `aitask_remove` | `cockpit2.py:1466` |
| `persona_skill_add` | `cockpit2.py:1483` |
| `rov2_add` | `cockpit2.py:1498` |
| `rov2_add_to_group` | `cockpit2.py:1510` |
| `rov2_remove` | `cockpit2.py:1522` |
| `rov2_remove_group` | `cockpit2.py:1537` |
| `rov2_setkind` | `cockpit2.py:1555` |
| `rov2_consent` | `cockpit2.py:1568` |
| `rov2_end` | `cockpit2.py:1590` |
| `wo_open` | `cockpit2.py:1614` |
| `wo_close` | `cockpit2.py:1624` |
| `wo_presence` | `cockpit2.py:1640` |
| `wo_present_all` | `cockpit2.py:1651` |
| `wo_ag_add` | `cockpit2.py:1663` |
| `wo_ag_remove` | `cockpit2.py:1675` |
| `wo_ag_note` | `cockpit2.py:1685` |
| `wo_ag_reopen` | `cockpit2.py:1697` |
| `wo_ag_resolve` | `cockpit2.py:1773` |
| `wo_checkout` | `cockpit2.py:1895` |
| `noochie_send` | `cockpit2.py:1907` |
| `noochie_reset` | `cockpit2.py:1933` |
| `noochie_ctx` | `cockpit2.py:1940` |
| `cl_add` | `cockpit2.py:1947` |
| `cl_report` | `cockpit2.py:1965` |
| `cl_remove` | `cockpit2.py:1980` |
| `m_add_kpi` | `cockpit2.py:1990` |
| `m_add_from_def` | `cockpit2.py:2022` |
| `def_add` | `cockpit2.py:2037` |
| `catalog_publish` | `cockpit2.py:2059` |
| `def_amend` | `cockpit2.py:2085` |
| `m_add_link` | `cockpit2.py:2127` |
| `m_sample` | `cockpit2.py:2138` |
| `m_remove` | `cockpit2.py:2148` |
| `m_pin` | `cockpit2.py:2158` |
| `m_unpin` | `cockpit2.py:2169` |
| `tile_add` | `cockpit2.py:2207` |
| `indicator_activate` | `cockpit2.py:2179` |
| `tile_remove` | `cockpit2.py:2241` |
| `rov2_set` | `cockpit2.py:2251` |
| `rov2_acc_add` | `cockpit2.py:2251` |
| `rov2_acc_remove` | `cockpit2.py:2251` |
| `rov2_dom_add` | `cockpit2.py:2251` |
| `rov2_dom_remove` | `cockpit2.py:2251` |
| `backlog_add` | `cockpit2.py:2283` |
| `backlog_update_staat` | `cockpit2.py:2295` |
| `backlog_update_prioriteit` | `cockpit2.py:2307` |
| `person_edit` | `cockpit2.py:2319` |
| `person_remove` | `cockpit2.py:2336` |
| `lk_mute` | `cockpit2.py:2357` |


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
