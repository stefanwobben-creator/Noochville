"""Wiki — de rol-note ÍS de pagina. Links, backlinks en feiten met grond.

Waarom dit bestaat. Kennis die extern leeft (een Drive-doc, een sheet) kan een inwoner niet
gronden, niet aan records linken en niet als werkgeheugen lezen-en-schrijven. Native kennis wel.
Maar een tweede store naast de artefacten zou precies de fout maken die dit project al eens
teruggedraaid heeft: dezelfde waarheid op twee plekken. Daarom is een pagina géén nieuw type —
het is de bestaande rol-note (`kind="note"` in de AttachmentStore):

    eigenaar-rol = domein        (wie cureert; identiek voor mens- en AI-vervuller)
    versie-historie              (elke mutatie een snapshot, append-only)
    erven                        (onderliggende rollen lezen read-only)
    /context                     (gaat al mee als systeemprompt-bron voor AI-vervullers)

Dit moduul voegt daar de wiki-laag aan toe, en niets anders:

1. **`[[links]]`** tussen pagina's — opgelost op note-id of op een UNIEKE titel. Twee pagina's met
   dezelfde titel lossen bewust NIET op: liever een zichtbaar 'bestaat niet' dan een link die naar
   de verkeerde pagina wijst.
2. **Backlinks** — afgeleid uit de bodies, nooit opgeslagen. Eén bron (de tekst zelf); een
   link-tabel ernaast zou stilletjes uit de pas kunnen lopen (`reference, don't copy`).
3. **Feiten met grond** — een feit op een pagina kan wijzen naar een Kroniek-record, een
   certificaat, een policy of een geciteerde externe bron. De grond wordt bij het LEZEN opnieuw
   vergeleken, nooit als oordeel opgeslagen: een verlopen certificaat draagt dan vanzelf niets
   meer, precies zoals `cert_register` het al doet voor claims.

Fail-closed: grond die niet gevonden wordt is `ontbreekt`, niet 'waarschijnlijk goed'. Een feit
zonder grond mag bestaan maar heet `ongegrond` — nooit stille suggestie van bewijs.

Puur domein: dit moduul rendert geen HTML (dat doet `views/wiki.py`) en schrijft niet naar schijf
(dat doet de AttachmentStore).
"""
from __future__ import annotations

import re
import urllib.parse

from nooch_village import cert_register

# De note is de pagina. Geen tweede soort, geen tweede store.
PAGINA_KIND = "note"

# De vier soorten grond die een feit kan dragen.
GROND_SOORTEN = ("kroniek", "cert", "policy", "bron")

# Grond-uitkomsten. `ongecontroleerd` is bewust geen synoniem van `gegrond`: een geciteerde URL of
# een niet-bevestigd Kroniek-record is herkomst, geen bewijs.
GEGROND = "gegrond"
ONGECONTROLEERD = "ongecontroleerd"
VERVALLEN = "vervallen"
ONTBREEKT = "ontbreekt"
ONGEGROND = "ongegrond"

# [[verwijzing]] — één regel, geen geneste haken. Max 160 tekens: een link is een naam, geen alinea.
LINK_RE = re.compile(r"\[\[([^\[\]\n]{1,160})\]\]")

_TEKST_MAX = 400
_REF_MAX = 120
_URL_MAX = 500


def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def pagina_url(aid: str) -> str:
    """De permalink van een pagina. Eén plek, zodat een link nooit met de hand wordt gebouwd."""
    return "/pagina?id=" + urllib.parse.quote(aid or "")


# ── De pagina's ─────────────────────────────────────────────────────────────

def paginas(store) -> list:
    """Alle actieve pagina's, org-breed. Een wiki-link kent geen rolgrens: je verwijst naar een
    pagina, niet naar 'de note van rol X'. Wie hem mag WIJZIGEN blijft de eigenaar-rol."""
    return store.by_kind(PAGINA_KIND)


def resolve(ref: str, pags: list):
    """De pagina waar `ref` naar wijst, of None.

    Volgorde: exact note-id (uniek per definitie), daarna een unieke titel-match. Meerdere
    pagina's met dezelfde titel → None: een gok zou naar de verkeerde pagina kunnen wijzen, en
    een zichtbare 'bestaat niet'-chip is eerlijker dan een stille misverwijzing."""
    r = _norm(ref)
    if not r:
        return None
    for a in pags:
        if a.id.lower() == r:
            return a
    treffers = [a for a in pags if _norm(a.title) == r]
    return treffers[0] if len(treffers) == 1 else None


