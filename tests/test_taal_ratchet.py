"""De interface is Engels, en blijft dat (27 september 2026).

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
  * LOGREGELS (`%s`/`%r`/`%d`). Ook die mogen Nederlands zijn.
  * DE DATA. Seed-definities in `/catalog` en skill-beschrijvingen zijn INHOUD, geen interface.
    Een scan op gerenderde HTML zou daar permanent rood op staan; dit is een bron-scan.
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
    # Wat hier nog staat is géén interface. Per bestand, nagelopen:
    "views/vangst.py": 4,       # attribuutnamen: `data-staat-voor`, `name='staat'`, `.uk-staat`
    "views/noochie.py": 3,      # de Nederlandse SYSTEEMPROMPT van Noochie — instructie aan een
                                # model, geen tekst die een mens leest
    "views/messages.py": 2,     # de change-note "gezien-stand niet bijgewerkt"
    "views/navpaneel.py": 2,    # queryparameter `?welke=` en één logregel
    "views/checklists.py": 1,   # formulierveld `name='naar'`
    "views/metrics.py": 1,      # trefwoordenlijst voor een modelaanroep
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
    if "%s" in v or "%r" in v or "%d" in v:
        return True                                   # logregel
    if ":root{" in v or "--ink:" in v or v.lstrip().startswith("/*"):
        return True                                   # CSS met NL commentaar
    return False


def _bestanden() -> list[pathlib.Path]:
    return sorted(list((ROOT / "views").glob("*.py")) + [ROOT / "cockpit2_util.py",
                                                         ROOT / "web_base.py"])


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
