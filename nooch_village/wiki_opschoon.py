"""Eenmalige opschoning en rapporten voor de wiki-feiten (W1b, 14 oktober 2026).

Twee commando's, allebei standaard een DRY-RUN:

  village wiki_opschoon_w1b [--apply]
      Haalt dubbele feiten en het afgebroken ISO/IEC 17025-fragment van een pagina. Met `--apply`
      eerst een back-up van de hele store met label (`<store>.bak-w1b-opschoon-<tijd>`), daarna één
      nieuwe versie per pagina — de oude versies blijven in de historie staan. Niet-geplaatste
      feiten (LTA) worden ALLEEN gemeld, met de keuzes: daar beslist een mens.

  village wiki_feit_rapport
      Alleen lezen. (1) Feiten met een getal dat niet voor zijn vraag gecheckt is (de Pliant-fout),
      (2) gecheckte feiten die nergens voor tellen, met een VOORSTEL per feit (vraag + waarde, of
      "background only") dat een mens bevestigt, (3) ongecheckte feiten die alleen via hun kopje
      meetellen (vóór variant B moeten die eerst echt gecheckt worden).

Een voorstel is een voorstel: niets in dit bestand zet een antwoord in een feit. Een afgeleid
antwoord mag nooit stilzwijgend tellen.
"""
from __future__ import annotations

import os
import re
import shutil
import time

from nooch_village import wiki
from nooch_village import wiki_dekking as dek

#: Het afgebroken fragment op NFW (de oude bulk import kapte hem af op 400 tekens). Op id ÉN begin van
#: de tekst: staat er onder die id iets anders, dan blijft het staan.
FRAGMENTEN = {"h06e6b5b718": "An ISO/IEC 17025-accredited lab"}

#: Dubbel OVER PAGINA'S heen, per besluit van Stefan (14 oktober): {weg te halen feit: het feit dat
#: blijft, op een andere pagina}. Alleen als dat andere feit nog bestaat met dezelfde tekst.
KRUIS_DUBBEL = {"3a3719e4c0": "ab169b9f5f"}

#: Pagina's waarvan de niet-geplaatste feiten gemeld worden (opdracht 14 oktober: LTA).
MELD_ONGEPLAATST = ("LTA",)


def _n(s) -> str:
    return " ".join(str(s or "").split()).lower()


def _zelfde(f: dict, g: dict) -> str:
    """De regel van de dubbelwaarschuwing in Bulk Import (`NV.bulkDubbel`): zelfde Quote én URL, of
    zelfde tekst. "" als ze niet dubbel zijn."""
    gf, gg = f.get("grond") or {}, g.get("grond") or {}
    if _n(gf.get("citaat")) and _n(gf.get("url")) and (_n(gf.get("citaat")), _n(gf.get("url"))) == (
            _n(gg.get("citaat")), _n(gg.get("url"))):
        return "same quote and URL"
    if _n(f.get("tekst")) and _n(f.get("tekst")) == _n(g.get("tekst")):
        return "same text"
    return ""


def _geplaatst(body: str) -> set[str]:
    return set(wiki.FEIT_MARKER_RE.findall(body or ""))


def _voorkeur(f: dict, geplaatst: set[str]) -> tuple:
    """Welk exemplaar blijft: geplaatst > gecheckt > met `For:` > met een quote. Bij gelijkspel het
    eerste (de volgorde van `meta["feiten"]`)."""
    return (wiki.feit_id(f) in geplaatst, bool(wiki.nagekeken(f)), bool(f.get("sectie")),
            bool((f.get("grond") or {}).get("citaat")))


