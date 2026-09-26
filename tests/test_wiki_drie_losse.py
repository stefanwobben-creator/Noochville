"""Drie losse dingen aan de wiki-pagina (26 september 2026).

1. Een afbeelding krijgt geen kader, ook niet in de huisstijl-laag.
2. Wie "Tabel" kiest, krijgt uitleg bij het tekstvak — de `|---|---|`-regel moet exact blijven
   staan, en dat zie je nergens aan.
3. Het domein van een pagina die er al één heeft, mag alleen nog de rol die dat domein HOUDT
   verzetten (plus de Circle Lead). Zolang er geen domein is, verandert er niets.
"""
from __future__ import annotations

import pathlib
import re

from conftest import js_zonder_uitleg
from nooch_village import cockpit2, triage_rol, wiki
from nooch_village.cockpit2_util import BLOK_HINT, BLOK_MENU, _md, blok_menu
from nooch_village.views.wiki import _domein_form, _mag_domein_wijzigen, render_pagina

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()


# ── 1. Geen kader om een afbeelding ──────────────────────────────────────────
def _regel(bron: str, sel: str) -> str:
    m = re.search(r"(?:^|[};])\s*" + re.escape(sel) + r"\{([^}]*)\}", bron, re.M)
    assert m, f"{sel} bestaat niet"
    return m.group(1)


def test_de_huisstijl_lijst_een_afbeelding_niet_in():
    """Een afbeelding ÍS het vlak; een rand eromheen maakt er een ingelijst plaatje van in plaats
    van een stuk pagina. Zelfde gedachte als bij `.wiki-inline` en de metadata-voet, waar het
    kader er om dezelfde reden af ging."""
    body = _regel(NU, ".nu .wb-img img")
    assert "border:" not in body, "de afbeelding staat weer in een kader"


def test_de_vierkante_hoeken_blijven():
    """Die zijn wél de huisstijl — deze laag kent geen ronde hoeken."""
    assert "border-radius:0" in _regel(NU, ".nu .wb-img img")


def test_de_basislaag_was_al_randloos():
    """De tegenproef: buiten `.nu` stond er nooit een rand, dus daar viel niets weg te halen."""
    assert "border:" not in _regel(CSS, ".wb-img img")


# ── 2. Uitleg bij het tabel-sjabloon ─────────────────────────────────────────
def test_de_tabel_heeft_een_hint():
    assert "table" in BLOK_HINT
    for woord in ("kolomnamen", "|---|---|", "exact"):
        assert woord in BLOK_HINT["table"], f"de hint zegt niets over {woord!r}"


def test_alleen_de_tabel_heeft_er_een():
    """Bij een codeblok is "typ hier je code" geen informatie. Een hint bij elk bloktype is
    hetzelfde als geen hint: je leest ze geen van allen meer."""
    assert set(BLOK_HINT) == {"table"}


def test_de_hint_hangt_aan_een_bloktype_dat_bestaat():
    """Dezelfde regel als bij `BLOK_MENU`: geen uitleg bij een blok dat de renderer niet maakt."""
    tags = {tag for tag, *_ in BLOK_MENU}
    assert set(BLOK_HINT) <= tags


def test_de_hint_reist_mee_in_het_sjabloon():
    knop = next(s for s in blok_menu().split("<button") if ">Tabel</button>" in s)
    assert "data-wiki-hint='" in knop
    assert "kolomnamen" in knop


def test_geen_ander_menu_item_draagt_hem():
    html = blok_menu()
    assert html.count("data-wiki-hint='") == 1


def test_de_browser_bedenkt_de_uitleg_niet():
    """DE TEKST KOMT VAN DE SERVER, zoals het sjabloon ernaast. Dit bestand bedenkt geen uitleg,
    net zomin als het bloktypes bedenkt — dezelfde regel die op drie plekken in `nooch.js` staat."""
    kaal = js_zonder_uitleg(JS)
    veld = kaal.split("function bronVeld(")[1].split("\n  function ")[0]
    assert "dataset.wikiHint" in kaal, "de hint wordt nergens uit het sjabloon gelezen"
    for verboden in ("kolomnamen", "|---|---|"):
        assert verboden not in veld, f"de uitleg staat letterlijk in JS ({verboden!r})"


