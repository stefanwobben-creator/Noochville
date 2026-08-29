"""Kennis-eerst — deterministische raadpleging van Lara's kennislaag bij projectstart.

Elke rol die aan een project begint raadpleegt EERST de kennislaag en neemt wat hij vindt
mee als context, zodat hij niet opnieuw uitvindt maar aanvult. Drie bronnen, alle drie
bestaande stores (alleen store-methodes, geen LLM):
  - kaartjes (atomen)  : NotesStore.relevant_for — het bestaande zeldzaamheids-gewogen
    woord-overlap-mechanisme op het word-veld;
  - inzichten (laag 2) : KennisbankStore — zelfde soort matching, gespiegeld op titel + why,
    met het live berekende verdict-woord (field/verdict) erbij;
  - signalen           : RadarStore.all_approved — goedgekeurd én nog niet gepromoveerd
    naar de kennisbank (promoted_atom_id leeg).

Fail-soft overal: een ontbrekende of kapotte store levert een lege deelverzameling op en
blokkeert het projectwerk nooit. De raadpleging zelf is puur deterministisch; de gevonden
kennis reist mee in de LLM-calls die er tóch al waren (geen extra LLM-calls).

Zichtbaarheid: `meld_raadpleging` publiceert bij elke raadpleging (ook bij 0/0/0) een
`kennis_geraadpleegd`-event op de bus — de Village-logger schrijft dat naar system_log.jsonl —
en logt één regel. De feed-regel op de projectkaart ("📚 raadpleegde de kennisbank: …")
zetten de aanroepers zelf via het bestaande ledger.add_feed_entry(kind="system")."""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("village.kennis")

# Harde cap op het hele grondingsblok. Ruimer dan de oude 1500: dat was een cap op één sectie
# (REEDS BEKEND), en met de grondwet, de Kroniek en de eerdere projecten erbij zou die de nieuwe
# secties er stilzwijgend weer afknippen. Elke sectie heeft daarnaast zijn eigen budget in
# `kennis_blok`, zodat één lange sectie de rest niet wegdrukt.
MAX_BLOK_CHARS = 4200

_SOORTEN = ("kaartjes", "inzichten", "signalen")
# Elk corpus zijn eigen embedding-index naast de store waar hij bij hoort.
INDEX_INZICHTEN = "kennisbank_embeddings.json"
INDEX_SIGNALEN = "radar_embeddings.json"          # gedeeld met radar_clusters — zelfde signalen

# Wat één semantische stap in het slechtste geval kost, gemeten. Onder deze resterende tijd beginnen
# we er niet meer aan.
#
# De semantische weg is de BETERE weg — hij vindt 'mycelium' bij 'paddenstoelvezel', en de lexicale
# weg doet dat nooit. Maar hij hangt aan een externe embedding-API plus een index op schijf, en die
# combinatie kostte op prod (28 aug 2026, gemeten): `_inzichten` 12,4s en `_signalen` 17,3s, terwijl
# de browser er al na 12s uitstapt. Vandaar een grens die niet optimistisch is maar gemeten: begin
# geen stap die je niet kunt betalen.
#
# Dat maakt dit GEEN verkapte aan/uit-schakelaar. De grens is een feit over de huidige kosten, en hij
# verandert van betekenis zodra die kosten veranderen: wordt de semantische stap weer een fractie van
# een seconde (zie de index-bevinding in de PR), dan laat hetzelfde budget hem gewoon weer door,
# zonder dat hier iets aan hoeft.
_SEMANTIEK_MINIMUM = 8.0


def _woorden(tekst: str) -> set[str]:
    from nooch_village.notes_store import _woorden as w   # één woord-splitser, geen kopie
    return w(tekst or "")


