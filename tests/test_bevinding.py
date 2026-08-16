"""De bevinding moet het in één blik doen — er is geen werkoverleg meer.

Wat er binnenkwam haalde dat niet: afgekapte zinnen ("…'Decide whether to permanently exclude this
overl"), interne verpakking, en jargon dat alleen binnen het dorp betekenis heeft. Deze tests
bevriezen de poorten die zulke tekst tegenhouden.

De poorten zijn deterministisch, met opzet: een model dat zijn eigen tekst beoordeelt kijkt zijn
eigen huiswerk na.
"""
from __future__ import annotations

import pytest

from nooch_village import bevinding as bv


GOED = {"spanning": "De tekst op de veelgestelde-vragenpagina zegt dat onze schoenen schoon zijn, "
                    "maar nergens staat wat we daarmee bedoelen of waarop het gebaseerd is.",
        "voorstel": "De zin vervangen door wat we wel kunnen aantonen: gemaakt zonder plastic."}


def test_een_goede_bevinding_komt_erdoor():
    ok, reden = bv.keur(GOED)
    assert ok and reden == ""


@pytest.mark.parametrize("spanning", [
    "Decide whether to permanently exclude this overl",
    "De pagina claimt 'clean' maar",
    "Het project kan niet verder zonder een beslissing over het uitsluiten van 'een overlappend",
])
def test_een_afgekapte_zin_wordt_geweigerd(spanning):
    ok, reden = bv.keur({**GOED, "spanning": spanning})
    assert not ok and ("middenin" in reden or "te kort" in reden)


def test_jargon_wordt_geweigerd():
    """De veertienjarige-toets op onze eigen interne taal — de lezer hoeft onze machinerie niet
    te kennen."""
    ok, reden = bv.keur({**GOED, "spanning": GOED["spanning"] + " De payload van de skill-run "
                                                               "gaf no_data terug."})
    assert not ok and "jargon" in reden


def test_zonder_voorstel_is_het_een_melding_geen_verzoek():
    ok, reden = bv.keur({**GOED, "voorstel": ""})
    assert not ok and "geen concreet voorstel" in reden


def test_licht_werk_mag_zonder_voorstel():
    """Niet elk item hoeft een vraag te dragen; alleen wat verzonden wordt."""
    ok, _ = bv.keur({**GOED, "voorstel": ""}, voorstel_verplicht=False)
    assert ok


def test_de_verpakking_gaat_eraf_voor_het_model_kijkt():
    """`kern` haalt de sjabloonzinnen weg; het model hoort het werk te zien, niet onze boilerplate."""
    ruw = ("⏸️ Project van Harry Hemp vastgelopen op 1 mens-/extern item(s): Deze taak vereist een "
           "mens of externe partij: 'Decide whether to exclude this overlap'")
    gezien = {}

    def _fake(prompt, **kw):
        gezien["prompt"] = prompt
        return '{"spanning": "' + GOED["spanning"] + '", "voorstel": "' + GOED["voorstel"] + '"}'

    uit = bv.herschrijf(ruw, rol="harry_hemp", reason_fn=_fake)
    assert uit["ok"]
    assert "vastgelopen op 1 mens-/extern" not in gezien["prompt"]
    assert "Decide whether to exclude this overlap" in gezien["prompt"]


def test_een_geweigerde_bevinding_degradeert_zichtbaar():
    """Liever zichtbaar onaf dan onzichtbaar onbegrijpelijk."""
    uit = bv.herschrijf("iets", rol="x",
                        reason_fn=lambda p, **kw: '{"spanning": "te kort", "voorstel": ""}')
    assert uit["ok"] is False and uit["reden"]


def test_zonder_antwoord_blijft_de_ruwe_tekst_staan():
    uit = bv.herschrijf("Decide whether to exclude this overlap", rol="x",
                        reason_fn=lambda p, **kw: None)
    assert uit["ok"] is False
    assert uit["ruw"] == "Decide whether to exclude this overlap"


def test_de_prompt_vraagt_om_een_korte_bevinding():
    """Drie van de veertien in de eerste dry-run werden geweigerd op afkapping, en de oorzaak was
    de token-limiet — niet het model. Ruimer budget én een lengte-instructie, want alleen ruimer
    maken nodigt uit tot langere antwoorden die opnieuw net niet passen."""
    gezien = {}
    bv.herschrijf("iets", rol="x",
                  reason_fn=lambda p, **kw: gezien.update(prompt=p, kw=kw) or '{"spanning":"","voorstel":""}')
    assert "HOOGSTENS VIER ZINNEN" in gezien["prompt"]
    assert gezien["kw"]["max_tokens"] >= 1200


def test_een_aangehaalde_term_is_geen_afgekapte_zin():
    """Vals alarm op het echte scherm: "de claim 'compensated' mag pas online…" werd geweigerd
    omdat de enkele aanhalingstekens oneven uitkwamen. In gewone tekst is die vaker een apostrof
    ("Nooch's") dan een citaat; een valse afwijzing kost een leesbare kaart."""
    assert bv.afgekapt("De claim 'compensated' mag pas online als het certificaat er is.") is False
    assert bv.afgekapt('Hij zei "dit mag niet.') is True          # dubbele telt wel
