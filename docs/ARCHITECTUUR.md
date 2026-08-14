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
| `ff_beslis` | `cockpit2.py:4405` |
| `ff_cluster` | `cockpit2.py:4533` |
| `ff_promote` | `cockpit2.py:4463` |
| `ff_demote` | `cockpit2.py:4487` |
| `ff_run` | `cockpit2.py:4506` |
| `kb_new` | `cockpit2.py:3881` |
| `kb_intake` | `cockpit2.py:3963` |
| `kb_intake_url` | `cockpit2.py:3980` |
| `kb_stage_edit` | `cockpit2.py:3999` |
| `kb_stage_accept` | `cockpit2.py:4011` |
| `kb_stage_delete` | `cockpit2.py:4030` |
| `kb_stage_merge` | `cockpit2.py:4036` |
| `kb_stage_commit` | `cockpit2.py:4047` |
| `kb_stage_discard` | `cockpit2.py:4067` |
| `kb_atoom_subject` | `cockpit2.py:4209` |
| `kb_atoom_purge` | `cockpit2.py:4193` |
| `tag_voorstel_besluit` | `cockpit2.py:4143` |
| `tag_onderhoud_run` | `cockpit2.py:4180` |
| `copy_stack_inclusie` | `cockpit2.py:4162` |
| `kb_blacklist_leeg` | `cockpit2.py:4202` |
| `kb_atoom_edit` | `cockpit2.py:4073` |
| `kb_atoom_related` | `cockpit2.py:4080` |
| `kb_atoom_reference` | `cockpit2.py:4125` |
| `kb_insight_link` | `cockpit2.py:4092` |
| `kb_insight_unlink` | `cockpit2.py:4099` |
| `kb_meta_start` | `cockpit2.py:4105` |
| `kb_atoom_merge` | `cockpit2.py:4220` |
| `kb_atoom_archive` | `cockpit2.py:4241` |
| `kb_atoom_unarchive` | `cockpit2.py:4250` |
| `kb_atoom_naar_spel` | `cockpit2.py:4256` |
| `kb_spel_start` | `cockpit2.py:4277` |
| `kb_spel_add` | `cockpit2.py:4291` |
| `kb_spel_remove` | `cockpit2.py:4301` |
| `kb_spel_flip` | `cockpit2.py:4308` |
| `kb_spel_finish` | `cockpit2.py:4314` |
| `kb_link` | `cockpit2.py:3890` |
| `kb_unlink` | `cockpit2.py:3904` |
| `kb_annotate` | `cockpit2.py:3915` |
| `kb_evidence` | `cockpit2.py:3921` |
| `kb_discuss` | `cockpit2.py:3942` |
| `kb_reformulate` | `cockpit2.py:3948` |
| `kw_nominate` | `cockpit2.py:4325` |
| `kw_nom_accept` | `cockpit2.py:4336` |
| `kw_nom_reject` | `cockpit2.py:4354` |
| `ws_forbid` | `cockpit2.py:4384` |
| `ws_approve` | `cockpit2.py:4389` |
| `proj_add` | `cockpit2.py:1181` |
| `artefact_add` | `cockpit2.py:1216` |
| `artefact_edit` | `cockpit2.py:1257` |
| `artefact_archive` | `cockpit2.py:1281` |
| `proj_status` | `cockpit2.py:1301` |
| `proj_done` | `cockpit2.py:1319` |
| `proj_dod` | `cockpit2.py:1368` |
| `proj_archive` | `cockpit2.py:1382` |
| `proj_unarchive` | `cockpit2.py:1405` |
| `proj_delete` | `cockpit2.py:1415` |
| `proj_edit` | `cockpit2.py:1442` |
| `proj_comment` | `cockpit2.py:1455` |
| `proj_rename` | `cockpit2.py:1465` |
| `proj_describe` | `cockpit2.py:1476` |
| `proj_doc_edit` | `cockpit2.py:1509` |
| `proj_regen_doc` | `cockpit2.py:1487` |
| `proj_settrekker` | `cockpit2.py:1522` |
| `proj_setowner` | `cockpit2.py:1559` |
| `proj_approve` | `cockpit2.py:1578` |
| `proj_discard` | `cockpit2.py:1589` |
| `proj_proposal_accept` | `cockpit2.py:1600` |
| `proj_proposal_reject` | `cockpit2.py:1613` |
| `proj_setlabel` | `cockpit2.py:1626` |
| `proj_setimpact` | `cockpit2.py:1641` |
| `proj_seteffort` | `cockpit2.py:1660` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1683` |
| `proj_setprivate` | `cockpit2.py:1707` |
| `proj_setdue` | `cockpit2.py:1718` |
| `attach_add` | `cockpit2.py:1729` |
| `attach_remove` | `cockpit2.py:1740` |
| `react_add` | `cockpit2.py:1750` |
| `feed_edit` | `cockpit2.py:1760` |
| `feed_remove` | `cockpit2.py:1770` |
| `wall_outcome` | `cockpit2.py:2720` |
| `notif_read` | `cockpit2.py:2818` |
| `notif_processed` | `cockpit2.py:2823` |
| `notif_outcome` | `cockpit2.py:2970` |
| `notif_besluit` | `cockpit2.py:3057` |
| `notif_klaar` | `cockpit2.py:2956` |
| `notif_delete` | `cockpit2.py:2828` |
| `notif_add` | `cockpit2.py:2940` |
| `notif_archive` | `cockpit2.py:3099` |
| `metrics2_fav` | `cockpit2.py:2834` |
| `metrics2_unfav` | `cockpit2.py:2844` |
| `metrics2_form` | `cockpit2.py:2849` |
| `metrics2_dim` | `cockpit2.py:2855` |
| `metrics2_compare` | `cockpit2.py:2862` |
| `metrics2_formula` | `cockpit2.py:2925` |
| `source_activate` | `cockpit2.py:2908` |
| `source_deactivate` | `cockpit2.py:2917` |
| `link_pursue` | `cockpit2.py:2889` |
| `link_ignore` | `cockpit2.py:2899` |
| `acc_check` | `cockpit2.py:2870` |
| `ai_reply` | `cockpit2.py:1779` |
| `proj_feed` | `cockpit2.py:1790` |
| `checklist_add` | `cockpit2.py:1820` |
| `checklist_remove` | `cockpit2.py:1831` |
| `check_add` | `cockpit2.py:1879` |
| `check_accept` | `cockpit2.py:1896` |
| `check_toggle` | `cockpit2.py:1906` |
| `check_skip` | `cockpit2.py:1928` |
| `check_unskip` | `cockpit2.py:1940` |
| `check_handoff` | `cockpit2.py:1952` |
| `check_remove` | `cockpit2.py:1966` |
| `role_assign` | `cockpit2.py:1976` |
| `role_unassign` | `cockpit2.py:1994` |
| `role_focus` | `cockpit2.py:2013` |
| `radar_approve` | `cockpit2.py:2046` |
| `radar_dismiss` | `cockpit2.py:2056` |
| `radar_promote` | `cockpit2.py:2060` |
| `radar_merge` | `cockpit2.py:2080` |
| `radar_koppel` | `cockpit2.py:2096` |
| `kb_stage_koppel` | `cockpit2.py:2123` |
| `aitask_add` | `cockpit2.py:2161` |
| `aitask_remove` | `cockpit2.py:2192` |
| `skilllink_add` | `cockpit2.py:2220` |
| `means_gap_add` | `cockpit2.py:2250` |
| `persona_skill_add` | `cockpit2.py:2404` |
| `rov2_add` | `cockpit2.py:2419` |
| `rov2_add_to_group` | `cockpit2.py:2431` |
| `rov2_remove` | `cockpit2.py:2443` |
| `rov2_remove_group` | `cockpit2.py:2458` |
| `rov2_setkind` | `cockpit2.py:2476` |
| `rov2_consent` | `cockpit2.py:2489` |
| `rov2_end` | `cockpit2.py:2511` |
| `wo_open` | `cockpit2.py:2535` |
| `wo_close` | `cockpit2.py:2545` |
| `wo_presence` | `cockpit2.py:2561` |
| `wo_present_all` | `cockpit2.py:2572` |
| `wo_ag_add` | `cockpit2.py:2584` |
| `wo_ag_remove` | `cockpit2.py:2596` |
| `wo_ag_note` | `cockpit2.py:2606` |
| `wo_ag_reopen` | `cockpit2.py:2618` |
| `wo_ag_resolve` | `cockpit2.py:2694` |
| `wo_checkout` | `cockpit2.py:3104` |
| `noochie_send` | `cockpit2.py:3116` |
| `noochie_reset` | `cockpit2.py:3142` |
| `noochie_ctx` | `cockpit2.py:3149` |
| `cl_add` | `cockpit2.py:3156` |
| `cl_report` | `cockpit2.py:3174` |
| `cl_remove` | `cockpit2.py:3189` |
| `m_add_kpi` | `cockpit2.py:3199` |
| `m_add_from_def` | `cockpit2.py:3231` |
| `def_add` | `cockpit2.py:3246` |
| `catalog_publish` | `cockpit2.py:3268` |
| `def_amend` | `cockpit2.py:3294` |
| `m_add_link` | `cockpit2.py:3336` |
| `m_sample` | `cockpit2.py:3347` |
| `m_remove` | `cockpit2.py:3357` |
| `m_pin` | `cockpit2.py:3367` |
| `m_unpin` | `cockpit2.py:3378` |
| `tile_add` | `cockpit2.py:3416` |
| `indicator_activate` | `cockpit2.py:3388` |
| `tile_remove` | `cockpit2.py:3450` |
| `rov2_set` | `cockpit2.py:3460` |
| `rov2_acc_add` | `cockpit2.py:3460` |
| `rov2_acc_remove` | `cockpit2.py:3460` |
| `rov2_dom_add` | `cockpit2.py:3460` |
| `rov2_dom_remove` | `cockpit2.py:3460` |
| `backlog_add` | `cockpit2.py:3492` |
| `backlog_update_staat` | `cockpit2.py:3504` |
| `backlog_update_prioriteit` | `cockpit2.py:3516` |
| `person_edit` | `cockpit2.py:3528` |
| `person_remove` | `cockpit2.py:3545` |
| `lk_mute` | `cockpit2.py:3566` |
| `claims_term_add` | `cockpit2.py:3669` |
| `claims_term_retract` | `cockpit2.py:3706` |
| `claims_work_status` | `cockpit2.py:3690` |
| `claims_bewijs_link` | `cockpit2.py:3735` |
| `claims_vondst_whitelist` | `cockpit2.py:3759` |
| `claims_regel_uit_vondst` | `cockpit2.py:3785` |
| `claims_to_board` | `cockpit2.py:3817` |
| `persona_edit` | `cockpit2.py:2303` |
| `persona_llm` | `cockpit2.py:2322` |
| `persona_finetune` | `cockpit2.py:2339` |
| `persona_finetune_apply` | `cockpit2.py:2357` |


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
