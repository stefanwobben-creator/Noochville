"""Wat er op een founder-kaart staat, en waarom dat geen keuze is.

Twee klachten: "een rol aan een rol" (wie werpt dit op, en welke van mijn verantwoordelijkheden
raakt het?) en de afgekapte dump met Ja/Nee. Zonder de aangesproken accountability weet de founder
niet waarom iets bij hem ligt — dan is tekenen een vinkje, geen besluit.
"""
from __future__ import annotations

from nooch_village import founder_kaart as fk


class _Def:
    def __init__(self, naam, accs):
        self.name = naam
        self.accountabilities = list(accs)
        self.purpose = ""
        self.domains = []


class _Rec:
    def __init__(self, rid, naam, accs=()):
        self.id = rid
        self.definition = _Def(naam, accs)


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


RECS = _Records([
    _Rec(fk.FOUNDER_ROL, "Strategic Lead / Founder Steward", [
        "Shaping overall business strategy and priorities",
        "Telling the Nooch story (press, investors, community)",
        "Leading fundraising and financial strategy",
        "Guarding mission, values and long-term principles",
    ]),
    _Rec("compliance", "Compliance"),
    _Rec("harry_hemp", "Harry Hemp"),
])


class _Projects:
    def __init__(self, d):
        self._p = dict(d)

    def get(self, pid):
        return self._p.get(pid)


def test_de_opwerper_is_nooit_een_rol():
    """De placeholder was letterlijk "een rol". Dan is de afzender onzichtbaar."""
    n = {"id": "n1", "by": "een rol", "project_id": "p1", "snippet": "iets"}
    rol, naam = fk.opwerper(n, _Projects({"p1": {"owner": "compliance"}}), RECS)
    assert rol == "compliance" and naam == "Compliance"


def test_zonder_afzender_zegt_de_kaart_dat_hardop(caplog):
    """Een onbekende afzender is een defect in de keten, geen cosmetisch probleem."""
    with caplog.at_level("WARNING"):
        rol, naam = fk.opwerper({"id": "n2", "by": "een rol"}, _Projects({}), RECS)
    assert rol == "" and "verloren" in naam
    assert "geen opwerper" in caplog.text


def test_de_geraakte_accountability_komt_uit_de_records():
    """De tekst leeft in governance en mag daar wijzigen zonder deze code te breken."""
    acc = fk.geraakte_accountability("compliance", RECS)
    assert acc == "Guarding mission, values and long-term principles"
    assert fk.geraakte_accountability("geld", RECS).startswith("Leading fundraising")


def test_geen_geraakte_accountability_is_zelf_het_antwoord():
    """Raakt een item geen enkele bevoegdheid, dan ligt het hier verkeerd — dat hoort er te staan."""
    n = {"id": "n3", "by": "compliance", "poort": {"deur": "deur_besluit", "klasse": "iets-anders"}}
    k = fk.kaart(n, records=RECS)
    assert k["hoort_hier"] is False
    assert "terug naar de routering" in k["accountability"]


def test_de_kaart_draagt_alle_velden():
    n = {"id": "n4", "by": "compliance", "snippet": "de claim X is herschreven",
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    k = fk.kaart(n, records=RECS, voorstel={
        "voorstel": "keur de herschreven claim goed",
        "ja": "de nieuwe tekst gaat live", "nee": "de claim blijft offline",
        "behoefte": "ik heb jou nodig om een claim vrij te geven — dat mag alleen jij"},
        bewijs="EmpCo Bijlage I 4c + Kroniek-record K1")
    for veld in ("rol", "gevonden", "voorstel", "ja", "nee", "bewijs", "behoefte"):
        assert k[veld], f"{veld} ontbreekt op de kaart"
    tekst = fk.render(k)
    assert "opgeworpen door : Compliance" in tekst
    assert "Ja betekent" in tekst and "Nee betekent" in tekst
    assert "EmpCo" in tekst


def test_de_kaart_toont_de_eigen_accountability_van_de_opwerper():
    """Niet 'jouw rol hierin: <founder-accountability>' — dan leest het alsof de founder de
    spanning voelde. De reden dat het bij hem ligt hoort in de behoefte-regel."""
    recs = _Records([_Rec(fk.FOUNDER_ROL, "Founder", ["Guarding mission, values and principles"]),
                     _Rec("compliance", "Compliance",
                          ["Checking every public claim against EmpCo and ACM"])])
    n = {"id": "n6", "by": "compliance",
         "snippet": "checking this public claim against EmpCo requires a decision",
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    k = fk.kaart(n, records=recs, voorstel={"behoefte": "ik heb jou nodig om dit vrij te geven"})
    assert "claim" in k["vanuit"].lower()
    tekst = fk.render(k)
    assert "vanuit accountability" in tekst
    assert "waarom bij jou" in tekst


def test_een_kaart_zonder_bewijsregel_zegt_dat_ook():
    n = {"id": "n5", "by": "compliance", "snippet": "iets",
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    assert "geen bewijsregel meegeleverd" in fk.render(fk.kaart(n, records=RECS))
