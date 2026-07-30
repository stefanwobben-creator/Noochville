"""Claims-substantiatie: een claim is alleen groen als de Kroniek hem onderbouwt.

Guards, in volgorde van hoe duur de fout is die ze voorkomen:

1. **Nooit stil groen.** Een risico-term zonder bevestigend bewijs mag onder geen enkele
   omstandigheid als groen uit de scan komen — dat is de juridische blootstelling.
2. **Fail-closed.** Geen register, leeg register of een onleesbaar register betekent
   'niet onderbouwd', nooit 'in orde'.
3. **Alleen ons eigen bewijs telt.** Een bevestigd record over een concurrent onderbouwt
   onze claim niet. Zonder deze regel praat de concurrentie-analyse onze site groen.
4. **De scan wordt niet stil onvolledig.** Een 429 sluit de week niet af; een 404 doet dat
   wél (anders zet één dode pagina de scan voor altijd vast) en gaat naar compliance.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from nooch_village import claims_board, claims_db, claims_substantiatie, safe_fetch
from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village.projects import ProjectLedger
from nooch_village.skills_impl import claims_site_scan as css
from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill

# Een pagina met een risico-term (oranje: 'mag mits onderbouwd') en een claim die in de
# termen-database op groen staat. Beide horen zonder bewijs als vlag te eindigen.
_PAGINA = """<html><head><title>Nooch — plastic-free shoes</title></head><body>
<p>Our shoes are plastic-free and vegan.</p>
<p>Handmade in Portugal, made on demand.</p>
</body></html>"""


def _kroniek(tmp_path) -> EvidenceLedger:
    return EvidenceLedger(str(tmp_path / "evidence_ledger.jsonl"))


def _ctx(tmp_path, monkeypatch=None, ledger=None):
    """Scan-context met een wegwerpkopie van de claims-database (de scan schrijft statussen terug)."""
    if monkeypatch is not None:
        kopie = tmp_path / "claims_database.json"
        kopie.write_text(json.dumps(claims_db.load(), ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(claims_db, "DB_PATH", str(kopie))
    return SimpleNamespace(data_dir=str(tmp_path), settings={}, records=None,
                           projects=ProjectLedger(str(tmp_path / "projects.json")),
                           evidence_ledger=ledger)


def _bev(stoplicht="orange", term="plasticvrij / plastic-free", gevonden=("plastic-free",)):
    return {"term": term, "gevonden": list(gevonden), "stoplicht": stoplicht,
            "categorie": "Generiek", "waarom": "vraagt bewijs", "alternatief": "noem het materiaal",
            "pagina": "home", "url": "https://nooch.earth/"}


def _db():
    return claims_db.load()


# ── Guard 1: een risico-term zonder bewijs komt nooit groen uit de scan ──────────────────────

def test_risicoterm_zonder_bewijs_is_nooit_groen(tmp_path):
    bevindingen = [_bev(stoplicht="orange"), _bev(stoplicht="green", term="vegan",
                                                  gevonden=["vegan"])]
    claims_substantiatie.pas_toe(bevindingen, ledger=_kroniek(tmp_path), db=_db())
    assert [b["stoplicht"] for b in bevindingen] == ["orange", "orange"]
    assert all(b["onderbouwing"] == claims_substantiatie.ONTBREEKT for b in bevindingen)
    assert bevindingen[1]["onderbouwing_verhoogd"] is True     # groen → oranje, zichtbaar waarom


def test_de_hele_scan_laat_een_onderbouwing_loze_claim_niet_vallen(tmp_path, monkeypatch):
    """Van pagina tot bord: de claim overleeft de green-filter en landt als taak."""
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA)}, ctx)
    assert uit["ok"] and uit["nieuw"] >= 1
    taken = [ctx.projects.get(t["pid"]) for t in uit["aangemaakt"]]
    assert any("ONTBREEKT" in (t.get("description") or "") for t in taken)
    assert all(t["stoplicht"] != "green" for t in uit["aangemaakt"])


def test_rood_blijft_rood_ook_met_bewijs(tmp_path):
    """Bewijs maakt een verboden generieke claim niet toelaatbaar — geen bewijs-korting op rood."""
    led = _kroniek(tmp_path)
    claims_substantiatie.leg_bewijs_vast(
        led, claim="eco-friendly", bron="https://example.org/cert", merk="nooch",
        citaat="This product is certified eco-friendly under the scheme.")
    bevindingen = [_bev(stoplicht="red", term="milieuvriendelijk / eco-friendly",
                        gevonden=["eco-friendly"])]
    claims_substantiatie.pas_toe(bevindingen, ledger=led, db=_db())
    assert bevindingen[0]["stoplicht"] == "red"
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.NIET_VAN_TOEPASSING


# ── Guard 2: fail-closed ─────────────────────────────────────────────────────────────────────

def test_zonder_register_geldt_niets_als_onderbouwd(tmp_path):
    bevindingen = [_bev()]
    claims_substantiatie.pas_toe(bevindingen, ledger=None, db=_db())
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.ONTBREEKT


def test_onleesbaar_register_geldt_als_niet_onderbouwd(tmp_path):
    class Kapot:
        def all_records(self):
            raise OSError("schijf weg")
    bevindingen = [_bev()]
    claims_substantiatie.pas_toe(bevindingen, ledger=Kapot(), db=_db())
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.ONTBREEKT


def test_db_zonder_scan_paginas_kan_niets_onderbouwen(tmp_path):
    """Geen eigen domein af te leiden → geen eigen merk → niets onderbouwd. Liever alles oranje
    dan een willekeurig record dat onze claim groen praat."""
    led = _kroniek(tmp_path)
    claims_substantiatie.leg_bewijs_vast(led, claim="plastic-free", bron="https://nooch.earth/x",
                                         merk="nooch", citaat="Verified plastic-free by the lab.")
    bevindingen = [_bev()]
    claims_substantiatie.pas_toe(bevindingen, ledger=led, db={"meta": {}})
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.ONTBREEKT


# ── Guard 3: alleen bewijs over ons eigen product telt ───────────────────────────────────────

def test_bevestigd_bewijs_maakt_de_claim_onderbouwd(tmp_path):
    led = _kroniek(tmp_path)
    record = claims_substantiatie.leg_bewijs_vast(
        led, claim="plastic-free", bron="https://nooch.earth/pages/materials", merk="nooch",
        citaat="Independent lab report 2026-03: no synthetic polymers detected in the upper.")
    bevindingen = [_bev()]
    claims_substantiatie.pas_toe(bevindingen, ledger=led, db=_db())
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.ONDERBOUWD
    assert record["id"] in bevindingen[0]["onderbouwing_records"]
    assert "lab report" in bevindingen[0]["onderbouwing_reden"]


def test_bewijs_over_een_concurrent_onderbouwt_onze_claim_niet(tmp_path):
    led = _kroniek(tmp_path)
    led.record(role_id="compliance", skill="claim_evidence", query="Vivobarefoot — plastic-free",
               source="https://vivobarefoot.com/x", status="bevestigd",
               result_ref="Vivobarefoot is certified plastic-free by an external body.")
    bevindingen = [_bev()]
    claims_substantiatie.pas_toe(bevindingen, ledger=led, db=_db())
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.ONTBREEKT


def test_leeg_of_fout_record_is_geen_bewijs(tmp_path):
    """'Onderzocht, niets gevonden' is een kennisgat, niet een onderbouwing — dezelfde
    waarheidslat als claim_evidence, die 'onduidelijk' al op 'leeg' zet."""
    led = _kroniek(tmp_path)
    for status in ("leeg", "fout"):
        led.record(role_id="compliance", skill="claim_evidence", query="nooch — plastic-free",
                   source="https://nooch.earth/", status=status)
    bevindingen = [_bev()]
    claims_substantiatie.pas_toe(bevindingen, ledger=led, db=_db())
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.ONTBREEKT


def test_halve_match_is_ambigu_en_gedraagt_zich_als_ontbreekt(tmp_path):
    led = _kroniek(tmp_path)
    led.record(role_id="compliance", skill=claims_substantiatie.SKILL,
               query="nooch — plasticvrije verpakking", source="https://nooch.earth/pack",
               status="bevestigd", result_ref="De verpakking is aantoonbaar plasticvrij.",
               meta={"subject": "nooch"})
    bevindingen = [_bev(term="composteerbaar", gevonden=["plasticvrije zool"])]
    ambigu = claims_substantiatie.pas_toe(bevindingen, ledger=led, db=_db())
    assert bevindingen[0]["onderbouwing"] == claims_substantiatie.AMBIGU
    assert ambigu == bevindingen                                # grondstof voor de gat-oogst
    assert bevindingen[0]["stoplicht"] != "green"


def test_eigen_merken_volgen_de_scan_lijst_niet_een_literal():
    assert claims_substantiatie.eigen_merken(_db()) == {"nooch"}
    anders = {"meta": {"scan_paginas": [{"label": "x", "url": "https://voorbeeldmerk.nl/"}]}}
    assert claims_substantiatie.eigen_merken(anders) == {"voorbeeldmerk"}


# ── Het schrijfpad ──────────────────────────────────────────────────────────────────────────

def test_bewijs_vastleggen_eist_bron_en_letterlijk_citaat(tmp_path):
    led = _kroniek(tmp_path)
    with pytest.raises(ValueError):
        claims_substantiatie.leg_bewijs_vast(led, claim="", bron="https://x", citaat="x" * 30,
                                            merk="nooch")
    with pytest.raises(ValueError):
        claims_substantiatie.leg_bewijs_vast(led, claim="c", bron="", citaat="x" * 30, merk="nooch")
    with pytest.raises(ValueError):
        claims_substantiatie.leg_bewijs_vast(led, claim="c", bron="https://x", citaat="te kort",
                                            merk="nooch")
    assert led.all_records() == []                             # niets half weggeschreven


def test_vastgelegd_toont_alleen_handmatig_bewijs_nieuwste_eerst(tmp_path):
    led = _kroniek(tmp_path)
    led.record(role_id="x", skill="epo_patents", query="iets anders", source="ops",
               status="bevestigd")
    for n in range(2):
        claims_substantiatie.leg_bewijs_vast(led, claim=f"claim {n}", bron="https://nooch.earth/",
                                             merk="nooch", citaat="Een letterlijk citaat dat lang genoeg is.")
    rijen = claims_substantiatie.vastgelegd(led)
    assert [r["meta"]["claim"] for r in rijen] == ["claim 1", "claim 0"]


def test_bewijs_link_is_compliance_gated(tmp_path, monkeypatch):
    """De schrijfactie zit achter dezelfde poort als termen cureren: een ingelogde onbekende
    mag geen bewijs vaststellen."""
    from nooch_village import cockpit2
    monkeypatch.setattr(cockpit2, "_role_gate", lambda *a, **k: "⛔ geen rechten")
    ctx = SimpleNamespace(nxt="/claims", st=SimpleNamespace(dd=str(tmp_path)), username="vreemde",
                          data_dir=str(tmp_path), g=lambda k: "x")
    _, melding = cockpit2._act_claims_bewijs_link(ctx)
    assert "⛔" in melding
    assert not os.path.exists(str(tmp_path / "evidence_ledger.jsonl"))


# ── Guard 4: de scan wordt niet stil onvolledig (deel 0) ─────────────────────────────────────

def _fetch_met_429(mislukken: set[str], status: int = 429):
    def fetch(url):
        if any(m in url for m in mislukken):
            raise safe_fetch.FetchMislukt(f"de pagina gaf HTTP {status}", status=status)
        return (200, _PAGINA)
    return fetch


def test_tijdelijke_fout_sluit_de_week_niet_af(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run(
        {"_fetch": _fetch_met_429({"mission"}), "_sleep": lambda s: None}, ctx)
    assert uit["ok"] and uit["volledig"] is False
    assert not css.week_gedaan(str(tmp_path), css.period_key("week"))   # volgende puls pakt de rest
    assert "onvolledig" in uit["headsup"]
    assert "mission" in uit["headsup"]


def test_permanente_fout_zet_de_scan_niet_voor_altijd_vast(tmp_path, monkeypatch):
    """Een 404 in de scan-lijst is een lijst-probleem: de week mág dicht, en compliance hoort het."""
    ctx = _ctx(tmp_path, monkeypatch)
    uit = ClaimsSiteScanSkill().run(
        {"_fetch": _fetch_met_429({"mission"}, status=404), "_sleep": lambda s: None}, ctx)
    assert uit["ok"] and uit["volledig"] is True
    assert css.week_gedaan(str(tmp_path), css.period_key("week"))
    assert "bestaan niet meer" in uit["headsup"]
    meldingen = json.loads((tmp_path / "notifications.json").read_text(encoding="utf-8"))
    tekst = json.dumps(meldingen, ensure_ascii=False)
    assert "Scan-lijst" in tekst and "mission" in tekst


def test_tijdelijke_fout_wordt_opnieuw_geprobeerd(tmp_path):
    """De 429 die 4 van 5 pagina's stil wegdrukte: één retry lost hem op."""
    pogingen = {"n": 0}

    def wisselvallig(url):
        pogingen["n"] += 1
        if pogingen["n"] == 1:
            raise safe_fetch.FetchMislukt("de pagina gaf HTTP 429", status=429)
        return (200, _PAGINA)
    gewacht = []
    uit = safe_fetch.haal_tekst_geduldig("https://nooch.earth/", _fetch=wisselvallig,
                                         _sleep=gewacht.append)
    assert "plastic-free" in uit["tekst"]
    assert gewacht == [2.0]                                    # één backoff, geen stille opgave


