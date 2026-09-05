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
| `ff_beslis` | `cockpit2.py:5442` |
| `ff_cluster` | `cockpit2.py:5570` |
| `ff_promote` | `cockpit2.py:5500` |
| `ff_demote` | `cockpit2.py:5524` |
| `ff_run` | `cockpit2.py:5543` |
| `kb_new` | `cockpit2.py:4805` |
| `kb_intake` | `cockpit2.py:4887` |
| `kb_intake_url` | `cockpit2.py:4904` |
| `kb_stage_edit` | `cockpit2.py:4923` |
| `kb_stage_accept` | `cockpit2.py:4935` |
| `kb_stage_delete` | `cockpit2.py:4954` |
| `kb_stage_merge` | `cockpit2.py:4960` |
| `kb_stage_commit` | `cockpit2.py:4971` |
| `kb_stage_discard` | `cockpit2.py:4991` |
| `kb_atoom_subject` | `cockpit2.py:5246` |
| `kb_atoom_purge` | `cockpit2.py:5230` |
| `tag_voorstel_besluit` | `cockpit2.py:5067` |
| `tag_onderhoud_run` | `cockpit2.py:5217` |
| `copy_stack_inclusie` | `cockpit2.py:5199` |
| `verzoek_besluit` | `cockpit2.py:5086` |
| `kb_blacklist_leeg` | `cockpit2.py:5239` |
| `kb_atoom_edit` | `cockpit2.py:4997` |
| `kb_atoom_related` | `cockpit2.py:5004` |
| `kb_atoom_reference` | `cockpit2.py:5049` |
| `kb_insight_link` | `cockpit2.py:5016` |
| `kb_insight_unlink` | `cockpit2.py:5023` |
| `kb_meta_start` | `cockpit2.py:5029` |
| `kb_atoom_merge` | `cockpit2.py:5257` |
| `kb_atoom_archive` | `cockpit2.py:5278` |
| `kb_atoom_unarchive` | `cockpit2.py:5287` |
| `kb_atoom_naar_spel` | `cockpit2.py:5293` |
| `kb_spel_start` | `cockpit2.py:5314` |
| `kb_spel_add` | `cockpit2.py:5328` |
| `kb_spel_remove` | `cockpit2.py:5338` |
| `kb_spel_flip` | `cockpit2.py:5345` |
| `kb_spel_finish` | `cockpit2.py:5351` |
| `kb_link` | `cockpit2.py:4814` |
| `kb_unlink` | `cockpit2.py:4828` |
| `kb_annotate` | `cockpit2.py:4839` |
| `kb_evidence` | `cockpit2.py:4845` |
| `kb_discuss` | `cockpit2.py:4866` |
| `kb_reformulate` | `cockpit2.py:4872` |
| `kw_nominate` | `cockpit2.py:5362` |
| `kw_nom_accept` | `cockpit2.py:5373` |
| `kw_nom_reject` | `cockpit2.py:5391` |
| `ws_forbid` | `cockpit2.py:5421` |
| `ws_approve` | `cockpit2.py:5426` |
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
| `proj_doc_edit` | `cockpit2.py:1772` |
| `verslag_bevestig` | `cockpit2.py:1692` |
| `verslag_overslaan` | `cockpit2.py:1726` |
| `verslag_bijwerken` | `cockpit2.py:1750` |
| `proj_regen_doc` | `cockpit2.py:1670` |
| `proj_settrekker` | `cockpit2.py:1785` |
| `proj_setowner` | `cockpit2.py:1826` |
| `proj_approve` | `cockpit2.py:1845` |
| `proj_discard` | `cockpit2.py:1856` |
| `proj_proposal_accept` | `cockpit2.py:1867` |
| `proj_proposal_reject` | `cockpit2.py:1880` |
| `proj_setlabel` | `cockpit2.py:1893` |
| `proj_setimpact` | `cockpit2.py:1908` |
| `proj_seteffort` | `cockpit2.py:1927` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1950` |
| `proj_setprivate` | `cockpit2.py:1974` |
| `proj_setdue` | `cockpit2.py:1985` |
| `attach_add` | `cockpit2.py:1996` |
| `attach_remove` | `cockpit2.py:2007` |
| `react_add` | `cockpit2.py:2017` |
| `feed_edit` | `cockpit2.py:2027` |
| `feed_remove` | `cockpit2.py:2037` |
| `wall_outcome` | `cockpit2.py:3583` |
| `notif_read` | `cockpit2.py:3679` |
| `notif_processed` | `cockpit2.py:3684` |
| `notif_outcome` | `cockpit2.py:3903` |
| `notif_klaar` | `cockpit2.py:3850` |
| `notif_delete` | `cockpit2.py:3689` |
| `notif_add` | `cockpit2.py:3801` |
| `notif_archive` | `cockpit2.py:4020` |
| `metrics2_fav` | `cockpit2.py:3695` |
| `metrics2_unfav` | `cockpit2.py:3705` |
| `metrics2_form` | `cockpit2.py:3710` |
| `metrics2_dim` | `cockpit2.py:3716` |
| `metrics2_compare` | `cockpit2.py:3723` |
| `metrics2_formula` | `cockpit2.py:3786` |
| `source_activate` | `cockpit2.py:3769` |
| `source_deactivate` | `cockpit2.py:3778` |
| `link_pursue` | `cockpit2.py:3750` |
| `link_ignore` | `cockpit2.py:3760` |
| `acc_check` | `cockpit2.py:3731` |
| `ai_reply` | `cockpit2.py:2046` |
| `proj_feed` | `cockpit2.py:2057` |
| `checklist_add` | `cockpit2.py:2104` |
| `checklist_remove` | `cockpit2.py:2115` |
| `check_add` | `cockpit2.py:2163` |
| `check_accept` | `cockpit2.py:2180` |
| `check_toggle` | `cockpit2.py:2190` |
| `check_skip` | `cockpit2.py:2212` |
| `check_unskip` | `cockpit2.py:2224` |
| `check_handoff` | `cockpit2.py:2236` |
| `check_remove` | `cockpit2.py:2250` |
| `role_assign` | `cockpit2.py:2260` |
| `role_unassign` | `cockpit2.py:2278` |
| `role_focus` | `cockpit2.py:2297` |
| `radar_approve` | `cockpit2.py:2330` |
| `radar_dismiss` | `cockpit2.py:2340` |
| `radar_promote` | `cockpit2.py:2344` |
| `radar_merge` | `cockpit2.py:2364` |
| `radar_koppel` | `cockpit2.py:2380` |
| `kb_stage_koppel` | `cockpit2.py:2407` |
| `aitask_add` | `cockpit2.py:2445` |
| `aitask_remove` | `cockpit2.py:2476` |
| `skilllink_add` | `cockpit2.py:2504` |
| `means_gap_add` | `cockpit2.py:2534` |
| `persona_skill_add` | `cockpit2.py:2688` |
| `rov2_add` | `cockpit2.py:2703` |
| `rov2_add_to_group` | `cockpit2.py:2715` |
| `rov2_remove` | `cockpit2.py:2727` |
| `rov2_remove_group` | `cockpit2.py:2742` |
| `rov2_setkind` | `cockpit2.py:2760` |
| `rov2_consent` | `cockpit2.py:2773` |
| `rov2_end` | `cockpit2.py:2795` |
| `wo_open` | `cockpit2.py:2819` |
| `wo_close` | `cockpit2.py:2829` |
| `wo_presence` | `cockpit2.py:2845` |
| `wo_present_all` | `cockpit2.py:2856` |
| `vangst_add` | `cockpit2.py:2868` |
| `vangst_tekst` | `cockpit2.py:2916` |
| `vangst_klaar` | `cockpit2.py:2926` |
| `vangst_uitkomst` | `cockpit2.py:2975` |
| `vangst_uitkomst_weg` | `cockpit2.py:2963` |
| `vangst_uitkomst_edit` | `cockpit2.py:2938` |
| `vangst_remove` | `cockpit2.py:2907` |
| `vangst_verwerk` | `cockpit2.py:3091` |
| `wo_checkout` | `cockpit2.py:4025` |
| `noochie_send` | `cockpit2.py:4040` |
| `noochie_reset` | `cockpit2.py:4066` |
| `noochie_ctx` | `cockpit2.py:4073` |
| `cl_add` | `cockpit2.py:4080` |
| `cl_report` | `cockpit2.py:4098` |
| `cl_remove` | `cockpit2.py:4113` |
| `m_add_kpi` | `cockpit2.py:4123` |
| `m_add_from_def` | `cockpit2.py:4155` |
| `def_add` | `cockpit2.py:4170` |
| `catalog_publish` | `cockpit2.py:4192` |
| `def_amend` | `cockpit2.py:4218` |
| `m_add_link` | `cockpit2.py:4260` |
| `m_sample` | `cockpit2.py:4271` |
| `m_remove` | `cockpit2.py:4281` |
| `m_pin` | `cockpit2.py:4291` |
| `m_unpin` | `cockpit2.py:4302` |
| `tile_add` | `cockpit2.py:4340` |
| `indicator_activate` | `cockpit2.py:4312` |
| `tile_remove` | `cockpit2.py:4374` |
| `rov2_set` | `cockpit2.py:4384` |
| `rov2_acc_add` | `cockpit2.py:4384` |
| `rov2_acc_remove` | `cockpit2.py:4384` |
| `rov2_dom_add` | `cockpit2.py:4384` |
| `rov2_dom_remove` | `cockpit2.py:4384` |
| `backlog_add` | `cockpit2.py:4416` |
| `backlog_update_staat` | `cockpit2.py:4428` |
| `backlog_update_prioriteit` | `cockpit2.py:4440` |
| `person_edit` | `cockpit2.py:4452` |
| `person_remove` | `cockpit2.py:4469` |
| `lk_mute` | `cockpit2.py:4490` |
| `claims_term_add` | `cockpit2.py:4593` |
| `claims_term_retract` | `cockpit2.py:4630` |
| `claims_work_status` | `cockpit2.py:4614` |
| `claims_bewijs_link` | `cockpit2.py:4659` |
| `claims_vondst_whitelist` | `cockpit2.py:4683` |
| `claims_regel_uit_vondst` | `cockpit2.py:4709` |
| `claims_to_board` | `cockpit2.py:4741` |
| `persona_edit` | `cockpit2.py:2587` |
| `persona_llm` | `cockpit2.py:2606` |
| `persona_finetune` | `cockpit2.py:2623` |
| `persona_finetune_apply` | `cockpit2.py:2641` |


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
