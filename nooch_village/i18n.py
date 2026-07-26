"""Dunne vertaallaag (seam) — één `t("key")`-functie + een centrale strings-catalogus.

Doel: UI-tekst door één punt laten lopen, zodat een latere Engelse vertaling mechanisch wordt
i.p.v. een handmatige jacht op duizenden losse strings. NU nog niet migreren: alleen de seam
inrichten en toepassen op nieuwe/net gewijzigde views (de metrics-scopes).

- `_CATALOG[key]` is per sleutel een dict `{"nl": ..., "en": ...}`. Vertalingen leven bij elkaar.
- `t(key, **kw)` geeft de tekst in de actieve taal; valt terug op `nl` en dan op de sleutel zelf
  (zichtbaar, nooit een crash). `**kw` → `str.format` voor interpolatie.
- Standaardtaal is `en` (de UI-taal sinds i18n fase 1). `nl` blijft als fallback staan.
- Sleutel-conventie: puntgescheiden, gegroepeerd per domein (`catalogus.koppelen.*`, `wizard.*`,
  `dashboard.*`).
"""
from __future__ import annotations

_LANG = "en"
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
# Beide talen gevuld: `en` is wat de UI toont, `nl` blijft als fallback en herkomst staan.
_CATALOG: dict[str, dict[str, str]] = {
    # ── Catalogus-koppelscherm (scope 4) ──
    "catalogus.koppelen.titel": {"nl": "Catalogus koppelen", "en": "Link catalogue"},
    "catalogus.koppelen.intro": {"nl": "Een gekoppelde bron levert ruwe velden op. Een nog niet "
        "gepubliceerd veld promoveer je tot indicator; nieuwe velden verschijnen hier vanzelf zodra de "
        "bron ze blootlegt. Alleen voor de curator (anchor-lead).",
        "en": "A connected source yields raw fields. A field that is not published yet can be "
        "promoted to an indicator; new fields appear here by themselves once the source exposes "
        "them. Curator only (anchor lead)."},
    "catalogus.koppelen.bron": {"nl": "Bron:", "en": "Source:"},
    "catalogus.koppelen.geen_velden": {"nl": "Deze bron declareert nog geen ruwe velden.",
        "en": "This source does not declare any raw fields yet."},
    "catalogus.koppelen.all_coupled": {"nl": "Alle velden van deze bron staan in de catalogus. "
        "Nieuwe velden verschijnen hier zodra de bron ze blootlegt — nu is er niets te koppelen.",
        "en": "All fields of this source are in the catalogue. New fields appear here as soon as "
        "the source exposes them — right now there is nothing to link."},
    "catalogus.koppelen.status.gekoppeld": {"nl": "in catalogus", "en": "in catalogue"},
    "catalogus.koppelen.status.ongekoppeld": {"nl": "nog niet gepubliceerd", "en": "not published yet"},
    # Data-vers-signaal (3 staten), gedeeld door koppelscherm + KPI-wizard.
    "data.vers.fresh": {"nl": "recente data", "en": "recent data"},
    "data.vers.fresh.tip": {"nl": "Er zijn datapunten van de afgelopen 7 dagen.",
        "en": "There are data points from the last 7 days."},
    "data.vers.stale": {"nl": "geen recente data", "en": "no recent data"},
    "data.vers.stale.tip": {"nl": "Gekoppeld, maar geen datapunt in de afgelopen 7 dagen — de bron levert nu niet.",
        "en": "Linked, but no data point in the last 7 days — the source is not delivering right now."},
    "data.vers.none": {"nl": "geen data", "en": "no data"},
    "data.vers.none.tip": {"nl": "Deze bron wordt (nog) niet in de observatie-store gevoed.",
        "en": "This source is not (yet) fed into the observation store."},
    "data.vers.unconfigured": {"nl": "niet geconfigureerd", "en": "not configured"},
    "data.vers.unconfigured.tip": {"nl": "Bron staat actief, maar de credentials ontbreken — los van een "
        "kapotte API. Voeg de creds toe zodat de puls 'm kan ophalen.",
        "en": "Source is active, but the credentials are missing — separate from a broken API. "
        "Add the creds so the pulse can fetch it."},
    "catalogus.koppelen.gekoppeld_als": {"nl": "Gekoppeld als", "en": "Linked as"},
    "catalogus.koppelen.veld.naam": {"nl": "Naam voor gebruikers", "en": "Name for users"},
    "catalogus.koppelen.veld.naam.ph": {"nl": "bijv. Verkochte paren", "en": "e.g. Pairs sold"},
    "catalogus.koppelen.veld.categorie": {"nl": "Categorie", "en": "Category"},
    "catalogus.koppelen.veld.aard": {"nl": "Aard", "en": "Nature"},
    "catalogus.koppelen.veld.eenheid": {"nl": "Eenheid", "en": "Unit"},
    "catalogus.koppelen.veld.eenheid.ph": {"nl": "bijv. euro, aantal, %", "en": "e.g. euro, count, %"},
    "catalogus.koppelen.veld.uitleg": {"nl": "Korte uitleg (komt in het ⓘ-icoon)",
        "en": "Short explanation (shows in the ⓘ icon)"},
    "catalogus.koppelen.veld.uitleg.ph": {"nl": "Wat betekent dit voor iemand die het niet kent?",
        "en": "What does this mean to someone who does not know it?"},
    "catalogus.koppelen.kies": {"nl": "— kies —", "en": "— choose —"},
    "catalogus.koppelen.publiceer": {"nl": "Publiceer naar catalogus", "en": "Publish to catalogue"},
    # ── KPI-wizard (scope 5) ──
    "wizard.modus.indicator": {"nl": "Bestaande indicator", "en": "Existing indicator"},
    "wizard.modus.formule": {"nl": "Formule maken", "en": "Create formula"},
    # ── Dashboard (scope 6) ──
    "dashboard.periode": {"nl": "Periode:", "en": "Period:"},
    "dashboard.vergelijk": {"nl": "Vergelijk met vorige periode", "en": "Compare with previous period"},
    "dashboard.ruwe_data": {"nl": "ruwe data", "en": "raw data"},
    "dashboard.geen_data_periode": {"nl": "geen data in deze periode", "en": "no data in this period"},
    "dashboard.geen_live_data": {"nl": "geen live data", "en": "no live data"},
}
