"""Projectbord → Radar: een afgerond project wordt automatisch een signaal op /signals.

Done is al een mens-poort (review-goedkeuring of bewuste bord-drag), dus het signaal slaat de
wachtkamer over en komt direct als 'goedgekeurd' op /signals te staan. Vandaar geen LLM en geen
extra curatiestap: de founder promoveert/koppelt het daar aan de kennisbank via de bestaande
radar_promote-flow.

Idempotent: link = "/project?id=<pid>" en de `seen`-lijst van de RadarStore ontdubbelt op die
link. Een heropend en opnieuw afgerond project levert dus geen tweede signaal op — de link is
het identiteitsanker, niet de (mogelijk gewijzigde) outcome-tekst. Alles loopt via de
store-methodes (append-only add + set_status + mark_seen); de aanroepers (cockpit-done,
board-watch) wikkelen de aanroep fail-soft in zodat een falend signaal nooit een done blokkeert.

Verdieping (rapport-lus): naast het signaal gaat het EINDDOCUMENT van een done-project door het
bestaande intake-pad (kennisbank_intake.atomiseer, zelfde prompt/contract) naar de kennisbank-
STAGING — de "even nakijken"-ronde, mens-gated — nooit direct de bibliotheek in. Zie
`report_to_staging`. Dit pad draait ALLEEN op de daemon (village._poll_board), waar de
LLM-ladder beschikbaar is; de cockpit-done doet géén synchrone LLM-call."""
from __future__ import annotations

import logging
import os

from datetime import datetime, timezone

log = logging.getLogger("village.signals")

FEED = "Projecten"
KIND = "project"
SOURCE = "projectbord"


def project_link(pid: str) -> str:
    """De canonieke signaal-link voor een project — tevens de dedupe-sleutel in `seen`."""
    return f"/project?id={pid}"


