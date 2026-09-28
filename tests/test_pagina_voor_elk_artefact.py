"""Elk artefact dat de wiki-index toont, heeft ook een pagina (23 september 2026).

WAT ER STUK WAS, gemeten op productie en niet bedacht. `/wiki` linkt elk artefact naar
`/pagina?id=…`, maar `render_pagina` liet alleen `kind="note"` door. Op prod gaf dat 28 links naar
"Page not found", verdeeld over 14 artefacten: 9 actieve policies en 5 tools. (28 links, 14
artefacten: de index toont elk item twee keer — links in de domeinkolom, rechts als kaart.) De
content bestond wél; alleen de poort was te smal.

DE POORT IS NU ÉÉN LIJST. Welke soorten een pagina krijgen staat niet hier en niet in de view,
maar in `attachments.ARTEFACT_KINDS` — dezelfde lijst waar de index zijn chips uit haalt. Komt er
ooit een vierde soort bij, dan krijgt die automatisch een pagina in plaats van een dode link. Dat
is `reference, don't copy` op een verzameling in plaats van op een getal.

MAAR EEN POLICY IS GEEN NOTE, en daarom is dit méér dan een verruimde `if`. Gemeten over de 14
artefacten op prod:

    policy   body 115–4350 tekens · ALTIJD een `domain` · nooit een url · 0 feiten · 0 [[links]]
    tool     ALTIJD een url · body 0–392 tekens (één is helemaal leeg) · 0 feiten · 0 [[links]]

Drie dingen die de note-pagina doet, kan een policy of tool dus niet:

  1. **Feiten.** Ze leven in `meta["feiten"]`, en `artefacts._feiten_van` geeft voor een
     niet-note bewust een lege lijst terug. Een feiten-formulier op een policy zou feiten
     opleveren die de context-laag nooit leest — zichtbaar op het scherm, onzichtbaar waar het
     telt.
  2. ~~**`[[links]]` en backlinks.**~~ INGETROKKEN OP 28 SEPTEMBER 2026. Hier stond "`wiki.paginas`
     is notes-only, dus een verwijzing vanuit een policy komt nergens op uit". Dat klopte tot
     24 september, toen `wiki.verwijsbaar` note, policy én tool ging omvatten ("verwijzen doe je
     naar alles wat een permalink heeft") — en `render_pagina` gebruikt díe lijst. Verwijzingen en
     backlinks werken dus voor elke soort; `test_een_policy_heeft_echte_backlinks` voert het uit.
  3. ~~**Bewerken.**~~ INGETROKKEN. Eerst verhuisde het bewerken naar de permalink (27 september),
     daarna kreeg elke soort dezelfde inline editor (28 september). Wat overblijft is dat een
     policy een `domain` heeft en een tool een `url`; die krijgen een eigen rij in het
     metadata-raster in plaats van een eigen formulier.

Punt 3 is de gevaarlijkste, want hij faalt STIL: `_act_artefact_edit` is niet op soort gepoort en
zou een policy gewoon opslaan, maar `pagina_feit_add`, `pagina_feit_del` en `pagina_voorstel` zijn
dat wél. Een pagina die die formulieren toont, belooft iets wat de actie daarna weigert met
"✗ page not found". Daarom toetst dit bestand niet alleen wat er staat, maar vooral wat er NIET
staat.
"""
from __future__ import annotations

import re

from nooch_village import cockpit2, wiki
from nooch_village.attachments import ARTEFACT_KINDS
from nooch_village.views.wiki import _WIKI_SOORTEN, render_pagina, render_wiki_index

#: Elke link naar een permalink, zoals de index hem schrijft.
_PAGINA_LINK = re.compile(r"/pagina\?id=([^'\"&]+)")


