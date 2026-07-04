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
from nooch_village.attachments import AttachmentStore, ARTEFACT_KINDS
from nooch_village import artefacts
from nooch_village.artefacts import can_write_artefact, requires_governance_ref
from nooch_village.artefact_seen import SeenStore
from nooch_village.personas import PersonaStore
from nooch_village.projects import ProjectLedger
from nooch_village.ai_tasks import AITaskStore
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.metric_schema import (CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
                                         TIJD_LABEL, BRUIKBAAR_LABEL, VERIFICATIE_LABEL)
from nooch_village.definitions import (DefinitionStore, seed_catalog as _seed_catalog,
                                       reground_seed as _reground_seed)
from nooch_village.cockpit2_util import _BUILD, _EXTRA_CSS, _CIRCLE_TABS, _ROLE_TABS, WEBSITE_DEVELOPER_ROLE
from nooch_village.notifications import NotifStore
from nooch_village.noochie import NoochieStore
from nooch_village.roloverleg import Agenda
from nooch_village.werkoverleg import WerkoverlegStore, STEPS as _WO_STEPS
from nooch_village.strategy_store import StrategyStore
from nooch_village.backlog import BacklogStore
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
        self.seen = SeenStore(os.path.join(dd, "artefact_seen.json"))
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
        self.strategies = StrategyStore(os.path.join(dd, "strategies.json"))
        self.backlog = BacklogStore(os.path.join(dd, "backlog.json"))


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
    st.att.migrate()              # attachments → artefact-model (legacy tool-notes, defaults; idempotent)


