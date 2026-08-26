"""Waarde-audit — wat bracht elke rol en elke skill voort dat een mens echt raakte?

De vraag is niet "draaide het?" maar "kwam er iets uit dat buiten het dorp iets veranderde?".
Een register dat zich vult, een spanning die zichzelf oplost en een pagina vol tekst zonder bron
zijn alle drie beweging; geen ervan is een uitkomst. Dit bestand telt ze uit elkaar.

**Fail-closed, net als de raad.** Geen record van een uitkomst betekent interne beweging — punt.
Er wordt geen potentie gekrediteerd, geen "dit zou waardevol kunnen worden", en er wordt niets
geraden: een twijfelgeval wordt gevlagd voor de mens, niet ingevuld. Geen LLM: de signalen staan
in de data, en een model dat hier een oordeel velt zou precies de zachtheid terugbrengen die deze
audit moet wegnemen.

## Wat als bewezen uitkomst telt

Vier signalen, elk een VERGELIJKING op bestaande records, elk met een id dat je kunt natrekken:

| signaal | bron | waarom dit telt |
|---|---|---|
| `project_afgerond` | `projects.json`, veld `outcome` | de mens kent Done pas toe ná review — er is dus een mens die dit heeft bekeken en afgetekend |
| `pagina_bewerkt` | `attachments.json`, een versie met `actor_type="human"` | iemand heeft de pagina gebruikt en aangeraakt; dat is het verschil tussen kennis en tekst |
| `besluit_genomen` | `notifications.json`, een verwerking met een echte uitkomst | een ja, een nee, een suggestie of een project — geen "niks nodig" |
| `certificaat_gebankt` | bestanden in `data/certificaten/` | een certificaat dat een claim kan dragen |

**Wat NIET telt, en waarom.** `ping` (doorgestuurd naar een andere rol) en `none` ("niks nodig")
zijn routering en afsluiting, geen uitkomst. `dod_outcome` is de definitie van klaar, niet het
bewijs dat het klaar is. Een Kroniek-record met status `bevestigd` is bewijs dát een bron antwoordde,
niet dat er iets mee gebeurde.

**Eerlijk over wat dit meet.** Zelfs `project_afgerond` bewijst dat een MENS iets aftekende, niet dat
er een schoen is verkocht of een leverancier iets deed. De uitkomsttekst is bovendien procedureel
("goedgekeurd na review") — `project_signal._PROCEDUREEL` waarschuwt daar zelf voor. Dit is het
sterkste signaal dat de data draagt; het is geen omzet.

## Kosten

Uit `llm_usage.jsonl`, geprijsd met `llm_keuze.kosten_eur` (één gezaghebbende prijstabel). Een trede
zonder prijs telt NIET als nul maar als onbekend — een schatting van nul liegt harder. Call-sites
`skill_<naam>` gaan naar die skill; de rest is dorpsinfrastructuur en wordt apart getoond, want die
kosten aan een rol toeschrijven zou een verzinsel zijn.
"""
from __future__ import annotations

import collections
import json
import os
import time

# ── Wat telt als een echte uitkomst ─────────────────────────────────────────
# Uit de verwerk-record-typen (`inbox_wizard`). 'none' is "niks nodig" en 'ping' is doorsturen naar
# een andere rol: allebei sluiten ze een item, geen van beide verandert iets buiten het dorp.
ECHTE_UITKOMSTEN = frozenset({"project", "action", "note", "roloverleg",
                              "besluit_ja", "besluit_nee", "besluit_suggestie"})
INTERNE_UITKOMSTEN = frozenset({"none", "ping"})

# Hoe recent is "nog actief"? 30 dagen: één maandcyclus van het dorp.
RECENT_DAGEN = 30
# Boven deze grens weegt "kosten zonder uitkomst" zwaar genoeg om te noemen.
DURE_POST_EUR = 0.50

WAKKER, SLAPEN, OPRUIMEN, VLAG = "wakker houden", "slapen", "opruimen", "vlag voor Stefan"
STRUCTUREEL = "structureel — niet op output te beoordelen"

# De grondwettelijke rollen. Een Circle Lead, Secretary, Facilitator of Rep bestaat om governance te
# dragen, niet om deliverables te maken; hem op output afrekenen is een categoriefout, en het advies
# "opruimen" zou betekenen dat je de Secretary opheft. Herkend aan het ACHTERVOEGSEL van de rol-id,
# want dat is hoe governance ze aanmaakt — niet aan de naam, die kan iemand wijzigen.
STRUCTURELE_ACHTERVOEGSELS = ("__circle_lead", "__circle_rep", "__secretary", "__facilitator")


def is_structureel(rol_id: str) -> bool:
    from nooch_village.founder_kaart import FOUNDER_ROL
    return (rol_id == FOUNDER_ROL
            or any(str(rol_id).endswith(a) for a in STRUCTURELE_ACHTERVOEGSELS))


