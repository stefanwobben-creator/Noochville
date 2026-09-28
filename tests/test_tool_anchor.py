"""Een tool hangt aan de cirkel — in de data, in de schrijfweg, en maar één keer (28 sep 2026).

WAT ER MISGING, gemeten in de productiedata en niet bedacht. `artefacts.TOOL_ANCHOR` legt sinds
27 september uit dat een tool-artefact bij de anchor-cirkel hoort, met de reden erbij: een tool die
onder één rol hangt maakt de vervuller van die rol stilzwijgend poortwachter van iets dat voor
iedereen open staat. Die regel werd door de twee ZAAI-wegen gevolgd — en verder door niets:

  * `_act_artefact_add` nam de `owner` kritiekloos uit het formulier over. Alleen een policy werd
    tegen de eigen rol gevalideerd; een tool landde waar je hem stuurde.
  * bestaande artefacten van vóór de regel bleven hangen waar ze stonden. Op prod: drie stuks.

Daarbovenop stond de copy-prompt-generator er DRIE keer als artefact (rol copywriter 14 augustus,
rol community & email 26 september, cirkel 27 september — drie generaties van dezelfde zaailijst,
identieke body, nooit door een mens aangeraakt) náást de vaste schermknop op de Nooch-cirkel die
hetzelfde doet. Vier kaarten met dezelfde naam op `/tools`.

DEZE RATCHET SLUIT ALLE VIER DE GATEN: de data-regel, de schrijfweg, de migratie van wat er al
stond, en de dubbeling tussen een artefact en een schermknop.
"""
from __future__ import annotations

import inspect
import urllib.parse

from nooch_village import artefacts, cockpit2, org

ANCHOR = artefacts.TOOL_ANCHOR

#: BEWUST NIET OP DE ANCHOR-CIRKEL, met de reden erbij. Leeg, en dat is de bedoeling: het Website
#: Handboek (`TOOL-WEBSIT-001`) was de laatste uitzondering en is meeverhuisd — "geen uitzondering",
#: besluit Stefan. Wie er een toevoegt, zet hier op waarom.
BUITEN: dict[str, str] = {}


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


# ══ 1. De data ═══════════════════════════════════════════════════════════════
def test_elk_tool_artefact_hangt_aan_de_cirkel(tmp_path):
    """DE REGEL ZELF, op een dorp zoals het uit de zaad-dataset komt."""
    dd, st = _dorp(tmp_path)
    fout = {a.id: a.anchor for a in st.att.by_kind("tool", include_archived=True)
            if a.anchor != ANCHOR and a.id not in BUITEN}
    assert not fout, (
        f"tool-artefact op een rol: {fout}. Hang hem aan `artefacts.TOOL_ANCHOR`, of zet hem in "
        f"`BUITEN` in deze toets met een reden.")


def test_de_anchor_is_echt_een_cirkel(tmp_path):
    """Anders verplaatst deze regel het probleem alleen maar."""
    dd, st = _dorp(tmp_path)
    rec = st.records.get(ANCHOR)
    assert rec is not None and org.is_circle(rec)


def test_de_uitzonderingen_bestaan_nog(tmp_path):
    """Een uitzondering voor een artefact dat er niet meer is, dekt de volgende vergissing af."""
    dd, st = _dorp(tmp_path)
    ids = {a.id for a in st.att.by_kind("tool", include_archived=True)}
    assert not (set(BUITEN) - ids), f"staat in BUITEN maar bestaat niet: {sorted(set(BUITEN) - ids)}"


# ══ 2. De schrijfweg ═════════════════════════════════════════════════════════
def _add(st, dd, kind, owner, titel, **extra):
    velden = {"csrf": "T", "owner": owner, "kind": kind, "title": titel, "next": "/tools", **extra}
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/tools", form=velden,
                        username="anchor@test.nl", action="artefact_add", data_dir=dd)
    return cockpit2.ACTIONS["artefact_add"](ctx)


