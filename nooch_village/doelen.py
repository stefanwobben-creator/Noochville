"""Doelen — waar het werk naartoe gaat, met de voortgang en het kritieke pad als afgeleiden.

Aanleiding (11 september 2026). Stefan: "wij hebben een keer een prototype gemaakt voor goals,
tijd om die functionaliteit te bouwen. Onder goals hangen weer projecten, we willen voortgang zien,
zou mooi zijn als je ook het kritieke pad inzichtelijk kunt maken." Het ontwerp stond al in
`docs/ontwerpnotitie_doelen.md` (mockup `docs/MITH_doelen_incockpit.html`); dit bouwt dat model,
plus de twee dingen die hij nu vraagt. Zijn vijf doelen zaait `zaai()`.

Het model (canoniek, uit de ontwerpnotitie):
- Een **doel** is een lichte entiteit in de intentielaag (`data/doelen.json`): titel, kort label,
  definition of done, deadline, status (open · behaald · gestopt), optioneel werkpakketten
  (activiteiten). Geen rol, geen cirkel; de anchor-lead beheert ze.
- Een **project blijft van zijn rol** en VERWIJST naar een doel (`doel_id`, optioneel `activiteit`).
  Rol-autonomie blijft intact; het doel is een etiket plus een optelsom.
- Een project kan zeggen van welke projecten het afhankelijk is (`depends_on`). Dat is een
  PLANNINGSrelatie, los van de runtime-status (`waiting_on` van de scheduler blijft wat hij is).

Twee afgeleiden, nooit opgeslagen (reference, don't copy):
- **Voortgang** = (afgeronde projecten × 1 + open projecten × hun checklist-ratio) / aantal. Eén
  formule, dezelfde `checklist_progress` als de kaart en de review-poort. Geen handmatig percentage.
- **Kritieke pad** = de langste keten van open projecten door de afhankelijkheden, het knelpunt
  (het open project waar de meeste andere op wachten), wie waarop wacht, wat nu vrij op te pakken
  is, en een vlag als een deadline in de keten voorbij de deadline van het doel ligt. Een kring in de
  afhankelijkheden is een fout in de invoer en wordt als zodanig gemeld, niet stilzwijgend gebroken.
"""
from __future__ import annotations

import time
import uuid

from nooch_village.util import JsonStore
from nooch_village import projects as _P

STATUSSEN = ("open", "behaald", "gestopt")

#: De vijf doelen van 11 september 2026, in Stefans woorden. `zaai()` maakt ze aan als ze er nog
#: niet zijn (op label); deadline en definition of done vult hij daarna in.
ZAAD = (
    ("Website", "De nieuwe website live"),
    ("STCB", "Rapport STCB-subsidie"),
    ("MITH", "Rapport MITH"),
    ("Batch 4", "Succesvolle lancering van batch 4"),
    ("Supply chain", "Supply chain helemaal zelf in beheer"),
)


class DoelStore(JsonStore):
    """`data/doelen.json`: id → doel. Onder het bestandsslot, want de cockpit en de CLI (zaai)
    schrijven allebei."""
    _STATE = "_data"
    _default = dict
    _EXPECT = dict
    _WRITE_METHODS = ("add", "update", "remove")

    def all(self) -> list[dict]:
        return sorted(self._data.values(), key=lambda d: (d.get("created_at") or 0, d.get("titel") or ""))

    def get(self, doel_id: str) -> dict | None:
        return self._data.get(doel_id or "")

    def by_label(self, label: str) -> dict | None:
        lab = (label or "").strip().lower()
        return next((d for d in self._data.values() if (d.get("label") or "").strip().lower() == lab), None)

    def add(self, titel: str, *, label: str = "", dod: str = "", deadline: str = "",
            activiteiten=(), by: str = "") -> dict:
        titel = (titel or "").strip()
        if not titel:
            raise ValueError("een doel heeft een titel nodig")
        did = uuid.uuid4().hex[:12]
        doel = {"id": did, "titel": titel[:140], "label": ((label or "").strip() or _kort_label(titel))[:24],
                "dod": (dod or "").strip()[:2000], "deadline": _datum(deadline), "status": "open",
                "activiteiten": [str(a).strip()[:120] for a in (activiteiten or ()) if str(a).strip()],
                "created_at": time.time(), "updated_at": time.time(), "by": by or ""}
        self._data[did] = doel
        self._save()
        return doel

    def update(self, doel_id: str, **velden) -> bool:
        """Alleen bekende velden; status alleen uit STATUSSEN; deadline als ISO-datum of leeg."""
        d = self._data.get(doel_id or "")
        if d is None:
            return False
        for k, v in velden.items():
            if k == "titel" and (v or "").strip():
                d["titel"] = str(v).strip()[:140]
            elif k == "label":
                d["label"] = (str(v or "").strip() or _kort_label(d["titel"]))[:24]
            elif k == "dod":
                d["dod"] = str(v or "").strip()[:2000]
            elif k == "deadline":
                d["deadline"] = _datum(v)
            elif k == "status" and v in STATUSSEN:
                d["status"] = v
            elif k == "activiteiten":
                d["activiteiten"] = [str(a).strip()[:120] for a in (v or ()) if str(a).strip()]
        d["updated_at"] = time.time()
        self._save()
        return True

    def remove(self, doel_id: str) -> bool:
        if self._data.pop(doel_id or "", None) is None:
            return False
        self._save()
        return True


