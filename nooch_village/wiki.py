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

import hashlib
import json
import re
import time
import urllib.parse
import uuid

from nooch_village import cert_register

# De note is de pagina. Geen tweede soort, geen tweede store.
PAGINA_KIND = "note"

# De vier soorten grond die een feit kan dragen.
GROND_SOORTEN = ("kroniek", "cert", "policy", "bron", "document", "attested")

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
_SECTIE_MAX = 80


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


def verwijsbaar(store) -> list:
    """Alles waar een `[[verwijzing]]` naar kan wijzen: note, policy én tool.

    APART VAN `paginas()`, en dat is geen dubbelop. `paginas()` voedt de bron-check, en die loopt
    over FEITEN — die wonen alleen op notes. Verwijzen doe je naar alles wat een permalink heeft,
    en sinds #574 hebben alle drie de soorten er een.

    VERBREED OP 24 SEPTEMBER 2026, en dat kon zonder risico: op prod staan NUL `[[verwijzingen]]`
    in welk artefact dan ook. Er verandert dus niets aan wat er vandaag op een scherm staat; het
    maakt alleen mogelijk wat sinds #574 al logisch was."""
    from nooch_village.attachments import ARTEFACT_KINDS
    uit = []
    for kind in ARTEFACT_KINDS:
        uit.extend(store.by_kind(kind))
    return uit


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


#: DE BOM-NAMEN VAN EEN PAGINA (4 oktober 2026). Een materiaal- of leverancierpagina onthoudt onder
#: welke naam /bom haar kent ("Pliant PCS", "NFW"). Zo blijft de koppeling staan als iemand de pagina
#: hernoemt — eerst brak "Supplied by" stil zodra een titel veranderde. Zet de zaaier bij het aanmaken
#: en `village wiki_bom_sleutels` voor bestaande pagina's; een mens hoeft het niet te onderhouden.
BOM_NAMEN = "bom_namen"


def bom_namen(a) -> list[str]:
    ruw = (getattr(a, "meta", None) or {}).get(BOM_NAMEN)
    return [str(n) for n in ruw if str(n).strip()] if isinstance(ruw, list) else []


def resolve_bom(naam: str, pags: list):
    """De pagina die bij een naam op /bom hoort: eerst op de BOM-namen die pagina's zelf onthouden
    (overleeft een hernoeming), daarna zoals elke [[link]] (`resolve`). Twee pagina's met dezelfde
    BOM-naam → geen treffer op die grond, net als bij een dubbele titel."""
    r = _norm(naam)
    if not r:
        return None
    treffers = [a for a in pags if r in {_norm(n) for n in bom_namen(a)}]
    if len(treffers) == 1:
        return treffers[0]
    return resolve(naam, pags)


#: De afgeleide blokken: markering → het label op het scherm. Hun INHOUD woont ergens anders —
#: feiten in `meta["feiten"]`, backlinks in de bodies van andere pagina's — en dat is precies
#: waarom ze een markering krijgen in plaats van markdown. Zou de tekst zelf de feiten dragen, dan
#: waren er twee waarheden en veroudert de tweede zonder dat iets zich meldt.
#:
#: DE LIJST IS KORT MET OPZET, om dezelfde reden als `domeinen.ROL_BAKJE`: elke markering erbij is
#: een stuk pagina dat de schrijver niet meer zelf in handen heeft. Een projectbord en KPI's zijn
#: hier bewust buiten gehouden (ontwerpbesluit 21 september 2026).
#: Het label is LETTERLIJK het kopje dat de sectie al droeg ("Links here"), niet een
#: nettere variant: twee namen voor hetzelfde ding is precies wat deze codebase
#: elders al een keer heeft moeten opruimen.
AFGELEID: dict[str, str] = {"facts": "Facts", "backlinks": "Links here"}

#: Alleen een regel die NIETS ANDERS is dan de markering telt. Dezelfde grens als bij de embed en
#: de tool-kaart, en om dezelfde reden: anders verandert één woord in een alinea de vorm van de
#: hele pagina.
MARKER_RE = re.compile(r"^\{\{([a-z]+)\}\}$", re.M)


def marker(naam: str) -> str:
    """De BRONREGEL van een afgeleid blok: `facts` → `{{facts}}`.

    Hij staat hier omdat `MARKER_RE` hier staat. Het blokmenu (`cockpit2_util.BLOK_MENU`) voegt
    deze regel in en de renderer leest hem terug; schreven die twee de accolades zelf, dan was de
    vorm van de markering op drie plekken vastgelegd en herkende de renderer na één wijziging
    niet meer wat het menu invoegt."""
    return "{{%s}}" % naam


