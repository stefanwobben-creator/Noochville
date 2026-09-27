"""Drie samenhangende punten (27 september 2026).

1. VERWIJDEREN BETEKENT NOOIT MEER TERUGZAAIEN. Elke zaai-routine checkt of het artefact er al
   staat, archief meegerekend. Dat dekt archiveren — maar een HARD verwijderd artefact
   (`AttachmentStore.remove`) laat helemaal geen rij achter, dus de eerstvolgende zaai-run ziet
   een lege plek en zaait opnieuw. Stefan verwijderde TOOL-STRATE-001 vier keer op één dag; hij
   kwam vier keer terug.

   Gegrond op het CHANGELOG, niet op een nieuwe store: `log_change` schrijft de verwijdering al
   weg vóór de rij verdwijnt — hij droeg alleen de titel niet, en een seeder kent geen id.

   HARDE EIS: dit stopt alleen de SEEDER. Een mens die bewust een artefact met die titel aanmaakt
   moet dat gewoon kunnen, ook als die titel ooit verwijderd is.

2. DE ANCHOR-LEAD MAG OVERAL PERMANENT VERWIJDEREN, net zoals hij overal al mag archiveren. Eén
   trede erbij, verder niets: de rolvervuller blijft uitgesloten.

3. TOOLS EN POLICIES WORDEN INLINE BEWERKT op hun eigen leespagina. Zelfde reden als bij notes op
   21 september: één bewerkpad per artefact, niet twee die uit elkaar kunnen lopen.
"""
from __future__ import annotations

import inspect

from nooch_village import artefacts, cockpit2
from nooch_village.views.decision_coach import TOOL_TITEL as DC_TITEL
from nooch_village.views.decision_coach import zorg_voor_tool as dc_tool
from nooch_village.views.overview import render_node
from nooch_village.views.wiki import render_pagina

ANCHOR = "mother_earth"
ROL = "mother_earth__nooch__compliance"
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


def _delete(st, dd, aid, username):
    velden = {"aid": aid, "next": "/wiki"}
    c = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/wiki",
                      form=velden, username=username, action="artefact_delete", data_dir=dd)
    try:
        return cockpit2.ACTIONS["artefact_delete"](c)[1]
    except cockpit2.Forbidden as e:
        return f"✗ {e}"


# ══ 1. De tombstone ══════════════════════════════════════════════════════════
def test_de_changelog_regel_draagt_nu_de_titel(tmp_path):
    """ZONDER TITEL IS DE VERWIJDERING ONVINDBAAR voor een seeder: die kent de PLEK en de NAAM,
    nooit het id dat het artefact ooit had."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Iets", body="x")
    entry = artefacts.log_change(dd, action="add", artefact=a, records=st.records)
    assert entry["title"] == "Iets"


def test_een_verwijderde_plek_wordt_niet_terugzaaid(tmp_path):
    """DE KERN. Zaaien, hard verwijderen, opnieuw zaaien → er groeit niets terug."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    aid = dc_tool(st.records, st.att, ANCHOR)
    assert aid
    artefacts.log_change(dd, action="delete", artefact=st.att.get(aid), records=st.records)
    st.att.remove(aid)
    assert dc_tool(st.records, st.att, ANCHOR) == ""
    # ALLEEN DEZE TITEL, niet de hele anchor: de zaad-dataset zet er meer dan één tool neer, en
    # die horen juist ongemoeid te blijven.
    titels = [a.title for a in st.att.list(ANCHOR, "tool", include_archived=True)]
    assert DC_TITEL not in titels, titels
    assert titels, "de andere tools zijn meegesneuveld"


def test_archiveren_blijft_werken_zoals_het_deed(tmp_path):
    """De bestaande `include_archived`-check is niet vervangen maar aangevuld."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    aid = dc_tool(st.records, st.att, ANCHOR)
    st.att.archive(aid, actor_id=baas.id, actor_type="person")
    assert dc_tool(st.records, st.att, ANCHOR) == aid, "er is een duplicaat bijgekomen"


def test_een_mens_mag_hem_gewoon_opnieuw_maken(tmp_path):
    """DE HARDE EIS. De tombstone geldt voor de seeder, niet voor de gebruiker."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    aid = dc_tool(st.records, st.att, ANCHOR)
    artefacts.log_change(dd, action="delete", artefact=st.att.get(aid), records=st.records)
    st.att.remove(aid)
    velden = {"owner": ANCHOR, "kind": "tool", "title": DC_TITEL, "body": "met de hand", "next": "/"}
    c = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/", form=velden,
                      username="anchor@test.nl", action="artefact_add", data_dir=dd)
    _nxt, msg = cockpit2.ACTIONS["artefact_add"](c)
    assert not msg.startswith("✗"), msg
    titels = [a.title for a in cockpit2._Stores(dd).att.list(ANCHOR, "tool")]
    assert DC_TITEL in titels


