"""Inzichten — de kennislaag: de gegronde inzicht-kaarten die de Librarian vangt.

De Librarian schrijft reactief een Insight-kaart (notes.json) zodra er gegrond bewijs binnenkomt
(harry_hemp's `keyword_evidence`). Die kaarten werden tot nu toe nergens getoond — ze bestonden alleen
in het bestand. Dit read-only scherm maakt ze zichtbaar: wat is er geleerd, waaruit, en hoe vaak gegrond.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav


def _card(c: dict) -> str:
    # Leest ruwe dicts (niet het Insight-model) zodat schema-drift het scherm nooit laat crashen.
    word = c.get("word") or c.get("concept_id") or "inzicht"
    claim = c.get("claim") or ""
    src = c.get("source") or ""
    date = c.get("source_date") or ""
    gc = c.get("grounding_count") or 1
    ref = c.get("reference") or ""
    if isinstance(ref, str) and ref.startswith("http"):
        reflink = f" · <a href='{_e(ref)}' target='_blank' rel='noopener'>bron</a>"
    else:
        reflink = f" · {_e(str(ref))}" if ref else ""
    tags = "".join(f"<span class='chip outline'>{_e(str(t))}</span>" for t in (c.get("tags") or [])[:5])
    meta = f"{_e(str(src))}{(' · ' + _e(str(date))) if date else ''} · {gc}× gegrond{reflink}"
    return (f"<div class='card'><div class='rdr-sig'>{_e(str(word))}</div>"
            f"<div>{_e(str(claim))}</div>"
            f"<div class='rdr-meta'><span class='muted'>{meta}</span> {tags}</div></div>")


def render_kennislaag(data_dir: str) -> str:
    path = os.path.join(data_dir, "notes.json")
    raw: dict = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = {}
    items = list(raw.values()) if isinstance(raw, dict) else (raw or [])
    cards = [n for n in items
             if isinstance(n, dict) and n.get("claim") and (n.get("word") or n.get("concept_id"))]
    cards.sort(key=lambda n: (-(n.get("grounding_count") or 1), str(n.get("word") or "")))
    rows = "".join(_card(n) for n in cards) or (
        "<p class='muted'>Nog geen inzichten. De Librarian schrijft een kaart zodra er gegrond bewijs "
        "binnenkomt (via harry_hemp). Draait de dorp-puls?</p>")
    main = (f"<div class='c2-main'><h1>Inzichten</h1>"
            f"<p class='muted'>De kennislaag: gegronde inzicht-kaarten die de Librarian ving uit bewijs. "
            f"{len(cards)} kaart(en), gesorteerd op hoe vaak ze gegrond zijn.</p>{rows}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Inzichten", inner)
