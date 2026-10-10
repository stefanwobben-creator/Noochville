"""Zicht — wie een gevoelige tegel, KPI of lijst mag zien en wijzigen (CN2 Runway, 10 oktober 2026).

Het dorp is open: elke ingelogde ziet elke tegel. Cash, de lijst vaste kosten en de runway zijn de
uitzondering (besluit Stefan): alleen de rolhouders van Financial Controller en Business strategy,
en Stefan zelf (de anchor lead). Een tegel of KPI draagt daarvoor `zicht: "<groep>"`; de groep en
haar rollen staan op ÉÉN plek, in `config/critical_numbers.json` → `zicht`. Een tegel draagt dus
een VERWIJZING, geen kopie van de rollen: wie de rollen verandert, doet dat op één plek.

ÉÉN POORT VOOR ALLE LEESPLEKKEN. In plaats van de gebruikersnaam door elke view te sturen, krijgt een
route die metrics toont een KIJKER-versie van de stores (`voor(st, username)`): zijn `metrics` geeft
alleen tegels en KPI's terug die deze kijker mag zien. Zo kan geen leesplek vergeten worden — ook de
sparkline in de catalogus en de CSV-export niet. Het is per request; er is geen globale toestand.

FAIL-CLOSED: een onbekende groep of een onbekende ingelogde ziet niets van die groep. Guest (auth
uit) mag alles, zoals overal in de cockpit.
"""
from __future__ import annotations


def groepen() -> dict:
    """{groep: {"zien": [rol-id's], "wijzigen": [rol-id's]}} uit het seed-bestand."""
    from nooch_village import critical_numbers
    try:
        return critical_numbers.laad().get("zicht") or {}
    except (OSError, ValueError):
        return {}


def mag(st, username: str | None, groep: str, wat: str = "zien") -> bool:
    """Mag deze gebruiker `wat` (zien | wijzigen) bij deze groep? Lege groep = open."""
    if not groep:
        return True
    if username == "guest":
        return True
    actor = st.people.by_email(username) if username else None
    if actor is None:
        return False
    from nooch_village.cockpit2 import is_circle_lead, is_role_filler
    if is_circle_lead(actor.id, "mother_earth", st.assign):          # de anchor lead (Stefan)
        return True
    rollen = (groepen().get(groep) or {}).get(wat) or []
    return any(is_role_filler(actor.id, r, st.assign) for r in rollen)


class _KijkMetrics:
    """De MetricStore zoals één kijker hem mag zien. Schrijven en alles wat niet gefilterd hoeft,
    gaat ongewijzigd door naar de echte store."""

    def __init__(self, metrics, ok):
        self._m, self._ok = metrics, ok

    def __getattr__(self, naam):
        return getattr(self._m, naam)

    def _item_ok(self, it: dict | None) -> bool:
        return it is None or self._ok(it.get("zicht", ""))

    def _tegel_ok(self, t: dict) -> bool:
        if not self._ok(t.get("zicht", "")):
            return False
        src = t.get("source", "")
        return not src.startswith("kpi:") or self._item_ok(self._m.get(src[4:]))

    def tiles_of(self, node: str) -> list[dict]:
        return [t for t in self._m.tiles_of(node) if self._tegel_ok(t)]

    def for_node(self, node: str) -> list[dict]:
        return [i for i in self._m.for_node(node) if self._item_ok(i)]

    def kpis_for_nodes(self, nodes) -> list[dict]:
        return [i for i in self._m.kpis_for_nodes(nodes) if self._item_ok(i)]

    def get(self, mid: str):
        it = self._m.get(mid)
        return it if self._item_ok(it) else None


class _Kijker:
    """De stores zoals één kijker ze mag zien: alles gaat door, behalve `metrics` (gefilterd)."""

    def __init__(self, st, username: str | None):
        self._st, self.username = st, username
        self.metrics = _KijkMetrics(st.metrics, lambda g: mag(st, username, g))

    def __getattr__(self, naam):
        return getattr(self._st, naam)

    def mag_zien(self, groep: str) -> bool:
        return mag(self._st, self.username, groep)


def voor(st, username: str | None):
    """De kijker-versie van de stores voor deze gebruiker. Zie de kop van dit moduul."""
    return _Kijker(st, username)


def mag_zien(st, groep: str) -> bool:
    """Voor een view: mag de kijker van `st` deze groep zien? Zonder kijker (een test, de daemon,
    een interne aanroep) is er geen mens om af te schermen: dan ja."""
    f = getattr(st, "mag_zien", None)
    return True if f is None else f(groep)
