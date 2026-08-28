"""Waar werk uit een overleg landt — en waar het NOOIT meer mag landen.

Stefan legde negen acties vast en zag ze nergens terug. Ze waren niet weg: ze hingen als
checklist-items aan "het eerste lopende project van deze eigenaar" — letterlijk de eerste die de
store toevallig teruggaf. Vier ongerelateerde acties belandden zo op één project waar ze niets mee
te maken hadden, en de PERSOON die de actie kreeg werd bij de bestemming niet eens gebruikt.

Die bug is stil: er is geen foutmelding, het scherm zegt "✓ opgeslagen", en het werk staat er echt
— alleen op een plek waar niemand kijkt. Precies het soort fout dat terugsluipt bij de eerstvolgende
refactor. Daarom staat hij hier vast, zoals de inline-style-ratchet en de fragment-ratchet dat voor
hun klasse doen:

  1. GEDRAG — een actie landt in de inbox van de gekozen persoon, nooit als checklist-item;
  2. CODE   — de aanhaak-helper `_outcome_action` wordt vanuit het overleg-pad niet meer aangeroepen.

De tweede is de ratchet: gedrag kun je per ongeluk terugdraaien met een regel die de test niet
raakt, maar de aanroep zelf is te tellen.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"
ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _punt(dd, tekst):
    cockpit2.dispatch(dd, "vangst_add", {"circle": [C], "punt": [tekst], "next": ["/"]},
                      username="guest")
    return cockpit2._Stores(dd).werk.punten(C)[0]["id"]


def _persoon(dd):
    st = cockpit2._Stores(dd)
    p = st.people.all()[0]
    st.assign.assign(RID, "person", p.id)
    return p


# ── 1. gedrag ───────────────────────────────────────────────────────────────

def test_een_actie_landt_bij_de_persoon_en_nergens_anders(tmp_path):
    dd = _dd(tmp_path)
    p = _persoon(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Klacht")
    _nxt, msg = cockpit2.dispatch(dd, "vangst_uitkomst",
                                  {"circle": [C], "iid": [iid], "otype": ["actie"],
                                   "persoon": [p.id], "tekst": ["reply to complaint e-mail"],
                                   "next": ["/"]}, username="guest")
    assert msg.startswith("✓")
    st = cockpit2._Stores(dd)
    ns = [n for n in st.notif.all() if "reply to complaint" in (n.get("snippet") or "")]
    assert len(ns) == 1, "de actie hoort precies één keer in een postbus te liggen"
    assert (ns[0]["target_type"], ns[0]["target_id"]) == ("person", p.id)
    assert ns[0]["type"] == "actie"
    los = [t for pr in st.projects.all() for cl in (pr.get("checklists") or [])
           for t in (cl.get("items") or []) if "reply to complaint" in (t.get("text") or "")]
    assert los == [], f"actie als checklist-item op een vreemd project: {los}"


def test_een_actie_maakt_geen_checklist_item_op_een_lopend_project(tmp_path):
    """De regressie in zijn scherpste vorm: een lopend project van de eigenaar bestaat, en de
    actie mag er tóch niet in verdwijnen."""
    dd = _dd(tmp_path)
    p = _persoon(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(f"ii:{C}", "Een lopend project van deze cirkel", "human")
    st.projects.start(pid)
    voor = len([t for pr in st.projects.all() for cl in (pr.get("checklists") or [])
                for t in (cl.get("items") or [])])
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    iid = _punt(dd, "Klacht")
    cockpit2.dispatch(dd, "vangst_uitkomst",
                      {"circle": [C], "iid": [iid], "otype": ["actie"], "persoon": [p.id],
                       "tekst": ["iets kleins"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    na = len([t for pr in st.projects.all() for cl in (pr.get("checklists") or [])
              for t in (cl.get("items") or [])])
    assert na == voor, "er is een checklist-item bijgekomen — de oude aanhaak-route is terug"


# ── 2. de ratchet op de code zelf ───────────────────────────────────────────

# `_outcome_action` haakt een regel aan een BESTAAND project. Dat blijft een legitieme helper: in de
# inbox kiest de mens zélf het project waar de regel bij hoort. Verboden is alleen de plek waar het
# project werd GERADEN — het overleg-pad.
_AANROEP = re.compile(r"_outcome_action\s*\(")

# Totaal aantal treffers in de codebase (1 definitie + 3 aanroepen vanuit de inbox, waar de mens
# het project aanwijst). MONOTOON DALEND: verdwijnt er een aanroep, verlaag het getal. Stijgt hij,
# dan is er ergens een nieuwe plek die een project raadt — en dat is precies de bug.
PLAFOND_TOTAAL = 4


def test_de_overleg_uitkomst_haakt_niets_meer_aan_een_geraden_project():
    """De directe poort: de functie die een overleg-uitkomst wegschrijft mag deze helper niet
    aanroepen. Daar werd het project geraden ("de eerste die de store teruggaf")."""
    import inspect

    bron = inspect.getsource(cockpit2._act_vangst_uitkomst)
    assert "_outcome_action" not in bron, (
        "de overleg-uitkomst haakt weer een actie aan een project — werk uit een overleg gaat naar "
        "de inbox van de persoon die het kreeg")


def test_de_aanhaak_helper_kruipt_nergens_anders_binnen():
    """De ratchet eromheen: gedrag kun je terugdraaien met een regel die geen test raakt, een
    extra aanroep niet."""
    totaal, waar = 0, {}
    for f in sorted(ROOT.rglob("*.py")):
        n = len(_AANROEP.findall(f.read_text(encoding="utf-8")))
        if n:
            waar[str(f.relative_to(ROOT))] = n
            totaal += n
    assert totaal <= PLAFOND_TOTAAL, (
        f"meer aanroepen van _outcome_action dan afgesproken ({totaal} > {PLAFOND_TOTAAL}): {waar}. "
        "Een project raden is de bug; laat de mens het aanwijzen of stuur het naar een postbus.")
    assert totaal == PLAFOND_TOTAAL, (
        f"schuld opgeruimd ({totaal} < {PLAFOND_TOTAAL}) — verlaag PLAFOND_TOTAAL zodat de ratchet "
        f"vastzet: {waar}")
