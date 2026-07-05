"""Catalogus-koppelscherm (scope 4) — de aanvoerkant van de metrics-catalogus.

De curator (anchor-lead) ziet per gekoppelde bron de ruwe velden die de skill oplevert
(available_metrics) en koppelt ze — naam, categorie, aard, eenheid, uitleg — aan een
catalogus-item (definitions.py, scope-3-schema). Pas na publiceren verschijnt een veld als
indicator in de KPI-wizard; een ongepubliceerd ruw veld bestaat daar niet.

Autorisatie op de route + de publish-actie (anchor-lead); deze view is puur presentatie.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from nooch_village.web_base import _e
from nooch_village.metric_schema import AARD, AARD_LABEL
from nooch_village.i18n import t
from nooch_village.views.metrics import indicator_freshness, freshness_chip

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

# Groeperings-categorieën die de curator per veld kan kiezen (vrij uitbreidbaar).
_CATEGORIEEN = ("Website", "Verkoop", "Zoekprestaties", "Content", "Werkoverleg", "Impact", "Financieel")


def catalog_sources() -> list[tuple[str, str, list[str]]]:
    """(catalogus-bronnaam, label, ruwe velden) per gekoppelde databron. De velden komen uit de
    skill zelf (available_metrics, geen API-call); de bronnaam is de `source` zoals in de catalogus
    (definitions.py) — die wijkt bewust af van de langere skill-naam (plausible vs plausible_stats)."""
    from nooch_village.skills_impl.plausible import PlausibleSkill
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    from nooch_village.skills_impl.openalex import OpenalexSkill
    return [
        ("plausible", "Plausible (web-analytics)", PlausibleSkill().available_metrics()),
        ("shopify", "Shopify (verkoop)", ShopifySalesSkill().available_metrics()),
        ("gsc", "Google Search Console", GscPerformanceSkill().available_metrics()),
        ("openalex", "OpenAlex (academische tellers)", OpenalexSkill().available_metrics()),
    ]


def _coupled_fields(st: _Stores, source: str) -> dict:
    """Ruw veld → catalogus-itemnaam voor deze bron (uit gepubliceerde definities die een `veld` dragen)."""
    out = {}
    for d in st.defs.all():
        cur = st.defs.current(d["id"]) or {}
        if cur.get("source") == source and cur.get("veld"):
            out[cur["veld"]] = cur.get("name", cur["veld"])
    return out


def _field_card(source: str, raw: str, coupled_name: str | None, csrf: str, fresh=None) -> str:
    chip = f"<span class='chip'>{_e(raw)}</span>"
    vers = freshness_chip(fresh)          # tweede signaal naast 'gekoppeld': levert de bron recente data?
    if coupled_name:
        return (f"<div class='card'><div class='ptitle'>{chip} "
                f"<span class='chip outline'>{_e(t('catalogus.koppelen.status.gekoppeld'))}</span> {vers}</div>"
                f"<div class='muted'>{_e(t('catalogus.koppelen.gekoppeld_als'))} <b>{_e(coupled_name)}</b>.</div></div>")
    kies = _e(t("catalogus.koppelen.kies"))
    cat_opts = "".join(f"<option>{_e(c)}</option>" for c in _CATEGORIEEN)
    aard_opts = "".join(f"<option value='{a}'>{_e(AARD_LABEL[a])}</option>" for a in AARD)
    return (
        f"<div class='card'><div class='ptitle'>{chip} "
        f"<span class='chip muted'>{_e(t('catalogus.koppelen.status.ongekoppeld'))}</span> {vers}</div>"
        f"<form method='post' action='/action' class='m-addform'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
        f"<input type='hidden' name='source' value='{_e(source)}'>"
        f"<input type='hidden' name='veld' value='{_e(raw)}'>"
        f"<input type='hidden' name='next' value='/catalog?koppel={_e(source)}'>"
        f"<label class='att-lbl'>{_e(t('catalogus.koppelen.veld.naam'))}</label>"
        f"<input name='naam' placeholder='{_e(t('catalogus.koppelen.veld.naam.ph'))}' autocomplete='off'>"
        f"<label class='att-lbl'>{_e(t('catalogus.koppelen.veld.categorie'))}</label>"
        f"<select name='categorie'><option value=''>{kies}</option>{cat_opts}</select>"
        f"<label class='att-lbl'>{_e(t('catalogus.koppelen.veld.aard'))}</label>"
        f"<select name='aard'><option value=''>{kies}</option>{aard_opts}</select>"
        f"<label class='att-lbl'>{_e(t('catalogus.koppelen.veld.eenheid'))}</label>"
        f"<input name='unit' placeholder='{_e(t('catalogus.koppelen.veld.eenheid.ph'))}' autocomplete='off'>"
        f"<label class='att-lbl'>{_e(t('catalogus.koppelen.veld.uitleg'))}</label>"
        f"<input name='definition' placeholder='{_e(t('catalogus.koppelen.veld.uitleg.ph'))}' autocomplete='off'>"
        f"<button class='btn ok' type='submit' name='action' value='catalog_publish'>"
        f"{_e(t('catalogus.koppelen.publiceer'))}</button>"
        f"</form></div>")


def _koppel_section(st: _Stores, csrf_token: str = "", source: str = "") -> str:
    """De koppel-flow als in-scherm-sectie op /catalog (curator-only): bron-picker + ruwe-veld-kaarten
    om een veld tot indicator te promoveren. Geen los scherm meer; ingebed via /catalog?koppel=<source>,
    en publiceren blijft op het samengevoegde scherm (next=/catalog?koppel=<source>)."""
    sources = catalog_sources()
    valid = [s for s, _l, _f in sources]
    sel = source if source in valid else (valid[0] if valid else "")

    def pick(s, lbl):                       # bron-picker: scope-1-pills (.chip-opt) in een .chip-wrap
        on = " on" if s == sel else ""
        return f"<a class='chip-opt{on}' href='/catalog?koppel={_e(s)}'>{_e(lbl)}</a>"
    bar = (f"<div class='cl-bar'><span class='muted'>{_e(t('catalogus.koppelen.bron'))}</span> "
           f"<span class='chip-wrap'>" + "".join(pick(s, lbl) for s, lbl, _f in sources) + "</span></div>")
    intro = f"<p class='muted'>{_e(t('catalogus.koppelen.intro'))}</p>"

    raw_fields = next((flds for s, _l, flds in sources if s == sel), [])
    coupled = _coupled_fields(st, sel)
    if not raw_fields:
        fields_html = f"<p class='muted'>{_e(t('catalogus.koppelen.geen_velden'))}</p>"
    else:
        fresh = {raw: indicator_freshness(st, sel, raw) for raw in raw_fields}
        # Alles gekoppeld → expliciete boodschap i.p.v. een rij actieloze kaarten; de kaarten blijven
        # (nu mét data-vers-signaal) zodat je per veld ziet of de bron ook echt vult.
        all_coupled = all(raw in coupled for raw in raw_fields)
        banner = (f"<div class='card'><div class='muted'>{_e(t('catalogus.koppelen.all_coupled'))}</div></div>"
                  if all_coupled else "")
        cards = "".join(_field_card(sel, raw, coupled.get(raw), csrf_token, fresh[raw]) for raw in raw_fields)
        fields_html = banner + cards

    titel = _e(t("catalogus.koppelen.titel"))
    return (f"<div class='c2-sec'><div class='cl-head'><h3>{titel}</h3>"
            f"<a class='btn sm' href='/catalog'>← sluiten</a></div>{intro}{bar}</div>"
            f"<div class='c2-sec'>{fields_html}</div>")
