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


# ── Wat de handmatige steekproef op 17 overdrachten blootlegde ──────────────

def test_de_rol_zelf_staat_in_de_kandidatenlijst():
    """De grootste misser-oorzaak: `match(van_rol=rol)` gaf de rol door als EXCLUDE aan de
    router-roster, dus stond hij niet in zijn eigen kandidatenlijst en kon de match nooit "dit is
    van jou" antwoorden. Gevolg: de copywriter gaf het herschrijven van een claim weg, compliance
    stuurde zijn eigen juridische oordeel naar de Librarian."""
    antwoord = '{"role": "compliance", "kind": "missing_capability", "capability": ""}'
    r = zv.verwerk("toets deze publieke claim aan de EmpCo-richtlijn", rol="compliance",
                   records=RECS, reason_fn=_llm(antwoord))
    # ZELF via de eigen-accountability-check of via de match maakt niet uit; het gaat erom dat het
    # werk NIET wordt weggegeven aan een ander bureau.
    assert r["uitkomst"] == zv.ZELF and r["naar_rol"] == ""


def test_werk_gaat_nooit_via_een_overdracht_naar_de_founder_rol():
    """Uit de steekproef: de financial controller schoof het jaarverslag naar de founder-rol. Dat
    omzeilt de hele poort — de founder bereik je via de bevoegdheidsvraag, niet via een handover."""
    from nooch_village.founder_kaart import FOUNDER_ROL
    recs = _Records([_Rec("financial_controller", ["Bookkeeping"]),
                     _Rec(FOUNDER_ROL, ["Leading fundraising and financial strategy"])])
    antwoord = ('{"role": "' + FOUNDER_ROL + '", "kind": "missing_capability", "capability": ""}')
    r = zv.verwerk("2025 annual report completed and submitted", rol="financial_controller",
                   records=recs, reason_fn=_llm(antwoord))
    assert r["uitkomst"] != zv.NAAR_ROL


def test_een_cirkel_kan_geen_werk_ontvangen():
    """Een cirkel heeft geen handen (harde regel 7): werk erheen schuiven laat het verdwijnen in
    een niveau in plaats van bij iemand."""
    from nooch_village import org
    import unittest.mock as m
    antwoord = '{"role": "librarian", "kind": "missing_capability", "capability": ""}'
    with m.patch.object(org, "is_circle", lambda rec: True):
        r = zv.verwerk("iets", rol="compliance", records=RECS, reason_fn=_llm(antwoord))
    assert r["uitkomst"] != zv.NAAR_ROL


# ── De Librarian-grens: route op DOEL, niet op trefwoord ────────────────────
#
# Dezelfde soort guard als op de founder-poort, en om dezelfde reden: dit lek komt terug zodra
# niemand oplet. De Librarian bezit alleen het lexicon als artefact — welke termen approved of
# avoid zijn en waarom. Dat er een woord, term of claim in de tekst staat is geen routeersignaal
# maar juist de val.

def _domein_recs():
    class _D:
        def __init__(self, dom, accs=()):
            self.domains = list(dom)
            self.accountabilities = list(accs)
            self.purpose = ""
            self.name = ""

    class _R:
        def __init__(self, rid, dom, accs=()):
            self.id = rid
            self.definition = _D(dom, accs)
            self.archived = False

    class _Recs:
        def __init__(self, r):
            self._r = {x.id: x for x in r}

        def get(self, i):
            return self._r.get(i)

        def all(self):
            return list(self._r.values())

    return _Recs([_R("librarian", ["bibliotheek"], ["Guarding the approved vocabulary"]),
                  _R("compliance", ["claim-verification"], ["Toetsen aan EmpCo"]),
                  _R("harry_hemp", [], ["Gathering scientific evidence"])])


def test_een_claim_scan_gaat_naar_compliance_niet_naar_de_librarian():
    """Uit de steekproef: twee claim-scans landden bij de Librarian omdat er 'term' in stond."""
    recs = _domein_recs()
    rol, waarom = zv.domein_grens("librarian",
                                  "Claim-scan: 4 model-gevonden claim(s) zonder lijstterm", recs)
    assert rol == "compliance" and "claim-domein" in waarom