def _kort_label(titel: str) -> str:
    return (titel or "").strip().split(" ")[0][:24] or "doel"


def _datum(v) -> str:
    """'YYYY-MM-DD' of leeg; iets anders is geen deadline (fail-closed, geen gok)."""
    s = str(v or "").strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-" and s[:4].isdigit() and s[5:7].isdigit() and s[8:].isdigit():
        return s
    return ""


# ── de projecten van een doel ────────────────────────────────────────────────

def projecten_van(doel_id: str, alle_projecten) -> list[dict]:
    """De projecten die naar dit doel verwijzen: alles wat niet gearchiveerd is, plús wat afgerond
    én gearchiveerd is. Sinds scope 49 verlaat een project het bord zodra zijn verslag bevestigd is;
    dat is een opruiming van het bord, geen uitschrijving uit het doel — een afgerond project blijft
    meetellen in de voortgang. Een gearchiveerd project dat NIET af is (opgegeven) telt niet mee.
    Concepten (draft) tellen mee zodra ze gekoppeld zijn: wie een concept aan een doel hangt, zegt
    dat het erbij hoort."""
    return [p for p in alle_projecten if p.get("doel_id") == doel_id
            and (not p.get("archived") or p.get("status") in _P.KLAAR)]


def project_score(p: dict) -> float:
    """1.0 als af; anders de checklist-ratio (dezelfde teller als de kaart); zonder checklist 0.0.
    Geen status-gok ("running = 30%"): een balk die iets belooft wat niemand mat is ruis."""
    if p.get("status") in _P.KLAAR:
        return 1.0
    items = [it for cl in (p.get("checklists") or []) for it in cl.get("items", [])]
    af, telbaar = _P.checklist_progress(items)
    return (af / telbaar) if telbaar else 0.0


def voortgang(doel: dict, alle_projecten) -> dict:
    ps = projecten_van(doel["id"], alle_projecten)
    af = [p for p in ps if p.get("status") in _P.KLAAR]
    punten = sum(project_score(p) for p in ps)
    pct = round(100 * punten / len(ps)) if ps else 0
    return {"totaal": len(ps), "af": len(af), "open": len(ps) - len(af),
            "punten": round(punten, 1), "pct": pct,
            "per_status": _per_status(ps)}


def _per_status(ps) -> dict:
    uit: dict = {}
    for p in ps:
        uit[p.get("status") or "?"] = uit.get(p.get("status") or "?", 0) + 1
    return uit


# ── het kritieke pad ─────────────────────────────────────────────────────────

class Kringloop(ValueError):
    """A wacht op B wacht op A: dat is geen pad, dat is een fout in de invoer."""