def markers(body: str) -> set[str]:
    """De afgeleide blokken die deze pagina zelf plaatst.

    `render_pagina` heeft dit nodig om te weten wat er ONDERAAN nog bij moet: een sectie die de
    schrijver in zijn tekst heeft gezet, hoort er niet nog een tweede keer onder te hangen.

    Leest de BRON en niet het scherm — op het scherm staat de uitkomst, en daar is de markering
    juist uit verdwenen."""
    return {m.group(1) for m in MARKER_RE.finditer(body or "") if m.group(1) in AFGELEID}


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

#: Waar een VOORGESTELDE synthese-alinea wacht tot een mens hem opslaat of weggooit. In de `meta`
#: van de pagina zelf, naast de feiten — geen tweede store voor tekst die alleen van deze pagina
#: is, en dus ook geen tweede plek die kan achterblijven als de pagina verdwijnt.
#:
#: HIJ IS GEEN INHOUD. Een pagina met een wachtend voorstel heeft die tekst NIET: hij staat in het
#: bewerkveld en nergens anders, tot iemand op Save drukt. `body` blijft tot dat moment de waarheid.
SYNTHESE_SLEUTEL = "synthese_concept"


def synthese_concept(a) -> dict:
    """Het wachtende synthese-voorstel van deze pagina, of {}."""
    c = (getattr(a, "meta", None) or {}).get(SYNTHESE_SLEUTEL)
    return c if isinstance(c, dict) and str(c.get("tekst") or "").strip() else {}


def feiten(a) -> list[dict]:
    """De feiten van een pagina. Ze leven in `meta["feiten"]` van dezelfde note — geen tweede
    opslag, en ze reizen dus vanzelf mee in versies, erven en /context."""
    ruw = (getattr(a, "meta", None) or {}).get("feiten")
    return [f for f in ruw if isinstance(f, dict)] if isinstance(ruw, list) else []


#: De grootheden die een feit als GETAL kan dragen, met hun vaste eenheid. ÉÉN plek: het formulier,
#: de weergave en het BOM-scherm lezen allemaal hier.
#:
#: DE EENHEID IS VAST, en dat is geen beperking maar de reden dat er gerekend kan worden. Het
#: BOM-scherm vermenigvuldigt met grammen per component; een vrij eenheid-veld ("per meter",
#: "per paar") zou een getal opleveren dat er niet mee te vermenigvuldigen is. Vandaar ook prijs
#: per KG en niet "per eenheid": dat is de enige prijs die met een gewicht optelt.
#: BEWUST VOORLOPIG: een eenheid per materiaalcategorie (stuk, meter, paar) volgt in een latere
#: scope, zodra de inhoud is uitgezocht — dan rekent de BOM per categorie, niet alles in grammen.
#:
#: CO2 en water horen op de MATERIAALpagina, de prijs op de LEVERANCIERpagina — twee leveranciers
#: van hetzelfde materiaal kunnen verschillend prijzen. Die verdeling dwingt deze tabel niet af;
#: het BOM-scherm leest elke grootheid van de plek waar hij hoort.
GROOTHEDEN: dict[str, dict[str, str]] = {
    "co2e_per_kg": {"label": "CO2e per kg", "eenheid": "kg CO2e/kg"},
    "water_per_kg": {"label": "Water per kg", "eenheid": "L/kg"},
    "prijs_per_kg": {"label": "Cost price per kg", "eenheid": "EUR/kg"},
}


