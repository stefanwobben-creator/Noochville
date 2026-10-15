"""B3 fase e, commit 3 (13 oktober 2026): ruimte.

Besluiten:
  - kaartpadding minimaal 12px (`--s3`);
  - 24 tot 32px tussen secties (`--s5` = 24px);
  - regelhoogte 1,5 voor lopende tekst (stond al: `body{line-height:1.5}` in web_base);
  - de padding-ratchet: een teller die alleen omlaag mag.

DE PADDING-RATCHET. Elke `padding`-declaratie in nooch.css met een waarde buiten de ruimteschaal
(`var(--s1)` … `var(--s6)`, of 0) telt. Dat zijn de bestaande uitzonderingen; een nieuwe laat de
teller stijgen en faalt. Ruim je er een op (bijv. bij een view die je toch aanraakt), verlaag dan
het plafond: zelfde principe als de inline-style-ratchet (monotone daling).
"""
from __future__ import annotations

import re

from nooch_village import web_base
from tests.test_b3_lijn import CSS, _blokken, _regel

PADDING_PLAFOND = 264


def _buiten_schaal() -> int:
    tel = 0
    for _sel, decl in _blokken(CSS):
        for d in re.findall(r"(?<![-\w])(padding(?:-[a-z]+)?\s*:[^;]*)", decl):
            waarden = d.split(":", 1)[1].split()
            if not all(re.fullmatch(r"0|var\(--s[1-6]\)|auto|inherit", w) for w in waarden):
                tel += 1
    return tel


def test_geen_nieuwe_padding_buiten_de_schaal():
    tel = _buiten_schaal()
    assert tel <= PADDING_PLAFOND, (
        f"{tel} padding-declaraties buiten de schaal, plafond {PADDING_PLAFOND}. Gebruik "
        f"var(--s1)…var(--s6) (4 · 8 · 12 · 16 · 24 · 32px).")
    assert tel == PADDING_PLAFOND, (
        f"{tel} padding-declaraties buiten de schaal, plafond {PADDING_PLAFOND}. Opgeruimd — "
        f"verlaag het plafond naar {tel}.")


def test_kaarten_hebben_minstens_12px_padding():
    assert "padding: var(--s3)" in _regel(":root .pcol .pcard")
    assert "padding: var(--s3)" in _regel(":root .tile")


def test_tussen_secties_24px():
    assert "margin:var(--s5) 0" in _regel(".c2-sec")


def test_lopende_tekst_heeft_regelhoogte_anderhalf():
    assert re.search(r"body\{[^}]*line-height:1\.5", web_base._CSS)
