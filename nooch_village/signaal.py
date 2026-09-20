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
  3. doel is een ROL zonder mens-vervuller          → de terugval (de founder)
  4. doel is een ROL met MEER DAN ÉÉN vervuller     → niemand; de aanroeper beslist wat hij doet

Geval 4 is geen fout maar een grens. Bij de migratie betekent het "parkeren en melden"; bij een
nieuwe melding betekent het "naar alle vervullers", want daar is een dubbel bericht minder erg dan
een bericht dat niemand krijgt. Dat verschil staat hier expliciet omdat het een keuze is.
"""
from __future__ import annotations

from nooch_village import channels

#: Wie de meldingen krijgt van een rol die niemand meer vervult.
TERUGVAL_ROL = "mother_earth__nooch__strategic_lead_founder_steward"

NAAR_PERSOON, NAAR_VERVULLER, NAAR_TERUGVAL, MEERDERE, ONBEKEND = (
    "persoon", "vervuller", "terugval", "meerdere-vervullers", "onbekend-doel")


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
    mensen = mensen_van(st, TERUGVAL_ROL)
    return mensen[0] if len(mensen) == 1 else ""


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
    terug = terugval(st)
    return ([terug], NAAR_TERUGVAL) if terug else ([], ONBEKEND)


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
