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
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `ff_beslis` | `cockpit2.py:4343` |
| `ff_cluster` | `cockpit2.py:4471` |
| `ff_promote` | `cockpit2.py:4401` |
| `ff_demote` | `cockpit2.py:4425` |
| `ff_run` | `cockpit2.py:4444` |
| `kb_new` | `cockpit2.py:3837` |
| `kb_intake` | `cockpit2.py:3919` |
| `kb_intake_url` | `cockpit2.py:3936` |
| `kb_stage_edit` | `cockpit2.py:3955` |
| `kb_stage_accept` | `cockpit2.py:3967` |
| `kb_stage_delete` | `cockpit2.py:3986` |
| `kb_stage_merge` | `cockpit2.py:3992` |
| `kb_stage_commit` | `cockpit2.py:4003` |
| `kb_stage_discard` | `cockpit2.py:4023` |
| `kb_atoom_subject` | `cockpit2.py:4147` |
| `kb_atoom_purge` | `cockpit2.py:4131` |
| `tag_voorstel_besluit` | `cockpit2.py:4099` |
| `tag_onderhoud_run` | `cockpit2.py:4118` |
| `kb_blacklist_leeg` | `cockpit2.py:4140` |
| `kb_atoom_edit` | `cockpit2.py:4029` |
| `kb_atoom_related` | `cockpit2.py:4036` |
| `kb_atoom_reference` | `cockpit2.py:4081` |
| `kb_insight_link` | `cockpit2.py:4048` |
| `kb_insight_unlink` | `cockpit2.py:4055` |
| `kb_meta_start` | `cockpit2.py:4061` |
| `kb_atoom_merge` | `cockpit2.py:4158` |
| `kb_atoom_archive` | `cockpit2.py:4179` |
| `kb_atoom_unarchive` | `cockpit2.py:4188` |
| `kb_atoom_naar_spel` | `cockpit2.py:4194` |
| `kb_spel_start` | `cockpit2.py:4215` |
| `kb_spel_add` | `cockpit2.py:4229` |
| `kb_spel_remove` | `cockpit2.py:4239` |
| `kb_spel_flip` | `cockpit2.py:4246` |
| `kb_spel_finish` | `cockpit2.py:4252` |
| `kb_link` | `cockpit2.py:3846` |
| `kb_unlink` | `cockpit2.py:3860` |
| `kb_annotate` | `cockpit2.py:3871` |
| `kb_evidence` | `cockpit2.py:3877` |
| `kb_discuss` | `cockpit2.py:3898` |
| `kb_reformulate` | `cockpit2.py:3904` |
| `kw_nominate` | `cockpit2.py:4263` |
| `kw_nom_accept` | `cockpit2.py:4274` |
| `kw_nom_reject` | `cockpit2.py:4292` |
| `ws_forbid` | `cockpit2.py:4322` |
| `ws_approve` | `cockpit2.py:4327` |
| `proj_add` | `cockpit2.py:1137` |
| `artefact_add` | `cockpit2.py:1172` |
| `artefact_edit` | `cockpit2.py:1213` |
| `artefact_archive` | `cockpit2.py:1237` |
| `proj_status` | `cockpit2.py:1257` |
| `proj_done` | `cockpit2.py:1275` |
| `proj_dod` | `cockpit2.py:1324` |
| `proj_archive` | `cockpit2.py:1338` |
| `proj_unarchive` | `cockpit2.py:1361` |
| `proj_delete` | `cockpit2.py:1371` |
| `proj_edit` | `cockpit2.py:1398` |
| `proj_comment` | `cockpit2.py:1411` |
| `proj_rename` | `cockpit2.py:1421` |
| `proj_describe` | `cockpit2.py:1432` |
| `proj_doc_edit` | `cockpit2.py:1465` |
| `proj_regen_doc` | `cockpit2.py:1443` |
| `proj_settrekker` | `cockpit2.py:1478` |
| `proj_setowner` | `cockpit2.py:1515` |
| `proj_approve` | `cockpit2.py:1534` |
| `proj_discard` | `cockpit2.py:1545` |
| `proj_proposal_accept` | `cockpit2.py:1556` |
| `proj_proposal_reject` | `cockpit2.py:1569` |
| `proj_setlabel` | `cockpit2.py:1582` |
| `proj_setimpact` | `cockpit2.py:1597` |
| `proj_seteffort` | `cockpit2.py:1616` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1639` |
| `proj_setprivate` | `cockpit2.py:1663` |
| `proj_setdue` | `cockpit2.py:1674` |
| `attach_add` | `cockpit2.py:1685` |
| `attach_remove` | `cockpit2.py:1696` |
| `react_add` | `cockpit2.py:1706` |
| `feed_edit` | `cockpit2.py:1716` |
| `feed_remove` | `cockpit2.py:1726` |
| `wall_outcome` | `cockpit2.py:2676` |
| `notif_read` | `cockpit2.py:2774` |
| `notif_processed` | `cockpit2.py:2779` |
| `notif_outcome` | `cockpit2.py:2926` |
| `notif_besluit` | `cockpit2.py:3013` |
| `notif_klaar` | `cockpit2.py:2912` |
| `notif_delete` | `cockpit2.py:2784` |
| `notif_add` | `cockpit2.py:2896` |
| `notif_archive` | `cockpit2.py:3055` |
| `metrics2_fav` | `cockpit2.py:2790` |
| `metrics2_unfav` | `cockpit2.py:2800` |
| `metrics2_form` | `cockpit2.py:2805` |
| `metrics2_dim` | `cockpit2.py:2811` |
| `metrics2_compare` | `cockpit2.py:2818` |
| `metrics2_formula` | `cockpit2.py:2881` |
| `source_activate` | `cockpit2.py:2864` |
| `source_deactivate` | `cockpit2.py:2873` |
| `link_pursue` | `cockpit2.py:2845` |
| `link_ignore` | `cockpit2.py:2855` |
| `acc_check` | `cockpit2.py:2826` |
| `ai_reply` | `cockpit2.py:1735` |
| `proj_feed` | `cockpit2.py:1746` |
| `checklist_add` | `cockpit2.py:1776` |
| `checklist_remove` | `cockpit2.py:1787` |
| `check_add` | `cockpit2.py:1835` |
| `check_accept` | `cockpit2.py:1852` |
| `check_toggle` | `cockpit2.py:1862` |
| `check_skip` | `cockpit2.py:1884` |
| `check_unskip` | `cockpit2.py:1896` |
| `check_handoff` | `cockpit2.py:1908` |
| `check_remove` | `cockpit2.py:1922` |
| `role_assign` | `cockpit2.py:1932` |
| `role_unassign` | `cockpit2.py:1950` |
| `role_focus` | `cockpit2.py:1969` |
| `radar_approve` | `cockpit2.py:2002` |
| `radar_dismiss` | `cockpit2.py:2012` |
| `radar_promote` | `cockpit2.py:2016` |
| `radar_merge` | `cockpit2.py:2036` |
| `radar_koppel` | `cockpit2.py:2052` |
| `kb_stage_koppel` | `cockpit2.py:2079` |
| `aitask_add` | `cockpit2.py:2117` |
| `aitask_remove` | `cockpit2.py:2148` |
| `skilllink_add` | `cockpit2.py:2176` |
| `means_gap_add` | `cockpit2.py:2206` |
| `persona_skill_add` | `cockpit2.py:2360` |
| `rov2_add` | `cockpit2.py:2375` |
| `rov2_add_to_group` | `cockpit2.py:2387` |
| `rov2_remove` | `cockpit2.py:2399` |
| `rov2_remove_group` | `cockpit2.py:2414` |
| `rov2_setkind` | `cockpit2.py:2432` |
| `rov2_consent` | `cockpit2.py:2445` |
| `rov2_end` | `cockpit2.py:2467` |
| `wo_open` | `cockpit2.py:2491` |
| `wo_close` | `cockpit2.py:2501` |
| `wo_presence` | `cockpit2.py:2517` |
| `wo_present_all` | `cockpit2.py:2528` |
| `wo_ag_add` | `cockpit2.py:2540` |
| `wo_ag_remove` | `cockpit2.py:2552` |
| `wo_ag_note` | `cockpit2.py:2562` |
| `wo_ag_reopen` | `cockpit2.py:2574` |
| `wo_ag_resolve` | `cockpit2.py:2650` |
| `wo_checkout` | `cockpit2.py:3060` |
| `noochie_send` | `cockpit2.py:3072` |
| `noochie_reset` | `cockpit2.py:3098` |
| `noochie_ctx` | `cockpit2.py:3105` |
| `cl_add` | `cockpit2.py:3112` |
| `cl_report` | `cockpit2.py:3130` |
| `cl_remove` | `cockpit2.py:3145` |
| `m_add_kpi` | `cockpit2.py:3155` |
| `m_add_from_def` | `cockpit2.py:3187` |
| `def_add` | `cockpit2.py:3202` |
| `catalog_publish` | `cockpit2.py:3224` |
| `def_amend` | `cockpit2.py:3250` |
| `m_add_link` | `cockpit2.py:3292` |
| `m_sample` | `cockpit2.py:3303` |
| `m_remove` | `cockpit2.py:3313` |
| `m_pin` | `cockpit2.py:3323` |
| `m_unpin` | `cockpit2.py:3334` |
| `tile_add` | `cockpit2.py:3372` |
| `indicator_activate` | `cockpit2.py:3344` |
| `tile_remove` | `cockpit2.py:3406` |
| `rov2_set` | `cockpit2.py:3416` |
| `rov2_acc_add` | `cockpit2.py:3416` |
| `rov2_acc_remove` | `cockpit2.py:3416` |
| `rov2_dom_add` | `cockpit2.py:3416` |
| `rov2_dom_remove` | `cockpit2.py:3416` |
| `backlog_add` | `cockpit2.py:3448` |
| `backlog_update_staat` | `cockpit2.py:3460` |
| `backlog_update_prioriteit` | `cockpit2.py:3472` |
| `person_edit` | `cockpit2.py:3484` |
| `person_remove` | `cockpit2.py:3501` |
| `lk_mute` | `cockpit2.py:3522` |
| `claims_term_add` | `cockpit2.py:3625` |
| `claims_term_retract` | `cockpit2.py:3662` |
| `claims_work_status` | `cockpit2.py:3646` |
| `claims_bewijs_link` | `cockpit2.py:3691` |
| `claims_vondst_whitelist` | `cockpit2.py:3715` |
| `claims_regel_uit_vondst` | `cockpit2.py:3741` |
| `claims_to_board` | `cockpit2.py:3773` |
| `persona_edit` | `cockpit2.py:2259` |
| `persona_llm` | `cockpit2.py:2278` |
| `persona_finetune` | `cockpit2.py:2295` |
| `persona_finetune_apply` | `cockpit2.py:2313` |


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
_53 routes · 181 dispatch-acties · 31 stores._
