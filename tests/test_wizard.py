"""Project-wizard (founder 20 jul): de LLM maakt een ruw idee scherp tot een toetsbare uitkomst
en stelt een checklist voor die per item tegen de skills van de rol wordt getoetst."""
from __future__ import annotations

import json

from nooch_village import cockpit2
from nooch_village.wizard import plan_items, sharpen_outcome


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_sharpen_fail_soft():
    # LLM levert niets → ruw idee terug (mens kan alsnog verder)
    assert sharpen_outcome("kijk naar zolen", reason_fn=lambda *a, **k: None) == "kijk naar zolen"
    assert sharpen_outcome("", reason_fn=lambda *a, **k: "x") == ""
    # LLM levert een uitkomst → schoongemaakt terug
    out = sharpen_outcome("zolen", reason_fn=lambda *a, **k: '  "Er ligt een overzicht van 3 zolen." ')
    assert out == "Er ligt een overzicht van 3 zolen."


CATALOG = [
    {"name": "epo_patents", "description": "patenten", "input": "query: str"},
    {"name": "openalex_evidence", "description": "studies", "input": "term: str"},
]
REQUIRED = {"epo_patents": ("query",), "openalex_evidence": ("term",)}


def _fake_plan(*a, **k):
    return json.dumps({"items": [
        {"tekst": "Zoek patenten op afbreekbare zolen", "skill": "epo_patents",
         "payload": {"query": "biodegradable outsole"}},
        {"tekst": "Haal studies op", "skill": "openalex_evidence", "payload": {}},   # payload mist
        {"tekst": "Bel drie leveranciers", "skill": None, "payload": {}},            # geen skill
        {"tekst": "Gebruik magie", "skill": "niet_bestaand", "payload": {}},         # skill niet van rol
    ]})


def test_plan_items_toetst_skills_en_payload():
    items = plan_items("Overzicht afbreekbare zolen", CATALOG,
                       reason_fn=_fake_plan, required_of=lambda s: REQUIRED.get(s, ()))
    assert len(items) == 4
    assert items[0]["skill"] == "epo_patents" and items[0]["ok"] is True
    assert items[1]["skill"] == "openalex_evidence" and items[1]["ok"] is False   # payload onvolledig
    assert "payload onvolledig" in items[1]["reden"]
    assert items[2]["skill"] is None and items[2]["ok"] is False                   # mens-taak
    assert items[3]["skill"] is None                                                # onbekende skill → null


def test_plan_items_fail_soft():
    assert plan_items("doel", CATALOG, reason_fn=lambda *a, **k: None) == []
    assert plan_items("", CATALOG, reason_fn=_fake_plan) == []


# ── één ingang: beide knoppen openen de wizard, voorgevuld ──────────────────

def test_de_wizard_neemt_voorvulling_mee(tmp_path):
    """Wat de mens al intypte hoort hij niet over te tikken — dat is precies waarom die kale
    formulieren bestonden. Sinds B1 zijn er geen stappen meer: de voorvulling landt in de velden
    van hetzelfde form, en opslaan kan meteen."""
    from nooch_village.views.wizard import render_wizard
    st = _st(tmp_path)
    rid = "mother_earth__nooch__website_developer"
    h = render_wizard(st, "t", role=rid, ruw="doos scheurt")
    assert 'ruw:"doos scheurt"' in h
    assert "wz-uit" not in h and "Done when" not in h    # geen apart done-when-veld meer (12 sep)
    assert f'__ROLE__' not in h and rid in h             # de rol is ingevuld, niet de placeholder
    assert "step:" not in h                              # geen stappen meer


