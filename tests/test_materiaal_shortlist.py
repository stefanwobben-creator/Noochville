"""De maandelijkse shortlist: een voorstel met bron, dat onthoudt wat het al vroeg.

DRIE EISEN UIT DE SPEC, elk met zijn eigen reden:
  filter      1-2 kandidaten die marktrijp zijn, footwear raken en bij Nooch passen
  bron        elk item met zijn herkomst — een kandidaat zonder bron is een bewering
  geheugen    wat al voorgelegd is komt niet terug. Zonder dat wordt de radar ruis: de feed blijft
              dezelfde ontdekking aanleveren via een tweede bron of een vervolgartikel.
"""
from __future__ import annotations

import json
import time
import types

from nooch_village import materiaal_memo as mm


def _item(content, *, link="", source="bron.nl", status="goedgekeurd", at=None):
    return {"content": content, "status": status, "feed": mm.FEED, "link": link,
            "source": source, "at": at if at is not None else time.time()}


def _st(*items):
    class _R:
        @staticmethod
        def all_items():
            return list(items)

    class _Recs:
        @staticmethod
        def all():
            return []
    return types.SimpleNamespace(radar=_R(), records=_Recs())


def _ctx(tmp_path):
    return types.SimpleNamespace(data_dir=str(tmp_path))


def _model(monkeypatch, antwoord):
    """Vervang de ladder door een vast antwoord; de schifting is een oordeel, geen telling."""
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "reason", lambda *a, **k: antwoord)


# ── het geheugen ──────────────────────────────────────────────────────────────────────────────

def test_wat_al_voorgelegd_is_komt_niet_terug(tmp_path, monkeypatch):
    d = str(tmp_path)
    st = _st(_item("mycelium schaalt", link="https://a.nl/1"),
             _item("PHA-zolen te koop", link="https://a.nl/2"))
    assert len(mm._nieuw_voor_de_mens(st, d, 0)) == 2

    mm.onthoud_voorgelegd(d, ["https://a.nl/1"])
    over = mm._nieuw_voor_de_mens(st, d, 0)
    assert [o["link"] for o in over] == ["https://a.nl/2"]


def test_een_nee_is_definitief(tmp_path):
    """Één keer afgewezen betekent nooit meer voorleggen — anders duwt de radar hem elke maand
    opnieuw omhoog tot de mens stopt met lezen."""
    d = str(tmp_path)
    st = _st(_item("mycelium", link="https://a.nl/1"))
    mm.onthoud_voorgelegd(d, ["https://a.nl/1"])
    mm.noteer_oordeel(d, "https://a.nl/1", "nee")
    assert mm._nieuw_voor_de_mens(st, d, 0) == []


def test_dezelfde_ontdekking_via_een_andere_bron_telt_als_nieuw(tmp_path):
    """EERLIJKE GRENS van het geheugen: de sleutel is de link. Een vervolgartikel op een ándere
    site is voor dit boek een nieuw signaal. Dat is bewust — de alternatieven (tekstgelijkenis)
    zouden verschillende ontdekkingen samenvoegen, en dat is de duurdere fout."""
    d = str(tmp_path)
    mm.onthoud_voorgelegd(d, ["https://a.nl/1"])
    st = _st(_item("mycelium schaalt", link="https://b.nl/ander"))
    assert len(mm._nieuw_voor_de_mens(st, d, 0)) == 1


# ── de schifting ──────────────────────────────────────────────────────────────────────────────

def test_de_kandidaat_draagt_zijn_bron(tmp_path, monkeypatch):
    _model(monkeypatch, json.dumps({"kandidaten": [
        {"nr": 0, "wat": "Mycelium-leer", "waarom": "plantaardig", "leverancier": "MycoWorks"}]}))
    st = _st(_item("mycelium leer marktrijp", link="https://a.nl/1", source="sciencedirect.com"))
    uit = mm.MateriaalShortlistSkill().run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))
    assert uit["kandidaten"] == 1
    assert "sciencedirect.com" in uit["headsup"] and "https://a.nl/1" in uit["headsup"]
    assert "MycoWorks" in uit["headsup"]


def test_het_is_een_voorstel_en_geen_bevinding(tmp_path, monkeypatch):
    """harry_hemp's eigen regel: hij draagt aan, de mens oordeelt."""
    _model(monkeypatch, json.dumps({"kandidaten": [
        {"nr": 0, "wat": "X", "waarom": "y", "leverancier": ""}]}))
    st = _st(_item("iets", link="https://a.nl/1"))
    uit = mm.MateriaalShortlistSkill().run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))
    assert "VOORSTELLEN, geen bevindingen" in uit["headsup"]
    assert "sample aanvragen" in uit["headsup"]
    # geen leverancier → dat staat er, in plaats van een verzonnen naam
    assert "niet genoemd in de bron" in uit["headsup"]


def test_zonder_model_een_LEGE_lijst_en_geen_ruis(tmp_path, monkeypatch):
    """Alles doorgeven zou de schifting overslaan en er tóch uitzien als een selectie — erger dan
    niets sturen."""
    _model(monkeypatch, None)
    st = _st(_item("van alles", link="https://a.nl/1"))
    uit = mm.MateriaalShortlistSkill().run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))
    assert uit["kandidaten"] == 0 and "geen enkele haalde de lat" in uit["reden"]


