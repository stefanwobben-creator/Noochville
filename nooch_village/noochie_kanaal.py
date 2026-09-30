"""Twee memo-kanalen tot één logboek (30 september 2026, eenmalig).

WAT ER LAG. De twee wekelijkse memo's kwamen in twee gesprekken terecht, omdat `signaal.stuur` het
DM-kanaal afleidt uit de afzendernaam:

    dm:dc5685eb2074|village   3 weekmemo's     ← wordt leeggehaald
    dm:dc5685eb2074|noochie   de Noochie-memo  ← het doel

Ze gaan over hetzelfde — wat er deze week in en om het dorp gebeurde — en Stefan moest ze allebei
apart onthouden te openen. Sinds vandaag schrijft ook de weekmemo naar het tweede adres
(`weekmemo.LOGBOEK`); dit script haalt de drie die er al staan erbij, zodat het logboek van voren
af aan compleet is.

DE BERICHTEN WORDEN VERPLAATST, NIET HERSCHREVEN. Elk bericht houdt zijn `id`, `at`, `text` en zijn
`author` — óók `author.id == "village"`. Dat is bewust: de auteur is vastgelegde herkomst, en "wie
schreef dit" mag een opruiming niet veranderen. Wat verandert is alleen in welk gesprek het staat.

HET BRONKANAAL BLIJFT BESTAAN, LEEG. Niet verwijderen: er komt niets meer bij (het nieuwe adres is
elders) en een leeg kanaal dat blijft staan is eerlijker dan een sleutel die verdwijnt — wie de
oude URL nog ergens heeft staan, krijgt een leeg gesprek in plaats van een fout.

Zelfde discipline als `dm_samenvoegen.py`, en met opzet zo dicht mogelijk daarbij: vingerafdruk
vooraf, blokkades die bij ELKE run opnieuw worden gesteld, droge run standaard, en achteraf een
veld-voor-veld-vergelijking die moet aantonen dat er alleen verplaatst is.

    python -m nooch_village.village noochie_kanaal            # droge run
    python -m nooch_village.village noochie_kanaal --apply
"""
from __future__ import annotations

import json
import logging
import os

from nooch_village.radar_archief import sha256

log = logging.getLogger("village.noochie_kanaal")

#: Expliciet en niet afgeleid. Een regel die "alle kanalen van village" samenvoegt, voegt op een dag
#: iets samen wat dat niet is — en dit script draait op de echte gesprekken van een mens.
BRON = "dm:dc5685eb2074|village"
DOEL = "dm:dc5685eb2074|noochie"


def _laad(data_dir: str) -> dict:
    pad = os.path.join(data_dir, "channels.json")
    if not os.path.exists(pad):
        return {}
    with open(pad, encoding="utf-8") as fh:
        return (json.load(fh) or {}).get("kanalen", {}) or {}


def plan(data_dir: str) -> dict:
    """Wat zou er gebeuren? Read-only."""
    kan = _laad(data_dir)
    bron = list(kan.get(BRON) or [])
    doel = list(kan.get(DOEL) or [])
    return {"bron": BRON, "doel": DOEL, "bron_n": len(bron), "doel_voor": len(doel),
            "verplaatst": len(bron), "doel_na": len(doel) + len(bron),
            "sha": sha256(os.path.join(data_dir, "channels.json"))}


def blokkades(data_dir: str) -> list[str]:
    """Wat maakt verplaatsen NIET eenduidig? Leeg = veilig.

    Bij ELKE run opnieuw gesteld, niet één keer vooraf: de data kan intussen veranderd zijn — er
    komt immers elke week een memo bij."""
    kan = _laad(data_dir)
    bron = list(kan.get(BRON) or [])
    doel = list(kan.get(DOEL) or [])
    uit = []
    zonder_at = [e.get("id") for e in bron + doel if not e.get("at")]
    if zonder_at:
        uit.append(f"{len(zonder_at)} bericht(en) zonder tijdstempel: niet op volgorde te zetten")
    ids = [e.get("id") for e in bron + doel]
    dubbel = {i for i in ids if i and ids.count(i) > 1}
    if dubbel:
        # EEN DUBBEL ID IS GEEN DETAIL: reacties, bewerken en verwijderen zoeken een bericht op id,
        # en met twee dezelfde treft elke actie het verkeerde — of allebei.
        uit.append(f"dubbele bericht-id's tussen bron en doel: {sorted(dubbel)}")
    if not bron:
        uit.append(f"{BRON} bestaat niet of is al leeg — er is niets te verplaatsen")
    return uit