def _lees_jsonl(pad: str) -> list[dict]:
    uit = []
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if regel:
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue                      # corrupte regel overslaan, rest blijft leesbaar
    except OSError:
        return []
    return uit


def _lees_json(pad: str, leeg):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return leeg


# ── De bronnen, één keer ingelezen ──────────────────────────────────────────

class Bronnen:
    """Alles wat de audit leest. Read-only; er wordt niets teruggeschreven."""

    def __init__(self, data_dir: str, records=None):
        d = self.data_dir = data_dir
        self.records = records
        self.kroniek = _lees_jsonl(os.path.join(d, "evidence_ledger.jsonl"))
        self.usage = _lees_jsonl(os.path.join(d, "llm_usage.jsonl"))
        self.verwerkingen = _lees_jsonl(os.path.join(d, "verwerkingen.jsonl"))
        self.raad = _lees_jsonl(os.path.join(d, "villageraad.jsonl"))
        self.gaps = _lees_jsonl(os.path.join(d, "gaps.jsonl"))
        self.projects = _lees_json(os.path.join(d, "projects.json"), {})
        self.attachments = _lees_json(os.path.join(d, "attachments.json"), {})
        self.deliverables = _lees_json(os.path.join(d, "deliverables.json"), {})
        self.notifs = _lees_json(os.path.join(d, "notifications.json"), [])
        cert_dir = os.path.join(d, "certificaten")
        self.certificaten = sorted(os.listdir(cert_dir)) if os.path.isdir(cert_dir) else []
        out_dir = os.path.join(d, "output")
        self.output = sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []


# ── De uitkomsten, per eigenaar ─────────────────────────────────────────────

def uitkomsten_per_rol(b: Bronnen) -> dict:
    """{rol_id: [{"soort", "ref", "wat", "ts"}]} — alleen bewezen uitkomsten."""
    uit: dict = collections.defaultdict(list)

    for pid, p in (b.projects or {}).items():
        if not str(p.get("outcome") or "").strip():
            continue                                  # dod_outcome is de definitie, niet het bewijs
        uit[str(p.get("owner") or "")].append({
            "soort": "project_afgerond", "ref": pid, "ts": p.get("updated_at") or p.get("created_at"),
            "wat": " ".join(str(p.get("scope") or pid).split())[:90]})

    for aid, a in (b.attachments or {}).items():
        mensen = [v for v in (a.get("versions") or []) if v.get("actor_type") == "human"]
        if not mensen:
            continue
        uit[str(a.get("anchor") or "")].append({
            "soort": "pagina_bewerkt", "ref": aid, "ts": max(v.get("ts") or 0 for v in mensen),
            "wat": f"{a.get('title') or aid} — {len(mensen)}x door een mens bewerkt"})

    for n in (b.notifs or []):
        echt = [v for v in (n.get("verwerkingen") or [])
                if (v.get("otype") or v.get("intent")) in ECHTE_UITKOMSTEN]
        if not echt:
            continue
        # De opwerpende rol krijgt het krediet: die bracht het onder de aandacht van een mens.
        uit[str(n.get("by") or "")].append({
            "soort": "besluit_genomen", "ref": str(n.get("id") or ""), "ts": n.get("at"),
            "wat": ", ".join(str(v.get("otype") or v.get("intent")) for v in echt)})

    return dict(uit)


def _cert_eigenaar(records) -> str:
    """Wie bezit het certificaten-register? Governance bepaalt dat, niet deze code."""
    for rec in (records.all() if records is not None else []):
        for dom in (getattr(getattr(rec, "definition", None), "domains", None) or []):
            if "claim" in str(dom).lower() or "compliance" in str(dom).lower():
                return rec.id
    return ""


# ── Kosten ──────────────────────────────────────────────────────────────────

def kosten_per_call_site(b: Bronnen) -> dict:
    """{call_site: {"eur", "calls", "tokens", "onbekend"}}.

    `onbekend` telt de calls op een trede zonder prijs. Die verdwijnen NIET in het totaal: een
    onbekende prijs als nul tellen maakt het overzicht onwaar op precies de plek waar het duur kan
    worden (zelfde regel als `llm_keuze.prijsloze_tredes`)."""
    from nooch_village.llm_keuze import _prijzen, kosten_eur

    prijzen = _prijzen()
    uit: dict = collections.defaultdict(lambda: {"eur": 0.0, "calls": 0, "tokens": 0, "onbekend": 0})
    for r in b.usage:
        cs = str(r.get("call_site") or "onbekend")
        rij = uit[cs]
        rij["calls"] += 1
        rij["tokens"] += int(r.get("tokens") or 0)
        in_t = int(r.get("in_tokens") or 0)
        out_t = int(r.get("out_tokens") or 0)
        eur = kosten_eur(str(r.get("tier") or ""), in_t, out_t, prijzen)
        if eur is None:
            rij["onbekend"] += 1
        else:
            rij["eur"] += eur
    return dict(uit)


