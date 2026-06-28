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
from nooch_village.governance import Records
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore
from nooch_village.personas import PersonaStore
from nooch_village.projects import ProjectLedger
from nooch_village.ai_tasks import AITaskStore
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.metric_schema import CADANS_LABEL, MEETTYPE_LABEL
from nooch_village.definitions import DefinitionStore, seed_catalog as _seed_catalog
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

# Welke tabs "leven" (echt werken) en welke nog grijs zijn. Status: live | basic | grey.
_TAB_STATUS = {
    "overview": "live", "roles": "live", "members": "live", "notes": "basic",
    "metrics": "basic", "checklists": "basic", "projects": "live",
    "policies": "grey", "history": "grey",
}
_TAB_LABEL = {
    "overview": "Overview", "roles": "Roles", "members": "Members", "policies": "Policies",
    "notes": "Notes", "projects": "Projects", "checklists": "Checklists",
    "metrics": "Metrics", "history": "History",
}
_CIRCLE_TABS = ["overview", "roles", "members", "policies", "notes", "projects",
                "checklists", "metrics", "history"]
_ROLE_TABS = ["overview", "policies", "notes", "projects", "checklists", "metrics", "history"]


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


def _name(rec) -> str:
    return getattr(rec.definition, "name", "") or rec.id


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper() or "?"


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


def _tabbar(node_id: str, tabs: list, cur: str) -> str:
    out = []
    for t in tabs:
        status = _TAB_STATUS.get(t, "grey")
        on = " on" if t == cur else ""
        out.append(f"<a class='c2-tab{on}' href='/node?id={_e(node_id)}&tab={t}'>"
                   f"{_e(_TAB_LABEL[t])}<span class='dot {status}'></span></a>")
    return "<div class='c2-tabs'>" + "".join(out) + "</div>"


def _todo(wat: str) -> str:
    return f"<div class='todo'><b>Nog te bouwen.</b> {_e(wat)}</div>"


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


def _avatar(label: str, is_ai: bool) -> str:
    if is_ai:
        return "<span class='av ai'>AI</span>"
    return f"<span class='av'>{_e(_initials(label))}</span>"


# Genderneutraal 'persoon + toevoegen'-icoon (silhouet + plus), kleurt mee met currentColor.
_ICON_ADD_PERSON = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='9' cy='8' r='3.2'/>"
    "<path d='M3.5 20c0-3.2 2.5-5.6 5.5-5.6s5.5 2.4 5.5 5.6'/>"
    "<path d='M18.5 8.5v5M16 11h5'/></svg>")

# Reactie toevoegen: neutrale lijn-smiley met plus (zelfde stijl als persoon-toevoegen).
_ICON_ADD_EMOJI = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='10' cy='12' r='8'/>"
    "<line x1='7.5' y1='10.5' x2='7.5' y2='10.5'/>"
    "<line x1='12.5' y1='10.5' x2='12.5' y2='10.5'/>"
    "<path d='M7 15a3.5 2.5 0 0 0 6 0'/>"
    "<path d='M20 2.6v4M18 4.6h4'/></svg>")


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


def _person_name(st: _Stores, pid: str) -> str:
    p = st.people.get(pid)
    return p.name if p else (pid or "")


def _age(ts) -> str:
    if not ts:
        return ""
    import time as _t
    d = max(0, int((_t.time() - ts) / 86400))
    if d == 0:
        return "vandaag"
    if d < 31:
        return f"{d} d oud"
    if d < 365:
        return f"{d//30} mnd oud"
    return f"{d//365} jr oud"


_NL_MND = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def _fmt_due(iso: str) -> str:
    """ISO-datum 'YYYY-MM-DD' → '25 jun 2026'."""
    if not iso:
        return ""
    try:
        y, m, d = iso.split("-")
        return f"{int(d)} {_NL_MND[int(m) - 1]} {y}"
    except Exception:
        return iso


def _created_full(ts) -> str:
    """Relatieve leeftijd + absolute datum, bijv. 'vandaag · 27 jun 2026' of '1 week oud · 20 jun 2026'."""
    if not ts:
        return "—"
    import datetime
    d = datetime.datetime.fromtimestamp(ts)
    return f"{_age(ts)} · {d.day} {_NL_MND[d.month - 1]} {d.year}"


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


def _cl_target_label(st: _Stores, item: dict) -> str:
    if item.get("target_type") == "role" and item.get("target_id"):
        r = st.records.get(item["target_id"])
        return _name(r) if r else item["target_id"]
    return "Alle leden"


def _cl_spark(item: dict) -> str:
    h = ChecklistStore.history(item, 6)
    if not h:
        return "<span class='cl-spark muted' title='nog geen historie'>—</span>"
    dots = "".join(f"<i class='{'ok' if b else 'no'}'>{'✓' if b else '✗'}</i>" for b in h)
    return f"<span class='cl-spark' title='laatste {len(h)} keer'>{dots}</span>"


def _cl_row(st: _Stores, item: dict, csrf: str) -> str:
    cid = item["id"]
    status = ChecklistStore.current_status(item)
    curval = ChecklistStore.current_value(item)
    tgt = f"<span class='chip muted'>{_e(_cl_target_label(st, item))}</span>"
    valbadge = "" if curval is None else f"<span class='cl-val'>{curval:g}</span>"
    # rapporteer ✓/✗ (+ optionele numerieke waarde) voor de huidige periode, in één formulier
    if csrf:
        vstr = "" if curval is None else f"{curval:g}"
        rep = (f"<form method='post' action='/action' class='cl-rep'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='cid' value='{_e(cid)}'>"
               f"<input type='hidden' name='action' value='cl_report'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
               f"<input class='cl-num' name='value' inputmode='decimal' value='{vstr}' "
               f"placeholder='#' title='waarde (optioneel)'>"
               f"<button class='cl-check ok{(' on' if status is True else '')}' type='submit' name='ok' value='1' title='check'>✓</button>"
               f"<button class='cl-check no{(' on' if status is False else '')}' type='submit' name='ok' value='0' title='geen check'>✗</button></form>")
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='cid' value='{_e(cid)}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
              f"<button class='dellink' type='submit' name='action' value='cl_remove' title='verwijderen'>✕</button></form>")
    else:
        rep = "" if status is None else (f"<span class='cl-check {'ok' if status else 'no'} on'>"
                                         f"{'✓' if status else '✗'}</span>")
        rm = ""
    danger = f"<span class='row-danger'>{rm}</span>" if rm else ""
    return (f"<div class='cl-row'><div class='cl-main'><span class='cl-desc'>{_e(item['description'])}</span> {tgt}{valbadge}</div>"
            f"<div class='cl-act'>{_cl_spark(item)}<span class='cl-checks'>{rep}</span>{danger}</div></div>")


def _checklists_tab_html(st: _Stores, rec, csrf: str = "", flt: str = "due", nav: str = "") -> str:
    is_c = org.is_circle(rec)
    items = st.checklists.for_node(rec.id)
    base = f"/node?id={_e(rec.id)}&tab=checklists"

    # Aandacht nodig: gemiste checks (✗ deze periode) bubbelen naar boven -> wordt werk.
    missed = [i for i in items if ChecklistStore.current_status(i) is False]
    aandacht = ""
    if missed:
        rows = "".join(_cl_row(st, i, csrf) for i in missed)
        aandacht = (f"<div class='c2-sec cl-attn'><h3>⚠ Aandacht nodig</h3>"
                    f"<p class='muted' style='font-size:.8rem'>Gemiste checks. Bespreek ze in het "
                    f"werkoverleg of maak er een agendapunt van.</p>{rows}</div>")

    shown = [i for i in items if ChecklistStore.is_due(i)] if flt == "due" else items
    # filter-schakelaar
    def fl(key, lbl):
        on = " on" if flt == key else ""
        if nav:   # in het werkoverleg: blijf in de modal
            u = f"{nav}&clf={key}"
            return f"<a class='cl-filter{on} js-modal' href='{u}' data-href='{u}'>{lbl}</a>"
        return f"<a class='cl-filter{on}' href='{base}&clf={key}'>{lbl}</a>"
    bar = f"<div class='cl-bar'><span class='muted'>Toon:</span> {fl('due', 'Nu te doen')} {fl('all', 'Alles')}</div>"

    # groepering per cadans
    groups = ""
    for cad in CADENCES:
        sub = [i for i in shown if i.get("cadence") == cad]
        if not sub:
            continue
        groups += (f"<div class='cl-group'><h4>{_e(CADENCE_LABEL[cad])}</h4>"
                   + "".join(_cl_row(st, i, csrf) for i in sub) + "</div>")
    if not groups:
        groups = ("<p class='muted'>Niets meer te doen deze periode. 🎉</p>" if flt == "due"
                  else "<p class='muted'>Nog geen checklist-items.</p>")

    # toevoegen (governance-poort: alleen een al bestaande terugkerende actie)
    add = ""
    if csrf:
        if is_c:
            roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
            opts = "<option value='all'>Alle cirkelleden</option>" + "".join(
                f"<option value='role:{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
            doel = (f"<label class='att-lbl'>Doel</label><select name='doel'>{opts}</select>")
        else:
            doel = "<input type='hidden' name='doel' value='all'>"
        cadopts = "".join(f"<option value='{c}'>{_e(CADENCE_LABEL[c])}</option>" for c in CADENCES)
        add = (f"<details class='cl-add'><summary class='btn ok sm'>+ Checklist-item</summary>"
               f"<form method='post' action='/action' class='cl-addform'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='node' value='{_e(rec.id)}'>"
               f"<input type='hidden' name='next' value='{base}'>"
               f"<label class='att-lbl'>Beschrijving</label>"
               f"<input name='description' placeholder='Bijv. Facturen verstuurd' autocomplete='off'>"
               f"<label class='att-lbl'>Cadans</label><select name='cadence'>{cadopts}</select>"
               f"{doel}"
               f"<label class='cl-gate'><input type='checkbox' name='bestaand' value='1'> "
               f"Dit is een al <b>bestaande</b> terugkerende actie (geen nieuwe verwachting).</label>"
               f"<button class='btn ok sm' type='submit' name='action' value='cl_add'>Toevoegen</button>"
               f"</form></details>")

    head = (f"<div class='cl-head'><h3>Checklists</h3>{add}</div>"
            f"<p class='muted' style='font-size:.8rem'>Transparantie over terugkerend werk (pre-flight): "
            f"✓ of ✗ per periode. Nieuwe verwachtingen lopen via het roloverleg.</p>")
    return f"<div class='c2-sec'>{head}{bar}</div>{aandacht}{groups}"


_MW = [("vandaag", "Vandaag"), ("7d", "7 dagen"), ("maand", "Maand"),
       ("kwartaal", "Kwartaal"), ("alles", "Alles")]
# Bron-KPI's: meetbaar uit bestaande dorpsdata (AI/agents schrijven hier al naartoe).
_SOURCE_KPIS = {"pulse_visitors": {"name": "Websitebezoekers (7-daags)", "unit": "bezoekers"}}


def _source_samples(dd: str, source: str):
    """Lees samples voor een bron-KPI uit bestaande data. pulse_visitors -> pulse_history.jsonl."""
    if source != "pulse_visitors":
        return []
    repo = os.path.join(os.path.dirname(__file__), "..", "data", "pulse_history.jsonl")
    out = []
    for p in (os.path.join(dd, "pulse_history.jsonl"), repo):
        if not os.path.exists(p):
            continue
        try:
            for line in open(p):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                v = d.get("visitors_7d")
                if v is not None and d.get("ts"):
                    out.append({"at": float(d["ts"]), "value": float(v)})
        except Exception:
            pass
        if out:
            break
    return out


def _metric_points(st: _Stores, item: dict, cutoff):
    samples = _source_samples(st.dd, item["source"]) if item.get("source") else item.get("samples", [])
    return filter_samples(samples, cutoff)


def _spark_svg(points, w=84, h=22) -> str:
    vals = [v for _, v in points]
    if len(vals) < 2:
        return "<span class='muted' style='font-size:.7rem'>—</span>"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    pts = " ".join(f"{(i / (n - 1)) * w:.1f},{h - ((v - lo) / rng) * h:.1f}" for i, v in enumerate(vals))
    return (f"<svg class='spark' viewBox='0 0 {w} {h}' width='{w}' height='{h}' preserveAspectRatio='none'>"
            f"<polyline points='{pts}' fill='none' stroke='var(--green)' stroke-width='1.5'/></svg>")


def _kpi_card(st: _Stores, item: dict, cutoff, csrf: str, *, provider=False, circle="") -> str:
    pts = _metric_points(st, item, cutoff)
    val = f"{pts[-1][1]:g}" if pts else "—"
    unit = f" <span class='kpi-unit'>{_e(item.get('unit', ''))}</span>" if item.get("unit") else ""
    prov = ""
    if provider:
        r = st.records.get(item["node"])
        prov = f"<div class='kpi-prov muted'>levert: {_e(_name(r) if r else item['node'])}</div>"
    src = " <span class='chip muted'>auto</span>" if item.get("source") else ""
    # handmatige meting toevoegen (alleen niet-bron KPI's, met csrf)
    add = ""
    if csrf and not item.get("source"):
        add = (f"<form method='post' action='/action' class='kpi-add'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
               f"<input name='value' inputmode='decimal' placeholder='meting' size='6'>"
               f"<button class='btn ok sm' type='submit' name='action' value='m_sample'>+</button></form>")
    pin = ""
    if csrf and circle:
        pinned = st.metrics.is_pinned(circle, item["id"])
        act = "m_unpin" if pinned else "m_pin"
        lbl = "losmaken" if pinned else "+ dashboard"
        pin = (f"<form method='post' action='/action' style='display:inline'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
               f"<input type='hidden' name='circle' value='{_e(circle)}'>"
               f"<input type='hidden' name='next' value='/node?id={_e(circle)}&tab=metrics'>"
               f"<button class='flink' type='submit' name='action' value='{act}'>{lbl}</button></form>")
    rm = ""
    if csrf and not circle:
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='m_remove'>✕</button></form>")
    return (f"<div class='kpi-card'><div class='kpi-h'><span class='kpi-name'>{_e(item['name'])}{src}</span>{rm}</div>"
            f"<div class='kpi-body'><span class='kpi-val'>{val}{unit}</span>{_spark_svg(pts)}</div>"
            f"{prov}<div class='kpi-foot'>{add}{pin}</div></div>")


def _link_card(item: dict, csrf: str) -> str:
    rm = ""
    if csrf:
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='mid' value='{_e(item['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='m_remove'>✕</button></form>")
    return (f"<div class='kpi-card kpi-link'><div class='kpi-h'>"
            f"<a href='{_e(item['url'])}' target='_blank' rel='noopener'>{_IC_LINK} {_e(item['name'])}</a>{rm}</div></div>")


def _metric_add_forms(st: _Stores, rec, csrf: str) -> str:
    base = f"/node?id={_e(rec.id)}&tab=metrics"
    src_opts = "".join(f"<option value='source:{k}'>{_e(v['name'])} (uit data)</option>"
                       for k, v in _SOURCE_KPIS.items())
    kpi = (f"<form method='post' action='/action' class='m-addform'>"
           f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
           f"<input type='hidden' name='next' value='{base}'>"
           f"<label class='att-lbl'>KPI uit lijst of nieuw</label>"
           f"<select name='pick'><option value='manual'>Nieuwe KPI (handmatig)</option>{src_opts}</select>"
           f"<input name='name' placeholder='Naam (bij handmatig)' autocomplete='off'>"
           f"<input name='unit' placeholder='Eenheid (bijv. €, %, stuks)' autocomplete='off'>"
           f"<button class='btn ok sm' type='submit' name='action' value='m_add_kpi'>KPI toevoegen</button></form>")
    link = (f"<form method='post' action='/action' class='m-addform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='next' value='{base}'>"
            f"<label class='att-lbl'>Link naar extern bestand</label>"
            f"<input name='name' placeholder='Naam' autocomplete='off'>"
            f"<input name='url' placeholder='https://…' autocomplete='off'>"
            f"<button class='btn sm' type='submit' name='action' value='m_add_link'>Link toevoegen</button></form>")
    return (f"<details class='m-add'><summary class='btn ok sm'>+ Metric</summary>"
            f"<div class='m-addgrid'>{kpi}{link}</div></details>")


def _shopify_window(dd: str):
    """Het 'alles'-venster uit shopify_metrics.json (snapshot met paren/orders/omzet/land/product)."""
    repo = os.path.join(os.path.dirname(__file__), "..", "data", "shopify_metrics.json")
    for p in (os.path.join(dd, "shopify_metrics.json"), repo):
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p))
            ws = d.get("windows") or {}
            return ws.get("0") or (list(ws.values())[0] if ws else None)
        except Exception:
            return None
    return None


