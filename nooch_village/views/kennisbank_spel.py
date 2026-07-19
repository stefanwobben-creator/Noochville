"""Het inzicht-spel (/kennisbank/spel?sid=...) — speel in je eigen AI (copy-paste).

De flow van het prototype (besluit Stefan): (1) cureer je hand — kaarten erbij, richting
draaien, tegenbewijs laten staan; (2) kopieer de gegenereerde prompt en voer de dialoog
in je eigen AI; (3) plak het === INZICHT ===-blok terug en munt het inzicht (v1.0, of een
nieuwe versie bij herformuleren). Geen LLM-call in de browser voor de dialoog zelf.

Spelronde dd 2026-07-19 (founder): de rechterkolom kopieert het Oracle-patroon — een
LIVE zoekbalk (blijft staan na een toevoeging; het fragment /kennisbank/spel/search
vervangt alleen de resultaten) waarin kaarten die al in het spel zitten een subtiel
groen (steunt) of rood (spreekt tegen) achtergrondje dragen. Daaronder ➕ Bron toevoegen
(zelfde kb_bron_add-pad als Oracle: bron → kaartjes → even nakijken). De vijf-regel is
een ZACHTE hint: boven de vijf kaarten een vriendelijke nudge over onafhankelijke
stemmen, nooit een blokkade — een zesde kaart als tegenbewijs weiger je nooit.
"""
from __future__ import annotations

import urllib.parse

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.kennisbank import load_atoms
from nooch_village.kennisbank_spel import gather, spel_prompt, steun_onafhankelijk


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _hand(spel: dict, atoms: dict, csrf: str, nxt: str, open_: bool) -> str:
    """De gecureerde set: per kaart richting draaien (één klik) en verwijderen."""
    rows = ""
    for k in spel.get("set") or []:
        a = atoms.get(k["atom_id"]) or {}
        cls = "counter" if k.get("stance") == "counter" else "support"
        lbl = "spreekt tegen" if cls == "counter" else "steunt"
        ann = (f"<span class='kn-ann'>notitie: {_e(k.get('annotation'))}</span>"
               if k.get("annotation") else "")
        ctrl = ""
        if open_:
            ctrl = (f"<div class='kn-nctrls'>"
                    f"<form method='post' action='/action' class='kn-unlink'>"
                    f"{_hid(csrf, 'kb_spel_flip', nxt, {'sid': spel['id'], 'atom_id': k['atom_id']})}"
                    f"<button class='btn' title='draai de richting om'>↔ {lbl}</button></form>"
                    f"<form method='post' action='/action' class='kn-unlink'>"
                    f"{_hid(csrf, 'kb_spel_remove', nxt, {'sid': spel['id'], 'atom_id': k['atom_id']})}"
                    f"<button class='btn' title='verwijder uit je hand'>×</button></form></div>")
        rows += (f"<div class='kn-note {cls}'><span class='kn-dot'></span>"
                 f"<div class='kn-ntext'>{_e(a.get('claim'))}"
                 f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}</span>{ann}</div>"
                 f"{ctrl}</div>")
    return rows or "<p class='muted'>Nog geen kaarten in je hand.</p>"


def _zoek_resultaten(spel: dict, atoms: dict, zoek: str, csrf: str) -> str:
    """Het live-fragment (#kn-spelresults): kandidaten bij de zoekterm. Bewust ZONDER
    stance-LLM-call — dit draait op elke toetsaanslag (debounced), dus de richting kiest
    de mens per kaart (zelfde afweging als de Oracle-live-search). Kaarten die al in het
    spel zitten renderen mét subtiel groen/rood achtergrondje en een ↔-flip in plaats
    van een koppel-formulier — zo zie je in je zoekresultaat direct wat er al in zit."""
    zoek = (zoek or "").strip()
    if not zoek:
        return ("<p class='muted'>Typ hierboven om kaarten in de bibliotheek te vinden — "
                "resultaten verschijnen direct en de balk blijft staan na een toevoeging.</p>")
    in_set = {k["atom_id"]: k for k in spel.get("set") or []}
    kandidaten = gather(zoek, atoms, reason_fn=lambda *a, **k: None)
    if not kandidaten:
        return "<p class='muted'>Geen kaarten gevonden. Probeer een ander woord.</p>"
    nxt = f"/kennisbank/spel?sid={spel['id']}&zoek={urllib.parse.quote(zoek)}"
    rows = ""
    for k in kandidaten:
        aid = k["atom_id"]
        a = atoms.get(aid) or {}
        tekst = (f"<div class='kn-lt'>{_e(a.get('claim'))}"
                 f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}</span></div>")
        if aid in in_set:
            stance = in_set[aid].get("stance") or "support"
            cls = "kn-inhand-sup" if stance == "support" else "kn-inhand-cou"
            lbl = "in je spel · steunt" if stance == "support" else "in je spel · spreekt tegen"
            rows += (f"<div class='kn-lrow {cls}'>{tekst}"
                     f"<span class='chip muted'>{lbl}</span>"
                     f"<form method='post' action='/action' class='kn-unlink'>"
                     f"{_hid(csrf, 'kb_spel_flip', nxt, {'sid': spel['id'], 'atom_id': aid})}"
                     f"<button class='btn' title='draai de richting om'>↔</button></form></div>")
        else:
            keuze = "".join(
                f"<option value='{s}'>{lbl}</option>"
                for s, lbl in (("support", "steunt"), ("counter", "spreekt tegen")))
            rows += (f"<form method='post' action='/action' class='kn-lrow'>"
                     f"{_hid(csrf, 'kb_spel_add', nxt, {'sid': spel['id'], 'atom_id': aid})}"
                     f"{tekst}<select name='stance'>{keuze}</select>"
                     f"<input name='annotation' placeholder='waarom? (optioneel)'>"
                     f"<button class='btn ok'>Koppel</button></form>")
    return rows


