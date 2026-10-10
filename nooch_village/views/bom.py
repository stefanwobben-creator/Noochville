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

import urllib.parse

from nooch_village import artefacts, bom_leveranciers, bom_reken, wiki
from nooch_village import wiki_dekking as dek
from nooch_village.cockpit2_util import _DS_LINK, _nav
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


def _url(model: str, variant: str, doel: str = "") -> str:
    """Eén plek voor de `/bom`-URL, zodat model en variant elkaar niet kwijtraken. Rauw; `_e()` waar
    hij in een attribuut landt. (De maat zat hier ook in, tot de maat-schaling op 2 oktober 2026
    verviel — zie `data_bom.REFERENTIEMAAT`.) `doel` is het filter van de dekking."""
    from nooch_village.data_bom import STANDAARD_MODEL
    delen = ([] if model == STANDAARD_MODEL else [f"model={model}"]) + \
            ([f"variant={variant}"] if variant else []) + ([f"doel={doel}"] if doel else [])
    return "/bom" + ("?" + "&".join(delen) if delen else "")


def _verborgen(velden: dict) -> str:
    return "".join(f"<input type='hidden' name='{k}' value='{_e(v)}'>" for k, v in velden.items())


def _popover(summary: str, formulier: str, aria: str = "") -> str:
    """Het popover-patroon van de Deadline-cel (projectrail), sinds #671 ook op `/bom`:
    `details.acard-d` > `summary.chip.outline` + `.datepop`."""
    a = f" aria-label='{_e(aria)}' title='change'" if aria else ""
    return (f"<details class='acard-d'><summary class='chip outline'{a}>{summary}</summary>"
            f"<div class='datepop'>{formulier}</div></details>")


def _form(csrf_token: str, actie: str, terug: str, velden: dict, invoer: str, knoppen: str = "") -> str:
    return (f"<form method='post' action='/action'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"{_verborgen({'action': actie, 'next': terug, **velden})}{invoer}"
            f"<button class='btn ok sm' type='submit'>Save</button>{knoppen}</form>")


def _cel(*, waarde: str, pagina, bewerk: bool, csrf_token: str, terug: str, actie: str,
         velden: dict, veld: str, wat: str, leeg: str, wis: str = "", titel: str = "") -> str:
    """Eén bewerkbare BOM-cel, voor Materiaal én Supplier — hetzelfde klikgedrag (Correctie 3, D):

        ingevuld  → de waarde is een LINK naar zijn wiki-pagina (of tekst als die er nog niet is),
                    met ernaast een los potloodje om te wijzigen; de hoofdklik bewerkt niet;
        leeg      → de klik opent meteen het toewijsformulier ("+ …");
        lezer     → alleen de link (of "—").

    `velden` zijn de verborgen sleutels (component, model, variant …); `wis` is de HTML van een
    terug-/wisknop, of leeg. Het veld stelt bestaande wiki-titels voor maar accepteert elke naam."""
    if waarde:
        lees = (f"<a href='{_e(wiki.pagina_url(pagina.id))}'{titel}>{_e(waarde)}</a>"
                if pagina is not None else f"<span{titel}>{_e(waarde)}</span>")
    else:
        lees = "—"
    if not bewerk:
        return lees
    invoer = (f"<input name='{veld}' value='{_e(waarde)}' list='{_LIJST_ID}' "
              f"aria-label='{_e(wat)}' placeholder='Name'>")
    formulier = _form(csrf_token, actie, terug, velden, invoer, wis if waarde else "")
    if not waarde:
        return _popover(leeg, formulier)
    return f"{lees} {_popover('✎', formulier, f'change {wat}')}"


def _gewicht_cel(r: dict, bewerk: bool, csrf_token: str, terug: str, velden: dict) -> str:
    """Het gewicht: geschaald getoond, maar het formulier bewerkt de REFERENTIEMAAT-waarde (die
    staat in de stuklijst of in een afwijking) — bij de referentiemaat."""
    getoond = _getal("gram", r["bijdrage"].get("gram"))
    if not bewerk:
        return getoond
    eigen = r.get("gram_eigen")
    invoer = (f"<input name='gram' value='{'' if eigen is None else f'{eigen:g}'}' "
              f"inputmode='decimal' aria-label='weight of {_e(r['part'])} in grams, reference size' "
              f"placeholder='grams at reference size'>")
    return f"{getoond} {_popover('✎', _form(csrf_token, 'bom_materiaal_zet', terug, velden, invoer), 'change weight of ' + r['part'])}"


