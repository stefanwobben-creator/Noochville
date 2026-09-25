"""De select krijgt de chevron van de huisstijl (25 september 2026).

WAT ER MIS WAS. Een `<select>` hield de NATIVE pijl van het besturingssysteem: een grijs
driehoekje in een doosje, met een eigen vorm per platform. Naast een veld dat in deze huisstijl
verder alleen een onderlijn heeft, is dat het enige stukje vreemde chrome op het scherm — en
precies wat een dropdown "een kale HTML-control" deed lijken.

`appearance:none` haalt méér weg dan de pijl: op Safari en oudere Chrome verdwijnt daarmee ook de
doos eromheen. Dat is de bedoeling; de onderlijn is de veldstijl van deze laag.

DRIE DINGEN DIE NIET VANZELF SPREKEN
  1. `:not([multiple])` is geen specificiteitstruc maar betekenis: een meerkeuzelijst klapt niet
     uit en heeft geen chevron. Dát hij daarmee zwaarder weegt dan `.fieldform select` in
     nooch.css is meegenomen — die zet een `padding`-shorthand, en nooch.css laadt ná dit bestand
     (`_NU_LINK` in de head, `_DS_LINK` vooraan in de body).
  2. De kleur staat hard in de data-URI. Dat is de ene plek waar `reference, don't copy` niet kan:
     `var()` werkt niet binnen een `url()`. Vandaar de toets hieronder.
  3. Zonder `padding-right` loopt een lange optie ónder de chevron door.
"""
from __future__ import annotations

import pathlib
import re

NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()


def _regel(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", NU, re.S)
    assert m, f"{selector} bestaat niet (meer)"
    return m.group(1)


def _token(naam: str) -> str:
    m = re.search(rf"--{naam}:\s*(#[0-9A-Fa-f]{{3,8}})", NU)
    assert m, f"token --{naam} niet gevonden"
    return m.group(1).lower()


def test_de_native_pijl_is_weg():
    inhoud = _regel(".nu select:not([multiple])")
    assert "appearance: none" in inhoud


def test_de_voorvoegsels_staan_erbij():
    """Safari kent de kale `appearance` pas sinds 15.4, en dit dorp heeft geen buildstap die ze
    toevoegt."""
    inhoud = _regel(".nu select:not([multiple])")
    assert "-webkit-appearance: none" in inhoud
    assert "-moz-appearance: none" in inhoud


def test_er_komt_een_eigen_chevron_voor_terug():
    """Zonder vervanging is er geen enkel teken dat het veld uitklapt."""
    inhoud = _regel(".nu select:not([multiple])")
    assert "background-image" in inhoud and "data:image/svg+xml" in inhoud
    assert "<svg" in inhoud and "<path" in inhoud


def test_de_chevron_komt_uit_geen_enkele_library():
    """Eis van Stefan, en de regel van dit project: geen extra afhankelijkheid voor een pijltje."""
    inhoud = _regel(".nu select:not([multiple])")
    assert "http://www.w3.org/2000/svg" in inhoud, "de SVG hoort inline te staan"
    assert ".woff" not in inhoud and "font" not in inhoud.lower(), "dit is een icoonfont, geen SVG"


def test_de_chevron_heeft_de_kleur_van_de_tekst():
    """DE ENE PLEK WAAR `reference, don't copy` NIET KAN: `var()` werkt niet binnen een `url()`.
    Deze toets is de vervanging — hij houdt de hardgecodeerde kleur gelijk aan het token."""
    inhoud = _regel(".nu select:not([multiple])")
    m = re.search(r"stroke='%23([0-9A-Fa-f]{3,6})'", inhoud)
    assert m, "de chevron heeft geen streekkleur"
    tekst = _token("nu-text").lstrip("#")
    kleur = m.group(1).lower()
    assert kleur in (tekst, tekst * 2 if len(tekst) == 3 else tekst[:3]), \
        f"chevron is #{kleur}, --nu-text is #{tekst}"


def test_bij_focus_volgt_de_chevron_de_lijn():
    """De onderlijn wordt bij focus groen; zou de chevron zwart blijven, dan staan er twee kleuren
    voor één toestand."""
    inhoud = _regel(".nu select:not([multiple]):focus")
    m = re.search(r"stroke='%23([0-9A-Fa-f]{6})'", inhoud)
    assert m, "de focus-chevron heeft geen streekkleur"
    assert m.group(1).lower() == _token("nu-accent").lstrip("#"), \
        f"focus-chevron is #{m.group(1)}, --nu-accent is {_token('nu-accent')}"


def test_er_is_ruimte_voor_de_chevron():
    """Zonder `padding-right` loopt een lange optie eronder door."""
    inhoud = _regel(".nu select:not([multiple])")
    assert "padding-right" in inhoud
    assert "background-repeat: no-repeat" in inhoud, "de chevron herhaalt zich over het veld"


def test_de_onderlijn_blijft_de_veldstijl():
    """`appearance:none` mag de huisstijl niet slopen: de gedeelde veldregel hoort de select nog
    steeds te raken."""
    gedeeld = re.search(r"\.nu textarea, \.nu select, [^{]*\{([^}]*)\}", NU)
    assert gedeeld and "border-bottom: 1.5px solid var(--nu-text)" in gedeeld.group(1)


def test_een_meerkeuzelijst_krijgt_geen_chevron():
    """Hij klapt niet uit; een chevron zou liegen. En het is de reden dat de selector zo heet."""
    assert ":not([multiple])" in NU
