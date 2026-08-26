"""Waarde-audit — bewezen output, niet potentie.

Vier beloften:
  1. fail-closed: geen record van een uitkomst = interne beweging, ook als er veel gebeurde;
  2. alleen ECHTE uitkomsten tellen — 'niks nodig' en 'doorgestuurd' zijn dat niet;
  3. een onbekende modelprijs telt niet als nul maar wordt gevlagd;
  4. elk advies volgt uit de records, met bewijs dat je kunt natrekken.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from nooch_village import cockpit2, waarde_audit as wa

ROL = "mother_earth__nooch__creator_of_shoes"
NU = 1787000000.0                      # vast moment: de tests mogen niet van de klok afhangen


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _schrijf(dd, naam, data):
    with open(os.path.join(dd, naam), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _rij(rapport, rol=ROL):
    return next(r for r in rapport["rollen"] if r["id"] == rol)


def _skill(rapport, naam):
    return next(s for s in rapport["skills"] if s["naam"] == naam)


# ── 1. fail-closed ──────────────────────────────────────────────────────────

def test_veel_beweging_zonder_uitkomst_blijft_interne_beweging(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    for i in range(20):
        st.evidence.record(role_id=ROL, skill="epo_patents", query=f"q{i}",
                           source="ops.epo.org", status="bevestigd", ts=NU - 1000)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    rij = _rij(r)
    assert rij["uitkomsten"] == []                    # bevestigd bewijs is nog geen uitkomst
    assert rij["kroniek_n"] == 20
    assert rij["advies"] == wa.SLAPEN


def test_een_rol_die_nooit_iets_deed_wordt_opgeruimd(tmp_path):
    dd = _dd(tmp_path)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    rij = _rij(r)
    assert rij["advies"] == wa.OPRUIMEN
    assert "nooit iets voortgebracht" in rij["waarom"]


# ── 2. alleen echte uitkomsten ──────────────────────────────────────────────

def test_afgetekend_project_telt_met_zijn_id(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROL, "zool-leverancier vergelijken", "human")
    st.projects.complete(pid, "goedgekeurd na review")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    rij = _rij(r)
    assert [u["soort"] for u in rij["uitkomsten"]] == ["project_afgerond"]
    assert rij["uitkomsten"][0]["ref"] == pid         # narekenbaar
    assert pid in wa._bewijs(rij["uitkomsten"])


def test_alleen_een_definitie_van_klaar_is_geen_uitkomst(tmp_path):
    """`dod_outcome` zegt wanneer iets klaar zou zijn, niet dat het klaar IS."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROL, "iets", "human")
    ruw = json.load(open(os.path.join(dd, "projects.json"), encoding="utf-8"))
    ruw[pid]["dod_outcome"] = "Klaar als de leverancier bevestigt"
    _schrijf(dd, "projects.json", ruw)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    assert _rij(r)["uitkomsten"] == []


