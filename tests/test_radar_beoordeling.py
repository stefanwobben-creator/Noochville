"""Rol-beoordeling van radar-signalen: de founder ziet voorstellen, geen signalen.

De radar dumpte rauwe signalen op de founder om te triëren. Dat is hetzelfde menu-model dat we voor
compliance-claims hebben afgeschaft — "rising Xero Shoes" is geen voorstel, en beoordelen of iets
het volgen waard is, is rolwerk.

Fase 1 op harry_hemp (21 wachtende materiaalsignalen), niet op concurrent_scout (5): de grotere set
geeft een bruikbaarder verhouding, én materiaalsignalen oefenen de moeilijke helft — de
vegan-strijdigheid — terwijl concurrent-signalen vooral off-segment-relevantie zijn.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from unittest.mock import patch

from nooch_village import radar_beoordeling as rb
from nooch_village.lexicon import Lexicon
from nooch_village.seeds import seed_lexicon


@pytest.fixture
def lex(tmp_path):
    lx = Lexicon(str(tmp_path / "lexicon.json"))
    seed_lexicon(lx)
    return lx


def _sig(content, rationale="", feed="Material Innovation", sid="s1"):
    return {"id": sid, "content": content, "rationale": rationale, "feed": feed,
            "role": "harry_hemp", "source": "biorxiv.org"}


# ── De strijdigheids-as: classificatie, gegrond en geauditeerd ─────────────

_REASON = "nooch_village.llm.reason"


def _classificeert(categorie, materiaal, citaat):
    """Stub voor de materiaal-classificatie."""
    import json as _j
    return lambda p, **kw: _j.dumps({"categorie": categorie, "materiaal": materiaal,
                                     "citaat": citaat})


def test_een_samenstelling_wordt_nu_wel_gevangen(lex):
    """DE reden voor deze herijking. Het lexicon kent 'wol', maar 'schapenwol' is één token en
    matchte niet — en dát is de normale vorm waarin een materiaal in een signaal staat. Gemeten:
    nul strijdig-dismisses over 21 materiaalsignalen terwijl er minstens één echte in zat, met een
    rationale die het nota bene aanprees als afbreekbaar alternatief."""
    sig = _sig("Hergebruik van ongewenste schapenwol voor textieltoepassingen",
               "Wol is een natuurlijke, biologisch afbreekbare vezel")
    with patch(_REASON, _classificeert("dierlijk", "schapenwol", "ongewenste schapenwol")):
        uit = rb.beoordeel(sig, lex)
    assert uit["besluit"] == rb.DISMISS_STRIJDIG
    assert uit["principe"] == "geen leer"
    assert "schapenwol" in uit["citaat"] and "geen leer" in uit["citaat"]


def test_de_categorie_bepaalt_het_principe_deterministisch(lex):
    """De classificatie kiest de categorie; de PRINCIPE-toewijzing is een tabel. Zo blijft de reden
    herleidbaar tot de grondwet, ook als het materiaal nergens in een lijst staat."""
    for cat, principe in (("dierlijk", "geen leer"), ("plastic", "geen plastic"),
                          ("niet_eu", "in europa geproduceerd")):
        with patch(_REASON, _classificeert(cat, "iets", "een materiaal")):
            uit = rb.beoordeel(_sig("een materiaal in de tekst"), lex)
        assert uit["principe"] == principe, cat


def test_zonder_citaat_geen_dismiss(lex):
    """Ongegrond = geen dismiss. Dezelfde regel als overal: een oordeel zonder aanwijsbare grond
    gaat niet door."""
    with patch(_REASON, _classificeert("dierlijk", "wol", "")):
        assert rb.beoordeel(_sig("wol in de tekst"), lex)["besluit"] != rb.DISMISS_STRIJDIG


def test_een_verzonnen_citaat_wordt_verworpen(lex):
    """Het citaat moet ECHT in het signaal staan. Zonder die controle is de grondslag een bewering
    van het model over zichzelf — dezelfde fout als een verzonnen bron."""
    with patch(_REASON, _classificeert("dierlijk", "wol", "dit staat er helemaal niet")):
        assert rb.beoordeel(_sig("iets over textiel"), lex)["besluit"] != rb.DISMISS_STRIJDIG


def test_geen_of_onbekende_categorie_dismisst_niet(lex):
    for cat in ("geen", "", "verzonnen_categorie"):
        with patch(_REASON, _classificeert(cat, "mycelium", "mycelium")):
            assert rb.beoordeel(_sig("mycelium uit Europa"), lex)["besluit"] != rb.DISMISS_STRIJDIG


def test_een_kapotte_classificatie_legt_niets_weg(lex):
    """Fail-OPEN. Een as die stilletjes wegwuift is erger dan een as die niets doet: het eerste is
    onzichtbaar, het tweede staat gewoon in de wachtrij."""
    for antwoord in (None, "", "geen json", '{"kapot":'):
        with patch(_REASON, lambda p, **kw: antwoord):
            assert rb.beoordeel(_sig("wol"), lex)["besluit"] != rb.DISMISS_STRIJDIG


def test_strijdigheid_gaat_voor_relevantie(lex):
    """Wol scoort positief op 'afbreekbaar & biobased' en zou als relevant doorgaan. De
    strijdigheid is de hardere uitspraak en moet dus eerst."""
    from nooch_village.mission import strategie_relevantie
    assert strategie_relevantie("schapenwol, biologisch afbreekbaar")[0] >= 1
    with patch(_REASON, _classificeert("dierlijk", "wol", "schapenwol")):
        uit = rb.beoordeel(_sig("schapenwol, biologisch afbreekbaar"), lex)
    assert uit["besluit"] == rb.DISMISS_STRIJDIG


def test_elke_strijdig_dismiss_gaat_langs_de_founder():
    """De prijs van een classificatie in plaats van een regel: 100% audit tot Stefan er genoeg heeft
    gezien om te verlagen. Geen classificatie zonder controle."""
    assert rb.AUDIT_PCT[rb.DISMISS_STRIJDIG] == 100
    assert all(rb.in_audit(f"s{i}", rb.DISMISS_STRIJDIG) for i in range(50))


# ── De relevantie-as ────────────────────────────────────────────────────────

def test_de_relevantie_as_legt_niets_meer_weg_op_de_materiaal_feed(lex):
    """Gemeten op de 21: 18 door, 3 af, en geen enkele echte strijdigheid gevangen. De reden is
    structureel — de feed is al materiaal-selectief, dus vrijwel elk signaal raakt 'afbreekbaar &
    biobased' of 'geen plastic'. Een filter dat op zijn eigen invoerselectie meet, discrimineert
    niet."""
    with patch(_REASON, _classificeert("geen", "", "")):
        uit = rb.beoordeel(_sig("Nieuwe blockchain-standaard voor NFT-ticketing"), lex)
    assert uit["besluit"] == rb.NAAR_VOORSTEL
    assert "Material Innovation" not in rb.RELEVANTIE_DISMIST_OP


def test_de_relevantie_as_dismisst_wel_op_een_brede_feed(lex):
    """Op een feed die niet vooraf op onderwerp geselecteerd is, discrimineert hij wél."""
    with patch(_REASON, _classificeert("geen", "", "")):
        uit = rb.beoordeel(_sig("Nieuwe blockchain-standaard voor NFT-ticketing",
                                feed="Competitor Watch"), lex)
    assert uit["besluit"] == rb.DISMISS_OFF_STRATEGIE
    assert "raakt geen enkel strategie-thema" in uit["citaat"]


def test_de_score_reist_mee_als_zwak_signaal(lex):
    """Retireren als dismiss-criterium is niet hetzelfde als weggooien."""
    with patch(_REASON, _classificeert("geen", "", "")):
        uit = rb.beoordeel(_sig("Mycelium-leer uit Europa, composteerbaar"), lex)
    assert uit["besluit"] == rb.NAAR_VOORSTEL and uit["themas"]


def test_een_relevant_signaal_gaat_naar_een_voorstel(lex):
    with patch(_REASON, _classificeert("geen", "", "")):
        uit = rb.beoordeel(_sig("Mycelium-leer uit Europa, composteerbaar"), lex)
    assert uit["besluit"] == rb.NAAR_VOORSTEL
    assert "afbreekbaar & biobased" in uit["themas"]


def test_een_kapotte_strategietoets_legt_niets_weg(monkeypatch, lex):
    """Fail-OPEN op deze as, anders dan elders. Een kapotte toets die alles wegwuift is erger dan
    een kapotte toets die alles doorlaat: het eerste is stil, het tweede zichtbaar."""
    def _stuk(_t):
        raise RuntimeError("mission-module weg")
    monkeypatch.setattr("nooch_village.mission.strategie_relevantie", _stuk)
    with patch(_REASON, _classificeert("geen", "", "")):
        assert rb.beoordeel(_sig("wat dan ook"), lex)["besluit"] == rb.NAAR_VOORSTEL


# ── De audit: ongelijk gewogen, en niet-optioneel ──────────────────────────

def test_de_off_strategie_steekproef_is_een_deelverzameling():
    """Blijft bemonsterd, niet volledig: die as is regel-gebaseerd en verandert niet."""
    n = 400
    off = sum(rb.in_audit(f"s{i}", rb.DISMISS_OFF_STRATEGIE) for i in range(n))
    assert 0 < off < n


def test_de_steekproef_is_deterministisch():
    """Geen loterij bij elke render: dezelfde dismiss valt altijd hetzelfde uit."""
    assert all(rb.in_audit("abc", rb.DISMISS_OFF_STRATEGIE) ==
               rb.in_audit("abc", rb.DISMISS_OFF_STRATEGIE) for _ in range(5))


def test_elke_dismiss_wordt_vastgelegd_ook_buiten_de_steekproef(tmp_path, lex):
    """DE regel. Het percentage bepaalt wat er op het SCHERM komt, niet wat er wordt bijgehouden.
    Anders is 'de audit staat uit' één config-regel van een stille drop verwijderd."""
    dd = str(tmp_path)
    for i in range(30):
        s = _sig("Nieuwe blockchain-standaard voor NFT-ticketing", sid=f"sig{i}",
                 feed="Competitor Watch")
        with patch(_REASON, _classificeert("geen", "", "")):
            rb.leg_vast(dd, signaal=s, oordeel=rb.beoordeel(s, lex), rol="harry_hemp")
    rijen = rb.alle(dd)
    assert len(rijen) == 30                                  # alles vastgelegd…
    assert 0 < len(rb.audit_wachtrij(dd)) < 30               # …een deel op het scherm


def test_de_vastlegging_draagt_het_principe_en_de_bron(tmp_path, lex):
    s = _sig("Bijenwas-coating")
    with patch(_REASON, _classificeert("dierlijk", "bijenwas", "Bijenwas-coating")):
        rij = rb.leg_vast(str(tmp_path), signaal=s, oordeel=rb.beoordeel(s, lex), rol="harry_hemp")
    assert rij["as"] == rb.DISMISS_STRIJDIG and rij["principe"] == "geen leer"
    assert rij["bron"] == "biorxiv.org" and rij["rol"] == "harry_hemp"


# ── De router: skill-eigenaarschap, niet accountability ────────────────────

class _Rec:
    def __init__(self, rid, skills):
        self.id = rid
        self.definition = type("D", (), {"skills": skills, "domains": []})()


def test_de_router_matcht_op_skill_eigenaarschap():
    """De geparkeerde router-vraag. Een concurrent-signaal hoort bij de rol die `competitor_news`
    bezit, niet bij de rol wiens accountability-tekst toevallig woorden deelt."""
    recs = [_Rec("harry_hemp", ["openalex_evidence"]), _Rec("concurrent_scout", ["competitor_news"])]
    rol, waarom = rb.rol_voor({"feed": "Competitor Watch", "role": "harry_hemp"}, recs)
    assert rol == "concurrent_scout" and "competitor_news" in waarom
    assert "feed-toewijzing wees naar 'harry_hemp'" in waarom


def test_de_router_valt_terug_op_de_feed_toewijzing():
    """Fail-soft: een signaal verdwijnt nooit doordat de router niets weet."""
    recs = [_Rec("harry_hemp", ["openalex_evidence"])]
    rol, waarom = rb.rol_voor({"feed": "Onbekende Feed", "role": "harry_hemp"}, recs)
    assert rol == "harry_hemp" and "geen skill-regel" in waarom

    rol2, waarom2 = rb.rol_voor({"feed": "Competitor Watch", "role": "harry_hemp"}, recs)
    assert rol2 == "harry_hemp" and "niemand bezit 'competitor_news'" in waarom2


def test_materiaalsignalen_komen_bij_harry_hemp():
    recs = [_Rec("harry_hemp", ["openalex_evidence"]), _Rec("concurrent_scout", ["competitor_news"])]
    rol, _ = rb.rol_voor({"feed": "Material Innovation", "role": "harry_hemp"}, recs)
    assert rol == "harry_hemp"