def _sources_for(st: _Stores, rec):
    """Zelf-beschrijvende bron-catalogus voor de tegel-wizard: elke bron declareert measures + dims.
    Op een cirkel tellen ook de handmatige KPI's van de onderliggende rollen mee."""
    is_c = org.is_circle(rec)
    srcs = [
        {"id": "pulse_visitors", "label": "Websitebezoekers",
         "measures": [("visitors", "Bezoekers (7d)")], "dims": [("time", "over tijd")]},
        {"id": "shopify", "label": "Verkoop",
         "measures": [("pairs_sold", "Paren verkocht"), ("orders", "Orders"),
                      ("revenue", "Omzet"), ("aov", "Gem. orderwaarde")],
         "dims": [("none", "totaal"), ("country", "per land"), ("product", "per product")]},
    ]
    # Werkoverleg-gezondheid (facilitator): leest het archief van de cirkel waar deze node onder valt.
    circle = rec.id if is_c else getattr(rec, "parent", None)
    if circle:
        srcs.append({"id": f"werk:{circle}", "label": "Werkoverleg",
                     "measures": [("tevredenheid", "Tevredenheid"), ("spanningen", "Spanningen verwerkt"),
                                  ("informatie", "Informatie verwerkt"), ("projecten", "Projecten"),
                                  ("acties", "Acties")],
                     "dims": [("gemiddeld", "gemiddeld per overleg"), ("totaal", "totaal"),
                              ("over_tijd", "over tijd")]})
    nodes = [rec.id] + ([r.id for r in org.roles_of(st.records.all(), rec.id)] if is_c else [])
    for k in st.metrics.kpis_for_nodes(nodes):
        if k.get("source"):
            continue                                  # bron-KPI's al gedekt door built-ins
        srcs.append({"id": f"kpi:{k['id']}", "label": k["name"],
                     "measures": [("value", k["name"])], "dims": [("time", "over tijd")]})
    return srcs


_WERK_MEASURE = {"spanningen": "behandeld", "informatie": "info", "projecten": "projecten",
                 "acties": "acties", "tevredenheid": "tevredenheid"}


def _werk_fetch(st: _Stores, circle: str, measure: str, dim: str, cutoff):
    key = _WERK_MEASURE.get(measure, "behandeld")
    pts, vals = [], []
    for m in st.werk.log(circle):
        v = m.get(key)
        if v is None:
            continue
        pts.append({"at": m.get("at", 0), "value": v})
        vals.append(v)
    unit = "/10" if measure == "tevredenheid" else ""
    if dim == "over_tijd":
        return {"kind": "series", "points": filter_samples(pts, cutoff), "unit": unit}
    if dim == "totaal" and measure != "tevredenheid":
        return {"kind": "number", "value": (sum(vals) if vals else None), "unit": unit}
    avg = round(sum(vals) / len(vals), 1) if vals else None   # gemiddeld (en tevredenheid-totaal)
    return {"kind": "number", "value": avg, "unit": unit}


def _default_form(dim: str) -> str:
    return {"time": "trend", "none": "getal"}.get(dim, "verdeling")


def _tile_combos(sources):
    out = []
    for s in sources:
        for mid, ml in s["measures"]:
            for did, dl in s["dims"]:
                out.append((f"{s['id']}|{mid}|{did}", f"{s['label']}: {ml} · {dl}", _default_form(did)))
    return out


def _tile_meta(st: _Stores, rec, tile) -> str:
    for s in _sources_for(st, rec):
        if s["id"] == tile["source"]:
            ml = dict(s["measures"]).get(tile["measure"], tile["measure"])
            dl = dict(s["dims"]).get(tile.get("dim", "none"), tile.get("dim", ""))
            return f"{s['label']}: {ml} · {dl}"
    return tile.get("measure", "metric")


def _fetch(st: _Stores, source: str, measure: str, dim: str, cutoff):
    """Haal de data voor een tegel op. Resultaat: series (punten), breakdown (rijen) of number."""
    if source == "pulse_visitors":
        return {"kind": "series", "points": filter_samples(_source_samples(st.dd, "pulse_visitors"), cutoff),
                "unit": "bezoekers"}
    if source == "shopify":
        w = _shopify_window(st.dd) or {}
        if dim == "country":
            return {"kind": "breakdown", "rows": [(c, n) for c, n in w.get("by_country", [])]}
        if dim == "product":
            return {"kind": "breakdown", "rows": [(p, n) for p, n in w.get("top_products", [])]}
        unit = "EUR" if measure in ("revenue", "aov") else ("paren" if measure == "pairs_sold" else "")
        return {"kind": "number", "value": w.get(measure), "unit": unit}
    if source.startswith("werk:"):
        return _werk_fetch(st, source[5:], measure, dim, cutoff)
    if source.startswith("kpi:"):
        it = st.metrics.get(source[4:])
        if not it:
            return {"kind": "number", "value": None, "unit": ""}
        raw = _source_samples(st.dd, it["source"]) if it.get("source") else it.get("samples", [])
        return {"kind": "series", "points": filter_samples(raw, cutoff), "unit": it.get("unit", "")}
    return {"kind": "number", "value": None, "unit": ""}


def _num(v):
    return f"{v:g}" if isinstance(v, (int, float)) else "—"


def _agg(res):
    if res["kind"] == "series":
        return res["points"][-1][1] if res.get("points") else None
    if res["kind"] == "breakdown":
        return sum(n for _, n in res.get("rows", [])) if res.get("rows") else None
    return res.get("value")


def _render_form(res, form, target=None):
    unit = res.get("unit", "")
    kind = res.get("kind")
    # Vorm/dimensie-mismatch: val terug op een zinnige vorm i.p.v. een lege melding.
    if form in ("verdeling", "tabel") and kind != "breakdown":
        form = "trend" if kind == "series" else "getal"
    if form == "trend" and kind != "series":
        form = "getal"
    if form == "trend":
        pts = res.get("points") or []
        return (f"<div class='tile-trend'><span class='kpi-val sm'>{_num(pts[-1][1] if pts else None)}</span>"
                f"{_spark_svg(pts)}</div>")
    if form in ("verdeling", "tabel"):
        rows = res.get("rows") or []
        if not rows:
            return "<p class='muted'>geen uitsplitsing</p>"
        if form == "tabel":
            body = "".join(f"<tr><td>{_e(str(l))}</td><td class='num'>{_num(n)}</td></tr>" for l, n in rows[:12])
            return f"<table class='mtab'>{body}</table>"
        mx = max((n for _, n in rows), default=1) or 1
        out = ""
        for l, n in rows[:8]:
            out += (f"<div class='bar-row'><span class='bar-l'>{_e(str(l))}</span>"
                    f"<span class='bar-t'><span class='bar-f' style='width:{int(n / mx * 100)}%'></span></span>"
                    f"<span class='bar-v'>{_num(n)}</span></div>")
        return f"<div class='bars'>{out}</div>"
    if form == "doelmeter":
        v = _agg(res) or 0
        t = target or 0
        pct = int(min(100, v / t * 100)) if t else 0
        return (f"<div class='goal'><span class='kpi-val sm'>{_num(v)} <span class='kpi-unit'>/ {_num(t)}</span></span>"
                f"<span class='bar-t'><span class='bar-f' style='width:{pct}%'></span></span></div>")
    # getal — leeg (None) is iets anders dan de waarde 0
    v = _agg(res)
    if v is None:
        return "<div class='kpi-val'><span class='muted' style='font-size:.9rem'>geen data</span></div>"
    u = f" <span class='kpi-unit'>{_e(unit)}</span>" if unit else ""
    return f"<div class='kpi-val'>{v:g}{u}</div>"


# Grondslag-laag (GAAP/IRIS): definitie, eenheid, bron, richting per bron-measure.
_SOURCE_GRONDSLAG = {
    "pulse_visitors|visitors": ("Unieke websitebezoekers, voortschrijdend 7-daags venster.",
                                "bezoekers", "pulse_history (Plausible-puls)", "up"),
    "shopify|pairs_sold": ("Verkochte paren uit betaalde orders.", "paren", "Shopify", "up"),
    "shopify|orders": ("Aantal betaalde orders.", "orders", "Shopify", "up"),
    "shopify|revenue": ("Omzet uit betaalde orders.", "EUR", "Shopify", "up"),
    "shopify|aov": ("Gemiddelde orderwaarde (omzet ÷ orders).", "EUR", "Shopify", "up"),
}
_WERK_GRONDSLAG = {
    "tevredenheid": ("Gemiddelde check-out-score (0-10) per overleg.", "0-10", "up"),
    "spanningen": ("Aantal behandelde spanningen per overleg.", "", ""),
    "informatie": ("Aantal info-uitkomsten per overleg.", "", ""),
    "projecten": ("Aantal als project verwerkte uitkomsten.", "", ""),
    "acties": ("Aantal als actie verwerkte uitkomsten.", "", ""),
}
_RICHTING = {"up": "hoger = beter", "down": "lager = beter", "": "—"}


def _grondslag(st: _Stores, source: str, measure: str) -> dict:
    if source.startswith("kpi:"):
        it = st.metrics.get(source[4:]) or {}
        origin = it.get("origin", "")
        bron = (_ORIGIN_LABEL.get(origin, origin) if origin
                else "Bron-KPI" if it.get("source") else "Handmatig (jij voert in)")
        if it.get("def_id"):
            bron += f" · catalogus v{it.get('def_version', 1)}"
        return {"definitie": it.get("definition", ""), "eenheid": it.get("unit", ""),
                "bron": bron, "richting": it.get("direction", ""), "drempel": it.get("threshold"),
                "cadans": it.get("cadence", ""), "meettype": it.get("meettype", ""),
                "venster": it.get("window", "")}
    if source.startswith("werk:"):
        d, u, r = _WERK_GRONDSLAG.get(measure, ("", "", ""))
        return {"definitie": d, "eenheid": u, "bron": "Werkoverleg-archief", "richting": r,
                "drempel": None, "cadans": "maand", "meettype": "snapshot", "venster": ""}
    d, u, b, r = _SOURCE_GRONDSLAG.get(f"{source}|{measure}", ("", "", "", ""))
    return {"definitie": d, "eenheid": u, "bron": b, "richting": r, "drempel": None,
            "cadans": "", "meettype": "", "venster": ""}


def _grondslag_popover(g: dict) -> str:
    rij = lambda k, v: f"<div class='gr-row'><span class='gr-k'>{k}</span><span>{_e(str(v))}</span></div>" if v else ""
    # meetmoment: cadans (hoe vaak) + meettype (hoe een waarde geldt) + eventueel venster
    cad = CADANS_LABEL.get(g.get("cadans"), "")
    mt = MEETTYPE_LABEL.get(g.get("meettype"), "")
    meet = ", ".join(x for x in (cad, mt) if x)
    if g.get("venster"):
        meet = f"{meet} ({g['venster']})" if meet else g["venster"]
    body = (rij("Definitie", g.get("definitie") or "— (nog niet vastgelegd)")
            + rij("Eenheid", g.get("eenheid")) + rij("Bron", g.get("bron"))
            + rij("Richting", _RICHTING.get(g.get("richting"), "—"))
            + (rij("Drempel", g.get("drempel")) if g.get("drempel") is not None else "")
            + rij("Meetmoment", meet))
    return (f"<details class='tile-info'><summary title='grondslag'>{_IC_INFO}</summary>"
            f"<div class='gr-pop'>{body}</div></details>")


