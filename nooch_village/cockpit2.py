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
import logging
import mimetypes
import os
import re
import time
import secrets
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nooch_village import auth as _auth
from nooch_village import claims_db as _claims_db
from nooch_village.web_base import _e, _page, _banner     # zelfde design system
from nooch_village.cockpit2_util import (
    _name, _initials, _tabbar, _avatar, _age, _fmt_due,
    _created_full, _ic, _bron_html, _stamp, _md, _parse_multipart,
    _link_host, _psec, _ICON_ADD_EMOJI, _person_name,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK, _IC_DL,
    _IC_DESC, _IC_CLOCK, _IC_FILE, _IC_TARGET,
)
from nooch_village.views.feed import (
    _feed_norm, _feed_who, _mentionables, _mentions_in,
    _hilite_mentions, _feed_entry_html, _feed_author_options,
    _wall_outcome_opts,
)
from nooch_village.governance import Records
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore, ARTEFACT_KINDS
from nooch_village.observations import ObservationStore
from nooch_village import observations
from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village import snake
from nooch_village.source_status import SourceStatusStore
from nooch_village.collector import migrate_data_sources
from nooch_village import artefacts
from nooch_village.artefacts import can_write_artefact, requires_governance_ref
from nooch_village import epic
from nooch_village.personas import PersonaStore
from nooch_village.projects import ProjectLedger, PREP_CHECKLIST_TITLE, _MISSIE_IMPACT, _BUSINESS_IMPACT
from nooch_village.deliverable_store import DeliverableStore
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.radar_store import RadarStore
from nooch_village.registry_factory import shared_registry
from nooch_village.skill_match import plan_offers
from nooch_village.util import refuse
from nooch_village.ai_tasks import AITaskStore
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.kennisbank import (KennisbankStore, parse_blok,
                                      field as kb_field, verdict as kb_verdict,
                                      WORD_LABEL as KB_WORD_LABEL,
                                      load_atoms as kb_load_atoms)
from nooch_village.kennisbank_intake import SUBJECTS as KB_SUBJECTS, intake as kb_intake
from nooch_village.kennisbank_spel import SpelStore, spel_finish
from nooch_village.kennisbank_staging import StagingStore, commit_batch
from nooch_village.views.kennisbank_staging import render_kennisbank_staging
from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight
from nooch_village.metric_schema import (CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
                                         TIJD_LABEL, BRUIKBAAR_LABEL, VERIFICATIE_LABEL)
from nooch_village.definitions import (DefinitionStore, seed_catalog as _seed_catalog,
                                       reground_seed as _reground_seed,
                                       migrate_definitions as _migrate_definitions)
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
        self.observations = ObservationStore(os.path.join(dd, "observations.jsonl"))
        self.evidence = EvidenceLedger(os.path.join(dd, "evidence_ledger.jsonl"))   # De Kroniek — bewijsregister
        self.sources = SourceStatusStore(os.path.join(dd, "sources.json"))
        self.personas = PersonaStore(os.path.join(dd, "personas.json"))
        self.projects = ProjectLedger(os.path.join(dd, "projects.json"))
        self.deliverables = DeliverableStore(os.path.join(dd, "deliverables.json"))
        self.project_docs = ProjectDocStore(dd)   # levend einddocument per project (weergave + edit-route)
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
        self.radar = RadarStore(os.path.join(dd, "radar.json"))   # Radar-tool: gecureerde Inoreader-signalen per rol
        self.kennisbank = KennisbankStore(os.path.join(dd, "kennisbank.json"))   # laag 2: geversioneerde inzichten
        self.notes = NotesStore(os.path.join(dd, "notes.json"))   # laag 1: de atomen-bibliotheek (kennislaag)
        self.spel = SpelStore(os.path.join(dd, "kennisbank_spel.json"))   # fase 3: inzicht-dialogen
        self.staging = StagingStore(os.path.join(dd, "kennisbank_staging.json"))   # zone 2: even-nakijken
        self.library = Library(os.path.join(dd, "library.json"))   # beschermde woordenschat (Lara cureert)
        self.nominations = NominationQueue(os.path.join(dd, "keyword_nominaties.json"))   # fase 4: pending-queue
        self.nom_kroniek = NominationKroniek(os.path.join(dd, "keyword_nominaties.jsonl"))   # fase 4: beslissings-Kroniek


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
    """Idempotent: het wekelijkse checklist-item dat transparantie operationeel checkt. De
    transparantie-POLICY zelf is in fase 2 uit de policy-lijst gehaald (was eerder een note);
    de cadans blijft via dit checklist-item. Voegt GEEN string meer toe aan definition.policies."""
    roots = org.roots(st.records.all())
    root = roots[0] if roots else None
    if root is None:
        return
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
    _migrate_definitions(st.defs)  # nieuwe verplichte velden (aard/aggregatie/formule) retroactief (idempotent)
    st.att.migrate()              # attachments → artefact-model (legacy tool-notes, defaults; idempotent)
    migrate_data_sources(dd)      # legacy visitors_day → plausible_visitors_day + Plausible actief (idempotent)
    st.metrics.migrate_metric_bindings(st.defs)   # wees-KPI's: veld/categorie uit de def + reeks-tegel-dim (idempotent)
    # OpenAlex: alle oude CUMULATIEVE concept-reeksen (openalex_works_day/citations_day, incl. ::concept)
    # weg; alleen de nieuwe 90/30-FLOW (openalex_works_90d::…) blijft. Verworpen meetopzet (bevroren
    # aggregaat), vóór meetstart. Idempotent.
    st.observations.remove_bron("openalex", keep_prefix="openalex_works_90d")
    # Trends: de Library-anker-reeksen (verworpen ontwerp, vóór meetstart) weg; alleen de nieuwe
    # stemming-paar-reeksen (trends_ratio_*) blijven. Idempotent. Zie de meetverantwoording in docs/.
    st.observations.remove_bron("trends", keep_prefix="trends_ratio_")
    # Belofte-graaf: zet eenmalig de schoen-ontleding uit de aangeleverde BOM (idempotent;
    # overschrijft gedane grondingen niet).
    from nooch_village.belofte_store import BelofteStore, seed_schoen_graaf
    seed_schoen_graaf(BelofteStore(os.path.join(dd, "belofte_grafen.json")))


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
    _render_bullet, _data_table, _render_burnup,
    _render_form, _grondslag, _grondslag_popover, _llm_says_comparable,
    _render_tile, _kpi_id_from_def, _goal_options, _metric_csv, _default_form,
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
from nooch_village.views.signals import render_signals
from nooch_village.views.inbox import (
    render_inbox, render_verwerk, render_inbox_frag, render_inbox_chrome, _person_role_options,
)
from nooch_village.views.metrics2 import render_metrics2
from nooch_village.views.bronnen import render_bronnen
from nooch_village.views.kennislaag import render_kennislaag
from nooch_village.views.kennisbank import render_kennisbank, render_kennisbank_search
from nooch_village.views.kennisbank_spel import render_kennisbank_spel
from nooch_village.views.linkbuilding import render_linkbuilding
from nooch_village.views.accountabilities import render_accountabilities
from nooch_village.views.woordenschat import render_woordenschat
from nooch_village.views.keyword_lens import render_keyword_lens
from nooch_village.library import Library
from nooch_village.keyword_nominations import (NominationQueue, NominationKroniek, valid_reason)
from nooch_village.views.belofte import render_belofte


from nooch_village.views.noochie import (
    _noochie_suggest, _noochie_reply,
    render_noochie, _noochie_chrome,
)
from nooch_village.views.callbar import _callbar_frame, render_callbar

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


def _person_targets(st: _Stores, username: str) -> list:
    """De inbox-doelen van de ingelogde mens: hemzelf als persoon ÉN elke rol die hij vervult. Zo bundelt
    de inbox mentions aan de persoon (individuele actie) en aan al zijn rollen. Onbekend/guest → []."""
    if not username or username == "guest":
        return []
    person = st.people.by_email(username)
    if person is None:
        return []
    targets = [("person", person.id)]
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        try:
            for f in st.assign.fillers_of(r.id, record=r):
                if getattr(f, "type", None) == "person" and f.id == person.id:
                    targets.append(("role", r.id))
                    break
        except Exception:
            continue
    return targets


def _scoped_project_opts(st: _Stores, n) -> str:
    """Projectlijst voor de actie-uitkomst, GESCOPET op de rol die bij deze spanning hoort (de doel-rol
    van de mention, anders de eigenaar van het bron-project). Alleen díe projecten — niet alles van
    iedereen (dat was de klacht). Fail-soft: geen rol → alleen de placeholder."""
    rid = ""
    if isinstance(n, dict):
        if n.get("target_type") == "role":
            rid = n.get("target_id") or ""
        if not rid and n.get("project_id"):
            p = st.projects.get(n.get("project_id"))
            rid = (p or {}).get("owner") or ""
    opts = ["<option value=''>— kies project —</option>"]
    if rid:
        for p in st.projects.all():
            if p.get("owner") == rid and not p.get("archived"):
                opts.append(f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:60])}</option>")
    return "".join(opts)


def _role_of_persona(st: _Stores, persona):
    """Eerste niet-gearchiveerde rol die door deze persona wordt vervuld, of None. Puur voor de
    'Rol: … purpose'-context in de reply; ontbreekt hij, dan valt die regel weg (fail-soft)."""
    if persona is None:
        return None
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        f = _owner_ai(st, r)
        if f is not None and f.id == persona.id:
            return r
    return None


def _mentioned_personas(st: _Stores, text: str) -> list:
    """AI-personas die in `text` @genoemd zijn — via rolnaam (→ de persona die de rol vervult) of via
    de persona-naam zelf. Zelfde match-regel als _mentions_in: substring '@naam' (case-insensitief).
    Ontdubbeld op persona-id, volgorde-behoudend. Een @mens levert niets op (die krijgt enkel notificatie)."""
    t = (text or "").lower()
    out, seen = [], set()

    def _maybe(name, persona):
        if persona is None or persona.id in seen:
            return
        if ("@" + (name or "").strip().lower()) in t:
            seen.add(persona.id)
            out.append(persona)

    for r in st.records.all():                       # rolnaam → de persona die de rol vervult
        if getattr(r, "archived", False):
            continue
        _maybe(_name(r), _owner_ai(st, r))
    for p in st.personas.all():                      # persona-naam → die persona
        _maybe(p.name, p)
    return out


def _role_capabilities_block(role) -> str:
    """Accountabilities + skills (naam + korte omschrijving) van de rol, als context zodat een @genoemde
    rol kan toetsen of dialoog-info bij één van haar verantwoordelijkheden past en een concrete stap kan
    voorstellen. Fail-soft: geen rol / geen DNA / registry-bouwfout → een lege string (geen blok, geen
    fout). Verzint niets: alleen wat echt in het DNA en de registry staat."""
    if role is None:
        return ""
    try:
        dna = role.definition
        accts = list(getattr(dna, "accountabilities", []) or [])
        skills = list(getattr(dna, "skills", []) or [])
        reg = None
        try:
            reg = shared_registry()
        except Exception:
            reg = None
        skill_lines = []
        for name in skills:
            obj = reg.get(name) if reg else None
            desc = (getattr(obj, "description", "") or "").strip() if obj else ""
            skill_lines.append(f"- {name}: {desc[:120]}" if desc else f"- {name}")
        acc_txt = "\n".join(f"- {a}" for a in accts) or "(geen)"
        sk_txt = "\n".join(skill_lines) or "(geen)"
        return (f"Jouw accountabilities:\n{acc_txt}\n"
                f"Jouw skills (de ENIGE concrete tools die je hebt):\n{sk_txt}\n")
    except Exception:
        return ""


def _ai_reply(st: _Stores, pid: str, ask=None, *, persona=None, prefix: str = "") -> bool:
    """Een @genoemde (of via de meedenk-knop aangesproken) AI-rol TRIAGEERT een signaal, i.p.v. blind een
    voorstel te posten. De beslisboom (zie `_parse_triage` + `_settle_inbox`):

      1. Past het bij mijn rol?  Nee → korte afwijzing (+ optioneel welk stuk wél), item verwerkt met reden.
      2. Ja/deels, en kan ik het puur uit mijn kennis beantwoorden (geen skill/project nodig)? → antwoord
         nu direct op de wall; het inbox-item wordt verwerkt met reden 'direct beantwoord'.
      3. Ja/deels, maar er is een skill/meerdere stappen nodig? → 'ik verwerk dit via mijn inbox'. Binnen
         scope (een skill die ECHT in het DNA zit, machine-gecheckt via plan_offers) + experiment aan →
         de rol maakt er meteen zelf een project van en markeert het inbox-item verwerkt met de uitkomst.
         Buiten scope / experiment uit → het item blijft 'nieuw' voor de mens.

    Zo is er één verwerkingsplek (de inbox) met historie: elk signaal krijgt een herkomst en een uitkomst,
    of het nu van een mens kwam of de rol het zichzelf toebedeelt. `ask(prompt)->str|None` is injecteerbaar
    (test); standaard via llm.reason. Fail-closed: geen persona / geen LLM-antwoord → geen post."""
    p = st.projects.get(pid)
    if p is None:
        return False
    if persona is None:
        role = st.records.get(p.get("owner"))        # knop-variant: de eigenaar-persona
        persona = _owner_ai(st, role)
    else:
        role = _role_of_persona(st, persona)         # @mention-variant: rol enkel voor de purpose-regel
    if persona is None:
        return False
    recent = "\n".join(f"- {m.get('text', '')}" for m in (p.get("log") or [])[-6:])
    rol_line = (f"Rol: {_name(role)} — purpose: {role.definition.purpose}\n" if role is not None else "")
    capab = _role_capabilities_block(role)          # accountabilities + skills → grondslag voor de toets
    aanleiding = (prefix.strip() + "\n\n") if (prefix or "").strip() else ""
    ctx = (f"{aanleiding}"
           f"Project: {_scope_text(p)}\n"
           f"Omschrijving: {p.get('description', '') or '(geen)'}\n"
           f"{rol_line}"
           f"{capab}"
           f"Recente dialoog:\n{recent or '(nog leeg)'}\n\n"
           "Triageer dit signaal tegen JOUW accountabilities en skills. Beantwoord drie dingen:\n"
           "1. Past het bij jouw rol? (ja / deels / nee — bij deels of nee: welk stuk kun je wél oppakken)\n"
           "2. Kun je het NU beantwoorden puur uit wat je al weet (informatie delen), zonder een skill te "
           "draaien of een project te starten? Zo ja: geef dat antwoord.\n"
           "3. Kan het niet direct (er is een skill of meerdere stappen nodig)? Zeg dan kort dat je het via "
           "je inbox verwerkt. Verzin niets en claim nooit dat je iets deed wat je niet deed.\n\n"
           "Antwoord UITSLUITEND met JSON, exact dit schema: {\"fit\": \"ja|deels|nee\", \"welk_stuk\": "
           "\"<bij deels/nee: welk deel je wél kunt, anders leeg>\", \"kan_direct\": true of false, "
           "\"reactie\": \"<bij kan_direct=true je informatie-antwoord; anders een korte reactie/afwijzing, "
           "max 4 zinnen>\"}.")
    from nooch_village.personas import persona_prompt
    prompt = (persona_prompt(persona) + "\n\n" + ctx).strip()
    if ask is None:
        try:
            from nooch_village import llm
            out = llm.reason(prompt, ladder=_match_ladder(), json_mode=True,
                             call_site="cockpit_mention_triage")
        except Exception:
            out = None
    else:
        out = ask(prompt)
    if not out:
        return False
    tri = _parse_triage(out)
    if tri is None:
        # Fail-closed: geen bruikbare triage-JSON → plaats de platte tekst als gewone reactie (geen gok,
        # geen inbox-actie). Zo blijven oude/gestubde platte-tekst-antwoorden gewoon zichtbaar.
        txt = (out or "").strip()
        if not txt:
            return False
        st.projects.add_feed_entry(pid, txt, kind="comment", author_type="persona", author_id=persona.id)
        return True
    return _apply_triage(st, pid, role, persona, tri, prefix)


def _ask_text(p: dict, prefix: str) -> str:
    """De tekst die aan de rol gevraagd wordt (het te triageren signaal), voor de skill-machinecheck. Uit
    de aanleidende mens-comment (`prefix`, ontdaan van de 'De mens vraagt jou:'-omlijsting) of anders de
    laatste dialoog-regel. Puur afgeleid, verzint niets."""
    t = (prefix or "").strip()
    for lead in ("De mens vraagt jou:", "De mens vraagt:"):
        if t.startswith(lead):
            t = t[len(lead):].strip()
            break
    if t:
        return t
    for m in reversed(p.get("log") or []):
        if (m.get("text") or "").strip():
            return m["text"].strip()
    return ""


