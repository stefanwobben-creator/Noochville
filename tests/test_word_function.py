"""Functie-as: een goedgekeurd woord is 'volg' (seed, voedt de radar) of 'doelwit' (rank-target).
Heuristiek classificeert, de mens corrigeert. Het weekrapport splitst beide."""
from __future__ import annotations
import time

from nooch_village.library import Library, classify_function
from nooch_village.inbox_actions import set_word_function
from nooch_village.cockpit import compute_digest


def test_heuristiek_classificeert():
    assert classify_function("vegan") == "volg"                       # één generiek woord
    assert classify_function("microplastics") == "volg"
    assert classify_function("vegan sneakers dames") == "doelwit"     # specifiek meerwoord
    assert classify_function("sustainable shoes") == "doelwit"
    # mega-volume head term → volg ongeacht woordenaantal
    assert classify_function("vegan shoes", {"volume": 1220000}) == "volg"
    assert classify_function("vegan shoes", {"volume": 22200}) == "doelwit"


def test_curate_zet_functie_bij_approve(tmp_path):
    lib = Library(str(tmp_path / "lib.json"))
    lib.curate("vegan", "approved", evidence={"volume": 1220000})
    lib.curate("vegan sneakers dames", "approved", evidence={"volume": 210})
    assert lib.function_of("vegan") == "volg"
    assert lib.function_of("vegan sneakers dames") == "doelwit"
    # forbidden krijgt geen functie-stempel
    lib.curate("nepwoord", "forbidden")
    assert "function" not in lib.status("nepwoord")


def test_mens_override_blijft_staan(tmp_path):
    lib = Library(str(tmp_path / "lib.json"))
    lib.curate("vegan", "approved", evidence={"volume": 1220000})     # heuristiek → volg
    lib.set_function("vegan", "doelwit")                              # mens promoveert
    assert lib.function_of("vegan") == "doelwit"
    # her-curatie (bv. nieuwe evidence) overschrijft de override NIET
    lib.curate("vegan", "approved", evidence={"volume": 1220000, "gsc_seen": False})
    assert lib.function_of("vegan") == "doelwit"


def test_set_function_via_inbox_action(tmp_path):
    lib = Library(str(tmp_path / "lib.json"))
    lib.curate("microplastics", "approved", evidence={"volume": 135000})
    ok = set_word_function(lib, "microplastics", "doelwit")
    assert ok["ok"] and lib.function_of("microplastics") == "doelwit"
    assert set_word_function(lib, "microplastics", "onzin")["ok"] is False
    assert set_word_function(lib, "bestaatniet", "volg")["ok"] is False


def test_digest_splitst_doelwit_en_volg():
    now = time.time()
    d = time.strftime("%Y-%m-%d", time.localtime(now))
    library = {
        "vegan":             {"status": "approved", "date": d,
                              "evidence": {"volume": 1220000}, "function": "volg"},
        "vegan sneakers dames": {"status": "approved", "date": d,
                                 "evidence": {"volume": 210}, "function": "doelwit"},
    }
    dg = compute_digest(library, [], [], [], now)
    assert [w["word"] for w in dg["new_seeds"]] == ["vegan"]
    assert [w["word"] for w in dg["new_targets"]] == ["vegan sneakers dames"]
