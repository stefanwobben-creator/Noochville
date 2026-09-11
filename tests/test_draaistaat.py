"""Elke skill laat een spoor na, en het scherm toont dat spoor in plaats van een belofte.

Aanleiding (11 september 2026). Stefan keek naar een gekoppeld middel op een rolpagina: "op basis
van één regel weet ik ook niet wat de skill precies doet, ik zie hem ook niet live werkend ofzo".
Meting: acht van de 49 skill-bestanden schreven een spoor. Voor de andere 41 bestond er nergens een
antwoord op de vraag of ze ooit iets gedaan hadden.

De drie dingen die hier vastliggen:

1. **Elke** skill noteert, niet alleen de netjes geïnstrumenteerde. Dat kan alleen als de
   omwikkeling bij `register()` gebeurt en niet per skill-bestand.
2. Ook aanroepers die NIET via de inwoner lopen (de onderzoekspas, de CLI, de demo's, en elke
   `registry.all()`-lus) komen langs de teller. Vandaar de methode en niet het object.
3. `leeg` is geen `gelukt`. Een bron die elke dag draait en elke dag niets vindt ziet er op
   "laatst gedraaid" springlevend uit; alleen `laatste_opbrengst` verraadt hem.
"""
from __future__ import annotations

import re
import tempfile
from types import SimpleNamespace

import pytest

from nooch_village import cockpit2, draaistaat
from nooch_village.skills import Skill, SkillRegistry


class _Goed(Skill):
    name = "t_goed"
    description = "levert altijd iets"
    cost = "free"

    def run(self, payload, context):
        return {"rows": [1, 2, 3]}


class _Leeg(Skill):
    name = "t_leeg"
    description = "vindt nooit iets"
    cost = "free"

    def run(self, payload, context):
        return {"no_data": True, "reason": "niets gevonden"}


class _Stuk(Skill):
    name = "t_stuk"
    description = "klapt altijd"
    cost = "free"

    def run(self, payload, context):
        raise RuntimeError("boem")


def _opzet(tmp_path):
    dd = str(tmp_path / "d")
    ctx = SimpleNamespace(data_dir=dd)
    reg = SkillRegistry()
    for s in (_Goed(), _Leeg(), _Stuk()):
        reg.register(s)
    return dd, ctx, reg, draaistaat.Draaistaat(draaistaat.pad_voor(dd))


# ── de omwikkeling ───────────────────────────────────────────────────────────

def test_registreren_wikkelt_om(tmp_path):
    _dd, _ctx, reg, _st = _opzet(tmp_path)
    assert draaistaat.is_omwikkeld(reg.get("t_goed"))


def test_omwikkelen_is_idempotent(tmp_path):
    _dd, ctx, reg, staat = _opzet(tmp_path)
    assert draaistaat.omwikkel(reg.get("t_goed")) is False     # al gedaan bij register()
    reg.get("t_goed").run({}, ctx)
    assert len(staat.voor_skill("t_goed")) == 1, "tweemaal wikkelen zou dubbel noteren"


def test_het_object_blijft_zichzelf(tmp_path):
    """De reden dat we de METHODE wikkelen en niet het object: vijf plekken in het dorp doen
    `isinstance(skill, DataSourceSkill)` en één leest `type(skill).__module__`. Een proxy breekt
    die allemaal stil."""
    _dd, _ctx, reg, _st = _opzet(tmp_path)
    s = reg.get("t_goed")
    assert isinstance(s, Skill) and isinstance(s, _Goed)
    assert type(s).__module__ == __name__
    assert s.description == "levert altijd iets"


def test_gedrag_blijft_ongewijzigd(tmp_path):
    _dd, ctx, reg, _st = _opzet(tmp_path)
    assert reg.get("t_goed").run({}, ctx) == {"rows": [1, 2, 3]}
    with pytest.raises(RuntimeError, match="boem"):
        reg.get("t_stuk").run({}, ctx)


# ── wat er genoteerd wordt ───────────────────────────────────────────────────

def test_de_drie_uitkomsten(tmp_path):
    _dd, ctx, reg, staat = _opzet(tmp_path)
    reg.get("t_goed").run({}, ctx)
    reg.get("t_leeg").run({}, ctx)
    with pytest.raises(RuntimeError):
        reg.get("t_stuk").run({}, ctx)
    assert [r["uitkomst"] for r in staat.alles()] == ["gelukt", "leeg", "fout"]


def test_een_klappende_skill_laat_juist_wel_een_spoor_na(tmp_path):
    """Zonder dit ziet een gereedschap dat altijd klapt er identiek uit aan één dat nooit is
    gebruikt — en dat is precies het verschil dat je wil zien bij het snoeien."""
    _dd, ctx, reg, staat = _opzet(tmp_path)
    with pytest.raises(RuntimeError):
        reg.get("t_stuk").run({}, ctx)
    assert staat.laatste("t_stuk")["uitkomst"] == "fout"
    assert staat.laatste_opbrengst("t_stuk") is None


def test_leeg_telt_niet_als_opbrengst(tmp_path):
    _dd, ctx, reg, staat = _opzet(tmp_path)
    reg.get("t_leeg").run({}, ctx)
    assert staat.laatste("t_leeg") is not None          # hij draaide wél
    assert staat.laatste_opbrengst("t_leeg") is None    # maar leverde niets op


