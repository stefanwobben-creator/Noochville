"""De faalrichting van elke autorisatiepoort staat één kant op, en "guest" is nooit de verliezer.

WAAROM DEZE TEST BESTAAT. De gedocumenteerde semantiek staat in CLAUDE.md en in elke gate-helper:

    guest (auth uit) mag alles · ingelogd-maar-onbekend wordt geweigerd

Vier handlers deden op 8 september exact het omgekeerde:

    if c.username in (None, "guest"):
        return c.nxt, "✗ not allowed"

Dat is fout in BEIDE richtingen tegelijk. Het weigert de guest, die per definitie alles mag omdat
auth uit staat, en het laat élke ingelogde gebruiker door, ook een die de gate had moeten weigeren.
`_act_source_activate` zette daarmee externe API's aan voor het hele dorp, op kosten van de
organisatie, achter een check die alleen de enige gebruiker tegenhield die hem niet nodig had.

Geen van die vier takken had een AUTHZ-label. Dat is geen toeval: het label dwingt je om te kiezen
uit de vier poorten, en wie kiest komt vanzelf bij een helper uit. Een handgeschreven check is de
plek waar de richting kan omvallen zonder dat iemand het ziet.

DEZE TEST MEET DE RICHTING, NIET DE VORM. Hij zoekt geen tekst maar rekent de conditie uit met
`username = "guest"`. Komt daar True uit terwijl het lichaam een weigering teruggeeft, dan wordt de
guest geweigerd, hoe de check ook is opgeschreven.
"""
from __future__ import annotations

import ast

import nooch_village.cockpit2 as cockpit2

_WEIGER_WOORDEN = ("not allowed", "no access", "geen toegang", "niet toegestaan")


def _is_weigering(node: ast.AST) -> bool:
    """Geeft dit `return` een weigering terug? Elke string-constante eronder telt mee, zodat
    `return c.nxt, "✗ not allowed"` én `return nxt, f"✗ {deny}"`-varianten worden gezien."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if any(w in sub.value.lower() for w in _WEIGER_WOORDEN):
                return True
    return False


def _waar_voor_guest(test: ast.AST) -> bool | None:
    """Reken de conditie uit met `username == "guest"`. True/False, of None als het niet te
    bepalen valt (dan zegt deze test er niets over — dat is het punt van een ratchet)."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        links = _als_username(test.left)
        op = test.ops[0]
        rechts = test.comparators[0]
        if links:
            if isinstance(op, (ast.In, ast.NotIn)) and isinstance(rechts, (ast.Tuple, ast.List, ast.Set)):
                leden = {e.value for e in rechts.elts if isinstance(e, ast.Constant)}
                erin = "guest" in leden
                return erin if isinstance(op, ast.In) else not erin
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(rechts, ast.Constant):
                gelijk = rechts.value == "guest"
                return gelijk if isinstance(op, ast.Eq) else not gelijk
        return None
    if isinstance(test, ast.BoolOp):
        deel = [_waar_voor_guest(v) for v in test.values]
        if isinstance(test.op, ast.Or):
            if any(d is True for d in deel):
                return True
            return False if all(d is False for d in deel) else None
        if any(d is False for d in deel):
            return False
        return True if all(d is True for d in deel) else None
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        binnen = _waar_voor_guest(test.operand)
        return None if binnen is None else not binnen
    return None


def _als_username(node: ast.AST) -> bool:
    """Is dit de gebruikersnaam? `username` of `c.username` — meer vormen komen niet voor."""
    if isinstance(node, ast.Name) and node.id == "username":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "username"


def _handlers() -> list[ast.FunctionDef]:
    boom = ast.parse(open(cockpit2.__file__, encoding="utf-8").read())
    return [n for n in ast.walk(boom)
            if isinstance(n, ast.FunctionDef) and n.name.startswith(("_act_", "_ff_"))]


#: De ENIGE tak die de guest bewust weigert, met de reden erbij. `_act_goedkeur` bedient het
#: human-inbox-approvaloppervlak, en CLAUDE.md is daar absoluut over: "Approvals en activaties
#: mogen uitsluitend op dit geauthenticeerde lokale oppervlak bevestigd worden." `guest` betekent
#: dat auth UIT staat — precies de toestand waarin een goedkeuring niet mag landen. Hier is
#: guest-weigeren dus geen omgekeerde faalrichting maar de regel zelf.
_MAG_GUEST_WEIGEREN = {"_act_goedkeur": "human-inbox approval — CLAUDE.md, beveiligingsgrens"}


