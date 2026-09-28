""""My actions" toont ook de mens-stappen uit de projectplannen (28 september 2026).

HET GAT. Een checklist-item zonder skill is een volgende stap die alleen een mens kan zetten — op
de projectpagina staat er letterlijk "○ no skill · needs a human" bij. Maar het stond alleen dáár:
je moest wéten welk project je moest openen. Dat is precies wat een actielijst oplost.

NIET UIT DE `ActieStore` MAAR UIT DE PROJECTEN (`ProjectLedger.checklists`), en dat verschil is
zichtbaar op het scherm: dit zijn geen briefjes die je zelf opschreef, het is werk dat al in een
plan staat. Het wordt hier dan ook niet gewijzigd — afvinken loopt via `check_toggle`, precies
dezelfde actie als op de projectpagina, met precies dezelfde poort.

DRIE BLOKKEN, DRIE SOORTEN: je eigen briefjes, wat anderen op jouw projecten schreven, en wat er in
de plannen op een mens wacht. Leeg is telkens echt leeg.
"""
from __future__ import annotations

import inspect

from nooch_village import cockpit2
from nooch_village.views import acties as V

ROL = "mother_earth__nooch__compliance"
ANDERE_ROL = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for rol in (ROL, ANDERE_ROL):
        for f in list(st.assign.fillers_of(rol, st.records.get(rol))):
            st.assign.unassign(rol, f.type, f.id)
    ik = st.people.add("Aap Een", "aap@test.nl")
    beer = st.people.add("Beer Twee", "beer@test.nl")
    st.assign.assign(ROL, "person", ik.id)
    st.assign.assign(ANDERE_ROL, "person", beer.id)
    return dd, st, ik, beer


def _plan(st, pid, items):
    """Een checklist met items; `skill=None` = een stap die een mens moet zetten."""
    cl = st.projects.checklist_add(pid, "Plan")
    for tekst, skill in items:
        st.projects.check_add(pid, cl["id"], tekst, skill=skill)
    return cl["id"]


def _teksten(st, wie):
    return [it.get("text") for it, _cl, _p in V._mijn_checklist_items(st, wie.id)]


# ══ 1. Wat er in hoort ═══════════════════════════════════════════════════════
def test_een_mens_stap_op_mijn_eigen_project(tmp_path):
    """DE KERN: een item zonder skill op een lopend project van een rol die ik vervul."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Zolen zonder lijm", "human", status="running")
    _plan(st, pid, [("Selco bellen over de zolen", None)])
    st = cockpit2._Stores(dd)
    assert _teksten(st, ik) == ["Selco bellen over de zolen"]
    h = V.render_acties(st, ik.id, "TOK")
    assert "From project checklists" in h and "Selco bellen over de zolen" in h
    assert "Zolen zonder lijm" in h.split("From project checklists")[1], "het project staat er niet bij"


def test_ook_als_ik_alleen_de_trekker_ben(tmp_path):
    """De tweede kant: het project hoort bij een rol die ik niet vervul, maar ík trek het. Dan is
    het werk aan mij toegewezen, en dan hoort het op mijn lijst."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ANDERE_ROL, "Verzending in Europa", "human", status="running")
    st.projects.edit(pid, person=ik.id)
    _plan(st, pid, [("Tarieven DHL vergelijken", None)])
    st = cockpit2._Stores(dd)
    assert _teksten(st, ik) == ["Tarieven DHL vergelijken"]


