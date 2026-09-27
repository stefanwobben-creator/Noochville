"""Tools horen bij een cirkel, en de anchor-lead mag overal schrijven (27 september 2026).

TWEE BESLUITEN, één oorzaak. `can_write_artefact` kijkt naar de EIGENAAR-rol van een artefact. Een
dorpsbreed gereedschap dat onder één rol hangt, maakt de vervuller van die rol stilzwijgend de
enige die de kaart kan bijwerken — terwijl de tool zelf voor iedereen open staat ("Open to every
member", letterlijk in de body van de decision coach).

1. TOOLS ANKEREN OP DE CIRKEL. Algemene regel, geen oordeel per tool: `artefacts.TOOL_ANCHOR`.
   Een derde tool volgt hem zonder dat iemand opnieuw beslist.

2. DE ANCHOR-LEAD MAG ALTIJD SCHRIJVEN. Derde trede in `can_write_artefact`, en geen nieuw
   governance-begrip: dezelfde terugval die `mag_kanaal_verwijderen` en `wis_namens` al gebruiken.
   Zonder hem liep opruimwerk telkens vast op een artefact van een rol twee cirkels verderop,
   terwijl de anchor-lead die rol wél mag opheffen.

PLUS een los defect dat hier aan vast zat: `zorg_voor_tool` zocht met `store.list(rol, "tool")`,
en dat laat archief weg. "Idempotent" was dus alleen waar zolang niemand de kaart opruimde — wie
hem archiveerde kreeg er bij de volgende start een tweede naast, met een opgehoogd id.
"""
from __future__ import annotations

import inspect

from nooch_village import artefacts, cockpit2
from nooch_village.views.copy_prompt import TOOL_TITEL as CP_TITEL
from nooch_village.views.copy_prompt import zorg_voor_tool as cp_tool
from nooch_village.views.decision_coach import TOOL_ROL, TOOL_TITEL as DC_TITEL
from nooch_village.views.decision_coach import zorg_voor_tool as dc_tool
from nooch_village.views.overview import render_node
from nooch_village.views.tools import render_tools

ANCHOR = "mother_earth"
SUBROL = "mother_earth__nooch__community_and_email"
SUBCIRKEL = "mother_earth__nooch"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    sub = st.people.add("Sub Lead", "sub@test.nl")
    buiten = st.people.add("Buitenstaander", "buiten@test.nl")
    st.assign.assign(f"{ANCHOR}__circle_lead", "person", baas.id)
    st.assign.assign(f"{SUBCIRKEL}__circle_lead", "person", sub.id)
    return dd, st, baas, sub, buiten


def _mag(st, pid, owner):
    return artefacts.can_write_artefact("person", pid, owner, st.records, st.assign)


# ══ 1. De tool-anchor is een cirkel ══════════════════════════════════════════
def test_beide_tools_wijzen_naar_dezelfde_constante():
    """DE HELE POINTE VAN DE REGEL. Stonden ze los, dan is een derde tool weer een besluit."""
    assert TOOL_ROL == artefacts.TOOL_ANCHOR
    assert cockpit2._COPY_PROMPT_ROLLEN == (artefacts.TOOL_ANCHOR,)


def test_de_constante_is_de_wortelcirkel():
    assert artefacts.TOOL_ANCHOR == artefacts.ANCHOR_CIRCLE == ANCHOR


def test_de_anchor_is_echt_een_cirkel(tmp_path):
    """Een tool op een ROL geeft precies het probleem terug dat dit oplost."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    from nooch_village import org
    rec = st.records.get(artefacts.TOOL_ANCHOR)
    assert rec is not None and org.is_circle(rec)
    assert getattr(rec, "parent", None) in (None, ""), "de anchor heeft geen ouder"


def test_geen_van_beide_bestanden_noemt_nog_een_rol_id():
    """`reference, don't copy`: één plek waar staat wáár een tool hangt."""
    from nooch_village.views import decision_coach
    for mod in (decision_coach, cockpit2):
        bron = inspect.getsource(mod)
        assert 'TOOL_ROL = "mother_earth__nooch' not in bron
    kop = inspect.getsource(decision_coach).split("TOOL_TITEL")[0]
    assert "artefacts.TOOL_ANCHOR" in kop


def test_de_bootstrap_zet_ze_op_de_cirkel(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    op_anchor = {(a.title or "").lower() for a in st.att.list(ANCHOR, "tool")}
    assert DC_TITEL.lower() in op_anchor
    assert CP_TITEL.lower() in op_anchor


def test_er_komt_niets_meer_op_de_oude_rol(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert st.att.list(SUBROL, "tool", include_archived=True) == []


# ══ 2. De UI rendert een cirkel-anchor ═══════════════════════════════════════
def test_de_kaarten_staan_op_de_tools_pagina(tmp_path):
    """HIER STOND "op de cirkelpagina", en dat klopte tot 27 september 2026: tools zaten in de
    wiki-tab van hun eigenaar. Ze hebben nu een eigen ingang (`/tools`) en zijn daar weggehaald —
    het punt van DEZE toets, dat ze bereikbaar en zichtbaar zijn, is onveranderd."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    h = render_tools(st, csrf_token="t", username="anchor@test.nl")
    assert DC_TITEL in h and CP_TITEL in h
    assert "/decision-coach" in h and "/copy-prompt" in h


