"""Twee dingen in Messages (26 september 2026): het doel-kanaal weg, en kanalen opheffen.

DEEL 1 — DE AUTOMATISCHE KOPPELING DOEL → KANAAL IS WEG. Elk open doel kreeg vanzelf een
`goal:<id>`-kanaal in de lijst, op twee plekken gegenereerd (`views/messages.py` en
`views/search.py`). De onderbouwing was "de doel-taxonomie bestaat al, dus dit is dezelfde indeling
op een tweede plek" — en dat tweede is precies wat eraf moest: een gesprek ontstaat doordat iemand
het begint, niet doordat er elders een doel wordt aangemaakt.

Doelen ZELF blijven ongewijzigd: het model, `/goals`, `/goal`, de voortgang, het kritieke pad en
`doel_id` op een project. Alleen dit koppelpunt is weg. De SOORT `goal:` blijft ook bestaan — op
prod staan drie van die kanalen met zes berichten; hem uitknippen zou die op slag onleesbaar maken
in plaats van ze te laten uitdoven.

DEEL 2 — EEN KANAAL KAN WEER WEG. Er was alleen aanmaken (`maak_topic`) en jezelf eraf halen
(`ontvolg`, geen verwijdering). Alleen `topic:`, want de andere vier soorten zijn afgeleid van iets
dat blijft bestaan. Wie: de maker of de anchor-lead — de afweging staat bij
`cockpit2.mag_kanaal_verwijderen`.
"""
from __future__ import annotations

import inspect

from nooch_village import channels, cockpit2
from nooch_village.views import messages as mv
from nooch_village.views import search as sv
from nooch_village.views.messages import _kanalen, render_messages

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Kanaal Tester", "kanaal@test.nl")
    return dd, st, ik.id


def _ctx(st, dd, velden, username):
    return cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/messages",
                         form=velden, username=username, action="kanaal_verwijder", data_dir=dd)


def _verwijder(st, dd, kanaal, username):
    return cockpit2.ACTIONS["kanaal_verwijder"](_ctx(st, dd, {"kanaal": kanaal}, username))


# ══ DEEL 1: het doel-kanaal ══════════════════════════════════════════════════
def test_een_open_doel_levert_geen_kanaal_meer_op(tmp_path):
    """DE KERN. Twee open doelen, en nul kanalen ervoor in de lijst."""
    dd, st, ik = _dorp(tmp_path)
    st.doelen.add("Duizend paar schoenen")
    st.doelen.add("De nieuwe website live")
    groepen, totaal, _g = _kanalen(st, ik, "")
    assert "Goals" not in groepen, "de groep staat er nog"
    alle = [k for rij in groepen.values() for k in rij]
    assert not [k for k in alle if channels.soort_van(k) == channels.GOAL]
    assert "Goals" not in totaal


def test_zoeken_biedt_ze_ook_niet_meer_aan(tmp_path):
    """DE TWEEDE GENERATOR. `search.py` had zijn eigen kopie van dezelfde regel; laat je die
    staan, dan is een doel-kanaal uit de lijst weg maar via zoeken gewoon terug."""
    dd, st, ik = _dorp(tmp_path)
    st.doelen.add("Duizend paar schoenen mycelium")
    kanalen = sv._kanalen(st, ["mycelium"])
    assert not [h for h in kanalen if "goal:" in str(h)], kanalen
    assert "goal_kanaal(" not in inspect.getsource(sv), "search genereert nog doel-kanalen"


def test_geen_van_beide_bestanden_maakt_er_nog_een(tmp_path):
    """Eén generator overslaan is de hele wijziging ongedaan maken; ze voedden dezelfde lijst."""
    for mod in (mv, sv):
        assert "goal_kanaal(" not in inspect.getsource(mod), mod.__name__


def test_de_voordeur_valt_niet_om_zonder_die_groep(tmp_path):
    """`volgorde` liep langs de groepsnamen, en "Goals" stond ertussen. Een naam die niet meer
    bestaat is hier een KeyError, geen lege lijst."""
    dd, st, ik = _dorp(tmp_path)
    html = render_messages(st, ik=ik, kanaal="", csrf_token="t")
    assert "<h2 class='msg-kop'>" in html


