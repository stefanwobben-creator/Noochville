"""Vangst — vangen scheiden van verwerken.

Vier beloften:
  1. vangen legt de zin vast en verder NIETS: geen bevinding, geen typering, geen kaart;
  2. het gevangen punt overleeft een herlaadbeurt en toont wie het inbracht;
  3. wie het inbracht reist mee, zodat het bij verwerken zíjn spanning wordt;
  4. verwerken hergebruikt de bestaande pijplijn: een spanning gaat door dezelfde haak die elke
     verse spanning typeert, en een project landt op het bord van de gekozen rol.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2
from nooch_village.views.vangst import render_vangst

CIRCLE = "mother_earth__nooch"
ROL = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _post(dd, action, **velden):
    return cockpit2.dispatch(dd, action, {k: [v] for k, v in velden.items()}, username="guest")


def _punten(dd):
    return cockpit2._Stores(dd).werk.punten(CIRCLE)


# ── 1. vangen schrijft alleen de zin ────────────────────────────────────────

def test_vangen_legt_vast_en_typeert_niets(tmp_path):
    dd = _dd(tmp_path)
    _post(dd, "vangst_add", circle=CIRCLE, punt="de leverancier belt nooit terug", next="/vangst")
    st = cockpit2._Stores(dd)
    punten = st.werk.punten(CIRCLE)
    assert [p["title"] for p in punten] == ["de leverancier belt nooit terug"]
    assert punten[0]["status"] == "open"
    assert punten[0].get("outcome") is None
    # Niets getypeerd, niets geschreven: geen enkele kaart bij wie dan ook.
    assert st.notif.all() == []


def test_lege_enter_is_geen_fout(tmp_path):
    dd = _dd(tmp_path)
    _nxt, msg = _post(dd, "vangst_add", circle=CIRCLE, punt="   ", next="/vangst")
    assert msg == ""
    assert _punten(dd) == []


def test_vangen_geeft_geen_banner(tmp_path):
    """Een bevestigingsbanner zou de aandacht (en op sommige schermen de focus) uit het veld halen;
    drie punten achter elkaar typen moet zonder onderbreking kunnen."""
    dd = _dd(tmp_path)
    _nxt, msg = _post(dd, "vangst_add", circle=CIRCLE, punt="een punt", next="/vangst")
    assert msg == ""


# ── 2. het punt blijft staan, en het scherm toont hem ───────────────────────

def test_drie_punten_blijven_staan_na_herladen(tmp_path):
    dd = _dd(tmp_path)
    for zin in ("eerste punt", "tweede punt", "derde punt"):
        _post(dd, "vangst_add", circle=CIRCLE, punt=zin, next="/vangst")
    # Verse stores = wat een herlaadbeurt ziet.
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    for zin in ("eerste punt", "tweede punt", "derde punt"):
        assert zin in html
    # Het veld staat er nog, leeg, met de cursor erin — anders is de één-toets-flow weg.
    assert "autofocus" in html and "vangst_add" in html


def test_scherm_toont_wie_het_inbracht(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.werk.backlog_add(CIRCLE, "punt van iemand", by="Stefan Wobben", by_id="p1")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "Stefan Wobben" in html


# ── 3. de inbrenger reist mee ───────────────────────────────────────────────

def test_inbrenger_wordt_de_afzender_van_de_spanning(tmp_path, monkeypatch):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "hier klopt iets niet aan de levertijden",
                             by="Stefan Wobben", by_id="p-stefan")
    _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="spanning", rol=ROL,
          next="/vangst")
    items = cockpit2._Stores(dd).notif.all()
    assert len(items) == 1
    assert items[0]["by"] == "p-stefan"                 # niet 'werkoverleg', niet leeg
    assert items[0]["snippet"] == "hier klopt iets niet aan de levertijden"


# ── 4. verwerken hergebruikt wat er al staat ────────────────────────────────

def test_spanning_gaat_ongetypeerd_de_bestaande_haak_in(tmp_path, monkeypatch):
    """De kaart mag hier NIET al een type dragen: dan zou `NotifStore.add` de haak overslaan en
    zou de vangst zijn eigen typering doen in plaats van de bestaande.

    En de haak moet ECHT gezet worden op de store die de actie gebruikt. `_bootstrap` zet hem op een
    `_Stores` die daarna wordt weggegooid, en elke request bouwt een verse — dus zonder deze regel
    draait de bevinding-schrijver in het web-pad nergens."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "een punt om te verwerken", by_id="p1")
    gezien = {}

    def _nep_verrijker(records, assignments, data_dir="", reason_fn=None):
        def _fn(n):
            gezien.update(n)
            return {"type": "naar_rol",
                    "bevinding": {"ok": True, "spanning": "x", "voorstel": "y"}}
        return _fn

    monkeypatch.setattr("nooch_village.spanning_ontstaat.maak_verrijker", _nep_verrijker)
    _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="spanning", rol=ROL,
          next="/vangst")
    assert gezien.get("snippet") == "een punt om te verwerken"      # de haak is echt gedraaid
    assert not gezien.get("type")                                   # ongetypeerd de haak in
    item = cockpit2._Stores(dd).notif.all()[0]
    assert item["type"] == "naar_rol"                               # de haak typeerde hem
    assert item["bevinding"]["ok"] is True