def test_de_snelle_route_is_twee_tikken(tmp_path):
    """Idee typen en opslaan. De uitkomst is optioneel: staat hij leeg, dan is je idee de
    uitkomst — anders houdt een leeg veld je tegen bij iets kernachtigs."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert 'id="wz-ruw"' in h and 'id="wz-save"' in h
    assert "Put on the board" in h
    # de opslaan-knop staat BOVEN de opgevouwen verrijking, niet erachter
    assert h.index('id="wz-save"') < h.index("Impact and effort")
    assert h.index('id="wz-save"') < h.index("Checklist")
    assert "S.uitkomst" not in h                         # de titel is de uitkomst, één veld


def test_alleen_wakkere_rollen_plus_individuele_actie(tmp_path):
    from nooch_village.views.wizard import _role_options
    st = _st(tmp_path)
    rid = "mother_earth__nooch__website_developer"
    rec = st.records.get(rid); rec.slaapt = True; st.records.put(rec)
    opts = _role_options(st)
    assert f"value='{rid}'" not in opts
    assert "Individual action" in opts


def test_de_bordknop_en_de_inbox_knop_openen_dezelfde_wizard(tmp_path):
    """Drie manieren om een project te maken werd er één. Beide knoppen bouwen dezelfde URL."""
    from nooch_village.views.projects import _quickadd
    from nooch_village.views.inbox import _outcome_form
    bord = _quickadd("mother_earth__nooch__website_developer", "actief", "t", "/node?id=x")
    assert "/project/nieuw?" in bord and "proj_add" not in bord
    # Het bord heeft geen eigen velden meer: het is een DEUR met de context die de kolom al weet.
    # Velden die eruitzien als een creatie-vorm maar doorsturen beloven iets anders dan ze doen.
    assert "role=" in bord and "<textarea" not in bord
    inbox = _outcome_form("project", "nid", "t", "de spanningstekst", "<option>r</option>", "",
                          "/inbox", "u1")
    assert "/project/nieuw?" in inbox and "notif_outcome" not in inbox
    assert "ruw=de+spanningstekst" in inbox              # de spanningstekst als zaad
    # GEEN ROL MEE, en dat is de beslissing van 29 aug 2026: uit de inbox maak je een project voor
    # een rol die je ZELF vervult (`mine=1` scopet de wizard-kiezer). Werk bij een andere rol
    # neerleggen is een verzoek, en een verzoek is een actie met `@` — een rol is baas over zijn
    # eigen bord. Daarom ook geen tekstveld hier: een ingang is een deur, geen formulier.
    assert "mine=1" in inbox and "role=" not in inbox
    assert "<textarea" not in inbox and "<select" not in inbox
    # de governance-route staat er ongewijzigd naast en neemt gewoon op
    gov = _outcome_form("roloverleg", "nid", "t", "x", "<option>r</option>", "", "/inbox", "u2")
    assert "notif_outcome" in gov and "/project/nieuw" not in gov


def test_de_ai_is_een_bonus_geen_poort(tmp_path):
    """Sterker dan een overslaan-knop: de AI-stappen zitten OPGEVOUWEN en laden pas als je ze
    opent. Wie ze nooit opent, merkt niets van een traag of ontbrekend model."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "<details" in h and "(optional)" in h
    assert "AbortController" in h and "AI_TIMEOUT_MS" in h        # timeout op élke AI-call
    # Elke AI-plek biedt bij mislukken een WEG VOORUIT, niet alleen een foutmelding. Op de
    # formulering zelf toetsen we niet — die mag veranderen; de uitweg niet.
    for uitweg in ("type it yourself, saving still works",         # het aanscherpen
                   "your own steps work fine",                     # de checklist
                   "set it yourself, or leave it empty"):          # de impact-gok
        assert uitweg in h, uitweg


# ── B2: impact en moeite ────────────────────────────────────────────────────

def test_de_gok_valt_per_as_dicht_bij_onzin():
    """Een verzonnen as is erger dan een lege: hij stuurt later de prioritering. Wat niet in de
    toegestane waarden zit valt weg, niet 'onbekend'."""
    from nooch_village.wizard import guess_impact
    goed = guess_impact("doos verstevigen", reason_fn=lambda *a, **k:
                        '{"tijd":"1d","missie":"neutraal","business":"medium","waarom":"klein"}')
    assert goed == {"tijd": "1d", "missie": "neutraal", "business": "medium", "waarom": "klein"}
    # onzin per as valt weg, de bruikbare as blijft
    half = guess_impact("x", reason_fn=lambda *a, **k:
                        '{"tijd":"3 weken","missie":"neutraal","business":"heel hoog"}')
    assert half == {"missie": "neutraal"}
    # geen model, kapotte json of leeg idee → niets, en dus lege chips
    for kapot in (None, "geen json", "{}"):
        assert guess_impact("x", reason_fn=lambda *a, **k: kapot) == {}
    assert guess_impact("", reason_fn=lambda *a, **k: '{"tijd":"1d"}') == {}


