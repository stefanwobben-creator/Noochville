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
| `ff_beslis` | `cockpit2.py:5497` |
| `ff_cluster` | `cockpit2.py:5625` |
| `ff_promote` | `cockpit2.py:5555` |
| `ff_demote` | `cockpit2.py:5579` |
| `ff_run` | `cockpit2.py:5598` |
| `kb_new` | `cockpit2.py:4860` |
| `kb_intake` | `cockpit2.py:4942` |
| `kb_intake_url` | `cockpit2.py:4959` |
| `kb_stage_edit` | `cockpit2.py:4978` |
| `kb_stage_accept` | `cockpit2.py:4990` |
| `kb_stage_delete` | `cockpit2.py:5009` |
| `kb_stage_merge` | `cockpit2.py:5015` |
| `kb_stage_commit` | `cockpit2.py:5026` |
| `kb_stage_discard` | `cockpit2.py:5046` |
| `kb_atoom_subject` | `cockpit2.py:5301` |
| `kb_atoom_purge` | `cockpit2.py:5285` |
| `tag_voorstel_besluit` | `cockpit2.py:5122` |
| `tag_onderhoud_run` | `cockpit2.py:5272` |
| `copy_stack_inclusie` | `cockpit2.py:5254` |
| `verzoek_besluit` | `cockpit2.py:5141` |
| `kb_blacklist_leeg` | `cockpit2.py:5294` |
| `kb_atoom_edit` | `cockpit2.py:5052` |
| `kb_atoom_related` | `cockpit2.py:5059` |
| `kb_atoom_reference` | `cockpit2.py:5104` |
| `kb_insight_link` | `cockpit2.py:5071` |
| `kb_insight_unlink` | `cockpit2.py:5078` |
| `kb_meta_start` | `cockpit2.py:5084` |
| `kb_atoom_merge` | `cockpit2.py:5312` |
| `kb_atoom_archive` | `cockpit2.py:5333` |
| `kb_atoom_unarchive` | `cockpit2.py:5342` |
| `kb_atoom_naar_spel` | `cockpit2.py:5348` |
| `kb_spel_start` | `cockpit2.py:5369` |
| `kb_spel_add` | `cockpit2.py:5383` |
| `kb_spel_remove` | `cockpit2.py:5393` |
| `kb_spel_flip` | `cockpit2.py:5400` |
| `kb_spel_finish` | `cockpit2.py:5406` |
| `kb_link` | `cockpit2.py:4869` |
| `kb_unlink` | `cockpit2.py:4883` |
| `kb_annotate` | `cockpit2.py:4894` |
| `kb_evidence` | `cockpit2.py:4900` |
| `kb_discuss` | `cockpit2.py:4921` |
| `kb_reformulate` | `cockpit2.py:4927` |
| `kw_nominate` | `cockpit2.py:5417` |
| `kw_nom_accept` | `cockpit2.py:5428` |
| `kw_nom_reject` | `cockpit2.py:5446` |
| `ws_forbid` | `cockpit2.py:5476` |
| `ws_approve` | `cockpit2.py:5481` |
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
| `wall_outcome` | `cockpit2.py:3638` |
| `notif_read` | `cockpit2.py:3734` |
| `notif_processed` | `cockpit2.py:3739` |
| `notif_outcome` | `cockpit2.py:3958` |
| `notif_klaar` | `cockpit2.py:3905` |
| `notif_delete` | `cockpit2.py:3744` |
| `notif_add` | `cockpit2.py:3856` |
| `notif_archive` | `cockpit2.py:4075` |
| `metrics2_fav` | `cockpit2.py:3750` |
| `metrics2_unfav` | `cockpit2.py:3760` |
| `metrics2_form` | `cockpit2.py:3765` |
| `metrics2_dim` | `cockpit2.py:3771` |
| `metrics2_compare` | `cockpit2.py:3778` |
| `metrics2_formula` | `cockpit2.py:3841` |
| `source_activate` | `cockpit2.py:3824` |
| `source_deactivate` | `cockpit2.py:3833` |
| `link_pursue` | `cockpit2.py:3805` |
| `link_ignore` | `cockpit2.py:3815` |
| `acc_check` | `cockpit2.py:3786` |
| `ai_reply` | `cockpit2.py:2071` |
| `proj_feed` | `cockpit2.py:2082` |
| `checklist_add` | `cockpit2.py:2129` |
| `checklist_remove` | `cockpit2.py:2169` |
| `plan_akkoord` | `cockpit2.py:2152` |
| `checklist_uitvoer` | `cockpit2.py:2140` |
| `check_add` | `cockpit2.py:2218` |
| `check_accept` | `cockpit2.py:2235` |
| `check_toggle` | `cockpit2.py:2245` |
| `check_skip` | `cockpit2.py:2267` |
| `check_unskip` | `cockpit2.py:2279` |
| `check_handoff` | `cockpit2.py:2291` |
| `check_remove` | `cockpit2.py:2305` |
| `role_assign` | `cockpit2.py:2315` |
| `role_unassign` | `cockpit2.py:2333` |
| `role_focus` | `cockpit2.py:2352` |
| `radar_approve` | `cockpit2.py:2385` |
| `radar_dismiss` | `cockpit2.py:2395` |
| `radar_promote` | `cockpit2.py:2399` |
| `radar_merge` | `cockpit2.py:2419` |
| `radar_koppel` | `cockpit2.py:2435` |
| `kb_stage_koppel` | `cockpit2.py:2462` |
| `aitask_add` | `cockpit2.py:2500` |
| `aitask_remove` | `cockpit2.py:2531` |
| `skilllink_add` | `cockpit2.py:2559` |
| `means_gap_add` | `cockpit2.py:2589` |
| `persona_skill_add` | `cockpit2.py:2743` |
| `rov2_add` | `cockpit2.py:2758` |
| `rov2_add_to_group` | `cockpit2.py:2770` |
| `rov2_remove` | `cockpit2.py:2782` |
| `rov2_remove_group` | `cockpit2.py:2797` |
| `rov2_setkind` | `cockpit2.py:2815` |
| `rov2_consent` | `cockpit2.py:2828` |
| `rov2_end` | `cockpit2.py:2850` |
| `wo_open` | `cockpit2.py:2874` |
| `wo_close` | `cockpit2.py:2884` |
| `wo_presence` | `cockpit2.py:2900` |
| `wo_present_all` | `cockpit2.py:2911` |
| `vangst_add` | `cockpit2.py:2923` |
| `vangst_tekst` | `cockpit2.py:2971` |
| `vangst_klaar` | `cockpit2.py:2981` |
| `vangst_uitkomst` | `cockpit2.py:3030` |
| `vangst_uitkomst_weg` | `cockpit2.py:3018` |
| `vangst_uitkomst_edit` | `cockpit2.py:2993` |
| `vangst_remove` | `cockpit2.py:2962` |
| `vangst_verwerk` | `cockpit2.py:3146` |
| `wo_checkout` | `cockpit2.py:4080` |
| `noochie_send` | `cockpit2.py:4095` |
| `noochie_reset` | `cockpit2.py:4121` |
| `noochie_ctx` | `cockpit2.py:4128` |
| `cl_add` | `cockpit2.py:4135` |
| `cl_report` | `cockpit2.py:4153` |
| `cl_remove` | `cockpit2.py:4168` |
| `m_add_kpi` | `cockpit2.py:4178` |
| `m_add_from_def` | `cockpit2.py:4210` |
| `def_add` | `cockpit2.py:4225` |
| `catalog_publish` | `cockpit2.py:4247` |
| `def_amend` | `cockpit2.py:4273` |
| `m_add_link` | `cockpit2.py:4315` |
| `m_sample` | `cockpit2.py:4326` |
| `m_remove` | `cockpit2.py:4336` |
| `m_pin` | `cockpit2.py:4346` |
| `m_unpin` | `cockpit2.py:4357` |
| `tile_add` | `cockpit2.py:4395` |
| `indicator_activate` | `cockpit2.py:4367` |
| `tile_remove` | `cockpit2.py:4429` |
| `rov2_set` | `cockpit2.py:4439` |
| `rov2_acc_add` | `cockpit2.py:4439` |
| `rov2_acc_remove` | `cockpit2.py:4439` |
| `rov2_dom_add` | `cockpit2.py:4439` |
| `rov2_dom_remove` | `cockpit2.py:4439` |
| `backlog_add` | `cockpit2.py:4471` |
| `backlog_update_staat` | `cockpit2.py:4483` |
| `backlog_update_prioriteit` | `cockpit2.py:4495` |
| `person_edit` | `cockpit2.py:4507` |
| `person_remove` | `cockpit2.py:4524` |
| `lk_mute` | `cockpit2.py:4545` |
| `claims_term_add` | `cockpit2.py:4648` |
| `claims_term_retract` | `cockpit2.py:4685` |
| `claims_work_status` | `cockpit2.py:4669` |
| `claims_bewijs_link` | `cockpit2.py:4714` |
| `claims_vondst_whitelist` | `cockpit2.py:4738` |
| `claims_regel_uit_vondst` | `cockpit2.py:4764` |
| `claims_to_board` | `cockpit2.py:4796` |
| `persona_edit` | `cockpit2.py:2642` |
| `persona_llm` | `cockpit2.py:2661` |
| `persona_finetune` | `cockpit2.py:2678` |
| `persona_finetune_apply` | `cockpit2.py:2696` |


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
_59 routes · 194 dispatch-acties · 32 stores._
