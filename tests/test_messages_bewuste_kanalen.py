"""De kanalenlijst van Messages: vier vaste lagen en één die je zelf vult (21 september 2026).

WAT ERVOOR IN DE PLAATS KOMT, en waarom dit geen aanscherping van het oude model is. Elk project
met een gesprek WAS een kanaal — 123 op productie, plus 42 DM's. De cap van 25 uit punt 1a maakte
dat zichtbaar ("25 of 159 · search for the rest") zonder het op te lossen: je scrolde nog steeds
langs namen die je niet zocht, alleen minder lang.

    General    het kanaal van de wortelcirkel — het hele dorp, altijd zichtbaar
    Goals      één per open doel; dezelfde taxonomie die het bord al gebruikt
    Channels   losse kanalen die een mens aanmaakt
    Projects   ALLEEN wat jij volgt; leeg tot je iets toevoegt
    Direct     ongewijzigd

VIJF EIGENSCHAPPEN MOETEN HARD ZIJN, en dit bestand toetst ze in die volgorde:

  1. Projects is leeg tot je iets toevoegt, en openen IS toevoegen;
  2. uit je lijst halen kan, en raakt het gesprek niet aan;
  3. zoeken ziet alles — anders is een project dat je niet volgt onvindbaar, en dat is de enige
     manier waarop deze wijziging iets kapot zou maken;
  4. de vaste lagen staan er zonder dat iemand ze aanmaakt;
  5. de andere cirkel valt samen met General tot hij actief wordt, maar wordt nooit onbereikbaar.
"""
from __future__ import annotations

import re

from nooch_village import channels, cockpit2
from nooch_village.views.messages import _kanalen, render_messages

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path, projecten: int = 4):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Lijst Tester", "lijst@test.nl")
    pids = []
    for i in range(projecten):
        pid = st.projects.create(OWNER, f"Project {i} mycelium", "human", status="running")
        st.projects.add_feed_entry(pid, f"bericht {i}", kind="comment",
                                   author_type="human", author_id=ik.id)
        pids.append(pid)
    return dd, st, ik.id, pids


def _namen(html: str) -> list[str]:
    return re.findall(r"class='msg-knaam'>([^<]+)</span>", html)


# ── 1. Projects vult zich alleen door jou ────────────────────────────────────
def test_projects_begint_leeg(tmp_path):
    """DE KERN VAN DE VERVANGING. Vier projecten met een gesprek, en nul in de lijst."""
    dd, st, ik, pids = _dorp(tmp_path)
    groepen, totaal, gevolgd = _kanalen(st, ik, "")
    assert groepen["Projects"] == []
    assert totaal["Projects"] == 4, "ze bestaan wel degelijk"
    assert gevolgd == set()


def test_openen_is_toevoegen(tmp_path):
    """Anders moet je een kanaal elke keer opnieuw opzoeken, en is "toevoegen" een tweede
    handeling voor iets wat je met je klik al zei."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.project_kanaal(pids[0])
    render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    assert st.people.volgt(ik, k) is True
    groepen, _t, _g = _kanalen(cockpit2._Stores(dd), ik, "")
    assert groepen["Projects"] == [k]


def test_de_lijst_stand_voegt_niet_toe(tmp_path):
    """Op een telefoon is `lijst=True` de kanalenlijst met de draad verborgen; het kanaal dat dan
    als voordeur is gekozen heb je niet geopend. Zelfde voorwaarde als bij `markeer_gezien` —
    zonder dat zou het openen van de LIJST iets aan je lijst toevoegen."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.project_kanaal(pids[0])
    render_messages(st, ik=ik, kanaal=k, csrf_token="t", lijst=True)
    assert st.people.volgt(ik, k) is False


def test_alleen_projecten_worden_gevolgd(tmp_path):
    """De andere soorten staan er sowieso. Ze volgen zou de lijst vervuilen met een begrip dat
    voor hen niets betekent."""
    dd, st, ik, pids = _dorp(tmp_path)
    d = st.doelen.add("Website live", label="Website")
    for k in (channels.goal_kanaal(d["id"]), channels.circle_kanaal("mother_earth")):
        render_messages(st, ik=ik, kanaal=k, csrf_token="t")
        assert st.people.volgt(ik, k) is False


