"""Finance — kosten met PDF, terugkerende kosten, maandoverzicht en het P&L in marge-lagen
(Finance PR 1, 10 oktober 2026).

ALLEEN VOOR DE GROEP `finance` (`zicht.py`): zien voor de domeinhouder van "Financial
administration" (zolang die er niet is: de Financial Controller), Business strategy en Stefan;
invoeren en corrigeren voor de domeinhouder en Stefan. Elke route toetst dat zelf en geeft anders een
404 — niet verraden dat Finance bestaat. Geen knop in het hoofdmenu: de ingang is "Runway inputs".

GEEN BOEKHOUDING (Venema blijft leidend). Alleen toevoegen: geen knop, route of functie die een
kostregel wijzigt of verwijdert — "Correct" maakt een tegenboeking plus een nieuwe regel.

LAGEN (atom → molecule → pattern), allemaal bestaand:
  atom      `.muted` · `td.num` · `.chip` · `.dellink` · `.btn`
  molecule  `table.mtab` · `.cl-bar` + `a.cl-filter` (de schermkeuze) · het popover-formulier
            (`details.acard-d` > `summary.chip.outline` + `.datepop`, zoals op /bom)
  pattern   de vijf schermen hieronder
Geen nieuwe CSS-klasse en geen inline style.
"""
from __future__ import annotations

import time

from nooch_village import finance_config as fc
from nooch_village import finance_pnl, zicht
from nooch_village.finance_register import KostenRegister, euro, filter_regels, maak_kost, posten, totalen
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.web_base import _banner, _e, _page

GROEP = "finance"
_CHIP_CORR = "<span class='chip'>correction</span>"
_CHIP_GEEN_DOC = "<span class='chip'>missing document</span>"
_DOORLOPEND = "<span class='muted'>ongoing</span>"
_SCHERMEN = (("/finance/costs", "Costs"), ("/finance/recurring", "Recurring"),
             ("/finance/monthly", "Monthly"), ("/finance/pnl", "P&L"), ("/fixed-costs", "Runway inputs"))


def mag_zien(st, username) -> bool:
    return zicht.mag(st, username, GROEP, "zien")


def mag_wijzigen(st, username) -> bool:
    return zicht.mag(st, username, GROEP, "wijzigen")


def _eur(c) -> str:
    """Centen → "€1,234.56" voor het scherm (nooit via float gerekend)."""
    if c is None:
        return ""
    s = euro(c)
    heel, dec = s.lstrip("-").split(".")
    return f"{'-' if s.startswith('-') else ''}€{int(heel):,}.{dec}"


