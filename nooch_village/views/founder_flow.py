"""views/founder_flow.py — het scherm van de graduele-autonomie-trainingslus.

Vormgeving: strikt hergebruik van het bestaande vocabulaire (`.card`, `.chip`, `.btn`, `.cl-bar`,
`.c2-sec`, `.pill`, `.muted`). Geen nieuw klasse-prefix, geen inline style, geen eigen CSS-blob —
de ratchet-guards bewaken dat, maar de reden is inhoudelijk: dit scherm is een lijst met knoppen,
en daar bestaat al een vormtaal voor.

Twee dingen die de VIEW moet afdwingen, niet alleen de logica:

1. **Blind-eerst is afwezigheid, geen verstopping.** Op niveau A/B en in de auditsteekproef staat
   het AI-voorstel niet in de HTML. Niet `hidden`, niet gedimd — er niet. Een voorstel dat in de
   broncode staat, is een voorstel dat lekt, en dan meet de lus de echo van de AI in plaats van
   het oordeel van de mens.
2. **Correctie kost één klik, net als goedkeuren.** Beide zijn één submit-knop in hetzelfde
   formulier. Zodra corrigeren twee klikken of een tekstveld kost, krijg je stilzwijgende
   instemming — en een meting die te mooi is om waar te zijn.

Op A/B zijn de knoppen bewust neutraal (`.btn`, geen `.btn ok`): daar mag niets naar een antwoord
duwen. Op C/D krijgt het AI-voorstel wél de primaire kleur — dáár ís het de default, en dat mag je
dan ook eerlijk laten zien (UX_PATTERNS §6: alleen sturen als je bewust stuurt).
"""
from __future__ import annotations

import time

from nooch_village import founder_flow as ff
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.web_base import _banner, _e, _page

RITMES = ("dag", "week")
_RITME_LABEL = {"dag": "Daily — short round", "week": "Weekly — full queue"}


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _terug(ritme: str) -> str:
    return f"/founder?ritme={ritme}"


