"""Kennisbank — "Wat Nooch weet": geversioneerde inzichten boven de atomen (fase 1).

UI-referentie: het prototype nooch-kb (drawer-gedrag, woord + 4-punts meter + één zin).
Server-rendered zonder JS: het detail opent als drawer via ?id=<inzicht> (de open-staat
is een URL, geen client-state); sluiten = terug naar /kennisbank. De machinerie
(percentages, trust, groepen) blijft binnen — de gebruiker ziet alleen het eindwoord.

Hergebruik: web_base (_e/_page/_field/_banner), cockpit2_util (_DS_LINK/_BUILD),
kern-klassen (.card/.btn/.chip/.muted) + de kn-*-familie in static/nooch.css (drawer,
meter, noten, koppel-paneel — expliciet vocabulaire-besluit, zie tests/test_ui_ratchets).

Statements-herontwerp (dd 2026-07-18, docs/SPEC_kennisbank_statements.html, akkoord founder): de
bibliotheek rechts is een KAAL statements-overzicht (alleen de claim); klik klapt het
detail uit (datum · bron op één plek · versie · gekoppeld · tags · ✏️ bewerk); zoeken =
typen (ook op bron/reference/tag); de ⠿-handle sleept een statement op een ander →
merge-modal → kb_atoom_merge (zie tests/test_kennisbank_statements.py).

Founder-ronde dd 2026-07-18 (ruimte winnen — meer content in beeld): de bulk-selectie
(checkbox + selectiebalk) is weg; archiveren/naar-spel zitten als tekstlinks in het
statement-detail. Koppen: "Insights" links, rustige "Signals" rechts mét tags-pill
(chips → live-zoekveld). Geen "+ Begin een leeg inzicht", geen uitlegtekst, geen groene
succes-banner (fouten blijven zichtbaar). Bron-propagatie: een gekoppelde reference gaat
óók naar bronloze atomen met dezelfde genormaliseerde bron (cockpit2/notes_store).
"""
from __future__ import annotations

import re

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _BUILD, _nav
from nooch_village.kennisbank import field, verdict, WORD_LABEL, load_atoms, meta_field
from nooch_village.kennisbank_intake import SUBJECTS
from nooch_village.kennisbank_spel import (clusters as kb_clusters, gather,
                                           spel_suggesties, subject_van)


def _dots(word: str, n: int) -> str:
    # Secundaire meter naast het WOORD (dat de status draagt). Tooltip legt de meter uit;
    # het woord is de leesbare status (recognition, Nielsen #1).
    balls = "".join(f"<span class='{'' if i < n else 'o'}'>●</span>" for i in range(4))
    return (f"<span class='kn-dots {_e(word)}' "
            f"title='Zekerheidsmeter: {n} van 4. Berekend uit onafhankelijke bronnen — "
            f"het woord draagt de status.'>{balls}</span>")


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _topic_card(ins: dict, atoms: dict, csrf: str = "", active_iid: str = "",
                related_ids: set | None = None) -> str:
    v = verdict(field(ins.get("evidence") or [], atoms))
    word = v["word"]
    subject = ins.get("subject") or ""
    chip = f"<span class='chip outline'>{_e(subject)}</span>" if subject else ""
    kaart = (
        f"<a class='card kn-topic' href='/kennisbank?id={_e(ins['id'])}'>"
        f"<div class='kn-thead'><div class='kn-tmain'>"
        f"<div class='kn-ttitle'>{_e(ins.get('title'))}"
        f"<span class='badge ro'>v{_e(ins.get('version') or '1.0')}</span></div>"
        f"<div class='kn-twhy'>{_e(ins.get('why'))} {chip}</div></div>"
        f"<div class='kn-conf'><span class='kn-word {_e(word)}'>{_e(WORD_LABEL[word])}</span>"
        f"{_dots(word, v['dots'])}</div><span class='kn-arrow'>›</span></div></a>")
    # B1: staat er een inzicht open, dan kun je ELK ander inzicht eraan koppelen (steun/tegen).
    if active_iid and ins["id"] != active_iid:
        nxt = f"/kennisbank?id={active_iid}"
        if ins["id"] in (related_ids or set()):
            koppel = "<span class='chip'>✓ gekoppeld</span>"
        else:
            koppel = (f"<span class='kn-koppellbl muted'>koppel aan het open inzicht:</span>"
                      f"<form method='post' action='/action' class='kn-unlink'>"
                      f"{_hid(csrf, 'kb_insight_link', nxt, {'iid': active_iid, 'other_id': ins['id'], 'stance': 'support'})}"
                      f"<button class='btn ok'>+ steunt</button></form>"
                      f"<form method='post' action='/action' class='kn-unlink'>"
                      f"{_hid(csrf, 'kb_insight_link', nxt, {'iid': active_iid, 'other_id': ins['id'], 'stance': 'counter'})}"
                      f"<button class='btn no'>+ spreekt tegen</button></form>")
        kaart += f"<div class='kn-topiclink'>{koppel}</div>"
    return kaart
def _note_html(ins: dict, link: dict, atom: dict | None, csrf: str, nxt: str) -> str:
    stance = link.get("stance") or "support"
    claim = (atom or {}).get("claim") or f"(kaart {link.get('atom_id')} niet gevonden)"
    src = (atom or {}).get("source") or ""
    ann = link.get("annotation") or ""
    aid = link.get("atom_id") or ""
    # A1: de comment-per-statement is weg (er is één gesprek onderaan het inzicht). Een
    # bestaande annotatie blijft leesbaar; alleen ontkoppelen kan hier nog (A4).
    ann_html = f"<span class='kn-ann'>notitie: {_e(ann)}</span>" if ann else ""
    prefix = "tegen · " if stance == "counter" else ""
    ctrl = (f"<form method='post' action='/action' class='kn-unlink'>"
            f"{_hid(csrf, 'kb_unlink', nxt, {'iid': ins['id'], 'atom_id': aid})}"
            f"<button class='btn' title='ontkoppelen (kaart blijft in de bibliotheek)'>×</button></form>")
    return (f"<div class='kn-note {_e(stance)}'>"
            f"<div class='kn-ntext'>{_e(claim)}"
            f"<span class='kn-src'>{_e(prefix)}{_e(src)}</span>{ann_html}</div>"
            f"<div class='kn-nctrls'>{ctrl}</div></div>")
def _flip_note_html(atom: dict | None, kant: str) -> str:
    """Eén bewijs-statement gelezen VAN DE ANDERE KANT (Taak 3). `kant='voor'`: dit statement
    (dat de oorspronkelijke claim tegensprak) pleit nu vóór de tegenkant; `kant='tegen'`: dit
    statement (dat de claim steunde) pleit nu tégen de tegenkant. De statement-tekst blijft
    ongewijzigd (geen nieuwe opgeslagen claim) — alleen de lens-lezing draait mee."""
    claim = (atom or {}).get("claim") or "(kaart niet gevonden)"
    src = (atom or {}).get("source") or ""
    stance = "support" if kant == "voor" else "counter"
    lens = ("↔ Vanaf de andere kant gelezen pleit dit vóór de tegenclaim "
            "(het sprak de oorspronkelijke claim tegen)." if kant == "voor"
            else "↔ Vanaf de andere kant gelezen pleit dit tégen de tegenclaim "
                 "(het steunde juist de oorspronkelijke claim).")
    return (f"<div class='kn-note {stance}'>"
            f"<div class='kn-ntext'>{_e(claim)}"
            f"<span class='kn-src'>{_e(src)}</span>"
            f"<span class='kn-fliplens'>{lens}</span></div></div>")