def test_een_tool_aanmaken_op_een_rol_landt_op_de_cirkel(tmp_path):
    """HET GAT DAT DE RATCHET ALLEEN ZOU MELDEN. Een toets die achteraf controleert is een toets
    die je pas leest als het al in de data staat; deze tak laat het niet meer gebeuren."""
    dd, st = _dorp(tmp_path)
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    st.assign.assign(f"{ANCHOR}__circle_lead", "person", baas.id)
    _add(st, dd, "tool", "mother_earth__nooch__community_and_email", "Een nieuwe tool",
         url="/ergens")
    verse = cockpit2._Stores(dd)
    nieuw = [a for a in verse.att.by_kind("tool") if a.title == "Een nieuwe tool"]
    assert len(nieuw) == 1 and nieuw[0].anchor == ANCHOR, [a.anchor for a in nieuw]


def test_een_note_blijft_gewoon_bij_zijn_rol(tmp_path):
    """DE TEGENPROEF. Zou de tak ruimer staan, dan verhuist elke pagina naar de wortelcirkel."""
    dd, st = _dorp(tmp_path)
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    st.assign.assign(f"{ANCHOR}__circle_lead", "person", baas.id)
    rol = "mother_earth__nooch__community_and_email"
    _add(st, dd, "note", rol, "Een pagina")
    verse = cockpit2._Stores(dd)
    assert [a.anchor for a in verse.att.by_kind("note") if a.title == "Een pagina"] == [rol]


def test_de_tak_leest_dezelfde_constante():
    """`reference, don't copy`: geen tweede plek die "mother_earth" uitschrijft."""
    bron = inspect.getsource(cockpit2._act_artefact_add)
    assert "artefacts.TOOL_ANCHOR" in bron
    assert '"mother_earth"' not in bron


# ══ 3. Wat er al stond ═══════════════════════════════════════════════════════
def test_een_bestaande_tool_op_een_rol_verhuist_mee(tmp_path):
    """DE MIGRATIE. Een regel die alleen voor nieuwe gevallen geldt, is geen regel maar een
    gewoonte — en op prod stond het Website Handboek al sinds 21 augustus op een rol."""
    dd, st = _dorp(tmp_path)
    rol = "mother_earth__nooch__community_and_email"
    a = st.att.add(rol, "tool", title="Handboek", body="tekst", url="https://voorbeeld.nl",
                   actor_id="iemand", actor_type="person")
    cockpit2._bootstrap(dd)                              # zoals bij elke start
    na = cockpit2._Stores(dd).att.get(a.id)
    assert na.anchor == ANCHOR
    assert na.id == a.id, "het id is een permalink en hoort niet mee te verhuizen"
    assert na.body == "tekst", "de inhoud is van wie hem schreef"
    assert "verhuisd" in (na.versions[-1].get("change_note") or ""), "de verhuizing staat niet in de historie"


def test_de_verhuizing_is_idempotent(tmp_path):
    dd, st = _dorp(tmp_path)
    a = st.att.add("mother_earth__nooch", "tool", title="X", url="/x")
    cockpit2._bootstrap(dd)
    n1 = len(cockpit2._Stores(dd).att.get(a.id).versions)
    cockpit2._bootstrap(dd)
    assert len(cockpit2._Stores(dd).att.get(a.id).versions) == n1


def test_een_gearchiveerde_tool_verhuist_ook(tmp_path):
    """Anders staat de regel niet in de data maar in de weergave: haal je hem uit het archief, dan
    hangt hij opeens weer verkeerd."""
    dd, st = _dorp(tmp_path)
    a = st.att.add("mother_earth__nooch", "tool", title="Oud", url="/x")
    st.att.archive(a.id, actor_id="system", actor_type="persona")
    cockpit2._bootstrap(dd)
    assert cockpit2._Stores(dd).att.get(a.id).anchor == ANCHOR


# ══ 4. Eén tool, niet twee ═══════════════════════════════════════════════════
def _schermlinks(st) -> dict[str, str]:
    """Elke vaste schermknop: pad → label. Uit dezelfde tabellen die `/tools` rendert."""
    from nooch_village.views.overview import _DOMAIN_TOOLS, _ROLE_TOOLS
    uit = {}
    for rijen in list(_ROLE_TOOLS.values()) + list(_DOMAIN_TOOLS.values()):
        for label, _desc, href in rijen:
            if href:
                uit[urllib.parse.urlsplit(href.replace("&amp;", "&")).path] = label
    return uit


