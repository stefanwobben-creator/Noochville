"""De copy-checker-view: dekking, groepering en de grens tussen laag 1 en laag 2."""
from __future__ import annotations

import types

from nooch_village.views import copy_check


class _Att:
    """Minimale AttachmentStore-dubbel: alleen `get`, want de view leest niets anders."""

    def __init__(self, bodies: dict[str, str]):
        self._b = bodies

    def get(self, pid):
        if pid not in self._b:
            return None
        return types.SimpleNamespace(id=pid, title=pid, body=self._b[pid])


VUIL = ("We cut emissions by 40% last year. Hey friend, join the movement.")

BODIES = {
    "COPYCHECK-001": ('Never write: friend, join the movement.\n\n'
                      '```check\n{"verboden": ["friend", "join the movement"]}\n```\n'),
    "POSITIONSTAT-001": ('Percentages without a source are never claimed.\n\n'
                         '```check\n{"regels": '
                         '{"percentage_zonder_bron": "Percentages without a source"}}\n```\n'),
    "TONEOFVOICE-001": ('Never write: friend.\n\n'
                        '```check\n{"verboden": ["friend"]}\n```\n'),
    # STANCE draagt bewust GEEN blok: al zijn statements zijn houdingen. Zie #422.
    "STANCE-001": "This governs how we stand. Nothing here is legally testable.",
}


def _att():
    return _Att(dict(BODIES))


def test_dekking_noemt_alleen_policies_met_een_blok():
    """VALSE DEKKING IS ERGER DAN GEEN DEKKING. STANCE-001 heeft geen structuurblok, dus er is
    niets aan getoetst — hem in de dekkingsregel noemen zou een controle claimen die niet bestond."""
    dekking = copy_check._dekking(_att())
    assert dekking == ["COPYCHECK-001", "POSITIONSTAT-001", "TONEOFVOICE-001"]
    assert "STANCE-001" not in dekking


def test_schone_tekst_toont_waartegen_er_gecheckt_is():
    """'Niets gevonden' zonder te zeggen waartegen, laat de lezer denken dat alles gedekt is."""
    html = copy_check._rapport(_att(), "We make shoes from plants.")
    assert "Nothing found" in html
    for pid in ("COPYCHECK-001", "POSITIONSTAT-001", "TONEOFVOICE-001"):
        assert pid in html.split("Layer 2")[0]
    # de dekkingsregel zelf claimt STANCE niet
    assert "STANCE-001" not in html.split("Layer 2")[0]


def test_een_zin_een_regel_met_alle_bronpolicies_eronder():
    """`friend` staat in twee policies. De CHECKER meldt dat twee keer — eerlijk, geen dedupe — en
    de VIEW vouwt het tot één zin met beide bronnen. Presentatie mag samenvatten, de meting niet."""
    rauw = [b for b in _rauw(VUIL) if "friend" in b["citaat"]]
    assert len(rauw) == 3                                     # friend x2, join the movement x1
    assert sorted({b["policy"] for b in rauw}) == ["COPYCHECK-001", "TONEOFVOICE-001"]

    groepen = copy_check._groepeer(_rauw(VUIL), VUIL)
    assert len(groepen) == 2                                  # twee zinnen, niet vier bevindingen
    friend = [g for g in groepen if "friend" in g["citaat"]][0]
    assert friend["policies"] == ["COPYCHECK-001", "TONEOFVOICE-001"]


def test_de_zinnen_staan_in_de_volgorde_van_de_TEKST():
    """`check_alles` loopt per POLICY, dus de tweede zin kan als laatste terugkomen als alleen de
    derde policy hem noemt. Dan leest het scherm als een klachtenlijst in plaats van als de tekst,
    en moet de schrijver zoeken waar hij is."""
    groepen = copy_check._groepeer(_rauw(VUIL), VUIL)
    posities = [VUIL.find(g["citaat"]) for g in groepen]
    assert posities == sorted(posities)


def _rauw(tekst):
    from nooch_village import copycheck
    return copycheck.check_alles(tekst, _att())


def test_de_percentage_regel_komt_van_een_policy_niet_uit_de_code():
    """Haal het blok van POSITIONSTAT weg en de regel vuurt niet meer. Zat hij in de code, dan
    bleef hij vuren — en dan meet de teller de code in plaats van de policies."""
    zonder = dict(BODIES)
    zonder["POSITIONSTAT-001"] = "Percentages without a source are never claimed."
    from nooch_village import copycheck
    hits = copycheck.check_alles("We cut emissions by 40% last year.", _Att(zonder))
    assert [h for h in hits if "percentage" in h["regel"]] == []


def test_elke_bevinding_draagt_een_bronpolicy():
    """De gevolg-invariant uit #422, hier als schermbelofte: kan de view een bevinding niet aan een
    policy koppelen, dan is dat geen presentatiegat maar een regel die nergens hoort."""
    for b in _rauw(VUIL):
        assert b.get("policy"), b


def test_laag_2_draagt_ook_de_policies_zonder_blok():
    """De grens uit #421: wat laag 1 niet kan tellen, weegt laag 2. STANCE hoort daar juist wél in
    — hij bepaalt de houding, en dat is precies wat een model kan beoordelen."""
    prompt = copy_check._laag2_prompt(_att(), "some copy")
    assert "STANCE-001" in prompt and "how we stand" in prompt
    assert "some copy" in prompt
    # en hij vraagt niet om herhaling van laag 1
    assert "Do NOT repeat those" in prompt
