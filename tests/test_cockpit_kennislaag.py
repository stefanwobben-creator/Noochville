"""Kennislaag brok 3: cockpit toont soort + berekende sterkte, de gat-lijsten, en de
onbeslist-kiezer (mens kiest de soort). Plus de note_set_kind-actie."""
from __future__ import annotations
import os
import tempfile

from nooch_village import cockpit
from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight, ClaimKind, EvidenceType


def _data():
    d = tempfile.mkdtemp()
    ns = NotesStore(os.path.join(d, "notes.json"))
    # standpunt zonder bevinding = publiceer-risico
    ns.add(Insight(id="st", claim="Onze schoen is composteerbaar", source="nooch",
                   kind=ClaimKind.STANDPUNT))
    # signaal zonder bevinding = onderzoekskans
    ns.add(Insight(id="sig", claim="zoekvolume plasticvrij stijgt", source="trends",
                   kind=ClaimKind.SIGNAAL))
    # bevinding (gemeten)
    ns.add(Insight(id="bev", claim="rubber degradeert traag", source="Lab",
                   kind=ClaimKind.BEVINDING, evidence_type=EvidenceType.MEASURED))
    # onbeslist
    ns.add(Insight(id="onb", claim="iets onduidelijks", source="x"))
    return d


def test_gather_vult_kennislaag():
    snap = cockpit.gather(_data())
    kn = snap["kennis"]
    assert kn["counts"].get("standpunt") == 1 and kn["counts"].get("bevinding") == 1
    assert kn["onbeslist_total"] == 1
    assert [i["id"] for i in kn["publiceer_risico"]] == ["st"]
    assert [i["id"] for i in kn["onderzoekskansen"]] == ["sig"]


def test_render_toont_kennislaag_en_kiezer():
    h = cockpit.render_html(cockpit.gather(_data()), csrf_token="t")
    assert "Kennislaag" in h
    assert "Publiceer-risico" in h and "Onderzoekskansen" in h
    assert "Onbeslist" in h and "note_set_kind" in h     # de kiezer-knoppen
    assert "📡 signaal" in h or "signaal" in h            # soort-chips
    assert "sterkte" in h


def test_set_kind_actie_persisteert():
    d = _data()
    r = cockpit._dispatch_action(d, "note_set_kind", "onb", "", extra={"kind": "kader"})
    assert r["ok"] and r["note_kind"] == "kader"
    assert NotesStore(os.path.join(d, "notes.json")).get("onb").kind == ClaimKind.KADER
    # onbekende soort → nette fout
    bad = cockpit._dispatch_action(d, "note_set_kind", "onb", "", extra={"kind": "flauwekul"})
    assert bad["ok"] is False
