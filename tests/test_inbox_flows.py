"""De twee inbox-flows: Actie en Project — één mechaniek, twee ingangen.

WAAROM DIT VERANDERDE. De inbox had een intentie-boom naar GlassFrog's "What do you need?": drie
abstracte bakken, elk met diagnostische vragen. Gemeten over de hele historie op prod:

    560 items · 42 met een uitkomst (7,5%) · daarvan 26x 'niks nodig'
    project 3x · ping 6x · action 0x

Nul keer een actie. Een menu dat je eerst laat classificeren wát voor behoefte je hebt vóór je iets
concreets mag doen, kost een denkstap die niemand zet.

DE KERNREGEL, en die is belangrijker dan de flows: één mechaniek, twee ingangen. De inbox krijgt
GEEN eigen actie- of projectvorm. Een actie loopt via `route_werk` (dezelfde als het werkoverleg en
de wizard), Project opent dezelfde wizard, een gekoppelde actie wordt een item in de project-
checklist die het project al heeft. Dat is de consolidatie van het projectbord, nu voor de inbox.
"""
from __future__ import annotations

from nooch_village import cockpit2

_OWNER = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _mens(st):
    p = st.people.all()[0]
    if not getattr(p, "email", ""):
        st.people.update(p.id, email="stefan@nooch.earth")
        p = st.people.get(p.id)
    return p


def _spanning(st, person):
    src = st.projects.create(_OWNER, "Bron-project", "human")
    e = st.projects.add_feed_entry(src, "de leverancier reageert niet", kind="comment",
                                   author_type="human")
    return src, st.notif.add("person", person.id, src, e["id"], by="dialoog",
                             snippet="de leverancier reageert niet")


def _pane(tmp_path):
    st = cockpit2._Stores(_dd(tmp_path))
    person = _mens(st)
    _src, n = _spanning(st, person)
    from nooch_village.views.inbox import _wizard_pane
    return st, n, _wizard_pane(st, n, "t", "<option value='r'>R</option>", "")


# ── Labels dragen de pedagogie ──────────────────────────────────────────────

def test_elke_flow_heeft_één_regel_uitleg_naast_het_label(tmp_path):
    """Zo leert een nieuweling roldenken al doende — aan het verschil tussen 'één handeling' en
    'werk dat een rol draagt' — in plaats van uit abstracte bakken. Uitleg die je moet zoeken is
    geen uitleg, dus hij staat naast het label en niet in een tooltip."""
    _st, _n, html = _pane(tmp_path)
    assert "Action" in html and "comes back in the inbox" in html
    assert "Project" in html and "for a role you fill yourself" in html


def test_de_abstracte_bakken_zijn_weg(tmp_path):
    _st, _n, html = _pane(tmp_path)
    for oud in ("What do you need?", "Share, get or record info", "Do something yourself",
                "Have someone else do something", "Ping someone"):
        assert oud not in html, oud


def test_de_governance_route_staat_er_ongewijzigd_bij(tmp_path):
    """Bewust NIET heringericht: flow 3 ontwerpen we apart, en tot die tijd mag er niets breken."""
    _st, _n, html = _pane(tmp_path)
    assert "governance meeting" in html.lower()
    assert "roloverleg" in html


# ── Flow 1: één mechaniek, geen tweede routing ──────────────────────────────

def test_de_inbox_heeft_geen_eigen_routing():
    """DE KERNREGEL. `route_werk` kent de regel dat een AI-vervulde rol de NotifStore nooit leest;
    een tweede kopie hier zou na één wijziging uit de pas lopen en werk stil verkeerd laten landen."""
    import inspect
    bron = inspect.getsource(cockpit2._act_notif_outcome)
    tak = bron[bron.index('if otype == "action"'):bron.index('elif otype == "roloverleg"')]
    assert "route_werk(" in tak
    assert "st.notif.add(" not in tak, "de inbox routeert zelf — dat is de tweede mechaniek"


def test_actie_zonder_doel_komt_bij_jezelf_terug(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = _mens(st)
    _src, n = _spanning(st, person)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                       "content": ["de leverancier bellen"], "next": ["/x"]},
                      username=person.email)
    eigen = [x for x in cockpit2._Stores(dd).notif.for_targets([("person", person.id)])
             if x.get("snippet") == "de leverancier bellen"]
    assert len(eigen) == 1


