"""Elke store die zijn eigen bestand schrijft, schrijft door het slot.

WAAROM DEZE TEST NAAST `test_geen_ongelockte_write.py`. Die telt hoe vaak `atomic_write_json`
buiten `util.py` wordt aangeroepen. Dat is een goede ratchet, maar hij telt de NETTE overtreding.
`notes_store.py` schreef zijn hele bestand met `open(path,"w")` plus een kale json-dump: geen slot
en geen atomic replace, vanaf zeventien plekken, en door twee processen tegelijk. Precies het
bestand met de zwakste bescherming was het enige dat de ratchet niet zag.

De regex verbreden loste dat niet op: dan telt hij ook elke json-dump die niets met een store te
maken heeft (een rapport, een export, een tijdelijk bestand), en dan vult de whitelist zich met
uitzonderingen zonder betekenis. Een guard die te veel vangt wordt net zo snel genegeerd als een
guard die te weinig vangt.

Dus toetst deze test de INVARIANT in plaats van de vorm: een klasse die naar `self.path` (of
`self._path`) schrijft, hoort dat via het gedeelde bestandsslot te doen. Dat kan op twee manieren,
en beide zijn goed:

  1. erven van `util.JsonStore` en `_WRITE_METHODS` declareren (de gewone weg, 25 stores);
  2. `_WRITE_METHODS` declareren en `synchronized` er zelf op zetten — voor een store die geen
     json-document is, zoals `ObservationStore` (jsonl met een append-pad).

Een klasse die schrijft zonder een van beide staat in `_BEWUST_ZONDER_SLOT`, mét reden. Dat is de
vorm van `test_geen_ongelockte_write.test_whitelist_is_actueel_en_heeft_redenen`: een uitzondering
mag, maar hij moet uitgeschreven staan en hij moet nog waar zijn.
"""
from __future__ import annotations

import ast
import glob
import os

_PKG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village")

#: klassenaam → reden. Alleen voor een store die BEWUST zonder slot schrijft.
_BEWUST_ZONDER_SLOT = {
    "EvidenceLedger": "append-only kroniek; neemt file_lock expliciet met de hand rond de append",
    "NominationKroniek": "append-only kroniek; neemt file_lock expliciet met de hand",
    "SkillLinkKroniek": "append-only kroniek; neemt file_lock expliciet met de hand",
}

_SCHRIJF_MODI = ("w", "a", "w+", "a+", "wb", "ab")


def _schrijft_naar_zichzelf(kl: ast.ClassDef) -> bool:
    """Schrijft deze klasse KAAL naar zijn eigen pad? Alleen `open(self.path, "w"/"a")`.

    Bewust NIET `atomic_write_json`: dat is het domein van `test_geen_ongelockte_write.py`, met een
    eigen whitelist. Twee guards die hetzelfde tellen leveren twee lijsten die uiteenlopen, en dan
    weet niemand meer welke de waarheid is. Deze guard dekt precies het gat dat die ander niet zag:
    schrijven zonder atomic replace."""
    for node in ast.walk(kl):
        if not isinstance(node, ast.Call):
            continue
        # open(self.path, "w"/"a") of open(self._path, ...)
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                    and node.args[1].value in _SCHRIJF_MODI:
                doel = node.args[0]
                if isinstance(doel, ast.Attribute) and isinstance(doel.value, ast.Name) \
                        and doel.value.id == "self" and doel.attr in ("path", "_path"):
                    return True
    return False


def _erft_jsonstore(kl: ast.ClassDef) -> bool:
    return any((isinstance(b, ast.Name) and b.id == "JsonStore")
               or (isinstance(b, ast.Attribute) and b.attr == "JsonStore") for b in kl.bases)


def _declareert_write_methods(kl: ast.ClassDef) -> bool:
    for stmt in kl.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "_WRITE_METHODS":
                    return True
    return False


def _klassen():
    for pad in sorted(glob.glob(os.path.join(_PKG, "**", "*.py"), recursive=True)):
        try:
            boom = ast.parse(open(pad, encoding="utf-8").read())
        except SyntaxError:                 # PEP 701-f-strings onder een oudere parser
            continue
        for node in ast.walk(boom):
            if isinstance(node, ast.ClassDef):
                yield os.path.relpath(pad, _PKG).replace(os.sep, "/"), node


def test_elke_schrijvende_store_gaat_door_het_slot():
    """DE KERNTEST. `notes_store.NotesStore` zakte hier vóór 8 september doorheen: hij schreef met
    een kale open-plus-dump, erfde niets, en declareerde niets."""
    zonder = []
    for rel, kl in _klassen():
        if not _schrijft_naar_zichzelf(kl):
            continue
        if _erft_jsonstore(kl) or _declareert_write_methods(kl):
            continue
        if kl.name in _BEWUST_ZONDER_SLOT:
            continue
        zonder.append(f"{rel}::{kl.name}")
    assert not zonder, (
        "deze klassen schrijven naar hun eigen pad zonder slot: " + ", ".join(sorted(zonder)) +
        ". Erf van util.JsonStore en declareer _WRITE_METHODS, of zet synchronized er zelf op "
        "(zoals ObservationStore). Bewuste uitzondering? Zet 'm in _BEWUST_ZONDER_SLOT mét reden.")


def test_de_uitzonderingen_bestaan_nog_en_hebben_een_reden():
    """Zelfde aanscherping als bij de andere ratchet: een uitzondering die niet meer bestaat houdt
    de guard slap, en een reden die verjaart is erger dan geen reden."""
    namen = {kl.name for _rel, kl in _klassen()}
    for naam, reden in _BEWUST_ZONDER_SLOT.items():
        assert reden.strip(), f"{naam}: uitzondering zonder reden"
        assert naam in namen, f"{naam}: staat in _BEWUST_ZONDER_SLOT maar bestaat niet meer"


def test_de_vijf_gemigreerde_stores_staan_onder_het_slot():
    """De vijf uit ronde A, expliciet. Zonder deze test zou een latere refactor ze stil kunnen
    terugzetten naar een eigen `_save` zonder dat de bovenstaande test het per se opmerkt."""
    from nooch_village.governance import Records
    from nooch_village.library import Library
    from nooch_village.source_status import SourceStatusStore
    from nooch_village.notes_store import NotesStore
    from nooch_village.observations import ObservationStore
    from nooch_village.util import JsonStore

    for kl in (Records, Library, SourceStatusStore, NotesStore):
        assert issubclass(kl, JsonStore), f"{kl.__name__} hoort van JsonStore te erven"
        assert kl._WRITE_METHODS, f"{kl.__name__} declareert geen schrijfmethoden"

    # ObservationStore is bewust GEEN JsonStore (jsonl), maar zijn schrijvers zijn wel gewrapt.
    assert not issubclass(ObservationStore, JsonStore)
    assert ObservationStore._WRITE_METHODS
    for naam in ObservationStore._WRITE_METHODS:
        meth = getattr(ObservationStore, naam)
        assert getattr(meth, "__wrapped__", None) is not None, (
            f"ObservationStore.{naam} is niet door synchronized gewrapt")
