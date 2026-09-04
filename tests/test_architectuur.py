"""Guard: docs/ARCHITECTUUR.md is AUTOMATISCH afgeleid en mag niet verouderen. Deze test regenereert
de vindkaart en vergelijkt met het gecommitte bestand — faalt zodra een nieuwe route/actie/store is
toegevoegd (of het bestand handmatig is bewerkt) zonder `python -m nooch_village.arch_map` + commit."""
from __future__ import annotations
import os
import re

from nooch_village import arch_map

_DOC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "ARCHITECTUUR.md")
_PKG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village")


def test_architectuur_md_is_actueel():
    generated = arch_map.render_markdown()
    committed = open(_DOC, encoding="utf-8").read()
    assert committed == generated, (
        "docs/ARCHITECTUUR.md is verouderd of handmatig bewerkt. "
        "Draai `python -m nooch_village.arch_map` en commit het resultaat.")


def test_tabellen_niet_leeg_en_kern_aanwezig():
    routes = dict((r, h) for r, h, _v in arch_map.routes())
    assert routes.get("/node") == "render_node" and routes.get("/kpi_new") == "render_kpi_composer"
    acties = dict(arch_map.dispatch_actions())
    assert "tile_add" in acties and "catalog_publish" in acties and len(acties) > 50
    stores = {c: (k, f) for c, k, f in arch_map.stores()}
    assert stores["observations"] == ("ObservationStore", "observations.jsonl")
    assert stores["metrics"][1] == "metrics.json"


def test_geen_twee_renderers_met_dezelfde_naam():
    """Twee `render_x` met dezelfde naam is een val met twee bekken.

    HET GEVAL (4 sep 2026, #444): `views/rapport.py` kreeg een `render_rapport` terwijl
    `views/claims.py` die naam al had. `cockpit2` importeert beide; de tweede import overschreef
    stil de eerste, dus de claims-aanroep `render_rapport(uitslag, markten=…)` riep de PROJECT-
    renderer aan met `uitslag` als `st`. De volle suite bleef groen — dat pad had geen test.

    En de architectuurkaart raakte er OS-afhankelijk van: `arch_map._render_def_index` doet
    `setdefault` over `os.walk`, dus bij een dubbele naam wint het bestand dat het bestandssysteem
    het eerst teruggeeft. Op APFS was dat de ene, op de Linux-runner de andere — groen bij mij,
    rood in CI. Deze test faalt op de oorzaak in plaats van op het symptoom.
    """
    import collections
    namen = collections.defaultdict(list)
    for base, dirs, files in os.walk(_PKG):
        dirs.sort()
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            full = os.path.join(base, fn)
            with open(full, encoding="utf-8") as fh:
                for ln in fh:
                    m = re.match(r"\s*def (render_\w+)\(", ln)
                    if m:
                        namen[m.group(1)].append(os.path.relpath(full, _PKG))
    dubbel = {n: sorted(set(f)) for n, f in namen.items() if len(set(f)) > 1}
    assert not dubbel, (
        f"renderer-namen in meer dan één bestand: {dubbel}. Geef ze een eigen naam — "
        f"cockpit2 importeert ze plat, dus de laatste import wint stil.")
