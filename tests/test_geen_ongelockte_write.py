"""Harde regel: naar een JSON-store schrijf je ALLEEN via de gedeelde, gelockte route
(`util.JsonStore._save` → `atomic_write_json`). Een directe `atomic_write_json`-aanroep buiten
`util.py` omzeilt het bestandsslot en kan een gelijktijdige schrijver overschrijven (lost update —
de bug die snapshots/bijlagen liet verdwijnen, #161/#168).

Ratchet (stijl `test_ui_no_inline_style`): elke huidige overtreder staat met zijn EXACTE aantal +
een VERPLICHTE reden in `_WHITELIST`. Meer → nieuwe ongelockte schuld (faal). Minder → je hebt een
store naar `JsonStore` gemigreerd, verlaag/verwijder de entry (faal met uitleg). Doel: monotone
daling naar nul. Wie een tweede schrijver aan een store hangt, laat de telling stijgen → moet de
whitelist aanraken en de reden heroverwegen.
"""
from __future__ import annotations

import glob
import os
import re

_PKG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village")
_PAT = re.compile(r"atomic_write_json\(")

# `util.py` is de ENIGE toegestane home: de definitie van atomic_write_json + JsonStore._save.
_ALLOWED = {"util.py"}

# bestand (relatief t.o.v. nooch_village) → (exact aantal directe atomic_write_json-calls, REDEN).
# Categorieën uit het Fase-1-rapport. Ratchet naar 0 bij migratie naar JsonStore.
_WHITELIST = {
    # ── (a) BEIDE processen schrijven — hoogste prioriteit (fase 4, batch 1) ──
    "governance.py":     (1, "(a) cross-proces: daemon-Secretary + cockpit-roloverleg (de waarheid)"),
    "human_inbox.py":    (1, "(a) cross-proces: daemon-Village + inbox-CLI (approval-oppervlak)"),
    "ai_match.py":       (1, "(a) cross-proces: cockpit2 serve + het match-subcommando"),
    # ── al gelockt via synchronized; convergeren naar JsonStore in fase 4, batch 0 ──
    "projects.py":       (1, "gelockt via synchronized; converge naar JsonStore (fase 4 batch 0)"),
    "attachments.py":    (1, "gelockt via file_lock; converge naar JsonStore (fase 4 batch 0)"),
    "werkoverleg.py":    (1, "gelockt via synchronized; converge naar JsonStore (fase 4 batch 0)"),
    # ── (b) alleen cockpit, maar ThreadingHTTPServer = concurrente requests (fase 4, batch 2) ──
    "ai_tasks.py":       (1, "(b) cockpit-concurrent (_Stores)"),
    "assignments.py":    (1, "(b) cockpit-concurrent (_Stores)"),
    "backlog.py":        (1, "(b) cockpit-concurrent (_Stores)"),
    "checklists.py":     (1, "(b) cockpit-concurrent (_Stores)"),
    "definitions.py":    (1, "(b) cockpit-concurrent (_Stores)"),
    "metrics.py":        (1, "(b) cockpit-concurrent (_Stores)"),
    "noochie.py":        (1, "(b) cockpit-concurrent (_Stores)"),
    "notifications.py":  (1, "(b) cockpit-concurrent (_Stores)"),
    "people.py":         (1, "(b) cockpit-concurrent (_Stores)"),
    "personas.py":       (1, "(b) cockpit-concurrent (_Stores) + occasionele CLI"),
    "roloverleg.py":     (1, "(b) cockpit-concurrent (_Stores, roloverleg-agenda)"),
    "strategy_store.py": (1, "(b) cockpit-concurrent (_Stores)"),
    "snake.py":          (1, "(b) cockpit-only game-scores (triviaal)"),
    # ── (c) alleen daemon, single-writer (puls/collector/skills) — laag risico ──
    "source_status.py":  (1, "single-writer: alleen de collector-daemon (cockpit leest)"),
    "library.py":        (1, "single-writer: alleen de Librarian-daemon"),
    "lexicon.py":        (1, "single-writer: seed + Librarian-daemon"),
    "monitoring.py":     (1, "single-writer: alleen de daemon"),
    "competitor_brands.py":     (1, "single-writer: alleen de daemon"),
    "competitor_news_store.py": (1, "single-writer: alleen de daemon"),
    "deadsource.py":     (1, "single-writer: alleen de daemon"),
    "link_targets.py":   (1, "single-writer: alleen de daemon"),
    "seed_surge_store.py": (1, "single-writer: alleen de daemon"),
    "keyword_scheduler.py": (1, "single-writer: alleen een daemon-skill"),
    "skills_impl/claims_site_scan.py": (1, "daemon-lokaal: weekmarker van de compliance-scan, één schrijver"),
    "deliverable_store.py": (1, "write-once sidecar per deliverable (data/deliverables/<id>.json); "
                               "lock-vrij want elk id is uniek — NIET de index, die loopt via JsonStore._save"),
    # ── daemon-lokaal: per-thread/single-writer state, geen gedeelde store ──
    "inhabitant.py":     (5, "daemon-lokaal: per-rol-thread reflect-/goal-state (eigen bestand per rol)"),
    "roles.py":          (4, "daemon-lokaal: per-rol single-writer state (last_day/seed; +trend_reindex_last_day)"),
    "village.py":        (1, "daemon single-writer: role_status.json (cockpit leest read-only)"),
    # ── dormant/legacy: alleen legacy cockpit1 of demo/CLI — geen live concurrente schrijver ──
    "constraints.py":    (1, "dormant: legacy cockpit1"),
    "feedback.py":       (1, "dormant: legacy cockpit1"),
    "governance_examples.py": (1, "dormant: legacy cockpit1 + handmatige CLI"),
    "link_suggest.py":   (1, "dormant: legacy cockpit1"),
    "news_distill.py":   (1, "dormant: legacy cockpit1"),
    "pinboard.py":       (1, "dormant: demo-only (discovery_board)"),
    "cli.py":            (1, "eenmalig CLI-commando (shopify_metrics), geen concurrency-store"),
}


