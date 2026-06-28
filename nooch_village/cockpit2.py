"""Cockpit 2 — de GlassFrog-vormige weergave (PoC).

Read-only "plaatje": rendert de organisatie als GlassFrog (cirkel-/rolpagina's met tabs +
org-verkenner), bovenop het nieuwe datamodel (records, people, assignments, attachments). Wat we
hebben tonen we echt; wat we nog niet hebben grijzen we uit ("nog te bouwen"), zodat in één blik
zichtbaar is welke brokken resten.

Design: hergebruikt het bestaande design system van cockpit 1 (tokens + _page).
Aparte server (poort 8766) zodat cockpit 1 ongemoeid blijft. Bootstrapt bij een lege dataset de
echte Nooch-structuur (glassfrog_import.nooch_poc_org) in data/poc/, zonder de live data aan te raken.

    python -m nooch_village.cockpit2            # http://127.0.0.1:8766
"""
from __future__ import annotations
import json
import mimetypes
import os
import re
import secrets
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nooch_village.cockpit import _e, _page, _banner     # zelfde design system
from nooch_village.cockpit2_util import (
    _name, _initials, _tabbar, _todo, _avatar, _age, _fmt_due,
    _created_full, _ic, _bron_html, _stamp, _md, _parse_multipart,
    _link_host, _psec, _ICON_ADD_EMOJI, _person_name,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK, _IC_DL,
)
from nooch_village.views.feed import (
    _feed_norm, _feed_who, _mentionables, _mentions_in,
    _hilite_mentions, _feed_entry_html, _feed_author_options,
)
from nooch_village.governance import Records
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore
from nooch_village.personas import PersonaStore
from nooch_village.projects import ProjectLedger
from nooch_village.ai_tasks import AITaskStore
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.metric_schema import (CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
                                         TIJD_LABEL, BRUIKBAAR_LABEL, VERIFICATIE_LABEL)
from nooch_village.definitions import (DefinitionStore, seed_catalog as _seed_catalog,
                                       reground_seed as _reground_seed)
