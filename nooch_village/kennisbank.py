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
        "Je bent mijn denkpartner, niet mijn fan. We maken van EEN vermoeden EEN klein, "
        "toetsbaar inzicht. Duw me, vlei me niet. Een vraag per beurt, dan stoppen en wachten.\n\n"
        f"MIJN VERMOEDEN:\n  {hunch or '(vul in)'}\n\n"
        f"DE KAARTEN OP TAFEL:\n{sig}\n\n"
        "WAT JE DOET, stap voor stap, elke beurt eindigend met EEN vraag:\n"
        "1. Geef de sterkste TEGENOVERGESTELDE (eerst wild, dan serieus). Vraag mijn reactie.\n"
        "2. Duw met 1-2 scherpe vragen. Gebruik vooral de kaarten die tegenspreken.\n"
        "3. Vraag me mijn vermoeden op een lijn 0-100 te zetten.\n"
        "4. Vat 3 tot 5 bewijzen samen uit de kaarten. Te weinig? Zeg \"nog niet rijp\" en stop.\n"
        "5. Vraag wat mij van gedachten zou doen veranderen. Geen business-excuus: "
        "iets dat je in de wereld ZIET gebeuren.\n"
        "6. Zodra we een claim, een reframe en een echte falsifier hebben, geef dit blok en stop:\n\n"
        "=== INZICHT ===\nTITEL: <kort>\nCLAIM: <1-2 zinnen>\nREFRAME: <sterkste tegenovergestelde, 1 zin>\n"
        "FALSIFIER: <wat zou dit onderuit halen>\n=== EINDE ===")


def parse_blok(text: str) -> dict:
    """Parse het === INZICHT ===-blok dat de AI teruggaf. Fail-soft: ontbrekende regels → ''."""
    o = {"title": "", "claim": "", "reframe": "", "falsifier": ""}
    for line in (text or "").splitlines():
        s = line.strip()
        for veld, key in (("TITEL", "title"), ("CLAIM", "claim"),
                          ("REFRAME", "reframe"), ("FALSIFIER", "falsifier")):
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

    _WRITE_METHODS = ("add", "link", "unlink", "annotate", "discuss", "reformulate",
                      "set_caveat")

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
            "created_by": by, "created_at": _now(), "updated_at": _now(),
        }
        self._save()
        return iid

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
                    falsifier: str = "", by: str = "") -> str | None:
        """De trage klok: claim/reframe/falsifier opnieuw gemunt (het spel opnieuw gespeeld).
        Bumpt de versie; de vorige versie + de evidence-set-van-toen gaan in `history`
        (reproduceerbaar). De evidence-links zelf blijven doorstromen (de snelle klok)."""
        ins = self._items.get(iid)
        if ins is None or not (title or reframe or falsifier):
            return None
        ins["history"].append({
            "version": ins["version"], "title": ins["title"], "reframe": ins["reframe"],
            "falsifier": ins["falsifier"],
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
        ins["updated_at"] = _now()
        self._save()
        return ins["version"]