def test_ze_zijn_daar_ook_te_bewerken(tmp_path):
    """TWEE WIJZIGINGEN KRUISTEN ELKAAR HIER, en de uitkomst is de combinatie.

    #619 haalde tools uit de wiki-tab en gaf ze een eigen ingang (`/tools`); die wees voor het
    bewerken door naar de ROL. Deze PR verplaatste het bewerken naar de LEESPAGINA van het
    artefact zelf — één bewerkpad per artefact. Samen: `/tools` wijst door naar de leespagina,
    want daar staat het formulier. Doorverwijzen naar de rol zou wijzen naar een plek waar niets
    meer te bewerken valt.

    De poort blijft dezelfde: alleen wie mag schrijven ziet de weg erheen."""
    from nooch_village.views.wiki import pagina_url, render_pagina
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    h = render_tools(st, csrf_token="t", username="anchor@test.nl")
    tools = st.att.list(ANCHOR, "tool")
    assert len(tools) >= 2
    for t in tools:
        assert pagina_url(t.id) in h, t.id
    assert "edit on the role" not in h, "hij wijst nog naar de rol"
    assert render_tools(st, csrf_token="t", username="buiten@test.nl").count("Edit") == 0
    # En daar staat het formulier ook echt.
    assert "value='artefact_edit'" in render_pagina(st, tools[0].id, csrf_token="t",
                                                    username="anchor@test.nl")


def test_de_copy_prompt_pagina_slikt_een_cirkel(tmp_path):
    """De generator is ge-URL-parameteriseerd op een rol (`?rol=<id>`); met de anchor erin hoort
    hij een echte pagina te geven en niet de rolkiezer."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    from nooch_village.views.copy_prompt import render_copy_prompt
    h = render_copy_prompt(st, rol=ANCHOR)
    assert len(h) > 12000 and "Not found" not in h


# ══ 3. De anchor-lead mag overal schrijven ═══════════════════════════════════
def test_de_anchor_lead_mag_op_een_rol_twee_cirkels_verderop(tmp_path):
    """DE KERN. `circle_of(SUBROL)` is de SUBcirkel, dus trede 2 wijst naar een andere lead."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert artefacts.circle_of(SUBROL, st.records) == SUBCIRKEL
    assert _mag(st, baas.id, SUBROL) is True


