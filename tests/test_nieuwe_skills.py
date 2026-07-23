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


def test_beide_in_registry():
    from nooch_village.registry_factory import build_skill_registry
    reg = build_skill_registry()
    assert reg.get("ruis_check") is not None
    assert reg.get("escaleer") is not None
