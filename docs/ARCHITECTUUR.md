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
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `proj_add` | `cockpit2.py:625` |
| `artefact_add` | `cockpit2.py:653` |
| `artefact_edit` | `cockpit2.py:694` |
| `artefact_archive` | `cockpit2.py:718` |
| `proj_status` | `cockpit2.py:738` |
| `proj_done` | `cockpit2.py:756` |
| `proj_archive` | `cockpit2.py:766` |
| `proj_unarchive` | `cockpit2.py:776` |
| `proj_delete` | `cockpit2.py:786` |
| `proj_edit` | `cockpit2.py:801` |
| `proj_comment` | `cockpit2.py:814` |
| `proj_rename` | `cockpit2.py:824` |
| `proj_describe` | `cockpit2.py:835` |
| `proj_settrekker` | `cockpit2.py:846` |
| `proj_setowner` | `cockpit2.py:858` |
| `proj_approve` | `cockpit2.py:876` |
| `proj_discard` | `cockpit2.py:887` |
| `proj_setlabel` | `cockpit2.py:898` |
| `proj_setimpact` | `cockpit2.py:913` |
| `proj_agendeer_verzwakt` | `cockpit2.py:932` |
| `proj_setprivate` | `cockpit2.py:956` |
| `proj_setdue` | `cockpit2.py:967` |
| `attach_add` | `cockpit2.py:978` |
| `attach_remove` | `cockpit2.py:989` |
| `react_add` | `cockpit2.py:999` |
| `feed_edit` | `cockpit2.py:1009` |
| `feed_remove` | `cockpit2.py:1019` |
| `ai_reply` | `cockpit2.py:1028` |
| `proj_feed` | `cockpit2.py:1039` |
| `checklist_add` | `cockpit2.py:1059` |
| `checklist_remove` | `cockpit2.py:1070` |
| `check_add` | `cockpit2.py:1080` |
| `check_toggle` | `cockpit2.py:1091` |
| `check_remove` | `cockpit2.py:1101` |
| `role_assign` | `cockpit2.py:1111` |
| `role_unassign` | `cockpit2.py:1129` |
| `role_focus` | `cockpit2.py:1148` |
| `aitask_add` | `cockpit2.py:1167` |
| `aitask_remove` | `cockpit2.py:1193` |
| `persona_skill_add` | `cockpit2.py:1210` |
| `rov2_add` | `cockpit2.py:1225` |
| `rov2_add_to_group` | `cockpit2.py:1237` |
| `rov2_remove` | `cockpit2.py:1249` |
| `rov2_remove_group` | `cockpit2.py:1264` |
| `rov2_setkind` | `cockpit2.py:1282` |
| `rov2_consent` | `cockpit2.py:1295` |
| `rov2_end` | `cockpit2.py:1317` |
| `wo_open` | `cockpit2.py:1341` |
| `wo_close` | `cockpit2.py:1351` |
| `wo_presence` | `cockpit2.py:1373` |
| `wo_present_all` | `cockpit2.py:1384` |
| `wo_ag_add` | `cockpit2.py:1396` |
| `wo_ag_remove` | `cockpit2.py:1408` |
| `wo_ag_note` | `cockpit2.py:1418` |
| `wo_ag_reopen` | `cockpit2.py:1430` |
| `wo_ag_resolve` | `cockpit2.py:1443` |
| `wo_checkout` | `cockpit2.py:1485` |
| `noochie_send` | `cockpit2.py:1496` |
| `noochie_reset` | `cockpit2.py:1522` |
| `noochie_ctx` | `cockpit2.py:1529` |
| `cl_add` | `cockpit2.py:1536` |
| `cl_report` | `cockpit2.py:1554` |
| `cl_remove` | `cockpit2.py:1569` |
| `m_add_kpi` | `cockpit2.py:1579` |
| `m_add_from_def` | `cockpit2.py:1611` |
| `def_add` | `cockpit2.py:1626` |
| `catalog_publish` | `cockpit2.py:1648` |
| `def_amend` | `cockpit2.py:1674` |
| `m_add_link` | `cockpit2.py:1716` |
| `m_sample` | `cockpit2.py:1727` |
| `m_remove` | `cockpit2.py:1737` |
| `m_pin` | `cockpit2.py:1747` |
| `m_unpin` | `cockpit2.py:1758` |
| `tile_add` | `cockpit2.py:1796` |
| `indicator_activate` | `cockpit2.py:1768` |
| `tile_remove` | `cockpit2.py:1830` |
| `rov2_set` | `cockpit2.py:1840` |
| `rov2_acc_add` | `cockpit2.py:1840` |
| `rov2_acc_remove` | `cockpit2.py:1840` |
| `rov2_dom_add` | `cockpit2.py:1840` |
| `rov2_dom_remove` | `cockpit2.py:1840` |
| `backlog_add` | `cockpit2.py:1872` |
| `backlog_update_staat` | `cockpit2.py:1884` |
| `backlog_update_prioriteit` | `cockpit2.py:1896` |
| `person_edit` | `cockpit2.py:1908` |
| `person_remove` | `cockpit2.py:1925` |


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
_24 routes · 86 dispatch-acties · 19 stores._
