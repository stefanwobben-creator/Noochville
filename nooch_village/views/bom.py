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

TWEE dingen zijn hier te wijzigen, allebei alleen voor wie mag (houder van `Materials` of Circle
Lead): welke leverancier een MATERIAAL levert (`bom_leveranciers`, Correctie 2) en welk materiaal
een COMPONENT heeft (`bom_materialen`, Correctie 3). Beide cellen klikken op dezelfde manier: zie
`_cel`.
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


def _cel(*, waarde: str, pagina, bewerk: bool, csrf_token: str, terug: str, actie: str,
         sleutel_veld: str, sleutel: str, veld: str, wat: str, leeg: str, wis_label: str,
         titel: str = "") -> str:
    """Eén bewerkbare BOM-cel, voor Materiaal én Supplier — hetzelfde klikgedrag (Correctie 3, D):

        ingevuld  → de waarde is een LINK naar zijn wiki-pagina (of tekst als die er nog niet is),
                    met ernaast een los potloodje om te wijzigen; de hoofdklik bewerkt niet;
        leeg      → de klik opent meteen het toewijsformulier ("+ …");
        lezer     → alleen de link (of "—").

    Het formulier is het bestaande popover-patroon: `details.acard-d` > `summary.chip.outline` +
    `.datepop` (de Deadline-cel van de projectrail, sinds #671 ook de Supplier-cel). Het veld stelt
    bestaande wiki-titels voor maar accepteert elke naam."""
    if waarde:
        lees = (f"<a href='{_e(wiki.pagina_url(pagina.id))}'{titel}>{_e(waarde)}</a>"
                if pagina is not None else f"<span{titel}>{_e(waarde)}</span>")
    else:
        lees = "—"
    if not bewerk:
        return lees
    wis = (f"<button class='dellink' type='submit' name='{veld}' value=''>{wis_label}</button>"
           if waarde and wis_label else "")
    formulier = (f"<div class='datepop'><form method='post' action='/action'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='action' value='{actie}'>"
                 f"<input type='hidden' name='next' value='{_e(terug)}'>"
                 f"<input type='hidden' name='{sleutel_veld}' value='{_e(sleutel)}'>"
                 f"<input name='{veld}' value='{_e(waarde)}' list='{_LIJST_ID}' "
                 f"aria-label='{_e(wat)}' placeholder='Name'>"
                 f"<button class='btn ok sm' type='submit'>Save</button>{wis}</form></div>")
    if not waarde:
        return (f"<details class='acard-d'><summary class='chip outline'>{leeg}</summary>"
                f"{formulier}</details>")
    return (f"{lees} <details class='acard-d'><summary class='chip outline' "
            f"aria-label='change {_e(wat)}' title='change'>✎</summary>{formulier}</details>")


def _rij(r: dict, csrf_token: str = "", bewerk: bool = False, terug: str = "/bom") -> str:
    b = r["bijdrage"]
    cellen = "".join(f"<td class='num'>{_getal(k, b.get(k))}</td>"
                     for k, _g, _w in bom_reken.METRIEKEN)
    status = _status("done", "Complete") if not r["open"] else _status("future", "Open")
    # Een GEWIJZIGD materiaal zegt waar het vandaan kwam: de stuklijst is de referentie, en zonder
    # deze hint is niet te zien dat deze rij ervan afwijkt.
    was = (f" title='changed on this screen; the bill of materials says {_e(r['origineel'])}'"
           if r.get("gewijzigd") else "")
    materiaal = _cel(waarde=r["materiaal"], pagina=r["mat"], bewerk=bewerk, csrf_token=csrf_token,
                     terug=terug, actie="bom_materiaal_zet", sleutel_veld="part", sleutel=r["part"],
                     veld="materiaal", wat=f"material of {r['part']}", leeg="+ set material",
                     wis_label="back to bill of materials" if r.get("gewijzigd") else "", titel=was)
    leverancier = _cel(waarde=r["supplier"], pagina=r["lev"], bewerk=bewerk, csrf_token=csrf_token,
                       terug=terug, actie="bom_leverancier_zet", sleutel_veld="materiaal",
                       sleutel=r["materiaal"], veld="leverancier",
                       wat=f"supplier of {r['materiaal']}", leeg="+ link supplier",
                       wis_label="remove")
    if not r["supplier"] and not bewerk:
        leverancier = "<span class='muted'>no supplier linked yet</span>"
    return (f"<tr><td>{_e(r['part'])}</td><td>{materiaal}</td><td>{leverancier}</td>"
            f"{cellen}<td>{status}</td></tr>")


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
                            schaal=bom_reken.schaalfactor(gekozen, cfg),
                            materialen=st.bom_materialen.alle())
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
            f"pages. What you set here: the material of a component, and which supplier delivers "
            f"a material.</p>{_banner(msg)}"
            f"{_maat_kiezer(gekozen, cfg) if cfg else ''}{_schatting(gekozen, cfg)}"
            f"<div class='c2-sec'><div class='tile-grid'>{tegels}</div></div>"
            f"<div class='c2-sec'>{tabel}</div>{nog_open}</div>")
    return _page("BOM", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
