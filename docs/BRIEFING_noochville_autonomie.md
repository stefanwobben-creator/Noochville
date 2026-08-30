# Briefing — NoochVille: wat het is, hoe het werkt, en waar autonomie & output nú begrensd zijn

> Doel van dit document: je in een AI-chat scherpe ontwerpvragen laten stellen over **het verhogen
> van het autonomie-niveau en de output van het dorp**. Het beschrijft het systeem zoals het echt is
> (geen wensbeeld), benoemt de harde grenzen en waaróm ze er zijn, en wijst de concrete hefbomen aan.
> Plak dit als context bovenaan je gesprek.

---

## 1. Wat NoochVille is

NoochVille is een **event-driven "dorp" van autonome inwoners** (rollen) met échte skills, gebouwd voor
**Nooch.earth** — een duurzaam schoenenmerk dat organisch wil groeien via missie-gedreven SEO. Elke
inwoner is één rol met een doel (purpose), accountabilities, domeinen en een lijst skills. Inwoners
pakken zelf werk op dat bij hun rol past, kunnen elkaar om hulp vragen, en werken samen aan een hoger
doel. Het bestuursmodel is **Holacracy**.

**Belangrijk:** dit is een werkende kern, **geen simulatie**. De skills doen echte I/O — echte API-calls
naar Google Trends, Search Console, ngram, OpenAlex, Semantic Scholar, EPO-patenten, concurrent-analyse,
enz. Een skill **faalt liever bewust "closed"** (geeft `None`/error) dan dat hij data verzint.

Kernprincipe: **Records = de waarheid; een levende inwoner is een projectie daarvan.** Er is één
gezaghebbende bron (de governance-records) en de draaiende inwoners worden daaruit opgebouwd door de
`Reconciler`. Meer verantwoordelijkheid krijgen = het record amenderen (versie-bump) + `reload()` — geen
respawn, geen state die alleen in een thread leeft.

---

## 2. De intentie-laag (waaróm het dorp bestaat)

Van zwaar naar licht — dit stuurt hoe agents keuzes maken:

| Laag | Wat | Wie bezit het |
|------|-----|----------------|
| **Missie** | Anchor Circle-purpose: het duurzaamste schoenenmerk ter wereld zijn, om te laten zien dat meliorisme echt kan | Founder (jij) |
| **Statuten / richting** | geen advertising/plastic/leer, alleen nooch.earth, on-demand | Missie/visie |
| **Strategie** | organisch boven betaald, langetermijn-keywords, eigen website | Founder — `config/strategy.json` |
| **Doelen** | tijdgebonden targets, bijv. 1000 paar Q4 2026 via nooch.earth | Founder — `config/strategy.json` |
| **Structuur** | rollen, cirkels, accountabilities | Agents via governance |
| **Operatie** | dagelijks autonoom werk binnen de rol | Agents |

**Prioriteitsvolgorde:** Missie/statuten > domein-policy > strategie > doel. Agents rangschikken acties
op doelbijdrage; off-domein acties (zonder schoen-relatie) vallen af.

---

## 3. Architectuur — drie lagen + governance

1. **Het marktplein — `EventBus`.** Broadcast van feiten/aankondigingen. In-memory, synchroon,
   geen persistentie. Autonomie: inwoners reageren zélf op events die hen aangaan.
2. **De postbus — `Inbox` per inwoner.** Toegewezen werk dat áf moet. Betrouwbaarheid.
3. **De matchmaker — `Matchmaker`.** Hoort "wie kan dit?" en legt werk in de inbox van een capabele inwoner.

**Governance-infra:**
- **Secretary** — bezit de records, schrijft aangenomen wijzigingen weg. **Heeft geen veto.**
- **Facilitator** — draait het proces: voert de G0–G4-poort uit, beslist adopt of escaleren. Oordeelt
  nooit over inhoud, alleen over de deterministische poort.
- **Reconciler** — herbouwt het levende dorp uit de records na elke wijziging.