# ── 2. En er weer uit ────────────────────────────────────────────────────────
def test_uit_je_lijst_halen_laat_het_gesprek_staan(tmp_path):
    """Het tegenwicht van "openen is toevoegen": zonder dit is één klik op een zoekresultaat een
    eenrichtingsdeur, en is de lijst binnen een week weer de muur die hij was."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.project_kanaal(pids[0])
    st.people.volg(ik, k)
    _nxt, msg = cockpit2.dispatch(dd, "kanaal_ontvolg",
                                  {"csrf": ["t"], "kanaal": [k], "next": ["/messages"]},
                                  username="lijst@test.nl")
    st2 = cockpit2._Stores(dd)
    assert st2.people.volgt(ik, k) is False
    assert len(st2.channels.trail(k)) == 1, "het gesprek is meegegaan"
    assert "removed from your list" in msg and "search to find it again" in msg


def test_de_knop_staat_er_alleen_als_hij_iets_doet(tmp_path):
    """Een knop die niets doet is erger dan geen knop. Alleen bij een project dat je volgt."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.project_kanaal(pids[0])
    assert "kanaal_ontvolg" not in render_messages(
        st, ik=ik, kanaal=channels.circle_kanaal("mother_earth"), csrf_token="t")
    assert "kanaal_ontvolg" in render_messages(st, ik=ik, kanaal=k, csrf_token="t")


def test_ontvolgen_zonder_mens_doet_niets(tmp_path):
    """Fail-closed op de identiteit: zonder herkende mens is er geen lijst om uit te halen."""
    dd, st, ik, pids = _dorp(tmp_path)
    _nxt, msg = cockpit2.dispatch(dd, "kanaal_ontvolg",
                                  {"csrf": ["t"], "kanaal": [channels.project_kanaal(pids[0])],
                                   "next": ["/messages"]}, username="guest")
    assert msg.startswith("✗")


# ── 3. Zoeken ziet alles ─────────────────────────────────────────────────────
def test_zoeken_toont_ook_wat_je_niet_volgt(tmp_path):
    """DE ENIGE MANIER WAAROP DIT IETS KAPOT ZOU MAKEN. Zou zoeken alleen je eigen lijst
    doorzoeken, dan is een project dat je nog niet hebt toegevoegd onvindbaar — en dan heb je geen
    rustiger lijst maar een verdwenen gesprek."""
    dd, st, ik, pids = _dorp(tmp_path)
    groepen, _t, gevolgd = _kanalen(st, ik, "mycelium")
    assert len(groepen["Projects"]) == 4 and gevolgd == set()


def test_een_niet_gevolgde_treffer_is_als_zodanig_herkenbaar(tmp_path):
    """Zonder merkteken zie je niet welke treffer al van jou is en welke je zou toevoegen. Twee
    dragers, want kleur alleen is nooit genoeg: een gestippelde rand én het woord "add"."""
    dd, st, ik, pids = _dorp(tmp_path)
    st.people.volg(ik, channels.project_kanaal(pids[0]))
    html = render_messages(st, ik=ik, csrf_token="t", q="mycelium")
    assert html.count("msg-kanaal--vreemd") == 3          # de drie die hij niet volgt
    assert html.count("msg-add") == 3
    assert len(_namen(html)) >= 4


# ── 4. De vaste lagen ────────────────────────────────────────────────────────
def test_general_en_de_doelen_staan_er_zonder_dat_iemand_ze_aanmaakt(tmp_path):
    dd, st, ik, pids = _dorp(tmp_path)
    for titel, label in (("De nieuwe website live", "Website"), ("Rapport MITH", "MITH")):
        st.doelen.add(titel, label=label)
    groepen, _t, _g = _kanalen(cockpit2._Stores(dd), ik, "")
    assert groepen["General"] == [channels.circle_kanaal("mother_earth")]
    assert len(groepen["Goals"]) == 2
    html = render_messages(cockpit2._Stores(dd), ik=ik, csrf_token="t")
    assert "General" in _namen(html) and "Website" in _namen(html) and "MITH" in _namen(html)


def test_de_wortelcirkel_heet_general_en_niet_mother_earth(tmp_path):
    """Wie dit kanaal zoekt, zoekt "algemeen" — niet de naam van de cirkel die toevallig bovenaan
    staat. De cirkel houdt zijn naam overal elders."""
    from nooch_village.views.messages import _label
    dd, st, ik, pids = _dorp(tmp_path)
    assert _label(st, channels.circle_kanaal("mother_earth"), ik) == "General"
    assert _label(st, channels.circle_kanaal("mother_earth__nooch"), ik) == "Nooch"


