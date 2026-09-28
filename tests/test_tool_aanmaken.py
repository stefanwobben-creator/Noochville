"""Een tool aanmaken doe je op `/tools` (28 september 2026).

HET GAT, gemeten vóór er iets veranderde: er was precies ÉÉN weg naar een nieuw tool-artefact, en
dat was "+ New page" op `/wiki` — het scherm waar een tool sinds deze stap juist niet meer thuis
hoort. De rol-wikitab bood hem niet aan (dat is in #619 weggehaald) en `/tools` toonde alleen
lijsten. De volgorde van deze twee stappen is daarom geen smaak: ging de wiki-kant er eerst uit,
dan kon er tussentijds nergens een tool bij.

WAT DIT FORMULIER NIET VRAAGT is net zo belangrijk als wat het wel vraagt:

  * GEEN EIGENAAR. `_act_artefact_add` dwingt sinds #632 zelf `owner = artefacts.TOOL_ANCHOR` af
    voor een tool. Een keuze aanbieden waarvan het antwoord genegeerd wordt, zet de regel op twee
    plekken — en dan lopen ze uiteen.
  * GEEN DOMEIN EN GEEN SECTIE. Die bepalen waar een PAGINA in de wiki-navigatie landt; een tool
    staat daar niet in.
"""
from __future__ import annotations

import inspect
import re

from nooch_village import artefacts, cockpit2
from nooch_village.views.tools import render_tools


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Aap Een", "aap@test.nl")
    return dd, cockpit2._Stores(dd)


def _leeg(st):
    """Alle zaad-tools weg, zodat de lege stand écht leeg is."""
    for a in list(st.att.by_kind("tool", include_archived=True)):
        st.att.remove(a.id)


def _maak_via_het_formulier(st, dd, html, **extra):
    """Post precies de velden die in het formulier staan — niet wat de toets handig vindt."""
    velden = {m.group(1): m.group(2) for m in
              re.finditer(r"<input type='hidden' name='(\w+)' value='([^']*)'>", html)}
    velden.update(extra)
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt=velden.get("next", "/tools"),
                        form=velden, username="aap@test.nl", action=velden["action"], data_dir=dd)
    return velden, cockpit2.ACTIONS[velden["action"]](ctx)


# ══ 1. Het formulier staat er ════════════════════════════════════════════════
def test_er_staat_een_aanmaakformulier_op_tools(tmp_path):
    dd, st = _dorp(tmp_path)
    h = render_tools(st, csrf_token="TOK", username="aap@test.nl")
    assert "+ New tool" in h and "value='artefact_add'" in h
    assert "name='kind' value='tool'" in h


def test_ook_als_er_nog_geen_enkele_tool_is(tmp_path):
    """DE STAND WAARIN JE HEM HET HARDST NODIG HEBT. Hing hij alleen onder een gevulde lijst, dan
    ontbreekt hij precies wanneer er nog niets is om aan toe te voegen."""
    dd, st = _dorp(tmp_path)
    _leeg(st)
    h = render_tools(cockpit2._Stores(dd), csrf_token="TOK", username="aap@test.nl")
    assert "No tools in the village yet" in h and "+ New tool" in h


def test_hij_vraagt_geen_eigenaar_en_geen_domein(tmp_path):
    """De anchor wordt door de schrijfweg afgedwongen, en een tool staat niet in de
    wiki-navigatie. Wat je niet kunt beïnvloeden, hoor je ook niet gevraagd te worden."""
    dd, st = _dorp(tmp_path)
    blok = render_tools(st, csrf_token="TOK", username="aap@test.nl").split("+ New tool")[1]
    formulier = blok.split("</form>")[0]
    for veld in ("name='owner'", "name='domain'", "name='sectie'"):
        assert veld not in formulier, f"{veld} staat in het formulier"


def test_de_drie_velden_zijn_label_veld_paren(tmp_path):
    """`_field()` en geen losse `<label>`: `test_ui_ratchets` bevriest kale labels, en een label
    zonder `for` is voor een schermlezer een los stukje tekst."""
    dd, st = _dorp(tmp_path)
    blok = render_tools(st, csrf_token="TOK", username="aap@test.nl").split("+ New tool")[1]
    formulier = blok.split("</form>")[0]
    for fid in ("nt-title", "nt-url", "nt-body"):
        assert f'for="{fid}"' in formulier and f'id="{fid}"' in formulier, fid
    assert "_field(" in inspect.getsource(
        __import__("nooch_village.views.tools", fromlist=["x"])._nieuwe_tool_form)


