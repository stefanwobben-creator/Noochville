"""Bronverrijking: de betekenis hoort bij de bron, niet bij de lezer.

Van de 28 gedegradeerde voorstellen ging 61% niet over fout redeneren maar over ONTBREKENDE
betekenis. `claims_check` gaf `score=100`, `rood=0`, `bevindingen=[]` en liet de lezer invullen wat
dat betekent. De synthese las "compliant", de critic zag een ongegronde gevolgtrekking, en beide
hadden gelijk — de betekenis stond nergens.

Drie verrijkingen, in volgorde van hefboom:
  1. `overgeslagen` als citeerbaar feit      1 claim
  2. de read-only paginacheck                3 claims
  3. deterministische betekenis-strings     10 claims

Alles REGEL-GEBASEERD. Een model dat de betekenis raadt zou confabulatie bij de bron zijn, en dat is
erger dan geen betekenis: dan draagt het verzinsel het gezag van de bron.
"""
from __future__ import annotations

import pytest

from nooch_village.skills_impl.claims_check import betekenis_van

LEEG = {"score": 100, "rood": 0, "oranje": 0, "groen": 0, "escaleren": 0, "bevindingen": []}


# ── 3. De betekenis-regels ──────────────────────────────────────────────────

def test_de_lege_run_wordt_benoemd_als_lege_run():
    """DE grote hefboom: 16 van de 28 rustten hierop. score=100 las als 'compliant'."""
    regels = betekenis_van(LEEG)
    assert len(regels) == 1
    assert "lege run" in regels[0] and "GEEN goedkeuring" in regels[0]
    assert "geen uitspraak over of de claim houdbaar is" in regels[0]


def test_geen_treffer_is_niet_hetzelfde_als_compliant():
    regels = betekenis_van({**LEEG, "score": 88})
    assert "niet hetzelfde als compliant" in regels[0]
    assert "zegt niets over de inhoud" in regels[0]


def test_een_bevinding_over_een_andere_term_wordt_gemarkeerd():
    """Twee degradaties gingen hierover: het voorstel behandelde een bevinding over term X alsof
    die bij de onderzochte claim hoorde."""
    uit = betekenis_van({**LEEG, "rood": 1, "bevindingen": [{"term": "plasticvrij"}]},
                        "Together we are revolutionizing footwear")
    assert any("gaat over de term 'plasticvrij', niet over de onderzochte claim" in r for r in uit)


def test_bij_twijfel_geen_melding_over_een_andere_term():
    """Bewust ruim: een onterechte 'gaat over een andere term' duwt een correcte bevinding weg, en
    dat is de duurdere fout."""
    uit = betekenis_van({**LEEG, "rood": 1, "bevindingen": [{"term": "plasticvrij"}]},
                        "is de claim plasticvrij houdbaar")
    assert not any("niet over de onderzochte claim" in r for r in uit)
    zonder_claim = betekenis_van({**LEEG, "rood": 1, "bevindingen": [{"term": "x"}]}, "")
    assert not any("niet over de onderzochte claim" in r for r in zonder_claim)


def test_het_alternatief_is_geen_goedgekeurde_tekst():
    uit = betekenis_van({**LEEG, "rood": 1,
                         "bevindingen": [{"term": "duurzaam", "alternatief": "noem de bron"}]},
                        "duurzaam")
    assert any("VOORGESTELD alternatief" in r and "geen goedgekeurde vervangtekst" in r for r in uit)


def test_een_gewone_uitslag_krijgt_geen_ruis():
    assert betekenis_van({**LEEG, "score": 88, "rood": 1,
                          "bevindingen": [{"term": "duurzaam"}]}, "duurzaam") == []


def test_de_strings_zeggen_wat_de_data_NIET_vaststelt():
    """Liever te terughoudend dan te toeschietelijk: een te sterke string is confabulatie bij de
    bron, en die draagt dan het gezag van de bron."""
    alles = " ".join(betekenis_van(LEEG) + betekenis_van({**LEEG, "score": 88}))
    for verboden in ("compliant is", "is goedgekeurd", "mag live", "is houdbaar"):
        assert verboden not in alles
    assert "GEEN goedkeuring" in alles and "niet hetzelfde als compliant" in alles


def test_de_betekenis_is_regel_gebaseerd_geen_model():
    """Geen LLM in dit pad. Een geraden betekenis zou het probleem verplaatsen, niet oplossen."""
    src = open("nooch_village/skills_impl/claims_check.py", encoding="utf-8").read()
    kern = src[src.index("def betekenis_van"):]
    for model_spoor in ("reason(", "llm", "prompt"):
        assert model_spoor not in kern.lower(), f"'{model_spoor}' hoort niet in de betekenis-regels"


def test_claims_check_levert_de_betekenis_zelf_mee():
    """Sinds scope 56 heet de lijst `toelichting` (metadata voor de uitvoerlaag): als `betekenis`
    won hij als 'langste lijst' van de bevindingen en toonde de wall-note vier disclaimers in plaats
    van de rode treffer. En een lege run is `no_data` mét de lege-run-regel als reden — 📭 "reported,
    nothing found", geen geslaagd resultaat met een disclaimer als antwoord."""
    from unittest.mock import patch
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
    with patch("nooch_village.claims_db.check_tekst", lambda *a, **k: dict(LEEG)):
        uit = ClaimsCheckSkill().run({"text": "iets"}, None)
    assert uit["ok"] is True and "lege run" in " ".join(uit["toelichting"])
    assert uit["no_data"] is True and "GEEN goedkeuring" in uit["reason"]















