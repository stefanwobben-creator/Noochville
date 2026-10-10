"""Het P&L in marge-lagen — bron-agnostisch (Finance PR 1, 10 oktober 2026).

De rijen volgen het voorbeeld-P&L (`config/finance.json` → `management_lines`): per groep de
managementregels, een groepssom, en daarna de laag (CM1, CM2, CM3, EBITDA, EBIT, EBT, Net earnings).

BRON-AGNOSTISCH. De berekening krijgt een lijst POSTEN: (maand YYYY-MM, managementregel, centen,
bron). In PR 1 is de bron altijd "register"; PR 2 voegt "history (manual or imported)" toe, met een
cutover-maand zodat een maand nooit uit twee bronnen komt. Deze functie hoeft daarvoor niet te
veranderen: een post is een post. OMZET is een optionele invoer van DEZELFDE berekening ({maand:
centen}); zonder omzet tonen de lagen "costs only" en zijn er geen percentages.

WEERGAVE ZOALS HET VOORBEELD: kosten negatief (opgeslagen als positief), een krediet op "marketing
contribution from suppliers" dus positief. Correcties zijn gewone posten: een tegenboeking heft de
oude regel vanzelf op.

Puur: geen I/O, geen stores.
"""
from __future__ import annotations


def bereken(posten: list[tuple], cfg: dict, *, omzet: dict[str, int] | None = None,
            maanden: list[str] | None = None, opbrengsten: list[tuple] | None = None,
            paren: dict[str, int] | None = None, historie_tot: str = "") -> dict:
    """{maanden, rijen, kosten_alleen, onbekend, bron, paren}.

    `opbrengsten` (PR 1b): posten (maand, opbrengstregel, centen, bron) uit het opbrengstregister.
    Net sales volgt de bronregel `net_sales_source_from` (`finance_omzet.net_sales_per_maand`); een
    andere opbrengstregel (subsidie) wordt een eigen rij vlak vóór de groep waarvan de laag in zijn
    `from_layer` staat — met `ebitda` dus direct onder CM3 — en telt vanaf die laag mee in het
    resultaat. NOOIT in de percentagebasis: die is alleen Net sales.

    Elke rij: {soort: omzet|regel|groep|laag, key, label, waarden: {maand: centen|None}, totaal,
    pct: {maand: float|None} | None}. Bedragen in weergave-teken: kosten negatief."""
    bron_per_maand: dict[str, str] = {}
    extra: dict[str, dict[str, int]] = {}                   # opbrengstregel → {maand: centen}
    if opbrengsten is not None:
        from nooch_village.finance_omzet import NET_SALES, net_sales_per_maand
        ns, bron_per_maand = net_sales_per_maand(opbrengsten, cfg.get("net_sales_source_from") or "",
                                                 historie_tot=historie_tot)
        omzet = ns or omzet
        for maand, lijn, cents, _b in opbrengsten:
            if lijn != NET_SALES:
                extra.setdefault(lijn, {})
                extra[lijn][maand] = extra[lijn].get(maand, 0) + int(cents)
    if omzet is not None and not any(omzet.values()):
        omzet = None                                        # geen omzet in deze periode: costs only
    maanden = sorted(set(maanden or []) | {p[0] for p in posten} | set(omzet or {})
                     | {m for w in extra.values() for m in w})
    regel_keys = {r["key"] for g in cfg["management_lines"] for r in g["regels"]}
    per: dict[tuple[str, str], int] = {}
    onbekend: dict[str, int] = {}
    for maand, regel, cents, _bron in posten:
        if regel not in regel_keys:
            onbekend[regel] = onbekend.get(regel, 0) + int(cents)
            continue
        per[(regel, maand)] = per.get((regel, maand), 0) + int(cents)
    met_omzet = omzet is not None

    def rij(soort, key, label, waarden, kosten_alleen=False):
        tot = sum(v for v in waarden.values() if v is not None) if any(
            v is not None for v in waarden.values()) else None
        pct = None
        if met_omzet:
            pct = {m: (waarden[m] / omzet[m] if waarden.get(m) is not None and omzet.get(m) else None)
                   for m in maanden}
            omzet_tot = sum(omzet.get(m) or 0 for m in maanden)
            pct["totaal"] = tot / omzet_tot if tot is not None and omzet_tot else None
        return {"soort": soort, "key": key, "label": label, "waarden": waarden, "totaal": tot,
                "pct": pct, "kosten_alleen": kosten_alleen}

    rijen = [rij("omzet", "net_sales", "Net sales",
                 {m: (omzet.get(m) if met_omzet else None) for m in maanden})]
    cumulatief = {m: 0 for m in maanden}                     # weergave-teken: kosten negatief
    lagen = {g["laag"]["key"] for g in cfg["management_lines"]}
    rev_cfg = {r["key"]: r for r in cfg.get("revenue_lines") or []}
    for lijn in extra:
        if str((rev_cfg.get(lijn) or {}).get("from_layer") or "").lower() not in lagen:
            onbekend[lijn] = onbekend.get(lijn, 0) + sum(extra[lijn].values())
    for g in cfg["management_lines"]:
        for lijn, w in extra.items():
            if str((rev_cfg.get(lijn) or {}).get("from_layer") or "").lower() != g["laag"]["key"]:
                continue
            # OPBRENGST BUITEN DE VERKOOP (subsidie): een eigen rij, positief, die vanaf deze laag
            # meetelt in het resultaat — niet in Net sales en niet in de percentagebasis.
            waarden = {m: w.get(m, 0) for m in maanden}
            for m in maanden:
                cumulatief[m] += waarden[m]
            rijen.append(rij("opbrengst", lijn, (rev_cfg.get(lijn) or {}).get("label", lijn), waarden))
        groep = {m: 0 for m in maanden}
        for r in g["regels"]:
            w = {m: -per.get((r["key"], m), 0) for m in maanden}
            for m in maanden:
                groep[m] += w[m]
            rijen.append(rij("regel", r["key"], r["label"], w))
        for m in maanden:
            cumulatief[m] += groep[m]
        if g.get("label"):
            rijen.append(rij("groep", g["groep"], g["label"], dict(groep)))
        laag = g["laag"]
        if met_omzet:
            rijen.append(rij("laag", laag["key"], laag["label"],
                             {m: (omzet.get(m) or 0) + cumulatief[m] for m in maanden}))
        else:
            rijen.append(rij("laag", laag["key"], f"{laag['label']} — costs only",
                             dict(cumulatief), kosten_alleen=True))
    return {"maanden": maanden, "rijen": rijen, "kosten_alleen": not met_omzet, "onbekend": onbekend,
            "bron": bron_per_maand, "paren": dict(paren or {})}
