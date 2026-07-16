"""Kennisbank — "Wat Nooch weet": geversioneerde inzichten boven de atomen (fase 1).

UI-referentie: het prototype nooch-kb (drawer-gedrag, woord + 4-punts meter + één zin).
Server-rendered zonder JS: het detail opent als drawer via ?id=<inzicht> (de open-staat
is een URL, geen client-state); sluiten = terug naar /kennisbank. De machinerie
(percentages, trust, groepen) blijft binnen — de gebruiker ziet alleen het eindwoord.

Hergebruik: web_base (_e/_page/_field/_banner), cockpit2_util (_DS_LINK/_BUILD),
kern-klassen (.card/.btn/.chip/.muted) + de kn-*-familie in static/nooch.css (drawer,
meter, noten, koppel-paneel — expliciet vocabulaire-besluit, zie tests/test_ui_ratchets).
"""
from __future__ import annotations

import re

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _BUILD
from nooch_village.kennisbank import (field, verdict, WORD_LABEL, load_atoms,
                                      bouw_spel_prompt)


def _dots(word: str, n: int) -> str:
    balls = "".join(f"<span class='{'' if i < n else 'o'}'>●</span>" for i in range(4))
    return f"<span class='kn-dots {_e(word)}'>{balls}</span>"


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _topic_card(ins: dict, atoms: dict) -> str:
    v = verdict(field(ins.get("evidence") or [], atoms))
    word = v["word"]
    subject = ins.get("subject") or ""
    chip = f"<span class='chip outline'>{_e(subject)}</span>" if subject else ""
    return (
        f"<a class='card kn-topic' href='/kennisbank?id={_e(ins['id'])}'>"
        f"<div class='kn-thead'><div class='kn-tmain'>"
        f"<div class='kn-ttitle'>{_e(ins.get('title'))}"
        f"<span class='badge ro'>v{_e(ins.get('version') or '1.0')}</span></div>"
        f"<div class='kn-twhy'>{_e(ins.get('why'))} {chip}</div></div>"
        f"<div class='kn-conf'><span class='kn-word {_e(word)}'>{_e(WORD_LABEL[word])}</span>"
        f"{_dots(word, v['dots'])}</div><span class='kn-arrow'>›</span></div></a>")


def _atom_zoek(atoms: dict, ins: dict, q: str, limit: int = 6) -> list[tuple[str, dict]]:
    """De recall-oprit (fase 1, zonder LLM): rangschik ongelinkte atomen op woord-overlap met
    de zoekterm (of met de claim van het inzicht als er geen zoekterm is). Precisie blijft
    bij de mens: insluiten + richting kiezen gebeurt in het paneel."""
    gelinkt = {l.get("atom_id") for l in (ins.get("evidence") or [])}
    tekst = q or f"{ins.get('title', '')} {ins.get('why', '')}"
    toks = {w for w in re.split(r"[^a-z0-9]+", tekst.lower()) if len(w) > 3}
    scored = []
    for aid, a in atoms.items():
        if aid in gelinkt or not a.get("claim"):
            continue
        hay = f"{a.get('claim', '')} {a.get('source', '')}".lower()
        s = sum(1 for w in toks if w in hay)
        if q:                                  # expliciet zoeken: alleen echte matches
            if s > 0:
                scored.append((s, aid, a))
        elif s > 0:
            scored.append((s, aid, a))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [(aid, a) for _, aid, a in scored[:limit]]


def _note_html(ins: dict, link: dict, atom: dict | None, csrf: str, nxt: str) -> str:
    stance = link.get("stance") or "support"
    claim = (atom or {}).get("claim") or f"(kaart {link.get('atom_id')} niet gevonden)"
    src = (atom or {}).get("source") or ""
    ann = link.get("annotation") or ""
    aid = link.get("atom_id") or ""
    ann_html = f"<span class='kn-ann'>notitie: {_e(ann)}</span>" if ann else ""
    prefix = "tegen · " if stance == "counter" else ""
    ctrl = (
        f"<details class='kn-nctrl'><summary title='notitie bij dit bewijs'>💬</summary>"
        f"<form method='post' action='/action'>"
        f"{_hid(csrf, 'kb_annotate', nxt, {'iid': ins['id'], 'atom_id': aid})}"
        f"{_field('notitie bij dit bewijs', 'text', value=ann, fid=f'f-ann-{aid}')}"
        f"<button class='btn'>bewaar</button></form></details>"
        f"<form method='post' action='/action' class='kn-unlink'>"
        f"{_hid(csrf, 'kb_unlink', nxt, {'iid': ins['id'], 'atom_id': aid})}"
        f"<button class='btn' title='loskoppelen (kaart blijft in de bibliotheek)'>×</button></form>")
    return (f"<div class='kn-note {_e(stance)}'><span class='kn-dot'></span>"
            f"<div class='kn-ntext'>{_e(claim)}"
            f"<span class='kn-src'>{_e(prefix)}{_e(src)}</span>{ann_html}</div>"
            f"<div class='kn-nctrls'>{ctrl}</div></div>")


