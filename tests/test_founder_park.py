"""Parkeren is een agenda-besluit, geen oordeel.

De wachtrij liep vol met dingen waar de founder niets zinnigs over kón beslissen: compliance-
bevindingen over een site die wordt herbouwd, en rauwe radar-signalen die nog door geen rol zijn
beoordeeld. Wegklikken als `verwerp` zou ze opruimen én de Founder Flow iets onwaars leren.

Het onderscheid moet STRUCTUREEL zijn, niet conventie: zodra een parkering in de labelstroom landt,
is elke afgeleide meting stilletjes vervuild — precies de klasse fout die deze codebase deze week
op vier plekken heeft weggehaald.
"""
from __future__ import annotations

import pytest

from nooch_village import founder_flow as ff
from nooch_village import founder_park as fp


def test_parkeren_schrijft_niet_in_de_labelstroom(tmp_path):
    """DE regel. Een label telt mee in de overeenstemming, de Wilson-poort en de drift; een
    parkering nergens in."""
    dd = str(tmp_path)
    fp.park(dd, taak=ff.VOORSTEL, items=["a", "b", "c"], reden="relaunch")
    assert fp.geparkeerd(dd, ff.VOORSTEL) == {"a", "b", "c"}
    assert ff.alle(dd) == []                                  # geen enkel label bijgeschreven
    assert ff.overeenstemming(ff.alle(dd), ff.VOORSTEL, 60)["n"] == 0


def test_een_parkering_draagt_altijd_een_terugkeer_voorwaarde(tmp_path):
    """'Later' zonder trigger is weggooien met een vriendelijker woord."""
    dd = str(tmp_path)
    fp.park(dd, taak=ff.RADAR, items=["s1"], reden="rol_triage")
    rij = fp.alle(dd)[0]
    assert rij["reden"] == "rol_triage"
    assert "zodra de rol" in rij["voorwaarde"]
    assert all(r for r in fp.REDENEN.values())                # elke reden heeft er een


def test_een_onbekende_reden_parkeert_niets(tmp_path):
    """Vrije tekst zou de terugkeer-voorwaarde optioneel maken, en dan is parkeren alsnog weggooien."""
    dd = str(tmp_path)
    assert fp.park(dd, taak=ff.VOORSTEL, items=["a"], reden="ff niet nu") == 0
    assert fp.geparkeerd(dd, ff.VOORSTEL) == set()


def test_parkeren_is_idempotent(tmp_path):
    dd = str(tmp_path)
    assert fp.park(dd, taak=ff.VOORSTEL, items=["a", "b"], reden="relaunch") == 2
    assert fp.park(dd, taak=ff.VOORSTEL, items=["a", "b"], reden="relaunch") == 0
    assert fp.park(dd, taak=ff.VOORSTEL, items=["b", "c"], reden="relaunch") == 1


def test_terughalen_herschrijft_niets(tmp_path):
    """Append-only, zoals elke andere reeks hier: een 'terug'-regel erbij, niets gewist."""
    dd = str(tmp_path)
    fp.park(dd, taak=ff.VOORSTEL, items=["a", "b"], reden="relaunch")
    fp.haal_terug(dd, taak=ff.VOORSTEL, item="a")
    assert fp.geparkeerd(dd, ff.VOORSTEL) == {"b"}
    assert len(fp.alle(dd)) == 3                              # 2 parkeringen + 1 terugregel


def test_parkeringen_zijn_per_taak_gescheiden(tmp_path):
    dd = str(tmp_path)
    fp.park(dd, taak=ff.VOORSTEL, items=["x"], reden="relaunch")
    fp.park(dd, taak=ff.RADAR, items=["x"], reden="rol_triage")
    assert fp.geparkeerd(dd, ff.VOORSTEL) == {"x"} and fp.geparkeerd(dd, ff.RADAR) == {"x"}
    fp.haal_terug(dd, taak=ff.RADAR, item="x")
    assert fp.geparkeerd(dd, ff.VOORSTEL) == {"x"} and fp.geparkeerd(dd, ff.RADAR) == set()


def test_de_wachtrij_toont_geparkeerde_items_niet(tmp_path, monkeypatch):
    from nooch_village import founder_taken as ft
    dd = str(tmp_path)
    monkeypatch.setitem(ft._WACHTRIJEN, ff.VOORSTEL,
                        lambda st, d, n="A": [{"item": i, "titel": i, "detail": "", "context": "",
                                               "link": "", "ai": None, "ai_waarom": ""}
                                              for i in ("a", "b", "c")])
    assert len(ft.wachtrij(None, dd, ff.VOORSTEL)) == 3
    fp.park(dd, taak=ff.VOORSTEL, items=["a", "b"], reden="relaunch")
    assert [i["item"] for i in ft.wachtrij(None, dd, ff.VOORSTEL)] == ["c"]


def test_telling_per_taak_en_reden(tmp_path):
    dd = str(tmp_path)
    fp.park(dd, taak=ff.VOORSTEL, items=["a", "b"], reden="relaunch")
    fp.park(dd, taak=ff.RADAR, items=["s1"], reden="rol_triage")
    t = fp.telling(dd)
    assert t[ff.VOORSTEL]["relaunch"] == 2 and t[ff.RADAR]["rol_triage"] == 1


# ── De weergaveregel: rauwe signalen zijn geen founderwerk ──────────────────

def test_een_signaal_met_een_beoordelende_rol_verdwijnt_van_de_wachtrij():
    """Eindtoestand van de omkering, alvast als weergaveregel: de founder ziet voorstellen, geen
    signalen. Het signaal wacht in de radar tot zijn rol het oppakt."""
    from nooch_village import founder_taken as ft

    class _Rec:
        id = "harry_hemp"
        definition = type("D", (), {"skills": ["openalex_evidence"], "domains": []})()

    assert ft._heeft_beoordelaar({"feed": "Material Innovation", "role": "harry_hemp"}, [_Rec()])


def test_een_signaal_zonder_beoordelaar_blijft_staan():
    """Anders is dit een stille drop: een signaal dat nergens meer landt."""
    from nooch_village import founder_taken as ft

    class _Rec:
        id = "iemand_anders"
        definition = type("D", (), {"skills": ["iets_anders"], "domains": []})()

    assert ft._heeft_beoordelaar({"feed": "Onbekende Feed", "role": "niemand"}, []) is False
    assert ft._heeft_beoordelaar({"feed": "Competitor Watch", "role": "weg"}, [_Rec()]) is False
