"""Spelvraag (founder, 19 jul): de claim is informatie, de vraag is verleiding. Drie
borgingen: (1) de vraag wordt gegenereerd, gevalideerd en gecachet — één LLM-call per
cluster, daarna nul; (2) de hallucinatie-guard weigert cijfers/jaartallen die niet
letterlijk in de kaarten staan; (3) fail-soft: geen bruikbare vraag → None (de kaart
toont de claim), en een mislukking wordt pas na het retry-venster opnieuw geprobeerd."""
from __future__ import annotations

from nooch_village.spelvraag import _grond_ok, _valide, vraag_voor

KAND = {"atom_ids": ["a1", "a2"], "hunch": "De Green Claims Directive ligt stil."}
ATOMS = {
    "a1": {"claim": "De ECGT-richtlijn treedt op 27 september 2026 in werking en "
                    "introduceert nieuwe beperkingen op misleidende milieuclaims."},
    "a2": {"claim": "De Green Claims Directive, die regels zou moeten bieden voor de "
                    "onderbouwing van claims, is nog in beraad bij de Raad zonder "
                    "duidelijke tijdlijn."},
}
_VRAAG = ("Hoe onderbouwt een bedrijf zijn milieuclaims vanaf 27 september 2026, "
          "als de Green Claims Directive zonder tijdlijn in beraad blijft?")


def test_vraag_wordt_gegenereerd_en_gecachet(tmp_path):
    calls = []

    def fake(prompt, **kw):
        calls.append(prompt)
        return _VRAAG

    v1 = vraag_voor(KAND, ATOMS, data_dir=str(tmp_path), reason_fn=fake)
    assert v1 == _VRAAG
    assert "27 september 2026" in calls[0]           # de kaarten zitten in de prompt
    v2 = vraag_voor(KAND, ATOMS, data_dir=str(tmp_path), reason_fn=fake)
    assert v2 == v1 and len(calls) == 1              # cache: precies één LLM-call


def test_hallucinatie_guard():
    bron = "De ECGT-richtlijn treedt op 27 september 2026 in werking."
    assert _grond_ok("Wat betekent 27 september 2026 voor onze claims?", bron)
    assert not _grond_ok("Wat verandert er in 2027 aan claims?", bron)      # jaartal-smokkel
    assert not _grond_ok("Klopt de beloofde 40% reductie wel?", bron)       # percentage-smokkel
    assert not _grond_ok("Gaat dit over 1000 paar schoenen?", bron)         # groot getal


def test_valide_afkeuringen():
    assert _valide("Dit is geen vraag maar een bewering over kaarten.", "x") is None
    assert _valide("Te kort?", "x") is None
    assert _valide(None, "x") is None
    assert _valide('  "Is dit een nette vraag over de kaarten in dit cluster?"  ', "x") \
        == "Is dit een nette vraag over de kaarten in dit cluster?"


def test_fail_soft_en_retry_venster(tmp_path):
    # ladder geeft niets → None, en de mislukking wordt met tijdstempel gecachet
    assert vraag_voor(KAND, ATOMS, data_dir=str(tmp_path),
                      reason_fn=lambda *a, **k: None, nu=1000.0) is None
    calls = []

    def fake(prompt, **kw):
        calls.append(1)
        return _VRAAG

    # binnen het retry-venster: geen nieuwe call, nog steeds fail-soft
    assert vraag_voor(KAND, ATOMS, data_dir=str(tmp_path),
                      reason_fn=fake, nu=2000.0) is None
    assert calls == []
    # na het venster (24h): één nieuwe poging, die slaagt
    assert vraag_voor(KAND, ATOMS, data_dir=str(tmp_path),
                      reason_fn=fake, nu=1000.0 + 25 * 3600) == _VRAAG
    assert calls == [1]


def test_gehallucineerde_vraag_valt_terug_op_claim(tmp_path):
    # het model smokkelt een jaartal dat nergens in de kaarten staat → None
    assert vraag_voor(KAND, ATOMS, data_dir=str(tmp_path),
                      reason_fn=lambda *a, **k:
                      "Wat betekent het verbod van 2031 voor Nooch?", nu=1.0) is None