def test_punt_wordt_project_op_het_bord_van_een_rol(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "zool-leverancier vergelijken", by_id="p1")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project",
                      owner=ROL, tekst="zool-leverancier vergelijken", next="/vangst")
    assert msg.startswith("✓ project")
    st2 = cockpit2._Stores(dd)
    assert [p for p in st2.projects.all() if p.get("owner") == ROL
            and "zool-leverancier" in str(p.get("scope"))]
    # En het punt staat als verwerkt in de lijst — de ruwe tekst blijft staan.
    punt = st2.werk.punt_get(CIRCLE, it["id"])
    assert punt["status"] == "done" and punt["outcome"]["type"] == "project"
    assert "zool-leverancier vergelijken" in punt["title"]


def test_een_verwerkt_punt_wordt_niet_twee_keer_verwerkt(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "dubbel verwerken", by_id="p1")
    _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project", owner=ROL,
          tekst="dubbel verwerken", next="/vangst")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project",
                      owner=ROL, tekst="dubbel verwerken", next="/vangst")
    assert msg == "✗ already processed"
    assert len([p for p in cockpit2._Stores(dd).projects.all()
                if "dubbel verwerken" in str(p.get("scope"))]) == 1


def test_een_cirkel_kan_geen_project_dragen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "punt", by_id="p1")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="project",
                      owner=CIRCLE, tekst="punt", next="/vangst")
    assert "circle cannot hold a project" in msg


