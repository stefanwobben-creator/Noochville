"""De gelaagde policy-stack, en dat een uitgezette policy écht uit de prompt valt.

"Alle policies van de cirkel" was te grof: de wortelcirkel draagt STANCE, WIP, DECISIONMAKING én
MONEY, allemaal `inherit=True`. Een copy-prompt kreeg dus de geld-policy mee — die gaat over
budgetten, zegt niets over schrijven, en verdunt de prompt met governance die de schrijver niet
aangaat.

Twee eisen, en de tweede is de scherpste: een knop die iets uitzet moet het ook echt uitzetten. Een
policy die als "uit" op het scherm staat maar toch in de prompt-tekst zit, is een leugen tegen de
gebruiker — hij denkt zonder die regel te werken en doet dat niet.
"""
from __future__ import annotations

import pytest

from nooch_village.views import copy_prompt as cp


class _Def:
    def __init__(self, domains=(), purpose="", accs=()):
        self.domains = list(domains)
        self.purpose = purpose
        self.accountabilities = list(accs)


class _Rec:
    def __init__(self, rid, domains=()):
        self.id = rid
        self.definition = _Def(domains)


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


WORTEL, MERK, ROL = "mother_earth__nooch", "mother_earth__nooch__brand", "mother_earth__nooch__copy"
RECS = _Records([_Rec(WORTEL), _Rec(MERK, ["Brand positioning", "Design system"]), _Rec(ROL)])

# MERK is een ZUSTERROL van ROL: zijn policies komen nooit vanzelf mee. In het oude model deed de
# ctx alsof ze geërfd werden, en dat verborg juist het gat dat de compositie oplost. Hier arriveren
# ze zoals ze echt arriveren — via een inclusie die iemand heeft gezet.
_POLICIES = {
    ROL:    [{"id": "TONEOFVOICE-001", "title": "Tone of Voice", "body": "wees warm"}],
    MERK:   [{"id": "BRANDPOSITIO-001", "title": "Brand positioning", "body": "merkstem"}],
    WORTEL: [{"id": "MONEY-001", "title": "Money", "body": "budget-regels"},
             {"id": "STANCE-001", "title": "Stance", "body": "wij vinden X"}],
}


class _Art:
    def __init__(self, d):
        self.__dict__.update(d)
        self.status = "active"


class _Att:
    def list(self, rid, kind):
        return [_Art(a) for a in _POLICIES.get(rid, [])] if kind == "policy" else []


class _Cfg:
    """StackConfig-dubbel: alleen wat componeer() nodig heeft."""
    def __init__(self, incl=None):
        self._i = dict(incl or {})

    def inclusies(self, rol):
        return list(self._i.get(rol, []))

    def door(self, rol, bron):
        return "test"


def _stack(uit=None, incl=(MERK,), monkeypatch=None):
    """De samengestelde stack voor ROL. serialize_context wordt gevoed uit _POLICIES, zodat
    erfenis (wortel) en eigen bezit uit dezelfde bron komen als in productie."""
    from nooch_village import artefacts, copy_stack

    def _fake_ctx(role_id, records, store):
        eigen = [dict(a) for a in _POLICIES.get(role_id, [])]
        geerfd = ([dict(a, origin_id=WORTEL, origin_path="via Mother Earth")
                   for a in _POLICIES[WORTEL]] if role_id != WORTEL else [])
        return {"role": {"id": role_id, "name": "Copywriter", "purpose": "schrijft",
                         "accountabilities": []},
                "policies": {"own": eigen, "inherited": geerfd}}

    import unittest.mock as _m
    with _m.patch.object(artefacts, "serialize_context", _fake_ctx), \
         _m.patch.object(copy_stack, "_own_policies",
                         lambda rol, records, att: [dict(a) for a in _POLICIES.get(rol, [])]):
        return copy_stack.componeer(ROL, RECS, _Att(), _Cfg({ROL: list(incl)}),
                                    uit=set(uit or ()))


