"""Ratchet-guards voor de HTML-basis (fase 1 van de designsysteem-sanering, dd 2026-07-14).

Zusje van tests/test_ui_no_inline_style.py en volgt hetzelfde principe: bestaande schuld
is per bestand bevroren op het huidige aantal, elke stijging faalt, elke daling verplicht
het plafond mee omlaag (monotone daling naar nul). Drie metrieken:

1. **Labels zonder for=** — een <label> zonder for-koppeling doet niets bij klikken en
   laat het veld voor screenreaders zweven. Nieuwe velden gebruiken web_base._field()
   (genereert label-for + input-id altijd als paar).
2. **Ad-hoc <style>-blokken** — CSS hoort in static/nooch.css (component-laag) of
   web_base._CSS (tokens/atomen), niet als losse blob in een view. Elke blob is een
   uitzondering die bij een restyle wordt gemist.
3. **Klasse-prefix-families (projectbreed)** — het aantal unieke prefixen (wo-, rov-,
   kpi-, …) is bevroren. Een nieuw prefix betekent feitelijk een nieuw privé-stylesheet
   voor één scherm; dat is een expliciet vocabulaire-besluit (docs/UX_PATTERNS.md),
   geen bijvangst van een feature.
"""
from __future__ import annotations

import glob
import os
import re

from nooch_village.web_base import _field, _page

_PKG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village")


def _governed_files():
    files = sorted(glob.glob(os.path.join(_PKG, "views", "*.py")))
    files.append(os.path.join(_PKG, "cockpit2.py"))
    return files


# ── 1. labels zonder for= ────────────────────────────────────────────────────
# Audit dd 2026-07-14, totaal 55. Verlaag een getal zodra je een view opruimt
# (vervang losse <label>/<input>-paren door web_base._field()).
_LABEL_WHITELIST = {
    "views/backlog.py": 2,
    "views/catalog_koppelen.py": 7,
    "views/checklists.py": 4,
    "views/feed.py": 4,
    "views/metrics.py": 11,
    "views/overview.py": 12,
    "views/projects.py": 8,
    "views/roloverleg.py": 4,
    "views/werkoverleg.py": 2,
}


def _labels_zonder_for(src: str) -> int:
    return sum(1 for m in re.finditer(r"<label(?:(?!>).)*?>", src, re.S)
               if " for=" not in m.group(0))


def test_geen_nieuwe_labels_zonder_for():
    for full in _governed_files():
        rel = os.path.relpath(full, _PKG).replace(os.sep, "/")
        count = _labels_zonder_for(open(full, encoding="utf-8").read())
        ceiling = _LABEL_WHITELIST.get(rel, 0)
        assert count <= ceiling, (
            f"{rel}: {count} labels zonder for=, plafond {ceiling}. Nieuw formulierveld? "
            f"Gebruik web_base._field() — die koppelt label en veld altijd via for=/id.")
        assert count >= ceiling, (
            f"{rel}: {count} labels zonder for=, plafond {ceiling}. Schuld opgeruimd — "
            f"verlaag het plafond naar {count} (of verwijder de regel bij 0).")


# ── 2. ad-hoc <style>-blokken ────────────────────────────────────────────────
# Audit dd 2026-07-14, totaal 4: callbar (eigen chrome, bewust), overview
# (admin-blok, opruimkandidaat), cockpit2 (fragment-injectie in _frag + login-flow).
_STYLE_BLOCK_WHITELIST = {
    "views/callbar.py": 1,
    "views/overview.py": 1,
    "cockpit2.py": 2,
}


def test_geen_nieuwe_style_blokken():
    for full in _governed_files():
        rel = os.path.relpath(full, _PKG).replace(os.sep, "/")
        count = open(full, encoding="utf-8").read().count("<style")
        ceiling = _STYLE_BLOCK_WHITELIST.get(rel, 0)
        assert count <= ceiling, (
            f"{rel}: {count} <style>-blokken, plafond {ceiling}. CSS hoort in "
            f"static/nooch.css (componenten) of web_base._CSS (tokens/atomen), "
            f"niet als blob in een view.")
        assert count >= ceiling, (
            f"{rel}: {count} <style>-blokken, plafond {ceiling}. Blob opgeruimd — "
            f"verlaag het plafond naar {count} (of verwijder de regel bij 0).")