def test_punt_van_de_agenda_blijft_zichtbaar_in_de_vangst(tmp_path):
    """Een overleg openen verplaatst de backlog naar de agenda. Zou de vangst alleen de backlog
    tonen, dan zou vastgelegd werk stil verdwijnen."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.werk.backlog_add(CIRCLE, "gisteren gevangen", by_id="p1")
    st.werk.open(CIRCLE)
    punten = cockpit2._Stores(dd).werk.punten(CIRCLE)
    assert [p["title"] for p in punten] == ["gisteren gevangen"]
    assert punten[0]["bron"] == "agenda"
    assert "gisteren gevangen" in render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")


def test_geen_cirkel_geen_vangst(tmp_path):
    dd = _dd(tmp_path)
    html = render_vangst(cockpit2._Stores(dd), ROL, csrf_token="t")
    assert "Vangen hoort bij een cirkel" in html


def test_de_flow_stuurt_de_actienaam_mee(tmp_path):
    """De actienaam staat op de submit-KNOP, en `new FormData(form)` neemt knopwaarden niet mee.

    Zonder een expliciete `set('action', …)` komt de POST als naamloze actie binnen, en die doet de
    dispatch stil niets — 200, en weg. Precies dat gebeurde in de eerste meting op het scherm: drie
    punten getypt, nul aangekomen, geen enkele foutmelding."""
    dd = _dd(tmp_path)
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "d.set('action','vangst_add')" in html
    # En het veld dat de flow draagt moet er zijn, met de lijst die ververst wordt.
    assert "id='vang-form'" in html and "id='vang-lijst'" in html and "data-frag=" in html


def test_fragment_toont_dezelfde_rijen_als_de_pagina(tmp_path):
    """Eén bron voor de rijen: de live-verversing mag geen tweede vorm van hetzelfde zijn."""
    from nooch_village.views.vangst import render_vangst_frag
    dd = _dd(tmp_path)
    cockpit2._Stores(dd).werk.backlog_add(CIRCLE, "een gevangen punt", by="Iemand", by_id="p1")
    frag = render_vangst_frag(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "een gevangen punt" in frag and "data-open='1'" in frag
    assert frag in render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")


# ── fase 2: meerdere uitkomsten, elke rol ───────────────────────────────────

ANDERE_CIRKEL_ROL = "mother_earth__shareholder"


def test_een_spanning_kan_meerdere_uitkomsten_hebben(tmp_path):
    """Eén punt levert zelden één ding op. Een radio-knop dwingt je te kiezen wélke van de drie je
    opschrijft, en de andere twee raak je kwijt."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "de leverancier reageert niet", by_id="p1")
    naam = cockpit2._name(st.records.get(ROL))
    for otype in ("info", "project", "governance"):
        _nxt, msg = _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype=otype,
                          rol=naam, tekst="zool-leverancier vergelijken", next="/vangst")
        assert msg.startswith("✓"), (otype, msg)
    punt = cockpit2._Stores(dd).werk.punt_get(CIRCLE, it["id"])
    assert [u["type"] for u in punt["uitkomsten"]] == ["info", "project", "governance"]


def test_een_punt_kan_naar_twee_verschillende_rollen(tmp_path):
    """De kernfunctie: het punt van persoon X wordt werk voor rol Y — en soms ook voor rol Z."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "de maatvoering klopt niet", by_id="p1")
    a, b = ROL, "mother_earth__nooch__marketing_lead"
    for rol in (a, b):
        naam = cockpit2._name(st.records.get(rol))
        _nxt, msg = _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="project",
                          rol=naam, tekst="maatvoering nakijken", next="/vangst")
        assert msg.startswith("✓"), msg
    punt = cockpit2._Stores(dd).werk.punt_get(CIRCLE, it["id"])
    assert {u["rol"] for u in punt["uitkomsten"]} == {a, b}
    eigenaars = {p["owner"] for p in cockpit2._Stores(dd).projects.all()
                 if "maatvoering" in str(p.get("scope"))}
    assert eigenaars == {a, b}


def test_elke_rol_mag_ontvangen_niet_alleen_deze_cirkel(tmp_path):
    """Beperken tot de eigen cirkel maakt precies de overdracht onmogelijk waar een overleg voor
    bestaat: iemand brengt iets in dat ergens anders thuishoort."""
    from nooch_village.views.vangst import alle_rollen
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    ids = {r.id for r in alle_rollen(st)}
    assert ROL in ids and ANDERE_CIRKEL_ROL in ids     # andere cirkel, wel beschikbaar
    assert CIRCLE not in ids                            # een cirkel heeft geen handen


def test_een_slapende_rol_staat_niet_in_de_autocomplete(tmp_path):
    from nooch_village import afslanken as af
    from nooch_village.views.vangst import alle_rollen
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    af.slaap_leggen(st.records, ROL, reden="test")
    st.records.save()
    assert ROL not in {r.id for r in alle_rollen(cockpit2._Stores(dd))}


def test_een_dubbelzinnige_rolnaam_levert_geen_gok_op(tmp_path):
    """Werk bij het verkeerde bureau kost een hop en levert een vals gat-record op. Een zichtbare
    'niet gevonden' is eerlijker."""
    from nooch_village.views.vangst import rol_uit_naam
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rid, reden = rol_uit_naam(st, "bestaat echt niet")
    assert rid == "" and "geen rol gevonden" in reden
    _nxt, msg = _post(dd, "vangst_uitkomst", circle=CIRCLE,
                      iid=(st.werk.backlog_add(CIRCLE, "x", by_id="p1") or {}).get("id"),
                      otype="project", rol="bestaat echt niet", tekst="x", next="/vangst")
    assert msg.startswith("✗")
    assert cockpit2._Stores(dd).projects.all() == [] or not any(
        p.get("scope") == "x" for p in cockpit2._Stores(dd).projects.all())


def test_zonder_rol_en_zonder_persoon_hangt_het_werk_nergens(tmp_path):
    """Rol is niet meer verplicht in de LIVE verwerking — maar één van beide moet er zijn."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _nxt, msg = _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="project",
                      rol="", persoon="", tekst="x", next="/vangst")
    assert "kies een persoon" in msg


