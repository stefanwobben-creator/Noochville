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
    cockpit2.dispatch(dd, "verslag_bevestig", {"pid": [pid], "oordeel": ["behaald"],
                                               "toelichting": ["Alles rond."], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    doc = st2.project_docs.read(pid)
    assert "oud document" not in doc and "Alles rond." in doc
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
    assert "Report says" in frag and "Twee gaten open" in frag
    assert "Checklist says" in frag and "achieved" in frag


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
    assert "Niet vastgelegd" in st2.project_docs.read(pid)
    assert st2.project_docs.concept(pid) == {}


def test_een_nee_kan_net_zo_makkelijk_als_een_ja(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    cockpit2.dispatch(dd, "verslag_bevestig", {"pid": [pid], "oordeel": ["niet_behaald"],
                                               "toelichting": ["De leverancier haakte af."],
                                               "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["resultaat"] == "niet_behaald"
    assert "niet behaald" in st2.project_docs.read(pid).lower()


def test_learnings_zijn_optioneel(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    cockpit2.dispatch(dd, "verslag_bevestig", {"pid": [pid], "oordeel": ["behaald"], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["resultaat"] == "behaald"
    assert "## Learnings" not in st2.project_docs.read(pid)


def test_een_onbekend_oordeel_schrijft_niets(tmp_path):
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    _, msg = cockpit2.dispatch(dd, "verslag_bevestig", {"pid": [pid], "oordeel": ["misschien"],
                                                        "next": ["/"]}, username="guest")
    assert cockpit2.is_weigering(msg)
    assert cockpit2._Stores(dd).project_docs.read(pid) == "oud document"


# ── het oordeel vervangt dat van het model, zonder de rest te verliezen ──────
def test_het_menselijke_oordeel_vervangt_dat_van_het_model():
    c = "## Goal\nDoel.\n\n## What happened\nDingen.\n\n## Result\nNot achieved. Twee gaten."
    n = met_result(c, "behaald", "Toch af na de review.", "Eerder om review vragen.")
    assert "## Goal\nDoel." in n and "Dingen." in n          # geen informatieverlies
    assert "Twee gaten" not in n                             # het voorstel maakt plaats
    assert "**Behaald.** Toch af na de review." in n         # verslagtaal = Nederlands
    assert "## Leringen\nEerder om review vragen." in n


def test_zonder_result_kop_komt_het_blok_er_gewoon_onder():
    """De modelloze variant heeft wél een Result-kop, maar een handmatig bijgewerkt concept
    misschien niet. Dan hoort het oordeel er alsnog bij te komen."""
    n = met_result("## Goal\nAlleen dit.", "behaald", "Klaar.")
    assert "Alleen dit." in n and "**Behaald.** Klaar." in n


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
    getoond = re.findall(r"class='einddoc-sigv'>([^<]*)", frag)
    assert any("not achieved" in g for g in getoond), getoond      # scherm blijft Engels
    assert not any(NIET_BEHAALD in g for g in getoond), f"opslagsleutel getoond: {getoond}"
    assert f"value='{NIET_BEHAALD}'" in frag                 # als formulierwaarde juist wél


# ── cluster 1: de suggestie doet het voorwerk ────────────────────────────────
def test_de_velden_zijn_voorgevuld_uit_het_concept(tmp_path):
    """DE ANTI-HUISWERK-BELOFTE. Een leeg veld laat de mens het werk doen dat de assembler net al
    deed: de analyse staat al in de wall én in het concept. Voorinvullen maakt van de vraag een
    aanvulling in plaats van een opstel."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    store = cockpit2._Stores(dd).project_docs
    c = store.concept(pid)
    store.write_concept(pid,
                        "## Doel\nx\n\n## Resultaat\n**Niet behaald.** Twee van drie reageerden.\n\n"
                        "## Leringen\nMonsters meteen meevragen.",
                        bronnen=c.get("bronnen") or [], voorzet="niet_behaald")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    # `_field` rendert met DUBBELE aanhalingstekens; de rest van de view met enkele. Op het
    # attribuut matchen in plaats van op een geciteerde string maakt de test daar ongevoelig voor.
    assert 'name="toelichting" value="Twee van drie reageerden."' in frag
    assert "Monsters meteen meevragen." in frag               # learnings voorgevuld
    assert "**Niet behaald.**" not in frag.split("einddoc-rform")[1]  # het label niet geëchood


def test_het_oordeel_wordt_niet_voorgeselecteerd(tmp_path):
    """GEEN DEFAULT OP DE JA/NEE. De toelichting en de leringen zijn een concept om bij te schaven
    — daar scheelt voorinvullen echt werk. Het oordeel is iets anders: dat is de ene beslissing die
    de mens actief moet nemen, en élke default duwt hem naar een antwoord zodra de twee signalen
    botsen. Ze staan eronder; hij kiest."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="", items=(("A", False),))
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "checked" not in frag.split("einddoc-rform")[1].split("</form>")[0]
    assert "value='behaald'" in frag and "value='niet_behaald'" in frag


def test_bevestigen_zonder_keuze_schrijft_niet(tmp_path):
    """Sinds de radio's leeg starten is dit bereikbaar: klikken op Confirm zonder te kiezen. Stil
    doorlaten zou het verslag bevestigen MÉT het modeloordeel erin, alsof de mens dat had
    onderschreven — precies wat de lege radio voorkomt."""
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="oud document")
    _, msg = cockpit2.dispatch(dd, "verslag_bevestig", {"pid": [pid], "next": ["/"]},
                               username="guest")
    assert cockpit2.is_weigering(msg), msg
    assert "Skip" in msg
    st2 = cockpit2._Stores(dd)
    assert st2.project_docs.read(pid) == "oud document"
    assert (st2.project_docs.concept(pid).get("tekst") or "").strip()   # concept blijft wachten


def test_het_verslag_is_nederlands_en_het_scherm_engels(tmp_path):
    """Twee lezers, één sleutel: de cockpit-chrome (Engels, i18n fase 1) en de orgkennis
    (Nederlands, de taal waarin hier gewerkt wordt)."""
    from nooch_village.project_verslag import label_voor
    assert label_voor("behaald") == "achieved"               # scherm
    assert label_voor("behaald", "nl") == "behaald"          # verslag
    dd, st = _st(tmp_path)
    pid = _afgesloten(dd, st, doc="")
    doc = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
    assert "## Doel" in doc and "## Wat er gebeurde" in doc and "## Resultaat" in doc
    assert "## Goal" not in doc and "## What happened" not in doc


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
    assert "GEEN kop per taak" in _PROMPT
    assert "Niet onderzocht:" in _PROMPT                      # één zin, niet een kopje per taak


def test_het_doeltype_staat_in_de_prompt():
    """Een beoordelingsproject is behaald zodra er een gegrond oordeel ligt — ook een "nee".
    Zonder dit leest de assembler elk "nee" als een mislukking."""
    from nooch_village.project_verslag import _PROMPT
    assert "BEOORDELINGSPROJECT" in _PROMPT and "ook als dat oordeel 'nee' is" in _PROMPT


def test_de_assemblage_staat_op_de_hoog_inzet_ladder():
    """Dit wordt orgkennis zodra een mens het bevestigt. Een zwakke samenvatting die je bevestigt
    is erger dan geen samenvatting: je kunt hem daarna niet meer wantrouwen."""
    from nooch_village.llm_keuze import HOOG_INZET, ladder_voor
    assert "verslag_assemblage" in HOOG_INZET
    assert (ladder_voor("verslag_assemblage") or "").startswith("anthropic:claude-sonnet")
