"""Een aanroepfout is geen afwezigheid.

WAT ER GEBEURDE (4 sep 2026): `secretary_rol` had `except Exception: pass`. Ik gaf hem een LIJST
waar hij de store verwacht — `records.all()` bestaat daar niet — de except slikte de AttributeError,
en de uitkomst las als "geen wakkere rol met de classificatie-accountability". Ik rapporteerde dat
als systeembevinding ("de routing staat stil") voordat ik doorhad dat het mijn eigen typefout was.

Dat is dezelfde stille-nul-familie als de rest van deze week, maar dan in een vangnet: het vangnet
maakte een fout ONWAARNEEMBAAR, en een onwaarneembare nul fabriceert verklaringen (CONVENTIES).
"""
from __future__ import annotations

import logging
import types

from nooch_village import triage_rol
from nooch_village.triage_rol import SECRETARY_ACCOUNTABILITY


def _rol(rid, accs, *, slaapt=False, archived=False):
    return types.SimpleNamespace(id=rid, slaapt=slaapt, archived=archived,
                                 definition=types.SimpleNamespace(accountabilities=accs))


def _store(*rollen):
    class _R:
        @staticmethod
        def all():
            return list(rollen)
    return _R()


def test_de_houder_wordt_gevonden():
    st = _store(_rol("a", ["iets anders"]), _rol("sec", [SECRETARY_ACCOUNTABILITY]))
    assert triage_rol.secretary_rol(st) == "sec"


def test_een_slapende_houder_telt_niet():
    st = _store(_rol("sec", [SECRETARY_ACCOUNTABILITY], slaapt=True))
    assert triage_rol.secretary_rol(st) == ""


def test_niemand_draagt_hem_is_STIL(caplog):
    """Een lege org is een geldig antwoord, geen fout — daar hoort geen waarschuwing bij."""
    with caplog.at_level(logging.WARNING):
        assert triage_rol.secretary_rol(_store(_rol("a", ["x"]))) == ""
    assert caplog.text == ""


def test_een_AANROEPFOUT_is_LUID(caplog):
    """DE FIX. Een lijst in plaats van de store gaf vroeger dezelfde lege string als 'niemand
    draagt hem'. Nu zegt hij dat het een aanroepfout is, en noemt hij het type."""
    with caplog.at_level(logging.WARNING):
        assert triage_rol.secretary_rol([]) == ""            # een LIJST, geen store
    assert "AANROEPFOUT" in caplog.text
    assert "AttributeError" in caplog.text


def test_de_uitkomst_blijft_leeg_en_klapt_niet():
    """De aanroeper hoort niet te klappen omdat de classificatie niet lukt — alleen hoorbaar te
    falen. Fail-open blijft, stilte niet."""
    assert triage_rol.secretary_rol(None) == ""
