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
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
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
| `ff_beslis` | `cockpit2.py:5806` |
| `ff_cluster` | `cockpit2.py:5934` |
| `ff_promote` | `cockpit2.py:5864` |
| `ff_demote` | `cockpit2.py:5888` |
| `ff_run` | `cockpit2.py:5907` |
| `kb_new` | `cockpit2.py:5156` |
| `kb_intake` | `cockpit2.py:5238` |
| `kb_intake_url` | `cockpit2.py:5255` |
| `kb_stage_edit` | `cockpit2.py:5274` |
| `kb_stage_accept` | `cockpit2.py:5286` |
| `kb_stage_delete` | `cockpit2.py:5305` |
| `kb_stage_merge` | `cockpit2.py:5311` |
| `kb_stage_commit` | `cockpit2.py:5322` |
| `kb_stage_discard` | `cockpit2.py:5342` |
| `kb_atoom_subject` | `cockpit2.py:5597` |
| `kb_atoom_purge` | `cockpit2.py:5581` |
| `tag_voorstel_besluit` | `cockpit2.py:5418` |
| `tag_onderhoud_run` | `cockpit2.py:5568` |
| `copy_stack_inclusie` | `cockpit2.py:5550` |
| `verzoek_besluit` | `cockpit2.py:5437` |
| `kb_blacklist_leeg` | `cockpit2.py:5590` |
| `kb_atoom_edit` | `cockpit2.py:5348` |
| `kb_atoom_related` | `cockpit2.py:5355` |
| `kb_atoom_reference` | `cockpit2.py:5400` |
| `kb_insight_link` | `cockpit2.py:5367` |
| `kb_insight_unlink` | `cockpit2.py:5374` |
| `kb_meta_start` | `cockpit2.py:5380` |
| `kb_atoom_merge` | `cockpit2.py:5608` |
| `kb_atoom_archive` | `cockpit2.py:5629` |
| `kb_atoom_unarchive` | `cockpit2.py:5638` |
| `kb_atoom_naar_spel` | `cockpit2.py:5644` |
| `kb_spel_start` | `cockpit2.py:5665` |
| `kb_spel_add` | `cockpit2.py:5679` |
| `kb_spel_remove` | `cockpit2.py:5689` |
| `kb_spel_flip` | `cockpit2.py:5696` |
| `kb_spel_finish` | `cockpit2.py:5702` |
| `kb_link` | `cockpit2.py:5165` |
| `kb_unlink` | `cockpit2.py:5179` |
| `kb_annotate` | `cockpit2.py:5190` |
| `kb_evidence` | `cockpit2.py:5196` |
| `kb_discuss` | `cockpit2.py:5217` |
| `kb_reformulate` | `cockpit2.py:5223` |
| `kw_nominate` | `cockpit2.py:5713` |
| `kw_nom_accept` | `cockpit2.py:5724` |
| `kw_nom_reject` | `cockpit2.py:5742` |
| `ws_forbid` | `cockpit2.py:5785` |
| `ws_approve` | `cockpit2.py:5790` |
| `proj_add` | `cockpit2.py:1268` |
| `artefact_add` | `cockpit2.py:1321` |
| `artefact_edit` | `cockpit2.py:1365` |
| `artefact_archive` | `cockpit2.py:1392` |
| `pagina_feit_add` | `cockpit2.py:1412` |
| `pagina_feit_del` | `cockpit2.py:1441` |
| `pagina_voorstel` | `cockpit2.py:1472` |
| `proj_status` | `cockpit2.py:1502` |
| `proj_done` | `cockpit2.py:1531` |
| `proj_dod` | `cockpit2.py:1625` |
| `proj_archive` | `cockpit2.py:1639` |
| `proj_unarchive` | `cockpit2.py:1662` |
| `proj_delete` | `cockpit2.py:1698` |
| `proj_edit` | `cockpit2.py:1725` |
| `proj_comment` | `cockpit2.py:1738` |
| `proj_rename` | `cockpit2.py:1749` |
| `proj_describe` | `cockpit2.py:1760` |
| `proj_doc_edit` | `cockpit2.py:1894` |
| `verslag_bevestig_behaald` | `cockpit2.py:1835` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1841` |
| `verslag_overslaan` | `cockpit2.py:1846` |
| `verslag_bijwerken` | `cockpit2.py:1872` |
| `proj_regen_doc` | `cockpit2.py:1771` |
| `proj_settrekker` | `cockpit2.py:1907` |
| `proj_setowner` | `cockpit2.py:1948` |
| `proj_approve` | `cockpit2.py:1967` |
| `proj_discard` | `cockpit2.py:1978` |
| `proj_proposal_accept` | `cockpit2.py:1989` |
| `proj_proposal_reject` | `cockpit2.py:2002` |
| `proj_setlabel` | `cockpit2.py:2015` |
| `proj_setimpact` | `cockpit2.py:2030` |
| `proj_seteffort` | `cockpit2.py:2049` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2072` |
| `proj_setprivate` | `cockpit2.py:2096` |
| `proj_setdue` | `cockpit2.py:2107` |
| `attach_add` | `cockpit2.py:2118` |
| `attach_remove` | `cockpit2.py:2129` |
| `react_add` | `cockpit2.py:2139` |
| `feed_edit` | `cockpit2.py:2150` |
| `feed_remove` | `cockpit2.py:2161` |
| `wall_outcome` | `cockpit2.py:3820` |
| `notif_read` | `cockpit2.py:3916` |
| `notif_processed` | `cockpit2.py:3926` |
| `notif_outcome` | `cockpit2.py:4242` |
| `notif_klaar` | `cockpit2.py:4183` |
| `goedkeur` | `cockpit2.py:3935` |
| `notif_delete` | `cockpit2.py:3980` |
| `notif_add` | `cockpit2.py:4131` |
| `notif_archive` | `cockpit2.py:4364` |
| `metrics2_fav` | `cockpit2.py:3991` |
| `metrics2_unfav` | `cockpit2.py:4006` |
| `metrics2_form` | `cockpit2.py:4011` |
| `metrics2_dim` | `cockpit2.py:4018` |
| `metrics2_compare` | `cockpit2.py:4026` |
| `metrics2_formula` | `cockpit2.py:4116` |
| `source_activate` | `cockpit2.py:4092` |
| `source_deactivate` | `cockpit2.py:4104` |
| `link_pursue` | `cockpit2.py:4066` |
| `link_ignore` | `cockpit2.py:4077` |
| `acc_check` | `cockpit2.py:4035` |
| `ai_reply` | `cockpit2.py:2171` |
| `proj_feed` | `cockpit2.py:2183` |
| `checklist_add` | `cockpit2.py:2231` |
| `checklist_remove` | `cockpit2.py:2271` |
| `plan_akkoord` | `cockpit2.py:2254` |
| `checklist_uitvoer` | `cockpit2.py:2242` |
| `check_add` | `cockpit2.py:2321` |
| `check_accept` | `cockpit2.py:2338` |
| `check_toggle` | `cockpit2.py:2348` |
| `check_skip` | `cockpit2.py:2370` |
| `check_unskip` | `cockpit2.py:2382` |
| `check_handoff` | `cockpit2.py:2403` |
| `check_remove` | `cockpit2.py:2451` |
| `check_rename` | `cockpit2.py:2461` |
| `check_move` | `cockpit2.py:2480` |
| `role_assign` | `cockpit2.py:2494` |
| `role_unassign` | `cockpit2.py:2512` |
| `role_focus` | `cockpit2.py:2531` |
| `radar_approve` | `cockpit2.py:2564` |
| `radar_dismiss` | `cockpit2.py:2574` |
| `radar_promote` | `cockpit2.py:2578` |
| `radar_merge` | `cockpit2.py:2598` |
| `radar_koppel` | `cockpit2.py:2614` |
| `kb_stage_koppel` | `cockpit2.py:2641` |
| `aitask_add` | `cockpit2.py:2682` |
| `aitask_remove` | `cockpit2.py:2713` |
| `skilllink_add` | `cockpit2.py:2741` |
| `means_gap_add` | `cockpit2.py:2771` |
| `persona_skill_add` | `cockpit2.py:2925` |
| `rov2_add` | `cockpit2.py:2940` |
| `rov2_add_to_group` | `cockpit2.py:2952` |
| `rov2_remove` | `cockpit2.py:2964` |
| `rov2_remove_group` | `cockpit2.py:2979` |
| `rov2_setkind` | `cockpit2.py:2997` |
| `rov2_consent` | `cockpit2.py:3010` |
| `rov2_end` | `cockpit2.py:3032` |
| `wo_open` | `cockpit2.py:3056` |
| `wo_close` | `cockpit2.py:3066` |
| `wo_presence` | `cockpit2.py:3082` |
| `wo_present_all` | `cockpit2.py:3093` |
| `vangst_add` | `cockpit2.py:3105` |
| `vangst_tekst` | `cockpit2.py:3153` |
| `vangst_klaar` | `cockpit2.py:3163` |
| `vangst_uitkomst` | `cockpit2.py:3212` |
| `vangst_uitkomst_weg` | `cockpit2.py:3200` |
| `vangst_uitkomst_edit` | `cockpit2.py:3175` |
| `vangst_remove` | `cockpit2.py:3144` |
| `vangst_verwerk` | `cockpit2.py:3328` |
| `wo_checkout` | `cockpit2.py:4373` |
| `noochie_send` | `cockpit2.py:4388` |
| `noochie_reset` | `cockpit2.py:4415` |
| `noochie_ctx` | `cockpit2.py:4423` |
| `cl_add` | `cockpit2.py:4431` |
| `cl_report` | `cockpit2.py:4449` |
| `cl_remove` | `cockpit2.py:4464` |
| `m_add_kpi` | `cockpit2.py:4474` |
| `m_add_from_def` | `cockpit2.py:4506` |
| `def_add` | `cockpit2.py:4521` |
| `catalog_publish` | `cockpit2.py:4543` |
| `def_amend` | `cockpit2.py:4569` |
| `m_add_link` | `cockpit2.py:4611` |
| `m_sample` | `cockpit2.py:4622` |
| `m_remove` | `cockpit2.py:4632` |
| `m_pin` | `cockpit2.py:4642` |
| `m_unpin` | `cockpit2.py:4653` |
| `tile_add` | `cockpit2.py:4691` |
| `indicator_activate` | `cockpit2.py:4663` |
| `tile_remove` | `cockpit2.py:4725` |
| `rov2_set` | `cockpit2.py:4735` |
| `rov2_acc_add` | `cockpit2.py:4735` |
| `rov2_acc_remove` | `cockpit2.py:4735` |
| `rov2_dom_add` | `cockpit2.py:4735` |
| `rov2_dom_remove` | `cockpit2.py:4735` |
| `backlog_add` | `cockpit2.py:4767` |
| `backlog_update_staat` | `cockpit2.py:4779` |
| `backlog_update_prioriteit` | `cockpit2.py:4791` |
| `person_edit` | `cockpit2.py:4803` |
| `person_remove` | `cockpit2.py:4820` |
| `lk_mute` | `cockpit2.py:4841` |
| `claims_term_add` | `cockpit2.py:4944` |
| `claims_term_retract` | `cockpit2.py:4981` |
| `claims_work_status` | `cockpit2.py:4965` |
| `claims_bewijs_link` | `cockpit2.py:5010` |
| `claims_vondst_whitelist` | `cockpit2.py:5034` |
| `claims_regel_uit_vondst` | `cockpit2.py:5060` |
| `claims_to_board` | `cockpit2.py:5092` |
| `persona_edit` | `cockpit2.py:2824` |
| `persona_llm` | `cockpit2.py:2843` |
| `persona_finetune` | `cockpit2.py:2860` |
| `persona_finetune_apply` | `cockpit2.py:2878` |


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
_59 routes · 197 dispatch-acties · 32 stores._