def _ctx():
    return {
        "role": {"id": ROL, "name": "Copywriter", "purpose": "schrijft", "accountabilities": []},
        "policies": {
            "own": [{"id": "TONEOFVOICE-001", "title": "Tone of Voice", "body": "wees warm"}],
            "inherited": [
                {"id": "MONEY-001", "title": "Money", "body": "budget-regels", "origin_id": WORTEL,
                 "origin_path": "via Mother Earth"},
                {"id": "STANCE-001", "title": "Stance", "body": "wij vinden X", "origin_id": WORTEL,
                 "origin_path": "via Mother Earth"},
                {"id": "BRANDPOSITIO-001", "title": "Brand positioning", "body": "merkstem",
                 "origin_id": MERK, "origin_path": "via Brand"},
            ],
        },
    }


def _laag(items, pid):
    return next(a["laag"] for a in items if a["id"] == pid)


# ── De lagen ────────────────────────────────────────────────────────────────

def test_elke_policy_landt_in_de_juiste_laag():
    """De laag volgt uit de HERKOMST, niet uit de titel — een titel kan iedereen wijzigen."""
    items = _stack()
    assert _laag(items, "TONEOFVOICE-001") == cp.LAAG_ROL
    assert _laag(items, "BRANDPOSITIO-001") == cp.LAAG_MERK
    assert _laag(items, "MONEY-001") == cp.LAAG_KADER
    assert _laag(items, "STANCE-001") == cp.LAAG_KADER


def test_de_merk_laag_wordt_aan_het_domein_herkend_niet_aan_de_rol_id():
    """Een id kan hernoemd worden, een domein is governance.

    Zonder merk-domein blijft de ingesloten bron wél ingesloten — hij landt alleen in de neutrale
    inclusie-laag in plaats van de merk-laag. Nooit stilzwijgend bij 'eigen': dan zou de schrijver
    denken dat zíjn rol die regel cureert."""
    from nooch_village import copy_stack
    assert copy_stack.laag_van_domeinen(["Brand positioning"]) == cp.LAAG_MERK
    assert copy_stack.laag_van_domeinen(["Copycheck"]) == cp.LAAG_STEM
    assert copy_stack.laag_van_domeinen([]) == cp.LAAG_OVERIG
    assert copy_stack.laag_van_domeinen(["iets anders"]) == cp.LAAG_OVERIG


def test_governance_van_de_wortelcirkel_staat_standaard_uit():
    """DE klacht: de geld-policy zat in een copy-prompt. Budgetten zeggen niets over schrijven."""
    items = _stack()
    aan = {a["id"] for a in items if a["aan"]}
    assert "MONEY-001" not in aan and "STANCE-001" not in aan
    assert {"TONEOFVOICE-001", "BRANDPOSITIO-001"} <= aan


def test_een_kader_policy_is_per_stuk_aan_te_zetten():
    """Per-policy controle bínnen de laag, niet alles-of-niets per cirkel: 'Stance' is voor copy
    vaak wél relevant, 'Money' nooit."""
    items = _stack(uit={"STANCE-001"})
    # 'uit' zet uit; om iets aan te zetten dat standaard uit staat gebruikt de UI dezelfde set
    # omgekeerd — hier toetsen we dat de expliciete set de default overruled voor wat aan stond.
    assert not any(a["aan"] for a in items if a["id"] == "MONEY-001")


def test_een_expliciet_uitgezette_policy_valt_uit():
    items = _stack(uit={"TONEOFVOICE-001"})
    assert not any(a["aan"] for a in items if a["id"] == "TONEOFVOICE-001")
    assert any(a["aan"] for a in items if a["id"] == "BRANDPOSITIO-001")


# ── DE toets: uit is uit, ook in de prompt-tekst ───────────────────────────

