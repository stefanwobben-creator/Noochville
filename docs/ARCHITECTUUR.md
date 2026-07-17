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
| `kb_new` | `cockpit2.py:3043` |
| `kb_intake` | `cockpit2.py:3125` |
| `kb_intake_url` | `cockpit2.py:3142` |
| `kb_stage_edit` | `cockpit2.py:3161` |
| `kb_stage_delete` | `cockpit2.py:3168` |
| `kb_stage_merge` | `cockpit2.py:3174` |
| `kb_stage_commit` | `cockpit2.py:3185` |
| `kb_stage_discard` | `cockpit2.py:3199` |
| `kb_atoom_subject` | `cockpit2.py:3269` |
| `kb_atoom_edit` | `cockpit2.py:3205` |
| `kb_atoom_related` | `cockpit2.py:3212` |
| `kb_atoom_reference` | `cockpit2.py:3257` |
| `kb_insight_link` | `cockpit2.py:3224` |
| `kb_insight_unlink` | `cockpit2.py:3231` |
| `kb_meta_start` | `cockpit2.py:3237` |
| `kb_atoom_merge` | `cockpit2.py:3280` |
| `kb_atoom_archive` | `cockpit2.py:3296` |
| `kb_atoom_unarchive` | `cockpit2.py:3305` |
| `kb_atoom_naar_spel` | `cockpit2.py:3311` |
| `kb_spel_start` | `cockpit2.py:3331` |
| `kb_spel_add` | `cockpit2.py:3345` |
| `kb_spel_remove` | `cockpit2.py:3355` |
| `kb_spel_flip` | `cockpit2.py:3362` |
| `kb_spel_finish` | `cockpit2.py:3368` |
| `kb_link` | `cockpit2.py:3052` |
| `kb_unlink` | `cockpit2.py:3066` |
| `kb_annotate` | `cockpit2.py:3077` |
| `kb_evidence` | `cockpit2.py:3083` |
| `kb_discuss` | `cockpit2.py:3104` |
| `kb_reformulate` | `cockpit2.py:3110` |
| `kw_nominate` | `cockpit2.py:3379` |
| `kw_nom_accept` | `cockpit2.py:3390` |
| `kw_nom_reject` | `cockpit2.py:3408` |
| `proj_add` | `cockpit2.py:1108` |
| `artefact_add` | `cockpit2.py:1136` |
| `artefact_edit` | `cockpit2.py:1177` |
| `artefact_archive` | `cockpit2.py:1201` |
| `proj_status` | `cockpit2.py:1221` |
| `proj_done` | `cockpit2.py:1239` |
| `proj_archive` | `cockpit2.py:1261` |
| `proj_unarchive` | `cockpit2.py:1271` |
| `proj_delete` | `cockpit2.py:1281` |
| `proj_edit` | `cockpit2.py:1308` |
| `proj_comment` | `cockpit2.py:1321` |
| `proj_rename` | `cockpit2.py:1331` |
| `proj_describe` | `cockpit2.py:1342` |
| `proj_doc_edit` | `cockpit2.py:1375` |
| `proj_regen_doc` | `cockpit2.py:1353` |
| `proj_settrekker` | `cockpit2.py:1388` |
| `proj_setowner` | `cockpit2.py:1425` |
| `proj_approve` | `cockpit2.py:1444` |
| `proj_discard` | `cockpit2.py:1455` |
| `proj_setlabel` | `cockpit2.py:1466` |
| `proj_setimpact` | `cockpit2.py:1481` |
| `proj_seteffort` | `cockpit2.py:1500` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1523` |
| `proj_setprivate` | `cockpit2.py:1547` |
| `proj_setdue` | `cockpit2.py:1558` |
| `attach_add` | `cockpit2.py:1569` |
| `attach_remove` | `cockpit2.py:1580` |
| `react_add` | `cockpit2.py:1590` |
| `feed_edit` | `cockpit2.py:1600` |
| `feed_remove` | `cockpit2.py:1610` |
| `wall_outcome` | `cockpit2.py:2203` |
| `notif_read` | `cockpit2.py:2301` |
| `notif_processed` | `cockpit2.py:2306` |
| `notif_outcome` | `cockpit2.py:2453` |
| `notif_klaar` | `cockpit2.py:2439` |
| `notif_delete` | `cockpit2.py:2311` |
| `notif_add` | `cockpit2.py:2423` |
| `notif_archive` | `cockpit2.py:2540` |
| `metrics2_fav` | `cockpit2.py:2317` |
| `metrics2_unfav` | `cockpit2.py:2327` |
| `metrics2_form` | `cockpit2.py:2332` |
| `metrics2_dim` | `cockpit2.py:2338` |
| `metrics2_compare` | `cockpit2.py:2345` |
| `metrics2_formula` | `cockpit2.py:2408` |
| `source_activate` | `cockpit2.py:2391` |
| `source_deactivate` | `cockpit2.py:2400` |
| `link_pursue` | `cockpit2.py:2372` |
| `link_ignore` | `cockpit2.py:2382` |
| `acc_check` | `cockpit2.py:2353` |
| `ai_reply` | `cockpit2.py:1619` |
| `proj_feed` | `cockpit2.py:1630` |
| `checklist_add` | `cockpit2.py:1660` |
| `checklist_remove` | `cockpit2.py:1671` |
| `check_add` | `cockpit2.py:1719` |
| `check_accept` | `cockpit2.py:1736` |
| `check_toggle` | `cockpit2.py:1746` |
| `check_remove` | `cockpit2.py:1756` |
| `role_assign` | `cockpit2.py:1766` |
| `role_unassign` | `cockpit2.py:1784` |
| `role_focus` | `cockpit2.py:1803` |
| `radar_approve` | `cockpit2.py:1836` |
| `radar_dismiss` | `cockpit2.py:1840` |
| `aitask_add` | `cockpit2.py:1844` |
| `aitask_remove` | `cockpit2.py:1870` |
| `persona_skill_add` | `cockpit2.py:1887` |
| `rov2_add` | `cockpit2.py:1902` |
| `rov2_add_to_group` | `cockpit2.py:1914` |
| `rov2_remove` | `cockpit2.py:1926` |
| `rov2_remove_group` | `cockpit2.py:1941` |
| `rov2_setkind` | `cockpit2.py:1959` |
| `rov2_consent` | `cockpit2.py:1972` |
| `rov2_end` | `cockpit2.py:1994` |
| `wo_open` | `cockpit2.py:2018` |
| `wo_close` | `cockpit2.py:2028` |
| `wo_presence` | `cockpit2.py:2044` |
| `wo_present_all` | `cockpit2.py:2055` |
| `wo_ag_add` | `cockpit2.py:2067` |
| `wo_ag_remove` | `cockpit2.py:2079` |
| `wo_ag_note` | `cockpit2.py:2089` |
| `wo_ag_reopen` | `cockpit2.py:2101` |
| `wo_ag_resolve` | `cockpit2.py:2177` |
| `wo_checkout` | `cockpit2.py:2545` |
| `noochie_send` | `cockpit2.py:2557` |
| `noochie_reset` | `cockpit2.py:2583` |
| `noochie_ctx` | `cockpit2.py:2590` |
| `cl_add` | `cockpit2.py:2597` |
| `cl_report` | `cockpit2.py:2615` |
| `cl_remove` | `cockpit2.py:2630` |
| `m_add_kpi` | `cockpit2.py:2640` |
| `m_add_from_def` | `cockpit2.py:2672` |
| `def_add` | `cockpit2.py:2687` |
| `catalog_publish` | `cockpit2.py:2709` |
| `def_amend` | `cockpit2.py:2735` |
| `m_add_link` | `cockpit2.py:2777` |
| `m_sample` | `cockpit2.py:2788` |
| `m_remove` | `cockpit2.py:2798` |
| `m_pin` | `cockpit2.py:2808` |
| `m_unpin` | `cockpit2.py:2819` |
| `tile_add` | `cockpit2.py:2857` |
| `indicator_activate` | `cockpit2.py:2829` |
| `tile_remove` | `cockpit2.py:2891` |
| `rov2_set` | `cockpit2.py:2901` |
| `rov2_acc_add` | `cockpit2.py:2901` |
| `rov2_acc_remove` | `cockpit2.py:2901` |
| `rov2_dom_add` | `cockpit2.py:2901` |
| `rov2_dom_remove` | `cockpit2.py:2901` |
| `backlog_add` | `cockpit2.py:2933` |
| `backlog_update_staat` | `cockpit2.py:2945` |
| `backlog_update_prioriteit` | `cockpit2.py:2957` |
| `person_edit` | `cockpit2.py:2969` |
| `person_remove` | `cockpit2.py:2986` |
| `lk_mute` | `cockpit2.py:3007` |


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
_42 routes · 145 dispatch-acties · 29 stores._
