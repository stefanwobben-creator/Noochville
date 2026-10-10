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
_FILTERS = (("", (dek.CONFLICT, dek.ONGECHECKT, dek.LEEG), "All"),
            ("conflict", (dek.CONFLICT,), "Conflict"),
            ("unchecked", (dek.ONGECHECKT,), "Unchecked"),
            ("open", (dek.LEEG,), "Open"))


def _eigenaar(st, pagina) -> str:
    """De rol die de pagina bezit; zonder pagina de houder van `Materials`, die hem moet maken."""
    rid = getattr(pagina, "anchor", "") if pagina is not None else ""
    rec = st.records.get(rid) if rid else org.role_for_domain(st.records.all(), bom_leveranciers.DOMEIN)
    return getattr(getattr(rec, "definition", None), "name", "") or getattr(rec, "id", "") or "—"


def render_open_vragen(st, status: str = "") -> str:
    from nooch_village.views.wiki import _bijlage_bestaat
    d, ctx = dek.uit_stores(st.att, st.bom_leveranciers, st.bom_materialen,
                            ledger=getattr(st, "evidence", None), bestaat=_bijlage_bestaat(st))
    alle = dek.open_vragen(d)
    status = status if status in {k for k, _s, _l in _FILTERS} else ""
    toegestaan = next(s for k, s, _l in _FILTERS if k == status)
    rijen = [r for r in alle if r["status"] in toegestaan]
    telling = {s: sum(1 for r in alle if r["status"] == s) for s in (dek.CONFLICT, dek.ONGECHECKT, dek.LEEG)}
    filter_ = " ".join(
        f"<a class='cl-filter{' on' if k == status else ''}' "
        f"href='/open-questions{'?status=' + k if k else ''}'>{_e(l)}"
        f"{'' if not k else ' (' + str(telling[s[0]]) + ')'}</a>" for k, s, l in _FILTERS)
    tr = []
    for r in rijen:
        vorm, woord = _DEK_VORM[r["status"]]
        naam = (f"<a href='{_e(_sprong(r['pagina'], r['kop']))}'>{_e(r['naam'])}</a>"
                if r["pagina"] is not None else f"{_e(r['naam'])} <span class='muted'>(no page yet)</span>")
        soort = "Material" if r["soort"] == "materiaal" else "Supplier"
        reden = f" — {_e(r['reden'])}" if r["status"] == dek.CONFLICT and r["reden"] else ""
        tr.append(f"<tr><td>{naam}<div class='muted'>{soort}</div></td><td>{_e(r['vraag'])}</td>"
                  f"<td><span class='nu-status nu-status--{vorm}'>{woord}</span>{reden}</td>"
                  f"<td>{_e(_eigenaar(st, r['pagina']))}</td></tr>")
    tabel = ("<table class='mtab' aria-label='open questions'><tr><th>Page</th><th>Question</th>"
             f"<th>Status</th><th>Owner</th></tr>{''.join(tr)}</table>" if tr
             else "<p class='muted'>Nothing here.</p>")
    main = (f"<div class='c2-main'><h1 class='ptitle'>Open questions</h1>"
            f"<p class='muted'>Every question on the material and supplier pages of the bill of "
            f"materials that has no checked answer yet: {telling[dek.CONFLICT]} in conflict, "
            f"{telling[dek.ONGECHECKT]} unchecked, {telling[dek.LEEG]} open. Computed from the wiki; "
            f"a page opens at the heading where the answer belongs. Open means not answered yet — "
            f"not “no”.</p>"
            f"<div class='cl-bar' aria-label='status'><span class='muted'>Status</span> {filter_}</div>"
            f"<div class='c2-sec'>{tabel}</div></div>")
    return _page("Open questions", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
