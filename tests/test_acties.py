"""Mijn acties — het lichtste ding dat een "volgende stap" kan dragen (27 september 2026).

HET GAT DAT DIT VULT, twee symptomen met één oorzaak:

  1. Een "actie"-uitkomst uit het werkoverleg landde als DM. Sinds de DM-vereenvoudiging van
     20 september heeft een DM geen eigen velden, dus geen status: geen klaar-knop, geen lijst om
     op terug te komen. Verstuurd, en daarna weg.
  2. Een losse actie buiten het werkoverleg om had helemaal geen plek. `projects.create()` eist een
     rol- of cirkel-eigenaar plus een trigger-type — het juiste gewicht voor werk met een uitkomst,
     veel te zwaar voor één regel uit een telefoongesprek.

DE KOPPELING MET WERKOVERLEG VERANDERT DE INBOX-TAK ZELF, en voegt er geen tak aan toe. `bestemming()`
rekent de vraag "is de ontvanger één concrete mens?" al helemaal uit; hem hierboven nog eens stellen
zou de tweede formulering zijn waar zijn eigen docstring voor waarschuwt.
"""
from __future__ import annotations

import inspect

from nooch_village import acties as A
from nooch_village import cockpit2
from nooch_village.acties import ActieStore
from nooch_village.views.acties import render_acties

ROL = "mother_earth__nooch__compliance"
ANDERE_ROL = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    # De zaad-dataset zet zelf al vervullers neer; leegmaken zodat "één vervuller" ook echt één is.
    for rol in (ROL, ANDERE_ROL):
        for f in list(st.assign.fillers_of(rol, st.records.get(rol))):
            st.assign.unassign(rol, f.type, f.id)
    a = st.people.add("Aap Een", "aap@test.nl")
    b = st.people.add("Beer Twee", "beer@test.nl")
    return dd, st, a, b


def _ctx(st, dd, velden, username, actie):
    return cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/acties",
                         form=velden, username=username, action=actie, data_dir=dd)


def _doe(st, dd, actie, velden, username):
    return cockpit2.ACTIONS[actie](_ctx(st, dd, velden, username, actie))


# ══ 1. De store ══════════════════════════════════════════════════════════════
def test_een_regel_tekst_is_genoeg(tmp_path):
    """DE HELE POINTE. Geen rol, geen cirkel, geen trigger-type — alleen tekst en een mens."""
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Bel Selco terug")
    assert it and it["tekst"] == "Bel Selco terug"
    assert it["done"] is False and it["project"] == ""


