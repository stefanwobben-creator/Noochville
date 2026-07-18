"""Opdrogen: rol-DNA-skills omzetten naar koppelingen op accountabilities.

Eindbeeld van de koppelingslaag: het rol-DNA is leeg en elk middel hangt aan de belofte die
het dient. Deze module stelt per rol voor welke DNA-skill naar welke accountability verhuist
(beste tekst-match), en kan die koppelingen aanmaken.

**Het VERWIJDEREN uit het rol-DNA doet dit commando NIET.** Dat is een mandaat-wijziging en
loopt via de normale governance-ronde (`remove_skills`). Zo blijft de scheiding intact: de
belofte beweegt op governance-snelheid, het middel op operationele snelheid — en er is geen
sluiproute die het DNA buiten governance om leegmaakt.

De dubbeling `keywords_everywhere` (librarian én billy) is de acceptatie-case: één middel,
twee links, DNA op dat punt leeg — na de governance-ronde.
"""
from __future__ import annotations

import logging

from nooch_village import acc_ids, skill_labels, skill_meta
from nooch_village.gap_classifier import _coverage, _skill_tokens, _tokenize

log = logging.getLogger("village.skills_naar_links")

# Onder ZWAK_DREMPEL is er geen zinnig verband; daarboven maar onder VOORSTEL_DREMPEL tonen we
# de match wél ("zwak") maar leggen we hem NIET automatisch: de mens kiest. Zo blijft de
# informatie zichtbaar zonder dat een blinde `apply` twijfelachtige koppelingen aanmaakt.
ZWAK_DREMPEL: float = 0.05
VOORSTEL_DREMPEL: float = 0.15


def _stammen(tokens) -> frozenset[str]:
    """Ruwe stam per token (eerste 6 tekens).

    Nederlandse verbuiging breekt exacte token-matching: 'beoordelen' vs 'beoordeelt',
    'woord' vs 'woorden'. Een volledige stemmer is hier overkill — dit is een VOORSTEL dat
    een mens leest, met de score erbij. Liever iets te ruim en zichtbaar dan te streng en stil.
    """
    return frozenset(t[:6] for t in tokens)


def _middel_signatuur(skill: str) -> frozenset[str]:
    """De woordwolk van een middel: zijn capability-id ÉN zijn mensentaal-label.

    Het id is Engels en technisch (`keywords_everywhere`), de accountability-tekst is
    Nederlands en functioneel ('zoekvolume bijhouden'). Die twee delen geen tokens. Het label
    uit `skill_labels` is precies de brug tussen beide werelden — dus dat is waar we op matchen.
    """
    return _stammen(_skill_tokens([skill]) | _tokenize(skill_labels.label(skill)))


def _beste_accountability(skill: str, defn) -> tuple[str, str, float]:
    """Welke belofte van deze rol past het best bij dit middel? (acc_id, tekst, score).

    Score = de fractie van de BELOFTE-woorden die het middel dekt. Die richting past bij de
    vraag die we stellen ('maakt dit middel deze belofte waar?'), niet andersom.
    """
    sig = _middel_signatuur(skill)
    best = ("", "", 0.0)
    for aid, tekst in acc_ids.pairs(defn):
        score = _coverage(_stammen(_tokenize(tekst)), sig)
        if score > best[2]:
            best = (aid, tekst, score)
    return best


