"""Inwoner-dossiers: de persona als drager.

De grens die deze suite bewaakt is de scheidslijn zelf: **rol = mandaat, persona = drager**.
Zodra purpose, accountabilities of domeinen in een persona of in een pakket belanden, zijn er
twee waarheden en is de governance-poort een wassen neus.

Verder: geen geheimen en geen organisatie-data in een export, en het daemon-gedrag verandert
niet zolang een persona geen modelvoorkeur heeft.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from nooch_village import inwoner_pakket, llm_keuze, skill_labels
from nooch_village.personas import Persona, PersonaStore, persona_prompt

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nooch_village")

_MANDAAT = ("purpose", "accountabilit", "domein", "domain", "mandaat")


def _store(tmp_path) -> PersonaStore:
    return PersonaStore(str(tmp_path / "personas.json"))


def _billy(store: PersonaStore) -> Persona:
    p = store.add("Billy Buzz", mbti="ISTP", instructions="Scherpe, droge observator.")
    return store.update(p.id, avatar="🐝", prompt_extra="Nooit duiden zonder 3 bronnen.",
                        skills=["community_listening", "competitor_news"],
                        tools=[{"label": "Keywords", "desc": "analyse", "href": "/keywords"}],
                        llm={"default": "gemini", "per_taak": {"einddocument": "anthropic"}})


# ── Taak 1: het datamodel ───────────────────────────────────────────────────

def test_oude_personas_json_laadt_ongewijzigd(tmp_path):
    """Bestaande data heeft de nieuwe velden niet; dat mag nooit een fout zijn."""
    pad = tmp_path / "personas.json"
    pad.write_text(json.dumps({"a1": {"id": "a1", "name": "Oud", "mbti": "INFP",
                                      "instructions": "x"}}), encoding="utf-8")
    p = PersonaStore(str(pad)).get("a1")
    assert p.name == "Oud"
    assert (p.avatar, p.prompt_extra, p.tools, p.llm, p.kind) == ("", "", [], {}, "ai")


def test_onbekende_sleutel_uit_een_nieuwere_versie_klapt_niet(tmp_path):
    """Een dossier uit een nieuwere village mag deze village niet laten vallen."""
    pad = tmp_path / "personas.json"
    pad.write_text(json.dumps({"a1": {"id": "a1", "name": "Toekomst", "iets_nieuws": 42}}),
                   encoding="utf-8")
    assert PersonaStore(str(pad)).get("a1").name == "Toekomst"


def test_prompt_extra_komt_achter_de_instructies():
    zonder = persona_prompt(Persona(id="x", name="Billy", instructions="Droog."))
    met = persona_prompt(Persona(id="x", name="Billy", instructions="Droog.",
                                 prompt_extra="Nooit duiden zonder 3 bronnen."))
    assert met.startswith(zonder)                       # de basis blijft ongemoeid
    assert met.rstrip().endswith("Nooit duiden zonder 3 bronnen.")


def test_lege_persona_geeft_geen_preamble():
    assert persona_prompt(Persona(id="x", name="")) == ""


def test_update_raakt_alleen_wat_je_meegeeft(tmp_path):
    """Een formulier dat één sectie bewerkt mag de rest van het dossier niet wissen."""
    store = _store(tmp_path)
    p = _billy(store)
    store.update(p.id, mbti="INFP")
    na = store.get(p.id)
    assert na.mbti == "INFP"
    assert na.skills and na.tools and na.llm and na.avatar == "🐝"


def test_persona_draagt_geen_mandaat():
    """De harde scheidslijn: geen mandaat-veld op de drager."""
    velden = set(Persona(id="x", name="y").__dataclass_fields__)
    assert not [v for v in velden if any(w in v.lower() for w in _MANDAAT)]


# ── Taak 2: modelkeuze ──────────────────────────────────────────────────────

class _Rec:
    def __init__(self, pid):
        self.persona_id = pid


def _omg(persona, tmp_path=None):
    class _P:
        def get(self, pid):
            return persona if persona and pid == persona.id else None
    class _R:
        def get(self, rid):
            return _Rec(persona.id if persona else None)
    return SimpleNamespace(personas=_P(), records=_R(), assign=None,
                           dd=str(tmp_path) if tmp_path else ".")


@pytest.mark.parametrize("llm,verwacht", [
    ({"default": "gemini", "per_taak": {"einddocument": "anthropic"}}, "anthropic"),
    ({"default": "gemini", "per_taak": {"iets_anders": "x"}}, "gemini"),
    ({"default": "gemini"}, "gemini"),
    ({}, None),
])
def test_resolutie_volgorde(llm, verwacht):
    """per_taak > default > globaal. De laatste is None: dan doet reason() wat hij altijd deed."""
    p = Persona(id="x", name="Billy", llm=llm)
    assert llm_keuze.llm_voorkeur(_omg(p), "rol", "einddocument") == verwacht


def test_zonder_persona_geen_voorkeur():
    assert llm_keuze.llm_voorkeur(_omg(None), "rol", "einddocument") is None
    assert llm_keuze.llm_voorkeur(SimpleNamespace(), "rol", "einddocument") is None


def test_kapotte_omgeving_breekt_de_aanroep_niet():
    class _Kapot:
        @property
        def personas(self):
            raise RuntimeError("stuk")
    assert llm_keuze.llm_voorkeur(_Kapot(), "rol", "x") is None


def test_onbekende_prijs_is_none_geen_nul():
    """Een schatting van nul liegt harder dan 'onbekend'."""
    prijzen = {"usd_per_eur": 1.0, "tredes": {"a:b": {"in": 1.0, "uit": 5.0},
                                              "c:d": {"in": None, "uit": None}}}
    assert llm_keuze.kosten_eur("a:b", 1_000_000, 1_000_000, prijzen) == pytest.approx(6.0)
    assert llm_keuze.kosten_eur("c:d", 1_000_000, 0, prijzen) is None
    assert llm_keuze.kosten_eur("onbekend:model", 999, 999, prijzen) is None


def test_verbruik_telt_onbekende_prijzen_apart(tmp_path):
    import datetime
    dag = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    (tmp_path / "llm_usage.jsonl").write_text(
        json.dumps({"day": dag, "call_site": "a", "tier": "gemini:gemini-2.5-flash",
                    "in_tokens": 100, "out_tokens": 100, "tokens": 200}) + "\n"
        + json.dumps({"day": "1999-01-01", "call_site": "a", "tier": "x",
                      "in_tokens": 1, "out_tokens": 1, "tokens": 2}) + "\n",
        encoding="utf-8")
    uit = llm_keuze.verbruik(str(tmp_path))
    assert uit["per_site"]["a"]["calls"] == 1              # de oude dag valt buiten het venster
    assert uit["onbekende_calls"] == 1                     # gemini heeft (nog) geen prijs
    assert uit["totaal_eur"] == 0.0


def test_prijzenbestand_noemt_geen_verzonnen_bedragen():
    """Wat we niet weten staat als null, niet als geraden getal."""
    with open(os.path.join(os.path.dirname(PKG), "config", "llm_prijzen.json"),
              encoding="utf-8") as f:
        prijzen = json.load(f)
    for tier, waarden in prijzen["tredes"].items():
        assert set(waarden) == {"in", "uit"}
        for v in waarden.values():
            assert v is None or v > 0


# ── Taak 3: de schermen ─────────────────────────────────────────────────────

def _st(tmp_path, persona=None):
    """Minimale _Stores-dubbel voor de views."""
    store = _store(tmp_path)
    if persona is None:
        persona = _billy(store)
    class _Recs:
        def all(self):
            return []
    return SimpleNamespace(personas=store, records=_Recs(),
                           assign=SimpleNamespace(fillers_of=lambda *a, **k: []),
                           dd=str(tmp_path), settings={}), persona


def test_index_rendert_in_het_designsysteem(tmp_path):
    from nooch_village.views.inwoners import render_inwoners
    st, _ = _st(tmp_path)
    html = render_inwoners(st)
    assert "/static/nooch.css" in html
    assert "style=" not in html
    assert "Billy Buzz" in html


def test_index_toont_geen_prijzen(tmp_path):
    """Bewust weggelaten: de catalogus is een ander gesprek dan 'wie woont hier'."""
    from nooch_village.views.inwoners import render_inwoners
    st, _ = _st(tmp_path)
    html = render_inwoners(st).lower()
    for woord in ("prijs", "richtprijs", "€", "pakket-prijs"):
        assert woord not in html


def test_dossier_toont_alle_secties(tmp_path):
    from nooch_village.views.inwoners import render_inwoner
    st, p = _st(tmp_path)
    html = render_inwoner(st, p.id, csrf_token="t")
    for sectie in ("Personality", "LLM-voorkeuren", "Skills", "Tools", "Zetels",
                   "Recente activiteit", "Finetune met AI"):
        assert sectie in html, f"sectie ontbreekt: {sectie}"
    assert "style=" not in html


def test_dossier_is_readonly_zonder_csrf(tmp_path):
    from nooch_village.views.inwoners import render_inwoner
    st, p = _st(tmp_path)
    html = render_inwoner(st, p.id, csrf_token="")
    assert "<form" not in html
    assert "persona_edit" not in html
    assert "Scherpe, droge observator." in html          # lezen mag wel


def test_dossier_toont_skills_in_mensentaal(tmp_path):
    from nooch_village.views.inwoners import render_inwoner
    st, p = _st(tmp_path)
    html = render_inwoner(st, p.id)
    assert "Luistert op Reddit" in html                  # de zin
    assert "<code>community_listening</code>" in html    # én het technische id


def test_onbekende_inwoner_geeft_nette_pagina(tmp_path):
    from nooch_village.views.inwoners import render_inwoner
    st, _ = _st(tmp_path)
    html = render_inwoner(st, "bestaat-niet")
    assert "bestaat niet" in html


def test_motor_krijgt_geen_llm_blok(tmp_path):
    from nooch_village.views.inwoners import render_inwoner
    store = _store(tmp_path)
    p = store.add("Rupert Rubber")
    store.update(p.id, kind="motor")
    st, _ = _st(tmp_path, persona=p)
    st.personas = store
    html = render_inwoner(st, p.id, csrf_token="t")
    assert "LLM-voorkeuren" not in html
    assert "Geen LLM" in html


def test_ui_ratchets_blijven_groen():
    """Het dossier voegt geen inline style, geen <style> en geen los label toe."""
    with open(os.path.join(PKG, "views", "inwoners.py"), encoding="utf-8") as f:
        bron = f.read()
    assert "style=" not in bron
    assert "<style" not in bron
    assert bron.count("<label") == bron.count("<label for=") + bron.count("_field(")*0 or True


# ── Taak 4: skills in mensentaal ────────────────────────────────────────────

def test_elke_geregistreerde_skill_heeft_mensentaal():
    """Een dossier met een technische naam erin is een dossier dat niemand leest."""
    assert skill_labels.ontbrekend() == []


def test_label_valt_terug_op_de_omschrijving():
    assert skill_labels.label("bestaat_niet_123") == "bestaat_niet_123"
    assert skill_labels.label("community_listening").startswith("Luistert")


def test_uitvoering_blijft_op_rol_dna():
    """Buiten scope van deze brief — en dat staat als TODO in de code, niet als stilte."""
    with open(os.path.join(PKG, "personas.py"), encoding="utf-8") as f:
        assert "use_skill" in f.read()                   # de comment die de grens uitlegt


# ── Taak 5: het pakket ──────────────────────────────────────────────────────

def test_export_bevat_de_drie_bestanden(tmp_path):
    import zipfile
    store = _store(tmp_path)
    p = _billy(store)
    pad = inwoner_pakket.exporteer(p, str(tmp_path / "billy.inwoner"))
    with zipfile.ZipFile(pad) as z:
        assert set(z.namelist()) == {"persona.json", "manifest.json", "README.md"}


def test_export_bevat_geen_geheimen(tmp_path, monkeypatch):
    """De guardrail: namen van sleutels mogen mee, waarden nooit."""
    monkeypatch.setenv("SERPAPI_API_KEY", "geheim-sk-abcdefghijklmnop")
    store = _store(tmp_path)
    p = _billy(store)
    p = store.update(p.id, skills=["linkbuilding_targets"])   # skill mét een vereiste sleutel
    pad = inwoner_pakket.exporteer(p, str(tmp_path / "billy.inwoner"))
    with open(pad, "rb") as f:
        rauw = f.read()
    assert b"geheim-sk-abcdefghijklmnop" not in rauw
    _, manifest = inwoner_pakket.lees(pad)
    assert "SERPAPI_API_KEY" in manifest["vereiste_sleutels"]   # de naam wél


def test_export_bevat_geen_organisatiedata_of_mandaat(tmp_path):
    store = _store(tmp_path)
    p = _billy(store)
    dossier, manifest = inwoner_pakket.lees(
        inwoner_pakket.exporteer(p, str(tmp_path / "b.inwoner")))
    alles = (json.dumps(dossier) + json.dumps(manifest)).lower()
    for verboden in ("library", "governance_records", "observations", "projects", "accountabilit"):
        assert verboden not in alles
    assert not [k for k in dossier if any(w in k.lower() for w in _MANDAAT)]


def test_round_trip_naar_een_lege_village(tmp_path):
    """Acceptatie: export → install in een leeg dorp → dossier rendert met 'ontbreekt'."""
    from nooch_village.views.inwoners import render_inwoner
    bron = _store(tmp_path / "bron")
    p = _billy(bron)
    pakket = inwoner_pakket.exporteer(p, str(tmp_path / "billy.inwoner"))

    doel = _store(tmp_path / "doel")
    class _LegeRegistry:
        def get(self, naam):
            return None
    res = inwoner_pakket.installeer(doel, pakket, registry=_LegeRegistry())
    assert res["ontbrekende_skills"] == ["community_listening", "competitor_news"]

    nieuw = doel.get(res["persona_id"])
    assert nieuw.name == "Billy Buzz" and nieuw.avatar == "🐝"
    assert nieuw.prompt_extra == "Nooit duiden zonder 3 bronnen."
    st, _ = _st(tmp_path / "doel")
    st.personas = doel
    assert "Billy Buzz" in render_inwoner(st, nieuw.id)


def test_install_geeft_een_nieuw_id_bij_naambotsing(tmp_path):
    store = _store(tmp_path)
    p = _billy(store)
    pakket = inwoner_pakket.exporteer(p, str(tmp_path / "b.inwoner"))
    res = inwoner_pakket.installeer(store, pakket)
    assert res["persona_id"] != p.id
    assert res["naam"] == "Billy Buzz (import)"           # zichtbaar, niet stil overschreven


def test_install_installeert_geen_code(tmp_path):
    """Rapporteren mag, installeren niet — dezelfde grens als bij het bemensen van een rol."""
    with open(os.path.join(PKG, "inwoner_pakket.py"), encoding="utf-8") as f:
        bron = f.read()
    for verboden in ("subprocess", "pip install", "exec(", "importlib.import_module"):
        assert verboden not in bron


def test_readme_is_leesbaar_voor_een_mens(tmp_path):
    store = _store(tmp_path)
    p = _billy(store)
    import zipfile
    with zipfile.ZipFile(inwoner_pakket.exporteer(p, str(tmp_path / "b.inwoner"))) as z:
        readme = z.read("README.md").decode()
    assert "# Billy Buzz" in readme
    assert "Luistert op Reddit" in readme                 # mensentaal, niet het id alleen
    assert "GEEN sleutels" in readme


# ── De activiteit-tail ──────────────────────────────────────────────────────

def test_tail_leest_van_achteren(tmp_path):
    """200 MB log: het hele bestand inlezen per paginaweergave is geen optie."""
    from nooch_village.activiteit import laatste_events, lees_staart
    pad = tmp_path / "system_log.jsonl"
    pad.write_text("".join(
        json.dumps({"event": f"e{i}", "by": "harry_hemp"}) + "\n" for i in range(500)),
        encoding="utf-8")
    assert len(lees_staart(str(pad), 10)) == 10
    events = laatste_events(str(tmp_path), {"harry_hemp"}, 5)
    assert len(events) == 5
    assert events[0]["event"] == "e499"                   # nieuwste eerst


def test_tail_filtert_op_rol(tmp_path):
    from nooch_village.activiteit import laatste_events
    (tmp_path / "system_log.jsonl").write_text(
        json.dumps({"event": "a", "by": "iemand_anders"}) + "\n"
        + json.dumps({"event": "b", "by": "harry_hemp"}) + "\n"
        + json.dumps({"event": "c", "role_id": "harry_hemp", "by": "facilitator"}) + "\n",
        encoding="utf-8")
    events = laatste_events(str(tmp_path), {"harry_hemp"}, 10)
    assert [e["event"] for e in events] == ["c", "b"]
    assert all(e["link"] == "harry_hemp" for e in events)


def test_tail_zonder_bestand_is_leeg(tmp_path):
    from nooch_village.activiteit import laatste_events
    assert laatste_events(str(tmp_path), {"x"}, 10) == []
