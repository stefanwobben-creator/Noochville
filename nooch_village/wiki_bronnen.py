""""Zegt de bron dit nog?" — de periodieke check op geciteerde bronnen van wiki-feiten.

Een certificaat vervalt door een datum te vergelijken: dat kan bij élke pageload, want het kost
niets. Een geciteerde URL kan dat niet — kijken of de bron het nog zegt is een netwerk-call, en die
hoort niet in een pageload thuis (traag, en een cockpit die bij het lezen naar buiten belt is
precies het patroon dat dit project elders vermijdt: bronnen worden door de puls opgehaald, niet
door een bezoeker).

Dus: dit moduul haalt de bron op, vergelijkt het citaat, en legt de uitkomst mét datum bij het feit
neer (`grond["check"]`). De pagina toont dáárna een gedateerde waarneming — "checked 2026-08-20 —
quote still present" — in plaats van te doen alsof hij het nu weet.

Drie regels:
- **Fail-closed op de conclusie.** Een netwerk- of HTTP-fout is géén oordeel over de bron: de check
  blijft dan 'niet te controleren', nooit 'weg'. Alleen een succesvol opgehaalde pagina waarin het
  citaat ontbreekt levert 'quote no longer found'.
- **Lui.** Een feit wordt pas opnieuw gecheckt als de vorige waarneming ouder is dan
  `OUDER_DAN_DAGEN`; zo blijft een dagelijkse run bijna gratis.
- **Geen versie-ruis.** De uitkomst gaat via `AttachmentStore.set_meta`: geen versie-entry en geen
  'laatst bewerkt'-bump, want er is niets aan de pagina veranderd.
"""
from __future__ import annotations

import datetime
import logging

from nooch_village import wiki

log = logging.getLogger("village.wiki_bronnen")

OUDER_DAN_DAGEN = 14


def _vandaag() -> str:
    return datetime.date.today().isoformat()


def _te_oud(check: dict, nu: str, ouder_dan_dagen: int) -> bool:
    op = str((check or {}).get("op") or "")
    if not op:
        return True
    try:
        d1 = datetime.date.fromisoformat(op)
        d2 = datetime.date.fromisoformat(nu)
    except ValueError:
        return True
    return (d2 - d1).days >= ouder_dan_dagen


def te_checken(a, *, nu: str = "", ouder_dan_dagen: int = OUDER_DAN_DAGEN) -> list[int]:
    """De indexen van de feiten op deze pagina die aan een check toe zijn: een geciteerde bron met
    een URL én een citaat, waarvan de vorige waarneming te oud is (of ontbreekt)."""
    nu = nu or _vandaag()
    uit = []
    for i, f in enumerate(wiki.feiten(a)):
        grond = f.get("grond") or {}
        if grond.get("soort") != "bron" or not grond.get("url") or not grond.get("citaat"):
            continue
        if _te_oud(grond.get("check") or {}, nu, ouder_dan_dagen):
            uit.append(i)
    return uit


def _standaard_ophaler(url: str) -> str:
    """De echte fetch, achter de SSRF-guardrail van `safe_fetch` — dezelfde poort als de
    claims-checker gebruikt voor een door een mens aangeleverde URL."""
    from nooch_village.safe_fetch import haal_tekst
    return str(haal_tekst(url).get("tekst") or "")


def check_pagina(store, a, *, ophaler=None, nu: str = "",
                 ouder_dan_dagen: int = OUDER_DAN_DAGEN, apply: bool = False) -> list[dict]:
    """Check de geciteerde bronnen van één pagina. Geeft een rapportregel per gecheckt feit.

    `ophaler` is injecteerbaar (callable(url) -> tekst) zodat een test dit kan bewijzen zonder
    netwerk; zonder injectie loopt het via `safe_fetch`."""
    nu = nu or _vandaag()
    haal = ophaler or _standaard_ophaler
    feiten = list(wiki.feiten(a))
    rapport = []
    gewijzigd = False
    for i in te_checken(a, nu=nu, ouder_dan_dagen=ouder_dan_dagen):
        f = feiten[i]
        grond = dict(f.get("grond") or {})
        url = str(grond.get("url") or "")
        try:
            tekst = haal(url)
            uitkomst = wiki.controleer_citaat(f, tekst)
        except Exception as e:                       # noqa: BLE001 — een fout is geen oordeel
            uitkomst = {"gevonden": None, "reden": f"could not fetch: {e}"}
            log.info("bron-check %s: %s", url, e)
        grond["check"] = {"op": nu, "gevonden": uitkomst["gevonden"], "reden": uitkomst["reden"]}
        feiten[i] = {**f, "grond": grond}
        gewijzigd = True
        rapport.append({"pagina": a.id, "titel": a.title or a.id, "feit": str(f.get("tekst") or "")[:60],
                        "url": url, "gevonden": uitkomst["gevonden"], "reden": uitkomst["reden"]})
    if gewijzigd and apply:
        meta = dict(getattr(a, "meta", None) or {})
        meta["feiten"] = feiten
        store.set_meta(a.id, meta)                   # geen versie-entry: er is niets gewijzigd
    return rapport


def check_alles(store, *, ophaler=None, nu: str = "", ouder_dan_dagen: int = OUDER_DAN_DAGEN,
                apply: bool = False) -> list[dict]:
    """Alle pagina's langs. Rapport per gecheckt feit; met `apply=False` wordt niets weggeschreven."""
    uit = []
    for a in wiki.paginas(store):
        uit += check_pagina(store, a, ophaler=ophaler, nu=nu,
                            ouder_dan_dagen=ouder_dan_dagen, apply=apply)
    return uit


def rapport_tekst(rapport: list[dict]) -> str:
    if not rapport:
        return "(geen geciteerde bronnen die aan een check toe zijn)"
    teken = {True: "✓ nog aanwezig", False: "⌛ citaat weg", None: "◌ niet te checken"}
    regels = []
    for r in rapport:
        regels.append(f"{teken.get(r['gevonden'], '?'):<18} {r['titel'][:28]:<28} "
                      f"{r['feit'][:40]:<40} {r['url'][:50]}")
        if r.get("reden"):
            regels.append(f"{'':<18} ↳ {r['reden']}")
    weg = sum(1 for r in rapport if r["gevonden"] is False)
    regels += ["", f"{len(rapport)} gecheckt · {weg} citaat/citaten niet meer gevonden"]
    return "\n".join(regels)
