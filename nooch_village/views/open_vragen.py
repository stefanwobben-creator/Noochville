"""Open questions — elke vraag die nog geen gecheckt antwoord heeft, voor het hele dorp (10 oktober 2026).

Dezelfde data als de sectie Coverage op /bom (`wiki_dekking`), maar als één lijst over alle modellen:
per rij de pagina, de vraag, de status, de eigenaar en een link naar de plek op de pagina waar het
antwoord hoort. BEREKEND, NIET OPGESLAGEN: wie een feit toevoegt of nakijkt, ziet de rij de volgende
pageload verdwijnen.

LAGEN (atom → molecule → pattern), allemaal bestaand:
  atom      `.nu-status` (vorm + woord, uit `views.bom._DEK_VORM`) · `.muted` · een wiki-link
  molecule  `table.mtab` · `.cl-bar` + `a.cl-filter` (statusfilter, zelfde vorm als op /bom)
  pattern   dit scherm
Geen nieuwe CSS-klasse en geen inline style.
"""
from __future__ import annotations

from nooch_village import bom_leveranciers, org, wiki_dekking as dek
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.views.bom import _DEK_VORM, _sprong
from nooch_village.web_base import _e, _page

#: Het statusfilter: sleutel in de URL → (statussen, label).
_FILTERS = (("", (dek.CONFLICT, dek.ONGECHECKT, dek.LEEG, dek.UITGESTELD), "All"),
            ("conflict", (dek.CONFLICT,), "Conflict"),
            ("unchecked", (dek.ONGECHECKT,), "Unchecked"),
            ("open", (dek.LEEG,), "Open"),
            ("deferred", (dek.UITGESTELD,), "Deferred"))

#: Hoe ver vooruit de voorgestelde "research by"-datum staat. Een voorstel, de mens kiest.
_UITSTEL_DAGEN = 30


def uitstel_form(csrf: str, pagina, soort: str, k: str, terug: str) -> str:
    """"Defer": één klik plus een datum. De eigenaar is de rol die de pagina bezit; de server
    toetst wie het mag (domeineigenaar of Circle Lead). Gedeeld door /open-questions en de wikipagina."""
    import time as _t
    from nooch_village.views.bom import _form, _popover
    voorstel = _t.strftime("%Y-%m-%d", _t.localtime(_t.time() + _UITSTEL_DAGEN * 86400))
    invoer = (f"<input type='date' name='tot' value='{voorstel}' aria-label='research by' required>")
    return _popover("Defer", _form(csrf, "vraag_uitstel", terug,
                                   {"aid": pagina.id, "soort": soort, "k": k,
                                    "eigenaar": getattr(pagina, "anchor", "")}, invoer),
                    "defer this question")


def terug_form(csrf: str, pagina, k: str, terug: str) -> str:
    """Het uitstel weghalen: de vraag staat weer open."""
    return (f"<form method='post' action='/action'><input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='action' value='vraag_uitstel_weg'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>"
            f"<input type='hidden' name='aid' value='{_e(pagina.id)}'><input type='hidden' name='k' "
            f"value='{_e(k)}'><button class='dellink' type='submit'>undo</button></form>")


def _eigenaar(st, pagina) -> str:
    """De rol die de pagina bezit; zonder pagina de houder van `Materials`, die hem moet maken."""
    rid = getattr(pagina, "anchor", "") if pagina is not None else ""
    rec = st.records.get(rid) if rid else org.role_for_domain(st.records.all(), bom_leveranciers.DOMEIN)
    return getattr(getattr(rec, "definition", None), "name", "") or getattr(rec, "id", "") or "—"


def _mag_bewerken(st, username, pagina) -> bool:
    """Dezelfde poort als de actie (`_artefact_gate`), zodat het scherm geen knop toont die de
    server daarna weigert."""
    if pagina is None or not username:
        return False
    from nooch_village.cockpit2 import _artefact_gate
    return _artefact_gate(pagina.anchor, username, st, domein=getattr(pagina, "domain", "")) is None


