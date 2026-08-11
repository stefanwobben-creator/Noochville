"""Citeerbare velden — wat een rapport uit een skill-resultaat mág aanhalen, compact en volledig.

De missie-critic verklaarde "Compliance Score: 88/100" ongegrond terwijl `claims_check` letterlijk
`score: 88` teruggaf. Niet omdat de synthese het cijfer verstopte, maar omdat het bewijsvenster van
de critic dit was:

    bewijs = "\\n".join(str(d)[:600] for d in (deliverables or [])[:8])

Eerste acht records, 600 tekens elk. Met een stapel duplicaten waren dat acht keer dezelfde twee
bevindingen, en stond `88` er domweg niet in. Een grondings-toets die het bewijs niet ziet, toetst
niet — hij gokt, en gokt streng.

Deze laag maakt van een skill-resultaat een platte lijst `(skill, veld, waarde)`. Een cijfer, een
stoplicht, een categorie: elk apart aanhaalbaar, elk met zijn herkomst erbij. Dat is precies de
"reference, don't copy"-regel toegepast op de prompt — het rapport hoeft een getal niet in proza te
laten overleven, het kan het citeren.

Twee dingen die hier bewust NIET gebeuren:

  1. **Geen stille begrenzing.** `[:8]` en `[:600]` waren onzichtbaar; wie het bewijs las, wist niet
     dat hij een fractie zag. Begrenzen mag (een project kan ooit veel unieke deliverables hebben),
     maar dan op tekens, met een regel eronder die zegt hoeveel er afviel. Zelfde regel als bij het
     thinking-budget, het afgekapte critic-antwoord en de cap-verlaging: nooit stil.
  2. **Geen selectie op "belangrijk".** Welk veld ertoe doet weet deze laag niet. Hij filtert alleen
     run-administratie weg (weeknummers, vlaggen, tellers) — dezelfde grens als
     `Inhabitant._classify_result`, en met dezelfde reden: een allowlist van gezegende sleutelnamen
     is stille koppeling.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.citeerbaar")

_MAX_WAARDE = 240                                           # per waarde; langer wordt afgekapt mét markering


# Boekhouding van de RUN, en niets meer.
#
# Eerst leende deze laag `inhabitant._META_KEYS` — "reference, don't copy". Dat was verkeerd
# toegepast: die regel gaat over hetzelfde feit op één plek, en dit zijn twee VERSCHILLENDE vragen.
# `_classify_result` vraagt "draagt dit resultaat inhoud?" en mag `term`, `query` en `bron` negeren,
# want een skill die alleen zijn invoer terugkaatst heeft niets opgeleverd. Deze laag vraagt "wat
# mag een rapport hieruit aanhalen?" — en dáár is `term` juist de bevinding.
#
# Gemeten gevolg van de verwisseling: `bevindingen[0].term = planet-safe / planet-friendly /
# planet-loving` viel uit het bewijsvenster terwijl het rapport die termenlijst wél citeerde. Precies
# het gat dat deze module moest dichten, opnieuw gemaakt door zijn eigen filter.
_RUN_ADMIN = frozenset({
    "ok", "error", "status", "skipped", "escalate", "headsup", "refuse",
    "week", "at", "ts", "datum", "day", "maand", "versie", "version", "id",
    "project_id", "role_id", "vraag_id", "force", "estimated",
})


def _meta_keys() -> frozenset:
    return _RUN_ADMIN


def _plat(waarde, prefix: str = "", meta: frozenset | None = None) -> list[tuple[str, str]]:
    """Maak van een geneste structuur een lijst (pad, waarde-als-tekst)."""
    meta = _meta_keys() if meta is None else meta
    uit: list[tuple[str, str]] = []
    if isinstance(waarde, dict):
        for k, v in waarde.items():
            k = str(k)
            if k.startswith("_") or k in meta:
                continue
            uit.extend(_plat(v, f"{prefix}.{k}" if prefix else k, meta))
    elif isinstance(waarde, (list, tuple)):
        for i, v in enumerate(waarde):
            uit.extend(_plat(v, f"{prefix}[{i}]" if prefix else f"[{i}]", meta))
    elif waarde is None or waarde == "":
        pass
    else:
        tekst = str(waarde).strip()
        if tekst:
            uit.append((prefix, tekst[:_MAX_WAARDE] + ("…" if len(tekst) > _MAX_WAARDE else "")))
    return uit


def velden_van(skill: str, content) -> list[tuple[str, str, str]]:
    """(skill, veld, waarde) voor één skill-resultaat. Lege lijst als er niets aanhaalbaars in zit."""
    return [(skill or "?", pad, w) for pad, w in _plat(content) if pad]


def bewijsblok(deliverables, content_for, *, max_chars: int = 12000,
               bron: str = "bewijs") -> str:
    """Het citeerbare bewijs van álle meegegeven deliverables, als platte regels.

    `content_for(rid)` haalt de volledige skill-uitvoer op (de sidecar). Valt die weg, dan blijft de
    `summary` over — beter een samenvatting dan niets, en het is zichtbaar welke van de twee je las.

    Begrenst op TEKENS, niet op records, en zegt het als er iets afvalt."""
    regels: list[str] = []
    for r in (deliverables or []):
        rid = r.get("id")
        skill = str(r.get("skill") or "?")
        inhoud = None
        try:
            inhoud = content_for(rid) if rid else None
        except Exception as e:                              # noqa: BLE001 — bewijs mag nooit crashen
            log.warning("citeerbaar: content van %s niet leesbaar: %s", rid, e)
        velden = velden_van(skill, inhoud) if inhoud is not None else []
        if velden:
            regels.extend(f"{s} | {veld} = {w}" for s, veld, w in velden)
        elif (r.get("summary") or "").strip():
            regels.append(f"{skill} | samenvatting = {str(r['summary']).strip()[:_MAX_WAARDE]}")
    if not regels:
        return ""
    tekst, weg = "", 0
    for i, regel in enumerate(regels):
        if len(tekst) + len(regel) + 1 <= max_chars:
            tekst += regel + "\n"
        else:
            weg = len(regels) - i
            break
    if weg:
        log.warning("CITEERBAAR_CAP: %d van %d bewijsregels vielen buiten %d tekens (%s) — het "
                    "bewijs is INCOMPLEET en dat staat ook in de prompt.", weg, len(regels),
                    max_chars, bron)
        tekst += (f"[LET OP: {weg} van de {len(regels)} bewijsregels vielen buiten het budget. Dit "
                  f"bewijs is onvolledig — noem iets niet ongegrond puur omdat het hier ontbreekt.]\n")
    return tekst.rstrip()
