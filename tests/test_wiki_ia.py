"""De pagina wordt één doorlopend document (26 september 2026).

DRIE DINGEN DIE APART KLEIN LIJKEN en alleen samen het probleem oplossen. Stefans formulering:
*"de inhoud is leidend, nu is type informatie leidend"* — en na de eerste ronde: *"je hebt een
blok, een witruimte, weer een blok, en dan voelt het niet als een pagina."*

1. FEITEN EN BACKLINKS WORDEN ECHTE BLOKKEN. De markering `{{facts}}`/`{{backlinks}}` bestaat al
   sinds #595, maar alleen voor wie de syntax kent. Het blokmenu — juist gebouwd om een blok te
   kunnen toevoegen ZONDER markdown te kennen — had ze niet. Daarmee bestond de plaatsbaarheid
   feitelijk niet voor wie het menu gebruikt.
2. DE METADATA GAAT NAAR ONDERAAN. Owner/Domain/Id/Last edited/History stond direct onder de
   titel: de administratie kreeg de plek van de inhoud. Boven blijft titel + Edit page.
3. EEN INLINE BLOK KRIJGT GEEN KADER. `_feiten_sectie` en `_backlink_sectie` renderden hun inhoud
   als `.card` — rand, achtergrond, eigen padding — terwijl een alinea niets van dat alles heeft.
   Zodra een Feit tússen twee alinea's kan staan botst dat, en dan verplaats je het
   "blok-witruimte-blok"-gevoel alleen maar.

WAAROM SAMEN: los van elkaar zijn het drie kleine fixes en blijft de pagina een stapel losse
stukken.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2, wiki
from nooch_village.cockpit2_util import BLOK_MENU, BLOK_SOORTEN, blok_menu
from nooch_village.views.wiki import render_pagina

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()

#: Een pagina met ECHT GEMENGDE inhoud, want dat is de eis: tekst → feit → tekst → backlink.
GEMENGD = ("Eerste alinea over het onderwerp.\n\n"
           "{{facts}}\n\n"
           "Tweede alinea, na het feit.\n\n"
           "{{backlinks}}\n\n"
           "Slotalinea.")


def _dorp(tmp_path, body=GEMENGD):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    mens = st.people.add("Beheerder", "b@t.nl")
    st.assign.assign(rol, "person", mens.id)
    a = st.att.add(rol, "note", title="Gemengde pagina", body=body)
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Schoenen wegen 300 gram")]})
    return dd, st, st.att.get(a.id)


def _pagina(tmp_path, **kw):
    dd, st, a = _dorp(tmp_path, **kw)
    return render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl"), a


# ── 1. Feiten en Backlinks zijn kiesbare blokken ─────────────────────────────
def test_het_menu_kent_feiten_en_backlinks():
    labels = {rij[1] for rij in BLOK_MENU}
    assert "Feiten" in labels and "Backlinks" in labels


def test_ze_voegen_de_bestaande_markering_in():
    """GEEN NIEUWE OPSLAG — de markering bestaat sinds #595. Dit maakt hem alleen bereikbaar."""
    per_label = {rij[1]: rij for rij in BLOK_MENU}
    assert per_label["Feiten"][3] == "{{facts}}"
    assert per_label["Backlinks"][3] == "{{backlinks}}"


def test_de_markeringen_komen_uit_de_bestaande_tabel():
    """`wiki.AFGELEID` is de bron; een tweede lijst in het menu zou na één wijziging uit de pas
    lopen met wat de renderer herkent."""
    for rij in BLOK_MENU:
        m = re.fullmatch(r"\{\{([a-z]+)\}\}", rij[3] or "")
        if m:
            assert m.group(1) in wiki.AFGELEID, f"{rij[1]} voegt een onbekende markering in"


def test_ze_staan_ook_in_het_gerenderde_menu():
    html = blok_menu()
    assert "Feiten" in html and "Backlinks" in html
    assert "{{facts}}" in html and "{{backlinks}}" in html


