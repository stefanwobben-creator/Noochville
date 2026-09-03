"""Notificaties — een rol of persoon weet dat er een @-mention voor hem/haar is.

Lichtgewicht store (data/notifications.json). Een notificatie heeft een doel (rol of persoon),
verwijst naar het project + de feed-entry, en draagt een snippet voor de weergave.
"""
from __future__ import annotations
import logging
import os
import re
import time
import uuid

from nooch_village.util import atomic_write_json, read_json

log = logging.getLogger("village.notificaties")

# Sleutels die de identiteit van een item vormen: die mag `extra` nooit overschrijven, anders kan
# een aanroeper een item op een ander doel of een andere tijd laten lijken dan het is.
_BESCHERMD = ("id", "target_type", "target_id", "at", "read", "by")

# HET PAD IS HET BEWIJS, NIET DE NAAM. Een schrijfpad weet of er een mens zat te typen; die kennis
# gaat verloren op het moment dat alleen een `by`-string overblijft. Zet dit veld op elk pad waar
# een mens de tekst zelf intikt — dan hoeft de poort hem niet te herkennen om hem met rust te laten.
MENS_GETYPT = "mens_getypt"


# De preview voor de lijst. Op een WOORDGRENS, want een halve zin leest als een defect en niet als
# een samenvatting — dezelfde les als bij de herkomst-regel van de laatste meter.
PREVIEW_MAX = 160


def preview(tekst: str, n: int = PREVIEW_MAX) -> str:
    """De korte afgeleide van een volledige tekst. Eén afleidingsplek, geen tweede feit."""
    t = " ".join(str(tekst or "").split())
    if len(t) <= n:
        return t
    # De ellips telt MEE in het budget: `n` is de maximale lengte van wat je overhoudt, niet van
    # wat je afknipt. Zonder deze regel wordt een tekst zonder spaties n+1 lang, en dan klopt de
    # belofte 'hoogstens n' niet meer. Mijn eigen test wees dat aan.
    ruimte = max(1, n - 1)
    kort = t[:ruimte].rsplit(" ", 1)[0]
    return (kort or t[:ruimte]) + "…"


def volledig(n: dict) -> str:
    """De hele tekst van een notificatie.

    Valt terug op `snippet` voor items van vóór 30 aug 2026: die hebben geen `tekst`, en hun
    origineel is weg. Beter de afgekapte waarheid dan een leeg scherm — maar het is wél afgekapt,
    en dat is precies waarom dit veld nu bestaat."""
    return str((n or {}).get("tekst") or (n or {}).get("snippet") or "")


def _is_mens_lezer(n: dict, data_dir: str) -> bool:
    """Gaat een MENS dit lezen? Een mens-vervulde rol of een persoon.

    DE LEZER BESLIST, NIET DE AFZENDER. Dit stond in `spanning_ontstaat` en keek naar allebei: het
    doel moest een rol zijn (personen vielen af) én de AFZENDER mocht niet slapen. Beide regels
    waren rol-hulpje-regels uit een tijd dat dit een dienst aan een rol was.

    Ze houden geen stand zodra dit een communicatielaag is. Het ijkpunt-bericht van de puls-wacht
    komt van een systeemcomponent zonder rol, laat staan een slaaptoestand — en 17 notificaties gaan
    naar een PERSOON, precies de berichten die een mens direct leest. Een mens die iets leest
    verdient een leesbaar bericht, ongeacht wie het stuurde."""
    tt, tid = str(n.get("target_type") or ""), str(n.get("target_id") or "")
    if not tid:
        return False
    try:
        if tt == "person":
            from nooch_village.people import PeopleStore
            return PeopleStore(os.path.join(data_dir, "people.json")).get(tid) is not None
        if tt == "role":
            from nooch_village.assignments import Assignments, door_mens_bemand
            from nooch_village.governance import Records
            recs = Records(os.path.join(data_dir, "governance_records.json"))
            assign = Assignments(os.path.join(data_dir, "assignments.json"))
            return bool(door_mens_bemand(tid, assign, recs))
    except Exception:                                # noqa: BLE001 — onbekend = niet verrijken
        return False
    return False