# ══ 2. Wat er niet in hoort ══════════════════════════════════════════════════
def test_een_item_met_een_skill_hoort_bij_de_rol_en_niet_bij_jou(tmp_path):
    """"needs a human" is de hele selectie. Een item met een skill wordt door de rol uitgevoerd;
    dat op een mens-lijst zetten is werk teruggeven dat al belegd is."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Project", "human", status="running")
    _plan(st, pid, [("Rapport draaien", "rapport")])
    assert _teksten(cockpit2._Stores(dd), ik) == []


def test_afgevinkt_en_overgeslagen_tellen_niet_mee(tmp_path):
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Project", "human", status="running")
    clid = _plan(st, pid, [("Al gedaan", None), ("Bewust overgeslagen", None)])
    items = {i["text"]: i for i in st.projects.get(pid)["checklists"][0]["items"]}
    st.projects.check_toggle(pid, clid, items["Al gedaan"]["id"])
    st.projects.set_item_skipped(pid, clid, items["Bewust overgeslagen"]["id"])
    assert _teksten(cockpit2._Stores(dd), ik) == []


def test_een_project_dat_niet_op_het_bord_staat_telt_niet_mee(tmp_path):
    """Een stap op een toekomstig of afgerond project is geen volgende stap — dezelfde regel als
    waarom je er geen actie aan kunt koppelen."""
    dd, st, ik, beer = _dorp(tmp_path)
    toekomst = st.projects.create(ROL, "Project future", "human", status="future")
    _plan(st, toekomst, [("Stap future", None)])
    # `done` kan niet als START-status; een project komt daar via de gewone weg terecht.
    af = st.projects.create(ROL, "Project done", "human", status="running")
    _plan(st, af, [("Stap done", None)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [af], "next": ["/"]}, username="guest")
    assert _teksten(cockpit2._Stores(dd), ik) == []


def test_ook_als_trekker_geldt_het_bord(tmp_path):
    """DE REGEL GELDT AAN BEIDE KANTEN. De opdracht noemde `OP_HET_BORD` bij de rol-kant, waar
    `_mijn_projecten` hem al afdwingt; op de trekker-kant stond hij nergens. Een stap op een
    project dat nog niet loopt is geen volgende stap, wie je er ook van bent — en zonder deze
    toets bleef die helft ongemeten (gevonden met een mutatie)."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ANDERE_ROL, "Nog niet begonnen", "human", status="future")
    st.projects.edit(pid, person=ik.id)
    _plan(st, pid, [("Stap voor later", None)])
    assert _teksten(cockpit2._Stores(dd), ik) == []


def test_het_project_van_een_ander_telt_niet_mee(tmp_path):
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ANDERE_ROL, "Project van Beer", "human", status="running")
    _plan(st, pid, [("Niet van mij", None)])
    st = cockpit2._Stores(dd)
    assert _teksten(st, ik) == []
    assert _teksten(st, beer) == ["Niet van mij"], "Beer hoort hem juist wél te zien"


def test_een_prive_project_dat_ik_niet_mag_lezen_telt_niet_mee(tmp_path):
    """De buitengrens blijft de zichtbaarheid, ook op de trekker-kant.

    DE ROL MOET IN EEN ÁNDERE CIRKEL ZITTEN, anders meet deze toets niets: `private` betekent
    "alleen voor deze cirkel", en `ik` zit als vervuller van `ROL` in dezelfde cirkel als
    `ANDERE_ROL` — dan mág hij het gewoon lezen. Gevonden doordat de toets slaagde om de
    verkeerde reden."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create("mother_earth__shareholder", "Achter gesloten deuren", "human",
                             status="running")
    st.projects.edit(pid, person=ik.id, private=True)
    _plan(st, pid, [("Geheim", None)])
    assert _teksten(cockpit2._Stores(dd), ik) == []


def test_leeg_is_echt_leeg(tmp_path):
    dd, st, ik, beer = _dorp(tmp_path)
    assert "From project checklists" not in V.render_acties(st, ik.id, "TOK")


# ══ 3. Afvinken: dezelfde poort als op de projectpagina ══════════════════════
def test_afvinken_mag_wie_de_eigenaar_rol_vervult(tmp_path):
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Mijn project", "human", status="running")
    _plan(st, pid, [("Selco bellen", None)])
    blok = V.render_acties(cockpit2._Stores(dd), ik.id, "TOK").split("From project checklists")[1]
    assert "value='check_toggle'" in blok


def test_de_trekker_zonder_de_rol_krijgt_geen_vakje(tmp_path):
    """DE REGEL DIE JE NIET MAG KORTSLUITEN. `check_toggle` poort op `_role_gate(project.owner)`;
    ben je wel trekker maar vervul je die rol niet, dan weigert de server. Het item staat er dus
    wel (het is jouw werk) maar zonder vakje — een knop die daarna 'No access' geeft is een
    belofte die je niet nakomt."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ANDERE_ROL, "Trek-project", "human", status="running")
    st.projects.edit(pid, person=ik.id)
    _plan(st, pid, [("Ik trek dit", None)])
    blok = V.render_acties(cockpit2._Stores(dd), ik.id, "TOK").split("From project checklists")[1]
    assert "Ik trek dit" in blok
    assert "value='check_toggle'" not in blok
    assert "<span class='ck-box'></span>" in blok, "het bolletje hoort te blijven staan"