def _dorp(tmp_path):
    """Eén rol met één artefact van elke soort — de drie die de index toont."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    note = st.att.add(rol, "note", title="Hoe we beslissen", body="Een **note** met tekst.")
    pol = st.att.add(rol, "policy", title="Geld", body="Een *policy* met tekst.",
                     domain="Money")
    tool = st.att.add(rol, "tool", title="Boekhouding", body="Waar de cijfers staan.",
                      url="https://example.org/boek")
    mens = st.people.add("Beheerder", "b@t.nl")
    st.assign.assign(rol, "person", mens.id)
    return dd, st, {"note": note, "policy": pol, "tool": tool}, mens


def _pagina(st, a, *, can_edit: bool = True) -> str:
    return render_pagina(st, a.id, csrf_token="TOK",
                         username="b@t.nl" if can_edit else "")


# ── 1. De keten tot het eind: geen enkele link uit de index is dood ──────────
def test_elke_link_in_de_index_levert_een_pagina_op(tmp_path):
    """DE TOETS DIE ERTOE DOET. Niet "de poort is verruimd" maar "loop de index af en open
    alles" — precies de fout die op prod maanden zichtbaar was zonder dat een toets viel."""
    dd, st, art, mens = _dorp(tmp_path)
    index = render_wiki_index(st, csrf_token="TOK")
    ids = sorted(set(_PAGINA_LINK.findall(index)))

    # ER STOND HIER `len(ids) == 3`, en dat mat de verkeerde kant: `_bootstrap` zaait zelf al
    # tools, dus het getal ging over het zaad en niet over de link-keten. Wat de toets bedoelt is
    # dat elke soort die de index TOONT er ook echt in staat.
    #
    # EN DAT IS SINDS 28 SEPTEMBER 2026 NIET MEER "TOOL". Gereedschap staat op `/tools`; de wiki
    # toont wat je LEEST. De keten-eis verandert daar niet door — hij verhuist mee, zie
    # `test_de_toolpagina_blijft_bereikbaar` hieronder.
    assert {art[k].id for k in ("note", "policy")} <= set(ids), (
        f"niet elke getoonde soort staat in de index: {ids}")
    assert art["tool"].id not in ids, "de index toont nog steeds gereedschap"

    dood = [i for i in ids if "Page not found" in render_pagina(st, i, csrf_token="TOK",
                                                               username="b@t.nl")]
    assert not dood, f"dode links in de wiki-index: {dood}"


def test_de_toolpagina_blijft_bereikbaar(tmp_path):
    """DE HELFT DIE NIET MAG VERDWIJNEN. Een tool is uit de wiki-INDEX weg, niet van het web: zijn
    permalink werkt gewoon, en `/tools` linkt ernaartoe. Zou dat wegvallen, dan is "hij hoeft niet
    meer via de wiki vindbaar te zijn" stilzwijgend "hij is nergens meer te openen" geworden."""
    from nooch_village.views.tools import render_tools
    dd, st, art, mens = _dorp(tmp_path)
    aid = art["tool"].id
    assert "Page not found" not in render_pagina(st, aid, csrf_token="TOK", username="b@t.nl")
    tools = render_tools(st, csrf_token="TOK", username="b@t.nl")
    assert art["tool"].title in tools
    # Met een url linkt de kaart naar het scherm; zonder url naar de permalink. Deze heeft er een.
    assert art["tool"].url in tools


def test_de_index_toont_een_bewuste_deelverzameling():
    """OMGEDRAAID OP 28 SEPTEMBER 2026, en het verschil is de moeite waard.

    Hier stond dat de chips van de index EXACT `ARTEFACT_KINDS` moeten zijn — geschreven toen het
    uiteenlopen van die twee lijsten de bug was (28 dode links). Wat toen ontbrak was een derde
    mogelijkheid: een soort die WEL een pagina heeft maar NIET in deze index thuishoort. Een tool is
    dat geval, en `/tools` is zijn plek.

    Wat de toets nu bewaakt is daarom niet gelijkheid maar de RICHTING: de index mag alleen
    soorten tonen die ook echt een pagina hebben. Andersom (een soort zonder index-chip) is een
    keuze; dit is de fout."""
    uit_index = {k for k, _ in _WIKI_SOORTEN[1:]}
    assert uit_index <= set(ARTEFACT_KINDS), (
        f"de index toont {uit_index - set(ARTEFACT_KINDS)}, en dat zijn geen artefact-soorten")
    assert "tool" not in uit_index, "gereedschap staat op /tools, niet in de wiki"
    assert uit_index == {"note", "policy"}


# ── 2. Wat een policy-pagina wél toont ───────────────────────────────────────
def test_de_policy_pagina_toont_zijn_domein_en_zijn_tekst(tmp_path):
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["policy"])
    assert "Page not found" not in html
    assert "<em>policy</em>" in html, "de body wordt niet als markdown gerenderd"
    assert "Money" in html, "het domein van een policy hoort op zijn pagina"
    assert art["policy"].id in html, "het id-chipje ontbreekt"


def test_de_tool_pagina_toont_zijn_url_als_link(tmp_path):
    """Een tool ZONDER zijn url is minder waard dan de kaart waar hij vandaan komt — daar staat
    hij wel (`_artefact_head`). Dat is het veld waar een tool om draait."""
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["tool"])
    assert "https://example.org/boek" in html
    assert "rel='noopener'" in html or 'rel="noopener"' in html


