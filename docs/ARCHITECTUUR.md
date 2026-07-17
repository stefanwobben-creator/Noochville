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
| `/kennisbank` | `render_kennisbank` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/spel` | `render_kennisbank_spel` | `nooch_village/views/kennisbank_spel.py` |
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
| `/woordenschat` | `render_woordenschat` | `nooch_village/views/woordenschat.py` |
| `/belofte` | `render_belofte` | `nooch_village/views/belofte.py` |
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
| `kb_new` | `cockpit2.py:3034` |
| `kb_intake` | `cockpit2.py:3116` |
| `kb_intake_url` | `cockpit2.py:3133` |
| `kb_atoom_subject` | `cockpit2.py:3152` |
| `kb_spel_start` | `cockpit2.py:3170` |
| `kb_spel_add` | `cockpit2.py:3184` |
| `kb_spel_remove` | `cockpit2.py:3194` |
| `kb_spel_flip` | `cockpit2.py:3201` |
| `kb_spel_finish` | `cockpit2.py:3207` |
| `kb_link` | `cockpit2.py:3043` |
| `kb_unlink` | `cockpit2.py:3057` |
| `kb_annotate` | `cockpit2.py:3068` |
| `kb_evidence` | `cockpit2.py:3074` |
| `kb_discuss` | `cockpit2.py:3095` |
| `kb_reformulate` | `cockpit2.py:3101` |
| `proj_add` | `cockpit2.py:1099` |
| `artefact_add` | `cockpit2.py:1127` |
| `artefact_edit` | `cockpit2.py:1168` |
| `artefact_archive` | `cockpit2.py:1192` |
| `proj_status` | `cockpit2.py:1212` |
| `proj_done` | `cockpit2.py:1230` |
| `proj_archive` | `cockpit2.py:1252` |
| `proj_unarchive` | `cockpit2.py:1262` |
| `proj_delete` | `cockpit2.py:1272` |
| `proj_edit` | `cockpit2.py:1299` |
| `proj_comment` | `cockpit2.py:1312` |
| `proj_rename` | `cockpit2.py:1322` |
| `proj_describe` | `cockpit2.py:1333` |
| `proj_doc_edit` | `cockpit2.py:1366` |
| `proj_regen_doc` | `cockpit2.py:1344` |
| `proj_settrekker` | `cockpit2.py:1379` |
| `proj_setowner` | `cockpit2.py:1416` |
| `proj_approve` | `cockpit2.py:1435` |
| `proj_discard` | `cockpit2.py:1446` |
| `proj_setlabel` | `cockpit2.py:1457` |
| `proj_setimpact` | `cockpit2.py:1472` |
| `proj_seteffort` | `cockpit2.py:1491` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1514` |
| `proj_setprivate` | `cockpit2.py:1538` |
| `proj_setdue` | `cockpit2.py:1549` |
| `attach_add` | `cockpit2.py:1560` |
| `attach_remove` | `cockpit2.py:1571` |
| `react_add` | `cockpit2.py:1581` |
| `feed_edit` | `cockpit2.py:1591` |
| `feed_remove` | `cockpit2.py:1601` |
| `wall_outcome` | `cockpit2.py:2194` |
| `notif_read` | `cockpit2.py:2292` |
| `notif_processed` | `cockpit2.py:2297` |
| `notif_outcome` | `cockpit2.py:2444` |
| `notif_klaar` | `cockpit2.py:2430` |
| `notif_delete` | `cockpit2.py:2302` |
| `notif_add` | `cockpit2.py:2414` |
| `notif_archive` | `cockpit2.py:2531` |
| `metrics2_fav` | `cockpit2.py:2308` |
| `metrics2_unfav` | `cockpit2.py:2318` |
| `metrics2_form` | `cockpit2.py:2323` |
| `metrics2_dim` | `cockpit2.py:2329` |
| `metrics2_compare` | `cockpit2.py:2336` |
| `metrics2_formula` | `cockpit2.py:2399` |
| `source_activate` | `cockpit2.py:2382` |
| `source_deactivate` | `cockpit2.py:2391` |
| `link_pursue` | `cockpit2.py:2363` |
| `link_ignore` | `cockpit2.py:2373` |
| `acc_check` | `cockpit2.py:2344` |
| `ai_reply` | `cockpit2.py:1610` |
| `proj_feed` | `cockpit2.py:1621` |
| `checklist_add` | `cockpit2.py:1651` |
| `checklist_remove` | `cockpit2.py:1662` |
| `check_add` | `cockpit2.py:1710` |
| `check_accept` | `cockpit2.py:1727` |
| `check_toggle` | `cockpit2.py:1737` |
| `check_remove` | `cockpit2.py:1747` |
| `role_assign` | `cockpit2.py:1757` |
| `role_unassign` | `cockpit2.py:1775` |
| `role_focus` | `cockpit2.py:1794` |
| `radar_approve` | `cockpit2.py:1827` |
| `radar_dismiss` | `cockpit2.py:1831` |
| `aitask_add` | `cockpit2.py:1835` |
| `aitask_remove` | `cockpit2.py:1861` |
| `persona_skill_add` | `cockpit2.py:1878` |
| `rov2_add` | `cockpit2.py:1893` |
| `rov2_add_to_group` | `cockpit2.py:1905` |
| `rov2_remove` | `cockpit2.py:1917` |
| `rov2_remove_group` | `cockpit2.py:1932` |
| `rov2_setkind` | `cockpit2.py:1950` |
| `rov2_consent` | `cockpit2.py:1963` |
| `rov2_end` | `cockpit2.py:1985` |
| `wo_open` | `cockpit2.py:2009` |
| `wo_close` | `cockpit2.py:2019` |
| `wo_presence` | `cockpit2.py:2035` |
| `wo_present_all` | `cockpit2.py:2046` |
| `wo_ag_add` | `cockpit2.py:2058` |
| `wo_ag_remove` | `cockpit2.py:2070` |
| `wo_ag_note` | `cockpit2.py:2080` |
| `wo_ag_reopen` | `cockpit2.py:2092` |
| `wo_ag_resolve` | `cockpit2.py:2168` |
| `wo_checkout` | `cockpit2.py:2536` |
| `noochie_send` | `cockpit2.py:2548` |
| `noochie_reset` | `cockpit2.py:2574` |
| `noochie_ctx` | `cockpit2.py:2581` |
| `cl_add` | `cockpit2.py:2588` |
| `cl_report` | `cockpit2.py:2606` |
| `cl_remove` | `cockpit2.py:2621` |
| `m_add_kpi` | `cockpit2.py:2631` |
| `m_add_from_def` | `cockpit2.py:2663` |
| `def_add` | `cockpit2.py:2678` |
| `catalog_publish` | `cockpit2.py:2700` |
| `def_amend` | `cockpit2.py:2726` |
| `m_add_link` | `cockpit2.py:2768` |
| `m_sample` | `cockpit2.py:2779` |
| `m_remove` | `cockpit2.py:2789` |
| `m_pin` | `cockpit2.py:2799` |
| `m_unpin` | `cockpit2.py:2810` |
| `tile_add` | `cockpit2.py:2848` |
| `indicator_activate` | `cockpit2.py:2820` |
| `tile_remove` | `cockpit2.py:2882` |
| `rov2_set` | `cockpit2.py:2892` |
| `rov2_acc_add` | `cockpit2.py:2892` |
| `rov2_acc_remove` | `cockpit2.py:2892` |
| `rov2_dom_add` | `cockpit2.py:2892` |
| `rov2_dom_remove` | `cockpit2.py:2892` |
| `backlog_add` | `cockpit2.py:2924` |
| `backlog_update_staat` | `cockpit2.py:2936` |
| `backlog_update_prioriteit` | `cockpit2.py:2948` |
| `person_edit` | `cockpit2.py:2960` |
| `person_remove` | `cockpit2.py:2977` |
| `lk_mute` | `cockpit2.py:2998` |


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
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `notes` | `NotesStore` | `notes.json` |
| `spel` | `SpelStore` | `kennisbank_spel.json` |


---
_38 routes · 127 dispatch-acties · 25 stores._
