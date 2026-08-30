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
| `ff_beslis` | `cockpit2.py:4979` |
| `ff_cluster` | `cockpit2.py:5107` |
| `ff_promote` | `cockpit2.py:5037` |
| `ff_demote` | `cockpit2.py:5061` |
| `ff_run` | `cockpit2.py:5080` |
| `kb_new` | `cockpit2.py:4359` |
| `kb_intake` | `cockpit2.py:4441` |
| `kb_intake_url` | `cockpit2.py:4458` |
| `kb_stage_edit` | `cockpit2.py:4477` |
| `kb_stage_accept` | `cockpit2.py:4489` |
| `kb_stage_delete` | `cockpit2.py:4508` |
| `kb_stage_merge` | `cockpit2.py:4514` |
| `kb_stage_commit` | `cockpit2.py:4525` |
| `kb_stage_discard` | `cockpit2.py:4545` |
| `kb_atoom_subject` | `cockpit2.py:4783` |
| `kb_atoom_purge` | `cockpit2.py:4767` |
| `tag_voorstel_besluit` | `cockpit2.py:4621` |
| `tag_onderhoud_run` | `cockpit2.py:4754` |
| `copy_stack_inclusie` | `cockpit2.py:4736` |
| `verzoek_besluit` | `cockpit2.py:4640` |
| `kb_blacklist_leeg` | `cockpit2.py:4776` |
| `kb_atoom_edit` | `cockpit2.py:4551` |
| `kb_atoom_related` | `cockpit2.py:4558` |
| `kb_atoom_reference` | `cockpit2.py:4603` |
| `kb_insight_link` | `cockpit2.py:4570` |
| `kb_insight_unlink` | `cockpit2.py:4577` |
| `kb_meta_start` | `cockpit2.py:4583` |
| `kb_atoom_merge` | `cockpit2.py:4794` |
| `kb_atoom_archive` | `cockpit2.py:4815` |
| `kb_atoom_unarchive` | `cockpit2.py:4824` |
| `kb_atoom_naar_spel` | `cockpit2.py:4830` |
| `kb_spel_start` | `cockpit2.py:4851` |
| `kb_spel_add` | `cockpit2.py:4865` |
| `kb_spel_remove` | `cockpit2.py:4875` |
| `kb_spel_flip` | `cockpit2.py:4882` |
| `kb_spel_finish` | `cockpit2.py:4888` |
| `kb_link` | `cockpit2.py:4368` |
| `kb_unlink` | `cockpit2.py:4382` |
| `kb_annotate` | `cockpit2.py:4393` |
| `kb_evidence` | `cockpit2.py:4399` |
| `kb_discuss` | `cockpit2.py:4420` |
| `kb_reformulate` | `cockpit2.py:4426` |
| `kw_nominate` | `cockpit2.py:4899` |
| `kw_nom_accept` | `cockpit2.py:4910` |
| `kw_nom_reject` | `cockpit2.py:4928` |
| `ws_forbid` | `cockpit2.py:4958` |
| `ws_approve` | `cockpit2.py:4963` |
| `proj_add` | `cockpit2.py:1207` |
| `artefact_add` | `cockpit2.py:1251` |
| `artefact_edit` | `cockpit2.py:1295` |
| `artefact_archive` | `cockpit2.py:1322` |
| `pagina_feit_add` | `cockpit2.py:1342` |
| `pagina_feit_del` | `cockpit2.py:1371` |
| `pagina_voorstel` | `cockpit2.py:1402` |
| `proj_status` | `cockpit2.py:1432` |
| `proj_done` | `cockpit2.py:1450` |
| `proj_dod` | `cockpit2.py:1505` |
| `proj_archive` | `cockpit2.py:1519` |
| `proj_unarchive` | `cockpit2.py:1542` |
| `proj_delete` | `cockpit2.py:1552` |
| `proj_edit` | `cockpit2.py:1579` |
| `proj_comment` | `cockpit2.py:1592` |
| `proj_rename` | `cockpit2.py:1602` |
| `proj_describe` | `cockpit2.py:1613` |
| `proj_doc_edit` | `cockpit2.py:1646` |
| `proj_regen_doc` | `cockpit2.py:1624` |
| `proj_settrekker` | `cockpit2.py:1659` |
| `proj_setowner` | `cockpit2.py:1696` |
| `proj_approve` | `cockpit2.py:1715` |
| `proj_discard` | `cockpit2.py:1726` |
| `proj_proposal_accept` | `cockpit2.py:1737` |
| `proj_proposal_reject` | `cockpit2.py:1750` |
| `proj_setlabel` | `cockpit2.py:1763` |
| `proj_setimpact` | `cockpit2.py:1778` |
| `proj_seteffort` | `cockpit2.py:1797` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1820` |
| `proj_setprivate` | `cockpit2.py:1844` |
| `proj_setdue` | `cockpit2.py:1855` |
| `attach_add` | `cockpit2.py:1866` |
| `attach_remove` | `cockpit2.py:1877` |
| `react_add` | `cockpit2.py:1887` |
| `feed_edit` | `cockpit2.py:1897` |
| `feed_remove` | `cockpit2.py:1907` |
| `wall_outcome` | `cockpit2.py:3182` |
| `notif_read` | `cockpit2.py:3278` |
| `notif_processed` | `cockpit2.py:3283` |
| `notif_outcome` | `cockpit2.py:3438` |
| `notif_besluit` | `cockpit2.py:3529` |
| `notif_klaar` | `cockpit2.py:3418` |
| `notif_delete` | `cockpit2.py:3288` |
| `notif_add` | `cockpit2.py:3400` |
| `notif_archive` | `cockpit2.py:3574` |
| `metrics2_fav` | `cockpit2.py:3294` |
| `metrics2_unfav` | `cockpit2.py:3304` |
| `metrics2_form` | `cockpit2.py:3309` |
| `metrics2_dim` | `cockpit2.py:3315` |
| `metrics2_compare` | `cockpit2.py:3322` |
| `metrics2_formula` | `cockpit2.py:3385` |
| `source_activate` | `cockpit2.py:3368` |
| `source_deactivate` | `cockpit2.py:3377` |
| `link_pursue` | `cockpit2.py:3349` |
| `link_ignore` | `cockpit2.py:3359` |
| `acc_check` | `cockpit2.py:3330` |
| `ai_reply` | `cockpit2.py:1916` |
| `proj_feed` | `cockpit2.py:1927` |
| `checklist_add` | `cockpit2.py:1974` |
| `checklist_remove` | `cockpit2.py:1985` |
| `check_add` | `cockpit2.py:2033` |
| `check_accept` | `cockpit2.py:2050` |
| `check_toggle` | `cockpit2.py:2060` |
| `check_skip` | `cockpit2.py:2082` |
| `check_unskip` | `cockpit2.py:2094` |
| `check_handoff` | `cockpit2.py:2106` |
| `check_remove` | `cockpit2.py:2120` |
| `role_assign` | `cockpit2.py:2130` |
| `role_unassign` | `cockpit2.py:2148` |
| `role_focus` | `cockpit2.py:2167` |
| `radar_approve` | `cockpit2.py:2200` |
| `radar_dismiss` | `cockpit2.py:2210` |
| `radar_promote` | `cockpit2.py:2214` |
| `radar_merge` | `cockpit2.py:2234` |
| `radar_koppel` | `cockpit2.py:2250` |
| `kb_stage_koppel` | `cockpit2.py:2277` |
| `aitask_add` | `cockpit2.py:2315` |
| `aitask_remove` | `cockpit2.py:2346` |
| `skilllink_add` | `cockpit2.py:2374` |
| `means_gap_add` | `cockpit2.py:2404` |
| `persona_skill_add` | `cockpit2.py:2558` |
| `rov2_add` | `cockpit2.py:2573` |
| `rov2_add_to_group` | `cockpit2.py:2585` |
| `rov2_remove` | `cockpit2.py:2597` |
| `rov2_remove_group` | `cockpit2.py:2612` |
| `rov2_setkind` | `cockpit2.py:2630` |
| `rov2_consent` | `cockpit2.py:2643` |
| `rov2_end` | `cockpit2.py:2665` |
| `wo_open` | `cockpit2.py:2689` |
| `wo_close` | `cockpit2.py:2699` |
| `wo_presence` | `cockpit2.py:2715` |
| `wo_present_all` | `cockpit2.py:2726` |
| `vangst_add` | `cockpit2.py:2738` |
| `vangst_tekst` | `cockpit2.py:2786` |
| `vangst_klaar` | `cockpit2.py:2796` |
| `vangst_uitkomst` | `cockpit2.py:2845` |
| `vangst_uitkomst_weg` | `cockpit2.py:2833` |
| `vangst_uitkomst_edit` | `cockpit2.py:2808` |
| `vangst_remove` | `cockpit2.py:2777` |
| `vangst_verwerk` | `cockpit2.py:2961` |
| `wo_checkout` | `cockpit2.py:3579` |
| `noochie_send` | `cockpit2.py:3594` |
| `noochie_reset` | `cockpit2.py:3620` |
| `noochie_ctx` | `cockpit2.py:3627` |
| `cl_add` | `cockpit2.py:3634` |
| `cl_report` | `cockpit2.py:3652` |
| `cl_remove` | `cockpit2.py:3667` |
| `m_add_kpi` | `cockpit2.py:3677` |
| `m_add_from_def` | `cockpit2.py:3709` |
| `def_add` | `cockpit2.py:3724` |
| `catalog_publish` | `cockpit2.py:3746` |
| `def_amend` | `cockpit2.py:3772` |
| `m_add_link` | `cockpit2.py:3814` |
| `m_sample` | `cockpit2.py:3825` |
| `m_remove` | `cockpit2.py:3835` |
| `m_pin` | `cockpit2.py:3845` |
| `m_unpin` | `cockpit2.py:3856` |
| `tile_add` | `cockpit2.py:3894` |
| `indicator_activate` | `cockpit2.py:3866` |
| `tile_remove` | `cockpit2.py:3928` |
| `rov2_set` | `cockpit2.py:3938` |
| `rov2_acc_add` | `cockpit2.py:3938` |
| `rov2_acc_remove` | `cockpit2.py:3938` |
| `rov2_dom_add` | `cockpit2.py:3938` |
| `rov2_dom_remove` | `cockpit2.py:3938` |
| `backlog_add` | `cockpit2.py:3970` |
| `backlog_update_staat` | `cockpit2.py:3982` |
| `backlog_update_prioriteit` | `cockpit2.py:3994` |
| `person_edit` | `cockpit2.py:4006` |
| `person_remove` | `cockpit2.py:4023` |
| `lk_mute` | `cockpit2.py:4044` |
| `claims_term_add` | `cockpit2.py:4147` |
| `claims_term_retract` | `cockpit2.py:4184` |
| `claims_work_status` | `cockpit2.py:4168` |
| `claims_bewijs_link` | `cockpit2.py:4213` |
| `claims_vondst_whitelist` | `cockpit2.py:4237` |
| `claims_regel_uit_vondst` | `cockpit2.py:4263` |
| `claims_to_board` | `cockpit2.py:4295` |
| `persona_edit` | `cockpit2.py:2457` |
| `persona_llm` | `cockpit2.py:2476` |
| `persona_finetune` | `cockpit2.py:2493` |
| `persona_finetune_apply` | `cockpit2.py:2511` |


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
