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
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `kb_new` | `cockpit2.py:3038` |
| `kb_intake` | `cockpit2.py:3120` |
| `kb_intake_url` | `cockpit2.py:3137` |
| `kb_stage_edit` | `cockpit2.py:3156` |
| `kb_stage_delete` | `cockpit2.py:3163` |
| `kb_stage_merge` | `cockpit2.py:3169` |
| `kb_stage_commit` | `cockpit2.py:3180` |
| `kb_stage_discard` | `cockpit2.py:3194` |
| `kb_atoom_subject` | `cockpit2.py:3264` |
| `kb_atoom_edit` | `cockpit2.py:3200` |
| `kb_atoom_related` | `cockpit2.py:3207` |
| `kb_atoom_reference` | `cockpit2.py:3252` |
| `kb_insight_link` | `cockpit2.py:3219` |
| `kb_insight_unlink` | `cockpit2.py:3226` |
| `kb_meta_start` | `cockpit2.py:3232` |
| `kb_atoom_merge` | `cockpit2.py:3275` |
| `kb_atoom_archive` | `cockpit2.py:3291` |
| `kb_atoom_unarchive` | `cockpit2.py:3300` |
| `kb_atoom_naar_spel` | `cockpit2.py:3306` |
| `kb_spel_start` | `cockpit2.py:3326` |
| `kb_spel_add` | `cockpit2.py:3340` |
| `kb_spel_remove` | `cockpit2.py:3350` |
| `kb_spel_flip` | `cockpit2.py:3357` |
| `kb_spel_finish` | `cockpit2.py:3363` |
| `kb_link` | `cockpit2.py:3047` |
| `kb_unlink` | `cockpit2.py:3061` |
| `kb_annotate` | `cockpit2.py:3072` |
| `kb_evidence` | `cockpit2.py:3078` |
| `kb_discuss` | `cockpit2.py:3099` |
| `kb_reformulate` | `cockpit2.py:3105` |
| `proj_add` | `cockpit2.py:1103` |
| `artefact_add` | `cockpit2.py:1131` |
| `artefact_edit` | `cockpit2.py:1172` |
| `artefact_archive` | `cockpit2.py:1196` |
| `proj_status` | `cockpit2.py:1216` |
| `proj_done` | `cockpit2.py:1234` |
| `proj_archive` | `cockpit2.py:1256` |
| `proj_unarchive` | `cockpit2.py:1266` |
| `proj_delete` | `cockpit2.py:1276` |
| `proj_edit` | `cockpit2.py:1303` |
| `proj_comment` | `cockpit2.py:1316` |
| `proj_rename` | `cockpit2.py:1326` |
| `proj_describe` | `cockpit2.py:1337` |
| `proj_doc_edit` | `cockpit2.py:1370` |
| `proj_regen_doc` | `cockpit2.py:1348` |
| `proj_settrekker` | `cockpit2.py:1383` |
| `proj_setowner` | `cockpit2.py:1420` |
| `proj_approve` | `cockpit2.py:1439` |
| `proj_discard` | `cockpit2.py:1450` |
| `proj_setlabel` | `cockpit2.py:1461` |
| `proj_setimpact` | `cockpit2.py:1476` |
| `proj_seteffort` | `cockpit2.py:1495` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1518` |
| `proj_setprivate` | `cockpit2.py:1542` |
| `proj_setdue` | `cockpit2.py:1553` |
| `attach_add` | `cockpit2.py:1564` |
| `attach_remove` | `cockpit2.py:1575` |
| `react_add` | `cockpit2.py:1585` |
| `feed_edit` | `cockpit2.py:1595` |
| `feed_remove` | `cockpit2.py:1605` |
| `wall_outcome` | `cockpit2.py:2198` |
| `notif_read` | `cockpit2.py:2296` |
| `notif_processed` | `cockpit2.py:2301` |
| `notif_outcome` | `cockpit2.py:2448` |
| `notif_klaar` | `cockpit2.py:2434` |
| `notif_delete` | `cockpit2.py:2306` |
| `notif_add` | `cockpit2.py:2418` |
| `notif_archive` | `cockpit2.py:2535` |
| `metrics2_fav` | `cockpit2.py:2312` |
| `metrics2_unfav` | `cockpit2.py:2322` |
| `metrics2_form` | `cockpit2.py:2327` |
| `metrics2_dim` | `cockpit2.py:2333` |
| `metrics2_compare` | `cockpit2.py:2340` |
| `metrics2_formula` | `cockpit2.py:2403` |
| `source_activate` | `cockpit2.py:2386` |
| `source_deactivate` | `cockpit2.py:2395` |
| `link_pursue` | `cockpit2.py:2367` |
| `link_ignore` | `cockpit2.py:2377` |
| `acc_check` | `cockpit2.py:2348` |
| `ai_reply` | `cockpit2.py:1614` |
| `proj_feed` | `cockpit2.py:1625` |
| `checklist_add` | `cockpit2.py:1655` |
| `checklist_remove` | `cockpit2.py:1666` |
| `check_add` | `cockpit2.py:1714` |
| `check_accept` | `cockpit2.py:1731` |
| `check_toggle` | `cockpit2.py:1741` |
| `check_remove` | `cockpit2.py:1751` |
| `role_assign` | `cockpit2.py:1761` |
| `role_unassign` | `cockpit2.py:1779` |
| `role_focus` | `cockpit2.py:1798` |
| `radar_approve` | `cockpit2.py:1831` |
| `radar_dismiss` | `cockpit2.py:1835` |
| `aitask_add` | `cockpit2.py:1839` |
| `aitask_remove` | `cockpit2.py:1865` |
| `persona_skill_add` | `cockpit2.py:1882` |
| `rov2_add` | `cockpit2.py:1897` |
| `rov2_add_to_group` | `cockpit2.py:1909` |
| `rov2_remove` | `cockpit2.py:1921` |
| `rov2_remove_group` | `cockpit2.py:1936` |
| `rov2_setkind` | `cockpit2.py:1954` |
| `rov2_consent` | `cockpit2.py:1967` |
| `rov2_end` | `cockpit2.py:1989` |
| `wo_open` | `cockpit2.py:2013` |
| `wo_close` | `cockpit2.py:2023` |
| `wo_presence` | `cockpit2.py:2039` |
| `wo_present_all` | `cockpit2.py:2050` |
| `wo_ag_add` | `cockpit2.py:2062` |
| `wo_ag_remove` | `cockpit2.py:2074` |
| `wo_ag_note` | `cockpit2.py:2084` |
| `wo_ag_reopen` | `cockpit2.py:2096` |
| `wo_ag_resolve` | `cockpit2.py:2172` |
| `wo_checkout` | `cockpit2.py:2540` |
| `noochie_send` | `cockpit2.py:2552` |
| `noochie_reset` | `cockpit2.py:2578` |
| `noochie_ctx` | `cockpit2.py:2585` |
| `cl_add` | `cockpit2.py:2592` |
| `cl_report` | `cockpit2.py:2610` |
| `cl_remove` | `cockpit2.py:2625` |
| `m_add_kpi` | `cockpit2.py:2635` |
| `m_add_from_def` | `cockpit2.py:2667` |
| `def_add` | `cockpit2.py:2682` |
| `catalog_publish` | `cockpit2.py:2704` |
| `def_amend` | `cockpit2.py:2730` |
| `m_add_link` | `cockpit2.py:2772` |
| `m_sample` | `cockpit2.py:2783` |
| `m_remove` | `cockpit2.py:2793` |
| `m_pin` | `cockpit2.py:2803` |
| `m_unpin` | `cockpit2.py:2814` |
| `tile_add` | `cockpit2.py:2852` |
| `indicator_activate` | `cockpit2.py:2824` |
| `tile_remove` | `cockpit2.py:2886` |
| `rov2_set` | `cockpit2.py:2896` |
| `rov2_acc_add` | `cockpit2.py:2896` |
| `rov2_acc_remove` | `cockpit2.py:2896` |
| `rov2_dom_add` | `cockpit2.py:2896` |
| `rov2_dom_remove` | `cockpit2.py:2896` |
| `backlog_add` | `cockpit2.py:2928` |
| `backlog_update_staat` | `cockpit2.py:2940` |
| `backlog_update_prioriteit` | `cockpit2.py:2952` |
| `person_edit` | `cockpit2.py:2964` |
| `person_remove` | `cockpit2.py:2981` |
| `lk_mute` | `cockpit2.py:3002` |


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


---
_42 routes · 142 dispatch-acties · 26 stores._
