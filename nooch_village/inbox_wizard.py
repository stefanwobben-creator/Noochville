"""De verwerk-flows van de inbox: wat kun je met een spanning doen?

Eén bron van waarheid voor de mens-UI (de twee-panelen-verwerk-pagina) en straks de autonome
AI-triage, zodat mens en AI dezelfde keuzes zien en in hetzelfde verwerk-record landen.

WAT HIER VERANDERDE, 29 aug 2026. Dit was een intentie-boom naar GlassFrog's "What do you need?":
drie abstracte bakken ('Share, get or record info' · 'Do something yourself' · 'Have someone else do
something'), elk met diagnostische vragen eronder. Gemeten over de hele historie op prod:

    560 inbox-items · 42 met een uitkomst (7,5%) · daarvan 26x 'niks nodig'
    project 3x · ping 6x · action 0x

Nul keer 'action', en 26 van de 42 uitkomsten was "ik doe hier niets mee". Een menu dat je eerst
vraagt te classificeren wat voor soort behoefte je hebt, vóór je iets concreets mag doen, kost een
denkstap die niemand wil zetten — dus verdween de spanning meestal ongebruikt.

Nu twee concrete handelingen, en het LABEL draagt de pedagogie:

    Actie   — komt terug in de inbox
    Project — voor een rol die je zelf vervult

Zo leert een nieuweling roldenken al doende, aan het verschil tussen "dit is één handeling" en "dit
is werk dat een rol draagt", in plaats van uit abstracte categorieën.

ÉÉN MECHANIEK, TWEE INGANGEN (docs/CONVENTIES.md). De inbox krijgt GEEN eigen actie- of
projectvorm: een actie loopt via `cockpit2.route_werk` — dezelfde routing als het werkoverleg en de
wizard — en Project opent de bestaande projectwizard. Een gekoppelde actie wordt een item in de
project-checklist die het project al heeft. Dit is dezelfde consolidatie als bij het projectbord.

WAT ER WEGGING: 'Share, get or record info'. Gemeten 6 keer gebruikt, allemaal als `ping` (een
bericht naar een rol) — niet nul, maar wel de minst gebruikte weg, en hij is nu opgegaan in iets
beters: een actie met `@rol` doet hetzelfde én komt bij de ontvanger terug als werk in plaats van
als losse mededeling. `_outcome_info` blijft bestaan voor de wall en het werkoverleg; daar is niets
aan veranderd.

WAT ER BLEEF: de governance-/roloverlegroute, ongewijzigd, tot flow 3 apart ontworpen is.
"""
from __future__ import annotations

# De flows, in de volgorde waarin ze op het scherm staan. `regel` is de één-regel-uitleg die de
# pedagogie draagt — hij staat naast het label, niet in een tooltip: uitleg die je moet zoeken is
# geen uitleg.
FLOWS = [
    {"key": "action", "otype": "action", "label": "Action",
     "regel": "one step — comes back in the inbox",
     "hulp": "Who does it? Default is you. Type @ for another role or person."},
    {"key": "project", "otype": "project", "label": "Project",
     "regel": "for a role you fill yourself",
     "hulp": "Opens the project wizard with this tension prefilled."},
]

# De governance-route staat er nog precies zoals hij stond. Bewust NIET meegenomen in de
# herontwerp-ronde: flow 3 ontwerpen we apart, en tot die tijd mag er niets breken.
GOVERNANCE = {"key": "governance", "otype": "roloverleg", "label": "To governance meeting",
              "regel": "to change a role — unchanged for now"}

# Leesbaar label per uitkomst-type (voor het verwerk-record en de historie). `ping`, `note`, `info`
# en `tactical` staan er nog in omdat OUDE records ze dragen: een historie die zijn eigen labels niet
# meer kan lezen is geen historie.
OTYPE_LABEL = {"action": "action", "project": "project", "roloverleg": "governance meeting item",
               "none": "handled without outcome",
               "ping": "ping", "note": "note", "tactical": "tactical meeting item"}

_INTENT_VAN = {"action": "action", "project": "project", "roloverleg": "governance",
               # historisch, voor het teruglezen van bestaande verwerk-records
               "ping": "info", "note": "info", "tactical": "info", "none": "none"}


def intent_of(otype: str) -> str:
    """De flow-key waar een uitkomst-type onder valt. Voor het verwerk-record en de historie."""
    return _INTENT_VAN.get(otype, "")
