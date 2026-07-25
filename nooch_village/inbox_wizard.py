"""De verwerk-wizard van de inbox, declaratief: intentie → diagnostische vraag → uitkomst.

Eén bron van waarheid voor zowel de mens-UI (de twee-panelen-verwerk-pagina) als straks de autonome
AI-triage. Zo lopen mens en AI dezelfde beslisboom en landt elke keuze in hetzelfde verwerk-record.

Model (naar GlassFrog's 'What do you need?'): je kiest eerst je INTENTIE, en per intentie staat er bij
elke UITKOMST een korte vraag die je helpt de juiste te kiezen. Een spanning kan meerdere uitkomsten
opleveren (stapelen); pas 'klaar' sluit het item.

`otype` verwijst naar de uitkomst-maker (dezelfde `_outcome_*`-helpers als de wall):
  note · action · project · roloverleg · tactical · none (afhandelen zonder uitkomst).
`ready=False` markeert een uitkomst die nog niet gebouwd is (dan toont de UI 'm uitgeschakeld).
"""
from __future__ import annotations

# Elke intentie: key, label, en een lijst uitkomsten {q (de vraag), otype, label, ready}.
INTENTS = [
    {
        "key": "info",
        "label": "Share, get or record info",
        "options": [
            {"q": "Ping someone?", "otype": "ping", "label": "Ping someone", "ready": True},
            {"q": "Does it need discussing?", "otype": "tactical",
             "label": "Put on the tactical meeting", "ready": False},
        ],
    },
    {
        "key": "self",
        "label": "Do something yourself",
        "options": [
            {"q": "Is the next step simple and clear?", "otype": "action",
             "label": "Add action", "ready": True},
            {"q": "Is the result more complex?", "otype": "project",
             "label": "Add project", "ready": True},
            {"q": "Want to change a role?", "otype": "roloverleg",
             "label": "To governance meeting", "ready": True},
        ],
    },
    {
        "key": "other",
        "label": "Have someone else do something",
        "options": [
            {"q": "One-off request that needs discussing?", "otype": "tactical",
             "label": "Put on the tactical meeting", "ready": False},
            {"q": "A concrete step for that role?", "otype": "action",
             "label": "Action for that role", "ready": True},
            {"q": "Do you expect it structurally?", "otype": "roloverleg",
             "label": "To governance meeting", "ready": True},
        ],
    },
]

# 'Niks nodig' is geen aparte intentie meer: sluit je met nul uitkomsten via 'Klaar met deze spanning',
# dan legt de handler zelf 'geen uitkomst' vast in het record. Eén sluitmodel.

# Leesbaar label per uitkomst-type (voor het verwerk-record en de historie).
OTYPE_LABEL = {"ping": "ping", "note": "note", "action": "action", "project": "project",
               "roloverleg": "governance meeting item", "tactical": "tactical meeting item",
               "none": "handled without outcome"}


def intent_of(otype: str) -> str:
    """De intentie-key waar een uitkomst-type onder valt (eerste match). Voor het record."""
    for it in INTENTS:
        for op in it["options"]:
            if op["otype"] == otype:
                return it["key"]
    return ""
