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
from nooch_village.kennisbank import field, verdict, WORD_LABEL, load_atoms
from nooch_village.kennisbank_intake import SUBJECTS
from nooch_village.kennisbank_spel import clusters as kb_clusters, gather, subject_van


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
        f"<button class='btn'>Bewaar</button></form></details>"
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
            f"<button class='btn ok'>Koppel</button></form>")
    if not rows:
        rows = ("<p class='muted'>Geen kandidaten gevonden. Zoek hierboven op een woord, "
                "of voeg nieuw bewijs toe.</p>")
    zoek = (f"<form method='get' action='/kennisbank' class='kn-zoek'>"
            f"<input type='hidden' name='id' value='{_e(ins['id'])}'>"
            f"{_field('zoek in de bibliotheek', 'q', value=q, fid='f-kn-q')}"
            f"<button class='btn'>Zoek kaarten</button></form>")
    return (f"<details class='kn-panel' {'open' if q else ''}>"
            f"<summary>🔗 Koppel kaarten uit de bibliotheek</summary>"
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
        f"<details class='kn-panel'><summary>+ Voeg bewijs of een reactie toe</summary>"
        f"<p class='muted'>Een reactie is óók een notitie — jij bent ook een bron "
        f"(herkomst: intern oordeel).</p>"
        f"<form method='post' action='/action'>"
        f"{_hid(csrf, 'kb_evidence', nxt, {'iid': ins['id']})}"
        f"{_field('wat wijst hierheen (of ertegen)?', 'text', kind='textarea', fid='f-kn-ev')}"
        f"{_field('bron (een studie, artikel, of jouw naam)', 'source', fid='f-kn-src')}"
        f"<label class='att-lbl' for='f-kn-stance'>richting</label>"
        f"<select id='f-kn-stance' name='stance'><option value='support'>steunt</option>"
        f"<option value='counter'>spreekt tegen</option></select> "
        f"<button class='btn ok'>Voeg toe</button></form></details>")

    # Herformuleren = een nieuw spel, geseed met de huidige evidence-set. Het spel zelf
    # is copy-paste (speel in je eigen AI); de losse prompt/plak-fallback die hier stond
    # is daarmee overbodig — één route, geen dubbele UI.
    spel_kaarten = "".join(
        f"<input type='hidden' name='kaart' value='{_e(l['atom_id'])}'>"
        f"<input type='hidden' name='stance_{_e(l['atom_id'])}' value='{_e(l.get('stance') or 'support')}'>"
        for l in ins.get("evidence") or [])
    herformuleer = (
        f"<form method='post' action='/action' class='kn-panel'>"
        f"{_hid(csrf, 'kb_spel_start', nxt, {'reformulate_of': ins['id'], 'hunch': ins.get('title') or ''})}"
        f"{spel_kaarten}<button class='btn'>↻ Speel opnieuw</button> "
        f"<span class='muted'>scherp de claim aan in je eigen AI; het eindigt in een "
        f"nieuwe versie en de vorige blijft bewaard</span></form>")

    gesprek = "".join(
        f"<div class='kn-comment'>{_e(d.get('text'))}"
        f"<span class='kn-by'>— {_e(d.get('by'))}</span></div>"
        for d in ins.get("discussion") or []) or (
        "<p class='muted'>Nog geen kanttekeningen. Dit is de plek voor opmerkingen "
        "over het inzicht als geheel.</p>")
    gesprek += (f"<form method='post' action='/action' class='kn-discrow'>"
                f"{_hid(csrf, 'kb_discuss', nxt, {'iid': ins['id']})}"
                f"{_field('plaats een kanttekening over dit inzicht', 'text', fid='f-kn-disc')}"
                f"<button class='btn'>Plaats</button></form>")

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


def _atoom_regel(aid: str, a: dict, selecteerbaar: bool = False) -> str:
    """Eén atoom compact: inhoud + onderwerp + bron (+ body-uitklap voor een samengestelde
    kaart, + optionele selectie-checkbox voor curatie). Geen trust, geen machinerie."""
    hub = subject_van(a)
    chip = f"<span class='chip outline'>{_e(hub)}</span>" if hub else ""
    vlag = (" <span class='chip muted'>verificatie vereist</span>"
            if "verificatie_vereist" in (a.get("tags") or []) else "")
    if a.get("merged_from"):
        chip += f" <span class='chip muted'>samengesteld uit {len(a['merged_from'])}</span>"
    body = ""
    if (a.get("body") or "").strip():
        body_html = _e(a["body"]).replace("\n", "<br>")
        body = (f"<details class='kn-nctrl'><summary>toon de inhoud</summary>"
                f"<div class='kn-ann'>{body_html}</div></details>")
    ref = f" · {_e(a['reference'])}" if a.get("reference") else ""
    vink = (f"<input type='checkbox' name='atoom' value='{_e(aid)}' "
            f"aria-label='selecteer notitie'>" if selecteerbaar else "")
    return (f"<div class='kn-note support'>{vink}<span class='kn-dot'></span>"
            f"<div class='kn-ntext'>{_e(a.get('claim'))}{vlag} {chip}"
            f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}{ref}</span>"
            f"{body}</div></div>")


