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
| `ff_beslis` | `cockpit2.py:5805` |
| `ff_cluster` | `cockpit2.py:5933` |
| `ff_promote` | `cockpit2.py:5863` |
| `ff_demote` | `cockpit2.py:5887` |
| `ff_run` | `cockpit2.py:5906` |
| `kb_new` | `cockpit2.py:5155` |
| `kb_intake` | `cockpit2.py:5237` |
| `kb_intake_url` | `cockpit2.py:5254` |
| `kb_stage_edit` | `cockpit2.py:5273` |
| `kb_stage_accept` | `cockpit2.py:5285` |
| `kb_stage_delete` | `cockpit2.py:5304` |
| `kb_stage_merge` | `cockpit2.py:5310` |
| `kb_stage_commit` | `cockpit2.py:5321` |
| `kb_stage_discard` | `cockpit2.py:5341` |
| `kb_atoom_subject` | `cockpit2.py:5596` |
| `kb_atoom_purge` | `cockpit2.py:5580` |
| `tag_voorstel_besluit` | `cockpit2.py:5417` |
| `tag_onderhoud_run` | `cockpit2.py:5567` |
| `copy_stack_inclusie` | `cockpit2.py:5549` |
| `verzoek_besluit` | `cockpit2.py:5436` |
| `kb_blacklist_leeg` | `cockpit2.py:5589` |
| `kb_atoom_edit` | `cockpit2.py:5347` |
| `kb_atoom_related` | `cockpit2.py:5354` |
| `kb_atoom_reference` | `cockpit2.py:5399` |
| `kb_insight_link` | `cockpit2.py:5366` |
| `kb_insight_unlink` | `cockpit2.py:5373` |
| `kb_meta_start` | `cockpit2.py:5379` |
| `kb_atoom_merge` | `cockpit2.py:5607` |
| `kb_atoom_archive` | `cockpit2.py:5628` |
| `kb_atoom_unarchive` | `cockpit2.py:5637` |
| `kb_atoom_naar_spel` | `cockpit2.py:5643` |
| `kb_spel_start` | `cockpit2.py:5664` |
| `kb_spel_add` | `cockpit2.py:5678` |
| `kb_spel_remove` | `cockpit2.py:5688` |
| `kb_spel_flip` | `cockpit2.py:5695` |
| `kb_spel_finish` | `cockpit2.py:5701` |
| `kb_link` | `cockpit2.py:5164` |
| `kb_unlink` | `cockpit2.py:5178` |
| `kb_annotate` | `cockpit2.py:5189` |
| `kb_evidence` | `cockpit2.py:5195` |
| `kb_discuss` | `cockpit2.py:5216` |
| `kb_reformulate` | `cockpit2.py:5222` |
| `kw_nominate` | `cockpit2.py:5712` |
| `kw_nom_accept` | `cockpit2.py:5723` |
| `kw_nom_reject` | `cockpit2.py:5741` |
| `ws_forbid` | `cockpit2.py:5784` |
| `ws_approve` | `cockpit2.py:5789` |
| `proj_add` | `cockpit2.py:1266` |
| `artefact_add` | `cockpit2.py:1319` |
| `artefact_edit` | `cockpit2.py:1363` |
| `artefact_archive` | `cockpit2.py:1390` |
| `pagina_feit_add` | `cockpit2.py:1410` |
| `pagina_feit_del` | `cockpit2.py:1439` |
| `pagina_voorstel` | `cockpit2.py:1470` |
| `proj_status` | `cockpit2.py:1500` |
| `proj_done` | `cockpit2.py:1529` |
| `proj_dod` | `cockpit2.py:1623` |
| `proj_archive` | `cockpit2.py:1637` |
| `proj_unarchive` | `cockpit2.py:1660` |
| `proj_delete` | `cockpit2.py:1696` |
| `proj_edit` | `cockpit2.py:1723` |
| `proj_comment` | `cockpit2.py:1736` |
| `proj_rename` | `cockpit2.py:1747` |
| `proj_describe` | `cockpit2.py:1758` |
| `proj_doc_edit` | `cockpit2.py:1892` |
| `verslag_bevestig_behaald` | `cockpit2.py:1833` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1839` |
| `verslag_overslaan` | `cockpit2.py:1844` |
| `verslag_bijwerken` | `cockpit2.py:1870` |
| `proj_regen_doc` | `cockpit2.py:1769` |
| `proj_settrekker` | `cockpit2.py:1905` |
| `proj_setowner` | `cockpit2.py:1946` |
| `proj_approve` | `cockpit2.py:1965` |
| `proj_discard` | `cockpit2.py:1976` |
| `proj_proposal_accept` | `cockpit2.py:1987` |
| `proj_proposal_reject` | `cockpit2.py:2000` |
| `proj_setlabel` | `cockpit2.py:2013` |
| `proj_setimpact` | `cockpit2.py:2028` |
| `proj_seteffort` | `cockpit2.py:2047` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2070` |
| `proj_setprivate` | `cockpit2.py:2094` |
| `proj_setdue` | `cockpit2.py:2105` |
| `attach_add` | `cockpit2.py:2116` |
| `attach_remove` | `cockpit2.py:2127` |
| `react_add` | `cockpit2.py:2137` |
| `feed_edit` | `cockpit2.py:2148` |
| `feed_remove` | `cockpit2.py:2159` |
| `wall_outcome` | `cockpit2.py:3792` |
| `notif_read` | `cockpit2.py:3888` |
| `notif_processed` | `cockpit2.py:3898` |
| `notif_outcome` | `cockpit2.py:4214` |
| `notif_klaar` | `cockpit2.py:4155` |
| `goedkeur` | `cockpit2.py:3907` |
| `notif_delete` | `cockpit2.py:3952` |
| `notif_add` | `cockpit2.py:4103` |
| `notif_archive` | `cockpit2.py:4336` |
| `metrics2_fav` | `cockpit2.py:3963` |
| `metrics2_unfav` | `cockpit2.py:3978` |
| `metrics2_form` | `cockpit2.py:3983` |
| `metrics2_dim` | `cockpit2.py:3990` |
| `metrics2_compare` | `cockpit2.py:3998` |
| `metrics2_formula` | `cockpit2.py:4088` |
| `source_activate` | `cockpit2.py:4064` |
| `source_deactivate` | `cockpit2.py:4076` |
| `link_pursue` | `cockpit2.py:4038` |
| `link_ignore` | `cockpit2.py:4049` |
| `acc_check` | `cockpit2.py:4007` |
| `ai_reply` | `cockpit2.py:2169` |
| `proj_feed` | `cockpit2.py:2181` |
| `checklist_add` | `cockpit2.py:2229` |
| `checklist_remove` | `cockpit2.py:2269` |
| `plan_akkoord` | `cockpit2.py:2252` |
| `checklist_uitvoer` | `cockpit2.py:2240` |
| `check_add` | `cockpit2.py:2319` |
| `check_accept` | `cockpit2.py:2336` |
| `check_toggle` | `cockpit2.py:2346` |
| `check_skip` | `cockpit2.py:2368` |
| `check_unskip` | `cockpit2.py:2380` |
| `check_handoff` | `cockpit2.py:2401` |
| `check_remove` | `cockpit2.py:2449` |
| `check_rename` | `cockpit2.py:2459` |
| `check_move` | `cockpit2.py:2478` |
| `role_assign` | `cockpit2.py:2492` |
| `role_unassign` | `cockpit2.py:2517` |
| `role_focus` | `cockpit2.py:2539` |
| `radar_approve` | `cockpit2.py:2572` |
| `radar_dismiss` | `cockpit2.py:2582` |
| `radar_promote` | `cockpit2.py:2586` |
| `radar_merge` | `cockpit2.py:2606` |
| `radar_koppel` | `cockpit2.py:2622` |
| `kb_stage_koppel` | `cockpit2.py:2649` |
| `middel_remove` | `cockpit2.py:2697` |
| `skilllink_add` | `cockpit2.py:2728` |
| `means_gap_add` | `cockpit2.py:2758` |
| `rov2_add` | `cockpit2.py:2912` |
| `rov2_add_to_group` | `cockpit2.py:2924` |
| `rov2_remove` | `cockpit2.py:2936` |
| `rov2_remove_group` | `cockpit2.py:2951` |
| `rov2_setkind` | `cockpit2.py:2969` |
| `rov2_consent` | `cockpit2.py:2982` |
| `rov2_end` | `cockpit2.py:3004` |
| `wo_open` | `cockpit2.py:3028` |
| `wo_close` | `cockpit2.py:3038` |
| `wo_presence` | `cockpit2.py:3054` |
| `wo_present_all` | `cockpit2.py:3065` |
| `vangst_add` | `cockpit2.py:3077` |
| `vangst_tekst` | `cockpit2.py:3125` |
| `vangst_klaar` | `cockpit2.py:3135` |
| `vangst_uitkomst` | `cockpit2.py:3184` |
| `vangst_uitkomst_weg` | `cockpit2.py:3172` |
| `vangst_uitkomst_edit` | `cockpit2.py:3147` |
| `vangst_remove` | `cockpit2.py:3116` |
| `vangst_verwerk` | `cockpit2.py:3300` |
| `wo_checkout` | `cockpit2.py:4345` |
| `noochie_send` | `cockpit2.py:4360` |
| `noochie_reset` | `cockpit2.py:4387` |
| `noochie_ctx` | `cockpit2.py:4395` |
| `cl_add` | `cockpit2.py:4403` |
| `cl_report` | `cockpit2.py:4421` |
| `cl_remove` | `cockpit2.py:4436` |
| `m_add_kpi` | `cockpit2.py:4446` |
| `m_add_from_def` | `cockpit2.py:4478` |
| `def_add` | `cockpit2.py:4493` |
| `catalog_publish` | `cockpit2.py:4515` |
| `def_amend` | `cockpit2.py:4541` |
| `m_add_link` | `cockpit2.py:4583` |
| `m_sample` | `cockpit2.py:4594` |
| `m_remove` | `cockpit2.py:4604` |
| `m_pin` | `cockpit2.py:4614` |
| `m_unpin` | `cockpit2.py:4625` |
| `tile_add` | `cockpit2.py:4663` |
| `indicator_activate` | `cockpit2.py:4635` |
| `tile_remove` | `cockpit2.py:4697` |
| `rov2_set` | `cockpit2.py:4707` |
| `rov2_acc_add` | `cockpit2.py:4707` |
| `rov2_acc_remove` | `cockpit2.py:4707` |
| `rov2_dom_add` | `cockpit2.py:4707` |
| `rov2_dom_remove` | `cockpit2.py:4707` |
| `backlog_add` | `cockpit2.py:4739` |
| `backlog_update_staat` | `cockpit2.py:4751` |
| `backlog_update_prioriteit` | `cockpit2.py:4763` |
| `person_edit` | `cockpit2.py:4775` |
| `person_remove` | `cockpit2.py:4792` |
| `lk_mute` | `cockpit2.py:4813` |
| `claims_term_add` | `cockpit2.py:4943` |
| `claims_term_retract` | `cockpit2.py:4980` |
| `claims_work_status` | `cockpit2.py:4964` |
| `claims_bewijs_link` | `cockpit2.py:5009` |
| `claims_vondst_whitelist` | `cockpit2.py:5033` |
| `claims_regel_uit_vondst` | `cockpit2.py:5059` |
| `claims_to_board` | `cockpit2.py:5091` |
| `persona_edit` | `cockpit2.py:2811` |
| `persona_llm` | `cockpit2.py:2830` |
| `persona_finetune` | `cockpit2.py:2847` |
| `persona_finetune_apply` | `cockpit2.py:2865` |


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
_60 routes · 195 dispatch-acties · 31 stores._
