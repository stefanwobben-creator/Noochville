"""Site audit — de lampjes van de shop, samengesteld uit bestaande checks, met uitleg en verloop.

Aanleiding (11 september 2026): "een soort site audit, automatisch, met een metric in groen,
oranje, rood en als je klikt een uitleg." Scope 45 = de samenstelling en het scherm voor de checks
die er al zijn (site_health, mobiel_audit, claims). Alles offline: skills geïnjecteerd.
"""
from __future__ import annotations

import types

from nooch_village import cockpit2, site_audit
from nooch_village.skills import Skill, SkillRegistry
from nooch_village.views.site_audit import render_site_audit

ROL = "mother_earth__nooch__website_developer"


class _Health(Skill):
    name = "site_health"
    cost = "free"

    def __init__(self, code=200, exc=None):
        self.code, self.exc = code, exc

    def run(self, payload, context):
        if self.exc:
            raise self.exc
        return {"url": payload["url"], "status_code": self.code, "ok": self.code == 200,
                "title": "Nooch", "bytes": 120_000}


class _Mobiel(Skill):
    name = "mobiel_audit"
    cost = "rate_limited"

    def __init__(self, uit=None):
        self.uit = uit

    def run(self, payload, context):
        return self.uit


def _lighthouse(perf=57, lcp=21200, cls=0.019, tbt=340, **extra):
    return {"ok": True, "url": "https://nooch.earth/", "strategie": "mobile",
            "scores": {"performance": perf, "accessibility": 86, "best_practices": 54, "seo": 92},
            "lab": {"lcp_ms": {"waarde": lcp, "weergave": f"{lcp / 1000:.1f} s"},
                    "cls": {"waarde": cls, "weergave": str(cls)},
                    "tbt_ms": {"waarde": tbt, "weergave": f"{tbt} ms"}},
            "veld": {"bron": None, "reden": "geen velddata"},
            "kansen": [{"audit": "image-delivery-insight", "titel": "Improve image delivery",
                        "winst_ms": 0, "winst_bytes": 2_256_896}],
            "bevindingen": [
                {"categorie": "performance", "audit": "lcp-discovery-insight", "titel": "LCP request discovery",
                 "score": 0.0, "weergave": "", "gewicht": 0},
                {"categorie": "best_practices", "audit": "third-party-cookies", "titel": "Uses third-party cookies",
                 "score": 0.0, "weergave": "5 cookies found", "gewicht": 5},
                {"categorie": "seo", "audit": "image-alt", "titel": "Image elements do not have [alt] attributes",
                 "score": 0.0, "weergave": "", "gewicht": 1}],
            "lcp_element": {"element": "Nooch 269 in het gras", "selector": "div.hero > img",
                            "fases_ms": {"TTFB": 400, "Load Delay": 15200, "Load Time": 3900, "Render Delay": 800},
                            "aanwijzingen": ["de LCP-afbeelding staat op loading=lazy (de browser stelt hem uit)"]},
            "mobiel": [], "waarschuwingen": [], "lighthouse_versie": "13.4.1", **extra}


def _reg(health=None, mobiel=None):
    reg = SkillRegistry()
    reg.register(health or _Health())
    reg.register(mobiel or _Mobiel(_lighthouse()))
    return reg


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _ctx(dd):
    return types.SimpleNamespace(settings={"PAGESPEED_API_KEY": "k"}, data_dir=dd)


# ── drempels ─────────────────────────────────────────────────────────────────

def test_drempels_zijn_googles_banden():
    assert site_audit.lamp_score(90) == "groen" and site_audit.lamp_score(89) == "oranje"
    assert site_audit.lamp_score(50) == "oranje" and site_audit.lamp_score(49) == "rood"
    assert site_audit.lamp_score(None) == "grijs"
    assert site_audit.lamp_lcp(2500) == "groen" and site_audit.lamp_lcp(2501) == "oranje"
    assert site_audit.lamp_lcp(4000) == "oranje" and site_audit.lamp_lcp(4001) == "rood"
    assert site_audit.lamp_cls(0.1) == "groen" and site_audit.lamp_cls(0.25) == "oranje" and site_audit.lamp_cls(0.3) == "rood"
    assert site_audit.lamp_tbt(200) == "groen" and site_audit.lamp_tbt(600) == "oranje" and site_audit.lamp_tbt(601) == "rood"
    assert site_audit._ergste(["groen", "oranje", "grijs"]) == "oranje"
    assert site_audit._ergste([]) == "grijs"


# ── de run ───────────────────────────────────────────────────────────────────

