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
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/middelen` | `render_middelen` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/goals` | `render_goals` | `nooch_village/views/doelen.py` |
| `/goal` | `render_goal` | `nooch_village/views/doelen.py` |
| `/site-audit` | `render_site_audit` | `nooch_village/views/site_audit.py` |
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
| `/vangst` | `render_vangst_frag` | `nooch_village/views/vangst.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/livekit-presence` | `(inline)` | `cockpit2.py` |
| `/claims/db.json` | `(inline)` | `cockpit2.py` |
| `/claims` | `render_claims` | `nooch_village/views/claims.py` |
| `/copy-check` | `render_copy_check` | `nooch_village/views/copy_check.py` |
| `/copy-prompt` | `render_copy_prompt` | `nooch_village/views/copy_prompt.py` |
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |
| `/project_pakket` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `ff_beslis` | `cockpit2.py:5847` |
| `ff_cluster` | `cockpit2.py:5975` |
| `ff_promote` | `cockpit2.py:5905` |
| `ff_demote` | `cockpit2.py:5929` |
| `ff_run` | `cockpit2.py:5948` |
| `kb_new` | `cockpit2.py:5197` |
| `kb_intake` | `cockpit2.py:5279` |
| `kb_intake_url` | `cockpit2.py:5296` |
| `kb_stage_edit` | `cockpit2.py:5315` |
| `kb_stage_accept` | `cockpit2.py:5327` |
| `kb_stage_delete` | `cockpit2.py:5346` |
| `kb_stage_merge` | `cockpit2.py:5352` |
| `kb_stage_commit` | `cockpit2.py:5363` |
| `kb_stage_discard` | `cockpit2.py:5383` |
| `kb_atoom_subject` | `cockpit2.py:5638` |
| `kb_atoom_purge` | `cockpit2.py:5622` |
| `tag_voorstel_besluit` | `cockpit2.py:5459` |
| `tag_onderhoud_run` | `cockpit2.py:5609` |
| `copy_stack_inclusie` | `cockpit2.py:5591` |
| `verzoek_besluit` | `cockpit2.py:5478` |
| `kb_blacklist_leeg` | `cockpit2.py:5631` |
| `kb_atoom_edit` | `cockpit2.py:5389` |
| `kb_atoom_related` | `cockpit2.py:5396` |
| `kb_atoom_reference` | `cockpit2.py:5441` |
| `kb_insight_link` | `cockpit2.py:5408` |
| `kb_insight_unlink` | `cockpit2.py:5415` |
| `kb_meta_start` | `cockpit2.py:5421` |
| `kb_atoom_merge` | `cockpit2.py:5649` |
| `kb_atoom_archive` | `cockpit2.py:5670` |
| `kb_atoom_unarchive` | `cockpit2.py:5679` |
| `kb_atoom_naar_spel` | `cockpit2.py:5685` |
| `kb_spel_start` | `cockpit2.py:5706` |
| `kb_spel_add` | `cockpit2.py:5720` |
| `kb_spel_remove` | `cockpit2.py:5730` |
| `kb_spel_flip` | `cockpit2.py:5737` |
| `kb_spel_finish` | `cockpit2.py:5743` |
| `kb_link` | `cockpit2.py:5206` |
| `kb_unlink` | `cockpit2.py:5220` |
| `kb_annotate` | `cockpit2.py:5231` |
| `kb_evidence` | `cockpit2.py:5237` |
| `kb_discuss` | `cockpit2.py:5258` |
| `kb_reformulate` | `cockpit2.py:5264` |
| `kw_nominate` | `cockpit2.py:5754` |
| `kw_nom_accept` | `cockpit2.py:5765` |
| `kw_nom_reject` | `cockpit2.py:5783` |
| `ws_forbid` | `cockpit2.py:5826` |
| `ws_approve` | `cockpit2.py:5831` |
| `proj_add` | `cockpit2.py:1244` |
| `artefact_add` | `cockpit2.py:1297` |
| `artefact_edit` | `cockpit2.py:1341` |
| `artefact_archive` | `cockpit2.py:1368` |
| `pagina_feit_add` | `cockpit2.py:1388` |
| `pagina_feit_del` | `cockpit2.py:1417` |
| `pagina_voorstel` | `cockpit2.py:1448` |
| `proj_status` | `cockpit2.py:1478` |
| `proj_done` | `cockpit2.py:1509` |
| `proj_dod` | `cockpit2.py:1604` |
| `proj_archive` | `cockpit2.py:1641` |
| `proj_unarchive` | `cockpit2.py:1649` |
| `proj_delete` | `cockpit2.py:1685` |
| `proj_edit` | `cockpit2.py:1712` |
| `proj_comment` | `cockpit2.py:1725` |
| `proj_rename` | `cockpit2.py:1736` |
| `proj_describe` | `cockpit2.py:1747` |
| `proj_doc_edit` | `cockpit2.py:1885` |
| `verslag_bevestig_behaald` | `cockpit2.py:1825` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1831` |
| `verslag_overslaan` | `cockpit2.py:1836` |
| `verslag_bijwerken` | `cockpit2.py:1863` |
| `proj_regen_doc` | `cockpit2.py:1758` |
| `proj_settrekker` | `cockpit2.py:1898` |
| `proj_setowner` | `cockpit2.py:1939` |
| `proj_approve` | `cockpit2.py:1958` |
| `proj_discard` | `cockpit2.py:1969` |
| `proj_proposal_accept` | `cockpit2.py:1980` |
| `proj_proposal_reject` | `cockpit2.py:1993` |
| `proj_setlabel` | `cockpit2.py:2006` |
| `proj_setimpact` | `cockpit2.py:2021` |
| `proj_seteffort` | `cockpit2.py:2051` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2069` |
| `proj_setprivate` | `cockpit2.py:2093` |
| `proj_setdue` | `cockpit2.py:2104` |
| `proj_goal` | `cockpit2.py:2115` |
| `proj_depends` | `cockpit2.py:2130` |
| `goal_add` | `cockpit2.py:2147` |
| `goal_edit` | `cockpit2.py:2161` |
| `goal_link` | `cockpit2.py:2175` |
| `attach_add` | `cockpit2.py:2192` |
| `attach_remove` | `cockpit2.py:2203` |
| `react_add` | `cockpit2.py:2213` |
| `feed_edit` | `cockpit2.py:2224` |
| `feed_remove` | `cockpit2.py:2235` |
| `wall_outcome` | `cockpit2.py:3863` |
| `notif_read` | `cockpit2.py:3959` |
| `notif_processed` | `cockpit2.py:3969` |
| `notif_outcome` | `cockpit2.py:4292` |
| `notif_klaar` | `cockpit2.py:4233` |
| `goedkeur` | `cockpit2.py:3978` |
| `notif_delete` | `cockpit2.py:4023` |
| `notif_add` | `cockpit2.py:4181` |
| `notif_archive` | `cockpit2.py:4414` |
| `metrics2_fav` | `cockpit2.py:4034` |
| `metrics2_unfav` | `cockpit2.py:4049` |
| `metrics2_form` | `cockpit2.py:4054` |
| `metrics2_dim` | `cockpit2.py:4061` |
| `metrics2_compare` | `cockpit2.py:4069` |
| `metrics2_formula` | `cockpit2.py:4166` |
| `source_activate` | `cockpit2.py:4142` |
| `source_deactivate` | `cockpit2.py:4154` |
| `link_pursue` | `cockpit2.py:4116` |
| `link_ignore` | `cockpit2.py:4127` |
| `acc_check` | `cockpit2.py:4078` |
| `ai_reply` | `cockpit2.py:2245` |
| `proj_feed` | `cockpit2.py:2257` |
| `checklist_add` | `cockpit2.py:2305` |
| `checklist_remove` | `cockpit2.py:2345` |
| `plan_akkoord` | `cockpit2.py:2328` |
| `checklist_uitvoer` | `cockpit2.py:2316` |
| `check_add` | `cockpit2.py:2395` |
| `check_accept` | `cockpit2.py:2412` |
| `check_toggle` | `cockpit2.py:2422` |
| `check_skip` | `cockpit2.py:2444` |
| `check_unskip` | `cockpit2.py:2456` |
| `check_handoff` | `cockpit2.py:2477` |
| `check_remove` | `cockpit2.py:2525` |
| `check_rename` | `cockpit2.py:2535` |
| `check_move` | `cockpit2.py:2554` |
| `role_assign` | `cockpit2.py:2568` |
| `role_unassign` | `cockpit2.py:2593` |
| `role_focus` | `cockpit2.py:2615` |
| `radar_approve` | `cockpit2.py:2648` |
| `radar_dismiss` | `cockpit2.py:2658` |
| `radar_promote` | `cockpit2.py:2662` |
| `radar_merge` | `cockpit2.py:2682` |
| `radar_koppel` | `cockpit2.py:2698` |
| `kb_stage_koppel` | `cockpit2.py:2725` |
| `middel_remove` | `cockpit2.py:2773` |
| `skilllink_add` | `cockpit2.py:2804` |
| `means_gap_add` | `cockpit2.py:2834` |
| `rov2_add` | `cockpit2.py:2988` |
| `rov2_add_to_group` | `cockpit2.py:3000` |
| `rov2_remove` | `cockpit2.py:3012` |
| `rov2_remove_group` | `cockpit2.py:3027` |
| `rov2_setkind` | `cockpit2.py:3045` |
| `rov2_consent` | `cockpit2.py:3058` |
| `rov2_end` | `cockpit2.py:3080` |
| `wo_open` | `cockpit2.py:3104` |
| `wo_close` | `cockpit2.py:3114` |
| `wo_presence` | `cockpit2.py:3130` |
| `wo_present_all` | `cockpit2.py:3141` |
| `vangst_add` | `cockpit2.py:3153` |
| `vangst_tekst` | `cockpit2.py:3201` |
| `vangst_klaar` | `cockpit2.py:3211` |
| `vangst_uitkomst` | `cockpit2.py:3260` |
| `vangst_uitkomst_weg` | `cockpit2.py:3248` |
| `vangst_uitkomst_edit` | `cockpit2.py:3223` |
| `vangst_remove` | `cockpit2.py:3192` |
| `vangst_verwerk` | `cockpit2.py:3376` |
| `wo_checkout` | `cockpit2.py:4423` |
| `noochie_send` | `cockpit2.py:4438` |
| `noochie_reset` | `cockpit2.py:4465` |
| `noochie_ctx` | `cockpit2.py:4473` |
| `cl_add` | `cockpit2.py:4481` |
| `cl_report` | `cockpit2.py:4499` |
| `cl_remove` | `cockpit2.py:4514` |
| `m_add_kpi` | `cockpit2.py:4524` |
| `m_add_from_def` | `cockpit2.py:4556` |
| `def_add` | `cockpit2.py:4571` |
| `catalog_publish` | `cockpit2.py:4593` |
| `def_amend` | `cockpit2.py:4619` |
| `m_add_link` | `cockpit2.py:4661` |
| `m_sample` | `cockpit2.py:4672` |
| `m_remove` | `cockpit2.py:4682` |
| `m_pin` | `cockpit2.py:4692` |
| `m_unpin` | `cockpit2.py:4703` |
| `tile_add` | `cockpit2.py:4741` |
| `indicator_activate` | `cockpit2.py:4713` |
| `tile_remove` | `cockpit2.py:4775` |
| `rov2_set` | `cockpit2.py:4785` |
| `rov2_acc_add` | `cockpit2.py:4785` |
| `rov2_acc_remove` | `cockpit2.py:4785` |
| `rov2_dom_add` | `cockpit2.py:4785` |
| `rov2_dom_remove` | `cockpit2.py:4785` |
| `person_edit` | `cockpit2.py:4817` |
| `person_remove` | `cockpit2.py:4834` |
| `lk_mute` | `cockpit2.py:4855` |
| `claims_term_add` | `cockpit2.py:4985` |
| `claims_term_retract` | `cockpit2.py:5022` |
| `claims_work_status` | `cockpit2.py:5006` |
| `claims_bewijs_link` | `cockpit2.py:5051` |
| `claims_vondst_whitelist` | `cockpit2.py:5075` |
| `claims_regel_uit_vondst` | `cockpit2.py:5101` |
| `claims_to_board` | `cockpit2.py:5133` |
| `persona_edit` | `cockpit2.py:2887` |
| `persona_llm` | `cockpit2.py:2906` |
| `persona_finetune` | `cockpit2.py:2923` |
| `persona_finetune_apply` | `cockpit2.py:2941` |


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
| `notif` | `NotifStore` | `notifications.json` |
| `agenda` | `Agenda` | `roloverleg_agenda.json` |
| `noochie` | `NoochieStore` | `noochie.json` |
| `checklists` | `ChecklistStore` | `checklists.json` |
| `metrics` | `MetricStore` | `metrics.json` |
| `defs` | `DefinitionStore` | `definitions.json` |
| `werk` | `WerkoverlegStore` | `werkoverleg.json` |
| `strategies` | `StrategyStore` | `strategies.json` |
| `doelen` | `DoelStore` | `doelen.json` |
| `copy_stack` | `CopyStackConfig` | `copy_stack.json` |
| `radar` | `RadarStore` | `radar.json` |
| `radar_besluiten` | `ClusterBesluitStore` | `radar_clusters.json` |
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `notes` | `NotesStore` | `notes.json` |
| `spel` | `SpelStore` | `kennisbank_spel.json` |
| `staging` | `StagingStore` | `kennisbank_staging.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


---
_62 routes · 197 dispatch-acties · 31 stores._