import time as _time
_BUILD = _time.strftime("%H:%M")   # proces-starttijd: zichtbaar in de balk, zo zie je of een herstart aankwam
from nooch_village.notifications import NotifStore
from nooch_village.noochie import NoochieStore
from nooch_village.roloverleg import Agenda
from nooch_village.werkoverleg import WerkoverlegStore, STEPS as _WO_STEPS
from nooch_village import ai_match
from nooch_village import org
from nooch_village.glassfrog_import import import_org, nooch_poc_org

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# Alleen layout-specifieke klassen; kleuren/typografie komen uit de design-tokens van cockpit 1.
_EXTRA_CSS = """
.c2-bar{color:var(--gray);font-size:.85rem;margin:.2rem 0 .5rem}
.c2-wrap{display:flex;gap:1.2rem;align-items:flex-start;margin-top:.6rem}
.c2-main{flex:1 1 auto;min-width:0}
.c2-rail{flex:0 0 280px;max-width:280px}
.c2-meet{display:flex;gap:.4rem;margin:.4rem 0}
.c2-tabs{display:flex;flex-wrap:wrap;gap:.1rem;border-bottom:1px solid var(--border);margin:.7rem 0 1rem}
.c2-tab{padding:.4rem .7rem;font-size:.85rem;border-bottom:2px solid transparent;color:var(--gray);text-decoration:none}
.c2-tab.on{border-bottom-color:var(--green-dark);color:var(--green-dark);font-weight:700}
.c2-tab .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-left:.35rem;vertical-align:middle}
.dot.live{background:var(--green)}.dot.basic{background:var(--yellow)}.dot.grey{background:var(--border)}
.c2-sec{margin:1.1rem 0}
.c2-sec h3{font-family:var(--font-display);font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--green-dark);margin:0 0 .3rem}
ul.clean{list-style:none;padding:0;margin:0}
ul.clean li{padding:.22rem 0;border-bottom:1px solid var(--border)}
ul.clean li:last-child{border-bottom:none}
.todo{background:var(--cream-2);border:1px dashed var(--border);border-radius:var(--radius);padding:1rem;color:var(--muted)}
.todo b{color:var(--gray)}
.person{display:inline-flex;align-items:center;gap:.35rem;padding:.15rem 0}
.av{width:22px;height:22px;border-radius:50%;background:var(--green);color:#fff;font-size:.62rem;display:inline-flex;align-items:center;justify-content:center;font-weight:700;flex:0 0 auto}
.av.ai{background:#7A5BD1}
.tree{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .85rem;box-shadow:var(--shadow)}
.tree h3{font-family:var(--font-display);font-size:.72rem;text-transform:uppercase;color:var(--green-dark);margin:.1rem 0 .4rem}
.tree ul{list-style:none;margin:0;padding-left:.8rem}.tree>ul{padding-left:0}
.tree li{padding:.12rem 0;font-size:.86rem}
.tree .c{font-weight:700}
.tree .here{background:var(--green-tint);border-radius:5px;padding:0 .3rem}
.legend{font-size:.74rem;color:var(--muted);margin-top:.6rem;display:flex;gap:.9rem;flex-wrap:wrap}
.legend .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:.25rem}
.pill{display:inline-block;font-size:.72rem;padding:.05rem .45rem;border-radius:var(--radius-pill);background:var(--cream-2);color:var(--gray);margin-left:.3rem}
.card{border:1px solid var(--border);border-radius:var(--radius);padding:.5rem .7rem;margin:.3rem 0;background:var(--surface)}
.pboard{display:flex;gap:.6rem;align-items:flex-start;overflow-x:auto}
.pcol{flex:1 1 0;min-width:160px;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem}
.pcol-scroll{max-height:540px;overflow-y:auto}
.swim{margin:.6rem 0}
.swim-h{font-family:var(--font-display);font-weight:700;font-size:.85rem;color:var(--green-dark);margin:.2rem 0 .25rem}
.pcol-h{font-family:var(--font-display);font-weight:700;font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;color:var(--green-dark);margin-bottom:.3rem}
.pcol .card{padding:.4rem .5rem;margin:.25rem 0;font-size:.85rem}
.dellink{background:none;border:none;color:var(--coral);font:inherit;font-size:.78rem;text-decoration:underline;cursor:pointer;padding:0;margin-left:.3rem}
.kpi-exp{color:var(--subtle);display:inline-flex;align-items:center;margin-left:.3rem}
.kpi-exp:hover{color:var(--green-dark)}
.kpi-exp svg{width:15px;height:15px}
.def-pick{display:flex;flex-direction:column;gap:.6rem;margin-top:.5rem}
.def-recs{display:flex;flex-wrap:wrap;align-items:center;gap:.35rem}
.def-rec{display:inline}
.def-grp{display:flex;flex-wrap:wrap;align-items:center;gap:.35rem;padding:.25rem 0;border-bottom:1px solid var(--border)}
.def-grp>.muted{flex:0 0 9rem}
.def-all{margin-top:.2rem}
.def-all>summary{cursor:pointer;list-style:none}
.def-share{display:flex;align-items:center;gap:.4rem;font-size:.82rem;color:var(--gray);margin:.2rem 0}
.cat-grid{display:grid;gap:.7rem;grid-template-columns:1fr}
@media(min-width:680px){.cat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cat-card{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface);min-width:0}
.cat-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.35rem}
.cat-use{font-size:.76rem;margin-top:.4rem}
.cat-hist{margin-top:.3rem;font-size:.78rem}
.cat-hist ul{margin:.3rem 0 0 1rem;padding:0}
.cat-hist summary{cursor:pointer;list-style:none}
.cat-nav{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;margin:.4rem 0 .9rem;position:sticky;top:0;background:var(--cream-2);padding:.5rem 0;z-index:5}
.cat-q{flex:1 1 14rem;min-width:10rem;border:1px solid var(--border);border-radius:var(--radius-pill);padding:.4rem .8rem;font:inherit}
.cat-f{border:1px solid var(--border);background:var(--surface);color:var(--gray);border-radius:var(--radius-pill);padding:.25rem .7rem;font-size:.8rem;cursor:pointer}
.cat-f.on{background:var(--green);color:#fff;border-color:var(--green)}
.cat-f-x{color:var(--subtle)}
.cat-count{margin-left:auto}
.cat-fg{display:inline-flex;align-items:center;gap:.3rem;flex-wrap:wrap}
.burnup-wrap{display:flex;flex-direction:column;gap:.25rem}
.bu-head b{font-size:1.2rem}
.burnup{display:block;border-bottom:1px solid var(--border)}
.bu-tempo{font-size:.85rem}
.bu-ok{color:var(--green-dark);font-weight:700}
.bu-no{color:var(--coral);font-weight:700}
.bu-proj{font-size:.74rem}
.tile-data{margin-top:.35rem;font-size:.76rem}
.tile-data>summary{cursor:pointer;list-style:none;color:var(--subtle);display:flex;align-items:center;gap:.4rem}
.tile-data>summary::-webkit-details-marker{display:none}
.tile-data>summary::before{content:'▸';color:var(--subtle)}
.tile-data[open]>summary::before{content:'▾'}
.tile-data .mtab{margin-top:.3rem;width:100%}
.delta{font-weight:700}
.delta.up{color:var(--green-dark)}
.delta.down{color:var(--coral)}
.delta.flat{color:var(--subtle)}
.bullet-wrap{display:flex;flex-direction:column;gap:.2rem}
.bullet-h b{font-size:1.1rem}
.bullet{display:block}
.bullet-bm{font-size:.72rem}
.kc-form{display:flex;flex-direction:column;gap:14px;max-width:34rem}
.kc-step{border:0.5px solid var(--border);border-radius:12px;padding:.7rem .9rem;background:var(--surface)}
.kc-h{display:flex;align-items:center;gap:8px;margin-bottom:.5rem}
.kc-n{display:inline-flex;align-items:center;justify-content:center;width:1.4rem;height:1.4rem;border-radius:999px;background:var(--green-tint);color:var(--green-dark);font-size:.8rem;font-weight:700}
.kc-form select,.kc-form input{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;margin-bottom:.3rem}
.kc-radio{display:block;font-size:.88rem;padding:.15rem 0}
.kc-radio input{width:auto;margin-right:.4rem}
.kc-cond{margin:.3rem 0 .3rem 1.3rem}
.kc-hint{font-size:.72rem;margin:.2rem 0 0}
.tile-prov{font-size:.66rem;color:var(--coral);border:1px solid var(--coral);border-radius:var(--radius-pill);padding:0 .35rem;margin-left:.35rem;vertical-align:middle}
.cat-sec{margin-bottom:.6rem}
.cat-sec>summary{cursor:pointer;list-style:none;padding:.3rem 0;border-bottom:1px solid var(--border);font-size:.95rem}
.cat-sec>summary::-webkit-details-marker{display:none}
.cat-sec[open]>summary{margin-bottom:.5rem}
.cat-sec>summary::before{content:'▸ ';color:var(--subtle)}
.cat-sec[open]>summary::before{content:'▾ '}
.cat-tags{display:inline-flex;gap:.3rem;align-items:center}
.cat-card.hide{display:none}
.card.arch{opacity:.6}
.pcard{cursor:pointer;position:relative;transition:box-shadow .1s,border-color .1s}
.pcard:hover{border-color:var(--green);box-shadow:0 0 0 2px var(--green-tint)}
.pcard:active{cursor:grabbing}
.ptitle{font-weight:600}
.clabel{height:7px;border-radius:4px;margin:-.1rem 0 .35rem}
.pbadge{display:flex;align-items:center;gap:.35rem;margin-top:.35rem;font-size:.7rem;color:var(--muted)}
.pbar{height:6px;background:var(--border);border-radius:999px;overflow:hidden;width:70px}
.pbar>div{height:100%;background:var(--green)}
.pcol.over{outline:2px dashed var(--green);outline-offset:-2px;background:var(--green-tint)}
/* override de basis-details-stijl (wit kaartje) → ghost in de kolomkleur, Trello-stijl */
.qadd{margin-top:.15rem;background:none;border:none;box-shadow:none;padding:0}
.qadd>summary{list-style:none;cursor:pointer;color:var(--gray);font-family:var(--font-body);font-weight:500;font-size:.84rem;padding:.4rem .55rem;border-radius:var(--radius)}
.qadd>summary:hover{background:rgba(27,27,27,.07);color:var(--ink)}
.qadd>summary::-webkit-details-marker{display:none}
.qadd[open]{padding:0}
.qadd[open]>summary{display:none}
.qadd-form{display:flex;flex-direction:column;gap:.4rem;margin-top:.1rem}
.qadd-form textarea{width:100%;box-sizing:border-box;padding:.45rem .55rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);box-shadow:var(--shadow);font:inherit;font-size:.85rem;resize:vertical}
.qadd-row{display:flex;align-items:center;gap:.4rem}
.qadd-x{background:none;border:none;font-size:1rem;color:var(--gray);cursor:pointer;padding:.1rem .3rem}
/* '+ project' krijgt dezelfde subtiele knop-vormgeving als de meeting-knoppen */
.addlink{display:inline-block;font-family:var(--font-body);font-weight:600;font-size:12px;
  border:1px solid rgba(27,27,27,.14);border-radius:var(--radius-pill);background:transparent;
  color:var(--gray);padding:.3rem .85rem;text-decoration:none;cursor:pointer;vertical-align:middle}
.addlink:hover{background:rgba(27,27,27,.05);color:var(--ink);text-decoration:none}
/* rollen-tab: rij met purpose + rechts uitgelijnde vervullers + toewijs-icoon */
.rrole{display:flex;align-items:flex-start;gap:1rem;padding:.6rem 0;border-bottom:1px solid var(--border)}
.rrole-info{flex:1 1 auto;min-width:0}
.rrole-pur{font-size:.84rem;margin-top:.1rem}
.rrole-fill{flex:0 0 220px;min-width:0}          /* vaste rechterkolom; inhoud links uitgelijnd */
.rrole-act{flex:0 0 auto}
.fillers{display:flex;flex-direction:column;gap:.15rem;align-items:flex-start}
.fperson{display:inline-flex;align-items:center;gap:.35rem;font-size:.86rem;color:var(--gray)}
.fillers.stack{flex-direction:row;align-items:center;gap:.3rem}
.stack-av{margin-left:-8px}.stack-av:first-child{margin-left:0}
.stack-av .av{border:2px solid var(--surface)}
.manage-ico{display:inline-flex;align-items:center;justify-content:center;color:var(--subtle);
  padding:.25rem;border-radius:var(--radius)}
.manage-ico:hover{color:var(--green-dark);background:rgba(27,27,27,.06)}
.accrow{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;padding:.35rem 0;border-bottom:1px solid var(--border)}
.acc-text{flex:1 1 auto;min-width:0}
.acc-ai{flex:0 0 auto;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;justify-content:flex-end}
/* Chip-atoom: .chip (default = tint) + kleur-modifiers. Eén pill voor status/deadline/reactie/AI. */
.chip{display:inline-flex;align-items:center;gap:.3rem;border-radius:var(--radius-pill);padding:.1rem .55rem;font-size:.74rem;font-weight:700;line-height:1.5;background:var(--green-tint);color:var(--green-dark)}
.chip svg{width:13px;height:13px}
.chip.green{background:var(--green);color:#fff}
.chip.muted{background:var(--cream-2);color:var(--gray)}
.chip.outline{background:transparent;border:1px solid var(--border);color:var(--gray);font-weight:600}
.chip.coral{background:var(--error-tint);color:var(--coral);border:1px solid var(--coral)}
.chip.coral-solid{background:var(--coral);color:#fff;font-size:.64rem;text-transform:uppercase;padding:.04rem .4rem}
.ai-gift{font-size:1rem;text-decoration:none;cursor:pointer;line-height:1}
.ai-on{font-size:.95rem;text-decoration:none;cursor:pointer;line-height:1;opacity:.8}
.ai-on:hover{opacity:1}
.ai-ov{margin:.2rem 0 .7rem}
.ai-ov-h{display:flex;align-items:center;gap:.4rem;margin-bottom:.2rem}
.ai-ov-list li{padding:.12rem 0}
.chiplink{text-decoration:none}
/* Knop-atoom: .btn (neutraal) + .ok (primair groen) + .no (gevaar) uit het design system,
   plus twee modifiers. Geen losse knop-varianten meer elders. */
.btn.sm{padding:.2rem .6rem;font-size:.74rem}
.btn.ghost{background:none;border-color:transparent}
.btn.ghost:hover{background:rgba(27,27,27,.05);border-color:var(--border)}
.dot{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;margin-right:.35rem;vertical-align:middle}
.fentry{margin:0 0 .85rem}
.fhead{display:flex;align-items:center;gap:.45rem;margin-bottom:.2rem}
.fwho{min-width:0}
.fname{font-weight:700}
.frole{color:var(--subtle);font-weight:400;font-size:.85rem}
.fbubble{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.5rem .65rem}
.fbul{margin:.2rem 0 .2rem 1.1rem}
.ffoot{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.25rem}
.ffoot-l{display:flex;align-items:center;gap:.35rem;flex-wrap:wrap;min-width:0}
.emoji-pick{position:relative;display:inline-block;background:none;border:none;box-shadow:none;padding:0;margin:0}
.emoji-pick>summary{list-style:none;cursor:pointer;line-height:0;color:var(--subtle);display:inline-flex}
.emoji-pick>summary svg{width:18px;height:18px}
.emoji-pick>summary::-webkit-details-marker{display:none}
.emoji-pick[open]>summary,.emoji-pick>summary:hover{color:var(--green-dark)}
.emoji-pop{position:absolute;left:0;top:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:.4rem;z-index:6;width:230px}
.emo-search{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem;margin-bottom:.35rem;font-size:.82rem}
.emo-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:.1rem;max-height:170px;overflow:auto}
.emo-f{display:inline}
.emo{border:none;background:none;cursor:pointer;font-size:1.05rem;padding:.15rem;border-radius:var(--radius);width:100%}
.emo:hover{background:var(--cream-2)}
.fstamp{color:var(--subtle);font-size:.72rem}
.flink{border:none;background:none;color:var(--gray);font-size:.78rem;cursor:pointer;text-decoration:underline;padding:0}
.flink:hover{color:var(--green-dark)}
.fsep{color:var(--subtle);font-size:.78rem}
.fedit{display:inline}
.fedit>summary{list-style:none;display:inline}
.fedit>summary::-webkit-details-marker{display:none}
.fedit textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .5rem}
.rov-list{margin-bottom:.6rem}
.rov-item{display:flex;align-items:center;gap:.3rem;padding:.25rem .3rem;border-radius:var(--radius)}
.rov-item.on{background:var(--cream-2)}
.rov-item:hover{background:var(--cream-2)}
.rov-link{flex:1 1 auto;min-width:0;display:flex;align-items:center;gap:.35rem;flex-wrap:wrap;text-decoration:none;color:var(--ink)}
.rov-title{font-weight:600}
.rov-kind{font-size:.68rem;flex-basis:100%}
@media(min-width:620px){.pgrid.rov-grid{grid-template-columns:minmax(0,1fr) minmax(0,3fr)}}
.rov-add{display:flex;gap:.4rem;margin-bottom:.6rem}
.rov-add input{flex:1 1 auto;min-width:0;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem}
.rov-item.done .rov-title{text-decoration:line-through;color:var(--muted)}
.rov-by{font-size:.6rem;width:auto;min-width:1.4rem;padding:0 .25rem;height:1.4rem;display:inline-flex;align-items:center;justify-content:center}
.rov-foot{position:sticky;bottom:-1.3rem;z-index:6;background:var(--surface);border-top:1px solid var(--border);margin:1rem -1.5rem -1.3rem;padding:.8rem 1.5rem 1.3rem;display:flex;align-items:center;justify-content:space-between;gap:.6rem}
.rovchat-toggle{display:inline-flex;align-items:center;gap:.4rem}
.rovchat-toggle svg{width:15px;height:15px}
.rov-editor input[name=value]{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .5rem}
.rovm{border:1px solid var(--border);border-radius:var(--radius);padding:.8rem .9rem;margin-bottom:.9rem;background:var(--surface)}
.rovm-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.6rem}
.rovm-kind{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700}
.rovm-kind b{color:var(--gray)}
.rovm-close{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.9rem;padding:0 .2rem}
.rovm-close:hover{color:var(--coral)}
.rovm-field{margin-top:.7rem}
.rovm-field input[name=value],.rovm-field textarea,.rovm-field select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .5rem;background:var(--surface);font:inherit}
.rovm-was{font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted);font-style:italic}
.rovm-item{display:flex;align-items:center;gap:.5rem;padding:.25rem .4rem;border-radius:var(--radius);border:1px solid var(--border);margin-top:.3rem}
.rovm-iv{flex:1 1 auto;min-width:0}
.rovm-item.is-new{background:var(--green-tint);border-color:var(--green)}
.rovm-item.is-del{background:var(--cream-2);border-style:dashed}
.rovm-item.is-del .rovm-iv s{color:var(--muted)}
.rovm-foot{display:flex;align-items:center;gap:1rem;margin-top:.8rem;padding-top:.6rem;border-top:1px solid var(--border)}
.rov-addprop{margin-top:.4rem;padding-top:.8rem;border-top:1px dashed var(--border)}
.rov-addgrid{display:grid;gap:.8rem;grid-template-columns:1fr}
@media(min-width:560px){.rov-addgrid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.rov-addgrid select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;background:var(--cream-2);color:var(--muted)}
.is-soon{color:var(--muted)}
.rov-more{font-size:.7rem;color:var(--subtle);font-weight:700}
.rov-block{margin-top:.8rem}
.rov-field{display:flex;align-items:center;gap:.5rem;padding:.2rem 0;border-bottom:1px solid var(--border)}
.rov-fv{flex:1 1 auto;min-width:0}
.rov-addrow{display:flex;gap:.4rem;margin-top:.35rem}
.rov-addrow input{flex:1 1 auto;min-width:0;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem}
.sec-issue{font-size:.78rem;border-radius:var(--radius);padding:.3rem .5rem;margin:.15rem 0 .4rem}
.sec-issue.let{background:var(--cream-2);color:var(--gray)}
.sec-issue.blok{background:var(--error-tint);color:var(--coral)}
.sec-block{margin-top:.9rem}
.sec-kop{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;margin-bottom:.3rem}
.rov-consent{margin-top:1rem}
.btn.ok:disabled,.btn:disabled{background:var(--cream-2);color:var(--muted);border-color:var(--border);cursor:not-allowed}
.rovchat{position:fixed;right:1.2rem;bottom:1.2rem;width:min(360px,92vw);max-height:72vh;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:0 12px 34px rgba(0,0,0,.2);z-index:60;overflow:hidden}
.rovchat-head{display:flex;align-items:center;justify-content:space-between;padding:.55rem .7rem;border-bottom:1px solid var(--border);font-weight:700;background:var(--green-tint);color:var(--green-dark)}
.rovchat-head>span{display:flex;align-items:center;gap:.4rem}
.rovchat-head svg{width:15px;height:15px}
.rovchat-x{text-decoration:none;color:var(--green-dark);font-weight:700;padding:0 .2rem}
.rovchat-intro{padding:.85rem;display:flex;flex-direction:column;gap:.5rem}
.rovchat-intro .btn{width:100%}
.rovchat-mode{display:flex;align-items:center;justify-content:space-between;padding:.4rem .7rem;font-size:.72rem;color:var(--subtle);border-bottom:1px solid var(--border)}
.rovchat .kb-body{padding:.7rem;overflow-y:auto}
.kb-msg{margin-bottom:.55rem}
.kb-msg.jij{text-align:right}
.kb-who{font-size:.7rem;font-weight:700;color:var(--subtle)}
.kb-text{display:inline-block;text-align:left;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .55rem;margin-top:.15rem}
.kb-msg.note .kb-text{background:var(--error-tint);border-color:var(--coral);color:var(--coral)}
.kb-form textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .55rem}
.c2-wrap{margin-left:3.4rem}
.noo-rail{position:fixed;top:0;left:0;bottom:0;width:2.6rem;background:var(--green-dark);display:flex;flex-direction:column;align-items:center;justify-content:space-between;padding:.7rem 0;z-index:40}
.noo-rail-top{width:1.1rem;height:1.1rem;border-radius:50%;border:2px solid rgba(255,255,255,.45)}
.noo-cta{writing-mode:vertical-rl;transform:rotate(180deg);background:var(--coral);color:#fff;border:none;border-radius:var(--radius-pill);padding:.8rem .35rem;font-weight:800;letter-spacing:.05em;cursor:pointer;font-size:.78rem}
.noo-cta:hover{filter:brightness(1.06)}
.noo-ovl{position:fixed;inset:0;background:rgba(0,0,0,.22);z-index:70;display:flex;align-items:flex-end;justify-content:flex-end}
.noo-box{width:min(380px,94vw);max-height:80vh;margin:0 1.2rem 1.2rem 0;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:0 14px 40px rgba(0,0,0,.25);overflow:hidden}
.noo-head{display:flex;align-items:center;justify-content:space-between;padding:.6rem .8rem;background:var(--green-tint);color:var(--green-dark);font-weight:800}
.noo-x{background:none;border:none;color:var(--green-dark);cursor:pointer;font-weight:700;font-size:.95rem}
.noo-win{display:flex;flex-direction:column;min-height:0}
.noo-sub{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.4rem .8rem;font-size:.72rem;color:var(--subtle);border-bottom:1px solid var(--border)}
.noo-ctx{display:flex;align-items:center;gap:.5rem;padding:.45rem .8rem;border-bottom:1px solid var(--border);font-size:.74rem}
.noo-feed{padding:.7rem .8rem;overflow-y:auto;max-height:46vh}
.noo-win .kb-form{padding:.7rem .8rem;border-top:1px solid var(--border)}
.kb-msg.noochie{text-align:left}
@media(max-width:760px){.c2-wrap{margin-left:2.8rem}}
.rov-delrole{margin-top:1rem;padding-top:.6rem;border-top:1px solid var(--border)}
.rov-delrole .flink{color:var(--coral)}
.rov-by{flex:0 0 auto}
.av.role{background:var(--green-dark);color:#fff}
.fkind{font-size:.64rem;text-transform:uppercase;letter-spacing:.04em;font-weight:700;border-radius:var(--radius-pill);padding:.03rem .45rem}
.fkind.upd{background:var(--green-tint);color:var(--green-dark)}
.fkind.cmt{background:var(--cream-2);color:var(--gray)}
.pgrid{display:grid;grid-template-columns:1fr;gap:1rem}
@media(min-width:620px){.pgrid{grid-template-columns:minmax(0,1.2fr) minmax(0,1fr)}}
.pmain{min-width:0}.pside{min-width:0}
.pcard-head{display:flex;align-items:flex-start;gap:.6rem;padding:0 2.6rem .8rem 0;border-bottom:1px solid var(--border);margin-bottom:1.1rem}
.pcard-head .titleform,.pcard-head .ptitle-ro{flex:1 1 auto;min-width:0}
.pcard-head-r{flex:0 0 auto;display:flex;align-items:center;gap:.5rem;padding-top:.2rem}
.menu-h{font-size:.62rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;padding:.25rem .55rem .1rem}
.menu-sep{height:1px;background:var(--border);margin:.3rem 0}
.menuitem.on{font-weight:700;color:var(--green-dark);background:var(--green-tint)}
.pdetail-h{display:flex;align-items:flex-start;gap:.4rem;margin-bottom:.7rem}
.titleform{display:flex;gap:.4rem;align-items:center;flex:1;min-width:0}
.title-edit{flex:1;min-width:0;font-family:var(--font-display);font-size:1.5rem;font-weight:700;border:1px solid transparent;border-radius:var(--radius);padding:.15rem .35rem;background:none;color:var(--ink)}
.title-edit:hover{border-color:var(--border)}
.title-edit:focus{border-color:var(--green);background:var(--surface);outline:none}
.title-save{flex:0 0 auto;opacity:0;transition:opacity .12s}   /* alleen reveal-gedrag; styling uit .btn.ok.sm */
.titleform:focus-within .title-save{opacity:1}
.ptitle-ro{margin:.1rem 0;font-family:var(--font-display)}
.cardmenu{position:relative;flex:0 0 auto}
.cardmenu>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:.3rem;padding:0}
.cardmenu>summary::-webkit-details-marker{display:none}
.statustrigger .caret{color:var(--subtle);font-size:.7rem}
.statustrigger:hover .caret{color:var(--gray)}
.cardmenu-b{position:absolute;right:0;top:2rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:.3rem;z-index:5;min-width:150px}
.menuitem{display:block;width:100%;text-align:left;border:none;background:none;padding:.4rem .55rem;border-radius:var(--radius);cursor:pointer;font-size:.85rem;color:var(--ink)}
.menuitem:hover{background:var(--cream-2)}
.menuitem.danger{color:var(--coral)}
.detailsbox{margin:0 0 1.1rem;border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .8rem}
.detailsbox .psec-h{margin-bottom:.5rem}
.actioncards{display:flex;gap:.5rem;flex-wrap:wrap;margin:0 0 1.1rem}
.acard{display:inline-flex;align-items:center;gap:.4rem;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .75rem;font-size:.82rem;font-weight:600;color:var(--gray);cursor:pointer}
.acard:hover{border-color:var(--green);color:var(--green-dark)}
.acard svg{width:15px;height:15px}
.acard-off{opacity:.5;cursor:not-allowed}
.acard-off:hover{border-color:var(--border);color:var(--gray)}
.acard-d{position:relative;list-style:none;background:none;border:none;box-shadow:none;padding:0;margin:0}
.acard-d>summary{list-style:none}
.acard-d>summary::-webkit-details-marker{display:none}
.datepop{position:absolute;left:0;top:2.5rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:.6rem;z-index:7}
.datepop input[type=date]{border:1px solid var(--border);border-radius:var(--radius);padding:.4rem .55rem;font-size:.88rem}
.checklist{margin:0 0 1.1rem}
.cl-head{display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem}
.cl-head svg{width:15px;height:15px;color:var(--subtle)}
.cl-title{font-weight:700;font-size:.92rem}
.cl-del{margin-left:auto}
.dcol{display:grid;grid-template-columns:auto 1fr;gap:.35rem .8rem;align-content:start;min-width:0}
.dk{align-self:baseline;color:var(--subtle);font-size:.66rem;text-transform:uppercase;letter-spacing:.04em;font-weight:700;padding-top:.12rem}
.dv{min-width:0;font-size:.88rem}
.visform,.visform label{font-size:.85rem;margin:0;display:inline}
.fieldform{display:flex;gap:.4rem;align-items:center}
.fieldform select{flex:1 1 auto;min-width:0}
.descform textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.45rem .55rem}
.att-pop{min-width:230px}
.att-lbl{display:block;font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;margin-bottom:.25rem}
.att-pop input[type=text],.att-pop input[name=url],.att-pop input[name=title]{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;font-size:.85rem}
.att-sep{height:1px;background:var(--border);margin:.6rem 0}
.card-del{margin-top:1.2rem;padding-top:.6rem;border-top:1px solid var(--border)}
.pdisc .psec{background:none;border:none;padding:0;margin:0}
.pdisc{background:var(--cream-2);border-radius:var(--radius);padding:.9rem;min-width:0}
.ment{color:var(--green-dark);font-weight:600}
.mention-pop{position:absolute;left:0;right:auto;top:100%;margin-top:2px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);z-index:8;min-width:180px;max-height:200px;overflow:auto}
.mention-it{display:block;width:100%;text-align:left;border:none;background:none;padding:.35rem .6rem;cursor:pointer;font-size:.85rem}
.mention-it:hover{background:var(--cream-2)}
.nt-list .nt-item{padding:.3rem 0;border-bottom:1px solid var(--border)}
.nt-dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;background:var(--green);margin-right:.4rem;vertical-align:middle}
.ai-ask{margin:.1rem 0 1rem}
.comp-form{margin-bottom:1rem}
.comp-row{margin-top:.4rem}
/* Trello-stijl editor: omkaderde box met opmaak-toolbar boven een randloze textarea. */
.editor{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);overflow:visible}
.editor:focus-within{border-color:var(--green)}
.editor-tb{display:flex;align-items:center;gap:.1rem;padding:.25rem .35rem;border-bottom:1px solid var(--border);background:var(--cream-2);border-radius:var(--radius) var(--radius) 0 0}
.editor-tb .tb-b{background:none;border:none;cursor:pointer;color:var(--gray);border-radius:var(--radius);padding:.2rem .42rem;font-size:.85rem;line-height:1;display:inline-flex;align-items:center}
.editor-tb .tb-b:hover{background:var(--cream-3);color:var(--green-dark)}
.editor-tb .tb-b svg{width:14px;height:14px}
.tb-sep{width:1px;height:1.1rem;background:var(--border);margin:0 .25rem}
.tb-help{margin-left:auto}
.tb-help>summary{cursor:pointer;color:var(--subtle);padding:.2rem .45rem;font-weight:700;list-style:none}
.tb-help>summary::-webkit-details-marker{display:none}
.md-help{position:absolute;right:0;margin-top:.3rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.45rem .6rem;font-size:.72rem;color:var(--gray);white-space:nowrap;box-shadow:0 6px 18px rgba(0,0,0,.12);z-index:5}
.editor textarea{border:none;width:100%;box-sizing:border-box;padding:.55rem .6rem;background:transparent;border-radius:0 0 var(--radius) var(--radius)}
.editor textarea:focus{outline:none}
/* Checklists */
.cl-head{display:flex;align-items:center;justify-content:space-between;gap:1rem}
.cl-bar{display:flex;align-items:center;gap:.6rem;margin-top:.5rem;font-size:.82rem}
.cl-filter{text-decoration:none;color:var(--gray);padding:.1rem .4rem;border-radius:var(--radius)}
.cl-filter.on{background:var(--green-tint);color:var(--green-dark);font-weight:700}
.cl-group{margin:.2rem 0 1rem}
.cl-group h4{margin:.6rem 0 .3rem;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle)}
.cl-row{display:flex;align-items:center;justify-content:space-between;gap:.8rem;padding:.4rem 0;border-bottom:1px solid var(--border)}
.cl-main{flex:1 1 auto;min-width:0;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.cl-desc{font-weight:600}
.cl-act{flex:0 0 auto;display:flex;align-items:center;gap:.5rem}
.cl-spark{display:inline-flex;gap:1px;font-size:.62rem;letter-spacing:0}
.cl-spark i{font-style:normal;width:.95em;text-align:center}
.cl-spark i.ok{color:var(--green)}
.cl-spark i.no{color:var(--coral)}
.cl-checks{display:inline-flex;gap:.25rem}
.cl-check{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;width:1.7rem;height:1.7rem;line-height:1;font-size:.85rem;color:var(--muted)}
.cl-check.ok.on{background:var(--green);color:#fff;border-color:var(--green)}
.cl-check.no.on{background:var(--coral);color:#fff;border-color:var(--coral)}
.cl-attn{background:var(--error-tint);border:1px solid var(--coral);border-radius:var(--radius);padding:.65rem .75rem}
.cl-add{display:inline-block}
.cl-add>summary{list-style:none;cursor:pointer}
.cl-add>summary::-webkit-details-marker{display:none}
.cl-addform{margin-top:.6rem;border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .8rem;background:var(--surface);max-width:30rem}
.cl-addform input[name=description],.cl-addform select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.35rem .5rem;margin-bottom:.2rem}
.cl-gate{display:flex;gap:.4rem;align-items:flex-start;font-size:.8rem;color:var(--gray);margin:.5rem 0 .7rem}
/* Metrics */
.kpi-grid{display:grid;gap:.7rem;grid-template-columns:1fr}
@media(min-width:560px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.kpi-card{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface)}
.kpi-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.kpi-name{font-weight:700;font-size:.85rem}
.kpi-body{display:flex;align-items:flex-end;justify-content:space-between;gap:.6rem;margin:.35rem 0 .2rem}
.kpi-val{font-family:var(--font-display);font-size:1.6rem;line-height:1}
.kpi-unit{font-size:.8rem;color:var(--subtle);font-family:inherit}
.spark{display:block}
.kpi-prov{font-size:.72rem;margin-top:.1rem}
.kpi-foot{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.3rem}
.kpi-add{display:flex;gap:.3rem}
.kpi-add input{width:5rem;border:1px solid var(--border);border-radius:var(--radius);padding:.2rem .4rem}
.kpi-link a{text-decoration:none;color:var(--green-dark);display:inline-flex;align-items:center;gap:.35rem}
.kpi-link svg{width:14px;height:14px}
.m-add,.m-sel{display:inline-block}
.m-add>summary,.m-sel>summary{list-style:none;cursor:pointer}
.m-add>summary::-webkit-details-marker,.m-sel>summary::-webkit-details-marker{display:none}
.m-addgrid{display:grid;gap:.8rem;grid-template-columns:1fr;margin-top:.6rem}
@media(min-width:560px){.m-addgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.m-addform{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface)}
.m-addform input,.m-addform select{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem;margin-bottom:.25rem}
.m-selrow{display:flex;align-items:center;justify-content:space-between;gap:.6rem;padding:.25rem 0;border-bottom:1px solid var(--border);font-size:.84rem}
.flink.on{color:var(--green-dark);font-weight:700}
/* Mini-Looker tegels */
.tile-grid{display:grid;gap:.7rem;grid-template-columns:1fr}
@media(min-width:560px){.tile-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tile{border:1px solid var(--border);border-radius:var(--radius);padding:.6rem .7rem;background:var(--surface);min-width:0}
.tile-h{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.4rem}
.tile-t{font-size:.74rem;color:var(--subtle);font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.tile-trend{display:flex;align-items:flex-end;justify-content:space-between;gap:.5rem}
.kpi-val.sm{font-size:1.15rem}
.tile-h-r{display:inline-flex;align-items:center;gap:.3rem}
.tile-info{position:relative;display:inline-block}
.tile-info>summary{list-style:none;cursor:pointer;color:var(--subtle);display:inline-flex;background:none;border:none;box-shadow:none;padding:0;opacity:.5}
.tile-info>summary:hover,.tile-info[open]>summary{opacity:1}
.tile-info>summary::-webkit-details-marker{display:none}
.tile-info>summary svg{width:13px;height:13px}
.gr-pop{position:absolute;right:0;bottom:calc(100% + 5px);z-index:6;width:15rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:0 8px 24px rgba(0,0,0,.14);padding:.5rem .6rem;font-size:.74rem}
.gr-row{display:flex;gap:.5rem;padding:.12rem 0;border-bottom:1px solid var(--border)}
.gr-k{flex:0 0 4.5rem;color:var(--subtle);font-weight:700}
.tile-goal{font-size:.72rem;margin-top:.3rem}
.tile-warn{color:var(--coral);margin-left:.3rem}
.bars{display:flex;flex-direction:column;gap:.25rem}
.bar-row{display:grid;grid-template-columns:minmax(0,7rem) 1fr auto;align-items:center;gap:.5rem;font-size:.78rem}
.bar-l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-t{display:block;height:.55rem;background:var(--cream-2);border-radius:var(--radius-pill);overflow:hidden}
.bar-f{display:block;height:100%;background:var(--green)}
.bar-v{color:var(--subtle);font-variant-numeric:tabular-nums}
.mtab{width:100%;border-collapse:collapse;font-size:.8rem}
.mtab td{padding:.2rem .3rem;border-bottom:1px solid var(--border)}
.mtab td.num{text-align:right;font-variant-numeric:tabular-nums}
.goal{display:flex;flex-direction:column;gap:.35rem}
.kpidata-row{display:flex;align-items:center;gap:.6rem;padding:.35rem 0;border-bottom:1px solid var(--border);flex-wrap:wrap}
.kpidata-n{flex:1 1 auto;min-width:0;font-weight:600}
.kpidata-v{font-variant-numeric:tabular-nums;color:var(--green-dark);font-weight:700}
/* Werkoverleg: stap-navigatie (hergebruikt rov-grid + rov-foot) */
.wo-nav{display:flex;flex-direction:column;gap:.2rem}
.wo-step{display:flex;align-items:center;gap:.5rem;text-decoration:none;color:var(--gray);padding:.4rem .5rem;border-radius:var(--radius);font-size:.86rem}
.wo-step:hover{background:var(--cream-2)}
.wo-step.on{background:var(--green-tint);color:var(--green-dark);font-weight:700}
.wo-num{display:inline-flex;align-items:center;justify-content:center;width:1.4rem;height:1.4rem;border-radius:50%;background:var(--cream-2);color:var(--gray);font-size:.72rem;font-weight:700;flex:0 0 auto}
.wo-step.on .wo-num{background:var(--green);color:#fff}
.wo-step.done{color:var(--green-dark)}
.wo-step.done .wo-num{background:var(--green);color:#fff}
.wo-sec{font-size:.8rem;margin-top:.4rem}
.wo-sp-add{margin:0}
.wo-substeps{padding:.1rem 0 .3rem 1.6rem}
.wo-substeps .rov-item{padding:.2rem .3rem}
.wo-substeps .rov-title{font-weight:400}
.wo-back-bar{margin:0 0 .8rem}
.wo-back-bar.wo-back-foot{margin:1rem 0 0;padding-top:.8rem;border-top:1px solid var(--border)}
.wo-mems:focus{outline:none}
.wo-mem{display:flex;align-items:center;gap:.6rem;padding:.4rem .5rem;border-radius:var(--radius);border:1px solid transparent;border-bottom:1px solid var(--border)}
.wo-mem.sel{background:var(--cream-2);border-color:var(--border)}
.wo-mem.absent .wo-mem-n{color:var(--muted);text-decoration:line-through}
.wo-mem-n{flex:1 1 auto;min-width:0;font-weight:600}
.wo-leave{font-size:.74rem}
.wo-who{display:flex;flex-wrap:wrap;gap:.3rem;align-items:center;margin-bottom:.6rem}
.cl-num{width:3.2rem;border:1px solid var(--border);border-radius:var(--radius);padding:.15rem .35rem;text-align:right}
.cl-val{font-variant-numeric:tabular-nums;color:var(--green-dark);font-weight:700;margin-left:.3rem}
.cl-rep{display:inline-flex;gap:.25rem;align-items:center}
.row-danger{margin-left:.7rem;padding-left:.7rem;border-left:1px solid var(--border);opacity:.6}
.row-danger:hover{opacity:1}
.wo-kpitabs{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.6rem}
.wo-focus .mtab{margin-top:.5rem}
.wo-outcomes{margin-top:.9rem;display:flex;flex-direction:column;gap:.5rem}
.wo-ocd{border:1px solid var(--border);border-radius:var(--radius)}
.wo-ocd>summary{cursor:pointer;list-style:none;padding:.4rem .6rem;font-weight:600;font-size:.86rem}
.wo-ocd>summary::-webkit-details-marker{display:none}
.wo-ocd>summary:hover{background:var(--cream-2)}
.wo-ocd[open]>summary{border-bottom:1px solid var(--border)}
.wo-ocd .wo-oc{padding:.5rem .6rem}
.wo-scale{display:inline-flex;flex-wrap:wrap;gap:.2rem}
.wo-sc{width:1.7rem;height:1.7rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);cursor:pointer;font-size:.78rem;color:var(--gray)}
.wo-sc.on{background:var(--green);color:#fff;border-color:var(--green)}
.wo-sc.prev{background:var(--green-tint);color:var(--green-dark);border-color:var(--green-tint)}
.wo-avg{font-weight:700;color:var(--green-dark)}
.wo-oc{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.wo-oc input,.wo-oc textarea,.wo-oc select{flex:1 1 12rem;min-width:0;border:1px solid var(--border);border-radius:var(--radius);padding:.3rem .45rem}
.wo-oc button{flex:0 0 auto}
.wo-sum{display:flex;flex-direction:column;gap:.2rem}
.wo-sumrow{display:flex;justify-content:space-between;gap:1rem;padding:.3rem 0;border-bottom:1px solid var(--border)}
.cfetti{position:fixed;top:-14px;width:9px;height:9px;border-radius:2px;z-index:9999;pointer-events:none;animation:cfall 2.2s linear forwards}
@keyframes cfall{to{transform:translateY(110vh) rotate(600deg);opacity:.5}}
.c2-toast{position:fixed;left:50%;bottom:2.2rem;transform:translateX(-50%) translateY(8px);z-index:9998;background:var(--green-dark);color:#fff;padding:.45rem .9rem;border-radius:var(--radius-pill);font-size:.82rem;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.2);opacity:0;transition:opacity .15s,transform .15s;pointer-events:none}
.c2-toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.pdetail-h h2{margin:.1rem 0 .5rem;font-family:var(--font-display);font-size:1.35rem;line-height:1.2}
.psec{margin:0 0 1.15rem}
.psec-h{display:flex;align-items:center;gap:.4rem;color:var(--subtle);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin-bottom:.45rem}
.psec-h svg{width:14px;height:14px;opacity:.75;flex:0 0 auto}
.pside .psec{background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.65rem .75rem;margin-bottom:.8rem}
.smeta{margin:0}
.smeta dt{font-size:.62rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700;margin-top:.55rem}
.smeta dt:first-child{margin-top:0}
.smeta dd{margin:.1rem 0 0}
.ckadd{display:flex;gap:.4rem;margin-top:.5rem}
.ckadd input{flex:1 1 auto;min-width:0}
.ckadd .btn{flex:0 0 auto;white-space:nowrap}
.composer{margin-top:.6rem}
.editbox{margin:0 0 .5rem}
.editbox>summary{cursor:pointer;font-weight:700;font-size:.85rem;color:var(--green-dark)}
.actrow{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
.sugg{background:#F4F1FB;border:1px solid #E0D7F5;border-radius:var(--radius);padding:.5rem .7rem;margin:.5rem 0}
.sugg-h{font-weight:700;color:#5b3fa6;font-size:.82rem;margin-bottom:.3rem}
.bagadd{background:none;border:none;box-shadow:none;padding:0;margin-top:.8rem}
.bagadd>summary{cursor:pointer;color:var(--subtle);font-size:.82rem;list-style:none}
.bagadd>summary:hover{color:#5b3fa6}
.frow{display:flex;align-items:flex-start;gap:.5rem;padding:.4rem 0;border-bottom:1px solid var(--border)}
.ffocus{background:none;border:none;box-shadow:none;padding:0;margin:0}
.ffocus>summary{list-style:none;cursor:pointer}
.ffocus>summary::-webkit-details-marker{display:none}
.ovl{position:fixed;inset:0;background:rgba(27,27,27,.45);z-index:50;display:flex;align-items:flex-start;justify-content:center}
.ovl-box{background:var(--surface);max-width:980px;width:95%;margin:4vh auto;border-radius:12px;padding:1.3rem 1.5rem;max-height:88vh;overflow:auto;position:relative;box-shadow:0 12px 48px rgba(27,27,27,.35)}
.ovl-x{position:absolute;top:.5rem;right:.7rem;border:none;background:none;font-size:1.2rem;cursor:pointer;color:var(--gray)}
.vswitch{display:inline-flex;gap:.2rem;align-items:center}
.vbtn{font-size:12px;font-weight:600;padding:.3rem .85rem;border:1px solid var(--border);border-radius:var(--radius-pill);color:var(--gray);text-decoration:none}
.vbtn.on{background:var(--green);color:#fff;border-color:var(--green)}
.ck-prog{display:flex;align-items:center;gap:.6rem;margin:.2rem 0 .6rem}
.ck-prog .pbar{flex:1 1 auto;width:auto}
.ck-prog .muted{flex:0 0 auto;font-size:.74rem;min-width:2.5rem;text-align:right}
.ck-list{}.ck-item{display:flex;align-items:center;gap:.5rem;padding:.25rem .3rem;border:none;border-radius:var(--radius)}
.ck-item:hover{background:var(--cream-2)}
.ck-box{width:18px;height:18px;border:1.5px solid var(--subtle);border-radius:4px;background:var(--surface);cursor:pointer;font-size:.72rem;line-height:1;color:#fff;flex:0 0 auto}
.ck-box.on{background:var(--green);border-color:var(--green)}
.ck-item .dellink{margin-left:auto;opacity:0}
.ck-item:hover .dellink{opacity:1}
.ck-done{text-decoration:line-through;color:var(--muted)}
.attcard{display:flex;align-items:center;gap:.55rem;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.45rem .6rem;margin-bottom:.4rem}
.att-ic{flex:0 0 auto;color:var(--gray);display:inline-flex}
.att-ic svg{width:16px;height:16px}
.att-name{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;text-decoration:none;color:var(--ink)}
.att-name:hover{text-decoration:underline}
.att-x{flex:0 0 auto}
.ghost-off{opacity:.55;cursor:not-allowed}
.btn.grey{color:var(--muted);border-style:dashed;cursor:not-allowed}
@media(max-width:760px){.c2-wrap{flex-direction:column}.c2-rail{max-width:none;flex-basis:auto}}
"""

