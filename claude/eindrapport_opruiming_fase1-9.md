# Eindrapport — opruiming fase 1 t/m 9

**Datum:** 20 september 2026
**Branch:** `fase1-dode-rolklassen`, 16 commits, `4cc594f` t/m `41522eb`
**Opdracht:** `~/Downloads/implementatiebrief_opruiming_19sept.md`, fase 1–9 achter elkaar door
**Waarom dit bestand en niet de terminal:** twee brede tabellen zijn onderweg naar Stefan
beschadigd geraakt. Alles met een lijst of tabel gaat vanaf nu naar een bestand.

---

## 1. Het eindcijfer

| | broncode (`nooch_village/`) | tests (`tests/`) |
|---|---:|---:|
| vóór fase 1 (`main`) | 98.185 regels · 349 bestanden | 80.040 regels · 491 bestanden |
| ná fase 6 | 71.556 | 57.795 |
| **ná fase 9 (`41522eb`)** | **71.978 regels · 259 bestanden** | **58.150 regels · 378 bestanden** |
| verschil t.o.v. `main` | **−26.207 (−26,7%)** | **−21.890 (−27,3%)** |
| | −90 modules | −113 testbestanden |

Fase 7, 8 en 9 zijn bouwfasen, geen opruimfasen: ze zetten er 422 regels broncode en 355 regels
test bíj bovenop de stand na fase 6. Dat is het verschil tussen de twee onderste regels.

Diffstat over de hele tak: **370 bestanden, +3.554, −51.270**.

### Wat er structureel kleiner werd

| | vóór | ná |
|---|---:|---:|
| Routes (`docs/ARCHITECTUUR.md` sectie a) | 63 | 42 |
| Dispatch-acties (sectie b) | 198 | 144 |
| Skills (`skills_impl/`) | 59 | 30 |
| Views (`views/`) | 42 | 30 |
| `inhabitant.py` | 3.282 regels | 866 regels |

### De audit zat er 10.000 regels naast

De audit schatte ~37.000 regels broncode "verdedigbaar weg". Het zijn er 26.207 geworden. Het
verschil zit vrijwel volledig in posten die bij nader inzien een levende lezer bleken te hebben —
zie §4.

### Per commit

| commit | fase | + | − |
|---|---|---:|---:|
| `4cc594f` | 1 — zes dode rolklassen | 72 | 4.487 |
| `3ba6db1` | 2a — elf modules zonder importer | 6 | 1.956 |
| `69c76ab` | 2b — de kennisbank-tak | 190 | 13.643 |
| `399cf2c` | 3 voorwerk — Noochie's voorstel naar het log | 73 | 22 |
| `993d0ff` | 3 BLOK A — projectuitvoering + sensing | 230 | 8.077 |
| `ee1ce43` | 3 BLOK C — Founder Flow, Codie-backlog | 67 | 4.460 |
| `87fbdca` | 3 BLOK B — projectrand + verslag-assembler | 95 | 3.572 |
| `d9f7834` | 4 — radar-beoordelingslaag | 200 | 7.485 |
| `b2c6524` | 4 sluitstuk — ingest aan dagcadans + legal-check | 356 | 0 |
| `a70fcaf` | 5 — claims los van rol/persona | 234 | 221 |
| `faf8c89` | 6 — dode handlers, routes, speeltuin, skills 1+2 | 179 | 6.789 |
| `25cefde` | 6 sluitstuk — EPIC-aardbol + alphavantage | 12 | 537 |
| `168f548` | 7 — zijbalk, Projects-landing, Wiki, Keep-in-wiki | 649 | 120 |
| `6cbce5f` | 8 — de gespreklaag | 656 | 26 |
| `0f47a98` | 8 — de twee cijferreeksen in `channels.py` | 23 | 4 |
| `41522eb` | 9 — Nooch UI v1 op negentien schermen | 646 | 5 |

---

## 2. Wat er in fase 9 bewust is overgeslagen

De brief: *"Schermen die in fase 1-8 niet zijn aangeraakt qua UI hoeven in deze fase niet mee.
Dat is een bewuste keuze, geen vergeten stuk: meld expliciet aan Stefan welke schermen je om die
reden overslaat."*

**Negentien schermen dóén mee** (`body.nu`, via `cockpit2._NU_ROUTES`):

