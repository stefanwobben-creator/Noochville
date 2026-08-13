"""De uitvoerbare kant van een `voorstel`-item in de human inbox.

Waarom dit bestaat. Een voorstel-item droeg alleen proza. `approve` viel daardoor in het vangnet
van de CLI: het item ging dicht, de melding zei "goedgekeurd", en de bron waar het voorstel over
ging bleef ongewijzigd tot iemand het zich later herinnerde. Dat is dezelfde klasse als de
luna-trede zonder prijs, het `library`-versus-`bibliotheek`-domein en `required_payload`: de
declaratie zegt aangenomen, de handhaving doet niets, en er is geen enkel signaal ertussen.

De fix is niet "voer proza uit" — dat kan niet. De fix is een voorstel dwingen te ZEGGEN wat het
muteert, in een vorm die een machine kan uitvoeren, en luid zijn als het dat niet doet:

  mutatie declared → approve voert hem uit; mislukt hij, dan blijft het item pending
  geen mutatie      → approve legt de beslissing vast en MELDT dat er niets is uitgevoerd

Zo is er geen stille derde toestand meer waarin "approved" en "de bron is ongewijzigd" tegelijk
waar zijn zonder dat iemand het ziet.

Vorm van een mutatie:

    {"soort": "lexicon_rationale", "concept_id": "conscious_consumer", "regel": "SCOPE: …"}

Nieuwe soorten registreren zich in `_UITVOERDERS`. Een onbekende soort faalt closed: liever een
voorstel dat blijft staan dan een goedkeuring die niets deed.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("village.voorstel_mutatie")

# Wat een mutatie minimaal moet dragen, per soort. Ontbreekt een veld, dan weigert de uitvoerder
# vóór hij iets aanraakt — dezelfde fail-closed-lijn als `required_payload` bij skills.
VELDEN = {
    "lexicon_rationale": ("concept_id", "regel"),
}


def _lexicon_rationale(mutatie: dict, data_dir: str) -> tuple[bool, str]:
    """Vul de rationale van een lexicon-concept aan. Cureren van het lexicon is Librarian-domein;
    deze weg bestaat omdat de mens op het geauthenticeerde oppervlak tekent, niet omdat een rol
    het lexicon buiten zijn domein om zou mogen schrijven."""
    from nooch_village.lexicon import Lexicon

    cid, regel = mutatie["concept_id"], mutatie["regel"]
    lex = Lexicon(os.path.join(data_dir, "lexicon.json"))
    if lex.concept(cid) is None:
        return False, f"lexicon-concept '{cid}' bestaat niet"
    if not lex.annoteer(cid, regel):
        return True, f"lexicon-concept '{cid}': regel stond er al — niets gewijzigd"
    nieuw = str((lex.concept(cid) or {}).get("rationale") or "")
    return True, f"lexicon-concept '{cid}' geannoteerd. Rationale nu: {nieuw}"


_UITVOERDERS = {
    "lexicon_rationale": _lexicon_rationale,
}


def beschrijf(mutatie: dict | None) -> str:
    """Eén regel over wat approve zou doen — voor `inbox show`, zodat de mens vóór het tekenen
    ziet of er iets wordt uitgevoerd of alleen vastgelegd."""
    if not mutatie:
        return "(geen — approve legt alleen de beslissing vast, er wordt niets geschreven)"
    soort = str(mutatie.get("soort") or "?")
    if soort == "lexicon_rationale":
        return (f"lexicon-concept '{mutatie.get('concept_id')}': rationale aanvullen met "
                f"\"{str(mutatie.get('regel') or '')[:80]}\"")
    return f"{soort} ({', '.join(f'{k}={v}' for k, v in mutatie.items() if k != 'soort')})"


def voer_uit(mutatie: dict | None, data_dir: str) -> tuple[bool, str]:
    """Voer de mutatie uit. Geeft (geslaagd, bericht).

    Geslaagd=False betekent: er is NIETS geschreven, en de aanroeper mag het item niet sluiten."""
    if not mutatie:
        return False, "geen mutatie gedeclareerd"
    soort = str(mutatie.get("soort") or "")
    fn = _UITVOERDERS.get(soort)
    if fn is None:
        return False, (f"onbekende mutatie-soort '{soort}' — bekend: {sorted(_UITVOERDERS)}. "
                       f"Fail-closed: er is niets geschreven.")
    mist = [v for v in VELDEN.get(soort, ()) if not str(mutatie.get(v) or "").strip()]
    if mist:
        return False, f"mutatie '{soort}' mist: {', '.join(mist)}"
    try:
        return fn(mutatie, data_dir)
    except Exception as e:                                   # noqa: BLE001 — fail closed, luid
        log.warning("mutatie '%s' faalde: %s", soort, e)
        return False, f"mutatie '{soort}' faalde: {e}"
