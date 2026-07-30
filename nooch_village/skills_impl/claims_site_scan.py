"""claims_site_scan — de wekelijkse zelf-scan van nooch.earth door compliance.

Verschil met `claims_check`: die skill is puur lokaal en toetst tekst die je hem geeft. Deze
skill haalt zélf de vaste pagina-set op (server-side, via `safe_fetch` met SSRF-guardrail) en
levert alleen NIEUWE bevindingen — wat al in de werklijst staat of al als taak loopt, telt niet.

Vier regels:
1. **Idempotent per week.** Een tweede puls in dezelfde ISO-week doet niets. De weekmarker
   wordt pas ná een geslaagde run gezet, zodat een mislukte run volgende puls opnieuw mag.
   Een run die niet ALLE pagina's kon halen door een tijdelijke fout sluit de week niet af.
2. **Fail-closed.** Alle pagina's onbereikbaar of de database corrupt → `escalate`, nooit een
   stille nul. "Geen bevindingen" moet betekenen dat er niets was, niet dat er niets werkte.
3. **Bewijs-eerst.** Een milieuclaim is alleen groen als de Kroniek hem onderbouwt; zonder
   bevestigd record wordt hij oranje "onderbouwing ontbreekt" (`claims_substantiatie`).
4. **Geen bord-ruis.** Niets nieuws → één logregel, geen taken, geen heads-up.
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
PAUZE_SECONDEN = 1.5
POGINGEN_PER_PAGINA = 3

# Totale wachttijd die één scan mag opsouperen. Shopify vraagt bij een 429 om 60 seconden per
# pagina; met vijf pagina's en drie pogingen zou een run tien minuten kunnen hangen. Dit budget is
# de middenweg: wacht zolang het zin heeft en laat de rest als TIJDELIJKE fout vallen — die pagina's
# sluiten de week niet af en worden bij de volgende puls opnieuw geprobeerd.
WACHTBUDGET_SECONDEN = 240.0


def _rol_voor(categorie: str) -> str:
    """De rol-routing van de checker, hier hergebruikt zodat een wekelijkse bevinding bij
    dezelfde rol landt als een handmatige."""
    from nooch_village.views.claims import rol_voor
    return rol_voor(categorie)


def week_gedaan(data_dir: str, week: str) -> bool:
    """Is deze ISO-week VOLLEDIG gescand?

    Een run die pagina's miste door een tijdelijke fout (429, timeout) schrijft `volledig: False` en
    sluit de week dus niet af — de volgende puls pakt de rest. Zonder die voorwaarde zet één 429 de
    site een hele week in de blinde vlek. Oudere markers zonder het veld gelden als volledig."""
    import json
    try:
        with open(os.path.join(data_dir, MARKER), encoding="utf-8") as f:
            marker = json.load(f)
        return marker.get("last_week") == week and marker.get("volledig", True) is not False
    except Exception:
        return False


# Hoeveel pulsen mag een week onvolledig blijven voordat de mens het hoort? Het hervatten is de
# kracht van de tijdelijke-fout-regel, maar zonder bovengrens wordt "we proberen het morgen weer"
# een stil abonnement op een blinde vlek. Drie dagpulsen: één slechte dag mag, drie is een probleem
# dat een mens moet weten.
MAX_ONVOLLEDIGE_POGINGEN = 3


def markeer_week(data_dir: str, week: str, uitkomst: dict | None = None) -> None:
    """Zet de weekmarker. Naast `last_week` gaat de uitkomst mee, zodat de rolpagina kan tonen
    wanneer de scan draaide en wat hij vond — zonder een tweede opslagplek.

    `pogingen` telt hoeveel keer deze week al een ONVOLLEDIGE run draaide. Die teller leeft in de
    marker en niet in het geheugen, want de daemon herstart en de puls draait één keer per dag."""
    from nooch_village.util import atomic_write_json
    vorige = laatste_run(data_dir)
    pogingen = int(vorige.get("pogingen", 0) or 0) if vorige.get("last_week") == week else 0
    try:
        atomic_write_json(os.path.join(data_dir, MARKER),
                          {"last_week": week, "at": time.time(), "pogingen": pogingen + 1,
                           **(uitkomst or {})})
    except Exception:
        pass                      # markeren mislukt = hooguit een dubbele scan, nooit een crash


def onvolledige_pogingen(data_dir: str, week: str) -> int:
    """Hoe vaak deze week al een onvolledige run draaide (0 als de week nog niet begon)."""
    marker = laatste_run(data_dir)
    if marker.get("last_week") != week or marker.get("volledig", True) is not False:
        return 0
    return int(marker.get("pogingen", 0) or 0)


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
    budget = safe_fetch.Wachtbudget(WACHTBUDGET_SECONDEN)
    for nummer, pagina in enumerate(paginas):
        if nummer:
            slaap(PAUZE_SECONDEN)                        # beleefd tegen de host, en het voorkomt 429's
        label = pagina.get("label") or pagina["url"]
        try:
            opgehaald = safe_fetch.haal_tekst_geduldig(
                pagina["url"], pogingen=POGINGEN_PER_PAGINA, budget=budget, _fetch=_fetch,
                _sleep=slaap)
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
                   "alleen NIEUWE rode/oranje bevindingen als taak bij de juiste rol. Eén keer "
                   "per ISO-week; wat al in de werklijst of op het bord staat wordt overgeslagen.")
    input_schema = "geen (optioneel: force: bool om de week-gate over te slaan)"
    output_schema = ("ok, week, skipped, gescand, paginas, volledig, nieuw, aangemaakt[], "
                     "overgeslagen, fouten[{label,url,reden,tijdelijk}], model_gevonden, "
                     "modelpas_ok, modelpas_mislukt, gewhitelist[], gaten[], headsup, escalate")

    def _verifieer_werklijst(self, context, db: dict, paginateksten: dict) -> list[dict]:
        """Toets de werklijst tegen wat we net zagen en sla de uitkomst op.

        Dit is de enige plek waar een skill de claims-database schrijft, en alleen het
        status-veld: termen, herformuleringen en landenregels blijven compliance-domein.
        Elke automatische wijziging krijgt `status_bron: auto`, zodat een mens altijd kan zien
        wie wat vond."""
        data_dir = getattr(context, "data_dir", ".")
        voorstellen = claims_verify.verifieer(db, paginateksten)
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
        if not payload.get("force") and week_gedaan(data_dir, week):
            return {"ok": True, "week": week, "skipped": True, "reden": "deze week al gescand"}

        try:
            db = claims_db.load(data_dir=data_dir)
        except claims_db.ClaimsDbError as e:
            return {"ok": False, "week": week, "escalate": {"reason": f"claims-database onleesbaar: {e}"}}

        paginas = scan_paginas(db)
        if not paginas:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen scan-paginas in de claims-database (meta.scan_paginas)"}}

        bevindingen, fouten, paginateksten, signalen = verzamel(
            paginas, db, _fetch=payload.get("_fetch"), ledger=self._kroniek(context),
            _sleep=payload.get("_sleep"), reason_fn=payload.get("_reason"),
            negatieven=claims_labels.negatieven(data_dir),
            modelpas=payload.get("modelpas", True))
        if len(fouten) == len(paginas):
            # Alle pagina's onbereikbaar: dat is geen 'schone site', dat is een kapotte scan.
            return {"ok": False, "week": week, "gescand": 0, "fouten": fouten,
                    "escalate": {"reason": "geen enkele pagina kon worden opgehaald: "
                                           + fout_tekst(fouten)}}

        if getattr(context, "projects", None) is None:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen projectenbord beschikbaar in de context"}}
        verslag = claims_board.zet_op_bord(
            context, db, bevindingen,
            bron=f"wekelijkse site-scan {week}", rol_voor=_rol_voor, trigger="role")
        statussen = self._verifieer_werklijst(context, db, paginateksten)

        # Tijdelijk versus permanent (de reden dat 4 van 5 pagina's stil wegvielen):
        #   tijdelijk (429/5xx/timeout) → de week NIET afsluiten; de volgende puls pakt de rest op.
        #   permanent (404/410/geweigerd) → de week mág dicht, anders zet één dode pagina in de
        #   scan-lijst de wekelijkse scan voor altijd vast. Het is dan een lijst-probleem, en dat is
        #   compliance-domein: het gaat als bericht naar de eigenaar van `meta.scan_paginas`.
        tijdelijk = [f for f in fouten if f["tijdelijk"]]
        permanent = [f for f in fouten if not f["tijdelijk"]]
        # Hervatten heeft een bovengrens. Blijft een pagina MAX_ONVOLLEDIGE_POGINGEN pulsen op slot,
        # dan is 'morgen weer' een stil abonnement op een blinde vlek geworden: dan sluit de week
        # (anders draait de scan elke dag opnieuw voor niets) en hoort de mens het expliciet.
        vastgelopen = bool(tijdelijk) and onvolledige_pogingen(data_dir, week) + 1 >= MAX_ONVOLLEDIGE_POGINGEN
        markeer_week(data_dir, week, {"nieuw": len(verslag["aangemaakt"]),
                                      "overgeslagen": verslag["overgeslagen"],
                                      "gescand": len(paginas) - len(fouten),
                                      "paginas": len(paginas),
                                      "statussen": len(statussen),
                                      "volledig": not tijdelijk or vastgelopen,
                                      "vastgelopen": vastgelopen,
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
                f"Al {MAX_ONVOLLEDIGE_POGINGEN} pulsen niet op te halen vanaf de server.")
        gaten = self._oogst_gaten(data_dir, signalen, verslag, bevindingen, tijdelijk, vastgelopen)
        headsup = self._headsup(verslag, statussen, tijdelijk, permanent, signalen, vastgelopen)
        return {"ok": True, "week": week, "skipped": False, "headsup": headsup,
                "statussen": statussen,
                "gescand": len(paginas) - len(fouten), "paginas": len(paginas), "fouten": fouten,
                "volledig": not tijdelijk or vastgelopen, "vastgelopen": vastgelopen,
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
                f"{len(tijdelijk or [])} eigen pagina('s) al {MAX_ONVOLLEDIGE_POGINGEN} pulsen niet "
                f"op te halen vanaf de server: "
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
                 vastgelopen: bool = False) -> str | None:
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
            gemist.append(f"{len(tijdelijk)} pagina('s) al {MAX_ONVOLLEDIGE_POGINGEN} pulsen niet "
                          f"op te halen vanaf de server ({fout_tekst(tijdelijk, 2)}) — dit lost "
                          f"zichzelf niet op, de scan blijft hier blind")
        elif tijdelijk:
            gemist.append(f"{len(tijdelijk)} pagina('s) tijdelijk niet op te halen "
                          f"({fout_tekst(tijdelijk, 2)}) — de volgende puls pakt ze opnieuw")
        if permanent:
            gemist.append(f"{len(permanent)} pagina('s) bestaan niet meer "
                          f"({fout_tekst(permanent, 2)}) — scan-lijst bijwerken")
        if not gemist:
            return kern
        staart = "⚠️ Scan onvolledig: " + "; ".join(gemist)
        return f"{kern} · {staart}" if kern else staart
