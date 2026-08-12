"""Rol-beoordeling van radar-signalen: de founder ziet voorstellen, geen signalen.

De radar dumpte rauwe signalen op de founder om te triëren (keep/dismiss/watch). Dat is hetzelfde
menu-model dat we voor compliance-claims hebben afgeschaft: "rising Xero Shoes" is geen voorstel, en
beoordelen of iets het volgen waard is, is rolwerk.

De omkering: radar surfacet → het signaal gaat naar de rol die er de skills voor heeft → die rol
legt het zelf weg met een gegronde reden, óf brengt een concreet voorstel bij de founder.

**Orkestratie, geen nieuwe capaciteit.** De beoordeling hieronder is deterministisch; het voorstel
zelf komt uit `onderzoekspas.draai` — dezelfde pipeline, dezelfde critic met gegrond-as, dezelfde
degradatie naar eerlijke bevinding, dezelfde `voorstel_oordeel`-kaart.

## De twee dismiss-assen, en hun ongelijke risico

  `strijdig`   het signaal botst met een grondwet-principe (bijenwas → 'geen leer': dierlijk).
               Herleidbaar via het Lexicon: een `avoid`-concept draagt het principe dat het schendt,
               dus de reden CITEERT de grondwet in plaats van naar een lijst te wijzen.
               Risico laag: een vegan-strijdigheid is bijna zeker terecht.

  `off_strategie`  het signaal raakt geen enkel thema uit `STRATEGIE_THEMAS`.
               Risico HOOG: dit kan een goed, nieuw signaal begraven dat nog geen bestaand thema
               raakt — een materiaal dat we nog niet gebruiken maar wél zouden moeten overwegen.

Die ongelijkheid stuurt de audit: `off_strategie` wordt zwaarder bemonsterd dan `strijdig`. Daar zit
de kans dat het filter iets wegwuift dat de founder had willen zien.

**De auditregel is niet-optioneel in code.** Elke dismiss schrijft er een; het percentage bepaalt
alleen wat er op het scherm komt. Anders is "de audit staat uit" één config-regel van de
stille-drop-ziekte verwijderd — en die hebben we deze week overal uitgeroeid.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

log = logging.getLogger("village.radar_beoordeling")

BESTAND = "radar_beoordelingen.jsonl"

DISMISS_STRIJDIG = "strijdig"
DISMISS_OFF_STRATEGIE = "off_strategie"
NAAR_VOORSTEL = "voorstel"

# Audit-percentage per dismiss-as.
#
# `strijdig` staat op 100 zolang de materiaal-classificatie nieuw is. Die as is niet meer
# regel-gebaseerd maar een CLASSIFICATIE, en dat is een bewuste afwijking van "nooit een model dat
# raadt": een woordenlijst kon `schapenwol` niet als wol herkennen, en dat is precies de vorm waarin
# materialen in signalen staan. De prijs van die afwijking is dat elke dismiss langs de founder gaat,
# tot hij er genoeg heeft gezien om te verlagen. Geen classificatie zonder controle.
AUDIT_PCT = {DISMISS_OFF_STRATEGIE: 40, DISMISS_STRIJDIG: 100}

# Op welke feeds de RELEVANTIE-as mag wegleggen.
#
# Gemeten op de 21 materiaalsignalen: 18 gingen door, 3 vielen af, en de as ving geen enkele echte
# strijdigheid. De reden is structureel — de feed is al materiaal-selectief, dus vrijwel elk signaal
# raakt "afbreekbaar & biobased" of "geen plastic". Een filter dat op zijn eigen invoerselectie
# meet, discrimineert niet.
#
# De score blijft wél meereizen als zwak secundair signaal (in `themas`), maar hij legt hier niets
# meer weg. Op feeds die niet vooraf op onderwerp geselecteerd zijn kan hij dat wel.
RELEVANTIE_DISMIST_OP = frozenset({"Competitor Watch", "Legal & Green Claims"})

# Materiaal-categorie → het grondwet-principe dat hij schendt. Deterministisch: de CLASSIFICATIE
# bepaalt de categorie, deze tabel bepaalt het principe. Zo blijft de dismiss-reden herleidbaar tot
# de grondwet ook als het materiaal zelf nergens in een lijst staat.
MATERIAAL_CATEGORIE = {
    "dierlijk": "geen leer",
    "plastic": "geen plastic",
    "niet_eu": "in europa geproduceerd",
}


def _tekst_van(signaal: dict) -> str:
    return " ".join(str(signaal.get(v) or "") for v in ("content", "rationale", "feed"))


def strijdig_met_grondwet(signaal: dict, lexicon=None) -> tuple[str, str, str] | None:
    """Botst het MATERIAAL in dit signaal met een grondwet-principe? → (materiaal, principe, waarom).

    Vervangt de lexicale match. Die kon `schapenwol` niet als wol herkennen — het lexicon kent 'wol',
    maar een samenstelling is één token, en dát is de normale vorm waarin een materiaal in een
    signaal staat. Gemeten: nul strijdig-dismisses over 21 materiaalsignalen terwijl er minstens
    één echte in zat, met een rationale die het nota bene aanprees als afbreekbaar alternatief.

    Nu een SMALLE classificatie: precies drie vragen, gesloten antwoordruimte, en de classificatie
    moet het materiaal noemen én uit de signaaltekst citeren. Kan hij dat niet, dan geen dismiss.

    Dit is een bewuste afwijking van "nooit een model dat raadt", en de prijs staat ernaast:
    `AUDIT_PCT[strijdig] = 100`. Elke dismiss langs de founder tot hij er genoeg heeft gezien.

    Fail-OPEN: geen classificatie, geen dismiss. Een as die stilletjes wegwuift is erger dan een as
    die niets doet — het eerste is onzichtbaar, het tweede staat gewoon in de wachtrij."""
    tekst = _tekst_van(signaal).strip()
    if not tekst:
        return None
    from nooch_village.llm import reason
    from nooch_village.llm_keuze import ladder_voor
    prompt = (
        "Je bent materiaalkundige bij Nooch (veganistische, plasticvrije schoenen uit Europa). "
        "Beantwoord over het MATERIAAL in dit signaal precies drie gesloten vragen. Beoordeel het "
        "materiaal zelf, niet of het onderwerp interessant is.\n\n"
        f"SIGNAAL:\n{tekst[:1200]}\n\n"
        "1. Is het materiaal van dierlijke oorsprong (wol, zijde, leer, bijenwas, caseïne, "
        "chitine uit schaaldieren, …)? → 'dierlijk'\n"
        "2. Is het een petrochemische kunststof (polyester, PU, PVC, nylon, PLA uit fossiele bron, "
        "…)? → 'plastic'\n"
        "3. Is het aantoonbaar NIET in Europa produceerbaar (palmolie, tropische gewassen, "
        "grondstoffen die alleen buiten Europa groeien)? → 'niet_eu'\n"
        "Geldt geen van drieën, of weet je het niet zeker → 'geen'.\n\n"
        "Bij twijfel kies je 'geen'. Een onterechte 'dierlijk' wuift echt onderzoek weg.\n"
        "Citeer LETTERLIJK het stuk uit het signaal waarop je oordeel steunt; kun je niets citeren, "
        "dan is het antwoord 'geen'.\n"
        'Antwoord UITSLUITEND met JSON: {"categorie":"dierlijk|plastic|niet_eu|geen",'
        '"materiaal":"...","citaat":"..."}')
    try:
        rauw = reason(prompt, call_site="materiaal_identiteit",
                      ladder=ladder_voor("materiaal_identiteit"), json_mode=True, max_tokens=400)
        data = json.loads(str(rauw)[str(rauw).find("{"):str(rauw).rfind("}") + 1]) if rauw else None
    except Exception as e:                               # noqa: BLE001 — fail-open
        log.warning("materiaal-classificatie faalde, geen dismiss: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    categorie = str(data.get("categorie") or "").strip().lower()
    principe = MATERIAAL_CATEGORIE.get(categorie)
    materiaal = str(data.get("materiaal") or "").strip()
    citaat = str(data.get("citaat") or "").strip()
    if not principe or not materiaal or not citaat:
        return None                                      # ongegrond = geen dismiss
    if citaat.lower() not in tekst.lower():
        # Het citaat moet ECHT in het signaal staan. Zonder deze controle is de grondslag een
        # bewering van het model over zichzelf — dezelfde fout als een verzonnen bron.
        log.info("materiaal-classificatie verworpen: citaat staat niet in het signaal (%s)",
                 citaat[:60])
        return None
    return materiaal, principe, f"{categorie}: \"{citaat[:160]}\""


def beoordeel(signaal: dict, lexicon=None) -> dict:
    """Wat moet er met dit signaal? → {besluit, as, principe, citaat, themas}.

    Volgorde is niet willekeurig: strijdigheid eerst. Een signaal dat 'geen leer' schendt kan
    prima op 'afbreekbaar & biobased' scoren — bijenwas doet dat — en zou dan als relevant
    doorgaan. De strijdigheid is de hardere uitspraak en gaat dus voor."""
    tekst = _tekst_van(signaal)
    botsing = strijdig_met_grondwet(signaal, lexicon)
    if botsing:
        materiaal, principe, waarom = botsing
        return {"besluit": DISMISS_STRIJDIG, "as": DISMISS_STRIJDIG, "principe": principe,
                "citaat": f"'{materiaal}' schendt het principe '{principe}' — {waarom}",
                "themas": []}
    try:
        from nooch_village.mission import strategie_relevantie
        score, themas = strategie_relevantie(tekst)
    except Exception as e:                               # noqa: BLE001 — fail-open: niet wegleggen
        log.warning("strategie-toets faalde, signaal blijft staan: %s", e)
        return {"besluit": NAAR_VOORSTEL, "as": "", "principe": "", "citaat": "", "themas": []}
    # De score reist altijd mee als zwak secundair signaal, maar legt alleen weg op feeds waar hij
    # discrimineert. Zie RELEVANTIE_DISMIST_OP.
    if str(signaal.get("feed") or "") not in RELEVANTIE_DISMIST_OP:
        return {"besluit": NAAR_VOORSTEL, "as": "", "principe": "", "citaat": "",
                "themas": list(themas)}
    if score < 1:
        return {"besluit": DISMISS_OFF_STRATEGIE, "as": DISMISS_OFF_STRATEGIE, "principe": "",
                "citaat": ("raakt geen enkel strategie-thema uit de grondwet (geen plastic, geen "
                           "leer, afbreekbaar & biobased, in Europa geproduceerd, op bestelling, "
                           "eerlijk werk & prijs, transparantie)"),
                "themas": []}
    return {"besluit": NAAR_VOORSTEL, "as": "", "principe": "", "citaat": "", "themas": list(themas)}


def in_audit(signaal_id: str, dismiss_as: str) -> bool:
    """Valt deze dismiss in de auditsteekproef?

    Hergebruikt de deterministische hash uit `founder_flow` — dezelfde dismiss valt altijd hetzelfde
    uit, dus geen loterij bij elke render. Het percentage verschilt per as omdat het risico verschilt:
    een `off_strategie`-dismiss kan een nieuw signaal begraven, een `strijdig`-dismiss bijna niet."""
    from nooch_village.founder_flow import in_auditsteekproef
    return in_auditsteekproef("dismiss_audit", f"{dismiss_as}:{signaal_id}",
                              AUDIT_PCT.get(dismiss_as, 25))


def leg_vast(data_dir: str, *, signaal: dict, oordeel: dict, rol: str,
             voorstel_id: str = "") -> dict:
    """Append-only vastleggen. ALTIJD, ook buiten de steekproef.

    De auditregel is niet-optioneel: het percentage bepaalt wat er op het scherm komt, niet wat er
    wordt bijgehouden. Zonder deze regel is 'de audit staat uit' één config-wijziging van een stille
    drop verwijderd."""
    sid = str(signaal.get("id") or "")
    rij = {"signaal": sid, "rol": rol, "besluit": oordeel.get("besluit"),
           "as": oordeel.get("as", ""), "principe": oordeel.get("principe", ""),
           "citaat": str(oordeel.get("citaat", ""))[:400],
           "themas": list(oordeel.get("themas") or []),
           "inhoud": str(signaal.get("content") or "")[:200],
           "bron": str(signaal.get("source") or ""),
           "audit": bool(oordeel.get("as") and in_audit(sid, oordeel["as"])),
           "voorstel": voorstel_id, "ts": time.time()}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, BESTAND), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rij, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("radar-beoordeling niet vastgelegd: %s", e)
    return rij


def alle(data_dir: str) -> list[dict]:
    uit = []
    try:
        with open(os.path.join(data_dir, BESTAND), encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if regel:
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue
    except FileNotFoundError:
        return []
    except OSError as e:
        log.warning("radar-beoordelingen onleesbaar: %s", e)
    return uit


def audit_wachtrij(data_dir: str) -> list[dict]:
    """De dismisses die de founder ter controle krijgt. Nieuwste eerst."""
    return sorted((r for r in alle(data_dir) if r.get("audit")),
                  key=lambda r: r.get("ts", 0), reverse=True)


# ── De router: welke rol beoordeelt dit signaal? ─────────────────────────────

def rol_voor(signaal: dict, records, registry=None) -> tuple[str, str]:
    """Wie hoort dit signaal te beoordelen? → (rol_id, waarom).

    Match op SKILL-eigenaarschap, niet op accountability. Dat was de geparkeerde router-vraag, en
    deze migratie heeft hem nodig: een concurrent-signaal hoort bij de rol die `competitor_news`
    bezit, niet bij de rol wiens accountability-tekst toevallig woorden deelt.

    Domein-match zou sterker zijn, maar `concurrent_scout` en `harry_hemp` houden er geen — alleen
    de librarian en compliance hebben domeinen. Dus skill eerst, domein als tiebreak zodra rollen
    ze krijgen.

    Fail-soft: geen match → de rol die het signaal al draagt (de feed-toewijzing bij ingest). Zo
    verdwijnt een signaal nooit doordat de router niets weet."""
    huidige = str(signaal.get("role") or "")
    nodig = _SKILL_VOOR_FEED.get(str(signaal.get("feed") or ""))
    if not nodig or records is None:
        return huidige, "feed-toewijzing bij ingest (geen skill-regel voor deze feed)"
    for rec in records:
        d = getattr(rec, "definition", None)
        if d is not None and nodig in (getattr(d, "skills", None) or []):
            waarom = f"bezit '{nodig}', de skill die deze feed vraagt"
            if rec.id != huidige:
                waarom += f" (feed-toewijzing wees naar '{huidige}')"
            return rec.id, waarom
    return huidige, f"niemand bezit '{nodig}' — feed-toewijzing blijft staan"


# Welke skill een feed vraagt. Bewust data, geen if-boom: een nieuwe feed is hier één regel, en de
# ROL volgt uit wie die skill bezit — niet uit een hardgecodeerde rolnaam die kan afdrijven zoals
# het bibliotheek-domein deed.
_SKILL_VOOR_FEED = {
    "Competitor Watch": "competitor_news",
    "Material Innovation": "openalex_evidence",
    "Legal & Green Claims": "claims_check",
}