from nooch_village.views.overview import (
    _filler_html, _members_of_circle, _tree_html,
    _ai_chip, _suggest_for_acc, _acc_row,
    _role_ai_overview, _overview_html, _fillsummary,
    _fillers_block, _role_row, _roles_html,
    _members_html, _att_html,
    render_node, render_person, render_patterns, render_admin,
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
    _person_projects_tab_html, render_project,
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


def _handle_person_add(data_dir: str, form: dict, username: str | None = None) -> tuple[str, int]:
    """Maak een persoon aan in people.json met een tijdelijk wachtwoord en toon dat éénmalig.

    Velden: voornaam, achternaam, email. Geeft (HTML-body, statuscode) terug (geen redirect),
    zodat het tijdelijke wachtwoord niet in een URL of browser-history terechtkomt.
    Autorisatie: alleen anchor-lead (people-beheer is org-breed); guest mag alles.
    """
    st = _Stores(data_dir)
    actor = st.people.by_email(username) if username != "guest" else None
    if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
        return "Geen toegang — alleen anchor-lead mag dit", 403
    if actor is None and username != "guest":
        return "Geen toegang — gebruiker niet herkend", 403
    g = lambda k: (form.get(k) or [""])[0].strip()
    voornaam, achternaam, email = g("voornaam"), g("achternaam"), g("email")
    back = g("next") or "/"
    if not back.startswith("/"):
        back = "/"
    naam = " ".join(p for p in (voornaam, achternaam) if p)
    if not naam or not email:
        body = ("<div class='c2-sec'><h3>Persoon toevoegen</h3>"
                "<p style='color:#c0392b'>Voornaam, achternaam én e-mailadres zijn verplicht.</p>"
                f"<p><a href='{_e(back)}'>← terug</a></p></div>")
        return _page("Persoon toevoegen", body), 200

    if st.people.by_email(email) is not None:
        body = ("<div class='c2-sec'><h3>Persoon toevoegen</h3>"
                f"<p style='color:#c0392b'>Er bestaat al een persoon met {_e(email)}.</p>"
                f"<p><a href='{_e(back)}'>← terug</a></p></div>")
        return _page("Persoon toevoegen", body), 200

    person = st.people.add(naam, email)
    temp = _auth.generate_temp_password()
    st.people.set_password(person.id, _auth.hash_password(temp))

    body = (
        "<div class='c2-sec'><h3>✓ Persoon toegevoegd</h3>"
        f"<p><b>{_e(person.name)}</b> — {_e(email)}</p>"
        "<p class='muted'>Geef dit tijdelijke wachtwoord door. Het wordt maar één keer getoond:</p>"
        f"<p style='font-size:1.4rem;font-family:monospace;background:#f4f1ec;"
        f"padding:.6rem 1rem;border-radius:6px;display:inline-block'>{_e(temp)}</p>"
        f"<p style='margin-top:1rem'><a href='{_e(back)}'>← terug</a></p></div>"
    )
    return _page("Persoon toegevoegd", body), 200


def _handle_person_reset(data_dir: str, form: dict, username: str | None = None) -> tuple[str, int]:
    """Reset het wachtwoord van een bestaande deelnemer: zet een nieuw tijdelijk wachtwoord en
    toon dat éénmalig (niet via redirect, zodat het niet in de URL/history belandt).
    Autorisatie: alleen anchor-lead (people-beheer is org-breed); guest mag alles."""
    st = _Stores(data_dir)
    actor = st.people.by_email(username) if username != "guest" else None
    if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
        return "Geen toegang — alleen anchor-lead mag dit", 403
    if actor is None and username != "guest":
        return "Geen toegang — gebruiker niet herkend", 403
    g = lambda k: (form.get(k) or [""])[0].strip()
    pid = g("pid")
    back = g("next") or "/admin"
    if not back.startswith("/"):
        back = "/admin"
    person = st.people.get(pid)
    if person is None:
        body = ("<div class='c2-sec'><h3>Wachtwoord resetten</h3>"
                "<p style='color:#c0392b'>Deelnemer niet gevonden.</p>"
                f"<p><a href='{_e(back)}'>← terug</a></p></div>")
        return _page("Wachtwoord resetten", body), 200
    temp = _auth.generate_temp_password()
    st.people.set_password(person.id, _auth.hash_password(temp))
    body = (
        "<div class='c2-sec'><h3>✓ Wachtwoord gereset</h3>"
        f"<p><b>{_e(person.name)}</b> — {_e(person.email)}</p>"
        "<p class='muted'>Geef dit tijdelijke wachtwoord door. Het wordt maar één keer getoond:</p>"
        f"<p style='font-size:1.4rem;font-family:monospace;background:#f4f1ec;"
        f"padding:.6rem 1rem;border-radius:6px;display:inline-block'>{_e(temp)}</p>"
        f"<p style='margin-top:1rem'><a href='{_e(back)}'>← terug</a></p></div>"
    )
    return _page("Wachtwoord gereset", body), 200


def is_circle_lead(person_id: str, circle_id: str, assignments) -> bool:
    """Geeft True als person_id filler is van {circle_id}__circle_lead."""
    if not person_id or not circle_id:
        return False
    role_id = f"{circle_id}__circle_lead"
    return any(f.type == "person" and f.id == person_id
               for f in assignments.fillers_of(role_id))


def is_role_filler(person_id: str, role_id: str, assignments) -> bool:
    """Geeft True als person_id een person-filler is van role_id."""
    if not person_id or not role_id:
        return False
    return any(f.type == "person" and f.id == person_id
               for f in assignments.fillers_of(role_id))


def resolve_circle_id(owner: str, records) -> str | None:
    """De cirkel van een project/metric/checklist-eigenaar, ongeacht de vorm van `owner`:
    een rol → zijn ouder-cirkel; een cirkel → zichzelf; een Individueel Initiatief
    ("ii:<circle>") → de cirkel uit de prefix. Onbekend/leeg → None."""
    if not owner:
        return None
    if owner.startswith(_II_PREFIX):
        return owner[len(_II_PREFIX):]
    rec = records.get(owner)
    if rec is None:
        return None
    return owner if org.is_circle(rec) else rec.parent


def is_circle_member(person_id: str, circle_id: str, records, assignments) -> bool:
    """True als person_id Circle Lead is van circle_id óf een rol vervult die in die
    cirkel hangt (parent == circle_id)."""
    if not person_id or not circle_id:
        return False
    if is_circle_lead(person_id, circle_id, assignments):
        return True
    return any(getattr(r, "parent", None) == circle_id
               and any(f.type == "person" and f.id == person_id
                       for f in assignments.fillers_of(r.id))
               for r in records.all())


def _role_gate(target: str, username: str | None, st) -> str | None:
    """Poort voor operationele takken. `target` = de eigenaar/node van het object
    (rol-id, cirkel-id of "ii:<circle>"). Geeft een foutmelding terug bij weigering,
    anders None (toegang). Regel: rolvervuller van de rol OF Circle Lead van de cirkel.
    "guest" (auth uit) mag alles; ingelogde-maar-onbekende wordt geweigerd."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "Geen toegang — gebruiker niet herkend"
    if (is_role_filler(actor.id, target, st.assign)
            or is_circle_lead(actor.id, resolve_circle_id(target, st.records), st.assign)):
        return None
    return "Geen toegang — alleen de rolvervuller of Circle Lead mag dit"


def _member_gate(circle_id: str, username: str | None, st) -> str | None:
    """Poort voor acties die elk lid van een cirkel mag doen (bv. een eigen Individueel
    Initiatief starten). Geeft een foutmelding terug bij weigering, anders None.
    "guest" mag alles; ingelogde-maar-onbekende wordt geweigerd."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "Geen toegang — gebruiker niet herkend"
    if is_circle_member(actor.id, circle_id, st.records, st.assign):
        return None
    return "Geen toegang — alleen leden van deze cirkel mogen dit"


def _wd_gate(username: str | None, st) -> str | None:
    """Poort voor het beheer van de Backlog Builder: alleen de rolvervuller van de Website
    Developer-rol. Foutmelding bij weigering, anders None. "guest" (auth uit) mag alles."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "Geen toegang — gebruiker niet herkend"
    if is_role_filler(actor.id, WEBSITE_DEVELOPER_ROLE, st.assign):
        return None
    return "Geen toegang — alleen de Website Developer mag de backlog beheren"


class Forbidden(Exception):
    """Een artefact-schrijfactie is geweigerd. `do_POST` vertaalt dit naar een echte HTTP 403 met
    de reden — i.p.v. de operationele 303-redirect met melding — zodat een client een expliciete
    weigering ziet en een ontbrekende governance_ref nooit een 500 wordt."""


def _web_actor_id(username: str | None, st) -> str:
    """Person-id van de ingelogde mens (voor de versie-/changelog-actor). "guest"/onbekend → ""."""
    if username in (None, "guest"):
        return ""
    actor = st.people.by_email(username)
    return actor.id if actor else ""


def _artefact_gate(owner_role_id: str, username: str | None, st) -> str | None:
    """Poort voor artefact-schrijfacties (add/edit/archive). Regel: rolvervuller van de eigenaar-rol
    OF Circle Lead van de omvattende cirkel — via `can_write_artefact`, dus identiek voor mens en
    (op de AI-weg) persona. Foutmelding bij weigering, anders None. "guest" (auth uit) mag alles."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "Geen toegang — gebruiker niet herkend"
    if can_write_artefact("person", actor.id, owner_role_id, st.records, st.assign):
        return None
    return "Geen toegang — alleen de rolvervuller of Circle Lead mag artefacten beheren"


def _lead_gate(circle_id: str, username: str | None, st) -> str | None:
    """Poort voor acties die alleen de Circle Lead van een cirkel mag (bv. een overleg
    openen/sluiten of de agenda-flow beheren). Foutmelding bij weigering, anders None.
    "guest" mag alles; ingelogde-maar-onbekende wordt geweigerd."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "Geen toegang — gebruiker niet herkend"
    if is_circle_lead(actor.id, circle_id, st.assign):
        return None
    return "Geen toegang — alleen Circle Lead mag dit"


# ── LiveKit-video: token-uitgifte ───────────────────────────────────────────
def maak_livekit_token(room: str, identity: str, naam: str) -> str:
    """Mint een LiveKit-access-token. ÉÉN plek voor de grants-config. Pakt LIVEKIT_API_KEY /
    LIVEKIT_API_SECRET automatisch uit de env. Lazy import zodat cockpit2 importeerbaar blijft
    zonder livekit-api (de token-tak faalt dan bewust closed, zie issue_livekit_token)."""
    from livekit import api
    from datetime import timedelta
    return (api.AccessToken()
            .with_identity(identity)
            .with_name(naam)
            .with_grants(api.VideoGrants(room_join=True, room=room))
            .with_ttl(timedelta(hours=2))
            .to_jwt())


def issue_livekit_token(st, circle: str, username: str | None):
    """Geef een LiveKit-token uit voor het lopende werkoverleg van `circle`. Geeft
    (status_code, payload) terug.

    HARDE REGEL: `room` en `identity` worden UITSLUITEND server-side bepaald — nooit uit de
    request-body. `circle` is de enige request-input en is (a) membership-gated via _member_gate
    en (b) enkel een lookup-sleutel naar de server-state. Deze functie accepteert dan ook geen
    room/identity-parameter, zodat een gemanipuleerde body ze onmogelijk kan zetten."""
    # AUTHZ: circle-member/rol-vervuller — hergebruikt _member_gate (dezelfde poort als
    # wo_presence/wo_ag_add). Rol-check vóór alles: geen rol in deze cirkel → geen token.
    deny = _member_gate(circle, username, st)
    if deny:
        return 403, {"error": deny}
    # ROOM: server bepaalt de room-naam uit de meeting-state, niet uit de request.
    m = st.werk.get(circle)
    if not m or m.get("status") != "open":
        return 409, {"error": "Geen lopend werkoverleg voor deze cirkel"}
    room = f"wo-{circle}-{int(m['started_at'])}"
    # IDENTITY: server bepaalt de rol-vervuller uit de authz-laag (de ingelogde sessie).
    actor = st.people.by_email(username) if username and username != "guest" else None
    if actor is None:
        return 403, {"error": "Geen herkende rol-vervuller"}
    server_url = os.getenv("LIVEKIT_URL", "").strip()
    if not server_url:
        return 503, {"error": "LiveKit niet geconfigureerd"}
    try:
        token = maak_livekit_token(room, actor.id, actor.name)
    except Exception as e:
        # De API-secret mag NOOIT lekken: alleen het exceptietype terug, geen details.
        return 500, {"error": f"token-generatie faalde ({type(e).__name__})"}
    return 200, {"token": token, "server_url": server_url}


def verwijder_livekit_room(room: str) -> bool:
    """Hef een LiveKit-room op (server-side, fail-soft). True bij succes, False als het niet lukt
    (geen creds, room al weg, netwerk) — NOOIT een exception naar de caller; het afronden van het
    overleg mag hier niet op stuklopen. De API-secret lekt niet (geen details in de return)."""
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url:
        return False
    api_url = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        import asyncio
        from livekit import api

        async def _run():
            lk = api.LiveKitAPI(api_url)          # api_key/secret uit de env
            try:
                await lk.room.delete_room(api.DeleteRoomRequest(room=room))
            finally:
                await lk.aclose()

        asyncio.run(_run())
        return True
    except Exception:
        return False


# Static-assets: whitelist (geen path-traversal). Nu alleen de gevendorde LiveKit-client-bundle.
_STATIC_TYPES = {"livekit-client.umd.min.js": "application/javascript; charset=utf-8"}


def role_context(st, role_id: str, fmt: str = "json"):
    """Serialiseer de volledige rol-context als (status, content_type, body).
    `fmt="markdown"` = de systeemprompt-bron voor AI-vervullers; anders JSON."""
    if not st.records.get(role_id):
        return 404, "text/plain; charset=utf-8", "Onbekende rol."
    ctx = artefacts.serialize_context(role_id, st.records, st.att)
    if fmt == "markdown":
        return 200, "text/markdown; charset=utf-8", artefacts.render_context_markdown(ctx)
    return 200, "application/json; charset=utf-8", json.dumps(ctx, ensure_ascii=False, indent=2)


def dispatch(data_dir: str, action: str, form: dict, username: str | None = None):
    """Verwerk een POST-actie. Geeft (redirect-URL, korte bevestiging) terug.

    `username` = e-mailadres van de ingelogde gebruiker (None = onbekend, "guest" = geen auth
    geconfigureerd). De rol-takken (role_assign/role_unassign/role_focus) dwingen autorisatie af:
    alleen de Circle Lead van de directe ouder-cirkel mag muteren. "guest" (auth uit) mag alles;
    een ingelogde maar onbekende gebruiker wordt geweigerd."""
    st = _Stores(data_dir)
    g = lambda k: (form.get(k) or [""])[0]
    nxt = g("next") or "/"
    if not nxt.startswith("/"):
        nxt = "/"
    pj = st.projects
    msg = ""
    if action == "proj_add":
        owner = g("owner")
        # Autorisatie: bij een rol → rolvervuller of Circle Lead; bij een Individueel
        # Initiatief (ii:<circle>) mag elk lid van die cirkel zijn eigen initiatief starten.
        _deny = (_member_gate(resolve_circle_id(owner, st.records), username, st)
                 if owner.startswith(_II_PREFIX)
                 else _role_gate(owner, username, st))
        if _deny:
            return nxt, _deny
        scope = g("scope").strip()
        person, agent = _parse_trekker(g("trekker"))
        col = g("col")
        create_status = "future" if col == "toekomst" else "queued"
        orec = st.records.get(owner)
        if orec is not None and org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: projecten horen bij een rol of Individueel Initiatief.
            return nxt, "✗ een cirkel kan geen project bevatten — kies een rol of Individueel Initiatief"
        if owner and scope:
            pid = pj.create(owner, scope[:200], "human", status=create_status,
                            person=person or None, agent=agent or None, private=(g("private") == "1"))
            if col == "wacht":
                pj.block(pid, "—")
            msg = "➕ project toegevoegd"
    elif action == "artefact_add":
        # AUTHZ: rolvervuller of Circle Lead — alleen de vervuller van de eigenaar-rol (of de Circle
        # Lead van de omvattende cirkel) mag artefacten binnen dat domein aanmaken; mens én AI gelijk.
        owner = g("owner")
        _deny = _artefact_gate(owner, username, st)          # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)                            # → HTTP 403, geen 303-redirect
        kind = g("kind")
        if kind not in ARTEFACT_KINDS:
            return nxt, "✗ onbekende artefact-soort"
        gref = g("governance_ref").strip()
        if requires_governance_ref(owner, st.records) and not gref:
            raise Forbidden("Anchor-cirkel: een schrijfactie vereist een governance_ref "
                            "(verwijzing naar het governance-besluit).")
        actor_id = _web_actor_id(username, st)
        a = st.att.add(owner, kind, title=g("title"), body=g("body"),
                       scope=g("scope"), url=g("url"), inherit=(g("inherit") != "0"),
                       actor_id=actor_id, actor_type="person",
                       governance_ref=gref, change_note="aangemaakt")
        if a is None:
            return nxt, "✗ artefact niet aangemaakt"
        artefacts.log_change(data_dir, action="add", artefact=a, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"➕ {kind} toegevoegd ({a.id})"
    elif action == "artefact_edit":
        # AUTHZ: rolvervuller of Circle Lead — bewerken mag alleen wie de eigenaar-rol vervult.
        cur = st.att.get(g("aid"))
        if cur is None:
            return nxt, "✗ artefact niet gevonden"
        _deny = _artefact_gate(cur.anchor, username, st)      # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)
        gref = g("governance_ref").strip()
        if requires_governance_ref(cur.anchor, st.records) and not gref:
            raise Forbidden("Anchor-cirkel: een wijziging vereist een governance_ref.")
        actor_id = _web_actor_id(username, st)
        upd = st.att.update(cur.id,
                            title=(g("title") if "title" in form else None),
                            body=(g("body") if "body" in form else None),
                            scope=(g("scope") if "scope" in form else None),
                            url=(g("url") if "url" in form else None),
                            inherit=(None if "inherit" not in form else (g("inherit") != "0")),
                            actor_id=actor_id, actor_type="person",
                            governance_ref=gref, change_note=(g("change_note") or "bewerkt"))
        artefacts.log_change(data_dir, action="edit", artefact=upd, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"✏️ {upd.kind} bijgewerkt ({upd.id})"
    elif action == "artefact_archive":
        # AUTHZ: rolvervuller of Circle Lead — archiveren (nooit hard delete) mag alleen de vervuller.
        cur = st.att.get(g("aid"))
        if cur is None:
            return nxt, "✗ artefact niet gevonden"
        _deny = _artefact_gate(cur.anchor, username, st)      # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)
        gref = g("governance_ref").strip()
        if requires_governance_ref(cur.anchor, st.records) and not gref:
            raise Forbidden("Anchor-cirkel: archiveren vereist een governance_ref.")
        actor_id = _web_actor_id(username, st)
        arch = st.att.archive(cur.id, actor_id=actor_id, actor_type="person",
                              governance_ref=gref, change_note="gearchiveerd")
        artefacts.log_change(data_dir, action="archive", artefact=arch, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"🗄️ {arch.kind} gearchiveerd ({arch.id})"
    elif action == "proj_status":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
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
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.complete(g("pid")); msg = "✓ afgerond"
    elif action == "proj_archive":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.archive(g("pid")); msg = "🗄 gearchiveerd (blijft bestaan)"
    elif action == "proj_unarchive":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.unarchive(g("pid")); msg = "↩ hersteld"
    elif action == "proj_delete":
        # ── Autorisatie: Circle Lead van de cirkel van het project ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = resolve_circle_id((pj.get(g("pid")) or {}).get("owner") or "", st.records)
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        pj.remove(g("pid")); msg = "🗑 verwijderd"
    elif action == "proj_edit":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        person, agent = _parse_trekker(g("trekker"))
        pj.edit(g("pid"), scope=g("scope"), person=person, agent=agent,
                private=(g("private") == "1"), description=g("description"), label=g("label"))
        msg = "💾 opgeslagen"
    elif action == "proj_comment":
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.add_comment(g("pid"), g("comment")):
            msg = "💬 geplaatst"
    elif action == "proj_rename":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), scope=g("scope"), allow_done=True):
            msg = "✓ titel opgeslagen"
    elif action == "proj_describe":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), description=g("description"), allow_done=True):
            msg = "✓ omschrijving opgeslagen"
    elif action == "proj_settrekker":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        person, agent = _parse_trekker(g("trekker"))
        if pj.edit(g("pid"), person=person, agent=agent, allow_done=True):
            msg = "✓ trekker opgeslagen"
    elif action == "proj_setowner":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        owner = g("owner")
        orec = st.records.get(owner)
        if orec is None:
            msg = "✗ onbekende rol"
        elif org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: een project hoort bij een rol.
            msg = "✗ een cirkel kan geen project bevatten — kies een rol"
        elif pj.edit(g("pid"), owner=owner, allow_done=True):
            msg = "✓ rol verplaatst"
    elif action == "proj_approve":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.approve(g("pid")):
            msg = "✓ concept goedgekeurd — staat nu op het bord"
    elif action == "proj_discard":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.discard(g("pid")):
            msg = "🗑 concept verworpen"
    elif action == "proj_setlabel":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), label=g("label"), allow_done=True):
            msg = "✓ label opgeslagen"
    elif action == "proj_setprivate":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), private=(g("private") == "1"), allow_done=True):
            msg = "✓ zichtbaarheid opgeslagen"
    elif action == "proj_setdue":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.set_due(g("pid"), g("due")):
            msg = "📅 datum opgeslagen" if g("due") else "✓ datum verwijderd"
    elif action == "attach_add":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.attach_add(g("pid"), url=g("url"), title=g("title")):
            msg = "🔗 bijlage toegevoegd"
    elif action == "attach_remove":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.attach_remove(g("pid"), g("aid")); msg = "🗑 bijlage verwijderd"
    elif action == "react_add":
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.add_reaction(g("pid"), g("item"), g("emoji")):
            msg = "✓ reactie geplaatst"
    elif action == "feed_edit":
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.feed_edit(g("pid"), g("item"), g("text")):
            msg = "✓ comment gewijzigd"
    elif action == "feed_remove":
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        pj.feed_remove(g("pid"), g("item")); msg = "🗑 comment verwijderd"
    elif action == "ai_reply":
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        _load_env()
        msg = ("🤖 AI heeft meegedacht" if _ai_reply(st, g("pid"))
               else "geen AI-antwoord (geen AI-inwoner op de rol of geen LLM-key)")
    elif action == "proj_feed":
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
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
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.checklist_add(g("pid"), g("title")):
            msg = "✓ checklist toegevoegd"
    elif action == "checklist_remove":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.checklist_remove(g("pid"), g("clid")); msg = "🗑 checklist verwijderd"
    elif action == "check_add":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.check_add(g("pid"), g("clid"), g("text")):
            msg = "✓ item toegevoegd"
    elif action == "check_toggle":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.check_toggle(g("pid"), g("clid"), g("item"))
    elif action == "check_remove":
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.check_remove(g("pid"), g("clid"), g("item")); msg = "🗑 item verwijderd"
    elif action == "role_assign":
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        person, agent = _parse_trekker(g("filler"))
        if person and st.assign.assign(g("role"), "person", person):
            msg = "✓ toegewezen"
        elif agent and st.assign.assign(g("role"), "persona", agent):
            msg = "🤖 AI toegewezen"
    elif action == "role_unassign":
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.unassign(g("role"), "person", person)
        elif agent:
            st.assign.unassign(g("role"), "persona", agent)
        msg = "✓ verwijderd"
    elif action == "role_focus":
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.set_focus(g("role"), "person", person, g("focus"))
        elif agent:
            st.assign.set_focus(g("role"), "persona", agent, g("focus"))
        msg = "✓ focus opgeslagen"
    elif action == "aitask_add":
        # ── Autorisatie: Circle Lead van de directe ouder-cirkel ──
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag AI-taken koppelen"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
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
        # ── Autorisatie: Circle Lead van de ouder-cirkel van de rol ──
        actor = st.people.by_email(username) if username != "guest" else None
        _task = next((t for t in st.ai.all() if t.id == g("tid")), None)
        _rec = st.records.get(_task.role) if _task else None
        circle_id = _rec.parent if _rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        st.ai.remove(g("tid")); msg = "✓ verwijderd"
    elif action == "persona_skill_add":
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag persona-skills toevoegen"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        if st.personas.add_skill(g("agent"), g("skill")):
            msg = "✓ skill aan rugzak toegevoegd"
    elif action == "rov2_add":
        # Autorisatie: elk cirkellid mag een voorstel op de agenda brengen
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if _rov_add_item(st, g("circle"), g("naam")):
            msg = "✓ agendapunt toegevoegd"
    elif action == "rov2_add_to_group":
        # Autorisatie: elk cirkellid mag aan een voorstel bijdragen
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if _rov_add_item(st, g("circle"), g("naam"), group=g("group")):
            msg = "✓ toegevoegd aan voorstel"
    elif action == "rov2_remove":
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        st.agenda.remove(g("iid")); msg = "🗑 uit voorstel verwijderd"
    elif action == "rov2_remove_group":
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        gid = st.agenda.group_of(g("iid"))
        for m in st.agenda.members_of_group(gid):
            st.agenda.remove(m["id"])
        msg = "🗑 voorstel verwijderd"
    elif action == "rov2_setkind":
        # Autorisatie: cirkellid mag het type van zijn eigen voorstel vormgeven
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("kind") in ("amend_role", "remove_role"):
            st.agenda.update_fields(g("iid"), kind=g("kind"))
            msg = "voorstel: rol verwijderen" if g("kind") == "remove_role" else "voorstel: rol wijzigen"
    elif action == "rov2_consent":
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        gid = st.agenda.group_of(g("iid"))
        members = st.agenda.members_of_group(gid)
        if members and not any(_rov_hard(st, m) for m in members):
            for m in members:
                st.agenda.set_status(m["id"], "consented")
            msg = "✓ consent — voorstel aangenomen"
        else:
            msg = "⛔ consent geblokkeerd — los de blokkade(s) op"
    elif action == "rov2_end":
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        done = _rov_apply(st)
        msg = f"✓ overleg gesloten — {len(done)} doorgevoerd" if done else "overleg gesloten"
    elif action == "wo_open":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.open(g("circle")); msg = "✓ werkoverleg gestart"
    elif action == "wo_close":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        # Room-naam vóór het sluiten bepalen (started_at is dan nog beschikbaar), dan sluiten,
        # dan de LiveKit-room opheffen — fail-soft: het afronden mag hier niet op stuklopen.
        _m = st.werk.get(g("circle"))
        _room = f"wo-{g('circle')}-{int(_m['started_at'])}" if _m and _m.get("started_at") else None
        st.werk.close(g("circle"))
        if _room:
            verwijder_livekit_room(_room)
        msg = "✓ werkoverleg gesloten"
    elif action == "wo_presence":
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.set_presence(g("circle"), g("pid"), g("present") == "1")
        msg = "✓ aanwezig" if g("present") == "1" else "✗ afwezig (taken gepauzeerd)"
    elif action == "wo_present_all":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        for p in _members_of_circle(st, g("circle")):
            st.werk.set_presence(g("circle"), p.id, True)
        msg = "✓ allen aanwezig"
    elif action == "wo_ag_add":
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        naam, by = _rov_initials(g("naam"))
        if st.werk.agenda_add(g("circle"), naam, by=by):
            msg = "✓ spanning op de agenda"
    elif action == "wo_ag_remove":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.agenda_remove(g("circle"), g("iid")); msg = "🗑 verwijderd"
    elif action == "wo_ag_note":
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("field") in ("spanning", "role", "need"):
            st.werk.agenda_set_note(g("circle"), g("iid"), **{g("field"): g("value")})
            msg = "✓ genoteerd"
    elif action == "wo_ag_reopen":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        it = st.werk.agenda_get(g("circle"), g("iid"))
        if it is not None:
            it["status"] = "open"; it["outcome"] = None; st.werk._save()
            msg = "↺ heropend"
    elif action == "wo_ag_resolve":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
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
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("score"):
            st.werk.set_checkout(g("circle"), g("pid"), g("score")); msg = "✓ score genoteerd"
    elif action == "noochie_send":
        # noochie_* (send/reset/ctx) BEWUST ongated: de assistent-chat mag elke ingelogde
        # gebruiker gebruiken (sessie-check in do_POST dekt "ingelogd = mag").
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
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
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
        # AUTHZ: rolvervuller of Circle Lead van de betrokken rol/cirkel — afvinken van een
        # checklist-item (namens de rol/cirkel bij target_type=all). by = wie afvinkte (de mens;
        # een AI-flow kan report() direct met by=<persona> aanroepen). Geen per-individu-verplichting.
        _deny = _role_gate((st.checklists.get(g("cid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        if st.checklists.report(g("cid"), g("ok") == "1", value=g("value"),
                                by=(username or "founder")):
            msg = "✓ genoteerd" if g("ok") == "1" else "✗ genoteerd (aandacht nodig)"
    elif action == "cl_remove":
        _deny = _role_gate((st.checklists.get(g("cid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        st.checklists.remove(g("cid")); msg = "🗑 checklist-item verwijderd"
    elif action == "m_add_kpi":
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
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
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        did = g("def_id")
        if not did and g("def_name"):
            d = st.defs.by_name(g("def_name"))
            did = d["id"] if d else ""
        kid = _kpi_id_from_def(st, g("node"), did)
        msg = "✓ KPI uit catalogus toegevoegd" if kid else "⛔ kies een bestaande definitie uit de catalogus"
    elif action == "def_add":
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
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
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
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
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        it = st.metrics.add_link(g("node"), g("name"), g("url"))
        msg = "✓ link toegevoegd" if it else "⛔ geef naam en URL"
    elif action == "m_sample":
        _deny = _role_gate((st.metrics.get(g("mid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        msg = "✓ meting genoteerd" if st.metrics.add_sample(g("mid"), g("value")) else "⛔ ongeldige meting"
    elif action == "m_remove":
        _deny = _role_gate((st.metrics.get(g("mid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        st.metrics.remove(g("mid")); msg = "🗑 metric verwijderd"
    elif action == "m_pin":
        # Autorisatie: het cirkeldashboard beheren is Circle Lead-werk
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.pin(g("circle"), g("mid")); msg = "✓ op cirkeldashboard"
    elif action == "m_unpin":
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.unpin(g("circle"), g("mid")); msg = "✓ van dashboard gehaald"
    elif action == "tile_add":
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
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
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.remove_tile(g("node"), g("tid")); msg = "🗑 tegel verwijderd"
    elif action in ("rov2_set", "rov2_acc_add", "rov2_acc_remove", "rov2_dom_add", "rov2_dom_remove"):
        # Autorisatie: cirkellid mag zijn eigen voorstel vormgeven
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
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
    elif action == "backlog_add":
        # AUTHZ: iedereen-ingelogd — elke ingelogde gebruiker mag een backlog-item indienen
        # (de sessie-check in do_POST dekt "ingelogd = mag"; guest = auth uit = mag ook)
        actor = st.people.by_email(username) if username != "guest" else None
        if st.backlog.add(g("titel"), g("beschrijving"), g("type"), g("domein"),
                          actor.id if actor else ""):
            msg = "✓ ingediend in de backlog"
    elif action == "backlog_update_staat":
        # AUTHZ: rolvervuller website_developer — beheer van de backlog (staat verplaatsen)
        _deny = _wd_gate(username, st)
        if _deny:
            return nxt, _deny
        if st.backlog.update_staat(g("bid"), g("staat")):
            msg = "✓ staat bijgewerkt"
    elif action == "backlog_update_prioriteit":
        # AUTHZ: rolvervuller website_developer — beheer van de backlog (impact/effort)
        _deny = _wd_gate(username, st)
        if _deny:
            return nxt, _deny
        if st.backlog.update_prioriteit(g("bid"), g("impact"), g("effort")):
            msg = "✓ prioriteit bijgewerkt"
    elif action == "person_edit":
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        if st.people.update(g("pid"), name=g("name"), email=g("email")):
            msg = "✓ deelnemer opgeslagen"
        else:
            msg = "✗ deelnemer niet gevonden"
    elif action == "person_remove":
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        pid = g("pid")
        # ruim ook de rol-toewijzingen op, anders blijven die als wees achter
        for rid in list(st.assign.roles_of("person", pid)):
            st.assign.unassign(rid, "person", pid)
        if st.people.remove(pid):
            msg = "🗑 deelnemer verwijderd"
        else:
            msg = "✗ deelnemer niet gevonden"
    return nxt, msg


# Niets is publiek: een uitgelogde bezoeker gaat overal naar /login. /login en /logout worden in
# do_GET vóór de auth-check afgehandeld en blijven dus bereikbaar. Er is geen asset/health-route die
# publiek moet blijven (/file staat al achter de auth-check).
_PUBLIC_GET: set[str] = set()


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
            # Globale Noochie-chrome alleen voor een sessie (ingelogd, of "guest" bij auth-uit) —
            # niet op de login-pagina of bij een uitgelogde bezoeker.
            if self._session_username() is not None and "</body>" in body:
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

        def _send_json(self, payload: dict, code: int = 200):
            b = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

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
            if path == "/context":
                # AUTHZ: iedereen-ingelogd — rol-context is dezelfde read-scope als /node?tab=notes
                # (één rol), dus in auth-uit óók voor guest zichtbaar; alleen de persoon-context-
                # aggregatie blijft gated (besluit 2026-07-03). De login-redirect hierboven dekt de
                # niet-ingelogde gebruiker al af.
                # OPEN PUNT (niet nu): geen read-scope-per-rol. Elke ingelogde gebruiker (+ guest in
                # auth-uit) leest élke rol-context. Nu ongevaarlijk (geen artefacten; anchor-policies
                # zijn publieke missieprincipes), maar zodra rollen gevoelige policies/notes krijgen
                # (business-model, leveranciers-afspraken) is een per-rol read-scope nodig.
                status, ctype, body = role_context(st, (qs.get("id") or [""])[0],
                                                    (qs.get("format") or ["json"])[0])
                b = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
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
                nid = (qs.get("id") or [""])[0]
                ntab = (qs.get("tab") or ["overview"])[0]
                if ntab in ("policies", "notes", "tools"):
                    st.seen.mark(username, nid, ntab)   # last_seen bij openen → seen-markering weg
                self._send(render_node(st, nid, ntab, csrf_token=effective_csrf,
                                       msg=(qs.get("msg") or [""])[0],
                                       group=(qs.get("group") or [""])[0],
                                       clf=(qs.get("clf") or ["due"])[0],
                                       mw=(qs.get("mw") or ["maand"])[0],
                                       username=username))
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
                self._send(render_person(st, (qs.get("id") or [""])[0],
                                         tab=(qs.get("tab") or ["rollen"])[0],
                                         username=username, csrf_token=effective_csrf))
                return
            if path == "/admin":
                self._send(render_admin(st, csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0]))
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
            if path == "/livekit-token":
                # Alleen `circle` uit de request; room + identity bepaalt de server zelf
                # (zie issue_livekit_token). AUTHZ zit in die functie via _member_gate.
                status, payload = issue_livekit_token(st, (qs.get("circle") or [""])[0], username)
                self._send_json(payload, status)
                return
            if path.startswith("/static/"):
                name = path[len("/static/"):]
                ct = _STATIC_TYPES.get(name)                 # whitelist → geen path-traversal
                if ct is None:
                    self._send("Niet gevonden", 404); return
                try:
                    with open(os.path.join(os.path.dirname(__file__), "static", name), "rb") as _f:
                        _data = _f.read()
                except OSError:
                    self._send("Niet gevonden", 404); return
                self._send_bytes(_data, ct); return
            if path == "/roloverleg2":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_roloverleg2(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("iid") or [""])[0],
                                                    csrf_token=effective_csrf, fragment=fr), fr))
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
                email    = (form.get("email") or [""])[0].strip()
                password = (form.get("password") or [""])[0]
                next_url = (form.get("next") or ["/"])[0]
                if users and users.verify_by_email(email, password):
                    _Stores(data_dir).people.touch_login(email)
                    token = sessions.create(email) if sessions else ""
                    self._redirect_to(next_url or "/", _auth.set_cookie(token))
                else:
                    self._send(_auth.login_page(next_url, error="E-mailadres of wachtwoord onjuist."))
                return

            if path != "/action":
                self._send("<p>404</p>", 404); return

            # ── Sessie-check voor alle /action POSTs ────────────────────────
            username = self._session_username()
            if sessions is not None and username is None:
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
            # person_add: rendert een pagina die het tijdelijke wachtwoord éénmalig toont
            # (niet via redirect, zodat het wachtwoord niet in de URL/history belandt).
            if action == "person_add":
                self._send(*_handle_person_add(data_dir, form, username=username))
                return
            if action == "person_reset_password":
                self._send(*_handle_person_reset(data_dir, form, username=username))
                return
            try:
                nxt, msg = dispatch(data_dir, action, form, username=username)
            except Forbidden as e:
                self._send(str(e), 403); return    # geweigerde artefact-mutatie → echte 403 + reden
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
    users    = _auth.UserStore(os.path.join(dd, "people.json"))
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
    _rov_signals, _rov_dupes, _rov_apply,
    _rov_draft, _rov_snapshot, _rov_save_draft,
    _rov_member_block, _rov_editor,
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
