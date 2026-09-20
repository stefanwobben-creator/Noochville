"""De weekronde: verzamelen → wat nog niet is voorgelegd → één memo → bij de founder.

WAT HIER BEWAAKT WORDT, in volgorde van hoe duur de fout is die het voorkomt:

1. **Het adres is vast.** De memo gaat naar de founder-ROL. Er is geen tak die 'de juiste rol'
   kiest — dat wás de oude uitgang (`claims_board`), en een model dat een ontvanger aanwijst wijst
   werk toe (CLAUDE.md, "AI is instrument, geen rol").
2. **Geen stille week.** Markeren gebeurt ná bezorging. Komt de DM nergens aan, dan blijft de week
   open en probeert de volgende puls opnieuw — anders boekt een week als gedaan terwijl niemand
   iets zag.
3. **Eén stukke bron maakt de memo niet stil.** Bij vijf losse memo's viel er één weg; hier zou
   één uitzondering alles wegnemen. Wat misging staat in het rapport, en dus in de memo.
4. **Het geheugen is er één, voor alle vijf.** Wat is voorgelegd komt niet terug; wat nooit is
   voorgelegd wel — ook als het oud is (de eerste ronde begint met een leeg boek).
"""
from __future__ import annotations

import types

import pytest

from nooch_village import weekmemo


@pytest.fixture
def bronnen(monkeypatch):
    """De vijf adapters, stuurbaar per test. `None` = deze bron gooit een uitzondering."""
    from nooch_village import claims_context, claims_modelpas, legal_signaal, materiaal_memo
    from nooch_village.skills_impl import claim_evidence

    staat: dict = {"legal": [], "claim_regex": [], "claim_model": [], "bewijs": [],
                   "materiaal": []}

    def _lever(naam):
        def _f(*a, **kw):
            uit = staat[naam]
            if uit is None:
                raise RuntimeError(f"{naam} is stuk")
            return list(uit)
        return _f

    monkeypatch.setattr(legal_signaal, "verzamel", _lever("legal"))
    monkeypatch.setattr(claims_context, "verzamel", _lever("claim_regex"))
    monkeypatch.setattr(claims_modelpas, "verzamel", _lever("claim_model"))
    monkeypatch.setattr(claim_evidence, "verzamel", _lever("bewijs"))
    monkeypatch.setattr(materiaal_memo, "verzamel", _lever("materiaal"))
    return staat


def _sig(bron="legal", herkomst="a1", tekst="er is iets gebeurd"):
    return weekmemo.Signaal(bron=bron, tekst=tekst, vindplaats="https://x/1",
                            gevonden_op=1_700_000_000.0, herkomst=herkomst)


def _omg(tmp_path):
    """Een omgeving met `records`, zodat de materiaal-adapter geen cockpit-stores hoeft te bouwen."""
    return types.SimpleNamespace(data_dir=str(tmp_path), records=object())


def _geen_model(prompt, **kw):
    """Geen synthese: de memo valt terug op de kale opsomming. Dat houdt de tests over het RITME
    los van de tekst — wat het model ervan maakt is hier niet de vraag."""
    return ""


# ── 1. verzamelen over vijf bronnen ──────────────────────────────────────────────────────────

def test_verzamel_alles_haalt_alle_vijf_de_bronnen_op(tmp_path, bronnen):
    bronnen["legal"] = [_sig("legal", "l1")]
    bronnen["claim_regex"] = [_sig("claim_regex", "r1")]
    bronnen["claim_model"] = [_sig("claim_model", "m1")]
    bronnen["bewijs"] = [_sig("bewijs", "b1")]
    bronnen["materiaal"] = [_sig("materiaal", "t1")]
    signalen, rapport = weekmemo.verzamel_alles(str(tmp_path), omgeving=_omg(tmp_path))
    assert {s.bron for s in signalen} == {"legal", "claim_regex", "claim_model", "bewijs",
                                          "materiaal"}
    assert {b: v["aantal"] for b, v in rapport.items()} == {
        "legal": 1, "claim_regex": 1, "claim_model": 1, "bewijs": 1, "materiaal": 1}


