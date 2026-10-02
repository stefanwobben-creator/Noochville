"""BOM — gewicht, kostprijs, CO2e en water per paar (`/bom`, BOM stuk 1, 1 oktober 2026).

Het scherm REKENT NIET ZELF en BEWAART NIETS: `bom_reken.bereken` leest de stuklijst en de
wiki-pagina's bij elke pageload. Komt er een factor op een materiaalpagina bij, dan staat hij de
volgende keer hier — er is geen tweede plek waar hij bijgewerkt moet worden.

LAGEN (atom → molecule → pattern), allemaal bestaand:
  atom      `.kpi-val`, `.muted`, `web_base._status` (vorm + woord), een wiki-link
  molecule  `.tile` met `.tile-h`/`.tile-t` · `table.mtab` met `td.num` · `.card` voor "nog open"
            · de Supplier-cel: `details.acard-d` > `summary.chip.outline` + `.datepop` met een
              formulier — PRECIES de Deadline-cel van de projectrail (`views/projects.py`)
  pattern   dit scherm: vier tegels, de stuklijst, en wat er nog ontbreekt
Geen nieuwe CSS-klasse en geen inline style.

ÉÉN ding is hier te wijzigen (Correctie 2, 2 oktober 2026): welke leverancier een MATERIAAL levert.
Die koppeling woont in `bom_leveranciers`; de Supplier-cel is er de ingang voor, en verschijnt als
formulier alleen voor wie mag (houder van het domein `Materials` of Circle Lead).
"""
from __future__ import annotations

from nooch_village import artefacts, bom_leveranciers, bom_reken, wiki
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.data_bom import NOOCH_SCHOEN_BOM
from nooch_village.web_base import _banner, _e, _page, _status

#: id van de suggestielijst met bestaande wiki-titels; één `<datalist>` per pagina, elke
#: Supplier-cel verwijst ernaar.
_LIJST_ID = "bom-lev-opties"

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


def _mag_koppelen(st, username: str | None) -> bool:
    """Dezelfde vraag als de poort van `bom_leverancier_zet`, zodat het scherm geen knop toont die
    de server daarna weigert. Guest (auth uit) mag alles, zoals overal in de cockpit."""
    if username == "guest":
        return True
    actor = st.people.by_email(username) if username else None
    if actor is None:
        return False
    from nooch_village import org
    from nooch_village.cockpit2 import resolve_circle_id
    houder = org.role_for_domain(st.records.all(), bom_leveranciers.DOMEIN)
    cirkel = resolve_circle_id(houder.id, st.records) if houder is not None else ""
    return artefacts.mag_schrijven_op_domein(st, bom_leveranciers.DOMEIN, actor.id,
                                             circle_id=cirkel or "")


def _maat_kiezer(maat: int, cfg: dict) -> str:
    """De maat als keuzebalk: `.cl-bar` met `a.cl-filter` en `.on` — het bestaande vocabulaire voor
    een filter-/periode-keuze (UX_PATTERNS, Kern-klassen), geen nieuwe vorm. Hij bepaalt alleen
    WELKE geschaalde waarden je ziet; er wordt niets opgeslagen.

    GEEN DROPDOWN, al noemde de correctie die als voorbeeld. Het `cardmenu` van `/metrics` klapt naar
    links uit (daar staat hij rechts op het scherm); hier, links op de pagina, viel het menu half
    achter de zijbalk. Elf maten passen op één regel, en dan zie je ook meteen waar je staat."""
    opties = " ".join(
        f"<a class='cl-filter{' on' if m == maat else ''}' href='/bom?maat={m}'"
        f"{' aria-current=' + chr(39) + 'true' + chr(39) if m == maat else ''}"
        f"{' title=' + chr(39) + 'reference size' + chr(39) if m == cfg['referentiemaat'] else ''}>{m}</a>"
        for m in cfg["maten"])
    return f"<div class='cl-bar' aria-label='EU size'><span class='muted'>EU size</span> {opties}</div>"


def _schatting(maat: int, cfg: dict) -> str:
    """WAT DE MAAT DOET, en dat het een schatting is — op de pagina, niet in een tooltip. Het getal
    zelf komt uit de config (`bom_reken.maat_config`), nooit uit deze tekst."""
    if not cfg:
        return ("<p class='muted'>Size scaling is unavailable (no readable config/bom_maten.json); "
                "the quantities are the reference values.</p>")
    pct = f"{cfg['schaal_per_maat'] * 100:g}%"
    ref = cfg["referentiemaat"]
    waar = (f"the reference size {ref}" if maat == ref else
            f"size {maat}, scaled from reference size {ref} by {pct} per size step")
    return (f"<p class='muted'>Quantities for {waar}. The scaling is a provisional assumption, "
            f"not yet based on factory data ({_e(cfg['bron'])}, {_e(cfg['datum'])}).</p>")


