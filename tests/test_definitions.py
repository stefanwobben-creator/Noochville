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


def test_zaad_catalogus_valideert_tegen_schema(tmp_path):
    # de toets: elke zaad-definitie (afgeleid uit de databron-skills) MOET door het
    # Pydantic indicator-schema komen, met behoud van zijn meetmoment-velden.
    from nooch_village.definitions import _DEFINITION_SEED
    from nooch_village.metric_schema import normalize, CADANS, MEETTYPE
    assert len(_DEFINITION_SEED) >= 20
    seen = set()
    for e in _DEFINITION_SEED:
        spec = normalize(name=e["name"], unit=e.get("unit", ""), source=e.get("source", ""),
                         definition=e.get("definition", ""), direction=e.get("direction", ""),
                         cadence=e.get("cadence", "ad-hoc"), meettype=e.get("meettype", "snapshot"),
                         window=e.get("window", ""))
        assert spec is not None, f"zaad-definitie valideert niet: {e['name']}"
        # geen stille terugval: de opgegeven cadans/meettype moeten bewaard blijven
        assert spec["cadence"] == e.get("cadence", "ad-hoc"), f"cadans gevallen bij {e['name']}"
        assert spec["meettype"] == e.get("meettype", "snapshot"), f"meettype gevallen bij {e['name']}"
        assert spec["cadence"] in CADANS and spec["meettype"] in MEETTYPE
        key = (e["name"], e.get("source", ""))
        assert key not in seen, f"dubbele zaad-definitie: {key}"
        seen.add(key)


def test_seed_catalog_idempotent(tmp_path):
    from nooch_village.definitions import seed_catalog, _DEFINITION_SEED
    s = DefinitionStore(str(tmp_path / "d.json"))
    n1 = seed_catalog(s)
    assert n1 == len(_DEFINITION_SEED) and len(s.all()) == n1
    assert seed_catalog(s) == 0 and len(s.all()) == n1   # tweede keer voegt niets toe
    # nieuwe cadans-waarden uit de inventaris zijn nu geldig
    assert any(s.current(d["id"])["cadence"] == "jaar" for d in s.all())
    assert any(s.current(d["id"])["cadence"] == "uur" for d in s.all())


def test_store_in_cockpit(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    base = len(st.defs.all())                          # bootstrap heeft de catalogus geseed
    assert base >= 20
    assert st.defs.add("Omzet", unit="EUR") is not None
    assert len(cockpit2._Stores(dd).defs.all()) == base + 1   # persistent
