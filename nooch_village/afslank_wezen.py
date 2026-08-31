"""Een rol slapend leggen laat zijn open projecten achter — dit ruimt ze op.

GEMETEN OP PROD, 31 aug 2026. Van de 331 open projecten stonden er 13 op een eigenaar zonder énige
vervuller. Acht daarvan zijn de individuele-actie-baan van de founder (`ii:<cirkel>`) en horen daar:
geen rol, wel een eigenaar die kijkt. De andere **vijf** zijn echte wezen — 3 op `noochie`, 2 op
`facilitator` — en ze hebben alle vijf dezelfde oorzaak: de rol werd slapend gelegd NÁ het aanmaken.

De afslank-poort (`afslank_afhankelijkheden`) vraagt wat er aan een rol HANGT: welke events anderen
van hem lezen, of hij een eigen ritme heeft, welke skills alleen hij houdt. Wat hij niet vraagt is
wat er OP ZIJN BORD LIGT. Vier van de vijf poorten keken naar opbrengst, de vijfde naar
afhankelijkheden — en het werk zelf viel tussen die twee door.

GEEN NIEUW MECHANIEK. Herrouteren gebeurt via `cockpit2.route_werk`, precies dezelfde regel die
elders bepaalt waar werk landt: één menselijke vervuller → die mens, geen vervuller → de Circle
Lead. Een tweede routeerregel hier zou na één wijziging uit de pas lopen, en dan landt werk stil op
de verkeerde plek — de fout die #364 wegnam.

Dry-run is de default. Wat er gebeurt is zichtbaar vóór het gebeurt.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.afslank_wezen")

#: De individuele-actie-baan is geen rol maar de eigen lijst van de founder. Die heeft een eigenaar
#: die kijkt, en hoort dus niet bij de wezen.
_II = "ii:"


def wezen(st) -> list[dict]:
    """Open projecten waarvan de eigenaar-rol niets meer kan: geen mens, geen AI, geen code."""
    from nooch_village.cockpit2 import _kan_uitvoeren, mens_vervullers
    uit = []
    for p in st.projects.all():
        if p.get("archived") or str(p.get("status") or "").lower() in ("done", "afgerond", "klaar"):
            continue
        rol = str(p.get("owner") or "")
        if not rol or rol.startswith(_II):
            continue
        if mens_vervullers(st, rol) or _kan_uitvoeren(st, rol):
            continue
        uit.append({"pid": p.get("id"), "rol": rol, "titel": str(p.get("scope") or "")[:80],
                    "status": p.get("status")})
    return uit


def herrouteer(st, *, apply: bool = False) -> dict:
    """Elk wees-project opnieuw langs `route_werk`. Geeft een verslag; schrijft alleen met apply."""
    from nooch_village.cockpit2 import route_werk
    gevonden = wezen(st)
    gedaan = []
    for w in gevonden:
        if not apply:
            gedaan.append({**w, "naar": "(dry-run)"})
            continue
        try:
            soort, ref = route_werk(
                st, tekst=w["titel"], rol=w["rol"],
                herkomst=f"↳ {w['rol']} heeft geen vervuller meer; project {w['pid']} lag stil",
                door="afslank-opruiming", bron_project=w["pid"])
            gedaan.append({**w, "naar": f"{soort}: {ref}"})
            log.info("wees %s (%s) herrouteerd → %s", w["pid"], w["rol"], ref)
        except Exception as e:                                # noqa: BLE001 — nooit blokkeren
            gedaan.append({**w, "naar": f"FOUT: {e}"})
            log.warning("wees %s niet herrouteerd: %s", w["pid"], e)
    return {"gevonden": len(gevonden), "items": gedaan, "toegepast": bool(apply)}
