"""De projectstatussen leven op ÉÉN plek, en elke lezer leidt af.

WAAROM DEZE TEST BESTAAT. Vóór 8 september somden elf plekken zelfstandig op wat een projectstatus
is, en ze waren het onderling niet eens. Twee gevolgen waren geen stijlkwestie:

  - `tensie_poort.LEVEND` bevatte `review`, `todo` en `active` (die niet bestaan) en MISTE `draft`
    en `proposed`. Een spanning die aan zo'n project hing viel door `geborgd()` heen, werd
    behandeld alsof er geen project bij hoorde, en kwam bij de founder terecht. Dat is de vorm van
    de notificatiestapel die al twee keer met de hand is weggeveegd.
  - `views/metrics._PROJ_STATUS_LABEL` miste `proposed`, dus daar viel de rauwe sleutel op het
    scherm. Al live, al groen.

En het woord `"active"` in die eerste lijst is exact het woord waarop de projectbadge op 7
september strandde. Dezelfde geraden waarde, dezelfde rol, een ander bestand.

DE TESTEN HIERONDER TOETSEN DE INVARIANT, NIET DE INHOUD. Ze schrijven nergens een statuslijst uit
(dat was juist de fout), maar eisen dat elke lezer een deelverzameling van `projects.STATUSSEN`
gebruikt en dat de sets sluitend zijn. Een achtste status valt dan luid om op de plek die hem mist,
in plaats van stil als "?" of als rauwe sleutel op het scherm te verschijnen.
"""

# WAT HIER WEG IS (B2, 20 september 2026): 1 test(s) over het inbox-scherm. `/inbox`,
# `/inbox/verwerk`, de lade en `NotifStore` bestaan niet meer — de wachtrij is een
# DM-stroom geworden. Verwijderd omdat hun onderwerp weg is, niet omdat ze faalden.

from __future__ import annotations

import ast
import os

from nooch_village import projects as P


# ── 1. De bron zelf is sluitend ──────────────────────────────────────────────

def test_levend_en_klaar_dekken_samen_alle_statussen():
    """Zonder deze eis kan een nieuwe status tussen wal en schip vallen: niet levend, niet klaar,
    en dus door elke poort heen."""
    assert P.LEVEND | P.KLAAR == set(P.STATUSSEN)
    assert not (P.LEVEND & P.KLAAR), "een status kan niet tegelijk levend en klaar zijn"


def test_de_afgeleide_sets_bevatten_alleen_echte_statussen():
    for naam in ("START_STATUSSEN", "LOPEND", "OP_HET_BORD", "INGEPLAND"):
        waarden = set(getattr(P, naam))
        onbekend = waarden - set(P.STATUSSEN)
        assert not onbekend, f"{naam} noemt statussen die niet bestaan: {sorted(onbekend)}"


def test_de_sets_lopen_van_smal_naar_breed():
    """LOPEND ⊂ OP_HET_BORD ⊂ INGEPLAND ⊂ LEVEND. Als die keten breekt, betekent een van de namen
    iets anders dan hij zegt."""
    assert set(P.LOPEND) < set(P.OP_HET_BORD) < set(P.INGEPLAND) <= P.LEVEND


def test_geen_enkele_status_is_verzonnen():
    """De statussen die `projects.py` ECHT schrijft, komen allemaal in STATUSSEN voor — en er staat
    niets in STATUSSEN dat nergens vandaan komt. Dit is de test die `LEVEND` had moeten hebben."""
    bron = open(P.__file__, encoding="utf-8").read()
    geschreven = set()
    for node in ast.walk(ast.parse(bron)):
        # p["status"] = "..."
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) \
                        and t.slice.value == "status":
                    geschreven.add(node.value.value)
    onbekend = geschreven - set(P.STATUSSEN)
    assert not onbekend, f"projects.py schrijft statussen die niet in STATUSSEN staan: {onbekend}"


# ── 2. Elke lezer leidt af ───────────────────────────────────────────────────

