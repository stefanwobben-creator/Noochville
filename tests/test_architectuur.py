"""Guard: docs/ARCHITECTUUR.md is AUTOMATISCH afgeleid en mag niet verouderen. Deze test regenereert
de vindkaart en vergelijkt met het gecommitte bestand — faalt zodra een nieuwe route/actie/store is
toegevoegd (of het bestand handmatig is bewerkt) zonder `python -m nooch_village.arch_map` + commit."""
from __future__ import annotations
import os
import re

from nooch_village import arch_map

_DOC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "ARCHITECTUUR.md")
_PKG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village")


def test_architectuur_md_is_actueel():
    generated = arch_map.render_markdown()
    committed = open(_DOC, encoding="utf-8").read()
    assert committed == generated, (
        "docs/ARCHITECTUUR.md is verouderd of handmatig bewerkt. "
        "Draai `python -m nooch_village.arch_map` en commit het resultaat.")


def test_tabellen_niet_leeg_en_kern_aanwezig():
    routes = dict((r, h) for r, h, _v in arch_map.routes())
    assert routes.get("/node") == "render_node" and routes.get("/kpi_new") == "render_kpi_composer"
    acties = dict(arch_map.dispatch_actions())
    assert "tile_add" in acties and "catalog_publish" in acties and len(acties) > 50
    stores = {c: (k, f) for c, k, f in arch_map.stores()}
    assert stores["observations"] == ("ObservationStore", "observations.jsonl")
    assert stores["metrics"][1] == "metrics.json"


def test_geen_twee_renderers_met_dezelfde_naam():
    """Twee `render_x` met dezelfde naam is een val met twee bekken.

    HET GEVAL (4 sep 2026, #444): `views/rapport.py` kreeg een `render_rapport` terwijl
    `views/claims.py` die naam al had. `cockpit2` importeert beide; de tweede import overschreef
    stil de eerste, dus de claims-aanroep `render_rapport(uitslag, markten=…)` riep de PROJECT-
    renderer aan met `uitslag` als `st`. De volle suite bleef groen — dat pad had geen test.

    En de architectuurkaart raakte er OS-afhankelijk van: `arch_map._render_def_index` doet
    `setdefault` over `os.walk`, dus bij een dubbele naam wint het bestand dat het bestandssysteem
    het eerst teruggeeft. Op APFS was dat de ene, op de Linux-runner de andere — groen bij mij,
    rood in CI. Deze test faalt op de oorzaak in plaats van op het symptoom.
    """
    import collections
    namen = collections.defaultdict(list)
    for base, dirs, files in os.walk(_PKG):
        dirs.sort()
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            full = os.path.join(base, fn)
            with open(full, encoding="utf-8") as fh:
                for ln in fh:
                    m = re.match(r"\s*def (render_\w+)\(", ln)
                    if m:
                        namen[m.group(1)].append(os.path.relpath(full, _PKG))
    dubbel = {n: sorted(set(f)) for n, f in namen.items() if len(set(f)) > 1}
    assert not dubbel, (
        f"renderer-namen in meer dan één bestand: {dubbel}. Geef ze een eigen naam — "
        f"cockpit2 importeert ze plat, dus de laatste import wint stil.")


# ── sectie (d): elk databestand is zichtbaar, of zichtbaar onbekend ──────────
#
# Sectie (c) dekte ongeveer de helft van de schrijvende opslag en dat stond er nergens bij: wie
# `data/decision_sheets.jsonl` vond, zocht in de kaart, vond niets, en kon concluderen dat het geen
# echte store was. Sectie (d) vult dat aan — maar een sectie (d) die 20 van de 27 toont is erger dan
# geen sectie (d), want dan gaat iemand hem vertrouwen. Vandaar deze twee guards.

def test_elk_gevonden_databestand_staat_ergens_in_de_kaart():
    """Geen bestand valt stilzwijgend weg: alles zit in (c), (d), (d2) of (d3) — precies één keer."""
    import os
    import re
    from nooch_village import arch_map

    gevonden = set()
    for f in os.listdir(os.path.dirname(arch_map.__file__)):
        if f.endswith(".py"):
            with open(os.path.join(os.path.dirname(arch_map.__file__), f), encoding="utf-8") as fh:
                gevonden |= set(arch_map._DATABESTAND_RE.findall(fh.read()))

    in_c = {b for _, _, b in arch_map.stores()}
    df = arch_map.data_files()
    in_d = [b for b, _ in df["eigenaar"]] + [b for b, _ in df["meerdere"]] + [b for (b,) in df["geen"]]

    ontbreekt = gevonden - in_c - set(in_d)
    assert not ontbreekt, (
        f"deze databestanden staan in geen enkele sectie van de vindkaart: {sorted(ontbreekt)}. "
        f"Vul sectie (d) aan of leg uit waarom ze er niet in horen — een kaart met een onzichtbaar "
        f"gat is erger dan geen kaart.")
    dubbel = [b for b in in_d if in_d.count(b) > 1] + sorted(set(in_d) & in_c)
    assert not dubbel, f"deze bestanden staan in meer dan één sectie: {sorted(set(dubbel))}"


def test_sectie_d_leidt_af_uit_schrijfgedrag_en_niet_uit_noemen():
    """De kern van de indeling: een module die een bestandsnaam alleen NOEMT is een lezer.

    `inhabitant.py` leest `human_inbox.json` en `evidence_ledger.jsonl` zonder er één te bezitten;
    zou de kaart op stringliterals werken, dan stond hij hier als eigenaar van allebei."""
    from nooch_village import arch_map

    df = arch_map.data_files()
    eigenaren = dict(df["eigenaar"])
    # decision_sheets.py schrijft met `open(pad(data_dir), "a")` — geneste haakjes, en precies het
    # geval dat de eerste versie van de detectie miste.
    assert eigenaren.get("decision_sheets.jsonl") == "decision_sheets.py"
    assert eigenaren.get("founder_park.jsonl") == "founder_park.py"
    # human_inbox.json heeft meerdere schrijvers en hoort dus NIET bij één eigenaar te staan
    assert "human_inbox.json" not in eigenaren
    assert any(b == "human_inbox.json" for b, _ in df["meerdere"])


def test_sectie_b_draagt_geen_regelnummers():
    """Het enige veld dat veranderde zonder dat de architectuur veranderde."""
    from nooch_village import arch_map

    md = arch_map.render_markdown()
    assert "cockpit2.py:" not in md, "regelnummer terug in de kaart — dat is de merge-conflictbron"
    assert "| `decision_sheet_log` | `_act_decision_sheet_log` |" in md
