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
| `ff_beslis` | `cockpit2.py:5467` |
| `ff_cluster` | `cockpit2.py:5595` |
| `ff_promote` | `cockpit2.py:5525` |
| `ff_demote` | `cockpit2.py:5549` |
| `ff_run` | `cockpit2.py:5568` |
| `kb_new` | `cockpit2.py:4830` |
| `kb_intake` | `cockpit2.py:4912` |
| `kb_intake_url` | `cockpit2.py:4929` |
| `kb_stage_edit` | `cockpit2.py:4948` |
| `kb_stage_accept` | `cockpit2.py:4960` |
| `kb_stage_delete` | `cockpit2.py:4979` |
| `kb_stage_merge` | `cockpit2.py:4985` |
| `kb_stage_commit` | `cockpit2.py:4996` |
| `kb_stage_discard` | `cockpit2.py:5016` |
| `kb_atoom_subject` | `cockpit2.py:5271` |
| `kb_atoom_purge` | `cockpit2.py:5255` |
| `tag_voorstel_besluit` | `cockpit2.py:5092` |
| `tag_onderhoud_run` | `cockpit2.py:5242` |
| `copy_stack_inclusie` | `cockpit2.py:5224` |
| `verzoek_besluit` | `cockpit2.py:5111` |
| `kb_blacklist_leeg` | `cockpit2.py:5264` |
| `kb_atoom_edit` | `cockpit2.py:5022` |
| `kb_atoom_related` | `cockpit2.py:5029` |
| `kb_atoom_reference` | `cockpit2.py:5074` |
| `kb_insight_link` | `cockpit2.py:5041` |
| `kb_insight_unlink` | `cockpit2.py:5048` |
| `kb_meta_start` | `cockpit2.py:5054` |
| `kb_atoom_merge` | `cockpit2.py:5282` |
| `kb_atoom_archive` | `cockpit2.py:5303` |
| `kb_atoom_unarchive` | `cockpit2.py:5312` |
| `kb_atoom_naar_spel` | `cockpit2.py:5318` |
| `kb_spel_start` | `cockpit2.py:5339` |
| `kb_spel_add` | `cockpit2.py:5353` |
| `kb_spel_remove` | `cockpit2.py:5363` |
| `kb_spel_flip` | `cockpit2.py:5370` |
| `kb_spel_finish` | `cockpit2.py:5376` |
| `kb_link` | `cockpit2.py:4839` |
| `kb_unlink` | `cockpit2.py:4853` |
| `kb_annotate` | `cockpit2.py:4864` |
| `kb_evidence` | `cockpit2.py:4870` |
| `kb_discuss` | `cockpit2.py:4891` |
| `kb_reformulate` | `cockpit2.py:4897` |
| `kw_nominate` | `cockpit2.py:5387` |
| `kw_nom_accept` | `cockpit2.py:5398` |
| `kw_nom_reject` | `cockpit2.py:5416` |
| `ws_forbid` | `cockpit2.py:5446` |
| `ws_approve` | `cockpit2.py:5451` |
| `proj_add` | `cockpit2.py:1209` |
| `artefact_add` | `cockpit2.py:1262` |
| `artefact_edit` | `cockpit2.py:1306` |
| `artefact_archive` | `cockpit2.py:1333` |
| `pagina_feit_add` | `cockpit2.py:1353` |
| `pagina_feit_del` | `cockpit2.py:1382` |
| `pagina_voorstel` | `cockpit2.py:1413` |
| `proj_status` | `cockpit2.py:1443` |
| `proj_done` | `cockpit2.py:1461` |
| `proj_dod` | `cockpit2.py:1555` |
| `proj_archive` | `cockpit2.py:1569` |
| `proj_unarchive` | `cockpit2.py:1592` |
| `proj_delete` | `cockpit2.py:1602` |
| `proj_edit` | `cockpit2.py:1629` |
| `proj_comment` | `cockpit2.py:1642` |
| `proj_rename` | `cockpit2.py:1652` |
| `proj_describe` | `cockpit2.py:1663` |
| `proj_doc_edit` | `cockpit2.py:1797` |
| `verslag_bevestig_behaald` | `cockpit2.py:1738` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1744` |
| `verslag_overslaan` | `cockpit2.py:1749` |
| `verslag_bijwerken` | `cockpit2.py:1775` |
| `proj_regen_doc` | `cockpit2.py:1674` |
| `proj_settrekker` | `cockpit2.py:1810` |
| `proj_setowner` | `cockpit2.py:1851` |
| `proj_approve` | `cockpit2.py:1870` |
| `proj_discard` | `cockpit2.py:1881` |
| `proj_proposal_accept` | `cockpit2.py:1892` |
| `proj_proposal_reject` | `cockpit2.py:1905` |
| `proj_setlabel` | `cockpit2.py:1918` |
| `proj_setimpact` | `cockpit2.py:1933` |
| `proj_seteffort` | `cockpit2.py:1952` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1975` |
| `proj_setprivate` | `cockpit2.py:1999` |
| `proj_setdue` | `cockpit2.py:2010` |
| `attach_add` | `cockpit2.py:2021` |
| `attach_remove` | `cockpit2.py:2032` |
| `react_add` | `cockpit2.py:2042` |
| `feed_edit` | `cockpit2.py:2052` |
| `feed_remove` | `cockpit2.py:2062` |
| `wall_outcome` | `cockpit2.py:3608` |
| `notif_read` | `cockpit2.py:3704` |
| `notif_processed` | `cockpit2.py:3709` |
| `notif_outcome` | `cockpit2.py:3928` |
| `notif_klaar` | `cockpit2.py:3875` |
| `notif_delete` | `cockpit2.py:3714` |
| `notif_add` | `cockpit2.py:3826` |
| `notif_archive` | `cockpit2.py:4045` |
| `metrics2_fav` | `cockpit2.py:3720` |
| `metrics2_unfav` | `cockpit2.py:3730` |
| `metrics2_form` | `cockpit2.py:3735` |
| `metrics2_dim` | `cockpit2.py:3741` |
| `metrics2_compare` | `cockpit2.py:3748` |
| `metrics2_formula` | `cockpit2.py:3811` |
| `source_activate` | `cockpit2.py:3794` |
| `source_deactivate` | `cockpit2.py:3803` |
| `link_pursue` | `cockpit2.py:3775` |
| `link_ignore` | `cockpit2.py:3785` |
| `acc_check` | `cockpit2.py:3756` |
| `ai_reply` | `cockpit2.py:2071` |
| `proj_feed` | `cockpit2.py:2082` |
| `checklist_add` | `cockpit2.py:2129` |
| `checklist_remove` | `cockpit2.py:2140` |
| `check_add` | `cockpit2.py:2188` |
| `check_accept` | `cockpit2.py:2205` |
| `check_toggle` | `cockpit2.py:2215` |
| `check_skip` | `cockpit2.py:2237` |
| `check_unskip` | `cockpit2.py:2249` |
| `check_handoff` | `cockpit2.py:2261` |
| `check_remove` | `cockpit2.py:2275` |
| `role_assign` | `cockpit2.py:2285` |
| `role_unassign` | `cockpit2.py:2303` |
| `role_focus` | `cockpit2.py:2322` |
| `radar_approve` | `cockpit2.py:2355` |
| `radar_dismiss` | `cockpit2.py:2365` |
| `radar_promote` | `cockpit2.py:2369` |
| `radar_merge` | `cockpit2.py:2389` |
| `radar_koppel` | `cockpit2.py:2405` |
| `kb_stage_koppel` | `cockpit2.py:2432` |
| `aitask_add` | `cockpit2.py:2470` |
| `aitask_remove` | `cockpit2.py:2501` |
| `skilllink_add` | `cockpit2.py:2529` |
| `means_gap_add` | `cockpit2.py:2559` |
| `persona_skill_add` | `cockpit2.py:2713` |
| `rov2_add` | `cockpit2.py:2728` |
| `rov2_add_to_group` | `cockpit2.py:2740` |
| `rov2_remove` | `cockpit2.py:2752` |
| `rov2_remove_group` | `cockpit2.py:2767` |
| `rov2_setkind` | `cockpit2.py:2785` |
| `rov2_consent` | `cockpit2.py:2798` |
| `rov2_end` | `cockpit2.py:2820` |
| `wo_open` | `cockpit2.py:2844` |
| `wo_close` | `cockpit2.py:2854` |
| `wo_presence` | `cockpit2.py:2870` |
| `wo_present_all` | `cockpit2.py:2881` |
| `vangst_add` | `cockpit2.py:2893` |
| `vangst_tekst` | `cockpit2.py:2941` |
| `vangst_klaar` | `cockpit2.py:2951` |
| `vangst_uitkomst` | `cockpit2.py:3000` |
| `vangst_uitkomst_weg` | `cockpit2.py:2988` |
| `vangst_uitkomst_edit` | `cockpit2.py:2963` |
| `vangst_remove` | `cockpit2.py:2932` |
| `vangst_verwerk` | `cockpit2.py:3116` |
| `wo_checkout` | `cockpit2.py:4050` |
| `noochie_send` | `cockpit2.py:4065` |
| `noochie_reset` | `cockpit2.py:4091` |
| `noochie_ctx` | `cockpit2.py:4098` |
| `cl_add` | `cockpit2.py:4105` |
| `cl_report` | `cockpit2.py:4123` |
| `cl_remove` | `cockpit2.py:4138` |
| `m_add_kpi` | `cockpit2.py:4148` |
| `m_add_from_def` | `cockpit2.py:4180` |
| `def_add` | `cockpit2.py:4195` |
| `catalog_publish` | `cockpit2.py:4217` |
| `def_amend` | `cockpit2.py:4243` |
| `m_add_link` | `cockpit2.py:4285` |
| `m_sample` | `cockpit2.py:4296` |
| `m_remove` | `cockpit2.py:4306` |
| `m_pin` | `cockpit2.py:4316` |
| `m_unpin` | `cockpit2.py:4327` |
| `tile_add` | `cockpit2.py:4365` |
| `indicator_activate` | `cockpit2.py:4337` |
| `tile_remove` | `cockpit2.py:4399` |
| `rov2_set` | `cockpit2.py:4409` |
| `rov2_acc_add` | `cockpit2.py:4409` |
| `rov2_acc_remove` | `cockpit2.py:4409` |
| `rov2_dom_add` | `cockpit2.py:4409` |
| `rov2_dom_remove` | `cockpit2.py:4409` |
| `backlog_add` | `cockpit2.py:4441` |
| `backlog_update_staat` | `cockpit2.py:4453` |
| `backlog_update_prioriteit` | `cockpit2.py:4465` |
| `person_edit` | `cockpit2.py:4477` |
| `person_remove` | `cockpit2.py:4494` |
| `lk_mute` | `cockpit2.py:4515` |
| `claims_term_add` | `cockpit2.py:4618` |
| `claims_term_retract` | `cockpit2.py:4655` |
| `claims_work_status` | `cockpit2.py:4639` |
| `claims_bewijs_link` | `cockpit2.py:4684` |
| `claims_vondst_whitelist` | `cockpit2.py:4708` |
| `claims_regel_uit_vondst` | `cockpit2.py:4734` |
| `claims_to_board` | `cockpit2.py:4766` |
| `persona_edit` | `cockpit2.py:2612` |
| `persona_llm` | `cockpit2.py:2631` |
| `persona_finetune` | `cockpit2.py:2648` |
| `persona_finetune_apply` | `cockpit2.py:2666` |


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
_59 routes · 192 dispatch-acties · 32 stores._