def test_geen_enkele_handler_weigert_de_guest():
    """DE KERNTEST. Een conditie die waar is voor de guest mag nooit op een weigering uitkomen,
    behalve op het approvaloppervlak (zie `_MAG_GUEST_WEIGEREN`)."""
    fout = []
    for fn in _handlers():
        if fn.name in _MAG_GUEST_WEIGEREN:
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            if _waar_voor_guest(node.test) is not True:
                continue
            if any(_is_weigering(s) for s in node.body if isinstance(s, ast.Return)):
                fout.append(f"{fn.name}:{node.lineno}")
    assert not fout, (
        "deze handlers weigeren juist de guest (auth uit = alles mag) en laten elke ingelogde "
        "gebruiker door: " + ", ".join(fout) +
        ". Gebruik _role_gate / _member_gate / _lead_gate / _anchor_gate; die kennen de richting.")


def test_de_uitzondering_weigert_de_guest_ook_echt_nog():
    """De allow-list mag geen dode letter worden. Zou `_act_goedkeur` zijn guest-weigering ooit
    verliezen, dan staat het approvaloppervlak open in auth-uit-modus en zegt deze lijst nog
    steeds dat het een bewuste uitzondering is."""
    for naam in _MAG_GUEST_WEIGEREN:
        fn = next((f for f in _handlers() if f.name == naam), None)
        assert fn is not None, f"{naam} bestaat niet meer — haal hem uit _MAG_GUEST_WEIGEREN"
        weigert = any(
            _waar_voor_guest(node.test) is True
            and any(_is_weigering(s) for s in node.body if isinstance(s, ast.Return))
            for node in ast.walk(fn) if isinstance(node, ast.If))
        assert weigert, (
            f"{naam} weigert de guest niet meer, terwijl hij op de uitzonderingslijst staat. "
            f"Ofwel de poort is weg (een gat), ofwel de lijst is verouderd.")


def test_de_gate_helpers_laten_de_guest_allemaal_door():
    """De tegenhanger, op gedrag in plaats van op vorm: als de helpers zelf zouden omvallen, meet
    de test hierboven de verkeerde waarheid."""
    class _Leeg:
        people = records = assign = None

        def by_email(self, *a):                          # pragma: no cover — wordt niet bereikt
            raise AssertionError("de guest hoort nooit tot een store-lookup te komen")

    st = _Leeg()
    st.people = st
    assert cockpit2._role_gate("welke_rol_dan_ook", "guest", st) is None
    assert cockpit2._member_gate("welke_cirkel_dan_ook", "guest", st) is None
    assert cockpit2._anchor_gate(st, "guest") is None


def test_een_onbekende_ingelogde_gebruiker_wordt_wel_geweigerd():
    """De andere helft van de regel. Zonder deze test zou "laat guest door" te repareren zijn
    door iedereen door te laten."""
    class _Mensen:
        def by_email(self, _u):
            return None

    class _St:
        people = _Mensen()
        records = None
        assign = None

    st = _St()
    assert cockpit2._role_gate("rol", "iemand@example.com", st)
    assert cockpit2._member_gate("cirkel", "iemand@example.com", st)
    assert cockpit2._anchor_gate(st, "iemand@example.com")


