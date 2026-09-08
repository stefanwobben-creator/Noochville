"""Metadata over skills als dorpsmiddel: domein, gewicht, suggestie-tegenhanger.

Een skill is een gedeeld middel — één implementatie, één key, één limiter, hoeveel rollen hem
ook gebruiken. Maar niet elk middel is vrij koppelbaar. Drie markeringen:

- `schrijft_in_domein` — deze skill BESLIST in een domein (bijv. `keyword_review` keurt woorden
  goed of verbiedt ze in "bibliotheek"). De domeinregel is absoluut: alleen de rol die dat
  domein zelf houdt mag hem koppelen én uitvoeren. Geen policy-omweg. Andere rollen krijgen de
  suggestie-tegenhanger, waarvan de output in de wachtrij van de domeinhouder landt.
- `zwaar` — dit middel draagt mandaat-gewicht; de grant loopt via governance (`add_skills`),
  niet via een operationele koppeling.
- `suggestie_van` — deze skill is de suggestie-tegenhanger van die beslis-skill.

Eén centrale map, net als `skill_labels.LABELS`: zo staan de markeringen naast elkaar en zie je
in één blik welke middelen domein-gebonden zijn. Additief en fail-soft: een skill die hier niet
staat is een vrij koppelbaar lees-/data-middel.
"""
from __future__ import annotations

META: dict[str, dict] = {
    # ── Domein "bibliotheek" — Lara beslist, anderen nomineren ───────────────
    "keyword_review": {
        "schrijft_in_domein": "bibliotheek",
        "zwaar": True,
        # Geen `suggestie_tegenhanger` meer: die wees naar `keyword_nominatie`, dat niet bestaat.
        # Zie het blok onder deze dict. Nomineren gaat via de cockpit-acties `kw_nominate` /
        # `kw_nom_accept` / `kw_nom_reject` (`keyword_nominations.py`), niet via een skill.
    },
}

# WEGGEHAALD OP 8 SEPTEMBER: `library_curate` en `keyword_nominatie`.
#
# Allebei "naamvariant uit de ontwerpnotitie, nog geen registry-implementatie". Ze stonden hier
# als reservering, en dat leek gratis. Dat was het niet: `koppelbaar()` gaf als weigeringsreden
# "Wel beschikbaar: de suggestie-variant 'keyword_nominatie'" — een tekst die via vier schermen
# naar de mens ging en een gereedschap noemde dat niet bestaat. Op de /skills-kaart stond
# bovendien "Suggestion counterpart: keyword_nominatie — other roles suggest, the domain owner
# decides." Dat is dezelfde fout als de ja-knop op een kans: het scherm belooft iets wat er niet
# is, en pas als iemand het probeert blijkt het.
#
# De FUNCTIE bestaat trouwens wel, onder een andere naam: `keyword_nominations.py` met
# `NominationQueue`/`NominationKroniek` en de cockpit-acties `kw_nominate` / `kw_nom_accept` /
# `kw_nom_reject`. Er viel dus niets te bouwen — er stond een tweede naam voor iets dat al leefde,
# en dat is precies wat "reference, don't copy" verbiedt.


def _entry(skill: str) -> dict:
    return META.get(skill) or {}


def schrijft_in_domein(skill: str) -> str | None:
    """In welk domein beslist deze skill? None = vrij koppelbaar op passendheid."""
    return _entry(skill).get("schrijft_in_domein")


def is_zwaar(skill: str) -> bool:
    """Draagt dit middel mandaat-gewicht (grant via governance i.p.v. een koppeling)?"""
    return bool(_entry(skill).get("zwaar"))


def suggestie_van(skill: str) -> str | None:
    """Van welke beslis-skill is dit de suggestie-variant?"""
    return _entry(skill).get("suggestie_van")


def suggestie_tegenhanger(skill: str) -> str | None:
    """Welke suggestie-variant hoort bij deze beslis-skill?"""
    return _entry(skill).get("suggestie_tegenhanger")


def _domains_of(rec) -> set[str]:
    defn = getattr(rec, "definition", None)
    return {d.lower() for d in (getattr(defn, "domains", None) or [])}


def koppelbaar(skill: str, rec) -> tuple[bool, str]:
    """Mag dit middel aan DEZE rol gekoppeld worden?

    Fail-closed: bestaat het record niet, dan nee. Een beslis-skill kan alleen bij de
    domeinhouder; alle andere middelen zijn vrij koppelbaar op passendheid (de Circle Lead
    oordeelt over de passendheid, niet de code).

    Returns (mag, reden) — de reden is mensentaal en gaat de UI in.
    """
    if not skill:
        return False, "geen middel opgegeven"
    if rec is None:
        return False, "rol niet gevonden"
    domein = schrijft_in_domein(skill)
    if not domein:
        return True, ""
    if domein.lower() in _domains_of(rec):
        return True, ""
    tegen = suggestie_tegenhanger(skill)
    extra = f" Wel beschikbaar: de suggestie-variant '{tegen}'." if tegen else ""
    return False, (f"'{skill}' beslist in het domein '{domein}'; alleen de domeinhouder mag "
                   f"dat middel voeren.{extra}")


def domein_gaten(records) -> list[str]:
    """Stille domein-gaten in de LEVENDE records: bewaakte domeinen zonder houder, en rollen die een
    domein-skill bezitten die ze niet mogen voeren.

    Bestaat omdat een pytest-guard alleen `seeds.py` ziet. Op productie hield de Librarian het
    domein `library` terwijl seeds en deze module `bibliotheek` bedoelen — het record was afgedreven,
    de code niet. Gevolg: `keyword_review` weigerde elke aanroep en de curatie-lijn stond stil,
    vijftien dagen lang, zonder dat iets zich meldde.

    Een uitgezette domein-skill meldt zichzelf niet: dat is het hele probleem. Dus melden wij."""
    uit: list[str] = []
    recs = list(records or [])
    for skill, meta in META.items():
        domein = meta.get("schrijft_in_domein")
        if not domein or domeinhouders(skill, recs):
            continue
        bezitters = [r.id for r in recs
                     if skill in (getattr(getattr(r, "definition", None), "skills", None) or [])]
        uit.append(f"domein '{domein}' heeft geen houder; '{skill}' is daardoor onbruikbaar"
                   + (f" voor {', '.join(bezitters)}" if bezitters else " (niemand bezit hem)"))
    for rec in recs:
        d = getattr(rec, "definition", None)
        for skill in (getattr(d, "skills", None) or []):
            if not schrijft_in_domein(skill):
                continue
            ok, waarom = koppelbaar(skill, rec)
            if not ok:
                uit.append(f"{rec.id}: {waarom} (eigen domeinen: {list(d.domains or []) or 'geen'})")
    return uit


def domeinhouders(skill: str, records) -> list[str]:
    """Welke rollen houden het domein waarin deze skill beslist? Leeg = vrij koppelbaar."""
    domein = schrijft_in_domein(skill)
    if not domein:
        return []
    out = []
    for rec in records:
        if getattr(rec, "archived", False):
            continue
        if domein.lower() in _domains_of(rec):
            out.append(rec.id)
    return sorted(out)