def test_een_stukke_bron_maakt_de_andere_vier_niet_stil(tmp_path, bronnen):
    """GEEN DATA IS GEEN NUL. De uitval staat in het rapport, niet alleen in een logregel."""
    bronnen["legal"] = None                                   # gooit
    bronnen["claim_model"] = [_sig("claim_model", "m1")]
    signalen, rapport = weekmemo.verzamel_alles(str(tmp_path), omgeving=_omg(tmp_path))
    assert [s.herkomst for s in signalen] == ["m1"]
    assert "RuntimeError" in rapport["legal"]["fout"]
    assert rapport["claim_model"] == {"aantal": 1}
    # En de lezer ziet het verschil tussen 'niets gevonden' en 'niet gelezen':
    regel = weekmemo._bron_regels(rapport)
    assert "legal: NIET GELEZEN" in regel and "claim_regex: 0" in regel


def test_de_kale_memo_draagt_het_bronrapport(tmp_path, bronnen):
    tekst = weekmemo._kaal([_sig()], "2026-W38", {"legal": {"aantal": 1},
                                                  "bewijs": {"fout": "OSError: weg"}})
    assert "Bronnen deze ronde:" in tekst and "bewijs: NIET GELEZEN" in tekst


# ── 2. de eerste ronde, met een leeg geheugen ────────────────────────────────────────────────

def test_de_eerste_ronde_legt_alles_voor_en_vult_daarna_het_boek(tmp_path, bronnen):
    """DE EERSTE KEER. Het boek is leeg, dus niets is ooit voorgelegd en alles is nieuw — ook een
    signaal van maanden terug dat toevallig nog in het venster valt. Dat is met opzet: de pijplijn
    heeft geen geschiedenis en mag er geen verzinnen."""
    assert weekmemo.voorgelegd(str(tmp_path)) == {}           # niets, dit is de eerste keer
    bronnen["legal"] = [_sig("legal", "l1"), _sig("legal", "l2")]
    bronnen["bewijs"] = [_sig("bewijs", "b1")]
    bezorgd: list = []
    uit = weekmemo.ronde(str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W38",
                         reason_fn=_geen_model,
                         bezorg=lambda dd, tekst, omg: bezorgd.append(tekst) or ["dm:stefan"])
    assert uit["gedraaid"] is True and uit["aantal"] == 3
    assert len(bezorgd) == 1 and "3 stuks" in bezorgd[0]
    assert set(weekmemo.voorgelegd(str(tmp_path))) == {"l1", "l2", "b1"}
    assert weekmemo.al_gedraaid(str(tmp_path), "2026-W38") is True


def test_dezelfde_week_draait_niet_twee_keer(tmp_path, bronnen):
    bronnen["legal"] = [_sig("legal", "l1")]
    bezorgd: list = []
    haal = lambda: weekmemo.ronde(                            # noqa: E731
        str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W38", reason_fn=_geen_model,
        bezorg=lambda dd, t, o: bezorgd.append(t) or ["dm:stefan"])
    haal()
    tweede = haal()
    assert tweede["gedraaid"] is False and "al gedraaid" in tweede["reden"]
    assert len(bezorgd) == 1


def test_wat_is_voorgelegd_komt_de_week_erna_niet_terug(tmp_path, bronnen):
    bronnen["legal"] = [_sig("legal", "l1")]
    bezorgd: list = []
    bezorg = lambda dd, t, o: bezorgd.append(t) or ["dm:stefan"]   # noqa: E731
    weekmemo.ronde(str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W38",
                   reason_fn=_geen_model, bezorg=bezorg)
    bronnen["legal"] = [_sig("legal", "l1"),                       # oud nieuws
                        _sig("legal", "l2", "een verse wetswijziging")]
    uit = weekmemo.ronde(str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W39",
                         reason_fn=_geen_model, bezorg=bezorg)
    assert uit["aantal"] == 1                                 # alleen het nieuwe signaal
    assert "een verse wetswijziging" in bezorgd[1]
    assert bezorgd[1].count("- [legal]") == 1                 # l1 staat er niet nog eens bij