def test_en_daarna_is_de_plek_weer_levend(tmp_path):
    """`is_gewist` kijkt naar de LAATSTE actie. Een `add` ná de `delete` heft de tombstone op,
    zonder dat iemand hem hoeft te "wissen"."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ANCHOR, "tool", title=DC_TITEL, body="x")
    artefacts.log_change(dd, action="delete", artefact=a, records=st.records)
    st.att.remove(a.id)
    assert artefacts.is_gewist(dd, ANCHOR, DC_TITEL) is True
    b = st.att.add(ANCHOR, "tool", title=DC_TITEL, body="opnieuw")
    artefacts.log_change(dd, action="add", artefact=b, records=st.records)
    assert artefacts.is_gewist(dd, ANCHOR, DC_TITEL) is False


def test_de_titel_wordt_genormaliseerd(tmp_path):
    """Een tombstone die net anders normaliseert dan de bestaat-check is geen tombstone."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ANCHOR, "tool", title="Decision   Coach", body="x")
    artefacts.log_change(dd, action="delete", artefact=a, records=st.records)
    st.att.remove(a.id)
    for variant in ("decision coach", "  Decision Coach  ", "DECISION   COACH"):
        assert artefacts.is_gewist(dd, ANCHOR, variant) is True, variant


def test_een_andere_eigenaar_is_een_andere_plek(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ANCHOR, "tool", title=DC_TITEL, body="x")
    artefacts.log_change(dd, action="delete", artefact=a, records=st.records)
    st.att.remove(a.id)
    assert artefacts.is_gewist(dd, ROL, DC_TITEL) is False
    assert dc_tool(st.records, st.att, ROL) != "", "de andere rol is meegeblokkeerd"


def test_regels_zonder_titel_blokkeren_niets(tmp_path):
    """FAIL-OPEN, en met opzet. Het veld bestaat pas sinds vandaag; alles wat daarvóór verwijderd
    is draagt hem niet. Liever één keer te veel zaaien dan een tombstone die op een lege
    vergelijking dichtslaat en een tool voorgoed onvindbaar maakt."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    import json
    import os
    with open(os.path.join(dd, "artefact_changelog.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": 1, "action": "delete", "anchor": ANCHOR, "kind": "tool"}) + "\n")
    assert artefacts.is_gewist(dd, ANCHOR, DC_TITEL) is False


def test_een_kapot_changelog_blokkeert_niets(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    import os
    with open(os.path.join(dd, "artefact_changelog.jsonl"), "a", encoding="utf-8") as f:
        f.write("{dit is geen json\n")
    assert artefacts.is_gewist(dd, ANCHOR, DC_TITEL) is False
    assert artefacts.is_gewist("/bestaat/niet", ANCHOR, DC_TITEL) is False


def test_alle_zaai_routines_raadplegen_hem():
    """"Roep die helper aan in elke zaai-routine." Drie plekken hadden dit patroon."""
    from nooch_village import wiki_seed
    from nooch_village.views import copy_prompt, decision_coach
    for fn in (wiki_seed._bestaat, copy_prompt.zorg_voor_tool, decision_coach.zorg_voor_tool):
        assert "is_gewist_bij" in inspect.getsource(fn), fn.__qualname__


def test_de_gebruikers_weg_raadpleegt_hem_juist_niet():
    """De tombstone geldt voor de seeder, niet voor de gebruiker."""
    bron = inspect.getsource(cockpit2._act_artefact_add)
    assert "is_gewist" not in bron


def test_het_is_geen_nieuwe_store():
    """"kleine, backwards-compatible uitbreiding van een bestaand mechanisme, geen nieuwe store"."""
    bron = inspect.getsource(artefacts.is_gewist)
    assert "artefact_changelog.jsonl" in bron
    assert "JsonStore" not in bron and "tombstones" not in bron


# ══ 2. De anchor-lead mag overal verwijderen ═════════════════════════════════
def test_de_anchor_lead_verwijdert_in_een_andere_cirkel(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Weg hiermee", body="x")
    assert _delete(st, dd, a.id, baas.email).startswith("\U0001f5d1")
    assert cockpit2._Stores(dd).att.get(a.id) is None


def test_de_eigen_circle_lead_nog_steeds_ook(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Van de subcirkel", body="x")
    assert _delete(st, dd, a.id, sub.email).startswith("\U0001f5d1")


def test_de_rolvervuller_blijft_uitgesloten(tmp_path):
    """"Dat verandert niet." Archiveren mag hij wél — dat is omkeerbaar."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    vervuller = st.people.add("Rolvervuller", "rol@test.nl")
    st.assign.assign(ROL, "person", vervuller.id)
    a = st.att.add(ROL, "note", title="Van mijn eigen rol", body="x")
    assert artefacts.can_write_artefact("person", vervuller.id, ROL, st.records, st.assign) is True
    assert _delete(st, dd, a.id, vervuller.email).startswith("✗")
    assert cockpit2._Stores(dd).att.get(a.id) is not None


