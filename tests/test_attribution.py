"""Attributie: koppel verkoop (via landingspagina) terug aan de doelwit-woorden, en toon dat
per woord in de cockpit-woordenschat. Puur, deterministisch."""
from __future__ import annotations
import json

from nooch_village.attribution import attribute_keywords



def test_attribute_basis():
    pages = [("/blogs/vegan/sneakers", 30), ("/collections/barefoot-shoes", 12)]
    kw = ["vegan sneakers", "barefoot shoes", "leren tas"]
    out = attribute_keywords(pages, kw)
    assert out["vegan sneakers"] == 30 and out["barefoot shoes"] == 12
    assert "leren tas" not in out


def test_attribute_enkelvoud_meervoud_en_drempel():
    # 'sneaker' in pad matcht 'sneakers' (prefix), 'dames' ook → 2/3 ≥ 0.5
    pages = [("/products/vegan-sneaker-dames-groen", 5)]
    assert attribute_keywords(pages, ["vegan sneakers dames"]) == {"vegan sneakers dames": 5}
    # één toevallig woord ('vegan') is te weinig voor een 3-woord-keyword → geen match
    assert attribute_keywords([("/blogs/vegan-leven", 9)], ["vegan sneakers dames"]) == {}


def test_attribute_een_pagina_een_woord():
    # pagina telt bij het sterkst overlappende woord, niet dubbel
    pages = [("/vegan-sneakers-dames", 4)]
    out = attribute_keywords(pages, ["vegan sneakers", "vegan sneakers dames"])
    assert sum(out.values()) == 4 and out.get("vegan sneakers dames") == 4


