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
  2. **`[[links]]` en backlinks.** `wiki.paginas` is notes-only, dus een verwijzing vanuit een
     policy zou nergens op uitkomen. (`_artefact_body_html` zegt dit al met zoveel woorden.)
  3. **Bewerken.** Een note wordt op zijn permalink bewerkt, een policy en tool op het formulier
     bij de eigenaar-rol. Dat staat zo in `_artefact_own_card`, mét de reden: twee bewerkpaden
     voor hetzelfde object lopen uiteen zodra er aan één van de twee iets verandert.

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
    # twee tools (TOOL-COMMUN-001, TOOL-STRATE-001), dus het getal ging over het zaad en niet
    # over de link-keten. Wat de toets bedoelt is dat elke SOORT vertegenwoordigd is — anders
    # kan hij groen blijven terwijl de index een soort niet meer toont.
    assert {art[k].id for k in ("note", "policy", "tool")} <= set(ids), (
        f"niet elke soort staat in de index: {ids}")

    dood = [i for i in ids if "Page not found" in render_pagina(st, i, csrf_token="TOK",
                                                               username="b@t.nl")]
    assert not dood, f"dode links in de wiki-index: {dood}"


def test_de_index_en_de_pagina_putten_uit_dezelfde_lijst():
    """Twee lijsten die "welke soorten bestaan" zeggen, lopen uiteen — dat is precies hoe dit
    gat ontstond. De chips van de index moeten exact `ARTEFACT_KINDS` zijn."""
    uit_index = {k for k, _ in _WIKI_SOORTEN[1:]}
    assert uit_index == set(ARTEFACT_KINDS), (
        f"de index toont {uit_index}, de artefact-soorten zijn {set(ARTEFACT_KINDS)}")


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


def test_de_policy_pagina_is_geen_tweede_bewerkpad(tmp_path):
    """`_artefact_own_card` legt vast dat een tool of policy zijn formulier bij de EIGENAAR-ROL
    houdt, omdat twee bewerkpaden voor hetzelfde object uiteen gaan lopen. Deze pagina leest;
    hij wijst naar waar bewerkt wordt."""
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["policy"], can_edit=True)
    assert "id='wiki-body'" not in html, "de inline editor hoort hier niet"
    assert "value='artefact_edit'" not in html, "dat is het tweede bewerkpad"
    assert "tab=policies" in html, "er staat geen weg naar de plek waar je hem wél bewerkt"


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
    # Nu op de belofte zelf, in de tekst die iemand leest.
    assert "Edit on the role" not in html, "een bewerkknop voor wie niet mag bewerken"


# ── 4. De note-pagina verandert niet ─────────────────────────────────────────
def test_de_note_pagina_houdt_zijn_editor(tmp_path):
    """De verruiming mag de bestaande pagina niet aanraken — dat is waar alle brok-1/2/3-toetsen
    op staan."""
    dd, st, art, mens = _dorp(tmp_path)
    html = _pagina(st, art["note"])
    assert "id='wiki-body'" in html
    assert "value='artefact_edit'" in html
    assert "data-blok-soorten" in html, "het blokmodel hoort alleen op de note-pagina"


def test_het_blokmodel_blijft_bij_de_note(tmp_path):
    """Een policy kent het blok-idioom niet (geen greep, geen /-menu): hij wordt hier niet
    bewerkt, dus er is niets om te grijpen."""
    dd, st, art, mens = _dorp(tmp_path)
    assert "data-blok-soorten" not in _pagina(st, art["policy"])
    assert "data-blok-soorten" not in _pagina(st, art["tool"])


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