def _iso(ts) -> str:
    """Epoch (updated_at = afrondmoment) → ISO-timestamp; onparsebaar → nu (UTC)."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError, OverflowError):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def signal_from_project(radar, project) -> str | None:
    """Maak (hoogstens één keer) een goedgekeurd radar-signaal van een afgerond project.

    Geeft de signal-id terug, of None als er al een signaal voor dit project bestaat
    (link-dedupe via `seen`) of het project geen id heeft. Deterministisch, geen LLM:
    content = outcome (anders "Afgerond: <scope>"), rationale = hypothese, role = owner
    (fallback "village")."""
    p = project or {}
    pid = p.get("id") or ""
    if not pid:
        return None
    link = project_link(pid)
    if radar.seen(link):
        return None                      # heropend + opnieuw afgerond → geen tweede signaal
    # De titel is de CONCLUSIE van het inhoudelijke werk (dod_outcome — het antwoord op de
    # projectvraag, projectpoort), niet de procedurele "checklist voltooid"-mededeling (outcome).
    # Founder 20 jul: op /signals wil je zien wát er gevonden is, niet dát de checklist af is.
    dod = str(p.get("dod_outcome") or "").strip()
    outcome = str(p.get("outcome") or "").strip()
    content = dod or outcome or f"Afgerond: {str(p.get('scope') or pid).strip()}"
    rid = radar.add(role=(p.get("owner") or "village"), feed=FEED, kind=KIND,
                    content=content, rationale=str(p.get("hypothesis") or "").strip(),
                    source=SOURCE, link=link, published_at=_iso(p.get("updated_at")))
    if rid is None:
        return None
    radar.set_status(rid, "goedgekeurd")   # done is al de mens-poort; wachtkamer overslaan
    radar.mark_seen(link)
    return rid


def backfill_done_projects(ledger, radar, dry_run: bool = False) -> dict:
    """Backfill: loop bestaande done-projecten langs en maak ontbrekende signalen (zelfde
    helper als de done-hooks). Geeft {"done", "created", "skipped"} terug. dry_run telt
    alleen wat er zóu gebeuren; echt draaien is idempotent herhaalbaar (link-dedupe,
    append-only add — geen backup nodig)."""
    done = ledger.by_status("done")
    created = skipped = 0
    for p in done:
        pid = p.get("id") or ""
        if not pid or radar.seen(project_link(pid)):
            skipped += 1
            continue
        if dry_run:
            created += 1
            continue
        if signal_from_project(radar, p) is not None:
            created += 1
        else:
            skipped += 1
    return {"done": len(done), "created": created, "skipped": skipped}


# ── Rapport-lus: einddocument → intake-atomiser → kennisbank-STAGING (mens-gated) ────────────

REPORT_MIN_CHARS = 200      # korter is een stub, geen rapport → niets doen (bewuste drempel)
STAGING_KIND = "projectrapport"


def report_source_hint(project) -> str:
    """De bron-hint én de bron op elk voorstel: "project: <scope>". Zo is de herkomst in de
    staging-review ("even nakijken") en later in de bibliotheek in één oogopslag te zien,
    en is hij samen met de rapporttekst de idempotentie-sleutel van de IntakeLedger."""
    p = project or {}
    return f"project: {str(p.get('scope') or p.get('id') or '').strip()}"


def report_to_staging(context_of_data_dir, project, reason_fn=None, dry_run: bool = False) -> dict:
    """Einddocument van een done-project → bestaand intake-pad → kennisbank-STAGING.

    De atomen landen in de StagingStore (de "even nakijken"-ronde, mens-gated), NOOIT direct
    in de bibliotheek. Elk voorstel krijgt source = "project: <scope>", reference =
    "/project?id=<pid>" (interne link) en source_date = de afronddatum — de LLM-bron wordt
    bewust overschreven: het rapport zelf is hier de bron.

    Idempotent per project via de bestaande IntakeLedger (hash van rapport + bron-hint):
    een heropend en opnieuw afgerond project met ongewijzigd rapport levert niets nieuws;
    een gewijzigd rapport levert een nieuwe staging-set (de bibliotheek-dedupe op
    hash(content+bron) vangt overlappende atomen bij de commit).

    Fail-closed: geen/te kort rapport → skip; LLM-ladder stil → géén kaartjes, géén
    ledger-record (een latere run mag het opnieuw proberen), één logregel, nooit een crash.

    Retourneert precies één van:
      {"batch": bid, "atoms": n} | {"dry_run": True} | {"skipped": reden} | {"failed": reden}
    """
    dd = context_of_data_dir if isinstance(context_of_data_dir, str) \
        else getattr(context_of_data_dir, "data_dir", None)
    p = project or {}
    pid = p.get("id") or ""
    if not pid or not dd:
        return {"skipped": "geen project"}
    from nooch_village.project_doc_store import ProjectDocStore
    md = ProjectDocStore(dd).read(pid).strip()
    if len(md) < REPORT_MIN_CHARS:
        return {"skipped": "geen rapport"}
    from nooch_village.kennisbank_intake import IntakeLedger, atomiseer, stable_id
    hint = report_source_hint(p)
    ledger = IntakeLedger(os.path.join(dd, "kennisbank_intake.json"))
    if ledger.seen(md, hint) is not None:      # zelfde rapport + zelfde hint → geen LLM, niets dubbel
        return {"skipped": "al verwerkt"}
    if dry_run:
        return {"dry_run": True}
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn      # lazy: alleen dit pad raakt de ladder
    atoms = atomiseer(md, hint, reason_fn=reason_fn)
    if not atoms:
        log.warning("project→staging: atomiser gaf niets voor %s (LLM-ladder stil of "
                    "onbruikbare output) — geen kaartjes, latere run probeert opnieuw", pid)
        return {"failed": "geen atomen (LLM)"}
    for a in atoms:                            # het rapport is de bron; de herkomst moet zichtbaar zijn
        a["source"] = hint
        a["reference"] = project_link(pid)
        a["source_date"] = _iso(p.get("updated_at"))[:10]      # afronddatum
    from nooch_village.kennisbank_staging import StagingStore
    staging = StagingStore(os.path.join(dd, "kennisbank_staging.json"))
    bid = staging.create(STAGING_KIND, hint, atoms)
    ledger.record(md, hint, [stable_id(a["content"], a["source"]) for a in atoms])
    log.info("project→staging: %d voorstel(len) uit rapport van %s in staging-set %s "
             "(even nakijken)", len(atoms), pid, bid)
    return {"batch": bid, "atoms": len(atoms)}


def backfill_reports_to_staging(ledger, data_dir: str, dry_run: bool = False,
                                reason_fn=None) -> dict:
    """Backfill (CLI `projects_to_staging`): loop bestaande done-projecten langs en zet hun
    rapport via `report_to_staging` in de staging. dry_run telt alleen welke projecten een
    set zóuden opleveren (rapport aanwezig + nog niet in de IntakeLedger) — geen LLM, geen
    schrijf. Herdraaien is veilig (ledger-dedupe); een LLM-misser telt als 'mislukt' en kan
    bij een volgende run alsnog. Geeft {"done", "batches", "atoms", "skipped", "mislukt"}."""
    done = ledger.by_status("done")
    res = {"done": len(done), "batches": 0, "atoms": 0, "skipped": 0, "mislukt": 0}
    for p in done:
        r = report_to_staging(data_dir, p, reason_fn=reason_fn, dry_run=dry_run)
        if r.get("batch") or r.get("dry_run"):
            res["batches"] += 1
            res["atoms"] += r.get("atoms") or 0
        elif "failed" in r:
            res["mislukt"] += 1
        else:
            res["skipped"] += 1
    return res