def _is_mens_schrijver(n: dict, data_dir: str) -> bool:
    """Heeft een MENS deze tekst getypt? Dan blijft hij zoals hij is.

    DIT IS EEN PRINCIPE, GEEN VOLUMEKWESTIE. De verleiding is om het op het cijfer te gronden — van
    de 262 berichten die een mens leest zijn er 5 door een mens getypt, dus 'het kost toch niks om
    ze mee te nemen'. Maar dan draait het besluit om zodra dat cijfer groeit, en gaan we op een dag
    de eigen woorden van mensen herschrijven.

    De echte grond: een mens-getypt bericht IS al mensentaal — precies de eindvorm die deze laag
    nastreeft. Er valt niets te vertalen. En andermans woorden herschrijven is geen leesbaarheid
    maar inmenging.

    De voorwaarde is dus tweeledig: een mens LEEST dit én een machine SCHREEF het.

    HET PAD WINT VAN DE NAAM. Eerst keek dit alleen naar `by`, en dan hangt de regel aan of we de
    afzender toevallig kunnen thuisbrengen. Dat gaat mis waar het het meeste pijn doet: een
    dialoog-comment van een uitgelogde of onbekende gebruiker viel terug op `by="dialoog"`, en een
    eigen spanning in je eigen inbox draagt `by="zelf"` — allebei onmiskenbaar mens-getypt, allebei
    'niet herkend', dus allebei herschreven. De naam ontbrak; het pad wist het wél.

    Daarom is `MENS_GETYPT` de eerste toets. Alleen een pad waar écht geen mens zat te typen is
    machine-tekst; ontbrekende auteur-herkenning is dat niet.

    Fail-richting: staat het pad-merk er niet én kennen we de afzender niet, dan geldt het als
    machine-tekst. Dat blijft de goedkope kant — maar de rand hierboven laat zien dat 'onbekend'
    te vaak 'mens zonder naam' betekende om er de hele regel op te bouwen."""
    if MENS_GETYPT in n:
        # HET PAD WEET HET BETER DAN DE INDIENER. Staat het merk er expliciet — ook op False — dan
        # heeft het schrijfpad de vraag al beantwoord, en die kennis is beter dan wat we uit `by`
        # kunnen raden. Op prod van 1 sep zette een mens een MACHINE-melding door; `by` was hij, de
        # tekst was niet van hem. De afzender is niet de auteur.
        return n[MENS_GETYPT] is True
    by = str(n.get("by") or "").strip()
    if not by:
        return False
    try:
        from nooch_village.people import PeopleStore
        mensen = PeopleStore(os.path.join(data_dir, "people.json")).all()
    except Exception:                                # noqa: BLE001
        return False
    for p in mensen:
        if by == getattr(p, "id", "") or by == (getattr(p, "name", "") or "").strip():
            return True
    return False


#: Wat in geen enkele naar-mens-tekst hoort. De poort BLOKKEERT niets — hij meldt zich, zodat een
#: volgend lek in het LOG verschijnt in plaats van in iemands inbox.
_COMMANDO_IN_TEKST = re.compile(
    r"\b(?:python\s+-m|\./venv/bin/|sudo\s+\w|systemctl\s+\w|journalctl\s+-|git\s+[a-z]+\s)", re.I)


def _meld_commando(n: dict) -> None:
    """DE INVARIANT WAARNEEMBAAR MAKEN. "Een terminalopdracht hoort in geen enkele naar-mens-tekst"
    was een regel zonder waarnemer, en dus lekte hij stil: het scherm strijkt hem weg, maar als het
    strijken een keer niet gebeurt merkt niemand het — je ziet het pas in je inbox.

    Zelfde vorm als 'handhaving vereist waarneembaarheid', nu op de leesbaarheidslaag. Geen blokkade:
    een melding tegenhouden is duurder dan een lelijke melding doorlaten."""
    tekst = volledig(n)
    if not tekst or not _COMMANDO_IN_TEKST.search(tekst):
        return
    from nooch_village.systeemtaal import ontjargon
    if _COMMANDO_IN_TEKST.search(ontjargon(tekst)):
        log.warning("LEESBAARHEID: notificatie %s draagt een commando dat de swap niet weghaalt — "
                    "dit komt zo op iemands scherm: %r", n.get("id"), tekst[:120])


