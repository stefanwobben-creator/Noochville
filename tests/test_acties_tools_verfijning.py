"""Drie verfijningen na de eerste ronde (27 september 2026, feedback Stefan).

1. AFGEVINKT VERDWIJNT NIET MEER. Een afgevinkte actie zakte naar een dichtgeklapt
   `<details>`-blokje ("X done"). De gedachte was "af is af"; de uitwerking was dat de regel
   VOELDE alsof hij verdween — je moest klikken om te zien dat hij er nog stond. Op papier streep
   je een regel door en hij blijft staan, en dat je hem nog ziet is precies wat "gedaan"
   bevredigend maakt.

2. HET SCHERM IS TE BREED. `/acties` gebruikte de volle contentkolom van de rest van de site.
   Voor een lijst met éénregelige acties springt het oog na elke regel helemaal terug. Een
   breedte-variant voor dit scherm — zonder `.c2-main`/`.c2-wrap` zelf aan te raken.

3. TOOLS KRIJGEN EEN EIGEN INGANG, en dat is GEEN derde plek: ze gaan WEG uit de wiki-tab per
   cirkel en komen op precies één plek. De voorwaarde was expliciet: echt weghalen, niet laten
   staan naast het nieuwe overzicht.

4. DE PROJECTKEUZE WAS ONBRUIKBAAR. `_projectopties` toonde alles wat je mocht lezen — honderden
   rijen op prod. Nu: wat loopt, onder je eigen rollen. Plus een tikbare verwijder-knop, want
   `.ck-item .dellink` is dorpsbreed hover-only en op een telefoon bestaat hover niet.
"""
from __future__ import annotations

import inspect
import pathlib
import re

from nooch_village import cockpit2
from nooch_village.views.acties import _projectopties, render_acties
from nooch_village.views.overview import render_node
from nooch_village.views.tools import render_tools

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
ROL = "mother_earth__nooch__compliance"
ANDERE_ROL = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for rol in (ROL, ANDERE_ROL):
        for f in list(st.assign.fillers_of(rol, st.records.get(rol))):
            st.assign.unassign(rol, f.type, f.id)
    a = st.people.add("Aap Een", "aap@test.nl")
    st.assign.assign(ROL, "person", a.id)
    return dd, st, a


# ══ 1. Afgevinkt blijft staan ════════════════════════════════════════════════
def test_een_afgevinkte_actie_staat_er_gewoon(tmp_path):
    """DE KERN VAN DE TERUGDRAAI. Geen klik nodig om te zien dat hij er nog is."""
    dd, st, a = _dorp(tmp_path)
    st.acties.add(a.id, "Open regel")
    it = st.acties.add(a.id, "Klare regel"); st.acties.zet(it["id"], a.id, done=True)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "Klare regel" in h
    # HET OUDE BLOKJE WAS `<details class='card'>`. De `<details>` die er nóg staat is de
    # koppel-uitklapper op een open regel — een ander ding, en die hoort er juist te zijn.
    assert "<details class='card'" not in h, "hij zit nog achter een inklapbaar blokje"
    assert "done</summary>" not in h


def test_hij_staat_onder_de_open_regels(tmp_path):
    dd, st, a = _dorp(tmp_path)
    st.acties.add(a.id, "Open regel")
    it = st.acties.add(a.id, "Klare regel"); st.acties.zet(it["id"], a.id, done=True)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert h.index("Open regel") < h.index("Klare regel")


def test_en_hij_is_doorgestreept(tmp_path):
    dd, st, a = _dorp(tmp_path)
    it = st.acties.add(a.id, "Klare regel"); st.acties.zet(it["id"], a.id, done=True)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "ck-done" in h and ".ck-done{text-decoration:line-through" in CSS


def test_de_scheiding_blijft_wel(tmp_path):
    """Zonder streep lopen open en klaar in elkaar over en is de lijst één grijze massa."""
    dd, st, a = _dorp(tmp_path)
    it = st.acties.add(a.id, "Klare regel"); st.acties.zet(it["id"], a.id, done=True)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "ck-klaar-kop" in h and "1 done" in h and "clear finished" in h
    assert "border-top" in re.search(r"\.ck-klaar-kop\{([^}]*)\}", CSS).group(1)


