# NoochVille — Ontwerpnotitie: Projecten, Metrics & de gedeelde Gap-Judgment (2026-06-14)

*Blauwdruk, geen implementatie. Vastgelegd zodat de volgende sessie hierop bouwt en niet op herinnering. Bouw niets van dit document zonder eerst `docs/STATE.md` te lezen en de spelregels te respecteren (mens-gated activatie, diff vóór commit, spine blijft dom).*

---

## Waarom deze upgrade

Het dorp draait nu op één tempo, de dagpuls, en kan alleen bestaande rollen amenderen. Drie gaten:

1. Geen niet-continu werk. Sommige taken hoeven niet dagelijks, maar eens per maand of kwartaal, of op aanleiding.
2. Geen tijdreeksen. Er is geen plek waar metric-waarden over tijd landen, dus geen patroondetectie. De analyst voelt dit al (bezoekers → `pairs_sold`).
3. Het dorp baart geen rollen en ontwikkelt geen nieuwe middelen uit zichzelf.

Deze notitie lost die drie samenhangend op, met één gedeeld oordeelsmechanisme.

---

## Holacracy-grondslag (de reden dat de spine dom blijft)

"Project" en "Metrics" zijn geen verzonnen machinerie, het zijn bestaande Holacracy-primitieven. En cruciaal: ze horen **niet bij governance**. Governance wijzigt de structuur (rollen, accountabilities, domeinen, policies). Projecten, metrics, checklists en acties zijn **tactisch/operationeel**, en een rol managet die zelf.

Gevolg, dat als anker geldt voor alles hieronder:

- Een project draait náást de spine, net als de dagpuls. Het gaat niet door G0-G4 en hoort niet in de zware inbox.
- Pas als de **uitkomst** van een project de structuur raakt, valt het terug op de poort of op een activatie.
- Dit is exact het bestaande onderscheid uit STATE.md tussen "kleine operationele plumbing" en "gate/missie-code", nu met een naam erbij.

---

## 1. Het project-primitief

Een project is operationeel, niet-continu, en gescopet.

- **Doel van een discovery-project**: niet alle data binnenhalen, maar de *menukaart* ophalen, wat valt er überhaupt uit te lezen binnen een scope. Daarna stopt de taak. Dat is het verschil tussen doorlopende en eenmalige taken.
- **Scope is onderdeel van de definitie.** Bij een begrensd schema (GSC, Plausible) is de scope impliciet en de menukaart goedkoop. Bij een firehose (beurs, een concurrent) is de scope expliciet, je ontdekt "wat is beschikbaar vóór entiteit X", nooit "wat is beschikbaar in de hele markt".
- **Noochie adviseert, de poort of de mens beslist.** Noochie bepleit welke ontdekte data missie-relevant lijkt om te monitoren. Dat landt als voorstel. Noochie beslist nooit zelf en muteert nooit records via een inhabitant. De firewall blijft heel.

### Vier triggers, twee dom eerst

Eén project-abstractie, vier legitieme triggers. Koppel de trigger los van het werk.

- **Periodiek** (maand/kwartaal): de TimeKeeper, de domme klok. Breid `dag_begint` uit met `maand_begint` / `kwartaal_begint`. De cadans is config, geen code.
- **Human push**: een event vanaf het geauthenticeerde oppervlak (inbox/CLI), net als approvals.
- **Noochie push**: Noochie stelt een project voor via governance.
- **Tension-driven**: een gesenste spanning die naar "dit vraagt een project" triageert.

**Bouw de abstractie zo dat alle vier erop kunnen pluggen, maar bedraad eerst alleen de twee domme** (periodiek + human push). Noochie-push en tension-driven zijn de intelligente triggers, die komen later, zelfde discipline als role-birth: deterministisch eerst.

---

## 2. Metrics: record verklaart, rol logt

Splits structureel van operationeel, meng nooit.

