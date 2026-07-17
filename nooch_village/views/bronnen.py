"""Bronnen — het aansluit-scherm voor externe databronnen.

Tot nu toe kon je een bron alleen via de CLI aanzetten. Dit scherm maakt 'aansluiten' zelfbedienend:
het toont elke DataSourceSkill met z'n live status (heb je de sleutels? staat de bron aan?), welke
sleutels ontbreken, en een aan/uit-knop. De sleutels zelf zet je in `.env` / `config/settings.ini`
(dat kan Claude niet voor je doen); daarna zie je hier 'verbonden' en zet je de bron aan. Activeren is
mens-gated en veroorzaakt pas bij de volgende pulse externe calls.
"""
from __future__ import annotations

import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav

# Leesbare labels voor bronnen zonder CATALOG_LABEL (fallback = de bron-id).
_SRC_LABEL = {
    "plausible": "Website-analytics (Plausible)", "shopify": "Verkoop (Shopify)",
    "gsc": "Zoekverkeer (Google Search Console)", "trends": "Zoekinteresse (Google Trends)",
    "trends_categorie": "Categorie-interesse (Google Trends)",
    "keywordseverywhere": "Zoekvolume (Keywords Everywhere)", "alphavantage": "Marktindex (AlphaVantage)",
    "openalex": "Wetenschap (OpenAlex)", "semanticscholar": "Wetenschap (Semantic Scholar)",
    "gdelt_tone": "Nieuwstoon (GDELT)", "co2_village": "LLM-gebruik & CO₂ (intern)",
}


def _bron_sources(st, ctx):
    """Elke DataSourceSkill één keer, met live status: (src, label, active, configured, required, missing)."""
    from nooch_village.registry_factory import build_skill_registry
    from nooch_village.skills import DataSourceSkill
    out, seen = [], set()
    for s in build_skill_registry().all():
        cls = type(s)
        src = getattr(cls, "SOURCE", None)
        if not isinstance(s, DataSourceSkill) or not src or src in seen:
            continue
        seen.add(src)
        try:
            configured = bool(s.is_configured(ctx))
        except Exception:
            configured = False
        req = [k for k in (getattr(s, "required_env", ()) or ())]
        missing = [k for k in req if not (ctx.settings.get(k) or os.getenv(k))]
        label = getattr(cls, "CATALOG_LABEL", "") or _SRC_LABEL.get(src, src)
        out.append({"src": src, "label": label, "active": st.sources.active(src),
                    "configured": configured, "req": req, "missing": missing})
    out.sort(key=lambda x: (not x["active"], not x["configured"], x["label"].lower()))
    return out


def _status_chip(it) -> str:
    if it["active"] and it["configured"]:
        return "<span class='chip'>● aan · verbonden</span>"
    if it["active"] and not it["configured"]:
        return "<span class='chip amber'>● aan · sleutel ontbreekt</span>"
    if it["configured"]:
        return "<span class='chip amber'>○ klaar om aan te zetten</span>"
    return "<span class='chip muted'>○ sleutel nodig</span>"


def _keys_line(it) -> str:
    if not it["req"]:
        return "<div class='muted'>Geen sleutel nodig.</div>"
    parts = []
    for k in it["req"]:
        ok = k not in it["missing"]
        parts.append(f"<code>{_e(k)}</code> {'✓' if ok else '✗ ontbreekt'}")
    return "<div class='muted'>Sleutels: " + ", ".join(parts) + "</div>"


def _bron_row(it, csrf: str) -> str:
    act = "source_deactivate" if it["active"] else "source_activate"
    lbl = "Zet uit" if it["active"] else "Zet aan"
    cls = "btn sm" if it["active"] else "btn ok sm"
    btn = ""
    if csrf:
        btn = (f"<form method='post' action='/action' class='emo-f'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='source' value='{_e(it['src'])}'>"
               f"<input type='hidden' name='next' value='/bronnen'>"
               f"<button class='{cls}' name='action' value='{act}'>{lbl}</button></form>")
    return (f"<div class='card'><div class='cl-head'><h3>{_e(it['label'])}</h3>"
            f"<span class='kc-actions'>{_status_chip(it)}{btn}</span></div>"
            f"<div class='muted'>bron-id: <code>{_e(it['src'])}</code></div>{_keys_line(it)}</div>")


def render_bronnen(st, base_dir: str, csrf_token: str = "") -> str:
    from nooch_village.config import load_context
    ctx = load_context(base_dir)
    items = _bron_sources(st, ctx)
    aan = sum(1 for i in items if i["active"])
    rows = "".join(_bron_row(i, csrf_token) for i in items) or "<p class='muted'>Geen bronnen gevonden.</p>"
    main = (f"<div class='c2-main'><h1>Bronnen aansluiten</h1>"
            f"<p class='muted'>{aan} van {len(items)} bronnen staan aan. Zet de sleutels in "
            f"<code>.env</code> of <code>config/settings.ini</code> op de server; zodra ze er staan zie "
            f"je hier ‘verbonden’ en kun je de bron aanzetten. Een bron haalt pas bij de volgende "
            f"dagelijkse pulse data op.</p>{rows}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Bronnen", inner)
