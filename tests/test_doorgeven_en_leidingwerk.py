"""Drie dingen die het echte bord van 7 september opleverde.

1. **Doorgeven is geen project maken.** De hand-off-knop vroeg om een 'done when…' en zette een
   queued project op het bord van de ontvanger. Een mens die één checklist-item doorgeeft wil geen
   project, hij wil dat iemand het ziet.
2. **De modal is een modal.** Een projectlink in de verwerk-pagina opende de hele site in de
   iframe-strook van 460 pixels, omdat `target=_top` ontbrak.
3. **De matcher zag de rugzak niet.** Het item "check savon de potasse suppliers in europe" kreeg
   "no skill · needs a human" terwijl `web_zoek` bestaat en in rugzak `buiten` zit. DERDE keer dat
   dezelfde verwarring toesloeg; daarom staat het antwoord nu in `skillset.py`.
"""
from __future__ import annotations

import pytest

from nooch_village import skillset
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.projects import ProjectLedger
from nooch_village.project_items import resolve_item


def _rol(skills=("escaleer",)):
    return Record(id="the_source", type=RecordType.ROLE, parent="noochville",
                  definition=RoleDefinition(purpose="p", skills=list(skills)), source="seed")


def _ctx(**kw):
    return type("Ctx", (), {"settings": {}, "links": None, "rugzakken": {}, **kw})()


# ── 1. Doorgeven ≠ handoff ───────────────────────────────────────────────────

