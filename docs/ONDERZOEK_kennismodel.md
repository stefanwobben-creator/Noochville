# Onderzoek — welk kennismodel voor NoochVille? (signaal/bevinding/kader vs Toulmin/Dung)

Doel van de kennislaag (vastgelegd met The Source): **kansen en gaten ruiken** (gap-detectie),
licht in onderhoud, en onbreekbaar. Verdedigbaarheid is secundair (mag later).

Methode: geen dynamiek-Monte-Carlo (dat test het model tegen zijn eigen aannames), maar een
**ontologie-stresstest** tegen echte data (196 notesstore-kaartjes) + ~75 bewust moeilijke
synthetische claims. Reproduceerbaar: `python tools/knowledge_model_experiment.py`.

## Wat we vonden

### 1. Het 3-type model (signaal/bevinding/kader) houdt stand voor EXTERNE kennis
Op de gecontroleerde synthetische set valt 83% netjes in één van de drie types (signaal 43%,
bevinding 20%, kader 20%), 0% ambigu. De drie naden snijden dus goed voor trends, empirie en
regelgeving.

### 2. Maar twee soorten claims passen er principieel niet in (de "ongeziene" categorie)
De breekgevallen waren niet willekeurig maar **systematisch**:

- **Standpunten / normen / waarden** (13 van de 75): "een merk hoort eerlijk te zijn", "moreel
  beter om on-demand te produceren", "mensen die vegan zijn zijn bewuster van alles". Dit is geen
  signaal, bevinding óf kader. Het wordt *beweerd*, niet *bewezen*. Voor een missiegedreven merk
  is dit juist een belangrijke soort: de eigen positie van Nooch. Die hoort een eigen plek te
  hebben, niet op de bewijs-as gedwongen te worden (anders krijg je schijn-bewijs voor een mening).
- **Definities** (4 van de 75): "vegan betekent afwezigheid van dierlijke grondstoffen",
  "biobased betekent hernieuwbare bron". Dit zijn afspraken over taal, geen feiten of signalen.
  NoochVille **heeft hier al een huis voor**: het Lexicon. Definities horen daar, niet in de
  notesstore. Dat lost ze schoon op zonder nieuwe categorie.

### 3. "reported" is de grote grijze zone in de ECHTE data
158 van de 196 kaartjes hebben een `evidence_type`; daarvan is **114 "reported"** (een bron meldt
iets), 42 "measured", 2 "claimed". "reported" zegt *dat* een bron iets meldt, niet *welke soort*
het is — het kan een signaal of een bevinding zijn. Dat is waarom een naïeve classifier 72% van de
echte kaartjes "onbeslist" liet: het echte werk zit in het onderscheiden van gemeld-signaal vs
gemeld-bewijs. Dat is precies een taak voor een agent/curator, niet voor een vast veld.

### 4. Gap-detectie werkt mechanisch
32 signalen vs 15 bevindingen in de synthetische set. De regel is simpel en zonder admin: **een
signaal zonder gelinkte bevinding = een kans/gat** (de satelliet die naar het centrum getrokken
moet worden). Dit volgt rechtstreeks uit type + links die er al zijn; geen extra invoer nodig.

## Het model afgezet tegen de alternatieven

| Model | Wat het doet | Admin-last | Past bij "gaten ruiken"? |
|-------|--------------|-----------|--------------------------|
| **signaal/bevinding/kader (+standpunt)** | rol van de claim + bewijskracht via `evidence_type` | laag (1 type-veld, rest al aanwezig) | **ja, direct** (signaal zonder bevinding = gat) |
| **Toulmin** (claim, grounds, warrant, qualifier, rebuttal) | structuur van één argument | hoog (warrant+rebuttal per kaart invullen) | nee — overkill voor ruiken; goed voor verdedigen |
| **Defeasible logic** | regels die gelden "tenzij" | hoog (regels formaliseren) | nee — breekt bij zachte, heterogene claims |
| **Dung-argumentatie** | claims + aanval-relaties, bereken wat overeind blijft | midden (aanval-edges nodig) | nee voor ruiken; **ja voor verdedigen** (later) |

Belangrijke vondst in de code: het `Insight`-model heeft **al** Toulmin-velden (`warrant`,
`qualifier`, `rebuttal`) — maar ze zijn 0/196 gevuld. Iemand begon ooit Toulmin en liet het liggen.
Dat is goed nieuws: we kunnen er één licht ding van lenen (zie hieronder) zonder iets te bouwen.

## Conclusie en voorstel (licht + onbreekbaar)

**Kies het signaal/bevinding/kader-model, met één toevoeging en één verplaatsing:**

1. **Vier types, niet drie:** `signaal`, `bevinding`, `kader`, **`standpunt`** (de eigen positie/
   waarde van Nooch — beweerd, niet bewezen). Dit dekt de systematische breukgevallen.
2. **Definities → Lexicon** (bestaat al). Niet in de notesstore.
3. **Sterkte wordt berekend, niet ingevoerd:** uit `evidence_type` (measured > reported > claimed)
   × aantal onafhankelijke bevindingen die de claim steunen (via links) − tegenspraak. Geen
   handmatig opgehoogd cijfer (lost de "grounding_count = altijd 1"-dood op).
4. **Onbreekbaar = elke claim heeft een huis:** wat in geen type valt → default `signaal` met
   status "onbeslist" → belandt in de mens-review (zoals de keyword-review). Crasht nooit, vervuilt
   nooit stil.
