# CC-opdracht: Claims Checker v3 — wetscheck bij compliance, @rol-berichten, zelfverifiërende status

**Voor:** Claude Code in de Noochville-repo. Vervolg op v1/v2 (geland). Zelfde guardrails, eigen branch (`claims-checker-v3`), schone working tree bij start.

**Doel in één zin:** de compliance-rol checkt maandelijks zelf of de wet is veranderd (zichtbaar in haar checklist), bevindingen bereiken rollen als @rol-bericht in hun eigen werkstroom, de werklijst-status verifieert zichzelf tegen de site, en álle terugkerende gedrag leeft in het product zelf — nul afhankelijkheid van externe scheduling, want dit moet ook werken als de checker ooit standalone verkocht wordt.

## Productprincipe (nieuw, hard)

De claims-checker kan op termijn als zelfstandig product verkocht worden. Daarom: geen enkele terugkerende taak, reminder of check mag buiten de repo leven (geen externe Claude scheduled tasks, geen cron op de host buiten systemd van de app zelf). Alles loopt via de bestaande pulslaag (`pulse_skills`) en is per rol via governance gegrant. Wat het dorp niet zelf kan, bestaat niet.

## Taak 1 — Skill `regulation_watch`: de wet verandert, compliance merkt het

Typisch zo'n klus die een mens vergeet en een machine niet — maar volgens het zwart-wit-principe: de tool DETECTEERT, de mens BEOORDEELT, niets muteert zichzelf de database in.

- `skills_impl/regulation_watch.py`, patroon identiek aan `claims_site_scan`: pure helpers + injecteerbare `_fetch`, fail-closed, registry, grant aan compliance (record → v6) en in haar `pulse_skills`. **Ritme: maandelijks**, idempotent per kalendermaand.
- **Bronnenlijst in `config/settings.ini`** (url + label + bron-letter), defaults:
  - EUR-Lex Richtlijn 2024/825 (A): `https://eur-lex.europa.eu/eli/dir/2024/825/oj/eng`
  - ACM Leidraad-pagina (B): `https://www.acm.nl/nl/publicaties/leidraad-duurzaamheidsclaims-0`
  - FOD-gids milieuclaims BE: de officiële PDF-url
  - NL-omzetting EmpCo: officiële bron zodra bekend; tot die tijd de CMS-trackerpagina, expliciet gelabeld "proxy"
