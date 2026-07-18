"""regulation_watch — merkt maandelijks of de wet onder de claims-database is verschoven.

Zwart-wit-principe: deze skill **detecteert**, de mens **beoordeelt**. Er wordt nooit iets aan
`config/claims_database.json` gewijzigd en er wordt geen duiding gegeven — geen LLM, geen
interpretatie van wat een wijziging betekent. De uitkomst is altijd: "bron X is veranderd,
kijk ernaar". Een test bewaakt dat deze module de claims-database niet aanraakt.

Mechaniek: elke bron wordt genormaliseerd (HTML → tekst met samengeknepen witruimte; een PDF op
zijn rauwe bytes) en gehasht. De hashes leven append-only in `data/regulation_watch.jsonl`,
zodat de geschiedenis van elke bron terug te lezen is. Hash anders dan de vorige geslaagde meting
→ bevinding.

Fail-closed met geheugen: één onbereikbare maand is geen alarm (sites haperen), twee maanden
achtereen wél — dan is de bewaking stuk en dat moet iemand weten.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from nooch_village import safe_fetch
from nooch_village.checklists import period_key
from nooch_village.skills import Skill

LOGBESTAND = "regulation_watch.jsonl"
ORIGIN = "regulation_change"          # herkomst-stempel van de taken die hieruit ontstaan

# Een bron met dit woord in het label is een tijdelijke plaatsvervanger voor een bron die nog
# niet bestaat (de NL-omzetting). Zulke pagina's veranderen constant om redenen die niets met
# ons te maken hebben, dus daar maken we géén taak van — we houden alleen de meting bij.
PROXY_MARKERING = "PROXY"

# Mijlpaal: vanaf deze datum handhaaft de EmpCo-richtlijn. De maand ervoor wil compliance een
# expliciete opdracht zien, niet een herinnering in iemands hoofd.
HANDHAVING_MAAND = "2026-09"


# ── Pure helpers ────────────────────────────────────────────────────────────

def parse_bronnen(settings) -> list[dict]:
    """`regulation_sources` uit settings.ini → [{letter, label, url, proxy}].

    Formaat per regel: `<letter> | <label> | <url>`. Onleesbare regels worden overgeslagen
    in plaats van de hele bewaking te laten klappen op één typefout."""
    rauw = (settings or {}).get("regulation_sources", "") if hasattr(settings, "get") else ""
    bronnen = []
    for regel in str(rauw).splitlines():
        delen = [d.strip() for d in regel.split("|")]
        if len(delen) != 3 or not delen[2].startswith("http"):
            continue
        letter, label, url = delen
        bronnen.append({"letter": letter.upper()[:1] or "C", "label": label, "url": url,
                        "proxy": PROXY_MARKERING in label.upper()})
    return bronnen


def normaliseer(ruw, content_type: str) -> bytes:
    """De byte-reeks waarover we hashen.

    HTML → zichtbare tekst met samengeknepen witruimte, zodat een gewijzigd sessie-id of een
    andere regelafbreking geen valse 'de wet is veranderd' oplevert. Alles wat geen HTML is
    (PDF) → de rauwe bytes; die zijn stabiel en we doen geen poging de inhoud te lezen."""
    is_html = "html" in (content_type or "").lower()
    if isinstance(ruw, bytes) and not is_html:
        return ruw
    tekst = ruw.decode("utf-8", errors="replace") if isinstance(ruw, bytes) else str(ruw)
    if is_html:
        _, tekst = safe_fetch.naar_tekst(tekst)
    return " ".join(tekst.split()).encode("utf-8")


def hash_van(ruw, content_type: str) -> str:
    return hashlib.sha256(normaliseer(ruw, content_type)).hexdigest()


def lees_log(data_dir: str) -> list[dict]:
    """De append-only meetreeks. Een kapotte regel wordt overgeslagen, niet stil geslikt:
    de rest van de geschiedenis blijft bruikbaar."""
    pad = os.path.join(data_dir, LOGBESTAND)
    rijen = []
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rijen.append(json.loads(regel))
                except ValueError:
                    continue
    except OSError:
        return []
    return rijen


def schrijf_regel(data_dir: str, rij: dict) -> None:
    from nooch_village.util import file_lock
    pad = os.path.join(data_dir, LOGBESTAND)
    os.makedirs(data_dir, exist_ok=True)
    with file_lock(pad):
        with open(pad, "a", encoding="utf-8") as f:
            f.write(json.dumps(rij, ensure_ascii=False) + "\n")


def laatste_meting(rijen: list[dict], url: str, alleen_geslaagd: bool = True) -> dict | None:
    """De meest recente meting van één bron; standaard de laatste die écht lukte."""
    for rij in reversed(rijen):
        if rij.get("url") != url or rij.get("soort") != "meting":
            continue
        if alleen_geslaagd and rij.get("status") != "ok":
            continue
        return rij
    return None


def opeenvolgende_fouten(rijen: list[dict], url: str) -> int:
    """Hoeveel metingen op rij zijn misgegaan sinds de laatste geslaagde?"""
    n = 0
    for rij in reversed(rijen):
        if rij.get("url") != url or rij.get("soort") != "meting":
            continue
        if rij.get("status") == "ok":
            break
        n += 1
    return n


def maand_gedaan(rijen: list[dict], maand: str) -> bool:
    return any(r.get("maand") == maand and r.get("soort") == "meting" for r in rijen)


def mijlpaal_gedaan(rijen: list[dict], sleutel: str) -> bool:
    return any(r.get("soort") == "mijlpaal" and r.get("sleutel") == sleutel for r in rijen)


def meet(bron: dict, _fetch=None) -> dict:
    """Meet één bron. Geeft `{hash}` of `{fout}` terug — nooit een exception naar boven."""
    try:
        opgehaald = safe_fetch.haal_ruw(bron["url"], _fetch=_fetch)
    except (safe_fetch.FetchGeweigerd, safe_fetch.FetchMislukt) as e:
        return {"fout": str(e)}
    return {"hash": hash_van(opgehaald["ruw"], opgehaald["content_type"]),
            "content_type": opgehaald["content_type"]}


# ── De skill ────────────────────────────────────────────────────────────────

class RegulationWatchSkill(Skill):
    name = "regulation_watch"
    cost = "free"
    side_effect_free = False           # maakt taken aan en schrijft de meetreeks
    required_env = ()
    description = ("Controleert maandelijks of de bronteksten van de claim-regelgeving "
                   "(EmpCo-richtlijn, ACM-leidraad, FOD-gids, NL-omzetting) zijn gewijzigd. "
                   "Detecteert alleen: elke wijziging wordt een taak voor compliance om de "
                   "impact te beoordelen. Wijzigt zelf nooit de claims-database.")
    input_schema = "geen (optioneel: force: bool om de maand-gate over te slaan)"
    output_schema = "ok, maand, skipped, gemeten, gewijzigd[], fouten[], nieuw, headsup, escalate"

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        data_dir = getattr(context, "data_dir", ".")
        maand = period_key("maand")
        rijen = lees_log(data_dir)
        if not payload.get("force") and maand_gedaan(rijen, maand):
            return {"ok": True, "maand": maand, "skipped": True, "reden": "deze maand al gemeten"}

        bronnen = parse_bronnen(getattr(context, "settings", {}))
        if not bronnen:
            return {"ok": False, "maand": maand,
                    "escalate": {"reason": "geen regulation_sources geconfigureerd in settings.ini"}}

        gewijzigd, fouten, stukke_bewaking = [], [], []
        for bron in bronnen:
            uitkomst = meet(bron, _fetch=payload.get("_fetch"))
            vorige = laatste_meting(rijen, bron["url"])
            if "fout" in uitkomst:
                schrijf_regel(data_dir, {"soort": "meting", "maand": maand, "url": bron["url"],
                                         "label": bron["label"], "letter": bron["letter"],
                                         "status": "fout", "reden": uitkomst["fout"],
                                         "at": time.time()})
                fouten.append(f"{bron['label']}: {uitkomst['fout']}")
                # Eén misser is geen alarm; twee maanden op rij betekent dat de bewaking stuk is.
                if opeenvolgende_fouten(rijen, bron["url"]) >= 1:
                    stukke_bewaking.append(bron["label"])
                continue
            schrijf_regel(data_dir, {"soort": "meting", "maand": maand, "url": bron["url"],
                                     "label": bron["label"], "letter": bron["letter"],
                                     "status": "ok", "hash": uitkomst["hash"],
                                     "content_type": uitkomst.get("content_type", ""),
                                     "at": time.time()})
            if vorige is None:
                continue                                   # eerste meting = nulmeting, geen nieuws
            if vorige.get("hash") != uitkomst["hash"]:
                gewijzigd.append({**bron, "vorige_hash": vorige.get("hash"),
                                  "nieuwe_hash": uitkomst["hash"],
                                  "vorige_maand": vorige.get("maand", "")})

        taken = self._taken(context, data_dir, maand, gewijzigd)
        taken += self._mijlpalen(context, data_dir, maand, rijen, bronnen)

        rood = [g for g in gewijzigd if g["letter"] == "A" and not g["proxy"]]
        headsup = None
        if rood:
            headsup = ("📜 Wetscheck: " + ", ".join(g["label"][:40] for g in rood)
                       + " is gewijzigd — beoordeel de impact op de claims-database")
        elif taken:
            headsup = f"📜 Wetscheck: {len(taken)} punt(en) voor compliance"

        escalatie = None
        if stukke_bewaking:
            escalatie = {"reason": "twee maanden achtereen onbereikbaar: "
                                   + ", ".join(stukke_bewaking)}
        elif len(fouten) == len(bronnen):
            escalatie = {"reason": "geen enkele bron kon worden opgehaald: " + "; ".join(fouten[:3])}

        return {"ok": escalatie is None, "maand": maand, "skipped": False,
                "gemeten": len(bronnen) - len(fouten), "gewijzigd": gewijzigd,
                "fouten": fouten, "nieuw": len(taken), "aangemaakt": taken,
                "headsup": headsup, "escalate": escalatie}

    # ── taken (alleen signaleren, nooit duiden) ──────────────────────────────

    def _taken(self, context, data_dir: str, maand: str, gewijzigd: list[dict]) -> list[dict]:
        uit = []
        for bron in gewijzigd:
            if bron["proxy"]:
                # Een plaatsvervangende bron verandert om redenen die niets met de wet te maken
                # hebben. De meting staat in het log; er komt geen taak van.
                continue
            titel = f"📜 Bron gewijzigd: {bron['label']}"
            beschrijving = (
                f"De brontekst is veranderd sinds {bron.get('vorige_maand') or 'de vorige meting'}.\n"
                f"Bron: {bron['url']}\n"
                f"Gewicht: {bron['letter']}\n"
                f"Wat te doen: lees de wijziging en beoordeel of termen, werklijst of landenregels "
                f"in de claims-database aangepast moeten worden.\n"
                f"De tool duidt bewust niet — dit is een compliance-oordeel.")
            pid = self._taak(context, titel, beschrijving, sleutel=f"{bron['url']}|{maand}")
            if pid:
                uit.append({"pid": pid, "titel": titel, "label": bron["label"]})
        return uit

    def _mijlpalen(self, context, data_dir: str, maand: str, rijen: list[dict],
                   bronnen: list[dict]) -> list[dict]:
        """Eenmalige, gedateerde opdrachten. Idempotent via een mijlpaal-regel in het log."""
        uit = []
        if maand >= HANDHAVING_MAAND and not mijlpaal_gedaan(rijen, "empco_handhaving"):
            titel = "📜 EmpCo-handhaving start 27-09 — volledige claim-doorloop"
            pid = self._taak(context, titel,
                             "Vanaf 27-09-2026 handhaaft de EmpCo-richtlijn, met boetes tot 4% "
                             "jaaromzet.\nDrie dingen vóór die datum:\n"
                             "1. Volledige scan van de site (alle pagina's, niet alleen de vaste set)\n"
                             "2. Alle RODE werklijst-items afgehandeld of expliciet geaccepteerd\n"
                             "3. De PETA-beslissing genomen (label-conflict met nooch-legal)",
                             sleutel="mijlpaal|empco_handhaving")
            if pid:
                schrijf_regel(data_dir, {"soort": "mijlpaal", "sleutel": "empco_handhaving",
                                         "maand": maand, "at": time.time()})
                uit.append({"pid": pid, "titel": titel, "label": "mijlpaal"})

        # De NL-omzetting: zolang de bron een PROXY is bestaat de wettekst nog niet. Zodra
        # compliance in settings.ini de echte bron invult (label zonder PROXY), is dát het moment
        # om de wettekst naast de database te leggen.
        nl = [b for b in bronnen if "NL-OMZETTING" in b["label"].upper()]
        if nl and not nl[0]["proxy"] and not mijlpaal_gedaan(rijen, "nl_omzetting"):
            titel = "📜 NL-wettekst naast de claims-database leggen"
            pid = self._taak(context, titel,
                             f"De NL-omzetting van EmpCo heeft een echte bron gekregen: "
                             f"{nl[0]['url']}\nLeg de wettekst naast de termen, de werklijst en de "
                             f"landenregels en noteer waar de NL-tekst nuances toevoegt.",
                             sleutel="mijlpaal|nl_omzetting")
            if pid:
                schrijf_regel(data_dir, {"soort": "mijlpaal", "sleutel": "nl_omzetting",
                                         "maand": maand, "at": time.time()})
                uit.append({"pid": pid, "titel": titel, "label": "mijlpaal"})
        return uit

    def _taak(self, context, titel: str, beschrijving: str, sleutel: str) -> str | None:
        """Eén taak voor compliance. Dedupe: zolang de vorige taak voor dezelfde bron open
        staat komt er geen tweede bij."""
        ledger = getattr(context, "projects", None)
        if ledger is None:
            return None
        basis = sleutel.split("|")[0]
        for p in ledger.all():
            if (p.get("origin") == ORIGIN and p.get("status") != "done"
                    and str(p.get("keyword", "")).startswith(basis)):
                return None
        pid = ledger.create("compliance", titel[:200], "role", status="future", origin=ORIGIN,
                            keyword=sleutel, description=beschrijving,
                            dod_outcome="de impact op de claims-database is beoordeeld",
                            done_when="de database is bijgewerkt of expliciet ongewijzigd gelaten",
                            goes_to="compliance")
        from nooch_village import claims_board
        claims_board.bericht_aan_rol(context, "compliance", titel, pid)
        return pid
