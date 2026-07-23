"""Twee nieuwe skills (founder 20 jul): ruis_check (te brede zoekopdracht = ongeldige meting,
niet een bevinding) en escaleer (een rol routeert bewust naar de juiste rol of de Founding
Farmer). Beide deterministisch, met een Kroniek-brug."""
from __future__ import annotations

import json
import types

from nooch_village.evidence_ledger import classify_result
from nooch_village.notifications import NotifStore
from nooch_village.skills_impl.escaleer import EscaleerSkill
from nooch_village.skills_impl.ruis_check import RuisCheckSkill


def test_ruis_check_drempel_en_kroniek():
    sk = RuisCheckSkill()
    ctx = types.SimpleNamespace(settings={})
    breed = sk.run({"query": "shoes", "aantal": 3079427}, ctx)
    assert breed["status"] == "te_breed" and "te breed" in breed["oordeel"]
    assert sk.evidence_records(breed, role_id="harry_hemp")[0]["status"] == "fout"
    ok = sk.run({"query": "PHA barefoot outsole", "aantal": 42}, ctx)
    assert ok["status"] == "bruikbaar"
    assert sk.evidence_records(ok, role_id="harry_hemp")[0]["status"] == "bevestigd"
    # override-drempel + fail-net bij ontbrekende/ongeldige input
    assert sk.run({"query": "x", "aantal": 100, "drempel": 50}, ctx)["status"] == "te_breed"
    assert "error" in sk.run({"query": "x"}, ctx)
    assert "error" in sk.run({"query": "x", "aantal": "veel"}, ctx)
    assert RuisCheckSkill.required_payload == ("query", "aantal")


def test_escaleer_landt_als_notificatie(tmp_path):
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    sk = EscaleerSkill()
    # 'founder' → the_source
    r = sk.run({"reden": "twijfel over de barefoot-claim", "naar": "founder", "van": "Lara"}, ctx)
    assert r["ok"] and r["naar"] == "the_source"
    notif = NotifStore(f"{tmp_path}/notifications.json")
    got = notif.for_targets([("role", "the_source")])
    assert got and "twijfel over de barefoot-claim" in got[0]["snippet"]
    assert sk.evidence_records(r, role_id="librarian")[0]["status"] == "bevestigd"
    # naar een concrete rol (aard='beslissing' expliciet)
    r2 = sk.run({"reden": "mogen we dit loslaten?", "naar": "compliance", "aard": "beslissing"}, ctx)
    assert r2["naar"] == "compliance" and r2["aard"] == "beslissing"
    assert NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "compliance")])
    # aard='bevinding' → uitkomst vastgelegd, GEEN notificatie naar de mens
    voor = len(NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "the_source")]))
    rb = sk.run({"reden": "geen enkel alternatief voldoet aan de eisen", "aard": "bevinding"}, ctx)
    assert rb["ok"] and rb["aard"] == "bevinding" and rb.get("text")
    na = len(NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "the_source")]))
    assert na == voor          # een bevinding landt niet bij de founder
    # fail-net: alleen 'reden' is nog verplicht (naar is optioneel geworden → default founder)
    assert "error" in sk.run({"aard": "beslissing"}, ctx)
    assert sk.run({"reden": "x", "aard": "beslissing"}, ctx)["naar"] == "the_source"


