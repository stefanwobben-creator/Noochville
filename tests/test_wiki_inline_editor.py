"""De wiki-editor: de tekst zelf is het invoerveld (21 september 2026).

WAT ER VERVANGEN IS, en waarom dit geen patch op het oude model is. Tot vandaag stond de
opgemaakte tekst bovenaan in een kader, en opende "Edit page" daaronder een tweede blok: een los
TITLE-veld plus een textarea met de RUWE markdown. Je las op de ene plek en typte op de andere,
met dezelfde inhoud twee keer op het scherm.

Vier eigenschappen moeten hard zijn, en dit bestand toetst ze in die volgorde:

  1. één kopie van de inhoud op het scherm, en één opslagpad;
  2. wie niet mag bewerken krijgt geen cursor en geen formulier (de poort staat vóór de belofte);
  3. de server maakt van de HTML weer markdown — er wordt nooit HTML opgeslagen;
  4. er is geen TWEEDE bewerkpad blijven staan, ook niet op de Notes-tab van de rol.

De omzetting zelf (HTML → markdown) heeft zijn eigen bestand: `tests/test_md_bron.py`.
"""
from __future__ import annotations

import pathlib

from nooch_village import cockpit2, wiki
from nooch_village.views.wiki import render_pagina

JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()

#: De werkbalk zoals hij gerenderd wordt — het argument reist als HTML-attribuut mee.
from nooch_village.cockpit2_util import opmaak_werkbalk as _werkbalk      # noqa: E402
JS_WERKBALK = _werkbalk()


def _dorp(tmp_path, *, can_edit: bool = True, body: str = "Wat **tekst** hier."):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    a = st.att.add(rol, wiki.PAGINA_KIND, title="Testpagina", body=body)
    mens = st.people.add("Beheerder", "b@t.nl")
    if can_edit:
        st.assign.assign(rol, "person", mens.id)
    return dd, st, a, mens


def _html(tmp_path, **kw):
    dd, st, a, mens = _dorp(tmp_path, **kw)
    return render_pagina(st, a.id, csrf_token="TOK",
                         username="b@t.nl" if kw.get("can_edit", True) else "")


# ── 1. Eén kopie, één opslagpad ──────────────────────────────────────────────
def test_de_tekst_staat_er_een_keer_en_is_daar_bewerkbaar(tmp_path):
    html = _html(tmp_path)
    assert html.count("<strong>tekst</strong>") == 1, "de inhoud staat twee keer op het scherm"
    assert "id='wiki-body'" in html                 # het element dat bewerkbaar wordt
    assert "id='wiki-titel'" in html                # de titel ook, op zijn plek in de kop
    assert html.count("value='artefact_edit'") == 1


def test_het_formulier_draagt_geen_inhoud_alleen_de_balk(tmp_path):
    """Het formulier staat onder de tekst, maar er valt niets in te lezen: alleen verborgen
    velden en de opslaan-balk. Zou er inhoud in staan, dan is het alsnog een tweede kopie."""
    html = _html(tmp_path)
    form = html.split("id='wiki-form'")[1].split("</form>")[0]
    assert "Wat" not in form and "tekst" not in form
    assert "name='body_html'" in form and "name='title'" in form
    assert "qadd-bar" in form


# ── 2. De poort staat vóór de belofte ────────────────────────────────────────
def test_wie_niet_mag_bewerken_krijgt_geen_editor(tmp_path):
    """Een cursor die belooft dat je kunt typen, terwijl de poort het daarna weigert, is erger
    dan geen cursor."""
    html = _html(tmp_path, can_edit=False)
    for haak in ("data-wiki-start", "wiki-form", "body_html", "opmaak-werkbalk", "id='wiki-tb'"):
        assert haak not in html, f"{haak} hoort niet op een pagina die je niet mag bewerken"
    assert "Wat" in html                            # lezen mag natuurlijk wel


