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
| `/kennisbank/search` | `render_kennisbank_search` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/staging` | `render_kennisbank_staging` | `nooch_village/views/kennisbank_staging.py` |
| `/kennisbank/spel` | `render_kennisbank_spel` | `nooch_village/views/kennisbank_spel.py` |
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
| `/woordenschat` | `render_woordenschat` | `nooch_village/views/woordenschat.py` |
| `/keywords` | `render_keyword_lens` | `nooch_village/views/keyword_lens.py` |
| `/long-term-trends` | `(inline)` | `cockpit2.py` |
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
| `/claims/db.json` | `(inline)` | `cockpit2.py` |
| `/claims` | `render_claims` | `nooch_village/views/claims.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `kb_new` | `cockpit2.py:3179` |
| `kb_intake` | `cockpit2.py:3261` |
| `kb_intake_url` | `cockpit2.py:3278` |
| `kb_stage_edit` | `cockpit2.py:3297` |
| `kb_stage_delete` | `cockpit2.py:3304` |
| `kb_stage_merge` | `cockpit2.py:3310` |
| `kb_stage_commit` | `cockpit2.py:3321` |
| `kb_stage_discard` | `cockpit2.py:3335` |
| `kb_atoom_subject` | `cockpit2.py:3405` |
| `kb_atoom_edit` | `cockpit2.py:3341` |
| `kb_atoom_related` | `cockpit2.py:3348` |
| `kb_atoom_reference` | `cockpit2.py:3393` |
| `kb_insight_link` | `cockpit2.py:3360` |
| `kb_insight_unlink` | `cockpit2.py:3367` |
| `kb_meta_start` | `cockpit2.py:3373` |
| `kb_atoom_merge` | `cockpit2.py:3416` |
| `kb_atoom_archive` | `cockpit2.py:3432` |
| `kb_atoom_unarchive` | `cockpit2.py:3441` |
| `kb_atoom_naar_spel` | `cockpit2.py:3447` |
| `kb_spel_start` | `cockpit2.py:3467` |
| `kb_spel_add` | `cockpit2.py:3481` |
| `kb_spel_remove` | `cockpit2.py:3491` |
| `kb_spel_flip` | `cockpit2.py:3498` |
| `kb_spel_finish` | `cockpit2.py:3504` |
| `kb_link` | `cockpit2.py:3188` |
| `kb_unlink` | `cockpit2.py:3202` |
| `kb_annotate` | `cockpit2.py:3213` |
| `kb_evidence` | `cockpit2.py:3219` |
| `kb_discuss` | `cockpit2.py:3240` |
| `kb_reformulate` | `cockpit2.py:3246` |
| `kw_nominate` | `cockpit2.py:3515` |
| `kw_nom_accept` | `cockpit2.py:3526` |
| `kw_nom_reject` | `cockpit2.py:3544` |
| `ws_forbid` | `cockpit2.py:3574` |
| `ws_approve` | `cockpit2.py:3579` |
| `proj_add` | `cockpit2.py:1111` |
| `artefact_add` | `cockpit2.py:1139` |
| `artefact_edit` | `cockpit2.py:1180` |
| `artefact_archive` | `cockpit2.py:1204` |
| `proj_status` | `cockpit2.py:1224` |
| `proj_done` | `cockpit2.py:1242` |
| `proj_archive` | `cockpit2.py:1264` |
| `proj_unarchive` | `cockpit2.py:1274` |
| `proj_delete` | `cockpit2.py:1284` |
| `proj_edit` | `cockpit2.py:1311` |
| `proj_comment` | `cockpit2.py:1324` |
| `proj_rename` | `cockpit2.py:1334` |
| `proj_describe` | `cockpit2.py:1345` |
| `proj_doc_edit` | `cockpit2.py:1378` |
| `proj_regen_doc` | `cockpit2.py:1356` |
| `proj_settrekker` | `cockpit2.py:1391` |
| `proj_setowner` | `cockpit2.py:1428` |
| `proj_approve` | `cockpit2.py:1447` |
| `proj_discard` | `cockpit2.py:1458` |
| `proj_setlabel` | `cockpit2.py:1469` |
| `proj_setimpact` | `cockpit2.py:1484` |
| `proj_seteffort` | `cockpit2.py:1503` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1526` |
| `proj_setprivate` | `cockpit2.py:1550` |
| `proj_setdue` | `cockpit2.py:1561` |
| `attach_add` | `cockpit2.py:1572` |
| `attach_remove` | `cockpit2.py:1583` |
| `react_add` | `cockpit2.py:1593` |
| `feed_edit` | `cockpit2.py:1603` |
| `feed_remove` | `cockpit2.py:1613` |
| `wall_outcome` | `cockpit2.py:2206` |
| `notif_read` | `cockpit2.py:2304` |
| `notif_processed` | `cockpit2.py:2309` |
| `notif_outcome` | `cockpit2.py:2456` |
| `notif_klaar` | `cockpit2.py:2442` |
| `notif_delete` | `cockpit2.py:2314` |
| `notif_add` | `cockpit2.py:2426` |
| `notif_archive` | `cockpit2.py:2543` |
| `metrics2_fav` | `cockpit2.py:2320` |
| `metrics2_unfav` | `cockpit2.py:2330` |
| `metrics2_form` | `cockpit2.py:2335` |
| `metrics2_dim` | `cockpit2.py:2341` |
| `metrics2_compare` | `cockpit2.py:2348` |
| `metrics2_formula` | `cockpit2.py:2411` |
| `source_activate` | `cockpit2.py:2394` |
| `source_deactivate` | `cockpit2.py:2403` |
| `link_pursue` | `cockpit2.py:2375` |
| `link_ignore` | `cockpit2.py:2385` |
| `acc_check` | `cockpit2.py:2356` |
| `ai_reply` | `cockpit2.py:1622` |
| `proj_feed` | `cockpit2.py:1633` |
| `checklist_add` | `cockpit2.py:1663` |
| `checklist_remove` | `cockpit2.py:1674` |
| `check_add` | `cockpit2.py:1722` |
| `check_accept` | `cockpit2.py:1739` |
| `check_toggle` | `cockpit2.py:1749` |
| `check_remove` | `cockpit2.py:1759` |
| `role_assign` | `cockpit2.py:1769` |
| `role_unassign` | `cockpit2.py:1787` |
| `role_focus` | `cockpit2.py:1806` |
| `radar_approve` | `cockpit2.py:1839` |
| `radar_dismiss` | `cockpit2.py:1843` |
| `aitask_add` | `cockpit2.py:1847` |
| `aitask_remove` | `cockpit2.py:1873` |
| `persona_skill_add` | `cockpit2.py:1890` |
| `rov2_add` | `cockpit2.py:1905` |
| `rov2_add_to_group` | `cockpit2.py:1917` |
| `rov2_remove` | `cockpit2.py:1929` |
| `rov2_remove_group` | `cockpit2.py:1944` |
| `rov2_setkind` | `cockpit2.py:1962` |
| `rov2_consent` | `cockpit2.py:1975` |
| `rov2_end` | `cockpit2.py:1997` |
| `wo_open` | `cockpit2.py:2021` |
| `wo_close` | `cockpit2.py:2031` |
| `wo_presence` | `cockpit2.py:2047` |
| `wo_present_all` | `cockpit2.py:2058` |
| `wo_ag_add` | `cockpit2.py:2070` |
| `wo_ag_remove` | `cockpit2.py:2082` |
| `wo_ag_note` | `cockpit2.py:2092` |
| `wo_ag_reopen` | `cockpit2.py:2104` |
| `wo_ag_resolve` | `cockpit2.py:2180` |
| `wo_checkout` | `cockpit2.py:2548` |
| `noochie_send` | `cockpit2.py:2560` |
| `noochie_reset` | `cockpit2.py:2586` |
| `noochie_ctx` | `cockpit2.py:2593` |
| `cl_add` | `cockpit2.py:2600` |
| `cl_report` | `cockpit2.py:2618` |
| `cl_remove` | `cockpit2.py:2633` |
| `m_add_kpi` | `cockpit2.py:2643` |
| `m_add_from_def` | `cockpit2.py:2675` |
| `def_add` | `cockpit2.py:2690` |
| `catalog_publish` | `cockpit2.py:2712` |
| `def_amend` | `cockpit2.py:2738` |
| `m_add_link` | `cockpit2.py:2780` |
| `m_sample` | `cockpit2.py:2791` |
| `m_remove` | `cockpit2.py:2801` |
| `m_pin` | `cockpit2.py:2811` |
| `m_unpin` | `cockpit2.py:2822` |
| `tile_add` | `cockpit2.py:2860` |
| `indicator_activate` | `cockpit2.py:2832` |
| `tile_remove` | `cockpit2.py:2894` |
| `rov2_set` | `cockpit2.py:2904` |
| `rov2_acc_add` | `cockpit2.py:2904` |
| `rov2_acc_remove` | `cockpit2.py:2904` |
| `rov2_dom_add` | `cockpit2.py:2904` |
| `rov2_dom_remove` | `cockpit2.py:2904` |
| `backlog_add` | `cockpit2.py:2936` |
| `backlog_update_staat` | `cockpit2.py:2948` |
| `backlog_update_prioriteit` | `cockpit2.py:2960` |
| `person_edit` | `cockpit2.py:2972` |
| `person_remove` | `cockpit2.py:2989` |
| `lk_mute` | `cockpit2.py:3010` |
| `claims_term_add` | `cockpit2.py:3089` |
| `claims_work_status` | `cockpit2.py:3112` |
| `claims_to_board` | `cockpit2.py:3131` |


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
| `staging` | `StagingStore` | `kennisbank_staging.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |


---
_44 routes · 150 dispatch-acties · 29 stores._
