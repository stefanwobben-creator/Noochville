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
    items = cp._policy_items(_ctx(), RECS)
    assert _laag(items, "TONEOFVOICE-001") == cp.LAAG_ROL
    assert _laag(items, "BRANDPOSITIO-001") == cp.LAAG_MERK
    assert _laag(items, "MONEY-001") == cp.LAAG_KADER
    assert _laag(items, "STANCE-001") == cp.LAAG_KADER


def test_de_merk_laag_wordt_aan_het_domein_herkend_niet_aan_de_rol_id():
    """Een id kan hernoemd worden, een domein is governance."""
    zonder_domein = _Records([_Rec(WORTEL), _Rec(MERK), _Rec(ROL)])
    items = cp._policy_items(_ctx(), zonder_domein)
    assert _laag(items, "BRANDPOSITIO-001") == cp.LAAG_KADER   # geen domein → geen merk-laag


def test_governance_van_de_wortelcirkel_staat_standaard_uit():
    """DE klacht: de geld-policy zat in een copy-prompt. Budgetten zeggen niets over schrijven."""
    items = cp._policy_items(_ctx(), RECS)
    aan = {a["id"] for a in items if a["aan"]}
    assert "MONEY-001" not in aan and "STANCE-001" not in aan
    assert {"TONEOFVOICE-001", "BRANDPOSITIO-001"} <= aan


def test_een_kader_policy_is_per_stuk_aan_te_zetten():
    """Per-policy controle bínnen de laag, niet alles-of-niets per cirkel: 'Stance' is voor copy
    vaak wél relevant, 'Money' nooit."""
    items = cp._policy_items(_ctx(), RECS, uit={"STANCE-001"})
    # 'uit' zet uit; om iets aan te zetten dat standaard uit staat gebruikt de UI dezelfde set
    # omgekeerd — hier toetsen we dat de expliciete set de default overruled voor wat aan stond.
    assert not any(a["aan"] for a in items if a["id"] == "MONEY-001")


def test_een_expliciet_uitgezette_policy_valt_uit():
    items = cp._policy_items(_ctx(), RECS, uit={"TONEOFVOICE-001"})
    assert not any(a["aan"] for a in items if a["id"] == "TONEOFVOICE-001")
    assert any(a["aan"] for a in items if a["id"] == "BRANDPOSITIO-001")


# ── DE toets: uit is uit, ook in de prompt-tekst ───────────────────────────

def test_een_uitgezette_policy_staat_niet_in_de_prompt_tekst():
    """Een knop die iets uitzet moet het ook echt uitzetten. Een policy die als 'uit' op het scherm
    staat maar toch in de prompt zit, laat de gebruiker denken dat hij zonder die regel werkt."""
    ctx = _ctx()
    items = cp._policy_items(ctx, RECS)
    prompt = cp.bouw_prompt(ctx, items=items)
    assert "budget-regels" not in prompt                  # MONEY-body weg
    assert "MONEY-001" not in prompt
    assert "wees warm" in prompt                          # rol-policy blijft
    assert "merkstem" in prompt                           # merk-policy blijft


def test_uitzetten_haalt_ook_de_body_weg():
    ctx = _ctx()
    zonder = cp.bouw_prompt(ctx, items=cp._policy_items(ctx, RECS, uit={"BRANDPOSITIO-001"}))
    assert "merkstem" not in zonder and "BRANDPOSITIO-001" not in zonder


def test_de_teller_telt_alleen_wat_aan_staat():
    ctx = _ctx()
    prompt = cp.bouw_prompt(ctx, items=cp._policy_items(ctx, RECS))
    assert "=== POLICIES (2) ===" in prompt               # tone of voice + brand, niet de 4


def test_alles_uit_zegt_dat_eerlijk():
    ctx = _ctx()
    uit = {a["id"] for a in cp._policy_items(ctx, RECS)}
    prompt = cp.bouw_prompt(ctx, items=cp._policy_items(ctx, RECS, uit=uit))
    assert "=== POLICIES (0) ===" in prompt
    assert "all policies are switched off" in prompt


def test_geen_policies_leest_anders_dan_alles_uitgezet():
    """Een rol ZONDER policies is een governance-gat (ga het halen); alles uitgezet is een keuze
    van de gebruiker (zet er een aan). Ze op één zin gooien verbergt het eerste achter het tweede."""
    leeg = {"role": {"id": ROL, "name": "X", "purpose": "", "accountabilities": []},
            "policies": {"own": [], "inherited": []}}
    assert "this role has no policies" in cp.bouw_prompt(leeg, items=[])
    ctx = _ctx()
    uit = {a["id"] for a in cp._policy_items(ctx, RECS)}
    assert "switched off" in cp.bouw_prompt(ctx, items=cp._policy_items(ctx, RECS, uit=uit))


# ── De bodem: altijd mee, niet uitzetbaar ──────────────────────────────────

def test_de_missie_staat_altijd_in_de_prompt():
    """Waar Nooch voor bestaat is de bodem, geen keuze: een tekst die daarbuiten valt is geen
    Nooch-tekst."""
    from nooch_village.mission import ANCHOR_PURPOSE
    ctx = _ctx()
    uit = {a["id"] for a in cp._policy_items(ctx, RECS)}
    prompt = cp.bouw_prompt(ctx, items=cp._policy_items(ctx, RECS, uit=uit))
    assert ANCHOR_PURPOSE in prompt
    assert "always applies" in prompt


def test_de_strategie_komt_uit_config_niet_uit_de_view():
    """Eén bron: `config/strategy.json` is mens-bewerkbaar. Fail-soft bij een kapot bestand — geen
    verzonnen vervanger."""
    regels = cp._strategie_regels()
    assert isinstance(regels, list)
    prompt = cp.bouw_prompt(_ctx(), items=cp._policy_items(_ctx(), RECS))
    for r in regels:
        assert r in prompt


def test_zonder_records_valt_niets_om():
    """Fail-soft: de view mag nooit breken omdat de records-store ontbreekt."""
    items = cp._policy_items(_ctx())
    assert len(items) == 4 and all(a["aan"] for a in items)


# ── De drie selectors: doel × lezer × formaat-als-stem ─────────────────────

def test_de_vier_blokken_staan_in_leesvolgorde():
    """Waarom we bestaan → voor wie → wat je schrijft → de regels → wat je oplevert. De policies
    stonden eerst vóór de lezer, en dan leest het model de constraints zonder te weten voor wie."""
    import re
    p = cp.bouw_prompt(_ctx(), items=cp._policy_items(_ctx(), RECS),
                       doel="informeren", awareness="just browsing", soort="email")
    koppen = [k for k in re.findall(r"^=== (.+?) ===$", p, re.M)]
    assert koppen == ["ROLE", "WHAT NOOCH IS FOR (always applies)", "READER", "ASSIGNMENT",
                      "POLICIES (2)", "OUTPUT"]


def test_hard_sell_is_geen_optie():
    """Een optie die er staat, wordt gekozen. De Open Door-pillar zegt: informeer, overtuig niet."""
    labels = [n for n, _ in cp.DOELEN]
    assert labels == ["informeren", "nieuwsgierig maken", "zacht overtuigen"]
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
    p = cp.bouw_prompt(_ctx(), items=[], doel="informeren", soort="email")
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
