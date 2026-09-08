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
| `ff_beslis` | `cockpit2.py:5795` |
| `ff_cluster` | `cockpit2.py:5923` |
| `ff_promote` | `cockpit2.py:5853` |
| `ff_demote` | `cockpit2.py:5877` |
| `ff_run` | `cockpit2.py:5896` |
| `kb_new` | `cockpit2.py:5145` |
| `kb_intake` | `cockpit2.py:5227` |
| `kb_intake_url` | `cockpit2.py:5244` |
| `kb_stage_edit` | `cockpit2.py:5263` |
| `kb_stage_accept` | `cockpit2.py:5275` |
| `kb_stage_delete` | `cockpit2.py:5294` |
| `kb_stage_merge` | `cockpit2.py:5300` |
| `kb_stage_commit` | `cockpit2.py:5311` |
| `kb_stage_discard` | `cockpit2.py:5331` |
| `kb_atoom_subject` | `cockpit2.py:5586` |
| `kb_atoom_purge` | `cockpit2.py:5570` |
| `tag_voorstel_besluit` | `cockpit2.py:5407` |
| `tag_onderhoud_run` | `cockpit2.py:5557` |
| `copy_stack_inclusie` | `cockpit2.py:5539` |
| `verzoek_besluit` | `cockpit2.py:5426` |
| `kb_blacklist_leeg` | `cockpit2.py:5579` |
| `kb_atoom_edit` | `cockpit2.py:5337` |
| `kb_atoom_related` | `cockpit2.py:5344` |
| `kb_atoom_reference` | `cockpit2.py:5389` |
| `kb_insight_link` | `cockpit2.py:5356` |
| `kb_insight_unlink` | `cockpit2.py:5363` |
| `kb_meta_start` | `cockpit2.py:5369` |
| `kb_atoom_merge` | `cockpit2.py:5597` |
| `kb_atoom_archive` | `cockpit2.py:5618` |
| `kb_atoom_unarchive` | `cockpit2.py:5627` |
| `kb_atoom_naar_spel` | `cockpit2.py:5633` |
| `kb_spel_start` | `cockpit2.py:5654` |
| `kb_spel_add` | `cockpit2.py:5668` |
| `kb_spel_remove` | `cockpit2.py:5678` |
| `kb_spel_flip` | `cockpit2.py:5685` |
| `kb_spel_finish` | `cockpit2.py:5691` |
| `kb_link` | `cockpit2.py:5154` |
| `kb_unlink` | `cockpit2.py:5168` |
| `kb_annotate` | `cockpit2.py:5179` |
| `kb_evidence` | `cockpit2.py:5185` |
| `kb_discuss` | `cockpit2.py:5206` |
| `kb_reformulate` | `cockpit2.py:5212` |
| `kw_nominate` | `cockpit2.py:5702` |
| `kw_nom_accept` | `cockpit2.py:5713` |
| `kw_nom_reject` | `cockpit2.py:5731` |
| `ws_forbid` | `cockpit2.py:5774` |
| `ws_approve` | `cockpit2.py:5779` |
| `proj_add` | `cockpit2.py:1268` |
| `artefact_add` | `cockpit2.py:1321` |
| `artefact_edit` | `cockpit2.py:1365` |
| `artefact_archive` | `cockpit2.py:1392` |
| `pagina_feit_add` | `cockpit2.py:1412` |
| `pagina_feit_del` | `cockpit2.py:1441` |
| `pagina_voorstel` | `cockpit2.py:1472` |
| `proj_status` | `cockpit2.py:1502` |
| `proj_done` | `cockpit2.py:1520` |
| `proj_dod` | `cockpit2.py:1614` |
| `proj_archive` | `cockpit2.py:1628` |
| `proj_unarchive` | `cockpit2.py:1651` |
| `proj_delete` | `cockpit2.py:1687` |
| `proj_edit` | `cockpit2.py:1714` |
| `proj_comment` | `cockpit2.py:1727` |
| `proj_rename` | `cockpit2.py:1738` |
| `proj_describe` | `cockpit2.py:1749` |
| `proj_doc_edit` | `cockpit2.py:1883` |
| `verslag_bevestig_behaald` | `cockpit2.py:1824` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1830` |
| `verslag_overslaan` | `cockpit2.py:1835` |
| `verslag_bijwerken` | `cockpit2.py:1861` |
| `proj_regen_doc` | `cockpit2.py:1760` |
| `proj_settrekker` | `cockpit2.py:1896` |
| `proj_setowner` | `cockpit2.py:1937` |
| `proj_approve` | `cockpit2.py:1956` |
| `proj_discard` | `cockpit2.py:1967` |
| `proj_proposal_accept` | `cockpit2.py:1978` |
| `proj_proposal_reject` | `cockpit2.py:1991` |
| `proj_setlabel` | `cockpit2.py:2004` |
| `proj_setimpact` | `cockpit2.py:2019` |
| `proj_seteffort` | `cockpit2.py:2038` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2061` |
| `proj_setprivate` | `cockpit2.py:2085` |
| `proj_setdue` | `cockpit2.py:2096` |
| `attach_add` | `cockpit2.py:2107` |
| `attach_remove` | `cockpit2.py:2118` |
| `react_add` | `cockpit2.py:2128` |
| `feed_edit` | `cockpit2.py:2139` |
| `feed_remove` | `cockpit2.py:2150` |
| `wall_outcome` | `cockpit2.py:3809` |
| `notif_read` | `cockpit2.py:3905` |
| `notif_processed` | `cockpit2.py:3915` |
| `notif_outcome` | `cockpit2.py:4231` |
| `notif_klaar` | `cockpit2.py:4172` |
| `goedkeur` | `cockpit2.py:3924` |
| `notif_delete` | `cockpit2.py:3969` |
| `notif_add` | `cockpit2.py:4120` |
| `notif_archive` | `cockpit2.py:4353` |
| `metrics2_fav` | `cockpit2.py:3980` |
| `metrics2_unfav` | `cockpit2.py:3995` |
| `metrics2_form` | `cockpit2.py:4000` |
| `metrics2_dim` | `cockpit2.py:4007` |
| `metrics2_compare` | `cockpit2.py:4015` |
| `metrics2_formula` | `cockpit2.py:4105` |
| `source_activate` | `cockpit2.py:4081` |
| `source_deactivate` | `cockpit2.py:4093` |
| `link_pursue` | `cockpit2.py:4055` |
| `link_ignore` | `cockpit2.py:4066` |
| `acc_check` | `cockpit2.py:4024` |
| `ai_reply` | `cockpit2.py:2160` |
| `proj_feed` | `cockpit2.py:2172` |
| `checklist_add` | `cockpit2.py:2220` |
| `checklist_remove` | `cockpit2.py:2260` |
| `plan_akkoord` | `cockpit2.py:2243` |
| `checklist_uitvoer` | `cockpit2.py:2231` |
| `check_add` | `cockpit2.py:2310` |
| `check_accept` | `cockpit2.py:2327` |
| `check_toggle` | `cockpit2.py:2337` |
| `check_skip` | `cockpit2.py:2359` |
| `check_unskip` | `cockpit2.py:2371` |
| `check_handoff` | `cockpit2.py:2392` |
| `check_remove` | `cockpit2.py:2440` |
| `check_rename` | `cockpit2.py:2450` |
| `check_move` | `cockpit2.py:2469` |
| `role_assign` | `cockpit2.py:2483` |
| `role_unassign` | `cockpit2.py:2501` |
| `role_focus` | `cockpit2.py:2520` |
| `radar_approve` | `cockpit2.py:2553` |
| `radar_dismiss` | `cockpit2.py:2563` |
| `radar_promote` | `cockpit2.py:2567` |
| `radar_merge` | `cockpit2.py:2587` |
| `radar_koppel` | `cockpit2.py:2603` |
| `kb_stage_koppel` | `cockpit2.py:2630` |
| `aitask_add` | `cockpit2.py:2671` |
| `aitask_remove` | `cockpit2.py:2702` |
| `skilllink_add` | `cockpit2.py:2730` |
| `means_gap_add` | `cockpit2.py:2760` |
| `persona_skill_add` | `cockpit2.py:2914` |
| `rov2_add` | `cockpit2.py:2929` |
| `rov2_add_to_group` | `cockpit2.py:2941` |
| `rov2_remove` | `cockpit2.py:2953` |
| `rov2_remove_group` | `cockpit2.py:2968` |
| `rov2_setkind` | `cockpit2.py:2986` |
| `rov2_consent` | `cockpit2.py:2999` |
| `rov2_end` | `cockpit2.py:3021` |
| `wo_open` | `cockpit2.py:3045` |
| `wo_close` | `cockpit2.py:3055` |
| `wo_presence` | `cockpit2.py:3071` |
| `wo_present_all` | `cockpit2.py:3082` |
| `vangst_add` | `cockpit2.py:3094` |
| `vangst_tekst` | `cockpit2.py:3142` |
| `vangst_klaar` | `cockpit2.py:3152` |
| `vangst_uitkomst` | `cockpit2.py:3201` |
| `vangst_uitkomst_weg` | `cockpit2.py:3189` |
| `vangst_uitkomst_edit` | `cockpit2.py:3164` |
| `vangst_remove` | `cockpit2.py:3133` |
| `vangst_verwerk` | `cockpit2.py:3317` |
| `wo_checkout` | `cockpit2.py:4362` |
| `noochie_send` | `cockpit2.py:4377` |
| `noochie_reset` | `cockpit2.py:4404` |
| `noochie_ctx` | `cockpit2.py:4412` |
| `cl_add` | `cockpit2.py:4420` |
| `cl_report` | `cockpit2.py:4438` |
| `cl_remove` | `cockpit2.py:4453` |
| `m_add_kpi` | `cockpit2.py:4463` |
| `m_add_from_def` | `cockpit2.py:4495` |
| `def_add` | `cockpit2.py:4510` |
| `catalog_publish` | `cockpit2.py:4532` |
| `def_amend` | `cockpit2.py:4558` |
| `m_add_link` | `cockpit2.py:4600` |
| `m_sample` | `cockpit2.py:4611` |
| `m_remove` | `cockpit2.py:4621` |
| `m_pin` | `cockpit2.py:4631` |
| `m_unpin` | `cockpit2.py:4642` |
| `tile_add` | `cockpit2.py:4680` |
| `indicator_activate` | `cockpit2.py:4652` |
| `tile_remove` | `cockpit2.py:4714` |
| `rov2_set` | `cockpit2.py:4724` |
| `rov2_acc_add` | `cockpit2.py:4724` |
| `rov2_acc_remove` | `cockpit2.py:4724` |
| `rov2_dom_add` | `cockpit2.py:4724` |
| `rov2_dom_remove` | `cockpit2.py:4724` |
| `backlog_add` | `cockpit2.py:4756` |
| `backlog_update_staat` | `cockpit2.py:4768` |
| `backlog_update_prioriteit` | `cockpit2.py:4780` |
| `person_edit` | `cockpit2.py:4792` |
| `person_remove` | `cockpit2.py:4809` |
| `lk_mute` | `cockpit2.py:4830` |
| `claims_term_add` | `cockpit2.py:4933` |
| `claims_term_retract` | `cockpit2.py:4970` |
| `claims_work_status` | `cockpit2.py:4954` |
| `claims_bewijs_link` | `cockpit2.py:4999` |
| `claims_vondst_whitelist` | `cockpit2.py:5023` |
| `claims_regel_uit_vondst` | `cockpit2.py:5049` |
| `claims_to_board` | `cockpit2.py:5081` |
| `persona_edit` | `cockpit2.py:2813` |
| `persona_llm` | `cockpit2.py:2832` |
| `persona_finetune` | `cockpit2.py:2849` |
| `persona_finetune_apply` | `cockpit2.py:2867` |


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
