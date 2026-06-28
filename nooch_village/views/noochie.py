"""Noochie-views — brok 6 van de cockpit2-split."""
from __future__ import annotations

from typing import TYPE_CHECKING

from nooch_village.cockpit import _e
from nooch_village.cockpit2_util import _md

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


def _noochie_suggest(st: _Stores, ask=None):
    """Gerichte suggestie via Noochie's canonieke capability `voorstel_schrijven` (spanning ->
    concreet voorstel: scope/aanpak/afweging). Fail-closed maar bruikbaar: zonder AI-key toch een
    concrete deterministische vervolgstap. `ask(tension)` is een testhook."""
    s = st.noochie.state()
    need, ctx = s.get("need", ""), s.get("ctx", "")
    tension = (s.get("spanning", "")
               + (f" — behoefte: {need}" if need else "")
               + (f" (context: {ctx})" if ctx else ""))
    if ask is not None:
        return ask(tension)
    try:
        from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
        res = VoorstelSchrijvenSkill().run({"tension": tension})
        if res.get("ok"):
            return ("Hier is mijn voorstel:\n\n" + res["voorstel"]
                    + "\n\nWil je dit als roloverleg-voorstel zetten?")
    except Exception:
        pass
    return ("Concrete tip (even zonder AI-verbinding): zet dit als agendapunt op het roloverleg en "
            "beleg je behoefte als accountability bij de best passende rol. Houd het klein: één rol, "
            "één heldere verantwoordelijkheid.")


def _noochie_reply(st: _Stores, text: str, ask=None):
    """Vrij vervolggesprek na de triage. Gebruikt Noochie's canonieke stem (roles.Noochie: de
    missiestem van Nooch.earth, scherp en nuchter; handelt nooit zelf). Fail-closed (None)."""
    from nooch_village.mission import ANCHOR_PURPOSE
    s = st.noochie.state()
    recent = "\n".join(f"- {m['who']}: {m['text']}" for m in s.get("messages", [])[-6:])
    prompt = ("Je bent Noochie, de missiestem van Nooch.earth: scherp, nuchter, en je kijkt naar het "
              "geheel. Je handelt nooit zelf; je stelt alleen voor. Kort en concreet, gericht op een "
              f"concrete vervolgstap.\nMissie: {ANCHOR_PURPOSE}\n"
              f"Spanning: {s.get('spanning', '')}\nBehoefte: {s.get('need', '')}\nGesprek:\n{recent}")
    if ask is not None:
        return ask(prompt)
    try:
        from nooch_village import llm
        from nooch_village.cockpit2 import _match_ladder
        return llm.reason(prompt, ladder=_match_ladder())
    except Exception:
        return None