def test_een_verzonnen_kandidaat_zonder_bronsignaal_valt_af(tmp_path, monkeypatch, caplog):
    """Zou het model er een verzinnen, dan heeft hij geen link, geen bron en geen sleutel — en
    precies dat maakt hem onnavolgbaar voor wie hem moet beoordelen."""
    import logging
    _model(monkeypatch, json.dumps({"kandidaten": [{"nr": 99, "wat": "verzonnen"}]}))
    st = _st(_item("echt signaal", link="https://a.nl/1"))
    with caplog.at_level(logging.WARNING):
        uit = mm.MateriaalShortlistSkill().run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))
    assert uit["kandidaten"] == 0
    assert "verwijst niet naar een signaal" in caplog.text


def test_een_lege_maand_zegt_dat_er_WEL_gekeken_is(tmp_path, monkeypatch):
    """#426 op de shortlist: nul is een uitkomst, geen stilte."""
    _model(monkeypatch, json.dumps({"kandidaten": []}))
    st = _st(_item("a", link="https://a.nl/1"), _item("b", link="https://a.nl/2"))
    uit = mm.MateriaalShortlistSkill().run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))
    assert "2 ongeziene signalen bekeken" in uit["reden"]


def test_hoogstens_twee(tmp_path, monkeypatch):
    _model(monkeypatch, json.dumps({"kandidaten": [
        {"nr": 0, "wat": "a"}, {"nr": 1, "wat": "b"}, {"nr": 2, "wat": "c"}]}))
    st = _st(_item("a", link="https://a.nl/1"), _item("b", link="https://a.nl/2"),
             _item("c", link="https://a.nl/3"))
    uit = mm.MateriaalShortlistSkill().run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))
    assert uit["kandidaten"] == 2


def test_het_ritme_is_maandelijks(tmp_path, monkeypatch):
    _model(monkeypatch, json.dumps({"kandidaten": []}))
    st = _st(_item("a", link="https://a.nl/1"))
    skill = mm.MateriaalShortlistSkill()
    assert skill.run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))["skipped"] is False
    assert skill.run({"_stores": st, "_periode": "2026-09"}, _ctx(tmp_path))["skipped"] is True
    assert skill.run({"_stores": st, "_periode": "2026-10"}, _ctx(tmp_path))["skipped"] is False


# ── De verzamelaar (pijplijn stap 2, 20 sept 2026) ──────────────────────────
#
# `verzamel()` is de shortlist zonder de aflevering: signalen terug, niets geschreven — ook het
# geheugen niet. Dat laatste is de bewuste knip van deze stap: onthouden is een SCHRIJF-actie, en
# de memo gaat dat straks voor alle vijf de bronnen op één plek doen. Tot die tijd LEEST hij het
# boek wel, anders legt de eerste weekmemo de hele geschiedenis opnieuw voor.

def test_verzamel_levert_signalen_en_onthoudt_niets(tmp_path, monkeypatch):
    d = str(tmp_path)
    st = _st(_item("mycelium-leer schaalt naar productie", link="https://a.nl/1", source="Mat.nl"))
    # `nr` is de index in de kandidatenlijst, niet de sleutel: een kandidaat die niet naar een
    # bronsignaal verwijst bestaat niet (zie `_schift`), en dat is precies de guard die voorkomt
    # dat het model er een verzint zonder link of bron.
    _model(monkeypatch, json.dumps({"kandidaten": [
        {"nr": 0, "wat": "mycelium-leer voor bovenwerk",
         "waarom": "marktrijp en past bij de missie", "leverancier": "MycoCorp"}]}))

    uit = mm.verzamel(st, d, context=_ctx(tmp_path))
    assert len(uit) == 1
    s = uit[0]
    assert s.bron == "materiaal"
    assert s.tekst == "mycelium-leer voor bovenwerk"
    assert s.vindplaats == "https://a.nl/1"
    assert s.extra["waarom"].startswith("marktrijp")        # het OORDEEL staat apart
    assert s.extra["leverancier"] == "MycoCorp"
    assert s.extra["bron_naam"] == "Mat.nl"
    # Het geheugen is NIET geschreven: een verzamelaar schrijft niet.
    assert mm.voorgelegd(d) == {}


def test_verzamel_leest_het_geheugen_wel(tmp_path, monkeypatch):
    """Lezen is geen schrijven. Zonder dit legt de eerste weekmemo alles opnieuw voor wat de
    shortlist eerder al had afgedaan — en dan is de radar weer ruis."""
    d = str(tmp_path)
    st = _st(_item("al voorgelegd", link="https://a.nl/1"),
             _item("nog nieuw", link="https://a.nl/2"))
    mm.onthoud_voorgelegd(d, ["https://a.nl/1"])
    gezien = {}

    def _vang(*a, **k):
        gezien["kandidaten"] = [i["link"] for i in a[1]] if len(a) > 1 else []
        return []
    monkeypatch.setattr(mm, "_schift", _vang)

    mm.verzamel(st, d, context=_ctx(tmp_path))
    assert gezien["kandidaten"] == ["https://a.nl/2"]


def test_verzamel_zonder_kandidaten_vraagt_het_model_niet(tmp_path, monkeypatch):
    """Liever nul dan een zwakke — en zonder kandidaten is er niets om te schiften. Een lege
    modelaanroep kost krediet en levert per definitie niets op."""
    def _nooit(*a, **k):
        raise AssertionError("het model werd aangeroepen zonder kandidaten")
    monkeypatch.setattr(mm, "_schift", _nooit)
    assert mm.verzamel(_st(), str(tmp_path), context=_ctx(tmp_path)) == []


def test_de_drempel_staat_op_de_bron():
    from nooch_village.weekmemo import DREMPELS
    assert mm.DREMPEL == "selectie" and mm.DREMPEL in DREMPELS
