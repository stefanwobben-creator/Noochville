"""De paginakop: de titel leidt, de rest is bijzaak (25 september 2026).

WAT ER STOND, op `NOTE-STRATE-002` op prod:

    📄 [NOTE-STRATE-002] Company Information [Strategic Lead & Founder Steward]
    Owned by this role — everyone reads, the role curates. Last edited: …
    DOMAIN [bibliotheek ▾] [Move]

Vier dingen mis, en ze hebben één patroon: TECHNIEK STAAT OP DE PLEK VAN INHOUD.

1. Het pagina-ID stond vóór de titel, groot. Dat is een interne sleutel, geen onderwerp. Hij
   VERDWIJNT NIET — hij wordt in gesprekken en documenten als verwijzing gebruikt — maar hij hoort
   klein en secundair.
2. De eigenaar-rol stond als los tagje naast de titel, terwijl de zin eronder "this role" zei
   zonder hem te noemen. Twee fragmenten van één ding. Nu één zin: "Owned by <rol> — …".
3. "DOMAIN" was een kale dropdown zonder uitleg. Hij is NIET overbodig — zie hieronder — dus hij
   krijgt een label dat zegt wat hij doet, plus waar de pagina nú valt.
4. "Move" zei niet wat er verplaatst wordt. Dat is de pagina binnen de wiki-STRUCTUUR, niet de
   inhoud.

WAAROM HET DOMEIN BLIJFT, gemeten op de 122 artefacten van prod voordat ik iets aanraakte:

  - 14 artefacten dragen een eigen `domain` (11 policies, 2 notes, 1 tool);
  - 10 pagina's verschuiven van BAKJE als het veld verdwijnt, 8 daarvan naar Overig;
  - 11 policy-ID's zijn uit de domeinslug GEMUNT (`MONEY-001`, `DESIGNSYSTEM-001`, …) en een ID is
    een permalink;
  - 33 changelog-regels loggen tegen `domain:<x>` in plaats van `role:<y>`.

Stefans eigen inschatting was "waarschijnlijk kan die weg". Dat is met de meting weerlegd, en
daarom is het label de uitkomst en niet de verwijdering.
"""
from __future__ import annotations

import re

from nooch_village import cockpit2
from nooch_village.views.wiki import render_pagina


def _dorp(tmp_path, *, domeinen=("bibliotheek", "onderzoeksmethode"), can_edit=True):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    rec = st.records.get(rol)
    rec.definition.domains = list(domeinen)
    st.records.put(rec)
    mens = st.people.add("Beheerder", "b@t.nl")
    if can_edit:
        st.assign.assign(rol, "person", mens.id)
    a = st.att.add(rol, "note", title="Company Information", body="tekst",
                   domain=domeinen[0] if domeinen else "")
    return dd, st, a, rec


def _pagina(tmp_path, **kw):
    dd, st, a, rec = _dorp(tmp_path, **kw)
    return render_pagina(st, a.id, csrf_token="TOK",
                         username="b@t.nl" if kw.get("can_edit", True) else ""), a, rec


# ── 1. De titel leidt ────────────────────────────────────────────────────────
def test_het_id_staat_niet_meer_in_de_kop(tmp_path):
    """DE EIS. Een interne sleutel hoort niet de eerste plek te krijgen."""
    html, a, _ = _pagina(tmp_path)
    h1 = html.split("<h1>")[1].split("</h1>")[0]
    assert a.id not in h1, f"het ID staat nog in de kop: {h1}"


def test_de_titel_staat_er_wel_en_blijft_bewerkbaar(tmp_path):
    """Hij is het enige inhoudelijke element in de kop — en sinds #567 ook het invoerveld."""
    html, a, _ = _pagina(tmp_path)
    h1 = html.split("<h1>")[1].split("</h1>")[0]
    assert "Company Information" in h1
    assert "id='wiki-titel'" in h1, "de titel is niet meer het bewerkbare element"


