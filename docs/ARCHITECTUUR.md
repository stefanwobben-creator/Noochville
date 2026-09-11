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
| `ff_beslis` | `cockpit2.py:5742` |
| `ff_cluster` | `cockpit2.py:5870` |
| `ff_promote` | `cockpit2.py:5800` |
| `ff_demote` | `cockpit2.py:5824` |
| `ff_run` | `cockpit2.py:5843` |
| `kb_new` | `cockpit2.py:5092` |
| `kb_intake` | `cockpit2.py:5174` |
| `kb_intake_url` | `cockpit2.py:5191` |
| `kb_stage_edit` | `cockpit2.py:5210` |
| `kb_stage_accept` | `cockpit2.py:5222` |
| `kb_stage_delete` | `cockpit2.py:5241` |
| `kb_stage_merge` | `cockpit2.py:5247` |
| `kb_stage_commit` | `cockpit2.py:5258` |
| `kb_stage_discard` | `cockpit2.py:5278` |
| `kb_atoom_subject` | `cockpit2.py:5533` |
| `kb_atoom_purge` | `cockpit2.py:5517` |
| `tag_voorstel_besluit` | `cockpit2.py:5354` |
| `tag_onderhoud_run` | `cockpit2.py:5504` |
| `copy_stack_inclusie` | `cockpit2.py:5486` |
| `verzoek_besluit` | `cockpit2.py:5373` |
| `kb_blacklist_leeg` | `cockpit2.py:5526` |
| `kb_atoom_edit` | `cockpit2.py:5284` |
| `kb_atoom_related` | `cockpit2.py:5291` |
| `kb_atoom_reference` | `cockpit2.py:5336` |
| `kb_insight_link` | `cockpit2.py:5303` |
| `kb_insight_unlink` | `cockpit2.py:5310` |
| `kb_meta_start` | `cockpit2.py:5316` |
| `kb_atoom_merge` | `cockpit2.py:5544` |
| `kb_atoom_archive` | `cockpit2.py:5565` |
| `kb_atoom_unarchive` | `cockpit2.py:5574` |
| `kb_atoom_naar_spel` | `cockpit2.py:5580` |
| `kb_spel_start` | `cockpit2.py:5601` |
| `kb_spel_add` | `cockpit2.py:5615` |
| `kb_spel_remove` | `cockpit2.py:5625` |
| `kb_spel_flip` | `cockpit2.py:5632` |
| `kb_spel_finish` | `cockpit2.py:5638` |
| `kb_link` | `cockpit2.py:5101` |
| `kb_unlink` | `cockpit2.py:5115` |
| `kb_annotate` | `cockpit2.py:5126` |
| `kb_evidence` | `cockpit2.py:5132` |
| `kb_discuss` | `cockpit2.py:5153` |
| `kb_reformulate` | `cockpit2.py:5159` |
| `kw_nominate` | `cockpit2.py:5649` |
| `kw_nom_accept` | `cockpit2.py:5660` |
| `kw_nom_reject` | `cockpit2.py:5678` |
| `ws_forbid` | `cockpit2.py:5721` |
| `ws_approve` | `cockpit2.py:5726` |
| `proj_add` | `cockpit2.py:1244` |
| `artefact_add` | `cockpit2.py:1297` |
| `artefact_edit` | `cockpit2.py:1341` |
| `artefact_archive` | `cockpit2.py:1368` |
| `pagina_feit_add` | `cockpit2.py:1388` |
| `pagina_feit_del` | `cockpit2.py:1417` |
| `pagina_voorstel` | `cockpit2.py:1448` |
| `proj_status` | `cockpit2.py:1478` |
| `proj_done` | `cockpit2.py:1507` |
| `proj_dod` | `cockpit2.py:1601` |
| `proj_archive` | `cockpit2.py:1615` |
| `proj_unarchive` | `cockpit2.py:1638` |
| `proj_delete` | `cockpit2.py:1674` |
| `proj_edit` | `cockpit2.py:1701` |
| `proj_comment` | `cockpit2.py:1714` |
| `proj_rename` | `cockpit2.py:1725` |
| `proj_describe` | `cockpit2.py:1736` |
| `proj_doc_edit` | `cockpit2.py:1870` |
| `verslag_bevestig_behaald` | `cockpit2.py:1811` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1817` |
| `verslag_overslaan` | `cockpit2.py:1822` |
| `verslag_bijwerken` | `cockpit2.py:1848` |
| `proj_regen_doc` | `cockpit2.py:1747` |
| `proj_settrekker` | `cockpit2.py:1883` |
| `proj_setowner` | `cockpit2.py:1924` |
| `proj_approve` | `cockpit2.py:1943` |
| `proj_discard` | `cockpit2.py:1954` |
| `proj_proposal_accept` | `cockpit2.py:1965` |
| `proj_proposal_reject` | `cockpit2.py:1978` |
| `proj_setlabel` | `cockpit2.py:1991` |
| `proj_setimpact` | `cockpit2.py:2006` |
| `proj_seteffort` | `cockpit2.py:2025` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2048` |
| `proj_setprivate` | `cockpit2.py:2072` |
| `proj_setdue` | `cockpit2.py:2083` |
| `attach_add` | `cockpit2.py:2094` |
| `attach_remove` | `cockpit2.py:2105` |
| `react_add` | `cockpit2.py:2115` |
| `feed_edit` | `cockpit2.py:2126` |
| `feed_remove` | `cockpit2.py:2137` |
| `wall_outcome` | `cockpit2.py:3765` |
| `notif_read` | `cockpit2.py:3861` |
| `notif_processed` | `cockpit2.py:3871` |
| `notif_outcome` | `cockpit2.py:4187` |
| `notif_klaar` | `cockpit2.py:4128` |
| `goedkeur` | `cockpit2.py:3880` |
| `notif_delete` | `cockpit2.py:3925` |
| `notif_add` | `cockpit2.py:4076` |
| `notif_archive` | `cockpit2.py:4309` |
| `metrics2_fav` | `cockpit2.py:3936` |
| `metrics2_unfav` | `cockpit2.py:3951` |
| `metrics2_form` | `cockpit2.py:3956` |
| `metrics2_dim` | `cockpit2.py:3963` |
| `metrics2_compare` | `cockpit2.py:3971` |
| `metrics2_formula` | `cockpit2.py:4061` |
| `source_activate` | `cockpit2.py:4037` |
| `source_deactivate` | `cockpit2.py:4049` |
| `link_pursue` | `cockpit2.py:4011` |
| `link_ignore` | `cockpit2.py:4022` |
| `acc_check` | `cockpit2.py:3980` |
| `ai_reply` | `cockpit2.py:2147` |
| `proj_feed` | `cockpit2.py:2159` |
| `checklist_add` | `cockpit2.py:2207` |
| `checklist_remove` | `cockpit2.py:2247` |
| `plan_akkoord` | `cockpit2.py:2230` |
| `checklist_uitvoer` | `cockpit2.py:2218` |
| `check_add` | `cockpit2.py:2297` |
| `check_accept` | `cockpit2.py:2314` |
| `check_toggle` | `cockpit2.py:2324` |
| `check_skip` | `cockpit2.py:2346` |
| `check_unskip` | `cockpit2.py:2358` |
| `check_handoff` | `cockpit2.py:2379` |
| `check_remove` | `cockpit2.py:2427` |
| `check_rename` | `cockpit2.py:2437` |
| `check_move` | `cockpit2.py:2456` |
| `role_assign` | `cockpit2.py:2470` |
| `role_unassign` | `cockpit2.py:2495` |
| `role_focus` | `cockpit2.py:2517` |
| `radar_approve` | `cockpit2.py:2550` |
| `radar_dismiss` | `cockpit2.py:2560` |
| `radar_promote` | `cockpit2.py:2564` |
| `radar_merge` | `cockpit2.py:2584` |
| `radar_koppel` | `cockpit2.py:2600` |
| `kb_stage_koppel` | `cockpit2.py:2627` |
| `middel_remove` | `cockpit2.py:2675` |
| `skilllink_add` | `cockpit2.py:2706` |
| `means_gap_add` | `cockpit2.py:2736` |
| `rov2_add` | `cockpit2.py:2890` |
| `rov2_add_to_group` | `cockpit2.py:2902` |
| `rov2_remove` | `cockpit2.py:2914` |
| `rov2_remove_group` | `cockpit2.py:2929` |
| `rov2_setkind` | `cockpit2.py:2947` |
| `rov2_consent` | `cockpit2.py:2960` |
| `rov2_end` | `cockpit2.py:2982` |
| `wo_open` | `cockpit2.py:3006` |
| `wo_close` | `cockpit2.py:3016` |
| `wo_presence` | `cockpit2.py:3032` |
| `wo_present_all` | `cockpit2.py:3043` |
| `vangst_add` | `cockpit2.py:3055` |
| `vangst_tekst` | `cockpit2.py:3103` |
| `vangst_klaar` | `cockpit2.py:3113` |
| `vangst_uitkomst` | `cockpit2.py:3162` |
| `vangst_uitkomst_weg` | `cockpit2.py:3150` |
| `vangst_uitkomst_edit` | `cockpit2.py:3125` |
| `vangst_remove` | `cockpit2.py:3094` |
| `vangst_verwerk` | `cockpit2.py:3278` |
| `wo_checkout` | `cockpit2.py:4318` |
| `noochie_send` | `cockpit2.py:4333` |
| `noochie_reset` | `cockpit2.py:4360` |
| `noochie_ctx` | `cockpit2.py:4368` |
| `cl_add` | `cockpit2.py:4376` |
| `cl_report` | `cockpit2.py:4394` |
| `cl_remove` | `cockpit2.py:4409` |
| `m_add_kpi` | `cockpit2.py:4419` |
| `m_add_from_def` | `cockpit2.py:4451` |
| `def_add` | `cockpit2.py:4466` |
| `catalog_publish` | `cockpit2.py:4488` |
| `def_amend` | `cockpit2.py:4514` |
| `m_add_link` | `cockpit2.py:4556` |
| `m_sample` | `cockpit2.py:4567` |
| `m_remove` | `cockpit2.py:4577` |
| `m_pin` | `cockpit2.py:4587` |
| `m_unpin` | `cockpit2.py:4598` |
| `tile_add` | `cockpit2.py:4636` |
| `indicator_activate` | `cockpit2.py:4608` |
| `tile_remove` | `cockpit2.py:4670` |
| `rov2_set` | `cockpit2.py:4680` |
| `rov2_acc_add` | `cockpit2.py:4680` |
| `rov2_acc_remove` | `cockpit2.py:4680` |
| `rov2_dom_add` | `cockpit2.py:4680` |
| `rov2_dom_remove` | `cockpit2.py:4680` |
| `person_edit` | `cockpit2.py:4712` |
| `person_remove` | `cockpit2.py:4729` |
| `lk_mute` | `cockpit2.py:4750` |
| `claims_term_add` | `cockpit2.py:4880` |
| `claims_term_retract` | `cockpit2.py:4917` |
| `claims_work_status` | `cockpit2.py:4901` |
| `claims_bewijs_link` | `cockpit2.py:4946` |
| `claims_vondst_whitelist` | `cockpit2.py:4970` |
| `claims_regel_uit_vondst` | `cockpit2.py:4996` |
| `claims_to_board` | `cockpit2.py:5028` |
| `persona_edit` | `cockpit2.py:2789` |
| `persona_llm` | `cockpit2.py:2808` |
| `persona_finetune` | `cockpit2.py:2825` |
| `persona_finetune_apply` | `cockpit2.py:2843` |


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
_59 routes · 192 dispatch-acties · 30 stores._
