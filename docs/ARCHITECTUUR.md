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
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
| `/woordenschat` | `render_woordenschat` | `nooch_village/views/woordenschat.py` |
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
| `proj_add` | `cockpit2.py:1081` |
| `artefact_add` | `cockpit2.py:1109` |
| `artefact_edit` | `cockpit2.py:1150` |
| `artefact_archive` | `cockpit2.py:1174` |
| `proj_status` | `cockpit2.py:1194` |
| `proj_done` | `cockpit2.py:1212` |
| `proj_archive` | `cockpit2.py:1234` |
| `proj_unarchive` | `cockpit2.py:1244` |
| `proj_delete` | `cockpit2.py:1254` |
| `proj_edit` | `cockpit2.py:1281` |
| `proj_comment` | `cockpit2.py:1294` |
| `proj_rename` | `cockpit2.py:1304` |
| `proj_describe` | `cockpit2.py:1315` |
| `proj_doc_edit` | `cockpit2.py:1348` |
| `proj_regen_doc` | `cockpit2.py:1326` |
| `proj_settrekker` | `cockpit2.py:1361` |
| `proj_setowner` | `cockpit2.py:1398` |
| `proj_approve` | `cockpit2.py:1417` |
| `proj_discard` | `cockpit2.py:1428` |
| `proj_setlabel` | `cockpit2.py:1439` |
| `proj_setimpact` | `cockpit2.py:1454` |
| `proj_seteffort` | `cockpit2.py:1473` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1496` |
| `proj_setprivate` | `cockpit2.py:1520` |
| `proj_setdue` | `cockpit2.py:1531` |
| `attach_add` | `cockpit2.py:1542` |
| `attach_remove` | `cockpit2.py:1553` |
| `react_add` | `cockpit2.py:1563` |
| `feed_edit` | `cockpit2.py:1573` |
| `feed_remove` | `cockpit2.py:1583` |
| `wall_outcome` | `cockpit2.py:2176` |
| `notif_read` | `cockpit2.py:2274` |
| `notif_processed` | `cockpit2.py:2279` |
| `notif_outcome` | `cockpit2.py:2426` |
| `notif_klaar` | `cockpit2.py:2412` |
| `notif_delete` | `cockpit2.py:2284` |
| `notif_add` | `cockpit2.py:2396` |
| `notif_archive` | `cockpit2.py:2513` |
| `metrics2_fav` | `cockpit2.py:2290` |
| `metrics2_unfav` | `cockpit2.py:2300` |
| `metrics2_form` | `cockpit2.py:2305` |
| `metrics2_dim` | `cockpit2.py:2311` |
| `metrics2_compare` | `cockpit2.py:2318` |
| `metrics2_formula` | `cockpit2.py:2381` |
| `source_activate` | `cockpit2.py:2364` |
| `source_deactivate` | `cockpit2.py:2373` |
| `link_pursue` | `cockpit2.py:2345` |
| `link_ignore` | `cockpit2.py:2355` |
| `acc_check` | `cockpit2.py:2326` |
| `ai_reply` | `cockpit2.py:1592` |
| `proj_feed` | `cockpit2.py:1603` |
| `checklist_add` | `cockpit2.py:1633` |
| `checklist_remove` | `cockpit2.py:1644` |
| `check_add` | `cockpit2.py:1692` |
| `check_accept` | `cockpit2.py:1709` |
| `check_toggle` | `cockpit2.py:1719` |
| `check_remove` | `cockpit2.py:1729` |
| `role_assign` | `cockpit2.py:1739` |
| `role_unassign` | `cockpit2.py:1757` |
| `role_focus` | `cockpit2.py:1776` |
| `radar_approve` | `cockpit2.py:1809` |
| `radar_dismiss` | `cockpit2.py:1813` |
| `aitask_add` | `cockpit2.py:1817` |
| `aitask_remove` | `cockpit2.py:1843` |
| `persona_skill_add` | `cockpit2.py:1860` |
| `rov2_add` | `cockpit2.py:1875` |
| `rov2_add_to_group` | `cockpit2.py:1887` |
| `rov2_remove` | `cockpit2.py:1899` |
| `rov2_remove_group` | `cockpit2.py:1914` |
| `rov2_setkind` | `cockpit2.py:1932` |
| `rov2_consent` | `cockpit2.py:1945` |
| `rov2_end` | `cockpit2.py:1967` |
| `wo_open` | `cockpit2.py:1991` |
| `wo_close` | `cockpit2.py:2001` |
| `wo_presence` | `cockpit2.py:2017` |
| `wo_present_all` | `cockpit2.py:2028` |
| `wo_ag_add` | `cockpit2.py:2040` |
| `wo_ag_remove` | `cockpit2.py:2052` |
| `wo_ag_note` | `cockpit2.py:2062` |
| `wo_ag_reopen` | `cockpit2.py:2074` |
| `wo_ag_resolve` | `cockpit2.py:2150` |
| `wo_checkout` | `cockpit2.py:2518` |
| `noochie_send` | `cockpit2.py:2530` |
| `noochie_reset` | `cockpit2.py:2556` |
| `noochie_ctx` | `cockpit2.py:2563` |
| `cl_add` | `cockpit2.py:2570` |
| `cl_report` | `cockpit2.py:2588` |
| `cl_remove` | `cockpit2.py:2603` |
| `m_add_kpi` | `cockpit2.py:2613` |
| `m_add_from_def` | `cockpit2.py:2645` |
| `def_add` | `cockpit2.py:2660` |
| `catalog_publish` | `cockpit2.py:2682` |
| `def_amend` | `cockpit2.py:2708` |
| `m_add_link` | `cockpit2.py:2750` |
| `m_sample` | `cockpit2.py:2761` |
| `m_remove` | `cockpit2.py:2771` |
| `m_pin` | `cockpit2.py:2781` |
| `m_unpin` | `cockpit2.py:2792` |
| `tile_add` | `cockpit2.py:2830` |
| `indicator_activate` | `cockpit2.py:2802` |
| `tile_remove` | `cockpit2.py:2864` |
| `rov2_set` | `cockpit2.py:2874` |
| `rov2_acc_add` | `cockpit2.py:2874` |
| `rov2_acc_remove` | `cockpit2.py:2874` |
| `rov2_dom_add` | `cockpit2.py:2874` |
| `rov2_dom_remove` | `cockpit2.py:2874` |
| `backlog_add` | `cockpit2.py:2906` |
| `backlog_update_staat` | `cockpit2.py:2918` |
| `backlog_update_prioriteit` | `cockpit2.py:2930` |
| `person_edit` | `cockpit2.py:2942` |
| `person_remove` | `cockpit2.py:2959` |
| `lk_mute` | `cockpit2.py:2980` |


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
_35 routes · 112 dispatch-acties · 22 stores._
