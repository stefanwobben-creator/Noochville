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


def _fake_notes(cards):
    """Mini NotesStore-dubbel voor tag/merge-tests: cards = [(id, claim, tags, grounding, created)]."""
    import re as _re

    class Note:
        def __init__(s, i, c, tags, g, cr):
            s.id, s.claim, s.tags, s.archived = i, c, list(tags), False
            s.grounding_count, s.created_at = g, cr

    class Notes:
        _path = "data/notes.json"
        def __init__(s): s.cards = [Note(*c) for c in cards]; s.merges = []
        def all(s): return s.cards
        def get(s, i): return next((a for a in s.cards if a.id == i), None)
        def retag(s, oud, nieuw=None):
            n = 0
            for a in s.cards:
                if oud in a.tags:
                    a.tags = [(nieuw if t == oud else t) for t in a.tags if (t != oud or nieuw)]
                    # dedup
                    seen = []; a.tags = [t for t in a.tags if not (t in seen or seen.append(t))]
                    n += 1
            return n
        def merge_into(s, tgt, src, tekst, by=""):
            a = s.get(src)
            if a: a.archived = True; s.merges.append((tgt, src)); return a
            return None
    return Notes()


def test_kennis_tags_hints():
    from nooch_village import kennis_tags
    notes = _fake_notes([
        ("a", "x", ["hint:leer", "hint:circulariteit", "signal"], 0, "2026-01-01"),
        ("b", "y", ["hint:leer", "hint:circulariteit"], 0, "2026-01-02"),
        ("c", "z", ["hint:circulariteit", "hint:kurkzooltje"], 0, "2026-01-03"),
    ])
    # hint:leer is exact een onderwerp → deterministische map (geen LLM nodig)
    plan = kennis_tags.plan_hints(notes, reason_fn=lambda *a, **k: '{"circulariteit":"materiaal","kurkzooltje":"NONE"}',
                                  drempel_nieuw=4)
    assert plan["map"].get("leer") == "leer"
    assert plan["map"].get("circulariteit") == "materiaal"     # via LLM
    assert "kurkzooltje" in plan["drop"]                        # LLM NONE + zeldzaam
    r = kennis_tags.pas_hints_toe(notes, plan)
    assert r["gemapt"] == 2 and r["gedropt"] == 1
    # na toepassen: geen hint:*-tags meer, wel de echte onderwerpen
    alle = {t for a in notes.all() for t in a.tags}
    assert not any(t.startswith("hint:") for t in alle)
    assert "leer" in alle and "materiaal" in alle

    # geen LLM → alleen exacte map, rest onaangeroerd (nooit stil weggooien)
    notes2 = _fake_notes([("a", "x", ["hint:leer", "hint:vaagconcept"], 0, "2026-01-01")])
    plan2 = kennis_tags.plan_hints(notes2, reason_fn=False)     # False → geen LLM
    assert plan2["map"].get("leer") == "leer" and "vaagconcept" in plan2["onaangeroerd"]


def test_kennis_merge_clusters():
    from nooch_village import kennis_merge
    notes = _fake_notes([
        ("a", "EU Ecolabel koppelt textiel aan de circulaire economie", [], 3, "2026-01-01"),
        ("b", "EU Ecolabel koppelt textiel aan circulaire economie inclusief herkomst", [], 1, "2026-01-05"),
        ("c", "Mycelium groeit snel op landbouwreststromen", [], 0, "2026-01-02"),
    ])
    zelfde = lambda nieuw, best, rf=None, **k: "zelfde"        # signatuur van _llm_zelfde
    # _llm_zelfde(nieuw, bestaand, reason_fn) → wij faken via reason_fn die alles 'ZELFDE' noemt
    res = kennis_merge.vind_clusters(notes, reason_fn=lambda *a, **k: "ZELFDE",
                                     lex_drempel=0.5, sem_drempel=0.99)
    assert len(res["clusters"]) == 1
    cl = res["clusters"][0]
    assert cl["target"] == "a"                                 # meeste grounding wint
    assert cl["sources"][0]["id"] == "b"
    r = kennis_merge.pas_merge_toe(notes, res["clusters"])
    assert r["kaarten_opgeruimd"] == 1 and notes.get("b").archived
