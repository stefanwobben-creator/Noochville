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
| `/backlog` | `render_backlog` | `nooch_village/views/backlog.py` |
| `/rapport` | `render_rapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
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


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `ff_beslis` | `cockpit2.py:5262` |
| `ff_cluster` | `cockpit2.py:5390` |
| `ff_promote` | `cockpit2.py:5320` |
| `ff_demote` | `cockpit2.py:5344` |
| `ff_run` | `cockpit2.py:5363` |
| `kb_new` | `cockpit2.py:4625` |
| `kb_intake` | `cockpit2.py:4707` |
| `kb_intake_url` | `cockpit2.py:4724` |
| `kb_stage_edit` | `cockpit2.py:4743` |
| `kb_stage_accept` | `cockpit2.py:4755` |
| `kb_stage_delete` | `cockpit2.py:4774` |
| `kb_stage_merge` | `cockpit2.py:4780` |
| `kb_stage_commit` | `cockpit2.py:4791` |
| `kb_stage_discard` | `cockpit2.py:4811` |
| `kb_atoom_subject` | `cockpit2.py:5066` |
| `kb_atoom_purge` | `cockpit2.py:5050` |
| `tag_voorstel_besluit` | `cockpit2.py:4887` |
| `tag_onderhoud_run` | `cockpit2.py:5037` |
| `copy_stack_inclusie` | `cockpit2.py:5019` |
| `verzoek_besluit` | `cockpit2.py:4906` |
| `kb_blacklist_leeg` | `cockpit2.py:5059` |
| `kb_atoom_edit` | `cockpit2.py:4817` |
| `kb_atoom_related` | `cockpit2.py:4824` |
| `kb_atoom_reference` | `cockpit2.py:4869` |
| `kb_insight_link` | `cockpit2.py:4836` |
| `kb_insight_unlink` | `cockpit2.py:4843` |
| `kb_meta_start` | `cockpit2.py:4849` |
| `kb_atoom_merge` | `cockpit2.py:5077` |
| `kb_atoom_archive` | `cockpit2.py:5098` |
| `kb_atoom_unarchive` | `cockpit2.py:5107` |
| `kb_atoom_naar_spel` | `cockpit2.py:5113` |
| `kb_spel_start` | `cockpit2.py:5134` |
| `kb_spel_add` | `cockpit2.py:5148` |
| `kb_spel_remove` | `cockpit2.py:5158` |
| `kb_spel_flip` | `cockpit2.py:5165` |
| `kb_spel_finish` | `cockpit2.py:5171` |
| `kb_link` | `cockpit2.py:4634` |
| `kb_unlink` | `cockpit2.py:4648` |
| `kb_annotate` | `cockpit2.py:4659` |
| `kb_evidence` | `cockpit2.py:4665` |
| `kb_discuss` | `cockpit2.py:4686` |
| `kb_reformulate` | `cockpit2.py:4692` |
| `kw_nominate` | `cockpit2.py:5182` |
| `kw_nom_accept` | `cockpit2.py:5193` |
| `kw_nom_reject` | `cockpit2.py:5211` |
| `ws_forbid` | `cockpit2.py:5241` |
| `ws_approve` | `cockpit2.py:5246` |
| `proj_add` | `cockpit2.py:1209` |
| `artefact_add` | `cockpit2.py:1253` |
| `artefact_edit` | `cockpit2.py:1297` |
| `artefact_archive` | `cockpit2.py:1324` |
| `pagina_feit_add` | `cockpit2.py:1344` |
| `pagina_feit_del` | `cockpit2.py:1373` |
| `pagina_voorstel` | `cockpit2.py:1404` |
| `proj_status` | `cockpit2.py:1434` |
| `proj_done` | `cockpit2.py:1452` |
| `proj_dod` | `cockpit2.py:1507` |
| `proj_archive` | `cockpit2.py:1521` |
| `proj_unarchive` | `cockpit2.py:1544` |
| `proj_delete` | `cockpit2.py:1554` |
| `proj_edit` | `cockpit2.py:1581` |
| `proj_comment` | `cockpit2.py:1594` |
| `proj_rename` | `cockpit2.py:1604` |
| `proj_describe` | `cockpit2.py:1615` |
| `proj_doc_edit` | `cockpit2.py:1648` |
| `proj_regen_doc` | `cockpit2.py:1626` |
| `proj_settrekker` | `cockpit2.py:1661` |
| `proj_setowner` | `cockpit2.py:1698` |
| `proj_approve` | `cockpit2.py:1717` |
| `proj_discard` | `cockpit2.py:1728` |
| `proj_proposal_accept` | `cockpit2.py:1739` |
| `proj_proposal_reject` | `cockpit2.py:1752` |
| `proj_setlabel` | `cockpit2.py:1765` |
| `proj_setimpact` | `cockpit2.py:1780` |
| `proj_seteffort` | `cockpit2.py:1799` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1822` |
| `proj_setprivate` | `cockpit2.py:1846` |
| `proj_setdue` | `cockpit2.py:1857` |
| `attach_add` | `cockpit2.py:1868` |
| `attach_remove` | `cockpit2.py:1879` |
| `react_add` | `cockpit2.py:1889` |
| `feed_edit` | `cockpit2.py:1899` |
| `feed_remove` | `cockpit2.py:1909` |
| `wall_outcome` | `cockpit2.py:3403` |
| `notif_read` | `cockpit2.py:3499` |
| `notif_processed` | `cockpit2.py:3504` |
| `notif_outcome` | `cockpit2.py:3723` |
| `notif_klaar` | `cockpit2.py:3670` |
| `notif_delete` | `cockpit2.py:3509` |
| `notif_add` | `cockpit2.py:3621` |
| `notif_archive` | `cockpit2.py:3840` |
| `metrics2_fav` | `cockpit2.py:3515` |
| `metrics2_unfav` | `cockpit2.py:3525` |
| `metrics2_form` | `cockpit2.py:3530` |
| `metrics2_dim` | `cockpit2.py:3536` |
| `metrics2_compare` | `cockpit2.py:3543` |
| `metrics2_formula` | `cockpit2.py:3606` |
| `source_activate` | `cockpit2.py:3589` |
| `source_deactivate` | `cockpit2.py:3598` |
| `link_pursue` | `cockpit2.py:3570` |
| `link_ignore` | `cockpit2.py:3580` |
| `acc_check` | `cockpit2.py:3551` |
| `ai_reply` | `cockpit2.py:1918` |
| `proj_feed` | `cockpit2.py:1929` |
| `checklist_add` | `cockpit2.py:1976` |
| `checklist_remove` | `cockpit2.py:1987` |
| `check_add` | `cockpit2.py:2035` |
| `check_accept` | `cockpit2.py:2052` |
| `check_toggle` | `cockpit2.py:2062` |
| `check_skip` | `cockpit2.py:2084` |
| `check_unskip` | `cockpit2.py:2096` |
| `check_handoff` | `cockpit2.py:2108` |
| `check_remove` | `cockpit2.py:2122` |
| `role_assign` | `cockpit2.py:2132` |
| `role_unassign` | `cockpit2.py:2150` |
| `role_focus` | `cockpit2.py:2169` |
| `radar_approve` | `cockpit2.py:2202` |
| `radar_dismiss` | `cockpit2.py:2212` |
| `radar_promote` | `cockpit2.py:2216` |
| `radar_merge` | `cockpit2.py:2236` |
| `radar_koppel` | `cockpit2.py:2252` |
| `kb_stage_koppel` | `cockpit2.py:2279` |
| `aitask_add` | `cockpit2.py:2317` |
| `aitask_remove` | `cockpit2.py:2348` |
| `skilllink_add` | `cockpit2.py:2376` |
| `means_gap_add` | `cockpit2.py:2406` |
| `persona_skill_add` | `cockpit2.py:2560` |
| `rov2_add` | `cockpit2.py:2575` |
| `rov2_add_to_group` | `cockpit2.py:2587` |
| `rov2_remove` | `cockpit2.py:2599` |
| `rov2_remove_group` | `cockpit2.py:2614` |
| `rov2_setkind` | `cockpit2.py:2632` |
| `rov2_consent` | `cockpit2.py:2645` |
| `rov2_end` | `cockpit2.py:2667` |
| `wo_open` | `cockpit2.py:2691` |
| `wo_close` | `cockpit2.py:2701` |
| `wo_presence` | `cockpit2.py:2717` |
| `wo_present_all` | `cockpit2.py:2728` |
| `vangst_add` | `cockpit2.py:2740` |
| `vangst_tekst` | `cockpit2.py:2788` |
| `vangst_klaar` | `cockpit2.py:2798` |
| `vangst_uitkomst` | `cockpit2.py:2847` |
| `vangst_uitkomst_weg` | `cockpit2.py:2835` |
| `vangst_uitkomst_edit` | `cockpit2.py:2810` |
| `vangst_remove` | `cockpit2.py:2779` |
| `vangst_verwerk` | `cockpit2.py:2963` |
| `wo_checkout` | `cockpit2.py:3845` |
| `noochie_send` | `cockpit2.py:3860` |
| `noochie_reset` | `cockpit2.py:3886` |
| `noochie_ctx` | `cockpit2.py:3893` |
| `cl_add` | `cockpit2.py:3900` |
| `cl_report` | `cockpit2.py:3918` |
| `cl_remove` | `cockpit2.py:3933` |
| `m_add_kpi` | `cockpit2.py:3943` |
| `m_add_from_def` | `cockpit2.py:3975` |
| `def_add` | `cockpit2.py:3990` |
| `catalog_publish` | `cockpit2.py:4012` |
| `def_amend` | `cockpit2.py:4038` |
| `m_add_link` | `cockpit2.py:4080` |
| `m_sample` | `cockpit2.py:4091` |
| `m_remove` | `cockpit2.py:4101` |
| `m_pin` | `cockpit2.py:4111` |
| `m_unpin` | `cockpit2.py:4122` |
| `tile_add` | `cockpit2.py:4160` |
| `indicator_activate` | `cockpit2.py:4132` |
| `tile_remove` | `cockpit2.py:4194` |
| `rov2_set` | `cockpit2.py:4204` |
| `rov2_acc_add` | `cockpit2.py:4204` |
| `rov2_acc_remove` | `cockpit2.py:4204` |
| `rov2_dom_add` | `cockpit2.py:4204` |
| `rov2_dom_remove` | `cockpit2.py:4204` |
| `backlog_add` | `cockpit2.py:4236` |
| `backlog_update_staat` | `cockpit2.py:4248` |
| `backlog_update_prioriteit` | `cockpit2.py:4260` |
| `person_edit` | `cockpit2.py:4272` |
| `person_remove` | `cockpit2.py:4289` |
| `lk_mute` | `cockpit2.py:4310` |
| `claims_term_add` | `cockpit2.py:4413` |
| `claims_term_retract` | `cockpit2.py:4450` |
| `claims_work_status` | `cockpit2.py:4434` |
| `claims_bewijs_link` | `cockpit2.py:4479` |
| `claims_vondst_whitelist` | `cockpit2.py:4503` |
| `claims_regel_uit_vondst` | `cockpit2.py:4529` |
| `claims_to_board` | `cockpit2.py:4561` |
| `persona_edit` | `cockpit2.py:2459` |
| `persona_llm` | `cockpit2.py:2478` |
| `persona_finetune` | `cockpit2.py:2495` |
| `persona_finetune_apply` | `cockpit2.py:2513` |


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
_59 routes · 188 dispatch-acties · 32 stores._
