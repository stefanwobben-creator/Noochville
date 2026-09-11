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
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/middelen` | `render_middelen` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/goals` | `render_goals` | `nooch_village/views/doelen.py` |
| `/goal` | `render_goal` | `nooch_village/views/doelen.py` |
| `/site-audit` | `render_site_audit` | `nooch_village/views/site_audit.py` |
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
| `ff_beslis` | `cockpit2.py:5822` |
| `ff_cluster` | `cockpit2.py:5950` |
| `ff_promote` | `cockpit2.py:5880` |
| `ff_demote` | `cockpit2.py:5904` |
| `ff_run` | `cockpit2.py:5923` |
| `kb_new` | `cockpit2.py:5172` |
| `kb_intake` | `cockpit2.py:5254` |
| `kb_intake_url` | `cockpit2.py:5271` |
| `kb_stage_edit` | `cockpit2.py:5290` |
| `kb_stage_accept` | `cockpit2.py:5302` |
| `kb_stage_delete` | `cockpit2.py:5321` |
| `kb_stage_merge` | `cockpit2.py:5327` |
| `kb_stage_commit` | `cockpit2.py:5338` |
| `kb_stage_discard` | `cockpit2.py:5358` |
| `kb_atoom_subject` | `cockpit2.py:5613` |
| `kb_atoom_purge` | `cockpit2.py:5597` |
| `tag_voorstel_besluit` | `cockpit2.py:5434` |
| `tag_onderhoud_run` | `cockpit2.py:5584` |
| `copy_stack_inclusie` | `cockpit2.py:5566` |
| `verzoek_besluit` | `cockpit2.py:5453` |
| `kb_blacklist_leeg` | `cockpit2.py:5606` |
| `kb_atoom_edit` | `cockpit2.py:5364` |
| `kb_atoom_related` | `cockpit2.py:5371` |
| `kb_atoom_reference` | `cockpit2.py:5416` |
| `kb_insight_link` | `cockpit2.py:5383` |
| `kb_insight_unlink` | `cockpit2.py:5390` |
| `kb_meta_start` | `cockpit2.py:5396` |
| `kb_atoom_merge` | `cockpit2.py:5624` |
| `kb_atoom_archive` | `cockpit2.py:5645` |
| `kb_atoom_unarchive` | `cockpit2.py:5654` |
| `kb_atoom_naar_spel` | `cockpit2.py:5660` |
| `kb_spel_start` | `cockpit2.py:5681` |
| `kb_spel_add` | `cockpit2.py:5695` |
| `kb_spel_remove` | `cockpit2.py:5705` |
| `kb_spel_flip` | `cockpit2.py:5712` |
| `kb_spel_finish` | `cockpit2.py:5718` |
| `kb_link` | `cockpit2.py:5181` |
| `kb_unlink` | `cockpit2.py:5195` |
| `kb_annotate` | `cockpit2.py:5206` |
| `kb_evidence` | `cockpit2.py:5212` |
| `kb_discuss` | `cockpit2.py:5233` |
| `kb_reformulate` | `cockpit2.py:5239` |
| `kw_nominate` | `cockpit2.py:5729` |
| `kw_nom_accept` | `cockpit2.py:5740` |
| `kw_nom_reject` | `cockpit2.py:5758` |
| `ws_forbid` | `cockpit2.py:5801` |
| `ws_approve` | `cockpit2.py:5806` |
| `proj_add` | `cockpit2.py:1247` |
| `artefact_add` | `cockpit2.py:1300` |
| `artefact_edit` | `cockpit2.py:1344` |
| `artefact_archive` | `cockpit2.py:1371` |
| `pagina_feit_add` | `cockpit2.py:1391` |
| `pagina_feit_del` | `cockpit2.py:1420` |
| `pagina_voorstel` | `cockpit2.py:1451` |
| `proj_status` | `cockpit2.py:1481` |
| `proj_done` | `cockpit2.py:1510` |
| `proj_dod` | `cockpit2.py:1604` |
| `proj_archive` | `cockpit2.py:1618` |
| `proj_unarchive` | `cockpit2.py:1641` |
| `proj_delete` | `cockpit2.py:1677` |
| `proj_edit` | `cockpit2.py:1704` |
| `proj_comment` | `cockpit2.py:1717` |
| `proj_rename` | `cockpit2.py:1728` |
| `proj_describe` | `cockpit2.py:1739` |
| `proj_doc_edit` | `cockpit2.py:1873` |
| `verslag_bevestig_behaald` | `cockpit2.py:1814` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1820` |
| `verslag_overslaan` | `cockpit2.py:1825` |
| `verslag_bijwerken` | `cockpit2.py:1851` |
| `proj_regen_doc` | `cockpit2.py:1750` |
| `proj_settrekker` | `cockpit2.py:1886` |
| `proj_setowner` | `cockpit2.py:1927` |
| `proj_approve` | `cockpit2.py:1946` |
| `proj_discard` | `cockpit2.py:1957` |
| `proj_proposal_accept` | `cockpit2.py:1968` |
| `proj_proposal_reject` | `cockpit2.py:1981` |
| `proj_setlabel` | `cockpit2.py:1994` |
| `proj_setimpact` | `cockpit2.py:2009` |
| `proj_seteffort` | `cockpit2.py:2028` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2051` |
| `proj_setprivate` | `cockpit2.py:2075` |
| `proj_setdue` | `cockpit2.py:2086` |
| `proj_goal` | `cockpit2.py:2097` |
| `proj_depends` | `cockpit2.py:2112` |
| `goal_add` | `cockpit2.py:2129` |
| `goal_edit` | `cockpit2.py:2143` |
| `goal_link` | `cockpit2.py:2157` |
| `attach_add` | `cockpit2.py:2174` |
| `attach_remove` | `cockpit2.py:2185` |
| `react_add` | `cockpit2.py:2195` |
| `feed_edit` | `cockpit2.py:2206` |
| `feed_remove` | `cockpit2.py:2217` |
| `wall_outcome` | `cockpit2.py:3845` |
| `notif_read` | `cockpit2.py:3941` |
| `notif_processed` | `cockpit2.py:3951` |
| `notif_outcome` | `cockpit2.py:4267` |
| `notif_klaar` | `cockpit2.py:4208` |
| `goedkeur` | `cockpit2.py:3960` |
| `notif_delete` | `cockpit2.py:4005` |
| `notif_add` | `cockpit2.py:4156` |
| `notif_archive` | `cockpit2.py:4389` |
| `metrics2_fav` | `cockpit2.py:4016` |
| `metrics2_unfav` | `cockpit2.py:4031` |
| `metrics2_form` | `cockpit2.py:4036` |
| `metrics2_dim` | `cockpit2.py:4043` |
| `metrics2_compare` | `cockpit2.py:4051` |
| `metrics2_formula` | `cockpit2.py:4141` |
| `source_activate` | `cockpit2.py:4117` |
| `source_deactivate` | `cockpit2.py:4129` |
| `link_pursue` | `cockpit2.py:4091` |
| `link_ignore` | `cockpit2.py:4102` |
| `acc_check` | `cockpit2.py:4060` |
| `ai_reply` | `cockpit2.py:2227` |
| `proj_feed` | `cockpit2.py:2239` |
| `checklist_add` | `cockpit2.py:2287` |
| `checklist_remove` | `cockpit2.py:2327` |
| `plan_akkoord` | `cockpit2.py:2310` |
| `checklist_uitvoer` | `cockpit2.py:2298` |
| `check_add` | `cockpit2.py:2377` |
| `check_accept` | `cockpit2.py:2394` |
| `check_toggle` | `cockpit2.py:2404` |
| `check_skip` | `cockpit2.py:2426` |
| `check_unskip` | `cockpit2.py:2438` |
| `check_handoff` | `cockpit2.py:2459` |
| `check_remove` | `cockpit2.py:2507` |
| `check_rename` | `cockpit2.py:2517` |
| `check_move` | `cockpit2.py:2536` |
| `role_assign` | `cockpit2.py:2550` |
| `role_unassign` | `cockpit2.py:2575` |
| `role_focus` | `cockpit2.py:2597` |
| `radar_approve` | `cockpit2.py:2630` |
| `radar_dismiss` | `cockpit2.py:2640` |
| `radar_promote` | `cockpit2.py:2644` |
| `radar_merge` | `cockpit2.py:2664` |
| `radar_koppel` | `cockpit2.py:2680` |
| `kb_stage_koppel` | `cockpit2.py:2707` |
| `middel_remove` | `cockpit2.py:2755` |
| `skilllink_add` | `cockpit2.py:2786` |
| `means_gap_add` | `cockpit2.py:2816` |
| `rov2_add` | `cockpit2.py:2970` |
| `rov2_add_to_group` | `cockpit2.py:2982` |
| `rov2_remove` | `cockpit2.py:2994` |
| `rov2_remove_group` | `cockpit2.py:3009` |
| `rov2_setkind` | `cockpit2.py:3027` |
| `rov2_consent` | `cockpit2.py:3040` |
| `rov2_end` | `cockpit2.py:3062` |
| `wo_open` | `cockpit2.py:3086` |
| `wo_close` | `cockpit2.py:3096` |
| `wo_presence` | `cockpit2.py:3112` |
| `wo_present_all` | `cockpit2.py:3123` |
| `vangst_add` | `cockpit2.py:3135` |
| `vangst_tekst` | `cockpit2.py:3183` |
| `vangst_klaar` | `cockpit2.py:3193` |
| `vangst_uitkomst` | `cockpit2.py:3242` |
| `vangst_uitkomst_weg` | `cockpit2.py:3230` |
| `vangst_uitkomst_edit` | `cockpit2.py:3205` |
| `vangst_remove` | `cockpit2.py:3174` |
| `vangst_verwerk` | `cockpit2.py:3358` |
| `wo_checkout` | `cockpit2.py:4398` |
| `noochie_send` | `cockpit2.py:4413` |
| `noochie_reset` | `cockpit2.py:4440` |
| `noochie_ctx` | `cockpit2.py:4448` |
| `cl_add` | `cockpit2.py:4456` |
| `cl_report` | `cockpit2.py:4474` |
| `cl_remove` | `cockpit2.py:4489` |
| `m_add_kpi` | `cockpit2.py:4499` |
| `m_add_from_def` | `cockpit2.py:4531` |
| `def_add` | `cockpit2.py:4546` |
| `catalog_publish` | `cockpit2.py:4568` |
| `def_amend` | `cockpit2.py:4594` |
| `m_add_link` | `cockpit2.py:4636` |
| `m_sample` | `cockpit2.py:4647` |
| `m_remove` | `cockpit2.py:4657` |
| `m_pin` | `cockpit2.py:4667` |
| `m_unpin` | `cockpit2.py:4678` |
| `tile_add` | `cockpit2.py:4716` |
| `indicator_activate` | `cockpit2.py:4688` |
| `tile_remove` | `cockpit2.py:4750` |
| `rov2_set` | `cockpit2.py:4760` |
| `rov2_acc_add` | `cockpit2.py:4760` |
| `rov2_acc_remove` | `cockpit2.py:4760` |
| `rov2_dom_add` | `cockpit2.py:4760` |
| `rov2_dom_remove` | `cockpit2.py:4760` |
| `person_edit` | `cockpit2.py:4792` |
| `person_remove` | `cockpit2.py:4809` |
| `lk_mute` | `cockpit2.py:4830` |
| `claims_term_add` | `cockpit2.py:4960` |
| `claims_term_retract` | `cockpit2.py:4997` |
| `claims_work_status` | `cockpit2.py:4981` |
| `claims_bewijs_link` | `cockpit2.py:5026` |
| `claims_vondst_whitelist` | `cockpit2.py:5050` |
| `claims_regel_uit_vondst` | `cockpit2.py:5076` |
| `claims_to_board` | `cockpit2.py:5108` |
| `persona_edit` | `cockpit2.py:2869` |
| `persona_llm` | `cockpit2.py:2888` |
| `persona_finetune` | `cockpit2.py:2905` |
| `persona_finetune_apply` | `cockpit2.py:2923` |


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
| `notif` | `NotifStore` | `notifications.json` |
| `agenda` | `Agenda` | `roloverleg_agenda.json` |
| `noochie` | `NoochieStore` | `noochie.json` |
| `checklists` | `ChecklistStore` | `checklists.json` |
| `metrics` | `MetricStore` | `metrics.json` |
| `defs` | `DefinitionStore` | `definitions.json` |
| `werk` | `WerkoverlegStore` | `werkoverleg.json` |
| `strategies` | `StrategyStore` | `strategies.json` |
| `doelen` | `DoelStore` | `doelen.json` |
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
_61 routes · 197 dispatch-acties · 31 stores._