def _actiebalk(open_: str, st, atoms: dict, inzichten: list, hunch: str, speel: str,
               cluster: int, csrf: str) -> str:
    """Zone 1 — de compacte, sticky actiebalk met twee accordions (open-staat via ?open=).
    Laag als beide dicht zijn; klapt één zone open zonder de pagina te verspringen."""
    bron_open = open_ == "bron"
    speel_open = open_ == "speel"
    knoppen = (f"<div class='kn-actiebtns'>"
               f"<a class='btn{' ok' if bron_open else ''}' "
               f"href='/kennisbank{'' if bron_open else '?open=bron'}'>➕ Bron toevoegen</a>"
               f"<a class='btn{' ok' if speel_open else ''}' "
               f"href='/kennisbank{'' if speel_open else '?open=speel'}'>🎲 Speel een inzicht</a></div>")
    paneel = ""
    if bron_open:
        paneel = f"<div class='card kn-capture'>{_bron_toevoegen(csrf)}</div>"
    elif speel_open:
        paneel = f"<div class='card kn-capture'>{_speel_toevoegen(st, atoms, inzichten, hunch, speel, cluster, csrf)}</div>"
    return f"<div class='kn-actiebalk'>{knoppen}{paneel}</div>"


def _bron_toevoegen(csrf: str) -> str:
    """Zone 2 — één ingang: plakken (tekst/link) OF een bestand. Auto-detectie server-side;
    het resultaat gaat naar de staging-ronde ('even nakijken'), niet meteen de bibliotheek in."""
    return (
        f"<form method='post' action='/action' enctype='multipart/form-data'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
        f"<input type='hidden' name='action' value='kb_bron_add'>"
        f"{_field('plak een notitie, een artikel, of een link (website / Google Sheet)', 'bron_text', kind='textarea', fid='f-bron-text')}"
        + _field("… of kies een bestand (PDF, Excel of CSV)", "file", kind="file",
                 fid="f-bron-file", attrs="accept='.pdf,.xlsx,.xls,.csv'")
        + f"<button class='btn ok'>Verwerk de bron</button>"
        f"<span class='muted'> — we herkennen het type zelf; daarna kijk je de voorstellen "
        f"na vóór ze de bibliotheek in gaan</span></form>")


def _speel_toevoegen(st, atoms: dict, inzichten: list, hunch: str, speel: str,
                     cluster: int, csrf: str) -> str:
    """Zone 3 — een hunch typen OF door de clusters bladeren (één tegelijk, vorige/volgende)."""
    delen = [f"<form method='get' action='/kennisbank' class='kn-zoek'>"
             f"<input type='hidden' name='open' value='speel'>"
             + _field("💡 ik heb een hunch", "hunch", value="" if speel else hunch,
                      fid="f-kn-hunchzoek",
                      placeholder="bijv. wachttijd is juist een feature, geen kost")
             + f"<button class='btn'>Zoek de kaarten</button></form>"]
    cls = kb_clusters(atoms, inzichten)
    if cls:
        i = max(0, min(cluster, len(cls) - 1))
        cl = cls[i]
        ids = ",".join(cl["atom_ids"])
        nav = ""
        if len(cls) > 1:
            prev = f"<a class='btn' href='/kennisbank?open=speel&cluster={i-1}'>← vorige</a> " if i > 0 else ""
            nxt = f"<a class='btn' href='/kennisbank?open=speel&cluster={i+1}'>volgende →</a>" if i < len(cls) - 1 else ""
            nav = f"<span class='muted'>cluster {i+1} van {len(cls)}</span> {prev}{nxt}"
        delen.append(
            f"<div class='kn-cluster'><b>🧩 {_e(cl['theme'])}</b> "
            f"<span class='muted'>· {len(cl['atom_ids'])} kaarten willen een inzicht worden</span><br>"
            f"<a class='btn ok' href='/kennisbank?open=speel&speel={_e(ids)}&hunch={_e(cl['theme'])}'>Speel deze</a> {nav}</div>")
    if speel:
        kandidaten = [{"atom_id": aid, "stance": "support"}
                      for aid in speel.split(",") if aid in atoms]
        delen.append(_curatie_sectie("Je set (draai de richting waar nodig)",
                                     kandidaten, atoms, hunch, csrf))
    elif hunch:
        kandidaten = gather(hunch, atoms)
        delen.append(_curatie_sectie(f"Kaarten bij: “{hunch}”", kandidaten, atoms, hunch, csrf))
    for s in st.spel.open_spellen()[:3]:
        delen.append(f"<p class='muted'>🎲 open spel: <a href='/kennisbank/spel?sid={_e(s['id'])}'>"
                     f"{_e(s.get('hunch') or s['id'])}</a></p>")
    return "".join(delen)


