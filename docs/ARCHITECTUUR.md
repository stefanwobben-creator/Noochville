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
| `ff_beslis` | `cockpit2.py:5649` |
| `ff_cluster` | `cockpit2.py:5777` |
| `ff_promote` | `cockpit2.py:5707` |
| `ff_demote` | `cockpit2.py:5731` |
| `ff_run` | `cockpit2.py:5750` |
| `kb_new` | `cockpit2.py:5012` |
| `kb_intake` | `cockpit2.py:5094` |
| `kb_intake_url` | `cockpit2.py:5111` |
| `kb_stage_edit` | `cockpit2.py:5130` |
| `kb_stage_accept` | `cockpit2.py:5142` |
| `kb_stage_delete` | `cockpit2.py:5161` |
| `kb_stage_merge` | `cockpit2.py:5167` |
| `kb_stage_commit` | `cockpit2.py:5178` |
| `kb_stage_discard` | `cockpit2.py:5198` |
| `kb_atoom_subject` | `cockpit2.py:5453` |
| `kb_atoom_purge` | `cockpit2.py:5437` |
| `tag_voorstel_besluit` | `cockpit2.py:5274` |
| `tag_onderhoud_run` | `cockpit2.py:5424` |
| `copy_stack_inclusie` | `cockpit2.py:5406` |
| `verzoek_besluit` | `cockpit2.py:5293` |
| `kb_blacklist_leeg` | `cockpit2.py:5446` |
| `kb_atoom_edit` | `cockpit2.py:5204` |
| `kb_atoom_related` | `cockpit2.py:5211` |
| `kb_atoom_reference` | `cockpit2.py:5256` |
| `kb_insight_link` | `cockpit2.py:5223` |
| `kb_insight_unlink` | `cockpit2.py:5230` |
| `kb_meta_start` | `cockpit2.py:5236` |
| `kb_atoom_merge` | `cockpit2.py:5464` |
| `kb_atoom_archive` | `cockpit2.py:5485` |
| `kb_atoom_unarchive` | `cockpit2.py:5494` |
| `kb_atoom_naar_spel` | `cockpit2.py:5500` |
| `kb_spel_start` | `cockpit2.py:5521` |
| `kb_spel_add` | `cockpit2.py:5535` |
| `kb_spel_remove` | `cockpit2.py:5545` |
| `kb_spel_flip` | `cockpit2.py:5552` |
| `kb_spel_finish` | `cockpit2.py:5558` |
| `kb_link` | `cockpit2.py:5021` |
| `kb_unlink` | `cockpit2.py:5035` |
| `kb_annotate` | `cockpit2.py:5046` |
| `kb_evidence` | `cockpit2.py:5052` |
| `kb_discuss` | `cockpit2.py:5073` |
| `kb_reformulate` | `cockpit2.py:5079` |
| `kw_nominate` | `cockpit2.py:5569` |
| `kw_nom_accept` | `cockpit2.py:5580` |
| `kw_nom_reject` | `cockpit2.py:5598` |
| `ws_forbid` | `cockpit2.py:5628` |
| `ws_approve` | `cockpit2.py:5633` |
| `proj_add` | `cockpit2.py:1239` |
| `artefact_add` | `cockpit2.py:1292` |
| `artefact_edit` | `cockpit2.py:1336` |
| `artefact_archive` | `cockpit2.py:1363` |
| `pagina_feit_add` | `cockpit2.py:1383` |
| `pagina_feit_del` | `cockpit2.py:1412` |
| `pagina_voorstel` | `cockpit2.py:1443` |
| `proj_status` | `cockpit2.py:1473` |
| `proj_done` | `cockpit2.py:1491` |
| `proj_dod` | `cockpit2.py:1585` |
| `proj_archive` | `cockpit2.py:1599` |
| `proj_unarchive` | `cockpit2.py:1622` |
| `proj_delete` | `cockpit2.py:1632` |
| `proj_edit` | `cockpit2.py:1659` |
| `proj_comment` | `cockpit2.py:1672` |
| `proj_rename` | `cockpit2.py:1682` |
| `proj_describe` | `cockpit2.py:1693` |
| `proj_doc_edit` | `cockpit2.py:1827` |
| `verslag_bevestig_behaald` | `cockpit2.py:1768` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1774` |
| `verslag_overslaan` | `cockpit2.py:1779` |
| `verslag_bijwerken` | `cockpit2.py:1805` |
| `proj_regen_doc` | `cockpit2.py:1704` |
| `proj_settrekker` | `cockpit2.py:1840` |
| `proj_setowner` | `cockpit2.py:1881` |
| `proj_approve` | `cockpit2.py:1900` |
| `proj_discard` | `cockpit2.py:1911` |
| `proj_proposal_accept` | `cockpit2.py:1922` |
| `proj_proposal_reject` | `cockpit2.py:1935` |
| `proj_setlabel` | `cockpit2.py:1948` |
| `proj_setimpact` | `cockpit2.py:1963` |
| `proj_seteffort` | `cockpit2.py:1982` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2005` |
| `proj_setprivate` | `cockpit2.py:2029` |
| `proj_setdue` | `cockpit2.py:2040` |
| `attach_add` | `cockpit2.py:2051` |
| `attach_remove` | `cockpit2.py:2062` |
| `react_add` | `cockpit2.py:2072` |
| `feed_edit` | `cockpit2.py:2082` |
| `feed_remove` | `cockpit2.py:2092` |
| `wall_outcome` | `cockpit2.py:3745` |
| `notif_read` | `cockpit2.py:3841` |
| `notif_processed` | `cockpit2.py:3846` |
| `notif_outcome` | `cockpit2.py:4110` |
| `notif_klaar` | `cockpit2.py:4057` |
| `goedkeur` | `cockpit2.py:3851` |
| `notif_delete` | `cockpit2.py:3896` |
| `notif_add` | `cockpit2.py:4008` |
| `notif_archive` | `cockpit2.py:4227` |
| `metrics2_fav` | `cockpit2.py:3902` |
| `metrics2_unfav` | `cockpit2.py:3912` |
| `metrics2_form` | `cockpit2.py:3917` |
| `metrics2_dim` | `cockpit2.py:3923` |
| `metrics2_compare` | `cockpit2.py:3930` |
| `metrics2_formula` | `cockpit2.py:3993` |
| `source_activate` | `cockpit2.py:3976` |
| `source_deactivate` | `cockpit2.py:3985` |
| `link_pursue` | `cockpit2.py:3957` |
| `link_ignore` | `cockpit2.py:3967` |
| `acc_check` | `cockpit2.py:3938` |
| `ai_reply` | `cockpit2.py:2101` |
| `proj_feed` | `cockpit2.py:2112` |
| `checklist_add` | `cockpit2.py:2159` |
| `checklist_remove` | `cockpit2.py:2199` |
| `plan_akkoord` | `cockpit2.py:2182` |
| `checklist_uitvoer` | `cockpit2.py:2170` |
| `check_add` | `cockpit2.py:2249` |
| `check_accept` | `cockpit2.py:2266` |
| `check_toggle` | `cockpit2.py:2276` |
| `check_skip` | `cockpit2.py:2298` |
| `check_unskip` | `cockpit2.py:2310` |
| `check_handoff` | `cockpit2.py:2331` |
| `check_remove` | `cockpit2.py:2379` |
| `check_rename` | `cockpit2.py:2389` |
| `check_move` | `cockpit2.py:2408` |
| `role_assign` | `cockpit2.py:2422` |
| `role_unassign` | `cockpit2.py:2440` |
| `role_focus` | `cockpit2.py:2459` |
| `radar_approve` | `cockpit2.py:2492` |
| `radar_dismiss` | `cockpit2.py:2502` |
| `radar_promote` | `cockpit2.py:2506` |
| `radar_merge` | `cockpit2.py:2526` |
| `radar_koppel` | `cockpit2.py:2542` |
| `kb_stage_koppel` | `cockpit2.py:2569` |
| `aitask_add` | `cockpit2.py:2607` |
| `aitask_remove` | `cockpit2.py:2638` |
| `skilllink_add` | `cockpit2.py:2666` |
| `means_gap_add` | `cockpit2.py:2696` |
| `persona_skill_add` | `cockpit2.py:2850` |
| `rov2_add` | `cockpit2.py:2865` |
| `rov2_add_to_group` | `cockpit2.py:2877` |
| `rov2_remove` | `cockpit2.py:2889` |
| `rov2_remove_group` | `cockpit2.py:2904` |
| `rov2_setkind` | `cockpit2.py:2922` |
| `rov2_consent` | `cockpit2.py:2935` |
| `rov2_end` | `cockpit2.py:2957` |
| `wo_open` | `cockpit2.py:2981` |
| `wo_close` | `cockpit2.py:2991` |
| `wo_presence` | `cockpit2.py:3007` |
| `wo_present_all` | `cockpit2.py:3018` |
| `vangst_add` | `cockpit2.py:3030` |
| `vangst_tekst` | `cockpit2.py:3078` |
| `vangst_klaar` | `cockpit2.py:3088` |
| `vangst_uitkomst` | `cockpit2.py:3137` |
| `vangst_uitkomst_weg` | `cockpit2.py:3125` |
| `vangst_uitkomst_edit` | `cockpit2.py:3100` |
| `vangst_remove` | `cockpit2.py:3069` |
| `vangst_verwerk` | `cockpit2.py:3253` |
| `wo_checkout` | `cockpit2.py:4232` |
| `noochie_send` | `cockpit2.py:4247` |
| `noochie_reset` | `cockpit2.py:4273` |
| `noochie_ctx` | `cockpit2.py:4280` |
| `cl_add` | `cockpit2.py:4287` |
| `cl_report` | `cockpit2.py:4305` |
| `cl_remove` | `cockpit2.py:4320` |
| `m_add_kpi` | `cockpit2.py:4330` |
| `m_add_from_def` | `cockpit2.py:4362` |
| `def_add` | `cockpit2.py:4377` |
| `catalog_publish` | `cockpit2.py:4399` |
| `def_amend` | `cockpit2.py:4425` |
| `m_add_link` | `cockpit2.py:4467` |
| `m_sample` | `cockpit2.py:4478` |
| `m_remove` | `cockpit2.py:4488` |
| `m_pin` | `cockpit2.py:4498` |
| `m_unpin` | `cockpit2.py:4509` |
| `tile_add` | `cockpit2.py:4547` |
| `indicator_activate` | `cockpit2.py:4519` |
| `tile_remove` | `cockpit2.py:4581` |
| `rov2_set` | `cockpit2.py:4591` |
| `rov2_acc_add` | `cockpit2.py:4591` |
| `rov2_acc_remove` | `cockpit2.py:4591` |
| `rov2_dom_add` | `cockpit2.py:4591` |
| `rov2_dom_remove` | `cockpit2.py:4591` |
| `backlog_add` | `cockpit2.py:4623` |
| `backlog_update_staat` | `cockpit2.py:4635` |
| `backlog_update_prioriteit` | `cockpit2.py:4647` |
| `person_edit` | `cockpit2.py:4659` |
| `person_remove` | `cockpit2.py:4676` |
| `lk_mute` | `cockpit2.py:4697` |
| `claims_term_add` | `cockpit2.py:4800` |
| `claims_term_retract` | `cockpit2.py:4837` |
| `claims_work_status` | `cockpit2.py:4821` |
| `claims_bewijs_link` | `cockpit2.py:4866` |
| `claims_vondst_whitelist` | `cockpit2.py:4890` |
| `claims_regel_uit_vondst` | `cockpit2.py:4916` |
| `claims_to_board` | `cockpit2.py:4948` |
| `persona_edit` | `cockpit2.py:2749` |
| `persona_llm` | `cockpit2.py:2768` |
| `persona_finetune` | `cockpit2.py:2785` |
| `persona_finetune_apply` | `cockpit2.py:2803` |


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
