"""Kennislaag brok 4: migratie met terugwerkende kracht (plan = dry-run; apply = toekennen).
Conservatief: al-gezet blijft, definities → Lexicon, twijfel → onbeslist/mens-review."""
from __future__ import annotations
import os
import tempfile

from nooch_village.insight import Insight, ClaimKind, EvidenceType
from nooch_village.notes_store import NotesStore
from nooch_village.kennis_migrate import plan_migration, apply_plan


def _store_with(notes):
    p = os.path.join(tempfile.mkdtemp(), "notes.json")
    s = NotesStore(p)
    for n in notes:
        s.add(n)
    return s


def _notes():
    return [
        Insight(id="kader", claim="EN13432 verplicht 90% afbraak in 3 maanden", source="EN"),
        Insight(id="bev", claim="rubber degradeert 15% in 236 dagen", source="Lab",
                evidence_type=EvidenceType.MEASURED),
        Insight(id="sig", claim="zoekvolume plasticvrij stijgt", source="trends"),
        Insight(id="standp", claim="Onze schoen is composteerbaar", source="nooch",
                evidence_type=EvidenceType.CLAIMED),
        Insight(id="def", claim="Vegan betekent de afwezigheid van dierlijke grondstoffen",
                source="lexicon"),
        Insight(id="al", claim="iets", source="s", kind=ClaimKind.BEVINDING),  # al gezet
        Insight(id="twijfel", claim="iets volstrekt neutraals zonder signaal", source="x"),
    ]


def test_plan_classificeert_en_telt():
    plan = plan_migration(_notes())
    by_id = {r["id"]: r for r in plan["rows"]}
    assert by_id["kader"]["proposed"] == "kader"
    assert by_id["bev"]["proposed"] == "bevinding"
    assert by_id["sig"]["proposed"] == "signaal"
    assert by_id["standp"]["proposed"] == "standpunt"
    assert by_id["def"]["proposed"] is None and "Lexicon" in by_id["def"]["note"]
    assert by_id["al"]["note"] == "al gezet — overslaan"
    assert by_id["twijfel"]["proposed"] is None and "mens-review" in by_id["twijfel"]["note"]
    s = plan["summary"]
    assert s["totaal"] == 7 and s["al_gezet"] == 1 and s["definitie_lexicon"] == 1
    assert s["onbeslist_review"] == 1


def test_dry_run_verandert_niets():
    store = _store_with(_notes())
    plan_migration(store.all())                       # plan maken raakt de store niet
    assert all(n.kind is None for n in store.all() if n.id != "al")


def test_apply_kent_toe_en_laat_twijfel_met_rust():
    store = _store_with(_notes())
    plan = plan_migration(store.all())
    applied = apply_plan(store, plan)
    assert applied == 4                               # kader, bev, sig, standp
    g = {n.id: n.kind for n in store.all()}
    assert g["kader"] == ClaimKind.KADER and g["bev"] == ClaimKind.BEVINDING
    assert g["sig"] == ClaimKind.SIGNAAL and g["standp"] == ClaimKind.STANDPUNT
    assert g["def"] is None and g["twijfel"] is None  # bewust met rust gelaten
    assert g["al"] == ClaimKind.BEVINDING             # ongemoeid


def test_apply_is_idempotent():
    store = _store_with(_notes())
    apply_plan(store, plan_migration(store.all()))
    # tweede ronde: alles wat een soort kreeg staat nu 'al gezet' → niets nieuws
    plan2 = plan_migration(store.all())
    assert apply_plan(store, plan2) == 0
