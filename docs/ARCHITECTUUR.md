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
| `proj_add` | `cockpit2.py:581` |
| `artefact_add` | `cockpit2.py:609` |
| `artefact_edit` | `cockpit2.py:650` |
| `artefact_archive` | `cockpit2.py:674` |
| `proj_status` | `cockpit2.py:694` |
| `proj_done` | `cockpit2.py:712` |
| `proj_archive` | `cockpit2.py:722` |
| `proj_unarchive` | `cockpit2.py:732` |
| `proj_delete` | `cockpit2.py:742` |
| `proj_edit` | `cockpit2.py:757` |
| `proj_comment` | `cockpit2.py:770` |
| `proj_rename` | `cockpit2.py:780` |
| `proj_describe` | `cockpit2.py:791` |
| `proj_settrekker` | `cockpit2.py:802` |
| `proj_setowner` | `cockpit2.py:814` |
| `proj_approve` | `cockpit2.py:832` |
| `proj_discard` | `cockpit2.py:843` |
| `proj_setlabel` | `cockpit2.py:854` |
| `proj_setprivate` | `cockpit2.py:865` |
| `proj_setdue` | `cockpit2.py:876` |
| `attach_add` | `cockpit2.py:887` |
| `attach_remove` | `cockpit2.py:898` |
| `react_add` | `cockpit2.py:908` |
| `feed_edit` | `cockpit2.py:918` |
| `feed_remove` | `cockpit2.py:928` |
| `ai_reply` | `cockpit2.py:937` |
| `proj_feed` | `cockpit2.py:948` |
| `checklist_add` | `cockpit2.py:968` |
| `checklist_remove` | `cockpit2.py:979` |
| `check_add` | `cockpit2.py:989` |
| `check_toggle` | `cockpit2.py:1000` |
| `check_remove` | `cockpit2.py:1010` |
| `role_assign` | `cockpit2.py:1020` |
| `role_unassign` | `cockpit2.py:1038` |
| `role_focus` | `cockpit2.py:1057` |
| `aitask_add` | `cockpit2.py:1076` |
| `aitask_remove` | `cockpit2.py:1102` |
| `persona_skill_add` | `cockpit2.py:1119` |
| `rov2_add` | `cockpit2.py:1134` |
| `rov2_add_to_group` | `cockpit2.py:1146` |
| `rov2_remove` | `cockpit2.py:1158` |
| `rov2_remove_group` | `cockpit2.py:1173` |
| `rov2_setkind` | `cockpit2.py:1191` |
| `rov2_consent` | `cockpit2.py:1204` |
| `rov2_end` | `cockpit2.py:1226` |
| `wo_open` | `cockpit2.py:1250` |
| `wo_close` | `cockpit2.py:1260` |
| `wo_presence` | `cockpit2.py:1282` |
| `wo_present_all` | `cockpit2.py:1293` |
| `wo_ag_add` | `cockpit2.py:1305` |
| `wo_ag_remove` | `cockpit2.py:1317` |
| `wo_ag_note` | `cockpit2.py:1327` |
| `wo_ag_reopen` | `cockpit2.py:1339` |
| `wo_ag_resolve` | `cockpit2.py:1352` |
| `wo_checkout` | `cockpit2.py:1394` |
| `noochie_send` | `cockpit2.py:1405` |
| `noochie_reset` | `cockpit2.py:1431` |
| `noochie_ctx` | `cockpit2.py:1438` |
| `cl_add` | `cockpit2.py:1445` |
| `cl_report` | `cockpit2.py:1463` |
| `cl_remove` | `cockpit2.py:1478` |
| `m_add_kpi` | `cockpit2.py:1488` |
| `m_add_from_def` | `cockpit2.py:1520` |
| `def_add` | `cockpit2.py:1535` |
| `catalog_publish` | `cockpit2.py:1557` |
| `def_amend` | `cockpit2.py:1583` |
| `m_add_link` | `cockpit2.py:1625` |
| `m_sample` | `cockpit2.py:1636` |
| `m_remove` | `cockpit2.py:1646` |
| `m_pin` | `cockpit2.py:1656` |
| `m_unpin` | `cockpit2.py:1667` |
| `tile_add` | `cockpit2.py:1677` |
| `tile_remove` | `cockpit2.py:1708` |
| `rov2_set` | `cockpit2.py:1718` |
| `rov2_acc_add` | `cockpit2.py:1718` |
| `rov2_acc_remove` | `cockpit2.py:1718` |
| `rov2_dom_add` | `cockpit2.py:1718` |
| `rov2_dom_remove` | `cockpit2.py:1718` |
| `backlog_add` | `cockpit2.py:1750` |
| `backlog_update_staat` | `cockpit2.py:1762` |
| `backlog_update_prioriteit` | `cockpit2.py:1774` |
| `person_edit` | `cockpit2.py:1786` |
| `person_remove` | `cockpit2.py:1803` |


## (c) Concern → store → bestand

De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse en het databestand in `data/` (gitignored).

| Concern (st.…) | Store-klasse | Databestand |
|---|---|---|
| `records` | `Records` | `governance_records.json` |
| `people` | `PeopleStore` | `people.json` |
| `assign` | `Assignments` | `assignments.json` |
| `att` | `AttachmentStore` | `attachments.json` |
| `observations` | `ObservationStore` | `observations.jsonl` |
| `seen` | `SeenStore` | `artefact_seen.json` |
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
_22 routes · 83 dispatch-acties · 19 stores._