def skill_van_call_site(cs: str) -> str:
    """`skill_claim_evidence` → `claim_evidence`. Alles zonder dat voorvoegsel is dorpsinfrastructuur
    en wordt NIET aan een skill toegeschreven — dat zou een verzinsel zijn."""
    return cs[len("skill_"):] if cs.startswith("skill_") else ""


def gebruik_per_skill(b: Bronnen) -> dict:
    """{skill: {rol: aantal keer gedraaid}} — uit de Kroniek en de deliverables.

    Nodig omdat het usage-log alleen de call-site kent, niet wie hem aanriep. Zonder deze verdeling
    krijgt ELKE rol die een skill houdt de VOLLE prijs van die skill, en `tegenspraak` staat op acht
    rollen: dan lees je vier keer dezelfde €3,55 en lijkt het dorp vier keer zo duur als het is.
    De Kroniek en de deliverables weten wél wie draaide, dus dat is de verdeelsleutel."""
    uit: dict = collections.defaultdict(collections.Counter)
    for r in b.kroniek:
        sk, rol = str(r.get("skill") or ""), str(r.get("role_id") or "")
        if sk and rol:
            uit[sk][rol] += 1
    for v in (b.deliverables or {}).values():
        sk, rol = str(v.get("skill") or ""), str(v.get("role") or "")
        if sk and rol:
            uit[sk][rol] += 1
    return {k: dict(v) for k, v in uit.items()}


def code_datums(base_dir: str) -> dict:
    """{skill: laatste commit-datum van zijn implementatiebestand} — uit de git-historie.

    Alleen voor het ADVIES 'opruimen': een skill die nooit iets voortbracht is iets anders als de
    code vorige week is geschreven (dan is hij nog niet bedraad) dan wanneer hij een jaar niet is
    aangeraakt (dan is hij vergeten). Fail-soft: geen git, geen datum — dan staat er 'onbekend',
    nooit een gok."""
    import subprocess

    impl = os.path.join(base_dir, "nooch_village", "skills_impl")
    if not os.path.isdir(impl):
        return {}
    uit = {}
    for naam in os.listdir(impl):
        if not naam.endswith(".py") or naam == "__init__.py":
            continue
        pad = os.path.join("nooch_village", "skills_impl", naam)
        try:
            r = subprocess.run(["git", "log", "-1", "--format=%at", "--", pad],
                               cwd=base_dir, capture_output=True, text=True, timeout=10)
            ts = (r.stdout or "").strip()
            if ts.isdigit():
                uit[naam[:-3]] = float(ts)
        except Exception:                                 # noqa: BLE001 — geen git = geen datum
            continue
    return uit


def rol_aandeel(skill: str, rol: str, gebruik: dict) -> float:
    """Welk deel van de kosten van deze skill hoort bij deze rol? 0.0 als er geen enkel gebruik is
    vastgelegd — dan is er geen grond om die kosten aan iemand toe te schrijven (fail-closed), en
    komen ze in de niet-toegewezen post terecht."""
    per_rol = gebruik.get(skill) or {}
    totaal = sum(per_rol.values())
    return (per_rol.get(rol, 0) / totaal) if totaal else 0.0


# ── De regels ───────────────────────────────────────────────────────────────

def _recent(ts, nu: float) -> bool:
    return bool(ts) and (nu - float(ts)) <= RECENT_DAGEN * 86400


def advies(*, uitkomsten: list, laatst: float, eur: float, onbekende_calls: int,
           ooit_actief: bool, nu: float, structureel: bool = False) -> tuple[str, str]:
    """(advies, waarom). Deterministisch en in deze volgorde — de eerste die past wint.

    De volgorde is het beleid: nooit-actief is opruimen, bewezen-recent is wakker houden, en alles
    daartussen zakt naar slapen. Een onbekende prijs blokkeert alleen het KOSTEN-argument, niet het
    uitkomst-argument: dan weet je niet wat het kost, en dat is een vraag voor de mens."""
    if structureel:
        # Vóór alle andere regels: deze rol hoort niet op output beoordeeld te worden, ook niet als
        # hij toevallig wél iets voortbracht.
        return STRUCTUREEL, ("grondwettelijke rol (governance dragen, geen output produceren) — "
                             + (f"draagt wel {len(uitkomsten)} bewezen uitkomst(en)" if uitkomsten
                                else "beoordeel hem op zijn governance-werk, niet hier"))
    if not ooit_actief:
        return OPRUIMEN, "nooit iets voortgebracht: geen Kroniek-record, geen deliverable, geen project, geen pagina"
    if uitkomsten and _recent(laatst, nu):
        return WAKKER, (f"{len(uitkomsten)} bewezen uitkomst(en), laatst actief binnen "
                        f"{RECENT_DAGEN} dagen")
    if uitkomsten:
        return VLAG, (f"{len(uitkomsten)} bewezen uitkomst(en) maar al langer dan {RECENT_DAGEN} "
                      f"dagen stil — is dit af of vergeten?")
    if onbekende_calls and eur <= 0:
        return VLAG, (f"geen bewezen uitkomst en de kosten zijn niet te bepalen "
                      f"({onbekende_calls} call(s) op een trede zonder prijs)")
    if eur >= DURE_POST_EUR:
        return SLAPEN, f"geen bewezen uitkomst, wel €{eur:.2f} aan model-verbruik"
    return SLAPEN, "geen bewezen uitkomst"


