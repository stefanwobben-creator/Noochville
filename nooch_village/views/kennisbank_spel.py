"""Het inzicht-spel (/kennisbank/spel?sid=...) — speel in je eigen AI (copy-paste).

De flow van het prototype (besluit Stefan): (1) cureer je hand — kaarten erbij, richting
draaien, tegenbewijs laten staan; (2) kopieer de gegenereerde prompt en voer de dialoog
in je eigen AI; (3) plak het === INZICHT ===-blok terug en munt het inzicht (v1.0, of een
nieuwe versie bij herformuleren). Geen LLM-call in de browser voor de dialoog zelf.
"""
from __future__ import annotations

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


def _koppel_paneel(spel: dict, atoms: dict, zoek: str, csrf: str, nxt: str) -> str:
    """De hand uitbreiden (anti-dun): zoek kaarten in de bibliotheek. Het systeem
    rangschikt en groepeert het tegenbewijs apart (anti-cherry-pick); een kale koppel
    volstaat, de richting kun je per kaart kiezen."""
    binnen = ""
    if zoek:
        in_set = {k["atom_id"] for k in spel.get("set") or []}
        kandidaten = [k for k in gather(zoek, atoms) if k["atom_id"] not in in_set]
        sup = [k for k in kandidaten if k["stance"] == "support"]
        cou = [k for k in kandidaten if k["stance"] == "counter"]

        def rij(k):
            aid = k["atom_id"]
            a = atoms.get(aid) or {}
            keuze = "".join(
                f"<option value='{s}'{' selected' if k['stance'] == s else ''}>{lbl}</option>"
                for s, lbl in (("support", "steunt"), ("counter", "spreekt tegen")))
            return (f"<form method='post' action='/action' class='kn-lrow'>"
                    f"{_hid(csrf, 'kb_spel_add', nxt, {'sid': spel['id'], 'atom_id': aid})}"
                    f"<div class='kn-lt'>{_e(a.get('claim'))}"
                    f"<span class='kn-src'>{_e(a.get('source') or 'bron onbekend')}</span></div>"
                    f"<select name='stance'>{keuze}</select>"
                    f"<input name='annotation' placeholder='waarom? (optioneel)'>"
                    f"<button class='btn ok'>Koppel</button></form>")

        if sup:
            binnen += "<div class='kn-sectitle'>Steunt mogelijk</div>" + "".join(rij(k) for k in sup)
        if cou:
            binnen += ("<div class='kn-sectitle'>Spreekt dit tegen? (laat staan — daar "
                       "scherp je aan)</div>" + "".join(rij(k) for k in cou))
        if not (sup or cou):
            binnen = "<p class='muted'>Geen kaarten gevonden. Probeer een ander woord.</p>"
    zoekveld = _field("zoek kaarten in de bibliotheek", "zoek", value=zoek,
                      fid="f-spel-zoek", placeholder="bijv. wachttijd, zool, prijs")
    return (f"<details class='kn-panel'{' open' if zoek else ''}>"
            f"<summary>🔗 Koppel meer kaarten</summary>"
            f"<form method='get' action='/kennisbank/spel' class='kn-zoek'>"
            f"<input type='hidden' name='sid' value='{_e(spel['id'])}'>"
            f"{zoekveld}<button class='btn'>Zoek kaarten</button></form>{binnen}</details>")


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
    main = (f"<div class='c2-main'><div class='c2-bar'>"
            f"<a href='/kennisbank'>← Oracle</a></div>"
            f"<h1>🎲 Speel een inzicht</h1>"
            f"<p class='muted'>Vermoeden: <b>{_e(spel.get('hunch'))}</b>{her}</p>{_banner(msg)}"
            f"{nudge}"
            f"<div class='kn-sec'><div class='kn-sectitle'>1 · Je hand "
            f"({len(spel.get('set') or [])} kaarten)</div>"
            f"<p class='muted'>Draai de richting waar nodig en laat het tegenbewijs staan — "
            f"daar scherp je aan.</p>"
            f"{_hand(spel, atoms, csrf_token, nxt, open_)}"
            + (_koppel_paneel(spel, atoms, zoek, csrf_token, nxt) if open_ else "")
            + f"</div>{stappen}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Speel een inzicht", inner)