def test_een_tool_zonder_tekst_krijgt_een_pagina_en_geen_leegte(tmp_path):
    """Op prod heeft TOOL-WEBSIT-001 een lege body. Een pagina die dan niets zegt, ziet eruit
    als een fout in plaats van als een tool waar nog geen uitleg bij staat."""
    dd, st, art, mens = _dorp(tmp_path)
    rol = st.records.all()[0].id
    leeg = st.att.add(rol, "tool", title="Website", body="", url="https://nooch.earth")
    html = _pagina(st, leeg)
    assert "Page not found" not in html
    assert "no text yet" in html.lower()
    assert "https://nooch.earth" in html, "de url blijft het punt van de pagina"


# ── 3. Wat een policy- en tool-pagina NIET mag tonen ─────────────────────────
def test_geen_formulier_dat_de_actie_daarna_weigert(tmp_path):
    """DE VAL. `pagina_feit_add`, `pagina_feit_del` en `pagina_voorstel` poorten op
    `kind == "note"` en antwoorden op alles anders met "✗ page not found". Een pagina die die
    formulieren toont, belooft iets wat niet kan."""
    dd, st, art, mens = _dorp(tmp_path)
    for soort in ("policy", "tool"):
        html = _pagina(st, art[soort])
        for actie in ("pagina_feit_add", "pagina_feit_del", "pagina_voorstel"):
            assert f"value='{actie}'" not in html, (
                f"de {soort}-pagina toont {actie}, maar die actie weigert een {soort}")


def test_de_policy_pagina_bewerkt_op_dezelfde_manier_als_een_note(tmp_path):
    """DE TWEEDE HELFT VAN DEZELFDE OPRUIMING (28 september 2026).

    Op 27 september verhuisde het bewerken van de eigenaar-rol naar de permalink: één bewerkpad
    per artefact. Wat er toen nog stond was een EENVOUDIG formulier onder de tekst — je las de
    policy bovenin en typte hem eronder over, in een tweede kopie van dezelfde inhoud. Dat is
    precies het model "lezen is de stand, bewerken is een modus" dat de note-pagina op 26 september
    al achter zich liet.

    Nu is er één editor voor alle drie de soorten. WAT ER NIET BIJ KOMT staat in de toets hierboven
    (`test_geen_formulier_dat_de_actie_daarna_weigert`): feiten en voorstellen zijn op soort
    gepoort en horen hier dus niet."""
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["policy"], can_edit=True)
    assert "id='wiki-body'" in html, "de inline editor hoort hier nu juist wél"
    assert "id='wiki-form'" in html, "zonder opslaan-balk is de tekst niet te bewaren"
    assert "value='artefact_edit'" in html
    assert "pagina_feit_add" not in html, "de feiten van een note horen hier niet"
    assert "tab=policies" in html, "er staat geen weg terug naar de tab van de eigenaar"


def test_de_tool_pagina_wijst_naar_zijn_eigen_tab(tmp_path):
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["tool"])
    assert "tab=tools" in html


def test_wie_niet_mag_bewerken_krijgt_de_weg_erheen_niet(tmp_path):
    """Zelfde regel als op de note-pagina: de poort staat vóór de belofte. Een knop die toch
    afketst op `_artefact_gate` is erger dan geen knop."""
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["policy"], can_edit=False)
    assert "Page not found" not in html, "lezen mag altijd"
    assert "Money" in html, "de inhoud blijft gewoon leesbaar"
    # ER STOND HIER `"✎" not in html`, en dat mat niets: de knop schrijft de entity `&#9998;`,
    # nooit het letterlijke teken. Een mutatie die de knop ALTIJD toonde bleef daardoor groen.
    #
    # DAARNA STOND ER `"Edit on the role" not in html`, en sinds het bewerken NAAR deze pagina
    # verhuisde mat óók dat niets meer: die zin bestaat hier niet eens meer, dus de toets was
    # altijd groen. Nu op het formulier zelf — het ding dat er niet hoort te staan.
    assert "value='artefact_edit'" not in html, "een bewerkformulier voor wie niet mag bewerken"
    assert "value='artefact_archive'" not in html, "een archiveerknop voor wie niet mag bewerken"


# ── 4. De note-pagina verandert niet ─────────────────────────────────────────
def test_de_note_pagina_houdt_zijn_editor(tmp_path):
    """De verruiming mag de bestaande pagina niet aanraken — dat is waar alle brok-1/2/3-toetsen
    op staan."""
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["note"])
    assert "id='wiki-body'" in html
    assert "value='artefact_edit'" in html
    assert "data-blok-soorten" in html, "het blokmodel hoort alleen op de note-pagina"


