"""once_sandbox() draait een puls tegen een wegwerp-kopie en raakt de bron-data nooit; de
gedeelde _run_single_pulse-helper houdt once() extern identiek (default data/)."""
from __future__ import annotations
import os
from types import SimpleNamespace

from nooch_village import village


class _FakeVillage:
    def __init__(self, heartbeat_seconds=None, data_dir=None):
        self.heartbeat_seconds = heartbeat_seconds
        self.context = SimpleNamespace(data_dir=data_dir)


def test_once_sandbox_raakt_bron_niet_en_draait_tegen_kopie(tmp_path, monkeypatch):
    src = tmp_path / "data"
    src.mkdir()
    sentinel = src / "governance_records.json"
    sentinel.write_text('{"SENTINEL": "onaangeroerd"}', encoding="utf-8")
    before = sentinel.read_bytes()

    seen = {}
    def fake_pulse(v):
        seen["data_dir"] = v.context.data_dir
        # schrijf in de sandbox: bewijs dat schrijven in de KOPIE landt, niet in de bron
        with open(os.path.join(v.context.data_dir, "governance_records.json"), "w") as f:
            f.write('{"MUTATED": true}')

    monkeypatch.setattr(village, "Village", _FakeVillage)
    monkeypatch.setattr(village, "_run_single_pulse", fake_pulse)

    tmp = village.once_sandbox(src=str(src))

    assert sentinel.read_bytes() == before          # bron byte-identiek
    assert seen["data_dir"] != str(src)             # puls draaide tegen een KOPIE
    assert not os.path.exists(tmp)                  # default: kopie opgeruimd


def test_once_sandbox_keep_behoudt_kopie(tmp_path, monkeypatch):
    src = tmp_path / "data"; src.mkdir()
    (src / "governance_records.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(village, "Village", _FakeVillage)
    monkeypatch.setattr(village, "_run_single_pulse", lambda v: None)
    tmp = village.once_sandbox(keep=True, src=str(src))
    try:
        assert os.path.exists(tmp)                                          # --keep: blijft staan
        assert os.path.exists(os.path.join(tmp, "governance_records.json"))  # echte spiegel
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_once_gebruikt_default_datadir_via_helper(monkeypatch):
    # once() blijft extern identiek: Village ZONDER data_dir (=> default data/) + delegatie.
    seen = {}
    monkeypatch.setattr(village, "Village", _FakeVillage)
    monkeypatch.setattr(village, "_run_single_pulse",
                        lambda v: seen.update(data_dir=v.context.data_dir, ran=True))
    village.once()
    assert seen["ran"] is True
    assert seen["data_dir"] is None
