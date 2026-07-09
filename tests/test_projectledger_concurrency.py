"""ProjectLedger concurrency: alle schrijfpaden serialiseren via file_lock + verse read onder het slot,
zodat gelijktijdige schrijvers elkaars mutaties niet meer overschrijven (de lost-update die geüploade
bijlagen liet verdwijnen). Reads blijven lock-vrij (board-watch wacht niet).
"""
from __future__ import annotations

import ast
import inspect
import threading

from nooch_village import projects as P
from nooch_village.projects import ProjectLedger
from nooch_village.util import file_lock

OWNER = "mother_earth__nooch__website_developer"


def _seed(tmp_path):
    path = str(tmp_path / "projects.json")
    pid = ProjectLedger(path).create(OWNER, "T", "human")
    return path, pid


# ── bewijst de race: zonder verse read onder het slot verliest er één ────────────
def test_zonder_verse_read_verliest_een_mutatie(tmp_path):
    path, pid = _seed(tmp_path)
    A = ProjectLedger(path)
    B = ProjectLedger(path)                       # beide laden dezelfde begintoestand
    # muteer DIRECT op de in-memory kopie en save rauw — dit is het oude read-modify-write-op-stale-kopie
    A._projects[pid].setdefault("attachments", []).append({"kind": "file", "name": "van A"})
    B._projects[pid].setdefault("log", []).append({"text": "van B"})
    A._save()
    B._save()                                     # B schrijft z'n stale kopie over A heen
    fresh = ProjectLedger(path).get(pid)
    assert not fresh.get("attachments") and len(fresh.get("log", [])) == 1   # A's mutatie is verloren


# ── met de gesynchroniseerde schrijfpaden overleven beide mutaties ───────────────
def test_gesynchroniseerde_writes_overleven_beide(tmp_path):
    path, pid = _seed(tmp_path)
    A = ProjectLedger(path)
    B = ProjectLedger(path)                       # beide 'oud' geladen; de synchronized-wrapper leest vers
    A.attach_add(pid, url="http://a", title="van A")          # slot + verse read + save
    B.add_feed_entry(pid, "van B", kind="comment", author_type="human")   # idem
    fresh = ProjectLedger(path).get(pid)
    assert len(fresh.get("attachments", [])) == 1 and len(fresh.get("log", [])) == 1   # beide overleven


def test_afwisselende_writers_alle_mutaties_overleven(tmp_path):
    path, pid = _seed(tmp_path)
    A = ProjectLedger(path); B = ProjectLedger(path)
    for i in range(5):                            # om en om, beide instanties 'stale' tussen de writes
        A.attach_add(pid, url=f"http://a{i}", title=f"A{i}")
        B.add_feed_entry(pid, f"B{i}", kind="comment", author_type="human")
    fresh = ProjectLedger(path).get(pid)
    assert len(fresh.get("attachments", [])) == 5 and len(fresh.get("log", [])) == 5


# ── performance-sanity: een read wacht NIET op het write-slot ────────────────────
def test_read_wacht_niet_op_write_slot(tmp_path):
    path, pid = _seed(tmp_path)
    L = ProjectLedger(path)
    done = []
    with file_lock(path):                         # simuleer een lopende write (slot vastgehouden)
        t = threading.Thread(target=lambda: (L.get(pid), L.all(), done.append(1)))
        t.start(); t.join(timeout=3)
    assert done, "een read blokkeerde op het write-slot (board-watch zou wachten)"


# ── guard: elke methode die _save() aanroept staat in _WRITE_METHODS ─────────────
def test_alle_schrijfpaden_gesynchroniseerd():
    tree = ast.parse(inspect.getsource(P))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ProjectLedger")
    savers = set()
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name != "_save":
            if any(isinstance(s, ast.Attribute) and s.attr == "_save" for s in ast.walk(node)):
                savers.add(node.name)
    missing = savers - set(P._WRITE_METHODS)
    assert not missing, f"schrijfpaden niet in _WRITE_METHODS (niet gesynchroniseerd): {sorted(missing)}"
    # geen dode namen in de lijst (elke naam bestaat als methode)
    assert all(hasattr(ProjectLedger, m) for m in P._WRITE_METHODS)
