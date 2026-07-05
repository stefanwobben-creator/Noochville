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
| `proj_add` | `cockpit2.py:579` |
| `artefact_add` | `cockpit2.py:607` |
| `artefact_edit` | `cockpit2.py:648` |
| `artefact_archive` | `cockpit2.py:672` |
| `proj_status` | `cockpit2.py:692` |
| `proj_done` | `cockpit2.py:710` |
| `proj_archive` | `cockpit2.py:720` |
| `proj_unarchive` | `cockpit2.py:730` |
| `proj_delete` | `cockpit2.py:740` |
| `proj_edit` | `cockpit2.py:755` |
| `proj_comment` | `cockpit2.py:768` |
| `proj_rename` | `cockpit2.py:778` |
| `proj_describe` | `cockpit2.py:789` |
| `proj_settrekker` | `cockpit2.py:800` |
| `proj_setowner` | `cockpit2.py:812` |
| `proj_approve` | `cockpit2.py:830` |
| `proj_discard` | `cockpit2.py:841` |
| `proj_setlabel` | `cockpit2.py:852` |
| `proj_setprivate` | `cockpit2.py:863` |
| `proj_setdue` | `cockpit2.py:874` |
| `attach_add` | `cockpit2.py:885` |
| `attach_remove` | `cockpit2.py:896` |
| `react_add` | `cockpit2.py:906` |
| `feed_edit` | `cockpit2.py:916` |
| `feed_remove` | `cockpit2.py:926` |
| `ai_reply` | `cockpit2.py:935` |
| `proj_feed` | `cockpit2.py:946` |
| `checklist_add` | `cockpit2.py:966` |
| `checklist_remove` | `cockpit2.py:977` |
| `check_add` | `cockpit2.py:987` |
| `check_toggle` | `cockpit2.py:998` |
| `check_remove` | `cockpit2.py:1008` |
| `role_assign` | `cockpit2.py:1018` |
| `role_unassign` | `cockpit2.py:1036` |
| `role_focus` | `cockpit2.py:1055` |
| `aitask_add` | `cockpit2.py:1074` |
| `aitask_remove` | `cockpit2.py:1100` |
| `persona_skill_add` | `cockpit2.py:1117` |
| `rov2_add` | `cockpit2.py:1132` |
| `rov2_add_to_group` | `cockpit2.py:1144` |
| `rov2_remove` | `cockpit2.py:1156` |
| `rov2_remove_group` | `cockpit2.py:1171` |
| `rov2_setkind` | `cockpit2.py:1189` |
| `rov2_consent` | `cockpit2.py:1202` |
| `rov2_end` | `cockpit2.py:1224` |
| `wo_open` | `cockpit2.py:1248` |
| `wo_close` | `cockpit2.py:1258` |
| `wo_presence` | `cockpit2.py:1280` |
| `wo_present_all` | `cockpit2.py:1291` |
| `wo_ag_add` | `cockpit2.py:1303` |
| `wo_ag_remove` | `cockpit2.py:1315` |
| `wo_ag_note` | `cockpit2.py:1325` |
| `wo_ag_reopen` | `cockpit2.py:1337` |
| `wo_ag_resolve` | `cockpit2.py:1350` |
| `wo_checkout` | `cockpit2.py:1392` |
| `noochie_send` | `cockpit2.py:1403` |
| `noochie_reset` | `cockpit2.py:1429` |
| `noochie_ctx` | `cockpit2.py:1436` |
| `cl_add` | `cockpit2.py:1443` |
| `cl_report` | `cockpit2.py:1461` |
| `cl_remove` | `cockpit2.py:1476` |
| `m_add_kpi` | `cockpit2.py:1486` |
| `m_add_from_def` | `cockpit2.py:1518` |
| `def_add` | `cockpit2.py:1533` |
| `catalog_publish` | `cockpit2.py:1555` |
| `def_amend` | `cockpit2.py:1581` |
| `m_add_link` | `cockpit2.py:1623` |
| `m_sample` | `cockpit2.py:1634` |
| `m_remove` | `cockpit2.py:1644` |
| `m_pin` | `cockpit2.py:1654` |
| `m_unpin` | `cockpit2.py:1665` |
| `tile_add` | `cockpit2.py:1675` |
| `tile_remove` | `cockpit2.py:1706` |
| `rov2_set` | `cockpit2.py:1716` |
| `rov2_acc_add` | `cockpit2.py:1716` |
| `rov2_acc_remove` | `cockpit2.py:1716` |
| `rov2_dom_add` | `cockpit2.py:1716` |
| `rov2_dom_remove` | `cockpit2.py:1716` |
| `backlog_add` | `cockpit2.py:1748` |
| `backlog_update_staat` | `cockpit2.py:1760` |
| `backlog_update_prioriteit` | `cockpit2.py:1772` |
| `person_edit` | `cockpit2.py:1784` |
| `person_remove` | `cockpit2.py:1801` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
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
_22 routes · 83 dispatch-acties · 18 stores._
