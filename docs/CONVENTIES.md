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

## Verwerken is werk routeren — kennis schrijven is iets anders

Drie schermen laten een mens een spanning verwerken: de **inbox**, het **werkoverleg** en de
**wall**. Ze delen één mechaniek en bieden daarom dezelfde drie uitkomsten:

| uitkomst | waar het landt |
|---|---|
| **Actie** | `route_werk` — mens-vervulde rol → inbox, AI-vervulde rol → project |
| **Project** | de projectwizard |
| **Roloverleg** | de governance-agenda |

Een vierde bak op één scherm en niet op de andere is drift. Dat is 29 aug 2026 opgeruimd:
'informatie delen' stond op alle drie en was op alle drie vrijwel ongebruikt (werkoverleg 0 van 9,
inbox 6 pings van 42, wall 1 in de hele historie). Hij is bovendien niet verloren — een mededeling
aan iemand is een **actie met `@`**: dezelfde landing, maar als werk dat terugkomt in plaats van een
los bericht dat daarna nergens meer opduikt.

`tests/test_verwerk_uitkomsten_bevroren.py` bevriest de drie op alle drie de schermen. Heropenen
mag, maar dan als besluit met een reden — niet als bijvangst van een refactor.

### `note` hoort er NIET bij, en dat is geen vergeten hoekje

De wall heeft daarnaast een `note`-uitkomst. Die blijft, met opzet, en hij hoort **niet** in de
ratchet en **niet** in de drie:

> `note` schrijft **kennis** bij een rol. De drie verwerk-uitkomsten routeren **werk** uit een
> spanning. Dat zijn twee concerns — kennisbank versus werkroutering — en die vegen we niet samen.

Dit staat hier omdat de volgende lezer precies de verkeerde conclusie kan trekken: "de wall heeft er
vier en de andere twee drie, dus die vierde moet weg". Dat is dezelfde redenering die bij
'informatie delen' wél klopte en hier niet. Het verschil zit niet in het aantal maar in wat het
ding dóét.

**Open ontwerppunt, nu geen actie.** Juist omdat het een kennis-schrijf is en geen verwerk-uitkomst,
hoort `note` eigenlijk een eigen affordance te zijn en geen vierde peer in dezelfde kiezer — daar
suggereert hij gelijkwaardigheid die er niet is. Er is op prod nul gebruik, dus er is niets kapot en
niets haastigs. Pak dit bewust op zodra iemand `note` gaat gebruiken, niet per ongeluk bij een
opruiming.

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
| `tests/test_verwerk_uitkomsten_bevroren.py` | een vierde verwerk-uitkomst op één van de drie schermen |

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

Elke ratchet is **monotoon dalend**: het plafond mag omlaag als je schuld opruimt, nooit omhoog.
Een nieuwe mechaniek toevoegen mag — maar dan met een expliciete regel in de lijst en een reden,
niet stilzwijgend.