def _afwijking(r: dict, variant: str) -> tuple[str, str]:
    """(chip, terug-knop-label) voor een rij die afwijkt. Zichtbaar als chip (niet alleen een
    tooltip, die op een telefoon niet bestaat) — zelfde afwijk-patroon als #674, nu per niveau."""
    if r.get("toegevoegd"):
        return ("<span class='chip muted'>added in this variant</span>" if variant
                else "<span class='chip muted'>added</span>", "remove component")
    if variant and r.get("niveau") == variant:
        return "<span class='chip muted'>differs from master</span>", "back to master"
    if not variant and r.get("niveau") == "master" and r.get("gewijzigd"):
        return ("<span class='chip muted'>changed</span>", "back to bill of materials")
    return "", ""


def _rij(r: dict, csrf_token: str = "", bewerk: bool = False, terug: str = "/bom",
         model: str = "", variant: str = "") -> str:
    from nooch_village.data_bom import STANDAARD_MODEL
    b = r["bijdrage"]
    cellen = "".join(f"<td class='num'>{_getal(k, b.get(k))}</td>"
                     for k, _g, _w in bom_reken.METRIEKEN if k != "gram")
    status = _status("done", "Complete") if not r["open"] else _status("future", "Open")
    chip, terug_label = _afwijking(r, variant)
    sleutels = {"part": r["part"], "model": model or STANDAARD_MODEL, "variant": variant}
    wis = (f"<button class='dellink' type='submit' name='wis' value='1'>{terug_label}</button>"
           if terug_label else "")
    # Wat de STUKLIJST zegt, als hint op de link: dat is de referentie waarvan deze rij afwijkt.
    was = (f" title='the bill of materials says {_e(r['origineel'])}'"
           if r.get("gewijzigd") and r.get("origineel") else "")
    materiaal = _cel(waarde=r["materiaal"], pagina=r["mat"], bewerk=bewerk, csrf_token=csrf_token,
                     terug=terug, actie="bom_materiaal_zet", velden=sleutels, veld="materiaal",
                     wat=f"material of {r['part']}", leeg="+ material", wis=wis, titel=was)
    leverancier = _cel(waarde=r["supplier"], pagina=r["lev"], bewerk=bewerk, csrf_token=csrf_token,
                       terug=terug, actie="bom_leverancier_zet", velden={"materiaal": r["materiaal"]},
                       veld="leverancier", wat=f"supplier of {r['materiaal']}", leeg="+ supplier",
                       wis="<button class='dellink' type='submit' name='leverancier' value=''>remove</button>")
    if not r["supplier"] and not bewerk:
        leverancier = "<span class='muted'>no supplier linked yet</span>"
    gewicht = _gewicht_cel(r, bewerk, csrf_token, terug, sleutels)
    return (f"<tr><td>{_e(r['part'])}{' ' + chip if chip else ''}</td><td>{materiaal}</td><td>{leverancier}</td>"
            f"<td class='num'>{gewicht}</td>{cellen}<td>{status}</td></tr>")


def _model_kiezer(model: str, variant: str, varianten: list[dict], bewerk: bool,
                  csrf_token: str) -> str:
    """Model en variant als keuzebalk (`.cl-bar` + `a.cl-filter`), het patroon van de maatkiezer.
    Alleen varianten die echt zijn aangemaakt; geen kruistabel. "Master" = geen variant."""
    from nooch_village.data_bom import MODELLEN
    modellen = " ".join(
        f"<a class='cl-filter{' on' if k == model else ''}' href='{_e(_url(k, ""))}'>"
        f"{_e(v['naam'])}</a>" for k, v in MODELLEN.items())
    opties = [f"<a class='cl-filter{' on' if not variant else ''}' href='{_e(_url(model, ""))}'>"
              f"Master</a>"]
    opties += [f"<a class='cl-filter{' on' if v['handle'] == variant else ''}' "
               f"href='{_e(_url(model, v["handle"]))}' title='{_e(v['handle'])}'>{_e(v['naam'])}</a>"
               for v in varianten]
    nieuw = ""
    if bewerk:
        invoer = (f"<input name='handle' aria-label='Shopify handle' placeholder='the-269-hi-black' "
                  f"required><input name='naam' aria-label='display name' placeholder='Hi · Black'>")
        nieuw = _popover("+ variant", _form(csrf_token, "bom_variant_add", _url(model, variant),
                                            {"model": model}, invoer))
    return (f"<div class='cl-bar' aria-label='model'><span class='muted'>Model</span> {modellen}</div>"
            f"<div class='cl-bar' aria-label='variant'><span class='muted'>Variant</span> "
            f"{' '.join(opties)} {nieuw}</div>")


