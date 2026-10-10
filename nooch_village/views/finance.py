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
_STREEP = "<span class='muted'>—</span>"
_GEEN_DATA = "<span class='muted'>no data</span>"
_SCHERMEN = (("/finance/costs", "Costs"), ("/finance/revenue", "Revenue"), ("/finance/recurring", "Recurring"),
             ("/finance/monthly", "Monthly"), ("/finance/pnl", "P&L"), ("/finance/history", "History"),
             ("/fixed-costs", "Runway inputs"))


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

def render_pnl(st, username, van: str = "", tot: str = "", batch: str = "", omzet: dict | None = None,
               per: str = "") -> str:
    """Het P&L in marge-lagen. Net sales en overige opbrengsten komen uit het opbrengstregister
    (PR 1b, handmatig); `omzet` blijft een optionele invoer van dezelfde berekening (PR 3: Shopify).
    `per="paar"`: elke rij gedeeld door het aantal paren van die maand; ontbreken paren, een streepje."""
    from nooch_village.finance_omzet import OpbrengstRegister, paren_per_maand
    from nooch_village.finance_omzet import posten as opbrengst_posten
    from nooch_village import finance_historie as fh
    cfg = fc.laad()
    binnen = lambda r: ((not van or r["period"] >= van) and (not tot or r["period"] <= tot)
                        and (not batch or r.get("batch") == batch))
    kosten = [r for r in KostenRegister(st.dd).alle() if binnen(r)]
    opbr = [r for r in OpbrengstRegister(st.dd).alle() if binnen(r)]
    # PR 2a: ÉÉN BRON PER MAAND. Tot en met de cutover de historie, daarna het register. Historie
    # heeft geen batch: in een batch-weergave telt alleen het register, en historie-maanden tonen
    # een streepje.
    h_tot = fh.Instellingen(st.dd).history_until()
    hk, ho, hp = fh.posten({k: r for k, r in fh.HistorieRegister(st.dd).actueel().items()
                            if (not van or k[0] >= van) and (not tot or k[0] <= tot)}, cfg)
    if batch:
        hk, ho, hp = [], [], {}
    k_posten, o_posten, genegeerd = fh.kies_bronnen(posten(kosten), opbrengst_posten(opbr), hk, ho, h_tot)
    par = {m: n for m, n in paren_per_maand(opbr).items() if not h_tot or m > h_tot}
    par.update({m: n for m, n in hp.items() if h_tot and m <= h_tot})
    # Met een volledig bereik (van én tot) staat elke maand erin; een maand zonder data in zijn
    # bron toont "no data", geen nul.
    bereik = []
    if van and tot and van <= tot:
        j, m = int(van[:4]), int(van[5:7])
        while f"{j}-{m:02d}" <= tot and len(bereik) < 120:
            bereik.append(f"{j}-{m:02d}")
            j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    uit = finance_pnl.bereken(k_posten, cfg, omzet=omzet, opbrengsten=o_posten, paren=par,
                              maanden=bereik, historie_tot=h_tot)
    maanden = uit["maanden"]
    met_data = {p[0] for p in k_posten} | {p[0] for p in o_posten} | set(omzet or {})
    is_hist = lambda m: bool(h_tot) and m <= h_tot
    perpaar = per == "paar"
    filt = (f"<form method='get' action='/finance/pnl' class='cl-bar' aria-label='filters'>"
            f"<input type='month' name='van' value='{_e(van)}' aria-label='from month'>"
            f"<input type='month' name='tot' value='{_e(tot)}' aria-label='until month'>"
            f"<input name='batch' value='{_e(batch)}' list='fin-batches' aria-label='batch' placeholder='Batch'>"
            f"{_lijst('fin-batches', cfg.get('batches') or [])}"
            f"<select name='per' aria-label='view'>{_opties([('', 'Amounts'), ('paar', 'Per pair')], per)}</select>"
            f"<button class='btn sm' type='submit'>Filter</button></form>")
    if not maanden:
        return _frame("Finance · P&L", "/finance/pnl", filt + "<p class='muted'>Nothing in this selection.</p>")
    paren = uit["paren"]
    # Het TOTAAL per paar alleen als élke maand paren heeft: anders deel je de omzet van een maand
    # zonder paren door de paren van een andere, en dat getal bestaat niet.
    paren_tot = sum(paren.get(m, 0) for m in maanden) if all(paren.get(m) for m in maanden) else 0

    def cel(c, m=None):
        if m is not None and m not in met_data:
            # GEEN DATA IS GEEN NUL. Een historie-maand in een batch-weergave: historie heeft geen batch.
            return "—" if (batch and is_hist(m)) else "<span class='muted'>no data</span>"
        if c is None:
            return ""
        if not perpaar:
            return _eur(c)
        n = paren.get(m, 0) if m is not None else paren_tot
        return _eur(round(c / n)) if n else "—"           # geen paren: een streepje, geen getal

    kop = ("".join(f"<th class='num'>{_e(m)}</th>" for m in maanden)
           + "<th class='num'>Total</th><th class='num'>% of net sales</th>")
    def bron_van(m):
        if m not in met_data:
            return "—" if (batch and is_hist(m)) else "no data"
        return fh.BRON if is_hist(m) else "register"
    bron = ("<tr><td class='muted'>Source</td>"
            + "".join(f"<td class='num muted'>{_e(bron_van(m))}</td>" for m in maanden)
            + "<td></td><td></td></tr>"
            "<tr><td class='muted'>Source of net sales</td>"
            + "".join(f"<td class='num muted'>{_e(uit['bron'].get(m, '—'))}</td>" for m in maanden)
            + "<td></td><td></td></tr>")
    rijen = []
    for r in uit["rijen"]:
        if r["soort"] == "omzet" and uit["kosten_alleen"]:
            rijen.append(f"<tr><td><strong>{_e(r['label'])}</strong></td>"
                         f"<td class='muted' colspan='{len(maanden) + 2}'>No revenue in this selection yet — "
                         f"<a href='/finance/revenue'>enter revenue</a></td></tr>")
            continue
        vet = r["soort"] in ("groep", "laag", "omzet")
        naam = f"<strong>{_e(r['label'])}</strong>" if vet else _e(r["label"])
        cellen = ""
        for m in maanden:
            p_m = (r["pct"] or {}).get(m)
            extra = (f"<div class='muted'>{p_m * 100:.1f}%</div>"
                     if p_m is not None and r["soort"] in ("laag", "omzet") and not perpaar else "")
            cellen += f"<td class='num'>{cel(r['waarden'].get(m), m)}{extra}</td>"
        pct = ""
        if r["pct"] and r["pct"].get("totaal") is not None:
            pct = f"{r['pct']['totaal'] * 100:.1f}%"
        rijen.append(f"<tr><td>{naam}</td>{cellen}<td class='num'>{cel(r['totaal'])}</td>"
                     f"<td class='num'>{pct}</td></tr>")
    paarrij = ("<tr><td class='muted'>Pairs</td>"
               + "".join(f"<td class='num muted'>{paren.get(m, '—')}</td>" for m in maanden)
               + f"<td class='num muted'>{paren_tot or '—'}</td><td></td></tr>")
    tabel = (f"<table class='mtab' aria-label='profit and loss'><tr><th></th>{kop}</tr>{bron}{paarrij}"
             f"{''.join(rijen)}</table>")
    noot = ("<p class='muted'>Costs only: the margin rows show the cumulative costs up to that layer "
            "until there is revenue. Costs are shown negative, as in the example P&L.</p>"
            if uit["kosten_alleen"] else
            "<p class='muted'>Percentages are of net sales. Grants and subsidies count from the layer "
            "set in the configuration, never in net sales or the percentage basis.</p>")
    if perpaar:
        noot += "<p class='muted'>Per pair: every row divided by the pairs of that month; no pairs, no number.</p>"
    if h_tot:
        noot += (f"<p class='muted'>Months up to and including {_e(h_tot)} come from the "
                 f"<a href='/finance/history'>{_e(fh.LABEL)}</a>; later months from the register.</p>")
    if genegeerd:
        noot += _cutover_waarschuwing(genegeerd, h_tot)
    return _frame("Finance · P&L", "/finance/pnl", f"{filt}{noot}<div class='c2-sec'>{tabel}</div>")


