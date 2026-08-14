"""Erfenis loopt omhoog; een zusterrol insluiten is een besluit.

De copy-prompt las één rol plus wat die rol ERFT. Overerving volgt de cirkelketen naar boven, dus
de policies van een zusterrol kwamen er nooit in — en precies daar wonen ze: de copy-governance
(COPYCHECK/TONEOFVOICE/POSITIONSTAT) bij Community and Email, de merkstem bij Brand & Visual
Designer. Wie als Copywriter schreef kreeg dus een lege stack.

Deze tests bevriezen de drie eisen die de fix moest halen:

  1. de policies VERHUIZEN NIET — eigendom blijft bij de rol die het domein houdt;
  2. een inclusie is zichtbaar ANDERS dan erfenis, tot in de prompt-tekst toe;
  3. de knoppen zijn admin-only, want een schrijver hoort de merkstem niet te kunnen uitzetten.
"""
from __future__ import annotations

import pytest

from nooch_village import copy_stack as cs
from nooch_village.views import copy_prompt as cp


# ── Fixtures: een mini-organisatie met een zusterrol ────────────────────────

class _Def:
    def __init__(self, domains=(), naam=""):
        self.domains = list(domains)
        self.purpose = "p"
        self.accountabilities = []
        self.name = naam


class _Rec:
    def __init__(self, rid, domains=(), naam="", parent=""):
        self.id = rid
        self.definition = _Def(domains, naam or rid)
        self.parent = parent
        self.archived = False
        self.members = []


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


CIRKEL, MERK, STEM, SCHRIJVER = "nooch", "nooch__brand", "nooch__community", "nooch__copywriter"

RECS = _Records([
    _Rec(CIRKEL, naam="Nooch"),
    _Rec(MERK, ["Brand positioning", "Design system"], "Brand & Visual Designer", CIRKEL),
    _Rec(STEM, ["Copycheck", "Tone of voice"], "Community and Email", CIRKEL),
    _Rec(SCHRIJVER, [], "Copywriter", CIRKEL),
])

_POLICIES = {
    CIRKEL: [{"id": "MONEY-001", "title": "Money", "body": "budget"}],
    MERK:   [{"id": "BRANDPOSITIO-001", "title": "Brand positioning", "body": "merkstem"}],
    STEM:   [{"id": "COPYCHECK-001", "title": "Copycheck", "body": "never write friend"}],
    SCHRIJVER: [],
}


class _Art:
    def __init__(self, d):
        self.__dict__.update(d)
        self.status = "active"


class _Att:
    def list(self, rid, kind):
        return [_Art(dict(a)) for a in _POLICIES.get(rid, [])] if kind == "policy" else []


@pytest.fixture(autouse=True)
def _fake_context(monkeypatch):
    """serialize_context uit de fixture voeden: eigen policies + erfenis van de cirkel."""
    from nooch_village import artefacts

    def _ctx(role_id, records, store):
        geerfd = ([dict(a, origin_id=CIRKEL, origin_path="via Nooch")
                   for a in _POLICIES[CIRKEL]] if role_id != CIRKEL else [])
        return {"role": {"id": role_id, "name": role_id, "purpose": "p", "accountabilities": []},
                "policies": {"own": [dict(a) for a in _POLICIES.get(role_id, [])],
                             "inherited": geerfd}}

    monkeypatch.setattr(artefacts, "serialize_context", _ctx)
    monkeypatch.setattr(cs, "_own_policies",
                        lambda rol, records, att: [dict(a) for a in _POLICIES.get(rol, [])])


def _cfg(tmp_path, incl=()):
    c = cs.StackConfig(str(tmp_path / "copy_stack.json"))
    for b in incl:
        c.zet(SCHRIJVER, b, True, door="test")
    return c


# ── 1. Het gat, en dat de fix hem sluit ─────────────────────────────────────