def test_permanente_fout_wordt_niet_geprobeerd(tmp_path):
    def weg(url):
        raise safe_fetch.FetchMislukt("de pagina gaf HTTP 404", status=404)
    gewacht = []
    with pytest.raises(safe_fetch.FetchMislukt):
        safe_fetch.haal_tekst_geduldig("https://nooch.earth/x", _fetch=weg, _sleep=gewacht.append)
    assert gewacht == []                                       # geen zinloze retry-lus


def test_fout_soort_wordt_correct_geclassificeerd():
    assert safe_fetch.is_tijdelijk(safe_fetch.FetchMislukt("x", status=429))
    assert safe_fetch.is_tijdelijk(safe_fetch.FetchMislukt("x", status=503))
    assert safe_fetch.is_tijdelijk(safe_fetch.FetchMislukt("netwerk weg"))     # geen status
    assert not safe_fetch.is_tijdelijk(safe_fetch.FetchMislukt("x", status=404))
    assert not safe_fetch.is_tijdelijk(safe_fetch.FetchGeweigerd("intern adres"))


def test_scan_pauzeert_tussen_paginas(tmp_path, monkeypatch):
    """De rootcause van de 429: vijf fetches zonder pauze. Nu zit er beleefdheid tussen."""
    ctx = _ctx(tmp_path, monkeypatch)
    gewacht = []
    ClaimsSiteScanSkill().run({"_fetch": lambda u: (200, _PAGINA),
                               "_sleep": gewacht.append}, ctx)
    paginas = len(css.scan_paginas(claims_db.load(data_dir=str(tmp_path))))
    assert gewacht == [css.PAUZE_SECONDEN] * (paginas - 1)


