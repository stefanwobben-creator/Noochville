"""acties.py — persoonlijke acties: het lichtste ding dat een "volgende stap" kan dragen.

WAAROM DIT BESTAAT. Er zat een gat tussen twee dingen die er al waren:

  * een PROJECT (`projects.create`) eist een rol- of cirkel-eigenaar plus een trigger-type. Dat is
    het juiste gewicht voor werk dat een uitkomst moet opleveren, en veel te zwaar voor één regel
    tekst uit een telefoongesprek;
  * een DM (`channels`) heeft sinds de vereenvoudiging van 20 september 2026 GEEN eigen velden meer,
    dus ook geen status. Een "actie" uit het werkoverleg landde daar, en had daarmee geen
    klaar-knop en geen lijst om op terug te komen. Verstuurd, en daarna weg.

Een actie is het derde: een regel tekst met een vinkje, van één mens.

WAAROM `acties.py` EN NIET `mijn_acties.py`. De store houdt de acties van IEDEREEN; "mijn" is het
perspectief van één scherm, niet van de opslag. Elke andere store hier heet naar wat hij bewaart
(`channels`, `people`, `projects`, `library`) en geen enkele naar wie ernaar kijkt. De PAGINA heet
wél "Mijn acties", want daar klopt het bezittelijk voornaamwoord: je ziet je eigen lijst.

WAT ER BEWUST NIET IN ZIT. Geen trigger-type, geen scope, geen checklist, geen deadline, geen
prioriteit, geen toewijzing-aan-een-ander. Elk van die velden is een reden om even na te denken
voor je iets opschrijft, en dan is het schrift weer trager dan een papieren schrift. Wie meer nodig
heeft, maakt een project — dat bestaat al.

Vijf velden, en de vijfde is de enige die uitleg vraagt:

    tekst      de regel zelf
    done       af of niet
    person     van wie hij is (de eigenaar; geen rol, geen cirkel)
    project    optioneel gekoppeld project — de enige relatie die een actie kent
    herkomst   waar hij vandaan kwam, als vrije tekst ("werkoverleg", "")

`herkomst` is GEEN trigger-type en classificeert niets: hij wordt nergens op gefilterd en nergens
op geteld. Hij bestaat omdat een actie die uit een werkoverleg komt anders uit het niets in je
lijst verschijnt, en "waarom ligt dit hier" is precies de vraag die een DM tenminste nog
beantwoordde. Eén regel context, verder niets.

ZICHTBAARHEID, en er komt geen nieuw niveau bij:

    geen project  → alleen de eigenaar. Dit is een schrift.
    wel project   → het leesrecht van DAT project (`views.messages.mag_project_lezen`), want dan
                    heb je hem zelf aan gezamenlijk werk gehangen.

Die tweede regel staat bewust niet hier uitgeschreven maar in `zichtbaar_voor`, die de bestaande
projectregel aanroept. Een tweede formulering van "mag jij dit project zien" zou na één wijziging
uit de pas lopen — dezelfde reden als overal elders in dit dorp.
"""
from __future__ import annotations

import time
import uuid

from nooch_village.util import JsonStore

#: Hoe lang de tekst van één actie mag zijn. Ruim, maar niet eindeloos: wie een alinea opschrijft
#: is geen actie aan het noteren maar een notitie aan het maken, en daar is de wiki voor.
TEKST_MAX = 500


def _normaliseer(tekst) -> str:
    """Eén regel, geen dubbele spaties, afgekapt. Zelfde vorm als `channels._normaliseer_naam`:
    een actie staat in een lijst naast een bolletje, en een tekst die afbreekt duwt die lijst uit
    elkaar."""
    return " ".join(str(tekst or "").split())[:TEKST_MAX]