def test_het_id_staat_zichtbaar_in_het_metadata_blok(tmp_path):
    """Hij verdwijnt niet: het ID wordt in gesprekken en documenten als verwijzing gebruikt (in
    het ontwerpdocument zelf ook). Alleen niet meer op de plek van het onderwerp.

    OP DE ZICHTBARE PLEK, en dat is het verschil dat deze toets eerst miste. Hij zei alleen "het
    ID komt ergens in de HTML voor", en dat is altijd waar: hij staat in `wiki.pagina_url(a.id)`
    in elk verborgen `next`-veld. Een mutatie die hem uit de kop HAALDE bleef daardoor groen.

    IN PR 1 STOND HIJ IN DE HERKOMST-REGEL, in PR 2 in het metadata-blok — dat was de bedoelde
    eindplek; de kopbalk was de tussenstap."""
    html, a, _ = _pagina(tmp_path)
    assert "<span class='dk'>Id</span>" in html, "er is geen Id-rij in het metadata-blok"
    rij = html.split("<span class='dk'>Id</span>")[1][:200]
    assert a.id in rij, "het ID staat nergens waar je het kunt lezen"


# ── 2. De eigenaar is één zin ────────────────────────────────────────────────
def test_de_eigenaar_heeft_een_eigen_rij_met_zijn_naam(tmp_path):
    """"Owned by this role" noemde de rol niet; het tagje ernaast noemde hem zonder zin.

    IN PR 1 werd dat één zin in de kopbalk. In PR 2 is het een rij in het metadata-blok, met de
    governance-regel als uitleg eronder — want de zin stond toen in de kop én de eigenaar in het
    blok, en dat is opnieuw twee plekken voor hetzelfde."""
    html, _a, rec = _pagina(tmp_path)
    assert "<span class='dk'>Owner</span>" in html
    rij = html.split("<span class='dk'>Owner</span>")[1][:400]
    assert rec.definition.name in rij, "de rolnaam staat niet in de eigenaar-rij"
    assert "this role curates" in rij, "de governance-regel hoort bij de eigenaar"
    assert "Owned by this role" not in html, "de oude zin staat er nog"


def test_de_rol_blijft_aanklikbaar(tmp_path):
    """Hij was een chip met een link naar de rol; die weg mag niet verdwijnen bij het samenvoegen."""
    html, a, _ = _pagina(tmp_path)
    rij = html.split("<span class='dk'>Owner</span>")[1][:400]
    assert f"/node?id={a.anchor}" in rij


def test_de_rol_staat_niet_meer_los_naast_de_titel(tmp_path):
    """Anders staat hij er twee keer, en dat is het probleem verdubbeld."""
    html, _a, rec = _pagina(tmp_path)
    h1 = html.split("<h1>")[1].split("</h1>")[0]
    assert rec.definition.name not in h1


# ── 3. Het domein zegt wat het doet ──────────────────────────────────────────
def test_het_domein_veld_bestaat_nog(tmp_path):
    """NIET VERWIJDERD, en dat is een gemeten besluit: 10 pagina's zouden van bakje verschuiven,
    11 policy-ID's zijn eruit gemunt. Zie de kop van dit bestand."""
    html, _a, _ = _pagina(tmp_path)
    assert "name='domain'" in html


def test_het_domein_zegt_waar_het_over_gaat(tmp_path):
    """Een kale "DOMAIN" zegt niets. Wat het doet: bepalen waar de pagina in de wiki-structuur
    valt."""
    # IN DE VOET, want daar staat het veld sinds #602 — en de kopbalk die deze toets las, bestaat
    # sinds 26 september niet meer (de "Edit page"-knop was het laatste wat erin stond).
    html, _a, _ = _pagina(tmp_path)
    voet = html.split("class='wiki-meta'")[1]
    assert "wiki structure" in voet.lower(), "het domein legt niet uit wat het doet"


def test_het_domein_toont_waar_de_pagina_nu_valt(tmp_path):
    """Het domein is een sleutel (`bibliotheek`), het BAKJE is wat je op de index ziet. Zonder dat
    tweede moet je `domeinen.DOMEIN_BAKJE` uit je hoofd kennen om de keuze te kunnen maken."""
    from nooch_village import domeinen
    html, a, _ = _pagina(tmp_path)
    bakje, _waarom = domeinen.bakje_van(a, [])
    assert domeinen.label(bakje) in html, f"het bakje ({bakje}) staat nergens"


def test_wie_niet_mag_bewerken_krijgt_geen_keuze_maar_wel_de_uitleg(tmp_path):
    """De poort staat vóór de belofte; lezen waar de pagina valt mag wel."""
    html, a, _ = _pagina(tmp_path, can_edit=False)
    assert "name='domain'" not in html
    assert "Move" not in html


