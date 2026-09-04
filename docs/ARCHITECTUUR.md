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
| `ff_beslis` | `cockpit2.py:5334` |
| `ff_cluster` | `cockpit2.py:5462` |
| `ff_promote` | `cockpit2.py:5392` |
| `ff_demote` | `cockpit2.py:5416` |
| `ff_run` | `cockpit2.py:5435` |
| `kb_new` | `cockpit2.py:4697` |
| `kb_intake` | `cockpit2.py:4779` |
| `kb_intake_url` | `cockpit2.py:4796` |
| `kb_stage_edit` | `cockpit2.py:4815` |
| `kb_stage_accept` | `cockpit2.py:4827` |
| `kb_stage_delete` | `cockpit2.py:4846` |
| `kb_stage_merge` | `cockpit2.py:4852` |
| `kb_stage_commit` | `cockpit2.py:4863` |
| `kb_stage_discard` | `cockpit2.py:4883` |
| `kb_atoom_subject` | `cockpit2.py:5138` |
| `kb_atoom_purge` | `cockpit2.py:5122` |
| `tag_voorstel_besluit` | `cockpit2.py:4959` |
| `tag_onderhoud_run` | `cockpit2.py:5109` |
| `copy_stack_inclusie` | `cockpit2.py:5091` |
| `verzoek_besluit` | `cockpit2.py:4978` |
| `kb_blacklist_leeg` | `cockpit2.py:5131` |
| `kb_atoom_edit` | `cockpit2.py:4889` |
| `kb_atoom_related` | `cockpit2.py:4896` |
| `kb_atoom_reference` | `cockpit2.py:4941` |
| `kb_insight_link` | `cockpit2.py:4908` |
| `kb_insight_unlink` | `cockpit2.py:4915` |
| `kb_meta_start` | `cockpit2.py:4921` |
| `kb_atoom_merge` | `cockpit2.py:5149` |
| `kb_atoom_archive` | `cockpit2.py:5170` |
| `kb_atoom_unarchive` | `cockpit2.py:5179` |
| `kb_atoom_naar_spel` | `cockpit2.py:5185` |
| `kb_spel_start` | `cockpit2.py:5206` |
| `kb_spel_add` | `cockpit2.py:5220` |
| `kb_spel_remove` | `cockpit2.py:5230` |
| `kb_spel_flip` | `cockpit2.py:5237` |
| `kb_spel_finish` | `cockpit2.py:5243` |
| `kb_link` | `cockpit2.py:4706` |
| `kb_unlink` | `cockpit2.py:4720` |
| `kb_annotate` | `cockpit2.py:4731` |
| `kb_evidence` | `cockpit2.py:4737` |
| `kb_discuss` | `cockpit2.py:4758` |
| `kb_reformulate` | `cockpit2.py:4764` |
| `kw_nominate` | `cockpit2.py:5254` |
| `kw_nom_accept` | `cockpit2.py:5265` |
| `kw_nom_reject` | `cockpit2.py:5283` |
| `ws_forbid` | `cockpit2.py:5313` |
| `ws_approve` | `cockpit2.py:5318` |
| `proj_add` | `cockpit2.py:1209` |
| `artefact_add` | `cockpit2.py:1253` |
| `artefact_edit` | `cockpit2.py:1297` |
| `artefact_archive` | `cockpit2.py:1324` |
| `pagina_feit_add` | `cockpit2.py:1344` |
| `pagina_feit_del` | `cockpit2.py:1373` |
| `pagina_voorstel` | `cockpit2.py:1404` |
| `proj_status` | `cockpit2.py:1434` |
| `proj_done` | `cockpit2.py:1452` |
| `proj_dod` | `cockpit2.py:1542` |
| `proj_archive` | `cockpit2.py:1556` |
| `proj_unarchive` | `cockpit2.py:1579` |
| `proj_delete` | `cockpit2.py:1589` |
| `proj_edit` | `cockpit2.py:1616` |
| `proj_comment` | `cockpit2.py:1629` |
| `proj_rename` | `cockpit2.py:1639` |
| `proj_describe` | `cockpit2.py:1650` |
| `proj_doc_edit` | `cockpit2.py:1720` |
| `verslag_bevestig` | `cockpit2.py:1683` |
| `verslag_bijwerken` | `cockpit2.py:1698` |
| `proj_regen_doc` | `cockpit2.py:1661` |
| `proj_settrekker` | `cockpit2.py:1733` |
| `proj_setowner` | `cockpit2.py:1770` |
| `proj_approve` | `cockpit2.py:1789` |
| `proj_discard` | `cockpit2.py:1800` |
| `proj_proposal_accept` | `cockpit2.py:1811` |
| `proj_proposal_reject` | `cockpit2.py:1824` |
| `proj_setlabel` | `cockpit2.py:1837` |
| `proj_setimpact` | `cockpit2.py:1852` |
| `proj_seteffort` | `cockpit2.py:1871` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1894` |
| `proj_setprivate` | `cockpit2.py:1918` |
| `proj_setdue` | `cockpit2.py:1929` |
| `attach_add` | `cockpit2.py:1940` |
| `attach_remove` | `cockpit2.py:1951` |
| `react_add` | `cockpit2.py:1961` |
| `feed_edit` | `cockpit2.py:1971` |
| `feed_remove` | `cockpit2.py:1981` |
| `wall_outcome` | `cockpit2.py:3475` |
| `notif_read` | `cockpit2.py:3571` |
| `notif_processed` | `cockpit2.py:3576` |
| `notif_outcome` | `cockpit2.py:3795` |
| `notif_klaar` | `cockpit2.py:3742` |
| `notif_delete` | `cockpit2.py:3581` |
| `notif_add` | `cockpit2.py:3693` |
| `notif_archive` | `cockpit2.py:3912` |
| `metrics2_fav` | `cockpit2.py:3587` |
| `metrics2_unfav` | `cockpit2.py:3597` |
| `metrics2_form` | `cockpit2.py:3602` |
| `metrics2_dim` | `cockpit2.py:3608` |
| `metrics2_compare` | `cockpit2.py:3615` |
| `metrics2_formula` | `cockpit2.py:3678` |
| `source_activate` | `cockpit2.py:3661` |
| `source_deactivate` | `cockpit2.py:3670` |
| `link_pursue` | `cockpit2.py:3642` |
| `link_ignore` | `cockpit2.py:3652` |
| `acc_check` | `cockpit2.py:3623` |
| `ai_reply` | `cockpit2.py:1990` |
| `proj_feed` | `cockpit2.py:2001` |
| `checklist_add` | `cockpit2.py:2048` |
| `checklist_remove` | `cockpit2.py:2059` |
| `check_add` | `cockpit2.py:2107` |
| `check_accept` | `cockpit2.py:2124` |
| `check_toggle` | `cockpit2.py:2134` |
| `check_skip` | `cockpit2.py:2156` |
| `check_unskip` | `cockpit2.py:2168` |
| `check_handoff` | `cockpit2.py:2180` |
| `check_remove` | `cockpit2.py:2194` |
| `role_assign` | `cockpit2.py:2204` |
| `role_unassign` | `cockpit2.py:2222` |
| `role_focus` | `cockpit2.py:2241` |
| `radar_approve` | `cockpit2.py:2274` |
| `radar_dismiss` | `cockpit2.py:2284` |
| `radar_promote` | `cockpit2.py:2288` |
| `radar_merge` | `cockpit2.py:2308` |
| `radar_koppel` | `cockpit2.py:2324` |
| `kb_stage_koppel` | `cockpit2.py:2351` |
| `aitask_add` | `cockpit2.py:2389` |
| `aitask_remove` | `cockpit2.py:2420` |
| `skilllink_add` | `cockpit2.py:2448` |
| `means_gap_add` | `cockpit2.py:2478` |
| `persona_skill_add` | `cockpit2.py:2632` |
| `rov2_add` | `cockpit2.py:2647` |
| `rov2_add_to_group` | `cockpit2.py:2659` |
| `rov2_remove` | `cockpit2.py:2671` |
| `rov2_remove_group` | `cockpit2.py:2686` |
| `rov2_setkind` | `cockpit2.py:2704` |
| `rov2_consent` | `cockpit2.py:2717` |
| `rov2_end` | `cockpit2.py:2739` |
| `wo_open` | `cockpit2.py:2763` |
| `wo_close` | `cockpit2.py:2773` |
| `wo_presence` | `cockpit2.py:2789` |
| `wo_present_all` | `cockpit2.py:2800` |
| `vangst_add` | `cockpit2.py:2812` |
| `vangst_tekst` | `cockpit2.py:2860` |
| `vangst_klaar` | `cockpit2.py:2870` |
| `vangst_uitkomst` | `cockpit2.py:2919` |
| `vangst_uitkomst_weg` | `cockpit2.py:2907` |
| `vangst_uitkomst_edit` | `cockpit2.py:2882` |
| `vangst_remove` | `cockpit2.py:2851` |
| `vangst_verwerk` | `cockpit2.py:3035` |
| `wo_checkout` | `cockpit2.py:3917` |
| `noochie_send` | `cockpit2.py:3932` |
| `noochie_reset` | `cockpit2.py:3958` |
| `noochie_ctx` | `cockpit2.py:3965` |
| `cl_add` | `cockpit2.py:3972` |
| `cl_report` | `cockpit2.py:3990` |
| `cl_remove` | `cockpit2.py:4005` |
| `m_add_kpi` | `cockpit2.py:4015` |
| `m_add_from_def` | `cockpit2.py:4047` |
| `def_add` | `cockpit2.py:4062` |
| `catalog_publish` | `cockpit2.py:4084` |
| `def_amend` | `cockpit2.py:4110` |
| `m_add_link` | `cockpit2.py:4152` |
| `m_sample` | `cockpit2.py:4163` |
| `m_remove` | `cockpit2.py:4173` |
| `m_pin` | `cockpit2.py:4183` |
| `m_unpin` | `cockpit2.py:4194` |
| `tile_add` | `cockpit2.py:4232` |
| `indicator_activate` | `cockpit2.py:4204` |
| `tile_remove` | `cockpit2.py:4266` |
| `rov2_set` | `cockpit2.py:4276` |
| `rov2_acc_add` | `cockpit2.py:4276` |
| `rov2_acc_remove` | `cockpit2.py:4276` |
| `rov2_dom_add` | `cockpit2.py:4276` |
| `rov2_dom_remove` | `cockpit2.py:4276` |
| `backlog_add` | `cockpit2.py:4308` |
| `backlog_update_staat` | `cockpit2.py:4320` |
| `backlog_update_prioriteit` | `cockpit2.py:4332` |
| `person_edit` | `cockpit2.py:4344` |
| `person_remove` | `cockpit2.py:4361` |
| `lk_mute` | `cockpit2.py:4382` |
| `claims_term_add` | `cockpit2.py:4485` |
| `claims_term_retract` | `cockpit2.py:4522` |
| `claims_work_status` | `cockpit2.py:4506` |
| `claims_bewijs_link` | `cockpit2.py:4551` |
| `claims_vondst_whitelist` | `cockpit2.py:4575` |
| `claims_regel_uit_vondst` | `cockpit2.py:4601` |
| `claims_to_board` | `cockpit2.py:4633` |
| `persona_edit` | `cockpit2.py:2531` |
| `persona_llm` | `cockpit2.py:2550` |
| `persona_finetune` | `cockpit2.py:2567` |
| `persona_finetune_apply` | `cockpit2.py:2585` |


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
_59 routes · 190 dispatch-acties · 32 stores._
