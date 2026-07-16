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
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
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
| `proj_add` | `cockpit2.py:1080` |
| `artefact_add` | `cockpit2.py:1108` |
| `artefact_edit` | `cockpit2.py:1149` |
| `artefact_archive` | `cockpit2.py:1173` |
| `proj_status` | `cockpit2.py:1193` |
| `proj_done` | `cockpit2.py:1211` |
| `proj_archive` | `cockpit2.py:1233` |
| `proj_unarchive` | `cockpit2.py:1243` |
| `proj_delete` | `cockpit2.py:1253` |
| `proj_edit` | `cockpit2.py:1280` |
| `proj_comment` | `cockpit2.py:1293` |
| `proj_rename` | `cockpit2.py:1303` |
| `proj_describe` | `cockpit2.py:1314` |
| `proj_doc_edit` | `cockpit2.py:1347` |
| `proj_regen_doc` | `cockpit2.py:1325` |
| `proj_settrekker` | `cockpit2.py:1360` |
| `proj_setowner` | `cockpit2.py:1397` |
| `proj_approve` | `cockpit2.py:1416` |
| `proj_discard` | `cockpit2.py:1427` |
| `proj_setlabel` | `cockpit2.py:1438` |
| `proj_setimpact` | `cockpit2.py:1453` |
| `proj_seteffort` | `cockpit2.py:1472` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1495` |
| `proj_setprivate` | `cockpit2.py:1519` |
| `proj_setdue` | `cockpit2.py:1530` |
| `attach_add` | `cockpit2.py:1541` |
| `attach_remove` | `cockpit2.py:1552` |
| `react_add` | `cockpit2.py:1562` |
| `feed_edit` | `cockpit2.py:1572` |
| `feed_remove` | `cockpit2.py:1582` |
| `wall_outcome` | `cockpit2.py:2175` |
| `notif_read` | `cockpit2.py:2273` |
| `notif_processed` | `cockpit2.py:2278` |
| `notif_outcome` | `cockpit2.py:2425` |
| `notif_klaar` | `cockpit2.py:2411` |
| `notif_delete` | `cockpit2.py:2283` |
| `notif_add` | `cockpit2.py:2395` |
| `notif_archive` | `cockpit2.py:2512` |
| `metrics2_fav` | `cockpit2.py:2289` |
| `metrics2_unfav` | `cockpit2.py:2299` |
| `metrics2_form` | `cockpit2.py:2304` |
| `metrics2_dim` | `cockpit2.py:2310` |
| `metrics2_compare` | `cockpit2.py:2317` |
| `metrics2_formula` | `cockpit2.py:2380` |
| `source_activate` | `cockpit2.py:2363` |
| `source_deactivate` | `cockpit2.py:2372` |
| `link_pursue` | `cockpit2.py:2344` |
| `link_ignore` | `cockpit2.py:2354` |
| `acc_check` | `cockpit2.py:2325` |
| `ai_reply` | `cockpit2.py:1591` |
| `proj_feed` | `cockpit2.py:1602` |
| `checklist_add` | `cockpit2.py:1632` |
| `checklist_remove` | `cockpit2.py:1643` |
| `check_add` | `cockpit2.py:1691` |
| `check_accept` | `cockpit2.py:1708` |
| `check_toggle` | `cockpit2.py:1718` |
| `check_remove` | `cockpit2.py:1728` |
| `role_assign` | `cockpit2.py:1738` |
| `role_unassign` | `cockpit2.py:1756` |
| `role_focus` | `cockpit2.py:1775` |
| `radar_approve` | `cockpit2.py:1808` |
| `radar_dismiss` | `cockpit2.py:1812` |
| `aitask_add` | `cockpit2.py:1816` |
| `aitask_remove` | `cockpit2.py:1842` |
| `persona_skill_add` | `cockpit2.py:1859` |
| `rov2_add` | `cockpit2.py:1874` |
| `rov2_add_to_group` | `cockpit2.py:1886` |
| `rov2_remove` | `cockpit2.py:1898` |
| `rov2_remove_group` | `cockpit2.py:1913` |
| `rov2_setkind` | `cockpit2.py:1931` |
| `rov2_consent` | `cockpit2.py:1944` |
| `rov2_end` | `cockpit2.py:1966` |
| `wo_open` | `cockpit2.py:1990` |
| `wo_close` | `cockpit2.py:2000` |
| `wo_presence` | `cockpit2.py:2016` |
| `wo_present_all` | `cockpit2.py:2027` |
| `wo_ag_add` | `cockpit2.py:2039` |
| `wo_ag_remove` | `cockpit2.py:2051` |
| `wo_ag_note` | `cockpit2.py:2061` |
| `wo_ag_reopen` | `cockpit2.py:2073` |
| `wo_ag_resolve` | `cockpit2.py:2149` |
| `wo_checkout` | `cockpit2.py:2517` |
| `noochie_send` | `cockpit2.py:2529` |
| `noochie_reset` | `cockpit2.py:2555` |
| `noochie_ctx` | `cockpit2.py:2562` |
| `cl_add` | `cockpit2.py:2569` |
| `cl_report` | `cockpit2.py:2587` |
| `cl_remove` | `cockpit2.py:2602` |
| `m_add_kpi` | `cockpit2.py:2612` |
| `m_add_from_def` | `cockpit2.py:2644` |
| `def_add` | `cockpit2.py:2659` |
| `catalog_publish` | `cockpit2.py:2681` |
| `def_amend` | `cockpit2.py:2707` |
| `m_add_link` | `cockpit2.py:2749` |
| `m_sample` | `cockpit2.py:2760` |
| `m_remove` | `cockpit2.py:2770` |
| `m_pin` | `cockpit2.py:2780` |
| `m_unpin` | `cockpit2.py:2791` |
| `tile_add` | `cockpit2.py:2829` |
| `indicator_activate` | `cockpit2.py:2801` |
| `tile_remove` | `cockpit2.py:2863` |
| `rov2_set` | `cockpit2.py:2873` |
| `rov2_acc_add` | `cockpit2.py:2873` |
| `rov2_acc_remove` | `cockpit2.py:2873` |
| `rov2_dom_add` | `cockpit2.py:2873` |
| `rov2_dom_remove` | `cockpit2.py:2873` |
| `backlog_add` | `cockpit2.py:2905` |
| `backlog_update_staat` | `cockpit2.py:2917` |
| `backlog_update_prioriteit` | `cockpit2.py:2929` |
| `person_edit` | `cockpit2.py:2941` |
| `person_remove` | `cockpit2.py:2958` |
| `lk_mute` | `cockpit2.py:2979` |


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
_34 routes · 112 dispatch-acties · 22 stores._