**Skills** worden geïnjecteerd via de `SkillRegistry` (echte I/O, fail-closed). **LLM** is optioneel
(een ladder: Gemini → Mistral → Anthropic), valt terug op `None` zonder key.

Drie soorten prikkels, bewust gescheiden:
- **Events** = aankondigingen → autonomie (reageer als het je aangaat).
- **Inbox** = toegewezen werk → betrouwbaarheid (dit moet áf).
- **`tick()`** = zelf-geïnitieerd werk → de hartslag.

---

## 4. Hoe een inwoner werkt

- **Eén rol per inwoner** (leaf). Een `Circle` is een composite (een cirkel delegeert, doet zelf geen werk).
- Reageren op events gaat via `self.react(event, handler)` — dat zet het event-job in de eigen inbox, zodat
  de handler op de eigen thread draait (nooit de afzender blokkeren; parallel werk).
- **Sensing op drie niveaus** (het dorp observeert gaten, meldt niet alleen incidenten):
  - *Doel-voortgang*: werkelijke trend vs. vereiste run-rate voor een actief doel.
  - *Missie-gat*: wat ontbreekt om de missie te dienen (geen rol, geen meting, geen koppeling).
  - *Zelf-gat*: eigen capaciteit vs. eigen accountabilities.
- Een gevoelde spanning gaat door **triage**: structureel/terugkerend → governance-voorstel; eenmalig →
  operationeel werk; past bij een andere rol → routeren; niets past → escaleren naar de mens.

**De uitvoer-primitief (hoe werk echt gebeurt):** projecten leven op een Kanban-bord met status-kolommen.
- **TOEKOMST** → `prepare_project`: een LLM breekt het projectdoel op in een **checklist**, waarbij het
  per item een skill uit **de DNA-skills van de owner-ROL** kiest + een payload vormt. Voert niets uit.
- **ACTIEF** → `_execute_checklist`: draait per item de skill, classificeert het resultaat (gelukt/leeg/fout),
  en schrijft een **deliverable-note** in de "wall" van het project. Vinkt een item alleen af bij écht succes.
- **DONE** → alleen als álle items af zijn (geen valse done; een onvoltooide checklist blijft in ACTIEF).
- Een **board-watch** pakt een sleep naar ACTIEF binnen seconden op (niet pas bij de dagelijkse puls).

---

## 5. Wat de AI's WEL doen (autonoom)

- Zelf werk oppakken dat bij hun rol-purpose/accountabilities past.
- Gaten signaleren (doel/missie/zelf) en er spanningen van maken.
- **Governance-voorstellen** genereren (`add_role`, `amend_role`) die beschrijven wat een nieuwe capaciteit
  zou doen — met een URL/bron als audittrail voor de mens.
- Échte skills draaien: data ophalen, analyseren, patenten/literatuur doorzoeken, concurrenten in kaart brengen.
- De **zoekwoord-ontdekkingslus** voeden: meerdere bronnen stellen kandidaat-woorden voor → de **Librarian**
  toetst aan de missie → goedgekeurde woorden worden zelfversterkend nieuw zaad. Dit is de belangrijkste
  waarde-motor en draait al echt autonoom.
- Elkaar om hulp vragen (via de Matchmaker) en aan de mens rapporteren (de dagelijkse Field Note, voorstellen).

---

## 6. Wat de AI's NIET doen — de harde grenzen (en waaróm)

Dit is de meest kritieke sectie voor je ontwerpvraag: elke hefboom om autonomie te verhogen botst hier
tegenaan of moet deze grens bewust heronderhandelen.

- **Zelfverbetering stopt bij voorstellen.** Een inwoner mag een gat signaleren en een `amend_role`/`add_role`
  -voorstel draften. Hij mag **NOOIT**: zelf code schrijven/uitvoeren/laden, een nieuwe externe API of databron
  aanroepen die niet al in zijn `skills`-lijst staat, een nieuwe `Skill` registreren, of een nieuwe thread
  starten voor nieuwe capaciteit.
