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
    h = render_wizard(st, "t", role=rid, ruw="doos scheurt", uitkomst="geen klachten meer")
    assert 'ruw:"doos scheurt"' in h and 'uitkomst:"geen klachten meer"' in h
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
    assert "(S.uitkomst||S.ruw)" in h                    # geen uitkomst → het idee telt


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
    assert "ruw:" in bord and "uitkomst:" in bord        # titel én done-when reizen mee
    inbox = _outcome_form("project", "nid", "t", "de spanningstekst", "<option>r</option>", "",
                          "/inbox", "u1")
    assert "/project/nieuw?" in inbox and "notif_outcome" not in inbox
    assert "ruw:" in inbox and "role:" in inbox          # content als zaad, rol mee
    # de andere uitkomsttypen blijven gewoon opnemen
    ping = _outcome_form("ping", "nid", "t", "x", "<option>r</option>", "", "/inbox", "u2")
    assert "notif_outcome" in ping and "/project/nieuw" not in ping


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
    de mens zetten bij een lijstje afvinken. Openen is typen."""
    from nooch_village.views.wizard import render_wizard
    h = render_wizard(_st(tmp_path), "t")
    assert "type a step and press Enter" in h
    assert "makes a checklist and checks it against your skills" not in h   # het wachtscherm
    # de suggestie-call wordt NIET ge-await voordat de lijst er staat
    body = h.split("async function checklist()")[1][:400]
    assert "draw();" in body and "suggesties();" in body
    assert "await suggesties" not in body


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