# ── De inventarisatie ───────────────────────────────────────────────────────

def _skills_van_rol(rec) -> list[str]:
    return [str(s) for s in (getattr(getattr(rec, "definition", None), "skills", None) or [])]


def rollen_regels(b: Bronnen, kosten: dict, nu: float) -> list[dict]:
    from nooch_village import org

    from nooch_village.villageraad import labels, rollen as levende_rollen

    gebruik = gebruik_per_skill(b)
    uit_per_rol = uitkomsten_per_rol(b)
    # Drie rollen die allemaal "Circle Lead" heten zijn in een tabel niet uit elkaar te houden.
    # Dezelfde helper als de villageraad gebruikt — één plek waar dat wordt opgelost.
    namen = labels(levende_rollen(b.records), b.records) if b.records is not None else {}
    cert_rol = _cert_eigenaar(b.records)
    if b.certificaten and cert_rol:
        uit_per_rol.setdefault(cert_rol, []).append(
            {"soort": "certificaat_gebankt", "ref": b.certificaten[0], "ts": nu,
             "wat": f"{len(b.certificaten)} certificaat/certificaten in het register"})

    kron = collections.defaultdict(list)
    for r in b.kroniek:
        kron[str(r.get("role_id") or "")].append(r)
    deliv = collections.defaultdict(list)
    for did, v in (b.deliverables or {}).items():
        deliv[str(v.get("role") or "")].append({**v, "id": did})
    projecten = collections.defaultdict(list)
    for pid, p in (b.projects or {}).items():
        projecten[str(p.get("owner") or "")].append({**p, "id": pid})
    paginas = collections.defaultdict(list)
    for aid, a in (b.attachments or {}).items():
        if a.get("kind") == "note":
            paginas[str(a.get("anchor") or "")].append({**a, "id": aid})
    opgeworpen = collections.Counter(str(n.get("by") or "") for n in (b.notifs or []))

    rijen = []
    for rec in (b.records.all() if b.records is not None else []):
        if getattr(rec, "archived", False):
            continue
        try:
            if org.is_circle(rec):
                continue                              # een cirkel heeft geen handen (harde regel 7)
        except Exception:                             # noqa: BLE001
            pass
        rid = rec.id
        k = kron.get(rid, [])
        d = deliv.get(rid, [])
        p = projecten.get(rid, [])
        pg = paginas.get(rid, [])
        u = uit_per_rol.get(rid, [])
        skills = _skills_van_rol(rec)

        # Naar RATO van het vastgelegde GEBRUIK, niet vol per rol — zie `gebruik_per_skill`.
        # En op gebruik, niet op toewijzing: een rol die een skill draaide zonder hem in zijn DNA te
        # hebben, heeft die calls echt verstookt. Wat er gebeurde weegt zwaarder dan wat er op
        # papier stond.
        gedraaid = [sk for sk, per_rol in gebruik.items() if per_rol.get(rid)]
        eur = onb = calls = 0.0
        for s in sorted(set(skills) | set(gedraaid)):
            c = kosten.get(f"skill_{s}", {})
            deel = rol_aandeel(s, rid, gebruik)
            eur += c.get("eur", 0.0) * deel
            onb += c.get("onbekend", 0) * deel
            calls += c.get("calls", 0) * deel
        onb, calls = int(round(onb)), int(round(calls))

        tijden = ([r.get("ts") or 0 for r in k]
                  + [v.get("created_at") or 0 for v in d]
                  + [x.get("updated_at") or x.get("created_at") or 0 for x in p]
                  + [a.get("updated_at") or 0 for a in pg]
                  + [x.get("ts") or 0 for x in u])
        laatst = max(tijden) if tijden else 0.0
        ooit = bool(k or d or p or pg)
        adv, waarom = advies(uitkomsten=u, laatst=laatst, eur=eur, onbekende_calls=onb,
                             ooit_actief=ooit, nu=nu, structureel=is_structureel(rid))
        rijen.append({
            "id": rid,
            "naam": namen.get(rid) or rid,
            "skills": skills,
            "kroniek": collections.Counter(str(r.get("status")) for r in k),
            "kroniek_n": len(k),
            "kroniek_ids": [str(r.get("id")) for r in k[:3]],
            "deliverables": len(d),
            "deliverable_ids": [v["id"] for v in d[:3]],
            "projecten": len(p),
            "paginas": len(pg),
            "paginas_met_feiten": sum(1 for a in pg if (a.get("meta") or {}).get("feiten")),
            "opgeworpen": opgeworpen.get(rid, 0),
            "uitkomsten": u,
            "eur": eur, "calls": calls, "onbekend": onb,
            "laatst": laatst, "advies": adv, "waarom": waarom,
        })
    return sorted(rijen, key=lambda r: (-len(r["uitkomsten"]), -r["eur"], r["naam"].lower()))


