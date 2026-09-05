"""Eén assembler, twee ingangen — en een terugval die je kunt vinden.

De rapportgeneratie had TWEE paden. Het afsluit-pad draaide de nieuwe assembler; de knop
"Refresh from deliverables" op /rapport draaide nog de oude per-taak-synthese uit
`inhabitant.synthesize_einddocument`. Dezelfde knop op hetzelfde scherm gaf dus een ander soort
document: Engels, een kop per taak, en "Niet onderzocht — geen gegrond resultaat" onder koppen waar
wél iets was gebeurd.

Gemeten op 310 productiedocumenten vóór de fix: mediaan 6 koppen (max 19), 253 kopblokken met
"niet onderzocht", 64 (bijna) leeg.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.project_verslag import bronnen_van, deliverable_blokken, stel_samen

ROLE = "mother_earth__nooch__brand_visual_designer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _project(dd, st, *, doc=""):
    pid = st.projects.create(ROLE, "Eén pad", "human", status="queued", done_when="af")
    st.projects.start(pid)
    cl = st.projects.checklist_add(pid, "tasks")["id"]
    st.projects.check_add(pid, cl, "Eerste stap")
    if doc:
        cockpit2._Stores(dd).project_docs.write(pid, doc)
    return pid


# ── één assembler ────────────────────────────────────────────────────────────
def test_de_knop_draait_de_nieuwe_assembler(tmp_path):
    """Niet meer de oude per-taak-synthese: hetzelfde geraamte als het afsluit-pad."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="# Oud\n\nEr stond al iets.")
    cockpit2.dispatch(dd, "proj_regen_doc", {"pid": [pid], "next": ["/"]}, username="guest")
    concept = cockpit2._Stores(dd).project_docs.concept(pid)
    assert (concept.get("tekst") or "").strip()
    assert "## Doel" in concept["tekst"] and "## Wat er gebeurde" in concept["tekst"]
    # "## Result" is een SUBSTRING van "## Resultaat" — op de Engelse kop matchen zou hier altijd
    # slagen. Toets op de Engelse kop mét regeleinde.
    assert "## Result\n" not in concept["tekst"]              # Engels geraamte is weg
    assert "## What happened" not in concept["tekst"]


def test_de_knop_schrijft_een_concept_en_niet_het_document(tmp_path):
    """Dezelfde regel als bij het afsluiten: alleen een expliciete bevestiging vervangt de
    canonieke tekst. "Opnieuw genereren" is een voorstel, en een voorstel dat zichzelf meteen
    doorvoert is geen voorstel."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="# Oud\n\nDeze tekst mag niet verdwijnen.")
    _, msg = cockpit2.dispatch(dd, "proj_regen_doc", {"pid": [pid], "next": ["/"]},
                               username="guest")
    assert not cockpit2.is_weigering(msg), msg
    assert "confirm" in msg.lower()
    assert "mag niet verdwijnen" in cockpit2._Stores(dd).project_docs.read(pid)


def test_de_oude_synthese_wordt_niet_meer_door_de_cockpit_aangeroepen():
    """De twee paden mochten niet naast elkaar blijven bestaan. `inhabitant.synthesize_einddocument`
    leeft nog voor de DAEMON-puls (vier aanroepen, en die leest deliverables tijdens het werk);
    de cockpit raakt hem niet meer aan."""
    import pathlib
    src = pathlib.Path("nooch_village/cockpit2.py").read_text(encoding="utf-8")
    regels = [r for r in src.splitlines()
              if "synthesize_einddocument" in r and not r.strip().startswith("#")]
    assert regels == [], regels


def test_beide_ingangen_lezen_dezelfde_bronnen(tmp_path):
    """Anders weet het ene pad meer dan het andere, en krijg je twee verschillende verslagen voor
    hetzelfde project — precies de situatie die deze PR opheft."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, doc="# Werk\n\nEen echt rapport met inhoud.")
    cockpit2.dispatch(dd, "proj_regen_doc", {"pid": [pid], "next": ["/"]}, username="guest")
    via_knop = cockpit2._Stores(dd).project_docs.concept(pid)["bronnen"]
    cockpit2._Stores(dd).project_docs.clear_concept(pid)
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    via_afsluiten = cockpit2._Stores(dd).project_docs.concept(pid)["bronnen"]
    assert via_knop == via_afsluiten, (via_knop, via_afsluiten)