# History is bewust weg uit de navigatie (later via settings te ontsluiten).
_CIRCLE_TABS = ["overview", "roles", "members", "policies", "notes", "projects",
                "checklists", "metrics"]
_ROLE_TABS = ["overview", "policies", "notes", "projects", "checklists", "metrics"]


def _default_data_dir() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "data", "poc")


class _Stores:
    def __init__(self, dd: str):
        os.makedirs(dd, exist_ok=True)
        self.dd = dd
        self.records = Records(os.path.join(dd, "governance_records.json"))
        self.people = PeopleStore(os.path.join(dd, "people.json"))
        self.assign = Assignments(os.path.join(dd, "assignments.json"))
        self.att = AttachmentStore(os.path.join(dd, "attachments.json"))
        self.personas = PersonaStore(os.path.join(dd, "personas.json"))
        self.projects = ProjectLedger(os.path.join(dd, "projects.json"))
        self.ai = AITaskStore(os.path.join(dd, "ai_tasks.json"))
        self.match = ai_match.MatchCache(os.path.join(dd, "ai_match_cache.json"))
        self.notif = NotifStore(os.path.join(dd, "notifications.json"))
        self.agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
        self.noochie = NoochieStore(os.path.join(dd, "noochie.json"))
        self.checklists = ChecklistStore(os.path.join(dd, "checklists.json"))
        self.metrics = MetricStore(os.path.join(dd, "metrics.json"))
        self.defs = DefinitionStore(os.path.join(dd, "definitions.json"))
        self.werk = WerkoverlegStore(os.path.join(dd, "werkoverleg.json"))


_FAC_ACC = "Rapporteren over de gezondheid van de werkoverleggen"
_FAC_CHECK = "Gezondheid werkoverleggen gerapporteerd"


def _ensure_facilitator_health(st: _Stores) -> None:
    """Idempotent: de Facilitator krijgt de accountability 'rapporteren over de gezondheid van de
    werkoverleggen', met een maandelijks checklist-item dat eraan hangt."""
    for fac in [r for r in st.records.all() if r.id.endswith("__facilitator")]:
        accs = fac.definition.accountabilities
        if _FAC_ACC not in accs:
            accs.append(_FAC_ACC)
            try:
                fac.version += 1
            except Exception:
                pass
            st.records.put(fac)
        if not any(i.get("description") == _FAC_CHECK for i in st.checklists.for_node(fac.id)):
            st.checklists.add(fac.id, _FAC_CHECK, "maand", target_type="all", by="founder")


_TRANSP_POLICY = "Rolvervullers zijn transparant over hun projecten (projectenbord bijgewerkt)."
_TRANSP_CHECK = "Projectenbord bijgewerkt (transparantie)"


def _ensure_transparency_policy(st: _Stores) -> None:
    """Idempotent: één transparantie-policy op de BREEDSTE cirkel (de rest erft die later over),
    met een gekoppeld wekelijks checklist-item dat de spelregel operationeel checkt."""
    roots = org.roots(st.records.all())
    root = roots[0] if roots else None
    if root is None:
        return
    if _TRANSP_POLICY not in root.definition.policies:
        root.definition.policies.append(_TRANSP_POLICY)
        try:
            root.version += 1
        except Exception:
            pass
        st.records.put(root)
    if not any(i.get("description") == _TRANSP_CHECK for i in st.checklists.for_node(root.id)):
        st.checklists.add(root.id, _TRANSP_CHECK, "week", target_type="all", by="founder")


def _bootstrap(dd: str) -> None:
    """Lege PoC-dataset? Laad dan de echte Nooch-structuur in (eenmalig)."""
    st = _Stores(dd)
    if not st.records.all():
        import_org(nooch_poc_org(), st.records, st.people, st.assign)
    _ensure_facilitator_health(st)
    _ensure_transparency_policy(st)
    _seed_catalog(st.defs)        # Librarian metrics-database: zaad-definities (idempotent)
    _reground_seed(st.defs)       # bestaande definities bijwerken met nieuwe grondingen (idempotent)


def _filler_html(st: _Stores, node_id: str, rec) -> str:
    fillers = st.assign.fillers_of(node_id, record=rec)
    if not fillers:
        return "<span class='muted'>Nog niet vervuld.</span>"
    out = []
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id)
            nm = p.name if p else f.id
            out.append(f"<span class='person'><span class='av'>{_e(_initials(nm))}</span>"
                       f"<a href='/person?id={_e(f.id)}'>{_e(nm)}</a></span>")
        else:
            pa = st.personas.get(f.id)
            nm = (pa.name if pa else f.id) + " (AI)"
            out.append(f"<span class='person'><span class='av ai'>AI</span>{_e(nm)}</span>")
    return "<div>" + " &nbsp; ".join(out) + "</div>"


def _members_of_circle(st: _Stores, circle_id: str) -> list:
    seen, ppl = set(), []
    anchors = [circle_id] + [r.id for r in org.roles_of(st.records.all(), circle_id)]
    for aid in anchors:
        rec = st.records.get(aid)
        for f in st.assign.fillers_of(aid, record=rec):
            if f.type == "person" and f.id not in seen:
                seen.add(f.id)
                p = st.people.get(f.id)
                if p:
                    ppl.append(p)
    return sorted(ppl, key=lambda p: p.name)


def _tree_html(st: _Stores, current_id: str) -> str:
    recs = st.records.all()

    def node_li(rec) -> str:
        is_c = org.is_circle(rec)
        cls = "c" if is_c else ""
        here = " here" if rec.id == current_id else ""
        label = f"<a class='{cls}{here}' href='/node?id={_e(rec.id)}'>{_e(_name(rec))}</a>"
        if is_c:
            # Kernrollen (Lead/Rep/Secretary/Facilitator) niet in de navigatie: die zie je via
            # de cirkel -> Rollen. Houdt de boom rustig.
            kids = sorted([k for k in org.children_of(recs, rec.id)
                           if org.is_circle(k) or _name(k).strip().lower() not in _CORE_ROLE_NAMES],
                          key=lambda r: (not org.is_circle(r), _name(r).lower()))
            return f"<li>{label}<ul>{''.join(node_li(k) for k in kids)}</ul></li>"
        return f"<li>{label}</li>"

    body = "".join(node_li(r) for r in org.roots(recs)) or "<li class='muted'>leeg</li>"
    legend = ("<div class='legend'>"
              "<span><span class='dot' style='background:var(--green)'></span>werkt</span>"
              "<span><span class='dot' style='background:var(--yellow)'></span>basis</span>"
              "<span><span class='dot' style='background:var(--border)'></span>nog te bouwen</span></div>")
    return f"<div class='tree'><h3>Organisatie</h3><ul>{body}</ul></div>{legend}"


def _ai_chip(st: _Stores, t) -> str:
    pa = st.personas.get(t.agent)
    nm = pa.name if pa else t.agent
    skill = f" · {_e(t.wat)}" if t.wat else ""
    return f"<span class='chip'>🤖 {_e(nm)}{skill}</span>"


def _suggest_for_acc(st: _Stores, role_id: str, acc_index: int, acc_text: str):
    """Welke (AI, skill) past bij deze accountability en is nog niet gekoppeld. Voedt het cadeautje.
    Matching loopt via ai_match (lexicaal + concept + optioneel gecachet LLM-oordeel)."""
    attached = {(t.agent, t.wat) for t in st.ai.for_acc(role_id, acc_index)}
    return ai_match.suggest(st.personas.all(), acc_text, attached, st.match)


def _acc_row(st: _Stores, rec, i: int, text: str, csrf_token: str) -> str:
    """Eén accountability-regel. Is er AI op gekoppeld, dan tonen we dat SUBTIEL (één 🤖-marker,
    klikbaar om te beheren); het 'wat' staat gebundeld in het AI-overzicht onder de rol. Zo niet
    dubbel. Het 🎁 verschijnt alleen als er een passende, nog niet gekoppelde AI-skill is."""
    tasks = st.ai.for_acc(rec.id, i)
    url = f"/aitask?role={_e(rec.id)}&acc={i}"
    marker = ""
    if tasks:
        if csrf_token:
            marker = (f"<a class='ai-on js-modal' href='{url}' data-href='{url}' "
                      f"title='AI-empowered — beheren'>🤖</a>")
        else:
            marker = "<span class='ai-on' title='AI-empowered'>🤖</span>"
    aff = ""
    if csrf_token and _suggest_for_acc(st, rec.id, i, text):
        aff = (f"<a class='ai-gift js-modal' href='{url}' data-href='{url}' "
               f"title='Er is een AI-skill die deze accountability autonoom kan uitvoeren'>🎁</a>")
    return (f"<div class='accrow'><div class='acc-text'>{_e(text)}</div>"
            f"<div class='acc-ai'>{marker}{aff}</div></div>")


def _role_ai_overview(st: _Stores, rec, csrf_token: str = "") -> str:
    """Overzicht (één keer, niet per accountability herhaald): wat doet elke AI autonoom in DEZE rol.
    Gegroepeerd per agent -> per skill de accountabilities die hij dekt."""
    tasks = st.ai.for_role(rec.id)
    if not tasks:
        return ""
    accs = rec.definition.accountabilities or []
    by_agent: dict[str, dict[str, list]] = {}
    for t in tasks:
        acc_txt = accs[t.acc_index] if 0 <= t.acc_index < len(accs) else "—"
        by_agent.setdefault(t.agent, {}).setdefault(t.wat or "—", []).append(acc_txt)
    blocks = ""
    for agent, skills in by_agent.items():
        pa = st.personas.get(agent)
        nm = pa.name if pa else agent
        rows = ""
        for wat, acclist in skills.items():
            uniq = ", ".join(dict.fromkeys(acclist))
            rows += f"<li><b>{_e(wat)}</b> <span class='muted'>· {_e(uniq)}</span></li>"
        manage = ""
        if csrf_token:
            url = f"/aitask?role={_e(rec.id)}&acc=0"
            manage = f" <a class='flink js-modal' href='{url}' data-href='{url}'>beheren</a>"
        blocks += (f"<div class='ai-ov'><div class='ai-ov-h'>{_avatar(nm, True)}"
                   f"<b>{_e(nm)}</b> <span class='muted'>doet autonoom in deze rol:</span>{manage}</div>"
                   f"<ul class='clean ai-ov-list'>{rows}</ul></div>")
    return f"<div class='c2-sec'><h3>AI in deze rol</h3>{blocks}</div>"