def test_de_uitleg_is_chrome_en_geen_tekst():
    """Zonder `data-chrome` belandt hij bij het opslaan in de bron, en dan staat de uitleg
    voortaan ín de tabel. Dezelfde verdediging als bij de greep en het bijschrift."""
    kaal = js_zonder_uitleg(JS)
    veld = kaal.split("function bronVeld(")[1].split("\n  function ")[0]
    assert 'setAttribute("data-chrome"' in veld


def test_de_uitleg_hergebruikt_een_bestaande_klasse():
    """Geen nieuwe klasse zonder gemeten aanleiding — `.wiki-hint` en `.muted` bestaan allebei."""
    kaal = js_zonder_uitleg(JS)
    veld = kaal.split("function bronVeld(")[1].split("\n  function ")[0]
    assert 'className = "muted wiki-hint"' in veld
    assert ".wiki-hint{" in CSS


def test_een_bestaande_tabel_draagt_de_hint_zelf():
    """DE TWEEDE ROUTE (26 september 2026). Hij kwam alleen mee als attribuut op de MENU-knop, dus
    wie een bestaande tabel openmaakte met "✎ bewerk als tekst" kreeg dezelfde `|---|---|`-val
    zonder waarschuwing. De server hangt hem nu aan het blok zelf, precies waar `data-blok` al
    gezet wordt."""
    html = _md("| A | B |\n|---|---|\n| 1 | 2 |", blokken=True)
    assert "data-blok='tabel'" in html
    assert f"data-wiki-hint='{BLOK_HINT['table']}'" in html


def test_alleen_de_tabel_krijgt_hem_op_het_blok():
    """Een alinea, een kop of een lijst heeft niets uit te leggen. Stond de hint op elk blok, dan
    droeg elke pagina hem tientallen keren mee zonder dat iemand hem ooit ziet."""
    for bron in ("gewone tekst", "### een kop", "- een punt", "```\ncode\n```"):
        assert "data-wiki-hint" not in _md(bron, blokken=True), f"{bron!r} kreeg uitleg"


def test_de_hint_op_het_blok_komt_uit_dezelfde_tabel():
    """ÉÉN BRON VOOR TWEE ROUTES. Een tweede vertaling tag→soort zou na één wijziging uit de pas
    lopen met de eerste, en dan krijgt één van de twee routes stil geen uitleg meer."""
    from nooch_village.cockpit2_util import BLOK_SOORTEN, _BLOK_HINT_PER_SOORT
    assert _BLOK_HINT_PER_SOORT == {BLOK_SOORTEN[t]: v for t, v in BLOK_HINT.items()}


def test_de_hint_overleeft_de_rondgang():
    """Hij is CHROME op het omhulsel, geen tekst. Kwam hij terug in de bron, dan stond de uitleg
    na één bewerkronde in de tabel — en daarna nog een keer, en nog een keer."""
    from nooch_village.cockpit2_util import _md_naar_bron
    bron = "| A | B |\n|---|---|\n| 1 | 2 |"
    assert _md_naar_bron(_md(bron, blokken=True)) == bron


def test_de_browser_kiest_niet_zelf_welk_blok_uitleg_krijgt():
    """`test_javascript_draagt_geen_eigen_soorten_lijst` verbiedt een bloktypelijst in JS, en die
    regel geldt hier net zo goed: `naarBron` leest een attribuut en vergelijkt geen soort."""
    kaal = js_zonder_uitleg(JS)
    naar = kaal.split("function naarBron(")[1].split("\n  function ")[0]
    assert "dataset.wikiHint" in naar
    for verboden in ('"tabel"', "'tabel'", '"table"'):
        assert verboden not in naar, f"de browser kent opeens een bloktype ({verboden})"


