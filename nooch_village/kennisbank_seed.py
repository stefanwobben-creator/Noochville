"""Eerste vulling van de kennisbank — de echte content uit het prototype (nooch-kb).

Idempotent en dry-run-eerst:

    python -m nooch_village.kennisbank_seed             # dry-run: toont wat er zou gebeuren
    python -m nooch_village.kennisbank_seed --apply     # schrijft echt

Dedup: atomen op genormaliseerde claim-tekst tegen ALLE bestaande kaartjes in notes.json;
inzichten op titel tegen kennisbank.json. Bestaand → overslaan, nooit overschrijven.

Bewuste afwijking van het prototype: het metric-inzicht ("Waar we op ranken in Google")
wordt NIET geseed — een metric is een append-only reeks in MetricStore (fase 4-koppeling),
geen hardgecodeerde regel tekst.
"""
from __future__ import annotations

import argparse
import re

from nooch_village.insight import Insight
from nooch_village.kennisbank import KennisbankStore, load_atoms
from nooch_village.notes_store import NotesStore


def _norm_claim(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


# key → (claim, bron, provenance)
_ATOMS: dict[str, tuple[str, str, str]] = {
    # de losse pool (koppelbare kaarten)
    "pla":         ("PLA/TENEC composteert 100% onder industriële omstandigheden.", "WUR-rapport", "peer_reviewed"),
    "mylo":        ("Mylo mycelium-leer: 90% afbreekbaar in 6 maanden (TÜV).", "fashiontheoryco", "media"),
    "ecolabel":    ("EU Ecolabel koppelt textiel aan de circulaire economie.", "europarl.europa.eu", "expert_opinion"),
    "built":       ("BUILT haalt $2M op voor \"natural movement\" footwear (India).", "entrackr", "media"),
    "cda":         ("Cellulosediacetaat breekt wisselend af (38-70%), sterk methode-afhankelijk.", "WUR-rapport", "peer_reviewed"),
    "eudr":        ("Commissie overweegt leer uit de EU-ontbossingswet te halen na lobby.", "opinieartikel", "media"),
    "veganplastic": ("Veel vegan-leer is nog PU-plastic met een eigen milieu-impact.", "materiaal-analyse", "expert_opinion"),
    "pricebench":  ("Vergelijkbare duurzame merken zitten rond €140.", "marktonderzoek", "expert_opinion"),
    "design":      ("48% van de niet-kopers noemt design als barrière #1.", "waitlist-survey", "survey"),
    "paidanyway":  ("Kopers betaalden tijdens de pre-order tóch de €199.", "onze shop-data", "internal_data"),
    "mec":         ("69% van de waitlisters zet het Mother Earth CEO-principe voorop.", "waitlist-survey", "survey"),
    "abandon":     ("Winkelwagen-verlaters nemen toe na ~6 weken wachten.", "onze shop-data", "internal_data"),
    # de al-gelinkte noten per inzicht
    "edge_wait":   ("Mensen wachten maanden op een pre-order en kopen tóch.", "onze shop-data", "internal_data"),
    "edge_crocs":  ("Crocs claimt 25% \"bio-circular\", sommige paren mogelijk 0%.", "AP News", "media"),
    "edge_soleic": ("Soleic: microplasticvrij PU, direct bruikbaar in zolen.", "renewable-carbon.eu", "media"),
    "edge_zool":   ("Onze eigen zool (natuurrubber) breekt maar 15,6% af in 236 dagen.", "WUR-rapport", "peer_reviewed"),
    "bel_lijm":    ("Lijm ST6521: composteert ≥90% in 90 dagen (EN 13432).", "WUR / fabrikant", "certificate"),
    "bel_zool":    ("Natuurrubber zool: 15,6% in 236 dagen. Het knelpunt.", "WUR-rapport", "peer_reviewed"),
    "bel_rest":    ("Nog 21 onderdelen (vamp, lining, veters...) niet onderzocht.", "nog geen bron", "unknown"),
    "leer_earthsight": ("Vier losse onderzoeken koppelen EU-leer aan illegale ontbossing.", "Earthsight", "advocacy"),
    "leer_amazone": ("Veeteelt is grootste oorzaak van Amazone-ontbossing.", "breed gerapporteerd", "media"),
    "leer_90":     ("\"90% looierij-arbeiders sterft voor 50e\" — geen primaire bron.", "opinieartikel", "media"),
    "leer_karkas": ("Leer is <5% van de karkaswaarde; \"maakt veeteelt winstgevend\" is betwist.", "landbouweconomie", "expert_opinion"),
    "prijs_51":    ("51% van de waitlisters wil de prijs van €199 naar €150.", "waitlist-survey", "survey"),
    "prijs_idealist": ("De Idealist: betaalbereidheid €100-129, onder de €149.", "waitlist-survey", "survey"),
    "prijs_vw":    ("De Twijfelaar: Van Westendorp optimum €120.", "waitlist-survey", "survey"),
}

# title, why, reframe, falsifier, caveat, subject, evidence [(atom_key, stance)]
_INSIGHTS: list[dict] = [
    {"title": "Volledig plasticvrij zijn is onze edge",
     "why": "Mensen wachten maanden op een pre-order en kopen tóch, terwijl grote merken bij halve maatregelen blijven.",
     "reframe": "Misschien is plasticvrij de verkeerde maatstaf, en wint juist hoe lang een schoen meegaat.",
     "falsifier": "Een labtest die \"100% plasticvrij\" onderuit haalt, of een groot merk dat wél een echt plasticvrije schoen op schaal levert.",
     "caveat": "", "subject": "duurzame-schoenen",
     "evidence": [("edge_wait", "support"), ("edge_crocs", "support"),
                  ("edge_soleic", "support"), ("edge_zool", "counter")]},
    {"title": "Kan de schoen 100% duurzaam & vegan?",
     "why": "Van de 23 onderdelen is er pas één hard bewezen. De zool is het knelpunt.",
     "reframe": "Misschien hoeft niet élk onderdeeltje perfect, zolang de schoen als geheel terug de kringloop in kan.",
     "falsifier": "Een zool-materiaal dat wél snel en volledig afbreekt, of bewijs dat de huidige zool het toch haalt.",
     "caveat": "De zwakste schakel telt: zolang de zool zwak is, blijft de hele belofte onbewezen.",
     "subject": "outsole",
     "evidence": [("bel_lijm", "support"), ("bel_zool", "counter"), ("bel_rest", "counter")]},
    {"title": "Leer is een probleem voor de sector",
     "why": "Sterk op het milieu-verhaal, maar veel van de rest komt uit één hoek.",
     "reframe": "Leer is een efficiënt bijproduct; het verbieden verplaatst impact misschien juist naar plastic.",
     "falsifier": "Onafhankelijk bewijs dat vegan-alternatieven een grotere impact hebben dan bijproduct-leer.",
     "caveat": "Het cijfer \"90% van looierij-arbeiders sterft jong\" heeft geen bron. Niet gebruiken tot het geverifieerd is.",
     "subject": "leer",
     "evidence": [("leer_earthsight", "support"), ("leer_amazone", "support"),
                  ("leer_90", "support"), ("leer_karkas", "counter")]},
    {"title": "Prijs blokkeert onze kern-doelgroep",
     "why": "Meerdere signalen, maar allemaal uit dezelfde survey.",
     "reframe": "Misschien is prijs niet de drempel, maar het ontwerp (mensen willen de schoen eerst mooi vinden).",
     "falsifier": "Een echte test: prijs naar €150 en kijken of de conversie meebeweegt.",
     "caveat": "", "subject": "prijs",
     "evidence": [("prijs_51", "support"), ("prijs_idealist", "support"), ("prijs_vw", "support")]},
    {"title": "Wachttijd is een feature, geen kost",
     "why": "Een mooi idee, maar het steunt nog op één observatie.",
     "reframe": "Wachttijd is misschien gewoon een kost die we mooi inpakken; verkort hem en we verkopen meer.",
     "falsifier": "Cijfers die laten zien dat een kortere wachttijd juist meer verkoopt.",
     "caveat": "", "subject": "vraag",
     "evidence": [("edge_wait", "support"), ("abandon", "counter")]},
]


def seed(data_dir: str = "data", apply: bool = False) -> list[str]:
    """Geeft een regel-per-handeling rapport terug; schrijft alleen bij apply=True."""
    report: list[str] = []
    atoms = load_atoms(data_dir)
    bestaand_norm = {_norm_claim(a.get("claim") or ""): aid for aid, a in atoms.items()}
    notes = NotesStore(f"{data_dir}/notes.json") if apply else None

    key_to_id: dict[str, str] = {}
    for key, (claim, bron, prov) in _ATOMS.items():
        n = _norm_claim(claim)
        if n in bestaand_norm:
            key_to_id[key] = bestaand_norm[n]
            report.append(f"= atoom bestaat al: {claim[:60]}…  (id {bestaand_norm[n]})")
            continue
        aid = f"kbseed_{key}"
        key_to_id[key] = aid
        report.append(f"+ atoom {aid} [{prov}] {claim[:60]}… (bron: {bron})")
        if apply and notes is not None:
            notes.add(Insight(id=aid, claim=claim, source=bron, provenance=prov))

    kb = KennisbankStore(f"{data_dir}/kennisbank.json")
    bestaande_titels = {i["title"] for i in kb.all()}
    for spec in _INSIGHTS:
        if spec["title"] in bestaande_titels:
            report.append(f"= inzicht bestaat al: {spec['title']}")
            continue
        report.append(f"+ inzicht \"{spec['title']}\" ({spec['subject']}, "
                      f"{len(spec['evidence'])} links)")
        if apply:
            iid = kb.add(spec["title"], why=spec["why"], reframe=spec["reframe"],
                         falsifier=spec["falsifier"], caveat=spec["caveat"],
                         subject=spec["subject"], by="seed")
            for key, stance in spec["evidence"]:
                kb.link(iid, key_to_id[key], stance, by="seed")
    return report


# key → onderwerp uit kennisbank_intake.SUBJECTS (fase 2: seed-atomen alsnog op hun hub,
# zodat het ongesorteerd-bakje en de cluster-oprit op echte data werken).
_SUBJECT_TAGS: dict[str, str] = {
    "pla": "materiaal", "mylo": "vegan-leer", "ecolabel": "regelgeving",
    "built": "concurrentie", "cda": "materiaal", "eudr": "regelgeving",
    "veganplastic": "vegan-leer", "pricebench": "prijs", "design": "segment",
    "paidanyway": "vraag", "mec": "segment", "abandon": "vraag",
    "edge_wait": "vraag", "edge_crocs": "concurrentie", "edge_soleic": "materiaal",
    "edge_zool": "outsole", "bel_lijm": "materiaal", "bel_zool": "outsole",
    "bel_rest": "duurzame-schoenen", "leer_earthsight": "leer", "leer_amazone": "leer",
    "leer_90": "ethiek", "leer_karkas": "leer",
    "prijs_51": "prijs", "prijs_idealist": "prijs", "prijs_vw": "prijs",
}


def tag_subjects(data_dir: str = "data", apply: bool = False) -> list[str]:
    """Idempotente migratie: geef de fase-1 seed-atomen hun onderwerp als tags[0].
    Alleen kaarten die het onderwerp nog niet dragen worden geraakt."""
    from nooch_village.kennisbank_intake import SUBJECTS
    report: list[str] = []
    notes = NotesStore(f"{data_dir}/notes.json")
    for key, subject in _SUBJECT_TAGS.items():
        assert subject in SUBJECTS, f"onbekend onderwerp {subject!r} voor {key}"
        kaart = notes.get(f"kbseed_{key}")
        if kaart is None:
            report.append(f"- kbseed_{key}: niet aanwezig (seed nog niet toegepast?)")
            continue
        if subject in kaart.tags:
            report.append(f"= kbseed_{key}: draagt '{subject}' al")
            continue
        report.append(f"+ kbseed_{key}: tag '{subject}'")
        if apply:
            notes.add_tags(kaart.id, [subject])
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="echt schrijven (default: dry-run)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--tag-subjects", action="store_true",
                   help="alleen de subject-tag-migratie op de seed-atomen draaien")
    args = p.parse_args()
    regels = (tag_subjects(args.data_dir, apply=args.apply) if args.tag_subjects
              else seed(args.data_dir, apply=args.apply))
    for line in regels:
        print(line)
    if not args.apply:
        print("\n(dry-run — niets geschreven; draai met --apply om te schrijven)")


if __name__ == "__main__":
    main()
