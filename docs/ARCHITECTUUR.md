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
| `ff_beslis` | `cockpit2.py:5816` |
| `ff_cluster` | `cockpit2.py:5944` |
| `ff_promote` | `cockpit2.py:5874` |
| `ff_demote` | `cockpit2.py:5898` |
| `ff_run` | `cockpit2.py:5917` |
| `kb_new` | `cockpit2.py:5166` |
| `kb_intake` | `cockpit2.py:5248` |
| `kb_intake_url` | `cockpit2.py:5265` |
| `kb_stage_edit` | `cockpit2.py:5284` |
| `kb_stage_accept` | `cockpit2.py:5296` |
| `kb_stage_delete` | `cockpit2.py:5315` |
| `kb_stage_merge` | `cockpit2.py:5321` |
| `kb_stage_commit` | `cockpit2.py:5332` |
| `kb_stage_discard` | `cockpit2.py:5352` |
| `kb_atoom_subject` | `cockpit2.py:5607` |
| `kb_atoom_purge` | `cockpit2.py:5591` |
| `tag_voorstel_besluit` | `cockpit2.py:5428` |
| `tag_onderhoud_run` | `cockpit2.py:5578` |
| `copy_stack_inclusie` | `cockpit2.py:5560` |
| `verzoek_besluit` | `cockpit2.py:5447` |
| `kb_blacklist_leeg` | `cockpit2.py:5600` |
| `kb_atoom_edit` | `cockpit2.py:5358` |
| `kb_atoom_related` | `cockpit2.py:5365` |
| `kb_atoom_reference` | `cockpit2.py:5410` |
| `kb_insight_link` | `cockpit2.py:5377` |
| `kb_insight_unlink` | `cockpit2.py:5384` |
| `kb_meta_start` | `cockpit2.py:5390` |
| `kb_atoom_merge` | `cockpit2.py:5618` |
| `kb_atoom_archive` | `cockpit2.py:5639` |
| `kb_atoom_unarchive` | `cockpit2.py:5648` |
| `kb_atoom_naar_spel` | `cockpit2.py:5654` |
| `kb_spel_start` | `cockpit2.py:5675` |
| `kb_spel_add` | `cockpit2.py:5689` |
| `kb_spel_remove` | `cockpit2.py:5699` |
| `kb_spel_flip` | `cockpit2.py:5706` |
| `kb_spel_finish` | `cockpit2.py:5712` |
| `kb_link` | `cockpit2.py:5175` |
| `kb_unlink` | `cockpit2.py:5189` |
| `kb_annotate` | `cockpit2.py:5200` |
| `kb_evidence` | `cockpit2.py:5206` |
| `kb_discuss` | `cockpit2.py:5227` |
| `kb_reformulate` | `cockpit2.py:5233` |
| `kw_nominate` | `cockpit2.py:5723` |
| `kw_nom_accept` | `cockpit2.py:5734` |
| `kw_nom_reject` | `cockpit2.py:5752` |
| `ws_forbid` | `cockpit2.py:5795` |
| `ws_approve` | `cockpit2.py:5800` |
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
| `wall_outcome` | `cockpit2.py:3830` |
| `notif_read` | `cockpit2.py:3926` |
| `notif_processed` | `cockpit2.py:3936` |
| `notif_outcome` | `cockpit2.py:4252` |
| `notif_klaar` | `cockpit2.py:4193` |
| `goedkeur` | `cockpit2.py:3945` |
| `notif_delete` | `cockpit2.py:3990` |
| `notif_add` | `cockpit2.py:4141` |
| `notif_archive` | `cockpit2.py:4374` |
| `metrics2_fav` | `cockpit2.py:4001` |
| `metrics2_unfav` | `cockpit2.py:4016` |
| `metrics2_form` | `cockpit2.py:4021` |
| `metrics2_dim` | `cockpit2.py:4028` |
| `metrics2_compare` | `cockpit2.py:4036` |
| `metrics2_formula` | `cockpit2.py:4126` |
| `source_activate` | `cockpit2.py:4102` |
| `source_deactivate` | `cockpit2.py:4114` |
| `link_pursue` | `cockpit2.py:4076` |
| `link_ignore` | `cockpit2.py:4087` |
| `acc_check` | `cockpit2.py:4045` |
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
| `role_unassign` | `cockpit2.py:2519` |
| `role_focus` | `cockpit2.py:2541` |
| `radar_approve` | `cockpit2.py:2574` |
| `radar_dismiss` | `cockpit2.py:2584` |
| `radar_promote` | `cockpit2.py:2588` |
| `radar_merge` | `cockpit2.py:2608` |
| `radar_koppel` | `cockpit2.py:2624` |
| `kb_stage_koppel` | `cockpit2.py:2651` |
| `aitask_add` | `cockpit2.py:2692` |
| `aitask_remove` | `cockpit2.py:2723` |
| `skilllink_add` | `cockpit2.py:2751` |
| `means_gap_add` | `cockpit2.py:2781` |
| `persona_skill_add` | `cockpit2.py:2935` |
| `rov2_add` | `cockpit2.py:2950` |
| `rov2_add_to_group` | `cockpit2.py:2962` |
| `rov2_remove` | `cockpit2.py:2974` |
| `rov2_remove_group` | `cockpit2.py:2989` |
| `rov2_setkind` | `cockpit2.py:3007` |
| `rov2_consent` | `cockpit2.py:3020` |
| `rov2_end` | `cockpit2.py:3042` |
| `wo_open` | `cockpit2.py:3066` |
| `wo_close` | `cockpit2.py:3076` |
| `wo_presence` | `cockpit2.py:3092` |
| `wo_present_all` | `cockpit2.py:3103` |
| `vangst_add` | `cockpit2.py:3115` |
| `vangst_tekst` | `cockpit2.py:3163` |
| `vangst_klaar` | `cockpit2.py:3173` |
| `vangst_uitkomst` | `cockpit2.py:3222` |
| `vangst_uitkomst_weg` | `cockpit2.py:3210` |
| `vangst_uitkomst_edit` | `cockpit2.py:3185` |
| `vangst_remove` | `cockpit2.py:3154` |
| `vangst_verwerk` | `cockpit2.py:3338` |
| `wo_checkout` | `cockpit2.py:4383` |
| `noochie_send` | `cockpit2.py:4398` |
| `noochie_reset` | `cockpit2.py:4425` |
| `noochie_ctx` | `cockpit2.py:4433` |
| `cl_add` | `cockpit2.py:4441` |
| `cl_report` | `cockpit2.py:4459` |
| `cl_remove` | `cockpit2.py:4474` |
| `m_add_kpi` | `cockpit2.py:4484` |
| `m_add_from_def` | `cockpit2.py:4516` |
| `def_add` | `cockpit2.py:4531` |
| `catalog_publish` | `cockpit2.py:4553` |
| `def_amend` | `cockpit2.py:4579` |
| `m_add_link` | `cockpit2.py:4621` |
| `m_sample` | `cockpit2.py:4632` |
| `m_remove` | `cockpit2.py:4642` |
| `m_pin` | `cockpit2.py:4652` |
| `m_unpin` | `cockpit2.py:4663` |
| `tile_add` | `cockpit2.py:4701` |
| `indicator_activate` | `cockpit2.py:4673` |
| `tile_remove` | `cockpit2.py:4735` |
| `rov2_set` | `cockpit2.py:4745` |
| `rov2_acc_add` | `cockpit2.py:4745` |
| `rov2_acc_remove` | `cockpit2.py:4745` |
| `rov2_dom_add` | `cockpit2.py:4745` |
| `rov2_dom_remove` | `cockpit2.py:4745` |
| `backlog_add` | `cockpit2.py:4777` |
| `backlog_update_staat` | `cockpit2.py:4789` |
| `backlog_update_prioriteit` | `cockpit2.py:4801` |
| `person_edit` | `cockpit2.py:4813` |
| `person_remove` | `cockpit2.py:4830` |
| `lk_mute` | `cockpit2.py:4851` |
| `claims_term_add` | `cockpit2.py:4954` |
| `claims_term_retract` | `cockpit2.py:4991` |
| `claims_work_status` | `cockpit2.py:4975` |
| `claims_bewijs_link` | `cockpit2.py:5020` |
| `claims_vondst_whitelist` | `cockpit2.py:5044` |
| `claims_regel_uit_vondst` | `cockpit2.py:5070` |
| `claims_to_board` | `cockpit2.py:5102` |
| `persona_edit` | `cockpit2.py:2834` |
| `persona_llm` | `cockpit2.py:2853` |
| `persona_finetune` | `cockpit2.py:2870` |
| `persona_finetune_apply` | `cockpit2.py:2888` |


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
