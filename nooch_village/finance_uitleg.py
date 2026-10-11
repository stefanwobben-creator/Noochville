"""De uitleg bij de Finance-formulieren — één plek voor de hulpteksten (UX-PR, 11 oktober 2026).

Aanleiding (Stefan, na de eerste keer invullen op prod): de velden hadden alleen een placeholder,
die verdwijnt zodra je typt; nergens stond wat welke datum is of hoe btw werkt. Nu krijgt elk veld
een zichtbaar label en een korte hulptekst, en `/finance/help` legt het geheel uit.

DE TEKST STAAT ALLEEN HIER. De hulptekst onder een veld en de tabel "What goes where" op de
hulppagina lezen dezelfde regel, zodat ze niet uit elkaar lopen. Verandert een veld van betekenis,
dan pas je het hier aan en nergens anders.

GEEN FISCALE REGELS VERZINNEN. Waar de boekhouding iets moet beslissen (niet-aftrekbare btw) zegt
de tekst "Ask Venema", tot Stefan het antwoord heeft.

Alleen tekst: dit module leest geen finance-data en hoort niet bij de guard-lijst.
"""
from __future__ import annotations

#: Eén veld: (veldnaam zoals hij gepost wordt, label, verplicht, hulptekst, voorbeeld).
#: De veldnamen zijn die van de bestaande formulieren — deze PR verandert ze niet.

KOSTEN = {
    "supplier": ("Supplier", True, "Who sent the invoice.", "Portuguese factory"),
    "description": ("Description", True, "What it was for, in a few words.", "Batch 3, second payment"),
    "entry_date": ("Invoice date", True, "The date printed on the invoice.", "2026-11-03"),
    "period": ("Period of use", False,
               "The month this cost belongs to. Empty means the month of the invoice date. "
               "An invoice dated 3 November for October: choose October.", "2026-10"),
    "file": ("Invoice document", False, "Upload the invoice: PDF, PNG or JPG, at most 10 MB.", ""),
    "no_document_reason": ("Why not?", False,
                           "Required when there is no document. The line then shows 'missing document' "
                           "until a document is added by a correction.", "Lost; asked the supplier for a copy"),
    "amount_excl": ("Amount excl. VAT", True,
                    "The net amount without VAT, in euros. An invoice of 121,00 with 21% VAT: enter 100,00.",
                    "100,00"),
    "vat": ("VAT", False,
            "The VAT amount on the invoice. It is only stored so the accountant can check it later; it is "
            "never added to the totals. No VAT on the invoice (for example a supplier abroad with reverse "
            "charge)? Leave it empty.", "21,00"),
    "account_code": ("Account (accountant)", False,
                     "The accountant's main group. Pick one and we propose the management line. The numbered "
                     "scheme follows when Venema delivers it.", "Kantoorkosten"),
    "management_line": ("Management line", False,
                        "Where this cost lands in the P&L. Required unless you picked an account: then empty "
                        "means we take the line proposed for that account.", "Other costs like housing and IT"),
    "batch": ("Batch", False, "Only fill in if this cost belongs to one batch. It is used in the P&L per batch.",
              "Batch 4"),
    "payment_status": ("Payment status", True, "Open until the money has left the account.", "Open"),
    "paid_date": ("Paid date", False, "The date the money left the account. Only for a paid invoice.",
                  "2026-11-10"),
    "recurring_id": ("Belongs to recurring cost", False,
                     "Pick the recurring cost this invoice is the actual bill of. Then it no longer shows as "
                     "'expected, not invoiced'.", "Office rent"),
    "note": ("Note", False, "Anything the accountant or you should know later.", ""),
}

OMZET = {
    "entry_date": ("Booking date", True, "The date of the booking or the document.", "2026-11-03"),
    "period": ("Period", True,
               "The month the revenue belongs to. Enter revenue in the month of delivery, as the accountant "
               "recognises it. Any month in the past is allowed.", "2026-10"),
    "revenue_line": ("Revenue line", True,
                     "Net sales: sales of shoes, the base for all percentages. Grants and subsidies: a subsidy "
                     "or grant; it counts from EBITDA, not in net sales or the margins before it.", "Net sales"),
    "description": ("Description", True, "What the revenue is, in a few words.", "Batch 4 deliveries, October"),
    "amount_excl": KOSTEN["amount_excl"],
    "vat": KOSTEN["vat"],
    "batch": ("Batch", False, "Only for net sales of one batch. Used in the P&L per batch.", "Batch 4"),
    "pairs": ("Pairs", False,
              "The number of pairs this line is about, only for net sales. Used in the P&L per pair.", "120"),
    "file": ("Document", False, "Optional. For a subsidy: the decision letter, strongly advised.", ""),
    "note": ("Note", False, "Required for a return or credit note (a negative amount).", "Return of 2 pairs"),
}