def _match(zoek: set[str], docs: list[tuple], limit: int) -> list:
    """Spiegel van NotesStore.relevant_for: gedeelde woorden gewogen op zeldzaamheid
    (1/doc_freq) — 'barefoot' (zeldzaam) telt zwaarder dan 'shoes' (overal). Geen vaste
    stopwoordenlijst; sterkste matches eerst, max `limit`. `docs` = [(object, tekst)]."""
    if not zoek or not docs:
        return []
    doc_freq: dict[str, int] = {}
    for _, tekst in docs:
        for w in _woorden(tekst):
            doc_freq[w] = doc_freq.get(w, 0) + 1
    gescoord = []
    for obj, tekst in docs:
        gedeeld = zoek & _woorden(tekst)
        score = sum(1.0 / doc_freq[w] for w in gedeeld)
        if score > 0:
            gescoord.append((score, obj))
    gescoord.sort(key=lambda t: -t[0])                    # stabiel: gelijke score → store-volgorde
    return [obj for _, obj in gescoord[:limit]]


def _rangschik(zoek_tekst: str, docs: list[tuple], limit: int, *, index: str = "",
               data_dir: str = "") -> tuple[list, str]:
    """De items die het dichtst bij `zoek_tekst` liggen, plus de gebruikte modus.

    Eerst op BETEKENIS (`kennis_embeddings.rank_semantisch`), want de lexicale weg mist precies wat
    je van een kennislaag wilt: een project over 'paddenstoelvezel' vindt zo geen enkel kaartje over
    'mycelium'. Lukt dat niet — geen sleutel, geen index, of niet elk item is geïndexeerd — dan valt
    hij terug op de bestaande woordoverlap. NOOIT slechter dan het oude gedrag, en de modus reist
    mee zodat het scherm/log niet suggereert dat er betekenis is vergeleken."""
    if index and data_dir:
        try:
            from nooch_village.kennis_embeddings import rank_semantisch
            paren = {id(o): (o, t) for o, t in docs}
            wrappers = [{"id": str(id(o)), "_t": t} for o, t in docs]
            hits = rank_semantisch(zoek_tekst, wrappers, os.path.join(data_dir, index),
                                   lambda w: w["_t"], limit=limit)
            if hits is not None:
                return [paren[int(h["id"])][0] for h in hits], "semantisch"
        except Exception as e:                            # noqa: BLE001 — nooit projectwerk blokkeren
            log.warning("semantische rangschikking faalde, terugval op lexicaal: %s", e)
    return _match(_woorden(zoek_tekst), docs, limit), "lexicaal"


def _regel(tekst: str, cap: int = 160) -> str:
    """Eén regel tekst: whitespace platgeslagen, hard afgekapt."""
    return " ".join(str(tekst or "").split())[:cap]


def _kaartjes(data_dir: str, tekst: str, limit: int) -> list[dict]:
    from nooch_village.notes_store import NotesStore
    pad = os.path.join(data_dir, "notes.json")
    if not os.path.exists(pad):
        return []
    hits = NotesStore(pad).relevant_for(tekst, limit=limit)
    return [{"id": n.id, "tekst": _regel(n.claim), "bron": _regel(n.source, 80)}
            for n in hits if not n.archived]              # gearchiveerd = buiten beeld (curatie)


