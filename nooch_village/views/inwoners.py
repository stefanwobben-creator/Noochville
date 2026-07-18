"""Inwoner-dossiers — de persona als dragend object.

De scheidslijn die dit scherm zichtbaar maakt: de **rol** is het mandaat (purpose,
accountabilities, domeinen — alleen te wijzigen via governance), de **persona** is de drager
(karakter, capaciteit, gereedschap, modelvoorkeur — die reist mee bij een zetelwissel). Dit
scherm toont en bewerkt uitsluitend de drager; het mandaat staat er alleen als verwijzing bij,
met een link naar de rol-pagina waar governance het beheert.

Vormgeving: het prototype (`docs/prototype_persona_*.html`) was de referentie, maar het
designsysteem wint. De pariteitstabel staat in de PR; één nieuwe klasse (`.avatar`) is bewust
toegevoegd, de rest is hergebruik.
"""
from __future__ import annotations

from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.skill_labels import label as skill_label
from nooch_village.web_base import _banner, _e, _field, _page

# Rangschikking van het dossier: welke secties in welke kolom. Smal links (identiteit en
# instellingen), breed rechts (wat hij kan en doet) — zoals het prototype.
_MBTI_HINT = "vier letters, bv. ISTP"


def zetels_van(st, persona_id: str) -> list:
    """Alle rollen die deze persona vervult.

    Leest bewust BEIDE lagen: de assignments-store én het legacy `persona_id`-veld op het
    record. `assignments.roles_of` kent alleen de eerste; een persona die via de CLI is
    gekoppeld zou dan geen enkele zetel tonen."""
    uit = []
    for rec in st.records.all():
        if getattr(rec, "archived", False):
            continue
        try:
            fillers = st.assign.fillers_of(rec.id, record=rec)
        except Exception:
            fillers = []
        if any(getattr(f, "type", None) == "persona" and f.id == persona_id for f in fillers):
            uit.append(rec)
    return uit


def _avatar(persona) -> str:
    return f"<span class='avatar'>{_e(persona.avatar or '🙂')}</span>"


def _status(st, persona, zetels: list) -> tuple[str, str]:
    """(chip-klasse, label). Motor = geen LLM-inwoner; concept = nog niets ingevuld;
    actief = heeft een zetel én een karakter."""
    if getattr(persona, "kind", "ai") == "motor":
        return "chip outline", "motor"
    if not (persona.mbti or persona.instructions or persona.prompt_extra):
        return "chip muted", "concept"
    return ("chip", "actief") if zetels else ("chip amber", "zonder zetel")


# ── /inwoners — de index ────────────────────────────────────────────────────

