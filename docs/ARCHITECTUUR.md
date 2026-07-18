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
| `kb_new` | `cockpit2.py:3407` |
| `kb_intake` | `cockpit2.py:3489` |
| `kb_intake_url` | `cockpit2.py:3506` |
| `kb_stage_edit` | `cockpit2.py:3525` |
| `kb_stage_delete` | `cockpit2.py:3532` |
| `kb_stage_merge` | `cockpit2.py:3538` |
| `kb_stage_commit` | `cockpit2.py:3549` |
| `kb_stage_discard` | `cockpit2.py:3563` |
| `kb_atoom_subject` | `cockpit2.py:3639` |
| `kb_atoom_edit` | `cockpit2.py:3569` |
| `kb_atoom_related` | `cockpit2.py:3576` |
| `kb_atoom_reference` | `cockpit2.py:3621` |
| `kb_insight_link` | `cockpit2.py:3588` |
| `kb_insight_unlink` | `cockpit2.py:3595` |
| `kb_meta_start` | `cockpit2.py:3601` |
| `kb_atoom_merge` | `cockpit2.py:3650` |
| `kb_atoom_archive` | `cockpit2.py:3671` |
| `kb_atoom_unarchive` | `cockpit2.py:3680` |
| `kb_atoom_naar_spel` | `cockpit2.py:3686` |
| `kb_spel_start` | `cockpit2.py:3707` |
| `kb_spel_add` | `cockpit2.py:3721` |
| `kb_spel_remove` | `cockpit2.py:3731` |
| `kb_spel_flip` | `cockpit2.py:3738` |
| `kb_spel_finish` | `cockpit2.py:3744` |
| `kb_link` | `cockpit2.py:3416` |
| `kb_unlink` | `cockpit2.py:3430` |
| `kb_annotate` | `cockpit2.py:3441` |
| `kb_evidence` | `cockpit2.py:3447` |
| `kb_discuss` | `cockpit2.py:3468` |
| `kb_reformulate` | `cockpit2.py:3474` |
| `kw_nominate` | `cockpit2.py:3755` |
| `kw_nom_accept` | `cockpit2.py:3766` |
| `kw_nom_reject` | `cockpit2.py:3784` |
| `ws_forbid` | `cockpit2.py:3814` |
| `ws_approve` | `cockpit2.py:3819` |
| `proj_add` | `cockpit2.py:1120` |
| `artefact_add` | `cockpit2.py:1148` |
| `artefact_edit` | `cockpit2.py:1189` |
| `artefact_archive` | `cockpit2.py:1213` |
| `proj_status` | `cockpit2.py:1233` |
| `proj_done` | `cockpit2.py:1251` |
| `proj_archive` | `cockpit2.py:1286` |
| `proj_unarchive` | `cockpit2.py:1296` |
| `proj_delete` | `cockpit2.py:1306` |
| `proj_edit` | `cockpit2.py:1333` |
| `proj_comment` | `cockpit2.py:1346` |
| `proj_rename` | `cockpit2.py:1356` |
| `proj_describe` | `cockpit2.py:1367` |
| `proj_doc_edit` | `cockpit2.py:1400` |
| `proj_regen_doc` | `cockpit2.py:1378` |
| `proj_settrekker` | `cockpit2.py:1413` |
| `proj_setowner` | `cockpit2.py:1450` |
| `proj_approve` | `cockpit2.py:1469` |
| `proj_discard` | `cockpit2.py:1480` |
| `proj_setlabel` | `cockpit2.py:1491` |
| `proj_setimpact` | `cockpit2.py:1506` |
| `proj_seteffort` | `cockpit2.py:1525` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1548` |
| `proj_setprivate` | `cockpit2.py:1572` |
| `proj_setdue` | `cockpit2.py:1583` |
| `attach_add` | `cockpit2.py:1594` |
| `attach_remove` | `cockpit2.py:1605` |
| `react_add` | `cockpit2.py:1615` |
| `feed_edit` | `cockpit2.py:1625` |
| `feed_remove` | `cockpit2.py:1635` |
| `wall_outcome` | `cockpit2.py:2405` |
| `notif_read` | `cockpit2.py:2503` |
| `notif_processed` | `cockpit2.py:2508` |
| `notif_outcome` | `cockpit2.py:2655` |
| `notif_klaar` | `cockpit2.py:2641` |
| `notif_delete` | `cockpit2.py:2513` |
| `notif_add` | `cockpit2.py:2625` |
| `notif_archive` | `cockpit2.py:2742` |
| `metrics2_fav` | `cockpit2.py:2519` |
| `metrics2_unfav` | `cockpit2.py:2529` |
| `metrics2_form` | `cockpit2.py:2534` |
| `metrics2_dim` | `cockpit2.py:2540` |
| `metrics2_compare` | `cockpit2.py:2547` |
| `metrics2_formula` | `cockpit2.py:2610` |
| `source_activate` | `cockpit2.py:2593` |
| `source_deactivate` | `cockpit2.py:2602` |
| `link_pursue` | `cockpit2.py:2574` |
| `link_ignore` | `cockpit2.py:2584` |
| `acc_check` | `cockpit2.py:2555` |
| `ai_reply` | `cockpit2.py:1644` |
| `proj_feed` | `cockpit2.py:1655` |
| `checklist_add` | `cockpit2.py:1685` |
| `checklist_remove` | `cockpit2.py:1696` |
| `check_add` | `cockpit2.py:1744` |
| `check_accept` | `cockpit2.py:1761` |
| `check_toggle` | `cockpit2.py:1771` |
| `check_remove` | `cockpit2.py:1781` |
| `role_assign` | `cockpit2.py:1791` |
| `role_unassign` | `cockpit2.py:1809` |
| `role_focus` | `cockpit2.py:1828` |
| `radar_approve` | `cockpit2.py:1861` |
| `radar_dismiss` | `cockpit2.py:1871` |
| `radar_promote` | `cockpit2.py:1875` |
| `aitask_add` | `cockpit2.py:1905` |
| `aitask_remove` | `cockpit2.py:1936` |
| `persona_skill_add` | `cockpit2.py:2089` |
| `rov2_add` | `cockpit2.py:2104` |
| `rov2_add_to_group` | `cockpit2.py:2116` |
| `rov2_remove` | `cockpit2.py:2128` |
| `rov2_remove_group` | `cockpit2.py:2143` |
| `rov2_setkind` | `cockpit2.py:2161` |
| `rov2_consent` | `cockpit2.py:2174` |
| `rov2_end` | `cockpit2.py:2196` |
| `wo_open` | `cockpit2.py:2220` |
| `wo_close` | `cockpit2.py:2230` |
| `wo_presence` | `cockpit2.py:2246` |
| `wo_present_all` | `cockpit2.py:2257` |
| `wo_ag_add` | `cockpit2.py:2269` |
| `wo_ag_remove` | `cockpit2.py:2281` |
| `wo_ag_note` | `cockpit2.py:2291` |
| `wo_ag_reopen` | `cockpit2.py:2303` |
| `wo_ag_resolve` | `cockpit2.py:2379` |
| `wo_checkout` | `cockpit2.py:2747` |
| `noochie_send` | `cockpit2.py:2759` |
| `noochie_reset` | `cockpit2.py:2785` |
| `noochie_ctx` | `cockpit2.py:2792` |
| `cl_add` | `cockpit2.py:2799` |
| `cl_report` | `cockpit2.py:2817` |
| `cl_remove` | `cockpit2.py:2832` |
| `m_add_kpi` | `cockpit2.py:2842` |
| `m_add_from_def` | `cockpit2.py:2874` |
| `def_add` | `cockpit2.py:2889` |
| `catalog_publish` | `cockpit2.py:2911` |
| `def_amend` | `cockpit2.py:2937` |
| `m_add_link` | `cockpit2.py:2979` |
| `m_sample` | `cockpit2.py:2990` |
| `m_remove` | `cockpit2.py:3000` |
| `m_pin` | `cockpit2.py:3010` |
| `m_unpin` | `cockpit2.py:3021` |
| `tile_add` | `cockpit2.py:3059` |
| `indicator_activate` | `cockpit2.py:3031` |
| `tile_remove` | `cockpit2.py:3093` |
| `rov2_set` | `cockpit2.py:3103` |
| `rov2_acc_add` | `cockpit2.py:3103` |
| `rov2_acc_remove` | `cockpit2.py:3103` |
| `rov2_dom_add` | `cockpit2.py:3103` |
| `rov2_dom_remove` | `cockpit2.py:3103` |
| `backlog_add` | `cockpit2.py:3135` |
| `backlog_update_staat` | `cockpit2.py:3147` |
| `backlog_update_prioriteit` | `cockpit2.py:3159` |
| `person_edit` | `cockpit2.py:3171` |
| `person_remove` | `cockpit2.py:3188` |
| `lk_mute` | `cockpit2.py:3209` |
| `claims_term_add` | `cockpit2.py:3301` |
| `claims_work_status` | `cockpit2.py:3324` |
| `claims_to_board` | `cockpit2.py:3343` |
| `persona_edit` | `cockpit2.py:1988` |
| `persona_llm` | `cockpit2.py:2007` |
| `persona_finetune` | `cockpit2.py:2024` |
| `persona_finetune_apply` | `cockpit2.py:2042` |


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
_46 routes · 155 dispatch-acties · 29 stores._
