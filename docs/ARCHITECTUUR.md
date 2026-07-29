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
| `kb_new` | `cockpit2.py:3737` |
| `kb_intake` | `cockpit2.py:3819` |
| `kb_intake_url` | `cockpit2.py:3836` |
| `kb_stage_edit` | `cockpit2.py:3855` |
| `kb_stage_accept` | `cockpit2.py:3867` |
| `kb_stage_delete` | `cockpit2.py:3886` |
| `kb_stage_merge` | `cockpit2.py:3892` |
| `kb_stage_commit` | `cockpit2.py:3903` |
| `kb_stage_discard` | `cockpit2.py:3923` |
| `kb_atoom_subject` | `cockpit2.py:4047` |
| `kb_atoom_purge` | `cockpit2.py:4031` |
| `tag_voorstel_besluit` | `cockpit2.py:3999` |
| `tag_onderhoud_run` | `cockpit2.py:4018` |
| `kb_blacklist_leeg` | `cockpit2.py:4040` |
| `kb_atoom_edit` | `cockpit2.py:3929` |
| `kb_atoom_related` | `cockpit2.py:3936` |
| `kb_atoom_reference` | `cockpit2.py:3981` |
| `kb_insight_link` | `cockpit2.py:3948` |
| `kb_insight_unlink` | `cockpit2.py:3955` |
| `kb_meta_start` | `cockpit2.py:3961` |
| `kb_atoom_merge` | `cockpit2.py:4058` |
| `kb_atoom_archive` | `cockpit2.py:4079` |
| `kb_atoom_unarchive` | `cockpit2.py:4088` |
| `kb_atoom_naar_spel` | `cockpit2.py:4094` |
| `kb_spel_start` | `cockpit2.py:4115` |
| `kb_spel_add` | `cockpit2.py:4129` |
| `kb_spel_remove` | `cockpit2.py:4139` |
| `kb_spel_flip` | `cockpit2.py:4146` |
| `kb_spel_finish` | `cockpit2.py:4152` |
| `kb_link` | `cockpit2.py:3746` |
| `kb_unlink` | `cockpit2.py:3760` |
| `kb_annotate` | `cockpit2.py:3771` |
| `kb_evidence` | `cockpit2.py:3777` |
| `kb_discuss` | `cockpit2.py:3798` |
| `kb_reformulate` | `cockpit2.py:3804` |
| `kw_nominate` | `cockpit2.py:4163` |
| `kw_nom_accept` | `cockpit2.py:4174` |
| `kw_nom_reject` | `cockpit2.py:4192` |
| `ws_forbid` | `cockpit2.py:4222` |
| `ws_approve` | `cockpit2.py:4227` |
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
| `proj_proposal_accept` | `cockpit2.py:1549` |
| `proj_proposal_reject` | `cockpit2.py:1562` |
| `proj_setlabel` | `cockpit2.py:1575` |
| `proj_setimpact` | `cockpit2.py:1590` |
| `proj_seteffort` | `cockpit2.py:1609` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1632` |
| `proj_setprivate` | `cockpit2.py:1656` |
| `proj_setdue` | `cockpit2.py:1667` |
| `attach_add` | `cockpit2.py:1678` |
| `attach_remove` | `cockpit2.py:1689` |
| `react_add` | `cockpit2.py:1699` |
| `feed_edit` | `cockpit2.py:1709` |
| `feed_remove` | `cockpit2.py:1719` |
| `wall_outcome` | `cockpit2.py:2669` |
| `notif_read` | `cockpit2.py:2767` |
| `notif_processed` | `cockpit2.py:2772` |
| `notif_outcome` | `cockpit2.py:2919` |
| `notif_besluit` | `cockpit2.py:3006` |
| `notif_klaar` | `cockpit2.py:2905` |
| `notif_delete` | `cockpit2.py:2777` |
| `notif_add` | `cockpit2.py:2889` |
| `notif_archive` | `cockpit2.py:3048` |
| `metrics2_fav` | `cockpit2.py:2783` |
| `metrics2_unfav` | `cockpit2.py:2793` |
| `metrics2_form` | `cockpit2.py:2798` |
| `metrics2_dim` | `cockpit2.py:2804` |
| `metrics2_compare` | `cockpit2.py:2811` |
| `metrics2_formula` | `cockpit2.py:2874` |
| `source_activate` | `cockpit2.py:2857` |
| `source_deactivate` | `cockpit2.py:2866` |
| `link_pursue` | `cockpit2.py:2838` |
| `link_ignore` | `cockpit2.py:2848` |
| `acc_check` | `cockpit2.py:2819` |
| `ai_reply` | `cockpit2.py:1728` |
| `proj_feed` | `cockpit2.py:1739` |
| `checklist_add` | `cockpit2.py:1769` |
| `checklist_remove` | `cockpit2.py:1780` |
| `check_add` | `cockpit2.py:1828` |
| `check_accept` | `cockpit2.py:1845` |
| `check_toggle` | `cockpit2.py:1855` |
| `check_skip` | `cockpit2.py:1877` |
| `check_unskip` | `cockpit2.py:1889` |
| `check_handoff` | `cockpit2.py:1901` |
| `check_remove` | `cockpit2.py:1915` |
| `role_assign` | `cockpit2.py:1925` |
| `role_unassign` | `cockpit2.py:1943` |
| `role_focus` | `cockpit2.py:1962` |
| `radar_approve` | `cockpit2.py:1995` |
| `radar_dismiss` | `cockpit2.py:2005` |
| `radar_promote` | `cockpit2.py:2009` |
| `radar_merge` | `cockpit2.py:2029` |
| `radar_koppel` | `cockpit2.py:2045` |
| `kb_stage_koppel` | `cockpit2.py:2072` |
| `aitask_add` | `cockpit2.py:2110` |
| `aitask_remove` | `cockpit2.py:2141` |
| `skilllink_add` | `cockpit2.py:2169` |
| `means_gap_add` | `cockpit2.py:2199` |
| `persona_skill_add` | `cockpit2.py:2353` |
| `rov2_add` | `cockpit2.py:2368` |
| `rov2_add_to_group` | `cockpit2.py:2380` |
| `rov2_remove` | `cockpit2.py:2392` |
| `rov2_remove_group` | `cockpit2.py:2407` |
| `rov2_setkind` | `cockpit2.py:2425` |
| `rov2_consent` | `cockpit2.py:2438` |
| `rov2_end` | `cockpit2.py:2460` |
| `wo_open` | `cockpit2.py:2484` |
| `wo_close` | `cockpit2.py:2494` |
| `wo_presence` | `cockpit2.py:2510` |
| `wo_present_all` | `cockpit2.py:2521` |
| `wo_ag_add` | `cockpit2.py:2533` |
| `wo_ag_remove` | `cockpit2.py:2545` |
| `wo_ag_note` | `cockpit2.py:2555` |
| `wo_ag_reopen` | `cockpit2.py:2567` |
| `wo_ag_resolve` | `cockpit2.py:2643` |
| `wo_checkout` | `cockpit2.py:3053` |
| `noochie_send` | `cockpit2.py:3065` |
| `noochie_reset` | `cockpit2.py:3091` |
| `noochie_ctx` | `cockpit2.py:3098` |
| `cl_add` | `cockpit2.py:3105` |
| `cl_report` | `cockpit2.py:3123` |
| `cl_remove` | `cockpit2.py:3138` |
| `m_add_kpi` | `cockpit2.py:3148` |
| `m_add_from_def` | `cockpit2.py:3180` |
| `def_add` | `cockpit2.py:3195` |
| `catalog_publish` | `cockpit2.py:3217` |
| `def_amend` | `cockpit2.py:3243` |
| `m_add_link` | `cockpit2.py:3285` |
| `m_sample` | `cockpit2.py:3296` |
| `m_remove` | `cockpit2.py:3306` |
| `m_pin` | `cockpit2.py:3316` |
| `m_unpin` | `cockpit2.py:3327` |
| `tile_add` | `cockpit2.py:3365` |
| `indicator_activate` | `cockpit2.py:3337` |
| `tile_remove` | `cockpit2.py:3399` |
| `rov2_set` | `cockpit2.py:3409` |
| `rov2_acc_add` | `cockpit2.py:3409` |
| `rov2_acc_remove` | `cockpit2.py:3409` |
| `rov2_dom_add` | `cockpit2.py:3409` |
| `rov2_dom_remove` | `cockpit2.py:3409` |
| `backlog_add` | `cockpit2.py:3441` |
| `backlog_update_staat` | `cockpit2.py:3453` |
| `backlog_update_prioriteit` | `cockpit2.py:3465` |
| `person_edit` | `cockpit2.py:3477` |
| `person_remove` | `cockpit2.py:3494` |
| `lk_mute` | `cockpit2.py:3515` |
| `claims_term_add` | `cockpit2.py:3618` |
| `claims_term_retract` | `cockpit2.py:3655` |
| `claims_work_status` | `cockpit2.py:3639` |
| `claims_to_board` | `cockpit2.py:3673` |
| `persona_edit` | `cockpit2.py:2252` |
| `persona_llm` | `cockpit2.py:2271` |
| `persona_finetune` | `cockpit2.py:2288` |
| `persona_finetune_apply` | `cockpit2.py:2306` |


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
_51 routes · 173 dispatch-acties · 30 stores._