def render_inwoners(st, msg: str = "") -> str:
    """Alle inwoners op een rij. Bewust ZONDER prijzen of pakket-kolom: dat is de externe
    catalogus, een ander gesprek dan 'wie woont hier en wat doet hij'."""
    rijen = ""
    for p in st.personas.all():
        zetels = zetels_van(st, p.id)
        cls, stat = _status(st, p, zetels)
        zetel_tekst = ", ".join(_e(_rolnaam(r)) for r in zetels) or "<span class='muted'>—</span>"
        rijen += (f"<tr><td>{_avatar(p)} <a href='/inwoner?id={_e(p.id)}'><b>{_e(p.name)}</b></a></td>"
                  f"<td>{_e(p.mbti) or '<span class=muted>—</span>'}</td>"
                  f"<td>{zetel_tekst}</td>"
                  f"<td><span class='{cls}'>{_e(stat)}</span></td>"
                  f"<td class='num'>{len(p.skills or [])}</td></tr>")
    tabel = (f"<table class='mtab'><tr><th>Inwoner</th><th>MBTI</th><th>Zetel(s)</th>"
             f"<th>Status</th><th class='num'>Skills</th></tr>{rijen}</table>")
    main = (f"<div class='c2-main'><h1>Inwoners van NoochVille</h1>"
            f"<p class='muted'>De persona draagt karakter, capaciteit en gereedschap. Het mandaat "
            f"(purpose, accountabilities, domeinen) hoort bij de rol en loopt via governance.</p>"
            f"{_banner(msg)}<div class='card'>{tabel}</div></div>")
    return _page("Inwoners", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")


def _rolnaam(rec) -> str:
    naam = getattr(getattr(rec, "definition", None), "name", "") or ""
    return naam or str(getattr(rec, "id", "")).split("__")[-1]


# ── /inwoner — het dossier ──────────────────────────────────────────────────

def render_inwoner(st, persona_id: str, csrf_token: str = "", msg: str = "",
                   voorstellen: list | None = None) -> str:
    persona = st.personas.get(persona_id)
    if persona is None:
        inner = (f"{_DS_LINK}{_nav()}<div class='c2-wrap'><div class='c2-main'><h1>Inwoner</h1>"
                 f"<div class='card'><p>Deze inwoner bestaat niet (meer).</p>"
                 f"<p><a href='/inwoners'>← alle inwoners</a></p></div></div></div>")
        return _page("Inwoner", inner)

    zetels = zetels_van(st, persona.id)
    cls, stat = _status(st, persona, zetels)
    kan_bewerken = bool(csrf_token)

    links = (_personality(persona, csrf_token, kan_bewerken, voorstellen or [])
             + (_llm_blok(st, persona, csrf_token, kan_bewerken)
                if getattr(persona, "kind", "ai") != "motor" else _motor_blok()))
    rechts = (_skills_blok(persona) + _tools_blok(persona) + _zetels_blok(st, persona, zetels)
              + _activiteit_blok(st, persona, zetels))

    kop = (f"<h1>{_avatar(persona)} {_e(persona.name)} "
           f"<span class='chip outline'>{_e(persona.mbti or '—')}</span> "
           f"<span class='{cls}'>{_e(stat)}</span></h1>"
           f"<p class='muted'><a href='/inwoners'>← Inwoners</a> · de persona draagt karakter, "
           f"capaciteit en gereedschap; het mandaat hoort bij de rol.</p>")
    main = (f"<div class='c2-main'>{kop}{_banner(msg)}"
            f"<div class='pgrid rov-grid'><div>{links}</div><div>{rechts}</div></div></div>")
    return _page(f"Inwoner — {persona.name}", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")


def _personality(persona, csrf_token: str, kan_bewerken: bool, voorstellen: list) -> str:
    lees = (f"<dl class='dcol'><dt class='muted'>MBTI</dt><dd>{_e(persona.mbti or '—')}</dd>"
            f"<dt class='muted'>Instructies</dt><dd>{_e(persona.instructions or '—')}</dd>"
            f"<dt class='muted'>Prompt-extra</dt><dd>{_e(persona.prompt_extra or '—')}</dd></dl>")
    if not kan_bewerken:
        return f"<div class='card'><h3>Personality</h3>{lees}</div>"
    form = (f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='/inwoner?id={_e(persona.id)}'>"
            f"<input type='hidden' name='pid' value='{_e(persona.id)}'>"
            f"{_field('Avatar (emoji)', 'avatar', value=persona.avatar, fid='f-inw-avatar')}"
            f"{_field('MBTI', 'mbti', value=persona.mbti, fid='f-inw-mbti', placeholder=_MBTI_HINT)}"
            f"{_field('Instructies', 'instructions', kind='textarea', value=persona.instructions, fid='f-inw-instr')}"
            f"{_field('Prompt-extra', 'prompt_extra', kind='textarea', value=persona.prompt_extra, fid='f-inw-extra')}"
            f"<div class='qadd-row'><button class='btn ok' name='action' value='persona_edit'>"
            f"Opslaan</button></div></form>")
    return (f"<div class='card'><h3>Personality</h3>{form}"
            f"{_finetune(persona, csrf_token, voorstellen)}</div>")


def _finetune(persona, csrf_token: str, voorstellen: list) -> str:
    """✨ Finetune met AI — de AI stelt voor, de mens kiest.

    Mens-gated per ontwerp: er wordt nooit iets overschreven zonder dat iemand een knop indrukt,
    en er is altijd een 'huidig'-optie zodat 'niets veranderen' een even makkelijke keuze is als
    de andere twee."""
    opties = [("huidig", persona.prompt_extra or "(nu leeg)")] + [
        (v.get("naam", "variant"), v.get("tekst", "")) for v in voorstellen]
    if len(opties) == 1:
        knop = (f"<form method='post' action='/action' class='qadd-row'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='next' value='/inwoner?id={_e(persona.id)}'>"
                f"<input type='hidden' name='pid' value='{_e(persona.id)}'>"
                f"<button class='btn sm' name='action' value='persona_finetune'>"
                f"✨ Finetune met AI</button></form>")
        return (f"<div class='c2-sec'><h3>✨ Finetune met AI</h3>"
                f"<p class='muted'>De AI stelt twee alternatieven voor je prompt-extra voor "
                f"— strakker en ruimer. Jij kiest.</p>{knop}</div>")
    rijen = ""
    for i, (naam, tekst) in enumerate(opties):
        fid = f"f-ft-{i}"
        rijen += (f"<div class='rdr-row'>"
                  f"<input type='radio' id='{fid}' name='keuze' value='{_e(tekst)}'"
                  f"{' checked' if i == 0 else ''}>"
                  f"<label for='{fid}'><b>{_e(naam)}</b>"
                  f"<div class='muted'>{_e(tekst)}</div></label></div>")
    return (f"<div class='c2-sec'><h3>✨ Finetune met AI</h3>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='/inwoner?id={_e(persona.id)}'>"
            f"<input type='hidden' name='pid' value='{_e(persona.id)}'>"
            f"{rijen}<div class='qadd-row'>"
            f"<button class='btn ok' name='action' value='persona_finetune_apply'>Gebruik selectie</button>"
            f"<button class='btn sm ghost' name='action' value='persona_finetune'>↻ nieuwe voorstellen</button>"
            f"</div></form></div>")


def _motor_blok() -> str:
    return ("<div class='card'><h3>Geen LLM</h3><p class='muted'>Dit is een motor: hij draait "
            "op regels, niet op een taalmodel. Er is dus geen modelvoorkeur en geen verbruik.</p></div>")


def _llm_blok(st, persona, csrf_token: str, kan_bewerken: bool) -> str:
    """Modelvoorkeur + wat het de afgelopen 14 dagen kostte."""
    from nooch_village.llm_keuze import verbruik
    llm = getattr(persona, "llm", None) or {}
    per_taak = llm.get("per_taak") or {}
    cijfers = verbruik(st.dd, call_sites=set(per_taak) or None)

    rijen = ""
    for site, model in sorted(per_taak.items()):
        vak = cijfers["per_site"].get(site, {})
        bedrag = (f"€ {vak['eur']:.2f}" if vak.get("eur") else
                  ("<span class='muted'>onbekend</span>" if vak.get("onbekend") else "—"))
        rijen += (f"<tr><td>{_e(site)}</td><td><code>{_e(model)}</code></td>"
                  f"<td class='num'>{bedrag}</td></tr>")
    tabel = (f"<table class='mtab'><tr><th>Taak</th><th>Model</th><th class='num'>14d</th></tr>"
             f"{rijen}</table>" if rijen else
             "<p class='muted'>Nog geen voorkeur per taak — alles loopt via de dorpsladder.</p>")

    budget = float((st.settings or {}).get("persona_llm_budget_eur", 5) if hasattr(st, "settings") else 5)
    balk = _budgetbalk(cijfers["totaal_eur"], budget, cijfers["onbekende_calls"])

    beheer = ""
    if kan_bewerken:
        beheer = (f"<form method='post' action='/action' class='qadd-form'>"
                  f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                  f"<input type='hidden' name='next' value='/inwoner?id={_e(persona.id)}'>"
                  f"<input type='hidden' name='pid' value='{_e(persona.id)}'>"
                  f"{_field('Standaardmodel', 'llm_default', value=llm.get('default', ''), fid='f-inw-llm', placeholder='gemini:gemini-2.5-flash-lite')}"
                  f"{_field('Per taak (call_site=model, één per regel)', 'llm_per_taak', kind='textarea', value=_pertaak_tekst(per_taak), fid='f-inw-pertaak')}"
                  f"<div class='qadd-row'><button class='btn ok' name='action' value='persona_llm'>"
                  f"Opslaan</button></div></form>")
    return (f"<div class='card'><h3>LLM-voorkeuren</h3>"
            f"<dl class='dcol'><dt class='muted'>Default</dt>"
            f"<dd>{_model_cel(llm.get('default'))}</dd></dl>"
            f"{tabel}{balk}{beheer}</div>")


def _model_cel(model: str | None) -> str:
    """Het gekozen model, of een expliciete verwijzing naar de dorpsladder — nooit een leeg vakje
    dat lijkt alsof er niets gebeurt."""
    return f"<code>{_e(model)}</code>" if model else "<span class='muted'>dorpsladder</span>"


def _pertaak_tekst(per_taak: dict) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(per_taak.items()))


def _budgetbalk(besteed: float, budget: float, onbekend: int) -> str:
    """Visueel signaal, geen rem. En eerlijk over wat er niet in zit."""
    pct = min(100, int((besteed / budget) * 100)) if budget else 0
    staart = (f" · {onbekend} call(s) op een trede zonder bekende prijs — niet meegeteld"
              if onbekend else "")
    return (f"<div class='c2-sec'><div class='muted'>LLM-verbruik 14 dagen · "
            f"€ {besteed:.2f} van € {budget:.2f} budget{_e(staart)}</div>"
            f"<span class='bar-t'><span class='bar-f bar-w{pct // 10}'></span></span></div>")


def _skills_blok(persona) -> str:
    """Wat deze inwoner kan, in mensentaal. Het technische id staat eronder — de brug tussen
    het dossier en de code blijft zichtbaar."""
    if not (persona.skills or []):
        return ("<div class='card'><h3>Skills</h3><p class='muted'>Nog geen capaciteit "
                "vastgelegd.</p></div>")
    rijen = "".join(
        f"<div class='rdr-row'><div><b>{_e(skill_label(s))}</b>"
        f"<div class='muted'><code>{_e(s)}</code></div></div></div>"
        for s in persona.skills)
    return (f"<div class='card'><h3>Skills <span class='muted'>— wat {_e(persona.name.split()[0])} "
            f"kan (reist mee naar elke zetel)</span></h3>{rijen}"
            f"<p class='muted'>Uitvoering loopt in deze fase nog op de rol-DNA; dit is het "
            f"dossier en het pakket-manifest.</p></div>")


def _tools_blok(persona) -> str:
    tools = getattr(persona, "tools", None) or []
    if not tools:
        return ""
    kaarten = "".join(
        f"<a class='card' href='{_e(t.get('href', '#'))}'><b>🛠 {_e(t.get('label', ''))}</b>"
        f"<div class='muted'>{_e(t.get('desc', ''))}</div></a>" for t in tools)
    return (f"<div class='card'><h3>Tools</h3><div class='tile-grid'>{kaarten}</div>"
            f"<p class='muted'>Tool-schermen horen bij de inwoner: download je het pakket, dan "
            f"krijg je deze schermen erbij.</p></div>")


def _zetels_blok(st, persona, zetels: list) -> str:
    if not zetels:
        return ("<div class='card'><h3>Zetels</h3><p class='muted'>Deze inwoner vervult nu geen "
                "rol.</p></div>")
    blokken = ""
    for i, rec in enumerate(zetels):
        dna = getattr(rec, "definition", None)
        vereist = list(getattr(dna, "skills", []) or [])
        heeft = set(persona.skills or [])
        dekking = "".join(
            (f"<span class='chip'>✓ {_e(s)}</span> " if s in heeft
             else f"<span class='chip coral'>✗ {_e(s)}</span> ") for s in vereist)
        blokken += (f"<details class='c2-hist'{' open' if i == 0 else ''}>"
                    f"<summary><b>🪑 {_e(_rolnaam(rec))}</b> <span class='chip outline'>rol</span></summary>"
                    f"<div class='muted'>Purpose: {_e(getattr(dna, 'purpose', '') or '—')}</div>"
                    f"<div class='c2-sec'>Vereist door de rol → gedekt: {dekking or '—'}</div>"
                    f"<div class='c2-sec'><a class='btn sm' href='/node?id={_e(rec.id)}'>"
                    f"→ naar de rol-pagina</a></div></details>")
    return (f"<div class='card'><h3>Zetels</h3>{blokken}"
            f"<p class='muted'>De rol houdt het mandaat (via governance). De inwoner neemt "
            f"skills en toon mee bij een zetelwissel.</p></div>")


def _activiteit_blok(st, persona, zetels: list) -> str:
    """De laatste gebeurtenissen van deze inwoner, uit de audit-trail.

    Eerlijk over de bron: system_log heeft geen tijdstempel op de bus-events, dus dit is de
    laatste N regels in bestandsvolgorde, niet 'de laatste N minuten'. Wat klikbaar kan zijn,
    is klikbaar; de rest blijft tekst in plaats van een dode link."""
    from nooch_village.activiteit import laatste_events
    rol_ids = {r.id for r in zetels}
    aantal = int((getattr(st, "settings", None) or {}).get("persona_activity_tail", 10) or 10)
    events = laatste_events(st.dd, rol_ids, aantal)
    if not events:
        return ("<div class='card'><h3>Recente activiteit</h3>"
                "<p class='muted'>Nog niets vastgelegd voor deze zetels.</p></div>")
    rijen = ""
    for e in events:
        doel = (f"<a href='/node?id={_e(e['link'])}'>{_e(e['link_label'])}</a>"
                if e.get("link") else f"<span class='muted'>{_e(e.get('detail', ''))}</span>")
        rijen += (f"<tr><td class='muted'>{_e(e['rol'])}</td><td>{_e(e['event'])}</td>"
                  f"<td>{doel}</td></tr>")
    return (f"<div class='card'><h3>Recente activiteit</h3>"
            f"<table class='mtab'><tr><th>Rol</th><th>Wat</th><th>Waarheen</th></tr>{rijen}</table>"
            f"<p class='muted'>Laatste {len(events)} regels uit de audit-trail, in "
            f"bestandsvolgorde — de bus-events dragen geen tijdstempel.</p></div>")
