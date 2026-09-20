"""De inbox naar de kanalen — stap 1 van drie: SCHRIJVEN, niets verwijderen.

Besluit Stefan, nacht van 19 op 20 september 2026: *"inbox moet gewoon weg, dat wordt een kanaal in
messages"*. Dat draait de fase-8-keuze om waarin `NotifStore` en `/inbox` bewust naast de
kanaallaag bleven staan.

DRIE STAPPEN, EN DIT IS DE EERSTE:

  1. schrijven naast `NotifStore` (deze module) — niets weg, uitkomst te bekijken
  2. `/inbox` laten lezen uit de kanalen
  3. pas dan `NotifStore` en de oude routes verwijderen

De reden voor die volgorde staat in `claude/fase10_voorstel_inbox_migratie.md`: 13
NotifStore-methodes, 46 aanroepen, 18 bronbestanden, 37 testbestanden. Een fout in stap 1 die pas
na stap 3 opvalt, neemt de historie van 371 items mee.

WAT HIER NIET GEBEURT. Geen vertaling naar een mens. Een notificatie is aan een ROL gericht en gaat
naar `role:<record_id>`. Daardoor is er voor de negentien open items op de vijf in fase 1-3
gearchiveerde rollen (librarian, harry_hemp, copywriter, compliance, concurrent_scout) niets te
kiezen: ze migreren mee met status open, want dat IS de waarheid — niemand heeft ze ooit gesloten
en er is nu niemand die dat namens de rol kan doen.

PERSOON-GERICHTE ITEMS BLIJVEN LIGGEN. 33 van de 371 zijn op een persoon gericht (2 open). Stefans
besluit gaat over rollen; een `person:`-kanaalsoort erbij verzinnen zou een tweede datamodel-begrip
zijn dat niemand heeft gevraagd. Ze worden geteld en gerapporteerd, niet aangeraakt.
"""
from __future__ import annotations

from nooch_village import channels

#: De twee tellingen die de migratie moet overleven. Zie de harde eis in het voorstel: 185
#: vastgelegde uitkomsten en 54 poort-oordelen zijn oordelen van een mens, geen afgeleide status.
TEL_VELDEN = ("outcome", "poort", "verwerkingen", "read", "processed", "archived", "done", "deleted")


def tellen(rijen) -> dict[str, int]:
    """Hoe vaak elk verwerkingsveld gevuld is. Vóór en ná moeten gelijk zijn."""
    return {v: sum(1 for n in rijen if n.get(v)) for v in TEL_VELDEN}


def tellen_entries(entries) -> dict[str, int]:
    """Dezelfde telling, maar over gemigreerde kanaalberichten."""
    return {v: sum(1 for e in entries if (e.get("verwerking") or {}).get(v)) for v in TEL_VELDEN}


def _rol_rijen(notif) -> list[dict]:
    return [n for n in notif.all() if n.get("target_type") == "role" and n.get("target_id")]


def migreer(notif, kanalen, *, apply: bool = False) -> dict:
    """Zet elke rol-gerichte notificatie in het kanaal van zijn rol.

    `apply=False` (default) schrijft niets en rapporteert wat er zou gebeuren — zelfde vorm als
    `wiki_seed.zaai`. Idempotent: een rij die al in het kanaal staat wordt overgeslagen.

    Geeft een rapport terug met de tellingen vóór en ná, zodat de guard geen aparte stap is maar
    onderdeel van de uitvoer. Een migratie die zijn eigen bewijs niet meelevert, is een bewering.
    """
    rijen = _rol_rijen(notif)
    voor = tellen(rijen)
    rapport = {"rol_rijen": len(rijen), "voor": voor, "geschreven": 0, "bestond_al": 0,
               "kanalen": {}, "persoon_rijen": sum(1 for n in notif.all()
                                                   if n.get("target_type") == "person")}
    for n in rijen:
        kanaal = channels.role_kanaal(n["target_id"])
        rapport["kanalen"][kanaal] = rapport["kanalen"].get(kanaal, 0) + 1
        if not apply:
            bestaat = any(e.get("id") == n.get("id") for e in kanalen.trail(kanaal, limit=10_000))
            rapport["bestond_al" if bestaat else "geschreven"] += 1
            continue
        if kanalen.plaats_notificatie(kanaal, n) is None:
            rapport["bestond_al"] += 1
        else:
            rapport["geschreven"] += 1

    na_entries = [e for k in rapport["kanalen"]
                  for e in kanalen.trail(k, limit=10_000)
                  if e.get("kind") == channels.NOTIFICATIE]
    rapport["na"] = tellen_entries(na_entries)
    rapport["na_berichten"] = len(na_entries)
    rapport["apply"] = apply
    rapport["klopt"] = (not apply) or (rapport["na"] == voor
                                       and rapport["na_berichten"] == len(rijen))
    return rapport