def test_een_gesloten_doel_valt_uit_de_lijst_maar_niet_uit_de_data(tmp_path):
    dd, st, ik, pids = _dorp(tmp_path)
    d = st.doelen.add("Klaar project", label="Klaar")
    k = channels.goal_kanaal(d["id"])
    st.channels.post(k, "iets gezegds", author_id=ik)
    st.doelen.update(d["id"], status="behaald")
    groepen, _t, _g = _kanalen(cockpit2._Stores(dd), ik, "")
    assert k not in groepen["Goals"]
    assert len(cockpit2._Stores(dd).channels.trail(k)) == 1


# ── 5. De tweede cirkel ──────────────────────────────────────────────────────
def test_de_tweede_cirkel_valt_samen_met_general_zolang_hij_leeg_is(tmp_path):
    """Besluit Stefan: samenvoegen met General, geen eigen rij — "trekken we er weer uit als die
    cirkel ooit actief wordt"."""
    dd, st, ik, pids = _dorp(tmp_path)
    groepen, _t, _g = _kanalen(st, ik, "")
    assert channels.circle_kanaal("mother_earth__nooch") not in groepen["Channels"]
    assert groepen["General"] == [channels.circle_kanaal("mother_earth")]


def test_maar_hij_wordt_nooit_onbereikbaar(tmp_path):
    """"Actief" is hier een VERGELIJKING en geen code-wijziging: zodra er iets in staat verschijnt
    hij onder Channels. Zonder deze regel zou een gesprek onbereikbaar worden doordat een lijst hem
    niet noemt — precies het soort stille verdwijning waar de rest van dit bestand tegen bewaakt."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth__nooch")
    st.channels.post(k, "de tweede cirkel begint te leven", author_id=ik)
    groepen, _t, _g = _kanalen(cockpit2._Stores(dd), ik, "")
    assert k in groepen["Channels"]


def test_de_voordeur_is_altijd_general(tmp_path):
    """DE REGEL WAS "OPEN OP IETS DAT GEZEGD IS", en dat leverde op productie een landing op in
    `dm:Candy Cotton|…` — een willekeurige DM, alfabetisch eerste van de 35 die allemaal een
    bericht hadden. Gemeten bij een klik-doorloop, niet beredeneerd.

    Ongevraagd in andermans privégesprek landen is het probleem; "meest recent actief" lost dat
    niet op, want dat kan net zo goed weer een DM zijn. General is in dit hele traject de voordeur
    van het dorp (besluit Stefan, 21 september 2026)."""
    dd, st, ik, pids = _dorp(tmp_path, projecten=1)
    st.doelen.add("Website live", label="Website")
    st2 = cockpit2._Stores(dd)

    # Er staat van alles: een project met een gesprek, een doel met een gesprek, een DM.
    st2.channels.post(channels.goal_kanaal(st2.doelen.all()[0]["id"]), "druk hier", author_id=ik)
    ander = st2.people.add("Ander Mens", "ander@test.nl")
    st2.channels.post(channels.dm_kanaal(ik, ander.id), "hoi", author_id=ander.id)
    st2.people.volg(ik, channels.project_kanaal(pids[0]))

    st3 = cockpit2._Stores(dd)
    kop = re.search(r"class='msg-kop'>([^<]*)", render_messages(st3, ik=ik, csrf_token="t"))
    assert kop and kop.group(1) == "General", "je landt in een ander gesprek dan het dorpskanaal"


def test_je_landt_nooit_ongevraagd_in_een_dm(tmp_path):
    """DE GUARD, in de vorm waarin het misging. Niet "de voordeur is General" maar "de voordeur is
    geen privégesprek" — die tweede overleeft ook een toekomstige herschikking van de volgorde."""
    dd, st, ik, pids = _dorp(tmp_path, projecten=0)
    ander = st.people.add("Ander Mens", "ander@test.nl")
    # Een DM die alfabetisch vóór alles komt, precies zoals "Candy Cotton" dat deed.
    st.channels.post(channels.dm_kanaal("Aaa Eerste", ik), "iets persoonlijks", author_id=ik)
    st2 = cockpit2._Stores(dd)
    html = render_messages(st2, ik=ik, csrf_token="t")
    assert "iets persoonlijks" not in html
    kop = re.search(r"class='msg-kop'>([^<]*)", html)
    assert kop and kop.group(1) == "General"


