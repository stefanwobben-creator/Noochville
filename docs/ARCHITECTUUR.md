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
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/metrics2` | `render_metrics2` | `nooch_village/views/metrics2.py` |
| `/inbox/verwerk` | `render_verwerk` | `nooch_village/views/inbox.py` |
| `/catalog` | `render_catalog` | `nooch_village/views/catalog.py` |
| `/catalogus_koppelen` | `(inline)` | `cockpit2.py` |
| `/kpi_new` | `render_kpi_composer` | `nooch_village/views/metrics.py` |
| `/noochie` | `render_noochie` | `nooch_village/views/noochie.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/livekit-presence` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:1076` |
| `artefact_add` | `cockpit2.py:1104` |
| `artefact_edit` | `cockpit2.py:1145` |
| `artefact_archive` | `cockpit2.py:1169` |
| `proj_status` | `cockpit2.py:1189` |
| `proj_done` | `cockpit2.py:1207` |
| `proj_archive` | `cockpit2.py:1229` |
| `proj_unarchive` | `cockpit2.py:1239` |
| `proj_delete` | `cockpit2.py:1249` |
| `proj_edit` | `cockpit2.py:1276` |
| `proj_comment` | `cockpit2.py:1289` |
| `proj_rename` | `cockpit2.py:1299` |
| `proj_describe` | `cockpit2.py:1310` |
| `proj_doc_edit` | `cockpit2.py:1343` |
| `proj_regen_doc` | `cockpit2.py:1321` |
| `proj_settrekker` | `cockpit2.py:1356` |
| `proj_setowner` | `cockpit2.py:1393` |
| `proj_approve` | `cockpit2.py:1412` |
| `proj_discard` | `cockpit2.py:1423` |
| `proj_setlabel` | `cockpit2.py:1434` |
| `proj_setimpact` | `cockpit2.py:1449` |
| `proj_seteffort` | `cockpit2.py:1468` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1491` |
| `proj_setprivate` | `cockpit2.py:1515` |
| `proj_setdue` | `cockpit2.py:1526` |
| `attach_add` | `cockpit2.py:1537` |
| `attach_remove` | `cockpit2.py:1548` |
| `react_add` | `cockpit2.py:1558` |
| `feed_edit` | `cockpit2.py:1568` |
| `feed_remove` | `cockpit2.py:1578` |
| `wall_outcome` | `cockpit2.py:2171` |
| `notif_read` | `cockpit2.py:2269` |
| `notif_processed` | `cockpit2.py:2274` |
| `notif_outcome` | `cockpit2.py:2336` |
| `notif_klaar` | `cockpit2.py:2322` |
| `notif_delete` | `cockpit2.py:2279` |
| `notif_add` | `cockpit2.py:2306` |
| `notif_archive` | `cockpit2.py:2423` |
| `metrics2_fav` | `cockpit2.py:2285` |
| `metrics2_unfav` | `cockpit2.py:2295` |
| `metrics2_form` | `cockpit2.py:2300` |
| `ai_reply` | `cockpit2.py:1587` |
| `proj_feed` | `cockpit2.py:1598` |
| `checklist_add` | `cockpit2.py:1628` |
| `checklist_remove` | `cockpit2.py:1639` |
| `check_add` | `cockpit2.py:1687` |
| `check_accept` | `cockpit2.py:1704` |
| `check_toggle` | `cockpit2.py:1714` |
| `check_remove` | `cockpit2.py:1724` |
| `role_assign` | `cockpit2.py:1734` |
| `role_unassign` | `cockpit2.py:1752` |
| `role_focus` | `cockpit2.py:1771` |
| `radar_approve` | `cockpit2.py:1804` |
| `radar_dismiss` | `cockpit2.py:1808` |
| `aitask_add` | `cockpit2.py:1812` |
| `aitask_remove` | `cockpit2.py:1838` |
| `persona_skill_add` | `cockpit2.py:1855` |
| `rov2_add` | `cockpit2.py:1870` |
| `rov2_add_to_group` | `cockpit2.py:1882` |
| `rov2_remove` | `cockpit2.py:1894` |
| `rov2_remove_group` | `cockpit2.py:1909` |
| `rov2_setkind` | `cockpit2.py:1927` |
| `rov2_consent` | `cockpit2.py:1940` |
| `rov2_end` | `cockpit2.py:1962` |
| `wo_open` | `cockpit2.py:1986` |
| `wo_close` | `cockpit2.py:1996` |
| `wo_presence` | `cockpit2.py:2012` |
| `wo_present_all` | `cockpit2.py:2023` |
| `wo_ag_add` | `cockpit2.py:2035` |
| `wo_ag_remove` | `cockpit2.py:2047` |
| `wo_ag_note` | `cockpit2.py:2057` |
| `wo_ag_reopen` | `cockpit2.py:2069` |
| `wo_ag_resolve` | `cockpit2.py:2145` |
| `wo_checkout` | `cockpit2.py:2428` |
| `noochie_send` | `cockpit2.py:2440` |
| `noochie_reset` | `cockpit2.py:2466` |
| `noochie_ctx` | `cockpit2.py:2473` |
| `cl_add` | `cockpit2.py:2480` |
| `cl_report` | `cockpit2.py:2498` |
| `cl_remove` | `cockpit2.py:2513` |
| `m_add_kpi` | `cockpit2.py:2523` |
| `m_add_from_def` | `cockpit2.py:2555` |
| `def_add` | `cockpit2.py:2570` |
| `catalog_publish` | `cockpit2.py:2592` |
| `def_amend` | `cockpit2.py:2618` |
| `m_add_link` | `cockpit2.py:2660` |
| `m_sample` | `cockpit2.py:2671` |
| `m_remove` | `cockpit2.py:2681` |
| `m_pin` | `cockpit2.py:2691` |
| `m_unpin` | `cockpit2.py:2702` |
| `tile_add` | `cockpit2.py:2740` |
| `indicator_activate` | `cockpit2.py:2712` |
| `tile_remove` | `cockpit2.py:2774` |
| `rov2_set` | `cockpit2.py:2784` |
| `rov2_acc_add` | `cockpit2.py:2784` |
| `rov2_acc_remove` | `cockpit2.py:2784` |
| `rov2_dom_add` | `cockpit2.py:2784` |
| `rov2_dom_remove` | `cockpit2.py:2784` |
| `backlog_add` | `cockpit2.py:2816` |
| `backlog_update_staat` | `cockpit2.py:2828` |
| `backlog_update_prioriteit` | `cockpit2.py:2840` |
| `person_edit` | `cockpit2.py:2852` |
| `person_remove` | `cockpit2.py:2869` |
| `lk_mute` | `cockpit2.py:2890` |


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
| `radar` | `RadarStore` | `radar.json` |


---
_30 routes · 104 dispatch-acties · 22 stores._