def _nieuw_toast(nieuw: str, atoms: dict) -> str:
    """Na een staging-commit tonen we kort de net toegevoegde atomen (via ?nieuw=)."""
    ids = [i for i in (nieuw or "").split(",") if i and i in atoms]
    if not ids:
        return ""
    rows = "".join(_atoom_regel(aid, atoms[aid]) for aid in ids)
    return (f"<div class='card kn-capture'><div class='kn-sectitle'>Net toegevoegd "
            f"({len(ids)})</div>{rows}</div>")


_PAG = 30


def _bibliotheek_sectie(st, atoms: dict, hub: str, pag: int, csrf: str) -> str:
    """Bladeren door de atomen per onderwerp-hub (taak 4: kalm op volume) + curatie
    (addendum C): selecteer notities en voeg samen, archiveer, of stuur ze naar een
    open spel. Gearchiveerde notities blijven terughaalbaar in hun eigen uitklap."""
    per_hub: dict[str, int] = {}
    for a in atoms.values():
        h = subject_van(a)
        if h and (a.get("claim") or "").strip():
            per_hub[h] = per_hub.get(h, 0) + 1
    if not per_hub:
        return ""
    chips = "".join(
        f"<a class='chip-opt{' on' if hub == h else ''}' "
        f"href='/kennisbank?hub={_e(h)}'>{_e(h)} ({n})</a>"
        for h, n in sorted(per_hub.items(), key=lambda kv: -kv[1]))
    lijst = ""
    if hub:
        rows = sorted(((aid, a) for aid, a in atoms.items() if subject_van(a) == hub),
                      key=lambda t: (t[1].get("created_at") or "", t[0]), reverse=True)
        start = max(0, (pag - 1)) * _PAG
        blad = rows[start:start + _PAG]
        nxt = f"/kennisbank?hub={hub}" + (f"&pag={pag}" if pag > 1 else "")
        regels = "".join(_atoom_regel(aid, a, selecteerbaar=True) for aid, a in blad) or \
            "<p class='muted'>Geen notities op deze pagina.</p>"
        nav = ""
        if start > 0:
            nav += f"<a class='btn' href='/kennisbank?hub={_e(hub)}&pag={pag - 1}'>← Vorige</a> "
        if start + _PAG < len(rows):
            nav += f"<a class='btn' href='/kennisbank?hub={_e(hub)}&pag={pag + 1}'>Volgende →</a>"
        teller = (f"<p class='muted'>{len(rows)} notities in '{_e(hub)}'"
                  + (f" · pagina {pag}" if len(rows) > _PAG else "") + "</p>")
        # Eén form; de drie knoppen kiezen de actie (name='action'). Kale vink volstaat.
        spellen = st.spel.open_spellen()[:8]
        spel_keuze = ""
        if spellen:
            opties = "".join(f"<option value='{_e(s['id'])}'>{_e(s.get('hunch') or s['id'])}"
                             f"</option>" for s in spellen)
            spel_keuze = (f"<select name='sid'>{opties}</select>"
                          f"<button class='btn' name='action' value='kb_atoom_naar_spel'>"
                          f"Voeg toe aan spel</button>")
        curatie = (f"<div class='kn-lrow'>"
                   f"{_field('kop voor de samengestelde kaart', 'kop', fid='f-kn-kop', placeholder='bijv. 19 micro-stappen met kinderarbeid in de leerschoenproductie')}"
                   f"<button class='btn ok' name='action' value='kb_atoom_merge'>Voeg samen</button>"
                   f"<button class='btn' name='action' value='kb_atoom_archive'>Archiveer</button>"
                   f"{spel_keuze}</div>")
        lijst = (f"{teller}<form method='post' action='/action'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                 f"<input type='hidden' name='next' value='{_e(nxt)}'>"
                 f"{regels}{curatie}</form>" + (f"<p>{nav}</p>" if nav else ""))
    archief = _gearchiveerd_uitklap(st, hub, csrf)
    return (f"<h2>Bibliotheek</h2><div class='c2-sec'>{chips}</div>{lijst}{archief}")


