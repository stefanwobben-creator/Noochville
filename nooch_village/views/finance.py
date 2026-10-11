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
from nooch_village import finance_uitleg as fu
from nooch_village.web_base import _banner, _e, _field, _page

GROEP = "finance"
_CHIP_CORR = "<span class='chip'>correction</span>"
_CHIP_GEEN_DOC = "<span class='chip'>missing document</span>"
_DOORLOPEND = "<span class='muted'>ongoing</span>"
_STREEP = "<span class='muted'>—</span>"
#: Een brede tabel in zijn eigen scrollcontainer (`.c2-scroll`, 11 oktober 2026). ALLEEN om een
#: tabel: om een gewone alinea (de lege toestand) verandert `overflow` het samenvallen van marges.
_SCROLL = " c2-scroll"


def _scrolt(tabel: str) -> str:
    """Alleen de tabel in een scrollcontainer, niet het kopje erboven (zelfde reden als `_SCROLL`)."""
    return f"<div class='c2-scroll'>{tabel}</div>"
_GEEN_DATA = "<span class='muted'>no data</span>"
_SCHERMEN = (("/finance/costs", "Costs"), ("/finance/revenue", "Revenue"), ("/finance/recurring", "Recurring"),
             ("/finance/monthly", "Monthly"), ("/finance/pnl", "P&L"), ("/finance/history", "History"),
             ("/fixed-costs", "Runway inputs"), ("/finance/help", "Help"))


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
    # `c2-main--vol`: op een telefoon de volle breedte, zodat een brede tabel in zijn eigen
    # scrollcontainer blijft (`c2-scroll`) in plaats van de hele pagina breder te maken.
    main = (f"<div class='c2-main c2-main--vol'><h1 class='ptitle'>{_e(titel)}</h1>"
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


# ── formulieren: label, hulptekst, blokken (UX-PR, 11 oktober 2026) ─────────
#
# ATOMEN: `_field` (label + veld als paar, `.att-lbl`), `.muted` (hulptekst), " *" (verplicht).
# MOLECULEN: `_veld` (één veld: label, veld, fout, hulptekst in een `.qadd-form`-kolom) en `_blok`
# (een `.card` met een kop en `.rov-addgrid`: twee kolommen op een breed scherm, één op een telefoon).
# PATRONEN: de formulieren hieronder. De TEKSTEN komen uit `finance_uitleg` — één plek, ook voor
# `/finance/help`. De veldnamen (wat er gepost wordt) zijn ongewijzigd.

def _veld(tabel: dict, naam: str, pre: str, *, waarde: str = "", kind: str = "text", opties=None,
          leeg: str = "", attrs: str = "", fout: str = "", toon_als: str = "", na: str = "") -> str:
    label, verplicht, hulp, voorbeeld = tabel[naam]
    fid = f"{pre}-{naam}"
    tekst = label + (" *" if verplicht else "")
    if opties is not None:
        ctrl = (f"<label class='att-lbl' for='{fid}'>{_e(tekst)}</label>"
                f"<select id='{fid}' name='{naam}'{' required' if verplicht else ''}{' ' + attrs if attrs else ''}>"
                f"{_opties(opties, waarde, leeg)}</select>")
    else:
        # DE PLACEHOLDER IS ALLEEN NOG EEN VOORBEELD: hij verdwijnt bij typen, het label niet.
        ph = f"Example: {voorbeeld}" if voorbeeld and kind == "text" else ""
        ctrl = _field(tekst, naam, kind=kind, value=waarde, fid=fid, required=verplicht, placeholder=ph,
                      attrs=attrs)
    fout_html = f"<div class='muted'><strong>⚠ {_e(fout)}</strong></div>" if fout else ""
    toon = f" data-toon-als='{_e(toon_als)}'" if toon_als else ""
    # DE GRIDCEL IS EEN KALE <div>: een `.qadd-form` (flex-kolom) direct in de cel rekt mee met de
    # hoogste buurcel, en dan groeit het invoerveld in de hoogte mee. Gezien in de browser.
    return (f"<div{toon}><div class='qadd-form'>{ctrl}</div>{na}{fout_html}"
            f"<div class='muted'>{_e(hulp)}</div></div>")


#: Een browser kan een gekozen bestand niet terugzetten na een fout; dat zeggen we erbij.
_OPNIEUW = "Choose the file again: a browser cannot keep a file after an error."


def _blok(titel: str, inhoud: str) -> str:
    return f"<div class='card'><h3>{_e(titel)}</h3><div class='rov-addgrid'>{inhoud}</div></div>"


def _hulp_link(anker: str) -> str:
    return f"<p class='muted'><a href='/finance/help#{_e(anker)}'>How do I fill this in?</a></p>"


#: Welke melding bij welk veld hoort: (stukje van de melding, veld). De meldingen komen van de
#: bestaande controles (`maak_kost`, `maak_opbrengst`, `maak_regel`); die veranderen niet.
_FOUT_VELD = (
    ("invoice date", "entry_date"), ("booking date", "entry_date"), ("period must", "period"),
    ("supplier and description", "supplier"), ("a description is required", "description"),
    ("pick a revenue line", "revenue_line"), ("amounts must", "amount_excl"),
    ("negative amounts", "amount_excl"), ("needs a note", "note"), ("pairs", "pairs"),
    ("pick a management line", "management_line"), ("unknown management line", "management_line"),
    ("payment status", "payment_status"), ("paid date", "paid_date"),
    ("attach the invoice", "no_document_reason"), ("already in the register", "file"),
    ("only pdf", "file"), ("larger than 10 mb", "file"), ("not a real", "file"), ("file is empty", "file"),
    ("amount per month", "bedrag"), ("start date", "van"), ("end date", "tot"),
)


def fout_veld(msg: str, velden) -> str:
    """Het veld waar deze foutmelding bij hoort (uit `velden`), of "" — dan alleen de banner."""
    m = (msg or "").lower()
    if "a description is required" in m and "omschrijving" in velden:
        return "omschrijving"
    return next((v for stuk, v in _FOUT_VELD if stuk in m and v in velden), "")


def _waarden(r: dict | None, waarden: dict | None, bedragen: dict) -> callable:
    """Een lezer voor de waarde van een veld: eerst wat er net gepost is (na een fout blijft het
    staan), anders het record (bedragen in centen → euro's)."""
    def lees(naam: str) -> str:
        if waarden is not None:
            v = waarden.get(naam, "")
            return str(v[0] if isinstance(v, list) else v)
        r_ = r or {}
        if naam in bedragen:
            return euro(r_[bedragen[naam]]) if r_.get(bedragen[naam]) is not None else ""
        return str(r_.get(naam) or "")
    return lees


def _btw_hulp(pre: str) -> str:
    """De rekenhulp "Only know the total?": vult `amount_excl` en `vat` in hele centen (`nooch.js`,
    `NV.finBtw`). De velden zelf blijven wat er wordt opgeslagen. Zonder JavaScript doet de knop
    niets, en vul je de twee velden zelf in."""
    tarieven = [(str(t), f"{t}%") for t in fu.BTW_TARIEVEN]
    return (f"<details class='acard-d'><summary class='chip outline'>{_e(fu.BTW_HULP)}</summary>"
            f"<div class='datepop'>"
            f"{_field('Total incl. VAT', '', fid=f'{pre}-btw-totaal', placeholder='Example: 121,00', attrs='inputmode=decimal')}"
            f"<label class='att-lbl' for='{pre}-btw-tarief'>VAT rate</label>"
            f"<select id='{pre}-btw-tarief'>{_opties(tarieven, '21')}</select>"
            f"<button class='btn sm' type='button' data-btw-reken='{pre}'>Fill in the two fields</button>"
            f"</div></details>")


def _kostvelden(st, cfg: dict, r: dict | None = None, *, pre: str = "fk", waarden: dict | None = None,
                fout: str = "") -> str:
    """De velden van een kostregel (nieuw of correctie), in vier blokken. Bedragen in euro's; de
    server rekent in centen. `waarden` = wat er net gepost is (na een fout); `fout` = de melding."""
    lees = _waarden(r, waarden, {"amount_excl": "amount_excl_cents", "vat": "vat_cents"})
    regels = [(x["key"], x["label"]) for x in fc.regels(cfg)]
    accounts = [a["naam_nl"] for a in cfg.get("accounts") or []]
    rec = [(x["id"], x["description"]) for x in st.vaste_kosten.alle()]
    bij = fout_veld(fout, fu.KOSTEN)
    T = fu.KOSTEN

    def v(naam, **kw):
        f_ = fout if bij == naam else (_OPNIEUW if naam == "file" and waarden is not None and fout else "")
        return _veld(T, naam, pre, waarde=lees(naam), fout=f_, **kw)

    # DOCUMENT: EEN EXPLICIETE KEUZE in plaats van twee losse velden naast elkaar. De radioknoppen
    # heten `doc_choice`, en die naam leest de server niet: het bestand of de reden blijft beslissen.
    # Zonder JavaScript staan beide velden er gewoon.
    geen = bool(lees("no_document_reason")) or (r is not None and not r.get("attachment") and waarden is None)
    keuze = (f"<div class='qadd-form' role='radiogroup' aria-label='document'>"
             f"<span class='att-lbl'>Document *</span>"
             f"<span><input type='radio' id='{pre}-doc-have' name='doc_choice' value='have'{'' if geen else ' checked'}>"
             f"<label for='{pre}-doc-have'>{_e(fu.DOC_HEB)}</label> "
             f"<input type='radio' id='{pre}-doc-none' name='doc_choice' value='none'{' checked' if geen else ''}>"
             f"<label for='{pre}-doc-none'>{_e(fu.DOC_GEEN)}</label></span></div>")
    dubbel = (f"<div><input type='checkbox' id='{pre}-dubbel' name='bevestig_dubbel' value='1'>"
              f"<label for='{pre}-dubbel' class='muted'>I know this file is already in the register</label></div>")
    document = (keuze
                + v("file", kind="file", attrs="accept='.pdf,.png,.jpg,.jpeg'", toon_als="doc_choice=have", na=dubbel)
                + v("no_document_reason", toon_als="doc_choice=none"))
    factuur = v("supplier") + v("description") + v("entry_date", kind="date") + v("period", kind="month") + document
    bedrag = (v("amount_excl", attrs="inputmode='decimal'") + v("vat", attrs="inputmode='decimal'")
              + f"<div class='qadd-form'>{_btw_hulp(pre)}</div>")
    pnl = (v("account_code", attrs=f"list='{pre}-accounts'", na=_lijst(f"{pre}-accounts", accounts))
           + v("management_line", opties=regels, leeg="— from the account —")
           + v("batch", attrs=f"list='{pre}-batches'", na=_lijst(f"{pre}-batches", cfg.get("batches") or [])))
    betaling = (v("payment_status", opties=[("open", "Open"), ("paid", "Paid")])
                + v("paid_date", kind="date", toon_als="payment_status=paid")
                + v("recurring_id", opties=rec, leeg="Not a recurring cost") + v("note"))
    kop = [t for t, _v in fu.KOSTEN_BLOKKEN]
    return _blok(kop[0], factuur) + _blok(kop[1], bedrag) + _blok(kop[2], pnl) + _blok(kop[3], betaling)


def _kostformulier(st, cfg: dict, csrf: str, actie: str, terug: str, r: dict | None = None,
                   extra: str = "", *, pre: str = "fk", waarden: dict | None = None, fout: str = "") -> str:
    return (f"<form method='post' action='/action' enctype='multipart/form-data'>"
            f"<p class='muted'>{_e(fu.KOSTEN_KOP)}</p>{_hulp_link('costs')}"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='action' value='{actie}'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>{extra}"
            f"{_kostvelden(st, cfg, r, pre=pre, waarden=waarden, fout=fout)}"
            f"<button class='btn ok sm' type='submit'>Save</button></form>")


def _annuleer_kaart(csrf: str, actie: str, kid: str, terug: str) -> str:
    """"Cancel line": alleen een tegenboeking, met een verplichte reden (11 oktober 2026). Correct
    maakt altijd ook een vervangende regel; wie een regel gewoon niet had moeten invoeren, wil die niet."""
    return _nieuw_kaart("Cancel line", (
        f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
        f"<input type='hidden' name='action' value='{actie}'><input type='hidden' name='kid' value='{_e(kid)}'>"
        f"<input type='hidden' name='next' value='{_e(terug)}'>"
        f"<p class='muted'>{_e(fu.ANNULEER_KOP)}</p>{_hulp_link('mistakes')}"
        f"{_veld(fu.ANNULEER, 'reason', 'fa', attrs='')}"
        f"<button class='btn sm' type='submit'>Cancel this line</button></form>"), open_=False)


def verwerk_annuleer(st, fields: dict, *, door: str, register) -> str:
    """Annuleer een kost- of omzetregel: alleen de tegenboeking. De rechten toetst de aanroeper (404)."""
    reg = register(st.dd)
    kid = fields.get("kid", "")
    if reg.get(kid) is None:
        return "✗ the line does not exist"
    if reg.niet_te_corrigeren(kid):
        return f"✗ {reg.niet_te_corrigeren(kid)}"
    if not " ".join(str(fields.get("reason") or "").split()):
        return "✗ give a reason for cancelling the line"
    reg.annuleer(kid, fields["reason"], door=door)
    return "✓ cancelled: a reversal was added, and the line now counts as zero"


def _nieuw_kaart(label: str, inhoud: str, open_: bool) -> str:
    """Het formulier voor een nieuwe regel: een volle kaart, niet in een klein popover-blokje. Open
    als er nog niets is, of als er net een fout was (dan staat wat je invulde er nog)."""
    return (f"<details class='card'{' open' if open_ else ''}><summary><strong>{_e(label)}</strong></summary>"
            f"{inhoud}</details>")


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


def _filter_select(label: str, naam: str, fid: str, opties, waarde: str, leeg: str) -> str:
    return (f"<div><div class='qadd-form'><label class='att-lbl' for='{fid}'>{_e(label)}</label>"
            f"<select id='{fid}' name='{naam}'>{_opties(opties, waarde, leeg)}</select></div></div>")


def _filter_veld(label: str, naam: str, fid: str, waarde: str, kind: str = "text") -> str:
    return f"<div><div class='qadd-form'>{_field(label, naam, kind=kind, value=waarde, fid=fid)}</div></div>"


def render_costs(st, username, csrf: str, f: dict, msg: str = "", *, waarden: dict | None = None,
                 fout: str = "") -> str:
    cfg = fc.laad()
    regels = gefilterd(st, f)
    labels = {x["key"]: x["label"] for x in fc.regels(cfg)}
    # ZICHTBARE LABELS IN DE FILTERBALK (UX-PR): een placeholder verdwijnt zodra je typt.
    filterform = (f"<form method='get' action='/finance/costs' aria-label='filters'><div class='rov-addgrid'>"
                  f"{_filter_veld('Period', 'periode', 'ff-periode', f.get('periode', ''), 'month')}"
                  f"{_filter_veld('Account', 'account', 'ff-account', f.get('account', ''))}"
                  f"{_filter_select('Management line', 'regel', 'ff-regel', sorted(labels.items(), key=lambda x: x[1]), f.get('regel', ''), 'All lines')}"
                  f"{_filter_veld('Batch', 'batch', 'ff-batch', f.get('batch', ''))}"
                  f"{_filter_veld('Supplier', 'leverancier', 'ff-leverancier', f.get('leverancier', ''))}"
                  f"{_filter_select('Payment status', 'status', 'ff-status', [('open', 'Open'), ('paid', 'Paid')], f.get('status', ''), 'Any status')}"
                  f"</div><input type='checkbox' id='fin-missing-doc' name='missing_doc' value='1'"
                  f"{' checked' if f.get('missing_doc') == '1' else ''}>"
                  f"<label for='fin-missing-doc' class='muted'>Only lines with a missing document</label> "
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
    alles_leeg = not KostenRegister(st.dd).alle()
    tabel = ("<table class='mtab' aria-label='costs'><tr><th>Date</th><th>Supplier</th><th>Account</th>"
             "<th>Management line</th><th>Batch</th><th class='num'>Excl. VAT</th><th>Status</th><th></th></tr>"
             f"{rijen}</table>" if regels else
             f"<p class='muted'>{_e(fu.LEEG['costs'] if alles_leeg else 'No costs in this selection.')}</p>")
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
    nieuw = (_nieuw_kaart("+ Add a cost line",
                          _kostformulier(st, cfg, csrf, "finance_kost_add", "/finance/costs",
                                         waarden=waarden, fout=fout),
                          open_=alles_leeg or bool(fout))
             if mag_wijzigen(st, username) and csrf else "")
    # DE FILTERS IN EEN POPOVER: zeven velden naast elkaar liepen op een gewoon scherm al buiten beeld.
    actief = ", ".join(f"{k}: {v}" for k, v in f.items() if v)
    filters = (_popover("Filter", filterform)
               + (f"<span class='muted'>{_e(actief)} · <a href='/finance/costs'>clear</a></span>" if actief else ""))
    inhoud = (f"{filters}<p><a href='/finance/costs.csv{'?' + q if q else ''}'>Export CSV for the accountant</a></p>"
              f"{nieuw}<div class='c2-sec{_SCROLL if regels else ""}'>{tabel}</div><div class='c2-sec'>{som}</div>{open_punten}")
    return _frame("Finance · Costs", "/finance/costs", inhoud, msg)


def render_cost(st, username, csrf: str, kid: str, msg: str = "", *, waarden: dict | None = None,
                fout: str = "") -> str | None:
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
    if mag_wijzigen(st, username) and csrf:
        if reg.niet_te_corrigeren(kid):
            correct = f"<p class='muted'>{_e(reg.niet_te_corrigeren(kid).capitalize())}.</p>"
        else:
            correct = (_nieuw_kaart("Correct", "<p class='muted'>This adds a reversal of this line and a new line "
                                    "with the values below. Nothing is overwritten.</p>"
                                    + _kostformulier(st, cfg, csrf, "finance_kost_correct",
                                                     f"/finance/costs/view?id={kid}", r,
                                                     extra=f"<input type='hidden' name='kid' value='{_e(kid)}'>",
                                                     pre="fkc", waarden=waarden, fout=fout),
                                    open_=bool(fout))
                       + _annuleer_kaart(csrf, "finance_kost_cancel", kid, f"/finance/costs/view?id={kid}"))
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


def render_recurring(st, username, csrf: str, msg: str = "", *, waarden: dict | None = None,
                     fout: str = "", rid: str = "") -> str:
    """`waarden`/`fout`/`rid`: na een fout opnieuw getoond, met wat er was ingevuld (`rid` = de regel
    die bewerkt werd, leeg = een nieuwe)."""
    from nooch_village.finance_register import centen
    cfg = fc.laad()
    labels = {x["key"]: x["label"] for x in fc.regels(cfg)}
    bewerk = mag_wijzigen(st, username) and bool(csrf)
    T = fu.TERUGKEREND

    def velden(r=None, pre="fr", w=None, f_=""):
        # Het record heet anders dan het formulier (description → omschrijving): de vertaling hier.
        rec = {"omschrijving": (r or {}).get("description"), "leverancier": (r or {}).get("supplier"),
               "amount_cents": (r or {}).get("amount_cents"), **(r or {})}
        lees = _waarden(rec if r else None, w, {"bedrag": "amount_cents"})
        bij = fout_veld(f_, T)

        def v(naam, **kw):
            return _veld(T, naam, pre, waarde=lees(naam), fout=f_ if bij == naam else "", **kw)
        # DE LIVE SAMENVATTING (`NV.finSamenvatting`), met dezelfde zin al vanaf de server, zodat hij
        # ook zonder JavaScript klopt voor wat er staat.
        zin = fu.samenvatting(centen(lees("bedrag")), lees("van"), lees("tot"))
        samen = f"<p class='muted' data-rc-samenvatting>{_e(zin)}</p>"
        kop = [t for t, _v in fu.TERUGKEREND_BLOKKEN]
        return (_blok(kop[0], v("omschrijving") + v("leverancier") + v("bedrag", attrs="inputmode='decimal'"))
                + _blok(kop[1], v("van", kind="date") + v("tot", kind="date") + samen)
                + _blok(kop[2], v("account_code", attrs=f"list='{pre}-accounts'",
                                  na=_lijst(f"{pre}-accounts", [a["naam_nl"] for a in cfg.get("accounts") or []]))
                        + v("management_line", opties=[(x["key"], x["label"]) for x in fc.regels(cfg)],
                            leeg="— none —")
                        + v("notitie")))

    def form(extra="", r=None, pre="fr", w=None, f_=""):
        return (f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='action' value='vaste_kosten_zet'>"
                f"<input type='hidden' name='next' value='/finance/recurring'>{extra}{_hulp_link('recurring')}"
                f"{velden(r, pre, w, f_)}<button class='btn ok sm' type='submit'>Save</button></form>")

    rijen = []
    for r in st.vaste_kosten.alle():
        acties = ""
        if bewerk:
            fout_hier = fout if rid == r["id"] else ""
            acties = (_nieuw_kaart("✎ Edit", form(f"<input type='hidden' name='rid' value='{_e(r['id'])}'>", r,
                                                  pre=f"fr-{r['id']}", w=waarden if fout_hier else None,
                                                  f_=fout_hier), open_=bool(fout_hier))
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
             + "".join(rijen) + "</table>" if rijen else f"<p class='muted'>{_e(fu.LEEG['recurring'])}</p>")
    nieuw_fout = fout if not rid else ""
    nieuw = (_nieuw_kaart("+ Add a recurring cost", form(w=waarden if nieuw_fout else None, f_=nieuw_fout),
                          open_=not rijen or bool(nieuw_fout)) if bewerk else "")
    open_ = verwacht_niet_gefactureerd(st, _maanden_tot_nu())
    verwacht = ("<table class='mtab' aria-label='expected, not invoiced'><tr><th>Month</th><th>Recurring cost</th>"
                "<th class='num'>Expected</th></tr>"
                + "".join(f"<tr><td>{_e(x['maand'])}</td><td>{_e(x['description'])}</td>"
                          f"<td class='num'>{_eur(x['amount_cents'])}</td></tr>" for x in open_)
                + "</table>") if open_ else "<p class='muted'>Every recurring cost has an invoice line.</p>"
    inhoud = (f"<p class='muted'>{_e(fu.TERUGKEREND_KOP)}</p>"
              f"<p>Running today: <strong>{_eur(st.vaste_kosten.totaal_cents_op())}</strong> per month — the "
              f"fixed costs of the runway.</p>{nieuw}<div class='c2-sec{_SCROLL if rijen else ""}'>{tabel}</div>"
              f"<div class='c2-sec'><h2>Expected, not invoiced (last 6 months)</h2>{_scrolt(verwacht) if open_ else verwacht}</div>")
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
    return _frame("Finance · Monthly", "/finance/monthly", f"<div class='c2-sec c2-scroll'>{tabel}</div>")


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
    filt = (f"<form method='get' action='/finance/pnl' aria-label='filters'><div class='rov-addgrid'>"
            f"{_filter_veld('From month', 'van', 'fp-van', van, 'month')}"
            f"{_filter_veld('Until month', 'tot', 'fp-tot', tot, 'month')}"
            f"<div class='qadd-form'>{_field('Batch', 'batch', value=batch, fid='fp-batch', attrs='list=fin-batches')}"
            f"{_lijst('fin-batches', cfg.get('batches') or [])}</div>"
            f"{_filter_select('View', 'per', 'fp-per', [('', 'Amounts'), ('paar', 'Per pair')], per, '')}"
            f"</div><button class='btn sm' type='submit'>Filter</button></form>")
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
    return _frame("Finance · P&L", "/finance/pnl", f"{filt}{noot}<div class='c2-sec c2-scroll'>{tabel}</div>")


def _cutover_waarschuwing(n: int, h_tot: str) -> str:
    return (f"<div class='card'>⚠ {n} register line(s) fall in months up to the cutover "
            f"({_e(h_tot)}). They are kept, but not counted: those months come from the history.</div>")


# ── /finance/revenue ────────────────────────────────────────────────────────

OMZET_FILTERS = ("periode", "lijn", "batch")


def _omzetvelden(cfg: dict, r: dict | None = None, *, pre: str = "fo", waarden: dict | None = None,
                 fout: str = "") -> str:
    from nooch_village.finance_omzet import regels as omzetregels
    lees = _waarden(r, waarden, {"amount_excl": "amount_excl_cents", "vat": "vat_cents"})
    if waarden is None and r is None:
        lees_ = lees
        lees = lambda n: lees_(n) or ("net_sales" if n == "revenue_line" else "")
    bij = fout_veld(fout, fu.OMZET)
    T = fu.OMZET

    def v(naam, **kw):
        f_ = fout if bij == naam else (_OPNIEUW if naam == "file" and waarden is not None and fout else "")
        return _veld(T, naam, pre, waarde=lees(naam), fout=f_, **kw)
    dubbel = (f"<div><input type='checkbox' id='{pre}-dubbel' name='bevestig_dubbel' value='1'>"
              f"<label for='{pre}-dubbel' class='muted'>I know this file is already in the register</label></div>")
    kop = [t for t, _v in fu.OMZET_BLOKKEN]
    return (_blok(kop[0], v("entry_date", kind="date") + v("period", kind="month")
                  + v("revenue_line", opties=[(x["key"], x["label"]) for x in omzetregels(cfg)])
                  + v("description"))
            + _blok(kop[1], v("amount_excl", attrs="inputmode='decimal'") + v("vat", attrs="inputmode='decimal'")
                    + f"<div class='qadd-form'>{_btw_hulp(pre)}</div>")
            + _blok(kop[2], v("batch", attrs=f"list='{pre}-batches'",
                              na=_lijst(f"{pre}-batches", cfg.get("batches") or []))
                    + v("pairs", attrs="inputmode='numeric'"))
            + _blok(kop[3], v("file", kind="file", attrs="accept='.pdf,.png,.jpg,.jpeg'", na=dubbel) + v("note")))


def _omzetformulier(cfg: dict, csrf: str, actie: str, terug: str, r: dict | None = None, extra: str = "",
                    *, pre: str = "fo", waarden: dict | None = None, fout: str = "") -> str:
    return (f"<form method='post' action='/action' enctype='multipart/form-data'>"
            f"<p class='muted'>{_e(fu.OMZET_KOP)}</p>{_hulp_link('revenue-form')}"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='action' value='{actie}'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>{extra}"
            f"{_omzetvelden(cfg, r, pre=pre, waarden=waarden, fout=fout)}"
            f"<button class='btn ok sm' type='submit'>Save</button></form>")


def omzet_gefilterd(st, f: dict) -> list[dict]:
    from nooch_village.finance_omzet import OpbrengstRegister
    return [r for r in OpbrengstRegister(st.dd).alle()
            if (not f.get("periode") or r["period"] == f["periode"])
            and (not f.get("lijn") or r["revenue_line"] == f["lijn"])
            and (not f.get("batch") or r.get("batch") == f["batch"])]


def render_revenue(st, username, csrf: str, f: dict, msg: str = "", *, waarden: dict | None = None,
                   fout: str = "") -> str:
    from nooch_village.finance_omzet import regels as omzetregels
    cfg = fc.laad()
    labels = {x["key"]: x["label"] for x in omzetregels(cfg)}
    regels_ = omzet_gefilterd(st, f)
    filterform = (f"<form method='get' action='/finance/revenue' aria-label='filters'><div class='rov-addgrid'>"
                  f"{_filter_veld('Period', 'periode', 'fr-periode', f.get('periode', ''), 'month')}"
                  f"{_filter_select('Revenue line', 'lijn', 'fr-lijn', list(labels.items()), f.get('lijn', ''), 'All lines')}"
                  f"{_filter_veld('Batch', 'batch', 'fr-batch', f.get('batch', ''))}"
                  f"</div><button class='btn sm' type='submit'>Filter</button></form>")
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
             f"{rijen}</table>" if regels_ else
             f"<p class='muted'>{_e('No revenue in this selection.' if any(f.values()) else fu.LEEG['revenue'])}</p>")
    per_maand = totalen(regels_, "period")
    per_lijn = totalen(regels_, "revenue_line")
    som = ("<table class='mtab' aria-label='totals per month'><tr><th>Month</th><th class='num'>Total</th></tr>"
           + "".join(f"<tr><td>{_e(k)}</td><td class='num'>{_eur(v)}</td></tr>" for k, v in sorted(per_maand.items()))
           + "</table><table class='mtab' aria-label='totals per line'><tr><th>Line</th><th class='num'>Total</th></tr>"
           + "".join(f"<tr><td>{_e(labels.get(k, k))}</td><td class='num'>{_eur(v)}</td></tr>" for k, v in per_lijn.items())
           + "</table>") if regels_ else ""
    nieuw = (_nieuw_kaart("+ Add a revenue line",
                          _omzetformulier(cfg, csrf, "finance_omzet_add", "/finance/revenue",
                                          waarden=waarden, fout=fout),
                          open_=not regels_ and not any(f.values()) or bool(fout))
             if mag_wijzigen(st, username) and csrf else "")
    inhoud = (f"<p class='muted'>Enter revenue on the period of delivery, as the accountant recognises it. "
              f"Any month can be entered, also in the past. A grant should carry its decision as a document.</p>"
              f"{filters}<p><a href='/finance/revenue.csv{'?' + q if q else ''}'>Export CSV for the accountant</a></p>"
              f"{nieuw}<div class='c2-sec{_SCROLL if regels_ else ""}'>{tabel}</div><div class='c2-sec'>{som}</div>")
    return _frame("Finance · Revenue", "/finance/revenue", inhoud, msg)


def render_revenue_regel(st, username, csrf: str, rid: str, msg: str = "", *, waarden: dict | None = None,
                         fout: str = "") -> str | None:
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
    if mag_wijzigen(st, username) and csrf:
        if reg.niet_te_corrigeren(rid):
            correct = f"<p class='muted'>{_e(reg.niet_te_corrigeren(rid).capitalize())}.</p>"
        else:
            correct = (_nieuw_kaart("Correct", "<p class='muted'>This adds a reversal of this line and a new line "
                                    "with the values below. Nothing is overwritten.</p>"
                                    + _omzetformulier(cfg, csrf, "finance_omzet_correct",
                                                      f"/finance/revenue/view?id={rid}", r,
                                                      extra=f"<input type='hidden' name='kid' value='{_e(rid)}'>",
                                                      pre="foc", waarden=waarden, fout=fout),
                                    open_=bool(fout))
                       + _annuleer_kaart(csrf, "finance_omzet_cancel", rid, f"/finance/revenue/view?id={rid}"))
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
    if correctie_van and reg.niet_te_corrigeren(correctie_van):
        return f"✗ {reg.niet_te_corrigeren(correctie_van)}"
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


# ── /finance/help (UX-PR, 11 oktober 2026) ─────────────────────────────────

def render_help(st, username) -> str:
    """De hulppagina. Alle tekst komt uit `finance_uitleg`, dezelfde bron als de hulpteksten bij de
    velden; de tabellen "What goes where" worden uit de veld-tabellen opgebouwd. Rechten: de route
    zit onder /finance/ (404 voor wie Finance niet mag zien)."""
    inhoud = ["<div class='c2-sec'><h2 id='what'>What goes where</h2>"]
    for anker, kop, tabel, _blokken in fu.HELP_FORMULIEREN:
        rijen = "".join(f"<tr><td>{_e(label)}{' *' if verplicht else ''}</td><td>{_e(hulp)}</td>"
                        f"<td>{_e(voorbeeld)}</td></tr>"
                        for label, verplicht, hulp, voorbeeld in tabel.values())
        inhoud.append(f"<h3 id='{_e(anker)}'>{_e(kop)}</h3><table class='mtab' aria-label='{_e(kop)}'>"
                      f"<tr><th>Field</th><th>What you fill in</th><th>Example</th></tr>{rijen}</table>")
    inhoud.append("<p class='muted'>* required</p></div>")
    for anker, kop, alineas in fu.HELP:
        inhoud.append(f"<div class='c2-sec'><h2 id='{_e(anker)}'>{_e(kop)}</h2>"
                      + "".join(f"<p>{_e(a)}</p>" for a in alineas) + "</div>")
    return _frame("Finance · Help", "/finance/help", "".join(inhoud))


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
    raster = _scrolt(f"<table class='mtab' aria-label='history {jaar}'><tr><th>{jaar}</th>{kop}</tr>"
                     f"{''.join(rijen)}</table>")
    if schrijven:
        raster = (f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
                  f"<input type='hidden' name='action' value='finance_hist_opslaan'>"
                  f"<input type='hidden' name='next' value='/finance/history?jaar={jaar}'>"
                  f"<input type='hidden' name='jaar' value='{jaar}'>{raster}"
                  f"<div class='qadd-form'>{_field('Note for this save', 'note', fid='fh-note', placeholder='Example: Venema 2025 annual figures')}"
                  f"<div class='muted'>One note for all cells you changed; it shows in each cell's history.</div></div>"
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
    controle = (f"<h2>Check: layers from the history above</h2>"
                + _scrolt(f"<table class='mtab' aria-label='layers {jaar}'><tr><th></th>{kop}</tr>{lagen}</table>"))
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
            f"{_veld(fu.HISTORIE, 'history_until', 'fh', waarde=h_tot, kind='month')}"
            f"<button class='btn ok sm' type='submit'>Save</button></form>"
            f"<p class='muted'>Every change is logged (who, when, old and new value).</p>"))
        beheer += _popover("Import", (
            f"<form method='post' action='/action' enctype='multipart/form-data'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='action' value='finance_hist_import'>"
            f"<input type='hidden' name='next' value='/finance/history?jaar={jaar}'>"
            f"{_veld(fu.HISTORIE, 'file', 'fhi', kind='file', attrs='accept=.csv,.xlsx')}"
            f"<button class='btn sm' type='submit'>Preview</button></form>"
            f"<p class='muted'>Same format as the export. An empty cell in the file only clears a filled cell if you tick that in the preview. You see a preview first; nothing is saved until you confirm.</p>"))
    log = fh.Instellingen(st.dd).alle()[-5:]
    loghtml = ("<ul>" + "".join(
        f"<li class='muted'>{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created_at']))} · "
        f"{_e(r.get('created_by') or '—')}: {_e(r.get('old') or 'none')} → {_e(r.get('new') or 'none')}</li>"
        for r in reversed(log)) + "</ul>") if log else ""
    inhoud = (f"<p class='muted'>{_e(fu.HISTORIE_KOP)}</p>{_hulp_link('history')}"
              f"<p><span class='chip'>{_e(fh.LABEL)}</span></p>{cutover}{loghtml}{nav}{beheer}"
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
    if correctie_van and reg.niet_te_corrigeren(correctie_van):
        return f"✗ {reg.niet_te_corrigeren(correctie_van)}"
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
