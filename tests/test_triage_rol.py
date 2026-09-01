"""Bij wie hoort dit? — de classificatiestap vóór de terugval op de Circle Lead.

Werk dat bij niemand terechtkan gaat naar de Circle Lead. Dat is eerlijk (iemand ziet het) maar
armzalig (die iemand moet alles zelf uitzoeken). Deze laag doet ertussenin één ding: een SUGGESTIE
met GROND, zodat de lezer iets te accepteren of te weerspreken heeft.

GEEN GROND, GEEN SUGGESTIE is de hele regel. Het model noemt een rol én citeert de accountability
waarop het matcht; dat citaat wordt daarna DETERMINISTISCH tegen de records gecontroleerd. Klopt het
niet, dan vervalt de suggestie — een verzonnen routering is gevaarlijker dan geen routering, want ze
ziet er precies zo uit als een goede.
"""
from __future__ import annotations

import types

from nooch_village import triage_rol as tr

ACC = "toetst publieke claims aan de geldende wetgeving"


def _records(*, secretary=True, slaapt=False):
    def _rol(rid, accs, parent="cirkel", slaap=False):
        return types.SimpleNamespace(id=rid, parent=parent, archived=False, slaapt=slaap,
                                     definition=types.SimpleNamespace(accountabilities=accs))
    rollen = [_rol("compliance", [ACC, "houdt de claims-database bij"]),
              _rol("website_dev", ["onderhoudt de website en de vindbaarheid"])]
    if secretary:
        rollen.append(_rol("secretary", [tr.SECRETARY_ACCOUNTABILITY], slaap=slaapt))
    return types.SimpleNamespace(all=lambda: rollen,
                                 get=lambda rid: next((r for r in rollen if r.id == rid), None))


def _antwoord(**velden):
    import json
    return lambda *a, **k: json.dumps({"vorm": "project", "rol": "compliance",
                                       "accountability": ACC, "waarom": "gaat over claims", **velden})


# ── de grond ────────────────────────────────────────────────────────────────

def test_een_gegronde_match_citeert_de_accountability():
    uit = tr.classificeer("De claims op de FAQ moeten getoetst worden", _records(),
                          reason_fn=_antwoord())
    assert uit["rol"] == "compliance"
    assert uit["accountability"] == ACC, "het citaat is niet de ECHTE accountability"


def test_een_verzonnen_citaat_laat_de_suggestie_vervallen():
    """DE KERNREGEL. Het model mag het oordeel geven; wij controleren of het ergens op slaat. Een
    citaat dat niet in de records staat is een verzinsel — en gevaarlijker dan zwijgen, want het
    ziet er precies zo uit als een goede match."""
    uit = tr.classificeer("iets", _records(),
                          reason_fn=_antwoord(accountability="bewaakt de merkidentiteit"))
    assert uit["rol"] == "" and "staat niet bij die rol" in uit["grond"]


def test_een_rol_buiten_de_lijst_telt_niet():
    uit = tr.classificeer("iets", _records(), reason_fn=_antwoord(rol="een_verzonnen_rol"))
    assert uit["rol"] == "" and "niet in de lijst" in uit["grond"]


def test_het_model_mag_ook_niets_vinden():
    """"Geen rol" is een geldig antwoord en beter dan een gok."""
    uit = tr.classificeer("iets", _records(), reason_fn=_antwoord(rol="", accountability=""))
    assert uit["rol"] == ""


# ── de vorm ────────────────────────────────────────────────────────────────

def test_de_vorm_heeft_een_voorzet_zonder_model():
    """Gratis, en het antwoord waar we op terugvallen als het model wegvalt."""
    assert tr.vorm_voorzet("Voortaan wekelijks de claims nalopen") == "accountability"
    assert tr.vorm_voorzet("Een compleet overzicht opzetten van alle leveranciers") == "project"
    assert tr.vorm_voorzet("Bel de leverancier over de zolen") == "actie"


def test_een_onzinnige_vorm_valt_terug_op_de_voorzet():
    uit = tr.classificeer("Bel de leverancier", _records(), reason_fn=_antwoord(vorm="banaan"))
    assert uit["vorm"] == "actie"


# ── de faalmodus is saai ───────────────────────────────────────────────────

def test_zonder_wakkere_secretary_geen_suggestie():
    """DE FAALMODUS DIE STEFAN EXPLICIET WILDE: slaapt de rol die dit werk draagt, dan is er geen
    suggestie — en het werk gaat gewoon naar de Circle Lead. Veilig, want de routering hangt hier
    niet van af."""
    for recs in (_records(secretary=False), _records(slaapt=True)):
        uit = tr.classificeer("iets", recs, reason_fn=_antwoord())
        assert uit["rol"] == "" and "classificatie-accountability" in uit["grond"]


def test_zonder_model_geen_suggestie_maar_wel_een_reden():
    def _stuk(*a, **k):
        raise RuntimeError("geen krediet")

    uit = tr.classificeer("iets", _records(), reason_fn=_stuk)
    assert uit["rol"] == "" and "faalde" in uit["grond"]
    assert uit["vorm"] in tr.VORMEN, "de vorm-voorzet hoort te blijven werken zonder model"


def test_een_rol_zonder_accountabilities_is_geen_kandidaat():
    """Matchen op een naam is raden. Zonder accountabilities valt er niets te staven, dus zo'n rol
    doet niet mee — ook niet als hij verder prima wakker is."""
    assert [k["id"] for k in tr._kandidaten(_records())] == ["compliance", "website_dev", "secretary"]
    kaal = types.SimpleNamespace(id="leeg", parent="cirkel", archived=False, slaapt=False,
                                 definition=types.SimpleNamespace(accountabilities=[]))
    recs = types.SimpleNamespace(all=lambda: [kaal], get=lambda rid: kaal)
    assert tr._kandidaten(recs) == []


def test_in_een_lege_cirkel_valt_er_niets_te_matchen():
    """De cirkel-filter kan alle kandidaten wegnemen; dan is zwijgen het enige eerlijke antwoord."""
    uit = tr.classificeer("iets", _records(), cirkel="een_andere_cirkel", reason_fn=_antwoord())
    assert uit["rol"] == "" and "accountabilities" in uit["grond"]


def test_de_eigenaar_wordt_op_accountability_gevonden_niet_op_naam():
    """Drie rollen heten 'Secretary' op prod. Wie het werk draagt staat in zijn DNA, niet in zijn
    titel."""
    assert tr.secretary_rol(_records()) == "secretary"
    assert tr.secretary_rol(_records(secretary=False)) == ""
