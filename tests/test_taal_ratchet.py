"""Systeemoutput is Engels, en blijft dat (27 september 2026; verbreed 2 oktober 2026).

VERBREED OP 2 OKTOBER 2026. De regel is nu "systeemoutput is Engels, mens-op-mens-tekst mag
Nederlands" (docs/CONVENTIES.md), en die geldt niet alleen voor views. De scan liep tot dan over
`views/` + twee helpers en sloeg twee dingen over die onder de nieuwe regel geen uitzondering meer
zijn: DE DATA (seed-teksten, skill-labels, gezaaide pagina's — die schrijft het systeem) en
LOGREGELS ("alles, tenzij Stefan het zelf uitzondert", en logs zijn niet uitgezonderd). Nu: ALLE
modules onder `nooch_village/`, logregels mee. De bestaande schuld (2202 woordtreffers in 165
bestanden, zie docs/taalschuld_2026-10-02.md) staat hieronder als plafond per bestand en wordt NIET
in één ronde vertaald: hij wacht op Stefans prioritering. Wat deze toets wél doet: er komt niets bij.

Wat volgt is de oorspronkelijke kop, met de twee vervallen uitzonderingen doorgestreept.

DE MELDING WAS TWEE GEVALLEN — "Werkoverleg"/"Roloverleg" in de zijbalk en een
accountability-melding in het Roloverleg — maar dat waren symptomen. Een scan over alle
user-facing strings gaf er 121 in 12 bestanden, waarvan een heel scherm (`views/vangst.py`, 22
strings) volledig Nederlands was.

DEZE TOETS IS EEN RATCHET, en hij werkt zoals `test_ui_no_inline_style.py`: per bestand een
PLAFOND dat alleen omlaag mag. Een nieuw Nederlands zinnetje in een view laat de telling stijgen
en maakt hem rood; een bestand dat nog niet in de tabel staat krijgt plafond 0, dus een NIEUWE
view kan dit gat niet opnieuw openen. Ruim je schuld op bij een view die je toch aanraakt, verlaag
dan het plafond — monotone daling, geen losse opruimronde (CLAUDE.md).

WAT HIJ NIET SCANT, en waarom dat geen gat is:

  * COMMENTAAR EN DOCSTRINGS. Die zijn in dit dorp bewust Nederlands ("Nederlandse comments/logs
    zijn prima", CLAUDE.md). Commentaar staat niet in de AST en docstrings worden herkend en
    overgeslagen — een scan op de ruwe tekst zou hier 90% ruis geven.
  * LOSSE WOORDEN ZONDER SPATIE. `'dagen'`, `'fout'`, `'verplicht'`: dat zijn sleutels en
    enum-waarden, geen zinnen. Een zin die een mens leest heeft een spatie.
  * INGEBEDDE JAVASCRIPT en CSS. Daar zit Nederlands COMMENTAAR in, en dat mag.
  * ~~LOGREGELS~~ — vervallen op 2 oktober 2026: logregels tellen mee.
  * ~~DE DATA~~ — vervallen op 2 oktober 2026: wat het systeem schrijft is systeemoutput, ook als
    het in een seed of een gezaaide pagina staat. Het blijft wel een BRON-scan (geen gerenderde
    HTML), dus tekst die een mens invulde wordt nooit geteld.
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

#: Woorden die Nederlands zijn en GÉÉN Engels woord. "door", "over", "van", "men", "die" en "of"
#: staan er bewust niet in: die zijn in beide talen geldig en zouden vals alarm geven.
NL_WOORDEN = """
niet geen wordt worden zijn deze alleen maar omdat waarom hier welke naar voor tussen zodat nog
ook wel werd heeft hebben kunnen moeten mogen staat gaat komt maakt toont opslaan bewerken
verwijderen toevoegen aanmaken wijzigen annuleren sluiten openen zoeken kiezen overleg gebruiker
wachtwoord mislukt gelukt opgeslagen verwijderd aangemaakt bijgewerkt ongeldig verplicht
ontbreekt bestaat cirkel vandaag gisteren morgen dagen maand volgende vorige nieuwe oude eerste
laatste minder groot klein slecht graag samen bijvoorbeeld daarna daarom echter verder misschien
natuurlijk opnieuw soms tenzij toch vaak weinig zelfs zonder gevangen hierboven hieronder typ
""".split()
_RE = re.compile(r"\b(" + "|".join(sorted(NL_WOORDEN)) + r")\b", re.I)

#: PLAFOND PER BESTAND — alleen omlaag. Wat er nu nog staat is grotendeels ruis die de filters
#: niet vangen (klassenamen als `msg-terug flink`, logregels, en de Nederlandse systeemprompt van
#: Noochie, die geen interface is maar een instructie aan een model). Een bestand dat hier niet
#: staat heeft plafond 0.
PLAFOND = {
    # GEGENEREERD op 2 oktober 2026 uit de scan (laag C). Geen uitzonderingen: ook `i18n.py`
    # (vertaaltabel), `arch_map.py` (genereert ontwikkelaarsdocs) en `demos/` staan er gewoon in —
    # uitzonderen is Stefans besluit, niet dat van de code. Een getal mag alleen omlaag.
    "afslank_afhankelijkheden.py": 5,
    "afslank_wezen.py": 7,
    "afslanken.py": 35,
    "ai_tasks.py": 4,
    "arch_map.py": 27,
    "artefacts.py": 10,
    "assignments.py": 9,
    "attachments.py": 1,
    "auth.py": 2,
    "backfill.py": 16,
    "biweekly_report.py": 17,
    "board_loop.py": 1,
    "bron_ophalen.py": 5,
    "cert_register.py": 10,
    "checklist_vorm.py": 4,
    "citeerbaar.py": 7,
    "claim_classify.py": 10,
    "claim_oordeel.py": 18,
    "claims_board.py": 15,
    "claims_context.py": 11,
    "claims_db.py": 11,
    "claims_labels.py": 2,
    "claims_modelpas.py": 35,
    "claims_substantiatie.py": 22,
    "claims_verify.py": 6,
    "cli.py": 92,
    "co2.py": 1,
    "cockpit2.py": 99,
    "coherence.py": 2,
    "collector.py": 4,
    "copy_stack.py": 2,
    "copycheck.py": 21,
    "dagcyclus.py": 6,
    "decision_sheets.py": 2,
    "definitions.py": 34,
    "deliverable_store.py": 5,
    "demos/analysis.py": 25,
    "demos/governance_demos.py": 25,
    "demos/ops.py": 22,
    "discovery_board.py": 8,
    "dm_samenvoegen.py": 7,
    "doelen.py": 3,
    "domeinen.py": 10,
    "draaistaat.py": 10,
    "escalation_router.py": 18,
    "evidence_ledger.py": 5,
    "feedback.py": 6,
    "founder_kaart.py": 8,
    "gap_classifier.py": 5,
    "gap_ledger.py": 4,
    "giphy.py": 4,
    "governance.py": 30,
    "governance_examples.py": 11,
    "governance_review.py": 18,
    "grounding.py": 3,
    "human_inbox.py": 11,
    "i18n.py": 39,
    "inbox/__main__.py": 70,
    "inbox_actions.py": 50,
    "inhabitant.py": 18,
    "inoreader_ingest.py": 4,
    "insight.py": 3,
    "intent.py": 1,
    "kennis_embeddings.py": 6,
    "kennis_migrate.py": 1,
    "kennisbank.py": 40,
    "key_audit.py": 6,
    "keyword_measure.py": 2,
    "keyword_nominations.py": 1,
    "leesextract.py": 2,
    "legal_signaal.py": 3,
    "library.py": 4,
    "linkbuilding.py": 4,
    "llm.py": 13,
    "llm_keuze.py": 24,
    "materiaal_memo.py": 60,
    "maturity.py": 4,
    "metric_schema.py": 1,
    "metrics.py": 2,
    "mission.py": 2,
    "ngram_correlate.py": 1,
    "noochie_kanaal.py": 7,
    "noochie_memo.py": 57,
    "observations.py": 2,
    "orphan_report.py": 5,
    "park_klep.py": 7,
    "people.py": 1,
    "personas.py": 1,
    "pinboard.py": 1,
    "project_items.py": 15,
    "projects.py": 1,
    "puls_wacht.py": 9,
    "role_proposals.py": 84,
    "role_rhythm.py": 9,
    "roles.py": 16,
    "roloverleg.py": 17,
    "rugzak.py": 7,
    "safe_fetch.py": 14,
    "seeds.py": 50,
    "signaal.py": 1,
    "site_audit.py": 19,
    "skill_labels.py": 12,
    "skill_links.py": 3,
    "skill_match.py": 10,
    "skill_meta.py": 6,
    "skills.py": 56,
    "skills_catalog.py": 3,
    "skills_impl/cert_evidence.py": 20,
    "skills_impl/claim_evidence.py": 3,
    "skills_impl/claims_check.py": 20,
    "skills_impl/claims_site_scan.py": 41,
    "skills_impl/epo_patents.py": 8,
    "skills_impl/escaleer.py": 6,
    "skills_impl/google_patents.py": 4,
    "skills_impl/gsc.py": 13,
    "skills_impl/haal_pagina.py": 11,
    "skills_impl/keywords_everywhere.py": 5,
    "skills_impl/library_skills.py": 7,
    "skills_impl/linkbuilding.py": 1,
    "skills_impl/mobiel_audit.py": 22,
    "skills_impl/openalex.py": 12,
    "skills_impl/projectverzoek.py": 5,
    "skills_impl/regulation_watch.py": 21,
    "skills_impl/semantic_scholar.py": 6,
    "skills_impl/serpapi_trends.py": 2,
    "skills_impl/shopify_sales.py": 6,
    "skills_impl/site_health.py": 2,
    "skills_impl/tegenspraak.py": 3,
    "skills_impl/trends.py": 10,
    "skills_impl/trends_categorie.py": 2,
    "skills_impl/voorstel.py": 3,
    "skills_impl/web_zoek.py": 23,
    "skills_impl/weten_we_dit_al.py": 1,
    "skills_naar_links.py": 10,
    "skillset.py": 2,
    "sluitronde.py": 25,
    "systeemtaal.py": 4,
    "triage_rol.py": 45,
    "util.py": 2,
    "vastgelopen_route.py": 5,
    "verslag.py": 11,
    "views/checklists.py": 1,
    "views/messages.py": 2,
    "views/metrics.py": 4,
    "views/navpaneel.py": 2,
    "views/noochie.py": 3,
    "views/search.py": 3,
    "views/vangst.py": 4,
    "village.py": 32,
    "voorstel_mutatie.py": 8,
    "voorstel_opruiming.py": 1,
    "waarde_audit.py": 81,
    "web_read.py": 1,
    "weekmemo.py": 38,
    "werkoverleg.py": 2,
    "wiki.py": 2,
    "wiki_bronnen.py": 5,
    "wiki_claims_policy.py": 4,
    "wiki_domein.py": 22,
    "wiki_how_we_decide.py": 4,
    "wiki_seed.py": 5,
    "wizard.py": 7,
    "zelf_verwerking.py": 35,
}


def _docstrings(tree) -> set:
    uit = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = getattr(n, "body", None)
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
               and isinstance(b[0].value.value, str):
                uit.add(id(b[0].value))
    return uit


def _overslaan(v: str) -> bool:
    """Zie de kop: wat géén user-facing zin is."""
    if " " not in v.strip():
        return True                                   # sleutel of enum-waarde
    if "function(" in v or "document." in v or "querySelector" in v:
        return True                                   # ingebedde JS met NL commentaar
    if ":root{" in v or "--ink:" in v or v.lstrip().startswith("/*"):
        return True                                   # CSS met NL commentaar
    return False


def _bestanden() -> list[pathlib.Path]:
    # ALLE MODULES (2 oktober 2026), niet meer alleen `views/` + twee helpers.
    return sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def treffers(pad: pathlib.Path) -> list[tuple[int, str, str]]:
    tree = ast.parse(pad.read_text())
    docs = _docstrings(tree)
    uit = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
            continue
        if id(n) in docs or _overslaan(n.value):
            continue
        for m in _RE.finditer(n.value):
            uit.append((n.lineno, m.group(1), n.value.strip()[:70]))
    return uit


def _telling() -> dict[str, int]:
    uit = {}
    for p in _bestanden():
        n = len(treffers(p))
        if n:
            uit[str(p.relative_to(ROOT))] = n
    return uit


# ══ De ratchet ═══════════════════════════════════════════════════════════════
def test_geen_bestand_boven_zijn_plafond():
    """Een nieuw Nederlands zinnetje laat de telling stijgen en maakt dit rood."""
    te_hoog = {f: (n, PLAFOND.get(f, 0)) for f, n in _telling().items()
               if n > PLAFOND.get(f, 0)}
    assert not te_hoog, f"boven het plafond (nu, plafond): {te_hoog}"


def test_een_nieuw_bestand_heeft_plafond_nul():
    """DE HELE POINTE voor de toekomst: wie een view toevoegt hoeft niets te doen om gedekt te
    zijn. Staat hij niet in de tabel, dan is zijn plafond 0."""
    onbekend = {f for f in _telling() if f not in PLAFOND}
    assert not onbekend, f"nieuw bestand met Nederlandse UI-tekst: {onbekend}"


def test_het_plafond_daalt_monotoon():
    """Zakt een bestand onder zijn plafond, dan hoort dat plafond mee te zakken — anders is er
    ruimte om er stilletjes weer iets bij te zetten."""
    telling = _telling()
    te_ruim = {f: (telling.get(f, 0), p) for f, p in PLAFOND.items() if telling.get(f, 0) < p}
    assert not te_ruim, f"plafond te ruim, verlaag het (nu, plafond): {te_ruim}"


# ══ De twee gemelde gevallen, met naam ═══════════════════════════════════════
def test_de_zijbalk_noemt_de_overleggen_in_het_engels():
    """Ze heetten "Werkoverleg"/"Roloverleg" terwijl de pagina's erachter al "Tactical meeting"
    en "Governance meeting" heten — niet alleen inconsistent met de interface, maar met de pagina
    waar ze heen wijzen."""
    from nooch_village.cockpit2_util import overleg_items
    h = overleg_items("mother_earth__nooch")
    assert "Werk" not in h and "Rol&shy;overleg" not in h
    assert "Tactical" in h and "Governance" in h


def test_de_accountability_melding_is_engels():
    """EERST DE MELDING, TOEN DE REGEL. In deze ronde is alleen de melding vertaald, met de
    Nederlandse -en-vormeis er nog onder — en dat was half werk: een Engelse zin die een
    Nederlandse vormeis beschrijft. De regel zélf is daarna Engels geworden (de gerund), en deelt
    nu één implementatie met `governance_review._ing_start`.

    Wat deze toets bewaakt is onveranderd: er staat hier geen Nederlands meer.
    `tests/test_accountability_vorm.py` toetst de regel zelf."""
    import inspect

    from nooch_village import roloverleg
    bron = inspect.getsource(roloverleg)
    assert "accountability begint niet met de -en-vorm" not in bron
    assert "should start with an -ing verb form" in bron


# ══ De scanner zelf ══════════════════════════════════════════════════════════
def test_de_scanner_vindt_nederlands_als_het_er_staat(tmp_path):
    """EEN RATCHET DIE NIETS VINDT IS GEEN RATCHET. Deze toets voert er zelf een in."""
    p = tmp_path / "nep.py"
    p.write_text('x = "<p>Deze regel is niet Engels</p>"\n')
    assert len(treffers(p)) >= 2


def test_hij_negeert_commentaar_en_docstrings(tmp_path):
    """Die zijn hier bewust Nederlands (CLAUDE.md). Zou de scan ze meenemen, dan is hij ruis."""
    p = tmp_path / "nep.py"
    p.write_text('"""Deze docstring is niet Engels."""\n# En dit commentaar ook niet.\nx = "ok"\n')
    assert treffers(p) == []


def test_hij_negeert_losse_sleutelwoorden(tmp_path):
    p = tmp_path / "nep.py"
    p.write_text('STATUS = {"verplicht": 1, "dagen": 2}\n')
    assert treffers(p) == []


def test_hij_negeert_ingebedde_javascript(tmp_path):
    p = tmp_path / "nep.py"
    p.write_text('JS = "<script>function(){ /* deze regel is niet Engels */ }</script>"\n')
    assert treffers(p) == []


# ══ De verbreding van 2 oktober 2026 ═════════════════════════════════════════
def test_een_logregel_telt_nu_mee(tmp_path):
    """"Logregels mogen Nederlands" is vervallen: wat het systeem schrijft, is systeemoutput."""
    p = tmp_path / "nep.py"
    p.write_text('log.info("bron-check %s mislukt, niet opnieuw geprobeerd", url)\n')
    assert len(treffers(p)) >= 2


def test_de_scan_dekt_ook_modules_buiten_views():
    """Het zaad, de CLI, de memo's: systeemoutput staat niet alleen in views."""
    namen = {str(p.relative_to(ROOT)) for p in _bestanden()}
    for module in ("wiki_seed.py", "cli.py", "cockpit2.py", "views/bom.py"):
        assert module in namen, module