# ── wat NIET verandert ───────────────────────────────────────────────────────
def test_doelen_zelf_blijven_bestaan(tmp_path):
    """SCOPE. "Doelen zelf (model, /goals, /goal, voortgang, kritieke pad, doel_id op projecten)
    blijft ongewijzigd, alleen dit koppelpunt naar Messages verdwijnt.\""""
    dd, st, ik = _dorp(tmp_path)
    d = st.doelen.add("Duizend paar schoenen")
    assert st.doelen.get(d["id"])["status"] == "open"
    assert [x["id"] for x in st.doelen.all()] == [d["id"]]


def test_de_soort_goal_bestaat_nog(tmp_path):
    """DRIE KANALEN MET ZES BERICHTEN OP PROD. Zou `goal:` uit `channels.py` of uit de lees- en
    labelpaden verdwijnen, dan zijn die op slag onleesbaar in plaats van uitdovend."""
    dd, st, ik = _dorp(tmp_path)
    d = st.doelen.add("Oud doel met gesprek")
    k = channels.goal_kanaal(d["id"])
    st.channels.post(k, "iets van vroeger", author_type="human", author_id=ik)
    assert channels.soort_van(k) == channels.GOAL
    assert mv.mag_kanaal_lezen(st, k, ik) is True
    assert mv._label(st, k, ik)
    assert len(st.channels.trail(k)) == 1


def test_een_bestaand_doelkanaal_is_nog_te_openen(tmp_path):
    """Hij staat nergens meer in een lijst, maar wie de link heeft komt er nog in."""
    dd, st, ik = _dorp(tmp_path)
    d = st.doelen.add("Oud doel met gesprek")
    k = channels.goal_kanaal(d["id"])
    st.channels.post(k, "hallo mycelium", author_type="human", author_id=ik)
    html = render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    assert "hallo mycelium" in html


