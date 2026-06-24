"""Opstart-rapport van API-sleutels: zelfbeschrijvend, niet-blokkerend, geen sleutel-lek."""
from __future__ import annotations

from nooch_village.key_audit import audit_keys, format_key_report
from nooch_village.skills import Skill, SkillRegistry


class _Ctx:
    def __init__(self, settings):
        self.settings = settings


class _NeedsBoth(Skill):
    name = "needs_both"
    required_env = ("FOO_KEY", "BAR_ID")
    def run(self, payload, context):    # pragma: no cover - niet aangeroepen
        return {}


class _Optional(Skill):
    name = "optional_only"
    optional_env = ("NICE_TO_HAVE",)
    def run(self, payload, context):    # pragma: no cover
        return {}


class _NoKeys(Skill):
    name = "no_keys"
    def run(self, payload, context):    # pragma: no cover
        return {}


def _registry(*skills):
    r = SkillRegistry()
    for s in skills:
        r.register(s)
    return r


def test_skill_zonder_sleutels_komt_niet_in_rapport():
    audit = audit_keys(_registry(_NoKeys()), _Ctx({}), environ={})
    assert audit["skills"] == []          # alleen skills met externe sleutels worden gerapporteerd


def test_harde_sleutel_aanwezig_maakt_skill_actief():
    audit = audit_keys(_registry(_NeedsBoth()), _Ctx({}),
                       environ={"FOO_KEY": "x", "BAR_ID": "y"})
    s = audit["skills"][0]
    assert s["active"] is True
    assert all(r["ok"] for r in s["required"])


def test_ontbrekende_harde_sleutel_faalt_closed():
    audit = audit_keys(_registry(_NeedsBoth()), _Ctx({"FOO_KEY": "x"}), environ={})
    s = audit["skills"][0]
    assert s["active"] is False           # BAR_ID mist → niet scherp
    assert any(not r["ok"] for r in s["required"])


def test_optionele_sleutel_houdt_skill_actief():
    audit = audit_keys(_registry(_Optional()), _Ctx({}), environ={})
    s = audit["skills"][0]
    assert s["active"] is True            # geen harde eis → altijd actief
    assert s["optional"][0]["ok"] is False


def test_settings_telt_net_als_environ():
    # GSC-stijl: sleutel in settings.ini i.p.v. de omgeving
    audit = audit_keys(_registry(_NeedsBoth()),
                       _Ctx({"FOO_KEY": "a", "BAR_ID": "b"}), environ={})
    assert audit["skills"][0]["active"] is True


def test_ladder_meldt_per_trede_of_er_een_sleutel_is(monkeypatch):
    import nooch_village.llm as llm
    monkeypatch.setattr(llm, "_ladder", lambda: [("gemini", "g1"), ("mistral", "m1"),
                                                 ("anthropic", "a1")])
    audit = audit_keys(_registry(), _Ctx({}),
                       environ={"GEMINI_API_KEY": "x", "ANTHROPIC_API_KEY": "y"})
    by = {t["vendor"]: t["ok"] for t in audit["ladder"]}
    assert by == {"gemini": True, "mistral": False, "anthropic": True}


def test_rapport_lekt_geen_sleutelwaarden():
    audit = audit_keys(_registry(_NeedsBoth()), _Ctx({}),
                       environ={"FOO_KEY": "supergeheim123", "BAR_ID": "ook-geheim"})
    txt = format_key_report(audit)
    assert "supergeheim123" not in txt and "ook-geheim" not in txt
    assert "FOO_KEY" in txt and "✓" in txt