def test_zonder_afgevinkte_geen_kopregel(tmp_path):
    dd, st, a = _dorp(tmp_path)
    st.acties.add(a.id, "Open regel")
    assert "ck-klaar-kop" not in render_acties(st, ik=a.id, csrf_token="t")


# ══ 2. De smalle kolom ═══════════════════════════════════════════════════════
def test_het_scherm_heeft_een_eigen_breedte(tmp_path):
    dd, st, a = _dorp(tmp_path)
    h = render_acties(st, ik=a.id, csrf_token="t")
    assert "c2-main c2-smal" in h
    m = re.search(r"\.c2-smal\{([^}]*)\}", CSS)
    assert m and "max-width" in m.group(1) and "margin-inline:auto" in m.group(1)


def test_de_gedeelde_klassen_zijn_niet_aangeraakt():
    """"zonder de bestaande klassen voor de rest van de site aan te raken". `.c2-main` en
    `.c2-wrap` dragen elk ander scherm; een breedte daar raakt het bord en de organisatieboom."""
    for klasse in (".c2-main", ".c2-wrap"):
        m = re.search(rf"(?:^|[}};])\s*{re.escape(klasse)}\{{([^}}]*)\}}", CSS, re.M)
        assert m, klasse
        assert "34rem" not in m.group(1)


def test_er_komt_geen_nieuwe_klasse_familie_bij():
    """`test_ui_ratchets` bevriest het aantal prefix-families. Een breedte-variant van de
    contentkolom hóórt bij `c2-`; een kopregel tussen checklist-items bij `ck-`."""
    assert not re.search(r"\.act-[a-z]", CSS), "er is toch een eigen act-familie"


def test_verwijderen_kan_ook_zonder_muis():
    """`.ck-item .dellink` staat dorpsbreed op `opacity:0` tot je hovert, en op een telefoon
    bestaat hover niet — dan is de knop onbereikbaar. Binnen dit scherm is hij altijd zichtbaar."""
    m = re.search(r"\.c2-smal \.ck-item \.dellink\{([^}]*)\}", CSS)
    assert m and "opacity:.45" in m.group(1)
    assert ".c2-smal .ck-item:focus-within .dellink" in CSS
    assert "@media (hover:none){.c2-smal .ck-item .dellink" in CSS


def test_de_projectchecklist_houdt_zijn_eigen_gedrag():
    """De override is gescoped; buiten /acties verandert er niets."""
    assert ".ck-item .dellink{margin-left:auto;opacity:0}" in CSS


# ══ 3. De projectkeuze is klein en relevant ══════════════════════════════════
def _opties(html: str) -> list[str]:
    return re.findall(r"<option value='[^']*'[^>]*>([^<]+)</option>", html)


def test_alleen_lopende_projecten_onder_je_eigen_rollen(tmp_path):
    dd, st, a = _dorp(tmp_path)
    mijn = st.projects.create(ROL, "Van mijn rol mycelium", "human", status="running")
    st.projects.create(ANDERE_ROL, "Van een andere rol", "human", status="running")
    st.projects.create(ROL, "Nog niet begonnen", "human", status="future")
    namen = _opties(_projectopties(st, a.id, ""))
    assert "Van mijn rol mycelium" in namen
    assert "Van een andere rol" not in namen, "andermans rol staat erbij"
    assert "Nog niet begonnen" not in namen, "een toekomstig project staat erbij"
    assert mijn


def test_een_geblokkeerd_project_telt_wel(tmp_path):
    """`blocked` betekent "loopt, maar staat stil" — daar hoort juist een volgende stap bij."""
    dd, st, a = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Staat stil mycelium", "human", status="running")
    st.projects.block(pid, ROL)
    assert "Staat stil mycelium" in _opties(_projectopties(st, a.id, ""))


def test_een_gearchiveerd_project_niet(tmp_path):
    dd, st, a = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Opgeruimd mycelium", "human", status="running")
    st.projects.archive(pid)
    assert "Opgeruimd mycelium" not in _opties(_projectopties(st, a.id, ""))