def test_run_geeft_zes_lampjes_met_uitleg_en_eigenaar(tmp_path):
    dd, st = _st(tmp_path)
    snap = site_audit.draai(st, _ctx(dd), _reg())
    per = {l["sleutel"]: l for l in snap["lampjes"]}
    assert list(per) == ["bereikbaar", "snelheid", "toegankelijkheid", "best_practices", "seo", "claims"]
    assert per["bereikbaar"]["kleur"] == "groen" and "HTTP 200" in per["bereikbaar"]["uitleg"]
    assert per["snelheid"]["kleur"] == "oranje" and per["snelheid"]["waarde"] == "57"
    assert "LCP 21.2 s (rood" in per["snelheid"]["uitleg"] and "CLS 0.019 (groen" in per["snelheid"]["uitleg"]
    assert "LCP-element: Nooch 269 in het gras, meeste tijd in Load Delay (75%)." in per["snelheid"]["uitleg"]
    # de checklist van Lighthouse 13 wordt een bevinding: dat is het repo-werk, niet de score
    assert "LCP-afbeelding: de LCP-afbeelding staat op loading=lazy (de browser stelt hem uit)" in per["snelheid"]["bevindingen"]
    assert "Geen velddata" in per["snelheid"]["uitleg"]
    # het bruikbaarste vooraan: de LCP-checklist, dan de kansen met winst, dan de falende audits
    assert per["snelheid"]["bevindingen"][:2] == ["LCP-afbeelding: de LCP-afbeelding staat op loading=lazy (de browser stelt hem uit)",
                                                  "Kans: Improve image delivery (2204 KiB)"]
    assert "LCP request discovery" in per["snelheid"]["bevindingen"]
    assert per["best_practices"]["kleur"] == "oranje" and per["best_practices"]["bevindingen"] == ["Uses third-party cookies (5 cookies found)"]
    assert per["seo"]["kleur"] == "groen" and per["seo"]["bevindingen"] == ["Image elements do not have [alt] attributes"]
    assert per["snelheid"]["eigenaar"] == ROL and per["snelheid"]["bron"] == "mobiel_audit"
    # claims: de seed-werklijst staat helemaal open, 11 rood → rood, eigenaar = de houder van het domein
    assert per["claims"]["kleur"] == "rood" and per["claims"]["waarde"] == "11/9"
    assert per["claims"]["eigenaar"] == "mother_earth__nooch__compliance"
    assert "20 claims op de werklijst: 11 rood en 9 oranje nog niet live, 0 live" in per["claims"]["uitleg"]
    assert "2024/825" in per["claims"]["uitleg"] and "nog niet gedraaid" in per["claims"]["uitleg"]
    assert len(per["claims"]["bevindingen"]) == site_audit.MAX_BEVINDINGEN, "begrensd, de werklijst zelf staat op /claims"
    assert snap["totaal"] == "rood" and snap["url"] == "https://nooch.earth/" and "duur_s" in snap


def test_claims_lampje_volgt_de_werklijst_van_compliance(tmp_path):
    from nooch_village import claims_db
    dd, st = _st(tmp_path)
    for nr in range(1, 21):
        claims_db.overlay_set_status(dd, nr, "live")
    per = {l["sleutel"]: l for l in site_audit.draai(st, _ctx(dd), _reg())["lampjes"]}
    assert per["claims"]["kleur"] == "groen" and per["claims"]["bevindingen"] == []
    claims_db.overlay_set_status(dd, 2, "in behandeling")       # item 2 is oranje in de seed
    per = {l["sleutel"]: l for l in site_audit.draai(st, _ctx(dd), _reg())["lampjes"]}
    assert per["claims"]["kleur"] == "oranje" and per["claims"]["waarde"] == "0/1", per["claims"]
    assert per["claims"]["bevindingen"] == ["🟠 “100% Plant-Based” — sitewide tagline [in behandeling]"]
    claims_db.overlay_set_status(dd, 12, "open")                # item 12 is rood in de seed
    per = {l["sleutel"]: l for l in site_audit.draai(st, _ctx(dd), _reg())["lampjes"]}
    assert per["claims"]["kleur"] == "rood" and per["claims"]["waarde"] == "1/1", per["claims"]