# ══ DEEL 2: een kanaal opheffen ══════════════════════════════════════════════
def test_de_maker_kan_zijn_kanaal_opheffen(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Website Batch 4", door=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert msg.startswith("🗑")
    assert k not in st.channels.topics()
    assert st.channels.naam_van(k) == ""


def test_het_gesprek_gaat_mee(tmp_path):
    """Anders blijft er een naamloze trail in `channels.json` staan die nooit meer een kanaal
    wordt: onbereikbaar, maar wel in het bestand."""
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    st.channels.post(k, "eerste", author_type="human", author_id=ik)
    st.channels.post(k, "tweede", author_type="human", author_id=ik)
    _verwijder(st, dd, k, "kanaal@test.nl")
    assert st.channels.trail(k) == []
    vers = cockpit2._Stores(dd)
    assert vers.channels.trail(k) == [], "op schijf staat hij er nog"


def test_de_bevestiging_noemt_hoeveel_gesprek_meegaat(tmp_path):
    """Een kanaal met 30 berichten weggooien hoort er anders uit te zien dan een leeg kanaal."""
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    for i in range(3):
        st.channels.post(k, f"bericht {i}", author_type="human", author_id=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert "3 messages" in msg


def test_een_leeg_kanaal_noemt_geen_berichten(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Leeg", door=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert "message" not in msg


def test_een_bericht_is_enkelvoud(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Eentje", door=ik)
    st.channels.post(k, "hoi", author_type="human", author_id=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert "1 message " in msg + " " and "1 messages" not in msg


def test_hij_verdwijnt_uit_ieders_lijst(tmp_path):
    """Zonder dit blijft er in `people.json` een verwijzing staan naar iets dat niet meer bestaat.
    Onzichtbaar, en juist daarom vervuilt het stil."""
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Iemand Anders", "anders@test.nl")
    k = st.channels.maak_topic("Batch 4", door=ik)
    st.people.volg(ik, k)
    st.people.volg(ander.id, k)
    _verwijder(st, dd, k, "kanaal@test.nl")
    assert st.people.volgt(ik, k) is False
    assert st.people.volgt(ander.id, k) is False


def test_na_afloop_sta_je_op_de_lijst(tmp_path):
    """Terugsturen naar het kanaal dat je net ophief geeft een leeg scherm."""
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    nxt, _msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert nxt == "/messages"


# ── de poort ─────────────────────────────────────────────────────────────────
def test_een_ander_mag_het_niet(tmp_path):
    """AANMAKEN EN OPHEFFEN ZIJN NIET SYMMETRISCH. `topic_add` is iedereen-ingelogd omdat het
    niets overschrijft; verwijderen is onomkeerbaar en raakt andermans berichten."""
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Iemand Anders", "anders@test.nl")
    k = st.channels.maak_topic("Batch 4", door=ik)
    _nxt, msg = _verwijder(st, dd, k, ander.email)
    assert msg.startswith("✗")
    assert k in st.channels.topics(), "hij is tóch weg"


def test_de_anchor_lead_mag_het_wel(tmp_path):
    """DE TWEEDE SLEUTEL. Zonder deze is een kanaal van een vertrokken mens onverwijderbaar."""
    dd, st, ik = _dorp(tmp_path)
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    st.assign.assign("mother_earth__circle_lead", "person", baas.id)
    k = st.channels.maak_topic("Batch 4", door=ik)
    _nxt, msg = _verwijder(st, dd, k, baas.email)
    assert msg.startswith("🗑") and k not in st.channels.topics()


def test_een_circle_lead_van_een_andere_cirkel_niet(tmp_path):
    """"Eén van de Circle Leads" zou betekenen dat de lead van een willekeurige andere cirkel
    meebeslist over een kanaal dat hem niet aangaat. Een topic hángt nergens onder."""
    dd, st, ik = _dorp(tmp_path)
    lead = st.people.add("Nooch Lead", "noochlead@test.nl")
    st.assign.assign("mother_earth__nooch__circle_lead", "person", lead.id)
    k = st.channels.maak_topic("Batch 4", door=ik)
    _nxt, msg = _verwijder(st, dd, k, lead.email)
    assert msg.startswith("✗") and k in st.channels.topics()


def test_zonder_maker_alleen_de_anchor_lead(tmp_path):
    """FAIL-CLOSED. Een leeg `makers`-veld is onbekend, geen vrijbrief — anders is elk kanaal van
    vóór dat veld door iedereen op te heffen."""
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Naamloos", door="")
    assert st.channels.maker_van(k) == ""
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert msg.startswith("✗")
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    st.assign.assign("mother_earth__circle_lead", "person", baas.id)
    _nxt, msg = _verwijder(cockpit2._Stores(dd), dd, k, baas.email)
    assert msg.startswith("🗑")


def test_een_onbekende_mens_mag_niets(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    _nxt, msg = _verwijder(st, dd, k, "niemand@nergens.nl")
    assert msg.startswith("✗") and k in st.channels.topics()


# ── alleen losse kanalen ─────────────────────────────────────────────────────
def test_een_projectkanaal_kan_niet(tmp_path):
    """DIT IS `project["log"]` VIA DE LEDGER. Weggooien zou het projectgesprek zelf wissen, dat
    de projectpagina óók toont."""
    dd, st, ik = _dorp(tmp_path)
    pid = st.projects.create(OWNER, "Project mycelium", "human", status="running")
    st.projects.add_feed_entry(pid, "bericht", kind="comment", author_type="human", author_id=ik)
    k = channels.project_kanaal(pid)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert msg.startswith("✗")
    assert len(st.channels.trail(k)) == 1, "het projectgesprek is geraakt"


def test_een_dm_kan_niet(tmp_path):
    """De helft van de berichten is van de ander. "Uit je lijst halen" bestaat al."""
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Iemand Anders", "anders@test.nl")
    k = channels.dm_kanaal(ik, ander.id)
    st.channels.post(k, "hoi", author_type="human", author_id=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert msg.startswith("✗") and len(st.channels.trail(k)) == 1


def test_een_cirkelkanaal_kan_niet(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    st.channels.post(k, "hoi", author_type="human", author_id=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert msg.startswith("✗") and len(st.channels.trail(k)) == 1


def test_een_doelkanaal_kan_niet(tmp_path):
    """Ook al staat hij nergens meer in een lijst: hij hangt aan een doel dat blijft bestaan."""
    dd, st, ik = _dorp(tmp_path)
    d = st.doelen.add("Een doel")
    k = channels.goal_kanaal(d["id"])
    st.channels.post(k, "hoi", author_type="human", author_id=ik)
    _nxt, msg = _verwijder(st, dd, k, "kanaal@test.nl")
    assert msg.startswith("✗") and len(st.channels.trail(k)) == 1


def test_de_store_weigert_ze_ook_zelf(tmp_path):
    """DE POORT IS DE POORT, maar een store die alles slikt is één vergeten `if` van een ramp af."""
    dd, st, ik = _dorp(tmp_path)
    d = st.doelen.add("Een doel")
    for k in (channels.circle_kanaal("mother_earth"), channels.goal_kanaal(d["id"]),
              channels.dm_kanaal("a", "b"), channels.project_kanaal("p1")):
        assert st.channels.verwijder_kanaal(k) is False, k


def test_een_kanaal_dat_er_niet_is(tmp_path):
    """Een verwijdering die "gelukt" zegt zonder iets te doen is erger dan een fout."""
    dd, st, ik = _dorp(tmp_path)
    assert st.channels.verwijder_kanaal("topic:bestaatniet") is False
    _nxt, msg = _verwijder(st, dd, "topic:bestaatniet", "kanaal@test.nl")
    assert msg.startswith("✗")


def test_twee_keer_verwijderen_is_geen_stille_ja(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    assert _verwijder(st, dd, k, "kanaal@test.nl")[1].startswith("🗑")
    assert _verwijder(st, dd, k, "kanaal@test.nl")[1].startswith("✗")


# ── het scherm stelt dezelfde vraag als de server ────────────────────────────
def test_de_maker_ziet_de_knop(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    html = render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    assert "value='kanaal_verwijder'" in html


def test_een_ander_ziet_hem_niet(tmp_path):
    """#610 LIET ZIEN WAT HET KOST als het scherm en de server een andere vraag stellen: de server
    werd daar ruimer en de knop niet, en dat viel pas live op. Hier de andere kant."""
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Iemand Anders", "anders@test.nl")
    k = st.channels.maak_topic("Batch 4", door=ik)
    html = render_messages(st, ik=ander.id, kanaal=k, csrf_token="t")
    assert "value='kanaal_verwijder'" not in html


def test_bij_een_project_staat_hij_er_niet(tmp_path):
    """Een knop die niets doet is erger dan geen knop — dezelfde regel als bij "remove from
    list", die ook alleen bij een project verschijnt."""
    dd, st, ik = _dorp(tmp_path)
    pid = st.projects.create(OWNER, "Project mycelium", "human", status="running")
    st.projects.add_feed_entry(pid, "x", kind="comment", author_type="human", author_id=ik)
    html = render_messages(st, ik=ik, kanaal=channels.project_kanaal(pid), csrf_token="t")
    assert "value='kanaal_verwijder'" not in html
    assert "value='kanaal_ontvolg'" in html, "de andere knop is meegesneuveld"


def test_de_knop_vraagt_het_eerst_en_noemt_het_aantal(tmp_path):
    """"Delete channel?" verzwijgt wat je meeneemt."""
    dd, st, ik = _dorp(tmp_path)
    k = st.channels.maak_topic("Batch 4", door=ik)
    for i in range(2):
        st.channels.post(k, f"bericht {i}", author_type="human", author_id=ik)
    html = render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    stuk = html[html.index("kanaal_verwijder") - 400:html.index("kanaal_verwijder") + 300]
    assert "confirm(" in stuk and "its 2 messages" in stuk
    assert "cannot be undone" in stuk


def test_de_poort_leeft_op_een_plek(tmp_path):
    """`reference, don't copy`. De view importeert de functie; hij bouwt hem niet na."""
    bron = inspect.getsource(mv)
    assert "mag_kanaal_verwijderen" in bron
    assert "maker_van(" not in bron, "de view stelt de vraag zelf opnieuw"


def test_de_tak_draagt_zijn_authz_label():
    """CLAUDE.md: geen nieuwe dispatch-tak zonder expliciet gekozen autorisatieniveau."""
    bron = inspect.getsource(cockpit2._act_kanaal_verwijder)
    assert "# AUTHZ: Circle Lead" in bron