def _inzichten(data_dir: str, tekst: str, limit: int, *, semantisch: bool = True) -> list[dict]:
    from nooch_village.kennisbank import KennisbankStore, field, load_atoms, verdict
    pad = os.path.join(data_dir, "kennisbank.json")
    if not os.path.exists(pad):
        return []
    alle = KennisbankStore(pad).all()
    docs = [(ins, f"{ins.get('title', '')} {ins.get('why', '')}") for ins in alle]
    hits, _modus = _rangschik(tekst, docs, limit,
                              index=INDEX_INZICHTEN if semantisch else "", data_dir=data_dir)
    if not hits:
        return []
    atoms = load_atoms(data_dir)                          # voor het live verdict-woord
    uit = []
    for ins in hits:
        try:
            woord = verdict(field(ins.get("evidence") or [], atoms)).get("word", "")
        except Exception:
            woord = ""                                    # verdict is garnering, nooit blokkerend
        # Falsifier en caveat gaan MEE. Zonder falsifier is een inzicht een mening met een id: de
        # lezer (mens of LLM) kan niet zien waaraan hij zou merken dat het niet meer klopt, en gaat
        # het dus als vaststaand behandelen. Het caveat is de rand van de geldigheid. Allebei
        # ruimer gecapt dan de titel — een afgekapte falsifier is erger dan geen falsifier, want
        # hij suggereert een toets die je niet kunt uitvoeren.
        uit.append({"id": ins.get("id", ""), "tekst": _regel(ins.get("title", "")),
                    "verdict": woord,
                    "falsifier": _regel(ins.get("falsifier", ""), 220),
                    "caveat": _regel(ins.get("caveat", ""), 180),
                    "reframe": _regel(ins.get("reframe", ""), 180)})
    return uit


def _signalen(data_dir: str, tekst: str, limit: int, *, semantisch: bool = True) -> list[dict]:
    from nooch_village.radar_store import RadarStore
    pad = os.path.join(data_dir, "radar.json")
    if not os.path.exists(pad):
        return []
    kandidaten = [it for it in RadarStore(pad).all_approved()
                  if not it.get("promoted_atom_id")]      # al gepromoveerd → zit al in de atomen
    docs = [(it, f"{it.get('content', '')} {it.get('rationale', '')}") for it in kandidaten]
    hits, _modus = _rangschik(tekst, docs, limit,
                              index=INDEX_SIGNALEN if semantisch else "", data_dir=data_dir)
    return [{"id": it.get("id", ""), "tekst": _regel(it.get("content", "")),
             "bron": _regel(it.get("source") or it.get("feed") or "", 80)} for it in hits]


# ── De Kroniek: wat is al bevestigd, wat is onderzocht-en-leeg, wat faalde ────────────────────

def _kroniek(data_dir: str, tekst: str, limit: int) -> dict:
    """De relevante Kroniek-stand voor dit onderwerp: bevestigd / leeg / fout.

    Waarom dit in elke productie- en oordeelsprompt hoort: zonder deze sectie onderzoekt een rol
    opnieuw wat al bevestigd is, en — erger — presenteert hij een kennisgat als een bevinding. De
    drie statussen zijn eersteklas: `leeg` betekent "onderzocht, niets gevonden" en dat is een
    resultaat, geen stilte.

    Gebruikt beide leeswegen van de Kroniek zoals ze bedoeld zijn: `interpret` rolt per onderwerp de
    laatste stand per (skill, query, bron) op, en `last_good` haalt bij een bevestigd onderwerp het
    meest recente BEVESTIGDE record op — die tweede was tot nu toe dode code, terwijl juist dat het
    record is waar een rol op mag leunen."""
    from nooch_village.evidence_ledger import EvidenceLedger, interpret
    pad = os.path.join(data_dir, "evidence_ledger.jsonl")
    if not os.path.exists(pad):
        return {"bevestigd": [], "leeg": [], "fout": []}
    led = EvidenceLedger(pad)
    uit = {"bevestigd": [], "leeg": [], "fout": []}
    gezien = set()
    for term in _onderwerpen(led, tekst, limit):
        rapport = interpret(led, term)
        for bak in ("bevestigd", "leeg", "fout"):
            for r in rapport.get(bak) or []:
                sleutel = (r.get("skill"), r.get("query"), r.get("source"))
                if sleutel in gezien:
                    continue
                gezien.add(sleutel)
                regel = {"skill": r.get("skill") or "?", "query": _regel(r.get("query"), 110),
                         "bron": _regel(r.get("source"), 60), "onderwerp": term}
                if bak == "bevestigd":
                    # last_good = het gezaghebbende laatste bevestigde record voor deze vraag.
                    beste = led.last_good(r.get("skill") or "", r.get("query") or "")
                    regel["bewijs"] = _regel((beste or r).get("result_ref") or r.get("bewijs"), 200)
                uit[bak].append(regel)
    # Bevestigde records MET bewijs eerst. De sectie heeft een budget, en op productie bleek dat
    # zelf-rapporterende skills (tegenspraak, escaleer) veel kale bevestigingen opleveren die het
    # echte bronbewijs anders wegdrukken. Een bevestiging zonder result_ref zegt "iemand heeft
    # hiernaar gekeken"; eentje mét zegt wát er gevonden is.
    uit["bevestigd"].sort(key=lambda r: not r.get("bewijs"))
    for bak in uit:
        uit[bak] = uit[bak][:limit]
    return uit