TERUGKEREND = {
    "omschrijving": ("Description", True, "What the cost is.", "Office rent"),
    "leverancier": ("Supplier", False, "Who you pay.", "Landlord"),
    "bedrag": ("Amount per month excl. VAT", True,
               "The amount for one month, without VAT. An annual or quarterly invoice? Enter the monthly share "
               "here (annual amount divided by 12). The Runway adds up these monthly amounts.", "450,00"),
    "van": ("From", True, "The first day this cost applies.", "2026-01-01"),
    "tot": ("Until", False, "The last day it applies. Leave empty if it continues.", "2026-12-31"),
    "account_code": KOSTEN["account_code"],
    "management_line": ("Management line", False, "Where this cost lands in the P&L.",
                        "Other costs like housing and IT"),
    "notitie": ("Note", False, "Anything worth knowing later.", ""),
}

HISTORIE = {
    "history_until": ("History until (cutover month)", False,
                      "Months up to and including this month come from the history, later months from the "
                      "register. Empty means no history is used.", "2026-09"),
    "file": ("File to import", True, "A CSV or XLSX file in the format of the export.", ""),
}

#: De blokken van het kostenformulier, in volgorde: (kop, velden).
KOSTEN_BLOKKEN = (
    ("The invoice", ("supplier", "description", "entry_date", "period")),
    ("Amount", ("amount_excl", "vat")),
    ("Where does it go in the P&L", ("account_code", "management_line", "batch")),
    ("Payment", ("payment_status", "paid_date", "recurring_id", "note")),
)

OMZET_BLOKKEN = (
    ("The revenue", ("entry_date", "period", "revenue_line", "description")),
    ("Amount", ("amount_excl", "vat")),
    ("Batch and pairs", ("batch", "pairs")),
    ("Document and note", ("file", "note")),
)

TERUGKEREND_BLOKKEN = (
    ("The cost", ("omschrijving", "leverancier", "bedrag")),
    ("When", ("van", "tot")),
    ("Where does it go in the P&L", ("account_code", "management_line", "notitie")),
)

KOSTEN_KOP = "A line cannot be edited afterwards. Made a mistake? Open the line and use Correct."
OMZET_KOP = KOSTEN_KOP
TERUGKEREND_KOP = (
    "Recurring costs are the costs you expect every month. They feed the Runway (fixed costs per month). "
    "When the actual invoice arrives, enter it as a cost line and link it to the recurring cost, so it no "
    "longer shows as expected, not invoiced.")
HISTORIE_KOP = (
    "Fill in the monthly amounts per line. Empty means no data, not zero. Months up to the cutover month "
    "come from here, later months from the register.")

DOC_HEB = "I have the document"
DOC_GEEN = "No document"
BTW_HULP = "Only know the total?"
BTW_TARIEVEN = (21, 9, 0)

LEEG = {
    "costs": "No costs yet. Add the first cost line above.",
    "revenue": "No revenue yet. Add the first revenue line above.",
    "recurring": "No recurring costs yet. Add the first one above.",
}


# ── de samenvatting bij terugkerende kosten ─────────────────────────────────

_MAANDEN = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
            "October", "November", "December")


def _datum_tekst(iso: str) -> str:
    try:
        j, m, d = (int(x) for x in iso.split("-"))
        return f"{d} {_MAANDEN[m - 1]} {j}"
    except (ValueError, IndexError):
        return ""


def _euro_tekst(cents: int) -> str:
    teken = "-" if cents < 0 else ""
    c = abs(int(cents))
    heel = f"{c // 100:,}".replace(",", ".")
    return f"{teken}€{heel},{c % 100:02d}"