def _gearchiveerd_uitklap(st, hub: str, csrf: str) -> str:
    """Archiveren is terugdraaibaar: de gearchiveerde notities met een terugzet-knop."""
    from nooch_village.kennisbank import load_atoms as _la
    alles = _la(st.dd, include_archived=True)
    archief = {aid: a for aid, a in alles.items()
               if isinstance(a, dict) and a.get("archived")}
    if not archief:
        return ""
    nxt = f"/kennisbank?hub={hub}" if hub else "/kennisbank"
    rows = ""
    for aid, a in sorted(archief.items())[:20]:
        rows += (f"<form method='post' action='/action' class='kn-lrow'>"
                 f"{_hid(csrf, 'kb_atoom_unarchive', nxt, {'atom_id': aid})}"
                 f"<div class='kn-lt'>{_e(a.get('claim'))}"
                 f"<span class='kn-src'>{_e(a.get('source') or '')}</span></div>"
                 f"<button class='btn'>Zet terug</button></form>")
    meer = (f"<p class='muted'>… en nog {len(archief) - 20} meer.</p>"
            if len(archief) > 20 else "")
    return (f"<details class='kn-panel'><summary>📦 Gearchiveerd ({len(archief)})</summary>"
            f"<p class='muted'>Uit de lijsten gehaald maar nooit weggegooid — "
            f"terugzetten kan altijd.</p>{rows}{meer}</details>")


def _ongesorteerd_bakje(atoms: dict, inzichten, csrf: str) -> str:
    """Zichtbaar bakje (besluit Stefan): atomen zonder onderwerp-tag, met per atoom een
    onderwerp-keuze zodat een mens ze naar een hub cureert. Geen stille restcategorie.

    Alleen kennisbank-era atomen (met `provenance`, dus seed + intake): de ~190 legacy
    Librarian-kaartjes in notes.json hebben geen provenance én geen onderwerp-tag en
    zouden het bakje anders overspoelen — die horen bij de kennislaag-flow, niet hier."""
    los = {aid: a for aid, a in atoms.items()
           if not subject_van(a) and a.get("provenance")
           and (a.get("claim") or "").strip()}
    if not los:
        return ""
    opts = "".join(f"<option value='{_e(s)}'>{_e(s)}</option>" for s in SUBJECTS)
    rows = ""
    for aid, a in sorted(los.items())[:30]:
        rows += (f"<form method='post' action='/action' class='kn-lrow'>"
                 f"{_hid(csrf, 'kb_atoom_subject', '/kennisbank', {'atom_id': aid})}"
                 f"<div class='kn-lt'>{_e(a.get('claim'))}"
                 f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}</span></div>"
                 f"<select name='subject'><option value=''>kies onderwerp…</option>{opts}</select>"
                 f"<button class='btn'>Sorteer</button></form>")
    meer = f"<p class='muted'>… en nog {len(los) - 30} meer.</p>" if len(los) > 30 else ""
    return (f"<details class='kn-panel'><summary>📥 Ongesorteerd ({len(los)})</summary>"
            f"<p class='muted'>Notities zonder onderwerp. Kies een hub, dan tellen ze mee "
            f"in clusters en zoekopdrachten.</p>{rows}{meer}</details>")