def test_de_assen_komen_uit_de_projectstore():
    """Eén bron. Een tweede lijst in de wizard zou na één wijziging uit de pas lopen, en dan raadt
    hij iets wat het project weigert."""
    from nooch_village import wizard
    from nooch_village.projects import _BUSINESS_IMPACT, _EFFORT, _MISSIE_IMPACT
    assert wizard._ASSEN == {"tijd": _EFFORT, "missie": _MISSIE_IMPACT,
                             "business": _BUSINESS_IMPACT}


def test_impact_laadt_pas_als_je_de_sectie_opent(tmp_path):
    """Zelfde discipline als de checklist: de AI draait niet tenzij gevraagd."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert 'ontoggle="if(this.open)schat()"' in h
    assert "/wizard/impact" in h and "AI_TIMEOUT_MS" in h
    assert "set it yourself, or leave it empty" in h          # fail-open, met een uitweg
    assert "a gok mag geen keuze overschrijven" not in h      # (commentaar hoort niet in de body)
    assert "if(!S[k]&&r&&r[k])S[k]=r[k]" in h                 # een gok overschrijft geen keuze


def test_het_label_is_afgeleid_en_wordt_niet_opgeslagen(tmp_path):
    """'Quick win' is een gevolg van moeite en business-impact. Zou het een veld zijn, dan klopt
    het niet meer zodra iemand een chip verzet."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "function label()" in h and "Quick win" in h
    assert "label:" not in h                                  # geen state-veld
    assert "items:JSON.stringify" in h and "label" not in h.split("post('/wizard/create'")[1][:200]


# ── B3: de checklist is meteen bruikbaar ────────────────────────────────────

