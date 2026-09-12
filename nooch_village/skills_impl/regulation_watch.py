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

De maand-poort telt alleen GESLAAGDE metingen (scope 56). Tot dan sloot één timeout op de eerste
puls van de maand die maand af: de bron werd pas de volgende maand opnieuw geprobeerd, zonder
melding, en het alarm kwam op zijn vroegst na twee kalendermaanden blindheid. Nu krijgt een bron die
faalt bij de volgende puls een nieuwe kans, tot `MAX_POGINGEN_PER_MAAND`, en hoort compliance het
bij de eerste misser én bij het opgeven.
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

# Hoe vaak een bron die faalt binnen één maand opnieuw geprobeerd wordt (één poging per dagpuls).
# Vijf, want: de puls is dagelijks, dus vijf pogingen beslaan een werkweek — een weekend-storing of
# een eenmalige timeout kost daarmee geen maand meer (dat kostte hij tot scope 56). Méér pogingen
# levert niets op: een bron die vijf dagen op rij niet antwoordt is structureel weg voor deze maand,
# en dertig fout-regels per bron per maand maken het append-only log onleesbaar. Bij het opgeven
# hoort compliance het; de teller start elke kalendermaand opnieuw.
MAX_POGINGEN_PER_MAAND = 5


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


def maanden_zonder_meting(rijen: list[dict], url: str) -> set[str]:
    """De KALENDERMAANDEN waarin deze bron sinds zijn laatste geslaagde meting alleen maar faalde.

    Niet 'pogingen op rij': sinds een bron binnen één maand meerdere kansen krijgt, zou het aantal
    mislukte pogingen "twee maanden achtereen" al na twee dagen melden. Het alarm gaat over maanden."""
    maanden: set[str] = set()
    for rij in reversed(rijen):
        if rij.get("url") != url or rij.get("soort") != "meting":
            continue
        if rij.get("status") == "ok":
            break
        maanden.add(str(rij.get("maand") or ""))
    return maanden


def gemeten_deze_maand(rijen: list[dict], url: str, maand: str) -> bool:
    """Heeft deze bron deze maand een GESLAAGDE meting? Een mislukte telt niet — die krijgt bij de
    volgende puls een nieuwe kans."""
    return any(r.get("url") == url and r.get("maand") == maand and r.get("soort") == "meting"
               and r.get("status") == "ok" for r in rijen)


def pogingen_deze_maand(rijen: list[dict], url: str, maand: str) -> int:
    """Hoeveel MISLUKTE metingen deze bron deze maand al had (de teller onder MAX_POGINGEN_PER_MAAND)."""
    return sum(1 for r in rijen if r.get("url") == url and r.get("maand") == maand
               and r.get("soort") == "meting" and r.get("status") != "ok")


def opgegeven(rijen: list[dict], url: str, maand: str) -> bool:
    """Deze bron is deze maand niet gemeten én de pogingen zijn op: de maand is voor hem dicht."""
    return (not gemeten_deze_maand(rijen, url, maand)
            and pogingen_deze_maand(rijen, url, maand) >= MAX_POGINGEN_PER_MAAND)


def te_meten(rijen: list[dict], bronnen: list[dict], maand: str) -> list[dict]:
    """De bronnen die deze puls aan de beurt zijn: nog niet geslaagd deze maand en nog pogingen over."""
    return [b for b in bronnen
            if not gemeten_deze_maand(rijen, b["url"], maand) and not opgegeven(rijen, b["url"], maand)]