def test_een_check_die_faalt_wordt_grijs_met_reden_en_de_rest_gaat_door(tmp_path):
    dd, st = _st(tmp_path)
    reg = _reg(health=_Health(exc=ConnectionError("dns")),
               mobiel=_Mobiel({"error": "geen PAGESPEED_API_KEY in .env", "tijdelijk": False}))
    snap = site_audit.draai(st, _ctx(dd), reg)
    per = {l["sleutel"]: l for l in snap["lampjes"]}
    assert per["bereikbaar"]["kleur"] == "rood" and "ConnectionError" in per["bereikbaar"]["uitleg"]
    for s in ("snelheid", "toegankelijkheid", "best_practices", "seo"):
        assert per[s]["kleur"] == "grijs" and "PAGESPEED_API_KEY" in per[s]["uitleg"]
    assert per["claims"]["kleur"] == "rood"
    assert snap["totaal"] == "rood", "grijs telt niet mee; rood wel"
    # zonder registry: alles grijs behalve claims, en geen exception
    snap2 = site_audit.draai(st, _ctx(dd), None)
    assert all(l["kleur"] == "grijs" for l in snap2["lampjes"] if l["sleutel"] != "claims")


def test_bereikbaar_kleuren():
    for code, kleur in ((200, "groen"), (301, "oranje"), (404, "oranje"), (503, "rood"), (0, "rood")):
        lamp = site_audit._check_bereikbaar(_reg(health=_Health(code=code)), None, "https://x/", ROL)[0]
        assert lamp["kleur"] == kleur, (code, lamp)


# ── de snapshot en het verschil ──────────────────────────────────────────────

def test_run_en_bewaar_is_append_only_en_meldt_wissels(tmp_path):
    dd, st = _st(tmp_path)
    snap1, w1 = site_audit.run_en_bewaar(st, _ctx(dd), _reg())
    assert w1 == []
    snap2, w2 = site_audit.run_en_bewaar(st, _ctx(dd), _reg(mobiel=_Mobiel(_lighthouse(perf=92))))
    assert w2 == [{"sleutel": "snelheid", "naam": "Snelheid (mobiel)", "was": "oranje", "nu": "groen"}]
    staat = site_audit.SiteAuditStaat(site_audit.pad_voor(dd))
    assert len(staat.alles()) == 2 and staat.laatste()["wissels"] == w2
    # een grijze run telt niet als wissel: niet gemeten is geen verandering
    _, w3 = site_audit.run_en_bewaar(st, _ctx(dd), _reg(mobiel=_Mobiel({"error": "quota"})))
    assert w3 == []
    _, w4 = site_audit.run_en_bewaar(st, _ctx(dd), _reg(mobiel=_Mobiel(_lighthouse(perf=40))))
    assert w4 == [], "van grijs naar rood is geen wissel; de vorige run was niet gemeten"


def test_verschil_los():
    a = {"lampjes": [{"sleutel": "x", "naam": "X", "kleur": "groen"}]}
    b = {"lampjes": [{"sleutel": "x", "naam": "X", "kleur": "rood"}, {"sleutel": "y", "naam": "Y", "kleur": "groen"}]}
    assert site_audit.verschil(a, b) == [{"sleutel": "x", "naam": "X", "was": "groen", "nu": "rood"}]
    assert site_audit.verschil(None, b) == []


# ── het scherm ───────────────────────────────────────────────────────────────

def test_scherm_leeg_en_gevuld(tmp_path):
    dd, st = _st(tmp_path)
    html = render_site_audit(st)
    assert "Nog geen run" in html and "village site_audit" in html
    site_audit.run_en_bewaar(st, _ctx(dd), _reg())
    site_audit.run_en_bewaar(st, _ctx(dd), _reg(mobiel=_Mobiel(_lighthouse(perf=92))))
    html = render_site_audit(cockpit2._Stores(dd))
    assert "chip green" in html and "chip amber" in html and "chip coral" in html
    assert "Gewisseld sinds de vorige run" in html and "Snelheid (mobiel)" in html
    assert "LCP-element: Nooch 269 in het gras" in html
    assert "Verloop" in html
    assert "eigenaar: <code>Website Developer</code>" in html or "eigenaar: <code>" in html
    assert "style=" not in html, "geen inline styles (designsysteem)"


def test_tool_kaart_op_de_website_developer():
    from nooch_village.views.overview import _ROLE_TOOLS
    from nooch_village.cockpit2_util import WEBSITE_DEVELOPER_ROLE
    assert any(href == "/site-audit" for _, _, href in _ROLE_TOOLS[WEBSITE_DEVELOPER_ROLE])


def test_route_bestaat(tmp_path):
    """De cockpit kent /site-audit; een GET zonder sessie gaat naar /login zoals alles."""
    import re
    src = open("nooch_village/cockpit2.py", encoding="utf-8").read()
    assert re.search(r'path == "/site-audit"', src) and "render_site_audit" in src


# ── dev op afroep: eigen reeks, eigen URL, nooit door elkaar met live ─────────