def _definition_datalist(st: _Stores) -> str:
    """Bestaande definities (eigen KPI's + ingebouwde grondslagen) als datalist, zodat je een
    bestaande grondslag hergebruikt i.p.v. een nieuwe te verzinnen (vergelijkbaarheid)."""
    defs = {it.get("definition", "").strip() for it in st.metrics._items.values()
            if it.get("kind") == "kpi" and it.get("definition", "").strip()}
    defs |= {d for (d, *_rest) in _SOURCE_GRONDSLAG.values() if d}
    opts = "".join(f"<option value='{_e(d)}'>" for d in sorted(defs))
    return f"<datalist id='gr-defs'>{opts}</datalist>"


def _render_tile(st: _Stores, rec, tile, cutoff, csrf: str) -> str:
    res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), cutoff)
    body = _render_form(res, tile.get("form", "getal"), tile.get("target"))
    g = _grondslag(st, tile["source"], tile["measure"])
    info = _grondslag_popover(g)
    # Doel-koppeling: de indicator geeft info, het project is het doel (outcome + deadline).
    goal = ""
    gp = st.projects.get(tile.get("goal_pid")) if tile.get("goal_pid") else None
    if gp is not None:
        due = _fmt_due(gp.get("due")) if gp.get("due") else ""
        goal = (f"<div class='tile-goal muted'>naar doel: <b>{_e(str(gp.get('scope') or gp['id'])[:50])}</b>"
                f"{(' · ' + _e(due)) if due else ''}</div>")
    # Drempel-signaal (Kaizen 'aandacht nodig'): waarde de verkeerde kant op t.o.v. de drempel.
    warn = ""
    thr, val = g.get("drempel"), _agg(res)
    if thr is not None and isinstance(val, (int, float)):
        bad = (val < thr) if g.get("richting") == "up" else (val > thr) if g.get("richting") == "down" else False
        if bad:
            warn = f"<span class='tile-warn' title='onder/over de drempel ({thr:g})'>⚠</span>"
    rm = ""
    if csrf:
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
              f"<input type='hidden' name='tid' value='{_e(tile['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(rec.id)}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='tile_remove'>✕</button></form>")
    return (f"<div class='tile'><div class='tile-h'><span class='tile-t'>{_e(_tile_meta(st, rec, tile))}{warn}</span>"
            f"<span class='tile-h-r'>{info}{rm}</span></div>"
            f"<div class='tile-b'>{body}</div>{goal}</div>")


def _tile_wizard(st: _Stores, rec, csrf: str) -> str:
    combos = _tile_combos(_sources_for(st, rec))
    opts = "".join(f"<option value='{_e(v)}' data-form='{df}'>{_e(lbl)}</option>" for v, lbl, df in combos)
    forms = [("getal", "Getal"), ("trend", "Trend (lijn)"), ("verdeling", "Verdeling (staaf)"),
             ("tabel", "Tabel"), ("doelmeter", "Doelmeter")]
    fopts = "".join(f"<option value='{k}'>{_e(l)}</option>" for k, l in forms)
    base = f"/node?id={_e(rec.id)}&tab=metrics"
    return (f"<details class='m-add'><summary class='btn ok sm'>+ KPI op dashboard</summary>"
            f"<form method='post' action='/action' class='m-addform'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='next' value='{base}'>"
            f"<label class='att-lbl'>Wat wil je zien</label>"
            f"<select name='combo' onchange=\"var o=this.options[this.selectedIndex];"
            f"var f=this.form.querySelector('[name=form]');if(o.dataset.form)f.value=o.dataset.form;\">{opts}</select>"
            f"<label class='att-lbl'>Vorm</label><select name='form'>{fopts}</select>"
            f"<label class='att-lbl'>Doelmeter: koppel aan een doel (project)</label>"
            f"<select name='goal_pid'>{_goal_options(st, rec)}</select>"
            f"<input name='target' inputmode='decimal' placeholder='streefwaarde, bijv. 1000' autocomplete='off'>"
            f"<p class='muted' style='font-size:.72rem'>De indicator geeft informatie; het doel is "
            f"het project (outcome + deadline). Alleen nodig bij vorm Doelmeter.</p>"
            f"<button class='btn ok sm' type='submit' name='action' value='tile_add'>Op dashboard</button></form></details>")


def _goal_options(st: _Stores, rec) -> str:
    """Projecten onder deze node als koppelbare doelen (= outcome + deadline)."""
    is_c = org.is_circle(rec)
    nodes = {rec.id} | ({r.id for r in org.roles_of(st.records.all(), rec.id)} if is_c else set())
    out = "<option value=''>— geen doel —</option>"
    for p in st.projects.all():
        if p.get("owner") in nodes and not p.get("archived"):
            out += f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:50])}</option>"
    return out


def _metric_csv(st: _Stores, mid: str) -> tuple[str, str] | None:
    """(bestandsnaam, csv-tekst) met alle metingen van een KPI; None als de KPI niet bestaat."""
    it = st.metrics.get(mid)
    if it is None or it.get("kind") != "kpi":
        return None
    raw = _source_samples(st.dd, it["source"]) if it.get("source") else it.get("samples", [])
    pts = filter_samples(raw, None)
    import csv as _csv
    import datetime as _dt
    import io as _io
    from nooch_village.metric_schema import SCHEMA_FIELDS
    buf = _io.StringIO()
    w = _csv.writer(buf)
    # 1. het volledige indicator-schema (grondslag + meetmoment), ook lege velden
    w.writerow(["indicator-schema", ""])
    for f in SCHEMA_FIELDS:
        v = it.get(f, "")
        w.writerow([f, "" if v is None else v])
    w.writerow([])
    # 2. de metingen
    w.writerow(["datum", "waarde", "eenheid"])
    for at, v in pts:
        dt = _dt.datetime.fromtimestamp(at).strftime("%Y-%m-%d %H:%M")
        w.writerow([dt, v, it.get("unit", "")])
    safe = "".join(c if c.isalnum() else "_" for c in (it.get("name") or "kpi"))[:40]
    return f"{safe}.csv", buf.getvalue()


def _kpi_data_row(st: _Stores, item: dict, csrf: str) -> str:
    raw = _source_samples(st.dd, item["source"]) if item.get("source") else item.get("samples", [])
    pts = filter_samples(raw, None)
    val = _num(pts[-1][1]) if pts else "—"
    unit = f" {_e(item.get('unit', ''))}" if item.get("unit") else ""
    # systeem-gemeten KPI (live-bron of catalogus-origin uit een systeembron): geen handmatige invoer
    is_sys = bool(item.get("source") or item.get("auto"))
    src = " <span class='chip muted'>systeem</span>" if is_sys else ""
    add = ""
    if csrf and not is_sys:
        add = (f"<form method='post' action='/action' class='kpi-add'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='mid' value='{_e(item['id'])}'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
               f"<input name='value' inputmode='decimal' placeholder='meting' size='6'>"
               f"<button class='btn ok sm' type='submit' name='action' value='m_sample'>+</button></form>")
    # grondslag (definitie + meetmoment) op de rij zelf, naast de naam (klik op de ⓘ)
    info = _grondslag_popover(_grondslag(st, f"kpi:{item['id']}", "value"))
    exp = (f"<a class='kpi-exp' href='/metric_export?mid={_e(item['id'])}' "
           f"title='Metingen exporteren (CSV)'>{_IC_DL}</a>")
    rm = ""
    if csrf:
        # destructief: vraagt bevestiging (en wijst op export) — een KPI met historie is niet terug te halen
        conf = (f"&#39;{_e(item['name'])}&#39; en alle metingen verwijderen? "
                "Dit kan niet ongedaan worden. Exporteer eventueel eerst de data.")
        rm = (f"<form method='post' action='/action' style='display:inline' data-confirm='{conf}'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='mid' value='{_e(item['id'])}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=metrics'>"
              f"<button class='dellink' type='submit' name='action' value='m_remove'>✕</button></form>")
    return (f"<div class='kpidata-row'><span class='kpidata-n'>{_e(item['name'])}{src} {info}</span>"
            f"<span class='kpidata-v'>{val}{unit}</span>{_spark_svg(pts)}{add}{exp}{rm}</div>")


# bronnen die het systeem/een API meet — hiervoor mag je NOOIT handmatig invoeren (integriteit).
# De waarde komt uit de bron; tot een live-koppeling bestaat toont de KPI 'nog niet gekoppeld'.
_SYSTEM_SOURCES = {"gsc", "plausible", "shopify", "trends", "keywords_everywhere", "ngram",
                   "openalex", "semantic_scholar", "site_health", "competitor_news",
                   "linkbuilding", "budget", "werkoverleg"}
# bron-herkomst → leesbaar label (voor de grondslag-popover van een catalogus-KPI)
_ORIGIN_LABEL = {
    "gsc": "Google Search Console", "plausible": "Plausible", "shopify": "Shopify",
    "trends": "Google Trends", "keywords_everywhere": "Keywords Everywhere", "ngram": "Google Ngram",
    "openalex": "OpenAlex", "semantic_scholar": "Semantic Scholar", "site_health": "Site health",
    "competitor_news": "Nieuws-monitor", "linkbuilding": "Linkbuilding", "budget": "Budget",
    "werkoverleg": "Werkoverleg-archief",
}
# lichte bron→functie-affiniteit bovenop tekstoverlap (zodat de juiste rol de juiste bron ziet)
_SOURCE_AFFINITY = {
    "gsc": "marketing seo zoek vindbaarheid content website",
    "trends": "marketing seo zoek trend content",
    "keywords_everywhere": "marketing seo zoek content",
    "plausible": "marketing website verkeer bezoekers analytics",
    "shopify": "verkoop sales omzet order webshop commerce conversie",
    "ngram": "content cultuur taal merk",
    "openalex": "onderzoek kennis wetenschap bewijs",
    "semantic_scholar": "onderzoek kennis wetenschap bewijs",
    "site_health": "website techniek beschikbaarheid developer ontwikkelaar",
    "competitor_news": "concurrent markt merk nieuws",
    "linkbuilding": "marketing seo link backlink",
    "budget": "budget kosten inkoop financ",
    "werkoverleg": "facilitator overleg proces governance gezondheid",
}
_DEF_STOP = {"beheert", "bewaakt", "zorgt", "rondom", "binnen", "deze", "wordt", "worden"}


def _def_tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-zà-ÿ]+", (text or "").lower())
            if len(w) > 3 and w not in _DEF_STOP}


def _role_text(rec) -> str:
    d = rec.definition
    parts = [getattr(d, "name", "") or "", d.purpose or ""]
    parts += list(d.accountabilities or [])
    parts += list(d.domains or [])
    return " ".join(parts)


def _role_relevant_defs(st: _Stores, rec, limit: int = 6) -> list[tuple[str, dict]]:
    """Catalogus-definities gerangschikt op relevantie voor deze rol (knows-approximately).
    Score = tekstoverlap (rol-purpose/accountabilities/domeinen × definitie) + bron-affiniteit."""
    rt = _def_tokens(_role_text(rec))
    if not rt:
        return []
    scored = []
    for d in st.defs.all():
        cur = st.defs.current(d["id"]) or {}
        dt = _def_tokens(cur.get("name", "") + " " + cur.get("definition", ""))
        aff = _def_tokens(_SOURCE_AFFINITY.get(cur.get("source", ""), ""))
        score = len(rt & dt) * 2 + len(rt & aff)
        if score > 0:
            scored.append((score, cur.get("name", ""), d["id"], cur))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [(did, cur) for _s, _n, did, cur in scored[:limit]]


def _catalog_picker(st: _Stores, rec, csrf: str, base: str) -> str:
    """Picker voor een nieuwe KPI: catalogus is de norm (knows-exactly zoek + knows-approximately
    aanbevelingen voor de rol), met een losse KPI als toegestane uitzondering."""
    hidden = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='node' value='{_e(rec.id)}'>"
              f"<input type='hidden' name='next' value='{base}'>")
    allcur = [(d["id"], st.defs.current(d["id"]) or {}) for d in st.defs.all()]
    allcur = [(i, c) for i, c in allcur if c.get("name")]

    # knows exactly: zoekveld met typeahead over alle catalogus-namen
    dl = "".join(f"<option value=\"{_e(c['name'])}\">" for _i, c in sorted(allcur, key=lambda x: x[1]["name"]))
    search = (f"<form method='post' action='/action' class='m-addform'>{hidden}"
              f"<label class='att-lbl'>Zoek een indicator (uit de catalogus)</label>"
              f"<input name='def_name' list='cat-defs' placeholder='typ een naam, bijv. Omzet' autocomplete='off'>"
              f"<datalist id='cat-defs'>{dl}</datalist>"
              f"<button class='btn ok sm' type='submit' name='action' value='m_add_from_def'>Toevoegen</button></form>")

    # knows approximately: aanbevolen voor deze rol
    chips = ""
    for did, cur in _role_relevant_defs(st, rec, 6):
        chips += (f"<form method='post' action='/action' class='def-rec'>{hidden}"
                  f"<input type='hidden' name='def_id' value='{_e(did)}'>"
                  f"<button class='btn ghost sm' type='submit' name='action' value='m_add_from_def' "
                  f"title='{_e(cur.get('definition', ''))}'>+ {_e(cur['name'])}</button></form>")
    recblock = f"<div class='def-recs'><span class='muted'>Voor jouw rol:</span>{chips}</div>" if chips else ""

    # vangnet: alle definities gegroepeerd per bron (voor wie scrollend zoekt)
    bysrc: dict[str, list] = {}
    for did, c in sorted(allcur, key=lambda x: x[1]["name"]):
        bysrc.setdefault(c.get("source", ""), []).append((did, c))
    groups = ""
    for s in sorted(bysrc):
        items = "".join(
            f"<form method='post' action='/action' class='def-rec'>{hidden}"
            f"<input type='hidden' name='def_id' value='{_e(did)}'>"
            f"<button class='btn ghost sm' type='submit' name='action' value='m_add_from_def' "
            f"title='{_e(c.get('definition', ''))}'>+ {_e(c['name'])}</button></form>"
            for did, c in bysrc[s])
        groups += f"<div class='def-grp'><span class='muted'>{_e(_ORIGIN_LABEL.get(s, s or 'overig'))}</span>{items}</div>"
    allblock = f"<details class='def-all'><summary class='muted'>Alle definities ({len(allcur)})</summary>{groups}</details>"

    # uitzondering: losse (niet-gedeelde) KPI of een nieuwe gedeelde definitie
    src_opts = "".join(f"<option value='source:{k}'>{_e(v['name'])} (uit data)</option>"
                       for k, v in _SOURCE_KPIS.items())
    loose = (f"<details class='m-add'><summary class='att-lbl' style='cursor:pointer'>Losse KPI of nieuwe definitie</summary>"
             f"<form method='post' action='/action' class='m-addform'>{hidden}"
             f"<select name='pick'><option value='manual'>Handmatige KPI</option>{src_opts}</select>"
             f"<input name='name' placeholder='Naam' autocomplete='off'>"
             f"<input name='unit' placeholder='Eenheid (€, %, stuks)' autocomplete='off'>"
             f"<input name='definition' list='gr-defs' placeholder='Definitie: wat telt mee? (grondslag)' autocomplete='off'>"
             f"{_definition_datalist(st)}"
             f"<select name='direction'><option value=''>Richting (geen)</option>"
             f"<option value='up'>hoger = beter</option><option value='down'>lager = beter</option></select>"
             f"<input name='threshold' inputmode='decimal' placeholder='Drempel (optioneel)' autocomplete='off'>"
             f"<select name='cadence' title='meetmoment: hoe vaak'>"
             + "".join(f"<option value='{k}'{' selected' if k == 'ad-hoc' else ''}>meet: {_e(v)}</option>"
                       for k, v in CADANS_LABEL.items())
             + "</select>"
             f"<select name='meettype' title='meetmoment: hoe een waarde geldt'>"
             + "".join(f"<option value='{k}'>{_e(v)}</option>" for k, v in MEETTYPE_LABEL.items())
             + "</select>"
             f"<label class='def-share'><input type='checkbox' name='share' value='1'> Deel in de catalogus (Librarian)</label>"
             f"<button class='btn ok sm' type='submit' name='action' value='m_add_kpi'>KPI toevoegen</button></form></details>")

    return (f"<details class='m-add'><summary class='btn sm'>+ KPI toevoegen</summary>"
            f"<div class='def-pick'>{search}{recblock}{allblock}{loose}</div></details>")