def test_hij_mag_het_op_elk_artefact(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    for owner in (ANCHOR, SUBCIRKEL, SUBROL, "mother_earth__nooch__compliance"):
        assert _mag(st, baas.id, owner) is True, owner


def test_de_bestaande_twee_treden_blijven_gelden(tmp_path):
    """De sub-lead mag in zijn eigen cirkel, de rolvervuller op zijn eigen rol."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert _mag(st, sub.id, SUBROL) is True
    vervuller = st.people.add("Rolvervuller", "rol@test.nl")
    st.assign.assign(SUBROL, "person", vervuller.id)
    assert _mag(st, vervuller.id, SUBROL) is True


def test_een_gewone_mens_mag_nog_steeds_niets(tmp_path):
    """DE POORT BLIJFT EEN POORT. Zou de derde trede naar "iedereen" lekken, dan is de hele
    eigenaar-regel weg."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    for owner in (ANCHOR, SUBCIRKEL, SUBROL):
        assert _mag(st, buiten.id, owner) is False, owner


def test_een_sub_lead_wordt_er_niet_stiekem_anchor_lead_van(tmp_path):
    """Hij leidt de subcirkel, niet het dorp: buiten zijn eigen tak blijft hij buiten."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert _mag(st, sub.id, ANCHOR) is False
    assert _mag(st, sub.id, "mother_earth__shareholder") is False


def test_het_geldt_ook_voor_een_persona(tmp_path):
    """"identiek voor person en persona" — die belofte stond er al en blijft staan."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    st.assign.assign(f"{ANCHOR}__circle_lead", "persona", "noochie")
    assert artefacts.can_write_artefact("persona", "noochie", SUBROL, st.records, st.assign) is True


def test_een_onbekende_eigenaar_blijft_dicht(tmp_path):
    """Fail-closed: geen record, geen schrijfrecht — ook niet voor de anchor-lead."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert _mag(st, baas.id, "bestaat-niet") is False
    assert _mag(st, baas.id, "") is False


def test_het_is_geen_nieuw_governance_begrip():
    """Dezelfde terugval als elders; geen tweede mechanisme om "wie leidt het dorp" vast te
    stellen, en de lead-check staat één keer uitgeschreven."""
    bron = inspect.getsource(artefacts.can_write_artefact)
    assert "ANCHOR_CIRCLE" in bron
    assert bron.count("__circle_lead") == 0, "de lead-rol wordt hier weer zelf samengesteld"
    assert inspect.getsource(artefacts).count('f"{circle_id}__circle_lead"') == 1


# ══ 4. Idempotent, ook na archiveren ═════════════════════════════════════════
def test_archiveren_levert_geen_tweede_kaart_op(tmp_path):
    """HET DEFECT. `list()` laat archief standaard weg, dus na opruimen kwam er bij de volgende
    start een tweede naast met een opgehoogd id."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    for zorg in (dc_tool, cp_tool):
        eerste = zorg(st.records, st.att, ANCHOR)
        st.att.archive(eerste, actor_id=baas.id, actor_type="person")
        assert zorg(st.records, st.att, ANCHOR) == eerste, zorg.__module__
    assert len(st.att.list(ANCHOR, "tool", include_archived=True)) == 2


def test_beide_zoekers_kijken_in_het_archief():
    from nooch_village.views import copy_prompt, decision_coach
    for mod in (copy_prompt, decision_coach):
        bron = inspect.getsource(mod.zorg_voor_tool)
        assert "include_archived=True" in bron, mod.__name__


def test_een_ontbrekende_anchor_geeft_geen_exceptie(tmp_path):
    """Fail-soft: een ontbrekend record is een governance-feit, geen reden om de cockpit op te
    houden. Die belofte stond er al."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert dc_tool(st.records, st.att, "bestaat-niet") == ""
    assert cp_tool(st.records, st.att, "bestaat-niet") == ""


# ══ 5. Scherm én server, want het zijn er twee ═══════════════════════════════
#
# DIT STOND NIET IN DE OPDRACHT, en het is de reden dat de opdracht anders niet werkt.
# `can_write_artefact` is het SCHERM (`views/overview.py` → `_can_edit_artefacts`, die de
# bewerkknoppen rendert). De SERVER-poort voor add/edit/archive is `_artefact_gate` →
# `artefacts.mag_schrijven_op_domein`, een andere functie sinds #610. Alleen de eerste verruimen
# laat de knop verschijnen op een artefact dat de server daarna weigert — het spiegelbeeld van de
# fout die #610 al een ronde kostte.
def _gegated_domein(st):
    """Een domein met precies één houder-rol; alleen dan gaat de poort écht dicht (bij nul of
    twee houders valt hij fail-open, zie de docstring van `mag_schrijven_op_domein`)."""
    from collections import Counter
    tel = Counter()
    for r in st.records.all():
        if getattr(r, "archived", False) or getattr(r, "slaapt", False):
            continue
        for d in (getattr(getattr(r, "definition", None), "domains", None) or []):
            tel[str(d).strip()] += 1
    for d, n in tel.items():
        if n == 1 and d:
            return d
    return ""


def test_de_server_poort_laat_de_anchor_lead_ook_door(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    dom = _gegated_domein(st)
    if not dom:
        import pytest
        pytest.skip("deze dataset heeft geen domein met precies één houder")
    assert artefacts.mag_schrijven_op_domein(st, dom, buiten.id) is False, "de poort staat al open"
    assert artefacts.mag_schrijven_op_domein(st, dom, baas.id) is True


def test_scherm_en_server_geven_hetzelfde_antwoord(tmp_path):
    """DE TOETS DIE DE HELE REDEN IS. Zouden ze uiteenlopen, dan is er een knop die weigert."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    dom = _gegated_domein(st)
    if not dom:
        import pytest
        pytest.skip("deze dataset heeft geen domein met precies één houder")
    for pid in (baas.id, buiten.id):
        scherm = _mag(st, pid, SUBROL)
        server = artefacts.mag_schrijven_op_domein(st, dom, pid)
        assert scherm == server, f"{pid}: scherm={scherm} server={server}"


def test_de_configuratiefout_blijft_fail_open(tmp_path):
    """"Een configuratiefout sluit niemand buiten" — die regel is niet aangeraakt."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert artefacts.mag_schrijven_op_domein(st, "bestaat-echt-niet", buiten.id) is True
    assert artefacts.mag_schrijven_op_domein(st, "", buiten.id) is True


def test_een_lege_actor_mag_nog_steeds_niets(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    assert artefacts.mag_schrijven_op_domein(st, _gegated_domein(st) or "x", "") is False


def test_verwijderen_is_niet_meeverruimd():
    """VERWIJDEREN VOLGT DE SCHRIJFREGEL NIET, en dat blijft zo. De domein-poort
    (`mag_schrijven_op_domein`) en de schrijf-poort (`can_write_artefact`) horen hier niet: wie op
    een artefact mag schrijven mag het daarom nog niet weggooien.

    ÉÉN TREDE IS ERBIJ GEKOMEN (27 september 2026, besluit Stefan): de anchor-lead mag overal
    permanent verwijderen, net zoals hij overal al mag archiveren. Dat is een tweede Circle
    Lead-check, geen andere soort regel — en verder verandert er niets, wat deze toets hieronder
    per rol nagaat."""
    bron = inspect.getsource(cockpit2._act_artefact_delete)
    # OP DE AANROEP EN NIET OP DE NAAM. De uitleg boven de tak NOEMT die twee poorten juist — om
    # te zeggen dat de anchor-terugval dezelfde is — en een verbod op de kale naam zou dus de
    # documentatie verbieden in plaats van de code. Met een haakje erachter is het een aanroep.
    assert "mag_schrijven_op_domein(" not in bron
    assert "can_write_artefact(" not in bron
    # Precies twee lead-checks: de eigen cirkel en de anchor. Een derde zou een nieuwe regel zijn.
    assert bron.count("is_circle_lead(") == 2
    assert "artefacts.ANCHOR_CIRCLE" in bron, "de wortelcirkel staat hier als kale string"


def _wis(st, dd, aid, username):
    velden = {"aid": aid, "next": "/wiki"}
    c = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/wiki",
                      form=velden, username=username, action="artefact_delete", data_dir=dd)
    try:
        return cockpit2.ACTIONS["artefact_delete"](c)[1]
    except cockpit2.Forbidden as e:
        return f"✗ {e}"


def test_de_anchor_lead_mag_overal_verwijderen(tmp_path):
    """DE NIEUWE TREDE. Het artefact hangt aan een rol twee cirkels verderop, waar hij geen
    Circle Lead van is."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(SUBROL, "note", title="Weg hiermee", body="x")
    assert _wis(st, dd, a.id, baas.email).startswith("🗑")
    assert cockpit2._Stores(dd).att.get(a.id) is None


def test_de_eigen_circle_lead_ook_nog_steeds(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(SUBROL, "note", title="Van de subcirkel", body="x")
    assert _wis(st, dd, a.id, sub.email).startswith("🗑")


def test_de_rolvervuller_nog_steeds_niet(tmp_path):
    """"De rolvervuller zelf blijft uitgesloten van hard verwijderen, dat verandert niet."
    Archiveren mag hij wél — dat is een andere actie en een omkeerbare."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    vervuller = st.people.add("Rolvervuller", "rol@test.nl")
    st.assign.assign(SUBROL, "person", vervuller.id)
    a = st.att.add(SUBROL, "note", title="Van mijn eigen rol", body="x")
    assert _mag(st, vervuller.id, SUBROL) is True, "hij mag er wél op schrijven"
    assert _wis(st, dd, a.id, vervuller.email).startswith("✗")
    assert cockpit2._Stores(dd).att.get(a.id) is not None


def test_een_willekeurige_mens_al_helemaal_niet(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(SUBROL, "note", title="Niet van jou", body="x")
    assert _wis(st, dd, a.id, buiten.email).startswith("✗")
    assert cockpit2._Stores(dd).att.get(a.id) is not None
