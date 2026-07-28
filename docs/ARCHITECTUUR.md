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
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
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
| `kb_new` | `cockpit2.py:3682` |
| `kb_intake` | `cockpit2.py:3764` |
| `kb_intake_url` | `cockpit2.py:3781` |
| `kb_stage_edit` | `cockpit2.py:3800` |
| `kb_stage_accept` | `cockpit2.py:3812` |
| `kb_stage_delete` | `cockpit2.py:3831` |
| `kb_stage_merge` | `cockpit2.py:3837` |
| `kb_stage_commit` | `cockpit2.py:3848` |
| `kb_stage_discard` | `cockpit2.py:3868` |
| `kb_atoom_subject` | `cockpit2.py:3992` |
| `kb_atoom_purge` | `cockpit2.py:3976` |
| `tag_voorstel_besluit` | `cockpit2.py:3944` |
| `tag_onderhoud_run` | `cockpit2.py:3963` |
| `kb_blacklist_leeg` | `cockpit2.py:3985` |
| `kb_atoom_edit` | `cockpit2.py:3874` |
| `kb_atoom_related` | `cockpit2.py:3881` |
| `kb_atoom_reference` | `cockpit2.py:3926` |
| `kb_insight_link` | `cockpit2.py:3893` |
| `kb_insight_unlink` | `cockpit2.py:3900` |
| `kb_meta_start` | `cockpit2.py:3906` |
| `kb_atoom_merge` | `cockpit2.py:4003` |
| `kb_atoom_archive` | `cockpit2.py:4024` |
| `kb_atoom_unarchive` | `cockpit2.py:4033` |
| `kb_atoom_naar_spel` | `cockpit2.py:4039` |
| `kb_spel_start` | `cockpit2.py:4060` |
| `kb_spel_add` | `cockpit2.py:4074` |
| `kb_spel_remove` | `cockpit2.py:4084` |
| `kb_spel_flip` | `cockpit2.py:4091` |
| `kb_spel_finish` | `cockpit2.py:4097` |
| `kb_link` | `cockpit2.py:3691` |
| `kb_unlink` | `cockpit2.py:3705` |
| `kb_annotate` | `cockpit2.py:3716` |
| `kb_evidence` | `cockpit2.py:3722` |
| `kb_discuss` | `cockpit2.py:3743` |
| `kb_reformulate` | `cockpit2.py:3749` |
| `kw_nominate` | `cockpit2.py:4108` |
| `kw_nom_accept` | `cockpit2.py:4119` |
| `kw_nom_reject` | `cockpit2.py:4137` |
| `ws_forbid` | `cockpit2.py:4167` |
| `ws_approve` | `cockpit2.py:4172` |
| `proj_add` | `cockpit2.py:1130` |
| `artefact_add` | `cockpit2.py:1165` |
| `artefact_edit` | `cockpit2.py:1206` |
| `artefact_archive` | `cockpit2.py:1230` |
| `proj_status` | `cockpit2.py:1250` |
| `proj_done` | `cockpit2.py:1268` |
| `proj_dod` | `cockpit2.py:1312` |
| `proj_archive` | `cockpit2.py:1326` |
| `proj_unarchive` | `cockpit2.py:1349` |
| `proj_delete` | `cockpit2.py:1359` |
| `proj_edit` | `cockpit2.py:1386` |
| `proj_comment` | `cockpit2.py:1399` |
| `proj_rename` | `cockpit2.py:1409` |
| `proj_describe` | `cockpit2.py:1420` |
| `proj_doc_edit` | `cockpit2.py:1453` |
| `proj_regen_doc` | `cockpit2.py:1431` |
| `proj_settrekker` | `cockpit2.py:1466` |
| `proj_setowner` | `cockpit2.py:1503` |
| `proj_approve` | `cockpit2.py:1522` |
| `proj_discard` | `cockpit2.py:1533` |
| `proj_proposal_accept` | `cockpit2.py:1544` |
| `proj_proposal_reject` | `cockpit2.py:1557` |
| `proj_setlabel` | `cockpit2.py:1570` |
| `proj_setimpact` | `cockpit2.py:1585` |
| `proj_seteffort` | `cockpit2.py:1604` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1627` |
| `proj_setprivate` | `cockpit2.py:1651` |
| `proj_setdue` | `cockpit2.py:1662` |
| `attach_add` | `cockpit2.py:1673` |
| `attach_remove` | `cockpit2.py:1684` |
| `react_add` | `cockpit2.py:1694` |
| `feed_edit` | `cockpit2.py:1704` |
| `feed_remove` | `cockpit2.py:1714` |
| `wall_outcome` | `cockpit2.py:2614` |
| `notif_read` | `cockpit2.py:2712` |
| `notif_processed` | `cockpit2.py:2717` |
| `notif_outcome` | `cockpit2.py:2864` |
| `notif_besluit` | `cockpit2.py:2951` |
| `notif_klaar` | `cockpit2.py:2850` |
| `notif_delete` | `cockpit2.py:2722` |
| `notif_add` | `cockpit2.py:2834` |
| `notif_archive` | `cockpit2.py:2993` |
| `metrics2_fav` | `cockpit2.py:2728` |
| `metrics2_unfav` | `cockpit2.py:2738` |
| `metrics2_form` | `cockpit2.py:2743` |
| `metrics2_dim` | `cockpit2.py:2749` |
| `metrics2_compare` | `cockpit2.py:2756` |
| `metrics2_formula` | `cockpit2.py:2819` |
| `source_activate` | `cockpit2.py:2802` |
| `source_deactivate` | `cockpit2.py:2811` |
| `link_pursue` | `cockpit2.py:2783` |
| `link_ignore` | `cockpit2.py:2793` |
| `acc_check` | `cockpit2.py:2764` |
| `ai_reply` | `cockpit2.py:1723` |
| `proj_feed` | `cockpit2.py:1734` |
| `checklist_add` | `cockpit2.py:1764` |
| `checklist_remove` | `cockpit2.py:1775` |
| `check_add` | `cockpit2.py:1823` |
| `check_accept` | `cockpit2.py:1840` |
| `check_toggle` | `cockpit2.py:1850` |
| `check_remove` | `cockpit2.py:1860` |
| `role_assign` | `cockpit2.py:1870` |
| `role_unassign` | `cockpit2.py:1888` |
| `role_focus` | `cockpit2.py:1907` |
| `radar_approve` | `cockpit2.py:1940` |
| `radar_dismiss` | `cockpit2.py:1950` |
| `radar_promote` | `cockpit2.py:1954` |
| `radar_merge` | `cockpit2.py:1974` |
| `radar_koppel` | `cockpit2.py:1990` |
| `kb_stage_koppel` | `cockpit2.py:2017` |
| `aitask_add` | `cockpit2.py:2055` |
| `aitask_remove` | `cockpit2.py:2086` |
| `skilllink_add` | `cockpit2.py:2114` |
| `means_gap_add` | `cockpit2.py:2144` |
| `persona_skill_add` | `cockpit2.py:2298` |
| `rov2_add` | `cockpit2.py:2313` |
| `rov2_add_to_group` | `cockpit2.py:2325` |
| `rov2_remove` | `cockpit2.py:2337` |
| `rov2_remove_group` | `cockpit2.py:2352` |
| `rov2_setkind` | `cockpit2.py:2370` |
| `rov2_consent` | `cockpit2.py:2383` |
| `rov2_end` | `cockpit2.py:2405` |
| `wo_open` | `cockpit2.py:2429` |
| `wo_close` | `cockpit2.py:2439` |
| `wo_presence` | `cockpit2.py:2455` |
| `wo_present_all` | `cockpit2.py:2466` |
| `wo_ag_add` | `cockpit2.py:2478` |
| `wo_ag_remove` | `cockpit2.py:2490` |
| `wo_ag_note` | `cockpit2.py:2500` |
| `wo_ag_reopen` | `cockpit2.py:2512` |
| `wo_ag_resolve` | `cockpit2.py:2588` |
| `wo_checkout` | `cockpit2.py:2998` |
| `noochie_send` | `cockpit2.py:3010` |
| `noochie_reset` | `cockpit2.py:3036` |
| `noochie_ctx` | `cockpit2.py:3043` |
| `cl_add` | `cockpit2.py:3050` |
| `cl_report` | `cockpit2.py:3068` |
| `cl_remove` | `cockpit2.py:3083` |
| `m_add_kpi` | `cockpit2.py:3093` |
| `m_add_from_def` | `cockpit2.py:3125` |
| `def_add` | `cockpit2.py:3140` |
| `catalog_publish` | `cockpit2.py:3162` |
| `def_amend` | `cockpit2.py:3188` |
| `m_add_link` | `cockpit2.py:3230` |
| `m_sample` | `cockpit2.py:3241` |
| `m_remove` | `cockpit2.py:3251` |
| `m_pin` | `cockpit2.py:3261` |
| `m_unpin` | `cockpit2.py:3272` |
| `tile_add` | `cockpit2.py:3310` |
| `indicator_activate` | `cockpit2.py:3282` |
| `tile_remove` | `cockpit2.py:3344` |
| `rov2_set` | `cockpit2.py:3354` |
| `rov2_acc_add` | `cockpit2.py:3354` |
| `rov2_acc_remove` | `cockpit2.py:3354` |
| `rov2_dom_add` | `cockpit2.py:3354` |
| `rov2_dom_remove` | `cockpit2.py:3354` |
| `backlog_add` | `cockpit2.py:3386` |
| `backlog_update_staat` | `cockpit2.py:3398` |
| `backlog_update_prioriteit` | `cockpit2.py:3410` |
| `person_edit` | `cockpit2.py:3422` |
| `person_remove` | `cockpit2.py:3439` |
| `lk_mute` | `cockpit2.py:3460` |
| `claims_term_add` | `cockpit2.py:3563` |
| `claims_term_retract` | `cockpit2.py:3600` |
| `claims_work_status` | `cockpit2.py:3584` |
| `claims_to_board` | `cockpit2.py:3618` |
| `persona_edit` | `cockpit2.py:2197` |
| `persona_llm` | `cockpit2.py:2216` |
| `persona_finetune` | `cockpit2.py:2233` |
| `persona_finetune_apply` | `cockpit2.py:2251` |


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
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `notes` | `NotesStore` | `notes.json` |
| `spel` | `SpelStore` | `kennisbank_spel.json` |
| `staging` | `StagingStore` | `kennisbank_staging.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


---
_51 routes · 170 dispatch-acties · 30 stores._