def _foto(st, model: str, variant: str, naam: str, bewerk: bool, csrf_token: str) -> str:
    """De productfoto bovenaan: die van de variant, anders die van het model. Het BEELD is het
    bestaande embed-atoom (`cockpit2_util._embed_html`), dezelfde `<figure>` als in de wiki.

    WAAR EEN NIEUWE FOTO HEEN GAAT (2 oktober 2026, gevonden door Stefan): naar het MODEL, tenzij
    deze kleur al een eigen foto heeft. Daarvoor schreef "+ photo" in een kleurvariant naar die
    variant, en kregen de andere kleuren hem niet als terugval — een losse, ongebruikte plek. In een
    kleurvariant kun je met de keuze in het formulier bewust "only this colour" nemen."""
    from nooch_village.cockpit2_util import _embed_html
    foto = st.bom_varianten.foto(model, variant)
    beeld = _embed_html(foto, naam, beeld=True) if foto else ""
    if not bewerk:
        return beeld
    terug = _url(model, variant)
    eigen = bool(variant) and bool((st.bom_varianten.get(model, variant) or {}).get("foto"))
    doel = variant if eigen else ""
    if variant:
        keuze = (f"<select name='variant' aria-label='who gets this photo'>"
                 f"<option value=''{'' if eigen else ' selected'}>whole model (every colour)</option>"
                 f"<option value='{_e(variant)}'{' selected' if eigen else ''}>only this colour</option>"
                 f"</select>")
        sleutels = {"model": model}
    else:
        keuze, sleutels = "", {"model": model, "variant": ""}
    huidig = st.bom_varianten.foto(model, doel) if (eigen or not variant) else foto
    adres = _form(csrf_token, "bom_foto", terug, sleutels,
                  f"{keuze}<input name='foto' type='url' "
                  f"value='{_e(huidig if huidig.startswith('https://') else '')}' "
                  f"aria-label='photo address' placeholder='https://…'>",
                  "<button class='dellink' type='submit' name='foto' value=''>remove</button>" if foto else "")
    upload = (f"<form method='post' action='/action' enctype='multipart/form-data'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
              f"{_verborgen({'action': 'bom_foto', 'next': terug, **sleutels})}{keuze}"
              f"<input type='file' name='file' accept='image/*' aria-label='upload a photo'>"
              f"<button class='btn ok sm' type='submit'>Upload</button></form>")
    return f"{beeld}{_popover('photo ✎' if foto else '+ photo', adres + upload, 'photo')}"


def _nieuwe_rij(model: str, variant: str, csrf_token: str) -> str:
    """Een component dat in de master niet bestaat (Hemp naast HyphaLite bij de Hi). Zelfde actie
    als een materiaal wijzigen, met `toegevoegd`."""
    invoer = ("<input name='part' aria-label='component' placeholder='Component' required>"
              f"<input name='materiaal' list='{_LIJST_ID}' aria-label='material' "
              "placeholder='Material' required>"
              "<input name='gram' inputmode='decimal' aria-label='weight in grams at reference size' "
              "placeholder='grams'>")
    wie = "this variant" if variant else "the master"
    return _popover(f"+ add a component to {wie}",
                    _form(csrf_token, "bom_materiaal_zet", _url(model, variant),
                          {"model": model, "variant": variant, "toegevoegd": "1"}, invoer))


# ── Dekking: welke vragen de pagina's al beantwoorden (10 oktober 2026) ──────
# LAGEN, allemaal bestaand (akkoord Stefan, 10 oktober 2026):
#   atom      `.nu-status` met zijn vier vormen — vol rondje, half vierkant, gestippeld leeg rondje,
#             driehoek — plus het woord; `.muted`; een wiki-link
#   molecule  `.tile` (de rollup per doel) · `table.mtab` (één strook per materiaal/leverancier)
#             · `.cl-bar` + `a.cl-filter` (het doelfilter, zelfde vorm als de modelkiezer)
#   pattern   de sectie "Coverage" onder de stuklijst
# Bewust NIET uit het prototype: het zijpaneel, de weergave "By question" en "least covered
# first". Een klik op een cel opent de wikipagina bij het kopje van die vraag.