def test_actie_met_at_naar_een_mens_rol_landt_in_diens_inbox(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = _mens(st)
    _src, n = _spanning(st, person)
    st.assign.assign(_OWNER, "person", person.id)          # mens op de rol → leest een inbox
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                       "doel": [f"role:{_OWNER}"], "content": ["kijk jij hiernaar?"],
                       "next": ["/x"]}, username=person.email)
    bij_rol = [x for x in cockpit2._Stores(dd).notif.for_targets([("role", _OWNER)])
               if x.get("snippet") == "kijk jij hiernaar?"]
    assert len(bij_rol) == 1


def test_een_gekozen_rol_wint_van_jezelf(tmp_path):
    """OP EEN TEST GEVONDEN, niet op het scherm. `route_werk` laat een persoon van een rol winnen,
    dus een rol kiezen én stilzwijgend jezelf meesturen liet het werk bij JOU landen terwijl het
    scherm de ander noemde — precies de stille misrouting die #364 wegnam."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = _mens(st)
    _src, n = _spanning(st, person)
    st.assign.assign(_OWNER, "person", person.id)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                       "doel": [f"role:{_OWNER}"], "content": ["voor de rol"], "next": ["/x"]},
                      username=person.email)
    st2 = cockpit2._Stores(dd)
    naar_rol = [x for x in st2.notif.all()
                if x.get("snippet") == "voor de rol" and x.get("target_type") == "role"]
    naar_mij = [x for x in st2.notif.all()
                if x.get("snippet") == "voor de rol" and x.get("target_type") == "person"]
    assert len(naar_rol) == 1 and naar_mij == []


def test_een_stilstaande_rol_krijgt_geen_werk(tmp_path):
    """Fail-closed, dezelfde regel als in de wizard en het werkoverleg: werk beloven aan een bureau
    waar niemand zit is precies wat de afslanking wilde voorkomen."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = _mens(st)
    _src, n = _spanning(st, person)
    rec = st.records.get(_OWNER)
    rec.slaapt = True
    st.records.put(rec)
    _nxt, msg = cockpit2.dispatch(dd, "notif_outcome",
                                  {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                                   "doel": [f"role:{_OWNER}"], "content": ["x"], "next": ["/x"]},
                                  username=person.email)
    assert "✗" in msg
    assert not [x for x in cockpit2._Stores(dd).notif.for_targets([("role", _OWNER)])
                if x.get("snippet") == "x"]


def test_de_at_lijst_bevat_alleen_wakkere_rollen_en_personen(tmp_path):
    from nooch_village.views.inbox import _at_doelen
    st = cockpit2._Stores(_dd(tmp_path))
    _mens(st)
    rec = st.records.get(_OWNER)
    rec.slaapt = True
    st.records.put(rec)
    st = cockpit2._Stores(st.dd)
    ids = {d["id"] for d in _at_doelen(st)}
    assert _OWNER not in ids
    assert {d["kind"] for d in _at_doelen(st)} <= {"role", "person"}


def test_actie_gekoppeld_aan_een_project_wordt_een_stap_in_de_bestaande_checklist(tmp_path):
    """Geen tweede checklist-store: de project-checklist is die van het project zelf."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = _mens(st)
    src, n = _spanning(st, person)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"], "pid_link": [src],
                       "content": ["de bron nakijken"], "next": ["/x"]}, username=person.email)
    p = cockpit2._Stores(dd).projects.get(src)
    stappen = [i.get("text") for cl in (p.get("checklists") or []) for i in (cl.get("items") or [])]
    assert "de bron nakijken" in stappen


# ── Flow 2: dezelfde wizard, gescoped op je eigen rollen ────────────────────

def test_project_is_een_deur_naar_dezelfde_wizard(tmp_path):
    _st, _n, html = _pane(tmp_path)
    assert "/project/nieuw?" in html and "mine=1" in html
    assert "ruw=" in html                                  # de spanningstekst reist mee als zaad


def test_er_is_geen_project_voor_een_ander_tak(tmp_path):
    """Een rol is baas over zijn eigen bord. Werk daar neerleggen is een verzoek, en een verzoek is
    flow 1 (een actie met `@`)."""
    from nooch_village.views.wizard import _role_options
    st = cockpit2._Stores(_dd(tmp_path))
    vol = _role_options(st)
    gescoped = _role_options(st, eigen=[_OWNER])
    assert _OWNER in vol and _OWNER in gescoped
    assert vol.count("<option") > gescoped.count("<option"), "mine=1 scopet niet"
    assert "mother_earth__nooch__scientist" not in gescoped


def test_zonder_scope_blijft_de_volle_lijst_staan(tmp_path):
    """Vanaf het projectbord kies je bewust een kolom; daar mag de lijst niet krimpen."""
    from nooch_village.views.wizard import _role_options
    st = cockpit2._Stores(_dd(tmp_path))
    assert _role_options(st) == _role_options(st, eigen=None)
