"""Afslanken — slapen is omkeerbaar, en de poorten zijn niet te omzeilen.

Vijf beloften:
  1. slapen ≠ verwijderen: het record blijft compleet en één commando zet het terug;
  2. een slapende rol krijgt geen thread, geen oordeel en geen nieuw werk;
  3. grondwettelijke rollen zijn onaanraakbaar, ook via een expliciet besluit;
  4. een skill die een WAKKERE rol houdt wordt niet weggenomen;
  5. dry-run schrijft niets.
"""
from __future__ import annotations

import json
import os

import pytest

from nooch_village import afslanken as af, cockpit2

ROL = "mother_earth__nooch__marketing_lead"
LEAD = "mother_earth__nooch__circle_lead"
WAKKER_ROL = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _recs(dd):
    from nooch_village.governance import Records
    return Records(os.path.join(dd, "governance_records.json"))


def _audit(**rijen):
    """Een minimaal audit-dict, zonder een verslag te hoeven schrijven."""
    return {"rollen": rijen.get("rollen", []), "skills": rijen.get("skills", []), "pad": "test.md"}


def _rol(naam, rid, advies, bewijs="iets"):
    return {"naam": naam, "id": rid, "advies": advies, "bewijs": bewijs,
            "uitkomst": "**nee**", "kosten": "€0.00", "laatst": "nooit"}


def _skill(naam, advies, bewijs="iets"):
    return {"naam": naam, "id": "", "advies": advies, "bewijs": bewijs,
            "uitkomst": "**nee**", "kosten": "€0.00", "laatst": "nooit"}


# ── 1. slapen is omkeerbaar ─────────────────────────────────────────────────