def _leverancier_cel(r: dict, csrf_token: str, bewerk: bool, terug: str = "/bom") -> str:
    """Lezen: de leverancier als link (of tekst, of —). Bewerken: dezelfde chip als de Deadline op de
    projectrail, die openklapt naar een formulier. Het veld stelt bestaande wiki-titels voor, maar
    accepteert elke naam: een leverancier mag gekoppeld worden vóór iemand zijn pagina schrijft."""
    lees = _link(r["lev"], r["supplier"])
    if not bewerk:
        return lees
    label = _e(r["supplier"]) if r["supplier"] else "+ link supplier"
    weg = (f"<button class='dellink' type='submit' name='leverancier' value=''>remove</button>"
           if r["supplier"] else "")
    return (f"<details class='acard-d'><summary class='chip outline'>{label}</summary>"
            f"<div class='datepop'><form method='post' action='/action'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='action' value='bom_leverancier_zet'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>"
            f"<input type='hidden' name='materiaal' value='{_e(r['materiaal'])}'>"
            f"<input name='leverancier' value='{_e(r['supplier'])}' list='{_LIJST_ID}' "
            f"aria-label='supplier of {_e(r['materiaal'])}' placeholder='Supplier name'>"
            f"<button class='btn ok sm' type='submit'>Save</button>{weg}"
            f"</form>{lees if r['lev'] is not None else ''}</div></details>")


def _rij(r: dict, csrf_token: str = "", bewerk: bool = False, terug: str = "/bom") -> str:
    b = r["bijdrage"]
    cellen = "".join(f"<td class='num'>{_getal(k, b.get(k))}</td>"
                     for k, _g, _w in bom_reken.METRIEKEN)
    status = _status("done", "Complete") if not r["open"] else _status("future", "Open")
    return (f"<tr><td>{_e(r['part'])}</td><td>{_link(r['mat'], r['materiaal'])}</td>"
            f"<td>{_leverancier_cel(r, csrf_token, bewerk, terug)}</td>{cellen}<td>{status}</td></tr>")


def render_bom(st, csrf_token: str = "", username: str | None = None, msg: str = "",
               maat: str = "") -> str:
    pags = wiki.paginas(st.att)
    # DE MAAT (Correctie 3). Een onbekende of ontbrekende maat is de referentiemaat — geen fout:
    # het is een kijkknop, en een vreemde waarde in de URL is geen keuze van een mens.
    cfg = bom_reken.maat_config()
    ref = cfg.get("referentiemaat", 42) if cfg else 42
    try:
        gekozen = int(maat)
    except (TypeError, ValueError):
        gekozen = ref
    if not cfg or gekozen not in cfg["maten"]:
        gekozen = ref
    terug = f"/bom?maat={gekozen}"
    uit = bom_reken.bereken(NOOCH_SCHOEN_BOM, pags, st.bom_leveranciers.alle(),
                            schaal=bom_reken.schaalfactor(gekozen, cfg))
    bewerk = bool(csrf_token) and _mag_koppelen(st, username)
    opties = ("".join(f"<option value='{_e(p.title)}'></option>" for p in pags if p.title)
              if bewerk else "")
    lijst = f"<datalist id='{_LIJST_ID}'>{opties}</datalist>" if bewerk else ""
    tegels = "".join(_tegel(k, uit["totalen"][k]) for k, _g, _w in bom_reken.METRIEKEN)
    kop = (f"<tr><th>Component</th><th>Material</th><th>Supplier</th><th class='num'>Weight</th>"
           f"<th class='num'>Cost price</th><th class='num'>{_CO2E}</th><th class='num'>Water</th>"
           "<th>Status</th></tr>")
    tabel = (f"<table class='mtab'>{kop}{''.join(_rij(r, csrf_token, bewerk, terug) for r in uit['rijen'])}"
             f"</table>{lijst}")
    open_rijen = [r for r in uit["rijen"] if r["open"]]
    nog_open = ""
    if open_rijen:
        items = "".join(f"<li><strong>{_e(r['part'])}</strong> — {_e('; '.join(r['open']))}</li>"
                        for r in open_rijen)
        nog_open = (f"<div class='card'><h3>Still open</h3>"
                    f"<p class='muted'>Fill in the weight in the bill of materials, link a supplier "
                    f"in the Supplier column, and add the numbers as a fact with a value on the "
                    f"material page (CO2e, water) or the supplier page (cost price). The totals "
                    f"above pick them up by themselves.</p>"
                    f"<ul>{items}</ul></div>")
    main = (f"<div class='c2-main'><h1 class='ptitle'>BOM · Nooch shoe</h1>"
            f"<p class='muted'>Bill of materials — weight, cost price, CO2e and water per pair. "
            f"Weights come from the bill of materials, the factors from the material and supplier "
            f"pages. The one thing set here is which supplier delivers a material.</p>{_banner(msg)}"
            f"{_maat_kiezer(gekozen, cfg) if cfg else ''}{_schatting(gekozen, cfg)}"
            f"<div class='c2-sec'><div class='tile-grid'>{tegels}</div></div>"
            f"<div class='c2-sec'>{tabel}</div>{nog_open}</div>")
    return _page("BOM", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