def test_kennis_dedup_poort():
    """De voorkant-poort: exact/near stapelt, grijs zonder LLM = twijfel (fail-open), ver = nieuw."""
    import re as _re
    from nooch_village.kennis_dedup import beoordeel_kaart

    class _N:
        def __init__(s, cards): s.cards = cards
        def _norm(s, t): return _re.sub(r"[^a-z0-9]", "", (t or "").lower())
        def find_claim_equal(s, c):
            d = s._norm(c)
            return next((i for i, cl in s.cards if s._norm(cl) == d), None)
        def _tok(s, t): return frozenset(w for w in _re.split(r"[\W_]+", (t or "").lower()) if len(w) >= 4)
        def gelijkende(s, c, drempel=0.55):
            doel = s._tok(c); best = None
            for i, cl in s.cards:
                w = s._tok(cl)
                if not w: continue
                sc = len(doel & w) / len(doel | w)
                if sc >= drempel and (best is None or sc > best[2]): best = (i, cl, sc)
            return best

    notes = _N([("k1", "EU Ecolabel koppelt textiel aan de circulaire economie")])
    geen_llm = lambda *a, **k: None
    # exact → stapel
    assert beoordeel_kaart("EU Ecolabel koppelt textiel aan de circulaire economie", notes,
                           reason_fn=geen_llm)["verdict"] == "stapel"
    # lexicaal dichtbij, geen LLM → twijfel (nieuw + markering, nooit stil stapelen)
    assert beoordeel_kaart("EU Ecolabel koppelt textiel aan circulaire economie voortaan", notes,
                           reason_fn=geen_llm)["verdict"] in ("twijfel", "stapel")
    # grijze band mét LLM-oordeel 'zelfde' → stapel
    assert beoordeel_kaart("EU Ecolabel koppelt textiel aan circulaire economie voortaan", notes,
                           reason_fn=lambda *a, **k: "ZELFDE")["verdict"] == "stapel"
    # ver weg → nieuw
    assert beoordeel_kaart("Mycelium groeit snel op landbouwreststromen", notes,
                           reason_fn=geen_llm)["verdict"] == "nieuw"
    # leeg → nieuw (fail-open)
    assert beoordeel_kaart("", notes, reason_fn=geen_llm)["verdict"] == "nieuw"


def test_kennis_embeddings_laag(tmp_path):
    """Semantische laag: cosine, store-roundtrip, en de poort die een parafrase-buur (lexicaal ver)
    via de LLM-oordeler alsnog stapelt — de biobased-drieling-case."""
    import re as _re
    from nooch_village.kennis_embeddings import cosine, EmbeddingStore, SemantiekIndex
    from nooch_village.kennis_dedup import beoordeel_kaart

    assert abs(cosine([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-9
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([], [1]) == 0.0 and cosine([1, 2], [1, 2, 3]) == 0.0

    # Store round-trip via schijf
    st = EmbeddingStore(f"{tmp_path}/kennis_embeddings.json")
    st.upsert("k1", "bio-based is ver genoeg", [1.0, 0.0, 0.0])
    st.save()
    st2 = EmbeddingStore(f"{tmp_path}/kennis_embeddings.json")
    assert len(st2) == 1 and st2.hash_of("k1") == st.hash_of("k1")

    class Note:
        def __init__(s, i, c): s.id, s.claim, s.archived = i, c, False

    class Notes:
        _path = f"{tmp_path}/notes.json"
        def __init__(s, cards): s.cards = [Note(i, c) for i, c in cards]
        def get(s, i): return next((a for a in s.cards if a.id == i), None)
        def _n(s, t): return _re.sub(r"[^a-z0-9]", "", (t or "").lower())
        def find_claim_equal(s, c):
            d = s._n(c); return next((a.id for a in s.cards if s._n(a.claim) == d), None)
        def _t(s, t): return frozenset(w for w in _re.split(r"[\W_]+", (t or "").lower()) if len(w) >= 4)
        def gelijkende(s, c, drempel=0.55): return None      # dwing de semantische tak (lexicaal niets)

    notes = Notes([("k1", "Volledig bio-based materialen zijn ver genoeg ontwikkeld")])
    # Een index die k1 als sterke betekenis-buur teruggeeft (embed_fn niet nodig — candidate is gefaket)
    idx = SemantiekIndex(f"{tmp_path}/notes.json")
    idx.candidate = lambda claim, notes, drempel=0.82: ("k1", notes.get("k1").claim, 0.91)

    zelfde = lambda *a, **k: "ZELFDE"
    geen = lambda *a, **k: None
    r = beoordeel_kaart("Voor gelijmde schoenen is composteerbaarheid de route", notes,
                        reason_fn=zelfde, semantiek=idx)
    assert r["verdict"] == "stapel" and r["kaart_id"] == "k1"
    r2 = beoordeel_kaart("Voor gelijmde schoenen is composteerbaarheid de route", notes,
                         reason_fn=geen, semantiek=idx)
    assert r2["verdict"] == "twijfel"          # geen LLM → markeren, nooit stil stapelen
    r3 = beoordeel_kaart("iets totaal anders", notes, reason_fn=zelfde, semantiek=False)
    assert r3["verdict"] == "nieuw"            # semantiek uit + lexicaal niets → nieuw


def test_beide_in_registry():
    from nooch_village.registry_factory import build_skill_registry
    reg = build_skill_registry()
    assert reg.get("ruis_check") is not None
    assert reg.get("escaleer") is not None
