"""Villageraad — de council-pass: geen grond, geen spanning.

Vier beloften die deze tests bewaken:
  1. een rol die niets gegronds vindt zegt dat, en werpt niets op;
  2. elke spanning draagt het id van het record of de pagina waarop hij rust;
  3. een bevinding die de kwaliteitspoort niet haalt wordt NIET verzonden — hij blijft hangen
     mét reden;
  4. dezelfde observatie wordt nooit twee keer opgeworpen.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, villageraad as vr, wiki, zelf_verwerking as zv
from nooch_village.founder_kaart import FOUNDER_ROL

OWNER = "mother_earth__nooch__creator_of_shoes"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _bevinding_ok(tekst, *, rol, records=None, reason_fn=None, ladder=""):
    """Een model dat altijd een bruikbare bevinding teruggeeft — zodat de tests de PIJPLIJN meten
    en niet de LLM."""
    return {"spanning": "Er is iets aan de hand dat ik in gewone taal kan uitleggen en dat "
                        "lang genoeg is om te lezen.",
            "voorstel": "Ik zoek een tweede weg naar deze gegevens.",
            "ok": True, "reden": "", "ruw": tekst}


def _bevinding_slecht(tekst, *, rol, records=None, reason_fn=None, ladder=""):
    return {"spanning": "", "voorstel": "", "ok": False, "reden": "lege signalering", "ruw": tekst}


@pytest.fixture()
def geen_llm(monkeypatch):
    """De pijplijn mag in een test nooit een echte call doen."""
    monkeypatch.setattr("nooch_village.tensie_poort.match",
                        lambda *a, **k: ("", "", "geen match"))


# ── 1. geen grond, geen spanning ────────────────────────────────────────────

def test_rol_zonder_grond_werpt_niets_op(tmp_path, geen_llm):
    _dd, st = _stores(tmp_path)
    r = vr.raad(records=st.records, att=st.att, ledger=st.evidence, assignments=st.assign)
    assert r["rijen"] == []
    assert r["voorstellen"] == []
    assert "Geen enkele rol vond een gegronde spanning" in vr.rapport_tekst(r)
    assert vr.kop_regel(r).startswith("0 spanningen, 0 onder de rollen opgelost, 0 voorstellen")


def test_een_enkele_fout_is_geen_dode_bron(tmp_path):
    """Eén storing is geen patroon. Pas bij herhaling ontstaat er een spanning."""
    _dd, st = _stores(tmp_path)
    st.evidence.record(role_id=OWNER, skill="epo_patents", query="hennep",
                       source="ops.epo.org", status="fout")
    rec = st.records.get(OWNER)
    assert vr.kroniek_observaties(rec, st.evidence) == []


# ── 2. elke spanning draagt zijn anker ──────────────────────────────────────

def test_dode_bron_draagt_het_kroniek_record(tmp_path):
    _dd, st = _stores(tmp_path)
    for _ in range(vr.DODE_BRON_DREMPEL):
        laatste = st.evidence.record(role_id=OWNER, skill="epo_patents", query="hennepvezel",
                                     source="ops.epo.org", status="fout")
    obs = vr.kroniek_observaties(st.records.get(OWNER), st.evidence)
    assert [o["soort"] for o in obs] == ["dode_bron"]
    assert obs[0]["anker"] == laatste["id"]
    assert obs[0]["anker_soort"] == "kroniek"
    assert laatste["id"] in obs[0]["bewijs"]
    # Het bewijs staat vooraan in de snippet, want de store kapt op 160 tekens.
    assert vr._snippet(obs[0]).startswith(f"Kroniek-record {laatste['id']}")


def test_vervallen_grond_op_eigen_pagina_draagt_de_pagina(tmp_path):
    _dd, st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="Hennep", body="wat wij weten")
    st.att.set_meta(a.id, {"feiten": [wiki.maak_feit("Dit is gecertificeerd", soort="cert",
                                                     ref="bestaat-niet")]})
    obs = vr.pagina_observaties(st.records.get(OWNER), st.att, st.evidence)
    soorten = {o["soort"]: o for o in obs}
    assert "ongegronde_pagina" in soorten          # cert-record ontbreekt → ontbreekt/ongegrond
    assert soorten["ongegronde_pagina"]["anker"] == a.id
    assert soorten["ongegronde_pagina"]["anker_soort"] == "pagina"


def test_verweesde_verwijzing_is_gegrond_op_de_pagina(tmp_path):
    _dd, st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="Hennep", body="zie ook [[Vlas]]")
    obs = vr.pagina_observaties(st.records.get(OWNER), st.att, st.evidence)
    verwees = [o for o in obs if o["soort"] == "verweesde_verwijzing"]
    assert verwees and verwees[0]["anker"] == a.id and "Vlas" in verwees[0]["tekst"]


# ── 3. een bevinding die de poort niet haalt gaat niet de deur uit ──────────

def test_onverzendbare_bevinding_blijft_hangen_met_reden(tmp_path, monkeypatch, geen_llm):
    dd, st = _stores(tmp_path)
    monkeypatch.setattr("nooch_village.bevinding.herschrijf", _bevinding_slecht)
    for _ in range(vr.DODE_BRON_DREMPEL):
        st.evidence.record(role_id=OWNER, skill="epo_patents", query="hennepvezel",
                           source="ops.epo.org", status="fout")
    r = vr.raad(records=st.records, att=st.att, ledger=st.evidence, assignments=st.assign,
                notif=st.notif, data_dir=dd, apply=True)
    assert len(r["rijen"]) == 1
    assert r["rijen"][0]["verzendbaar"] is False
    assert r["rijen"][0]["verzonden"] is False
    assert st.notif.all() == []                                   # niets bij iemand geland
    assert r["hangt"] and "lege signalering" in vr.rapport_tekst(r)


def test_founder_kaart_landt_in_de_inbox_met_bewijs(tmp_path, monkeypatch, geen_llm):
    dd, st = _stores(tmp_path)
    monkeypatch.setattr("nooch_village.bevinding.herschrijf", _bevinding_ok)
    # Een spanning die om een besluit in een voorbehouden domein vraagt → founder.
    monkeypatch.setattr(vr, "kroniek_observaties", lambda rec, ledger: (
        [vr._obs(rec.id, "dode_bron", "rec-1", "kroniek",
                 "Deze claim vereist goedkeuring van de founder voordat hij naar buiten gaat.",
                 "Kroniek-record rec-1 (claim_evidence · fout)")]
        if rec.id == OWNER else []))
    r = vr.raad(records=st.records, att=st.att, ledger=st.evidence, assignments=st.assign,
                notif=st.notif, data_dir=dd, apply=True)
    kaarten = [x for x in r["rijen"] if x["type"] == zv.FOUNDER]
    assert kaarten, [x["type"] for x in r["rijen"]]
    item = st.notif.all()[0]
    assert item["target_id"] == FOUNDER_ROL and item["by"] == OWNER
    assert item["type"] == zv.FOUNDER                              # het type reist mee
    assert item["raad"]["anker"] == "rec-1"
    assert "rec-1" in item["snippet"]                              # het anker overleeft de 160-cap
    k = kaarten[0]["kaart"]
    assert k["bewijs"] and k["voorstel"] and k["rol_id"] == OWNER


# ── 4. nooit twee keer hetzelfde punt ───────────────────────────────────────

def test_tweede_ronde_werpt_dezelfde_observatie_niet_opnieuw_op(tmp_path, monkeypatch, geen_llm):
    dd, st = _stores(tmp_path)
    monkeypatch.setattr("nooch_village.bevinding.herschrijf", _bevinding_ok)
    for _ in range(vr.DODE_BRON_DREMPEL):
        st.evidence.record(role_id=OWNER, skill="epo_patents", query="hennepvezel",
                           source="ops.epo.org", status="fout")
    kw = dict(records=st.records, att=st.att, ledger=st.evidence, assignments=st.assign,
              notif=st.notif, data_dir=dd)
    eerste = vr.raad(**kw, apply=True)
    assert len(eerste["rijen"]) == 1
    tweede = vr.raad(**kw, apply=True)
    assert tweede["rijen"] == []
    rol = [p for p in tweede["per_rol"] if p["rol"] == OWNER][0]
    assert rol["eerder"] == 1 and rol["nieuw"] == 0
    assert "al eerder opgeworpen" in vr.rapport_tekst(tweede)


def test_cap_kapt_nooit_stil_af(tmp_path, geen_llm):
    _dd, st = _stores(tmp_path)
    for n in range(4):
        a = st.att.add(OWNER, "note", title=f"P{n}", body="zie ook [[nergens]]")
        assert a
    r = vr.raad(records=st.records, att=st.att, ledger=st.evidence, assignments=st.assign, cap=2)
    rol = [p for p in r["per_rol"] if p["rol"] == OWNER][0]
    assert rol["ingebracht"] == 2 and rol["niet_ingebracht"] == 2
    assert "niet ingebracht" in vr.rapport_tekst(r)


def test_cirkels_zitten_niet_aan_tafel(tmp_path):
    _dd, st = _stores(tmp_path)
    ids = {r.id for r in vr.rollen(st.records)}
    assert OWNER in ids
    assert "mother_earth__nooch" not in ids                        # een cirkel heeft geen handen