def _overview_html(st: _Stores, rec, csrf_token: str = "") -> str:
    d = rec.definition
    is_c = org.is_circle(rec)
    parts = [f"<div class='c2-sec'><h3>Purpose</h3><div>{_e(d.purpose) or '<span class=muted>—</span>'}</div></div>"]
    if is_c:
        parts.append("<div class='c2-sec'><h3>Strategy / Core Values</h3>"
                     + _todo("Strategie en kernwaarden per cirkel (nu alleen op de anchor-cirkel).")
                     + "</div>")
    doms = d.domains or []
    parts.append("<div class='c2-sec'><h3>Domains</h3>"
                 + ("<ul class='clean'>" + "".join(f"<li>{_e(x)}</li>" for x in doms) + "</ul>"
                    if doms else "<span class='muted'>Geen domein.</span>") + "</div>")
    accs = d.accountabilities or []
    if not is_c:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3>"
                     + ("".join(_acc_row(st, rec, i, a, csrf_token) for i, a in enumerate(accs))
                        if accs else "<span class='muted'>Geen accountabilities.</span>") + "</div>")
        parts.append(_role_ai_overview(st, rec, csrf_token))
    elif accs:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3><ul class='clean'>"
                     + "".join(f"<li>{_e(x)}</li>" for x in accs) + "</ul></div>")
    if not is_c:
        parts.append(f"<div class='c2-sec'><h3>Role Fillers</h3>{_filler_html(st, rec.id, rec)}</div>")
    return "".join(parts)


def _fillsummary(st: _Stores, rec) -> str:
    fs = st.assign.fillers_of(rec.id, record=rec)
    if not fs:
        return "— niet vervuld"
    names = []
    for f in fs:
        if f.type == "person":
            p = st.people.get(f.id); names.append(p.name if p else f.id)
        else:
            names.append("AI")
    return "· " + ", ".join(names)


_CORE_ROLE_NAMES = {"circle lead", "lead link", "facilitator", "secretary", "secretaris",
                    "rep link", "circle rep", "cross link"}


# Genderneutraal 'persoon + toevoegen'-icoon (silhouet + plus), kleurt mee met currentColor.
_ICON_ADD_PERSON = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='9' cy='8' r='3.2'/>"
    "<path d='M3.5 20c0-3.2 2.5-5.6 5.5-5.6s5.5 2.4 5.5 5.6'/>"
    "<path d='M18.5 8.5v5M16 11h5'/></svg>")

# Reactie toevoegen: neutrale lijn-smiley met plus (zelfde stijl als persoon-toevoegen).


def _fillers_block(st: _Stores, role) -> str:
    """Rechts uitgelijnde rolvervullers; bij 3+ gestapelde avatars + '+ nog N'."""
    fillers = st.assign.fillers_of(role.id, record=role)
    resolved = []
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id)
            resolved.append((p.name if p else f.id, False, f.id))
        else:
            pa = st.personas.get(f.id)
            resolved.append(((pa.name if pa else f.id), True, f.id))
    if not resolved:
        return "<span class='muted' style='font-size:.8rem'>niet vervuld</span>"
    if len(resolved) >= 3:
        avs = "".join(f"<span class='stack-av'>{_avatar(n, ai)}</span>" for n, ai, fid in resolved[:3])
        extra = f"<span class='muted' style='font-size:.82rem'>+ nog {len(resolved)-3}</span>" if len(resolved) > 3 else ""
        return f"<div class='fillers stack'>{avs}{extra}</div>"
    rows = ""
    for n, ai, fid in resolved:
        nm = (f"<a href='/person?id={_e(fid)}'>{_e(n)}</a>" if not ai else f"{_e(n)} (AI)")
        rows += f"<div class='fperson'>{_avatar(n, ai)}<span>{nm}</span></div>"
    return f"<div class='fillers'>{rows}</div>"


def _role_row(st: _Stores, role, csrf_token: str) -> str:
    purpose = role.definition.purpose or ""
    pur = f"<div class='muted rrole-pur'>{_e(purpose)}</div>" if purpose else ""
    assign = ""
    if csrf_token:
        url = f"/rolefillers?role={_e(role.id)}"
        assign = (f"<a class='manage-ico js-modal' href='{url}' data-href='{url}' "
                  f"title='rolvervullers beheren'>{_ICON_ADD_PERSON}</a>")
    return (f"<div class='rrole'>"
            f"<div class='rrole-info'><a href='/node?id={_e(role.id)}'>{_e(_name(role))}</a>{pur}</div>"
            f"<div class='rrole-fill'>{_fillers_block(st, role)}</div>"
            f"<div class='rrole-act'>{assign}</div></div>")


def _roles_html(st: _Stores, rec, csrf_token: str = "") -> str:
    recs = st.records.all()
    subs = sorted(org.subcircles_of(recs, rec.id), key=lambda r: _name(r).lower())
    roles = sorted(org.roles_of(recs, rec.id), key=lambda r: _name(r).lower())
    core = [r for r in roles if _name(r).strip().lower() in _CORE_ROLE_NAMES]
    rest = [r for r in roles if _name(r).strip().lower() not in _CORE_ROLE_NAMES]
    out = []
    if core:
        out.append("<div class='c2-sec'><h3>Kernrollen</h3>"
                   + "".join(_role_row(st, r, csrf_token) for r in core) + "</div>")
    out.append("<div class='c2-sec'><h3>Rollen</h3>"
               + ("".join(_role_row(st, r, csrf_token) for r in rest)
                  if rest else "<span class='muted'>Geen rollen.</span>") + "</div>")
    if subs:
        out.append("<div class='c2-sec'><h3>Subcirkels</h3><ul class='clean'>"
                   + "".join(f"<li><a href='/node?id={_e(s.id)}'>{_e(_name(s))}</a> "
                             f"<span class='chip'>cirkel</span></li>" for s in subs) + "</ul></div>")
    return "".join(out)


def _members_html(st: _Stores, rec) -> str:
    ppl = _members_of_circle(st, rec.id)
    if not ppl:
        return "<div class='c2-sec'><h3>Members</h3><span class='muted'>Geen mensen.</span></div>"
    cells = "".join(
        f"<div class='card'><span class='person'><span class='av'>{_e(_initials(p.name))}</span>"
        f"<a href='/person?id={_e(p.id)}'>{_e(p.name)}</a></span></div>" for p in ppl)
    return f"<div class='c2-sec'><h3>Members ({len(ppl)})</h3>{cells}</div>"


def _att_html(st: _Stores, rec, kind: str, leeg: str) -> str:
    items = st.att.list(rec.id, kind)
    if not items:
        return (f"<p class='muted'>{_e(leeg)}</p>"
                "<p class='muted' style='font-size:.8rem'>De opslag werkt al; het invoeren/"
                "tonen (en de meeting-koppeling) komt nog.</p>")
    out = "<ul class='clean'>"
    for a in items:
        meta = ""
        if a.meta:
            meta = " <span class='pill'>" + _e(", ".join(f"{k}: {v}" for k, v in a.meta.items())) + "</span>"
        out += f"<li><b>{_e(a.title) or '—'}</b>{meta}<br><span class='muted'>{_e(a.body)}</span></li>"
    return out + "</ul>"


_PROJ_CHIP = {   # status -> (label, chip-kleur-modifier)
    "running": ("Actief", "green"),
    "queued": ("Wachtrij", "muted"),
    "future": ("Toekomst", "muted"),
    "blocked": ("Wacht", "coral"),
    "draft": ("Concept", "muted"),
    "done": ("Done", "green"),
}


def _proj_chip(status: str) -> str:
    lbl, mod = _PROJ_CHIP.get(status, (status, "muted"))
    return f"<span class='chip {mod}'>{_e(lbl)}</span>"


def _trekker_html(st: _Stores, p: dict) -> str:
    if p.get("agent"):
        pa = st.personas.get(p["agent"])
        return (f"<span class='person'><span class='av ai'>AI</span>"
                f"{_e((pa.name if pa else p['agent']))} <span class='muted'>(AI)</span></span>")
    if p.get("person"):
        return (f"<span class='person'><span class='av'>{_e(_initials(_person_name(st, p['person'])))}"
                f"</span>{_e(_person_name(st, p['person']))}</span>")
    return "<span class='muted'>geen trekker</span>"


def _trekker_options(st: _Stores, sel_person="", sel_agent="") -> str:
    out = ["<option value=''>— geen trekker —</option>"]
    for pr in st.people.all():
        s = " selected" if pr.id == sel_person else ""
        out.append(f"<option value='person:{_e(pr.id)}'{s}>{_e(pr.name)}</option>")
    for pa in st.personas.all():
        s = " selected" if pa.id == sel_agent else ""
        out.append(f"<option value='persona:{_e(pa.id)}'{s}>🤖 {_e(pa.name)} (AI)</option>")
    return "".join(out)


_PROJ_COLS = [("Actief", "actief", ("running", "queued")), ("Wacht", "wacht", ("blocked",)),
              ("Done", "done", ("done",)), ("Toekomst", "toekomst", ("future",))]


_LABELS = {"groen": "#1F9D55", "geel": "#FFCE2E", "koraal": "#FF6B5B",
           "blauw": "#2B5BB5", "paars": "#7A5BD1", "": ""}


def _proj_progress(p: dict):
    items = [it for cl in (p.get("checklists") or []) for it in cl.get("items", [])]
    if not items:
        return None
    done = sum(1 for it in items if it.get("done"))
    return done, len(items), round(100 * done / len(items))


def _due_overdue(due: str) -> bool:
    """Is de deadline (ISO 'YYYY-MM-DD') verstreken (vóór vandaag)?"""
    if not due:
        return False
    import datetime
    try:
        return datetime.date.fromisoformat(due) < datetime.date.today()
    except Exception:
        return False


def _progress_badge(p: dict) -> str:
    pr = _proj_progress(p)
    if not pr:
        return ""
    done, total, pct = pr
    return (f"<div class='pbadge' title='{done}/{total}'>"
            f"<div class='pbar'><div style='width:{pct}%'></div></div>"
            f"<span>{pct}%</span></div>")


def _scope_text(p) -> str:
    scope = p.get("scope")
    if isinstance(scope, dict):
        return " · ".join(f"{k}: {v}" for k, v in scope.items())
    return str(scope or "—")


def _proj_card(st: _Stores, p: dict, csrf_token: str, back: str) -> str:
    pid = p["id"]
    href = f"/project?pid={_e(pid)}&back={urllib.parse.quote(back, safe='')}"
    bar = ""
    if p.get("label") in _LABELS and _LABELS.get(p.get("label")):
        bar = f"<div class='clabel' style='background:{_LABELS[p['label']]}'></div>"
    meta = (f"<div class='muted' style='font-size:.72rem;margin-top:.25rem'>"
            f"{_trekker_html(st, p)} · {_e(_age(p.get('created_at')))}</div>")
    drag = ' draggable="true"' if csrf_token else ''
    return (f"<div class='card pcard' data-pid='{_e(pid)}' data-href='{href}'{drag}>"
            f"{bar}<div class='ptitle'>{_e(_scope_text(p))}</div>{meta}{_progress_badge(p)}</div>")


def _quickadd(owner: str, col: str, csrf_token: str, back: str, trekker: str = "") -> str:
    """Trello-stijl '+ kaart toevoegen': klap open → vol-breed invoerveld bovenaan, knop eronder.
    `trekker` (person:<id>/persona:<id>) wordt voorgevuld bij groeperen per persoon."""
    if not csrf_token or col == "done":
        return ""
    trek = f"<input type='hidden' name='trekker' value='{_e(trekker)}'>" if trekker else ""
    return (
        f"<details class='qadd'><summary>+ project toevoegen</summary>"
        f"<form method='post' action='/action' class='qadd-form'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='owner' value='{_e(owner)}'>"
        f"<input type='hidden' name='col' value='{_e(col)}'>"
        f"<input type='hidden' name='next' value='{_e(back)}'>{trek}"
        f"<textarea name='scope' rows='2' placeholder='Titel van het project…' aria-label='nieuw project'></textarea>"
        f"<div class='qadd-row'>"
        f"<button class='btn ok' type='submit' name='action' value='proj_add'>Project toevoegen</button>"
        f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
        f"aria-label='annuleren'>✕</button></div>"
        f"</form></details>")


def _inline_add_project(st: _Stores, rec, csrf_token: str, back: str) -> str:
    """Universele inline '+ project' (één patroon, geen aparte modal). Op een cirkel kies je de rol;
    op een rol staat de eigenaar vast. Dekt ook lege rollen/cirkels die per-kolom-quickadd mist."""
    if not csrf_token:
        return ""
    if org.is_circle(rec):
        roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
        ro = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
        owner_field = f"<label class='att-lbl'>Rol</label><select name='owner'>{ro}</select>"
    else:
        owner_field = f"<input type='hidden' name='owner' value='{_e(rec.id)}'>"
    return (
        f"<details class='qadd qadd-top'><summary>+ project</summary>"
        f"<form method='post' action='/action' class='qadd-form'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='next' value='{_e(back)}'>"
        f"<textarea name='scope' rows='2' placeholder='Te bereiken uitkomst…' aria-label='nieuw project'></textarea>"
        f"{owner_field}"
        f"<label class='att-lbl'>Status</label><select name='col'>"
        f"<option value='actief'>Actief</option><option value='wacht'>Wacht</option>"
        f"<option value='toekomst'>Toekomst</option></select>"
        f"<label class='att-lbl'>Trekker (persoon of AI)</label><select name='trekker'>{_trekker_options(st)}</select>"
        f"<div class='qadd-row'><button class='btn ok' type='submit' name='action' value='proj_add'>"
        f"Project toevoegen</button></div></form></details>")


def _columns_html(st: _Stores, items: list, add_owner: str, add_trekker: str,
                  csrf_token: str, back: str, quickadd: bool) -> str:
    cols = ""
    for label, key, statuses in _PROJ_COLS:
        its = [p for p in items if p.get("status") in statuses]
        its.sort(key=lambda p: -(p.get("created_at") or 0))
        body = "".join(_proj_card(st, p, csrf_token, back) for p in its)
        qa = _quickadd(add_owner, key, csrf_token, back, trekker=add_trekker) if quickadd else ""
        cols += (f"<div class='pcol' data-to='{key}'>"
                 f"<div class='pcol-h'>{_e(label)} ({len(its)})</div>"
                 f"<div class='pcol-scroll'>{body}</div>{qa}</div>")
    return f"<div class='pboard'>{cols}</div>"


def _drag_script(csrf_token: str, back: str) -> str:
    if not csrf_token:
        return ""
    return (
        "<script>(function(){"
        f"var csrf={json.dumps(csrf_token)},next={json.dumps(back)},pid=null;"
        "document.querySelectorAll('.pcard').forEach(function(c){"
        "c.addEventListener('dragstart',function(e){pid=c.getAttribute('data-pid');window.__pdrag=true;"
        "e.dataTransfer.effectAllowed='move';c.style.opacity='.5';});"
        "c.addEventListener('dragend',function(){c.style.opacity='';setTimeout(function(){window.__pdrag=false;},60);});});"
        "document.querySelectorAll('.pcol[data-to]').forEach(function(col){"
        "col.addEventListener('dragover',function(e){e.preventDefault();col.classList.add('over');});"
        "col.addEventListener('dragleave',function(){col.classList.remove('over');});"
        "col.addEventListener('drop',function(e){e.preventDefault();col.classList.remove('over');"
        "if(!pid)return;var to=col.getAttribute('data-to');"
        "var f=document.createElement('form');f.method='post';f.action='/action';"
        "function a(n,v){var i=document.createElement('input');i.type='hidden';i.name=n;i.value=v;f.appendChild(i);}"
        "a('csrf',csrf);a('pid',pid);a('next',next);"
        "if(to==='done'){a('action','proj_done');}else{a('action','proj_status');a('to',to);}"
        "document.body.appendChild(f);f.submit();});});})();</script>")


_II_PREFIX = "ii:"   # Individual Initiative-pseudo-eigenaar per cirkel: 'ii:<circle_id>'


