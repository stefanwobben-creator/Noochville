"""Structurele fix voor projecten die eeuwig ACTIEF blijven op een skill-loos item.

De knel (prod, 28 juli 2026 — pid e39f1c2feabb en e327ccac08b0): een uitvoerplan met 4 skill-items
en 1 item zonder skill ("zorg dat de QR-code op de schoenen linkt naar…"). De uitvoerlus slaat een
skill-loos item over, de vastloop-klep keek alléén naar skill-items die hun retry-grens raakten, en
`done == total` werd dus nooit gehaald. Elke puls opnieuw: "⏳ voortgang 4/5 — blijft in ACTIEF".
Zulke zombies waren de hoofdmoot van de 34 running-projecten tegen een WIP-bord van 3.

Twee garanties, en dit bestand bevriest ze allebei:
  1. één tend op een project waarvan alleen nog skill-loze items open staan → NIET meer running;
  2. "sla over" op dat item maakt de checklist afrondbaar → het project kan naar review.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.project_items import resolve_item
from nooch_village.projects import ProjectLedger, checklist_progress
from nooch_village.skills import Skill, SkillRegistry

TODAY = "2026-07-29"


class _OkSkill(Skill):
    name = "claims_check"
    description = "fake skill die het altijd doet"

    def run(self, payload, context):
        return {"ok": True, "result": "gecontroleerd"}


class _StukSkill(Skill):
    name = "kapotte_bron"
    description = "fake skill die altijd een bronfout geeft"

    def run(self, payload, context):
        return {"error": "bron gaf HTTP 500"}


def _inh(tmp_path, ledger, **settings):
    reg = SkillRegistry()
    reg.register(_OkSkill())
    reg.register(_StukSkill())
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", **settings},
                          data_dir=str(tmp_path), projects=ledger, records=None)
    rec = Record(id="compliance", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="geen greenwashing", accountabilities=["claims"],
                                           domains=[], skills=["claims_check", "kapotte_bron"]),
                 source="sensed")
    return Inhabitant(rec, EventBus(name="test"), reg, ctx)


def _project(ledger, items):
    """items = [(tekst, skill|None)] — bouwt een ACTIEF project met een uitvoerplan."""
    pid = ledger.create("compliance", "QR-codes op alle schoenen", "human", status="queued")
    ledger.start(pid)
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    for tekst, skill in items:
        ledger.check_add(pid, cl["id"], tekst, skill=skill,
                         reason="" if skill else "geen skill: dit vraagt een mens")
    return pid, cl["id"]


# ── garantie 1: de zombie kan niet meer ontstaan ────────────────────────────────

def test_alleen_skilloos_item_open_gaat_na_een_tend_naar_waiting(tmp_path):
    """DE test. Vier skill-items lopen, het vijfde kan alleen een mens doen: na één tend staat het
    project op WAITING (blocked) — niet meer op running, dus ook niet meer in de WIP-telling."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("verifieer de claim", "claims_check"),
                                  ("toets de uitleg", "claims_check"),
                                  ("controleer de certificaten", "claims_check"),
                                  ("escaleer twijfels", "claims_check"),
                                  ("zorg dat de QR-code op de schoen komt", None)])
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), TODAY)

    p = ledger.get(pid)
    assert p["status"] != "running"                     # ← de zombie is weg
    assert p["status"] == "blocked" and "vastgelopen" in (p["blocked_on"] or "")
    assert "mens of externe partij" in (p["blocked_on"] or "")
    assert checklist_progress(_cl(p, clid)) == (4, 5)   # eerlijk: 4 van 5, nog niet af


