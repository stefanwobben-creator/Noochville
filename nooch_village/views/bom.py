"""BOM — gewicht, kostprijs, CO2e en water per paar (`/bom`, BOM stuk 1, 1 oktober 2026).

Het scherm REKENT NIET ZELF en BEWAART NIETS: `bom_reken.bereken` leest de stuklijst en de
wiki-pagina's bij elke pageload. Komt er een factor op een materiaalpagina bij, dan staat hij de
volgende keer hier — er is geen tweede plek waar hij bijgewerkt moet worden.

LAGEN (atom → molecule → pattern), allemaal bestaand:
  atom      `.kpi-val`, `.muted`, `web_base._status` (vorm + woord), een wiki-link
  molecule  `.tile` met `.tile-h`/`.tile-t` · `table.mtab` met `td.num` · `.card` voor "nog open"
  pattern   dit scherm: vier tegels, de stuklijst, en wat er nog ontbreekt
Geen nieuwe CSS-klasse en geen inline style.
"""
from __future__ import annotations

from nooch_village import bom_reken, wiki
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.data_bom import NOOCH_SCHOEN_BOM
from nooch_village.web_base import _e, _page, _status

#: Tegelkop en eenheid per metriek. De SLEUTELS komen uit `bom_reken.METRIEKEN`.
#: "CO2e" staat in een `<span class='nu-term'>`: `.tile-t` en `th` zetten hun tekst in hoofdletters,
#: en "CO2E" is een andere eenheid. Alleen de term ontsnapt, niet de hele titel (zie UX_PATTERNS).
_CO2E = "<span class='nu-term'>CO2e</span>"
_TEGEL = {"gram": "Total weight", "prijs": "Total cost price", "co2e": f"Total {_CO2E}",
          "water": "Water use"}


def _getal(sleutel: str, x: float | None) -> str:
    if x is None:
        return "—"
    if sleutel == "gram":
        return f"{x:.0f} g"
    if sleutel == "prijs":
        return f"€{x:.2f}"
    if sleutel == "co2e":
        return f"{x:.2f} kg"
    return f"{x:.1f} L"


def _link(pagina, tekst: str) -> str:
    if pagina is None:
        return _e(tekst) if tekst else "—"
    return f"<a href='{_e(wiki.pagina_url(pagina.id))}'>{_e(tekst)}</a>"


def _tegel(sleutel: str, t: dict) -> str:
    # HET "n VAN m" STAAT IN ELKE TEGEL, niet in één regel eronder: de vier totalen tellen elk een
    # ander aantal componenten mee (een gewicht kan er zijn zonder CO2-factor), en één gedeelde
    # regel zou voor drie van de vier tegels niet kloppen.
    som = _getal(sleutel, t["som"]) if t["n"] else "—"
    # `_TEGEL` is vaste markup uit dit bestand (de `nu-term`-span), geen invoer — dus niet escapen.
    return (f"<div class='tile'><div class='tile-h'><span class='tile-t'>{_TEGEL[sleutel]}"
            f"</span></div><div class='kpi-val'>{som}</div>"
            f"<div class='muted'>based on {t['n']} of {t['m']} components</div></div>")


def _rij(r: dict) -> str:
    b = r["bijdrage"]
    cellen = "".join(f"<td class='num'>{_getal(k, b.get(k))}</td>"
                     for k, _g, _w in bom_reken.METRIEKEN)
    status = _status("done", "Complete") if not r["open"] else _status("future", "Open")
    return (f"<tr><td>{_e(r['part'])}</td><td>{_link(r['mat'], r['materiaal'])}</td>"
            f"<td>{_link(r['lev'], r['supplier'])}</td>{cellen}<td>{status}</td></tr>")


def render_bom(st) -> str:
    uit = bom_reken.bereken(NOOCH_SCHOEN_BOM, wiki.paginas(st.att))
    tegels = "".join(_tegel(k, uit["totalen"][k]) for k, _g, _w in bom_reken.METRIEKEN)
    kop = (f"<tr><th>Component</th><th>Material</th><th>Supplier</th><th class='num'>Weight</th>"
           f"<th class='num'>Cost price</th><th class='num'>{_CO2E}</th><th class='num'>Water</th>"
           "<th>Status</th></tr>")
    tabel = f"<table class='mtab'>{kop}{''.join(_rij(r) for r in uit['rijen'])}</table>"
    open_rijen = [r for r in uit["rijen"] if r["open"]]
    nog_open = ""
    if open_rijen:
        items = "".join(f"<li><strong>{_e(r['part'])}</strong> — {_e('; '.join(r['open']))}</li>"
                        for r in open_rijen)
        nog_open = (f"<div class='card'><h3>Still open</h3>"
                    f"<p class='muted'>Fill in the weight in the bill of materials, and add the "
                    f"numbers as a fact with a value on the material page (CO2e, water) or the "
                    f"supplier page (cost price). The totals above pick them up by themselves.</p>"
                    f"<ul>{items}</ul></div>")
    main = (f"<div class='c2-main'><h1 class='ptitle'>BOM · Nooch shoe</h1>"
            f"<p class='muted'>Bill of materials — weight, cost price, CO2e and water per pair. "
            f"Every number comes from the bill of materials or from a wiki page; nothing is "
            f"stored here.</p>"
            f"<div class='c2-sec'><div class='tile-grid'>{tegels}</div></div>"
            f"<div class='c2-sec'>{tabel}</div>{nog_open}</div>")
    return _page("BOM", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
