"""Strategie-tab voor operationele cirkels — read-only weergave (structuur C, hybride gestructureerd).

Rendert de strategie-entry (StrategyStore) als leesbare pagina: per sectie een kop, kaart-look
zoals de andere tabs. Twee dynamische blokken: (1) de geërfde purpose-keten uit de records, en
(2) twee placeholders (Words That Require Evidence → kennisbank/Lara; Current Focus → projectbord).
Elke sectie rendert alleen als hij in de entry aanwezig is, zodat een gedeeltelijke entry niet breekt.

Edit-UI, live purpose-erving-logica en de strategy_lookup-skill komen in aparte stappen.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import _name, _md
from nooch_village import org

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


def _sec(title: str, body: str) -> str:
    if not body:
        return ""
    return f"<div class='c2-sec'><h3>{_e(title)}</h3>{body}</div>"


def _text(v) -> str:
    return f"<div style='white-space:pre-wrap'>{_md(str(v))}</div>" if v else ""


def _named_items(items: list) -> str:
    """Lijst van {name, description} → naam vet + omschrijving eronder."""
    out = ""
    for it in items or []:
        nm = _e(str(it.get("name", "")))
        desc = _md(str(it.get("description", "")))
        out += (f"<div style='margin:.5rem 0'><b>{nm}</b>"
                f"<div class='muted' style='white-space:pre-wrap'>{desc}</div></div>")
    return out


def _bullets(items: list, cls: str = "") -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_md(str(x))}</li>" for x in items)
    return f"<ul class='clean {cls}'>{lis}</ul>"


def _grouped(groups: dict, labels: dict) -> str:
    """do_list/dont_list: dict van groep → lijst van strings, met leesbare groepslabels."""
    out = ""
    for key, items in (groups or {}).items():
        if not items:
            continue
        lbl = labels.get(key, key.replace("_", " ").capitalize())
        out += f"<h4 style='margin:.5rem 0 .2rem'>{_e(lbl)}</h4>{_bullets(items)}"
    return out


_DO_LABELS = {"production_and_materials": "Production & materials",
              "business_model": "Business model", "community": "Community"}
_DONT_LABELS = {"materials": "Materials", "communication": "Communication",
                "business_model": "Business model", "culture": "Culture"}


def _purpose_chain(st: "_Stores", rec) -> str:
    """Dynamisch blok: de geërfde purpose-keten van root (Mother Earth) naar deze cirkel (Nooch)."""
    recs = st.records.all()
    by_id = {r.id: r for r in recs}
    rows = ""
    for cid in org.breadcrumb(recs, rec.id):       # root eerst
        c = by_id.get(cid)
        if c is None or not org.is_circle(c):
            continue
        purpose = getattr(c.definition, "purpose", "") or "(geen purpose)"
        rows += (f"<div style='margin:.4rem 0;padding-left:.7rem;border-left:2px solid var(--border)'>"
                 f"<b>{_e(_name(c))}</b><div class='muted' style='white-space:pre-wrap'>{_e(purpose)}</div></div>")
    return _sec("Purpose (geërfde keten)", rows)


def _tone_of_voice(tov: dict) -> str:
    if not tov:
        return ""
    body = _text(tov.get("intro"))
    for p in tov.get("pillars", []) or []:
        nm = _e(str(p.get("name", "")))
        desc = _md(str(p.get("description", "")))
        do = _bullets(p.get("do"), "do")
        dont = _bullets(p.get("dont"), "dont")
        do_block = f"<div class='muted' style='font-size:.8rem;margin-top:.2rem'>Do</div>{do}" if do else ""
        dont_block = f"<div class='muted' style='font-size:.8rem'>Don't</div>{dont}" if dont else ""
        body += (f"<div style='margin:.6rem 0'><b>{nm}</b>"
                 f"<div class='muted' style='white-space:pre-wrap'>{desc}</div>{do_block}{dont_block}</div>")
    if tov.get("when_serious"):
        body += f"<h4 style='margin:.5rem 0 .2rem'>When serious</h4>{_text(tov.get('when_serious'))}"
    if tov.get("checks"):
        body += f"<h4 style='margin:.5rem 0 .2rem'>Checks</h4>{_named_items(tov.get('checks'))}"
    return _sec("Tone of voice", body)


def _honest_constraints(hc: dict) -> str:
    if not hc:
        return ""
    body = ""
    if hc.get("opener"):
        body += f"<p style='font-weight:600'>{_e(str(hc.get('opener')))}</p>"
    body += _text(hc.get("intro"))
    body += _named_items(hc.get("rules"))
    return _sec("Honest constraints", body)


def _strategy_tab_html(st: "_Stores", rec, with_purpose_chain: bool = True) -> str:
    strat = st.strategies.get(rec.id)
    if not strat:
        return ("<div class='c2-sec'><h3>Strategie</h3>"
                "<p class='muted'>Geen strategie gedefinieerd voor deze cirkel.</p></div>")

    # In de overview-tab staat de Purpose er al boven → chain overslaan (geen dubbeling).
    out = _purpose_chain(st, rec) if with_purpose_chain else ""
    # Simpele strategie-bullets onder de gewone kop "Strategie" (bv. de Mother-Earth-principes).
    out += _sec("Strategie", _bullets(strat.get("strategy")))
    out += _sec("Core sentence", _text(strat.get("core_sentence")))
    out += _sec("Vision", _text(strat.get("vision")))
    out += _sec("Mission", _text(strat.get("mission")))
    out += _sec("Operating values", _named_items(strat.get("operating_values")))
    out += _tone_of_voice(strat.get("tone_of_voice"))
    out += _sec("Position statements", _named_items(strat.get("position_statements")))
    out += _sec("Beliefs", _bullets(strat.get("beliefs")))
    # De twee placeholder-secties horen bij een RIJKE strategie (zoals Nooch); een bullets-only
    # entry (zoals Mother Earth) toont alleen zijn eigen inhoud.
    _rich = any(strat.get(k) for k in (
        "core_sentence", "vision", "mission", "operating_values", "tone_of_voice",
        "position_statements", "beliefs", "honest_constraints", "non_negotiables",
        "do_list", "dont_list"))
    if _rich:
        # Placeholder (dynamisch blok 2a): woordkeuze-bewijs leeft in de kennisbank
        out += _sec("Words that require evidence",
                    "<p class='muted'>Deze lijst wordt onderhouden in de kennisbank door "
                    "Lara the Librarian. Integratie komt later.</p>")
    out += _honest_constraints(strat.get("honest_constraints"))
    out += _sec("Non-negotiables", _named_items(strat.get("non_negotiables")))
    out += _sec("Do", _grouped(strat.get("do_list"), _DO_LABELS))
    out += _sec("Don't", _grouped(strat.get("dont_list"), _DONT_LABELS))
    if _rich:
        # Placeholder (dynamisch blok 2b): kwartaaldoelen leven op het projectbord
        out += _sec("Current focus",
                    "<p class='muted'>Quarterly goals worden beheerd in NoochVille projectbord. "
                    "Zie de projects-tab van deze cirkel.</p>")
    ver, upd = strat.get("version"), strat.get("updated_at")
    if ver is not None or upd:
        out += (f"<p class='muted' style='font-size:.78rem;margin-top:.8rem'>"
                f"versie {_e(str(ver))} · bijgewerkt {_e(str(upd))}</p>")
    return out