```
/ (→ /projects)   /projects      /messages      /wiki          /pagina
/node             /person        /project       /project/nieuw /admin
/search           /inbox         /inbox/verwerk /goals         /goal
/werkoverleg      /roloverleg2   /vangst        /index.html
```

**Zevenentwintig routes blijven in de oude stijl:**

| groep | routes | waarom overgeslagen |
|---|---|---|
| Claims | `/claims`, `/claims/scan` | Fase 5 raakte alleen de persona-koppeling, niet de UI. Het best werkende cluster van het dorp, met een externe deadline (EmpCo, 27 september). |
| Metrics | `/metrics2`, `/kpi_new`, `/metric_export` | Grootste view-bestand van de repo (2.149 regels). Niet aangeraakt in fase 1–8. |
| Catalogus & bronnen | `/catalog`, `/bronnen`, `/skills` | Niet aangeraakt in fase 1–8. |
| Tools | `/copy-check`, `/copy-prompt`, `/decision-coach`, `/site-audit` | Eigen schermen, los van de herbouwde navigatie. |
| Zoekwoorden | `/keywords`, `/woordenschat`, `/long-term-trends` | Niet aangeraakt. |
| Lezers | `/rapport`, `/noochie`, `/middelen`, `/rolefillers`, `/context`, `/file` | `/rapport` is in fase 3 read-only gemaakt, verder onaangeroerd. |
| Auth | `/login`, `/logout`, `/wachtwoord` | Buiten de ingelogde cockpit. |
| Wizard | `/wizard/create`, `/wizard/plan`, `/wizard/sharpen` | Fase 3 haalde er AI-velden uit; de vormgeving bleef. |

**Twee daarvan springen eruit.** `/claims` is het cluster dat je het vaakst open hebt staan en
`/metrics2` is het grootste scherm. Ze overslaan betekent dat het dorp er half nieuw en half oud
uitziet op precies de schermen die dagelijks gebruikt worden. Jij hebt ze geparkeerd als kandidaat
voor een tiende fase; dit is de expliciete melding die de brief eist.

**Daarnaast blijven 63 kleur-alleen-statussen staan** buiten de negentien schermen (`kn-` 14,
`ibx-` 6, `cl-` 5, `wz-` 5, `ck-` 3, `imp-` 2, `noo-` 2, `rdr-` 2, `einddoc-` 2, `chip.coral` 2,
plus 18 losse selectors). De regel "status is vorm plus woord" geldt dorpsbreed, maar toepassen
buiten de scope was groter dan fase 9. Jouw besluit; hier gelogd.

**En drie prototype-onderdelen zijn bewust níét gebouwd:**

1. `.embed` / `.embed-head` / `.file-grid` / `.file-card` / `.img-placeholder` — dit is de
   "rich page (demo)" op de wiki in het prototype: een demonstratie van wat een pagina *zou
   kunnen* dragen. Er zit geen bestaande functionaliteit achter. Bouwen zou een feature verzinnen
   onder het mom van vormgeving.
2. `.toggle` / `.track` — alleen nodig op Admin · Skills, en die blijft read-only tot jij over de
   schrijfbaarheid beslist.
3. `.crumb` — de breadcrumb is op 23 juli met reden verwijderd (de hiërarchie staat in de
   organisatieboom). Niet terugzetten zonder besluit.

---

## 3. Alle stopmomenten, fase 1 t/m 9

De opdracht was: doorlopen zonder tussentijds akkoord, en alleen stoppen bij (a) een
onverklaarbare testregressie, (b) de momenten die het document zelf aanwijst, (c) iets onderweg
dat niet in het document staat. Het zijn er **negentien** geworden. De derde categorie is met
afstand de grootste, en dat is het belangrijkste cijfer in dit rapport.