def _door_de_poort(n: dict, data_dir: str, eigen=None) -> dict:
    """DE POORT, en hij zit in `add()` — de klasse-methode die álle schrijvers aanroepen.

    Hij hing hiervóór aan de INSTANTIE (`set_verrijker`), en dat is geen poort maar een suggestie:
    zeven plekken in het dorp bouwen hun eigen `NotifStore`, en de haak werd op twee gezet — beide
    in de web-laag. Het hoofdkanaal van de daemon naar de founder, het puls-wacht-alarm en de
    escalatie-skill gingen er dus nooit langs. Een achtste store zou hem opnieuw missen.

    Hier kan niemand er meer omheen: elke instantie draagt hem, want de klasse draagt hem.

    Twee vragen, en ze doen niet hetzelfde:
      * LEEST een mens dit? Zo nee, dan gebeurt er niets. De lezer opent de poort.
      * SCHREEF een mens dit? Zo ja, dan wordt er wél getypeerd (dat zegt alleen wát het is) maar
        niet HERschreven (dat vervangt de zin die de lezer ziet). Mensentaal hoeft niet vertaald te
        worden, en andermans woorden herschrijven is inmenging — maar hem daarom ook niet meer
        routeren zou van een principe een storing maken. Zie `maak_verrijker`.

    `eigen` is er alleen voor tests. Fail-soft: kan de poort niet draaien, dan blijft de rauwe
    notificatie gewoon staan — een spanning die niet verrijkt kon worden is nog steeds een spanning."""
    try:
        if eigen is not None:
            return eigen(dict(n)) or {}
        # DE LEZER OPENT DE POORT: gaat geen mens dit lezen, dan hoeft er niets te gebeuren.
        if not _is_mens_lezer(n, data_dir):
            return {}
        # DE SCHRIJVER BEPAALT HOEVER HET GAAT, en dat is een fijnere grens dan 'wel of niet'.
        # Typeren zegt wát dit is en laat de tekst staan; herschrijven vervángt de zin die de lezer
        # ziet. Alleen dat tweede is inmenging in andermans woorden — zie `maak_verrijker`.
        from nooch_village.assignments import Assignments
        from nooch_village.governance import Records
        from nooch_village.spanning_ontstaat import maak_verrijker
        verrijk = maak_verrijker(Records(os.path.join(data_dir, "governance_records.json")),
                                 Assignments(os.path.join(data_dir, "assignments.json")),
                                 data_dir, herschrijf=not _is_mens_schrijver(n, data_dir))
        return verrijk(dict(n)) or {}
    except Exception as e:                           # noqa: BLE001 — verrijken mag nooit blokkeren
        log.warning("poort op notificatie %s faalde: %s", n.get("id"), e)
        return {}


