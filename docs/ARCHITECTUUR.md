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
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/inzichten` | `render_kennislaag` | `nooch_village/views/kennislaag.py` |
| `/kennisbank` | `render_kennisbank` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/search` | `render_kennisbank_search` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/staging` | `render_kennisbank_staging` | `nooch_village/views/kennisbank_staging.py` |
| `/kennisbank/spel` | `render_kennisbank_spel` | `nooch_village/views/kennisbank_spel.py` |
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
| `kb_new` | `cockpit2.py:3448` |
| `kb_intake` | `cockpit2.py:3530` |
| `kb_intake_url` | `cockpit2.py:3547` |
| `kb_stage_edit` | `cockpit2.py:3566` |
| `kb_stage_delete` | `cockpit2.py:3573` |
| `kb_stage_merge` | `cockpit2.py:3579` |
| `kb_stage_commit` | `cockpit2.py:3590` |
| `kb_stage_discard` | `cockpit2.py:3604` |
| `kb_atoom_subject` | `cockpit2.py:3680` |
| `kb_atoom_edit` | `cockpit2.py:3610` |
| `kb_atoom_related` | `cockpit2.py:3617` |
| `kb_atoom_reference` | `cockpit2.py:3662` |
| `kb_insight_link` | `cockpit2.py:3629` |
| `kb_insight_unlink` | `cockpit2.py:3636` |
| `kb_meta_start` | `cockpit2.py:3642` |
| `kb_atoom_merge` | `cockpit2.py:3691` |
| `kb_atoom_archive` | `cockpit2.py:3712` |
| `kb_atoom_unarchive` | `cockpit2.py:3721` |
| `kb_atoom_naar_spel` | `cockpit2.py:3727` |
| `kb_spel_start` | `cockpit2.py:3748` |
| `kb_spel_add` | `cockpit2.py:3762` |
| `kb_spel_remove` | `cockpit2.py:3772` |
| `kb_spel_flip` | `cockpit2.py:3779` |
| `kb_spel_finish` | `cockpit2.py:3785` |
| `kb_link` | `cockpit2.py:3457` |
| `kb_unlink` | `cockpit2.py:3471` |
| `kb_annotate` | `cockpit2.py:3482` |
| `kb_evidence` | `cockpit2.py:3488` |
| `kb_discuss` | `cockpit2.py:3509` |
| `kb_reformulate` | `cockpit2.py:3515` |
| `kw_nominate` | `cockpit2.py:3796` |
| `kw_nom_accept` | `cockpit2.py:3807` |
| `kw_nom_reject` | `cockpit2.py:3825` |
| `ws_forbid` | `cockpit2.py:3855` |
| `ws_approve` | `cockpit2.py:3860` |
| `proj_add` | `cockpit2.py:1123` |
| `artefact_add` | `cockpit2.py:1151` |
| `artefact_edit` | `cockpit2.py:1192` |
| `artefact_archive` | `cockpit2.py:1216` |
| `proj_status` | `cockpit2.py:1236` |
| `proj_done` | `cockpit2.py:1254` |
| `proj_archive` | `cockpit2.py:1289` |
| `proj_unarchive` | `cockpit2.py:1299` |
| `proj_delete` | `cockpit2.py:1309` |
| `proj_edit` | `cockpit2.py:1336` |
| `proj_comment` | `cockpit2.py:1349` |
| `proj_rename` | `cockpit2.py:1359` |
| `proj_describe` | `cockpit2.py:1370` |
| `proj_doc_edit` | `cockpit2.py:1403` |
| `proj_regen_doc` | `cockpit2.py:1381` |
| `proj_settrekker` | `cockpit2.py:1416` |
| `proj_setowner` | `cockpit2.py:1453` |
| `proj_approve` | `cockpit2.py:1472` |
| `proj_discard` | `cockpit2.py:1483` |
| `proj_setlabel` | `cockpit2.py:1494` |
| `proj_setimpact` | `cockpit2.py:1509` |
| `proj_seteffort` | `cockpit2.py:1528` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1551` |
| `proj_setprivate` | `cockpit2.py:1575` |
| `proj_setdue` | `cockpit2.py:1586` |
| `attach_add` | `cockpit2.py:1597` |
| `attach_remove` | `cockpit2.py:1608` |
| `react_add` | `cockpit2.py:1618` |
| `feed_edit` | `cockpit2.py:1628` |
| `feed_remove` | `cockpit2.py:1638` |
| `wall_outcome` | `cockpit2.py:2446` |
| `notif_read` | `cockpit2.py:2544` |
| `notif_processed` | `cockpit2.py:2549` |
| `notif_outcome` | `cockpit2.py:2696` |
| `notif_klaar` | `cockpit2.py:2682` |
| `notif_delete` | `cockpit2.py:2554` |
| `notif_add` | `cockpit2.py:2666` |
| `notif_archive` | `cockpit2.py:2783` |
| `metrics2_fav` | `cockpit2.py:2560` |
| `metrics2_unfav` | `cockpit2.py:2570` |
| `metrics2_form` | `cockpit2.py:2575` |
| `metrics2_dim` | `cockpit2.py:2581` |
| `metrics2_compare` | `cockpit2.py:2588` |
| `metrics2_formula` | `cockpit2.py:2651` |
| `source_activate` | `cockpit2.py:2634` |
| `source_deactivate` | `cockpit2.py:2643` |
| `link_pursue` | `cockpit2.py:2615` |
| `link_ignore` | `cockpit2.py:2625` |
| `acc_check` | `cockpit2.py:2596` |
| `ai_reply` | `cockpit2.py:1647` |
| `proj_feed` | `cockpit2.py:1658` |
| `checklist_add` | `cockpit2.py:1688` |
| `checklist_remove` | `cockpit2.py:1699` |
| `check_add` | `cockpit2.py:1747` |
| `check_accept` | `cockpit2.py:1764` |
| `check_toggle` | `cockpit2.py:1774` |
| `check_remove` | `cockpit2.py:1784` |
| `role_assign` | `cockpit2.py:1794` |
| `role_unassign` | `cockpit2.py:1812` |
| `role_focus` | `cockpit2.py:1831` |
| `radar_approve` | `cockpit2.py:1864` |
| `radar_dismiss` | `cockpit2.py:1874` |
| `radar_promote` | `cockpit2.py:1878` |
| `aitask_add` | `cockpit2.py:1908` |
| `aitask_remove` | `cockpit2.py:1939` |
| `skilllink_add` | `cockpit2.py:1967` |
| `persona_skill_add` | `cockpit2.py:2130` |
| `rov2_add` | `cockpit2.py:2145` |
| `rov2_add_to_group` | `cockpit2.py:2157` |
| `rov2_remove` | `cockpit2.py:2169` |
| `rov2_remove_group` | `cockpit2.py:2184` |
| `rov2_setkind` | `cockpit2.py:2202` |
| `rov2_consent` | `cockpit2.py:2215` |
| `rov2_end` | `cockpit2.py:2237` |
| `wo_open` | `cockpit2.py:2261` |
| `wo_close` | `cockpit2.py:2271` |
| `wo_presence` | `cockpit2.py:2287` |
| `wo_present_all` | `cockpit2.py:2298` |
| `wo_ag_add` | `cockpit2.py:2310` |
| `wo_ag_remove` | `cockpit2.py:2322` |
| `wo_ag_note` | `cockpit2.py:2332` |
| `wo_ag_reopen` | `cockpit2.py:2344` |
| `wo_ag_resolve` | `cockpit2.py:2420` |
| `wo_checkout` | `cockpit2.py:2788` |
| `noochie_send` | `cockpit2.py:2800` |
| `noochie_reset` | `cockpit2.py:2826` |
| `noochie_ctx` | `cockpit2.py:2833` |
| `cl_add` | `cockpit2.py:2840` |
| `cl_report` | `cockpit2.py:2858` |
| `cl_remove` | `cockpit2.py:2873` |
| `m_add_kpi` | `cockpit2.py:2883` |
| `m_add_from_def` | `cockpit2.py:2915` |
| `def_add` | `cockpit2.py:2930` |
| `catalog_publish` | `cockpit2.py:2952` |
| `def_amend` | `cockpit2.py:2978` |
| `m_add_link` | `cockpit2.py:3020` |
| `m_sample` | `cockpit2.py:3031` |
| `m_remove` | `cockpit2.py:3041` |
| `m_pin` | `cockpit2.py:3051` |
| `m_unpin` | `cockpit2.py:3062` |
| `tile_add` | `cockpit2.py:3100` |
| `indicator_activate` | `cockpit2.py:3072` |
| `tile_remove` | `cockpit2.py:3134` |
| `rov2_set` | `cockpit2.py:3144` |
| `rov2_acc_add` | `cockpit2.py:3144` |
| `rov2_acc_remove` | `cockpit2.py:3144` |
| `rov2_dom_add` | `cockpit2.py:3144` |
| `rov2_dom_remove` | `cockpit2.py:3144` |
| `backlog_add` | `cockpit2.py:3176` |
| `backlog_update_staat` | `cockpit2.py:3188` |
| `backlog_update_prioriteit` | `cockpit2.py:3200` |
| `person_edit` | `cockpit2.py:3212` |
| `person_remove` | `cockpit2.py:3229` |
| `lk_mute` | `cockpit2.py:3250` |
| `claims_term_add` | `cockpit2.py:3342` |
| `claims_work_status` | `cockpit2.py:3365` |
| `claims_to_board` | `cockpit2.py:3384` |
| `persona_edit` | `cockpit2.py:2029` |
| `persona_llm` | `cockpit2.py:2048` |
| `persona_finetune` | `cockpit2.py:2065` |
| `persona_finetune_apply` | `cockpit2.py:2083` |


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
_46 routes · 156 dispatch-acties · 30 stores._
