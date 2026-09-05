"""Het verslag stelt zichzelf samen bij afsluiting — als CONCEPT, zonder poort.

Drie dingen die deze tests bewaken, elk met een reden die uit de meting op productie komt:

1. **Het bestaande document overleeft.** `ProjectDocStore` overschrijft atomisch en houdt geen
   versies. Een assemblage die meteen over het document heen schrijft, wist de werkoutput die de
   puls erin zette — onherroepelijk. Het concept wacht dus ernaast.
2. **Er is geen nieuwe poort.** We hebben net `dod_poort` weggehaald; een assemblage die kan
   blokkeren zou daar een nieuwe van maken met een ander gezicht. Mislukt hij, dan is het project
   gewoon afgesloten.
3. **De kaart liegt niet.** Onbevestigde modeltekst als essentie tonen zou de kaart weer laten
   zeggen dat er een verslag ligt dat er nog niet ligt — hetzelfde als de sjabloonzin bij de seeds.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.project_verslag import (BEHAALD, NIET_BEHAALD, ONBEKEND, bronnen_van, stel_samen,
                                   voorzet_result)
from nooch_village.views import projects as P
from nooch_village.views.rapport import render_projectrapport

ROLE = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _project(dd, st, *, doc="", items=(), gesprek=()):
    pid = st.projects.create(ROLE, "Hemp canvas bij een tweede leverancier", "human",
                             status="queued", done_when="Er ligt een shortlist van drie.")
    st.projects.start(pid)
    if items:
        # `checklist_add` geeft een dict terug en `check_add` een bool — niet de id's. De id's
        # komen dus uit het project zelf; ze raden zou de helper stil laten falen (en dat deed hij).
        cl = st.projects.checklist_add(pid, "Stappen")
        cid = cl["id"]
        for tekst, _ in items:
            assert st.projects.check_add(pid, cid, tekst), tekst
        vers = st.projects.get(pid)
        rij = next(c for c in vers["checklists"] if c["id"] == cid)["items"]
        for (tekst, af), it in zip(items, rij):
            if af:
                assert st.projects.check_toggle(pid, cid, it["id"]), tekst
    for tekst in gesprek:
        cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "text": [tekst], "author": ["human:"],
                                            "next": ["/"]}, username="guest")
    if doc:
        cockpit2._Stores(dd).project_docs.write(pid, doc)
    return pid


# ── de voorzet: deterministisch, en een "nee" mag ────────────────────────────
def test_voorzet_alles_af_is_waarschijnlijk_behaald():
    p = {"checklists": [{"items": [{"text": "a", "done": True}, {"text": "b", "done": True}]}]}
    soort, reden = voorzet_result(p)
    # De reden is Engels: hij reist naar de prompt én naar het scherm. De SLEUTEL blijft
    # Nederlands, want die wordt opgeslagen en vergeleken.
    # De redenen zijn Nederlands sinds het verslag Nederlands is: ze reizen naar de
    # prompt én naar de verslagtekst, en beide zijn orgkennis.
    assert soort == BEHAALD and "ticked" in reden


def test_voorzet_niets_af_is_waarschijnlijk_niet_behaald():
    """Een 'nee' is net zo waardevol als een 'ja'. Zou de voorzet altijd positief zijn, dan wordt
    een mislukking stil weggezet — precies wat we vermijden."""
    p = {"checklists": [{"items": [{"text": "a", "done": False}, {"text": "b", "done": False}]}]}
    assert voorzet_result(p)[0] == NIET_BEHAALD


def test_voorzet_zegt_onbekend_in_plaats_van_te_gokken():
    half = {"checklists": [{"items": [{"text": "a", "done": True}, {"text": "b", "done": False}]}]}
    assert voorzet_result(half)[0] == ONBEKEND
    assert voorzet_result({})[0] == ONBEKEND          # geen checklist = niets om aan af te lezen


# ── provenance: alleen wat er echt is ────────────────────────────────────────
def test_bronnen_noemen_alleen_wat_bestaat():
    """Een lege checklist als bron noemen maakt de telling ("samengesteld uit N bronnen") een
    leugen — en die telling is juist waarop een mens zijn bevestiging baseert."""
    kaal = {"scope": "Iets"}
    assert bronnen_van(kaal) == ["the project definition"]
    rijk = {"scope": "Iets", "checklists": [{"items": [{"text": "a", "done": True}]}],
            "log": [{"who": "rol", "text": "gedaan"}]}
    b = bronnen_van(rijk, "een document")
    assert len(b) == 4 and "the existing end document" in b


def test_zonder_enige_bron_geen_concept():
    assert stel_samen({}, "") is None


# ── de terugval zonder model ─────────────────────────────────────────────────
def test_zonder_model_toch_een_verslag_maar_zichtbaar_soberder():
    """Fail-closed betekent hier: niets bedenken, niet niets leveren. De feiten liggen er al."""
    p = {"scope": "Shortlist", "done_when": "Drie leveranciers benaderd.",
         "checklists": [{"items": [{"text": "Leverancier A", "done": True},
                                   {"text": "Leverancier B", "done": False}]}]}
    c = stel_samen(p, "", reason=None)
    assert c is not None
    assert "## Goal" in c.tekst and "## What happened" in c.tekst and "## Result" in c.tekst
    assert "Leverancier A" in c.tekst and "Leverancier B" in c.tekst
    assert "without a language model" in c.tekst     # herkenbaar soberder, geen nep-proza


def test_een_kapot_model_blokkeert_niets():
    def stuk(*a, **k):
        raise RuntimeError("model weg")
    c = stel_samen({"scope": "Iets", "checklists": [{"items": [{"text": "a", "done": True}]}]},
                   "", reason=stuk)
    assert c is not None and "## Result" in c.tekst


# ── de afsluitflow: geen poort, document blijft ──────────────────────────────
def test_afsluiten_maakt_een_concept_naast_het_document(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="# Het werk\n\nDrie leveranciers vergeleken op prijs en herkomst.",
                   items=[("Leverancier A", True), ("Leverancier B", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["status"] == "done"
    # HET DOCUMENT IS ONGEMOEID — dit is de kern: de store kent geen versies.
    assert "Drie leveranciers vergeleken" in st2.project_docs.read(pid)
    c = st2.project_docs.concept(pid)
    assert (c.get("tekst") or "").strip()
    assert c["voorzet"] == BEHAALD and len(c["bronnen"]) >= 3


def test_afsluiten_lukt_ook_als_de_assemblage_stukgaat(tmp_path, monkeypatch):
    """GEEN NIEUWE POORT. We haalden net dod_poort weg; een assemblage die kan blokkeren zou daar
    een nieuwe van maken met een ander gezicht."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, items=[("A", True)])
    import nooch_village.project_verslag as V
    monkeypatch.setattr(V, "stel_samen", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["status"] == "done"        # afgesloten, ondanks de kapotte assembler
    assert st2.project_docs.concept(pid) == {}


def test_de_mislukking_wordt_luid_gelogd(tmp_path, monkeypatch, caplog):
    """Een assemblage die stil wegvalt leest later als "er viel niets samen te stellen" — dezelfde
    onzichtbaarheid als bij het radarsignaal dat in een `except` verdween."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, items=[("A", True)])
    import nooch_village.project_verslag as V
    monkeypatch.setattr(V, "stel_samen", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    with caplog.at_level("ERROR"):
        cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    assert any("VERSLAG_MISLUKT" in r.message for r in caplog.records), caplog.text


# ── bevestigen en bijwerken ──────────────────────────────────────────────────
def test_bevestigen_maakt_het_concept_het_document(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="oud document", items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    concept = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
    # Bevestigen vereist een oordeel sinds de radio's leeg starten: zonder keuze zou het verslag
    # het modeloordeel bevestigen alsof de mens dat onderschreef. Zie
    # test_verslag_result.test_bevestigen_zonder_keuze_schrijft_niet.
    # De keuze ÍS de bevestiging: één actie draagt oordeel én bevestiging. Zie
    # test_verslag_result.test_een_keuzeknop_draagt_zowel_de_actie_als_het_oordeel.
    cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": ["/"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    assert "## Result" in st2.project_docs.read(pid)
    assert concept.split("\n")[0] in st2.project_docs.read(pid)   # de rest van het concept bleef
    assert st2.project_docs.concept(pid) == {}          # niets meer te bevestigen


def test_bijwerken_houdt_het_onbevestigd_en_bewaart_de_provenance(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="oud document", items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    bronnen_voor = cockpit2._Stores(dd).project_docs.concept(pid)["bronnen"]
    cockpit2.dispatch(dd, "verslag_bijwerken", {"pid": [pid], "tekst": ["## Result\nmijn versie"],
                                                "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    c = st2.project_docs.concept(pid)
    assert c["tekst"] == "## Result\nmijn versie"
    assert c["bronnen"] == bronnen_voor                 # waaruit is samengesteld verandert niet
    assert st2.project_docs.read(pid) == "oud document"  # nog steeds niet bevestigd


def test_leeg_bijwerken_wist_niets(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    _, msg = cockpit2.dispatch(dd, "verslag_bijwerken", {"pid": [pid], "tekst": ["  "],
                                                         "next": ["/"]}, username="guest")
    assert cockpit2.is_weigering(msg)
    assert (cockpit2._Stores(dd).project_docs.concept(pid).get("tekst") or "").strip()


def test_bevestigen_zonder_concept_is_een_nette_weigering(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st)
    _, msg = cockpit2.dispatch(dd, "verslag_bevestig_behaald", {"pid": [pid], "next": ["/"]},
                               username="guest")
    assert cockpit2.is_weigering(msg)


# ── de schermen ──────────────────────────────────────────────────────────────
def test_de_route_toont_het_concept_met_zijn_provenance(tmp_path):
    """OF-OF, NIET ALLEBEI. Deze test eiste eerst dat het document ONDER het concept mee-rendeerde;
    dat waren twee versies van hetzelfde rapport op één pagina, en de lezer moest raden welke telt.
    Wacht er een concept, dan is dát het onderwerp — het document blijft op DATANIVEAU bestaan tot
    bevestigen het vervangt, en de pagina zegt dat met zoveel woorden.
    Zie tests/test_rapport_route.py::test_nooit_het_concept_en_het_document_tegelijk."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="oud document", items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "not confirmed yet" in html
    assert "assembled from" in html
    assert "oud document" not in html                   # niet meer mee-gerenderd
    assert "stays as it is until you confirm" in html   # maar wél benoemd
    assert "oud document" in cockpit2._Stores(dd).project_docs.read(pid)   # en nog steeds de waarheid
    assert "verslag_bevestig" in html and "verslag_bijwerken" in html


def test_de_kaart_toont_een_merkteken_maar_niet_de_onbevestigde_tekst(tmp_path):
    """De essentie blijft die van het BEVESTIGDE document. Onbevestigde modeltekst als samenvatting
    tonen is dezelfde leugen als de sjabloonzin bij de seeds."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="# Kop\n\nDit is het bevestigde werk met een echte eerste zin.",
                   items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    concept = cockpit2._Stores(dd).project_docs.concept(pid)["tekst"]
    assert "Draft report awaiting confirmation" in frag
    assert "Dit is het bevestigde werk" in frag         # de essentie van het document
    assert concept[:60] not in frag                     # niet de onbevestigde tekst


def test_zonder_schrijfrecht_geen_bevestigknop(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="")
    assert "not confirmed yet" in html                  # lezen mag
    assert "verslag_bevestig" not in html               # bevestigen niet


# ── kwaliteitsfixes uit de eerste echte assemblage op productie ──────────────
# Drie dingen die pas zichtbaar werden toen er echte concepten uitrolden. Ze staan hier als test
# omdat ze alle drie raken wat er bij BEVESTIGEN wordt opgeslagen — en dat is de canonieke tekst.

def test_de_markdown_fence_wordt_gestript_voor_opslag():
    """Het model wikkelt zijn antwoord in ```markdown. Op het scherm valt dat niet op (`_md_doc`
    stript hem), maar bij bevestigen wordt deze tekst het document — en dan bestendigt hij precies
    de opslag-rommel die in 46 van de 307 bestaande documenten zit."""
    c = stel_samen({"scope": "X", "checklists": [{"items": [{"text": "a", "done": True}]}]}, "",
                   reason=lambda *a, **k: "```markdown\n## Goal\nIets\n```")
    assert not c.tekst.startswith("```") and c.tekst.startswith("## Goal")


def test_de_voorzet_gaat_als_engels_label_de_prompt_in():
    """IDENTIFIER IS MECHANIEK, LABEL IS CONTENT. De sleutel blijft Nederlands (hij wordt
    opgeslagen en vergeleken); wat naar het model en het scherm gaat is Engels. Zonder die
    scheiding stond er letterlijk "## Result: onbekend (geen checklist om aan af te lezen)" in
    een Engels verslag — gezien op productie."""
    from nooch_village.project_verslag import label_voor
    gezien = {}

    def vang(prompt, **k):
        gezien["p"] = prompt
        return "## Goal\nx"
    # Twee bronnen, anders slaat `stel_samen` het model over (zie
    # test_alleen_de_definitie_roept_geen_model_aan) en is er geen prompt om te toetsen.
    stel_samen({"scope": "X", "log": [{"who": "rol", "text": "iets gedaan"}]}, "", reason=vang)
    # De PROMPT is Nederlands (het verslag wordt orgkennis); het SCHERM blijft Engels.
    assert "unclear" in gezien["p"]
    assert "onbekend" not in gezien["p"]              # de sleutel zelf nooit
    assert label_voor(BEHAALD) == "achieved"         # scherm
    assert label_voor(BEHAALD, "nl") == "behaald"    # verslag


def test_onbekende_voorzetsleutel_valt_niet_stil_weg():
    from nooch_village.project_verslag import label_voor
    assert label_voor("iets_nieuws") == "iets_nieuws"


def test_een_seed_document_is_geen_bron():
    """Bij 31% van de afgesloten projecten op productie is het "document" niets dan de opdracht.
    Meetellen maakt de provenance-telling onwaar; als materiaal aanbieden zette het model op een
    dwaalspoor ("an existing final document titled 'Klaar wanneer'"). De opdracht komt al binnen
    via done_when."""
    from nooch_village.projects import seed_document
    seed = seed_document("POS material created")
    assert "the existing end document" not in bronnen_van({"scope": "POS"}, seed)
    assert "the existing end document" in bronnen_van({"scope": "POS"}, "# Werk\n\nEcht werk.")


def test_de_seed_tekst_komt_niet_in_het_materiaal():
    from nooch_village.projects import seed_document
    seed = seed_document("POS material created")
    gezien = {}

    def vang(prompt, **k):
        gezien["p"] = prompt
        return "## Goal\nx"
    stel_samen({"scope": "POS", "checklists": [{"items": [{"text": "a", "done": True}]}]},
               seed, reason=vang)
    assert "De inwoner werkt dit document" not in gezien["p"]


def test_de_route_toont_de_voorzet_als_label_niet_als_sleutel(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, items=[("A", True)])
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "result: achieved" in html
    assert ">result: behaald<" not in html


def test_alleen_de_definitie_roept_geen_model_aan():
    """Met alleen een titel kan een model niets doen behalve gaten opvullen. Gemeten op productie:
    zo'n project houdt ~5 tokens materiaal over. De gestructureerde variant zegt hetzelfde,
    eerlijker, en kost niets."""
    geroepen = []
    c = stel_samen({"scope": "POS material created"}, "",
                   reason=lambda *a, **k: geroepen.append(1) or "verzonnen proza")
    assert geroepen == [], "model aangeroepen terwijl er niets te verslaan viel"
    assert c is not None and "without a language model" in c.tekst


def test_met_een_tweede_bron_wel():
    geroepen = []

    def vang(*a, **k):
        geroepen.append(1)
        return "## Goal\nx"
    stel_samen({"scope": "X", "checklists": [{"items": [{"text": "a", "done": True}]}]}, "",
               reason=vang)
    assert geroepen == [1]