# ══ 2. Aanmaken werkt, en landt waar het hoort ═══════════════════════════════
def test_een_tool_aanmaken_via_tools(tmp_path):
    """DE KETEN TOT HET EIND: de velden uit het formulier door de echte dispatch-tak, en dan
    kijken of hij op het scherm staat waar je hem aanmaakte."""
    dd, st = _dorp(tmp_path)
    _leeg(st)
    st = cockpit2._Stores(dd)
    h = render_tools(st, csrf_token="TOK", username="aap@test.nl")
    velden, (pad, melding) = _maak_via_het_formulier(
        st, dd, h, title="Zoolmeter", url="https://voorbeeld.nl/zool", body="Meet de zool.")
    assert melding.startswith("➕") and pad == "/tools"

    verse = cockpit2._Stores(dd)
    tools = verse.att.by_kind("tool")
    assert [a.title for a in tools] == ["Zoolmeter"]
    assert tools[0].url == "https://voorbeeld.nl/zool"
    assert "Zoolmeter" in render_tools(verse, csrf_token="TOK", username="aap@test.nl")


def test_hij_hangt_aan_de_cirkel_zonder_dat_het_formulier_dat_zegt(tmp_path):
    """DE REGEL WOONT IN DE SCHRIJFWEG. Het formulier stuurt geen `owner` mee; `_act_artefact_add`
    zet hem op `TOOL_ANCHOR`. Zou die tak dat niet meer doen, dan valt deze toets om — en niet het
    formulier, dat er niets over zegt."""
    dd, st = _dorp(tmp_path)
    _leeg(st)
    st = cockpit2._Stores(dd)
    h = render_tools(st, csrf_token="TOK", username="aap@test.nl")
    velden, _ = _maak_via_het_formulier(st, dd, h, title="Zoolmeter", url="/x")
    assert "owner" not in velden, "het formulier stuurt tóch een eigenaar mee"
    assert cockpit2._Stores(dd).att.by_kind("tool")[0].anchor == artefacts.TOOL_ANCHOR


def test_een_tool_zonder_link_krijgt_zijn_eigen_pagina(tmp_path):
    """De url is optioneel; de kaart linkt dan naar de permalink. Dat gat is in #619 al gedicht,
    en het blijft gelden voor wat je hier aanmaakt."""
    dd, st = _dorp(tmp_path)
    _leeg(st)
    st = cockpit2._Stores(dd)
    h = render_tools(st, csrf_token="TOK", username="aap@test.nl")
    _maak_via_het_formulier(st, dd, h, title="Zonder link", url="")
    verse = cockpit2._Stores(dd)
    aid = verse.att.by_kind("tool")[0].id
    assert f"/pagina?id={aid}" in render_tools(verse, csrf_token="TOK", username="aap@test.nl")


# ══ 3. En de wiki laat gereedschap los ═══════════════════════════════════════
#
# DE VOLGORDE IS DE HELE AFSPRAAK: eerst kan `/tools` aanmaken (hierboven), pas daarna gaat de
# wiki-kant eruit. Andersom was er tussentijds nergens een tool bij te maken.

def test_de_wiki_toont_en_telt_geen_tools_meer(tmp_path):
    from nooch_village.views.wiki import _WIKI_ICOON, _WIKI_SOORTEN, _wiki_items, render_wiki_index
    dd, st = _dorp(tmp_path)
    rol = "mother_earth__nooch__compliance"
    st.att.add(rol, "note", title="Een note")
    st.att.add(rol, "tool", title="Een gereedschap", url="/ergens")
    st = cockpit2._Stores(dd)

    assert "tool" not in {k for k, _ in _WIKI_SOORTEN} and "tool" not in _WIKI_ICOON
    # DE "ALL"-TELLING VOLGT UIT DEZELFDE LIJST, dus er is geen tweede plek die het moet weten.
    assert {a.kind for a in _wiki_items(st, "all")} <= {"note", "policy"}
    h = render_wiki_index(st, csrf_token="TOK", username="aap@test.nl")
    assert "Een gereedschap" not in h and ">Tool<" not in h