def test_dev_is_een_eigen_reeks_en_wisselt_nooit_tegen_live(tmp_path):
    """Stefan, 11 sep: "dev op afroep, maak dat." Een dev-run naast een live-run zou een valse
    'gewisseld' geven; daarom twee bestanden, en `verschil` vergelijkt alleen binnen een doel."""
    import types
    dd, st = _st(tmp_path)
    ctx = types.SimpleNamespace(settings={"PAGESPEED_API_KEY": "k",
                                          "mobiel_audit_dev_url": "https://nooch.earth/?preview_theme_id=42"}, data_dir=dd)
    live, _ = site_audit.run_en_bewaar(st, ctx, _reg(mobiel=_Mobiel(_lighthouse(perf=57))))
    dev, wissels = site_audit.run_en_bewaar(st, ctx, _reg(mobiel=_Mobiel(_lighthouse(perf=92))), doel="dev")
    assert live["doel"] == "live" and live["url"] == "https://nooch.earth/"
    assert dev["doel"] == "dev" and dev["url"] == "https://nooch.earth/?preview_theme_id=42"
    assert wissels == [], "de eerste dev-run heeft geen vorige dev-run; live telt niet als vorige"
    assert site_audit.SiteAuditStaat(site_audit.pad_voor(dd, "live")).alles()[-1]["lampjes"][1]["waarde"] == "57"
    assert site_audit.SiteAuditStaat(site_audit.pad_voor(dd, "dev")).alles()[-1]["lampjes"][1]["waarde"] == "92"
    assert site_audit.pad_voor(dd, "dev").endswith("site_audit_dev.jsonl") and site_audit.pad_voor(dd).endswith("site_audit.jsonl")
    # tweede dev-run: nu wél een wissel, binnen dev
    _, wissels = site_audit.run_en_bewaar(st, ctx, _reg(mobiel=_Mobiel(_lighthouse(perf=40))), doel="dev")
    assert [(w["sleutel"], w["was"], w["nu"]) for w in wissels] == [("snelheid", "groen", "rood")]


def test_dev_zonder_url_meet_niets_en_zegt_wat_er_mist(tmp_path):
    import pytest
    dd, st = _st(tmp_path)
    with pytest.raises(site_audit.GeenDevUrl, match="mobiel_audit_dev_url"):
        site_audit.draai(st, _ctx(dd), _reg(), doel="dev")
    assert not __import__("os").path.exists(site_audit.pad_voor(dd, "dev"))
    with pytest.raises(ValueError):
        site_audit.draai(st, _ctx(dd), _reg(), doel="staging")


def test_preview_die_niet_herkend_is_staat_op_alle_vier_de_lampjes(tmp_path):
    """Een preview-URL waarvan de skill het preview-thema niet terugzag: dan is mogelijk live
    gemeten, en dat hoort op de lampjes, niet in een log."""
    dd, st = _st(tmp_path)
    uit = _lighthouse(perf=92, preview={"gevraagd": True, "herkend": False})
    per = {l["sleutel"]: l for l in site_audit.draai(st, _ctx(dd), _reg(mobiel=_Mobiel(uit)))["lampjes"]}
    for k in ("snelheid", "toegankelijkheid", "best_practices", "seo"):
        assert "preview-thema niet herkend" in per[k]["uitleg"], k
    uit = _lighthouse(perf=92, preview={"gevraagd": True, "herkend": True})
    per = {l["sleutel"]: l for l in site_audit.draai(st, _ctx(dd), _reg(mobiel=_Mobiel(uit)))["lampjes"]}
    assert "preview-thema" not in per["snelheid"]["uitleg"]


def test_scherm_toont_live_en_dev_als_twee_reeksen(tmp_path):
    import types
    dd, st = _st(tmp_path)
    html = render_site_audit(st, doel="dev")
    assert "site_audit --dev" in html and "mobiel_audit_dev_url" in html and "class='seg'" in html
    assert "href='/site-audit'" in html and "href='/site-audit?doel=dev'" in html
    ctx = types.SimpleNamespace(settings={"PAGESPEED_API_KEY": "k",
                                          "mobiel_audit_dev_url": "https://nooch.earth/?preview_theme_id=42"}, data_dir=dd)
    site_audit.run_en_bewaar(st, ctx, _reg(mobiel=_Mobiel(_lighthouse(perf=92))), doel="dev")
    st = cockpit2._Stores(dd)
    dev = render_site_audit(st, doel="dev")
    assert "preview_theme_id=42" in dev and "preview-balk" in dev and "class='on' href='/site-audit?doel=dev'" in dev
    assert "Nog geen run" in render_site_audit(st), "live blijft leeg: de dev-run hoort daar niet"
    assert "Nog geen run" in render_site_audit(st, doel="onzin"), "onbekend doel valt terug op live"
    assert "style=" not in dev
