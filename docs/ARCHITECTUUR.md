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
| `ff_beslis` | `cockpit2.py:4365` |
| `ff_cluster` | `cockpit2.py:4493` |
| `ff_promote` | `cockpit2.py:4423` |
| `ff_demote` | `cockpit2.py:4447` |
| `ff_run` | `cockpit2.py:4466` |
| `kb_new` | `cockpit2.py:3859` |
| `kb_intake` | `cockpit2.py:3941` |
| `kb_intake_url` | `cockpit2.py:3958` |
| `kb_stage_edit` | `cockpit2.py:3977` |
| `kb_stage_accept` | `cockpit2.py:3989` |
| `kb_stage_delete` | `cockpit2.py:4008` |
| `kb_stage_merge` | `cockpit2.py:4014` |
| `kb_stage_commit` | `cockpit2.py:4025` |
| `kb_stage_discard` | `cockpit2.py:4045` |
| `kb_atoom_subject` | `cockpit2.py:4169` |
| `kb_atoom_purge` | `cockpit2.py:4153` |
| `tag_voorstel_besluit` | `cockpit2.py:4121` |
| `tag_onderhoud_run` | `cockpit2.py:4140` |
| `kb_blacklist_leeg` | `cockpit2.py:4162` |
| `kb_atoom_edit` | `cockpit2.py:4051` |
| `kb_atoom_related` | `cockpit2.py:4058` |
| `kb_atoom_reference` | `cockpit2.py:4103` |
| `kb_insight_link` | `cockpit2.py:4070` |
| `kb_insight_unlink` | `cockpit2.py:4077` |
| `kb_meta_start` | `cockpit2.py:4083` |
| `kb_atoom_merge` | `cockpit2.py:4180` |
| `kb_atoom_archive` | `cockpit2.py:4201` |
| `kb_atoom_unarchive` | `cockpit2.py:4210` |
| `kb_atoom_naar_spel` | `cockpit2.py:4216` |
| `kb_spel_start` | `cockpit2.py:4237` |
| `kb_spel_add` | `cockpit2.py:4251` |
| `kb_spel_remove` | `cockpit2.py:4261` |
| `kb_spel_flip` | `cockpit2.py:4268` |
| `kb_spel_finish` | `cockpit2.py:4274` |
| `kb_link` | `cockpit2.py:3868` |
| `kb_unlink` | `cockpit2.py:3882` |
| `kb_annotate` | `cockpit2.py:3893` |
| `kb_evidence` | `cockpit2.py:3899` |
| `kb_discuss` | `cockpit2.py:3920` |
| `kb_reformulate` | `cockpit2.py:3926` |
| `kw_nominate` | `cockpit2.py:4285` |
| `kw_nom_accept` | `cockpit2.py:4296` |
| `kw_nom_reject` | `cockpit2.py:4314` |
| `ws_forbid` | `cockpit2.py:4344` |
| `ws_approve` | `cockpit2.py:4349` |
| `proj_add` | `cockpit2.py:1159` |
| `artefact_add` | `cockpit2.py:1194` |
| `artefact_edit` | `cockpit2.py:1235` |
| `artefact_archive` | `cockpit2.py:1259` |
| `proj_status` | `cockpit2.py:1279` |
| `proj_done` | `cockpit2.py:1297` |
| `proj_dod` | `cockpit2.py:1346` |
| `proj_archive` | `cockpit2.py:1360` |
| `proj_unarchive` | `cockpit2.py:1383` |
| `proj_delete` | `cockpit2.py:1393` |
| `proj_edit` | `cockpit2.py:1420` |
| `proj_comment` | `cockpit2.py:1433` |
| `proj_rename` | `cockpit2.py:1443` |
| `proj_describe` | `cockpit2.py:1454` |
| `proj_doc_edit` | `cockpit2.py:1487` |
| `proj_regen_doc` | `cockpit2.py:1465` |
| `proj_settrekker` | `cockpit2.py:1500` |
| `proj_setowner` | `cockpit2.py:1537` |
| `proj_approve` | `cockpit2.py:1556` |
| `proj_discard` | `cockpit2.py:1567` |
| `proj_proposal_accept` | `cockpit2.py:1578` |
| `proj_proposal_reject` | `cockpit2.py:1591` |
| `proj_setlabel` | `cockpit2.py:1604` |
| `proj_setimpact` | `cockpit2.py:1619` |
| `proj_seteffort` | `cockpit2.py:1638` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1661` |
| `proj_setprivate` | `cockpit2.py:1685` |
| `proj_setdue` | `cockpit2.py:1696` |
| `attach_add` | `cockpit2.py:1707` |
| `attach_remove` | `cockpit2.py:1718` |
| `react_add` | `cockpit2.py:1728` |
| `feed_edit` | `cockpit2.py:1738` |
| `feed_remove` | `cockpit2.py:1748` |
| `wall_outcome` | `cockpit2.py:2698` |
| `notif_read` | `cockpit2.py:2796` |
| `notif_processed` | `cockpit2.py:2801` |
| `notif_outcome` | `cockpit2.py:2948` |
| `notif_besluit` | `cockpit2.py:3035` |
| `notif_klaar` | `cockpit2.py:2934` |
| `notif_delete` | `cockpit2.py:2806` |
| `notif_add` | `cockpit2.py:2918` |
| `notif_archive` | `cockpit2.py:3077` |
| `metrics2_fav` | `cockpit2.py:2812` |
| `metrics2_unfav` | `cockpit2.py:2822` |
| `metrics2_form` | `cockpit2.py:2827` |
| `metrics2_dim` | `cockpit2.py:2833` |
| `metrics2_compare` | `cockpit2.py:2840` |
| `metrics2_formula` | `cockpit2.py:2903` |
| `source_activate` | `cockpit2.py:2886` |
| `source_deactivate` | `cockpit2.py:2895` |
| `link_pursue` | `cockpit2.py:2867` |
| `link_ignore` | `cockpit2.py:2877` |
| `acc_check` | `cockpit2.py:2848` |
| `ai_reply` | `cockpit2.py:1757` |
| `proj_feed` | `cockpit2.py:1768` |
| `checklist_add` | `cockpit2.py:1798` |
| `checklist_remove` | `cockpit2.py:1809` |
| `check_add` | `cockpit2.py:1857` |
| `check_accept` | `cockpit2.py:1874` |
| `check_toggle` | `cockpit2.py:1884` |
| `check_skip` | `cockpit2.py:1906` |
| `check_unskip` | `cockpit2.py:1918` |
| `check_handoff` | `cockpit2.py:1930` |
| `check_remove` | `cockpit2.py:1944` |
| `role_assign` | `cockpit2.py:1954` |
| `role_unassign` | `cockpit2.py:1972` |
| `role_focus` | `cockpit2.py:1991` |
| `radar_approve` | `cockpit2.py:2024` |
| `radar_dismiss` | `cockpit2.py:2034` |
| `radar_promote` | `cockpit2.py:2038` |
| `radar_merge` | `cockpit2.py:2058` |
| `radar_koppel` | `cockpit2.py:2074` |
| `kb_stage_koppel` | `cockpit2.py:2101` |
| `aitask_add` | `cockpit2.py:2139` |
| `aitask_remove` | `cockpit2.py:2170` |
| `skilllink_add` | `cockpit2.py:2198` |
| `means_gap_add` | `cockpit2.py:2228` |
| `persona_skill_add` | `cockpit2.py:2382` |
| `rov2_add` | `cockpit2.py:2397` |
| `rov2_add_to_group` | `cockpit2.py:2409` |
| `rov2_remove` | `cockpit2.py:2421` |
| `rov2_remove_group` | `cockpit2.py:2436` |
| `rov2_setkind` | `cockpit2.py:2454` |
| `rov2_consent` | `cockpit2.py:2467` |
| `rov2_end` | `cockpit2.py:2489` |
| `wo_open` | `cockpit2.py:2513` |
| `wo_close` | `cockpit2.py:2523` |
| `wo_presence` | `cockpit2.py:2539` |
| `wo_present_all` | `cockpit2.py:2550` |
| `wo_ag_add` | `cockpit2.py:2562` |
| `wo_ag_remove` | `cockpit2.py:2574` |
| `wo_ag_note` | `cockpit2.py:2584` |
| `wo_ag_reopen` | `cockpit2.py:2596` |
| `wo_ag_resolve` | `cockpit2.py:2672` |
| `wo_checkout` | `cockpit2.py:3082` |
| `noochie_send` | `cockpit2.py:3094` |
| `noochie_reset` | `cockpit2.py:3120` |
| `noochie_ctx` | `cockpit2.py:3127` |
| `cl_add` | `cockpit2.py:3134` |
| `cl_report` | `cockpit2.py:3152` |
| `cl_remove` | `cockpit2.py:3167` |
| `m_add_kpi` | `cockpit2.py:3177` |
| `m_add_from_def` | `cockpit2.py:3209` |
| `def_add` | `cockpit2.py:3224` |
| `catalog_publish` | `cockpit2.py:3246` |
| `def_amend` | `cockpit2.py:3272` |
| `m_add_link` | `cockpit2.py:3314` |
| `m_sample` | `cockpit2.py:3325` |
| `m_remove` | `cockpit2.py:3335` |
| `m_pin` | `cockpit2.py:3345` |
| `m_unpin` | `cockpit2.py:3356` |
| `tile_add` | `cockpit2.py:3394` |
| `indicator_activate` | `cockpit2.py:3366` |
| `tile_remove` | `cockpit2.py:3428` |
| `rov2_set` | `cockpit2.py:3438` |
| `rov2_acc_add` | `cockpit2.py:3438` |
| `rov2_acc_remove` | `cockpit2.py:3438` |
| `rov2_dom_add` | `cockpit2.py:3438` |
| `rov2_dom_remove` | `cockpit2.py:3438` |
| `backlog_add` | `cockpit2.py:3470` |
| `backlog_update_staat` | `cockpit2.py:3482` |
| `backlog_update_prioriteit` | `cockpit2.py:3494` |
| `person_edit` | `cockpit2.py:3506` |
| `person_remove` | `cockpit2.py:3523` |
| `lk_mute` | `cockpit2.py:3544` |
| `claims_term_add` | `cockpit2.py:3647` |
| `claims_term_retract` | `cockpit2.py:3684` |
| `claims_work_status` | `cockpit2.py:3668` |
| `claims_bewijs_link` | `cockpit2.py:3713` |
| `claims_vondst_whitelist` | `cockpit2.py:3737` |
| `claims_regel_uit_vondst` | `cockpit2.py:3763` |
| `claims_to_board` | `cockpit2.py:3795` |
| `persona_edit` | `cockpit2.py:2281` |
| `persona_llm` | `cockpit2.py:2300` |
| `persona_finetune` | `cockpit2.py:2317` |
| `persona_finetune_apply` | `cockpit2.py:2335` |


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
_54 routes · 181 dispatch-acties · 31 stores._