def _metrics_tab_html(st: _Stores, rec, csrf: str = "", win: str = "maand", nav: str = "") -> str:
    cutoff = window_cutoff(win)
    base = f"/node?id={_e(rec.id)}&tab=metrics"

    def pl(k, lbl):
        on = " on" if win == k else ""
        if nav:   # in het werkoverleg: blijf in de modal
            u = f"{nav}&mw={k}"
            return f"<a class='cl-filter{on} js-modal' href='{u}' data-href='{u}'>{_e(lbl)}</a>"
        return f"<a class='cl-filter{on}' href='{base}&mw={k}'>{_e(lbl)}</a>"
    wbar = ("<div class='cl-bar'><span class='muted'>Periode:</span> "
            + "".join(pl(k, lbl) for k, lbl in _MW) + "</div>")
    head = f"<div class='cl-head'><h3>Metrics</h3>{_tile_wizard(st, rec, csrf) if csrf else ''}</div>{wbar}"

    # 1. Dashboard van tegels (bron + measure + dimensie + vorm), volgt de periode-keuze
    tiles = st.metrics.tiles_of(rec.id)
    dash = ("".join(_render_tile(st, rec, t, cutoff, csrf) for t in tiles) if tiles
            else "<p class='muted'>Nog geen KPI's op het dashboard. Kies er een met “+ KPI op dashboard”.</p>")
    out = f"<div class='c2-sec'>{head}</div><div class='c2-sec'><div class='tile-grid'>{dash}</div></div>"

    # 2. Eigen KPI's (data invoeren) — handmatige KPI's worden vanzelf bron in de wizard
    kpis = [i for i in st.metrics.for_node(rec.id) if i.get("kind") == "kpi"]
    rows = "".join(_kpi_data_row(st, i, csrf) for i in kpis) if kpis else "<p class='muted'>Nog geen eigen KPI's.</p>"
    define = _catalog_picker(st, rec, csrf, base) if csrf else ""
    out += f"<div class='c2-sec'><div class='cl-head'><h3>Eigen KPI's</h3>{define}</div>{rows}</div>"

    # 3. Links naar externe bestanden
    links = st.metrics.links_for(rec.id)
    lc = "".join(_link_card(i, csrf) for i in links)
    addlink = ""
    if csrf:
        addlink = (f"<details class='m-add'><summary class='btn sm'>+ Link</summary>"
                   f"<form method='post' action='/action' class='m-addform'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf)}'><input type='hidden' name='node' value='{_e(rec.id)}'>"
                   f"<input type='hidden' name='next' value='{base}'>"
                   f"<input name='name' placeholder='Naam' autocomplete='off'>"
                   f"<input name='url' placeholder='https://…' autocomplete='off'>"
                   f"<button class='btn ok sm' type='submit' name='action' value='m_add_link'>Link toevoegen</button></form></details>")
    out += (f"<div class='c2-sec'><div class='cl-head'><h3>Links</h3>{addlink}</div>"
            f"<div class='kpi-grid'>{lc or '<p class=muted>Geen links.</p>'}</div></div>")
    return out


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
             "<div class='bar'>cockpit 2 · GlassFrog-vorm (PoC) · "
             "<a href='/'>home</a></div>"
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
             "<div class='bar'>cockpit 2 · GlassFrog-vorm (PoC) · <a href='/'>home</a></div>"
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


def _rov_kindlabel(kind: str) -> str:
    return {"add_role": "nieuwe rol", "remove_role": "rol verwijderen"}.get(kind, "rol wijzigen")


def _rov_children(st: _Stores, circle_id: str):
    """Directe kinderen van een cirkel: eigen rollen + subcirkels. Een supercirkel mag van een
    subcirkel de naam/purpose/accountabilities aanpassen, maar niet de rollen bínnen die subcirkel."""
    return [r for r in st.records.all()
            if getattr(r, "parent", None) == circle_id and not getattr(r, "archived", False)]


def _rov_items(st: _Stores, circle_id: str):
    """Alle agendapunten van DEZE cirkel (open + behandeld), voor de lijst en de groene knop."""
    cids = {r.id for r in _rov_children(st, circle_id)}
    return [it for it in st.agenda.all()
            if it.get("status") in ("open", "objected", "consented")
            and (it.get("role_id") in cids or it.get("change", {}).get("new_role_parent") == circle_id)]


def _rov_open(st: _Stores, circle_id: str):
    """Nog onbehandelde agendapunten (voor selectie en auto-door-naar-volgend)."""
    return [it for it in _rov_items(st, circle_id) if it.get("status") != "consented"]


def _rov_groups(st: _Stores, circle_id: str):
    """Agendapunten gegroepeerd per voorstel (GlassFrog: één voorstel kan meerdere rol-wijzigingen
    bevatten). Geeft [(group_id, [members])], in agenda-volgorde, leden op aanmaaktijd."""
    order, groups = [], {}
    for it in _rov_items(st, circle_id):
        gid = it.get("group") or it["id"]
        if gid not in groups:
            groups[gid] = []
            order.append(gid)
        groups[gid].append(it)
    return [(gid, sorted(groups[gid], key=lambda i: i.get("created_at", 0))) for gid in order]


def _rov_initials(text: str):
    """Splits een trailing '-SW' / '-JvdP' als initialen af. Geeft (rest, initialen)."""
    m = re.search(r"\s*-\s*([A-Za-z][A-Za-z.]{0,6})\s*$", text or "")
    if m:
        return text[:m.start()].strip(), m.group(1)
    return (text or "").strip(), ""


def _rov_add_item(st: _Stores, circle: str, naam_raw: str, group: str | None = None) -> bool:
    """Zet een rol-wijziging op de agenda: bestaande rol (naam matcht een kind) -> amend, anders
    nieuwe rol. Met `group` hangt de wijziging onder een bestaand voorstel (GlassFrog: meerdere
    wijzigingen per voorstel). Geeft True als er iets is toegevoegd."""
    naam, by = _rov_initials(naam_raw)        # '-SW' achteraan = initialen
    if not naam:
        return False
    match = next((r for r in _rov_children(st, circle) if _name(r).lower() == naam.lower()), None)
    if match is not None:
        st.agenda.add(match.id, "amend_role", {}, "", by=by or "founder", title=_name(match), group=group)
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", naam.lower()).strip("_") or "rol"
        st.agenda.add(f"{circle}__{slug}", "add_role",
                      {"name": naam, "new_role_parent": circle, "purpose": "", "add_accountabilities": []},
                      "", by=by or "founder", title=naam, group=group)
    return True


def _rov_hard(st: _Stores, item: dict):
    """Mens-regel voor consent: een rol heeft een naam én minstens één accountability nodig
    (purpose is optioneel). Geeft een lijst blokkades terug (leeg = consent kan)."""
    if item.get("kind") == "remove_role":
        return []   # verwijderen mag (ook met verweesd werk; dat is advies, geen blok)
    d = _rov_draft(st, item)
    out = []
    if not (d.get("name") or "").strip():
        out.append("Geef de rol een naam.")
    if not [a for a in d.get("accs", []) if a.strip()]:
        out.append("Een rol heeft minstens één accountability nodig.")
    return out


def _rov_signals(st: _Stores, item: dict):
    """Secretaris-signalen tijdens het overleg (advies, niet-blokkerend): domein-botsing (G1),
    accountability-duplicaat bij een ándere rol (G2), verweesd werk (G3), mechanische purpose (G0),
    plus de lichte checks (-en-vorm, duplicaat binnen de rol, rijpheid)."""
    from nooch_village.roloverleg import _proposal_from_item, secretary_check
    from nooch_village.governance import Gate
    g, c = Gate(), _proposal_from_item(item).change
    out = []
    for label, fn in (("Domein-botsing", g._g1), ("Dubbele accountability", g._g2),
                      ("Verweesd werk", g._g3)):
        ok, reason = fn(c, st.records)
        if not ok:
            out.append({"level": "let op", "msg": f"{label}: {reason}"})
    if (c.purpose or "").strip().lower().startswith("beheert en bewaakt "):
        out.append({"level": "let op",
                    "msg": "Purpose lijkt een woordcluster ('Beheert en bewaakt …'); "
                           "beschrijf een echte functie."})
    out += [i for i in secretary_check(item, st.records) if i["level"] == "let op"]
    return out


def _rov_dupes(st: _Stores, text: str, exclude_role: str = ""):
    """Bestaat een vergelijkbare accountability al bij een ándere rol? (woordoverlap/substring)."""
    words = {w for w in re.findall(r"[a-zA-Z]{4,}", (text or "").lower())}
    low = (text or "").strip().lower()
    hits = []
    if not low:
        return hits
    for r in st.records.all():
        if getattr(r, "archived", False) or r.id == exclude_role:
            continue
        for a in r.definition.accountabilities:
            al = a.lower()
            if (len(words & {w for w in re.findall(r"[a-zA-Z]{4,}", al)}) >= 2
                    or low in al or al in low):
                hits.append((_name(r), a))
    return hits[:3]


def _rov_ai_kladblok(st: _Stores, item: dict, mode: str = "", ask=None):
    """AI-assistent bij een voorstel. mode: 'spanning' (stelt vragen) of 'accountability'
    (formuleert sneller). Injecteerbaar via `ask`."""
    d = _rov_draft(st, item)
    recent = "\n".join(f"- {m.get('who')}: {m.get('text','')}" for m in (item.get("kladblok") or [])[-6:])
    if mode == "accountability":
        taak = ("Help een accountability te formuleren voor deze rol. Antwoord beknopt en geef een "
                "concrete voorbeeldformulering in de -en-vorm (bijv. 'Bewaken van …').")
    elif mode == "spanning":
        taak = ("Help de spanning achter dit voorstel te verhelderen. Stel 1-2 korte, scherpe vragen "
                "(geen oplossing nog).")
    else:
        taak = "Denk kort mee (max 4 zinnen); je wijzigt de rol niet."
    prompt = (f"Je bent een Holacracy-facilitator. {taak}\n"
              f"Rol: {d.get('name')}\nPurpose: {d.get('purpose') or '(geen)'}\n"
              f"Accountabilities: {', '.join(d.get('accs', [])) or '(geen)'}\n"
              f"Gesprek tot nu:\n{recent or '(leeg)'}")
    if ask is not None:
        return ask(prompt)
    try:
        from nooch_village import llm
        return llm.reason(prompt, ladder=_match_ladder())
    except Exception:
        return None


def _rov_apply(st: _Stores):
    """Voer aangenomen (consented) voorstellen door op de records (mens-regel; niet de strikte
    autonome Gate). Gebruikt Secretary._adopt voor de schrijfactie."""
    from nooch_village.event_bus import EventBus
    from nooch_village.governance import Secretary
    from nooch_village.roloverleg import _proposal_from_item
    sec = Secretary(st.records, EventBus(name="roloverleg2"))
    done = []
    for item in [i for i in st.agenda.all() if i["status"] == "consented"]:
        if _rov_hard(st, item):
            continue
        naam = (_rov_draft(st, item).get("name") or "").strip()
        sec._adopt(_proposal_from_item(item))
        # _adopt zet bij een nieuwe rol geen weergavenaam — die vullen we hier aan.
        if item.get("kind") == "add_role" and naam:
            rec = st.records.get(item.get("role_id"))
            if rec is not None:
                rec.definition.name = naam
                rec.version += 1
                st.records.put(rec)
        st.agenda.remove(item["id"])
        done.append(item.get("title"))
    return done


def _rov_draft(st: _Stores, item: dict) -> dict:
    """De bewerkbare rol-definitie van een agendapunt (naam/purpose/domeinen/accountabilities).
    Init uit het bestaande record (amend) of uit de change (nieuwe rol)."""
    d = item.get("draft")
    if d:
        return {"name": d.get("name", ""), "purpose": d.get("purpose", ""),
                "accs": list(d.get("accs", [])), "domains": list(d.get("domains", []))}
    if item.get("kind") == "add_role":
        ch = item.get("change", {})
        return {"name": item.get("title", ""), "purpose": ch.get("purpose", ""),
                "accs": list(ch.get("add_accountabilities", [])), "domains": list(ch.get("add_domains", []))}
    rec = st.records.get(item.get("role_id"))
    if rec is not None:
        de = rec.definition
        return {"name": _name(rec), "purpose": de.purpose or "",
                "accs": list(de.accountabilities), "domains": list(de.domains)}
    return {"name": item.get("title", ""), "purpose": "", "accs": [], "domains": []}