def _modal_html(mentions_json: str = "[]") -> str:
    """Herbruikbare detail-overlay (modal): klik op een kaart → haalt het fragment op en toont het;
    formulieren erin posten via fetch en verversen alleen de overlay. Val-terug: zonder JS navigeert
    de kaart-link naar de volledige /project-pagina. Bedoeld als standaard-patroon (ook kenniskaartjes)."""
    return (
        "<div id='ovl' class='ovl' style='display:none'><div class='ovl-box'>"
        "<button type='button' class='ovl-x' aria-label='sluiten'>✕</button>"
        "<div id='ovl-body'></div></div></div>"
        "<script>(function(){"
        "var ov=document.getElementById('ovl'),bd=document.getElementById('ovl-body'),last=null,dirty=false;"
        f"window.__mentions={mentions_json};"
        "window.wrapSel=function(btn,pre,post){var f=btn.closest('form');var t=f&&f.querySelector('textarea');"
        "if(!t)return;var s=t.selectionStart,e=t.selectionEnd,v=t.value;"
        "t.value=v.slice(0,s)+pre+v.slice(s,e)+post+v.slice(e);t.focus();"
        "t.selectionStart=s+pre.length;t.selectionEnd=e+pre.length;};"
        "function mentionWire(t){var box=null;function close(){if(box){box.remove();box=null;}}"
        "t.addEventListener('input',function(){var v=t.value.slice(0,t.selectionStart);"
        "var m=v.match(/@([^@\\n]*)$/);close();if(!m)return;var q=m[1].toLowerCase();"
        "var hits=(window.__mentions||[]).filter(function(x){return x.l.toLowerCase().indexOf(q)===0;}).slice(0,6);"
        "if(!hits.length)return;box=document.createElement('div');box.className='mention-pop';"
        "hits.forEach(function(h){var b=document.createElement('button');b.type='button';b.className='mention-it';"
        "b.textContent='@'+h.l;b.addEventListener('mousedown',function(ev){ev.preventDefault();"
        "var s=t.value,c=t.selectionStart;var pre=s.slice(0,c).replace(/@([^@\\n]*)$/,'@'+h.l+' ');"
        "t.value=pre+s.slice(c);t.focus();t.selectionStart=t.selectionEnd=pre.length;close();});box.appendChild(b);});"
        "t.parentNode.style.position='relative';t.parentNode.appendChild(box);});"
        "t.addEventListener('blur',function(){setTimeout(close,200);});}"
        "window.emoFilter=function(inp){var q=inp.value.toLowerCase();"
        "inp.parentNode.querySelectorAll('.emo-f').forEach(function(f){"
        "var k=f.getAttribute('data-k')||'';f.style.display=(!q||k.indexOf(q)>-1)?'':'none';});};"
        "function frag(u){return u+(u.indexOf('?')>-1?'&':'?')+'fragment=1';}"
        "function openCard(u){last=u;"
        "fetch(frag(u)).then(function(r){return r.text();}).then(function(h){bd.innerHTML=h;ov.style.display='flex';"
        "window.__noclose=!!bd.querySelector('[data-noclose]');"
        "var xb=document.querySelector('.ovl-x');if(xb)xb.style.display=window.__noclose?'none':'';wire();});}"
        "function reopen(){if(last)openCard(last);}"
        "function shut(){ov.style.display='none';bd.innerHTML='';if(dirty){dirty=false;location.reload();}}"
        "function confetti(){var c=['#2e7d32','#ef6c5a','#f6c244','#7bb661'];for(var i=0;i<70;i++){"
        "var d=document.createElement('div');d.className='cfetti';d.style.left=(Math.random()*100)+'vw';"
        "d.style.background=c[i%4];d.style.animationDelay=(Math.random()*0.4)+'s';document.body.appendChild(d);"
        "(function(x){setTimeout(function(){x.remove();},2400);})(d);}}"
        "function toast(t){var d=document.createElement('div');d.className='c2-toast';d.textContent=t;"
        "document.body.appendChild(d);setTimeout(function(){d.classList.add('show');},10);"
        "setTimeout(function(){d.classList.remove('show');},1600);setTimeout(function(){d.remove();},2000);}"
        "function wire(){bd.querySelectorAll('form').forEach(function(f){f.addEventListener('submit',function(e){"
        "e.preventDefault();dirty=true;var act=(e.submitter&&e.submitter.value)||'';var opts;"
        "if(f.classList.contains('filepost')){opts={method:'POST',body:new FormData(f)};}"
        "else{var data=new URLSearchParams(new FormData(f));"
        "if(e.submitter&&e.submitter.name){data.set(e.submitter.name,e.submitter.value);}opts={method:'POST',body:data};}"
        "fetch('/action',opts).then(function(){"
        "if(act==='wo_close'||act==='rov2_end'){confetti();setTimeout(shut,700);}"
        "else if(act==='proj_delete'||act==='proj_archive'||act==='proj_add'){shut();}"
        "else{var r=f.getAttribute('data-reopen');if(r){last=r;}reopen();toast('\\u2713 opgeslagen');}});});});"
        "bd.querySelectorAll('textarea').forEach(mentionWire);"
        "bd.querySelectorAll('a.js-modal[data-href]').forEach(function(a){"
        "a.addEventListener('click',function(e){e.preventDefault();openCard(a.getAttribute('data-href'));});});"
        "var mems=bd.querySelector('.wo-mems');if(mems){var rows=[].slice.call(mems.querySelectorAll('.wo-mem')),sel=0;"
        "function paint(){rows.forEach(function(r,i){r.classList.toggle('sel',i===sel);});}if(rows.length)paint();"
        "mems.addEventListener('keydown',function(e){if(e.key==='ArrowDown'){sel=Math.min(rows.length-1,sel+1);paint();e.preventDefault();}"
        "else if(e.key==='ArrowUp'){sel=Math.max(0,sel-1);paint();e.preventDefault();}"
        "else if(e.key==='v'||e.key==='Enter'){var b=rows[sel]&&rows[sel].querySelector('.cl-check.ok');if(b)b.click();}"
        "else if(e.key==='x'){var b=rows[sel]&&rows[sel].querySelector('.cl-check.no');if(b)b.click();}});mems.focus();}"
        # Projectenbord IN de modal: kaartjes slepen (fetch + reopen) en klik -> projectdetails.
        "var dcsrf=(bd.querySelector(\"input[name=csrf]\")||{}).value||'';"
        "bd.querySelectorAll('.pcard[data-pid]').forEach(function(c){"
        "c.setAttribute('draggable','true');"
        "c.addEventListener('dragstart',function(e){window.__pdrag=true;e.dataTransfer.setData('text',c.getAttribute('data-pid'));"
        "e.dataTransfer.effectAllowed='move';c.style.opacity='.5';});"
        "c.addEventListener('dragend',function(){c.style.opacity='';setTimeout(function(){window.__pdrag=false;},60);});});"
        "bd.querySelectorAll('.pcol[data-to]').forEach(function(col){"
        "col.addEventListener('dragover',function(e){e.preventDefault();col.classList.add('over');});"
        "col.addEventListener('dragleave',function(){col.classList.remove('over');});"
        "col.addEventListener('drop',function(e){e.preventDefault();col.classList.remove('over');"
        "var pid=e.dataTransfer.getData('text');if(!pid)return;var to=col.getAttribute('data-to');"
        "var d=new URLSearchParams();d.set('csrf',dcsrf);d.set('pid',pid);d.set('next','/');"
        "if(to==='done'){d.set('action','proj_done');}else{d.set('action','proj_status');d.set('to',to);}"
        "fetch('/action',{method:'POST',body:d}).then(function(){reopen();toast('\\u2713 verplaatst');});});});"
        "bd.querySelectorAll('.pcard[data-href]').forEach(function(c){"
        "c.addEventListener('click',function(e){if(window.__pdrag)return;e.preventDefault();"
        "var href=c.getAttribute('data-href');"
        "if(last&&last.indexOf('/werkoverleg')>-1){"
        "href=href.replace(/[?&]back=[^&]*/,'');"
        "href+=(href.indexOf('?')>-1?'&':'?')+'back='+encodeURIComponent(last);}"
        "openCard(href);});});"
        "}"
        "document.querySelectorAll('.pcard[data-href],a.js-modal[data-href]').forEach(function(c){"
        "c.addEventListener('click',function(e){if(window.__pdrag)return;e.preventDefault();"
        "openCard(c.getAttribute('data-href'));});});"
        "ov.addEventListener('click',function(e){if(e.target===ov&&!window.__noclose)shut();});"
        "document.querySelector('.ovl-x').addEventListener('click',function(){if(!window.__noclose)shut();});"
        "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&ov.style.display!=='none'&&!window.__noclose)shut();});"
        "})();</script>")


def _group_meta(st: _Stores, p: dict, mode: str, node_owner: str):
    """(gid, sorteersleutel, label, add_owner, add_trekker) voor groeperen per persoon/rol."""
    owner = p.get("owner") or ""
    if mode == "rol":
        if owner.startswith(_II_PREFIX):
            return (("ii", owner), "zzz", "Individual Initiative", owner, "")
        orec = st.records.get(owner)
        nm = _name(orec) if orec else (owner or "—")
        return (("rol", owner), nm.lower(), nm, owner, "")
    if p.get("agent"):
        pa = st.personas.get(p["agent"])
        return (("persona", p["agent"]), "1", f"🤖 {(pa.name if pa else p['agent'])} (AI)",
                node_owner, f"persona:{p['agent']}")
    if p.get("person"):
        nm = _person_name(st, p["person"])
        return (("person", p["person"]), "0_" + nm.lower(), nm, node_owner, f"person:{p['person']}")
    return (("none",), "2", "Geen trekker", node_owner, "")


def _projects_board(st: _Stores, projs: list, owner: str, csrf_token: str, back: str,
                    group: str = "persoon", quickadd: bool = True) -> str:
    """Swimlanes per groep — alleen NIET-lege lanes (lege boards zijn ruis). Lege return → ''."""
    mode = group if group in ("persoon", "rol") else "persoon"
    groups: dict = {}
    for p in projs:
        gid, sk, label, ao, at = _group_meta(st, p, mode, owner)
        g = groups.setdefault(gid, {"sk": sk, "label": label, "items": [], "ao": ao, "at": at})
        g["items"].append(p)
    if not groups:
        return ""
    board = ""
    for gid, g in sorted(groups.items(), key=lambda kv: kv[1]["sk"]):
        board += (f"<div class='swim'><div class='swim-h'>{_e(g['label'])} ({len(g['items'])})</div>"
                  f"{_columns_html(st, g['items'], g['ao'], g['at'], csrf_token, back, quickadd=quickadd)}"
                  f"</div>")
    return board + _drag_script(csrf_token, back)


def _archived_html(st: _Stores, archived: list, csrf_token: str, back: str) -> str:
    if not archived:
        return ""
    rows = ""
    for p in archived:
        scope = p.get("scope")
        if isinstance(scope, dict):
            scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
        ctrl = ""
        if csrf_token:
            ctrl = (
                f" <form method='post' action='/action' style='display:inline'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(p['id'])}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='btn' type='submit' name='action' value='proj_unarchive'>herstellen</button>"
                f"<button type='submit' name='action' value='proj_delete' class='dellink' "
                f"onclick=\"return confirm('Definitief verwijderen?')\">verwijderen</button></form>")
        rows += f"<li class='muted'>{_e(str(scope or '—'))}{ctrl}</li>"
    return (f"<details style='margin-top:.6rem'><summary>🗄 Gearchiveerd ({len(archived)})</summary>"
            f"<ul class='clean'>{rows}</ul></details>")




