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
| `proj_add` | `cockpit2.py:734` |
| `artefact_add` | `cockpit2.py:762` |
| `artefact_edit` | `cockpit2.py:803` |
| `artefact_archive` | `cockpit2.py:827` |
| `proj_status` | `cockpit2.py:847` |
| `proj_done` | `cockpit2.py:865` |
| `proj_archive` | `cockpit2.py:876` |
| `proj_unarchive` | `cockpit2.py:886` |
| `proj_delete` | `cockpit2.py:896` |
| `proj_edit` | `cockpit2.py:911` |
| `proj_comment` | `cockpit2.py:924` |
| `proj_rename` | `cockpit2.py:934` |
| `proj_describe` | `cockpit2.py:945` |
| `proj_settrekker` | `cockpit2.py:956` |
| `proj_setowner` | `cockpit2.py:993` |
| `proj_approve` | `cockpit2.py:1012` |
| `proj_discard` | `cockpit2.py:1023` |
| `proj_setlabel` | `cockpit2.py:1034` |
| `proj_setimpact` | `cockpit2.py:1049` |
| `proj_seteffort` | `cockpit2.py:1068` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1091` |
| `proj_setprivate` | `cockpit2.py:1115` |
| `proj_setdue` | `cockpit2.py:1126` |
| `attach_add` | `cockpit2.py:1137` |
| `attach_remove` | `cockpit2.py:1148` |
| `react_add` | `cockpit2.py:1158` |
| `feed_edit` | `cockpit2.py:1168` |
| `feed_remove` | `cockpit2.py:1178` |
| `wall_outcome` | `cockpit2.py:1737` |
| `ai_reply` | `cockpit2.py:1187` |
| `proj_feed` | `cockpit2.py:1198` |
| `checklist_add` | `cockpit2.py:1225` |
| `checklist_remove` | `cockpit2.py:1236` |
| `check_add` | `cockpit2.py:1276` |
| `check_accept` | `cockpit2.py:1292` |
| `check_toggle` | `cockpit2.py:1302` |
| `check_remove` | `cockpit2.py:1312` |
| `role_assign` | `cockpit2.py:1322` |
| `role_unassign` | `cockpit2.py:1340` |
| `role_focus` | `cockpit2.py:1359` |
| `aitask_add` | `cockpit2.py:1378` |
| `aitask_remove` | `cockpit2.py:1404` |
| `persona_skill_add` | `cockpit2.py:1421` |
| `rov2_add` | `cockpit2.py:1436` |
| `rov2_add_to_group` | `cockpit2.py:1448` |
| `rov2_remove` | `cockpit2.py:1460` |
| `rov2_remove_group` | `cockpit2.py:1475` |
| `rov2_setkind` | `cockpit2.py:1493` |
| `rov2_consent` | `cockpit2.py:1506` |
| `rov2_end` | `cockpit2.py:1528` |
| `wo_open` | `cockpit2.py:1552` |
| `wo_close` | `cockpit2.py:1562` |
| `wo_presence` | `cockpit2.py:1578` |
| `wo_present_all` | `cockpit2.py:1589` |
| `wo_ag_add` | `cockpit2.py:1601` |
| `wo_ag_remove` | `cockpit2.py:1613` |
| `wo_ag_note` | `cockpit2.py:1623` |
| `wo_ag_reopen` | `cockpit2.py:1635` |
| `wo_ag_resolve` | `cockpit2.py:1711` |
| `wo_checkout` | `cockpit2.py:1833` |
| `noochie_send` | `cockpit2.py:1845` |
| `noochie_reset` | `cockpit2.py:1871` |
| `noochie_ctx` | `cockpit2.py:1878` |
| `cl_add` | `cockpit2.py:1885` |
| `cl_report` | `cockpit2.py:1903` |
| `cl_remove` | `cockpit2.py:1918` |
| `m_add_kpi` | `cockpit2.py:1928` |
| `m_add_from_def` | `cockpit2.py:1960` |
| `def_add` | `cockpit2.py:1975` |
| `catalog_publish` | `cockpit2.py:1997` |
| `def_amend` | `cockpit2.py:2023` |
| `m_add_link` | `cockpit2.py:2065` |
| `m_sample` | `cockpit2.py:2076` |
| `m_remove` | `cockpit2.py:2086` |
| `m_pin` | `cockpit2.py:2096` |
| `m_unpin` | `cockpit2.py:2107` |
| `tile_add` | `cockpit2.py:2145` |
| `indicator_activate` | `cockpit2.py:2117` |
| `tile_remove` | `cockpit2.py:2179` |
| `rov2_set` | `cockpit2.py:2189` |
| `rov2_acc_add` | `cockpit2.py:2189` |
| `rov2_acc_remove` | `cockpit2.py:2189` |
| `rov2_dom_add` | `cockpit2.py:2189` |
| `rov2_dom_remove` | `cockpit2.py:2189` |
| `backlog_add` | `cockpit2.py:2221` |
| `backlog_update_staat` | `cockpit2.py:2233` |
| `backlog_update_prioriteit` | `cockpit2.py:2245` |
| `person_edit` | `cockpit2.py:2257` |
| `person_remove` | `cockpit2.py:2274` |
| `lk_mute` | `cockpit2.py:2295` |


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
_24 routes · 90 dispatch-acties · 19 stores._