def _rov_snapshot(st: _Stores, item: dict):
    if item.get("kind") == "add_role":
        return None
    rec = st.records.get(item.get("role_id"))
    if rec is None:
        return None
    de = rec.definition
    return {"name": _name(rec), "purpose": de.purpose,
            "accountabilities": list(de.accountabilities), "domains": list(de.domains)}


def _rov_save_draft(st: _Stores, iid: str, draft: dict) -> None:
    """Sla de draft op én herbereken de change (diff t.o.v. de huidige rol) via roloverleg-logica."""
    item = st.agenda.get(iid)
    if item is None:
        return
    from nooch_village.roloverleg import build_change_from_fields
    change, _rid, title = build_change_from_fields(
        item, _rov_snapshot(st, item), naam=draft["name"], purpose=draft["purpose"],
        accs=draft["accs"], domeinen=draft["domains"])
    st.agenda.update_fields(iid, draft=draft, change=change, title=title or item.get("title"))


def _rov_member_block(st: _Stores, item: dict, csrf: str, back: str, circle_id: str = "") -> tuple[str, list]:
    """Eén rol-wijziging binnen een voorstel (GlassFrog: een voorstel kan er meerdere bevatten).
    Velden: naam, purpose, domeinen, accountabilities. Diff-weergave: verwijderd = doorgestreept
    (pas weg na consent) met herstel, toegevoegd = als 'nieuw' gemarkeerd. Geeft (html, harde-regels)."""
    draft = _rov_draft(st, item)
    iid = item["id"]
    snap = _rov_snapshot(st, item)
    is_amend = snap is not None and item.get("kind") != "add_role"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='iid' value='{_e(iid)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")
    keep = f"data-reopen='{_e(back)}'"
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"

    def _iss_html(lst):
        return "".join(f"<div class='sec-issue {('blok' if i['level'] == 'blok' else 'let')}'>📋 {_e(i['msg'])}</div>"
                       for i in lst)

    rm_member = (f"<form method='post' action='/action' style='display:inline' {keep}>{hid()}"
                 f"<button class='rovm-close' type='submit' name='action' value='rov2_remove' "
                 f"title='Verwijder uit voorstel'>✕</button></form>")

    # --- verwijder-rol blok ---
    if item.get("kind") == "remove_role":
        nm = _name(st.records.get(item.get("role_id"))) or item.get("title")
        adv = _rov_signals(st, item)
        sec = (f"<div class='sec-block'><div class='sec-kop'>📋 Secretaris (advies)</div>{_iss_html(adv)}</div>"
               if adv else "")
        revert = (f"<form method='post' action='/action' {keep}>{hid()}"
                  f"<input type='hidden' name='kind' value='amend_role'>"
                  f"<button class='flink' type='submit' name='action' value='rov2_setkind'>← terug naar wijzigen</button></form>")
        note = ("<p class='muted' style='font-size:.78rem;margin:.2rem 0 .6rem'>"
                "De secretaris signaleert alleen; het overleg beslist. Consent verwijdert de rol, "
                "ook als er werk verweesd raakt.</p>")
        html = (f"<div class='rovm rovm-del'><div class='rovm-h'>"
                f"<span class='rovm-kind'>Verwijderen · <b>{_e(nm)}</b></span>{rm_member}</div>"
                f"<p>Deze rol wordt <b>verwijderd</b> als het voorstel wordt aangenomen.</p>{sec}{note}{revert}</div>")
        return html, []

    # --- amend / add blok ---
    acc_issues, general = {}, []
    for iss in _rov_signals(st, item):
        hit = next((a for a in draft["accs"] if a and a[:40].lower() in iss["msg"].lower()), None)
        if hit is not None:
            acc_issues.setdefault(hit, []).append(iss)
        else:
            general.append(iss)
    hard = _rov_hard(st, item)

    def field_form(field, label, value, was=""):
        waschip = f" <span class='rovm-was'>was: {_e(was)}</span>" if was else ""
        return (f"<div class='rovm-field'><label class='att-lbl'>{label}{waschip}</label>"
                f"<form method='post' action='/action' {keep}>{hid()}"
                f"<input type='hidden' name='action' value='rov2_set'><input type='hidden' name='field' value='{field}'>"
                f"<input name='value' value='{_e(value)}' onchange='{sub}'></form></div>")

    name_was = (snap.get("name", "") if (is_amend and (snap.get("name", "") or "") != draft["name"]) else "")
    purp_was = (snap.get("purpose", "") if (is_amend and snap.get("purpose")
                and (snap.get("purpose", "") or "") != draft["purpose"]) else "")
    name_f = field_form("name", "Naam", draft["name"], name_was)
    purpose_f = field_form("purpose", "Purpose", draft["purpose"], purp_was)

    def diff_list(label, orig, drafted, add_action, rm_action, per_issue=None):
        ol = {x.lower() for x in orig}
        dl = {x.lower() for x in drafted}

        def itform(text, action, lbl, cls):
            return (f"<form method='post' action='/action' style='display:inline' {keep}>{hid()}"
                    f"<input type='hidden' name='text' value='{_e(text)}'>"
                    f"<button class='{cls}' type='submit' name='action' value='{action}'>{lbl}</button></form>")
        rows = ""
        for x in orig:                                   # bestaand: behouden of (doorgestreept) verwijderd
            if x.lower() in dl:
                rows += (f"<div class='rovm-item'><span class='rovm-iv'>{_e(x)}</span>"
                         f"{itform(x, rm_action, '✕', 'dellink')}</div>"
                         f"{_iss_html(per_issue.get(x, [])) if per_issue else ''}")
            else:
                rows += (f"<div class='rovm-item is-del'><span class='rovm-iv'><s>{_e(x)}</s></span>"
                         f"{itform(x, add_action, 'herstel', 'flink')}</div>")
        for x in drafted:                                # nieuw toegevoegd
            if x.lower() not in ol:
                badge = "<span class='chip green'>nieuw</span> " if is_amend else ""
                rows += (f"<div class='rovm-item is-new'><span class='rovm-iv'>{badge}{_e(x)}</span>"
                         f"{itform(x, rm_action, '✕', 'dellink')}</div>"
                         f"{_iss_html(per_issue.get(x, [])) if per_issue else ''}")
        addf = (f"<form method='post' action='/action' class='rov-addrow' {keep}>{hid()}"
                f"<input name='text' placeholder='{_e(label.lower())} toevoegen…'>"
                f"<button class='btn ok sm' type='submit' name='action' value='{add_action}'>+</button></form>")
        return f"<div class='rovm-field'><label class='att-lbl'>{_e(label)}</label>{rows}{addf}</div>"

    acc_b = diff_list("Accountabilities", list(snap["accountabilities"]) if snap else [], draft["accs"],
                      "rov2_acc_add", "rov2_acc_remove", per_issue=acc_issues)
    dom_b = diff_list("Domeinen", list(snap["domains"]) if snap else [], draft["domains"],
                      "rov2_dom_add", "rov2_dom_remove")

    sec = ""
    if general:
        sec += f"<div class='sec-block'><div class='sec-kop'>📋 Secretaris (advies)</div>{_iss_html(general)}</div>"
    if hard:
        sec += ("<div class='sec-block'>"
                + "".join(f"<div class='sec-issue blok'>⛔ {_e(h)}</div>" for h in hard) + "</div>")

    # GlassFrog: 'verwijder deze rol' + 'maak van deze rol een cirkel' (roadmap, grijs).
    footer = ""
    if item.get("kind") == "amend_role":
        delrole = (f"<form method='post' action='/action' {keep}>{hid()}"
                   f"<input type='hidden' name='kind' value='remove_role'>"
                   f"<button class='flink' type='submit' name='action' value='rov2_setkind'>Rol verwijderen</button></form>")
        circ = "<span class='flink is-soon' title='Binnenkort'>Maak van deze rol een cirkel</span>"
        footer = f"<div class='rovm-foot rov-delrole'>{delrole}{circ}</div>"

    kindlbl = "Nieuwe rol" if item.get("kind") == "add_role" else "Wijzigen rol"
    nm = draft["name"] or item.get("title")
    head = f"<div class='rovm-h'><span class='rovm-kind'>{kindlbl} · <b>{_e(nm)}</b></span>{rm_member}</div>"
    html = f"<div class='rovm'>{head}{name_f}{purpose_f}{acc_b}{dom_b}{sec}{footer}</div>"
    return html, hard


def _rov_editor(st: _Stores, item: dict, csrf: str, back: str, circle_id: str = "") -> str:
    """Een voorstel (GlassFrog-model): één of meer rol-wijzigingen samen, met diff-weergave en één
    consent voor het hele voorstel. 'Toevoegen aan voorstel' betrekt nog een (bestaande of nieuwe)
    rol erbij. Werkafspraak/verkiezing zijn roadmap (grijs)."""
    base = f"/roloverleg2?circle={circle_id}"
    gid = st.agenda.group_of(item["id"])
    members = st.agenda.members_of_group(gid) or [item]
    back = f"{base}&iid={item['id']}"

    blocks, all_hard = "", []
    for m in members:
        b, hard = _rov_member_block(st, m, csrf, back, circle_id)
        blocks += b
        all_hard += hard

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='iid' value='{_e(item['id'])}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")
    keep = f"data-reopen='{_e(back)}'"

    roles = sorted(_rov_children(st, circle_id), key=lambda r: _name(r).lower())
    dl = "".join(f"<option value='{_e(_name(r))}'>" for r in roles)
    add_role = (f"<form method='post' action='/action' class='rov-addrow' {keep}>{hid()}"
                f"<input type='hidden' name='group' value='{_e(gid)}'>"
                f"<input name='naam' list='rov-roles-add' placeholder='Bestaande of nieuwe rol… (-SW)' autocomplete='off'>"
                f"<datalist id='rov-roles-add'>{dl}</datalist>"
                f"<button class='btn ok sm' type='submit' name='action' value='rov2_add_to_group'>+</button></form>")
    soon = "<select disabled><option>Binnenkort</option></select>"
    add_block = (f"<div class='rov-addprop'><div class='sec-kop'>Toevoegen aan voorstel</div>"
                 f"<div class='rov-addgrid'>"
                 f"<div><label class='att-lbl'>Rol toevoegen/wijzigen</label>{add_role}</div>"
                 f"<div><label class='att-lbl is-soon'>Werkafspraak toevoegen/wijzigen</label>{soon}</div>"
                 f"</div></div>")

    if all_hard:
        consent = ("<button class='btn ok' disabled>Neem voorstel aan</button> "
                   "<span class='muted'>los de blokkade(s) op</span>")
    else:
        consent = (f"<form method='post' action='/action'>{hid()}"
                   f"<button class='btn ok' type='submit' name='action' value='rov2_consent' "
                   f"data-reopen='{_e(base)}'>Neem voorstel aan</button></form>")

    return (f"<div class='rov-editor'>{blocks}{add_block}"
            f"<div class='rov-consent'>{consent}</div></div>")


def _rov_chat(st: _Stores, item: dict, csrf: str, circle_id: str) -> str:
    """AI-assistent als chatvenster (vanuit de footer). Eerst de keuze: spanning verhelderen of
    accountability formuleren. Bij 'accountability' checkt het systeem automatisch of die niet al
    elders belegd is. Fail-closed zonder AI-key (jouw bericht blijft staan, geen AI-antwoord)."""
    base = f"/roloverleg2?circle={circle_id}"
    iid = item["id"]
    churl = f"{base}&iid={iid}&chat=1"
    close = f"{base}&iid={iid}"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='iid' value='{_e(iid)}'>"
                f"<input type='hidden' name='next' value='{_e(close)}'>")
    keep = f"data-reopen='{_e(churl)}'"
    head = (f"<div class='rovchat-head'><span>{_IC_CHAT}AI-assistent</span>"
            f"<a class='rovchat-x js-modal' href='{close}' data-href='{close}' title='Sluiten'>✕</a></div>")

    mode = item.get("chatmode") or ""
    if mode not in ("spanning", "accountability"):
        def opt(m, lbl):
            return (f"<form method='post' action='/action' {keep}>{hid()}"
                    f"<input type='hidden' name='mode' value='{m}'>"
                    f"<button class='btn' type='submit' name='action' value='rov2_chat_start'>{lbl}</button></form>")
        body = (f"<div class='rovchat-intro'><p class='muted'>Waar kan ik mee helpen?</p>"
                f"{opt('spanning', 'Spanning verhelderen')}"
                f"{opt('accountability', 'Accountability formuleren')}</div>")
        return f"<div class='rovchat'>{head}{body}</div>"

    msgs = ""
    for m in (item.get("kladblok") or []):
        who = m.get("who")
        cls = "ai" if who == "ai" else ("note" if who == "note" else "jij")
        lbl = {"ai": "🤖 AI", "note": "⚠ Check"}.get(who, "🙋 jij")
        msgs += (f"<div class='kb-msg {cls}'><span class='kb-who'>{lbl}</span>"
                 f"<div class='kb-text'>{_md(m.get('text', ''))}</div></div>")
    ph = "Beschrijf de spanning…" if mode == "spanning" else "Waar gaat de accountability over?"
    comp = (f"<form method='post' action='/action' class='kb-form' {keep}>{hid()}"
            f"<textarea name='text' rows='2' placeholder='{ph}'></textarea>"
            f"<button class='btn ok sm' type='submit' name='action' value='rov2_kladblok' "
            f"style='margin-top:.3rem'>Stuur</button></form>")
    label = "Spanning verhelderen" if mode == "spanning" else "Accountability formuleren"
    reset = (f"<form method='post' action='/action' {keep}>{hid()}"
             f"<input type='hidden' name='mode' value='reset'>"
             f"<button class='flink' type='submit' name='action' value='rov2_chat_start'>↺ ander onderwerp</button></form>")
    sub = f"<div class='rovchat-mode'><span>{label}</span>{reset}</div>"
    return f"<div class='rovchat'>{head}{sub}<div class='kb-body'>{msgs}{comp}</div></div>"