def _hidden(csrf_token: str, ritme: str, **velden) -> str:
    rijen = [f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>",
             f"<input type='hidden' name='next' value='{_e(_terug(ritme))}'>"]
    rijen += [f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>" for k, v in velden.items()]
    return "".join(rijen)


# ── De onthulling na een blinde beslissing ───────────────────────────────────

def _onthulling(onthuld: str, csrf_token: str, ritme: str) -> str:
    """Wat de AI zou hebben gezegd, ná de menselijke beslissing.

    Dit is de tegenhanger van blind-eerst: de founder wordt niet gestuurd, maar leert wél. Op
    niveau A blijft het bij de constatering (daar beslist hij en verder niemand). Vanaf B mag hij
    met één klik alsnog het AI-voorstel overnemen — die klik wordt als correctie gelogd en telt,
    juist omdat hij besmet is, NIET mee in de meting."""
    delen = (onthuld or "").split("|")
    if len(delen) != 5:
        return ""
    taak, item, mens, ai, niveau = delen
    if taak not in ff.TAKEN or mens not in ff.OORDELEN[taak]:
        return ""
    mens_l = _e(ff.OORDEEL_LABEL.get(mens, mens))
    if ai not in ff.OORDELEN[taak]:
        return (f"<div class='card'><div class='ptitle'>You: {mens_l}</div>"
                f"<p class='muted'>The AI had no proposal for this item, so this decision does "
                f"not count towards the measurement.</p></div>")
    eens = mens == ai
    ai_l = _e(ff.OORDEEL_LABEL.get(ai, ai))
    chip = ("<span class='chip green'>agreed</span>" if eens
            else "<span class='chip amber'>disagreed</span>")
    knop = ""
    if not eens and niveau != "A" and csrf_token:
        knop = (f"<form method='post' action='/action'>"
                f"{_hidden(csrf_token, ritme, taak=taak, item=item, oordeel=ai, correctie='1')}"
                f"<button class='btn sm' type='submit' name='action' value='ff_beslis'>"
                f"take the AI's answer instead</button></form>")
    return (f"<div class='card'>{chip} <span class='ptitle'>You: {mens_l} · AI: {ai_l}</span>"
            f"<p class='muted'>Recorded blind — the proposal was computed before you decided but "
            f"only shown afterwards, so this example counts towards the measurement.</p>"
            f"{knop}</div>")


# ── De kop van een taak: niveau, meting, promotie ────────────────────────────

def _meterkaart(data_dir: str, taak: str, niveau: str, labels: list[dict], cfg: dict,
                csrf_token: str, ritme: str) -> str:
    meting = ff.overeenstemming(labels, taak, cfg["venster"])
    kan, reden = ff.promoveerbaar(labels, taak, niveau, cfg)
    afwijking = ff.drift(labels, taak, niveau, cfg)

    meetregel = (
        f"agreement <b>{_pct(meting['ratio'])}</b> "
        f"(95% lower bound {_pct(meting['lo'])}) over {meting['n']} blind example(s) · "
        f"bar {_pct(cfg['lat'])}, minimum {int(cfg['min_n'])}"
        if meting["n"] else
        f"no blind examples yet · bar {_pct(cfg['lat'])}, minimum {int(cfg['min_n'])}")

    knoppen = ""
    if csrf_token:
        if kan:
            knoppen += (
                f"<form method='post' action='/action'>"
                f"{_hidden(csrf_token, ritme, taak=taak)}"
                f"<button class='btn ok sm' type='submit' name='action' value='ff_promote'>"
                f"promote to {ff.volgende(niveau)}</button></form>")
        if niveau != "A":
            knoppen += (
                f"<form method='post' action='/action'>"
                f"{_hidden(csrf_token, ritme, taak=taak)}"
                f"<button class='btn sm' type='submit' name='action' value='ff_demote'>"
                f"step back to {ff.vorige(niveau)}</button></form>")
    poort = "" if kan else f"<p class='muted'>Promotion blocked: {_e(reden)}</p>"
    waarschuwing = f"<div class='flash err'>{_e(afwijking)}</div>" if afwijking else ""

    return (f"<div class='card'>"
            f"<div class='ptitle'>Level {_e(niveau)} "
            f"<span class='pill'>{_e(ff.NIVEAU_UITLEG[niveau])}</span></div>"
            f"<p class='muted'>{meetregel}</p>"
            f"{waarschuwing}{poort}{knoppen}"
            f"{_weekregel(labels, taak)}</div>")


def _weekregel(labels: list[dict], taak: str) -> str:
    """De succesmetriek: founder-minuten per week, en welk aandeel de AI overnam.

    Het getal dat moet dalen staat vooraan. Zonder weken toont hij dat er nog niets te zien is —
    'leeg' is iets anders dan 'nul' (UX_PATTERNS §7)."""
    cijfers = ff.weekcijfers(labels, taak)
    if not cijfers:
        # De naam van de metriek staat er ook zonder data: "leeg" is iets anders dan "nul", en een
        # metriek die pas verschijnt als hij gevuld is, valt niet op als hij wegblijft.
        return "<p class='muted'>Founder minutes per week: nothing measured yet.</p>"
    stukken = " · ".join(
        f"{_e(c['week'])} <b>{c['minuten']} min</b> "
        f"({c['beslissingen']} decision(s), AI {_pct(c['ai_aandeel'])})"
        for c in cijfers)
    richting = ff.trend(cijfers)
    staart = f" <span class='pill'>{_e(richting)}</span>" if richting else ""
    return f"<p class='muted'>Founder minutes per week: {stukken}{staart}</p>"


# ── Eén item ─────────────────────────────────────────────────────────────────

def _knoppen(taak: str, item: dict, toon_voorstel: bool, csrf_token: str, ritme: str,
             correctie: bool = False) -> str:
    """Elke keuze is één submit-knop in hetzelfde formulier: goedkeuren en corrigeren kosten
    exact evenveel. Alleen als het voorstel zichtbaar is krijgt het de primaire kleur."""
    if not csrf_token:
        return "<p class='muted'>Read-only — log in to decide.</p>"
    knoppen = ""
    for oordeel in ff.OORDELEN[taak]:
        primair = " ok" if (toon_voorstel and oordeel == item.get("ai")) else ""
        label = ff.OORDEEL_LABEL.get(oordeel, oordeel)
        knoppen += (f"<button class='btn{primair} sm' type='submit' name='oordeel' "
                    f"value='{_e(oordeel)}'>{_e(label)}</button>")
    extra = {"correctie": "1"} if correctie else {}
    return (f"<form method='post' action='/action'>"
            f"{_hidden(csrf_token, ritme, taak=taak, item=item['item'], **extra)}"
            f"<input type='hidden' name='action' value='ff_beslis'>"
            # Server-gestempeld: hieruit volgen de founder-minuten. De client kiest het moment
            # niet — hij krijgt het mee en stuurt het terug.
            f"<input type='hidden' name='getoond' value='{time.time():.0f}'>"
            f"{knoppen}</form>")


def _itemkaart(taak: str, item: dict, niveau: str, audit: bool, csrf_token: str,
               ritme: str) -> str:
    toon = ff.toont_voorstel_vooraf(niveau, audit)
    kop = ""
    if audit and niveau in ("C", "D"):
        kop = "<span class='chip amber'>audit sample</span> "
    detail = f"<p class='muted'>{_e(item.get('detail', ''))}</p>" if item.get("detail") else ""
    bron = ""
    if item.get("context"):
        bron = f"<span class='pill'>{_e(item['context'])}</span>"
    if item.get("link"):
        bron += (f" <a href='{_e(item['link'])}' target='_blank' rel='noopener'>source ↗</a>")

    if toon and item.get("ai"):
        voorstel = (f"<p class='muted'>The AI proposes <b>"
                    f"{_e(ff.OORDEEL_LABEL.get(item['ai'], item['ai']))}</b> — "
                    f"{_e(item.get('ai_waarom', ''))}</p>")
    elif toon:
        voorstel = "<p class='muted'>The AI has no proposal for this item — you decide.</p>"
    else:
        # Blind: geen voorstel in de HTML. Alleen de belofte dat het er ná de beslissing is.
        voorstel = "<p class='muted'>You decide first; the AI's proposal follows afterwards.</p>"

    return (f"<div class='card'>{kop}<span class='ptitle'>{_e(item.get('titel', ''))}</span> {bron}"
            f"{detail}{voorstel}"
            f"{_knoppen(taak, item, toon, csrf_token, ritme)}</div>")


def _ai_gedaan(labels: list[dict], taak: str, niveau: str, csrf_token: str, ritme: str,
               maximaal: int = 8) -> str:
    """Niveau C: wat de AI zelf afhandelde, mét een correctie op één klik.

    Op D staat dit blok er bewust NIET — dat is precies het verschil tussen 'jij auditeert' en
    'stil'. De auditsteekproef blijft op beide niveaus doorlopen, dus meten doen we hoe dan ook."""
    if niveau != "C":
        return ""
    rijen = [r for r in labels if r.get("taak") == taak and r.get("mens") is None]
    rijen.sort(key=lambda r: r.get("ts", 0), reverse=True)
    if not rijen:
        return ""
    kaarten = ""
    for r in rijen[:maximaal]:
        gedaan = _e(ff.OORDEEL_LABEL.get(r.get("ai"), r.get("ai") or "?"))
        item = {"item": r.get("item", ""), "ai": r.get("ai")}
        kaarten += (
            f"<div class='card'><span class='chip muted'>done by the AI</span> "
            f"<span class='ptitle'>{_e(r.get('titel') or r.get('item', ''))}</span> "
            f"<span class='pill'>{gedaan}</span>"
            f"{_knoppen(taak, item, True, csrf_token, ritme, correctie=True)}</div>")
    return (f"<div class='c2-sec'><h3>Handled by the AI — audit</h3>"
            f"<p class='muted'>One click corrects any of these; the correction is recorded.</p>"
            f"{kaarten}</div>")


# ── Eén taak ─────────────────────────────────────────────────────────────────

def _taaksectie(st, data_dir: str, taak: str, niveau: str, labels: list[dict], cfg: dict,
                csrf_token: str, ritme: str) -> str:
    from nooch_village import founder_taken

    items = founder_taken.wachtrij(st, data_dir, taak, labels)
    cap = int(cfg.get("dag_cap", 5)) if ritme == "dag" else len(items)
    getoond, rest = items[:cap], max(0, len(items) - cap)

    kaarten = ""
    for it in getoond:
        audit = ff.in_auditsteekproef(taak, it["item"], cfg.get("audit_pct", 0))
        kaarten += _itemkaart(taak, it, niveau, audit, csrf_token, ritme)
    if not getoond:
        kaarten = "<p class='muted'>Nothing waiting.</p>"
    staart = (f"<p class='muted'>{rest} more waiting — the weekly round shows them all.</p>"
              if rest else "")

    run = ""
    if niveau in ("C", "D") and items and csrf_token:
        run = (f"<form method='post' action='/action'>"
               f"{_hidden(csrf_token, ritme, taak=taak)}"
               f"<button class='btn sm' type='submit' name='action' value='ff_run'>"
               f"let the AI work through the queue</button></form>")

    return (f"<div class='c2-sec'><h3>{_e(ff.TAAK_LABEL[taak])}</h3>"
            f"{_meterkaart(data_dir, taak, niveau, labels, cfg, csrf_token, ritme)}"
            f"{run}{kaarten}{staart}</div>"
            f"{_ai_gedaan(labels, taak, niveau, csrf_token, ritme)}")


# ── De pagina ────────────────────────────────────────────────────────────────

def render_founder_flow(st, data_dir: str, *, csrf_token: str = "", msg: str = "",
                        ritme: str = "dag", onthuld: str = "") -> str:
    ritme = ritme if ritme in RITMES else "dag"
    niveaus = ff.NiveauStore(f"{data_dir}/{ff.NIVEAU_BESTAND}")
    labels = ff.alle(data_dir)
    cfg = ff.instellingen(data_dir)

    picker = "".join(
        f"<a class='cl-filter{' on' if r == ritme else ''}' href='/founder?ritme={r}'>"
        f"{_e(_RITME_LABEL[r])}</a>" for r in RITMES)

    secties = "".join(
        _taaksectie(st, data_dir, taak, niveaus.niveau(taak), labels, cfg[taak], csrf_token, ritme)
        for taak in ff.TAKEN)

    main = (
        f"<div class='c2-main'><div class='c2-bar'><a href='/admin'>← people</a></div>"
        f"<h1>Founder Flow <span class='chip'>training loop</span></h1>"
        f"{_banner(msg)}"
        f"<p class='muted'>Every decision here becomes a labelled example. Each task climbs "
        f"A → B → C → D on its own, and only when the measured agreement between the AI's "
        f"proposal and your judgement clears the bar on a held-out sample.</p>"
        f"<div class='cl-bar'>Rhythm: {picker}</div>"
        f"{_onthulling(onthuld, csrf_token, ritme)}"
        f"{secties}</div>")
    return _page("Founder Flow", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
