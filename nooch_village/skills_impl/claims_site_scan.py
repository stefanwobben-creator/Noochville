"""claims_site_scan — de wekelijkse zelf-scan van nooch.earth door compliance.

Verschil met `claims_check`: die skill is puur lokaal en toetst tekst die je hem geeft. Deze
skill haalt zélf de vaste pagina-set op (server-side, via `safe_fetch` met SSRF-guardrail) en
levert alleen NIEUWE bevindingen — wat al in de werklijst staat of al als taak loopt, telt niet.

Vier regels:
1. **Volledige dekking per week, desnoods over meerdere pulsen.** De week is pas gedaan als ELKE
   pagina uit de set een keer gelukt is. Lukte een pagina niet, dan scant de volgende puls precies
   de pagina's die nog missen — nooit weer de hele lijst vanaf pagina 1. Zonder dat geheugen haalde
   de scan elke dag dezelfde eerste pagina's en bleven de laatste structureel ongezien.
2. **Fail-closed.** Alle pagina's onbereikbaar of de database corrupt → `escalate`, nooit een
   stille nul. "Geen bevindingen" moet betekenen dat er niets was, niet dat er niets werkte.
3. **Bewijs-eerst.** Een milieuclaim is alleen groen als de Kroniek hem onderbouwt; zonder
   bevestigd record wordt hij oranje "onderbouwing ontbreekt" (`claims_substantiatie`).
4. **Geen bord-ruis.** Niets nieuws → één logregel, geen taken, geen heads-up.

Twee handmatige duwtjes, met verschillende betekenis: `force` slaat de week-poort over maar
respecteert de dekking (hij helpt de scan vooruit), `herstart` gooit de dekking weg en doet de
hele week opnieuw.
"""
from __future__ import annotations

import os
import time

from nooch_village import (
    claims_board,
    claims_db,
    claims_labels,
    claims_modelpas,
    claims_substantiatie,
    claims_verify,
    gap_ledger,
    safe_fetch,
)
from nooch_village.checklists import period_key
from nooch_village.skills import Skill

MARKER = "claims_site_scan_last_week.json"

# Beleefdheid tussen twee pagina's van dezelfde host. Zonder pauze antwoordt Shopify op de tweede
# pagina met een 429 en scande de wekelijkse run in de praktijk 2 van de 5 pagina's — terwijl hij
# 'ok' meldde. Een scan die driekwart van de site niet ziet is gevaarlijker dan een scan die traag is.
# Pacing, op basis van twee gemeten productie-runs. Cloudflare (Shopify's edge) antwoordt vanaf de
# server met `local_rate_limited` + `Retry-After: 60`, maar de bucket blijkt niet "één per minuut" te
# zijn: zowel met 1,5s als met 65s pauze kwamen er precies TWEE pagina's door. Het is een kleine
# bucket met trage refill, en een mislukt verzoek verbruikt hem net zo goed als een geslaagd verzoek.
#
# Daarom: ÉÉN poging per pagina per puls. Retryen binnen een run verbrandt de bucket voor de pagina's
# die daarna komen — het maakt de dekking kleiner in plaats van groter. De dekking komt van de
# volgende puls (zie DEKKING hieronder), niet van harder aandringen.
PAUZE_SECONDEN = 10.0
POGINGEN_PER_PAGINA = 1

# DEKKING PER WEEK — de bug die dit oplost: elke puls begon weer bij pagina 1, dus haalde hij elke
# dag dezelfde eerste twee pagina's en kwamen de laatste drie NOOIT aan de beurt, hoe vaak het ritme
# ook hervatte. De weekmarker houdt nu bij welke pagina's deze week al gelukt zijn; de volgende puls
# scant alleen de rest. Vijf pagina's bij twee per puls = binnen drie dagpulsen een volledige week.
#
# De bovengrens hangt niet aan het aantal pogingen maar aan VOORTGANG: twee pulsen op rij zonder één
# nieuwe pagina betekent dat hervatten niets meer oplevert. Dan sluit de week, hoort compliance het,
# en ligt er een capaciteitsgat. Zo blijft "morgen weer" nooit een stil abonnement op een blinde vlek,
# en wordt een langzame-maar-vorderende scan niet ten onrechte als vastgelopen afgeschreven.
MAX_PULSEN_ZONDER_VOORTGANG = 2