- **Geboren versus bemenst.** Een aangenomen `add_role` schrijft alléén de rol-definitie (de rol is
  "onbemand geboren"). Pas als een **mens** de bijbehorende code schrijft én registreert (in `CLASS_MAP` +
  `SkillRegistry`) kan de rol als live inwoner draaien. **Capaciteitsuitbreiding is altijd mens-gated** —
  identiek aan deze splitsing voor rollen.
- **Skills falen closed.** Geen mock/verzonnen/geïnterpoleerde data; een gat blijft een gat.
- **Approvals uitsluitend via de geauthenticeerde lokale Human-inbox.** Geen extern/ongeauthenticeerd kanaal
  (mail, Slack, webhook) mag ooit een approval of activatie triggeren.
- **De Secretary heeft geen veto**; de G0–G4-poort is deterministisch, geen inhoudelijk oordeel.
- **Anti-proliferatie (G0):** een `add_role` vereist bewijs van herhaling — één incident is onvoldoende grond.

**Waarom dit zo is:** draaiende autonome code is niet omkeerbaar zoals een record-edit dat is. De drempel
voor nieuwe draaiende capaciteit is daarom altijd menselijke goedkeuring + handmatige registratie.

**Wat wél al soepel is:** *adopt-by-default*. Een niet-geëscaleerd, structureel-geldig voorstel wordt
automatisch aangenomen (de mens hoeft niet te tekenen). Alleen wat de G1–G4-poort niet haalt (domein-botsing,
accountability-duplicaat, verweesd werk, of een wijziging van de missie-purpose) escaleert naar de mens.

---

## 7. Waar autonomie & output nú begrensd zijn — de hefbomen

Dit zijn de concrete plekken waar je aan kunt draaien. Elk is een ontwerpkeuze, geen bug.

1. **Uitvoerdiepte = formatteren, niet synthetiseren.** De rol leest de skill-output, classificeert 'm
   (gelukt/leeg/fout) en schrijft de rúwe velden als note. Er is **geen redeneerstap** die de deliverables
   samensmelt tot een echt artefact (een brief, een pagina, een aanbeveling). De output is "ruwe data,
   nette note" — niet "inzicht" of "actie".
2. **Bijna alle skills lezen; weinig schrijven.** Het dorp haalt op en analyseert; het produceert nauwelijks
   iets dat de wereld ín gaat (content publiceren, de site bijwerken). Output = inzicht, geen actie.
3. **De uitkomst-lus is niet gesloten.** Het dorp produceert keywords/onderzoek maar meet de échte uitkomst
   niet (bv. `pairs_sold` is niet meetbaar in de puls). Doel-voortgang-sensing bestaat, maar zonder outcome-
   metriek kan het dorp niet op resultaat bijsturen.
4. **Capaciteit is 100% mens-gated.** Nieuwe skills/rollen vereisen mens-code + registratie. Het dorp kan
   z'n eigen capaciteit wél voorstéllen maar niet uitbreiden. Er is (nog) geen "adopt-by-default voor capaciteit".
5. **De mens is de flessenhals voor activatie + escalatie.** Alles wat de G1–G4-poort niet haalt, plus elke
   rol-activatie, wacht op de lokale inbox.
6. **Coördinatie tussen inwoners is dun.** Ze kunnen elkaar via de Matchmaker om hulp vragen, maar echte
   multi-rol-samenwerking op één uitkomst (een cluster dat samen aan één doel werkt) is beperkt.
7. **Ritme & betrouwbaarheid van prep.** De puls draait ~1×/dag; LLM-plangeneratie kan falen (parse/afkap),
   items kunnen fail-closed blijven. Output-volume hangt aan prep-robuustheid en aan skill-`cost`/quota.

---

## 8. Het kernspanningsveld voor je ontwerp

