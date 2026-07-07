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
from nooch_village.views.metrics import (indicator_freshness, freshness_chip,
                                         _data_source_classes, _default_form)
from nooch_village.cockpit2_util import _name

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

# Groeperings-categorieën die de curator per veld kan kiezen (vrij uitbreidbaar).
_CATEGORIEEN = ("Website", "Verkoop", "Zoekprestaties", "Content", "Werkoverleg", "Impact", "Financieel")

# Formulier-hulp: concrete invul-voorbeelden per bron (stand vs reeks, eenheid, uitleg) zodat de curator
# weet wat een veld betekent. Toont als muted regel op de ongekoppelde kaart.
_FIELD_HELP = {
    "openalex": "Voorbeeld — naam 'OpenAlex werken', eenheid 'n', aard 'stand' (cumulatieve teller), "
                "uitleg 'Totaal aantal werken in OpenAlex voor deze term.'",
    "semanticscholar": "Voorbeeld — naam 'Semantic Scholar citaties', eenheid 'n', aard 'stand', "
                       "uitleg 'Citatie-telling van het meest geciteerde paper.'",
    "serpstat": "Voorbeeld — naam 'Serpstat zichtbaarheid', eenheid 'index', aard 'reeks' (over tijd), "
                "uitleg 'Domein-zichtbaarheidsindex.'",
}