def test_een_te_brede_query_is_onderzoeksmethode_geen_lexicon():
    recs = _domein_recs()
    rol, waarom = zv.domein_grens("librarian",
                                  "Flag if the searches return an excessively broad result set", recs)
    assert rol != "librarian" and "onderzoeksmethode" in waarom


def test_echte_lexicon_curatie_blijft_bij_de_librarian():
    """De grens mag niet doorschieten: het lexicon is wél van de Librarian."""
    recs = _domein_recs()
    rol, waarom = zv.domein_grens("librarian",
                                  "Evalueer of het woord 'regenerative' in het lexicon mag", recs)
    assert rol == "librarian" and waarom == ""


def test_een_term_in_de_tekst_is_geen_routeersignaal():
    """De val, expliciet: geen lexicon-doel, geen claim-doel, geen methode-doel → geen overdracht."""
    recs = _domein_recs()
    rol, waarom = zv.domein_grens("librarian", "de term staat op de verpakking van batch 3", recs)
    assert rol == "" and "geen routeersignaal" in waarom


def test_de_grens_geldt_alleen_voor_de_lexicon_houder():
    """Andere ontvangers worden niet aangeraakt — dit is een grens, geen algemene herrouteerder."""
    recs = _domein_recs()
    rol, waarom = zv.domein_grens("compliance", "Claim-scan: iets", recs)
    assert rol == "compliance" and waarom == ""


def test_de_rollen_komen_uit_hun_domein_niet_uit_hun_id():
    """Een id kan hernoemd worden; een domein dragen is een governance-besluit."""
    recs = _domein_recs()
    assert zv._rol_met_domein(recs, zv._LEXICON_DOMEIN) == "librarian"
    assert zv._rol_met_domein(recs, zv._CLAIM_DOMEIN) == "compliance"
    assert zv._rol_met_domein(recs, zv._METHODE_DOMEIN) == ""      # governance-gat, geen gok


def test_meervoud_telt_als_hetzelfde_woord():
    """Exacte tokenmatch liet 'claim' en 'claims' als verschillende woorden gelden, waardoor de
    eigen-accountability-check vrijwel nooit aansloeg — en dan leest werk dat een rol duidelijk
    bezit als 'niet van mij'. Zichtbaar geworden op het scherm: de kaart toonde geen 'vanuit
    accountability'-regel bij een claim-item van compliance."""
    # Twee woorden moeten aansluiten: 'claim(s)' en 'EmpCo'. Zonder prefix-vergelijking telde
    # alleen 'EmpCo' en bleef de check onder de drempel.
    assert zv._woorden("de claims toetsen") & zv._woorden("een claim beoordelen") == {"claim"}
    recs = _domein_recs()
    acc = zv.eigen_domein("toets de claims aan de EmpCo-richtlijn", "compliance", recs)
    assert acc == "Toetsen aan EmpCo"


# ── Het vierde type: governance ─────────────────────────────────────────────

def test_terugkerend_werk_zonder_eigenaar_is_een_governance_voorstel():
    """Het antwoord is geen handeling maar een wijziging in wie waarvoor staat."""
    r = zv.verwerk("dit komt wekelijks terug en geen enkele rol heeft hier een accountability voor",
                   rol="compliance", records=RECS, gebruik_llm=False)
    assert r["uitkomst"] == zv.GOVERNANCE


def test_een_klacht_zonder_structuur_object_is_geen_governance():
    """"Dit gebeurt vaker" zonder object is een klacht, geen structuurvoorstel."""
    r = zv.verwerk("dit gebeurt telkens weer en het kost me veel tijd", rol="compliance",
                   records=RECS, gebruik_llm=False)
    assert r["uitkomst"] != zv.GOVERNANCE


def test_een_rol_noemen_zonder_herhaling_is_gewoon_werk():
    r = zv.verwerk("de rol van compliance moet deze claim beoordelen", rol="compliance",
                   records=RECS, gebruik_llm=False)
    assert r["uitkomst"] != zv.GOVERNANCE