def test_zonder_inclusie_is_de_copywriter_stack_leeg(tmp_path):
    """De bug, expliciet: de Copywriter bezit niets en erft alleen het kader. Zonder inclusie is
    er dus geen enkele schrijfregel — en dat was precies de klacht."""
    items = cs.componeer(SCHRIJVER, RECS, _Att(), _cfg(tmp_path))
    assert [a["id"] for a in items] == ["MONEY-001"]
    assert [a["id"] for a in items if a["aan"]] == []      # kader staat standaard uit


def test_met_inclusie_draagt_de_copywriter_merk_en_copy_als_aparte_lagen(tmp_path):
    items = cs.componeer(SCHRIJVER, RECS, _Att(), _cfg(tmp_path, [STEM, MERK]))
    per_laag = {a["id"]: a["laag"] for a in items}
    assert per_laag["COPYCHECK-001"] == cs.LAAG_STEM
    assert per_laag["BRANDPOSITIO-001"] == cs.LAAG_MERK
    assert per_laag["MONEY-001"] == cs.LAAG_KADER
    aan = {a["id"] for a in items if a["aan"]}
    assert aan == {"COPYCHECK-001", "BRANDPOSITIO-001"}    # ingesloten aan, kader uit


def test_een_inclusie_verhuist_geen_eigendom(tmp_path):
    """De hardste eis. De policy blijft van de bronrol; de stack leent hem alleen."""
    cfg = _cfg(tmp_path, [STEM])
    items = cs.componeer(SCHRIJVER, RECS, _Att(), cfg)
    copycheck = next(a for a in items if a["id"] == "COPYCHECK-001")
    assert copycheck["bron"] == "inclusie"
    assert copycheck["herkomst"] == "Community and Email"
    # En de bron zelf is niets kwijt.
    eigen_bij_bron = cs.componeer(STEM, RECS, _Att(), cfg)
    assert any(a["id"] == "COPYCHECK-001" and a["bron"] == "eigen" for a in eigen_bij_bron)


def test_erfenis_en_inclusie_zijn_verschillende_dingen(tmp_path):
    items = cs.componeer(SCHRIJVER, RECS, _Att(), _cfg(tmp_path, [MERK]))
    bronnen = {a["id"]: a["bron"] for a in items}
    assert bronnen["MONEY-001"] == "erfenis"          # komt vanzelf, niemand koos hem
    assert bronnen["BRANDPOSITIO-001"] == "inclusie"  # iemand koos hem


def test_dubbele_binnenkomst_telt_een_keer(tmp_path):
    """Erft een rol iets dat ook via een inclusie binnenkomt, dan mag het niet twee keer in de
    prompt staan — dubbele tekst leest als nadruk die niemand bedoelde."""
    cfg = _cfg(tmp_path, [CIRKEL])
    ids = [a["id"] for a in cs.componeer(SCHRIJVER, RECS, _Att(), cfg)]
    assert ids.count("MONEY-001") == 1


# ── 2. De config: een besluit met een naam eraan ────────────────────────────

def test_config_bewaart_wie_de_inclusie_zette(tmp_path):
    cfg = cs.StackConfig(str(tmp_path / "copy_stack.json"))
    assert cfg.zet(SCHRIJVER, MERK, True, door="stefan@x") is True
    assert cfg.zet(SCHRIJVER, MERK, True, door="stefan@x") is False     # idempotent
    assert cfg.door(SCHRIJVER, MERK) == "stefan@x"
    assert cs.StackConfig(str(tmp_path / "copy_stack.json")).inclusies(SCHRIJVER) == [MERK]


def test_uitzetten_verwijdert_de_inclusie(tmp_path):
    cfg = _cfg(tmp_path, [MERK, STEM])
    assert cfg.zet(SCHRIJVER, MERK, False, door="stefan@x") is True
    assert cfg.inclusies(SCHRIJVER) == [STEM]


