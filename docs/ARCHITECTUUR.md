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
| `kb_new` | `cockpit2.py:3706` |
| `kb_intake` | `cockpit2.py:3788` |
| `kb_intake_url` | `cockpit2.py:3805` |
| `kb_stage_edit` | `cockpit2.py:3824` |
| `kb_stage_accept` | `cockpit2.py:3836` |
| `kb_stage_delete` | `cockpit2.py:3855` |
| `kb_stage_merge` | `cockpit2.py:3861` |
| `kb_stage_commit` | `cockpit2.py:3872` |
| `kb_stage_discard` | `cockpit2.py:3892` |
| `kb_atoom_subject` | `cockpit2.py:4016` |
| `kb_atoom_purge` | `cockpit2.py:4000` |
| `tag_voorstel_besluit` | `cockpit2.py:3968` |
| `tag_onderhoud_run` | `cockpit2.py:3987` |
| `kb_blacklist_leeg` | `cockpit2.py:4009` |
| `kb_atoom_edit` | `cockpit2.py:3898` |
| `kb_atoom_related` | `cockpit2.py:3905` |
| `kb_atoom_reference` | `cockpit2.py:3950` |
| `kb_insight_link` | `cockpit2.py:3917` |
| `kb_insight_unlink` | `cockpit2.py:3924` |
| `kb_meta_start` | `cockpit2.py:3930` |
| `kb_atoom_merge` | `cockpit2.py:4027` |
| `kb_atoom_archive` | `cockpit2.py:4048` |
| `kb_atoom_unarchive` | `cockpit2.py:4057` |
| `kb_atoom_naar_spel` | `cockpit2.py:4063` |
| `kb_spel_start` | `cockpit2.py:4084` |
| `kb_spel_add` | `cockpit2.py:4098` |
| `kb_spel_remove` | `cockpit2.py:4108` |
| `kb_spel_flip` | `cockpit2.py:4115` |
| `kb_spel_finish` | `cockpit2.py:4121` |
| `kb_link` | `cockpit2.py:3715` |
| `kb_unlink` | `cockpit2.py:3729` |
| `kb_annotate` | `cockpit2.py:3740` |
| `kb_evidence` | `cockpit2.py:3746` |
| `kb_discuss` | `cockpit2.py:3767` |
| `kb_reformulate` | `cockpit2.py:3773` |
| `kw_nominate` | `cockpit2.py:4132` |
| `kw_nom_accept` | `cockpit2.py:4143` |
| `kw_nom_reject` | `cockpit2.py:4161` |
| `ws_forbid` | `cockpit2.py:4191` |
| `ws_approve` | `cockpit2.py:4196` |
| `proj_add` | `cockpit2.py:1130` |
| `artefact_add` | `cockpit2.py:1165` |
| `artefact_edit` | `cockpit2.py:1206` |
| `artefact_archive` | `cockpit2.py:1230` |
| `proj_status` | `cockpit2.py:1250` |
| `proj_done` | `cockpit2.py:1268` |
| `proj_dod` | `cockpit2.py:1312` |
| `proj_archive` | `cockpit2.py:1326` |
| `proj_unarchive` | `cockpit2.py:1349` |
| `proj_delete` | `cockpit2.py:1359` |
| `proj_edit` | `cockpit2.py:1386` |
| `proj_comment` | `cockpit2.py:1399` |
| `proj_rename` | `cockpit2.py:1409` |
| `proj_describe` | `cockpit2.py:1420` |
| `proj_doc_edit` | `cockpit2.py:1453` |
| `proj_regen_doc` | `cockpit2.py:1431` |
| `proj_settrekker` | `cockpit2.py:1466` |
| `proj_setowner` | `cockpit2.py:1503` |
| `proj_approve` | `cockpit2.py:1522` |
| `proj_discard` | `cockpit2.py:1533` |
| `proj_setlabel` | `cockpit2.py:1544` |
| `proj_setimpact` | `cockpit2.py:1559` |
| `proj_seteffort` | `cockpit2.py:1578` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1601` |
| `proj_setprivate` | `cockpit2.py:1625` |
| `proj_setdue` | `cockpit2.py:1636` |
| `attach_add` | `cockpit2.py:1647` |
| `attach_remove` | `cockpit2.py:1658` |
| `react_add` | `cockpit2.py:1668` |
| `feed_edit` | `cockpit2.py:1678` |
| `feed_remove` | `cockpit2.py:1688` |
| `wall_outcome` | `cockpit2.py:2638` |
| `notif_read` | `cockpit2.py:2736` |
| `notif_processed` | `cockpit2.py:2741` |
| `notif_outcome` | `cockpit2.py:2888` |
| `notif_besluit` | `cockpit2.py:2975` |
| `notif_klaar` | `cockpit2.py:2874` |
| `notif_delete` | `cockpit2.py:2746` |
| `notif_add` | `cockpit2.py:2858` |
| `notif_archive` | `cockpit2.py:3017` |
| `metrics2_fav` | `cockpit2.py:2752` |
| `metrics2_unfav` | `cockpit2.py:2762` |
| `metrics2_form` | `cockpit2.py:2767` |
| `metrics2_dim` | `cockpit2.py:2773` |
| `metrics2_compare` | `cockpit2.py:2780` |
| `metrics2_formula` | `cockpit2.py:2843` |
| `source_activate` | `cockpit2.py:2826` |
| `source_deactivate` | `cockpit2.py:2835` |
| `link_pursue` | `cockpit2.py:2807` |
| `link_ignore` | `cockpit2.py:2817` |
| `acc_check` | `cockpit2.py:2788` |
| `ai_reply` | `cockpit2.py:1697` |
| `proj_feed` | `cockpit2.py:1708` |
| `checklist_add` | `cockpit2.py:1738` |
| `checklist_remove` | `cockpit2.py:1749` |
| `check_add` | `cockpit2.py:1797` |
| `check_accept` | `cockpit2.py:1814` |
| `check_toggle` | `cockpit2.py:1824` |
| `check_skip` | `cockpit2.py:1846` |
| `check_unskip` | `cockpit2.py:1858` |
| `check_handoff` | `cockpit2.py:1870` |
| `check_remove` | `cockpit2.py:1884` |
| `role_assign` | `cockpit2.py:1894` |
| `role_unassign` | `cockpit2.py:1912` |
| `role_focus` | `cockpit2.py:1931` |
| `radar_approve` | `cockpit2.py:1964` |
| `radar_dismiss` | `cockpit2.py:1974` |
| `radar_promote` | `cockpit2.py:1978` |
| `radar_merge` | `cockpit2.py:1998` |
| `radar_koppel` | `cockpit2.py:2014` |
| `kb_stage_koppel` | `cockpit2.py:2041` |
| `aitask_add` | `cockpit2.py:2079` |
| `aitask_remove` | `cockpit2.py:2110` |
| `skilllink_add` | `cockpit2.py:2138` |
| `means_gap_add` | `cockpit2.py:2168` |
| `persona_skill_add` | `cockpit2.py:2322` |
| `rov2_add` | `cockpit2.py:2337` |
| `rov2_add_to_group` | `cockpit2.py:2349` |
| `rov2_remove` | `cockpit2.py:2361` |
| `rov2_remove_group` | `cockpit2.py:2376` |
| `rov2_setkind` | `cockpit2.py:2394` |
| `rov2_consent` | `cockpit2.py:2407` |
| `rov2_end` | `cockpit2.py:2429` |
| `wo_open` | `cockpit2.py:2453` |
| `wo_close` | `cockpit2.py:2463` |
| `wo_presence` | `cockpit2.py:2479` |
| `wo_present_all` | `cockpit2.py:2490` |
| `wo_ag_add` | `cockpit2.py:2502` |
| `wo_ag_remove` | `cockpit2.py:2514` |
| `wo_ag_note` | `cockpit2.py:2524` |
| `wo_ag_reopen` | `cockpit2.py:2536` |
| `wo_ag_resolve` | `cockpit2.py:2612` |
| `wo_checkout` | `cockpit2.py:3022` |
| `noochie_send` | `cockpit2.py:3034` |
| `noochie_reset` | `cockpit2.py:3060` |
| `noochie_ctx` | `cockpit2.py:3067` |
| `cl_add` | `cockpit2.py:3074` |
| `cl_report` | `cockpit2.py:3092` |
| `cl_remove` | `cockpit2.py:3107` |
| `m_add_kpi` | `cockpit2.py:3117` |
| `m_add_from_def` | `cockpit2.py:3149` |
| `def_add` | `cockpit2.py:3164` |
| `catalog_publish` | `cockpit2.py:3186` |
| `def_amend` | `cockpit2.py:3212` |
| `m_add_link` | `cockpit2.py:3254` |
| `m_sample` | `cockpit2.py:3265` |
| `m_remove` | `cockpit2.py:3275` |
| `m_pin` | `cockpit2.py:3285` |
| `m_unpin` | `cockpit2.py:3296` |
| `tile_add` | `cockpit2.py:3334` |
| `indicator_activate` | `cockpit2.py:3306` |
| `tile_remove` | `cockpit2.py:3368` |
| `rov2_set` | `cockpit2.py:3378` |
| `rov2_acc_add` | `cockpit2.py:3378` |
| `rov2_acc_remove` | `cockpit2.py:3378` |
| `rov2_dom_add` | `cockpit2.py:3378` |
| `rov2_dom_remove` | `cockpit2.py:3378` |
| `backlog_add` | `cockpit2.py:3410` |
| `backlog_update_staat` | `cockpit2.py:3422` |
| `backlog_update_prioriteit` | `cockpit2.py:3434` |
| `person_edit` | `cockpit2.py:3446` |
| `person_remove` | `cockpit2.py:3463` |
| `lk_mute` | `cockpit2.py:3484` |
| `claims_term_add` | `cockpit2.py:3587` |
| `claims_term_retract` | `cockpit2.py:3624` |
| `claims_work_status` | `cockpit2.py:3608` |
| `claims_to_board` | `cockpit2.py:3642` |
| `persona_edit` | `cockpit2.py:2221` |
| `persona_llm` | `cockpit2.py:2240` |
| `persona_finetune` | `cockpit2.py:2257` |
| `persona_finetune_apply` | `cockpit2.py:2275` |


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
_51 routes · 171 dispatch-acties · 30 stores._
