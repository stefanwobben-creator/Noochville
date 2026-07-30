"""De recall-pas, de gat-oogst en de labels-motor van de claim-checker.

De guards, in volgorde van hoe duur de fout is die ze voorkomen:

1. **Fail-soft.** Zonder LLM is de scan EXACT het regex-pad. Deze pas mag nooit iets slechter maken
   dan het was; hij mag alleen kandidaten toevoegen.
2. **Nooit gehallucineerd, nooit rood.** Een fragment dat niet letterlijk op de pagina staat valt af,
   en een modelvondst is een vermoeden — rood blijft voorbehouden aan de termen-database met wetsbron.
3. **Gegrond in de records.** Het regelkader in de prompt komt uit de claims-database, niet uit een
   literal in code.
4. **Wat de tool niet kan, wordt opgeschreven.** Abstineren, novel type en ambigu bewijs leveren een
   capaciteitsgat op — én de bevinding wordt alsnog gevlagd.
5. **Een uitzondering verbergt niets.** Weggewuifd = geen taak, maar wél zichtbaar, met een label.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from nooch_village import claims_db, claims_labels, claims_modelpas, claims_substantiatie, gap_ledger
from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village.projects import ProjectLedger
from nooch_village.skills_impl import claims_site_scan as css
from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill

# Eén zin met een lijstterm (eco-friendly → rood) en één zin die een afbreekbaarheidsclaim maakt
# zonder één enkele lijstterm — precies het gat dat de modelpas moet dichten.
_ZIN_ZONDER_TERM = "Our soles simply return to the soil after a few seasons outdoors."
_PAGINA = f"""<html><head><title>Nooch</title></head><body>
<p>These shoes are eco-friendly and made on demand.</p>
<p>{_ZIN_ZONDER_TERM}</p>
</body></html>"""


def _ctx(tmp_path, monkeypatch=None, ledger=None):
    if monkeypatch is not None:
        kopie = tmp_path / "claims_database.json"
        kopie.write_text(json.dumps(claims_db.load(), ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(claims_db, "DB_PATH", str(kopie))
    return SimpleNamespace(data_dir=str(tmp_path), settings={}, records=None,
                           projects=ProjectLedger(str(tmp_path / "projects.json")),
                           evidence_ledger=ledger)


def _antwoord(fragment=_ZIN_ZONDER_TERM, zeker=True, categorie="Framing", **extra):
    """Een nep-LLM die één kandidaat teruggeeft."""
    payload = {"kandidaten": [{"fragment": fragment, "waarom": "belooft afbreekbaarheid",
                               "categorie": categorie, "zeker": zeker, **extra}]}
    return lambda *a, **k: json.dumps(payload)


def _stil(*a, **k):
    """Een LLM die niets teruggeeft — precies wat `llm.reason` doet zonder key."""
    return None


def _fetch(u):
    return (200, _PAGINA)


# ── Guard 1: fail-soft ───────────────────────────────────────────────────────────────────────

def test_zonder_llm_is_de_scan_exact_het_regex_pad(tmp_path):
    db = claims_db.load()
    paginas = css.scan_paginas(db)
    zonder_pas, _, _, _ = css.verzamel(paginas, db, _fetch=_fetch, modelpas=False)
    met_stille_pas, _, _, signalen = css.verzamel(paginas, db, _fetch=_fetch, reason_fn=_stil)
    assert met_stille_pas == zonder_pas                       # byte-voor-byte hetzelfde
    assert signalen["modelpas_gedraaid"] is False
    assert signalen["model_gevonden"] == 0


def test_kapot_llm_antwoord_is_ook_fail_soft(tmp_path):
    db = claims_db.load()
    pas = claims_modelpas.extra_kandidaten("tekst met inhoud", db, [],
                                           reason_fn=lambda *a, **k: "geen json {{{")
    assert pas["gedraaid"] is False and pas["kandidaten"] == []


def test_llm_die_klapt_breekt_de_scan_niet(tmp_path):
    def boem(*a, **k):
        raise RuntimeError("provider down")
    db = claims_db.load()
    bevindingen, _, _, signalen = css.verzamel(css.scan_paginas(db), db, _fetch=_fetch,
                                               reason_fn=boem)
    assert bevindingen                                        # het regex-pad draait door
    assert signalen["modelpas_gedraaid"] is False


# ── Guard 2: gegrond, en nooit rood ──────────────────────────────────────────────────────────

def test_modelvondst_wordt_kandidaat_met_zichtbare_herkomst(tmp_path):
    db = claims_db.load()
    bevindingen, _, _, signalen = css.verzamel(css.scan_paginas(db), db, _fetch=_fetch,
                                               reason_fn=_antwoord())
    model = [b for b in bevindingen if b.get("herkomst") == claims_modelpas.HERKOMST]
    assert model, "de modelvondst moet als bevinding meekomen"
    assert signalen["model_gevonden"] >= 1
    b = model[0]
    assert b["bron"] == claims_modelpas.BRON_LETTER           # M: geen wet, een vermoeden
    assert claims_modelpas.HERKOMST_LABEL in b["waarom"]
    assert b["stoplicht"] == "orange"                         # geen bewijs → oranje, telt mee
    assert b["onderbouwing"] == claims_substantiatie.ONTBREEKT


def test_modelpas_levert_nooit_rood(tmp_path):
    db = claims_db.load()
    pas = claims_modelpas.extra_kandidaten(_PAGINA, db, [], reason_fn=_antwoord())
    claims_modelpas.weeg_bewijs(pas["kandidaten"])
    assert all(b["stoplicht"] != "red" for b in pas["kandidaten"])


def test_modelvondst_met_bewijs_escaleert_in_plaats_van_oranje(tmp_path):
    """Bewijs aanwezig, formulering onbekend: de tool heeft geen wetsoordeel → compliance beslist."""
    led = EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))
    claims_substantiatie.leg_bewijs_vast(
        led, claim=_ZIN_ZONDER_TERM, bron="https://nooch.earth/materials", merk="nooch",
        citaat="Lab report: full soil degradation within one season under EN 13432.")
    db = claims_db.load()
    bevindingen, _, _, _ = css.verzamel(css.scan_paginas(db), db, _fetch=_fetch,
                                        reason_fn=_antwoord(), ledger=led)
    model = [b for b in bevindingen if b.get("herkomst") == claims_modelpas.HERKOMST][0]
    assert model["stoplicht"] == claims_db.ESCALEREN
    assert model["onderbouwing"] == claims_substantiatie.ONDERBOUWD


def test_gehallucineerd_fragment_valt_af(tmp_path):
    """De grondings-poort: wat niet letterlijk op de pagina staat, wordt nooit een taak."""
    db = claims_db.load()
    pas = claims_modelpas.extra_kandidaten(
        _PAGINA, db, [], reason_fn=_antwoord(fragment="Onze schoenen genezen de oceaan volledig."))
    assert pas["gedraaid"] is True
    assert pas["kandidaten"] == []
    assert pas["verworpen"][0]["reden"] == "niet letterlijk in de tekst"


def test_te_kort_fragment_valt_af(tmp_path):
    db = claims_db.load()
    pas = claims_modelpas.extra_kandidaten(_PAGINA, db, [], reason_fn=_antwoord(fragment="soil"))
    assert pas["kandidaten"] == []


def test_wat_de_regex_al_vond_wordt_niet_dubbel_gevlagd(tmp_path):
    db = claims_db.load()
    bestaande = [{"term": "eco-friendly", "gevonden": ["eco-friendly"], "stoplicht": "red"}]
    pas = claims_modelpas.extra_kandidaten(
        _PAGINA, db, bestaande,
        reason_fn=_antwoord(fragment="These shoes are eco-friendly and made on demand."))
    assert pas["kandidaten"] == []
    assert pas["verworpen"][0]["reden"] == "regex vond deze claim al"


def test_modelvondst_gaat_naar_compliance_niet_naar_de_copywriter(tmp_path, monkeypatch):
    """Er zit geen lijstterm en geen wetsartikel achter: het eerste werk is een oordeel."""
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run({"_fetch": _fetch, "_reason": _antwoord()}, ctx)
    model = [t for t in uit["aangemaakt"] if t.get("herkomst") == claims_modelpas.HERKOMST]
    assert model and all(t["owner"] == "compliance" for t in model)
    assert "model-gevonden" in uit["headsup"]


# ── Guard 3: de prompt is gegrond in de records ──────────────────────────────────────────────

def test_regelkader_komt_uit_de_database_niet_uit_code():
    db = claims_db.load()
    kader = claims_modelpas.regelkader(db)
    assert db["meta"]["toetsingskader"]["principe"][:40] in kader
    assert db["termen"][0]["term"] in kader                   # bestaande termen als 'niet nog eens'
    assert claims_modelpas.regelkader({}) == ""               # geen database → geen verzonnen kader


def test_regelkader_volgt_een_gewijzigde_database():
    eigen = {"meta": {"toetsingskader": {"principe": "eigen principe"}},
             "termen": [{"term": "verzonnen term", "categorie": "Eigen"}]}
    kader = claims_modelpas.regelkader(eigen)
    assert "eigen principe" in kader and "verzonnen term" in kader and "Eigen" in kader


def test_weggewuifde_vlaggen_gaan_als_negatief_de_prompt_in():
    gezien = {}

    def spion(prompt, **k):
        gezien["prompt"] = prompt
        return json.dumps({"kandidaten": []})
    claims_modelpas.extra_kandidaten(_PAGINA, claims_db.load(), [], reason_fn=spion,
                                     negatieven=["wij planten bomen in Portugal"])
    assert "wij planten bomen in Portugal" in gezien["prompt"]
    assert "GEEN claim" in gezien["prompt"]


# ── Guard 4: de gat-oogst ────────────────────────────────────────────────────────────────────

def test_geen_llm_terwijl_er_te_toetsen_was_geeft_een_capaciteitsgat(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run({"_fetch": _fetch, "_reason": _stil}, ctx)
    labels = [g["capability"] for g in gap_ledger.alle(str(tmp_path))]
    assert ClaimsSiteScanSkill.GAT_GEEN_MODELPAS in labels
    assert uit["nieuw"] >= 1                                  # en de regex-bevindingen landen gewoon
    assert all(g["reason"] == gap_ledger.MISSING_CAPABILITY for g in gap_ledger.alle(str(tmp_path)))


def test_onzekere_kandidaat_wordt_gevlagd_en_opgeschreven(tmp_path, monkeypatch):
    """Abstineren mag nooit betekenen: niks melden. Vlaggen én het gat vastleggen."""
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run({"_fetch": _fetch, "_reason": _antwoord(zeker=False)}, ctx)
    titels = " ".join(t["titel"] for t in uit["aangemaakt"])
    assert "soil" in titels                                   # de onzekere claim staat op het bord
    clusters = gap_ledger.clusters(str(tmp_path))
    labels = [c["capability"] for c in clusters]
    assert ClaimsSiteScanSkill.GAT_CLASSIFICATIE in labels


def test_gat_hangt_aan_het_project_dat_eruit_kwam(tmp_path, monkeypatch):
    """Zonder project-koppeling rangschikt de Codie-backlog een terugkerend gat onderaan."""
    ctx = _ctx(tmp_path, monkeypatch)
    ClaimsSiteScanSkill().run({"_fetch": _fetch, "_reason": _antwoord(zeker=False)}, ctx)
    cluster = [c for c in gap_ledger.clusters(str(tmp_path))
               if c["capability"] == ClaimsSiteScanSkill.GAT_CLASSIFICATIE][0]
    assert cluster["n_projecten"] == 1
    assert ctx.projects.get(cluster["projecten"][0]) is not None


def test_ambigu_bewijs_geeft_een_gat(tmp_path, monkeypatch):
    led = EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))
    led.record(role_id="compliance", skill=claims_substantiatie.SKILL,
               query="nooch — plasticvrije verpakking", source="https://nooch.earth/pack",
               status="bevestigd", result_ref="De verpakking is aantoonbaar plasticvrij.")
    ctx = _ctx(tmp_path, monkeypatch, ledger=led)
    ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, "<p>Onze plasticvrije zool is nieuw.</p>"),
                               "_reason": _stil}, ctx)
    labels = [g["capability"] for g in gap_ledger.alle(str(tmp_path))]
    assert ClaimsSiteScanSkill.GAT_SUBSTANTIATIE in labels


# ── Guard 5: een uitzondering verbergt niets ─────────────────────────────────────────────────

def test_uitzondering_onderdrukt_de_taak_maar_niet_de_bevinding(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    # Sitewide, want de nep-fetch geeft elke pagina dezelfde tekst; per-pagina wordt hieronder getest.
    claims_db.overlay_uitzondering(str(tmp_path), "These shoes are eco-friendly",
                                   waarom="citaat uit een klantvraag", door="stefan")
    uit = ClaimsSiteScanSkill().run({"_fetch": _fetch, "_reason": _stil}, ctx)
    gewhitelist = uit["gewhitelist"]
    assert gewhitelist, "de weggewuifde bevinding moet zichtbaar blijven"
    assert gewhitelist[0]["uitzondering"]["door"] == "stefan"
    assert gewhitelist[0]["term"]                             # mét de bevinding zelf, niet alleen een telling
    titels = " ".join(t["titel"] for t in uit["aangemaakt"])
    assert "eco-friendly" not in titels                       # maar geen taak meer


def test_uitzondering_geldt_per_pagina(tmp_path):
    db = claims_db.load(data_dir=str(tmp_path))
    claims_db.overlay_uitzondering(str(tmp_path), "made on demand", pagina="faq")
    db = claims_db.load(data_dir=str(tmp_path))
    op_faq = {"gevonden": ["made on demand"], "pagina": "faq", "term": "x"}
    op_home = {"gevonden": ["made on demand"], "pagina": "home", "term": "x"}
    assert claims_db.is_uitgezonderd(op_faq, db) is not None
    assert claims_db.is_uitgezonderd(op_home, db) is None     # andere pagina = nieuwe beslissing


def test_uitzondering_zonder_pagina_geldt_sitewide(tmp_path):
    claims_db.overlay_uitzondering(str(tmp_path), "made on demand")
    db = claims_db.load(data_dir=str(tmp_path))
    assert claims_db.is_uitgezonderd({"gevonden": ["made on demand"], "pagina": "x"}, db)


def test_uitzondering_moet_een_vindplaats_aanwijzen(tmp_path):
    """Een uitzondering op 'eco' zou de halve site blind maken — precies de fout die dit voorkomt."""
    with pytest.raises(ValueError):
        claims_db.overlay_uitzondering(str(tmp_path), "eco")
    assert not os.path.exists(os.path.join(str(tmp_path), claims_db.OVERLAY_NAAM))


def test_uitzondering_raakt_de_getrackte_seed_niet(tmp_path):
    voor = open(claims_db.DB_PATH, encoding="utf-8").read()
    claims_db.overlay_uitzondering(str(tmp_path), "made on demand somewhere")
    assert open(claims_db.DB_PATH, encoding="utf-8").read() == voor


# ── De twee lichte acties ────────────────────────────────────────────────────────────────────

def _dispatch_ctx(tmp_path, velden, username="guest"):
    """`guest` = auth-uit-modus, waarin `_role_gate` alles doorlaat; de poort zelf wordt hieronder
    apart getest met een geweigerde gebruiker."""
    return SimpleNamespace(nxt="/claims", st=SimpleNamespace(dd=str(tmp_path)), username=username,
                           data_dir=str(tmp_path), g=lambda k: velden.get(k, ""))


def test_whitelist_actie_legt_uitzondering_en_negatief_label_vast(tmp_path):
    from nooch_village import cockpit2
    ctx = _dispatch_ctx(tmp_path, {"fragment": "we plant a tree for every pair",
                                   "pagina": "home", "waarom": "geen milieuclaim over het product"})
    _, melding = cockpit2._act_claims_vondst_whitelist(ctx)
    assert "no claim" in melding
    db = claims_db.load(data_dir=str(tmp_path))
    assert claims_db.is_uitgezonderd({"gevonden": ["we plant a tree for every pair"],
                                      "pagina": "home"}, db)
    assert claims_labels.negatieven(str(tmp_path)) == ["we plant a tree for every pair"]


def test_regel_uit_vondst_maakt_een_patroon_dat_echt_matcht(tmp_path):
    from nooch_village import cockpit2
    ctx = _dispatch_ctx(tmp_path, {"fragment": "  return to the   soil  ", "pagina": "product"})
    _, melding = cockpit2._act_claims_regel_uit_vondst(ctx)
    assert "rule added" in melding
    db = claims_db.load(data_dir=str(tmp_path))
    uitslag = claims_db.check_tekst("Our soles return to\nthe soil after use.", db)
    termen = [b["term"] for b in uitslag["bevindingen"]]
    assert "return to the soil" in termen                     # witruimte-buigzaam patroon
    assert uitslag["bevindingen"][0]["stoplicht"] == claims_db.ESCALEREN   # geen tooloordeel
    assert claims_labels.alle(str(tmp_path))[0]["label"] == claims_labels.CLAIM


def test_regel_uit_vondst_weigert_een_lege_vondst(tmp_path):
    from nooch_village import cockpit2
    _, melding = cockpit2._act_claims_regel_uit_vondst(_dispatch_ctx(tmp_path, {"fragment": "ja"}))
    assert "⛔" in melding


def test_beide_acties_zijn_compliance_gated(tmp_path, monkeypatch):
    from nooch_village import cockpit2
    monkeypatch.setattr(cockpit2, "_role_gate", lambda *a, **k: "⛔ geen rechten")
    ctx = _dispatch_ctx(tmp_path, {"fragment": "een lange genoeg zin om te whitelisten"})
    for actie in (cockpit2._act_claims_vondst_whitelist, cockpit2._act_claims_regel_uit_vondst):
        _, melding = actie(ctx)
        assert "⛔" in melding
    assert claims_labels.alle(str(tmp_path)) == []             # niets weggeschreven
    assert not os.path.exists(os.path.join(str(tmp_path), claims_db.OVERLAY_NAAM))


def test_labels_telling_voor_het_scherm(tmp_path):
    claims_labels.leg_vast(str(tmp_path), fragment="wel een claim", label=claims_labels.CLAIM)
    claims_labels.leg_vast(str(tmp_path), fragment="geen claim hier", label=claims_labels.GEEN_CLAIM)
    claims_labels.leg_vast(str(tmp_path), fragment="", label=claims_labels.CLAIM)      # geweigerd
    assert claims_labels.telling(str(tmp_path)) == {"claim": 1, "geen-claim": 1, "totaal": 2}


def test_onbekend_label_wordt_geweigerd(tmp_path):
    assert claims_labels.leg_vast(str(tmp_path), fragment="x" * 30, label="misschien") is None


# ── De weergave ─────────────────────────────────────────────────────────────────────────────

def test_rapport_toont_herkomst_en_de_twee_acties():
    from nooch_village.views.claims import render_rapport
    uitslag = claims_db.check_tekst("These shoes are eco-friendly.")
    uitslag["tekst"] = "These shoes are eco-friendly."
    uitslag["bevindingen"][0]["herkomst"] = claims_modelpas.HERKOMST
    uitslag["bevindingen"][0]["model_zeker"] = False
    html = render_rapport(uitslag, csrf_token="t", kan_bord=True, db=claims_db.load())
    assert "model-found (no listed term)" in html
    assert "model unsure" in html
    assert "claims_vondst_whitelist" in html and "claims_regel_uit_vondst" in html
    assert "style=" not in html


def test_acties_alleen_voor_wie_mag_cureren():
    from nooch_village.views.claims import render_rapport
    uitslag = claims_db.check_tekst("These shoes are eco-friendly.")
    uitslag["tekst"] = "x"
    html = render_rapport(uitslag, csrf_token="t", kan_bord=False, db=claims_db.load())
    assert "claims_vondst_whitelist" not in html


def test_gemiste_claim_blok_alleen_voor_compliance():
    from nooch_village.views.claims import render_claims
    zonder = render_claims(csrf_token="t", tab="check", kan_cureren=False)
    met = render_claims(csrf_token="t", tab="check", kan_cureren=True,
                        labels={"claim": 2, "geen-claim": 1, "totaal": 3})
    assert "claims_regel_uit_vondst" not in zonder
    assert "claims_regel_uit_vondst" in met
    assert "2 caught misses" in met
    assert "style=" not in met
