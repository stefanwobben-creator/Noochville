"""Eén logboek voor de twee wekelijkse memo's, en opmaak die als opmaak leest (30 september 2026).

DRIE KLEINE DINGEN UIT HET EERSTE ECHTE GEBRUIK, en ze horen bij elkaar omdat ze allemaal gaan over
wat Stefan te ZIEN krijgt:

  I.   MARKDOWN RENDERT NU BIJ EEN ROL-AFZENDER. `###` en `**vet**` stonden er letterlijk. Dat
       klopte zolang een bericht door een MENS wordt getypt — die plakt een adres en typt geen
       markdown — maar een memo wordt door een model geschreven, en die schrijft wél markdown.
  II.  BEIDE MEMO'S IN ÉÉN KANAAL. Twee gesprekken die je allebei apart moest onthouden te openen,
       terwijl ze over hetzelfde gaan.
  III. DE DRIE DIE ER AL STAAN VERHUIZEN MEE, eenmalig, zodat het logboek van voren af aan klopt.

De grens van I is de reden dat het een tak is en geen vervanging: mens-chat blijft platte tekst.
"""
from __future__ import annotations

import json
import os

import pytest

from nooch_village import channels, cockpit2, noochie_kanaal as K, noochie_memo, weekmemo

BRON, DOEL = K.BRON, K.DOEL


def _b(bid, at, tekst, auteur, soort="role"):
    return {"id": bid, "kind": "comment", "at": float(at), "text": tekst,
            "author": {"type": soort, "id": auteur}}


def _dorp(tmp_path, kanalen: dict):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    with open(os.path.join(dd, "channels.json"), "w", encoding="utf-8") as fh:
        json.dump({"kanalen": kanalen, "namen": {}}, fh)
    return dd


def _echt():
    """De prod-vorm: drie weekmemo's in het village-kanaal, één Noochie-memo in het doel."""
    return {BRON: [_b("w1", 100, "🗂 Weekmemo 2026-W38", "village"),
                   _b("w2", 300, "🗂 Weekmemo 2026-W39", "village"),
                   _b("w3", 500, "🗂 Weekmemo 2026-W40", "village")],
            DOEL: [_b("n1", 400, "🌱 Noochie kijkt naar het dorp", "noochie")]}


def _kan(dd) -> dict:
    with open(os.path.join(dd, "channels.json"), encoding="utf-8") as fh:
        return json.load(fh).get("kanalen", {})


# ══ I. Opmaak ════════════════════════════════════════════════════════════════
def _render(dd, kanaal, ik=""):
    from nooch_village.views.messages import render_messages
    return render_messages(cockpit2._Stores(dd), kanaal=kanaal, csrf_token="TOK", ik=ik)


def test_een_rolbericht_rendert_zijn_markdown(tmp_path):
    tekst = "## Wat er ligt\n\nDe **onderbouwingen** stapelen zich op.\n\n- een punt\n- nog een"
    dd = _dorp(tmp_path, {DOEL: [_b("n1", 100, tekst, "noochie")]})
    h = _render(dd, DOEL)
    assert "<strong>onderbouwingen</strong>" in h
    #  zet een  om in een <h4> — de kopniveaus van die renderer beginnen lager, zodat een
    # bericht nooit met een paginakop concurreert. Wat telt is dat het een KOP is en geen tekens.
    assert "<h4>Wat er ligt</h4>" in h, "de kop staat er nog als tekens"
    assert "## Wat er ligt" not in h


def test_een_mensbericht_blijft_platte_tekst(tmp_path):
    """DE GRENS. Een mens die `**dit**` typt, bedoelt sterretjes — en `_md` loslaten op elk bericht
    verandert bestaand chatgedrag zonder dat iemand erom vroeg."""
    dd = _dorp(tmp_path, {DOEL: [_b("m1", 100, "kijk: **dit** en ## dat", "iemand", soort="human")]})
    h = _render(dd, DOEL)
    assert "**dit**" in h and "<strong>" not in h.split("msg-text")[1][:200]
    assert "## dat" in h


def test_een_link_blijft_klikbaar_bij_allebei(tmp_path):
    """`_md` linkt http(s) zelf; `linkify` doet het voor de mens-tak. Geen van beide mag door deze
    wijziging zijn link verliezen."""
    dd = _dorp(tmp_path, {DOEL: [_b("r1", 100, "zie https://nooch.earth/pagina", "noochie"),
                                 _b("m1", 200, "zie https://nooch.earth/pagina", "x",
                                    soort="human")]})
    h = _render(dd, DOEL)
    assert h.count("href='https://nooch.earth/pagina'") + \
           h.count('href="https://nooch.earth/pagina"') >= 2


# ══ II. Eén kanaal ═══════════════════════════════════════════════════════════
def test_de_weekmemo_schrijft_naar_het_logboek(tmp_path, monkeypatch):
    """HET ADRES VERANDERT, DE ROL NIET. `stuur` leidt het DM-kanaal af uit `by`, dus dezelfde
    waarde als `noochie_memo.AFZENDER` betekent dezelfde draad."""
    from nooch_village import signaal
    gezien: dict = {}

    def _stuur(data_dir, doel_type, doel_id, tekst, **kw):
        gezien.update(doel_type=doel_type, doel_id=doel_id, by=kw.get("by"))
        return ["dm:x"]

    monkeypatch.setattr(signaal, "stuur_en_volg", _stuur)
    weekmemo._bezorg_bij_de_founder(str(tmp_path), "de memo", None)
    assert gezien["by"] == "noochie" == noochie_memo.AFZENDER
    assert gezien["doel_type"] == "role"