def test_de_bestaande_koppeling_staat_er_altijd_bij(tmp_path):
    """Anders wist een select die je opent om te ONTkoppelen stilzwijgend de koppeling die er
    stond — de browser stuurt immers de geselecteerde optie mee."""
    dd, st, a = _dorp(tmp_path)
    pid = st.projects.create(ANDERE_ROL, "Niet van mijn rol", "human", status="running")
    html = _projectopties(st, a.id, pid)
    assert "Niet van mijn rol" in _opties(html)
    assert "selected" in html


def test_de_zichtbaarheid_blijft_de_buitengrens(tmp_path):
    """Filter 3 werkt op eigenaarschap; de leesregel blijft er als vangnet omheen."""
    bron = inspect.getsource(_projectopties)
    assert "mag_project_lezen" in bron


def test_de_lijst_is_echt_korter_geworden(tmp_path):
    """GEMETEN, niet aangenomen: 20 projecten in het dorp, waarvan 2 van jou en lopend."""
    dd, st, a = _dorp(tmp_path)
    for i in range(18):
        st.projects.create(ANDERE_ROL, f"Andermans {i}", "human", status="running")
    for i in range(2):
        st.projects.create(ROL, f"Van mij {i}", "human", status="running")
    namen = _opties(_projectopties(st, a.id, ""))
    assert len(namen) == 3, namen        # 2 eigen + "no project…"


# ══ 4. Tools op één plek ═════════════════════════════════════════════════════
def test_de_tools_pagina_toont_het_hele_dorp(tmp_path):
    dd, st, a = _dorp(tmp_path)
    h = render_tools(st, csrf_token="t", username="aap@test.nl")
    assert "Decision coach" in h and "Copy prompt generator" in h


def test_ze_staan_niet_meer_in_de_wiki_tab(tmp_path):
    """DE VOORWAARDE: echt weghalen, niet laten staan naast het nieuwe overzicht."""
    dd, st, a = _dorp(tmp_path)
    for kind in ("", "tool", "all"):
        q = f"&kind={kind}" if kind else ""
        h = render_node(st, "mother_earth", "wiki", csrf_token="t", username="aap@test.nl",
                        kind_flt=kind)
        assert "Decision coach" not in h, f"kind={kind!r}: de tool staat er nog"
        assert ">Tool</a>" not in h, f"kind={kind!r}: het Tool-filter staat er nog"
        assert q is not None


def test_de_wiki_tab_wijst_de_weg(tmp_path):
    """Een tool die stil verdwijnt laat niemand merken dat hij ergens anders staat."""
    dd, st, a = _dorp(tmp_path)
    h = render_node(st, "mother_earth", "wiki", csrf_token="t", username="aap@test.nl")
    assert "/tools" in h


def test_notes_en_policies_blijven_waar_ze_waren(tmp_path):
    """Alleen tools verhuizen. Een note en een policy zijn er om te LEZEN en horen bij hun rol."""
    dd, st, a = _dorp(tmp_path)
    h = render_node(st, "mother_earth", "wiki", csrf_token="t", username="aap@test.nl")
    assert ">Policy</a>" in h and ">Note</a>" in h


def test_het_ritme_blok_is_niet_zoekgeraakt(tmp_path):
    """Het stond onder het tool-filter maar is geen gereedschap; het hoort bij de rol-context."""
    from nooch_village.views import overview
    from conftest import py_zonder_uitleg
    bron = inspect.getsource(overview.render_node)
    assert "_ritme_html(st, rec)" in bron
    # ZONDER COMMENTAAR, anders toetst dit de uitleg die juist vértelt dat hij verhuisd is.
    wiki_deel = py_zonder_uitleg(bron.split('elif tab == "wiki"')[1])
    assert "_ritme_html" not in wiki_deel, "het ritme hangt nog aan de wiki-tab"


def test_de_view_kopieert_de_tool_tabellen_niet():
    """Zou `/tools` zijn eigen lijst houden, dan is een tool die elders wordt toegevoegd hier
    onzichtbaar — precies het twee-plekken-probleem dat dit scherm oplost."""
    from nooch_village.views import tools
    bron = inspect.getsource(tools)
    assert "_ROLE_TOOLS" in bron and "_DOMAIN_TOOLS" in bron
    assert "linkbuilding" not in bron.lower(), "er staat een gekopieerde tool-lijst in"