# ── 4. Move zegt wat hij verplaatst ──────────────────────────────────────────
def _move_knop(html: str) -> str:
    """De openingstag van de Move-knop, gevonden via ZIJN FORMULIER.

    NIET VIA "DE EERSTE `artefact_edit`-KNOP OP DE PAGINA". Dat was het, en het klopte zolang het
    metadata-blok boven de editor stond; toen het op 26 september naar onderaan verhuisde vond
    dezelfde regex de Save-knop van de editor — die stuurt dezelfde actie. Drie toetsen sloegen
    daardoor aan op een knop die ze niet bedoelden. `.fieldform` is het formulier dat alleen het
    domein verzet, en dat verhuist met zijn onderwerp mee."""
    form = html.split("class='fieldform'")[1].split("</form>")[0]
    m = re.search(r"<button[^>]*value='artefact_edit'[^>]*>[^<]*</button>", form)
    assert m, "de Move-knop staat niet in zijn eigen formulier"
    return m.group(0)


def test_de_move_knop_zegt_wat_er_verplaatst_wordt(tmp_path):
    """"Move" alleen leest als "verplaats deze tekst". Het gaat om de plek van de PAGINA in de
    structuur van de wiki."""
    html, _a, _ = _pagina(tmp_path)
    # DE TEKST VAN DE KNOP, niet "de string Move komt ergens voor". Mijn eerste versie deed
    # `rstrip("</button>")` om de tag weg te halen, en `rstrip` strípt KARAKTERS en geen
    # substring — "Move" eindigt op een "e" die niet in die set zit, dus er ging niets af en de
    # toets slaagde op de oude knop.
    tekst = _move_knop(html).split(">", 1)[1].split("<")[0].strip()
    assert "Move" in tekst
    assert tekst != "Move", "de knop zegt nog steeds alleen 'Move'"


def test_de_move_knop_draagt_een_tooltip(tmp_path):
    """Voor wie de knoptekst kort houdt maar toch wil weten wat er gebeurt.

    OP DE KNOP ZELF. De eerste versie keek of er ergens in het formulier een `title=` stond — en
    die staat er ook op het `<form>`, zodat de hele rij hem toont. Een mutatie die hem van de KNOP
    haalde bleef daardoor groen, terwijl de knop juist het ding is waar je op mikt."""
    html, _a, _ = _pagina(tmp_path)
    knop = _move_knop(html)
    assert "title=" in knop, f"de knop draagt geen tooltip: {knop}"
    assert "wiki" in knop.lower(), "de tooltip zegt niet dat het om de wiki-structuur gaat"


# ── 5. Wat niet mag veranderen ───────────────────────────────────────────────
def test_er_is_geen_bewerkknop_meer_maar_wel_een_bewerkvlak(tmp_path):
    """DE KNOP IS WEG (26 september 2026), en dat is de hele wijziging: wie mag bewerken, bewerkt
    — zoals in een tekstverwerker. Deze toets heette "de bewerkknop blijft" en bewaakte precies
    het tegenovergestelde; hij meet nu waar het recht écht aan hangt.

    HET BEWERKVLAK IS DE POORT. `nooch.js` zet niets aan zonder `#wiki-form`, en dat formulier
    rendert alleen met bewerkrecht. Verdwijnt die koppeling, dan is de pagina voor iedereen
    bewerkbaar of voor niemand — daarom staat hij hier vast."""
    html, _a, _ = _pagina(tmp_path)
    assert "data-wiki-start" not in html, "de Edit page-knop staat er nog"
    assert "id='wiki-form'" in html, "er is geen bewerkvlak voor wie wel mag"


def test_zonder_bewerkrecht_blijft_de_pagina_leesbaar(tmp_path):
    """De andere kant van dezelfde poort: geen formulier, dus zet de browser niets aan."""
    dd, st, a, _rec = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="", username=None)
    assert "id='wiki-form'" not in html and "contenteditable" not in html


def test_de_blokstand_blijft_aan(tmp_path):
    """De hele bloklaag van de vorige sprint hangt hieraan."""
    html, _a, _ = _pagina(tmp_path)
    assert "data-blok-soorten" in html and "id='wiki-body'" in html


