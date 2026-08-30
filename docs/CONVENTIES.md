# Conventies — één mechaniek per ding

> **Zoek eerst de bestaande mechaniek voordat je een nieuwe vorm, store of formulier bouwt.**
>
> Bijna elke bug van 28 augustus 2026 was een tweede mechaniek voor iets dat al bestond: een tweede
> terug-URL in een fragment, een tweede plek waar een actie landde, een tweede telling van hetzelfde
> overleg. Ze faalden allemaal stil — geen foutmelding, wél verkeerde data. Een tweede vorm van
> hetzelfde is geen extra functie; het is een divergentie die op zijn moment wacht.

## De mechanieken

| ding | de mechaniek | waar |
|---|---|---|
| **vangen** (typ-en-Enter, één regel) | `form[data-qa-frag]` + de wachtrij in `static/nooch.js` | `views/vangst.py::_vang_form` |
| **verwerken** (spanning → uitkomsten) | de gedeelde vang-en-verwerk-component | `views/vangst.py::render_vangst_frag` |
| **fragment-swap** (een stuk pagina vervangt zichzelf) | `NV.swap` + `data-nv-mirror(-html)` | `static/nooch.js` |
| **projectcreatie** (door een mens) | de wizard | `views/wizard.py` + `/project/nieuw` |
| **project-checklist** (stappen ín een project) | de checklist op het project zelf | `projects.py::checklist_add` / `check_add` |
| **meldingen aan een mens** | de inbox | `notifications.py::NotifStore` + `views/inbox.py` |
| **bewijs / herkomst** | de Kroniek, append-only | `evidence_ledger.py` |
| **overleg-archief** | het snapshot met de punten erin | `werkoverleg.py::_snapshot` |

Twee dingen die op elkaar lijken maar het níét zijn — verwar ze niet en voeg ze niet samen:

- **`ChecklistStore`** (`checklists.json`) is de *terugkerende cirkel-checklist* uit stap 2 van het
  werkoverleg. Dat is iets anders dan de checklist ván een project.
- **`AITaskStore`** is werk dat een AI-rol uitvoert; de **inbox** is een melding aan een mens. Een
  AI-vervulde rol leest de NotifStore nooit — daar werk neerleggen als bericht is het stil
  verliezen. Zie de dead-letter-guard in `_act_vangst_uitkomst`.

Er zijn **drie postbussen**, en ze zijn geen variant van elkaar:

| klasse | van wie | waarvoor |
|---|---|---|
| `NotifStore` | een **mens** | meldingen, spanningen, acties uit een overleg |
| `Inbox` | een **inwoner** (thread) | toegewezen werk dat áf moet — de betrouwbaarheidskant van de bus |
| `HumanInbox` | de **founder**, lokaal en geauthenticeerd | approvals: governance-escalaties en rol-activaties |

Een vierde is wél een tweede postbus: dan mist iemand de helft van zijn werk en merkt niemand het.

## Fail-open op AI

Een AI-stap is een **bonus, geen poort**. De mens moet zijn handeling altijd kunnen afmaken zonder
model: met een overslaan-knop die er meteen staat (ook tijdens het wachten), een timeout, en een
lege uitkomst met een nette melding in plaats van een hangend scherm. Zie `views/wizard.py`
(`PLAN_TIMEOUT_MS`, `Skip this step`).

## De poortjes

"Modulair, geen redundantie" is pas een regel als een test omvalt. Deze bewaken het:

| test | valt om bij |
|---|---|
| `tests/test_conventies_ratchet.py` | een tweede store (dus ook een tweede checklist-store of meldingskanaal), of een tweede projectcreatie-**vorm** |
| `tests/test_ui_fragment_mechaniek.py` | een tweede fragment-swap of een eigen kopie van de vang-wachtrij |
| `tests/test_actie_routing_ratchet.py` | werk uit een overleg dat weer op een geraden project belandt |
| `tests/test_overleg_archief_ratchet.py` | een overleg-archief dat de punten niet bewaart |

### Een poort bewaakt alleen wat hij telt

De projectcreatie-ratchet telde eerst één actienaam (`proj_add`). Daarna bleef er een formulier op
het projectenbord staan dat de wizard opende maar er precies uitzag als een tweede creatie-vorm:
twee tekstvelden en een groene knop. De telling zei nul; het scherm zei iets anders, en een lezer
concludeerde terecht dat er nog een tweede deur was.