@pytest.fixture()
def project(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("the_source", "doel", "human", status="queued")
    cl = led.checklist_add(pid, title="Uitvoerplan")
    led.check_add(pid, cl["id"], "check savon de potasse suppliers in europe")
    return led, pid, cl["id"], led.get(pid)["checklists"][0]["items"][0]["id"]


def test_doorgeven_maakt_geen_project(project):
    """DE KERNTEST. `handoff` maakt een project op het bord van de ontvanger; dat is goed als een ROL
    werk belegt, maar niet als een mens één item doorgeeft."""
    led, pid, clid, iid = project
    voor = len(led.all())
    ok, msg = resolve_item(led, pid, clid, iid, "doorgeven", by="stefan", naar_label="Nina")
    assert ok is True
    assert len(led.all()) == voor                          # geen nieuw project
    assert "Nina" in msg


def test_doorgeven_sluit_het_item_en_legt_vast_waar_het_heen_ging(project):
    """Zonder afsluiten blijft het item het project blokkeren; zonder de vastlegging weet niemand
    over een week nog waaróm het hier wegging."""
    led, pid, clid, iid = project
    resolve_item(led, pid, clid, iid, "doorgeven", by="stefan", naar_label="Nina")
    it = led.get(pid)["checklists"][0]["items"][0]
    assert it.get("skipped") is True
    assert "Nina" in str(it.get("skip_reason") or "")
    regels = " ".join(e.get("text", "") for e in led.get(pid).get("log", []))
    assert "Doorgegeven aan Nina" in regels


def test_handoff_blijft_bestaan_voor_de_rol_naar_rol_route(project):
    """De escalatie-router en de `projectverzoek`-skill beleggen werk BIJ EEN ROL, en daar hoort wél
    een project bij. Die route mag niet meeveranderen met de mens-knop."""
    led, pid, clid, iid = project
    from nooch_village import project_items
    assert "handoff" in project_items._ACTIES and "doorgeven" in project_items._ACTIES


def test_de_knop_routeert_en_maakt_niets(monkeypatch):
    """De routering staat in `route_werk`, de gedeelde regel van het werkoverleg en de inbox. Een
    tweede kopie hier zou na één wijziging werk stil op de verkeerde plek laten landen."""
    import inspect
    from nooch_village import cockpit2
    src = inspect.getsource(cockpit2._act_check_handoff)
    assert "route_werk(" in src
    assert "handoff" not in src.replace("_act_check_handoff", "").replace("check_handoff", "")
    assert '"doorgeven"' in src


def test_een_onbekend_doel_is_een_fout_en_geen_gok():
    """FAIL-CLOSED. Werk bij een geraden ontvanger neerleggen is stiller en erger dan een melding."""
    import inspect
    from nooch_village import cockpit2
    src = inspect.getsource(cockpit2._act_check_handoff)
    assert "is not a role or person I know" in src


def test_het_formulier_is_een_at_veld_en_geen_projectformulier():
    """Twee dingen mis met het oude: het vroeg om een projectdoel, en drie velden naast de itemtekst
    persten die tekst samen tot één woord per regel."""
    import inspect
    from nooch_village.views import checklists as C
    src = inspect.getsource(C._cl_resolve_row)
    assert "list='ck-doelen'" in src
    # Op de MARKUP toetsen en niet op de tekst: 'done when' staat nog in het commentaar dat uitlegt
    # waarom het weg is, en dat commentaar hoort te blijven staan.
    assert "placeholder='done when" not in src             # geen projectdoel meer
    assert "select name='naar_rol'" not in src


# ── 2. De modal is een modal ─────────────────────────────────────────────────

def test_projectlinks_in_de_verwerk_pagina_openen_bovenaan():
    """De verwerk-pagina draait als iframe in de inbox-lade. Zonder `target=_top` opent de hele site
    zich in een strook van 460 pixels."""
    import inspect
    from nooch_village.views import inbox as V
    src = inspect.getsource(V)
    for regel in src.splitlines():
        if "href='/project?pid=" in regel:
            assert "target='_top'" in regel, f"projectlink zonder _top: {regel.strip()[:90]}"


# ── 3. Eén antwoord op 'welke skills mag deze rol voeren' ────────────────────

def test_zonder_context_is_het_gewoon_het_dna():
    """Elke oudere aanroeper gedraagt zich als voorheen; niets verandert stil van gedrag."""
    assert skillset.van_record(_rol(["escaleer"])) == {"escaleer"}
    assert skillset.effectief(["a", "b"]) == {"a", "b"}


def test_de_rugzak_telt_mee():
    """DE KERNTEST VAN DIT BLOK. `web_zoek` zit in geen enkel rol-DNA maar wel in rugzak `buiten`,
    en is dus voor élke rol beschikbaar. Zag de matcher dat niet, dan kreeg een mens-getypt item
    'no skill · needs a human' terwijl het gereedschap er lag."""
    ctx = _ctx(rugzakken={"buiten": {"skills": ["web_zoek", "haal_pagina"]}})
    uit = skillset.van_record(_rol(["escaleer"]), context=ctx)
    assert uit == {"escaleer", "web_zoek", "haal_pagina"}


def test_het_dna_is_de_vloer():
    """Geen laag hierboven neemt ooit iets af."""
    ctx = _ctx(rugzakken={"b": {"skills": ["web_zoek"]}})
    assert "escaleer" in skillset.van_record(_rol(["escaleer"]), context=ctx)


def test_koppelingen_alleen_als_de_vlag_aanstaat():
    ctx_uit = _ctx(settings={"skill_links_active": "0"})
    ctx_aan = _ctx(settings={"skill_links_active": "1"})
    # Zonder links-store levert de aan-stand hetzelfde als de uit-stand; het gaat hier om de vlag,
    # niet om de inhoud van de store (die heeft zijn eigen tests).
    assert skillset.van_record(_rol(), context=ctx_uit) == skillset.van_record(_rol(), context=ctx_aan)


def test_een_stukke_rugzak_breekt_de_aanroeper_niet():
    """Fail-soft in elke tak: een matcher die crasht op een scheve config is erger dan een matcher
    die een rugzak mist."""
    class _Stuk(dict):
        def __bool__(self):
            return True
    ctx = _ctx(rugzakken=_Stuk({"kapot": "geen dict"}))
    assert "escaleer" in skillset.van_record(_rol(["escaleer"]), context=ctx)


def test_de_inwoner_gebruikt_dezelfde_bron():
    """Het antwoord woonde als methode op Inhabitant, en het cockpit heeft geen Inwoner — precies
    daarom werd het drie keer overgeschreven. Nu is de Inwoner één van de aanroepers."""
    import inspect
    from nooch_village.inhabitant import Inhabitant
    assert "skillset.effectief" in inspect.getsource(Inhabitant.effective_skills)


def test_de_matcher_krijgt_de_context_mee():
    import inspect
    from nooch_village import skill_match, cockpit2
    assert "skillset.van_record" in inspect.getsource(skill_match.plan_offers)
    assert "_context_of(st.dd)" in inspect.getsource(cockpit2)


def test_de_spawn_beslissing_blijft_op_het_dna():
    """BEWUSTE UITZONDERING. Zou `Reconciler` de rugzakken meetellen, dan is elke rol per definitie
    'bemand' en komt elke slapende rol weer tot leven — het tegenovergestelde van de afslanking.
    Capaciteit is iets anders dan bestaan."""
    import inspect
    from nooch_village import governance
    src = inspect.getsource(governance)
    tak = src.split("geen CLASS_MAP entry")[0][-1200:]
    assert "rugzak" not in tak.lower(), "de spawn-beslissing telt nu rugzakken mee"