def _frame(titel: str, actief: str, inhoud: str, msg: str = "") -> str:
    tabs = " ".join(f"<a class='cl-filter{' on' if pad == actief else ''}' href='{pad}'>{_e(l)}</a>"
                    for pad, l in _SCHERMEN)
    main = (f"<div class='c2-main'><h1 class='ptitle'>{_e(titel)}</h1>"
            f"<div class='cl-bar' aria-label='finance'>{tabs}</div>{_banner(msg)}"
            f"<p class='muted'>Management administration next to the books. The books stay with the "
            f"accountant (Dutch GAAP, RJ). Amounts exclude VAT.</p>{inhoud}</div>")
    return _page(titel, f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")


def _opties(paren, gekozen: str = "", leeg: str = "") -> str:
    o = f"<option value=''>{_e(leeg)}</option>" if leeg else ""
    return o + "".join(f"<option value='{_e(k)}'{' selected' if k == gekozen else ''}>{_e(l)}</option>"
                       for k, l in paren)


def _lijst(lid: str, waarden) -> str:
    return f"<datalist id='{lid}'>" + "".join(f"<option value='{_e(w)}'></option>" for w in waarden) + "</datalist>"


def _kostvelden(st, cfg: dict, r: dict | None = None) -> str:
    """De invoervelden van een kostregel (nieuw of correctie). Bedragen in euro's; de server rekent
    in centen."""
    r = r or {}
    regels = [(x["key"], x["label"]) for x in fc.regels(cfg)]
    accounts = [a["naam_nl"] for a in cfg.get("accounts") or []]
    rec = [(x["id"], x["description"]) for x in st.vaste_kosten.alle()]
    bedrag = euro(r["amount_excl_cents"]) if "amount_excl_cents" in r else ""
    btw = euro(r["vat_cents"]) if "vat_cents" in r else ""
    v = lambda k: _e(str(r.get(k) or ""))
    return (f"<input type='date' name='entry_date' value='{v('entry_date')}' aria-label='invoice date' required>"
            f"<input type='month' name='period' value='{v('period')}' aria-label='period of use (empty = month of the invoice)'>"
            f"<input name='supplier' value='{v('supplier')}' aria-label='supplier' placeholder='Supplier' required>"
            f"<input name='description' value='{v('description')}' aria-label='description' placeholder='Description' required>"
            f"<input name='amount_excl' value='{_e(bedrag)}' inputmode='decimal' aria-label='amount excl. VAT in EUR' placeholder='EUR excl. VAT' required>"
            f"<input name='vat' value='{_e(btw)}' inputmode='decimal' aria-label='VAT in EUR (stored, never counted)' placeholder='VAT EUR'>"
            f"<input name='account_code' value='{v('account_code')}' list='fin-accounts' aria-label='account (Venema)' placeholder='Account'>"
            f"{_lijst('fin-accounts', accounts)}"
            f"<select name='management_line' aria-label='management line (empty = proposal from the account)'>"
            f"{_opties(regels, r.get('management_line', ''), 'Management line: from the account')}</select>"
            f"<input name='batch' value='{v('batch')}' list='fin-batches' aria-label='batch' placeholder='Batch'>"
            f"{_lijst('fin-batches', cfg.get('batches') or [])}"
            f"<select name='payment_status' aria-label='payment status'>"
            f"{_opties([('open', 'open'), ('paid', 'paid')], r.get('payment_status', 'open'))}</select>"
            f"<input type='date' name='paid_date' value='{v('paid_date')}' aria-label='paid date'>"
            f"<select name='recurring_id' aria-label='recurring cost this invoice belongs to'>"
            f"{_opties(rec, r.get('recurring_id', ''), 'Not a recurring cost')}</select>"
            f"<input name='note' value='{v('note')}' aria-label='note' placeholder='Note'>")


def _kostformulier(st, cfg: dict, csrf: str, actie: str, terug: str, r: dict | None = None,
                   extra: str = "") -> str:
    return (f"<form method='post' action='/action' enctype='multipart/form-data'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='action' value='{actie}'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>{extra}{_kostvelden(st, cfg, r)}"
            f"<input type='file' name='file' accept='.pdf,.png,.jpg,.jpeg' aria-label='invoice (pdf, png or jpg, max 10 MB)'>"
            f"<input name='no_document_reason' aria-label='no document available: why' placeholder='No document? Say why'>"
            f"<input type='checkbox' id='fin-dubbel' name='bevestig_dubbel' value='1'>"
            f"<label for='fin-dubbel' class='muted'>I know this file is already in the register</label>"
            f"<button class='btn ok sm' type='submit'>Save</button></form>")


def _popover(label: str, inhoud: str) -> str:
    return (f"<details class='acard-d'><summary class='chip outline'>{_e(label)}</summary>"
            f"<div class='datepop'>{inhoud}</div></details>")


# ── /finance/costs ──────────────────────────────────────────────────────────

FILTERS = ("periode", "account", "regel", "batch", "leverancier", "status", "missing_doc")


def gefilterd(st, f: dict) -> list[dict]:
    return filter_regels(KostenRegister(st.dd).alle(), periode=f.get("periode", ""),
                         account=f.get("account", ""), regel=f.get("regel", ""),
                         batch=f.get("batch", ""), leverancier=f.get("leverancier", ""),
                         status=f.get("status", ""), zonder_document=f.get("missing_doc") == "1")


def render_costs(st, username, csrf: str, f: dict, msg: str = "") -> str:
    cfg = fc.laad()
    regels = gefilterd(st, f)
    labels = {x["key"]: x["label"] for x in fc.regels(cfg)}
    filterform = (f"<form method='get' action='/finance/costs' aria-label='filters'>"
                  f"<input type='month' name='periode' value='{_e(f.get('periode', ''))}' aria-label='period'>"
                  f"<input name='account' value='{_e(f.get('account', ''))}' aria-label='account' placeholder='Account'>"
                  f"<select name='regel' aria-label='management line'>"
                  f"{_opties(sorted(labels.items(), key=lambda x: x[1]), f.get('regel', ''), 'All lines')}</select>"
                  f"<input name='batch' value='{_e(f.get('batch', ''))}' aria-label='batch' placeholder='Batch'>"
                  f"<input name='leverancier' value='{_e(f.get('leverancier', ''))}' aria-label='supplier' placeholder='Supplier'>"
                  f"<select name='status' aria-label='payment status'>"
                  f"{_opties([('open', 'open'), ('paid', 'paid')], f.get('status', ''), 'Any status')}</select>"
                  f"<input type='checkbox' id='fin-missing-doc' name='missing_doc' value='1'"
                  f"{' checked' if f.get('missing_doc') == '1' else ''}>"
                  f"<label for='fin-missing-doc' class='muted'>missing document</label>"
                  f"<button class='btn sm' type='submit'>Filter</button></form>")
    q = "&".join(f"{k}={_e(v)}" for k, v in f.items() if v)
    rijen = "".join(
        f"<tr><td><a href='/finance/costs/view?id={_e(r['id'])}'>{_e(r['entry_date'])}</a>"
        f"<div class='muted'>{_e(r['period'])}</div></td><td>{_e(r['supplier'])}"
        f"<div class='muted'>{_e(r['description'])}</div></td><td>{_e(r.get('account_code', ''))}</td>"
        f"<td>{_e(labels.get(r['management_line'], r['management_line']))}</td><td>{_e(r.get('batch', ''))}</td>"
        f"<td class='num'>{_eur(r['amount_excl_cents'])}</td><td>{_e(r['payment_status'])}</td>"
        f"<td>{_CHIP_CORR if r.get('corrects') else ''}{'' if r.get('attachment') else _CHIP_GEEN_DOC}</td></tr>"
        for r in sorted(regels, key=lambda x: (x["entry_date"], x["created_at"]), reverse=True))
    tabel = ("<table class='mtab' aria-label='costs'><tr><th>Date</th><th>Supplier</th><th>Account</th>"
             "<th>Management line</th><th>Batch</th><th class='num'>Excl. VAT</th><th>Status</th><th></th></tr>"
             f"{rijen}</table>" if regels else "<p class='muted'>No costs in this selection.</p>")
    per_acc = totalen(regels, "account_code")
    per_regel = totalen(regels, "management_line")
    som = ("<table class='mtab' aria-label='totals per account'><tr><th>Account</th><th class='num'>Total</th></tr>"
           + "".join(f"<tr><td>{_e(k)}</td><td class='num'>{_eur(v)}</td></tr>" for k, v in sorted(per_acc.items()))
           + "</table><table class='mtab' aria-label='totals per management line'><tr><th>Management line</th>"
           "<th class='num'>Total</th></tr>"
           + "".join(f"<tr><td>{_e(labels.get(k, k))}</td><td class='num'>{_eur(v)}</td></tr>"
                     for k, v in sorted(per_regel.items(), key=lambda x: labels.get(x[0], x[0])))
           + f"</table><p><strong>Total excl. VAT: {_eur(sum(per_acc.values()))}</strong></p>") if regels else ""
    zonder = [r for r in KostenRegister(st.dd).alle() if not r.get("attachment") and not r.get("corrects")]
    open_punten = ("<div class='c2-sec'><h2>Open items: missing document</h2><ul>"
                   + "".join(f"<li><a href='/finance/costs/view?id={_e(r['id'])}'>{_e(r['entry_date'])} "
                             f"{_e(r['supplier'])}</a> — {_e(r['no_document_reason'])}</li>" for r in zonder)
                   + "</ul></div>") if zonder else ""
    nieuw = (_popover("+ add a cost", _kostformulier(st, cfg, csrf, "finance_kost_add", "/finance/costs"))
             if mag_wijzigen(st, username) and csrf else "")
    # DE FILTERS IN EEN POPOVER: zeven velden naast elkaar liepen op een gewoon scherm al buiten beeld.
    actief = ", ".join(f"{k}: {v}" for k, v in f.items() if v)
    filters = (_popover("Filter", filterform)
               + (f"<span class='muted'>{_e(actief)} · <a href='/finance/costs'>clear</a></span>" if actief else ""))
    inhoud = (f"{filters}<p><a href='/finance/costs.csv{'?' + q if q else ''}'>Export CSV for the accountant</a></p>"
              f"{nieuw}<div class='c2-sec'>{tabel}</div><div class='c2-sec'>{som}</div>{open_punten}")
    return _frame("Finance · Costs", "/finance/costs", inhoud, msg)


def render_cost(st, username, csrf: str, kid: str, msg: str = "") -> str | None:
    reg = KostenRegister(st.dd)
    r = reg.get(kid)
    if r is None:
        return None
    cfg = fc.laad()
    labels = {x["key"]: x["label"] for x in fc.regels(cfg)}
    velden = [("Invoice date", r["entry_date"]), ("Period", r["period"]), ("Supplier", r["supplier"]),
              ("Description", r["description"]), ("Excl. VAT", _eur(r["amount_excl_cents"])),
              ("VAT (stored, not counted)", _eur(r["vat_cents"])), ("Currency", r["currency"]),
              ("Account", r.get("account_code", "")),
              ("Management line", labels.get(r["management_line"], r["management_line"])),
              ("Batch", r.get("batch", "")), ("Payment", f"{r['payment_status']} {r.get('paid_date', '')}"),
              ("Note", r.get("note", "")), ("Corrects", r.get("corrects", "")),
              ("Recorded", f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created_at']))} by {r.get('created_by') or '—'}")]
    tabel = ("<table class='mtab' aria-label='cost'>"
             + "".join(f"<tr><th>{_e(k)}</th><td>{_e(str(v))}</td></tr>" for k, v in velden) + "</table>")
    b = r.get("attachment")
    if b:
        doc = (f"<p>{_e(b['filename'])} · {b['size'] // 1024} KB · sha256 <code>{_e(b['sha256'][:16])}…</code></p>"
               f"<p><a href='/finance/file?id={_e(kid)}&inline=1' target='_blank' rel='noopener'>Open</a> · "
               f"<a href='/finance/file?id={_e(kid)}'>Download</a></p>")
    else:
        doc = f"<p class='muted'>No document: {_e(r.get('no_document_reason', ''))}</p>"
    geschiedenis = reg.correcties_van(kid)
    hist = ("<ul>" + "".join(f"<li><a href='/finance/costs/view?id={_e(x['id'])}'>{_e(x['note'] or x['id'])}</a> "
                             f"({_eur(x['amount_excl_cents'])})</li>" for x in geschiedenis) + "</ul>"
            if geschiedenis else "<p class='muted'>Not corrected.</p>")
    correct = ""
    if mag_wijzigen(st, username) and csrf and not r.get("corrects"):
        correct = _popover("Correct", "<p class='muted'>This adds a reversal of this line and a new line "
                           "with the values below. Nothing is overwritten.</p>"
                           + _kostformulier(st, cfg, csrf, "finance_kost_correct", f"/finance/costs/view?id={kid}",
                                            r, extra=f"<input type='hidden' name='kid' value='{_e(kid)}'>"))
    inhoud = (f"<div class='c2-sec'>{tabel}</div><div class='c2-sec'><h2>Document</h2>{doc}</div>"
              f"<div class='c2-sec'><h2>Corrections</h2>{hist}{correct}</div>")
    return _frame(f"Finance · {r['supplier']}", "/finance/costs", inhoud, msg)


# ── /finance/recurring ──────────────────────────────────────────────────────

def _maanden_tot_nu(n: int = 6) -> list[str]:
    t = time.localtime()
    jaar, maand = t.tm_year, t.tm_mon
    uit = []
    for _ in range(n):
        uit.append(f"{jaar:04d}-{maand:02d}")
        maand -= 1
        if maand == 0:
            jaar, maand = jaar - 1, 12
    return sorted(uit)


def verwacht_niet_gefactureerd(st, maanden: list[str]) -> list[dict]:
    """Per maand de terugkerende kosten die in die maand liepen maar waar (netto) nog geen kostregel
    met dat `recurring_id` en die periode voor is. {maand, id, description, amount_cents}."""
    from nooch_village.vaste_kosten import loopt_op
    regels = KostenRegister(st.dd).alle()
    uit = []
    for m in maanden:
        for rc in st.vaste_kosten.alle():
            if not loopt_op(rc, f"{m}-01") and not loopt_op(rc, f"{m}-28"):
                continue
            geboekt = sum(r["amount_excl_cents"] for r in regels
                          if r.get("recurring_id") == rc["id"] and r["period"] == m)
            if geboekt == 0:
                uit.append({"maand": m, "id": rc["id"], "description": rc["description"],
                            "amount_cents": rc["amount_cents"]})
    return uit


def render_recurring(st, username, csrf: str, msg: str = "") -> str:
    cfg = fc.laad()
    labels = {x["key"]: x["label"] for x in fc.regels(cfg)}
    bewerk = mag_wijzigen(st, username) and bool(csrf)

    def velden(r=None):
        r = r or {}
        v = lambda k: _e(str(r.get(k) or ""))
        bedrag = euro(r["amount_cents"]) if "amount_cents" in r else ""
        return (f"<input name='omschrijving' value='{v('description')}' aria-label='description' placeholder='Description' required>"
                f"<input name='leverancier' value='{v('supplier')}' aria-label='supplier' placeholder='Supplier'>"
                f"<input name='bedrag' value='{_e(bedrag)}' inputmode='decimal' aria-label='amount per month excl. VAT in EUR' placeholder='EUR per month' required>"
                f"<input name='account_code' value='{v('account_code')}' list='fin-accounts' aria-label='account' placeholder='Account'>"
                f"{_lijst('fin-accounts', [a['naam_nl'] for a in cfg.get('accounts') or []])}"
                f"<select name='management_line' aria-label='management line'>"
                f"{_opties([(x['key'], x['label']) for x in fc.regels(cfg)], r.get('management_line', ''), 'Management line')}</select>"
                f"<input type='date' name='van' value='{v('van')}' aria-label='from' required>"
                f"<input type='date' name='tot' value='{v('tot')}' aria-label='until (empty = ongoing)'>"
                f"<input name='notitie' value='{v('notitie')}' aria-label='note' placeholder='Note'>")

    def form(extra="", r=None):
        return (f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='action' value='vaste_kosten_zet'>"
                f"<input type='hidden' name='next' value='/finance/recurring'>{extra}{velden(r)}"
                f"<button class='btn ok sm' type='submit'>Save</button></form>")

    rijen = []
    for r in st.vaste_kosten.alle():
        acties = ""
        if bewerk:
            acties = (_popover("✎", form(f"<input type='hidden' name='rid' value='{_e(r['id'])}'>", r))
                      + f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
                      f"<input type='hidden' name='action' value='vaste_kosten_weg'><input type='hidden' name='next' "
                      f"value='/finance/recurring'><input type='hidden' name='rid' value='{_e(r['id'])}'>"
                      f"<button class='dellink' type='submit'>remove</button></form>")
        rijen.append(f"<tr><td>{_e(r['description'])}<div class='muted'>{_e(r.get('supplier', ''))} "
                     f"{_e(r.get('notitie', ''))}</div></td><td>{_e(r.get('account_code', ''))}</td>"
                     f"<td>{_e(labels.get(r.get('management_line', ''), ''))}</td>"
                     f"<td class='num'>{_eur(r['amount_cents'])}</td><td>{_e(r['van'])}</td>"
                     f"<td>{_e(r['tot']) if r.get('tot') else _DOORLOPEND}</td>"
                     f"<td>{acties}</td></tr>")
    tabel = ("<table class='mtab' aria-label='recurring costs'><tr><th>Description</th><th>Account</th>"
             "<th>Management line</th><th class='num'>Per month</th><th>From</th><th>Until</th><th></th></tr>"
             + "".join(rijen) + "</table>" if rijen else "<p class='muted'>No recurring costs yet.</p>")
    nieuw = _popover("+ add a recurring cost", form()) if bewerk else ""
    open_ = verwacht_niet_gefactureerd(st, _maanden_tot_nu())
    verwacht = ("<table class='mtab' aria-label='expected, not invoiced'><tr><th>Month</th><th>Recurring cost</th>"
                "<th class='num'>Expected</th></tr>"
                + "".join(f"<tr><td>{_e(x['maand'])}</td><td>{_e(x['description'])}</td>"
                          f"<td class='num'>{_eur(x['amount_cents'])}</td></tr>" for x in open_)
                + "</table>") if open_ else "<p class='muted'>Every recurring cost has an invoice line.</p>"
    inhoud = (f"<p>Running today: <strong>{_eur(st.vaste_kosten.totaal_cents_op())}</strong> per month — the "
              f"fixed costs of the runway.</p>{nieuw}<div class='c2-sec'>{tabel}</div>"
              f"<div class='c2-sec'><h2>Expected, not invoiced (last 6 months)</h2>{verwacht}</div>")
    return _frame("Finance · Recurring costs", "/finance/recurring", inhoud, msg)


# ── /finance/monthly ────────────────────────────────────────────────────────

def render_monthly(st, username) -> str:
    regels = KostenRegister(st.dd).alle()
    maanden = sorted({r["period"] for r in regels})
    accounts = sorted({r.get("account_code") or "—" for r in regels})
    cel = {}
    for r in regels:
        k = (r.get("account_code") or "—", r["period"])
        cel[k] = cel.get(k, 0) + r["amount_excl_cents"]
    if not regels:
        return _frame("Finance · Monthly", "/finance/monthly", "<p class='muted'>No costs yet.</p>")
    kop = "".join(f"<th class='num'>{_e(m)}</th>" for m in maanden)
    rijen = "".join(f"<tr><td>{_e(a)}</td>" + "".join(f"<td class='num'>{_eur(cel.get((a, m)))}</td>" for m in maanden)
                    + f"<td class='num'>{_eur(sum(cel.get((a, m), 0) for m in maanden))}</td></tr>" for a in accounts)
    tabel = (f"<table class='mtab' aria-label='totals per account per month'><tr><th>Account</th>{kop}"
             f"<th class='num'>Total</th></tr>{rijen}</table>")
    return _frame("Finance · Monthly", "/finance/monthly", f"<div class='c2-sec'>{tabel}</div>")


# ── /finance/pnl ────────────────────────────────────────────────────────────

def render_pnl(st, username, van: str = "", tot: str = "", batch: str = "", omzet: dict | None = None) -> str:
    """Het kostenoverzicht in marge-lagen. `omzet` is een optionele invoer van dezelfde berekening
    (PR 3 levert hem uit Shopify); zonder omzet: "costs only" en geen percentages."""
    cfg = fc.laad()
    regels = [r for r in KostenRegister(st.dd).alle()
              if (not van or r["period"] >= van) and (not tot or r["period"] <= tot)
              and (not batch or r.get("batch") == batch)]
    uit = finance_pnl.bereken(posten(regels), cfg, omzet=omzet)
    maanden = uit["maanden"]
    filt = (f"<form method='get' action='/finance/pnl' class='cl-bar' aria-label='filters'>"
            f"<input type='month' name='van' value='{_e(van)}' aria-label='from month'>"
            f"<input type='month' name='tot' value='{_e(tot)}' aria-label='until month'>"
            f"<input name='batch' value='{_e(batch)}' list='fin-batches' aria-label='batch' placeholder='Batch'>"
            f"{_lijst('fin-batches', cfg.get('batches') or [])}<button class='btn sm' type='submit'>Filter</button></form>")
    if not maanden:
        return _frame("Finance · P&L", "/finance/pnl", filt + "<p class='muted'>No costs in this selection.</p>")
    kop = "".join(f"<th class='num'>{_e(m)}</th>" for m in maanden) + "<th class='num'>Total</th><th class='num'>%</th>"
    rijen = []
    for r in uit["rijen"]:
        if r["soort"] == "omzet" and omzet is None:
            rijen.append(f"<tr><td><strong>{_e(r['label'])}</strong></td>"
                         f"<td class='muted' colspan='{len(maanden) + 2}'>Revenue comes from Shopify (PR 3)</td></tr>")
            continue
        naam = f"<strong>{_e(r['label'])}</strong>" if r["soort"] in ("groep", "laag", "omzet") else _e(r["label"])
        pct = ""
        if r["pct"] and r["pct"].get("totaal") is not None:
            pct = f"{r['pct']['totaal'] * 100:.1f}%"
        rijen.append(f"<tr><td>{naam}</td>" + "".join(f"<td class='num'>{_eur(r['waarden'].get(m))}</td>" for m in maanden)
                     + f"<td class='num'>{_eur(r['totaal'])}</td><td class='num'>{pct}</td></tr>")
    tabel = f"<table class='mtab' aria-label='profit and loss'><tr><th></th>{kop}</tr>{''.join(rijen)}</table>"
    noot = ("<p class='muted'>Costs only: the margin rows show the cumulative costs up to that layer "
            "until revenue is connected. Costs are shown negative, as in the example P&L.</p>"
            if uit["kosten_alleen"] else "")
    return _frame("Finance · P&L", "/finance/pnl", f"{filt}{noot}<div class='c2-sec'>{tabel}</div>")


# ── CSV voor Venema ─────────────────────────────────────────────────────────

CSV_KOLOMMEN = ("id", "entry_date", "period", "supplier", "description", "account_code", "management_line",
                "batch", "amount_excl_eur", "vat_eur", "currency", "payment_status", "paid_date",
                "document", "corrects", "note")


def csv_export(regels: list[dict]) -> str:
    """Puntkomma, decimale komma, euro's met twee decimalen (Nederlandse Excel opent hem goed)."""
    def eur_nl(c: int) -> str:
        return euro(c).replace(".", ",")

    def cel(x) -> str:
        s = str(x if x is not None else "")
        return '"' + s.replace('"', '""') + '"' if any(t in s for t in (";", '"', "\n")) else s

    uit = [";".join(CSV_KOLOMMEN)]
    for r in sorted(regels, key=lambda x: (x["entry_date"], x["created_at"])):
        b = r.get("attachment") or {}
        doc = f"{b.get('filename', '')} sha256:{b.get('sha256', '')}" if b else f"none: {r.get('no_document_reason', '')}"
        uit.append(";".join(cel(v) for v in (
            r["id"], r["entry_date"], r["period"], r["supplier"], r["description"], r.get("account_code", ""),
            r["management_line"], r.get("batch", ""), eur_nl(r["amount_excl_cents"]), eur_nl(r["vat_cents"]),
            r["currency"], r["payment_status"], r.get("paid_date", ""), doc, r.get("corrects", ""), r.get("note", ""))))
    return "\r\n".join(uit) + "\r\n"


# ── verwerken (multipart, vanuit de cockpit-handler) ────────────────────────

def verwerk_kost(st, fields: dict, files: dict, *, username, door: str) -> str:
    """Een nieuwe kostregel of een correctie (`fields["kid"]`). Geeft de melding terug.
    De rechten toetst de aanroeper (404 voor wie niet mag)."""
    cfg = fc.laad()
    reg = KostenRegister(st.dd)
    correctie_van = fields.get("kid", "") if fields.get("action") == "finance_kost_correct" else ""
    oud = reg.get(correctie_van) if correctie_van else None
    if correctie_van and oud is None:
        return "✗ the line to correct does not exist"
    v = {k: fields.get(k, "") for k in ("entry_date", "period", "supplier", "description", "amount_excl",
                                         "vat", "account_code", "management_line", "batch", "payment_status",
                                         "paid_date", "recurring_id", "note", "no_document_reason")}
    fname, blob = files.get("file") or ("", b"")
    if blob:
        h = __import__("hashlib").sha256(blob).hexdigest()
        eerder = [r for r in reg.met_hash(h) if not oud or r["id"] != oud["id"]]
        if eerder and fields.get("bevestig_dubbel") != "1":
            e = eerder[0]
            return (f"⚠ this file is already in the register ({e['entry_date']}, {e['supplier']}). "
                    f"Nothing saved — tick 'I know this file is already in the register' to save it anyway.")
        bijlage, fout = reg.bewaar_bijlage(fname, blob, jaar=(v["entry_date"] or "")[:4])
        if bijlage is None:
            return f"✗ {fout}"
        v["attachment"] = bijlage
    elif oud is not None and oud.get("attachment"):
        v["attachment"] = oud["attachment"]                  # een correctie houdt het originele document
    regel, fout = maak_kost(v, cfg)
    if regel is None:
        return f"✗ {fout}"
    if oud is not None:
        reg.correctie(correctie_van, regel, door=door)
        return "✓ corrected: a reversal and a new line were added"
    reg.voeg_toe(regel, door=door)
    return "✓ cost saved"