class ActieStore(JsonStore):
    """De acties van het hele dorp, in `data/acties.json`.

    JsonStore en geen eigen bestandsafhandeling: die basis is slot-veilig (zie het
    JsonStore-programma in CLAUDE.md) en dit is een store die vanaf twee kanten geschreven wordt —
    door een mens die typt, en door `route_werk` tijdens een werkoverleg. `_WRITE_METHODS` is wat
    die veiligheid aanzet: elke genoemde methode neemt het slot en herleest onder dat slot, zodat
    de cockpit en de daemon elkaars schrijf niet overschrijven."""

    _WRITE_METHODS = ("add", "zet", "koppel", "wis_afgerond", "verwijder")

    # ── schrijven ────────────────────────────────────────────────────────────
    def add(self, person: str, tekst: str, *, project: str = "", herkomst: str = "") -> dict | None:
        """Eén regel erbij. Geeft het item terug, of None bij een lege tekst of eigenaar.

        FAIL-CLOSED OP ALLEBEI. Een actie zonder eigenaar hoort bij niemand en komt dus op geen
        enkele lijst terug; een lege actie is geen actie. In geen van beide gevallen is er iets
        zinnigs te bewaren, en stilzwijgend iets aanmaken dat nooit meer opduikt is erger dan
        niets doen."""
        tekst = _normaliseer(tekst)
        if not (person and tekst):
            return None
        item = {
            "id": uuid.uuid4().hex[:12],
            "person": str(person),
            "tekst": tekst,
            "done": False,
            "project": str(project or ""),
            "herkomst": str(herkomst or ""),
            "at": time.time(),
            "done_at": 0.0,
        }
        self._items[item["id"]] = item
        self._save()
        return dict(item)

    def zet(self, aid: str, person: str, *, done: bool) -> bool:
        """Af- of weer aanvinken. Alleen de EIGENAAR, ook als het item aan een project hangt.

        Zichtbaarheid en zeggenschap zijn hier twee dingen: een collega mag een gekoppelde actie
        zien staan, maar hem afvinken is zeggen "ik heb dit gedaan" namens iemand anders. Dat is
        precies de verwarring die een gedeelde checklist wél oplost (daar is het gedeeld werk) en
        een persoonlijke lijst niet hoort te hebben."""
        it = self._items.get(aid or "")
        if it is None or it.get("person") != person:
            return False
        if bool(it.get("done")) == bool(done):
            return False
        it["done"] = bool(done)
        it["done_at"] = time.time() if done else 0.0
        self._save()
        return True

    def koppel(self, aid: str, person: str, project: str) -> bool:
        """Hang deze actie aan een project, of haal hem er weer af (lege `project`).

        DIT IS DE ENIGE PLEK WAAR DE ZICHTBAARHEID VERANDERT, en daarom staat hier geen controle
        op het project zelf: die hoort bij de aanroeper, die weet welke projecten deze mens mag
        zien. Zou de store zelf gaan oordelen, dan is er een tweede plek waar dat gebeurt."""
        it = self._items.get(aid or "")
        if it is None or it.get("person") != person:
            return False
        if it.get("project") == str(project or ""):
            return False
        it["project"] = str(project or "")
        self._save()
        return True

    def wis_afgerond(self, person: str) -> int:
        """Gooi de afgevinkte acties van deze mens weg. Geeft terug hoeveel er weg zijn.

        ECHT WEG, geen archief. Een afgevinkte actie is geen historie: de dingen die het waard zijn
        om terug te lezen staan in een project of in de Kroniek. Een lijst die alles bewaart wordt
        een lijst waar je niet meer in durft te kijken, en dat is precies wat een schrift níét is."""
        items = self._items
        weg = [k for k, v in items.items() if v.get("person") == person and v.get("done")]
        for k in weg:
            items.pop(k, None)
        if weg:
            self._save()
        return len(weg)

    def verwijder(self, aid: str, person: str) -> bool:
        """Eén actie weg, ook als hij nog open staat. Alleen de eigenaar."""
        items = self._items
        it = items.get(aid or "")
        if it is None or it.get("person") != person:
            return False
        items.pop(aid, None)
        self._save()
        return True

    # ── lezen ────────────────────────────────────────────────────────────────
    def get(self, aid: str) -> dict | None:
        it = self._items.get(aid or "")
        return dict(it) if it else None

    def voor(self, person: str) -> list[dict]:
        """De acties van deze mens: open eerst (nieuwste bovenaan), daarna de afgevinkte.

        NIEUWSTE BOVENAAN, en dat is niet de gebruikelijke volgorde van een lijst. Het is wel de
        volgorde van het invoerveld: je typt bovenaan en ziet de regel meteen op de plek waar je
        hem neerzette. Een regel die na het typen onderaan verschijnt voelt alsof er niets
        gebeurde."""
        if not person:
            return []
        rij = [dict(v) for v in self._items.values()
               if v.get("person") == person]
        rij.sort(key=lambda a: (bool(a.get("done")), -float(a.get("at") or 0)))
        return rij

    def open_aantal(self, person: str) -> int:
        """Hoeveel er open staan. Voor het balkje in de zijbalk — zonder dat getal is een
        persoonlijke lijst een scherm dat je moet ONTHOUDEN te openen, en dan komt een actie uit
        het werkoverleg er net zo stil in te liggen als in de DM waar hij uit komt."""
        return sum(1 for v in self._items.values()
                   if v.get("person") == person and not v.get("done"))

    def bij_project(self, pid: str) -> list[dict]:
        """Alle acties die aan dit project hangen, van wie dan ook. Ongesorteerd op eigenaar —
        de aanroeper bepaalt wat hij ermee toont."""
        if not pid:
            return []
        return [dict(v) for v in self._items.values()
                if v.get("project") == pid]


def zichtbaar_voor(st, actie: dict, ik: str) -> bool:
    """Mag deze mens deze actie zien? \xc9\xc9N regel, gesteld door het scherm \xe9n door elke actie.

    Twee takken, en de tweede leent hij:

        geen project  → alleen de eigenaar
        wel project   → het leesrecht van dat project

    DE PROJECTREGEL WORDT AANGEROEPEN, NIET NAGESCHREVEN. `mag_project_lezen` kent de
    priv\xe9-vlag en de cirkel-lidmaatschapscheck; die hier nog eens uitschrijven levert een tweede
    formulering op die na \xe9\xe9n wijziging anders antwoordt — en dan toont het ene scherm iets wat
    het andere verbergt.

    Fail-closed: geen actie, geen mens, of een gekoppeld project dat niet (meer) bestaat → alleen
    de eigenaar. Een verdwenen project mag een actie niet stilzwijgend openzetten."""
    if not (actie and ik):
        return False
    if actie.get("person") == ik:
        return True
    pid = str(actie.get("project") or "")
    if not pid:
        return False
    from nooch_village.views.messages import mag_project_lezen
    return mag_project_lezen(st, pid, ik)
