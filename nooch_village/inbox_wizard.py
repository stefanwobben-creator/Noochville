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
        "label": "Info delen, halen of vastleggen",
        "options": [
            {"q": "Moet het besproken worden?", "otype": "tactical",
             "label": "Op het werkoverleg zetten", "ready": False},
            {"q": "Wil je het vastleggen?", "otype": "note", "label": "Note toevoegen", "ready": True},
        ],
    },
    {
        "key": "self",
        "label": "Zelf iets doen",
        "options": [
            {"q": "Is de volgende stap simpel en helder?", "otype": "action",
             "label": "Actie toevoegen", "ready": True},
            {"q": "Is het resultaat complexer?", "otype": "project",
             "label": "Project toevoegen", "ready": True},
            {"q": "Wil je een rol wijzigen?", "otype": "roloverleg",
             "label": "Naar roloverleg", "ready": True},
        ],
    },
    {
        "key": "other",
        "label": "Iemand anders iets laten doen",
        "options": [
            {"q": "Eenmalig verzoek dat besproken moet worden?", "otype": "tactical",
             "label": "Op het werkoverleg zetten", "ready": False},
            {"q": "Een concrete stap voor die rol?", "otype": "action",
             "label": "Actie voor die rol", "ready": True},
            {"q": "Verwacht je het structureel?", "otype": "roloverleg",
             "label": "Naar roloverleg", "ready": True},
        ],
    },
]

# 'Niks nodig' is geen aparte intentie meer: sluit je met nul uitkomsten via 'Klaar met deze spanning',
# dan legt de handler zelf 'geen uitkomst' vast in het record. Eén sluitmodel.

# Leesbaar label per uitkomst-type (voor het verwerk-record en de historie).
OTYPE_LABEL = {"note": "note", "action": "actie", "project": "project",
               "roloverleg": "roloverleg-punt", "tactical": "werkoverleg-punt",
               "none": "afgehandeld zonder uitkomst"}


def intent_of(otype: str) -> str:
    """De intentie-key waar een uitkomst-type onder valt (eerste match). Voor het record."""
    for it in INTENTS:
        for op in it["options"]:
            if op["otype"] == otype:
                return it["key"]
    return ""
