"""De poort zit in de KLASSE, niet op een instantie.

WAT ER MIS WAS. `NotifStore` had een instantie-haak (`set_verrijker`). Zeven plekken in het dorp
bouwen hun eigen store, en de haak werd op twéé gezet — beide in de web-laag. Dus:

    cockpit2 (web)              haak  ✔
    inhabitant  _notify_founder  ✘   ← het hoofdkanaal van de daemon naar de founder
    human_inbox                  ✘
    puls_wacht  (het alarm)      ✘   ← precies het ijkpunt-bericht dat leesbaar moest worden
    roles       _notify_role     ✘
    claims_board                 ✘
    skills_impl/escaleer         ✘

Een poort die je per instantie moet aanzetten is geen poort maar een suggestie, en de achtste store
ontsnapt sowieso. Hij zit nu in `add()` — de klasse-methode die álle schrijvers aanroepen — zodat
elke instantie hem structureel draagt.

DEZE RATCHET BEVRIEST BEIDE KANTEN: het aantal plekken dat een store bouwt (elke nieuwe is een
besluit), en dat de handhaving in de klasse blijft zitten.
"""
from __future__ import annotations

import inspect
import pathlib
import re

from nooch_village import notifications as nm

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

# Elke plek die zelf een NotifStore bouwt. Eentje erbij mag — maar dan bewust, en met de wetenschap
# dat hij de poort automatisch meekrijgt. Zakt het aantal, verlaag dit dan.
STORE_PLEKKEN = 7


def _bouwers() -> list[str]:
    uit = []
    for f in sorted(ROOT.rglob("*.py")):
        if f.name == "notifications.py":
            continue                                     # de klasse zelf
        for n, regel in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bNotifStore\(", regel) and "import" not in regel:
                uit.append(f"{f.relative_to(ROOT)}:{n}")
    return uit


def test_het_aantal_store_bouwers_staat_vast():
    bouwers = _bouwers()
    assert len(bouwers) == STORE_PLEKKEN, (
        f"{len(bouwers)} plekken bouwen een NotifStore (was {STORE_PLEKKEN}):\n  "
        + "\n  ".join(bouwers)
        + "\n\nDat mag — sinds de poort in `add()` zit krijgt elke nieuwe store hem automatisch. "
          "Pas dit getal aan mét een reden in de commit.")


def test_de_poort_zit_in_add_niet_op_een_instantie():
    """DE KERN. Zolang hij op een instantie hing, stond hij op 2 van de 7."""
    bron = inspect.getsource(nm.NotifStore.add)
    assert "_door_de_poort(" in bron, "de poort wordt niet vanuit add() aangeroepen"
    assert not hasattr(nm.NotifStore, "set_verrijker"), (
        "`set_verrijker` is terug: dan kan een schrijver de poort weer per instantie aan- of "
        "uitzetten, en dat was precies het gat.")


def test_niemand_zet_de_haak_nog_per_instantie():
    """`notifications.py` mag de naam noemen — daar staat in het commentaar WAAROM hij weg is, en
    dat is precies de uitleg die een volgende lezer nodig heeft. Elders is hij een regressie."""
    treffers = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*.py")
                if f.name != "notifications.py" and "set_verrijker" in f.read_text(encoding="utf-8")]
    assert treffers == [], f"instantie-haak terug in {treffers}"


# ── De poort filtert op de LEZER ───────────────────────────────────────────

def test_een_persoon_telt_als_mens_lezer(tmp_path):
    """17 notificaties gaan naar een persoon, en die vielen er vroeger buiten — juist de berichten
    die een mens direct leest."""
    from nooch_village.people import PeopleStore
    p = PeopleStore(str(tmp_path / "people.json")).add("Stefan", "s@n.nl")
    assert nm._is_mens_lezer({"target_type": "person", "target_id": p.id}, str(tmp_path)) is True
    assert nm._is_mens_lezer({"target_type": "person", "target_id": "bestaat-niet"},
                             str(tmp_path)) is False


def test_de_afzender_doet_er_niet_toe(tmp_path):
    """Het puls-wacht-alarm heeft `by='puls-wacht'` — geen rol, geen slaaptoestand. Vroeger viel het
    daarom buiten de boot; nu telt alleen wie het leest."""
    from nooch_village.people import PeopleStore
    p = PeopleStore(str(tmp_path / "people.json")).add("Stefan", "s@n.nl")
    for afzender in ("puls-wacht", "compliance", "", "een-rol-die-slaapt"):
        assert nm._is_mens_lezer({"target_type": "person", "target_id": p.id,
                                  "by": afzender}, str(tmp_path)) is True


