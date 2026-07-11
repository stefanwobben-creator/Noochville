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
| `proj_add` | `cockpit2.py:749` |
| `artefact_add` | `cockpit2.py:777` |
| `artefact_edit` | `cockpit2.py:818` |
| `artefact_archive` | `cockpit2.py:842` |
| `proj_status` | `cockpit2.py:862` |
| `proj_done` | `cockpit2.py:880` |
| `proj_archive` | `cockpit2.py:902` |
| `proj_unarchive` | `cockpit2.py:912` |
| `proj_delete` | `cockpit2.py:922` |
| `proj_edit` | `cockpit2.py:949` |
| `proj_comment` | `cockpit2.py:962` |
| `proj_rename` | `cockpit2.py:972` |
| `proj_describe` | `cockpit2.py:983` |
| `proj_doc_edit` | `cockpit2.py:994` |
| `proj_settrekker` | `cockpit2.py:1007` |
| `proj_setowner` | `cockpit2.py:1044` |
| `proj_approve` | `cockpit2.py:1063` |
| `proj_discard` | `cockpit2.py:1074` |
| `proj_setlabel` | `cockpit2.py:1085` |
| `proj_setimpact` | `cockpit2.py:1100` |
| `proj_seteffort` | `cockpit2.py:1119` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1142` |
| `proj_setprivate` | `cockpit2.py:1166` |
| `proj_setdue` | `cockpit2.py:1177` |
| `attach_add` | `cockpit2.py:1188` |
| `attach_remove` | `cockpit2.py:1199` |
| `react_add` | `cockpit2.py:1209` |
| `feed_edit` | `cockpit2.py:1219` |
| `feed_remove` | `cockpit2.py:1229` |
| `wall_outcome` | `cockpit2.py:1797` |
| `ai_reply` | `cockpit2.py:1238` |
| `proj_feed` | `cockpit2.py:1249` |
| `checklist_add` | `cockpit2.py:1276` |
| `checklist_remove` | `cockpit2.py:1287` |
| `check_add` | `cockpit2.py:1335` |
| `check_accept` | `cockpit2.py:1352` |
| `check_toggle` | `cockpit2.py:1362` |
| `check_remove` | `cockpit2.py:1372` |
| `role_assign` | `cockpit2.py:1382` |
| `role_unassign` | `cockpit2.py:1400` |
| `role_focus` | `cockpit2.py:1419` |
| `aitask_add` | `cockpit2.py:1438` |
| `aitask_remove` | `cockpit2.py:1464` |
| `persona_skill_add` | `cockpit2.py:1481` |
| `rov2_add` | `cockpit2.py:1496` |
| `rov2_add_to_group` | `cockpit2.py:1508` |
| `rov2_remove` | `cockpit2.py:1520` |
| `rov2_remove_group` | `cockpit2.py:1535` |
| `rov2_setkind` | `cockpit2.py:1553` |
| `rov2_consent` | `cockpit2.py:1566` |
| `rov2_end` | `cockpit2.py:1588` |
| `wo_open` | `cockpit2.py:1612` |
| `wo_close` | `cockpit2.py:1622` |
| `wo_presence` | `cockpit2.py:1638` |
| `wo_present_all` | `cockpit2.py:1649` |
| `wo_ag_add` | `cockpit2.py:1661` |
| `wo_ag_remove` | `cockpit2.py:1673` |
| `wo_ag_note` | `cockpit2.py:1683` |
| `wo_ag_reopen` | `cockpit2.py:1695` |
| `wo_ag_resolve` | `cockpit2.py:1771` |
| `wo_checkout` | `cockpit2.py:1893` |
| `noochie_send` | `cockpit2.py:1905` |
| `noochie_reset` | `cockpit2.py:1931` |
| `noochie_ctx` | `cockpit2.py:1938` |
| `cl_add` | `cockpit2.py:1945` |
| `cl_report` | `cockpit2.py:1963` |
| `cl_remove` | `cockpit2.py:1978` |
| `m_add_kpi` | `cockpit2.py:1988` |
| `m_add_from_def` | `cockpit2.py:2020` |
| `def_add` | `cockpit2.py:2035` |
| `catalog_publish` | `cockpit2.py:2057` |
| `def_amend` | `cockpit2.py:2083` |
| `m_add_link` | `cockpit2.py:2125` |
| `m_sample` | `cockpit2.py:2136` |
| `m_remove` | `cockpit2.py:2146` |
| `m_pin` | `cockpit2.py:2156` |
| `m_unpin` | `cockpit2.py:2167` |
| `tile_add` | `cockpit2.py:2205` |
| `indicator_activate` | `cockpit2.py:2177` |
| `tile_remove` | `cockpit2.py:2239` |
| `rov2_set` | `cockpit2.py:2249` |
| `rov2_acc_add` | `cockpit2.py:2249` |
| `rov2_acc_remove` | `cockpit2.py:2249` |
| `rov2_dom_add` | `cockpit2.py:2249` |
| `rov2_dom_remove` | `cockpit2.py:2249` |
| `backlog_add` | `cockpit2.py:2281` |
| `backlog_update_staat` | `cockpit2.py:2293` |
| `backlog_update_prioriteit` | `cockpit2.py:2305` |
| `person_edit` | `cockpit2.py:2317` |
| `person_remove` | `cockpit2.py:2334` |
| `lk_mute` | `cockpit2.py:2355` |


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
_25 routes · 91 dispatch-acties · 20 stores._
