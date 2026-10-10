"""De herstel-toets van de back-up (10 oktober 2026): hij moet een kapotte snapshot herkennen."""
from __future__ import annotations

import importlib.util
import os

from nooch_village import cockpit2

_PAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts",
                    "backup_herstel_toets.py")
_spec = importlib.util.spec_from_file_location("backup_herstel_toets", _PAD)
toets_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(toets_mod)


def _data(tmp_path):
    dd = str(tmp_path / "data")
    cockpit2._bootstrap(dd)
    return dd


def test_een_gezonde_snapshot_is_te_herstellen(tmp_path):
    assert toets_mod.toets(_data(tmp_path)) == []


def test_een_half_geschreven_json_valt_op(tmp_path):
    dd = _data(tmp_path)
    open(os.path.join(dd, "people.json"), "w").write('{"half": ')
    fouten = toets_mod.toets(dd)
    assert any("people.json" in f and "geen geldige JSON" in f for f in fouten)


def test_alleen_de_laatste_jsonl_regel_mag_half_zijn(tmp_path):
    dd = _data(tmp_path)
    pad = os.path.join(dd, "log.jsonl")
    open(pad, "w").write('{"a": 1}\n{"b": ')                  # een append die net liep: geen fout
    assert toets_mod.toets(dd) == []
    open(pad, "w").write('{"a": 1}\nkapot\n{"c": 3}\n')        # middenin kapot: wel een fout
    assert any("log.jsonl" in f for f in toets_mod.toets(dd))


def test_een_lege_map_is_geen_back_up(tmp_path):
    leeg = tmp_path / "leeg"
    leeg.mkdir()
    assert toets_mod.toets(str(leeg))                          # geen records, geen mensen
    assert toets_mod.toets(str(tmp_path / "bestaat_niet")) == [f"geen map: {tmp_path / 'bestaat_niet'}"]


def test_finance_bijlagen_worden_tegen_hun_sha256_nagelopen(tmp_path):
    import hashlib
    import json
    dd = _data(tmp_path)
    os.makedirs(os.path.join(dd, "finance", "attachments", "2026"))
    blob = b"%PDF-1.4 factuur"
    rel = "finance/attachments/2026/a.pdf"
    open(os.path.join(dd, rel), "wb").write(blob)
    regel = {"id": "k1", "attachment": {"path": rel, "sha256": hashlib.sha256(blob).hexdigest()}}
    open(os.path.join(dd, "finance", "costs.jsonl"), "w").write(json.dumps(regel) + "\n")
    assert toets_mod.toets(dd) == []
    open(os.path.join(dd, rel), "ab").write(b"x")                     # beschadigd in de back-up
    assert any("sha256" in f for f in toets_mod.toets(dd))
    os.remove(os.path.join(dd, rel))
    assert any("ontbreekt" in f for f in toets_mod.toets(dd))


def test_ook_de_bijlagen_van_het_opbrengstregister(tmp_path):
    """Finance PR 1b: een subsidie-beschikking in `finance/revenue.jsonl` is net zo goed geborgd."""
    import hashlib
    import json
    dd = _data(tmp_path)
    os.makedirs(os.path.join(dd, "finance", "attachments", "2026"))
    blob = b"%PDF-1.4 beschikking"
    rel = "finance/attachments/2026/b.pdf"
    open(os.path.join(dd, rel), "wb").write(blob)
    regel = {"id": "o1", "attachment": {"path": rel, "sha256": hashlib.sha256(blob).hexdigest()}}
    open(os.path.join(dd, "finance", "revenue.jsonl"), "w").write(json.dumps(regel) + "\n")
    assert toets_mod.toets(dd) == []
    open(os.path.join(dd, rel), "ab").write(b"x")
    assert any("sha256" in f and "b.pdf" in f for f in toets_mod.toets(dd))


