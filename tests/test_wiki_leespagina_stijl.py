"""De blok-vormgeving bereikt ook een leespagina (24 september 2026).

WAT ER MISGING, gezien op prod en niet in een toets. Sinds #574 rendert een POLICY of TOOL op een
leespagina: `_artefact_pagina` riep `_md(a.body)` aan zonder blokstand, dus er stonden geen
`.wb`-wrappers omheen. (Die renderer is op 28 september vervallen — alle drie de soorten delen nu
één editor — maar de les eronder is er alleen maar harder van geworden, zie de laatste alinea.) Mijn CSS voor het codeblok en de tabel was op `.wb` gescopet — en juist
DESIGNSYSTEM-001, de enige pagina met tabellen én een codeblok, is een policy.

Gemeten op de echte pagina: vijf tabellen (die zagen er toevallig goed uit, want `web_base._CSS`
heeft een generieke `table`-regel) en één codeblok met `background: rgba(0,0,0,0)` — volledig
ongestileerd.

DE OPLOSSING IS DE SCOPE, NIET EEN TWEEDE REGELSET. `.att-body` is de container in ALLEBEI de
gevallen: de note-editor gebruikt `class='att-body wiki-body'`, de leespagina `class='att-body'`.
Eén selector die beide dekt is minder om uit elkaar te laten lopen dan twee die hetzelfde zeggen.
En dat betaalde zich uit: toen de policypagina van renderer wisselde, verhuisde de bug niet mee.
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


def test_de_policypagina_krijgt_de_stijl(tmp_path):
    """DE PAGINA DIE HET LIET ZIEN. Een policy met een codeblok.

    HIJ HEETTE "leespagina" (28 september 2026). Die bestaat niet meer: een policy krijgt sinds
    deze stap dezelfde editor als een note, dus hij heeft nu wél `.wb`-wrappers. Dat maakt de
    stelling van dit bestand niet minder waar maar juist sterker — de vormgeving hangt aan
    `.att-body`, en die container is er in ALLEBEI de standen. Was de CSS op `.wb` blijven hangen,
    dan verhuisde de bug gewoon mee naar de volgende renderer."""
    from nooch_village import cockpit2
    from nooch_village.views.wiki import render_pagina
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    a = st.att.add(rol, "policy", title="Design System", domain="Money",
                   body="| A | B |\n|---|---|\n| 1 | 2 |\n\n```\ncode\n```")
    html = render_pagina(st, a.id, csrf_token="TOK", username="")
    assert "att-body" in html
    assert "<table" in html and "<pre" in html


def test_de_nu_tegenhanger_volgt_dezelfde_scope():
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    assert ".nu .att-body th" in nu, "de nu-laag hangt nog aan .wb"