def test_elke_menu_soort_bestaat_nog_steeds():
    """De bestaande guard: geen knop voor een blok dat de renderer niet maakt."""
    for tag, label, cmd, arg in BLOK_MENU:
        assert tag == "p" or tag in BLOK_SOORTEN, f"{label}: {tag!r} kent de renderer niet"


def test_geen_vaste_telling_van_menu_items():
    """DE LES VAN #595, waar een hardgecodeerde `=== 7` de sprint drie keer inhaalde. Met twee
    entries erbij mag nergens een vast getal staan dat meegroeien moet.

    OP DE GETELDE UITDRUKKING, niet op de regel eromheen. Mijn eerste versie keek 160 tekens
    terug en sloeg daardoor aan op `Object.keys(soorten).length > 0 && mist.length === 0` — waar
    het vaste getal bij `mist` hoort (nul ontbrekende soorten, een AFGELEIDE telling) en niet bij
    de soorten zelf. Een guard die een correcte regel afkeurt, wordt uitgezet."""
    check = (pathlib.Path(__file__).resolve().parents[1]
             / "claude" / "blok_browsercheck.js").read_text()
    for m in re.finditer(r"\.length\s*===\s*\d+", check):
        # Wat wordt hier geteld? Alles tot de vorige scheiding — dus `mist`, niet de hele regel.
        geteld = re.split(r"[&|,;(){}=!<>]\s*", check[:m.start()])[-1]
        assert "soorten" not in geteld and "wiki-cmd" not in geteld, \
            f"vaste telling van bloksoorten: {geteld}{m.group(0)}"


# ── 2. De metadata staat onderaan ────────────────────────────────────────────
def test_de_metadata_staat_na_de_inhoud(tmp_path):
    html, _a = _pagina(tmp_path)
    assert html.index("id='wiki-body'") < html.index("class='dcol'"), \
        "de metadata staat nog vóór de tekst"


def test_de_metadata_staat_na_feiten_en_backlinks(tmp_path):
    """"Na de content, na Feiten en Links-here" — dus echt als laatste."""
    html, _a = _pagina(tmp_path, body="Alleen tekst, geen markeringen.")
    assert html.index(">Facts</h3>") < html.index("class='dcol'")
    assert html.index(">Links here</h3>") < html.index("class='dcol'")


def test_boven_de_vouw_staat_alleen_titel_en_bewerken(tmp_path):
    html, a = _pagina(tmp_path)
    kop = html[:html.index("id='wiki-body'")]
    assert "wiki-titel" in kop and "data-wiki-start" in kop
    for weg in ("class='dcol'", ">Last edited<", a.id):
        assert weg not in kop, f"{weg} staat nog boven de tekst"


def test_de_leespagina_volgt_dezelfde_volgorde(tmp_path):
    """Drie renderers met drie volgordes is precies hoe ze uit elkaar lopen."""
    dd, st, _a = _dorp(tmp_path)
    p = st.att.add(st.records.all()[0].id, "policy", title="Beleid", body="tekst")
    html = render_pagina(st, p.id, csrf_token="TOK", username="b@t.nl")
    assert html.index("class='att-body'") < html.index("class='dcol'")


def test_het_uploadformulier_blijft_bij_de_tekst(tmp_path):
    """DE NAAD MET #603, want die PR en deze raken allebei de volgorde van één f-string.

    Een bijlage landt als blok aan het EIND van de body. Het formulier hoort dus onder de tekst
    waar hij in terechtkomt, en niet onder de administratie — dan staat de knop los van zijn
    uitkomst. Bij het rebasen is dit precies de regel die je per ongeluk anders oplost."""
    html, _a = _pagina(tmp_path)
    assert "value='wiki_bijlage'" in html, "het uploadformulier staat er niet"
    assert html.index("id='wiki-body'") < html.index("value='wiki_bijlage'") \
        < html.index("class='dcol'"), "het uploadformulier staat niet tussen tekst en metadata"