def skill_regels(b: Bronnen, kosten: dict, nu: float, code: dict | None = None) -> list[dict]:
    """Elke skill die ergens sporen naliet: toegewezen in governance, gedraaid in de Kroniek, of
    een deliverable geschreven. Een skill die nergens voorkomt bestaat alleen als bestand."""
    toegewezen = collections.defaultdict(list)
    for rec in (b.records.all() if b.records is not None else []):
        if getattr(rec, "archived", False):
            continue
        for s in _skills_van_rol(rec):
            toegewezen[s].append(rec.id)

    kron = collections.defaultdict(list)
    for r in b.kroniek:
        kron[str(r.get("skill") or "")].append(r)
    deliv = collections.defaultdict(list)
    for did, v in (b.deliverables or {}).items():
        deliv[str(v.get("skill") or "")].append({**v, "id": did})

    # Een deliverable telt pas als uitkomst als het PROJECT waar hij aan hangt door een mens is
    # afgetekend. Anders is hij een bestand dat niemand aanraakte.
    def _mens_afgetekend(pid: str) -> bool:
        p = (b.projects or {}).get(pid or "")
        return bool(p and str(p.get("outcome") or "").strip())

    namen = set(toegewezen) | set(kron) | set(deliv) | {
        skill_van_call_site(cs) for cs in kosten if skill_van_call_site(cs)}
    namen.discard("")

    rijen = []
    for s in sorted(namen):
        k = kron.get(s, [])
        d = deliv.get(s, [])
        kd = [v for v in d if _mens_afgetekend(str(v.get("project_id") or ""))]
        c = kosten.get(f"skill_{s}", {})
        tijden = [r.get("ts") or 0 for r in k] + [v.get("created_at") or 0 for v in d]
        laatst = max(tijden) if tijden else 0.0
        # ALLE treffers, niet de eerste vijf: de weergave kapt af, de telling nooit — anders leest
        # een skill met 21 uitkomsten als een skill met 5.
        u = [{"soort": "deliverable_in_afgetekend_project", "ref": v["id"],
              "ts": v.get("created_at"), "wat": str(v.get("title") or "")[:80]} for v in kd]
        adv, waarom = advies(uitkomsten=u, laatst=laatst, eur=c.get("eur", 0.0),
                             onbekende_calls=c.get("onbekend", 0),
                             ooit_actief=bool(k or d or c.get("calls")), nu=nu)
        rijen.append({
            "naam": s,
            "rollen": toegewezen.get(s, []),
            "kroniek": collections.Counter(str(r.get("status")) for r in k),
            "kroniek_n": len(k),
            "kroniek_ids": [str(r.get("id")) for r in k[:3]],
            "deliverables": len(d),
            "deliverables_afgetekend": len(kd),
            "uitkomsten": u,
            "eur": c.get("eur", 0.0), "calls": c.get("calls", 0),
            "onbekend": c.get("onbekend", 0),
            "laatst": laatst, "advies": adv, "waarom": waarom,
            "code_laatst": (code or {}).get(s),
        })
    return sorted(rijen, key=lambda r: (-len(r["uitkomsten"]), -r["eur"], r["naam"]))


def audit(data_dir: str, records, nu: float | None = None, base_dir: str = "") -> dict:
    nu = nu if nu is not None else time.time()
    b = Bronnen(data_dir, records)
    kosten = kosten_per_call_site(b)
    code = code_datums(base_dir) if base_dir else {}
    rollen = rollen_regels(b, kosten, nu)
    skills = skill_regels(b, kosten, nu, code)
    infra = {cs: v for cs, v in kosten.items() if not skill_van_call_site(cs)}
    # Skill-kosten waarvoor geen enkel gebruik is vastgelegd: die horen bij niemand, en dat is zelf
    # een bevinding — er draaide iets waarvan geen record zegt wie het aanriep.
    gebruik = gebruik_per_skill(b)
    zwevend = {cs: v for cs, v in kosten.items()
               if skill_van_call_site(cs) and not (gebruik.get(skill_van_call_site(cs)) or {})}
    return {"nu": nu, "bronnen": b, "kosten": kosten, "infra": infra, "zwevend": zwevend,
            "rollen": rollen, "skills": skills}