def test_het_blokmodel_geldt_nu_voor_elke_soort(tmp_path):
    """Het blok-idioom hoort bij de EDITOR, niet bij de soort. Nu alle drie de soorten dezelfde
    editor gebruiken, heeft een policy dus ook een greep en een /-menu."""
    dd, st, art, mens = _dorp(tmp_path)
    for soort in ("note", "policy", "tool"):
        assert "data-blok-soorten" in _pagina(st, art[soort]), soort


def test_alleen_de_note_krijgt_de_feiten_knop_in_het_menu(tmp_path):
    """HET ENIGE MENU-ITEM DAT WÉL OP SOORT POORT. `{{facts}}` levert bij een policy een blok op
    dat nooit gevuld kan worden: `artefacts._feiten_van` geeft voor een niet-note een lege lijst en
    `pagina_feit_add` antwoordt met "✗ page not found". De knop staat er daarom niet.

    BACKLINKS BLIJVEN WÉL, en dat is nagemeten en niet aangenomen: `wiki.verwijsbaar` neemt sinds
    24 september note, policy én tool mee, dus een verwijzing NAAR een policy levert daar een echte
    backlink op. Zie `test_een_policy_heeft_echte_backlinks`."""
    dd, st, art, mens = _dorp(tmp_path)
    note, pol = _pagina(st, art["note"]), _pagina(st, art["policy"])
    assert ">Feiten<" in note and ">Backlinks<" in note
    assert ">Feiten<" not in pol, "de feiten-knop hoort niet in het menu van een policy"
    assert ">Backlinks<" in pol, "backlinks werken wél voor een policy"


def test_een_policy_heeft_echte_backlinks(tmp_path):
    """DE PREMISSE DIE NIET MEER KLOPTE. In de kop van dit bestand stond "`wiki.paginas` is
    notes-only, dus een verwijzing vanuit een policy zou nergens op uitkomen". Dat was waar tot
    24 september, toen `wiki.verwijsbaar` alle drie de soorten ging omvatten — en `render_pagina`
    gebruikt díe lijst. Hier uitgevoerd in plaats van geredeneerd."""
    dd, st, art, mens = _dorp(tmp_path)
    rol = st.records.all()[0].id
    st.att.add(rol, "note", title="Verwijzer", body="Zie [[Geld]] voor de regels.")
    html = _pagina(st, art["policy"])
    assert "Verwijzer" in html, "de note die naar deze policy linkt staat er niet bij"


def test_de_tool_pagina_laat_zijn_url_bewerken(tmp_path):
    """Een tool heeft een url en een note niet. Nu de inline editor alleen titel en tekst kent,
    zou dat veld nergens meer te wijzigen zijn — het krijgt daarom een eigen rij in het
    metadata-raster, net als het domein."""
    dd, st, art, mens = _dorp(tmp_path)
    kan = _pagina(st, art["tool"], can_edit=True)
    assert "name='url'" in kan and "value='https://example.org/boek'" in kan
    niet = _pagina(st, art["tool"], can_edit=False)
    assert "name='url'" not in niet, "een invoerveld voor wie niet mag bewerken"
    assert "https://example.org/boek" in niet, "het adres blijft wel gewoon te openen"


# ── 5. Wat er nog steeds niet bestaat ────────────────────────────────────────
def test_een_onbekend_id_blijft_een_nette_melding(tmp_path):
    dd, st, art, mens = _dorp(tmp_path)
    html = render_pagina(st, "BESTAAT-NIET-001", csrf_token="TOK", username="b@t.nl")
    assert "Page not found" in html


def test_de_melding_belooft_niet_langer_dat_een_pagina_altijd_een_note_is(tmp_path):
    """De oude tekst zei "A page is a role note". Sinds een policy en een tool er ook één
    krijgen, is dat onjuist — en een onjuiste uitleg stuurt iemand naar de verkeerde tab."""
    dd, st, art, mens = _dorp(tmp_path)
    html = render_pagina(st, "BESTAAT-NIET-001", csrf_token="TOK", username="b@t.nl")
    assert "A page is a role note" not in html


def test_een_soort_buiten_de_lijst_krijgt_geen_pagina(tmp_path):
    """De poort blijft fail-closed: alleen wat in `ARTEFACT_KINDS` staat. Een `metric` of
    `checklist` (het model noemt ze) heeft geen eigenaar-tab en dus geen weg terug."""
    dd, st, art, mens = _dorp(tmp_path)
    rol = st.records.all()[0].id
    vreemd = st.att.add(rol, "metric", title="Bezoekers", body="Een getal.")
    assert "metric" not in ARTEFACT_KINDS                   # anders meet deze toets niets
    html = render_pagina(st, vreemd.id, csrf_token="TOK", username="b@t.nl")
    assert "Page not found" in html