def test_een_individuele_actie_mag_zonder_rol(tmp_path):
    """"Lotte belt de leverancier even" hoort bij Lotte, niet bij een mandaat. Het werk landt op
    het bestaande Individueel Initiatief van de cirkel, niet op een verzonnen pseudo-rol."""
    from nooch_village.views.vangst import INDIVIDUELE_ACTIE
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    p = st.people.all()[0]
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _nxt, msg = _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="project",
                      rol=INDIVIDUELE_ACTIE, persoon=p.id, tekst="Leverancier bellen",
                      next="/vangst")
    assert msg.startswith("✓"), msg
    st2 = cockpit2._Stores(dd)
    u = st2.werk.punt_get(CIRCLE, it["id"])["uitkomsten"][0]
    assert u["rol"] == "" and u["persoon"] == p.id
    pr = [x for x in st2.projects.all() if "Leverancier bellen" in str(x.get("scope"))]
    assert pr and pr[0]["owner"] == f"ii:{CIRCLE}"


def test_de_ai_route_houdt_zijn_rol_borging(tmp_path):
    """Het onderscheid dat niet mag doorlekken: de getypeerde AI-spanning eist nog steeds een rol,
    want dat oordeel rust op de accountabilities van die rol."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _nxt, msg = _post(dd, "vangst_verwerk", circle=CIRCLE, iid=it["id"], otype="spanning",
                      rol="", next="/vangst")
    assert "pick a role" in msg


def test_afgevinkt_blijft_zichtbaar_en_doorgestreept(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "een afgehandeld punt", by_id="p1")
    _post(dd, "vangst_klaar", circle=CIRCLE, iid=it["id"], klaar="1", next="/vangst")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    assert "een afgehandeld punt" in html               # niet weg
    assert "ck-done" in html                            # doorgestreept
    assert cockpit2._Stores(dd).werk.punt_get(CIRCLE, it["id"])["status"] == "done"


def test_afvinken_is_omkeerbaar(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _post(dd, "vangst_klaar", circle=CIRCLE, iid=it["id"], klaar="1", next="/vangst")
    _post(dd, "vangst_klaar", circle=CIRCLE, iid=it["id"], klaar="0", next="/vangst")
    assert cockpit2._Stores(dd).werk.punt_get(CIRCLE, it["id"])["status"] == "open"


def test_uitkomsten_overleven_het_afvinken(tmp_path):
    """Afvinken sluit het punt, het wist niet wat eruit kwam."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    st.werk.punt_uitkomst_add(CIRCLE, it["id"], {"type": "info", "rol": ROL, "tekst": "x"})
    _post(dd, "vangst_klaar", circle=CIRCLE, iid=it["id"], klaar="1", next="/vangst")
    assert len(cockpit2._Stores(dd).werk.punt_get(CIRCLE, it["id"])["uitkomsten"]) == 1


