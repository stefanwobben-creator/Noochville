"""De embedding-indexen opschonen: weg met sleutels die nooit meer een treffer kunnen geven.

AANLEIDING (29 aug 2026). `kennis_context._rangschik` sleutelde op `str(id(o))` — het geheugenadres
van een Python-object. Dat adres verschilt per proces en per aanroep, dus de index kon per definitie
nooit raak zijn: élk item werd bij élke raadpleging opnieuw geëmbed en elke nieuwe afval-sleutel
bleef permanent staan. Op prod groeiden de twee indexen daardoor naar samen 476 MB, terwijl er 31
levende inzichten en 105 levende signalen zijn.

De sleutel is gerepareerd; deze module ruimt op wat de oude sleutel achterliet.

WAT ER WEGGAAT, en waarom precies dit. Een entry gaat weg als zijn sleutel GEEN levende id is in het
corpus dat bij deze index hoort. Dat is een grond, geen patroon: 'ziet eruit als een adres' zou een
echte id die toevallig uit cijfers bestaat kunnen meenemen. Beide getallen worden apart gerapporteerd,
zodat zichtbaar blijft wat er precies opgeruimd is.

WAT ER NOOIT WEGGAAT. Een entry waarvan de id wél leeft blijft staan, ook als zijn tekst intussen
veranderde — dan zorgt de hash-vergelijking in `vectors_for` zelf voor een verse vector. Opruimen is
hier goedkoop maar niet gratis: een onterecht verwijderde vector kost een embed-call, en die calls
zijn juist het schaarse goed.

DROGE LOOP IS DE DEFAULT. `--apply` schrijft pas echt, en dan onder het bestandsslot met een verse
store — er kan een tweede schrijver zijn (een render naast de bulk-vuller).
"""
from __future__ import annotations

import json
import logging
import os
import re

log = logging.getLogger("village.embed_opruimen")

# Een sleutel die puur uit ≥9 cijfers bestaat is een CPython-geheugenadres. Alleen voor de
# rapportage: het opruimen zelf gaat op levende ids, niet op dit patroon.
_ADRES = re.compile(r"^\d{9,}$")


def levende_ids(data_dir: str, index: str) -> set[str]:
    """De ids die deze index legitiem mag bevatten, uit de stores die hem vullen.

    Fail-closed: kunnen we het corpus niet lezen, dan geven we `set()` terug en weigert `opruimen`
    iets te verwijderen — een lege verzameling betekent hier 'ik weet het niet', en op grond van niet
    weten hoor je geen 476 MB weg te gooien."""
    uit: set[str] = set()
    try:
        if index == "kennisbank_embeddings.json":
            from nooch_village.kennisbank import KennisbankStore
            pad = os.path.join(data_dir, "kennisbank.json")
            if not os.path.exists(pad):
                return set()
            uit = {str(i.get("id") or "") for i in KennisbankStore(pad).all()}
        elif index == "radar_embeddings.json":
            # Twee gebruikers, één index: `radar_clusters` indexeert ALLE radar-items, `_signalen`
            # de goedgekeurde. De ruimste verzameling wint, anders gooien we het werk van de ander weg.
            from nooch_village.radar_store import RadarStore
            pad = os.path.join(data_dir, "radar.json")
            if not os.path.exists(pad):
                return set()
            uit = {str(it.get("id") or "") for it in RadarStore(pad).all_items()}
        else:
            return set()
    except Exception as e:                                # noqa: BLE001
        log.warning("corpus voor %s onleesbaar (%s) — niets opruimen", index, e)
        return set()
    return {i for i in uit if i}


def opruimen(data_dir: str, index: str, *, apply: bool = False) -> dict:
    """Ruim één index op. Geeft altijd een verslag terug; schrijft alleen bij `apply=True`."""
    pad = os.path.join(data_dir, index)
    verslag = {"index": index, "bestond": os.path.exists(pad), "mb_voor": 0.0, "mb_na": 0.0,
               "entries_voor": 0, "entries_na": 0, "weg": 0, "adres_achtig": 0,
               "levend": 0, "toegepast": bool(apply), "reden": ""}
    if not verslag["bestond"]:
        verslag["reden"] = "index bestaat niet"
        return verslag
    verslag["mb_voor"] = round(os.path.getsize(pad) / 1e6, 1)

    from nooch_village.kennis_embeddings import EmbeddingStore
    st = EmbeddingStore(pad)
    sleutels = [k for k, _ in st.items()]
    verslag["entries_voor"] = len(sleutels)
    verslag["adres_achtig"] = sum(1 for k in sleutels if _ADRES.match(str(k)))

    levend = levende_ids(data_dir, index)
    verslag["levend"] = len(levend)
    if not levend:
        verslag["entries_na"] = verslag["entries_voor"]
        verslag["mb_na"] = verslag["mb_voor"]
        verslag["reden"] = "geen levende ids gevonden — fail-closed, niets verwijderd"
        return verslag

    weg = [k for k in sleutels if str(k) not in levend]
    verslag["weg"] = len(weg)
    verslag["entries_na"] = verslag["entries_voor"] - len(weg)
    if not apply or not weg:
        verslag["mb_na"] = verslag["mb_voor"] if not weg else 0.0
        verslag["reden"] = "droge loop" if weg else "niets op te ruimen"
        return verslag

    from nooch_village.util import file_lock
    with file_lock(pad):
        vers = EmbeddingStore(pad)                        # verse store ONDER het slot
        for k in [k for k, _ in vers.items() if str(k) not in levend]:
            vers.drop(k)
        vers.save()
        verslag["entries_na"] = len(vers)
    verslag["mb_na"] = round(os.path.getsize(pad) / 1e6, 1)
    verslag["reden"] = "opgeruimd"
    return verslag


def rapport(data_dir: str, *, apply: bool = False) -> list[dict]:
    """Beide indexen, met een leesbare regel per index."""
    from nooch_village.kennis_context import INDEX_INZICHTEN, INDEX_SIGNALEN
    uit = []
    for index in (INDEX_INZICHTEN, INDEX_SIGNALEN):
        v = opruimen(data_dir, index, apply=apply)
        uit.append(v)
        print(f"{v['index']}")
        print(f"   {v['mb_voor']:8.1f} MB → {v['mb_na']:8.1f} MB" if v["toegepast"] and v["weg"]
              else f"   {v['mb_voor']:8.1f} MB")
        print(f"   entries {v['entries_voor']} → {v['entries_na']}   "
              f"(weg: {v['weg']}, waarvan adres-achtig {v['adres_achtig']})")
        print(f"   levende ids in het corpus: {v['levend']}   [{v['reden']}]")
    return uit
