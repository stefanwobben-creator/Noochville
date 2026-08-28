"""Één mechaniek per ding — als poortje, niet als voornemen.

Bijna elke bug van 28 augustus 2026 was een tweede mechaniek voor iets dat al bestond: een tweede
terug-URL in een fragment, een tweede plek waar een actie landde, een tweede telling van hetzelfde
overleg. Ze faalden allemaal stil. Een tweede vorm van hetzelfde is geen extra functie; het is een
divergentie die op zijn moment wacht.

Twee poorten hier (de rest staat in `docs/CONVENTIES.md` met zijn eigen ratchet):

  1. DE STORES ZIJN BEVROREN. Een tweede checklist-store, een tweede meldingskanaal of een tweede
     projectstore verschijnt onvermijdelijk als een nieuw attribuut op `_Stores`. Toevoegen mag —
     maar dan bewust, met een regel erbij en een reden.
  2. ÉÉN PROJECTCREATIE-FORMULIER. Een mens maakt een project via de wizard. Elk ander formulier
     dat rechtstreeks een project aanmaakt is de tweede vorm.
"""
from __future__ import annotations

import pathlib
import re
import tempfile

from nooch_village import cockpit2

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

# ── 1. de stores ────────────────────────────────────────────────────────────
#
# Voeg je er één toe, zet hem hier ERBIJ met een reden in de commit. Dat is de hele bedoeling:
# een tweede store is een besluit, geen bijvangst.
STORES = {
    "agenda", "ai", "assign", "att", "backlog", "checklists", "copy_stack", "defs",
    "deliverables", "evidence", "kennisbank", "library", "link_kroniek", "match", "metrics",
    "nom_kroniek", "nominations", "noochie", "notes", "notif", "observations", "people",
    "personas", "project_docs", "projects", "radar", "radar_besluiten", "records", "sources",
    "spel", "staging", "strategies", "werk",
}


def test_de_stores_zijn_bevroren():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    nu = {k for k in vars(st) if not k.startswith("_") and k != "dd"}
    erbij = nu - STORES
    assert erbij == set(), (
        f"nieuwe store(s) {sorted(erbij)} — zoek eerst de bestaande mechaniek (docs/CONVENTIES.md). "
        "Is het écht een nieuw ding, zet hem dan in STORES met een reden in de commit.")
    weg = STORES - nu
    assert weg == set(), f"store(s) verdwenen: {sorted(weg)} — haal ze uit STORES zodat de lijst klopt"


# Er zijn DRIE postbussen, en ze zijn geen variant van elkaar:
#
#   NotifStore  de inbox van een MENS — meldingen, spanningen, acties uit een overleg;
#   Inbox       de werkwachtrij van een INWONER (thread) — toegewezen werk dat áf moet;
#   HumanInbox  het geauthenticeerde lokale approval-oppervlak (governance, activaties).
#
# Een vierde is wél een tweede postbus: dan mist iemand de helft van zijn werk en merkt niemand het.
POSTBUSSEN = {"NotifStore", "Inbox", "HumanInbox"}


def test_er_komt_geen_vierde_postbus_bij():
    klassen = set()
    for f in ROOT.rglob("*.py"):
        for m in re.finditer(r"^class (\w*Notif\w*|\w*Inbox\w*)\b", f.read_text(encoding="utf-8"),
                             re.M):
            klassen.add(m.group(1))
    erbij = klassen - POSTBUSSEN
    assert erbij == set(), (
        f"nieuwe postbus-achtige klasse(n): {sorted(erbij)}. Er zijn er drie en ze doen elk iets "
        "anders (mens / inwoner-thread / approval) — zie docs/CONVENTIES.md. Is dit echt een vierde "
        "soort, zet hem dan in POSTBUSSEN met een reden.")
    weg = POSTBUSSEN - klassen
    assert weg == set(), f"postbus verdwenen: {sorted(weg)} — werk POSTBUSSEN bij"


# ── 2. projectcreatie ───────────────────────────────────────────────────────
#
# Een mens maakt een project via de WIZARD. `proj_add` is de oude directe route; hij zit nog in
# `views/projects.py::_inline_add_project`, dat nergens meer gerenderd wordt. MONOTOON DALEND:
# bij de wizard-optimalisatie gaat dit naar 0 en verlaag je het plafond.
PROJ_ADD_PLAFOND = {"views/projects.py": 1}

_FORM_ACTIE = re.compile(r"value='proj_add'")


def _proj_add_formulieren() -> dict[str, int]:
    uit: dict[str, int] = {}
    for f in sorted(ROOT.rglob("*.py")):
        n = len(_FORM_ACTIE.findall(f.read_text(encoding="utf-8")))
        if n:
            uit[str(f.relative_to(ROOT))] = n
    return uit


def test_geen_tweede_projectcreatie_formulier():
    nu = _proj_add_formulieren()
    nieuw = {k: v for k, v in nu.items() if k not in PROJ_ADD_PLAFOND}
    assert nieuw == {}, (
        f"nieuw projectcreatie-formulier in {sorted(nieuw)} — een mens maakt een project via de "
        "wizard (/project/nieuw), zodat rol, uitkomst en checklist één vorm hebben")
    te_hoog = {k: (v, PROJ_ADD_PLAFOND[k]) for k, v in nu.items() if v > PROJ_ADD_PLAFOND[k]}
    assert te_hoog == {}, f"plafond overschreden (nu, max): {te_hoog}"
    gedaald = {k: (nu.get(k, 0), v) for k, v in PROJ_ADD_PLAFOND.items() if nu.get(k, 0) < v}
    assert gedaald == {}, f"schuld opgeruimd — verlaag PROJ_ADD_PLAFOND: {gedaald}"


def test_de_bekende_ingangen_wijzen_naar_de_wizard():
    """Gedrag naast de telling: het bord en de inbox mogen niet zelf een project maken."""
    from nooch_village.views.inbox import _outcome_form
    from nooch_village.views.projects import _quickadd

    bord = _quickadd("mother_earth__nooch__website_developer", "actief", "t", "/node?id=x")
    assert "/project/nieuw?" in bord and "proj_add" not in bord
    inbox = _outcome_form("project", "n", "t", "tekst", "<option>r</option>", "", "/inbox", "u")
    assert "/project/nieuw?" in inbox and "notif_outcome" not in inbox


def test_de_conventies_staan_opgeschreven():
    """Een regel die alleen in een test staat vindt niemand terug."""
    doc = (ROOT.parent / "docs" / "CONVENTIES.md").read_text(encoding="utf-8")
    for mechaniek in ("NV.swap", "NotifStore", "de wizard", "data-qa-frag"):
        assert mechaniek in doc, mechaniek
    assert "tests/test_conventies_ratchet.py" in doc      # het doc wijst naar zijn eigen poortje
