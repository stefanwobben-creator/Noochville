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
| `/keywords` | `render_keywords` | `nooch_village/views/keywords.py` |
| `/long-term-trends` | `render_long_term_trends` | `nooch_village/views/long_term_trends.py` |
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
| `kb_new` | `cockpit2.py:3039` |
| `kb_intake` | `cockpit2.py:3121` |
| `kb_intake_url` | `cockpit2.py:3138` |
| `kb_stage_edit` | `cockpit2.py:3157` |
| `kb_stage_delete` | `cockpit2.py:3164` |
| `kb_stage_merge` | `cockpit2.py:3170` |
| `kb_stage_commit` | `cockpit2.py:3181` |
| `kb_stage_discard` | `cockpit2.py:3195` |
| `kb_atoom_subject` | `cockpit2.py:3265` |
| `kb_atoom_edit` | `cockpit2.py:3201` |
| `kb_atoom_related` | `cockpit2.py:3208` |
| `kb_atoom_reference` | `cockpit2.py:3253` |
| `kb_insight_link` | `cockpit2.py:3220` |
| `kb_insight_unlink` | `cockpit2.py:3227` |
| `kb_meta_start` | `cockpit2.py:3233` |
| `kb_atoom_merge` | `cockpit2.py:3276` |
| `kb_atoom_archive` | `cockpit2.py:3292` |
| `kb_atoom_unarchive` | `cockpit2.py:3301` |
| `kb_atoom_naar_spel` | `cockpit2.py:3307` |
| `kb_spel_start` | `cockpit2.py:3327` |
| `kb_spel_add` | `cockpit2.py:3341` |
| `kb_spel_remove` | `cockpit2.py:3351` |
| `kb_spel_flip` | `cockpit2.py:3358` |
| `kb_spel_finish` | `cockpit2.py:3364` |
| `kb_link` | `cockpit2.py:3048` |
| `kb_unlink` | `cockpit2.py:3062` |
| `kb_annotate` | `cockpit2.py:3073` |
| `kb_evidence` | `cockpit2.py:3079` |
| `kb_discuss` | `cockpit2.py:3100` |
| `kb_reformulate` | `cockpit2.py:3106` |
| `proj_add` | `cockpit2.py:1104` |
| `artefact_add` | `cockpit2.py:1132` |
| `artefact_edit` | `cockpit2.py:1173` |
| `artefact_archive` | `cockpit2.py:1197` |
| `proj_status` | `cockpit2.py:1217` |
| `proj_done` | `cockpit2.py:1235` |
| `proj_archive` | `cockpit2.py:1257` |
| `proj_unarchive` | `cockpit2.py:1267` |
| `proj_delete` | `cockpit2.py:1277` |
| `proj_edit` | `cockpit2.py:1304` |
| `proj_comment` | `cockpit2.py:1317` |
| `proj_rename` | `cockpit2.py:1327` |
| `proj_describe` | `cockpit2.py:1338` |
| `proj_doc_edit` | `cockpit2.py:1371` |
| `proj_regen_doc` | `cockpit2.py:1349` |
| `proj_settrekker` | `cockpit2.py:1384` |
| `proj_setowner` | `cockpit2.py:1421` |
| `proj_approve` | `cockpit2.py:1440` |
| `proj_discard` | `cockpit2.py:1451` |
| `proj_setlabel` | `cockpit2.py:1462` |
| `proj_setimpact` | `cockpit2.py:1477` |
| `proj_seteffort` | `cockpit2.py:1496` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1519` |
| `proj_setprivate` | `cockpit2.py:1543` |
| `proj_setdue` | `cockpit2.py:1554` |
| `attach_add` | `cockpit2.py:1565` |
| `attach_remove` | `cockpit2.py:1576` |
| `react_add` | `cockpit2.py:1586` |
| `feed_edit` | `cockpit2.py:1596` |
| `feed_remove` | `cockpit2.py:1606` |
| `wall_outcome` | `cockpit2.py:2199` |
| `notif_read` | `cockpit2.py:2297` |
| `notif_processed` | `cockpit2.py:2302` |
| `notif_outcome` | `cockpit2.py:2449` |
| `notif_klaar` | `cockpit2.py:2435` |
| `notif_delete` | `cockpit2.py:2307` |
| `notif_add` | `cockpit2.py:2419` |
| `notif_archive` | `cockpit2.py:2536` |
| `metrics2_fav` | `cockpit2.py:2313` |
| `metrics2_unfav` | `cockpit2.py:2323` |
| `metrics2_form` | `cockpit2.py:2328` |
| `metrics2_dim` | `cockpit2.py:2334` |
| `metrics2_compare` | `cockpit2.py:2341` |
| `metrics2_formula` | `cockpit2.py:2404` |
| `source_activate` | `cockpit2.py:2387` |
| `source_deactivate` | `cockpit2.py:2396` |
| `link_pursue` | `cockpit2.py:2368` |
| `link_ignore` | `cockpit2.py:2378` |
| `acc_check` | `cockpit2.py:2349` |
| `ai_reply` | `cockpit2.py:1615` |
| `proj_feed` | `cockpit2.py:1626` |
| `checklist_add` | `cockpit2.py:1656` |
| `checklist_remove` | `cockpit2.py:1667` |
| `check_add` | `cockpit2.py:1715` |
| `check_accept` | `cockpit2.py:1732` |
| `check_toggle` | `cockpit2.py:1742` |
| `check_remove` | `cockpit2.py:1752` |
| `role_assign` | `cockpit2.py:1762` |
| `role_unassign` | `cockpit2.py:1780` |
| `role_focus` | `cockpit2.py:1799` |
| `radar_approve` | `cockpit2.py:1832` |
| `radar_dismiss` | `cockpit2.py:1836` |
| `aitask_add` | `cockpit2.py:1840` |
| `aitask_remove` | `cockpit2.py:1866` |
| `persona_skill_add` | `cockpit2.py:1883` |
| `rov2_add` | `cockpit2.py:1898` |
| `rov2_add_to_group` | `cockpit2.py:1910` |
| `rov2_remove` | `cockpit2.py:1922` |
| `rov2_remove_group` | `cockpit2.py:1937` |
| `rov2_setkind` | `cockpit2.py:1955` |
| `rov2_consent` | `cockpit2.py:1968` |
| `rov2_end` | `cockpit2.py:1990` |
| `wo_open` | `cockpit2.py:2014` |
| `wo_close` | `cockpit2.py:2024` |
| `wo_presence` | `cockpit2.py:2040` |
| `wo_present_all` | `cockpit2.py:2051` |
| `wo_ag_add` | `cockpit2.py:2063` |
| `wo_ag_remove` | `cockpit2.py:2075` |
| `wo_ag_note` | `cockpit2.py:2085` |
| `wo_ag_reopen` | `cockpit2.py:2097` |
| `wo_ag_resolve` | `cockpit2.py:2173` |
| `wo_checkout` | `cockpit2.py:2541` |
| `noochie_send` | `cockpit2.py:2553` |
| `noochie_reset` | `cockpit2.py:2579` |
| `noochie_ctx` | `cockpit2.py:2586` |
| `cl_add` | `cockpit2.py:2593` |
| `cl_report` | `cockpit2.py:2611` |
| `cl_remove` | `cockpit2.py:2626` |
| `m_add_kpi` | `cockpit2.py:2636` |
| `m_add_from_def` | `cockpit2.py:2668` |
| `def_add` | `cockpit2.py:2683` |
| `catalog_publish` | `cockpit2.py:2705` |
| `def_amend` | `cockpit2.py:2731` |
| `m_add_link` | `cockpit2.py:2773` |
| `m_sample` | `cockpit2.py:2784` |
| `m_remove` | `cockpit2.py:2794` |
| `m_pin` | `cockpit2.py:2804` |
| `m_unpin` | `cockpit2.py:2815` |
| `tile_add` | `cockpit2.py:2853` |
| `indicator_activate` | `cockpit2.py:2825` |
| `tile_remove` | `cockpit2.py:2887` |
| `rov2_set` | `cockpit2.py:2897` |
| `rov2_acc_add` | `cockpit2.py:2897` |
| `rov2_acc_remove` | `cockpit2.py:2897` |
| `rov2_dom_add` | `cockpit2.py:2897` |
| `rov2_dom_remove` | `cockpit2.py:2897` |
| `backlog_add` | `cockpit2.py:2929` |
| `backlog_update_staat` | `cockpit2.py:2941` |
| `backlog_update_prioriteit` | `cockpit2.py:2953` |
| `person_edit` | `cockpit2.py:2965` |
| `person_remove` | `cockpit2.py:2982` |
| `lk_mute` | `cockpit2.py:3003` |


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