# ── Het verslag ─────────────────────────────────────────────────────────────

_SOORT_ZIN = {
    "project_afgerond": "project afgetekend door een mens",
    "pagina_bewerkt": "pagina door een mens bewerkt",
    "besluit_genomen": "besluit genomen op een spanning",
    "certificaat_gebankt": "certificaat in het register",
    "deliverable_in_afgetekend_project": "deliverable in een afgetekend project",
}


def _dt(ts) -> str:
    if not ts:
        return "nooit"
    return time.strftime("%Y-%m-%d", time.localtime(float(ts)))


def _eur(bedrag: float, onbekend: int = 0) -> str:
    s = f"€{bedrag:.2f}"
    return s + (f" + {onbekend} zonder prijs" if onbekend else "")


def _kosten_cel(r: dict) -> str:
    """Model-verbruik én API-verbruik in één cel. Elke Kroniek-regel is één aanroep van een externe
    bron — dat is het API-verbruik, en het staat los van wat het model kostte."""
    delen = [_eur(r["eur"], r["onbekend"])]
    if r.get("calls"):
        delen.append(f"{r['calls']} model-calls")
    if r.get("kroniek_n"):
        delen.append(f"{r['kroniek_n']} bron-aanroepen")
    return " · ".join(delen)


def _bewijs(u: list, cap: int = 3) -> str:
    if not u:
        return "—"
    stukken = [f"{_SOORT_ZIN.get(x['soort'], x['soort'])} `{x['ref']}`" for x in u[:cap]]
    rest = f" (+{len(u) - cap})" if len(u) > cap else ""
    return "; ".join(stukken) + rest


def _beweging(r: dict, *, rol: bool) -> str:
    """Wat er wél gebeurde, als het geen uitkomst was. Concreet, uit de tellingen."""
    d = []
    k = r["kroniek"]
    if r["kroniek_n"]:
        d.append(f"{r['kroniek_n']} Kroniek-record(s): {k.get('bevestigd', 0)} bevestigd, "
                 f"{k.get('leeg', 0)} leeg, {k.get('fout', 0)} fout")
    if rol:
        if r["deliverables"]:
            d.append(f"{r['deliverables']} deliverable(s)")
        if r["projecten"]:
            d.append(f"{r['projecten']} project(en)")
        if r["paginas"]:
            d.append(f"{r['paginas']} pagina('s), waarvan {r['paginas_met_feiten']} met een "
                     f"gegrond feit")
        if r["opgeworpen"]:
            d.append(f"{r['opgeworpen']} spanning(en) opgeworpen")
    else:
        if r["deliverables"]:
            d.append(f"{r['deliverables']} deliverable(s), waarvan "
                     f"{r['deliverables_afgetekend']} in een afgetekend project")
    return "; ".join(d) or "niets"


def top_line(rapport: dict) -> str:
    rollen, skills = rapport["rollen"], rapport["skills"]
    raak = (sum(1 for r in rollen if r["uitkomsten"])
            + sum(1 for s in skills if s["uitkomsten"]))
    return (f"{len(rollen)} rollen en {len(skills)} skills geïnventariseerd, waarvan {raak} "
            f"aantoonbaar een Nooch-uitkomst raakten.")


def duurste_zonder_uitkomst(rapport: dict, n: int = 5) -> dict:
    """De posten die het meeste kostten voor de minste bewezen uitkomst, in TWEE lijsten.

    Rollen en skills apart, en dat is geen vormkeuze: dezelfde euro verschijnt in allebei (een rol
    kost wat zijn skills kosten). Door elkaar gehusseld zou de lijst suggereren dat er twee keer zo
    veel te besparen valt als er is."""
    rollen = [{"wat": r["naam"], "eur": r["eur"], "calls": r["calls"],
               "beweging": _beweging(r, rol=True)}
              for r in rapport["rollen"] if not r["uitkomsten"] and r["eur"] > 0]
    skills = [{"wat": s["naam"], "eur": s["eur"], "calls": s["calls"],
               "beweging": _beweging(s, rol=False)}
              for s in rapport["skills"] if not s["uitkomsten"] and s["eur"] > 0]
    return {"rollen": sorted(rollen, key=lambda x: -x["eur"])[:n],
            "skills": sorted(skills, key=lambda x: -x["eur"])[:n]}