| # | fase | waar het over ging | categorie | uitkomst |
|---|---|---|---|---|
| 1 | nulmeting | De volledige suite liep vast bij de nulmeting. | a | Opgelost, `ga door`. |
| 2 | 1 | Elf documenten waar de brief naar verwijst bestaan geen van alle. Voor fase 3 en 6 is dat blokkerend. | c | Gemeld; document kwam later. |
| 3 | 2 | `orphan_report.py` — de brief zegt zelf "check dit eerst". Geen importer, geen spoor op de server; of hij ooit gedraaid heeft kon ik niet vaststellen. | b | Laten staan. |
| 4 | 2 | De kennisbank-tak: drie wegen, waarvan één de claims-poort vóór 27 september zou raken. | c | Optie 1: alles eruit, `notes_store` mee. |
| 5 | 2 | Bevestiging gevraagd dat `content_check.py`/`content_schrijven.py` geen levende aanroeper meer hebben. | c | Bevestigd, weg. |
| 6 | 2b | `weten_we_dit_al` zit bij twee **levende mens-rollen** in het DNA en leest een andere store dan de brief aannam. | c | `kennisbank.py` + store blijven ongewijzigd. |
| 7 | 3 | `audit_diep_..._19sept.md` §1 moet de bindende bron zijn voor de methodegrenzen in `inhabitant.py`, en bestaat niet. | c | Document kwam; §1 werd leidend. |
| 8 | 3 | `_sense_gap` staat op de sloop-lijst maar wordt door `Noochie._reflect` aangeroepen, en Noochie blijft bestaan. | c | `Noochie._reflect` logt nu in plaats van te escaleren (`399cf2c`). |
| 9 | 3 | **BLOK A leeft.** `llm_usage.jsonl` toonde 271/46/46 calls, laatste op 19 september. De audit zet BLOK A in §7 zelf achter een voorwaarde die de brief negeert. | c | Bewust gedragsbesluit: toch weg. |
| 10 | 3 | `/rapport` zou "0 van 386" zijn. In werkelijkheid 363 einddocumenten, 3,0 MB, nieuwste 18 september. Weghalen betekent dat die hun enige lezer verliezen. | c | Optie 2: reader blijft read-only, `stel_samen` + LLM-call eruit. |
| 11 | 3 | BLOK C: `founder_kaart.py`, `gap_ledger.py`, `gap_classifier.py` — de brief groepeert ze fout. | c | Met rust gelaten; alleen `/codie` weg. |
| 12 | 4 | `inoreader_ingest` draait op prod als crontab-regel, niet op de dagcyclus. Verhuizen zonder dat jij die regel schrapt geeft twee ingests per dag. | b | Verhuizen; schrappen als expliciete deploy-stap. Jij hebt de regel op 19 sept al verwijderd. |
| 13 | 6 | Voorstel om fase 6 eerst te inventariseren in plaats van de brief te volgen — na vier eerdere gevallen waarin de bestandslijst niet klopte. | c | Akkoord; leverde negen afwijkingen op. |
| 14 | 6 | `/catalogus_koppelen` (alleen een 303-redirect; de echte view rendert inline in `/catalog`) en `/claims/db.json` (nul requests in 14 dagen, maar een eigen script viel niet uit te sluiten). | b | Beide weg. |
| 15 | 6 | `/epic/frame` bleek geen speeltuin maar de NASA-aardbol op de Mother Earth-overzichtspagina; `alphavantage` haalde die ochtend nog data op. | c | Beide weg, inclusief `meetcatalog.CATALOG` en `sources.json`. |
| 16 | 7 | Messages in de zijbalk zonder channel-laag erachter; de tussentoestand "fase 7 is structuur, fase 9 is stijl"; Admin · Skills schrijfbaar in het prototype. | c | Messages helemaal weg tot fase 8; stijl volgens plan; Skills read-only. |
| 17 | 8 | Wat er met de 362 meldingen moet gebeuren: 24 @-vermeldingen versus 338 rol-notificaties. | c | Driedeling: alleen de 24 naar kanalen. |
| 18 | 8 | Je vroeg na afloop om de exacte verantwoording voor die 338 vóór je akkoord gaf. | c | Twee harde cijfers geleverd, vastgelegd in `channels.py`. |
| 19 | 9 | Vier ontwerpvragen (statusweergave, tokens, `/claims`+`/metrics2`, screenshots). | b + c | Alle vier beantwoord. |

### Wat dit cijfer zegt

