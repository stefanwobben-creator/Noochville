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
| `ff_beslis` | `cockpit2.py:4350` |
| `ff_cluster` | `cockpit2.py:4478` |
| `ff_promote` | `cockpit2.py:4408` |
| `ff_demote` | `cockpit2.py:4432` |
| `ff_run` | `cockpit2.py:4451` |
| `kb_new` | `cockpit2.py:3844` |
| `kb_intake` | `cockpit2.py:3926` |
| `kb_intake_url` | `cockpit2.py:3943` |
| `kb_stage_edit` | `cockpit2.py:3962` |
| `kb_stage_accept` | `cockpit2.py:3974` |
| `kb_stage_delete` | `cockpit2.py:3993` |
| `kb_stage_merge` | `cockpit2.py:3999` |
| `kb_stage_commit` | `cockpit2.py:4010` |
| `kb_stage_discard` | `cockpit2.py:4030` |
| `kb_atoom_subject` | `cockpit2.py:4154` |
| `kb_atoom_purge` | `cockpit2.py:4138` |
| `tag_voorstel_besluit` | `cockpit2.py:4106` |
| `tag_onderhoud_run` | `cockpit2.py:4125` |
| `kb_blacklist_leeg` | `cockpit2.py:4147` |
| `kb_atoom_edit` | `cockpit2.py:4036` |
| `kb_atoom_related` | `cockpit2.py:4043` |
| `kb_atoom_reference` | `cockpit2.py:4088` |
| `kb_insight_link` | `cockpit2.py:4055` |
| `kb_insight_unlink` | `cockpit2.py:4062` |
| `kb_meta_start` | `cockpit2.py:4068` |
| `kb_atoom_merge` | `cockpit2.py:4165` |
| `kb_atoom_archive` | `cockpit2.py:4186` |
| `kb_atoom_unarchive` | `cockpit2.py:4195` |
| `kb_atoom_naar_spel` | `cockpit2.py:4201` |
| `kb_spel_start` | `cockpit2.py:4222` |
| `kb_spel_add` | `cockpit2.py:4236` |
| `kb_spel_remove` | `cockpit2.py:4246` |
| `kb_spel_flip` | `cockpit2.py:4253` |
| `kb_spel_finish` | `cockpit2.py:4259` |
| `kb_link` | `cockpit2.py:3853` |
| `kb_unlink` | `cockpit2.py:3867` |
| `kb_annotate` | `cockpit2.py:3878` |
| `kb_evidence` | `cockpit2.py:3884` |
| `kb_discuss` | `cockpit2.py:3905` |
| `kb_reformulate` | `cockpit2.py:3911` |
| `kw_nominate` | `cockpit2.py:4270` |
| `kw_nom_accept` | `cockpit2.py:4281` |
| `kw_nom_reject` | `cockpit2.py:4299` |
| `ws_forbid` | `cockpit2.py:4329` |
| `ws_approve` | `cockpit2.py:4334` |
| `proj_add` | `cockpit2.py:1144` |
| `artefact_add` | `cockpit2.py:1179` |
| `artefact_edit` | `cockpit2.py:1220` |
| `artefact_archive` | `cockpit2.py:1244` |
| `proj_status` | `cockpit2.py:1264` |
| `proj_done` | `cockpit2.py:1282` |
| `proj_dod` | `cockpit2.py:1331` |
| `proj_archive` | `cockpit2.py:1345` |
| `proj_unarchive` | `cockpit2.py:1368` |
| `proj_delete` | `cockpit2.py:1378` |
| `proj_edit` | `cockpit2.py:1405` |
| `proj_comment` | `cockpit2.py:1418` |
| `proj_rename` | `cockpit2.py:1428` |
| `proj_describe` | `cockpit2.py:1439` |
| `proj_doc_edit` | `cockpit2.py:1472` |
| `proj_regen_doc` | `cockpit2.py:1450` |
| `proj_settrekker` | `cockpit2.py:1485` |
| `proj_setowner` | `cockpit2.py:1522` |
| `proj_approve` | `cockpit2.py:1541` |
| `proj_discard` | `cockpit2.py:1552` |
| `proj_proposal_accept` | `cockpit2.py:1563` |
| `proj_proposal_reject` | `cockpit2.py:1576` |
| `proj_setlabel` | `cockpit2.py:1589` |
| `proj_setimpact` | `cockpit2.py:1604` |
| `proj_seteffort` | `cockpit2.py:1623` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1646` |
| `proj_setprivate` | `cockpit2.py:1670` |
| `proj_setdue` | `cockpit2.py:1681` |
| `attach_add` | `cockpit2.py:1692` |
| `attach_remove` | `cockpit2.py:1703` |
| `react_add` | `cockpit2.py:1713` |
| `feed_edit` | `cockpit2.py:1723` |
| `feed_remove` | `cockpit2.py:1733` |
| `wall_outcome` | `cockpit2.py:2683` |
| `notif_read` | `cockpit2.py:2781` |
| `notif_processed` | `cockpit2.py:2786` |
| `notif_outcome` | `cockpit2.py:2933` |
| `notif_besluit` | `cockpit2.py:3020` |
| `notif_klaar` | `cockpit2.py:2919` |
| `notif_delete` | `cockpit2.py:2791` |
| `notif_add` | `cockpit2.py:2903` |
| `notif_archive` | `cockpit2.py:3062` |
| `metrics2_fav` | `cockpit2.py:2797` |
| `metrics2_unfav` | `cockpit2.py:2807` |
| `metrics2_form` | `cockpit2.py:2812` |
| `metrics2_dim` | `cockpit2.py:2818` |
| `metrics2_compare` | `cockpit2.py:2825` |
| `metrics2_formula` | `cockpit2.py:2888` |
| `source_activate` | `cockpit2.py:2871` |
| `source_deactivate` | `cockpit2.py:2880` |
| `link_pursue` | `cockpit2.py:2852` |
| `link_ignore` | `cockpit2.py:2862` |
| `acc_check` | `cockpit2.py:2833` |
| `ai_reply` | `cockpit2.py:1742` |
| `proj_feed` | `cockpit2.py:1753` |
| `checklist_add` | `cockpit2.py:1783` |
| `checklist_remove` | `cockpit2.py:1794` |
| `check_add` | `cockpit2.py:1842` |
| `check_accept` | `cockpit2.py:1859` |
| `check_toggle` | `cockpit2.py:1869` |
| `check_skip` | `cockpit2.py:1891` |
| `check_unskip` | `cockpit2.py:1903` |
| `check_handoff` | `cockpit2.py:1915` |
| `check_remove` | `cockpit2.py:1929` |
| `role_assign` | `cockpit2.py:1939` |
| `role_unassign` | `cockpit2.py:1957` |
| `role_focus` | `cockpit2.py:1976` |
| `radar_approve` | `cockpit2.py:2009` |
| `radar_dismiss` | `cockpit2.py:2019` |
| `radar_promote` | `cockpit2.py:2023` |
| `radar_merge` | `cockpit2.py:2043` |
| `radar_koppel` | `cockpit2.py:2059` |
| `kb_stage_koppel` | `cockpit2.py:2086` |
| `aitask_add` | `cockpit2.py:2124` |
| `aitask_remove` | `cockpit2.py:2155` |
| `skilllink_add` | `cockpit2.py:2183` |
| `means_gap_add` | `cockpit2.py:2213` |
| `persona_skill_add` | `cockpit2.py:2367` |
| `rov2_add` | `cockpit2.py:2382` |
| `rov2_add_to_group` | `cockpit2.py:2394` |
| `rov2_remove` | `cockpit2.py:2406` |
| `rov2_remove_group` | `cockpit2.py:2421` |
| `rov2_setkind` | `cockpit2.py:2439` |
| `rov2_consent` | `cockpit2.py:2452` |
| `rov2_end` | `cockpit2.py:2474` |
| `wo_open` | `cockpit2.py:2498` |
| `wo_close` | `cockpit2.py:2508` |
| `wo_presence` | `cockpit2.py:2524` |
| `wo_present_all` | `cockpit2.py:2535` |
| `wo_ag_add` | `cockpit2.py:2547` |
| `wo_ag_remove` | `cockpit2.py:2559` |
| `wo_ag_note` | `cockpit2.py:2569` |
| `wo_ag_reopen` | `cockpit2.py:2581` |
| `wo_ag_resolve` | `cockpit2.py:2657` |
| `wo_checkout` | `cockpit2.py:3067` |
| `noochie_send` | `cockpit2.py:3079` |
| `noochie_reset` | `cockpit2.py:3105` |
| `noochie_ctx` | `cockpit2.py:3112` |
| `cl_add` | `cockpit2.py:3119` |
| `cl_report` | `cockpit2.py:3137` |
| `cl_remove` | `cockpit2.py:3152` |
| `m_add_kpi` | `cockpit2.py:3162` |
| `m_add_from_def` | `cockpit2.py:3194` |
| `def_add` | `cockpit2.py:3209` |
| `catalog_publish` | `cockpit2.py:3231` |
| `def_amend` | `cockpit2.py:3257` |
| `m_add_link` | `cockpit2.py:3299` |
| `m_sample` | `cockpit2.py:3310` |
| `m_remove` | `cockpit2.py:3320` |
| `m_pin` | `cockpit2.py:3330` |
| `m_unpin` | `cockpit2.py:3341` |
| `tile_add` | `cockpit2.py:3379` |
| `indicator_activate` | `cockpit2.py:3351` |
| `tile_remove` | `cockpit2.py:3413` |
| `rov2_set` | `cockpit2.py:3423` |
| `rov2_acc_add` | `cockpit2.py:3423` |
| `rov2_acc_remove` | `cockpit2.py:3423` |
| `rov2_dom_add` | `cockpit2.py:3423` |
| `rov2_dom_remove` | `cockpit2.py:3423` |
| `backlog_add` | `cockpit2.py:3455` |
| `backlog_update_staat` | `cockpit2.py:3467` |
| `backlog_update_prioriteit` | `cockpit2.py:3479` |
| `person_edit` | `cockpit2.py:3491` |
| `person_remove` | `cockpit2.py:3508` |
| `lk_mute` | `cockpit2.py:3529` |
| `claims_term_add` | `cockpit2.py:3632` |
| `claims_term_retract` | `cockpit2.py:3669` |
| `claims_work_status` | `cockpit2.py:3653` |
| `claims_bewijs_link` | `cockpit2.py:3698` |
| `claims_vondst_whitelist` | `cockpit2.py:3722` |
| `claims_regel_uit_vondst` | `cockpit2.py:3748` |
| `claims_to_board` | `cockpit2.py:3780` |
| `persona_edit` | `cockpit2.py:2266` |
| `persona_llm` | `cockpit2.py:2285` |
| `persona_finetune` | `cockpit2.py:2302` |
| `persona_finetune_apply` | `cockpit2.py:2320` |


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