def _inzicht_detail(ins: dict, atoms: dict, csrf: str, by_id: dict | None = None,
                    flip: bool = False) -> str:
    """Het inzicht-detail in de LINKERkolom. B2: een "↺ draai om" toont de ACHTERKANT (de
    andere kant + falsifier + gespiegeld bewijs). B1: een sectie met gekoppelde inzichten +
    "speel een meta-inzicht". Bewijs koppel je via de bibliotheek rechts."""
    by_id = by_id or {}
    nxt = f"/kennisbank?id={ins['id']}"
    v = verdict(field(ins.get("evidence") or [], atoms))
    word = v["word"]
    sup = [l for l in ins.get("evidence") or [] if l.get("stance") == "support"]
    cou = [l for l in ins.get("evidence") or [] if l.get("stance") == "counter"]

    # B2 — de flip is een denkoefening: hetzelfde materiaal van de tegenkant gelezen. De
    # reframe wordt de claim, de falsifier prominent, en het bewijs spiegelt (counter = wat de
    # tegenkant STEUNT, support = wat de tegenkant tegenspreekt). Hergebruikt bestaande velden.
    if flip:
        terug = f"<a class='btn' href='/kennisbank?id={_e(ins['id'])}'>↺ terug</a>"
        # Taak 3: op de achterkant leest ELK statement van de tegenkant. Een statement dat de
        # oorspronkelijke claim tegensprak pleit nu VÓÓR de andere kant; een dat 'm steunde pleit
        # er nu TÉGEN. We hergebruiken de bestaande stance (geen nieuwe opgeslagen claim) en
        # geven per statement een omgekeerde lens-lezing.
        back_sup = "".join(_flip_note_html(atoms.get(l.get("atom_id") or ""), "voor") for l in cou) \
            or "<p class='muted'>Geen tegenbewijs verzameld — de andere kant staat er dun voor.</p>"
        back_cou = "".join(_flip_note_html(atoms.get(l.get("atom_id") or ""), "tegen") for l in sup)
        falsi_back = (f"<div class='kn-sec'><div class='kn-sectitle'>Wat zou de oorspronkelijke "
                      f"claim onderuit halen?</div><div class='kn-falsi'>{_e(ins.get('falsifier'))}</div></div>"
                      if ins.get("falsifier") else "")
        return (
            f"<div class='card kn-detail kn-flip'>"
            f"<div class='kn-flipbar'><span class='chip muted'>de andere kant</span>{terug}</div>"
            f"<div class='kn-claim'>{_e(ins.get('reframe') or 'Geen tegenovergestelde geformuleerd.')}</div>"
            f"<p class='muted'>Lees hetzelfde inzicht van de tegenkant — een denkoefening, geen conclusie.</p>"
            f"<div class='kn-sec'><div class='kn-sectitle'>Bewijs voor de andere kant</div>{back_sup}"
            + (f"<div class='kn-sectitle'>Spreekt de andere kant tegen</div>{back_cou}" if back_cou else "")
            + f"</div>{falsi_back}</div>")

    noten_sup = "".join(_note_html(ins, l, atoms.get(l.get("atom_id") or ""), csrf, nxt)
                        for l in sup) or "<p class='muted'>Nog geen bewijs.</p>"
    noten_cou = "".join(_note_html(ins, l, atoms.get(l.get("atom_id") or ""), csrf, nxt)
                        for l in cou)
    caveat = (f"<div class='kn-caveat'>⚠ {_e(ins.get('caveat'))}</div>"
              if ins.get("caveat") else "")
    # Kantelvoorwaarde (falsifier) hoort ook op de VOORKANT zichtbaar: elke zekerheid draagt
    # de voorwaarde waaronder hij kantelt bij zich (founder, 18 jul). De flip-achterkant
    # toont hem daarnaast als "wat haalt de claim onderuit".
    kantel = (f"<div class='kn-kantel'>⚖ <span class='muted'>Kantelt als:</span> "
              f"{_e(ins.get('falsifier'))}</div>"
              if ins.get("falsifier") else "")

    # A1: geen apart "voeg bewijs/reactie toe"-paneel meer (het derde pad). Bewijs koppel je
    # rechts uit de bibliotheek; een reactie plaats je in het gesprek onderaan.

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

    # C3: het gesprek OVER het inzicht als geheel — een echte draad (afzender + tijd), met
    # het invoerveld als natuurlijke afsluiting. Append-only (kb_discuss).
    draad = "".join(
        f"<div class='kn-msg'><div class='kn-msg-head'><b>{_e(d.get('by') or 'iemand')}</b>"
        f"<span class='muted'>{_e((d.get('created_at') or '')[:16].replace('T', ' '))}</span></div>"
        f"<div class='kn-msg-text'>{_e(d.get('text'))}</div></div>"
        for d in ins.get("discussion") or [])
    if not draad:
        draad = ("<p class='muted'>Nog geen kanttekeningen. Dit is de plek voor opmerkingen "
                 "over het inzicht als geheel.</p>")
    gesprek = (f"<div class='kn-thread'>{draad}</div>"
               f"<form method='post' action='/action' class='kn-discrow'>"
               f"{_hid(csrf, 'kb_discuss', nxt, {'iid': ins['id']})}"
               f"{_field('schrijf een kanttekening…', 'text', fid='f-kn-disc', placeholder='je opmerking over dit inzicht')}"
               f"<button class='btn ok'>Plaats</button></form>")

    historie = ""
    if ins.get("history"):
        rows = "".join(f"<div class='muted'>v{_e(h.get('version'))} · {_e(h.get('title'))} "
                       f"<span class='kn-src'>({_e((h.get('at') or '')[:10])})</span></div>"
                       for h in reversed(ins["history"]))
        historie = (f"<details class='kn-panel'><summary>eerdere versies "
                    f"({len(ins['history'])})</summary>{rows}</details>")

    # B1 (vindbaarheid): de gerelateerde-inzichten-sectie staat ALTIJD bij een open inzicht — ook
    # leeg, met een uitnodiging — zodat de meta-flow ontdekbaar is (voorheen kip-ei: alleen zichtbaar
    # als er al iets gekoppeld was). De koppel-actie zelf zit in de lijst eronder.
    related = ins.get("related") or []
    rrows = ""
    for r in related:
        other = by_id.get(r["insight_id"]) or {}
        pref = "tegen · " if r.get("stance") == "counter" else ""
        rrows += (f"<div class='kn-note {_e(r.get('stance') or 'support')}'>"
                  f"<div class='kn-ntext'><a href='/kennisbank?id={_e(r['insight_id'])}'>"
                  f"{_e(pref)}{_e(other.get('title') or r['insight_id'])}</a></div>"
                  f"<div class='kn-nctrls'><form method='post' action='/action' class='kn-unlink'>"
                  f"{_hid(csrf, 'kb_insight_unlink', nxt, {'iid': ins['id'], 'other_id': r['insight_id']})}"
                  f"<button class='btn' title='ontkoppelen'>×</button></form></div></div>")
    meta_woord = ""
    if related:
        mv = verdict(meta_field(ins, by_id, atoms))
        meta_woord = f" <span class='kn-word {_e(mv['word'])}'>{_e(WORD_LABEL[mv['word']])}</span>"
    if len(related) >= 2:
        onderkant = (f"<form method='post' action='/action' class='kn-metaplay'>"
                     f"{_hid(csrf, 'kb_meta_start', nxt, {'iid': ins['id']})}"
                     f"<button class='btn ok'>🎲 Speel een meta-inzicht</button> "
                     f"<span class='muted'>maak van deze gekoppelde inzichten één superinzicht "
                     f"(zelfde spel-flow)</span></form>")
    elif related:
        onderkant = ("<p class='muted'>Koppel nog een inzicht (hieronder) om een meta-inzicht "
                     "te kunnen spelen.</p>")
    else:
        onderkant = ("<p class='muted'>Nog niets gekoppeld. Kies hieronder een inzicht dat dit "
                     "<b>steunt</b> of <b>tegenspreekt</b> — bij twee of meer speel je een "
                     "meta-inzicht.</p>")
    related_sec = (
        f"<div class='kn-sec kn-relbox'><div class='kn-sectitle'>🔗 Gerelateerde inzichten{meta_woord}</div>"
        f"<p class='muted'>Koppel inzichten die elkaar steunen of tegenspreken — samen worden ze "
        f"een superinzicht. De meta-zekerheid volgt uit de onderliggende inzichten.</p>"
        f"{rrows}{onderkant}</div>")

    brug_hint = ("<p class='muted'>Koppel bewijs door in de bibliotheek rechts op "
                 "“+ steunt” of “+ tegen” te klikken — de suggesties staan al gemarkeerd.</p>")
    flip_knop = (f"<a class='btn kn-flipbtn' href='/kennisbank?id={_e(ins['id'])}&flip=1'>↺ draai om</a>"
                 if ins.get("reframe") or ins.get("falsifier") else "")
    return (
        f"<div class='card kn-detail'>"
        f"<div class='kn-flipbar'>{flip_knop}<a class='kn-x' href='/kennisbank'>×</a></div>"
        f"<div class='kn-claim'>{_e(ins.get('title'))}"
        f"<span class='badge ro'>v{_e(ins.get('version') or '1.0')}</span></div>"
        f"<div class='kn-conf'><span class='kn-word {_e(word)}'>{_e(WORD_LABEL[word])}</span>"
        f"{_dots(word, v['dots'])}</div>"
        f"<div class='kn-sentence'>{v['sentence']}</div>{caveat}{kantel}"
        f"<div class='kn-sec'><div class='kn-sectitle'>Het bewijs</div>{noten_sup}"
        + (f"<div class='kn-sectitle'>Tegenspraak</div>{noten_cou}" if noten_cou else "")
        + f"{brug_hint}{herformuleer}</div>"
        f"{related_sec}"
        f"<div class='kn-sec'><div class='kn-sectitle'>Gesprek</div>{gesprek}</div>"
        f"{historie}</div>")


