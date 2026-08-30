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