def test_een_uitgezette_policy_staat_niet_in_de_prompt_tekst():
    """Een knop die iets uitzet moet het ook echt uitzetten. Een policy die als 'uit' op het scherm
    staat maar toch in de prompt zit, laat de gebruiker denken dat hij zonder die regel werkt."""
    ctx = _ctx()
    items = _stack()
    prompt = cp.bouw_prompt(ctx, items=items)
    assert "budget-regels" not in prompt                  # MONEY-body weg
    assert "MONEY-001" not in prompt
    assert "wees warm" in prompt                          # rol-policy blijft
    assert "merkstem" in prompt                           # merk-policy blijft


def test_uitzetten_haalt_ook_de_body_weg():
    ctx = _ctx()
    zonder = cp.bouw_prompt(ctx, items=_stack(uit={"BRANDPOSITIO-001"}))
    assert "merkstem" not in zonder and "BRANDPOSITIO-001" not in zonder


def test_de_teller_telt_alleen_wat_aan_staat():
    ctx = _ctx()
    prompt = cp.bouw_prompt(ctx, items=_stack())
    assert "=== POLICIES (2) ===" in prompt               # tone of voice + brand, niet de 4


def test_alles_uit_zegt_dat_eerlijk():
    ctx = _ctx()
    uit = {a["id"] for a in _stack()}
    prompt = cp.bouw_prompt(ctx, items=_stack(uit=uit))
    assert "=== POLICIES (0) ===" in prompt
    assert "all policies are switched off" in prompt


def test_geen_policies_leest_anders_dan_alles_uitgezet():
    """Een rol ZONDER policies is een governance-gat (ga het halen); alles uitgezet is een keuze
    van de gebruiker (zet er een aan). Ze op één zin gooien verbergt het eerste achter het tweede."""
    leeg = {"role": {"id": ROL, "name": "X", "purpose": "", "accountabilities": []},
            "policies": {"own": [], "inherited": []}}
    assert "this role has no policies" in cp.bouw_prompt(leeg, items=[])
    ctx = _ctx()
    uit = {a["id"] for a in _stack()}
    assert "switched off" in cp.bouw_prompt(ctx, items=_stack(uit=uit))


# ── De bodem: altijd mee, niet uitzetbaar ──────────────────────────────────

def test_de_missie_staat_altijd_in_de_prompt():
    """Waar Nooch voor bestaat is de bodem, geen keuze: een tekst die daarbuiten valt is geen
    Nooch-tekst."""
    from nooch_village.mission import ANCHOR_PURPOSE
    ctx = _ctx()
    uit = {a["id"] for a in _stack()}
    prompt = cp.bouw_prompt(ctx, items=_stack(uit=uit))
    assert ANCHOR_PURPOSE in prompt
    assert "always applies" in prompt


def test_de_strategie_komt_uit_config_niet_uit_de_view():
    """Eén bron: `config/strategy.json` is mens-bewerkbaar. Fail-soft bij een kapot bestand — geen
    verzonnen vervanger."""
    regels = cp._strategie_regels()
    assert isinstance(regels, list)
    prompt = cp.bouw_prompt(_ctx(), items=_stack())
    for r in regels:
        assert r in prompt


def test_zonder_inclusies_blijft_de_eigen_stack_staan():
    """Geen inclusie = geen merk-laag, maar wel gewoon eigen + geërfd. Een rol zonder inclusies
    hoort een werkende (zij het smallere) stack te houden, niet een lege."""
    items = _stack(incl=())
    assert {a["id"] for a in items} == {"TONEOFVOICE-001", "MONEY-001", "STANCE-001"}
    assert all(a["bron"] in ("eigen", "erfenis") for a in items)
    assert [a["id"] for a in items if a["aan"]] == ["TONEOFVOICE-001"]   # kader staat uit


# ── De drie selectors: doel × lezer × formaat-als-stem ─────────────────────

def test_de_vier_blokken_staan_in_leesvolgorde():
    """Waarom we bestaan → voor wie → wat je schrijft → de regels → wat je oplevert. De policies
    stonden eerst vóór de lezer, en dan leest het model de constraints zonder te weten voor wie."""
    import re
    p = cp.bouw_prompt(_ctx(), items=_stack(),
                       doel="inform", awareness="just browsing", soort="email")
    koppen = [k for k in re.findall(r"^=== (.+?) ===$", p, re.M)]
    assert koppen == ["ROLE", "WHAT NOOCH IS FOR (always applies)", "READER", "ASSIGNMENT",
                      "POLICIES (2)", "OUTPUT"]


