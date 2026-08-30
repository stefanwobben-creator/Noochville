"""De cap hoort op één plek, en dat is niet bij de aanroeper.

#389 haalde de harde `[:160]` uit `NotifStore.add` en verving hem door twee velden met één
waarheid: `tekst` volledig, `snippet` afgeleid. Maar VIJF aanroepers droegen hun eigen kopie van die
cap en kapten dus nog steeds af vóór de store hem ooit zag:

    inhabitant.py      _notify_founder      ← het HOOFDKANAAL van de daemon naar de founder
    human_inbox.py     founder-melding
    skills_impl/escaleer.py
    cockpit2.py        route_werk           ← elke actie uit inbox, wizard en werkoverleg
    cockpit2.py        meld_opdrachtgever

Dat is dezelfde fout als de bug zelf, één laag hoger: één feit (hoe lang mag dit zijn) op zes
plekken. De reparatie in de store werkte, en werd door de aanroepers meteen ongedaan gemaakt.

DEZE RATCHET TELT DE VORM, niet de plek — zoals de conventie-ratchet dat na #375 doet. Een nieuwe
aanroeper die zijn eigen cap meebrengt valt op, ook als hij ergens anders staat.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

# `snippet=<iets>[:<n>]` — een cap op de HELE snippet bij de aanroeper.
#
# ONDERSCHEID DAT ERTOE DOET: `f"{kop} op '{ander[:70]}'"` kapt een AANGEHAALD fragment af binnen
# een groter bericht. Dat is geen cap op de eigen tekst maar een citaat, en dat hoort kort. Een
# ratchet die daar op afgaat wordt genegeerd — dus: een `[:n]` die direct gevolgd wordt door `}`
# zit in een f-string-interpolatie en telt niet mee.
_SNIPPET = re.compile(r"snippet\s*=")
_CAP = re.compile(r"\[:\s*\d+\s*\](.?)")


def _treffers() -> list[str]:
    uit = []
    for f in sorted(ROOT.rglob("*.py")):
        for n, regel in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = _SNIPPET.search(regel)
            if not m:
                continue
            for cap in _CAP.finditer(regel, m.end()):
                if cap.group(1) != "}":                  # geen citaat-in-een-f-string
                    uit.append(f"{f.relative_to(ROOT)}:{n}: {regel.strip()[:100]}")
                    break
    return uit


def test_geen_enkele_aanroeper_kapt_zelf_af():
    treffers = _treffers()
    assert treffers == [], (
        "een aanroeper kapt de snippet zelf af. De store bewaart sinds #389 de VOLLEDIGE tekst en "
        "leidt de preview af; hier nog eens kappen maakt die reparatie ongedaan en het origineel is "
        "dan weg. Geef de hele tekst mee.\n" + "\n".join(treffers))


def test_een_citaat_in_een_bericht_mag_wel():
    """Onderscheid dat ertoe doet: `f\"{kop} op '{ander[:70]}'\"` kapt een AANGEHAALD fragment af
    binnen een groter bericht. Dat is geen cap op de eigen tekst maar een citaat, en dat hoort kort.
    De ratchet mag daar niet op afgaan, anders wordt hij genegeerd."""
    regel = """st.notif.add("role", o, p, by=n, snippet=(f"{kop} op '{(n.get('snippet') or '')[:70]}'"))"""
    m = _SNIPPET.search(regel)
    caps = [c for c in _CAP.finditer(regel, m.end()) if c.group(1) != "}"]
    assert caps == [], "de ratchet gaat af op een citaat, en dan wordt hij genegeerd"


def test_de_store_is_en_blijft_de_enige_plek():
    from nooch_village.notifications import PREVIEW_MAX, preview
    assert preview("x" * 500) != "x" * 500
    assert len(preview("x" * 500)) <= PREVIEW_MAX


def test_het_founderkanaal_bewaart_nu_de_volle_tekst(tmp_path):
    """Het pad waar het het meest kostte: de daemon die de founder iets meldt."""
    from nooch_village.notifications import NotifStore
    lang = ("De dagpuls draaide gisteren niet en harry_hemp gaf geen teken van leven, "
            "waarschijnlijk draait zijn service niet meer; kun je kijken of hij nog loopt? " * 2)
    st = NotifStore(str(tmp_path / "n.json"))
    n = st.add("role", "founder", "", by="rol", snippet=lang)
    assert n["tekst"] == lang and len(n["tekst"]) > 200
