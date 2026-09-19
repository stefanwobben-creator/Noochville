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
| `/rapport` | `render_projectrapport` | `nooch_village/views/rapport.py` |
| `/pagina` | `render_pagina` | `nooch_village/views/wiki.py` |
| `/project/nieuw` | `render_wizard` | `nooch_village/views/wizard.py` |
| `/project` | `render_project` | `nooch_village/views/projects.py` |
| `/rolefillers` | `render_rolefillers` | `nooch_village/views/overview.py` |
| `/middelen` | `render_middelen` | `nooch_village/views/overview.py` |
| `/person` | `render_person` | `nooch_village/views/overview.py` |
| `/admin` | `render_admin` | `nooch_village/views/overview.py` |
| `/founder` | `render_founder_flow` | `nooch_village/views/founder_flow.py` |
| `/_patterns` | `render_patterns` | `nooch_village/views/overview.py` |
| `/inbox` | `render_inbox_frag` | `nooch_village/views/inbox.py` |
| `/search` | `render_search_fragment` | `nooch_village/views/search.py` |
| `/skills` | `render_skills` | `nooch_village/views/skills.py` |
| `/goals` | `render_goals` | `nooch_village/views/doelen.py` |
| `/goal` | `render_goal` | `nooch_village/views/doelen.py` |
| `/site-audit` | `render_site_audit` | `nooch_village/views/site_audit.py` |
| `/bronnen` | `render_bronnen` | `nooch_village/views/bronnen.py` |
| `/codie` | `render_codie` | `nooch_village/views/codie.py` |
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
| `/decision-coach` | `render_decision_coach` | `nooch_village/views/decision_coach.py` |
| `/copy-prompt` | `render_copy_prompt` | `nooch_village/views/copy_prompt.py` |
| `/inwoners` | `render_inwoners` | `nooch_village/views/inwoners.py` |
| `/inwoner` | `render_inwoner` | `nooch_village/views/inwoners.py` |
| `/roloverleg2` | `render_roloverleg2` | `nooch_village/views/roloverleg.py` |
| `/metric_export` | `(inline)` | `cockpit2.py` |
| `/file` | `(inline)` | `cockpit2.py` |
| `/project_pakket` | `(inline)` | `cockpit2.py` |


## (b) Dispatch-actie → handler

De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn `_act_*`-handlerfunctie in `cockpit2.py`; gegroepeerde acties delen één handler. Bewust géén regelnummer: dat verandert bij elke regel die erboven wordt toegevoegd, zonder dat de architectuur verandert.

