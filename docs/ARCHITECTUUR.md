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
| `/codie` | `render_codie` | `nooch_village/views/codie.py` |
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
| `kb_new` | `cockpit2.py:3738` |
| `kb_intake` | `cockpit2.py:3820` |
| `kb_intake_url` | `cockpit2.py:3837` |
| `kb_stage_edit` | `cockpit2.py:3856` |
| `kb_stage_accept` | `cockpit2.py:3868` |
| `kb_stage_delete` | `cockpit2.py:3887` |
| `kb_stage_merge` | `cockpit2.py:3893` |
| `kb_stage_commit` | `cockpit2.py:3904` |
| `kb_stage_discard` | `cockpit2.py:3924` |
| `kb_atoom_subject` | `cockpit2.py:4048` |
| `kb_atoom_purge` | `cockpit2.py:4032` |
| `tag_voorstel_besluit` | `cockpit2.py:4000` |
| `tag_onderhoud_run` | `cockpit2.py:4019` |
| `kb_blacklist_leeg` | `cockpit2.py:4041` |
| `kb_atoom_edit` | `cockpit2.py:3930` |
| `kb_atoom_related` | `cockpit2.py:3937` |
| `kb_atoom_reference` | `cockpit2.py:3982` |
| `kb_insight_link` | `cockpit2.py:3949` |
| `kb_insight_unlink` | `cockpit2.py:3956` |
| `kb_meta_start` | `cockpit2.py:3962` |
| `kb_atoom_merge` | `cockpit2.py:4059` |
| `kb_atoom_archive` | `cockpit2.py:4080` |
| `kb_atoom_unarchive` | `cockpit2.py:4089` |
| `kb_atoom_naar_spel` | `cockpit2.py:4095` |
| `kb_spel_start` | `cockpit2.py:4116` |
| `kb_spel_add` | `cockpit2.py:4130` |
| `kb_spel_remove` | `cockpit2.py:4140` |
| `kb_spel_flip` | `cockpit2.py:4147` |
| `kb_spel_finish` | `cockpit2.py:4153` |
| `kb_link` | `cockpit2.py:3747` |
| `kb_unlink` | `cockpit2.py:3761` |
| `kb_annotate` | `cockpit2.py:3772` |
| `kb_evidence` | `cockpit2.py:3778` |
| `kb_discuss` | `cockpit2.py:3799` |
| `kb_reformulate` | `cockpit2.py:3805` |
| `kw_nominate` | `cockpit2.py:4164` |
| `kw_nom_accept` | `cockpit2.py:4175` |
| `kw_nom_reject` | `cockpit2.py:4193` |
| `ws_forbid` | `cockpit2.py:4223` |
| `ws_approve` | `cockpit2.py:4228` |
| `proj_add` | `cockpit2.py:1131` |
| `artefact_add` | `cockpit2.py:1166` |
| `artefact_edit` | `cockpit2.py:1207` |
| `artefact_archive` | `cockpit2.py:1231` |
| `proj_status` | `cockpit2.py:1251` |
| `proj_done` | `cockpit2.py:1269` |
| `proj_dod` | `cockpit2.py:1318` |
| `proj_archive` | `cockpit2.py:1332` |
| `proj_unarchive` | `cockpit2.py:1355` |
| `proj_delete` | `cockpit2.py:1365` |
| `proj_edit` | `cockpit2.py:1392` |
| `proj_comment` | `cockpit2.py:1405` |
| `proj_rename` | `cockpit2.py:1415` |
| `proj_describe` | `cockpit2.py:1426` |
| `proj_doc_edit` | `cockpit2.py:1459` |
| `proj_regen_doc` | `cockpit2.py:1437` |
| `proj_settrekker` | `cockpit2.py:1472` |
| `proj_setowner` | `cockpit2.py:1509` |
| `proj_approve` | `cockpit2.py:1528` |
| `proj_discard` | `cockpit2.py:1539` |
| `proj_proposal_accept` | `cockpit2.py:1550` |
| `proj_proposal_reject` | `cockpit2.py:1563` |
| `proj_setlabel` | `cockpit2.py:1576` |
| `proj_setimpact` | `cockpit2.py:1591` |
| `proj_seteffort` | `cockpit2.py:1610` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1633` |
| `proj_setprivate` | `cockpit2.py:1657` |
| `proj_setdue` | `cockpit2.py:1668` |
| `attach_add` | `cockpit2.py:1679` |
| `attach_remove` | `cockpit2.py:1690` |
| `react_add` | `cockpit2.py:1700` |
| `feed_edit` | `cockpit2.py:1710` |
| `feed_remove` | `cockpit2.py:1720` |
| `wall_outcome` | `cockpit2.py:2670` |
| `notif_read` | `cockpit2.py:2768` |
| `notif_processed` | `cockpit2.py:2773` |
| `notif_outcome` | `cockpit2.py:2920` |
| `notif_besluit` | `cockpit2.py:3007` |
| `notif_klaar` | `cockpit2.py:2906` |
| `notif_delete` | `cockpit2.py:2778` |
| `notif_add` | `cockpit2.py:2890` |
| `notif_archive` | `cockpit2.py:3049` |
| `metrics2_fav` | `cockpit2.py:2784` |
| `metrics2_unfav` | `cockpit2.py:2794` |
| `metrics2_form` | `cockpit2.py:2799` |
| `metrics2_dim` | `cockpit2.py:2805` |
| `metrics2_compare` | `cockpit2.py:2812` |
| `metrics2_formula` | `cockpit2.py:2875` |
| `source_activate` | `cockpit2.py:2858` |
| `source_deactivate` | `cockpit2.py:2867` |
| `link_pursue` | `cockpit2.py:2839` |
| `link_ignore` | `cockpit2.py:2849` |
| `acc_check` | `cockpit2.py:2820` |
| `ai_reply` | `cockpit2.py:1729` |
| `proj_feed` | `cockpit2.py:1740` |
| `checklist_add` | `cockpit2.py:1770` |
| `checklist_remove` | `cockpit2.py:1781` |
| `check_add` | `cockpit2.py:1829` |
| `check_accept` | `cockpit2.py:1846` |
| `check_toggle` | `cockpit2.py:1856` |
| `check_skip` | `cockpit2.py:1878` |
| `check_unskip` | `cockpit2.py:1890` |
| `check_handoff` | `cockpit2.py:1902` |
| `check_remove` | `cockpit2.py:1916` |
| `role_assign` | `cockpit2.py:1926` |
| `role_unassign` | `cockpit2.py:1944` |
| `role_focus` | `cockpit2.py:1963` |
| `radar_approve` | `cockpit2.py:1996` |
| `radar_dismiss` | `cockpit2.py:2006` |
| `radar_promote` | `cockpit2.py:2010` |
| `radar_merge` | `cockpit2.py:2030` |
| `radar_koppel` | `cockpit2.py:2046` |
| `kb_stage_koppel` | `cockpit2.py:2073` |
| `aitask_add` | `cockpit2.py:2111` |
| `aitask_remove` | `cockpit2.py:2142` |
| `skilllink_add` | `cockpit2.py:2170` |
| `means_gap_add` | `cockpit2.py:2200` |
| `persona_skill_add` | `cockpit2.py:2354` |
| `rov2_add` | `cockpit2.py:2369` |
| `rov2_add_to_group` | `cockpit2.py:2381` |
| `rov2_remove` | `cockpit2.py:2393` |
| `rov2_remove_group` | `cockpit2.py:2408` |
| `rov2_setkind` | `cockpit2.py:2426` |
| `rov2_consent` | `cockpit2.py:2439` |
| `rov2_end` | `cockpit2.py:2461` |
| `wo_open` | `cockpit2.py:2485` |
| `wo_close` | `cockpit2.py:2495` |
| `wo_presence` | `cockpit2.py:2511` |
| `wo_present_all` | `cockpit2.py:2522` |
| `wo_ag_add` | `cockpit2.py:2534` |
| `wo_ag_remove` | `cockpit2.py:2546` |
| `wo_ag_note` | `cockpit2.py:2556` |
| `wo_ag_reopen` | `cockpit2.py:2568` |
| `wo_ag_resolve` | `cockpit2.py:2644` |
| `wo_checkout` | `cockpit2.py:3054` |
| `noochie_send` | `cockpit2.py:3066` |
| `noochie_reset` | `cockpit2.py:3092` |
| `noochie_ctx` | `cockpit2.py:3099` |
| `cl_add` | `cockpit2.py:3106` |
| `cl_report` | `cockpit2.py:3124` |
| `cl_remove` | `cockpit2.py:3139` |
| `m_add_kpi` | `cockpit2.py:3149` |
| `m_add_from_def` | `cockpit2.py:3181` |
| `def_add` | `cockpit2.py:3196` |
| `catalog_publish` | `cockpit2.py:3218` |
| `def_amend` | `cockpit2.py:3244` |
| `m_add_link` | `cockpit2.py:3286` |
| `m_sample` | `cockpit2.py:3297` |
| `m_remove` | `cockpit2.py:3307` |
| `m_pin` | `cockpit2.py:3317` |
| `m_unpin` | `cockpit2.py:3328` |
| `tile_add` | `cockpit2.py:3366` |
| `indicator_activate` | `cockpit2.py:3338` |
| `tile_remove` | `cockpit2.py:3400` |
| `rov2_set` | `cockpit2.py:3410` |
| `rov2_acc_add` | `cockpit2.py:3410` |
| `rov2_acc_remove` | `cockpit2.py:3410` |
| `rov2_dom_add` | `cockpit2.py:3410` |
| `rov2_dom_remove` | `cockpit2.py:3410` |
| `backlog_add` | `cockpit2.py:3442` |
| `backlog_update_staat` | `cockpit2.py:3454` |
| `backlog_update_prioriteit` | `cockpit2.py:3466` |
| `person_edit` | `cockpit2.py:3478` |
| `person_remove` | `cockpit2.py:3495` |
| `lk_mute` | `cockpit2.py:3516` |
| `claims_term_add` | `cockpit2.py:3619` |
| `claims_term_retract` | `cockpit2.py:3656` |
| `claims_work_status` | `cockpit2.py:3640` |
| `claims_to_board` | `cockpit2.py:3674` |
| `persona_edit` | `cockpit2.py:2253` |
| `persona_llm` | `cockpit2.py:2272` |
| `persona_finetune` | `cockpit2.py:2289` |
| `persona_finetune_apply` | `cockpit2.py:2307` |


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
_52 routes · 173 dispatch-acties · 30 stores._
