"""Payload-contract op de woord-skills (founder 19-20 jul): library_lookup, keyword_review
en budget_adjust indexeerden hun payload hard (payload["word"]) zonder required_payload te
declareren, dus de planner-poort (inhabitant._missing_required) liet een bundel-in-één of
leeg veld door en de skill crashte live met de cryptische KeyError 'word' (Lara's blokkade).

Twee borgingen per skill: (1) het contract is nu gedeclareerd, zodat de planner het item
vóór uitvoering afvangt; (2) defense-in-depth — sluipt er tóch een payload zonder het veld
door (andere aanroeproute), dan geeft run() een nette {"error": ...} i.p.v. een KeyError,
zodat de Kroniek een leesbaar 'fout'-feit krijgt i.p.v. 'word'."""
from __future__ import annotations

import types

from nooch_village.evidence_ledger import classify_result
from nooch_village.skills_impl.budget import BudgetSkill
from nooch_village.skills_impl.library_skills import (KeywordReviewSkill,
                                                      LibraryLookupSkill)


class _Lib:
    def status(self, word):
        return None


def _ctx(tmp_path=None):
    return types.SimpleNamespace(library=_Lib(), settings={},
                                 data_dir=str(tmp_path) if tmp_path else ".")


def test_contract_gedeclareerd():
    # het machine-leesbare contract dat de planner-poort leest
    assert LibraryLookupSkill.required_payload == ("word",)
    assert KeywordReviewSkill.required_payload == ("word",)
    assert BudgetSkill.required_payload == ("line", "delta_eur")


def test_library_lookup_faalt_net_zonder_word():
    r = LibraryLookupSkill().run({}, _ctx())
    assert "error" in r and "word" in r["error"]
    assert classify_result(r) == "fout"                    # leesbaar Kroniek-feit, geen KeyError
    # mét word werkt hij gewoon
    ok = LibraryLookupSkill().run({"word": "barefoot shoes"}, _ctx())
    assert ok["word"] == "barefoot shoes" and ok["status"] == "unknown"


def test_keyword_review_faalt_net_zonder_word():
    r = KeywordReviewSkill().run({"demand": {}}, _ctx())    # bundel zonder 'word'
    assert "error" in r and "word" in r["error"]
    assert classify_result(r) == "fout"


def test_budget_faalt_net_zonder_velden(tmp_path):
    sk = BudgetSkill()
    assert "error" in sk.run({"line": "materiaal"}, _ctx(tmp_path))       # delta mist
    assert "error" in sk.run({"delta_eur": 10}, _ctx(tmp_path))          # line mist
    assert "error" in sk.run({"line": "x", "delta_eur": "n/a"}, _ctx(tmp_path))  # geen getal
    ok = sk.run({"line": "materiaal", "delta_eur": 12.5}, _ctx(tmp_path))
    assert ok["new_line_total"] == 12.5
