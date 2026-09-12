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
| `ff_beslis` | `cockpit2.py:5830` |
| `ff_cluster` | `cockpit2.py:5958` |
| `ff_promote` | `cockpit2.py:5888` |
| `ff_demote` | `cockpit2.py:5912` |
| `ff_run` | `cockpit2.py:5931` |
| `kb_new` | `cockpit2.py:5180` |
| `kb_intake` | `cockpit2.py:5262` |
| `kb_intake_url` | `cockpit2.py:5279` |
| `kb_stage_edit` | `cockpit2.py:5298` |
| `kb_stage_accept` | `cockpit2.py:5310` |
| `kb_stage_delete` | `cockpit2.py:5329` |
| `kb_stage_merge` | `cockpit2.py:5335` |
| `kb_stage_commit` | `cockpit2.py:5346` |
| `kb_stage_discard` | `cockpit2.py:5366` |
| `kb_atoom_subject` | `cockpit2.py:5621` |
| `kb_atoom_purge` | `cockpit2.py:5605` |
| `tag_voorstel_besluit` | `cockpit2.py:5442` |
| `tag_onderhoud_run` | `cockpit2.py:5592` |
| `copy_stack_inclusie` | `cockpit2.py:5574` |
| `verzoek_besluit` | `cockpit2.py:5461` |
| `kb_blacklist_leeg` | `cockpit2.py:5614` |
| `kb_atoom_edit` | `cockpit2.py:5372` |
| `kb_atoom_related` | `cockpit2.py:5379` |
| `kb_atoom_reference` | `cockpit2.py:5424` |
| `kb_insight_link` | `cockpit2.py:5391` |
| `kb_insight_unlink` | `cockpit2.py:5398` |
| `kb_meta_start` | `cockpit2.py:5404` |
| `kb_atoom_merge` | `cockpit2.py:5632` |
| `kb_atoom_archive` | `cockpit2.py:5653` |
| `kb_atoom_unarchive` | `cockpit2.py:5662` |
| `kb_atoom_naar_spel` | `cockpit2.py:5668` |
| `kb_spel_start` | `cockpit2.py:5689` |
| `kb_spel_add` | `cockpit2.py:5703` |
| `kb_spel_remove` | `cockpit2.py:5713` |
| `kb_spel_flip` | `cockpit2.py:5720` |
| `kb_spel_finish` | `cockpit2.py:5726` |
| `kb_link` | `cockpit2.py:5189` |
| `kb_unlink` | `cockpit2.py:5203` |
| `kb_annotate` | `cockpit2.py:5214` |
| `kb_evidence` | `cockpit2.py:5220` |
| `kb_discuss` | `cockpit2.py:5241` |
| `kb_reformulate` | `cockpit2.py:5247` |
| `kw_nominate` | `cockpit2.py:5737` |
| `kw_nom_accept` | `cockpit2.py:5748` |
| `kw_nom_reject` | `cockpit2.py:5766` |
| `ws_forbid` | `cockpit2.py:5809` |
| `ws_approve` | `cockpit2.py:5814` |
| `proj_add` | `cockpit2.py:1247` |
| `artefact_add` | `cockpit2.py:1299` |
| `artefact_edit` | `cockpit2.py:1343` |
| `artefact_archive` | `cockpit2.py:1370` |
| `pagina_feit_add` | `cockpit2.py:1390` |
| `pagina_feit_del` | `cockpit2.py:1419` |
| `pagina_voorstel` | `cockpit2.py:1450` |
| `proj_status` | `cockpit2.py:1480` |
| `proj_done` | `cockpit2.py:1511` |
| `proj_dod` | `cockpit2.py:1606` |
| `proj_archive` | `cockpit2.py:1620` |
| `proj_unarchive` | `cockpit2.py:1643` |
| `proj_delete` | `cockpit2.py:1679` |
| `proj_edit` | `cockpit2.py:1706` |
| `proj_comment` | `cockpit2.py:1719` |
| `proj_rename` | `cockpit2.py:1730` |
| `proj_describe` | `cockpit2.py:1741` |
| `proj_doc_edit` | `cockpit2.py:1875` |
| `verslag_bevestig_behaald` | `cockpit2.py:1816` |
| `verslag_bevestig_niet_behaald` | `cockpit2.py:1822` |
| `verslag_overslaan` | `cockpit2.py:1827` |
| `verslag_bijwerken` | `cockpit2.py:1853` |
| `proj_regen_doc` | `cockpit2.py:1752` |
| `proj_settrekker` | `cockpit2.py:1888` |
| `proj_setowner` | `cockpit2.py:1929` |
| `proj_approve` | `cockpit2.py:1948` |
| `proj_discard` | `cockpit2.py:1959` |
| `proj_proposal_accept` | `cockpit2.py:1970` |
| `proj_proposal_reject` | `cockpit2.py:1983` |
| `proj_setlabel` | `cockpit2.py:1996` |
| `proj_setimpact` | `cockpit2.py:2011` |
| `proj_seteffort` | `cockpit2.py:2041` |
| `proj_agendeer_verzwakt` | `cockpit2.py:2059` |
| `proj_setprivate` | `cockpit2.py:2083` |
| `proj_setdue` | `cockpit2.py:2094` |
| `proj_goal` | `cockpit2.py:2105` |
| `proj_depends` | `cockpit2.py:2120` |
| `goal_add` | `cockpit2.py:2137` |
| `goal_edit` | `cockpit2.py:2151` |
| `goal_link` | `cockpit2.py:2165` |
| `attach_add` | `cockpit2.py:2182` |
| `attach_remove` | `cockpit2.py:2193` |
| `react_add` | `cockpit2.py:2203` |
| `feed_edit` | `cockpit2.py:2214` |
| `feed_remove` | `cockpit2.py:2225` |
| `wall_outcome` | `cockpit2.py:3853` |
| `notif_read` | `cockpit2.py:3949` |
| `notif_processed` | `cockpit2.py:3959` |
| `notif_outcome` | `cockpit2.py:4275` |
| `notif_klaar` | `cockpit2.py:4216` |
| `goedkeur` | `cockpit2.py:3968` |
| `notif_delete` | `cockpit2.py:4013` |
| `notif_add` | `cockpit2.py:4164` |
| `notif_archive` | `cockpit2.py:4397` |
| `metrics2_fav` | `cockpit2.py:4024` |
| `metrics2_unfav` | `cockpit2.py:4039` |
| `metrics2_form` | `cockpit2.py:4044` |
| `metrics2_dim` | `cockpit2.py:4051` |
| `metrics2_compare` | `cockpit2.py:4059` |
| `metrics2_formula` | `cockpit2.py:4149` |
| `source_activate` | `cockpit2.py:4125` |
| `source_deactivate` | `cockpit2.py:4137` |
| `link_pursue` | `cockpit2.py:4099` |
| `link_ignore` | `cockpit2.py:4110` |
| `acc_check` | `cockpit2.py:4068` |
| `ai_reply` | `cockpit2.py:2235` |
| `proj_feed` | `cockpit2.py:2247` |
| `checklist_add` | `cockpit2.py:2295` |
| `checklist_remove` | `cockpit2.py:2335` |
| `plan_akkoord` | `cockpit2.py:2318` |
| `checklist_uitvoer` | `cockpit2.py:2306` |
| `check_add` | `cockpit2.py:2385` |
| `check_accept` | `cockpit2.py:2402` |
| `check_toggle` | `cockpit2.py:2412` |
| `check_skip` | `cockpit2.py:2434` |
| `check_unskip` | `cockpit2.py:2446` |
| `check_handoff` | `cockpit2.py:2467` |
| `check_remove` | `cockpit2.py:2515` |
| `check_rename` | `cockpit2.py:2525` |
| `check_move` | `cockpit2.py:2544` |
| `role_assign` | `cockpit2.py:2558` |
| `role_unassign` | `cockpit2.py:2583` |
| `role_focus` | `cockpit2.py:2605` |
| `radar_approve` | `cockpit2.py:2638` |
| `radar_dismiss` | `cockpit2.py:2648` |
| `radar_promote` | `cockpit2.py:2652` |
| `radar_merge` | `cockpit2.py:2672` |
| `radar_koppel` | `cockpit2.py:2688` |
| `kb_stage_koppel` | `cockpit2.py:2715` |
| `middel_remove` | `cockpit2.py:2763` |
| `skilllink_add` | `cockpit2.py:2794` |
| `means_gap_add` | `cockpit2.py:2824` |
| `rov2_add` | `cockpit2.py:2978` |
| `rov2_add_to_group` | `cockpit2.py:2990` |
| `rov2_remove` | `cockpit2.py:3002` |
| `rov2_remove_group` | `cockpit2.py:3017` |
| `rov2_setkind` | `cockpit2.py:3035` |
| `rov2_consent` | `cockpit2.py:3048` |
| `rov2_end` | `cockpit2.py:3070` |
| `wo_open` | `cockpit2.py:3094` |
| `wo_close` | `cockpit2.py:3104` |
| `wo_presence` | `cockpit2.py:3120` |
| `wo_present_all` | `cockpit2.py:3131` |
| `vangst_add` | `cockpit2.py:3143` |
| `vangst_tekst` | `cockpit2.py:3191` |
| `vangst_klaar` | `cockpit2.py:3201` |
| `vangst_uitkomst` | `cockpit2.py:3250` |
| `vangst_uitkomst_weg` | `cockpit2.py:3238` |
| `vangst_uitkomst_edit` | `cockpit2.py:3213` |
| `vangst_remove` | `cockpit2.py:3182` |
| `vangst_verwerk` | `cockpit2.py:3366` |
| `wo_checkout` | `cockpit2.py:4406` |
| `noochie_send` | `cockpit2.py:4421` |
| `noochie_reset` | `cockpit2.py:4448` |
| `noochie_ctx` | `cockpit2.py:4456` |
| `cl_add` | `cockpit2.py:4464` |
| `cl_report` | `cockpit2.py:4482` |
| `cl_remove` | `cockpit2.py:4497` |
| `m_add_kpi` | `cockpit2.py:4507` |
| `m_add_from_def` | `cockpit2.py:4539` |
| `def_add` | `cockpit2.py:4554` |
| `catalog_publish` | `cockpit2.py:4576` |
| `def_amend` | `cockpit2.py:4602` |
| `m_add_link` | `cockpit2.py:4644` |
| `m_sample` | `cockpit2.py:4655` |
| `m_remove` | `cockpit2.py:4665` |
| `m_pin` | `cockpit2.py:4675` |
| `m_unpin` | `cockpit2.py:4686` |
| `tile_add` | `cockpit2.py:4724` |
| `indicator_activate` | `cockpit2.py:4696` |
| `tile_remove` | `cockpit2.py:4758` |
| `rov2_set` | `cockpit2.py:4768` |
| `rov2_acc_add` | `cockpit2.py:4768` |
| `rov2_acc_remove` | `cockpit2.py:4768` |
| `rov2_dom_add` | `cockpit2.py:4768` |
| `rov2_dom_remove` | `cockpit2.py:4768` |
| `person_edit` | `cockpit2.py:4800` |
| `person_remove` | `cockpit2.py:4817` |
| `lk_mute` | `cockpit2.py:4838` |
| `claims_term_add` | `cockpit2.py:4968` |
| `claims_term_retract` | `cockpit2.py:5005` |
| `claims_work_status` | `cockpit2.py:4989` |
| `claims_bewijs_link` | `cockpit2.py:5034` |
| `claims_vondst_whitelist` | `cockpit2.py:5058` |
| `claims_regel_uit_vondst` | `cockpit2.py:5084` |
| `claims_to_board` | `cockpit2.py:5116` |
| `persona_edit` | `cockpit2.py:2877` |
| `persona_llm` | `cockpit2.py:2896` |
| `persona_finetune` | `cockpit2.py:2913` |
| `persona_finetune_apply` | `cockpit2.py:2931` |


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