def verwijzingen(body: str) -> list[str]:
    """De ruwe `[[…]]`-verwijzingen in een body, in tekstvolgorde (met duplicaten)."""
    return [m.group(1).strip() for m in LINK_RE.finditer(body or "")]


def backlinks(pagina, pags: list) -> list:
    """Pagina's die naar deze verwijzen. Afgeleid uit de bodies — nooit opgeslagen."""
    uit = []
    for a in pags:
        if a.id == pagina.id:
            continue
        for ref in verwijzingen(a.body):
            doel = resolve(ref, pags)
            if doel is not None and doel.id == pagina.id:
                uit.append(a)
                break
    return uit


def ontbrekende_links(pagina, pags: list) -> list[str]:
    """Verwijzingen op deze pagina die (nog) niet oplossen — de verlanglijst van de wiki. Er wordt
    NOOIT automatisch een lege pagina van gemaakt: een pagina krijgt een eigenaar, en dat is een
    besluit van een mens of van de eigenaar-rol zelf."""
    uit, gezien = [], set()
    for ref in verwijzingen(pagina.body):
        k = _norm(ref)
        if k in gezien or resolve(ref, pags) is not None:
            continue
        gezien.add(k)
        uit.append(ref)
    return uit


# ── Feiten met grond ────────────────────────────────────────────────────────

def feiten(a) -> list[dict]:
    """De feiten van een pagina. Ze leven in `meta["feiten"]` van dezelfde note — geen tweede
    opslag, en ze reizen dus vanzelf mee in versies, erven en /context."""
    ruw = (getattr(a, "meta", None) or {}).get("feiten")
    return [f for f in ruw if isinstance(f, dict)] if isinstance(ruw, list) else []


def maak_feit(tekst: str, *, soort: str = "", ref: str = "", citaat: str = "",
              url: str = "") -> dict | None:
    """Normaliseer één feit. None bij lege tekst (fail-closed: geen leeg feit in de lijst).
    Een onbekende grond-soort valt weg — het feit blijft dan bestaan, maar heet `ongegrond`."""
    tekst = " ".join((tekst or "").split())[:_TEKST_MAX]
    if not tekst:
        return None
    grond: dict = {}
    if soort in GROND_SOORTEN:
        grond = {"soort": soort,
                 "ref": (ref or "").strip()[:_REF_MAX],
                 "citaat": " ".join((citaat or "").split())[:_TEKST_MAX],
                 "url": (url or "").strip()[:_URL_MAX]}
    return {"tekst": tekst, "grond": grond}


def _kroniek_record(ledger, rid: str) -> dict | None:
    if not rid or ledger is None:
        return None
    for r in ledger.all_records():
        if r.get("id") == rid:
            return r
    return None


def _uit(grond: dict, status: str, label: str, detail: str = "") -> dict:
    return {"status": status, "label": label, "detail": detail,
            "soort": str(grond.get("soort") or ""), "ref": str(grond.get("ref") or ""),
            "url": str(grond.get("url") or ""), "citaat": str(grond.get("citaat") or "")}


