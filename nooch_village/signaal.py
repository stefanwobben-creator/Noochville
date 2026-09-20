"""Waar een signalering landt: bij een MENS, als DM.

Eén plek die bepaalt wie een melding krijgt, gebruikt door twee kanten:

  * `notif_migratie` — de 371 bestaande `NotifStore`-rijen (eenmalig, stap A)
  * `cockpit2._signaleer` — alles wat vanaf nu ontstaat (stap B)

Dat is met opzet dezelfde functie en niet twee keer dezelfde regels: liep de routering van de
migratie uiteen met die van nieuwe meldingen, dan zou dezelfde rol-id vandaag bij Lotte landen en
morgen bij Stefan, zonder dat iets zich meldt.

DE REGEL, in deze volgorde:
  1. doel is een PERSOON                            → die persoon
  2. doel is een ROL met precies één mens-vervuller → die mens (ook als de rol gearchiveerd is)
  3. doel is een ROL zonder mens-vervuller          → de Circle Lead van zijn cirkel
  3b. en heeft die er ook geen                      → de terugval (de founder)
  4. doel is een ROL met MEER DAN ÉÉN vervuller     → niemand; de aanroeper beslist wat hij doet

Geval 4 is geen fout maar een grens. Bij de migratie betekent het "parkeren en melden"; bij een
nieuwe melding betekent het "naar alle vervullers", want daar is een dubbel bericht minder erg dan
een bericht dat niemand krijgt. Dat verschil staat hier expliciet omdat het een keuze is.
"""
from __future__ import annotations

from nooch_village import channels

#: Wie de meldingen krijgt van een rol die niemand meer vervult.
TERUGVAL_ROL = "mother_earth__nooch__strategic_lead_founder_steward"

NAAR_PERSOON, NAAR_VERVULLER, NAAR_LEAD, NAAR_TERUGVAL, MEERDERE, ONBEKEND = (
    "persoon", "vervuller", "circle-lead", "terugval", "meerdere-vervullers", "onbekend-doel")


def mensen_van(st, rol: str) -> list[str]:
    """De mensen die deze rol vervullen. Fail-soft: een stukke store levert geen vervullers op in
    plaats van een exceptie — dit pad wordt ook door schermen gebruikt (`cockpit2.mens_vervullers`)
    en een kapotte records-store mag een pagina niet omver halen."""
    try:
        rec = st.records.get(rol)
        return [f.id for f in st.assign.fillers_of(rol, rec) if f.type == "person"] if rec else []
    except Exception:                                         # noqa: BLE001
        return []


def terugval(st) -> str:
    """De mens die meldingen krijgt als er niemand anders te vinden is.

    NEEMT DE EERSTE ALS ER MEER ZIJN, en dat is een correctie. De eerste versie gaf "" terug zodra
    de terugval-rol méér dan één vervuller had — een vangnet dat het begeeft juist omdat er meer
    mensen beschikbaar zijn. Gevonden op een test waar het zaad twee vervullers op die rol zet: de
    melding kwam nergens aan, zonder fout. Gesorteerd, zodat dezelfde melding niet de ene keer bij
    de een en de andere keer bij de ander landt."""
    mensen = sorted(mensen_van(st, TERUGVAL_ROL))
    return mensen[0] if mensen else ""


def ontvangers(st, doel_type: str, doel_id: str) -> tuple[list[str], str]:
    """(persoon_ids, reden). Lege lijst = niet te routeren; de reden zegt waarom."""
    doel_id = str(doel_id or "")
    if doel_type == "person":
        if st.people.get(doel_id):
            return [doel_id], NAAR_PERSOON
        # ONBEKENDE PERSOON → TERUGVAL, niet weggooien. Dit is geen theorie: een GAST die via
        # "+ tension" iets noteert had geen persoon-id, en onder de eerste versie van deze functie
        # verdween dat punt spoorloos — het oude pad zette het nog als item op de pseudo-persoon
        # "guest". Een genoteerde spanning die nergens aankomt is het ergste wat deze laag kan doen:
        # de schrijver denkt dat hij iets heeft vastgelegd.
        terug = terugval(st)
        return ([terug], NAAR_TERUGVAL) if terug else ([], ONBEKEND)
    if doel_type != "role" or not doel_id:
        terug = terugval(st)
        return ([terug], NAAR_TERUGVAL) if terug else ([], ONBEKEND)
    mensen = mensen_van(st, doel_id)
    if len(mensen) == 1:
        return mensen, NAAR_VERVULLER
    if len(mensen) > 1:
        return mensen, MEERDERE
    # EERST DE CIRCLE LEAD, DAN PAS DE FOUNDER. Een rol zonder mens valt in dit dorp al overal
    # terug op de Circle Lead van de omvattende cirkel — `wiki.ontvanger` doet het zo, en
    # `claims_board` ook. Die regel hier overslaan betekende dat een melding voor een AI-vervulde
    # rol langs de dichtstbijzijnde mens schoot, regelrecht naar de founder, of helemaal nergens
    # heen als die rol in dit dorp niet bestaat. Gevonden op `test_rol_kanaal`.
    lead = _circle_lead(st, doel_id)
    if lead:
        return [lead], NAAR_LEAD
    terug = terugval(st)
    return ([terug], NAAR_TERUGVAL) if terug else ([], ONBEKEND)