def test_de_mensvraag_gaat_niet_over_een_bron_die_leeg_bleef(tmp_path):
    """Taal telt: bij een skill-loos item is er geen bron mislukt. 'Bron X bleef leeg' stuurt de mens
    het verkeerde bos in; de vraag moet zijn dat dit een mens of externe partij vereist."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("regel een fysieke sticker bij de leverancier", None)])
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), TODAY)

    vraag = next(e["text"] for e in ledger.get(pid).get("log", []) if e["text"].startswith("⏸️"))
    assert "mens of externe partij" in vraag
    assert "regel een fysieke sticker bij de leverancier" in vraag
    assert "pogingen" not in vraag                      # geen retry-taal bij werk dat nooit is geprobeerd


def test_blijft_actief_zolang_een_skill_item_nog_pogingen_over_heeft(tmp_path):
    """De klep mag niet te vroeg dichtslaan: één kansloos item naast een skill-item dat nog mag
    herproberen → het project blijft gewoon actief."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, _clid = _project(ledger, [("mens-taak", None), ("haal bewijs op", "kapotte_bron")])
    inh = _inh(tmp_path, ledger, item_fail_limit="3")

    inh._execute_checklist(ledger.get(pid), TODAY)      # poging 1 van 3 op het skill-item

    assert ledger.get(pid)["status"] == "running"


def test_parkeert_zodra_ook_het_skill_item_op_is(tmp_path):
    """…en slaat wél dicht zodra niemand meer vooruit kan (skill-item op zijn grens + mens-item)."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, _clid = _project(ledger, [("mens-taak", None), ("haal bewijs op", "kapotte_bron")])
    inh = _inh(tmp_path, ledger, item_fail_limit="1")

    inh._execute_checklist(ledger.get(pid), TODAY)

    p = ledger.get(pid)
    assert p["status"] == "blocked"
    vraag = next(e["text"] for e in p.get("log", []) if e["text"].startswith("⏸️"))
    assert "mens of externe partij" in vraag and "pogingen" in vraag    # beide blokkades benoemd


def test_onuitvoerbare_payload_telt_ook_als_kansloos(tmp_path):
    """Zelfde zombie-familie: een item mét skill maar met payload_ok=False wordt door de uitvoerlus
    overgeslagen, dus het kan uit zichzelf nooit vooruit."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid = ledger.create("compliance", "doel", "human", status="queued")
    ledger.start(pid)
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "onvolledig item", skill="claims_check", payload_ok=False)
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), TODAY)

    assert ledger.get(pid)["status"] == "blocked"


def test_klep_uit_beschermt_nog_steeds_tegen_het_kansloze_item(tmp_path):
    """`item_fail_limit=0` zet alleen het retry-parkeren uit (skill-items herproberen eeuwig).
    Een item dat geen enkele skill ooit kan draaien blijft blokkeren — anders is de zombie terug."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, _clid = _project(ledger, [("mens-taak", None)])
    inh = _inh(tmp_path, ledger, item_fail_limit="0")

    inh._execute_checklist(ledger.get(pid), TODAY)

    assert ledger.get(pid)["status"] == "blocked"


# ── garantie 2: de mens kan de lus doorbreken ──────────────────────────────────

def _cl(p, clid):
    return next(c for c in p["checklists"] if c["id"] == clid)


def test_sla_over_brengt_het_project_naar_review(tmp_path):
    """DE tweede test. 4/5 af, het vijfde item is een mens-taak die niet (meer) hoeft: 'sla over'
    haalt 'm uit de klaar-telling, waardoor done == telbaar en het project naar review kan."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("verifieer de claim", "claims_check"),
                                  ("toets de uitleg", "claims_check"),
                                  ("controleer de certificaten", "claims_check"),
                                  ("escaleer twijfels", "claims_check"),
                                  ("zorg dat de QR-code op de schoen komt", None)])
    inh = _inh(tmp_path, ledger)
    inh._execute_checklist(ledger.get(pid), TODAY)             # → geparkeerd op het mens-item
    item = _cl(ledger.get(pid), clid)["items"][-1]

    ok, msg = resolve_item(ledger, pid, clid, item["id"], "skip",
                           reason="stickers vervallen; QR komt op de doos", by="stefan")

    assert ok and "review" in msg
    p = ledger.get(pid)
    assert p["status"] == "blocked" and p["blocked_on"] == "review"   # klaar voor review
    assert checklist_progress(_cl(p, clid)) == (4, 4)                # overgeslagen telt niet mee
    assert _cl(p, clid)["items"][-1]["skipped"] is True               # blijft staan, mét reden
    assert "vervallen" in _cl(p, clid)["items"][-1]["skip_reason"]


