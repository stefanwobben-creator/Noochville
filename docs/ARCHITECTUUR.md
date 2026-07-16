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
| `kb_new` | `cockpit2.py:3030` |
| `kb_link` | `cockpit2.py:3039` |
| `kb_unlink` | `cockpit2.py:3053` |
| `kb_annotate` | `cockpit2.py:3064` |
| `kb_evidence` | `cockpit2.py:3070` |
| `kb_discuss` | `cockpit2.py:3091` |
| `kb_reformulate` | `cockpit2.py:3097` |
| `proj_add` | `cockpit2.py:1095` |
| `artefact_add` | `cockpit2.py:1123` |
| `artefact_edit` | `cockpit2.py:1164` |
| `artefact_archive` | `cockpit2.py:1188` |
| `proj_status` | `cockpit2.py:1208` |
| `proj_done` | `cockpit2.py:1226` |
| `proj_archive` | `cockpit2.py:1248` |
| `proj_unarchive` | `cockpit2.py:1258` |
| `proj_delete` | `cockpit2.py:1268` |
| `proj_edit` | `cockpit2.py:1295` |
| `proj_comment` | `cockpit2.py:1308` |
| `proj_rename` | `cockpit2.py:1318` |
| `proj_describe` | `cockpit2.py:1329` |
| `proj_doc_edit` | `cockpit2.py:1362` |
| `proj_regen_doc` | `cockpit2.py:1340` |
| `proj_settrekker` | `cockpit2.py:1375` |
| `proj_setowner` | `cockpit2.py:1412` |
| `proj_approve` | `cockpit2.py:1431` |
| `proj_discard` | `cockpit2.py:1442` |
| `proj_setlabel` | `cockpit2.py:1453` |
| `proj_setimpact` | `cockpit2.py:1468` |
| `proj_seteffort` | `cockpit2.py:1487` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1510` |
| `proj_setprivate` | `cockpit2.py:1534` |
| `proj_setdue` | `cockpit2.py:1545` |
| `attach_add` | `cockpit2.py:1556` |
| `attach_remove` | `cockpit2.py:1567` |
| `react_add` | `cockpit2.py:1577` |
| `feed_edit` | `cockpit2.py:1587` |
| `feed_remove` | `cockpit2.py:1597` |
| `wall_outcome` | `cockpit2.py:2190` |
| `notif_read` | `cockpit2.py:2288` |
| `notif_processed` | `cockpit2.py:2293` |
| `notif_outcome` | `cockpit2.py:2440` |
| `notif_klaar` | `cockpit2.py:2426` |
| `notif_delete` | `cockpit2.py:2298` |
| `notif_add` | `cockpit2.py:2410` |
| `notif_archive` | `cockpit2.py:2527` |
| `metrics2_fav` | `cockpit2.py:2304` |
| `metrics2_unfav` | `cockpit2.py:2314` |
| `metrics2_form` | `cockpit2.py:2319` |
| `metrics2_dim` | `cockpit2.py:2325` |
| `metrics2_compare` | `cockpit2.py:2332` |
| `metrics2_formula` | `cockpit2.py:2395` |
| `source_activate` | `cockpit2.py:2378` |
| `source_deactivate` | `cockpit2.py:2387` |
| `link_pursue` | `cockpit2.py:2359` |
| `link_ignore` | `cockpit2.py:2369` |
| `acc_check` | `cockpit2.py:2340` |
| `ai_reply` | `cockpit2.py:1606` |
| `proj_feed` | `cockpit2.py:1617` |
| `checklist_add` | `cockpit2.py:1647` |
| `checklist_remove` | `cockpit2.py:1658` |
| `check_add` | `cockpit2.py:1706` |
| `check_accept` | `cockpit2.py:1723` |
| `check_toggle` | `cockpit2.py:1733` |
| `check_remove` | `cockpit2.py:1743` |
| `role_assign` | `cockpit2.py:1753` |
| `role_unassign` | `cockpit2.py:1771` |
| `role_focus` | `cockpit2.py:1790` |
| `radar_approve` | `cockpit2.py:1823` |
| `radar_dismiss` | `cockpit2.py:1827` |
| `aitask_add` | `cockpit2.py:1831` |
| `aitask_remove` | `cockpit2.py:1857` |
| `persona_skill_add` | `cockpit2.py:1874` |
| `rov2_add` | `cockpit2.py:1889` |
| `rov2_add_to_group` | `cockpit2.py:1901` |
| `rov2_remove` | `cockpit2.py:1913` |
| `rov2_remove_group` | `cockpit2.py:1928` |
| `rov2_setkind` | `cockpit2.py:1946` |
| `rov2_consent` | `cockpit2.py:1959` |
| `rov2_end` | `cockpit2.py:1981` |
| `wo_open` | `cockpit2.py:2005` |
| `wo_close` | `cockpit2.py:2015` |
| `wo_presence` | `cockpit2.py:2031` |
| `wo_present_all` | `cockpit2.py:2042` |
| `wo_ag_add` | `cockpit2.py:2054` |
| `wo_ag_remove` | `cockpit2.py:2066` |
| `wo_ag_note` | `cockpit2.py:2076` |
| `wo_ag_reopen` | `cockpit2.py:2088` |
| `wo_ag_resolve` | `cockpit2.py:2164` |
| `wo_checkout` | `cockpit2.py:2532` |
| `noochie_send` | `cockpit2.py:2544` |
| `noochie_reset` | `cockpit2.py:2570` |
| `noochie_ctx` | `cockpit2.py:2577` |
| `cl_add` | `cockpit2.py:2584` |
| `cl_report` | `cockpit2.py:2602` |
| `cl_remove` | `cockpit2.py:2617` |
| `m_add_kpi` | `cockpit2.py:2627` |
| `m_add_from_def` | `cockpit2.py:2659` |
| `def_add` | `cockpit2.py:2674` |
| `catalog_publish` | `cockpit2.py:2696` |
| `def_amend` | `cockpit2.py:2722` |
| `m_add_link` | `cockpit2.py:2764` |
| `m_sample` | `cockpit2.py:2775` |
| `m_remove` | `cockpit2.py:2785` |
| `m_pin` | `cockpit2.py:2795` |
| `m_unpin` | `cockpit2.py:2806` |
| `tile_add` | `cockpit2.py:2844` |
| `indicator_activate` | `cockpit2.py:2816` |
| `tile_remove` | `cockpit2.py:2878` |
| `rov2_set` | `cockpit2.py:2888` |
| `rov2_acc_add` | `cockpit2.py:2888` |
| `rov2_acc_remove` | `cockpit2.py:2888` |
| `rov2_dom_add` | `cockpit2.py:2888` |
| `rov2_dom_remove` | `cockpit2.py:2888` |
| `backlog_add` | `cockpit2.py:2920` |
| `backlog_update_staat` | `cockpit2.py:2932` |
| `backlog_update_prioriteit` | `cockpit2.py:2944` |
| `person_edit` | `cockpit2.py:2956` |
| `person_remove` | `cockpit2.py:2973` |
| `lk_mute` | `cockpit2.py:2994` |


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


---
_37 routes · 119 dispatch-acties · 24 stores._