_SPEL_SEARCH_JS = """<script>(function(){
 var box=document.getElementById('kn-spelsearch');
 var host=document.getElementById('kn-spelresults'); var t;
 function run(){
   if(!box||!host)return;
   var u='/kennisbank/spel/search?sid='+encodeURIComponent(box.dataset.sid||'')
     +'&zoek='+encodeURIComponent(box.value);
   fetch(u,{credentials:'same-origin'}).then(function(r){return r.text();})
     .then(function(h){host.innerHTML=h;});
 }
 if(box) box.addEventListener('input',function(){clearTimeout(t);t=setTimeout(run,250);});
})();</script>"""


def _zoek_kolom(spel: dict, atoms: dict, zoek: str, csrf: str) -> str:
    """De rechterkolom (Oracle-patroon, founder dd 2026-07-19): live zoekbalk + resultaten
    + ➕ Bron toevoegen. De zoekbalk blijft staan: het fragment vervangt alleen
    #kn-spelresults, en na een Koppel-POST komt de pagina terug mét dezelfde zoekterm
    (de zoekterm reist mee in `next`)."""
    kop = (f"<div class='kn-koprij'><h2 class='kn-koprustig'>🔎 Koppel kaarten</h2></div>"
           f"<p class='muted kn-brugkop'>Zoek in de bibliotheek en koppel zonder opnieuw "
           f"te zoeken. Wat al in je spel zit is gemarkeerd: "
           f"<span class='chip'>groen steunt</span> "
           f"<span class='chip muted'>rood spreekt tegen</span>.</p>")
    zoekbox = (f"<input id='kn-spelsearch' class='kn-searchbox' type='search' "
               f"value='{_e(zoek)}' placeholder='zoek kaarten — gewoon typen…' "
               f"autocomplete='off' data-sid='{_e(spel['id'])}'>")
    results = _zoek_resultaten(spel, atoms, zoek, csrf)
    # Zelfde ingang als op Oracle (kb_bron_add → kaartjes → even nakijken): mis je bewijs
    # tijdens het spel, dan hoef je de pagina niet uit om een bron toe te voegen.
    from nooch_village.views.kennisbank import _bron_toevoegen
    bron = (f"<details class='kn-panel'><summary>➕ Bron toevoegen</summary>"
            f"<p class='muted'>Mis je bewijs? Voeg hier een bron toe — die wordt in "
            f"kaartjes geknipt; na het nakijken koppel je ze via 🎲 naar spel of "
            f"hierboven aan dit spel.</p>{_bron_toevoegen(csrf)}</details>")
    return (f"{kop}{zoekbox}<div id='kn-spelresults'>{results}</div>{bron}"
            f"{_SPEL_SEARCH_JS}")


def render_kennisbank_spel_search(st, sid: str, zoek: str = "",
                                  csrf_token: str = "") -> str:
    """Fragment voor het live-zoek-endpoint op de spel-pagina: alleen de resultatenlijst
    (#kn-spelresults), over de verse bibliotheek en de verse hand."""
    spel = st.spel.get(sid)
    if spel is None:
        return "<p class='muted'>Spel niet gevonden.</p>"
    return _zoek_resultaten(spel, load_atoms(st.dd), zoek, csrf_token)


