"""Runway inputs — alles waar de runway uit rekent, op één scherm (CN2, 10 oktober 2026).

SINDS DE AANVULLING (vrije cash): cash per rekening (bunq, Mollie), productieverplichtingen per batch,
belasting- en leveranciersschulden, en de vaste kosten. De metingen (cash, schulden) gaan via
dezelfde `m_sample`-route als het werkoverleg — één schrijfroute, hetzelfde sample.

Hieronder de oorspronkelijke kop van het vaste-kostenscherm:

Fixed costs per month — de noemer van de runway (CN2, 10 oktober 2026).

Een korte lijst, geen boekhouding: omschrijving, bedrag per maand, categorie, van, tot (leeg =
doorlopend) en een notitie. Het totaal is de som van wat VANDAAG loopt (`VasteKostenStore.totaal_op`).

ZICHT: alleen voor de groep `finance` (`zicht.py`): lezen voor Financial Controller, Business
strategy en de anchor lead; wijzigen voor Financial Controller en de anchor lead.

LAGEN (atom → molecule → pattern), allemaal bestaand:
  atom      `.muted` · `td.num` · `.dellink`
  molecule  `table.mtab` · het popover-formulier van /bom (`details.acard-d` > `summary.chip.outline`
            + `.datepop`, via `views.bom._popover`/`_form`)
  pattern   dit scherm
Geen nieuwe CSS-klasse en geen inline style.
"""
from __future__ import annotations

from nooch_village import zicht
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.views.bom import _form, _popover
from nooch_village.views.metrics import (BELASTING_CN, CASH_REKENINGEN, CREDITEUREN_CN, RUNWAY_ZICHT,
                                        runway)
from nooch_village.web_base import _banner, _e, _page

_TERUG = "/fixed-costs"


def _invoer(r: dict | None = None) -> str:
    r = r or {}
    v = lambda k: _e("" if r.get(k) is None else (f"{r[k]:g}" if k == "bedrag" else str(r[k])))
    return (f"<input name='omschrijving' value='{v('omschrijving')}' aria-label='description' "
            f"placeholder='Description' required>"
            f"<input name='bedrag' value='{v('bedrag')}' inputmode='decimal' "
            f"aria-label='amount per month in EUR' placeholder='EUR per month' required>"
            f"<input name='categorie' value='{v('categorie')}' aria-label='category' placeholder='Category'>"
            f"<input name='van' type='date' value='{v('van')}' aria-label='from' required>"
            f"<input name='tot' type='date' value='{v('tot')}' aria-label='until (empty = ongoing)'>"
            f"<input name='notitie' value='{v('notitie')}' aria-label='note' placeholder='Note'>")


def _meting_form(csrf: str, mid: str, wat: str) -> str:
    """Een nieuwe meting (bedrag, datum, notitie) via `m_sample`, zoals in het werkoverleg."""
    return (f"<form method='post' action='/action' class='kpi-add'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='mid' "
            f"value='{_e(mid)}'><input type='hidden' name='next' value='{_TERUG}'>"
            f"<input name='value' inputmode='decimal' placeholder='EUR' aria-label='{_e(wat)} in EUR' required>"
            f"<input name='datum' type='date' aria-label='date (empty = today)'>"
            f"<input name='notitie' placeholder='note (optional)' aria-label='note'>"
            f"<button class='btn ok sm' type='submit' name='action' value='m_sample'>+</button></form>")


