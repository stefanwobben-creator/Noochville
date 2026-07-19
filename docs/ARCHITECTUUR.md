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
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
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
| `kb_new` | `cockpit2.py:3555` |
| `kb_intake` | `cockpit2.py:3637` |
| `kb_intake_url` | `cockpit2.py:3654` |
| `kb_stage_edit` | `cockpit2.py:3673` |
| `kb_stage_accept` | `cockpit2.py:3685` |
| `kb_stage_delete` | `cockpit2.py:3704` |
| `kb_stage_merge` | `cockpit2.py:3710` |
| `kb_stage_commit` | `cockpit2.py:3721` |
| `kb_stage_discard` | `cockpit2.py:3741` |
| `kb_atoom_subject` | `cockpit2.py:3865` |
| `kb_atoom_purge` | `cockpit2.py:3849` |
| `tag_voorstel_besluit` | `cockpit2.py:3817` |
| `tag_onderhoud_run` | `cockpit2.py:3836` |
| `kb_blacklist_leeg` | `cockpit2.py:3858` |
| `kb_atoom_edit` | `cockpit2.py:3747` |
| `kb_atoom_related` | `cockpit2.py:3754` |
| `kb_atoom_reference` | `cockpit2.py:3799` |
| `kb_insight_link` | `cockpit2.py:3766` |
| `kb_insight_unlink` | `cockpit2.py:3773` |
| `kb_meta_start` | `cockpit2.py:3779` |
| `kb_atoom_merge` | `cockpit2.py:3876` |
| `kb_atoom_archive` | `cockpit2.py:3897` |
| `kb_atoom_unarchive` | `cockpit2.py:3906` |
| `kb_atoom_naar_spel` | `cockpit2.py:3912` |
| `kb_spel_start` | `cockpit2.py:3933` |
| `kb_spel_add` | `cockpit2.py:3947` |
| `kb_spel_remove` | `cockpit2.py:3957` |
| `kb_spel_flip` | `cockpit2.py:3964` |
| `kb_spel_finish` | `cockpit2.py:3970` |
| `kb_link` | `cockpit2.py:3564` |
| `kb_unlink` | `cockpit2.py:3578` |
| `kb_annotate` | `cockpit2.py:3589` |
| `kb_evidence` | `cockpit2.py:3595` |
| `kb_discuss` | `cockpit2.py:3616` |
| `kb_reformulate` | `cockpit2.py:3622` |
| `kw_nominate` | `cockpit2.py:3981` |
| `kw_nom_accept` | `cockpit2.py:3992` |
| `kw_nom_reject` | `cockpit2.py:4010` |
| `ws_forbid` | `cockpit2.py:4040` |
| `ws_approve` | `cockpit2.py:4045` |
| `proj_add` | `cockpit2.py:1125` |
| `artefact_add` | `cockpit2.py:1153` |
| `artefact_edit` | `cockpit2.py:1194` |
| `artefact_archive` | `cockpit2.py:1218` |
| `proj_status` | `cockpit2.py:1238` |
| `proj_done` | `cockpit2.py:1256` |
| `proj_archive` | `cockpit2.py:1291` |
| `proj_unarchive` | `cockpit2.py:1314` |
| `proj_delete` | `cockpit2.py:1324` |
| `proj_edit` | `cockpit2.py:1351` |
| `proj_comment` | `cockpit2.py:1364` |
| `proj_rename` | `cockpit2.py:1374` |
| `proj_describe` | `cockpit2.py:1385` |
| `proj_doc_edit` | `cockpit2.py:1418` |
| `proj_regen_doc` | `cockpit2.py:1396` |
| `proj_settrekker` | `cockpit2.py:1431` |
| `proj_setowner` | `cockpit2.py:1468` |
| `proj_approve` | `cockpit2.py:1487` |
| `proj_discard` | `cockpit2.py:1498` |
| `proj_setlabel` | `cockpit2.py:1509` |
| `proj_setimpact` | `cockpit2.py:1524` |
| `proj_seteffort` | `cockpit2.py:1543` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1566` |
| `proj_setprivate` | `cockpit2.py:1590` |
| `proj_setdue` | `cockpit2.py:1601` |
| `attach_add` | `cockpit2.py:1612` |
| `attach_remove` | `cockpit2.py:1623` |
| `react_add` | `cockpit2.py:1633` |
| `feed_edit` | `cockpit2.py:1643` |
| `feed_remove` | `cockpit2.py:1653` |
| `wall_outcome` | `cockpit2.py:2553` |
| `notif_read` | `cockpit2.py:2651` |
| `notif_processed` | `cockpit2.py:2656` |
| `notif_outcome` | `cockpit2.py:2803` |
| `notif_klaar` | `cockpit2.py:2789` |
| `notif_delete` | `cockpit2.py:2661` |
| `notif_add` | `cockpit2.py:2773` |
| `notif_archive` | `cockpit2.py:2890` |
| `metrics2_fav` | `cockpit2.py:2667` |
| `metrics2_unfav` | `cockpit2.py:2677` |
| `metrics2_form` | `cockpit2.py:2682` |
| `metrics2_dim` | `cockpit2.py:2688` |
| `metrics2_compare` | `cockpit2.py:2695` |
| `metrics2_formula` | `cockpit2.py:2758` |
| `source_activate` | `cockpit2.py:2741` |
| `source_deactivate` | `cockpit2.py:2750` |
| `link_pursue` | `cockpit2.py:2722` |
| `link_ignore` | `cockpit2.py:2732` |
| `acc_check` | `cockpit2.py:2703` |
| `ai_reply` | `cockpit2.py:1662` |
| `proj_feed` | `cockpit2.py:1673` |
| `checklist_add` | `cockpit2.py:1703` |
| `checklist_remove` | `cockpit2.py:1714` |
| `check_add` | `cockpit2.py:1762` |
| `check_accept` | `cockpit2.py:1779` |
| `check_toggle` | `cockpit2.py:1789` |
| `check_remove` | `cockpit2.py:1799` |
| `role_assign` | `cockpit2.py:1809` |
| `role_unassign` | `cockpit2.py:1827` |
| `role_focus` | `cockpit2.py:1846` |
| `radar_approve` | `cockpit2.py:1879` |
| `radar_dismiss` | `cockpit2.py:1889` |
| `radar_promote` | `cockpit2.py:1893` |
| `radar_merge` | `cockpit2.py:1913` |
| `radar_koppel` | `cockpit2.py:1929` |
| `kb_stage_koppel` | `cockpit2.py:1956` |
| `aitask_add` | `cockpit2.py:1994` |
| `aitask_remove` | `cockpit2.py:2025` |
| `skilllink_add` | `cockpit2.py:2053` |
| `means_gap_add` | `cockpit2.py:2083` |
| `persona_skill_add` | `cockpit2.py:2237` |
| `rov2_add` | `cockpit2.py:2252` |
| `rov2_add_to_group` | `cockpit2.py:2264` |
| `rov2_remove` | `cockpit2.py:2276` |
| `rov2_remove_group` | `cockpit2.py:2291` |
| `rov2_setkind` | `cockpit2.py:2309` |
| `rov2_consent` | `cockpit2.py:2322` |
| `rov2_end` | `cockpit2.py:2344` |
| `wo_open` | `cockpit2.py:2368` |
| `wo_close` | `cockpit2.py:2378` |
| `wo_presence` | `cockpit2.py:2394` |
| `wo_present_all` | `cockpit2.py:2405` |
| `wo_ag_add` | `cockpit2.py:2417` |
| `wo_ag_remove` | `cockpit2.py:2429` |
| `wo_ag_note` | `cockpit2.py:2439` |
| `wo_ag_reopen` | `cockpit2.py:2451` |
| `wo_ag_resolve` | `cockpit2.py:2527` |
| `wo_checkout` | `cockpit2.py:2895` |
| `noochie_send` | `cockpit2.py:2907` |
| `noochie_reset` | `cockpit2.py:2933` |
| `noochie_ctx` | `cockpit2.py:2940` |
| `cl_add` | `cockpit2.py:2947` |
| `cl_report` | `cockpit2.py:2965` |
| `cl_remove` | `cockpit2.py:2980` |
| `m_add_kpi` | `cockpit2.py:2990` |
| `m_add_from_def` | `cockpit2.py:3022` |
| `def_add` | `cockpit2.py:3037` |
| `catalog_publish` | `cockpit2.py:3059` |
| `def_amend` | `cockpit2.py:3085` |
| `m_add_link` | `cockpit2.py:3127` |
| `m_sample` | `cockpit2.py:3138` |
| `m_remove` | `cockpit2.py:3148` |
| `m_pin` | `cockpit2.py:3158` |
| `m_unpin` | `cockpit2.py:3169` |
| `tile_add` | `cockpit2.py:3207` |
| `indicator_activate` | `cockpit2.py:3179` |
| `tile_remove` | `cockpit2.py:3241` |
| `rov2_set` | `cockpit2.py:3251` |
| `rov2_acc_add` | `cockpit2.py:3251` |
| `rov2_acc_remove` | `cockpit2.py:3251` |
| `rov2_dom_add` | `cockpit2.py:3251` |
| `rov2_dom_remove` | `cockpit2.py:3251` |
| `backlog_add` | `cockpit2.py:3283` |
| `backlog_update_staat` | `cockpit2.py:3295` |
| `backlog_update_prioriteit` | `cockpit2.py:3307` |
| `person_edit` | `cockpit2.py:3319` |
| `person_remove` | `cockpit2.py:3336` |
| `lk_mute` | `cockpit2.py:3357` |
| `claims_term_add` | `cockpit2.py:3449` |
| `claims_work_status` | `cockpit2.py:3472` |
| `claims_to_board` | `cockpit2.py:3491` |
| `persona_edit` | `cockpit2.py:2136` |
| `persona_llm` | `cockpit2.py:2155` |
| `persona_finetune` | `cockpit2.py:2172` |
| `persona_finetune_apply` | `cockpit2.py:2190` |


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
_49 routes · 165 dispatch-acties · 30 stores._