def _cutover_waarschuwing(n: int, h_tot: str) -> str:
    return (f"<div class='card'>⚠ {n} register line(s) fall in months up to the cutover "
            f"({_e(h_tot)}). They are kept, but not counted: those months come from the history.</div>")


# ── /finance/revenue ────────────────────────────────────────────────────────

OMZET_FILTERS = ("periode", "lijn", "batch")


def _omzetvelden(cfg: dict, r: dict | None = None) -> str:
    from nooch_village.finance_omzet import regels as omzetregels
    r = r or {}
    v = lambda k: _e(str(r.get(k) if r.get(k) is not None else ""))
    bedrag = euro(r["amount_excl_cents"]) if "amount_excl_cents" in r else ""
    btw = euro(r["vat_cents"]) if "vat_cents" in r else ""
    return (f"<input type='date' name='entry_date' value='{v('entry_date')}' aria-label='booking date' required>"
            f"<input type='month' name='period' value='{v('period')}' aria-label='period (any month, also in the past)'>"
            f"<select name='revenue_line' aria-label='revenue line' required>"
            f"{_opties([(x['key'], x['label']) for x in omzetregels(cfg)], r.get('revenue_line', 'net_sales'))}</select>"
            f"<input name='description' value='{v('description')}' aria-label='description' placeholder='Description' required>"
            f"<input name='amount_excl' value='{_e(bedrag)}' inputmode='decimal' aria-label='amount excl. VAT in EUR' placeholder='EUR excl. VAT' required>"
            f"<input name='vat' value='{_e(btw)}' inputmode='decimal' aria-label='VAT in EUR (stored, never counted)' placeholder='VAT EUR'>"
            f"<input name='batch' value='{v('batch')}' list='fin-batches' aria-label='batch' placeholder='Batch'>"
            f"{_lijst('fin-batches', cfg.get('batches') or [])}"
            f"<input name='pairs' value='{v('pairs')}' inputmode='numeric' aria-label='pairs (net sales only)' placeholder='Pairs'>"
            f"<input name='note' value='{v('note')}' aria-label='note (required for a return or credit note)' placeholder='Note'>")


