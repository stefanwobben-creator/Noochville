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
| `ff_beslis` | `cockpit2.py:4851` |
| `ff_cluster` | `cockpit2.py:4979` |
| `ff_promote` | `cockpit2.py:4909` |
| `ff_demote` | `cockpit2.py:4933` |
| `ff_run` | `cockpit2.py:4952` |
| `kb_new` | `cockpit2.py:4231` |
| `kb_intake` | `cockpit2.py:4313` |
| `kb_intake_url` | `cockpit2.py:4330` |
| `kb_stage_edit` | `cockpit2.py:4349` |
| `kb_stage_accept` | `cockpit2.py:4361` |
| `kb_stage_delete` | `cockpit2.py:4380` |
| `kb_stage_merge` | `cockpit2.py:4386` |
| `kb_stage_commit` | `cockpit2.py:4397` |
| `kb_stage_discard` | `cockpit2.py:4417` |
| `kb_atoom_subject` | `cockpit2.py:4655` |
| `kb_atoom_purge` | `cockpit2.py:4639` |
| `tag_voorstel_besluit` | `cockpit2.py:4493` |
| `tag_onderhoud_run` | `cockpit2.py:4626` |
| `copy_stack_inclusie` | `cockpit2.py:4608` |
| `verzoek_besluit` | `cockpit2.py:4512` |
| `kb_blacklist_leeg` | `cockpit2.py:4648` |
| `kb_atoom_edit` | `cockpit2.py:4423` |
| `kb_atoom_related` | `cockpit2.py:4430` |
| `kb_atoom_reference` | `cockpit2.py:4475` |
| `kb_insight_link` | `cockpit2.py:4442` |
| `kb_insight_unlink` | `cockpit2.py:4449` |
| `kb_meta_start` | `cockpit2.py:4455` |
| `kb_atoom_merge` | `cockpit2.py:4666` |
| `kb_atoom_archive` | `cockpit2.py:4687` |
| `kb_atoom_unarchive` | `cockpit2.py:4696` |
| `kb_atoom_naar_spel` | `cockpit2.py:4702` |
| `kb_spel_start` | `cockpit2.py:4723` |
| `kb_spel_add` | `cockpit2.py:4737` |
| `kb_spel_remove` | `cockpit2.py:4747` |
| `kb_spel_flip` | `cockpit2.py:4754` |
| `kb_spel_finish` | `cockpit2.py:4760` |
| `kb_link` | `cockpit2.py:4240` |
| `kb_unlink` | `cockpit2.py:4254` |
| `kb_annotate` | `cockpit2.py:4265` |
| `kb_evidence` | `cockpit2.py:4271` |
| `kb_discuss` | `cockpit2.py:4292` |
| `kb_reformulate` | `cockpit2.py:4298` |
| `kw_nominate` | `cockpit2.py:4771` |
| `kw_nom_accept` | `cockpit2.py:4782` |
| `kw_nom_reject` | `cockpit2.py:4800` |
| `ws_forbid` | `cockpit2.py:4830` |
| `ws_approve` | `cockpit2.py:4835` |
| `proj_add` | `cockpit2.py:1206` |
| `artefact_add` | `cockpit2.py:1250` |
| `artefact_edit` | `cockpit2.py:1294` |
| `artefact_archive` | `cockpit2.py:1321` |
| `pagina_feit_add` | `cockpit2.py:1341` |
| `pagina_feit_del` | `cockpit2.py:1370` |
| `pagina_voorstel` | `cockpit2.py:1401` |
| `proj_status` | `cockpit2.py:1431` |
| `proj_done` | `cockpit2.py:1449` |
| `proj_dod` | `cockpit2.py:1498` |
| `proj_archive` | `cockpit2.py:1512` |
| `proj_unarchive` | `cockpit2.py:1535` |
| `proj_delete` | `cockpit2.py:1545` |
| `proj_edit` | `cockpit2.py:1572` |
| `proj_comment` | `cockpit2.py:1585` |
| `proj_rename` | `cockpit2.py:1595` |
| `proj_describe` | `cockpit2.py:1606` |
| `proj_doc_edit` | `cockpit2.py:1639` |
| `proj_regen_doc` | `cockpit2.py:1617` |
| `proj_settrekker` | `cockpit2.py:1652` |
| `proj_setowner` | `cockpit2.py:1689` |
| `proj_approve` | `cockpit2.py:1708` |
| `proj_discard` | `cockpit2.py:1719` |
| `proj_proposal_accept` | `cockpit2.py:1730` |
| `proj_proposal_reject` | `cockpit2.py:1743` |
| `proj_setlabel` | `cockpit2.py:1756` |
| `proj_setimpact` | `cockpit2.py:1771` |
| `proj_seteffort` | `cockpit2.py:1790` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1813` |
| `proj_setprivate` | `cockpit2.py:1837` |
| `proj_setdue` | `cockpit2.py:1848` |
| `attach_add` | `cockpit2.py:1859` |
| `attach_remove` | `cockpit2.py:1870` |
| `react_add` | `cockpit2.py:1880` |
| `feed_edit` | `cockpit2.py:1890` |
| `feed_remove` | `cockpit2.py:1900` |
| `wall_outcome` | `cockpit2.py:3070` |
| `notif_read` | `cockpit2.py:3168` |
| `notif_processed` | `cockpit2.py:3173` |
| `notif_outcome` | `cockpit2.py:3320` |
| `notif_besluit` | `cockpit2.py:3407` |
| `notif_klaar` | `cockpit2.py:3306` |
| `notif_delete` | `cockpit2.py:3178` |
| `notif_add` | `cockpit2.py:3290` |
| `notif_archive` | `cockpit2.py:3449` |
| `metrics2_fav` | `cockpit2.py:3184` |
| `metrics2_unfav` | `cockpit2.py:3194` |
| `metrics2_form` | `cockpit2.py:3199` |
| `metrics2_dim` | `cockpit2.py:3205` |
| `metrics2_compare` | `cockpit2.py:3212` |
| `metrics2_formula` | `cockpit2.py:3275` |
| `source_activate` | `cockpit2.py:3258` |
| `source_deactivate` | `cockpit2.py:3267` |
| `link_pursue` | `cockpit2.py:3239` |
| `link_ignore` | `cockpit2.py:3249` |
| `acc_check` | `cockpit2.py:3220` |
| `ai_reply` | `cockpit2.py:1909` |
| `proj_feed` | `cockpit2.py:1920` |
| `checklist_add` | `cockpit2.py:1950` |
| `checklist_remove` | `cockpit2.py:1961` |
| `check_add` | `cockpit2.py:2009` |
| `check_accept` | `cockpit2.py:2026` |
| `check_toggle` | `cockpit2.py:2036` |
| `check_skip` | `cockpit2.py:2058` |
| `check_unskip` | `cockpit2.py:2070` |
| `check_handoff` | `cockpit2.py:2082` |
| `check_remove` | `cockpit2.py:2096` |
| `role_assign` | `cockpit2.py:2106` |
| `role_unassign` | `cockpit2.py:2124` |
| `role_focus` | `cockpit2.py:2143` |
| `radar_approve` | `cockpit2.py:2176` |
| `radar_dismiss` | `cockpit2.py:2186` |
| `radar_promote` | `cockpit2.py:2190` |
| `radar_merge` | `cockpit2.py:2210` |
| `radar_koppel` | `cockpit2.py:2226` |
| `kb_stage_koppel` | `cockpit2.py:2253` |
| `aitask_add` | `cockpit2.py:2291` |
| `aitask_remove` | `cockpit2.py:2322` |
| `skilllink_add` | `cockpit2.py:2350` |
| `means_gap_add` | `cockpit2.py:2380` |
| `persona_skill_add` | `cockpit2.py:2534` |
| `rov2_add` | `cockpit2.py:2549` |
| `rov2_add_to_group` | `cockpit2.py:2561` |
| `rov2_remove` | `cockpit2.py:2573` |
| `rov2_remove_group` | `cockpit2.py:2588` |
| `rov2_setkind` | `cockpit2.py:2606` |
| `rov2_consent` | `cockpit2.py:2619` |
| `rov2_end` | `cockpit2.py:2641` |
| `wo_open` | `cockpit2.py:2665` |
| `wo_close` | `cockpit2.py:2675` |
| `wo_presence` | `cockpit2.py:2691` |
| `wo_present_all` | `cockpit2.py:2702` |
| `vangst_add` | `cockpit2.py:2714` |
| `vangst_tekst` | `cockpit2.py:2753` |
| `vangst_klaar` | `cockpit2.py:2763` |
| `vangst_uitkomst` | `cockpit2.py:2787` |
| `vangst_uitkomst_weg` | `cockpit2.py:2775` |
| `vangst_remove` | `cockpit2.py:2744` |
| `vangst_verwerk` | `cockpit2.py:2850` |
| `wo_ag_add` | `cockpit2.py:2934` |
| `wo_ag_remove` | `cockpit2.py:2946` |
| `wo_ag_note` | `cockpit2.py:2956` |
| `wo_ag_reopen` | `cockpit2.py:2968` |
| `wo_ag_resolve` | `cockpit2.py:3044` |
| `wo_checkout` | `cockpit2.py:3454` |
| `noochie_send` | `cockpit2.py:3466` |
| `noochie_reset` | `cockpit2.py:3492` |
| `noochie_ctx` | `cockpit2.py:3499` |
| `cl_add` | `cockpit2.py:3506` |
| `cl_report` | `cockpit2.py:3524` |
| `cl_remove` | `cockpit2.py:3539` |
| `m_add_kpi` | `cockpit2.py:3549` |
| `m_add_from_def` | `cockpit2.py:3581` |
| `def_add` | `cockpit2.py:3596` |
| `catalog_publish` | `cockpit2.py:3618` |
| `def_amend` | `cockpit2.py:3644` |
| `m_add_link` | `cockpit2.py:3686` |
| `m_sample` | `cockpit2.py:3697` |
| `m_remove` | `cockpit2.py:3707` |
| `m_pin` | `cockpit2.py:3717` |
| `m_unpin` | `cockpit2.py:3728` |
| `tile_add` | `cockpit2.py:3766` |
| `indicator_activate` | `cockpit2.py:3738` |
| `tile_remove` | `cockpit2.py:3800` |
| `rov2_set` | `cockpit2.py:3810` |
| `rov2_acc_add` | `cockpit2.py:3810` |
| `rov2_acc_remove` | `cockpit2.py:3810` |
| `rov2_dom_add` | `cockpit2.py:3810` |
| `rov2_dom_remove` | `cockpit2.py:3810` |
| `backlog_add` | `cockpit2.py:3842` |
| `backlog_update_staat` | `cockpit2.py:3854` |
| `backlog_update_prioriteit` | `cockpit2.py:3866` |
| `person_edit` | `cockpit2.py:3878` |
| `person_remove` | `cockpit2.py:3895` |
| `lk_mute` | `cockpit2.py:3916` |
| `claims_term_add` | `cockpit2.py:4019` |
| `claims_term_retract` | `cockpit2.py:4056` |
| `claims_work_status` | `cockpit2.py:4040` |
| `claims_bewijs_link` | `cockpit2.py:4085` |
| `claims_vondst_whitelist` | `cockpit2.py:4109` |
| `claims_regel_uit_vondst` | `cockpit2.py:4135` |
| `claims_to_board` | `cockpit2.py:4167` |
| `persona_edit` | `cockpit2.py:2433` |
| `persona_llm` | `cockpit2.py:2452` |
| `persona_finetune` | `cockpit2.py:2469` |
| `persona_finetune_apply` | `cockpit2.py:2487` |


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
_57 routes · 193 dispatch-acties · 32 stores._