def _rol_voor(categorie: str) -> str:
    """De rol-routing van de checker, hier hergebruikt zodat een wekelijkse bevinding bij
    dezelfde rol landt als een handmatige."""
    from nooch_village.views.claims import rol_voor
    return rol_voor(categorie)


def week_gedaan(data_dir: str, week: str) -> bool:
    """Is deze ISO-week VOLLEDIG gedekt?

    Volledig = elke pagina uit de scan-set is deze week minstens één keer gelukt, eventueel verdeeld
    over meerdere pulsen. Een run die pagina's miste door een tijdelijke fout (429, timeout) schrijft
    `volledig: False` en sluit de week dus niet af. Zonder die voorwaarde zet één 429 de site een hele
    week in de blinde vlek. Oudere markers zonder het veld gelden als volledig."""
    marker = laatste_run(data_dir)
    return marker.get("last_week") == week and marker.get("volledig", True) is not False


def gedekt_deze_week(data_dir: str, week: str) -> list[str]:
    """De labels die deze week al met succes zijn opgehaald (leeg bij een nieuwe week).

    Dit is het geheugen dat de scan miste: zonder deze lijst begint elke puls bij pagina 1 en blijven
    de laatste pagina's van de set structureel ongezien."""
    marker = laatste_run(data_dir)
    if marker.get("last_week") != week:
        return []
    return [str(x) for x in (marker.get("gedekt") or []) if x]


def resterend(paginas: list[dict], gedekt) -> list[dict]:
    """De pagina's die deze week nog NIET gelukt zijn, in de volgorde van de scan-set.

    Bewust alleen de resterende en niet 'ongedekte eerst, daarna de rest': elk verzoek kost een token
    uit de rate-limit-bucket, en een token besteden aan een pagina die we deze week al zagen gaat
    rechtstreeks ten koste van een pagina die we nog niet zagen."""
    al_gezien = {str(g) for g in (gedekt or [])}
    return [p for p in paginas if (p.get("label") or p.get("url")) not in al_gezien]


def markeer_week(data_dir: str, week: str, uitkomst: dict | None = None) -> None:
    """Zet de weekmarker. Naast `last_week` gaat de uitkomst mee, zodat de rolpagina kan tonen
    wanneer de scan draaide en wat hij vond — zonder een tweede opslagplek.

    `pogingen` telt de pulsen in deze week. Die teller leeft in de marker en niet in het geheugen,
    want de daemon herstart en de puls draait één keer per dag."""
    from nooch_village.util import atomic_write_json
    vorige = laatste_run(data_dir)
    pogingen = int(vorige.get("pogingen", 0) or 0) if vorige.get("last_week") == week else 0
    try:
        atomic_write_json(os.path.join(data_dir, MARKER),
                          {"last_week": week, "at": time.time(), "pogingen": pogingen + 1,
                           **(uitkomst or {})})
    except Exception:
        pass                      # markeren mislukt = hooguit een dubbele scan, nooit een crash


def pulsen_zonder_voortgang(data_dir: str, week: str) -> int:
    """Hoeveel pulsen op rij deze week geen enkele NIEUWE pagina opleverden.

    Voortgang, niet pogingen, is het juiste signaal: een scan die elke puls één pagina toevoegt is
    langzaam maar gezond; een scan die twee pulsen niets toevoegt loopt vast en moet dat zeggen."""
    marker = laatste_run(data_dir)
    if marker.get("last_week") != week:
        return 0
    return int(marker.get("zonder_voortgang", 0) or 0)