def _omzetformulier(cfg: dict, csrf: str, actie: str, terug: str, r: dict | None = None, extra: str = "") -> str:
    return (f"<form method='post' action='/action' enctype='multipart/form-data'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='action' value='{actie}'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>{extra}{_omzetvelden(cfg, r)}"
            f"<input type='file' name='file' accept='.pdf,.png,.jpg,.jpeg' aria-label='document (optional; for a grant: the decision)'>"
            f"<input type='checkbox' id='fin-dubbel-omzet' name='bevestig_dubbel' value='1'>"
            f"<label for='fin-dubbel-omzet' class='muted'>I know this file is already in the register</label>"
            f"<button class='btn ok sm' type='submit'>Save</button></form>")


def omzet_gefilterd(st, f: dict) -> list[dict]:
    from nooch_village.finance_omzet import OpbrengstRegister
    return [r for r in OpbrengstRegister(st.dd).alle()
            if (not f.get("periode") or r["period"] == f["periode"])
            and (not f.get("lijn") or r["revenue_line"] == f["lijn"])
            and (not f.get("batch") or r.get("batch") == f["batch"])]


def render_revenue(st, username, csrf: str, f: dict, msg: str = "") -> str:
    from nooch_village.finance_omzet import regels as omzetregels
    cfg = fc.laad()
    labels = {x["key"]: x["label"] for x in omzetregels(cfg)}
    regels_ = omzet_gefilterd(st, f)
    filterform = (f"<form method='get' action='/finance/revenue' aria-label='filters'>"
                  f"<input type='month' name='periode' value='{_e(f.get('periode', ''))}' aria-label='period'>"
                  f"<select name='lijn' aria-label='revenue line'>{_opties(list(labels.items()), f.get('lijn', ''), 'All lines')}</select>"
                  f"<input name='batch' value='{_e(f.get('batch', ''))}' aria-label='batch' placeholder='Batch'>"
                  f"<button class='btn sm' type='submit'>Filter</button></form>")
    actief = ", ".join(f"{k}: {v}" for k, v in f.items() if v)
    filters = (_popover("Filter", filterform)
               + (f"<span class='muted'>{_e(actief)} · <a href='/finance/revenue'>clear</a></span>" if actief else ""))
    q = "&".join(f"{k}={_e(v)}" for k, v in f.items() if v)
    rijen = "".join(
        f"<tr><td><a href='/finance/revenue/view?id={_e(r['id'])}'>{_e(r['period'])}</a>"
        f"<div class='muted'>{_e(r['entry_date'])}</div></td><td>{_e(labels.get(r['revenue_line'], r['revenue_line']))}"
        f"<div class='muted'>{_e(r['description'])}</div></td><td>{_e(r.get('batch', ''))}</td>"
        f"<td class='num'>{r['pairs'] if r.get('pairs') is not None else ''}</td>"
        f"<td class='num'>{_eur(r['amount_excl_cents'])}</td>"
        f"<td>{_CHIP_CORR if r.get('corrects') else ''}"
        f"{_CHIP_GEEN_DOC if r['revenue_line'] != 'net_sales' and not r.get('attachment') else ''}</td></tr>"
        for r in sorted(regels_, key=lambda x: (x["period"], x["created_at"]), reverse=True))
    tabel = ("<table class='mtab' aria-label='revenue'><tr><th>Period</th><th>Line</th><th>Batch</th>"
             "<th class='num'>Pairs</th><th class='num'>Excl. VAT</th><th></th></tr>"
             f"{rijen}</table>" if regels_ else "<p class='muted'>No revenue in this selection.</p>")
    per_maand = totalen(regels_, "period")
    per_lijn = totalen(regels_, "revenue_line")
    som = ("<table class='mtab' aria-label='totals per month'><tr><th>Month</th><th class='num'>Total</th></tr>"
           + "".join(f"<tr><td>{_e(k)}</td><td class='num'>{_eur(v)}</td></tr>" for k, v in sorted(per_maand.items()))
           + "</table><table class='mtab' aria-label='totals per line'><tr><th>Line</th><th class='num'>Total</th></tr>"
           + "".join(f"<tr><td>{_e(labels.get(k, k))}</td><td class='num'>{_eur(v)}</td></tr>" for k, v in per_lijn.items())
           + "</table>") if regels_ else ""
    nieuw = (_popover("+ add revenue", _omzetformulier(cfg, csrf, "finance_omzet_add", "/finance/revenue"))
             if mag_wijzigen(st, username) and csrf else "")
    inhoud = (f"<p class='muted'>Enter revenue on the period of delivery, as the accountant recognises it. "
              f"Any month can be entered, also in the past. A grant should carry its decision as a document.</p>"
              f"{filters}<p><a href='/finance/revenue.csv{'?' + q if q else ''}'>Export CSV for the accountant</a></p>"
              f"{nieuw}<div class='c2-sec'>{tabel}</div><div class='c2-sec'>{som}</div>")
    return _frame("Finance · Revenue", "/finance/revenue", inhoud, msg)