def test_een_policy_pagina_verandert_niet_van_vorm(tmp_path):
    """`_artefact_pagina` is een andere renderer; die komt in PR 2 aan de beurt."""
    dd, st, a, rec = _dorp(tmp_path)
    p = st.att.add(rec.id, "policy", title="Beleid", body="tekst", domain="bibliotheek")
    html = render_pagina(st, p.id, csrf_token="TOK", username="b@t.nl")
    assert p.id in html


def test_het_woord_domein_staat_er_maar_een_keer(tmp_path):
    """GEZIEN OP DE SCREENSHOT, NIET IN EEN TOETS — en precies waarom die screenshot sinds
    25 september bij "klaar" hoort. Mijn eerste versie zette de uitleg in een eigen `.att-lbl`,
    terwijl `_domain_field` zijn EIGEN label al rendert. Op het scherm stond toen:

        DOMAIN — WHERE THIS PAGE SITS IN THE WIKI STRUCTURE. NOW: OVERIG   DOMAIN [bibliotheek ▾]

    Twee keer hetzelfde woord naast elkaar — de dubbeling die deze PR juist weghaalt."""
    html, _a, _ = _pagina(tmp_path)
    # IN HET METADATA-BLOK, want daar staat het veld sinds PR 2. Deze toets keek naar
    # `wiki-kopacties`, en toen het formulier daaruit verhuisde mat hij een lege regio en slaagde
    # hij altijd — een mutatie die het eigen label van het veld terugzette bleef groen. Een toets
    # die met zijn onderwerp meeverhuist of anders stopt met meten: dit was het tweede.
    # OP DE ZICHTBARE TEKST, met de tags eruit. Een kale substring-telling telt `name='domain'`,
    # `id='f-domain-…'` en `aria-label='Domain'` mee en komt op vier — dat meet de markup, niet
    # wat iemand leest.
    import re as _re
    blok = html.split("class='dcol'")[1].split("</div></div>")[0]
    tekst = _re.sub(r"<[^>]+>", " ", blok).lower()
    assert tekst.count("domain") == 1, \
        f"het woord Domain staat {tekst.count('domain')}x op het scherm in plaats van 1x"


def test_de_uitleg_schreeuwt_niet(tmp_path):
    """`.att-lbl` is `text-transform:uppercase` — prima voor een kort veldlabel, fout voor een
    zin. De uitleg gebruikt de hint-klasse, die dat niet doet."""
    html, _a, _ = _pagina(tmp_path)
    zin = "Where this page sits in the wiki structure"
    assert zin in html
    regel = html[html.index(zin) - 120:html.index(zin)]
    assert "att-lbl" not in regel, "de uitleg staat in een klasse die alles in kapitalen zet"
    assert "wiki-hint" in regel


def test_de_hint_gebruikt_de_hele_precedentieregel(tmp_path):
    """`bakje_van` heeft vijf stappen en drie ervan hebben de recordboom nodig. Mijn eerste versie
    gaf een LEGE lijst mee, en dan zegt de hint "Overig" voor elke pagina zonder eigen domein —
    terwijl de index hem onder het domein van zijn rol toont.

    Gemeten: een note zonder eigen domein onder een rol met `Materials` geeft mét records
    `shoe-development`, zonder records `overig`. Een hint die liegt is erger dan geen hint."""
    from nooch_village import domeinen
    dd, st, _a, rec = _dorp(tmp_path, domeinen=("Materials",))
    zonder = st.att.add(rec.id, "note", title="Zonder eigen domein", body="x")
    html = render_pagina(st, zonder.id, csrf_token="TOK", username="b@t.nl")
    echt, _w = domeinen.bakje_van(zonder, st.records.all())
    assert echt == "shoe-development", "de opstelling meet niet wat hij denkt te meten"
    assert domeinen.label(echt) in html, "de hint toont een ander bakje dan de index"


# ── 6. Eén samenhangend blok, in het bestaande vocabulaire (PR 2) ────────────
def test_de_metadata_staat_in_een_raster_dat_de_app_al_heeft(tmp_path):
    """GEEN NIEUW VOCABULAIRE — dat was de opdracht. `.dcol` met `.dk`/`.dv` is het
    sleutel-waarde-raster dat de projectkaart al gebruikt."""
    html, _a, _ = _pagina(tmp_path)
    assert "class='dcol'" in html
    assert "class='dk'" in html and "class='dv'" in html