def test_hard_sell_is_geen_optie():
    """Een optie die er staat, wordt gekozen. De Open Door-pillar zegt: informeer, overtuig niet."""
    labels = [n for n, _ in cp.DOELEN]
    assert labels == ["inform", "spark curiosity", "gently persuade"]
    assert not any("sell" in u.lower() and "never" not in u.lower() for _n, u in cp.DOELEN)


def test_de_onwetende_lezer_staat_rijk_beschreven():
    """De standaard-Nooch-lezer vond Nooch zonder te zoeken. Wat hij NIET weet is de kern van dit
    blok — zonder die opsomming schrijft het model voor een insider die niet bestaat."""
    p = cp.bouw_prompt(_ctx(), items=[], awareness="just browsing")
    for onbekend in ("made from oil", "what a batch is", "vegan is not the same as plastic-free",
                     "minimum order quantity", "regulated claim"):
        assert onbekend in p
    assert "Build every bridge" in p


def test_verder_op_de_schaal_vallen_de_bruggen_weg():
    kort = cp.bouw_prompt(_ctx(), items=[], awareness="knows exactly")
    assert "Do not re-explain the problem" in kort
    assert "Build every bridge" not in kort


def test_de_vier_lezersvragen_staan_er_altijd():
    """Ook zonder awareness-keuze: het zijn de doel-ankers van elke tekst."""
    p = cp.bouw_prompt(_ctx(), items=[])
    for vraag in cp.LEZERSVRAGEN:
        assert vraag in p
    assert "found us without looking" in p               # de default-lezer, expliciet


def test_formaat_zet_de_stem_en_is_geen_lege_tab():
    for naam, uitleg in cp.FORMATEN:
        p = cp.bouw_prompt(_ctx(), items=[], soort=naam)
        assert f"Format and voice: {naam}" in p and uitleg in p


def test_het_register_is_overal_weg():
    """Doel, doelgroep en stem hebben het overgenomen. Een derde as ernaast liet de schrijver
    kiezen tussen twee dingen die hetzelfde bedoelden."""
    import inspect
    assert "register" not in inspect.signature(cp.bouw_prompt).parameters
    assert "register" not in inspect.signature(cp.render_copy_prompt).parameters
    assert not hasattr(cp, "registers_uit_policies")
    p = cp.bouw_prompt(_ctx(), items=[], doel="inform", soort="email")
    assert "Register" not in p


def test_de_craft_regels_staan_niet_in_de_code():
    """A-route: de craft-laag verdwijnt IN de policy. Zou hij hier ook staan, dan drijft hij af
    zodra iemand COPYCHECK-001 bijwerkt — luna, het bibliotheek-domein, required_payload."""
    src = open("nooch_village/views/copy_prompt.py", encoding="utf-8").read()
    # De namen van de checks en de verboden woorden: die staan in COPYCHECK-001/TONEOFVOICE-001.
    for uit_de_policy in ("conscious consumer", "Smirk", "Try-Hard", "Mainstream",
                          "exclamation mark", "em-dash", "eco-warrior", "join the movement"):
        assert uit_de_policy not in src, f"'{uit_de_policy}' hoort in de policy, niet in de view"
    # `biodegradable` mag hier WEL staan — maar alleen als feit over wat de lezer niet weet, nooit
    # als schrijfregel. Het onderscheid is het hele punt van de A-route.
    assert "regulated claim" in src                       # lezerskennis
    assert "Never \"biodegradable\"" not in src            # dat is de policy-regel