# ── 3. de stille week, en de mislukte bezorging ──────────────────────────────────────────────

def test_een_lege_ronde_stuurt_geen_memo_maar_markeert_wel(tmp_path, bronnen):
    """Een memo die 'niets gevonden' meldt leert je hem ongeopend weg te klikken. Markeren doet hij
    wél: anders verzamelt de daemon elke dag van de week opnieuw om weer op nul uit te komen."""
    bezorgd: list = []
    uit = weekmemo.ronde(str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W38",
                         reason_fn=_geen_model,
                         bezorg=lambda dd, t, o: bezorgd.append(t) or ["dm:stefan"])
    assert bezorgd == [] and uit["tekst"] == ""
    assert weekmemo.al_gedraaid(str(tmp_path), "2026-W38") is True


def test_een_mislukte_bezorging_laat_de_week_open(tmp_path, bronnen):
    """DE VEILIGHEID VAN DE VOLGORDE. Markeren vóór bezorgen zou een week stil verliezen: het ritme
    zegt 'gedaan' terwijl niemand iets heeft gezien, en het boek zegt 'voorgelegd' over een signaal
    dat nooit is voorgelegd."""
    bronnen["legal"] = [_sig("legal", "l1")]
    uit = weekmemo.ronde(str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W38",
                         reason_fn=_geen_model, bezorg=lambda dd, t, o: [])
    assert uit["gedraaid"] is False and "niet gemarkeerd" in uit["reden"]
    assert weekmemo.al_gedraaid(str(tmp_path), "2026-W38") is False
    assert weekmemo.voorgelegd(str(tmp_path)) == {}           # het boek is niet vervuild


def test_een_droge_run_schrijft_niets(tmp_path, bronnen):
    bronnen["legal"] = [_sig("legal", "l1")]
    uit = weekmemo.ronde(str(tmp_path), omgeving=_omg(tmp_path), periode="2026-W38",
                         reason_fn=_geen_model, dry=True)
    assert uit["tekst"] and uit["gedraaid"] is False
    assert weekmemo.al_gedraaid(str(tmp_path), "2026-W38") is False
    assert weekmemo.voorgelegd(str(tmp_path)) == {}


# ── 4. het adres ─────────────────────────────────────────────────────────────────────────────

def test_de_memo_gaat_altijd_naar_de_founder_rol(tmp_path, monkeypatch):
    """DE GUARD. Geen lookup, geen model, geen 'meest passende rol' — één adres dat niet kan
    verschuiven. Wie het werk oppakt, beslist de mens die de memo leest."""
    from nooch_village import signaal
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    gezien: dict = {}

    def _stuur(data_dir, doel_type, doel_id, tekst, **kw):
        gezien.update(doel_type=doel_type, doel_id=doel_id, tekst=tekst, by=kw.get("by"))
        return ["dm:stefan"]

    monkeypatch.setattr(signaal, "stuur_op_pad", _stuur)
    kanalen = weekmemo._bezorg_bij_de_founder(str(tmp_path), "de memo", None)
    assert kanalen == ["dm:stefan"]
    assert gezien["doel_type"] == "role" and gezien["doel_id"] == FOUNDER_ROLE_ID
    assert gezien["by"] == weekmemo.AFZENDER


def test_de_ronde_kiest_geen_ontvanger(tmp_path):
    """Structureel, niet op gedrag: in `ronde` en `_bezorg_bij_de_founder` staat geen enkele
    verwijzing naar een rol-keuze. Een gedragstest zou een nieuwe tak missen die alleen in een
    zeldzaam geval vuurt."""
    import inspect
    bron = inspect.getsource(weekmemo.ronde) + inspect.getsource(weekmemo._bezorg_bij_de_founder)
    code = "\n".join(r for r in bron.splitlines() if not r.strip().startswith("#"))
    for verboden in ("classificeer", "menselijke_eigenaar", "kies_ontvanger", "rol_voor"):
        assert verboden not in code
