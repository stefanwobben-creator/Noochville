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
        # DE VOLLE SCOPE, en dat is een correctie op mijn eigen sweep van gisteren. Hier stond
        # `[:80]`, en dat kapte midden in een woord — "…compleet overzicht beschikbaa". Die
        # afkapping ging vervolgens als TEKST de nieuwe inbox-melding in, dus geen enkele
        # weergave-fix kon hem nog repareren: het verlies zat al in de data.
        #
        # Zelfde les als de 160-cap: een veld dat 'titel' heet maar de enige kopie is, is geen
        # titel maar een amputatie. Wie een korte regel wil, leidt hem af bij het TONEN.
        uit.append({"pid": p.get("id"), "rol": rol, "titel": str(p.get("scope") or ""),
                    "status": p.get("status")})
    return uit


def herrouteer(st, *, apply: bool = False) -> dict:
    """Elk wees-project opnieuw langs `route_werk`. Geeft een verslag; schrijft alleen met apply."""
    from nooch_village.cockpit2 import route_werk
    gevonden = wezen(st)
    gedaan = []
    for w in gevonden:
        if not apply:
            # DE BESTEMMING VOORSPELD MET DEZELFDE REGEL die hem straks uitvoert. "(dry-run)" als
            # bestemming is geen droge run maar een lege belofte: je ziet dat er iets gebeurt, niet
            # wát — en dan is het aftekenen van een sweep een handtekening zonder inhoud.
            from nooch_village.cockpit2 import bestemming, bestemming_tekst
            try:
                doel = bestemming_tekst(st, bestemming(st, rol=w["rol"]))
            except Exception as e:                            # noqa: BLE001
                doel = f"(niet te bepalen: {e})"
            # BEIDE KANTEN VAN DE VERHUIZING. Alleen de bestemming tonen laat de helft weg die het
            # verschil maakt tussen verplaatsen en kopiëren — en juist dáár ging het bijna mis.
            # "Zeg wát er gebeurt, niet dát er iets gebeurt" geldt ook voor wat er ACHTERBLIJFT.
            gedaan.append({**w, "naar": doel,
                           "origineel": f"archiveren met spoor naar: {doel}"})
            continue
        try:
            soort, ref = route_werk(
                st, tekst=w["titel"], rol=w["rol"],
                herkomst=f"↳ {w['rol']} heeft geen vervuller meer; project {w['pid']} lag stil",
                door="afslank-opruiming", bron_project=w["pid"])
            # HET ORIGINEEL MOET DICHT, anders is dit geen VERHUIZING maar een KOPIE. Zonder deze
            # stap blijft het wees-project staan én verschijnt er een nieuw item: twee plekken voor
            # één stuk werk, en bij de volgende sweep opnieuw. Een opruiming die niet idempotent is
            # maakt bij elke run meer rommel dan hij weghaalt.
            #
            # Archiveren en niet afronden: het werk is niet klaar, het ligt ergens anders. De
            # verwijzing gaat als feed-entry mee zodat je het spoor terug kunt lopen.
            st.projects.add_feed_entry(
                w["pid"], f"↳ verhuisd: {w['rol']} heeft geen vervuller meer → {ref}",
                kind="system", author_type="system", author_id="afslank-opruiming")
            st.projects.archive(w["pid"])
            gedaan.append({**w, "naar": f"{soort}: {ref}", "origineel": "gearchiveerd"})
            log.info("wees %s (%s) herrouteerd → %s (origineel gearchiveerd)", w["pid"], w["rol"], ref)
        except Exception as e:                                # noqa: BLE001 — nooit blokkeren
            gedaan.append({**w, "naar": f"FOUT: {e}"})
            log.warning("wees %s niet herrouteerd: %s", w["pid"], e)
    return {"gevonden": len(gevonden), "items": gedaan, "toegepast": bool(apply)}
