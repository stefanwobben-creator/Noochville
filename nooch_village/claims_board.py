"""Van claim-bevinding naar taak op het projectenbord.

Waarom een eigen module: dezelfde omzetting wordt aangeroepen door de knop in de checker
(mens klikt) en door de wekelijkse site-scan (compliance zelf). Dedupe-regels, rol-routing en
taakopmaak mogen daar niet uiteenlopen — één plek, twee aanroepers.

De harde regel hier is **dedupe**. Zonder dedupe zet elke scan dezelfde twintig bekende claims
opnieuw op het bord en is het bord binnen een week onbruikbaar.
"""
from __future__ import annotations

import re

ORIGIN = "claims_fix"          # herkomst-stempel: hieraan herkennen we onze eigen taken terug

# Rol-label uit de bevinding → record-id van de rol die het werk doet. Onbekende of niet-bestaande
# id's vallen terug op compliance: liever bij de eigenaar van het domein dan nergens.
ROL_IDS = {
    "copywriter": "mother_earth__nooch__noochville__copywriter",
    "visual designer": "mother_earth__nooch__brand_visual_designer",
    "marketeer": "mother_earth__nooch__marketing_lead",
    "compliance": "compliance",
    "copywriter + compliance": "mother_earth__nooch__noochville__copywriter",
}
FALLBACK_ROL = "compliance"

_NIET_WOORD = re.compile(r"[^a-z0-9]+")


def normaliseer(tekst: str) -> str:
    """Claim-tekst tot een vergelijkbare sleutel: kleine letters, alleen letters en cijfers.

    Zo matcht «"100% Planet-Safe" — homepage, sitewide» met «100% planet safe homepage sitewide»
    en herkent de dedupe een werklijst-item ook als de scan het net anders formuleert."""
    return _NIET_WOORD.sub(" ", (tekst or "").lower()).strip()


def rol_id_voor(rol_label: str, records=None) -> str:
    """De record-id van de rol die deze bevinding oppakt. Bestaat de rol niet (meer) in de
    records, dan gaat het werk naar compliance in plaats van naar een dood id."""
    kandidaat = ROL_IDS.get(rol_label, FALLBACK_ROL)
    if records is not None and records.get(kandidaat) is None:
        return FALLBACK_ROL
    return kandidaat


def taak_sleutel(bevinding: dict) -> str:
    """De dedupe-sleutel van één bevinding: wat er letterlijk gevonden is, plus de pagina.

    Dezelfde verboden term op twee pagina's is twee stukken werk (zo staat het ook in de
    werklijst: claim én vindplaats), dus de pagina hoort in de sleutel."""
    gevonden = (bevinding.get("gevonden") or [""])[0]
    pagina = bevinding.get("pagina") or ""
    return normaliseer(f"{gevonden} {pagina}").strip()


def _zoektermen(bevinding: dict) -> list[str]:
    """De letterlijke vondsten, genormaliseerd — waarop we tegen bestaand werk matchen.

    Bewust de gevonden frase en niet de term-omschrijving: de werklijst noteert
    «"100% Planet-Safe" — homepage» en de scan vindt «Planet-Safe». Die twee matchen op de
    frase, nooit op de databank-term "planet-safe / planet-friendly / planet-loving"."""
    return [n for n in (normaliseer(g) for g in (bevinding.get("gevonden") or [])) if n]


def _bestaande_sleutels(ledger, db: dict) -> set[str]:
    """Alles waarvoor al werk loopt: onze eigen open taken én de openstaande werklijst-items.

    Werklijst-items tellen mee omdat die de site-audit zijn — een bekende claim staat daar al,
    en hoeft niet nóg eens als taak op het bord."""
    sleutels = set()
    for p in ledger.all():
        if p.get("origin") != ORIGIN or p.get("status") == "done":
            continue
        if p.get("keyword"):
            sleutels.add(p["keyword"])
        sleutels.add(normaliseer(p.get("scope") or ""))
    for w in (db or {}).get("werklijst", []):
        if str(w.get("status", "open")).lower() == "live":
            continue                                   # afgehandeld → een nieuwe vondst mág weer
        sleutels.add(normaliseer(w.get("claim") or ""))
    return sleutels


def _dekt(bevinding: dict, bestaand: set[str]) -> bool:
    """Loopt er al werk voor deze bevinding?

    Ja zodra een van de gevonden frases voorkomt in een bestaande omschrijving (werklijst-item
    of open taak). De werklijst schrijft claims uitgebreider op dan de scan ze vindt, dus de
    match gaat van frase → omschrijving, niet andersom."""
    termen = _zoektermen(bevinding)
    if not termen:
        return True                                    # niets concreets gevonden = niets te doen
    for term in termen:
        for b in bestaand:
            if b and term in b:
                return True
    return False


def taak_tekst(bevinding: dict, bron: str) -> tuple[str, str]:
    """(titel, beschrijving) van de taak. De beschrijving bevat alles wat de rol nodig heeft
    om het zonder terugvragen op te lossen: claim, vindplaats, oordeel, veilige herformulering
    en de nacheck."""
    rood = bevinding.get("stoplicht") == "red"
    gevonden = ", ".join(bevinding.get("gevonden") or []) or bevinding.get("term", "")
    werkwoord = "Vervang" if rood else "Onderbouw"
    titel = f"{'🔴' if rood else '🟠'} {werkwoord}: {gevonden}"
    beschrijving = (
        f"Claim: {gevonden} ({bevinding.get('term', '')})\n"
        f"Vindplaats: {bron or 'onbekend'}\n"
        f"Oordeel: {'verboden — niet publiceren' if rood else 'risico — alleen met genoemd bewijs'}"
        f" · categorie {bevinding.get('categorie', '')}\n"
        f"Waarom: {bevinding.get('waarom', '')}\n"
        f"Veilige herformulering: {bevinding.get('alternatief', '')}\n"
        f"Nacheck na aanpassing: tov + legal."
    )
    return titel[:200], beschrijving


def zet_op_bord(ledger, records, db: dict, bevindingen: list[dict], bron: str,
                rol_voor, trigger: str = "human") -> dict:
    """Maak een taak per rode/oranje bevinding die nog nergens loopt.

    `rol_voor` is de routing-functie (categorie → rol-label); die woont in de view, zodat de
    checker en het bord dezelfde routing gebruiken. Geeft een verslag terug van wat er is
    aangemaakt en wat is overgeslagen."""
    bestaand = _bestaande_sleutels(ledger, db)
    aangemaakt, overgeslagen = [], 0
    for b in bevindingen:
        if b.get("stoplicht") not in ("red", "orange"):
            continue
        if _dekt(b, bestaand):
            overgeslagen += 1
            continue
        sleutel = taak_sleutel(b)
        titel, beschrijving = taak_tekst(b, b.get("url") or bron)
        eigenaar = rol_id_voor(rol_voor(b.get("categorie", "")), records)
        pid = ledger.create(eigenaar, titel, trigger, status="future", origin=ORIGIN,
                            keyword=sleutel, description=beschrijving,
                            dod_outcome="de claim staat compliant op de site",
                            done_when="de herformulering is live en door legal gezien",
                            goes_to="compliance")
        aangemaakt.append({"pid": pid, "owner": eigenaar, "titel": titel,
                           "stoplicht": b.get("stoplicht")})
        bestaand.add(sleutel)                          # binnen één run niet dubbel
        bestaand.update(_zoektermen(b))
    return {"aangemaakt": aangemaakt, "overgeslagen": overgeslagen,
            "rood": sum(1 for t in aangemaakt if t["stoplicht"] == "red")}
