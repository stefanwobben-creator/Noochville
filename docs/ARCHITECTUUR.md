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
| `kb_new` | `cockpit2.py:3348` |
| `kb_intake` | `cockpit2.py:3430` |
| `kb_intake_url` | `cockpit2.py:3447` |
| `kb_stage_edit` | `cockpit2.py:3466` |
| `kb_stage_delete` | `cockpit2.py:3473` |
| `kb_stage_merge` | `cockpit2.py:3479` |
| `kb_stage_commit` | `cockpit2.py:3490` |
| `kb_stage_discard` | `cockpit2.py:3504` |
| `kb_atoom_subject` | `cockpit2.py:3574` |
| `kb_atoom_edit` | `cockpit2.py:3510` |
| `kb_atoom_related` | `cockpit2.py:3517` |
| `kb_atoom_reference` | `cockpit2.py:3562` |
| `kb_insight_link` | `cockpit2.py:3529` |
| `kb_insight_unlink` | `cockpit2.py:3536` |
| `kb_meta_start` | `cockpit2.py:3542` |
| `kb_atoom_merge` | `cockpit2.py:3585` |
| `kb_atoom_archive` | `cockpit2.py:3601` |
| `kb_atoom_unarchive` | `cockpit2.py:3610` |
| `kb_atoom_naar_spel` | `cockpit2.py:3616` |
| `kb_spel_start` | `cockpit2.py:3636` |
| `kb_spel_add` | `cockpit2.py:3650` |
| `kb_spel_remove` | `cockpit2.py:3660` |
| `kb_spel_flip` | `cockpit2.py:3667` |
| `kb_spel_finish` | `cockpit2.py:3673` |
| `kb_link` | `cockpit2.py:3357` |
| `kb_unlink` | `cockpit2.py:3371` |
| `kb_annotate` | `cockpit2.py:3382` |
| `kb_evidence` | `cockpit2.py:3388` |
| `kb_discuss` | `cockpit2.py:3409` |
| `kb_reformulate` | `cockpit2.py:3415` |
| `kw_nominate` | `cockpit2.py:3684` |
| `kw_nom_accept` | `cockpit2.py:3695` |
| `kw_nom_reject` | `cockpit2.py:3713` |
| `ws_forbid` | `cockpit2.py:3743` |
| `ws_approve` | `cockpit2.py:3748` |
| `proj_add` | `cockpit2.py:1115` |
| `artefact_add` | `cockpit2.py:1143` |
| `artefact_edit` | `cockpit2.py:1184` |
| `artefact_archive` | `cockpit2.py:1208` |
| `proj_status` | `cockpit2.py:1228` |
| `proj_done` | `cockpit2.py:1246` |
| `proj_archive` | `cockpit2.py:1268` |
| `proj_unarchive` | `cockpit2.py:1278` |
| `proj_delete` | `cockpit2.py:1288` |
| `proj_edit` | `cockpit2.py:1315` |
| `proj_comment` | `cockpit2.py:1328` |
| `proj_rename` | `cockpit2.py:1338` |
| `proj_describe` | `cockpit2.py:1349` |
| `proj_doc_edit` | `cockpit2.py:1382` |
| `proj_regen_doc` | `cockpit2.py:1360` |
| `proj_settrekker` | `cockpit2.py:1395` |
| `proj_setowner` | `cockpit2.py:1432` |
| `proj_approve` | `cockpit2.py:1451` |
| `proj_discard` | `cockpit2.py:1462` |
| `proj_setlabel` | `cockpit2.py:1473` |
| `proj_setimpact` | `cockpit2.py:1488` |
| `proj_seteffort` | `cockpit2.py:1507` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1530` |
| `proj_setprivate` | `cockpit2.py:1554` |
| `proj_setdue` | `cockpit2.py:1565` |
| `attach_add` | `cockpit2.py:1576` |
| `attach_remove` | `cockpit2.py:1587` |
| `react_add` | `cockpit2.py:1597` |
| `feed_edit` | `cockpit2.py:1607` |
| `feed_remove` | `cockpit2.py:1617` |
| `wall_outcome` | `cockpit2.py:2346` |
| `notif_read` | `cockpit2.py:2444` |
| `notif_processed` | `cockpit2.py:2449` |
| `notif_outcome` | `cockpit2.py:2596` |
| `notif_klaar` | `cockpit2.py:2582` |
| `notif_delete` | `cockpit2.py:2454` |
| `notif_add` | `cockpit2.py:2566` |
| `notif_archive` | `cockpit2.py:2683` |
| `metrics2_fav` | `cockpit2.py:2460` |
| `metrics2_unfav` | `cockpit2.py:2470` |
| `metrics2_form` | `cockpit2.py:2475` |
| `metrics2_dim` | `cockpit2.py:2481` |
| `metrics2_compare` | `cockpit2.py:2488` |
| `metrics2_formula` | `cockpit2.py:2551` |
| `source_activate` | `cockpit2.py:2534` |
| `source_deactivate` | `cockpit2.py:2543` |
| `link_pursue` | `cockpit2.py:2515` |
| `link_ignore` | `cockpit2.py:2525` |
| `acc_check` | `cockpit2.py:2496` |
| `ai_reply` | `cockpit2.py:1626` |
| `proj_feed` | `cockpit2.py:1637` |
| `checklist_add` | `cockpit2.py:1667` |
| `checklist_remove` | `cockpit2.py:1678` |
| `check_add` | `cockpit2.py:1726` |
| `check_accept` | `cockpit2.py:1743` |
| `check_toggle` | `cockpit2.py:1753` |
| `check_remove` | `cockpit2.py:1763` |
| `role_assign` | `cockpit2.py:1773` |
| `role_unassign` | `cockpit2.py:1791` |
| `role_focus` | `cockpit2.py:1810` |
| `radar_approve` | `cockpit2.py:1843` |
| `radar_dismiss` | `cockpit2.py:1847` |
| `aitask_add` | `cockpit2.py:1851` |
| `aitask_remove` | `cockpit2.py:1877` |
| `persona_skill_add` | `cockpit2.py:2030` |
| `rov2_add` | `cockpit2.py:2045` |
| `rov2_add_to_group` | `cockpit2.py:2057` |
| `rov2_remove` | `cockpit2.py:2069` |
| `rov2_remove_group` | `cockpit2.py:2084` |
| `rov2_setkind` | `cockpit2.py:2102` |
| `rov2_consent` | `cockpit2.py:2115` |
| `rov2_end` | `cockpit2.py:2137` |
| `wo_open` | `cockpit2.py:2161` |
| `wo_close` | `cockpit2.py:2171` |
| `wo_presence` | `cockpit2.py:2187` |
| `wo_present_all` | `cockpit2.py:2198` |
| `wo_ag_add` | `cockpit2.py:2210` |
| `wo_ag_remove` | `cockpit2.py:2222` |
| `wo_ag_note` | `cockpit2.py:2232` |
| `wo_ag_reopen` | `cockpit2.py:2244` |
| `wo_ag_resolve` | `cockpit2.py:2320` |
| `wo_checkout` | `cockpit2.py:2688` |
| `noochie_send` | `cockpit2.py:2700` |
| `noochie_reset` | `cockpit2.py:2726` |
| `noochie_ctx` | `cockpit2.py:2733` |
| `cl_add` | `cockpit2.py:2740` |
| `cl_report` | `cockpit2.py:2758` |
| `cl_remove` | `cockpit2.py:2773` |
| `m_add_kpi` | `cockpit2.py:2783` |
| `m_add_from_def` | `cockpit2.py:2815` |
| `def_add` | `cockpit2.py:2830` |
| `catalog_publish` | `cockpit2.py:2852` |
| `def_amend` | `cockpit2.py:2878` |
| `m_add_link` | `cockpit2.py:2920` |
| `m_sample` | `cockpit2.py:2931` |
| `m_remove` | `cockpit2.py:2941` |
| `m_pin` | `cockpit2.py:2951` |
| `m_unpin` | `cockpit2.py:2962` |
| `tile_add` | `cockpit2.py:3000` |
| `indicator_activate` | `cockpit2.py:2972` |
| `tile_remove` | `cockpit2.py:3034` |
| `rov2_set` | `cockpit2.py:3044` |
| `rov2_acc_add` | `cockpit2.py:3044` |
| `rov2_acc_remove` | `cockpit2.py:3044` |
| `rov2_dom_add` | `cockpit2.py:3044` |
| `rov2_dom_remove` | `cockpit2.py:3044` |
| `backlog_add` | `cockpit2.py:3076` |
| `backlog_update_staat` | `cockpit2.py:3088` |
| `backlog_update_prioriteit` | `cockpit2.py:3100` |
| `person_edit` | `cockpit2.py:3112` |
| `person_remove` | `cockpit2.py:3129` |
| `lk_mute` | `cockpit2.py:3150` |
| `claims_term_add` | `cockpit2.py:3242` |
| `claims_work_status` | `cockpit2.py:3265` |
| `claims_to_board` | `cockpit2.py:3284` |
| `persona_edit` | `cockpit2.py:1929` |
| `persona_llm` | `cockpit2.py:1948` |
| `persona_finetune` | `cockpit2.py:1965` |
| `persona_finetune_apply` | `cockpit2.py:1983` |


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
_46 routes · 154 dispatch-acties · 29 stores._
