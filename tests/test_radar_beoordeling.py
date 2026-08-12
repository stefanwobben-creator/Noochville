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


# ── De strijdigheids-as: citeert de grondwet, geen lijst ────────────────────

def test_een_strijdig_signaal_citeert_het_geschonden_principe(lex):
    """Niet "stond op een lijst" maar "schendt 'geen leer'". Daarmee is de dismiss herleidbaar tot
    de grondwet, en dat is de eis: nooit een black-box dismiss."""
    uit = rb.beoordeel(_sig("Bijenwas-coating voor waterafstotende schoenen",
                            "biobased en volledig afbreekbaar"), lex)
    assert uit["besluit"] == rb.DISMISS_STRIJDIG
    assert uit["principe"] == "geen leer"
    assert "'bijenwas' schendt het principe 'geen leer'" in uit["citaat"]
    assert "dierlijk product" in uit["citaat"]


def test_strijdigheid_werkt_in_beide_talen(lex):
    """Het Lexicon is meertalig en status geldt symmetrisch — een EN-signaal hoort dezelfde dismiss
    te krijgen als zijn NL-tegenhanger."""
    nl = rb.beoordeel(_sig("Bijenwas als coating"), lex)
    en = rb.beoordeel(_sig("Beeswax as a coating"), lex)
    assert nl["besluit"] == en["besluit"] == rb.DISMISS_STRIJDIG
    assert nl["principe"] == en["principe"]


def test_een_samenstelling_wordt_herkend(lex):
    """`[\\w-]` maakte van 'bijenwas-coating' één token en miste het lexicon-woord — terwijl een
    samenstelling juist de normale vorm is waarin zo'n materiaal in een signaal staat."""
    assert rb.beoordeel(_sig("bijenwas-coating"), lex)["besluit"] == rb.DISMISS_STRIJDIG
    assert rb.beoordeel(_sig("wol/zijde-mengsel"), lex)["besluit"] == rb.DISMISS_STRIJDIG


def test_strijdigheid_gaat_voor_relevantie(lex):
    """Bijenwas scoort positief op 'afbreekbaar & biobased' en zou als relevant doorgaan. De
    strijdigheid is de hardere uitspraak en moet dus eerst."""
    from nooch_village.mission import strategie_relevantie
    score, _ = strategie_relevantie("Bijenwas-coating, biobased en afbreekbaar")
    assert score >= 1                                        # het scoort écht relevant…
    assert rb.beoordeel(_sig("Bijenwas-coating, biobased en afbreekbaar"),
                        lex)["besluit"] == rb.DISMISS_STRIJDIG      # …en zakt toch


def test_een_avoid_zonder_principe_dismisst_niet(tmp_path):
    """Een `avoid`-concept zonder `schendt` levert niets citeerbaars op — en een dismiss zonder
    citeerbaar principe is precies de black box die we niet willen."""
    lx = Lexicon(str(tmp_path / "l.json"))
    lx.add_concept("iets", {"nl": "onzinwoord"}, status="avoid", rationale="omdat het kan")
    assert lx.schendt_principe("onzinwoord") is None
    assert rb.beoordeel(_sig("een onzinwoord in de tekst"), lx)["besluit"] != rb.DISMISS_STRIJDIG


# ── De relevantie-as ────────────────────────────────────────────────────────

def test_een_off_strategie_signaal_wordt_weggelegd_met_reden(lex):
    uit = rb.beoordeel(_sig("Nieuwe blockchain-standaard voor NFT-ticketing"), lex)
    assert uit["besluit"] == rb.DISMISS_OFF_STRATEGIE
    assert "raakt geen enkel strategie-thema" in uit["citaat"]


def test_een_relevant_signaal_gaat_naar_een_voorstel(lex):
    uit = rb.beoordeel(_sig("Mycelium-leer uit Europa, composteerbaar"), lex)
    assert uit["besluit"] == rb.NAAR_VOORSTEL
    assert "afbreekbaar & biobased" in uit["themas"]


def test_een_kapotte_strategietoets_legt_niets_weg(monkeypatch, lex):
    """Fail-OPEN op deze as, anders dan elders. Een kapotte toets die alles wegwuift is erger dan
    een kapotte toets die alles doorlaat: het eerste is stil, het tweede zichtbaar."""
    def _stuk(_t):
        raise RuntimeError("mission-module weg")
    monkeypatch.setattr("nooch_village.mission.strategie_relevantie", _stuk)
    assert rb.beoordeel(_sig("wat dan ook"), lex)["besluit"] == rb.NAAR_VOORSTEL


# ── De audit: ongelijk gewogen, en niet-optioneel ──────────────────────────

def test_off_strategie_wordt_zwaarder_bemonsterd_dan_strijdig():
    """Het risico verschilt: een off-strategie-dismiss kan een goed nieuw signaal begraven dat nog
    geen bestaand thema raakt; een vegan-strijdigheid is bijna zeker terecht."""
    assert rb.AUDIT_PCT[rb.DISMISS_OFF_STRATEGIE] > rb.AUDIT_PCT[rb.DISMISS_STRIJDIG]
    n = 400
    off = sum(rb.in_audit(f"s{i}", rb.DISMISS_OFF_STRATEGIE) for i in range(n))
    con = sum(rb.in_audit(f"s{i}", rb.DISMISS_STRIJDIG) for i in range(n))
    assert off > con * 2                                     # ~40% vs ~10%


def test_de_steekproef_is_deterministisch():
    """Geen loterij bij elke render: dezelfde dismiss valt altijd hetzelfde uit."""
    assert all(rb.in_audit("abc", rb.DISMISS_OFF_STRATEGIE) ==
               rb.in_audit("abc", rb.DISMISS_OFF_STRATEGIE) for _ in range(5))


def test_elke_dismiss_wordt_vastgelegd_ook_buiten_de_steekproef(tmp_path, lex):
    """DE regel. Het percentage bepaalt wat er op het SCHERM komt, niet wat er wordt bijgehouden.
    Anders is 'de audit staat uit' één config-regel van een stille drop verwijderd."""
    dd = str(tmp_path)
    for i in range(30):
        s = _sig("Nieuwe blockchain-standaard voor NFT-ticketing", sid=f"sig{i}")
        rb.leg_vast(dd, signaal=s, oordeel=rb.beoordeel(s, lex), rol="harry_hemp")
    rijen = rb.alle(dd)
    assert len(rijen) == 30                                  # alles vastgelegd…
    assert 0 < len(rb.audit_wachtrij(dd)) < 30               # …een deel op het scherm


def test_de_vastlegging_draagt_het_principe_en_de_bron(tmp_path, lex):
    s = _sig("Bijenwas-coating")
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