def laatste_run(data_dir: str) -> dict:
    """Wat de rolpagina nodig heeft: de laatste weekmarker, of leeg als er nog niets draaide."""
    import json
    try:
        with open(os.path.join(data_dir, MARKER), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def scan_paginas(db: dict) -> list[dict]:
    """De vaste pagina-set uit de claims-database (compliance beheert die lijst, niet de code)."""
    return [p for p in (db.get("meta") or {}).get("scan_paginas", [])
            if isinstance(p, dict) and p.get("url")]


def verzamel(paginas: list[dict], db: dict, _fetch=None, ledger=None, _sleep=None,
             reason_fn=None, negatieven=None,
             modelpas: bool = True) -> tuple[list[dict], list[dict], dict, dict]:
    """Scan elke pagina en geef (bevindingen, fouten, paginateksten) terug. Elke bevinding draagt
    de pagina waar hij vandaan komt, zodat de taak een vindplaats heeft; de teksten gaan mee
    zodat de werklijst-verificatie tegen dezelfde waarneming kan toetsen.

    Elke fout draagt zijn soort (`tijdelijk`), zodat de caller een 429 anders kan behandelen dan een
    404: het eerste is 'kom later terug', het tweede is een kapotte scan-lijst.

    `ledger` is de Kroniek. Vóór het wegfilteren van groen stelt `claims_substantiatie` de bewijs-vraag:
    een claim zonder bevestigd record wordt oranje en blijft dus staan. Zonder ledger geldt niets als
    onderbouwd — fail-closed, nooit stil groen.

    `modelpas` laat daarnaast `claims_modelpas` zoeken naar claims die GEEN lijstterm raken. Fail-soft:
    zonder LLM levert die pas niets en is het resultaat exact het regex-pad.

    Het vierde element (`signalen`) draagt wat de caller nodig heeft voor de terugkoppeling en de
    gat-oogst: weggewuifde vlaggen, onzekere modelvondsten, ambigu bewijs en of de modelpas draaide."""
    # Beleefdheid geldt tegen een échte host. Een geïnjecteerde `_fetch` (test, demo) raakt geen
    # netwerk, dus daar wachten we niet — anders koopt elke test de backoff in echte seconden.
    if _sleep is not None:
        slaap = _sleep
    elif _fetch is not None:
        def slaap(_seconden):
            return None
    else:
        slaap = time.sleep
    bevindingen, fouten, teksten = [], [], {}
    signalen = {"gewhitelist": [], "onzeker": [], "ambigu": [], "model_gevonden": 0,
                "modelpas_ok": 0, "modelpas_mislukt": 0, "modelpas_reden": ""}
    for nummer, pagina in enumerate(paginas):
        if nummer:
            slaap(PAUZE_SECONDEN)                        # beleefd tegen de host, en het voorkomt 429's
        label = pagina.get("label") or pagina["url"]
        try:
            # Eén poging (POGINGEN_PER_PAGINA=1): een mislukt verzoek verbruikt de rate-limit-bucket
            # net zo goed als een geslaagd, dus retryen kost dekking bij de volgende pagina's.
            opgehaald = safe_fetch.haal_tekst_geduldig(
                pagina["url"], pogingen=POGINGEN_PER_PAGINA, _fetch=_fetch, _sleep=slaap)
        except (safe_fetch.FetchGeweigerd, safe_fetch.FetchMislukt) as e:
            fouten.append({"label": label, "url": pagina["url"], "reden": str(e),
                           "tijdelijk": safe_fetch.is_tijdelijk(e)})
            continue
        teksten[label] = opgehaald["tekst"]
        uitslag = claims_db.check_tekst(opgehaald["tekst"], db)
        van_pagina = [{**b, "pagina": pagina.get("label", ""), "url": pagina["url"]}
                      for b in uitslag["bevindingen"]]

        # De recall-pas: kandidaten die GEEN lijstterm raken. Voegt toe, filtert nooit weg.
        if modelpas:
            pas = claims_modelpas.extra_kandidaten(
                opgehaald["tekst"], db, van_pagina, reason_fn=reason_fn,
                pagina=pagina.get("label", ""), url=pagina["url"], negatieven=negatieven)
            # Per pagina tellen, niet één vlag: de pas kan op de ene pagina draaien en op de andere
            # op een rate-limit stuiten. Eén vlag maakte daar 'niet gedraaid' van, terwijl er wél
            # kandidaten uitkwamen — en dat loog in beide richtingen.
            signalen["modelpas_ok" if pas["gedraaid"] else "modelpas_mislukt"] += 1
            if not pas["gedraaid"] and pas["reden"]:
                signalen["modelpas_reden"] = pas["reden"]
            van_pagina.extend(pas["kandidaten"])
            signalen["onzeker"].extend(pas["onzeker"])
            signalen["model_gevonden"] += len(pas["kandidaten"])

        signalen["ambigu"].extend(claims_substantiatie.pas_toe(van_pagina, ledger=ledger, db=db))
        claims_modelpas.weeg_bewijs(van_pagina)          # bewijs → oranje of escaleren, nooit rood
        for b in van_pagina:
            if b["stoplicht"] == "green":
                continue                                 # escaleren telt wél: compliance beslist
            uitzondering = claims_db.is_uitgezonderd(b, db)
            if uitzondering is not None:
                # Weggewuifd door een mens: geen taak, maar wél zichtbaar mét wie dat besloot.
                signalen["gewhitelist"].append({**b, "uitzondering": uitzondering})
                continue
            bevindingen.append(b)
    return bevindingen, fouten, teksten, signalen


def fout_tekst(fouten: list[dict], maximaal: int = 3) -> str:
    """De fouten als één leesbare regel, voor een escalatie of een heads-up."""
    return "; ".join(f"{f['label']}: {f['reden']}" for f in fouten[:maximaal])


def _wie_fixte(ledger, nr: int) -> str | None:
    """De rol die aan dit werklijst-item gewerkt heeft — die moet een regressie als eerste weten."""
    try:
        for p in ledger.all():
            if p.get("origin") == claims_board.ORIGIN and f"#{nr}" in str(p.get("description", "")):
                return p.get("owner")
    except Exception:
        pass
    return None


class ClaimsSiteScanSkill(Skill):
    name = "claims_site_scan"
    cost = "free"
    side_effect_free = False           # maakt taken aan op het bord
    required_env = ()
    description = ("Scant de vaste pagina-set van nooch.earth tegen de claims-database en zet "
                   "alleen NIEUWE rode/oranje bevindingen als taak bij de juiste rol. Eén volledige "
                   "dekking per ISO-week, desnoods verdeeld over meerdere pulsen als de host "
                   "pagina's tijdelijk weigert; wat al in de werklijst of op het bord staat wordt "
                   "overgeslagen.")
    input_schema = ("geen (optioneel: force: bool om de week-poort over te slaan met behoud van de "
                    "dekking · herstart: bool om de dekking van deze week weg te gooien)")
    output_schema = ("ok, week, skipped, gescand, gedekt[], paginas, volledig, nieuw, aangemaakt[], "
                     "overgeslagen, fouten[{label,url,reden,tijdelijk}], model_gevonden, "
                     "modelpas_ok, modelpas_mislukt, gewhitelist[], gaten[], headsup, escalate")

    def _verifieer_werklijst(self, context, db: dict, paginateksten: dict,
                             volledig: bool = True) -> list[dict]:
        """Toets de werklijst tegen wat we net zagen en sla de uitkomst op.

        Dit is de enige plek waar een skill de claims-database schrijft, en alleen het
        status-veld: termen, herformuleringen en landenregels blijven compliance-domein.
        Elke automatische wijziging krijgt `status_bron: auto`, zodat een mens altijd kan zien
        wie wat vond."""
        data_dir = getattr(context, "data_dir", ".")
        voorstellen = claims_verify.verifieer(db, paginateksten, volledig=volledig)
        if not voorstellen:
            return []
        try:
            levend = claims_db.load(data_dir=data_dir)   # effectief (seed + overlay), verse kopie
        except claims_db.ClaimsDbError:
            return []
        gewijzigd = claims_verify.pas_toe(levend, voorstellen)
        if not gewijzigd:
            return []
        # Statuswijzigingen landen in de runtime-overlay, niet in de getrackte seed (machine=True:
        # de auto-scan mag de AUTO_STATUSSEN zetten). Zo blijft config/claims_database.json schoon.
        for v in gewijzigd:
            try:
                claims_db.overlay_set_status(data_dir, v["nr"], v["naar"], machine=True)
            except (ValueError, TypeError):
                continue
        claims_verify.pas_toe(db, voorstellen)           # de scan-dict meetrekken
        for v in gewijzigd:
            if v["naar"] != claims_db.AUTO_REGRESSIE:
                continue
            # Een regressie gaat naar wie hem gefixt had én altijd naar compliance.
            tekst = f"↩️ Werklijst #{v['nr']} staat weer op de site — {v['reden']}"
            eigenaar = _wie_fixte(context.projects, v["nr"])
            if eigenaar:
                claims_board.bericht_aan_rol(context, eigenaar, tekst)
            claims_board.bericht_aan_rol(context, "compliance", tekst)
        return gewijzigd

    def _kroniek(self, context):
        """De Kroniek waartegen de bewijs-vraag wordt gesteld. Zelfde resolutie-idioom als
        `weten_we_dit_al`: een injectie uit de context wint, anders het bestand naast de stores.
        Lukt zelfs dat niet, dan is er geen bewijs — en dan is niets onderbouwd (fail-closed)."""
        ledger = getattr(context, "evidence_ledger", None) or getattr(context, "evidence", None)
        if ledger is not None:
            return ledger
        try:
            from nooch_village.evidence_ledger import EvidenceLedger
            return EvidenceLedger(os.path.join(getattr(context, "data_dir", "."),
                                               "evidence_ledger.jsonl"))
        except Exception:                                # noqa: BLE001
            return None

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        data_dir = getattr(context, "data_dir", ".")
        week = period_key("week")
        if not (payload.get("force") or payload.get("herstart")) and week_gedaan(data_dir, week):
            return {"ok": True, "week": week, "skipped": True, "reden": "deze week al gescand"}

        try:
            db = claims_db.load(data_dir=data_dir)
        except claims_db.ClaimsDbError as e:
            return {"ok": False, "week": week, "escalate": {"reason": f"claims-database onleesbaar: {e}"}}

        paginas = scan_paginas(db)
        if not paginas:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen scan-paginas in de claims-database (meta.scan_paginas)"}}

        # `herstart` gooit de dekking van deze week weg en begint opnieuw bij pagina 1 — de expliciete
        # weg om een week over te doen. `force` slaat alléén de week-poort over en respecteert de
        # dekking, zodat een handmatige duw de scan vooruit helpt in plaats van dezelfde eerste
        # pagina's nog eens te halen (precies de fout die deze versie repareert).
        gedekt = [] if payload.get("herstart") else gedekt_deze_week(data_dir, week)
        te_doen = resterend(paginas, gedekt)
        if not te_doen:
            markeer_week(data_dir, week, {"gedekt": [p.get("label") or p["url"] for p in paginas],
                                          "paginas": len(paginas), "volledig": True})
            return {"ok": True, "week": week, "skipped": True,
                    "reden": "alle pagina's zijn deze week al gedekt"}

        bevindingen, fouten, paginateksten, signalen = verzamel(
            te_doen, db, _fetch=payload.get("_fetch"), ledger=self._kroniek(context),
            _sleep=payload.get("_sleep"), reason_fn=payload.get("_reason"),
            negatieven=claims_labels.negatieven(data_dir),
            modelpas=payload.get("modelpas", True))
        if len(fouten) == len(te_doen) and not gedekt:
            # Niets gelukt én niets eerder gedekt: dat is geen 'schone site', dat is een kapotte scan.
            return {"ok": False, "week": week, "gescand": 0, "fouten": fouten,
                    "escalate": {"reason": "geen enkele pagina kon worden opgehaald: "
                                           + fout_tekst(fouten)}}

        if getattr(context, "projects", None) is None:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen projectenbord beschikbaar in de context"}}
        verslag = claims_board.zet_op_bord(
            context, db, bevindingen,
            bron=f"wekelijkse site-scan {week}", rol_voor=_rol_voor, trigger="role")

        # Tijdelijk versus permanent:
        #   tijdelijk (429/5xx/timeout) → de week NIET afsluiten; de volgende puls pakt de rest op.
        #   permanent (404/410/geweigerd) → die pagina blokkeert de week niet, anders zet één dode
        #   pagina in de scan-lijst de wekelijkse scan voor altijd vast. Het is dan een lijst-probleem,
        #   en dat is compliance-domein: het gaat als bericht naar de eigenaar van `meta.scan_paginas`.
        tijdelijk = [f for f in fouten if f["tijdelijk"]]
        permanent = [f for f in fouten if not f["tijdelijk"]]
        nieuw_gedekt = sorted(set(gedekt) | set(paginateksten))
        # Een permanent dode pagina telt als 'afgehandeld' voor de dekking: hij komt nooit meer,
        # en de mens is erover geïnformeerd. Anders houdt hij de week eeuwig open.
        afgeschreven = {f["label"] for f in permanent}
        alle_labels = {p.get("label") or p["url"] for p in paginas}
        dekking_compleet = alle_labels <= set(nieuw_gedekt) | afgeschreven
        # Bovengrens op VOORTGANG, niet op pogingen: leverde deze puls geen enkele nieuwe pagina op?
        zonder_voortgang = (0 if set(paginateksten) - set(gedekt)
                            else pulsen_zonder_voortgang(data_dir, week) + 1)
        vastgelopen = not dekking_compleet and zonder_voortgang >= MAX_PULSEN_ZONDER_VOORTGANG
        # De werklijst-verificatie mag alleen 'opgelost' concluderen als de hele set gezien is: een
        # claim die 'sitewide' staat kan op een pagina zitten die deze week nog niet gehaald is.
        statussen = self._verifieer_werklijst(context, db, paginateksten,
                                              volledig=dekking_compleet)
        markeer_week(data_dir, week, {"nieuw": len(verslag["aangemaakt"]),
                                      "overgeslagen": verslag["overgeslagen"],
                                      "gescand": len(paginateksten),
                                      "gedekt": nieuw_gedekt,
                                      "paginas": len(paginas),
                                      "statussen": len(statussen),
                                      "volledig": dekking_compleet or vastgelopen,
                                      "vastgelopen": vastgelopen,
                                      "zonder_voortgang": zonder_voortgang,
                                      "onbereikbaar": [f["label"] for f in tijdelijk],
                                      "fouten": fout_tekst(fouten, 5)})
        for f in permanent:
            claims_board.bericht_aan_rol(
                context, "compliance",
                f"🧭 Scan-lijst: '{f['label']}' is niet meer op te halen ({f['reden']}) — "
                f"werk meta.scan_paginas bij ({f['url']})")

        if vastgelopen:
            # Eén bericht aan compliance, met de pagina's die vanaf de server niet leesbaar zijn.
            # Compliance bezit de scan-lijst; dit is hun beslissing (andere bron, andere route).
            claims_board.bericht_aan_rol(
                context, "compliance",
                f"🚧 Site-scan blijft blind op {len(tijdelijk)} pagina('s): "
                f"{', '.join(f['label'] for f in tijdelijk)} — {fout_tekst(tijdelijk, 1)}. "
                f"Al {MAX_PULSEN_ZONDER_VOORTGANG} pulsen geen enkele nieuwe pagina erbij.")
        gaten = self._oogst_gaten(data_dir, signalen, verslag, bevindingen, tijdelijk, vastgelopen)
        headsup = self._headsup(verslag, statussen, tijdelijk, permanent, signalen, vastgelopen,
                                len(nieuw_gedekt), len(paginas))
        # Een schone scan is een ANTWOORD ("de site is compliant"), geen kennisgat. Zonder dit
        # leest een geslaagde scan zonder bevindingen als ontbrekende kennis — en dat is precies
        # het soort valse gat waar de missie-critic op zakt.
        schoon = (not verslag["aangemaakt"] and not bevindingen and not fouten
                  and not tijdelijk and not permanent)
        extra = ({"no_data": True,
                  "reason": (f"{len(paginateksten)} pagina('s) gescand, geen enkele claim-bevinding "
                             f"en geen bronfout — de site is op deze punten schoon")}
                 if schoon else {})
        return {"ok": True, "week": week, "skipped": False, "headsup": headsup, **extra,
                "statussen": statussen,
                "gescand": len(paginateksten), "gedekt": nieuw_gedekt, "paginas": len(paginas),
                "fouten": fouten,
                "volledig": dekking_compleet or vastgelopen, "vastgelopen": vastgelopen,
                "nieuw": len(verslag["aangemaakt"]), "aangemaakt": verslag["aangemaakt"],
                "overgeslagen": verslag["overgeslagen"], "rood": verslag["rood"],
                "model_gevonden": signalen["model_gevonden"],
                "modelpas_ok": signalen["modelpas_ok"],
                "modelpas_mislukt": signalen["modelpas_mislukt"],
                "gewhitelist": signalen["gewhitelist"], "gaten": gaten,
                "escalate": None}

    # ── De gat-oogst: opschrijven waar de tool zwak is, op het moment dat het pijn doet ──────────
    # Drie soorten onvermogen, alle drie `missing_capability` (software zou dit kunnen). De bevinding
    # wordt in ALLE gevallen gewoon gevlagd — het gat is een aantekening, geen excuus om te zwijgen.
    GAT_GEEN_MODELPAS = "LLM-pas voor claims zonder lijstterm"
    GAT_CLASSIFICATIE = "claim-classificatie zonder wettelijke bron"
    GAT_SUBSTANTIATIE = "claim-substantiatie niet machinaal vast te stellen"
    GAT_ONLEESBARE_PAGINA = "eigen pagina lezen zonder door de edge geblokkeerd te worden"

    def _oogst_gaten(self, data_dir: str, signalen: dict, verslag: dict, bevindingen: list[dict],
                     tijdelijk: list[dict] | None = None,
                     vastgelopen: bool = False) -> list[dict]:
        """Leg per onbeslisbaar geval één capaciteitsgat vast in de gat-ledger van de Codie-backlog.

        Het project-id van de taak die uit de bevinding kwam gaat mee waar dat kan: `gap_ledger`
        rangschikt clusters op het aantal GEBLOKKEERDE PROJECTEN, dus zonder die koppeling zou een
        echt terugkerend gat onderaan de backlog blijven staan."""
        pid_van = {claims_board.normaliseer(t.get("gevonden", "")): t["pid"]
                   for t in verslag["aangemaakt"] if t.get("gevonden")}

        def leg_vast(capability: str, tekst: str, gevonden: str = "") -> dict | None:
            return gap_ledger.record(
                data_dir, role="compliance", item_text=tekst,
                project_id=pid_van.get(claims_board.normaliseer(gevonden), ""),
                reason=gap_ledger.MISSING_CAPABILITY, capability=capability)

        gaten = []
        mislukt = signalen["modelpas_mislukt"]
        if mislukt:
            # Op minstens één pagina kon de recall-pas niet draaien. Dat is een blinde vlek, ook als
            # hij het elders wél deed — daarom telt hier de pagina, niet de run.
            totaal = mislukt + signalen["modelpas_ok"]
            gaten.append(leg_vast(
                self.GAT_GEEN_MODELPAS,
                f"op {mislukt} van {totaal} pagina('s) kon de scan geen claims zonder lijstterm "
                f"zoeken ({signalen['modelpas_reden'] or 'geen LLM beschikbaar'}); daar gold alleen "
                f"de regex"))
        for b in signalen["onzeker"]:
            gaten.append(leg_vast(
                self.GAT_CLASSIFICATIE,
                f"kon niet vaststellen of dit een claim is: '{(b.get('gevonden') or [''])[0][:120]}' "
                f"({b.get('pagina', '')})", (b.get("gevonden") or [""])[0]))
        if vastgelopen:
            # Het scherpste capaciteitsgat van deze skill: we kunnen onze EIGEN pagina niet lezen.
            # Dat is een bouwbaar probleem (andere route of andere bron), dus het hoort in de backlog.
            gaten.append(leg_vast(
                self.GAT_ONLEESBARE_PAGINA,
                f"{len(tijdelijk or [])} eigen pagina('s) na {MAX_PULSEN_ZONDER_VOORTGANG} pulsen "
                f"zonder voortgang nog niet op te halen vanaf de server: "
                f"{', '.join(f['label'] for f in (tijdelijk or []))} — {fout_tekst(tijdelijk or [], 1)}"))
        for b in signalen["ambigu"]:
            gaten.append(leg_vast(
                self.GAT_SUBSTANTIATIE,
                f"bewijs raakt de claim maar gedeeltelijk: '{(b.get('gevonden') or [''])[0][:120]}' "
                f"({b.get('pagina', '')}) — {b.get('onderbouwing_reden', '')[:120]}",
                (b.get("gevonden") or [""])[0]))
        return [g for g in gaten if g]

    def _headsup(self, verslag: dict, statussen: list[dict], tijdelijk: list[dict],
                 permanent: list[dict], signalen: dict | None = None,
                 vastgelopen: bool = False, gedekt: int = 0, totaal: int = 0) -> str | None:
        """Wat de mens moet zien. De generieke pulslaag stuurt dit door naar de founder.

        Alleen bij ROOD (oranje is werk voor de rol, geen alarm voor de founder) of bij een
        regressie — plus altijd een regel als de scan pagina's niet zag: een onvolledige scan die
        'niets gevonden' meldt is precies de stille fout die dit ritme moet uitsluiten."""
        regressies = [s for s in statussen if s["naar"] == claims_db.AUTO_REGRESSIE]
        kern = None
        if regressies:
            # Een teruggekeerde claim weegt zwaarder dan een nieuwe: iemand dacht dat dit af was.
            kern = (f"↩️ Claim-regressie: {len(regressies)} eerder opgeloste claim(s) staan "
                    f"weer op de site (#{', #'.join(str(r['nr']) for r in regressies)})")
        elif verslag["rood"]:
            # Spiegel van de regressie-tak: mét identifiers. Een telling alleen dwingt de mens de
            # cockpit te openen om te weten of dit erg is; term + pagina zegt dat meteen.
            kern = (f"🔴 Claim-scan: {verslag['rood']} nieuwe verboden claim(s) op nooch.earth "
                    f"— {claims_board.vindplaatsen(verslag['aangemaakt'], stoplicht='red')} "
                    f"({len(verslag['aangemaakt'])} taak/taken op het bord)")
        # Modelvondsten die tot een taak leidden: die verdienen een eigen regel, want een claim die
        # geen lijstterm raakt is precies wat de scan tot nu toe miste.
        model = [t for t in verslag["aangemaakt"] if t.get("herkomst") == claims_modelpas.HERKOMST]
        if model:
            regel = (f"{len(model)} model-gevonden claim(s) zonder lijstterm "
                     f"— {claims_board.vindplaatsen(model)} (vermoeden, geen wet)")
            kern = f"{kern} · {regel}" if kern else f"🟠 Claim-scan: {regel}"
        gemist = []
        if tijdelijk and vastgelopen:
            # Hervatten is geen oplossing meer: dit is een structureel probleem tussen de server en
            # de site (bv. een edge die dit IP throttelt). De mens moet dat weten in plaats van elke
            # dag opnieuw 'we proberen het morgen' te lezen.
            gemist.append(f"{gedekt} van {totaal} pagina's gedekt en al "
                          f"{MAX_PULSEN_ZONDER_VOORTGANG} pulsen geen nieuwe erbij "
                          f"({fout_tekst(tijdelijk, 2)}) — dit lost zichzelf niet op, de scan "
                          f"blijft blind op {', '.join(f['label'] for f in tijdelijk)}")
        elif tijdelijk:
            gemist.append(f"{gedekt} van {totaal} pagina's deze week gedekt; "
                          f"{', '.join(f['label'] for f in tijdelijk)} volgt bij de volgende puls "
                          f"({fout_tekst(tijdelijk, 1)})")
        if permanent:
            gemist.append(f"{len(permanent)} pagina('s) bestaan niet meer "
                          f"({fout_tekst(permanent, 2)}) — scan-lijst bijwerken")
        if not gemist:
            return kern
        staart = "⚠️ Scan onvolledig: " + "; ".join(gemist)
        return f"{kern} · {staart}" if kern else staart
