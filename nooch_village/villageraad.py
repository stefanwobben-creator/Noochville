"""Villageraad — de council-pass: elke rol leest de Kroniek en zijn eigen pagina's.

Een raad is geen vergadering waarin iedereen iets mag vinden. Het is een ronde waarin elke rol,
vanuit zijn eigen purpose en accountabilities, naar het bewijsregister en naar zijn eigen pagina's
kijkt en zegt wat er niet klopt. Wat hij ziet moet ergens aan vastzitten — een Kroniek-record of een
pagina — anders is het een mening, en meningen horen niet in een agenda.

**Geen grond, geen spanning.** Dit is de hele discipline van deze module. Elke observatie hieronder
is een VERGELIJKING op bestaande data (faalde deze bron twee keer op rij; draagt dit feit nog; wijst
deze verwijzing ergens heen) en draagt het id van datgene waarop hij rust. Een rol die niets vindt
zegt dat hardop; hij verzint geen agendapunt om aan tafel iets te zeggen te hebben. Zelfde regel als
bij `wiki.grond_status`: de uitkomst wordt bij het LEZEN berekend en nooit als oordeel opgeslagen.

De pijplijn erna is de bestaande, niet een tweede:

    observatie  →  bevinding.herschrijf   (wat is er aan de hand, wat wil ik — in gewone taal)
                →  zelf_verwerking.verwerk (zelf / naar rol / governance / founder)
                →  NotifStore.add          (alleen als het de rol verlaat)

Twee dingen die de pass NIET doet, en waarom:

* **Een bevinding die de poort niet haalt wordt niet verzonden.** `bevinding.keur` is deterministisch;
  zakt de tekst erdoor, dan blijft de spanning hangen mét reden. Een halve kaart bij iemand op het
  bureau is erger dan een zichtbaar onaf item in het verslag.
* **Niets wordt twee keer opgeworpen.** Elke verwerkte observatie landt in `data/villageraad.jsonl`
  op sleutel (rol, soort, anker). Een tweede ronde ziet dezelfde dode bron opnieuw, herkent hem, en
  telt hem als 'al opgeworpen' in plaats van als nieuwe spanning.
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("village.villageraad")

BESTAND = "villageraad.jsonl"

# Hoeveel spanningen één rol per ronde mag opwerpen. Een raad waarin één rol dertig punten inbrengt
# is geen raad maar een dump; de zwaarste eerst, de rest staat in het verslag als 'niet ingebracht'
# (nooit stil afkappen — zie de no-silent-caps-regel).
CAP_PER_ROL = 3

# Twee keer op rij falen is een patroon, één keer is een storing. Zelfde drempel als de skill-ladder
# hanteert voor een dode route.
DODE_BRON_DREMPEL = 2
# Twee keer 'onderzocht, niets gevonden' op dezelfde skill is een kennisgat. Leeg ≠ fout: dit is een
# echt feit over de wereld, geen mislukking (B3), en dus een spanning van een andere soort.
KENNISGAT_DREMPEL = 2

# Ernst bepaalt alleen de VOLGORDE waarin een rol zijn punten inbrengt, niet of ze waar zijn.
ERNST = {
    "vervallen_grond":       5,   # een feit dat zijn bewijs heeft overleefd — dat is het ergste
    "dode_bron":             4,   # de rol kan iets niet meer ophalen
    "ongegronde_pagina":     3,   # beweringen zonder enige bron
    "domein_gat":            3,   # in mijn domein is iets onderzocht en het gaf niets
    "kennisgat":             2,
    "ongecontroleerde_bron": 2,
    "pagina_zonder_feiten":  1,
    "verweesde_verwijzing":  1,
}


# ── wie zit er aan tafel ────────────────────────────────────────────────────

def rollen(records) -> list:
    """De rollen die deelnemen: levend, geen cirkel. Een cirkel heeft geen handen (harde regel 7),
    dus hij senst ook niet — zijn leden doen dat."""
    from nooch_village import org

    uit = []
    for rec in (records.all() if records is not None else []):
        if getattr(rec, "archived", False):
            continue
        try:
            if org.is_circle(rec):
                continue
        except Exception:                                  # noqa: BLE001 — geen org-info = meedoen
            pass
        uit.append(rec)
    return uit


def _naam(rec) -> str:
    return getattr(getattr(rec, "definition", None), "name", "") or getattr(rec, "id", "")


def _accountabilities(rec) -> list[str]:
    return list(getattr(getattr(rec, "definition", None), "accountabilities", None) or [])


def _domeinen(rec) -> list[str]:
    return [str(d) for d in (getattr(getattr(rec, "definition", None), "domains", None) or [])]


def labels(recs: list, records) -> dict:
    """Rol-id → leesbare naam. Drie Circle Leads die allemaal "Circle Lead" heten zijn in een
    verslag niet uit elkaar te houden; een dubbele naam krijgt daarom de cirkel erachter."""
    namen = [_naam(r) for r in recs]
    uit = {}
    for rec, naam in zip(recs, namen):
        if namen.count(naam) > 1:
            ouder = records.get(getattr(rec, "parent", "") or "") if records is not None else None
            if ouder is not None:
                naam = f"{naam} ({_naam(ouder)})"
        uit[getattr(rec, "id", "")] = naam
    return uit


# ── de Kroniek, gelezen vanuit één rol ──────────────────────────────────────

def _laatste_per_vraag(rijen: list[dict]) -> dict:
    """De LAATSTE stand per (skill, query, bron). Een oude fout telt niet meer als diezelfde bron
    later bevestigde — dezelfde oprol-regel als `evidence_ledger.interpret`."""
    laatste: dict = {}
    for r in rijen:
        sleutel = (r.get("skill"), r.get("query"), r.get("source"))
        if sleutel not in laatste or r.get("ts", 0) >= laatste[sleutel].get("ts", 0):
            laatste[sleutel] = r
    return laatste


def _obs(rol: str, soort: str, anker: str, anker_soort: str, tekst: str, bewijs: str) -> dict:
    return {"rol": rol, "soort": soort, "ernst": ERNST.get(soort, 1), "anker": anker,
            "anker_soort": anker_soort, "tekst": " ".join(tekst.split()), "bewijs": bewijs}


def kroniek_observaties(rec, ledger) -> list[dict]:
    """Wat deze rol in het bewijsregister ziet dat niet klopt. Alleen zijn eigen sporen: een rol
    verantwoordt wat hij zelf ophaalde."""
    rol = getattr(rec, "id", "")
    if ledger is None or not rol:
        return []
    eigen = [r for r in ledger.all_records() if r.get("role_id") == rol]
    if not eigen:
        return []
    uit: list[dict] = []

    # 1. Dode bron — deze (skill, bron) faalde op rij. De teller komt uit de Kroniek zelf, zodat
    #    'op rij' hier hetzelfde betekent als bij de skill-ladder.
    gezien = set()
    for r in sorted(eigen, key=lambda x: -(x.get("ts") or 0)):
        skill, bron = str(r.get("skill") or ""), str(r.get("source") or "")
        if not skill or not bron or (skill, bron) in gezien or r.get("status") != "fout":
            continue
        gezien.add((skill, bron))
        n = ledger.consecutive_failures(skill, bron)
        if n < DODE_BRON_DREMPEL:
            continue
        uit.append(_obs(
            rol, "dode_bron", str(r.get("id") or ""), "kroniek",
            f"De bron {bron} faalde {n} keer op rij bij {skill}; de laatste poging ging over "
            f"“{str(r.get('query') or '')[:80]}”. Zolang die bron stil blijft kan ik dit niet meer "
            f"ophalen en rust alles wat ik erover zeg op oudere waarnemingen.",
            f"Kroniek-record {r.get('id')} ({skill} · {bron} · fout)"))

    # 2. Kennisgat — onderzocht, niets gevonden. Leeg is een echt feit, geen storing, en dus een
    #    andere spanning dan een dode bron: hier werkte de bron wél.
    leeg_per_skill: dict = {}
    for r in _laatste_per_vraag(eigen).values():
        if r.get("status") == "leeg":
            leeg_per_skill.setdefault(str(r.get("skill") or ""), []).append(r)
    for skill, rijen in leeg_per_skill.items():
        if len(rijen) < KENNISGAT_DREMPEL:
            continue
        nieuwste = max(rijen, key=lambda x: x.get("ts") or 0)
        vragen = "; ".join(str(x.get("query") or "")[:50] for x in rijen[:3])
        uit.append(_obs(
            rol, "kennisgat", str(nieuwste.get("id") or ""), "kroniek",
            f"Op {len(rijen)} vragen via {skill} gaf de bron niets terug — onderzocht, niets "
            f"gevonden. Het gaat onder meer om: {vragen}. Dat is geen storing maar een gat in wat "
            f"er te weten valt, en ik heb er nu geen tweede weg naartoe.",
            f"Kroniek-record {nieuwste.get('id')} ({skill} · leeg, {len(rijen)}x)"))
    return uit


def domein_observaties(rec, ledger) -> list[dict]:
    """Een gat in MIJN domein dat een ander achterliet.

    Alleen op domein, niet op een woord uit de accountability-tekst. Een domein dragen is een
    governance-besluit; een woord dat toevallig in een zoekvraag voorkomt is precies de trefwoord-val
    die `zelf_verwerking.domein_grens` weghaalt. Zonder domein dus geen tweede lens — fail-closed."""
    rol = getattr(rec, "id", "")
    doms = [d.strip().lower() for d in _domeinen(rec) if len(d.strip()) >= 4]
    if ledger is None or not rol or not doms:
        return []
    kandidaten = [r for r in ledger.all_records()
                  if r.get("role_id") != rol and r.get("status") in ("fout", "leeg")
                  and any(d in str(r.get("query") or "").lower() for d in doms)]
    if not kandidaten:
        return []
    nieuwste = max(kandidaten, key=lambda r: r.get("ts") or 0)
    dom = next(d for d in doms if d in str(nieuwste.get("query") or "").lower())
    return [_obs(
        rol, "domein_gat", str(nieuwste.get("id") or ""), "kroniek",
        f"In mijn domein “{dom}” liep {nieuwste.get('role_id')} vast: de vraag "
        f"“{str(nieuwste.get('query') or '')[:70]}” via {nieuwste.get('skill')} leverde niets op "
        f"({nieuwste.get('status')}). Ik cureer dit domein, dus dit gat is van mij, ook al deed "
        f"iemand anders de zoekpoging.",
        f"Kroniek-record {nieuwste.get('id')} ({nieuwste.get('skill')} · {nieuwste.get('status')})")]


# ── de eigen pagina's ───────────────────────────────────────────────────────

def pagina_observaties(rec, att, ledger, *, vandaag: str = "", alle_paginas=None) -> list[dict]:
    """Wat deze rol op zijn eigen pagina's ziet. De grond wordt hier opnieuw vergeleken — dat is de
    hele reden dat `wiki.grond_status` niets opslaat."""
    from nooch_village import wiki

    rol = getattr(rec, "id", "")
    if att is None or not rol:
        return []
    mijn = att.list(rol, wiki.PAGINA_KIND)
    if not mijn:
        return []
    pags = alle_paginas if alle_paginas is not None else wiki.paginas(att)
    uit: list[dict] = []
    for a in mijn:
        titel = a.title or a.id
        tel = wiki.telling(a, ledger=ledger, store=att, vandaag=vandaag)
        feiten = wiki.feiten(a)
        bewijs = f"pagina {a.id} “{titel}”"

        if tel.get(wiki.VERVALLEN):
            uit.append(_obs(
                rol, "vervallen_grond", a.id, "pagina",
                f"Op mijn pagina “{titel}” staan {tel[wiki.VERVALLEN]} feit(en) waarvan de "
                f"onderbouwing niet meer geldt: het certificaat is verlopen, de policy is "
                f"gearchiveerd of het aangehaalde citaat staat niet meer op de bron. De pagina "
                f"beweert dus iets wat ik nu niet meer waar kan maken.",
                bewijs))

        ongegrond = tel.get(wiki.ONGEGROND, 0) + tel.get(wiki.ONTBREEKT, 0)
        if ongegrond:
            uit.append(_obs(
                rol, "ongegronde_pagina", a.id, "pagina",
                f"Van de {len(feiten)} feiten op mijn pagina “{titel}” dragen er {ongegrond} geen "
                f"enkele bron, of de bron waar ze naar wijzen bestaat niet meer. Wie de pagina "
                f"leest ziet een bewering die nergens op rust.",
                bewijs))

        if feiten and tel.get(wiki.ONGECONTROLEERD, 0) == len(feiten):
            uit.append(_obs(
                rol, "ongecontroleerde_bron", a.id, "pagina",
                f"Alle {len(feiten)} feiten op mijn pagina “{titel}” wijzen wel naar een bron, maar "
                f"er heeft nog nooit iemand gekeken of die bron het ook echt zegt. Een aangehaalde "
                f"bron is herkomst, geen bewijs.",
                bewijs))

        if not feiten and len((a.body or "").strip()) >= 200:
            uit.append(_obs(
                rol, "pagina_zonder_feiten", a.id, "pagina",
                f"Mijn pagina “{titel}” staat vol tekst maar bevat geen enkel vastgelegd feit met "
                f"een bron. Alles wat er staat is daarmee onbewijsbaar geworden voor wie hem leest, "
                f"ook voor mijzelf als ik hem later als werkgeheugen gebruik.",
                bewijs))

        ontbrekend = wiki.ontbrekende_links(a, pags)
        if ontbrekend:
            uit.append(_obs(
                rol, "verweesde_verwijzing", a.id, "pagina",
                f"Mijn pagina “{titel}” verwijst naar {len(ontbrekend)} pagina('s) die niet "
                f"bestaan: {', '.join(ontbrekend[:4])}. Elke verwijzing is een stuk kennis waarvan "
                f"ik aannam dat het ergens stond, en dat staat er niet.",
                bewijs))
    return uit


def observaties_van(rec, *, ledger, att, vandaag: str = "", alle_paginas=None) -> list[dict]:
    """Alles wat deze rol gegrond ziet, zwaarste eerst."""
    obs = (kroniek_observaties(rec, ledger)
           + domein_observaties(rec, ledger)
           + pagina_observaties(rec, att, ledger, vandaag=vandaag, alle_paginas=alle_paginas))
    return sorted(obs, key=lambda o: -o["ernst"])


# ── het spoor: wat is er al eens opgeworpen ─────────────────────────────────

def sleutel(obs: dict) -> str:
    return f"{obs.get('rol')}|{obs.get('soort')}|{obs.get('anker')}"


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def eerder_opgeworpen(data_dir: str) -> set[str]:
    uit: set[str] = set()
    try:
        with open(pad(data_dir), encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    uit.add(str(json.loads(regel).get("sleutel") or ""))
                except ValueError:
                    continue
    except FileNotFoundError:
        return uit
    except OSError as e:                                   # noqa: BLE001
        log.warning("villageraad-spoor onleesbaar: %s", e)
    return uit


def leg_vast(data_dir: str, rij: dict) -> bool:
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**rij, "ts": time.time()}, ensure_ascii=False) + "\n")
        return True
    except OSError as e:                                   # noqa: BLE001
        log.warning("villageraad-spoor niet weggeschreven: %s", e)
        return False


# ── één observatie door de bestaande pijplijn ───────────────────────────────

def _snippet(obs: dict) -> str:
    """De ruwe signalering zoals hij op de kaart onder “ruwe signalering” komt te staan.

    De store kapt op 160 tekens, dus het BEWIJS staat vooraan: een kaart waarvan het anker is
    weggevallen is precies de kaart die niemand kan natrekken."""
    return f"{obs['bewijs']} — {obs['tekst']}"[:160]


def verwerk_observatie(obs: dict, *, records, reason_fn=None, data_dir: str = "") -> dict:
    """Bevinding schrijven en het type bepalen. Geeft de volledige regel voor het verslag.

    `verzendbaar` is de poort van `bevinding.keur`: haalt de tekst hem niet, dan blijft de spanning
    hangen mét reden in plaats van als halve kaart bij iemand te landen."""
    from nooch_village import bevinding as bv, zelf_verwerking as zv

    rol = obs["rol"]
    b = bv.herschrijf(obs["tekst"], rol=rol, records=records, reason_fn=reason_fn)
    t = zv.verwerk(obs["tekst"], rol=rol, records=records, reason_fn=reason_fn,
                   voorstel=b.get("voorstel") or "", data_dir=data_dir)
    return {**obs, "sleutel": sleutel(obs), "bevinding": b, "type": t.get("uitkomst"),
            "verwerking": t, "verzendbaar": bool(b.get("ok")),
            "reden_niet_verzendbaar": "" if b.get("ok") else str(b.get("reden") or "")}


def kaart(rij: dict, records) -> dict:
    """De getypeerde kaart: wie werpt dit op, vanuit welke eigen verantwoordelijkheid, wat is er
    gevonden, wat stelt hij voor, wat heeft hij nodig, en waarop rust het."""
    from nooch_village import founder_kaart as fk, zelf_verwerking as zv

    rol_id = rij["rol"]
    rec = records.get(rol_id) if records is not None else None
    naam = rij.get("rol_naam") or (_naam(rec) if rec is not None else rol_id)
    t = dict(rij.get("verwerking") or {})
    b = dict(rij.get("bevinding") or {})
    behoefte = t.get("behoefte") or ""
    return {
        "type":           rij.get("type") or "",
        "type_label":     zv.TYPE_LABEL.get(rij.get("type") or "", "?"),
        "rol_id":         rol_id,
        "rol":            naam,
        "vanuit":         (t.get("eigen_accountability")
                           or fk.eigen_accountability(rol_id, rij["tekst"], records)
                           or "geen eigen accountability raakt dit — het kwam uit het bewijs, "
                              "niet uit een taak"),
        "bevinding":      b.get("spanning") or rij["tekst"],
        "voorstel":       b.get("voorstel") or "",
        "wat_nodig":      behoefte or t.get("reden") or "",
        "bewijs":         rij["bewijs"],
        "anker":          rij["anker"],
        "anker_soort":    rij["anker_soort"],
        "verzendbaar":    bool(rij.get("verzendbaar")),
        "reden":          rij.get("reden_niet_verzendbaar") or "",
    }


def ontvanger_van(rij: dict, records, assignments) -> dict:
    """Op wiens bureau landt dit? `{"rol", "reden"}`; lege rol = nergens, mét reden.

    Governance en founder gaan naar de founder-rol: allebei vragen ze een besluit dat alleen daar
    genomen wordt. Een operationeel verzoek gaat naar de rol die het werk bezit — maar via dezelfde
    omleiding als een pagina-voorstel, want een rol zonder menselijke vervuller leest zijn postbus
    nooit en dan is de kaart een dode brief."""
    from nooch_village import founder_kaart as fk, wiki, zelf_verwerking as zv

    soort = rij.get("type")
    if soort in (zv.GOVERNANCE, zv.FOUNDER):
        if records is not None and records.get(fk.FOUNDER_ROL) is None:
            return {"rol": "", "reden": "de founder-rol bestaat niet in de records"}
        return {"rol": fk.FOUNDER_ROL, "reden": ""}
    if soort == zv.NAAR_ROL:
        doel = str((rij.get("verwerking") or {}).get("naar_rol") or "")
        if not doel:
            return {"rol": "", "reden": "geen ontvangende rol aangewezen"}
        return wiki.ontvanger(doel, records, assignments)
    return {"rol": "", "reden": ""}                        # zelf/info verlaten de rol niet


def _extra(rij: dict, k: dict) -> dict:
    """Wat er bij het ONTSTAAN al bekend is, mee op het item. Het type staat erop, dus de
    herschrijf-haak slaat dit item over — hij zou een al geschreven antwoord overschrijven."""
    return {"type": rij.get("type"), "bevinding": rij.get("bevinding") or {},
            "raad": {"soort": rij["soort"], "anker": rij["anker"],
                     "anker_soort": rij["anker_soort"], "bewijs": rij["bewijs"],
                     "vanuit": k.get("vanuit", ""), "wat_nodig": k.get("wat_nodig", "")}}


# ── de ronde ────────────────────────────────────────────────────────────────

def raad(*, records, att, ledger, assignments=None, notif=None, data_dir: str = "",
         apply: bool = False, cap: int = CAP_PER_ROL, reason_fn=None, vandaag: str = "",
         opnieuw: bool = False) -> dict:
    """De volledige council-pass. `apply=False` schrijft niets en verstuurt niets."""
    from nooch_village import wiki, zelf_verwerking as zv

    gezien = set() if opnieuw else eerder_opgeworpen(data_dir) if data_dir else set()
    pags = wiki.paginas(att) if att is not None else []
    per_rol: list[dict] = []
    rijen: list[dict] = []
    deelnemers = rollen(records)
    naam_van = labels(deelnemers, records)

    for rec in deelnemers:
        rol = rec.id
        alle = observaties_van(rec, ledger=ledger, att=att, vandaag=vandaag, alle_paginas=pags)
        oud = [o for o in alle if sleutel(o) in gezien]
        vers = [o for o in alle if sleutel(o) not in gezien]
        gekozen, gedropt = vers[:cap], vers[cap:]
        if gedropt:
            log.info("villageraad: %s bracht %d punt(en) in, %d niet ingebracht (cap %d)",
                     rol, len(gekozen), len(gedropt), cap)
        verwerkt = []
        for o in gekozen:
            rij = verwerk_observatie(o, records=records, reason_fn=reason_fn, data_dir=data_dir)
            rij["rol_naam"] = naam_van.get(rol, rol)
            rij["kaart"] = kaart(rij, records)
            doel = ontvanger_van(rij, records, assignments)
            rij["naar"] = doel.get("rol") or ""
            rij["omleiding"] = doel.get("reden") or ""
            rij["verzonden"] = False
            if apply and rij["verzendbaar"] and rij["naar"] and notif is not None:
                n = notif.add("role", rij["naar"], "", by=rol, snippet=_snippet(o),
                              extra=_extra(rij, rij["kaart"]))
                rij["verzonden"], rij["notif_id"] = True, n.get("id", "")
            if apply:
                zv.leg_vast(data_dir, rij["verwerking"])
                leg_vast(data_dir, {"sleutel": rij["sleutel"], "rol": rol, "soort": o["soort"],
                                    "anker": o["anker"], "type": rij.get("type"),
                                    "verzonden": rij["verzendbaar"] and bool(rij["naar"]),
                                    "naar": rij["naar"]})
            verwerkt.append(rij)
            rijen.append(rij)
        per_rol.append({"rol": rol, "naam": naam_van.get(rol, rol), "gevonden": len(alle),
                        "eerder": len(oud), "nieuw": len(vers), "ingebracht": len(gekozen),
                        "niet_ingebracht": len(gedropt), "rijen": verwerkt,
                        "soorten": sorted({o["soort"] for o in vers})})

    verdeling = zv.verdeling([r["verwerking"] for r in rijen])
    voorstellen = [r for r in rijen if r.get("type") in (zv.GOVERNANCE, zv.FOUNDER)]
    return {"datum": vandaag or time.strftime("%Y-%m-%d"), "apply": apply, "cap": cap,
            "per_rol": per_rol, "rijen": rijen, "verdeling": verdeling,
            "voorstellen": voorstellen,
            "hangt": [r for r in rijen if not r["verzendbaar"]
                      or (r.get("type") in (zv.NAAR_ROL, zv.GOVERNANCE, zv.FOUNDER)
                          and not r["naar"])]}


# ── het verslag ─────────────────────────────────────────────────────────────

_SOORT_ZIN = {
    "vervallen_grond":       "een feit dat zijn bewijs heeft overleefd",
    "dode_bron":             "een bron die niet meer antwoordt",
    "ongegronde_pagina":     "beweringen zonder bron",
    "domein_gat":            "een gat in het eigen domein",
    "kennisgat":             "onderzocht, niets gevonden",
    "ongecontroleerde_bron": "een bron die nooit is nagekeken",
    "pagina_zonder_feiten":  "een pagina zonder vastgelegd feit",
    "verweesde_verwijzing":  "een verwijzing naar een pagina die niet bestaat",
}


def kop_regel(r: dict) -> str:
    """De ene regel bovenaan. Alles eronder moet hem kunnen dragen."""
    from nooch_village import zelf_verwerking as zv

    v = r["verdeling"]
    onder = sum(v["per_uitkomst"].get(k, 0) for k in (zv.ZELF, zv.INFO, zv.NAAR_ROL))
    return (f"{v['totaal']} spanningen, {onder} onder de rollen opgelost, "
            f"{len(r['voorstellen'])} voorstellen voor de founder.")


def _kaart_tekst(k: dict, n: int) -> list[str]:
    regels = [f"### {n}. {k['type_label']} — {k['rol']}", "",
              f"- **opgeworpen door**: {k['rol']} (`{k['rol_id']}`)",
              f"- **vanuit accountability**: {k['vanuit']}",
              f"- **bevinding**: {k['bevinding']}",
              f"- **voorstel**: {k['voorstel'] or '— geen concreet voorstel meegeleverd'}",
              f"- **wat nodig**: {k['wat_nodig'] or '—'}",
              f"- **bewijs-record**: {k['bewijs']}"]
    if not k["verzendbaar"]:
        regels.append(f"- **niet verzonden**: {k['reden']}")
    regels.append("")
    return regels


def rapport_tekst(r: dict) -> str:
    from nooch_village import zelf_verwerking as zv

    v = r["verdeling"]
    uit = [kop_regel(r), "", f"# Villageraad — {r['datum']}", "",
           f"*{'LIVE' if r['apply'] else 'DRY-RUN'} · cap {r['cap']} punten per rol · "
           f"{len(r['per_rol'])} rollen aan tafel*", "",
           "## Toestandsbeeld", ""]

    if not r["rijen"]:
        uit += ["Geen enkele rol vond een gegronde spanning. Er is niets in het bewijsregister of "
                "op een pagina waar nu iets aan mankeert dat aan een record vastzit.", ""]
    else:
        uit.append(f"{v['totaal']} spanning(en) verwerkt. De verdeling over de vier uitkomsten:")
        uit.append("")
        for k, n in sorted(v["per_uitkomst"].items(), key=lambda kv: -kv[1]):
            uit.append(f"- **{n}× {zv.LABEL.get(k, k)}**")
        uit += ["", f"{v['onder_de_rollen']}% loste onder de rollen op; "
                    f"{v['naar_de_founder']} bereikte(n) de founder.", ""]

        stroomt = [x for x in r["rijen"] if x["verzendbaar"] and x["naar"]]
        uit += ["**Wat stroomt.** " + (
            f"{len(stroomt)} spanning(en) hebben een bureau gevonden: "
            + "; ".join(f"{x.get('rol_naam') or x['rol']} → {x['naar']}" for x in stroomt[:8])
            + ("…" if len(stroomt) > 8 else "") if stroomt else
            "Niets verliet een rol — alles wat gevonden is, is werk binnen de eigen rol."), ""]

        if r["hangt"]:
            uit += ["**Wat blijft hangen, en waarom.**", ""]
            for x in r["hangt"]:
                waarom = (x["reden_niet_verzendbaar"] or x["omleiding"]
                          or "geen ontvanger gevonden")
                uit.append(f"- {x.get('rol_naam') or x['rol']} · "
                           f"{_SOORT_ZIN.get(x['soort'], x['soort'])} — {waarom}")
            uit.append("")

        omgeleid = [x for x in r["rijen"] if x["omleiding"] and x["naar"]]
        if omgeleid:
            uit += ["**Omgeleid.** Een rol zonder menselijke vervuller leest zijn postbus niet; "
                    "die kaarten gingen naar de Circle Lead:", ""]
            uit += [f"- {x.get('rol_naam') or x['rol']} → {x['naar']} ({x['omleiding']})"
                    for x in omgeleid]
            uit.append("")

    uit += ["### Per rol", ""]
    stil = []
    for p in r["per_rol"]:
        if not p["nieuw"] and not p["eerder"]:
            stil.append(p)
            continue
        if not p["nieuw"]:
            uit.append(f"- **{p['naam']}** — niets nieuws; {p['eerder']} punt(en) al eerder "
                       f"opgeworpen en nog niet weg.")
            continue
        soorten = ", ".join(_SOORT_ZIN.get(s, s) for s in p["soorten"])
        staart = (f" ({p['niet_ingebracht']} niet ingebracht — cap)" if p["niet_ingebracht"]
                  else "")
        typen = ", ".join(sorted({zv.LABEL.get(x.get("type"), "?") for x in p["rijen"]}))
        uit.append(f"- **{p['naam']}** — {soorten}; {p['ingebracht']} ingebracht"
                   f"{staart} → {typen or 'nog niet verwerkt'}.")
    if stil:
        uit += ["", f"**Geen gegronde spanning** ({len(stil)} rollen): "
                    + ", ".join(p["naam"] for p in stil) + ". Deze rollen vonden niets in de "
                    "Kroniek en op hun pagina's waar nu iets aan mankeert. Dat is de uitkomst, "
                    "geen gebrek aan agenda."]
    uit.append("")

    uit += ["## Voorstellen", ""]
    if not r["voorstellen"]:
        uit += ["Geen governance-voorstel en geen founder-besluit. Alles wat gevonden is, is "
                "opgelost of belegd binnen de rollen.", ""]
    else:
        uit += [f"{len(r['voorstellen'])} kaart(en) voor de founder — governance-voorstellen en "
                f"besluiten die alleen hij mag nemen.", ""]
        for i, x in enumerate(r["voorstellen"], 1):
            uit += _kaart_tekst(x["kaart"], i)
            uit.append(f"*{'in de inbox gezet' if x.get('verzonden') else 'niet verzonden'}"
                       f"{' (' + x['naar'] + ')' if x.get('naar') else ''}*")
            uit.append("")
    return "\n".join(uit)