def grond_status(feit: dict, *, ledger=None, store=None, vandaag: str = "") -> dict:
    """Draagt dit feit nu nog? Een LEVENDE vergelijking, elke keer opnieuw.

    Dit is dezelfde regel als bij een claim: een goedkeuring mag zijn bewijs niet overleven. Er
    wordt daarom nooit een uitkomst opgeslagen — verloopt het certificaat of verdwijnt het
    Kroniek-record, dan verliest het feit vanzelf zijn grond."""
    grond = (feit or {}).get("grond") or {}
    soort = str(grond.get("soort") or "")

    if soort not in GROND_SOORTEN:
        return _uit(grond, ONGEGROND, "ungrounded", "this fact carries no source")

    if soort == "bron":
        # Een geciteerde bron is herkomst, geen bewijs — tótdat iemand kijkt of hij het nog zegt.
        # Die check draait NIET tijdens het lezen (dat zou elke pageload een netwerk-call maken);
        # `wiki_bronnen` doet hem periodiek en legt de uitkomst hier neer. Wat we tonen is dus
        # altijd een gedateerde waarneming, met de datum erbij.
        url = str(grond.get("url") or "")
        if not url:
            return _uit(grond, ONTBREEKT, "source missing", "no URL with this citation")
        check = grond.get("check") or {}
        wanneer = str(check.get("op") or "")
        if not check:
            return _uit(grond, ONGECONTROLEERD, "cited source", "not verified")
        if check.get("gevonden") is True:
            return _uit(grond, GEGROND, "cited source — quote still present",
                        f"checked {wanneer}" if wanneer else "checked")
        if check.get("gevonden") is False:
            return _uit(grond, VERVALLEN, "cited source — quote no longer found",
                        f"checked {wanneer}" if wanneer else "checked")
        # Niet gelukt om te kijken (netwerk, HTTP-fout): dat is géén oordeel over de bron.
        return _uit(grond, ONGECONTROLEERD, "cited source",
                    f"could not check{': ' + str(check.get('reden')) if check.get('reden') else ''}")

    if soort == "policy":
        a = store.get(str(grond.get("ref") or "")) if store is not None else None
        if a is None or getattr(a, "kind", "") != "policy":
            return _uit(grond, ONTBREEKT, "policy not found", str(grond.get("ref") or ""))
        if getattr(a, "status", "active") == "archived":
            return _uit(grond, VERVALLEN, "policy archived", a.id)
        return _uit(grond, GEGROND, a.title or a.id, f"policy {a.id}")

    r = _kroniek_record(ledger, str(grond.get("ref") or ""))
    if r is None:
        return _uit(grond, ONTBREEKT, "chronicle record not found", str(grond.get("ref") or ""))

    if soort == "cert":
        if r.get("source") != cert_register.EXTERN:
            return _uit(grond, ONTBREEKT, "not a certificate",
                        "this record is not external certificate evidence")
        cert = dict(r.get("meta") or {})
        instantie = str(cert.get("instantie") or "certificate")
        tot = str(cert.get("geldig_tot") or "")
        verlopen = cert_register.verlopen(cert, vandaag=vandaag)
        if verlopen is None:
            # Geen leesbare vervaldatum is nadrukkelijk niet 'geldig': niemand kan zeggen tot
            # wanneer dit draagt (zelfde regel als cert_register.verlopen).
            return _uit(grond, VERVALLEN, f"{instantie} — no readable expiry date", r.get("id") or "")
        if verlopen:
            return _uit(grond, VERVALLEN, f"{instantie} — expired {tot}", r.get("id") or "")
        return _uit(grond, GEGROND, f"{instantie} — valid until {tot}", r.get("id") or "")

    # soort == "kroniek": alleen een BEVESTIGD record draagt. leeg/fout zijn echte uitkomsten,
    # maar het zijn geen bewijs.
    status = str(r.get("status") or "")
    detail = f"{r.get('skill') or '?'} · {r.get('source') or '?'}"
    if status != "bevestigd":
        return _uit(grond, ONGECONTROLEERD, f"chronicle — {status or 'unknown'}", detail)
    return _uit(grond, GEGROND, f"chronicle — {detail}", r.get("id") or "")


# ── Een voorstel op een pagina ("ik vind dat pagina X moet zeggen Y") ───────
# Bewerken is van de eigenaar. Wie dat niet is, kan wél een voorstel doen — en dat loopt langs het
# BESTAANDE verzoekmechanisme (een `naar_rol`-item in de inbox met accepteren / aanpassen /
# weigeren). Geen nieuw scherm en geen tweede beslis-logica; alleen de accepteer-handeling is hier
# concreter dan bij een gewoon verzoek: de tekst ís het voorstel, dus accepteren schrijft hem.

def is_wijziging(pagina, voorstel: str) -> bool:
    """Verschilt het voorstel écht van wat er staat? Een identiek 'voorstel' is geen verzoek maar
    ruis in de inbox van de eigenaar."""
    return (voorstel or "").strip() != (getattr(pagina, "body", "") or "").strip()


