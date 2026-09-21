"""De live-join-knop en de herstructurering van het verwerkscherm (21 september 2026).

TWEE DINGEN, ÉÉN BEURT, want ze raken hetzelfde overleg.

1. LIVE-JOIN. Draait er een werkoverleg, dan wordt de knop in de balk "Join meeting" met een
   pulserend groen rondje. Polling, geen websocket — en de reden staat in de meting: de vraag
   kost 0,31 ms zolang je alleen de store bouwt die hem kan beantwoorden, tegen 70 ms voor alle
   stores samen. Alleen werkoverleg: roloverleg heeft geen open/dicht-staat (besluit Stefan).

2. HET VERWERKSCHERM. De spanning krijgt een band bovenaan in plaats van een klein uitklapje, en
   de Volgende/In-afwachting-keuze komt terug — schrijvend naar het PROJECT, niet naar een eigen
   veld op de uitkomst. Die keuze is op 29 augustus weggehaald omdat hij een tweede plek was die
   de wachtstatus bijhield; dat bezwaar is niet vervallen, alleen de oplossing van toen.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2
from nooch_village.cockpit2_util import overleg_items
from nooch_village.views.vangst import _spanning_titel, _uitkomst_formulier

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()

CIRCLE = "mother_earth__nooch"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Secretaris", "sec@test.nl")
    # De uitkomst-poort laat alleen de rolvervuller of de Circle Lead door. Zonder deze toewijzing
    # test je de poort en niet de wachtstand.
    st.assign.assign("mother_earth__nooch__creator_of_shoes", "person", mens.id)
    return dd, cockpit2._Stores(dd), mens


# ── 1. De live-knop ──────────────────────────────────────────────────────────
def test_de_knop_verandert_pas_als_er_echt_een_overleg_draait():
    dicht = overleg_items(CIRCLE)
    assert "Werk&shy;overleg" in dicht and "Join meeting" not in dicht
    open_ = overleg_items(CIRCLE, werk_open=True)
    assert "Join meeting" in open_ and "c2-overleg--live" in open_


def test_het_rondje_is_nooit_de_enige_drager():
    """Kleur alleen is nooit genoeg: een groen stipje is onzichtbaar in zwart-wit en voor wie
    groen niet ziet. De TEKST verandert mee, en het stipje draagt `aria-hidden` omdat het niets
    toevoegt voor wie het voorgelezen krijgt."""
    h = overleg_items(CIRCLE, werk_open=True)
    assert "Join meeting" in h                       # de tweede drager
    assert "<span class='c2-live' aria-hidden='true'></span>" in h


def test_alleen_het_werkoverleg_wordt_live():
    """Roloverleg heeft geen open/dicht-staat — zijn agenda is een lijst governance-voorstellen.
    Die staat erbij bouwen is een eigen klus en valt buiten deze ronde (besluit Stefan)."""
    h = overleg_items(CIRCLE, werk_open=True)
    rol = h.split("/roloverleg2")[1]
    assert "Join meeting" not in rol and "c2-live" not in rol


def test_de_pulse_gaat_uit_voor_wie_geen_beweging_wil():
    """Het stipje blijft staan, alleen het kloppen stopt — er gaat dus geen informatie verloren.
    Zelfde regel als bij `.ck-item.bezig`."""
    blok = "".join(CSS.split("@media (prefers-reduced-motion: reduce)")[1:])
    assert ".c2-live{animation:none}" in blok.replace(" ", "")


def test_de_poller_gedraagt_zich():
    """Drie dingen die een poller beschaafd houden: niets vragen als het tabblad verborgen is,
    bij een fout het interval verdubbelen in plaats van doorrammen, en niets vervangen als er
    niets veranderd is (anders verliest een knop die je aanwijst zijn hover)."""
    assert "document.hidden" in JS
    assert "wacht = Math.min(wacht * 2" in JS
    assert "if (nu === html) return;" in JS
    assert "visibilitychange" in JS


def test_de_poll_route_bouwt_niet_alle_stores():
    """DE HELE REDEN DAT DIT POLLING MAG ZIJN. Gemeten op productie: alle stores bouwen kost 70 ms
    per verzoek, `WerkoverlegStore(...).is_open()` 0,31 ms. Een poller die elke 20 seconden 70 ms
    serverwerk aanzet voor een ja/nee is geen polling maar een lek."""
    bron = (pathlib.Path(__file__).resolve().parents[1]
            / "nooch_village" / "cockpit2.py").read_text()
    blok = bron.split('if path == "/overleg-status":')[1].split("return")[0]
    # DE CODE, NIET DE UITLEG. De comment in dat blok NOEMT `_Stores(data_dir)` juist, om te
    # zeggen waarom het er niet staat. Een guard die zijn eigen verantwoording meetelt, verbiedt
    # de uitleg in plaats van de fout — dat is vandaag al drie keer gebeurd.
    code = "\n".join(r for r in blok.split("\n") if not r.lstrip().startswith("#"))
    assert "WerkoverlegStore" in code
    assert "_Stores(" not in code, "de poll-route bouwt alsnog alle stores"


def test_de_poll_route_faalt_closed(tmp_path):
    """Een onbekende cirkel, een kapot bestand: geen uitnodiging. Een knop die "Join meeting" zegt
    terwijl er niets draait, stuurt iemand een leeg scherm in."""
    assert overleg_items("") == ""
    assert "Join meeting" not in overleg_items(CIRCLE, werk_open=False)


# ── 2. De spanningsband ──────────────────────────────────────────────────────
def test_de_spanning_krijgt_een_band_en_geen_klein_regeltje(tmp_path):
    dd, st, mens = _dorp(tmp_path)
    it = {"id": "p1", "title": "FSC verloopt",
          "note": {"spanning": "De FSC-verklaring van Selco verloopt in november."}}
    h = _spanning_titel(st, CIRCLE, it, "TOK", "/x")
    assert "wo-band" in h
    assert "De FSC-verklaring van Selco verloopt in november." in h
    assert "wo-band-edit" in h                        # de bewerk-ingang, náást de tekst


def test_een_lege_band_zegt_wat_er_te_doen_is(tmp_path):
    """Leeg is een eigen toestand, geen leeg vlak — dat leest als een weergavefout."""
    dd, st, mens = _dorp(tmp_path)
    h = _spanning_titel(st, CIRCLE, {"id": "p1", "title": "t"}, "TOK", "/x")
    assert "nog geen spanning opgeschreven" in h
    assert "wo-band" in h


def test_de_band_vraagt_nog_steeds_niets(tmp_path):
    """DE REDEN DAT HET UITKLAPJE ER OOIT KWAM BLIJFT GELDEN: in een live overleg is er geen tijd
    om een spanning uit te schrijven, dus een groot invulvak bleef altijd leeg. De band TOONT; het
    tekstvak zit achter de potloodknop en springt niet vanzelf open."""
    dd, st, mens = _dorp(tmp_path)
    h = _spanning_titel(st, CIRCLE, {"id": "p1", "title": "t"}, "TOK", "/x")
    assert "<details class='wo-band-edit'>" in h      # dicht, geen `open`
    assert "<textarea" in h                           # het vak bestaat wel, achter de klik


def test_de_band_gebruikt_hetzelfde_opslagpad(tmp_path):
    """Alleen de INGANG is verplaatst. Eén actie, één opslagpad — anders ontstaat er een tweede
    waarheid over wat de spanningstekst is."""
    dd, st, mens = _dorp(tmp_path)
    h = _spanning_titel(st, CIRCLE, {"id": "p1", "title": "t"}, "TOK", "/x")
    assert h.count("value='vangst_tekst'") == 1


# ── 3. De status-keuze ───────────────────────────────────────────────────────
def test_de_keuze_staat_er_alleen_bij_een_project(tmp_path):
    dd, st, mens = _dorp(tmp_path)
    h = _uitkomst_formulier(st, CIRCLE, {"id": "abc", "title": "t"}, "TOK", "/x")
    rij = re.search(r"<div class='qadd-row wo-staat'[^>]*>", h)
    assert rij and " hidden>" in rij.group(0), "de keuze staat open bij een actie-uitkomst"
    assert "this.value!=='project'" in h


def test_in_afwachting_zet_het_project_op_blocked(tmp_path):
    """DE KERN VAN DE AFSPRAAK. De keuze schrijft naar de plek waar de waarheid al staat, niet
    naast die plek. Zou hij een eigen veld op de uitkomst zetten, dan houden twee plekken
    hetzelfde bij en lopen ze na een week uit de pas — precies waarom hij op 29 augustus wegging."""
    dd, st, mens = _dorp(tmp_path)
    it = st.werk.backlog_add(CIRCLE, "FSC verloopt", by_id=mens.id)
    voor = {p["id"] for p in st.projects.all()}
    cockpit2.dispatch(dd, "vangst_uitkomst", {
        "csrf": ["t"], "circle": [CIRCLE], "iid": [it["id"]], "otype": ["project"],
        "tekst": ["Nieuwe leverancier zoeken"], "rol": ["Creator of shoes"], "persoon": [""],
        "staat": ["wachtend"], "next": ["/x"]}, username="sec@test.nl")
    st2 = cockpit2._Stores(dd)
    nieuw = [p for p in st2.projects.all() if p["id"] not in voor]
    assert len(nieuw) == 1
    assert nieuw[0]["status"] == "blocked"
    assert "werkoverleg" in (nieuw[0].get("blocked_on") or "")
    # en geen tweede plek die hetzelfde bijhoudt
    uit = st2.werk.punt_get(CIRCLE, it["id"])["uitkomsten"][0]
    assert "staat" not in uit


def test_volgende_laat_het_project_gewoon_beginnen(tmp_path):
    dd, st, mens = _dorp(tmp_path)
    it = st.werk.backlog_add(CIRCLE, "FSC verloopt", by_id=mens.id)
    voor = {p["id"] for p in st.projects.all()}
    cockpit2.dispatch(dd, "vangst_uitkomst", {
        "csrf": ["t"], "circle": [CIRCLE], "iid": [it["id"]], "otype": ["project"],
        "tekst": ["Nieuwe leverancier zoeken"], "rol": ["Creator of shoes"], "persoon": [""],
        "staat": ["volgende"], "next": ["/x"]}, username="sec@test.nl")
    st2 = cockpit2._Stores(dd)
    nieuw = [p for p in st2.projects.all() if p["id"] not in voor]
    assert len(nieuw) == 1 and nieuw[0]["status"] != "blocked"


def test_een_wachtstand_op_een_governance_punt_doet_niets(tmp_path):
    """Die gaat naar het roloverleg en heeft daar zijn eigen agenda. Fail-closed: een keuze die
    nergens landt hoort ook niets te doen, ook niet als hij toch wordt meegepost."""
    dd, st, mens = _dorp(tmp_path)
    it = st.werk.backlog_add(CIRCLE, "Rol onduidelijk", by_id=mens.id)
    voor = {p["id"] for p in st.projects.all()}
    cockpit2.dispatch(dd, "vangst_uitkomst", {
        "csrf": ["t"], "circle": [CIRCLE], "iid": [it["id"]], "otype": ["governance"],
        "tekst": ["Domein toevoegen"], "rol": ["Creator of shoes"], "persoon": [""],
        "staat": ["wachtend"], "next": ["/x"]}, username="sec@test.nl")
    st2 = cockpit2._Stores(dd)
    assert {p["id"] for p in st2.projects.all()} == voor      # geen project, dus niets geblokkeerd
