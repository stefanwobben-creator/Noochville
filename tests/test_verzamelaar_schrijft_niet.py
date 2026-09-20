"""Een verzamelaar WAARNEEMT. Hij schrijft niet.

WAAROM DIT EEN RATCHET IS. De signaalpijplijn (20 september 2026) bestaat uit vijf adapters die
elk een bron lezen en `weekmemo.Signaal`-objecten teruggeven. Twee van die vijf schreven vóór de
pijplijn wél: `legal_signaal.check` zette een item in de human-inbox, `materiaal_memo`'s shortlist
onthield wat het had voorgelegd. Dat onthouden gebeurt nu op ÉÉN plek — in `weekmemo.ronde`, ná
bezorging — en precies dat is de winst die stil kan verdampen: de volgende keer dat iemand een bron
toevoegt is "even hier onthouden dat ik dit al gezien heb" de makkelijkste regel om te schrijven.

WAT ER DAN MISGAAT, en waarom het erger is dan dubbel werk:

1. **Het geheugen drijft uiteen.** Twee boeken over hetzelfde feit ("is dit al voorgelegd?") lopen
   uit de pas zodra één van de twee paden faalt. Dat is de `reference, don't copy`-regel uit
   CLAUDE.md, toegepast op een boek in plaats van op een getal.
2. **Een mislukte bezorging verliest een week stil.** De ronde onthoudt bewust pas ná een geslaagde
   DM. Een verzamelaar die zelf onthoudt, onthoudt al tijdens het verzamelen — en dan is een
   signaal "voorgelegd" dat niemand ooit zag.
3. **Een droge run is dan niet meer droog.** `village weekmemo` zonder `--doen` hoort niets te
   veranderen; dat kan alleen als het verzamelen zelf side-effect-free is.

DE REGEL IS DE NAAM. Elke functie in `nooch_village/` die `verzamel` heet of daarmee begint, mag
in zijn hele aanroepketting BINNEN ZIJN EIGEN MODULE geen schrijf-aanroep doen. Een nieuwe bron
valt daarmee automatisch onder de regel zodra hij de naamconventie volgt — geen lijst om bij te
werken, en geen stilte als iemand er eentje vergeet.

DE GRENS, expliciet: dit volgt aanroepen binnen dezelfde module en herkent schrijvers op NAAM.
Een verzamelaar die een schrijffunctie uit een ander bestand importeert en aanroept valt hier
alleen op als die naam in `SCHRIJVERS` staat. Zoals bij de routerings-ratchet: dit is een net met
mazen, geen bewijs — en daarom staat de regel óók in `weekmemo`'s eigen kop.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

#: Aanroepen die iets vastleggen: op schijf, in een store, of als bericht. Bewust ruim — een
#: verzamelaar heeft geen van deze nodig, dus een valse treffer kost hier niets en een gemiste wel.
SCHRIJVERS = {
    # schijf
    "atomic_write_json", "write_text", "write_bytes", "dump", "mkdir", "unlink", "rename",
    # stores
    "_save", "_schrijf", "zet", "set_meta", "create", "add", "record", "resolve", "assign",
    "curate", "leg_vast", "overlay_set_status", "overlay_add_term", "overlay_uitzondering",
    # pijplijn-specifiek: de twee plekken waar het geheugen en het ritme leven
    "markeer_week", "markeer_gedraaid", "noteer_periode", "noteer_oordeel",
    "onthoud", "onthoud_voorgelegd",
    # uitgangen
    "post", "stuur", "stuur_op_pad", "zet_op_bord", "bericht_aan_rol", "_signaleer",
}

#: De vijf bronnen van de weekmemo. Ze hoeven hier niet te staan om bewaakt te wórden (de
#: naamregel doet dat), maar hun AANWEZIGHEID wordt wel getoetst: verdwijnt er een uit deze
#: telling, dan is een bron hernoemd of weggevallen en dan bewaakt deze test hem niet meer.
BRON_MODULES = {"legal_signaal.py", "claims_context.py", "claims_modelpas.py",
                "materiaal_memo.py", "claim_evidence.py"}


def _naam(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _schrijft(call: ast.Call) -> str:
    """De schrijf-aanroep die dit is, of "". `open(pad, "w")` telt ook."""
    naam = _naam(call.func)
    if naam in SCHRIJVERS:
        return naam
    if naam == "open":
        modes = [a.value for a in call.args[1:] if isinstance(a, ast.Constant)]
        modes += [k.value.value for k in call.keywords
                  if k.arg == "mode" and isinstance(k.value, ast.Constant)]
        if any(isinstance(m, str) and any(c in m for c in "wax+") for m in modes):
            return 'open(..., "w")'
    return ""


def _overtredingen_in(boom: ast.AST, bestand: str) -> list[str]:
    """Elke schrijf-aanroep in de aanroepketting van een `verzamel*`-functie in deze module."""
    lokaal = {n.name: n for n in ast.walk(boom)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    uit = []
    for fn in lokaal.values():
        if not fn.name.startswith("verzamel"):
            continue
        gezien, stapel = {fn.name}, [fn]
        while stapel:
            huidig = stapel.pop()
            for call in ast.walk(huidig):
                if not isinstance(call, ast.Call):
                    continue
                schrijf = _schrijft(call)
                if schrijf:
                    uit.append(f"{bestand}:{call.lineno} {fn.name}() schrijft via "
                               f"`{schrijf}`"
                               + (f" (via {huidig.name}())" if huidig is not fn else ""))
                naam = _naam(call.func)
                if naam in lokaal and naam not in gezien:
                    gezien.add(naam)
                    stapel.append(lokaal[naam])
    return uit


def _alle_verzamelaars() -> dict[str, list[str]]:
    gevonden: dict[str, list[str]] = {}
    for f in sorted(ROOT.rglob("*.py")):
        boom = ast.parse(f.read_text(encoding="utf-8"))
        namen = [n.name for n in ast.walk(boom)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name.startswith("verzamel")]
        if namen:
            gevonden[f.name] = namen
    return gevonden


def test_geen_verzamelaar_schrijft():
    overtredingen = []
    for f in sorted(ROOT.rglob("*.py")):
        boom = ast.parse(f.read_text(encoding="utf-8"))
        overtredingen += _overtredingen_in(boom, str(f.relative_to(ROOT)))
    assert overtredingen == [], (
        "een verzamelaar legt hier iets vast. Verzamelen is WAARNEMEN; het onthouden hoort op één "
        "plek te staan (`weekmemo.ronde`, ná bezorging), anders drijft het geheugen uiteen en "
        "verliest een mislukte bezorging een week stil.\n" + "\n".join(overtredingen))


def test_alle_vijf_de_bronnen_vallen_onder_de_regel():
    """Zonder deze telling verdwijnt een bron geruisloos uit de bewaking zodra hij hernoemd wordt —
    en dan is de ratchet groen omdat hij niets meer ziet, niet omdat er niets mis is."""
    gevonden = _alle_verzamelaars()
    ontbreekt = BRON_MODULES - set(gevonden)
    assert not ontbreekt, f"deze bronnen hebben geen `verzamel`-functie meer: {sorted(ontbreekt)}"
    assert "verzamel_alles" in gevonden["weekmemo.py"]


# ── de ratchet moet zelf aantoonbaar werken ────────────────────────────────────────────────────

def _scan(bron: str) -> list[str]:
    return _overtredingen_in(ast.parse(bron), "test")


def test_een_verzamelaar_die_onthoudt_valt_op():
    """DE AANLEIDING, letterlijk: `materiaal_memo.verzamel` deed dit tot adapter 2 (stap 2)."""
    assert _scan('''
def verzamel(st, data_dir, sinds=0.0):
    uit = [s for s in st.radar.all_items() if s["at"] >= sinds]
    onthoud_voorgelegd(data_dir, [s["id"] for s in uit])
    return uit
''')


def test_ook_een_schrijf_via_een_eigen_hulpje_valt_op():
    """De naïeve check ("staat er een schrijf-aanroep in deze functie") mist precies de vorm die
    een mens schrijft als hij het netjes wil doen: een hulpje ernaast."""
    assert _scan('''
def _boek_bij(data_dir, ids):
    atomic_write_json(data_dir + "/boek.json", {"ids": ids})

def verzamel(data_dir, sinds=0.0):
    uit = _lees(data_dir, sinds)
    _boek_bij(data_dir, [s.herkomst for s in uit])
    return uit
''')


def test_een_verzamelaar_die_alleen_leest_mag_wel():
    """Lezen van het boek mag juist wél — anders legt de eerste memo de hele geschiedenis voor.
    Gaat de ratchet hier af, dan verbiedt hij het ontwerp dat hij hoort te beschermen."""
    assert not _scan('''
def verzamel(st, data_dir, sinds=0.0):
    boek = voorgelegd(data_dir)
    return [s for s in st.radar.all_items()
            if s["at"] >= sinds and s["id"] not in boek]
''')


def test_de_ronde_zelf_mag_wel_schrijven():
    """`ronde` IS de plek die onthoudt. Een regel die dat ook zou verbieden, verbiedt de oplossing."""
    assert not _scan('''
def ronde(data_dir, periode):
    signalen = verzamel_bronnen(data_dir)
    markeer_gedraaid(data_dir, periode)
    onthoud(data_dir, [s.herkomst for s in signalen])
    return signalen

def verzamel_bronnen(data_dir):
    return lees(data_dir)
''')