| Actie | Handler (cockpit2.py) |
|---|---|
| `decision_sheet_log` | `_act_decision_sheet_log` |
| `ff_beslis` | `_act_ff_beslis` |
| `ff_cluster` | `_act_ff_cluster` |
| `ff_promote` | `_act_ff_promote` |
| `ff_demote` | `_act_ff_demote` |
| `ff_run` | `_act_ff_run` |
| `kb_new` | `_act_kb_new` |
| `tag_onderhoud_run` | `_act_tag_onderhoud_run` |
| `copy_stack_inclusie` | `_act_copy_stack_inclusie` |
| `verzoek_besluit` | `_act_verzoek_besluit` |
| `kb_insight_link` | `_act_kb_insight_link` |
| `kb_insight_unlink` | `_act_kb_insight_unlink` |
| `kb_link` | `_act_kb_link` |
| `kb_unlink` | `_act_kb_unlink` |
| `kb_annotate` | `_act_kb_annotate` |
| `kb_discuss` | `_act_kb_discuss` |
| `kb_reformulate` | `_act_kb_reformulate` |
| `kw_nominate` | `_act_kw_nominate` |
| `kw_nom_accept` | `_act_kw_nom_accept` |
| `kw_nom_reject` | `_act_kw_nom_reject` |
| `ws_forbid` | `_act_ws_forbid` |
| `ws_approve` | `_act_ws_approve` |
| `proj_add` | `_act_proj_add` |
| `artefact_add` | `_act_artefact_add` |
| `artefact_edit` | `_act_artefact_edit` |
| `artefact_archive` | `_act_artefact_archive` |
| `pagina_feit_add` | `_act_pagina_feit_add` |
| `pagina_feit_del` | `_act_pagina_feit_del` |
| `pagina_voorstel` | `_act_pagina_voorstel` |
| `proj_status` | `_act_proj_status` |
| `proj_done` | `_act_proj_done` |
| `proj_dod` | `_act_proj_dod` |
| `proj_archive` | `_act_proj_archive` |
| `proj_unarchive` | `_act_proj_unarchive` |
| `proj_delete` | `_act_proj_delete` |
| `proj_edit` | `_act_proj_edit` |
| `proj_comment` | `_act_proj_comment` |
| `proj_rename` | `_act_proj_rename` |
| `proj_describe` | `_act_proj_describe` |
| `proj_doc_edit` | `_act_proj_doc_edit` |
| `verslag_bevestig_behaald` | `_act_verslag_bevestig_behaald` |
| `verslag_bevestig_niet_behaald` | `_act_verslag_bevestig_niet_behaald` |
| `verslag_overslaan` | `_act_verslag_overslaan` |
| `verslag_bijwerken` | `_act_verslag_bijwerken` |
| `proj_regen_doc` | `_act_proj_regen_doc` |
| `proj_settrekker` | `_act_proj_settrekker` |
| `proj_setowner` | `_act_proj_setowner` |
| `proj_approve` | `_act_proj_approve` |
| `proj_discard` | `_act_proj_discard` |
| `proj_proposal_accept` | `_act_proj_proposal_accept` |
| `proj_proposal_reject` | `_act_proj_proposal_reject` |
| `proj_setlabel` | `_act_proj_setlabel` |
| `proj_setimpact` | `_act_proj_setimpact` |
| `proj_seteffort` | `_act_proj_seteffort` |
| `proj_agendeer_verzwakt` | `_act_proj_agendeer_verzwakt` |
| `proj_setprivate` | `_act_proj_setprivate` |
| `proj_setdue` | `_act_proj_setdue` |
| `proj_goal` | `_act_proj_goal` |
| `proj_depends` | `_act_proj_depends` |
| `goal_add` | `_act_goal_add` |
| `goal_edit` | `_act_goal_edit` |
| `goal_link` | `_act_goal_link` |
| `attach_add` | `_act_attach_add` |
| `attach_remove` | `_act_attach_remove` |
| `react_add` | `_act_react_add` |
| `feed_edit` | `_act_feed_edit` |
| `feed_remove` | `_act_feed_remove` |
| `wall_outcome` | `_act_wall_outcome` |
| `notif_read` | `_act_notif_read` |
| `notif_processed` | `_act_notif_processed` |
| `notif_outcome` | `_act_notif_outcome` |
| `notif_klaar` | `_act_notif_klaar` |
| `goedkeur` | `_act_goedkeur` |
| `notif_delete` | `_act_notif_delete` |
| `notif_add` | `_act_notif_add` |
| `notif_archive` | `_act_notif_archive` |
| `metrics2_fav` | `_act_metrics2_fav` |
| `metrics2_unfav` | `_act_metrics2_unfav` |
| `metrics2_form` | `_act_metrics2_form` |
| `metrics2_dim` | `_act_metrics2_dim` |
| `metrics2_compare` | `_act_metrics2_compare` |
| `metrics2_formula` | `_act_metrics2_formula` |
| `source_activate` | `_act_source_activate` |
| `source_deactivate` | `_act_source_deactivate` |
| `link_pursue` | `_act_link_pursue` |
| `link_ignore` | `_act_link_ignore` |
| `acc_check` | `_act_acc_check` |
| `ai_reply` | `_act_ai_reply` |
| `proj_feed` | `_act_proj_feed` |
| `checklist_add` | `_act_checklist_add` |
| `checklist_remove` | `_act_checklist_remove` |
| `plan_akkoord` | `_act_plan_akkoord` |
| `checklist_uitvoer` | `_act_checklist_uitvoer` |
| `check_add` | `_act_check_add` |
| `check_accept` | `_act_check_accept` |
| `check_toggle` | `_act_check_toggle` |
| `check_skip` | `_act_check_skip` |
| `check_unskip` | `_act_check_unskip` |
| `check_handoff` | `_act_check_handoff` |
| `check_remove` | `_act_check_remove` |
| `check_rename` | `_act_check_rename` |
| `check_move` | `_act_check_move` |
| `role_assign` | `_act_role_assign` |
| `role_unassign` | `_act_role_unassign` |
| `role_focus` | `_act_role_focus` |
| `radar_dismiss` | `_act_radar_dismiss` |
| `radar_merge` | `_act_radar_merge` |
| `middel_remove` | `_act_middel_remove` |
| `skilllink_add` | `_act_skilllink_add` |
| `means_gap_add` | `_act_means_gap_add` |
| `rov2_add` | `_act_rov2_add` |
| `rov2_add_to_group` | `_act_rov2_add_to_group` |
| `rov2_remove` | `_act_rov2_remove` |
| `rov2_remove_group` | `_act_rov2_remove_group` |
| `rov2_setkind` | `_act_rov2_setkind` |
| `rov2_consent` | `_act_rov2_consent` |
| `rov2_end` | `_act_rov2_end` |
| `wo_open` | `_act_wo_open` |
| `wo_close` | `_act_wo_close` |
| `wo_presence` | `_act_wo_presence` |
| `wo_present_all` | `_act_wo_present_all` |
| `vangst_add` | `_act_vangst_add` |
| `vangst_tekst` | `_act_vangst_tekst` |
| `vangst_klaar` | `_act_vangst_klaar` |
| `vangst_uitkomst` | `_act_vangst_uitkomst` |
| `vangst_uitkomst_weg` | `_act_vangst_uitkomst_weg` |
| `vangst_uitkomst_edit` | `_act_vangst_uitkomst_edit` |
| `vangst_remove` | `_act_vangst_remove` |
| `vangst_verwerk` | `_act_vangst_verwerk` |
| `wo_checkout` | `_act_wo_checkout` |
| `noochie_send` | `_act_noochie_send` |
| `noochie_reset` | `_act_noochie_reset` |
| `noochie_ctx` | `_act_noochie_ctx` |
| `cl_add` | `_act_cl_add` |
| `cl_report` | `_act_cl_report` |
| `cl_remove` | `_act_cl_remove` |
| `m_add_kpi` | `_act_m_add_kpi` |
| `m_add_from_def` | `_act_m_add_from_def` |
| `def_add` | `_act_def_add` |
| `catalog_publish` | `_act_catalog_publish` |
| `def_amend` | `_act_def_amend` |
| `m_add_link` | `_act_m_add_link` |
| `m_sample` | `_act_m_sample` |
| `m_remove` | `_act_m_remove` |
| `m_pin` | `_act_m_pin` |
| `m_unpin` | `_act_m_unpin` |
| `tile_add` | `_act_tile_add` |
| `indicator_activate` | `_act_indicator_activate` |
| `tile_remove` | `_act_tile_remove` |
| `rov2_set` | `_act_rov2_set` |
| `rov2_acc_add` | `_act_rov2_set` |
| `rov2_acc_remove` | `_act_rov2_set` |
| `rov2_dom_add` | `_act_rov2_set` |
| `rov2_dom_remove` | `_act_rov2_set` |
| `person_edit` | `_act_person_edit` |
| `person_remove` | `_act_person_remove` |
| `lk_mute` | `_act_lk_mute` |
| `claims_term_add` | `_act_claims_term_add` |
| `claims_term_retract` | `_act_claims_term_retract` |
| `claims_work_status` | `_act_claims_work_status` |
| `claims_bewijs_link` | `_act_claims_bewijs_link` |
| `claims_vondst_whitelist` | `_act_claims_vondst_whitelist` |
| `claims_regel_uit_vondst` | `_act_claims_regel_uit_vondst` |
| `claims_to_board` | `_act_claims_to_board` |
| `persona_edit` | `_act_persona_edit` |
| `persona_llm` | `_act_persona_llm` |
| `persona_finetune` | `_act_persona_finetune` |
| `persona_finetune_apply` | `_act_persona_finetune_apply` |


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
| `notif` | `NotifStore` | `notifications.json` |
| `agenda` | `Agenda` | `roloverleg_agenda.json` |
| `noochie` | `NoochieStore` | `noochie.json` |
| `checklists` | `ChecklistStore` | `checklists.json` |
| `metrics` | `MetricStore` | `metrics.json` |
| `defs` | `DefinitionStore` | `definitions.json` |
| `werk` | `WerkoverlegStore` | `werkoverleg.json` |
| `strategies` | `StrategyStore` | `strategies.json` |
| `doelen` | `DoelStore` | `doelen.json` |
| `copy_stack` | `CopyStackConfig` | `copy_stack.json` |
| `radar` | `RadarStore` | `radar.json` |
| `radar_besluiten` | `ClusterBesluitStore` | `radar_clusters.json` |
| `kennisbank` | `KennisbankStore` | `kennisbank.json` |
| `library` | `Library` | `library.json` |
| `nominations` | `NominationQueue` | `keyword_nominaties.json` |
| `nom_kroniek` | `NominationKroniek` | `keyword_nominaties.jsonl` |
| `link_kroniek` | `SkillLinkKroniek` | `skill_links_kroniek.jsonl` |