def _atoom_regel(aid: str, a: dict) -> str:
    """Eén atoom compact: inhoud + onderwerp + bron (+ body-uitklap voor een samengestelde
    kaart). Geen trust, geen machinerie, geen selectie (founder dd 2026-07-18)."""
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
    return (f"<div class='kn-note support'><span class='kn-dot'></span>"
            f"<div class='kn-ntext'>{_e(a.get('claim'))}{vlag} {chip}"
            f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}{ref}</span>"
            f"{body}</div></div>")


def _actiebalk(open_: str, st, atoms: dict, inzichten: list, hunch: str, speel: str,
               cluster: int, csrf: str) -> str:
    """Zone 1 — de compacte, sticky actiebalk met twee accordions (open-staat via ?open=).
    Laag als beide dicht zijn; klapt één zone open zonder de pagina te verspringen."""
    bron_open = open_ == "bron"
    speel_open = open_ == "speel"
    # De 🎲-pill is weg (founder, 19 jul): de suggestiekaart bovenaan de inzichten-kolom
    # is nu dé ingang naar het spel. De speel-zone zelf blijft bereikbaar via ?open=speel
    # (eigen vermoeden typen, cluster-navigatie) — alleen de knop in de balk verviel.
    knoppen = (f"<div class='kn-actiebtns'>"
               f"<a class='btn{' ok' if bron_open else ''}' "
               f"href='/kennisbank{'' if bron_open else '?open=bron'}'>➕ Bron toevoegen</a>"
               f"<a class='btn' href='/signals' title='Goedgekeurde radar-signalen — het "
               f"startpunt voor inzichten'>🛰 Signals</a></div>")
    paneel = ""
    if bron_open:
        paneel = f"<div class='card kn-capture'>{_bron_toevoegen(csrf)}</div>"
    elif speel_open:
        paneel = f"<div class='card kn-capture'>{_speel_toevoegen(st, atoms, inzichten, hunch, speel, cluster, csrf)}</div>"
    return f"<div class='kn-actiebalk'>{knoppen}{paneel}</div>"


def _bron_toevoegen(csrf: str) -> str:
    """Zone 2 — één ingang: plakken (tekst/link) OF een bestand. Auto-detectie server-side;
    het resultaat gaat naar de staging-ronde ('even nakijken'), niet meteen de bibliotheek in."""
    # A5: één rustige verticale indeling — plak-veld, dan bestand, dan één primaire knop,
    # met de "we herkennen het type zelf"-hint eronder. Design-system-spacing (kn-bronform).
    return (
        f"<form method='post' action='/action' enctype='multipart/form-data' class='kn-bronform'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
        f"<input type='hidden' name='action' value='kb_bron_add'>"
        f"<div class='kn-bronveld'>{_field('Plak een notitie, artikel of link (website / Google Sheet)', 'bron_text', kind='textarea', fid='f-bron-text')}</div>"
        f"<div class='kn-bronveld'>"
        + _field("Of kies een bestand (PDF, Excel of CSV)", "file", kind="file",
                 fid="f-bron-file", attrs="accept='.pdf,.xlsx,.xls,.csv'")
        + f"</div>"
        f"<button class='btn ok'>Verwerk de bron</button>"
        f"<p class='muted kn-bronhint'>We herkennen het type zelf; daarna kijk je de "
        f"voorstellen na vóór ze de bibliotheek in gaan.</p></form>"
        # Voortgangsscherm: verschijnt bij submit (JS haalt [hidden] weg). De balk is pure
        # CSS-animatie met een ease-in-curve — traag op gang, steeds sneller richting het
        # einde (goal-gradient: versnellende voortgang voelt als vooruitgang). De echte
        # redirect van de server onderbreekt hem vanzelf; hij is voortgangsgevoel, geen meting.
        f"<div class='kn-overlay' id='kn-bronbezig' hidden>"
        f"<div class='kn-modal kn-vgmodal'><h2>\U0001f331 De bron wordt verwerkt</h2>"
        f"<div class='kn-vgbaan'><div class='kn-vgbalk'></div></div>"
        f"<p class='muted'>Lezen, in kaartjes knippen, herkomst eraan… daarna kijk jij "
        f"ze na.</p></div></div>"
        f"<script>(function(){{var f=document.querySelector('.kn-bronform');"
        f"var o=document.getElementById('kn-bronbezig');if(!f||!o)return;"
        f"f.addEventListener('submit',function(){{o.removeAttribute('hidden');}});}})();"
        f"</script>")


