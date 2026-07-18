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
| `/claims` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `kb_new` | `cockpit2.py:3108` |
| `kb_intake` | `cockpit2.py:3190` |
| `kb_intake_url` | `cockpit2.py:3207` |
| `kb_stage_edit` | `cockpit2.py:3226` |
| `kb_stage_delete` | `cockpit2.py:3233` |
| `kb_stage_merge` | `cockpit2.py:3239` |
| `kb_stage_commit` | `cockpit2.py:3250` |
| `kb_stage_discard` | `cockpit2.py:3264` |
| `kb_atoom_subject` | `cockpit2.py:3334` |
| `kb_atoom_edit` | `cockpit2.py:3270` |
| `kb_atoom_related` | `cockpit2.py:3277` |
| `kb_atoom_reference` | `cockpit2.py:3322` |
| `kb_insight_link` | `cockpit2.py:3289` |
| `kb_insight_unlink` | `cockpit2.py:3296` |
| `kb_meta_start` | `cockpit2.py:3302` |
| `kb_atoom_merge` | `cockpit2.py:3345` |
| `kb_atoom_archive` | `cockpit2.py:3361` |
| `kb_atoom_unarchive` | `cockpit2.py:3370` |
| `kb_atoom_naar_spel` | `cockpit2.py:3376` |
| `kb_spel_start` | `cockpit2.py:3396` |
| `kb_spel_add` | `cockpit2.py:3410` |
| `kb_spel_remove` | `cockpit2.py:3420` |
| `kb_spel_flip` | `cockpit2.py:3427` |
| `kb_spel_finish` | `cockpit2.py:3433` |
| `kb_link` | `cockpit2.py:3117` |
| `kb_unlink` | `cockpit2.py:3131` |
| `kb_annotate` | `cockpit2.py:3142` |
| `kb_evidence` | `cockpit2.py:3148` |
| `kb_discuss` | `cockpit2.py:3169` |
| `kb_reformulate` | `cockpit2.py:3175` |
| `kw_nominate` | `cockpit2.py:3444` |
| `kw_nom_accept` | `cockpit2.py:3455` |
| `kw_nom_reject` | `cockpit2.py:3473` |
| `ws_forbid` | `cockpit2.py:3503` |
| `ws_approve` | `cockpit2.py:3508` |
| `proj_add` | `cockpit2.py:1109` |
| `artefact_add` | `cockpit2.py:1137` |
| `artefact_edit` | `cockpit2.py:1178` |
| `artefact_archive` | `cockpit2.py:1202` |
| `proj_status` | `cockpit2.py:1222` |
| `proj_done` | `cockpit2.py:1240` |
| `proj_archive` | `cockpit2.py:1262` |
| `proj_unarchive` | `cockpit2.py:1272` |
| `proj_delete` | `cockpit2.py:1282` |
| `proj_edit` | `cockpit2.py:1309` |
| `proj_comment` | `cockpit2.py:1322` |
| `proj_rename` | `cockpit2.py:1332` |
| `proj_describe` | `cockpit2.py:1343` |
| `proj_doc_edit` | `cockpit2.py:1376` |
| `proj_regen_doc` | `cockpit2.py:1354` |
| `proj_settrekker` | `cockpit2.py:1389` |
| `proj_setowner` | `cockpit2.py:1426` |
| `proj_approve` | `cockpit2.py:1445` |
| `proj_discard` | `cockpit2.py:1456` |
| `proj_setlabel` | `cockpit2.py:1467` |
| `proj_setimpact` | `cockpit2.py:1482` |
| `proj_seteffort` | `cockpit2.py:1501` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1524` |
| `proj_setprivate` | `cockpit2.py:1548` |
| `proj_setdue` | `cockpit2.py:1559` |
| `attach_add` | `cockpit2.py:1570` |
| `attach_remove` | `cockpit2.py:1581` |
| `react_add` | `cockpit2.py:1591` |
| `feed_edit` | `cockpit2.py:1601` |
| `feed_remove` | `cockpit2.py:1611` |
| `wall_outcome` | `cockpit2.py:2204` |
| `notif_read` | `cockpit2.py:2302` |
| `notif_processed` | `cockpit2.py:2307` |
| `notif_outcome` | `cockpit2.py:2454` |
| `notif_klaar` | `cockpit2.py:2440` |
| `notif_delete` | `cockpit2.py:2312` |
| `notif_add` | `cockpit2.py:2424` |
| `notif_archive` | `cockpit2.py:2541` |
| `metrics2_fav` | `cockpit2.py:2318` |
| `metrics2_unfav` | `cockpit2.py:2328` |
| `metrics2_form` | `cockpit2.py:2333` |
| `metrics2_dim` | `cockpit2.py:2339` |
| `metrics2_compare` | `cockpit2.py:2346` |
| `metrics2_formula` | `cockpit2.py:2409` |
| `source_activate` | `cockpit2.py:2392` |
| `source_deactivate` | `cockpit2.py:2401` |
| `link_pursue` | `cockpit2.py:2373` |
| `link_ignore` | `cockpit2.py:2383` |
| `acc_check` | `cockpit2.py:2354` |
| `ai_reply` | `cockpit2.py:1620` |
| `proj_feed` | `cockpit2.py:1631` |
| `checklist_add` | `cockpit2.py:1661` |
| `checklist_remove` | `cockpit2.py:1672` |
| `check_add` | `cockpit2.py:1720` |
| `check_accept` | `cockpit2.py:1737` |
| `check_toggle` | `cockpit2.py:1747` |
| `check_remove` | `cockpit2.py:1757` |
| `role_assign` | `cockpit2.py:1767` |
| `role_unassign` | `cockpit2.py:1785` |
| `role_focus` | `cockpit2.py:1804` |
| `radar_approve` | `cockpit2.py:1837` |
| `radar_dismiss` | `cockpit2.py:1841` |
| `aitask_add` | `cockpit2.py:1845` |
| `aitask_remove` | `cockpit2.py:1871` |
| `persona_skill_add` | `cockpit2.py:1888` |
| `rov2_add` | `cockpit2.py:1903` |
| `rov2_add_to_group` | `cockpit2.py:1915` |
| `rov2_remove` | `cockpit2.py:1927` |
| `rov2_remove_group` | `cockpit2.py:1942` |
| `rov2_setkind` | `cockpit2.py:1960` |
| `rov2_consent` | `cockpit2.py:1973` |
| `rov2_end` | `cockpit2.py:1995` |
| `wo_open` | `cockpit2.py:2019` |
| `wo_close` | `cockpit2.py:2029` |
| `wo_presence` | `cockpit2.py:2045` |
| `wo_present_all` | `cockpit2.py:2056` |
| `wo_ag_add` | `cockpit2.py:2068` |
| `wo_ag_remove` | `cockpit2.py:2080` |
| `wo_ag_note` | `cockpit2.py:2090` |
| `wo_ag_reopen` | `cockpit2.py:2102` |
| `wo_ag_resolve` | `cockpit2.py:2178` |
| `wo_checkout` | `cockpit2.py:2546` |
| `noochie_send` | `cockpit2.py:2558` |
| `noochie_reset` | `cockpit2.py:2584` |
| `noochie_ctx` | `cockpit2.py:2591` |
| `cl_add` | `cockpit2.py:2598` |
| `cl_report` | `cockpit2.py:2616` |
| `cl_remove` | `cockpit2.py:2631` |
| `m_add_kpi` | `cockpit2.py:2641` |
| `m_add_from_def` | `cockpit2.py:2673` |
| `def_add` | `cockpit2.py:2688` |
| `catalog_publish` | `cockpit2.py:2710` |
| `def_amend` | `cockpit2.py:2736` |
| `m_add_link` | `cockpit2.py:2778` |
| `m_sample` | `cockpit2.py:2789` |
| `m_remove` | `cockpit2.py:2799` |
| `m_pin` | `cockpit2.py:2809` |
| `m_unpin` | `cockpit2.py:2820` |
| `tile_add` | `cockpit2.py:2858` |
| `indicator_activate` | `cockpit2.py:2830` |
| `tile_remove` | `cockpit2.py:2892` |
| `rov2_set` | `cockpit2.py:2902` |
| `rov2_acc_add` | `cockpit2.py:2902` |
| `rov2_acc_remove` | `cockpit2.py:2902` |
| `rov2_dom_add` | `cockpit2.py:2902` |
| `rov2_dom_remove` | `cockpit2.py:2902` |
| `backlog_add` | `cockpit2.py:2934` |
| `backlog_update_staat` | `cockpit2.py:2946` |
| `backlog_update_prioriteit` | `cockpit2.py:2958` |
| `person_edit` | `cockpit2.py:2970` |
| `person_remove` | `cockpit2.py:2987` |
| `lk_mute` | `cockpit2.py:3008` |
| `claims_term_add` | `cockpit2.py:3044` |
| `claims_work_status` | `cockpit2.py:3067` |


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


---
_44 routes · 149 dispatch-acties · 29 stores._
