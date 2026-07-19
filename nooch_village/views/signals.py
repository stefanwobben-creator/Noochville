"""Signals — dé centrale trechter van de library: hier komt álles binnen.

De radar verhuisde van de rol-pagina's naar deze ene plek (founder, 19 jul): bovenaan de
wachtrij (status 'wacht', alle feeds, ✓/✗), daaronder de goedgekeurde signalen. Vanaf hier
promoveer je naar de kennisbank: één signaal via "→ kenniskaartje", of meerdere tegelijk via
de selectievakjes — beide landen in dezelfde Even-nakijken-set (staging), waar de bron gelezen
en geatomiseerd is en je kunt bewerken, mergen of weggooien vóór er kaartjes ontstaan.

Read-only aggregatie via RadarStore (all_pending/all_approved) — geen nieuwe opslag.
Hergebruik: web_base (_e/_page), cockpit2_util (_DS_LINK/_name/_nav) en .rdr-*/.kn-*-stijl."""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _name, _nav

_KIND = {"kaart": "🃏 signaal", "seed": "🌱 kiem", "doelwit": "🎯 doelwit", "concurrent": "🏁 concurrent"}


def _sig_date(s: str) -> str:
    s = (s or "").strip()
    return s[:10] if s else ""


def radar_promote_ctl(it: dict, csrf: str, nxt: str) -> str:
    """Promotie-control op een GOEDGEKEURD radar-signaal: knop '→ kenniskaartje' zolang het
    niet gepromoveerd is (POST /action, actie radar_promote; leidt naar de Even-nakijken-set),
    daarna een chip '→ in kennisbank' die via het bestaande zoekpad (tag 'signal') naar de
    bibliotheek linkt. Geen csrf en niet gepromoveerd → niets."""
    if it.get("promoted_atom_id"):
        return ("<a class='chip rdr-inkb' href='/kennisbank?q=signal' "
                "title='dit signaal is al een kenniskaartje'>→ in kennisbank</a>")
    if not csrf:
        return ""
    return (f"<form method='post' action='/action' class='cl-rep rdr-promoteform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='rid' value='{_e(it.get('id', ''))}'>"
            f"<input type='hidden' name='next' value='{_e(nxt)}'>"
            f"<button class='rdr-promote' type='submit' name='action' value='radar_promote' "
            f"title='lees de bron en zet voorstellen klaar bij Even nakijken'>"
            f"→ kenniskaartje</button></form>")


def _sig_body(st, it) -> str:
    """De gedeelde kern van een signaal-kaart: content, rationale en meta-regel."""
    orec = st.records.get(it.get("role", ""))
    rolenaam = _name(orec) if orec else it.get("role", "")
    klabel = _KIND.get(it.get("kind", ""), it.get("kind", ""))
    pub = _sig_date(it.get("published_at", ""))
    src = (it.get("source") or "").strip()
    link = (it.get("link") or "").strip()
    bron = (f"<a href='{_e(link)}' target='_blank' rel='noopener'>{_e(src or 'bron')}</a>"
            if link else _e(src))
    rat = (it.get("rationale") or "").strip()
    meta = " · ".join(x for x in (
        f"<span class='chip muted'>{_e(klabel)}</span>",
        (f"<span class='chip muted'>📅 {_e(pub)}</span>" if pub else ""),
        (f"<span class='chip'>{_e(it.get('feed', ''))}</span>" if it.get("feed") else ""),
        f"<span class='muted'>via {_e(rolenaam)}</span>",
        bron) if x)
    return (f"<div class='rdr-body'>"
            f"<div class='rdr-sig'>{_e(it.get('content', ''))}</div>"
            + (f"<div class='muted rdr-rat'>{_e(rat)}</div>" if rat else "")
            + f"<div class='rdr-meta'>{meta}</div></div>")


def _wachtrij_card(st, it, csrf: str, nxt: str) -> str:
    """Eén wachtend signaal in de centrale wachtrij: ✓ (relevant → goedgekeurd) en
    ✗ (wegklikken). Zonder csrf alleen-lezen."""
    body = _sig_body(st, it)
    if not csrf:
        return f"<div class='rdr-row'>{body}</div>"
    ctl = (f"<form method='post' action='/action' class='cl-rep'>"
           f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='rid' value='{_e(it['id'])}'>"
           f"<input type='hidden' name='next' value='{_e(nxt)}'>"
           f"<button class='cl-check ok' type='submit' name='action' value='radar_approve' "
           f"title='relevant — naar de goedgekeurde lijst'>✓</button>"
           f"<button class='cl-check no' type='submit' name='action' value='radar_dismiss' "
           f"title='niet relevant — wegklikken'>✗</button></form>")
    return f"<div class='rdr-row'>{ctl}{body}</div>"


def _signal_card(st, it, csrf: str = "", nxt: str = "/signals") -> str:
    """Eén goedgekeurd signaal: selectievakje (voor de multi-promotie) + promotie-control."""
    sel = ""
    if csrf and not it.get("promoted_atom_id"):
        sel = (f"<input type='checkbox' class='rdr-sel' form='rdr-selform' name='rid' "
               f"value='{_e(it.get('id', ''))}' aria-label='selecteer dit signaal'>")
    ctl = radar_promote_ctl(it, csrf, nxt)
    return f"<div class='rdr-row rdr-arch'>{sel}{ctl}{_sig_body(st, it)}</div>"