def test_de_server_weigert_hem_inderdaad(tmp_path):
    """DE KETEN TOT HET EIND: als dit tóch mocht, was het vakje hierboven onterecht weggelaten."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ANDERE_ROL, "Trek-project", "human", status="running")
    st.projects.edit(pid, person=ik.id)
    clid = _plan(st, pid, [("Ik trek dit", None)])
    item = st.projects.get(pid)["checklists"][0]["items"][0]["id"]
    st = cockpit2._Stores(dd)
    velden = {"csrf": "T", "pid": pid, "clid": clid, "item": item, "next": "/acties"}
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/acties", form=velden,
                        username="aap@test.nl", action="check_toggle", data_dir=dd)
    _pad, melding = cockpit2.ACTIONS["check_toggle"](ctx)
    assert melding.startswith("No access")


def test_het_vakje_werkt_ook_echt(tmp_path):
    """En de andere kant: wie het vakje wél krijgt, vinkt er ook echt mee af."""
    dd, st, ik, beer = _dorp(tmp_path)
    pid = st.projects.create(ROL, "Mijn project", "human", status="running")
    clid = _plan(st, pid, [("Selco bellen", None)])
    item = st.projects.get(pid)["checklists"][0]["items"][0]["id"]
    st = cockpit2._Stores(dd)
    velden = {"csrf": "T", "pid": pid, "clid": clid, "item": item, "next": "/acties"}
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/acties", form=velden,
                        username="aap@test.nl", action="check_toggle", data_dir=dd)
    cockpit2.ACTIONS["check_toggle"](ctx)
    verse = cockpit2._Stores(dd)
    assert verse.projects.get(pid)["checklists"][0]["items"][0]["done"] is True
    assert _teksten(verse, ik) == [], "afgevinkt hoort meteen uit het blok te zijn"


def test_de_poort_is_een_gedeelde_regel_en_geen_kopie():
    """`mag_rolwerk` is de regel; `_role_gate` is dezelfde regel met een e-mailadres ervoor. Het
    scherm en de server stellen dus letterlijk dezelfde vraag."""
    assert "mag_rolwerk(" in inspect.getsource(cockpit2._role_gate)
    bron = inspect.getsource(V._checklist_regel)
    assert "mag_rolwerk(" in bron
    for eigen in ("is_role_filler", "is_circle_lead", "resolve_circle_id"):
        assert eigen not in bron, f"{eigen} wordt hier opnieuw uitgeschreven"


# ══ 4. Eén bron voor "wat staat er op het bord" ══════════════════════════════
def test_de_bordstatussen_komen_uit_projects():
    """`reference, don't copy`: hier stond `("running", "blocked")` naast precies dezelfde waarde
    in `projects.OP_HET_BORD`."""
    from nooch_village.projects import OP_HET_BORD
    assert V._LOPEND is OP_HET_BORD


def test_het_blok_gebruikt_dezelfde_projectdefinitie():
    assert "_mijn_projecten(" in inspect.getsource(V._mijn_checklist_items)
