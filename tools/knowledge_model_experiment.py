"""Ontologie-stresstest voor het kennismodel (signaal / bevinding / kader).

GEEN dynamiek-simulatie (dat zou het model tegen zijn eigen aannames testen), maar een
confrontatie met ECHTE data (de 196 notesstore-kaartjes) plus ~100 bewust moeilijke synthetische
claims. We meten waar het schema WRINGT: hoeveel claims passen niet netjes, vallen in twee vakken,
of breken het model. Dat percentage is de objectieve maat of de indeling deugt.

Doel van het model: kansen en gaten RUIKEN (gap-detectie), licht in onderhoud, onbreekbaar.

Run: PYTHONPATH=/tmp/shim python3 tools/knowledge_model_experiment.py
"""
from __future__ import annotations
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Het voorgestelde model: drie TYPES (rol van de claim) ─────────────────────
# SIGNAAL   = trend/opinie/nieuws: roept een vraag op (zegt iets over de cultuur/aandacht)
# BEVINDING = empirie: beantwoordt een vraag (zegt iets over de wereld)
# KADER     = regelgeving/norm: bindend, niet waar/onwaar
TYPES = ("signaal", "bevinding", "kader")

_KADER = re.compile(r"\b(directive|richtlijn|wet|wetgeving|verplicht|mag niet|verboden|"
                    r"certific|iso\b|green claims|reglement|norm|compliance|aansprakelijk)\b", re.I)
_SIGNAAL = re.compile(r"\b(zoekvolume|trend|stijg|daal|populair|viral|sentiment|opinie|"
                      r"mensen (vinden|zeggen|denken|willen)|reddit|nieuws|artikel|"
                      r"waitlist|survey|enqu|respondent|geïnteresseerd|interesse|"
                      r"volgers|linkedin|piek|aandacht)\b", re.I)
_BEVINDING = re.compile(r"\b(studie|onderzoek|meta-?analyse|rct|gerandomiseerd|cohort|"
                        r"data toont|gemeten|meet|correlat|proefpersonen|n=|"
                        r"peer-?review|wetenschappelijk|aangetoond|experiment)\b", re.I)
# Hard te plaatsen: normatief/waardeoordeel, definitie, voorspelling, onbewijsbaar/absurd
_NORMATIEF = re.compile(r"\b(zou moeten|hoort|beter|slechter|bewuster|goed|slecht|moreel|"
                        r"verantwoord|deugt|waardevol)\b", re.I)
_DEFINITIE = re.compile(r"\b(is per definitie|betekent|wordt gedefinieerd|definieert|"
                        r"is een soort|valt onder)\b", re.I)
_VOORSPELLING = re.compile(r"\b(zal|gaat .*(worden|stijgen|dalen)|voorspel|tegen 20\d\d|"
                           r"binnen \d+ jaar)\b", re.I)


def classify(text: str, evidence_type: str | None) -> dict:
    """Eerste-pas classificatie (heuristiek, geen LLM). Geeft de gekozen types + vlaggen.
    De WAARDE zit in de randgevallen die hieruit komen, niet in een nauwkeurigheidscijfer."""
    t = text or ""
    hits = set()
    if _KADER.search(t):
        hits.add("kader")
    if _SIGNAAL.search(t):
        hits.add("signaal")
    if _BEVINDING.search(t):
        hits.add("bevinding")
    # evidence_type (al in de data) als sterk hulpsignaal
    if evidence_type == "measured":
        hits.add("bevinding")
    elif evidence_type == "claimed":
        hits.add("signaal")
    # 'reported' is bewust GEEN type: het zegt 'een bron meldt het', niet wélke soort → ambigu
    flags = {
        "normatief": bool(_NORMATIEF.search(t)),
        "definitie": bool(_DEFINITIE.search(t)),
        "voorspelling": bool(_VOORSPELLING.search(t)),
    }
    if not hits:
        verdict = "ONBESLIST"          # past in geen enkel vak → mogelijke breuk
    elif len(hits) > 1:
        verdict = "AMBIGU"             # past in twee vakken → naad onscherp
    else:
        verdict = next(iter(hits))
    return {"types": sorted(hits), "verdict": verdict, "flags": flags}


