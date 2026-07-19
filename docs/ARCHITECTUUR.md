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
| `kb_new` | `cockpit2.py:3525` |
| `kb_intake` | `cockpit2.py:3607` |
| `kb_intake_url` | `cockpit2.py:3624` |
| `kb_stage_edit` | `cockpit2.py:3643` |
| `kb_stage_delete` | `cockpit2.py:3650` |
| `kb_stage_merge` | `cockpit2.py:3656` |
| `kb_stage_commit` | `cockpit2.py:3667` |
| `kb_stage_discard` | `cockpit2.py:3687` |
| `kb_atoom_subject` | `cockpit2.py:3763` |
| `kb_atoom_edit` | `cockpit2.py:3693` |
| `kb_atoom_related` | `cockpit2.py:3700` |
| `kb_atoom_reference` | `cockpit2.py:3745` |
| `kb_insight_link` | `cockpit2.py:3712` |
| `kb_insight_unlink` | `cockpit2.py:3719` |
| `kb_meta_start` | `cockpit2.py:3725` |
| `kb_atoom_merge` | `cockpit2.py:3774` |
| `kb_atoom_archive` | `cockpit2.py:3795` |
| `kb_atoom_unarchive` | `cockpit2.py:3804` |
| `kb_atoom_naar_spel` | `cockpit2.py:3810` |
| `kb_spel_start` | `cockpit2.py:3831` |
| `kb_spel_add` | `cockpit2.py:3845` |
| `kb_spel_remove` | `cockpit2.py:3855` |
| `kb_spel_flip` | `cockpit2.py:3862` |
| `kb_spel_finish` | `cockpit2.py:3868` |
| `kb_link` | `cockpit2.py:3534` |
| `kb_unlink` | `cockpit2.py:3548` |
| `kb_annotate` | `cockpit2.py:3559` |
| `kb_evidence` | `cockpit2.py:3565` |
| `kb_discuss` | `cockpit2.py:3586` |
| `kb_reformulate` | `cockpit2.py:3592` |
| `kw_nominate` | `cockpit2.py:3879` |
| `kw_nom_accept` | `cockpit2.py:3890` |
| `kw_nom_reject` | `cockpit2.py:3908` |
| `ws_forbid` | `cockpit2.py:3938` |
| `ws_approve` | `cockpit2.py:3943` |
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
| `wall_outcome` | `cockpit2.py:2523` |
| `notif_read` | `cockpit2.py:2621` |
| `notif_processed` | `cockpit2.py:2626` |
| `notif_outcome` | `cockpit2.py:2773` |
| `notif_klaar` | `cockpit2.py:2759` |
| `notif_delete` | `cockpit2.py:2631` |
| `notif_add` | `cockpit2.py:2743` |
| `notif_archive` | `cockpit2.py:2860` |
| `metrics2_fav` | `cockpit2.py:2637` |
| `metrics2_unfav` | `cockpit2.py:2647` |
| `metrics2_form` | `cockpit2.py:2652` |
| `metrics2_dim` | `cockpit2.py:2658` |
| `metrics2_compare` | `cockpit2.py:2665` |
| `metrics2_formula` | `cockpit2.py:2728` |
| `source_activate` | `cockpit2.py:2711` |
| `source_deactivate` | `cockpit2.py:2720` |
| `link_pursue` | `cockpit2.py:2692` |
| `link_ignore` | `cockpit2.py:2702` |
| `acc_check` | `cockpit2.py:2673` |
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
| `radar_promote_multi` | `cockpit2.py:1899` |
| `kb_stage_koppel` | `cockpit2.py:1926` |
| `aitask_add` | `cockpit2.py:1964` |
| `aitask_remove` | `cockpit2.py:1995` |
| `skilllink_add` | `cockpit2.py:2023` |
| `means_gap_add` | `cockpit2.py:2053` |
| `persona_skill_add` | `cockpit2.py:2207` |
| `rov2_add` | `cockpit2.py:2222` |
| `rov2_add_to_group` | `cockpit2.py:2234` |
| `rov2_remove` | `cockpit2.py:2246` |
| `rov2_remove_group` | `cockpit2.py:2261` |
| `rov2_setkind` | `cockpit2.py:2279` |
| `rov2_consent` | `cockpit2.py:2292` |
| `rov2_end` | `cockpit2.py:2314` |
| `wo_open` | `cockpit2.py:2338` |
| `wo_close` | `cockpit2.py:2348` |
| `wo_presence` | `cockpit2.py:2364` |
| `wo_present_all` | `cockpit2.py:2375` |
| `wo_ag_add` | `cockpit2.py:2387` |
| `wo_ag_remove` | `cockpit2.py:2399` |
| `wo_ag_note` | `cockpit2.py:2409` |
| `wo_ag_reopen` | `cockpit2.py:2421` |
| `wo_ag_resolve` | `cockpit2.py:2497` |
| `wo_checkout` | `cockpit2.py:2865` |
| `noochie_send` | `cockpit2.py:2877` |
| `noochie_reset` | `cockpit2.py:2903` |
| `noochie_ctx` | `cockpit2.py:2910` |
| `cl_add` | `cockpit2.py:2917` |
| `cl_report` | `cockpit2.py:2935` |
| `cl_remove` | `cockpit2.py:2950` |
| `m_add_kpi` | `cockpit2.py:2960` |
| `m_add_from_def` | `cockpit2.py:2992` |
| `def_add` | `cockpit2.py:3007` |
| `catalog_publish` | `cockpit2.py:3029` |
| `def_amend` | `cockpit2.py:3055` |
| `m_add_link` | `cockpit2.py:3097` |
| `m_sample` | `cockpit2.py:3108` |
| `m_remove` | `cockpit2.py:3118` |
| `m_pin` | `cockpit2.py:3128` |
| `m_unpin` | `cockpit2.py:3139` |
| `tile_add` | `cockpit2.py:3177` |
| `indicator_activate` | `cockpit2.py:3149` |
| `tile_remove` | `cockpit2.py:3211` |
| `rov2_set` | `cockpit2.py:3221` |
| `rov2_acc_add` | `cockpit2.py:3221` |
| `rov2_acc_remove` | `cockpit2.py:3221` |
| `rov2_dom_add` | `cockpit2.py:3221` |
| `rov2_dom_remove` | `cockpit2.py:3221` |
| `backlog_add` | `cockpit2.py:3253` |
| `backlog_update_staat` | `cockpit2.py:3265` |
| `backlog_update_prioriteit` | `cockpit2.py:3277` |
| `person_edit` | `cockpit2.py:3289` |
| `person_remove` | `cockpit2.py:3306` |
| `lk_mute` | `cockpit2.py:3327` |
| `claims_term_add` | `cockpit2.py:3419` |
| `claims_work_status` | `cockpit2.py:3442` |
| `claims_to_board` | `cockpit2.py:3461` |
| `persona_edit` | `cockpit2.py:2106` |
| `persona_llm` | `cockpit2.py:2125` |
| `persona_finetune` | `cockpit2.py:2142` |
| `persona_finetune_apply` | `cockpit2.py:2160` |


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
_47 routes · 159 dispatch-acties · 30 stores._
