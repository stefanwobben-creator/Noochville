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
| `kb_new` | `cockpit2.py:3470` |
| `kb_intake` | `cockpit2.py:3552` |
| `kb_intake_url` | `cockpit2.py:3569` |
| `kb_stage_edit` | `cockpit2.py:3588` |
| `kb_stage_delete` | `cockpit2.py:3595` |
| `kb_stage_merge` | `cockpit2.py:3601` |
| `kb_stage_commit` | `cockpit2.py:3612` |
| `kb_stage_discard` | `cockpit2.py:3626` |
| `kb_atoom_subject` | `cockpit2.py:3702` |
| `kb_atoom_edit` | `cockpit2.py:3632` |
| `kb_atoom_related` | `cockpit2.py:3639` |
| `kb_atoom_reference` | `cockpit2.py:3684` |
| `kb_insight_link` | `cockpit2.py:3651` |
| `kb_insight_unlink` | `cockpit2.py:3658` |
| `kb_meta_start` | `cockpit2.py:3664` |
| `kb_atoom_merge` | `cockpit2.py:3713` |
| `kb_atoom_archive` | `cockpit2.py:3734` |
| `kb_atoom_unarchive` | `cockpit2.py:3743` |
| `kb_atoom_naar_spel` | `cockpit2.py:3749` |
| `kb_spel_start` | `cockpit2.py:3770` |
| `kb_spel_add` | `cockpit2.py:3784` |
| `kb_spel_remove` | `cockpit2.py:3794` |
| `kb_spel_flip` | `cockpit2.py:3801` |
| `kb_spel_finish` | `cockpit2.py:3807` |
| `kb_link` | `cockpit2.py:3479` |
| `kb_unlink` | `cockpit2.py:3493` |
| `kb_annotate` | `cockpit2.py:3504` |
| `kb_evidence` | `cockpit2.py:3510` |
| `kb_discuss` | `cockpit2.py:3531` |
| `kb_reformulate` | `cockpit2.py:3537` |
| `kw_nominate` | `cockpit2.py:3818` |
| `kw_nom_accept` | `cockpit2.py:3829` |
| `kw_nom_reject` | `cockpit2.py:3847` |
| `ws_forbid` | `cockpit2.py:3877` |
| `ws_approve` | `cockpit2.py:3882` |
| `proj_add` | `cockpit2.py:1124` |
| `artefact_add` | `cockpit2.py:1152` |
| `artefact_edit` | `cockpit2.py:1193` |
| `artefact_archive` | `cockpit2.py:1217` |
| `proj_status` | `cockpit2.py:1237` |
| `proj_done` | `cockpit2.py:1255` |
| `proj_archive` | `cockpit2.py:1290` |
| `proj_unarchive` | `cockpit2.py:1300` |
| `proj_delete` | `cockpit2.py:1310` |
| `proj_edit` | `cockpit2.py:1337` |
| `proj_comment` | `cockpit2.py:1350` |
| `proj_rename` | `cockpit2.py:1360` |
| `proj_describe` | `cockpit2.py:1371` |
| `proj_doc_edit` | `cockpit2.py:1404` |
| `proj_regen_doc` | `cockpit2.py:1382` |
| `proj_settrekker` | `cockpit2.py:1417` |
| `proj_setowner` | `cockpit2.py:1454` |
| `proj_approve` | `cockpit2.py:1473` |
| `proj_discard` | `cockpit2.py:1484` |
| `proj_setlabel` | `cockpit2.py:1495` |
| `proj_setimpact` | `cockpit2.py:1510` |
| `proj_seteffort` | `cockpit2.py:1529` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1552` |
| `proj_setprivate` | `cockpit2.py:1576` |
| `proj_setdue` | `cockpit2.py:1587` |
| `attach_add` | `cockpit2.py:1598` |
| `attach_remove` | `cockpit2.py:1609` |
| `react_add` | `cockpit2.py:1619` |
| `feed_edit` | `cockpit2.py:1629` |
| `feed_remove` | `cockpit2.py:1639` |
| `wall_outcome` | `cockpit2.py:2468` |
| `notif_read` | `cockpit2.py:2566` |
| `notif_processed` | `cockpit2.py:2571` |
| `notif_outcome` | `cockpit2.py:2718` |
| `notif_klaar` | `cockpit2.py:2704` |
| `notif_delete` | `cockpit2.py:2576` |
| `notif_add` | `cockpit2.py:2688` |
| `notif_archive` | `cockpit2.py:2805` |
| `metrics2_fav` | `cockpit2.py:2582` |
| `metrics2_unfav` | `cockpit2.py:2592` |
| `metrics2_form` | `cockpit2.py:2597` |
| `metrics2_dim` | `cockpit2.py:2603` |
| `metrics2_compare` | `cockpit2.py:2610` |
| `metrics2_formula` | `cockpit2.py:2673` |
| `source_activate` | `cockpit2.py:2656` |
| `source_deactivate` | `cockpit2.py:2665` |
| `link_pursue` | `cockpit2.py:2637` |
| `link_ignore` | `cockpit2.py:2647` |
| `acc_check` | `cockpit2.py:2618` |
| `ai_reply` | `cockpit2.py:1648` |
| `proj_feed` | `cockpit2.py:1659` |
| `checklist_add` | `cockpit2.py:1689` |
| `checklist_remove` | `cockpit2.py:1700` |
| `check_add` | `cockpit2.py:1748` |
| `check_accept` | `cockpit2.py:1765` |
| `check_toggle` | `cockpit2.py:1775` |
| `check_remove` | `cockpit2.py:1785` |
| `role_assign` | `cockpit2.py:1795` |
| `role_unassign` | `cockpit2.py:1813` |
| `role_focus` | `cockpit2.py:1832` |
| `radar_approve` | `cockpit2.py:1865` |
| `radar_dismiss` | `cockpit2.py:1875` |
| `radar_promote` | `cockpit2.py:1879` |
| `aitask_add` | `cockpit2.py:1909` |
| `aitask_remove` | `cockpit2.py:1940` |
| `skilllink_add` | `cockpit2.py:1968` |
| `means_gap_add` | `cockpit2.py:1998` |
| `persona_skill_add` | `cockpit2.py:2152` |
| `rov2_add` | `cockpit2.py:2167` |
| `rov2_add_to_group` | `cockpit2.py:2179` |
| `rov2_remove` | `cockpit2.py:2191` |
| `rov2_remove_group` | `cockpit2.py:2206` |
| `rov2_setkind` | `cockpit2.py:2224` |
| `rov2_consent` | `cockpit2.py:2237` |
| `rov2_end` | `cockpit2.py:2259` |
| `wo_open` | `cockpit2.py:2283` |
| `wo_close` | `cockpit2.py:2293` |
| `wo_presence` | `cockpit2.py:2309` |
| `wo_present_all` | `cockpit2.py:2320` |
| `wo_ag_add` | `cockpit2.py:2332` |
| `wo_ag_remove` | `cockpit2.py:2344` |
| `wo_ag_note` | `cockpit2.py:2354` |
| `wo_ag_reopen` | `cockpit2.py:2366` |
| `wo_ag_resolve` | `cockpit2.py:2442` |
| `wo_checkout` | `cockpit2.py:2810` |
| `noochie_send` | `cockpit2.py:2822` |
| `noochie_reset` | `cockpit2.py:2848` |
| `noochie_ctx` | `cockpit2.py:2855` |
| `cl_add` | `cockpit2.py:2862` |
| `cl_report` | `cockpit2.py:2880` |
| `cl_remove` | `cockpit2.py:2895` |
| `m_add_kpi` | `cockpit2.py:2905` |
| `m_add_from_def` | `cockpit2.py:2937` |
| `def_add` | `cockpit2.py:2952` |
| `catalog_publish` | `cockpit2.py:2974` |
| `def_amend` | `cockpit2.py:3000` |
| `m_add_link` | `cockpit2.py:3042` |
| `m_sample` | `cockpit2.py:3053` |
| `m_remove` | `cockpit2.py:3063` |
| `m_pin` | `cockpit2.py:3073` |
| `m_unpin` | `cockpit2.py:3084` |
| `tile_add` | `cockpit2.py:3122` |
| `indicator_activate` | `cockpit2.py:3094` |
| `tile_remove` | `cockpit2.py:3156` |
| `rov2_set` | `cockpit2.py:3166` |
| `rov2_acc_add` | `cockpit2.py:3166` |
| `rov2_acc_remove` | `cockpit2.py:3166` |
| `rov2_dom_add` | `cockpit2.py:3166` |
| `rov2_dom_remove` | `cockpit2.py:3166` |
| `backlog_add` | `cockpit2.py:3198` |
| `backlog_update_staat` | `cockpit2.py:3210` |
| `backlog_update_prioriteit` | `cockpit2.py:3222` |
| `person_edit` | `cockpit2.py:3234` |
| `person_remove` | `cockpit2.py:3251` |
| `lk_mute` | `cockpit2.py:3272` |
| `claims_term_add` | `cockpit2.py:3364` |
| `claims_work_status` | `cockpit2.py:3387` |
| `claims_to_board` | `cockpit2.py:3406` |
| `persona_edit` | `cockpit2.py:2051` |
| `persona_llm` | `cockpit2.py:2070` |
| `persona_finetune` | `cockpit2.py:2087` |
| `persona_finetune_apply` | `cockpit2.py:2105` |


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
_47 routes · 157 dispatch-acties · 30 stores._