def test_nooit_gedraaid_geeft_none(tmp_path):
    _dd, _ctx, _reg, staat = _opzet(tmp_path)
    assert staat.laatste("bestaat_niet") is None
    assert staat.samenvatting() == {}


def test_ook_buiten_de_inwoner_om(tmp_path):
    """`registry.all()` is de route van de onderzoekspas, de CLI en de demo's. Die moeten óók
    tellen, anders meldt /skills 'nog geen spoor' over een skill die gewoon draait."""
    _dd, ctx, reg, staat = _opzet(tmp_path)
    [s for s in reg.all() if s.name == "t_goed"][0].run({}, ctx)
    assert len(staat.voor_skill("t_goed")) == 1


def test_het_aanroeper_label(tmp_path):
    _dd, ctx, reg, staat = _opzet(tmp_path)
    with draaistaat.aanroeper("mother_earth__nooch__website_developer"):
        reg.get("t_goed").run({}, ctx)
    reg.get("t_goed").run({}, ctx)                      # zonder label
    door = [r["door"] for r in staat.voor_skill("t_goed")]
    assert door == ["mother_earth__nooch__website_developer", ""]


def test_aanroeper_herstelt_bij_een_uitzondering(tmp_path):
    _dd, ctx, reg, _st = _opzet(tmp_path)
    with draaistaat.aanroeper("buiten"):
        with pytest.raises(RuntimeError):
            with draaistaat.aanroeper("binnen"):
                reg.get("t_stuk").run({}, ctx)
        assert draaistaat.huidige_aanroeper() == "buiten"
    assert draaistaat.huidige_aanroeper() == ""


# ── fail-soft: observatie mag nooit duurder zijn dan wat ze observeert ────────

def test_zonder_data_dir_draait_de_skill_gewoon(tmp_path):
    _dd, _ctx, reg, _st = _opzet(tmp_path)
    kaal = SimpleNamespace()                            # geen data_dir (de meeste tests)
    assert reg.get("t_goed").run({}, kaal) == {"rows": [1, 2, 3]}


def test_een_onschrijfbare_staat_breekt_niets(tmp_path):
    staat = draaistaat.Draaistaat("/proc/kan-hier-niet/schrijven.jsonl")
    assert staat.noteer(skill="x", door="y", uitkomst="gelukt") is None
    assert staat.alles() == []


def test_een_onbekende_uitkomst_wordt_niet_genoteerd(tmp_path):
    staat = draaistaat.Draaistaat(str(tmp_path / "s.jsonl"))
    assert staat.noteer(skill="x", door="y", uitkomst="prima") is None
    assert staat.alles() == []


def test_een_kapotte_regel_wist_de_staat_niet(tmp_path):
    pad = str(tmp_path / "s.jsonl")
    staat = draaistaat.Draaistaat(pad)
    staat.noteer(skill="x", door="", uitkomst="gelukt")
    with open(pad, "a", encoding="utf-8") as f:
        f.write("{dit is geen json\n")
    staat.noteer(skill="y", door="", uitkomst="fout")
    assert [r["skill"] for r in draaistaat.Draaistaat(pad).alles()] == ["x", "y"]


# ── het scherm ───────────────────────────────────────────────────────────────

def _pagina(tmp_path, rijen=()):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    staat = draaistaat.Draaistaat(draaistaat.pad_voor(dd))
    for skill, uitkomst in rijen:
        staat.noteer(skill=skill, door="noochie", uitkomst=uitkomst)
    return cockpit2.render_skills(cockpit2._Stores(dd), None)


def _kaart(page: str, skill: str) -> str:
    m = re.search(r"<div class='card'>(?:(?!<div class='card'>).)*?<code>" + skill + r"</code>",
                  page, re.S)
    assert m, f"geen kaart voor {skill}"
    return m.group(0)


def test_de_kaart_toont_de_eigen_beschrijving(tmp_path):
    """Het veld bestond al op `Skill` en werd nergens getoond: je zag alleen de bijnaam."""
    page = _pagina(tmp_path)
    assert "Checkt of een site live is" in _kaart(page, "site_health")


def test_zonder_spoor_zegt_het_scherm_dat(tmp_path):
    page = _pagina(tmp_path)
    assert "No trace yet" in _kaart(page, "claims_check")


def test_gedraaid_zonder_opbrengst_leest_anders_dan_gedraaid_met(tmp_path):
    page = _pagina(tmp_path, [("site_health", "gelukt"),
                              ("claims_check", "leeg"), ("claims_check", "fout")])
    assert "Last produced something" in _kaart(page, "site_health")
    leeg = _kaart(page, "claims_check")
    assert "never" in leeg and "1 empty, 1 failed" in leeg


def test_de_kop_telt_gedraaid_en_opgeleverd(tmp_path):
    page = _pagina(tmp_path, [("site_health", "gelukt"), ("claims_check", "leeg")])
    assert "actually run: <b>2</b>" in page
    assert "ever produced something: <b>1</b>" in page


def test_niet_toegekend_beweert_niet_meer_dat_niemand_hem_kan_gebruiken(tmp_path):
    """De oude tekst was "Nobody wields this means yet" terwijl elke rol hem via de rugzak bereikt.
    Die zin stond op 10 september live bij een skill die gewoon draaide."""
    page = _pagina(tmp_path)
    assert "Nobody wields this means yet" not in page
    assert "Not separately granted to any role" in page
