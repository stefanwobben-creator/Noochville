"""Het menselijke sluitstuk: zien, bijstellen, bevestigen — en pas dán schrijven.

DIT IS DE EERSTE FEATURE DIE ÉCHT IN DE PROJECTDOCUMENTEN SCHRIJFT. Twee harde regels op de data,
en beide staan hier omdat ze met de hand terugsluipen zodra iemand "even" een pad bijmaakt:

1. **Alleen een expliciete bevestiging schrijft.** Een onbevestigd concept mag nooit stil het
   document worden. Dat is niet één functie die je bewaakt maar een eigenschap van het geheel:
   geen enkele andere route mag de canonieke tekst vervangen.
2. **Geen downgrade.** Waar al een écht rapport staat (geen seed), dringt de vraag zich niet op.
   Gemeten op productie: 152 van de 300 afsluitbare projecten hebben een leeg of seed-document en
   krijgen de vraag wél; 148 hebben een echt rapport en krijgen hem niet.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.project_verslag import met_result, modeloordeel
from nooch_village.projects import seed_document
from nooch_village.views import projects as P

ROLE = "mother_earth__nooch__brand_visual_designer"          # één vervuller: geen keuze-eis


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _afgesloten(dd, st, *, doc="", items=(("A", True),)):
    pid = st.projects.create(ROLE, "Sluitstuk", "human", status="queued", done_when="af")
    st.projects.start(pid)
    cl = st.projects.checklist_add(pid, "tasks")["id"]
    for tekst, _ in items:
        st.projects.check_add(pid, cl, tekst)
    rij = next(c for c in st.projects.get(pid)["checklists"] if c["id"] == cl)["items"]
    for (_, af), it in zip(items, rij):
        if af:
            st.projects.check_toggle(pid, cl, it["id"])
    if doc:
        cockpit2._Stores(dd).project_docs.write(pid, doc)
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    return pid


# ── regel 1: alleen een expliciete bevestiging schrijft ──────────────────────
def test_afsluiten_alleen_verandert_het_document_niet(tmp_path):
    """De hele reden dat het concept ernaast wacht."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="# Het werk\n\nDit stond er al en mag niet verdwijnen.")
    st2 = cockpit2._Stores(dd)
    assert "mag niet verdwijnen" in st2.project_docs.read(pid)
    assert (st2.project_docs.concept(pid).get("tekst") or "").strip()


def test_bijwerken_schrijft_niet(tmp_path):
    """Bijstellen raakt het CONCEPT. Wie een tekst bijschaaft heeft daarmee nog niets bevestigd."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    cockpit2.dispatch(dd, "verslag_bijwerken", {"pid": [pid], "tekst": ["## Result\nmijn versie"],
                                                "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).project_docs.read(pid) == "oud document"


def test_geen_enkele_andere_dispatch_maakt_het_concept_tot_document(tmp_path):
    """DE EIGENSCHAP, NIET DE FUNCTIE. Niet één handler bewaken maar het geheel: draai alles wat
    een project raakt en controleer dat het document onaangeroerd blijft."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    concept = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
    for actie, extra in (("proj_status", {"to": ["actief"]}),
                         ("proj_setimpact", {"kind": ["missie"], "value": ["versterkt"]}),
                         ("proj_seteffort", {"number": ["2"], "unit": ["uren"]}),
                         ("proj_setdue", {"due": ["2026-12-01"]}),
                         ("proj_feed", {"text": ["iets"], "author": ["human:"]}),
                         ("checklist_add", {"title": ["tasks"]}),
                         ("proj_done", {}),
                         ("verslag_bijwerken", {"tekst": ["ander concept"]})):
        cockpit2.dispatch(dd, actie, {"pid": [pid], "next": ["/"], **extra}, username="guest")
        assert cockpit2._Stores(dd).project_docs.read(pid) == "oud document", actie
    assert concept                                          # er wás wel degelijk iets te schrijven