def _curatie_sectie(titel: str, kandidaten: list[dict], atoms: dict, hunch: str,
                    csrf: str, reformulate_of: str = "") -> str:
    """De hand cureren vóór het spel: vink + richting per kaart (systeem stelt voor, mens
    draait), tegenbewijs in een eigen sectie (anti-cherry-pick). Post → kb_spel_start."""
    sup = [k for k in kandidaten if k["stance"] == "support"]
    cou = [k for k in kandidaten if k["stance"] == "counter"]

    def rij(k):
        aid = k["atom_id"]
        a = atoms.get(aid) or {}
        keuze = "".join(f"<option value='{s}'{' selected' if k['stance'] == s else ''}>{lbl}</option>"
                        for s, lbl in (("support", "steunt"), ("counter", "spreekt tegen")))
        return (f"<div class='kn-lrow'><input type='checkbox' name='kaart' value='{_e(aid)}' checked "
                f"id='f-krt-{_e(aid)}' form='spelstart'>"
                f"<div class='kn-lt'><label for='f-krt-{_e(aid)}'>{_e(a.get('claim'))}</label>"
                f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}</span></div>"
                f"<select name='stance_{_e(aid)}' form='spelstart'>{keuze}</select></div>")

    binnen = ""
    if sup:
        binnen += "<div class='kn-sectitle'>Steunt mogelijk</div>" + "".join(rij(k) for k in sup)
    if cou:
        binnen += ("<div class='kn-sectitle'>spreekt dit tegen? (laat staan — daar scherp je aan)"
                   "</div>" + "".join(rij(k) for k in cou))
    if not binnen:
        binnen = "<p class='muted'>Geen kaarten gevonden bij dit vermoeden.</p>"
    # Zachte rem (taak 2): onder 3 onafhankelijke steunbronnen een nudge, nooit een blokkade.
    # Na het starten rekent de spel-pagina hem per mutatie opnieuw uit.
    indep = field(kandidaten, atoms)["indep"]
    nudge = ""
    if kandidaten and indep < 3:
        nudge = (f"<div class='kn-caveat'>Nog dun: {indep} onafhankelijke "
                 f"steunbron{'nen' if indep != 1 else ''} in deze set. Drie losse bronnen "
                 f"maken een inzicht stevig — in het spel kun je kaarten bijkoppelen. "
                 f"Spelen mag altijd.</div>")
    return (f"<div class='card'><div class='kn-sectitle'>{_e(titel)}</div>{nudge}"
            f"<form method='post' action='/action' id='spelstart'>"
            f"{_hid(csrf, 'kb_spel_start', '/kennisbank?open=speel', {'reformulate_of': reformulate_of})}"
            f"{_field('je vermoeden', 'hunch', value=hunch, fid='f-kn-hunch', required=True)}"
            f"</form>{binnen}"
            f"<button class='btn ok' form='spelstart'>speel het inzicht →</button> "
            f"<span class='muted'>de dialoog duwt je; hij eindigt met een claim, "
            f"een reframe en een falsifier</span></div>")


def render_kennisbank(st, kid: str = "", q: str = "", csrf_token: str = "",
                      msg: str = "", hunch: str = "", speel: str = "",
                      nieuw: str = "", hub: str = "", pag: int = 1,
                      open_: str = "", cluster: int = 0) -> str:
    atoms = load_atoms(st.dd)
    inzichten = st.kennisbank.all()
    # Een lopende hunch/speel-set houdt de speel-zone vanzelf open.
    if (hunch or speel) and not open_:
        open_ = "speel"
    cards = "".join(_topic_card(i, atoms) for i in inzichten) or (
        "<p class='muted'>Nog geen inzichten. Maak er een met \"+ Begin een leeg inzicht\", of "
        "seed de eerste vulling: <code>python -m nooch_village.kennisbank_seed --apply</code></p>")

    nieuw_form = (
        f"<details class='kn-panel'><summary>+ Begin een leeg inzicht</summary>"
        f"<form method='post' action='/action'>"
        f"{_hid(csrf_token, 'kb_new', '/kennisbank')}"
        f"{_field('de claim (mensentaal, kort)', 'title', fid='f-kn-title', required=True)}"
        f"{_field('waarom denk je dit? (één zin, optioneel)', 'why', fid='f-kn-why')}"
        f"<button class='btn ok'>Maak het inzicht</button>"
        f"<span class='muted'> — groeit van \"nog dun\" naar \"stevig\" door bewijs te koppelen</span>"
        f"</form></details>")

    actiebalk = _actiebalk(open_, st, atoms, inzichten, hunch, speel, cluster, csrf_token)
    toast = _nieuw_toast(nieuw, atoms)
    bakje = _ongesorteerd_bakje(atoms, inzichten, csrf_token)
    bieb = _bibliotheek_sectie(st, atoms, hub, pag, csrf_token)

    drawer = ""
    if kid:
        ins = st.kennisbank.get(kid)
        if ins is not None:
            drawer = _drawer(ins, atoms, q, csrf_token)

    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>🌱 Wat Nooch weet</h1>"
            f"{actiebalk}{_banner(msg)}{toast}"
            f"<h2>Onze inzichten</h2>{nieuw_form}{cards}"
            f"{bieb}{bakje}"
            f"<p class='muted'>Elke zekerheid schuift mee als er info bijkomt.</p></div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/signals'>signalen</a> · "
             "<a href='/inzichten'>kennislaag</a></div>"
             f"<div class='c2-wrap'>{main}</div>{drawer}")
    return _page("Wat Nooch weet", inner)
