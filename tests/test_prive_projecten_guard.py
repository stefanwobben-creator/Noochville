"""Guard: elke plek die projecten LEEST vraagt de privé-regel, of staat hieronder met een reden.

Zelfde idee als de Finance-guard (`test_finance_pr1.test_guard_niemand_anders_leest_finance`): een
nieuwe leesroute of context-opbouwer die projecten gebruikt zonder `project_lezer` /
`mag_project_lezen` / `mag_project_dict_lezen` / `zichtbaar_voor` (of een `leest`-filter dat een
aanroeper meegeeft) laat deze toets falen. Wie hem toevoegt, kiest bewust: de regel erbij, of een
regel op `_UITGEZONDERD` mét reden — en dan leest een reviewer die reden.

WAT "LEZEN" IS: een aanroep van `all`, `get`, `values`, `by_status` of `active` op een store die
`projects` heet (`st.projects.all()`, of een parameter `projects`), of een eigen `ProjectLedger(...)`.

GRENS VAN DE TOETS: hij werkt per FUNCTIE. `do_GET` en `do_POST` zijn één functie voor alle routes;
daar kijkt hij of de regel er staat, niet bij welke route. Een nieuwe route met projecten hoort daarom
een eigen view-functie te krijgen — die toetst hij wel.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"
LEES = {"all", "get", "values", "by_status", "active"}
REGEL = {"project_lezer", "_project_lezer", "mag_project_lezen", "mag_project_dict_lezen", "zichtbaar_voor",
         "leest"}

#: "module:functie" → waarom deze plek de privé-regel niet vraagt. Soorten:
#:   OPEN (n) = een bekend gat, gemeld aan Stefan (11 oktober 2026), nog niet gedicht.
_UITGEZONDERD = {
    # ── opslag en eigen context ──
    "cockpit2.py:__init__": "opslaglaag: _Stores bouwt de ledger",
    "signaal.py:__init__": "opslaglaag: een store-object voor stuur",
    "village.py:__init__": "opslaglaag: de daemon bouwt de ledger",
    "cockpit2.py:_ai_reply": "een AI-rol antwoordt IN het project zelf; de context is dat ene project",
    "cockpit2.py:eigenaar_rol_van_project": "autorisatiehulp: welke rol is eigenaar (geen inhoud naar buiten)",
    # ── schrijfacties op één project (de poort is die van de actie) ──
    "cockpit2.py:_apply_triage": "OPEN (3): schrijfactie op een pid, rechten via de actie, niet via de leesregel",
    "cockpit2.py:_wall_poort": "OPEN (3): schrijfactie op een pid",
    "cockpit2.py:_act_conclusie_naar_wiki": "OPEN (3): kopieert projecttekst naar de wiki (die iedereen leest)",
    "cockpit2.py:_act_vangst_verwerk": "OPEN (3): schrijfactie op een pid",
    "cockpit2.py:_outcome_action": "OPEN (3): schrijfactie op een pid",
    # ── alleen aantallen, geen inhoud ──
    "views/doelen.py:render_goals": "alleen de voortgang (x/y) per doel, geen titels",
    "views/today.py:_doelen": "alleen de voortgang (x/y) per doel, geen titels (zoals /goals)",
    "views/projects.py:_doel_kop": "alleen de voortgang (x/y) van het doel",
    "views/metrics.py:_project_fetch": "alleen aantallen per status / doorlooptijd",
    # ── de aanroeper heeft de regel al gevraagd ──
    "views/projects.py:render_project": "de route /project vraagt _project_lezer vóór het renderen",
    "views/acties.py:_projectnaam": "naam bij een actie die al door zichtbaar_voor ging",
    "views/messages.py:_label": "label van een kanaal dat al door mag_kanaal_lezen ging",
    "views/messages.py:_projectkanalen_met_gesprek": "de lijst wordt daarna door mag_kanaal_lezen gefilterd",
    "views/messages.py:_bericht": "OPEN (4): een bericht dat de lezer mag zien kan naar een privé-project verwijzen (titel)",
    # ── dood: geen aanroeper ──
    "cockpit2.py:_scoped_project_opts": "dood: geen aanroeper",
    "views/feed.py:_wall_outcome_opts": "dood: geen aanroeper",
    "views/vangst.py:_project_opties": "dood: geen aanroeper",
    # ── LLM-context en memo's ──
    "noochie_memo.py:projecten": "OPEN (1): Noochie-memo bevat projecttitels en -stand van alle projecten",
    "noochie_memo.py:_rol_activiteit": "OPEN (1): Noochie-memo, activiteit per rol (telt projecten)",
    "skills_impl/weten_we_dit_al.py:run": "OPEN (5): skill vergelijkt met alle projecten; uitkomst landt in een ander project",
    # ── meldingen van de daemon ──
    "vastgelopen_route.py:pas": "OPEN (2): meldt vastgelopen projecten aan een mens die geen lid hoeft te zijn",
    "village.py:_meld_weesprojecten": "OPEN (2): meldt weesprojecten",
    "founder_kaart.py:opwerper": "OPEN (2): de founder-kaart noemt de eigenaar-rol van het project",
    # ── daemon-ritme en systeemwerk (geen mens leest de projecten hier) ──
    "board_loop.py:_root": "daemon: bord-ritme",
    "board_loop.py:activate_pulse": "daemon: bord-ritme",
    "board_loop.py:board_active": "daemon: bord-ritme",
    "board_loop.py:role_active": "daemon: bord-ritme",
    "discovery_board.py:ensure_root": "daemon: discovery-bord",
    "discovery_board.py:root_active": "daemon: discovery-bord",
    "discovery_board.py:ensure_experiment": "daemon: discovery-bord",
    "discovery_board.py:run_role": "daemon: discovery-bord",
    "afslank_afhankelijkheden.py:open_projecten": "analyse voor afslanken (CLI/mens-gated plan)",
    "afslank_wezen.py:wezen": "analyse voor afslanken (CLI)",
    "afslanken.py:voer_uit": "CLI: afslankplan uitvoeren",
    "radar_archief.py:voer_uit": "CLI: opruiming",
    "voorstel_opruiming.py:voer_uit": "CLI: opruiming",
    "waarde_audit.py:rapport_tekst": "CLI: rapport voor de operator",
    "orphan_report.py:find_orphans": "CLI: rapport voor de operator",
    "cli.py:main": "CLI op de server (operator)",
    "demos/ops.py:discovery_demo": "demo",
}


def _leest(node):
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr in LEES:
            v = f.value
            if (isinstance(v, ast.Attribute) and v.attr == "projects") or (isinstance(v, ast.Name) and v.id == "projects"):
                yield n.lineno
        if isinstance(f, ast.Name) and f.id == "ProjectLedger":
            yield n.lineno


def _namen(node) -> set[str]:
    return ({n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            | {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            | {a.arg for n in ast.walk(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               for a in n.args.args + n.args.kwonlyargs})


def _lezers() -> dict[str, bool]:
    """{"module:functie": vraagt de regel} voor elke functie die zelf projecten leest."""
    uit = {}
    for f in sorted(ROOT.rglob("*.py")):
        if f == ROOT / "projects.py":
            continue                                   # de store zelf
        boom = ast.parse(f.read_text(encoding="utf-8"))
        for fn in ast.walk(boom):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            binnen = [g for g in ast.walk(fn) if g is not fn and isinstance(g, (ast.FunctionDef, ast.AsyncFunctionDef))]
            regels = [r for r in _leest(fn) if not any(g.lineno <= r <= g.end_lineno for g in binnen)]
            if regels:
                uit[f"{f.relative_to(ROOT)}:{fn.name}"] = bool(_namen(fn) & REGEL)
    return uit


def test_elke_projectlezer_vraagt_de_regel_of_staat_op_de_lijst_met_reden():
    zonder = sorted(k for k, ok in _lezers().items() if not ok and k not in _UITGEZONDERD)
    assert zonder == [], ("deze functies lezen projecten zonder de privé-regel (project_lezer / "
                          "mag_project_lezen) en staan niet op _UITGEZONDERD: " + ", ".join(zonder))


def test_de_lijst_veroudert_niet():
    """Een uitzondering die niet meer leest (of de regel inmiddels wél vraagt) moet eraf: anders
    groeit de lijst en dekt hij straks een nieuwe lezer met dezelfde naam."""
    lezers = _lezers()
    oud = sorted(k for k in _UITGEZONDERD if k not in lezers or lezers[k])
    assert oud == [], "haal deze van _UITGEZONDERD: " + ", ".join(oud)


def test_de_toets_ziet_een_nieuwe_lezer(tmp_path, monkeypatch):
    """Zonder deze toets bewijst de guard niets: hij moet een lezer zonder regel echt vinden."""
    boom = ast.parse("def nieuw(st):\n    return [p['scope'] for p in st.projects.all()]\n"
                     "def goed(st, username):\n    l = project_lezer(st, username)\n"
                     "    return [p for p in st.projects.all() if l(p)]\n")
    fns = {f.name: f for f in boom.body}
    assert list(_leest(fns["nieuw"])) and not (_namen(fns["nieuw"]) & REGEL)
    assert list(_leest(fns["goed"])) and (_namen(fns["goed"]) & REGEL)