def test_optionele_rol_bij_het_vangen_blokkeert_niets(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    naam = cockpit2._name(st.records.get(ROL))
    _post(dd, "vangst_add", circle=CIRCLE, punt=f"zolen nakijken @{naam}", next="/vangst")
    _post(dd, "vangst_add", circle=CIRCLE, punt="iets @nietbestaandrol", next="/vangst")
    punten = cockpit2._Stores(dd).werk.punten(CIRCLE)
    per_titel = {p["title"]: p for p in punten}
    assert per_titel[f"zolen nakijken @{naam}"].get("rol_hint") == ROL
    # Een niet-oplosbare @rol gooit het punt NIET weg — de tekst staat er gewoon.
    assert "iets @nietbestaandrol" in per_titel
    assert per_titel["iets @nietbestaandrol"].get("rol_hint") in (None, "")


def test_vangen_kost_een_veld_en_een_enter(tmp_path):
    """De meting uit de opdracht: hoeveel velden kost het om één punt te vangen in fase 1?

    Precies één zichtbaar invoerveld in het vangformulier, en geen enkele uitkomst-keuze."""
    import re
    dd = _dd(tmp_path)
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")
    form = re.search(r"<form[^>]*id='vang-form'.*?</form>", html, re.S).group(0)
    zichtbaar = [m for m in re.findall(r"<(?:input|select|textarea)[^>]*>", form)
                 if "type='hidden'" not in m]
    assert len(zichtbaar) == 1, zichtbaar
    for woord in ("otype", "vangst_uitkomst", "Wat levert dit op"):
        assert woord not in form                        # geen uitkomst-keuze in fase 1


def test_het_verwerkblok_blijft_open_na_een_uitkomst(tmp_path):
    """Eén spanning levert meerdere uitkomsten op; elke keer opnieuw moeten uitklappen maakt van
    'meerdere mag' alsnog een drempel per regel."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "een punt", by_id="p1")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "<details class='wo-ocd box-details' open>" in html
    # En de formulieren sturen je terug mét dat punt open.
    assert f"open={it['id']}" in html
    # Een ander punt blijft dicht.
    ander = st.werk.backlog_add(CIRCLE, "tweede punt", by_id="p1")
    html2 = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert html2.count("<details class='wo-ocd box-details' open>") == 1
    assert ander["id"] != it["id"]


# ── de twee vang-ingangen naast elkaar ──────────────────────────────────────

def test_de_header_biedt_geen_tweede_vang_ingang_meer(tmp_path):
    """Twee ingangen naar dezelfde functie maken geen van beide de vanzelfsprekende. De ROUTE
    blijft: de agenda-stap leunt erop en directe links mogen niet breken."""
    from nooch_village.views.overview import render_node
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    html = render_node(st, CIRCLE, "overview", csrf_token="t", username="guest")
    assert "Governance meeting" in html and "Tactical meeting" in html
    assert "Quick capture" not in html
    assert "/vangst" not in html
    # …maar de route zelf leeft nog.
    assert "Vangen" in render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t")


def test_de_inbox_vangt_een_los_punt_in_een_regel(tmp_path):
    """De vervangende ingang moet het minimum kunnen: één regel, zonder uitkomst-keuze."""
    dd = _dd(tmp_path)
    _nxt, msg = _post(dd, "notif_add", text="de zolen komen te laat", role="", next="/inbox")
    assert msg.startswith("✓")
    items = cockpit2._Stores(dd).notif.all()
    assert len(items) == 1
    assert items[0]["snippet"] == "de zolen komen te laat"
    assert items[0]["at"]                                   # wanneer: ja
    assert not items[0].get("type")                         # geen uitkomst-keuze bij het noteren


def test_de_inbox_vang_legt_de_opwerper_NIET_vast(tmp_path):
    """Het verschil dat gemeld moet worden: /vangst bewaart wie het punt inbracht (naam én id),
    de inbox-vangst schrijft de letterlijke tekst 'zelf'. Voor een persoonlijke inbox is dat
    genoeg — voor een overleg met vijf mensen aan tafel niet."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _post(dd, "notif_add", text="een punt", role="", next="/inbox")
    assert cockpit2._Stores(dd).notif.all()[0]["by"] == "zelf"

    st.werk.backlog_add(CIRCLE, "een punt", by="Stefan Wobben", by_id="p-stefan")
    punt = cockpit2._Stores(dd).werk.punten(CIRCLE)[0]
    assert punt["by"] == "Stefan Wobben" and punt["by_id"] == "p-stefan"


def test_de_inbox_vang_kent_geen_gedeelde_lijst_per_cirkel(tmp_path):
    """Een inbox-punt landt in je EIGEN inbox; het komt niet op de agenda van het eerstvolgende
    werkoverleg en niemand anders ziet het. Dat is het tweede verschil."""
    dd = _dd(tmp_path)
    _post(dd, "notif_add", text="een los punt", role="", next="/inbox")
    assert cockpit2._Stores(dd).werk.punten(CIRCLE) == []


def test_vangst_zonder_cirkel_valt_terug_op_de_thuiscirkel(tmp_path):
    """`/vangst` zonder `?circle=` gaf een 502: de route gaf de Records-STORE door aan `org.roots`,
    dat over records itereert. Onzichtbaar voor elke test die wél een cirkel meegeeft — en precies
    de URL die je intikt als je het scherm zoekt."""
    from nooch_village.cockpit2 import _home_node
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    thuis = _home_node(st.records.all())               # zo roept de route hem aan
    assert thuis and st.records.get(thuis) is not None
    assert "Vangen" in render_vangst(st, thuis, csrf_token="t")


# ── de live-vorm: niets forceren dat toch leeg blijft ───────────────────────

def test_een_kaal_agendapunt_toont_geen_groot_spanningsvak(tmp_path):
    """Het normale live-geval. Er is geen tijd om een spanning uit te schrijven, dus het scherm
    vraagt er niet om: één klein '⚡ Geen' en meteen door naar het uitkomst-formulier."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "Checkout hapert", by_id="p1")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "⚡ Geen" in html
    assert "beschrijf hier wat er speelt" not in html        # het oude, dwingende blok is weg
    # en het uitkomst-formulier staat vóór de uitkomstenlijst
    assert html.index("name='otype'") < html.index("Uitkomsten van het overleg")


def test_een_vooraf_ingevoerde_spanning_staat_er_gewoon(tmp_path):
    """Het enige geval waarin de tekst zinnig is: iemand voerde hem vooraf in. Dan lees je hem
    meteen, zonder te hoeven klikken."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "Checkout hapert", by="Stefan Wobben", by_id="p1")
    st.werk.punt_tekst(CIRCLE, it["id"], "Klanten haken af bij de betaalstap sinds de nieuwe flow.")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "Klanten haken af bij de betaalstap" in html
    assert "⚡ Geen" not in html


def test_de_herkomst_is_automatisch_geen_invulveld(tmp_path):
    """'Welke rol voelt het' is herkomst, geen toewijzing — en de secretaris tikt het niet in."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    naam = cockpit2._name(st.records.get(ROL))
    _post(dd, "vangst_add", circle=CIRCLE, punt=f"Checkout hapert @{naam}", next="/vangst")
    it = cockpit2._Stores(dd).werk.punten(CIRCLE)[0]
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "gevoeld vanuit" in html and naam in html
    # geen invulveld ervoor
    assert "voelt het" not in html and "feels it" not in html


def test_het_uitkomst_formulier_is_waar_de_secretaris_werkt(tmp_path):
    """ROL is de ONTVANGER van het werk, niet 'wie het voelt' — en er staat een PERSOON naast."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "Iets", by_id="p1")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    for veld in (">Wat</label>", ">Rol</label>", ">Persoon</label>"):
        assert veld in html, veld
    assert "— Kies persoon —" in html and "Elk cirkellid" in html
    assert "Individuele actie" in html          # eerste rol-optie, rol is niet verplicht
    assert "Alleen zichtbaar voor de cirkel" in html
    # GEEN staat-keuze meer: de wachtstatus leeft op projectniveau.
    assert "name='staat'" not in html
    assert "In afwachting" not in html
    # en het twee-koloms raster van de referentie
    assert "rov-addgrid" in html


def test_de_uitkomsten_staan_in_een_tabel_met_kolomkoppen(tmp_path):
    """Zoals de referentie: WAT · wat precies · ROL · PERSOON · STAAT, met potlood en prullenbak."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "Iets", by_id="p1")
    naam = cockpit2._name(st.records.get(ROL))
    _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="actie", rol=naam,
          tekst="Leverancier bellen", persoon="", next="/vangst")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "<table class='mtab'>" in html
    for kop in ("<strong>Wat</strong>", "<strong>Rol</strong>", "<strong>Persoon</strong>",
                "<strong>Herkomst</strong>"):
        assert kop in html, kop
    assert "Leverancier bellen" in html


def test_de_herkomst_staat_er_ook_zonder_uitkomsten(tmp_path):
    """Het geval waarvoor herkomst bestaat: een vooraf ingevoerde spanning die je nu behandelt."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    naam = cockpit2._name(st.records.get(ROL))
    _post(dd, "vangst_add", circle=CIRCLE, punt=f"Checkout hapert @{naam}", next="/vangst")
    it = cockpit2._Stores(dd).werk.punten(CIRCLE)[0]
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "gevoeld vanuit" in html
    assert "Er zijn (nog) geen uitkomsten vastgelegd" in html


def test_de_leeftijd_is_fijn_aan_de_korte_kant(tmp_path):
    """"42 seconden oud" is informatie in een overleg; "vandaag" is alles wat je die ochtend deed."""
    import time as _t
    from nooch_village.views.vangst import _leeftijd
    nu = _t.time()
    assert _leeftijd(nu - 42) == "42 seconden oud"
    assert _leeftijd(nu - 1) == "1 seconde oud"
    assert _leeftijd(nu - 300) == "5 minuten oud"
    assert _leeftijd(nu - 7200) == "2 uur oud"
    assert _leeftijd(nu - 3 * 86400) == "3 dagen oud"
    assert _leeftijd(0) == ""


def test_alleen_zichtbaar_voor_de_cirkel_maakt_het_project_prive(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    naam = cockpit2._name(st.records.get(ROL))
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="project", rol=naam,
          tekst="Stil project", prive="1", next="/vangst")
    st2 = cockpit2._Stores(dd)
    pr = [x for x in st2.projects.all() if "Stil project" in str(x.get("scope"))]
    assert pr and pr[0].get("private") is True
    u = st2.werk.punt_get(CIRCLE, it["id"])["uitkomsten"][0]
    assert u["prive"] is True
    assert "🔒" in render_vangst(st2, CIRCLE, csrf_token="t", open_iid=it["id"])


def test_elk_cirkellid_is_een_echte_keuze(tmp_path):
    """De lege '— Kies persoon —' staat bovenaan zodat je niet in 'elk cirkellid' rolt."""
    from nooch_village.views.vangst import ELK_LID_WAARDE
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    naam = cockpit2._name(st.records.get(ROL))
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="project", rol=naam,
          persoon=ELK_LID_WAARDE, tekst="x", next="/vangst")
    u = cockpit2._Stores(dd).werk.punt_get(CIRCLE, it["id"])["uitkomsten"][0]
    assert u["persoon"] == ""                    # opgeslagen als 'nog niemand', bewust gekozen


