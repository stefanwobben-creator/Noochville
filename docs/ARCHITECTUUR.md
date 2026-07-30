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
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/signals` | `render_signals` | `nooch_village/views/signals.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/codie` | `render_codie` | `nooch_village/views/codie.py` |
| `/inzichten` | `render_kennislaag` | `nooch_village/views/kennislaag.py` |
| `/kennisbank` | `render_kennisbank` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/search` | `render_kennisbank_search` | `nooch_village/views/kennisbank.py` |
| `/kennisbank/tags` | `render_tag_onderhoud` | `nooch_village/views/tag_onderhoud.py` |
| `/kennisbank/staging` | `render_kennisbank_staging` | `nooch_village/views/kennisbank_staging.py` |
| `/kennisbank/spel` | `render_kennisbank_spel` | `nooch_village/views/kennisbank_spel.py` |
| `/kennisbank/spel/search` | `render_kennisbank_spel_search` | `nooch_village/views/kennisbank_spel.py` |
| `/linkbuilding` | `render_linkbuilding` | `nooch_village/views/linkbuilding.py` |
| `/accountabilities` | `render_accountabilities` | `nooch_village/views/accountabilities.py` |
| `/woordenschat` | `render_woordenschat` | `nooch_village/views/woordenschat.py` |
| `/keywords` | `render_keyword_lens` | `nooch_village/views/keyword_lens.py` |
| `/long-term-trends` | `(inline)` | `cockpit2.py` |
| `/belofte` | `render_belofte` | `nooch_village/views/belofte.py` |
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
| `/claims/db.json` | `(inline)` | `cockpit2.py` |
| `/claims` | `render_claims` | `nooch_village/views/claims.py` |
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `kb_new` | `cockpit2.py:3832` |
| `kb_intake` | `cockpit2.py:3914` |
| `kb_intake_url` | `cockpit2.py:3931` |
| `kb_stage_edit` | `cockpit2.py:3950` |
| `kb_stage_accept` | `cockpit2.py:3962` |
| `kb_stage_delete` | `cockpit2.py:3981` |
| `kb_stage_merge` | `cockpit2.py:3987` |
| `kb_stage_commit` | `cockpit2.py:3998` |
| `kb_stage_discard` | `cockpit2.py:4018` |
| `kb_atoom_subject` | `cockpit2.py:4142` |
| `kb_atoom_purge` | `cockpit2.py:4126` |
| `tag_voorstel_besluit` | `cockpit2.py:4094` |
| `tag_onderhoud_run` | `cockpit2.py:4113` |
| `kb_blacklist_leeg` | `cockpit2.py:4135` |
| `kb_atoom_edit` | `cockpit2.py:4024` |
| `kb_atoom_related` | `cockpit2.py:4031` |
| `kb_atoom_reference` | `cockpit2.py:4076` |
| `kb_insight_link` | `cockpit2.py:4043` |
| `kb_insight_unlink` | `cockpit2.py:4050` |
| `kb_meta_start` | `cockpit2.py:4056` |
| `kb_atoom_merge` | `cockpit2.py:4153` |
| `kb_atoom_archive` | `cockpit2.py:4174` |
| `kb_atoom_unarchive` | `cockpit2.py:4183` |
| `kb_atoom_naar_spel` | `cockpit2.py:4189` |
| `kb_spel_start` | `cockpit2.py:4210` |
| `kb_spel_add` | `cockpit2.py:4224` |
| `kb_spel_remove` | `cockpit2.py:4234` |
| `kb_spel_flip` | `cockpit2.py:4241` |
| `kb_spel_finish` | `cockpit2.py:4247` |
| `kb_link` | `cockpit2.py:3841` |
| `kb_unlink` | `cockpit2.py:3855` |
| `kb_annotate` | `cockpit2.py:3866` |
| `kb_evidence` | `cockpit2.py:3872` |
| `kb_discuss` | `cockpit2.py:3893` |
| `kb_reformulate` | `cockpit2.py:3899` |
| `kw_nominate` | `cockpit2.py:4258` |
| `kw_nom_accept` | `cockpit2.py:4269` |
| `kw_nom_reject` | `cockpit2.py:4287` |
| `ws_forbid` | `cockpit2.py:4317` |
| `ws_approve` | `cockpit2.py:4322` |
| `proj_add` | `cockpit2.py:1132` |
| `artefact_add` | `cockpit2.py:1167` |
| `artefact_edit` | `cockpit2.py:1208` |
| `artefact_archive` | `cockpit2.py:1232` |
| `proj_status` | `cockpit2.py:1252` |
| `proj_done` | `cockpit2.py:1270` |
| `proj_dod` | `cockpit2.py:1319` |
| `proj_archive` | `cockpit2.py:1333` |
| `proj_unarchive` | `cockpit2.py:1356` |
| `proj_delete` | `cockpit2.py:1366` |
| `proj_edit` | `cockpit2.py:1393` |
| `proj_comment` | `cockpit2.py:1406` |
| `proj_rename` | `cockpit2.py:1416` |
| `proj_describe` | `cockpit2.py:1427` |
| `proj_doc_edit` | `cockpit2.py:1460` |
| `proj_regen_doc` | `cockpit2.py:1438` |
| `proj_settrekker` | `cockpit2.py:1473` |
| `proj_setowner` | `cockpit2.py:1510` |
| `proj_approve` | `cockpit2.py:1529` |
| `proj_discard` | `cockpit2.py:1540` |
| `proj_proposal_accept` | `cockpit2.py:1551` |
| `proj_proposal_reject` | `cockpit2.py:1564` |
| `proj_setlabel` | `cockpit2.py:1577` |
| `proj_setimpact` | `cockpit2.py:1592` |
| `proj_seteffort` | `cockpit2.py:1611` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1634` |
| `proj_setprivate` | `cockpit2.py:1658` |
| `proj_setdue` | `cockpit2.py:1669` |
| `attach_add` | `cockpit2.py:1680` |
| `attach_remove` | `cockpit2.py:1691` |
| `react_add` | `cockpit2.py:1701` |
| `feed_edit` | `cockpit2.py:1711` |
| `feed_remove` | `cockpit2.py:1721` |
| `wall_outcome` | `cockpit2.py:2671` |
| `notif_read` | `cockpit2.py:2769` |
| `notif_processed` | `cockpit2.py:2774` |
| `notif_outcome` | `cockpit2.py:2921` |
| `notif_besluit` | `cockpit2.py:3008` |
| `notif_klaar` | `cockpit2.py:2907` |
| `notif_delete` | `cockpit2.py:2779` |
| `notif_add` | `cockpit2.py:2891` |
| `notif_archive` | `cockpit2.py:3050` |
| `metrics2_fav` | `cockpit2.py:2785` |
| `metrics2_unfav` | `cockpit2.py:2795` |
| `metrics2_form` | `cockpit2.py:2800` |
| `metrics2_dim` | `cockpit2.py:2806` |
| `metrics2_compare` | `cockpit2.py:2813` |
| `metrics2_formula` | `cockpit2.py:2876` |
| `source_activate` | `cockpit2.py:2859` |
| `source_deactivate` | `cockpit2.py:2868` |
| `link_pursue` | `cockpit2.py:2840` |
| `link_ignore` | `cockpit2.py:2850` |
| `acc_check` | `cockpit2.py:2821` |
| `ai_reply` | `cockpit2.py:1730` |
| `proj_feed` | `cockpit2.py:1741` |
| `checklist_add` | `cockpit2.py:1771` |
| `checklist_remove` | `cockpit2.py:1782` |
| `check_add` | `cockpit2.py:1830` |
| `check_accept` | `cockpit2.py:1847` |
| `check_toggle` | `cockpit2.py:1857` |
| `check_skip` | `cockpit2.py:1879` |
| `check_unskip` | `cockpit2.py:1891` |
| `check_handoff` | `cockpit2.py:1903` |
| `check_remove` | `cockpit2.py:1917` |
| `role_assign` | `cockpit2.py:1927` |
| `role_unassign` | `cockpit2.py:1945` |
| `role_focus` | `cockpit2.py:1964` |
| `radar_approve` | `cockpit2.py:1997` |
| `radar_dismiss` | `cockpit2.py:2007` |
| `radar_promote` | `cockpit2.py:2011` |
| `radar_merge` | `cockpit2.py:2031` |
| `radar_koppel` | `cockpit2.py:2047` |
| `kb_stage_koppel` | `cockpit2.py:2074` |
| `aitask_add` | `cockpit2.py:2112` |
| `aitask_remove` | `cockpit2.py:2143` |
| `skilllink_add` | `cockpit2.py:2171` |
| `means_gap_add` | `cockpit2.py:2201` |
| `persona_skill_add` | `cockpit2.py:2355` |
| `rov2_add` | `cockpit2.py:2370` |
| `rov2_add_to_group` | `cockpit2.py:2382` |
| `rov2_remove` | `cockpit2.py:2394` |
| `rov2_remove_group` | `cockpit2.py:2409` |
| `rov2_setkind` | `cockpit2.py:2427` |
| `rov2_consent` | `cockpit2.py:2440` |
| `rov2_end` | `cockpit2.py:2462` |
| `wo_open` | `cockpit2.py:2486` |
| `wo_close` | `cockpit2.py:2496` |
| `wo_presence` | `cockpit2.py:2512` |
| `wo_present_all` | `cockpit2.py:2523` |
| `wo_ag_add` | `cockpit2.py:2535` |
| `wo_ag_remove` | `cockpit2.py:2547` |
| `wo_ag_note` | `cockpit2.py:2557` |
| `wo_ag_reopen` | `cockpit2.py:2569` |
| `wo_ag_resolve` | `cockpit2.py:2645` |
| `wo_checkout` | `cockpit2.py:3055` |
| `noochie_send` | `cockpit2.py:3067` |
| `noochie_reset` | `cockpit2.py:3093` |
| `noochie_ctx` | `cockpit2.py:3100` |
| `cl_add` | `cockpit2.py:3107` |
| `cl_report` | `cockpit2.py:3125` |
| `cl_remove` | `cockpit2.py:3140` |
| `m_add_kpi` | `cockpit2.py:3150` |
| `m_add_from_def` | `cockpit2.py:3182` |
| `def_add` | `cockpit2.py:3197` |
| `catalog_publish` | `cockpit2.py:3219` |
| `def_amend` | `cockpit2.py:3245` |
| `m_add_link` | `cockpit2.py:3287` |
| `m_sample` | `cockpit2.py:3298` |
| `m_remove` | `cockpit2.py:3308` |
| `m_pin` | `cockpit2.py:3318` |
| `m_unpin` | `cockpit2.py:3329` |
| `tile_add` | `cockpit2.py:3367` |
| `indicator_activate` | `cockpit2.py:3339` |
| `tile_remove` | `cockpit2.py:3401` |
| `rov2_set` | `cockpit2.py:3411` |
| `rov2_acc_add` | `cockpit2.py:3411` |
| `rov2_acc_remove` | `cockpit2.py:3411` |
| `rov2_dom_add` | `cockpit2.py:3411` |
| `rov2_dom_remove` | `cockpit2.py:3411` |
| `backlog_add` | `cockpit2.py:3443` |
| `backlog_update_staat` | `cockpit2.py:3455` |
| `backlog_update_prioriteit` | `cockpit2.py:3467` |
| `person_edit` | `cockpit2.py:3479` |
| `person_remove` | `cockpit2.py:3496` |
| `lk_mute` | `cockpit2.py:3517` |
| `claims_term_add` | `cockpit2.py:3620` |
| `claims_term_retract` | `cockpit2.py:3657` |
| `claims_work_status` | `cockpit2.py:3641` |
| `claims_bewijs_link` | `cockpit2.py:3686` |
| `claims_vondst_whitelist` | `cockpit2.py:3710` |
| `claims_regel_uit_vondst` | `cockpit2.py:3736` |
| `claims_to_board` | `cockpit2.py:3768` |
| `persona_edit` | `cockpit2.py:2254` |
| `persona_llm` | `cockpit2.py:2273` |
| `persona_finetune` | `cockpit2.py:2290` |
| `persona_finetune_apply` | `cockpit2.py:2308` |


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
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `notes` | `NotesStore` | `notes.json` |
| `spel` | `SpelStore` | `kennisbank_spel.json` |
| `staging` | `StagingStore` | `kennisbank_staging.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


---
_52 routes · 176 dispatch-acties · 30 stores._
