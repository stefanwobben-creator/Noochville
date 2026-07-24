"""Kennisbank — laag 2 van de kennislaag: geversioneerde inzichten bóven de atomen.

Twee lagen, streng gescheiden (docs-brief kennisbank):
  - Laag 1 (atomen) = de bestaande kaartjes in `data/notes.json` (NotesStore/insight.Insight).
    Dom en simpel: inhoud + bron + herkomst. GEEN consensus-wiskunde op dit niveau.
  - Laag 2 (dit bestand) = inzichten: een claim + reframe + falsifier, verankerd aan een
    gecureerde set atomen (evidence-links met richting). Pas hier ontstaat het "veld"
    van zekerheid — berekend uit het netwerk van bewijs, nooit met de hand gezet.

Principes die dit bestand bewaakt:
  - Zekerheid is een VELD, geen waarde op een kaart: `field()` + `verdict()` rekenen het
    live uit de gelinkte atomen; er wordt nooit een zekerheids-getal opgeslagen.
  - Onafhankelijkheid telt, niet aantal (woozle-guard): atomen met dezelfde
    onafhankelijkheidsgroep (genormaliseerde bron) zijn samen één stem.
  - Gewicht wordt AFGELEID (provenance × onafhankelijkheid × actualiteit), niet gerangschikt.
  - Append-only: loskoppelen verwijdert een link, de kaart blijft in de bibliotheek;
    herformuleren bumpt de versie en bewaart de vorige in `history` (reproduceerbaar).
  - De machinerie blijft binnen: de UI toont alleen het woord + meter + één zin.
"""
from __future__ import annotations

import copy
import json
import os
import re
import uuid
from datetime import datetime

from nooch_village.util import JsonStore

# ── Trust-ladder (de "provenance") ───────────────────────────────────────────
# De ordening is belangrijker dan de exacte waarden: peer-reviewed > certificaat >
# eigen metingen > survey > domein-expert > media > advocacy. Een intern oordeel
# (meningssterkte) staat bewust los van bewijssterkte.
PROVENANCE_TRUST = {
    "peer_reviewed": 0.90,
    "certificate": 0.85,
    "internal_data": 0.75,
    "survey": 0.65,
    "expert_opinion": 0.60,
    "media": 0.40,
    "internal_judgment": 0.40,
    "advocacy": 0.30,
    "unknown": 0.20,
}

# Fallback voor bestaande kaartjes zonder provenance-veld: het al aanwezige
# insight.EvidenceType vertaalt naar dezelfde ladder (zelfde ordening).
_EVIDENCE_TRUST = {
    "peer_reviewed": 0.90,
    "certified": 0.85,
    "measured": 0.75,
    "reported": 0.40,
    "claimed": 0.30,
}


def norm_bron(source: str) -> str:
    """Onafhankelijkheidsgroep: genormaliseerde bron-sleutel voor de woozle-guard.
    Kaarten met dezelfde onderliggende bron (bijv. één survey) delen één groep = één stem."""
    return re.sub(r"[^a-z0-9]", "", (source or "").lower())


def independence_group(atom: dict) -> str:
    expl = (atom.get("independence_group") or "").strip()
    return expl or norm_bron(atom.get("source") or "")


def atom_trust(atom: dict) -> float:
    """Afgeleid gewicht van één atoom. Provenance eerst; ontbreekt die, dan het
    bestaande evidence_type; anders 'unknown'. Nooit met de hand gezet."""
    prov = (atom.get("provenance") or "").strip()
    if prov in PROVENANCE_TRUST:
        return PROVENANCE_TRUST[prov]
    ev = (atom.get("evidence_type") or "").strip()
    return _EVIDENCE_TRUST.get(ev, PROVENANCE_TRUST["unknown"])


def _recency_weight(atom: dict, now: datetime | None = None) -> float:
    """Actualiteit: oude punten vervagen zacht (verouderd feit ≠ vandaag). Tot 3 jaar
    vol gewicht, daarna −5%/jaar met een bodem van 0.5. Zonder datum: vol gewicht."""
    raw = (atom.get("source_date") or atom.get("created_at") or "")[:10]
    try:
        d = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return 1.0
    years = max(0.0, ((now or datetime.now()) - d).days / 365.25)
    return 1.0 if years <= 3 else max(0.5, 1.0 - 0.05 * (years - 3))


# ── Het veld van zekerheid (inzicht-niveau) ──────────────────────────────────