#: celstatus → (vorm uit `.nu-status`, woord). De vorm draagt de betekenis, niet de kleur.
_DEK_VORM = {dek.GECHECKT: ("ok", "Checked"), dek.ONGECHECKT: ("wait", "Unchecked"),
             dek.LEEG: ("open", "Open"), dek.CONFLICT: ("off", "Conflict")}


def _sprong(pagina, kop: str) -> str:
    """De pagina-URL, bij een kopje met `#kop=<tekst>`. Wiki-koppen hebben geen id; `naarKop` in
    nooch.js zoekt het kopje op zijn tekst (een `#:~:text=`-fragment werkt niet in bewerkbare tekst).
    Zonder JavaScript opent gewoon de pagina."""
    url = wiki.pagina_url(pagina.id)
    return url + ("#kop=" + urllib.parse.quote(kop, safe="") if kop else "")


def _dek_cel(vraag: dict, cel: dict, pagina) -> str:
    vorm, woord = _DEK_VORM[cel["status"]]
    reden = f" — {cel['reden']}" if cel["status"] == dek.CONFLICT and cel["reden"] else ""
    label = _e(f"{vraag['label']}: {woord}{reden}")
    if pagina is None:
        return (f"<span class='nu-status nu-status--{vorm}' aria-label='{label}' "
                f"title='{label}'>{woord}</span>")
    return (f"<a class='nu-status nu-status--{vorm}' href='{_e(_sprong(pagina, cel['kop']))}' "
            f"aria-label='{label}' title='{label}'>{woord}</a>")


def _nieuwe_pagina(st, naam: str, sjabloon: str, terug: str, csrf_token: str) -> str:
    """"Create page" voor een rij zonder pagina: het BESTAANDE `artefact_add`, met het skelet van
    deze paginasoort, op het domein `Materials` bij zijn houder — waar de zaaier de andere
    materiaal- en leverancierpagina's ook neerzette. Geen houder → geen knop, maar de reden."""
    from nooch_village import org
    houder = org.role_for_domain(st.records.all(), bom_leveranciers.DOMEIN)
    if houder is None:
        return f"<div class='muted'>No page yet — no role holds “{bom_leveranciers.DOMEIN}”.</div>"
    velden = {"action": "artefact_add", "next": terug, "owner": houder.id, "kind": wiki.PAGINA_KIND,
              "domain": bom_leveranciers.DOMEIN, "sjabloon": sjabloon, "title": naam,
              "naar_pagina": "1"}
    return (f"<form method='post' action='/action'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>{_verborgen(velden)}"
            f"<button class='btn sm' type='submit'>Create page</button></form>")


def _dek_tabel(st, rijen: list[dict], soort: str, doel: str, bewerk: bool, csrf_token: str,
               terug: str) -> str:
    vragen = dek.vragen(soort, doel)
    if not vragen or not rijen:
        return ""
    # `_CO2E` om dezelfde reden als in de stuklijst: `th` zet zijn tekst in hoofdletters.
    kop = "".join(f"<th>{_e(v['label']).replace('CO2e', _CO2E)}<div class='muted'>"
                  f"{_e(' · '.join(dek.DOELEN[d] for d in v['doelen']))}</div></th>" for v in vragen)
    wat = "Material" if soort == "materiaal" else "Supplier"
    uit = [f"<table class='mtab' aria-label='{wat} coverage'><tr><th>{wat}</th>{kop}</tr>"]
    for r in rijen:
        if soort == "materiaal":
            sub = (f"Supplied by {r['leverancier']}" if r["leverancier"] else "No supplier linked")
            sub += " · " + ", ".join(r["onderdelen"])
        else:
            sub = "Supplies " + ", ".join(r["materialen"])
        if r["pagina"] is not None:
            naam = f"<a href='{_e(wiki.pagina_url(r['pagina'].id))}'>{_e(r['naam'])}</a>"
        else:
            naam = _e(r["naam"]) + (_nieuwe_pagina(st, r["naam"], soort, terug, csrf_token) if bewerk
                                    else "<div class='muted'>No page yet</div>")
        cellen = "".join(f"<td>{_dek_cel(v, r['cellen'][v['k']], r['pagina'])}</td>" for v in vragen)
        uit.append(f"<tr><td>{naam}<div class='muted'>{_e(sub)}</div></td>{cellen}</tr>")
    return "".join(uit) + "</table>"