def render_open_vragen(st, status: str = "", csrf_token: str = "", username: str | None = None) -> str:
    from nooch_village.views.wiki import _bijlage_bestaat
    d, ctx = dek.uit_stores(st.att, st.bom_leveranciers, st.bom_materialen,
                            ledger=getattr(st, "evidence", None), bestaat=_bijlage_bestaat(st))
    alle = dek.open_vragen(d)
    status = status if status in {k for k, _s, _l in _FILTERS} else ""
    toegestaan = next(s for k, s, _l in _FILTERS if k == status)
    rijen = [r for r in alle if r["status"] in toegestaan]
    telling = {s: sum(1 for r in alle if r["status"] == s)
               for s in (dek.CONFLICT, dek.ONGECHECKT, dek.LEEG, dek.UITGESTELD)}
    filter_ = " ".join(
        f"<a class='cl-filter{' on' if k == status else ''}' "
        f"href='/open-questions{'?status=' + k if k else ''}'>{_e(l)}"
        f"{'' if not k else ' (' + str(telling[s[0]]) + ')'}</a>" for k, s, l in _FILTERS)
    terug = f"/open-questions{'?status=' + status if status else ''}"
    tr = []
    for r in rijen:
        vorm, woord = _DEK_VORM[r["status"]]
        bewerk = bool(csrf_token) and _mag_bewerken(st, username, r["pagina"])
        soort = r["soort"]
        if r["status"] == dek.UITGESTELD:
            datum = _e(r["tot"]) + (terug_form(csrf_token, r["pagina"], r["k"], terug) if bewerk else "")
            actie = ""
        else:
            datum = (f"<span class='muted'>{_e(r['tot'])} — expired</span>" if r.get("verlopen") else "")
            actie = (uitstel_form(csrf_token, r["pagina"], soort, r["k"], terug)
                     if bewerk and r["status"] == dek.LEEG else "")
        antwoord = (f"<a href='{_e(_sprong(r['pagina'], r['kop']))}'>answer</a> " if r["pagina"] is not None
                    and r["status"] in (dek.LEEG, dek.UITGESTELD) else "")
        naam = (f"<a href='{_e(_sprong(r['pagina'], r['kop']))}'>{_e(r['naam'])}</a>"
                if r["pagina"] is not None else f"{_e(r['naam'])} <span class='muted'>(no page yet)</span>")
        label = "Material" if soort == "materiaal" else "Supplier"
        reden = f" — {_e(r['reden'])}" if r["status"] == dek.CONFLICT and r["reden"] else ""
        tr.append(f"<tr><td>{naam}<div class='muted'>{label}</div></td><td>{_e(r['vraag'])}</td>"
                  f"<td><span class='nu-status nu-status--{vorm}'>{woord}</span>{reden}</td>"
                  f"<td>{datum}</td><td>{_e(_eigenaar(st, r['pagina']))}</td><td>{antwoord}{actie}</td></tr>")
    tabel = ("<table class='mtab' aria-label='open questions'><tr><th>Page</th><th>Question</th>"
             f"<th>Status</th><th>Research by</th><th>Owner</th><th></th></tr>{''.join(tr)}</table>" if tr
             else "<p class='muted'>Nothing here.</p>")
    main = (f"<div class='c2-main'><h1 class='ptitle'>Open questions</h1>"
            f"<p class='muted'>Every question on the material and supplier pages of the bill of "
            f"materials that has no checked answer yet: {telling[dek.CONFLICT]} in conflict, "
            f"{telling[dek.ONGECHECKT]} unchecked, {telling[dek.LEEG]} open, "
            f"{telling[dek.UITGESTELD]} deferred. Computed from the wiki; a page opens at the heading "
            f"where the answer belongs. Open means not answered yet — not “no”. Deferred means "
            f"someone will research it by the date shown; it never counts as checked, and once the "
            f"date has passed the question is open again.</p>"
            f"<div class='cl-bar' aria-label='status'><span class='muted'>Status</span> {filter_}</div>"
            f"<div class='c2-sec'>{tabel}</div></div>")
    return _page("Open questions", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