## (d) Databestand → schrijvende module (buiten `_Stores`)

Sectie (c) dekt alleen de stores die als handle op `_Stores` hangen — ongeveer de helft van de schrijvende opslag. De rest woont in losse modules. **Deze lijst is afgeleid uit SCHRIJFGEDRAG**: een module telt als schrijver als hij de bestandsnaam noemt én ergens `open(..., "a"/"w")`, de veilige json-schrijver, een `JsonStore`-subklasse of `_WRITE_METHODS` bevat. Een module die de naam alleen noemt is een lezer en staat hier niet.

| Databestand | Schrijvende module |
|---|---|
| `accountability_check.json` | `cockpit2.py` |
| `afslanken.jsonl` | `afslanken.py` |
| `artefact_changelog.jsonl` | `artefacts.py` |
| `autonomie_signaal.jsonl` | `zelf_verwerking.py` |
| `belofte_grafen.json` | `cockpit2.py` |
| `board_pulse.jsonl` | `board_loop.py` |
| `checklist_suggesties.jsonl` | `checklist_vorm.py` |
| `claims_database.json` | `claims_db.py` |
| `claims_labels.jsonl` | `claims_labels.py` |
| `claims_runtime.json` | `claims_db.py` |
| `critic_labels.jsonl` | `missie_critic.py` |
| `csrf.json` | `cockpit2.py` |
| `deadsource_state.json` | `village.py` |
| `decision_sheets.jsonl` | `decision_sheets.py` |
| `draaistaat.jsonl` | `draaistaat.py` |
| `feedback.json` | `inhabitant.py` |
| `feeds.json` | `radar_store.py` |
| `founder_flow.json` | `founder_flow.py` |
| `founder_labels.jsonl` | `founder_flow.py` |
| `founder_park.jsonl` | `founder_park.py` |
| `gaps.jsonl` | `gap_ledger.py` |
| `governance_examples.json` | `cli.py` |
| `kennis_embeddings.json` | `kennis_embeddings.py` |
| `materiaal_memo.json` | `materiaal_memo.py` |
| `meta.json` | `epic.py` |
| `noochie_daily.json` | `roles.py` |
| `notes.json` | `kennisbank.py` |
| `persona_kroniek.jsonl` | `cockpit2.py` |
| `pinboard.json` | `village.py` |
| `project_proposals.json` | `project_proposals.py` |
| `pulse_heartbeat.json` | `inhabitant.py` |
| `radar_beoordelingen.jsonl` | `radar_beoordeling.py` |
| `radar_embeddings.json` | `radar_clusters.py` |
| `radar_nieuwheid.json` | `radar_nieuwheid.py` |
| `relaunch_park.jsonl` | `relaunch_park.py` |
| `role_metrics.json` | `village.py` |
| `role_status.json` | `village.py` |
| `sessions.json` | `cockpit2.py` |
| `shopify_metrics.json` | `cli.py` |
| `site_audit.jsonl` | `site_audit.py` |
| `site_audit_dev.jsonl` | `site_audit.py` |
| `snake_scores.json` | `snake.py` |
| `strategy.json` | `pinboard.py` |
| `triage_uitkomsten.jsonl` | `triage_rol.py` |
| `verwerkingen.jsonl` | `zelf_verwerking.py` |
| `villageraad.jsonl` | `villageraad.py` |
| `voorstellen.jsonl` | `onderzoekspas.py` |


