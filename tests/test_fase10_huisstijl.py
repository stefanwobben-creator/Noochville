"""Fase 10 — de huisstijl uit de échte nooch.earth-beelden, en de dekking van `nooch-ui.css`.

Twee soorten bewaking:

1. **De kleurwaarden zijn gesampled, niet gekozen.** Ze komen uit `claude/huisstijl_referentie_*`
   (elke pixel geteld met Pillow, zie `claude/fase10_huisstijl_inventarisatie.md` §5). Wie ze
   wijzigt moet opnieuw samplen, niet schatten — dat is precies de fout die deze fase begon: zes
   van de acht "afwijkingen" die ik eerst rapporteerde waren getoetst aan een beschrijving in
   woorden en niet aan het beeld, en bleken pixel-exact goed te staan.

2. **Een klassenfamilie doet pas mee als `nooch-ui.css` hem aanstuurt.** `/project/nieuw` stond
   gewoon in `_NU_ROUTES` en zag er tóch oud uit, omdat de wizard met een eigen `wz-*`-familie
   rendert. Route in de lijst ≠ herstyled.
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
NU = (REPO / "nooch_village" / "static" / "nooch-ui.css").read_text()
OUD = (REPO / "nooch_village" / "static" / "nooch.css").read_text()

_ONTCOM = lambda t: re.sub(r"/\*.*?\*/", "", t, flags=re.S)


def _tokens(css: str) -> dict[str, str]:
    blok = re.search(r"\.nu\s*\{(.*?)\n\}", _ONTCOM(css), re.S)
    assert blok, "het .nu-tokenblok is niet te vinden"
    return dict(re.findall(r"(--nu-[a-z-]+)\s*:\s*([^;]+);", blok.group(1)))


def test_de_kleuren_zijn_de_gesampelde_waarden():
    """Elke waarde hieronder is geteld in claude/huisstijl_referentie_email.png of
    -productpagina.jpg. Verandert er één, dan hoort daar een nieuwe sampling bij."""
    t = _tokens(NU)
    assert t["--nu-bg"] == "#FFFAFA"            # 84,4% van de e-mail
    assert t["--nu-surface"] == "#FFFFFF"       # 6,4%
    assert t["--nu-neon"] == "#00FF00"          # de CTA-vulling, met zwarte tekst erop
    assert t["--nu-accent"] == "#00A551"        # de aankondigingsbalk, met witte tekst erop
    assert t["--nu-bg-alt"] == "#E2FFE3"        # het lichtgroene vlak (18% van de productpagina)
    assert t["--nu-accent-text"] == "#1F9D55"   # #14713C kwam in geen van beide beelden voor
    assert t["--nu-muted"] == "#58595B"
    assert t["--nu-border-subtle"] == "#E6E7E8"
    assert t["--nu-text"] == "#000000"          # bewust één token: #1A1A1A is met het oog gelijk


def test_de_referentiebeelden_staan_in_de_repo():
    """Zonder de beelden is de vorige test een lijst getallen zonder herkomst."""
    for naam in ("huisstijl_referentie_productpagina.jpg", "huisstijl_referentie_email.png"):
        p = REPO / "claude" / naam
        assert p.exists() and p.stat().st_size > 100_000, naam


def test_att_en_qadd_worden_aangestuurd():
    """De twee families die in zes views terugkomen. Zie §3 groep A van de inventarisatie."""
    for klasse in ("att-lbl", "att-body", "att-name", "att-ic", "att-sep", "att-pop",
                   "qadd", "qadd-form", "qadd-x"):
        assert re.search(rf"\.nu[^{{]*\.{re.escape(klasse)}\b", NU), f".{klasse} mist een nu-regel"


def test_elke_oude_look_op_att_en_qadd_is_overschreven():
    """Structureel, niet op naam: pak elke selector in nooch.css die op een `att-`/`qadd-`-klasse
    een radius, schaduw of rand zet, en eis dat nooch-ui.css diezelfde klasse aanstuurt."""
    schuldig = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        if not re.search(r"(border-radius|box-shadow|border)\s*:", body):
            continue
        for k in re.findall(r"\.((?:att|qadd)[a-z-]*)", sel):
            schuldig.add(k)
    for k in sorted(schuldig):
        assert re.search(rf"\.nu[^{{]*\.{re.escape(k)}\b", NU), \
            f".{k} zet in nooch.css nog rand/radius/schaduw en wordt niet overschreven"


def test_de_qadd_schaduw_is_expliciet_uitgezet():
    """`.qadd-form textarea` was het enige invoerveld met een `box-shadow`. Een schaduw is in deze
    huisstijl geen stijlkeuze maar een fout — de referentie heeft er nul."""
    assert re.search(r"\.nu \.qadd-form textarea\s*\{[^}]*box-shadow:\s*none", NU, re.S)
    assert "var(--shadow)" in OUD          # hij staat er nog, voor de geparkeerde schermen


def test_geen_enkele_nieuwe_regel_valt_buiten_de_nu_scope():
    """Eén regel zonder `.nu` ervoor raakt élk scherm, ook de 27 geparkeerde."""
    regels = [r.split("{")[0].strip() for r in _ONTCOM(NU).split("}") if "{" in r]
    buiten = [r for r in regels if r and not r.startswith(".nu") and not r.startswith("@")]
    assert not buiten, f"regels buiten de scope: {buiten}"


# ── Typografie: de vier punten die de referentiebeelden letterlijk tonen ─────────────────────

def test_koppen_staan_in_hoofdletters():
    """NINE PLANTS, ONE SHOE · GROW A PAIR · QUESTIONS PEOPLE ACTUALLY ASKED. Er staat geen enkele
    kop in onderkast op de productpagina. `.nu h2, .nu h3` zette hier eerst `text-transform: none`."""
    for sel in (r"\.nu h1", r"\.nu h2, \.nu h3"):
        blok = re.search(rf"{sel}\s*\{{([^}}]*)\}}", NU, re.S)
        assert blok, sel
        assert "text-transform: uppercase" in blok.group(1), sel
    assert "text-transform: none" not in _ONTCOM(NU).split(".nu .pill")[0]


def test_knoptekst_staat_in_hoofdletters():
    """ORDER NOW · BECOME FOUNDING MEMBER · ALL REVIEWS · READ THE LETTERS."""
    blok = re.search(r"\.nu \.btn \{([^}]*)\}", NU, re.S)
    assert blok and "text-transform: uppercase" in blok.group(1)


def test_geen_enkele_ronde_hoek_meer():
    """Structureel, niet op naam: élke border-radius in het bestand moet 0 zijn, met als enige
    uitzondering de 50% van de statusvormen — dat is vorm-codering, geen decoratie.
    `.c2-navct` stond op 999px en was de laatste overgebleven pil."""
    waarden = {w.strip() for w in re.findall(r"border-radius:\s*([^;}]+)", _ONTCOM(NU))}
    assert waarden <= {"0", "50%"}, f"onverwachte radius: {waarden - {'0', '50%'}}"


def test_elke_eyebrow_in_de_oude_css_wordt_aangestuurd():
    """De vingerafdruk van een eyebrow: klein, hoofdletters, vet. Elke selector in nooch.css die
    daaraan voldoet moet binnen `.nu` een tegenhanger hebben — anders staat er op een van de
    negentien schermen nog een groen-of-grijs labeltje in de oude maatvoering."""
    # Bewust buiten beeld, met de reden erbij. Geen stille uitzonderingen.
    BUITEN = {
        ".tile-t": "staat op /metrics2, een van de 27 geparkeerde schermen",
        ".fkind": "geen enkele view rendert hem nog — dode CSS na fase 1-9",
        ".einddoc-toggle": "idem, dode CSS",
        ".smeta dt": "idem, dode CSS",
        ".kn-spelvraag .wie": "kennisbank-UI, in fase 2b verwijderd — dode CSS",
        ".wz-now .lb": "idem, dode CSS",
    }
    gemist = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        maat = re.search(r"font-size:\s*\.(\d+)rem", body)
        if not (maat and int(maat.group(1)[:2].ljust(2, "0")) <= 78):
            continue
        if "text-transform:uppercase" not in body.replace(" ", ""):
            continue
        if "font-weight:700" not in body.replace(" ", ""):
            continue
        if sel.strip() in BUITEN:
            continue
        kern = sel.strip().split()[-1].lstrip(".")
        if not re.search(rf"\.nu[^{{]*[\s.]{re.escape(kern)}\b", NU):
            gemist.append(sel.strip())
    assert not gemist, f"eyebrow-achtige selectors zonder nu-regel: {gemist}"


def test_de_eyebrow_is_een_definitie_en_geen_twaalfde_naam():
    """Elf namen wijzen naar één regel. Zou elk van die elf een eigen blok krijgen, dan is het
    probleem dat deze stap oplost gewoon verplaatst."""
    assert NU.count("text-transform: uppercase; letter-spacing: .06em") == 1
    vorm = re.search(r"([^{}]*\.nu-eyebrow[^{}]*)\{[^}]*letter-spacing: \.06em", NU, re.S)
    assert vorm and len(re.findall(r"\.nu ", vorm.group(1))) >= 10


def test_link_knoppen_staan_ook_in_hoofdletters():
    """`+ add project` en `by role / by person` zijn links die als knop gelezen worden. Ze vielen
    buiten `.nu .btn` en bleven dus in onderkast staan terwijl de echte knoppen al om waren — in de
    broncode onzichtbaar, in de browser meteen te zien."""
    blok = re.search(r"\.nu \.addlink, \.nu \.vswitch a, \.nu \.flink \{([^}]*)\}", NU, re.S)
    assert blok and "text-transform: uppercase" in blok.group(1)


def test_green_dark_ratchet():
    """#14713C komt in GEEN van beide referentiebeelden voor, en staat 57 keer in nooch.css.

    Dit is een ratchet in de vorm die het dorp al kent (`_STYLE_WHITELIST`, `_PREFIX_CEILING`):
    het getal mag alleen omlaag. Elke stap van groep A die een scherm aanpakt hoort er een paar af
    te halen; komt er één bij, dan is er een oude groene kleur teruggekropen op een scherm dat al
    om was.
    """
    _PLAFOND = 46          # 20 sep 2026: 57 selectors met --green-dark, 11 hebben een nu-tegenhanger
    zonder = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        if "var(--green-dark)" not in body:
            continue
        kern = sel.strip().split(",")[0].strip().split()[-1].lstrip(".").split(":")[0]
        if kern and not re.search(rf"\.nu[^{{]*[\s.]{re.escape(kern)}\b", NU):
            zonder.append(sel.strip()[:40])
    assert len(zonder) <= _PLAFOND, (
        f"{len(zonder)} selectors met --green-dark zonder nu-tegenhanger (plafond {_PLAFOND}). "
        f"Gestegen? Dan is er een oude groentint teruggekomen: {zonder[:5]}")