def _speel_toevoegen(st, atoms: dict, inzichten: list, hunch: str, speel: str,
                     cluster: int, csrf: str) -> str:
    """Zone 3 — de clusters zijn de hoofdingang; de hunch is een ondergeschikte neveningang
    ónder de clusters (A1/A5). Rustige verticale indeling."""
    delen: list[str] = []
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
    # De hunch: ondergeschikte neveningang, ónder de clusters.
    delen.append(
        f"<form method='get' action='/kennisbank' class='kn-hunch'>"
        f"<input type='hidden' name='open' value='speel'>"
        + _field("Of typ een eigen vermoeden", "hunch", value="" if speel else hunch,
                 fid="f-kn-hunchzoek", placeholder="bijv. wachttijd is juist een feature, geen kost")
        + f"<button class='btn'>Zoek de kaarten</button>"
        f"<span class='muted kn-bronhint'>een neveningang — meestal begin je met een cluster hierboven</span>"
        f"</form>")
    if speel:
        kandidaten = [{"atom_id": aid, "stance": "support"}
                      for aid in speel.split(",") if aid in atoms]
        delen.append(_curatie_sectie("Je set (draai de richting waar nodig)",
                                     kandidaten, atoms, hunch, csrf))
    elif hunch:
        kandidaten = gather(hunch, atoms)
        delen.append(_curatie_sectie(f"Kaarten bij: “{hunch}”", kandidaten, atoms, hunch, csrf))
    open_spellen = st.spel.open_spellen()[:3]
    if open_spellen:
        rijen = "".join(f"<a href='/kennisbank/spel?sid={_e(s['id'])}'>{_e(s.get('hunch') or s['id'])}</a>"
                        for s in open_spellen)
        delen.append(f"<div class='kn-openspel muted'>Lopende spellen: {rijen}</div>")
    return "".join(delen)


def _suggestie_kaart(atoms: dict, inzichten: list, sug: int, csrf: str,
                     data_dir: str = "") -> str:
    """De bovenste plek van de inzichten-kolom (founder, 19 jul): één vóórgevuld inzicht
    uit het sterkste cluster — lichtgeel, expliciet 'not verified', met een verify-knop
    die het spel start (kb_spel_start, de kaarten van het cluster als hand) en bladeren
    naar de volgende kandidaat (?sug=). De voorvulling is deterministisch
    (kennisbank_spel.spel_suggesties); het scherp formuleren gebeurt in het spel.
    Spelvraag (founder, 19 jul): de claim is informatie, de vraag is verleiding — als
    spelvraag.vraag_voor een gecachete/verse vraag heeft, opent de kaart daarmee (Lara
    stelt hem) en zakt de claim naar een startpunt-regel; anders de claim, zoals altijd."""
    if not csrf:
        return ""
    kandidaten = spel_suggesties(atoms, inzichten)
    if not kandidaten:
        return ""
    i = max(0, min(sug, len(kandidaten) - 1))
    kand = kandidaten[i]
    verborgen = "".join(
        f"<input type='hidden' name='kaart' value='{_e(aid)}'>"
        f"<input type='hidden' name='stance_{_e(aid)}' value='support'>"
        for aid in kand["atom_ids"])
    nav = ""
    if len(kandidaten) > 1:
        prev = (f"<a class='btn' href='/kennisbank?sug={i - 1}' "
                f"title='vorige kandidaat'>←</a>" if i > 0 else "")
        volg = (f"<a class='btn' href='/kennisbank?sug={i + 1}' "
                f"title='volgende kandidaat'>→</a>" if i < len(kandidaten) - 1 else "")
        nav = (f"<span class='muted'>kandidaat {i + 1} van {len(kandidaten)}</span> "
               f"{prev}{volg}")
    vraag = ""
    if data_dir:
        from nooch_village.spelvraag import vraag_voor
        vraag = vraag_voor(kand, atoms, data_dir=data_dir) or ""
    kop = (f"<div class='kn-spelvraag'><span class='wie'>📚 Lara vraagt zich af</span>"
           f"{_e(vraag)}</div>"
           f"<div class='muted kn-spelstart'>startpunt: {_e(kand['hunch'][:140])}</div>"
           ) if vraag else f"<div class='kn-claim'>{_e(kand['hunch'])}</div>"
    return (
        f"<div class='card kn-sugg'>"
        f"<div class='kn-sugghead'><span class='chip kn-suggflag'>not verified</span>"
        f"<span class='muted'>voorzet uit je signals — verifieer om er een inzicht van "
        f"te maken</span></div>"
        f"{kop}"
        f"<p class='muted'>🧩 {_e(kand['theme'])} · {len(kand['atom_ids'])} kaarten "
        f"staan klaar (inclusief wat tegenspreekt)</p>"
        f"<div class='kn-suggbtns'><form method='post' action='/action' class='kn-unlink'>"
        f"{_hid(csrf, 'kb_spel_start', '/kennisbank', {'hunch': kand['hunch']})}"
        f"{verborgen}<button class='btn ok'>✓ Verify — speel dit inzicht</button></form>"
        f"{nav}</div></div>")


def _nieuw_toast(nieuw: str, atoms: dict) -> str:
    """Na een staging-commit tonen we kort de net toegevoegde atomen (via ?nieuw=)."""
    ids = [i for i in (nieuw or "").split(",") if i and i in atoms]
    if not ids:
        return ""
    rows = "".join(_atoom_regel(aid, atoms[aid]) for aid in ids)
    return (f"<div class='card kn-capture'><div class='kn-sectitle'>Net toegevoegd "
            f"({len(ids)})</div>{rows}</div>")


_PAG = 30
_ZOEK_MAX = 60


def _stmt_datum(a: dict) -> str:
    """De Datum-rij (spec): source_date (de datum van de bron) gaat vóór; is die er niet,
    dan created_at met het label 'toegevoegd' — nooit een valse bron-datum suggereren."""
    sd = (a.get("source_date") or "").strip()
    if sd:
        return _e(sd[:10])
    ca = (a.get("created_at") or "")[:10]
    return (f"{_e(ca)} <span class='muted'>· toegevoegd</span>" if ca
            else "<span class='muted'>—</span>")


def _stmt_bron(aid: str, a: dict, csrf: str, nxt: str) -> str:
    """De Bron-rij — de bron leeft op ÉÉN plek (spec). Een reference-URL of -PDF rendert
    als externe link (target=_blank; een PDF is een /kbref/-pad naar het geserveerde
    bestand); een legacy label-reference (DOI/ISBN/documentlabel) als tekst (fail-soft);
    alleen een bronnaam als kale tekst. Het kleine ✏️ ernaast (of '+ voeg bron toe' als er
    niets is) klapt inline het compacte koppel-blok uit: URL-veld (kb_atoom_reference) +
    PDF-upload (het bestaande kb_atoom_ref_pdf-formulier). Zonder csrf: alleen weergave."""
    ref = (a.get("reference") or "").strip()
    src = (a.get("source") or "").strip()
    # Een DOI is óók een link (founder, 19 jul): DOI:10.xxxx/… → https://doi.org/10.xxxx/…
    # — dezelfde weergave als een URL-reference, zodat elke bron met een resolvebaar
    # kenmerk klikbaar is. Andere legacy labels (ISBN, documentnaam) blijven tekst.
    doi = re.match(r"(?i)^doi:\s*(10\.\S+)$", ref)
    if ref.startswith(("http://", "https://", "/kbref/")):
        label = src or (ref.rsplit("_", 1)[-1] if ref.startswith("/kbref/") else ref)
        weergave = f"<a href='{_e(ref)}' target='_blank' rel='noopener'>{_e(label)} ↗</a>"
    elif doi:
        label = f"{src} · {ref}" if src and src not in ref else ref
        weergave = (f"<a href='https://doi.org/{_e(doi.group(1))}' target='_blank' "
                    f"rel='noopener'>{_e(label)} ↗</a>")
    elif ref:
        weergave = _e(f"{src} · {ref}" if src and src not in ref else ref)
    elif src:
        weergave = _e(src)
    else:
        weergave = ""
    if not csrf:
        return weergave or "<span class='muted'>—</span>"
    # Mét reference: klein ✏️ ernaast. Zonder reference (ook als er wél een bronnaam
    # staat): '+ voeg bron toe' op diezelfde plek (spec) — de naam blijft leesbaar.
    knop = "✏️" if ref else "+ voeg bron toe"
    vorm = (f"<details class='kn-bronvorm'>"
            f"<summary title='bron wijzigen of toevoegen'>{knop}</summary>"
            f"<form method='post' action='/action' class='kn-editform'>"
            f"{_hid(csrf, 'kb_atoom_reference', nxt, {'atom_id': aid})}"
            f"{_field('plak een URL als bron', 'url', fid=f'f-refu-{aid}', placeholder='https://…')}"
            f"<button class='btn'>koppel</button></form>"
            f"<form method='post' action='/action' enctype='multipart/form-data' class='kn-editform'>"
            f"{_hid(csrf, 'kb_atoom_ref_pdf', nxt, {'atom_id': aid})}"
            + _field("… of een PDF als bron", "file", kind="file", fid=f"f-refp-{aid}",
                     attrs="accept='application/pdf'")
            + f"<button class='btn'>koppel PDF</button></form></details>")
    return f"{weergave} {vorm}"