def test_slapen_laat_het_record_compleet(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    voor = recs.get(ROL)
    purpose, accs, versie = voor.definition.purpose, list(voor.definition.accountabilities), voor.version
    assert af.slaap_leggen(recs, ROL, reden="audit: geen uitkomst", data_dir=dd)
    recs.save()
    na = _recs(dd).get(ROL)
    assert na.slaapt is True and na.slaap_reden and na.slaap_sinds
    assert na.archived is False                       # NIET gearchiveerd
    assert na.definition.purpose == purpose           # DNA ongemoeid
    assert list(na.definition.accountabilities) == accs
    assert na.version == versie


def test_wekken_zet_alles_terug(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    af.slaap_leggen(recs, ROL, reden="x", data_dir=dd)
    recs.save()
    recs2 = _recs(dd)
    assert af.wekken(recs2, ROL, data_dir=dd)
    recs2.save()
    na = _recs(dd).get(ROL)
    assert na.slaapt is False and na.slaap_reden is None and na.slaap_sinds is None


def test_het_spoor_draagt_de_terugweg(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    af.slaap_leggen(recs, ROL, reden="audit", data_dir=dd)
    regels = [json.loads(x) for x in open(os.path.join(dd, af.BESTAND), encoding="utf-8") if x.strip()]
    assert regels[-1]["actie"] == "slaap"
    assert regels[-1]["terug"] == f"village afslanken wek {ROL}"


def test_slapen_is_idempotent(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    assert af.slaap_leggen(recs, ROL, reden="x", data_dir=dd) is True
    assert af.slaap_leggen(recs, ROL, reden="x", data_dir=dd) is False


# ── 2. een slapende rol draait niet, oordeelt niet, krijgt geen werk ────────

def test_slapende_rol_krijgt_geen_thread(tmp_path):
    """De Reconciler bouwt hem niet — dát is wat slapen doet."""
    from nooch_village.governance import Reconciler
    dd = _dd(tmp_path)
    recs = _recs(dd)
    af.slaap_leggen(recs, ROL, reden="x")
    recs.save()

    class _Bus:
        def subscribe(self, *a, **k): pass
        def publish(self, *a, **k): pass

    class _MM:
        def register(self, *a, **k): pass

    class _Reg:
        def get(self, *a, **k): return object()        # elke skill 'bestaat'

    class _Ctx:
        settings = {"reflect_interval_seconds": "0"}
        data_dir = dd
        links = None

    r = Reconciler(_recs(dd), _Bus(), _Reg(), _Ctx(), _MM(), class_map={})
    r.build()
    assert ROL not in r.live
    assert ROL in r.unmanned                            # zichtbaar gepauzeerd, niet verdwenen


def test_slapende_rol_krijgt_geen_oordeel_meer(tmp_path):
    """De dure kant: geen bevinding, geen typering voor een spanning van een slapende rol."""
    from nooch_village.spanning_ontstaat import maak_verrijker
    dd = _dd(tmp_path)
    recs = _recs(dd)
    st = cockpit2._Stores(dd)
    geroepen = []

    def _reason(*a, **k):
        geroepen.append(1)
        return '{"spanning": "x", "voorstel": "y"}'

    verrijk = maak_verrijker(recs, st.assign, dd, reason_fn=_reason)
    n = {"target_type": "role", "target_id": WAKKER_ROL, "by": ROL, "snippet": "een spanning"}
    af.slaap_leggen(recs, ROL, reden="x")
    assert verrijk(dict(n)) == {}
    assert geroepen == []                               # geen enkele model-call


def test_slapende_rol_staat_niet_meer_op_de_roster(tmp_path):
    from nooch_village import escalation_router as er
    dd = _dd(tmp_path)
    recs = _recs(dd)
    assert any(x["id"] == ROL for x in er.roster(recs, exclude=set()))
    af.slaap_leggen(recs, ROL, reden="x")
    assert not any(x["id"] == ROL for x in er.roster(recs, exclude=set()))


# ── 3. grondwettelijke rollen zijn onaanraakbaar ────────────────────────────

def test_een_circle_lead_kan_niet_slapen(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    assert af.slaap_leggen(recs, LEAD, reden="x", data_dir=dd) is False
    assert recs.get(LEAD).slaapt is False


def test_een_secretary_kan_niet_gearchiveerd_worden(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    sec = "mother_earth__nooch__secretary"
    assert af.rol_opruimen(recs, sec, reden="x", data_dir=dd) is False
    assert recs.get(sec).archived is False


def test_het_plan_slaat_grondwettelijke_rollen_over_ook_als_de_audit_ze_noemt(tmp_path):
    """Fail-closed: een verkeerd verslag mag de organisatie niet kunnen uitzetten."""
    dd = _dd(tmp_path)
    recs = _recs(dd)
    p = af.plan(_audit(rollen=[_rol("Circle Lead", LEAD, af.SLAPEN)]), recs)
    assert p["slapen"] == []
    assert any("grondwettelijk" in o["waarom"] for o in p["overgeslagen"])


# ── 4. een wakkere rol raakt zijn handen niet kwijt ─────────────────────────

def test_skill_van_een_wakkere_rol_wordt_niet_ingetrokken(tmp_path):
    """De audit beoordeelt een skill op 'deliverable in een afgetekend project'. Bij compliance en
    de librarian is dat massaal niet zo, terwijl die rollen wakker blijven — die skills wegnemen
    zou een wakkere rol zijn handen afnemen op grond van een meting over iets anders."""
    dd = _dd(tmp_path)
    recs = _recs(dd)
    rec = recs.get(WAKKER_ROL)
    rec.definition.skills = ["claims_check"]
    recs.put(rec)
    audit = _audit(rollen=[_rol("Creator", WAKKER_ROL, af.WAKKER)],
                   skills=[_skill("claims_check", af.OPRUIMEN)])
    p = af.plan(audit, recs)
    assert p["opruimen"] == []
    assert any("WAKKERE rol" in o["waarom"] for o in p["overgeslagen"])


def test_een_skill_met_advies_slapen_wordt_niet_stilzwijgend_ingetrokken(tmp_path):
    """Voor een skill bestaat geen omkeerbare slaap. 'Slapen' naar 'weg' escaleren is precies de
    fout die deze operatie moest vermijden."""
    dd = _dd(tmp_path)
    p = af.plan(_audit(skills=[_skill("field_note", af.SLAPEN)]), _recs(dd))
    assert p["opruimen"] == []
    assert any("geen omkeerbare slaap" in o["waarom"] for o in p["overgeslagen"])


def test_een_expliciet_founder_besluit_gaat_wel_door(tmp_path):
    dd = _dd(tmp_path)
    p = af.plan(_audit(skills=[_skill("tegenspraak", af.SLAPEN)]), _recs(dd),
                kill_skills=("tegenspraak",))
    assert [x["naam"] for x in p["opruimen"]] == ["tegenspraak"]
    assert p["opruimen"][0]["expliciet"] is True


def test_intrekken_haalt_de_skill_bij_elke_houder_weg_en_bumpt_de_versie(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    rec = recs.get(ROL)
    rec.definition.skills = ["tegenspraak", "iets_anders"]
    v = rec.version
    recs.put(rec)
    geraakt = af.skill_intrekken(recs, "tegenspraak", reden="founder", data_dir=dd)
    assert geraakt == [ROL]
    na = recs.get(ROL)
    assert na.definition.skills == ["iets_anders"]
    assert na.version == v + 1                          # DNA-wijziging = versie omhoog


# ── 5. dry-run schrijft niets ───────────────────────────────────────────────

def test_plan_muteert_niets(tmp_path):
    dd = _dd(tmp_path)
    pad = os.path.join(dd, "governance_records.json")
    voor = open(pad, encoding="utf-8").read()
    audit = _audit(rollen=[_rol("Marketing", ROL, af.SLAPEN)],
                   skills=[_skill("bulletin_schrijven", af.OPRUIMEN)])
    p = af.plan(audit, _recs(dd))
    assert p["slapen"] and p["opruimen"]
    assert open(pad, encoding="utf-8").read() == voor
    assert not os.path.exists(os.path.join(dd, af.BESTAND))
    assert "DRY-RUN" in af.rapport_tekst(p, apply=False)
    assert "afslanken wek" in af.rapport_tekst(p, apply=False)   # de terugweg staat erbij


def test_onvindbaar_verslag_stelt_niets_voor(tmp_path):
    """Fail-closed: onleesbaar verslag = geen operatie, geen gok."""
    a = af.lees_audit(str(tmp_path / "bestaat-niet.md"))
    assert a["rollen"] == [] and a["skills"] == []
    p = af.plan(a, _recs(_dd(tmp_path)))
    assert p["slapen"] == [] and p["opruimen"] == []


# ── 6. een seed mag een governance-besluit niet terugdraaien ────────────────

def test_seed_zet_een_ingetrokken_skill_niet_terug(tmp_path):
    """Op prod stond `bulletin_schrijven` na het afslanken gewoon weer bij Noochie: de seeding
    'zorgt idempotent' dat een rol een skill heeft, en draaide daarmee stil een besluit terug."""
    from nooch_village import seeds
    dd = _dd(tmp_path)
    recs = _recs(dd)
    rec = recs.get(ROL)
    rec.definition.skills = ["bulletin_schrijven"]
    recs.put(rec)

    af.skill_intrekken(recs, "bulletin_schrijven", reden="founder", data_dir=dd)
    assert recs.get(ROL).definition.skills == []
    assert "bulletin_schrijven" in recs.get(ROL).ingetrokken_skills

    # De seed draait opnieuw (elke Village-start) en moet hem NIET terugzetten.
    assert seeds._zorg_skill(recs, recs.get(ROL), "bulletin_schrijven") is False
    assert recs.get(ROL).definition.skills == []


def test_seed_vult_wel_aan_wat_nooit_besloten_is(tmp_path):
    """De poort mag niet zo streng worden dat een verse rol zijn skill nooit krijgt."""
    from nooch_village import seeds
    dd = _dd(tmp_path)
    recs = _recs(dd)
    rec = recs.get(ROL)
    rec.definition.skills = []
    recs.put(rec)
    assert seeds._zorg_skill(recs, recs.get(ROL), "gsc_report") is True
    assert "gsc_report" in recs.get(ROL).definition.skills


def test_de_intrekking_is_terug_te_draaien(tmp_path):
    dd = _dd(tmp_path)
    recs = _recs(dd)
    rec = recs.get(ROL)
    rec.definition.skills = ["tegenspraak"]
    recs.put(rec)
    af.skill_intrekken(recs, "tegenspraak", reden="founder", data_dir=dd)
    assert af.skill_herstellen(recs, "tegenspraak", ROL, data_dir=dd) is True
    na = recs.get(ROL)
    assert "tegenspraak" in na.definition.skills
    assert na.ingetrokken_skills == []
    # En dan mag de seed hem weer gewoon aanvullen.
    from nooch_village import seeds
    na.definition.skills = []
    recs.put(na)
    assert seeds._zorg_skill(recs, recs.get(ROL), "tegenspraak") is True
