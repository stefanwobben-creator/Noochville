"""ronde_twee — de namen uit wat gelezen is, opnieuw opgezocht en beoordeeld.

AANLEIDING (12 september 2026). Het dorp schreef zijn zoekplan in één keer, draaide het, en stopte.
Wat een mens dan doet, deed niemand: de namen die in de gevonden teksten opduiken (Kiilto, acib,
nahtur-design) opnieuw googelen, hun site openen en beslissen of dit iets is. Stefan: "waarom kan
AI niet zelf een site via Google opzoeken en bekijken?" Het kon half; dit is de andere helft.

HOE HET WERKT, en waarom precies zo:
- **Wanneer.** Op het moment dat de uitvoerlijst helemaal af is en het project anders naar review
  zou gaan. Niet eerder, want de rol werkt één lijst (`uitvoerlijst` is exclusief): een tweede
  lijst eerder aanmaken zou de open items van de eerste in de steek laten.
- **Waaruit.** De deliverables van het project (de store, met de extracten van scope 50) — dus ook
  wat op een eerdere dag gelezen is. Zonder store: de oogst van deze puls.
- **Wat.** Eén goedkope modelronde haalt de leads uit dat materiaal (bedrijven, producten,
  instituten, merken die een nadere blik verdienen) plus de criteria van de opdracht, zodat elke
  lead langs dezelfde lat gaat. Per lead één item `lead_beoordeling` (naam, url als die er al was,
  vraag, opdracht, criteria).
- **Als voorstel.** De tweede lijst krijgt `akkoord=False` en wacht op dezelfde 'go ahead' als elk
  plan: zoeken kost credits, en de mens ziet zo welke namen het dorp wil nalopen vóór er iets
  draait. Zelfde knip als bij het eerste plan.
- **Eén keer.** `ronde_twee_van` op de lijst is de rem, precies zoals `herplan_van` dat is voor de
  strategie. Ronde drie zou weer leads opleveren uit de beoordelingen, en dan zoekt het dorp door
  zonder ooit te concluderen.

FAIL-SOFT. Geen model, geen leads, de rol heeft de skill niet: dan gaat het project gewoon naar
review, zoals het altijd deed. Ronde twee is een dienst, geen voorwaarde.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("village.ronde_twee")

SKILL = "lead_beoordeling"
#: De titel van de tweede lijst. Bewust NIET `PREP_CHECKLIST_TITLE`: die wordt op de kaart
#: verzwegen als default-naam, en juist hier wil je zien dat dit ronde twee is. De rol vindt de
#: lijst via de `uitvoer`-vlag (regel 1 van `uitvoerlijst`), niet via de titel.
TITEL = "Round two: leads"
MAX_LEADS_DEFAULT = 5
MAX_CRITERIA = 6
_MAX_MATERIAAL = 7000            # tekens materiaal in de prompt: ~2000 tokens, goedkope trede
_MAX_RECORDS = 25
_STREKKING = ("extract", "abstract", "tldr", "fragment", "snippet")
_TITEL = ("titel", "title", "name", "term", "naam")
_ADRES = ("url", "link")
_PARTIJEN = ("applicants", "assignee", "authors", "inventors")


def _kort(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _records(inhoud: dict) -> list[dict]:
    """De grootste lijst van dicts in een resultaat (dezelfde keuze als het verslag maakt)."""
    beste: list = []
    for k, v in (inhoud or {}).items():
        if str(k).startswith("_"):
            continue
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v) and len(v) > len(beste):
            beste = v
    return beste


def _regel(r: dict) -> str:
    titel = next((str(r[k]) for k in _TITEL if isinstance(r.get(k), str) and r[k].strip()), "")
    adres = next((str(r[k]) for k in _ADRES if isinstance(r.get(k), str) and r[k].strip()), "")
    strekking = next((str(r[k]) for k in _STREKKING if isinstance(r.get(k), str) and r[k].strip()), "")
    partijen = []
    for k in _PARTIJEN:
        v = r.get(k)
        if isinstance(v, list) and v:
            partijen.append(f"{k}: " + ", ".join(str(x) for x in v[:4]))
    delen = [d for d in (_kort(titel, 100), adres and f"<{_kort(adres, 100)}>", _kort(strekking, 320),
                         "; ".join(partijen)) if d]
    return "• " + " — ".join(delen) if delen else ""


def materiaal_uit_resultaten(resultaten) -> str:
    """`resultaten` = iterable van (item_tekst, inhoud-dict). Eén tekstblok, gecapt."""
    regels: list[str] = []
    n = 0
    for item_tekst, inhoud in resultaten or []:
        if not isinstance(inhoud, dict):
            continue
        recs = _records(inhoud)
        if not recs:
            continue
        regels.append(f"[{_kort(item_tekst, 90)}]")
        for r in recs:
            regel = _regel(r)
            if regel:
                regels.append(regel)
                n += 1
            if n >= _MAX_RECORDS:
                break
        if n >= _MAX_RECORDS:
            break
    tekst = "\n".join(regels)
    return tekst[:_MAX_MATERIAAL]


def materiaal_uit_store(store, pid: str) -> str:
    """Het materiaal uit de deliverable-store van dit project. Fail-soft: leeg bij een stukke store."""
    if store is None or not pid:
        return ""
    try:
        recs = store.for_project(pid) or []
    except Exception as e:                                   # noqa: BLE001 — luid, niet stil
        log.warning("ronde_twee: deliverables niet leesbaar voor %s: %s", pid, e)
        return ""
    paren = []
    for r in recs:
        try:
            inhoud = store.content_for(r["id"])
        except Exception:                                    # noqa: BLE001
            inhoud = None
        if isinstance(inhoud, dict) and not inhoud.get("_truncated"):
            paren.append((r.get("title") or r.get("skill") or "", inhoud))
    return materiaal_uit_resultaten(paren)


def _json_uit(rauw):
    tekst = str(rauw or "").strip()
    if not tekst:
        return None
    tekst = re.sub(r"^```(?:json)?|```$", "", tekst, flags=re.M).strip()
    try:
        return json.loads(tekst)
    except Exception:                                        # noqa: BLE001
        m = re.search(r"\{.*\}", tekst, re.S)
        try:
            return json.loads(m.group()) if m else None
        except Exception:                                    # noqa: BLE001
            return None


def _prompt(goal: str, description: str, materiaal: str, max_leads: int) -> str:
    return (
        "Below are the findings of one research round for a project. Pick the leads worth a closer "
        "look: companies, products, institutes, brands or projects that are named in the findings and "
        "that could answer the goal. Skip generic articles, blogs, marketplaces and pages that only "
        "explain the topic. Skip the project owner's own brand.\n\n"
        f"GOAL: {_kort(goal, 300)}\n"
        f"ASSIGNMENT: {_kort(description, 500) or '(none)'}\n\n"
        f"FINDINGS:\n{materiaal}\n\n"
        f"Give at most {max_leads} leads, best first. For each: the name as it appears, what kind of "
        "thing it is, the URL of its OWN site only if a finding gives it (else empty), and one clause "
        "why it is worth a look. Also list the criteria the assignment or goal implies for judging "
        f"a lead (at most {MAX_CRITERIA}, short noun phrases such as 'plastic-free', 'proven in "
        "footwear', 'available in the EU'). Do not invent names that are not in the findings. Write "
        "in English; names stay as they are.\n\n"
        "Answer ONLY with JSON, exactly this shape:\n"
        '{"leads": [{"naam": "...", "soort": "company|product|institute|brand|project", '
        '"url": "", "waarom": "..."}], "criteria": ["..."]}'
    )


def leads_uit(goal: str, description: str, materiaal: str, *, reason_fn=None, ladder=None,
              max_leads: int = MAX_LEADS_DEFAULT) -> tuple[list[dict], list[str]]:
    """(leads, criteria) uit het materiaal, één modelronde. Fail-soft: ([], [])."""
    if not (materiaal or "").strip():
        return [], []
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn        # noqa: PLC0415 — lazy, testbaar
    try:
        rauw = reason_fn(_prompt(goal, description, materiaal, max_leads), json_mode=True,
                         max_tokens=700, call_site="ronde_twee_leads", ladder=ladder)
    except Exception as exc:                                 # noqa: BLE001 — nooit de puls breken
        log.info("ronde_twee: model faalde (%s)", exc)
        return [], []
    data = _json_uit(rauw)
    if not isinstance(data, dict):
        return [], []
    leads: list[dict] = []
    gezien: set[str] = set()
    for l in (data.get("leads") or []):
        if not isinstance(l, dict):
            continue
        naam = _kort(l.get("naam"), 100)
        if not naam or naam.lower() in gezien:
            continue
        gezien.add(naam.lower())
        url = str(l.get("url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            url = ""                                         # geen adres → de skill zoekt zelf
        leads.append({"naam": naam, "soort": _kort(l.get("soort"), 30), "url": url,
                      "waarom": _kort(l.get("waarom"), 160)})
        if len(leads) >= max(1, int(max_leads)):
            break
    criteria: list[str] = []
    for c in (data.get("criteria") or []):
        c = _kort(c, 60)
        if c and c.lower() not in {x.lower() for x in criteria}:
            criteria.append(c)
        if len(criteria) >= MAX_CRITERIA:
            break
    return leads, criteria


def plan_items(leads: list[dict], goal: str, description: str, criteria: list[str]) -> list[dict]:
    """Per lead één item in de vorm van `_plan_checklist` (`text`, `skill`, `payload`, `reason`)."""
    uit = []
    for l in leads:
        payload = {"naam": l["naam"], "url": l.get("url") or "", "vraag": _kort(goal, 300),
                   "opdracht": _kort(description, 600), "criteria": list(criteria)}
        uit.append({"text": f"Assess lead: {l['naam']}" + (f" ({l['soort']})" if l.get("soort") else ""),
                    "skill": SKILL, "payload": payload,
                    "reason": l.get("waarom") or "named in the findings of round one"})
    return uit