def _apply_triage(st: _Stores, pid: str, role, persona, tri: dict, prefix: str) -> bool:
    """Voer de getriageerde beslissing uit: post de reactie op de wall en verwerk/laat-staan het inbox-item
    (met historie). Zie `_ai_reply` voor de beslisboom. Fail-closed op deelfouten."""
    p = st.projects.get(pid)
    reactie = tri.get("reactie") or ""
    fit = tri.get("fit")
    welk = (tri.get("welk_stuk") or "").strip()
    ask = _ask_text(p or {}, prefix)

    # 1. Past niet bij de rol → korte afwijzing; item is afgehandeld (met reden), geen skill/geen project.
    if fit == "nee":
        txt = reactie or ("Dit past niet bij mijn rol." + (f" Wel oppakbaar: {welk}" if welk else ""))
        entry = st.projects.add_feed_entry(pid, txt, kind="comment", author_type="persona", author_id=persona.id)
        reden = "past niet bij mijn rol" + (f" — wel: {welk}" if welk else "")
        _settle_inbox(st, role, pid, (entry or {}).get("id", ""), ask, processed=True, reason=reden)
        return True

    # 2/3. Past (deels): heeft beantwoorden een EIGEN skill nodig? Harde machine-check tegen het DNA.
    off = _dna_skill_for(st, role, ask)
    skill_needed = bool(off and off.get("skill"))

    # 2. Puur kennisantwoord (geen skill nodig én de rol zegt kan_direct) → nu direct op de wall.
    if not skill_needed and tri.get("kan_direct") and reactie:
        entry = st.projects.add_feed_entry(pid, reactie, kind="comment", author_type="persona", author_id=persona.id)
        _settle_inbox(st, role, pid, (entry or {}).get("id", ""), ask, processed=True,
                      reason="direct beantwoord op de wall")
        return True

    # 3. Skill/meerdere stappen nodig → 'ik verwerk dit via mijn inbox'.
    ack = reactie or "Ik pak dit op en verwerk het via mijn inbox."
    entry = st.projects.add_feed_entry(pid, ack, kind="comment", author_type="persona", author_id=persona.id)
    eid = (entry or {}).get("id", "")

    # Binnen scope (eigen skill in DNA) + experiment aan → de rol verwerkt het item meteen zelf als project
    # via de vijf-uitkomsten-flow, en markeert het inbox-item verwerkt met de uitkomst (historie).
    if skill_needed and role is not None and not org.is_circle(role) and _mention_autotask_on():
        titel = (ask or reactie).strip()[:200]
        vst = {"titel": titel, "skill": off["skill"],
               "payload": off.get("payload") if isinstance(off.get("payload"), dict) else {},
               "role_id": role.id}
        new_pid = _create_task_from_voorstel(st, role, vst)
        if new_pid:
            _prov_feed(st, new_pid, f"↳ binnen scope zelf opgepakt uit dialoog op {pid}#{eid}", "")
            _prov_feed(st, pid, f"→ {_name(role)} pakte dit binnen scope zelf op: {titel}", "")
            _settle_inbox(st, role, pid, eid, ask, processed=True, reason=f"zelf opgepakt als project: {titel}")
            return True

    # Buiten scope / experiment uit / geen project gemaakt → item blijft 'nieuw' voor de mens (of de rol
    # zelf) om via de vijf-uitkomsten te verwerken.
    _settle_inbox(st, role, pid, eid, ask, processed=False, reason="")
    return True


def _dna_skill_for(st: _Stores, role, ask_text: str):
    """Harde machine-check: matcht het gevraagde (`ask_text`) op een skill die ECHT in het DNA van de rol
    zit? Retourneert {skill, payload, ...} of None. Hergebruikt plan_offers (dat de skill tegen de harde
    DNA-lijst toetst). Fail-closed: geen rol / geen skills / geen tekst / fout → None."""
    if role is None or org.is_circle(role) or not (ask_text or "").strip():
        return None
    try:
        offers = plan_offers(role, [ask_text], shared_registry(), name=_name(role))
    except Exception:
        return None
    return offers[0] if offers else None


def _settle_inbox(st: _Stores, role, pid: str, entry_id: str, ask_text: str, *,
                  processed: bool, reason: str):
    """Eén verwerkingsplek: zorg dat er een inbox-item voor deze rol op dit project bestaat en zet de
    status. Bestond er al een open item (bv. van een mens-@mention), dan wordt DAT verwerkt/gelaten; anders
    vijlt de rol er zelf één (autonome trigger). `processed=True` → verwerkt met `reason` als historie;
    `processed=False` → blijft 'nieuw' voor de mens. Fail-closed: geen rol → niets."""
    if role is None:
        return None
    rid = getattr(role, "id", "") or ""
    if not rid:
        return None
    try:
        open_items = [n for n in st.notif.for_targets([("role", rid)])
                      if n.get("project_id") == pid and not n.get("processed") and not n.get("archived")]
        n = open_items[0] if open_items else st.notif.add("role", rid, pid, entry_id,
                                                          by=_name(role), snippet=ask_text or "")
        if processed:
            st.notif.mark_item_processed(n["id"], outcome=reason, by=_name(role))
        return n
    except Exception:
        return None


def _mention_autotask_on() -> bool:
    """Experiment-schakelaar: mogen rollen een binnen-scope-stap (eigen skill) zelf tot taak maken, zonder
    mens-knop? Default UIT (env `mention_autotask` ontbreekt → veilig, alles via de knop). Aan met
    mention_autotask=1 in .env — omkeerbaar voor een week-experiment. Buiten-scope blijft altijd de knop."""
    _load_env()
    return os.getenv("mention_autotask", "0").strip().lower() in ("1", "true", "yes", "on", "ja")


def _create_task_from_voorstel(st, orec, vst) -> str | None:
    """Maak een project owned door rol `orec` uit een dialoog-voorstel, met de voorgestelde skill als
    checklist-item (de daemon voert projectwerk uit onder de EIGENAAR-rol, dus de voorstellende rol is de
    eigenaar). Returnt het nieuwe pid, of None bij een ongeldige rol/cirkel/lege titel. Puur de creatie;
    herkomst-trail en het weghalen van het voorstel doet de caller. Gedeeld door de auto- en knop-route."""
    if orec is None or org.is_circle(orec):
        return None
    titel = str((vst or {}).get("titel", "")).strip()[:200]
    if not titel:
        return None
    new_pid = st.projects.create(orec.id, titel, "human")
    sk = vst.get("skill") or None
    payload = vst.get("payload") if isinstance(vst.get("payload"), dict) else {}
    ok = True
    if sk:
        try:
            from nooch_village.skill_match import _payload_ok
            ok = _payload_ok(sk, payload, shared_registry())
        except Exception:
            ok = True
    cl = st.projects.checklist_add(new_pid, "Uit dialoog")
    if cl:
        st.projects.check_add(new_pid, cl["id"], titel, skill=sk, payload=payload, payload_ok=ok)
    return new_pid


def _parse_triage(out: str):
    """Split het triage-antwoord in {fit, welk_stuk, kan_direct, reactie} of None (fail-closed). Verwacht
    JSON {fit:'ja|deels|nee', welk_stuk, kan_direct:bool, reactie}. Ongeldige fit of lege reactie → None,
    zodat de caller terugvalt op een gewone platte-tekst-reactie (geen triage-gok op rommel)."""
    txt = (out or "").strip()
    try:
        from nooch_village.skill_match import _extract_json
        data = _extract_json(txt)
    except Exception:
        data = None
    if not isinstance(data, dict):
        return None
    fit = str(data.get("fit", "")).strip().lower()
    if fit not in ("ja", "deels", "nee"):
        return None
    reactie = str(data.get("reactie", "")).strip()
    if not reactie:
        return None
    return {"fit": fit, "welk_stuk": str(data.get("welk_stuk", "")).strip(),
            "kan_direct": bool(data.get("kan_direct")), "reactie": reactie}


def _reply_to_mentions(st: _Stores, pid: str, text: str) -> int:
    """Laat elke in `text` @genoemde AI-persona één keer meedenken op de wall, met de aanleidende
    comment bovenaan de context. Cap op mention_reply_limit (default 2, uit .env/env) tegen LLM-budget.
    Fail-closed: geen persona-match, geen LLM-antwoord of een exceptie → geen post, en het bestaande
    notificatie-gedrag blijft ongemoeid. Alleen de aanroeper (mens-comment) mag dit triggeren."""
    try:
        personas = _mentioned_personas(st, text)
    except Exception:
        return 0
    if not personas:
        return 0
    _load_env()
    try:
        limit = max(0, int(os.getenv("mention_reply_limit", "2")))
    except (TypeError, ValueError):
        limit = 2
    prefix = f"De mens vraagt jou: {(text or '').strip()}"
    replied = 0
    for persona in personas:
        if replied >= limit:
            break
        try:
            if _ai_reply(st, pid, persona=persona, prefix=prefix):
                replied += 1
        except Exception:
            continue
    return replied


# De @mention-reply doet blokkerende LLM-calls; die mogen de POST (en dus het verschijnen van de eigen
# comment op de wall) niet ophouden. Async = default (prod); tests zetten dit op False voor determinisme.
_MENTION_REPLY_ASYNC = True


def _run_mention_reply(st: _Stores, pid: str, text: str):
    """Draai de @mention-reply. Async (default): start 'm in een daemon-thread en geef de Thread terug
    (de comment staat dan al op de wall; het AI-antwoord landt zodra de LLM klaar is, zichtbaar bij de
    volgende refresh). Sync (test): draai inline en geef het aantal replies (int) terug. De stores zijn
    flock-veilig, dus een schrijf vanuit de thread is veilig; _reply_to_mentions is al fail-closed."""
    if _MENTION_REPLY_ASYNC:
        import threading
        t = threading.Thread(target=lambda: _reply_to_mentions(st, pid, text), daemon=True)
        t.start()
        return t                                     # niet-int → "AI denkt mee…"; joinbaar in de test
    return _reply_to_mentions(st, pid, text)         # int aantal replies


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


_MIN_PASSWORD_LEN = 10


def _password_change(data_dir: str, form: dict, username: str | None):
    """Self-service wachtwoordwijziging (self óf geforceerd bij een temp). Valideert het huidige
    wachtwoord, het beleid (min. lengte + ≠ huidig) en de bevestiging. (True, None) bij succes → de
    caller redirect + verbreekt oude sessies; (False, foutpagina) bij een fout."""
    st = _Stores(data_dir)
    g = lambda k: (form.get(k) or [""])[0]
    current, new, confirm = g("current"), g("new"), g("confirm")
    forced = st.people.must_change(username or "")
    person = st.people.by_email(username or "")
    us = _auth.UserStore(os.path.join(data_dir, "people.json"))

    def fail(msg):
        return False, _auth.password_change_page(error=msg, forced=forced)

    if person is None:
        return fail("Gebruiker niet herkend.")
    # Een VRIJWILLIGE wijziging vraagt het huidige wachtwoord; een VERPLICHTE (temp na eerste login/reset)
    # NIET — de gebruiker is net via login geauthenticeerd (die verifieerde het temp al). Het huidig-veld
    # lokt daar bovendien browser-autofill van het OUDE wachtwoord uit → een onmogelijk-op-te-lossen loop.
    if not forced and not us.verify_by_email(username or "", current):
        return fail("Huidig wachtwoord onjuist.")
    if new != confirm:
        return fail("De nieuwe wachtwoorden komen niet overeen.")
    if len(new) < _MIN_PASSWORD_LEN:
        return fail(f"Kies minimaal {_MIN_PASSWORD_LEN} tekens.")
    if us.verify_by_email(username or "", new):      # nieuw ≠ het huidige/temp wachtwoord (zonder typen)
        return fail("Kies een ander wachtwoord dan je huidige.")
    st.people.set_own_password(person.id, _auth.hash_password(new))
    return True, None


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


VILLAGE_ROOM = "village"


def _tab_suffix(tab: str | None) -> str:
    """Saniteer een client-tab-id tot [a-z0-9], max 12 tekens. Puur een disambiguator per tabblad —
    hij wordt alleen ACHTER de server-bepaalde base geplakt en kan die base nooit overschrijven."""
    return re.sub(r"[^a-z0-9]", "", (tab or "").lower())[:12]


def issue_livekit_token(st, username: str | None, tab: str | None = None):
    """Geef een LiveKit-token uit voor de DORP-BREDE call bar. Geeft (status_code, payload) terug.

    HARDE REGEL: `room` en de identity-BASE worden UITSLUITEND server-side bepaald — nooit uit de
    request. Er is één dorp-brede room (`VILLAGE_ROOM`). `tab` is de enige request-input en dient
    alléén als per-tabblad-suffix (`<base>#tab-<tab>`) zodat meerdere tabs van dezelfde gebruiker niet
    op een duplicate-identity-kick lopen; de suffix wordt gesanitiseerd en kan de base niet vervangen
    (geen impersonatie). De vroegere wo-<circle>-<started_at>-afleiding is vervallen."""
    # AUTHZ: iedereen-ingelogd — de call bar is dorp-breed; er is geen cirkel-structuur om aan te
    # toetsen. Elke herkende ingelogde actor krijgt een (toeschouwer-)token; deelnemen/muten is een
    # gespreksdaad, geen structuurdaad. Een niet-herkende sessie krijgt geen token (fail-closed).
    server_url = os.getenv("LIVEKIT_URL", "").strip()
    if not server_url:
        return 503, {"error": "LiveKit niet geconfigureerd"}
    # IDENTITY-BASE: de ingelogde actor. Guest = de lokale sessie bij auth-uit → één vaste base.
    if username and username != "guest":
        actor = st.people.by_email(username)
        if actor is None:
            return 403, {"error": "Geen herkende gebruiker"}
        base, name = actor.id, actor.name
    else:
        base, name = "guest", "Gast"
    suffix = _tab_suffix(tab)
    identity = f"{base}#tab-{suffix}" if suffix else base
    try:
        token = maak_livekit_token(VILLAGE_ROOM, identity, name)
    except Exception as e:
        # De API-secret mag NOOIT lekken: alleen het exceptietype terug, geen details.
        return 500, {"error": f"token-generatie faalde ({type(e).__name__})"}
    return 200, {"token": token, "server_url": server_url, "identity": identity}


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


def livekit_mute_participant(identity: str, muted: bool = True) -> bool:
    """Mute/unmute de audio-track(s) van een deelnemer server-side (voor iedereen), fail-soft. True als
    er minstens één audio-track is (un)gemute, False bij geen creds / deelnemer of track weg / netwerk —
    NOOIT een exception naar de caller. De API-secret lekt niet. Zelfde patroon als
    verwijder_livekit_room (api.LiveKitAPI, wss->https-conversie, async in één asyncio.run)."""
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url or not (identity or "").strip():
        return False
    api_url = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        import asyncio
        from livekit import api

        async def _run():
            lk = api.LiveKitAPI(api_url)          # api_key/secret uit de env
            try:
                p = await lk.room.get_participant(
                    api.RoomParticipantIdentity(room=VILLAGE_ROOM, identity=identity))
                sids = [t.sid for t in p.tracks if t.type == api.TrackType.AUDIO]
                for sid in sids:
                    await lk.room.mute_published_track(api.MuteRoomTrackRequest(
                        room=VILLAGE_ROOM, identity=identity, track_sid=sid, muted=muted))
                return bool(sids)
            finally:
                await lk.aclose()

        return asyncio.run(_run())
    except Exception:
        return False


def livekit_presence():
    """Aantal deelnemers in de dorp-room, server-side via list_participants — GEEN eigen
    deelnemer-verbinding, dus kost GEEN WebRTC-minuten (in tegenstelling tot de oude observer-connect).
    Fail-soft: (0, []) zonder creds of bij een fout. Ontdubbelt op de identity-base (tab-suffix eraf)
    zodat meerdere tabs van één persoon als één deelnemer tellen. Zelfde async-in-asyncio.run-patroon
    als livekit_mute_participant."""
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url:
        return 0, []
    api_url = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        import asyncio
        from livekit import api

        async def _run():
            lk = api.LiveKitAPI(api_url)          # api_key/secret uit de env
            try:
                res = await lk.room.list_participants(api.ListParticipantsRequest(room=VILLAGE_ROOM))
                return list(res.participants)
            finally:
                await lk.aclose()

        parts = asyncio.run(_run())
        seen = {}
        for p in parts:
            base = (p.identity or "").split("#tab-")[0]
            if base:
                seen[base] = p.name or base
        return len(seen), list(seen.values())[:8]
    except Exception:
        return 0, []


# Static-assets: whitelist (geen path-traversal). Nu alleen de gevendorde LiveKit-client-bundle.
_STATIC_TYPES = {
    "livekit-client.umd.min.js": "application/javascript; charset=utf-8",
    # Design-systeem-CSS (component-laag). URL draagt ?v=<inhoud-hash> (_DS_LINK),
    # dus de browser mag lang cachen: nieuwe CSS = nieuwe URL.
    "nooch.css": "text/css; charset=utf-8",
}


def role_context(st, role_id: str, fmt: str = "json"):
    """Serialiseer de volledige rol-context als (status, content_type, body).
    `fmt="markdown"` = de systeemprompt-bron voor AI-vervullers; anders JSON."""
    if not st.records.get(role_id):
        return 404, "text/plain; charset=utf-8", "Onbekende rol."
    ctx = artefacts.serialize_context(role_id, st.records, st.att)
    if fmt == "markdown":
        return 200, "text/markdown; charset=utf-8", artefacts.render_context_markdown(ctx)
    return 200, "application/json; charset=utf-8", json.dumps(ctx, ensure_ascii=False, indent=2)


class _Ctx:
    """De gedeelde dispatch-state, doorgegeven aan elke geregistreerde actie-handler."""
    __slots__ = ("st", "g", "nxt", "form", "username", "action", "data_dir", "pj")

    def __init__(self, st, g, nxt, form, username, action, data_dir):
        self.st, self.g, self.nxt = st, g, nxt
        self.form, self.username, self.action, self.data_dir = form, username, action, data_dir
        self.pj = st.projects


def _act_proj_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
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
        return nxt, msg