# ── 3. klasse-prefix-families (projectbreed) ────────────────────────────────
# Audit dd 2026-07-14: 58 families. Doel: een klein vocabulaire (card, btn, chip,
# tile, field, …) + varianten — zie de fase-2-inventarisatie. Dit plafond voorkomt
# dat er ondertussen nieuwe privé-prefixen bijkomen.
_PREFIX_CEILING = 60   # +1: 'ibx-' — de inbox-drawer is een bewust nieuw UI-component (globale chrome)
                       # +1: 'kn-' — de kennisbank (/kennisbank, prototype nooch-kb): drawer + zekerheids-
                       #      meter + bewijs-noten; expliciet besluit dd 2026-07-16 (akkoord Stefan)


def _prefix_families() -> set[str]:
    pref: set[str] = set()
    for full in _governed_files():
        src = open(full, encoding="utf-8").read()
        for m in re.findall(r"""class=\\?["']([^"'{}]+)""", src):
            for c in m.split():
                if "-" in c:
                    pref.add(c.split("-")[0])
    return pref


def test_geen_nieuwe_klasse_prefixen():
    fams = _prefix_families()
    assert len(fams) <= _PREFIX_CEILING, (
        f"{len(fams)} klasse-prefix-families, plafond {_PREFIX_CEILING}. Nieuw prefix "
        f"(bv. een scherm-eigen xx-*) = een nieuw privé-stylesheet. Hergebruik het "
        f"vocabulaire (docs/UX_PATTERNS.md → Kern-klassen) of maak er een expliciet "
        f"besluit van en verhoog het plafond mét reden. Families: {sorted(fams)}")
    assert len(fams) >= _PREFIX_CEILING, (
        f"{len(fams)} families, plafond {_PREFIX_CEILING}. Vocabulaire gekrompen — "
        f"verlaag het plafond naar {len(fams)} zodat de ratchet vastzet.")


# ── positieve tegenhangers: de nieuwe bouwstenen doen wat ze beloven ────────

def test_field_koppelt_label_aan_veld():
    html = _field("E-mailadres", "email", kind="email", required=True)
    assert 'for="f-email"' in html and 'id="f-email"' in html
    assert 'type="email"' in html and " required" in html
    # eigen id + textarea-variant
    ta = _field("Notitie", "body", kind="textarea", fid="note-body", value="a<b")
    assert 'for="note-body"' in ta and 'id="note-body"' in ta
    assert "a&lt;b</textarea>" in ta            # waarde wordt ge-escapet


def test_page_heeft_main_landmark_en_focusregel():
    html = _page("Titel", "<p>inhoud</p>")
    assert "<main><p>inhoud</p></main>" in html
    assert ":focus-visible" in html


def test_views_linken_designsysteem_css():
    """Views dragen geen eigen kopie van de design-CSS meer mee: één <link> naar
    /static/nooch.css met inhoud-hash (cache-bust), i.p.v. 56 KB inline per pagina."""
    from nooch_village.cockpit2_util import _DS_LINK, _EXTRA_CSS
    assert _DS_LINK.startswith('<link rel="stylesheet" href="/static/nooch.css?v=')
    assert len(_EXTRA_CSS) > 10_000          # het bestand is echt geladen
    for view in ("overview", "projects", "metrics", "catalog", "signals"):
        src = open(os.path.join(_PKG, "views", f"{view}.py"), encoding="utf-8").read()
        assert "_DS_LINK" in src, f"views/{view}.py linkt de design-CSS niet"
        assert "<style>{_EXTRA_CSS}</style>" not in src, (
            f"views/{view}.py draagt nog een inline kopie van de design-CSS")