def test_tools_staat_in_de_zijbalk():
    from nooch_village.cockpit2_util import _SIDE_ITEMS
    paden = {h: (l, p) for h, l, p in _SIDE_ITEMS}
    assert paden["/tools"] == ("Tools", ""), "het is een paneel geworden"


def test_bewerken_stuurt_je_terug_naar_tools():
    """Een tool heeft geen tab meer om naar terug te keren; zonder dit land je na het opslaan op
    een wiki-tab waar hij niet meer staat, en dat leest als "mijn wijziging is weg"."""
    from nooch_village.views.overview import _terug_url
    assert _terug_url("mother_earth", "tool") == "/tools"
    assert _terug_url("mother_earth", "note").startswith("/node?id=mother_earth")


def test_de_eigenaar_blijft_zichtbaar(tmp_path):
    """Wie hem mag bewerken hangt aan de eigenaar, en dat weten is de helft van "mag ik hier iets
    aan veranderen"."""
    dd, st, a = _dorp(tmp_path)
    h = render_tools(st, csrf_token="t", username="aap@test.nl")
    assert "/node?id=mother_earth&tab=wiki" in h


def test_alleen_wie_mag_krijgt_de_bewerk_link(tmp_path):
    """DE LINK WIJST NAAR DE LEESPAGINA, niet meer naar de rol: het bewerkformulier is daarheen
    verhuisd (één bewerkpad per artefact). De poórt is onveranderd — alleen wie mag schrijven
    ziet de weg erheen."""
    from nooch_village.wiki import pagina_url
    dd, st, a = _dorp(tmp_path)
    tool = st.att.list("mother_earth", "tool")[0]
    zonder = render_tools(st, csrf_token="t", username="aap@test.nl")
    assert f">Edit</a>" not in zonder
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    st.assign.assign("mother_earth__circle_lead", "person", baas.id)
    met = render_tools(cockpit2._Stores(dd), csrf_token="t", username="anchor@test.nl")
    assert f">Edit</a>" in met
    assert pagina_url(tool.id) in met, "de link wijst niet naar de leespagina"
    assert "edit on the role" not in met, "hij wijst nog naar de rol"


def _namen_op_volgorde(html: str) -> list[str]:
    """De zichtbare naam van elke kaart, in de volgorde waarin hij op het scherm staat.

    Beide soorten kaart zetten dezelfde 🛠 voor de naam — die van een artefact (`_kaart`) en die
    van een ingebouwd scherm (`_tool_kaart`). Dat is precies wat een platte lijst mogelijk maakt:
    de kaarten zijn niet aan hun soort te herkennen, en hoeven dat ook niet te zijn."""
    blok = html.split("tile-grid")[1]
    return re.findall(r"\U0001f6e0 ([^<]+)", blok)


def test_de_tools_staan_in_een_platte_alfabetische_lijst(tmp_path):
    """DE INDELING WAS DIE VAN DE MAKER (29 september 2026). Twee blokken — "Tools" voor de
    artefacten, "Screens per role" voor de ingebouwde schermen, die laatste nog eens per rol
    ondergroepeerd — vroegen van de lezer dat hij wist hoe een stuk gereedschap ooit gebouwd is
    vóór hij wist waar hij moest kijken. Eén lijst op naam vraagt dat niet.

    DE GROEPERING PER ROL BLIJFT BESTAAN waar de rol wél het onderwerp is: op de Tools-tab van die
    rol (`_role_tools_html`). Die tabel is dezelfde; alleen dit overzicht groepeert niet meer."""
    dd, st, a = _dorp(tmp_path)
    st.att.add("mother_earth", "tool", title="Aardige eerste tool", url="/ergens")
    st.att.add("mother_earth", "tool", title="Zzz laatste tool", url="/elders")
    h = render_tools(cockpit2._Stores(dd), csrf_token="t", username="aap@test.nl")

    namen = _namen_op_volgorde(h)
    assert namen == sorted(namen, key=str.lower), f"niet alfabetisch: {namen}"
    # DOOR ELKAAR, niet achter elkaar: een artefact staat vóór een scherm en een ander erachter.
    assert namen[0].startswith("Aardige") and namen[-1].startswith("Zzz")
    assert "Site audit" in namen and "Decision coach" in namen

    # GEEN GROEPERING MEER: geen blokkop, en geen rolnaam als kopje.
    assert "Screens per role" not in h
    assert "<h3>" not in h, "er staat nog een kopje per rol"
    assert h.count("tile-grid") == 1, "er is meer dan één lijst"
    # De paginatekst en het formulier blijven staan, in die volgorde.
    assert h.index("Everything in the village") < h.index("tile-grid") < h.index("+ New tool")


