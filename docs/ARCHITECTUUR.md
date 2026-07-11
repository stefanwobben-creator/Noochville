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
| `/catalog` | `render_catalog` | `nooch_village/views/catalog.py` |
| `/catalogus_koppelen` | `(inline)` | `cockpit2.py` |
| `/kpi_new` | `render_kpi_composer` | `nooch_village/views/metrics.py` |
| `/noochie` | `render_noochie` | `nooch_village/views/noochie.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:748` |
| `artefact_add` | `cockpit2.py:776` |
| `artefact_edit` | `cockpit2.py:817` |
| `artefact_archive` | `cockpit2.py:841` |
| `proj_status` | `cockpit2.py:861` |
| `proj_done` | `cockpit2.py:879` |
| `proj_archive` | `cockpit2.py:901` |
| `proj_unarchive` | `cockpit2.py:911` |
| `proj_delete` | `cockpit2.py:921` |
| `proj_edit` | `cockpit2.py:948` |
| `proj_comment` | `cockpit2.py:961` |
| `proj_rename` | `cockpit2.py:971` |
| `proj_describe` | `cockpit2.py:982` |
| `proj_doc_edit` | `cockpit2.py:993` |
| `proj_settrekker` | `cockpit2.py:1006` |
| `proj_setowner` | `cockpit2.py:1043` |
| `proj_approve` | `cockpit2.py:1062` |
| `proj_discard` | `cockpit2.py:1073` |
| `proj_setlabel` | `cockpit2.py:1084` |
| `proj_setimpact` | `cockpit2.py:1099` |
| `proj_seteffort` | `cockpit2.py:1118` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1141` |
| `proj_setprivate` | `cockpit2.py:1165` |
| `proj_setdue` | `cockpit2.py:1176` |
| `attach_add` | `cockpit2.py:1187` |
| `attach_remove` | `cockpit2.py:1198` |
| `react_add` | `cockpit2.py:1208` |
| `feed_edit` | `cockpit2.py:1218` |
| `feed_remove` | `cockpit2.py:1228` |
| `wall_outcome` | `cockpit2.py:1796` |
| `ai_reply` | `cockpit2.py:1237` |
| `proj_feed` | `cockpit2.py:1248` |
| `checklist_add` | `cockpit2.py:1275` |
| `checklist_remove` | `cockpit2.py:1286` |
| `check_add` | `cockpit2.py:1334` |
| `check_accept` | `cockpit2.py:1351` |
| `check_toggle` | `cockpit2.py:1361` |
| `check_remove` | `cockpit2.py:1371` |
| `role_assign` | `cockpit2.py:1381` |
| `role_unassign` | `cockpit2.py:1399` |
| `role_focus` | `cockpit2.py:1418` |
| `aitask_add` | `cockpit2.py:1437` |
| `aitask_remove` | `cockpit2.py:1463` |
| `persona_skill_add` | `cockpit2.py:1480` |
| `rov2_add` | `cockpit2.py:1495` |
| `rov2_add_to_group` | `cockpit2.py:1507` |
| `rov2_remove` | `cockpit2.py:1519` |
| `rov2_remove_group` | `cockpit2.py:1534` |
| `rov2_setkind` | `cockpit2.py:1552` |
| `rov2_consent` | `cockpit2.py:1565` |
| `rov2_end` | `cockpit2.py:1587` |
| `wo_open` | `cockpit2.py:1611` |
| `wo_close` | `cockpit2.py:1621` |
| `wo_presence` | `cockpit2.py:1637` |
| `wo_present_all` | `cockpit2.py:1648` |
| `wo_ag_add` | `cockpit2.py:1660` |
| `wo_ag_remove` | `cockpit2.py:1672` |
| `wo_ag_note` | `cockpit2.py:1682` |
| `wo_ag_reopen` | `cockpit2.py:1694` |
| `wo_ag_resolve` | `cockpit2.py:1770` |
| `wo_checkout` | `cockpit2.py:1892` |
| `noochie_send` | `cockpit2.py:1904` |
| `noochie_reset` | `cockpit2.py:1930` |
| `noochie_ctx` | `cockpit2.py:1937` |
| `cl_add` | `cockpit2.py:1944` |
| `cl_report` | `cockpit2.py:1962` |
| `cl_remove` | `cockpit2.py:1977` |
| `m_add_kpi` | `cockpit2.py:1987` |
| `m_add_from_def` | `cockpit2.py:2019` |
| `def_add` | `cockpit2.py:2034` |
| `catalog_publish` | `cockpit2.py:2056` |
| `def_amend` | `cockpit2.py:2082` |
| `m_add_link` | `cockpit2.py:2124` |
| `m_sample` | `cockpit2.py:2135` |
| `m_remove` | `cockpit2.py:2145` |
| `m_pin` | `cockpit2.py:2155` |
| `m_unpin` | `cockpit2.py:2166` |
| `tile_add` | `cockpit2.py:2204` |
| `indicator_activate` | `cockpit2.py:2176` |
| `tile_remove` | `cockpit2.py:2238` |
| `rov2_set` | `cockpit2.py:2248` |
| `rov2_acc_add` | `cockpit2.py:2248` |
| `rov2_acc_remove` | `cockpit2.py:2248` |
| `rov2_dom_add` | `cockpit2.py:2248` |
| `rov2_dom_remove` | `cockpit2.py:2248` |
| `backlog_add` | `cockpit2.py:2280` |
| `backlog_update_staat` | `cockpit2.py:2292` |
| `backlog_update_prioriteit` | `cockpit2.py:2304` |
| `person_edit` | `cockpit2.py:2316` |
| `person_remove` | `cockpit2.py:2333` |
| `lk_mute` | `cockpit2.py:2354` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
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


---
_25 routes · 91 dispatch-acties · 20 stores._
