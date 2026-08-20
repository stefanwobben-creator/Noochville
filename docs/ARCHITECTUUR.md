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
| `/werkoverleg` | `render_werkoverleg` | `nooch_village/views/werkoverleg.py` |
| `/callbar` | `render_callbar` | `nooch_village/views/callbar.py` |
| `/livekit-token` | `(inline)` | `cockpit2.py` |
| `/livekit-presence` | `(inline)` | `cockpit2.py` |
| `/claims/db.json` | `(inline)` | `cockpit2.py` |
| `/claims` | `render_claims` | `nooch_village/views/claims.py` |
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
| `ff_beslis` | `cockpit2.py:4563` |
| `ff_cluster` | `cockpit2.py:4691` |
| `ff_promote` | `cockpit2.py:4621` |
| `ff_demote` | `cockpit2.py:4645` |
| `ff_run` | `cockpit2.py:4664` |
| `kb_new` | `cockpit2.py:3978` |
| `kb_intake` | `cockpit2.py:4060` |
| `kb_intake_url` | `cockpit2.py:4077` |
| `kb_stage_edit` | `cockpit2.py:4096` |
| `kb_stage_accept` | `cockpit2.py:4108` |
| `kb_stage_delete` | `cockpit2.py:4127` |
| `kb_stage_merge` | `cockpit2.py:4133` |
| `kb_stage_commit` | `cockpit2.py:4144` |
| `kb_stage_discard` | `cockpit2.py:4164` |
| `kb_atoom_subject` | `cockpit2.py:4367` |
| `kb_atoom_purge` | `cockpit2.py:4351` |
| `tag_voorstel_besluit` | `cockpit2.py:4240` |
| `tag_onderhoud_run` | `cockpit2.py:4338` |
| `copy_stack_inclusie` | `cockpit2.py:4320` |
| `verzoek_besluit` | `cockpit2.py:4259` |
| `kb_blacklist_leeg` | `cockpit2.py:4360` |
| `kb_atoom_edit` | `cockpit2.py:4170` |
| `kb_atoom_related` | `cockpit2.py:4177` |
| `kb_atoom_reference` | `cockpit2.py:4222` |
| `kb_insight_link` | `cockpit2.py:4189` |
| `kb_insight_unlink` | `cockpit2.py:4196` |
| `kb_meta_start` | `cockpit2.py:4202` |
| `kb_atoom_merge` | `cockpit2.py:4378` |
| `kb_atoom_archive` | `cockpit2.py:4399` |
| `kb_atoom_unarchive` | `cockpit2.py:4408` |
| `kb_atoom_naar_spel` | `cockpit2.py:4414` |
| `kb_spel_start` | `cockpit2.py:4435` |
| `kb_spel_add` | `cockpit2.py:4449` |
| `kb_spel_remove` | `cockpit2.py:4459` |
| `kb_spel_flip` | `cockpit2.py:4466` |
| `kb_spel_finish` | `cockpit2.py:4472` |
| `kb_link` | `cockpit2.py:3987` |
| `kb_unlink` | `cockpit2.py:4001` |
| `kb_annotate` | `cockpit2.py:4012` |
| `kb_evidence` | `cockpit2.py:4018` |
| `kb_discuss` | `cockpit2.py:4039` |
| `kb_reformulate` | `cockpit2.py:4045` |
| `kw_nominate` | `cockpit2.py:4483` |
| `kw_nom_accept` | `cockpit2.py:4494` |
| `kw_nom_reject` | `cockpit2.py:4512` |
| `ws_forbid` | `cockpit2.py:4542` |
| `ws_approve` | `cockpit2.py:4547` |
| `proj_add` | `cockpit2.py:1203` |
| `artefact_add` | `cockpit2.py:1247` |
| `artefact_edit` | `cockpit2.py:1291` |
| `artefact_archive` | `cockpit2.py:1318` |
| `pagina_feit_add` | `cockpit2.py:1338` |
| `pagina_feit_del` | `cockpit2.py:1367` |
| `proj_status` | `cockpit2.py:1398` |
| `proj_done` | `cockpit2.py:1416` |
| `proj_dod` | `cockpit2.py:1465` |
| `proj_archive` | `cockpit2.py:1479` |
| `proj_unarchive` | `cockpit2.py:1502` |
| `proj_delete` | `cockpit2.py:1512` |
| `proj_edit` | `cockpit2.py:1539` |
| `proj_comment` | `cockpit2.py:1552` |
| `proj_rename` | `cockpit2.py:1562` |
| `proj_describe` | `cockpit2.py:1573` |
| `proj_doc_edit` | `cockpit2.py:1606` |
| `proj_regen_doc` | `cockpit2.py:1584` |
| `proj_settrekker` | `cockpit2.py:1619` |
| `proj_setowner` | `cockpit2.py:1656` |
| `proj_approve` | `cockpit2.py:1675` |
| `proj_discard` | `cockpit2.py:1686` |
| `proj_proposal_accept` | `cockpit2.py:1697` |
| `proj_proposal_reject` | `cockpit2.py:1710` |
| `proj_setlabel` | `cockpit2.py:1723` |
| `proj_setimpact` | `cockpit2.py:1738` |
| `proj_seteffort` | `cockpit2.py:1757` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1780` |
| `proj_setprivate` | `cockpit2.py:1804` |
| `proj_setdue` | `cockpit2.py:1815` |
| `attach_add` | `cockpit2.py:1826` |
| `attach_remove` | `cockpit2.py:1837` |
| `react_add` | `cockpit2.py:1847` |
| `feed_edit` | `cockpit2.py:1857` |
| `feed_remove` | `cockpit2.py:1867` |
| `wall_outcome` | `cockpit2.py:2817` |
| `notif_read` | `cockpit2.py:2915` |
| `notif_processed` | `cockpit2.py:2920` |
| `notif_outcome` | `cockpit2.py:3067` |
| `notif_besluit` | `cockpit2.py:3154` |
| `notif_klaar` | `cockpit2.py:3053` |
| `notif_delete` | `cockpit2.py:2925` |
| `notif_add` | `cockpit2.py:3037` |
| `notif_archive` | `cockpit2.py:3196` |
| `metrics2_fav` | `cockpit2.py:2931` |
| `metrics2_unfav` | `cockpit2.py:2941` |
| `metrics2_form` | `cockpit2.py:2946` |
| `metrics2_dim` | `cockpit2.py:2952` |
| `metrics2_compare` | `cockpit2.py:2959` |
| `metrics2_formula` | `cockpit2.py:3022` |
| `source_activate` | `cockpit2.py:3005` |
| `source_deactivate` | `cockpit2.py:3014` |
| `link_pursue` | `cockpit2.py:2986` |
| `link_ignore` | `cockpit2.py:2996` |
| `acc_check` | `cockpit2.py:2967` |
| `ai_reply` | `cockpit2.py:1876` |
| `proj_feed` | `cockpit2.py:1887` |
| `checklist_add` | `cockpit2.py:1917` |
| `checklist_remove` | `cockpit2.py:1928` |
| `check_add` | `cockpit2.py:1976` |
| `check_accept` | `cockpit2.py:1993` |
| `check_toggle` | `cockpit2.py:2003` |
| `check_skip` | `cockpit2.py:2025` |
| `check_unskip` | `cockpit2.py:2037` |
| `check_handoff` | `cockpit2.py:2049` |
| `check_remove` | `cockpit2.py:2063` |
| `role_assign` | `cockpit2.py:2073` |
| `role_unassign` | `cockpit2.py:2091` |
| `role_focus` | `cockpit2.py:2110` |
| `radar_approve` | `cockpit2.py:2143` |
| `radar_dismiss` | `cockpit2.py:2153` |
| `radar_promote` | `cockpit2.py:2157` |
| `radar_merge` | `cockpit2.py:2177` |
| `radar_koppel` | `cockpit2.py:2193` |
| `kb_stage_koppel` | `cockpit2.py:2220` |
| `aitask_add` | `cockpit2.py:2258` |
| `aitask_remove` | `cockpit2.py:2289` |
| `skilllink_add` | `cockpit2.py:2317` |
| `means_gap_add` | `cockpit2.py:2347` |
| `persona_skill_add` | `cockpit2.py:2501` |
| `rov2_add` | `cockpit2.py:2516` |
| `rov2_add_to_group` | `cockpit2.py:2528` |
| `rov2_remove` | `cockpit2.py:2540` |
| `rov2_remove_group` | `cockpit2.py:2555` |
| `rov2_setkind` | `cockpit2.py:2573` |
| `rov2_consent` | `cockpit2.py:2586` |
| `rov2_end` | `cockpit2.py:2608` |
| `wo_open` | `cockpit2.py:2632` |
| `wo_close` | `cockpit2.py:2642` |
| `wo_presence` | `cockpit2.py:2658` |
| `wo_present_all` | `cockpit2.py:2669` |
| `wo_ag_add` | `cockpit2.py:2681` |
| `wo_ag_remove` | `cockpit2.py:2693` |
| `wo_ag_note` | `cockpit2.py:2703` |
| `wo_ag_reopen` | `cockpit2.py:2715` |
| `wo_ag_resolve` | `cockpit2.py:2791` |
| `wo_checkout` | `cockpit2.py:3201` |
| `noochie_send` | `cockpit2.py:3213` |
| `noochie_reset` | `cockpit2.py:3239` |
| `noochie_ctx` | `cockpit2.py:3246` |
| `cl_add` | `cockpit2.py:3253` |
| `cl_report` | `cockpit2.py:3271` |
| `cl_remove` | `cockpit2.py:3286` |
| `m_add_kpi` | `cockpit2.py:3296` |
| `m_add_from_def` | `cockpit2.py:3328` |
| `def_add` | `cockpit2.py:3343` |
| `catalog_publish` | `cockpit2.py:3365` |
| `def_amend` | `cockpit2.py:3391` |
| `m_add_link` | `cockpit2.py:3433` |
| `m_sample` | `cockpit2.py:3444` |
| `m_remove` | `cockpit2.py:3454` |
| `m_pin` | `cockpit2.py:3464` |
| `m_unpin` | `cockpit2.py:3475` |
| `tile_add` | `cockpit2.py:3513` |
| `indicator_activate` | `cockpit2.py:3485` |
| `tile_remove` | `cockpit2.py:3547` |
| `rov2_set` | `cockpit2.py:3557` |
| `rov2_acc_add` | `cockpit2.py:3557` |
| `rov2_acc_remove` | `cockpit2.py:3557` |
| `rov2_dom_add` | `cockpit2.py:3557` |
| `rov2_dom_remove` | `cockpit2.py:3557` |
| `backlog_add` | `cockpit2.py:3589` |
| `backlog_update_staat` | `cockpit2.py:3601` |
| `backlog_update_prioriteit` | `cockpit2.py:3613` |
| `person_edit` | `cockpit2.py:3625` |
| `person_remove` | `cockpit2.py:3642` |
| `lk_mute` | `cockpit2.py:3663` |
| `claims_term_add` | `cockpit2.py:3766` |
| `claims_term_retract` | `cockpit2.py:3803` |
| `claims_work_status` | `cockpit2.py:3787` |
| `claims_bewijs_link` | `cockpit2.py:3832` |
| `claims_vondst_whitelist` | `cockpit2.py:3856` |
| `claims_regel_uit_vondst` | `cockpit2.py:3882` |
| `claims_to_board` | `cockpit2.py:3914` |
| `persona_edit` | `cockpit2.py:2400` |
| `persona_llm` | `cockpit2.py:2419` |
| `persona_finetune` | `cockpit2.py:2436` |
| `persona_finetune_apply` | `cockpit2.py:2454` |


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
_55 routes · 185 dispatch-acties · 32 stores._