def _onderwerpen(led, tekst: str, limit: int) -> list[str]:
    """De onderwerpen waarop we de Kroniek bevragen: de woorden uit de tekst die ook echt in
    Kroniek-vragen voorkomen, zeldzaamste eerst.

    `interpret` matcht op substring in de query, dus je moet 'm een term voeren die daar bestaat —
    de hele projectscope erin gooien levert per definitie niets op. Zeldzaam eerst, want 'shoes'
    matcht half de Kroniek en zegt daarmee niets."""
    woorden = {w for w in _woorden(tekst) if len(w) >= 4}
    if not woorden:
        return []
    freq: dict[str, int] = {}
    try:
        for r in led.all_records():
            for w in _woorden(str(r.get("query") or "")) & woorden:
                freq[w] = freq.get(w, 0) + 1
    except Exception:                                     # noqa: BLE001 — nooit projectwerk blokkeren
        return []
    return [w for w, _ in sorted(freq.items(), key=lambda kv: kv[1])][:max(1, limit // 2)]


# ── Eerdere projecten over hetzelfde ─────────────────────────────────────────────────────────

def _projecten(data_dir: str, tekst: str, limit: int, *, exclude: str = "") -> list[dict]:
    """Verwante eerdere projecten, met hun antwoord (`dod_outcome`) als dat er is.

    Zonder deze sectie begint een rol met een schone lei aan iets waar het dorp al aan gewerkt
    heeft — en dat is precies het soort dubbel werk dat de kennislaag hoort te voorkomen."""
    from nooch_village.projects import ProjectLedger
    pad = os.path.join(data_dir, "projects.json")
    if not os.path.exists(pad):
        return []
    alle = [p for p in ProjectLedger(pad).all()
            if p.get("id") != exclude and not p.get("archived") and not p.get("private")]
    docs = [(p, f"{_scope(p)} {p.get('description', '')} {p.get('dod_outcome', '')}") for p in alle]
    hits, _modus = _rangschik(tekst, docs, limit)          # lexicaal: projecten hebben geen index
    return [{"id": p.get("id", ""), "tekst": _regel(_scope(p)), "status": p.get("status", ""),
             "eigenaar": _regel(p.get("owner", ""), 60),
             "antwoord": _regel(p.get("dod_outcome", ""), 180)} for p in hits]


def _scope(p: dict) -> str:
    sc = p.get("scope")
    if isinstance(sc, dict):
        return " · ".join(f"{k}: {v}" for k, v in sc.items())
    return str(sc or "")


# ── De pre-flight: weten we dit al? ──────────────────────────────────────────────────────────

def _preflight(data_dir: str, tekst: str) -> dict:
    """Draai `weten_we_dit_al` AUTOMATISCH bij elke raadpleging.

    Die skill was opt-in: een rol moest 'm in zijn DNA hebben én zelf kiezen om 'm te draaien, en
    dus gebeurde het zelden — terwijl de vraag "hebben we dit al" bij élk stuk werk vooraf hoort.
    Hier draait hij als pre-flight, deterministisch en zonder LLM, en zijn verdict (`bekend`) wordt
    de kop van het grondingsblok. Fail-soft: een fout → geen verdict, nooit een blokkade."""
    try:
        import types

        from nooch_village.skills_impl.weten_we_dit_al import WetenWeDitAlSkill
        uit = WetenWeDitAlSkill().run({"vraag": tekst}, types.SimpleNamespace(data_dir=data_dir))
    except Exception as e:                                # noqa: BLE001
        log.warning("pre-flight weten_we_dit_al faalde fail-soft: %s", e)
        return {}
    if not isinstance(uit, dict) or not uit.get("ok"):
        return {}
    return {"bekend": bool(uit.get("bekend")), "treffers": int(uit.get("treffers") or 0),
            "samenvatting": _regel(uit.get("samenvatting"), 240)}


def kennis_voor(bron, tekst: str, limit: int = 5, *, exclude_pid: str = "",
                deadline: float | None = None) -> dict:
    """Raadpleeg de kennislaag én de Kroniek voor een project-scope/hypothese.

    `bron` = een data_dir-pad (str) óf een Context-achtig object met `.data_dir`. Geeft
    {kaartjes, inzichten, signalen, kroniek, projecten, preflight, samenvatting}. Fail-soft per
    bron: een ontbrekende of kapotte store levert een lege deelverzameling en blokkeert nooit het
    projectwerk — het blok wordt dan gewoon korter, nooit foutief.

    `deadline`: budget in SECONDEN voor deze raadpleging. None (de default, en wat de daemon
    gebruikt) = geen budget: neem de tijd, de beste kennis wint. Een getal betekent dat er iemand
    wácht — de mens voor een scherm — en dan knijpt het budget precies één ding af: de semantische
    stap van `_inzichten` en `_signalen`. Die twee hangen aan een externe embedding-API en zijn de
    enige bronnen hier die seconden kunnen kosten; de rest is een woordvergelijking van 0,0s.
    Verloopt het budget, dan antwoorden ze lexicaal. NOOIT overgeslagen: een kortere match is een
    antwoord, een weggelaten bron is een gat waar niemand van weet.

    Het budget is een BOVENGRENS OP DE POGING, geen garantie op de duur: een semantische stap die
    net binnen de grens begint mag zelf nog uitlopen. Wil je een harde wandkloktijd, zet die dan
    bij de aanroeper (de browser doet dat met `AI_TIMEOUT_MS`)."""
    data_dir = bron if isinstance(bron, str) else getattr(bron, "data_dir", None)
    uit: dict = {s: [] for s in _SOORTEN}
    uit["kroniek"] = {"bevestigd": [], "leeg": [], "fout": []}
    uit["projecten"] = []
    uit["preflight"] = {}
    eind = (time.monotonic() + float(deadline)) if deadline else None
    def _mag_semantisch() -> bool:
        return eind is None or (eind - time.monotonic()) > _SEMANTIEK_MINIMUM

    if data_dir and (tekst or "").strip():
        # De derde kolom zegt of deze bron een embedding-index gebruikt. Kaartjes doen dat niet
        # (NotesStore matcht van nature lexicaal), dus daar valt ook niets af te knijpen.
        for soort, fn, indexeert in (("kaartjes", _kaartjes, False),
                                     ("inzichten", _inzichten, True),
                                     ("signalen", _signalen, True)):
            try:
                kw = {"semantisch": _mag_semantisch()} if indexeert else {}
                uit[soort] = fn(data_dir, tekst, limit, **kw)
            except Exception as e:                        # nooit projectwerk blokkeren
                log.warning("kennis-raadpleging (%s) faalde fail-soft: %s", soort, e)
                uit[soort] = []
        try:
            uit["kroniek"] = _kroniek(data_dir, tekst, limit)
        except Exception as e:                            # noqa: BLE001
            log.warning("kennis-raadpleging (kroniek) faalde fail-soft: %s", e)
        try:
            uit["projecten"] = _projecten(data_dir, tekst, limit, exclude=exclude_pid)
        except Exception as e:                            # noqa: BLE001
            log.warning("kennis-raadpleging (projecten) faalde fail-soft: %s", e)
        uit["preflight"] = _preflight(data_dir, tekst)
    kron = uit["kroniek"]
    uit["samenvatting"] = (f"{len(uit['kaartjes'])} kaartjes, {len(uit['inzichten'])} "
                           f"inzichten, {len(uit['signalen'])} signalen, "
                           f"{len(kron['bevestigd'])} bevestigd + {len(kron['leeg'])} leeg + "
                           f"{len(kron['fout'])} fout in de Kroniek, "
                           f"{len(uit['projecten'])} eerdere projecten")
    return uit


def totaal(kennis: dict | None) -> int:
    """Aantal gevonden items over ALLE bronnen (fail-soft: geen dict → 0).

    De Kroniek en de eerdere projecten tellen mee: zonder dat zou een raadpleging die alleen
    bevestigd bewijs vond als '0 gevonden' lezen en het blok helemaal wegvallen — precies de
    grounding die je wilde hebben."""
    if not isinstance(kennis, dict):
        return 0
    n = sum(len(kennis.get(s) or []) for s in _SOORTEN)
    n += len(kennis.get("projecten") or [])
    kron = kennis.get("kroniek") or {}
    n += sum(len(kron.get(b) or []) for b in ("bevestigd", "leeg", "fout"))
    return n


def kennis_blok(kennis: dict | None, max_chars: int = MAX_BLOK_CHARS) -> str:
    """Render de grondingssectie voor een productie- of oordeelsprompt.

    Volgorde is niet willekeurig — hij loopt van "waar dit werk aan moet voldoen" naar "wat we al
    weten" naar "wat we al geprobeerd hebben":

      1. GRONDWET      — de missie zelf. Altijd, ook als er verder niets gevonden is: een tekst die
                         zonder de missie geschreven wordt, moet je achteraf tegen de missie leggen,
                         en dat gebeurt zelden.
      2. WETEN WE DIT AL — het pre-flight-verdict, als kop.
      3. DE KRONIEK    — bevestigd / onderzocht-en-leeg / bron faalde. Bevestigd bewijs voorkomt
                         dubbel onderzoek; een leeg record voorkomt dat een kennisgat als bevinding
                         wordt gepresenteerd.
      4. REEDS BEKEND  — inzichten MET hun falsifier en caveat, dan kaartjes en signalen.
      5. EERDERE PROJECTEN.

    Elke sectie heeft een eigen budget, zodat één lange sectie de andere niet wegdrukt — met één
    gedeelde cap zou de Kroniek de inzichten kunnen opeten of andersom, afhankelijk van de data.
    Niets gevonden en geen grondwet → "" (dan géén injectie)."""
    from nooch_village.mission import ANCHOR_PURPOSE
    if not isinstance(kennis, dict):
        return ""
    secties: list[tuple[str, list[str], int]] = []

    pf = kennis.get("preflight") or {}
    if pf:
        antwoord = "JA" if pf.get("bekend") else "NEE"
        secties.append((f"WETEN WE DIT AL? {antwoord} — {pf.get('treffers', 0)} directe treffer(s).",
                        [], 300))

    kron = kennis.get("kroniek") or {}
    kron_regels: list[str] = []
    for r in kron.get("bevestigd") or []:
        bewijs = f" — {r['bewijs']}" if r.get("bewijs") else ""
        kron_regels.append(f"- [BEVESTIGD] {r.get('skill')} \"{r.get('query')}\" "
                           f"via {r.get('bron') or 'onbekende bron'}{bewijs}")
    for r in kron.get("leeg") or []:
        kron_regels.append(f"- [LEEG] {r.get('skill')} \"{r.get('query')}\" — onderzocht, niets "
                           f"gevonden. Dit is een kennisgat, geen bevinding.")
    for r in kron.get("fout") or []:
        kron_regels.append(f"- [FOUT] {r.get('skill')} \"{r.get('query')}\" via "
                           f"{r.get('bron') or '?'} — de bron faalde; hierover weten we niets.")
    if kron_regels:
        secties.append(("DE KRONIEK (bevestigd bewijs — onderzoek dit niet opnieuw; leeg = "
                        "kennisgat, presenteer het niet als bevinding):", kron_regels, 1400))

    weten_regels: list[str] = []
    for i in kennis.get("inzichten") or []:
        staart = f" (bewijs: {i['verdict']})" if i.get("verdict") else ""
        weten_regels.append(f"- [inzicht {i.get('id', '')}] {i.get('tekst', '')}{staart}")
        # De falsifier is geen decoratie: hij zegt waaraan je zou merken dat dit inzicht NIET meer
        # klopt. Zonder die regel leest een inzicht als een vaststaand feit.
        if i.get("falsifier"):
            weten_regels.append(f"    WEERLEGD ALS: {i['falsifier']}")
        if i.get("caveat"):
            weten_regels.append(f"    LET OP: {i['caveat']}")
    for k in kennis.get("kaartjes") or []:
        staart = f" (bron: {k['bron']})" if k.get("bron") else ""
        weten_regels.append(f"- [kaartje {k.get('id', '')}] {k.get('tekst', '')}{staart}")
    for sg in kennis.get("signalen") or []:
        staart = f" (bron: {sg['bron']})" if sg.get("bron") else ""
        weten_regels.append(f"- [signaal {sg.get('id', '')}] {sg.get('tekst', '')}{staart}")
    if weten_regels:
        secties.append(("REEDS BEKEND (kennisbank — vul aan, herhaal niet):", weten_regels, 1600))

    proj_regels = [f"- [{p.get('status', '')}] {p.get('tekst', '')} (bij {p.get('eigenaar', '')})"
                   + (f" → {p['antwoord']}" if p.get("antwoord") else "")
                   for p in kennis.get("projecten") or []]
    if proj_regels:
        secties.append(("EERDERE PROJECTEN HIEROVER (bouw erop voort, begin niet opnieuw):",
                        proj_regels, 800))

    blokken = [f"GRONDWET (waaraan dit werk moet voldoen):\n{ANCHOR_PURPOSE}"]
    for kop, regels, budget in secties:
        stuk = kop
        for r in regels:
            kandidaat = stuk + "\n" + r
            if len(kandidaat) > budget:
                break
            stuk = kandidaat
        blokken.append(stuk)
    blok = "\n\n".join(blokken)
    return blok if len(blok) <= max_chars else blok[:max_chars]


def meld_raadpleging(bus, *, project_id: str, rol: str, kennis: dict | None,
                     sender: str = "") -> None:
    """Maak de raadpleging zichtbaar: één logregel + (als er een bus is) het event
    `kennis_geraadpleegd` met {project_id, rol, gevonden: {kaartjes, inzichten, signalen},
    ids}. Ook 0/0/0 is een event — 'niets gevonden' is óók activiteit. Fail-soft: een
    kapotte bus mag het projectwerk nooit breken."""
    kennis = kennis if isinstance(kennis, dict) else {}
    gevonden = {s: len(kennis.get(s) or []) for s in _SOORTEN}
    ids = [item.get("id", "") for s in _SOORTEN for item in (kennis.get(s) or [])]
    log.info("📚 %s raadpleegde de kennisbank voor project %s: %s", rol or "?", project_id,
             kennis.get("samenvatting") or "0 kaartjes, 0 inzichten, 0 signalen")
    if bus is None:
        return
    try:
        from nooch_village.event_bus import Event
        bus.publish(Event("kennis_geraadpleegd",
                          {"project_id": project_id, "rol": rol, "gevonden": gevonden,
                           "ids": ids}, sender or rol or "kennis_context"))
    except Exception as e:
        log.warning("kennis_geraadpleegd-event kon niet worden gepubliceerd: %s", e)