def plan(records, ai) -> list[dict]:
    """Stel per rol voor welke DNA-skill naar welke accountability verhuist.

    Elk voorstel draagt een `status`:
      - "voorstel"    — een passende belofte gevonden;
      - "al gekoppeld" — de koppeling bestaat al (de echte run slaat hem over);
      - "geen match"   — geen belofte past; een mens moet kiezen, wij raden niet;
      - "domeinpoort"  — beslis-skill bij een rol zonder dat domein: NIET koppelen, dit hoort
                         een governance-gesprek te zijn (of de suggestie-variant).
    """
    out: list[dict] = []
    for rec in records:
        if getattr(rec, "archived", False):
            continue
        defn = rec.definition
        bestaand = {t.skill for t in (ai.links_for_role(rec.id) if ai is not None else [])}
        for skill in sorted(defn.skills or []):
            aid, tekst, score = _beste_accountability(skill, defn)
            mag, reden = skill_meta.koppelbaar(skill, rec)
            if not mag:
                status, aid, tekst = "domeinpoort", "", reden
            elif skill in bestaand:
                status = "al gekoppeld"
            elif not aid or score < ZWAK_DREMPEL:
                status, aid, tekst = "geen match", "", ""
            elif score < VOORSTEL_DREMPEL:
                status = "zwak"          # zichtbaar, maar niet automatisch koppelen
            else:
                status = "voorstel"
            out.append({
                "role": rec.id, "skill": skill, "label": skill_labels.label(skill),
                "acc_id": aid, "acc": tekst, "score": round(score, 3), "status": status,
            })
    return out


def voer_uit(records, ai, *, door: str = "skills_naar_links", kroniek=None) -> list[dict]:
    """Maak de voorgestelde koppelingen aan. Idempotent — een tweede run legt niets nieuws.

    Raakt het rol-DNA NOOIT aan: opdrogen daarvan loopt via governance (`remove_skills`).
    """
    gelegd = []
    for r in plan(records, ai):
        if r["status"] != "voorstel":
            continue
        link = ai.add_link(r["role"], r["acc_id"], r["skill"], gelegd_door=door)
        if link is None:
            log.warning("koppeling %s → %s kon niet worden gelegd", r["skill"], r["role"])
            continue
        if kroniek is not None:
            kroniek.record(action="gelegd", role_id=r["role"], acc_id=r["acc_id"],
                           skill=r["skill"], door=door, reden="opdrogen (skills_naar_links)")
        gelegd.append(r)
    return gelegd


# ── Mensentaal-rapport ───────────────────────────────────────────────────────

_ICON = {"voorstel": "→", "al gekoppeld": "✓", "geen match": "?", "domeinpoort": "⛔",
         "zwak": "~"}


def rapport(rijen: list[dict], *, dry_run: bool = True) -> str:
    if not rijen:
        return "Geen DNA-skills gevonden om te verplaatsen."
    regels = [("DROOGLOOP (dry-run) — er is niets gewijzigd:" if dry_run
               else "KOPPELINGEN GELEGD:"), ""]
    per_rol: dict[str, list[dict]] = {}
    for r in rijen:
        per_rol.setdefault(r["role"], []).append(r)
    for rol, items in per_rol.items():
        regels.append(f"  {rol}")
        for r in items:
            icon = _ICON.get(r["status"], "·")
            if r["status"] == "voorstel":
                regels.append(f"    {icon} {r['label']} ({r['skill']}) "
                              f"→ '{r['acc']}' [{r['score']}]")
            elif r["status"] == "al gekoppeld":
                regels.append(f"    {icon} {r['label']} ({r['skill']}) — al gekoppeld")
            elif r["status"] == "zwak":
                regels.append(f"    {icon} {r['label']} ({r['skill']}) "
                              f"~ '{r['acc']}' [{r['score']}] — zwakke match, niet automatisch "
                              f"gekoppeld; kies zelf")
            elif r["status"] == "domeinpoort":
                regels.append(f"    {icon} {r['label']} ({r['skill']}) — {r['acc']}")
            else:
                regels.append(f"    {icon} {r['label']} ({r['skill']}) — geen passende "
                              f"accountability; kies er zelf een")
        regels.append("")
    n = sum(1 for r in rijen if r["status"] == "voorstel")
    regels.append(f"{n} koppeling(en) {'voor te stellen' if dry_run else 'gelegd'}.")
    regels.append("Het rol-DNA is NIET aangeraakt: verwijderen daaruit loopt via de normale "
                  "governance-ronde (remove_skills).")
    return "\n".join(regels)
