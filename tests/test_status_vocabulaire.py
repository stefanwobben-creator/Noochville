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

def test_de_poort_leidt_af_en_typt_niet_over():
    """DE KERNTEST OP DE BUG. `LEVEND` moet `draft` en `proposed` bevatten en mag geen enkele
    verzonnen waarde meer dragen."""
    from nooch_village import tensie_poort as tp
    assert tp.LEVEND == P.LEVEND
    assert "draft" in tp.LEVEND and "proposed" in tp.LEVEND
    for spook in ("review", "todo", "active"):
        assert spook not in tp.LEVEND, f"{spook!r} is geen projectstatus"
    # `cancelled`/`archived` zijn tensie-uitkomsten, geen projectstatussen; die mogen wél extra zijn.
    assert P.KLAAR <= tp.KLAAR


def test_het_bord_gebruikt_alleen_bestaande_statussen():
    from nooch_village.views.projects import _PROJ_COLS, _PROJ_CHIP, _ACTIEF_STATUSSEN
    uit_kolommen = {s for _lbl, _key, statussen in _PROJ_COLS for s in statussen}
    assert uit_kolommen <= set(P.STATUSSEN), "een kolom noemt een status die niet bestaat"
    assert set(_ACTIEF_STATUSSEN) == set(P.LOPEND), "de Active-kolom is precies LOPEND"
    assert set(_PROJ_CHIP) == set(P.STATUSSEN), "elke status hoort een chip te hebben"


def test_elke_status_heeft_een_teken_op_de_commandoregel():
    """`future`, `draft` en `proposed` misten en werden een '?'. Een vraagteken op een lijst die je
    gebruikt om te beslissen is erger dan geen lijst."""
    from nooch_village.projects_cli import _STATUS_ICON, _status_icon
    assert set(_STATUS_ICON) == set(P.STATUSSEN)
    for s in P.STATUSSEN:
        assert _status_icon(s) != "?", f"status {s!r} heeft geen teken"


def test_elke_status_heeft_een_label_op_het_metrics_scherm():
    """`proposed` miste, dus daar stond de rauwe sleutel."""
    from nooch_village.views.metrics import _PROJ_STATUS_LABEL
    assert set(_PROJ_STATUS_LABEL) == set(P.STATUSSEN)


# ── 3. Niemand somt ze nog zelf op ───────────────────────────────────────────

#: Waar een statuslijst LEGITIEM letterlijk staat: de bron zelf, en de plek die de bordkolommen
#: definieert (dat is een indelings-BESLUIT, geen statusfeit — de test hierboven eist wel dat elke
#: genoemde waarde bestaat).
_MAG_OPSOMMEN = {"projects.py", "views/projects.py", "systeemtaal.py"}

_KERN = {"queued", "running", "blocked"}


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

def test_de_inbox_chip_kent_alle_vier_de_notificatie_toestanden():
    """`NotifStore.status_of` geeft vier waarden; `views/inbox._STATUS` kende er drie, dus een
    AFGEHANDELDE spanning kreeg de groene 'nieuw'-chip. Zelfde vorm als de projectstatussen: een
    vocabulaire dat op twee plekken leeft en waarvan de ene helft een waarde mist."""
    from nooch_village.views.inbox import _STATUS
    from nooch_village.notifications import NotifStore
    toestanden = {
        NotifStore.status_of({}),                      # nieuw
        NotifStore.status_of({"read": True}),          # gelezen
        NotifStore.status_of({"processed": True}),     # verwerkt
        NotifStore.status_of({"done": True}),          # klaar
    }
    ontbreekt = toestanden - set(_STATUS)
    assert not ontbreekt, f"_STATUS mist {sorted(ontbreekt)} — die vallen terug op de 'nieuw'-chip"