def _projects_tab_html(st: _Stores, rec, csrf_token: str, group: str = "", add: bool = True) -> str:
    allp = st.projects.all()
    back_base = f"/node?id={rec.id}&tab=projects"

    addlink = _inline_add_project(st, rec, csrf_token, back_base) if add else ""

    if not org.is_circle(rec):
        # ROL: eigen projecten, gegroepeerd per persoon (de doener). Lege lanes tonen we niet.
        projs = [p for p in allp if p.get("owner") == rec.id and not p.get("archived")]
        archived = [p for p in allp if p.get("owner") == rec.id and p.get("archived")]
        board = _projects_board(st, projs, rec.id, csrf_token, back_base, "persoon", quickadd=add)
        if not board:
            board = ("<p class='muted'>Nog geen projecten. Voeg er een toe met + project.</p>" if add
                     else "<p class='muted'>Nog geen projecten.</p>")
        head = (f"<div style='margin-bottom:1rem'>"
                f"<h3 style='margin:0;display:inline'>Projecten ({len(projs)})</h3> &nbsp; {addlink}</div>")
        return f"<div class='c2-sec'>{head}{board}{_archived_html(st, archived, csrf_token, back_base)}</div>"

    # CIRKEL: doet zelf geen uitvoerend werk. Toont projecten van haar DIRECTE rollen +
    # Individual Initiative. Lege lanes tonen we niet; subcirkels = eigen bord (niet aggregeren).
    g = group if group in ("persoon", "rol") else "rol"
    direct = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    rids = {r.id for r in direct}
    ii = f"{_II_PREFIX}{rec.id}"
    projs = [p for p in allp if (p.get("owner") in rids or p.get("owner") == ii) and not p.get("archived")]
    back = f"{back_base}&group={g}"
    board = _projects_board(st, projs, rec.id, csrf_token, back, g, quickadd=add)
    if not board:
        board = ("<p class='muted'>Nog geen projecten. Voeg er een toe met + project.</p>" if add
                 else "<p class='muted'>Nog geen projecten.</p>")
    subs = sorted(org.subcircles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    sub_html = ""
    if subs:
        lis = "".join(f"<li><a href='/node?id={_e(s.id)}&tab=projects'>{_e(_name(s))}</a> "
                      f"<span class='muted'>→ eigen projectenbord</span></li>" for s in subs)
        sub_html = (f"<div class='c2-sec'><h3>Subcirkels</h3>"
                    f"<p class='muted' style='font-size:.8rem'>Een subcirkel heeft een eigen "
                    f"projectenbord.</p><ul class='clean'>{lis}</ul></div>")
    on = lambda v: " on" if g == v else ""
    switch = (f"<div class='vswitch'>Groeperen: "
              f"<a class='vbtn{on('rol')}' href='{back_base}&group=rol'>per rol</a>"
              f"<a class='vbtn{on('persoon')}' href='{back_base}&group=persoon'>per persoon</a></div>")
    head = (f"<div style='display:flex;align-items:center;justify-content:space-between;"
            f"flex-wrap:wrap;gap:.6rem;margin-bottom:1rem'>"
            f"<div><h3 style='margin:0;display:inline'>Projecten ({len(projs)})</h3> &nbsp; {addlink}</div>"
            f"{switch}</div>")
    return f"<div class='c2-sec'>{head}{board}{sub_html}</div>"


def _person_projects_html(st: _Stores, pid: str) -> str:
    role_ids = set(st.assign.roles_of("person", pid))
    projs = [p for p in st.projects.all()
             if not p.get("archived") and (p.get("person") == pid or p.get("owner") in role_ids)]
    projs.sort(key=lambda p: (p.get("status") == "done", -(p.get("created_at") or 0)))
    if not projs:
        return ""
    items = ""
    for p in projs:
        orec = st.records.get(p.get("owner"))
        owner = _e(_name(orec) if orec else (p.get("owner") or ""))
        scope = p.get("scope")
        if isinstance(scope, dict):
            scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
        items += (f"<li>{_proj_chip(p.get('status',''))} {_e(str(scope or '—'))} "
                  f"<span class='muted'>· {owner}</span></li>")
    return f"<div class='c2-sec'><h3>Projecten ({len(projs)})</h3><ul class='clean'>{items}</ul></div>"


from nooch_village.views.checklists import (
    _cl_target_label, _cl_spark, _cl_row,
    _checklists_tab_html, _checklists_html,
)
from nooch_village.views.metrics import (
    _source_samples, _metric_points, _spark_svg, _kpi_card,
    _metric_add_forms, _shopify_window, _sources_for, _werk_fetch,
    _tile_combos, _tile_meta, _fetch, _num, _agg,
    _render_bullet, _data_table, _delta_badge, _render_burnup,
    _render_form, _grondslag, _grondslag_popover, _llm_says_comparable,
    _render_tile, _kpi_id_from_def, _goal_options, _metric_csv,
    _kpi_data_row, _def_tokens, _role_text, _role_relevant_defs,
    _metrics_tab_html, _break_indices, _link_card,
    _dir_select, _cad_select, _mt_select, _opt_select,
    _aard_chips, _mw_select, _mw_chip,
    render_kpi_composer,
    _MW, _SOURCE_KPIS, _RICHTING, _ORIGIN_LABEL,
)


from nooch_village.views.catalog import (
    _catalog_edit_form, _catalog_card,
    _catalog_add_form, render_catalog,
)


def render_node(st: _Stores, node_id: str, tab: str, csrf_token: str = "", msg: str = "",
                group: str = "", clf: str = "due", mw: str = "maand") -> str:
    rec = st.records.get(node_id)
    if rec is None:
        return _page("Niet gevonden", "<p>Node niet gevonden.</p><p><a href='/'>← home</a></p>")
    is_c = org.is_circle(rec)
    tabs = _CIRCLE_TABS if is_c else _ROLE_TABS
    if tab not in tabs:
        tab = "overview"
    recs = st.records.all()
    crumb = " › ".join(
        f"<a href='/node?id={_e(i)}'>{_e(_name(st.records.get(i)))}</a>"
        for i in org.breadcrumb(recs, node_id))
    chip = "<span class='chip'>cirkel</span>" if is_c else "<span class='chip'>rol</span>"

    if tab == "overview":
        content = _overview_html(st, rec, csrf_token)
    elif tab == "roles":
        content = _roles_html(st, rec, csrf_token)
    elif tab == "members":
        content = _members_html(st, rec)
    elif tab == "notes":
        content = ("<div class='c2-sec'><h3>Notes</h3>"
                   + _att_html(st, rec, "note", "Nog geen notities op deze rol/cirkel.")
                   + "<p class='muted' style='font-size:.8rem'>Hierin vouwen we Nooch's "
                   "concurrenten-notities.</p></div>")
    elif tab == "metrics":
        content = _metrics_tab_html(st, rec, csrf_token, win=mw)
    elif tab == "checklists":
        content = _checklists_tab_html(st, rec, csrf_token, flt=clf)
    elif tab == "projects":
        content = _projects_tab_html(st, rec, csrf_token, group=group)
    elif tab == "policies":
        content = _todo("Policies per cirkel (nu alleen harde policies op de anchor-cirkel).")
    else:  # history
        content = _todo("Wijzigingsgeschiedenis per rol/cirkel (records dragen al versies; de "
                        "weergave moet nog).")

    # Meetings zijn een CIRKEL-functie (een rol heeft geen governance/tactical meeting).
    if is_c and csrf_token:
        rov_url = f"/roloverleg2?circle={_e(node_id)}"
        open_cls = "btn ok" if _rov_items(st, node_id) else "btn"   # groen = lopend roloverleg
        wo_url = f"/werkoverleg?circle={_e(node_id)}"
        wo_cls = "btn ok" if st.werk.is_open(node_id) else "btn"    # groen = lopend werkoverleg
        meet = (f"<div class='c2-meet'>"
                f"<a class='{open_cls} js-modal' href='{rov_url}' data-href='{rov_url}'>Governance meeting</a>"
                f"<a class='{wo_cls} js-modal' href='{wo_url}' data-href='{wo_url}'>Tactical meeting</a></div>")
    else:
        meet = ""
    main = (f"<div class='c2-main'><div class='c2-bar'>{crumb}</div>"
            f"<h1>{_e(_name(rec))} {chip}</h1>{_banner(msg)}{meet}"
            f"{_tabbar(node_id, tabs, tab)}{content}</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, node_id)}</div>"
    modal = _modal_html(json.dumps(_mentionables(st)[0])) if csrf_token else ""
    inner = (f"<style>{_EXTRA_CSS}</style>"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/catalog'>catalogus</a></div>"
             f"<div class='c2-wrap'>{main}{rail}</div>{modal}")
    return _page(_name(rec), inner)


def render_person(st: _Stores, pid: str) -> str:
    p = st.people.get(pid)
    if p is None:
        return _page("Niet gevonden", "<p>Persoon niet gevonden.</p><p><a href='/'>← home</a></p>")
    role_ids = st.assign.roles_of("person", pid)
    rows = ""
    for rid in sorted(role_ids):
        rec = st.records.get(rid)
        if rec is None:
            continue
        crumb = " › ".join(_e(_name(st.records.get(i)))
                           for i in org.breadcrumb(st.records.all(), rid)[:-1])
        rows += (f"<li><a href='/node?id={_e(rid)}'>{_e(_name(rec))}</a> "
                 f"<span class='muted'>{('· ' + crumb) if crumb else ''}</span></li>")
    # Notificaties: @-mentions van mij of van een rol die ik vervul.
    targets = {("person", pid)} | {("role", rid) for rid in role_ids}
    notes = st.notif.for_targets(targets)
    nrows = ""
    for n in notes[:25]:
        proj = st.projects.get(n.get("project_id"))
        ptitle = _scope_text(proj) if proj else "project"
        href = f"/project?pid={_e(n.get('project_id',''))}&back={urllib.parse.quote('/person?id=' + pid, safe='')}"
        dot = "" if n.get("read") else "<span class='nt-dot'></span>"
        nrows += (f"<li class='nt-item'>{dot}<a class='js-modal' href='{href}' data-href='{href}'>"
                  f"{_e(ptitle)}</a> <span class='muted'>· {_e((n.get('snippet') or '')[:80])}</span> "
                  f"<span class='muted' style='font-size:.72rem'>{_e(_age(n.get('at')))}</span></li>")
    unread = sum(1 for n in notes if not n.get("read"))
    notif_html = (f"<div class='c2-sec'><h3>🔔 Notificaties ({unread} nieuw)</h3>"
                  + (f"<ul class='clean nt-list'>{nrows}</ul>" if nrows
                     else "<span class='muted'>Geen notificaties.</span>") + "</div>")
    main = (f"<div class='c2-main'><h1><span class='av' style='width:28px;height:28px'>"
            f"{_e(_initials(p.name))}</span> {_e(p.name)}</h1>"
            f"<div class='muted'>{_e(p.email) or 'geen e-mail'}</div>"
            f"{notif_html}"
            f"<div class='c2-sec'><h3>Mijn rollen ({len(role_ids)})</h3>"
            + (f"<ul class='clean'>{rows}</ul>" if rows else "<span class='muted'>Geen rollen.</span>")
            + "</div>" + _person_projects_html(st, pid) + "</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, '')}</div>"
    inner = (f"<style>{_EXTRA_CSS}</style>"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}{rail}</div>")
    return _page(p.name, inner)


def render_patterns(csrf_token: str = "") -> str:
    """Levende styleguide: elk atoom/molecuul één keer. Bron van waarheid; geen losse varianten."""
    def sec(title, body):
        return f"<div class='c2-sec'><h3>{_e(title)}</h3><div style='display:flex;gap:.5rem;flex-wrap:wrap;align-items:center'>{body}</div></div>"
    buttons = ("<button class='btn ok'>Primair</button>"
               "<button class='btn'>Neutraal</button>"
               "<button class='btn no'>Gevaar</button>"
               "<button class='btn ok sm'>Primair sm</button>"
               "<button class='btn sm'>Neutraal sm</button>"
               "<button class='btn ghost sm'>Ghost sm</button>"
               "<a class='dellink' href='#'>verwijderen</a>")
    chips = ("<span class='chip green'>green</span><span class='chip muted'>muted</span>"
             "<span class='chip outline'>outline</span><span class='chip coral'>coral</span>"
             "<span class='chip coral-solid'>Overdue</span><span class='chip'>tint (default)</span>"
             "<span class='badge ro'>read</span><span class='badge rw'>edit</span>")
    cards = (f"<button class='acard'>{_IC_CLOCK}<span>Datum</span></button>"
             f"<button class='acard'>{_IC_CHECK}<span>Checklist</span></button>"
             f"<button class='acard acard-off' disabled>{_IC_TARGET}<span>Goals</span></button>")
    att = f"<div class='attcard'><span class='att-ic'>{_IC_LINK}</span><a class='att-name' href='#'>voorbeeld bijlage</a></div>"
    due = (f"<span class='chip outline'>{_IC_CLOCK}25 jun 2026</span>"
           f"<span class='chip coral'>{_IC_CLOCK}1 jan 2020</span><span class='chip coral-solid'>Overdue</span>")
    av = _avatar("Stefan Wobben", False) + _avatar("Codie", True)
    icons = (f"<span class='manage-ico' title='persoon toevoegen'>{_ICON_ADD_PERSON}</span>"
             f"<span class='manage-ico' title='reactie toevoegen'>{_ICON_ADD_EMOJI}</span>")
    body = (sec("Knoppen — atoom: .btn [.ok|.no] [.sm] [.ghost] + .dellink", buttons)
            + sec("Lijn-iconen (neutraal, currentColor)", icons)
            + sec("Status & chips & badges", chips)
            + sec("Action-cards (molecule)", cards)
            + sec("Bijlage-card", att)
            + sec("Deadline-chip", due)
            + sec("Avatar", av))
    main = (f"<div class='c2-main'><h1>Patterns</h1>"
            f"<p class='muted'>Levende referentie. Gebruik deze atomen en moleculen; verzin geen varianten.</p>{body}</div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · patterns · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Patterns", inner)



from nooch_village.views.noochie import (
    _noochie_suggest, _noochie_reply,
    render_noochie, _noochie_chrome,
)

from nooch_village.views.werkoverleg import (
    _wo_hid, _wo_checkin, _wo_checklist, _wo_metrics,
    _wo_spanning_add, _wo_spanning_items, _wo_triage,
    _wo_checkout, _wo_summary, render_werkoverleg,
)


_IC_DESC = _ic("<line x1='4' y1='7' x2='20' y2='7'/><line x1='4' y1='12' x2='20' y2='12'/>"
               "<line x1='4' y1='17' x2='14' y2='17'/>")

_IC_GEAR = _ic("<circle cx='12' cy='12' r='3'/><path d='M19 12a7 7 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6a7 7 0 0 0 .1-1z'/>")
_IC_CLOCK = _ic("<circle cx='12' cy='12' r='9'/><polyline points='12 7 12 12 15 14'/>")
_IC_FILE = _ic("<path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><path d='M14 3v5h5'/>")


_IC_TARGET = _ic("<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1.5'/>")



def render_project(st: _Stores, pid: str, csrf_token: str = "", msg: str = "", back: str = "/",
                   fragment: bool = False) -> str:
    p = st.projects.get(pid)
    if p is None:
        if fragment:
            return "<p class='muted'>Project bestaat niet meer.</p>"
        return _page("Niet gevonden", "<p>Project niet gevonden.</p><p><a href='/'>← home</a></p>")
    if not back.startswith("/"):
        back = "/"
    orec = st.records.get(p.get("owner"))
    owner_link = (f"<a href='/node?id={_e(p['owner'])}'>{_e(_name(orec))}</a>" if orec
                  else _e(p.get("owner") or ""))
    rw = bool(csrf_token)

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(f'/project?pid={pid}&back=' + urllib.parse.quote(back, safe=''))}'>")

    status = p.get("status", "")

    # ---- Rechterkolom: de dialoog (mensen + AI) ----
    role_name = _name(orec) if orec else ""
    mention_names = [m["l"] for m in _mentionables(st)[0]]   # voor highlight in de bubble
    # Nieuwste boven.
    feed = "".join(_feed_entry_html(st, m, role_name=role_name, pid=pid, csrf_token=csrf_token,
                                    mention_names=mention_names)
                   for m in reversed(p.get("log") or []))
    if not feed:
        feed = "<p class='muted'>Nog geen updates of reacties.</p>"
    composer = ""
    if rw:
        # Directe textarea met mini-toolbar op de gele achtergrond; Plaatsen links uitgelijnd.
        composer = (f"<form method='post' action='/action' class='pf comp-form'>{hid()}"
                    f"<input type='hidden' name='author' value='human:'>"
                    f"<div class='editor'>"
                    f"<div class='editor-tb'>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'**','**')\" title='Vet'><b>B</b></button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'*','*')\" title='Cursief'><i>I</i></button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'~~','~~')\" title='Doorhalen'><s>S</s></button>"
                    f"<span class='tb-sep'></span>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'- ','')\" title='Lijst'>•</button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'## ','')\" title='Kop'>H</button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'[','](url)')\" title='Link'>{_IC_LINK}</button>"
                    f"<details class='emoji-pick tb-help'><summary title='Opmaak-hulp'>?</summary>"
                    f"<div class='md-help'>**vet** · *cursief* · ~~doorhalen~~ · # kop · - lijst · [tekst](url)</div>"
                    f"</details></div>"
                    f"<textarea name='text' rows='2' placeholder='Schrijf een reactie…'></textarea>"
                    f"</div>"
                    f"<div class='comp-row'>"
                    f"<button class='btn ok sm' type='submit' name='action' value='proj_feed'>Plaatsen</button>"
                    f"</div></form>")
        ai = _owner_ai(st, orec)
        if ai is not None:
            composer += (f"<form method='post' action='/action' class='ai-ask'>{hid()}"
                         f"<button class='btn ghost sm ai-ask-btn' type='submit' name='action' value='ai_reply'>"
                         f"🤖 Vraag {_e(ai.name)} om mee te denken</button></form>")
    discussie = _psec(_IC_CHAT, "Dialoog", composer + feed)   # schrijf-box boven, reacties eronder

    # ---- Status zit volledig in het …-menu (huidige status gemarkeerd); geen los chip-label ----
    menu = ""
    if rw:
        st_items = ""
        for label, key, statuses in _PROJ_COLS:
            act = "proj_done" if key == "done" else "proj_status"
            to = "" if key == "done" else f"<input type='hidden' name='to' value='{key}'>"
            on = " on" if status in statuses else ""
            st_items += (f"<form method='post' action='/action'>{hid()}{to}"
                         f"<button class='menuitem{on}' type='submit' name='action' value='{act}'>{_e(label)}</button></form>")
        menu = (f"<details class='cardmenu'><summary class='statustrigger' aria-label='status wijzigen'>"
                f"{_proj_chip(status)}<span class='caret'>▾</span></summary><div class='cardmenu-b'>"
                f"<div class='menu-h'>Status</div>{st_items}<div class='menu-sep'></div>"
                f"<form method='post' action='/action'>{hid()}<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='menuitem' type='submit' name='action' value='proj_archive'>Archiveren</button></form>"
                f"<form method='post' action='/action'>{hid()}<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='menuitem danger' type='submit' name='action' value='proj_delete' "
                f"onclick=\"return confirm('Definitief verwijderen? Archiveren bewaart het project.')\">Verwijderen</button>"
                f"</form></div></details>")

    # ---- Header (volledige breedte): titel inline + status + …-menu ----
    if rw:
        title = (f"<form method='post' action='/action' class='titleform'>{hid()}"
                 f"<input class='title-edit' name='scope' value='{_e(_scope_text(p))}' aria-label='projecttitel'>"
                 f"<button class='btn ok sm title-save' type='submit' name='action' value='proj_rename'>opslaan</button></form>")
    else:
        title = f"<h2 class='ptitle-ro'>{_e(_scope_text(p))}</h2>"
    # Deadline-chip vóór de status (overzicht), met Overdue-markering.
    due_head = ""
    if p.get("due"):
        over = _due_overdue(p["due"])
        badge = "<span class='chip coral-solid'>Overdue</span>" if over else ""
        due_head = (f"<span class='chip {'coral' if over else 'outline'}'>"
                    f"{_IC_CLOCK}{_e(_fmt_due(p['due']))}</span>{badge}")
    head = (f"<div class='pcard-head'>{title}"
            f"<div class='pcard-head-r'>{due_head}{menu or _proj_chip(status)}</div></div>")

    # ---- Details: kader zonder achtergrond, tweekoloms, links uitgelijnd, altijd open ----
    owner = p.get("owner", "")
    if owner.startswith(_II_PREFIX):
        rol_naam = "Individual Initiative"
    else:
        rol_naam = _name(orec) if orec else (owner or "—")
    rol_v = (f"<a href='/node?id={_e(owner)}'>{_e(rol_naam)}</a>" if orec else _e(rol_naam))
    if p.get("agent"):
        pa = st.personas.get(p["agent"])
        pers_v = f"{_e(pa.name if pa else p['agent'])} (AI)"
    elif p.get("person"):
        pers_v = f"<a href='/person?id={_e(p['person'])}'>{_e(_person_name(st, p['person']))}</a>"
    else:
        pers_v = "<span class='muted'>—</span>"
    if rw:
        vis_v = (f"<form method='post' action='/action' class='visform'>{hid()}"
                 f"<input type='hidden' name='action' value='proj_setprivate'>"
                 f"<label><input type='checkbox' name='private' value='1'"
                 f"{' checked' if p.get('private') else ''} "
                 f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
                 f" alleen voor deze cirkel</label></form>")
    else:
        vis_v = "Alleen voor deze cirkel" if p.get("private") else "Hele cirkel-boom"
    details = (
        f"<div class='detailsbox'><div class='psec-h'>{_IC_INFO}<span>Details</span></div>"
        f"<div class='dcol'>"
        f"<span class='dk'>Rol</span><span class='dv'>{rol_v}</span>"
        f"<span class='dk'>Persoon</span><span class='dv'>{pers_v}</span>"
        f"<span class='dk'>Aangemaakt</span><span class='dv'>{_e(_created_full(p.get('created_at')))}</span>"
        f"<span class='dk'>Zichtbaar</span><span class='dv'>{vis_v}</span>"
        f"</div></div>")

    # ---- Omschrijving (inline, omkaderd) ----
    if rw:
        desc_body = (f"<form method='post' action='/action' class='descform'>{hid()}"
                     f"<textarea name='description' rows='3' placeholder='Voeg een omschrijving toe…'>"
                     f"{_e(p.get('description',''))}</textarea>"
                     f"<button class='btn ok' type='submit' name='action' value='proj_describe' "
                     f"style='margin-top:.3rem'>opslaan</button></form>")
    else:
        desc_body = f"<div>{_e(p.get('description','')) or '<span class=muted>geen omschrijving</span>'}</div>"
    omschrijving = _psec(_IC_DESC, "Omschrijving", desc_body)

    # ---- Bijlagen-overzicht: Links + Bestanden (card-pattern). Toevoegen via de Bijlage-kaart. ----
    def _att_rm(aid):
        return ("" if not rw else
                f"<form method='post' action='/action' class='att-x'>{hid()}"
                f"<input type='hidden' name='aid' value='{_e(aid)}'>"
                f"<button class='dellink' type='submit' name='action' value='attach_remove' "
                f"title='verwijderen'>✕</button></form>")
    link_cards, file_cards = "", ""
    for a in (p.get("attachments") or []):
        if a.get("kind", "link") == "file":
            nm = a.get("title") or a.get("name", "bestand")
            href = f"/file?pid={_e(pid)}&aid={_e(a.get('id', ''))}"
            file_cards += (f"<div class='attcard'><span class='att-ic'>{_IC_FILE}</span>"
                           f"<a class='att-name' href='{href}' target='_blank' rel='noopener'>{_e(nm)}</a>"
                           f"{_att_rm(a.get('id', ''))}</div>")
        else:
            nm = a.get("title") or _link_host(a.get("url", ""))
            link_cards += (f"<div class='attcard'><span class='att-ic'>{_IC_LINK}</span>"
                           f"<a class='att-name' href='{_e(a.get('url', ''))}' target='_blank' rel='noopener'>{_e(nm)}</a>"
                           f"{_att_rm(a.get('id', ''))}</div>")
    verrijking = ""
    if link_cards:
        verrijking += _psec(_IC_LINK, "Links", link_cards)
    if file_cards:
        verrijking += _psec(_IC_FILE, "Bijlagen", file_cards)

    checklists_html = _checklists_html(p, csrf_token, pid, back, rw)

    # ---- Actie-kaarten (Trello 'Add to card') ----
    actioncards = ""
    if rw:
        due = p.get("due") or ""
        due_lbl = _fmt_due(due) or "Datum"
        date_rm = ("" if not due else
                   f"<form method='post' action='/action' style='margin-top:.5rem'>{hid()}"
                   f"<input type='hidden' name='action' value='proj_setdue'>"
                   f"<input type='hidden' name='due' value=''>"
                   f"<button class='dellink' type='submit'>datum verwijderen</button></form>")
        date_card = (
            f"<details class='acard-d'><summary class='acard'>"
            f"{_IC_CLOCK}<span>{_e(due_lbl)}</span></summary>"
            f"<div class='datepop'><form method='post' action='/action'>{hid()}"
            f"<input type='hidden' name='action' value='proj_setdue'>"
            f"<input type='date' name='due' value='{_e(due)}' "
            f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
            f"</form>{date_rm}</div></details>")
        checklist_card = (
            f"<details class='acard-d'><summary class='acard'>{_IC_CHECK}<span>Checklist</span></summary>"
            f"<div class='datepop'><form method='post' action='/action'>{hid()}"
            f"<input name='title' placeholder='Naam checklist'>"
            f"<button class='btn ok' type='submit' name='action' value='checklist_add' "
            f"style='margin-left:.4rem'>Voeg toe</button></form></div></details>")
        nxt_full = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        bijlage_card = (
            f"<details class='acard-d'><summary class='acard'>{_IC_LINK}<span>Bijlage</span></summary>"
            f"<div class='datepop att-pop'>"
            f"<form method='post' action='/action' enctype='multipart/form-data' class='filepost'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='pid' value='{_e(pid)}'>"
            f"<input type='hidden' name='action' value='attach_file'>"
            f"<input type='hidden' name='next' value='{_e(nxt_full)}'>"
            f"<label class='att-lbl'>Bestand van je computer</label>"
            f"<input type='file' name='file'>"
            f"<button class='btn ok sm' type='submit' style='margin-top:.4rem'>Upload</button></form>"
            f"<div class='att-sep'></div>"
            f"<form method='post' action='/action'>{hid()}"
            f"<label class='att-lbl'>Of een link plakken</label>"
            f"<input name='url' placeholder='https://…'>"
            f"<input name='title' placeholder='Naam (optioneel)' style='margin-top:.3rem'>"
            f"<button class='btn ok sm' type='submit' name='action' value='attach_add' "
            f"style='margin-top:.4rem'>Toevoegen</button></form>"
            f"</div></details>")
        actioncards = (
            "<div class='actioncards'>"
            f"{date_card}{checklist_card}{bijlage_card}"
            f"<button type='button' class='acard acard-off' disabled "
            f"title='binnenkort'>{_IC_TARGET}<span>Goals</span></button>"
            "</div>")

    labelbar = ""
    if _LABELS.get(p.get("label")):
        labelbar = f"<div class='clabel' style='background:{_LABELS[p['label']]};height:8px;border-radius:4px;margin-bottom:.6rem'></div>"

    # Geopend vanuit het werkoverleg: prominente terug-CTA boven én onder; het kruisje wordt
    # uitgeschakeld (zie modal-JS via data-noclose) zodat je via deze CTA terugkeert.
    meeting = back.startswith("/werkoverleg")
    wo_cta = (f"<a class='btn ok sm js-modal' href='{_e(back)}' data-href='{_e(back)}'>"
              f"← terug naar werkoverleg</a>") if meeting else ""
    top_bar = f"<div class='wo-back-bar'>{wo_cta}</div>" if meeting else ""
    foot_bar = f"<div class='wo-back-bar wo-back-foot'>{wo_cta}</div>" if meeting else ""

    maincol = details + actioncards + omschrijving + checklists_html + verrijking
    detail = (f"{top_bar}{labelbar}{_banner(msg)}{head}"
              f"<div class='pgrid'><div class='pmain'>{maincol}</div>"
              f"<aside class='pdisc'>{discussie}</aside></div>{foot_bar}")
    if fragment:
        return f"<div data-noclose='1'>{detail}</div>" if meeting else detail
    main = (f"<div class='c2-main' style='max-width:980px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{detail}</div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · projectdetail · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page(_scope_text(p), inner)




def render_rolefillers(st: _Stores, role_id: str, csrf_token: str = "", fragment: bool = False) -> str:
    rec = st.records.get(role_id)
    if rec is None:
        return ("<p class='muted'>Onbekende rol.</p>" if fragment
                else _page("Niet gevonden", "<p>Onbekend.</p>"))
    back = f"/node?id={(rec.parent or rec.id)}&tab=roles"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='role' value='{_e(role_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")

    fillers = st.assign.fillers_of(role_id, record=rec)
    rows = ""
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id); label = (p.name if p else f.id); ai = False
            name = f"<a href='/person?id={_e(f.id)}'>{_e(label)}</a>"
        else:
            pa = st.personas.get(f.id); label = (pa.name if pa else f.id); ai = True
            name = f"{_e(label)} (AI)"
        prev = f" <span class='muted' style='font-size:.8rem'>· {_e(f.focus)}</span>" if f.focus else ""
        rows += (
            f"<div class='frow'>"
            f"<details class='ffocus' style='flex:1'>"
            f"<summary>{_avatar(label, ai)} {name}{prev}</summary>"
            f"<form method='post' action='/action' style='margin:.3rem 0 .2rem 30px'>{hid()}"
            f"<input type='hidden' name='filler' value='{f.type}:{_e(f.id)}'>"
            f"<input name='focus' value='{_e(f.focus)}' placeholder='Focus (optioneel)' "
            f"style='padding:.3rem .4rem;border:1px solid var(--border);border-radius:var(--radius)'> "
            f"<button class='btn' type='submit' name='action' value='role_focus'>Focus opslaan</button>"
            f"</form></details>"
            f"<form method='post' action='/action' style='display:inline'>{hid()}"
            f"<input type='hidden' name='filler' value='{f.type}:{_e(f.id)}'>"
            f"<button class='dellink' type='submit' name='action' value='role_unassign'>verwijderen</button>"
            f"</form></div>")
    if not rows:
        rows = "<p class='muted'>Nog niemand toegewezen.</p>"
    # Alleen mensen vervullen een rol; AI koppel je per accountability (niet hier).
    opts = "<option value=''>— kies persoon —</option>"
    opts += "".join(f"<option value='person:{_e(p.id)}'>{_e(p.name)}</option>" for p in st.people.all())
    add = (f"<div class='pf' style='margin-top:.6rem'><form method='post' action='/action'>{hid()}"
           f"<label>Toevoegen aan {_e(_name(rec))}</label>"
           f"<select name='filler'>{opts}</select>"
           f"<button class='btn ok' type='submit' name='action' value='role_assign' "
           f"style='margin-top:.4rem'>Toewijzen</button></form></div>")
    frag = (f"<h2 style='margin-top:0'>Rolvervullers beheren — {_e(_name(rec))}</h2>"
            f"<div>{rows}</div>{add}")
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{frag}</div>")
    return _page("Rolvervullers", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")


def render_aitask(st: _Stores, role_id: str, acc_index: int, csrf_token: str = "",
                  fragment: bool = False) -> str:
    rec = st.records.get(role_id)
    accs = rec.definition.accountabilities if rec else []
    acc_text = accs[acc_index] if (rec and 0 <= acc_index < len(accs)) else ""
    back = f"/node?id={role_id}&tab=overview"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='role' value='{_e(role_id)}'>"
                f"<input type='hidden' name='acc' value='{acc_index}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")

    def pickform(agent: str, skill: str, label: str, cls: str) -> str:
        return (f"<form method='post' action='/action' style='display:inline'>{hid()}"
                f"<input type='hidden' name='pick' value='{_e(agent)}::{_e(skill)}'>"
                f"<button class='{cls}' type='submit' name='action' value='aitask_add'>{label}</button></form>")

    # 1) Voorgesteld: (AI, skill) die lexicaal bij deze accountability past (het cadeautje).
    sugg = _suggest_for_acc(st, role_id, acc_index, acc_text)
    sugg_html = ""
    if sugg:
        items = "".join(f"<div class='frow'><span style='flex:1'>🤖 {_e(p.name)} · {_e(sk)}</span>"
                        f"{pickform(p.id, sk, 'koppel', 'btn ok')}</div>" for p, sk in sugg)
        sugg_html = (f"<div class='sugg'><div class='sugg-h'>🎁 Voorgesteld</div>{items}</div>")

    # 2) Al gekoppeld: verwijderbaar.
    rows = ""
    for t in st.ai.for_acc(role_id, acc_index):
        rows += (f"<div class='frow'><span style='flex:1'>{_ai_chip(st, t)}</span>"
                 f"<form method='post' action='/action' style='display:inline'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='tid' value='{_e(t.id)}'>"
                 f"<input type='hidden' name='next' value='{_e(back)}'>"
                 f"<button class='dellink' type='submit' name='action' value='aitask_remove'>verwijderen</button>"
                 f"</form></div>")

    # 3) Selecteren uit een rugzakje (geen vrije tekst): combinaties AI · skill, niet al gekoppeld.
    personas = st.personas.all()
    attached = {(t.agent, t.wat) for t in st.ai.for_acc(role_id, acc_index)}
    combos = [(p, sk) for p in personas for sk in (p.skills or []) if (p.id, sk) not in attached]
    if combos:
        opts = "".join(f"<option value='{_e(p.id)}::{_e(sk)}'>🤖 {_e(p.name)} · {_e(sk)}</option>"
                       for p, sk in combos)
        select = (f"<div class='pf'><form method='post' action='/action'>{hid()}"
                  f"<label>Kies een skill uit het rugzakje van een AI</label>"
                  f"<select name='pick'>{opts}</select>"
                  f"<button class='btn ok' type='submit' name='action' value='aitask_add' "
                  f"style='margin-top:.4rem'>Koppel</button></form></div>")
    elif personas:
        select = "<p class='muted'>Alle skills van de AI's zijn hier al gekoppeld, of de rugzakjes zijn leeg.</p>"
    else:
        select = ("<p class='muted'>Er zijn nog geen AI-inwoners. Maak er eerst een aan, "
                  "dan kun je een skill koppelen.</p>")

    # 4) Rugzak uitbreiden (set-up): een nieuwe skill aan een AI toevoegen.
    bag = ""
    if personas:
        popts = "".join(f"<option value='{_e(p.id)}'>🤖 {_e(p.name)}</option>" for p in personas)
        bag = (f"<details class='bagadd'><summary>Rugzak van een AI uitbreiden</summary>"
               f"<form method='post' action='/action'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
               f"<input type='hidden' name='next' value='{_e(back + '&_aitask=' + str(acc_index))}'>"
               f"<label>AI-inwoner</label><select name='agent'>{popts}</select>"
               f"<label>Nieuwe skill</label><input name='skill' placeholder='bijv. schrijft de code'>"
               f"<button class='btn' type='submit' name='action' value='persona_skill_add' "
               f"style='margin-top:.4rem'>Aan rugzak toevoegen</button></form></details>")

    frag = (f"<h2 style='margin-top:0'>AI op deze accountability</h2>"
            f"<p class='muted'>Accountability: {_e(acc_text) or '—'}</p>"
            f"<p style='font-size:.82rem;color:var(--gray)'>De mens blijft verantwoordelijk; de AI "
            f"voert <b>zelfstandig</b> een skill uit z'n rugzakje uit. Je typt niets, je "
            f"<b>selecteert</b> een skill.</p>{sugg_html}{rows}{select}{bag}")
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{frag}</div>")
    return _page("AI op accountability", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")


def _owner_ai(st: _Stores, orec):
    """De AI-inwoner (persona) die de eigenaar-rol vervult, of None."""
    if orec is None:
        return None
    for f in st.assign.fillers_of(orec.id, record=orec):
        if f.type == "persona":
            return st.personas.get(f.id)
    return None


def _ai_reply(st: _Stores, pid: str, ask=None) -> bool:
    """Laat de AI-inwoner van de eigenaar-rol kort meedenken in de dialoog (op verzoek).
    `ask(prompt)->str|None` is injecteerbaar (test); standaard via llm.reason. Fail-closed."""
    p = st.projects.get(pid)
    if p is None:
        return False
    orec = st.records.get(p.get("owner"))
    persona = _owner_ai(st, orec)
    if persona is None:
        return False
    recent = "\n".join(f"- {m.get('text', '')}" for m in (p.get("log") or [])[-6:])
    ctx = (f"Project: {_scope_text(p)}\n"
           f"Omschrijving: {p.get('description', '') or '(geen)'}\n"
           f"Rol: {_name(orec)} — purpose: {orec.definition.purpose}\n"
           f"Recente dialoog:\n{recent or '(nog leeg)'}\n\n"
           f"Reageer kort (max 4 zinnen) en concreet als deze rol: geef een volgende stap of inzicht.")
    from nooch_village.personas import persona_prompt
    prompt = (persona_prompt(persona) + "\n\n" + ctx).strip()
    if ask is None:
        try:
            from nooch_village import llm
            out = llm.reason(prompt, ladder=_match_ladder())
        except Exception:
            out = None
    else:
        out = ask(prompt)
    if not out:
        return False
    st.projects.add_feed_entry(pid, out.strip(), kind="comment",
                              author_type="persona", author_id=persona.id)
    return True


def _parse_trekker(val: str):
    """'person:<id>' of 'persona:<id>' → (person_id of '', agent_id of '')."""
    val = (val or "").strip()
    if val.startswith("person:"):
        return val[7:], ""
    if val.startswith("persona:"):
        return "", val[8:]
    return "", ""


def dispatch(data_dir: str, action: str, form: dict):
    """Verwerk een POST-actie. Geeft (redirect-URL, korte bevestiging) terug."""
    st = _Stores(data_dir)
    g = lambda k: (form.get(k) or [""])[0]
    nxt = g("next") or "/"
    if not nxt.startswith("/"):
        nxt = "/"
    pj = st.projects
    msg = ""
    if action == "proj_add":
        owner = g("owner")
        scope = g("scope").strip()
        person, agent = _parse_trekker(g("trekker"))
        col = g("col")
        create_status = "future" if col == "toekomst" else "queued"
        orec = st.records.get(owner)
        if orec is not None and org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: projecten horen bij een rol of Individual Initiative.
            return nxt, "✗ een cirkel kan geen project bevatten — kies een rol of Individual Initiative"
        if owner and scope:
            pid = pj.create(owner, scope[:200], "human", status=create_status,
                            person=person or None, agent=agent or None, private=(g("private") == "1"))
            if col == "wacht":
                pj.block(pid, "—")
            msg = "➕ project toegevoegd"
    elif action == "proj_status":
        to = g("to")
        pj.reopen(g("pid"))   # was het 'done', haal dat er eerst af zodat heractiveren kan
        if to == "actief":
            pj.start(g("pid"))
        elif to == "wacht":
            pj.block(g("pid"), "—")
        elif to == "toekomst":
            pj.to_future(g("pid"))
        msg = "✓ verplaatst"
    elif action == "proj_done":
        pj.complete(g("pid")); msg = "✓ afgerond"
    elif action == "proj_archive":
        pj.archive(g("pid")); msg = "🗄 gearchiveerd (blijft bestaan)"
    elif action == "proj_unarchive":
        pj.unarchive(g("pid")); msg = "↩ hersteld"
    elif action == "proj_delete":
        pj.remove(g("pid")); msg = "🗑 verwijderd"
    elif action == "proj_edit":
        person, agent = _parse_trekker(g("trekker"))
        pj.edit(g("pid"), scope=g("scope"), person=person, agent=agent,
                private=(g("private") == "1"), description=g("description"), label=g("label"))
        msg = "💾 opgeslagen"
    elif action == "proj_comment":
        if pj.add_comment(g("pid"), g("comment")):
            msg = "💬 geplaatst"
    elif action == "proj_rename":
        if pj.edit(g("pid"), scope=g("scope"), allow_done=True):
            msg = "✓ titel opgeslagen"
    elif action == "proj_describe":
        if pj.edit(g("pid"), description=g("description"), allow_done=True):
            msg = "✓ omschrijving opgeslagen"
    elif action == "proj_settrekker":
        person, agent = _parse_trekker(g("trekker"))
        if pj.edit(g("pid"), person=person, agent=agent, allow_done=True):
            msg = "✓ trekker opgeslagen"
    elif action == "proj_setlabel":
        if pj.edit(g("pid"), label=g("label"), allow_done=True):
            msg = "✓ label opgeslagen"
    elif action == "proj_setprivate":
        if pj.edit(g("pid"), private=(g("private") == "1"), allow_done=True):
            msg = "✓ zichtbaarheid opgeslagen"
    elif action == "proj_setdue":
        if pj.set_due(g("pid"), g("due")):
            msg = "📅 datum opgeslagen" if g("due") else "✓ datum verwijderd"
    elif action == "attach_add":
        if pj.attach_add(g("pid"), url=g("url"), title=g("title")):
            msg = "🔗 bijlage toegevoegd"
    elif action == "attach_remove":
        pj.attach_remove(g("pid"), g("aid")); msg = "🗑 bijlage verwijderd"
    elif action == "react_add":
        if pj.add_reaction(g("pid"), g("item"), g("emoji")):
            msg = "✓ reactie geplaatst"
    elif action == "feed_edit":
        if pj.feed_edit(g("pid"), g("item"), g("text")):
            msg = "✓ comment gewijzigd"
    elif action == "feed_remove":
        pj.feed_remove(g("pid"), g("item")); msg = "🗑 comment verwijderd"
    elif action == "ai_reply":
        _load_env()
        msg = ("🤖 AI heeft meegedacht" if _ai_reply(st, g("pid"))
               else "geen AI-antwoord (geen AI-inwoner op de rol of geen LLM-key)")
    elif action == "proj_feed":
        atype, _, aid = g("author").partition(":")
        atype = atype or "human"
        kind = "comment" if atype == "human" else "update"
        entry = pj.add_feed_entry(g("pid"), g("text"), kind=kind, author_type=atype, author_id=aid)
        if entry:
            msg = "💬 update geplaatst" if kind == "update" else "💬 reactie geplaatst"
            _, by_name = _mentionables(st)
            ment = _mentions_in(g("text"), by_name)
            for ty, tid, nm in ment:
                st.notif.add(ty, tid, g("pid"), entry["id"], by="dialoog", snippet=g("text"))
            if ment:
                msg += f" · {len(ment)} genotificeerd"
    elif action == "checklist_add":
        if pj.checklist_add(g("pid"), g("title")):
            msg = "✓ checklist toegevoegd"
    elif action == "checklist_remove":
        pj.checklist_remove(g("pid"), g("clid")); msg = "🗑 checklist verwijderd"
    elif action == "check_add":
        if pj.check_add(g("pid"), g("clid"), g("text")):
            msg = "✓ item toegevoegd"
    elif action == "check_toggle":
        pj.check_toggle(g("pid"), g("clid"), g("item"))
    elif action == "check_remove":
        pj.check_remove(g("pid"), g("clid"), g("item")); msg = "🗑 item verwijderd"
    elif action == "role_assign":
        person, agent = _parse_trekker(g("filler"))
        if person and st.assign.assign(g("role"), "person", person):
            msg = "✓ toegewezen"
        elif agent and st.assign.assign(g("role"), "persona", agent):
            msg = "🤖 AI toegewezen"
    elif action == "role_unassign":
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.unassign(g("role"), "person", person)
        elif agent:
            st.assign.unassign(g("role"), "persona", agent)
        msg = "✓ verwijderd"
    elif action == "role_focus":
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.set_focus(g("role"), "person", person, g("focus"))
        elif agent:
            st.assign.set_focus(g("role"), "persona", agent, g("focus"))
        msg = "✓ focus opgeslagen"
    elif action == "aitask_add":
        try:
            acc_i = int(g("acc"))
        except ValueError:
            acc_i = -1
        pick = g("pick")
        if "::" in pick:
            agent, skill = pick.split("::", 1)
        else:
            agent, skill = g("agent"), g("wat")   # fallback (legacy)
        if agent and acc_i >= 0 and st.ai.add(g("role"), acc_i, agent, skill):
            msg = "🤖 AI gekoppeld aan accountability"
    elif action == "aitask_remove":
        st.ai.remove(g("tid")); msg = "✓ verwijderd"
    elif action == "persona_skill_add":
        if st.personas.add_skill(g("agent"), g("skill")):
            msg = "✓ skill aan rugzak toegevoegd"
    elif action == "rov2_add":
        if _rov_add_item(st, g("circle"), g("naam")):
            msg = "✓ agendapunt toegevoegd"
    elif action == "rov2_add_to_group":
        if _rov_add_item(st, g("circle"), g("naam"), group=g("group")):
            msg = "✓ toegevoegd aan voorstel"
    elif action == "rov2_remove":
        st.agenda.remove(g("iid")); msg = "🗑 uit voorstel verwijderd"
    elif action == "rov2_remove_group":
        gid = st.agenda.group_of(g("iid"))
        for m in st.agenda.members_of_group(gid):
            st.agenda.remove(m["id"])
        msg = "🗑 voorstel verwijderd"
    elif action == "rov2_setkind":
        if g("kind") in ("amend_role", "remove_role"):
            st.agenda.update_fields(g("iid"), kind=g("kind"))
            msg = "voorstel: rol verwijderen" if g("kind") == "remove_role" else "voorstel: rol wijzigen"
    elif action == "rov2_consent":
        gid = st.agenda.group_of(g("iid"))
        members = st.agenda.members_of_group(gid)
        if members and not any(_rov_hard(st, m) for m in members):
            for m in members:
                st.agenda.set_status(m["id"], "consented")
            msg = "✓ consent — voorstel aangenomen"
        else:
            msg = "⛔ consent geblokkeerd — los de blokkade(s) op"
    elif action == "rov2_chat_start":
        item = st.agenda.get(g("iid"))
        if item is not None:
            mode = g("mode")
            if mode == "reset":
                st.agenda.update_fields(g("iid"), chatmode="")
                msg = "↺ ander onderwerp"
            elif mode in ("spanning", "accountability"):
                st.agenda.update_fields(g("iid"), chatmode=mode)
                _load_env()
                opener = _rov_ai_kladblok(st, st.agenda.get(g("iid")), mode=mode)
                if opener:
                    st.agenda.add_kladblok(g("iid"), "ai", opener.strip())
                msg = "🤖 AI-assistent gestart"
    elif action == "rov2_kladblok":
        item = st.agenda.get(g("iid"))
        if item is not None and g("text").strip():
            st.agenda.add_kladblok(g("iid"), "jij", g("text"))
            _load_env()
            item = st.agenda.get(g("iid"))
            mode = item.get("chatmode") or ""
            if mode == "accountability":
                for nm, a in _rov_dupes(st, g("text"), exclude_role=item.get("role_id") or ""):
                    st.agenda.add_kladblok(g("iid"), "note",
                                           f"Lijkt op '{a}' bij {nm}. Beleg het niet dubbel — "
                                           "of formuleer scherper waarin deze rol verschilt.")
            reply = _rov_ai_kladblok(st, st.agenda.get(g("iid")), mode=mode)
            if reply:
                st.agenda.add_kladblok(g("iid"), "ai", reply.strip())
            msg = "💬 meegedacht" if reply else "💬 geplaatst (geen AI-antwoord)"
    elif action == "rov2_end":
        done = _rov_apply(st)
        msg = f"✓ overleg gesloten — {len(done)} doorgevoerd" if done else "overleg gesloten"
    elif action == "wo_open":
        st.werk.open(g("circle")); msg = "✓ werkoverleg gestart"
    elif action == "wo_close":
        st.werk.close(g("circle")); msg = "✓ werkoverleg gesloten"
    elif action == "wo_presence":
        st.werk.set_presence(g("circle"), g("pid"), g("present") == "1")
        msg = "✓ aanwezig" if g("present") == "1" else "✗ afwezig (taken gepauzeerd)"
    elif action == "wo_present_all":
        for p in _members_of_circle(st, g("circle")):
            st.werk.set_presence(g("circle"), p.id, True)
        msg = "✓ allen aanwezig"
    elif action == "wo_ag_add":
        naam, by = _rov_initials(g("naam"))
        if st.werk.agenda_add(g("circle"), naam, by=by):
            msg = "✓ spanning op de agenda"
    elif action == "wo_ag_remove":
        st.werk.agenda_remove(g("circle"), g("iid")); msg = "🗑 verwijderd"
    elif action == "wo_ag_note":
        if g("field") in ("spanning", "role", "need"):
            st.werk.agenda_set_note(g("circle"), g("iid"), **{g("field"): g("value")})
            msg = "✓ genoteerd"
    elif action == "wo_ag_reopen":
        it = st.werk.agenda_get(g("circle"), g("iid"))
        if it is not None:
            it["status"] = "open"; it["outcome"] = None; st.werk._save()
            msg = "↺ heropend"
    elif action == "wo_ag_resolve":
        otype, detail = g("otype"), g("detail")
        it = st.werk.agenda_get(g("circle"), g("iid"))
        if otype == "info":
            # richting (delen/nodig) + @-targeting: gericht aan rol/persoon, anders iedereen
            dr = g("dir") or "delen"
            _, by_name = _mentionables(st)
            ment = _mentions_in(detail, by_name)
            for ty, tid, nm in ment:
                st.notif.add(ty, tid, "", "", by="werkoverleg", snippet=detail)
            tgt = ", ".join(nm for _, _, nm in ment) if ment else "iedereen"
            detail = f"{dr} ({tgt}): {detail.strip()}"
        elif otype == "project" and g("owner") and detail.strip():
            st.projects.create(g("owner"), detail.strip(), "human")
            detail = f"{detail.strip()} → {_name(st.records.get(g('owner')))}"
        elif otype == "action" and g("pid_link") and detail.strip():
            # actie gekoppeld aan een project = checklist-item op dat project
            pid = g("pid_link"); p = st.projects.get(pid)
            if p is not None:
                cl = next((c for c in (p.get("checklists") or []) if c.get("title") == "Acties uit overleg"), None)
                if cl is None:
                    cl = st.projects.checklist_add(pid, "Acties uit overleg")
                if cl:
                    st.projects.check_add(pid, cl["id"], detail.strip())
                detail = f"{detail.strip()} → project"
        elif otype == "roloverleg" and detail.strip():
            slug = re.sub(r"[^a-z0-9]+", "_", detail.lower()).strip("_")[:40] or "punt"
            by = (it or {}).get("by") or "werkoverleg"   # ingebracht door de indiener van de spanning
            st.agenda.add(f"{g('circle')}__{slug}", "add_role",
                          {"name": (it or {}).get("title", "Nieuwe rol"), "new_role_parent": g("circle"),
                           "purpose": "", "add_accountabilities": []},
                          detail.strip(), by=by, title=(it or {}).get("title", detail[:60]))
        st.werk.agenda_resolve(g("circle"), g("iid"), otype, detail)
        msg = f"✓ verwerkt als {otype}"
    elif action == "wo_checkout":
        if g("score"):
            st.werk.set_checkout(g("circle"), g("pid"), g("score")); msg = "✓ score genoteerd"
    elif action == "noochie_send":
        s = st.noochie
        if g("text").strip():
            ph = s.phase
            s.add("jij", g("text"))
            _load_env()
            if ph == "ask_spanning":
                s.set_field("spanning", g("text")); s.set_phase("ask_need")
                s.add("noochie", "Top! En wat heb je nodig om dit op te lossen?")
                msg = "💬"
            elif ph == "ask_need":
                s.set_field("need", g("text")); s.set_phase("free")
                s.add("noochie", (_noochie_suggest(st) or "").strip() or "…")
                msg = "💡 suggestie"
            else:
                rep = _noochie_reply(st, g("text"))
                s.add("noochie", (rep or "Even geen AI-verbinding — denk aan een klein "
                                  "roloverleg-voorstel als vervolgstap.").strip())
                msg = "💬"
    elif action == "noochie_reset":
        st.noochie.reset(); msg = "↺ Noochie opnieuw"
    elif action == "noochie_ctx":
        st.noochie.set_field("ctx", g("ctx")); msg = "✓ context bijgewerkt"
    elif action == "cl_add":
        # Governance-poort: alleen een al bestaande terugkerende actie (geen nieuwe verwachting).
        if g("bestaand") != "1":
            msg = "⛔ alleen bestaande terugkerende acties — nieuwe verwachting? via het roloverleg"
        else:
            doel = g("doel") or "all"
            tt, tid = ("role", doel[5:]) if doel.startswith("role:") else ("all", "")
            it = st.checklists.add(g("node"), g("description"), g("cadence"),
                                   target_type=tt, target_id=tid, by="founder")
            msg = "✓ checklist-item toegevoegd" if it else "⛔ geef een beschrijving"
    elif action == "cl_report":
        if st.checklists.report(g("cid"), g("ok") == "1", value=g("value"), by="founder"):
            msg = "✓ genoteerd" if g("ok") == "1" else "✗ genoteerd (aandacht nodig)"
    elif action == "cl_remove":
        st.checklists.remove(g("cid")); msg = "🗑 checklist-item verwijderd"
    elif action == "m_add_kpi":
        pick = g("pick") or "manual"
        if pick.startswith("source:"):
            src = pick[7:]
            cat = _SOURCE_KPIS.get(src)
            it = st.metrics.add_kpi(g("node"), (cat or {}).get("name", src),
                                    (cat or {}).get("unit", ""), source=src) if cat else None
            msg = "✓ KPI uit data toegevoegd" if it else "⛔ onbekende bron-KPI"
        else:
            # losse KPI; optioneel 'deel in catalogus' → maak eerst een gedeelde definitie aan
            def_id, def_version = "", 0
            if g("share") == "1":
                d = st.defs.add(g("name"), owner=g("node"), provenance="sensed",
                                unit=g("unit"), definition=g("definition"), direction=g("direction"),
                                cadence=g("cadence") or "ad-hoc", meettype=g("meettype") or "snapshot",
                                window=g("window"))
                if d:
                    def_id, def_version = d["id"], st.defs.current_version_no(d["id"])
            it = st.metrics.add_kpi(g("node"), g("name"), g("unit"), definition=g("definition"),
                                    direction=g("direction"), threshold=g("threshold"),
                                    cadence=g("cadence") or "ad-hoc", meettype=g("meettype") or "snapshot",
                                    window=g("window"), def_id=def_id, def_version=def_version)
            msg = ("✓ KPI + catalogus-definitie toegevoegd" if (it and def_id)
                   else "✓ KPI toegevoegd" if it else "⛔ geef een naam")
    elif action == "m_add_from_def":
        did = g("def_id")
        if not did and g("def_name"):
            d = st.defs.by_name(g("def_name"))
            did = d["id"] if d else ""
        kid = _kpi_id_from_def(st, g("node"), did)
        msg = "✓ KPI uit catalogus toegevoegd" if kid else "⛔ kies een bestaande definitie uit de catalogus"
    elif action == "def_add":
        d = st.defs.add(g("name"), owner="librarian", provenance="sensed",
                        unit=g("unit"), definition=g("definition"), direction=g("direction"),
                        source=g("csource"), threshold=g("threshold"),
                        cadence=g("cadence") or "ad-hoc", meettype=g("meettype") or "snapshot",
                        window=g("window"), meetwijze=g("meetwijze") or "handmatig",
                        tijd=g("tijd"), bruikbaar=g("bruikbaar"),
                        standaard=g("standaard"), benchmark=g("benchmark"),
                        bron_url=g("bron_url"), verificatie=g("verificatie"), waarde=g("waarde"))
        msg = "✓ definitie toegevoegd aan de catalogus" if d else "⛔ geef een naam"
    elif action == "def_amend":
        # wijzig een gedeelde catalogus-definitie; migratie bepaalt wat met de historie gebeurt
        did = g("def_id")
        old = st.defs.current(did) if did else None
        if not old:
            msg = "⛔ onbekende definitie"
        else:
            from nooch_village.definitions import suggest_migration
            new = {k: g(k) for k in ("definition", "unit", "direction", "threshold", "cadence",
                                     "meettype", "window", "meetwijze", "tijd", "bruikbaar",
                                     "standaard", "benchmark", "bron_url", "verificatie",
                                     "waarde") if g(k) != ""}
            mig = g("migration") or "auto"
            if mig == "auto":
                mig, _why = suggest_migration(old, new)
                if mig == "break" and _llm_says_comparable(old, new):
                    mig = "backcast"     # LLM: historie blijft vergelijkbaar → één reeks
            ver = st.defs.amend(did, mig, **new)
            if ver:
                fields = {k: ver.get(k) for k in ("name", "unit", "definition", "direction",
                                                  "threshold", "cadence", "meettype", "window",
                                                  "meetwijze", "benchmark", "bron_url", "verificatie",
                                                  "tijd", "bruikbaar", "standaard", "waarde")}
                st.metrics.retune_kpis_to_def(did, ver["version"], fields, mig)
                label = {"clarify": "verduidelijking (reeks intact)",
                         "backcast": "back-cast (historie hergebruikt)",
                         "break": "reeksbreuk (nieuwe versie)"}.get(mig, mig)
                msg = f"✓ definitie v{ver['version']} — {label}"
            else:
                msg = "⛔ wijziging ongeldig"
    elif action == "m_add_link":
        it = st.metrics.add_link(g("node"), g("name"), g("url"))
        msg = "✓ link toegevoegd" if it else "⛔ geef naam en URL"
    elif action == "m_sample":
        msg = "✓ meting genoteerd" if st.metrics.add_sample(g("mid"), g("value")) else "⛔ ongeldige meting"
    elif action == "m_remove":
        st.metrics.remove(g("mid")); msg = "🗑 metric verwijderd"
    elif action == "m_pin":
        st.metrics.pin(g("circle"), g("mid")); msg = "✓ op cirkeldashboard"
    elif action == "m_unpin":
        st.metrics.unpin(g("circle"), g("mid")); msg = "✓ van dashboard gehaald"
    elif action == "tile_add":
        combo = g("combo") or ""
        if combo.startswith("def:"):     # indicator direct uit de catalogus → zet als KPI op de node
            kid = _kpi_id_from_def(st, g("node"), combo[4:])
            combo = f"kpi:{kid}|value|none" if kid else ""
        parts = combo.split("|")
        if len(parts) == 3 and parts[0]:
            ref = g("ref_kind")
            t = st.metrics.add_tile(g("node"), parts[0], parts[1], parts[2], g("form"),
                                    target=g("target"), goal_pid=("" if ref == "benchmark" else g("goal_pid")),
                                    ref_kind=ref)
            msg = "✓ KPI op dashboard" if t else "⛔ kon KPI niet maken"
        else:
            msg = "⛔ kies wat je wilt zien"
    elif action == "tile_remove":
        st.metrics.remove_tile(g("node"), g("tid")); msg = "🗑 tegel verwijderd"
    elif action in ("rov2_set", "rov2_acc_add", "rov2_acc_remove", "rov2_dom_add", "rov2_dom_remove"):
        item = st.agenda.get(g("iid"))
        if item is not None:
            draft = _rov_draft(st, item)
            if action == "rov2_set" and g("field") in ("name", "purpose"):
                draft[g("field")] = g("value")
            elif action in ("rov2_acc_add", "rov2_dom_add") and g("text").strip():
                key = "accs" if action == "rov2_acc_add" else "domains"
                t = g("text").strip()
                if t.lower() not in {x.lower() for x in draft[key]}:   # dedup (ook bij 'herstel')
                    draft[key].append(t)
            elif action in ("rov2_acc_remove", "rov2_dom_remove"):
                key = "accs" if action == "rov2_acc_remove" else "domains"
                text = g("text")
                if text:                                              # diff-weergave: verwijder op waarde
                    draft[key] = [x for x in draft[key] if x != text]
                else:
                    try:
                        draft[key].pop(int(g("idx")))
                    except (ValueError, IndexError):
                        pass
            _rov_save_draft(st, g("iid"), draft)
            msg = "✓ voorstel bijgewerkt"
    return nxt, msg


def make_handler(data_dir: str, csrf_token: str):
    class H(BaseHTTPRequestHandler):
        def _send(self, body: str, code: int = 200):
            # Globale Noochie-chrome op elke volledige pagina (niet op fragmenten/zonder csrf).
            if csrf_token and "</body>" in body:
                body = body.replace("</body>", _noochie_chrome() + "</body>", 1)
            b = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _send_bytes(self, data: bytes, content_type: str, filename: str = ""):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            st = _Stores(data_dir)
            if path in ("/", "/index.html"):
                roots = org.roots(st.records.all())
                if roots:
                    self.send_response(302)
                    self.send_header("Location", f"/node?id={roots[0].id}")
                    self.end_headers()
                    return
                self._send(_page("Leeg", "<p>Nog geen organisatie geladen.</p>"))
                return
            if path == "/node":
                self._send(render_node(st, (qs.get("id") or [""])[0],
                                       (qs.get("tab") or ["overview"])[0], csrf_token=csrf_token,
                                       msg=(qs.get("msg") or [""])[0],
                                       group=(qs.get("group") or [""])[0],
                                       clf=(qs.get("clf") or ["due"])[0],
                                       mw=(qs.get("mw") or ["maand"])[0]))
                return
            # Modal-fragmenten krijgen hun eigen <style> mee, zodat ze altijd verse CSS tonen
            # (de overlay hergebruikt anders de stylesheet van de eerste pagina-load).
            def _frag(out: str, is_frag: bool) -> str:
                return (f"<style>{_EXTRA_CSS}</style>{out}") if is_frag else out

            if path == "/project":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_project(st, (qs.get("pid") or [""])[0], csrf_token=csrf_token,
                                                msg=(qs.get("msg") or [""])[0],
                                                back=(qs.get("back") or ["/"])[0], fragment=fr), fr))
                return
            if path == "/rolefillers":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_rolefillers(st, (qs.get("role") or [""])[0],
                                                    csrf_token=csrf_token, fragment=fr), fr))
                return
            if path == "/aitask":
                try:
                    acc_i = int((qs.get("acc") or ["-1"])[0])
                except ValueError:
                    acc_i = -1
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_aitask(st, (qs.get("role") or [""])[0], acc_i,
                                               csrf_token=csrf_token, fragment=fr), fr))
                return
            if path == "/person":
                self._send(render_person(st, (qs.get("id") or [""])[0]))
                return
            if path == "/_patterns":
                self._send(render_patterns(csrf_token))
                return
            if path == "/catalog":
                self._send(render_catalog(st, csrf_token=csrf_token, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/kpi_new":
                self._send(render_kpi_composer(st, (qs.get("node") or [""])[0],
                                               csrf_token=csrf_token, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/noochie":
                self._send(render_noochie(st, csrf_token, (qs.get("ctx") or [""])[0]))
                return
            if path == "/werkoverleg":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_werkoverleg(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("step") or ["checkin"])[0],
                                                    csrf_token=csrf_token, fragment=fr,
                                                    iid=(qs.get("iid") or [""])[0],
                                                    kpi=(qs.get("kpi") or [""])[0],
                                                    mw=(qs.get("mw") or ["maand"])[0]), fr))
                return
            if path == "/roloverleg2":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_roloverleg2(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("iid") or [""])[0],
                                                    csrf_token=csrf_token, fragment=fr,
                                                    chat=(qs.get("chat") or [""])[0] == "1"), fr))
                return
            if path == "/metric_export":
                res = _metric_csv(st, (qs.get("mid") or [""])[0])
                if res is None:
                    self._send("<p>KPI niet gevonden</p>", 404); return
                fname, body = res
                self._send_bytes(body.encode("utf-8"), "text/csv; charset=utf-8", fname)
                return
            if path == "/file":
                p = st.projects.get((qs.get("pid") or [""])[0])
                aid = (qs.get("aid") or [""])[0]
                att = next((a for a in (p.get("attachments") or [])
                            if a.get("id") == aid and a.get("kind") == "file"), None) if p else None
                full = os.path.join(data_dir, att["stored"]) if att else None
                if not (full and os.path.exists(full)):
                    self._send("<p>Bestand niet gevonden</p>", 404); return
                with open(full, "rb") as fh:
                    data = fh.read()
                mt = mimetypes.guess_type(att.get("name", ""))[0] or "application/octet-stream"
                self._send_bytes(data, mt)
                return
            self._send("<p>404</p>", 404)

        def _redirect(self, nxt: str, msg: str):
            if msg:
                sep = "&" if "?" in nxt else "?"
                nxt = f"{nxt}{sep}msg={urllib.parse.quote(msg)}"
            self.send_response(303); self.send_header("Location", nxt); self.end_headers()

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/action":
                self._send("<p>404</p>", 404); return
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length") or 0)
            # Bestand-upload (multipart): apart afhandelen; bestand wegschrijven + registreren.
            if ctype.startswith("multipart/form-data") and "boundary=" in ctype:
                raw = self.rfile.read(length) if length else b""
                boundary = ctype.split("boundary=", 1)[1].strip().strip('"')
                fields, files = _parse_multipart(raw, boundary)
                if not secrets.compare_digest(fields.get("csrf", ""), csrf_token):
                    self._send("CSRF-token ongeldig", 403); return
                msg = ""
                pid = fields.get("pid", "")
                if fields.get("action") == "attach_file" and files.get("file"):
                    fname, blob = files["file"]
                    if fname and blob:
                        safe = os.path.basename(fname).replace("\\", "_")[:120]
                        rel = os.path.join("attachments", pid, uuid.uuid4().hex[:8] + "_" + safe)
                        full = os.path.join(data_dir, rel)
                        os.makedirs(os.path.dirname(full), exist_ok=True)
                        with open(full, "wb") as fh:
                            fh.write(blob)
                        _Stores(data_dir).projects.attach_file(pid, safe, rel)
                        msg = "📎 bijlage geupload"
                self._redirect(fields.get("next", "/"), msg)
                return
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            form = urllib.parse.parse_qs(raw)
            token = (form.get("csrf") or [""])[0]
            if not secrets.compare_digest(token, csrf_token):
                self._send("CSRF-token ongeldig", 403); return
            action = (form.get("action") or [""])[0]
            nxt, msg = dispatch(data_dir, action, form)
            self._redirect(nxt, msg)

        def log_message(self, *_):
            pass
    return H


