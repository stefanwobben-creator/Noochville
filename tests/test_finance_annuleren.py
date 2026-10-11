"""Cancel line (11 oktober 2026): alleen een tegenboeking, met een verplichte reden; en een regel
wordt hoogstens één keer tegengeboekt (dubbel corrigeren telde eerder −€50 voor een factuur van €100)."""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, finance_uitleg as fu
from nooch_village.finance_omzet import OpbrengstRegister
from nooch_village.finance_register import KostenRegister
from nooch_village.views import finance as fin

from tests.test_finance_omzet import _omzet
from tests.test_finance_pr1 import _boek, _dorp, _st, _velden


def _annuleer(dd, kid, reden="Entered twice", wie="fc@t.nl", actie="finance_kost_cancel"):
    return cockpit2.dispatch(dd, actie, {"kid": [kid], "reason": [reden], "next": ["/"]}, username=wie)[1]


def test_annuleren_is_alleen_een_tegenboeking_en_telt_netto_nul(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    assert "✓ cancelled" in _annuleer(dd, kid)
    regels = KostenRegister(dd).alle()
    assert len(regels) == 2                                             # één regel erbij, geen vervanger
    storno = regels[1]
    assert storno["corrects"] == kid and storno["note"] == "Cancelled: Entered twice"
    assert storno["amount_excl_cents"] == -10000 and storno["vat_cents"] == -2100
    assert storno["attachment"] == regels[0]["attachment"]              # het document blijft bij de regel
    assert sum(r["amount_excl_cents"] for r in regels) == 0


def test_een_reden_is_verplicht(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    assert "✗ give a reason" in _annuleer(dd, kid, reden="   ")
    assert len(KostenRegister(dd).alle()) == 1


def test_niet_twee_keer_tegenboeken(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    _annuleer(dd, kid)
    storno = KostenRegister(dd).alle()[1]["id"]
    assert "already corrected or cancelled" in _annuleer(dd, kid)
    assert "itself a correction or reversal" in _annuleer(dd, storno)
    msg = fin.verwerk_kost(_st(dd), _velden(action="finance_kost_correct", kid=kid, amount_excl="50"), {},
                           username="fc@t.nl", door="fc")
    assert "already corrected or cancelled" in msg
    assert len(KostenRegister(dd).alle()) == 2


def test_dubbel_corrigeren_kan_niet_meer(tmp_path):
    """De bug: €100 → corrigeer naar 0 → corrigeer dezelfde regel naar 50 gaf netto −€50."""
    dd = _dorp(tmp_path)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    fin.verwerk_kost(_st(dd), _velden(action="finance_kost_correct", kid=kid, amount_excl="0"), {},
                     username="fc@t.nl", door="fc")
    msg = fin.verwerk_kost(_st(dd), _velden(action="finance_kost_correct", kid=kid, amount_excl="50"), {},
                           username="fc@t.nl", door="fc")
    assert msg.startswith("✗")
    assert sum(r["amount_excl_cents"] for r in KostenRegister(dd).alle()) == 0
    # de NIEUWSTE regel (de vervanger) corrigeren mag wel
    vervanger = [r for r in KostenRegister(dd).alle() if not r.get("corrects") and r["id"] != kid][0]
    assert "✓" in fin.verwerk_kost(_st(dd), _velden(action="finance_kost_correct", kid=vervanger["id"],
                                                    amount_excl="50"), {}, username="fc@t.nl", door="fc")
    assert sum(r["amount_excl_cents"] for r in KostenRegister(dd).alle()) == 5000


def test_omzet_annuleren_draait_ook_de_paren_om(tmp_path):
    dd = _dorp(tmp_path)
    _omzet(dd)
    rid = OpbrengstRegister(dd).alle()[0]["id"]
    assert "✓ cancelled" in _annuleer(dd, rid, actie="finance_omzet_cancel")
    regels = OpbrengstRegister(dd).alle()
    assert len(regels) == 2 and sum(r["amount_excl_cents"] for r in regels) == 0
    assert sum(r["pairs"] for r in regels) == 0


def test_rechten_zelfde_als_correct(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    for wie in ("bs@t.nl", "lid@t.nl"):                                 # zien ≠ wijzigen; buiten = 404
        with pytest.raises(cockpit2.NietGevonden):
            _annuleer(dd, kid, wie=wie)
    assert len(KostenRegister(dd).alle()) == 1
    assert "✓" in _annuleer(dd, kid, wie="stefan@nooch.earth")


def test_de_knop_staat_op_de_regel_en_de_uitleg_in_de_hulp(tmp_path):
    dd = _dorp(tmp_path)
    _boek(dd)
    kid = KostenRegister(dd).alle()[0]["id"]
    st = _st(dd)
    h = fin.render_cost(st, "fc@t.nl", "t", kid)
    assert "value='finance_kost_cancel'" in h and "Cancel this line" in h and "id=\"fa-reason\"" in h
    assert "finance_kost_cancel" not in fin.render_cost(st, "bs@t.nl", "t", kid)
    _annuleer(dd, kid)
    h = fin.render_cost(_st(dd), "fc@t.nl", "t", kid)
    assert "finance_kost_cancel" not in h and "finance_kost_correct" not in h
    assert "already corrected or cancelled" in h
    help_ = fin.render_help(st, "fc@t.nl")
    assert "Cancel line" in help_ and "at most once" in help_
    assert fu.ANNULEER["reason"][1] is True
