"""Een model mag een ontvanger VOORSTELLEN, nooit AANWIJZEN.

CLAUDE.md, "AI is instrument, geen rol" (20 september 2026): elke plek waar een LLM-uitkomst een
organisatorisch effect heeft — wie iets toegewezen krijgt, of iets wordt opgevolgd — hoort een
expliciete mensbeslissing ertussen te hebben vóórdat het effect optreedt.

WAAROM DIT EEN TEST IS EN GEEN AFSPRAAK. `docs/CONVENTIES.md` zegt het al: **handhaving vereist
waarneembaarheid.** De vier regels die daar in de tabel staan faalden allemaal op dezelfde manier —
er was niets dat ze kón waarnemen, dus gold de regel op papier en niet in de code. Deze regel zou
precies zo verdampen: `_mens_ontvanger` liet een model de ontvanger kiezen en `naar_mens` leverde af
op die keuze, en dat stond wekenlang in de repo zonder dat iets zich meldde.

WAT DEZE RATCHET TELT — en dit is de les uit de eerste versie, die op dat punt faalde. De naïeve
check ("orakel en bezorger in dezelfde functie") vond de echte bug NIET, want daar zaten ze in twee
functies met een `return` ertussen. Een ratchet die zijn eigen aanleiding niet vangt is theater.
Daarom volgt deze de uitkomst ook over returnwaarden heen, met een vaste-punt-ronde over alle
modules: een functie die een orakel-uitkomst teruggeeft, IS zelf een orakel voor zijn aanroepers.

EN PER TUPLE-POSITIE, want zonder dat wordt het onbruikbaar. `_mens_ontvanger` geeft nu
`(rol, persoon, grond, suggestie)` terug waarvan alleen `suggestie` uit het model komt; een ratchet
die de hele unpack besmet zou precies het goede ontwerp afkeuren en dus worden uitgezet.

  ORAKELS    model-afgeleid oordeel over WIE iets bezit: `_vraag_llm`, `kies_ontvanger`,
             `escalation_router.match` — plus alles wat die uitkomst doorgeeft.
  BEZORGERS  leveren werk af of sluiten iets af: `route_werk`, `stuur`, `stuur_op_pad`,
             `_signaleer`, `post`, `create`, `resolve`.

Een orakel-uitkomst die alleen in TEKST belandt (een f-string, een logregel, een voorstel-zin in een
bericht) is precies wat WÉL mag — dat is het instrument. Daarom kijkt de test naar de argumenten van
bezorgers en niet naar het bestaan van de variabele.

DE GRENS, expliciet: dit volgt returnwaarden, geen attributen, geen dicts, geen callbacks. Stop je
de rol in `uit["rol"]` en lees je die drie functies verderop uit, dan ziet deze ratchet het niet. Dat
is de reden dat de regel óók in CLAUDE.md staat, en dat de drie bekende plekken hieronder daarnaast
een eigen gedragstest hebben in `test_bestemming_is_altijd_de_founder`.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

#: Functies die een model-afgeleid oordeel geven over wie werk bezit.
#:
#: `classificeer` STOND HIER NIET, en dat was een gat. Die functie matcht tekst tegen de actuele
#: accountabilities en was tot 20 september 2026 het ADRES waar een memo heen ging als geen rol het
#: domein hield (`triage_rol.menselijke_eigenaar`) — precies het gedrag dat deze ratchet hoort te
#: vangen, en precies het gedrag dat hij niet zag. Toegevoegd bij pijplijn stap 7, in dezelfde
#: beurt waarin die trede verdween: een ratchet die zijn eigen aanleiding niet dekt is theater, en
#: dat geldt voor de tweede aanleiding net zo goed als voor de eerste.
BASIS_ORAKELS = {"_vraag_llm", "kies_ontvanger", "match", "classificeer"}

#: Modulealiassen waaronder `match` het orakel is. Zonder deze lijst gaat de ratchet af op
#: `re.match(...)` en `pat.match(...)`, en een ratchet met valse alarmen wordt genegeerd.
MATCH_MODULES = {"er", "escalation_router", "router"}

#: Functies die werk AFLEVEREN of een uitkomst vastleggen.
BEZORGERS = {"route_werk", "stuur", "stuur_op_pad", "_signaleer", "post", "create", "resolve"}

#: True = de hele uitkomst is besmet; een set = alleen deze tuple-posities zijn besmet.
Besmetting = object


def _naam(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _orakel_van(call: ast.Call, bekend: dict, *, in_router: bool):
    """De besmetting die deze aanroep oplevert: True, een set posities, of None."""
    naam = _naam(call.func)
    if naam == "match":
        if isinstance(call.func, ast.Attribute):
            bron = call.func.value
            return True if (isinstance(bron, ast.Name) and bron.id in MATCH_MODULES) else None
        return True if in_router else None
    if naam in BASIS_ORAKELS:
        return True
    return bekend.get(naam)


def _besmette_namen(fn: ast.AST, bekend: dict, *, in_router: bool) -> set[str]:
    """Namen die in deze functie een orakel-uitkomst dragen, positie-bewust bij een unpack."""
    besmet: set[str] = set()
    for _ in range(3):                      # klein vast punt: a = orakel(); b = a
        voor = len(besmet)
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign):
                continue
            bron = None
            if isinstance(node.value, ast.Call):
                bron = _orakel_van(node.value, bekend, in_router=in_router)
            elif isinstance(node.value, ast.Name) and node.value.id in besmet:
                bron = True
            if bron is None:
                continue
            for doel in node.targets:
                if isinstance(doel, (ast.Tuple, ast.List)) and isinstance(bron, set):
                    for i, el in enumerate(doel.elts):
                        if i in bron and isinstance(el, ast.Name):
                            besmet.add(el.id)
                else:
                    for stuk in ast.walk(doel):
                        if isinstance(stuk, ast.Name):
                            besmet.add(stuk.id)
        if len(besmet) == voor:
            break
    return besmet


def _geeft_orakel_terug(fn: ast.AST, besmet: set[str], bekend: dict, *, in_router: bool):
    """Geeft deze functie een orakel-uitkomst terug? True, een set posities, of None."""
    posities: set[int] = set()
    heel = False
    for node in ast.walk(fn):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        stukken = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
        for i, el in enumerate(stukken):
            vuil = False
            for deel in ast.walk(el):
                if isinstance(deel, ast.Name) and deel.id in besmet:
                    vuil = True
                elif isinstance(deel, ast.Call) and _orakel_van(deel, bekend, in_router=in_router):
                    vuil = True
            if not vuil:
                continue
            # EEN F-STRING IS GEEN ADRES. Precies dit onderscheid houdt de ratchet bruikbaar:
            # een voorstel-zin teruggeven mag, een rol-id teruggeven niet.
            if isinstance(el, ast.JoinedStr):
                continue
            if isinstance(node.value, ast.Tuple):
                posities.add(i)
            else:
                heel = True
    if heel:
        return True
    return posities or None


def _bekende_orakels() -> dict:
    """Vast punt over ALLE modules: welke functies geven een orakel-uitkomst door?"""
    bomen = {f: ast.parse(f.read_text(encoding="utf-8")) for f in sorted(ROOT.rglob("*.py"))}
    bekend: dict = {}
    for _ in range(6):
        voor = dict(bekend)
        for f, boom in bomen.items():
            in_router = f.name == "escalation_router.py"
            for fn in ast.walk(boom):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                besmet = _besmette_namen(fn, bekend, in_router=in_router)
                uit = _geeft_orakel_terug(fn, besmet, bekend, in_router=in_router)
                if uit is not None:
                    bekend[fn.name] = uit
        if bekend == voor:
            break
    return bekend


def _overtredingen() -> list[str]:
    bekend = _bekende_orakels()
    uit = []
    for f in sorted(ROOT.rglob("*.py")):
        in_router = f.name == "escalation_router.py"
        boom = ast.parse(f.read_text(encoding="utf-8"))
        for fn in ast.walk(boom):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            besmet = _besmette_namen(fn, bekend, in_router=in_router)
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call) or _naam(call.func) not in BEZORGERS:
                    continue
                for arg in list(call.args) + [k.value for k in call.keywords]:
                    if isinstance(arg, ast.JoinedStr):
                        continue                      # tekst mag, zie de kop van dit bestand
                    for stuk in ast.walk(arg):
                        if isinstance(stuk, ast.Call) and _orakel_van(stuk, bekend,
                                                                     in_router=in_router):
                            uit.append(f"{f.relative_to(ROOT)}:{call.lineno} "
                                       f"{_naam(call.func)}(...) krijgt een orakel-uitkomst "
                                       f"rechtstreeks als argument")
                            break
                        if isinstance(stuk, ast.Name) and stuk.id in besmet:
                            uit.append(f"{f.relative_to(ROOT)}:{call.lineno} "
                                       f"{_naam(call.func)}(...) krijgt `{stuk.id}`, en die draagt "
                                       f"in {fn.name}() een model-oordeel over wie dit bezit")
                            break
                    else:
                        continue
                    break
    return uit


def test_geen_modeloordeel_bepaalt_een_bestemming():
    overtredingen = _overtredingen()
    assert overtredingen == [], (
        "een model-afgeleid oordeel over WIE iets bezit bepaalt hier een bestemming. CLAUDE.md "
        "(\"AI is instrument, geen rol\"): het model mag voorstellen, niet aanwijzen — zet de "
        "uitkomst in de TEKST van het bericht en laat een mens hem accepteren.\n"
        + "\n".join(overtredingen))


# ── de ratchet moet zelf aantoonbaar werken ────────────────────────────────

def _scan(bron: str, *, in_router: bool = True) -> list[str]:
    boom = ast.parse(bron)
    bekend: dict = {}
    for _ in range(4):
        for fn in ast.walk(boom):
            if isinstance(fn, ast.FunctionDef):
                b = _besmette_namen(fn, bekend, in_router=in_router)
                u = _geeft_orakel_terug(fn, b, bekend, in_router=in_router)
                if u is not None:
                    bekend[fn.name] = u
    treffers = []
    for fn in ast.walk(boom):
        if not isinstance(fn, ast.FunctionDef):
            continue
        besmet = _besmette_namen(fn, bekend, in_router=in_router)
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call) or _naam(call.func) not in BEZORGERS:
                continue
            for arg in list(call.args) + [k.value for k in call.keywords]:
                if isinstance(arg, ast.JoinedStr):
                    continue
                for stuk in ast.walk(arg):
                    if isinstance(stuk, ast.Call) and _orakel_van(stuk, bekend,
                                                                  in_router=in_router):
                        treffers.append(fn.name)
                    elif isinstance(stuk, ast.Name) and stuk.id in besmet:
                        treffers.append(fn.name)
    return treffers


def test_de_historische_bug_valt_op():
    """DE ECHTE VORM, met een `return` tussen de keuze en de aflevering. De eerste versie van deze
    ratchet keek alleen binnen één functie en vond hem NIET — precies de bug die hij moest vangen."""
    assert _scan('''
def _mens_ontvanger(st, tekst, kandidaten, from_role, reason_fn):
    keuze = kies_ontvanger(_vraag_llm(tekst, "", kandidaten, from_role, reason_fn),
                           kandidaten, [], from_role)
    if keuze:
        return keuze, "", "deze rol bezit dit werk"
    return "", "", "niemand"

def naar_mens(st, project, tekst, from_role):
    rol, persoon, grond = _mens_ontvanger(st, tekst, [], from_role, None)
    return route_werk(st, tekst=tekst, rol=rol, persoon=persoon)
''')


def test_de_tweede_historische_bug_valt_op_in_zijn_directe_vorm():
    """DE PLEK DIE DEZE RATCHET TOT 20 SEPTEMBER 2026 MISTE: `triage_rol.menselijke_eigenaar`.
    De modelmatch bepaalde de rol, de rol werd het adres, en `stuur_op_pad` leverde af — en
    `classificeer` stond niet in `BASIS_ORAKELS`. Nu wel."""
    assert _scan('''
def menselijke_eigenaar(st, tekst, reason_fn):
    rol = classificeer(tekst, st.records, reason_fn=reason_fn)
    return rol, "gematcht door de secretary"

def stuur_memo(st, data_dir, tekst):
    rol, waarom = menselijke_eigenaar(st, tekst, None)
    return stuur_op_pad(data_dir, "role", rol, tekst)
''', in_router=False)


def test_de_get_vorm_ontsnapt_en_dat_is_gemeten():
    """DE GRENS, EERLIJK VASTGELEGD — en dit is de vorm die de ECHTE bug had.

    `rol = uitslag.get("rol") or ""` is een BoolOp om een attribute-call om een besmette naam. De
    besmetting reist alleen door een kale `Call` of een kale `Name`, dus `rol` blijft schoon en de
    ratchet zwijgt. Dat staat al in de kop ("volgt returnwaarden, geen attributen, geen dicts"),
    maar het is makkelijk te lezen als een detail — het is de reden dat deze bug maanden kon staan.

    WAAROM NIET GEWOON VERBREDEN. Geprobeerd op 20 september 2026 (elke naam die ergens in de
    toegewezen waarde zit telt mee). Uitkomst: 5 treffers op echte code, alle vijf onterecht —
    `escalation_router.route_werk(herkomst=…)` en `inbox.resolve(…, extra=summary)` dragen TEKST,
    `cli.main`'s `k["id"]` en twee `wiki.ontvanger`-uitkomsten dragen een deterministisch adres met
    een besmette INVOER. Vijf uitzonderingen op een ratchet van deze omvang is precies waar de kop
    hierboven voor waarschuwt: "een ratchet met valse alarmen wordt genegeerd".

    Daarom blijft de ratchet smal en staat de echte bewaking op deze plek in een GEDRAGSTEST
    (`test_menselijke_eigenaar.test_het_modelvoorstel_is_nooit_het_adres`). Zelfde arbeidsdeling als
    voor de drie bekende plekken die de kop noemt."""
    assert not _scan('''
def menselijke_eigenaar(st, tekst, reason_fn):
    uitslag = classificeer(tekst, st.records, reason_fn=reason_fn)
    rol = uitslag.get("rol") or ""
    return rol, "gematcht door de secretary"

def stuur_memo(st, data_dir, tekst):
    rol, waarom = menselijke_eigenaar(st, tekst, None)
    return stuur_op_pad(data_dir, "role", rol, tekst)
''', in_router=False)


def test_het_voorstel_naast_een_vast_adres_mag_wel():
    """De vorm die er nu staat: het model levert een ZIN, het adres is een constante. Gaat de
    ratchet hier toch af, dan keurt hij de oplossing af die hij zelf afdwong."""
    assert not _scan('''
def menselijke_eigenaar(st, tekst, reason_fn):
    uitslag = classificeer(tekst, st.records, reason_fn=reason_fn)
    regel = f"voorstel: dit raakt mogelijk {uitslag.get('rol')}"
    return FOUNDER_ROLE_ID, regel

def stuur_memo(st, data_dir, tekst):
    rol, regel = menselijke_eigenaar(st, tekst, None)
    return stuur_op_pad(data_dir, "role", rol, f"{tekst} - {regel}")
''', in_router=False)


def test_een_voorstel_in_de_tekst_mag_wel():
    """De vorm die we WILLEN: het model levert een zin op positie 3, de bestemming komt van
    `signaal.terugval`. Gaat de ratchet hier toch af, dan keurt hij het goede ontwerp af."""
    assert not _scan('''
def _mens_ontvanger(st, tekst, from_role, reason_fn):
    rol, kind, waarom = er.match(tekst, st.records, van_rol=from_role, reason_fn=reason_fn)
    suggestie = f"voorstel: dit lijkt van {rol} - {waarom}"
    founder = signaal.terugval(st)
    return "", founder, "alles komt eerst bij jou", suggestie

def naar_mens(st, project, tekst, from_role):
    rol, persoon, grond, suggestie = _mens_ontvanger(st, tekst, from_role, None)
    herkomst = f"{grond} - {suggestie}"
    return route_werk(st, tekst=tekst, rol=rol, persoon=persoon, herkomst=herkomst)
''')


def test_re_match_is_geen_orakel():
    """`re.match` en `pat.match` heten toevallig hetzelfde. Een ratchet die daarop afgaat wordt
    uitgezet, en dan bewaakt hij niets meer."""
    assert not _scan('''
def stuur_iets(st, tekst):
    m = re.match(r"x", tekst)
    return stuur(st, "role", "x", m.group(0) if m else tekst)
''', in_router=False)