5. **Eén ding van Toulmin lenen (optioneel, al in het schema):** `rebuttal` ("wat zou dit
   onderuithalen") als optioneel veld. Daarmee is een claim later verdedigbaar (jouw secundaire
   doel) zonder nu admin-last. Dung komt pas in beeld als verdedigen primair wordt; een
   "spreekt-tegen"-link is dan precies een Dung-aanval-edge op dezelfde graaf die er al is.

**Admin-last:** één keuzeveld (type) per kaart; de rest (`evidence_type`, links, status) bestaat al.
**Gap-detectie:** gratis afgeleid (signaal zonder bevinding-link).
**Overzicht-laag (vraag van eerder):** sorteer niet op een dood getal maar op (a) sterkste claims
(berekende sterkte), (b) signalen-zonder-bevinding (de gaten/kansen), (c) betwiste claims.

## Vastgelegde besluiten (na ontwerpdialoog)

### Soort vs sterkte (de kern)
Twee dingen die los van elkaar staan:

- **Soort** (signaal / bevinding / kader / standpunt) verandert NOOIT. Een signaal wordt geen
  bevinding door ouder te worden; een mening wordt geen feit. De soorten gaan over verschillende
  werelden (signaal = aandacht/cultuur, bevinding = de wereld, kader = norm, standpunt = wat wij
  beweren). Ze door elkaar laten lopen zou betekenen dat opinie zich kan vermommen als bewijs
  (de bevestigingsbias-val) en je je audittrail verliest.
- **Sterkte** binnen één soort evolueert WEL. Een bevinding groeit: `ondersteund` (1 bron) →
  `bevestigd` (meerdere onafhankelijke) → `geverifieerd` (haalt de lat). Een standpunt groeit in
  publiceerbaarheid: `positie` → `onderbouwd` → `publiceerbaar`.

Een "bewezen claim" is dus GEEN één kaartje dat van vorm verandert, maar een ketting van gelinkte
kaartjes, elk met een eigen sterkte-evolutie:

```
SIGNAAL  → roept vraag op →  BEVINDING  → onderbouwt →  STANDPUNT
(blijft signaal)             (groeit in sterkte)        (wordt publiceerbaar zodra de
                                  ↑ gelinkt aan          bevinding geverifieerd is
                                  KADER (de lat)         én aan het kader voldoet)
```

### Autonome promotie, mét validiteitscheck (geen ja-knikker)
Een claim mag autonoom naar `geverifieerd` springen, MAAR alleen als een automatische, objectief
toetsbare controle slaagt. De mens wordt zo bewaard voor de twijfelgevallen, niet voor het stempelen
van routinewerk. De automatische validiteitscheck (startdefinitie, verfijnbaar):

1. ≥2 **onafhankelijke** bevindingen steunen de claim (onafhankelijk = niet naar elkaar verwijzend), en
2. ≥1 daarvan is `evidence_type = measured`, en
3. er is **geen** tegensprekend kaartje (geen `betwist`).

Slaagt de check → systeem promoot zelf. Faalt iets (één bron, alleen `claimed`/`reported`, of
tegenspraak) → géén autopromotie, het komt bij de mens als een ECHTE afweging (geen vinkje).

### Standpunt: ongescoord, maar koppelbaar
Een `standpunt` krijgt geen eigen bewijs-sterkte (een waarde is geen bewijs). Het ERFT sterkte van de
bevindingen die eraan gelinkt zijn. Zo zie je welke standpunten onderbouwd zijn en welke pure
overtuiging (ook een soort gat). De publiceer-beslissing onder een kader blijft mens-gated (Legal
signaleert, de mens beslist) — dit is bewust GEEN autopromotie, want het is consequent en juridisch.

### Kader draagt zijn eigen drempel
Hoeveel bewijs "genoeg" is, verschilt per regel (EN13432 eist een gemeten labtest; een vrijwillig
keurmerk neemt soms een fabrikantverklaring). De lat staat daarom als veld/tekst op het kader-kaartje
zelf, niet hardgecodeerd. Mag in v1 simpel beginnen met één defaultdrempel en later verfijnen.

## De Legal-rol (signaleert, blokkeert niet)
Een nieuwe rol, geboren via governance, bemenst zodra code + de bestaande `nooch-legal`-skill
geregistreerd zijn (born-vs-manned).

- **Capaciteit (rol):** bezit het **kader-domein** in de kennislaag (cureert de kader-kaartjes:
  EN13432, Green Claims, BRL, ISO/ASTM). Lezen vrij, cureren exclusief — zelfde domeinregel als de
  Librarian met de bibliotheek. "Alle legal kennis" = exact de verzameling kader-kaartjes, niet meer
  (fail-closed: een leeg kader = "ik weet het hier niet", geen orakel).
- **Wat hij doet:** doorlopende accountability die de compliance-loop bewaakt. Zodra een standpunt
  aan een kader hangt zonder voldoende bevinding → hangt hij een **publiceer-risico-signaal** in de
  focus-inbox (claim + geschonden kader + ontbrekend bewijs). Stolt via hetzelfde experiment-patroon.
- **Grenzen (3x niet, 1x wel):** beslist NIET over waarheid (dat doet het bewijs), schrijft GEEN
  copy (dat doet nooch-copy), blokkeert NOOIT publicatie (dat doet de mens). Hij signaleert alleen
  het gat tussen claim en bewijs, gemeten tegen een kader.
- Optioneel: een inwoner met karakter (nuchtere, precieze ISTJ-compliance-stem).

## Status
Ontworpen en op papier getest (196 echte kaartjes + 100 synthetische claims + het
biodegradability-rapport als integrale casus). Nog niets gebouwd. Volgende stap: in kleine,
toetsbare brokken bouwen, net als bij het prikbord.