def render_revenue_regel(st, username, csrf: str, rid: str, msg: str = "") -> str | None:
    from nooch_village.finance_omzet import OpbrengstRegister, regels as omzetregels
    reg = OpbrengstRegister(st.dd)
    r = reg.get(rid)
    if r is None:
        return None
    cfg = fc.laad()
    labels = {x["key"]: x["label"] for x in omzetregels(cfg)}
    velden = [("Booking date", r["entry_date"]), ("Period", r["period"]),
              ("Line", labels.get(r["revenue_line"], r["revenue_line"])), ("Description", r["description"]),
              ("Excl. VAT", _eur(r["amount_excl_cents"])), ("VAT (stored, not counted)", _eur(r["vat_cents"])),
              ("Batch", r.get("batch", "")), ("Pairs", "" if r.get("pairs") is None else r["pairs"]),
              ("Source", r.get("source", "")), ("Note", r.get("note", "")), ("Corrects", r.get("corrects", "")),
              ("Recorded", f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created_at']))} by {r.get('created_by') or '—'}")]
    tabel = ("<table class='mtab' aria-label='revenue line'>"
             + "".join(f"<tr><th>{_e(k)}</th><td>{_e(str(v))}</td></tr>" for k, v in velden) + "</table>")
    b = r.get("attachment")
    doc = (f"<p>{_e(b['filename'])} · {b['size'] // 1024} KB · sha256 <code>{_e(b['sha256'][:16])}…</code></p>"
           f"<p><a href='/finance/file?reg=revenue&amp;id={_e(rid)}&amp;inline=1' target='_blank' rel='noopener'>Open</a> · "
           f"<a href='/finance/file?reg=revenue&amp;id={_e(rid)}'>Download</a></p>"
           if b else "<p class='muted'>No document.</p>")
    hist = reg.correcties_van(rid)
    hist_html = ("<ul>" + "".join(f"<li><a href='/finance/revenue/view?id={_e(x['id'])}'>{_e(x['note'] or x['id'])}</a> "
                                  f"({_eur(x['amount_excl_cents'])})</li>" for x in hist) + "</ul>"
                 if hist else "<p class='muted'>Not corrected.</p>")
    correct = ""
    if mag_wijzigen(st, username) and csrf and not r.get("corrects"):
        correct = _popover("Correct", "<p class='muted'>This adds a reversal of this line and a new line with "
                           "the values below. Nothing is overwritten.</p>"
                           + _omzetformulier(cfg, csrf, "finance_omzet_correct", f"/finance/revenue/view?id={rid}",
                                             r, extra=f"<input type='hidden' name='kid' value='{_e(rid)}'>"))
    inhoud = (f"<div class='c2-sec'>{tabel}</div><div class='c2-sec'><h2>Document</h2>{doc}</div>"
              f"<div class='c2-sec'><h2>Corrections</h2>{hist_html}{correct}</div>")
    return _frame(f"Finance · {r['description']}", "/finance/revenue", inhoud, msg)


def csv_omzet(regels_: list[dict]) -> str:
    def eur_nl(c: int) -> str:
        return euro(c).replace(".", ",")

    def cel(x) -> str:
        s = str(x if x is not None else "")
        return '"' + s.replace('"', '""') + '"' if any(t in s for t in (";", '"', "\n")) else s
    kol = ("id", "entry_date", "period", "revenue_line", "description", "batch", "pairs", "amount_excl_eur",
           "vat_eur", "currency", "source", "document", "corrects", "note")
    uit = [";".join(kol)]
    for r in sorted(regels_, key=lambda x: (x["period"], x["created_at"])):
        b = r.get("attachment") or {}
        doc = f"{b.get('filename', '')} sha256:{b.get('sha256', '')}" if b else ""
        uit.append(";".join(cel(v) for v in (
            r["id"], r["entry_date"], r["period"], r["revenue_line"], r["description"], r.get("batch", ""),
            "" if r.get("pairs") is None else r["pairs"], eur_nl(r["amount_excl_cents"]), eur_nl(r["vat_cents"]),
            r["currency"], r.get("source", ""), doc, r.get("corrects", ""), r.get("note", ""))))
    return "\r\n".join(uit) + "\r\n"


def verwerk_omzet(st, fields: dict, files: dict, *, username, door: str) -> str:
    """Een nieuwe opbrengstregel of een correctie. De rechten toetst de aanroeper (404)."""
    import hashlib
    from nooch_village.finance_omzet import OpbrengstRegister, maak_opbrengst
    cfg = fc.laad()
    reg = OpbrengstRegister(st.dd)
    correctie_van = fields.get("kid", "") if fields.get("action") == "finance_omzet_correct" else ""
    oud = reg.get(correctie_van) if correctie_van else None
    if correctie_van and oud is None:
        return "✗ the line to correct does not exist"
    v = {k: fields.get(k, "") for k in ("entry_date", "period", "revenue_line", "description", "amount_excl",
                                         "vat", "batch", "pairs", "note")}
    fname, blob = files.get("file") or ("", b"")
    if blob:
        h = hashlib.sha256(blob).hexdigest()
        # DUBBEL OVER BEIDE REGISTERS: hetzelfde document als kost én als opbrengst is net zo goed een vergissing.
        eerder = [r for r in reg.met_hash(h) + KostenRegister(st.dd).met_hash(h) if not oud or r["id"] != oud["id"]]
        if eerder and fields.get("bevestig_dubbel") != "1":
            e = eerder[0]
            return (f"⚠ this file is already in the register ({e['entry_date']}, "
                    f"{e.get('supplier') or e.get('description')}). Nothing saved — tick 'I know this file is "
                    f"already in the register' to save it anyway.")
        bijlage, fout = reg.bewaar_bijlage(fname, blob, jaar=(v["entry_date"] or "")[:4])
        if bijlage is None:
            return f"✗ {fout}"
        v["attachment"] = bijlage
    elif oud is not None and oud.get("attachment"):
        v["attachment"] = oud["attachment"]
    regel, fout, waarschuwing = maak_opbrengst(v, cfg)
    if regel is None:
        return f"✗ {fout}"
    if oud is not None:
        reg.correctie(correctie_van, regel, door=door)
        return "✓ corrected: a reversal and a new line were added"
    reg.voeg_toe(regel, door=door)
    return "✓ revenue saved" + (f" — ⚠ {waarschuwing}" if waarschuwing else "")


# ── /finance/history (PR 2a) ────────────────────────────────────────────────

def _jaar(jaar: str) -> str:
    return jaar if (len(jaar) == 4 and jaar.isdigit()) else time.strftime("%Y")


def _register_voor_cutover(st, h_tot: str) -> int:
    from nooch_village.finance_omzet import OpbrengstRegister
    if not h_tot:
        return 0
    return sum(1 for r in KostenRegister(st.dd).alle() + OpbrengstRegister(st.dd).alle() if r["period"] <= h_tot)


def render_history(st, username, csrf: str, jaar: str = "", msg: str = "") -> str:
    """Het raster: regels in P&L-volgorde × de maanden van één jaar. Bewerkbaar voor wie mag
    wijzigen; alleen gewijzigde cellen worden nieuwe regels. Onderaan de lagen als controle."""
    from nooch_village import finance_historie as fh
    cfg = fc.laad()
    jaar = _jaar(jaar)
    maanden = fh.maanden_van(jaar)
    hreg = fh.HistorieRegister(st.dd)
    actueel = hreg.actueel()
    met_geschiedenis = {(r["period"], r["line_key"]) for r in hreg.alle()}
    h_tot = fh.Instellingen(st.dd).history_until()
    schrijven = mag_wijzigen(st, username) and bool(csrf)

    def invoer(x, m):
        if x["soort"] == "paren":
            r = actueel.get((m, fh.NET_SALES))
            waarde = "" if not r or r.get("pairs") is None else str(r["pairs"])
            sleutel = (m, fh.NET_SALES)
        else:
            r = actueel.get((m, x["key"]))
            waarde = euro(r["amount_cents"]) if r else ""
            sleutel = (m, x["key"])
        terug = ""
        if sleutel in met_geschiedenis:
            terug = (f" <a class='muted' href='/finance/history/cell?period={_e(sleutel[0])}&amp;line={_e(sleutel[1])}' "
                     f"aria-label='earlier values of {_e(x['label'])} {_e(m)}'>↺</a>")
        if not schrijven:
            return f"<td class='num'>{_e(waarde) or _STREEP}{terug}</td>"
        modus = "numeric" if x["soort"] == "paren" else "decimal"
        return (f"<td class='num'><input name='c|{_e(x['key'])}|{m}' value='{_e(waarde)}' inputmode='{modus}' "
                f"size='8' aria-label='{_e(x['label'])} {m}'>{terug}</td>")

    kop = "".join(f"<th class='num'>{m[5:]}</th>" for m in maanden)
    rijen = []
    for x in fh.lijnen(cfg):
        if x["soort"] == "kop":
            rijen.append(f"<tr><td colspan='{len(maanden) + 1}'><strong>{_e(x['label'])}</strong></td></tr>")
            continue
        rijen.append(f"<tr><td>{_e(x['label'])}</td>{''.join(invoer(x, m) for m in maanden)}</tr>")
    raster = (f"<table class='mtab' aria-label='history {jaar}'><tr><th>{jaar}</th>{kop}</tr>"
              f"{''.join(rijen)}</table>")
    if schrijven:
        raster = (f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
                  f"<input type='hidden' name='action' value='finance_hist_opslaan'>"
                  f"<input type='hidden' name='next' value='/finance/history?jaar={jaar}'>"
                  f"<input type='hidden' name='jaar' value='{jaar}'>{raster}"
                  f"<input name='note' aria-label='note for this save' placeholder='Note (e.g. Venema 2025 annual figures)'>"
                  f"<button class='btn ok sm' type='submit'>Save changed cells</button></form>"
                  f"<p class='muted'>An empty cell means no data, not zero. Emptying a cell that has a value "
                  f"clears it; the old value stays in the cell history (↺).</p>")
    # DE LAGEN ALS CONTROLE: alleen uit de ingevulde historie van dit jaar, los van de cutover — zo
    # vergelijk je de invoer met het resultaat van Venema.
    hk, ho, hp = fh.posten({k: r for k, r in actueel.items() if k[0][:4] == jaar}, cfg)
    uit = finance_pnl.bereken(hk, cfg, opbrengsten=ho, paren=hp, maanden=maanden, historie_tot=f"{jaar}-12")
    gevuld = {p[0] for p in hk} | {p[0] for p in ho}
    lagen = "".join(
        f"<tr><td><strong>{_e(r['label'])}</strong></td>"
        + "".join(f"<td class='num'>{_eur(r['waarden'].get(m)) if m in gevuld else _GEEN_DATA}</td>"
                  for m in maanden) + "</tr>"
        for r in uit["rijen"] if r["soort"] in ("omzet", "laag"))
    controle = (f"<h2>Check: layers from the history above</h2><table class='mtab' aria-label='layers {jaar}'>"
                f"<tr><th></th>{kop}</tr>{lagen}</table>")
    nav = (f"<p><a href='/finance/history?jaar={int(jaar) - 1}'>← {int(jaar) - 1}</a> · <strong>{jaar}</strong> · "
           f"<a href='/finance/history?jaar={int(jaar) + 1}'>{int(jaar) + 1} →</a> · "
           f"<a href='/finance/history.csv?jaar={jaar}'>Export CSV</a> · "
           f"<a href='/finance/history.xlsx?jaar={jaar}'>Export XLSX</a> · <a href='/finance/pnl'>P&amp;L</a></p>")
    cutover = (f"<p>Cutover: months up to and including <strong>{_e(h_tot)}</strong> come from this history; "
               f"later months from the register.</p>" if h_tot else
               "<p class='muted'>No cutover set: the P&amp;L uses only the register. Set a cutover month to use "
               "this history.</p>")
    n_voor = _register_voor_cutover(st, h_tot)
    if n_voor:
        cutover += _cutover_waarschuwing(n_voor, h_tot)
    beheer = ""
    if schrijven:
        beheer = _popover("Cutover", (
            f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='action' value='finance_hist_cutover'>"
            f"<input type='hidden' name='next' value='/finance/history?jaar={jaar}'>"
            f"<input type='month' name='history_until' value='{_e(h_tot)}' aria-label='history until (empty = no history)'>"
            f"<button class='btn ok sm' type='submit'>Save</button></form>"
            f"<p class='muted'>Every change is logged (who, when, old and new value).</p>"))
        beheer += _popover("Import", (
            f"<form method='post' action='/action' enctype='multipart/form-data'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='action' value='finance_hist_import'>"
            f"<input type='hidden' name='next' value='/finance/history?jaar={jaar}'>"
            f"<input type='file' name='file' accept='.csv,.xlsx' aria-label='CSV or XLSX in the export format' required>"
            f"<button class='btn sm' type='submit'>Preview</button></form>"
            f"<p class='muted'>Same format as the export. An empty cell in the file only clears a filled cell if you tick that in the preview. You see a preview first; nothing is saved until you confirm.</p>"))
    log = fh.Instellingen(st.dd).alle()[-5:]
    loghtml = ("<ul>" + "".join(
        f"<li class='muted'>{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created_at']))} · "
        f"{_e(r.get('created_by') or '—')}: {_e(r.get('old') or 'none')} → {_e(r.get('new') or 'none')}</li>"
        for r in reversed(log)) + "</ul>") if log else ""
    inhoud = (f"<p><span class='chip'>{_e(fh.LABEL)}</span></p>{cutover}{loghtml}{nav}{beheer}"
              f"<div class='c2-sec'>{raster}</div><div class='c2-sec'>{controle}</div>")
    return _frame("Finance · History", "/finance/history", inhoud, msg)


def render_history_cel(st, username, period: str, line: str) -> str | None:
    from nooch_village import finance_historie as fh
    reg = fh.HistorieRegister(st.dd)
    hist = reg.geschiedenis(period, line)
    if not hist:
        return None
    labels = {x["key"]: x["label"] for x in fh.lijnen(fc.laad())}
    rijen = "".join(
        f"<tr><td>{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created_at']))}</td>"
        f"<td>{_e(r.get('created_by') or '—')}</td>"
        f"<td class='num'>{'no data (cleared)' if r.get('cleared') else _eur(r['amount_cents'])}</td>"
        f"<td class='num'>{'' if r.get('pairs') is None else r['pairs']}</td><td>{_e(r.get('source', ''))}</td>"
        f"<td>{_e(r.get('note', ''))}</td><td>{'current' if i == 0 else 'replaced'}</td></tr>"
        for i, r in enumerate(hist))
    tabel = ("<table class='mtab' aria-label='cell history'><tr><th>When</th><th>Who</th><th class='num'>Amount</th>"
             f"<th class='num'>Pairs</th><th>Source</th><th>Note</th><th></th></tr>{rijen}</table>")
    terug = f"<p><a href='/finance/history?jaar={_e(period[:4])}'>← history {_e(period[:4])}</a></p>"
    return _frame(f"Finance · {labels.get(line, line)} {period}", "/finance/history",
                  f"{terug}<div class='c2-sec'>{tabel}</div>")


def verwerk_history_opslaan(st, form: dict, *, door: str) -> str:
    """Het raster opslaan: alleen GEWIJZIGDE cellen worden nieuwe regels (met `supersedes`). Een
    cel met een waarde die leeg wordt aangeboden, wordt leeggemaakt (`cleared`). De rechten toetst
    de aanroeper (404)."""
    from nooch_village import finance_historie as fh
    cfg = fc.laad()
    hreg = fh.HistorieRegister(st.dd)
    bedragen, paren_, leeg, paren_leeg, fouten = {}, {}, set(), set(), []
    for naam, waarden in form.items():
        if not naam.startswith("c|"):
            continue
        _c, key, m = (naam.split("|") + ["", ""])[:3]
        v = (waarden[0] if isinstance(waarden, list) else waarden).strip()
        if key == fh.PAREN:
            n, fout = fh.paren(v)
            if fout:
                fouten.append(f"{m} pairs: {fout}")
            elif n is not None:
                paren_[m] = n
            else:
                paren_leeg.add(m)
            continue
        c, fout = fh.bedrag(v)
        if fout:
            fouten.append(f"{m} {key}: {fout}")
        elif c is not None:
            bedragen[(m, key)] = c
        else:
            leeg.add((m, key))
    if fouten:
        return "✗ nothing saved — " + "; ".join(fouten[:5])
    diff = fh.vergelijk(bedragen, paren_, hreg.laatste(), cfg, leeg=leeg, paren_leeg=paren_leeg)
    if diff["fouten"]:
        return "✗ nothing saved — " + "; ".join(diff["fouten"][:5])
    note = form.get("note", [""])
    hreg.schrijf(diff["schrijf"], door=door, note=note[0] if isinstance(note, list) else note)
    return f"✓ {diff['nieuw']} new, {diff['gewijzigd']} changed, {diff['geleegd']} cleared"


def _vorm_wijziging(w: dict, labels: dict) -> str:
    oud = w.get("oud")
    was = f"{_eur(oud['amount_cents'])}" if oud else "no data"
    paar = f" · pairs {w['pairs']}" if w.get("pairs") is not None else ""
    na = "no data (cleared)" if w.get("cleared") else f"{_eur(w['amount_cents'])}{paar}"
    return (f"<tr><td>{_e(w['period'])}</td><td>{_e(labels.get(w['line_key'], w['line_key']))}</td>"
            f"<td class='num'>{was}</td><td class='num'>{na}</td></tr>")


def _import_diffs(gelezen: dict, laatste: dict, cfg: dict) -> tuple[dict, dict, list[dict]]:
    """(zonder, met, te_legen): de import ZONDER leegmaken (de standaard), MET leegmaken, en de
    regels die alleen het vinkje "also clear" toevoegt — lege cellen in het bestand die nu een waarde
    hebben (ook paren die leeg zijn aangeboden). Zo toont de preview ze altijd, en schrijft de import
    ze alleen als Stefan het vinkje aanzet (besluit 10 oktober)."""
    from nooch_village import finance_historie as fh
    zonder = fh.vergelijk(gelezen["bedragen"], gelezen["paren"], laatste, cfg)
    met = fh.vergelijk(gelezen["bedragen"], gelezen["paren"], laatste, cfg,
                       leeg=gelezen["leeg"], paren_leeg=gelezen["paren_leeg"])
    basis = {(w["period"], w["line_key"]): w for w in zonder["schrijf"]}
    te_legen = [w for w in met["schrijf"]
                if {k: v for k, v in w.items() if k != "oud"}
                != {k: v for k, v in (basis.get((w["period"], w["line_key"])) or {}).items() if k != "oud"}]
    return zonder, met, te_legen


def verwerk_history_import(st, fields: dict, files: dict, *, door: str, csrf: str) -> tuple[str, str]:
    """Stap 1: bewaar het bestand (borging) en toon een PREVIEW → ("html", pagina) of ("msg", melding).
    Stap 2 (`bevestig`): lees het bewaarde bestand opnieuw (hash gecontroleerd), vergelijk opnieuw
    met de actuele stand en schrijf. Fouten blokkeren tenzij expliciet "ook de geldige rijen". Een
    lege cel in het bestand maakt een gevulde cel ALLEEN leeg met het vinkje `also_clear`."""
    from nooch_village import finance_historie as fh
    cfg = fc.laad()
    log = fh.ImportLog(st.dd)
    hreg = fh.HistorieRegister(st.dd)
    if fields.get("action") == "finance_hist_import_bevestig":
        imp = log.status(fields.get("import_id", ""))
        if imp is None or imp.get("status") != "previewed":
            return "msg", "✗ this import does not exist or was already handled"
        blob, fout = log.lees_bijlage(imp)
        if blob is None:
            return "msg", f"✗ {fout}"
        gelezen = fh.lees_bestand(imp["attachment"]["filename"], blob, cfg)
        zonder, met, te_legen = _import_diffs(gelezen, hreg.laatste(), cfg)
        legen = fields.get("also_clear") == "1"
        diff = met if legen else zonder
        fouten = gelezen["fouten"] + diff["fouten"]
        if fouten and fields.get("valid_rows") != "1":
            return "msg", "✗ nothing imported: the file has errors — confirm that the valid rows may go ahead"
        hreg.schrijf(diff["schrijf"], door=door, bron=f"import:{imp['import_id']}",
                     note=f"Import {imp['attachment']['filename']}")
        geleegd = len(te_legen) if legen else 0
        log.meld(imp, door=door, status="applied", rows=gelezen["rijen"], new=diff["nieuw"],
                 changed=diff["gewijzigd"], cleared=geleegd, skipped_clears=0 if legen else len(te_legen),
                 errors=len(fouten))
        uit = (f"✓ imported: {zonder['nieuw']} new, {zonder['gewijzigd']} changed, {geleegd} cleared, "
               f"{zonder['ongewijzigd']} unchanged")
        if te_legen and not legen:
            uit += f" — {len(te_legen)} empty cell(s) in the file were skipped (not cleared)"
        return "msg", uit
    fname, blob = files.get("file") or ("", b"")
    imp, fout = log.bewaar(fname, blob, door=door)
    if imp is None:
        return "msg", f"✗ {fout}"
    gelezen = fh.lees_bestand(fname, blob, cfg)
    zonder, met, te_legen = _import_diffs(gelezen, hreg.laatste(), cfg)
    fouten = gelezen["fouten"] + zonder["fouten"]
    labels = {x["key"]: x["label"] for x in fh.lijnen(cfg)}
    tabel = ("<table class='mtab' aria-label='changes'><tr><th>Month</th><th>Line</th><th class='num'>Now</th>"
             "<th class='num'>After import</th></tr>"
             + "".join(_vorm_wijziging(w, labels) for w in zonder["schrijf"][:300]) + "</table>"
             if zonder["schrijf"] else "<p class='muted'>No changes.</p>")
    leeg_tabel = ""
    if te_legen:
        leeg_tabel = ("<h2>Empty in the file, filled now</h2><p class='muted'>Skipped unless you tick "
                      "\"also clear\" below.</p><table class='mtab' aria-label='cells to clear'><tr><th>Month</th>"
                      "<th>Line</th><th class='num'>Now</th><th class='num'>With the tick</th></tr>"
                      + "".join(_vorm_wijziging(w, labels) for w in te_legen[:300]) + "</table>")
    foutlijst = ("<h2>Errors</h2><ul>" + "".join(f"<li>{_e(f)}</li>" for f in fouten[:200]) + "</ul>"
                 if fouten else "")
    ook = ("<input type='checkbox' id='fin-valid-rows' name='valid_rows' value='1'>"
           "<label for='fin-valid-rows'>Import the valid rows anyway; the rows with errors are skipped</label>"
           if fouten else "")
    if te_legen:
        ook += (f"<input type='checkbox' id='fin-also-clear' name='also_clear' value='1'>"
                f"<label for='fin-also-clear'>Also clear {len(te_legen)} cell(s)</label>")
    bevestig = (f"<form method='post' action='/action' enctype='multipart/form-data'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='action' value='finance_hist_import_bevestig'>"
                f"<input type='hidden' name='import_id' value='{_e(imp['import_id'])}'>"
                f"<input type='hidden' name='next' value='{_e(fields.get('next') or '/finance/history')}'>{ook}"
                f"<button class='btn ok sm' type='submit'>Confirm import</button> "
                f"<a href='{_e(fields.get('next') or '/finance/history')}'>Cancel</a></form>"
                if (zonder["schrijf"] or te_legen) else "")
    inhoud = (f"<p>{_e(imp['attachment']['filename'])} · sha256 <code>{_e(imp['attachment']['sha256'][:16])}…</code> · "
              f"{gelezen['rijen']} row(s)</p>"
              f"<p><strong>{zonder['nieuw']}</strong> new · <strong>{zonder['gewijzigd']}</strong> changed · "
              f"<strong>{len(te_legen)}</strong> to clear (only with the tick) · "
              f"<strong>{zonder['ongewijzigd']}</strong> unchanged · <strong>{len(fouten)}</strong> error(s)</p>"
              f"{foutlijst}{bevestig}<div class='c2-sec'>{tabel}{leeg_tabel}</div>")
    return "html", _frame("Finance · Import preview", "/finance/history", inhoud)


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
