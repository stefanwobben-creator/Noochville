"""Het inzicht-spel (/kennisbank/spel?sid=...) — de server-side dialoog van fase 3.

De AI is denkpartner, geen fan: één vraag per beurt, en het gesprek eindigt met het
=== INZICHT ===-blok. Deze view toont het transcript (chat-atomen .kb-msg/.kb-who/.kb-text,
hergebruikt van Noochie), de kaarten op tafel, het antwoord-formulier, en — zodra het blok
er is — de munt-knop. Machinerie (prompt, ladder, tredes) blijft binnen.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _BUILD
from nooch_village.kennisbank import load_atoms
from nooch_village.kennisbank_spel import BLOK_MARKER


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _msg_html(m: dict) -> str:
    mij = m.get("role") == "ik"
    wie = "jij" if mij else "denkpartner"
    tekst = _e(m.get("text")).replace("\n", "<br>")
    return (f"<div class='kb-msg{' jij' if mij else ''}'><span class='kb-who'>{wie}</span>"
            f"<div class='kb-text'>{tekst}</div></div>")


def render_kennisbank_spel(st, sid: str, csrf_token: str = "", msg: str = "") -> str:
    spel = st.spel.get(sid)
    if spel is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 f"<p class='muted'>Spel niet gevonden. <a href='/kennisbank'>← terug</a></p>"
                 f"</div></div>")
        return _page("Spel", inner)
    atoms = load_atoms(st.dd)
    nxt = f"/kennisbank/spel?sid={sid}"

    kaarten = ""
    for k in spel.get("set") or []:
        a = atoms.get(k["atom_id"]) or {}
        cls = "counter" if k.get("stance") == "counter" else "support"
        kaarten += (f"<div class='kn-note {cls}'><span class='kn-dot'></span>"
                    f"<div class='kn-ntext'>{_e(a.get('claim'))}"
                    f"<span class='kn-src'>{'tegen · ' if cls == 'counter' else ''}"
                    f"{_e(a.get('source') or '')}</span></div></div>")

    berichten = "".join(_msg_html(m) for m in spel.get("messages") or [])
    status = spel.get("status")

    voet = ""
    if status == "gemunt" and spel.get("insight_id"):
        voet = (f"<p><a class='btn ok' href='/kennisbank?id={_e(spel['insight_id'])}'>"
                f"→ bekijk het inzicht</a></p>")
    else:
        if not berichten:
            # Nog geen beurt: de eerste zet komt van de denkpartner (stap 1 van het spel).
            voet += (f"<form method='post' action='/action'>"
                     f"{_hid(csrf_token, 'kb_spel_reply', nxt, {'sid': sid})}"
                     f"<button class='btn ok'>start de dialoog →</button></form>")
        else:
            reply = _field("jouw antwoord", "text", kind="textarea", fid="f-spel-reply")
            voet += (f"<form method='post' action='/action' class='kb-form'>"
                     f"{_hid(csrf_token, 'kb_spel_reply', nxt, {'sid': sid})}"
                     f"{reply}<button class='btn ok'>antwoord</button></form>")
        if status == "klaar":
            wat = "nieuwe versie maken" if spel.get("reformulate_of") else "maak het inzicht"
            voet += (f"<form method='post' action='/action'>"
                     f"{_hid(csrf_token, 'kb_spel_finish', nxt, {'sid': sid})}"
                     f"<button class='btn ok'>✓ {wat} →</button> "
                     f"<span class='muted'>het blok is er — munten kan</span></form>")

    transcript = berichten or "<p class='muted'>Nog geen beurten.</p>"
    her = " · herformuleert een bestaand inzicht" if spel.get("reformulate_of") else ""
    main = (f"<div class='c2-main'><div class='c2-bar'>"
            f"<a href='/kennisbank'>← wat Nooch weet</a></div>"
            f"<h1>🎲 Speel een inzicht</h1>"
            f"<p class='muted'>Vermoeden: <b>{_e(spel.get('hunch'))}</b>{her}</p>{_banner(msg)}"
            f"<details class='kn-panel'><summary>de kaarten op tafel "
            f"({len(spel.get('set') or [])})</summary>{kaarten}</details>"
            f"<div class='kn-sec'>{transcript}</div>"
            f"{voet}</div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             f"<a href='/'>home</a> · <a href='/kennisbank'>kennisbank</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Speel een inzicht", inner)
