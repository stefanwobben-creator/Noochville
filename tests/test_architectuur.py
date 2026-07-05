"""Guard: docs/ARCHITECTUUR.md is AUTOMATISCH afgeleid en mag niet verouderen. Deze test regenereert
de vindkaart en vergelijkt met het gecommitte bestand — faalt zodra een nieuwe route/actie/store is
toegevoegd (of het bestand handmatig is bewerkt) zonder `python -m nooch_village.arch_map` + commit."""
from __future__ import annotations
import os

from nooch_village import arch_map

_DOC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "ARCHITECTUUR.md")


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
