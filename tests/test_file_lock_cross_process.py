"""Cross-proces-lock: twee ECHTE processen (subprocess) muteren dezelfde projects.json. Zonder de
fcntl-flock verliest er één (raw save op een stale kopie); met de gesynchroniseerde schrijfpaden
overleven beide. Plus: flock-timeout geeft een nette fout, en het slot komt vrij bij procesdood (OS).
"""
from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from nooch_village.projects import ProjectLedger
from nooch_village.util import file_lock

REPO = str(Path(__file__).resolve().parent.parent)
OWNER = "mother_earth__nooch__website_developer"


def _run(code, *args, wait=True):
    p = subprocess.Popen([sys.executable, "-c", code, *map(str, args)], cwd=REPO)
    if wait:
        p.wait(timeout=60)
    return p


_SYNC = (
    "import sys\n"
    "from nooch_village.projects import ProjectLedger\n"
    "path, pid, field, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])\n"
    "L = ProjectLedger(path)\n"
    "for i in range(n):\n"
    "    if field == 'att': L.attach_add(pid, url='u%d' % i, title='a%d' % i)\n"
    "    else: L.add_feed_entry(pid, 'm%d' % i, kind='comment', author_type='human')\n"
)


def test_cross_process_gesynchroniseerd_overleeft(tmp_path):
    path = str(tmp_path / "projects.json")
    pid = ProjectLedger(path).create(OWNER, "T", "human")
    N = 12
    a = _run(_SYNC, path, pid, "att", N, wait=False)     # proces A: N bijlagen
    b = _run(_SYNC, path, pid, "log", N, wait=False)     # proces B: N feed-entries — gelijktijdig
    a.wait(timeout=60); b.wait(timeout=60)
    p = ProjectLedger(path).get(pid)
    assert len(p.get("attachments", [])) == N and len(p.get("log", [])) == N   # beide volledig overleven


_RAW = (
    "import sys, os, time\n"
    "from nooch_village.projects import ProjectLedger\n"
    "path, pid, field, ready, other = sys.argv[1:6]\n"
    "L = ProjectLedger(path)\n"                            # laadt de begintoestand (leeg field)
    "open(ready, 'w').close()\n"                           # signaal: ik heb gelezen
    "t = time.monotonic()\n"
    "while not os.path.exists(other) and time.monotonic() - t < 15: time.sleep(0.01)\n"   # barrier
    "L._projects[pid].setdefault(field, []).append({'v': 1})\n"   # muteer de STALE kopie
    "L._save()\n"                                          # RAW save: geen slot, geen verse read
)


def test_cross_process_zonder_lock_verliest_een(tmp_path):
    path = str(tmp_path / "projects.json")
    pid = ProjectLedger(path).create(OWNER, "T", "human")
    rA, rB = str(tmp_path / "rA"), str(tmp_path / "rB")
    a = _run(_RAW, path, pid, "attachments", rA, rB, wait=False)
    b = _run(_RAW, path, pid, "log", rB, rA, wait=False)
    a.wait(timeout=30); b.wait(timeout=30)
    p = ProjectLedger(path).get(pid)
    # beide lazen dezelfde lege staat en schreven rauw hun eigen kopie → de laatste save wint, één verloren
    assert len(p.get("attachments", [])) + len(p.get("log", [])) == 1


def test_flock_timeout_geeft_nette_fout(tmp_path, monkeypatch):
    path = str(tmp_path / "projects.json")
    ProjectLedger(path).create(OWNER, "T", "human")
    monkeypatch.setenv("NOOCH_FILE_LOCK_TIMEOUT_S", "0.3")
    fd = os.open(path + ".lock", os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)                         # houd het slot rauw vast
    try:
        t0 = time.monotonic()
        with pytest.raises(TimeoutError):
            with file_lock(path):
                pass
        assert time.monotonic() - t0 < 3                  # faalde binnen ~timeout, geen eeuwige hang
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)


_HOLDER = (
    "import sys, os, time, fcntl\n"
    "fd = os.open(sys.argv[1] + '.lock', os.O_CREAT | os.O_RDWR)\n"
    "fcntl.flock(fd, fcntl.LOCK_EX)\n"
    "open(sys.argv[2], 'w').close()\n"                     # signaal: slot gepakt
    "time.sleep(30)\n"
)


def test_flock_vrij_na_procesdood(tmp_path):
    path = str(tmp_path / "projects.json")
    ProjectLedger(path).create(OWNER, "T", "human")
    ready = str(tmp_path / "held")
    holder = _run(_HOLDER, path, ready, wait=False)
    t = time.monotonic()
    while not os.path.exists(ready) and time.monotonic() - t < 10:
        time.sleep(0.01)
    assert os.path.exists(ready), "holder pakte het slot niet"
    holder.kill(); holder.wait(timeout=10)                # dood het proces MET het slot vast
    t0 = time.monotonic()
    with file_lock(path):                                 # OS gaf de flock vrij → direct te pakken
        pass
    assert time.monotonic() - t0 < 3, "slot niet vrijgegeven na procesdood (deadlock)"