def field(evidence: list[dict], atoms: dict[str, dict]) -> dict:
    """Bereken het veld uit de evidence-links van een inzicht. Twee assen (IPCC-stijl):
    bewijssterkte (noisy-OR over onafhankelijke bronnen) en overeenstemming.
    Tien noten uit dezelfde bron zijn één stem (per groep telt de hoogste trust)."""
    def _groups(links: list[dict]) -> dict[str, float]:
        best: dict[str, float] = {}
        for l in links:
            a = atoms.get(l.get("atom_id") or "")
            if a is None:
                continue
            g = independence_group(a)
            t = atom_trust(a) * _recency_weight(a)
            if t > best.get(g, 0.0):
                best[g] = t
        return best

    sup = [l for l in evidence if l.get("stance") == "support"]
    cou = [l for l in evidence if l.get("stance") == "counter"]
    sg = _groups(sup)
    # Tegenspraak zonder echte bron ("nog geen bron") telt niet als onafhankelijke tegenstem.
    cg = {g: t for g, t in _groups(cou).items() if g}
    strength = 1.0
    for t in sg.values():
        strength *= (1.0 - t)
    strength = 1.0 - strength
    s_mass, c_mass = sum(sg.values()), sum(cg.values())
    agreement = 0.5 if (s_mass + c_mass) == 0 else s_mass / (s_mass + c_mass)
    return {"strength": strength, "agreement": agreement,
            "indep": len(sg), "indep_counter": len(cg), "n_support": len(sup)}


def meta_field(ins: dict, by_id: dict[str, dict], atoms: dict[str, dict]) -> dict:
    """Zekerheid van een META-inzicht (B1): afgeleid uit de onderliggende inzichten (ins['related']),
    nooit met de hand. Elk gelinkt inzicht draagt zijn DRAGENDE bewijs (zijn support-atomen) bij,
    met de richting van de meta-link; field() groepeert dan op de onderliggende atoom-bronnen
    (woozle), zodat twee gelinkte inzichten die dezelfde bron delen niet dubbeltellen. Zo blijft
    'zwaarte is afgeleid uit onafhankelijke bronnen' intact, één laag hoger."""
    synth: list[dict] = []
    for rel in ins.get("related") or []:
        other = by_id.get(rel.get("insight_id") or "")
        if other is None:
            continue
        link_stance = rel.get("stance") or "support"
        for l in other.get("evidence") or []:
            if l.get("stance") == "support":       # de dragende basis van het onderliggende inzicht
                synth.append({"atom_id": l.get("atom_id"), "stance": link_stance})
    return field(synth, atoms)


def verdict(f: dict) -> dict:
    """Vertaal het veld naar wat de mens ziet: één gewoon woord + 4-punts meter + één zin.
    NOOIT percentages, groep-ids of ruwe trust naar buiten laten lekken."""
    indep, indep_c, n_sup = f["indep"], f["indep_counter"], f["n_support"]
    if indep == 0:
        return {"word": "dun", "dots": 0, "sentence": "Nog geen bewijs verzameld."}
    if indep == 1:
        if n_sup > 1:
            zin = (f"Dit lijkt sterk, maar {n_sup} bevindingen komen <b>allemaal uit één "
                   f"bron</b>. Dat is één stem, niet {n_sup}.")
        else:
            zin = "Dit steunt op <b>één bron</b>. Leuk om te testen, nog geen conclusie."
        return {"word": "dun", "dots": 1, "sentence": zin}
    if indep_c >= indep:
        return {"word": "omstreden", "dots": 2,
                "sentence": "Losse bronnen wijzen <b>twee kanten</b> op. Nog geen winnaar."}
    if indep_c > 0:
        return {"word": "groeit", "dots": min(3, indep),
                "sentence": f"<b>{indep} losse bronnen</b> wijzen hierheen, "
                            "maar er is een serieus tegenpunt."}
    return {"word": "stevig", "dots": 4 if indep >= 3 else 3,
            "sentence": f"<b>{indep} losse bronnen</b> wijzen hierheen, "
                        "en niemand spreekt het tegen."}


WORD_LABEL = {"stevig": "stevig", "groeit": "groeit nog", "omstreden": "omstreden", "dun": "nog dun"}


# ── Het spel (fase 1: copy-paste; fase 3 draait dit server-side via de LLM-ladder) ─

