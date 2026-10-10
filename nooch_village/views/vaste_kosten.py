"""Fixed costs per month — de noemer van de runway (CN2, 10 oktober 2026).

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
from nooch_village.views.metrics import RUNWAY_ZICHT, runway
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


def render_vaste_kosten(st, username: str | None, csrf_token: str = "", msg: str = "") -> str:
    if not zicht.mag(st, username, RUNWAY_ZICHT, "zien"):
        main = ("<div class='c2-main'><h1 class='ptitle'>Fixed costs</h1><p class='muted'>Only the "
                "Financial Controller, Business strategy and the anchor lead can see this page.</p></div>")
        return _page("Fixed costs", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
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
    maanden = (f"{r['maanden']:g} months" if r["maanden"] is not None
               else "no runway yet (it needs a cash reading and fixed costs above zero)")
    main = (f"<div class='c2-main'><h1 class='ptitle'>Fixed costs</h1>"
            f"<p class='muted'>Fixed costs per month, the denominator of the runway. Not the books: "
            f"ledger, invoices and VAT stay with the accountant (Dutch GAAP, RJ). The total counts the "
            f"lines that run today.</p>{_banner(msg)}"
            f"<p><strong>Fixed costs per month: €{r['vaste_kosten']:,.2f}</strong> · runway: {_e(maanden)}</p>"
            f"<div class='c2-sec'>{tabel}{erbij}</div></div>")
    return _page("Fixed costs", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