# ── 3. Wie mag het domein verzetten ──────────────────────────────────────────
#: HET GEVAL DAT DEZE REGEL ÉCHT RAAKT, en dat is smaller dan je zou denken. `_domein_form` biedt
#: alleen de domeinen van de EIGENAAR-rol aan, dus normaal houdt die rol zijn eigen domein en
#: verandert er niets: dezelfde mensen mochten het al. Het bijt zodra governance het domein naar
#: een ÁNDERE rol verplaatst terwijl de pagina blijft staan — dan kan de oude eigenaar hem niet
#: meer uit dat domein wegtrekken. Die opstelling bouwt dit dorpje na.
#:
#: "proefdomein" EN NIET "materials": `creator_of_shoes` houdt `Materials` al in de bootstrap, dus
#: met die naam houden drie rollen hetzelfde domein en valt de poort terug op een configuratiefout.
#: Gevonden doordat de toets slaagde om de verkeerde reden.
def _dorp(tmp_path, *, domein="", houder_domeinen=("proefdomein",)):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rollen = st.records.all()
    schrijver, houder = rollen[0].id, rollen[1].id

    rec = st.records.get(schrijver)
    # DE EIGENAAR-ROL HOUDT "proefdomein" NIET — dat is de hele opstelling. Hield hij hem ook,
    # dan zijn er twee houders en valt de poort terug op een configuratiefout; dan slaagt de toets
    # om de verkeerde reden. Twee eigen domeinen, zodat het veld een keuzelijst blijft.
    rec.definition.domains = ["schrijfdomein", "tweede-domein"]
    st.records.put(rec)
    hrec = st.records.get(houder)
    hrec.definition.domains = list(houder_domeinen)
    st.records.put(hrec)

    # TWEE MENSEN DIE ALLEBEI DE PAGINA MOGEN BEWERKEN — anders meet je alleen `can_edit`. De
    # tweede vult daarnaast de rol die het domein houdt. Dat de poort een DOORSNEDE is en geen
    # uitbreiding hoort erbij: de domeinhouder krijgt hier geen bewerkrecht van, hij verliest
    # alleen niets.
    wie = {}
    for naam, mail, extra in (("Schrijver", "s@t.nl", None), ("Houder", "h@t.nl", houder)):
        p = st.people.add(naam, mail)
        st.assign.assign(schrijver, "person", p.id)
        if extra:
            st.assign.assign(extra, "person", p.id)
        wie[naam.lower()] = p
    a = st.att.add(schrijver, "note", title="Een pagina", body="Tekst.", domain=domein)
    return dd, st, st.att.get(a.id), wie


def test_zonder_domein_mag_iedereen_met_bewerkrecht(tmp_path):
    """Een ongeplaatste pagina heeft nog geen eigenaar die er iets over te zeggen heeft, en de
    drempel om hem überhaupt in te delen moet laag blijven."""
    dd, st, a, wie = _dorp(tmp_path)
    assert _mag_domein_wijzigen(a, st, "s@t.nl") is True


def test_met_domein_mag_de_houder(tmp_path):
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    assert triage_rol.domein_eigenaar(st, "proefdomein")["rol"], "de opstelling klopt niet"
    assert _mag_domein_wijzigen(a, st, "h@t.nl") is True


def test_met_domein_mag_een_ander_niet(tmp_path):
    """Verplaatsen is een ingreep in andermans domein: de rol die het houdt verliest er iets uit."""
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    assert _mag_domein_wijzigen(a, st, "s@t.nl") is False


def test_de_circle_lead_mag_altijd(tmp_path):
    """Dezelfde figuur die bij `artefact_delete` de zwaarste knop bedient."""
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    cirkel = cockpit2.resolve_circle_id(a.anchor, st.records)
    st.assign.assign(f"{cirkel}__circle_lead", "person", wie["schrijver"].id)
    assert _mag_domein_wijzigen(a, st, "s@t.nl") is True


