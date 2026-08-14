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
| `ff_beslis` | `cockpit2.py:4416` |
| `ff_cluster` | `cockpit2.py:4544` |
| `ff_promote` | `cockpit2.py:4474` |
| `ff_demote` | `cockpit2.py:4498` |
| `ff_run` | `cockpit2.py:4517` |
| `kb_new` | `cockpit2.py:3892` |
| `kb_intake` | `cockpit2.py:3974` |
| `kb_intake_url` | `cockpit2.py:3991` |
| `kb_stage_edit` | `cockpit2.py:4010` |
| `kb_stage_accept` | `cockpit2.py:4022` |
| `kb_stage_delete` | `cockpit2.py:4041` |
| `kb_stage_merge` | `cockpit2.py:4047` |
| `kb_stage_commit` | `cockpit2.py:4058` |
| `kb_stage_discard` | `cockpit2.py:4078` |
| `kb_atoom_subject` | `cockpit2.py:4220` |
| `kb_atoom_purge` | `cockpit2.py:4204` |
| `tag_voorstel_besluit` | `cockpit2.py:4154` |
| `tag_onderhoud_run` | `cockpit2.py:4191` |
| `copy_stack_inclusie` | `cockpit2.py:4173` |
| `kb_blacklist_leeg` | `cockpit2.py:4213` |
| `kb_atoom_edit` | `cockpit2.py:4084` |
| `kb_atoom_related` | `cockpit2.py:4091` |
| `kb_atoom_reference` | `cockpit2.py:4136` |
| `kb_insight_link` | `cockpit2.py:4103` |
| `kb_insight_unlink` | `cockpit2.py:4110` |
| `kb_meta_start` | `cockpit2.py:4116` |
| `kb_atoom_merge` | `cockpit2.py:4231` |
| `kb_atoom_archive` | `cockpit2.py:4252` |
| `kb_atoom_unarchive` | `cockpit2.py:4261` |
| `kb_atoom_naar_spel` | `cockpit2.py:4267` |
| `kb_spel_start` | `cockpit2.py:4288` |
| `kb_spel_add` | `cockpit2.py:4302` |
| `kb_spel_remove` | `cockpit2.py:4312` |
| `kb_spel_flip` | `cockpit2.py:4319` |
| `kb_spel_finish` | `cockpit2.py:4325` |
| `kb_link` | `cockpit2.py:3901` |
| `kb_unlink` | `cockpit2.py:3915` |
| `kb_annotate` | `cockpit2.py:3926` |
| `kb_evidence` | `cockpit2.py:3932` |
| `kb_discuss` | `cockpit2.py:3953` |
| `kb_reformulate` | `cockpit2.py:3959` |
| `kw_nominate` | `cockpit2.py:4336` |
| `kw_nom_accept` | `cockpit2.py:4347` |
| `kw_nom_reject` | `cockpit2.py:4365` |
| `ws_forbid` | `cockpit2.py:4395` |
| `ws_approve` | `cockpit2.py:4400` |
| `proj_add` | `cockpit2.py:1192` |
| `artefact_add` | `cockpit2.py:1227` |
| `artefact_edit` | `cockpit2.py:1268` |
| `artefact_archive` | `cockpit2.py:1292` |
| `proj_status` | `cockpit2.py:1312` |
| `proj_done` | `cockpit2.py:1330` |
| `proj_dod` | `cockpit2.py:1379` |
| `proj_archive` | `cockpit2.py:1393` |
| `proj_unarchive` | `cockpit2.py:1416` |
| `proj_delete` | `cockpit2.py:1426` |
| `proj_edit` | `cockpit2.py:1453` |
| `proj_comment` | `cockpit2.py:1466` |
| `proj_rename` | `cockpit2.py:1476` |
| `proj_describe` | `cockpit2.py:1487` |
| `proj_doc_edit` | `cockpit2.py:1520` |
| `proj_regen_doc` | `cockpit2.py:1498` |
| `proj_settrekker` | `cockpit2.py:1533` |
| `proj_setowner` | `cockpit2.py:1570` |
| `proj_approve` | `cockpit2.py:1589` |
| `proj_discard` | `cockpit2.py:1600` |
| `proj_proposal_accept` | `cockpit2.py:1611` |
| `proj_proposal_reject` | `cockpit2.py:1624` |
| `proj_setlabel` | `cockpit2.py:1637` |
| `proj_setimpact` | `cockpit2.py:1652` |
| `proj_seteffort` | `cockpit2.py:1671` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1694` |
| `proj_setprivate` | `cockpit2.py:1718` |
| `proj_setdue` | `cockpit2.py:1729` |
| `attach_add` | `cockpit2.py:1740` |
| `attach_remove` | `cockpit2.py:1751` |
| `react_add` | `cockpit2.py:1761` |
| `feed_edit` | `cockpit2.py:1771` |
| `feed_remove` | `cockpit2.py:1781` |
| `wall_outcome` | `cockpit2.py:2731` |
| `notif_read` | `cockpit2.py:2829` |
| `notif_processed` | `cockpit2.py:2834` |
| `notif_outcome` | `cockpit2.py:2981` |
| `notif_besluit` | `cockpit2.py:3068` |
| `notif_klaar` | `cockpit2.py:2967` |
| `notif_delete` | `cockpit2.py:2839` |
| `notif_add` | `cockpit2.py:2951` |
| `notif_archive` | `cockpit2.py:3110` |
| `metrics2_fav` | `cockpit2.py:2845` |
| `metrics2_unfav` | `cockpit2.py:2855` |
| `metrics2_form` | `cockpit2.py:2860` |
| `metrics2_dim` | `cockpit2.py:2866` |
| `metrics2_compare` | `cockpit2.py:2873` |
| `metrics2_formula` | `cockpit2.py:2936` |
| `source_activate` | `cockpit2.py:2919` |
| `source_deactivate` | `cockpit2.py:2928` |
| `link_pursue` | `cockpit2.py:2900` |
| `link_ignore` | `cockpit2.py:2910` |
| `acc_check` | `cockpit2.py:2881` |
| `ai_reply` | `cockpit2.py:1790` |
| `proj_feed` | `cockpit2.py:1801` |
| `checklist_add` | `cockpit2.py:1831` |
| `checklist_remove` | `cockpit2.py:1842` |
| `check_add` | `cockpit2.py:1890` |
| `check_accept` | `cockpit2.py:1907` |
| `check_toggle` | `cockpit2.py:1917` |
| `check_skip` | `cockpit2.py:1939` |
| `check_unskip` | `cockpit2.py:1951` |
| `check_handoff` | `cockpit2.py:1963` |
| `check_remove` | `cockpit2.py:1977` |
| `role_assign` | `cockpit2.py:1987` |
| `role_unassign` | `cockpit2.py:2005` |
| `role_focus` | `cockpit2.py:2024` |
| `radar_approve` | `cockpit2.py:2057` |
| `radar_dismiss` | `cockpit2.py:2067` |
| `radar_promote` | `cockpit2.py:2071` |
| `radar_merge` | `cockpit2.py:2091` |
| `radar_koppel` | `cockpit2.py:2107` |
| `kb_stage_koppel` | `cockpit2.py:2134` |
| `aitask_add` | `cockpit2.py:2172` |
| `aitask_remove` | `cockpit2.py:2203` |
| `skilllink_add` | `cockpit2.py:2231` |
| `means_gap_add` | `cockpit2.py:2261` |
| `persona_skill_add` | `cockpit2.py:2415` |
| `rov2_add` | `cockpit2.py:2430` |
| `rov2_add_to_group` | `cockpit2.py:2442` |
| `rov2_remove` | `cockpit2.py:2454` |
| `rov2_remove_group` | `cockpit2.py:2469` |
| `rov2_setkind` | `cockpit2.py:2487` |
| `rov2_consent` | `cockpit2.py:2500` |
| `rov2_end` | `cockpit2.py:2522` |
| `wo_open` | `cockpit2.py:2546` |
| `wo_close` | `cockpit2.py:2556` |
| `wo_presence` | `cockpit2.py:2572` |
| `wo_present_all` | `cockpit2.py:2583` |
| `wo_ag_add` | `cockpit2.py:2595` |
| `wo_ag_remove` | `cockpit2.py:2607` |
| `wo_ag_note` | `cockpit2.py:2617` |
| `wo_ag_reopen` | `cockpit2.py:2629` |
| `wo_ag_resolve` | `cockpit2.py:2705` |
| `wo_checkout` | `cockpit2.py:3115` |
| `noochie_send` | `cockpit2.py:3127` |
| `noochie_reset` | `cockpit2.py:3153` |
| `noochie_ctx` | `cockpit2.py:3160` |
| `cl_add` | `cockpit2.py:3167` |
| `cl_report` | `cockpit2.py:3185` |
| `cl_remove` | `cockpit2.py:3200` |
| `m_add_kpi` | `cockpit2.py:3210` |
| `m_add_from_def` | `cockpit2.py:3242` |
| `def_add` | `cockpit2.py:3257` |
| `catalog_publish` | `cockpit2.py:3279` |
| `def_amend` | `cockpit2.py:3305` |
| `m_add_link` | `cockpit2.py:3347` |
| `m_sample` | `cockpit2.py:3358` |
| `m_remove` | `cockpit2.py:3368` |
| `m_pin` | `cockpit2.py:3378` |
| `m_unpin` | `cockpit2.py:3389` |
| `tile_add` | `cockpit2.py:3427` |
| `indicator_activate` | `cockpit2.py:3399` |
| `tile_remove` | `cockpit2.py:3461` |
| `rov2_set` | `cockpit2.py:3471` |
| `rov2_acc_add` | `cockpit2.py:3471` |
| `rov2_acc_remove` | `cockpit2.py:3471` |
| `rov2_dom_add` | `cockpit2.py:3471` |
| `rov2_dom_remove` | `cockpit2.py:3471` |
| `backlog_add` | `cockpit2.py:3503` |
| `backlog_update_staat` | `cockpit2.py:3515` |
| `backlog_update_prioriteit` | `cockpit2.py:3527` |
| `person_edit` | `cockpit2.py:3539` |
| `person_remove` | `cockpit2.py:3556` |
| `lk_mute` | `cockpit2.py:3577` |
| `claims_term_add` | `cockpit2.py:3680` |
| `claims_term_retract` | `cockpit2.py:3717` |
| `claims_work_status` | `cockpit2.py:3701` |
| `claims_bewijs_link` | `cockpit2.py:3746` |
| `claims_vondst_whitelist` | `cockpit2.py:3770` |
| `claims_regel_uit_vondst` | `cockpit2.py:3796` |
| `claims_to_board` | `cockpit2.py:3828` |
| `persona_edit` | `cockpit2.py:2314` |
| `persona_llm` | `cockpit2.py:2333` |
| `persona_finetune` | `cockpit2.py:2350` |
| `persona_finetune_apply` | `cockpit2.py:2368` |


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
_54 routes · 182 dispatch-acties · 32 stores._