def _stmt_koppels(a: dict, atoms: dict) -> str:
    """De Gekoppeld-rij: supports/links_to/contradicts als klikbare chips die het
    doel-statement openen en erheen scrollen (JS; de href is de anchor-fallback).
    Contradicts visueel onderscheiden (coral rand). Links naar gearchiveerde of
    onbekende atomen renderen niet (geen wees-chips)."""
    delen: list[str] = []
    gezien: set[str] = set()
    for veld, extra in (("supports", ""), ("links_to", ""), ("contradicts", " contra")):
        for tid in a.get(veld) or []:
            if tid in gezien:
                continue
            gezien.add(tid)
            doel = atoms.get(tid)
            if not isinstance(doel, dict):
                continue
            tekst = (doel.get("claim") or tid).strip()
            label = _e(tekst[:48]) + ("…" if len(tekst) > 48 else "")
            titel = " title='spreekt tegen'" if extra else ""
            delen.append(f"<a class='chip kn-koppel{extra}' "
                         f"href='#stmt-{_e(tid)}'{titel}>{label}</a>")
    return " ".join(delen) or "<span class='muted'>—</span>"


def _stmt(aid: str, a: dict, atoms: dict, csrf: str, nxt: str, active_iid: str,
          sugg: str = "", gelinkt: bool = False, spellen: list | None = None) -> str:
    """Eén statement in de bibliotheek (herontwerp dd 2026-07-18, docs/SPEC_kennisbank_statements.html):
    KAAL in het overzicht — alleen de claim-tekst; klik klapt het detail uit met
    datum · bron (één plek) · versie · gekoppeld · tags. Bewerken zit achter een
    '✏️ bewerk'-knop (textarea niet meer standaard open, append-only via kb_atoom_edit).
    Curatie zit sinds de founder-ronde dd 2026-07-18 óók hier: kleine tekstlinks
    'archiveer' en 'naar spel' naast de bewerk-knop (geen bulk-selectie meer).
    De ⠿-handle links (zichtbaar bij hover) draagt de drag&drop-merge. Zonder csrf
    (read-only) geen handle en geen formulieren."""
    try:
        versie = int(a.get("version") or 1)
    except (TypeError, ValueError):
        versie = 1
    vchips = ""
    if a.get("merged_from"):
        vchips += f" <span class='chip muted'>samengesteld uit {len(a['merged_from'])}</span>"
    if a.get("edit_history"):
        vchips += f" <span class='chip muted'>bewerkt {len(a['edit_history'])}×</span>"
    tags = " ".join(f"<span class='chip'>{_e(t)}</span>" for t in a.get("tags") or []) \
        or "<span class='muted'>—</span>"
    body = ""
    if (a.get("body") or "").strip():
        body = (f"<details class='kn-nctrl'><summary>toon de inhoud</summary>"
                f"<div class='kn-ann'>{_e(a['body']).replace(chr(10), '<br>')}</div></details>")

    bewerk = ""
    if csrf:
        bewerk = (f"<details class='kn-editable'><summary>✏️ bewerk</summary>"
                  f"<form method='post' action='/action' class='kn-editform'>"
                  f"{_hid(csrf, 'kb_atoom_edit', nxt, {'atom_id': aid})}"
                  f"<textarea name='claim' rows='4'>{_e(a.get('claim') or '')}</textarea>"
                  f"<button class='btn ok'>Bewaar (nieuwe versie)</button></form></details>")
        # Curatie per statement (founder dd 2026-07-18, verving de selectiebalk): archiveren
        # als tekstlink; 'naar spel' klapt een spel-keuze uit (alleen bij open spellen).
        bewerk += (f"<form method='post' action='/action' class='kn-stmtactie'>"
                   f"{_hid(csrf, 'kb_atoom_archive', nxt, {'atom_id': aid})}"
                   f"<button class='kn-actlink' title='uit de lijst, nooit weg — "
                   f"verwijderd maar onthouden (black-list) — terugzetten kan via ⚙'>🗑 verwijder</button></form>")
        if spellen:
            opties = "".join(
                f"<option value='{_e(s['id'])}'>{_e(s.get('hunch') or s['id'])}</option>"
                for s in spellen)
            bewerk += (f"<details class='kn-spelvorm kn-stmtactie'>"
                       f"<summary title='koppel dit statement aan een open spel'>🎲 naar spel</summary>"
                       f"<form method='post' action='/action' class='kn-editform'>"
                       f"{_hid(csrf, 'kb_atoom_naar_spel', nxt, {'atoom': aid})}"
                       f"<select name='sid'>{opties}</select>"
                       f"<button class='btn'>koppel aan dit spel</button></form></details>")
        bewerk = f"<div class='kn-stmtacties'>{bewerk}</div>"

    # Koppel-brug naar het open inzicht (A4: geen dubbel pad als de kaart al gelinkt is).
    brug = ""
    if active_iid and csrf:
        sugg_chip = ""
        if sugg == "support" and not gelinkt:
            sugg_chip = "<span class='chip'>past mogelijk</span> "
        elif sugg == "counter" and not gelinkt:
            sugg_chip = "<span class='chip muted'>spreekt mogelijk tegen</span> "
        knoppen = ("<span class='muted kn-al'>al gekoppeld</span>" if gelinkt else
                   f"<form method='post' action='/action' class='kn-unlink'>"
                   f"{_hid(csrf, 'kb_link', nxt, {'iid': active_iid, 'atom_id': aid, 'stance': 'support'})}"
                   f"<button class='btn ok'>+ steunt</button></form>"
                   f"<form method='post' action='/action' class='kn-unlink'>"
                   f"{_hid(csrf, 'kb_link', nxt, {'iid': active_iid, 'atom_id': aid, 'stance': 'counter'})}"
                   f"<button class='btn no'>+ tegen</button></form>")
        brug = f"<div class='kn-nctrls'>{sugg_chip}{knoppen}</div>"

    handle = ("<span class='kn-handle' draggable='true' "
              "title='sleep op een ander statement om te mergen'>⠿</span>" if csrf else "")
    return (f"<div class='kn-stmt' id='stmt-{_e(aid)}' data-id='{_e(aid)}'>"
            f"{handle}"
            f"<details class='kn-stmtbody'>"
            f"<summary class='kn-stmttekst'>{_e(a.get('claim'))}</summary>"
            f"<div class='kn-stmtdetail'><dl class='kn-dl'>"
            f"<dt>Datum</dt><dd>{_stmt_datum(a)}</dd>"
            f"<dt>Bron</dt><dd>{_stmt_bron(aid, a, csrf, nxt)}</dd>"
            + (f"<dt>Herkomst</dt><dd><span class='chip muted'>"
               f"{_e(a.get('provenance') or '')}</span> "
               f"{_e(a.get('provenance_note') or '')}</dd>"
               if (a.get("provenance_note") or "").strip() else "")
            + f"<dt>Versie</dt><dd>v{versie}{vchips}</dd>"
            f"<dt>Gekoppeld</dt><dd>{_stmt_koppels(a, atoms)}</dd>"
            f"<dt>Tags</dt><dd>{tags}</dd>"
            f"</dl>{body}{bewerk}{brug}</div></details></div>")