- **Het record verklaart wélke metrics** een rol monitort. Structureel, alleen via governance gewijzigd. (Vereist een veld op `RoleDefinition`, dat nu ontbreekt.)
- **De rol logt de wáárden** in een aparte observatie-store: append-only, getimestampt, per rol/metric. Operationeel, de rol beheert dit zelf.
- Holacracy-regel: elke rol houdt z'n eigen indicatoren-overzicht bij. Het is **van de rol**, niet van het systeem.
- De tijdreeks maakt patroondetectie mogelijk. Dit is het gat dat de analyst al voelt.

De observatie-store gaat nooit in het governance-record. Het record is DNA, de store is logboek.

---

## 3. De gedeelde gap-judgment (A / B / C)

Eén judgment, gevoed door zowel sensing (een accountability-gat) als metric-discovery (een metric-gat). Geen twee parallelle matchers, dat houdt de spine klein.

Twee signaturen uit het bestaande DNA, dat al *mandaat* van *middel* scheidt:

- **Mandaat-signatuur**: purpose + accountabilities + domeinen.
- **Middel-signatuur**: skills.

Drie uitkomsten:

- **A. Mandaat én middel aanwezig** bij een rol → gewoon beginnen met meten. Licht, operationeel, de rol regelt z'n eigen metric.
- **B. Mandaat aanwezig, middel afwezig** → die rol mist een skill. Activatie, mens-gated met per-edit review (een skill is code/API). Het dorp **benoemt** het gat maar kiest **niet** zelf de API of skill, die gok wordt expliciet als gok gelabeld en jij kiest het middel. Fail-closed, want dit is precies waar een model met overtuiging een verouderde of niet-bestaande bron voorstelt.
- **C. Geen rol dekt het mandaat** → role-birth, geboren onbemand.

Dit is de uitbreiding op de al gespecceerde deterministische roster-match: van één dekkingsscore naar twee signaturen. `pairs_sold` valt zo correct op B (de analyst dekt het mandaat, mist het middel), niet op een blind zelf-amendement.

Discipline: deterministisch eerst. De LLM-stap komt er pas op als de term-overlap te grof blijkt, en dan alleen voor de twijfelband rond de drempel, fail-closed (geen antwoord of fout → niet baren).

---

## 4. Het project-grootboek (status & provenance)

De **inhoud** van de menukaart is transient. Het **bestaan en de status** van een project moet inzichtelijk blijven. Dat is een derde store, operationeel, los van het record én los van de inbox.

- **Status is geen beslissing.** Toestanden: gepland / in de wachtrij / lopend / wacht-op-rol-X / klaar, plus een `blocked_on`-veld. Dit hoort niet in de zeldzame zware inbox.
- **Alleen de structurele uitkomst raakt de inbox.** Een lopend of klaar project is status (grootboek). Een uitkomst die een mens vraagt (activatie, governance-voorstel) is een beslissing (inbox). Zo blijft de inbox laag-volume.
- **Bewaar provenance, niet de payload.** Per project: id, eigenaar-rol, scope, trigger-bron, status, timestamps, en een pointer naar de uitkomst (voorstel-id). Niet de menukaart zelf. Je ziet later: "concurrenten-check draaide 1 maart, leverde voorstel X, volgende gepland 1 juni."
- "Wacht-op-rol-X" maakt de fan-out zichtbaar (agent ontdekt kaart → Noochie adviseert → inhabitant past toe). Elke overdracht is een toestandsovergang.
- Dit grootboek is de "proces"-kolom van de geplande cockpit (records / inbox / proces).

Simpel eerst: queued → lopend → klaar, plus `blocked_on`. Dat ene veld accommodeert de fan-out later, maar bouw het meerstaps-orkestratie-grootboek pas als er een echt fan-out-project bestaat.

---

## 5. Volgorde (decompositie, geen big-bang)

