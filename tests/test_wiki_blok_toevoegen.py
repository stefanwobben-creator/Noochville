"""Een blok toevoegen zonder markdown te kennen (25 september 2026).

EIS 2 UIT HET ONTWERPDOCUMENT: *"Er is een zichtbare, ontdekbare manier om een nieuw blok toe te
voegen zonder de markdown-syntax uit je hoofd te kennen — een '+'-knop, een slash-commando, of
allebei."* Stefan liet de keuze aan mij; het worden er twee, want ze lossen verschillende helften
op.

WAT ER WAS. Het `/`-menu bestond al, maar het opent alleen als een blok EXACT `"/"` bevat. Dat
werkt perfect als je het weet en is onvindbaar als je het niet weet: er is geen knop, geen hint en
geen plek waar het zich aankondigt. En het menu dekte 8 van de 10 bloksoorten — een tabel en een
codeblok kon je alleen maken door de markdown te typen, precies wat deze eis uitsluit.

DE PLUS DOET LETTERLIJK WAT TYPEN DOET, en dat is geen luiheid maar de veiligste route. In
`blokMenuKies` staat een gemeten waarschuwing: *"eerst leegmaken en dán `formatBlock` doet NIETS —
een leeg blok met een samengevallen selectie heeft geen inhoud om op te werken."* Een plus die een
écht leeg blok invoegt loopt recht in dat gat. Hij voegt daarom een blok met een `/` in en opent
het menu, langs hetzelfde pad dat al werkt.

TABEL EN CODE KUNNEN NIET VIA `execCommand`. Die twee krijgen hun markdown-sjabloon van de SERVER
mee (vierde kolom van `BLOK_MENU`) en openen meteen het bron-bewerkvlak dat voor die twee soorten
al bestaat. Zo blijft het vocabulaire op één plek: dit bestand kent geen bloktypes, zoals er in
`nooch.js` ook geen lijst staat.

EMBED ZIT ER BEWUST NIET IN: een regel die alleen een link is wordt al vanzelf een kaart, en een
menu-item zou om een URL moeten vragen. Eigen stap, met Stefan afgestemd.
"""
from __future__ import annotations

import pathlib

from nooch_village.cockpit2_util import BLOK_MENU, BLOK_SOORTEN, _md, _md_naar_bron, blok_menu

WORTEL = pathlib.Path(__file__).resolve().parents[1]
JS = (WORTEL / "nooch_village" / "static" / "nooch.js").read_text()
CSS = (WORTEL / "nooch_village" / "static" / "nooch.css").read_text()


# ── 1. Het menu dekt de soorten die je niet kunt typen ───────────────────────
def test_het_menu_kent_de_tabel_en_het_codeblok():
    """De twee soorten die je tot nu toe alleen met markdown kon maken."""
    cmds = {rij[0] for rij in BLOK_MENU}
    assert "table" in cmds and "pre" in cmds, f"menu dekt {sorted(cmds)}"


def test_elke_menu_soort_bestaat_ook_echt():
    """Een menu-item voor een soort die de renderer niet kent, maakt een blok dat bij de eerste
    bewerkronde iets anders wordt. `BLOK_SOORTEN` is de enige tabel die telt."""
    for tag, label, cmd, arg in BLOK_MENU:
        if tag == "p":
            continue                       # de gewone alinea heeft geen eigen soort
        assert tag in BLOK_SOORTEN, f"{label}: {tag!r} staat niet in BLOK_SOORTEN"


def test_de_embed_zit_er_bewust_niet_in():
    """Een regel die alleen een link is wordt al vanzelf een kaart; een menu-item zou om een URL
    moeten vragen. Als die er ooit toch komt, hoort deze toets bewust te sneuvelen."""
    assert "figure" not in {rij[0] for rij in BLOK_MENU}


def test_de_tabel_en_de_code_dragen_hun_sjabloon_van_de_server():
    """`execCommand` kan die twee niet maken. Ze krijgen daarom markdown mee en openen het
    bron-bewerkvlak. Het sjabloon staat op de SERVER, zodat `nooch.js` geen bloktypes kent."""
    per_tag = {rij[0]: rij for rij in BLOK_MENU}
    for tag, begin in (("table", "|"), ("pre", "```")):
        _tag, label, cmd, arg = per_tag[tag]
        assert cmd == "bron", f"{label} gebruikt {cmd!r} in plaats van het bron-pad"
        assert arg.startswith(begin), f"{label} heeft geen bruikbaar sjabloon: {arg!r}"