def test_de_twee_memos_delen_hun_adres():
    """Zou een van de twee later een andere naam kiezen, dan staan ze weer in twee gesprekken —
    zonder dat iets zich meldt. Daarom staat het hier als vergelijking."""
    assert weekmemo.LOGBOEK == noochie_memo.AFZENDER
    assert weekmemo.AFZENDER == "village", "de herkomst van bestaande berichten is verschoven"


# ══ III. De eenmalige verhuizing ═════════════════════════════════════════════
def test_de_droge_run_schrijft_niets(tmp_path):
    dd = _dorp(tmp_path, _echt())
    voor = _kan(dd)
    v = K.voer_uit(dd, apply=False)
    assert v["verplaatst"] == 3 and v["doel_na"] == 4 and v["toegepast"] is False
    assert _kan(dd) == voor


def test_verplaatsen_houdt_elk_bericht_precies_zoals_het_was(tmp_path):
    """DE KERN. Een verhuizing mag herkomst niet herschrijven: `id`, `at`, `text` en `author`
    blijven staan — óók `author.id == "village"`, want dat is wie het schreef."""
    dd = _dorp(tmp_path, _echt())
    v = K.voer_uit(dd, apply=True)
    assert v["onverwacht"] == [], v["onverwacht"]
    doel = _kan(dd)[DOEL]
    # OP TIJD, DOOR ELKAAR: de Noochie-memo van 400 staat tussen weekmemo 300 en 500 in. Dat is
    # het punt van één logboek — je leest de week in de volgorde waarin hij gebeurde.
    assert [e["id"] for e in doel] == ["w1", "w2", "n1", "w3"], "niet op tijd gesorteerd"
    w1 = next(e for e in doel if e["id"] == "w1")
    assert w1["author"] == {"type": "role", "id": "village"}
    assert w1["at"] == 100 and w1["text"] == "🗂 Weekmemo 2026-W38"


def test_het_bronkanaal_blijft_leeg_bestaan(tmp_path):
    """Niet verwijderen: wie de oude URL nog heeft staan, krijgt een leeg gesprek in plaats van
    een fout. Er komt niets meer bij, want het nieuwe adres is elders."""
    dd = _dorp(tmp_path, _echt())
    K.voer_uit(dd, apply=True)
    kan = _kan(dd)
    assert BRON in kan and kan[BRON] == []


def test_de_volgverwijzing_gaat_mee_weg(tmp_path):
    """Anders houdt de Messages-lijst een leeg gesprek in "Direct" — precies het restant waar
    `ontvolg_allen` voor gemaakt is."""
    dd = _dorp(tmp_path, _echt())
    st = cockpit2._Stores(dd)
    mens = st.people.add("Stefan", "s@nooch.earth")
    st.people.volg(mens.id, BRON)
    v = K.voer_uit(dd, apply=True)
    assert v["ontvolgd"] == 1
    assert not cockpit2._Stores(dd).people.volgt(mens.id, BRON)


def test_een_dubbel_bericht_id_blokkeert_de_verhuizing(tmp_path):
    """Reacties, bewerken en verwijderen zoeken een bericht op id; met twee dezelfde treft elke
    actie het verkeerde — of allebei. Dan hoort hier niets te gebeuren."""
    kanalen = _echt()
    kanalen[DOEL].append(_b("w2", 600, "toevallig hetzelfde id", "noochie"))
    dd = _dorp(tmp_path, kanalen)
    voor = _kan(dd)
    v = K.voer_uit(dd, apply=True)
    assert any("dubbele bericht-id" in b for b in v["blokkades"]), v["blokkades"]
    assert _kan(dd) == voor, "er is tóch geschreven"


def test_een_bericht_zonder_tijdstempel_blokkeert(tmp_path):
    kanalen = _echt()
    kanalen[BRON][0].pop("at")
    dd = _dorp(tmp_path, kanalen)
    v = K.voer_uit(dd, apply=True)
    assert any("zonder tijdstempel" in b for b in v["blokkades"])
    assert _kan(dd)[BRON], "de bron is tóch leeggehaald"


def test_een_tweede_keer_draaien_doet_niets(tmp_path):
    """IDEMPOTENT ZONDER EEN VLAG. Na de verhuizing is de bron leeg, en dan is er niets meer te
    verplaatsen — dat is een blokkade en geen fout."""
    dd = _dorp(tmp_path, _echt())
    K.voer_uit(dd, apply=True)
    na_een = _kan(dd)
    v = K.voer_uit(dd, apply=True)
    assert any("niets te verplaatsen" in b for b in v["blokkades"])
    assert _kan(dd) == na_een


def test_het_logboek_leest_daarna_als_een_draad(tmp_path):
    """DE BEDOELING, GEMETEN OP HET SCHERM: vier memo's op volgorde in één gesprek."""
    dd = _dorp(tmp_path, _echt())
    K.voer_uit(dd, apply=True)
    h = _render(dd, DOEL)
    for tekst in ("2026-W38", "2026-W39", "2026-W40", "Noochie kijkt naar het dorp"):
        assert tekst in h, tekst
    assert h.index("2026-W38") < h.index("2026-W39") < h.index("2026-W40")