def test_hetzelfde_scherm_staat_er_maar_een_keer(tmp_path):
    """Twee rollen met hetzelfde domein gaven twee kaarten onder twee kopjes — leesbaar. Naast
    elkaar in één lijst is dat ruis: zelfde naam, zelfde bestemming."""
    from nooch_village import claims_db
    dd, st, a = _dorp(tmp_path)
    for rol in (ROL, ANDERE_ROL):
        rec = st.records.get(rol)
        rec.definition.domains = [claims_db.DOMEIN]
        st.records.put(rec)
    h = render_tools(cockpit2._Stores(dd), csrf_token="t", username="aap@test.nl")
    assert _namen_op_volgorde(h).count("Claims checker") == 1


def test_de_titel_is_de_link_want_een_tool_open_je(tmp_path):
    dd, st, a = _dorp(tmp_path)
    h = render_tools(st, csrf_token="t", username="aap@test.nl")
    assert "/decision-coach" in h and "/copy-prompt" in h


# ══ 5. De vormgeving van het paneel ══════════════════════════════════════════
#
# Het scherm hing als losse onderdelen onder elkaar: een invoerveld, dan regels, zonder dat iets ze
# bij elkaar hield. Het prototype is één afgebakend paneel met een duidelijke naad tussen "hier
# schrijf je" en "hier staat het". Alles binnen `c2-` en `ck-` — geen nieuwe klasse-familie.
def _blok(selector: str) -> str:
    m = re.search(rf"(?:^|[}};])\s*{re.escape(selector)}\{{([^}}]*)\}}", CSS, re.M)
    assert m, f"{selector} bestaat niet"
    return m.group(1)


def test_het_paneel_is_afgebakend():
    """Eén kaart met een schaduw eromheen, en geen eigen padding meer: de onderdelen erin dragen
    hun eigen lucht, zodat de banden van rand tot rand lopen."""
    body = _blok(".c2-smal > .card")
    assert "padding:0" in body and "box-shadow" in body and "overflow:hidden" in body


def test_de_invoerrij_is_een_vlak_met_een_naad():
    body = _blok(".c2-smal .qadd-form")
    assert "background:var(--cream-2)" in body
    assert "border-bottom" in body, "geen scheiding tussen schrijven en lezen"
    assert "padding" in body


def test_het_veld_heeft_geen_kader_in_een_kader():
    """Het vlak eromheen ÍS de rand; twee kaders lezen als twee dingen."""
    body = _blok(".c2-smal .qadd-form input[type=text],.c2-smal .qadd-form input:not([type])")
    assert "border-color:transparent" in body and "box-shadow:none" in body


def test_de_regels_hebben_lucht_en_een_scheiding():
    body = _blok(".c2-smal .ck-item")
    assert "padding" in body and "border-bottom" in body
    assert "border-bottom:none" in _blok(".c2-smal .ck-item:last-child")


def test_de_klaar_kop_is_een_band_in_het_paneel():
    body = _blok(".c2-smal .ck-klaar-kop")
    assert "margin:0" in body and "background:var(--cream-2)" in body


def test_de_gedeelde_klassen_blijven_ongemoeid():
    """`.card` draagt elk ander scherm; alleen de variant BINNEN `.c2-smal` verandert."""
    kaart = _blok(".card")
    assert "padding:.5rem .7rem" in kaart, "de gedeelde kaart is aangepast"
    assert "overflow:hidden" not in kaart
    qadd = _blok(".qadd-form")
    assert "cream-2" not in qadd, "de gedeelde invoerrij is aangepast"


