"""Eén naam voor "de breedte van een formulierkolom" (27 september 2026).

DRIE KLASSEN HADDEN HETZELFDE CONCEPT APART UITGEVONDEN:

    .kc-form     34rem   het KPI-formulier (metrics.py)
    .cl-addform  30rem   het checklist-item-formulier (checklists.py)
    .c2-smal     34rem   de actielijst (acties.py)

DE 30 WAS GEEN KEUZE. Alle drie de getallen kwamen in één commit binnen (167eb29, de
CSS-extractie waarbij inline styles naar het bestand verhuisden), er stond geen reden bij, en de
layout eromheen dwingt niets af: `.cl-addform` hangt in een `<details class='cl-add'>` met
`display:inline-block` in een flex-rij die hem niet begrenst. Eén maat dus, één naam.

Dit is `reference, don't copy` op een getal: "als dit verandert, op hoeveel plekken pas ik het
aan?" Het juiste antwoord is één.
"""
from __future__ import annotations

import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
BASE = (pathlib.Path(__file__).resolve().parents[1]
        / "nooch_village" / "web_base.py").read_text()

#: De drie klassen die een formulierkolom begrenzen.
KOLOMMEN = (".kc-form", ".cl-addform", ".c2-smal")


def _blok(selector: str) -> str:
    m = re.search(rf"(?:^|[}};])\s*{re.escape(selector)}\{{([^}}]*)\}}", CSS, re.M)
    assert m, f"{selector} bestaat niet"
    return m.group(1)


def test_het_token_bestaat_en_staat_bij_de_andere():
    """Tokens horen inline in `web_base._CSS` (CLAUDE.md: "Tokens en basis-atomen blijven inline");
    `nooch.css` is de component-laag en verwijst ernaar, net als naar `--border` en `--radius`."""
    assert "--w-smal-form:" in BASE
    # HET BLOK OP REGELNIVEAU AFBAKENEN. Een `split("}")` knipt hier op de eerste accolade, en
    # die staat in een COMMENTAAR midden in het blok — dan meet je een willekeurig stuk.
    regels = BASE.splitlines()
    start = next(i for i, r in enumerate(regels) if r.strip().startswith(":root{"))
    eind = next(i for i in range(start + 1, len(regels)) if regels[i].strip() == "}")
    blok = "\n".join(regels[start:eind])
    assert "--w-smal-form" in blok, "hij staat niet in het :root-blok"
    assert "--radius" in blok and "--shadow" in blok, "dit is niet het tokenblok"


def test_alle_drie_verwijzen_naar_het_token():
    for klasse in KOLOMMEN:
        body = _blok(klasse)
        assert "max-width:var(--w-smal-form)" in body, klasse


def test_er_staat_nergens_meer_een_losse_kolombreedte():
    """DE HELE POINTE. Eén los `max-width:34rem` erbij en het concept is weer versplinterd.

    OP DE TWEE MATEN DIE HET WAREN, en niet op elke `max-width` in rem: `nooch.css` begrenst ook
    een chip (14rem), een select (8.5rem) en een link-kaart (`min(34rem,92vw)`). Dat zijn andere
    dingen — die allemaal verbieden zou de buurman meten en deze toets onbruikbaar maken."""
    los = re.findall(r"max-width:\s*(?:34|30)rem", CSS)
    assert los == [], f"losse kolombreedtes: {los}"


def test_het_getal_staat_op_een_plek():
    assert BASE.count("--w-smal-form:") == 1
    for klasse in KOLOMMEN:
        assert "rem" not in _blok(klasse).split("max-width:")[1].split(";")[0], klasse


def test_alleen_de_breedte_is_aangeraakt():
    """"Verander verder niets aan padding/border/flex-layout van de drie klassen." """
    kc = _blok(".kc-form")
    assert "display:flex" in kc and "flex-direction:column" in kc and "gap:14px" in kc
    cl = _blok(".cl-addform")
    assert "margin-top:.6rem" in cl and "padding:.7rem .8rem" in cl
    assert "border:1px solid var(--border)" in cl and "background:var(--surface)" in cl
    c2 = _blok(".c2-smal")
    assert "margin-inline:auto" in c2


def test_de_token_waarde_is_de_ruimste_van_de_drie():
    """34 en niet 30: de smalste van twee toevallige getallen kiezen zou de andere twee
    schermen versmallen zonder dat iemand daarom vroeg. Nu wordt alleen `.cl-addform` 4rem
    ruimer, op een plek waar die ruimte er is."""
    m = re.search(r"--w-smal-form:\s*([\d.]+)rem", BASE)
    assert m and float(m.group(1)) == 34.0