def test_ook_de_geimporteerde_historiebestanden(tmp_path):
    """Finance PR 2a: een importbestand in `finance/imports/` is geborgd met zijn sha256, en een
    kapotte `history.jsonl` valt op zoals elke andere JSONL."""
    import hashlib
    import json
    dd = _data(tmp_path)
    os.makedirs(os.path.join(dd, "finance", "imports"))
    blob = b"line_key;label;2025-01\nbrand;;1\n"
    rel = "finance/imports/i.csv"
    open(os.path.join(dd, rel), "wb").write(blob)
    regel = {"import_id": "i1", "attachment": {"path": rel, "sha256": hashlib.sha256(blob).hexdigest()}}
    open(os.path.join(dd, "finance", "history_imports.jsonl"), "w").write(json.dumps(regel) + "\n")
    assert toets_mod.toets(dd) == []
    open(os.path.join(dd, rel), "ab").write(b"x")
    assert any("sha256" in f and "i.csv" in f for f in toets_mod.toets(dd))
    open(os.path.join(dd, rel), "wb").write(blob)
    open(os.path.join(dd, "finance", "history.jsonl"), "w").write('{"a": 1}\nkapot\n{"b": 2}\n')
    assert any("history.jsonl" in f for f in toets_mod.toets(dd))


# ── het script zelf: een handmatige snapshot overschrijft nooit (11 oktober 2026) ─────────────

def _draai(tmp_path, *args, stempel="2026-10-11_120000", py=""):
    """Draai `backup_mac.sh` met een nep-rsync (kopieert een lokale datamap) en een vaste klok."""
    import shutil
    import subprocess
    bron = tmp_path / "bron"
    if not bron.exists():
        cockpit2._bootstrap(str(bron))
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "rsync").write_text('#!/bin/bash\nfor a; do doel="$a"; done\nmkdir -p "$doel"\n'
                                 'cp -R "$NEP_BRON"/. "$doel"\n')
    (stubs / "date").write_text(f'#!/bin/bash\nif [ "$1" = "+%Y-%m-%d_%H%M%S" ]; then echo {stempel}; '
                                f'else exec /bin/date "$@"; fi\n')
    for s in ("rsync", "date"):
        (stubs / s).chmod(0o755)
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import sys
    # NOOCH_PY: de Python van DEZE testrun. CI heeft geen `venv/` in de repo (setup-python + pip),
    # en de standaard `$REPO/venv/bin/python` bestaat daar niet.
    env = {**os.environ, "PATH": f"{stubs}:{os.environ['PATH']}", "NEP_BRON": str(bron),
           "NOOCH_BACKUP_DIR": str(tmp_path / "doel"), "NOOCH_REPO": repo, "NOOCH_BACKUP_STIL": "1",
           "NOOCH_PY": py or sys.executable}
    assert shutil.which("bash")
    return subprocess.run(["bash", os.path.join(repo, "scripts", "backup_mac.sh"), *args],
                          env=env, capture_output=True, text=True, timeout=120)


def test_handmatige_snapshot_krijgt_eigen_map_en_overschrijft_nooit(tmp_path):
    r = _draai(tmp_path, "--label", "pre-apply")
    assert r.returncode == 0, r.stdout + r.stderr
    doel = tmp_path / "doel"
    map_ = doel / "2026-10-11_120000_pre-apply"
    assert (map_ / "data").is_dir() and "herstel-toets OK" in (doel / "backup.log").read_text()
    (map_ / "data" / "merkteken.txt").write_text("vóór")
    # zelfde naam nog eens: weigeren, en de bestaande map blijft precies zoals hij was
    r2 = _draai(tmp_path, "--label", "pre-apply")
    assert r2.returncode != 0 and "overschrijft nooit" in (doel / "backup.log").read_text()
    assert (map_ / "data" / "merkteken.txt").read_text() == "vóór"
    # de dagelijkse run (zonder argumenten) blijft zijn dagmap schrijven en laat de gelabelde staan
    r3 = _draai(tmp_path)
    assert r3.returncode == 0, r3.stdout + r3.stderr
    import time as _t
    assert (doel / _t.strftime("%Y-%m-%d") / "data").is_dir() and map_.is_dir()


def test_onbekend_argument_of_leeg_label_wordt_geweigerd(tmp_path):
    assert _draai(tmp_path, "--label", "").returncode == 2
    assert _draai(tmp_path, "pre-apply").returncode == 2


def test_zonder_python_voor_de_herstel_toets_een_duidelijke_melding(tmp_path):
    """Ontbreekt de Python (geen venv, geen NOOCH_PY), dan zegt het log dat — niet alleen
    "herstel-toets faalde"."""
    r = _draai(tmp_path, "--label", "zonder-py", py=str(tmp_path / "bestaat_niet" / "python"))
    assert r.returncode == 1
    assert "geen Python voor de herstel-toets" in (tmp_path / "doel" / "backup.log").read_text()