def catalog_sources() -> list[tuple[str, str, list[str]]]:
    """(catalogus-bronnaam, label, ruwe velden) per gekoppelde databron. De velden komen uit de
    skill zelf (available_metrics, geen API-call); de bronnaam is de `source` zoals in de catalogus
    (definitions.py) — die wijkt bewust af van de langere skill-naam (plausible vs plausible_stats)."""
    from nooch_village.skills_impl.plausible import PlausibleSkill
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    from nooch_village.skills_impl.openalex import OpenalexSkill
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
    from nooch_village.skills_impl.serpstat import SerpstatSkill
    return [
        ("plausible", "Plausible (web-analytics)", PlausibleSkill().available_metrics()),
        ("shopify", "Shopify (verkoop)", ShopifySalesSkill().available_metrics()),
        ("gsc", "Google Search Console", GscPerformanceSkill().available_metrics()),
        ("openalex", "OpenAlex (academische tellers)", OpenalexSkill().available_metrics()),
        ("semanticscholar", "Semantic Scholar (auteur-tellers)", SemanticScholarSkill().available_metrics()),
        ("serpstat", "Serpstat (domein-zichtbaarheid)", SerpstatSkill().available_metrics()),
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
    hulp = _FIELD_HELP.get(source, "")
    hulp_html = f"<div class='muted'>{_e(hulp)}</div>" if hulp else ""
    return (
        f"<div class='card'><div class='ptitle'>{chip} "
        f"<span class='chip muted'>{_e(t('catalogus.koppelen.status.ongekoppeld'))}</span> {vers}</div>{hulp_html}"
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


# ── Stap 2 (STATUS) + stap 3 (ACTIVEREN) — de flow-redesign ──────────────────────────────────────
def _source_field_map() -> dict:
    """Bron-id → set ruwe velden die de skill oplevert (available_metrics). Bepaalt of een 'zonder
    data'-indicator komt door 'bron levert dit veld niet' of door een tijdelijke hapering."""
    out = {}
    for cls in _data_source_classes():
        try:
            out[cls.SOURCE] = set(cls().available_metrics(None) or [])
        except Exception:
            out[cls.SOURCE] = set()
    return out


def _geen_data_reden(fresh: str, source: str, veld: str, produces: dict, active: dict) -> tuple[str, str]:
    """Twee soorten reden bij 'zonder data' (kind, tekst):
      - 'veld'   = bron levert dit veld niet (configuratie/bug: niet geïmplementeerd, geen creds, veld
                   onbekend) → structureel, vraagt een mens;
      - 'hapert' = bron levert het wél en is actief, maar gaf (nog) niets terug → tijdelijk (fail-closed
                   gat, bijv. rate-limit 429)."""
    if fresh == "unconfigured":
        return ("veld", "bron levert dit veld niet — niet geconfigureerd (creds ontbreken)")
    levert = veld in produces.get(source, set())
    is_active = bool((active.get(source) or {}).get("active"))
    if levert and is_active:
        return ("hapert", "bron hapert — fail-closed gaten (tijdelijk, bijv. rate-limit 429)")
    return ("veld", "bron levert dit veld niet (nog niet geïmplementeerd of veld onbekend)")


def _bron_indicators(st: _Stores) -> list[dict]:
    """Alle bron-gekoppelde catalogus-indicatoren met hun data-status. Niet-bron (manueel/formule) →
    geen data-notie, dus niet in deze lijst."""
    produces, active = _source_field_map(), st.sources.all()
    out = []
    for d in st.defs.all():
        cur = st.defs.current(d["id"]) or {}
        source, veld = cur.get("source", ""), cur.get("veld", "")
        fresh = indicator_freshness(st, source, veld)
        if fresh is None:
            continue
        heeft = fresh in ("fresh", "stale")
        out.append({"did": d["id"], "name": cur.get("name", ""), "source": source, "veld": veld,
                    "aard": cur.get("aard", ""), "fresh": fresh, "heeft_data": heeft,
                    "reden": ("", "") if heeft else _geen_data_reden(fresh, source, veld, produces, active)})
    return sorted(out, key=lambda i: i["name"])


def _status_section(st: _Stores) -> str:
    """Stap 2: één status-lijst, gesplitst in 'met data' en 'zonder data' (met de reden per stuk)."""
    inds = _bron_indicators(st)
    met = [i for i in inds if i["heeft_data"]]
    zonder = [i for i in inds if not i["heeft_data"]]

    def met_kaart(i):
        return (f"<div class='card'><div class='ptitle'><span class='chip'>{_e(i['name'])}</span> "
                f"{freshness_chip(i['fresh'])}</div></div>")

    def zonder_kaart(i):
        kind, txt = i["reden"]
        chip = "coral" if kind == "veld" else "outline"      # config/bug = rood; tijdelijk = neutraal
        return (f"<div class='card'><div class='ptitle'><span class='chip'>{_e(i['name'])}</span> "
                f"<span class='chip {chip}'>geen data</span></div>"
                f"<div class='muted'>{_e(txt)}</div></div>")

    met_html = "".join(met_kaart(i) for i in met) or "<p class='muted'>— nog geen indicator met data —</p>"
    zon_html = "".join(zonder_kaart(i) for i in zonder) or "<p class='muted'>— alle bronnen leveren —</p>"
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Status · met data ({len(met)})</h3></div>{met_html}</div>"
            f"<div class='c2-sec'><div class='cl-head'><h3>Status · zonder data ({len(zonder)})</h3></div>{zon_html}</div>")


def _node_options(st: _Stores) -> str:
    """Alle rollen én cirkels als dashboard-doel (open books: geen filtering op autorisatie)."""
    return "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in st.records.all())


def _activate_section(st: _Stores, csrf: str) -> str:
    """Stap 3: kies indicatoren MÉT data (checkbox) → rol/cirkel → toevoegen aan dat dashboard."""
    met = [i for i in _bron_indicators(st) if i["heeft_data"]]
    if not met:
        return ("<div class='c2-sec'><div class='cl-head'><h3>Activeren op een dashboard</h3></div>"
                "<p class='muted'>Nog geen indicatoren met data om te activeren.</p></div>")
    checks = "".join(
        f"<div class='card'><label class='att-lbl'><input type='checkbox' name='did' value='{_e(i['did'])}'> "
        f"{_e(i['name'])}</label></div>" for i in met)
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Activeren op een dashboard</h3></div>"
            f"<form method='post' action='/action'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='next' value='/catalog'>"
            f"{checks}"
            f"<label class='att-lbl'>Dashboard (rol of cirkel)</label>"
            f"<select name='node'>{_node_options(st)}</select> "
            f"<button class='btn ok' type='submit' name='action' value='indicator_activate'>"
            f"+ Toevoegen aan dashboard</button></form></div>")
