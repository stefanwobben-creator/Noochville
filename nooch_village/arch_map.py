"""Architectuur-vindkaart — AUTOMATISCH afgeleid uit de bron, niet handmatig overgetypt.

Leidt drie tabellen af uit de daadwerkelijke code:
  (a) Route → handler → view    (uit do_GET in cockpit2.py + de def render_* in de views)
  (b) Dispatch-actie → regel     (uit de if/elif action-keten in dispatch())
  (c) Concern → store → bestand  (uit _Stores.__init__)
  (d) Store buiten _Stores       (uit schrijfgedrag per module: wie schrijft welk databestand)

`render_markdown()` bouwt het volledige docs/ARCHITECTUUR.md. `python -m nooch_village.arch_map`
schrijft het weg. Een guard-test (tests/test_architectuur.py) regenereert en vergelijkt met het
gecommitte bestand, zodat het document niet kan verouderen zonder dat het zichtbaar (rood) wordt.
"""
from __future__ import annotations
import os
import re

_PKG = os.path.dirname(__file__)
_ROOT = os.path.dirname(_PKG)
_COCKPIT2 = os.path.join(_PKG, "cockpit2.py")


def _lines(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def _render_def_index() -> dict[str, str]:
    """{render_functienaam: repo-relatief bestand} — waar elke view-renderer gedefinieerd is."""
    index: dict[str, str] = {}
    for base, _dirs, files in os.walk(_PKG):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(base, fn)
            rel = os.path.relpath(full, _ROOT)
            for ln in _lines(full):
                m = re.match(r"\s*def (render_\w+)\(", ln)
                if m:
                    index.setdefault(m.group(1), rel)
    return index


def routes() -> list[tuple[str, str, str]]:
    """(route, handler, view-bestand) uit do_GET in cockpit2.py, in bronvolgorde."""
    src = _lines(_COCKPIT2)
    idx = _render_def_index()
    # Scope tot de do_GET-methode (POST-routes horen niet in deze GET-tabel).
    starts = [i for i, ln in enumerate(src) if re.match(r"\s*def do_GET\(", ln)]
    ends = [i for i, ln in enumerate(src) if re.match(r"\s*def do_POST\(", ln)]
    lo = starts[0] if starts else 0
    hi = next((e for e in ends if e > lo), len(src))
    src = src[:hi]                      # knip alles ná do_GET weg (routes staan binnen do_GET)
    hits = []  # (regelnr, [paden])
    for i in range(lo, len(src)):
        ln = src[i]
        m = re.match(r"\s*if path == \"([^\"]+)\":", ln)
        if m:
            hits.append((i, [m.group(1)]))
            continue
        m = re.match(r"\s*if path in \(([^)]*)\):", ln)
        if m:
            paths = re.findall(r"\"([^\"]+)\"", m.group(1))
            hits.append((i, paths))
    out = []
    for n, (line_i, paths) in enumerate(hits):
        end = hits[n + 1][0] if n + 1 < len(hits) else min(line_i + 40, len(src))
        body = "\n".join(src[line_i + 1:end])
        rm = re.search(r"\b(render_\w+)\(", body)
        handler = rm.group(1) if rm else "(inline)"
        view = idx.get(handler, "cockpit2.py" if handler == "(inline)" else "?")
        for p in paths:
            out.append((p, handler, view))
    return out


def dispatch_actions() -> list[tuple[str, str]]:
    """(actie, handlernaam) uit de ACTIONS-registry, in registervolgorde.
    Elke actie wijst naar zijn `_act_*`-handlerfunctie; gegroepeerde acties delen één handler.

    HIER STOND EEN REGELNUMMER, en dat was het enige veld in deze kaart dat verandert zonder dat de
    architectuur verandert. Eén regel toevoegen bovenin cockpit2.py verschoof 200 tabelregels, en
    dat maakte elke parallelle PR die cockpit2.py aanraakt conflicterend — op 18 sept 2026 twee keer
    op één dag. De handlernaam wijst net zo goed: `grep -n "def _act_tile_add" cockpit2.py`."""
    src = _lines(_COCKPIT2)
    out, in_reg = [], False
    for ln in src:
        if re.match(r"ACTIONS = \{", ln):
            in_reg = True
            continue
        if in_reg and ln.startswith("}"):
            break
        m = re.match(r'\s*"([^"]+)": (_act_\w+),', ln)
        if in_reg and m:
            out.append((m.group(1), m.group(2)))
    return out


def stores() -> list[tuple[str, str, str]]:
    """(concern/attribuut, store-klasse, databestand) uit _Stores.__init__, in bronvolgorde."""
    out, in_stores = [], False
    for ln in _lines(_COCKPIT2):
        if re.match(r"\s*class _Stores", ln):
            in_stores = True
            continue
        if in_stores and re.match(r"\s*(class |def _bootstrap)", ln):
            break
        m = re.match(r"\s*self\.(\w+) = ([\w.]+)\(os\.path\.join\(dd, \"([^\"]+)\"\)", ln)
        if in_stores and m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


#: Wat als SCHRIJVEN telt. Bewust patronen en geen stringliterals: een bestandsnaam in een module
#: zegt alleen dat hij hem KENT, en de meeste noemers zijn lezers. Op 18 sept 2026 zou een scan op
#: literals 51 lezers als ontbrekende store hebben aangewezen — dezelfde leugen als een halve lijst,
#: alleen andersom.
#:
#: `open(...)` mag geneste haakjes bevatten, want `open(pad(data_dir), "a")` is hier de gangbare
#: vorm; zonder die nesting miste de eerste versie zijn eigen voorbeeld (`decision_sheets.py`).
_SCHRIJF_PATRONEN = (
    r'open\((?:[^()]|\([^()]*\))*,\s*["\'][aw]',       # open(..., "a"/"w")
    r"atomic_write_json\(",                             # de veilige json-schrijver
    r"class \w+\(JsonStore\)",                          # een eigen store-klasse
    r"_WRITE_METHODS\s*=",                              # JsonStore's schrijf-declaratie
)

_DATABESTAND_RE = re.compile(r"""["']([a-z_0-9]+\.jsonl?)["']""")


def _modules() -> dict[str, str]:
    """Elke module in het pakket met zijn broncode (geen subpakketten: die bezitten geen stores)."""
    uit = {}
    for f in sorted(os.listdir(_PKG)):
        if f.endswith(".py"):
            with open(os.path.join(_PKG, f), encoding="utf-8") as fh:
                uit[f] = fh.read()
    return uit


def data_files() -> dict[str, list]:
    """Elk databestand buiten `_Stores`, ingedeeld naar wat over zijn eigenaar af te leiden is.

    Drie bakken, en de derde en vierde staan er OMDAT ze er staan: een lijst die doet alsof hij
    compleet is, is erger dan een lijst met een zichtbaar gat. Wie hier niets vindt moet kunnen zien
    dát er niets te vinden was, niet denken dat het bestand niet bestaat.

      eigenaar  — precies één module die deze naam noemt én schrijft
      meerdere  — meer dan één schrijver; welke de eigenaar is, is niet af te leiden
      geen      — niemand die hem aantoonbaar schrijft (lees-only config, of geschreven buiten
                  het pakket, bijvoorbeeld in een exportpakket)
    """
    in_c = {b for _, _, b in stores()}
    pats = [re.compile(p) for p in _SCHRIJF_PATRONEN]
    src = _modules()
    schrijvers = {f for f, code in src.items() if any(p.search(code) for p in pats)}
    per: dict[str, set] = {}
    for f, code in src.items():
        for b in set(_DATABESTAND_RE.findall(code)):
            per.setdefault(b, set())
            if f in schrijvers:
                per[b].add(f)
    eigenaar, meerdere, geen = [], [], []
    for b, wie in sorted(per.items()):
        if b in in_c:
            continue                                     # staat al in sectie (c)
        w = sorted(wie)
        if len(w) == 1:
            eigenaar.append((b, w[0]))
        elif w:
            meerdere.append((b, ", ".join(w)))
        else:
            geen.append((b,))
    return {"eigenaar": eigenaar, "meerdere": meerdere, "geen": geen}


def _table(headers: list[str], rows: list[tuple]) -> str:
    sep = "| " + " | ".join(headers) + " |\n"
    sep += "|" + "|".join(["---"] * len(headers)) + "|\n"
    for r in rows:
        sep += "| " + " | ".join(f"`{c}`" if c else "—" for c in r) + " |\n"
    return sep


def render_markdown() -> str:
    """Het volledige docs/ARCHITECTUUR.md — volledig gegenereerd, byte-voor-byte reproduceerbaar."""
    rt, ac, sto, df = routes(), dispatch_actions(), stores(), data_files()
    parts = [
        "# NoochVille — Architectuur-vindkaart\n",
        "> **Automatisch gegenereerd** door `nooch_village/arch_map.py`. NIET handmatig bewerken —\n"
        "> draai `python -m nooch_village.arch_map` en commit. De guard-test\n"
        "> `tests/test_architectuur.py` faalt zodra dit bestand verouderd is (nieuwe route/actie/store\n"
        "> zonder regenereren). Zie de regel hierover in `CLAUDE.md`.\n",
        "## (a) Route → handler → view\n",
        "De GET-routes uit `do_GET` (cockpit2.py) en de view die ze renderen. `(inline)` = geen "
        "aparte `render_*`, de response wordt in cockpit2 zelf opgebouwd.\n",
        _table(["Route", "Handler", "View-bestand"], rt),
        "\n## (b) Dispatch-actie → handler\n",
        "De POST-acties uit de `ACTIONS`-registry (cockpit2.py). Elke actie wijst naar zijn "
        "`_act_*`-handlerfunctie in `cockpit2.py`; gegroepeerde acties delen één handler. Bewust "
        "géén regelnummer: dat verandert bij elke regel die erboven wordt toegevoegd, zonder dat de "
        "architectuur verandert.\n",
        _table(["Actie", "Handler (cockpit2.py)"], ac),
        "\n## (c) Concern → store → bestand\n",
        "De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse "
        "en het databestand in `data/` (gitignored).\n",
        _table(["Concern (st.…)", "Store-klasse", "Databestand"], sto),
        "\n## (d) Databestand → schrijvende module (buiten `_Stores`)\n",
        "Sectie (c) dekt alleen de stores die als handle op `_Stores` hangen — ongeveer de helft van "
        "de schrijvende opslag. De rest woont in losse modules. **Deze lijst is afgeleid uit "
        "SCHRIJFGEDRAG**: een module telt als schrijver als hij de bestandsnaam noemt én ergens "
        "`open(..., \"a\"/\"w\")`, de veilige json-schrijver, een `JsonStore`-subklasse of "
        "`_WRITE_METHODS` bevat. Een module die de naam alleen noemt is een lezer en staat hier "
        "niet.\n",
        _table(["Databestand", "Schrijvende module"], df["eigenaar"]),
        "\n### (d2) Meerdere schrijvers — eigenaarschap niet af te leiden\n",
        "Meer dan één module schrijft dit bestand. Dat is geen fout, maar de kaart kan niet zeggen "
        "wie de eigenaar is; dat blijft mensenwerk.\n",
        _table(["Databestand", "Schrijvende modules"], df["meerdere"]),
        "\n### (d3) Geen schrijver gevonden\n",
        "Genoemd in het pakket, maar niemand schrijft hem aantoonbaar: lees-only configuratie, of "
        "geschreven buiten het pakket (bijvoorbeeld in een exportpakket). Staat hier zodat het gat "
        "zichtbaar is in plaats van weggelaten.\n",
        _table(["Databestand"], df["geen"]),
        f"\n---\n_{len(rt)} routes · {len(ac)} dispatch-acties · {len(sto)} stores in `_Stores` · "
        f"{len(df['eigenaar'])} daarbuiten met één schrijver · {len(df['meerdere'])} met meerdere · "
        f"{len(df['geen'])} zonder gevonden schrijver._\n",
    ]
    return "\n".join(parts)


def write() -> str:
    path = os.path.join(_ROOT, "docs", "ARCHITECTUUR.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_markdown())
    return path


if __name__ == "__main__":
    print("✅ geschreven:", write())