def samenvatting(cents: int | None, van: str, tot: str = "") -> str:
    """"€450,00 per month, from 1 January 2026, ongoing." — dezelfde zin als de live samenvatting
    in `nooch.js` (`NV.finSamenvatting`); een toets houdt ze gelijk."""
    if cents is None or not _datum_tekst(van):
        return ""
    eind = f"until {_datum_tekst(tot)}" if _datum_tekst(tot) else "ongoing"
    return f"{_euro_tekst(cents)} per month, from {_datum_tekst(van)}, {eind}."


# ── /finance/help ───────────────────────────────────────────────────────────

#: De secties van de hulppagina: (anker, kop, alinea's). De tabellen van "What goes where" komen uit
#: de veld-tabellen hierboven, niet uit tekst hier.
HELP = (
    ("dates", "Which date is which", (
        "Invoice date: the date printed on the invoice.",
        "Period of use: the month a cost belongs to. The P&L works on this month, not on the payment date. "
        "An invoice dated 3 November for work in October belongs to October.",
        "Paid date: the day the money left the account. It only tells whether a cost is paid; it does not "
        "move the cost to another month.",
        "From and until (recurring costs): the first and last day a monthly cost runs. Empty until means "
        "it continues.",
        "Booking date (revenue): the date of the booking or document. The period is the month of delivery, "
        "as the accountant recognises revenue.",
    )),
    ("vat", "VAT", (
        "Amounts are always excluding VAT.",
        "The VAT field is optional and never counts in any total; it is only stored so the accountant can "
        "check it.",
        "No VAT on the invoice, for example a supplier abroad with reverse charge: leave the VAT field empty.",
        "A credit note from a supplier: open the original cost line and use Correct, with the new net amount. "
        "A credit note cannot yet be entered as a line of its own.",
        "VAT that cannot be deducted is a decision for the books. Ask Venema before entering such a cost.",
    )),
    ("mistakes", "Mistakes", (
        "Lines can only be added, never changed or deleted. That keeps the register trustworthy for the "
        "accountant.",
        "Made a mistake? Open the line and use Correct. That adds two lines: a reversal of the old line "
        "(the same amounts, negative) and a new line with the right values. Together they count as the "
        "new value.",
    )),
    ("documents", "Documents", (
        "Every cost line carries its invoice, so the accountant can check it. The file is stored with a "
        "fingerprint (sha256); if it ever changes, it is refused instead of delivered.",
        "No document? Say why. The line then shows 'missing document' and appears under Open items until "
        "a correction adds the document.",
        "The same file twice gives a warning, because that is usually a mistake. Tick 'I know this file is "
        "already in the register' if it is meant.",
    )),
    ("recurring", "Recurring costs versus cost lines", (
        "A recurring cost is what you expect every month (rent, subscriptions). It feeds the Runway and has "
        "no document.",
        "A cost line is an actual invoice. Link it to the recurring cost with 'Belongs to recurring cost'; "
        "until then that month shows as 'expected, not invoiced'.",
        "An annual invoice: enter the monthly share as the recurring cost. As a cost line, one invoice lands "
        "in one month of the P&L, and the other months of that recurring cost show as expected, not invoiced.",
    )),
    ("revenue", "Revenue and subsidy", (
        "Enter revenue in the month of delivery. Any month in the past is allowed.",
        "Grants and subsidies are kept apart: they count from EBITDA, never in net sales or the margins "
        "before it. Attach the decision letter.",
        "Batch and pairs on net sales make the P&L per batch and per pair work.",
    )),
    ("history", "History", (
        "The history holds monthly amounts per line for months before the register, for example from the "
        "accountant's figures.",
        "The cutover month decides the source: up to and including it the history, after it the register. "
        "A month never comes from both.",
        "An empty cell means no data, not zero.",
        "Export a year as CSV or XLSX, fill it in, and import it again. You see a preview before anything "
        "is saved.",
    )),
    ("lines", "Batch, account and management line", (
        "Batch: only when a cost or revenue belongs to one batch.",
        "Account: the accountant's main group. Pick one and the management line is proposed for you.",
        "Management line: the row of the P&L the amount lands on. Required unless an account proposes one.",
    )),
)

#: De tabellen van sectie 1, "What goes where": (anker, kop, veld-tabel, blokken).
HELP_FORMULIEREN = (
    ("costs", "Cost line", KOSTEN, KOSTEN_BLOKKEN),
    ("recurring-form", "Recurring cost", TERUGKEREND, TERUGKEREND_BLOKKEN),
    ("revenue-form", "Revenue line", OMZET, OMZET_BLOKKEN),
)
