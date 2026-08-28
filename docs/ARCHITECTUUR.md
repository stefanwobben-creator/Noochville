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
| `ff_beslis` | `cockpit2.py:4896` |
| `ff_cluster` | `cockpit2.py:5024` |
| `ff_promote` | `cockpit2.py:4954` |
| `ff_demote` | `cockpit2.py:4978` |
| `ff_run` | `cockpit2.py:4997` |
| `kb_new` | `cockpit2.py:4276` |
| `kb_intake` | `cockpit2.py:4358` |
| `kb_intake_url` | `cockpit2.py:4375` |
| `kb_stage_edit` | `cockpit2.py:4394` |
| `kb_stage_accept` | `cockpit2.py:4406` |
| `kb_stage_delete` | `cockpit2.py:4425` |
| `kb_stage_merge` | `cockpit2.py:4431` |
| `kb_stage_commit` | `cockpit2.py:4442` |
| `kb_stage_discard` | `cockpit2.py:4462` |
| `kb_atoom_subject` | `cockpit2.py:4700` |
| `kb_atoom_purge` | `cockpit2.py:4684` |
| `tag_voorstel_besluit` | `cockpit2.py:4538` |
| `tag_onderhoud_run` | `cockpit2.py:4671` |
| `copy_stack_inclusie` | `cockpit2.py:4653` |
| `verzoek_besluit` | `cockpit2.py:4557` |
| `kb_blacklist_leeg` | `cockpit2.py:4693` |
| `kb_atoom_edit` | `cockpit2.py:4468` |
| `kb_atoom_related` | `cockpit2.py:4475` |
| `kb_atoom_reference` | `cockpit2.py:4520` |
| `kb_insight_link` | `cockpit2.py:4487` |
| `kb_insight_unlink` | `cockpit2.py:4494` |
| `kb_meta_start` | `cockpit2.py:4500` |
| `kb_atoom_merge` | `cockpit2.py:4711` |
| `kb_atoom_archive` | `cockpit2.py:4732` |
| `kb_atoom_unarchive` | `cockpit2.py:4741` |
| `kb_atoom_naar_spel` | `cockpit2.py:4747` |
| `kb_spel_start` | `cockpit2.py:4768` |
| `kb_spel_add` | `cockpit2.py:4782` |
| `kb_spel_remove` | `cockpit2.py:4792` |
| `kb_spel_flip` | `cockpit2.py:4799` |
| `kb_spel_finish` | `cockpit2.py:4805` |
| `kb_link` | `cockpit2.py:4285` |
| `kb_unlink` | `cockpit2.py:4299` |
| `kb_annotate` | `cockpit2.py:4310` |
| `kb_evidence` | `cockpit2.py:4316` |
| `kb_discuss` | `cockpit2.py:4337` |
| `kb_reformulate` | `cockpit2.py:4343` |
| `kw_nominate` | `cockpit2.py:4816` |
| `kw_nom_accept` | `cockpit2.py:4827` |
| `kw_nom_reject` | `cockpit2.py:4845` |
| `ws_forbid` | `cockpit2.py:4875` |
| `ws_approve` | `cockpit2.py:4880` |
| `proj_add` | `cockpit2.py:1207` |
| `artefact_add` | `cockpit2.py:1251` |
| `artefact_edit` | `cockpit2.py:1295` |
| `artefact_archive` | `cockpit2.py:1322` |
| `pagina_feit_add` | `cockpit2.py:1342` |
| `pagina_feit_del` | `cockpit2.py:1371` |
| `pagina_voorstel` | `cockpit2.py:1402` |
| `proj_status` | `cockpit2.py:1432` |
| `proj_done` | `cockpit2.py:1450` |
| `proj_dod` | `cockpit2.py:1499` |
| `proj_archive` | `cockpit2.py:1513` |
| `proj_unarchive` | `cockpit2.py:1536` |
| `proj_delete` | `cockpit2.py:1546` |
| `proj_edit` | `cockpit2.py:1573` |
| `proj_comment` | `cockpit2.py:1586` |
| `proj_rename` | `cockpit2.py:1596` |
| `proj_describe` | `cockpit2.py:1607` |
| `proj_doc_edit` | `cockpit2.py:1640` |
| `proj_regen_doc` | `cockpit2.py:1618` |
| `proj_settrekker` | `cockpit2.py:1653` |
| `proj_setowner` | `cockpit2.py:1690` |
| `proj_approve` | `cockpit2.py:1709` |
| `proj_discard` | `cockpit2.py:1720` |
| `proj_proposal_accept` | `cockpit2.py:1731` |
| `proj_proposal_reject` | `cockpit2.py:1744` |
| `proj_setlabel` | `cockpit2.py:1757` |
| `proj_setimpact` | `cockpit2.py:1772` |
| `proj_seteffort` | `cockpit2.py:1791` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1814` |
| `proj_setprivate` | `cockpit2.py:1838` |
| `proj_setdue` | `cockpit2.py:1849` |
| `attach_add` | `cockpit2.py:1860` |
| `attach_remove` | `cockpit2.py:1871` |
| `react_add` | `cockpit2.py:1881` |
| `feed_edit` | `cockpit2.py:1891` |
| `feed_remove` | `cockpit2.py:1901` |
| `wall_outcome` | `cockpit2.py:3112` |
| `notif_read` | `cockpit2.py:3210` |
| `notif_processed` | `cockpit2.py:3215` |
| `notif_outcome` | `cockpit2.py:3362` |
| `notif_besluit` | `cockpit2.py:3449` |
| `notif_klaar` | `cockpit2.py:3348` |
| `notif_delete` | `cockpit2.py:3220` |
| `notif_add` | `cockpit2.py:3332` |
| `notif_archive` | `cockpit2.py:3491` |
| `metrics2_fav` | `cockpit2.py:3226` |
| `metrics2_unfav` | `cockpit2.py:3236` |
| `metrics2_form` | `cockpit2.py:3241` |
| `metrics2_dim` | `cockpit2.py:3247` |
| `metrics2_compare` | `cockpit2.py:3254` |
| `metrics2_formula` | `cockpit2.py:3317` |
| `source_activate` | `cockpit2.py:3300` |
| `source_deactivate` | `cockpit2.py:3309` |
| `link_pursue` | `cockpit2.py:3281` |
| `link_ignore` | `cockpit2.py:3291` |
| `acc_check` | `cockpit2.py:3262` |
| `ai_reply` | `cockpit2.py:1910` |
| `proj_feed` | `cockpit2.py:1921` |
| `checklist_add` | `cockpit2.py:1951` |
| `checklist_remove` | `cockpit2.py:1962` |
| `check_add` | `cockpit2.py:2010` |
| `check_accept` | `cockpit2.py:2027` |
| `check_toggle` | `cockpit2.py:2037` |
| `check_skip` | `cockpit2.py:2059` |
| `check_unskip` | `cockpit2.py:2071` |
| `check_handoff` | `cockpit2.py:2083` |
| `check_remove` | `cockpit2.py:2097` |
| `role_assign` | `cockpit2.py:2107` |
| `role_unassign` | `cockpit2.py:2125` |
| `role_focus` | `cockpit2.py:2144` |
| `radar_approve` | `cockpit2.py:2177` |
| `radar_dismiss` | `cockpit2.py:2187` |
| `radar_promote` | `cockpit2.py:2191` |
| `radar_merge` | `cockpit2.py:2211` |
| `radar_koppel` | `cockpit2.py:2227` |
| `kb_stage_koppel` | `cockpit2.py:2254` |
| `aitask_add` | `cockpit2.py:2292` |
| `aitask_remove` | `cockpit2.py:2323` |
| `skilllink_add` | `cockpit2.py:2351` |
| `means_gap_add` | `cockpit2.py:2381` |
| `persona_skill_add` | `cockpit2.py:2535` |
| `rov2_add` | `cockpit2.py:2550` |
| `rov2_add_to_group` | `cockpit2.py:2562` |
| `rov2_remove` | `cockpit2.py:2574` |
| `rov2_remove_group` | `cockpit2.py:2589` |
| `rov2_setkind` | `cockpit2.py:2607` |
| `rov2_consent` | `cockpit2.py:2620` |
| `rov2_end` | `cockpit2.py:2642` |
| `wo_open` | `cockpit2.py:2666` |
| `wo_close` | `cockpit2.py:2676` |
| `wo_presence` | `cockpit2.py:2692` |
| `wo_present_all` | `cockpit2.py:2703` |
| `vangst_add` | `cockpit2.py:2715` |
| `vangst_tekst` | `cockpit2.py:2763` |
| `vangst_klaar` | `cockpit2.py:2773` |
| `vangst_uitkomst` | `cockpit2.py:2822` |
| `vangst_uitkomst_weg` | `cockpit2.py:2810` |
| `vangst_uitkomst_edit` | `cockpit2.py:2785` |
| `vangst_remove` | `cockpit2.py:2754` |
| `vangst_verwerk` | `cockpit2.py:2957` |
| `wo_checkout` | `cockpit2.py:3496` |
| `noochie_send` | `cockpit2.py:3511` |
| `noochie_reset` | `cockpit2.py:3537` |
| `noochie_ctx` | `cockpit2.py:3544` |
| `cl_add` | `cockpit2.py:3551` |
| `cl_report` | `cockpit2.py:3569` |
| `cl_remove` | `cockpit2.py:3584` |
| `m_add_kpi` | `cockpit2.py:3594` |
| `m_add_from_def` | `cockpit2.py:3626` |
| `def_add` | `cockpit2.py:3641` |
| `catalog_publish` | `cockpit2.py:3663` |
| `def_amend` | `cockpit2.py:3689` |
| `m_add_link` | `cockpit2.py:3731` |
| `m_sample` | `cockpit2.py:3742` |
| `m_remove` | `cockpit2.py:3752` |
| `m_pin` | `cockpit2.py:3762` |
| `m_unpin` | `cockpit2.py:3773` |
| `tile_add` | `cockpit2.py:3811` |
| `indicator_activate` | `cockpit2.py:3783` |
| `tile_remove` | `cockpit2.py:3845` |
| `rov2_set` | `cockpit2.py:3855` |
| `rov2_acc_add` | `cockpit2.py:3855` |
| `rov2_acc_remove` | `cockpit2.py:3855` |
| `rov2_dom_add` | `cockpit2.py:3855` |
| `rov2_dom_remove` | `cockpit2.py:3855` |
| `backlog_add` | `cockpit2.py:3887` |
| `backlog_update_staat` | `cockpit2.py:3899` |
| `backlog_update_prioriteit` | `cockpit2.py:3911` |
| `person_edit` | `cockpit2.py:3923` |
| `person_remove` | `cockpit2.py:3940` |
| `lk_mute` | `cockpit2.py:3961` |
| `claims_term_add` | `cockpit2.py:4064` |
| `claims_term_retract` | `cockpit2.py:4101` |
| `claims_work_status` | `cockpit2.py:4085` |
| `claims_bewijs_link` | `cockpit2.py:4130` |
| `claims_vondst_whitelist` | `cockpit2.py:4154` |
| `claims_regel_uit_vondst` | `cockpit2.py:4180` |
| `claims_to_board` | `cockpit2.py:4212` |
| `persona_edit` | `cockpit2.py:2434` |
| `persona_llm` | `cockpit2.py:2453` |
| `persona_finetune` | `cockpit2.py:2470` |
| `persona_finetune_apply` | `cockpit2.py:2488` |


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
_57 routes · 189 dispatch-acties · 32 stores._