def _circle_lead(st, rol: str) -> str:
    """De mens die de Circle Lead van de omvattende cirkel vervult, of "" als die er niet is."""
    try:
        from nooch_village import artefacts
        cirkel = artefacts.circle_of(rol, st.records)
        if not cirkel:
            return ""
        mensen = sorted(mensen_van(st, f"{cirkel}__circle_lead"))
        return mensen[0] if mensen else ""
    except Exception:                                         # noqa: BLE001
        return ""


def stuur(st, doel_type: str, doel_id: str, tekst: str, *, by: str = "village",
          herkomst: dict | None = None) -> list[str]:
    """Stuur één signalering. Geeft de kanalen terug waarin hij is geland (leeg = nergens).

    Bij meerdere vervullers gaat hij naar ALLEMAAL. Een dubbel bericht is hier minder erg dan een
    bericht dat niemand krijgt — dit is nieuw werk dat iemand moet oppakken, geen historie die
    precies één plek hoort te hebben.
    """
    wie, _reden = ontvangers(st, doel_type, doel_id)
    uit = []
    for persoon in wie:
        if not persoon:
            continue
        kanaal = channels.dm_kanaal(str(by or "village"), persoon)
        if st.channels.post(kanaal, tekst, author_type="role", author_id=str(by or "village"),
                            herkomst=herkomst):
            uit.append(kanaal)
    return uit


class _MiniStores:
    """Het minimum dat `stuur` nodig heeft, opgebouwd uit een datamap.

    WAAROM DIT BESTAAT. Zes plekken buiten de cockpit stuurden een melding: de daemon
    (`inhabitant`, `roles`, `puls_wacht`), de claims-board, de human-inbox en de escaleer-skill.
    Die bouwden elk hun eigen `NotifStore(os.path.join(data_dir, "notifications.json"))` — zes
    plekken die wisten waar een bestand stond. `cockpit2._Stores` importeren kan niet: dat trekt de
    hele webkant de daemon in.

    Vier stores, niet meer. Wie hier iets bij wil zetten moet zich eerst afvragen of hij niet
    gewoon `_Stores` nodig heeft."""

    __slots__ = ("records", "people", "assign", "channels")

    def __init__(self, data_dir: str):
        import os
        from nooch_village.assignments import Assignments
        from nooch_village.channels import ChannelStore
        from nooch_village.governance import Records
        from nooch_village.people import PeopleStore
        from nooch_village.projects import ProjectLedger

        pad = lambda naam: os.path.join(data_dir, naam)
        self.records = Records(pad("governance_records.json"))
        self.people = PeopleStore(pad("people.json"))
        self.assign = Assignments(pad("assignments.json"))
        # De ledger moet mee: een projectkanaal schrijft daarin, en `ChannelStore` weigert zonder.
        self.channels = ChannelStore(pad("channels.json"), ledger=ProjectLedger(pad("projects.json")))


def stores_van(omgeving, data_dir: str):
    """Een store-object voor `stuur`, dat GEÏNJECTEERDE stores hergebruikt waar ze er zijn.

    Waarom niet altijd vanaf het pad: `claims_board` en de daemon krijgen hun `records` en
    `assign` mee (DI, harde regel 2 in CLAUDE.md). Die negeren en alles van schijf herlezen
    betekent dat een test met gestubde stores iets anders meet dan productie — en dat een
    aanroeper die bewust een andere store meegeeft stilzwijgend wordt overruled."""
    mini = _MiniStores(data_dir)
    for naam in ("records", "people", "assign", "channels"):
        gegeven = getattr(omgeving, naam, None)
        if gegeven is not None:
            setattr(mini, naam, gegeven)
    return mini


def stuur_op_pad(data_dir: str, doel_type: str, doel_id: str, tekst: str, *,
                 by: str = "village", herkomst: dict | None = None, omgeving=None) -> list[str]:
    """`stuur`, maar vanaf een datamap in plaats van een `_Stores`. Voor de daemon-kant.

    Fail-soft: een stukke of ontbrekende store levert geen bericht op in plaats van een exceptie.
    Deze paden draaien in een puls of in een skill, en daar mag een melding die niet lukt niet het
    werk eromheen omver halen — maar hij mag ook niet stil zijn, dus hij logt."""
    import logging
    try:
        st = stores_van(omgeving, data_dir) if omgeving is not None else _MiniStores(data_dir)
        return stuur(st, doel_type, doel_id, tekst, by=by, herkomst=herkomst)
    except Exception:                                         # noqa: BLE001
        logging.getLogger("village.signaal").exception(
            "signalering faalde: %s/%s vanaf %s", doel_type, doel_id, data_dir)
        return []