def test_bevestigen_is_de_enige_schrijver(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    concept_voor = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
    cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    doc = st2.project_docs.read(pid)
    # De concepttekst gaat ONGEWIJZIGD door: wat de mens las is wat er wordt vastgelegd.
    assert "oud document" not in doc and doc == concept_voor
    assert st2.project_docs.concept(pid) == {}
    assert st2.projects.get(pid)["resultaat"] == "behaald"


# ── regel 2: geen downgrade ──────────────────────────────────────────────────
def test_bij_een_echt_rapport_dringt_de_vraag_zich_niet_op(tmp_path):
    """Een formulier dat vraagt of we een bestaand rapport mogen vervangen is een stille downgrade
    in beleefde vorm. 148 van de 300 afsluitbare projecten zitten in dit geval."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="# Werk\n\nDit is een echt geschreven rapport met inhoud.")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "needs your confirmation" not in frag
    assert "Draft report awaiting confirmation" in frag      # wel te vinden, niet opgedrongen


def test_bij_een_leeg_of_seed_document_wel(tmp_path):
    """152 van de 300: daar is er niets om te downgraden, en dan is de vraag juist welkom."""
    dd, st = _st(tmp_path)
    leeg = _afgesloten(dd, st, doc="")
    seed = _afgesloten(dd, st, doc=seed_document("De shortlist is af"))
    for pid in (leeg, seed):
        frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
        assert "needs your confirmation" in frag, pid
        assert "verslag_bevestig" in frag and "verslag_overslaan" in frag


# ── de vorm: geen poort, twee signalen, overslaan mag ────────────────────────
def test_de_status_staat_al_op_done_voordat_de_vraag_komt(tmp_path):
    """GEEN DIALOOG TUSSEN DE KLIK EN DE STATUSWISSEL. De vraag is een gevolg, geen voorwaarde."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "done"


def test_de_twee_signalen_staan_naast_elkaar(tmp_path):
    """Botsen ze — checklist "8 van 8 af", gesprek "twee gaten open" — dan is dat iets om naar te
    kijken. Samenvoegen tot één cijfer zou juist die botsing verstoppen."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    store = cockpit2._Stores(dd).project_docs
    store.write_concept(pid, "## Goal\nx\n\n## Result\nNot achieved. Twee gaten open.",
                        bronnen=["de projectdefinitie"], voorzet="behaald")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    sig = frag.split("einddoc-sig'>")[1].split("</div>")[0]
    # HET OORDEEL, niet de hele alinea: "Twee gaten open" is de onderbouwing en hoort in het
    # rapport. In een balk van één regel zou hij als tweede samenvatting lezen.
    assert "Draft concluded" in sig and "Not achieved" in sig
    assert "Twee gaten open" not in sig
    assert "Checklist says" in sig and "achieved" in sig
    # de botsing blijft zichtbaar: het model zegt nee, de checklist ja
    assert "Not achieved" in sig and "<b>achieved</b>" in sig


def test_zonder_result_kop_toont_alleen_de_kruischeck(tmp_path):
    """Liever niets dan een willekeurige alinea die zich voordoet als een oordeel."""
    assert modeloordeel("## Goal\nx\n\n## What happened\ny") == ""


def test_overslaan_markeert_eerlijk_in_plaats_van_te_zwijgen(tmp_path):
    """Een overgeslagen vraag mag later niet lezen als een bevestigd "behaald" — dat is precies de
    stille mislukking die we vermijden."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    cockpit2.dispatch(dd, "verslag_overslaan", {"pid": [pid], "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["resultaat"] == "overgeslagen"
    # Het VERSLAG is Nederlands (orgkennis); het SCHERM blijft Engels. Zelfde sleutel,
    # twee lezers — zie label_voor(taal=).
    # Toevoegen, niet herschrijven: anders leest het rapport als een bevestigd oordeel
    # terwijl niemand er ja op zei.
    assert "Closed without a recorded result" in st2.project_docs.read(pid)
    assert st2.project_docs.concept(pid) == {}


def test_een_nee_kan_net_zo_makkelijk_als_een_ja(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    cockpit2.dispatch(dd, "verslag_bevestig_niet_behaald", {"pid": [pid], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    # Het TELBARE deel is het oordeel; de tekst blijft die van het rapport.
    assert st2.projects.get(pid)["resultaat"] == "niet_behaald"


def test_learnings_zijn_optioneel(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["resultaat"] == "behaald"
    assert "## Learnings" not in st2.project_docs.read(pid)


def test_een_onbekende_waarde_kan_niet_meer_binnenkomen(tmp_path):
    """Het oordeel komt niet meer uit het formulier maar uit de ACTIE, en die is er maar in twee
    smaken. `set_resultaat` blijft fail-closed voor programmatische aanroepen."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    assert st.projects.set_resultaat(pid, "misschien") is False
    assert cockpit2._Stores(dd).project_docs.read(pid) == "oud document"


# ── het oordeel vervangt dat van het model, zonder de rest te verliezen ──────
def test_het_menselijke_oordeel_vervangt_dat_van_het_model():
    c = "## Goal\nDoel.\n\n## What happened\nDingen.\n\n## Result\nNot achieved. Twee gaten."
    n = met_result(c, "behaald", "Toch af na de review.", "Eerder om review vragen.")
    assert "## Goal\nDoel." in n and "Dingen." in n          # geen informatieverlies
    assert "Twee gaten" not in n                             # het voorstel maakt plaats
    assert "**Achieved.** Toch af na de review." in n        # verslagtaal = Engels
    assert "## Learnings\nEerder om review vragen." in n


def test_zonder_result_kop_komt_het_blok_er_gewoon_onder():
    """De modelloze variant heeft wél een Result-kop, maar een handmatig bijgewerkt concept
    misschien niet. Dan hoort het oordeel er alsnog bij te komen."""
    n = met_result("## Goal\nAlleen dit.", "behaald", "Klaar.")
    assert "Alleen dit." in n and "**Achieved.** Klaar." in n


# ── één set sleutels voor het hele dorp ──────────────────────────────────────
def test_de_oordeelsleutels_staan_op_een_plek():
    """ZE STONDEN EVEN IN TWEE SPELLINGEN. `projects.py` had "niet_behaald" en `project_verslag`
    had "niet behaald" (met een spatie). Het gevolg was meteen zichtbaar in een doorloop: de kaart
    toonde `Checklist says: niet_behaald` — de rauwe sleutel, omdat de labeltabel de ándere
    spelling kende en er dus geen label was.

    De sleutels wonen in `projects.py` (project_verslag mag daaruit importeren, andersom zou een
    cirkel zijn) en de ledger leest dezelfde tupel."""
    from nooch_village.project_verslag import _VOORZET_LABEL, label_voor
    from nooch_village.projects import (BEHAALD, NIET_BEHAALD, OVERGESLAGEN, ProjectLedger,
                                        RESULTAAT_WAARDEN)
    assert ProjectLedger.RESULTAAT_WAARDEN is RESULTAAT_WAARDEN
    assert RESULTAAT_WAARDEN == (BEHAALD, NIET_BEHAALD, OVERGESLAGEN)
    # elke opslagbare waarde heeft een label; anders lekt de sleutel naar het scherm
    # DE ECHTE EIS IS EEN INGANG, niet dat sleutel en label verschillen: in het Nederlands ís
    # `behaald` gewoon "behaald". Ontbreekt een ingang, dan valt `label_voor` terug op de sleutel
    # en lekt die naar het scherm — dát is wat hier bewaakt wordt.
    for taal in ("en", "nl"):
        for w in RESULTAAT_WAARDEN:
            assert w in _VOORZET_LABEL[taal], (taal, w)
    # Op het SCHERM (Engels) mag een label nooit gelijk zijn aan de opslagsleutel: daar zou een
    # ontbrekende ingang onzichtbaar blijven.
    for w in RESULTAAT_WAARDEN:
        assert label_voor(w, "en") != w, w


def test_geen_rauwe_sleutel_op_de_kaart(tmp_path):
    """De doorloop ving dit: een voorzet zonder label rendert als `niet_behaald`."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    store = cockpit2._Stores(dd).project_docs
    from nooch_village.projects import NIET_BEHAALD
    c = store.concept(pid)
    store.write_concept(pid, c["tekst"], bronnen=c.get("bronnen") or [], voorzet=NIET_BEHAALD)
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    # In de GETOONDE tekst hoort het label; als radio-WAARDE hoort juist de sleutel. Toets dus de
    # signaal-cellen en niet de hele HTML — anders verbiedt de guard iets wat correct is.
    import re
    sig = frag.split("einddoc-sig'>")[1].split("</div>")[0]
    assert "not achieved" in sig, sig                        # scherm blijft Engels
    assert NIET_BEHAALD not in sig, f"opslagsleutel getoond: {sig}"
    # De sleutel staat niet meer als formulierwaarde in de HTML: hij zit in de ACTIENAAM
    # (`verslag_bevestig_niet_behaald`). Dat is nóg een plek minder waar hij kan lekken.
    assert "value='verslag_bevestig_niet_behaald'" in frag


# ── cluster 1: de suggestie doet het voorwerk ────────────────────────────────
def test_er_zijn_geen_losse_why_en_learnings_velden(tmp_path):
    """HET RAPPORT ÍS HET FORMULIER. Die velden herhaalden de Result- en Learnings-sectie die al in
    het rapport staat: je typte tweemaal hetzelfde en er ontstonden twee versies van dezelfde
    gedachte. Bewerken gebeurt op één plek — in het rapport, via "Edit before confirming"."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert 'name="toelichting"' not in frag and 'name="learnings"' not in frag
    assert "Edit before confirming" in frag or "Read the draft" in frag
    assert "reasoning and learnings live in the report" in frag


def test_het_oordeel_wordt_niet_voorgeselecteerd(tmp_path):
    """GEEN DEFAULT OP DE JA/NEE. De toelichting en de leringen zijn een concept om bij te schaven
    — daar scheelt voorinvullen echt werk. Het oordeel is iets anders: dat is de ene beslissing die
    de mens actief moet nemen, en élke default duwt hem naar een antwoord zodra de twee signalen
    botsen. Ze staan eronder; hij kiest."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="", items=(("A", False),))
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    # De keuze is een segmented control van twee ACTIES. Een knop heeft geen "checked"-staat, dus
    # voorselectie is niet alleen afwezig maar onmogelijk — sterker dan een lege radio.
    assert "value='verslag_bevestig_behaald'" in frag
    assert "value='verslag_bevestig_niet_behaald'" in frag
    assert "checked" not in frag.split("einddoc-rform")[1].split("</form>")[0]


def test_bevestigen_zonder_keuze_kan_niet_meer_bestaan(tmp_path):
    """Er was een aparte Confirm-knop die een oordeel EISTE maar er geen kon meesturen — daar kwam
    de weigering "pick achieved or not achieved first" vandaan. Die knop is weg: de keuze ís de
    bevestiging, dus een POST zonder oordeel bestaat niet meer als pad.

    Wat blijft: een onbekende actie doet niets. Dat is de vangnet-kant."""
    from nooch_village import cockpit2 as ck
    assert "verslag_bevestig" not in ck.ACTIONS
    assert "verslag_bevestig_behaald" in ck.ACTIONS
    assert "verslag_bevestig_niet_behaald" in ck.ACTIONS


def test_verslag_en_scherm_delen_de_taal_maar_de_infra_blijft(tmp_path):
    """Scherm én verslag zijn Engels, passend bij de cockpit. De `taal`-parameter blijft staan:
    de sleutel is mechaniek en het label is content, dus zodra er een taalinstelling komt hoeft
    alleen de aanroep te kiezen. We bouwen die instelling nu niet — alleen de default staat om."""
    from nooch_village.project_verslag import label_voor
    assert label_voor("behaald") == "achieved"               # default = scherm én verslag
    assert label_voor("behaald", "nl") == "behaald"          # de taal-infra blijft bestaan
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    doc = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
    assert "## Goal" in doc and "## What happened" in doc and "## Result" in doc
    assert "## Doel" not in doc and "## Wat er gebeurde" not in doc


def test_de_kopnamen_leven_op_een_plek():
    """`met_result` en `modeloordeel` zoeken naar de koppen die de prompt voorschrijft. Stonden die
    los, dan zou een prompt-wijziging de zoekfunctie stil laten missen — en dan valt het
    modeloordeel weg zónder foutmelding. Engelse koppen blijven herkend voor oude documenten."""
    from nooch_village.project_verslag import KOP_RESULTAAT, _PROMPT, met_result, modeloordeel
    assert f"## {KOP_RESULTAAT}" in _PROMPT
    assert modeloordeel(f"## {KOP_RESULTAAT}\nBehaald.") == "Behaald."
    assert modeloordeel("## Result\nAchieved.") == "Achieved."          # document van vóór deze PR
    assert "Twee gaten" not in met_result("## Result\nTwee gaten.", "behaald")


def test_geen_kop_per_taak_meer_in_de_prompt():
    """Gemeten op productie: 310 documenten met mediaan 6 koppen, waarvan 253 kopblokken
    "niet onderzocht" bevatten en 64 (bijna) leeg zijn. Een kop per taak levert vooral koppen op
    die zeggen dat er niets is."""
    from nooch_village.project_verslag import _PROMPT
    assert "NO heading per task" in _PROMPT
    assert "Not investigated:" in _PROMPT                     # één zin, niet een kopje per taak


def test_het_doeltype_staat_in_de_prompt():
    """Een beoordelingsproject is behaald zodra er een gegrond oordeel ligt — ook een "nee".
    Zonder dit leest de assembler elk "nee" als een mislukking."""
    from nooch_village.project_verslag import _PROMPT
    assert "ASSESSMENT project" in _PROMPT and "including a 'no'" in _PROMPT


def test_de_assemblage_staat_op_de_hoog_inzet_ladder():
    """Dit wordt orgkennis zodra een mens het bevestigt. Een zwakke samenvatting die je bevestigt
    is erger dan geen samenvatting: je kunt hem daarna niet meer wantrouwen.

    LET OP WAT DEZE TEST WÉL EN NIET ZEGT: hij toetst de BEREKENDE ladder. Dat is de configuratie,
    niet het gedrag — en die stond maandenlang groen terwijl `reason()` in werkelijkheid mistral
    pakte, omdat niemand de berekende ladder aan `reason()` doorgaf.
    `test_hoog_inzet_gebruikt_de_dure_kop_ook_zonder_expliciete_ladder` hieronder toetst de
    GEBRUIKTE ladder; die twee horen bij elkaar."""
    from nooch_village.llm_keuze import HOOG_INZET, ladder_voor
    assert "verslag_assemblage" in HOOG_INZET
    assert (ladder_voor("verslag_assemblage") or "").startswith("anthropic:claude-sonnet")


def test_hoog_inzet_gebruikt_de_dure_kop_ook_zonder_expliciete_ladder(monkeypatch):
    """DE GEBRUIKTE LADDER, NIET DE BEREKENDE. Dit is de guard die er niet was.

    `ladder_voor()` gaf de Sonnet-kop keurig terug, maar `reason()` gebruikte de DORPSLADDER —
    die met mistral begint — tenzij de caller `ladder=` meegaf. Vijf van de tien HOOG_INZET-sites
    deden dat niet, dus die draaiden stil op de goedkope staart. Op productie: wizard_plan 31 van
    31 calls op mistral, terwijl Sonnet gewoon 200 gaf.

    Deze test kijkt naar WELKE TREDE ER DAADWERKELIJK WORDT AANGEROEPEN, voor élke hoog-inzet-site,
    zonder expliciete ladder."""
    from nooch_village import llm
    from nooch_village.llm_keuze import HOOG_INZET
    geprobeerd: list[tuple] = []

    def _vang(vendor, model, prompt, **k):
        geprobeerd.append((vendor, model))
        return "ok"
    monkeypatch.setattr(llm, "_call_tier", _vang)
    monkeypatch.setattr(llm, "_in_cooldown", lambda tier, **k: False)
    for site in sorted(HOOG_INZET):
        geprobeerd.clear()
        llm.reason("x", call_site=site)                       # GEEN ladder= meegegeven
        assert geprobeerd, site
        vendor, model = geprobeerd[0]
        assert vendor == "anthropic" and "sonnet" in (model or ""), (site, geprobeerd[0])


def test_een_gewone_site_blijft_op_de_dorpsladder(monkeypatch):
    """De tegenproef: zonder deze zou de test hierboven ook slagen als ALLES op Sonnet ging."""
    from nooch_village import llm
    geprobeerd: list[tuple] = []
    monkeypatch.setattr(llm, "_call_tier",
                        lambda vendor, model, prompt, **k: geprobeerd.append((vendor, model)) or "ok")
    monkeypatch.setattr(llm, "_in_cooldown", lambda tier, **k: False)
    llm.reason("x", call_site="triage_spanning")
    assert geprobeerd and geprobeerd[0][0] != "anthropic", geprobeerd


def test_een_expliciete_ladder_wint_nog_steeds(monkeypatch):
    """De caller mag bewust afwijken; `reason` vult alleen een gat."""
    from nooch_village import llm
    geprobeerd: list[tuple] = []
    monkeypatch.setattr(llm, "_call_tier",
                        lambda vendor, model, prompt, **k: geprobeerd.append((vendor, model)) or "ok")
    monkeypatch.setattr(llm, "_in_cooldown", lambda tier, **k: False)
    llm.reason("x", call_site="verslag_assemblage", ladder="mistral:mistral-small-latest")
    assert geprobeerd[0] == ("mistral", "mistral-small-latest"), geprobeerd


# ── de oordeelvraag staat op BEIDE schermen ──────────────────────────────────
def test_de_rapportroute_biedt_dezelfde_oordeelvraag(tmp_path):
    """DE BLOKKADE. `/rapport` had alleen een kale "Confirm report"-knop; de radio's stonden enkel
    op de kaart. Toen bevestigen een oordeel ging EISEN, weigerde die knop dus altijd — op het
    scherm waar het concept juist het best zichtbaar is.

    Eén functie (`views.projects.result_velden`), twee aanroepers. Een derde kopie zou hetzelfde
    opnieuw laten verlopen."""
    from nooch_village.views.rapport import render_projectrapport
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    for naam, html in (("kaart", P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")),
                       ("route", render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK"))):
        assert "value='verslag_bevestig_behaald'" in html, naam
        assert "value='verslag_bevestig_niet_behaald'" in html, naam
        assert "verslag_overslaan" in html, naam
        blok = html.split("einddoc-rform")[1].split("</form>")[0]
        assert "checked" not in blok, f"{naam}: oordeel voorgeselecteerd"


def test_bevestigen_vanaf_de_route_werkt_met_een_keuze(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    _, msg = cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": [f"/rapport?pid={pid}"]},
                      username="guest")
    assert not cockpit2.is_weigering(msg), msg
    assert cockpit2._Stores(dd).projects.get(pid)["resultaat"] == "behaald"


# ── de koppen zijn vaste labels ──────────────────────────────────────────────
def test_een_verkeerd_gespelde_kop_wordt_rechtgezet():
    """"Lernings" is geen verzinsel: dat stond letterlijk in een document op productie. Een kop die
    uit modeltekst komt is een typefout die wacht om te gebeuren — en dan vindt `met_result` de
    Result-sectie niet meer en valt het modeloordeel weg ZONDER foutmelding."""
    from nooch_village.project_verslag import normaliseer_koppen
    n = normaliseer_koppen("## Lernings\nx\n\n### Wat er gebeurde\ny\n\n## Resultaat\nz")
    assert "## Learnings" in n and "### What happened" in n and "## Result" in n
    assert "Lernings" not in n


def test_een_onbekende_kop_blijft_staan():
    """Liever een onbekende kop zichtbaar dan stilletjes hernoemd naar iets wat het model niet
    bedoelde."""
    from nooch_village.project_verslag import normaliseer_koppen
    assert "## Iets eigens" in normaliseer_koppen("## Iets eigens\nx")


def test_de_normalisatie_draait_op_de_modeloutput(tmp_path):
    from nooch_village.project_verslag import stel_samen
    c = stel_samen({"scope": "x", "checklists": [{"items": [{"text": "a", "done": True}]}]}, "",
                   reason=lambda *a, **k: "```markdown\n## Lernings\nIets geleerd.\n```")
    assert "## Learnings" in c.tekst and "Lernings" not in c.tekst


# ── de caps knipten feiten weg ───────────────────────────────────────────────
def test_de_gesprekscap_is_verruimd_op_een_meting():
    """Een verslag zei "Paques niet bevestigd" terwijl de wall die communicatie toonde: de
    vermelding stond op positie 670 in een regel van 1296 tekens, en de cap stond op 600. Een
    tweede project verloor hem aan de regel-cap (23 → 20 regels).

    Gemeten over 373 projecten: 3075 gespreksregels, 2696 in de prompt, 598 ingekort, 22 projecten
    die hele regels kwijtraakten. Bij 1500/50 zijn mediaan en p90 van de invoer identiek aan
    ongekapt (1556 / 3897 tokens); de caps bijten alleen de uiterste staart nog."""
    from nooch_village.project_verslag import _MAX_REGELS, _REGEL_CAP
    assert _REGEL_CAP >= 1300, "een regel van 1296 tekens moet er heel in passen"
    assert _MAX_REGELS >= 40
    # en ze staan er nog: zonder cap bepaalt het langste gesprek de prijs van élk verslag
    assert _REGEL_CAP < 10_000 and _MAX_REGELS < 1_000


def test_een_feit_diep_in_een_lange_regel_bereikt_de_prompt():
    from nooch_village.project_verslag import _gesprek
    lang = "x " * 400 + "Paques Helian bevestigde de levering." + " y" * 200
    regels = _gesprek({"log": [{"who": "rol", "text": lang}]})
    assert any("Paques Helian bevestigde" in r for r in regels), "feit weggeknipt door de cap"


# ── de outcome-affordance is weg ─────────────────────────────────────────────
def test_de_outcome_kiezer_staat_niet_meer_onder_elk_bericht(tmp_path):
    """Hij werd niet gebruikt — routeren gebeurt vanuit de inbox of via een @mention. Een
    affordance die niemand gebruikt is niet neutraal: hij staat onder ÉLK bericht en maakt de wall
    drukker naarmate er meer gesprek is."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "text": ["een bericht"], "author": ["human:"],
                                        "next": ["/"]}, username="guest")
    html = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "wall_outcome" not in html
    assert "→ outcome" not in html and "→ uitkomst" not in html


def test_de_outcome_machinerie_zelf_blijft_bestaan():
    """De checklist-kant gebruikt hem nog en de `wall_outcome`-dispatch bedient de inbox-route.
    Alleen de knop onder elk bericht is weg, niet het mechanisme."""
    from nooch_village.views.feed import _wall_outcome_form, _wall_outcome_opts
    from nooch_village import cockpit2 as ck
    assert callable(_wall_outcome_form) and callable(_wall_outcome_opts)
    assert "wall_outcome" in ck.ACTIONS


# ── de compacte bevestigbalk (docs/confirm_schoon.html) ─────────────────────
def test_de_balk_staat_onder_het_rapport_in_de_volgorde_van_de_referentie(tmp_path):
    """HET RAPPORT ÍS HET FORMULIER: eerst lezen, dan de balk. Banner → chip → provenance →
    rapport → scheiding → signalen → keuze → acties → hint."""
    from nooch_village.views.rapport import render_projectrapport
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK")
    # alleen de MARKUP: de ingesloten stylesheet bevat dezelfde klassenamen en matcht anders mee —
    # dat maakte mijn eerste meting onzin.
    body = html[html.rindex("</style>"):]
    volgorde = ["einddoc-banner", "not confirmed yet", "einddoc-prov", "einddoc-body",
                "einddoc-split", "einddoc-sig'", "einddoc-verdict", "einddoc-acties",
                "einddoc-hint"]
    pos = [body.find(k) for k in volgorde]
    assert all(p >= 0 for p in pos), dict(zip(volgorde, pos))
    assert pos == sorted(pos), dict(zip(volgorde, pos))


def test_de_signaalregel_toont_het_oordeel_en_niet_de_hele_alinea():
    """Gezien in de render: "Draft concluded **Achieved.** The STCB grant was successfully
    submitted, approved, and funded." — de hele Result-alinea, mét sterretjes, in een balk van één
    regel. Dan staat dezelfde samenvatting er twee keer en leest de balk als een tweede rapport."""
    from nooch_village.project_verslag import modeloordeel_kort
    lang = "**Achieved.** The STCB grant was successfully submitted, approved, and funded."
    assert modeloordeel_kort(f"## Result\n{lang}") == "Achieved"
    assert "**" not in modeloordeel_kort(f"## Result\n{lang}")
    assert modeloordeel_kort("## Goal\nx") == ""            # geen Result-kop → geen signaal
    lang2 = "Not achieved because two of three suppliers never replied to the request at all"
    assert len(modeloordeel_kort(f"## Result\n{lang2}")) <= 61


def test_de_keuze_is_de_enige_gestructureerde_invoer(tmp_path):
    """Het telbare oordeel blijft; de reasoning en leringen leven in het rapport."""
    from nooch_village.views.rapport import render_projectrapport
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK")
    body = html[html.rindex("</style>"):]
    invoervelden = [n for n in ("toelichting", "learnings")
                    if f'name="{n}"' in body or f"name='{n}'" in body]
    assert invoervelden == [], invoervelden
    # het oordeel zit in de ACTIE, niet in een veld — zie test_een_keuzeknop_draagt_zowel…
    assert "value='verslag_bevestig_behaald'" in body


# ── één klik draagt de hele beslissing ───────────────────────────────────────
def _knoppen_in_de_balk(html: str):
    """De submitknoppen in het bevestigformulier, zoals een browser ze zou versturen: alleen de
    naam/waarde van de knop die je indrukt, plus de hidden inputs."""
    import re
    body = html[html.rindex("</style>"):]
    form = body.split("einddoc-rform")[1].split("</form>")[0]
    knoppen = [(m.group(1), m.group(2))
               for m in re.finditer(r"<button[^>]*name='([a-z]+)' value='([a-z_]+)'", form)]
    hidden = dict(re.findall(r"<input type='hidden' name='([a-z]+)' value='([^']*)'", form))
    return form, knoppen, hidden


def test_een_keuzeknop_draagt_zowel_de_actie_als_het_oordeel(tmp_path):
    """DE BUG: er stonden vier losse submits in één formulier — twee met `name='oordeel'` en één
    met `name='action'`. Een HTML-submit draagt alleen zijn EIGEN naam/waarde, dus die twee konden
    nooit samen in één POST: "Achieved" stuurde een oordeel zonder actie (er gebeurde niets) en
    "Confirm report" een actie zonder oordeel (validatie faalde). Er was geen klik die beide droeg.

    Deze test kijkt naar wat ÉÉN knop verstuurt, want dat was precies wat ontbrak."""
    from nooch_village.views.rapport import render_projectrapport
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    for naam, html in (("kaart", P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")),
                       ("route", render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK"))):
        form, knoppen, _ = _knoppen_in_de_balk(html)
        assert ("action", "verslag_bevestig_behaald") in knoppen, naam
        assert ("action", "verslag_bevestig_niet_behaald") in knoppen, naam
        # geen losse oordeel-knop meer, en geen aparte Confirm die de splitsing veroorzaakte
        assert not [k for k in knoppen if k[0] == "oordeel"], (naam, knoppen)
        assert "value='verslag_bevestig'>" not in form, naam


def test_een_enkele_post_legt_het_oordeel_vast_en_bevestigt(tmp_path):
    """Wat de knop verstuurt, moet de server in ÉÉN verzoek afmaken: oordeel opslaan én het concept
    tot document maken. Simuleert precies wat een browser stuurt bij één klik — de knopwaarde plus
    de hidden inputs, meer niet."""
    dd, st = _st(tmp_path)
    for actie, verwacht in (("verslag_bevestig_behaald", "behaald"),
                            ("verslag_bevestig_niet_behaald", "niet_behaald")):
        pid = _afgesloten(dd, st, doc="oud document")
        concept = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
        _, msg = cockpit2.dispatch(dd, actie, {"pid": [pid], "next": ["/"]}, username="guest")
        assert not cockpit2.is_weigering(msg), (actie, msg)
        st2 = cockpit2._Stores(dd)
        assert st2.projects.get(pid)["resultaat"] == verwacht          # vastgelegd
        assert st2.project_docs.read(pid) == concept                   # én bevestigd
        assert st2.project_docs.concept(pid) == {}                     # niets blijft wachten


def test_zonder_wachtend_concept_een_nette_weigering(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Leeg", "human", status="queued", done_when="af")
    _, msg = cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": ["/"]},
                               username="guest")
    assert cockpit2.is_weigering(msg), msg


def test_het_formulier_stuurt_precies_een_next(tmp_path):
    """`hid()` draagt csrf, pid ÉN next; de balk voegde er nóg een toe. Twee gelijknamige inputs
    versturen allebei — de eerste wint en de tweede is ruis die bij de volgende wijziging gaat
    afwijken."""
    from nooch_village.views.rapport import render_projectrapport
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    for naam, html in (("kaart", P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")),
                       ("route", render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK"))):
        form, _, _ = _knoppen_in_de_balk(html)
        assert form.count("name='next'") == 1, (naam, form.count("name='next'"))
        assert form.count("name='csrf'") == 1 and form.count("name='pid'") == 1, naam
