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
        return "<div class='muted'>Geen sleutel nodig.</div>"
    parts = []
    if req:
        parts.append("Sleutel nodig: " + ", ".join(f"<code>{_e(k)}</code>" for k in req))
    if opt:
        parts.append("optioneel: " + ", ".join(f"<code>{_e(k)}</code>" for k in opt))
    return f"<div class='muted'>{' · '.join(parts)}</div>"


def _gebruikers_regel(gebruikers: list[dict]) -> str:
    """Wie voert dit middel — en via welke route. De belofte staat erbij bij een koppeling:
    dát is waar het middel voor dient."""
    if not gebruikers:
        return "<div class='muted'>Nog niemand voert dit middel.</div>"
    delen = []
    for g in gebruikers:
        if g["route"] == "koppeling":
            acc = f" · {_e(g['acc'])}" if g.get("acc") else ""
            delen.append(f"<code>{_e(g['role'])}</code> (koppeling{acc})")
        else:
            delen.append(f"<code>{_e(g['role'])}</code> (DNA)")
    return f"<div class='muted'>Gevoerd door: {', '.join(delen)}</div>"


def _markering(row: dict) -> str:
    """Domein- en zwaar-markering als chip; een vrij koppelbaar middel krijgt het groene chip."""
    if row["domein"]:
        return f"<span class='chip amber'>domein: {_e(row['domein'])}</span>"
    return "<span class='chip'>● uitvoerbaar</span>"


def _skill_card(row: dict) -> str:
    extra = ""
    if row["zwaar"]:
        extra += " · zwaar (grant via governance)"
    tegen = ""
    if row["suggestie_tegenhanger"]:
        tegen = (f"<div class='muted'>Suggestie-tegenhanger: "
                 f"<code>{_e(row['suggestie_tegenhanger'])}</code> — andere rollen suggereren, "
                 f"de domeinhouder beslist.</div>")
    elif row["suggestie_van"]:
        tegen = (f"<div class='muted'>Suggestie-variant van "
                 f"<code>{_e(row['suggestie_van'])}</code>; de output landt in de wachtrij "
                 f"van de domeinhouder.</div>")
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['label'])}</h3>"
            f"<span class='kc-actions'>{_markering(row)}</span></div>"
            f"<div class='muted'>capability: <code>{_e(row['skill'])}</code>{extra}</div>"
            f"{_sleutel_regel(row['sleutels'])}{tegen}"
            f"{_gebruikers_regel(row['gebruikers'])}</div>")


def _zonder_impl_card(row: dict) -> str:
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['skill'])}</h3>"
            f"<span class='kc-actions'><span class='chip muted'>○ geen implementatie</span>"
            f"</span></div>"
            f"<div class='muted'>Genoemd in het dorp, maar de registry kent deze capability "
            f"niet. Een aanroep faalt closed.</div>{_gebruikers_regel(row['gebruikers'])}</div>")


def _dood_card(row: dict) -> str:
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['label'])}</h3>"
            f"<span class='kc-actions'><span class='chip amber'>○ aangeroepen zonder grant"
            f"</span></span></div>"
            f"<div class='muted'>capability: <code>{_e(row['skill'])}</code> · rol: "
            f"<code>{_e(row['role'])}</code></div>"
            f"<div class='muted'>De code roept dit middel aan, maar de rol voert het niet. "
            f"Grant via governance óf koppel het op de accountability.</div></div>")


def _gewenst_card(row: dict) -> str:
    wie = ""
    if row["role"]:
        wie = f"<div class='muted'>Mandaat ligt bij <code>{_e(row['role'])}</code>"
        if row["gevoeld_door"]:
            wie += f", gevoeld door <code>{_e(row['gevoeld_door'])}</code>"
        wie += ".</div>"
    return (f"<div class='card'><div class='cl-head'><h3>{_e(row['beschrijving']) or '—'}</h3>"
            f"<span class='kc-actions'><span class='chip muted'>○ tooling gewenst</span>"
            f"</span></div>"
            f"<div class='muted'>gap: <code>{_e(row['gap_key'])}</code></div>{wie}</div>")


# ── De pagina ────────────────────────────────────────────────────────────────

def render_skills(st, human_inbox=None) -> str:
    data = skills_catalog.catalogus(st.records.all(), st.ai, human_inbox)

    uit = data["uitvoerbaar"]
    kaarten = "".join(_skill_card(r) for r in uit) or "<p class='muted'>Geen skills gevonden.</p>"

    zonder = data["niet_gedekt"]["zonder_implementatie"]
    dood = data["niet_gedekt"]["dood"]
    if zonder or dood:
        blok2 = "".join(_zonder_impl_card(r) for r in zonder) + "".join(_dood_card(r) for r in dood)
    else:
        blok2 = ("<p class='muted'>Niets. Elk genoemd middel heeft een implementatie en elke "
                 "aanroep heeft een grant.</p>")

    wens = data["gewenst"]
    blok3 = "".join(_gewenst_card(r) for r in wens) or (
        "<p class='muted'>Geen openstaande means-gaps: er is geen rol die mandaat heeft "
        "zonder middel.</p>")

    gedekt = sum(1 for r in uit if r["gebruikers"])
    main = (f"<div class='c2-main'><h1>Skills — wat kan het dorp al?</h1>"
            f"<p class='muted'>Een skill is een gedeeld dorpsmiddel: één implementatie, één "
            f"sleutel, één limiter, hoeveel rollen hem ook voeren. Hij hangt aan een belofte "
            f"(accountability), niet aan een rol. Een middel dat in een domein <b>beslist</b> "
            f"kan alleen bij de domeinhouder; anderen krijgen de suggestie-variant.</p>"
            f"<h2>Uitvoerbaar</h2>"
            f"<p class='muted'>{len(uit)} middelen met een implementatie, waarvan {gedekt} "
            f"daadwerkelijk gevoerd worden.</p>{kaarten}"
            f"<h2>Genoemd maar niet gedekt</h2>"
            f"<p class='muted'>Genoemd in DNA of in een koppeling zonder implementatie, plus "
            f"aanroepen in code zonder grant.</p>{blok2}"
            f"<h2>Gewenst</h2>"
            f"<p class='muted'>De bouwlijst: waar mandaat bestaat maar het middel ontbreekt.</p>"
            f"{blok3}</div>")
    return _page("Skills", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
