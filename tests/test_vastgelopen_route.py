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

#: de mens die de founder-rol vervult in deze fixtures — het ADRES sinds de
#: vervuller-pass; de rol blijft de context op het item.
FOUNDER_PERSOON = "p-founder"

MENS = "vastgelopen op 1 item(s) — wacht op een mens of externe partij"
ROLWERK = "vastgelopen op 1 item(s) — payload onvolledig na herstelpoging: veld term"


@pytest.fixture
def dd(tmp_path, monkeypatch):
    cockpit2._bootstrap(str(tmp_path))
    # `mens_vervullers` en niet meer `door_mens_bemand`: `route_werk` kijkt sinds de vervuller-pass
    # naar WIE een rol draagt, niet naar of hij gedragen wordt. De founder-rol krijgt hier één
    # vervuller, dus het werk landt bij die mens met de rol als context.
    # Patch op `signaal.mensen_van` en niet meer op `cockpit2.mens_vervullers`: die laatste
    # delegeert er sinds B2 naartoe, en de signaal-routering (die het bericht bezorgt) leest
    # dezelfde functie. Eén plek patchen dekt nu allebei — dat was precies het doel van die
    # samenvoeging.
    from nooch_village import signaal as _sig
    monkeypatch.setattr(_sig, "mensen_van",
                        lambda _st, rol: [FOUNDER_PERSOON] if rol == FOUNDER_ROLE_ID else [])
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)      # geen model → founder
    return str(tmp_path)


def _dm_aan(st, persoon_id):
    """De DM-teksten die deze persoon kreeg. Het SPOOR van een melding is sinds B2 een bericht in
    een kanaal in plaats van een rij in een wachtrij; de redenering eromheen is ongewijzigd."""
    return [e.get("text") or "" for k in st.channels.kanalen_van(persoon_id)
            for e in st.channels.trail(k)]

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
    n = _dm_aan(cockpit2._Stores(dd), FOUNDER_PERSOON)
    assert n and "erkend lab" in n[-1]


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
    n = _dm_aan(cockpit2._Stores(dd), FOUNDER_PERSOON)
    assert len(n) == 1, "dezelfde vraag twee keer verstuurd"


def test_de_idempotentie_hangt_aan_de_MELDING_niet_aan_een_vlag():
    """Een vlag op het item en een verstuurde melding zijn twee plekken voor één feit; die drijven
    uiteen zodra iemand de inbox opruimt. Zelfde regel als `reference, don't copy`."""
    import inspect
    bron = inspect.getsource(vr.al_geland)
    assert "st.channels" in bron          # het spoor is de verstuurde DM, geen losse vlag


# ── De droge loop is de default ─────────────────────────────────────────────

def test_droge_loop_schrijft_niets(dd):
    _vastgelopen(dd)
    v = vr.pas(dd)                                     # geen apply
    assert len(v["geland"]) == 1 and v["toegepast"] is False
    assert not _dm_aan(cockpit2._Stores(dd), FOUNDER_PERSOON)


def test_filteren_op_één_rol(dd):
    _vastgelopen(dd)
    assert vr.pas(dd)["in_aanmerking"] == 1
    assert vr.pas(dd, owner="iemand_anders")["in_aanmerking"] == 0


# ── De droge loop moet de ENIGE beslissing meten die ertoe doet ──────────────

def test_de_droge_loop_toont_waar_het_zou_landen(dd):
    """Een droge loop die alleen TELT laat de vraag onbeantwoord die het besluit draagt: routeren we,
    of dumpen we 33 items op één inbox? Dat zijn twee verschillende handelingen."""
    _vastgelopen(dd)
    v = vr.pas(dd)
    assert v["toegepast"] is False
    assert sum(v["verdeling"].values()) == 1
    assert list(v["gronden"]) == ["geen rol bezit dit, en het project heeft geen opdrachtgever"]
    assert not [x for x in cockpit2._Stores(dd).notif.all()          # en nog steeds niets geschreven
                if x.get("target_id") == FOUNDER_PERSOON]


def test_de_verdeling_noemt_de_rol_bij_naam_niet_bij_id(dd):
    """Een id in een verdeling is niet te lezen; de vraag is welke MENS dit krijgt."""
    _vastgelopen(dd)
    assert "Strategic Lead" in " ".join(vr.pas(dd)["verdeling"])