def test_de_metadata_staat_er_maar_een_keer(tmp_path):
    """Verplaatsen is niet kopiëren. Bij de vorige ronde stond het domein-formulier er twee keer
    nadat het blok erbij kwam; die les geldt hier net zo goed."""
    html, _a = _pagina(tmp_path)
    assert html.count("class='dcol'") == 1


# ── 3. Een inline blok leest als onderdeel van de pagina ─────────────────────
def test_een_feit_heeft_geen_kaderrand(tmp_path):
    """`.card` geeft rand, achtergrond én eigen padding; een alinea heeft geen van drieën. Zodra
    een Feit tussen de tekst staat botst dat."""
    html, _a = _pagina(tmp_path)
    blok = html.split("data-blok='facts'")[1].split("</div></div>")[0]
    assert "class='card'" not in blok, "het feit staat nog in een kaart"


def test_een_backlink_heeft_geen_kaderrand(tmp_path):
    html, _a = _pagina(tmp_path)
    blok = html.split("data-blok='backlinks'")[1].split("<span class='dk'>")[0]
    assert "class='card'" not in blok


def test_het_onderscheid_blijft_maar_via_een_lijn(tmp_path):
    """Een Feit mag herkenbaar zijn als Feit — de eis is alleen dat het geen losstaand kader is.
    Een dunne accentlijn is wat het ontwerpdocument daarvoor noemt."""
    html, _a = _pagina(tmp_path)
    assert "wiki-inline" in html
    regel = re.search(r"(?:^|[};])\s*\.wiki-inline\s*>\s*(?:div|a)[^{]*\{([^}]*)\}", CSS, re.M)
    assert regel, ".wiki-inline heeft geen eigen vormgeving"
    assert "border-left" in regel.group(1), "het onderscheid is geen lijn"
    assert "border:" not in regel.group(1), "er staat alsnog een kader omheen"


def test_de_nu_laag_kent_het_inline_blok():
    """Les uit #598: een nieuwe zichtbare klasse zonder tegenhanger laat de huisstijl-ratchet
    vallen, en terecht."""
    assert ".nu .wiki-inline" in NU


def test_de_sectie_heeft_niet_zijn_eigen_marge(tmp_path):
    """`.c2-sec` zet `margin:1.1rem 0` — meer dan een alinea krijgt. Tussen de tekst maakt dat
    precies het gat dat "blok, witruimte, blok" oplevert."""
    html, _a = _pagina(tmp_path)
    blok = html.split("data-blok='facts'")[1][:300]
    assert "c2-sec" not in blok, "de inline sectie draagt nog de sectie-marge"


def test_onderaan_ziet_het_er_hetzelfde_uit(tmp_path):
    """DE EIS DIE JE ZOU VERGETEN: ook bij een schrijver die niets verplaatst heeft. Dezelfde
    functie rendert beide gevallen, dus dat mag niet uiteenlopen."""
    html, _a = _pagina(tmp_path, body="Alleen tekst, geen markeringen.")
    sectie = html.split(">Facts</h3>")[1].split("</div>")[0]
    assert "class='card'" not in sectie
    assert "wiki-inline" in html


# ── 4. De rondgang en het blokmodel ──────────────────────────────────────────
def test_de_gemengde_pagina_overleeft_de_rondgang(tmp_path):
    from nooch_village.cockpit2_util import _md, _md_naar_bron
    eerste = _md(GEMENGD, blokken=True)
    assert _md(_md_naar_bron(eerste), blokken=True) == eerste


def test_de_twee_blokken_zijn_sleepbaar(tmp_path):
    """Sleepbaar = een `.wb` met een eigen soort, want daar hangt de greep aan. Dat kregen ze in
    #595 al; deze toets legt vast dat het zo blijft nu ze ook uit het menu komen."""
    html, _a = _pagina(tmp_path)
    for soort in ("facts", "backlinks"):
        assert f"data-blok='{soort}'" in html