Van de negentien stopmomenten waren er **drie** wat de brief voorzag (#3, #12, #14) en **vier**
de fase-9-vragen of een testprobleem. De overige **twaalf** waren premissen in de brief of de
audit die bij live verificatie niet klopten. Dat is geen klacht over het document — het is het
argument voor de volgorde die jij na fase 6 zelf benoemde: *"Met hoe vaak de documenten en
aannames dit traject niet bleken te kloppen, is dat de juiste volgorde."*

### Twee stopmomenten die ik had kunnen overslaan, en niet heb overgeslagen

- **#9 (BLOK A).** Ik had kunnen uitvoeren wat er stond. In plaats daarvan heb ik aangetoond dat
  de cluster leefde en het besluit teruggelegd. Jij hebt hem daarna alsnog weggehaald — maar als
  bewuste gedragsverandering, niet als opruiming van dode code. Dat onderscheid staat nu in de
  commit en overleeft de sessie.
- **#10 (`/rapport`).** De brief zei "weg". 363 bestaande documenten zouden hun enige lezer
  verliezen. Dat is geen technische keuze en ik wilde het je expliciet horen zeggen.

---

## 4. Elf premissen die bij verificatie onjuist bleken

Dit is de kern van waarom het traject 26.207 in plaats van 37.000 regels werd.

| premisse | werkelijkheid | bron van bewijs |
|---|---|---|
| BLOK A is "idle" | 271 / 46 / 46 LLM-calls, laatste 19 september | `data/llm_usage.jsonl` op prod |
| `/rapport`: 0 van 386 | 363 documenten, 3,0 MB, nieuwste 18 september | `data/output/` op prod |
| `views/strategy.py` wordt nooit getoond | `_strategy_tab_html` rendert in élk cirkel-overzicht | call-site in `views/overview.py` |
| `/epic/frame` is een speeltuin | rendert de NASA-aardbol op de anchor-cirkelpagina | live pagina |
| `alphavantage` ligt stil | haalde die ochtend AEX + S&P op, 52 metingen per reeks | `data/metrics.jsonl` |
| `/catalogus_koppelen` is een scherm | is een 303-redirect; de 232-regel view rendert inline in `/catalog` | `cockpit2.py` |
| `_act_check_handoff` is dode AI-plumbing | is mens-naar-mens routing (`@iemand, kijk jij hier even naar`) | `route_werk` → inbox |
| `semantic_scholar` is dormant | tweede trede van de bewijs-ladder onder `openalex_evidence` | `evidence_ledger.py:43` |
| `weten_we_dit_al` hangt aan `notes.json` | leest `data/kennisbank.json`, andere store, twee levende mens-rollen | rol-DNA in `governance_records.json` |
| de organisatieboom bestaat nergens (**mijn eigen fout**) | bestond al als `c2-rail`; fase 7 was verhuizen, niet bouwen | `cockpit2_util.py` |
| tokens kunnen in twee losse `:root`-blokken | kan niet: `--border` is oud een kleur en nieuw een shorthand, 147× gebruikt | `nooch.css` |

De laatste is de enige waar ik van de letterlijke instructie ben afgeweken. Zie §6.

---

## 5. Mijn eigen fouten in dit traject

Zonder deze lijst is het rapport niet eerlijk. Alles hieronder is door de testsuite, de browser of
door jou gevonden, niet door mij bij het schrijven.

**Methodefouten** — verkeerde meetmethode, goede uitkomst:

1. **De `data-qa-action`-blinde vlek (fase 6).** Mijn verzender-check zocht alleen naar
   `value='actie'` in HTML. Ik miste dat `nooch.js` óók `data-qa-action` leest. Ik heb alle twaalf
   handlers opnieuw gecontroleerd — ze bleken alsnog onbereikbaar — maar de check had vanaf het
   begin de JavaScript mee moeten nemen.
2. **De testscanner miste verwijzingen, drie rondes lang.** Eerst een platte naam-match, toen
   transitiviteit binnen een bestand via helpers, toen alias-detectie (`from X import Y as op` →
   tests die `op.draai` aanroepen). Elke ronde liet falende tests achter die de volledige suite
   opving.
3. **54 versus 63 kleur-alleen-statussen.** Mijn eerste telling was een `grep -c` op regels, niet
   op selectors. Gecorrigeerd in het inventarisatiebestand.
4. **De zwakste van drie argumenten als hoofdargument gebruikt (fase 8).** Ik verdedigde het
   laten staan van de 338 rol-notificaties met "ruis". De twee harde redenen — 5 van 338 hebben
   een mens-afzender; het read/processed/archived/outcome/poort-model is geen boolean — heb ik pas
   opgezocht nadat jij ernaar vroeg. Ze staan nu in `channels.py` zelf.

**Uitvoeringsfouten** — kapot gemaakt en gerepareerd:

5. **Te agressieve opruiming in `tests/`.** Mijn orphan-helper-logica verwijderde vooraf bestaande
   dode testhelpers (`_seed` in `test_cockpit.py`) die niets met de fase te maken hadden. Scope
   creep, gevonden door de diff te lezen. Teruggedraaid met `git checkout -- tests/`, logica uit.
6. **Een voorbarige assertie.** `assert not hasattr(noochie, "_sense_gap")` terwijl de methode nog
   bestond. Erger: de docstring erbij beweerde dat de cluster al weg was. Beide gecorrigeerd — de
   assertie toetst nu de *aanroep*, via AST.
7. **`_DS_LINK` niet geïmporteerd** in `cockpit2` → `NameError` → de server verbrak verbindingen →
   `test_login_required` faalde met `RemoteDisconnected`.
8. **Mijn eigen CSS-test las een comment.** Het uitleg-blok bovenin `nooch-ui.css` noemt `:root`,
   en de test telde dat mee. Exact dezelfde les als de docstring bij #6: strip eerst de comments.
9. **Regex-fouten, drie stuks.** `[^\]]+` brak op geneste haken in `[d["id"]]`; ingesprongen
   imports verloren hun inspringing bij het herschrijven; de token-regex matchte klassenamen
   (`.nu-status--ok::before` → `--ok`), en `@media` werd als selector gelezen.
10. **`git stash` liet mijn werk in de stash staan** terwijl een grep op de achtergrond liep.
    Teruggehaald met `git stash pop`.
11. **Een testfixture die op bootstrap-namen botste.** `people.add` dedupliceert op naam en
    `_bootstrap` zet al een "Stefan Wobben" zónder e-mail neer, dus `by_email` gaf `None` en de
    vermelding viel terug op een notificatie. De terugval wérkte precies zoals bedoeld; mijn
    fixture was fout.

---

## 6. De eindcheck met Playwright — volledige bevindingen

**Methode.** `claude/fase9_screenshots/maak_screenshots.py` zet een wegwerp-datamap op met vier
demo-projecten, twee personen, een note/policy/tool, een cirkelbericht, een DM en een
project-feed-entry; start de cockpit in gast-modus op poort 8807; en schiet elk scherm op twee
breedtes met Chromium. Acht schermen × twee breedtes = **16 screenshots**, opgeslagen in
`claude/fase9_screenshots/`.

Waarom gast-modus: `serve()` zet altijd een `SessionStore` neer, en dan is élke route een
login-redirect. `make_handler(dd, csrf, None, None)` is de modus die de testsuite ook gebruikt.

### De scope-meting

| scherm | route | 1280×900 | 390×844 | `body.nu` |
|---|---|---|---|---|
| Projects | `/projects` | ✓ | ✓ | **True** |
| Messages | `/messages` | ✓ | ✓ | **True** |
| Wiki | `/wiki` | ✓ | ✓ | **True** |
| Circle | `/node?id=mother_earth__nooch` | ✓ | ✓ | **True** |
| Circle · Wiki-tab | `/node?…&tab=wiki` | ✓ | ✓ | **True** |
| Project-detail | `/project?id=…` | ✓ | ✓ | **True** |
| Admin | `/admin` | ✓ | ✓ | **True** |
| Claims (geparkeerd) | `/claims` | ✓ | ✓ | **False** |

Zestien van de zestien renderden zonder fout. De scopegrens doet precies wat hij belooft: zeven
schermen in, `/claims` eruit.

### Vier dingen die alleen de browser vond

1. **Alle zestien screenshots van de eerste ronde waren de loginpagina.** `serve()` zet altijd een
   sessiestore. Zonder de browser had ik "16 screenshots gemaakt" gerapporteerd zonder ooit een
   scherm gezien te hebben. Dit is het ongemakkelijkste punt in dit rapport: de fout zat in mijn
   verificatie, niet in de code.
2. **`_DS_LINK` was niet geïmporteerd in `cockpit2`.** Een `NameError` zodra de scope-injectie
   liep. De unit-tests lezen de broncode en zagen niets; pas een echt HTTP-verzoek liet de server
   de verbinding verbreken.
3. **De vier bordkolommen droegen elk een pasteltint** (blauw, oranje, groen, grijs) — precies de
   kleur-alleen-status die dit hele systeem vervangt. In zwart-wit vier identieke vakken.
   Vervangen door één rustige achtergrond plus een vormmerk per kolom, dezelfde vormen als
   `.nu-status`.
4. **Messages opende op een leeg kanaal.** Hij pakte simpelweg het eerste kanaal uit de lijst, en
   dat was de anchor-cirkel: je landde op *"Nothing said here yet"* terwijl er drie kanalen
   verderop wél gesprek stond. Nu opent hij op het eerste kanaal mét berichten.

**Geen van de vier was met een unit-test te vinden.** De 4.027 tests lezen broncode; de browser
leest de gerenderde pagina. Dat is de reden dat Playwright nu in `requirements-dev.txt` staat en
niet weer uit de venv verdwijnt.

### Twee correcties op het addendum van gisteren

- `nooch-ui.css` is **179 regels**, niet 170. De bordkolom-fix van punt 3 kwam er na het schrijven
  van het addendum bij.
- De screenshots staan niet meer "in de scratchpad van de sessie" maar in
  `claude/fase9_screenshots/`, samen met het script dat ze maakt.

### De afwijking van de letterlijke instructie

Je besluit was: *"Tokens: strikt twee gescheiden bestanden/`:root`-blokken, geen aliasing."* Dat
kan technisch niet. Vier tokennamen botsen, en `--border` is dodelijk: in `nooch.css` is het een
**kleur** (`#DDD4C0`), in het prototype een **shorthand** (`2px solid var(--text)`), en hij staat
er **147×** als `border:1px solid var(--border)`. Een tweede globale `:root` maakt daar
`border:1px solid 2px solid #000` van — ongeldige CSS — en dan verdwijnen de randen op élk scherm,
óók de geparkeerde.

Opgelost met de **`--nu-`-naamruimte onder een `.nu`-scope**: eigen bestand, eigen blok, geen
aliasing, geen botsing. De uitleg staat in de kop van `nooch-ui.css` zelf, bij de code, niet alleen
hier.

---

## 7. Eigen keuzes waar stoppen niet verplicht was

De brief vroeg hier expliciet naar. Dit zijn beslissingen die ik zelf heb genomen en gerapporteerd,
in plaats van te vragen.

| fase | keuze | waarom |
|---|---|---|
| 1 | Geknipt op **AST-grenzen** in plaats van op de regelnummers uit de brief (634 in plaats van 696 voor `HarryHemp`). | De bron is betrouwbaarder dan het document. Dit bleek later het patroon van het hele traject. |
| 1 | `source_died` herschreven in plaats van weggegooid, en meteen over **alle** rollen getoetst in plaats van alleen `website_watcher`. | Dorpsinfrastructuur mag nergens in een rol terugkruipen. |
| 2b | `reeds_bekend.py` nieuw gebouwd als verse vervanging voor `kennis_context`, met alle zeven aanroepers omgebouwd. | Weghalen zonder vervanging had zeven call-sites stil laten falen. |
| 3 | De **aanroep-closure** zelf afgeleid in plaats van §1's methode-aantallen te vertrouwen; alles met een aanroeper buiten de cluster bleef staan. | Jouw expliciete instructie bij #9, en daarna als werkwijze aangehouden. |
| 3 | `curate` bleek al geen implementatie meer te hebben; alleen het label opgeruimd. | Verklaart meteen de `fout`-uitkomst op prod: de uitvoerder draaide een skill die niet bestond. |
| 3 | `HOOG_INZET` in `llm_keuze.py` van een comment voorzien in plaats van de dode namen te verwijderen. | Elf modelbeleid-tests gebruiken die namen als voorbeeld-callsite. Aparte beurt. |
| 5 | Een echte bug uit mijn eigen fase 2b gerepareerd: `/wizard/plan` importeerde `kennis_context`, en de `except` slikte zowel de `ImportError` als het deliverable-blok in dezelfde `try`. | De wizard logde bij elke plan-aanroep stilletjes een exception. Nu twee aparte `try`'s. |
| 6 | `_act_check_handoff` en `semantic_scholar` **teruggezet** nadat ik ze had verwijderd. | Zie §4. Gevonden door de diff te lezen, niet door een test. |
| 6 | `views/strategy.py` en `strategy_store.py` laten staan hoewel ze op de lijst stonden. | Dat is geen opruiming maar een functionele breuk in elk cirkel-overzicht. |
| 7 | Keep-in-wiki **strenger** dan het prototype: alleen de rolvervuller of Circle Lead van de pagina mag er een feit op zetten. | Een stilzwijgend lossere poort is erger dan een strakke. Knelt het, dan is het een governance-vraag, geen UI-vraag. |
| 8 | Project-kanalen delegeren naar `ledger.add_feed_entry` in plaats van een eigen store te krijgen; alleen cirkel- en DM-kanalen leven in `data/channels.json`. | Anders had hetzelfde gesprek op twee plekken geleefd — de `reference, don't copy`-regel. |
| 8 | De @-vermelding valt **fail-closed** terug op een notificatie als de tweede partij niet te bepalen is. | Liever een melding te veel dan een bericht dat nergens aankomt. |
| 9 | De `--nu-`-naamruimte in plaats van twee `:root`-blokken. | Zie §6 — de enige afwijking van een letterlijke instructie in het hele traject. |
| 9 | `.embed`, `.toggle` en `.crumb` niet gebouwd. | Zie §2 — respectievelijk een verzonnen feature, een openstaand besluit, en een bewuste eerdere verwijdering. |

---

## 8. Toestand bij oplevering

**Testsuite:** 4.027 passed, 1 failed, 1 xfailed (`./venv/bin/python -m pytest tests/ -q`, 120 s).

De ene failure is `tests/test_scope58_eigen_cijfers.py::test_plausible_zonder_sleutel_is_een_fout_geen_lege_lijst`.
Die faalt **ook op kale `main`** en is niet door dit traject veroorzaakt: het is een
omgevingslek — een eerder testbestand laadt de echte `.env`, waarna `is_configured` de werkelijke
`PLAUSIBLE_SITE_ID` ziet. Los van deze opruiming, eigen beurt.

**Nog niet gedeployed.** De tak staat lokaal; de deploy doe jij met `scripts/deploy.sh`.

**Eén openstaand deploy-detail uit fase 6:** `Pillow>=11` in `requirements.txt` draagt het commentaar
*"EPIC-aardbol: volle NASA-PNG server-side resizen"*. Die aardbol is in `25cefde` verwijderd en er
is nu **nul** verwijzing naar `PIL` in de broncode. De regel en het commentaar zijn dus dood. Ik heb
hem laten staan: een dependency schrappen laat `deploy.sh` de venv opnieuw resolven, en dat is een
risicomoment dat jij hoort te kiezen, niet ik.

---

## 9. Wat hierna nog open staat

1. **Admin · Skills-schrijfbaarheid** — het prototype zet er toggles neer (*"No approval needed to
   switch on/off"*), live is `/skills` read-only. Dit is geen UI-vraag maar een nieuwe
   schrijfbevoegdheid op skills. Ligt bij jou.
2. **Een tiende fase voor `/claims` en `/metrics2`** — de twee schermen uit §2 die je het vaakst
   gebruikt en die nu in de oude stijl staan.
3. **De 63 kleur-alleen-statussen** buiten de negentien schermen (§2).
4. **`Pillow` uit `requirements.txt`** (§8).
5. **De plausible-testfailure** — een omgevingslek, geen regressie (§8).
6. **De pagina "How we decide here" rendert zijn eerste regel verkeerd.** `content/how_we_decide_en.md`
   opent met `# How we decide here` en bevat een `---`-streep, maar de wiki-renderer (`_md`) kent
   alleen `## `-koppen en `- `-lijsten. Beide komen er letterlijk doorheen, dus op
   `village.nooch.earth/pagina?id=NOTE-STRATE-001` staat sinds 18 september een zichtbare `#` boven
   de tekst. Mijn fout: ik heb die tekst destijds nooit gerenderd bekeken — dezelfde categorie als
   de zestien loginpagina-screenshots in §6. **Het bronbestand repareren helpt niet:** `wiki_seed`
   overschrijft nooit, dus de live pagina verandert alleen als iemand hem in de UI bijwerkt.
   `content/claims_policy_en.md` is wél voor deze renderer geschreven, met een guard-test erop.

---

*Bijlagen: `claude/fase9_designsysteem_inventarisatie.md` (designsysteem-diff, 20-rijige
pariteitstabel, scope-lijsten) en `claude/fase9_screenshots/` (16 screenshots + het script).*
