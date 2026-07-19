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
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
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
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `kb_new` | `cockpit2.py:3541` |
| `kb_intake` | `cockpit2.py:3623` |
| `kb_intake_url` | `cockpit2.py:3640` |
| `kb_stage_edit` | `cockpit2.py:3659` |
| `kb_stage_delete` | `cockpit2.py:3671` |
| `kb_stage_merge` | `cockpit2.py:3677` |
| `kb_stage_commit` | `cockpit2.py:3688` |
| `kb_stage_discard` | `cockpit2.py:3708` |
| `kb_atoom_subject` | `cockpit2.py:3784` |
| `kb_atoom_edit` | `cockpit2.py:3714` |
| `kb_atoom_related` | `cockpit2.py:3721` |
| `kb_atoom_reference` | `cockpit2.py:3766` |
| `kb_insight_link` | `cockpit2.py:3733` |
| `kb_insight_unlink` | `cockpit2.py:3740` |
| `kb_meta_start` | `cockpit2.py:3746` |
| `kb_atoom_merge` | `cockpit2.py:3795` |
| `kb_atoom_archive` | `cockpit2.py:3816` |
| `kb_atoom_unarchive` | `cockpit2.py:3825` |
| `kb_atoom_naar_spel` | `cockpit2.py:3831` |
| `kb_spel_start` | `cockpit2.py:3852` |
| `kb_spel_add` | `cockpit2.py:3866` |
| `kb_spel_remove` | `cockpit2.py:3876` |
| `kb_spel_flip` | `cockpit2.py:3883` |
| `kb_spel_finish` | `cockpit2.py:3889` |
| `kb_link` | `cockpit2.py:3550` |
| `kb_unlink` | `cockpit2.py:3564` |
| `kb_annotate` | `cockpit2.py:3575` |
| `kb_evidence` | `cockpit2.py:3581` |
| `kb_discuss` | `cockpit2.py:3602` |
| `kb_reformulate` | `cockpit2.py:3608` |
| `kw_nominate` | `cockpit2.py:3900` |
| `kw_nom_accept` | `cockpit2.py:3911` |
| `kw_nom_reject` | `cockpit2.py:3929` |
| `ws_forbid` | `cockpit2.py:3959` |
| `ws_approve` | `cockpit2.py:3964` |
| `proj_add` | `cockpit2.py:1124` |
| `artefact_add` | `cockpit2.py:1152` |
| `artefact_edit` | `cockpit2.py:1193` |
| `artefact_archive` | `cockpit2.py:1217` |
| `proj_status` | `cockpit2.py:1237` |
| `proj_done` | `cockpit2.py:1255` |
| `proj_archive` | `cockpit2.py:1290` |
| `proj_unarchive` | `cockpit2.py:1300` |
| `proj_delete` | `cockpit2.py:1310` |
| `proj_edit` | `cockpit2.py:1337` |
| `proj_comment` | `cockpit2.py:1350` |
| `proj_rename` | `cockpit2.py:1360` |
| `proj_describe` | `cockpit2.py:1371` |
| `proj_doc_edit` | `cockpit2.py:1404` |
| `proj_regen_doc` | `cockpit2.py:1382` |
| `proj_settrekker` | `cockpit2.py:1417` |
| `proj_setowner` | `cockpit2.py:1454` |
| `proj_approve` | `cockpit2.py:1473` |
| `proj_discard` | `cockpit2.py:1484` |
| `proj_setlabel` | `cockpit2.py:1495` |
| `proj_setimpact` | `cockpit2.py:1510` |
| `proj_seteffort` | `cockpit2.py:1529` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1552` |
| `proj_setprivate` | `cockpit2.py:1576` |
| `proj_setdue` | `cockpit2.py:1587` |
| `attach_add` | `cockpit2.py:1598` |
| `attach_remove` | `cockpit2.py:1609` |
| `react_add` | `cockpit2.py:1619` |
| `feed_edit` | `cockpit2.py:1629` |
| `feed_remove` | `cockpit2.py:1639` |
| `wall_outcome` | `cockpit2.py:2539` |
| `notif_read` | `cockpit2.py:2637` |
| `notif_processed` | `cockpit2.py:2642` |
| `notif_outcome` | `cockpit2.py:2789` |
| `notif_klaar` | `cockpit2.py:2775` |
| `notif_delete` | `cockpit2.py:2647` |
| `notif_add` | `cockpit2.py:2759` |
| `notif_archive` | `cockpit2.py:2876` |
| `metrics2_fav` | `cockpit2.py:2653` |
| `metrics2_unfav` | `cockpit2.py:2663` |
| `metrics2_form` | `cockpit2.py:2668` |
| `metrics2_dim` | `cockpit2.py:2674` |
| `metrics2_compare` | `cockpit2.py:2681` |
| `metrics2_formula` | `cockpit2.py:2744` |
| `source_activate` | `cockpit2.py:2727` |
| `source_deactivate` | `cockpit2.py:2736` |
| `link_pursue` | `cockpit2.py:2708` |
| `link_ignore` | `cockpit2.py:2718` |
| `acc_check` | `cockpit2.py:2689` |
| `ai_reply` | `cockpit2.py:1648` |
| `proj_feed` | `cockpit2.py:1659` |
| `checklist_add` | `cockpit2.py:1689` |
| `checklist_remove` | `cockpit2.py:1700` |
| `check_add` | `cockpit2.py:1748` |
| `check_accept` | `cockpit2.py:1765` |
| `check_toggle` | `cockpit2.py:1775` |
| `check_remove` | `cockpit2.py:1785` |
| `role_assign` | `cockpit2.py:1795` |
| `role_unassign` | `cockpit2.py:1813` |
| `role_focus` | `cockpit2.py:1832` |
| `radar_approve` | `cockpit2.py:1865` |
| `radar_dismiss` | `cockpit2.py:1875` |
| `radar_promote` | `cockpit2.py:1879` |
| `radar_merge` | `cockpit2.py:1899` |
| `radar_koppel` | `cockpit2.py:1915` |
| `kb_stage_koppel` | `cockpit2.py:1942` |
| `aitask_add` | `cockpit2.py:1980` |
| `aitask_remove` | `cockpit2.py:2011` |
| `skilllink_add` | `cockpit2.py:2039` |
| `means_gap_add` | `cockpit2.py:2069` |
| `persona_skill_add` | `cockpit2.py:2223` |
| `rov2_add` | `cockpit2.py:2238` |
| `rov2_add_to_group` | `cockpit2.py:2250` |
| `rov2_remove` | `cockpit2.py:2262` |
| `rov2_remove_group` | `cockpit2.py:2277` |
| `rov2_setkind` | `cockpit2.py:2295` |
| `rov2_consent` | `cockpit2.py:2308` |
| `rov2_end` | `cockpit2.py:2330` |
| `wo_open` | `cockpit2.py:2354` |
| `wo_close` | `cockpit2.py:2364` |
| `wo_presence` | `cockpit2.py:2380` |
| `wo_present_all` | `cockpit2.py:2391` |
| `wo_ag_add` | `cockpit2.py:2403` |
| `wo_ag_remove` | `cockpit2.py:2415` |
| `wo_ag_note` | `cockpit2.py:2425` |
| `wo_ag_reopen` | `cockpit2.py:2437` |
| `wo_ag_resolve` | `cockpit2.py:2513` |
| `wo_checkout` | `cockpit2.py:2881` |
| `noochie_send` | `cockpit2.py:2893` |
| `noochie_reset` | `cockpit2.py:2919` |
| `noochie_ctx` | `cockpit2.py:2926` |
| `cl_add` | `cockpit2.py:2933` |
| `cl_report` | `cockpit2.py:2951` |
| `cl_remove` | `cockpit2.py:2966` |
| `m_add_kpi` | `cockpit2.py:2976` |
| `m_add_from_def` | `cockpit2.py:3008` |
| `def_add` | `cockpit2.py:3023` |
| `catalog_publish` | `cockpit2.py:3045` |
| `def_amend` | `cockpit2.py:3071` |
| `m_add_link` | `cockpit2.py:3113` |
| `m_sample` | `cockpit2.py:3124` |
| `m_remove` | `cockpit2.py:3134` |
| `m_pin` | `cockpit2.py:3144` |
| `m_unpin` | `cockpit2.py:3155` |
| `tile_add` | `cockpit2.py:3193` |
| `indicator_activate` | `cockpit2.py:3165` |
| `tile_remove` | `cockpit2.py:3227` |
| `rov2_set` | `cockpit2.py:3237` |
| `rov2_acc_add` | `cockpit2.py:3237` |
| `rov2_acc_remove` | `cockpit2.py:3237` |
| `rov2_dom_add` | `cockpit2.py:3237` |
| `rov2_dom_remove` | `cockpit2.py:3237` |
| `backlog_add` | `cockpit2.py:3269` |
| `backlog_update_staat` | `cockpit2.py:3281` |
| `backlog_update_prioriteit` | `cockpit2.py:3293` |
| `person_edit` | `cockpit2.py:3305` |
| `person_remove` | `cockpit2.py:3322` |
| `lk_mute` | `cockpit2.py:3343` |
| `claims_term_add` | `cockpit2.py:3435` |
| `claims_work_status` | `cockpit2.py:3458` |
| `claims_to_board` | `cockpit2.py:3477` |
| `persona_edit` | `cockpit2.py:2122` |
| `persona_llm` | `cockpit2.py:2141` |
| `persona_finetune` | `cockpit2.py:2158` |
| `persona_finetune_apply` | `cockpit2.py:2176` |


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
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


---
_47 routes · 160 dispatch-acties · 30 stores._