class NotifStore:
    """Notificaties, plus de haak bij het ONTSTAAN.

    Elke nieuwe spanning gaat door `add`: de enige trechter waar ze allemaal doorheen komen. De
    store blijft dom — hij roept alleen een haak aan die de aanroeper zet — zodat hier geen
    model-aanroep in de opslaglaag belandt.

    De haak zit op de INSTANTIE en niet op de module. Een globale versie lekte naar elke test die
    de cockpit opstartte: die zette hem, en daarna deed elke `add` in elke andere test stilletjes
    een model-aanroep. Een haak die verder reikt dan het object dat hem draagt, is geen haak maar
    een verrassing."""

    def __init__(self, path: str, verrijker=None):
        self.path = path
        self._verrijker = verrijker              # alleen voor tests: None = de eigen poort
        self._items: list[dict] = read_json(path, [], expect=list)

    @property
    def data_dir(self) -> str:
        """De map waar deze store in leeft — genoeg om zelf zijn records te vinden."""
        return os.path.dirname(self.path) or "."

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, target_type: str, target_id: str, project_id: str, entry_id: str = "",
            by: str = "", snippet: str = "", *, extra: dict | None = None) -> dict:
        """Voeg een item toe. `extra` zijn velden die bij het ONTSTAAN al bekend zijn (type,
        bevinding, en bv. de pagina waar een voorstel over gaat). Beschermde sleutels blijven
        onaanraakbaar; wie iets al weet, mag het niet stiekem over de identiteit heen schrijven.

        TWEE VELDEN, ÉÉN WAARHEID. `tekst` is de volledige, ongekapte tekst; `snippet` is de
        AFGELEIDE preview voor de lijst. Ze zijn geen twee feiten: `snippet` wordt hier, op één
        plek, uit `tekst` afgeleid — verander de afleiding en alles verandert mee.

        WAAROM DIT MOEST, gemeten op prod 30 aug 2026. Dit veld heette `snippet`, was gecapt op 160
        tekens, en was tegelijk de ENIGE kopie. Van de 566 notificaties waren er 220 exact 160
        tekens lang; de langste tekst in de hele store was 160. Elke spanning die langer was, werd
        bij het schrijven halverwege een zin afgehakt en het origineel bestond nergens meer: van de
        223 afgekapte items was er in 30 nog een langere versie in de project-feed terug te vinden,
        en in 193 niet. Een veld dat 'samenvatting' heet maar de enige kopie is, is geen
        samenvatting maar een amputatie."""
        volledig = (snippet or "")
        n = {
            "id": uuid.uuid4().hex[:10],
            "target_type": target_type, "target_id": target_id,
            "project_id": project_id, "entry_id": entry_id,
            "by": by, "tekst": volledig, "snippet": preview(volledig),
            "at": time.time(), "read": False,
        }
        n.update({k: v for k, v in (extra or {}).items() if k not in _BESCHERMD})
        # WIE DIT SCHREEF IS EEN FEIT VAN NU, geen live afleiding. Staat het merk er nog niet, dan
        # zetten we het hier één keer, zodat elke latere lezer (de poort, de leesbaarheidslaag, het
        # scherm) hetzelfde veld leest in plaats van people.json opnieuw te bevragen. Verandert die
        # store later — iemand hernoemd, iemand weg — dan blijft staan wat waar wás toen er getypt
        # werd, en dat is precies de vraag die we stellen.
        # Staat het merk er al (het schrijfpad WEET of er getypt is), dan wint dat: alleen als
        # niemand het zegt leiden we het af uit `by`. Een expliciet `False` blijft dus False —
        # anders zou de afleiding uit de indiener het pad-oordeel overschrijven, en precies dat lekte.
        if MENS_GETYPT not in n and _is_mens_schrijver(n, self.data_dir):
            n[MENS_GETYPT] = True
        self._items.append(n)
        self._save()
        # Een item dat zijn type al bij het ontstaan kent (een pagina-voorstel weet exact wat het
        # vraagt) gaat NIET langs de herschrijf-poort: die is er om een rauwe signalering te
        # typeren, en een dure LLM-call zou hier alleen een al bekend antwoord overschrijven.
        _meld_commando(n)          # invariant-alarm, blokkeert niets
        if not n.get("type"):
            extra = _door_de_poort(n, self.data_dir, self._verrijker)
            if extra:
                n.update(extra)
                self._save()
        return n

    def for_targets(self, targets) -> list[dict]:
        """Notificaties voor een set (type, id)-doelen, nieuwste eerst."""
        s = {(t, i) for t, i in targets}
        out = [n for n in self._items if (n.get("target_type"), n.get("target_id")) in s]
        return sorted(out, key=lambda n: -(n.get("at") or 0))

    def unread_count(self, targets) -> int:
        return sum(1 for n in self.for_targets(targets) if not n.get("read"))

    def mark_read(self, targets) -> None:
        s = {(t, i) for t, i in targets}
        changed = False
        for n in self._items:
            if (n.get("target_type"), n.get("target_id")) in s and not n.get("read"):
                n["read"] = True; changed = True
        if changed:
            self._save()

    # ── inbox-levenscyclus: nieuw → gelezen → verwerkt (+ archiveren) ─────────────
    @staticmethod
    def status_of(n: dict) -> str:
        """De inbox-status van één notificatie: 'verwerkt' (mens is klaar), 'gelezen' (geopend, nog te
        doen), of 'nieuw' (nog niet bekeken). Afgeleid van de vlaggen, backward-compat met oude items."""
        if n.get("done"):
            return "klaar"
        if n.get("processed"):
            return "verwerkt"
        return "gelezen" if n.get("read") else "nieuw"

    def open_for_targets(self, targets) -> list[dict]:
        """De inbox-wachtrij: NIET-gearchiveerde, NIET-weggegooide notificaties voor deze doelen, nieuwste
        eerst."""
        # `done` erbij: sluiten hoort de wachtrij te verkorten, anders is het geen sluiten.
        # BEWUST GEEN retro-close op `processed`: dat veld zet ook `mark_item_processed`, en dat is
        # "bekeken", geen besluit. Zes bestaande items dorp-breed dragen het; die stilletjes
        # dichtdoen zou geschiedenis herschrijven op een aanname.
        return [n for n in self.for_targets(targets)
                if not n.get("archived") and not n.get("deleted") and not n.get("done")]

    def _find(self, notif_id: str) -> dict | None:
        return next((n for n in self._items if n.get("id") == notif_id), None)

    def mark_item_read(self, notif_id: str) -> bool:
        """Nieuw → gelezen (geopend, maar nog te verwerken). Idempotent; verandert 'verwerkt' niet."""
        n = self._find(notif_id)
        if n is None or n.get("read"):
            return False
        n["read"] = True
        self._save()
        return True

    def mark_item_processed(self, notif_id: str, outcome: str = "", by: str = "") -> bool:
        """Markeer als verwerkt (bron afgehandeld). Handmatig door de mens, of autonoom door de rol zelf.
        `outcome` (welke uitkomst) en `by` (wie verwerkte) worden vastgelegd als historie, zodat je later
        kunt terugkijken hoe een signaal is afgehandeld. Beide optioneel (backward-compat)."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["read"] = True
        n["processed"] = True
        if outcome:
            n["outcome"] = str(outcome)[:200]
        if by:
            n["processed_by"] = str(by)[:80]
        self._save()
        return True

    def set_poort(self, notif_id: str, verdict: dict) -> bool:
        """Leg het oordeel van de tensie-poort op het item vast.

        Op het item en niet in een aparte store, om dezelfde reden als `result_ref` bij de Kroniek:
        het oordeel hoort bij het ding waarover het gaat. Zo kan de weergave groeperen zonder de
        poort (en dus een LLM-call) opnieuw te draaien bij elke pageload."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["poort"] = dict(verdict or {})
        self._save()
        return True

    def archive_item(self, notif_id: str) -> bool:
        """Verwerkt item uit de wachtrij halen. Alleen wat verwerkt is mag weg (schone regie)."""
        n = self._find(notif_id)
        if n is None or not n.get("processed"):
            return False
        n["archived"] = True
        self._save()
        return True

    # ── verwerk-record: stapelbare uitkomsten per spanning (mens én AI) ─────────────
    def add_outcome(self, notif_id: str, intent: str = "", otype: str = "", ref: str = "",
                    label: str = "", by: str = "") -> dict | None:
        """Voeg een uitkomst toe aan het verwerk-record van een item ZONDER het te sluiten. Zo kun je
        meerdere uitkomsten op één spanning stapelen (het item blijft open) tot je expliciet 'klaar' bent.
        Elke entry legt intentie, uitkomst-type, een verwijzing, een leesbaar label, wie en wanneer vast:
        het gedrag-record dat je later op een raadsvergadering kunt bespreken (stopt een rol bij de eerste
        uitkomst of haalt hij er meer uit?). Zet het item op 'gelezen'. Onbekend id → None."""
        n = self._find(notif_id)
        if n is None:
            return None
        entry = {"intent": str(intent)[:40], "otype": str(otype)[:40], "ref": str(ref)[:120],
                 "label": str(label)[:200], "by": str(by)[:80], "at": time.time()}
        n.setdefault("verwerkingen", []).append(entry)
        n["read"] = True
        self._save()
        return entry

    def mark_done(self, notif_id: str, by: str = "") -> bool:
        """Sluit een item ('klaar'): het is af en verdwijnt uit de wachtrij.

        HIJ SLOOT NIETS. Deze methode zette `read` en `processed` — precies dezelfde twee velden als
        `mark_item_processed`, dat alleen "bekeken/afgehandeld" betekent — terwijl
        `open_for_targets` uitsluitend op `archived` en `deleted` filtert. Sluiten schreef dus een
        staat die de wachtrij niet als gesloten kende, en een afgehandelde spanning bleef staan. Voor
        altijd, en voor elke spanning; Stefan liep erop vast met een project dat wél bestond.

        Nu is er een eigen vlag. `processed` blijft staan voor backward-compat, maar `done` is wat
        telt — en `done_at` maakt achteraf te zien wanneer iets dichtging."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["read"] = True
        n["processed"] = True
        n["done"] = True
        n["done_at"] = time.time()
        if by:
            n["processed_by"] = str(by)[:80]
        self._save()
        return True

    @staticmethod
    def verwerkingen_of(n: dict) -> list[dict]:
        """Het verwerk-record van een item, oudste eerst. Backward-compat: een oud item met alleen een
        enkel `outcome`-veld wordt als één entry getoond."""
        vs = list(n.get("verwerkingen") or [])
        if vs:
            return vs
        if n.get("outcome"):
            return [{"intent": "", "otype": "", "ref": "", "label": n.get("outcome"),
                     "by": n.get("processed_by", ""), "at": n.get("at")}]
        return []

    def delete_item(self, notif_id: str) -> bool:
        """Prullenbak: haal ruis die je niet wilt verwerken uit de wachtrij. Anders dan archiveren mag dit
        ook op een nog-niet-verwerkt item. Zacht (dismissed-vlag), zodat de data niet echt verdwijnt."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["deleted"] = True
        self._save()
        return True

    def all(self) -> list[dict]:
        return list(self._items)