def test_de_wiki_biedt_geen_tool_meer_aan_om_te_starten(tmp_path):
    """"+ New page" maakt pagina's. Gereedschap start je op `/tools`."""
    from nooch_village.views.wiki import _nieuwe_pagina_form
    dd, st = _dorp(tmp_path)
    h = _nieuwe_pagina_form(st, "TOK", "aap@test.nl")
    assert "value='tool'" not in h
    assert "name='kind' value='note'" in h, "de soort moet wel meegestuurd blijven worden"


def test_een_onbekende_filterwaarde_valt_terug_op_all(tmp_path):
    """`/wiki?kind=tool` bestaat nog als url (een bookmark, een oude link). Hij hoort terug te
    vallen op "all" en niet op een lege lijst zonder uitleg."""
    from nooch_village.views.wiki import render_wiki_index
    dd, st = _dorp(tmp_path)
    st.att.add("mother_earth__nooch__compliance", "note", title="Een note")
    st = cockpit2._Stores(dd)
    h = render_wiki_index(st, csrf_token="TOK", soort="tool", username="aap@test.nl")
    assert "Een note" in h


def test_de_wiki_wijst_naar_waar_gereedschap_wel_staat(tmp_path):
    """Weghalen zonder wegwijzer laat iemand zoeken naar iets dat er gisteren nog was.

    IN BEIDE STANDEN, en dat is niet overdreven: de index heeft een aparte tekst voor "er staat
    nog niets" en een voor de gevulde lijst. Alleen de lege stand toetsen liet een mutatie op de
    andere zin ongemerkt door — gevonden met precies die mutatie."""
    from nooch_village.views.wiki import render_wiki_index
    dd, st = _dorp(tmp_path)
    # OP DE ZIN EN NIET OP `/tools`: de zijbalk heeft ook een Tools-link, dus een scan over de hele
    # pagina meet de buurman. Gevonden met een mutatie die de wegwijzer weghaalde en de toets groen
    # liet — precies de val waar deze codebase al vaker in liep.
    leeg = render_wiki_index(st, csrf_token="TOK", username="aap@test.nl")
    assert "Tools live on" in leeg, "de lege index wijst nergens heen"

    st.att.add("mother_earth__nooch__compliance", "note", title="Een note")
    gevuld = render_wiki_index(cockpit2._Stores(dd), csrf_token="TOK", username="aap@test.nl")
    assert "Een note" in gevuld
    assert "Tools live on" in gevuld, "de gevulde index wijst nergens heen"


def test_er_hangt_geen_dode_tool_ingang_meer_in_de_rol_tab():
    """GECHECKT EN NIET AANGENOMEN (vraag van Stefan): is er nog een `_artefact_add_form(rec,
    "tool", …)` die nooit bereikt wordt? Nee. `_artefact_add_form` heeft twee aanroepers, allebei
    binnen `_artefact_tab_html`, en díe wordt alleen met "policy" en "note" aangeroepen — de
    tool-tak is in #619 in zijn geheel weggehaald. Deze toets houdt dat vast, zodat er niet stil
    een derde soort bij komt op een tab die hem niet toont."""
    from nooch_village.views import overview
    bron = inspect.getsource(overview)
    aanroepen = [r.strip() for r in bron.splitlines() if "_artefact_tab_html(" in r
                 and not r.lstrip().startswith("def ")]
    assert aanroepen and all('"policy"' in r or '"note"' in r for r in aanroepen), aanroepen
    assert '"tool"' not in inspect.getsource(overview._artefact_tab_html)


# ══ 3. Dezelfde poort als de server ══════════════════════════════════════════
def test_zonder_schrijfsessie_geen_formulier(tmp_path):
    dd, st = _dorp(tmp_path)
    assert "+ New tool" not in render_tools(st, csrf_token="", username="aap@test.nl")


def test_een_onbekende_naam_krijgt_niets(tmp_path):
    """Fail-closed, en het spiegelt `_artefact_gate`: die weigert een naam die het dorp niet kent."""
    dd, st = _dorp(tmp_path)
    assert "+ New tool" not in render_tools(st, csrf_token="TOK", username="wie@test.nl")


def test_met_auth_uit_mag_het_gewoon(tmp_path):
    """"guest" mag alles, zoals overal in de cockpit — anders is het scherm met auth uit stuk."""
    dd, st = _dorp(tmp_path)
    assert "+ New tool" in render_tools(st, csrf_token="TOK", username="guest")