def hersync(notif, kanalen) -> dict:
    """Breng de kanalen bij met `NotifStore`, in één pass. Stap 2 leunt hierop.

    ZOLANG STAP 3 NIET IS GEZET, IS `NotifStore` DE SCHRIJVER. Elke inbox-actie (gelezen,
    verwerkt, uitkomst, poort, archiveren) schrijft nog steeds daar. Het kanaal is in stap 2 de
    LEZER. Twee plekken met hetzelfde feit is normaal gesproken precies wat `reference, don't copy`
    verbiedt — hier is het tijdelijk en bewust, en dit is de enige plek die ze bij elkaar houdt:
    één functie, aangeroepen vlak vóór het lezen, in plaats van een sync-aanroep verspreid over
    elke schrijf-actie. Drift is daarmee niet mogelijk, want er wordt nooit uit een verouderde
    kopie gelezen.

    In stap 3 verdwijnt deze functie samen met `NotifStore`.
    """
    rijen = {n["id"]: n for n in _rol_rijen(notif)}
    bij, nieuw = 0, 0
    for n in rijen.values():
        kanaal = channels.role_kanaal(n["target_id"])
        entry = next((e for e in kanalen.trail(kanaal, limit=10_000)
                      if e.get("id") == n.get("id")), None)
        if entry is None:
            if kanalen.plaats_notificatie(kanaal, n) is not None:
                nieuw += 1
            continue
        vers = {k: v for k, v in n.items() if k not in channels.VERWERKING_OVERSLAAN}
        if entry.get("verwerking") != vers:
            kanalen.werk_verwerking_bij(kanaal, n["id"], vers)
            bij += 1
    return {"nieuw": nieuw, "bijgewerkt": bij, "totaal": len(rijen)}


def open_uit_kanalen(kanalen, targets) -> list[dict]:
    """De inbox-wachtrij, maar gelezen uit de KANALEN in plaats van uit `NotifStore`.

    Geeft dicts met dezelfde vorm als `NotifStore.open_for_targets` teruggaf, zodat de view niet
    hoeft te weten waar zijn items vandaan komen. Dat is geen truc om een herschrijving te
    vermijden: de vorm ís hetzelfde feit, alleen op een andere plek opgeslagen.

    Alleen rol-doelen. Persoon-gerichte items zijn niet gemigreerd (besluit: buiten deze ronde),
    dus die haalt de aanroeper nog bij `NotifStore` vandaan.
    """
    rollen = [i for t, i in targets if t == "role"]
    uit = []
    for rol in rollen:
        for e in kanalen.trail(channels.role_kanaal(rol), limit=10_000):
            if e.get("kind") != channels.NOTIFICATIE:
                continue
            v = dict(e.get("verwerking") or {})
            if v.get("archived") or v.get("deleted") or v.get("done"):
                continue
            v.update({"id": e.get("id"), "at": e.get("at"),
                      "tekst": e.get("text") or "", "target_type": "role", "target_id": rol})
            v.setdefault("snippet", (e.get("text") or "")[:160])
            uit.append(v)
    return sorted(uit, key=lambda n: -(n.get("at") or 0))


def rapport_tekst(r: dict) -> str:
    regels = [f"rol-gerichte notificaties : {r['rol_rijen']}",
              f"persoon-gericht (blijft)  : {r['persoon_rijen']}",
              f"geschreven                : {r['geschreven']}",
              f"bestond al                : {r['bestond_al']}",
              f"kanalen                   : {len(r['kanalen'])}", ""]
    # BIJ EEN DROOGLOOP GEEN VERGELIJKING. De eerste versie printte de ná-kolom ook dan, en die
    # stond logischerwijs op nul — acht regels "← WIJKT AF" met eronder "✓ tellingen kloppen".
    # Dat leest als een kapotte migratie óf als een geslaagde, maar zeker niet als "er is nog niets
    # gebeurd". Zelfde fout als de neutrale ▸ bij een no-op deploy: de uitvoer moet zeggen wat er
    # is gebeurd, niet wat er zou kunnen.
    if not r.get("apply"):
        regels.append(f"{'veld':<14}{'nu':>8}")
        for v in TEL_VELDEN:
            regels.append(f"{v:<14}{r['voor'].get(v, 0):>8}")
        regels.append("")
        regels.append("◌ droogloop — de ná-telling en de guard volgen bij --apply")
        return "\n".join(regels)

    regels.append(f"{'veld':<14}{'vóór':>8}{'ná':>8}")
    for v in TEL_VELDEN:
        vo, na = r["voor"].get(v, 0), r["na"].get(v, 0)
        merk = "" if vo == na else "   ← WIJKT AF"
        regels.append(f"{v:<14}{vo:>8}{na:>8}{merk}")
    regels.append("")
    regels.append("✓ tellingen kloppen" if r["klopt"] else "✗ TELLINGEN KLOPPEN NIET — niet doorgaan")
    return "\n".join(regels)