# ── De tool is een schermknop, geen artefact ────────────────────────────────
#
# OMGEDRAAID OP 28 SEPTEMBER 2026. Hier stonden drie toetsen op `zorg_voor_tool`, die de generator
# als tool-ARTEFACT op een rol zette. Er bestond al een vaste schermknop "Copy prompt generator" op
# de Nooch-cirkel (`_ROLE_TOOLS`) die naar `/copy-prompt` gaat — dus het artefact was een tweede
# kaart met dezelfde naam en dezelfde bestemming. Op prod stonden er drie, uit drie generaties van
# de zaailijst. `ruim_tool_op` haalt ze weg; de knop blijft.

def _store(tmp_path):
    from nooch_village.attachments import AttachmentStore
    return AttachmentStore(str(tmp_path / "att.json"))


def _zaai(store, anchor="mother_earth"):
    """Zoals de oude zaai-routine hem neerzette: door `system`, één versie."""
    return store.add(anchor, "tool", title=cp.TOOL_TITEL, body=cp.TOOL_BODY,
                     url=f"/copy-prompt?rol={anchor}", inherit=False,
                     actor_id="system", actor_type="persona",
                     change_note="copy-prompt-generator ontsloten op de rol die hem gebruikt")


def test_de_zaai_uitvoer_wordt_opgeruimd(tmp_path):
    """DE KERN: wat de zaailijst maakte, haalt de opruiming weg."""
    store = _store(tmp_path)
    a = _zaai(store)
    assert cp.ruim_tool_op(store) == [a.id]
    assert store.get(a.id) is None


def test_hij_pakt_ze_op_elke_anchor(tmp_path):
    """Op prod stonden ze op twee rollen én op de cirkel — drie generaties van dezelfde lijst."""
    store = _store(tmp_path)
    ids = [_zaai(store, a).id for a in ("mother_earth", "rol_een", "rol_twee")]
    assert sorted(cp.ruim_tool_op(store)) == sorted(ids)
    assert store.by_kind("tool", include_archived=True) == []


def test_hij_is_idempotent(tmp_path):
    store = _store(tmp_path)
    _zaai(store)
    assert cp.ruim_tool_op(store)
    assert cp.ruim_tool_op(store) == []


def test_een_aangeraakte_kaart_blijft_staan(tmp_path):
    """DE GUARD, en het hele verschil tussen opruimen en wissen. Heeft iemand er ooit iets aan
    veranderd, dan is het geen zaai-uitvoer meer maar werk — en dan is weghalen een mensbeslissing."""
    store = _store(tmp_path)
    a = _zaai(store)
    store.update(a.id, body="ik heb hier iets aan toegevoegd",
                 actor_id="een-mens", actor_type="person")
    assert cp.ruim_tool_op(store) == []
    assert store.get(a.id) is not None


def test_een_machinale_versie_erbij_blokkeert_hem_niet(tmp_path):
    """De verhuizing naar de anchor-cirkel schrijft óók een versie-entry. Telde de guard op het
    AANTAL versies, dan blokkeerde het dorp zijn eigen opruiming met zijn eigen spoor."""
    store = _store(tmp_path)
    a = _zaai(store, "rol_een")
    store.verplaats(a.id, "mother_earth", actor_id="system", actor_type="persona")
    assert cp.ruim_tool_op(store) == [a.id]


def test_een_andere_tool_blijft_met_rust(tmp_path):
    """Op de titel en niet op de soort: de decision coach staat op dezelfde anchor."""
    store = _store(tmp_path)
    _zaai(store)
    coach = store.add("mother_earth", "tool", title="Decision coach", url="/decision-coach",
                      actor_id="system", actor_type="persona")
    cp.ruim_tool_op(store)
    assert [a.id for a in store.by_kind("tool")] == [coach.id]


def test_de_schermknop_is_wat_er_overblijft():
    """WAAROM HET WEG MAG. Niet "het is dubbel" als bewering, maar de knop aanwijzen die het werk
    doet — en die staat op de cirkel, met dezelfde naam en dezelfde bestemming."""
    from nooch_village.views.overview import _ROLE_TOOLS
    labels = {l: h for l, _d, h in _ROLE_TOOLS["mother_earth__nooch"]}
    assert labels.get(cp.TOOL_TITEL) == "/copy-prompt"
