"""Done vereist GEEN einddocument. En: `set_dod` schrijft alleen de contractvelden.

DE REGEL IS OMGEDRAAID (4 sep 2026). Hier stond het omgekeerde: `dod_poort` weigerde Done zolang
het einddocument leeg was of alleen de geseede opdracht bevatte (founder 19 jul, verhuisd naar het
document op 21 jul). Stefan heeft die poort ingetrokken.

De reden: de poort keek naar het document, niet naar het werk. Een taak waarvan de titel de
opdracht goed omschrijft en die echt af is, is Done — of er nu iemand een rapport bij schreef of
niet. Dat oordeel hoort bij de mens. Bij het intrekken stonden 65 projecten op deze poort vast
(44 met een leeg document, 21 met alleen de opdracht), gemeten op de draaiende server.

Bewust ook geen zachte variant: geen nudge, geen waarschuwing, geen "weet je het zeker". Die zijn
expliciet afgewezen — half blokkeren houdt de traagheid zonder de zekerheid te leveren.

Waarom dit een test is en geen aantekening: een conventie die je moet onthouden is een
waarschuwing, geen guard. Zou iemand de poort ooit opnieuw invoeren, dan valt deze test om en
leest hij meteen waarom hij weg was.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.projects import ProjectLedger, seed_document

ROLE = "mother_earth__nooch__website_developer"


def test_er_is_geen_document_poort_meer():
    """De functie zelf is weg. Terugkomen mag, maar niet ongemerkt."""
    import nooch_village.projects as P
    assert not hasattr(P, "dod_poort"), (
        "dod_poort is terug. Dat is een beleidswijziging (Done zou weer een document vereisen) "
        "en hoort een eigen besluit te zijn — zie de docstring bovenaan dit bestand.")
    assert not hasattr(P, "is_seed_van_dit_project"), (
        "is_seed_van_dit_project hoorde bij die poort en had daarna geen consument meer. "
        "Voor de weergavevraag is er `heeft_seed_vorm`.")


def _done(tmp_path, doc: str | None):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    done_when = "Er ligt een getal met bron, of de uitleg waarom dat niet kan."
    pid = st.projects.create(ROLE, "Hoeveel massa verliest een schoenzool?", "human",
                             done_when=done_when)
    st.projects.start(pid)
    if doc is not None:
        cockpit2._Stores(dd).project_docs.write(pid, doc)
    _, msg = cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    return cockpit2._Stores(dd).projects.get(pid), msg, done_when


def test_afronden_zonder_enig_einddocument(tmp_path):
    p, msg, _ = _done(tmp_path, None)
    assert p["status"] == "done", msg
    assert not cockpit2.is_weigering(msg), msg


def test_afronden_met_alleen_de_opdracht_in_het_document(tmp_path):
    """Precies het geval dat de poort blokkeerde: het document is nog de seed."""
    seed = seed_document("Er ligt een getal met bron, of de uitleg waarom dat niet kan.")
    p, msg, _ = _done(tmp_path, seed)
    assert p["status"] == "done", msg
    assert not cockpit2.is_weigering(msg), msg


def test_afronden_met_een_geschreven_rapport_blijft_gewoon_werken(tmp_path):
    doc = seed_document("Er ligt een getal met bron.") + "\n\n## Conclusie\nCa. 1-5 g per 100 km."
    p, msg, _ = _done(tmp_path, doc)
    assert p["status"] == "done", msg


def test_de_uitkomst_wordt_nog_steeds_vastgelegd(tmp_path):
    """De poort is weg, de administratie niet: er hoort nog altijd een outcome bij een Done."""
    p, _, _ = _done(tmp_path, None)
    assert (p.get("dod_outcome") or p.get("outcome") or "").strip(), p


# ── ongewijzigd: het DoD-contract zelf ───────────────────────────────────────
def test_set_dod_schrijft_alleen_contractvelden(tmp_path):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("librarian", "Woordenschat-toets", "human")
    assert pj.set_dod(pid, "done_when", "Alle drie de woorden hebben een oordeel.")
    assert pj.set_dod(pid, "dod_outcome", "Twee goedgekeurd, één afgewezen.")
    p = pj.get(pid)
    assert p["done_when"] == "Alle drie de woorden hebben een oordeel."
    assert p["dod_outcome"] == "Twee goedgekeurd, één afgewezen."
    # onbekend veld of onbekend project: geweigerd, niets geschreven
    assert not pj.set_dod(pid, "scope", "hack")
    assert not pj.set_dod("bestaat_niet", "done_when", "x")
    assert pj.get(pid)["scope"] == "Woordenschat-toets"


def test_create_met_done_when(tmp_path):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("website_watcher", "Bezoekersdaling duiden", "human",
                    done_when="Er ligt één verklaring met bewijs, of drie uitgesloten oorzaken.")
    assert pj.get(pid)["done_when"].startswith("Er ligt één verklaring")