def test_gedaan_brengt_het_project_ook_naar_review(tmp_path):
    """(a) van de drie: 'ik heb het gedaan' vinkt af én controleert of het project daarmee af is —
    anders sluit de mens het laatste item terwijl het project geparkeerd blijft staan."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("doe de claim", "claims_check"), ("mens-taak", None)])
    inh = _inh(tmp_path, ledger)
    inh._execute_checklist(ledger.get(pid), TODAY)
    item = _cl(ledger.get(pid), clid)["items"][-1]

    ok, msg = resolve_item(ledger, pid, clid, item["id"], "done", by="stefan")

    assert ok and "review" in msg
    assert ledger.get(pid)["blocked_on"] == "review"


def test_overdragen_maakt_een_project_bij_de_andere_rol(tmp_path):
    """(c) van de drie: los mens-project via het projectverzoek-patroon. Het item is hier klaar
    (overgedragen), het werk leeft verder op het bord van de andere rol, en beide zijn gelinkt."""
    from nooch_village.governance import Records
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    recs = Records(str(tmp_path / "gov.json"))
    recs.put(Record(id="website_developer", type=RecordType.ROLE, parent=None,
                    definition=RoleDefinition(purpose="de site")))
    pid, clid = _project(ledger, [("bouw de QR-landingspagina", None)])
    item = _cl(ledger.get(pid), clid)["items"][0]

    ok, msg = resolve_item(ledger, pid, clid, item["id"], "handoff", naar_rol="website_developer",
                           reason="pagina staat live", by="stefan", records=recs)

    assert ok and "website_developer" in msg
    nieuw = [p for p in ledger.all() if p["owner"] == "website_developer"]
    assert len(nieuw) == 1 and nieuw[0]["status"] == "queued"
    assert nieuw[0]["origin"] == "projectverzoek" and pid in nieuw[0]["links"]
    assert _cl(ledger.get(pid), clid)["items"][0]["skipped"] is True   # telt hier niet meer mee


def test_overdragen_naar_een_onbekende_rol_doet_niets(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    from nooch_village.governance import Records
    recs = Records(str(tmp_path / "gov.json"))
    pid, clid = _project(ledger, [("bouw iets", None)])
    item = _cl(ledger.get(pid), clid)["items"][0]

    ok, msg = resolve_item(ledger, pid, clid, item["id"], "handoff", naar_rol="bestaat_niet",
                           records=recs)

    assert not ok and "onbekende doelrol" in msg
    assert not _cl(ledger.get(pid), clid)["items"][0].get("skipped")


def test_overslaan_is_terug_te_draaien(tmp_path):
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("mens-taak", None), ("nog een", None)])
    item = _cl(ledger.get(pid), clid)["items"][0]

    resolve_item(ledger, pid, clid, item["id"], "skip", reason="nvt")
    ok, _msg = resolve_item(ledger, pid, clid, item["id"], "unskip")

    assert ok and not _cl(ledger.get(pid), clid)["items"][0].get("skipped")
    assert checklist_progress(_cl(ledger.get(pid), clid)) == (0, 2)


def test_afvinken_duwt_een_toekomst_project_niet_de_review_in(tmp_path):
    """Grens: alleen werk dat loopt (of geparkeerd wacht) gaat naar review. Een TOEKOMST-project mag
    niet door het aanvinken van vakjes de review-gate in worden geduwd."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid = ledger.create("compliance", "nog niet begonnen", "human", status="future")
    cl = ledger.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    ledger.check_add(pid, cl["id"], "een taak", skill=None)
    item = _cl(ledger.get(pid), cl["id"])["items"][0]

    resolve_item(ledger, pid, cl["id"], item["id"], "done")

    assert ledger.get(pid)["status"] == "future"