def _rollup_tegels(per_model: dict[str, dict], doel: str) -> str:
    """Eén tegel per doel: per model hoeveel materialen en leveranciers volledig zijn."""
    from nooch_village.data_bom import MODELLEN
    tegels = []
    for d, label in dek.DOELEN.items():
        if doel and d != doel:
            continue
        regels = []
        for m, ru in per_model.items():
            delen = [f"{ru[d][sleutel][0]} of {ru[d][sleutel][1]} {wat}"
                     for wat, sleutel in (("materials", "materialen"), ("suppliers", "leveranciers"))
                     if sleutel in ru[d]]
            regels.append(f"<div class='muted'><strong>{_e(MODELLEN[m]['naam'])}</strong>: "
                          f"{_e(', '.join(delen))} complete</div>")
        tegels.append(f"<div class='tile'><div class='tile-h'><span class='tile-t'>{_e(label)}"
                      f"</span></div>{''.join(regels)}</div>")
    return f"<div class='tile-grid'>{''.join(tegels)}</div>"


def _dekking_sectie(st, uit: dict, model: str, variant: str, doel: str, bewerk: bool,
                    csrf_token: str) -> str:
    from nooch_village.data_bom import MODELLEN
    # DEZELFDE CONTEXT ALS DE PAGINA (`views.wiki._feit_html`), ook `bestaat`: anders telt een
    # document-feit waarvan het bestand weg is hier als gecheckt, terwijl de pagina "no source" zegt.
    from nooch_village.views.wiki import _bijlage_bestaat
    ctx = {"ledger": getattr(st, "evidence", None), "store": st.att, "bestaat": _bijlage_bestaat(st)}
    d = dek.dekking(uit, **ctx)
    # DE ROLLUP IS PER MODEL, op modelniveau (zonder kleurvariant): de vraag is of de 269 Lo en de
    # 269 Hi klaar zijn, niet één kleur. Voor het getoonde model zonder variant is `uit` dat al.
    pags = wiki.paginas(st.att)
    per_model = {}
    for m in MODELLEN:
        b = uit if (m == model and not variant) else bom_reken.bereken(
            MODELLEN[m]["master"], pags, st.bom_leveranciers.alle(),
            afwijkingen=st.bom_materialen.afwijkingen(m, ""))
        per_model[m] = dek.rollup(dek.dekking(b, **ctx))
    filter_ = " ".join(
        f"<a class='cl-filter{' on' if k == doel else ''}' "
        f"href='{_e(_url(model, variant, k))}#coverage'>{_e(lbl)}</a>"
        for k, lbl in (("", "All"), *dek.DOELEN.items()))
    legenda = " ".join(f"<span class='nu-status nu-status--{v}'>{w}</span>"
                       for v, w in _DEK_VORM.values())
    terug = _url(model, variant, doel)
    return (f"<div class='c2-sec' id='coverage'><h2>Coverage</h2>"
            f"<p class='muted'>Which questions each material and supplier page answers, computed "
            f"from the facts on the page. Checked = a person checked it, a valid certificate, or the "
            f"quote was found at the source. Open means not answered yet — not “no”. A cell opens "
            f"the page at the heading where the answer belongs.</p>"
            f"<div class='cl-bar' aria-label='goal'><span class='muted'>Goal</span> {filter_}</div>"
            f"{_rollup_tegels(per_model, doel)}"
            f"<p class='muted'>{legenda}</p>"
            f"{_dek_tabel(st, d['materialen'], 'materiaal', doel, bewerk, csrf_token, terug)}"
            f"{_dek_tabel(st, d['leveranciers'], 'leverancier', doel, bewerk, csrf_token, terug)}"
            f"</div>")