# ── 6. Rol- en systeemafzenders staan niet tussen je gesprekken ──────────────
#
# GEMETEN OP PRODUCTIE: 42 DM-kanalen, waarvan 2 een echt gesprek tussen twee mensen. De andere
# 40 dragen een ROL of een systeemnaam als tegenpartij (`compliance`, `claims-checker`, `dialoog`,
# `Lara the Librarian`) — overblijfsels van de inbox-migratie. Die lezen geen berichten, en ze
# stonden tussen de twee gesprekken die dat wél zijn.
#
# DIT IS EEN WEERGAVE EN GEEN MIGRATIE. Er lag een voorstel voor een vijfde kanaalsoort
# `role:<record_id>`; dat is in dezelfde implementatiebrief weer ingetrokken ("vervalt, niet meer
# nodig nu er altijd een mens als DM-ontvanger is"). Dat argument staat nog. Wat overbleef is een
# lijst-probleem, en dat wordt hier opgelost — zonder één kanaal-id te verplaatsen.

def test_een_rol_als_tegenpartij_hoort_niet_bij_direct(tmp_path):
    from nooch_village.views.messages import _dm_groepen
    dd, st, ik, pids = _dorp(tmp_path)
    mens = st.people.add("Echte Collega", "collega@test.nl")
    st.channels.post(channels.dm_kanaal(ik, mens.id), "hoi", author_id=ik)
    st.channels.post(channels.dm_kanaal(ik, "compliance"), "scan af", author_id="compliance")
    st.channels.post(channels.dm_kanaal(ik, "claims-checker"), "3 claims", author_id="claims-checker")
    st2 = cockpit2._Stores(dd)
    direct, rollen = _dm_groepen(st2, ik)
    # NIET MEER OP AANTAL. Direct bevat sinds 22 september ook een lege rij per mens in het dorp;
    # waar het hier om gaat is de SPLITSING: de mens staat erin, de twee rollen niet.
    assert channels.dm_kanaal(ik, mens.id) in direct
    assert channels.dm_kanaal(ik, "compliance") not in direct
    assert channels.dm_kanaal(ik, "claims-checker") not in direct
    assert len(rollen) == 2


def test_een_afzender_op_NAAM_of_E_MAIL_blijft_een_mens(tmp_path):
    """DE RIJEN DIE STEFAN ZELF BEOORDEELT. Drie kanalen dragen een persoonsnaam ("Stefan Wobben",
    2x) of een e-mailadres ("stefan@nooch.earth") als afzender-id in plaats van een persoon-id.
    Op id alleen beoordelen zou ze bij het systeem zetten, en dan verdwijnen ze uit het zicht
    vóórdat hij ernaar heeft kunnen kijken."""
    from nooch_village.views.messages import _dm_groepen, _is_mens
    dd, st, ik, pids = _dorp(tmp_path)
    # Een NIEUWE naam, want `people.add` dedupliceert op naam: bestond "Stefan Wobben" al (uit de
    # bootstrap), dan krijg je die terug zónder dat het e-mailadres wordt gezet, en dan meet deze
    # test niets. Zelfde soort meetfout als de lege `_namen()`-regex van fase 11.
    mens = st.people.add("Twijfel Tester", "twijfel@test.nl")
    assert mens.email == "twijfel@test.nl", "de proefpersoon kreeg geen e-mailadres"
    assert _is_mens(st, mens.id) and _is_mens(st, "Twijfel Tester") and _is_mens(st, "twijfel@test.nl")
    assert not _is_mens(st, "compliance") and not _is_mens(st, "")
    for tegen in ("Twijfel Tester", "twijfel@test.nl"):
        st.channels.post(channels.dm_kanaal(ik, tegen), "iets", author_id=tegen)
    st2 = cockpit2._Stores(dd)
    direct, rollen = _dm_groepen(st2, ik)
    # Op de twee kanalen zelf en niet op het aantal: Direct draagt nu ook lege rijen (22 sept).
    for tegen in ("Twijfel Tester", "twijfel@test.nl"):
        assert channels.dm_kanaal(ik, tegen) in direct
    assert rollen == []


