"""Skills — de catalogus van dorpsmiddelen.

Wat kan het dorp al, en waarvoor moet er nog tooling komen? Drie blokken, allemaal leeswerk
op bestaande bronnen (registry, records, koppelingen, human inbox) — dit scherm schrijft niets.

Vormgeving: hergebruikt het patroon van `views/bronnen.py` (één `.card` per middel met
`.cl-head` + `h3`, statuschip in `.kc-actions`, sleutel- en gebruikersregels in `.muted` met
`<code>`). Geen nieuwe CSS-klassen, geen inline styles.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village import skills_catalog


# ── Regels binnen een kaart ──────────────────────────────────────────────────

def _sleutel_regel(sleutels: dict) -> str:
    req, opt = sleutels.get("verplicht") or [], sleutels.get("optioneel") or []
    if not req and not opt:
        return "<div class='muted'>No key needed.</div>"
    parts = []
    if req:
        parts.append("Key needed: " + ", ".join(f"<code>{_e(k)}</code>" for k in req))
    if opt:
        parts.append("optional: " + ", ".join(f"<code>{_e(k)}</code>" for k in opt))
    return f"<div class='muted'>{' · '.join(parts)}</div>"


def _gebruikers_regel(gebruikers: list[dict]) -> str:
    """Wie voert dit middel — en via welke route. De belofte staat erbij bij een koppeling:
    dát is waar het middel voor dient."""
    if not gebruikers:
        return "<div class='muted'>Nobody wields this means yet.</div>"
    delen = []
    for g in gebruikers:
        if g["route"] == "koppeling":
            acc = f" · {_e(g['acc'])}" if g.get("acc") else ""
            delen.append(f"<code>{_e(g['role'])}</code> (link{acc})")
        else:
            delen.append(f"<code>{_e(g['role'])}</code> (DNA)")
    return f"<div class='muted'>Wielded by: {', '.join(delen)}</div>"


def _markering(row: dict) -> str:
    """Domein- en zwaar-markering als chip; een vrij koppelbaar middel krijgt het groene chip."""
    if row["domein"]:
        return f"<span class='chip amber'>domain: {_e(row['domein'])}</span>"
    return "<span class='chip'>● executable</span>"


def _skill_card(row: dict) -> str:
    extra = ""
    if row["zwaar"]:
        extra += " · heavy (grant via governance)"
    tegen = ""
    if row["suggestie_tegenhanger"]:
        tegen = (f"<div class='muted'>Suggestion counterpart: "
                 f"<code>{_e(row['suggestie_tegenhanger'])}</code> — other roles suggest, "
                 f"the domain owner decides.</div>")
    elif row["suggestie_van"]:
        tegen = (f"<div class='muted'>Suggestion variant of "
                 f"<code>{_e(row['suggestie_van'])}</code>; the output lands in the queue "
                 f"of the domain owner.</div>")
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['label'])}</h3>"
            f"<span class='kc-actions'>{_markering(row)}</span></div>"
            f"<div class='muted'>capability: <code>{_e(row['skill'])}</code>{extra}</div>"
            f"{_sleutel_regel(row['sleutels'])}{tegen}"
            f"{_gebruikers_regel(row['gebruikers'])}</div>")


def _zonder_impl_card(row: dict) -> str:
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['skill'])}</h3>"
            f"<span class='kc-actions'><span class='chip muted'>○ no implementation</span>"
            f"</span></div>"
            f"<div class='muted'>Named in the village, but the registry does not know this "
            f"capability. A call fails closed.</div>{_gebruikers_regel(row['gebruikers'])}</div>")


def _dood_card(row: dict) -> str:
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['label'])}</h3>"
            f"<span class='kc-actions'><span class='chip amber'>○ called without a grant"
            f"</span></span></div>"
            f"<div class='muted'>capability: <code>{_e(row['skill'])}</code> · role: "
            f"<code>{_e(row['role'])}</code></div>"
            f"<div class='muted'>The code calls this means, but the role does not wield it. "
            f"Grant it via governance or link it on the accountability.</div></div>")


def _gewenst_card(row: dict) -> str:
    wie = ""
    if row["role"]:
        wie = f"<div class='muted'>Mandate sits with <code>{_e(row['role'])}</code>"
        if row["gevoeld_door"]:
            wie += f", sensed by <code>{_e(row['gevoeld_door'])}</code>"
        wie += ".</div>"
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['beschrijving']) or '—'}</h3>"
            f"<span class='kc-actions'><span class='chip muted'>○ tooling wanted</span>"
            f"</span></div>"
            f"<div class='muted'>gap: <code>{_e(row['gap_key'])}</code></div>{wie}</div>")


# ── De pagina ────────────────────────────────────────────────────────────────

def render_skills(st, human_inbox=None) -> str:
    data = skills_catalog.catalogus(st.records.all(), st.ai, human_inbox)

    uit = data["uitvoerbaar"]
    kaarten = "".join(_skill_card(r) for r in uit) or "<p class='muted'>No skills found.</p>"

    zonder = data["niet_gedekt"]["zonder_implementatie"]
    dood = data["niet_gedekt"]["dood"]
    if zonder or dood:
        blok2 = "".join(_zonder_impl_card(r) for r in zonder) + "".join(_dood_card(r) for r in dood)
    else:
        blok2 = ("<p class='muted'>Nothing. Every named means has an implementation and every "
                 "call has a grant.</p>")

    wens = data["gewenst"]
    blok3 = "".join(_gewenst_card(r) for r in wens) or (
        "<p class='muted'>No open means gaps: there is no role with a mandate but no "
        "means.</p>")

    gedekt = sum(1 for r in uit if r["gebruikers"])
    main = (f"<div class='c2-main'><h1>Skills — what can the village already do?</h1>"
            f"<p class='muted'>A skill is a shared village resource: one implementation, one "
            f"key, one limiter, however many roles wield it. It hangs on a commitment "
            f"(accountability), not on a role. A means that <b>decides</b> inside a domain "
            f"can only sit with the domain owner; others get the suggestion variant.</p>"
            f"<h2>Executable</h2>"
            f"<p class='muted'>{len(uit)} means with an implementation, of which {gedekt} "
            f"are actually wielded.</p>{kaarten}"
            f"<h2>Named but not covered</h2>"
            f"<p class='muted'>Named in DNA or in a link without an implementation, plus "
            f"calls in code without a grant.</p>{blok2}"
            f"<h2>Wanted</h2>"
            f"<p class='muted'>The build list: where a mandate exists but the means is missing.</p>"
            f"{blok3}</div>")
    # Behoud dezelfde shell als het projectenbord: de organisatieboom in de rail, zodat je bij een
    # tool/skill je navigatie niet kwijt bent (founder 23 jul).
    from nooch_village.views.overview import _tree_html
    rail = f"<div class='c2-rail'>{_tree_html(st, '')}</div>"
    return _page("Skills", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}{rail}</div>")
