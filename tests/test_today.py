"""/today (13 oktober 2026): een leesoverzicht op bestaande gegevens.

Getoetst op de HTML zelf:
  - de pagina laadt en toont de blokken met de juiste aantallen op testdata;
  - Finance: zonder recht ontbreekt CN2 helemaal en bevat de HTML geen runway-getal of Finance-term
    (ook niet verborgen); met recht staat de tegel er;
  - geen Finance-getal in een kop (Noochie stuurt de eerste kop mee);
  - de open-vragen-aantallen zijn gelijk aan die op /open-questions (één berekening);
  - lege toestanden: geen acties, geen open vragen, geen goals, een Critical Number zonder waarde;
  - het nav-item staat onder de meeting-knoppen en boven Projects.
"""
from __future__ import annotations

import http.client
import re
import threading
import time
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, zicht
from nooch_village.views.open_vragen import stand
from tests.test_cn2_runway import C, _dorp, _st, _vul

LID_ROL = "mother_earth__nooch__marketing_lead"
SHOE = "mother_earth__nooch__shoe_developer"
FINANCE_TERMEN = ("runway", "cash", "fixed-costs", "finance", "bunq", "mollie", "payables",
                  "liabilities")


def _vraagpagina(st):
    """Een materiaalpagina zonder feiten: elke vraag erop is open (zoals in test_w1_antwoorden)."""
    st.att.add(SHOE, "note", title="Full Green", body="## Conclusion\n\nSome text.", meta={"feiten": []})
    st.bom_materialen.zet("Insole", "Full Green")


def _testdorp(tmp_path, *, vragen=True, werk=True, doelen=True):
    dd = _dorp(tmp_path)
    st = _st(dd)
    lid = st.people.by_email("lid@t.nl").id
    if vragen:
        _vraagpagina(st)
    if werk:
        st.acties.add(lid, "Bel de fabriek")
        st.acties.add(lid, "Mail de leverancier")
        for titel, n in (("Vegan Society", 3), ("MITH report", 2)):
            pid = st.projects.create(LID_ROL, titel, "human", status="running")
            cl = st.projects.checklist_add(pid, "Plan")
            for i in range(n):
                st.projects.check_add(pid, cl["id"], f"Stap {i}")
    if doelen:
        st.doelen.add("Te laat", deadline="2026-01-01")
        st.doelen.add("Later", deadline="2099-06-30")
        st.doelen.add("Zonder datum")
        gehaald = st.doelen.add("Al gehaald")
        st.doelen.update(gehaald["id"], status="behaald")
    return dd


def _server(dd):
    sessies = _auth.SessionStore()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, sessies


