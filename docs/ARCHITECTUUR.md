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
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie; het regelnummer is de def-regel. Gegroepeerde acties delen één handler.

| Actie | Handler (cockpit2.py:regel) |
|---|---|
| `ff_beslis` | `cockpit2.py:4339` |
| `ff_promote` | `cockpit2.py:4397` |
| `ff_demote` | `cockpit2.py:4421` |
| `ff_run` | `cockpit2.py:4440` |
| `kb_new` | `cockpit2.py:3833` |
| `kb_intake` | `cockpit2.py:3915` |
| `kb_intake_url` | `cockpit2.py:3932` |
| `kb_stage_edit` | `cockpit2.py:3951` |
| `kb_stage_accept` | `cockpit2.py:3963` |
| `kb_stage_delete` | `cockpit2.py:3982` |
| `kb_stage_merge` | `cockpit2.py:3988` |
| `kb_stage_commit` | `cockpit2.py:3999` |
| `kb_stage_discard` | `cockpit2.py:4019` |
| `kb_atoom_subject` | `cockpit2.py:4143` |
| `kb_atoom_purge` | `cockpit2.py:4127` |
| `tag_voorstel_besluit` | `cockpit2.py:4095` |
| `tag_onderhoud_run` | `cockpit2.py:4114` |
| `kb_blacklist_leeg` | `cockpit2.py:4136` |
| `kb_atoom_edit` | `cockpit2.py:4025` |
| `kb_atoom_related` | `cockpit2.py:4032` |
| `kb_atoom_reference` | `cockpit2.py:4077` |
| `kb_insight_link` | `cockpit2.py:4044` |
| `kb_insight_unlink` | `cockpit2.py:4051` |
| `kb_meta_start` | `cockpit2.py:4057` |
| `kb_atoom_merge` | `cockpit2.py:4154` |
| `kb_atoom_archive` | `cockpit2.py:4175` |
| `kb_atoom_unarchive` | `cockpit2.py:4184` |
| `kb_atoom_naar_spel` | `cockpit2.py:4190` |
| `kb_spel_start` | `cockpit2.py:4211` |
| `kb_spel_add` | `cockpit2.py:4225` |
| `kb_spel_remove` | `cockpit2.py:4235` |
| `kb_spel_flip` | `cockpit2.py:4242` |
| `kb_spel_finish` | `cockpit2.py:4248` |
| `kb_link` | `cockpit2.py:3842` |
| `kb_unlink` | `cockpit2.py:3856` |
| `kb_annotate` | `cockpit2.py:3867` |
| `kb_evidence` | `cockpit2.py:3873` |
| `kb_discuss` | `cockpit2.py:3894` |
| `kb_reformulate` | `cockpit2.py:3900` |
| `kw_nominate` | `cockpit2.py:4259` |
| `kw_nom_accept` | `cockpit2.py:4270` |
| `kw_nom_reject` | `cockpit2.py:4288` |
| `ws_forbid` | `cockpit2.py:4318` |
| `ws_approve` | `cockpit2.py:4323` |
| `proj_add` | `cockpit2.py:1133` |
| `artefact_add` | `cockpit2.py:1168` |
| `artefact_edit` | `cockpit2.py:1209` |
| `artefact_archive` | `cockpit2.py:1233` |
| `proj_status` | `cockpit2.py:1253` |
| `proj_done` | `cockpit2.py:1271` |
| `proj_dod` | `cockpit2.py:1320` |
| `proj_archive` | `cockpit2.py:1334` |
| `proj_unarchive` | `cockpit2.py:1357` |
| `proj_delete` | `cockpit2.py:1367` |
| `proj_edit` | `cockpit2.py:1394` |
| `proj_comment` | `cockpit2.py:1407` |
| `proj_rename` | `cockpit2.py:1417` |
| `proj_describe` | `cockpit2.py:1428` |
| `proj_doc_edit` | `cockpit2.py:1461` |
| `proj_regen_doc` | `cockpit2.py:1439` |
| `proj_settrekker` | `cockpit2.py:1474` |
| `proj_setowner` | `cockpit2.py:1511` |
| `proj_approve` | `cockpit2.py:1530` |
| `proj_discard` | `cockpit2.py:1541` |
| `proj_proposal_accept` | `cockpit2.py:1552` |
| `proj_proposal_reject` | `cockpit2.py:1565` |
| `proj_setlabel` | `cockpit2.py:1578` |
| `proj_setimpact` | `cockpit2.py:1593` |
| `proj_seteffort` | `cockpit2.py:1612` |
| `proj_agendeer_verzwakt` | `cockpit2.py:1635` |
| `proj_setprivate` | `cockpit2.py:1659` |
| `proj_setdue` | `cockpit2.py:1670` |
| `attach_add` | `cockpit2.py:1681` |
| `attach_remove` | `cockpit2.py:1692` |
| `react_add` | `cockpit2.py:1702` |
| `feed_edit` | `cockpit2.py:1712` |
| `feed_remove` | `cockpit2.py:1722` |
| `wall_outcome` | `cockpit2.py:2672` |
| `notif_read` | `cockpit2.py:2770` |
| `notif_processed` | `cockpit2.py:2775` |
| `notif_outcome` | `cockpit2.py:2922` |
| `notif_besluit` | `cockpit2.py:3009` |
| `notif_klaar` | `cockpit2.py:2908` |
| `notif_delete` | `cockpit2.py:2780` |
| `notif_add` | `cockpit2.py:2892` |
| `notif_archive` | `cockpit2.py:3051` |
| `metrics2_fav` | `cockpit2.py:2786` |
| `metrics2_unfav` | `cockpit2.py:2796` |
| `metrics2_form` | `cockpit2.py:2801` |
| `metrics2_dim` | `cockpit2.py:2807` |
| `metrics2_compare` | `cockpit2.py:2814` |
| `metrics2_formula` | `cockpit2.py:2877` |
| `source_activate` | `cockpit2.py:2860` |
| `source_deactivate` | `cockpit2.py:2869` |
| `link_pursue` | `cockpit2.py:2841` |
| `link_ignore` | `cockpit2.py:2851` |
| `acc_check` | `cockpit2.py:2822` |
| `ai_reply` | `cockpit2.py:1731` |
| `proj_feed` | `cockpit2.py:1742` |
| `checklist_add` | `cockpit2.py:1772` |
| `checklist_remove` | `cockpit2.py:1783` |
| `check_add` | `cockpit2.py:1831` |
| `check_accept` | `cockpit2.py:1848` |
| `check_toggle` | `cockpit2.py:1858` |
| `check_skip` | `cockpit2.py:1880` |
| `check_unskip` | `cockpit2.py:1892` |
| `check_handoff` | `cockpit2.py:1904` |
| `check_remove` | `cockpit2.py:1918` |
| `role_assign` | `cockpit2.py:1928` |
| `role_unassign` | `cockpit2.py:1946` |
| `role_focus` | `cockpit2.py:1965` |
| `radar_approve` | `cockpit2.py:1998` |
| `radar_dismiss` | `cockpit2.py:2008` |
| `radar_promote` | `cockpit2.py:2012` |
| `radar_merge` | `cockpit2.py:2032` |
| `radar_koppel` | `cockpit2.py:2048` |
| `kb_stage_koppel` | `cockpit2.py:2075` |
| `aitask_add` | `cockpit2.py:2113` |
| `aitask_remove` | `cockpit2.py:2144` |
| `skilllink_add` | `cockpit2.py:2172` |
| `means_gap_add` | `cockpit2.py:2202` |
| `persona_skill_add` | `cockpit2.py:2356` |
| `rov2_add` | `cockpit2.py:2371` |
| `rov2_add_to_group` | `cockpit2.py:2383` |
| `rov2_remove` | `cockpit2.py:2395` |
| `rov2_remove_group` | `cockpit2.py:2410` |
| `rov2_setkind` | `cockpit2.py:2428` |
| `rov2_consent` | `cockpit2.py:2441` |
| `rov2_end` | `cockpit2.py:2463` |
| `wo_open` | `cockpit2.py:2487` |
| `wo_close` | `cockpit2.py:2497` |
| `wo_presence` | `cockpit2.py:2513` |
| `wo_present_all` | `cockpit2.py:2524` |
| `wo_ag_add` | `cockpit2.py:2536` |
| `wo_ag_remove` | `cockpit2.py:2548` |
| `wo_ag_note` | `cockpit2.py:2558` |
| `wo_ag_reopen` | `cockpit2.py:2570` |
| `wo_ag_resolve` | `cockpit2.py:2646` |
| `wo_checkout` | `cockpit2.py:3056` |
| `noochie_send` | `cockpit2.py:3068` |
| `noochie_reset` | `cockpit2.py:3094` |
| `noochie_ctx` | `cockpit2.py:3101` |
| `cl_add` | `cockpit2.py:3108` |
| `cl_report` | `cockpit2.py:3126` |
| `cl_remove` | `cockpit2.py:3141` |
| `m_add_kpi` | `cockpit2.py:3151` |
| `m_add_from_def` | `cockpit2.py:3183` |
| `def_add` | `cockpit2.py:3198` |
| `catalog_publish` | `cockpit2.py:3220` |
| `def_amend` | `cockpit2.py:3246` |
| `m_add_link` | `cockpit2.py:3288` |
| `m_sample` | `cockpit2.py:3299` |
| `m_remove` | `cockpit2.py:3309` |
| `m_pin` | `cockpit2.py:3319` |
| `m_unpin` | `cockpit2.py:3330` |
| `tile_add` | `cockpit2.py:3368` |
| `indicator_activate` | `cockpit2.py:3340` |
| `tile_remove` | `cockpit2.py:3402` |
| `rov2_set` | `cockpit2.py:3412` |
| `rov2_acc_add` | `cockpit2.py:3412` |
| `rov2_acc_remove` | `cockpit2.py:3412` |
| `rov2_dom_add` | `cockpit2.py:3412` |
| `rov2_dom_remove` | `cockpit2.py:3412` |
| `backlog_add` | `cockpit2.py:3444` |
| `backlog_update_staat` | `cockpit2.py:3456` |
| `backlog_update_prioriteit` | `cockpit2.py:3468` |
| `person_edit` | `cockpit2.py:3480` |
| `person_remove` | `cockpit2.py:3497` |
| `lk_mute` | `cockpit2.py:3518` |
| `claims_term_add` | `cockpit2.py:3621` |
| `claims_term_retract` | `cockpit2.py:3658` |
| `claims_work_status` | `cockpit2.py:3642` |
| `claims_bewijs_link` | `cockpit2.py:3687` |
| `claims_vondst_whitelist` | `cockpit2.py:3711` |
| `claims_regel_uit_vondst` | `cockpit2.py:3737` |
| `claims_to_board` | `cockpit2.py:3769` |
| `persona_edit` | `cockpit2.py:2255` |
| `persona_llm` | `cockpit2.py:2274` |
| `persona_finetune` | `cockpit2.py:2291` |
| `persona_finetune_apply` | `cockpit2.py:2309` |


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
_53 routes · 180 dispatch-acties · 30 stores._