def verschil_berichten(voor: dict, na: dict) -> list[str]:
    """Is er ONDERWEG iets aan een bericht veranderd? Per bericht-id, veld voor veld.

    Een sha256 zegt alleen dát het bestand anders is — dat is hier per definitie zo. De vraag die
    ertoe doet is of een BERICHT anders is dan het was, en dat is deze vergelijking."""
    def plat(kanalen: dict) -> dict:
        uit = {}
        for k in (BRON, DOEL):
            for e in (kanalen.get(k) or []):
                uit[e.get("id")] = e
        return uit

    a, b = plat(voor), plat(na)
    uit = []
    for bid in sorted(set(a) | set(b), key=str):
        if bid not in b:
            uit.append(f"{bid}: VERDWENEN")
            continue
        if bid not in a:
            uit.append(f"{bid}: NIEUW")
            continue
        for sleutel in sorted(set(a[bid]) | set(b[bid])):
            if a[bid].get(sleutel) != b[bid].get(sleutel):
                uit.append(f"{bid}.{sleutel}: {a[bid].get(sleutel)!r} → {b[bid].get(sleutel)!r}")
    return uit


def voer_uit(data_dir: str, *, apply: bool = False) -> dict:
    from nooch_village.channels import ChannelStore
    from nooch_village.people import PeopleStore

    v = {**plan(data_dir), "toegepast": bool(apply),
         "blokkades": blokkades(data_dir), "onverwacht": [], "ontvolgd": 0}
    if v["blokkades"] or not apply:
        return v

    voor = _laad(data_dir)
    st = ChannelStore(os.path.join(data_dir, "channels.json"))
    kanalen = st._data.setdefault("kanalen", {})
    samen = list(kanalen.get(BRON) or []) + list(kanalen.get(DOEL) or [])
    samen.sort(key=lambda e: float(e.get("at") or 0))
    kanalen[DOEL] = samen
    kanalen[BRON] = []                                   # blijft bestaan, leeg — zie de kop
    st._save()

    # DE VOLG-VERWIJZING MOET MEE WEG. Blijft hij staan, dan houdt de Messages-lijst een leeg
    # gesprek in "Direct" — precies het soort restant waar `ontvolg_allen` voor gemaakt is.
    ps = PeopleStore(os.path.join(data_dir, "people.json"))
    v["ontvolgd"] = ps.ontvolg_allen(BRON)

    na = _laad(data_dir)
    v["onverwacht"] = verschil_berichten(voor, na)       # hoort leeg te zijn: alleen verplaatst
    v["sha_na"] = sha256(os.path.join(data_dir, "channels.json"))
    v["doel_werkelijk"] = len(na.get(DOEL) or [])
    v["bron_werkelijk"] = len(na.get(BRON) or [])
    return v


def rapport(data_dir: str, *, apply: bool = False) -> dict:
    v = voer_uit(data_dir, apply=apply)
    print(f"channels.json sha256 {v['sha'][:16]}…")
    print(f"   {v['bron_n']:3d} bericht(en)  {BRON}   (bron)")
    print(f"   {v['doel_voor']:3d} bericht(en)  {DOEL}   (doel)")
    if v["blokkades"]:
        print("\nNIET EENDUIDIG — er wordt niets verplaatst:")
        for b in v["blokkades"]:
            print(f"   ✗ {b}")
        return v
    print(f"\n{'verplaatst' if apply else 'zou verplaatsen'}: "
          f"{v['verplaatst']} bericht(en) → {v['doel_na']} in het logboek")
    if apply:
        print(f"   werkelijk in het doel : {v.get('doel_werkelijk')}")
        print(f"   bron blijft leeg achter: {v.get('bron_werkelijk')} bericht(en)")
        print(f"   volg-verwijzing weg bij: {v['ontvolgd']} mens(en)")
        print(f"   sha256 ná             : {v.get('sha_na','')[:16]}…")
        print(f"   gewijzigde berichten  : {len(v['onverwacht'])}"
              + ("" if not v["onverwacht"] else f" → {v['onverwacht'][:5]}"))
    else:
        print("\nDroge loop. Voeg --apply toe om het echt te doen.")
    return v