def test_er_komt_nog_steeds_geen_familie_bij():
    assert not re.search(r"\.act-[a-z]", CSS)
    for sel in (".c2-smal > .card", ".c2-smal .qadd-form", ".c2-smal .ck-item",
                ".c2-smal .ck-klaar-kop"):
        assert sel in CSS, sel


def test_het_blijft_zonder_javascript(tmp_path):
    """BEWUSTE KEUZE, en die verandert niet: typen + Enter werkt omdat één tekstveld in een
    formulier uit zichzelf verstuurt."""
    dd, st, a = _dorp(tmp_path)
    h = render_acties(st, ik=a.id, csrf_token="t")
    # OP HET FORMULIER, niet op de pagina: de gedeelde schil (nav, zoekbalk) draagt overal
    # JavaScript, en dat meten zegt niets over dit scherm. De claim is dat het INVOERGEBAAR geen
    # script nodig heeft — één tekstveld in een formulier verstuurt bij Enter uit zichzelf.
    form = h.split("value='actie_add'")[0].rsplit("<form", 1)[1]
    assert form.count("<input") - form.count("type='hidden'") == 1
    assert "onclick" not in form and "data-" not in form
    # En het afvinken en koppelen evenmin: allemaal gewone formulieren, geen enkel `data-`-haakje
    # waar een script zich aan vastmaakt. (De gedeelde schil bindt zijn éigen listeners — die
    # meten zou de nav toetsen, niet dit scherm.)
    dd2, st2, b2 = _dorp(pathlib.Path(dd).parent / "tweede")
    it = st2.acties.add(b2.id, "Iets")
    st2.acties.zet(it["id"], b2.id, done=True)
    vol = render_acties(st2, ik=b2.id, csrf_token="t")
    kern = vol[vol.index("<div class='card'"):]
    assert "data-qadd" not in kern and "addEventListener" not in kern


# ══ 6. "+ link to a project" naast het prototype ═════════════════════════════
#
# ELEMENT VOOR ELEMENT VERGELEKEN met het Mijn Acties-prototype. Zelfde PLAATS (de meta-regel
# onder de tekst) en zelfde STATEN (geen project → linkje · open → keuzelijst · gekoppeld →
# labeltje met ×). Drie dingen weken af, en alle drie maakten hem prominenter dan bedoeld:
#
#   1. `<summary>` tekent een driehoekje (▸); het prototype heeft geen marker.
#   2. `.flink` kleurt `--gray` (#4A4A4A), de op één na donkerste tekstkleur. Het prototype
#      gebruikt de faintste (#a19c88) — `--muted` (#9A9483) is hier de tegenhanger.
#   3. de onderstreping liep in currentColor en zonder afstand; in het prototype is hij
#      `--border`-kleurig met 2px offset.
def test_het_koppellinkje_heeft_geen_driehoekje():
    body = _blok(".c2-smal .ck-meta > summary")
    assert "list-style:none" in body
    assert ".c2-smal .ck-meta > summary::-webkit-details-marker{display:none}" in CSS


def test_het_is_de_faintste_tekstkleur():
    """`--gray` is de kleur van gewone tekst; dit linkje hoort zachter te zijn dan wat het
    begeleidt, niet even hard."""
    body = _blok(".c2-smal .ck-meta > summary")
    assert "color:var(--muted)" in body
    assert "var(--gray)" not in body


def test_de_onderstreping_is_aanwezig_maar_niet_luid():
    body = _blok(".c2-smal .ck-meta > summary")
    assert "text-decoration-color:var(--border)" in body
    assert "text-underline-offset:2px" in body


def test_hover_en_focus_maken_hem_vol():
    """Het prototype kleurt bij hover naar accent. Focus erbij, want met Tab moet hij ook
    oplichten — anders is de toetsenbordweg onzichtbaar."""
    assert ".c2-smal .ck-meta > summary:hover,.c2-smal .ck-meta > summary:focus-visible" in CSS