def rapport_tekst(rapport: dict) -> str:
    b = rapport["bronnen"]
    rollen, skills = rapport["rollen"], rapport["skills"]
    datum = _dt(rapport["nu"])
    uit = [top_line(rapport), "", f"# Waarde-audit — {datum}", "",
           "*Deterministisch, geen LLM-oordeel. Fail-closed: geen record van een uitkomst = interne "
           "beweging.*", ""]

    # ── methode, want een lijst zonder meetlat is een mening ────────────────
    uit += ["## Wat als uitkomst telt", "",
            "| signaal | bron | wat het bewijst |",
            "|---|---|---|",
            "| project afgetekend | `projects.json`, veld `outcome` | een mens heeft het bekeken "
            "en Done toegekend (Done komt pas ná review) |",
            "| pagina bewerkt | `attachments.json`, versie met `actor_type=\"human\"` | iemand "
            "gebruikte de pagina en raakte hem aan |",
            "| besluit genomen | `notifications.json`, verwerking met een echte uitkomst | ja, nee, "
            "suggestie, project, actie of roloverleg-punt |",
            "| certificaat | `data/certificaten/` | een certificaat dat een claim kan dragen |",
            "",
            "**Niet meegeteld:** `ping` (doorsturen) en `none` (\"niks nodig\") sluiten een item "
            "zonder iets te veranderen. `dod_outcome` is de definitie van klaar, niet het bewijs. "
            "Een Kroniek-record `bevestigd` bewijst dat een bron antwoordde, niet dat er iets mee "
            "gebeurde.", "",
            "**Bij een skill** telt een deliverable die in een door een mens afgetekend project zit. Dat is "
            "samen-voorkomen, geen oorzaak: het project is afgetekend, en deze skill leverde er iets "
            "aan. Het omgekeerde is wél hard — een skill wiens deliverables in géén enkel afgetekend "
            "project zitten, heeft niets geleverd waar een mens ooit een handtekening onder zette.",
            "",
            "**Wat dit NIET meet.** Ook een afgetekend project bewijst dat een mens tekende, niet "
            "dat er een schoen verkocht is of een leverancier bewoog. De uitkomsttekst is "
            "procedureel (\"goedgekeurd na review\") — de code waarschuwt daar zelf voor "
            "(`project_signal._PROCEDUREEL`). Dit is het sterkste signaal dat de data draagt; het "
            "is geen omzet.", ""]

    # ── de kostenkant ──────────────────────────────────────────────────────
    duur = duurste_zonder_uitkomst(rapport)
    tot_eur = sum(v["eur"] for v in rapport["kosten"].values())
    tot_onb = sum(v["onbekend"] for v in rapport["kosten"].values())
    uit += ["## Kosten voor de minste uitkomst", "",
            f"Totaal model-verbruik in het log: {_eur(tot_eur, tot_onb)} over "
            f"{sum(v['calls'] for v in rapport['kosten'].values())} calls.", ""]
    if duur["rollen"] or duur["skills"]:
        uit += ["Deze posten kostten het meest zonder één bewezen uitkomst — de eerste kandidaten "
                "om te laten slapen. **Rollen en skills staan apart omdat het dezelfde euro's zijn** "
                "(een rol kost wat zijn skills kosten); door elkaar gehusseld zou het lijken alsof "
                "er twee keer zo veel te besparen valt.", ""]
        for kop, rijen, is_rol in (("Rollen", duur["rollen"], True),
                                   ("Skills", duur["skills"], False)):
            if not rijen:
                continue
            uit += [f"**{kop}**", "", "| post | kosten | calls | wat er wél gebeurde |",
                    "|---|---|---|---|"]
            uit += [f"| {x['wat'] if is_rol else '`' + x['wat'] + '`'} | €{x['eur']:.2f} | "
                    f"{x['calls']} | {x['beweging']} |" for x in rijen]
            uit.append("")
    else:
        uit += ["Geen enkele post met kosten én zonder bewezen uitkomst.", ""]

    uit += ["*Kosten per rol zijn naar rato van het VASTGELEGDE gebruik verdeeld (Kroniek + "
            "deliverables), niet vol per rol: `tegenspraak` staat op acht rollen, en die alle acht "
            "de volle prijs geven maakt het dorp acht keer zo duur als het is.*", ""]

    zwevend = sorted(rapport.get("zwevend", {}).items(), key=lambda kv: -kv[1]["eur"])
    zwevend = [(cs, v) for cs, v in zwevend if v["eur"] > 0 or v["onbekend"]]
    if zwevend:
        uit += ["**Niet toe te wijzen skill-kosten.** Deze skills draaiden wél model-calls, maar "
                "geen enkel record zegt wie ze aanriep — geen Kroniek-regel, geen deliverable. Ze "
                "horen dus bij niemand, en dat is zelf een bevinding:", "",
                "| skill | kosten | calls |", "|---|---|---|"]
        uit += [f"| `{skill_van_call_site(cs)}` | {_eur(v['eur'], v['onbekend'])} | {v['calls']} |"
                for cs, v in zwevend]
        uit.append("")

    infra = sorted(rapport["infra"].items(), key=lambda kv: -kv[1]["eur"])[:8]
    if infra:
        uit += ["**Dorpsinfrastructuur** (niet aan een rol of skill toe te schrijven, want de "
                "call-site zegt niet wie hem aanriep):", "",
                "| call-site | kosten | calls |", "|---|---|---|"]
        uit += [f"| `{cs}` | {_eur(v['eur'], v['onbekend'])} | {v['calls']} |" for cs, v in infra]
        uit.append("")

    # ── de rollen ──────────────────────────────────────────────────────────
    uit += ["## Rollen", "",
            "| rol | bracht voort | Nooch-uitkomst? | kosten | laatst | advies |",
            "|---|---|---|---|---|---|"]
    for r in rollen:
        raakt = f"**ja** — {_bewijs(r['uitkomsten'])}" if r["uitkomsten"] else "**nee**"
        uit.append(f"| {r['naam']} | {_beweging(r, rol=True)} | {raakt} | "
                   f"{_kosten_cel(r)} | {_dt(r['laatst'])} | {r['advies']} |")
    uit.append("")
    uit += ["Per rol, waarom dat advies:", ""]
    uit += [f"- **{r['naam']}** (`{r['id']}`) — {r['waarom']}." for r in rollen]
    uit.append("")

    # ── de skills ──────────────────────────────────────────────────────────
    uit += ["## Skills", "",
            "| skill | bracht voort | Nooch-uitkomst? | kosten | laatst | advies |",
            "|---|---|---|---|---|---|"]
    for s in skills:
        raakt = f"**ja** — {_bewijs(s['uitkomsten'])}" if s["uitkomsten"] else "**nee**"
        uit.append(f"| `{s['naam']}` | {_beweging(s, rol=False)} | {raakt} | "
                   f"{_kosten_cel(s)} | {_dt(s['laatst'])} | {s['advies']} |")
    uit.append("")
    uit += ["Per skill, waarom dat advies:", ""]
    for s in skills:
        regel = (f"- **`{s['naam']}`** — {s['waarom']}"
                 + (f" · toegewezen aan: {', '.join(s['rollen'])}" if s["rollen"] else
                    " · aan geen enkele rol toegewezen"))
        if s["advies"] == OPRUIMEN:
            # Nooit gedraaid is iets anders als de code vers is dan wanneer hij vergeten is.
            regel += (f" · code laatst gewijzigd {_dt(s['code_laatst'])}" if s.get("code_laatst")
                      else " · geen implementatiebestand gevonden")
        uit.append(regel + ".")
    uit.append("")

    # ── wat de mens moet beslissen ─────────────────────────────────────────
    structureel = [r for r in rollen if r["advies"] == STRUCTUREEL]
    if structureel:
        uit += ["## Grondwettelijke rollen — buiten de meting", "",
                "Een Circle Lead, Circle Rep, Secretary of Facilitator bestaat om governance te "
                "dragen, niet om deliverables te maken. Ze op output afrekenen is een "
                "categoriefout, en \"opruimen\" zou betekenen dat je de Secretary opheft. Ze staan "
                "hier compleet, zonder oordeel:", "",
                ", ".join(f"{r['naam']} (`{r['id']}`)" for r in structureel), ""]

    vlaggen = [r for r in rollen if r["advies"] == VLAG] + [s for s in skills if s["advies"] == VLAG]
    uit += ["## Twijfelgevallen — voor Stefan", ""]
    if vlaggen:
        uit += ["Deze zijn niet met de data te beslissen. Ze staan hier ongeraden:", ""]
        uit += [f"- **{v.get('naam')}** — {v['waarom']}" for v in vlaggen]
    else:
        uit += ["Geen. Elke rol en elke skill viel eenduidig uit de records."]
    uit.append("")

    # ── de bronnen, zodat het narekenbaar is ───────────────────────────────
    uit += ["## Waarop dit rust", "",
            f"- Kroniek: {len(b.kroniek)} records",
            f"- Model-verbruik: {len(b.usage)} calls",
            f"- Projecten: {len(b.projects)}, waarvan "
            f"{sum(1 for p in b.projects.values() if str(p.get('outcome') or '').strip())} "
            f"afgetekend door een mens",
            f"- Artefacten: {len(b.attachments)}, waarvan "
            f"{sum(1 for a in b.attachments.values() if a.get('kind') == 'note')} pagina's",
            f"- Deliverables: {len(b.deliverables)}",
            f"- Spanningen: {len(b.notifs)}, waarvan "
            f"{sum(1 for n in b.notifs if n.get('verwerkingen'))} met een verwerk-record",
            f"- Certificaten: {len(b.certificaten)}",
            f"- Output-bestanden: {len(b.output)}",
            f"- Zelf-verwerkingen: {len(b.verwerkingen)} · villageraad: {len(b.raad)} · "
            f"gaten: {len(b.gaps)}", ""]
    return "\n".join(uit)