def test_zonder_schrijfsessie_geen_editor(tmp_path):
    """Geen csrf-token = een publieke view. Dan ook geen formulier dat toch zou afketsen."""
    dd, st, a, mens = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="", username="b@t.nl")
    assert "wiki-form" not in html and "body_html" not in html


# ── 3. De server slaat markdown op, nooit HTML ───────────────────────────────
def test_de_server_maakt_van_de_html_weer_markdown(tmp_path):
    """DE BELANGRIJKSTE TEST VAN DIT BESTAND. De browser stuurt HTML; in de opslag hoort markdown
    te staan. Staat daar HTML, dan is elke andere lezer van dat veld (de zoekindex, de
    systeemprompt, een export) vanaf dat moment stuk."""
    dd, st, a, mens = _dorp(tmp_path)
    _, msg = cockpit2.dispatch(dd, "artefact_edit", {
        "csrf": ["TOK"], "aid": [a.id], "title": ["Nieuwe titel"],
        "body_html": ["<h4>Kop</h4><ul class='fbul'><li>een <strong>vet</strong></li></ul>tekst"],
        "next": ["/pagina"]}, username="b@t.nl")
    na = cockpit2._Stores(dd).att.get(a.id)
    assert na.body == "## Kop\n- een **vet**\ntekst"
    assert "<" not in na.body and na.title == "Nieuwe titel"
    assert "updated" in msg


def test_wat_chrome_werkelijk_terugstuurt(tmp_path):
    """HET ECHTE GEVAL, niet een schoolvoorbeeld. Dit is de HTML zoals een browser hem oplevert
    nadat je in de tekst hebt getypt, een woord vet hebt gemaakt met de werkbalk en een regel hebt
    bijgezet: een `<div>` per nieuwe regel, `<b>` uit `execCommand('bold')` naast de `<strong>`
    die er al stond, en de `fbul`-klasse die `_md` zelf op de lijst zet.

    Deze invoer is één op één overgenomen uit een doorloop tegen de draaiende cockpit (HTTP POST
    op `/action`, niet alleen de functie): de opslag die daaruit kwam staat hieronder."""
    dd, st, a, mens = _dorp(tmp_path)
    cockpit2.dispatch(dd, "artefact_edit", {
        "csrf": ["TOK"], "aid": [a.id], "title": ["Four conditions v2"],
        "body_html": ['<h4>Four conditions</h4><ul class="fbul">'
                      '<li><strong>On the list.</strong> Het materiaal staat op de lijst.</li>'
                      '<li><em>Traceerbaar</em> tot de bron.</li>'
                      '<li><b>Nieuw punt</b> erbij getypt.</li></ul>'
                      '<div>Een slotzin met <del>doorhaling</del>.</div>'
                      '<div>En een regel die ik net toevoegde.</div>'],
        "next": ["/pagina"]}, username="b@t.nl")
    na = cockpit2._Stores(dd).att.get(a.id)
    assert na.body == ("## Four conditions\n"
                       "- **On the list.** Het materiaal staat op de lijst.\n"
                       "- *Traceerbaar* tot de bron.\n"
                       "- **Nieuw punt** erbij getypt.\n"
                       "Een slotzin met ~~doorhaling~~.\n"
                       "En een regel die ik net toevoegde.")
    assert na.title == "Four conditions v2"


def test_geplakte_rommel_komt_niet_in_de_opslag(tmp_path):
    """Wat de browser ook terugstuurt — een half Word-document, een script — er wordt tekst van
    gemaakt. Fail-closed, en de tweede helft van dezelfde belofte als in `test_md_bron.py`."""
    dd, st, a, mens = _dorp(tmp_path)
    cockpit2.dispatch(dd, "artefact_edit", {
        "csrf": ["TOK"], "aid": [a.id],
        "body_html": ["<script>alert(1)</script><font face='Arial'>uit Word</font>"],
        "next": ["/pagina"]}, username="b@t.nl")
    na = cockpit2._Stores(dd).att.get(a.id)
    assert "<script" not in na.body and "font" not in na.body
    assert "uit Word" in na.body


