"""JsonStore-basisklasse (util.JsonStore): de gedeelde, concurrency-veilige fundering voor JSON-stores.

Bewijst drie dingen: (1) een gedeclareerde _WRITE_METHOD wordt automatisch met `synchronized` gewrapt
(neemt het slot + verse _load), (2) reads blijven ongewrapt, (3) twee ECHTE processen die gelijktijdig
schrijven overleven allebei (geen lost update) — precies de garantie waarom stores hierheen migreren.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from nooch_village.util import JsonStore

REPO = str(Path(__file__).resolve().parent.parent)


class _Counter(JsonStore):
    """Minimale dict-store: bump(key) verhoogt een teller. Eén schrijfmethode, via _save()."""
    _STATE = "_m"
    _WRITE_METHODS = ("bump",)

    def bump(self, key: str) -> None:
        self._m[key] = self._m.get(key, 0) + 1
        self._save()

    def get(self, key: str) -> int:
        return self._m.get(key, 0)


def test_write_method_is_gewrapt_met_synchronized():
    """De gedeclareerde _WRITE_METHOD is vervangen door de synchronized-wrapper (heeft __wrapped__)."""
    assert hasattr(_Counter.bump, "__wrapped__"), "bump zou door __init_subclass__ gewrapt moeten zijn"
    # een niet-gedeclareerde methode blijft ongemoeid
    assert not hasattr(_Counter.get, "__wrapped__")


def test_load_save_roundtrip(tmp_path):
    """Muteren + _save schrijft naar schijf; een verse instance leest het terug (verse _load)."""
    path = str(tmp_path / "counter.json")
    c = _Counter(path)
    c.bump("a"); c.bump("a"); c.bump("b")
    assert _Counter(path).get("a") == 2 and _Counter(path).get("b") == 1


def test_default_lege_staat(tmp_path):
    """Zonder bestand start de store leeg (default dict) i.p.v. te knallen."""
    assert _Counter(str(tmp_path / "leeg.json")).get("x") == 0


_BUMP = (
    "import sys\n"
    "from nooch_village.util import JsonStore\n"
    "class C(JsonStore):\n"
    "    _STATE='_m'; _WRITE_METHODS=('bump',)\n"
    "    def bump(self,k):\n"
    "        self._m[k]=self._m.get(k,0)+1; self._save()\n"
    "c=C(sys.argv[1]); tag=sys.argv[2]; n=int(sys.argv[3])\n"
    "for i in range(n):\n"
    "    c.bump('%s%d'%(tag,i))\n"
)


def test_gelijktijdige_processen_overleven_allemaal(tmp_path):
    """Twee ECHTE processen bumpen elk 20 unieke sleutels op dezelfde file → alle 40 overleven.
    Zonder het auto-gewrapte slot zou de een de ander overschrijven (lost update)."""
    path = str(tmp_path / "shared.json")
    _Counter(path).bump("seed")                    # bestand bestaat
    a = subprocess.Popen([sys.executable, "-c", _BUMP, path, "a", "20"], cwd=REPO)
    b = subprocess.Popen([sys.executable, "-c", _BUMP, path, "b", "20"], cwd=REPO)
    a.wait(timeout=60); b.wait(timeout=60)
    m = _Counter(path)._m
    assert sum(1 for k in m if k.startswith("a")) == 20
    assert sum(1 for k in m if k.startswith("b")) == 20
