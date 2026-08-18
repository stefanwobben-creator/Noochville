"""De rol verwerkt zijn spanning zelf — de founder is de laatste optie, niet de eerste.

De "What do you need?"-boom stond als founder-menu op Stefans bureau: hij mocht kiezen wat er met
andermans spanning moest gebeuren. Dat is de verkeerde volgorde. Diezelfde boom is de EERSTE
handeling van de rol die de spanning voelt:

    zelf        ik los het op in mijn eigen domein
    info        ik heb niets nodig, ik deel wat ik vond
    naar rol    ik heb rol Y nodig, en ik zeg waarvoor
    founder     ik heb de founder nodig, voor een bevoegdheid die alleen hij heeft

De eerste drie bereiken de beslis-inbox niet. Rol-naar-rol lost onderling op; dat is wat een
zelfsturende organisatie doet. Alleen de vierde wordt een kaart, en dan met de behoefte erbij: niet
"hier is een probleem" maar "ik heb jou nodig voor X".

De boom is niet nieuw. `inbox_wizard.INTENTS` bestaat al als gedeelde beslisboom voor mens én
"straks de autonome AI-triage" — dat is deze laag. Hier wordt hij toegepast vanuit het perspectief
van de rol, en elke verwerking landt in hetzelfde verwerk-record, zodat mens en AI hetzelfde spoor
achterlaten.

**Founder-bevoegdheid is smal.** Niet "het gaat over compliance" maar "hier moet iemand tekenen die
als enige mag tekenen". Een claim voorbereiden, onderbouwen en herschrijven is rolwerk; alleen het
uiteindelijke ja/nee op iets dat de missie, het merk, het geld of de structuur raakt is van hem.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

log = logging.getLogger("village.zelf_verwerking")

BESTAND = "verwerkingen.jsonl"

ZELF       = "zelf"        # licht: opgelost in eigen domein
INFO       = "info"        # licht: niets nodig, gedeeld wat er gevonden is
NAAR_ROL   = "naar_rol"    # operationeel verzoek aan een andere rol
GOVERNANCE = "governance"  # de STRUCTUUR moet mee: een rol, accountability, domein of policy
FOUNDER    = "founder"     # een bevoegdheid die alleen de founder heeft

LABEL = {ZELF: "zelf opgelost", INFO: "info gedeeld", NAAR_ROL: "operationeel verzoek",
         GOVERNANCE: "governance-voorstel", FOUNDER: "founder-besluit"}

# De vier typen zoals ze op een kaart staan. `licht` is geen kaart: die verlaat de rol niet.
TYPE_LABEL = {NAAR_ROL: "operationeel verzoek", GOVERNANCE: "governance-voorstel",
              FOUNDER: "founder-besluit", ZELF: "licht", INFO: "licht"}

# Wanneer is een spanning STRUCTUREEL? Als het antwoord niet één handeling is maar een wijziging in
# wie waarvoor staat. Twee signalen samen: iets structureels/terugkerends, én een structuur-object
# (rol, accountability, domein, policy, mandaat). Eén van de twee is niet genoeg — "dit gebeurt
# vaker" zonder object is een klacht, en "de rol van X" zonder herhaling is gewoon werk.
_STRUCTUREEL = re.compile(r"structure\w*|terugkeren\w*|meermaals|telkens|elke week|wekelijks|"
                          r"steeds opnieuw|systematisch|niemand (?:is|voelt zich) verantwoordelijk|"
                          r"hoort bij niemand|geen enkele rol", re.I)
_STRUCTUUR_OBJECT = re.compile(r"\brol\b|\brollen\b|accountabilit|verantwoordelijkheid|"
                               r"\bdomein\b|\bpolicy\b|beleidsregel|mandaat|governance", re.I)

# Wanneer is het écht van de founder? Een besluit-vraag ÉN een voorbehouden domein. De domeinen
# staan al in de poort; hier telt bovendien dat er om een besluit gevraagd wordt — anders is
# "het gaat over compliance" genoeg om iemand anders zijn werk op het bureau van de mens te leggen.
_BEVOEGDHEID = {
    "merk":       "een uitspraak over het merk en de missie",
    "strategie":  "een koerskeuze",
    "geld":       "een uitgave boven de grens",
    "governance": "een wijziging in de structuur (rollen, mandaten)",
    "compliance": "een claim",
}


def _woorden(tekst: str) -> set[str]:
    """Betekenisdragende woorden, vergeleken op hun eerste vijf letters.

    Exacte tokenmatch was te streng: "claim" en "claims", "evidence" en "evidences" telden als
    verschillende woorden, waardoor de eigen-accountability-check vrijwel nooit aansloeg en werk
    dat een rol duidelijk bezit toch als "niet van mij" las. Vijf letters is geen stemmer, maar
    het vangt meervoud en verbuiging zonder losse woorden aan elkaar te plakken."""
    return {w[:5] for w in re.findall(r"[a-zA-Z][a-zA-Z\-]{4,}", (tekst or "").lower())}


def eigen_domein(tekst: str, rol: str, records, *, drempel: int = 2) -> str:
    """Welke eigen accountability raakt deze spanning? "" als geen enkele."""
    rec = records.get(rol) if records is not None else None
    if rec is None:
        return ""
    doel = _woorden(tekst)
    beste, score = "", 0
    for acc in getattr(rec.definition, "accountabilities", None) or []:
        overlap = len(doel & _woorden(acc))
        if overlap > score:
            beste, score = acc, overlap
    return beste if score >= drempel else ""


def founder_behoefte(tekst: str) -> tuple[str, str]:
    """Vraagt dit om een bevoegdheid die alleen de founder heeft? → (domein, behoefte-regel)."""
    from nooch_village import tensie_poort as tp

    if not tp._VRAAGT_BESLUIT.search(tekst or ""):
        return "", ""
    if tp._GEEN_BEWIJS.search(tekst or ""):
        # Geen bewijs is geen bevoegdheidsvraag maar een bewijs-gat; dat spoor bestaat al.
        return "", ""
    for naam, pat in tp._BESLUIT_DOMEIN.items():
        if pat.search(tekst or ""):
            return naam, (f"ik heb jou nodig om {_BEVOEGDHEID.get(naam, naam)} vrij te geven — "
                          f"dat is een bevoegdheid die alleen jij hebt")
    return "", ""


# ── De domein-grens: routeren op DOEL, niet op trefwoord ────────────────────
#
# De val, letterlijk uit de steekproef: staat er een woord, term of claim in de tekst, dan wijst de
# match de Librarian aan. Maar de Librarian bezit alleen het LEXICON als artefact — welke termen
# approved of avoid zijn, en waarom. Content scannen om claims te toetsen is Compliance; een te
# brede of ruizige query is onderzoeksmethode, dus Scientist.
#
# Dat een term in de zin voorkomt is dus geen routeersignaal maar juist de valkuil. De vraag is wat
# er GEVRAAGD wordt.
#
# De rollen worden herkend aan hun DOMEIN (bibliotheek / claim-verification), niet aan hun id: een
# id kan hernoemd worden, een domein dragen is een governance-besluit.
_LEXICON_DOMEIN = ("bibliotheek", "lexicon", "vocabulary")
_CLAIM_DOMEIN   = ("claim-verification", "claims-database")
# Onderzoeksmethode hoort bij de Scientist — maar die rol houdt vandaag GEEN domein, dus er is
# langs governance geen weg om hem aan te wijzen. Zodra hij er een krijgt, werkt deze route vanzelf.
# Tot dan: geen overdracht (fail-closed) en een logregel, want een gok op een rol-id is precies de
# trefwoord-val die we hier weghalen.
_METHODE_DOMEIN = ("onderzoeksmethode", "research", "science", "wetenschap")

# Wat er gevraagd wordt, per doel.
_DOEL_LEXICON = re.compile(r"\b(?:approve|goedkeur|afkeur|toevoeg\w*|opnemen)\b[^.]{0,40}"
                           r"\b(?:woord|term|lexicon|vocabulaire|vocabulary)|"
                           r"\b(?:lexicon|vocabulaire|woordenlijst)\b", re.I)
_DOEL_CLAIM   = re.compile(r"claim[- ]?scan|toets\w*|beoordeel|substantiat|onderboud|onderbouw\w*|"
                           r"EmpCo|ACM|juridisch|greenwash|verboden claim|claim\b", re.I)
_DOEL_METHODE = re.compile(r"\bquer\w+|zoekopdracht|result set|resultaten\b|noisy|ruis|"
                           r"te breed|broad|search\w*|steekproef|methode", re.I)


def _rol_met_domein(records, domeinen) -> str:
    """De rol die een van deze domeinen houdt, of "". Governance bepaalt wie dat is, niet deze code."""
    for rec in (records.all() if records is not None else []):
        for d in getattr(getattr(rec, "definition", None), "domains", None) or []:
            if str(d).strip().lower() in domeinen:
                return rec.id
    return ""


def domein_grens(naar_rol: str, tekst: str, records) -> tuple[str, str]:
    """Corrigeer een overdracht die op een trefwoord is aangewezen in plaats van op het doel.

    Geeft (rol, waarom-gecorrigeerd). Rol == `naar_rol` betekent: de overdracht blijft staan.
    Kan de juiste rol niet gevonden worden, dan geeft hij "" terug — liever geen overdracht dan een
    naar het verkeerde bureau, want die kost een hop en levert een vals gat-record op."""
    lexicon_rol = _rol_met_domein(records, _LEXICON_DOMEIN)
    if not naar_rol or naar_rol != lexicon_rol:
        return naar_rol, ""
    # De ontvanger is de lexicon-houder. Is dit écht lexicon-curatie?
    if _DOEL_LEXICON.search(tekst or ""):
        return naar_rol, ""
    if _DOEL_CLAIM.search(tekst or ""):
        claim_rol = _rol_met_domein(records, _CLAIM_DOMEIN)
        return claim_rol, (f"dit toetst een claim; dat is het claim-domein, niet het lexicon"
                           if claim_rol else
                           "dit toetst een claim, maar er is geen rol met het claim-domein")
    if _DOEL_METHODE.search(tekst or ""):
        methode_rol = _rol_met_domein(records, _METHODE_DOMEIN)
        if methode_rol:
            return methode_rol, "dit gaat over onderzoeksmethode, niet over het lexicon"
        log.info("zelf-verwerking: methode-werk hoort bij de Scientist, maar geen rol houdt een "
                 "onderzoeksmethode-domein — geen overdracht (governance-gat)")
        return "", ("dit gaat over onderzoeksmethode, niet over het lexicon — en geen rol houdt "
                    "een onderzoeksmethode-domein")
    return "", "dit raakt het lexicon-domein niet — een term in de tekst is geen routeersignaal"


# ── Toestemming vragen is geen zelf-doen ───────────────────────────────────
#
# In de eerste bevinding-dry-run schreven meerdere `licht`-items een voorstel als "Geef mij de
# ruimte om onderzoek te doen" of "Geef toestemming om te onderzoeken". Het type zei "doe het
# zelf", de tekst vroeg toestemming. Die twee kunnen niet allebei waar zijn.
#
# Zelf-doen vereist TWEE dingen: niemand anders nodig, ÉN de rol heeft de autoriteit. Ontbreekt het
# tweede, dan is het geen licht werk maar een gat: of iemand moet het geven (verzoek), of het hoort
# in de structuur geborgd te worden (governance).
_VRAAGT_TOESTEMMING = re.compile(
    r"geef (?:mij |me )?(?:de )?(?:ruimte|toestemming|akkoord|groen licht)|"
    r"toestemming (?:om|voor|nodig)|\bmag ik\b|\bmogen wij\b|"
    r"goedkeuring (?:nodig|vragen)|met (?:jouw|je) akkoord|als (?:jij|je) akkoord|"
    r"\bpermission\b|\bapproval\b|\bmay I\b|are we allowed", re.I)


def vraagt_toestemming(tekst: str) -> str:
    """De zinsnede waarmee om toestemming wordt gevraagd, of "". """
    m = _VRAAGT_TOESTEMMING.search(tekst or "")
    return m.group(0) if m else ""


def autonomie_signaal(data_dir: str, *, rol: str, tensie: str, voorstel: str, zinsnede: str,
                      eigen_accountability: str = "") -> bool:
    """Leg vast dat een rol toestemming vraagt voor iets wat binnen zijn eigen werk lijkt te vallen.

    Niet stil wegschrijven: een rol die binnen zijn domein steeds toestemming vraagt, legt een
    governance-gat bloot dat later een voorstel wordt ("deze rol mist mandaat, of denkt dat te
    missen"). Dat patroon zie je alleen als je het per rol telt."""
    return _append(data_dir, "autonomie_signaal.jsonl",
                   {"rol": rol, "tensie": tensie[:300], "voorstel": voorstel[:300],
                    "zinsnede": zinsnede, "eigen_accountability": eigen_accountability[:160]})


def autonomie_per_rol(data_dir: str) -> dict:
    """Hoe vaak vroeg elke rol toestemming? De teller die het gat zichtbaar maakt."""
    uit: dict = {}
    for r in _lees(data_dir, "autonomie_signaal.jsonl"):
        uit[r.get("rol", "?")] = uit.get(r.get("rol", "?"), 0) + 1
    return dict(sorted(uit.items(), key=lambda kv: -kv[1]))


def _mag_ontvangen(rol_id: str, records) -> bool:
    """Mag deze rol werk ONTVANGEN via een rol-naar-rol-overdracht?

    Twee weigeringen, allebei uit de steekproef:

      de FOUNDER-rol — die bereik je via de bevoegdheidsvraag, niet via een handover. Anders
      omzeilt een overdracht de hele poort: in de steekproef schoof de financial controller het
      jaarverslag naar de founder-rol, en dat is gewoon zijn eigen werk;
      een CIRKEL — die heeft geen handen (harde regel 7), dus werk erheen schuiven is het laten
      verdwijnen in een niveau in plaats van bij iemand.
    """
    from nooch_village import org
    from nooch_village.founder_kaart import FOUNDER_ROL

    if not rol_id or rol_id == FOUNDER_ROL:
        return False
    rec = records.get(rol_id) if records is not None else None
    if rec is None or getattr(rec, "archived", False):
        return False
    try:
        return not org.is_circle(rec)
    except Exception:                                    # noqa: BLE001 — geen org-info = niet blokkeren
        return True


def verwerk(tekst: str, *, rol: str, records, reason_fn=None, gebruik_llm: bool = True,
            van_eigen_bord: bool = False, voorstel: str = "", data_dir: str = "") -> dict:
    """De eerste handeling van de rol die de spanning voelt.

    Volgorde: is dit een bevoegdheidsvraag → founder; kan ik het zelf → zelf; bezit een ander het
    → naar die rol; anders deel ik wat ik vond. De founder staat vooraan omdat het de smalste
    categorie is, niet omdat hij de eerste keuze is: valt hij af, dan probeert de rol álles zelf."""
    from nooch_village import tensie_poort as tp

    kern = tp.kern(tekst)
    domein, behoefte = founder_behoefte(tekst)
    if domein:
        return {"uitkomst": FOUNDER, "rol": rol, "naar_rol": "", "domein": domein,
                "behoefte": behoefte, "tensie": kern,
                "reden": f"dit vraagt een besluit in een voorbehouden domein ({domein})"}

    # TOESTEMMING VRAGEN IS GEEN ZELF-DOEN. Zelf-doen vereist twee dingen: niemand anders nodig ÉN
    # de autoriteit hebben. Vraagt het voorstel om toestemming, dan ontbreekt het tweede — en dan is
    # het per definitie geen licht werk, ongeacht of het op het eigen bord staat of in de eigen
    # accountability valt. Eén plek, vóór álle licht-paden, want in twee losse checks lekte hij weg.
    zin = vraagt_toestemming(voorstel or kern)
    if zin:
        eigen_acc = eigen_domein(kern, rol, records)
        if data_dir:
            autonomie_signaal(data_dir, rol=rol, tensie=kern, voorstel=voorstel or "",
                              zinsnede=zin, eigen_accountability=eigen_acc)
        waarom = (f"dit valt onder mijn eigen accountability ({eigen_acc[:60]}) maar het voorstel "
                  f"vraagt toestemming" if eigen_acc else "het voorstel vraagt toestemming")
        return {"uitkomst": GOVERNANCE, "rol": rol, "naar_rol": "", "domein": "", "behoefte": "",
                "tensie": kern, "eigen_accountability": eigen_acc, "autonomie_signaal": zin,
                "reden": (f"{waarom} (\"{zin}\") — óf ik heb het mandaat en hoef niet te vragen, "
                          f"óf het mandaat ontbreekt en dat hoort geborgd")}

    # Structureel? Dan is het antwoord geen handeling maar een wijziging in wie waarvoor staat.
    # Dat gaat langs governance (G0-G4 + Secretary), niet langs een bord.
    if _STRUCTUREEL.search(kern) and _STRUCTUUR_OBJECT.search(kern):
        return {"uitkomst": GOVERNANCE, "rol": rol, "naar_rol": "", "domein": "", "behoefte": "",
                "tensie": kern,
                "reden": ("dit is terugkerend én raakt wie waarvoor staat — dan is het antwoord "
                          "een structuurwijziging, geen handeling")}

    eigen = eigen_domein(kern, rol, records)
    if eigen:
        return {"uitkomst": ZELF, "rol": rol, "naar_rol": "", "domein": "", "behoefte": "",
                "tensie": kern, "eigen_accountability": eigen,
                "reden": f"dit valt onder mijn eigen accountability: {eigen[:80]}"}

    ander, kind, waarom = ("", "", "")
    if gebruik_llm:
        try:
            # GEEN van_rol hier. `match` geeft dat door aan de router-roster als EXCLUDE, en dan
            # staat de rol zelf niet in de kandidatenlijst — de match kán dus nooit "dit is van
            # jou" antwoorden en wijst altijd iemand anders aan. In de steekproef gaf dat vier
            # duidelijke missers: de copywriter die het herschrijven van een claim weggaf, en
            # compliance dat zijn eigen juridische oordeel naar de Librarian stuurde.
            ander, kind, waarom = tp.match(kern, records, reason_fn=reason_fn)
            if ander == rol:
                return {"uitkomst": ZELF, "rol": rol, "naar_rol": "", "domein": "",
                        "behoefte": "", "tensie": kern, "eigen_accountability": "",
                        "reden": f"de match wijst mij zelf aan als eigenaar ({waarom})"}
        except Exception as e:                            # noqa: BLE001 — fail-soft, luid
            log.warning("zelf-verwerking: match faalde (%s) — ik deel wat ik vond", e)
    if ander:
        gecorrigeerd, waarom_grens = domein_grens(ander, kern, records)
        if gecorrigeerd != ander:
            log.info("zelf-verwerking: overdracht %s → %s gecorrigeerd naar %r (%s)",
                     rol, ander, gecorrigeerd or "geen", waarom_grens)
            ander = gecorrigeerd
            waarom = waarom_grens or waarom
            if ander == rol:
                return {"uitkomst": ZELF, "rol": rol, "naar_rol": "", "domein": "", "behoefte": "",
                        "tensie": kern, "eigen_accountability": "",
                        "reden": f"de domein-grens wijst dit terug naar mij: {waarom_grens}"}
    if ander and not _mag_ontvangen(ander, records):
        log.info("zelf-verwerking: overdracht naar %r geweigerd — geen geldige ontvanger", ander)
        ander = ""
    if ander:
        return {"uitkomst": NAAR_ROL, "rol": rol, "naar_rol": ander, "domein": "", "behoefte": "",
                "tensie": kern, "reden": f"{ander} bezit dit werk ({waarom})"}

    if van_eigen_bord:
        # Het staat al op MIJN bord. Dan is het van mij, ook als de woorden niet netjes overlappen
        # met een accountability-tekst. In de eerste meting viel 101 van de 172 hierop terug als
        # 'info gedeeld' — het dorp zou 101 keer iets gaan delen in plaats van het werk te doen.
        return {"uitkomst": ZELF, "rol": rol, "naar_rol": "", "domein": "", "behoefte": "",
                "tensie": kern, "eigen_accountability": "",
                "reden": "dit staat op mijn eigen bord en niemand anders bezit het — dus doe ik het"}

    return {"uitkomst": INFO, "rol": rol, "naar_rol": "", "domein": "", "behoefte": "",
            "tensie": kern,
            "reden": "niemand anders bezit dit en het valt buiten mijn accountabilities — "
                     "ik deel wat ik vond in plaats van het door te schuiven"}


# ── Het spoor: de bron van de statusweergave ────────────────────────────────

def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def _append(data_dir: str, bestand: str, rij: dict) -> bool:
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, bestand), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**rij, "ts": time.time()}, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        log.warning("%s niet vastgelegd: %s", bestand, e)
        return False


def _lees(data_dir: str, bestand: str) -> list[dict]:
    uit = []
    try:
        with open(os.path.join(data_dir, bestand), encoding="utf-8") as fh:
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
        log.warning("%s onleesbaar: %s", bestand, e)
    return uit


def leg_vast(data_dir: str, verwerking: dict) -> bool:
    """Append-only. Dit is systeemstatus, geen wachtrij: er wordt niets afgevinkt."""
    return _append(data_dir, BESTAND, verwerking)


def alle(data_dir: str) -> list[dict]:
    return _lees(data_dir, BESTAND)


def verdeling(rijen: list[dict]) -> dict:
    """Hoeveel loste in-rol op, hoeveel ging rol-naar-rol, hoeveel bereikte de founder."""
    uit: dict = {}
    for r in rijen:
        uit[r.get("uitkomst", "?")] = uit.get(r.get("uitkomst", "?"), 0) + 1
    totaal = sum(uit.values()) or 1
    return {"per_uitkomst": uit, "totaal": sum(uit.values()),
            "onder_de_rollen": round(100 * sum(uit.get(k, 0) for k in (ZELF, INFO, NAAR_ROL))
                                     / totaal),
            "naar_de_founder": uit.get(FOUNDER, 0)}
