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
| `/decision-coach` | `render_decision_coach` | `nooch_village/views/decision_coach.py` |
| `/copy-prompt` | `render_copy_prompt` | `nooch_village/views/copy_prompt.py` |
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |
| `/project_pakket` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `decision_sheet_log` | `cockpit2.py:6020` |
| `ff_beslis` | `cockpit2.py:5859` |
| `ff_cluster` | `cockpit2.py:5987` |
| `ff_promote` | `cockpit2.py:5917` |
| `ff_demote` | `cockpit2.py:5941` |
| `ff_run` | `cockpit2.py:5960` |
| `kb_new` | `cockpit2.py:5209` |
| `kb_intake` | `cockpit2.py:5291` |
| `kb_intake_url` | `cockpit2.py:5308` |
| `kb_stage_edit` | `cockpit2.py:5327` |
| `kb_stage_accept` | `cockpit2.py:5339` |
| `kb_stage_delete` | `cockpit2.py:5358` |
| `kb_stage_merge` | `cockpit2.py:5364` |
| `kb_stage_commit` | `cockpit2.py:5375` |
| `kb_stage_discard` | `cockpit2.py:5395` |
| `kb_atoom_subject` | `cockpit2.py:5650` |
| `kb_atoom_purge` | `cockpit2.py:5634` |
| `tag_voorstel_besluit` | `cockpit2.py:5471` |
| `tag_onderhoud_run` | `cockpit2.py:5621` |
| `copy_stack_inclusie` | `cockpit2.py:5603` |
| `verzoek_besluit` | `cockpit2.py:5490` |
| `kb_blacklist_leeg` | `cockpit2.py:5643` |
| `kb_atoom_edit` | `cockpit2.py:5401` |
| `kb_atoom_related` | `cockpit2.py:5408` |
| `kb_atoom_reference` | `cockpit2.py:5453` |
| `kb_insight_link` | `cockpit2.py:5420` |
| `kb_insight_unlink` | `cockpit2.py:5427` |
| `kb_meta_start` | `cockpit2.py:5433` |
| `kb_atoom_merge` | `cockpit2.py:5661` |
| `kb_atoom_archive` | `cockpit2.py:5682` |
| `kb_atoom_unarchive` | `cockpit2.py:5691` |
| `kb_atoom_naar_spel` | `cockpit2.py:5697` |
| `kb_spel_start` | `cockpit2.py:5718` |
| `kb_spel_add` | `cockpit2.py:5732` |
| `kb_spel_remove` | `cockpit2.py:5742` |
| `kb_spel_flip` | `cockpit2.py:5749` |
| `kb_spel_finish` | `cockpit2.py:5755` |
| `kb_link` | `cockpit2.py:5218` |
| `kb_unlink` | `cockpit2.py:5232` |
| `kb_annotate` | `cockpit2.py:5243` |
| `kb_evidence` | `cockpit2.py:5249` |
| `kb_discuss` | `cockpit2.py:5270` |
| `kb_reformulate` | `cockpit2.py:5276` |
| `kw_nominate` | `cockpit2.py:5766` |
| `kw_nom_accept` | `cockpit2.py:5777` |
| `kw_nom_reject` | `cockpit2.py:5795` |
| `ws_forbid` | `cockpit2.py:5838` |
| `ws_approve` | `cockpit2.py:5843` |
| `proj_add` | `cockpit2.py:1256` |
| `artefact_add` | `cockpit2.py:1309` |
| `artefact_edit` | `cockpit2.py:1353` |
| `artefact_archive` | `cockpit2.py:1380` |
| `pagina_feit_add` | `cockpit2.py:1400` |
| `pagina_feit_del` | `cockpit2.py:1429` |
| `pagina_voorstel` | `cockpit2.py:1460` |
| `proj_status` | `cockpit2.py:1490` |
| `proj_done` | `cockpit2.py:1521` |
| `proj_dod` | `cockpit2.py:1616` |
| `proj_archive` | `cockpit2.py:1653` |
| `proj_unarchive` | `cockpit2.py:1661` |
| `proj_delete` | `cockpit2.py:1697` |
| `proj_edit` | `cockpit2.py:1724` |
| `proj_comment` | `cockpit2.py:1737` |
| `proj_rename` | `cockpit2.py:1748` |
| `proj_describe` | `cockpit2.py:1759` |
| `proj_doc_edit` | `cockpit2.py:1897` |
| `verslag_bevestig_behaald` | `cockpit2.py:1837` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1843` |
| `verslag_overslaan` | `cockpit2.py:1848` |
| `verslag_bijwerken` | `cockpit2.py:1875` |
| `proj_regen_doc` | `cockpit2.py:1770` |
| `proj_settrekker` | `cockpit2.py:1910` |
| `proj_setowner` | `cockpit2.py:1951` |
| `proj_approve` | `cockpit2.py:1970` |
| `proj_discard` | `cockpit2.py:1981` |
| `proj_proposal_accept` | `cockpit2.py:1992` |
| `proj_proposal_reject` | `cockpit2.py:2005` |
| `proj_setlabel` | `cockpit2.py:2018` |
| `proj_setimpact` | `cockpit2.py:2033` |
| `proj_seteffort` | `cockpit2.py:2063` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2081` |
| `proj_setprivate` | `cockpit2.py:2105` |
| `proj_setdue` | `cockpit2.py:2116` |
| `proj_goal` | `cockpit2.py:2127` |
| `proj_depends` | `cockpit2.py:2142` |
| `goal_add` | `cockpit2.py:2159` |
| `goal_edit` | `cockpit2.py:2173` |
| `goal_link` | `cockpit2.py:2187` |
| `attach_add` | `cockpit2.py:2204` |
| `attach_remove` | `cockpit2.py:2215` |
| `react_add` | `cockpit2.py:2225` |
| `feed_edit` | `cockpit2.py:2236` |
| `feed_remove` | `cockpit2.py:2247` |
| `wall_outcome` | `cockpit2.py:3875` |
| `notif_read` | `cockpit2.py:3971` |
| `notif_processed` | `cockpit2.py:3981` |
| `notif_outcome` | `cockpit2.py:4304` |
| `notif_klaar` | `cockpit2.py:4245` |
| `goedkeur` | `cockpit2.py:3990` |
| `notif_delete` | `cockpit2.py:4035` |
| `notif_add` | `cockpit2.py:4193` |
| `notif_archive` | `cockpit2.py:4426` |
| `metrics2_fav` | `cockpit2.py:4046` |
| `metrics2_unfav` | `cockpit2.py:4061` |
| `metrics2_form` | `cockpit2.py:4066` |
| `metrics2_dim` | `cockpit2.py:4073` |
| `metrics2_compare` | `cockpit2.py:4081` |
| `metrics2_formula` | `cockpit2.py:4178` |
| `source_activate` | `cockpit2.py:4154` |
| `source_deactivate` | `cockpit2.py:4166` |
| `link_pursue` | `cockpit2.py:4128` |
| `link_ignore` | `cockpit2.py:4139` |
| `acc_check` | `cockpit2.py:4090` |
| `ai_reply` | `cockpit2.py:2257` |
| `proj_feed` | `cockpit2.py:2269` |
| `checklist_add` | `cockpit2.py:2317` |
| `checklist_remove` | `cockpit2.py:2357` |
| `plan_akkoord` | `cockpit2.py:2340` |
| `checklist_uitvoer` | `cockpit2.py:2328` |
| `check_add` | `cockpit2.py:2407` |
| `check_accept` | `cockpit2.py:2424` |
| `check_toggle` | `cockpit2.py:2434` |
| `check_skip` | `cockpit2.py:2456` |
| `check_unskip` | `cockpit2.py:2468` |
| `check_handoff` | `cockpit2.py:2489` |
| `check_remove` | `cockpit2.py:2537` |
| `check_rename` | `cockpit2.py:2547` |
| `check_move` | `cockpit2.py:2566` |
| `role_assign` | `cockpit2.py:2580` |
| `role_unassign` | `cockpit2.py:2605` |
| `role_focus` | `cockpit2.py:2627` |
| `radar_approve` | `cockpit2.py:2660` |
| `radar_dismiss` | `cockpit2.py:2670` |
| `radar_promote` | `cockpit2.py:2674` |
| `radar_merge` | `cockpit2.py:2694` |
| `radar_koppel` | `cockpit2.py:2710` |
| `kb_stage_koppel` | `cockpit2.py:2737` |
| `middel_remove` | `cockpit2.py:2785` |
| `skilllink_add` | `cockpit2.py:2816` |
| `means_gap_add` | `cockpit2.py:2846` |
| `rov2_add` | `cockpit2.py:3000` |
| `rov2_add_to_group` | `cockpit2.py:3012` |
| `rov2_remove` | `cockpit2.py:3024` |
| `rov2_remove_group` | `cockpit2.py:3039` |
| `rov2_setkind` | `cockpit2.py:3057` |
| `rov2_consent` | `cockpit2.py:3070` |
| `rov2_end` | `cockpit2.py:3092` |
| `wo_open` | `cockpit2.py:3116` |
| `wo_close` | `cockpit2.py:3126` |
| `wo_presence` | `cockpit2.py:3142` |
| `wo_present_all` | `cockpit2.py:3153` |
| `vangst_add` | `cockpit2.py:3165` |
| `vangst_tekst` | `cockpit2.py:3213` |
| `vangst_klaar` | `cockpit2.py:3223` |
| `vangst_uitkomst` | `cockpit2.py:3272` |
| `vangst_uitkomst_weg` | `cockpit2.py:3260` |
| `vangst_uitkomst_edit` | `cockpit2.py:3235` |
| `vangst_remove` | `cockpit2.py:3204` |
| `vangst_verwerk` | `cockpit2.py:3388` |
| `wo_checkout` | `cockpit2.py:4435` |
| `noochie_send` | `cockpit2.py:4450` |
| `noochie_reset` | `cockpit2.py:4477` |
| `noochie_ctx` | `cockpit2.py:4485` |
| `cl_add` | `cockpit2.py:4493` |
| `cl_report` | `cockpit2.py:4511` |
| `cl_remove` | `cockpit2.py:4526` |
| `m_add_kpi` | `cockpit2.py:4536` |
| `m_add_from_def` | `cockpit2.py:4568` |
| `def_add` | `cockpit2.py:4583` |
| `catalog_publish` | `cockpit2.py:4605` |
| `def_amend` | `cockpit2.py:4631` |
| `m_add_link` | `cockpit2.py:4673` |
| `m_sample` | `cockpit2.py:4684` |
| `m_remove` | `cockpit2.py:4694` |
| `m_pin` | `cockpit2.py:4704` |
| `m_unpin` | `cockpit2.py:4715` |
| `tile_add` | `cockpit2.py:4753` |
| `indicator_activate` | `cockpit2.py:4725` |
| `tile_remove` | `cockpit2.py:4787` |
| `rov2_set` | `cockpit2.py:4797` |
| `rov2_acc_add` | `cockpit2.py:4797` |
| `rov2_acc_remove` | `cockpit2.py:4797` |
| `rov2_dom_add` | `cockpit2.py:4797` |
| `rov2_dom_remove` | `cockpit2.py:4797` |
| `person_edit` | `cockpit2.py:4829` |
| `person_remove` | `cockpit2.py:4846` |
| `lk_mute` | `cockpit2.py:4867` |
| `claims_term_add` | `cockpit2.py:4997` |
| `claims_term_retract` | `cockpit2.py:5034` |
| `claims_work_status` | `cockpit2.py:5018` |
| `claims_bewijs_link` | `cockpit2.py:5063` |
| `claims_vondst_whitelist` | `cockpit2.py:5087` |
| `claims_regel_uit_vondst` | `cockpit2.py:5113` |
| `claims_to_board` | `cockpit2.py:5145` |
| `persona_edit` | `cockpit2.py:2899` |
| `persona_llm` | `cockpit2.py:2918` |
| `persona_finetune` | `cockpit2.py:2935` |
| `persona_finetune_apply` | `cockpit2.py:2953` |


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
_63 routes · 198 dispatch-acties · 31 stores._
