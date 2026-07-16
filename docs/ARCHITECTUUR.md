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
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/inzichten` | `render_kennislaag` | `nooch_village/views/kennislaag.py` |
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
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
| `proj_add` | `cockpit2.py:1079` |
| `artefact_add` | `cockpit2.py:1107` |
| `artefact_edit` | `cockpit2.py:1148` |
| `artefact_archive` | `cockpit2.py:1172` |
| `proj_status` | `cockpit2.py:1192` |
| `proj_done` | `cockpit2.py:1210` |
| `proj_archive` | `cockpit2.py:1232` |
| `proj_unarchive` | `cockpit2.py:1242` |
| `proj_delete` | `cockpit2.py:1252` |
| `proj_edit` | `cockpit2.py:1279` |
| `proj_comment` | `cockpit2.py:1292` |
| `proj_rename` | `cockpit2.py:1302` |
| `proj_describe` | `cockpit2.py:1313` |
| `proj_doc_edit` | `cockpit2.py:1346` |
| `proj_regen_doc` | `cockpit2.py:1324` |
| `proj_settrekker` | `cockpit2.py:1359` |
| `proj_setowner` | `cockpit2.py:1396` |
| `proj_approve` | `cockpit2.py:1415` |
| `proj_discard` | `cockpit2.py:1426` |
| `proj_setlabel` | `cockpit2.py:1437` |
| `proj_setimpact` | `cockpit2.py:1452` |
| `proj_seteffort` | `cockpit2.py:1471` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1494` |
| `proj_setprivate` | `cockpit2.py:1518` |
| `proj_setdue` | `cockpit2.py:1529` |
| `attach_add` | `cockpit2.py:1540` |
| `attach_remove` | `cockpit2.py:1551` |
| `react_add` | `cockpit2.py:1561` |
| `feed_edit` | `cockpit2.py:1571` |
| `feed_remove` | `cockpit2.py:1581` |
| `wall_outcome` | `cockpit2.py:2174` |
| `notif_read` | `cockpit2.py:2272` |
| `notif_processed` | `cockpit2.py:2277` |
| `notif_outcome` | `cockpit2.py:2405` |
| `notif_klaar` | `cockpit2.py:2391` |
| `notif_delete` | `cockpit2.py:2282` |
| `notif_add` | `cockpit2.py:2375` |
| `notif_archive` | `cockpit2.py:2492` |
| `metrics2_fav` | `cockpit2.py:2288` |
| `metrics2_unfav` | `cockpit2.py:2298` |
| `metrics2_form` | `cockpit2.py:2303` |
| `metrics2_dim` | `cockpit2.py:2309` |
| `metrics2_compare` | `cockpit2.py:2316` |
| `metrics2_formula` | `cockpit2.py:2360` |
| `source_activate` | `cockpit2.py:2343` |
| `source_deactivate` | `cockpit2.py:2352` |
| `link_pursue` | `cockpit2.py:2324` |
| `link_ignore` | `cockpit2.py:2334` |
| `ai_reply` | `cockpit2.py:1590` |
| `proj_feed` | `cockpit2.py:1601` |
| `checklist_add` | `cockpit2.py:1631` |
| `checklist_remove` | `cockpit2.py:1642` |
| `check_add` | `cockpit2.py:1690` |
| `check_accept` | `cockpit2.py:1707` |
| `check_toggle` | `cockpit2.py:1717` |
| `check_remove` | `cockpit2.py:1727` |
| `role_assign` | `cockpit2.py:1737` |
| `role_unassign` | `cockpit2.py:1755` |
| `role_focus` | `cockpit2.py:1774` |
| `radar_approve` | `cockpit2.py:1807` |
| `radar_dismiss` | `cockpit2.py:1811` |
| `aitask_add` | `cockpit2.py:1815` |
| `aitask_remove` | `cockpit2.py:1841` |
| `persona_skill_add` | `cockpit2.py:1858` |
| `rov2_add` | `cockpit2.py:1873` |
| `rov2_add_to_group` | `cockpit2.py:1885` |
| `rov2_remove` | `cockpit2.py:1897` |
| `rov2_remove_group` | `cockpit2.py:1912` |
| `rov2_setkind` | `cockpit2.py:1930` |
| `rov2_consent` | `cockpit2.py:1943` |
| `rov2_end` | `cockpit2.py:1965` |
| `wo_open` | `cockpit2.py:1989` |
| `wo_close` | `cockpit2.py:1999` |
| `wo_presence` | `cockpit2.py:2015` |
| `wo_present_all` | `cockpit2.py:2026` |
| `wo_ag_add` | `cockpit2.py:2038` |
| `wo_ag_remove` | `cockpit2.py:2050` |
| `wo_ag_note` | `cockpit2.py:2060` |
| `wo_ag_reopen` | `cockpit2.py:2072` |
| `wo_ag_resolve` | `cockpit2.py:2148` |
| `wo_checkout` | `cockpit2.py:2497` |
| `noochie_send` | `cockpit2.py:2509` |
| `noochie_reset` | `cockpit2.py:2535` |
| `noochie_ctx` | `cockpit2.py:2542` |
| `cl_add` | `cockpit2.py:2549` |
| `cl_report` | `cockpit2.py:2567` |
| `cl_remove` | `cockpit2.py:2582` |
| `m_add_kpi` | `cockpit2.py:2592` |
| `m_add_from_def` | `cockpit2.py:2624` |
| `def_add` | `cockpit2.py:2639` |
| `catalog_publish` | `cockpit2.py:2661` |
| `def_amend` | `cockpit2.py:2687` |
| `m_add_link` | `cockpit2.py:2729` |
| `m_sample` | `cockpit2.py:2740` |
| `m_remove` | `cockpit2.py:2750` |
| `m_pin` | `cockpit2.py:2760` |
| `m_unpin` | `cockpit2.py:2771` |
| `tile_add` | `cockpit2.py:2809` |
| `indicator_activate` | `cockpit2.py:2781` |
| `tile_remove` | `cockpit2.py:2843` |
| `rov2_set` | `cockpit2.py:2853` |
| `rov2_acc_add` | `cockpit2.py:2853` |
| `rov2_acc_remove` | `cockpit2.py:2853` |
| `rov2_dom_add` | `cockpit2.py:2853` |
| `rov2_dom_remove` | `cockpit2.py:2853` |
| `backlog_add` | `cockpit2.py:2885` |
| `backlog_update_staat` | `cockpit2.py:2897` |
| `backlog_update_prioriteit` | `cockpit2.py:2909` |
| `person_edit` | `cockpit2.py:2921` |
| `person_remove` | `cockpit2.py:2938` |
| `lk_mute` | `cockpit2.py:2959` |


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
_33 routes · 111 dispatch-acties · 22 stores._