def render_bom(st, csrf_token: str = "", username: str | None = None, msg: str = "",
               model: str = "", variant: str = "", doel: str = "") -> str:
    from nooch_village.data_bom import MODELLEN, REFERENTIEMAAT, STANDAARD_MODEL
    pags = wiki.paginas(st.att)
    # MODEL EN VARIANT (Stuk 4). Onbekend = het standaardmodel / de master: een kijkknop, en een
    # vreemde waarde in de URL is geen keuze van een mens.
    model = model if model in MODELLEN else STANDAARD_MODEL
    varianten = st.bom_varianten.varianten(model)
    if variant not in {v["handle"] for v in varianten}:
        variant = ""
    v_naam = next((v["naam"] for v in varianten if v["handle"] == variant), "")
    doel = doel if doel in dek.DOELEN else ""
    terug = _url(model, variant)
    uit = bom_reken.bereken(MODELLEN[model]["master"], pags, st.bom_leveranciers.alle(),
                            afwijkingen=st.bom_materialen.afwijkingen(model, variant))
    bewerk = bool(csrf_token) and _mag_koppelen(st, username)
    opties = ("".join(f"<option value='{_e(p.title)}'></option>" for p in pags if p.title)
              if bewerk else "")
    lijst = f"<datalist id='{_LIJST_ID}'>{opties}</datalist>" if bewerk else ""
    tegels = "".join(_tegel(k, uit["totalen"][k]) for k, _g, _w in bom_reken.METRIEKEN)
    kop = (f"<tr><th>Component</th><th>Material</th><th>Supplier</th><th class='num'>Weight</th>"
           f"<th class='num'>Cost price</th><th class='num'>{_CO2E}</th><th class='num'>Water</th>"
           "<th>Status</th></tr>")
    rijen = "".join(_rij(r, csrf_token, bewerk, terug, model, variant) for r in uit["rijen"])
    erbij = _nieuwe_rij(model, variant, csrf_token) if bewerk else ""
    tabel = f"<table class='mtab'>{kop}{rijen}</table>{erbij}{lijst}"
    open_rijen = [r for r in uit["rijen"] if r["open"]]
    nog_open = ""
    if open_rijen:
        items = "".join(f"<li><strong>{_e(r['part'])}</strong> — {_e('; '.join(r['open']))}</li>"
                        for r in open_rijen)
        nog_open = (f"<div class='card'><h3>Still open</h3>"
                    f"<p class='muted'>Fill in the weight{' (✎ in the Weight column)' if bewerk else ''}, "
                    f"link a supplier in the Supplier column, and add the numbers as a fact with a value on the "
                    f"material page (CO2e, water) or the supplier page (cost price). The totals "
                    f"above pick them up by themselves.</p>"
                    f"<ul>{items}</ul></div>")
    titel = MODELLEN[model]["naam"] + (f" · {v_naam}" if variant else "")
    uitleg = ("This colour variant shows the model's bill of materials with its own differences "
              "on top." if variant else
              "The model's bill of materials; a colour variant shows its own differences on top of it.")
    # 269 HI BEGINT BIJ DE LIJST VAN 269 LO (`basis_van`, besluit Stefan): dat staat erbij, anders
    # leest een identieke lijst als een eigen, gecontroleerde Hi-lijst.
    basis = MODELLEN[model].get("basis_van")
    basis_zin = (f" This model has no list of its own yet: it starts from "
                 f"{_e(MODELLEN[basis]['naam'])}, and its differences are set here."
                 if basis in MODELLEN else "")
    main = (f"<div class='c2-main'><h1 class='ptitle'>BOM · {_e(titel)}</h1>"
            f"<p class='muted'>Bill of materials — weight, cost price, CO2e and water per pair. "
            f"{uitleg}{basis_zin} Weights and materials can be changed here per component; the "
            f"factors come from the material and supplier pages.</p>{_banner(msg)}"
            f"{_foto(st, model, variant, titel, bewerk, csrf_token)}"
            f"{_model_kiezer(model, variant, varianten, bewerk, csrf_token)}"
            # GEEN MAATKIEZER MEER (2 oktober 2026): alle hoeveelheden gelden bij de referentiemaat.
            f"<p class='muted'>Quantities at reference size EU {REFERENTIEMAAT}.</p>"
            f"<div class='c2-sec'><div class='tile-grid'>{tegels}</div></div>"
            f"<div class='c2-sec'>{tabel}</div>{nog_open}"
            f"{_dekking_sectie(st, uit, model, variant, doel, bewerk, csrf_token)}</div>")
    return _page("BOM", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