#: Skeletten voor een nieuwe pagina (BOM stuk 3, 1 oktober 2026): sleutel → (label, body).
#: ENGELS, op besluit van Stefan (1 oktober 2026): kopjes en uitlegzinnen die de APP aanlevert zijn
#: systeemoutput — zie "Systeemoutput is Engels, mens-op-mens-tekst mag Nederlands" in docs/CONVENTIES.md.
#: De tekst die een mens eronder schrijft blijft zijn eigen taal. Zelfde termen als `wiki_seed`.
#: GEEN "Supplied by" IN HET MATERIAALSKELET (2 oktober 2026): wie levert, staat in de stuklijst, en
#: `wiki_seed.materiaal_paginas` leidt het daaruit af — net als "Used in". Een handmatige kop zou een
#: tweede plek zijn voor hetzelfde feit.
#: ÉÉN PLEK — het "+ New page"-formulier toont de labels, `artefact_add` vult de body. Het blijft
#: VRIJE TEKST: de kopjes zeggen wat er verwacht wordt, ze dwingen niets af. De zin onder elk kopje
#: beschrijft de vorm, en beweert niets over wat er (nog niet) staat — die zou anders gaan liegen
#: zodra de eigenaar het invult. GEEN `[[…]]` IN DEZE TEKST: dat is een echte wiki-link, en een
#: voorbeeld als `[[link]]` zou een gewenste pagina "link" op elke nieuwe pagina zetten. Leverancier en materiaal zijn gescheiden om dezelfde reden als in
#: `GROOTHEDEN`: de prijs hoort bij de leverancier, CO2 en water bij het materiaal.
#: COMPLIANCE-KLAAR (2 oktober 2026, besluit Stefan): twee secties die het zaad én het skelet allebei
#: schrijven — ÉÉN plek voor hun tekst en hun standaard-open-punten, zodat ze niet uiteenlopen. Zelfde
#: vorm als "CO2 & Water": een feit met grond (`soort` bron of cert), geen nieuw feiten-mechanisme.
DIERLIJK_CHEMISCH = (
    "## Animal-derived & chemical status",
    "As a fact, grounded in a certificate (for example vegan) or the supplier's disclosure: whether "
    "the material contains anything animal-derived, and which dyes and chemicals are used.",
    ("Animal-derived status: not yet verified", "Dye/chemical disclosure: not yet provided"),
)
ARBEID_COMPLIANCE = (
    "## Labor & compliance",
    "As a fact, grounded in an audit, a certificate or the supplier's own policy: where the work is "
    "done, whether wages are verified as living wages, and which compliance policies apply.",
    ("Facility address: not yet provided", "Living wage verification: not yet provided",
     "Compliance policies (modern slavery, child labor, health & safety, anti-discrimination, "
     "union rights): not yet provided"),
)


def _sectie(s: tuple) -> str:
    return f"{s[0]}\n{s[1]}"


def _open(*secties: tuple) -> str:
    return "\n".join(f"- {p}" for s in secties for p in s[2])


SJABLONEN: dict[str, tuple[str, str]] = {
    "materiaal": ("Material page", "\n\n".join((
        "## Characteristics\nWhat it is, what it is made of, what it does in the shoe.",
        "## CO2 & Water\nAs a fact with a value (CO2e per kg, water per kg), grounded in the supplier "
        "TDS or another source. The BOM screen calculates with these values.",
        _sectie(DIERLIJK_CHEMISCH),
        "## Circularity\nWhat can happen to it at the end of its life: reuse, recycling, composting.",
        "## Certification\nAs a fact, grounded in the certificate or Chronicle record.",
        "## Open items\nWhat still needs to be found out.\n" + _open(DIERLIJK_CHEMISCH),
    ))),
    "leverancier": ("Supplier page", "\n\n".join((
        "## Location & contact\nCountry, kind of supplier, contact person.",
        "## Company certification\nAs a fact, grounded in the certificate or Chronicle record.",
        "## Price agreement\nAs a fact with a value (cost price per kg), grounded in the quote or "
        "the contract. The BOM screen calculates with this value.",
        _sectie(ARBEID_COMPLIANCE),
        "## Open items\nWhat still needs to be found out.\n" + _open(ARBEID_COMPLIANCE),
    ))),
}


