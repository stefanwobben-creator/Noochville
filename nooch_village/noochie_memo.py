"""Eén memo van Noochie aan de founder, op afroep — en sinds scope 42a: over de INHOUD.

Aanleiding (11 september 2026). Stefan: "ik denk dat Noochie nog dingen naar de verkeerde inbox
stuurt want ik zie niks van haar." Gemeten: het was niet de verkeerde inbox maar géén inbox.
`Noochie._on_dag_eindigt` schrijft elke dag een bulletin naar `data/output/` en publiceert
`bulletin_geschreven`; daar luistert precies één ding naar, `village._observe`, een logger. Ze doet
het werk, het bewijs ligt op schijf, en niemand krijgt het te horen.

Scope 41 was de toets van de pijp: één memo, op afroep, via dezelfde `_notify_founder`-route die
elf andere plekken al gebruiken. Die kwam aan. De eerste memo was een overzicht van hoe we
georganiseerd zijn ("17 van de 127 projecten staan vast"), en dat is precies wat je krijgt als je
Noochie alleen tellingen en titels geeft. Stefan, dezelfde middag: "ik mis dat ie inhoudelijk
meedenkt." Twee voorbeelden uit zijn mond, allebei gemeten op de echte data:

- Het mobiel-project "zit vast op 1 item, wacht op een mens". Het projectlog zegt wát dat item is:
  een technische audit van CSS/HTML-broncode. Dat is geen mens-op-een-telefoon-taak, dat is werk
  voor Claude Code op de repo. En twee van de drie metingen die wél draaiden zeggen niets, en dat
  staat er ook: `haal_pagina` las 93 tekens (de loginpagina), `plausible_stats` keek naar
  /collections en /products/the-269-black, dus naar de shop, niet naar village.
- Vier projecten vormen samen één draad die zij niet zag: "Establish Network of footwear factories
  in Spain" (met de top10-pdf, de Alicante-spreadsheet, de INESCOP-link en het comment "eerst
  catalogus/portfolio info opvragen bij de top10"), Cristian/Apolo (done: disqualified), en Mees
  Productions twee keer (lopend en vast, met hun sampling- en design-pdf's).

Daarom leest ze nu de inhoud: per project dat loopt, vastzit of net is afgerond de comments van
mensen, de laatste logregels, het uitvoerplan met wat elk item opleverde (inclusief de reden waarom
een meting leeg was), de bijlagen en de tekst uit pdf's. Plus de wiki, de claims per status en de
werkoverleg-backlog. En één ding gaat er juist UIT: haar eigen oude ruis, de comments van
`noochie_persona` uit de gesloopte matchlaag ("@Library, dit lijkt binnen jouw scope (skill:
keyword_review). Oppakken?" op het mobiel-project). Anders leest ze haar eigen onzin als inhoud.

Drie keuzes die niet toevallig zijn:

- **Rauwe invoer, geen eerdere LLM-tekst.** De Field Notes en het bulletin zijn zelf al
  LLM-output; die opnieuw laten samenvatten geeft een memo die geïnformeerd klinkt en niets zegt.
  Logregels van rollen zijn wél inhoud: ze zeggen wat een skill echt opleverde.
- **Sonnet 5 via `HOOG_INZET`.** Mens-facing, zelfde reden als `skill_bulletin`. Kosten zijn hier
  bewust geen overweging; het is één call per memo, en de invoer is begroot (`INVOER_BUDGET`).
- **Fail-closed op de LLM.** Geen antwoord = geen memo, en dat zegt het commando met zoveel
  woorden. Er wordt nooit een sjabloon bezorgd alsof Noochie hem schreef.

De memo is in het Nederlands: rapportage aan de mens volgt de taal van de mens (CLAUDE.md, "Taal
van een output"), en dit is precies dat. De memo mag een terminal- of Claude Code-opdracht bevatten:
dat is de ene naar-mens-tekst waar de founder er expliciet om vroeg (`views/inbox.py`,
`notifications._meld_commando` kennen het type daarom).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter

from nooch_village import projects as _P

log = logging.getLogger("village.noochie_memo")

CALL_SITE = "noochie_memo"
AFZENDER = "noochie"
#: Het type dat het inbox-item bij het ontstaan meekrijgt. Daardoor slaat `NotifStore.add` de
#: herschrijf-poort over: die zou de memo (niet-mens-schrijver → herschrijf=True) door een goedkoop
#: model laten herformuleren tot een spanning. De inbox rendert dit type als document (markdown met
#: codeblokken), niet als beslis-kaart — precies wat een memo moet zijn.
TYPE = "memo"

#: Hoeveel dagen aan events de memo meekrijgt.
DAGEN = 7
#: Een afgerond project telt nog zo lang mee als "wat er net gebeurd is": dat is waar de draden
#: zitten (een gediskwalificeerde leverancier zegt iets over de zoektocht die nog loopt).
AFGEROND_DAGEN = 30
#: Bijlagen worden alleen gelezen op projecten die recent zijn aangeraakt; een pdf van een maand
#: geleden op een lopend project is meestal al verwerkt in het log.
PDF_DAGEN = 21
MAX_COMMENTS = 8
MAX_LOG = 6
MAX_PLAN = 10
MAX_BIJLAGEN = 4
MAX_TITELS = 8
PDF_TEKENS = 1800            # per bijlage
PDF_BUDGET = 24_000          # totaal aan pdf-tekst over de hele memo
#: Tekens JSON voor projecten mét inhoud (~45k tokens). Daarboven krijgt een project alleen nog
#: titel + status: de memo moet kunnen kiezen, niet verzuipen.
INVOER_BUDGET = 180_000

#: Statussen waarvan de inhoud altijd meegaat: wat op het bord staat (`projects.OP_HET_BORD`) plus
#: wat is voorgesteld en op een oordeel wacht. `future` telt alleen mee in de telling: 58 stuks op
#: 11 september, en die zijn per definitie nog niet aan de orde. Het vocabulaire komt uit
#: `projects.py`; hier wordt niets opgesomd (test_status_vocabulaire).
ACTIEF = _P.OP_HET_BORD + ("proposed",)

#: De oude matchlaag (verwijderd in scope 39) liet Noochie's persona op honderden projecten een
#: comment achter van de vorm "@Rol, dit lijkt binnen jouw scope (skill: x). Oppakken?". Het waren
#: gokken op een skill-naam, geen inhoud. Ze staan nog in de logs; hier gaan ze eruit.
_RUIS = re.compile(r"dit lijkt binnen jouw scope", re.I)


# ── 1. Verzamelen: rauwe feiten, geen oordelen ───────────────────────────────

def _dagen_geleden(ts, nu: float) -> int | None:
    try:
        return max(0, int((nu - float(ts)) / 86400))
    except (TypeError, ValueError):
        return None


def _auteur(e: dict) -> str:
    """mens | persona | rol | systeem — uit de twee logvormen die het bord kent (`who` en `author`)."""
    a = e.get("author") or {}
    t = str(a.get("type") or "")
    if t in ("human", "person") or e.get("who") == "mens":
        return "mens"
    if t == "persona":
        return "persona"
    if e.get("kind") == "system":
        return "systeem"
    return "rol"


def _is_ruis(e: dict) -> bool:
    return _auteur(e) == "persona" and bool(_RUIS.search(str(e.get("text") or "")))


def _plan_items(p: dict) -> list[dict]:
    """Het uitvoerplan zoals het er echt bij staat: per item of het klaar is, welke skill, en wat
    de uitkomst zei. `leeg_reden` is het veld dat op het mobiel-project "93 tekens gelezen" droeg —
    zonder dat veld ziet een afgevinkte meting eruit als een geslaagde meting."""
    uit = []
    for cl in p.get("checklists") or []:
        for it in cl.get("items") or []:
            rij = {"item": str(it.get("text") or "")[:160], "klaar": bool(it.get("done"))}
            if it.get("skill"):
                rij["skill"] = it["skill"]
            if it.get("human_task"):
                rij["mens_taak"] = True
            if it.get("leeg"):
                rij["leeg"] = str(it.get("leeg_reden") or "leeg")[:200]
            if it.get("skipped"):
                rij["overgeslagen"] = str(it.get("skip_reason") or "")[:160]
            if it.get("routed"):
                rij["doorgestuurd"] = True
            if not it.get("done") and it.get("reason"):
                rij["waarom_niet"] = str(it["reason"])[:200]
            uit.append(rij)
    return uit[:MAX_PLAN]


def _bijlagen(p: dict, data_dir: str, *, pdf_lezen: bool, pdf_ruimte: list[int]) -> list[dict]:
    """Links met titel, bestanden met naam, en van pdf's de tekst (begrensd, binnen het totale
    pdf-budget). `pdf_ruimte` is een één-elements lijst: het resterende budget, gedeeld over alle
    projecten van deze memo."""
    uit = []
    for b in (p.get("attachments") or [])[-MAX_BIJLAGEN:]:
        rij = {"soort": b.get("kind") or "?", "naam": str(b.get("title") or b.get("name") or "")[:120]}
        if b.get("url"):
            rij["url"] = str(b["url"])[:200]
        stored = str(b.get("stored") or "")
        if pdf_lezen and stored.lower().endswith(".pdf") and pdf_ruimte[0] > 0:
            tekst = _pdf_tekst(os.path.join(data_dir, stored), str(b.get("name") or ""))
            if tekst:
                tekst = tekst[:min(PDF_TEKENS, pdf_ruimte[0])]
                pdf_ruimte[0] -= len(tekst)
                rij["tekst"] = tekst
            else:
                rij["tekst"] = None                 # geen tekstlaag of onleesbaar: benoemd, niet verzonnen
        uit.append(rij)
    return uit


def _pdf_tekst(pad: str, naam: str) -> str | None:
    """Dezelfde lezer als de kennisbank (`kennisbank_sources.van_pdf`): één plek die weet wat een
    scan zonder tekstlaag is. Fail-soft: een onleesbaar bestand geeft None, geen fout in de memo."""
    try:
        from nooch_village.kennisbank_sources import van_pdf
        with open(pad, "rb") as f:
            chunks = van_pdf(f.read(), naam)
    except Exception as exc:                          # noqa: BLE001
        log.debug("noochie_memo: pdf %s onleesbaar: %s", pad, exc)
        return None
    if not chunks:
        return None
    return " ".join(str(c[0]) for c in chunks).strip() or None


def _project_inhoud(p: dict, data_dir: str, nu: float, *, pdf_ruimte: list[int]) -> dict:
    """Wat er ECHT in een project staat, in de vorm waarin Noochie ermee kan denken."""
    from nooch_village.views.projects import _scope_text

    rij = {
        "titel": _scope_text(p)[:120],
        "status": p.get("status") or "?",
        "eigenaar": p.get("owner") or "",
        "bijgewerkt_dagen_geleden": _dagen_geleden(p.get("updated_at"), nu),
    }
    for veld, naam in (("done_when", "klaar_als"), ("outcome", "uitkomst"), ("learnings", "learnings"),
                       ("resultaat", "resultaat"), ("resultaat_toelichting", "resultaat_toelichting"),
                       ("opdrachtgever", "opdrachtgever")):
        if p.get(veld):
            rij[naam] = str(p[veld])[:300]
    impact = {k: p.get(k) for k in ("missie_impact", "business_impact", "effort") if p.get(k)}
    if impact:
        rij["impact"] = impact
    if p.get("cluster") and p.get("cluster") != p.get("id"):
        rij["cluster"] = p["cluster"]
    if p.get("status") == "blocked" and p.get("blocked_on") not in (None, "", "—"):
        rij["wacht_op"] = str(p["blocked_on"])[:160]
    log_ = [e for e in (p.get("log") or []) if isinstance(e, dict) and not _is_ruis(e)]
    comments = [e for e in log_ if _auteur(e) == "mens" and e.get("kind", "comment") == "comment"]
    if comments:
        rij["comments_van_mensen"] = [str(e.get("text") or "")[:400] for e in comments[-MAX_COMMENTS:]]
    rest = [e for e in log_ if e not in comments]
    if rest:
        rij["log"] = [f"[{_auteur(e)}] " + " ".join(str(e.get("text") or "").split())[:350]
                      for e in rest[-MAX_LOG:]]
    plan = _plan_items(p)
    if plan:
        rij["uitvoerplan"] = plan
        blok = [i["item"] for i in plan if not i["klaar"] and (i.get("mens_taak") or i.get("doorgestuurd"))]
        if blok:
            rij["blokkeert_op"] = blok
    recent = (rij["bijgewerkt_dagen_geleden"] or 0) <= PDF_DAGEN
    bijl = _bijlagen(p, data_dir, pdf_lezen=recent and p.get("status") in ACTIEF,
                     pdf_ruimte=pdf_ruimte)
    if bijl:
        rij["bijlagen"] = bijl
    return rij


def _projecten(st, data_dir: str, nu: float | None = None) -> dict:
    """Per status een telling, en de INHOUD van wat loopt, vastzit of net is afgerond."""
    nu = nu or time.time()
    try:
        alle = [p for p in st.projects.all() if isinstance(p, dict)]
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: projecten onleesbaar: %s", exc)
        return {"fout": str(exc)}
    levend = [p for p in alle if not p.get("archived")]
    per_status = Counter(p.get("status") or "?" for p in levend)

    def recent_af(p):
        if p.get("status") not in _P.KLAAR:
            return False
        d = _dagen_geleden(p.get("resultaat_at") or p.get("archived_at") or p.get("updated_at"), nu)
        return d is not None and d <= AFGEROND_DAGEN

    # Volgorde = prioriteit voor het budget: wat vastzit eerst, dan wat loopt, dan de wachtrij
    # (`OP_HET_BORD` achterstevoren), dan wat is voorgesteld, dan wat net af is. Binnen een groep
    # het recentst bijgewerkte eerst.
    rang = {s: i for i, s in enumerate(reversed(_P.OP_HET_BORD))}
    rang["proposed"] = len(rang)
    keuze = [p for p in levend if p.get("status") in ACTIEF] + [p for p in alle if recent_af(p)]
    keuze.sort(key=lambda p: (rang.get(p.get("status"), len(rang)), -float(p.get("updated_at") or 0)))

    pdf_ruimte = [PDF_BUDGET]
    inhoud, alleen_titel, omvang = [], [], 0
    for p in keuze:
        rij = _project_inhoud(p, data_dir, nu, pdf_ruimte=pdf_ruimte)
        lengte = len(json.dumps(rij, ensure_ascii=False))
        if omvang + lengte > INVOER_BUDGET:
            alleen_titel.append({"titel": rij["titel"], "status": rij["status"]})
            continue
        omvang += lengte
        inhoud.append(rij)
    uit = {"per_status": dict(per_status), "totaal": len(levend),
           "afgerond_laatste_dagen": AFGEROND_DAGEN, "inhoud": inhoud}
    if alleen_titel:
        uit["buiten_budget_alleen_titel"] = alleen_titel
    return uit


def _claims(data_dir: str) -> dict:
    """De werklijst uit de claims-database, per status. Niet alleen 'open': op de server stond
    alles op `in behandeling` of `live`, en met alleen een open-telling zag Noochie '0 open' en
    schreef 'óf klaar, óf niet bijgehouden' — een artefact van de feed, niet van de werklijst."""
    try:
        from nooch_village import claims_db
        db = claims_db.load(data_dir=data_dir)
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: claims-database onleesbaar: %s", exc)
        return {"fout": str(exc)}
    wl = db.get("werklijst") or []
    per_status: dict[str, list] = {}
    for i in wl:
        per_status.setdefault(str(i.get("status") or "?"), []).append(i)
    return {
        "werklijst": len(wl),
        "per_status": {s: len(items) for s, items in per_status.items()},
        "per_oordeel": dict(Counter(str(i.get("oordeel") or "?") for i in wl)),
        "voorbeelden_per_status": {s: [(i.get("claim") or "")[:80] for i in items[:2]]
                                   for s, items in per_status.items()},
        "handhaving": ((db.get("meta") or {}).get("regelgeving") or {}).get("empco", ""),
    }


def _events(data_dir: str, dagen: int = DAGEN) -> dict:
    """De events uit `system_log.jsonl` van de afgelopen dagen, geteld per naam.

    Het log heeft geen tijdstempel per regel (village._observe schrijft alleen naam + data), dus we
    nemen de STAART van het bestand. Dat is een benadering en de memo krijgt dat te horen."""
    pad = os.path.join(data_dir, "system_log.jsonl")
    namen: Counter = Counter()
    regels = 0
    try:
        with open(pad, encoding="utf-8") as f:
            staart = f.readlines()[-2000:]
        for regel in staart:
            try:
                e = json.loads(regel)
            except ValueError:
                continue
            namen[e.get("event") or "?"] += 1
            regels += 1
    except FileNotFoundError:
        return {"regels": 0, "per_event": {}, "opmerking": "geen system_log gevonden"}
    except Exception as exc:                          # noqa: BLE001
        return {"fout": str(exc)}
    return {"regels": regels, "per_event": dict(namen.most_common(15)),
            "opmerking": f"de laatste {regels} regels van het log; geen tijdstempel per regel"}


def _draaistaat(data_dir: str) -> dict:
    """Wat het gereedschap heeft gedaan. Leeg vlak na de deploy van scope 40, en dat mag de memo
    gewoon zeggen."""
    try:
        from nooch_village import draaistaat
        s = draaistaat.Draaistaat(draaistaat.pad_voor(data_dir)).samenvatting()
    except Exception as exc:                          # noqa: BLE001
        return {"fout": str(exc)}
    return {"skills_gedraaid": len(s),
            "zonder_opbrengst": sorted(k for k, v in s.items() if not v.get("laatste_opbrengst")),
            "met_opbrengst": sorted(k for k, v in s.items() if v.get("laatste_opbrengst"))}


def _backlog(st, circle: str) -> list[str]:
    """Open spanningen in de werkoverleg-backlog van een cirkel."""
    try:
        return [(b.get("title") or "")[:90] for b in st.werk.backlog(circle)][:MAX_TITELS]
    except Exception as exc:                          # noqa: BLE001
        log.debug("noochie_memo: backlog onleesbaar: %s", exc)
        return []


def _wiki(st) -> list[dict]:
    """De wiki: titel, eigenaar, het begin van de tekst en de feiten. Dit is het geheugen van het
    dorp dat een mens heeft geschreven of goedgekeurd; het hoort bij wat Noochie 'al weet'."""
    try:
        from nooch_village import wiki
        pags = wiki.paginas(st.att)
    except Exception as exc:                          # noqa: BLE001
        log.debug("noochie_memo: wiki onleesbaar: %s", exc)
        return []
    uit = []
    for a in pags[:40]:
        rij = {"titel": (a.title or "")[:120], "eigenaar": a.anchor,
               "begin": " ".join((a.body or "").split())[:300]}
        fs = [str(f.get("tekst") or "")[:160] for f in wiki.feiten(a)][:5]
        if fs:
            rij["feiten"] = fs
        uit.append(rij)
    return uit


def verzamel(st, data_dir: str, circle: str = "mother_earth__nooch") -> dict:
    """Alle rauwe invoer voor één memo. Elke bron faalt los: een kapotte store levert een `fout`-
    veld op, niet een lege memo."""
    return {
        "datum": time.strftime("%Y-%m-%d"),
        "projecten": _projecten(st, data_dir),
        "claims": _claims(data_dir),
        "wiki": _wiki(st),
        "werkoverleg_backlog": _backlog(st, circle),
        "events": _events(data_dir),
        "gereedschap": _draaistaat(data_dir),
    }


def omvang(feiten: dict) -> dict:
    """Hoe groot de invoer is, voor de terminal: projecten met inhoud, pdf's gelezen, tekens."""
    pr = feiten.get("projecten") or {}
    inhoud = pr.get("inhoud") or []
    pdfs = sum(1 for p in inhoud for b in p.get("bijlagen") or [] if b.get("tekst"))
    tekens = len(json.dumps(feiten, ensure_ascii=False))
    return {"projecten_met_inhoud": len(inhoud), "alleen_titel": len(pr.get("buiten_budget_alleen_titel") or []),
            "pdfs_gelezen": pdfs, "wiki_paginas": len(feiten.get("wiki") or []),
            "tekens": tekens, "tokens_ongeveer": tekens // 4}


# ── 2. Schrijven ─────────────────────────────────────────────────────────────

#: Wat Noochie over de omgeving moet weten om een bruikbare opdracht te schrijven. Bewust klein en
#: stabiel: wat een repo is en waar de site leeft, geen feiten die drijven.
_OMGEVING = (
    "- village.nooch.earth is deze applicatie zelf: de Python-repo `noochville` (package "
    "`nooch_village/`, views in `nooch_village/views/`, CSS in `nooch_village/static/nooch.css` en "
    "de basis-CSS in `web_base._CSS`, tests met `pytest tests/`). Stefan laat wijzigingen daaraan "
    "bouwen door Claude Code: een opdracht voor Claude Code is een prompt in gewone taal die hij "
    "plakt, met scope, wat er af moet zijn en hoe dat te toetsen is.\n"
    "- nooch.earth is de Shopify-shop (eigen thema, aparte repo). Bezoekersdata via Plausible "
    "gaat over nooch.earth; village.nooch.earth zit achter een login.\n"
    "- Rollen die eindigen op een naam als `financial_controller` of `website_developer` zijn "
    "Holacracy-rollen in de Nooch-cirkel; een mens vult ze in, de AI helpt.\n"
)


def prompt_voor(feiten: dict) -> str:
    return (
        "Je bent Noochie, de AI-rol van Nooch (nooch.earth, plantaardige made-to-order sneakers, "
        "missie: het duurzaamste schoenenmerk ter wereld zijn). Je schrijft één memo aan Stefan, "
        "founder en bestuurder.\n\n"
        "Hieronder staat de INHOUD van het dorp: projecten met hun logboek, de comments van "
        "mensen, het uitvoerplan met wat elk item echt opleverde, bijlagen (soms met de tekst uit "
        "een pdf), de claims-werklijst per status, de wiki, de werkoverleg-backlog. Geen "
        "conclusies: dat is jouw werk.\n\n"
        "Wat een goede memo is: niet een overzicht van hoe we georganiseerd zijn, maar meedenken "
        "over de inhoud. Je zoekt de DRADEN: meerdere projecten die samen één vraag zijn (bijv. "
        "'we zoeken een productiepartner'). Je leest wat er echt gebeurd is (welke taak blokkeert "
        "en wat die taak inhoudt, wat een meting wél of niet zei en of die meting überhaupt naar "
        "het juiste keek, wat een mens in een comment schreef, wat in een pdf staat) en je zegt "
        "wat de volgende concrete stap is. En die stap maak je zo klaar mogelijk. De comments van "
        "mensen wegen het zwaarst: dat is wat het team zelf zegt. Een logregel van een rol zegt wat "
        "een skill echt opleverde; lees hem letterlijk, ook als de meting niets waard blijkt.\n\n"
        "Omgeving:\n" + _OMGEVING + "\n"
        "Vorm:\n"
        "- Nederlands, informeel, direct. Geen aanhef, geen kop 'MEMO', geen inleiding, geen "
        "afsluiting.\n"
        "- De EERSTE regel is één onderwerpregel van hooguit 120 tekens: de draden van deze memo, "
        "gescheiden door ' · '. Daarna een lege regel.\n"
        "- Maximaal 3 draden. Per draad:\n"
        "  ### <titel van de draad>\n"
        "  **Wat ik zie**: 2 tot 4 zinnen, met de bron erbij (welk project, wat er in het log, "
        "het comment of de pdf staat). Getallen alleen met bron. Geen tijdsduur verzinnen: als "
        "er geen datum staat, zeg je niet 'al een tijd'.\n"
        "  **Wat jij nu kunt doen**: één concrete stap, en het artefact erbij. Is het repo-werk, "
        "dan een opdracht voor Claude Code in een codeblok (```), compleet genoeg om te plakken: "
        "wat, waar, wanneer klaar, hoe te toetsen. Is het een mail, dan het mailconcept. Is het "
        "een keuze, dan de beslissing met 2 of 3 opties en jouw voorkeur. Niet 'overweeg om', "
        "maar het ding zelf.\n"
        "- Daarna **Wat ik niet weet**: hooguit 3 punten, wat je uit deze inhoud niet kunt "
        "afleiden en wel zou willen weten.\n"
        "- Verzin niets. Interne veldnamen (zoals 'voorbeelden_open' of 'leeg_reden') noem je "
        "niet; je zegt het in gewone taal.\n"
        "- Sla over wat er niet toe doet. Een lege bron is leeg, geen probleem, tenzij het een "
        "probleem is.\n"
        "- Hoogstens 700 woorden, codeblokken niet meegeteld.\n\n"
        f"INHOUD (JSON):\n{json.dumps(feiten, ensure_ascii=False, indent=1)}\n"
    )


def _ladder():
    """De hoog-inzet-ladder voor deze call-site; fail-soft naar de dorpsladder."""
    try:
        from nooch_village.llm_keuze import ladder_voor
        return ladder_voor(CALL_SITE)
    except Exception:                                 # noqa: BLE001
        return None


def schrijf(feiten: dict) -> str | None:
    """Laat Noochie de memo schrijven. None als er geen LLM-antwoord is: fail-closed, geen sjabloon."""
    try:
        from nooch_village.llm import reason
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: llm niet beschikbaar: %s", exc)
        return None
    tekst = reason(prompt_voor(feiten), ladder=_ladder(), max_tokens=3000, call_site=CALL_SITE)
    tekst = (tekst or "").strip()
    return tekst or None


_MAANDEN = ("jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec")


def _nl_datum(iso: str) -> str:
    """'2026-09-11' → '11 sep 2026'; iets anders blijft wat het is."""
    try:
        j, m, d = (int(x) for x in iso.split("-"))
        return f"{d} {_MAANDEN[m - 1]} {j}"
    except (ValueError, IndexError):
        return iso


def met_onderwerp(tekst: str, datum: str) -> str:
    """Zet de onderwerpregel om in de eerste regel die de inbox als preview toont.

    De store leidt de preview zelf af uit de volledige tekst (één waarheid, `notifications.preview`),
    dus de enige manier om een leesbare regel in de lijst te krijgen is hem vooraan in de tekst te
    zetten. Schreef het model geen onderwerpregel (begint met een kop), dan komen de koppen zelf."""
    regels = tekst.strip().split("\n")
    eerste = regels[0].strip() if regels else ""
    if eerste and not eerste.startswith("#") and len(eerste) <= 160:
        onderwerp = re.sub(r"^(onderwerp|subject)\s*:\s*", "", eerste.strip("*").strip(), flags=re.I)
        rest = "\n".join(regels[1:]).strip()
    else:
        koppen = [r.strip().lstrip("#").strip() for r in regels if r.strip().startswith("### ")]
        onderwerp, rest = " · ".join(koppen)[:120] or "memo", tekst.strip()
    return f"Memo van Noochie, {_nl_datum(datum)}: {onderwerp}\n\n{rest}"


# ── 3. Bezorgen ──────────────────────────────────────────────────────────────

def lever(data_dir: str, tekst: str) -> bool:
    """Zet de memo in de cockpit-inbox van de founder, via de bestaande heads-up-route.

    Bewust dezelfde functie als de elf andere founder-meldingen: één bezorgroute, één plek waar
    `FOUNDER_ROLE_ID` telt. De store bewaart de volle tekst en leidt zelf de preview af."""
    try:
        from nooch_village.human_inbox import _notify_founder
        inbox_pad = os.path.join(data_dir, "human_inbox.json")
        _notify_founder(inbox_pad, by=AFZENDER, snippet=tekst, extra={"type": TYPE})
        return True
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: bezorgen mislukt: %s", exc)
        return False


# ── Het geheel ───────────────────────────────────────────────────────────────

def memo(st, data_dir: str, *, apply: bool = True) -> dict:
    """Verzamel, schrijf, bezorg. Geeft een rapport terug dat zegt wat er wél en niet gebeurde.

    `apply=False` schrijft de memo wel maar bezorgt niet: je leest hem in de terminal en beslist
    dan. Dat is de dry-run-conventie van het dorp (`wiki_zaad`, `wiki_broncheck`)."""
    feiten = verzamel(st, data_dir)
    tekst = schrijf(feiten)
    if tekst is None:
        return {"ok": False, "reden": "geen LLM-antwoord: memo niet geschreven en niet bezorgd",
                "feiten": feiten, "tekst": None, "bezorgd": False}
    tekst = met_onderwerp(tekst, feiten.get("datum") or time.strftime("%Y-%m-%d"))
    bezorgd = lever(data_dir, tekst) if apply else False
    return {"ok": True, "tekst": tekst, "bezorgd": bezorgd, "feiten": feiten,
            "reden": "" if (bezorgd or not apply) else "geschreven maar niet bezorgd"}