> **Autonomie & output omhoog vs. de mens-gate (veiligheid/omkeerbaarheid).**

Elke echte hefboom (dieper uitvoeren, schrijf-acties, zelf-uitbreiden, vaker draaien) verhoogt óf de
output óf de autonomie, maar raakt de grens uit sectie 6. Het scherpe ontwerpwerk is niet "hoe zet ik de
gate uit", maar: **"per as — welke stap kan veilig binnen (of net over) de gate, en met welk vangnet?"**
Het systeem heeft daar al een sjabloon voor: *adopt-by-default* (aannemen tenzij structureel ongeldig) en
*geboren-versus-bemenst* (definiëren mag autonoom, activeren is mens-gated). De vraag is telkens: wat is
het equivalent van die twee patronen voor déze nieuwe capaciteit?

---

## 9. Scherpe ontwerpvragen om het gesprek te voeden

Gebruik deze als startpunt (of laat de AI ze aanscherpen tegen de context hierboven):

- **Synthese-laag:** Wat is de veiligste manier om een redeneerstap toe te voegen tussen skill-output en
  deliverable (ruwe data → gesynthetiseerd artefact), zónder de fail-closed-regel te breken? Waar leest de
  rol de output, en wat mag een LLM daar wél/niet mee?
- **Schrijf-skills:** Welke schrijf-acties (concept-content, pagina-draft, interne notitie) mogen autonoom,
  en welke blijven mens-gated? Waar ligt precies de grens tussen "voorstel" en "uitvoering" bij content?
- **Adopt-by-default voor capaciteit:** Kan er een **gecureerde, vooraf-goedgekeurde skill-bibliotheek**
  bestaan die een inwoner binnen grenzen zelf mag activeren — het capaciteits-equivalent van adopt-by-default?
  Welke eigenschappen (read-only, geen quota, side-effect-free) maken een skill "auto-activeerbaar"?
- **Uitkomst-lus sluiten:** Welke minimale, echt-meetbare outcome-metriek (bezoekers → conversie → paar)
  sluit de lus zodat het dorp op resultaat kan bijsturen i.p.v. alleen op tussenproducten?
- **Approval-doorvoer:** Welke beslissingen kunnen binnen policy vooraf-gedelegeerd worden, zodat de mens
  niet de flessenhals is — en welke moeten altijd mens-gated blijven? Hoe ziet een "policy-envelop" eruit
  waarbinnen de agent zelf mag beslissen?
- **Coördinatie:** Welk primitief laat een **cluster rollen samen** aan één uitkomst werken (deel-projecten,
  afhankelijkheden, een rol die sub-werk delegeert) i.p.v. losse projecten per rol?
- **Ritme & kosten:** Verhoogt vaker pulsen de output, of botst dat op skill-`cost`/quota? Waar zit de
  economische begrenzing, en welke skills zijn veilig-herhaalbaar (`free`) vs. gemeten (`credits`)?
- **Betrouwbaarheid:** Hoe maak je prep + uitvoering robuuster (retry, partiële voortgang, betere planning)
  zodat meer projecten daadwerkelijk tot deliverables komen i.p.v. leeg/fout blijven?

---

## 10. Woorden die je AI-gesprekspartner moet respecteren

Als de AI voorstellen doet, laat 'm deze grenzen expliciet honoreren (of bewust benoemen dat hij ze
heronderhandelt):
- Zelfverbetering stopt bij voorstellen; nieuwe draaiende capaciteit is mens-gated.
- Skills falen closed — nooit verzonnen data.
- Approvals alleen via het geauthenticeerde lokale oppervlak.
- Records = waarheid; capaciteit erbij = record amenderen + (mens) code registreren, geen respawn.
- Missie > domein-policy > strategie > doel.

Vraag de AI om per voorstel te benoemen: **welke as van autonomie/output het verhoogt, welke grens het
raakt, en welk vangnet (gate, policy-envelop, omkeerbaarheid) het meebrengt.**
