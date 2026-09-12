"""Scope 51a (12 september 2026) — de stap die een mens ná het zoeken doet, als gereedschap.

Stefan: "waarom kan AI niet zelf een site via Google opzoeken en bekijken?" Wat hieronder vastligt:

1. zonder url zoekt de skill de naam op en kiest de eerste treffer die geen verzamelsite is; welke
   het werd staat in de uitkomst;
2. hij leest de pagina en beoordeelt met één modelronde: wat is dit, per criterium ja/nee/onbekend
   met citaat, oordeel, volgende stap;
3. GEEN JA OF NEE ZONDER CITAAT: een verdict zonder letterlijke zin wordt 'unknown', geteld;
4. fail-closed: geen site, onleesbare pagina of onzin van het model is een fout, geen antwoord;
5. een placeholder-url wordt bij het plannen al geweigerd; de skill staat in de registry, de rugzak
   en de labels.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from nooch_village import safe_fetch
from nooch_village.skills_impl import lead_beoordeling as lb
from nooch_village.skills_impl.lead_beoordeling import LeadBeoordelingSkill, kies_site

CTX = SimpleNamespace(settings={"SERPAPI_API_KEY": "k"})
PAGINA = ("Die Schuhe sind rahmengenäht. Dadurch entsteht eine dauerhafte Verbindung zwischen "
          "Obermaterial und Sohle. Die Sohle besteht aus Eco-Rubber, einer Naturkautschukmischung. "
          "Produziert in Portugal. ") * 4


class _Zoek:
    """Een nep-web_zoek: dezelfde `run`-vorm, geen netwerk."""
    def __init__(self, treffers, error=None):
        self.treffers, self.error, self.gezien = treffers, error, []

    def run(self, payload, context=None):
        self.gezien.append(payload)
        if self.error:
            return {"error": self.error}
        return {"ok": True, "bron": "serpapi", "treffers": self.treffers}


def _model(antwoord):
    def _f(prompt, **k):
        _f.prompt, _f.kwargs = prompt, k
        return json.dumps(antwoord) if isinstance(antwoord, dict) else antwoord
    return _f


GOED = {"what_is_this": "German plastic-free barefoot shoe brand, made in Portugal (brand)",
        "criteria": [{"criterion": "plastic-free", "verdict": "yes",
                      "quote": "Die Sohle besteht aus Eco-Rubber, einer Naturkautschukmischung."},
                     {"criterion": "vegan", "verdict": "yes", "quote": ""},
                     {"criterion": "proven in footwear", "verdict": "yes",
                      "quote": "Die Schuhe sind rahmengenäht."}],
        "fit": "high", "why": "Stitched construction on natural rubber, no glue.",
        "next_step": "contact", "quote": "Die Schuhe sind rahmengenäht."}


def _skill(treffers=None, antwoord=GOED, haal=None, zoek_error=None):
    zoek = _Zoek(treffers if treffers is not None else
                 [{"titel": "nahtur-design", "url": "https://nahtur-design.de/", "domein": "nahtur-design.de"}],
                 error=zoek_error)
    s = LeadBeoordelingSkill(zoek=zoek, haal=haal or (lambda url: {"url": url, "titel": "nahtur", "tekst": PAGINA}),
                             reason_fn=_model(antwoord))
    s._test_zoek = zoek
    return s


# ── 1: opzoeken op de naam ───────────────────────────────────────────────────

def test_zonder_url_zoekt_hij_de_naam_op_en_zegt_hoe():
    s = _skill()
    uit = s.run({"naam": "nahtur-design", "vraag": "glue-free joining", "criteria": ["plastic-free"]}, CTX)
    assert uit["ok"] is True and uit["url"] == "https://nahtur-design.de/"
    assert uit["gevonden_via"] == "zoek:serpapi" and uit["site_onzeker"] is False
    assert s._test_zoek.gezien[0]["term"] == "nahtur-design" and s._test_zoek.gezien[0]["lees"] == 0


def test_kies_site_slaat_verzamelsites_over():
    treffers = [{"url": "https://en.wikipedia.org/wiki/Kiilto", "domein": "en.wikipedia.org"},
                {"url": "https://www.linkedin.com/company/kiilto", "domein": "linkedin.com"},
                {"url": "https://www.kiilto.com/industry/", "domein": "kiilto.com"}]
    assert kies_site(treffers) == ("https://www.kiilto.com/industry/", False)
    assert kies_site(treffers[:2]) == ("https://en.wikipedia.org/wiki/Kiilto", True)   # tóch, maar onzeker
    assert kies_site([]) == ("", False)


def test_alleen_verzamelsites_markeert_de_site_als_onzeker():
    s = _skill(treffers=[{"url": "https://www.linkedin.com/company/x", "domein": "linkedin.com"}])
    uit = s.run({"naam": "x"}, CTX)
    assert uit["ok"] is True and uit["site_onzeker"] is True and "site uncertain" in uit["text"]


def test_met_url_wordt_niet_gezocht():
    s = _skill()
    uit = s.run({"naam": "nahtur-design", "url": "https://nahtur-design.de/products/x"}, CTX)
    assert uit["gevonden_via"] == "url" and s._test_zoek.gezien == []


# ── 2: lezen en beoordelen ───────────────────────────────────────────────────

def test_beoordeling_bevat_wat_is_dit_criteria_en_oordeel():
    s = _skill()
    uit = s.run({"naam": "nahtur-design", "vraag": "glue-free joining", "opdracht": "plastic-free and vegan",
                 "criteria": ["plastic-free", "vegan", "proven in footwear"]}, CTX)
    assert uit["oordeel"] == "high" and uit["volgende_stap"] == "contact"
    assert uit["wat_is_dit"].startswith("German plastic-free")
    rijen = uit["beoordeling"]
    assert rijen[0] == {"criterium": "what is this", "oordeel": uit["wat_is_dit"], "citaat": ""}
    assert rijen[1] == {"criterium": "plastic-free", "oordeel": "yes",
                        "citaat": "Die Sohle besteht aus Eco-Rubber, einer Naturkautschukmischung."}
    assert rijen[-1]["criterium"] == "fit" and rijen[-1]["oordeel"].startswith("high — Stitched")
    assert rijen[-1]["volgende_stap"] == "contact"
    p = s._reason.prompt
    assert "QUESTION: glue-free joining" in p and "ASSIGNMENT: plastic-free and vegan" in p
    assert "plastic-free; vegan; proven in footwear" in p and "Die Schuhe sind rahmengenäht" in p
    assert "a 'yes' or 'no' needs a verbatim sentence" in p
    assert s._reason.kwargs["call_site"] == "skill_lead_beoordeling"


def test_de_wall_tekst_leest_als_een_oordeel_met_citaten():
    uit = _skill().run({"naam": "nahtur-design", "criteria": ["plastic-free"]}, CTX)
    t = uit["text"]
    assert t.startswith("Assessed nahtur-design (https://nahtur-design.de/, found via zoek:serpapi): high fit")
    assert "• plastic-free: yes — “Die Sohle besteht aus Eco-Rubber" in t
    assert "Next: contact." in t


# ── 3: geen ja of nee zonder citaat ──────────────────────────────────────────

def test_een_verdict_zonder_citaat_wordt_onbekend_en_geteld():
    uit = _skill().run({"naam": "x", "criteria": ["plastic-free", "vegan"]}, CTX)
    vegan = next(r for r in uit["beoordeling"] if r["criterium"] == "vegan")
    assert vegan["oordeel"] == "unknown" and vegan["citaat"] == ""
    assert uit["zonder_citaat_teruggezet"] == 1
    assert "1 verdict(s) had no quote" in uit["text"]


def test_een_criterium_dat_het_model_oversloeg_staat_er_als_onbekend():
    uit = _skill().run({"naam": "x", "criteria": ["plastic-free", "available in the EU"]}, CTX)
    eu = next(r for r in uit["beoordeling"] if r["criterium"] == "available in the EU")
    assert eu == {"criterium": "available in the EU", "oordeel": "unknown", "citaat": ""}


def test_onbekende_waarden_vallen_terug_op_veilige_defaults():
    antwoord = {**GOED, "fit": "excellent", "next_step": "buy now",
                "criteria": [{"criterion": "x", "verdict": "maybe", "quote": "q"}]}
    uit = _skill(antwoord=antwoord).run({"naam": "x"}, CTX)
    assert uit["oordeel"] == "low" and uit["volgende_stap"] == "discard"
    assert next(r for r in uit["beoordeling"] if r["criterium"] == "x")["oordeel"] == "unknown"


# ── 4: fail-closed ───────────────────────────────────────────────────────────

def test_geen_site_gevonden_is_een_fout_geen_antwoord():
    uit = _skill(treffers=[]).run({"naam": "iets onvindbaars"}, CTX)
    assert "error" in uit and "geen site gevonden" in uit["error"] and "no_data" not in uit
    uit2 = _skill(zoek_error="geen zoeksleutel").run({"naam": "x"}, CTX)
    assert "geen zoeksleutel" in uit2["error"]


def test_onleesbare_pagina_is_een_fout():
    def _kapot(url):
        raise safe_fetch.FetchMislukt("HTTP 403")
    uit = _skill(haal=_kapot).run({"naam": "x", "url": "https://x.example/"}, CTX)
    assert "site niet leesbaar" in uit["error"] and uit["url"] == "https://x.example/"
    uit2 = _skill(haal=lambda url: {"url": url, "tekst": ""}).run({"naam": "x", "url": "https://x.example/"}, CTX)
    assert "geen leesbare tekst" in uit2["error"]


def test_onzin_van_het_model_is_een_fout():
    uit = _skill(antwoord="dit is geen json").run({"naam": "x", "url": "https://x.example/"}, CTX)
    assert "geen oordeel" in uit["error"]

    def _stuk(prompt, **k):
        raise RuntimeError("geen krediet")
    s = LeadBeoordelingSkill(zoek=_Zoek([]), haal=lambda url: {"url": url, "tekst": PAGINA}, reason_fn=_stuk)
    assert "geen oordeel" in s.run({"naam": "x", "url": "https://x.example/"}, CTX)["error"]


def test_zonder_naam_en_url_is_het_een_fout():
    assert "verplicht" in _skill().run({}, CTX)["error"]


# ── 5: de poort bij het plannen, en de registratie ───────────────────────────

def test_placeholder_url_wordt_bij_het_plannen_geweigerd():
    s = LeadBeoordelingSkill()
    assert s.validate_payload({"naam": "x", "url": "PLACEHOLDER — url from an earlier step"}, None)
    assert s.validate_payload({"naam": "x", "url": ""}, None) == []
    assert s.validate_payload({"naam": "x", "url": "https://x.example/"}, None) == []
    from nooch_village.skills import ontbrekende_velden
    assert ontbrekende_velden(s.required_payload, {}) == ["naam|url"]
    assert ontbrekende_velden(s.required_payload, {"naam": "x"}) == []


def test_geregistreerd_in_rugzak_en_labels():
    from nooch_village.registry_factory import build_skill_registry
    from nooch_village import rugzak, skill_labels
    import pathlib, json as _json
    reg = build_skill_registry()
    assert reg.get("lead_beoordeling") is not None and reg.get("lead_beoordeling").cost == "credits"
    zakken = _json.loads(pathlib.Path("config/rugzakken.json").read_text(encoding="utf-8"))
    assert "lead_beoordeling" in zakken["buiten"]["skills"]
    assert skill_labels.label("lead_beoordeling").startswith("Looks up")
    assert skill_labels.match_label("lead_beoordeling").startswith("Zoekt")
    assert lb.FIT == ("high", "medium", "low")
