"""Eenmalige correctie van ÉÉN wiki-pagina: NOTE-STRATE-001, "How we decide here".

WAAROM DIT BESTAAT. De pagina is op 18 september 2026 gezaaid uit
`content/how_we_decide_en.md`. Die tekst opent met een `# `-kop en bevat een `---`-streep, maar de
wiki-renderer (`cockpit2_util._md`) kent alleen `## `-koppen en `- `-lijsten. Beide komen er
LETTERLIJK doorheen, dus op de live pagina staat een zichtbare `# How we decide here` boven de
tekst en een regel met drie streepjes eronder. Dat is nooit gerenderd bekeken vóór het zaaien.

WAAROM HET GEEN WIJZIGING IN `wiki_zaad` IS. `wiki_seed.zaai` overschrijft bewust nooit: een pagina
met dezelfde titel bij dezelfde eigenaar wordt overgeslagen, zodat wat de eigenaar zelf heeft
aangepast blijft staan. Die regel is goed en blijft staan. Het bronbestand repareren doet dus niets
aan de al bestaande pagina — dat is precies waarom deze losse, expliciete actie nodig is. Eén
pagina, één keer, met de hand aangezet.

DRIE FAIL-CLOSED CONTROLES, want dit overschrijft tekst die een mens kan hebben aangeraakt:
  1. De pagina bestaat, is een note, heet "How we decide here" en hangt aan de verwachte rol.
  2. De live tekst heeft het gebrek nog (een kale `# `-regel of een `---`-regel). Zo niet, dan is
     er niets te corrigeren en stopt het script.
  3. De WOORDEN van de live tekst zijn identiek aan die van de nieuwe tekst, op de weggevallen
     titelregel na. Wijkt er één woord af, dan heeft iemand de pagina inhoudelijk bewerkt en
     stopt het script — dan is dit een gesprek, geen script.

De schrijfactie loopt via `AttachmentStore.update`, dus er komt een versie-entry bij met een
change_note: de correctie is terug te lezen in de historie van de pagina, en terug te draaien.

Gebruik (op de server, want daar staat de pagina):
    ./venv/bin/python scripts/herstel_note_strate_001.py
    ./venv/bin/python scripts/herstel_note_strate_001.py --doen

Zonder `--doen` is het een droogloop: hij toont de diff en raakt niets aan.
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nooch_village import wiki, wiki_how_we_decide as hwd     # noqa: E402
from nooch_village.cockpit2 import _Stores                     # noqa: E402
from nooch_village.config import load_context                  # noqa: E402
from nooch_village.village import BASE_DIR                     # noqa: E402

PAGINA_ID = "NOTE-STRATE-001"


def _woorden(t: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", t or "")


def _stop(reden: str) -> None:
    print(f"✗ {reden}")
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doen", action="store_true", help="schrijf de correctie weg")
    ap.add_argument("--id", default=PAGINA_ID, help=f"pagina-id (default {PAGINA_ID})")
    args = ap.parse_args()

    ctx = load_context(BASE_DIR)
    st = _Stores(ctx.data_dir)

    a = st.att.get(args.id)
    if a is None:
        _stop(f"{args.id} bestaat niet in deze dataset")
    if a.kind != wiki.PAGINA_KIND:
        _stop(f"{args.id} is geen wiki-pagina maar kind={a.kind!r}")
    if (a.title or "").strip() != hwd.TITEL:
        _stop(f"{args.id} heet {a.title!r}, verwacht {hwd.TITEL!r}")
    if a.anchor != hwd.EIGENAAR:
        _stop(f"{args.id} hangt aan {a.anchor!r}, verwacht {hwd.EIGENAAR!r}")

    oud = a.body or ""
    regels = [r.strip() for r in oud.split("\n")]
    if not any(r.startswith("# ") for r in regels) and "---" not in regels:
        _stop(f"{args.id} heeft het gebrek niet (geen kale '# '-regel, geen '---'-regel) — "
              f"niets te corrigeren")

    nieuw = hwd.tekst(BASE_DIR)
    weg = [w for w in _woorden(oud) if w not in _woorden(nieuw)]
    if _woorden(oud) != _woorden("How we decide here " + nieuw):
        print(f"✗ de woorden van de live tekst wijken af van {hwd.BRONBESTAND}.")
        print(f"  Dit script corrigeert alleen OPMAAK. Verschil in woorden betekent dat iemand de")
        print(f"  pagina heeft bewerkt; die bewerking mag niet stilzwijgend verdwijnen.")
        if weg:
            print(f"  woorden die alleen live staan: {weg[:15]}")
        sys.exit(1)

    print(f"pagina : {args.id} · {a.title} · eigenaar {a.anchor}")
    print(f"versies: {len(getattr(a, 'versions', []) or [])}")
    print()
    for regel in difflib.unified_diff(oud.split("\n"), nieuw.split("\n"),
                                      fromfile=f"{args.id} (live)",
                                      tofile=hwd.BRONBESTAND, lineterm=""):
        print(regel)
    print()

    if not args.doen:
        print("DROOGLOOP — er is niets geschreven. Draai opnieuw met --doen.")
        return

    uit = st.att.update(args.id, body=nieuw, actor_id="system", actor_type="person",
                        governance_ref=f"role:{a.anchor}",
                        change_note="opmaak-correctie: '# '-kop en '---' weg, lijst als '- ' "
                                    "(de wiki-renderer kent alleen ## en -)")
    if uit is None:
        _stop("de store weigerde de update")
    print(f"✓ geschreven · versie {len(uit.versions)} · {wiki.pagina_url(args.id)}")


if __name__ == "__main__":
    main()