def test_een_notitie_aan_jezelf_blijft_direct(tmp_path):
    """Een kanaal met jezelf bestaat echt (op prod één). Dat is een notitie aan jezelf, geen
    systeemafzender."""
    from nooch_village.views.messages import _dm_groepen
    dd, st, ik, pids = _dorp(tmp_path)
    st.channels.post(channels.dm_kanaal(ik, ik), "onthouden", author_id=ik)
    direct, rollen = _dm_groepen(cockpit2._Stores(dd), ik)
    # Het kanaal met jezelf staat er ÉÉN keer in: het bestaat al, dus het aanvullen met lege
    # rijen (22 sept) mag er geen tweede van maken — daarom `count` en niet `in`.
    assert direct.count(channels.dm_kanaal(ik, ik)) == 1
    assert rollen == []


def test_de_rolkanalen_staan_niet_meer_in_de_lijst_maar_wel_in_de_data(tmp_path):
    """DEZE TEST EISTE DE GROEP OP HET SCHERM, en die is er op 22 september 2026 uit (eis Stefan):
    "Roles & system verbergen, niet wissen". Een dag eerder was de groep zelf de verbetering —
    37 rol-afzenders uit Direct — en nu blijkt dat je die 37 regels ook gewoon niet wilt zien.

    De helft die telde is onveranderd, en dat is wat deze test nu bewaakt: het gesprek staat er
    nog, precies zoals het stond. Verbergen is geen migratie."""
    dd, st, ik, pids = _dorp(tmp_path)
    st.channels.post(channels.dm_kanaal(ik, "compliance"), "scan af", author_id="compliance")
    st2 = cockpit2._Stores(dd)
    html = render_messages(st2, ik=ik, csrf_token="t")
    assert "Roles &amp; system" not in html and "Roles & system" not in html
    # en het gesprek zelf is onaangeroerd — dit is een weergave, geen migratie
    assert len(st2.channels.trail(channels.dm_kanaal(ik, "compliance"))) == 1


# ── 7. Reacties in Messages ─────────────────────────────────────────────────
def test_een_bericht_in_een_kanaal_kan_een_reactie_dragen(tmp_path):
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    e = st.channels.post(k, "iets gezegds", author_id=ik)
    _nxt, msg = cockpit2.dispatch(dd, "react_add", {
        "csrf": ["t"], "kanaal": [k], "item": [e["id"]], "emoji": ["👍"], "next": ["/messages"]},
        username="lijst@test.nl")
    assert "geplaatst" in msg
    assert cockpit2._Stores(dd).channels.trail(k)[0]["reactions"] == {"👍": 1}


def test_een_reactie_op_een_projectkanaal_landt_op_het_project(tmp_path):
    """REFERENCE, DON'T COPY. Een projectkanaal IS `project["log"]` — dezelfde regel die de
    projectfeed toont. Een reactie daarop hoort dus op het project te staan en niet een tweede
    keer in `channels.json`, anders zie je 'm op de ene pagina wel en op de andere niet."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.project_kanaal(pids[0])
    eid = st.projects.get(pids[0])["log"][0]["id"]
    cockpit2.dispatch(dd, "react_add", {
        "csrf": ["t"], "kanaal": [k], "item": [eid], "emoji": ["🎉"], "next": ["/messages"]},
        username="lijst@test.nl")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pids[0])["log"][0]["reactions"] == {"🎉": 1}
    import json
    import os
    pad = f"{dd}/channels.json"
    ruw = json.load(open(pad)) if os.path.exists(pad) else {}
    assert k not in (ruw.get("kanalen") or {}), "de reactie is óók in channels.json beland"


def test_de_kiezer_is_hetzelfde_component_als_in_de_projectfeed(tmp_path):
    """Zou Messages zijn eigen emoji-lijst krijgen, dan is de ene na één wijziging langer dan de
    andere zonder dat iemand het merkt."""
    from nooch_village.views.feed import _EMOJIS_FULL
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    st.channels.post(k, "iets", author_id=ik)
    html = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="t")
    assert "emoji-pick" in html and "emo-grid" in html
    assert html.count("value='react_add'") == len(_EMOJIS_FULL)


def test_zonder_schrijfsessie_geen_kiezer(tmp_path):
    """Fail-closed: geen csrf = geen knop die straks afketst."""
    dd, st, ik, pids = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    st.channels.post(k, "iets", author_id=ik)
    html = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="")
    assert "emoji-pick" not in html


def test_een_bericht_zonder_id_draagt_geen_reactie(tmp_path):
    """Het oude schema. Een knop die niets kan raken hoort er niet te staan."""
    from nooch_village.views.feed import reactie_blok
    rx, picker = reactie_blok({"text": "oud"}, "t", {"kanaal": "x"})
    assert rx == "" and picker == ""