1. **Observatie-store.** Los, sensed-nuttig, ontgrendelt patroondetectie.
2. **Eén klein metric-discovery-project** op één al-gekoppelde API (GSC of Plausible). Menukaart van wat meetbaar is → Noochie adviseert → voorstel → mens keurt goed → de dagpuls logt die metrics getimestampt. Geen fan-out, geen nieuwe API, geen entiteit-scoping. Dit bewijst de hele keten end-to-end.
3. **Project-grootboek** (simpel) + TimeKeeper `maand_begint`/`kwartaal_begint` + human-push trigger.
4. **Generaliseren naar fan-out** over meerdere agents.
5. **Entiteit-gescopete zwaargewichten** (beurs, concurrenten), met een gecureerde entiteitenlijst die zichzelf op een kwartaal-project onderhoudt ("zijn er nieuwe bijgekomen, zijn er veranderingen"). Hoogste data-volume én hoogste oordeel, dus laatste.
6. **Intelligente triggers** (Noochie-push, tension-driven) + de LLM-laag op de gap-judgment, fail-closed, alleen de twijfelband.

---

## 6. WIP-limieten & backpressure

Een autonoom systeem dat zelf werk genereert (sensing → projecten, proposals) kan overlopen. WIP-limieten zijn het tegengif. Twee lagen, conform "dom eerst".

**Dom plafond (nu gebouwd):** een harde circuit-breaker op het grootboek. `FUTURE_MAX` open projecten, `RUNNING_MAX` lopende (blocked telt niet als lopend, anders deadlock). Boven het plafond: weiger en log, fail-closed. Geen afstelling nodig, het is een veiligheidsdak, geen doorstroom-knop.

**Slimme WIP (later, bij observeerbaarheid + fan-out + prioriteit):** drie banen, elk met een limiet die de bron stil maakt als hij vol zit. Backpressure op elke baan die een bottleneck voedt.

- Lopende baan: WIP-limiet op running, blocked bezet geen slot.
- Future-bord: limiet op queued. Bij vol beslist prioriteit (Missie > Policy > Strategy > Goal, broker plasticvrij > plantbased > vegan) wat blijft, de rest valt weg.
- Per-overdracht: max 1 openstaand verzoek naar dezelfde rol. Bijt pas bij fan-out.
- Inbox: bij veel wachtende activaties (B/C-gevallen) schakelt het sensen van nieuwe activatie-kandidaten terug.

Twee regels die de slimme laag kloppend maken:

- **Stop niet met sensen, stop met acteren.** Blijf zien, queue alleen niet boven capaciteit. Anders ga je blind voor nieuwe signalen.
- **Droppen bij vol is veilig omdat sensoren herhalen.** Een gat dat nu wegvalt, sense je volgende cyclus opnieuw zodra er ruimte is. Zelfde herhalings-eigenschap als de role-birth-poort.

---

## Principes die voor deze upgrade niet mogen driften

- Project = operationeel. Niet door G0-G4, niet in de inbox. Alleen de structurele uitkomst is gated.
- Noochie adviseert, beslist nooit, muteert nooit records via een inhabitant.
- Metric-waarden nooit in het record. Record verklaart, rol logt.
- Menukaart transient (inhoud weg), grootboek persistent (status + provenance).
- Scope-first, nooit "haal op wat je kunt". Geen overproductie, ook niet van data.
- Eén gedeelde gap-judgment voor accountability-gaten én metric-gaten, niet twee.
- Deterministisch eerst, LLM pas op de twijfelband, fail-closed.
- Niet vooruitbouwen: fan-out-grootboek pas bij fan-out, entiteit-scoping pas bij een firehose-project.
- WIP: dom plafond nu (fail-closed circuit-breaker), slimme WIP (prioriteit-eviction, backpressure, per-overdracht, inbox) pas bij observeerbaarheid en fan-out.

---

## Open knoppen (genoteerd, niet beslist)

- De drempel van de roster-match is empirisch. Stel 'm bij ná het zien draaien, niet vooraf.
- Welke intelligente trigger eerst (Noochie-push of tension-driven) blijft open tot de domme triggers staan.
- De WIP-getallen (FUTURE_MAX, RUNNING_MAX, en de slimme varianten) stel je af nadat je het bord hebt zien vollopen, niet vooraf.
