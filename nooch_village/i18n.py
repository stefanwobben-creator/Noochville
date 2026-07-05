"""Dunne vertaallaag (seam) — één `t("key")`-functie + een centrale strings-catalogus.

Doel: UI-tekst door één punt laten lopen, zodat een latere Engelse vertaling mechanisch wordt
i.p.v. een handmatige jacht op duizenden losse strings. NU nog niet migreren: alleen de seam
inrichten en toepassen op nieuwe/net gewijzigde views (de metrics-scopes).

- `_CATALOG[key]` is per sleutel een dict `{"nl": ..., "en": ...}`. Vertalingen leven bij elkaar.
- `t(key, **kw)` geeft de tekst in de actieve taal; valt terug op `nl` en dan op de sleutel zelf
  (zichtbaar, nooit een crash). `**kw` → `str.format` voor interpolatie.
- Standaardtaal is `nl` (de huidige UI). Alleen `nl` is gevuld; `en` groeit incrementeel per sleutel.
- Sleutel-conventie: puntgescheiden, gegroepeerd per domein (`catalogus.koppelen.*`, `wizard.*`,
  `dashboard.*`).
"""
from __future__ import annotations

_LANG = "nl"
_FALLBACK = "nl"


def set_lang(lang: str) -> None:
    """Zet de actieve taal (bv. later per-request/uit config). Onbekend → geen wijziging."""
    global _LANG
    if lang in ("nl", "en"):
        _LANG = lang


def lang() -> str:
    return _LANG


def t(key: str, /, **kw) -> str:
    """Vertaalde UI-tekst: actieve taal → nl → de sleutel zelf. `**kw` interpoleert via str.format."""
    entry = _CATALOG.get(key, {})
    s = entry.get(_LANG) or entry.get(_FALLBACK) or key
    return s.format(**kw) if kw else s


# ── Catalogus ──────────────────────────────────────────────────────────────────
# Alleen `nl` gevuld (de huidige teksten, byte-identiek). `en` komt later per sleutel.
# `catalogus.koppelen.titel` heeft één `en` als bewijs dat de tweetalige structuur werkt.
_CATALOG: dict[str, dict[str, str]] = {
    # ── Catalogus-koppelscherm (scope 4) ──
    "catalogus.koppelen.titel": {"nl": "Catalogus koppelen", "en": "Link catalogue"},
    "catalogus.koppelen.intro": {"nl": "Een gekoppelde bron levert ruwe velden op, geen KPI's. "
        "Per veld wijs je naam, categorie en aard toe. Pas na publiceren verschijnt een veld als "
        "indicator in de KPI-wizard. Alleen voor de curator (anchor-lead)."},
    "catalogus.koppelen.bron": {"nl": "Bron:"},
    "catalogus.koppelen.geen_velden": {"nl": "Deze bron declareert nog geen ruwe velden."},
    "catalogus.koppelen.status.gekoppeld": {"nl": "in catalogus"},
    "catalogus.koppelen.status.ongekoppeld": {"nl": "nog niet gepubliceerd"},
    "catalogus.koppelen.gekoppeld_als": {"nl": "Gekoppeld als"},
    "catalogus.koppelen.veld.naam": {"nl": "Naam voor gebruikers"},
    "catalogus.koppelen.veld.naam.ph": {"nl": "bijv. Verkochte paren"},
    "catalogus.koppelen.veld.categorie": {"nl": "Categorie"},
    "catalogus.koppelen.veld.aard": {"nl": "Aard"},
    "catalogus.koppelen.veld.eenheid": {"nl": "Eenheid"},
    "catalogus.koppelen.veld.eenheid.ph": {"nl": "bijv. euro, aantal, %"},
    "catalogus.koppelen.veld.uitleg": {"nl": "Korte uitleg (komt in het ⓘ-icoon)"},
    "catalogus.koppelen.veld.uitleg.ph": {"nl": "Wat betekent dit voor iemand die het niet kent?"},
    "catalogus.koppelen.kies": {"nl": "— kies —"},
    "catalogus.koppelen.publiceer": {"nl": "Publiceer naar catalogus"},
    # ── KPI-wizard (scope 5) ──
    "wizard.modus.indicator": {"nl": "Bestaande indicator"},
    "wizard.modus.formule": {"nl": "Formule maken"},
    # ── Dashboard (scope 6) ──
    "dashboard.periode": {"nl": "Periode:"},
    "dashboard.vergelijk": {"nl": "Vergelijk met vorige periode"},
    "dashboard.ruwe_data": {"nl": "ruwe data"},
    "dashboard.geen_data_periode": {"nl": "geen data in deze periode"},
    "dashboard.geen_live_data": {"nl": "geen live data"},
}
