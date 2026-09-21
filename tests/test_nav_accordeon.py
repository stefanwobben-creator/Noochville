"""De navigatiebalk als accordeon (21 september 2026).

WAT ER VERANDERT. PR, ME en CI waren paginasprongen: je verliet het scherm waar je mee bezig was
om een lijst te zien, koos iets, en kwam ergens anders uit. Nu klapt die lijst open NAAST de balk.
WI en AD blijven een sprong — daar kies je niets uit een lijst. Erbij: een ZOEK-knop bovenaan, en
onderaan twee directe knoppen naar Werkoverleg en Roloverleg.

VIJF DINGEN MOETEN HARD ZIJN:

  1. de balk blijft VERTICAAL op elke schermbreedte (expliciet besluit, tegen de standaardreflex in);
  2. Werkoverleg en Roloverleg zijn geen kanaal en geen paneel maar een directe knop;
  3. het paneel rendert bestaande data — geen tweede lijst naast die van Messages of Projects;
  4. het paneel komt pas als je klikt, niet met elke pageload;
  5. zonder JS blijft elke knop een werkende link.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import channels, cockpit2
from nooch_village.cockpit2_util import _nav
from nooch_village.views.navpaneel import render_nav_paneel

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Paneel Tester", "paneel@test.nl")
    st.assign.assign(OWNER, "person", mens.id)
    for i in range(3):
        pid = st.projects.create(OWNER, f"Project {i} mycelium", "human", status="running")
        st.projects.add_feed_entry(pid, f"bericht {i}", kind="comment",
                                   author_type="human", author_id=mens.id)
    st.doelen.add("De nieuwe website live", label="Website")
    return dd, cockpit2._Stores(dd), mens.id


# ── 1. De balk ───────────────────────────────────────────────────────────────
def test_de_balk_klapt_nooit_om_naar_horizontaal():
    """DE STANDAARDREFLEX IS HIER DE VERKEERDE, en hij stond er: onder 760px kreeg `.c2-side`
    `flex-direction:row` en werd de zijbalk een rij boven de inhoud. Dat maakt van één
    navigatiemodel twee — precies wat fase 7 opruimde — en de accordeon heeft een verticale balk
    nodig om een paneel naast te kunnen zetten. Smal betekent: de balk krimpt, het paneel gaat
    eronder."""
    smal = CSS.split("@media(max-width:760px)")
    assert len(smal) > 1
    blok = "".join(smal[1:])
    zijbalk = [r for r in re.findall(r"([^{}]*)\{([^{}]*)\}", blok) if ".c2-side{" in r[0] + "{"]
    assert zijbalk, "geen smalle-schermregel voor de zijbalk gevonden"
    for _sel, body in zijbalk:
        assert "flex-direction:row" not in body.replace(" ", ""), "de balk klapt om naar horizontaal"


def test_de_knoppen_die_een_paneel_openen_en_die_dat_niet_doen():
    h = _nav()
    for sleutel in ("zoek", "pr", "me", "ci"):
        assert f"data-nav-paneel='{sleutel}'" in h, sleutel
    # WI en AD springen gewoon naar hun pagina: daar kies je niets uit een lijst, en een
    # tussenlijst is dan een extra klik zonder winst.
    wi = h.split("/wiki")[1][:120]
    assert "data-nav-paneel" not in wi
    ad = h.split("/admin")[1][:120]
    assert "data-nav-paneel" not in ad
    assert "Inbox" not in h                       # verwijderd in #531, komt niet terug


def test_elke_paneelknop_blijft_zonder_js_een_werkende_link():
    """Zonder deze regel is de balk bij een JS-fout een rij dode elementen. De knop draagt zijn
    href, en `preventDefault` gebeurt pas als het paneel echt opengaat."""
    h = _nav()
    for sleutel, href in (("zoek", "/search"), ("pr", "/projects"),
                          ("me", "/messages"), ("ci", "/node")):
        stuk = h.split(f"data-nav-paneel='{sleutel}'")[0][-160:]
        assert f"href='{href}'" in stuk, f"{sleutel} heeft geen val-terug-link"
    assert "e.preventDefault()" in JS


def test_de_twee_overleggen_zijn_geen_kanaal_en_geen_paneel():
    """CORRECTIE OP HET PROTOTYPE (Stefan, 21 september 2026): Werkoverleg en Roloverleg stonden
    daar eerst als kanaal. Het zijn twee bestaande schermen; één klik, geen lijst ervoor."""
    h = _nav()
    for href in ("/werkoverleg", "/roloverleg2"):
        assert f"class='c2-overleg' href='{href}'" in h
        stuk = h.split(href)[1][:160]
        assert "data-nav-paneel" not in stuk
    # en ze staan los van de PR/ME/WI/CI/AD-groep, onder een eigen scheiding
    assert h.index("c2-subnav-div") < h.index("c2-overleg")


# ── 2. Eén paneel tegelijk, en dicht met dezelfde knop ───────────────────────
def test_het_paneel_gedraagt_zich_als_een_accordeon():
    assert 'if (open === sleutel) { sluit(); return; }' in JS      # nogmaals = sluiten
    assert 'k === knop ? "true" : "false"' in JS                   # precies één aria-expanded
    assert '"Escape"' in JS                                        # en met het toetsenbord dicht


def test_het_paneel_staat_leeg_in_de_pagina():
    """LAZY, en dat is de hele reden dat het een route is. Zou de inhoud meekomen met elke
    pageload, dan betaalt élk scherm voor een projectlijst (442) en een kanalenlijst (123) die je
    meestal niet opent."""
    h = _nav()
    leeg = h.split("id='c2-paneel-in'")[1].split("</aside>")[0]
    assert leeg.strip() in (">", "></div>"), f"het paneel draagt al inhoud: {leeg[:80]!r}"
    assert "/nav-paneel?p=" in JS


# ── 3. Wat de panelen tonen is bestaande data ────────────────────────────────
def test_het_messages_paneel_is_dezelfde_lijst_als_het_scherm(tmp_path):
    """EEN RENDER-PLEK-WIJZIGING, GEEN NIEUWE LIJST. Zou dit paneel zijn eigen kanalenlijst
    opbouwen, dan geeft "wat staat er in mijn lijst" twee antwoorden zodra er aan één iets
    verandert."""
    from nooch_village.views.messages import _kanalen
    dd, st, ik = _dorp(tmp_path)
    st.people.volg(ik, channels.project_kanaal(st.projects.all()[0]["id"]))
    st2 = cockpit2._Stores(dd)
    groepen, _t, _g = _kanalen(st2, ik, "")
    h = render_nav_paneel(st2, "me", ik)
    assert "General" in h and "Website" in h
    for k in groepen["Projects"]:
        assert f"k={channels.PROJECT}" in h.replace("%3A", "=")   # het gevolgde project staat erin
    assert h.count("c2-prij") == sum(len(r) for r in groepen.values())


def test_het_projects_paneel_opent_op_mijn_projecten(tmp_path):
    """Standaard "mijn projecten", met dezelfde definitie als de persoon-lens: een project is van
    jou als zijn eigenaar-rol door jou wordt vervuld. Een tweede definitie zou hier stilletjes een
    andere lijst geven dan op je eigen pagina."""
    dd, st, ik = _dorp(tmp_path)
    mijn = render_nav_paneel(st, "pr", ik)
    assert "My projects" in mijn and mijn.count("c2-prij") == 3
    # een mens zonder rollen ziet bij "mijn" niets, en bij "alle" alles
    vreemd = st.people.add("Zonder Rol", "zonder@test.nl")
    assert render_nav_paneel(st, "pr", vreemd.id).count("c2-prij") == 0
    assert render_nav_paneel(st, "pr", vreemd.id, welke="alle").count("c2-prij") == 3


def test_het_circle_paneel_meldt_een_rol_zonder_vervuller(tmp_path):
    """"open — nobody" is informatie. Een lege regel laat het lezen als een weergavefout."""
    dd, st, ik = _dorp(tmp_path)
    h = render_nav_paneel(st, "ci", ik)
    assert "c2-prij" in h and "open — nobody" in h
    assert "Paneel Tester" in h                    # en wie wél vervult staat erbij


def test_een_onbekend_paneel_geeft_niets(tmp_path):
    """Fail-closed: geen gok, geen foutpagina in een fragment dat in een open scherm wordt gezet."""
    dd, st, ik = _dorp(tmp_path)
    assert render_nav_paneel(st, "bestaat-niet", ik) == ""
    assert render_nav_paneel(st, "", ik) == ""


# ── 4. Zoeken in het paneel ──────────────────────────────────────────────────
def test_het_zoekpaneel_gebruikt_de_bestaande_zoekmachine(tmp_path):
    """GEEN TWEEDE ZOEKMACHINE. `views/search.py` doorzoekt al tien bronnen met per groep een
    eigen fail-soft. Een tweede index zou een tweede antwoord geven op "wat is vindbaar"."""
    dd, st, ik = _dorp(tmp_path)
    assert "Type to search" in render_nav_paneel(st, "zoek", ik)        # drempel van 2 tekens
    h = render_nav_paneel(st, "zoek", ik, q="mycelium")
    assert "gs-group" in h and "Projects" in h


def test_zoeken_vindt_een_kanaal_op_zijn_naam(tmp_path):
    """HET GAT DAT DICHTGING. `_gesprekken` zocht in de TEKST van berichten: zoek je op "Website",
    dan vond je berichten waarin dat woord viel, maar niet het Website-kanaal zelf — en dat is
    meestal precies wat je zocht. Doel- en losse kanalen vielen er helemaal buiten."""
    from nooch_village.views.search import _zoek
    dd, st, ik = _dorp(tmp_path)
    res = dict(_zoek(st, ["website"])[0])
    assert [h["titel"] for h in res["Channels"]] == ["Website"]
    assert res["Channels"][0]["url"].startswith("/messages?k=goal:")


def test_een_dm_blijft_buiten_de_zoek(tmp_path):
    """Een privégesprek doorzoekbaar maken voor iedereen die is ingelogd is geen zoekfunctie maar
    een lek. Dat gold al voor de berichten; het geldt net zo voor de NAAM van het gesprek."""
    from nooch_village.views.search import _zoek
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Geheime Vriend", "geheim@test.nl")
    st.channels.post(channels.dm_kanaal(ik, ander.id), "iets vertrouwelijks", author_id=ik)
    st2 = cockpit2._Stores(dd)
    for term in ("geheime", "vertrouwelijks"):
        res = dict(_zoek(st2, [term])[0])
        assert res["Channels"] == [] and res["Messages"] == [], term