def test_niemand_houdt_het_domein_dan_verandert_er_niets(tmp_path):
    """EEN CONFIGURATIEFOUT SLUIT NIEMAND BUITEN. Het domein bestaat niet als verklaring, of het
    governance-akte is nooit gezet — dat hoort daar opgelost te worden, niet doordat een pagina
    hier stilzwijgend op slot gaat en niemand meer weet waarom."""
    dd, st, a, wie = _dorp(tmp_path, domein="verdwenen-domein")
    assert triage_rol.domein_eigenaar(st, "verdwenen-domein")["rol"] == ""
    assert _mag_domein_wijzigen(a, st, "s@t.nl") is True


def test_twee_rollen_houden_het_dan_ook_niet(tmp_path):
    """Twee eigenaren van één domein is een governance-fout; ertussen kiezen zou die fout
    verbergen achter een gok — dat zegt `domein_eigenaar` zelf al, en hier geldt hetzelfde."""
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    derde = st.records.all()[2]
    derde.definition.domains = ["proefdomein"]
    st.records.put(derde)
    st2 = cockpit2._Stores(dd)
    assert triage_rol.domein_eigenaar(st2, "proefdomein")["rol"] == "", "de opstelling klopt niet"
    assert _mag_domein_wijzigen(st2.att.get(a.id), st2, "s@t.nl") is True


def test_zonder_sessie_geen_oordeel(tmp_path):
    """De echte poort staat op de server; dit bepaalt alleen wat je te zien krijgt. Zonder `st` of
    gebruiker kan hij de vraag niet stellen, en dan valt hij terug."""
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    assert _mag_domein_wijzigen(a, None, "h@t.nl") is True
    assert _mag_domein_wijzigen(a, st, None) is True
    assert _mag_domein_wijzigen(a, st, "guest") is True


# ── 3b. Wat je er op het scherm van ziet ─────────────────────────────────────
def test_wie_niet_mag_ziet_een_chip_en_geen_veld(tmp_path):
    """Een knop die de server daarna weigert, belooft iets wat niet kan. Lezen blijft vrij, dus
    wáár de pagina hangt zie je nog steeds."""
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    html = render_pagina(st, a.id, csrf_token="TOK", username="s@t.nl")
    assert "name='domain'" not in html, "het veld staat er nog"
    assert "value='artefact_edit'" not in html.split("class='wiki-meta'")[1], \
        "de Move page-knop staat er nog"
    assert "proefdomein" in html, "je ziet niet meer waar de pagina hangt"


def test_wie_wel_mag_ziet_het_veld(tmp_path):
    dd, st, a, wie = _dorp(tmp_path, domein="proefdomein")
    html = render_pagina(st, a.id, csrf_token="TOK", username="h@t.nl")
    assert "name='domain'" in html


def test_zonder_domein_ziet_de_schrijver_het_veld_nog_steeds(tmp_path):
    """DE REGEL RAAKT ALLEEN WIE HET VELD MAG WIJZIGEN, en alleen zodra er iets te beschermen is."""
    dd, st, a, wie = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="s@t.nl")
    assert "name='domain'" in html


def test_de_keuzelijst_regel_bij_een_domein_blijft_ongemoeid(tmp_path):
    """ANDER ONDERWERP, staat hier los van: een rol met precies één domein krijgt een vaste
    waarde en geen keuzelijst. Dat besluit heeft zijn eigen toets en is niet aangeraakt."""
    from nooch_village.views.overview import _domain_field
    assert "<select" not in _domain_field(["materials"], huidig="")


def test_een_policy_of_tool_krijgt_hier_nog_steeds_niets(tmp_path):
    """De poort die er al stond, blijft vóór de nieuwe staan: alleen een note wordt hier bewerkt."""
    dd, st, a, wie = _dorp(tmp_path)
    p = st.att.add(a.anchor, "policy", title="Beleid", body="x", domain="materials")
    assert _domein_form(p, st.records.get(a.anchor), "TOK", True, st.records.all(),
                        st=st, username="h@t.nl") == ""