def test_niks_nodig_en_doorsturen_tellen_niet(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    n = st.notif.add("role", ROL, "", by=ROL, snippet="een spanning")
    st.notif.add_outcome(n["id"], otype="none", ref="", label="niks nodig")
    st.notif.add_outcome(n["id"], otype="ping", ref="", label="doorgestuurd")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    assert _rij(r)["uitkomsten"] == []


def test_een_echt_besluit_telt_wel(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    n = st.notif.add("role", ROL, "", by=ROL, snippet="een spanning")
    st.notif.add_outcome(n["id"], otype="besluit_ja", ref="", label="ja")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    rij = _rij(r)
    assert [u["soort"] for u in rij["uitkomsten"]] == ["besluit_genomen"]
    assert rij["uitkomsten"][0]["ref"] == n["id"]


def test_pagina_telt_pas_als_een_mens_hem_aanraakte(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    a = st.att.add(ROL, "note", title="Hennep", body="tekst", actor_id="ai-1", actor_type="ai")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    assert _rij(r)["uitkomsten"] == []
    assert _rij(r)["paginas"] == 1
    st.att.update(a.id, body="door een mens bijgewerkt", actor_id="p1", actor_type="human")
    r2 = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    assert [u["soort"] for u in _rij(r2)["uitkomsten"]] == ["pagina_bewerkt"]


# ── 3. onbekende prijs is niet nul ──────────────────────────────────────────

def test_onbekende_prijs_wordt_gevlagd_niet_op_nul_gezet(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.evidence.record(role_id=ROL, skill="epo_patents", query="q", source="s",
                       status="leeg", ts=NU - 1000)
    with open(os.path.join(dd, "llm_usage.jsonl"), "w", encoding="utf-8") as f:
        for _ in range(4):
            f.write(json.dumps({"call_site": "skill_epo_patents", "tier": "verzonnen:model",
                                "in_tokens": 1000, "out_tokens": 1000, "tokens": 2000,
                                "day": "2026-08-01", "ts": NU - 1000}) + "\n")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    s = _skill(r, "epo_patents")
    assert s["eur"] == 0.0 and s["onbekend"] == 4
    assert s["advies"] == wa.VLAG                      # niet stil als 'gratis' wegzetten
    assert "niet te bepalen" in s["waarom"]
    assert "4 zonder prijs" in wa._eur(s["eur"], s["onbekend"])


# ── 4. het advies volgt uit de records ──────────────────────────────────────

def test_bewezen_en_recent_is_wakker_houden(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROL, "iets echts", "human")
    st.projects.complete(pid, "goedgekeurd na review")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=time.time())
    assert _rij(r)["advies"] == wa.WAKKER


def test_bewezen_maar_lang_stil_wordt_gevlagd_niet_geraden():
    adv, waarom = wa.advies(uitkomsten=[{"soort": "x", "ref": "y"}],
                            laatst=NU - 200 * 86400, eur=0.0, onbekende_calls=0,
                            ooit_actief=True, nu=NU)
    assert adv == wa.VLAG and "af of vergeten" in waarom


def test_duur_zonder_uitkomst_komt_bovenaan_de_kostenlijst(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.evidence.record(role_id=ROL, skill="claim_evidence", query="q", source="s",
                       status="leeg", ts=NU - 1000)
    with open(os.path.join(dd, "llm_usage.jsonl"), "w", encoding="utf-8") as f:
        for _ in range(50):
            f.write(json.dumps({"call_site": "skill_claim_evidence",
                                "tier": "anthropic:claude-sonnet-5",
                                "in_tokens": 20000, "out_tokens": 5000, "tokens": 25000,
                                "day": "2026-08-01", "ts": NU - 1000}) + "\n")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    duur = wa.duurste_zonder_uitkomst(r)
    assert duur["skills"] and duur["skills"][0]["wat"] == "claim_evidence"
    assert duur["skills"][0]["eur"] > 0
    # Rollen en skills staan apart: het zijn dezelfde euro's, twee keer bekeken.
    assert duur["rollen"] and duur["rollen"][0]["eur"] == duur["skills"][0]["eur"]
    assert _skill(r, "claim_evidence")["advies"] == wa.SLAPEN


def test_top_line_telt_rollen_en_skills(tmp_path):
    dd = _dd(tmp_path)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    t = wa.top_line(r)
    assert t.startswith(f"{len(r['rollen'])} rollen en {len(r['skills'])} skills")
    assert "waarvan 0 aantoonbaar" in t


def test_het_verslag_zegt_wat_het_niet_meet(tmp_path):
    """De meetlat hoort in het stuk: een lijst zonder meetlat is een mening."""
    dd = _dd(tmp_path)
    tekst = wa.rapport_tekst(wa.audit(dd, cockpit2._Stores(dd).records, nu=NU))
    assert "Wat als uitkomst telt" in tekst
    assert "het is geen omzet" in tekst
    assert "Twijfelgevallen" in tekst


def test_cirkels_staan_niet_in_de_lijst(tmp_path):
    dd = _dd(tmp_path)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    assert "mother_earth__nooch" not in {x["id"] for x in r["rollen"]}


# ── 5. gedeelde skills worden niet bij elke rol vol geteld ──────────────────

def test_gedeelde_skill_wordt_naar_gebruik_verdeeld(tmp_path):
    """`tegenspraak` staat op acht rollen. Elke rol de volle prijs geven maakt het dorp acht keer
    zo duur als het is; de Kroniek weet wie hem écht draaide, dus dat is de verdeelsleutel."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    ander = "mother_earth__nooch__marketing_lead"
    # ROL draaide hem 3x, de ander 1x → 75/25.
    for i in range(3):
        st.evidence.record(role_id=ROL, skill="tegenspraak", query=f"q{i}", source="s",
                           status="bevestigd", ts=NU - 1000)
    st.evidence.record(role_id=ander, skill="tegenspraak", query="q9", source="s",
                       status="bevestigd", ts=NU - 1000)
    with open(os.path.join(dd, "llm_usage.jsonl"), "w", encoding="utf-8") as f:
        for _ in range(40):
            f.write(json.dumps({"call_site": "skill_tegenspraak",
                                "tier": "anthropic:claude-sonnet-5",
                                "in_tokens": 10000, "out_tokens": 2000, "tokens": 12000,
                                "day": "2026-08-01", "ts": NU - 1000}) + "\n")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    skill_eur = _skill(r, "tegenspraak")["eur"]
    mijn = _rij(r)["eur"]
    hun = _rij(r, ander)["eur"]
    assert skill_eur > 0
    assert mijn == pytest.approx(skill_eur * 0.75, rel=1e-6)
    assert hun == pytest.approx(skill_eur * 0.25, rel=1e-6)
    # En samen niet méér dan de skill zelf kostte.
    assert sum(x["eur"] for x in r["rollen"]) == pytest.approx(skill_eur, rel=1e-6)


def test_skill_zonder_enig_gebruiksrecord_hoort_bij_niemand(tmp_path):
    """Fail-closed: draaien zonder dat een record zegt wie, is geen grond om iemand te belasten."""
    dd = _dd(tmp_path)
    with open(os.path.join(dd, "llm_usage.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"call_site": "skill_spookskill",
                            "tier": "anthropic:claude-sonnet-5",
                            "in_tokens": 10000, "out_tokens": 2000, "tokens": 12000,
                            "day": "2026-08-01", "ts": NU - 1000}) + "\n")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    assert sum(x["eur"] for x in r["rollen"]) == 0.0
    assert "skill_spookskill" in r["zwevend"]
    assert "Niet toe te wijzen" in wa.rapport_tekst(r)


def _geef_skill(dd, skill):
    """Ken een skill toe via governance — dan staat hij in de inventaris, ook zonder ooit te draaien."""
    recs = cockpit2._Stores(dd).records
    rec = recs.get(ROL)
    rec.definition.skills = list(getattr(rec.definition, "skills", None) or []) + [skill]
    recs.put(rec)


def test_opruimen_noemt_wanneer_de_code_voor_het_laatst_bewoog(tmp_path, monkeypatch):
    """Nooit gedraaid is iets anders als de code vers is (nog niet bedraad) dan wanneer hij een jaar
    stil ligt (vergeten). Zonder git blijft het 'geen implementatiebestand gevonden' — geen gok."""
    dd = _dd(tmp_path)
    _geef_skill(dd, "serpapi_trends")
    monkeypatch.setattr(wa, "code_datums", lambda base: {"serpapi_trends": NU - 400 * 86400})
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU, base_dir="/verzonnen")
    s = _skill(r, "serpapi_trends")
    assert s["advies"] == wa.OPRUIMEN
    assert s["code_laatst"] == NU - 400 * 86400
    assert "code laatst gewijzigd" in wa.rapport_tekst(r)


def test_zonder_git_geen_verzonnen_datum(tmp_path):
    dd = _dd(tmp_path)
    _geef_skill(dd, "serpapi_trends")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)      # geen base_dir → geen git
    assert _skill(r, "serpapi_trends")["code_laatst"] is None
    assert "geen implementatiebestand gevonden" in wa.rapport_tekst(r)


# ── 6. grondwettelijke rollen vallen buiten de meting ───────────────────────

def test_de_secretary_wordt_nooit_opgeruimd(tmp_path):
    """Een Secretary die niets voortbrengt is geen dode rol maar een governance-drager. Het advies
    'opruimen' zou betekenen dat je hem opheft — dat is een categoriefout, geen bevinding."""
    dd = _dd(tmp_path)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    for rol in r["rollen"]:
        if wa.is_structureel(rol["id"]):
            assert rol["advies"] == wa.STRUCTUREEL, rol["id"]
    assert "Grondwettelijke rollen" in wa.rapport_tekst(r)


def test_structureel_wint_ook_van_een_bewezen_uitkomst(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    lead = "mother_earth__nooch__circle_lead"
    pid = st.projects.create(lead, "iets", "human")
    st.projects.complete(pid, "goedgekeurd na review")
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    rij = _rij(r, lead)
    assert rij["advies"] == wa.STRUCTUREEL
    assert "draagt wel 1 bewezen uitkomst" in rij["waarom"]


def test_dubbele_rolnamen_worden_uit_elkaar_gehouden(tmp_path):
    """Drie rollen die allemaal 'Circle Lead' heten zijn in een tabel niet te onderscheiden."""
    dd = _dd(tmp_path)
    r = wa.audit(dd, cockpit2._Stores(dd).records, nu=NU)
    namen = [x["naam"] for x in r["rollen"]]
    assert len(namen) == len(set(namen)), [n for n in namen if namen.count(n) > 1]


def test_de_kostenkolom_toont_model_en_bronverbruik(tmp_path):
    """Twee soorten verbruik, twee getallen: wat het model kostte en hoe vaak een externe bron is
    aangeroepen. Elke Kroniek-regel is zo'n aanroep."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    for i in range(7):
        st.evidence.record(role_id=ROL, skill="epo_patents", query=f"q{i}", source="ops",
                           status="bevestigd", ts=NU - 1000)
    with open(os.path.join(dd, "llm_usage.jsonl"), "w", encoding="utf-8") as f:
        for _ in range(3):
            f.write(json.dumps({"call_site": "skill_epo_patents",
                                "tier": "anthropic:claude-sonnet-5", "in_tokens": 100,
                                "out_tokens": 100, "tokens": 200, "day": "2026-08-01",
                                "ts": NU - 1000}) + "\n")
    tekst = wa.rapport_tekst(wa.audit(dd, cockpit2._Stores(dd).records, nu=NU))
    assert "3 model-calls" in tekst and "7 bron-aanroepen" in tekst
