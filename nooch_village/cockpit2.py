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

from nooch_village import auth as _auth
from nooch_village.cockpit import _e, _page, _banner     # zelfde design system
from nooch_village.cockpit2_util import (
    _name, _initials, _tabbar, _todo, _avatar, _age, _fmt_due,
    _created_full, _ic, _bron_html, _stamp, _md, _parse_multipart,
    _link_host, _psec, _ICON_ADD_EMOJI, _person_name,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK, _IC_DL,
    _IC_DESC, _IC_CLOCK, _IC_FILE, _IC_TARGET,
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
from nooch_village.cockpit2_util import _BUILD, _EXTRA_CSS, _CIRCLE_TABS, _ROLE_TABS
from nooch_village.notifications import NotifStore
from nooch_village.noochie import NoochieStore
from nooch_village.roloverleg import Agenda
from nooch_village.werkoverleg import WerkoverlegStore, STEPS as _WO_STEPS
from nooch_village import ai_match
from nooch_village import org
from nooch_village.glassfrog_import import import_org, nooch_poc_org

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}





def _default_data_dir() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "data")


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


from nooch_village.views.overview import (
    _filler_html, _members_of_circle, _tree_html,
    _ai_chip, _suggest_for_acc, _acc_row,
    _role_ai_overview, _overview_html, _fillsummary,
    _fillers_block, _role_row, _roles_html,
    _members_html, _att_html,
    render_node, render_person, render_patterns,
    render_rolefillers, render_aitask,
    _CORE_ROLE_NAMES, _ICON_ADD_PERSON,
)



from nooch_village.views.projects import (
    _proj_chip, _trekker_html, _trekker_options,
    _proj_progress, _due_overdue, _progress_badge,
    _scope_text, _proj_card, _quickadd,
    _inline_add_project, _columns_html, _drag_script,
    _modal_html, _group_meta, _projects_board,
    _archived_html, _projects_tab_html,
    _person_projects_html, render_project,
    _PROJ_CHIP, _PROJ_COLS, _LABELS, _II_PREFIX,
)


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


from nooch_village.views.noochie import (
    _noochie_suggest, _noochie_reply,
    render_noochie, _noochie_chrome,
)

from nooch_village.views.werkoverleg import (
    _wo_hid, _wo_checkin, _wo_checklist, _wo_metrics,
    _wo_spanning_add, _wo_spanning_items, _wo_triage,
    _wo_checkout, _wo_summary, render_werkoverleg,
)


_IC_GEAR = _ic("<circle cx='12' cy='12' r='3'/><path d='M19 12a7 7 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6a7 7 0 0 0 .1-1z'/>")




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


_PUBLIC_GET = {"/", "/index.html", "/node"}


def make_handler(data_dir: str, csrf_token: str,
                 sessions: "_auth.SessionStore | None" = None,
                 users: "_auth.UserStore | None" = None):
    class H(BaseHTTPRequestHandler):
        def _session_username(self) -> str | None:
            if sessions is None:
                return "guest"
            token = _auth.get_session_token(self.headers)
            return sessions.get_username(token) if token else None

        def _redirect_to(self, location: str, cookie: str | None = None) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()

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

            # ── Login / logout ──────────────────────────────────────────────
            if path == "/login":
                next_url = (qs.get("next") or ["/"])[0]
                self._send(_auth.login_page(next_url))
                return
            if path == "/logout":
                token = _auth.get_session_token(self.headers)
                if token and sessions:
                    sessions.delete(token)
                self._redirect_to("/login", _auth.clear_cookie())
                return

            # ── Auth-check voor niet-publieke GETs ─────────────────────────
            username = self._session_username()
            if username is None and path not in _PUBLIC_GET:
                self._redirect_to(f"/login?next={urllib.parse.quote(self.path)}")
                return

            # Publieke views krijgen geen CSRF-token → geen schrijfknoppen
            effective_csrf = csrf_token if username else ""

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
                                       (qs.get("tab") or ["overview"])[0], csrf_token=effective_csrf,
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
                self._send(_frag(render_project(st, (qs.get("pid") or [""])[0], csrf_token=effective_csrf,
                                                msg=(qs.get("msg") or [""])[0],
                                                back=(qs.get("back") or ["/"])[0], fragment=fr), fr))
                return
            if path == "/rolefillers":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_rolefillers(st, (qs.get("role") or [""])[0],
                                                    csrf_token=effective_csrf, fragment=fr), fr))
                return
            if path == "/aitask":
                try:
                    acc_i = int((qs.get("acc") or ["-1"])[0])
                except ValueError:
                    acc_i = -1
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_aitask(st, (qs.get("role") or [""])[0], acc_i,
                                               csrf_token=effective_csrf, fragment=fr), fr))
                return
            if path == "/person":
                self._send(render_person(st, (qs.get("id") or [""])[0]))
                return
            if path == "/_patterns":
                self._send(render_patterns(effective_csrf))
                return
            if path == "/catalog":
                self._send(render_catalog(st, csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/kpi_new":
                self._send(render_kpi_composer(st, (qs.get("node") or [""])[0],
                                               csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/noochie":
                self._send(render_noochie(st, effective_csrf, (qs.get("ctx") or [""])[0]))
                return
            if path == "/werkoverleg":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_werkoverleg(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("step") or ["checkin"])[0],
                                                    csrf_token=effective_csrf, fragment=fr,
                                                    iid=(qs.get("iid") or [""])[0],
                                                    kpi=(qs.get("kpi") or [""])[0],
                                                    mw=(qs.get("mw") or ["maand"])[0]), fr))
                return
            if path == "/roloverleg2":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_roloverleg2(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("iid") or [""])[0],
                                                    csrf_token=effective_csrf, fragment=fr,
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
            path = self.path.split("?", 1)[0]
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length") or 0)

            # ── Login POST ──────────────────────────────────────────────────
            if path == "/login":
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                username = (form.get("username") or [""])[0].strip()
                password = (form.get("password") or [""])[0]
                next_url = (form.get("next") or ["/"])[0]
                if users and users.verify(username, password):
                    token = sessions.create(username) if sessions else ""
                    self._redirect_to(next_url or "/", _auth.set_cookie(token))
                else:
                    self._send(_auth.login_page(next_url, error="Gebruikersnaam of wachtwoord onjuist."))
                return

            if path != "/action":
                self._send("<p>404</p>", 404); return

            # ── Sessie-check voor alle /action POSTs ────────────────────────
            if sessions is not None and self._session_username() is None:
                self._send("Niet ingelogd", 403); return
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
    users    = _auth.UserStore(os.path.join(dd, "users.json"))
    sessions = _auth.SessionStore()
    httpd = ThreadingHTTPServer((host, port), make_handler(dd, csrf_token, sessions, users))
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