def test_het_blijft_zichtbaar_zonder_muis():
    """"of als hover-knop" is BEWUST NIET overgenomen: hover bestaat niet op een telefoon, en
    `.ck-item .dellink` liet al zien wat dat kost — daar was de knop onbereikbaar."""
    body = _blok(".c2-smal .ck-meta > summary")
    assert "opacity:0" not in body and "display:none" not in body


def test_de_drie_staten_staan_er_nog(tmp_path):
    """De vergelijking ging over de VORM, niet over het gedrag: geen project → linkje, open →
    keuzelijst, gekoppeld → labeltje met ×."""
    dd, st, a = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Batch 4 mycelium", "human", status="running")
    los = st.acties.add(a.id, "Zonder project")
    vast = st.acties.add(a.id, "Met project")
    st.acties.koppel(vast["id"], a.id, pid)
    h = render_acties(cockpit2._Stores(dd), ik=a.id, csrf_token="t")
    assert "+ link to a project" in h                      # staat 1
    assert "<select" in h                                  # staat 2 (achter de uitklapper)
    assert "cl-filter pill" in h and "actie_koppel" in h    # staat 3: labeltje + ontkoppelen
    assert los and vast


# ══ 7. Het koppel-linkje onder het designsysteem ═════════════════════════════
#
# HERMETEN NADAT /acties `.nu` KREEG (#627). Twee dingen die er zonder designsysteem niet
# uitsprongen, deden dat daarmee wél — en allebei stonden ze er al vóór #627:
#
#   1. `web_base._CSS` geeft ELKE `<details>` een rand, achtergrond, schaduw, marge en padding.
#      Hier is de `<details>` een linkje van vier woorden, geen uitklapbaar blok.
#   2. het designsysteem maakt van `.flink` een KNOP
#      (`:root .addlink, :root .vswitch a, :root .flink { border:1.5px solid …; background:… }`),
#      en de summary droeg die klasse. Resultaat: een omrande knop over de volle breedte.
#
# Dat laatste is geen fout in het designsysteem — `.flink` ÍS daar een knop. Dit element is er
# alleen nooit één geweest.
def test_de_uitklapper_is_geen_kaart():
    body = _blok(".c2-smal .ck-meta")
    for eig in ("background:none", "border:0", "box-shadow:none", "margin:0", "padding:0"):
        assert eig in body, eig


def test_de_summary_claimt_geen_knop_klasse():
    """`.flink` is onder `.nu` een omrande knop. Dit is een label, geen knop."""
    from nooch_village.views.acties import _meta
    import inspect
    bron = inspect.getsource(_meta)
    assert "<summary class='flink'>" not in bron
    assert "<summary>+ link to a project</summary>" in bron


def test_en_brengt_zijn_eigen_uiterlijk_mee():
    """Zonder `.flink` moet de regel zelf leveren wat die klasse gaf: grootte en cursor — plus
    expliciet geén rand of achtergrond, zodat een toekomstige generieke regel hem niet alsnog
    in een doos zet."""
    body = _blok(".c2-smal .ck-meta > summary")
    for eig in ("font-size:.78rem", "cursor:pointer", "background:none", "border:0"):
        assert eig in body, eig


def test_acties_draagt_het_designsysteem(tmp_path):
    """De aanleiding: `/acties` stond niet in `_NU_ROUTES` en zag er daarom anders uit dan
    Messages. Deze toets hoort hier omdat de opmaak hierboven ERVAN UITGAAT dat het designsysteem
    meedoet.

    DE LIJST BESTAAT NIET MEER (28 september 2026): er is één stylesheet en elke pagina krijgt hem.
    De vraag blijft dezelfde — draagt dit scherm het systeem? — maar hij wordt nu aan de PAGINA
    gesteld in plaats van aan een lijst met routes."""
    from nooch_village import cockpit2
    from nooch_village.views.acties import render_acties
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Aap", "aap@test.nl")
    html = render_acties(st, mens.id, "TOK")
    assert "/static/nooch.css" in html
    assert "nooch-ui" not in html, "er is weer een tweede stylesheet"