def test_de_js_kent_het_bron_pad_ook_echt():
    """DE SERVERTABEL KAN KLOPPEN TERWIJL DE JS ER NIETS MEE DOET. Een mutatie die de
    `bron`-tak in `blokMenuKies` uitschakelde liet alle toetsen hierboven groen: die meten de
    menu-DATA, niet wat er bij een klik gebeurt. Dan kies je "Tabel" en er verschijnt een lege
    alinea."""
    kies = JS.split("function blokMenuKies")[1].split("\n  function ")[0]
    assert 'wikiCmd === "bron"' in kies, "de bron-tak ontbreekt"
    assert "bronVeld(" in kies, "de bron-tak opent geen bewerkvlak"


def test_een_sjabloon_sluit_zichzelf_af():
    """Een codeblok waarvan het sluithek ontbreekt, slokt alles op wat je erna typt. De rondgang
    merkt dat NIET — `_md` sluit een openstaand hek fail-soft aan het eind, dus het rendert en
    reist netjes rond. Wat er misgaat zie je pas als de schrijver verder typt."""
    for tag, label, cmd, arg in BLOK_MENU:
        if cmd != "bron":
            continue
        assert arg.count("```") % 2 == 0, f"{label} laat een hek openstaan: {arg!r}"


def test_het_sjabloon_rendert_ook_echt_als_dat_soort():
    """DE TOETS DIE ERTOE DOET. Een sjabloon dat er goed uitziet maar als alinea rendert, levert
    een menu-item op dat iets anders maakt dan het belooft."""
    per_tag = {rij[0]: rij for rij in BLOK_MENU}
    for tag in ("table", "pre"):
        arg = per_tag[tag][3]
        html = _md(arg, blokken=True)
        assert f"data-blok='{BLOK_SOORTEN[tag]}'" in html, f"{arg!r} werd geen {tag}: {html[:120]}"


def test_het_sjabloon_overleeft_de_rondgang():
    """Anders is het blok na één keer opslaan weer weg."""
    for tag, label, cmd, arg in BLOK_MENU:
        if cmd != "bron":
            continue
        eerste = _md(arg, blokken=True)
        assert _md(_md_naar_bron(eerste), blokken=True) == eerste, f"{label} overleeft niet"


def test_het_menu_sjabloon_draagt_de_argumenten_mee():
    html = blok_menu()
    assert "data-wiki-cmd='bron'" in html
    assert "|" in html and "```" in html


# ── 2. De plus-knop ──────────────────────────────────────────────────────────
def test_er_is_een_plus_knop_naast_de_greep():
    """DE ONTDEKBARE HELFT. Het `/`-menu werkt alleen als je weet dat het bestaat."""
    greep = JS.split("function greepVoor")[1][:1800]
    assert "wb-plus" in greep, "er komt geen plus-knop in de goot"


def test_de_plus_voegt_toe_via_hetzelfde_pad_als_typen():
    """In `blokMenuKies` staat een GEMETEN waarschuwing: een leeg blok met een samengevallen
    selectie heeft geen inhoud om `formatBlock` op te werken, dus dan verandert het bloktype niet.
    Een plus die een écht leeg blok invoegt loopt recht in dat gat. Hij voegt daarom een blok met
    een `/` in en laat het bestaande menu openen."""
    fn = JS.split("function nieuwBlokOnder")[1].split("\n  function ")[0]
    # OP DE TOEKENNING, niet "komt een schuine streep voor in dit venster": een mutatie die er
    # `textContent = ""` van maakte bleef groen, en dan voegt de plus een LEEG blok in — precies
    # het geval waar de gemeten waarschuwing in `blokMenuKies` over gaat.
    assert 'textContent = "/"' in fn, "de plus voegt geen streep-blok in"
    assert 'dispatchEvent(new Event("input"' in fn, "het bestaande menu wordt niet aangeroepen"


def test_de_plus_is_ook_op_touch_te_bereiken():
    """Het ontwerpdocument vraagt om touch *"niet per ongeluk onmogelijk te maken"*. De greep
    heeft daarvoor al een media-query; de plus hangt in dezelfde goot en hoort mee."""
    import re
    m = re.search(r"@media\(hover:none\)\{([^}]*)\}", CSS)
    assert m and "wb-plus" in m.group(1), "de plus verschijnt op touch nooit"


def test_de_plus_telt_niet_als_tekst():
    """Dezelfde les als de greep (⠿): alles in het bewerkbare veld gaat bij het opslaan mee als
    `innerHTML`. De plus hangt in de greep-span, die al `data-chrome` draagt."""
    greep = JS.split("function greepVoor")[1][:1800]
    plus = greep[greep.index("wb-plus"):]
    assert "g.appendChild(plus)" in plus or "g.insertBefore(plus" in plus, \
        "de plus hangt niet in de chrome-span"


def test_de_plus_gebruikt_de_bestaande_knop_taal():
    """Geen nieuwe familie: `wb-` bestaat al, en de ratchet in `test_ui_ratchets` bevriest het
    aantal families."""
    assert ".wb-plus" in CSS
