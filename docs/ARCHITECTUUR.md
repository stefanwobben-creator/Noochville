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
| `ff_beslis` | `cockpit2.py:4425` |
| `ff_cluster` | `cockpit2.py:4553` |
| `ff_promote` | `cockpit2.py:4483` |
| `ff_demote` | `cockpit2.py:4507` |
| `ff_run` | `cockpit2.py:4526` |
| `kb_new` | `cockpit2.py:3901` |
| `kb_intake` | `cockpit2.py:3983` |
| `kb_intake_url` | `cockpit2.py:4000` |
| `kb_stage_edit` | `cockpit2.py:4019` |
| `kb_stage_accept` | `cockpit2.py:4031` |
| `kb_stage_delete` | `cockpit2.py:4050` |
| `kb_stage_merge` | `cockpit2.py:4056` |
| `kb_stage_commit` | `cockpit2.py:4067` |
| `kb_stage_discard` | `cockpit2.py:4087` |
| `kb_atoom_subject` | `cockpit2.py:4229` |
| `kb_atoom_purge` | `cockpit2.py:4213` |
| `tag_voorstel_besluit` | `cockpit2.py:4163` |
| `tag_onderhoud_run` | `cockpit2.py:4200` |
| `copy_stack_inclusie` | `cockpit2.py:4182` |
| `kb_blacklist_leeg` | `cockpit2.py:4222` |
| `kb_atoom_edit` | `cockpit2.py:4093` |
| `kb_atoom_related` | `cockpit2.py:4100` |
| `kb_atoom_reference` | `cockpit2.py:4145` |
| `kb_insight_link` | `cockpit2.py:4112` |
| `kb_insight_unlink` | `cockpit2.py:4119` |
| `kb_meta_start` | `cockpit2.py:4125` |
| `kb_atoom_merge` | `cockpit2.py:4240` |
| `kb_atoom_archive` | `cockpit2.py:4261` |
| `kb_atoom_unarchive` | `cockpit2.py:4270` |
| `kb_atoom_naar_spel` | `cockpit2.py:4276` |
| `kb_spel_start` | `cockpit2.py:4297` |
| `kb_spel_add` | `cockpit2.py:4311` |
| `kb_spel_remove` | `cockpit2.py:4321` |
| `kb_spel_flip` | `cockpit2.py:4328` |
| `kb_spel_finish` | `cockpit2.py:4334` |
| `kb_link` | `cockpit2.py:3910` |
| `kb_unlink` | `cockpit2.py:3924` |
| `kb_annotate` | `cockpit2.py:3935` |
| `kb_evidence` | `cockpit2.py:3941` |
| `kb_discuss` | `cockpit2.py:3962` |
| `kb_reformulate` | `cockpit2.py:3968` |
| `kw_nominate` | `cockpit2.py:4345` |
| `kw_nom_accept` | `cockpit2.py:4356` |
| `kw_nom_reject` | `cockpit2.py:4374` |
| `ws_forbid` | `cockpit2.py:4404` |
| `ws_approve` | `cockpit2.py:4409` |
| `proj_add` | `cockpit2.py:1201` |
| `artefact_add` | `cockpit2.py:1236` |
| `artefact_edit` | `cockpit2.py:1277` |
| `artefact_archive` | `cockpit2.py:1301` |
| `proj_status` | `cockpit2.py:1321` |
| `proj_done` | `cockpit2.py:1339` |
| `proj_dod` | `cockpit2.py:1388` |
| `proj_archive` | `cockpit2.py:1402` |
| `proj_unarchive` | `cockpit2.py:1425` |
| `proj_delete` | `cockpit2.py:1435` |
| `proj_edit` | `cockpit2.py:1462` |
| `proj_comment` | `cockpit2.py:1475` |
| `proj_rename` | `cockpit2.py:1485` |
| `proj_describe` | `cockpit2.py:1496` |
| `proj_doc_edit` | `cockpit2.py:1529` |
| `proj_regen_doc` | `cockpit2.py:1507` |
| `proj_settrekker` | `cockpit2.py:1542` |
| `proj_setowner` | `cockpit2.py:1579` |
| `proj_approve` | `cockpit2.py:1598` |
| `proj_discard` | `cockpit2.py:1609` |
| `proj_proposal_accept` | `cockpit2.py:1620` |
| `proj_proposal_reject` | `cockpit2.py:1633` |
| `proj_setlabel` | `cockpit2.py:1646` |
| `proj_setimpact` | `cockpit2.py:1661` |
| `proj_seteffort` | `cockpit2.py:1680` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1703` |
| `proj_setprivate` | `cockpit2.py:1727` |
| `proj_setdue` | `cockpit2.py:1738` |
| `attach_add` | `cockpit2.py:1749` |
| `attach_remove` | `cockpit2.py:1760` |
| `react_add` | `cockpit2.py:1770` |
| `feed_edit` | `cockpit2.py:1780` |
| `feed_remove` | `cockpit2.py:1790` |
| `wall_outcome` | `cockpit2.py:2740` |
| `notif_read` | `cockpit2.py:2838` |
| `notif_processed` | `cockpit2.py:2843` |
| `notif_outcome` | `cockpit2.py:2990` |
| `notif_besluit` | `cockpit2.py:3077` |
| `notif_klaar` | `cockpit2.py:2976` |
| `notif_delete` | `cockpit2.py:2848` |
| `notif_add` | `cockpit2.py:2960` |
| `notif_archive` | `cockpit2.py:3119` |
| `metrics2_fav` | `cockpit2.py:2854` |
| `metrics2_unfav` | `cockpit2.py:2864` |
| `metrics2_form` | `cockpit2.py:2869` |
| `metrics2_dim` | `cockpit2.py:2875` |
| `metrics2_compare` | `cockpit2.py:2882` |
| `metrics2_formula` | `cockpit2.py:2945` |
| `source_activate` | `cockpit2.py:2928` |
| `source_deactivate` | `cockpit2.py:2937` |
| `link_pursue` | `cockpit2.py:2909` |
| `link_ignore` | `cockpit2.py:2919` |
| `acc_check` | `cockpit2.py:2890` |
| `ai_reply` | `cockpit2.py:1799` |
| `proj_feed` | `cockpit2.py:1810` |
| `checklist_add` | `cockpit2.py:1840` |
| `checklist_remove` | `cockpit2.py:1851` |
| `check_add` | `cockpit2.py:1899` |
| `check_accept` | `cockpit2.py:1916` |
| `check_toggle` | `cockpit2.py:1926` |
| `check_skip` | `cockpit2.py:1948` |
| `check_unskip` | `cockpit2.py:1960` |
| `check_handoff` | `cockpit2.py:1972` |
| `check_remove` | `cockpit2.py:1986` |
| `role_assign` | `cockpit2.py:1996` |
| `role_unassign` | `cockpit2.py:2014` |
| `role_focus` | `cockpit2.py:2033` |
| `radar_approve` | `cockpit2.py:2066` |
| `radar_dismiss` | `cockpit2.py:2076` |
| `radar_promote` | `cockpit2.py:2080` |
| `radar_merge` | `cockpit2.py:2100` |
| `radar_koppel` | `cockpit2.py:2116` |
| `kb_stage_koppel` | `cockpit2.py:2143` |
| `aitask_add` | `cockpit2.py:2181` |
| `aitask_remove` | `cockpit2.py:2212` |
| `skilllink_add` | `cockpit2.py:2240` |
| `means_gap_add` | `cockpit2.py:2270` |
| `persona_skill_add` | `cockpit2.py:2424` |
| `rov2_add` | `cockpit2.py:2439` |
| `rov2_add_to_group` | `cockpit2.py:2451` |
| `rov2_remove` | `cockpit2.py:2463` |
| `rov2_remove_group` | `cockpit2.py:2478` |
| `rov2_setkind` | `cockpit2.py:2496` |
| `rov2_consent` | `cockpit2.py:2509` |
| `rov2_end` | `cockpit2.py:2531` |
| `wo_open` | `cockpit2.py:2555` |
| `wo_close` | `cockpit2.py:2565` |
| `wo_presence` | `cockpit2.py:2581` |
| `wo_present_all` | `cockpit2.py:2592` |
| `wo_ag_add` | `cockpit2.py:2604` |
| `wo_ag_remove` | `cockpit2.py:2616` |
| `wo_ag_note` | `cockpit2.py:2626` |
| `wo_ag_reopen` | `cockpit2.py:2638` |
| `wo_ag_resolve` | `cockpit2.py:2714` |
| `wo_checkout` | `cockpit2.py:3124` |
| `noochie_send` | `cockpit2.py:3136` |
| `noochie_reset` | `cockpit2.py:3162` |
| `noochie_ctx` | `cockpit2.py:3169` |
| `cl_add` | `cockpit2.py:3176` |
| `cl_report` | `cockpit2.py:3194` |
| `cl_remove` | `cockpit2.py:3209` |
| `m_add_kpi` | `cockpit2.py:3219` |
| `m_add_from_def` | `cockpit2.py:3251` |
| `def_add` | `cockpit2.py:3266` |
| `catalog_publish` | `cockpit2.py:3288` |
| `def_amend` | `cockpit2.py:3314` |
| `m_add_link` | `cockpit2.py:3356` |
| `m_sample` | `cockpit2.py:3367` |
| `m_remove` | `cockpit2.py:3377` |
| `m_pin` | `cockpit2.py:3387` |
| `m_unpin` | `cockpit2.py:3398` |
| `tile_add` | `cockpit2.py:3436` |
| `indicator_activate` | `cockpit2.py:3408` |
| `tile_remove` | `cockpit2.py:3470` |
| `rov2_set` | `cockpit2.py:3480` |
| `rov2_acc_add` | `cockpit2.py:3480` |
| `rov2_acc_remove` | `cockpit2.py:3480` |
| `rov2_dom_add` | `cockpit2.py:3480` |
| `rov2_dom_remove` | `cockpit2.py:3480` |
| `backlog_add` | `cockpit2.py:3512` |
| `backlog_update_staat` | `cockpit2.py:3524` |
| `backlog_update_prioriteit` | `cockpit2.py:3536` |
| `person_edit` | `cockpit2.py:3548` |
| `person_remove` | `cockpit2.py:3565` |
| `lk_mute` | `cockpit2.py:3586` |
| `claims_term_add` | `cockpit2.py:3689` |
| `claims_term_retract` | `cockpit2.py:3726` |
| `claims_work_status` | `cockpit2.py:3710` |
| `claims_bewijs_link` | `cockpit2.py:3755` |
| `claims_vondst_whitelist` | `cockpit2.py:3779` |
| `claims_regel_uit_vondst` | `cockpit2.py:3805` |
| `claims_to_board` | `cockpit2.py:3837` |
| `persona_edit` | `cockpit2.py:2323` |
| `persona_llm` | `cockpit2.py:2342` |
| `persona_finetune` | `cockpit2.py:2359` |
| `persona_finetune_apply` | `cockpit2.py:2377` |


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
_54 routes · 182 dispatch-acties · 32 stores._