def render_noochie(st: _Stores, csrf: str, screen_ctx: str = "") -> str:
    """Noochie-venster: geleide mini-triage (spanning -> behoefte -> gerichte suggestie), daarna een
    vrij gesprek. Schermcontext wordt alleen meegenomen als de mens dat zelf aanzet (chip 'leest: X')."""
    s = st.noochie
    if not s.messages:                                  # zaai de opening (één vraag tegelijk)
        if screen_ctx:                                  # vanuit een spanning aangeroepen (werkoverleg)
            s.add("noochie", f"Heb je hulp nodig bij {screen_ctx}? Vertel: wat voel je precies?")
        else:
            s.add("noochie", "Hoi, ik ben Noochie, de missiestem van Nooch. Welke spanning voel je?")

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='next' value='/'>")

    if s.ctx:
        ctxrow = (f"<div class='noo-ctx'><span class='chip green'>leest: {_e(s.ctx)}</span>"
                  f"<form method='post' action='/action' style='display:inline'>{hid()}"
                  f"<input type='hidden' name='ctx' value=''>"
                  f"<button class='flink' type='submit' name='action' value='noochie_ctx'>verwijderen</button></form></div>")
    elif screen_ctx:
        ctxrow = (f"<div class='noo-ctx'><span class='muted'>Dit scherm: {_e(screen_ctx)}</span>"
                  f"<form method='post' action='/action' style='display:inline'>{hid()}"
                  f"<input type='hidden' name='ctx' value='{_e(screen_ctx)}'>"
                  f"<button class='flink' type='submit' name='action' value='noochie_ctx'>neem dit scherm mee</button></form></div>")
    else:
        ctxrow = ""

    msgs = ""
    for m in s.messages:
        jij = m.get("who") == "jij"
        cls = "jij" if jij else "noochie"
        lbl = "🙋 jij" if jij else "🐸 Noochie"
        msgs += (f"<div class='kb-msg {cls}'><span class='kb-who'>{lbl}</span>"
                 f"<div class='kb-text'>{_md(m.get('text', ''))}</div></div>")

    ph = {"ask_spanning": "Wat is je spanning?", "ask_need": "Wat heb je nodig?"}.get(s.phase, "Typ je bericht…")
    comp = (f"<form method='post' action='/action' class='kb-form'>{hid()}"
            f"<textarea name='text' rows='2' placeholder='{_e(ph)}'></textarea>"
            f"<button class='btn ok sm' type='submit' name='action' value='noochie_send' "
            f"style='margin-top:.3rem'>Stuur</button></form>")
    reset = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
             f"<button class='flink' type='submit' name='action' value='noochie_reset'>↺ opnieuw</button></form>")
    return (f"<div class='noo-win'><div class='noo-sub'><span>Snelle hulp · ik stel alleen voor</span>{reset}</div>"
            f"{ctxrow}<div class='kb-body noo-feed'>{msgs}</div>{comp}</div>")


def _noochie_chrome() -> str:
    """Globale chrome (op elke pagina): dunne linkerbalk met de Noochie-CTA onderaan + het venster.
    Later komt de inbox in deze balk. Reuse: het venster gebruikt dezelfde chat-atomen (kb-msg)."""
    rail = ("<div class='noo-rail'><div class='noo-rail-top' title='Inbox — binnenkort'></div>"
            "<button class='noo-cta' type='button'><span class='noo-cta-tx'>Noochie</span></button></div>")
    overlay = ("<div id='novl' class='noo-ovl' style='display:none'><div class='noo-box'>"
               "<div class='noo-head'><span>🐸 Noochie</span><button type='button' class='noo-x'>✕</button></div>"
               "<div id='noo-body'></div></div></div>")
    js = ("<script>(function(){"
          "document.addEventListener('submit',function(e){var f=e.target;"
          "var c=f&&f.getAttribute&&f.getAttribute('data-confirm');"
          "if(c&&!window.confirm(c)){e.preventDefault();e.stopPropagation();}},true);"
          "function ctxLabel(){var el=document.querySelector('.c2-main h2,.c2-main h1,h2,h1');"
          "return (el?el.textContent:document.title||'').trim().slice(0,80);}"
          "function load(show,ctx){fetch('/noochie?fragment=1&ctx='+encodeURIComponent(ctx!=null?ctx:ctxLabel()))"
          ".then(function(r){return r.text();}).then(function(h){"
          "document.getElementById('noo-body').innerHTML=h;"
          "if(show)document.getElementById('novl').style.display='flex';wireN();});}"
          "window.noochieAsk=function(label){load(true,label);};"
          "function wireN(){document.querySelectorAll('#noo-body form').forEach(function(f){"
          "f.addEventListener('submit',function(e){e.preventDefault();"
          "var d=new URLSearchParams(new FormData(f));var s=e.submitter;if(s&&s.name)d.set(s.name,s.value);"
          "fetch('/action',{method:'POST',body:d}).then(function(){load(false);});});});"
          "var ta=document.querySelector('#noo-body textarea');if(ta)ta.focus();}"
          "var cta=document.querySelector('.noo-cta');if(cta)cta.addEventListener('click',function(){load(true);});"
          "var nx=document.querySelector('.noo-x');if(nx)nx.addEventListener('click',function(){document.getElementById('novl').style.display='none';});"
          "var nv=document.getElementById('novl');if(nv)nv.addEventListener('click',function(e){if(e.target===nv)nv.style.display='none';});"
          "})();</script>")
    return rail + overlay + js