def plan(store) -> list[dict]:
    """[{id, titel, weg: [{fid, tekst, waarom, blijft}], ongeplaatst: [{fid, tekst, gecheckt}]}]
    — alleen pagina's waar iets te doen of te melden is."""
    rapport = []
    alle = {wiki.feit_id(f): (f, a) for a in wiki.paginas(store) for f in wiki.feiten(a)}
    for a in wiki.paginas(store):
        feiten = list(wiki.feiten(a))
        geplaatst = _geplaatst(getattr(a, "body", ""))
        weg: list[dict] = []
        gezien: list[dict] = []
        for f in feiten:
            fid = wiki.feit_id(f)
            begin = FRAGMENTEN.get(fid)
            if begin and (f.get("tekst") or "").startswith(begin):
                weg.append({"fid": fid, "tekst": f.get("tekst", ""), "blijft": "",
                            "waarom": "cut-off fragment from the old bulk import"})
                continue
            ander = alle.get(KRUIS_DUBBEL.get(fid, ""))
            if ander and ander[1].id != a.id and _n(ander[0].get("tekst")) == _n(f.get("tekst")):
                weg.append({"fid": fid, "tekst": f.get("tekst", ""), "blijft": "",
                            "waarom": f"same text as {KRUIS_DUBBEL[fid]} on {ander[1].title}, which stays"})
                continue
            twin = next((g for g in gezien if _zelfde(f, g)), None)
            if twin is None:
                gezien.append(f)
                continue
            waarom = _zelfde(f, twin)
            houden, kwijt = (twin, f) if _voorkeur(twin, geplaatst) >= _voorkeur(f, geplaatst) else (f, twin)
            if kwijt is twin:
                gezien[gezien.index(twin)] = f
            regel = {"fid": wiki.feit_id(kwijt), "tekst": kwijt.get("tekst", ""), "waarom": waarom,
                     "blijft": wiki.feit_id(houden)}
            # Een quote die alleen op het weg te halen exemplaar staat, gaat niet verloren: hij gaat
            # LETTERLIJK naar het blijvende feit (besluit Stefan, 14 oktober). Was dat feit gecheckt,
            # dan vervalt die check — zijn bron verandert — en dat staat in de dry-run.
            q = (kwijt.get("grond") or {}).get("citaat")
            if q and not (houden.get("grond") or {}).get("citaat"):
                regel["quote_naar"] = {"fid": wiki.feit_id(houden), "citaat": q,
                                       "check_vervalt": bool(wiki.nagekeken(houden))}
            weg.append(regel)
        ongeplaatst = []
        if (a.title or "") in MELD_ONGEPLAATST:
            ongeplaatst = [{"fid": wiki.feit_id(f), "tekst": f.get("tekst", ""),
                            "gecheckt": bool(wiki.nagekeken(f))}
                           for f in feiten if wiki.feit_id(f) not in geplaatst
                           and wiki.feit_id(f) not in {w["fid"] for w in weg}]
        if weg or ongeplaatst:
            rapport.append({"id": a.id, "titel": a.title or a.id, "weg": weg, "ongeplaatst": ongeplaatst})
    return rapport


def back_up(store, label: str = "w1b-opschoon") -> str:
    """Een kopie van het hele store-bestand naast het origineel, met label en tijd. Geeft het pad."""
    doel = f"{store.path}.bak-{label}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(store.path, doel)
    return doel


def toepassen(store, rapport: list[dict], *, actor_id: str = "") -> int:
    """Haalt de feiten in `weg` van hun pagina (en hun `{{fact:id}}`-regel uit de tekst) en zet een
    quote die alleen op het weggehaalde exemplaar stond letterlijk op het blijvende feit. Eén nieuwe
    versie per pagina. Geeft het aantal verwijderde feiten."""
    n = 0
    for r in rapport:
        ids = {w["fid"] for w in r["weg"]}
        if not ids:
            continue
        a = store.get(r["id"])
        meta = dict(getattr(a, "meta", None) or {})
        quotes = {w["quote_naar"]["fid"]: w["quote_naar"]["citaat"] for w in r["weg"] if w.get("quote_naar")}
        feiten = []
        for f in wiki.feiten(a):
            if wiki.feit_id(f) in ids:
                continue
            if wiki.feit_id(f) in quotes and not (f.get("grond") or {}).get("citaat"):
                f = {**f, "grond": {**(f.get("grond") or {}), "citaat": quotes[wiki.feit_id(f)]}}
                f.pop("gezien", None)                       # nieuwe bron: opnieuw nakijken
            feiten.append(f)
        meta["feiten"] = feiten
        body = getattr(a, "body", "") or ""
        nieuw = re.sub(r"^\{\{fact:(%s)\}\}[ \t]*\n?" % "|".join(map(re.escape, ids)), "", body, flags=re.M)
        store.update(r["id"], meta=meta, body=nieuw if nieuw != body else None, actor_id=actor_id,
                     actor_type="person", change_note=f"W1b cleanup: {len(ids)} duplicate/fragment fact(s) removed")
        n += len(ids)
    return n