def maak_waarde(grootheid: str, getal) -> dict | None:
    """`{grootheid, getal}` of None. Fail-closed: een onbekende grootheid, geen getal, een negatief
    of oneindig getal → None. Komma als decimaalteken mag ('2,4')."""
    if grootheid not in GROOTHEDEN:
        return None
    try:
        n = float(str(getal).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    if n != n or n in (float("inf"), float("-inf")) or n < 0:
        return None
    return {"grootheid": grootheid, "getal": n}


def waarde(feit: dict) -> dict | None:
    """De getal-waarde van een feit, opnieuw gevalideerd bij het LEZEN — wat er in de opslag staat
    is niet per se door `maak_waarde` gegaan (oudere data, een handmatige edit)."""
    w = (feit or {}).get("waarde")
    if not isinstance(w, dict):
        return None
    return maak_waarde(str(w.get("grootheid") or ""), w.get("getal"))


def waarde_tekst(w: dict) -> str:
    """'2.4 kg CO2e/kg'. Tot zes decimalen, zonder staartnullen en zonder e-notatie."""
    getal = f"{w['getal']:.6f}".rstrip("0").rstrip(".")
    return f"{getal} {GROOTHEDEN[w['grootheid']]['eenheid']}"


def feit_id(f: dict) -> str:
    """Het vaste id van een feit (4 oktober 2026). Feiten van daarvoor hebben er geen: die krijgen
    een id AFGELEID uit hun inhoud, zodat bewerken en verwijderen ze ook zonder migratie op hun
    inhoud terugvinden in plaats van op hun plek in de lijst — die plek verschuift zodra iemand
    intussen een feit weghaalt, en dan raakte "verwijder nummer 3" het verkeerde feit."""
    if f.get("id"):
        return str(f["id"])
    g = f.get("grond") or {}
    sleutel = json.dumps([f.get("tekst"), g.get("soort"), g.get("ref"), g.get("url")],
                         ensure_ascii=False)
    return "h" + hashlib.sha1(sleutel.encode("utf-8")).hexdigest()[:10]


def maak_feit(tekst: str, *, soort: str = "", ref: str = "", citaat: str = "",
              url: str = "", waarde: dict | None = None, sectie: str = "",
              fid: str = "", op: str = "") -> dict | None:
    """Normaliseer één feit. None bij lege tekst (fail-closed: geen leeg feit in de lijst).
    Een onbekende grond-soort valt weg — het feit blijft dan bestaan, maar heet `ongegrond`.

    `waarde` (uit `maak_waarde`) maakt er een feit MET GETAL van — de vorm die het BOM-scherm leest.
    Het getal krijgt dezelfde grond als de tekst: geen tweede bron-veld, één feit is één bewering.

    `sectie` (4 oktober 2026): onder welk kopje van de pagina dit feit hoort — de `For:`-regel van
    Bulk Import. Optioneel; een feit zonder (of met een niet-bestaande) sectie verdwijnt nooit, hij
    landt bij de weergave in "Other facts".

    `fid`: het id dat het feit houdt bij een BEWERKING; leeg = een nieuw id.
    `op`: bij `attested` de datum van de verklaring (ISO); leeg = vandaag."""
    tekst = " ".join((tekst or "").split())[:_TEKST_MAX]
    if not tekst:
        return None
    grond: dict = {}
    if soort in GROND_SOORTEN:
        grond = {"soort": soort,
                 "ref": (ref or "").strip()[:_REF_MAX],
                 "citaat": " ".join((citaat or "").split())[:_TEKST_MAX],
                 "url": (url or "").strip()[:_URL_MAX]}
        if soort == "attested":
            # UIT EERSTE HAND, ZONDER DOCUMENT (4 oktober 2026). Wie en wanneer zijn het hele bewijs,
            # dus ze staan erbij; een citaat of URL heeft zo'n feit per definitie niet.
            grond.update(citaat="", url="", op=(op or time.strftime("%Y-%m-%d"))[:10])
    uit = {"id": fid or uuid.uuid4().hex[:10], "tekst": tekst, "grond": grond}
    sectie = " ".join((sectie or "").split())[:_SECTIE_MAX]
    if sectie:
        uit["sectie"] = sectie
    if isinstance(waarde, dict) and maak_waarde(str(waarde.get("grootheid") or ""), waarde.get("getal")):
        uit["waarde"] = maak_waarde(str(waarde["grootheid"]), waarde["getal"])
    return uit


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


#: DE LABELS OP DE PAGINA (besluit Stefan, 4 oktober 2026). Eén plek: de chip, de wiki-uitleg en de
#: tests lezen hier. "Self-reported" viel af — een FSC-database of een nieuwsbron is extern; wat deze
#: labels zeggen is wat NoochVille met de bron DEED, niet wie hem schreef.
LABEL = {
    "geen_bron": "no source",                  # geen publieke URL
    "niet_gecheckt": "not yet checked",        # URL + citaat, nog niet nagekeken
    "gevonden": "verified",                    # citaat teruggevonden op de URL (bewijst: de bron zegt het)
    "veranderd": "changed — recheck",          # citaat niet meer op de URL
    "niet_te_lezen": "couldn't check",         # URL niet te lezen (bijv. een PDF) — geen oordeel
    "op_file": "on file, not public",          # gedeeld document zonder publieke vindplaats
    "attested": "attested by {wie}, {wanneer}",  # uit eerste hand, zonder document
    # Een geldig certificaat houdt zijn label "<uitgever> — valid until <datum>": zie grond_status.
}


def grond_status(feit: dict, *, ledger=None, store=None, vandaag: str = "",
                 bestaat=None) -> dict:
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
            return _uit(grond, ONTBREEKT, LABEL["geen_bron"], "no public URL with this citation")
        check = grond.get("check") or {}
        wanneer = str(check.get("op") or "")
        if not check:
            return _uit(grond, ONGECONTROLEERD, LABEL["niet_gecheckt"], "cited source")
        if check.get("gevonden") is True:
            return _uit(grond, GEGROND, LABEL["gevonden"],
                        f"checked {wanneer}" if wanneer else "checked")
        if check.get("gevonden") is False:
            return _uit(grond, VERVALLEN, LABEL["veranderd"],
                        f"checked {wanneer}" if wanneer else "checked")
        # Niet gelukt om te kijken (netwerk, HTTP-fout): dat is géén oordeel over de bron.
        return _uit(grond, ONGECONTROLEERD, LABEL["niet_te_lezen"],
                    f"could not check{': ' + str(check.get('reden')) if check.get('reden') else ''}")

    if soort == "attested":
        # GRIJS, NIET ROOD: het staat vast voor wie het verklaarde, er is alleen geen papier. De
        # bron-check slaat hem over (hij kijkt alleen naar `bron`).
        wanneer = str(grond.get("op") or "")
        try:
            wanneer = time.strftime("%-d %b %Y", time.strptime(wanneer, "%Y-%m-%d"))
        except ValueError:
            pass
        return _uit(grond, ONGECONTROLEERD,
                    LABEL["attested"].format(wie=str(grond.get("ref") or "someone"),
                                             wanneer=wanneer or "date unknown"),
                    "first-hand, no document")

    if soort == "document":
        # GEDEELD, NIET PUBLIEK (4 oktober 2026). Een document dat iemand op deze pagina uploadde
        # maar dat nergens publiek staat (het labrapport van NFW). Grijs en niet rood: er IS een
        # bron, alleen kan niemand buiten NoochVille hem openen en kan de bron-check er niets mee.
        # `bestaat(url)` is optioneel: wie de schijf kan zien (de pagina-weergave) geeft hem mee,
        # en dan wordt een verdwenen bestand eerlijk "no source".
        url = str(grond.get("url") or "")
        if not url or (bestaat is not None and not bestaat(url)):
            return _uit(grond, ONTBREEKT, LABEL["geen_bron"], "the file is no longer on this page")
        return _uit(grond, ONGECONTROLEERD, LABEL["op_file"], "shared document")

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
        # ONGEWIJZIGD (besluit 4 oktober 2026, "certified"): de uitgever en de datum ZIJN hier het
        # label, en ze gaan ook mee in de rol-context van een AI-rol. "certified" alleen zou die
        # informatie weggooien.
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
    from nooch_village.assignments import bemensing

    mens, waarom = bemensing(anchor, assignments, records, alleen_mensen=True)
    if mens:
        return {"rol": anchor, "reden": ""}
    if mens is None:
        # Niet vast te stellen. Dan NIET omleiden: omleiden zegt tegen de eigenaar "jij hebt geen
        # mens", en dat is een bewering over de organisatie die we op dit moment niet kunnen doen.
        # Bij de eigenaar laten mét de echte reden erbij is eerlijk en corrigeert zichzelf zodra
        # de store weer leest.
        return {"rol": anchor, "reden": f"could not check who fills this role ({waarom})"}
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
    # DE VOORGESTELDE TEKST HOORT IN HET BERICHT. Tot B2 stond alleen dit zinnetje in de snippet en
    # zat de eigenlijke tekst in `extra["pagina"]["body"]`, die het inbox-scherm uitklapte. Nu is
    # het bericht een DM en is er geen scherm dat dat blok openvouwt — dan staat er "iemand stelt
    # iets voor" zonder wát. Dat is geen suggestie maar een raadsel, en de hele afspraak is dat de
    # rolvervuller zélf de pagina aanpast als hij het ermee eens is. Daar heeft hij de tekst voor
    # nodig, plus de permalink om hem te kunnen plakken.
    snippet = (f"voorstel voor pagina {titel}: {spanning}"
               f" — voorgestelde tekst: {voorstel.strip()}"
               f" — pagina: {pagina_url(getattr(pagina, 'id', ''))}")
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