_VG_OVERLAY = (
    "<div class='kn-overlay' id='rdr-bezig' hidden>"
    "<div class='kn-modal kn-vgmodal'><h2>📖 De bron wordt gelezen</h2>"
    "<div class='kn-vgbaan'><div class='kn-vgbalk'></div></div>"
    "<p class='muted'>Artikel ophalen, in voorstellen knippen, herkomst eraan… daarna "
    "kijk jij ze na bij Even nakijken.</p></div></div>"
    "<script>(function(){var o=document.getElementById('rdr-bezig');if(!o)return;"
    "function toon(){o.removeAttribute('hidden');}"
    "var i,fs=document.querySelectorAll('.rdr-promoteform');"
    "for(i=0;i<fs.length;i++){fs[i].addEventListener('submit',toon);}"
    "var s=document.getElementById('rdr-selform');"
    "if(s){s.addEventListener('submit',toon);}})();</script>")


def render_signals(st, csrf_token: str = "", feed: str = "") -> str:
    """De /signals-pagina: centrale wachtrij bovenaan, dan de goedgekeurde signalen
    (nieuwste eerst), optioneel gefilterd op feed."""
    nxt = "/signals" + (f"?feed={feed}" if feed else "")
    wachtend = st.radar.all_pending()
    alle = st.radar.all_approved()
    # Gepromoveerde signalen zijn kenniskaartjes geworden — signalen zijn de wachtkamer,
    # niet het archief (founder, 18 jul). Ze verdwijnen uit de lijst; onderaan blijft een
    # ingeklapte teller zodat niets spoorloos is.
    items = [it for it in alle if not it.get("promoted_atom_id")]
    promoted = [it for it in alle if it.get("promoted_atom_id")]
    feeds = sorted({it.get("feed", "") for it in (items + wachtend) if it.get("feed")})
    if feed:
        items = [it for it in items if it.get("feed") == feed]
        wachtend = [it for it in wachtend if it.get("feed") == feed]
    chips = ""
    if feeds:
        opts = [("", "alle")] + [(f, f) for f in feeds]
        chips = ("<div class='c2-sec'>" + "".join(
            f"<a class='chip-opt{(' on' if feed == val else '')}' "
            f"href='/signals{('?feed=' + _e(val)) if val else ''}'>{_e(lbl)}</a>"
            for val, lbl in opts) + "</div>")
    # ── wachtrij (centraal: alle feeds, alle rollen) ─────────────────────────
    if wachtend:
        wacht = (f"<div class='rdr-sub'>Wachtrij <span class='muted'>· {len(wachtend)} nieuw "
                 f"signaal{'en' if len(wachtend) != 1 else ''}, jij bepaalt wat relevant is"
                 f"</span></div>"
                 + "".join(_wachtrij_card(st, it, csrf_token, nxt) for it in wachtend))
    else:
        wacht = "<p class='muted'>Geen nieuwe signalen in de wachtrij.</p>"
    # ── goedgekeurd: selecteerbaar voor de gezamenlijke promotie ─────────────
    selbar = ""
    if csrf_token and items:
        selbar = (f"<form method='post' action='/action' id='rdr-selform' class='rdr-selbar'>"
                  f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                  f"<input type='hidden' name='action' value='radar_promote_multi'>"
                  f"<input type='hidden' name='next' value='{_e(nxt)}'>"
                  f"<button class='btn ok' type='submit' title='lees de bronnen en zet de "
                  f"selectie samen klaar bij Even nakijken'>→ Even nakijken (selectie)</button>"
                  f"<span class='muted'>vink signalen aan om ze samen te promoveren en daar "
                  f"te mergen</span></form>")
    body = ("".join(_signal_card(st, it, csrf_token, nxt) for it in items) if items
            else "<p class='muted'>Nog geen goedgekeurde signalen. Keur ze hierboven goed "
                 "in de wachtrij, dan verschijnen ze hier.</p>")
    if promoted:
        body += (f"<details class='c2-hist'><summary class='muted'>→ in kennisbank · "
                 f"{len(promoted)}</summary>"
                 + "".join(_signal_card(st, it, csrf_token, nxt) for it in promoted)
                 + "</details>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>Signalen <span class='chip'>library</span></h1>"
            f"<p class='muted'>Hier komt alles binnen: de centrale wachtrij van alle feeds. "
            f"Wat je goedkeurt kun je hieronder (samen) promoveren tot kenniskaartjes.</p>"
            f"{chips}"
            f"<div class='rdr-tool'>{wacht}</div>"
            f"<div class='rdr-sub'>Goedgekeurd <span class='muted'>· klaar om te promoveren"
            f"</span></div>{selbar}"
            f"<div class='rdr-tool'>{body}</div>"
            f"{_VG_OVERLAY if csrf_token else ''}</div>")
    inner = (f"{_DS_LINK}"
             f"{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Signalen", inner)