def test_een_willekeurige_mens_al_helemaal_niet(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Niet van jou", body="x")
    assert _delete(st, dd, a.id, buiten.email).startswith("✗")
    assert cockpit2._Stores(dd).att.get(a.id) is not None


def test_verwijderen_en_tombstone_werken_samen(tmp_path):
    """DE LUS ROND. De anchor-lead gooit weg via de echte actie, en de seeder laat het daarna."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    aid = dc_tool(st.records, st.att, ANCHOR)
    assert _delete(st, dd, aid, baas.email).startswith("\U0001f5d1")
    verse = cockpit2._Stores(dd)
    assert dc_tool(verse.records, verse.att, ANCHOR) == ""


# ══ 3. Inline bewerken op de eigen pagina ════════════════════════════════════
def test_een_policy_wordt_op_zijn_eigen_pagina_bewerkt(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="Mits dit.")
    h = render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")
    assert "value='artefact_edit'" in h
    assert "name='domain'" in h, "het domeinveld hoort bij een policy"
    assert "value='artefact_archive'" in h


def test_een_tool_ook_en_met_zijn_url_veld(tmp_path):
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title="Serpstat", url="https://serpstat.com", body="x")
    h = render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")
    assert "value='artefact_edit'" in h and "name='url'" in h


def test_zonder_bewerkrecht_geen_formulier(tmp_path):
    """`can_edit` bepaalt zoals nu al of het formulier verschijnt."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = render_pagina(st, a.id, csrf_token="t", username="buiten@test.nl")
    assert "value='artefact_edit'" not in h and "value='artefact_archive'" not in h


def test_je_blijft_staan_waar_je_typte(tmp_path):
    """Na opslaan terug naar de rol-pagina zou betekenen dat je je eigen wijziging niet ziet."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title="Serpstat", url="https://x", body="y")
    h = render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")
    assert f"value='/pagina?id={a.id}'" in h


def test_de_rol_pagina_bewerkt_niets_meer(tmp_path):
    """"haal ze van de rol-pagina weg." Blijven ze staan, dan zijn het twee bewerkpaden."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    st.att.add(ROL, "policy", title="Testbeleid", body="x")
    st.att.add(ROL, "note", title="Een note", body="x")
    h = render_node(st, ROL, "wiki", csrf_token="t", username="anchor@test.nl")
    assert "value='artefact_edit'" not in h, "het bewerkformulier staat er nog"
    assert "value='artefact_archive'" not in h, "de archiveerknop staat er nog"


def test_maar_wijst_wel_de_weg(tmp_path):
    """Een formulier dat stil verdwijnt laat niemand merken waar het heen is."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = render_node(st, ROL, "wiki", csrf_token="t", username="anchor@test.nl")
    assert "Edit on its page" in h and f"/pagina?id={a.id}" in h


def test_het_blijft_het_eenvoudige_formulier(tmp_path):
    """"Dit hoeft geen rich-text-editor te worden zoals bij notes." De blok-editor, de feiten en
    de `[[link]]`-oplossing horen bij een note; die staan hier niet."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "policy", title="Testbeleid", body="x")
    h = render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")
    assert "data-blok" not in h and "pagina_feit_add" not in h


def test_een_note_verandert_niet(tmp_path):
    """Die had zijn inline editor al sinds 21 september; hier is niets aan gedaan."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Een note", body="tekst")
    h = render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")
    assert "data-blok" in h, "de blok-editor van de note is weg"


def test_er_is_maar_een_bewerkpad_per_artefact(tmp_path):
    """DE REGEL WAAR DIT ALLEMAAL OM DRAAIT, in één toets."""
    dd, st, baas, sub, buiten = _dorp(tmp_path)
    for kind in ("note", "policy", "tool"):
        a = st.att.add(ROL, kind, title=f"Ding {kind}", body="x")
        rol = render_node(st, ROL, "wiki", csrf_token="t", username="anchor@test.nl")
        pag = render_pagina(st, a.id, csrf_token="t", username="anchor@test.nl")
        assert "value='artefact_edit'" not in rol, kind
        assert "artefact_edit" in pag or "data-blok" in pag, kind