def test_de_tekst_wordt_platgeslagen(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    assert st.acties.add(a.id, "  Bel   Selco\n terug ")["tekst"] == "Bel Selco terug"


def test_leeg_levert_niets_op(tmp_path):
    """Fail-closed op allebei: een actie zonder eigenaar komt op geen enkele lijst terug, en een
    lege actie is geen actie."""
    dd, st, a, b = _dorp(tmp_path)
    assert st.acties.add(a.id, "   ") is None
    assert st.acties.add("", "iets") is None


def test_afvinken_en_weer_openen(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Iets")
    assert st.acties.zet(it["id"], a.id, done=True) is True
    assert st.acties.get(it["id"])["done"] is True
    assert st.acties.get(it["id"])["done_at"] > 0
    assert st.acties.zet(it["id"], a.id, done=True) is False, "tweemaal hetzelfde is geen wijziging"
    assert st.acties.zet(it["id"], a.id, done=False) is True
    assert st.acties.get(it["id"])["done_at"] == 0.0


def test_alleen_de_eigenaar_vinkt_af(tmp_path):
    """Zichtbaarheid en zeggenschap zijn twee dingen: meekijken mag, namens iemand anders "gedaan"
    zeggen niet."""
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Van Aap")
    assert st.acties.zet(it["id"], b.id, done=True) is False
    assert st.acties.koppel(it["id"], b.id, "p1") is False
    assert st.acties.verwijder(it["id"], b.id) is False
    assert st.acties.get(it["id"])["done"] is False


def test_open_eerst_nieuwste_bovenaan(tmp_path):
    """De volgorde van het INVOERVELD: je typt bovenaan en ziet de regel op de plek waar je hem
    neerzette. Onderaan verschijnen voelt alsof er niets gebeurde."""
    dd, st, a, b = _dorp(tmp_path)
    een = st.acties.add(a.id, "Een")
    st.acties.add(a.id, "Twee")
    st.acties.add(a.id, "Drie")
    st.acties.zet(een["id"], a.id, done=True)
    assert [x["tekst"] for x in st.acties.voor(a.id)] == ["Drie", "Twee", "Een"]


def test_wis_afgerond_raakt_alleen_jouw_afgevinkte(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    mijn = st.acties.add(a.id, "Mijn klaar"); st.acties.zet(mijn["id"], a.id, done=True)
    st.acties.add(a.id, "Mijn open")
    van_b = st.acties.add(b.id, "Van Beer"); st.acties.zet(van_b["id"], b.id, done=True)
    assert st.acties.wis_afgerond(a.id) == 1
    assert [x["tekst"] for x in st.acties.voor(a.id)] == ["Mijn open"]
    assert len(st.acties.voor(b.id)) == 1, "andermans lijst is geraakt"
    assert st.acties.wis_afgerond(a.id) == 0


def test_de_teller_telt_alleen_open(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Een"); st.acties.add(a.id, "Twee")
    assert st.acties.open_aantal(a.id) == 2
    st.acties.zet(it["id"], a.id, done=True)
    assert st.acties.open_aantal(a.id) == 1
    assert st.acties.open_aantal(b.id) == 0


def test_het_overleeft_een_herstart(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.acties.add(a.id, "Blijft staan")
    assert [x["tekst"] for x in cockpit2._Stores(dd).acties.voor(a.id)] == ["Blijft staan"]


def test_de_store_is_slotveilig():
    """JsonStore-contract: elke schrijfmethode staat in `_WRITE_METHODS`, anders schrijft de
    cockpit over de daemon heen (zie het JsonStore-programma in CLAUDE.md)."""
    schrijvers = {"add", "zet", "koppel", "wis_afgerond", "verwijder"}
    assert schrijvers <= set(ActieStore._WRITE_METHODS)
    bron = inspect.getsource(A)
    assert "atomic_write_json" not in bron, "er wordt buiten JsonStore om geschreven"


# ══ 2. Zichtbaarheid ═════════════════════════════════════════════════════════
def test_zonder_project_alleen_van_jou(tmp_path):
    """Dit is een schrift."""
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Van mij")
    assert A.zichtbaar_voor(st, it, a.id) is True
    assert A.zichtbaar_voor(st, it, b.id) is False


def test_gekoppeld_volgt_het_project(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    pid = st.projects.create(ROL, "Batch 4 mycelium", "human", status="running")
    it = st.acties.add(a.id, "Van mij")
    st.acties.koppel(it["id"], a.id, pid)
    it = st.acties.get(it["id"])
    assert A.zichtbaar_voor(st, it, b.id) is True, "een open project is voor iedereen"
    st.projects.edit(pid, private=True)
    assert A.zichtbaar_voor(st, it, b.id) is False, "privé betekent alleen die cirkel"
    assert A.zichtbaar_voor(st, it, a.id) is True, "de eigenaar ziet hem altijd"


def test_er_komt_geen_nieuw_privacyniveau_bij():
    """"Hergebruik wat er al is." De projectregel wordt AANGEROEPEN, niet nageschreven."""
    bron = inspect.getsource(A.zichtbaar_voor)
    assert "mag_project_lezen" in bron
    assert "private" not in bron and "is_circle_member" not in bron


def test_een_verdwenen_project_zet_niets_open(tmp_path):
    """Fail-closed: een gekoppeld project dat niet meer bestaat valt terug op "alleen de
    eigenaar", niet op "iedereen"."""
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Van mij")
    st.acties.koppel(it["id"], a.id, "bestaat-niet")
    it = st.acties.get(it["id"])
    assert A.zichtbaar_voor(st, it, b.id) is False
    assert A.zichtbaar_voor(st, it, a.id) is True


# ══ 3. De dispatch-takken ════════════════════════════════════════════════════
def test_toevoegen_via_het_scherm(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    _nxt, msg = _doe(st, dd, "actie_add", {"tekst": "Bel Selco"}, a.email)
    assert msg.startswith("✓")
    assert [x["tekst"] for x in cockpit2._Stores(dd).acties.voor(a.id)] == ["Bel Selco"]


def test_een_lege_regel_zegt_dat(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    assert _doe(st, dd, "actie_add", {"tekst": "  "}, a.email)[1].startswith("✗")


def test_zonder_herkende_mens_gaat_er_niets(tmp_path):
    """Een actie hoort bij iemand; een lijst zonder eigenaar bestaat niet."""
    dd, st, a, b = _dorp(tmp_path)
    for actie in ("actie_add", "actie_zet", "actie_koppel", "actie_weg", "actie_wis"):
        assert _doe(st, dd, actie, {"tekst": "x"}, "guest")[1].startswith("✗"), actie


def test_afvinken_via_het_scherm(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Iets")
    assert _doe(st, dd, "actie_zet", {"aid": it["id"], "done": "1"}, a.email)[1].startswith("✓")
    assert cockpit2._Stores(dd).acties.get(it["id"])["done"] is True


def test_andermans_actie_afvinken_lukt_niet_via_het_scherm(tmp_path):
    """DE DIEPE POORT. Een knop die niet gerenderd wordt houdt geen POST tegen."""
    dd, st, a, b = _dorp(tmp_path)
    it = st.acties.add(a.id, "Van Aap")
    assert _doe(st, dd, "actie_zet", {"aid": it["id"], "done": "1"}, b.email)[1].startswith("✗")
    assert cockpit2._Stores(dd).acties.get(it["id"])["done"] is False


def test_koppelen_kan_alleen_aan_een_project_dat_je_mag_zien(tmp_path):
    """Anders kun je je eigen actie naar een plek sturen waar je niet kunt kijken."""
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    pid = st.projects.create(ROL, "Geheim mycelium", "human", status="running")
    st.projects.edit(pid, private=True)
    it = st.acties.add(b.id, "Van Beer")
    assert _doe(st, dd, "actie_koppel", {"aid": it["id"], "project": pid}, b.email)[1].startswith("✗")
    assert cockpit2._Stores(dd).acties.get(it["id"])["project"] == ""


def test_ontkoppelen_kan_altijd(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    pid = st.projects.create(ROL, "Batch 4", "human", status="running")
    it = st.acties.add(a.id, "Van mij"); st.acties.koppel(it["id"], a.id, pid)
    assert _doe(st, dd, "actie_koppel", {"aid": it["id"], "project": ""}, a.email)[1].startswith("✓")
    assert cockpit2._Stores(dd).acties.get(it["id"])["project"] == ""


def test_wis_afgerond_via_het_scherm(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    for t in ("Een", "Twee"):
        it = st.acties.add(a.id, t); st.acties.zet(it["id"], a.id, done=True)
    _nxt, msg = _doe(st, dd, "actie_wis", {}, a.email)
    assert "2 finished actions cleared" in msg
    assert cockpit2._Stores(dd).acties.voor(a.id) == []


def test_elke_tak_draagt_een_authz_label():
    """CLAUDE.md: geen nieuwe dispatch-tak zonder expliciet gekozen autorisatieniveau."""
    assert "# AUTHZ: iedereen-ingelogd" in inspect.getsource(cockpit2._actie_poort)
    for naam in ("actie_add", "actie_zet", "actie_koppel", "actie_weg", "actie_wis"):
        assert naam in cockpit2.ACTIONS, naam
        assert "_actie_poort(c)" in inspect.getsource(cockpit2.ACTIONS[naam]), naam


# ══ 4. De koppeling met Werkoverleg ══════════════════════════════════════════
def test_een_rol_met_een_vervuller_levert_een_actie(tmp_path):
    """DE KERN. Hiervoor werd dit een DM zonder status."""
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    soort, ref = cockpit2.route_werk(st, tekst="Bel Selco terug", rol=ROL, door="werkoverleg")
    assert soort == "inbox" and "als actie bij" in ref
    assert [x["tekst"] for x in st.acties.voor(a.id)] == ["Bel Selco terug"]
    assert st.channels.bestaande("dm") == [], "er is tóch een kale DM gestuurd"


def test_een_persoon_rechtstreeks_ook(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    cockpit2.route_werk(st, tekst="Direct", persoon=b.id, door="werkoverleg")
    assert [x["tekst"] for x in st.acties.voor(b.id)] == ["Direct"]


def test_de_herkomst_reist_mee(tmp_path):
    """"Waarom ligt dit hier" is precies de vraag die een DM tenminste nog beantwoordde."""
    dd, st, a, b = _dorp(tmp_path)
    cockpit2.route_werk(st, tekst="Uit het overleg", persoon=a.id, door="werkoverleg")
    assert st.acties.voor(a.id)[0]["herkomst"] == "werkoverleg"


def test_het_bronproject_wordt_de_koppeling(tmp_path):
    """Komt het uit een project, dan hangt de actie daar meteen aan — en zien de betrokkenen hem."""
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    pid = st.projects.create(ROL, "Batch 4 mycelium", "human", status="running")
    cockpit2.route_werk(st, tekst="Uit een project", persoon=b.id, bron_project=pid)
    it = st.acties.voor(b.id)[0]
    assert it["project"] == pid
    assert A.zichtbaar_voor(st, it, a.id) is True


def test_een_rol_met_meerdere_vervullers_houdt_de_dm(tmp_path):
    """Een actie is van ÉÉN mens. Hem in vier persoonlijke lijsten leggen maakt van één stuk werk
    vier stukken werk."""
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    st.assign.assign(ROL, "person", b.id)
    soort, ref = cockpit2.route_werk(st, tekst="Voor de rol", rol=ROL, door="werkoverleg")
    assert soort == "inbox" and "als actie" not in ref
    assert st.acties.voor(a.id) == [] and st.acties.voor(b.id) == []
    assert st.channels.bestaande("dm"), "de DM naar de rol is weggevallen"


def test_een_rol_zonder_vervuller_blijft_zoals_hij_was(tmp_path):
    """Die klimt naar de Circle Lead of wordt een project — die takken zijn niet aangeraakt."""
    dd, st, a, b = _dorp(tmp_path)
    soort, _ref = cockpit2.route_werk(st, tekst="Niemand", rol=ROL, door="werkoverleg")
    assert soort in ("inbox", "project")
    assert st.acties.voor(a.id) == [] and st.acties.voor(b.id) == []


def test_de_keuze_tak_is_niet_geraakt(tmp_path):
    """Meerdere vervullers plus `keuze_kan` blijft "keuze" — daar wordt niets weggeschreven."""
    dd, st, a, b = _dorp(tmp_path)
    st.assign.assign(ROL, "person", a.id)
    st.assign.assign(ROL, "person", b.id)
    soort, _ref = cockpit2.route_werk(st, tekst="x", rol=ROL, keuze_kan=True)
    assert soort == "keuze"
    assert st.acties.voor(a.id) == [] and st.acties.voor(b.id) == []


def test_de_tak_leest_bestemming_en_rekent_niet_zelf(tmp_path):
    """DE KEUZE DIE GEMAAKT IS: de inbox-tak verandert, er komt er geen bij. `bestemming()` rekent
    "is dit één concrete mens" al uit; die vraag hierboven nog eens stellen zou de tweede
    formulering zijn waar zijn eigen docstring voor waarschuwt."""
    bron = inspect.getsource(cockpit2.route_werk)
    assert 'if doel_type == "person":' in bron
    assert "mens_vervullers" not in bron, "route_werk telt de vervullers opnieuw"


def test_een_kapotte_actie_laat_het_werk_niet_verdampen(tmp_path):
    """Fail-soft: lukt de actie niet, dan alsnog de DM. Liever een melding zonder status dan
    niets — verstuurd mag nooit kwijt betekenen."""
    dd, st, a, b = _dorp(tmp_path)

    class Stuk:
        def add(self, *_a, **_k):
            return None
    st.acties = Stuk()
    soort, ref = cockpit2.route_werk(st, tekst="Valt terug", persoon=a.id, door="werkoverleg")
    assert soort == "inbox" and "als actie" not in ref
    assert cockpit2._Stores(dd).channels.bestaande("dm"), "er is niets verstuurd"


# ══ 5. Het scherm ════════════════════════════════════════════════════════════
def test_de_pagina_toont_je_eigen_lijst(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.acties.add(a.id, "Bel Selco mycelium")
    st.acties.add(b.id, "Van Beer geheim")
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "Bel Selco mycelium" in h and "Van Beer geheim" not in h


def test_zonder_mens_geen_lijst(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.acties.add(a.id, "Bel Selco mycelium")
    h = render_acties(st, ik="", csrf_token="t")
    assert "Bel Selco mycelium" not in h and "Log in as a person" in h


def test_typen_en_enter_is_het_hele_formulier(tmp_path):
    """EÉN tekstveld in een formulier verstuurt bij Enter uit zichzelf. Geen JavaScript, en
    niets anders is verplicht."""
    dd, st, a, b = _dorp(tmp_path)
    h = render_acties(st, ik=a.id, csrf_token="t")
    form = h.split("value='actie_add'")[0].rsplit("<form", 1)[1]
    assert form.count("<input") - form.count("type='hidden'") == 1, form
    assert "<select" not in form and "<textarea" not in form
    assert "autofocus" in form


def test_het_koppel_linkje_zit_niet_in_de_weg(tmp_path):
    """Dichtgeklapt is het één grijs linkje; de select komt pas als je erop klikt."""
    dd, st, a, b = _dorp(tmp_path)
    st.acties.add(a.id, "Iets")
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "<details" in h and "+ link to a project" in h
    kop = h.split("+ link to a project")[0]
    assert "<select" not in kop, "de keuzelijst staat al open"


def test_afgevinkte_items_zakken_naar_het_klaar_blokje(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.acties.add(a.id, "Open regel")
    it = st.acties.add(a.id, "Klare regel"); st.acties.zet(it["id"], a.id, done=True)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "1 done" in h and "clear finished" in h
    assert h.index("Open regel") < h.index("1 done") < h.index("Klare regel")


def test_zonder_afgevinkte_geen_blokje(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    st.acties.add(a.id, "Open regel")
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "clear finished" not in h and "done</summary>" not in h


def test_de_wis_knop_vraagt_het_eerst_en_noemt_het_aantal(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    for t in ("Een", "Twee"):
        it = st.acties.add(a.id, t); st.acties.zet(it["id"], a.id, done=True)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "confirm('Clear 2 finished actions?" in h and "cannot be undone" in h


def test_een_lege_lijst_zegt_iets_vriendelijks(tmp_path):
    dd, st, a, b = _dorp(tmp_path)
    assert "Nothing open" in render_acties(st, ik=a.id, csrf_token="t")


def test_de_view_verzint_geen_css(tmp_path):
    """HARDE REGEL uit CLAUDE.md: geen inline styles, geen nieuwe klasse zonder besluit."""
    import pathlib
    bron = inspect.getsource(__import__("nooch_village.views.acties", fromlist=["x"]))
    assert "style=" not in bron and "<style" not in bron
    css = (pathlib.Path(__file__).resolve().parents[1]
           / "nooch_village" / "static" / "nooch.css").read_text()
    for klasse in ("ck-item", "ck-box", "ck-txt", "ck-done", "qadd-form", "qadd-row",
                   "cl-filter", "dellink", "flink", "ck-meta", "ck-doorgeef"):
        assert f".{klasse}" in css, f"{klasse} bestaat niet in het designsysteem"


def test_mijn_acties_staat_in_de_zijbalk():
    """Zelfde soort item als Messages en Wiki, geen nieuwe hoofdcategorie."""
    from nooch_village.cockpit2_util import _SIDE_ITEMS
    paden = {h: (l, p) for h, l, p in _SIDE_ITEMS}
    assert paden["/acties"] == ("My actions", ""), "het is een paneel geworden"
    assert list(paden).index("/acties") == list(paden).index("/messages") + 1
