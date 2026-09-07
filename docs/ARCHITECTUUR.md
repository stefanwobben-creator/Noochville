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
| `ff_beslis` | `cockpit2.py:5675` |
| `ff_cluster` | `cockpit2.py:5803` |
| `ff_promote` | `cockpit2.py:5733` |
| `ff_demote` | `cockpit2.py:5757` |
| `ff_run` | `cockpit2.py:5776` |
| `kb_new` | `cockpit2.py:5038` |
| `kb_intake` | `cockpit2.py:5120` |
| `kb_intake_url` | `cockpit2.py:5137` |
| `kb_stage_edit` | `cockpit2.py:5156` |
| `kb_stage_accept` | `cockpit2.py:5168` |
| `kb_stage_delete` | `cockpit2.py:5187` |
| `kb_stage_merge` | `cockpit2.py:5193` |
| `kb_stage_commit` | `cockpit2.py:5204` |
| `kb_stage_discard` | `cockpit2.py:5224` |
| `kb_atoom_subject` | `cockpit2.py:5479` |
| `kb_atoom_purge` | `cockpit2.py:5463` |
| `tag_voorstel_besluit` | `cockpit2.py:5300` |
| `tag_onderhoud_run` | `cockpit2.py:5450` |
| `copy_stack_inclusie` | `cockpit2.py:5432` |
| `verzoek_besluit` | `cockpit2.py:5319` |
| `kb_blacklist_leeg` | `cockpit2.py:5472` |
| `kb_atoom_edit` | `cockpit2.py:5230` |
| `kb_atoom_related` | `cockpit2.py:5237` |
| `kb_atoom_reference` | `cockpit2.py:5282` |
| `kb_insight_link` | `cockpit2.py:5249` |
| `kb_insight_unlink` | `cockpit2.py:5256` |
| `kb_meta_start` | `cockpit2.py:5262` |
| `kb_atoom_merge` | `cockpit2.py:5490` |
| `kb_atoom_archive` | `cockpit2.py:5511` |
| `kb_atoom_unarchive` | `cockpit2.py:5520` |
| `kb_atoom_naar_spel` | `cockpit2.py:5526` |
| `kb_spel_start` | `cockpit2.py:5547` |
| `kb_spel_add` | `cockpit2.py:5561` |
| `kb_spel_remove` | `cockpit2.py:5571` |
| `kb_spel_flip` | `cockpit2.py:5578` |
| `kb_spel_finish` | `cockpit2.py:5584` |
| `kb_link` | `cockpit2.py:5047` |
| `kb_unlink` | `cockpit2.py:5061` |
| `kb_annotate` | `cockpit2.py:5072` |
| `kb_evidence` | `cockpit2.py:5078` |
| `kb_discuss` | `cockpit2.py:5099` |
| `kb_reformulate` | `cockpit2.py:5105` |
| `kw_nominate` | `cockpit2.py:5595` |
| `kw_nom_accept` | `cockpit2.py:5606` |
| `kw_nom_reject` | `cockpit2.py:5624` |
| `ws_forbid` | `cockpit2.py:5654` |
| `ws_approve` | `cockpit2.py:5659` |
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
| `proj_delete` | `cockpit2.py:1658` |
| `proj_edit` | `cockpit2.py:1685` |
| `proj_comment` | `cockpit2.py:1698` |
| `proj_rename` | `cockpit2.py:1708` |
| `proj_describe` | `cockpit2.py:1719` |
| `proj_doc_edit` | `cockpit2.py:1853` |
| `verslag_bevestig_behaald` | `cockpit2.py:1794` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1800` |
| `verslag_overslaan` | `cockpit2.py:1805` |
| `verslag_bijwerken` | `cockpit2.py:1831` |
| `proj_regen_doc` | `cockpit2.py:1730` |
| `proj_settrekker` | `cockpit2.py:1866` |
| `proj_setowner` | `cockpit2.py:1907` |
| `proj_approve` | `cockpit2.py:1926` |
| `proj_discard` | `cockpit2.py:1937` |
| `proj_proposal_accept` | `cockpit2.py:1948` |
| `proj_proposal_reject` | `cockpit2.py:1961` |
| `proj_setlabel` | `cockpit2.py:1974` |
| `proj_setimpact` | `cockpit2.py:1989` |
| `proj_seteffort` | `cockpit2.py:2008` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2031` |
| `proj_setprivate` | `cockpit2.py:2055` |
| `proj_setdue` | `cockpit2.py:2066` |
| `attach_add` | `cockpit2.py:2077` |
| `attach_remove` | `cockpit2.py:2088` |
| `react_add` | `cockpit2.py:2098` |
| `feed_edit` | `cockpit2.py:2108` |
| `feed_remove` | `cockpit2.py:2118` |
| `wall_outcome` | `cockpit2.py:3771` |
| `notif_read` | `cockpit2.py:3867` |
| `notif_processed` | `cockpit2.py:3872` |
| `notif_outcome` | `cockpit2.py:4136` |
| `notif_klaar` | `cockpit2.py:4083` |
| `goedkeur` | `cockpit2.py:3877` |
| `notif_delete` | `cockpit2.py:3922` |
| `notif_add` | `cockpit2.py:4034` |
| `notif_archive` | `cockpit2.py:4253` |
| `metrics2_fav` | `cockpit2.py:3928` |
| `metrics2_unfav` | `cockpit2.py:3938` |
| `metrics2_form` | `cockpit2.py:3943` |
| `metrics2_dim` | `cockpit2.py:3949` |
| `metrics2_compare` | `cockpit2.py:3956` |
| `metrics2_formula` | `cockpit2.py:4019` |
| `source_activate` | `cockpit2.py:4002` |
| `source_deactivate` | `cockpit2.py:4011` |
| `link_pursue` | `cockpit2.py:3983` |
| `link_ignore` | `cockpit2.py:3993` |
| `acc_check` | `cockpit2.py:3964` |
| `ai_reply` | `cockpit2.py:2127` |
| `proj_feed` | `cockpit2.py:2138` |
| `checklist_add` | `cockpit2.py:2185` |
| `checklist_remove` | `cockpit2.py:2225` |
| `plan_akkoord` | `cockpit2.py:2208` |
| `checklist_uitvoer` | `cockpit2.py:2196` |
| `check_add` | `cockpit2.py:2275` |
| `check_accept` | `cockpit2.py:2292` |
| `check_toggle` | `cockpit2.py:2302` |
| `check_skip` | `cockpit2.py:2324` |
| `check_unskip` | `cockpit2.py:2336` |
| `check_handoff` | `cockpit2.py:2357` |
| `check_remove` | `cockpit2.py:2405` |
| `check_rename` | `cockpit2.py:2415` |
| `check_move` | `cockpit2.py:2434` |
| `role_assign` | `cockpit2.py:2448` |
| `role_unassign` | `cockpit2.py:2466` |
| `role_focus` | `cockpit2.py:2485` |
| `radar_approve` | `cockpit2.py:2518` |
| `radar_dismiss` | `cockpit2.py:2528` |
| `radar_promote` | `cockpit2.py:2532` |
| `radar_merge` | `cockpit2.py:2552` |
| `radar_koppel` | `cockpit2.py:2568` |
| `kb_stage_koppel` | `cockpit2.py:2595` |
| `aitask_add` | `cockpit2.py:2633` |
| `aitask_remove` | `cockpit2.py:2664` |
| `skilllink_add` | `cockpit2.py:2692` |
| `means_gap_add` | `cockpit2.py:2722` |
| `persona_skill_add` | `cockpit2.py:2876` |
| `rov2_add` | `cockpit2.py:2891` |
| `rov2_add_to_group` | `cockpit2.py:2903` |
| `rov2_remove` | `cockpit2.py:2915` |
| `rov2_remove_group` | `cockpit2.py:2930` |
| `rov2_setkind` | `cockpit2.py:2948` |
| `rov2_consent` | `cockpit2.py:2961` |
| `rov2_end` | `cockpit2.py:2983` |
| `wo_open` | `cockpit2.py:3007` |
| `wo_close` | `cockpit2.py:3017` |
| `wo_presence` | `cockpit2.py:3033` |
| `wo_present_all` | `cockpit2.py:3044` |
| `vangst_add` | `cockpit2.py:3056` |
| `vangst_tekst` | `cockpit2.py:3104` |
| `vangst_klaar` | `cockpit2.py:3114` |
| `vangst_uitkomst` | `cockpit2.py:3163` |
| `vangst_uitkomst_weg` | `cockpit2.py:3151` |
| `vangst_uitkomst_edit` | `cockpit2.py:3126` |
| `vangst_remove` | `cockpit2.py:3095` |
| `vangst_verwerk` | `cockpit2.py:3279` |
| `wo_checkout` | `cockpit2.py:4258` |
| `noochie_send` | `cockpit2.py:4273` |
| `noochie_reset` | `cockpit2.py:4299` |
| `noochie_ctx` | `cockpit2.py:4306` |
| `cl_add` | `cockpit2.py:4313` |
| `cl_report` | `cockpit2.py:4331` |
| `cl_remove` | `cockpit2.py:4346` |
| `m_add_kpi` | `cockpit2.py:4356` |
| `m_add_from_def` | `cockpit2.py:4388` |
| `def_add` | `cockpit2.py:4403` |
| `catalog_publish` | `cockpit2.py:4425` |
| `def_amend` | `cockpit2.py:4451` |
| `m_add_link` | `cockpit2.py:4493` |
| `m_sample` | `cockpit2.py:4504` |
| `m_remove` | `cockpit2.py:4514` |
| `m_pin` | `cockpit2.py:4524` |
| `m_unpin` | `cockpit2.py:4535` |
| `tile_add` | `cockpit2.py:4573` |
| `indicator_activate` | `cockpit2.py:4545` |
| `tile_remove` | `cockpit2.py:4607` |
| `rov2_set` | `cockpit2.py:4617` |
| `rov2_acc_add` | `cockpit2.py:4617` |
| `rov2_acc_remove` | `cockpit2.py:4617` |
| `rov2_dom_add` | `cockpit2.py:4617` |
| `rov2_dom_remove` | `cockpit2.py:4617` |
| `backlog_add` | `cockpit2.py:4649` |
| `backlog_update_staat` | `cockpit2.py:4661` |
| `backlog_update_prioriteit` | `cockpit2.py:4673` |
| `person_edit` | `cockpit2.py:4685` |
| `person_remove` | `cockpit2.py:4702` |
| `lk_mute` | `cockpit2.py:4723` |
| `claims_term_add` | `cockpit2.py:4826` |
| `claims_term_retract` | `cockpit2.py:4863` |
| `claims_work_status` | `cockpit2.py:4847` |
| `claims_bewijs_link` | `cockpit2.py:4892` |
| `claims_vondst_whitelist` | `cockpit2.py:4916` |
| `claims_regel_uit_vondst` | `cockpit2.py:4942` |
| `claims_to_board` | `cockpit2.py:4974` |
| `persona_edit` | `cockpit2.py:2775` |
| `persona_llm` | `cockpit2.py:2794` |
| `persona_finetune` | `cockpit2.py:2811` |
| `persona_finetune_apply` | `cockpit2.py:2829` |


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