def _py_files():
    return sorted(glob.glob(os.path.join(_PKG, "**", "*.py"), recursive=True))


def _count(path):
    return len(_PAT.findall(open(path, encoding="utf-8").read()))


def test_geen_directe_atomic_write_json_buiten_jsonstore():
    """Ratchet: elke overtreder heeft EXACT zijn gewhiteliste aantal directe atomic_write_json-calls."""
    seen = set()
    for full in _py_files():
        rel = os.path.relpath(full, _PKG).replace(os.sep, "/")
        if rel in _ALLOWED:
            continue
        count = _count(full)
        if count == 0:
            continue
        seen.add(rel)
        ceil, reason = _WHITELIST.get(rel, (0, ""))
        assert count <= ceil, (
            f"{rel}: {count} directe atomic_write_json-call(s), plafond {ceil}. Schrijf via "
            f"util.JsonStore._save (erf van JsonStore + declareer _WRITE_METHODS). Bewuste "
            f"uitzondering? Verhoog het plafond in _WHITELIST MÉT reden.")
        assert count >= ceil, (
            f"{rel}: {count} directe call(s), plafond {ceil}. Je hebt (deels) gemigreerd — verlaag "
            f"het plafond naar {count} of verwijder de entry bij 0 zodat de ratchet vastzet.")


def test_whitelist_is_actueel_en_heeft_redenen():
    """Elke whitelist-entry moet een niet-lege reden hebben (aanscherping a) én nog echt bestaan
    (geen stale entry die de ratchet slap houdt)."""
    for rel, (ceil, reason) in _WHITELIST.items():
        assert reason.strip(), f"{rel}: whitelist-entry mist de verplichte reden-comment"
        assert ceil >= 1, f"{rel}: plafond {ceil} — verwijder de entry i.p.v. 0 whitelisten"
        full = os.path.join(_PKG, rel)
        assert os.path.exists(full) and _count(full) == ceil, (
            f"{rel}: whitelist zegt {ceil} maar het bestand telt {_count(full) if os.path.exists(full) else 'MIST'} "
            f"— stale entry, werk _WHITELIST bij.")
