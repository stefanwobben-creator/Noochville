"""Architectuur-vindkaart — AUTOMATISCH afgeleid uit de bron, niet handmatig overgetypt.

Leidt drie tabellen af uit de daadwerkelijke code:
  (a) Route → handler → view    (uit do_GET in cockpit2.py + de def render_* in de views)
  (b) Dispatch-actie → regel     (uit de if/elif action-keten in dispatch())
  (c) Concern → store → bestand  (uit _Stores.__init__)

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


def dispatch_actions() -> list[tuple[str, int]]:
    """(actie, regelnr in cockpit2.py) uit de if/elif action-keten in dispatch(), in bronvolgorde."""
    out = []
    for i, ln in enumerate(_lines(_COCKPIT2)):
        m = re.match(r"\s*(?:if|elif) action == \"([^\"]+)\":", ln)
        if m:
            out.append((m.group(1), i + 1))
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


def _table(headers: list[str], rows: list[tuple]) -> str:
    sep = "| " + " | ".join(headers) + " |\n"
    sep += "|" + "|".join(["---"] * len(headers)) + "|\n"
    for r in rows:
        sep += "| " + " | ".join(f"`{c}`" if c else "—" for c in r) + " |\n"
    return sep


def render_markdown() -> str:
    """Het volledige docs/ARCHITECTUUR.md — volledig gegenereerd, byte-voor-byte reproduceerbaar."""
    rt, ac, sto = routes(), dispatch_actions(), stores()
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
        "\n## (b) Dispatch-actie → regel\n",
        "De POST-acties uit de `dispatch()`-keten (cockpit2.py). Elke actie is één `if/elif "
        "action == \"…\"`-tak; het regelnummer wijst naar het begin ervan.\n",
        _table(["Actie", "cockpit2.py:regel"], [(a, f"cockpit2.py:{n}") for a, n in ac]),
        "\n## (c) Concern → store → bestand\n",
        "De stores uit `_Stores.__init__` (cockpit2.py): het attribuut (de handle), de store-klasse "
        "en het databestand in `data/` (gitignored).\n",
        _table(["Concern (st.…)", "Store-klasse", "Databestand"], sto),
        f"\n---\n_{len(rt)} routes · {len(ac)} dispatch-acties · {len(sto)} stores._\n",
    ]
    return "\n".join(parts)


def write() -> str:
    path = os.path.join(_ROOT, "docs", "ARCHITECTUUR.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_markdown())
    return path


if __name__ == "__main__":
    print("✅ geschreven:", write())