# ── Terugkoppeling (deel 3) ─────────────────────────────────────────────────────────────────

def test_headsup_noemt_term_en_pagina(tmp_path):
    aangemaakt = [{"pid": "p1", "owner": "compliance", "titel": "🔴 Vervang: eco-friendly",
                   "stoplicht": "red", "gevonden": "eco-friendly", "pagina": "home"},
                  {"pid": "p2", "owner": "compliance", "titel": "🔴 Vervang: climate neutral",
                   "stoplicht": "red", "gevonden": "climate neutral", "pagina": "impact"},
                  {"pid": "p3", "owner": "compliance", "titel": "🟠 Onderbouw: vegan",
                   "stoplicht": "orange", "gevonden": "vegan", "pagina": "faq"}]
    tekst = claims_board.vindplaatsen(aangemaakt, stoplicht="red")
    assert tekst == '"eco-friendly" (home), "climate neutral" (impact)'
    assert "vegan" not in tekst


def test_vindplaatsen_verzwijgt_de_rest_niet():
    aangemaakt = [{"stoplicht": "red", "gevonden": f"term{n}", "pagina": "home"} for n in range(5)]
    tekst = claims_board.vindplaatsen(aangemaakt, stoplicht="red")
    assert tekst.endswith("+2 meer")


def test_bord_taak_draagt_de_vindplaats_mee(tmp_path):
    omg = SimpleNamespace(projects=ProjectLedger(str(tmp_path / "p.json")), records=None,
                          data_dir=str(tmp_path))
    bev = _bev(stoplicht="red", term="gifvrij", gevonden=["volstrekt gifvrij"])
    bev["onderbouwing"] = claims_substantiatie.ONTBREEKT
    from nooch_village.views.claims import rol_voor
    verslag = claims_board.zet_op_bord(omg, _db(), [bev], "scan", rol_voor)
    assert verslag["aangemaakt"][0]["gevonden"] == "volstrekt gifvrij"
    assert verslag["aangemaakt"][0]["pagina"] == "home"
