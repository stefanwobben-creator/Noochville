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
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/inzichten` | `render_kennislaag` | `nooch_village/views/kennislaag.py` |
| `/kennisbank` | `render_kennisbank` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/search` | `render_kennisbank_search` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/tags` | `render_tag_onderhoud` | `nooch_village/views/tag_onderhoud.py` |
| `/kennisbank/staging` | `render_kennisbank_staging` | `nooch_village/views/kennisbank_staging.py` |
| `/kennisbank/spel` | `render_kennisbank_spel` | `nooch_village/views/kennisbank_spel.py` |
| `/kennisbank/spel/search` | `render_kennisbank_spel_search` | `nooch_village/views/kennisbank_spel.py` |
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
| `kb_new` | `cockpit2.py:3711` |
| `kb_intake` | `cockpit2.py:3793` |
| `kb_intake_url` | `cockpit2.py:3810` |
| `kb_stage_edit` | `cockpit2.py:3829` |
| `kb_stage_accept` | `cockpit2.py:3841` |
| `kb_stage_delete` | `cockpit2.py:3860` |
| `kb_stage_merge` | `cockpit2.py:3866` |
| `kb_stage_commit` | `cockpit2.py:3877` |
| `kb_stage_discard` | `cockpit2.py:3897` |
| `kb_atoom_subject` | `cockpit2.py:4021` |
| `kb_atoom_purge` | `cockpit2.py:4005` |
| `tag_voorstel_besluit` | `cockpit2.py:3973` |
| `tag_onderhoud_run` | `cockpit2.py:3992` |
| `kb_blacklist_leeg` | `cockpit2.py:4014` |
| `kb_atoom_edit` | `cockpit2.py:3903` |
| `kb_atoom_related` | `cockpit2.py:3910` |
| `kb_atoom_reference` | `cockpit2.py:3955` |
| `kb_insight_link` | `cockpit2.py:3922` |
| `kb_insight_unlink` | `cockpit2.py:3929` |
| `kb_meta_start` | `cockpit2.py:3935` |
| `kb_atoom_merge` | `cockpit2.py:4032` |
| `kb_atoom_archive` | `cockpit2.py:4053` |
| `kb_atoom_unarchive` | `cockpit2.py:4062` |
| `kb_atoom_naar_spel` | `cockpit2.py:4068` |
| `kb_spel_start` | `cockpit2.py:4089` |
| `kb_spel_add` | `cockpit2.py:4103` |
| `kb_spel_remove` | `cockpit2.py:4113` |
| `kb_spel_flip` | `cockpit2.py:4120` |
| `kb_spel_finish` | `cockpit2.py:4126` |
| `kb_link` | `cockpit2.py:3720` |
| `kb_unlink` | `cockpit2.py:3734` |
| `kb_annotate` | `cockpit2.py:3745` |
| `kb_evidence` | `cockpit2.py:3751` |
| `kb_discuss` | `cockpit2.py:3772` |
| `kb_reformulate` | `cockpit2.py:3778` |
| `kw_nominate` | `cockpit2.py:4137` |
| `kw_nom_accept` | `cockpit2.py:4148` |
| `kw_nom_reject` | `cockpit2.py:4166` |
| `ws_forbid` | `cockpit2.py:4196` |
| `ws_approve` | `cockpit2.py:4201` |
| `proj_add` | `cockpit2.py:1130` |
| `artefact_add` | `cockpit2.py:1165` |
| `artefact_edit` | `cockpit2.py:1206` |
| `artefact_archive` | `cockpit2.py:1230` |
| `proj_status` | `cockpit2.py:1250` |
| `proj_done` | `cockpit2.py:1268` |
| `proj_dod` | `cockpit2.py:1317` |
| `proj_archive` | `cockpit2.py:1331` |
| `proj_unarchive` | `cockpit2.py:1354` |
| `proj_delete` | `cockpit2.py:1364` |
| `proj_edit` | `cockpit2.py:1391` |
| `proj_comment` | `cockpit2.py:1404` |
| `proj_rename` | `cockpit2.py:1414` |
| `proj_describe` | `cockpit2.py:1425` |
| `proj_doc_edit` | `cockpit2.py:1458` |
| `proj_regen_doc` | `cockpit2.py:1436` |
| `proj_settrekker` | `cockpit2.py:1471` |
| `proj_setowner` | `cockpit2.py:1508` |
| `proj_approve` | `cockpit2.py:1527` |
| `proj_discard` | `cockpit2.py:1538` |
| `proj_setlabel` | `cockpit2.py:1549` |
| `proj_setimpact` | `cockpit2.py:1564` |
| `proj_seteffort` | `cockpit2.py:1583` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1606` |
| `proj_setprivate` | `cockpit2.py:1630` |
| `proj_setdue` | `cockpit2.py:1641` |
| `attach_add` | `cockpit2.py:1652` |
| `attach_remove` | `cockpit2.py:1663` |
| `react_add` | `cockpit2.py:1673` |
| `feed_edit` | `cockpit2.py:1683` |
| `feed_remove` | `cockpit2.py:1693` |
| `wall_outcome` | `cockpit2.py:2643` |
| `notif_read` | `cockpit2.py:2741` |
| `notif_processed` | `cockpit2.py:2746` |
| `notif_outcome` | `cockpit2.py:2893` |
| `notif_besluit` | `cockpit2.py:2980` |
| `notif_klaar` | `cockpit2.py:2879` |
| `notif_delete` | `cockpit2.py:2751` |
| `notif_add` | `cockpit2.py:2863` |
| `notif_archive` | `cockpit2.py:3022` |
| `metrics2_fav` | `cockpit2.py:2757` |
| `metrics2_unfav` | `cockpit2.py:2767` |
| `metrics2_form` | `cockpit2.py:2772` |
| `metrics2_dim` | `cockpit2.py:2778` |
| `metrics2_compare` | `cockpit2.py:2785` |
| `metrics2_formula` | `cockpit2.py:2848` |
| `source_activate` | `cockpit2.py:2831` |
| `source_deactivate` | `cockpit2.py:2840` |
| `link_pursue` | `cockpit2.py:2812` |
| `link_ignore` | `cockpit2.py:2822` |
| `acc_check` | `cockpit2.py:2793` |
| `ai_reply` | `cockpit2.py:1702` |
| `proj_feed` | `cockpit2.py:1713` |
| `checklist_add` | `cockpit2.py:1743` |
| `checklist_remove` | `cockpit2.py:1754` |
| `check_add` | `cockpit2.py:1802` |
| `check_accept` | `cockpit2.py:1819` |
| `check_toggle` | `cockpit2.py:1829` |
| `check_skip` | `cockpit2.py:1851` |
| `check_unskip` | `cockpit2.py:1863` |
| `check_handoff` | `cockpit2.py:1875` |
| `check_remove` | `cockpit2.py:1889` |
| `role_assign` | `cockpit2.py:1899` |
| `role_unassign` | `cockpit2.py:1917` |
| `role_focus` | `cockpit2.py:1936` |
| `radar_approve` | `cockpit2.py:1969` |
| `radar_dismiss` | `cockpit2.py:1979` |
| `radar_promote` | `cockpit2.py:1983` |
| `radar_merge` | `cockpit2.py:2003` |
| `radar_koppel` | `cockpit2.py:2019` |
| `kb_stage_koppel` | `cockpit2.py:2046` |
| `aitask_add` | `cockpit2.py:2084` |
| `aitask_remove` | `cockpit2.py:2115` |
| `skilllink_add` | `cockpit2.py:2143` |
| `means_gap_add` | `cockpit2.py:2173` |
| `persona_skill_add` | `cockpit2.py:2327` |
| `rov2_add` | `cockpit2.py:2342` |
| `rov2_add_to_group` | `cockpit2.py:2354` |
| `rov2_remove` | `cockpit2.py:2366` |
| `rov2_remove_group` | `cockpit2.py:2381` |
| `rov2_setkind` | `cockpit2.py:2399` |
| `rov2_consent` | `cockpit2.py:2412` |
| `rov2_end` | `cockpit2.py:2434` |
| `wo_open` | `cockpit2.py:2458` |
| `wo_close` | `cockpit2.py:2468` |
| `wo_presence` | `cockpit2.py:2484` |
| `wo_present_all` | `cockpit2.py:2495` |
| `wo_ag_add` | `cockpit2.py:2507` |
| `wo_ag_remove` | `cockpit2.py:2519` |
| `wo_ag_note` | `cockpit2.py:2529` |
| `wo_ag_reopen` | `cockpit2.py:2541` |
| `wo_ag_resolve` | `cockpit2.py:2617` |
| `wo_checkout` | `cockpit2.py:3027` |
| `noochie_send` | `cockpit2.py:3039` |
| `noochie_reset` | `cockpit2.py:3065` |
| `noochie_ctx` | `cockpit2.py:3072` |
| `cl_add` | `cockpit2.py:3079` |
| `cl_report` | `cockpit2.py:3097` |
| `cl_remove` | `cockpit2.py:3112` |
| `m_add_kpi` | `cockpit2.py:3122` |
| `m_add_from_def` | `cockpit2.py:3154` |
| `def_add` | `cockpit2.py:3169` |
| `catalog_publish` | `cockpit2.py:3191` |
| `def_amend` | `cockpit2.py:3217` |
| `m_add_link` | `cockpit2.py:3259` |
| `m_sample` | `cockpit2.py:3270` |
| `m_remove` | `cockpit2.py:3280` |
| `m_pin` | `cockpit2.py:3290` |
| `m_unpin` | `cockpit2.py:3301` |
| `tile_add` | `cockpit2.py:3339` |
| `indicator_activate` | `cockpit2.py:3311` |
| `tile_remove` | `cockpit2.py:3373` |
| `rov2_set` | `cockpit2.py:3383` |
| `rov2_acc_add` | `cockpit2.py:3383` |
| `rov2_acc_remove` | `cockpit2.py:3383` |
| `rov2_dom_add` | `cockpit2.py:3383` |
| `rov2_dom_remove` | `cockpit2.py:3383` |
| `backlog_add` | `cockpit2.py:3415` |
| `backlog_update_staat` | `cockpit2.py:3427` |
| `backlog_update_prioriteit` | `cockpit2.py:3439` |
| `person_edit` | `cockpit2.py:3451` |
| `person_remove` | `cockpit2.py:3468` |
| `lk_mute` | `cockpit2.py:3489` |
| `claims_term_add` | `cockpit2.py:3592` |
| `claims_term_retract` | `cockpit2.py:3629` |
| `claims_work_status` | `cockpit2.py:3613` |
| `claims_to_board` | `cockpit2.py:3647` |
| `persona_edit` | `cockpit2.py:2226` |
| `persona_llm` | `cockpit2.py:2245` |
| `persona_finetune` | `cockpit2.py:2262` |
| `persona_finetune_apply` | `cockpit2.py:2280` |


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
_51 routes · 171 dispatch-acties · 30 stores._
