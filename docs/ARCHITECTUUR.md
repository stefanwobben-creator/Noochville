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
| `proj_add` | `cockpit2.py:844` |
| `artefact_add` | `cockpit2.py:872` |
| `artefact_edit` | `cockpit2.py:913` |
| `artefact_archive` | `cockpit2.py:937` |
| `proj_status` | `cockpit2.py:957` |
| `proj_done` | `cockpit2.py:975` |
| `proj_archive` | `cockpit2.py:997` |
| `proj_unarchive` | `cockpit2.py:1007` |
| `proj_delete` | `cockpit2.py:1017` |
| `proj_edit` | `cockpit2.py:1044` |
| `proj_comment` | `cockpit2.py:1057` |
| `proj_rename` | `cockpit2.py:1067` |
| `proj_describe` | `cockpit2.py:1078` |
| `proj_doc_edit` | `cockpit2.py:1111` |
| `proj_regen_doc` | `cockpit2.py:1089` |
| `proj_settrekker` | `cockpit2.py:1124` |
| `proj_setowner` | `cockpit2.py:1161` |
| `proj_approve` | `cockpit2.py:1180` |
| `proj_discard` | `cockpit2.py:1191` |
| `proj_setlabel` | `cockpit2.py:1202` |
| `proj_setimpact` | `cockpit2.py:1217` |
| `proj_seteffort` | `cockpit2.py:1236` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1259` |
| `proj_setprivate` | `cockpit2.py:1283` |
| `proj_setdue` | `cockpit2.py:1294` |
| `attach_add` | `cockpit2.py:1305` |
| `attach_remove` | `cockpit2.py:1316` |
| `react_add` | `cockpit2.py:1326` |
| `feed_edit` | `cockpit2.py:1336` |
| `feed_remove` | `cockpit2.py:1346` |
| `wall_outcome` | `cockpit2.py:1939` |
| `ai_reply` | `cockpit2.py:1355` |
| `proj_feed` | `cockpit2.py:1366` |
| `checklist_add` | `cockpit2.py:1396` |
| `checklist_remove` | `cockpit2.py:1407` |
| `check_add` | `cockpit2.py:1455` |
| `check_accept` | `cockpit2.py:1472` |
| `check_toggle` | `cockpit2.py:1482` |
| `check_remove` | `cockpit2.py:1492` |
| `role_assign` | `cockpit2.py:1502` |
| `role_unassign` | `cockpit2.py:1520` |
| `role_focus` | `cockpit2.py:1539` |
| `radar_approve` | `cockpit2.py:1572` |
| `radar_dismiss` | `cockpit2.py:1576` |
| `aitask_add` | `cockpit2.py:1580` |
| `aitask_remove` | `cockpit2.py:1606` |
| `persona_skill_add` | `cockpit2.py:1623` |
| `rov2_add` | `cockpit2.py:1638` |
| `rov2_add_to_group` | `cockpit2.py:1650` |
| `rov2_remove` | `cockpit2.py:1662` |
| `rov2_remove_group` | `cockpit2.py:1677` |
| `rov2_setkind` | `cockpit2.py:1695` |
| `rov2_consent` | `cockpit2.py:1708` |
| `rov2_end` | `cockpit2.py:1730` |
| `wo_open` | `cockpit2.py:1754` |
| `wo_close` | `cockpit2.py:1764` |
| `wo_presence` | `cockpit2.py:1780` |
| `wo_present_all` | `cockpit2.py:1791` |
| `wo_ag_add` | `cockpit2.py:1803` |
| `wo_ag_remove` | `cockpit2.py:1815` |
| `wo_ag_note` | `cockpit2.py:1825` |
| `wo_ag_reopen` | `cockpit2.py:1837` |
| `wo_ag_resolve` | `cockpit2.py:1913` |
| `wo_checkout` | `cockpit2.py:2035` |
| `noochie_send` | `cockpit2.py:2047` |
| `noochie_reset` | `cockpit2.py:2073` |
| `noochie_ctx` | `cockpit2.py:2080` |
| `cl_add` | `cockpit2.py:2087` |
| `cl_report` | `cockpit2.py:2105` |
| `cl_remove` | `cockpit2.py:2120` |
| `m_add_kpi` | `cockpit2.py:2130` |
| `m_add_from_def` | `cockpit2.py:2162` |
| `def_add` | `cockpit2.py:2177` |
| `catalog_publish` | `cockpit2.py:2199` |
| `def_amend` | `cockpit2.py:2225` |
| `m_add_link` | `cockpit2.py:2267` |
| `m_sample` | `cockpit2.py:2278` |
| `m_remove` | `cockpit2.py:2288` |
| `m_pin` | `cockpit2.py:2298` |
| `m_unpin` | `cockpit2.py:2309` |
| `tile_add` | `cockpit2.py:2347` |
| `indicator_activate` | `cockpit2.py:2319` |
| `tile_remove` | `cockpit2.py:2381` |
| `rov2_set` | `cockpit2.py:2391` |
| `rov2_acc_add` | `cockpit2.py:2391` |
| `rov2_acc_remove` | `cockpit2.py:2391` |
| `rov2_dom_add` | `cockpit2.py:2391` |
| `rov2_dom_remove` | `cockpit2.py:2391` |
| `backlog_add` | `cockpit2.py:2423` |
| `backlog_update_staat` | `cockpit2.py:2435` |
| `backlog_update_prioriteit` | `cockpit2.py:2447` |
| `person_edit` | `cockpit2.py:2459` |
| `person_remove` | `cockpit2.py:2476` |
| `lk_mute` | `cockpit2.py:2497` |


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
_27 routes · 94 dispatch-acties · 22 stores._