def serve(host: str = "127.0.0.1", port: int = 8766, data_dir: str | None = None) -> None:
    if host not in _LOCAL_HOSTS:
        raise SystemExit(f"Cockpit 2 weigert niet-lokale host '{host}'.")
    dd = data_dir or _default_data_dir()
    _load_env()   # LLM-keys beschikbaar maken voor 'AI praat mee'
    _bootstrap(dd)
    csrf_token = secrets.token_urlsafe(32)
    httpd = ThreadingHTTPServer((host, port), make_handler(dd, csrf_token))
    httpd.daemon_threads = True
    print(f"Cockpit 2 (GlassFrog-vorm, PoC) op http://{host}:{port}  —  Ctrl-C om te stoppen")
    print(f"Dataset: {dd}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCockpit 2 gestopt.")
    finally:
        httpd.server_close()


def _match_ladder() -> str:
    """Eén werkende, lokaal beschikbare trede voor de matcher. Default Anthropic (Gemini vereist
    google-generativeai). Override via env LLM_MATCH_LADDER (bijv. 'mistral')."""
    return os.getenv("LLM_MATCH_LADDER", "anthropic")


from nooch_village.views.roloverleg import (
    _rov_kindlabel, _rov_children, _rov_items, _rov_open,
    _rov_groups, _rov_initials, _rov_add_item, _rov_hard,
    _rov_signals, _rov_dupes, _rov_ai_kladblok, _rov_apply,
    _rov_draft, _rov_snapshot, _rov_save_draft,
    _rov_member_block, _rov_editor, _rov_chat,
    render_roloverleg2,
)