def test_zonder_records_valt_de_poort_dicht_niet_om(tmp_path):
    """Fail-soft: kan de poort niet vaststellen wie leest, dan verrijkt hij niet — en blijft de
    rauwe notificatie gewoon staan. Een spanning die niet verrijkt kon worden is nog steeds een
    spanning."""
    assert nm._is_mens_lezer({"target_type": "role", "target_id": "x"}, str(tmp_path)) is False
    assert nm._door_de_poort({"target_type": "role", "target_id": "x"}, str(tmp_path)) == {}


def test_een_item_dat_zijn_type_al_kent_slaat_de_poort_over(tmp_path):
    """Een pagina-voorstel weet exact wat het vraagt; een dure call zou alleen een al bekend
    antwoord overschrijven."""
    geraakt = []
    st = nm.NotifStore(str(tmp_path / "n.json"),
                       verrijker=lambda n: geraakt.append(n) or {})
    st.add("role", "r", "", by="x", snippet="iets", extra={"type": "founder"})
    assert geraakt == []


def _herschrijft(n: dict, dd: str, mp=None) -> bool:
    """Wat de poort de verrijker meegeeft. TYPEREN en HERSCHRIJVEN zijn twee handelingen: de eerste
    zegt wát iets is en laat de tekst staan, de tweede vervángt de zin die de lezer ziet. Alleen de
    tweede raakt andermans woorden — en alleen die staat hier ter discussie."""
    import nooch_village.spanning_ontstaat as so
    gezien = {}

    def _nep(records, assignments, data_dir="", reason_fn=None, herschrijf=True):
        gezien["h"] = herschrijf
        return lambda x: {}
    echt = so.maak_verrijker
    so.maak_verrijker = _nep
    try:
        nm._door_de_poort(n, dd)
    finally:
        so.maak_verrijker = echt
    return gezien.get("h")


# ── Mensentaal blijft mensentaal ───────────────────────────────────────────

def test_wat_een_mens_typte_wordt_niet_herschreven(tmp_path):
    """PRINCIPE, GEEN VOLUME. De verleiding was om dit op het cijfer te gronden (5 van de 262, dus
    'het kost toch niks'). Maar dan draait het besluit om zodra dat cijfer groeit, en gaan we op een
    dag iemands eigen woorden herschrijven.

    De echte grond: een mens-getypt bericht ÍS al mensentaal — precies de eindvorm die deze laag
    nastreeft. Er valt niets te vertalen, en andermans woorden herschrijven is geen leesbaarheid
    maar inmenging.

    Zelfde discipline als bij het schrappen van 'Informatie': de grond was coherentie, en het
    gebruikscijfer was de bevestiging."""
    from nooch_village.people import PeopleStore
    p = PeopleStore(str(tmp_path / "people.json")).add("Stefan Wobben", "s@n.nl")
    dd = str(tmp_path)
    # op id én op naam — beide vormen komen in `by` voor
    assert nm._is_mens_schrijver({"by": p.id}, dd) is True
    assert nm._is_mens_schrijver({"by": "Stefan Wobben"}, dd) is True
    # en de poort geeft dat door aan de verrijker: typeren mag, herschrijven niet
    assert _herschrijft({"target_type": "person", "target_id": p.id, "by": p.id}, dd) is False


def test_een_machine_bericht_aan_een_mens_gaat_er_wel_doorheen(tmp_path):
    """De andere helft van de voorwaarde. `by='puls-wacht'` is een systeemcomponent."""
    from nooch_village.people import PeopleStore
    p = PeopleStore(str(tmp_path / "people.json")).add("Stefan", "s@n.nl")
    dd = str(tmp_path)
    for machine in ("puls-wacht", "compliance", "werkoverleg", "noochie"):
        assert nm._is_mens_schrijver({"by": machine}, dd) is False
    # en dan mag er wél herschreven worden — dit is precies de tekst waar de laag voor bestaat
    assert _herschrijft({"target_type": "person", "target_id": p.id, "by": "puls-wacht"}, dd) is True


def test_onbekende_afzender_telt_als_machine(tmp_path):
    """Fail-RICHTING, bewust gekozen: 'per ongeluk een machinebericht leesbaar maken' is een
    goedkope fout, 'per ongeluk iemands woorden herschrijven' niet."""
    assert nm._is_mens_schrijver({"by": "iets-onbekends"}, str(tmp_path)) is False
    assert nm._is_mens_schrijver({"by": ""}, str(tmp_path)) is False