def _bieb_results(st, atoms: dict, q: str, hub: str, active_ins: dict | None,
                  csrf: str) -> str:
    """De doorzoekbare statements-lijst (het fragment dat /kennisbank/search vervangt).
    Zoeken = typen (spec): matcht op inhoud, bron, reference ÉN tags over de verse volledige
    bibliotheek; markeert steun/tegen-suggesties als er een inzicht actief is
    (anti-cherry-pick, beide kanten)."""
    ql = (q or "").strip().lower()
    if ql:
        def _raak(a: dict) -> bool:
            return (ql in (a.get("claim") or "").lower()
                    or ql in (a.get("source") or "").lower()
                    or ql in (a.get("reference") or "").lower()
                    or any(ql in (t or "").lower() for t in a.get("tags") or []))
        rijen = [(aid, a) for aid, a in atoms.items() if _raak(a)]
        kop = f"{len(rijen)} statement(s) voor “{_e(q)}”"
    elif hub:
        rijen = [(aid, a) for aid, a in atoms.items() if subject_van(a) == hub]
        kop = f"{len(rijen)} in ‘{_e(hub)}’"
    else:
        rijen = list(atoms.items())
        kop = f"{len(rijen)} statements"
    rijen.sort(key=lambda t: (t[1].get("created_at") or "", t[0]), reverse=True)
    getoond = rijen[:_ZOEK_MAX]

    sugg: dict[str, str] = {}
    active_iid = ""
    al_gelinkt: set = set()
    if active_ins is not None:
        active_iid = active_ins["id"]
        al_gelinkt = {l.get("atom_id") for l in active_ins.get("evidence") or []}
        # Markeer kandidaten met RECALL (woord-overlap), bewust ZONDER LLM: dit fragment draait
        # op elke toetsaanslag (debounced live-search), dus een stance-LLM-call per zoekactie zou
        # de ladder platleggen. De mens kiest de richting expliciet met + steunt / + tegen (dat
        # ís de anti-cherry-pick-keuze). De support/counter-splitsing via de LLM blijft in het
        # spel, waar hij één keer draait.
        for k in gather(active_ins.get("title") or "", atoms, reason_fn=lambda *a, **k: None):
            if k["atom_id"] not in al_gelinkt:
                sugg[k["atom_id"]] = "support"       # 'past mogelijk' — richting kiest de mens
    nxt = f"/kennisbank?id={active_iid}" if active_iid else (f"/kennisbank?hub={hub}" if hub else "/kennisbank")
    spellen = st.spel.open_spellen()[:8] if csrf else []
    kaarten = "".join(_stmt(aid, a, atoms, csrf, nxt, active_iid, sugg.get(aid, ""),
                            gelinkt=(aid in al_gelinkt), spellen=spellen)
                      for aid, a in getoond)
    lijst = (f"<div class='kn-lijst'>{kaarten}</div>" if kaarten
             else "<p class='muted'>Geen statements gevonden.</p>")
    meer = (f"<p class='muted'>… en nog {len(rijen) - _ZOEK_MAX} meer — verfijn je zoekterm.</p>"
            if len(rijen) > _ZOEK_MAX else "")
    return f"<p class='muted'>{kop}</p>{lijst}{meer}"
def _bibliotheek_rechts(st, atoms: dict, q: str, hub: str, active_ins: dict | None,
                        csrf: str) -> str:
    """De rechterkolom (Signals): live smart-search + tags-pill + onderwerp-chips +
    resultaten + archief. De zoekbox vervangt (JS, debounced) alleen #kn-biebresults over
    de verse bibliotheek. Curatie (archiveren, naar spel) zit sinds de founder-ronde
    dd 2026-07-18 per statement in het uitklap-detail — geen bulk-selectiebalk meer."""
    active_iid = active_ins["id"] if active_ins else ""
    per_hub: dict[str, int] = {}
    for a in atoms.values():
        h = subject_van(a)
        if h:
            per_hub[h] = per_hub.get(h, 0) + 1
    # Eén taal: TAGS, geen aparte onderwerpen meer in de UI (founder, 19 jul). Alle tags
    # als A–Z-lijst met aantallen; klik = zoeken (bestaand kn-tagchip-pad). De wekelijkse
    # tag-onderhoudslus van de Library houdt deze lijst schoon.
    tel: dict[str, int] = {}
    for a in atoms.values():
        for t in (a.get("tags") or []):
            if t.startswith("hint:"):
                continue
            tel[t] = tel.get(t, 0) + 1
    taglijst = "".join(
        f"<button type='button' class='kn-tagchip' data-tag='{_e(t)}'>{_e(t)}"
        f"<span class='kn-tagtal'>{n}</span></button>"
        for t, n in sorted(tel.items(), key=lambda kv: kv[0].lower()))
    # Open weekvoorstellen van de Library → één rustige regel naar de review.
    onderhoud = ""
    try:
        from nooch_village.tag_onderhoud import TagVoorstellenStore
        n_open = len(TagVoorstellenStore(f"{st.dd}/tag_voorstellen.json").open_voorstellen())
        if n_open:
            onderhoud = (f"<p class='muted'><a href='/kennisbank/tags'>🏷 {n_open} "
                         f"tag-voorstel(len) van de Library — nakijken</a></p>")
    except Exception:
        pass
    tags = (f"<details class='kn-tags'{' open' if hub else ''}>"
            f"<summary>alle tags (A–Z)</summary>"
            f"<div class='c2-sec kn-taglijst'>{taglijst}"
            f"<a class='chip-opt' href='/kennisbank/tags' title='wekelijkse schoonmaaklus: "
            f"samenvoegen, opschonen, abstraheren'>🏷 onderhoud</a></div></details>{onderhoud}")
    zoekbox = (f"<input id='kn-search' class='kn-searchbox' type='search' value='{_e(q)}' "
               f"placeholder='zoek in statements, bronnen en tags — gewoon typen…' "
               f"autocomplete='off' "
               f"data-active='{_e(active_iid)}' data-hub='{_e(hub)}'>")
    results = _bieb_results(st, atoms, q, hub, active_ins, csrf)
    nxt = f"/kennisbank?id={active_iid}" if active_iid else (f"/kennisbank?hub={hub}" if hub else "/kennisbank")
    # Tags-pill naast de Signals-kop (founder dd 2026-07-18): alle voorkomende tags als
    # klikbare chips; klik zet de tag in het live-zoekveld (JS) — filteren loopt via het
    # bestaande zoekpad, geen nieuwe backend.
    alle_tags = sorted({t for a in atoms.values() for t in (a.get("tags") or []) if t})
    tagpill = ""
    if alle_tags:
        tchips = "".join(f"<button type='button' class='kn-tagchip' data-tag='{_e(t)}'>"
                         f"{_e(t)}</button>" for t in alle_tags)
        tagpill = (f"<details class='kn-tagpill'><summary title='filter op een tag'>🏷 tags"
                   f"</summary><div class='kn-tagchips'>{tchips}</div></details>")
    # Taak 2: met een open inzicht leest de rechterkolom als "hier koppel je bewijs" — een
    # expliciete kop + uitleg die de brug tussen 'inzicht links' en 'bewijs rechts' benoemt.
    if active_ins is not None:
        kop = (f"<h2>🔎 Koppel bewijs</h2>"
               f"<p class='muted kn-brugkop'>Je hebt links <b>“{_e((active_ins.get('title') or '')[:60])}”</b> "
               f"open. Zoek hier een kaart en klik <span class='chip'>+ steunt</span> of "
               f"<span class='chip muted'>+ tegen</span> — kandidaten staan al gemarkeerd. "
               f"Gekoppeld bewijs verschijnt links onder “Het bewijs”.</p>")
    else:
        # Founder dd 2026-07-18: rustige kop "Signals" (kn-koprustig — geen vet/uppercase),
        # zonder uitlegtekst; de tags-pill staat ernaast.
        kop = f"<div class='kn-koprij'><h2 class='kn-koprustig'>Signals</h2>{tagpill}</div>"
    return (f"{kop}{zoekbox}{tags}"
            f"<div id='kn-biebresults'>{results}</div>"
            f"{_merge_modal(csrf, nxt)}"
            f"{_gearchiveerd_uitklap(st, hub, csrf)}"
            f"{_ongesorteerd_bakje(atoms, [], csrf)}")


