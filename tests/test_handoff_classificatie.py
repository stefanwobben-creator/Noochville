"""Een geslaagde overdracht mag niet als 'geen resultaat' in het log staan.

Waargenomen op productie (bewijsrun 10 aug): `projectverzoek` draaide met een complete payload,
`project_items.handoff` maakte een echt project op het bord van de doelrol — en de logregel zei
`📭 … afgerond zonder resultaat`. Ik heb daardoor eerst geconcludeerd dat de skill stuk was; pas
een blik op het bord liet zien dat de overdracht gelukt was.

Oorzaak: `_classify_result` kent de uitvoer van een handoff niet. `{ok, pid, naar_rol, titel}`
heeft geen enkele sleutel uit _LIST_KEYS/_TEXT_KEYS/_METRIC_KEYS, dus hij valt door naar "leeg".
Gevolg is niet alleen een misleidende logregel: een 'leeg' item wordt niet als deliverable
opgeslagen en telt sinds de missie-critic mee als kennisgat.
"""
from __future__ import annotations

from nooch_village.inhabitant import Inhabitant


def test_geslaagde_handoff_leest_als_gelukt():
    resultaat = {"ok": True, "pid": "abc123", "naar_rol": "copywriter",
                 "titel": "Compliant kopregel schrijven"}
    status, archetype = Inhabitant._classify_result(resultaat)
    assert status == "gelukt"
    assert archetype == ("text", "titel")


def test_mislukte_handoff_blijft_fout():
    status, _ = Inhabitant._classify_result({"error": "onbekende doelrol: 'x'"})
    assert status == "fout"


def test_echt_leeg_blijft_leeg():
    """De reparatie mag 'onderzocht, niets gevonden' niet stiekem als succes gaan lezen."""
    assert Inhabitant._classify_result({"ok": True})[0] == "leeg"
    assert Inhabitant._classify_result({"no_data": True, "reason": "niets"})[0] == "leeg"
    assert Inhabitant._classify_result({"hits": []})[0] == "leeg"


def test_pid_alleen_telt_ook_als_resultaat():
    """Een overdracht zonder titel (kale pid) is nog steeds een gebeurde overdracht."""
    assert Inhabitant._classify_result({"ok": True, "pid": "abc"})[0] == "gelukt"