def plan_tekst(rapport: list[dict]) -> str:
    if not rapport:
        return "Nothing to clean up."
    uit = []
    for r in rapport:
        uit.append(f"{r['id']}  {r['titel']}")
        for w in r["weg"]:
            blijft = f" — keeps {w['blijft']}" if w["blijft"] else ""
            uit.append(f"  remove {w['fid']} ({w['waarom']}{blijft}): {w['tekst'][:90]}")
            if w.get("quote_naar"):
                qn = w["quote_naar"]
                uit.append(f"    copy quote literally to {qn['fid']}: “{qn['citaat']}”"
                           + (" (its check lapses: the source changes)" if qn["check_vervalt"] else ""))
        if r["ongeplaatst"]:
            uit.append(f"  not placed (no action — choose per fact: place under a heading, mark "
                       f"background only when checking, or remove):")
            for o in r["ongeplaatst"]:
                uit.append(f"    {o['fid']} {'checked' if o['gecheckt'] else 'unchecked'}: {o['tekst'][:90]}")
    return "\n".join(uit)


# ── het leesrapport ─────────────────────────────────────────────────────────────────────────────

_JA = re.compile(r"^\s*(?:contains \w+|[\w ]{0,30}):\s*yes\b", re.I)
_NEE = re.compile(r"^\s*(?:contains \w+|[\w ]{0,30}):\s*no\b", re.I)


def _voorstel(f: dict, soort: str, kop: str) -> dict:
    """Een VOORSTEL voor een gecheckt feit dat nergens telt: de vraag waar zijn kopje of `For:` bij
    hoort, met yes/no als de tekst dat letterlijk vooraan zegt; anders "background only". Een mens
    bevestigt per feit — dit wordt nergens opgeslagen."""
    sectie = f.get("sectie") or kop
    for v in dek.vragen(soort):
        if not v["grootheid"] and sectie and dek._norm(sectie) in {dek._norm(k) for k in v["koppen"]}:
            tekst = f.get("tekst") or ""
            waarde = "yes" if _JA.match(tekst) else "no" if _NEE.match(tekst) else "?"
            return {"vraag": v["label"], "waarde": waarde,
                    "reden": f"its heading '{sectie}' belongs to this question"
                             + ("" if waarde != "?" else "; the text does not say yes or no up front")}
    tekst = f.get("tekst") or ""
    voor = _n(tekst.split(":", 1)[0]) if ":" in tekst[:60] else ""
    for v in dek.vragen(soort):
        if voor and voor == _n(v["label"]).rstrip("?"):
            waarde = "yes" if _JA.match(tekst) else "no" if _NEE.match(tekst) else "?"
            return {"vraag": v["label"], "waarde": waarde, "reden": f"the text starts with '{tekst.split(':', 1)[0]}'"}
    # het trefwoord dat het EERST in de tekst staat: daar gaat de zin over
    treffers = sorted(((t.start(), t.group(0), v) for v in dek.vragen(soort)
                       if (m := _TREFWOORD.get(v["k"])) and (t := m.search(tekst))), key=lambda x: x[0])
    if treffers:
        _pos, woord, v = treffers[0]
        return {"vraag": v["label"], "waarde": "?" if not v["grootheid"] else "value",
                "reden": f"the text mentions '{woord}' first; the answer is a human's call"}
    return {"vraag": "", "waarde": "", "reden": "no question fits its heading or text"}