def test_het_oude_markdown_pad_werkt_onveranderd(tmp_path):
    """Een tool en een policy hebben géén inline editor en sturen nog steeds `body` als markdown.
    Die tak mag door deze wijziging niet verschuiven — hij deelt de handler."""
    dd, st, a, mens = _dorp(tmp_path)
    cockpit2.dispatch(dd, "artefact_edit", {
        "csrf": ["TOK"], "aid": [a.id], "body": ["## Gewoon markdown\n- punt"],
        "next": ["/pagina"]}, username="b@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "## Gewoon markdown\n- punt"


def test_de_poort_geldt_ook_voor_de_nieuwe_ingang(tmp_path):
    """`body_html` is een nieuwe INGANG, geen nieuwe deur om de autorisatie heen.

    MET EEN DOMEIN sinds 26 september, want de poort hangt daar nu aan. Zonder domein mag elke
    herkende persoon bewerken — dan meet deze toets de verruiming in plaats van de ingang, en
    slaagt hij om de verkeerde reden. `Materials` hoort bij `creator_of_shoes`, en de opstelling
    hier geeft `b@t.nl` die rol niet."""
    dd, st, a, mens = _dorp(tmp_path, can_edit=False)
    st.att.update(a.id, domain="Materials")
    try:
        cockpit2.dispatch(dd, "artefact_edit", {
            "csrf": ["TOK"], "aid": [a.id], "body_html": ["<p>stiekem</p>"],
            "next": ["/pagina"]}, username="b@t.nl")
    except Exception as e:                                   # noqa: BLE001
        assert "Forbidden" in type(e).__name__ or "mag" in str(e).lower()
    assert "stiekem" not in (cockpit2._Stores(dd).att.get(a.id).body or "")


# ── 4. Geen tweede bewerkpad ─────────────────────────────────────────────────
def test_de_notes_tab_bewerkt_de_note_niet_meer_zelf(tmp_path):
    """Een note IS een wiki-pagina. Zou de Notes-tab zijn eigen formulier houden, dan zijn er twee
    bewerkpaden voor hetzelfde object — en die gaan uiteen lopen zodra er aan één iets verandert.
    De tab wijst nu naar de pagina; een TOOL houdt zijn formulier wel, want dat is geen pagina."""
    from nooch_village.views.overview import _artefact_own_card
    dd, st, a, mens = _dorp(tmp_path)
    kaart = _artefact_own_card(a, "TOK", True)
    assert "data-qadd-inline" not in kaart and "name='body'" not in kaart
    assert wiki.pagina_url(a.id) in kaart and "Edit on its page" in kaart

    tool = st.att.add(st.records.all()[0].id, "tool", title="Een tool", url="https://x.nl")
    kaart_tool = _artefact_own_card(tool, "TOK", True)
    assert "data-qadd-inline" in kaart_tool, "een tool houdt zijn eigen formulier"


# ── De bedrading ─────────────────────────────────────────────────────────────
def test_de_editor_is_bedraad_in_het_gedeelde_bestand():
    """In `nooch.js`, niet als inline `<script>`: een script uit `innerHTML` draait niet, en die
    les is één dag oud (de checklist-microinteractie die stil faalde in de modal)."""
    # OP `#wiki-form` EN NIET MEER OP `data-wiki-start`: die knop bestaat sinds 26 september niet
    # meer, want bewerken is de stand voor wie mag bewerken. Het formulier is nu het haakje én de
    # poort — zonder bewerkrecht rendert de server het niet, en dan zet de browser niets aan.
    assert '#wiki-form' in JS and "wikiEdit(root)" in JS


def test_plakken_gaat_als_platte_tekst():
    """Zonder dit brengt één plakactie uit Word een halve stylesheet mee. De server gooit die toch
    weg — maar dan zie je pas ná het opslaan dat je opmaak verdwenen is."""
    assert "paste" in JS and "insertText" in JS and "text/plain" in JS


def test_de_werkbalk_schrijft_tags_en_geen_stijlen():
    """`styleWithCSS` op false is de reden dat dit zonder editor-library kan: mét CSS levert de
    browser `<span style="font-weight:bold">`, en dat is geen tag die de server kent — de
    vetgedrukte tekst zou bij het opslaan gewoon gewone tekst worden."""
    assert 'execCommand("styleWithCSS", false, false)' in JS


#: Wat `execCommand` WERKELIJK oplevert, per commando, per browser. Niet één vorm per knop maar
#: alle vormen die in het wild voorkomen — dat onderscheid is precies waar de vorige versie van
#: deze test op stukging (zie `test_doorhalen_overleeft_het_opslaan` hieronder).
_ECHTE_UITKOMSTEN = {
    "bold": ("<b>x</b>", "<strong>x</strong>"),
    "italic": ("<i>x</i>", "<em>x</em>"),
    # Chrome: <strike>. Firefox: <strike> of <s>. Safari: <s>. Alle drie moeten door.
    "strikeThrough": ("<strike>x</strike>", "<s>x</s>", "<del>x</del>"),
    "insertUnorderedList": ("<ul><li>x</li></ul>", '<ul class="fbul"><li>x</li></ul>'),
    "formatBlock": ("<h4>x</h4>",),
    # INLINE CODE MAKEN WÍJ ZELF (25 september 2026). Er is geen `execCommand` voor, dus
    # `inlineCode()` in `nooch.js` plakt de selectie terug met `insertHTML`. Gemeten in Chrome op
    # de harness: `<code>gewone</code>`, met precies één `<code>` en zonder omhulsel eromheen.
    #
    # WAT DE METING ERBIJ LIET ZIEN: Chrome vervangt de spaties NAAST de invoeging door `&nbsp;`
    # (`Een&nbsp;<code>gewone</code>&nbsp;alinea`). De rondgang overleeft dat, maar er zou een
    # onzichtbaar ander teken in de opgeslagen markdown belanden dan de schrijver typte. Daarom
    # haalt `ontharde()` die randtekens weg; de vorm hieronder is wat er ná die stap staat.
    "nvCode": ("<code>x</code>",),
    # LINK MAKEN WIJ OOK ZELF (26 september 2026). `createLink` bestaat wél, maar hij heeft een
    # adres nodig en de browser levert daar niets voor; `nooch.js` maakt eerst de `<a>` en vult
    # het adres daarna via de link-kaart in. Wat er dan staat is een gewone link, en die moet de
    # weg terug als markdown-link teruglezen — anders is hij na één bewerkronde platte tekst.
    #
    # DRIE VORMEN, want ze komen alle drie voor: zoals `_md` hem rendert (met target en rel), en
    # zoals `createLink` hem in Chrome en Firefox achterlaat (alleen href).
    "nvLink": ("<a href='https://x.nl' target='_blank' rel='noopener'>x</a>",
               '<a href="https://x.nl">x</a>',
               "<a href='https://x.nl'>x</a>"),
}

#: Wat er in de bron hoort te staan als de knop gewerkt heeft. `x` alleen = de opmaak is weg.
_VERWACHT = {"bold": "**x**", "italic": "*x*", "strikeThrough": "~~x~~",
             "insertUnorderedList": "- x", "formatBlock": "## x", "nvCode": "`x`",
             "nvLink": "[x](https://x.nl)"}


def test_de_werkbalk_gebruikt_alleen_tags_die_de_omzetter_kent():
    """DEZE TEST STOND EERST TE LIEGEN, en dat kostte een live bug. Hij voerde `<del>x</del>` in
    als "wat de strikethrough-knop oplevert" — een AANNAME over de browser, opgeschreven als
    meting. Chrome levert `<strike>`, die tag viel buiten de whitelist, en doorhalen werd bij het
    opslaan stilletjes platte tekst. Fail-closed deed precies wat het moest; de tag hoorde er
    alleen in.

    Nu voert hij per knop ELKE vorm in die een browser werkelijk produceert, en toetst hij niet
    "er komt iets anders dan x uit" maar wat er exact in de bron hoort te staan."""
    from nooch_village.cockpit2_util import _OPMAAK_KNOPPEN, _md_naar_bron
    for cmd, _arg, _label, _titel in _OPMAAK_KNOPPEN:
        if not cmd:
            continue
        assert cmd in _ECHTE_UITKOMSTEN, f"knop {cmd} heeft geen gemeten uitkomst"
        for html in _ECHTE_UITKOMSTEN[cmd]:
            assert _md_naar_bron(html).strip() == _VERWACHT[cmd], (
                f"{cmd} levert {html} en dat wordt {_md_naar_bron(html)!r} "
                f"in plaats van {_VERWACHT[cmd]!r} — de opmaak valt bij het opslaan weg")


def test_doorhalen_overleeft_het_opslaan(tmp_path):
    """DE LIVE BUG, als test. Op village.nooch.earth: doorhalen wérkte zichtbaar tijdens het
    bewerken en was na opslaan en herladen weg — zonder foutmelding, want er ging niets kapot.
    De drie vormen gaan hier door de hele keten: HTML in, markdown in de opslag, opmaak terug op
    het scherm."""
    from nooch_village.cockpit2_util import _md
    for html in _ECHTE_UITKOMSTEN["strikeThrough"]:
        dd, st, a, mens = _dorp(tmp_path / html[:3].strip("<"))
        cockpit2.dispatch(dd, "artefact_edit", {
            "csrf": ["TOK"], "aid": [a.id], "body_html": [f"Een zin met {html} erin"],
            "next": ["/pagina"]}, username="b@t.nl")
        bron = cockpit2._Stores(dd).att.get(a.id).body
        assert bron == "Een zin met ~~x~~ erin", f"{html} ging verloren: {bron!r}"
        assert "<del>x</del>" in _md(bron), "en op het scherm komt hij niet terug"


def test_formatblock_geeft_zijn_argument_in_punthaken_door():
    """`formatBlock` met "h4" doet in Chrome en Safari niets: geen fout, geen effect. Alleen met
    "<h4>" maakt hij een kop. Bij de klik-doorloop had de H-knop inderdaad geen zichtbaar effect.

    Dit is dezelfde soort fout als bij `strike`: een aanname over de browser-API die nergens werd
    getoetst omdat hij in geen enkele Python-assertie voorkwam.

    DE TOETS IS MEEVERHUISD MET ZIJN ONDERWERP (26 september 2026). Hij las `_OPMAAK_KNOPPEN`,
    maar daar staat sinds deze stap geen `formatBlock` meer in: koppen horen exclusief in het
    blokmenu, want twee wegen naar dezelfde handeling lopen uiteen. De val is er niet minder om —
    `BLOK_MENU` heeft drie `formatBlock`-items — dus toetst hij ze daar, en alle drie."""
    from nooch_village.cockpit2_util import BLOK_MENU, _OPMAAK_KNOPPEN
    assert not [c for c, *_ in _OPMAAK_KNOPPEN if c == "formatBlock"], \
        "formatBlock staat weer in de opmaak-werkbalk én in het blokmenu"
    args = [a for _t, _l, cmd, a in BLOK_MENU if cmd == "formatBlock"]
    assert len(args) >= 3, "het blokmenu kent geen koppen meer"
    from nooch_village.cockpit2_util import blok_menu
    sjabloon = blok_menu()
    for arg in args:
        assert arg.startswith("<") and arg.endswith(">"), \
            f"zonder punthaken maakt formatBlock geen kop: {arg!r}"
        # EN HET ARGUMENT MOET DE BROWSER OOK BEREIKEN. Het reist als attribuut mee in het
        # sjabloon; klopt de tabel wel maar het sjabloon niet, dan doet de knop alsnog niets.
        veilig = arg.replace("<", "&lt;").replace(">", "&gt;")
        assert f"data-wiki-arg='{veilig}'" in sjabloon, \
            f"het sjabloon draagt {arg!r} niet"