def _metingen(st, csrf: str, bewerk: bool) -> str:
    """Cash per rekening en de twee schulden: de laatste meting, met datum, notitie en invoer."""
    import time as _t
    rijen = []
    for cn, label in ([(cn, f"Cash — {n}") for cn, n in CASH_REKENINGEN.items()]
                      + [(BELASTING_CN, "Tax liabilities"), (CREDITEUREN_CN, "Supplier payables")]):
        it = st.metrics.by_cn(cn)
        if it is None:
            rijen.append(f"<tr><td>{_e(label)}</td><td class='muted' colspan='3'>not set up yet "
                         f"(run <code>village cn_zaad --apply</code>)</td></tr>")
            continue
        s = max(it.get("samples") or [{}], key=lambda x: x.get("at", 0))
        waarde = f"€{s['value']:,.2f}" if "value" in s else "<span class='muted'>no reading yet</span>"
        datum = _t.strftime("%Y-%m-%d", _t.localtime(s["at"])) if "at" in s else ""
        invoer = _meting_form(csrf, it["id"], label) if bewerk else ""
        rijen.append(f"<tr><td>{_e(label)}</td><td class='num'>{waarde}</td><td>{_e(datum)}"
                     f"<div class='muted'>{_e(s.get('notitie', ''))}</div></td><td>{invoer}</td></tr>")
    return ("<table class='mtab' aria-label='cash and liabilities'><tr><th>Reading</th>"
            "<th class='num'>Latest</th><th>Date</th><th></th></tr>" + "".join(rijen) + "</table>")


def _verplichting_invoer(r: dict | None = None) -> str:
    from nooch_village.productieverplichtingen import STATUSSEN
    r = r or {}
    eur = lambda k: "" if r.get(k) is None else f"{r[k] / 100:g}"
    opties = "".join(f"<option value='{s}'{' selected' if r.get('status') == s else ''}>{s}</option>"
                     for s in STATUSSEN)
    return (f"<input name='batch' value='{_e(r.get('batch', ''))}' aria-label='batch' placeholder='Batch' required>"
            f"<input name='totaal' value='{eur('totaal_cents')}' inputmode='decimal' "
            f"aria-label='total production cost in EUR' placeholder='total EUR' required>"
            f"<input name='betaald' value='{eur('betaald_cents')}' inputmode='decimal' "
            f"aria-label='paid to the factory in EUR' placeholder='paid EUR'>"
            f"<select name='status' aria-label='status'>{opties}</select>"
            f"<input name='notitie' value='{_e(r.get('notitie', ''))}' aria-label='note' placeholder='Note'>")


def _verplichtingen(st, csrf: str, bewerk: bool) -> str:
    from nooch_village.productieverplichtingen import verplichting_cents
    rijen = []
    for r in st.productieverplichtingen.alle():
        acties = ""
        if bewerk:
            weg = (f"<form method='post' action='/action'><input type='hidden' name='csrf' "
                   f"value='{_e(csrf)}'><input type='hidden' name='action' value='verplichting_weg'>"
                   f"<input type='hidden' name='next' value='{_TERUG}'><input type='hidden' name='rid' "
                   f"value='{_e(r['id'])}'><button class='dellink' type='submit'>remove</button></form>")
            acties = _popover("✎", _form(csrf, "verplichting_zet", _TERUG, {"rid": r["id"]},
                                         _verplichting_invoer(r)), f"change {r['batch']}") + weg
        rijen.append(f"<tr><td>{_e(r['batch'])}<div class='muted'>{_e(r.get('notitie', ''))}</div></td>"
                     f"<td>{_e(r['status'])}</td><td class='num'>€{r['totaal_cents'] / 100:,.2f}</td>"
                     f"<td class='num'>€{r['betaald_cents'] / 100:,.2f}</td>"
                     f"<td class='num'>€{verplichting_cents(r) / 100:,.2f}</td><td>{acties}</td></tr>")
    tabel = ("<table class='mtab' aria-label='production commitments'><tr><th>Batch</th><th>Status</th>"
             "<th class='num'>Total</th><th class='num'>Paid</th><th class='num'>Still owed</th><th></th></tr>"
             f"{''.join(rijen)}</table>" if rijen else "<p class='muted'>No open batches recorded.</p>")
    erbij = (_popover("+ add a batch", _form(csrf, "verplichting_zet", _TERUG, {}, _verplichting_invoer()))
             if bewerk else "")
    return tabel + erbij


