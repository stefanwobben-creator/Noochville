"""Projectbord → Radar: een afgerond project wordt automatisch een signaal op /signals.

Done is al een mens-poort (review-goedkeuring of bewuste bord-drag), dus het signaal slaat de
wachtkamer over en komt direct als 'goedgekeurd' op /signals te staan. Vandaar geen LLM en geen
extra curatiestap: de founder promoveert/koppelt het daar aan de kennisbank via de bestaande
radar_promote-flow.

Idempotent: link = "/project?id=<pid>" en de `seen`-lijst van de RadarStore ontdubbelt op die
link. Een heropend en opnieuw afgerond project levert dus geen tweede signaal op — de link is
het identiteitsanker, niet de (mogelijk gewijzigde) outcome-tekst. Alles loopt via de
store-methodes (append-only add + set_status + mark_seen); de aanroepers (cockpit-done,
board-watch) wikkelen de aanroep fail-soft in zodat een falend signaal nooit een done blokkeert."""
from __future__ import annotations

from datetime import datetime, timezone

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
    outcome = str(p.get("outcome") or "").strip()
    content = outcome or f"Afgerond: {str(p.get('scope') or pid).strip()}"
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
