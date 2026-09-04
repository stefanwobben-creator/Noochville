"""De materiaal-memo's: ritme, geheugen, en een nul die zichzelf verklaart.

WAAROM DIT BESTAAT. De radar produceert al dagelijks (423 items in de feed Material Innovation),
maar er was geen UITGANG: 84 items stonden te wachten en 181 goedgekeurde gingen nergens heen. Dit
is de uitgang — als memo, niet als store, want de kennisbank-meting liet zien dat 96% van de atomen
wereldkennis is die het model al heeft.
"""
from __future__ import annotations

import json
import time
import types

from nooch_village import materiaal_memo as mm


def _radar(*items, rollen=()):
    """Een dorp met alleen wat de memo aanraakt: de radar-stroom en de records voor de ontvanger."""
    class _R:
        @staticmethod
        def all_items():
            return list(items)

    class _Recs:
        @staticmethod
        def all():
            return list(rollen)
    return types.SimpleNamespace(radar=_R(), records=_Recs())


def _item(content, *, status="goedgekeurd", feed=mm.FEED, at=None, link="", source="bron.nl"):
    return {"content": content, "status": status, "feed": feed,
            "at": at if at is not None else time.time(), "link": link, "source": source}


# ── het ritme ─────────────────────────────────────────────────────────────────────────────────

def test_hij_draait_een_kwartaal_maar_een_keer(tmp_path):
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    st = _radar(_item("mycelium wordt schaalbaar"))
    skill = mm.MateriaalKwartaalSkill()

    eerste = skill.run({"_stores": st, "_periode": "2026-Q3"}, ctx)
    assert eerste["skipped"] is False and eerste["aantal"] == 1

    tweede = skill.run({"_stores": st, "_periode": "2026-Q3"}, ctx)
    assert tweede["skipped"] is True and "al gedraaid" in tweede["reden"]

    derde = skill.run({"_stores": st, "_periode": "2026-Q4"}, ctx)
    assert derde["skipped"] is False          # nieuw kwartaal, opnieuw


def test_een_lege_periode_zegt_WAAROM(tmp_path):
    """#426: een nul zonder reden laat de lezer raden of we niets vonden of niet gekeken hebben."""
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    uit = mm.MateriaalKwartaalSkill().run({"_stores": _radar(), "_periode": "2026-Q3"}, ctx)
    assert uit["aantal"] == 0 and "geen goedgekeurde signalen" in uit["reden"]


def test_alleen_goedgekeurde_signalen_tellen(tmp_path):
    """Een wachtend item is nog niet beoordeeld; een afgewezen item is dat wél — negatief. Beide in
    een memo stoppen gooit het oordeel weg dat er al ligt."""
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    st = _radar(_item("ja", status="goedgekeurd"),
                _item("nee", status="afgewezen"),
                _item("later", status="wacht"),
                _item("ander onderwerp", feed="Competitor Watch"))
    uit = mm.MateriaalKwartaalSkill().run({"_stores": st, "_periode": "2026-Q3"}, ctx)
    assert uit["aantal"] == 1


def test_oude_signalen_vallen_buiten_het_venster(tmp_path):
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    oud = time.time() - (200 * 24 * 3600)
    uit = mm.MateriaalKwartaalSkill().run(
        {"_stores": _radar(_item("van vorig jaar", at=oud)), "_periode": "2026-Q3"}, ctx)
    assert uit["aantal"] == 0


# ── het geheugen ──────────────────────────────────────────────────────────────────────────────

def test_wat_is_voorgelegd_wordt_onthouden(tmp_path):
    """ZONDER DIT WORDT DE RADAR RUIS. De feed blijft dezelfde ontdekking aanleveren; een filter
    zonder geheugen kent geen verschil tussen 'nieuw' en 'vorige maand al afgewezen'."""
    d = str(tmp_path)
    assert mm.voorgelegd(d) == {}
    mm.onthoud_voorgelegd(d, ["https://a.nl/mycelium", "https://b.nl/pha"])
    boek = mm.voorgelegd(d)
    assert set(boek) == {"https://a.nl/mycelium", "https://b.nl/pha"}
    assert boek["https://a.nl/mycelium"]["oordeel"] == ""       # nog geen antwoord


def test_een_nee_wordt_vastgelegd_en_blijft_staan(tmp_path):
    d = str(tmp_path)
    mm.onthoud_voorgelegd(d, ["https://a.nl/mycelium"])
    assert mm.noteer_oordeel(d, "https://a.nl/mycelium", "nee") is True
    assert mm.voorgelegd(d)["https://a.nl/mycelium"]["oordeel"] == "nee"
    # onthoud opnieuw mag het oordeel niet wissen
    mm.onthoud_voorgelegd(d, ["https://a.nl/mycelium"])
    assert mm.voorgelegd(d)["https://a.nl/mycelium"]["oordeel"] == "nee"


def test_een_oordeel_op_iets_onbekends_is_geen_stille_no_op(tmp_path):
    assert mm.noteer_oordeel(str(tmp_path), "nooit voorgelegd", "nee") is False


def test_de_sleutel_is_de_LINK_en_niet_de_tekst():
    """Dezelfde ontdekking krijgt bij een tweede bron een andere formulering; een tekst-sleutel zou
    hem dan als nieuw lezen."""
    a = mm.sleutel_van({"link": "https://X.nl/A", "content": "mycelium schaalt"})
    b = mm.sleutel_van({"link": "https://x.nl/a", "content": "schimmeldraden worden schaalbaar"})
    assert a == b
    # zonder link: terugval op de inhoud, want geen sleutel is erger dan een zwakke
    assert mm.sleutel_van({"content": "iets"}) == "iets"


def test_een_kapotte_staat_start_leeg_MAAR_LUID(tmp_path, caplog):
    """Cache, geen record: leeg beginnen kost hooguit één herhaling; niet starten zet de memo stil."""
    import logging
    (tmp_path / mm.STATE).write_text("{kapot", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert mm.voorgelegd(str(tmp_path)) == {}
    assert "onleesbaar" in caplog.text


# ── de ontvanger ──────────────────────────────────────────────────────────────────────────────

def test_de_memo_overleeft_een_mislukte_adressering(tmp_path, caplog):
    """FAIL-SOFT MAAR LUID. De memo is de waarde; een kapotte lookup mag hem niet opeten. Zonder
    ontvanger valt de pulslus terug op de founder — bij de verkeerde mens is beter dan bij niemand."""
    import logging
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    kapot = types.SimpleNamespace(radar=_radar(_item("iets")).radar)   # géén .records
    with caplog.at_level(logging.WARNING):
        uit = mm.MateriaalKwartaalSkill().run({"_stores": kapot, "_periode": "2026-Q3"}, ctx)
    assert uit["headsup"]                       # de memo staat er
    assert uit["ontvanger"] == ""               # de pulslus valt terug op de founder
    assert "ontvanger niet te bepalen" in caplog.text


def test_het_eigenaar_domein_komt_uit_de_feed_config(tmp_path):
    """Niet uit de memo-module: wie kijkt en wie bezit horen in één governance-aanpasbare plek."""
    assert mm.eigenaar_domein(str(tmp_path)) == "Materials"     # uit _DEFAULT_FEEDS