#: Trefwoorden voor een VOORSTEL (geen koppeling): welke vraag een tekst lijkt te raken.
_TREFWOORD = {k: re.compile(p, re.I) for k, p in {
    "plastic": r"\b(plastic|PLA|polyester|polyurethane|PU)\b",
    "biobased": r"\bbio-?based\b|\bTENCEL\b",
    "animal": r"\b(animal|vegan|leather|wool)\b",
    "chem": r"\b(chemical|REACH|finishing mix\w*|resins?|dyes?)\b",
    "water": r"\bwater (footprint|use|consumption)\b",       # niet "water-based"
    "co2": r"\b(CO2e?|carbon|emissions?)\b",
    "cert": r"\b(certificat\w*|EMAS|ISO \d+|FSC|GRS|OEKO-TEX)\b",
    "loc": r"\b(plant|site|located|address)\b",
    "labor": r"\b(employees|workers|labou?r|injur\w*)\b",
}.items()}


def leesrapport(att, leveranciers, materialen, *, bestaat=None) -> dict:
    d, ctx = dek.uit_stores(att, leveranciers, materialen, bestaat=bestaat)
    getal, dood, kopje = [], [], []
    for soort, rijen in (("materiaal", d["materialen"]), ("leverancier", d["leveranciers"])):
        for rij in rijen:
            p = rij.get("pagina")
            if p is None:
                continue
            for f in wiki.feiten(p):
                w = wiki.waarde(f) or (f.get("waarde") if isinstance(f.get("waarde"), dict) else None)
                if not w:
                    continue
                v = next((x for x in dek.vragen(soort) if x["grootheid"] == w.get("grootheid")), None)
                if v and not any(a["vraag"] == v["k"] for a in wiki.antwoorden(f)):
                    getal.append({"pagina": p.title, "fid": wiki.feit_id(f), "tekst": f.get("tekst", ""),
                                  "waarde": w, "vraag": v["label"], "geldig": wiki.waarde(f) is not None})
            for x in dek.dode_feiten(rij, ctx):
                f = next(g for g in wiki.feiten(p) if wiki.feit_id(g) == x["fid"])
                dood.append({"pagina": p.title, **x, "voorstel": _voorstel(f, soort, x["kop"])})
            per_id = {wiki.feit_id(f): f for f in wiki.feiten(p)}
            for k, c in rij["cellen"].items():
                for fid in c["feiten"]:
                    f = per_id.get(fid)
                    if f is not None and not wiki.antwoorden(f) and not wiki.achtergrond(f):
                        kopje.append({"pagina": p.title, "fid": fid, "vraag": k,
                                      "gecheckt": bool(wiki.nagekeken(f)), "tekst": f.get("tekst", "")})
    # één pagina kan in meerdere rijen staan (materiaal in twee modellen): dubbelen eruit
    def uniek(lijst, sleutel):
        gezien, uit = set(), []
        for x in lijst:
            if sleutel(x) not in gezien:
                gezien.add(sleutel(x))
                uit.append(x)
        return uit
    return {"getal": uniek(getal, lambda x: (x["pagina"], x["fid"])),
            "dood": uniek(dood, lambda x: (x["pagina"], x["fid"])),
            "kopje": uniek(kopje, lambda x: (x["pagina"], x["fid"], x["vraag"]))}


def leesrapport_tekst(r: dict) -> str:
    uit = [f"1. Facts with a number not checked for its question: {len(r['getal'])}"]
    for x in r["getal"]:
        uit.append(f"   {x['pagina']} {x['fid']}: {x['vraag']} = {x['waarde'].get('getal')}"
                   f"{'' if x['geldig'] else ' (invalid, no longer counts)'} — {x['tekst'][:70]}")
    uit.append(f"\n2. Checked facts that count for nothing: {len(r['dood'])} (proposals — confirm per fact)")
    for x in r["dood"]:
        v = x["voorstel"]
        wat = f"{v['vraag']} ({v['waarde']})" if v["vraag"] else "background only"
        uit.append(f"   {x['pagina']} {x['fid']}: {x['tekst'][:70]}")
        uit.append(f"      proposal: {wat} — {v['reden']}")
    uit.append(f"\n3. Facts that count only through their heading, without a chosen answer: {len(r['kopje'])}")
    for x in r["kopje"]:
        uit.append(f"   {x['pagina']} {x['fid']} → {x['vraag']} ({'checked' if x['gecheckt'] else 'unchecked'})"
                   f": {x['tekst'][:60]}")
    return "\n".join(uit)