# ── ~100 synthetische claims, bewust op de moeilijke randen ───────────────────
SYNTH = [
    # — heldere signalen —
    ("Het zoekvolume rond 'microplastics in schoenen' is dit kwartaal met 40% gestegen.", "reported"),
    ("Op Reddit r/sustainability klagen mensen dat veganleer-sneakers snel slijten.", "claimed"),
    ("Een opiniestuk in NRC stelt dat 'duurzaam' een leeg marketingwoord is geworden.", "claimed"),
    ("Google Trends laat een piek zien voor 'plasticvrije schoenen' rond Earth Day.", "reported"),
    ("Influencers noemen hennep steeds vaker als materiaal van de toekomst.", "reported"),
    ("De interesse voor tweedehands sneakers groeit volgens marktrapporten.", "reported"),
    ("Veel waitlisters zeggen dat ze wachten op een hardloopmodel.", "reported"),
    ("Sentiment over Nooch op social is overwegend positief maar klein in volume.", "reported"),
    # — heldere bevindingen —
    ("Een meta-analyse toont dat hennepvezel 30% minder water gebruikt dan katoen.", "measured"),
    ("RCT: proefpersonen met biobased zolen rapporteerden gelijke demping (n=120).", "measured"),
    ("Levenscyclusanalyse meet 2,1 kg CO2 per paar voor het huidige model.", "measured"),
    ("Cohortdata laat correlatie zien tussen prijs en retourpercentage.", "measured"),
    ("Bodemstudie meet tragere afbraak van PU dan van natuurlijk rubber.", "measured"),
    # — heldere kaders —
    ("De EU Green Claims Directive verplicht onderbouwing van elke milieuclaim.", None),
    ("Volgens de richtlijn mag 'biologisch afbreekbaar' niet zonder testnorm.", None),
    ("ISO 14021 stelt eisen aan zelfverklaarde milieuclaims.", None),
    ("De wet verbiedt het woord 'klimaatneutraal' zonder compensatiebewijs.", None),
    # — jouw voorbeelden: bewust lastig —
    ("Noochies kun je veilig begraven in je tuin.", "claimed"),
    ("Nooch is vegan.", "claimed"),
    ("Mensen die vegan zijn, zijn bewuster van zo'n beetje alles.", "claimed"),
    # — normatief / waardeoordeel (geen van de drie?) —
    ("Bedrijven zouden nooit mogen adverteren met halve waarheden.", "claimed"),
    ("Echte duurzaamheid betekent minder produceren, niet groener produceren.", "claimed"),
    ("Het is moreel beter om on-demand te produceren dan op voorraad.", "claimed"),
    ("Schoenen horen gemaakt te zijn om gerepareerd te worden.", "claimed"),
    # — definitie / tautologie —
    ("Vegan materiaal betekent de afwezigheid van dierlijke grondstoffen.", "claimed"),
    ("Een 'Noochie' is per definitie een drager van een paar Nooch-schoenen.", "claimed"),
    ("Biobased betekent dat de grondstof uit hernieuwbare bron komt.", "claimed"),
    # — voorspelling —
    ("Tegen 2030 zal veganleer goedkoper zijn dan dierlijk leer.", "claimed"),
    ("De vraag naar plasticvrije schoenen gaat de komende jaren stijgen.", "claimed"),
    # — mengvormen (signaal + bevinding, of feit + norm) —
    ("Zoekvolume stijgt (signaal) terwijl studies de schade van microplastics bevestigen.", "reported"),
    ("Omdat de richtlijn onderbouwing eist, moeten we onze CO2-claim laten meten.", None),
    ("Klanten vragen om recyclebaarheid, maar er is nog geen meetbaar bewijs dat het kan.", "reported"),
    # — onbewijsbaar / absurd / grens —
    ("Schoenen onthouden de stappen van hun drager.", "claimed"),
    ("Een goed paar schoenen brengt geluk.", "claimed"),
    ("Nooch maakt de wereld meetbaar mooier.", "claimed"),
]
# vul aan tot ~100 met variaties op de drie assen
_extra_signaal = [f"Zoekterm '{w}' wint dit seizoen aan populariteit."
                  for w in ("kurk sneakers", "algenschuim", "ananasleer", "appelleer",
                            "bananenvezel", "mycelium schoenen", "tweedehands hardloopschoenen",
                            "reparatieservice schoenen", "schoenen zonder lijm", "circulaire veters")]