def _act_artefact_add(c):
        nxt, st, g, form, username, action, data_dir = c.nxt, c.st, c.g, c.form, c.username, c.action, c.data_dir
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead — alleen de vervuller van de eigenaar-rol (of de Circle
        # Lead van de omvattende cirkel) mag artefacten binnen dat domein aanmaken; mens én AI gelijk.
        owner = g("owner")
        _deny = _artefact_gate(owner, username, st)          # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)                            # → HTTP 403, geen 303-redirect
        kind = g("kind")
        if kind not in ARTEFACT_KINDS:
            return nxt, "✗ onbekende artefact-soort"
        domain = ""
        if kind == "policy":
            # Een policy kan alleen op een domein dat de rol ÉCHT via governance bezit. Het gekozen
            # domein wordt server-side gevalideerd tegen definition.domains; geen fallback/voorbak.
            rec = st.records.get(owner)
            owner_domains = list(getattr(rec.definition, "domains", None) or []) if rec else []
            if not owner_domains:
                return nxt, ("✗ deze rol heeft nog geen domein; wijs er eerst een toe via governance, "
                             "daarna kun je er een policy op maken")
            chosen = g("domain").strip()
            if not chosen and len(owner_domains) == 1:
                chosen = owner_domains[0]            # één domein → vaste keuze (form stuurt 'm mee)
            if chosen not in owner_domains:
                return nxt, "✗ kies een domein dat deze rol daadwerkelijk bezit"
            domain = chosen
        gref = f"domain:{domain}" if domain else f"role:{owner}"
        actor_id = _web_actor_id(username, st)
        a = st.att.add(owner, kind, title=g("title"), body=g("body"),
                       url=g("url"), domain=domain, inherit=True,   # policies gelden altijd voor iedereen
                       actor_id=actor_id, actor_type="person",
                       governance_ref=gref, change_note="aangemaakt")
        if a is None:
            return nxt, "✗ artefact niet aangemaakt"
        artefacts.log_change(data_dir, action="add", artefact=a, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"➕ {kind} toegevoegd ({a.id})"
        return nxt, msg


def _act_artefact_edit(c):
        nxt, st, g, form, username, action, data_dir = c.nxt, c.st, c.g, c.form, c.username, c.action, c.data_dir
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead — bewerken mag alleen wie de eigenaar-rol vervult.
        cur = st.att.get(g("aid"))
        if cur is None:
            return nxt, "✗ artefact niet gevonden"
        _deny = _artefact_gate(cur.anchor, username, st)      # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)
        gref = f"domain:{cur.domain}" if getattr(cur, 'domain', '') else f"role:{cur.anchor}"
        actor_id = _web_actor_id(username, st)
        upd = st.att.update(cur.id,
                            title=(g("title") if "title" in form else None),
                            body=(g("body") if "body" in form else None),
                            url=(g("url") if "url" in form else None),
                            actor_id=actor_id, actor_type="person",
                            governance_ref=gref, change_note="bewerkt")
        artefacts.log_change(data_dir, action="edit", artefact=upd, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"✏️ {upd.kind} bijgewerkt ({upd.id})"
        return nxt, msg


def _act_artefact_archive(c):
        nxt, st, g, username, action, data_dir = c.nxt, c.st, c.g, c.username, c.action, c.data_dir
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead — archiveren (nooit hard delete) mag alleen de vervuller.
        cur = st.att.get(g("aid"))
        if cur is None:
            return nxt, "✗ artefact niet gevonden"
        _deny = _artefact_gate(cur.anchor, username, st)      # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)
        gref = f"domain:{cur.domain}" if getattr(cur, 'domain', '') else f"role:{cur.anchor}"
        actor_id = _web_actor_id(username, st)
        arch = st.att.archive(cur.id, actor_id=actor_id, actor_type="person",
                              governance_ref=gref, change_note="gearchiveerd")
        artefacts.log_change(data_dir, action="archive", artefact=arch, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"🗄️ {arch.kind} gearchiveerd ({arch.id})"
        return nxt, msg


def _act_proj_status(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
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
        return nxt, msg


def _act_proj_done(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pid = g("pid")
        # Outcome met behoud van de telling; de mens kent Done toe ná review (Q3).
        p = pj.get(pid) or {}
        cl = next((c for c in p.get("checklists", []) if c.get("title") == PREP_CHECKLIST_TITLE), None)
        if cl is not None:
            items = cl.get("items", [])
            done = sum(1 for it in items if it.get("done"))
            outcome = f"checklist voltooid ({done}/{len(items)}) — goedgekeurd na review"
        else:
            outcome = "goedgekeurd na review"
        pj.complete(pid, outcome); msg = "✓ afgerond"
        # Geen event vanuit dit proces — de daemon-board-watch (village._poll_board) detecteert de
        # wacht→done-overgang (blocked_on=="review") en vuurt project_completed op de in-memory bus (#10-fix).
        return nxt, msg


def _act_proj_archive(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.archive(g("pid")); msg = "🗄 gearchiveerd (blijft bestaan)"
        return nxt, msg


def _act_proj_unarchive(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.unarchive(g("pid")); msg = "↩ hersteld"
        return nxt, msg


def _act_proj_delete(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel van het project ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = resolve_circle_id((pj.get(g("pid")) or {}).get("owner") or "", st.records)
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        pid = g("pid")
        pj.remove(pid)
        # Cascade bij definitieve delete: index-records ÉN write-once sidecars mee-verwijderen.
        # delete_for_project logt zelf beide aantallen (records + sidecars); geen status-overgang komt hier.
        dstore = getattr(st, "deliverables", None)
        if dstore is not None:
            dstore.delete_for_project(pid)
        # Cascade: het levende einddocument (sidecar-.md) mee-verwijderen.
        docstore = getattr(st, "project_docs", None)
        if docstore is not None and docstore.delete_for(pid):
            logging.getLogger("village.project_docs").info(
                "cascade: einddocument verwijderd bij project-delete %s", pid)
        msg = "🗑 verwijderd"
        return nxt, msg


def _act_proj_edit(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        person, agent = _parse_trekker(g("trekker"))
        pj.edit(g("pid"), scope=g("scope"), person=person, agent=agent,
                private=(g("private") == "1"), description=g("description"), label=g("label"))
        msg = "💾 opgeslagen"
        return nxt, msg


def _act_proj_comment(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.add_comment(g("pid"), g("comment")):
            msg = "💬 geplaatst"
        return nxt, msg


def _act_proj_rename(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), scope=g("scope"), allow_done=True):
            msg = "✓ titel opgeslagen"
        return nxt, msg


def _act_proj_describe(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), description=g("description"), allow_done=True):
            msg = "✓ omschrijving opgeslagen"
        return nxt, msg


def _act_proj_regen_doc(c):
        # AUTHZ: zelfde poort als de edit-route (rolvervuller of Circle Lead) — regenereren overschrijft
        # het einddocument. Forceert een verse synthese uit de deliverables ('trek oud project bij').
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        p = pj.get(g("pid"))
        if p is None:
            return nxt, "✗ project niet gevonden"
        _deny = _role_gate(p.get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        _load_env()                                          # LLM-key beschikbaar maken (zoals _ai_reply)
        import logging
        from nooch_village.inhabitant import synthesize_einddocument
        rec = st.records.get(p.get("owner"))
        ok = synthesize_einddocument(
            project_docs=st.project_docs, deliverables=st.deliverables, projects=st.projects,
            personas=st.personas, record=rec, settings={}, project=p, force_final=True,
            log=logging.getLogger("village.cockpit_regen"))
        return nxt, ("📄 rapport opnieuw gegenereerd" if ok
                     else "geen rapport gegenereerd (geen deliverables of geen LLM-key)")


def _act_proj_doc_edit(c):
        # AUTHZ: rolvervuller of Circle Lead — het einddocument is operationeel werk binnen de rol; de
        # mens redigeert het bij review via dezelfde poort als andere project-operaties.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        store = getattr(st, "project_docs", None)
        if store is not None:                              # atomic write; last-writer wint (v1, geen merge)
            store.write(g("pid"), g("doc"))
        return nxt, "📄 einddocument opgeslagen"


def _act_proj_settrekker(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        person, agent = _parse_trekker(g("trekker"))
        if pj.edit(g("pid"), person=person, agent=agent, allow_done=True):
            msg = "✓ trekker opgeslagen"
        return nxt, msg


def _resync_trekker(pj, st, pid: str, owner: str, orec) -> None:
    """Na een owner-wissel mag de trekker niet VERWEESD achterblijven: is de huidige trekker een echte
    trekker maar géén filler van de nieuwe rol, zet 'm op de enige filler van die rol (indien precies
    één) of op leeg. Een al-lege trekker blijft leeg (dat is niet verweesd)."""
    p = pj.get(pid)
    if p is None:
        return
    fillers = st.assign.fillers_of(owner, record=orec)
    keys = {(f.type, f.id) for f in fillers}
    if p.get("person"):
        cur = ("person", p["person"])
    elif p.get("agent"):
        cur = ("persona", p["agent"])
    else:
        return                                                 # geen trekker → niets verweesd
    if cur in keys:
        return                                                 # trekker bezet de nieuwe rol → laat staan
    if len(fillers) == 1:                                      # precies één filler → daarheen
        f = fillers[0]
        pj.edit(pid, person=(f.id if f.type == "person" else ""),
                agent=(f.id if f.type == "persona" else ""), allow_done=True)
    else:                                                      # 0 of meerdere fillers → leeg (nooit verweesd)
        pj.edit(pid, person="", agent="", allow_done=True)


def _act_proj_setowner(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
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
            _resync_trekker(pj, st, g("pid"), owner, orec)     # geen verweesde trekker laten staan
            msg = "✓ rol verplaatst"
        return nxt, msg


def _act_proj_approve(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.approve(g("pid")):
            msg = "✓ concept goedgekeurd — staat nu op het bord"
        return nxt, msg


def _act_proj_discard(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.discard(g("pid")):
            msg = "🗑 concept verworpen"
        return nxt, msg


def _act_proj_setlabel(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), label=g("label"), allow_done=True):
            msg = "✓ label opgeslagen"
        return nxt, msg


_IMPACT_FIELDS = {"missie": ("missie_impact", _MISSIE_IMPACT), "business": ("business_impact", _BUSINESS_IMPACT)}
# effort is geen enum-label meer maar een numeriek veld (uren) → eigen tak proj_seteffort (zie hieronder)


def _act_proj_setimpact(c):
        # AUTHZ: rolvervuller-of-Circle-Lead — impact-labels zijn operationeel projectwerk (zelfde gate als
        # de andere proj_set*-takken). Leeg = wissen (ongelabeld); dat mag ook.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        spec = _IMPACT_FIELDS.get(g("kind"))
        if spec is None:
            return nxt, "onbekend impact-veld"
        field, allowed = spec
        value = g("value")
        if value and value not in allowed:
            return nxt, "ongeldige impact-waarde"
        if pj.edit(g("pid"), allow_done=True, **{field: value}):
            return nxt, ("✓ impact opgeslagen" if value else "✓ impact leeggemaakt")
        return nxt, ""


def _act_proj_seteffort(c):
        # AUTHZ: rolvervuller of Circle Lead — effort-inschatting is operationeel projectwerk (zelfde gate
        # als proj_setimpact). Effort wordt canoniek in uren opgeslagen ({"hours": N}); leeg = wissen.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        raw = (g("number") or "").strip().replace(",", ".")
        if not raw:                                          # leeg getal → wissen (ongeschat)
            pj.edit(g("pid"), allow_done=True, effort="")
            return nxt, "✓ effort leeggemaakt"
        try:
            n = float(raw)
        except ValueError:
            return nxt, "ongeldige effort-waarde"
        hours = int(round(n * (8 if g("unit") == "dagen" else 1)))   # dagen → uren (8-urige werkdag)
        if hours <= 0:
            pj.edit(g("pid"), allow_done=True, effort="")
            return nxt, "✓ effort leeggemaakt"
        pj.edit(g("pid"), allow_done=True, effort={"hours": hours})
        return nxt, "✓ effort opgeslagen"


def _act_proj_agendeer_verzwakt(c):
        # AUTHZ: circle-member — een spanning inbrengen is dezelfde laag als elders in het werkoverleg
        # (_member_gate). Signaal, geen blokkade: statuswissels blijven hier los van mogelijk.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        p = pj.get(g("pid"))
        if p is None:
            return nxt, "project niet gevonden"
        circle = resolve_circle_id(p.get("owner") or "", st.records)
        if not circle:
            return nxt, "geen cirkel voor dit project"
        _deny = _member_gate(circle, username, st)
        if _deny:
            return nxt, _deny
        scope = p.get("scope")
        titel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
                 if isinstance(scope, dict) else str(scope or "project"))
        actor = st.people.by_email(username) if username and username != "guest" else None
        # In de PERSISTENTE werkoverleg-backlog van de cirkel — opent géén overleg; komt bij het
        # eerstvolgende overleg vanzelf op de agenda.
        if st.werk.backlog_add(circle, f"Missie verzwakt: {titel}"[:140], by=(actor.name if actor else "")):
            return nxt, "✓ als spanning in de werkoverleg-backlog van de cirkel gezet"
        return nxt, ""


def _act_proj_setprivate(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), private=(g("private") == "1"), allow_done=True):
            msg = "✓ zichtbaarheid opgeslagen"
        return nxt, msg


def _act_proj_setdue(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.set_due(g("pid"), g("due")):
            msg = "📅 datum opgeslagen" if g("due") else "✓ datum verwijderd"
        return nxt, msg


def _act_attach_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.attach_add(g("pid"), url=g("url"), title=g("title")):
            msg = "🔗 bijlage toegevoegd"
        return nxt, msg


def _act_attach_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.attach_remove(g("pid"), g("aid")); msg = "🗑 bijlage verwijderd"
        return nxt, msg


def _act_react_add(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.add_reaction(g("pid"), g("item"), g("emoji")):
            msg = "✓ reactie geplaatst"
        return nxt, msg


def _act_feed_edit(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.feed_edit(g("pid"), g("item"), g("text")):
            msg = "✓ comment gewijzigd"
        return nxt, msg


def _act_feed_remove(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        pj.feed_remove(g("pid"), g("item")); msg = "🗑 comment verwijderd"
        return nxt, msg


def _act_ai_reply(c):
        nxt, st, g = c.nxt, c.st, c.g
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        _load_env()
        msg = ("🤖 AI heeft meegedacht" if _ai_reply(st, g("pid"))
               else "geen AI-antwoord (geen AI-inwoner op de rol of geen LLM-key)")
        return nxt, msg


def _act_proj_feed(c):
        nxt, st, g, pj = c.nxt, c.st, c.g, c.pj
        msg = ""
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
            # @mention van een AI-persona → die persona antwoordt eenmalig op de wall. Alleen bij een
            # mens-comment: een persona-comment kan nooit een nieuwe reply triggeren (geen loop), ook
            # niet met een @erin. Cap + fail-closed zitten in _reply_to_mentions.
            if atype == "human":
                res = _run_mention_reply(st, g("pid"), g("text"))   # async: blokkeert de POST niet
                if isinstance(res, int):
                    if res:
                        msg += f" · {res} AI-antwoord{'en' if res != 1 else ''}"
                elif any(ty == "persona" for ty, _, _ in ment):
                    msg += " · AI denkt mee…"                        # async: antwoord landt zo op de wall
        return nxt, msg


def _act_checklist_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.checklist_add(g("pid"), g("title")):
            msg = "✓ checklist toegevoegd"
        return nxt, msg


def _act_checklist_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.checklist_remove(g("pid"), g("clid")); msg = "🗑 checklist verwijderd"
        return nxt, msg


def _offer_skill(st, pj, pid: str, clid: str) -> bool:
    """Stil skill-aanbod bij een net toegevoegd checklist-item: match het item-tekst tegen de DNA-skills
    van de owner-rol en, bij een match, hang een aanbod aan het item. UITSLUITEND op de "Uitvoerplan"-
    checklist (de enige die de daemon uitvoert) en alleen bij een echte rol-owner (geen II, geen dangling).
    Draait de match in het cockpit-proces via de ladder; fail-closed — nooit een foutmelding.
    Grens: dit matcht en biedt aan; uitvoeren doet uitsluitend de daemon.

    Elke early-return logt een STABIELE code via refuse() (WARNING, laag volume — het pad draait alleen
    bij een menselijke check_add). Zonder deze regels kost "waarom geen aanbod?" uren gis-diagnose: de
    fail-closed maakte II/title-gate/geen-record/geen-DNA/geen-match/exceptie ononderscheidbaar in het log."""
    p = pj.get(pid) or {}
    owner = p.get("owner") or ""
    if not owner or owner.startswith(_II_PREFIX):        # II / geen owner → geen rol-DNA
        return refuse("OFFER_SKIP_II", "geen rol-owner (II/dangling) → geen skill-match", pid=pid, owner=owner)
    cl = next((c for c in (p.get("checklists") or []) if c.get("id") == clid), None)
    if cl is None:
        return refuse("OFFER_SKIP_NO_CL", "checklist niet gevonden op project", pid=pid, clid=clid)
    if cl.get("title") != PREP_CHECKLIST_TITLE:          # alleen de uitvoer-checklist
        return refuse("OFFER_SKIP_TITLE", "niet de Uitvoerplan-checklist → geen aanbod (title-gate)",
                      pid=pid, clid=clid, title=cl.get("title"))
    items = cl.get("items") or []
    if not items:
        return refuse("OFFER_SKIP_EMPTY", "Uitvoerplan leeg", pid=pid, clid=clid)
    item = items[-1]                                     # het net toegevoegde item (append't, dus laatste)
    if item.get("skill") or item.get("offer"):
        return refuse("OFFER_SKIP_HAS", "laatste item heeft al skill/offer", pid=pid, item=item.get("id"))
    orec = st.records.get(owner)
    if orec is None:                                     # owner-id matcht geen record → geen DNA-lookup mogelijk
        return refuse("OFFER_NO_RECORD", "owner-record niet gevonden in records", pid=pid, owner=owner)
    _load_env()                                          # LLM-keys beschikbaar maken (zoals bij _ai_reply)
    offers = plan_offers(orec, [item.get("text", "")], shared_registry(), name=_name(orec))
    off = offers[0] if offers else None
    if not off:                                          # geen match (plan_offers logt LLM-None/-exceptie apart)
        return refuse("OFFER_NO_MATCH", "geen DNA-skill matcht het item", pid=pid, owner=owner,
                      text=(item.get("text", "") or "")[:80])
    return pj.set_item_offer(pid, clid, item["id"], off)   # succes: het aanbod verschijnt in de UI


def _act_check_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.check_add(g("pid"), g("clid"), g("text")):
            msg = "✓ item toegevoegd"
            try:                                         # skill-aanbod is bijzaak: mag de toevoeging nooit breken
                if _offer_skill(st, pj, g("pid"), g("clid")):
                    msg += " · 🤖 aanbod"
            except Exception as e:                       # bv. een stille registry-bouwfout: niet meer onzichtbaar
                refuse("OFFER_UNCAUGHT", "skill-aanbod wierp een exceptie (weggevangen)",
                       pid=g("pid"), exc=type(e).__name__)
        return nxt, msg


def _act_check_accept(c):
        # AUTHZ: rolvervuller of Circle Lead — operationeel werk binnen een rol (een skill aan een item hangen)
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        msg = "🤖 opgepakt door de rol" if pj.accept_item_offer(g("pid"), g("clid"), g("item")) else ""
        return nxt, msg


def _act_check_toggle(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.check_toggle(g("pid"), g("clid"), g("item"))
        return nxt, msg


def _act_check_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.check_remove(g("pid"), g("clid"), g("item")); msg = "🗑 item verwijderd"
        return nxt, msg


def _act_role_assign(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_role_unassign(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_role_focus(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_radar_set(c, status: str, ok_msg: str):
        """Radar-signaal goedkeuren/wegklikken. Poort op de EIGEN rol van het item (niet op een
        meegestuurde rol), zodat alleen de rolvervuller of Circle Lead cureert."""
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        it = st.radar.get(g("rid"))
        if it is None:
            return nxt, "✗ onbekend radar-signaal"
        _deny = _role_gate(it["role"], username, st)
        if _deny:
            return nxt, _deny
        st.radar.set_status(g("rid"), status)
        return nxt, ok_msg


def _act_radar_approve(c):
        return _act_radar_set(c, "goedgekeurd", "✓ aan het archief toegevoegd")


def _act_radar_dismiss(c):
        return _act_radar_set(c, "afgewezen", "🗑 signaal weggeklikt")


def _act_aitask_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_aitask_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_persona_skill_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag persona-skills toevoegen"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        if st.personas.add_skill(g("agent"), g("skill")):
            msg = "✓ skill aan rugzak toegevoegd"
        return nxt, msg


def _act_rov2_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: elk cirkellid mag een voorstel op de agenda brengen
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if _rov_add_item(st, g("circle"), g("naam")):
            msg = "✓ agendapunt toegevoegd"
        return nxt, msg


def _act_rov2_add_to_group(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: elk cirkellid mag aan een voorstel bijdragen
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if _rov_add_item(st, g("circle"), g("naam"), group=g("group")):
            msg = "✓ toegevoegd aan voorstel"
        return nxt, msg


def _act_rov2_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        st.agenda.remove(g("iid")); msg = "🗑 uit voorstel verwijderd"
        return nxt, msg


def _act_rov2_remove_group(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_rov2_setkind(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: cirkellid mag het type van zijn eigen voorstel vormgeven
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("kind") in ("amend_role", "remove_role"):
            st.agenda.update_fields(g("iid"), kind=g("kind"))
            msg = "voorstel: rol verwijderen" if g("kind") == "remove_role" else "voorstel: rol wijzigen"
        return nxt, msg


def _act_rov2_consent(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_rov2_end(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "Geen toegang — alleen Circle Lead mag dit"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        done = _rov_apply(st)
        # Sluiten = de vergadering écht afronden: haal de resterende (onbehandelde) agendapunten van
        # DEZE cirkel van de agenda, zodat de "Governance meeting"-knop niet groen blijft hangen door
        # open punten. Niet-geconsenteerde voorstellen vervallen; opnieuw indienen kan altijd.
        cleared = _rov_items(st, circle_id)
        for it in cleared:
            st.agenda.remove(it["id"])
        msg = f"✓ overleg gesloten — {len(done)} doorgevoerd"
        if cleared:
            msg += f", {len(cleared)} onbehandeld punt van de agenda gehaald"
        return nxt, msg


def _act_wo_open(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.open(g("circle")); msg = "✓ werkoverleg gestart"
        return nxt, msg


def _act_wo_close(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.close(g("circle"))
        # dag-observatie (tevredenheid + duur) van dit overleg wegschrijven — idempotent per dag,
        # naast de bestaande all-time aggregaten in de log.
        _lg = st.werk.log(g("circle"))
        if _lg:
            observations.record_werk_daily(st.observations, g("circle"), _lg[-1])
        msg = "✓ werkoverleg gesloten"
        return nxt, msg


def _act_wo_presence(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.set_presence(g("circle"), g("pid"), g("present") == "1")
        msg = "✓ aanwezig" if g("present") == "1" else "✗ afwezig (taken gepauzeerd)"
        return nxt, msg


def _act_wo_present_all(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        for p in _members_of_circle(st, g("circle")):
            st.werk.set_presence(g("circle"), p.id, True)
        msg = "✓ allen aanwezig"
        return nxt, msg


def _act_wo_ag_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        naam, by = _rov_initials(g("naam"))
        if st.werk.agenda_add(g("circle"), naam, by=by):
            msg = "✓ spanning op de agenda"
        return nxt, msg


def _act_wo_ag_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.agenda_remove(g("circle"), g("iid")); msg = "🗑 verwijderd"
        return nxt, msg


def _act_wo_ag_note(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("field") in ("spanning", "role", "need"):
            st.werk.agenda_set_note(g("circle"), g("iid"), **{g("field"): g("value")})
            msg = "✓ genoteerd"
        return nxt, msg


def _act_wo_ag_reopen(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        it = st.werk.agenda_get(g("circle"), g("iid"))
        if it is not None:
            it["status"] = "open"; it["outcome"] = None; st.werk._save()
            msg = "↺ heropend"
        return nxt, msg


# ── Gedeelde uitkomst-routes (reference, don't copy) ───────────────────────────────
# Eén plek waar een uitkomst naar de BESTAANDE stores schrijft. Gebruikt door zowel het
# werkoverleg (_act_wo_ag_resolve) als de wall-outcome-flow (_act_wall_outcome). `provenance`
# (herkomst) reist mee waar de bron een wall-comment is; het werkoverleg heeft zijn eigen audit
# (de agenda) en laat 'm leeg. Zo dupliceren we de routing-logica niet.

def _prov_feed(st, pid: str, provenance: str, actor_id: str = "") -> None:
    """Leg herkomst/rationale vast als neutrale systeem-entry op een project. No-op zonder herkomst
    of pid (dan draagt de agenda de audit — werkoverleg)."""
    if pid and provenance:
        st.projects.add_feed_entry(pid, provenance, kind="system", author_type="human", author_id=actor_id)


def _outcome_info(st, detail: str, by: str = "", *, src_pid: str = "", src_eid: str = ""):
    """Info → notificatie(s), @-gericht (rol/persoon), anders niemand. Herkomst reist mee in de
    notif-payload (project_id/entry_id). Retourneert (doel-omschrijving, mentions)."""
    _, by_name = _mentionables(st)
    ment = _mentions_in(detail, by_name)
    for ty, tid, _nm in ment:
        st.notif.add(ty, tid, src_pid, src_eid, by=by or "werkoverleg", snippet=detail)
    tgt = ", ".join(nm for _, _, nm in ment) if ment else "iedereen"
    return tgt, ment


def _outcome_project(st, owner: str, title: str, *, provenance: str = "", actor_id: str = "") -> str:
    """Project → nieuw project op `owner` (trigger 'human'). Herkomst als eerste systeem-entry."""
    pid = st.projects.create(owner, (title or "").strip()[:200], "human")
    _prov_feed(st, pid, provenance, actor_id)
    return pid


def _outcome_action(st, pid_link: str, title: str):
    """Action → checklist-item 'Acties uit overleg' op een bestaand project. Retourneert de checklist of None.
    LET OP: doet zelf GEEN reopen — de wall-flow reopent ná dit item (harde rand: item eerst, dán reopen)."""
    p = st.projects.get(pid_link)
    if p is None:
        return None
    cl = next((cc for cc in (p.get("checklists") or []) if cc.get("title") == "Acties uit overleg"), None)
    if cl is None:
        cl = st.projects.checklist_add(pid_link, "Acties uit overleg")
    if cl:
        st.projects.check_add(pid_link, cl["id"], (title or "").strip())
    return cl


def _outcome_note(st, note_role: str, body: str, *, actor_id: str = "", change_note: str = ""):
    """Note → artefact kind='note' op een rol. De caller checkt len(body) <= 4000 VOORAF (geen truncatie)."""
    return st.att.add(note_role, "note", body=body, actor_id=actor_id,
                      actor_type="person", change_note=change_note or "aangemaakt")


def _outcome_roloverleg(st, circle: str, name: str, title: str, detail: str,
                        by: str = "", *, provenance: str = "") -> str:
    """Roloverleg → add_role-voorstel op de roloverleg-agenda (mens-route via Secretary, NIET de
    autonome Facilitator/G0-G4). Herkomst in het `example`-veld van het voorstel."""
    slug = re.sub(r"[^a-z0-9]+", "_", (detail or "").lower()).strip("_")[:40] or "punt"
    return st.agenda.add(f"{circle}__{slug}", "add_role",
                         {"name": name or "Nieuwe rol", "new_role_parent": circle,
                          "purpose": "", "add_accountabilities": []},
                         detail, by=by or "werkoverleg", title=title or (detail or "")[:60],
                         example=provenance)


def _act_wo_ag_resolve(c):
        nxt, st, g, username, action = c.nxt, c.st, c.g, c.username, c.action
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        otype, detail = g("otype"), g("detail")
        it = st.werk.agenda_get(g("circle"), g("iid"))
        if otype == "info":
            # richting (delen/nodig) + @-targeting: gericht aan rol/persoon, anders iedereen
            dr = g("dir") or "delen"
            tgt, _ment = _outcome_info(st, detail, by="werkoverleg")
            detail = f"{dr} ({tgt}): {detail.strip()}"
        elif otype == "project" and g("owner") and detail.strip():
            _outcome_project(st, g("owner"), detail.strip())
            detail = f"{detail.strip()} → {_name(st.records.get(g('owner')))}"
        elif otype == "action" and g("pid_link") and detail.strip():
            if _outcome_action(st, g("pid_link"), detail.strip()) is not None:
                detail = f"{detail.strip()} → project"
        elif otype == "roloverleg" and detail.strip():
            by = (it or {}).get("by") or "werkoverleg"   # ingebracht door de indiener van de spanning
            _outcome_roloverleg(st, g("circle"), (it or {}).get("title", "Nieuwe rol"),
                                (it or {}).get("title", detail[:60]), detail.strip(), by=by)
        st.werk.agenda_resolve(g("circle"), g("iid"), otype, detail)
        return nxt, f"✓ verwerkt als {otype}"


def _act_wall_outcome(c):
        # Mens routeert een wall-comment naar één van de vijf bestaande uitkomsten (dezelfde routes als
        # het werkoverleg, via de gedeelde _outcome_*-helpers). Puur mens-gestuurd: geen LLM, geen
        # persona-voorstellen (dat is deel 2). HERKOMST is verplicht: elke uitkomst draagt de bron-comment
        # mee (feed-entry / change_note / notif-payload). GEEN bus-events — cross-proces, zie de
        # netwerk-bus-naad; consistent met _act_proj_done (mens-routing behoeft geen aankondiging).
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        otype = g("otype")
        src_pid, src_eid = g("pid"), g("item")
        content = (g("content") or "").strip()       # bewerkbaar inhoud-veld, voorgevuld met de comment-tekst
        # Herkomst verplicht: zonder geldige bron-comment geen uitkomst.
        src_p = pj.get(src_pid)
        src_entry = next((e for e in (src_p or {}).get("log", []) if e.get("id") == src_eid), None) if src_p else None
        if src_p is None or src_entry is None:
            return nxt, "✗ bron-comment niet gevonden — een uitkomst vereist herkomst"
        if not content:
            return nxt, "✗ inhoud is verplicht"
        actor = st.people.by_email(username)
        aid = actor.id if actor else ""
        prov = f"↳ uit wall-comment op {src_pid}#{src_eid}"   # herkomst (geen verplichte rationale)
        title = content[:60]
        _LBL = {"info": "info gedeeld", "project": "project", "action": "actie",
                "note": "note", "roloverleg": "roloverleg-punt"}

        if otype == "info":
            # AUTHZ: circle-member of iedereen-ingelogd — info delen binnen de cirkel raakt geen structuur
            circle = resolve_circle_id(src_p.get("owner") or "", st.records)
            _deny = _member_gate(circle, username, st)
            if _deny:
                return nxt, _deny
            _outcome_info(st, content, by=f"wall:{src_pid}", src_pid=src_pid, src_eid=src_eid)

        elif otype == "project":
            # AUTHZ: rolvervuller of Circle Lead — een project aanmaken raakt de rol/cirkel van de eigenaar
            owner = g("owner")
            if not owner:
                return nxt, "✗ kies een rol-eigenaar voor het project"
            _deny = (_member_gate(resolve_circle_id(owner, st.records), username, st)
                     if owner.startswith(_II_PREFIX) else _role_gate(owner, username, st))
            if _deny:
                return nxt, _deny
            orec = st.records.get(owner)
            if orec is not None and org.is_circle(orec):
                return nxt, "✗ een cirkel kan geen project bevatten — kies een rol of Individueel Initiatief"
            _outcome_project(st, owner, content, provenance=prov, actor_id=aid)

        elif otype == "action":
            # AUTHZ: rolvervuller of Circle Lead — een actie toevoegen raakt het doel-project van de eigenaar
            pid_link = g("pid_link")
            tgt = pj.get(pid_link)
            if tgt is None:
                return nxt, "✗ doel-project niet gevonden"
            _deny = _role_gate(tgt.get("owner") or "", username, st)
            if _deny:
                return nxt, _deny
            # HARDE RAND 1: eerst het checklist-item toevoegen, DÁN reopen — nooit andersom. reopen wist
            # outcome; met een compleet ge-vinkte checklist zou de puls het project meteen weer op DONE
            # zetten met een vals project_completed-event. Het nieuwe (open) item maakt de checklist
            # incompleet, zodat reopen veilig is. reopen() is een no-op als het project niet terminal is.
            _outcome_action(st, pid_link, content)
            _prov_feed(st, pid_link, prov, aid)      # herkomst op het doel-project
            pj.reopen(pid_link)

        elif otype == "note":
            # AUTHZ: rolvervuller of Circle Lead — een note is een artefact bij de rol (_artefact_gate)
            note_role = g("note_role")
            if not note_role:
                return nxt, "✗ kies een rol voor de note"
            _deny = _artefact_gate(note_role, username, st)
            if _deny:
                return nxt, _deny
            # HARDE RAND note: >4000 tekens → weigeren met melding, geen stille truncatie.
            if len(content) > 4000:
                return nxt, f"✗ note te lang ({len(content)}/4000 tekens) — kort in; geen automatische afkap"
            _outcome_note(st, note_role, content, actor_id=aid, change_note=prov)

        elif otype == "roloverleg":
            # AUTHZ: circle-member — een punt voor het roloverleg agenderen mag elk cirkellid
            circle = resolve_circle_id(src_p.get("owner") or "", st.records)
            _deny = _member_gate(circle, username, st)
            if _deny:
                return nxt, _deny
            _outcome_roloverleg(st, circle, title, title, content, by=f"wall:{src_pid}", provenance=prov)

        else:
            return nxt, "✗ onbekende uitkomst"

        # Systeem-entry op de BRON-wall: de audittrail (met herkomst) leeft op de wall.
        pj.add_feed_entry(src_pid, f"→ {_LBL[otype]} aangemaakt: {title}",
                          kind="system", author_type="human", author_id=aid)
        # Kwam dit uit de inbox (nid meegegeven)? Dan is die mention nu verwerkt: leg de uitkomst + reden
        # vast als historie en haal 'm uit de nieuw/gelezen-wachtrij. Eén klik: uitkomst maken én afvinken.
        nid = (g("nid") or "").strip()
        if nid:
            st.notif.mark_item_processed(nid, outcome=f"{_LBL[otype]}: {title}", by=_person_name(st, aid))
        return nxt, f"✓ {_LBL[otype]} aangemaakt"


def _act_notif_read(c):
        c.st.notif.mark_item_read(c.g("nid"))
        return c.nxt, "✓ gemarkeerd als gelezen"


def _act_notif_processed(c):
        c.st.notif.mark_item_processed(c.g("nid"))
        return c.nxt, "✓ verwerkt"


def _act_notif_delete(c):
        # Prullenbak: ruis die je niet wilt verwerken uit de wachtrij halen (zacht, dismissed-vlag).
        ok = c.st.notif.delete_item(c.g("nid"))
        return c.nxt, ("🗑 weggegooid" if ok else "✗ item niet gevonden")


def _act_metrics2_fav(c):
        # Favoriet = een tegel op de node (bestaand mechanisme). Gate: cirkellid.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(resolve_circle_id(g("node"), st.records), username, st)
        if _deny:
            return nxt, _deny
        tile = st.metrics.add_tile(g("node"), g("source"), g("measure"), g("dim") or "none", g("form") or "getal")
        return nxt, ("★ op je dashboard" if tile else "✗ kon niet toevoegen")


def _act_metrics2_unfav(c):
        ok = c.st.metrics.remove_tile(c.g("node"), c.g("tid"))
        return c.nxt, ("verwijderd van je dashboard" if ok else "✗ niet gevonden")


def _act_metrics2_form(c):
        # Weergave-schakelaar: de vorm van een tegel wisselen (view losgekoppeld van data).
        ok = c.st.metrics.set_tile_form(c.g("node"), c.g("tid"), c.g("form"))
        return c.nxt, ("weergave gewijzigd" if ok else "✗ niet gevonden")


def _act_metrics2_dim(c):
        # Segmentatie: de dimensie van een tegel wisselen (bv. per land / per product / over tijd).
        # De view stuurt een passende vorm mee (segmentatie bepaalt welke weergaves kloppen).
        ok = c.st.metrics.set_tile_dim(c.g("node"), c.g("tid"), c.g("dim"), c.g("form"))
        return c.nxt, ("gesegmenteerd" if ok else "✗ niet gevonden")


def _act_metrics2_compare(c):
        # Metric-vs-metric: een tweede meting koppelen (combo staaf+lijn) of leeg → vergelijking eraf.
        g = c.g
        ok = c.st.metrics.set_tile_compare(g("node"), g("tid"), g("cmp_source"),
                                           g("cmp_measure"), g("cmp_dim") or "over_tijd")
        return c.nxt, ("vergelijking ingesteld" if ok else "✗ niet gevonden")


def _act_acc_check(c):
        # Dorpsbrede accountability-check (dubbelingen + formulering) via één LLM-call; bewaart de uitkomst.
        if c.username in (None, "guest"):
            return c.nxt, "✗ niet toegestaan"
        from nooch_village.skills_impl.accountability_check import check_accountabilities
        from nooch_village.views.accountabilities import roles_with_accountabilities
        from nooch_village import llm
        roles = roles_with_accountabilities(c.st)
        res = check_accountabilities(
            roles, lambda p: llm.reason(p, call_site="cockpit_accountability_check"))
        try:
            with open(os.path.join(c.data_dir, "accountability_check.json"), "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False)
        except Exception:
            pass
        n = len(res.get("duplicates") or []) + len(res.get("weak") or [])
        return c.nxt, f"check klaar: {n} aandachtspunt(en)"


def _act_link_pursue(c):
        # Linkbuilding-doelwit op 'pitchen' zetten (geborgd in cockpit 2).
        if c.username in (None, "guest"):
            return c.nxt, "✗ niet toegestaan"
        from nooch_village.link_targets import LinkTargets
        store = LinkTargets(os.path.join(c.data_dir, "linkbuilding_targets.json"))
        ok = store.pursue((c.g("link") or "").strip())
        return c.nxt, ("→ wordt gepitcht" if ok else "✗ niet gevonden")


def _act_link_ignore(c):
        if c.username in (None, "guest"):
            return c.nxt, "✗ niet toegestaan"
        from nooch_village.link_targets import LinkTargets
        store = LinkTargets(os.path.join(c.data_dir, "linkbuilding_targets.json"))
        ok = store.ignore((c.g("link") or "").strip())
        return c.nxt, ("genegeerd" if ok else "✗ niet gevonden")


def _act_source_activate(c):
        # Externe bron aanzetten (mens-gated). Haalt pas bij de volgende pulse data op.
        src = (c.g("source") or "").strip()
        if not src or c.username in (None, "guest"):
            return c.nxt, "✗ niet toegestaan"
        c.st.sources.set_active(src, True)
        return c.nxt, f"✓ {src} staat aan (data volgt bij de volgende pulse)"


def _act_source_deactivate(c):
        src = (c.g("source") or "").strip()
        if not src or c.username in (None, "guest"):
            return c.nxt, "✗ niet toegestaan"
        c.st.sources.set_active(src, False)
        return c.nxt, f"○ {src} staat uit"


def _act_metrics2_formula(c):
        # Eigen formule van twee bestaande reeks-metingen (A op B per dag), als formule-tegel.
        st, g, username = c.st, c.g, c.username
        _deny = _member_gate(resolve_circle_id(g("node"), st.records), username, st)
        if _deny:
            return c.nxt, _deny
        f_a, f_b, f_op = g("f_a"), g("f_b"), g("f_op") or "÷"
        f_name, f_agg = g("f_name").strip(), g("f_agg") or "gemiddelde"
        if not (f_a and f_b and f_name):
            return c.nxt, "Formule: kies meting A, meting B en een naam"
        t = st.metrics.add_tile(g("node"), "formule", f_name, "none", "formule",
                                extra={"f_a": f_a, "f_op": f_op, "f_b": f_b, "aggregatie": f_agg})
        return c.nxt, ("✓ formule op je dashboard" if t else "⛔ kon formule niet maken")


def _act_notif_add(c):
        # Zelf een spanning toevoegen (GlassFrog-capture): vrij tekstveld + vanuit welke rol je 'm voelt.
        # Landt in je eigen inbox om daarna te verwerken. Leeg → niets.
        st, g, username = c.st, c.g, c.username
        text = (g("text") or "").strip()
        role = (g("role") or "").strip()
        if not text:
            return c.nxt, "✗ lege spanning"
        if role and st.records.get(role) is not None:
            st.notif.add("role", role, "", by="zelf", snippet=text)
        else:
            actor = st.people.by_email(username) if username and username != "guest" else None
            st.notif.add("person", actor.id if actor else "guest", "", by="zelf", snippet=text)
        return c.nxt, "✓ spanning toegevoegd"


def _act_notif_klaar(c):
        # 'Klaar met deze spanning': het ENIGE sluitmodel. Sloot je met nul uitkomsten, dan legt de handler
        # zelf 'geen uitkomst' vast (zichtbaar voor de raadsvergadering). Redirect naar de inbox met de
        # zojuist-verwerkte spanning gemarkeerd — een klein viermoment.
        st, nid = c.st, c.g("nid")
        n = st.notif._find(nid)
        if n is not None and not st.notif.verwerkingen_of(n):
            st.notif.add_outcome(nid, intent="none", otype="none", label="geen uitkomst")
        actor = st.people.by_email(c.username) if c.username and c.username != "guest" else None
        by = _person_name(st, actor.id) if actor else ""
        st.notif.mark_done(nid, by=by)
        return f"/inbox?done={nid}", "✓ klaar met deze spanning 🎉"


def _act_notif_outcome(c):
        # Eén uitkomst vastleggen vanuit de verwerk-wizard: maak 'm via dezelfde _outcome_*-helpers als de
        # wall (met de bron-spanning als herkomst) ÉN voeg 'm toe aan het verwerk-record. Sluit het item
        # NIET — zo kun je meerdere uitkomsten op één spanning stapelen; 'Klaar' sluit pas.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        from nooch_village.inbox_wizard import intent_of, OTYPE_LABEL
        nid = g("nid")
        n = st.notif._find(nid)
        if n is None:
            return nxt, "✗ spanning niet gevonden"
        otype = g("otype")
        content = (g("content") or "").strip()
        if not content:
            return nxt, "✗ inhoud is verplicht"
        src_pid, src_eid = n.get("project_id", ""), n.get("entry_id", "")
        src_p = pj.get(src_pid) if src_pid else None
        actor = st.people.by_email(username) if username and username != "guest" else None
        aid = actor.id if actor else ""
        by_name = _person_name(st, aid) if aid else (username or "")
        prov = f"↳ uit inbox-spanning {nid}"
        label = OTYPE_LABEL.get(otype, otype)
        made = ""
        if otype == "ping":
            # Ping = een licht pingetje: de inhoud landt als mention in de inbox van de gekozen rol. Geen
            # note, geen overleg. (Iedere ingelogde mag pingen — het is puur een bericht, geen structuur.)
            ping_role = g("ping_role")
            prec = st.records.get(ping_role) if ping_role else None
            if prec is None:
                return nxt, "✗ kies een rol om te pingen"
            st.notif.add("role", ping_role, src_pid, src_eid, by=(by_name or "inbox"), snippet=content)
            made = f"{label} naar {_name(prec)}: {content[:50]}"
        elif otype == "project":
            owner = g("owner")
            if not owner:
                return nxt, "✗ kies een rol-eigenaar voor het project"
            _deny = (_member_gate(resolve_circle_id(owner, st.records), username, st)
                     if owner.startswith(_II_PREFIX) else _role_gate(owner, username, st))
            if _deny:
                return nxt, _deny
            orec = st.records.get(owner)
            if orec is not None and org.is_circle(orec):
                return nxt, "✗ een cirkel kan geen project bevatten — kies een rol"
            _outcome_project(st, owner, content, provenance=prov, actor_id=aid)
            made = f"{label}: {content[:60]}"
        elif otype == "action":
            pid_link = g("pid_link")
            tgt = pj.get(pid_link)
            if tgt is None:
                return nxt, "✗ doel-project niet gevonden"
            _deny = _role_gate(tgt.get("owner") or "", username, st)
            if _deny:
                return nxt, _deny
            _outcome_action(st, pid_link, content)
            _prov_feed(st, pid_link, prov, aid)
            pj.reopen(pid_link)
            made = f"{label}: {content[:60]}"
        elif otype == "note":
            note_role = g("note_role")
            if not note_role:
                return nxt, "✗ kies een rol voor de note"
            _deny = _artefact_gate(note_role, username, st)
            if _deny:
                return nxt, _deny
            if len(content) > 4000:
                return nxt, f"✗ note te lang ({len(content)}/4000) — kort in"
            _outcome_note(st, note_role, content, actor_id=aid, change_note=prov)
            made = f"{label} bij {_name(st.records.get(note_role))}"
        elif otype == "roloverleg":
            if src_p is None:
                return nxt, "✗ geen bron-cirkel voor een roloverleg-punt"
            circle = resolve_circle_id(src_p.get("owner") or "", st.records)
            _deny = _member_gate(circle, username, st)
            if _deny:
                return nxt, _deny
            _outcome_roloverleg(st, circle, content[:60], content[:60], content,
                                by=f"inbox:{nid}", provenance=prov)
            made = f"{label}: {content[:60]}"
        else:
            return nxt, "✗ onbekende uitkomst"
        # Audittrail op de bron-wall (als er een bron is) + de uitkomst in het verwerk-record.
        if src_pid:
            pj.add_feed_entry(src_pid, f"→ {label} aangemaakt uit inbox: {content[:60]}",
                              kind="system", author_type="human", author_id=aid)
        st.notif.add_outcome(nid, intent=intent_of(otype), otype=otype, label=made, by=by_name)
        return nxt, f"✓ {label} vastgelegd — nog een uitkomst, of klik Klaar."


def _act_notif_archive(c):
        ok = c.st.notif.archive_item(c.g("nid"))
        return c.nxt, ("🗄 gearchiveerd" if ok else "⛔ alleen verwerkte items kunnen worden gearchiveerd")


def _act_wo_checkout(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("score"):
            ok = st.werk.set_checkout(g("circle"), g("pid"), g("score"))
            msg = "✓ score genoteerd" if ok else "⛔ score geweigerd — het overleg is niet (meer) open"
        return nxt, msg


def _act_noochie_send(c):
        nxt, st, g = c.nxt, c.st, c.g
        msg = ""
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
        return nxt, msg


def _act_noochie_reset(c):
        nxt, st = c.nxt, c.st
        msg = ""
        st.noochie.reset(); msg = "↺ Noochie opnieuw"
        return nxt, msg


def _act_noochie_ctx(c):
        nxt, st, g = c.nxt, c.st, c.g
        msg = ""
        st.noochie.set_field("ctx", g("ctx")); msg = "✓ context bijgewerkt"
        return nxt, msg


def _act_cl_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_cl_report(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead van de betrokken rol/cirkel — afvinken van een
        # checklist-item (namens de rol/cirkel bij target_type=all). by = wie afvinkte (de mens;
        # een AI-flow kan report() direct met by=<persona> aanroepen). Geen per-individu-verplichting.
        _deny = _role_gate((st.checklists.get(g("cid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        if st.checklists.report(g("cid"), g("ok") == "1", value=g("value"),
                                by=(username or "founder")):
            msg = "✓ genoteerd" if g("ok") == "1" else "✗ genoteerd (aandacht nodig)"
        return nxt, msg


def _act_cl_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate((st.checklists.get(g("cid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        st.checklists.remove(g("cid")); msg = "🗑 checklist-item verwijderd"
        return nxt, msg


def _act_m_add_kpi(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_m_add_from_def(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        did = g("def_id")
        if not did and g("def_name"):
            d = st.defs.by_name(g("def_name"))
            did = d["id"] if d else ""
        kid = _kpi_id_from_def(st, g("node"), did)
        msg = "✓ KPI uit catalogus toegevoegd" if kid else "⛔ kies een bestaande definitie uit de catalogus"
        return nxt, msg


def _act_def_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_catalog_publish(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: anchor-lead — cureert welke ruwe velden een gebruiker als indicator mag kiezen
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "Geen toegang — alleen anchor-lead mag de catalogus koppelen"
        if actor is None and username != "guest":
            return nxt, "Geen toegang — gebruiker niet herkend"
        # ── einde autorisatie ──
        naam, categorie, aard = g("naam").strip(), g("categorie").strip(), g("aard").strip()
        source, veld = g("source").strip(), g("veld").strip()
        if not (naam and categorie and aard):
            return nxt, "Naam, categorie en aard zijn verplicht"
        already = any((st.defs.current(d["id"]) or {}).get("source") == source
                      and (st.defs.current(d["id"]) or {}).get("veld") == veld for d in st.defs.all())
        if already:
            return nxt, "Dit veld staat al in de catalogus"
        # Scope-3-schema: aard expliciet; aggregatie leeg + formule=False (geen formule-veld hier).
        d = st.defs.add(naam, owner="anchor-lead", provenance="curated",
                        source=source, veld=veld, categorie=categorie, aard=aard,
                        unit=g("unit"), definition=g("definition"), meetwijze="systeem")
        msg = f"✓ ‘{naam}’ in de catalogus" if d else "Publiceren mislukt (ongeldige invoer)"
        return nxt, msg


def _act_def_amend(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_m_add_link(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        it = st.metrics.add_link(g("node"), g("name"), g("url"))
        msg = "✓ link toegevoegd" if it else "⛔ geef naam en URL"
        return nxt, msg


def _act_m_sample(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate((st.metrics.get(g("mid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        msg = "✓ meting genoteerd" if st.metrics.add_sample(g("mid"), g("value")) else "⛔ ongeldige meting"
        return nxt, msg


def _act_m_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate((st.metrics.get(g("mid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        st.metrics.remove(g("mid")); msg = "🗑 metric verwijderd"
        return nxt, msg


def _act_m_pin(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: het cirkeldashboard beheren is Circle Lead-werk
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.pin(g("circle"), g("mid")); msg = "✓ op cirkeldashboard"
        return nxt, msg


def _act_m_unpin(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.unpin(g("circle"), g("mid")); msg = "✓ van dashboard gehaald"
        return nxt, msg


def _act_indicator_activate(c):
        # AUTHZ: circle-member-of-iedereen-ingelogd — open-books-besluit: iedereen met catalogus-toegang mag
        # een indicator MÉT data op een rol/cirkel-dashboard activeren (bewust ongated). Wie/wat/wanneer
        # wordt wél geregistreerd in de audit-trail (system_log.jsonl).
        nxt, st, username = c.nxt, c.st, c.username
        node = c.g("node")
        dids = [d for d in (c.form.get("did") or []) if d]
        if not node or not dids:
            return nxt, "⛔ kies minstens één indicator en een dashboard"
        added = 0
        for did in dids:
            kid = _kpi_id_from_def(st, node, did)
            if not kid:
                continue
            cur = st.defs.current(did) or {}
            dim = "time" if cur.get("aard") == "reeks" else "none"   # reeks → grafiek, moment → los getal
            if st.metrics.add_tile(node, f"kpi:{kid}", "value", dim, _default_form(dim)):
                added += 1
        try:                                    # geen bus in dispatch → direct naar de audit-trail
            with open(os.path.join(st.dd, "system_log.jsonl"), "a") as f:
                f.write(json.dumps({"event": "indicator_activated", "by": username or "?",
                                    "node": node, "def_ids": dids, "at": time.time()},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
        return nxt, (f"✓ {added} indicator(en) geactiveerd op het dashboard" if added else "⛔ niets geactiveerd")


def _act_tile_add(c):
        nxt, st, g, form, username = c.nxt, c.st, c.g, c.form, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        if g("mode") == "formule":       # scope 5: formule = A op B + aggregatie (opslag; berekening volgt)
            f_a, f_op, f_b = g("f_a"), g("f_op"), g("f_b")
            f_name, f_agg = g("f_name").strip(), g("f_agg")
            if not (f_a and f_b and f_name and f_agg):
                return nxt, "Formule: kies metric A, metric B, een naam én een aggregatie"
            t = st.metrics.add_tile(g("node"), "formule", f_name, "none", "formule",
                                    extra={"f_a": f_a, "f_op": f_op, "f_b": f_b, "aggregatie": f_agg})
            msg = "✓ formule-KPI op dashboard (berekening volgt)" if t else "⛔ kon formule niet maken"
        else:
            combo = g("combo") or ""
            if combo.startswith("def:"):     # indicator direct uit de catalogus → zet als KPI op de node
                did = combo[4:]
                kid = _kpi_id_from_def(st, g("node"), did)
                cur = st.defs.current(did) or {}
                dim = "time" if cur.get("aard") == "reeks" else "none"   # reeks → grafiek, moment → los getal
                combo = f"kpi:{kid}|value|{dim}" if kid else ""
            parts = combo.split("|")
            if len(parts) == 3 and parts[0]:
                ref = g("ref_kind")
                t = st.metrics.add_tile(g("node"), parts[0], parts[1], parts[2], g("form"),
                                        target=g("target"), goal_pid=("" if ref == "benchmark" else g("goal_pid")),
                                        ref_kind=ref)
                msg = "✓ KPI op dashboard" if t else "⛔ kon KPI niet maken"
            else:
                msg = "⛔ kies wat je wilt zien"
        return nxt, msg


def _act_tile_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.remove_tile(g("node"), g("tid")); msg = "🗑 tegel verwijderd"
        return nxt, msg


def _act_rov2_set(c):   # + rov2_acc_add, rov2_acc_remove, rov2_dom_add, rov2_dom_remove
        nxt, st, g, username, action = c.nxt, c.st, c.g, c.username, c.action
        msg = ""
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
        return nxt, msg


def _act_backlog_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: iedereen-ingelogd — elke ingelogde gebruiker mag een backlog-item indienen
        # (de sessie-check in do_POST dekt "ingelogd = mag"; guest = auth uit = mag ook)
        actor = st.people.by_email(username) if username != "guest" else None
        if st.backlog.add(g("titel"), g("beschrijving"), g("type"), g("domein"),
                          actor.id if actor else ""):
            msg = "✓ ingediend in de backlog"
        return nxt, msg


def _act_backlog_update_staat(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: rolvervuller website_developer — beheer van de backlog (staat verplaatsen)
        _deny = _wd_gate(username, st)
        if _deny:
            return nxt, _deny
        if st.backlog.update_staat(g("bid"), g("staat")):
            msg = "✓ staat bijgewerkt"
        return nxt, msg


def _act_backlog_update_prioriteit(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: rolvervuller website_developer — beheer van de backlog (impact/effort)
        _deny = _wd_gate(username, st)
        if _deny:
            return nxt, _deny
        if st.backlog.update_prioriteit(g("bid"), g("impact"), g("effort")):
            msg = "✓ prioriteit bijgewerkt"
        return nxt, msg


def _act_person_edit(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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
        return nxt, msg


def _act_person_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
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


def _act_lk_mute(c):
        # AUTHZ: circle-member of iedereen-ingelogd — muten is een gespreksdaad, geen structuurdaad;
        # toeschouwers zijn uitgesloten via de client-state (observer-tiles zijn niet klikbaar), niet
        # via authz. De sessie-check in do_POST dekt "ingelogd = mag" (guest = auth uit = mag ook).
        nxt, g = c.nxt, c.g
        target = g("identity").strip()
        if not target:
            return nxt, ""
        muted = g("muted") != "0"                 # muted=0 → unmute; anders mute
        ok = livekit_mute_participant(target, muted)
        verb = "gemute" if muted else "ge-unmute"
        return nxt, (f"✓ {verb}" if ok else "muten niet gelukt")


# ── Claims-checker: cureren van de claims-database ───────────────────────────
# De database (`config/claims_database.json`) is het domein van de compliance-rol. Lezen is vrij
# (route /claims/db.json); cureren is exclusief de domein-eigenaar. De juridische inhoud is
# mensenwerk — deze takken schrijven alleen door wat compliance invoert.

def _claims_gate_open(st, username: str | None) -> bool:
    """Mag deze gebruiker de claims-database cureren? Eén definitie voor zowel het tonen van de
    schrijfknoppen als het toestaan van de mutatie — de knop kan dus nooit iets beloven wat de
    dispatch-tak weigert (reference, don't copy)."""
    return _role_gate("compliance", username, st) is None


def _claims_audit(st, username: str | None, event: str, **velden) -> None:
    """Leg de mutatie vast in de bestaande audit-trail. Geen bus in dispatch → direct schrijven."""
    try:
        with open(os.path.join(st.dd, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": event, "by": username or "?", "at": time.time(), **velden},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def _act_claims_term_add(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance-domein: alleen de domein-eigenaar cureert
        # de claims-database.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        db = _claims_db.load()
        try:
            nieuw = _claims_db.add_term(db, term=g("term").strip(), patroon=g("patroon").strip(),
                                        stoplicht=g("stoplicht").strip(),
                                        categorie=g("categorie").strip(),
                                        waarom=g("waarom").strip(),
                                        alternatief=g("alternatief").strip())
        except ValueError as e:
            return nxt, f"⛔ {e}"
        versie = _claims_db.bump_versie(db)
        _claims_db.save(db)
        _claims_audit(st, username, "claims_term_added", term=nieuw["term"],
                      stoplicht=nieuw["stoplicht"], versie=versie)
        return nxt, f"✓ term toegevoegd — database v{versie}"


def _act_claims_work_status(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance-domein: de werklijst-status van een
        # site-fix is een compliance-oordeel, geen open bord.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        db = _claims_db.load()
        try:
            item = _claims_db.set_werk_status(db, int(g("nr") or 0), g("status").strip())
        except (ValueError, TypeError) as e:
            return nxt, f"⛔ {e}"
        versie = _claims_db.bump_versie(db)
        _claims_db.save(db)
        _claims_audit(st, username, "claims_work_status", nr=item["nr"],
                      status=item["status"], versie=versie)
        return nxt, f"✓ #{item['nr']} → {item['status']} — database v{versie}"


# ── Kennisbank (laag 2): inzichten, bewijs-links, gesprek en versies ─────────
# Alle kb_-takken: AUTHZ: iedereen-ingelogd — kennis verzamelen is dorpsbreed (permissieve
# intake, strenge uitgang: de garbage-poort staat bij het GEBRUIK van kennis, niet bij de
# ingang). De herkomst wordt per handeling vastgelegd (by=persoon).

def _kb_actor(c) -> str:
    """Weergavenaam van de handelende mens (de lezer is ook een bron)."""
    if c.username in (None, "guest"):
        return "gast"
    p = c.st.people.by_email(c.username)
    return p.name if p else c.username


def _kb_word(c, iid: str) -> str:
    """Het zekerheids-woord van een inzicht ná een mutatie (voor de bevestiging)."""
    ins = c.st.kennisbank.get(iid)
    if ins is None:
        return ""
    atoms = kb_load_atoms(c.data_dir)
    return KB_WORD_LABEL[kb_verdict(kb_field(ins.get("evidence") or [], atoms))["word"]]


def _act_kb_new(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    title = c.g("title").strip()
    if not title:
        return c.nxt, "✗ typ eerst een claim"
    iid = c.st.kennisbank.add(title, why=c.g("why"), by=_kb_actor(c))
    return f"/kennisbank?id={iid}", "➕ inzicht gemaakt (v1.0) — koppel bewijs en kijk hoe zeker het wordt"


def _act_kb_link(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    iid, atom_id = c.g("iid"), c.g("atom_id")
    if atom_id not in kb_load_atoms(c.data_dir):
        return c.nxt, "✗ kaart niet gevonden in de bibliotheek"
    voor = _kb_word(c, iid)
    ok = c.st.kennisbank.link(iid, atom_id, c.g("stance"),
                              annotation=c.g("annotation"), by=_kb_actor(c))
    if not ok:
        return c.nxt, "✗ koppelen niet gelukt"
    na = _kb_word(c, iid)
    return c.nxt, ("🔗 gekoppeld. " + (f"Zekerheid nu: {na}" if na != voor else "Zekerheid herberekend."))


def _act_kb_unlink(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    iid = c.g("iid")
    voor = _kb_word(c, iid)
    if not c.st.kennisbank.unlink(iid, c.g("atom_id")):
        return c.nxt, "✗ loskoppelen niet gelukt"
    na = _kb_word(c, iid)
    return c.nxt, ("Losgekoppeld (kaart blijft in de bibliotheek). "
                   + (f"Zekerheid nu: {na}" if na != voor else "Zekerheid herberekend."))


def _act_kb_annotate(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    ok = c.st.kennisbank.annotate(c.g("iid"), c.g("atom_id"), c.g("text"))
    return c.nxt, ("💬 notitie opgeslagen" if ok else "✗ notitie niet opgeslagen")


def _act_kb_evidence(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Nieuw bewijs = een nieuw
    # ATOOM in de bibliotheek (laag 1, dom: geen oordeel bij de intake) + een link met richting.
    iid, text = c.g("iid"), c.g("text").strip()
    if not text:
        return c.nxt, "✗ typ eerst iets"
    actor = _kb_actor(c)
    bron = c.g("source").strip() or actor
    # Eigen naam als bron = een intern oordeel (meningssterkte ≠ bewijssterkte);
    # elke andere bron blijft 'unknown' tot een curator de herkomst duidt.
    prov = "internal_judgment" if bron == actor else "unknown"
    atom_id = "atom_" + uuid.uuid4().hex[:8]
    c.st.notes.add(Insight(id=atom_id, claim=text[:500], source=bron, provenance=prov))
    voor = _kb_word(c, iid)
    ok = c.st.kennisbank.link(iid, atom_id, c.g("stance") or "support", by=actor)
    if not ok:
        return c.nxt, "✗ kaart gemaakt maar koppelen niet gelukt"
    na = _kb_word(c, iid)
    return c.nxt, ("➕ toegevoegd. " + (f"Zekerheid nu: {na}" if na != voor else "Zekerheid herberekend."))


def _act_kb_discuss(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    ok = c.st.kennisbank.discuss(c.g("iid"), c.g("text"), _kb_actor(c))
    return c.nxt, ("💬 kanttekening geplaatst" if ok else "✗ typ eerst een kanttekening")


def _act_kb_reformulate(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. De trage klok: claim/
    # reframe/falsifier opnieuw gemunt uit het spel; de vorige versie blijft in history.
    iid = c.g("iid")
    parsed = parse_blok(c.g("blok"))
    if not parsed["claim"]:
        return c.nxt, "✗ kon het blok niet lezen — zorg voor een CLAIM:-regel"
    nieuwe = c.st.kennisbank.reformulate(iid, title=parsed["claim"],
                                         reframe=parsed["reframe"],
                                         falsifier=parsed["falsifier"], by=_kb_actor(c))
    if nieuwe is None:
        return c.nxt, "✗ herformuleren niet gelukt"
    return c.nxt, f"↻ geherformuleerd → v{nieuwe} (vorige versie bewaard)"


def _act_kb_intake(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Fase 2: ruwe tekst →
    # LLM-ladder → atomen, idempotent (hash content+bron) append aan de bibliotheek.
    # Laag 1 blijft dom: geen oordeel, geen veld; trust wordt pas in laag 2 afgeleid.
    uitkomst = kb_intake(c.g("raw"), c.g("source_hint"), c.data_dir)
    if uitkomst is None:
        return c.nxt, "✗ de noteer-hulp gaf geen bruikbaar antwoord — probeer het zo nog eens"
    nieuw, dubbel = uitkomst
    if not nieuw and not dubbel:
        return c.nxt, "✗ typ eerst iets om te noteren"
    if not nieuw:
        return c.nxt, f"Al bekend: {dubbel} notitie(s) stonden er al (niets gedupliceerd)"
    extra = f" ({dubbel} al bekend)" if dubbel else ""
    return (f"/kennisbank?nieuw={','.join(nieuw)}",
            f"✂️ we splitsten dit in {len(nieuw)} notities{extra}")


def _act_kb_intake_url(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. URL = source-adapter:
    # trafilatura haalt de hoofdtekst op, de bestaande atomiser doet de rest (geen fork).
    from nooch_village.kennisbank_sources import van_url
    uit = van_url(c.g("url"))
    if uit is None:
        return c.nxt, "✗ kon deze pagina niet ophalen of er geen leesbare tekst uit halen"
    raw, label = uit
    uitkomst = kb_intake(raw, label, c.data_dir)
    if uitkomst is None:
        return c.nxt, "✗ de noteer-hulp gaf geen bruikbaar antwoord — probeer het zo nog eens"
    nieuw, dubbel = uitkomst
    if not nieuw:
        return c.nxt, f"Al bekend: {dubbel} notitie(s) stonden er al (niets gedupliceerd)"
    extra = f" ({dubbel} al bekend)" if dubbel else ""
    return (f"/kennisbank?nieuw={','.join(nieuw)}",
            f"✂️ we splitsten de pagina in {len(nieuw)} notities{extra}")


def _act_kb_stage_edit(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Staging bewerken vóór commit.
    ok = c.st.staging.edit_atom(c.g("bid"), c.g("sid"), content=c.g("content"),
                                subject=c.g("subject"), provenance=c.g("provenance"))
    return c.nxt, ("✏️ bijgewerkt" if ok else "✗ niet gevonden")


def _act_kb_stage_delete(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.staging.remove_atom(c.g("bid"), c.g("sid"))
    return c.nxt, ("🗑 weggegooid" if ok else "✗ niet gevonden")


def _act_kb_stage_merge(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    sids = [s for s in (c.form.get("sid") or []) if s]
    if len(sids) < 2:
        return c.nxt, "✗ vink minstens twee voorstellen aan"
    if not c.g("kop").strip():
        return c.nxt, "✗ geef de samengestelde kaart een kop"
    ok = c.st.staging.merge_atoms(c.g("bid"), sids, c.g("kop"))
    return c.nxt, ("🧩 samengevoegd" if ok else "✗ samenvoegen niet gelukt")


def _act_kb_stage_commit(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Pas hier landen de
    # nagekeken atomen append-only in de bibliotheek (idempotent op hash content+bron).
    res = commit_batch(c.st.staging, c.g("bid"), c.data_dir)
    if res is None:
        return c.nxt, "✗ deze set bestaat niet meer"
    nieuw, dubbel = res
    if not nieuw:
        return "/kennisbank", (f"Al bekend: {dubbel} notitie(s) stonden er al" if dubbel
                               else "Niets toegevoegd — de set was leeg")
    extra = f" ({dubbel} al bekend)" if dubbel else ""
    return "/kennisbank", f"✅ {nieuw} notities toegevoegd aan de bibliotheek{extra}"


def _act_kb_stage_discard(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.staging.discard(c.g("bid"))
    return "/kennisbank", ("Set weggegooid — niets in de bibliotheek" if ok else "✗ set niet gevonden")


def _act_kb_atoom_edit(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Bewerken-met-historie
    # (PR-2): de vorige claim blijft bewaard in edit_history (append-only, extractie-fouten).
    res = c.st.notes.edit_note(c.g("atom_id"), claim=c.g("claim"))
    return c.nxt, ("✏️ bijgewerkt (vorige versie bewaard)" if res else "✗ bewerken niet gelukt")


def _act_kb_atoom_related(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. "Voeg gerelateerd feit toe":
    # een NIEUW gelinkt atoom met eigen bron (het 36%-geval), geen verrijking-in-place.
    actor = _kb_actor(c)
    bron = c.g("source").strip() or actor
    prov = "internal_judgment" if bron == actor else "unknown"
    res = c.st.notes.add_related(c.g("atom_id"), c.g("content"), bron, provenance=prov)
    if res is None:
        return c.nxt, "✗ kon geen gerelateerd feit toevoegen (leeg, of bestaat al)"
    return c.nxt, "➕ gerelateerd feit toegevoegd en gelinkt"


def _act_kb_insight_link(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. B1: koppel een ander INZICHT
    # als steun/tegen aan het geopende inzicht (de Zettelkasten-ladder → meta-inzicht).
    ok = c.st.kennisbank.link_insight(c.g("iid"), c.g("other_id"), c.g("stance"), by=_kb_actor(c))
    return c.nxt, ("🔗 inzicht gekoppeld" if ok else "✗ koppelen niet gelukt")


def _act_kb_insight_unlink(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.kennisbank.unlink_insight(c.g("iid"), c.g("other_id"))
    return c.nxt, ("ontkoppeld" if ok else "✗ ontkoppelen niet gelukt")


def _act_kb_meta_start(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. B1: speel een META-inzicht —
    # de gekoppelde inzichten van dit inzicht als input aan dezelfde copy-paste-spel-flow.
    src = c.st.kennisbank.get(c.g("iid"))
    if src is None:
        return c.nxt, "✗ inzicht niet gevonden"
    related = src.get("related") or []
    if len(related) < 2:
        return c.nxt, "✗ koppel eerst ≥2 inzichten (steun/tegen) om een meta-inzicht te spelen"
    kaarten = []
    for r in related:
        other = c.st.kennisbank.get(r["insight_id"])
        if other is not None:
            kaarten.append({"atom_id": r["insight_id"], "stance": r.get("stance") or "support",
                            "label": other.get("title") or ""})
    sid = c.st.spel.start(f"Meta-inzicht over: {src.get('title') or ''}", kaarten,
                          by=_kb_actor(c), meta=True)
    return f"/kennisbank/spel?sid={sid}", "🎲 meta-spel gestart — de gekoppelde inzichten zijn de hand"


def _act_kb_atoom_reference(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Een URL als bronlink bij een
    # atoom (A3): landt in het reference-veld. Een expliciet-geplakte bronlink houden we (anders
    # dan de intake-validator, die een kale artikel-URL juist dropt).
    url = c.g("url").strip()
    if not re.match(r"^https?://", url):
        return c.nxt, "✗ plak een geldige URL (https://…)"
    if not c.st.notes.set_reference(c.g("atom_id"), url):
        return c.nxt, "✗ notitie niet gevonden"
    return c.nxt, "🔗 bronlink gekoppeld"


def _act_kb_atoom_subject(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Curatie van het
    # ongesorteerd-bakje: een mens hangt een subject-loze notitie aan een hub.
    subject = c.g("subject")
    if subject not in KB_SUBJECTS:
        return c.nxt, "✗ kies een onderwerp uit de lijst"
    if not c.st.notes.add_tags(c.g("atom_id"), [subject]):
        return c.nxt, "✗ notitie niet gevonden"
    return c.nxt, f"📥 gesorteerd naar '{subject}'"


def _act_kb_atoom_merge(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Curatie (addendum C):
    # selectie → één samengestelde kaart; originelen gearchiveerd met merged_from-terugweg.
    ids = [a for a in (c.form.get("atoom") or []) if a]
    kop = c.g("kop").strip()
    if len(ids) < 2:
        return c.nxt, "✗ selecteer minstens twee notities om samen te voegen"
    if not kop:
        return c.nxt, "✗ geef de samengestelde kaart eerst een kop"
    kaart = c.st.notes.merge(ids, kop, by=_kb_actor(c))
    if kaart is None:
        return c.nxt, "✗ samenvoegen niet gelukt (bestaat deze samenvoeging al?)"
    return c.nxt, (f"🧩 samengevoegd tot één kaart ({len(kaart.merged_from)} originelen "
                   f"bewaard als gearchiveerd)")


def _act_kb_atoom_archive(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Archiveren ≠ wissen.
    ids = [a for a in (c.form.get("atoom") or []) if a] or [c.g("atom_id")]
    ok = sum(1 for aid in ids if aid and c.st.notes.archive(aid))
    if not ok:
        return c.nxt, "✗ selecteer eerst een notitie"
    return c.nxt, f"📦 {ok} notitie(s) gearchiveerd — terug te zetten via 'Gearchiveerd'"


def _act_kb_atoom_unarchive(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.notes.archive(c.g("atom_id"), archived=False)
    return c.nxt, ("↩ teruggezet in de bibliotheek" if ok else "✗ terugzetten niet gelukt")


def _act_kb_atoom_naar_spel(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Selectie voedt de
    # spel-hand (koppeling met de hand-uitbreiding; richting draai je in het spel).
    ids = [a for a in (c.form.get("atoom") or []) if a]
    sid = c.g("sid")
    if not ids:
        return c.nxt, "✗ selecteer eerst een notitie"
    if not sid or c.st.spel.get(sid) is None:
        return c.nxt, "✗ kies een open spel"
    ok = sum(1 for aid in ids if c.st.spel.add_kaart(sid, aid, "support"))
    return f"/kennisbank/spel?sid={sid}", f"🔗 {ok} kaart(en) aan je hand gekoppeld"


def _kb_spel_set(c) -> list[dict]:
    """Gecureerde set uit het formulier: checkboxes `kaart` + per kaart `stance_<id>`."""
    ids = c.form.get("kaart") or []
    return [{"atom_id": aid, "stance": (c.g(f"stance_{aid}") or "support")}
            for aid in ids if aid]


def _act_kb_spel_start(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Start een dialoog
    # met de gecureerde set; bij reformulate_of wordt het een versie-spel.
    kaarten = _kb_spel_set(c)
    hunch = c.g("hunch").strip()
    if not hunch:
        return c.nxt, "✗ typ eerst je vermoeden"
    if not kaarten:
        return c.nxt, "✗ vink minstens één kaart aan"
    sid = c.st.spel.start(hunch, kaarten, reformulate_of=c.g("reformulate_of"),
                          by=_kb_actor(c))
    return f"/kennisbank/spel?sid={sid}", "🎲 spel gestart — de denkpartner opent"


def _act_kb_spel_add(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. De hand uitbreiden
    # (taak 2): idempotent, kaart moet in de bibliotheek bestaan.
    if c.g("atom_id") not in kb_load_atoms(c.data_dir):
        return c.nxt, "✗ kaart niet gevonden in de bibliotheek"
    ok = c.st.spel.add_kaart(c.g("sid"), c.g("atom_id"), c.g("stance") or "support",
                             annotation=c.g("annotation"))
    return c.nxt, ("🔗 gekoppeld aan je hand" if ok else "✗ koppelen niet gelukt")


def _act_kb_spel_remove(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.spel.remove_kaart(c.g("sid"), c.g("atom_id"))
    return c.nxt, ("Verwijderd uit je hand (kaart blijft in de bibliotheek)" if ok
                   else "✗ verwijderen niet gelukt")


def _act_kb_spel_flip(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Richting in één klik.
    ok = c.st.spel.flip_kaart(c.g("sid"), c.g("atom_id"))
    return c.nxt, ("↔ richting gedraaid" if ok else "✗ draaien niet gelukt")


def _act_kb_spel_finish(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Munt het inzicht uit
    # het teruggeplakte blok (copy-paste-spel): v1.0, of versie-bump bij herformuleren.
    res = spel_finish(c.st.spel, c.g("sid"), c.st.kennisbank, c.g("blok"))
    if res is None:
        return c.nxt, "✗ kon het blok niet lezen — zorg voor een CLAIM:-regel"
    iid, versie = res
    woord = ("nieuwe versie v" + versie) if versie != "1.0" else "inzicht gemaakt (v1.0)"
    return f"/kennisbank?id={iid}", f"✓ {woord} — de zekerheid rekent live mee"


def _act_kw_nominate(c):
    # AUTHZ: circle-member of iedereen-ingelogd — iedereen mag een keyword NOMINEREN; het
    # schrijven naar de beschermde woordenschat blijft voorbehouden aan Lara (kw_nom_accept).
    term = c.g("term").strip()
    if not term:
        return c.nxt, "✗ geen keyword opgegeven"
    ok = c.st.nominations.nominate(term, by=_kb_actor(c))
    return c.nxt, (f"🗳 “{term}” genomineerd — Lara beslist" if ok
                   else f"“{term}” staat al in de wachtrij")


def _act_kw_nom_accept(c):
    # AUTHZ: rolvervuller of Circle Lead — alleen de Library-rolvervuller (Lara) schrijft de
    # beschermde woordenschat. _role_gate faalt closed (guest mag; onbekende geweigerd).
    deny = _role_gate("librarian", c.username, c.st)
    if deny:
        return c.nxt, f"✗ {deny}"
    term = c.g("term").strip()
    status = c.g("status") or "approved"          # approved | forbidden
    if status not in ("approved", "forbidden"):
        return c.nxt, "✗ ongeldige status"
    reason = c.g("reason").strip()
    c.st.library.curate(term, status, rationale=reason, by=_kb_actor(c))
    c.st.nom_kroniek.record(role_id=_kb_actor(c), term=term, decision="accept",
                            reason=reason or f"aangenomen als {status}")
    c.st.nominations.remove(term)
    return c.nxt, f"✓ “{term}” geborgd als {status}"


def _act_kw_nom_reject(c):
    # AUTHZ: rolvervuller of Circle Lead — alleen de Library-rolvervuller (Lara) beslist over
    # de woordenschat. Afwijzen dwingt een echte reden af (borging), fail-closed.
    deny = _role_gate("librarian", c.username, c.st)
    if deny:
        return c.nxt, f"✗ {deny}"
    term = c.g("term").strip()
    reason = c.g("reason").strip()
    if not valid_reason(reason):
        return c.nxt, "✗ een afwijzing vereist een echte reden (niet leeg of “n.v.t.”)"
    c.st.nom_kroniek.record(role_id=_kb_actor(c), term=term, decision="reject", reason=reason)
    c.st.nominations.remove(term)
    return c.nxt, f"✗ “{term}” afgewezen — geborgd in de Kroniek"


# ── Woordenschat-beheer (/woordenschat): de mens cureert de Library vanuit cockpit 2 ────────
# AUTHZ: iedereen-ingelogd — de sessie-check in do_POST dekt "ingelogd = mag" (zelfde regel als
# de andere beheer-schrijfacties zonder extra rolcheck). Schrijven loopt uitsluitend via de
# domein-methodes (inbox_actions → Library.curate), nooit in de json. Bewust minimaal:
# alleen verbied + heractiveer/goedkeuren; functie (doelwit/volg) bepaalt de heuristiek zelf.

def _act_ws_curate(c, status: str, ok_msg: str):
    # Gedeelde kern voor pauzeer/verbied/heractiveer: curatie via curate_library_term.
    from nooch_village.inbox_actions import curate_library_term
    res = curate_library_term(c.st.library, c.g("word"), status,
                              reason=c.g("reason"), by=_kb_actor(c))
    return c.nxt, (ok_msg.format(word=res["word"]) if res.get("ok")
                   else f"✗ {res.get('error')}")


def _act_ws_forbid(c):
    # Verbieden: status → forbidden; zonder reden geldt de default-rationale in curate_library_term.
    return _act_ws_curate(c, "forbidden", "✗ “{word}” verboden")


def _act_ws_approve(c):
    # Heractiveren (of geëscaleerd goedkeuren): status → approved.
    return _act_ws_curate(c, "approved", "✓ “{word}” geactiveerd (approved)")


ACTIONS = {
    "kb_new": _act_kb_new,
    "kb_intake": _act_kb_intake,
    "kb_intake_url": _act_kb_intake_url,
    "kb_stage_edit": _act_kb_stage_edit,
    "kb_stage_delete": _act_kb_stage_delete,
    "kb_stage_merge": _act_kb_stage_merge,
    "kb_stage_commit": _act_kb_stage_commit,
    "kb_stage_discard": _act_kb_stage_discard,
    "kb_atoom_subject": _act_kb_atoom_subject,
    "kb_atoom_edit": _act_kb_atoom_edit,
    "kb_atoom_related": _act_kb_atoom_related,
    "kb_atoom_reference": _act_kb_atoom_reference,
    "kb_insight_link": _act_kb_insight_link,
    "kb_insight_unlink": _act_kb_insight_unlink,
    "kb_meta_start": _act_kb_meta_start,
    "kb_atoom_merge": _act_kb_atoom_merge,
    "kb_atoom_archive": _act_kb_atoom_archive,
    "kb_atoom_unarchive": _act_kb_atoom_unarchive,
    "kb_atoom_naar_spel": _act_kb_atoom_naar_spel,
    "kb_spel_start": _act_kb_spel_start,
    "kb_spel_add": _act_kb_spel_add,
    "kb_spel_remove": _act_kb_spel_remove,
    "kb_spel_flip": _act_kb_spel_flip,
    "kb_spel_finish": _act_kb_spel_finish,
    "kb_link": _act_kb_link,
    "kb_unlink": _act_kb_unlink,
    "kb_annotate": _act_kb_annotate,
    "kb_evidence": _act_kb_evidence,
    "kb_discuss": _act_kb_discuss,
    "kb_reformulate": _act_kb_reformulate,
    "kw_nominate": _act_kw_nominate,
    "kw_nom_accept": _act_kw_nom_accept,
    "kw_nom_reject": _act_kw_nom_reject,
    "ws_forbid": _act_ws_forbid,
    "ws_approve": _act_ws_approve,
    "proj_add": _act_proj_add,
    "artefact_add": _act_artefact_add,
    "artefact_edit": _act_artefact_edit,
    "artefact_archive": _act_artefact_archive,
    "proj_status": _act_proj_status,
    "proj_done": _act_proj_done,
    "proj_archive": _act_proj_archive,
    "proj_unarchive": _act_proj_unarchive,
    "proj_delete": _act_proj_delete,
    "proj_edit": _act_proj_edit,
    "proj_comment": _act_proj_comment,
    "proj_rename": _act_proj_rename,
    "proj_describe": _act_proj_describe,
    "proj_doc_edit": _act_proj_doc_edit,
    "proj_regen_doc": _act_proj_regen_doc,
    "proj_settrekker": _act_proj_settrekker,
    "proj_setowner": _act_proj_setowner,
    "proj_approve": _act_proj_approve,
    "proj_discard": _act_proj_discard,
    "proj_setlabel": _act_proj_setlabel,
    "proj_setimpact": _act_proj_setimpact,
    "proj_seteffort": _act_proj_seteffort,
    "proj_agendeer_verzwakt": _act_proj_agendeer_verzwakt,
    "proj_setprivate": _act_proj_setprivate,
    "proj_setdue": _act_proj_setdue,
    "attach_add": _act_attach_add,
    "attach_remove": _act_attach_remove,
    "react_add": _act_react_add,
    "feed_edit": _act_feed_edit,
    "feed_remove": _act_feed_remove,
    "wall_outcome": _act_wall_outcome,
    "notif_read": _act_notif_read,
    "notif_processed": _act_notif_processed,
    "notif_outcome": _act_notif_outcome,
    "notif_klaar": _act_notif_klaar,
    "notif_delete": _act_notif_delete,
    "notif_add": _act_notif_add,
    "notif_archive": _act_notif_archive,
    "metrics2_fav": _act_metrics2_fav,
    "metrics2_unfav": _act_metrics2_unfav,
    "metrics2_form": _act_metrics2_form,
    "metrics2_dim": _act_metrics2_dim,
    "metrics2_compare": _act_metrics2_compare,
    "metrics2_formula": _act_metrics2_formula,
    "source_activate": _act_source_activate,
    "source_deactivate": _act_source_deactivate,
    "link_pursue": _act_link_pursue,
    "link_ignore": _act_link_ignore,
    "acc_check": _act_acc_check,

    "ai_reply": _act_ai_reply,
    "proj_feed": _act_proj_feed,
    "checklist_add": _act_checklist_add,
    "checklist_remove": _act_checklist_remove,
    "check_add": _act_check_add,
    "check_accept": _act_check_accept,
    "check_toggle": _act_check_toggle,
    "check_remove": _act_check_remove,
    "role_assign": _act_role_assign,
    "role_unassign": _act_role_unassign,
    "role_focus": _act_role_focus,
    "radar_approve": _act_radar_approve,
    "radar_dismiss": _act_radar_dismiss,
    "aitask_add": _act_aitask_add,
    "aitask_remove": _act_aitask_remove,
    "persona_skill_add": _act_persona_skill_add,
    "rov2_add": _act_rov2_add,
    "rov2_add_to_group": _act_rov2_add_to_group,
    "rov2_remove": _act_rov2_remove,
    "rov2_remove_group": _act_rov2_remove_group,
    "rov2_setkind": _act_rov2_setkind,
    "rov2_consent": _act_rov2_consent,
    "rov2_end": _act_rov2_end,
    "wo_open": _act_wo_open,
    "wo_close": _act_wo_close,
    "wo_presence": _act_wo_presence,
    "wo_present_all": _act_wo_present_all,
    "wo_ag_add": _act_wo_ag_add,
    "wo_ag_remove": _act_wo_ag_remove,
    "wo_ag_note": _act_wo_ag_note,
    "wo_ag_reopen": _act_wo_ag_reopen,
    "wo_ag_resolve": _act_wo_ag_resolve,
    "wo_checkout": _act_wo_checkout,
    "noochie_send": _act_noochie_send,
    "noochie_reset": _act_noochie_reset,
    "noochie_ctx": _act_noochie_ctx,
    "cl_add": _act_cl_add,
    "cl_report": _act_cl_report,
    "cl_remove": _act_cl_remove,
    "m_add_kpi": _act_m_add_kpi,
    "m_add_from_def": _act_m_add_from_def,
    "def_add": _act_def_add,
    "catalog_publish": _act_catalog_publish,
    "def_amend": _act_def_amend,
    "m_add_link": _act_m_add_link,
    "m_sample": _act_m_sample,
    "m_remove": _act_m_remove,
    "m_pin": _act_m_pin,
    "m_unpin": _act_m_unpin,
    "tile_add": _act_tile_add,
    "indicator_activate": _act_indicator_activate,
    "tile_remove": _act_tile_remove,
    "rov2_set": _act_rov2_set,
    "rov2_acc_add": _act_rov2_set,
    "rov2_acc_remove": _act_rov2_set,
    "rov2_dom_add": _act_rov2_set,
    "rov2_dom_remove": _act_rov2_set,
    "backlog_add": _act_backlog_add,
    "backlog_update_staat": _act_backlog_update_staat,
    "backlog_update_prioriteit": _act_backlog_update_prioriteit,
    "person_edit": _act_person_edit,
    "person_remove": _act_person_remove,
    "lk_mute": _act_lk_mute,
    "claims_term_add": _act_claims_term_add,
    "claims_work_status": _act_claims_work_status,
}


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
    handler = ACTIONS.get(action)
    if handler is None:
        return nxt, ""                 # onbekende actie: no-op (was: fall-through naar eind-return)
    return handler(_Ctx(st, g, nxt, form, username, action, data_dir))


# Niets is publiek: een uitgelogde bezoeker gaat overal naar /login. /login en /logout worden in
# do_GET vóór de auth-check afgehandeld en blijven dus bereikbaar. Er is geen asset/health-route die
# publiek moet blijven (/file staat al achter de auth-check).
_PUBLIC_GET: set[str] = set()


def _home_node(recs) -> str:
    """De node waarop '/' opent: de operationele cirkel (Nooch), niet de anchor (Mother Earth) —
    daar gebeurt het meeste werk. Fallback: eerste sub-cirkel van de root, anders de root zelf,
    anders '' (geen organisatie geladen)."""
    roots = org.roots(recs)
    if not roots:
        return ""
    subs = [k for k in org.children_of(recs, roots[0].id) if org.is_circle(k)]
    return next((s.id for s in subs if s.id == "mother_earth__nooch"),
                subs[0].id if subs else roots[0].id)


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

        def _send(self, body: str, code: int = 200, chrome: bool = True):
            # Globale chrome = de inbox-drawer (launcher + uitschuif-paneel links + modal). Alleen voor een
            # sessie en alleen op volledige HTML-pagina's (met </body>). chrome=False voor de inbox-routes
            # zelf (die zijn de drawer-inhoud / het fragment; injecteren zou de drawer in zichzelf nesten).
            # De Noochie-rail + call bar zijn eruit; 'chatten met de raad' komt later als eigen feature.
            if chrome and self._session_username() is not None and "</body>" in body:
                try:
                    _st = _Stores(data_dir)
                    _ro = _person_role_options(_st, _person_targets(_st, self._session_username()))
                except Exception:
                    _ro = ""
                body = body.replace("</body>", render_inbox_chrome(csrf_token, _ro) + "</body>", 1)
            b = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _send_bytes(self, data: bytes, content_type: str, filename: str = "",
                        cache_secs: int = 0):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            if cache_secs:
                self.send_header("Cache-Control", f"public, max-age={cache_secs}")
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
            # ── Wachtwoordwijziging (self-service + verplichte eerste-login/na-reset-poort) ──
            if path == "/wachtwoord":
                # AUTHZ: circle-member of iedereen-ingelogd — eigen wachtwoord wijzigen
                self._send(_auth.password_change_page(forced=st.people.must_change(username or "")))
                return
            if username and st.people.must_change(username):     # poort: alles → /wachtwoord tot gewijzigd
                self._redirect_to("/wachtwoord")
                return
            if path == "/snake":
                # AUTHZ: ingelogde-member — verborgen easter-egg 'Snaker'; puur fun, los van alles.
                # De login-redirect hierboven dekt de niet-ingelogde gebruiker al af.
                # chrome=False: geen dorp-brede call bar/Noochie-rail injecteren — de pagina draait als
                # fullscreen-overlay-iframe op de cockpit; de bar leeft in de PARENT en wordt daar via
                # body.overlay-open verborgen. Injecteren zou hier een tweede (ongestylede) bar geven.
                self._send(snake.render_snake_page(st, username, effective_csrf), chrome=False)
                return
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
            if path == "/epic/frame":
                # NASA EPIC-frame (server-side naar ~512px JPEG geresized) doorserveren; key blijft server-side.
                data = epic.frame_bytes((qs.get("image") or [""])[0], (qs.get("date") or [""])[0])
                if data:
                    self._send_bytes(data, "image/jpeg")
                else:
                    self._send("", 404)
                return
            if path in ("/", "/index.html"):
                default_id = _home_node(st.records.all())
                if default_id:
                    self.send_response(302)
                    self.send_header("Location", f"/node?id={default_id}")
                    self.end_headers()
                    return
                self._send(_page("Leeg", "<p>Nog geen organisatie geladen.</p>"))
                return
            if path == "/node":
                nid = (qs.get("id") or [""])[0]
                ntab = (qs.get("tab") or ["overview"])[0]
                self._send(render_node(st, nid, ntab, csrf_token=effective_csrf,
                                       msg=(qs.get("msg") or [""])[0],
                                       group=(qs.get("group") or [""])[0],
                                       clf=(qs.get("clf") or ["due"])[0],
                                       mw=(qs.get("mw") or ["7d"])[0],
                                       van=(qs.get("van") or [""])[0],
                                       tot=(qs.get("tot") or [""])[0],
                                       compare=(qs.get("compare") or [""])[0] == "1",
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
            if path == "/signals":
                # Dorp-brede lijst van goedgekeurde radar-signalen (read-only aggregatie). Publiek zoals
                # het overzicht; achter de sessie-auth zoals alles.
                self._send(render_signals(st, csrf_token=effective_csrf, feed=(qs.get("feed") or [""])[0]))
                return
            if path == "/inbox":
                # De inbox van de ingelogde mens: mentions aan hem (als persoon of via zijn rollen).
                tgts = _person_targets(st, username)
                # chrome=False: de drawer wordt door _send geïnjecteerd op ANDERE pagina's; deze route IS
                # de drawer-inhoud (fragment) of de standalone-fallback, dus geen drawer-in-drawer.
                if (qs.get("frag") or [""])[0]:
                    self._send(render_inbox_frag(st, tgts, csrf_token=effective_csrf), chrome=False)
                    return
                nm = ""
                if username and username != "guest":
                    _p = st.people.by_email(username)
                    nm = _p.name if _p else ""
                done = (qs.get("done") or [""])[0]
                self._send(render_inbox(st, tgts, csrf_token=effective_csrf, naam=nm, done=done), chrome=False)
                return
            if path == "/bronnen":
                # Aansluit-scherm voor externe databronnen (status + aan/uit).
                self._send(render_bronnen(st, os.path.dirname(data_dir), csrf_token=effective_csrf))
                return
            if path == "/inzichten":
                # Kennislaag: de inzicht-kaarten die de Librarian ving (read-only).
                self._send(render_kennislaag(data_dir))
                return
            if path == "/kennisbank":
                # Kennisbank (laag 2): geversioneerde inzichten met een berekend veld van
                # zekerheid boven de atomen (notes.json). ?id= opent het detail als drawer;
                # ?hunch= zoekt kaarten (top-down), ?speel= toont een cluster-set (bottom-up),
                # ?nieuw= toont de atomen van de laatste intake.
                try:
                    _pag = max(1, int((qs.get("pag") or ["1"])[0]))
                except ValueError:
                    _pag = 1
                try:
                    _cl = max(0, int((qs.get("cluster") or ["0"])[0]))
                except ValueError:
                    _cl = 0
                self._send(render_kennisbank(st, kid=(qs.get("id") or [""])[0],
                                             q=(qs.get("q") or [""])[0],
                                             csrf_token=effective_csrf,
                                             msg=(qs.get("msg") or [""])[0],
                                             hunch=(qs.get("hunch") or [""])[0],
                                             speel=(qs.get("speel") or [""])[0],
                                             nieuw=(qs.get("nieuw") or [""])[0],
                                             hub=(qs.get("hub") or [""])[0], pag=_pag,
                                             open_=(qs.get("open") or [""])[0], cluster=_cl,
                                             flip=(qs.get("flip") or [""])[0] in ("1", "true", "on")))
                return
            if path == "/kennisbank/search":
                # Live smart-search fragment (PR-2): alleen de resultatenlijst, over de verse
                # bibliotheek. Zoekt op inhoud én bron; markeert brug-suggesties bij een
                # actief inzicht. chrome=False: het is een fragment dat de JS inplakt.
                self._send(render_kennisbank_search(st, (qs.get("q") or [""])[0],
                                                    (qs.get("hub") or [""])[0],
                                                    (qs.get("active") or [""])[0],
                                                    csrf_token=effective_csrf), chrome=False)
                return
            if path == "/kennisbank/staging":
                # Zone 2: de "even nakijken"-ronde vóór de bibliotheek (bewerken/samenvoegen/weggooien).
                self._send(render_kennisbank_staging(st, (qs.get("batch") or [""])[0],
                                                     csrf_token=effective_csrf,
                                                     msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/kennisbank/spel":
                # Het inzicht-spel, copy-paste-flow: hand cureren → prompt kopiëren →
                # blok terugplakken → munten. ?zoek= zoekt kaarten voor de hand.
                self._send(render_kennisbank_spel(st, (qs.get("sid") or [""])[0],
                                                  zoek=(qs.get("zoek") or [""])[0],
                                                  csrf_token=effective_csrf,
                                                  msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/linkbuilding":
                # Linkbuilding-doelwitten geborgd in cockpit 2 (pitchen/negeren).
                self._send(render_linkbuilding(data_dir, csrf_token=effective_csrf))
                return
            if path == "/accountabilities":
                # Dorpsbrede accountability-check (dubbelingen + formulering).
                self._send(render_accountabilities(st, data_dir, csrf_token=effective_csrf))
                return
            if path == "/woordenschat":
                # Library-kansenscherm: verrijkte keywords gerangschikt op kansrijkheid; met
                # csrf-token read-write (beheer: verbied/heractiveer + nominatie-oordeel).
                # can_decide: alleen de Librarian-vervuller beslist over nominaties (zelfde
                # gate als /keywords?lens=library).
                can_decide = _role_gate("librarian", username, st) is None
                self._send(render_woordenschat(data_dir, csrf_token=effective_csrf,
                                               msg=(qs.get("msg") or [""])[0],
                                               can_decide=can_decide))
                return
            if path == "/keywords":
                # IA-fase 3: één keyword-datalaag, rol-lenzen (?lens=marketing|scientist|trends|
                # library|kroniek). IA-fase 4: nomineren kan iedereen; alleen Lara (librarian-
                # rolvervuller) beslist — can_decide gate bepaalt of accept/reject-controls renderen.
                can_decide = _role_gate("librarian", username, st) is None
                self._send(render_keyword_lens(st, (qs.get("lens") or ["trends"])[0],
                                               csrf_token=effective_csrf, can_decide=can_decide))
                return
            if path == "/long-term-trends":
                # IA-fase 2→3: de Scientist-lens is nu een lens op de gedeelde laag. Oude route
                # blijft werken via een redirect (geen dode deep-links).
                self._redirect_to("/keywords?lens=scientist")
                return
            if path == "/belofte":
                # Belofte-graaf: eerste-principes-ontleding, sterkte op het zwakste onderdeel (read-only, stap 1).
                bid = (qs.get("id") or [""])[0]
                self._send(render_belofte(data_dir, bid))
                return
            if path == "/metrics2":
                # Nieuw catalogus-plus-dashboard-scherm, náást het bestaande metrics-scherm.
                node = (qs.get("node") or [""])[0]
                rec = st.records.get(node) if node else None
                win = (qs.get("mw") or ["7d"])[0]
                compare = (qs.get("compare") or [""])[0] in ("1", "true", "on")
                van = (qs.get("van") or [""])[0]
                tot = (qs.get("tot") or [""])[0]
                self._send(render_metrics2(st, rec, csrf_token=effective_csrf, win=win,
                                           compare=compare, van=van, tot=tot))
                return
            if path == "/inbox/verwerk":
                # De twee-panelen-verwerkpagina voor één spanning: links de spanning, rechts de wizard.
                # chrome=False: draait als modal-iframe binnen de drawer; geen tweede drawer injecteren.
                nid = (qs.get("nid") or [""])[0]
                n = st.notif._find(nid)
                ro = _wall_outcome_opts(st)[0] if n is not None else ""
                po = _scoped_project_opts(st, n) if n is not None else ""
                self._send(render_verwerk(st, n, csrf_token=effective_csrf, role_opts=ro, pj_opts=po),
                           chrome=False)
                return
            if path == "/catalog":
                # AUTHZ: anchor-lead — het overzicht is publiek; de geïntegreerde koppel-sectie (ruw veld
                # → indicator) rendert alleen voor de curator. guest (auth-uit) telt als curator.
                actor = st.people.by_email(username) if username and username != "guest" else None
                curator = actor is None or is_circle_lead(actor.id, "mother_earth", st.assign)
                self._send(render_catalog(st, csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0],
                                          koppel=(qs.get("koppel") or [""])[0], curator=curator))
                return
            if path == "/catalogus_koppelen":
                # Samengevoegd in /catalog (scope 4): geen los scherm meer → 303 naar het koppel-onderdeel.
                src = (qs.get("source") or [""])[0]
                self._redirect_to(f"/catalog?koppel={urllib.parse.quote(src or '1')}")
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
            if path == "/callbar":
                # AUTHZ: iedereen-ingelogd — de route levert alleen de bar-UI (iframe-body); de
                # daadwerkelijke toegang bewaakt /livekit-token zelf. Achter de sessie-auth zoals alles.
                # chrome=False: deze pagina IS de bar en mag de iframe niet in zichzelf injecteren.
                self._send(render_callbar(csrf_token=effective_csrf), chrome=False)
                return
            if path == "/livekit-token":
                # Enige request-input: `tab` (per-tabblad-suffix). Room + identity-base bepaalt de
                # server zelf (zie issue_livekit_token). AUTHZ: iedereen-ingelogd, in die functie.
                status, payload = issue_livekit_token(st, username, (qs.get("tab") or [""])[0])
                self._send_json(payload, status)
                return
            if path == "/livekit-presence":
                # Goedkope presence voor de callbar: telt deelnemers in de dorp-room server-side, ZONDER
                # zelf te verbinden. Vervangt de oude observer-connect die WebRTC-minuten opslurpte.
                count, names = livekit_presence()
                self._send_json({"count": count, "names": names}, 200)
                return
            if path == "/claims/db.json":
                # AUTHZ: iedereen-ingelogd — naslagwerk, lezen is vrij (domein-regel: cureren is
                # exclusief compliance, en dat loopt via de dispatch-takken hieronder).
                try:
                    self._send_bytes(json.dumps(_claims_db.load(), ensure_ascii=False).encode("utf-8"),
                                     "application/json; charset=utf-8")
                except _claims_db.ClaimsDbError as e:
                    self._send_json({"error": str(e)}, 500)   # fail-closed: liever een fout dan lege lijst
                return
            if path == "/claims":
                # AUTHZ: iedereen-ingelogd — checken is voor alle rollen; muteren kan hier niet
                # (de schrijfknoppen hangen aan de compliance-gate in _act_claims_*).
                # Statisch bestand, bewust GEEN governeerde view: het prototype heeft eigen
                # vormgeving en valt daarom buiten het design-systeem en de view-ratchets.
                try:
                    with open(os.path.join(os.path.dirname(__file__), "static",
                                           "claims_checker.html"), encoding="utf-8") as _f:
                        _html = _f.read()
                except OSError:
                    self._send("Claims-checker niet gevonden", 404); return
                _mag_cureren = _claims_gate_open(_Stores(data_dir), username)
                _html = (_html.replace("__CSRF__", effective_csrf)
                              .replace("__MAG_CUREREN__", "true" if _mag_cureren else "false"))
                # _send_bytes i.p.v. _send: geen inbox-chrome injecteren in een standalone pagina.
                self._send_bytes(_html.encode("utf-8"), "text/html; charset=utf-8")
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
                # Alle whitelisted statics zijn versieloos-of-gehasht → dag-cache is veilig
                # (nooch.css draagt een inhoud-hash in de URL, zie _DS_LINK).
                self._send_bytes(_data, ct, cache_secs=86400); return
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

            if path == "/snake/score":
                # AUTHZ: ingelogde-member — iedereen mag spelen; de score wordt ONDER de sessie-gebruiker
                # geschreven (nooit een meegestuurde naam), en alleen als hij hoger is dan het record.
                username = self._session_username()
                if sessions is not None and username is None:
                    self._send("Niet ingelogd", 403); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                if not secrets.compare_digest((form.get("csrf") or [""])[0], csrf_token):
                    self._send("CSRF-token ongeldig", 403); return
                self._send_json(snake.handle_score(_Stores(data_dir), username, (form.get("score") or ["0"])[0]))
                return

            if path == "/wachtwoord":
                # AUTHZ: circle-member of iedereen-ingelogd — eigen wachtwoord wijzigen (self + geforceerd)
                username = self._session_username()
                if sessions is not None and username is None:
                    self._redirect_to("/login"); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                ok, page = _password_change(data_dir, form, username)
                if ok:
                    if sessions is not None:      # haak: verbreek oude sessies, behoud de eigen (no-op nu)
                        sessions.invalidate_user(username, keep_token=_auth.get_session_token(self.headers))
                    self._redirect_to((form.get("next") or ["/"])[0] or "/")
                else:
                    self._send(page, 200)
                return

            if path != "/action":
                self._send("<p>404</p>", 404); return

            # ── Sessie-check voor alle /action POSTs ────────────────────────
            username = self._session_username()
            if sessions is not None and username is None:
                self._send("Niet ingelogd", 403); return
            # Bestand-upload (multipart): apart afhandelen; bestand wegschrijven + registreren.
            if ctype.startswith("multipart/form-data") and "boundary=" in ctype:
                # nginx capt de body op 25M (413 vóór de app); de app-limiet ligt bewust lager (20M) zodat
                # de app zelf de nette fout geeft voor bestanden tussen de app-limiet en de nginx-cap.
                raw = self.rfile.read(length) if length else b""
                boundary = ctype.split("boundary=", 1)[1].strip().strip('"')
                fields, files = _parse_multipart(raw, boundary)
                if not secrets.compare_digest(fields.get("csrf", ""), csrf_token):
                    self._send("CSRF-token ongeldig", 403); return
                if fields.get("action") == "attach_file":
                    err = _upload_error(files, _upload_max_bytes())
                    if err:                                  # te groot / geen bestand → expliciete fout, geen no-op
                        self._send(err[0], err[1]); return
                    fname, blob = files["file"]
                    pid = fields.get("pid", "")
                    safe = os.path.basename(fname).replace("\\", "_")[:120]
                    rel = os.path.join("attachments", pid, uuid.uuid4().hex[:8] + "_" + safe)
                    full = os.path.join(data_dir, rel)
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(full, "wb") as fh:
                        fh.write(blob)
                    _Stores(data_dir).projects.attach_file(pid, safe, rel)
                    self._redirect(fields.get("next", "/"), "📎 bijlage geupload"); return
                if fields.get("action") == "kb_atoom_ref_pdf":
                    # AUTHZ: iedereen-ingelogd — kennisbank. Een PDF als bronlink bij een atoom (A3):
                    # via de bestaande adapter halen we een net documentlabel; dat landt in reference.
                    err = _upload_error(files, _upload_max_bytes())
                    if err:
                        self._send(err[0], err[1]); return
                    from nooch_village.kennisbank_sources import van_pdf
                    fname, blob = files["file"]
                    nxt = fields.get("next", "/kennisbank")
                    chunks = van_pdf(blob, os.path.basename(fname))
                    label = chunks[0][1] if chunks else os.path.basename(fname)[:120]
                    ok = _Stores(data_dir).notes.set_reference(fields.get("atom_id", ""), label)
                    self._redirect(nxt, "🔗 PDF als bronlink gekoppeld" if ok else "✗ notitie niet gevonden")
                    return
                if fields.get("action") == "kb_intake_pdf":
                    # AUTHZ: iedereen-ingelogd — kennisbank-intake. PDF = source-adapter:
                    # tekst-extractie + chunken, elke chunk door de bestaande atomiser
                    # (ledger per chunk → her-uploaden idempotent; een gefaalde chunk
                    # komt bij een volgende upload vanzelf terug).
                    err = _upload_error(files, _upload_max_bytes())
                    if err:
                        self._send(err[0], err[1]); return
                    from nooch_village.kennisbank_sources import van_pdf
                    fname, blob = files["file"]
                    chunks = van_pdf(blob, os.path.basename(fname))
                    if chunks is None:
                        self._redirect(fields.get("next", "/kennisbank"),
                                       "✗ geen tekstlaag gevonden in deze PDF (scan? "
                                       "OCR valt buiten v1)"); return
                    nieuw_alles: list[str] = []
                    dubbel_alles = mislukt = 0
                    for chunk_raw, label in chunks:
                        uitkomst = kb_intake(chunk_raw, label, data_dir)
                        if uitkomst is None:
                            mislukt += 1
                            continue
                        _nieuw, _dubbel = uitkomst
                        nieuw_alles.extend(_nieuw)
                        dubbel_alles += _dubbel
                    delen = [f"✂️ {len(nieuw_alles)} notities uit {len(chunks)} delen"]
                    if dubbel_alles:
                        delen.append(f"{dubbel_alles} al bekend")
                    if mislukt:
                        delen.append(f"{mislukt} deel/delen mislukt — upload nogmaals "
                                     f"voor de rest (niets raakt dubbel)")
                    nxt = "/kennisbank" + (f"?nieuw={','.join(nieuw_alles)}" if nieuw_alles else "")
                    self._redirect(nxt, " · ".join(delen)); return
                if fields.get("action") == "kb_bron_add":
                    # AUTHZ: iedereen-ingelogd — kennisbank zone 2. Eén ingang: tekst OF bestand →
                    # auto-detect → adapter → atomiser → STAGING-batch (niet direct de bibliotheek;
                    # de mens kijkt na op /kennisbank/staging).
                    from nooch_village.kennisbank_sources import detect_and_extract
                    from nooch_village.kennisbank_intake import atomiseer
                    username = self._session_username()
                    fname, blob = files.get("file", ("", b""))
                    res = detect_and_extract(text=fields.get("bron_text", ""),
                                             filename=fname if blob else "", data=blob)
                    if res["chunks"] is None:
                        self._redirect("/kennisbank?open=bron",
                                       f"✗ {res.get('error') or 'niets herkend'}"); return
                    stores = _Stores(data_dir)
                    atoms: list[dict] = []
                    label = res["chunks"][0][1]
                    mislukt = 0
                    # Atomiciteit-bovengrens per document (fix-brief bug 2): een lang stuk of een
                    # referentielijst mag niet in tientallen mini-kaartjes ontploffen. Zodra de cap
                    # gehaald is stoppen we met verdere chunks — de mens ziet in de staging wat er is.
                    _DOC_CAP = 40
                    for craw, clabel in res["chunks"]:
                        got = atomiseer(craw, clabel, tabular=res["tabular"])
                        if got is None:
                            mislukt += 1
                            continue
                        atoms += got
                        label = clabel
                        if len(atoms) >= _DOC_CAP:
                            atoms = atoms[:_DOC_CAP]
                            break
                    if not atoms:
                        self._redirect("/kennisbank?open=bron",
                                       "✗ de atomiser gaf niets bruikbaars"); return
                    bid = stores.staging.create(res["kind"], label, atoms,
                                                tabular=res["tabular"],
                                                by=(username if username != "guest" else ""))
                    extra = f" · {mislukt} deel/delen mislukt" if mislukt else ""
                    self._redirect(f"/kennisbank/staging?batch={bid}",
                                   f"✂️ {len(atoms)} voorstellen uit {res['kind']} — even nakijken{extra}")
                    return
                self._redirect(fields.get("next", "/"), ""); return
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
            if action == "lk_mute":
                # AJAX-actie vanuit de call bar: geen full-page redirect (de bar blijft staan),
                # alleen een korte 200 met de bevestiging. Business-logica leeft in de dispatch-tak.
                _, msg = dispatch(data_dir, action, form, username=username)
                self._send(msg or "ok", 200)
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
    _Stores(dd).people.backfill_must_change()   # markeer uitstaande temps 'moet wijzigen' (idempotent)
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


def _upload_max_bytes() -> int:
    """Max upload-grootte in bytes (config-key upload_max_bytes, default 20M). BEWUST onder de nginx-cap
    (25M) zodat de app zelf de nette fout kan geven i.p.v. nginx (413). Accepteert '20M'/'20MB'/bytes."""
    raw = (os.getenv("upload_max_bytes", "") or "").strip().upper()
    if not raw:
        return 20 * 1024 * 1024
    try:
        if raw.endswith("MB"):
            return int(raw[:-2]) * 1024 * 1024
        if raw.endswith("M"):
            return int(raw[:-1]) * 1024 * 1024
        return int(raw)
    except ValueError:
        return 20 * 1024 * 1024


def _upload_error(files: dict, limit: int):
    """Valideer een multipart-upload vóór wegschrijven. Geeft (melding, http-status) bij een probleem,
    anders None. Vervangt de oude stille no-op: een ontbrekend/leeg bestand of een te groot bestand
    levert nu een expliciete fout i.p.v. een lege redirect."""
    fname, blob = (files.get("file") or ("", b""))
    if not (fname and blob):
        return ("Geen bestand geselecteerd", 400)
    if len(blob) > limit:
        return (f"Bestand te groot (max {limit // (1024 * 1024)} MB)", 413)
    return None


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
            out = llm.reason(prompt, ladder=_match_ladder(), call_site="cockpit_match_pair")
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
            has_key = bool(llm.reason("antwoord met 'ok'", ladder=_match_ladder(), call_site="cockpit_match_keycheck"))
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