def maand_gedaan(rijen: list[dict], maand: str, bronnen: list[dict] | None = None) -> bool:
    """Is deze maand gedaan? Mét bronnen: elke bron is geslaagd óf opgegeven. Zonder bronnen (oudere
    aanroepers, het ritme-scherm): er is minstens één GESLAAGDE meting deze maand.

    Tot scope 56 telde élke meting, ook een mislukte — één timeout op de eerste puls sloot de maand."""
    if bronnen is not None:
        return not te_meten(rijen, bronnen, maand)
    return any(r.get("maand") == maand and r.get("soort") == "meting" and r.get("status") == "ok"
               for r in rijen)


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
    description = ("Monthly check whether the source texts of the claims regulation (EmpCo directive, "
                   "ACM guideline, FOD guide, NL transposition) have changed, by hashing each source. "
                   "Detects only: every change becomes a task for compliance to judge the impact; "
                   "never edits the claims database, no model. A source that fails is retried on the "
                   f"next pulse, up to {MAX_POGINGEN_PER_MAAND} times a month.")
    input_schema = ("no fields required · force: bool (optional — re-measure every source now, "
                    "skipping the month gate)")
    output_schema = ("ok, maand, skipped, text, gemeten, gewijzigd[{label, url, letter, vorige_hash, "
                     "nieuwe_hash}], fouten[], nieuw, aangemaakt[{pid, titel, label}], headsup, "
                     "escalate | no_data+reason (nothing changed / month done)")

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        data_dir = getattr(context, "data_dir", ".")
        # `_maand` is er voor de TEST, net als `_fetch`. Zonder injectiepunt hingen zes tests aan de
        # echte klok, en op 1 september 2026 vielen ze allemaal om: `HANDHAVING_MAAND` was aangebroken,
        # dus de skill deed zijn werk (een mijlpaal-regel erbij) en de tests rekenden op de wereld van
        # daarvoor. Geen bug in de skill maar een tijdbom in de tests — en die gaat af op een dag dat
        # je met iets anders bezig bent.
        maand = payload.get("_maand") or period_key("maand")
        rijen = lees_log(data_dir)
        bronnen = parse_bronnen(getattr(context, "settings", {}))
        if not bronnen:
            return {"ok": False, "maand": maand,
                    "escalate": {"reason": "geen regulation_sources geconfigureerd in settings.ini"}}

        # Per bron, niet per maand: wie deze maand al lukte wordt niet opnieuw gehaald, wie faalde
        # krijgt een nieuwe kans tot de pogingen op zijn. `force` meet alles opnieuw (de handmatige duw).
        beurt = bronnen if payload.get("force") else te_meten(rijen, bronnen, maand)
        if not beurt:
            gemeten = sum(1 for b in bronnen if gemeten_deze_maand(rijen, b["url"], maand))
            weg = [b["label"] for b in bronnen if opgegeven(rijen, b["url"], maand)]
            reden = f"deze maand al gemeten ({gemeten} van {len(bronnen)} bronnen)"
            if weg:
                reden += (f"; opgegeven na {MAX_POGINGEN_PER_MAAND} pogingen: " + ", ".join(weg))
            # `no_data` + `reason` voor het checklist-pad (📭 in plaats van een kennisgat), `skipped`
            # + `reden` voor de pulslaag — zelfde regel als bij claims_site_scan.
            return {"ok": True, "maand": maand, "skipped": True, "reden": reden,
                    "no_data": True, "reason": reden, "text": reden}

        gewijzigd, fouten, stukke_bewaking, hapert, opgegeven_nu = [], [], [], [], []
        for bron in beurt:
            uitkomst = meet(bron, _fetch=payload.get("_fetch"))
            vorige = laatste_meting(rijen, bron["url"])
            if "fout" in uitkomst:
                schrijf_regel(data_dir, {"soort": "meting", "maand": maand, "url": bron["url"],
                                         "label": bron["label"], "letter": bron["letter"],
                                         "status": "fout", "reden": uitkomst["fout"],
                                         "at": time.time()})
                fouten.append(f"{bron['label']}: {uitkomst['fout']}")
                poging = pogingen_deze_maand(rijen, bron["url"], maand) + 1
                # Eén misser is geen alarm, wél een melding: de bron krijgt morgen een nieuwe kans en
                # compliance ziet dat NU, niet pas na twee maanden. Bij het opgeven nog één keer.
                # Tussendoor stil (alleen het log), anders krijgt de founder vijf dagen dezelfde regel.
                if poging >= MAX_POGINGEN_PER_MAAND:
                    opgegeven_nu.append(f"{bron['label']} ({uitkomst['fout'][:60]})")
                elif poging == 1:
                    hapert.append(f"{bron['label']} ({uitkomst['fout'][:60]}) — poging "
                                  f"{poging}/{MAX_POGINGEN_PER_MAAND}, morgen opnieuw")
                # Twee KALENDERMAANDEN op rij zonder geslaagde meting: de bewaking is stuk. `rijen`
                # is het log van vóór deze run, dus de huidige maand telt hier expliciet mee.
                if len(maanden_zonder_meting(rijen, bron["url"]) | {maand}) >= 2:
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
        # Een enkele falende bron is een regel in de heads-up, geen alarm — maar ook geen stilte.
        # Tot scope 56 stond hij alleen in `fouten` en las niemand hem.
        for regel in ([f"⚠️ Wetscheck: bron niet gemeten — {h}" for h in hapert]
                      + [f"⚠️ Wetscheck: bron deze maand opgegeven na {MAX_POGINGEN_PER_MAAND} "
                         f"pogingen — {o}" for o in opgegeven_nu]):
            headsup = f"{headsup} · {regel}" if headsup else regel

        escalatie = None
        if stukke_bewaking:
            escalatie = {"reason": "twee maanden achtereen onbereikbaar: "
                                   + ", ".join(stukke_bewaking)}
        elif len(fouten) == len(bronnen):
            # Op ALLE geconfigureerde bronnen, niet op de beurt: een herkansing waarin alleen de
            # haperende bron aan de beurt is, is geen "niets bereikbaar" — de rest lukte deze maand
            # al. Anders escaleert elke herkansing naar de founder, vijf dagen op rij.
            escalatie = {"reason": "geen enkele bron kon worden opgehaald: " + "; ".join(fouten[:3])}

        gemeten = len(beurt) - len(fouten)
        uit = {"ok": escalatie is None, "maand": maand, "skipped": False,
               "gemeten": gemeten, "gewijzigd": gewijzigd,
               "fouten": fouten, "nieuw": len(taken), "aangemaakt": taken,
               "headsup": headsup, "escalate": escalatie}
        uit["text"] = (f"{gemeten} of {len(beurt)} source(s) measured for {maand}: "
                       f"{len(gewijzigd)} changed, {len(taken)} task(s) for compliance"
                       + (f"; {len(fouten)} not reachable" if fouten else ""))
        if escalatie is None and not gewijzigd and not taken:
            # Niets veranderd is een antwoord ("de wet ligt er nog zo"), geen kennisgat.
            uit["no_data"] = True
            uit["reason"] = uit["text"] + " — no source text changed"
        return uit

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
            pid = self._taak(context, titel, beschrijving, sleutel=f"{bron['url']}|{maand}",
                             dedupe=bron["url"])
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

    def _taak(self, context, titel: str, beschrijving: str, sleutel: str,
              dedupe: str | None = None) -> str | None:
        """Eén taak voor compliance. Dedupe: zolang een open taak bestaat waarvan de sleutel met
        `dedupe` begint, komt er geen tweede bij. Default = de volledige sleutel.

        Tot scope 56 dedupliceerde dit op `sleutel.split("|")[0]`; beide mijlpalen delen de basis
        "mijlpaal", dus zolang de EmpCo-handhavingstaak open stond werd de NL-omzettingsmijlpaal
        nooit aangemaakt (en ook niet gelogd). Een bron-taak dedupliceert bewust op de URL (zie
        `_taken`): dezelfde bron die in een volgende maand wéér wijzigt terwijl de vorige taak nog
        open staat, hoort geen stapel duplicaten op te leveren."""
        ledger = getattr(context, "projects", None)
        if ledger is None:
            return None
        basis = dedupe if dedupe is not None else sleutel
        for p in ledger.all():
            if (p.get("origin") == ORIGIN and p.get("status") != "done"
                    and str(p.get("keyword", "")).startswith(basis)):
                return None
        from nooch_village import claims_board
        rol = claims_board.claims_rol(getattr(context, "records", None))
        if not rol:
            # Geen levende rol bezit het claims-domein: geen eigenaarloze taak aanmaken en geen
            # bericht naar een naam die niemand draagt.
            return None
        pid = ledger.create(rol, titel[:200], "role", status="future", origin=ORIGIN,
                            keyword=sleutel, description=beschrijving,
                            dod_outcome="de impact op de claims-database is beoordeeld",
                            done_when="de database is bijgewerkt of expliciet ongewijzigd gelaten",
                            goes_to=rol)
        claims_board.bericht_aan_rol(context, rol, titel, pid)
        return pid
