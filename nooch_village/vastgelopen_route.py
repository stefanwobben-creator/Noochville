"""De 33 die al stilstonden: een eenmalige pas over projecten die vóór de laatste meter vastliepen.

De laatste meter (`escalation_router.naar_mens`) vuurt op het MOMENT van de park-beslissing. Voor de
projecten die daarvóór al geparkeerd waren gebeurt er dus niets meer: hun items dragen `routed=True`,
en dat is precies de garantie die voorkomt dat de router elke puls opnieuw dezelfde LLM-call doet.

Gemeten op prod, 29 aug 2026: 33 geblokkeerde projecten van de Scientist, alle 33 met dezelfde
park-reden, samen 21 openstaande stappen, de oudste 51 dagen stil. Code repareren haalt die stapel
niet weg — dezelfde les als bij de notificatie-opruiming van 14 aug: **de fix stopt de instroom, hij
ruimt de voorraad niet op.**

Drie guards, en ze zijn geen van drieën optioneel:

1. **Alleen een MENS-park-reden.** Een `fails`- of `payload`-blokkade is rolwerk; die bij een mens
   neerleggen is precies de ruis die #287 wegnam.
2. **Alleen wat nu nog open is.** Een afgevinkte of overgeslagen stap is geen vraag meer.
3. **Idempotent op het SPOOR, niet op afwezigheid.** Er wordt gekeken of er al een melding over
   deze stap bij dit project ligt. Een marker op het item zou hetzelfde feit op een tweede plek
   zetten, en dat drijft uiteen — dezelfde regel als `reference, don't copy`.

Droge loop is de default, en hij BEPAALT WEL DE ONTVANGER — hij schrijft alleen niet.

Dat kost een modelcall per stap, en dat is precies de bedoeling: de vraag vóór het toepassen is niet
"hoeveel items" maar "waar landen ze". Een droge loop die alleen telt, laat de enige beslissing die
ertoe doet ongemeten. Valt de ladder terug op de founder, dan is deze pas geen ROUTERING maar een
stapel van 33 op één inbox — een andere handeling, met een ander besluit erachter.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.vastgelopen")

# De park-reden die zegt: hier ligt werk voor een mens. De andere twee redenen (`payload`, `fails`)
# zijn rolwerk en horen hier niet.
_MENS_REDEN = "wacht op een mens of externe partij"


def _naam_van(st, rol: str) -> str:
    rec = st.records.get(rol or "")
    return (getattr(getattr(rec, "definition", None), "name", "") or rol or "(onbekend)")


def _persoon_van(st, pid: str) -> str:
    p = st.people.get(pid or "")
    return (getattr(p, "name", "") or pid or "(onbekend)")


def _open_items(project: dict) -> list[dict]:
    return [it for cl in (project.get("checklists") or []) for it in (cl.get("items") or [])
            if not it.get("done") and not it.get("skipped")]


def al_geland(st, pid: str, item_text: str) -> bool:
    """Ligt er al een melding over deze stap bij dit project?

    Gegrond op het SPOOR (de verstuurde melding zelf), niet op een vlaggetje dat we er los naast
    zouden zetten. Een vlag en een melding zijn twee plekken voor één feit, en dan is de vraag
    'is dit al gemeld?' na één handmatige opruiming niet meer te beantwoorden."""
    kern = (item_text or "").strip()[:60]
    if not kern:
        return True                                   # niets te vragen → niets te doen
    for n in st.notif.all():
        if (n.get("bron_project") or n.get("project_id")) != pid:
            continue
        if kern in (n.get("snippet") or ""):
            return True
    return False


def pas(data_dir: str, *, apply: bool = False, owner: str = "", reason_fn=None) -> dict:
    """Loop de al-geparkeerde projecten langs. Geeft een verslag; schrijft alleen bij `apply=True`."""
    from nooch_village.cockpit2 import _Stores
    from nooch_village.escalation_router import _mens_ontvanger, naar_mens, trail_of

    st = _Stores(data_dir)
    verslag = {"bekeken": 0, "in_aanmerking": 0, "stappen": 0, "al_gemeld": 0,
               "geland": [], "mislukt": 0, "toegepast": bool(apply),
               "verdeling": {}, "gronden": {}}
    for p in st.projects.all():
        if p.get("status") != "blocked" or p.get("archived"):
            continue
        verslag["bekeken"] += 1
        if _MENS_REDEN not in str(p.get("blocked_on") or ""):
            continue                                  # guard 1: rolwerk blijft rolwerk
        if owner and p.get("owner") != owner:
            continue
        verslag["in_aanmerking"] += 1
        rec = st.records.get(p.get("owner") or "")
        naam = (getattr(getattr(rec, "definition", None), "name", "") or p.get("owner") or "")
        for it in _open_items(p):                     # guard 2: alleen wat nu nog open is
            tekst = (it.get("text") or "").strip()
            if not tekst:
                continue
            verslag["stappen"] += 1
            if al_geland(st, p["id"], tekst):         # guard 3: idempotent op het spoor
                verslag["al_gemeld"] += 1
                continue
            if not apply:
                # Wél de ontvanger bepalen, niet schrijven: zonder dat meet een droge loop de enige
                # beslissing niet die ertoe doet.
                try:
                    rol, persoon, grond = _mens_ontvanger(st, p, tekst, p.get("owner") or "",
                                                          trail_of(p), reason_fn)
                    naar = (_naam_van(st, rol) if rol else _persoon_van(st, persoon))
                except Exception as e:                # noqa: BLE001 — meten mag nooit breken
                    log.warning("ontvanger niet te bepalen (%s)", e)
                    naar, grond = "(onbekend)", "kon niet bepaald worden"
                verslag["geland"].append({"pid": p["id"], "rol": p.get("owner"), "naam": naam,
                                          "stap": tekst[:90], "ref": f"→ {naar}", "grond": grond})
                verslag["verdeling"][naar] = verslag["verdeling"].get(naar, 0) + 1
                verslag["gronden"][grond] = verslag["gronden"].get(grond, 0) + 1
                continue
            uit = naar_mens(data_dir=data_dir, project=p, item_text=tekst,
                            from_role=p.get("owner") or "", from_naam=naam,
                            waarom="het vraagt een mens of externe partij", reason_fn=reason_fn)
            if uit is None:
                verslag["mislukt"] += 1
                continue
            naar = (_naam_van(st, uit.get("rol")) if uit.get("rol")
                    else _persoon_van(st, uit.get("persoon")))
            verslag["geland"].append({"pid": p["id"], "rol": p.get("owner"), "naam": naam,
                                      "stap": tekst[:90], "ref": uit.get("ref", ""),
                                      "grond": uit.get("grond", "")})
            verslag["verdeling"][naar] = verslag["verdeling"].get(naar, 0) + 1
            verslag["gronden"][uit.get("grond", "")] = \
                verslag["gronden"].get(uit.get("grond", ""), 0) + 1
            st = _Stores(data_dir)                    # verse store: de melding telt mee voor guard 3
    return verslag


def rapport(data_dir: str, *, apply: bool = False, owner: str = "") -> dict:
    v = pas(data_dir, apply=apply, owner=owner)
    print(f"{v['bekeken']} geblokkeerde projecten bekeken · {v['in_aanmerking']} met een "
          f"mens-park-reden · {v['stappen']} openstaande stappen")
    print(f"  al gemeld (overgeslagen): {v['al_gemeld']}")
    print(f"  {'gelegd' if apply else 'zou leggen'}: {len(v['geland'])}"
          + (f" · mislukt: {v['mislukt']}" if v["mislukt"] else ""))
    for g in v["geland"]:
        print(f"    {g['naam'][:18]:18s} {g['stap'][:58]:58s} {g.get('ref','')}")
    if v["verdeling"]:
        print("\n  VERDELING — waar landt het:")
        for naam, n in sorted(v["verdeling"].items(), key=lambda t: -t[1]):
            print(f"    {n:3d}  {naam}")
        print("  op welke grond:")
        for grond, n in sorted(v["gronden"].items(), key=lambda t: -t[1]):
            print(f"    {n:3d}  {grond}")
    return v