def test_niemand_typt_een_statuslijst_over():
    """DE KERNTEST OP DE BUG, nu project-breed in plaats van op één lezer.

    Hier stond de test op `tensie_poort.LEVEND` — de lijst die `review`, `todo` en `active` bevatte
    en `draft` en `proposed` miste. Die poort is op 20 september 2026 met de founder-inbox
    verdwenen, en daarmee de laatste overtyper. De INVARIANT overleeft hem: buiten `projects.py`
    schrijft niemand een statuslijst uit, hij leidt af. Zo valt een achtste status luid om op de
    plek die hem mist, in plaats van stil bij de eerstvolgende die hem overtypte.

    De drempel ligt op drie: twee statussen naast elkaar is een concrete vergelijking ("queued of
    running"), drie of meer is een LIJST — en een lijst hoort één bron te hebben."""
    import pathlib
    wortel = pathlib.Path(P.__file__).parent
    statussen = set(P.STATUSSEN)
    overtreders = []
    for f in sorted(wortel.rglob("*.py")):
        if f.name == "projects.py":
            continue                                   # de bron mag het als enige uitschrijven
        boom = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(boom):
            # Een DICT met statussen als sleutel is iets anders: dat is een label- of vormkaart,
            # en zijn risico is niet overtypen maar INCOMPLEET zijn (`_PROJ_STATUS_LABEL` miste
            # `proposed` en zette de rauwe sleutel op het scherm). Dat bewaakt de test hieronder.
            if not isinstance(node, (ast.Set, ast.Tuple, ast.List)):
                continue
            woorden = {n.value for n in node.elts
                       if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            if len(woorden & statussen) >= 3:
                overtreders.append(f"{f.relative_to(wortel.parent)}:{node.lineno} "
                                   f"{sorted(woorden & statussen)}")
    assert not overtreders, (
        "deze plek(ken) typen een statuslijst over in plaats van hem uit `projects` af te leiden:\n"
        + "\n".join(overtreders))


def test_de_statuskaart_dekt_elke_status():
    """De andere helft van dezelfde bug: `views/metrics._PROJ_STATUS_LABEL` miste `proposed`, dus
    viel de rauwe sleutel op het scherm. Een kaart die op status sleutelt hoort compleet te zijn —
    anders leest een gebruiker 'proposed' waar 'Proposed' hoort te staan."""
    from nooch_village.web_base import _STATUS_VORM
    mist = set(P.STATUSSEN) - set(_STATUS_VORM)
    assert not mist, f"_STATUS_VORM mist {sorted(mist)} — die status valt rauw op het scherm"


def test_het_bord_gebruikt_alleen_bestaande_statussen():
    from nooch_village.views.projects import _PROJ_COLS, _PROJ_CHIP, _ACTIEF_STATUSSEN
    uit_kolommen = {s for _lbl, _key, statussen in _PROJ_COLS for s in statussen}
    assert uit_kolommen <= set(P.STATUSSEN), "een kolom noemt een status die niet bestaat"
    assert set(_ACTIEF_STATUSSEN) == set(P.LOPEND), "de Active-kolom is precies LOPEND"
    assert set(_PROJ_CHIP) == set(P.STATUSSEN), "elke status hoort een chip te hebben"




def test_elke_status_heeft_een_label_op_het_metrics_scherm():
    """`proposed` miste, dus daar stond de rauwe sleutel."""
    from nooch_village.views.metrics import _PROJ_STATUS_LABEL
    assert set(_PROJ_STATUS_LABEL) == set(P.STATUSSEN)


# ── 3. Niemand somt ze nog zelf op ───────────────────────────────────────────

#: Waar een statuslijst LEGITIEM letterlijk staat: de bron zelf, en de plek die de bordkolommen
#: definieert (dat is een indelings-BESLUIT, geen statusfeit — de test hierboven eist wel dat elke
#: genoemde waarde bestaat).
_MAG_OPSOMMEN = {"projects.py", "views/projects.py", "systeemtaal.py"}

_KERN = {"future", "running", "blocked"}


def test_geen_enkele_module_somt_de_statussen_nog_zelf_op():
    """De ratchet op de wortel van dit alles: een tuple/lijst/set met drie of meer projectstatussen
    erin is een tweede bron van waarheid. Leid af uit `projects.py`."""
    pkg = os.path.dirname(P.__file__)
    overtreders = []
    for wortel, _dirs, files in os.walk(pkg):
        for naam in files:
            if not naam.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(wortel, naam), pkg).replace(os.sep, "/")
            if rel in _MAG_OPSOMMEN:
                continue
            try:
                boom = ast.parse(open(os.path.join(wortel, naam), encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(boom):
                if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                    continue
                waarden = {e.value for e in node.elts
                           if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                if len(waarden & set(P.STATUSSEN)) >= 3 and len(waarden & _KERN) >= 2:
                    overtreders.append(f"{rel}:{node.lineno}")
    assert not overtreders, (
        "deze plekken sommen de projectstatussen zelf op: " + ", ".join(sorted(overtreders)) +
        ". Leid af uit projects.STATUSSEN / LEVEND / LOPEND / OP_HET_BORD / INGEPLAND.")


# ── 4. De inbox-status, dezelfde fout een laag hoger ─────────────────────────