def kritieke_pad(doel: dict, alle_projecten) -> dict:
    """De langste keten van OPEN projecten door `depends_on`, plus knelpunt, wachtenden, vrij werk en
    de deadline-vlaggen. Afgeronde projecten zijn geen schakel meer: een keten loopt er dwars
    doorheen alsof ze er niet zijn. Afhankelijkheden op projecten buiten dit doel tellen wél als
    'wacht op' (het werk wacht echt), maar staan niet in de keten van dit doel."""
    ps = projecten_van(doel["id"], alle_projecten)
    per_id = {p["id"]: p for p in alle_projecten}
    open_ = {p["id"]: p for p in ps if p.get("status") not in _P.KLAAR}

    def open_deps(pid: str) -> list[str]:
        return [d for d in (per_id.get(pid, {}).get("depends_on") or [])
                if d in per_id and per_id[d].get("status") not in _P.KLAAR and not per_id[d].get("archived")]

    # langste keten (in schakels) die in een open project van dit doel eindigt; memo + kringdetectie
    memo: dict[str, list[str]] = {}
    bezig: set[str] = set()

    def keten(pid: str) -> list[str]:
        if pid in memo:
            return memo[pid]
        if pid in bezig:
            raise Kringloop(pid)
        bezig.add(pid)
        beste: list[str] = []
        for d in open_deps(pid):
            if d in open_:                       # alleen schakels binnen dit doel vormen de keten
                k = keten(d)
                if len(k) > len(beste):
                    beste = k
        bezig.discard(pid)
        memo[pid] = beste + [pid]
        return memo[pid]

    kring = ""
    langste: list[str] = []
    for pid in open_:
        try:
            k = keten(pid)
        except Kringloop as exc:
            kring = str(exc)
            break
        if len(k) > len(langste) or (len(k) == len(langste) and _laatste_due(k, per_id) > _laatste_due(langste, per_id)):
            langste = k

    # wie wacht waarop (open op open), en wat is vrij
    wachtend = [(pid, open_deps(pid)) for pid in open_ if open_deps(pid)]
    wacht_ids = {pid for pid, _ in wachtend}
    vrij = [pid for pid in open_ if pid not in wacht_ids]

    # knelpunt: het open project met de meeste (transitieve) afhankelijke open projecten
    afh: dict[str, set] = {pid: set() for pid in open_}
    for pid, deps in wachtend:
        for d in deps:
            if d in afh:
                afh[d].add(pid)

    def transitief(pid: str, gezien=None) -> set:
        gezien = gezien if gezien is not None else set()
        for x in afh.get(pid, ()):
            if x not in gezien:
                gezien.add(x)
                transitief(x, gezien)
        return gezien

    tellingen = {pid: len(transitief(pid)) for pid in open_}
    knel = max(tellingen, key=lambda k: (tellingen[k], k)) if tellingen and max(tellingen.values()) > 0 else ""

    # deadline-vlaggen: een project in de keten (of open) met een deadline ná die van het doel
    vlaggen = []
    dl = doel.get("deadline") or ""
    if dl:
        for pid, p in open_.items():
            if (p.get("due") or "") > dl:
                vlaggen.append({"pid": pid, "due": p["due"], "in_keten": pid in langste})
    return {"keten": langste, "knelpunt": {"pid": knel, "wachtenden": tellingen.get(knel, 0)} if knel else None,
            "wachtend": wachtend, "vrij": vrij, "vlaggen": vlaggen, "kring": kring,
            "open": len(open_), "met_afhankelijkheden": len(wachtend)}


def _laatste_due(pids, per_id) -> str:
    return max((per_id.get(p, {}).get("due") or "" for p in pids), default="")


# ── zaad ─────────────────────────────────────────────────────────────────────

def zaai(store: DoelStore, *, apply: bool = False, by: str = "zaad") -> list[dict]:
    """De vijf doelen van 11 september, idempotent op label. Dry-run default: geeft terug wat er
    zou komen; met apply=True schrijft hij. Geen deadline en geen DoD: die vult de founder in."""
    uit = []
    for label, titel in ZAAD:
        bestaat = store.by_label(label)
        if bestaat:
            uit.append({"label": label, "titel": titel, "actie": "bestaat", "id": bestaat["id"]})
            continue
        if apply:
            d = store.add(titel, label=label, by=by)
            uit.append({"label": label, "titel": titel, "actie": "aangemaakt", "id": d["id"]})
        else:
            uit.append({"label": label, "titel": titel, "actie": "zou aanmaken", "id": ""})
    return uit