def test_de_ratchet_ziet_de_oude_vorm_echt():
    """Bewijs dat de meting bijt: de vier vormen waarin de bug is voorgekomen worden herkend,
    en de CORRECTE inline-vorm (guest juist buiten de weigering) niet."""
    fout = ast.parse(
        "def _act_x(c):\n"
        "    if c.username in (None, 'guest'):\n"
        "        return c.nxt, '✗ not allowed'\n"
        "def _act_y(c):\n"
        "    if not src or c.username in (None, 'guest'):\n"
        "        return c.nxt, '✗ not allowed'\n"
        "def _act_z(c):\n"
        "    if c.username == 'guest':\n"
        "        return c.nxt, 'No access — nope'\n"
    )
    goed = ast.parse(
        "def _act_ok(c):\n"
        "    if actor is None and username != 'guest':\n"
        "        return nxt, 'No access — user not recognised'\n"
    )

    def _tel(boom):
        n = 0
        for fn in [f for f in ast.walk(boom) if isinstance(f, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.If) and _waar_voor_guest(node.test) is True:
                    n += sum(1 for s in node.body
                             if isinstance(s, ast.Return) and _is_weigering(s))
        return n

    assert _tel(fout) == 3, "de ratchet moet alle drie de omgekeerde vormen zien"
    assert _tel(goed) == 0, "de correcte vorm mag niet vals alarm geven"


#: De poort-helpers plus de twee inline-vormen die hetzelfde doen. Roept een tak er één aan, dan
#: is er een keuze gemaakt, ook als het label ontbreekt.
_POORTEN = {"_role_gate", "_member_gate", "_lead_gate", "_anchor_gate", "_notif_gate",
            "is_circle_lead", "is_role_filler", "is_circle_member", "_act_ws_curate"}


def _alle_functies() -> dict:
    boom = ast.parse(open(cockpit2.__file__, encoding="utf-8").read())
    return {n.name: n for n in ast.walk(boom) if isinstance(n, ast.FunctionDef)}


def _roept_een_poort(fn: ast.FunctionDef, fns: dict, diepte: int = 0) -> bool:
    """Zit er een poort in deze tak, desnoods één of twee helpers diep? `_act_ws_forbid` gaat via
    `_act_ws_curate`, en die vorm mag niet als 'ongegate' tellen."""
    namen = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    if namen & _POORTEN:
        return True
    if diepte < 2:
        return any(n in fns and n.startswith("_") and _roept_een_poort(fns[n], fns, diepte + 1)
                   for n in namen)
    return False


def _heeft_label(fn: ast.FunctionDef, regels: list[str]) -> bool:
    """In de tak zelf, of in het blok-comment er direct boven (het bestaande idioom: één
    blok-comment voor een familie van takken)."""
    start, eind = fn.lineno, (fn.end_lineno or fn.lineno)
    if any("AUTHZ:" in r for r in regels[start - 1:eind]):
        return True
    for i in range(start - 2, max(-1, start - 32), -1):
        r = regels[i]
        if "AUTHZ:" in r:
            return True
        if r.strip() and not r.lstrip().startswith("#") and not r.startswith("def "):
            break
    return False


def test_geen_dispatch_tak_zonder_poort_en_zonder_label():
    """DE TWEEDE HELFT VAN RONDE D PUNT 6, op de vraag die telt: is er iemand die hierover heeft
    nagedacht? Een tak die géén poort aanroept EN geen label draagt is een tak waar niemand een
    keuze maakte, en dat is precies waar de vier omgekeerde handlers vandaan kwamen.

    Bewust niet "elke tak moet een label hebben": 69 takken draaien een echte poort en missen
    alleen de comment. Dat is administratieve schuld, geen risico, en een test die die twee op
    één hoop gooit is een test die je uitzet.

    Plafond nul: er is er geen enkele meer. Nieuwe takken erven de eis."""
    fns = _alle_functies()
    regels = open(cockpit2.__file__, encoding="utf-8").read().splitlines()
    namen = {getattr(fn, "__name__", "") for fn in cockpit2.ACTIONS.values()}
    blind = sorted(n for n in namen
                   if n in fns and not _heeft_label(fns[n], regels) and not _roept_een_poort(fns[n], fns))
    assert not blind, (
        "deze dispatch-takken hebben geen poort én geen AUTHZ-label — niemand heeft gekozen: "
        + ", ".join(blind) +
        ". Kies één van de vier: anchor-lead · Circle Lead · rolvervuller of Circle Lead · "
        "circle-member of iedereen-ingelogd, en zet hem als comment boven de tak. Bewust ongated "
        "mag, maar dan mét het label en de reden.")


def test_de_labelschuld_daalt_monotoon():
    """De rest: takken die wél een poort draaien maar de comment missen. Een ratchet met een
    plafond, zodat het opruimen kan doorgaan zonder dat iemand er nu 69 comments bij typt."""
    fns = _alle_functies()
    regels = open(cockpit2.__file__, encoding="utf-8").read().splitlines()
    namen = {getattr(fn, "__name__", "") for fn in cockpit2.ACTIONS.values()}
    schuld = [n for n in namen if n in fns and not _heeft_label(fns[n], regels)]
    assert len(schuld) <= _LABELSCHULD, (
        f"{len(schuld)} takken zonder AUTHZ-label (plafond {_LABELSCHULD}). Nieuwe takken krijgen "
        f"er direct een; zie CLAUDE.md → Autorisatie.")
    assert len(schuld) == _LABELSCHULD, (
        f"nog maar {len(schuld)} takken zonder label — zet _LABELSCHULD op dat getal. De ratchet "
        f"daalt monotoon naar nul.")


#: Bestaande labelschuld (takken mét poort, zónder comment). Mag alleen DALEN.
_LABELSCHULD = 66
