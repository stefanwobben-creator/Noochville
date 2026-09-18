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
| `/decision-coach` | `render_decision_coach` | `nooch_village/views/decision_coach.py` |
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
| `decision_sheet_log` | `cockpit2.py:6017` |
| `ff_beslis` | `cockpit2.py:5856` |
| `ff_cluster` | `cockpit2.py:5984` |
| `ff_promote` | `cockpit2.py:5914` |
| `ff_demote` | `cockpit2.py:5938` |
| `ff_run` | `cockpit2.py:5957` |
| `kb_new` | `cockpit2.py:5206` |
| `kb_intake` | `cockpit2.py:5288` |
| `kb_intake_url` | `cockpit2.py:5305` |
| `kb_stage_edit` | `cockpit2.py:5324` |
| `kb_stage_accept` | `cockpit2.py:5336` |
| `kb_stage_delete` | `cockpit2.py:5355` |
| `kb_stage_merge` | `cockpit2.py:5361` |
| `kb_stage_commit` | `cockpit2.py:5372` |
| `kb_stage_discard` | `cockpit2.py:5392` |
| `kb_atoom_subject` | `cockpit2.py:5647` |
| `kb_atoom_purge` | `cockpit2.py:5631` |
| `tag_voorstel_besluit` | `cockpit2.py:5468` |
| `tag_onderhoud_run` | `cockpit2.py:5618` |
| `copy_stack_inclusie` | `cockpit2.py:5600` |
| `verzoek_besluit` | `cockpit2.py:5487` |
| `kb_blacklist_leeg` | `cockpit2.py:5640` |
| `kb_atoom_edit` | `cockpit2.py:5398` |
| `kb_atoom_related` | `cockpit2.py:5405` |
| `kb_atoom_reference` | `cockpit2.py:5450` |
| `kb_insight_link` | `cockpit2.py:5417` |
| `kb_insight_unlink` | `cockpit2.py:5424` |
| `kb_meta_start` | `cockpit2.py:5430` |
| `kb_atoom_merge` | `cockpit2.py:5658` |
| `kb_atoom_archive` | `cockpit2.py:5679` |
| `kb_atoom_unarchive` | `cockpit2.py:5688` |
| `kb_atoom_naar_spel` | `cockpit2.py:5694` |
| `kb_spel_start` | `cockpit2.py:5715` |
| `kb_spel_add` | `cockpit2.py:5729` |
| `kb_spel_remove` | `cockpit2.py:5739` |
| `kb_spel_flip` | `cockpit2.py:5746` |
| `kb_spel_finish` | `cockpit2.py:5752` |
| `kb_link` | `cockpit2.py:5215` |
| `kb_unlink` | `cockpit2.py:5229` |
| `kb_annotate` | `cockpit2.py:5240` |
| `kb_evidence` | `cockpit2.py:5246` |
| `kb_discuss` | `cockpit2.py:5267` |
| `kb_reformulate` | `cockpit2.py:5273` |
| `kw_nominate` | `cockpit2.py:5763` |
| `kw_nom_accept` | `cockpit2.py:5774` |
| `kw_nom_reject` | `cockpit2.py:5792` |
| `ws_forbid` | `cockpit2.py:5835` |
| `ws_approve` | `cockpit2.py:5840` |
| `proj_add` | `cockpit2.py:1253` |
| `artefact_add` | `cockpit2.py:1306` |
| `artefact_edit` | `cockpit2.py:1350` |
| `artefact_archive` | `cockpit2.py:1377` |
| `pagina_feit_add` | `cockpit2.py:1397` |
| `pagina_feit_del` | `cockpit2.py:1426` |
| `pagina_voorstel` | `cockpit2.py:1457` |
| `proj_status` | `cockpit2.py:1487` |
| `proj_done` | `cockpit2.py:1518` |
| `proj_dod` | `cockpit2.py:1613` |
| `proj_archive` | `cockpit2.py:1650` |
| `proj_unarchive` | `cockpit2.py:1658` |
| `proj_delete` | `cockpit2.py:1694` |
| `proj_edit` | `cockpit2.py:1721` |
| `proj_comment` | `cockpit2.py:1734` |
| `proj_rename` | `cockpit2.py:1745` |
| `proj_describe` | `cockpit2.py:1756` |
| `proj_doc_edit` | `cockpit2.py:1894` |
| `verslag_bevestig_behaald` | `cockpit2.py:1834` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1840` |
| `verslag_overslaan` | `cockpit2.py:1845` |
| `verslag_bijwerken` | `cockpit2.py:1872` |
| `proj_regen_doc` | `cockpit2.py:1767` |
| `proj_settrekker` | `cockpit2.py:1907` |
| `proj_setowner` | `cockpit2.py:1948` |
| `proj_approve` | `cockpit2.py:1967` |
| `proj_discard` | `cockpit2.py:1978` |
| `proj_proposal_accept` | `cockpit2.py:1989` |
| `proj_proposal_reject` | `cockpit2.py:2002` |
| `proj_setlabel` | `cockpit2.py:2015` |
| `proj_setimpact` | `cockpit2.py:2030` |
| `proj_seteffort` | `cockpit2.py:2060` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2078` |
| `proj_setprivate` | `cockpit2.py:2102` |
| `proj_setdue` | `cockpit2.py:2113` |
| `proj_goal` | `cockpit2.py:2124` |
| `proj_depends` | `cockpit2.py:2139` |
| `goal_add` | `cockpit2.py:2156` |
| `goal_edit` | `cockpit2.py:2170` |
| `goal_link` | `cockpit2.py:2184` |
| `attach_add` | `cockpit2.py:2201` |
| `attach_remove` | `cockpit2.py:2212` |
| `react_add` | `cockpit2.py:2222` |
| `feed_edit` | `cockpit2.py:2233` |
| `feed_remove` | `cockpit2.py:2244` |
| `wall_outcome` | `cockpit2.py:3872` |
| `notif_read` | `cockpit2.py:3968` |
| `notif_processed` | `cockpit2.py:3978` |
| `notif_outcome` | `cockpit2.py:4301` |
| `notif_klaar` | `cockpit2.py:4242` |
| `goedkeur` | `cockpit2.py:3987` |
| `notif_delete` | `cockpit2.py:4032` |
| `notif_add` | `cockpit2.py:4190` |
| `notif_archive` | `cockpit2.py:4423` |
| `metrics2_fav` | `cockpit2.py:4043` |
| `metrics2_unfav` | `cockpit2.py:4058` |
| `metrics2_form` | `cockpit2.py:4063` |
| `metrics2_dim` | `cockpit2.py:4070` |
| `metrics2_compare` | `cockpit2.py:4078` |
| `metrics2_formula` | `cockpit2.py:4175` |
| `source_activate` | `cockpit2.py:4151` |
| `source_deactivate` | `cockpit2.py:4163` |
| `link_pursue` | `cockpit2.py:4125` |
| `link_ignore` | `cockpit2.py:4136` |
| `acc_check` | `cockpit2.py:4087` |
| `ai_reply` | `cockpit2.py:2254` |
| `proj_feed` | `cockpit2.py:2266` |
| `checklist_add` | `cockpit2.py:2314` |
| `checklist_remove` | `cockpit2.py:2354` |
| `plan_akkoord` | `cockpit2.py:2337` |
| `checklist_uitvoer` | `cockpit2.py:2325` |
| `check_add` | `cockpit2.py:2404` |
| `check_accept` | `cockpit2.py:2421` |
| `check_toggle` | `cockpit2.py:2431` |
| `check_skip` | `cockpit2.py:2453` |
| `check_unskip` | `cockpit2.py:2465` |
| `check_handoff` | `cockpit2.py:2486` |
| `check_remove` | `cockpit2.py:2534` |
| `check_rename` | `cockpit2.py:2544` |
| `check_move` | `cockpit2.py:2563` |
| `role_assign` | `cockpit2.py:2577` |
| `role_unassign` | `cockpit2.py:2602` |
| `role_focus` | `cockpit2.py:2624` |
| `radar_approve` | `cockpit2.py:2657` |
| `radar_dismiss` | `cockpit2.py:2667` |
| `radar_promote` | `cockpit2.py:2671` |
| `radar_merge` | `cockpit2.py:2691` |
| `radar_koppel` | `cockpit2.py:2707` |
| `kb_stage_koppel` | `cockpit2.py:2734` |
| `middel_remove` | `cockpit2.py:2782` |
| `skilllink_add` | `cockpit2.py:2813` |
| `means_gap_add` | `cockpit2.py:2843` |
| `rov2_add` | `cockpit2.py:2997` |
| `rov2_add_to_group` | `cockpit2.py:3009` |
| `rov2_remove` | `cockpit2.py:3021` |
| `rov2_remove_group` | `cockpit2.py:3036` |
| `rov2_setkind` | `cockpit2.py:3054` |
| `rov2_consent` | `cockpit2.py:3067` |
| `rov2_end` | `cockpit2.py:3089` |
| `wo_open` | `cockpit2.py:3113` |
| `wo_close` | `cockpit2.py:3123` |
| `wo_presence` | `cockpit2.py:3139` |
| `wo_present_all` | `cockpit2.py:3150` |
| `vangst_add` | `cockpit2.py:3162` |
| `vangst_tekst` | `cockpit2.py:3210` |
| `vangst_klaar` | `cockpit2.py:3220` |
| `vangst_uitkomst` | `cockpit2.py:3269` |
| `vangst_uitkomst_weg` | `cockpit2.py:3257` |
| `vangst_uitkomst_edit` | `cockpit2.py:3232` |
| `vangst_remove` | `cockpit2.py:3201` |
| `vangst_verwerk` | `cockpit2.py:3385` |
| `wo_checkout` | `cockpit2.py:4432` |
| `noochie_send` | `cockpit2.py:4447` |
| `noochie_reset` | `cockpit2.py:4474` |
| `noochie_ctx` | `cockpit2.py:4482` |
| `cl_add` | `cockpit2.py:4490` |
| `cl_report` | `cockpit2.py:4508` |
| `cl_remove` | `cockpit2.py:4523` |
| `m_add_kpi` | `cockpit2.py:4533` |
| `m_add_from_def` | `cockpit2.py:4565` |
| `def_add` | `cockpit2.py:4580` |
| `catalog_publish` | `cockpit2.py:4602` |
| `def_amend` | `cockpit2.py:4628` |
| `m_add_link` | `cockpit2.py:4670` |
| `m_sample` | `cockpit2.py:4681` |
| `m_remove` | `cockpit2.py:4691` |
| `m_pin` | `cockpit2.py:4701` |
| `m_unpin` | `cockpit2.py:4712` |
| `tile_add` | `cockpit2.py:4750` |
| `indicator_activate` | `cockpit2.py:4722` |
| `tile_remove` | `cockpit2.py:4784` |
| `rov2_set` | `cockpit2.py:4794` |
| `rov2_acc_add` | `cockpit2.py:4794` |
| `rov2_acc_remove` | `cockpit2.py:4794` |
| `rov2_dom_add` | `cockpit2.py:4794` |
| `rov2_dom_remove` | `cockpit2.py:4794` |
| `person_edit` | `cockpit2.py:4826` |
| `person_remove` | `cockpit2.py:4843` |
| `lk_mute` | `cockpit2.py:4864` |
| `claims_term_add` | `cockpit2.py:4994` |
| `claims_term_retract` | `cockpit2.py:5031` |
| `claims_work_status` | `cockpit2.py:5015` |
| `claims_bewijs_link` | `cockpit2.py:5060` |
| `claims_vondst_whitelist` | `cockpit2.py:5084` |
| `claims_regel_uit_vondst` | `cockpit2.py:5110` |
| `claims_to_board` | `cockpit2.py:5142` |
| `persona_edit` | `cockpit2.py:2896` |
| `persona_llm` | `cockpit2.py:2915` |
| `persona_finetune` | `cockpit2.py:2932` |
| `persona_finetune_apply` | `cockpit2.py:2950` |


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
_63 routes · 198 dispatch-acties · 31 stores._
