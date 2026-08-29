"""De voorraad, niet alleen de instroom.

De laatste meter vuurt op het MOMENT van parkeren. Wat daarvóór al vastliep blijft liggen: die items
dragen `routed=True`, en dat is precies de garantie die voorkomt dat de router elke puls opnieuw
dezelfde LLM-call doet. Zelfde les als de notificatie-opruiming van 14 aug 2026: **code repareren
haalt de emissies van die code niet weg** — en hier andersom: het haalt de STILSTAND niet weg.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, escalation_router as er, vastgelopen_route as vr
from nooch_village.human_inbox import FOUNDER_ROLE_ID

MENS = "vastgelopen op 1 item(s) — wacht op een mens of externe partij"
ROLWERK = "vastgelopen op 1 item(s) — payload onvolledig na herstelpoging: veld term"


@pytest.fixture
def dd(tmp_path, monkeypatch):
    cockpit2._bootstrap(str(tmp_path))
    monkeypatch.setattr("nooch_village.assignments.door_mens_bemand",
                        lambda rol, a, r: rol == FOUNDER_ROLE_ID)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)      # geen model → founder
    return str(tmp_path)


def _vastgelopen(dd, *, reden=MENS, stap="Laat de samples testen in een erkend lab") -> str:
    st = cockpit2._Stores(dd)
    pid = st.projects.create("harry_hemp", "PHA-aanbodlandschap", "human")
    cl = st.projects.checklist_add(pid, title="Uitvoerplan")
    st.projects.check_add(pid, cl["id"], stap)
    st.projects.block(pid, reden)
    return pid


# ── Guard 1: alleen een mens-park-reden ─────────────────────────────────────

def test_alleen_mens_werk_gaat_naar_een_mens(dd):
    _vastgelopen(dd, reden=ROLWERK)
    v = vr.pas(dd, apply=True)
    assert v["in_aanmerking"] == 0 and v["geland"] == []


def test_een_mens_park_reden_landt_wel(dd):
    pid = _vastgelopen(dd)
    v = vr.pas(dd, apply=True)
    assert v["in_aanmerking"] == 1 and len(v["geland"]) == 1
    assert v["geland"][0]["pid"] == pid
    n = [x for x in cockpit2._Stores(dd).notif.all() if x.get("target_id") == FOUNDER_ROLE_ID]
    assert n and "erkend lab" in (n[-1].get("snippet") or "")


# ── Guard 2: alleen wat nu nog open is ──────────────────────────────────────

def test_een_afgevinkte_stap_is_geen_vraag_meer(dd):
    pid = _vastgelopen(dd)
    st = cockpit2._Stores(dd)
    p = st.projects.get(pid)
    cl = p["checklists"][0]
    st.projects.check_toggle(pid, cl["id"], cl["items"][0]["id"])
    assert vr.pas(dd, apply=True)["stappen"] == 0


# ── Guard 3: idempotent op het spoor ────────────────────────────────────────

def test_twee_keer_draaien_levert_geen_tweede_melding(dd):
    _vastgelopen(dd)
    eerste = vr.pas(dd, apply=True)
    tweede = vr.pas(dd, apply=True)
    assert len(eerste["geland"]) == 1
    assert tweede["geland"] == [] and tweede["al_gemeld"] == 1
    n = [x for x in cockpit2._Stores(dd).notif.all() if x.get("target_id") == FOUNDER_ROLE_ID]
    assert len(n) == 1, "dezelfde vraag twee keer verstuurd"


def test_de_idempotentie_hangt_aan_de_MELDING_niet_aan_een_vlag():
    """Een vlag op het item en een verstuurde melding zijn twee plekken voor één feit; die drijven
    uiteen zodra iemand de inbox opruimt. Zelfde regel als `reference, don't copy`."""
    import inspect
    bron = inspect.getsource(vr.al_geland)
    assert "st.notif.all()" in bron


# ── De droge loop is de default ─────────────────────────────────────────────

def test_droge_loop_schrijft_niets(dd):
    _vastgelopen(dd)
    v = vr.pas(dd)                                     # geen apply
    assert len(v["geland"]) == 1 and v["toegepast"] is False
    assert not [x for x in cockpit2._Stores(dd).notif.all()
                if x.get("target_id") == FOUNDER_ROLE_ID]


def test_filteren_op_één_rol(dd):
    _vastgelopen(dd)
    assert vr.pas(dd)["in_aanmerking"] == 1
    assert vr.pas(dd, owner="iemand_anders")["in_aanmerking"] == 0