def ontvanger(anchor: str, records, assignments) -> dict:
    """Wie beslist over een voorstel op deze pagina? `{"rol": id, "reden": str}`.

    Normaal de eigenaar-rol zelf. Maar een AI-vervulde (of onbemande) rol leest de mens-inbox
    nooit — daar zou het verzoek doodstil blijven liggen. Dan gaat het naar de Circle Lead van de
    omvattende cirkel, die via dezelfde artefact-poort ook mág schrijven. Het verzoek verandert niet
    van inhoud, alleen van postbus, en de reden staat erbij zodat niemand hoeft te raden."""
    from nooch_village import artefacts
    from nooch_village.assignments import door_mens_bemand

    if door_mens_bemand(anchor, assignments, records):
        return {"rol": anchor, "reden": ""}
    cirkel = artefacts.circle_of(anchor, records)
    lead = f"{cirkel}__circle_lead" if cirkel else ""
    if lead and records.get(lead) is not None:
        return {"rol": lead, "reden": "the owner role has no human filler"}
    # Geen Circle Lead: liever bij de eigenaar laten liggen mét reden dan naar een willekeurige
    # andere postbus sturen. Fail-closed op routering, niet op de inhoud.
    return {"rol": anchor, "reden": "no Circle Lead found — stays with the owner role"}


def voorstel_velden(pagina, *, voorstel: str, waarom: str, van_naam: str, van_id: str,
                    reden: str = "") -> tuple[str, dict]:
    """(snippet, extra) voor `NotifStore.add`. Het type staat er meteen op: dit item weet bij zijn
    ontstaan precies wat het vraagt, dus het hoeft niet door de herschrijf-haak."""
    from nooch_village import zelf_verwerking as zv

    titel = getattr(pagina, "title", "") or getattr(pagina, "id", "")
    spanning = waarom.strip() or f"“{titel}” zegt volgens {van_naam or 'iemand'} niet het juiste"
    snippet = f"voorstel voor pagina {titel}: {spanning}"   # geen eigen cap (#389)
    extra = {
        "type": zv.NAAR_ROL,
        "bevinding": {"ok": True, "spanning": spanning,
                      "voorstel": f"pas de tekst van “{titel}” aan zoals voorgesteld"},
        "pagina": {"aid": getattr(pagina, "id", ""), "titel": titel,
                   "eigenaar": getattr(pagina, "anchor", ""), "body": voorstel,
                   "was": getattr(pagina, "body", "") or "",
                   "van_naam": van_naam, "van_id": van_id, "reden": reden},
    }
    return snippet, extra


def _plat(s: str) -> str:
    """Tekst voor een citaat-vergelijking: kleine letters, één spatie, typografische aanhalings-
    en koppeltekens genormaliseerd. Zonder dit zou een pagina die alleen ’ in ' verandert al
    'de bron zegt dit niet meer' opleveren."""
    t = (s or "").lower()
    for teken, vlak in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                        ("–", "-"), ("—", "-"), (" ", " ")):
        t = t.replace(teken, vlak)
    return " ".join(t.split())


def controleer_citaat(feit: dict, tekst: str) -> dict:
    """Staat het citaat nog in de opgehaalde brontekst? `{gevonden, reden}` — puur, geen netwerk.

    Fail-closed op het randgeval: zonder citaat valt er niets te toetsen, en dan is 'gevonden' niet
    True maar None — anders zou een feit met alleen een URL zichzelf tot bewijs promoveren."""
    citaat = _plat(str((feit.get("grond") or {}).get("citaat") or ""))
    if not citaat:
        return {"gevonden": None, "reden": "no quote to check"}
    if len(citaat) < 12:
        # Een heel kort 'citaat' matcht overal; dat is geen toets maar toeval.
        return {"gevonden": None, "reden": "quote too short to check"}
    return ({"gevonden": True, "reden": ""} if citaat in _plat(tekst)
            else {"gevonden": False, "reden": "quote not found in the source text"})


def telling(a, *, ledger=None, store=None, vandaag: str = "") -> dict:
    """{status: aantal} over de feiten van een pagina — voor een kop die niet liegt."""
    uit: dict[str, int] = {}
    for f in feiten(a):
        s = grond_status(f, ledger=ledger, store=store, vandaag=vandaag)["status"]
        uit[s] = uit.get(s, 0) + 1
    return uit
