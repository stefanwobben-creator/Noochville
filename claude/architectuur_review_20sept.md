# Architectuurreview, vervolg op de diepe audit (20 sept, nacht)

Alleen-lezend uitgevoerd op de live repo terwijl Claude Code lokaal aan fase 10 (huisstijl) werkte.
Geen code aangeraakt. Aanleiding: "denk dat er nog 25% af moet kunnen" naast de al afgeronde
fase 1-9 opruiming (98.185 → 71.978 broncoderegels, 80.040 → 58.150 testregels).

## Belangrijkste bevinding: het grootste deel van de eerdere audit is al uitgevoerd

`claude/audit_diep_cockpit_views_skills_19sept.md` (dezelfde dag geschreven) rekende op een
verdedigbare 37.000 regels weg te halen bovenop de 98.185 van toen. Ik heb de kernclaims van die
audit live tegen de huidige repo gehouden in plaats van het cijfer over te nemen, en het grootste
deel blijkt al gebeurd, vermoedelijk in een sessie die niet in dit gesprek zichtbaar is geweest:

| onderdeel | audit (19 sept) | nu gemeten (20 sept) | verschil |
|---|---|---|---|
| `inhabitant.py` | 3.282 regels | 866 regels | -2.416 |
| radar/buzz/competitor/inoreader-familie | ~4.249 regels | 552 regels | -3.697 |
| `cli.py` | 2.040 regels, 91 modes | 1.385 regels, 58 modes | -655, -33 modes |
| founder_flow.py, founder_taken.py, views/founder_flow.py, founder_park.py | aanwezig | weg | volledig |
| views/signals.py, radar_beoordeling/promote/nieuwheid, news_distill, project_signal, views/linkbuilding | aanwezig | weg | volledig |
| missie_critic.py, project_worker.py | aanwezig | weg | volledig |
| `views/` totaal | 17.197 regels | 13.905 regels | -3.292 |
| cockpit2.py dode handlers/imports naar bovenstaande | aanwezig (genoemd) | geen enkele referentie meer gevonden | schoon |

Dat is de reden dat een nieuwe grondige audit vanaf nul weinig zou toevoegen: de grote klap is al
uitgedeeld. Wat overblijft is kleiner dan het "nog 25%" gevoel doet vermoeden.

## Wat nog wel concreet openstaat, geverifieerd

**1. Keyword/kennisbank-laag: ~2.991 regels (1.920 bron + 1.071 tests), nog volledig aanwezig en
nog 34x aangeroepen vanuit `cockpit2.py`'s dispatch.** Dit is exact de "3B, Keywords/library" uit de
audit, met hetzelfde oordeel: weg, behalve `library.json` (de goedgekeurde/verboden-woordenlijst die
de claims-checker al gebruikt, dat is 1 bestand, geen 1.900 regels). Niemand heeft een lens meer
die hij leest (bevestigd 17 sept in de audit, en er is sindsdien niets bijgekomen dat dat
tegenspreekt). Grootste, laaghangende, nog niet geplukte fruit.

**2. Vijf kleine stragglers uit de audit, individueel "weg", nog niet verwijderd (877 regels
samen):** `founder_kaart.py` (151), `gap_ledger.py` (134), `gap_classifier.py` (201, restanten van de
Codie-backlog), `project_verslag.py` (200), `views/strategy.py` + `strategy_store.py` (153 + 38).
Klein, maar goedkoop: geen van alle heeft nog een aanroeppad na de rest van de opruiming.

**3. `views/metrics.py`, 2.149 regels, ongewijzigd.** De audit noemde dit al "tweeduizend regels
voor twee tegels" (live: `/metrics2` toont 2 KPI's voor de Nooch-cirkel). Ik heb dit nu niet
regel-voor-regel uitgeplozen zoals de rest, dat verdient een eigen doorlichting voor je er iets van
verwijdert, want in tegenstelling tot de radar/founder-familie heeft dit scherm wel een dagelijkse
gebruiker (jou). Kandidaat, geen verdict.

**4. `cockpit2.py`, 6.545 regels, structureel probleem, niet per se een regel-probleem.** Nog steeds
een lange if-ladder in `do_GET`/`do_POST` (geen routetabel), zoals de audit al aangaf. Ik vond geen
dode routes meer (goed teken, dat is al opgeruimd), dus dit is nu vooral een onderhoudbaarheids- en
"eleganter"-vraag: splitsen in modules per domein kan pas na een routetabel, en die refactor voegt
eerder regels toe dan dat hij ze wegneemt (expliciete mapping in plaats van impliciete if's). Relevant
voor je vraag naar elegantie, niet voor de 25%.

**5. Niet geverifieerd, wel het navragen waard:** of de persona-plumbing uit het claims-domein
(escaleer/projectverzoek-aanroepen in `claims_check.py`/`claim_evidence.py`) al is losgekoppeld
zoals in paragraaf 9 van de audit besloten. Dat is een kleine correctie, geen grote regelpost.

## Het eerlijke antwoord op "nog 25%"

Nee, niet uit meer verwijderen alleen. Concreet en geverifieerd staat er nu nog zo'n 3.900 regels
(keyword-laag + de vijf stragglers) klaar om weg te halen, op 72.048 regels bron is dat ongeveer 5%,
niet 25%. De grote 37.000-regel-belofte uit de audit van gisteren is voor het grootste deel al
verzilverd; wat overblijft is opgeruimd tot op het bot.

Om alsnog richting 25% te komen zijn er twee eerlijke routes, geen derde:

- **(a) Een nieuwe, even diepe doorlichting van wat nog wel leeft** (`views/metrics.py`, het
  claims-domein, `cockpit2.py`'s architectuur, en de rest van `views/` die ik nu niet een voor een
  is nagelopen), met dezelfde bril als de vorige audit: niet "draait het nog" maar "verdient het
  zijn plek". Dat kost een aparte, gerichte sessie, geen 20 minuten grep-werk.
- **(b) Verwachtingen bijstellen.** Een dorp dat net van 98.000 naar effectief zo'n 68.000
  functionerende regels is gegaan (72.048 nu, min de 3.900 die hierboven al klaarliggen) is al een
  reductie van 30% ten opzichte van het startpunt van gisteren. Nog eens 25% daarbovenop, gemeten
  vanaf nu, zou het dorp op ongeveer 51.000 regels brengen, mogelijk, maar dan moet er iets
  functioneels sneuvelen, geen dode code meer.

Mijn advies: eerst punt 1 (keyword-laag) en punt 2 (de vijf stragglers) laten doen door Claude Code
zodra fase 10 klaar is, dat is puur risicoloos opruimen van al besloten werk. Daarna pas beslissen of
je (a) wilt: een nieuwe diepe doorlichting specifiek op metrics/claims/cockpit2-architectuur.