def _koppel_paneel(ins: dict, atoms: dict, q: str, csrf: str, nxt: str) -> str:
    kandidaten = _atom_zoek(atoms, ins, q)
    rows = ""
    for aid, a in kandidaten:
        rows += (
            f"<form method='post' action='/action' class='kn-lrow'>"
            f"{_hid(csrf, 'kb_link', nxt, {'iid': ins['id'], 'atom_id': aid})}"
            f"<div class='kn-lt'>{_e(a.get('claim'))}"
            f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}</span></div>"
            f"<select name='stance'><option value='support'>steunt</option>"
            f"<option value='counter'>spreekt tegen</option></select>"
            f"<input name='annotation' placeholder='waarom? (optioneel)'>"
            f"<button class='btn ok'>koppel</button></form>")
    if not rows:
        rows = ("<p class='muted'>Geen kandidaten gevonden. Zoek hierboven op een woord, "
                "of voeg nieuw bewijs toe.</p>")
    zoek = (f"<form method='get' action='/kennisbank' class='kn-zoek'>"
            f"<input type='hidden' name='id' value='{_e(ins['id'])}'>"
            f"{_field('zoek in de bibliotheek', 'q', value=q, fid='f-kn-q')}"
            f"<button class='btn'>zoek</button></form>")
    return (f"<details class='kn-panel' {'open' if q else ''}>"
            f"<summary>🔗 koppel kaarten uit de bibliotheek</summary>"
            f"<p class='muted'>Het systeem vond deze kaarten. Een kale koppel volstaat; "
            f"de richting kun je per kaart kiezen.</p>{zoek}{rows}</details>")


def _drawer(ins: dict, atoms: dict, q: str, csrf: str) -> str:
    nxt = f"/kennisbank?id={ins['id']}"
    v = verdict(field(ins.get("evidence") or [], atoms))
    word = v["word"]
    sup = [l for l in ins.get("evidence") or [] if l.get("stance") == "support"]
    cou = [l for l in ins.get("evidence") or [] if l.get("stance") == "counter"]
    noten_sup = "".join(_note_html(ins, l, atoms.get(l.get("atom_id") or ""), csrf, nxt)
                        for l in sup) or "<p class='muted'>Nog geen bewijs.</p>"
    noten_cou = "".join(_note_html(ins, l, atoms.get(l.get("atom_id") or ""), csrf, nxt)
                        for l in cou)
    caveat = (f"<div class='kn-caveat'>⚠ {_e(ins.get('caveat'))}</div>"
              if ins.get("caveat") else "")

    nieuw = (
        f"<details class='kn-panel'><summary>+ nieuw bewijs of reactie</summary>"
        f"<p class='muted'>Een reactie is óók een notitie — jij bent ook een bron "
        f"(herkomst: intern oordeel).</p>"
        f"<form method='post' action='/action'>"
        f"{_hid(csrf, 'kb_evidence', nxt, {'iid': ins['id']})}"
        f"{_field('wat wijst hierheen (of ertegen)?', 'text', kind='textarea', fid='f-kn-ev')}"
        f"{_field('bron (een studie, artikel, of jouw naam)', 'source', fid='f-kn-src')}"
        f"<label class='att-lbl' for='f-kn-stance'>richting</label>"
        f"<select id='f-kn-stance' name='stance'><option value='support'>steunt</option>"
        f"<option value='counter'>spreekt tegen</option></select> "
        f"<button class='btn ok'>toevoegen</button></form></details>")

    spel_rows = [{"claim": (atoms.get(l.get("atom_id") or "") or {}).get("claim", ""),
                  "stance": l.get("stance")} for l in ins.get("evidence") or []]
    prompt = bouw_spel_prompt(ins.get("title", ""), spel_rows)
    herformuleer = (
        f"<details class='kn-panel'><summary>↻ herformuleer (speel opnieuw)</summary>"
        f"<p class='muted'>1 · Kopieer de prompt naar je AI en voer de dialoog. "
        f"2 · Plak het === INZICHT ===-blok terug. De vorige versie blijft bewaard.</p>"
        f"<textarea class='kn-prompt' readonly rows='8'>{_e(prompt)}</textarea>"
        f"<form method='post' action='/action'>"
        f"{_hid(csrf, 'kb_reformulate', nxt, {'iid': ins['id']})}"
        f"{_field('plak hier het === INZICHT ===-blok', 'blok', kind='textarea', fid='f-kn-blok')}"
        f"<button class='btn ok'>nieuwe versie maken →</button></form></details>")

    gesprek = "".join(
        f"<div class='kn-comment'>{_e(d.get('text'))}"
        f"<span class='kn-by'>— {_e(d.get('by'))}</span></div>"
        for d in ins.get("discussion") or []) or (
        "<p class='muted'>Nog geen kanttekeningen. Dit is de plek voor opmerkingen "
        "over het inzicht als geheel.</p>")
    gesprek += (f"<form method='post' action='/action' class='kn-discrow'>"
                f"{_hid(csrf, 'kb_discuss', nxt, {'iid': ins['id']})}"
                f"{_field('plaats een kanttekening over dit inzicht', 'text', fid='f-kn-disc')}"
                f"<button class='btn'>plaats</button></form>")

    historie = ""
    if ins.get("history"):
        rows = "".join(f"<div class='muted'>v{_e(h.get('version'))} · {_e(h.get('title'))} "
                       f"<span class='kn-src'>({_e((h.get('at') or '')[:10])})</span></div>"
                       for h in reversed(ins["history"]))
        historie = (f"<details class='kn-panel'><summary>eerdere versies "
                    f"({len(ins['history'])})</summary>{rows}</details>")

    andere_kant = (f"<div class='kn-sec'><div class='kn-sectitle'>De andere kant</div>"
                   f"<div class='kn-other'>{_e(ins.get('reframe'))}</div></div>"
                   if ins.get("reframe") else "")
    falsi = (f"<div class='kn-sec'><div class='kn-sectitle'>Wat zou dit onderuit halen?</div>"
             f"<div class='kn-falsi'>{_e(ins.get('falsifier'))}</div></div>"
             if ins.get("falsifier") else "")

    return (
        f"<a class='kn-scrim' href='/kennisbank' aria-label='sluiten'></a>"
        f"<div class='kn-drawer' role='dialog' aria-label='{_e(ins.get('title'))}'>"
        f"<a class='kn-x' href='/kennisbank'>×</a>"
        f"<div class='kn-claim'>{_e(ins.get('title'))}"
        f"<span class='badge ro'>v{_e(ins.get('version') or '1.0')}</span></div>"
        f"<div class='kn-conf'><span class='kn-word {_e(word)}'>{_e(WORD_LABEL[word])}</span>"
        f"{_dots(word, v['dots'])}</div>"
        f"<div class='kn-sentence'>{v['sentence']}</div>{caveat}"
        f"<div class='kn-sec'><div class='kn-sectitle'>Het bewijs</div>{noten_sup}"
        + (f"<div class='kn-sectitle'>Tegenspraak</div>{noten_cou}" if noten_cou else "")
        + f"{_koppel_paneel(ins, atoms, q, csrf, nxt)}{nieuw}{herformuleer}</div>"
        f"{andere_kant}{falsi}"
        f"<div class='kn-sec'><div class='kn-sectitle'>Gesprek</div>{gesprek}</div>"
        f"{historie}</div>")