def render_kennisbank_spel(st, sid: str, zoek: str = "", csrf_token: str = "",
                           msg: str = "") -> str:
    spel = st.spel.get(sid)
    if spel is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 f"<p class='muted'>Spel niet gevonden. <a href='/kennisbank'>← terug</a></p>"
                 f"</div></div>")
        return _page("Speel een inzicht", inner)
    atoms = load_atoms(st.dd)
    nxt = f"/kennisbank/spel?sid={sid}"
    open_ = spel.get("status") != "gemunt"

    nudge = ""
    indep = steun_onafhankelijk(spel, atoms)
    if open_ and indep < 3:
        wat = "één onafhankelijke steunbron" if indep == 1 else f"{indep} onafhankelijke steunbronnen"
        if indep == 0:
            wat = "nog geen steunbron"
        nudge = (f"<div class='kn-caveat'>Nog dun: {wat} in je hand. Drie losse bronnen "
                 f"maken een inzicht stevig — overweeg meer bewijs te koppelen. "
                 f"Spelen mag altijd.</div>")
    # De zachte vijf (founder, 19 jul): een richtgetal, geen blokkade. De kwaliteit hangt
    # aan onafhankelijke stemmen, niet aan het aantal kaarten — en een zesde kaart als
    # tegenbewijs weiger je nooit.
    n_hand = len(spel.get("set") or [])
    if open_ and n_hand > 5:
        nudge += (f"<div class='kn-caveat'>{n_hand} kaarten in je hand — meer is hier "
                  f"niet per se beter: het verdict telt onafhankelijke stemmen "
                  f"(nu {indep}). Kies je sterkste vijf, de rest verwatert het inzicht. "
                  f"Tegenbewijs mag er altijd bij.</div>")

    stappen = ""
    if open_:
        prompt = spel_prompt(spel, atoms)
        stappen = (
            f"<div class='kn-sec'><div class='kn-sectitle'>2 · Speel het in je eigen AI</div>"
            f"<p class='muted'>Kopieer de prompt en voer de dialoog in ChatGPT, Claude of je "
            f"eigen AI. Die duwt je — en eindigt met een blok.</p>"
            f"<textarea id='spel-prompt' class='kn-prompt' readonly rows='9'>{_e(prompt)}</textarea>"
            f"<button class='btn' id='spel-copy'>📋 Kopieer prompt</button>"
            f"<script>document.getElementById('spel-copy').onclick=function(){{"
            f"var t=document.getElementById('spel-prompt');t.select();"
            f"if(navigator.clipboard)navigator.clipboard.writeText(t.value);"
            f"this.textContent='✓ Gekopieerd';}};</script></div>"
            f"<div class='kn-sec'><div class='kn-sectitle'>3 · Plak het resultaat</div>"
            f"<form method='post' action='/action'>"
            f"{_hid(csrf_token, 'kb_spel_finish', nxt, {'sid': sid})}"
            f"{_field('plak hier het === INZICHT ===-blok', 'blok', kind='textarea', fid='f-spel-blok')}"
            f"<button class='btn ok'>"
            + ("Maak nieuwe versie" if spel.get("reformulate_of") else "Maak het inzicht")
            + f" →</button></form></div>")
    elif spel.get("insight_id"):
        stappen = (f"<p><a class='btn ok' href='/kennisbank?id={_e(spel['insight_id'])}'>"
                   f"Bekijk het inzicht →</a></p>")

    her = " · herformuleert een bestaand inzicht" if spel.get("reformulate_of") else ""
    links = (f"<div class='kn-col-left'>{nudge}"
             f"<div class='kn-sec'><div class='kn-sectitle'>1 · Je hand "
             f"({n_hand} kaarten)</div>"
             f"<p class='muted'>Draai de richting waar nodig en laat het tegenbewijs staan — "
             f"daar scherp je aan.</p>"
             f"{_hand(spel, atoms, csrf_token, nxt, open_)}</div>{stappen}</div>")
    rechts = (f"<div class='kn-col-right'>"
              f"{_zoek_kolom(spel, atoms, zoek, csrf_token) if open_ else ''}</div>")
    main = (f"<div class='c2-main'><div class='c2-bar'>"
            f"<a href='/kennisbank'>← Oracle</a></div>"
            f"<h1>🎲 Speel een inzicht</h1>"
            f"<p class='muted'>Vermoeden: <b>{_e(spel.get('hunch'))}</b>{her}</p>{_banner(msg)}"
            f"<div class='kn-cols'>{links}{rechts}</div></div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Speel een inzicht", inner)