def test_de_checklist_opent_als_invoerveld_niet_als_wachtscherm(tmp_path):
    """Hier stond een spinner van maximaal twaalf seconden vóór je iets kon. Dat is de AI vóór
    de mens zetten bij een lijstje afvinken. Openen is typen. En sinds 12 sep (Stefan: "met een
    knop de AI-suggestie in werking zetten") draait openen ook geen model meer: de suggesties komen
    alleen op de knop."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "type a step and press Enter" in h
    assert "makes a checklist and checks it against your skills" not in h   # het wachtscherm
    body = h.split("async function checklist()")[1].split("async function suggesties()")[0]
    assert "draw();" in body and "suggesties" not in body                  # openen = alleen tekenen
    assert 'id="wz-sugbtn" onclick="suggesties()"' in h                    # de knop
    assert "await suggesties" not in h


def test_suggesties_komen_erbij_en_blokkeren_niet(tmp_path):
    """Ze halen je in, of ze halen je niet in. Beide zijn goed."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "tap to add" in h and "function neem(" in h
    assert "you can keep typing" in h                    # tijdens het denken blijft de lijst open
    assert "your own steps work fine" in h               # fail-open, zonder alarm
    assert "AI_TIMEOUT_MS" in h


def test_een_suggestie_die_je_al_hebt_wordt_niet_nog_eens_aangeboden(tmp_path):
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "heb.has(x.tekst.trim().toLowerCase())" in h


def test_de_stappen_zijn_bewerkbaar_en_gaan_naar_de_project_checklist(tmp_path):
    """Geen tweede checklist-store: `/wizard/create` schrijft in de checklist die het project
    zelf al heeft. De conventie-ratchet bewaakt dat er geen tweede bijkomt."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert 'oninput="S.checklist[' in h                   # elke stap is een invoerveld
    assert "items:JSON.stringify(S.checklist)" in h       # en reist mee naar create
    from nooch_village import cockpit2 as c2
    bron = __import__("inspect").getsource(c2.make_handler)
    assert "checklist_add(pid" in bron and "check_add(pid" in bron


# ── B4: wie kan dit oppakken, en de lus terug ───────────────────────────────

def test_toewijzen_gebruikt_dezelfde_routing_als_het_werkoverleg(tmp_path):
    """Geen tweede routing. Een mens-vervulde rol krijgt het in zijn inbox; een AI-vervulde rol
    krijgt een project, want die leest de NotifStore nooit."""
    from nooch_village import cockpit2 as c2
    st = _st(tmp_path)
    rid = "mother_earth__nooch__website_developer"
    p = st.people.all()[0]

    st.assign.assign(rid, "person", p.id)                     # mens vervult de rol
    soort, ref = c2.route_werk(st, tekst="site nakijken", rol=rid, opdrachtgever=p.id)
    assert soort == "inbox" and "inbox" in ref
    n = next(x for x in st.notif.all() if "site nakijken" in (x.get("snippet") or ""))
    assert n["opdrachtgever"] == p.id                          # de lus kan sluiten

    # Alleen de MENSEN eraf, de AI-vervuller blijft: dat is de projectroute-casus. Álles weghalen
    # maakt de rol volledig onbemand, en dat is sinds de vervuller-pass een ander geval — dan gaat
    # het naar de Circle Lead in plaats van naar een bord waar niemand kijkt.
    for f in list(st.assign.fillers_of(rid)):
        if f.type == "person":
            st.assign.unassign(rid, f.type, f.id)
    if not [f for f in st.assign.fillers_of(rid) if f.type == "persona"]:
        st.assign.assign(rid, "persona", "een-ai")
    soort2, _ref2 = c2.route_werk(st, tekst="ander werk", rol=rid, opdrachtgever=p.id)
    assert soort2 == "project"
    pr = next(x for x in st.projects.all() if "ander werk" in str(x.get("scope")))
    assert pr["opdrachtgever"] == p.id


def test_de_lus_sluit_bij_een_afgerond_project(tmp_path):
    """Zonder deze melding is werk dat een rol voor je oppakt een eenrichtingsweg."""
    from nooch_village import cockpit2 as c2
    st = _st(tmp_path)
    p = st.people.all()[0]
    pid = st.projects.create("mother_earth__nooch__website_developer", "Iets uitzoeken", "human",
                             opdrachtgever=p.id)
    voor = len(st.notif.all())
    c2.meld_opdrachtgever(st, opdrachtgever=p.id, wat="Iets uitzoeken", bron_project=pid)
    ns = [x for x in st.notif.all() if (x.get("snippet") or "").startswith("Klaar:")]
    assert len(st.notif.all()) == voor + 1 and ns
    assert ns[-1]["target_type"] == "person" and ns[-1]["target_id"] == p.id
    assert ns[-1]["afronding"] is True                          # meldt zichzelf niet terug


def test_zonder_opdrachtgever_geen_melding(tmp_path):
    """Fail-closed: liever geen bericht dan een bericht aan niemand."""
    from nooch_village import cockpit2 as c2
    st = _st(tmp_path)
    voor = len(st.notif.all())
    assert c2.meld_opdrachtgever(st, opdrachtgever="", wat="x") == ""
    assert c2.meld_opdrachtgever(st, opdrachtgever="bestaat-niet", wat="x") == ""
    assert len(st.notif.all()) == voor


# ── B5: individuele actie hangt onder een cirkel, en die kies je niet stilzwijgend ──

def test_de_wizard_herkent_een_ii_eigenaar_als_voorselectie(tmp_path):
    """Klik je vanaf een Individueel-Initiatief-baan op '+ add project', dan wist de wizard de
    context die het bord al had: `ii:<cirkel>` staat niet in de records, dus viel hij terug op
    'Pick a role…'."""
    import re
    from nooch_village.views.wizard import render_wizard
    st = _st(tmp_path)
    h = render_wizard(st, "t", role="ii:mother_earth__nooch")
    assert re.search(r'PREROLE="ii:mother_earth__nooch"', h)
    assert "value='ii:mother_earth__nooch'" in h


def test_een_onbekende_ii_cirkel_wordt_niet_geslikt(tmp_path):
    """Fail-closed: een cirkel die niet bestaat is geen geldige eigenaar."""
    import re
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t", role="ii:bestaat-niet")
    assert re.search(r'PREROLE=""', h)


def test_de_cirkel_van_een_individuele_actie_wordt_niet_stilzwijgend_gekozen(tmp_path):
    """`_thuis_cirkel` koos de EERSTE subcirkel. Met één cirkel klopt dat toevallig; met twee zou
    'Individual action' er stilzwijgend één kiezen — dezelfde soort aanname als 'het eerste lopende
    project van deze eigenaar', die vandaag negen acties liet begraven."""
    from nooch_village import org
    from nooch_village.models import Record, RecordType, RoleDefinition
    from nooch_village.views.wizard import _role_options
    st = _st(tmp_path)
    tweede = Record(id="mother_earth__tweede", type=RecordType.CIRCLE, parent="mother_earth",
                    definition=RoleDefinition(purpose="tweede cirkel", accountabilities=[]))
    st.records.put(tweede)
    opts = _role_options(st)
    # beide cirkels worden aangeboden, elk met zijn naam — niet één stil gekozen
    assert opts.count("Individual action in ") == 2
    assert "value='ii:mother_earth__nooch'" in opts and "value='ii:mother_earth__tweede'" in opts
    # mét context is het er precies één: die van de baan waar je vandaan komt
    met = _role_options(st, circle="mother_earth__tweede")
    assert met.count("Individual action") == 1 and "value='ii:mother_earth__tweede'" in met


# ── Het kennis-budget en één modelbeleid (29 aug 2026) ──────────────────────

def _post(dd, pad: str, velden: dict) -> dict:
    """Eén echte POST naar het endpoint. Via een ECHTE request, want de vraag is juist of de ROUTE
    de dingen doorgeeft — een test die de hulpfunctie rechtstreeks aanroept slaat precies de regel
    over die stuk kan gaan."""
    import json as _json, threading, urllib.parse, urllib.request
    from http.server import HTTPServer
    from nooch_village import cockpit2 as c2

    srv = HTTPServer(("127.0.0.1", 0), c2.make_handler(dd, "t"))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        data = urllib.parse.urlencode({**velden, "csrf": "t"}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}{pad}", data=data)
        with urllib.request.urlopen(req, timeout=10) as r:
            return _json.loads(r.read().decode("utf-8"))
    finally:
        srv.shutdown()
        srv.server_close()


def test_de_wizard_vraagt_de_kennislaag_met_een_budget(tmp_path, monkeypatch):
    """De MENS wacht. Zijn browser stapt eruit na AI_TIMEOUT_MS, dus de raadpleging vóór het model
    krijgt een budget mee — anders eet de aanloop het werk op (gemeten op prod: 29,4s aanloop tegen
    3,3s plannen, waarna de checklist in een dichte verbinding werd geschreven)."""
    from nooch_village import cockpit2 as c2
    gezien = {}

    def _nep_kennis(bron, tekst, limit=5, *, exclude_pid="", deadline=None):
        gezien["deadline"] = deadline
        return {}
    monkeypatch.setattr("nooch_village.kennis_context.kennis_voor", _nep_kennis)
    monkeypatch.setattr("nooch_village.wizard.plan_items", lambda *a, **k: [])

    st = _st(tmp_path)
    _post(st.dd, "/wizard/plan", {"uitkomst": "iets onderzocht", "role": ""})
    assert gezien.get("deadline") == c2._WIZARD_KENNIS_BUDGET_S
    assert 0 < c2._WIZARD_KENNIS_BUDGET_S < 12, "het budget hoort een fractie van AI_TIMEOUT_MS te zijn"


def test_de_daemon_houdt_zijn_volle_raadpleging(tmp_path):
    """Het budget is er voor wie WACHT. De daemon kijkt naar geen enkel scherm en mag de tijd nemen;
    daar verandert deze PR niets — de default blijft 'geen budget'."""
    import inspect
    from nooch_village.kennis_context import kennis_voor
    assert inspect.signature(kennis_voor).parameters["deadline"].default is None


def test_plan_items_geeft_zijn_ladder_door(tmp_path):
    """Eén modelbeleid: de wizard-planner draait op het brein dat `llm_keuze` kiest, niet op de
    dorpsladder omdat de call_site toevallig anders heet dan bij de daemon."""
    from nooch_village.wizard import plan_items
    gezien = {}

    def _nep(prompt, **kw):
        gezien.update(kw)
        return '{"items":[{"tekst":"stap","skill":null,"payload":{}}]}'
    uit = plan_items("doel", [], reason_fn=_nep, ladder="anthropic:claude-sonnet-5,mistral:x")
    assert gezien["ladder"] == "anthropic:claude-sonnet-5,mistral:x"
    assert gezien["call_site"] == "wizard_plan"
    assert uit and uit[0]["tekst"] == "stap"
    # en zonder ladder blijft het gedrag exact als vóór deze PR: de dorpsladder
    plan_items("doel", [], reason_fn=_nep)
    assert gezien["ladder"] is None


def test_de_niet_blokkerende_suggestie_krijgt_een_eigen_budget(tmp_path):
    """De 12s zit er tegen een BLOKKERENDE wachttijd. De checklist-suggestie blokkeert niets — het
    invoerveld staat er al met de cursor erin — en draait bovendien op het traagste (beste) model.
    Met hetzelfde budget zouden we dat model betalen en het antwoord weggooien."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "const PLAN_TIMEOUT_MS=45000;" in h
    assert "/wizard/plan',{uitkomst:idee,role:S.role},PLAN_TIMEOUT_MS)" in h
    # de blokkerende stappen houden hun korte budget
    assert "/wizard/sharpen',{ruw:S.ruw},AI_TIMEOUT_MS)" in h
    assert 'onclick="suggesties()"' in h and "await suggesties()" not in h   # op de knop, niet ge-await


# ── Jouw woorden komen op het bord (12 september 2026) ──────────────────────

def test_de_suggestie_staat_naast_je_idee_en_landt_erin(tmp_path):
    """Stefan: "nu kan ik niet zien welke ik toevoeg." ✨ stond naast het kleine Done-when-veld en
    schreef daarin; het idee zelf ging nergens heen. Nu staat de knop achter het EERSTE veld en zet
    hij de suggestie dáár, met een weg terug naar je eigen woorden."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    form = h[h.index('id="wz-ruw"'):h.index('id="wz-role"')]
    assert form.count('id="wz-ai"') == 1                               # de knop, bij het eerste veld
    scherp = h[h.index("async function scherp"):h.index("function form")]
    assert "getElementById('wz-ruw')" in scherp and "getElementById('wz-uit')" not in scherp
    assert "S.ruwEigen=S.ruw" in scherp and "put your own words back" in scherp
    assert "function terug()" in h and "window.terug=terug" in h
    # het veld zegt wat het is: precies deze tekst komt op het bord
    assert "on the board exactly as written" in h


def test_de_titel_komt_letterlijk_op_het_bord(tmp_path, monkeypatch):
    """"Als ik het toevoeg laat AI de formulering nog een keer aanpassen, dat moet nooit mogen."
    Er zat een `title_from` in /wizard/create. Nu: wat de client als titel stuurt is de scope,
    teken voor teken, en er wordt bij het opslaan geen model meer aangeroepen."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "titel:S.ruw," in h and "uitkomst:S." not in h              # het veld, niet een afleiding

    def _geen_model(*a, **k):
        raise AssertionError("het model werd aangeroepen bij het opslaan")
    monkeypatch.setattr("nooch_village.llm.reason", _geen_model)
    st = _st(tmp_path)
    rid = "mother_earth__nooch__website_developer"
    wie = f"person:{st.people.all()[0].id}"                # de rol heeft twee vervullers: kies er één
    titel = "Onderzoek naar afbreekbare zolen, precies zoals ik het typte"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": titel, "uitkomst": "", "trekker": wie})
    assert r.get("pid") and r.get("titel") == titel, r
    p = cockpit2._Stores(st.dd).projects.get(r["pid"])
    assert p["scope"] == titel
    assert p["done_when"] == titel                       # de titel is de done-when: één tekst
    # een meegestuurde uitkomst wordt genegeerd: er is geen tweede veld meer
    r2 = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Header af", "uitkomst": "no complaints",
                                         "trekker": wie})
    p2 = cockpit2._Stores(st.dd).projects.get(r2["pid"])
    assert p2["scope"] == "Header af" and p2["done_when"] == "Header af"
    # zonder titel geen project (400, dus urllib gooit)
    import pytest, urllib.error
    voor = len(cockpit2._Stores(st.dd).projects.all())
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(st.dd, "/wizard/create", {"role": rid, "titel": "  ", "uitkomst": "x", "trekker": wie})
    assert exc.value.code == 400
    assert len(cockpit2._Stores(st.dd).projects.all()) == voor


def test_de_kolom_van_de_deur_reist_mee(tmp_path, monkeypatch):
    """"+ add project" onder Future maakte een project in Active: de wizard kende alleen queued.
    Stefan (12 sep): "dan neemt ie dat niet over." Nu draagt de deur zijn kolom, en de wizard
    vertaalt hem precies zoals het kale formulier dat deed: toekomst → future, wacht → geblokkeerd."""
    from nooch_village.views.projects import _quickadd
    rid = "mother_earth__nooch__website_developer"
    assert "col=toekomst" in _quickadd(rid, "toekomst", "t", "/x")
    assert "col=wacht" in _quickadd(rid, "wacht", "t", "/x")
    assert "col=actief" in _quickadd(rid, "actief", "t", "/x")        # de deur onder Active maakt actief
    from nooch_village.views.wizard import render_wizard
    st = _st(tmp_path)
    h = render_wizard(st, "t", role=rid, col="toekomst")
    assert 'col:"toekomst"' in h and "' · Future'" in h              # de kop zegt waar het landt
    assert 'col:""' in render_wizard(st, "t", role=rid, col="onzin")  # onbekend = actief
    monkeypatch.setattr("nooch_village.llm.reason", lambda *a, **k: None)
    wie = f"person:{st.people.all()[0].id}"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Later", "col": "toekomst", "trekker": wie})
    assert cockpit2._Stores(st.dd).projects.get(r["pid"])["status"] == "future"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Wacht", "col": "wacht", "trekker": wie})
    p = cockpit2._Stores(st.dd).projects.get(r["pid"])
    assert p["status"] == "blocked" and p["blocked_on"] == "—"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Nu", "col": "actief", "trekker": wie})
    assert cockpit2._Stores(st.dd).projects.get(r["pid"])["status"] == "running"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Zonder deur", "trekker": wie})
    assert cockpit2._Stores(st.dd).projects.get(r["pid"])["status"] == "future"   # default: slapend (scope 49)


def test_tijd_is_een_getal_met_uren_of_dagen(tmp_path, monkeypatch):
    """De vier chips (1 hour · 1 day · 2 days · 1 week) zijn weg: Stefan wil "een invoerveld en
    erachter uren of dagen", en zo staat het al in de rail. Eén conversieregel (`uren_uit`) voor
    beide; de AI-gok levert nog een bucket en wordt via dezelfde tabel naar uren vertaald."""
    from nooch_village.views.wizard import render_wizard
    from nooch_village.views.projects import _EFFORT_ENUM_HOURS
    st = _st(tmp_path)
    h = render_wizard(st, "t")
    assert 'id="wz-uren"' in h and 'id="wz-eenheid"' in h and "1 week" not in h
    assert "EFFORT_UREN=" + json.dumps(_EFFORT_ENUM_HOURS) in h          # de servertabel, één bron
    assert "uren:S.uren,eenheid:S.eenheid" in h
    assert cockpit2.uren_uit("2", "dagen") == 16 and cockpit2.uren_uit("3", "uren") == 3
    assert cockpit2.uren_uit("", "uren") is None and cockpit2.uren_uit("0", "dagen") is None
    monkeypatch.setattr("nooch_village.llm.reason", lambda *a, **k: None)
    rid = "mother_earth__nooch__website_developer"
    wie = f"person:{st.people.all()[0].id}"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Twee dagen", "uren": "2",
                                        "eenheid": "dagen", "trekker": wie})
    assert cockpit2._Stores(st.dd).projects.get(r["pid"])["effort"] == {"hours": 16}
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Ongeschat", "uren": "", "trekker": wie})
    assert not cockpit2._Stores(st.dd).projects.get(r["pid"]).get("effort")


def test_een_doel_kies_je_al_in_de_wizard(tmp_path, monkeypatch):
    """Stefan: "hier ook alvast de koppeling met een doel kunnen maken." De open doelen staan in de
    wizard; het werkpakket verschijnt alleen als het doel er heeft; create koppelt via dezelfde
    `set_doel` als de rail. Een onbekend doel is een 400, geen half project."""
    from nooch_village.views.wizard import render_wizard
    st = _st(tmp_path)
    assert 'DOELOPTS="";' in render_wizard(st, "t")                     # geen open doel = geen keuze
    d = st.doelen.add("Rapport MITH", label="MITH", activiteiten=["WP1", "WP2"])
    dicht = st.doelen.add("Oud doel", label="Oud"); st.doelen.update(dicht["id"], status="behaald")
    h = render_wizard(st, "t")
    assert f"value='{d['id']}'" in h and "MITH · Rapport MITH" in h
    assert f"value='{dicht['id']}'" not in h                              # alleen open doelen
    assert json.dumps({d["id"]: {"w": ["WP1", "WP2"]}}) in h
    assert "label:" not in h                                             # geen state-veld (zie label-test)
    monkeypatch.setattr("nooch_village.llm.reason", lambda *a, **k: None)
    rid = "mother_earth__nooch__website_developer"
    wie = f"person:{st.people.all()[0].id}"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Sectie 1", "doel_id": d["id"],
                                        "activiteit": "WP1", "trekker": wie})
    p = cockpit2._Stores(st.dd).projects.get(r["pid"])
    assert p["doel_id"] == d["id"] and p["activiteit"] == "WP1"
    r = _post(st.dd, "/wizard/create", {"role": rid, "titel": "Los", "doel_id": d["id"],
                                        "activiteit": "bestaat niet", "trekker": wie})
    p = cockpit2._Stores(st.dd).projects.get(r["pid"])
    assert p["doel_id"] == d["id"] and p["activiteit"] is None           # onbekend werkpakket valt af
    import pytest, urllib.error
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(st.dd, "/wizard/create", {"role": rid, "titel": "X", "doel_id": "nope", "trekker": wie})
    assert exc.value.code == 400


def test_de_sectie_wie_kan_dit_oppakken_is_weg_maar_de_owner_kiezer_niet(tmp_path):
    """Stefan (12 sep): "de stap 'who could pick this up' kan ook weg." Rolsuggesties, stappen
    uitdelen en het endpoint /wizard/rollen zijn eruit. De owner-kiezer niet: de server weigert een
    project bij een rol met twee vervullers zonder owner, dus die staat nu op de snelle route, direct
    onder de rol, en alleen als er echt iets te kiezen valt."""
    from nooch_village.views.wizard import render_wizard
    st = _st(tmp_path)
    h = render_wizard(st, "t")
    assert "<summary>Who could pick this up" not in h and "/wizard/rollen" not in h
    assert 'class="wz-clab">Hand out steps' not in h and "taken:" not in h and "function rollen" not in h
    assert "function toonOwner()" in h and 'id="wz-ownerwrap"' in h
    assert h.index('id="wz-ownerwrap"') < h.index('id="wz-save"')       # op de snelle route
    assert "opties.length<2" in h                                       # alleen bij ≥ 2 vervullers
    from nooch_village import wizard
    assert not hasattr(wizard, "roles_for") and not hasattr(wizard, "roles_for_tekst")