def _merge_modal(csrf: str, nxt: str) -> str:
    """De merge-modal (spec): na een drop toont JS deze dialoog — radio-keuze welke van de
    twee teksten de default wordt, een prefilled textarea om aan te passen, en annuleer /
    'merge → nieuwe versie'. Submit = POST /action kb_atoom_merge (target_id, source_id,
    tekst, csrf, next). Eén exemplaar per pagina; JS vult de teksten en ids bij een drop.
    Zonder csrf (read-only) rendert de modal niet — er valt dan ook niets te slepen."""
    if not csrf:
        return ""
    return (
        f"<div class='kn-overlay' id='kn-overlay' hidden></div>"
        f"<div class='kn-modal' id='kn-modal' hidden role='dialog' aria-modal='true' "
        f"aria-labelledby='kn-modaltitel'>"
        f"<h2 id='kn-modaltitel'>Statements mergen</h2>"
        f"<p class='muted'>Kies welke tekst de standaard wordt (bronnen, koppelingen en "
        f"tags van allebei blijven bewaard; dit wordt een nieuwe versie).</p>"
        f"<form method='post' action='/action' id='kn-mergeform'>"
        f"{_hid(csrf, 'kb_atoom_merge', nxt)}"
        f"<input type='hidden' name='target_id' value=''>"
        f"<input type='hidden' name='source_id' value=''>"
        f"<label class='kn-opt on' id='kn-opta' for='f-kn-keuze-a'>"
        f"<input type='radio' name='keuze' value='a' id='f-kn-keuze-a' checked>"
        f"<span></span></label>"
        f"<label class='kn-opt' id='kn-optb' for='f-kn-keuze-b'>"
        f"<input type='radio' name='keuze' value='b' id='f-kn-keuze-b'>"
        f"<span></span></label>"
        f"{_field('eventueel nog aanpassen', 'tekst', kind='textarea', fid='f-kn-mergetekst')}"
        f"<div class='kn-modalbtns'>"
        f"<button type='button' class='btn' id='kn-mergecancel'>annuleer</button>"
        f"<button class='btn ok'>merge → nieuwe versie</button></div></form></div>")


def render_kennisbank_search(st, q: str, hub: str, active_iid: str,
                             csrf_token: str = "") -> str:
    """Fragment voor het live-search-endpoint: alleen de resultatenlijst (#kn-biebresults),
    over de VERSE volledige bibliotheek."""
    atoms = load_atoms(st.dd)
    active_ins = st.kennisbank.get(active_iid) if active_iid else None
    return _bieb_results(st, atoms, q, hub, active_ins, csrf_token)


_KN_SEARCH_JS = """<script>(function(){
 var box=document.getElementById('kn-search');
 var host=document.getElementById('kn-biebresults'); var t;
 function run(cb){
   if(!box||!host)return;
   var u='/kennisbank/search?q='+encodeURIComponent(box.value)
     +'&active='+encodeURIComponent(box.dataset.active||'')
     +'&hub='+encodeURIComponent(box.dataset.hub||'');
   fetch(u,{credentials:'same-origin'}).then(function(r){return r.text();})
     .then(function(h){host.innerHTML=h; if(typeof cb==='function')cb();});
 }
 if(box) box.addEventListener('input',function(){clearTimeout(t);t=setTimeout(run,250);});
 // Tags-pill: klik op een tag-chip zet de tag in het live-zoekveld en triggert het
 // bestaande zoekpad (input-event) — filteren zonder nieuwe backend.
 document.addEventListener('click',function(e){
   var b=e.target.closest&&e.target.closest('.kn-tagchip'); if(!b||!box)return;
   box.value=b.dataset.tag||'';
   box.dispatchEvent(new Event('input',{bubbles:true}));
   var d=b.closest('details'); if(d)d.open=false;
 });
 // Gekoppeld-chips: open het doel-statement en scroll erheen (staat het buiten de
 // huidige zoekfilter, dan eerst de filter wissen en opnieuw laden).
 function openStmt(id){
   var el=document.querySelector('.kn-stmt[data-id="'+id+'"]');
   if(!el&&box&&box.value){box.value='';run(function(){openStmt(id);});return;}
   if(!el)return;
   var d=el.querySelector('.kn-stmtbody'); if(d)d.open=true;
   el.scrollIntoView({behavior:'smooth',block:'center'});
 }
 document.addEventListener('click',function(e){
   var a=e.target.closest&&e.target.closest('.kn-koppel'); if(!a)return;
   e.preventDefault();
   openStmt((a.getAttribute('href')||'').replace('#stmt-',''));
 });
 // ⠿ drag & drop mergen (HTML5; gedelegeerd zodat het de live-search-vervanging overleeft).
 var dragSrc=null;
 function stmtVan(e){return e.target&&e.target.closest?e.target.closest('.kn-stmt'):null;}
 document.addEventListener('dragstart',function(e){
   if(!(e.target.closest&&e.target.closest('.kn-handle')))return;
   var s=stmtVan(e); if(!s)return;
   dragSrc=s.dataset.id; s.classList.add('dragging');
   e.dataTransfer.effectAllowed='move';
   try{e.dataTransfer.setData('text/plain',dragSrc);}catch(_){}
 });
 document.addEventListener('dragend',function(){
   dragSrc=null;
   document.querySelectorAll('.kn-stmt.dragging,.kn-stmt.dragover').forEach(function(x){
     x.classList.remove('dragging','dragover');});
 });
 document.addEventListener('dragover',function(e){
   var s=stmtVan(e);
   if(s&&dragSrc&&s.dataset.id!==dragSrc){e.preventDefault();s.classList.add('dragover');}
 });
 document.addEventListener('dragleave',function(e){
   var s=stmtVan(e); if(s)s.classList.remove('dragover');
 });
 document.addEventListener('drop',function(e){
   var s=stmtVan(e); if(!s||!dragSrc)return;
   e.preventDefault(); s.classList.remove('dragover');
   if(s.dataset.id!==dragSrc) openMerge(dragSrc,s.dataset.id);
 });
 // De merge-modal: radio kiest de default-tekst, de textarea is wat er wordt opgeslagen.
 var modal=document.getElementById('kn-modal'), overlay=document.getElementById('kn-overlay');
 function tekstVan(id){
   var el=document.querySelector('.kn-stmt[data-id="'+id+'"] .kn-stmttekst');
   return el?el.textContent.trim():'';
 }
 function kies(a){
   var oa=document.getElementById('kn-opta'), ob=document.getElementById('kn-optb');
   oa.classList.toggle('on',a); ob.classList.toggle('on',!a);
   document.getElementById('f-kn-keuze-'+(a?'a':'b')).checked=true;
   document.getElementById('f-kn-mergetekst').value=(a?oa:ob).querySelector('span').textContent;
 }
 function openMerge(srcId,tgtId){
   if(!modal)return;
   var f=document.getElementById('kn-mergeform');
   f.querySelector('[name=target_id]').value=tgtId;
   f.querySelector('[name=source_id]').value=srcId;
   document.getElementById('kn-opta').querySelector('span').textContent=tekstVan(srcId);
   document.getElementById('kn-optb').querySelector('span').textContent=tekstVan(tgtId);
   kies(true);
   overlay.hidden=false; modal.hidden=false;
 }
 function sluitModal(){ if(modal){overlay.hidden=true; modal.hidden=true;} }
 if(modal){
   document.getElementById('kn-opta').addEventListener('click',function(){kies(true);});
   document.getElementById('kn-optb').addEventListener('click',function(){kies(false);});
   document.getElementById('kn-mergecancel').addEventListener('click',sluitModal);
   overlay.addEventListener('click',sluitModal);
   document.addEventListener('keydown',function(e){if(e.key==='Escape')sluitModal();});
 }
})();</script>"""


