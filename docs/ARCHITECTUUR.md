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
| `/backlog` | `render_backlog` | `nooch_village/views/backlog.py` |
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/aitask` | `render_aitask` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
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
| `/vangst` | `render_vangst_frag` | `nooch_village/views/vangst.py` |
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/livekit-presence` | `(inline)` | `cockpit2.py` |
| `/claims/db.json` | `(inline)` | `cockpit2.py` |
| `/claims` | `render_claims` | `nooch_village/views/claims.py` |
| `/copy-check` | `render_copy_check` | `nooch_village/views/copy_check.py` |
| `/copy-prompt` | `render_copy_prompt` | `nooch_village/views/copy_prompt.py` |
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `ff_beslis` | `cockpit2.py:5448` |
| `ff_cluster` | `cockpit2.py:5576` |
| `ff_promote` | `cockpit2.py:5506` |
| `ff_demote` | `cockpit2.py:5530` |
| `ff_run` | `cockpit2.py:5549` |
| `kb_new` | `cockpit2.py:4811` |
| `kb_intake` | `cockpit2.py:4893` |
| `kb_intake_url` | `cockpit2.py:4910` |
| `kb_stage_edit` | `cockpit2.py:4929` |
| `kb_stage_accept` | `cockpit2.py:4941` |
| `kb_stage_delete` | `cockpit2.py:4960` |
| `kb_stage_merge` | `cockpit2.py:4966` |
| `kb_stage_commit` | `cockpit2.py:4977` |
| `kb_stage_discard` | `cockpit2.py:4997` |
| `kb_atoom_subject` | `cockpit2.py:5252` |
| `kb_atoom_purge` | `cockpit2.py:5236` |
| `tag_voorstel_besluit` | `cockpit2.py:5073` |
| `tag_onderhoud_run` | `cockpit2.py:5223` |
| `copy_stack_inclusie` | `cockpit2.py:5205` |
| `verzoek_besluit` | `cockpit2.py:5092` |
| `kb_blacklist_leeg` | `cockpit2.py:5245` |
| `kb_atoom_edit` | `cockpit2.py:5003` |
| `kb_atoom_related` | `cockpit2.py:5010` |
| `kb_atoom_reference` | `cockpit2.py:5055` |
| `kb_insight_link` | `cockpit2.py:5022` |
| `kb_insight_unlink` | `cockpit2.py:5029` |
| `kb_meta_start` | `cockpit2.py:5035` |
| `kb_atoom_merge` | `cockpit2.py:5263` |
| `kb_atoom_archive` | `cockpit2.py:5284` |
| `kb_atoom_unarchive` | `cockpit2.py:5293` |
| `kb_atoom_naar_spel` | `cockpit2.py:5299` |
| `kb_spel_start` | `cockpit2.py:5320` |
| `kb_spel_add` | `cockpit2.py:5334` |
| `kb_spel_remove` | `cockpit2.py:5344` |
| `kb_spel_flip` | `cockpit2.py:5351` |
| `kb_spel_finish` | `cockpit2.py:5357` |
| `kb_link` | `cockpit2.py:4820` |
| `kb_unlink` | `cockpit2.py:4834` |
| `kb_annotate` | `cockpit2.py:4845` |
| `kb_evidence` | `cockpit2.py:4851` |
| `kb_discuss` | `cockpit2.py:4872` |
| `kb_reformulate` | `cockpit2.py:4878` |
| `kw_nominate` | `cockpit2.py:5368` |
| `kw_nom_accept` | `cockpit2.py:5379` |
| `kw_nom_reject` | `cockpit2.py:5397` |
| `ws_forbid` | `cockpit2.py:5427` |
| `ws_approve` | `cockpit2.py:5432` |
| `proj_add` | `cockpit2.py:1209` |
| `artefact_add` | `cockpit2.py:1262` |
| `artefact_edit` | `cockpit2.py:1306` |
| `artefact_archive` | `cockpit2.py:1333` |
| `pagina_feit_add` | `cockpit2.py:1353` |
| `pagina_feit_del` | `cockpit2.py:1382` |
| `pagina_voorstel` | `cockpit2.py:1413` |
| `proj_status` | `cockpit2.py:1443` |
| `proj_done` | `cockpit2.py:1461` |
| `proj_dod` | `cockpit2.py:1551` |
| `proj_archive` | `cockpit2.py:1565` |
| `proj_unarchive` | `cockpit2.py:1588` |
| `proj_delete` | `cockpit2.py:1598` |
| `proj_edit` | `cockpit2.py:1625` |
| `proj_comment` | `cockpit2.py:1638` |
| `proj_rename` | `cockpit2.py:1648` |
| `proj_describe` | `cockpit2.py:1659` |
| `proj_doc_edit` | `cockpit2.py:1778` |
| `verslag_bevestig` | `cockpit2.py:1692` |
| `verslag_overslaan` | `cockpit2.py:1732` |
| `verslag_bijwerken` | `cockpit2.py:1756` |
| `proj_regen_doc` | `cockpit2.py:1670` |
| `proj_settrekker` | `cockpit2.py:1791` |
| `proj_setowner` | `cockpit2.py:1832` |
| `proj_approve` | `cockpit2.py:1851` |
| `proj_discard` | `cockpit2.py:1862` |
| `proj_proposal_accept` | `cockpit2.py:1873` |
| `proj_proposal_reject` | `cockpit2.py:1886` |
| `proj_setlabel` | `cockpit2.py:1899` |
| `proj_setimpact` | `cockpit2.py:1914` |
| `proj_seteffort` | `cockpit2.py:1933` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1956` |
| `proj_setprivate` | `cockpit2.py:1980` |
| `proj_setdue` | `cockpit2.py:1991` |
| `attach_add` | `cockpit2.py:2002` |
| `attach_remove` | `cockpit2.py:2013` |
| `react_add` | `cockpit2.py:2023` |
| `feed_edit` | `cockpit2.py:2033` |
| `feed_remove` | `cockpit2.py:2043` |
| `wall_outcome` | `cockpit2.py:3589` |
| `notif_read` | `cockpit2.py:3685` |
| `notif_processed` | `cockpit2.py:3690` |
| `notif_outcome` | `cockpit2.py:3909` |
| `notif_klaar` | `cockpit2.py:3856` |
| `notif_delete` | `cockpit2.py:3695` |
| `notif_add` | `cockpit2.py:3807` |
| `notif_archive` | `cockpit2.py:4026` |
| `metrics2_fav` | `cockpit2.py:3701` |
| `metrics2_unfav` | `cockpit2.py:3711` |
| `metrics2_form` | `cockpit2.py:3716` |
| `metrics2_dim` | `cockpit2.py:3722` |
| `metrics2_compare` | `cockpit2.py:3729` |
| `metrics2_formula` | `cockpit2.py:3792` |
| `source_activate` | `cockpit2.py:3775` |
| `source_deactivate` | `cockpit2.py:3784` |
| `link_pursue` | `cockpit2.py:3756` |
| `link_ignore` | `cockpit2.py:3766` |
| `acc_check` | `cockpit2.py:3737` |
| `ai_reply` | `cockpit2.py:2052` |
| `proj_feed` | `cockpit2.py:2063` |
| `checklist_add` | `cockpit2.py:2110` |
| `checklist_remove` | `cockpit2.py:2121` |
| `check_add` | `cockpit2.py:2169` |
| `check_accept` | `cockpit2.py:2186` |
| `check_toggle` | `cockpit2.py:2196` |
| `check_skip` | `cockpit2.py:2218` |
| `check_unskip` | `cockpit2.py:2230` |
| `check_handoff` | `cockpit2.py:2242` |
| `check_remove` | `cockpit2.py:2256` |
| `role_assign` | `cockpit2.py:2266` |
| `role_unassign` | `cockpit2.py:2284` |
| `role_focus` | `cockpit2.py:2303` |
| `radar_approve` | `cockpit2.py:2336` |
| `radar_dismiss` | `cockpit2.py:2346` |
| `radar_promote` | `cockpit2.py:2350` |
| `radar_merge` | `cockpit2.py:2370` |
| `radar_koppel` | `cockpit2.py:2386` |
| `kb_stage_koppel` | `cockpit2.py:2413` |
| `aitask_add` | `cockpit2.py:2451` |
| `aitask_remove` | `cockpit2.py:2482` |
| `skilllink_add` | `cockpit2.py:2510` |
| `means_gap_add` | `cockpit2.py:2540` |
| `persona_skill_add` | `cockpit2.py:2694` |
| `rov2_add` | `cockpit2.py:2709` |
| `rov2_add_to_group` | `cockpit2.py:2721` |
| `rov2_remove` | `cockpit2.py:2733` |
| `rov2_remove_group` | `cockpit2.py:2748` |
| `rov2_setkind` | `cockpit2.py:2766` |
| `rov2_consent` | `cockpit2.py:2779` |
| `rov2_end` | `cockpit2.py:2801` |
| `wo_open` | `cockpit2.py:2825` |
| `wo_close` | `cockpit2.py:2835` |
| `wo_presence` | `cockpit2.py:2851` |
| `wo_present_all` | `cockpit2.py:2862` |
| `vangst_add` | `cockpit2.py:2874` |
| `vangst_tekst` | `cockpit2.py:2922` |
| `vangst_klaar` | `cockpit2.py:2932` |
| `vangst_uitkomst` | `cockpit2.py:2981` |
| `vangst_uitkomst_weg` | `cockpit2.py:2969` |
| `vangst_uitkomst_edit` | `cockpit2.py:2944` |
| `vangst_remove` | `cockpit2.py:2913` |
| `vangst_verwerk` | `cockpit2.py:3097` |
| `wo_checkout` | `cockpit2.py:4031` |
| `noochie_send` | `cockpit2.py:4046` |
| `noochie_reset` | `cockpit2.py:4072` |
| `noochie_ctx` | `cockpit2.py:4079` |
| `cl_add` | `cockpit2.py:4086` |
| `cl_report` | `cockpit2.py:4104` |
| `cl_remove` | `cockpit2.py:4119` |
| `m_add_kpi` | `cockpit2.py:4129` |
| `m_add_from_def` | `cockpit2.py:4161` |
| `def_add` | `cockpit2.py:4176` |
| `catalog_publish` | `cockpit2.py:4198` |
| `def_amend` | `cockpit2.py:4224` |
| `m_add_link` | `cockpit2.py:4266` |
| `m_sample` | `cockpit2.py:4277` |
| `m_remove` | `cockpit2.py:4287` |
| `m_pin` | `cockpit2.py:4297` |
| `m_unpin` | `cockpit2.py:4308` |
| `tile_add` | `cockpit2.py:4346` |
| `indicator_activate` | `cockpit2.py:4318` |
| `tile_remove` | `cockpit2.py:4380` |
| `rov2_set` | `cockpit2.py:4390` |
| `rov2_acc_add` | `cockpit2.py:4390` |
| `rov2_acc_remove` | `cockpit2.py:4390` |
| `rov2_dom_add` | `cockpit2.py:4390` |
| `rov2_dom_remove` | `cockpit2.py:4390` |
| `backlog_add` | `cockpit2.py:4422` |
| `backlog_update_staat` | `cockpit2.py:4434` |
| `backlog_update_prioriteit` | `cockpit2.py:4446` |
| `person_edit` | `cockpit2.py:4458` |
| `person_remove` | `cockpit2.py:4475` |
| `lk_mute` | `cockpit2.py:4496` |
| `claims_term_add` | `cockpit2.py:4599` |
| `claims_term_retract` | `cockpit2.py:4636` |
| `claims_work_status` | `cockpit2.py:4620` |
| `claims_bewijs_link` | `cockpit2.py:4665` |
| `claims_vondst_whitelist` | `cockpit2.py:4689` |
| `claims_regel_uit_vondst` | `cockpit2.py:4715` |
| `claims_to_board` | `cockpit2.py:4747` |
| `persona_edit` | `cockpit2.py:2593` |
| `persona_llm` | `cockpit2.py:2612` |
| `persona_finetune` | `cockpit2.py:2629` |
| `persona_finetune_apply` | `cockpit2.py:2647` |


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
| `copy_stack` | `CopyStackConfig` | `copy_stack.json` |
| `radar` | `RadarStore` | `radar.json` |
| `radar_besluiten` | `ClusterBesluitStore` | `radar_clusters.json` |
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `notes` | `NotesStore` | `notes.json` |
| `spel` | `SpelStore` | `kennisbank_spel.json` |
| `staging` | `StagingStore` | `kennisbank_staging.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


---
_59 routes · 191 dispatch-acties · 32 stores._
