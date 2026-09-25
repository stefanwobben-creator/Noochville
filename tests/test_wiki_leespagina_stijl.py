"""De blok-vormgeving bereikt ook een leespagina (24 september 2026).

WAT ER MISGING, gezien op prod en niet in een toets. Sinds #574 rendert een POLICY of TOOL op een
leespagina: `_artefact_pagina` roept `_md(a.body)` aan zonder blokstand, dus er staan geen
`.wb`-wrappers omheen. Mijn CSS voor het codeblok en de tabel was op `.wb` gescopet — en juist
DESIGNSYSTEM-001, de enige pagina met tabellen én een codeblok, is een policy.

Gemeten op de echte pagina: vijf tabellen (die zagen er toevallig goed uit, want `web_base._CSS`
heeft een generieke `table`-regel) en één codeblok met `background: rgba(0,0,0,0)` — volledig
ongestileerd.

DE OPLOSSING IS DE SCOPE, NIET EEN TWEEDE REGELSET. `.att-body` is de container in ALLEBEI de
gevallen: de note-editor gebruikt `class='att-body wiki-body'`, de leespagina `class='att-body'`.
Eén selector die beide dekt is minder om uit elkaar te laten lopen dan twee die hetzelfde zeggen.
"""
from __future__ import annotations

import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()


def test_de_blokvormgeving_hangt_aan_de_container_en_niet_aan_de_wrapper():
    """`.wb` bestaat alleen in de blokstand; `.att-body` in allebei."""
    for tag in ("pre", "table"):
        assert re.search(rf"\.att-body {tag}\{{", CSS), f"{tag} is nog op .wb gescopet"
        assert not re.search(rf"\.wb {tag}\{{", CSS), f"{tag} hangt nog aan .wb"


def test_de_leespagina_van_een_policy_krijgt_de_stijl(tmp_path):
    """DE PAGINA DIE HET LIET ZIEN. Een policy met een codeblok, gerenderd zoals #574 dat doet."""
    from nooch_village import cockpit2
    from nooch_village.views.wiki import render_pagina
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    a = st.att.add(rol, "policy", title="Design System", domain="Money",
                   body="| A | B |\n|---|---|\n| 1 | 2 |\n\n```\ncode\n```")
    html = render_pagina(st, a.id, csrf_token="TOK", username="")
    assert "class='att-body'" in html
    assert "<table" in html and "<pre" in html
    assert "class='wb'" not in html, "een leespagina hoort geen blok-wrappers te hebben"


def test_de_nu_tegenhanger_volgt_dezelfde_scope():
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    assert ".nu .att-body th" in nu, "de nu-laag hangt nog aan .wb"
