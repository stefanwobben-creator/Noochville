"""Een batch als Critical Number: CN1 "Batch 4 sold" (10 oktober 2026).

Nooch verkoopt made-to-order in batches: de winkel gaat open, klanten bestellen en betalen, en als
de batch vol of de deadline daar is gaat de winkel dicht. Tussen batches wordt niets verkocht. Dus:

* TELLING op BESTELDATUM: de paren uit de dagreeks `shopify_pairs_sold_day` (die per besteldag
  telt) vanaf de startdatum. Geen tag — elke batch verkoopt hetzelfde model, een tag onderscheidt
  batches niet.
* TOESTANDEN:
    not started  vóór de startdatum — geen status, geen rood;
    open         tussen start en sluiten — met de lijn naar het doel;
    closed       doel gehaald óf deadline voorbij — de eindstand blijft staan, er komt geen rood bij.
  Tussen twee batches staat het nummer dus op "closed", niet op 0%.
* De STARTDATUM is de begindatum van de lijn op de tegel (`lijn.van`) — één plek. Hij staat als
  voorlopige waarde in `config/critical_numbers.json` en Sales of de anchor lead verzet hem in de UI.

Puur: rekent op een dagreeks en een tegel, leest niets van schijf.
"""
from __future__ import annotations

import time

NIET_GESTART, OPEN, GESLOTEN = "not started", "open", "closed"


def stand(reeks: list[dict], tile: dict, vandaag: str = "") -> dict:
    """{toestand, paren, sluitdatum}. `reeks` = rijen met `datum` en `value` (paren per besteldag).

    `paren` = de som vanaf de startdatum tot en met vandaag, of — als de batch gesloten is — tot en
    met de dag waarop hij sloot (de dag dat het doel gehaald werd, of de deadline). Geen data → None,
    nooit 0: zonder Shopify-reeks weten we niet dat er niets verkocht is."""
    vandaag = vandaag or time.strftime("%Y-%m-%d")
    lijn = tile.get("lijn") or {}
    start, deadline, doel = lijn.get("van", ""), lijn.get("tot", ""), tile.get("target")
    if not start or vandaag < start:
        return {"toestand": NIET_GESTART, "paren": None, "sluitdatum": ""}
    dagen = sorted((str(r.get("datum") or "")[:10], float(r["value"])) for r in reeks
                   if r.get("value") is not None and start <= str(r.get("datum") or "")[:10] <= deadline)
    totaal, sluit = 0.0, ""
    for datum, v in dagen:
        if datum > vandaag:
            break
        totaal += v
        if doel is not None and totaal >= float(doel):
            sluit = datum
            break
    if not sluit and deadline and vandaag > deadline:
        sluit = deadline
    paren = totaal if dagen else None
    return {"toestand": GESLOTEN if sluit else OPEN, "paren": paren, "sluitdatum": sluit}
