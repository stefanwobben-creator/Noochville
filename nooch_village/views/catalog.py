"""Metrics-catalogus views — brok 7 van de cockpit2-split."""
from __future__ import annotations

from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import _name, _bron_html
from nooch_village.metric_schema import (CADANS_LABEL, MEETTYPE_LABEL,
                                         TIJD_LABEL, BRUIKBAAR_LABEL, VERIFICATIE_LABEL)
from nooch_village.cockpit2_util import _EXTRA_CSS, _BUILD
from nooch_village.views.metrics import (
    _num, _dir_select, _cad_select, _mt_select, _mw_select, _opt_select,
    _aard_chips, _mw_chip, indicator_freshness, freshness_chip,
    _RICHTING, _ORIGIN_LABEL,
)

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


def _catalog_edit_form(st: _Stores, did: str, cur: dict, csrf: str) -> str:
    base = "/catalog"
    hidden = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='def_id' value='{_e(did)}'>"
              f"<input type='hidden' name='next' value='{base}'>")
    thr = "" if cur.get("threshold") is None else _num(cur.get("threshold"))
    mig = ("<select name='migration' title='wat gebeurt er met de historie?'>"
           "<option value='auto'>migratie: automatisch bepalen</option>"
           "<option value='clarify'>verduidelijking (reeks intact)</option>"
           "<option value='backcast'>back-cast (historie hergebruiken)</option>"
           "<option value='break'>reeksbreuk (nieuwe versie)</option></select>")
    return (f"<details class='m-add'><summary class='att-lbl' style='cursor:pointer'>✎ wijzig definitie</summary>"
            f"<form method='post' action='/action' class='m-addform'>{hidden}"
            f"<input name='definition' value=\"{_e(cur.get('definition', ''))}\" placeholder='Definitie: wat telt mee?' autocomplete='off'>"
            f"<input name='unit' value=\"{_e(cur.get('unit', ''))}\" placeholder='Eenheid' autocomplete='off'>"
            f"{_dir_select('direction', cur.get('direction', ''))}"
            f"<input name='threshold' value=\"{_e(str(thr))}\" inputmode='decimal' placeholder='Drempel (optioneel)' autocomplete='off'>"
            f"{_cad_select('cadence', cur.get('cadence', 'ad-hoc'))}{_mt_select('meettype', cur.get('meettype', 'snapshot'))}"
            f"<input name='window' value=\"{_e(cur.get('window', ''))}\" placeholder='Venster (bijv. 7d)' autocomplete='off'>"
            f"{_mw_select('meetwijze', cur.get('meetwijze', 'handmatig'))}"
            f"{_opt_select('tijd', TIJD_LABEL, cur.get('tijd', ''), 'leading/lagging?')}"
            f"{_opt_select('bruikbaar', BRUIKBAAR_LABEL, cur.get('bruikbaar', ''), 'actionable/vanity?')}"
            f"<input name='standaard' value=\"{_e(cur.get('standaard', ''))}\" placeholder='Grondslag/bron (bijv. DORA, IRIS+)' autocomplete='off'>"
            f"<input name='benchmark' value=\"{_e(cur.get('benchmark', ''))}\" placeholder='Benchmark/referentiewaarde' autocomplete='off'>"
            f"<input name='bron_url' value=\"{_e(cur.get('bron_url', ''))}\" placeholder='Bron-link (kenniskaart / LCA-rapport, http of /pad)' autocomplete='off'>"
            f"{_opt_select('verificatie', VERIFICATIE_LABEL, cur.get('verificatie', ''), 'verificatie?')}"
            f"<input name='waarde' value=\"{_e('' if cur.get('waarde') is None else _num(cur.get('waarde')))}\" inputmode='decimal' placeholder='Canonieke waarde (vaste constante, optioneel)' autocomplete='off'>"
            f"{mig}"
            f"<button class='btn ok sm' type='submit' name='action' value='def_amend'>Doorvoeren</button></form></details>")


