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
| `proj_add` | `cockpit2.py:744` |
| `artefact_add` | `cockpit2.py:772` |
| `artefact_edit` | `cockpit2.py:813` |
| `artefact_archive` | `cockpit2.py:837` |
| `proj_status` | `cockpit2.py:857` |
| `proj_done` | `cockpit2.py:875` |
| `proj_archive` | `cockpit2.py:886` |
| `proj_unarchive` | `cockpit2.py:896` |
| `proj_delete` | `cockpit2.py:906` |
| `proj_edit` | `cockpit2.py:921` |
| `proj_comment` | `cockpit2.py:934` |
| `proj_rename` | `cockpit2.py:944` |
| `proj_describe` | `cockpit2.py:955` |
| `proj_settrekker` | `cockpit2.py:966` |
| `proj_setowner` | `cockpit2.py:1003` |
| `proj_approve` | `cockpit2.py:1022` |
| `proj_discard` | `cockpit2.py:1033` |
| `proj_setlabel` | `cockpit2.py:1044` |
| `proj_setimpact` | `cockpit2.py:1059` |
| `proj_seteffort` | `cockpit2.py:1078` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1101` |
| `proj_setprivate` | `cockpit2.py:1125` |
| `proj_setdue` | `cockpit2.py:1136` |
| `attach_add` | `cockpit2.py:1147` |
| `attach_remove` | `cockpit2.py:1158` |
| `react_add` | `cockpit2.py:1168` |
| `feed_edit` | `cockpit2.py:1178` |
| `feed_remove` | `cockpit2.py:1188` |
| `wall_outcome` | `cockpit2.py:1756` |
| `ai_reply` | `cockpit2.py:1197` |
| `proj_feed` | `cockpit2.py:1208` |
| `checklist_add` | `cockpit2.py:1235` |
| `checklist_remove` | `cockpit2.py:1246` |
| `check_add` | `cockpit2.py:1294` |
| `check_accept` | `cockpit2.py:1311` |
| `check_toggle` | `cockpit2.py:1321` |
| `check_remove` | `cockpit2.py:1331` |
| `role_assign` | `cockpit2.py:1341` |
| `role_unassign` | `cockpit2.py:1359` |
| `role_focus` | `cockpit2.py:1378` |
| `aitask_add` | `cockpit2.py:1397` |
| `aitask_remove` | `cockpit2.py:1423` |
| `persona_skill_add` | `cockpit2.py:1440` |
| `rov2_add` | `cockpit2.py:1455` |
| `rov2_add_to_group` | `cockpit2.py:1467` |
| `rov2_remove` | `cockpit2.py:1479` |
| `rov2_remove_group` | `cockpit2.py:1494` |
| `rov2_setkind` | `cockpit2.py:1512` |
| `rov2_consent` | `cockpit2.py:1525` |
| `rov2_end` | `cockpit2.py:1547` |
| `wo_open` | `cockpit2.py:1571` |
| `wo_close` | `cockpit2.py:1581` |
| `wo_presence` | `cockpit2.py:1597` |
| `wo_present_all` | `cockpit2.py:1608` |
| `wo_ag_add` | `cockpit2.py:1620` |
| `wo_ag_remove` | `cockpit2.py:1632` |
| `wo_ag_note` | `cockpit2.py:1642` |
| `wo_ag_reopen` | `cockpit2.py:1654` |
| `wo_ag_resolve` | `cockpit2.py:1730` |
| `wo_checkout` | `cockpit2.py:1852` |
| `noochie_send` | `cockpit2.py:1864` |
| `noochie_reset` | `cockpit2.py:1890` |
| `noochie_ctx` | `cockpit2.py:1897` |
| `cl_add` | `cockpit2.py:1904` |
| `cl_report` | `cockpit2.py:1922` |
| `cl_remove` | `cockpit2.py:1937` |
| `m_add_kpi` | `cockpit2.py:1947` |
| `m_add_from_def` | `cockpit2.py:1979` |
| `def_add` | `cockpit2.py:1994` |
| `catalog_publish` | `cockpit2.py:2016` |
| `def_amend` | `cockpit2.py:2042` |
| `m_add_link` | `cockpit2.py:2084` |
| `m_sample` | `cockpit2.py:2095` |
| `m_remove` | `cockpit2.py:2105` |
| `m_pin` | `cockpit2.py:2115` |
| `m_unpin` | `cockpit2.py:2126` |
| `tile_add` | `cockpit2.py:2164` |
| `indicator_activate` | `cockpit2.py:2136` |
| `tile_remove` | `cockpit2.py:2198` |
| `rov2_set` | `cockpit2.py:2208` |
| `rov2_acc_add` | `cockpit2.py:2208` |
| `rov2_acc_remove` | `cockpit2.py:2208` |
| `rov2_dom_add` | `cockpit2.py:2208` |
| `rov2_dom_remove` | `cockpit2.py:2208` |
| `backlog_add` | `cockpit2.py:2240` |
| `backlog_update_staat` | `cockpit2.py:2252` |
| `backlog_update_prioriteit` | `cockpit2.py:2264` |
| `person_edit` | `cockpit2.py:2276` |
| `person_remove` | `cockpit2.py:2293` |
| `lk_mute` | `cockpit2.py:2314` |


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
_25 routes · 90 dispatch-acties · 19 stores._