def test_zaad_wint_nooit_van_een_menselijke_keuze(tmp_path):
    """Zodra iemand de compositie heeft aangeraakt is dát de waarheid. Een zaad dat bij elke start
    terugkomt zou een bewuste verwijdering elke nacht ongedaan maken."""
    cfg = _cfg(tmp_path, [MERK])
    cfg.zet(SCHRIJVER, MERK, False, door="stefan@x")       # mens haalt hem er bewust uit
    assert cfg.zaad(SCHRIJVER, [MERK], door="system") == 0
    assert cfg.inclusies(SCHRIJVER) == []


def test_een_rol_kan_zichzelf_niet_insluiten(tmp_path):
    cfg = cs.StackConfig(str(tmp_path / "copy_stack.json"))
    assert cfg.zet(SCHRIJVER, SCHRIJVER, True) is False


def test_verdwenen_bron_wordt_overgeslagen_en_gelogd(tmp_path, caplog):
    """Fail-soft, maar niet stil: een inclusie naar een verwijderde rol mag de pagina niet breken
    én mag niet onopgemerkt verdampen."""
    cfg = cs.StackConfig(str(tmp_path / "copy_stack.json"))
    cfg.zet(SCHRIJVER, "bestaat_niet", True)
    with caplog.at_level("WARNING"):
        items = cs.componeer(SCHRIJVER, RECS, _Att(), cfg)
    assert [a["id"] for a in items] == ["MONEY-001"]
    assert "bestaat niet meer" in caplog.text


# ── 3. De prompt en de UI ───────────────────────────────────────────────────

def test_de_prompt_zegt_dat_een_regel_is_ingesloten(tmp_path):
    """Anders leest een merkregel als iets wat de schrijvende rol zelf cureert, en dan weet je niet
    bij wie je moet zijn om hem te wijzigen."""
    items = cs.componeer(SCHRIJVER, RECS, _Att(), _cfg(tmp_path, [MERK]))
    prompt = cp.bouw_prompt({"role": {"id": SCHRIJVER, "name": "Copywriter"}}, items=items)
    assert "included from Brand & Visual Designer" in prompt


def test_kandidaten_komen_uit_de_organisatie(tmp_path):
    """Geen rol-id in de code: wie iets te lenen heeft, bepaalt de organisatie."""
    ks = {k["id"]: k for k in cs.kandidaten(RECS, _Att(), behalve=SCHRIJVER)}
    assert set(ks) == {CIRKEL, MERK, STEM}
    assert ks[MERK]["laag"] == cs.LAAG_MERK and ks[STEM]["laag"] == cs.LAAG_STEM
    assert SCHRIJVER not in ks


class _St:
    def __init__(self, tmp_path, cfg):
        self.records, self.att, self.copy_stack, self.dd = RECS, _Att(), cfg, str(tmp_path)


def test_de_schrijver_ziet_de_stack_maar_geen_knoppen(tmp_path):
    """Transparantie zonder bedieningspaneel: hij mag zien waar zijn regels vandaan komen, en niet
    per ongeluk de merkstem uitzetten."""
    st = _St(tmp_path, _cfg(tmp_path, [MERK, STEM]))
    html = cp.render_copy_prompt(st, rol=SCHRIJVER, admin=False)
    assert "Brand positioning" in html and "Copycheck" in html      # ziet de stack
    assert "Composition (admin)" not in html                        # geen compositie-paneel
    assert "copy_stack_inclusie" not in html                        # geen schrijf-actie
    assert "href='/copy-prompt?brief=" not in html                  # geen toggle-links


def test_de_admin_ziet_de_knoppen_en_het_paneel(tmp_path):
    st = _St(tmp_path, _cfg(tmp_path, [MERK, STEM]))
    html = cp.render_copy_prompt(st, rol=SCHRIJVER, admin=True)
    assert "Composition (admin)" in html
    assert "copy_stack_inclusie" in html
    assert "Brand &amp; Visual Designer" in html or "Brand & Visual Designer" in html


def test_render_is_fail_closed_zonder_admin_vlag(tmp_path):
    """De default is de lees-versie. Wie de vlag vergeet door te geven, opent geen knoppen."""
    import inspect
    assert inspect.signature(cp.render_copy_prompt).parameters["admin"].default is False