def render_kennisbank(st, kid: str = "", q: str = "", csrf_token: str = "",
                      msg: str = "") -> str:
    atoms = load_atoms(st.dd)
    inzichten = st.kennisbank.all()
    cards = "".join(_topic_card(i, atoms) for i in inzichten) or (
        "<p class='muted'>Nog geen inzichten. Maak er een met \"+ leeg inzicht\", of seed "
        "de eerste vulling: <code>python -m nooch_village.kennisbank_seed --apply</code></p>")

    nieuw_form = (
        f"<details class='kn-panel'><summary>+ leeg inzicht</summary>"
        f"<form method='post' action='/action'>"
        f"{_hid(csrf_token, 'kb_new', '/kennisbank')}"
        f"{_field('de claim (mensentaal, kort)', 'title', fid='f-kn-title', required=True)}"
        f"{_field('waarom denk je dit? (één zin, optioneel)', 'why', fid='f-kn-why')}"
        f"<button class='btn ok'>maak inzicht</button>"
        f"<span class='muted'> — groeit van \"nog dun\" naar \"stevig\" door bewijs te koppelen</span>"
        f"</form></details>")

    capture = ("<div class='card kn-capture'>"
               "<p class='muted'>Noteer iets… een idee, een artikel, een cijfer. "
               "We splitsen het in losse notities en hangen ze op de juiste plek. "
               "<span class='chip outline'>komt in fase 2 — de intake via de LLM-ladder</span></p></div>")

    drawer = ""
    if kid:
        ins = st.kennisbank.get(kid)
        if ins is not None:
            drawer = _drawer(ins, atoms, q, csrf_token)

    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>🌱 Wat Nooch weet</h1>"
            f"<p class='muted'>Alles wat binnenkomt wordt kleine notities. Hieronder zie je wat "
            f"we daaruit leren en hoe zeker we zijn. Tik een inzicht open om het bewijs te zien, "
            f"kaarten te koppelen en er iets aan toe te voegen.</p>"
            f"{_banner(msg)}{capture}"
            f"<h2>Onze inzichten</h2>{nieuw_form}{cards}"
            f"<p class='muted'>Elke zekerheid schuift mee als er info bijkomt.</p></div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/signals'>signalen</a> · "
             "<a href='/inzichten'>kennislaag</a></div>"
             f"<div class='c2-wrap'>{main}</div>{drawer}")
    return _page("Wat Nooch weet", inner)
