"""Zelfverificatie van de werklijst: staat die claim er nog?

De statusvraag was tot nu toe onbeantwoordbaar — een mens zette een vinkje en de tool geloofde
hem. Deze module toetst elk werklijst-item tegen de tekst die de wekelijkse scan ophaalde.

De grens is scherp en bewust: dit is **byte-vergelijking, geen interpretatie**. Staat de
claim-frase nog letterlijk in de gescande tekst, of niet. Alles wat oordeel vraagt — "is deze
herformulering goed genoeg?" — blijft mensenwerk.

Drie uitkomsten, en één die net zo belangrijk is als de andere twee: een item dat op een pagina
buiten de vaste scan-set staat kan NIET geverifieerd worden. Dat zeggen we dan ook, in plaats
van een status te tonen die betrouwbaarheid suggereert.
"""
from __future__ import annotations

import time

from nooch_village import claims_db
from nooch_village.claims_board import normaliseer

# Handmatige statussen die de mens bewust heeft gezet. Die overschrijft de scan alleen als hij
# het tegendeel wáárneemt (regressie) — niet om "opgelost" te herbevestigen.
_MENS_OPGELOST = ("live", "opgelost")


def claim_frases(item: dict) -> list[str]:
    """De frases waarop we dit werklijst-item herkennen: alles tussen aanhalingstekens in de
    claim-omschrijving. De werklijst schrijft «"100% Planet-Safe" — homepage, sitewide»; de
    frase tussen de curly quotes is wat er letterlijk op de site hoort te staan."""
    import re
    claim = item.get("claim") or ""
    frases = re.findall(r"[“\"']([^“”\"']{4,})[”\"']", claim)
    return [normaliseer(f) for f in frases if normaliseer(f)]


def verifieer(db: dict, paginateksten: dict[str, str], nu: float | None = None) -> list[dict]:
    """Bepaal per werklijst-item wat de gescande pagina's laten zien.

    `paginateksten` is {label: tekst} van de pagina's die deze run gelukt zijn. Geeft een lijst
    voorstellen terug: `{nr, van, naar, reden, frase}` — alleen voor items die écht veranderen.
    Schrijft zelf niets; de aanroeper beslist en slaat op."""
    nu = nu or time.time()
    datum = time.strftime("%Y-%m-%d", time.localtime(nu))
    alles = normaliseer(" ".join(paginateksten.values()))
    voorstellen = []
    for item in db.get("werklijst", []):
        frases = claim_frases(item)
        huidig = str(item.get("status") or "open")
        if not frases:
            # Geen citeerbare frase → we kunnen niets waarnemen. Dat is geen 'opgelost'.
            if huidig == "open":
                voorstellen.append({"nr": item.get("nr"), "van": huidig,
                                    "naar": claims_db.NIET_VERIFIEERBAAR,
                                    "reden": "geen citeerbare claim-frase in de omschrijving",
                                    "frase": ""})
            continue
        aanwezig = next((f for f in frases if f in alles), None)
        if aanwezig:
            # De claim staat er (nog). Alleen ingrijpen als iemand hem al afgevinkt had:
            # dat is een regressie en het belangrijkste signaal dat deze module kan geven.
            if huidig in _MENS_OPGELOST or huidig == claims_db.AUTO_OPGELOST:
                voorstellen.append({"nr": item.get("nr"), "van": huidig,
                                    "naar": claims_db.AUTO_REGRESSIE,
                                    "reden": f"de claim staat weer op de site ({datum})",
                                    "frase": aanwezig})
            continue
        # De claim is niet gevonden in de gescande tekst.
        if not _staat_op_gescande_pagina(item, paginateksten):
            if huidig == "open":
                voorstellen.append({"nr": item.get("nr"), "van": huidig,
                                    "naar": claims_db.NIET_VERIFIEERBAAR,
                                    "reden": "de vindplaats valt buiten de vaste scan-set",
                                    "frase": frases[0]})
            continue
        if huidig in (claims_db.AUTO_OPGELOST,) or huidig in _MENS_OPGELOST:
            continue                                    # al opgelost, niets te melden
        voorstellen.append({"nr": item.get("nr"), "van": huidig,
                            "naar": f"{claims_db.AUTO_OPGELOST[:-1]} {datum})",
                            "reden": "de claim is niet meer aanwezig op de gescande pagina",
                            "frase": frases[0]})
    return voorstellen


def _staat_op_gescande_pagina(item: dict, paginateksten: dict[str, str]) -> bool:
    """Valt de vindplaats van dit item binnen de pagina's die we deze run zagen?

    De werklijst noemt de plek in gewone taal ("homepage", "FAQ", "productpagina"). We matchen
    die tegen de labels van de scan-set. Geen match → we kunnen er niets over zeggen."""
    plek = normaliseer(item.get("claim") or "")
    synoniemen = {"home": ("homepage", "home", "sitewide", "header"),
                  "faq": ("faq", "veelgestelde"),
                  "mission": ("mission", "missionpagina", "missie"),
                  "product": ("product", "productpagina", "outsole", "insoles", "lining"),
                  "impact": ("impact", "forest")}
    for label in paginateksten:
        for woord in synoniemen.get(label, (label,)):
            if woord in plek:
                return True
    return False


def pas_toe(db: dict, voorstellen: list[dict]) -> list[dict]:
    """Voer de voorstellen door in de database-dict (in geheugen). Geeft terug wat er wijzigde."""
    per_nr = {v["nr"]: v for v in voorstellen}
    gewijzigd = []
    for item in db.get("werklijst", []):
        v = per_nr.get(item.get("nr"))
        if not v:
            continue
        item["status"] = v["naar"]
        item["status_bron"] = "auto"          # machine-oordeel, expliciet gelabeld
        gewijzigd.append(v)
    return gewijzigd
