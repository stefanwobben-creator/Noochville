"""De capaciteit-gat-oogst: wat het dorp niet kán, opgeschreven op het moment dat het pijn doet.

Elke keer dat werk vastloopt omdat niemand het kan uitvoeren, ontstaat hier een record. Dat is de
enige plek in het systeem waar structureel wordt bijgehouden wélke capaciteit ontbreekt en hoe vaak
dat iets blokkeerde — de grondstof voor de Codie-backlog.

Twee redenen, en alleen de eerste is bouwbaar:
  `missing_capability` — software zou dit kunnen; deze rol heeft er (nog) geen skill voor.
                         Dit voedt de dev-backlog.
  `human_external`     — geen software kan dit ooit (fysiek, offline, handtekening, telefoon).
                         Wel geregistreerd (zo zie je hoeveel mens-werk er in de keten zit),
                         maar het is nooit een feature-verzoek.

Append-only JSONL naast de stores (overlay-patroon, zoals de claims-runtime en de voorstel-overlay):
een gat is een waarneming met een tijdstip, geen state die je muteert. Fail-soft: een schrijffout mag
nooit een puls breken — de oogst is waardevol, maar niet waardevoller dan het werk zelf.
"""
from __future__ import annotations

import json
import logging
import os
import time

_LOG = logging.getLogger("village.gaps")

BESTAND = "gaps.jsonl"
MISSING_CAPABILITY = "missing_capability"
HUMAN_EXTERNAL = "human_external"
_REDENEN = (MISSING_CAPABILITY, HUMAN_EXTERNAL)


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def record(data_dir: str, *, role: str, item_text: str, project_id: str, reason: str,
           capability: str = "", hop_trail=None, item_id: str = "") -> dict | None:
    """Leg één capaciteitsgat vast. Geeft het geschreven record terug, of None bij een fout.

    `capability` is het korte, herbruikbare label waarop de backlog clustert ('patent search API'),
    los van de projectspecifieke `item_text` — anders is elk gat een eigen cluster van één."""
    if reason not in _REDENEN:
        _LOG.warning("gat NIET vastgelegd: onbekende reden %r (rol=%s)", reason, role)
        return None
    rij = {"role": role or "", "item_text": (item_text or "")[:300], "project_id": project_id or "",
           "reason": reason, "capability": (capability or "").strip()[:120],
           "hop_trail": list(hop_trail or []), "item_id": item_id or "", "ts": time.time()}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(rij, ensure_ascii=False) + "\n")
    except Exception as e:                       # noqa: BLE001 — oogsten mag de puls nooit breken
        _LOG.warning("gat niet weggeschreven (%s): %s", role, e)
        return None
    _LOG.info("🕳 capaciteitsgat [%s] %s — %s", reason, role, (capability or item_text)[:80])
    return rij


def alle(data_dir: str) -> list[dict]:
    """Alle gat-records, oudste eerst. Kapotte regels worden overgeslagen, niet fataal."""
    uit = []
    try:
        with open(pad(data_dir), encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = json.loads(regel)
                except ValueError:
                    continue
                if isinstance(rij, dict):
                    uit.append(rij)
    except FileNotFoundError:
        return []
    except Exception as e:                       # noqa: BLE001
        _LOG.warning("gat-ledger onleesbaar: %s", e)
        return []
    return uit


def _sleutel(rij: dict) -> str:
    """Cluster-sleutel: het capability-label, genormaliseerd. Zonder label valt een gat terug op
    zijn itemtekst — dan clustert hij niet met anderen, en dat is eerlijker dan hem bij een
    willekeurig ander gat te schuiven."""
    lab = (rij.get("capability") or "").strip().lower()
    return lab or ("item:" + (rij.get("item_text") or "").strip().lower()[:80])


def clusters(data_dir: str, reason: str = MISSING_CAPABILITY) -> list[dict]:
    """De gaten geclusterd per capaciteit, gerangschikt op hoeveel PROJECTEN elk blokkeerde.

    Frequentie telt in projecten, niet in records: tien records over hetzelfde project is één
    geblokkeerd project, geen tienvoudige urgentie. Bij gelijk aantal projecten wint het cluster met
    de meeste records, daarna het meest recente — zo staat bovenaan wat het vaakst écht in de weg zat.
    """
    per: dict[str, dict] = {}
    for rij in alle(data_dir):
        if reason and rij.get("reason") != reason:
            continue
        k = _sleutel(rij)
        c = per.setdefault(k, {"capability": (rij.get("capability") or "").strip() or "(geen label)",
                               "sleutel": k, "records": [], "rollen": {}, "projecten": set(),
                               "laatst": 0.0, "reason": rij.get("reason")})
        c["records"].append(rij)
        rol = rij.get("role") or "?"
        c["rollen"][rol] = c["rollen"].get(rol, 0) + 1
        if rij.get("project_id"):
            c["projecten"].add(rij["project_id"])
        c["laatst"] = max(c["laatst"], float(rij.get("ts") or 0))
    uit = []
    for c in per.values():
        uit.append({**c, "projecten": sorted(c["projecten"]),
                    "n_projecten": len(c["projecten"]), "n_records": len(c["records"]),
                    "rollen": sorted(c["rollen"].items(), key=lambda kv: (-kv[1], kv[0]))})
    uit.sort(key=lambda c: (-c["n_projecten"], -c["n_records"], -c["laatst"]))
    return uit


def probleemstelling(cluster: dict) -> str:
    """Het cluster als PROBLEEMSTELLING, niet als code-spec. Codie draft hiermee, een mens beoordeelt,
    en pas daarna schrijft iemand code — de poort zit op dat pad, niet op het routeren zelf.

    Bewust geen oplossing, geen API-keuze, geen architectuur: dat is precies het denkwerk dat je
    niet wilt automatiseren. Wat hier staat is wat er gebeurde en hoe vaak."""
    rollen = ", ".join(f"{r.split('__')[-1]} ({n}x)" for r, n in cluster["rollen"][:4])
    voorbeelden = "; ".join(f"'{(r.get('item_text') or '')[:90]}'" for r in cluster["records"][:3])
    n_p = cluster["n_projecten"]
    return (f"{cluster['capability']} — blokkeerde {n_p} project"
            f"{'en' if n_p != 1 else ''} bij {rollen}. "
            f"Voorbeelden: {voorbeelden}. "
            f"Wat er nu gebeurt: het werk loopt vast en wacht op een mens. "
            f"Wat een oplossing zou moeten opleveren: dat een rol dit zelf kan uitvoeren.")