# --- Noochie: de globale AI-assistent (ESFP) -----------------------------------------------------

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


def _wo_hid(csrf, circle, nextu):
    return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='circle' value='{_e(circle)}'>"
            f"<input type='hidden' name='next' value='{_e(nextu)}'>")


def _wo_checkin(st: _Stores, crec, csrf: str) -> str:
    """Stap 1: aanwezigheid. ✓ = aanwezig, ✗ = afwezig/op verlof (taken pauzeren)."""
    ppl = _members_of_circle(st, crec.id)
    nxt = f"/werkoverleg?circle={crec.id}&step=checkin"
    if not ppl:
        return ("<div class='c2-sec'><h3>Check-in</h3>"
                "<p class='muted'>Nog geen mensen aan deze cirkel gekoppeld (zie Rollen → rolvervullers).</p></div>")
    rows = ""
    for p in ppl:
        present = st.werk.is_present(crec.id, p.id)
        if csrf:
            def b(val, lbl, c):
                on = " on" if present == val else ""
                return (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, nxt)}"
                        f"<input type='hidden' name='pid' value='{_e(p.id)}'>"
                        f"<input type='hidden' name='present' value='{'1' if val else '0'}'>"
                        f"<button class='cl-check {c}{on}' type='submit' name='action' value='wo_presence' "
                        f"title='{lbl}'>{'✓' if val else '✗'}</button></form>")
            ctrl = b(True, "aanwezig", "ok") + b(False, "afwezig (verlof)", "no")
        else:
            ctrl = f"<span class='cl-check {'ok' if present else 'no'} on'>{'✓' if present else '✗'}</span>"
        leave = "" if present else "<span class='wo-leave muted'>op verlof — taken gepauzeerd</span>"
        rows += (f"<div class='wo-mem{'' if present else ' absent'}'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>{leave}<span class='cl-checks'>{ctrl}</span></div>")
    allbtn = ""
    if csrf:
        allbtn = (f"<form method='post' action='/action'>{_wo_hid(csrf, crec.id, nxt)}"
                  f"<button class='btn sm' type='submit' name='action' value='wo_present_all'>Allen aanwezig</button></form>")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-in</h3>{allbtn}</div>"
            f"<p class='muted' style='font-size:.8rem'>Wie doet mee? Klik of gebruik ↑/↓ en dan "
            f"<b>v</b> (aanwezig) / <b>x</b> (afwezig). ✗ = op verlof: niet aanwezig en taken pauzeren.</p>"
            f"<div class='wo-mems' tabindex='0'>{rows}</div></div>")


def _wo_checklist(st: _Stores, crec, csrf: str) -> str:
    """Stap 2: de checklist-ronde. Hergebruikt het checklist-scherm; toont wie rapporteert
    (afwezigen met ✗)."""
    ppl = _members_of_circle(st, crec.id)
    chips = "".join(
        f"<span class='chip {'muted' if st.werk.is_present(crec.id, p.id) else 'coral'}'>"
        f"{'✗ ' if not st.werk.is_present(crec.id, p.id) else ''}{_e(p.name)}</span>" for p in ppl)
    who = f"<div class='wo-who'><span class='muted'>Rapporteren:</span> {chips}</div>" if ppl else ""
    # In het overleg: toon ALLES (afgevinkte items met hun resultaat blijven staan) en blijf in de modal.
    nav = f"/werkoverleg?circle={crec.id}&step=checklist"
    return who + _checklists_tab_html(st, crec, csrf, "all", nav=nav)


def _wo_metrics(st: _Stores, crec, csrf: str, kpi: str = "", win: str = "maand") -> str:
    """Stap 3: metrics-ronde. Hergebruikt het dashboard; optioneel één tegel uitvergroot met
    trend + tabel + een knop voor Noochie-duiding."""
    base = f"/werkoverleg?circle={crec.id}&step=metrics"
    focus = ""
    if kpi:
        tile = next((t for t in st.metrics.tiles_of(crec.id) if t["id"] == kpi), None)
        if tile is not None:
            res = _fetch(st, tile["source"], tile["measure"], tile.get("dim", "none"), None)
            pts = res.get("points") or []
            rows = res.get("rows") or []
            tbl = ""
            if pts:
                tbl = "<table class='mtab'>" + "".join(
                    f"<tr><td>{_dt(at)}</td><td class='num'>{v:g}</td></tr>" for at, v in pts[-12:]) + "</table>"
            elif rows:
                tbl = "<table class='mtab'>" + "".join(
                    f"<tr><td>{_e(str(l))}</td><td class='num'>{n:g}</td></tr>" for l, n in rows[:12]) + "</table>"
            ask = _e(f"{_tile_meta(st, crec, tile)} (laatste: {(_num(_agg(res)))})")
            ai = (f"<button class='btn sm' type='button' onclick=\"window.noochieAsk&&noochieAsk('{ask}')\">"
                  f"🐸 Noochie duidt deze KPI</button>")
            focus = (f"<div class='c2-sec wo-focus'><div class='cl-head'><h3>{_e(_tile_meta(st, crec, tile))}</h3>"
                     f"<a class='flink js-modal' href='{base}' data-href='{base}'>← terug</a></div>"
                     f"{_spark_svg(pts, 280, 70) if pts else ''}{tbl or '<p class=muted>geen data</p>'}"
                     f"<div style='margin-top:.6rem'>{ai}</div></div>")
    # uitvergroot-links per tegel
    links = ""
    for t in st.metrics.tiles_of(crec.id):
        u = f"{base}&kpi={t['id']}"
        links += f"<a class='chip outline js-modal' href='{u}' data-href='{u}'>{_e(_tile_meta(st, crec, t))}</a> "
    tabrow = f"<div class='wo-kpitabs'>{links}</div>" if links else ""
    return focus + tabrow + _metrics_tab_html(st, crec, csrf, win, nav=base)


def _wo_spanning_add(st: _Stores, crec, csrf: str) -> str:
    """Spanning toevoegen — staat bovenaan de linkerkolom (boven de stappen), altijd bereikbaar."""
    if not csrf:
        return "<span class='muted'>—</span>"
    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    return (f"<form method='post' action='/action' class='rov-add wo-sp-add'>{_wo_hid(csrf, crec.id, base)}"
            f"<input name='naam' placeholder='Spanning… (-SW voor initialen)' autocomplete='off'>"
            f"<button class='btn ok sm' type='submit' name='action' value='wo_ag_add'>+</button></form>")


def _wo_spanning_items(st: _Stores, crec, csrf: str, active_iid: str = "") -> str:
    """Ingebrachte spanningen — genest onder de Agenda-stap in het linkermenu (geen microcopy)."""
    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    rows = ""
    for it in st.werk.agenda(crec.id):
        done = it["status"] == "done"
        on = " on" if it["id"] == active_iid else ""
        url = f"{base}&iid={it['id']}"
        by = (it.get("by") or "").strip()
        av = f"<span class='av rov-by' title='door {_e(by)}'>{_e(by)}</span>" if by else ""
        rm = (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, base)}"
              f"<input type='hidden' name='iid' value='{_e(it['id'])}'>"
              f"<button class='flink' type='submit' name='action' value='wo_ag_remove'>✕</button></form>") if csrf else ""
        rows += (f"<div class='rov-item{on}{(' done' if done else '')}'>"
                 f"<a class='js-modal rov-link' href='{url}' data-href='{url}'><span class='rov-title'>{_e(it['title'])}</span></a>"
                 f"{av}{rm}</div>")
    return rows


def _wo_triage(st: _Stores, crec, csrf: str, item: dict) -> str:
    """Stap 5b: een spanning verwerken. Noteer spanning/rol/behoefte en kies een uitkomst:
    info delen, project toevoegen, punt voor roloverleg, of nevermind."""
    iid = item["id"]
    base = f"/werkoverleg?circle={crec.id}&step=agenda"
    back = f"{base}&iid={iid}"
    note = item.get("note", {})
    done = item["status"] == "done"
    roles = sorted(org.roles_of(st.records.all(), crec.id), key=lambda r: _name(r).lower())
    keep = f"data-reopen='{_e(back)}'"
    sub = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"

    def setf(field, label, value, ta=False):
        inp = (f"<textarea name='value' rows='2' onchange='{sub}'>{_e(value)}</textarea>" if ta
               else f"<input name='value' value='{_e(value)}' onchange='{sub}'>")
        return (f"<div class='rovm-field'><label class='att-lbl'>{label}</label>"
                f"<form method='post' action='/action' {keep}>{_wo_hid(csrf, crec.id, back)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='field' value='{field}'>"
                f"<input type='hidden' name='action' value='wo_ag_note'>{inp}</form></div>")

    ropts = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
    cur_role = note.get("role", "")
    ropts_role = "".join(f"<option value='{_e(r.id)}'{' selected' if r.id == cur_role else ''}>{_e(_name(r))}</option>"
                         for r in roles)
    head = f"<div class='cl-head'><h3>Spanning verwerken</h3><a class='flink js-modal' href='{base}' data-href='{base}'>← agenda</a></div>"
    if done:
        oc = item.get("outcome", {})
        return (f"<div class='c2-sec'>{head}<p><b>{_e(item['title'])}</b></p>"
                f"<div class='sec-issue let'>Afgehandeld als <b>{_e(oc.get('type', ''))}</b>"
                f"{(': ' + _e(oc.get('detail', ''))) if oc.get('detail') else ''}</div>"
                f"<form method='post' action='/action' {keep} style='margin-top:.5rem'>{_wo_hid(csrf, crec.id, back)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'>"
                f"<button class='flink' type='submit' name='action' value='wo_ag_reopen'>↺ heropenen</button></form></div>")

    # Spanning + rol (optioneel) als eigen blok, los van de uitkomsten. 'Wat heb je nodig' is weg:
    # dat is altijd de uitkomst zelf.
    fields = (f"<div class='wo-spanning'>"
              + setf("spanning", "Wat is de spanning?", note.get("spanning", ""), ta=True)
              + f"<div class='rovm-field'><label class='att-lbl'>Welke rol voelt 'm? (optioneel)</label>"
                f"<form method='post' action='/action' {keep}>{_wo_hid(csrf, crec.id, back)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='field' value='role'>"
                f"<input type='hidden' name='action' value='wo_ag_note'>"
                f"<select name='value' onchange='{sub}'><option value=''>—</option>{ropts_role}</select></form></div></div>")

    # Progressive disclosure: kies eerst het type, dan verschijnt het juiste veld. Gelijkwaardig
    # (geen primary-kleur die naar één uitkomst stuurt).
    def oc_details(otype, summary, inner):
        return (f"<details class='wo-ocd'><summary>{summary}</summary>"
                f"<form method='post' action='/action' {keep} class='wo-oc'>{_wo_hid(csrf, crec.id, base)}"
                f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='otype' value='{otype}'>"
                f"{inner}<button class='btn sm' type='submit' name='action' value='wo_ag_resolve'>Vastleggen</button></form></details>")

    # projecten onder deze cirkel (om een actie optioneel aan te koppelen = checklist-item),
    # gegroepeerd per rol zodat het ook bij veel projecten navigeerbaar blijft (+ type-ahead).
    circle_nodes = {crec.id} | {r.id for r in roles}
    by_role: dict = {}
    for p in st.projects.all():
        if p.get("owner") in circle_nodes and not p.get("archived"):
            by_role.setdefault(p["owner"], []).append(p)
    pj_opts = "<option value=''>— los (geen project) —</option>"
    for rid in sorted(by_role, key=lambda x: _name(st.records.get(x) or crec).lower()):
        rn = _name(st.records.get(rid)) if st.records.get(rid) else rid
        opts = "".join(f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:60])}</option>"
                       for p in by_role[rid])
        pj_opts += f"<optgroup label='{_e(rn)}'>{opts}</optgroup>"

    info = oc_details("info", "Informatie",
                      "<select name='dir'><option value='delen'>delen</option>"
                      "<option value='nodig'>nodig</option></select>"
                      "<textarea name='detail' rows='2' placeholder='Wat? Gebruik @naam of @rol voor "
                      "gericht; anders geldt het voor iedereen'></textarea>")
    proj = oc_details("project", "Project toevoegen",
                      f"<select name='owner'>{ropts}</select>"
                      f"<input name='detail' placeholder='formulering van het project' autocomplete='off'>")
    act = oc_details("action", "Actie",
                     "<input name='detail' placeholder='wat ga je doen? (bv. meeting plannen, mail doorsturen)' autocomplete='off'>"
                     f"<select name='pid_link'>{pj_opts}</select>"
                     "<span class='muted' style='font-size:.74rem'>Gaat altijd door. Aan een project gekoppeld "
                     "= checklist-item; los = losse actie. Terugkerend werk? Overweeg het roloverleg.</span>")
    rov = oc_details("roloverleg", "Punt voor roloverleg",
                     "<textarea name='detail' rows='2' placeholder='kans / probleem / behoefte / eerste rol-schets'></textarea>")
    nm = (f"<form method='post' action='/action' {keep} class='wo-oc'>{_wo_hid(csrf, crec.id, base)}"
          f"<input type='hidden' name='iid' value='{_e(iid)}'><input type='hidden' name='otype' value='nevermind'>"
          f"<button class='flink' type='submit' name='action' value='wo_ag_resolve'>Niet nodig</button></form>")
    # secretaris-signaal (licht): mis je info/scope? (Noochie zit al in de balk; geen losse knop.)
    hint = ""
    if not (note.get("spanning") or "").strip():
        hint = "<div class='sec-issue let'>📋 Secretaris: noteer kort de spanning zodat 'm te verwerken is.</div>"
    return (f"<div class='c2-sec'>{head}<p><b>{_e(item['title'])}</b></p>{hint}{fields}"
            f"<div class='wo-outcomes'><div class='sec-kop'>Uitkomst kiezen</div>{info}{proj}{act}{rov}{nm}</div></div>")


