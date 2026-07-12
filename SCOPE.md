# SCOPE — De Kroniek (fase 1: onthouden)

Levend afsprakenbestand voor branch `feature/de-kroniek`. Bij divergentie chat vs. dit bestand wint
dit bestand. Wordt bij merge verwijderd (afspraken leven dan in code, tests, commit-message).

## Visie (mens-goedgekeurd 12-07-2026)
Van "meer van hetzelfde" → **ONTHOUDEN · LEREN · INTERPRETEREN · ONTDEKKEN**. De Kroniek is één
ruggengraat; elke trede ontsluit de volgende. Geheugen is de hefboom: fase 1 bouwt uitsluitend het
geheugen; leren/interpreteren/ontdekken zijn fase 2–4 (aparte, mens-getekende scopes).

Herkomst: raadsadvies (9 bemenste rollen), verankerd in de productie-data van 11–12 juli 2026 (44
identieke skill-mislukkingen, field note met kop "22 mei 2024" los van de observatie-store, einddocs
met `[Datum invullen]`). Deelbare pagina + governance-voorstel besproken; the_source akkoord.

## Beslissingen
- **B1** — Fase 1 = ALLEEN onthouden + de scherpste grondings-poort (field note). Niet breed uitrollen.
- **B2** — Alternatief-pad (Stefan): skill-ladder als generalisatie van `LLM_LADDER`; escaleren naar de
  mens is de LÁÁTSTE tree, nooit de eerste.
- **B3** — `leeg` en `fout` zijn eersteklas resultaten in het register, geen stilte.
- **B4** — Eigenaarschap: **Librarian = hoeder/domein-eigenaar** (bibliotheek-domein van *woorden* naar
  *bewijs*: curatie/dedup/snoeien). **harry_hemp = vuller + waarheidslat.** Alle rollen voeden; lezen vrij.
- **B5** — codie_code **borgt fase 1 op zijn projectenbord** (ProjectStore.create, owner=codie_code).
- **B6** — Nieuwe capaciteit blijft mens-gated: de grondings-poort raakt een bestaande skill → pattern
  eerst tonen, pas na akkoord bouwen (werkafspraak).

## Bouwscope fase 1 (in bestaande patronen)
1. **`EvidenceLedger`** (`nooch_village/evidence_ledger.py`) — append-only `data/evidence_ledger.jsonl`
   + `util.file_lock` (zoals ObservationStore/DeliverableStore). record: `{id, role_id, skill, query,
   source, status(bevestigd|leeg|fout), result_ref, ts}`. ✅ increment 1.
2. **`run_with_ladder()` + `classify_result()`** (in `evidence_ledger.py`) — loopt fallback-trappen af,
   logt elke uitkomst naar de Kroniek, escaleert (injecteerbare callback) na uitputting ALLEEN bij een
   fout; alle-leeg = legitiem no_data, geen escalatie. ✅ increment 2.
   - Alternatief pad = **`google_patents`** (keyless skill, `skills_impl/google_patents.py`),
     geregistreerd in de factory. VOORBEREID; governance-toewijzing aan harry_hemp = activatie (Stefan).
3. **Grondings-poort op de field note** (`grounding.py` + `field_note`-skill) — datum-drift + ongegrond
   bezoekersgetal (getal dat nergens in de plausible-data voorkomt; per-pagina-aantallen blijven gegrond).
   Ongegrond → ONGEGROND-banner i.p.v. schoon publiceren + `fout` in de Kroniek (fail-safe). ✅ increment 2.
4. **`st.evidence`** in `_Stores` gedraad (cockpit) + `arch_map` bijgewerkt (nieuwe store). ✅ increment 2.

## Conventies (branch)
fcntl-flock (`util.file_lock`) op de store; backup vóór elke serverwrite; geen inline styles;
diff-before-save; `# AUTHZ`-label op elke aangeraakte/nieuwe dispatch-tak; `python -m
nooch_village.arch_map` bijwerken bij nieuwe route/dispatch-actie/store; smoke + **volledige** suite
groen vóór merge.

## Tests fase 1
- EvidenceLedger: record + statusvalidatie; `leeg`/`fout` eersteklas; append-integriteit + cache;
  `last_good` (geheugen-eerst); `consecutive_failures` (ladder-signaal); corrupte regel fail-loud
  overgeslagen. ✅ increment 1.
- run_with_ladder: route A faalt → B geprobeerd + gelogd; alles faalt → precies één human_inbox-escalatie.
- Grondings-poort: field-note-cijfer zonder match → gemarkeerd; met match → publiceert.

## Roadmap (buiten fase 1)
Fase 2 leren (hitrate-gestuurde ladder) · Fase 3 interpreteren (synthese-laag over de Kroniek) ·
Fase 4 ontdekken (discovery-lus). Elke fase eigen scope + mens-akkoord.

## Open vragen
- Concrete alternatieve patentbron voor de `epo_patents`-ladder: Google Patents-scrape vs Lens.org-API?
- Grondings-poort eerst alleen field note, of meteen ook het noochie-bulletin?
- codie_code-projectkaart: op de LIVE server-board plaatsen (flock-veilig via ProjectStore op prod) —
  bevestigen vóór de serverwrite.