def _catalog_card(st: _Stores, d: dict, cur: dict, csrf: str) -> str:
    did = d["id"]
    rij = lambda k, v: f"<div class='gr-row'><span class='gr-k'>{k}</span><span>{_e(str(v))}</span></div>" if v else ""
    meet = ", ".join(x for x in (CADANS_LABEL.get(cur.get("cadence"), ""),
                                 MEETTYPE_LABEL.get(cur.get("meettype"), "")) if x)
    if cur.get("window"):
        meet = f"{meet} ({cur['window']})" if meet else cur["window"]
    body = (rij("Definitie", cur.get("definition") or "— (nog niet vastgelegd)")
            + rij("Eenheid", cur.get("unit")) + rij("Richting", _RICHTING.get(cur.get("direction"), "—"))
            + (rij("Waarde", _num(cur.get("waarde"))) if cur.get("waarde") is not None else "")
            + (rij("Drempel", _num(cur.get("threshold"))) if cur.get("threshold") is not None else "")
            + rij("Meetmoment", meet)
            + rij("Grondslag", cur.get("standaard"))
            + rij("Benchmark", cur.get("benchmark"))
            + (f"<div class='gr-row'><span class='gr-k'>Bron</span>{_bron_html(cur['bron_url'])}</div>"
               if cur.get("bron_url") else ""))
    ks = st.metrics.kpis_for_def(did)
    users = sorted({_name(st.records.get(k["node"])) for k in ks if st.records.get(k["node"])})
    usage = (f"{len(ks)}× in gebruik" + (": " + ", ".join(users) if users else "")) if ks else "nog niet in gebruik"
    # Tweede signaal naast 'in gebruik': haalt het systeem er ook data voor op? (gedeelde helper, 3 staten)
    vers = freshness_chip(indicator_freshness(st, cur.get("source", ""), cur.get("veld", "")))
    nver = len(d.get("versions", []))
    vhist = ""
    if nver > 1:
        items = "".join(f"<li>v{v['version']}: {_e({'': 'aangemaakt', 'clarify': 'verduidelijking', 'backcast': 'back-cast', 'break': 'reeksbreuk'}.get(v.get('migration', ''), v.get('migration', '')))}</li>"
                        for v in d["versions"])
        vhist = f"<details class='cat-hist'><summary class='muted'>historie ({nver} versies)</summary><ul>{items}</ul></details>"
    edit = _catalog_edit_form(st, did, cur, csrf) if csrf else ""
    mw = cur.get("meetwijze", "handmatig")
    label = _ORIGIN_LABEL.get(cur.get("source", ""), cur.get("source", "") or "eigen")
    txt = _e(f"{cur.get('name','')} {cur.get('definition','')} {label}".lower())
    grounded = "0" if (cur.get("standaard", "") in ("", "interne aanname")) else "1"
    ver = cur.get("verificatie", "")
    vchip = ""
    if ver:
        vchip = f"<span class='chip {'green' if ver == 'geverifieerd' else 'coral'}' title='verificatiestatus'>{_e(VERIFICATIE_LABEL.get(ver, ver))}</span>"
    return (f"<div class='cat-card' data-mw='{_e(mw)}' data-tijd='{_e(cur.get('tijd',''))}' "
            f"data-bruikbaar='{_e(cur.get('bruikbaar',''))}' data-grounded='{grounded}' "
            f"data-ver='{_e(ver)}' data-text=\"{txt}\">"
            f"<div class='cat-h'><b>{_e(cur.get('name', ''))}</b>"
            f"<span class='cat-tags'>{vchip}{_aard_chips(cur)}{_mw_chip(mw)}<span class='chip muted'>v{d.get('current', 1)}</span></span></div>"
            f"<div class='gr-pop' style='position:static;width:auto;box-shadow:none;border:none;padding:0'>{body}</div>"
            f"<div class='muted cat-use'>{_e(usage)} {vers}</div>{vhist}{edit}</div>")


def _catalog_add_form(st: _Stores, csrf: str) -> str:
    origin_opts = "<option value=''>(handmatig / eigen meting)</option>" + "".join(
        f"<option value='{k}'>{_e(v)}</option>" for k, v in _ORIGIN_LABEL.items())
    return (f"<details class='m-add'><summary class='btn sm'>+ Nieuwe definitie</summary>"
            f"<form method='post' action='/action' class='m-addform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='next' value='/catalog'>"
            f"<input name='name' placeholder='Naam (bijv. NPS)' autocomplete='off'>"
            f"<input name='unit' placeholder='Eenheid (%, score, EUR)' autocomplete='off'>"
            f"<input name='definition' placeholder='Definitie: wat telt mee? (grondslag)' autocomplete='off'>"
            f"<select name='csource' title='bron/herkomst'>{origin_opts}</select>"
            f"{_dir_select('direction', '')}"
            f"<input name='threshold' inputmode='decimal' placeholder='Drempel (optioneel)' autocomplete='off'>"
            f"{_cad_select('cadence', 'ad-hoc')}{_mt_select('meettype', 'snapshot')}"
            f"<input name='window' placeholder='Venster (bijv. 7d, optioneel)' autocomplete='off'>"
            f"{_mw_select('meetwijze', 'handmatig')}"
            f"{_opt_select('tijd', TIJD_LABEL, '', 'leading/lagging?')}"
            f"{_opt_select('bruikbaar', BRUIKBAAR_LABEL, '', 'actionable/vanity?')}"
            f"<input name='standaard' placeholder='Grondslag/bron (bijv. DORA, IRIS+)' autocomplete='off'>"
            f"<input name='benchmark' placeholder='Benchmark/referentiewaarde (optioneel)' autocomplete='off'>"
            f"<input name='bron_url' placeholder='Bron-link (kenniskaart / rapport, optioneel)' autocomplete='off'>"
            f"{_opt_select('verificatie', VERIFICATIE_LABEL, '', 'verificatie?')}"
            f"<input name='waarde' inputmode='decimal' placeholder='Canonieke waarde (vaste constante, optioneel)' autocomplete='off'>"
            f"<button class='btn ok sm' type='submit' name='action' value='def_add'>Definitie toevoegen</button></form></details>")


