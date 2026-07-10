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
| `proj_add` | `cockpit2.py:743` |
| `artefact_add` | `cockpit2.py:771` |
| `artefact_edit` | `cockpit2.py:812` |
| `artefact_archive` | `cockpit2.py:836` |
| `proj_status` | `cockpit2.py:856` |
| `proj_done` | `cockpit2.py:874` |
| `proj_archive` | `cockpit2.py:885` |
| `proj_unarchive` | `cockpit2.py:895` |
| `proj_delete` | `cockpit2.py:905` |
| `proj_edit` | `cockpit2.py:920` |
| `proj_comment` | `cockpit2.py:933` |
| `proj_rename` | `cockpit2.py:943` |
| `proj_describe` | `cockpit2.py:954` |
| `proj_settrekker` | `cockpit2.py:965` |
| `proj_setowner` | `cockpit2.py:1002` |
| `proj_approve` | `cockpit2.py:1021` |
| `proj_discard` | `cockpit2.py:1032` |
| `proj_setlabel` | `cockpit2.py:1043` |
| `proj_setimpact` | `cockpit2.py:1058` |
| `proj_seteffort` | `cockpit2.py:1077` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1100` |
| `proj_setprivate` | `cockpit2.py:1124` |
| `proj_setdue` | `cockpit2.py:1135` |
| `attach_add` | `cockpit2.py:1146` |
| `attach_remove` | `cockpit2.py:1157` |
| `react_add` | `cockpit2.py:1167` |
| `feed_edit` | `cockpit2.py:1177` |
| `feed_remove` | `cockpit2.py:1187` |
| `wall_outcome` | `cockpit2.py:1746` |
| `ai_reply` | `cockpit2.py:1196` |
| `proj_feed` | `cockpit2.py:1207` |
| `checklist_add` | `cockpit2.py:1234` |
| `checklist_remove` | `cockpit2.py:1245` |
| `check_add` | `cockpit2.py:1285` |
| `check_accept` | `cockpit2.py:1301` |
| `check_toggle` | `cockpit2.py:1311` |
| `check_remove` | `cockpit2.py:1321` |
| `role_assign` | `cockpit2.py:1331` |
| `role_unassign` | `cockpit2.py:1349` |
| `role_focus` | `cockpit2.py:1368` |
| `aitask_add` | `cockpit2.py:1387` |
| `aitask_remove` | `cockpit2.py:1413` |
| `persona_skill_add` | `cockpit2.py:1430` |
| `rov2_add` | `cockpit2.py:1445` |
| `rov2_add_to_group` | `cockpit2.py:1457` |
| `rov2_remove` | `cockpit2.py:1469` |
| `rov2_remove_group` | `cockpit2.py:1484` |
| `rov2_setkind` | `cockpit2.py:1502` |
| `rov2_consent` | `cockpit2.py:1515` |
| `rov2_end` | `cockpit2.py:1537` |
| `wo_open` | `cockpit2.py:1561` |
| `wo_close` | `cockpit2.py:1571` |
| `wo_presence` | `cockpit2.py:1587` |
| `wo_present_all` | `cockpit2.py:1598` |
| `wo_ag_add` | `cockpit2.py:1610` |
| `wo_ag_remove` | `cockpit2.py:1622` |
| `wo_ag_note` | `cockpit2.py:1632` |
| `wo_ag_reopen` | `cockpit2.py:1644` |
| `wo_ag_resolve` | `cockpit2.py:1720` |
| `wo_checkout` | `cockpit2.py:1842` |
| `noochie_send` | `cockpit2.py:1854` |
| `noochie_reset` | `cockpit2.py:1880` |
| `noochie_ctx` | `cockpit2.py:1887` |
| `cl_add` | `cockpit2.py:1894` |
| `cl_report` | `cockpit2.py:1912` |
| `cl_remove` | `cockpit2.py:1927` |
| `m_add_kpi` | `cockpit2.py:1937` |
| `m_add_from_def` | `cockpit2.py:1969` |
| `def_add` | `cockpit2.py:1984` |
| `catalog_publish` | `cockpit2.py:2006` |
| `def_amend` | `cockpit2.py:2032` |
| `m_add_link` | `cockpit2.py:2074` |
| `m_sample` | `cockpit2.py:2085` |
| `m_remove` | `cockpit2.py:2095` |
| `m_pin` | `cockpit2.py:2105` |
| `m_unpin` | `cockpit2.py:2116` |
| `tile_add` | `cockpit2.py:2154` |
| `indicator_activate` | `cockpit2.py:2126` |
| `tile_remove` | `cockpit2.py:2188` |
| `rov2_set` | `cockpit2.py:2198` |
| `rov2_acc_add` | `cockpit2.py:2198` |
| `rov2_acc_remove` | `cockpit2.py:2198` |
| `rov2_dom_add` | `cockpit2.py:2198` |
| `rov2_dom_remove` | `cockpit2.py:2198` |
| `backlog_add` | `cockpit2.py:2230` |
| `backlog_update_staat` | `cockpit2.py:2242` |
| `backlog_update_prioriteit` | `cockpit2.py:2254` |
| `person_edit` | `cockpit2.py:2266` |
| `person_remove` | `cockpit2.py:2283` |
| `lk_mute` | `cockpit2.py:2304` |


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