def test_de_reden_staat_bij_de_code_niet_alleen_hier():
    """Een regel die alleen in een test staat vindt niemand terug — en deze moet juist overeind
    blijven als het volume verandert."""
    import inspect
    bron = inspect.getsource(nm._is_mens_schrijver)
    assert "PRINCIPE, GEEN VOLUMEKWESTIE" in bron
    assert "inmenging" in bron


def test_het_mention_pad_geeft_de_auteur_mee_niet_het_kanaal(tmp_path):
    """OP HET PRINCIPE GESTUIT. `_act_proj_feed` schreef `by="dialoog"` — een label voor de PLEK,
    niet voor de auteur. Daardoor kon de poort niet zien dat een mens deze woorden typte, en zou
    hij ze alsnog herschrijven. Een principe dat het record niet kan waarnemen, handhaaft niets."""
    import inspect

    from nooch_village import cockpit2
    bron = inspect.getsource(cockpit2._act_proj_feed)
    assert 'by="dialoog"' not in bron.split("Fail-soft")[-1], "het kanaal staat weer in `by`"
    assert "st.people.by_email(c.username)" in bron


# ── Het pad wint van de naam ───────────────────────────────────────────────

def test_een_mens_pad_zonder_naam_blijft_mens(tmp_path):
    """DE RAND DIE ANDERSOM MOEST. De harde regel is 'nooit andermans woorden herschrijven'. Als
    die alleen op auteur-HERKENNING hangt, valt hij om precies waar het pijn doet: een
    dialoog-comment van een uitgelogde gebruiker viel terug op `by="dialoog"`, en een eigen spanning
    in je eigen inbox draagt `by="zelf"` — allebei onmiskenbaar mens-getypt, allebei onherkenbaar,
    dus allebei herschreven.

    Het pad wist wél dat er een mens zat te typen. Dus zegt het record dat nu, en het pad wint van
    de naam. Alleen een écht niet-mens-pad is machine-tekst."""
    dd = str(tmp_path)
    for by in ("dialoog", "zelf", "", "The Source"):
        n = {"by": by, nm.MENS_GETYPT: True}
        assert nm._is_mens_schrijver(n, dd) is True, by


def test_het_merk_moet_er_echt_staan(tmp_path):
    """Geen 'truthy genoeg': alleen True telt. Een pad dat het veld half zet, is een pad dat het
    niet weet — en dan valt het terug op de goedkope fout."""
    dd = str(tmp_path)
    for waarde in (False, None, "ja", 1, 0):
        assert nm._is_mens_schrijver({"by": "dialoog", nm.MENS_GETYPT: waarde}, dd) is False, waarde


def test_de_typ_paden_merken_hun_eigen_tekst():
    """Het merk hoort bij het PAD, en een pad dat het vergeet is stil: dan wordt er alsnog
    herschreven en merkt niemand het. Deze vier zijn de plekken waar een mens letterlijk zit te
    typen en de tekst ongefilterd in een notificatie belandt."""
    import inspect

    from nooch_village import cockpit2
    for fn in (cockpit2._act_proj_feed, cockpit2._act_notif_add, cockpit2._act_notif_besluit):
        assert "MENS_GETYPT" in inspect.getsource(fn), fn.__name__


def test_het_dialoog_merk_hangt_aan_het_pad_niet_aan_de_persoon():
    """Specifiek: bij een mention is `atype == "human"` het bewijs, niet of we de persoon
    terugvinden. Anders herschrijven we juist de woorden van wie we níét kennen."""
    import inspect

    from nooch_village import cockpit2
    bron = inspect.getsource(cockpit2._act_proj_feed)
    assert 'if atype == "human" else {}' in bron


def test_typeren_gaat_door_ook_bij_een_mens_die_typte(tmp_path):
    """DE VONDST DIE EEN TEST DEED OMVALLEN. De poort stond vóór de verrijker, en die verrijker doet
    twee dingen tegelijk: typeren (wát is dit) én herschrijven (de zin die de lezer krijgt). 'Nooit
    andermans woorden herschrijven' zette daarmee stilzwijgend ook de ROUTERING uit — een
    handgevangen spanning kwam ongetypeerd bij de rol aan.

    Een principe dat een werkende stroom afknijpt is geen principe meer maar een storing. Dus knipt
    de poort de twee uit elkaar: typeren altijd (voor een mens-lezer), herschrijven alleen bij
    machinetekst."""
    import nooch_village.spanning_ontstaat as so
    bron = inspect.getsource(so.maak_verrijker)
    assert "herschrijf: bool = True" in bron
    assert "geen aanvulling" in bron            # het verschil staat bij de code