Twee lessen, allebei duurder dan ze klinken:

1. **Tel de vorm, niet de naam.** De ratchet telt nu het veld waarmee je een project beschrijft bij
   het aanmaken (`done_when`), niet alleen de oude actie. Een volgende poging met andere veldnamen
   valt daarmee alsnog op.
2. **Een ingang is een deur, geen formulier.** Velden die er als een creatie-vorm uitzien maar
   stiekem doorsturen zijn erger dan geen velden: ze beloven iets anders dan ze doen. Typen doe je
   in de wizard, in het veld dat het project ook echt aanmaakt.

Zelfde familie als de postbus-blinde-vlek hierboven: de aanname was "er zijn er twee", de telling
wees de derde aan.

### Handhaving vereist waarneembaarheid

De meta-les onder de twee hierboven, en onder de afslank-poort. Drie keer dezelfde vorm:

| regel | wat er ontbrak | gevolg |
|---|---|---|
| "een tweede projectcreatie-vorm mag niet" | de poort telde een naam, niet de vorm | het formulier stond er gewoon, telling nul |
| "er zijn drie postbussen" | niets telde de klassen | de aanname was twee |
| "een rol slapen leggen mag niet stilletjes werk breken" | niemand keek wat die rol droeg | ingetrokken skill, teruggezaaid door `seeds.py` |
| "nooit andermans woorden herschrijven" | het record schreef `by="dialoog"` — de plek, niet de auteur | de poort kón niet zien dat een mens typte |

**Een principe dat het record niet kan waarnemen, handhaaft niets.** Een regel is pas een regel als
er een feit in de data staat waaraan je hem kunt toetsen; anders is het een voornemen dat toevallig
in een docstring belandde. Twee gevolgen bij elke nieuwe regel:

1. **Leg het feit vast op het pad dat het weet.** Het schrijfpad weet of een mens zat te typen; die
   kennis verdwijnt zodra er alleen een string overblijft. Vandaar `notifications.MENS_GETYPT` —
   het pad merkt zijn eigen tekst, in plaats van dat de poort de afzender moet raden.
2. **Het pad wint van de afleiding.** Herkenning-achteraf faalt precies bij de randgevallen: `zelf`,
   `dialoog`, een uitgelogde gebruiker. Wie de regel op herkenning bouwt, schendt hem bij de mensen
   die hij het minst kent.

### Tonen is zwakker dan wegnemen

De poort uit `afslank_afhankelijkheden.py` is een **vangnet, geen eerste keus.** Hij bestond omdat
`facilitator` slapend werd gelegd terwijl die rol de dagbel luidde; hij zou zo'n snit voortaan tonen
vóór hij gebeurt. Maar een waarschuwing die je mag wegklikken houdt geen systeem overeind — en de
echte fout was niet dat het onzichtbaar was, maar dat de hartslag überhaupt aan een rol hing.

De volgorde is dus:

1. **Kun je ontkoppelen, ontkoppel dan.** De cadans verhuisde naar `dagcyclus.py`: geen rol, geen
   record, geen `CLASS_MAP`. De afhankelijkheid bestaat niet meer, dus valt er ook niets te
   waarschuwen. De test die de koppeling aantoonde, bewijst nu haar afwezigheid.
2. **Bewaak wat je niet kunt weghalen.** `pulse_completed` komt van `website_watcher` en dat is
   terecht rolwerk. Daar heeft de poort tanden, want daar hangt echt werk aan een echte rol.
3. **Wat je niet kunt loskoppelen, moet je kunnen horen.** `once()` printte bij uitval
   `Field Note: None` — dat leest als een lege dag, niet als een uitgevallen puls. `None` hoor je
   niet; een melding mét de naam van de stilgevallen rol wel.

Zelfde beweging als hierboven, één trede hoger: waarneembaarheid maakt een regel handhaafbaar,
maar de regel niet nodig hebben is beter dan hem kunnen handhaven.

Elke ratchet is **monotoon dalend**: het plafond mag omlaag als je schuld opruimt, nooit omhoog.
Een nieuwe mechaniek toevoegen mag — maar dan met een expliciete regel in de lijst en een reden,
niet stilzwijgend.