def _wo_checkout(st: _Stores, crec, csrf: str) -> str:
    """Stap 6: check-out. Per persoon een tevredenheidsscore 0-10."""
    ppl = _members_of_circle(st, crec.id)
    nxt = f"/werkoverleg?circle={crec.id}&step=checkout"
    scores = st.werk.checkout(crec.id)
    if not ppl:
        return "<div class='c2-sec'><h3>Check-out</h3><p class='muted'>Geen leden.</p></div>"
    prev = st.werk.prev_checkout(crec.id)               # scores van het vorige overleg (ghost)
    vals = [v for v in scores.values() if isinstance(v, int)]
    avg = f"{round(sum(vals) / len(vals), 1)}/10" if vals else "—"
    rows = ""
    for p in ppl:
        cur = scores.get(p.id)
        pv = prev.get(p.id)
        if csrf:
            cells = ""
            for n in range(0, 11):
                cls = "wo-sc" + (" on" if cur == n else (" prev" if cur is None and pv == n else ""))
                title = " title='vorige keer'" if (pv == n and cur != n) else ""
                cells += (f"<form method='post' action='/action' style='display:inline'>{_wo_hid(csrf, crec.id, nxt)}"
                          f"<input type='hidden' name='pid' value='{_e(p.id)}'><input type='hidden' name='score' value='{n}'>"
                          f"<button class='{cls}'{title} type='submit' name='action' value='wo_checkout'>{n}</button></form>")
            sel = f"<span class='wo-scale'>{cells}</span>"
        else:
            sel = f"<span class='kpidata-v'>{cur if cur is not None else '—'}</span>"
        rows += (f"<div class='wo-mem'><span class='av'>{_e(_initials(p.name))}</span>"
                 f"<span class='wo-mem-n'>{_e(p.name)}</span>{sel}</div>")
    legend = ("<span class='muted' style='font-size:.74rem'>lichter = vorige keer</span>"
              if prev else "")
    return (f"<div class='c2-sec'><div class='cl-head'><h3>Check-out</h3>"
            f"<span class='muted'>gemiddeld: <span class='wo-avg'>{avg}</span></span></div>"
            f"<p class='muted' style='font-size:.8rem'>Op een schaal van 0-10: hoe tevreden ben je met "
            f"de uitkomst van dit overleg? {legend}</p>{rows}</div>")


def _wo_summary(st: _Stores, crec, csrf: str) -> str:
    """Stap 7: samenvatting + sluiten (confetti via wo_close)."""
    s = st.werk.summary(crec.id)
    pres = st.werk.presence(crec.id)
    ppl = _members_of_circle(st, crec.id)
    aanwezig = [p.name for p in ppl if pres.get(p.id, True)]
    afwezig = [p.name for p in ppl if pres.get(p.id) is False]
    tev = f"{s['tevredenheid']}/10" if s["tevredenheid"] is not None else "n.v.t."
    rij = lambda k, v: f"<div class='wo-sumrow'><span>{k}</span><b>{v}</b></div>"
    body = (rij("Aanwezig", ", ".join(aanwezig) or "—")
            + rij("Afwezig", ", ".join(afwezig) or "—")
            + rij("Punten behandeld", s["behandeld"])
            + rij("Informatie verwerkt", s["info"])
            + rij("Projecten toegevoegd", s["projecten"])
            + rij("Acties", s.get("acties", 0))
            + rij("Punten voor roloverleg", s["roloverleg"])
            + rij("Gemiddelde tevredenheid", tev)
            + rij("Duur", f"{s['duur_min']} min"))
    return (f"<div class='c2-sec'><h3>Samenvatting</h3><div class='wo-sum'>{body}</div>"
            f"<p class='muted' style='font-size:.8rem;margin-top:.6rem'>Klik “Sluit overleg” onderaan: "
            f"alle uitkomsten worden verwerkt en het overleg sluit.</p></div>")


