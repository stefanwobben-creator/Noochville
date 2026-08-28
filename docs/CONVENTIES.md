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
| `tests/test_conventies_ratchet.py` | een tweede store (dus ook een tweede checklist-store of meldingskanaal), of een tweede projectcreatie-formulier |
| `tests/test_ui_fragment_mechaniek.py` | een tweede fragment-swap of een eigen kopie van de vang-wachtrij |
| `tests/test_actie_routing_ratchet.py` | werk uit een overleg dat weer op een geraden project belandt |
| `tests/test_overleg_archief_ratchet.py` | een overleg-archief dat de punten niet bewaart |

Elke ratchet is **monotoon dalend**: het plafond mag omlaag als je schuld opruimt, nooit omhoog.
Een nieuwe mechaniek toevoegen mag — maar dan met een expliciete regel in de lijst en een reden,
niet stilzwijgend.