- **Mechaniek:** tekst normaliseren (HTML strippen, whitespace collapsen; PDF's op bytes/headers), hash + laatst-gezien in append-only `data/regulation_watch.jsonl`. Hash gewijzigd → bevinding. Bron 2 maanden achtereen onbereikbaar → fail-closed escalatie (één misser is geen alarm).
- **Uitkomst:** per gewijzigde bron een taak voor compliance ("Bron gewijzigd: [label] — beoordeel impact op de claims-database") + @compliance-bericht (Taak 2-mechanisme) + heads-up founder bij een A-bron. Dedupe zolang de vorige taak open staat. GEEN duiding, GEEN mutatie van `config/claims_database.json` — test die dat bewaakt.
- **Mijlpalen in de skill (idempotent, éénmalig):** eerste maandpuls van september 2026 → taak+heads-up "EmpCo-handhaving start 27-09: volledige scan, rode werklijst-items, PETA-beslissing"; en zodra de NL-omzettingsbron voor het eerst echte inhoud toont → taak "NL-wettekst naast de database leggen".

## Taak 2 — Zichtbaar in de checklist van compliance

Stefan wil op de rol-pagina van compliance ZIEN dat dit gebeurt, niet erop moeten vertrouwen.

- Toon op de compliance-rolpagina (bij het bestaande gereedschap-blok) haar terugkerende ritme: "Wekelijkse site-scan — laatste run [datum], [n nieuw/stil]" en "Maandelijkse wetscheck — laatste run [datum], [bronnen ongewijzigd / X gewijzigd]". Data uit de bestaande logs/state (`trend`-patroon: lees de eigen jsonl's), geen nieuwe opslag.
- Puls al 1+ periode overtijd (bijv. dorp lag stil) → toon dat als waarschuwing op de rolpagina in plaats van een verouderde "laatste run" die vertrouwen wekt.
- **Acceptatie:** na een puls toont de rolpagina de verse run; draai je de klok een maand vooruit zonder puls, dan verschijnt de overtijd-waarschuwing.

## Taak 3 — "Zet op het bord" wordt @rol-bericht

Feedback founder: na "Zet op het bord" gebeurt er zichtbaar niets en het is onduidelijk op wiens bord het landt.

- Bij het omzetten van bevindingen: naast de taak óók een bericht aan de rol via het bestaande berichten/inbox-oppervlak van het dorp (hetzelfde mechanisme als de @founding farmer-heads-ups, maar dan gericht aan de rol: @copywriter, @brand_visual_designer, @marketing_lead, @compliance). Bericht bevat: bevinding, stoplicht+bron-badge, herformulering, link naar de taak. De ontvangende rol pakt het op in haar eigen werkstroom; de taak is de administratie, het bericht is de trigger.
- Direct na de klik toont de UI het resultaat: "3 taken aangemaakt → @copywriter (2), @compliance (1)" met links — nooit meer een stille klik. Ook bij 0 nieuwe (alles dedupe): toon "0 nieuw — alle bevindingen staan al als taak/werklijst-item", met links naar de bestaande.
- Escaleren-bevindingen (bron C) gaan ALTIJD naar @compliance, nooit naar een andere rol (bestaand principe uit Taak 6 v2).
- **Acceptatie:** klik met bekende bevindingen → zichtbare "0 nieuw"-terugkoppeling; klik met een nieuwe rode term → taak + @rol-bericht bij de juiste rol, en de UI toont beide met links.

## Taak 4 — Werklijst-status verifieert zichzelf

Vraag founder: "hoe weet de tool de status?" Antwoord nu: niet — een mens zet hem. Dat wordt tweetraps:

- **Automatisch (deterministisch, dus toegestaan):** de wekelijkse `claims_site_scan` toetst elk werklijst-item tegen de gescande pagina's: claim-tekst niet meer aanwezig → status automatisch naar "opgelost (auto-geverifieerd [datum])" met logregel; claim wéér aanwezig terwijl status "opgelost/live" is → status terug naar "open (regressie)" + @rol-bericht naar de rol die hem gefixt had + @compliance. Dit is byte-vergelijking, geen interpretatie — past binnen het zwart-wit-principe.
- **Handmatig blijft:** compliance kan via de beheer-tab altijd overschrijven (bijv. "opgelost" voor een claim op een pagina buiten de scan-set); handmatige overrides winnen tot de volgende scan iets anders waarneemt, en elke automatische wijziging is als zodanig gelabeld zodat mens- en machine-oordeel nooit verward raken.
- Items op pagina's buiten de vaste scan-set kunnen niet auto-geverifieerd worden: toon dat expliciet als "niet auto-verifieerbaar" in plaats van een status die betrouwbaarheid suggereert.
- **Acceptatie:** dry-run met geïnjecteerde `_fetch` waarin claim #13 ("PLANET-FRIENDLY.") van de productpagina verdwenen is → status wordt "opgelost (auto-geverifieerd)"; run waarin hij terugkeert → "open (regressie)" + berichten; item buiten de scan-set → "niet auto-verifieerbaar".

## Guardrails

- Volle suite groen; arch_map + ARCHITECTUUR.md mee; deploy conform protocol incl. chown-check `config/claims_database.json`.
- Alleen GET's naar geconfigureerde bronnen; SSRF-guardrail hergebruiken; nette User-Agent/timeouts.
- Geen LLM-duiding in `regulation_watch`; geen mutaties van de claims-database door welke skill dan ook (tests bewaken beide).
- Append-only state; gerichte governance-edits met backup; apply als user `nooch`.
- Productprincipe bewaken: geen enkele nieuwe afhankelijkheid buiten de repo voor terugkerend gedrag.