def test_een_oude_staat_blijft_leesbaar(tmp_path):
    """Geen stille drop: het INVULVELD is weg, de vastgelegde waarde niet. Een uitkomst van vóór
    deze wijziging die 'in afwachting' zei, zegt dat nog steeds."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    st.werk.punt_uitkomst_add(CIRCLE, it["id"], {"type": "actie", "rol": ROL, "tekst": "oud werk",
                                                 "staat": "wachtend"})
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "In afwachting" in html               # de oude waarde staat er nog
    assert "<strong>Staat</strong>" in html      # met zijn kolom
    assert "name='staat'" not in html            # maar je kunt hem nergens meer invullen


def test_zonder_oude_records_verdwijnt_de_staat_kolom(tmp_path):
    """Een kolom die bij elke nieuwe uitkomst leeg blijft is ruis. Hij komt alleen terug zodra er
    nog een record ligt dat hem draagt."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    naam = cockpit2._name(st.records.get(ROL))
    it = st.werk.backlog_add(CIRCLE, "x", by_id="p1")
    _post(dd, "vangst_uitkomst", circle=CIRCLE, iid=it["id"], otype="actie", rol=naam,
          tekst="nieuw werk", next="/vangst")
    html = render_vangst(cockpit2._Stores(dd), CIRCLE, csrf_token="t", open_iid=it["id"])
    assert "nieuw werk" in html
    assert "<strong>Staat</strong>" not in html