### (d2) Meerdere schrijvers — eigenaarschap niet af te leiden

Meer dan één module schrijft dit bestand. Dat is geen fout, maar de kaart kan niet zeggen wie de eigenaar is; dat blijft mensenwerk.

| Databestand | Schrijvende modules |
|---|---|
| `buzz_observations.jsonl` | `cli.py, village.py` |
| `buzz_query_sets.json` | `cli.py, village.py` |
| `competitor_brands.json` | `cli.py, village.py` |
| `constraints.json` | `cli.py, inhabitant.py` |
| `groeidagboek.jsonl` | `role_proposals.py, village.py` |
| `human_inbox.json` | `cli.py, cockpit2.py, dagcyclus.py, inhabitant.py, village.py` |
| `lexicon.json` | `cli.py, village.py` |
| `linkbuilding_targets.json` | `cli.py, cockpit2.py` |
| `llm_usage.jsonl` | `llm_usage.py, village.py` |
| `system_log.jsonl` | `cockpit2.py, verslag.py, village.py` |
| `timekeeper_last_day.json` | `dagcyclus.py, puls_wacht.py` |


### (d3) Geen schrijver gevonden

Genoemd in het pakket, maar niemand schrijft hem aantoonbaar: lees-only configuratie, of geschreven buiten het pakket (bijvoorbeeld in een exportpakket). Staat hier zodat het gat zichtbaar is in plaats van weggelaten.

| Databestand |
|---|
| `co2_factoren.json` |
| `llm_prijzen.json` |
| `manifest.json` |
| `persona.json` |
| `project.json` |
| `rugzakken.json` |
| `seed_surges.json` |
| `trend_signals.jsonl` |


---
_55 routes · 168 dispatch-acties · 28 stores in `_Stores` · 47 daarbuiten met één schrijver · 11 met meerdere · 8 zonder gevonden schrijver._