_CATALOG_JS = """<script>
(function(){
 var q=document.getElementById('cat-q'), cnt=document.getElementById('cat-count');
 var AF='', AV='';                         // één actief filter (of/of, niet en/en)
 function apply(){
   var t=(q&&q.value||'').toLowerCase().trim(), shown=0;
   document.querySelectorAll('.cat-card').forEach(function(c){
     var ok=(!t||(c.dataset.text||'').indexOf(t)>=0) && (!AF || c.dataset[AF]===AV);
     c.classList.toggle('hide',!ok); if(ok)shown++;
   });
   var active=t||!!AF;
   document.querySelectorAll('.cat-sec').forEach(function(s){
     var any=s.querySelectorAll('.cat-card:not(.hide)').length;
     s.style.display=any?'':'none'; if(any&&active)s.open=true;
   });
   if(cnt)cnt.textContent=shown+' definities';
 }
 q&&q.addEventListener('input',apply);
 document.querySelectorAll('.cat-f').forEach(function(b){b.addEventListener('click',function(){
   var facet=b.dataset.facet, val=b.dataset.val;
   if(!facet || (AF===facet && AV===val)){ AF=''; AV=''; }   // 'alle' of nogmaals = wissen
   else { AF=facet; AV=val; }
   document.querySelectorAll('.cat-f').forEach(function(x){
     var sel = x.dataset.facet ? (x.dataset.facet===AF && x.dataset.val===AV) : (AF==='');
     x.classList.toggle('on', sel);
   });
   apply();
 });});
})();
</script>"""


def render_catalog(st: _Stores, csrf_token: str = "", msg: str = "",
                   koppel: str = "", curator: bool = False) -> str:
    defs = st.defs.all()
    bysrc: dict[str, list] = {}
    for d in defs:
        cur = st.defs.current(d["id"]) or {}
        bysrc.setdefault(cur.get("source", ""), []).append((d, cur))
    total = len(defs)
    sections = ""
    for s in sorted(bysrc, key=lambda x: _ORIGIN_LABEL.get(x, "zzz" + (x or "zzz"))):
        cards = "".join(_catalog_card(st, d, cur, csrf_token)
                        for d, cur in sorted(bysrc[s], key=lambda t: t[1].get("name", "")))
        label = _ORIGIN_LABEL.get(s, s or "Eigen / handmatig")
        sections += (f"<details class='cat-sec' open><summary><b>{_e(label)}</b> "
                     f"<span class='muted'>({len(bysrc[s])})</span></summary>"
                     f"<div class='cat-grid'>{cards}</div></details>")
    addform = _catalog_add_form(st, csrf_token) if csrf_token else ""
    ungrounded = sum(1 for d in defs
                     if (st.defs.current(d["id"]) or {}).get("standaard", "") in ("", "interne aanname"))
    bf = lambda facet, val, lbl: f"<button type='button' class='cat-f' data-facet='{facet}' data-val='{val}'>{_e(lbl)}</button>"
    nav = ("<div class='cat-nav'>"
           "<input id='cat-q' class='cat-q' placeholder='Zoek een indicator…' autocomplete='off'>"
           "<span class='cat-fg'><span class='muted'>toon:</span>"
           + bf("bruikbaar", "actionable", "actionable") + bf("tijd", "leading", "leading")
           + bf("grounded", "0", "ongegrond") + bf("ver", "voorlopig", "voorlopig")
           + "<button type='button' class='cat-f cat-f-x on' data-facet='' data-val=''>alle</button></span>"
           f"<span class='muted cat-count' id='cat-count'>{total} definities · {ungrounded} ongegrond</span></div>")
    # Koppel-flow (ruw bron-veld → indicator) is hier geïntegreerd, curator-only: dicht = een ingang,
    # open (?koppel=<source>) = de sectie inline. Niet-curators zien niets hiervan.
    koppel_ui = ""
    if curator:
        from nooch_village.views.catalog_koppelen import _koppel_section, catalog_sources
        if koppel:
            koppel_ui = _koppel_section(st, csrf_token, koppel)
        else:
            srcs = catalog_sources()
            first = _e(srcs[0][0]) if srcs else ""
            koppel_ui = (f"<div class='c2-sec'><a class='btn ok' href='/catalog?koppel={first}'>"
                         f"+ Koppel nieuw veld</a> <span class='muted'>— promoveer een ruw bron-veld tot indicator</span></div>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>Metrics-catalogus <span class='chip'>Librarian</span></h1>{_banner(msg)}"
            f"<p class='muted'>Eén bron voor indicator-definities: rollen kiezen hieruit. Een definitie "
            f"wijzigen versioneert nooit in-place, maar als verduidelijking, back-cast of reeksbreuk.</p>"
            f"{koppel_ui}"
            f"<div class='c2-sec'>{addform}</div>{nav}{sections}</div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · <a href='/'>home</a> · "
             "<a href='/catalog'>catalogus</a></div>"
             f"<div class='c2-wrap'>{main}</div>{_CATALOG_JS}")
    return _page("Metrics-catalogus", inner)