def _get(httpd, sessies, pad, wie):
    c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=20)
    c.request("GET", pad, headers={"Cookie": f"nv_session={sessies.create(wie)}"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


@pytest.fixture
def dorp(tmp_path):
    return _testdorp(tmp_path)


@pytest.fixture
def server(dorp):
    httpd, sessies = _server(dorp)
    yield lambda pad, wie: _get(httpd, sessies, pad, wie)
    httpd.shutdown()


# ── laden, blokken en aantallen ─────────────────────────────────────────────

def test_today_laadt_met_de_blokken_en_de_juiste_aantallen(server):
    status, h = server("/today", "lid@t.nl")
    assert status == 200
    assert "<h1 class='ptitle'>Today</h1>" in h
    assert time.strftime("%B %Y") in h                                    # de datum
    for kop in ("Critical numbers", "My actions", "Open questions", "Goals"):
        assert kop in h, kop
    assert "2 open of your own" in h
    assert "5 checklist items need a human" in h and "across 2 projects" in h
    assert "biggest: Vegan Society (3), MITH report (2)" in h
    for link in ("href='/acties'", "href='/open-questions'", "href='/goals'"):
        assert link in h, link


def test_goals_alleen_open_achterstallig_eerst_dan_op_deadline(server):
    _s, h = server("/today", "lid@t.nl")
    blok = h.split("<h3>Goals</h3>", 1)[1]
    volgorde = [t for t in ("Te laat", "Later", "Zonder datum") if t in blok]
    assert volgorde == ["Te laat", "Later", "Zonder datum"]
    assert blok.index("Te laat") < blok.index("Later") < blok.index("Zonder datum")
    assert "Al gehaald" not in blok                                       # behaald valt weg
    assert re.search(r"Overdue \d+ days", blok) and "Due 30 Jun 2099" in blok and "No deadline" in blok


def test_het_navitem_staat_onder_de_meetings_en_boven_projects(server):
    _s, h = server("/today", "lid@t.nl")
    zij = h.split("<nav class='c2-subnav'", 1)[1]
    assert zij.index("href='/today'") < zij.index("href='/projects'")
    assert zij.index("c2-overleg") < zij.index("href='/today'")
    assert re.search(r"<a href='/today'[^>]*aria-current", h)              # de huidige plek
    assert ">TD<" in zij and zij.count(">TO<") == 1                      # Tools houdt "TO"


# ── Finance ─────────────────────────────────────────────────────────────────

def test_zonder_finance_recht_geen_cn2_en_geen_finance_term_in_de_html(dorp):
    _vul(dorp, bunq=43210, mollie=1000, tax=500, payables=250, kosten=2000)
    httpd, sessies = _server(dorp)
    try:
        _s, lid = _get(httpd, sessies, "/today", "lid@t.nl")
        _s, fc = _get(httpd, sessies, "/today", "fc@t.nl")
    finally:
        httpd.shutdown()
    assert zicht.mag(_st(dorp), "fc@t.nl", "finance") and not zicht.mag(_st(dorp), "lid@t.nl", "finance")
    gevonden = [w for w in FINANCE_TERMEN if w in lid.lower()]
    assert gevonden == [], gevonden                                       # ook niet verborgen
    for getal in ("43210", "43.210", "44210", "21.2", "21.2 "):
        assert getal not in lid, getal
    assert "Runway (months)" in fc and "Runway (months)" not in lid
    assert lid.count("<div class='tile'>") == fc.count("<div class='tile'>") - 1   # geen plaatshouder


def test_geen_finance_getal_in_een_kop(dorp):
    _vul(dorp, bunq=43210, mollie=1000, tax=500, payables=250, kosten=2000)
    httpd, sessies = _server(dorp)
    try:
        _s, h = _get(httpd, sessies, "/today", "fc@t.nl")
    finally:
        httpd.shutdown()
    # Noochie leest de eerste `h1`/`h2` BINNEN `.c2-main` (views/noochie.py, ctxLabel)
    inhoud = h.split("<div class='c2-main'>", 1)[1]
    koppen = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", inhoud, re.S)
    assert koppen and koppen[0] == "Today"
    assert not any(re.search(r"\d", k) or "unway" in k or "ash" in k for k in koppen), koppen


# ── één telling voor open vragen ────────────────────────────────────────────

def test_open_vragen_tellen_gelijk_met_open_questions(server, dorp):
    sd = stand(_st(dorp))
    totaal = len(sd["alle"])
    assert totaal > 0
    _s, today = server("/today", "lid@t.nl")
    _s, oq = server("/open-questions", "lid@t.nl")
    assert f"<b>{totaal} open</b>" in today
    t = sd["telling"]
    from nooch_village import wiki_dekking as dek
    assert (f"{t[dek.CONFLICT]} in conflict, {t[dek.ONGECHECKT]} unchecked, {t[dek.LEEG]} open, "
            f"{t[dek.UITGESTELD]} deferred") in oq
    assert f"{sd['paginas']} page" in today


def test_de_vragen_voor_jouw_rollen(dorp):
    """De houder van `Materials` bezit de vragen op pagina's die er nog niet zijn."""
    from nooch_village import bom_leveranciers, org
    st = _st(dorp)
    houder = org.role_for_domain(st.records.all(), bom_leveranciers.DOMEIN).id
    shoe = st.people.add("Schoen", "shoe@t.nl")
    st.assign.assign(houder, "person", shoe.id)
    httpd, sessies = _server(dorp)
    try:
        _s, h = _get(httpd, sessies, "/today", "shoe@t.nl")
        _s, ander = _get(httpd, sessies, "/today", "lid@t.nl")
    finally:
        httpd.shutdown()
    n = sum(k for rid, _naam, k in stand(_st(dorp))["per_eigenaar"] if rid == houder)
    assert n and f"<b>{n} for your roles</b>" in h
    assert "for your roles" not in ander


# ── lege toestanden ─────────────────────────────────────────────────────────

def test_lege_toestanden(tmp_path):
    dd = _testdorp(tmp_path, vragen=False, werk=False, doelen=False)
    httpd, sessies = _server(dd)
    try:
        _s, h = _get(httpd, sessies, "/today", "lid@t.nl")
    finally:
        httpd.shutdown()
    assert "Nothing open of your own." in h and "Nothing waits on you." in h
    assert "No open goals." in h
    # een Critical Number zonder waarde: "No data yet" met de volgende stap, nooit een nul
    # (CN3 mag 0 zijn: 0% gestaafd is een echte waarde. CN1 heeft nog GEEN waarde.)
    batch = h.split("Batch 4 sold", 1)[1].split("<div class='tile'>", 1)[0]
    assert "No data yet" in batch and "Not started — the batch opens" in batch
    assert "kpi-val" not in batch


def test_cn_zonder_waarde_noemt_de_volgende_stap_voor_finance(dorp):
    httpd, sessies = _server(dorp)
    try:
        _s, h = _get(httpd, sessies, "/today", "fc@t.nl")
    finally:
        httpd.shutdown()
    tegel = h.split("Runway (months)", 1)[1].split("<div class='tile'>", 1)[0]
    assert "No data yet" in tegel and "Missing: cash bunq" in tegel and "href='/fixed-costs'" in tegel


# ── niet in zoekindex, context of Noochie ───────────────────────────────────

def test_today_komt_niet_in_zoekindex_context_of_noochie(dorp):
    """Zoeken, de rolcontext en Noochie lezen uit de stores, niet uit pagina's. Deze toets houdt dat
    zo: een Finance-getal dat op /today staat (voor de FC) duikt daar nergens op, en /today zelf is
    geen zoekresultaat."""
    from nooch_village import artefacts, noochie_memo
    from nooch_village.views.search import render_search_fragment
    _vul(dorp, bunq=43210, mollie=1000, tax=500, payables=250, kosten=2000)
    st = _st(dorp)
    assert "43210" not in render_search_fragment(st, "43210")
    assert "/today" not in render_search_fragment(st, "today")
    for rol in (r.id for r in st.records.all()):
        assert "43210" not in artefacts.render_context_markdown(
            artefacts.serialize_context(rol, st.records, st.att))
    beeld, rapport = noochie_memo.verzamel(dorp)
    assert "43210" not in repr(beeld) + repr(rapport)


def test_lege_toestand_open_vragen(dorp, monkeypatch):
    """Een gebootstrapt dorp heeft altijd open vragen (de stuklijst van de modellen staat vast); de
    lege toestand toetsen we daarom op het blok zelf, met een lege `stand`."""
    from nooch_village.views import open_vragen, today
    from nooch_village import wiki_dekking as dek
    monkeypatch.setattr(open_vragen, "stand", lambda st: {
        "alle": [], "telling": {s: 0 for s in open_vragen.STATUSSEN}, "paginas": 0, "per_eigenaar": []})
    h = today._open_vragen(_st(dorp), "")
    assert "No open questions" in h and "<b>0 open</b>" not in h
    assert dek.CONFLICT in open_vragen.STATUSSEN
