"""De tool-kaart: `[[TOOL-XXX]]` op een eigen regel wordt een kaart (24 september 2026).

DE KEUZE DIE IK HIER MAAK, want het ontwerp liet hem open ("`[[TOOL-XXX]]`-verwijzing of het
interne pad"). Het wordt de wiki-verwijzing, en daarmee moet de resolutie tools en policies kennen
— tot vandaag keek `wiki.resolve` alleen naar notes.

WAAROM DAT NU KAN. Op prod staan NUL `[[verwijzingen]]`, in geen enkel artefact. Het verbreden van
de resolutie verandert vandaag dus aantoonbaar niets aan wat er op het scherm staat; het maakt
alleen mogelijk wat sinds #574 al logisch was, namelijk dat een tool en een policy hun eigen
pagina hebben en je daar dus naar kunt wijzen.

WAAROM NIET ALLEEN TOOLS. "Tools wel, policies niet" zou een derde regel zijn om te onthouden,
terwijl beide sinds #574 een permalink hebben. Asymmetrie is hier duurder dan volledigheid.

`wiki.paginas` BLIJFT NOTES-ONLY, want die betekent iets anders: hij voedt de bron-check die over
FEITEN loopt, en die wonen alleen op notes. Voor de resolutie is er nu `wiki.verwijsbaar`.

ALLEEN OP EEN EIGEN REGEL WORDT HET EEN KAART, net als bij de embed. Een verwijzing midden in een
zin blijft een pil — anders verandert één woord in een alinea de vorm van de hele pagina.

GEEN LIVE INSLUITING, zoals afgesproken. Een interne tool is een SCHERM; insluiten betekent een
iframe (auth, geneste navigatie) of een tweede renderpad per tool, en dat contract bestaat voor
geen van de vijf tools op prod.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki
from nooch_village.cockpit2_util import _md_naar_bron
from nooch_village.views.wiki import _body_html


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    tool = st.att.add(rol, "tool", title="Decision coach", url="/decision-coach")
    note = st.att.add(rol, "note", title="Een notitie")
    pol = st.att.add(rol, "policy", title="Geld", domain="Money")
    return st, rol, tool, note, pol


# ── 1. De resolutie kent nu alle artefact-soorten ────────────────────────────
def test_verwijsbaar_bevat_alle_drie_de_soorten(tmp_path):
    st, rol, tool, note, pol = _dorp(tmp_path)
    ids = {a.id for a in wiki.verwijsbaar(st.att)}
    assert {tool.id, note.id, pol.id} <= ids


def test_paginas_blijft_notes_only(tmp_path):
    """Die voedt de bron-check, en die loopt over FEITEN — en feiten wonen alleen op notes."""
    st, rol, tool, note, pol = _dorp(tmp_path)
    ids = {a.id for a in wiki.paginas(st.att)}
    assert note.id in ids
    assert tool.id not in ids and pol.id not in ids


def test_een_verwijzing_naar_een_tool_lost_nu_op(tmp_path):
    st, rol, tool, note, pol = _dorp(tmp_path)
    html = _body_html(f"[[{tool.id}]]", wiki.verwijsbaar(st.att), blokken=True)
    assert "no unique page with this name" not in html


# ── 2. De kaart ──────────────────────────────────────────────────────────────
def test_een_tool_op_een_eigen_regel_wordt_een_kaart(tmp_path):
    st, rol, tool, note, pol = _dorp(tmp_path)
    html = _body_html(f"[[{tool.id}]]", wiki.verwijsbaar(st.att), blokken=True)
    assert "wb-emb--tool" in html
    assert "Decision coach" in html


def test_de_kaart_wijst_naar_de_pagina_van_de_tool(tmp_path):
    st, rol, tool, note, pol = _dorp(tmp_path)
    html = _body_html(f"[[{tool.id}]]", wiki.verwijsbaar(st.att), blokken=True)
    assert wiki.pagina_url(tool.id) in html


def test_een_verwijzing_in_een_zin_blijft_een_pil(tmp_path):
    """DE GRENS. Zou elke verwijzing een kaart worden, dan verandert één woord in een alinea de
    vorm van de hele pagina."""
    st, rol, tool, note, pol = _dorp(tmp_path)
    html = _body_html(f"zie [[{tool.id}]] hiervoor", wiki.verwijsbaar(st.att), blokken=True)
    assert "wb-emb--tool" not in html
    assert "class='pill'" in html


def test_een_note_wordt_geen_tool_kaart(tmp_path):
    st, rol, tool, note, pol = _dorp(tmp_path)
    html = _body_html(f"[[{note.id}]]", wiki.verwijsbaar(st.att), blokken=True)
    assert "wb-emb--tool" not in html


def test_er_wordt_niets_ingesloten(tmp_path):
    """Afgesproken in het ontwerp: een kaart die naar de tool linkt, geen iframe."""
    st, rol, tool, note, pol = _dorp(tmp_path)
    html = _body_html(f"[[{tool.id}]]", wiki.verwijsbaar(st.att), blokken=True)
    assert "<iframe" not in html


# ── 3. De rondgang ───────────────────────────────────────────────────────────
def test_de_verwijzing_komt_terug_zoals_hij_stond(tmp_path):
    """`data-ref` draagt de ORIGINELE verwijzing; zonder dat komt de titel terug in plaats van
    het id, en dat is een andere verwijzing dan wat de schrijver typte."""
    st, rol, tool, note, pol = _dorp(tmp_path)
    bron = f"[[{tool.id}]]"
    html = _body_html(bron, wiki.verwijsbaar(st.att), blokken=True)
    assert _md_naar_bron(html) == bron


def test_de_rondgang_blijft_gelijk(tmp_path):
    st, rol, tool, note, pol = _dorp(tmp_path)
    pags = wiki.verwijsbaar(st.att)
    for bron in (f"[[{tool.id}]]", f"tekst\n\n[[{tool.id}]]\n\nmeer",
                 f"zie [[{tool.id}]] hier"):
        eerste = _body_html(bron, pags, blokken=True)
        assert _body_html(_md_naar_bron(eerste), pags, blokken=True) == eerste, bron
