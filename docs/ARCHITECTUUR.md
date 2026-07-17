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
| `kb_new` | `cockpit2.py:3037` |
| `kb_intake` | `cockpit2.py:3119` |
| `kb_intake_url` | `cockpit2.py:3136` |
| `kb_stage_edit` | `cockpit2.py:3155` |
| `kb_stage_delete` | `cockpit2.py:3162` |
| `kb_stage_merge` | `cockpit2.py:3168` |
| `kb_stage_commit` | `cockpit2.py:3179` |
| `kb_stage_discard` | `cockpit2.py:3193` |
| `kb_atoom_subject` | `cockpit2.py:3218` |
| `kb_atoom_edit` | `cockpit2.py:3199` |
| `kb_atoom_related` | `cockpit2.py:3206` |
| `kb_atoom_merge` | `cockpit2.py:3229` |
| `kb_atoom_archive` | `cockpit2.py:3245` |
| `kb_atoom_unarchive` | `cockpit2.py:3254` |
| `kb_atoom_naar_spel` | `cockpit2.py:3260` |
| `kb_spel_start` | `cockpit2.py:3280` |
| `kb_spel_add` | `cockpit2.py:3294` |
| `kb_spel_remove` | `cockpit2.py:3304` |
| `kb_spel_flip` | `cockpit2.py:3311` |
| `kb_spel_finish` | `cockpit2.py:3317` |
| `kb_link` | `cockpit2.py:3046` |
| `kb_unlink` | `cockpit2.py:3060` |
| `kb_annotate` | `cockpit2.py:3071` |
| `kb_evidence` | `cockpit2.py:3077` |
| `kb_discuss` | `cockpit2.py:3098` |
| `kb_reformulate` | `cockpit2.py:3104` |
| `proj_add` | `cockpit2.py:1102` |
| `artefact_add` | `cockpit2.py:1130` |
| `artefact_edit` | `cockpit2.py:1171` |
| `artefact_archive` | `cockpit2.py:1195` |
| `proj_status` | `cockpit2.py:1215` |
| `proj_done` | `cockpit2.py:1233` |
| `proj_archive` | `cockpit2.py:1255` |
| `proj_unarchive` | `cockpit2.py:1265` |
| `proj_delete` | `cockpit2.py:1275` |
| `proj_edit` | `cockpit2.py:1302` |
| `proj_comment` | `cockpit2.py:1315` |
| `proj_rename` | `cockpit2.py:1325` |
| `proj_describe` | `cockpit2.py:1336` |
| `proj_doc_edit` | `cockpit2.py:1369` |
| `proj_regen_doc` | `cockpit2.py:1347` |
| `proj_settrekker` | `cockpit2.py:1382` |
| `proj_setowner` | `cockpit2.py:1419` |
| `proj_approve` | `cockpit2.py:1438` |
| `proj_discard` | `cockpit2.py:1449` |
| `proj_setlabel` | `cockpit2.py:1460` |
| `proj_setimpact` | `cockpit2.py:1475` |
| `proj_seteffort` | `cockpit2.py:1494` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1517` |
| `proj_setprivate` | `cockpit2.py:1541` |
| `proj_setdue` | `cockpit2.py:1552` |
| `attach_add` | `cockpit2.py:1563` |
| `attach_remove` | `cockpit2.py:1574` |
| `react_add` | `cockpit2.py:1584` |
| `feed_edit` | `cockpit2.py:1594` |
| `feed_remove` | `cockpit2.py:1604` |
| `wall_outcome` | `cockpit2.py:2197` |
| `notif_read` | `cockpit2.py:2295` |
| `notif_processed` | `cockpit2.py:2300` |
| `notif_outcome` | `cockpit2.py:2447` |
| `notif_klaar` | `cockpit2.py:2433` |
| `notif_delete` | `cockpit2.py:2305` |
| `notif_add` | `cockpit2.py:2417` |
| `notif_archive` | `cockpit2.py:2534` |
| `metrics2_fav` | `cockpit2.py:2311` |
| `metrics2_unfav` | `cockpit2.py:2321` |
| `metrics2_form` | `cockpit2.py:2326` |
| `metrics2_dim` | `cockpit2.py:2332` |
| `metrics2_compare` | `cockpit2.py:2339` |
| `metrics2_formula` | `cockpit2.py:2402` |
| `source_activate` | `cockpit2.py:2385` |
| `source_deactivate` | `cockpit2.py:2394` |
| `link_pursue` | `cockpit2.py:2366` |
| `link_ignore` | `cockpit2.py:2376` |
| `acc_check` | `cockpit2.py:2347` |
| `ai_reply` | `cockpit2.py:1613` |
| `proj_feed` | `cockpit2.py:1624` |
| `checklist_add` | `cockpit2.py:1654` |
| `checklist_remove` | `cockpit2.py:1665` |
| `check_add` | `cockpit2.py:1713` |
| `check_accept` | `cockpit2.py:1730` |
| `check_toggle` | `cockpit2.py:1740` |
| `check_remove` | `cockpit2.py:1750` |
| `role_assign` | `cockpit2.py:1760` |
| `role_unassign` | `cockpit2.py:1778` |
| `role_focus` | `cockpit2.py:1797` |
| `radar_approve` | `cockpit2.py:1830` |
| `radar_dismiss` | `cockpit2.py:1834` |
| `aitask_add` | `cockpit2.py:1838` |
| `aitask_remove` | `cockpit2.py:1864` |
| `persona_skill_add` | `cockpit2.py:1881` |
| `rov2_add` | `cockpit2.py:1896` |
| `rov2_add_to_group` | `cockpit2.py:1908` |
| `rov2_remove` | `cockpit2.py:1920` |
| `rov2_remove_group` | `cockpit2.py:1935` |
| `rov2_setkind` | `cockpit2.py:1953` |
| `rov2_consent` | `cockpit2.py:1966` |
| `rov2_end` | `cockpit2.py:1988` |
| `wo_open` | `cockpit2.py:2012` |
| `wo_close` | `cockpit2.py:2022` |
| `wo_presence` | `cockpit2.py:2038` |
| `wo_present_all` | `cockpit2.py:2049` |
| `wo_ag_add` | `cockpit2.py:2061` |
| `wo_ag_remove` | `cockpit2.py:2073` |
| `wo_ag_note` | `cockpit2.py:2083` |
| `wo_ag_reopen` | `cockpit2.py:2095` |
| `wo_ag_resolve` | `cockpit2.py:2171` |
| `wo_checkout` | `cockpit2.py:2539` |
| `noochie_send` | `cockpit2.py:2551` |
| `noochie_reset` | `cockpit2.py:2577` |
| `noochie_ctx` | `cockpit2.py:2584` |
| `cl_add` | `cockpit2.py:2591` |
| `cl_report` | `cockpit2.py:2609` |
| `cl_remove` | `cockpit2.py:2624` |
| `m_add_kpi` | `cockpit2.py:2634` |
| `m_add_from_def` | `cockpit2.py:2666` |
| `def_add` | `cockpit2.py:2681` |
| `catalog_publish` | `cockpit2.py:2703` |
| `def_amend` | `cockpit2.py:2729` |
| `m_add_link` | `cockpit2.py:2771` |
| `m_sample` | `cockpit2.py:2782` |
| `m_remove` | `cockpit2.py:2792` |
| `m_pin` | `cockpit2.py:2802` |
| `m_unpin` | `cockpit2.py:2813` |
| `tile_add` | `cockpit2.py:2851` |
| `indicator_activate` | `cockpit2.py:2823` |
| `tile_remove` | `cockpit2.py:2885` |
| `rov2_set` | `cockpit2.py:2895` |
| `rov2_acc_add` | `cockpit2.py:2895` |
| `rov2_acc_remove` | `cockpit2.py:2895` |
| `rov2_dom_add` | `cockpit2.py:2895` |
| `rov2_dom_remove` | `cockpit2.py:2895` |
| `backlog_add` | `cockpit2.py:2927` |
| `backlog_update_staat` | `cockpit2.py:2939` |
| `backlog_update_prioriteit` | `cockpit2.py:2951` |
| `person_edit` | `cockpit2.py:2963` |
| `person_remove` | `cockpit2.py:2980` |
| `lk_mute` | `cockpit2.py:3001` |


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
_40 routes · 138 dispatch-acties · 26 stores._