def _load_env() -> None:
    """Laad project-.env in os.environ (idempotent, setdefault), zodat de losse cockpit2-CLI
    dezelfde LLM-keys ziet als de volledige village. Zoekt .env in cwd en repo-root."""
    import pathlib
    seen = set()
    for cand in (os.path.join(os.getcwd(), ".env"),
                 os.path.join(pathlib.Path(__file__).resolve().parent.parent, ".env")):
        if cand in seen or not os.path.exists(cand):
            continue
        seen.add(cand)
        for line in open(cand):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def refresh_matches(data_dir: str | None = None, ask=None, progress=None) -> int:
    """Achtergrond-pas: laat de LLM per (accountability, skill) oordelen en cache het, zodat het
    cadeautje semantisch matcht. Zonder key/`ask` is dit een no-op (fail-closed); de render valt
    dan terug op lexicaal + concept. `ask` is injecteerbaar voor tests."""
    dd = data_dir or _default_data_dir()
    _bootstrap(dd)
    st = _Stores(dd)
    if ask is None:
        try:
            from nooch_village import llm
        except Exception:
            return 0

        def ask(acc: str, skill: str):
            prompt = ("Ondersteunt de vaardigheid een verantwoordelijkheid? Antwoord met enkel "
                      f"'ja' of 'nee'.\nVerantwoordelijkheid: {acc}\nVaardigheid: {skill}")
            out = llm.reason(prompt, ladder=_match_ladder())
            if not out:
                return None
            o = out.strip().lower()
            if o.startswith("ja") or o.startswith("yes"):
                return True
            if o.startswith("nee") or o.startswith("no"):
                return False
            return None

    skills = sorted({s for p in st.personas.all() for s in (p.skills or [])})
    accs = sorted({a for r in st.records.all() if not org.is_circle(r)
                   for a in (r.definition.accountabilities or [])})
    pairs = [(a, s) for a in accs for s in skills]
    return ai_match.refresh_semantic(pairs, ask, st.match, skip_cached=True, progress=progress)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="nooch_village.cockpit2")
    ap.add_argument("cmd", nargs="?", default="serve", choices=["serve", "match"],
                    help="serve = cockpit; match = achtergrond semantische matcher vullen")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--data-dir", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "match":
        _load_env()   # zorg dat .env-keys beschikbaar zijn voor de losse CLI
        # Snelle key-check: zonder LLM-key heeft de achtergrond-pas niets te doen.
        try:
            from nooch_village import llm
            has_key = bool(llm.reason("antwoord met 'ok'", ladder=_match_ladder()))
        except Exception:
            has_key = False
        if not has_key:
            print("Geen werkende LLM-key gevonden. De matcher draait al op lexicaal + concept "
                  "(code ~ feature, bug ~ testscript); de semantische laag voegt pas iets toe "
                  "met een Anthropic- of Gemini-key in .env. Niets te doen.")
            return

        def progress(i, total, acc, skill):
            print(f"  [{i}/{total}] {acc[:40]} ↔ {skill[:30]}", flush=True)

        print("Semantische matcher: oordelen ophalen (al-gecachete paren worden overgeslagen)…",
              flush=True)
        n = refresh_matches(a.data_dir, progress=progress)
        print(f"Klaar: {n} nieuwe paren bepaald en gecachet.")
        return
    serve(host=a.host, port=a.port, data_dir=a.data_dir)


if __name__ == "__main__":
    main()
