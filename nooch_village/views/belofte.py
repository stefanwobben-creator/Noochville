"""Belofte-graaf-scherm — de eerste-principes-ontleding van een belofte, zichtbaar van kaal
naar rijp.

Een belofte ("de schoen is duurzaam") valt uiteen in constituenten (de BOM-onderdelen). Elk
onderdeel krijgt na gronden een oordeel: houdt / houdt-niet / onbekend. De belofte is zo sterk
als haar zwakste constituent (weakest link). Dit scherm toont per belofte de gereconstrueerde
sterkte, de bottleneck (waar hij breekt of nog gapt) en per onderdeel het oordeel plus de
eventuele duurzame alternatieven. Stap 1: read-only, de graaf zien groeien. Het gronden
(scientist velt oordelen) en de pull volgen als stap 2.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.belofte_graaf import Oordeel, Sterkte, weeg_belofte

# Display-mapping: de sleutels blijven de opgeslagen enum-waarden, alleen het label is Engels.
_OORDEEL_CHIP = {
    Oordeel.HOUDT.value: ("chip green", "holds"),
    Oordeel.HOUDT_NIET.value: ("chip coral", "does not hold"),
    Oordeel.ONBEKEND.value: ("chip outline", "unknown"),
}
_STERKTE_CHIP = {
    Sterkte.VERDEDIGBAAR.value: ("chip green", "defensible"),
    Sterkte.ONBEWEZEN.value: ("chip amber", "unproven"),
    Sterkte.GEBROKEN.value: ("chip coral", "broken"),
    Sterkte.LEEG.value: ("chip outline", "empty"),
}


def _oordelen(entry: dict) -> dict[str, Oordeel]:
    geldig = {o.value for o in Oordeel}
    return {r["naam"]: Oordeel(r["oordeel"]) if r.get("oordeel") in geldig else Oordeel.ONBEKEND
            for r in entry.get("constituenten", [])}


def _load(data_dir: str) -> dict:
    path = os.path.join(data_dir, "belofte_grafen.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _sterkte_chip(sterkte: Sterkte) -> str:
    cls, label = _STERKTE_CHIP.get(sterkte.value, ("chip outline", sterkte.value))
    return f"<span class='{cls}'>{_e(label)}</span>"


def _rijpheid(entry: dict) -> tuple[int, int]:
    """Hoeveel constituenten zijn gegrond (oordeel != onbekend) t.o.v. het totaal."""
    rijen = entry.get("constituenten", [])
    gegrond = sum(1 for r in rijen if r.get("oordeel") and r["oordeel"] != Oordeel.ONBEKEND.value)
    return gegrond, len(rijen)


def _lijst(data: dict) -> str:
    kaarten = []
    for bid, entry in sorted(data.items()):
        weging = weeg_belofte(_oordelen(entry))
        gegrond, totaal = _rijpheid(entry)
        bottleneck = weging.bottleneck
        bn = (f"<p class='muted'>Bottleneck: {len(bottleneck)} component(s), "
              f"incl. {_e(', '.join(bottleneck[:3]))}</p>") if bottleneck else \
             "<p class='muted'>No bottleneck: every constituent holds.</p>"
        kaarten.append(
            f"<div class='card'><h3><a href='/belofte?id={_e(bid)}'>{_e(entry.get('belofte') or bid)}</a></h3>"
            f"<p>{_sterkte_chip(weging.sterkte)} "
            f"<span class='muted'>{gegrond}/{totaal} grounded</span></p>{bn}</div>")
    if not kaarten:
        return "<p class='muted'>No promise graphs yet. The BOM seed fills the shoe graph at startup.</p>"
    return "".join(kaarten)


def _detail(bid: str, entry: dict) -> str:
    weging = weeg_belofte(_oordelen(entry))
    gegrond, totaal = _rijpheid(entry)
    bottleneck = set(weging.bottleneck)
    rijen = []
    for r in entry.get("constituenten", []):
        cls, label = _OORDEEL_CHIP.get(r.get("oordeel"), ("chip outline", "unknown"))
        alt = ", ".join(r.get("alternatieven") or []) or "—"
        merk = " ◀ bottleneck" if r["naam"] in bottleneck else ""
        rijen.append(
            f"<tr><td>{_e(r['naam'])}{_e(merk)}</td>"
            f"<td>{_e(r.get('realisatie') or '—')}</td>"
            f"<td>{_e(alt)}</td>"
            f"<td><span class='{cls}'>{_e(label)}</span></td></tr>")
    tabel = (f"<table class='mtab'><tr><th>Component</th><th>Realisation</th>"
             f"<th>Sustainable alternative</th><th>Verdict</th></tr>{''.join(rijen)}</table>")
    bn = (f"<p class='muted'>The promise breaks or gaps on: "
          f"<b>{_e(', '.join(weging.bottleneck))}</b>.</p>") if weging.bottleneck else \
         "<p class='muted'>Every constituent holds: the promise is defensible in theory.</p>"
    return (f"<div class='c2-main'><div class='c2-bar'><a href='/belofte'>← all promises</a></div>"
            f"<h1>{_e(entry.get('belofte') or bid)}</h1>"
            f"<p>{_sterkte_chip(weging.sterkte)} "
            f"<span class='muted'>maturity {gegrond}/{totaal} constituents grounded</span></p>{bn}"
            f"<p class='muted'>First principles: the promise breaks down into its components; each "
            f"component is grounded separately; the promise is only as strong as its weakest component. "
            f"As long as a component is unknown, the promise is unproven, not broken.</p>{tabel}</div>")


def render_belofte(data_dir: str, belofte_id: str = "") -> str:
    data = _load(data_dir)
    if belofte_id and belofte_id in data:
        main = _detail(belofte_id, data[belofte_id])
    elif belofte_id:
        main = ("<div class='c2-main'><div class='c2-bar'><a href='/belofte'>← all promises</a></div>"
                "<p class='muted'>Unknown promise.</p></div>")
    else:
        main = (f"<div class='c2-main'><h1>Promises &amp; first principles</h1>"
                f"<p class='muted'>Every promise broken down into its constituents and weighed on the "
                f"weakest component. Click through for the graph per promise.</p>{_lijst(data)}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Promises", inner)