def render_vaste_kosten(st, username: str | None, csrf_token: str = "", msg: str = "") -> str:
    if not zicht.mag(st, username, RUNWAY_ZICHT, "zien"):
        main = ("<div class='c2-main'><h1 class='ptitle'>Runway inputs</h1><p class='muted'>Only the "
                "Financial Controller, Business strategy and the anchor lead can see this page.</p></div>")
        return _page("Runway inputs", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
    bewerk = bool(csrf_token) and zicht.mag(st, username, RUNWAY_ZICHT, "wijzigen")
    r = runway(st)
    rijen = []
    for k in st.vaste_kosten.alle():
        acties = ""
        if bewerk:
            weg = (f"<form method='post' action='/action'><input type='hidden' name='csrf' "
                   f"value='{_e(csrf_token)}'><input type='hidden' name='action' value='vaste_kosten_weg'>"
                   f"<input type='hidden' name='next' value='{_TERUG}'><input type='hidden' name='rid' "
                   f"value='{_e(k['id'])}'><button class='dellink' type='submit'>remove</button></form>")
            acties = _popover("✎", _form(csrf_token, "vaste_kosten_zet", _TERUG, {"rid": k["id"]},
                                         _invoer(k)), f"change {k['omschrijving']}") + weg
        tot = _e(k["tot"]) if k.get("tot") else "<span class='muted'>ongoing</span>"
        rijen.append(f"<tr><td>{_e(k['omschrijving'])}<div class='muted'>{_e(k.get('notitie', ''))}</div></td>"
                     f"<td>{_e(k.get('categorie', ''))}</td><td class='num'>€{k['bedrag']:,.2f}</td>"
                     f"<td>{_e(k['van'])}</td><td>{tot}</td><td>{acties}</td></tr>")
    tabel = ("<table class='mtab' aria-label='fixed costs'><tr><th>Description</th><th>Category</th>"
             "<th class='num'>Per month</th><th>From</th><th>Until</th><th></th></tr>"
             f"{''.join(rijen)}</table>" if rijen else "<p class='muted'>No fixed costs yet.</p>")
    erbij = (_popover("+ add a fixed cost", _form(csrf_token, "vaste_kosten_zet", _TERUG, {}, _invoer()))
             if bewerk else "")
    eur = lambda x: "—" if x is None else f"€{x:,.2f}"
    maanden = (f"{r['maanden']:g} months" if r["maanden"] is not None
               else "no runway yet (missing: " + ", ".join(r["ontbreekt"]) + ")")
    main = (f"<div class='c2-main'><h1 class='ptitle'>Runway inputs</h1>"
            f"<p class='muted'>Everything the runway is computed from. Not the books: ledger, invoices "
            f"and VAT stay with the accountant (Dutch GAAP, RJ).</p>{_banner(msg)}"
            f"<p><strong>Runway: {_e(maanden)}</strong><br>Cash {eur(r['cash'])} − production "
            f"commitments {eur(r['verplichtingen'])} − tax liabilities {eur(r['belasting'])} − supplier "
            f"payables {eur(r['crediteuren'])} = <strong>free cash {eur(r['vrije_cash'])}</strong>, "
            f"divided by fixed costs {eur(r['vaste_kosten'])} per month.</p>"
            f"<div class='c2-sec'><h2>Cash and liabilities</h2>{_metingen(st, csrf_token, bewerk)}</div>"
            f"<div class='c2-sec' id='commitments'><h2>Production commitments (open batches)</h2>"
            f"<p class='muted'>The factory is paid 50% when the batch is ordered and 50% on delivery: "
            f"still owed = total − paid, and 0 once delivered and paid in full.</p>"
            f"{_verplichtingen(st, csrf_token, bewerk)}</div>"
            f"<div class='c2-sec'><h2>Fixed costs per month</h2>{tabel}{erbij}</div></div>")
    return _page("Runway inputs", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
