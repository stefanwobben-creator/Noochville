"""De loop-breker: een geparkeerd project weer los krijgen door zijn open item op te lossen.

De vastloop-klep (`Inhabitant._execute_checklist`) zet een project op WAITING zodra geen enkel open
item nog vooruit kan, en stelt de mens een vraag. Tot nu toe eindigde het dáár: de mens beantwoordde
of sloot de spanning, maar er schreef niets terug naar het project — het item bleef open, de telling
bleef 4/5, en de volgende reactivering liep tegen exact dezelfde muur. Dat is de herhaal-lus.

Deze module maakt het antwoord van de mens uitvoerbaar, met drie uitkomsten per item:

  done   — 'ik heb het gedaan'  → item afvinken;
  skip   — 'sla over / n.v.t.'  → item uit de klaar-telling halen (blijft staan, mét reden);
  handoff— 'los mens-project'   → overdragen aan een andere rol via het projectverzoek-patroon, en
                                  het item hier overslaan (het werk leeft verder, elders).

Na elk van de drie kijkt `maybe_finish` of de checklist daarmee áf is; zo ja, dan gaat het project
meteen naar review in plaats van te wachten op een puls die het toch niet meer oppakt (een geparkeerd
project wordt niet getend). Dát is de brug die ontbrak.
"""
from __future__ import annotations

from nooch_village.projects import checklist_progress, not_answered_note

_ACTIES = ("done", "skip", "unskip", "handoff")


def _checklist_of(project: dict, clid: str) -> dict | None:
    for cl in (project or {}).get("checklists", []):
        if cl.get("id") == clid:
            return cl
    return None


def _item_of(cl: dict, item_id: str) -> dict | None:
    return next((it for it in (cl or {}).get("items", []) if it.get("id") == item_id), None)


def maybe_finish(ledger, pid: str, clid: str) -> bool:
    """Is de checklist na deze mutatie áf? Zet het project dan op wacht-op-review.

    Nodig omdat een geparkeerd (blocked) project níét meer wordt getend: zonder deze brug zou de
    laatste handeling van de mens wel het item sluiten maar het project op WAITING laten staan —
    precies de klacht. Geen bus-event: dit draait meestal in het cockpit-proces (cross-proces, zie
    de netwerk-bus-naad); de daemon-board-watch ziet de statuswissel zelf."""
    p = ledger.get(pid) or {}
    cl = _checklist_of(p, clid)
    if cl is None:
        return False
    done, telbaar = checklist_progress(cl)
    # `telbaar == 0` (alles overgeslagen) is bewust GEEN afronding: dan is het plan verdampt, en dat
    # verdient het oordeel van de mens op het geparkeerde project — geen automatische review met 0/0.
    if not telbaar or done != telbaar:
        return False
    # Alleen een project dat daadwerkelijk in uitvoering is (of geparkeerd wacht) gaat naar review.
    # Een future/draft/proposed project mag niet door het afvinken van vakjes de review-gate in worden
    # geduwd — dat is werk dat nog niet eens begonnen is.
    if p.get("status") not in ("running", "queued", "blocked"):
        return False
    # De review-melding draagt de overgeslagen taken mee: 4/4 mag nooit lezen als "alles gedaan"
    # wanneer een kernitem bewust is laten vallen. Valse voltooiing is erger dan onaffe voortgang.
    weg = not_answered_note(cl)
    ledger.add_role_message(pid, f"✅ Checklist voltooid ({done}/{telbaar}) — klaar voor review."
                            + (f"\n⤳ LET OP: {weg}. Dit deel van het projectdoel is NIET beantwoord."
                               if weg else ""))
    return ledger.mark_awaiting_review(pid)