def bouw_spel_prompt(hunch: str, atoms_rows: list[dict]) -> str:
    """De game-prompt uit de brief (§7): denkpartner, niet fan. atoms_rows: [{claim, stance}]."""
    sig = "\n".join(f"  - {a.get('claim', '')}"
                    + ("  [spreekt tegen]" if a.get("stance") == "counter" else "")
                    for a in atoms_rows) or "  (nog geen kaarten)"
    return (
        "Je bent mijn denkpartner, niet mijn fan. We maken van EEN vermoeden EEN klein, TOETSBAAR "
        "inzicht: scherp en weerlegbaar, niet per se 'waar'. Duw me, vlei me niet. Eén vraag per "
        "beurt, dan stoppen en wachten.\n\n"
        f"MIJN VERMOEDEN:\n  {hunch or '(vul in)'}\n\n"
        f"DE KAARTEN OP TAFEL:\n{sig}\n\n"
        "ELKE BEURT begin je met één regel die het werk-inzicht vasthoudt, zodat we de draad niet "
        "kwijtraken:\n  NU: <claim in wording> | reframe: <…> | falsifier: <…>   (nog leeg? schrijf "
        "'NU: nog aan het vormen').\n"
        "Blijf bij ÉÉN onderwerp en ÉÉN eigenschap. Schuift mijn antwoord of een kaart naar iets "
        "anders (bijv. van 'blijft sterk' naar 'composteert snel'), benoem dat en vraag of we wisselen "
        "of vasthouden — wissel nooit stiekem van onderwerp.\n\n"
        "WAT JE DOET, stap voor stap, elke beurt eindigend met EEN vraag:\n"
        "1. Geef de sterkste TEGENOVERGESTELDE (eerst wild, dan serieus). Vraag mijn reactie.\n"
        "2. Duw met 1-2 scherpe vragen. Gebruik vooral de kaarten die tegenspreken; laat een kaart die "
        "mijn claim ondergraaft NOOIT stil vallen — die hoort genuanceerd in de claim of in CAVEAT.\n"
        "3. Vraag me mijn vermoeden op een lijn 0-100 te zetten.\n"
        "4. Vat 3 tot 5 bewijzen samen uit de kaarten. Te weinig, of leunt alle steun op één bron? "
        "Zeg \"nog niet rijp\", geef GEEN inzicht-blok, en stop.\n"
        "5. Vraag wat mij van gedachten zou doen veranderen: iets dat je in de wereld ZIET gebeuren, "
        "geen business-excuus. Zeg ik 'niets' of 'het is een feit'? Dan is het geloof, geen toetsbaar "
        "inzicht — zeg dat eerlijk, duw door, rond niet af.\n"
        "6. Rond pas af bij een zelfstandige CLAIM, een echte REFRAME én een ECHTE falsifier. Een echte "
        "falsifier is IETS DAT JE KUNT ZIEN gebeuren en dat de claim onderuithaalt — niet de claim "
        "simpelweg omgekeerd ('het klopt niet'), niet iets onmogelijks ('alle veeteelt stopt'). Geef "
        "dan dit blok, één keer, en stop.\n\n"
        "HARDE EIS aan het inzicht: het moet OP ZICHZELF STAAN. Iemand die het onderwerp niet kent, "
        "of ikzelf een jaar later, moet uit de CLAIM alléén begrijpen waar het over gaat. Benoem dus "
        "WAT het ding of de speler IS in één adem: niet 'P-Life's additief', maar 'P-Life's organische "
        "additief dat gewoon plastic door bacteriën laat afbreken'. Kort en scherp: één zelfstandige "
        "bewering, geen verhaal en geen twee claims samengeperst. EENVOUDIGE, alledaagse taal: schrijf "
        "alsof je het uitlegt aan een slimme vriend die geen vakspecialist is. Vermijd jargon (dus niet "
        "'oxidatieve degradatie', 'mineraliseren', 'polyolefine', 'microbiologisch'); moet een vakterm "
        "echt, zeg hem dan meteen in gewone woorden ('bacteriën breken het af'). De TITEL is pakkend, "
        "maar de betekenis moet in de CLAIM staan, niet in de titel.\n\n"
        "=== INZICHT ===\n"
        "TITEL: <kort en pakkend>\n"
        "CLAIM: <1-2 zinnen, één zelfstandige bewering — benoem wat het onderwerp IS, niet alleen dat "
        "het iets doet; iemand zonder voorkennis snapt het>\n"
        "REFRAME: <sterkste tegenovergestelde, 1 zin>\n"
        "FALSIFIER: <concreet en waarneembaar: wat zou je in de wereld moeten zien gebeuren dat dit "
        "onderuithaalt>\n"
        "CAVEAT: <wat spreekt dit tegen of maakt het onzeker — vooral de tegenkaarten; laat leeg als "
        "er echt niets is, maar verzin niets>\n"
        "=== EINDE ===")