_extra_bevinding = [f"Onderzoek meet dat {w} de CO2-voetafdruk meetbaar verlaagt."
                    for w in ("mycelium", "kurk", "gerecycled rubber", "hennep", "vlas",
                              "algenschuim", "biokatoen", "ananasvezel", "kokosvezel", "wol")]
_extra_kader = [f"Een norm vereist bewijs voordat je '{w}' op de verpakking zet."
                for w in ("composteerbaar", "klimaatneutraal", "100% natuurlijk", "gifvrij",
                          "oceaanplastic", "CO2-negatief", "vegan-gecertificeerd",
                          "cruelty-free", "fair trade", "lokaal geproduceerd")]
_extra_normatief = [f"Een merk hoort {w} te zijn." for w in
                    ("eerlijk", "transparant", "geduldig", "speels", "rebels",
                     "zuinig", "gul", "moedig", "nederig", "consistent")]
SYNTH += [(s, "reported") for s in _extra_signaal]
SYNTH += [(s, "measured") for s in _extra_bevinding]
SYNTH += [(s, None) for s in _extra_kader]
SYNTH += [(s, "claimed") for s in _extra_normatief]


def run():
    from nooch_village.notes_store import NotesStore
    ns = NotesStore(os.path.join(os.path.dirname(__file__), "..", "data", "notes.json"))
    real = [(c.claim or "", getattr(getattr(c, "evidence_type", None), "value", None))
            for c in ns.all()]
    synth = SYNTH

    def analyse(rows, label):
        res = [classify(t, et) for t, et in rows]
        verdicts = Counter(r["verdict"] for r in res)
        norm = sum(1 for r in res if r["flags"]["normatief"])
        defi = sum(1 for r in res if r["flags"]["definitie"])
        voor = sum(1 for r in res if r["flags"]["voorspelling"])
        n = len(rows)
        print(f"\n=== {label} (n={n}) ===")
        for v in ("signaal", "bevinding", "kader", "AMBIGU", "ONBESLIST"):
            c = verdicts.get(v, 0)
            print(f"  {v:10} {c:4}  ({100*c/n:.0f}%)")
        wring = verdicts.get("AMBIGU", 0) + verdicts.get("ONBESLIST", 0)
        print(f"  --> WRINGT (ambigu+onbeslist): {wring}/{n} = {100*wring/n:.0f}%")
        print(f"  flags: normatief={norm}, definitie={defi}, voorspelling={voor} "
              f"(deze 3 passen in GEEN van de drie types als 'feit/signaal')")
        return res

    rr = analyse(real, "ECHTE kaartjes (notesstore)")
    sr = analyse(synth, "SYNTHETISCHE claims")

    # toon de breekgevallen uit de synthetische set (de echte ontologie-test)
    print("\n=== BREEKGEVALLEN (synthetisch): ONBESLIST of normatief/definitie ===")
    for (t, et), r in zip(synth, sr):
        if r["verdict"] == "ONBESLIST" or r["flags"]["normatief"] or r["flags"]["definitie"]:
            tag = ("ONBESLIST" if r["verdict"] == "ONBESLIST" else
                   ",".join(k for k, v in r["flags"].items() if v))
            print(f"  [{tag}] {t[:75]}")

    # gap-detectie-demo: signalen zonder bevinding = onderzoeksgaten/kansen
    sig = sum(1 for r in sr if r["verdict"] == "signaal")
    bev = sum(1 for r in sr if r["verdict"] == "bevinding")
    print(f"\n=== GAP-SIGNAAL (synthetisch): {sig} signalen vs {bev} bevindingen ===")
    print("  In het echte systeem: een signaal zonder gelinkte bevinding = een kans/gat "
          "(satelliet die naar het centrum getrokken moet worden).")


if __name__ == "__main__":
    run()