# ── de deliverables gingen niet verloren ─────────────────────────────────────
def test_deliverables_zijn_een_bron_van_de_nieuwe_assembler():
    """De oude synthese las ze (652 deliverables over 197 van de 373 projecten). Ze niet overnemen
    zou betekenen dat het nieuwe pad MINDER weet dan het oude — dan is "vervangen" in werkelijkheid
    informatieverlies."""
    assert "de opgeleverde deliverables (2)" in bronnen_van({"scope": "x"}, "", ["a", "b"])
    c = stel_samen({"scope": "x"}, "", reason=None, deliverables=["Rapport A"])
    assert c is not None and "de opgeleverde deliverables (1)" in c.bronnen


def test_deliverables_lezen_faalt_zacht_maar_luid(caplog):
    """Een verslag zonder deliverables is nog steeds een verslag; een kapotte store mag hem niet
    tegenhouden. Maar wél gelogd — stil wegvallen leest als "er waren er geen"."""
    class Stuk:
        def for_project(self, pid):
            raise RuntimeError("store stuk")
    with caplog.at_level("WARNING"):
        assert deliverable_blokken(Stuk(), "p1") == []
    assert any("VERSLAG_DELIVERABLES_FAIL" in r.message for r in caplog.records)


def test_zonder_store_gewoon_leeg():
    assert deliverable_blokken(None, "p1") == []


# ── de terugval is vindbaar ──────────────────────────────────────────────────
def test_een_terugval_op_een_hoog_inzet_site_wordt_luid_gelogd(caplog, monkeypatch):
    """OP PRODUCTIE DRAAIDE ÉLKE HOOG-INZET-CALL ACHT DAGEN OP DE GOEDKOPE STAART zonder dat iemand
    het zag: elke trede logt zijn eigen falen, maar dat verdrinkt, en je merkt het pas als je per
    document naar de herkomst-badge kijkt. Deze regel maakt het patroon met één grep vindbaar.

    (De oorzaak zelf was geen code: het Anthropic-krediet was op — HTTP 400 "credit balance is too
    low". Dat kan een test niet repareren; hij zorgt dat het de volgende keer opvalt.)"""
    from nooch_village import llm
    monkeypatch.setattr(llm, "_ladder",
                        lambda: [("anthropic", "claude-sonnet-5"), ("mistral", "m-small")])
    monkeypatch.setattr(llm, "_in_cooldown", lambda tier, **k: False)

    def _call(vendor, model, prompt, **k):
        if vendor == "anthropic":
            raise RuntimeError("credit balance is too low")
        return "antwoord van de staart"
    monkeypatch.setattr(llm, "_call_tier", _call)
    with caplog.at_level("WARNING"):
        llm.reason("iets", call_site="verslag_assemblage")
    regels = [r.message for r in caplog.records if "HOOG_INZET_TERUGVAL" in r.message]
    assert regels, [r.message for r in caplog.records]
    assert "verslag_assemblage" in regels[0] and "sonnet" in regels[0]


def test_een_terugval_op_een_gewone_site_is_geen_waarschuwing(caplog, monkeypatch):
    """Alleen waar het OORDEEL telt. Op een triage-site is goedkoop de juiste keuze, en dan is een
    waarschuwing ruis die de echte verdringt."""
    from nooch_village import llm
    monkeypatch.setattr(llm, "_ladder",
                        lambda: [("anthropic", "claude-sonnet-5"), ("mistral", "m-small")])
    monkeypatch.setattr(llm, "_in_cooldown", lambda tier, **k: False)
    monkeypatch.setattr(llm, "_call_tier",
                        lambda vendor, model, prompt, **k: None if vendor == "anthropic" else "ok")
    with caplog.at_level("WARNING"):
        llm.reason("iets", call_site="triage_spanning")
    assert not [r for r in caplog.records if "HOOG_INZET_TERUGVAL" in r.message]