def test_een_overgeslagen_item_wordt_niet_meer_uitgevoerd(tmp_path):
    """Idempotent: de uitvoerlus laat een overgeslagen item met rust, ook als het een skill heeft."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("haal bewijs op", "kapotte_bron")])
    item = _cl(ledger.get(pid), clid)["items"][0]
    resolve_item(ledger, pid, clid, item["id"], "skip", reason="niet meer nodig")
    ledger.start(pid)                                          # mens zet 'm terug op actief
    inh = _inh(tmp_path, ledger)

    inh._execute_checklist(ledger.get(pid), TODAY)

    assert not _cl(ledger.get(pid), clid)["items"][0].get("fails")   # geen poging gedaan


# ── de knoppen in de cockpit (thread-vrij, via render + dispatch) ───────────────

ROLE = "mother_earth__nooch__website_developer"


def _cockpit(tmp_path):
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2, dd, cockpit2._Stores(dd)


def _mensproject(st):
    pid = st.projects.create(ROLE, "iets met een mens-taak", "human", status="queued")
    st.projects.start(pid)
    cl = st.projects.checklist_add(pid, title=Inhabitant._PREP_CHECKLIST_TITLE)
    st.projects.check_add(pid, cl["id"], "controleer de tekst", skill="content_check")
    st.projects.check_add(pid, cl["id"], "bel de leverancier", skill=None,
                          reason="geen skill: dit vraagt een mens")
    st.projects.check_toggle(pid, cl["id"], _cl(st.projects.get(pid), cl["id"])["items"][0]["id"])
    return pid, cl["id"]


def test_view_toont_de_uitkomsten_bij_een_mens_item(tmp_path):
    from nooch_village.views import projects as P
    cockpit2, dd, st = _cockpit(tmp_path)
    pid, _clid = _mensproject(st)

    rw = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    ro = P.render_project(cockpit2._Stores(dd), pid, csrf_token="")

    assert "check_skip" in rw and "check_handoff" in rw
    assert "check_skip" not in ro                      # read-only: geen knoppen


def test_skip_via_dispatch_brengt_het_project_naar_review(tmp_path):
    cockpit2, dd, st = _cockpit(tmp_path)
    pid, clid = _mensproject(st)
    item = _cl(st.projects.get(pid), clid)["items"][-1]

    _nxt, msg = cockpit2.dispatch(dd, "check_skip",
                                  {"pid": [pid], "clid": [clid], "item": [item["id"]],
                                   "reason": ["niet meer nodig"], "next": ["/"]}, username="guest")

    assert "review" in msg
    assert cockpit2._Stores(dd).projects.get(pid)["blocked_on"] == "review"


def test_laatste_vinkje_via_dispatch_brengt_het_project_naar_review(tmp_path):
    """Het ✓-vakje loopt via dezelfde resolutie-route — anders blijft een geparkeerd project staan
    nadat de mens het laatste item afvinkt (geblokkeerd = niet meer getend)."""
    cockpit2, dd, st = _cockpit(tmp_path)
    pid, clid = _mensproject(st)
    st.projects.block(pid, "vastgelopen op 1 item(s) — wacht op een mens of externe partij")
    item = _cl(st.projects.get(pid), clid)["items"][-1]

    cockpit2.dispatch(dd, "check_toggle", {"pid": [pid], "clid": [clid], "item": [item["id"]],
                                           "next": ["/"]}, username="guest")

    assert cockpit2._Stores(dd).projects.get(pid)["blocked_on"] == "review"


# ── valse voltooiing: overslaan mag nooit lezen als afronden ────────────────────

def test_overgeslagen_taak_staat_apart_in_de_einddocument_opdracht(tmp_path):
    """Een overgeslagen item is een BESLUIT, geen kennisgat: het krijgt een eigen, stelligere
    instructie ('niet beantwoord') en valt niet in de generieke 'niet onderzocht'-bak."""
    from unittest.mock import patch
    from nooch_village.inhabitant import _skipped_tasks, _ungrounded_tasks, synthesize_einddocument
    from nooch_village.project_doc_store import ProjectDocStore
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("doe de claim", "claims_check"), ("mens-taak", None)])
    item = _cl(ledger.get(pid), clid)["items"][-1]
    resolve_item(ledger, pid, clid, item["id"], "skip", reason="valt buiten scope")
    p = ledger.get(pid)

    assert _skipped_tasks(p) == [("mens-taak", "valt buiten scope")]
    assert "mens-taak" not in _ungrounded_tasks(p, [])       # niet in de generieke bak

    with patch("nooch_village.llm.reason", return_value="# doc") as m:
        synthesize_einddocument(project_docs=ProjectDocStore(str(tmp_path)), deliverables=None,
                                projects=ledger, personas=None, record=None, settings={},
                                project=p, force_final=True, log=logging.getLogger("t"))
    prompt = m.call_args[0][0]
    assert "NIET BEANTWOORDE TAKEN" in prompt
    assert "valt buiten scope" in prompt
    assert "NIET beantwoord" in prompt
    assert "conclusie" in prompt.lower()                     # moet in de conclusie benoemd worden


def test_review_melding_benoemt_de_overgeslagen_taak(tmp_path):
    """Op het review-moment moet de mens zien dat 4/4 niet 'alles gedaan' betekent."""
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("doe de claim", "claims_check"), ("materiaal-analyse", None)])
    inh = _inh(tmp_path, ledger)
    inh._execute_checklist(ledger.get(pid), TODAY)
    item = _cl(ledger.get(pid), clid)["items"][-1]

    resolve_item(ledger, pid, clid, item["id"], "skip", reason="geen labcapaciteit")

    melding = [e["text"] for e in ledger.get(pid).get("log", []) if "klaar voor review" in e["text"]][-1]
    assert "materiaal-analyse" in melding and "geen labcapaciteit" in melding
    assert "NIET beantwoord" in melding


def test_afrond_uitkomst_draagt_de_overgeslagen_taak_mee(tmp_path):
    """De uitkomst is wat later over dit project wordt teruggelezen — daar hoort het besluit in."""
    from nooch_village import cockpit2
    cockpit2_, dd, st = _cockpit(tmp_path)
    pid, clid = _mensproject(st)
    item = _cl(st.projects.get(pid), clid)["items"][-1]
    cockpit2_.dispatch(dd, "check_skip", {"pid": [pid], "clid": [clid], "item": [item["id"]],
                                          "reason": ["niet meer nodig"], "next": ["/"]},
                       username="guest")
    st2 = cockpit2._Stores(dd)
    st2.project_docs.write(pid, "# Rapport\n\nEcht antwoord op de vraag, met bevindingen.")

    cockpit2_.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")

    uitkomst = cockpit2._Stores(dd).projects.get(pid)["outcome"]
    assert "overgeslagen" in uitkomst and "NIET beantwoord" in uitkomst


def test_voortgangsbadge_markeert_een_overgeslagen_taak(tmp_path):
    """100% zonder markering leest als 'alles gedaan'; de ⤳ en de tooltip voorkomen dat."""
    from nooch_village.views import projects as P
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    pid, clid = _project(ledger, [("doe de claim", "claims_check"), ("materiaal-analyse", None)])
    items = _cl(ledger.get(pid), clid)["items"]
    ledger.check_toggle(pid, clid, items[0]["id"])
    resolve_item(ledger, pid, clid, items[1]["id"], "skip", reason="geen labcapaciteit")

    badge = P._progress_badge(ledger.get(pid))

    assert "100%" in badge and "⤳" in badge
    assert "materiaal-analyse" in badge and "geen labcapaciteit" in badge   # in de tooltip
