"""Seed/overlay-splitsing van de claims-database: de getrackte seed blijft read-only, runtime-
curatie (toevoegen/intrekken/status) landt in data/claims_runtime.json. Dekt de exacte delta-merge,
de conflictregel (aanwezigheid wint), de test-isolatie van het overlay-pad, de migratie en de
retract-UI via de dispatch."""
from __future__ import annotations

import json
import os
import shutil

from nooch_village import claims_db, claims_migrate, cockpit2


def _kopie_seed(tmp_path):
    """Een verse kopie van de seed op een tmp-pad + een eigen data_dir voor de overlay."""
    pad = str(tmp_path / "claims_database.json")
    shutil.copy(claims_db.DB_PATH, pad)
    dd = str(tmp_path / "data")
    os.makedirs(dd, exist_ok=True)
    return pad, dd


# ── 1. De overlay-kern ────────────────────────────────────────────────────────────────────────

def test_geen_overlay_is_identiek_aan_seed(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    seed = claims_db.load_seed()
    eff = claims_db.load(data_dir=dd)
    assert [t["patroon"] for t in eff["termen"]] == [t["patroon"] for t in seed["termen"]]
    assert not os.path.exists(os.path.join(dd, "claims_runtime.json"))   # lezen schrijft niets


def test_add_landt_in_overlay_niet_in_seed(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    voor = len(claims_db.load_seed()["termen"])
    nieuw, versie = claims_db.overlay_add_term(dd, term="Xclaim", patroon=r"xclaim",
                                               stoplicht="red", categorie="Test")
    assert nieuw["term"] == "Xclaim" and versie
    eff = claims_db.load(data_dir=dd)
    assert any(t["patroon"] == "xclaim" for t in eff["termen"]) and len(eff["termen"]) == voor + 1
    assert os.path.exists(os.path.join(dd, "claims_runtime.json"))       # onder data_dir (isolatie)
    assert len(claims_db.load_seed()["termen"]) == voor                  # seed ongemoeid


def test_retract_runtime_term_verdwijnt_schoon(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db.overlay_add_term(dd, term="Weg", patroon=r"wegterm", stoplicht="orange", categorie="Test")
    claims_db.overlay_retract(dd, "wegterm")
    eff = claims_db.load(data_dir=dd)
    assert not any(t["patroon"] == "wegterm" for t in eff["termen"])
    assert not eff.get("_conflicten")                                    # geen conflict: was runtime


def test_retract_seed_term_blijft_en_meldt_conflict(tmp_path):
    """De conflictregel: een in-git seed-term die runtime wordt ingetrokken blijft staan
    (aanwezigheid wint) en het conflict wordt zichtbaar in `_conflicten` gezet."""
    _pad, dd = _kopie_seed(tmp_path)
    seed_patroon = claims_db.load_seed()["termen"][0]["patroon"]
    claims_db.overlay_retract(dd, seed_patroon)
    eff = claims_db.load(data_dir=dd)
    assert any(t["patroon"] == seed_patroon for t in eff["termen"])      # blijft staan
    assert eff.get("_conflicten")                                        # conflict zichtbaar


def test_add_heft_eerdere_retractie_op(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db.overlay_retract(dd, "herstelterm")
    claims_db.overlay_add_term(dd, term="Herstel", patroon=r"herstelterm", stoplicht="green", categorie="Test")
    eff = claims_db.load(data_dir=dd)
    assert any(t["patroon"] == "herstelterm" for t in eff["termen"])
    ov = json.load(open(os.path.join(dd, "claims_runtime.json"), encoding="utf-8"))
    assert "herstelterm" not in ov["ingetrokken"]


def test_status_override_via_overlay(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    seed = claims_db.load_seed()
    item = seed["werklijst"][0]
    doel = next(s for s in claims_db.werk_statussen(seed) if s != item["status"])
    claims_db.overlay_set_status(dd, item["nr"], doel)
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == item["nr"])["status"] == doel
    assert claims_db.load_seed()["werklijst"][0]["status"] == item["status"]    # seed ongemoeid


def test_status_onbekend_wordt_geweigerd_maar_machine_mag_auto(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    nr = claims_db.load_seed()["werklijst"][0]["nr"]
    try:
        claims_db.overlay_set_status(dd, nr, "verzonnenstatus")
        assert False, "onbekende status moet weigeren"
    except ValueError:
        pass
    # de auto-scan mag de AUTO_STATUSSEN wél zetten
    claims_db.overlay_set_status(dd, nr, claims_db.AUTO_REGRESSIE, machine=True)
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == nr)["status"] == claims_db.AUTO_REGRESSIE


def test_check_tekst_pikt_runtime_term_op(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db.overlay_add_term(dd, term="Runtimeclaim", patroon=r"runtimeclaim",
                               stoplicht="red", categorie="Test")
    met = claims_db.check_tekst("hier staat een runtimeclaim", data_dir=dd)
    assert any(b["term"] == "Runtimeclaim" for b in met["bevindingen"])
    zonder = claims_db.check_tekst("hier staat een runtimeclaim")       # kale seed
    assert not any(b["term"] == "Runtimeclaim" for b in zonder["bevindingen"])


def test_kapotte_overlay_faalt_luid(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    with open(os.path.join(dd, "claims_runtime.json"), "w", encoding="utf-8") as f:
        f.write("{ kapot")
    try:
        claims_db.load(data_dir=dd)
        assert False, "kapotte overlay moet luid falen"
    except claims_db.ClaimsDbError:
        pass


# ── 2. Migratie ───────────────────────────────────────────────────────────────────────────────

def test_bereken_delta_tilt_extra_termen_en_statusdiffs():
    committed = {"termen": [{"patroon": "a", "term": "A"}],
                 "werklijst": [{"nr": 1, "status": "open"}], "meta": {"versie": "2026-07-01"}}
    working = {"termen": [{"patroon": "a", "term": "A"}, {"patroon": "b", "term": "B-runtime"}],
               "werklijst": [{"nr": 1, "status": "opgelost"}], "meta": {"versie": "2026-07-20"}}
    d = claims_migrate.bereken_delta(committed, working)
    assert [t["patroon"] for t in d["toegevoegd"]] == ["b"]
    assert d["werklijst"] == {"1": "opgelost"} and d["meta_versie"] == "2026-07-20"
    assert d["ingetrokken"] == []                                        # nooit auto-intrekken
    assert claims_migrate._leeg(claims_migrate.bereken_delta(committed, committed))


def test_migratie_is_idempotent_als_overlay_bestaat(tmp_path, capsys):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db._schrijf_overlay(dd, claims_db._leeg_overlay())
    assert claims_migrate.main([dd]) == 0
    assert "bestaat al" in capsys.readouterr().out


# ── 3. Retract-UI via de dispatch ───────────────────────────────────────────────────────────────

def test_dispatch_retract_verwijdert_runtime_term(tmp_path, monkeypatch):
    pad, dd = _kopie_seed(tmp_path)
    monkeypatch.setattr(claims_db, "DB_PATH", pad)
    cockpit2.dispatch(dd, "claims_term_add",
                      {"term": ["Tijdelijk"], "patroon": ["tijdelijkterm"], "stoplicht": ["red"],
                       "categorie": ["Test"], "next": ["/claims"]}, "guest")
    assert any(t["patroon"] == "tijdelijkterm" for t in claims_db.load(data_dir=dd)["termen"])
    _, msg = cockpit2.dispatch(dd, "claims_term_retract",
                               {"patroon": ["tijdelijkterm"], "next": ["/claims"]}, "guest")
    assert msg.startswith("✓")
    assert not any(t["patroon"] == "tijdelijkterm" for t in claims_db.load(data_dir=dd)["termen"])


def test_database_tab_toont_intrek_knop_alleen_voor_curator(tmp_path, monkeypatch):
    pad, dd = _kopie_seed(tmp_path)
    monkeypatch.setattr(claims_db, "DB_PATH", pad)
    from nooch_village.views.claims import render_claims
    zonder = render_claims(csrf_token="t", tab="database", kan_cureren=False, data_dir=dd)
    assert "claims_term_retract" not in zonder
    met = render_claims(csrf_token="t", tab="database", kan_cureren=True, data_dir=dd)
    assert "claims_term_retract" in met and "Retract" in met


# ── 5. Een mislukte schrijfactie meldt geen succes ────────────────────────────────────────────

def _scan_omgeving(tmp_path, monkeypatch, *, laat_schrijven_falen: bool):
    """Een `_verifieer_werklijst`-opstelling waarin één claim-frase op de pagina staat terwijl het
    item al op 'opgelost' stond. Dat is een REGRESSIE: het pad met een bericht eraan vast."""
    from nooch_village import claims_db as cdb
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill

    _pad, dd = _kopie_seed(tmp_path)
    db = cdb.load(data_dir=dd)
    item = next(i for i in db["werklijst"] if _frase(i))
    frase = _frase(item)
    cdb.overlay_set_status(dd, item["nr"], cdb.AUTO_OPGELOST, machine=True)
    db = cdb.load(data_dir=dd)

    if laat_schrijven_falen:
        def _kapot(*a, **k):
            raise OSError("schijf vol")
        monkeypatch.setattr(cdb, "overlay_set_status", _kapot)

    berichten = []
    monkeypatch.setattr("nooch_village.claims_board.bericht_aan_rol",
                        lambda ctx, rol, tekst, **k: berichten.append((rol, tekst)) or [rol])

    class _Ctx:
        data_dir = dd
        projects = None

    uit = ClaimsSiteScanSkill()._verifieer_werklijst(_Ctx(), db, {"home": f"... {frase} ..."})
    return uit, berichten, dd, item["nr"]


def _frase(item):
    from nooch_village.claims_verify import claim_frases
    fr = claim_frases(item)
    return fr[0] if fr else ""


def test_geslaagde_statuswijziging_telt_en_meldt(tmp_path, monkeypatch):
    """De referentie: als het schrijven lukt, gaat alles zoals het hoort."""
    (geschreven, mislukt), berichten, dd, nr = _scan_omgeving(tmp_path, monkeypatch,
                                                              laat_schrijven_falen=False)
    assert mislukt == [], "geen enkele statuswijziging mag stilletjes stranden"
    assert nr in [v["nr"] for v in geschreven]
    assert any("staat weer op de site" in t for _rol, t in berichten)
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == nr)["status"] == claims_db.AUTO_REGRESSIE


def test_mislukte_statuswijziging_meldt_geen_succes_en_stuurt_geen_bericht(tmp_path, monkeypatch):
    """DE BUG. `overlay_set_status` faalde met een kale `continue`, maar de wijziging bleef in
    `gewijzigd` staan. Gevolg: het regressie-bericht ('staat weer op de site') ging de deur uit
    voor een status die nergens is opgeslagen, `statussen` telde de mislukking als succes, en de
    volgende scan deed exact hetzelfde nog eens — er was immers niets veranderd.

    Niet geschreven = niet gebeurd. De mislukking verdwijnt niet: hij komt als reden naar boven."""
    (geschreven, mislukt), berichten, dd, nr = _scan_omgeving(tmp_path, monkeypatch,
                                                              laat_schrijven_falen=True)
    assert geschreven == [], "een niet-opgeslagen wijziging is geen wijziging"
    assert any(f"#{nr} " in m and "OSError" in m for m in mislukt)
    assert not berichten, "geen bericht over een status die nergens staat"
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == nr)["status"] == claims_db.AUTO_OPGELOST


def test_onleesbare_claims_db_geeft_de_reden_mee(tmp_path, monkeypatch):
    """Fail-soft blijft, maar stil is het niet meer: de reden reist mee naar de aanroeper."""
    from nooch_village import claims_db as cdb
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill

    _pad, dd = _kopie_seed(tmp_path)
    db = cdb.load(data_dir=dd)
    item = next(i for i in db["werklijst"] if _frase(i))
    monkeypatch.setattr(cdb, "load", lambda *a, **k: (_ for _ in ()).throw(
        cdb.ClaimsDbError("kapot bestand")))

    class _Ctx:
        data_dir = dd
        projects = None

    geschreven, mislukt = ClaimsSiteScanSkill()._verifieer_werklijst(
        _Ctx(), db, {"home": f"... {_frase(item)} ..."})
    assert geschreven == []
    assert mislukt and "niet leesbaar" in mislukt[0]


def test_de_scan_verzint_geen_statuswaarden(tmp_path):
    """DE REGRESSIETEST OP EEN LIVE BUG. `claims_verify` bouwde de auto-opgelost-status als
    `f"{AUTO_OPGELOST[:-1]} {datum})"`: een nieuwe statuswaarde per dag. `overlay_set_status`
    kent alleen de vaste `AUTO_STATUSSEN` en weigerde die met een ValueError, die de aanroeper
    met een kale `continue` opat. Sinds de seed/overlay-splitsing is er dus geen enkele
    auto-oplossing weggeschreven, terwijl de scan hem elke week als wijziging meldde.

    Erger nog: de regressiedetectie vergelijkt `huidig == AUTO_OPGELOST`, en tegen een gedateerde
    variant matcht dat nooit. Een claim die de scanner zelf had afgemeld en die daarna terugkwam
    op de site, was daarmee onzichtbaar geworden voor precies de module die hem moet zien.

    De invariant, niet de inhoud: elke status die `verifieer` voorstelt moet een BESTAANDE waarde
    zijn — een die `overlay_set_status(machine=True)` ook accepteert."""
    from nooch_village import claims_verify

    _pad, dd = _kopie_seed(tmp_path)
    db = claims_db.load(data_dir=dd)
    tekst = " ".join(_frase(i) for i in db["werklijst"] if _frase(i))
    geldig = set(claims_db.werk_statussen(claims_db.load_seed())) | set(claims_db.AUTO_STATUSSEN)

    for volledig in (True, False):
        for paginas in ({"home": tekst}, {"home": "niets van dit alles"}):
            for v in claims_verify.verifieer(db, paginas, volledig=volledig):
                assert v["naar"] in geldig, (
                    f"verzonnen status {v['naar']!r} — overlay_set_status weigert die, en de "
                    f"weigering is eerder een jaar lang opgegeten")


def test_auto_opgelost_wordt_ook_echt_opgeslagen(tmp_path, monkeypatch):
    """Het end-to-end bewijs van hierboven: de auto-oplossing landt nu in de overlay."""
    from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill

    _pad, dd = _kopie_seed(tmp_path)
    db = claims_db.load(data_dir=dd)
    item = next(i for i in db["werklijst"] if _frase(i) and i.get("status") == "open")
    monkeypatch.setattr("nooch_village.claims_board.bericht_aan_rol",
                        lambda *a, **k: [])

    class _Ctx:
        data_dir = dd
        projects = None

    # Een pagina zonder de frase: de claim is weg → auto-opgelost.
    geschreven, mislukt = ClaimsSiteScanSkill()._verifieer_werklijst(
        _Ctx(), db, {"home": "een pagina zonder enige claim"})
    assert mislukt == []
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == item["nr"])["status"] \
        == claims_db.AUTO_OPGELOST
    assert item["nr"] in [v["nr"] for v in geschreven]
