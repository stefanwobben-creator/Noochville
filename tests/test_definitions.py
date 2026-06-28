"""Librarian metrics-database: gedeelde indicator-definities + versionering (clarify/backcast/break)."""
from __future__ import annotations

from nooch_village.definitions import DefinitionStore, MIGRATIONS


def test_add_en_current(tmp_path):
    s = DefinitionStore(str(tmp_path / "d.json"))
    d = s.add("Conversie", owner="lib", unit="%", definition="orders / bezoekers",
              direction="up", cadence="week", meettype="venster", window="7d")
    assert d is not None and d["current"] == 1 and d["owner"] == "lib"
    cur = s.current(d["id"])
    assert cur["version"] == 1 and cur["definition"] == "orders / bezoekers"
    assert cur["cadence"] == "week" and cur["meettype"] == "venster" and cur["migration"] == ""
    # lege naam => geen definitie
    assert s.add("   ") is None


def test_amend_maakt_nieuwe_versie(tmp_path):
    s = DefinitionStore(str(tmp_path / "d.json"))
    d = s.add("Bezoekers", unit="n", definition="alle sessies")
    did = d["id"]
    # 'clarify': alleen tekst, reeks blijft heel
    v2 = s.amend(did, "clarify", definition="alle sessies (excl. bots)")
    assert v2["version"] == 2 and v2["migration"] == "clarify"
    assert s.current_version_no(did) == 2
    # niet meegegeven velden erven van de vorige versie
    assert v2["unit"] == "n"
    # oude versie blijft bewaard (nooit in-place)
    assert s.version(did, 1)["definition"] == "alle sessies"
    # 'break': substantiële wijziging
    v3 = s.amend(did, "break", definition="unieke bezoekers", unit="uniek")
    assert v3["version"] == 3 and v3["migration"] == "break" and v3["unit"] == "uniek"
    assert len(s.get(did)["versions"]) == 3


def test_amend_validatie(tmp_path):
    s = DefinitionStore(str(tmp_path / "d.json"))
    d = s.add("X")
    assert s.amend(d["id"], "onzin") is None         # onbekende migratie
    assert s.amend("bestaatniet", "clarify") is None  # onbekende definitie
    assert set(MIGRATIONS) == {"clarify", "backcast", "break"}


def test_store_in_cockpit(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    assert st.defs.add("Omzet", unit="EUR") is not None
    assert len(cockpit2._Stores(dd).defs.all()) == 1   # persistent
