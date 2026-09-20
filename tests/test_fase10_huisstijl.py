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
