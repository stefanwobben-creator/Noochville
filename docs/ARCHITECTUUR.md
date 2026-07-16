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
| `proj_add` | `cockpit2.py:1078` |
| `artefact_add` | `cockpit2.py:1106` |
| `artefact_edit` | `cockpit2.py:1147` |
| `artefact_archive` | `cockpit2.py:1171` |
| `proj_status` | `cockpit2.py:1191` |
| `proj_done` | `cockpit2.py:1209` |
| `proj_archive` | `cockpit2.py:1231` |
| `proj_unarchive` | `cockpit2.py:1241` |
| `proj_delete` | `cockpit2.py:1251` |
| `proj_edit` | `cockpit2.py:1278` |
| `proj_comment` | `cockpit2.py:1291` |
| `proj_rename` | `cockpit2.py:1301` |
| `proj_describe` | `cockpit2.py:1312` |
| `proj_doc_edit` | `cockpit2.py:1345` |
| `proj_regen_doc` | `cockpit2.py:1323` |
| `proj_settrekker` | `cockpit2.py:1358` |
| `proj_setowner` | `cockpit2.py:1395` |
| `proj_approve` | `cockpit2.py:1414` |
| `proj_discard` | `cockpit2.py:1425` |
| `proj_setlabel` | `cockpit2.py:1436` |
| `proj_setimpact` | `cockpit2.py:1451` |
| `proj_seteffort` | `cockpit2.py:1470` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1493` |
| `proj_setprivate` | `cockpit2.py:1517` |
| `proj_setdue` | `cockpit2.py:1528` |
| `attach_add` | `cockpit2.py:1539` |
| `attach_remove` | `cockpit2.py:1550` |
| `react_add` | `cockpit2.py:1560` |
| `feed_edit` | `cockpit2.py:1570` |
| `feed_remove` | `cockpit2.py:1580` |
| `wall_outcome` | `cockpit2.py:2173` |
| `notif_read` | `cockpit2.py:2271` |
| `notif_processed` | `cockpit2.py:2276` |
| `notif_outcome` | `cockpit2.py:2385` |
| `notif_klaar` | `cockpit2.py:2371` |
| `notif_delete` | `cockpit2.py:2281` |
| `notif_add` | `cockpit2.py:2355` |
| `notif_archive` | `cockpit2.py:2472` |
| `metrics2_fav` | `cockpit2.py:2287` |
| `metrics2_unfav` | `cockpit2.py:2297` |
| `metrics2_form` | `cockpit2.py:2302` |
| `metrics2_dim` | `cockpit2.py:2308` |
| `metrics2_compare` | `cockpit2.py:2315` |
| `metrics2_formula` | `cockpit2.py:2340` |
| `source_activate` | `cockpit2.py:2323` |
| `source_deactivate` | `cockpit2.py:2332` |
| `ai_reply` | `cockpit2.py:1589` |
| `proj_feed` | `cockpit2.py:1600` |
| `checklist_add` | `cockpit2.py:1630` |
| `checklist_remove` | `cockpit2.py:1641` |
| `check_add` | `cockpit2.py:1689` |
| `check_accept` | `cockpit2.py:1706` |
| `check_toggle` | `cockpit2.py:1716` |
| `check_remove` | `cockpit2.py:1726` |
| `role_assign` | `cockpit2.py:1736` |
| `role_unassign` | `cockpit2.py:1754` |
| `role_focus` | `cockpit2.py:1773` |
| `radar_approve` | `cockpit2.py:1806` |
| `radar_dismiss` | `cockpit2.py:1810` |
| `aitask_add` | `cockpit2.py:1814` |
| `aitask_remove` | `cockpit2.py:1840` |
| `persona_skill_add` | `cockpit2.py:1857` |
| `rov2_add` | `cockpit2.py:1872` |
| `rov2_add_to_group` | `cockpit2.py:1884` |
| `rov2_remove` | `cockpit2.py:1896` |
| `rov2_remove_group` | `cockpit2.py:1911` |
| `rov2_setkind` | `cockpit2.py:1929` |
| `rov2_consent` | `cockpit2.py:1942` |
| `rov2_end` | `cockpit2.py:1964` |
| `wo_open` | `cockpit2.py:1988` |
| `wo_close` | `cockpit2.py:1998` |
| `wo_presence` | `cockpit2.py:2014` |
| `wo_present_all` | `cockpit2.py:2025` |
| `wo_ag_add` | `cockpit2.py:2037` |
| `wo_ag_remove` | `cockpit2.py:2049` |
| `wo_ag_note` | `cockpit2.py:2059` |
| `wo_ag_reopen` | `cockpit2.py:2071` |
| `wo_ag_resolve` | `cockpit2.py:2147` |
| `wo_checkout` | `cockpit2.py:2477` |
| `noochie_send` | `cockpit2.py:2489` |
| `noochie_reset` | `cockpit2.py:2515` |
| `noochie_ctx` | `cockpit2.py:2522` |
| `cl_add` | `cockpit2.py:2529` |
| `cl_report` | `cockpit2.py:2547` |
| `cl_remove` | `cockpit2.py:2562` |
| `m_add_kpi` | `cockpit2.py:2572` |
| `m_add_from_def` | `cockpit2.py:2604` |
| `def_add` | `cockpit2.py:2619` |
| `catalog_publish` | `cockpit2.py:2641` |
| `def_amend` | `cockpit2.py:2667` |
| `m_add_link` | `cockpit2.py:2709` |
| `m_sample` | `cockpit2.py:2720` |
| `m_remove` | `cockpit2.py:2730` |
| `m_pin` | `cockpit2.py:2740` |
| `m_unpin` | `cockpit2.py:2751` |
| `tile_add` | `cockpit2.py:2789` |
| `indicator_activate` | `cockpit2.py:2761` |
| `tile_remove` | `cockpit2.py:2823` |
| `rov2_set` | `cockpit2.py:2833` |
| `rov2_acc_add` | `cockpit2.py:2833` |
| `rov2_acc_remove` | `cockpit2.py:2833` |
| `rov2_dom_add` | `cockpit2.py:2833` |
| `rov2_dom_remove` | `cockpit2.py:2833` |
| `backlog_add` | `cockpit2.py:2865` |
| `backlog_update_staat` | `cockpit2.py:2877` |
| `backlog_update_prioriteit` | `cockpit2.py:2889` |
| `person_edit` | `cockpit2.py:2901` |
| `person_remove` | `cockpit2.py:2918` |
| `lk_mute` | `cockpit2.py:2939` |


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


---
_32 routes · 109 dispatch-acties · 22 stores._
