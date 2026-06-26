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

## Open vraag voor de bouwfase
Moet `standpunt` ook een berekende "sterkte" krijgen (bv. hoe consistent het met de missie is), of
blijft het bewust ongescoord (een waarde is geen bewijs)? Mijn voorstel: ongescoord, maar wél
koppelbaar aan bevindingen die het ondersteunen (zo zie je welke waarden onderbouwd zijn en welke
puur overtuiging — ook een soort gat).