def test_alle_metadata_staat_bij_elkaar(tmp_path):
    """Het ontwerpdocument: "los verspreid rond de titel" wordt één sectie."""
    html, _a, _ = _pagina(tmp_path)
    blok = html.split("class='dcol'")[1].split("</div></div>")[0]
    for sleutel in ("Owner", "Domain", "Id", "Last edited"):
        assert f">{sleutel}</span>" in blok, f"{sleutel} staat niet in het blok"


def test_het_domein_formulier_staat_er_maar_een_keer(tmp_path):
    """GEVONDEN DOOR EEN BESTAANDE TOETS, niet door mij: na het invoegen van het metadata-blok
    stond het domein-formulier er TWEE keer — het blok rendert het, en de kopbalk deed het ook
    nog. `test_het_is_een_eigen_formulier_naast_de_blok_editor` telt de `artefact_edit`-vormen en
    sloeg aan op drie in plaats van twee."""
    html, _a, _ = _pagina(tmp_path)
    assert html.count("name='domain'") == 1


def test_de_uitleg_zit_in_de_cel_van_zijn_veld(tmp_path):
    """DE EIS: de zin moet zichtbaar BIJ het veld horen, niet los eronder hangen. In een
    `.dcol`-raster betekent dat: in dezelfde `.dv`-cel, zodat hij onder de dropdown uitlijnt in
    plaats van onder de hele rij."""
    html, _a, _ = _pagina(tmp_path)
    cel = html.split("<span class='dk'>Domain</span>")[1].split("</span>")
    hele_cel = html.split("<span class='dk'>Domain</span>")[1].split("<span class='dk'>")[0]
    assert "name='domain'" in hele_cel, "het veld staat niet in deze cel"
    assert "Where this page sits" in hele_cel, "de uitleg staat buiten de cel van zijn veld"


def test_verplaatsen_blijft_de_lichte_variant(tmp_path):
    """Gemeten stonden Move page en Edit page er ooit identiek bij; Move werd daarom `ghost`.

    DE VERGELIJKING IS VERVALLEN, de keuze niet. "Edit page" bestaat sinds 26 september niet meer
    — bewerken is de stand — dus er valt niets meer náást te leggen. Wat blijft: verplaatsen is een
    structuurwijziging in een voet vol administratie, en die hoort geen volle knop te zijn."""
    html, _a, _ = _pagina(tmp_path)
    assert "ghost" in _move_knop(html), "de Move-knop is zwaarder geworden dan hij was"


def test_het_veld_en_de_knop_staan_op_een_rij(tmp_path):
    """`.fieldform` is de klasse die de app daarvoor heeft, mét een eigen `.nu`-regel die de
    onderlijn bij het VELD laat in plaats van om de rij heen."""
    html, _a, _ = _pagina(tmp_path)
    assert "class='fieldform'" in html


def test_de_select_staat_op_dezelfde_voet_als_de_knop(tmp_path):
    """Gemeten in de browser: de select was 18px hoog met het browser-font en padding 0, de knop
    ernaast 30px. Dat verschil is wat "kale HTML-control" doet lijken. De maten stonden alleen in
    de specifiekere `.pside`-variant; nu in de gedeelde klasse."""
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1]
           / "nooch_village" / "static" / "nooch.css").read_text()
    import re as _re
    m = _re.search(r"(?:^|[};])\s*\.fieldform select\{([^}]*)\}", css, _re.M)
    assert m, ".fieldform select bestaat niet"
    assert "font:inherit" in m.group(1), "de select houdt het browser-font"
    assert "padding" in m.group(1), "de select heeft geen hoogte"


def test_de_leespagina_krijgt_dezelfde_kop(tmp_path):
    """Drie renderers met drie koppen is precies hoe ze uit elkaar lopen. De policy/tool-leespagina
    deelt nu hetzelfde blok."""
    dd, st, _a, rec = _dorp(tmp_path)
    p = st.att.add(rec.id, "policy", title="Beleid", body="tekst", domain="bibliotheek")
    html = render_pagina(st, p.id, csrf_token="TOK", username="b@t.nl")
    assert "class='dcol'" in html
    h1 = html.split("<h1>")[1].split("</h1>")[0]
    assert p.id not in h1, "het ID staat nog in de kop van de leespagina"
    assert p.id in html