def parse_blok(text: str) -> dict:
    """Parse het === INZICHT ===-blok dat de AI teruggaf. Fail-soft: ontbrekende regels → ''."""
    o = {"title": "", "claim": "", "reframe": "", "falsifier": "", "caveat": ""}
    for line in (text or "").splitlines():
        s = line.strip()
        for veld, key in (("TITEL", "title"), ("CLAIM", "claim"),
                          ("REFRAME", "reframe"), ("FALSIFIER", "falsifier"),
                          ("CAVEAT", "caveat")):
            if re.match(rf"^{veld}:", s, re.I):
                o[key] = re.sub(rf"^{veld}:", "", s, flags=re.I).strip()
    return o


def _bump(version: str) -> str:
    p = (version or "1.0").split(".")
    try:
        minor = int(p[1]) if len(p) > 1 else 0
    except ValueError:
        minor = 0
    return f"{p[0]}.{minor + 1}"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Atomen lezen (laag 1) ────────────────────────────────────────────────────

def load_atoms(data_dir: str, include_archived: bool = False) -> dict[str, dict]:
    """Lees de atomen-bibliotheek (notes.json) als ruwe dicts, zodat schema-drift in oude
    kaartjes het kennisbank-scherm nooit laat crashen (zelfde keuze als views/kennislaag).
    Gearchiveerde kaarten (curatie, addendum C) blijven standaard buiten beeld — bakje,
    bibliotheek, clusters, zoeken en spel zijn daarmee in één klap schoon."""
    path = os.path.join(data_dir, "notes.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    if include_archived:
        return raw
    return {aid: a for aid, a in raw.items()
            if not (isinstance(a, dict) and a.get("archived"))}


# ── De store (laag 2) ────────────────────────────────────────────────────────

class KennisbankStore(JsonStore):
    """Geversioneerde inzichten. Eén inzicht:
    {id, title (de claim, mensentaal), why (één zin context), reframe, falsifier, caveat,
     subject, version, history[], evidence[{atom_id, stance, annotation, by, created_at}],
     discussion[{text, by, created_at}], created_at, updated_at}"""

    _WRITE_METHODS = ("add", "link", "unlink", "link_insight", "unlink_insight",
                      "annotate", "discuss", "reformulate",
                      "set_caveat", "rewire_atom")

    # -- reads (lock-vrij) --
    def get(self, iid: str) -> dict | None:
        return self._items.get(iid)

    def all(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda i: i.get("created_at") or "", reverse=True)

    # -- writes (automatisch gelockt + vers geladen) --
    def add(self, title: str, *, why: str = "", reframe: str = "", falsifier: str = "",
            caveat: str = "", subject: str = "", by: str = "") -> str:
        iid = "kb_" + uuid.uuid4().hex[:8]
        self._items[iid] = {
            "id": iid, "title": (title or "").strip(), "why": (why or "").strip(),
            "reframe": (reframe or "").strip(), "falsifier": (falsifier or "").strip(),
            "caveat": (caveat or "").strip(), "subject": (subject or "").strip(),
            "version": "1.0", "history": [], "evidence": [], "discussion": [],
            "related": [],
            "created_by": by, "created_at": _now(), "updated_at": _now(),
        }
        self._save()
        return iid

    def link_insight(self, iid: str, other_id: str, stance: str, *, by: str = "") -> bool:
        """Koppel een ander INZICHT als steun/tegen (B1: de Zettelkasten-ladder atoom→inzicht→
        meta-inzicht). Idempotent (richting bijwerken, geen dubbele stem); geen zelf-link;
        beide moeten bestaan."""
        ins = self._items.get(iid)
        if ins is None or other_id == iid or stance not in ("support", "counter") \
                or other_id not in self._items:
            return False
        ins.setdefault("related", [])
        for r in ins["related"]:
            if r["insight_id"] == other_id:
                r["stance"] = stance
                break
        else:
            ins["related"].append({"insight_id": other_id, "stance": stance,
                                   "by": by, "created_at": _now()})
        ins["updated_at"] = _now()
        self._save()
        return True

    def unlink_insight(self, iid: str, other_id: str) -> bool:
        ins = self._items.get(iid)
        if ins is None:
            return False
        voor = len(ins.get("related") or [])
        ins["related"] = [r for r in ins.get("related") or [] if r["insight_id"] != other_id]
        if len(ins["related"]) == voor:
            return False
        ins["updated_at"] = _now()
        self._save()
        return True

    def link(self, iid: str, atom_id: str, stance: str, *, annotation: str = "",
             by: str = "") -> bool:
        """Koppel een atoom als bewijs (richting + optionele waarom-annotatie). Idempotent:
        bestaat de link al, dan worden richting/annotatie bijgewerkt (geen dubbele stem)."""
        ins = self._items.get(iid)
        if ins is None or stance not in ("support", "counter") or not atom_id:
            return False
        for l in ins["evidence"]:
            if l["atom_id"] == atom_id:
                l["stance"] = stance
                if annotation:
                    l["annotation"] = annotation.strip()
                break
        else:
            ins["evidence"].append({"atom_id": atom_id, "stance": stance,
                                    "annotation": (annotation or "").strip() or None,
                                    "by": by, "created_at": _now()})
        ins["updated_at"] = _now()
        self._save()
        return True

    def unlink(self, iid: str, atom_id: str) -> bool:
        """Loskoppelen verwijdert alleen de LINK; de kaart blijft in de bibliotheek (append-only)."""
        ins = self._items.get(iid)
        if ins is None:
            return False
        voor = len(ins["evidence"])
        ins["evidence"] = [l for l in ins["evidence"] if l["atom_id"] != atom_id]
        if len(ins["evidence"]) == voor:
            return False
        ins["updated_at"] = _now()
        self._save()
        return True

    def rewire_atom(self, old_id: str, new_id: str) -> int:
        """Herwijs evidence-links in ALLE inzichten van old_id → new_id (na een atoom-merge:
        het bron-atoom verdwijnt, de bewijs-links mogen geen wezen worden). Wijst een inzicht
        al naar new_id, dan vervalt de oude link (geen dubbele stem — zelfde regel als
        link()-idempotentie). Geeft het aantal aangepaste inzichten terug."""
        if not old_id or not new_id or old_id == new_id:
            return 0
        n = 0
        for ins in self._items.values():
            ev = ins.get("evidence") or []
            if not any(l.get("atom_id") == old_id for l in ev):
                continue
            heeft_nieuw = any(l.get("atom_id") == new_id for l in ev)
            nieuw: list[dict] = []
            for l in ev:
                if l.get("atom_id") == old_id:
                    if heeft_nieuw:
                        continue                      # target al gelinkt → oude link vervalt
                    l = {**l, "atom_id": new_id}
                    heeft_nieuw = True
                nieuw.append(l)
            ins["evidence"] = nieuw
            ins["updated_at"] = _now()
            n += 1
        if n:
            self._save()
        return n

    def annotate(self, iid: str, atom_id: str, text: str) -> bool:
        """De waarom-notitie van de lezer bij één link (kennisdrager, optioneel)."""
        ins = self._items.get(iid)
        if ins is None:
            return False
        for l in ins["evidence"]:
            if l["atom_id"] == atom_id:
                l["annotation"] = (text or "").strip() or None
                ins["updated_at"] = _now()
                self._save()
                return True
        return False

    def discuss(self, iid: str, text: str, by: str) -> bool:
        """Kanttekening over het inzicht als geheel (de lezer is ook een bron)."""
        ins = self._items.get(iid)
        if ins is None or not (text or "").strip():
            return False
        ins["discussion"].append({"text": text.strip(), "by": by or "onbekend",
                                  "created_at": _now()})
        ins["updated_at"] = _now()
        self._save()
        return True

    def set_caveat(self, iid: str, text: str) -> bool:
        ins = self._items.get(iid)
        if ins is None:
            return False
        ins["caveat"] = (text or "").strip()
        ins["updated_at"] = _now()
        self._save()
        return True

    def reformulate(self, iid: str, *, title: str = "", reframe: str = "",
                    falsifier: str = "", caveat: str = "", by: str = "") -> str | None:
        """De trage klok: claim/reframe/falsifier/caveat opnieuw gemunt (het spel opnieuw gespeeld).
        Bumpt de versie; de vorige versie + de evidence-set-van-toen gaan in `history`
        (reproduceerbaar). De evidence-links zelf blijven doorstromen (de snelle klok)."""
        ins = self._items.get(iid)
        if ins is None or not (title or reframe or falsifier or caveat):
            return None
        ins["history"].append({
            "version": ins["version"], "title": ins["title"], "reframe": ins["reframe"],
            "falsifier": ins["falsifier"], "caveat": ins.get("caveat", ""),
            "evidence_snapshot": copy.deepcopy(ins["evidence"]),
            "at": _now(), "by": by,
        })
        ins["version"] = _bump(ins["version"])
        if title:
            ins["title"] = title.strip()
        if reframe:
            ins["reframe"] = reframe.strip()
        if falsifier:
            ins["falsifier"] = falsifier.strip()
        if caveat:
            ins["caveat"] = caveat.strip()
        ins["updated_at"] = _now()
        self._save()
        return ins["version"]
