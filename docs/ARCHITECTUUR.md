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
| `ff_beslis` | `cockpit2.py:4351` |
| `ff_cluster` | `cockpit2.py:4479` |
| `ff_promote` | `cockpit2.py:4409` |
| `ff_demote` | `cockpit2.py:4433` |
| `ff_run` | `cockpit2.py:4452` |
| `kb_new` | `cockpit2.py:3845` |
| `kb_intake` | `cockpit2.py:3927` |
| `kb_intake_url` | `cockpit2.py:3944` |
| `kb_stage_edit` | `cockpit2.py:3963` |
| `kb_stage_accept` | `cockpit2.py:3975` |
| `kb_stage_delete` | `cockpit2.py:3994` |
| `kb_stage_merge` | `cockpit2.py:4000` |
| `kb_stage_commit` | `cockpit2.py:4011` |
| `kb_stage_discard` | `cockpit2.py:4031` |
| `kb_atoom_subject` | `cockpit2.py:4155` |
| `kb_atoom_purge` | `cockpit2.py:4139` |
| `tag_voorstel_besluit` | `cockpit2.py:4107` |
| `tag_onderhoud_run` | `cockpit2.py:4126` |
| `kb_blacklist_leeg` | `cockpit2.py:4148` |
| `kb_atoom_edit` | `cockpit2.py:4037` |
| `kb_atoom_related` | `cockpit2.py:4044` |
| `kb_atoom_reference` | `cockpit2.py:4089` |
| `kb_insight_link` | `cockpit2.py:4056` |
| `kb_insight_unlink` | `cockpit2.py:4063` |
| `kb_meta_start` | `cockpit2.py:4069` |
| `kb_atoom_merge` | `cockpit2.py:4166` |
| `kb_atoom_archive` | `cockpit2.py:4187` |
| `kb_atoom_unarchive` | `cockpit2.py:4196` |
| `kb_atoom_naar_spel` | `cockpit2.py:4202` |
| `kb_spel_start` | `cockpit2.py:4223` |
| `kb_spel_add` | `cockpit2.py:4237` |
| `kb_spel_remove` | `cockpit2.py:4247` |
| `kb_spel_flip` | `cockpit2.py:4254` |
| `kb_spel_finish` | `cockpit2.py:4260` |
| `kb_link` | `cockpit2.py:3854` |
| `kb_unlink` | `cockpit2.py:3868` |
| `kb_annotate` | `cockpit2.py:3879` |
| `kb_evidence` | `cockpit2.py:3885` |
| `kb_discuss` | `cockpit2.py:3906` |
| `kb_reformulate` | `cockpit2.py:3912` |
| `kw_nominate` | `cockpit2.py:4271` |
| `kw_nom_accept` | `cockpit2.py:4282` |
| `kw_nom_reject` | `cockpit2.py:4300` |
| `ws_forbid` | `cockpit2.py:4330` |
| `ws_approve` | `cockpit2.py:4335` |
| `proj_add` | `cockpit2.py:1145` |
| `artefact_add` | `cockpit2.py:1180` |
| `artefact_edit` | `cockpit2.py:1221` |
| `artefact_archive` | `cockpit2.py:1245` |
| `proj_status` | `cockpit2.py:1265` |
| `proj_done` | `cockpit2.py:1283` |
| `proj_dod` | `cockpit2.py:1332` |
| `proj_archive` | `cockpit2.py:1346` |
| `proj_unarchive` | `cockpit2.py:1369` |
| `proj_delete` | `cockpit2.py:1379` |
| `proj_edit` | `cockpit2.py:1406` |
| `proj_comment` | `cockpit2.py:1419` |
| `proj_rename` | `cockpit2.py:1429` |
| `proj_describe` | `cockpit2.py:1440` |
| `proj_doc_edit` | `cockpit2.py:1473` |
| `proj_regen_doc` | `cockpit2.py:1451` |
| `proj_settrekker` | `cockpit2.py:1486` |
| `proj_setowner` | `cockpit2.py:1523` |
| `proj_approve` | `cockpit2.py:1542` |
| `proj_discard` | `cockpit2.py:1553` |
| `proj_proposal_accept` | `cockpit2.py:1564` |
| `proj_proposal_reject` | `cockpit2.py:1577` |
| `proj_setlabel` | `cockpit2.py:1590` |
| `proj_setimpact` | `cockpit2.py:1605` |
| `proj_seteffort` | `cockpit2.py:1624` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1647` |
| `proj_setprivate` | `cockpit2.py:1671` |
| `proj_setdue` | `cockpit2.py:1682` |
| `attach_add` | `cockpit2.py:1693` |
| `attach_remove` | `cockpit2.py:1704` |
| `react_add` | `cockpit2.py:1714` |
| `feed_edit` | `cockpit2.py:1724` |
| `feed_remove` | `cockpit2.py:1734` |
| `wall_outcome` | `cockpit2.py:2684` |
| `notif_read` | `cockpit2.py:2782` |
| `notif_processed` | `cockpit2.py:2787` |
| `notif_outcome` | `cockpit2.py:2934` |
| `notif_besluit` | `cockpit2.py:3021` |
| `notif_klaar` | `cockpit2.py:2920` |
| `notif_delete` | `cockpit2.py:2792` |
| `notif_add` | `cockpit2.py:2904` |
| `notif_archive` | `cockpit2.py:3063` |
| `metrics2_fav` | `cockpit2.py:2798` |
| `metrics2_unfav` | `cockpit2.py:2808` |
| `metrics2_form` | `cockpit2.py:2813` |
| `metrics2_dim` | `cockpit2.py:2819` |
| `metrics2_compare` | `cockpit2.py:2826` |
| `metrics2_formula` | `cockpit2.py:2889` |
| `source_activate` | `cockpit2.py:2872` |
| `source_deactivate` | `cockpit2.py:2881` |
| `link_pursue` | `cockpit2.py:2853` |
| `link_ignore` | `cockpit2.py:2863` |
| `acc_check` | `cockpit2.py:2834` |
| `ai_reply` | `cockpit2.py:1743` |
| `proj_feed` | `cockpit2.py:1754` |
| `checklist_add` | `cockpit2.py:1784` |
| `checklist_remove` | `cockpit2.py:1795` |
| `check_add` | `cockpit2.py:1843` |
| `check_accept` | `cockpit2.py:1860` |
| `check_toggle` | `cockpit2.py:1870` |
| `check_skip` | `cockpit2.py:1892` |
| `check_unskip` | `cockpit2.py:1904` |
| `check_handoff` | `cockpit2.py:1916` |
| `check_remove` | `cockpit2.py:1930` |
| `role_assign` | `cockpit2.py:1940` |
| `role_unassign` | `cockpit2.py:1958` |
| `role_focus` | `cockpit2.py:1977` |
| `radar_approve` | `cockpit2.py:2010` |
| `radar_dismiss` | `cockpit2.py:2020` |
| `radar_promote` | `cockpit2.py:2024` |
| `radar_merge` | `cockpit2.py:2044` |
| `radar_koppel` | `cockpit2.py:2060` |
| `kb_stage_koppel` | `cockpit2.py:2087` |
| `aitask_add` | `cockpit2.py:2125` |
| `aitask_remove` | `cockpit2.py:2156` |
| `skilllink_add` | `cockpit2.py:2184` |
| `means_gap_add` | `cockpit2.py:2214` |
| `persona_skill_add` | `cockpit2.py:2368` |
| `rov2_add` | `cockpit2.py:2383` |
| `rov2_add_to_group` | `cockpit2.py:2395` |
| `rov2_remove` | `cockpit2.py:2407` |
| `rov2_remove_group` | `cockpit2.py:2422` |
| `rov2_setkind` | `cockpit2.py:2440` |
| `rov2_consent` | `cockpit2.py:2453` |
| `rov2_end` | `cockpit2.py:2475` |
| `wo_open` | `cockpit2.py:2499` |
| `wo_close` | `cockpit2.py:2509` |
| `wo_presence` | `cockpit2.py:2525` |
| `wo_present_all` | `cockpit2.py:2536` |
| `wo_ag_add` | `cockpit2.py:2548` |
| `wo_ag_remove` | `cockpit2.py:2560` |
| `wo_ag_note` | `cockpit2.py:2570` |
| `wo_ag_reopen` | `cockpit2.py:2582` |
| `wo_ag_resolve` | `cockpit2.py:2658` |
| `wo_checkout` | `cockpit2.py:3068` |
| `noochie_send` | `cockpit2.py:3080` |
| `noochie_reset` | `cockpit2.py:3106` |
| `noochie_ctx` | `cockpit2.py:3113` |
| `cl_add` | `cockpit2.py:3120` |
| `cl_report` | `cockpit2.py:3138` |
| `cl_remove` | `cockpit2.py:3153` |
| `m_add_kpi` | `cockpit2.py:3163` |
| `m_add_from_def` | `cockpit2.py:3195` |
| `def_add` | `cockpit2.py:3210` |
| `catalog_publish` | `cockpit2.py:3232` |
| `def_amend` | `cockpit2.py:3258` |
| `m_add_link` | `cockpit2.py:3300` |
| `m_sample` | `cockpit2.py:3311` |
| `m_remove` | `cockpit2.py:3321` |
| `m_pin` | `cockpit2.py:3331` |
| `m_unpin` | `cockpit2.py:3342` |
| `tile_add` | `cockpit2.py:3380` |
| `indicator_activate` | `cockpit2.py:3352` |
| `tile_remove` | `cockpit2.py:3414` |
| `rov2_set` | `cockpit2.py:3424` |
| `rov2_acc_add` | `cockpit2.py:3424` |
| `rov2_acc_remove` | `cockpit2.py:3424` |
| `rov2_dom_add` | `cockpit2.py:3424` |
| `rov2_dom_remove` | `cockpit2.py:3424` |
| `backlog_add` | `cockpit2.py:3456` |
| `backlog_update_staat` | `cockpit2.py:3468` |
| `backlog_update_prioriteit` | `cockpit2.py:3480` |
| `person_edit` | `cockpit2.py:3492` |
| `person_remove` | `cockpit2.py:3509` |
| `lk_mute` | `cockpit2.py:3530` |
| `claims_term_add` | `cockpit2.py:3633` |
| `claims_term_retract` | `cockpit2.py:3670` |
| `claims_work_status` | `cockpit2.py:3654` |
| `claims_bewijs_link` | `cockpit2.py:3699` |
| `claims_vondst_whitelist` | `cockpit2.py:3723` |
| `claims_regel_uit_vondst` | `cockpit2.py:3749` |
| `claims_to_board` | `cockpit2.py:3781` |
| `persona_edit` | `cockpit2.py:2267` |
| `persona_llm` | `cockpit2.py:2286` |
| `persona_finetune` | `cockpit2.py:2303` |
| `persona_finetune_apply` | `cockpit2.py:2321` |


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