def _gearchiveerd_uitklap(st, hub: str, csrf: str) -> str:
    """⚙-paneel (founder, 19 jul): 'gearchiveerd' is eigenlijk VERWIJDERD — we bewaren ze
    alleen zodat ze niet opnieuw binnenkomen (black-list, zelfde idee als de verboden
    woorden in de woordenschat). Hoort niet in de hoofdflow; terugzetten kan altijd."""
    from nooch_village.kennisbank import load_atoms as _la
    alles = _la(st.dd, include_archived=True)
    archief = {aid: a for aid, a in alles.items()
               if isinstance(a, dict) and a.get("archived")}
    if not archief:
        return ""
    nxt = f"/kennisbank?hub={hub}" if hub else "/kennisbank"
    rows = ""
    for aid, a in sorted(archief.items())[:20]:
        rows += (f"<div class='kn-lrow kn-blrow'>"
                 f"<div class='kn-lt'>{_e(a.get('claim'))}"
                 f"<span class='kn-src'>{_e(a.get('source') or '')}</span></div>"
                 f"<form method='post' action='/action'>"
                 f"{_hid(csrf, 'kb_atoom_unarchive', nxt, {'atom_id': aid})}"
                 f"<button class='btn'>Zet terug</button></form>"
                 f"<form method='post' action='/action'>"
                 f"{_hid(csrf, 'kb_atoom_purge', nxt, {'atom_id': aid})}"
                 f"<button class='btn no' title='echt weg — hierna kan dezelfde tekst in "
                 f"principe ooit opnieuw binnenkomen'>🔥 definitief</button></form></div>")
    meer = (f"<p class='muted'>… en nog {len(archief) - 20} meer.</p>"
            if len(archief) > 20 else "")
    leegknop = (f"<form method='post' action='/action' class='kn-blleeg'>"
                f"{_hid(csrf, 'kb_blacklist_leeg', nxt)}"
                f"<button class='btn no' title='gooi alle {len(archief)} definitief weg; "
                f"wat al geborgd is in andere signals verlies je daarmee niet'>"
                f"🔥 Leeg de hele lijst definitief ({len(archief)})</button></form>")
    return (f"<details class='kn-panel kn-settings'><summary>⚙ <span class='muted'>"
            f"instellingen</span></summary>"
            f"<h3>🗑 Verwijderd ({len(archief)})</h3>"
            f"<p class='muted'>Verwijderd maar onthouden (black-list): deze signals komen "
            f"niet opnieuw binnen. Terugzetten kan altijd; 🔥 definitief gooit ze echt weg "
            f"(en dan kan dezelfde tekst in principe ooit opnieuw binnenkomen).</p>"
            f"{leegknop}{rows}{meer}</details>")


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
            f"<p class='muted'>Zonder onderwerp tellen ze niet mee in clusters en "
            f"zoekopdrachten. De verrijkingsronde (kb_verrijk) sorteert ze automatisch; "
            f"dit is het restje waar de LLM niet uitkwam.</p>{rows}{meer}</details>")


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
                      open_: str = "", cluster: int = 0, flip: bool = False,
                      sug: int = 0) -> str:
    atoms = load_atoms(st.dd)
    inzichten = st.kennisbank.all()
    by_id = {i["id"]: i for i in inzichten}
    # Een lopende hunch/speel-set houdt de speel-zone vanzelf open.
    if (hunch or speel) and not open_:
        open_ = "speel"
    active_ins = st.kennisbank.get(kid) if kid else None
    active_iid = active_ins["id"] if active_ins else ""
    related_ids = {r["insight_id"] for r in (active_ins or {}).get("related") or []}
    cards = "".join(_topic_card(i, atoms, csrf_token, active_iid, related_ids)
                    for i in inzichten if i["id"] != active_iid) or (
        "<p class='muted'>Nog geen inzichten. Verifieer de voorzet hierboven (zodra er "
        "signals zijn), of seed de eerste vulling: "
        "<code>python -m nooch_village.kennisbank_seed --apply</code></p>")

    actiebalk = _actiebalk(open_, st, atoms, inzichten, hunch, speel, cluster, csrf_token)
    toast = _nieuw_toast(nieuw, atoms)

    # LINKS: het geopende inzicht (detail, evt. geflipt) bovenaan, daaronder de inzicht-lijst.
    # Zonder open detail neemt de suggestiekaart de bovenste plek (founder, 19 jul).
    detail = _inzicht_detail(active_ins, atoms, csrf_token, by_id, flip=flip) if active_ins else ""
    suggestie = "" if active_ins else _suggestie_kaart(atoms, inzichten, sug, csrf_token,
                                                       data_dir=st.dd)
    if active_iid:
        lijst_kop = ("<h2>🔗 Koppel een gerelateerd inzicht</h2>"
                     "<p class='muted kn-brugkop'>Kies hieronder een inzicht dat "
                     "<b>“" + _e((active_ins.get('title') or '')[:50]) + "”</b> steunt of "
                     "tegenspreekt. Bij twee of meer kun je er samen een <b>meta-inzicht</b> "
                     "spelen (zie de sectie in het detail).</p>")
    else:
        lijst_kop = "<h2>Insights</h2>"
    links = (f"<div class='kn-col-left'>{detail}{suggestie}"
             f"{lijst_kop}{cards}</div>")
    # RECHTS: de bibliotheek met live smart-search + de koppel-brug (als er een inzicht open is).
    rechts = f"<div class='kn-col-right'>{_bibliotheek_rechts(st, atoms, q, hub, active_ins, csrf_token)}</div>"

    # Founder dd 2026-07-18: geen groene succes-banner meer op deze pagina — de uitkomst is
    # zelf zichtbaar (de link/kaart verschijnt). Fouten (✗ …) blijven wél zichtbaar: daar is
    # er niets op de pagina dat de mislukking toont. Het msg-mechanisme zelf blijft intact.
    foutbalk = _banner(msg) if str(msg or "").lstrip().startswith("✗") else ""
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>🔮 Oracle</h1>"
            f"{actiebalk}{foutbalk}{toast}"
            f"<div class='kn-cols'>{links}{rechts}</div>"
            f"<p class='muted'>Elke zekerheid schuift mee als er info bijkomt.</p></div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>{_KN_SEARCH_JS}")
    return _page("Oracle", inner)
