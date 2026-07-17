"""IA-fase 4: nominatie-instrument — iedereen nomineert, alleen Lara schrijft, elke
beslissing append-only in de Kroniek (reden verplicht bij afwijzing)."""
from __future__ import annotations

import json
import os

from nooch_village.keyword_nominations import (NominationQueue, NominationKroniek, valid_reason)
from nooch_village.cockpit2 import dispatch, _Stores


def _form(**kw):
    return {k: [v] for k, v in kw.items()}


# ── store-laag ──────────────────────────────────────────────────────────────

def test_queue_dedup_en_remove(tmp_path):
    q = NominationQueue(os.path.join(str(tmp_path), "n.json"))
    assert q.nominate("Vegan Boots", by="Billy")
    assert not q.nominate("vegan boots", by="Billy")     # dedup op kleine letter
    assert not q.nominate("   ", by="x")                 # leeg → niet
    assert q.has("vegan boots") and len(q.pending()) == 1
    assert q.remove("VEGAN BOOTS") and not q.has("vegan boots")


def test_valid_reason_fail_closed():
    for goed in ("te breed", "past niet bij de missie"):
        assert valid_reason(goed)
    for slecht in ("", "  ", "n.v.t.", "nvt", "-", "geen"):
        assert not valid_reason(slecht)


def test_kroniek_append_only_en_decision_validatie(tmp_path):
    k = NominationKroniek(os.path.join(str(tmp_path), "k.jsonl"))
    k.record(role_id="Lara", term="a", decision="accept", reason="sterk")
    k.record(role_id="Lara", term="b", decision="reject", reason="te breed")
    recs = k.all_records()
    assert len(recs) == 2 and {r["decision"] for r in recs} == {"accept", "reject"}
    try:
        k.record(role_id="Lara", term="c", decision="misschien", reason="x")
        assert False, "ongeldige decision had moeten falen"
    except ValueError:
        pass


# ── dispatch + authz ─────────────────────────────────────────────────────────

def test_nominate_via_dispatch_iedereen(tmp_path):
    dd = str(tmp_path)
    nxt, msg = dispatch(dd, "kw_nominate", _form(term="mycelium shoes", next="/keywords?lens=trends"),
                        username="guest")
    assert "genomineerd" in msg
    assert _Stores(dd).nominations.has("mycelium shoes")


def test_reject_zonder_reden_geweigerd(tmp_path):
    dd = str(tmp_path)
    _Stores(dd).nominations.nominate("mycelium shoes", by="Billy")
    nxt, msg = dispatch(dd, "kw_nom_reject",
                        _form(term="mycelium shoes", reason="n.v.t.", next="/keywords?lens=library"),
                        username="guest")
    assert "een echte reden" in msg
    st = _Stores(dd)
    assert st.nominations.has("mycelium shoes")           # niet verwijderd
    assert st.nom_kroniek.all_records() == []             # niets geborgd


def test_reject_met_reden_borgt_en_verwijdert(tmp_path):
    dd = str(tmp_path)
    _Stores(dd).nominations.nominate("mycelium shoes", by="Billy")
    nxt, msg = dispatch(dd, "kw_nom_reject",
                        _form(term="mycelium shoes", reason="te niche", next="/keywords?lens=library"),
                        username="guest")
    assert "afgewezen" in msg
    st = _Stores(dd)
    assert not st.nominations.has("mycelium shoes")
    recs = st.nom_kroniek.all_records()
    assert len(recs) == 1 and recs[0]["decision"] == "reject" and recs[0]["reason"] == "te niche"


def test_accept_schrijft_woordenschat_en_kroniek(tmp_path):
    dd = str(tmp_path)
    _Stores(dd).nominations.nominate("ocean plastic shoes", by="Billy")
    nxt, msg = dispatch(dd, "kw_nom_accept",
                        _form(term="ocean plastic shoes", status="approved", reason="sterk signaal",
                              next="/keywords?lens=library"), username="guest")
    assert "geborgd als approved" in msg
    st = _Stores(dd)
    assert not st.nominations.has("ocean plastic shoes")
    ent = st.library.status("ocean plastic shoes")
    assert ent and ent["status"] == "approved" and ent["rationale"] == "sterk signaal"
    recs = st.nom_kroniek.all_records()
    assert len(recs) == 1 and recs[0]["decision"] == "accept"


def test_beslissen_gated_onbekende_gebruiker_geweigerd(tmp_path):
    dd = str(tmp_path)
    _Stores(dd).nominations.nominate("mycelium shoes", by="Billy")
    # een ingelogde, niet-herkende gebruiker (geen guest) mag NIET beslissen
    nxt, msg = dispatch(dd, "kw_nom_accept",
                        _form(term="mycelium shoes", status="approved", next="/keywords?lens=library"),
                        username="onbekend@nergens.nl")
    assert "Geen toegang" in msg
    st = _Stores(dd)
    assert st.nominations.has("mycelium shoes")           # niets gebeurd
    assert st.library.status("mycelium shoes") is None