def render_werkoverleg(st: _Stores, circle_id: str, step: str = "checkin", csrf_token: str = "",
                       fragment: bool = False, iid: str = "", kpi: str = "", mw: str = "maand") -> str:
    """Werkoverleg-modal: links de vaste stap-navigatie, rechts de inhoud per stap. De inhoud
    HERGEBRUIKT de bestaande schermen (members/checklists/metrics/projecten). Alleen de secretaris
    opent en sluit. Brok 1: frame + ingebedde schermen; de overleg-specifieke stappen volgen."""
    crec = st.records.get(circle_id)
    if crec is None or not org.is_circle(crec):
        return ("<p class='muted'>Geen cirkel.</p>" if fragment
                else _page("Niet gevonden", "<p>Geen cirkel.</p>"))
    base = f"/werkoverleg?circle={circle_id}"
    sec = "<div class='wo-sec muted'>Alleen de secretaris opent en sluit dit overleg.</div>"

    def hid(nextu):
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(nextu)}'>")

    if not st.werk.is_open(circle_id):
        start = ""
        if csrf_token:
            su = f"{base}&step=checkin"
            start = (f"<form method='post' action='/action'>{hid(su)}"
                     f"<button class='btn ok' type='submit' name='action' value='wo_open' "
                     f"data-reopen='{_e(su)}'>Werkoverleg starten</button></form>")
        body = (f"<h2 style='margin-top:0'>Werkoverleg — {_e(_name(crec))}</h2>"
                f"<p class='muted'>Vaste volgorde: check-in, checklist, metrics, projecten, agenda, "
                f"check-out, sluiten.</p>{sec}<div style='margin-top:1rem'>{start}</div>")
        return body if fragment else _page(
            "Werkoverleg", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{body}</div>")

    cur = step if step in dict(_WO_STEPS) else "checkin"
    st.werk.mark_visited(circle_id, cur)                 # voortgang: bezochte stappen
    visited = set(st.werk.visited(circle_id))
    nav = ""
    for i, (k, lbl) in enumerate(_WO_STEPS, 1):
        url = f"{base}&step={k}"
        done = k in visited and k != cur
        num = "✓" if done else str(i)
        cls = "wo-step" + (" on" if k == cur else "") + (" done" if done else "")
        nav += (f"<a class='{cls} js-modal' href='{url}' data-href='{url}'>"
                f"<span class='wo-num'>{num}</span>{_e(lbl)}</a>")
        if k == "agenda":   # ingebrachte spanningen genest onder de Agenda-stap
            items = _wo_spanning_items(st, crec, csrf_token, iid)
            if items:
                nav += f"<div class='wo-substeps'>{items}</div>"
    # Spanning toevoegen staat bovenaan (boven Check-in); de stappen eronder.
    left = (_psec(_IC_INFO, "Spanningen", _wo_spanning_add(st, crec, csrf_token))
            + _psec(_IC_CHECK, "Overleg", f"<div class='wo-nav'>{nav}</div>"))

    if cur == "checkin":
        content = _wo_checkin(st, crec, csrf_token)
    elif cur == "checklist":
        content = _wo_checklist(st, crec, csrf_token)
    elif cur == "metrics":
        content = _wo_metrics(st, crec, csrf_token, kpi, win=mw)
    elif cur == "projecten":
        # In het overleg worden projecten via de triage (agenda) toegevoegd, niet hier los.
        content = _projects_tab_html(st, crec, csrf_token, group="", add=False)
    elif cur == "agenda":
        item = st.werk.agenda_get(crec.id, iid) if iid else None
        content = (_wo_triage(st, crec, csrf_token, item) if item is not None
                   else "<div class='c2-sec'><h3>Spanning verwerken</h3>"
                        "<p class='muted'>Kies links een spanning om te verwerken, of voeg er een toe.</p></div>")
    elif cur == "checkout":
        content = _wo_checkout(st, crec, csrf_token)
    else:
        content = _wo_summary(st, crec, csrf_token)

    foot = (f"<div class='rov-foot'><form method='post' action='/action' "
            f"data-confirm='Overleg sluiten en alle uitkomsten verwerken? Dit kan niet ongedaan.'>"
            f"{hid(f'/node?id={circle_id}')}"
            f"<button class='btn ok' type='submit' name='action' value='wo_close'>Sluit overleg</button></form>"
            f"<span class='muted'>loopt {st.werk.duration_min(circle_id)} min</span></div>")
    detail = (f"<h2 style='margin-top:0'>Werkoverleg — {_e(_name(crec))}</h2>"
              f"<div class='pgrid rov-grid'><div class='pmain'>{left}</div>"
              f"<aside class='pdisc'>{content}</aside></div>{foot}")
    if fragment:
        return detail
    return _page("Werkoverleg", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>"
                 f"<div class='c2-main' style='max-width:1000px'>{detail}</div></div>")


def render_roloverleg2(st: _Stores, circle_id: str, iid: str = "", csrf_token: str = "",
                       fragment: bool = False, chat: bool = False) -> str:
    """Roloverleg in modal-vorm. Brok 1: frame + agenda links (toevoegen, lijst, selecteren)."""
    crec = st.records.get(circle_id)
    if crec is None:
        return ("<p class='muted'>Onbekende cirkel.</p>" if fragment
                else _page("Niet gevonden", "<p>Onbekend.</p>"))
    base = f"/roloverleg2?circle={circle_id}"
    roles = sorted(_rov_children(st, circle_id), key=lambda r: _name(r).lower())

    def hid(nextu):
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
                f"<input type='hidden' name='next' value='{_e(nextu)}'>")

    # Agenda-lijst: één rij per VOORSTEL (GlassFrog: een voorstel kan meerdere rol-wijzigingen
    # bevatten). Behandeld = doorgestreept; initialen van de indiener achteraan.
    items_all = _rov_items(st, circle_id)
    items_open = _rov_open(st, circle_id)
    active = iid or (items_open[0]["id"] if items_open else "")
    rows = ""
    for gid, members in _rov_groups(st, circle_id):
        primary = members[0]
        done = all(m.get("status") == "consented" for m in members)
        on = any(m["id"] == active for m in members)
        cls = "rov-item" + (" on" if on else "") + (" done" if done else "")
        url = f"{base}&iid={primary['id']}"
        rm = (f"<form method='post' action='/action' style='display:inline'>{hid(base)}"
              f"<input type='hidden' name='iid' value='{_e(primary['id'])}'>"
              f"<button class='flink' type='submit' name='action' value='rov2_remove_group'>✕</button></form>")
        by = (primary.get("by") or "").strip()
        av = f"<span class='av rov-by' title='door {_e(by)}'>{_e(by)}</span>" if by and by != "founder" else ""
        title = primary.get("title") or primary.get("role_id")
        extra = f" <span class='rov-more'>+{len(members) - 1}</span>" if len(members) > 1 else ""
        rows += (f"<div class='{cls}'><a class='js-modal rov-link' href='{url}' data-href='{url}'>"
                 f"<span class='rov-title'>{_e(title)}{extra}</span></a>"
                 f"{av}{rm}</div>")
    if not rows:
        rows = "<p class='muted'>Nog geen agendapunten.</p>"

    # Toevoegen boven de lijst; minimalistisch: één veld (Enter of '+'); smart-search op bestaande rollen.
    dl = "".join(f"<option value='{_e(_name(r))}'>" for r in roles)
    add = (f"<form method='post' action='/action' class='rov-add'>{hid(base)}"
           f"<input name='naam' list='rov-roles' placeholder='Rol… (-SW voor initialen)' autocomplete='off'>"
           f"<datalist id='rov-roles'>{dl}</datalist>"
           f"<button class='btn ok sm' type='submit' name='action' value='rov2_add'>+</button></form>")
    left = _psec(_IC_CHECK, "Agenda", f"{add}<div class='rov-list'>{rows}</div>")

    # Rechts: editor van het geselecteerde voorstel; geen iid -> auto-selecteer het eerste open punt
    # (zo land je na consent vanzelf op het volgende).
    sel = next((it for it in items_all if it["id"] == iid), None) or (items_open[0] if items_open else None)
    if sel:
        right = _rov_editor(st, sel, csrf_token, f"{base}&iid={sel['id']}", circle_id=circle_id)
    else:
        right = "<p class='muted'>Geen open agendapunten meer. Voeg er een toe, of sluit de vergadering.</p>"

    # AI-assistent: knop rechts in de footer; opent een chatvenster (chat=1) bij het actieve punt.
    ai_btn = ""
    if sel:
        churl = f"{base}&iid={sel['id']}&chat=1"
        ai_btn = (f"<a class='btn js-modal rovchat-toggle' href='{churl}' data-href='{churl}'>"
                  f"{_IC_CHAT}AI-assistent</a>")
    n_consent = sum(1 for it in items_all if it.get("status") == "consented")
    confirm = (f"Overleg sluiten? {n_consent} aangenomen voorstel(len) worden doorgevoerd in de "
               f"records. Dit kan niet ongedaan." if n_consent
               else "Overleg sluiten? Er zijn geen aangenomen voorstellen om door te voeren.")
    foot = (f"<div class='rov-foot'><form method='post' action='/action' data-confirm='{_e(confirm)}'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='circle' value='{_e(circle_id)}'>"
            f"<input type='hidden' name='next' value='/node?id={_e(circle_id)}'>"
            f"<button class='btn ok' type='submit' name='action' value='rov2_end'>"
            f"Vergadering sluiten</button></form>{ai_btn}</div>")
    chat_panel = _rov_chat(st, sel, csrf_token, circle_id) if (chat and sel) else ""
    sec_note = ("<p class='wo-sec muted' style='margin:.2rem 0 .6rem'>Alleen de secretaris opent en "
                "sluit dit overleg.</p>")
    detail = (f"<h2 style='margin-top:0'>Governance meeting — {_e(_name(crec))}</h2>{sec_note}"
              f"<div class='pgrid rov-grid'><div class='pmain'>{left}</div>"
              f"<aside class='pdisc'>{right}</aside></div>{foot}{chat_panel}")
    if fragment:
        return detail
    main = f"<div class='c2-main' style='max-width:980px'><div class='c2-bar'><a href='/node?id={_e(circle_id)}'>← terug</a></div>{detail}</div>"
    return _page("Roloverleg", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")


def _feed_norm(entry: dict):
    """Normaliseer een feed-entry naar (kind, author_type, author_id). Leest zowel het nieuwe
    schema (author/kind) als het oude ({who: 'mens'|'rol'})."""
    if "author" in entry:
        a = entry.get("author") or {}
        return entry.get("kind", "comment"), a.get("type", "human"), a.get("id", "")
    if entry.get("who") == "rol":
        return "update", "role", ""
    return "comment", "human", ""


def _feed_who(st: _Stores, atype: str, aid: str):
    """(avatar-html, naam) voor een feed-auteur."""
    if atype == "person":
        nm = _person_name(st, aid) or "Iemand"
        return _avatar(nm, False), nm
    if atype == "persona":
        pa = st.personas.get(aid)
        nm = pa.name if pa else "AI"
        return _avatar(nm, True), nm
    if atype == "role":
        r = st.records.get(aid)
        return "<span class='av role'>R</span>", (_name(r) if r else "Rol")
    return "<span class='av'>🙋</span>", "Jij"


def _stamp(ts) -> str:
    """Datum + tijd, bijv. '27 jun 2026, 14:32'."""
    if not ts:
        return ""
    import datetime
    d = datetime.datetime.fromtimestamp(ts)
    return f"{d.day} {_NL_MND[d.month - 1]} {d.year}, {d.hour:02d}:{d.minute:02d}"


def _md(text: str) -> str:
    """Lichte opmaak voor reacties: HTML-veilig, met **vet**, regelafbrekingen en '- ' lijstjes."""
    import re
    s = _e(text or "")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    out, in_ul = [], False
    for ln in s.split("\n"):
        if ln.strip().startswith("- "):
            if not in_ul:
                out.append("<ul class='fbul'>"); in_ul = True
            out.append(f"<li>{ln.strip()[2:]}</li>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(ln + "<br>")
    if in_ul:
        out.append("</ul>")
    html = "".join(out)
    return html[:-4] if html.endswith("<br>") else html


def _mentionables(st: _Stores):
    """(lijst voor de JS-autocomplete, naam→doel-map voor het parsen). Rollen + mensen."""
    js, by_name = [], {}
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        nm = _name(r)
        js.append({"l": nm}); by_name[nm.lower()] = ("role", r.id)
    for pr in st.people.all():
        js.append({"l": pr.name}); by_name[pr.name.lower()] = ("person", pr.id)
    return js, by_name


def _mentions_in(text: str, by_name: dict):
    """(type, id, naam) voor elke '@naam' uit by_name die in de tekst voorkomt."""
    t = (text or "").lower()
    return [(ty, i, nm) for nm, (ty, i) in by_name.items() if ("@" + nm) in t]


def _hilite_mentions(html: str, names) -> str:
    """Markeer '@naam' in al-gerenderde (veilige) HTML. Langste namen eerst (subset-botsing)."""
    for nm in sorted(names, key=len, reverse=True):
        esc = _e(nm)
        html = html.replace("@" + esc, f"<span class='ment'>@{esc}</span>")
    return html


# Gecureerde set standaard emoji's met zoekwoorden (NL/EN) voor de picker.
_EMOJIS_FULL = [
    ("👍", "duim like goed prima"), ("👎", "duim slecht nee"), ("🙏", "dank bedankt please"),
    ("👏", "applaus klap"), ("🙌", "hoera yes"), ("💪", "sterk kracht power"), ("🤝", "deal akkoord hand"),
    ("😀", "blij lach happy"), ("😂", "lachen lol"), ("😉", "knipoog wink"), ("😍", "liefde hart love"),
    ("😎", "cool stoer"), ("🤔", "denken hmm"), ("😮", "wow verbaasd"), ("😢", "verdrietig sad"),
    ("😡", "boos angry"), ("🥳", "feest party"), ("😴", "slaap moe"),
    ("❤️", "hart liefde love rood"), ("💚", "hart groen"), ("💙", "hart blauw"),
    ("🔥", "vuur top fire"), ("⭐", "ster top star"), ("✨", "sprankel magie"),
    ("🎉", "feest party hoera"), ("🎊", "confetti"), ("✅", "check klaar done ok"), ("❌", "kruis fout nee"),
    ("⚠️", "waarschuwing let op warning"), ("❓", "vraag question"), ("❗", "uitroep belangrijk"),
    ("💡", "idee lamp insight"), ("🚀", "raket snel launch"), ("📈", "omhoog groei up"),
    ("📉", "omlaag daling down"), ("💰", "geld money"), ("⏰", "tijd klok deadline"), ("📌", "pin belangrijk"),
    ("🌱", "groei plant duurzaam"), ("🌍", "aarde wereld earth"), ("♻️", "recycle duurzaam"),
    ("👀", "kijk ogen"), ("🤖", "ai robot"), ("🙂", "glimlach"),
]


def _feed_entry_html(st: _Stores, entry: dict, role_name: str = "",
                     pid: str = "", csrf_token: str = "", mention_names=()) -> str:
    kind, atype, aid = _feed_norm(entry)
    av, nm = _feed_who(st, atype, aid)
    if atype == "role":
        who = f"<b class='fname'>@{_e(nm)}</b>"
    elif atype in ("person", "persona") and role_name:
        who = f"<b class='fname'>{_e(nm)}</b> <span class='frole'>@{_e(role_name)}</span>"
    else:
        who = f"<b class='fname'>{_e(nm)}</b>"
    rx = "".join(f"<span class='chip outline'>{emo} {cnt}</span>" for emo, cnt in (entry.get("reactions") or {}).items())
    picker = ""
    eid = entry.get("id")
    if csrf_token and eid:
        btns = "".join(
            f"<form method='post' action='/action' class='emo-f' data-k='{_e(kw)}' style='display:inline'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='pid' value='{_e(pid)}'>"
            f"<input type='hidden' name='item' value='{_e(eid)}'>"
            f"<input type='hidden' name='emoji' value='{emo}'>"
            f"<button class='emo' type='submit' name='action' value='react_add' title='{_e(kw)}'>{emo}</button></form>"
            for emo, kw in _EMOJIS_FULL)
        picker = (f"<details class='emoji-pick'><summary class='emoji-add' title='reactie' "
                  f"aria-label='reactie toevoegen'>{_ICON_ADD_EMOJI}</summary>"
                  f"<div class='emoji-pop'>"
                  f"<input class='emo-search' type='text' placeholder='Zoek emoji…' oninput='emoFilter(this)'>"
                  f"<div class='emo-grid'>{btns}</div></div></details>")
    bubble = _md(entry.get("text", ""))
    if mention_names:
        bubble = _hilite_mentions(bubble, mention_names)
    # Eigen comment (mens) is wijzigbaar/verwijderbaar.
    tools = ""
    if csrf_token and eid and atype == "human":
        hidf = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='item' value='{_e(eid)}'>")
        editd = (f"<details class='fedit'><summary class='flink'>Wijzigen</summary>"
                 f"<form method='post' action='/action' class='pf' style='margin-top:.3rem'>{hidf}"
                 f"<textarea name='text' rows='2'>{_e(entry.get('text', ''))}</textarea>"
                 f"<button class='btn ok sm' type='submit' name='action' value='feed_edit' "
                 f"style='margin-top:.3rem'>Opslaan</button></form></details>")
        deld = (f"<form method='post' action='/action' style='display:inline'>{hidf}"
                f"<button class='flink' type='submit' name='action' value='feed_remove' "
                f"onclick=\"return confirm('Comment verwijderen?')\">Verwijderen</button></form>")
        tools = f"<span class='fsep'>·</span>{editd}<span class='fsep'>·</span>{deld}"
    return (f"<div class='fentry'>"
            f"<div class='fhead'>{av}<span class='fwho'>{who}</span>"
            f"<span class='fstamp'>{_e(_stamp(entry.get('at')))}</span></div>"
            f"<div class='fbubble'>{bubble}</div>"
            f"<div class='ffoot'><div class='ffoot-l'>{rx}{picker}{tools}</div></div>"
            f"</div>")


def _feed_author_options(st: _Stores, p: dict) -> str:
    """Namens-keuze voor de composer: jij (reactie) + de rolvervullers van de eigenaar-rol (update)."""
    opts = ["<option value='human:'>🙋 Jij (reactie)</option>"]
    orec = st.records.get(p.get("owner"))
    if orec is not None:
        for f in st.assign.fillers_of(orec.id, record=orec):
            if f.type == "person":
                opts.append(f"<option value='person:{_e(f.id)}'>{_e(_person_name(st, f.id))} (update)</option>")
            else:
                pa = st.personas.get(f.id)
                opts.append(f"<option value='persona:{_e(f.id)}'>🤖 {_e(pa.name if pa else f.id)} (update)</option>")
    return "".join(opts)


def _ic(path: str) -> str:
    return (f"<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'>{path}</svg>")


_IC_DESC = _ic("<line x1='4' y1='7' x2='20' y2='7'/><line x1='4' y1='12' x2='20' y2='12'/>"
               "<line x1='4' y1='17' x2='14' y2='17'/>")
_IC_CHECK = _ic("<polyline points='9 11 12 14 20 6'/><path d='M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9'/>")
_IC_CHAT = _ic("<path d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/>")
_IC_INFO = _ic("<circle cx='12' cy='12' r='9'/><line x1='12' y1='11' x2='12' y2='16'/><line x1='12' y1='8' x2='12' y2='8'/>")
_IC_GEAR = _ic("<circle cx='12' cy='12' r='3'/><path d='M19 12a7 7 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6a7 7 0 0 0 .1-1z'/>")
_IC_LINK = _ic("<path d='M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1'/><path d='M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1'/>")
_IC_CLOCK = _ic("<circle cx='12' cy='12' r='9'/><polyline points='12 7 12 12 15 14'/>")
_IC_FILE = _ic("<path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><path d='M14 3v5h5'/>")
_IC_DL = _ic("<path d='M12 4v10'/><polyline points='8 11 12 15 16 11'/><line x1='5' y1='19' x2='19' y2='19'/>")


def _parse_multipart(body: bytes, boundary: str):
    """Minimale multipart/form-data parser → (velden{str:str}, bestanden{str:(filename,bytes)})."""
    fields, files = {}, {}
    delim = ("--" + boundary).encode()
    for part in body.split(delim):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        head, _, content = part.partition(b"\r\n\r\n")
        headers = head.decode("utf-8", "replace")
        mname = re.search(r'name="([^"]*)"', headers)
        if not mname:
            continue
        mfile = re.search(r'filename="([^"]*)"', headers)
        if mfile:
            files[mname.group(1)] = (mfile.group(1), content)
        else:
            fields[mname.group(1)] = content.decode("utf-8", "replace")
    return fields, files
_IC_TARGET = _ic("<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1.5'/>")


def _link_host(url: str) -> str:
    """Domeinnaam uit een URL als nette weergavenaam (zoals Trello bij een bijlage zonder titel)."""
    u = (url or "").split("//", 1)[-1]
    return u.split("/", 1)[0] or url


def _psec(icon: str, title: str, body: str) -> str:
    return (f"<div class='psec'><div class='psec-h'>{icon}<span>{_e(title)}</span></div>"
            f"<div class='psec-b'>{body}</div></div>")


def _checklists_html(p: dict, csrf: str, pid: str, back: str, rw: bool) -> str:
    """Named checklists (Trello-stijl): titel + voortgangsbalk + items + verwijderen."""
    def hid():
        nxt = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>")

    out = ""
    for cl in (p.get("checklists") or []):
        items = cl.get("items", [])
        done = sum(1 for it in items if it.get("done"))
        tot = len(items)
        pct = round(100 * done / tot) if tot else 0
        bar = (f"<div class='ck-prog'><div class='pbar' style='flex:1'><div style='width:{pct}%'></div></div>"
               f"<span class='muted'>{pct}% ({done}/{tot})</span></div>") if tot else ""
        rows = ""
        for it in items:
            d = it.get("done")
            clitem = (f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                      f"<input type='hidden' name='item' value='{_e(it['id'])}'>")
            chk = (f"<form method='post' action='/action' style='display:inline'>{hid()}{clitem}"
                   f"<button class='ck-box{' on' if d else ''}' type='submit' name='action' "
                   f"value='check_toggle'>{'✓' if d else ''}</button></form>") if rw else ("☑" if d else "☐")
            rm = (f"<form method='post' action='/action' style='display:inline'>{hid()}{clitem}"
                  f"<button class='dellink' type='submit' name='action' value='check_remove'>✕</button></form>") if rw else ""
            rows += f"<li class='ck-item'>{chk}<span class='{'ck-done' if d else ''}'>{_e(it['text'])}</span>{rm}</li>"
        add = (f"<form method='post' action='/action' class='ckadd'>{hid()}"
               f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
               f"<input name='text' placeholder='item toevoegen…'>"
               f"<button class='btn ok' type='submit' name='action' value='check_add'>+ item</button></form>") if rw else ""
        delc = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
                f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                f"<button class='dellink cl-del' type='submit' name='action' value='checklist_remove' "
                f"onclick=\"return confirm('Checklist verwijderen?')\">verwijderen</button></form>") if rw else ""
        out += (f"<div class='checklist'><div class='cl-head'>{_IC_CHECK}"
                f"<span class='cl-title'>{_e(cl.get('title', 'Checklist'))}</span>{delc}</div>"
                f"{bar}<ul class='clean ck-list'>{rows or '<li class=muted>nog geen items</li>'}</ul>{add}</div>")
    return out


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
        cur = st.defs.current(did) if did else None
        if cur:
            # catalogus-KPI: handmatig invoerbaar; herkomst bewaard als origin (geen live-feed)
            it = st.metrics.add_kpi(g("node"), cur.get("name"), cur.get("unit", ""),
                                    definition=cur.get("definition", ""), direction=cur.get("direction", ""),
                                    threshold=cur.get("threshold"), cadence=cur.get("cadence", "ad-hoc"),
                                    meettype=cur.get("meettype", "snapshot"), window=cur.get("window", ""),
                                    def_id=did, def_version=st.defs.current_version_no(did),
                                    origin=cur.get("source", ""),
                                    auto=cur.get("source", "") in _SYSTEM_SOURCES)
            msg = "✓ KPI uit catalogus toegevoegd" if it else "⛔ kon KPI niet toevoegen"
        else:
            msg = "⛔ kies een bestaande definitie uit de catalogus"
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
        parts = (g("combo") or "").split("|")
        if len(parts) == 3 and parts[0]:
            t = st.metrics.add_tile(g("node"), parts[0], parts[1], parts[2], g("form"),
                                    target=g("target"), goal_pid=g("goal_pid"))
            msg = "✓ tegel op dashboard" if t else "⛔ kon tegel niet maken"
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
