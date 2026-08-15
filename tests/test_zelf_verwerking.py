"""De rol verwerkt eerst zelf; de founder is de laatste optie.

De "What do you need?"-boom stond als founder-menu op Stefans bureau — hij mocht kiezen wat er met
andermans spanning gebeurde. Diezelfde boom hoort de eerste handeling van de rol te zijn. Deze
tests leggen die volgorde vast, en vooral de smalte van de founder-categorie: niet "het gaat over
compliance" maar "hier moet iemand tekenen die als enige mag tekenen".
"""
from __future__ import annotations

from nooch_village import zelf_verwerking as zv


class _Def:
    def __init__(self, accs):
        self.accountabilities = list(accs)
        self.purpose = ""
        self.domains = []
        self.name = ""


class _Rec:
    def __init__(self, rid, accs=()):
        self.id = rid
        self.definition = _Def(accs)
        self.archived = False


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


RECS = _Records([
    _Rec("compliance", ["Checking every public claim against EmpCo and ACM guidelines",
                        "Recording evidence in the Chronicle"]),
    _Rec("harry_hemp", ["Gathering scientific evidence by searching OpenAlex and Semantic Scholar"]),
    _Rec("librarian", ["Guarding the approved vocabulary"]),
])


def _llm(antwoord):
    return lambda prompt, **kw: antwoord


def test_werk_in_eigen_domein_lost_de_rol_zelf_op():
    r = zv.verwerk("Gathering scientific evidence by searching OpenAlex for new studies",
                   rol="harry_hemp", records=RECS, gebruik_llm=False)
    assert r["uitkomst"] == zv.ZELF and "OpenAlex" in r["eigen_accountability"]


def test_werk_van_een_ander_gaat_naar_die_rol_niet_naar_de_founder():
    antwoord = '{"role": "librarian", "kind": "missing_capability", "capability": ""}'
    r = zv.verwerk("het goedgekeurde vocabulaire klopt niet meer", rol="harry_hemp",
                   records=RECS, reason_fn=_llm(antwoord))
    assert r["uitkomst"] == zv.NAAR_ROL and r["naar_rol"] == "librarian"


def test_zonder_eigenaar_deelt_de_rol_wat_hij_vond():
    """Niet doorschuiven naar de mens omdat niemand het bezit — delen wat je vond."""
    antwoord = '{"role": "NONE", "kind": "missing_capability", "capability": ""}'
    r = zv.verwerk("iets dat nergens thuishoort", rol="harry_hemp", records=RECS,
                   reason_fn=_llm(antwoord))
    assert r["uitkomst"] == zv.INFO and "deel" in r["reden"]


def test_alleen_een_bevoegdheidsvraag_bereikt_de_founder():
    r = zv.verwerk("⤴ beslissing gevraagd: mag deze geherformuleerde claim live volgens EmpCo?",
                   rol="compliance", records=RECS, gebruik_llm=False)
    assert r["uitkomst"] == zv.FOUNDER
    assert r["domein"] == "compliance"
    assert "alleen jij" in r["behoefte"]


def test_compliance_werk_zonder_besluitvraag_blijft_bij_compliance():
    """'Het gaat over compliance' is niet genoeg. Voorbereiden en onderbouwen is rolwerk."""
    r = zv.verwerk("Checking this public claim against the EmpCo guidelines", rol="compliance",
                   records=RECS, gebruik_llm=False)
    assert r["uitkomst"] == zv.ZELF


def test_een_claim_zonder_bewijs_is_geen_bevoegdheidsvraag():
    """Dat spoor bestaat al (het bewijs-wachtspoor); het is geen founder-bevoegdheid."""
    r = zv.verwerk("⤴ beslissing gevraagd: de claim mist harde bewijzen", rol="compliance",
                   records=RECS, gebruik_llm=False)
    assert r["uitkomst"] != zv.FOUNDER


def test_de_verdeling_telt_wat_onder_de_rollen_bleef():
    rijen = [{"uitkomst": zv.ZELF}, {"uitkomst": zv.ZELF}, {"uitkomst": zv.NAAR_ROL},
             {"uitkomst": zv.FOUNDER}]
    v = zv.verdeling(rijen)
    assert v["totaal"] == 4 and v["naar_de_founder"] == 1 and v["onder_de_rollen"] == 75


def test_het_spoor_is_append_only(tmp_path):
    """Systeemstatus, geen wachtrij: er wordt niets afgevinkt."""
    zv.leg_vast(str(tmp_path), {"rol": "compliance", "uitkomst": zv.ZELF, "tensie": "x"})
    zv.leg_vast(str(tmp_path), {"rol": "harry_hemp", "uitkomst": zv.INFO, "tensie": "y"})
    rijen = zv.alle(str(tmp_path))
    assert len(rijen) == 2 and all("ts" in r for r in rijen)


def test_werk_op_je_eigen_bord_doe_je_gewoon():
    """Uit de eerste meting: 101 van de 172 vielen terug op 'info gedeeld' omdat de woorden niet
    netjes overlapten met een accountability-tekst. Maar het stond al op hún bord — dan is het van
    hen. Het dorp zou anders 101 keer iets gaan delen in plaats van het werk te doen."""
    antwoord = '{"role": "NONE", "kind": "missing_capability", "capability": ""}'
    r = zv.verwerk("een taak die op mijn bord staat maar nergens netjes op matcht",
                   rol="harry_hemp", records=RECS, reason_fn=_llm(antwoord), van_eigen_bord=True)
    assert r["uitkomst"] == zv.ZELF and "eigen bord" in r["reden"]


def test_de_behoefte_regel_leest_als_een_zin():
    """Stond als 'om een claim vrijgeven vrij te geven' op de kaart."""
    r = zv.verwerk("⤴ beslissing gevraagd: mag deze claim live volgens EmpCo?", rol="compliance",
                   records=RECS, gebruik_llm=False)
    assert r["behoefte"] == ("ik heb jou nodig om een claim vrij te geven — dat is een "
                             "bevoegdheid die alleen jij hebt")


def test_een_ontbrekend_certificaat_is_een_bewijs_gat():
    r = zv.verwerk("⤴ beslissing gevraagd: de FAQ claimt circular economy maar mist certificering",
                   rol="compliance", records=RECS, gebruik_llm=False)
    assert r["uitkomst"] != zv.FOUNDER
