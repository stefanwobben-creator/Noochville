"""Elke nieuwe signaalregel draagt zijn eigen tijd. De oude krijgen er geen.

WAAROM (4 sep 2026): `trend_signals.jsonl` had 639 regels zonder tijdstempel. De velden die er wél
staan — `base_year`, `index_latest`, `recent_months` — beschrijven de MEETPERIODE van Google Trends,
niet het moment waarop wij keken. Daardoor kan deze store niet beantwoorden wat er "dit kwartaal"
veranderde, en dat is de vraag waarvoor een signaalstore bestaat. Het kwartaaloverzicht (#436) draait
daarom op de radar-feed, die wel een datum heeft.

GEEN TERUGWERKENDE KRACHT. Een verzonnen tijd op historie is een gefabriceerd signaal — erger dan de
eerlijke afwezigheid, want het ziet eruit als een meting.
"""
from __future__ import annotations

import json
import time

from nooch_village.skills_impl.trend_reindex import _append_signal, _SIGNALS_FILE


def _regels(tmp_path):
    return [json.loads(r) for r in (tmp_path / _SIGNALS_FILE).read_text().splitlines() if r.strip()]


def test_een_nieuwe_regel_krijgt_at_en_op(tmp_path):
    voor = time.time()
    _append_signal(str(tmp_path), {"term": "barefoot shoes", "signal_type": "stijgend"})
    r = _regels(tmp_path)[0]
    assert r["term"] == "barefoot shoes"
    assert voor <= r["at"] <= time.time()
    assert len(r["op"]) == 10 and r["op"][4] == "-"           # ISO-datum, leesbaar in het log


def test_een_meegegeven_tijd_wint(tmp_path):
    """Een herstel- of importpad mag zijn eigen tijd meebrengen; anders zou dit script de tijd van
    het SCHRIJVEN opdringen aan een observatie van gisteren."""
    _append_signal(str(tmp_path), {"term": "x", "at": 1700000000.0, "op": "2023-11-14"})
    r = _regels(tmp_path)[0]
    assert r["at"] == 1700000000.0 and r["op"] == "2023-11-14"


def test_de_bestaande_velden_blijven_ongemoeid(tmp_path):
    _append_signal(str(tmp_path), {"term": "x", "base_year": 2020, "index_latest": 88,
                                   "recent_months": [1, 2, 3]})
    r = _regels(tmp_path)[0]
    assert r["base_year"] == 2020 and r["index_latest"] == 88 and r["recent_months"] == [1, 2, 3]


def test_append_only_blijft_append_only(tmp_path):
    _append_signal(str(tmp_path), {"term": "a"})
    _append_signal(str(tmp_path), {"term": "b"})
    assert [r["term"] for r in _regels(tmp_path)] == ["a", "b"]


def test_oude_regels_zonder_tijd_blijven_leesbaar(tmp_path):
    """De 639 bestaande regels krijgen niets. Ze blijven geldig en tellen mee waar tijd niet nodig
    is; alleen tijdgebonden vragen slaan ze over."""
    pad = tmp_path / _SIGNALS_FILE
    pad.write_text(json.dumps({"term": "oud", "signal_type": "vlak"}) + "\n", encoding="utf-8")
    _append_signal(str(tmp_path), {"term": "nieuw"})
    rijen = _regels(tmp_path)
    assert "at" not in rijen[0]                               # historie ongemoeid
    assert "at" in rijen[1]
    # en een lezer kan de twee groepen scheiden zonder te raden
    met_tijd = [r for r in rijen if r.get("at")]
    assert [r["term"] for r in met_tijd] == ["nieuw"]