def handoff(ledger, naar_rol: str, titel: str, *, done_criterium: str = "",
            records=None, van_pid: str = "") -> dict:
    """Draag werk over aan een andere rol: een queued project op háár bord, met terugverwijzing.

    Dit is de gedeelde kern van het projectverzoek-patroon: de `projectverzoek`-skill (de rol doet het
    zelf) en de mens-knop in de cockpit lopen allebei hierlangs, zodat een overdracht er altijd
    hetzelfde uitziet — reference, don't copy. Fail-soft: onbekende rol of ontbrekende store → error."""
    naar = (naar_rol or "").strip()
    titel = (titel or "").strip()
    if not naar or not titel:
        return {"error": "ontbrekende parameter: 'naar_rol' en 'titel' zijn beide verplicht"}
    if ledger is None:
        return {"error": "geen projectledger in context — kan geen projectverzoek plaatsen"}
    if records is not None and records.get(naar) is None:
        return {"error": f"onbekende doelrol: '{naar}'"}
    done = (done_criterium or "").strip() or titel
    try:
        pid = ledger.create(naar, titel[:200], "tension", status="queued",
                            done_when=done[:200], origin="projectverzoek",
                            links=[van_pid] if van_pid else None)
    except Exception as e:                     # noqa: BLE001 — nette fout terug, geen stacktrace omhoog
        return {"error": f"kon projectverzoek niet plaatsen: {e}"}
    try:                                       # terugverwijzing op het nieuwe project (fail-soft)
        ledger.add_feed_entry(
            pid, f"📥 Binnengekomen als projectverzoek (overdracht van werk dat hier hoort). "
                 f"Klaar wanneer: {done[:160]}", kind="system", author_type="role")
    except Exception:
        pass
    return {"ok": True, "pid": pid, "naar_rol": naar, "titel": titel[:200]}


def resolve_item(ledger, pid: str, clid: str, item_id: str, actie: str, *,
                 reason: str = "", by: str = "", naar_rol: str = "", records=None) -> tuple[bool, str]:
    """Los één open checklist-item op namens de mens. Geeft (gelukt, bericht voor de mens).

    Elke uitkomst laat een systeem-regel op de kaart achter (wie, wat, waarom) én controleert daarna
    of het project daarmee áf is. Zonder die tweede stap sluit de spanning wel maar blijft het
    project hangen — de lus die dit moduul weghaalt."""
    if actie not in _ACTIES:
        return False, f"✗ onbekende actie: {actie}"
    p = ledger.get(pid)
    cl = _checklist_of(p, clid) if p else None
    it = _item_of(cl, item_id) if cl else None
    if it is None:
        return False, "✗ onbekend checklist-item"
    tekst = str(it.get("text", ""))[:120]
    wie = by or "mens"

    if actie == "done":
        if it.get("done"):
            return False, "✓ dit item stond al af"
        ledger.set_item_skipped(pid, clid, item_id, False)     # 'gedaan' wint van een eerdere skip
        ledger.check_toggle(pid, clid, item_id)
        ledger.add_feed_entry(pid, f"✅ Mens-taak afgerond: {tekst}"
                              + (f" — {reason[:200]}" if reason else ""),
                              kind="system", author_type="human", author_id=wie)
        msg = "✓ item afgerond"
    elif actie == "skip":
        if it.get("skipped"):
            return False, "✓ dit item stond al op overgeslagen"
        ledger.set_item_skipped(pid, clid, item_id, True, reason)
        ledger.add_feed_entry(pid, f"⤳ Item overgeslagen (telt niet meer mee): {tekst}"
                              + (f" — {reason[:200]}" if reason else ""),
                              kind="system", author_type="human", author_id=wie)
        msg = "⤳ item overgeslagen — telt niet meer mee"
    elif actie == "unskip":
        if not it.get("skipped"):
            return False, "✓ dit item stond niet op overgeslagen"
        ledger.set_item_skipped(pid, clid, item_id, False)
        ledger.add_feed_entry(pid, f"↩ Overslaan teruggedraaid: {tekst}",
                              kind="system", author_type="human", author_id=wie)
        return True, "↩ item telt weer mee"                    # kan het project nooit áf maken
    else:                                                      # handoff
        res = handoff(ledger, naar_rol, it.get("text", ""), done_criterium=reason,
                      records=records, van_pid=pid)
        if not res.get("ok"):
            return False, "✗ " + str(res.get("error", "overdracht mislukt"))
        ledger.set_item_skipped(pid, clid, item_id, True,
                                f"overgedragen aan {naar_rol} (project {res['pid']})")
        ledger.link(pid, res["pid"])
        ledger.add_feed_entry(pid, f"📤 Overgedragen aan {naar_rol} als eigen project: {tekst}. "
                                   f"Dit item telt hier niet meer mee.",
                              kind="system", author_type="human", author_id=wie)
        msg = f"📤 overgedragen aan {naar_rol}"

    if maybe_finish(ledger, pid, clid):
        msg += " — checklist compleet, project staat klaar voor review"
    return True, msg
