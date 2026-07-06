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
| `proj_add` | `cockpit2.py:614` |
| `artefact_add` | `cockpit2.py:642` |
| `artefact_edit` | `cockpit2.py:683` |
| `artefact_archive` | `cockpit2.py:707` |
| `proj_status` | `cockpit2.py:727` |
| `proj_done` | `cockpit2.py:745` |
| `proj_archive` | `cockpit2.py:755` |
| `proj_unarchive` | `cockpit2.py:765` |
| `proj_delete` | `cockpit2.py:775` |
| `proj_edit` | `cockpit2.py:790` |
| `proj_comment` | `cockpit2.py:803` |
| `proj_rename` | `cockpit2.py:813` |
| `proj_describe` | `cockpit2.py:824` |
| `proj_settrekker` | `cockpit2.py:835` |
| `proj_setowner` | `cockpit2.py:847` |
| `proj_approve` | `cockpit2.py:865` |
| `proj_discard` | `cockpit2.py:876` |
| `proj_setlabel` | `cockpit2.py:887` |
| `proj_setimpact` | `cockpit2.py:901` |
| `proj_setprivate` | `cockpit2.py:920` |
| `proj_setdue` | `cockpit2.py:931` |
| `attach_add` | `cockpit2.py:942` |
| `attach_remove` | `cockpit2.py:953` |
| `react_add` | `cockpit2.py:963` |
| `feed_edit` | `cockpit2.py:973` |
| `feed_remove` | `cockpit2.py:983` |
| `ai_reply` | `cockpit2.py:992` |
| `proj_feed` | `cockpit2.py:1003` |
| `checklist_add` | `cockpit2.py:1023` |
| `checklist_remove` | `cockpit2.py:1034` |
| `check_add` | `cockpit2.py:1044` |
| `check_toggle` | `cockpit2.py:1055` |
| `check_remove` | `cockpit2.py:1065` |
| `role_assign` | `cockpit2.py:1075` |
| `role_unassign` | `cockpit2.py:1093` |
| `role_focus` | `cockpit2.py:1112` |
| `aitask_add` | `cockpit2.py:1131` |
| `aitask_remove` | `cockpit2.py:1157` |
| `persona_skill_add` | `cockpit2.py:1174` |
| `rov2_add` | `cockpit2.py:1189` |
| `rov2_add_to_group` | `cockpit2.py:1201` |
| `rov2_remove` | `cockpit2.py:1213` |
| `rov2_remove_group` | `cockpit2.py:1228` |
| `rov2_setkind` | `cockpit2.py:1246` |
| `rov2_consent` | `cockpit2.py:1259` |
| `rov2_end` | `cockpit2.py:1281` |
| `wo_open` | `cockpit2.py:1305` |
| `wo_close` | `cockpit2.py:1315` |
| `wo_presence` | `cockpit2.py:1337` |
| `wo_present_all` | `cockpit2.py:1348` |
| `wo_ag_add` | `cockpit2.py:1360` |
| `wo_ag_remove` | `cockpit2.py:1372` |
| `wo_ag_note` | `cockpit2.py:1382` |
| `wo_ag_reopen` | `cockpit2.py:1394` |
| `wo_ag_resolve` | `cockpit2.py:1407` |
| `wo_checkout` | `cockpit2.py:1449` |
| `noochie_send` | `cockpit2.py:1460` |
| `noochie_reset` | `cockpit2.py:1486` |
| `noochie_ctx` | `cockpit2.py:1493` |
| `cl_add` | `cockpit2.py:1500` |
| `cl_report` | `cockpit2.py:1518` |
| `cl_remove` | `cockpit2.py:1533` |
| `m_add_kpi` | `cockpit2.py:1543` |
| `m_add_from_def` | `cockpit2.py:1575` |
| `def_add` | `cockpit2.py:1590` |
| `catalog_publish` | `cockpit2.py:1612` |
| `def_amend` | `cockpit2.py:1638` |
| `m_add_link` | `cockpit2.py:1680` |
| `m_sample` | `cockpit2.py:1691` |
| `m_remove` | `cockpit2.py:1701` |
| `m_pin` | `cockpit2.py:1711` |
| `m_unpin` | `cockpit2.py:1722` |
| `tile_add` | `cockpit2.py:1732` |
| `tile_remove` | `cockpit2.py:1763` |
| `rov2_set` | `cockpit2.py:1773` |
| `rov2_acc_add` | `cockpit2.py:1773` |
| `rov2_acc_remove` | `cockpit2.py:1773` |
| `rov2_dom_add` | `cockpit2.py:1773` |
| `rov2_dom_remove` | `cockpit2.py:1773` |
| `backlog_add` | `cockpit2.py:1805` |
| `backlog_update_staat` | `cockpit2.py:1817` |
| `backlog_update_prioriteit` | `cockpit2.py:1829` |
| `person_edit` | `cockpit2.py:1841` |
| `person_remove` | `cockpit2.py:1858` |


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
_24 routes · 84 dispatch-acties · 19 stores._
