"""WerkoverlegStore concurrency-safe + set_checkout status-guard.

Twee ECHTE processen (subprocess, zoals #161) muteren dezelfde werkoverleg.json: zonder de
gesynchroniseerde schrijfpaden verliest er één (raw save op een stale kopie); mét het slot overleven
beide en overleeft de close-snapshot. Plus: een check-out op een gesloten overleg wordt fail-loud
geweigerd (geen stille mutatie).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from nooch_village.werkoverleg import WerkoverlegStore

REPO = str(Path(__file__).resolve().parent.parent)
C = "mother_earth__nooch"

_CHECKOUTS = (
    "import sys\n"
    "from nooch_village.werkoverleg import WerkoverlegStore\n"
    "W = WerkoverlegStore(sys.argv[1]); c = sys.argv[2]; tag = sys.argv[3]; n = int(sys.argv[4])\n"
    "for i in range(n):\n"
    "    W.set_checkout(c, 'p_%s%d' % (tag, i), 8)\n"
)
_CLOSE = (
    "import sys\n"
    "from nooch_village.werkoverleg import WerkoverlegStore\n"
    "WerkoverlegStore(sys.argv[1]).close(sys.argv[2])\n"
)


def _run(code, *args):
    return subprocess.Popen([sys.executable, "-c", code, *map(str, args)], cwd=REPO)


def test_gelijktijdige_checkouts_overleven_allemaal(tmp_path):
    """Twee processen zetten elk 8 check-outs op hetzelfde open overleg → alle 16 overleven (geen lost update)."""
    path = str(tmp_path / "werkoverleg.json")
    W = WerkoverlegStore(path); W.open(C)
    a = _run(_CHECKOUTS, path, C, "a", 8)
    b = _run(_CHECKOUTS, path, C, "b", 8)          # gelijktijdig
    a.wait(timeout=60); b.wait(timeout=60)
    st = WerkoverlegStore(path).get(C)
    assert len(st.get("checkout", {})) == 16       # geen enkele schrijver klobbert de ander


def test_close_en_checkout_gelijktijdig_snapshot_overleeft(tmp_path):
    """Proces A sluit (snapshot), proces B zet check-outs — de snapshot overleeft (niet geklobberd)."""
    path = str(tmp_path / "werkoverleg.json")
    W = WerkoverlegStore(path); W.open(C)
    a = _run(_CLOSE, path, C)
    b = _run(_CHECKOUTS, path, C, "b", 8)          # gelijktijdig met de close
    a.wait(timeout=60); b.wait(timeout=60)
    st = WerkoverlegStore(path).get(C)
    assert st["status"] == "closed"
    assert len(st.get("log", [])) == 1             # precies één snapshot — de close-write overleeft de race


def test_set_checkout_op_closed_geweigerd(tmp_path, caplog):
    """Een score op een gesloten overleg → fail-loud geweigerd (False + WARNING), geen mutatie."""
    path = str(tmp_path / "werkoverleg.json")
    W = WerkoverlegStore(path); W.open(C); W.close(C)   # gesloten, met snapshot; checkout leeg
    with caplog.at_level("WARNING", logger="nooch.refuse"):
        ok = W.set_checkout(C, "p1", 9)
    assert ok is False
    st = WerkoverlegStore(path).get(C)                  # verse read van schijf
    assert st.get("checkout", {}) == {}                 # geen stille mutatie
    assert any("WERK_CHECKOUT_ON_CLOSED" in r.getMessage() for r in caplog.records)


def test_set_checkout_op_open_lukt(tmp_path):
    """Sanity: op een open overleg lukt de score wél (True) en landt hij."""
    path = str(tmp_path / "werkoverleg.json")
    W = WerkoverlegStore(path); W.open(C)
    assert W.set_checkout(C, "p1", 7) is True
    assert WerkoverlegStore(path).get(C)["checkout"]["p1"] == 7