def test_geen_tool_artefact_dubbelt_een_schermknop(tmp_path):
    """DE REGEL DIE DE DRIE COPY-PROMPT-KAARTEN HAD GEVANGEN.

    `/tools` toont de artefacten én de vaste schermknoppen onder elkaar. Wijst een artefact naar
    hetzelfde scherm als een knop die er al is, dan staan er twee kaarten met dezelfde naam en
    dezelfde bestemming — en moet de lezer raden wat het verschil is. Er is er geen.

    OP HET PAD EN NIET OP DE TITEL: `?rol=<id>` maakt van dezelfde bestemming drie verschillende
    urls, en precies zo bleven de drie kopieën naast elkaar staan zonder op te vallen."""
    dd, st = _dorp(tmp_path)
    links = _schermlinks(st)
    dubbel = {a.id: a.url for a in st.att.by_kind("tool", include_archived=True)
              if urllib.parse.urlsplit(a.url or "").path in links}
    assert not dubbel, (
        f"tool-artefact met dezelfde bestemming als een schermknop: {dubbel}. Kies er één — de "
        f"knop staat in `_ROLE_TOOLS`/`_DOMAIN_TOOLS`, het artefact in de AttachmentStore.")


def test_de_decision_coach_is_geen_dubbele(tmp_path):
    """De tegenproef op dezelfde regel: die tool HEEFT geen schermknop, dus zijn artefact is het
    enige oppervlak. Hem "voor de consistentie" ook opruimen zou het vermogen weghalen."""
    dd, st = _dorp(tmp_path)
    coach = [a for a in st.att.by_kind("tool") if a.url == "/decision-coach"]
    assert len(coach) == 1
    assert "/decision-coach" not in _schermlinks(st)


def test_de_copy_prompt_generator_bestaat_nog_wel_als_knop(tmp_path):
    """Wat er weg is, is de KAART — niet het gereedschap. Zonder deze toets leest de opruiming als
    "de generator is verdwenen"."""
    from nooch_village.views.tools import render_tools
    dd, st = _dorp(tmp_path)
    h = render_tools(st, csrf_token="T", username="")
    assert "Copy prompt generator" in h and "/copy-prompt" in h
    assert h.count("Copy prompt generator") == 1, "hij staat er weer dubbel"


# ══ 5. De copywriter blijft bereikbaar ═══════════════════════════════════════
def test_de_copywriter_staat_in_de_rolkiezer(tmp_path):
    """HET GEVOLG DAT NIET MOCHT GEBEUREN. `TOOL-COPYWR-001` was het enige oppervlak dat naar
    `/copy-prompt?rol=<copywriter>` wees; die kaart is nu weg. `_rolkiezer` slaat een rol over die
    geen eigen policies én geen inclusie heeft, en de copywriter heeft er nul van allebei — dus
    zonder een inclusie zou het opruimen een rol stil onbereikbaar maken.

    GEEN NIEUW MECHANISME: `copy_stack` bestaat precies hiervoor, en `zaad` laat een menselijke
    keuze met rust."""
    import dataclasses

    from nooch_village.views.copy_prompt import _rolkiezer
    dd, st = _dorp(tmp_path)
    # De zaad-dataset kent de copywriter niet (hij is op prod via governance ontstaan), dus hier
    # neergezet zoals hij daar staat: onder de Nooch-cirkel, zonder eigen policies.
    basis = st.records.get("mother_earth__nooch__community_and_email")
    st.records.put(dataclasses.replace(
        basis, id="mother_earth__nooch__copywriter",
        definition=dataclasses.replace(basis.definition, name="Copywriter", domains=[])))
    cockpit2._bootstrap(dd)                              # het zaad pakt zodra het record er is
    verse = cockpit2._Stores(dd)
    assert verse.copy_stack.inclusies("mother_earth__nooch__copywriter") == [
        "mother_earth__nooch__community_and_email"]
    assert "Copywriter" in _rolkiezer(verse)


def test_het_zaad_overschrijft_geen_menselijke_keuze(tmp_path):
    """`zaad` raakt een bestaande compositie niet aan — zodra een mens hem aanraakte is dát de
    waarheid. Die belofte stond er al; hier wordt hij gebruikt."""
    dd, st = _dorp(tmp_path)
    st.copy_stack.zet("mother_earth__nooch__copywriter", "mother_earth__nooch", True, door="mens")
    cockpit2._bootstrap(dd)
    assert cockpit2._Stores(dd).copy_stack.inclusies("mother_earth__nooch__copywriter") == [
        "mother_earth__nooch"]
