"""Drie kanalen die allemaal dezelfde mens zijn, samenvoegen tot één (22 september 2026, eenmalig).

WAT ER LAG. Op productie stonden drie DM-kanalen die alle drie Stefan-met-zichzelf zijn, onder
drie spellingen van dezelfde persoon:

    dm:Stefan Wobben|dc5685eb2074      zijn NAAM naast zijn id
    dm:dc5685eb2074|stefan@nooch.earth zijn id naast zijn E-MAIL
    dm:dc5685eb2074|dc5685eb2074       zijn id naast zichzelf   ← het doel

Dat is een overblijfsel van de inbox-migratie: die schreef de afzender weg zoals hij 'm aantrof —
soms een id, soms een naam, soms een adres. Voor de lezer zijn het drie gesprekken met zichzelf
waar er één hoort te zijn.

DE BERICHTEN WORDEN VERPLAATST, NIET HERSCHREVEN. Elk bericht houdt zijn `id`, `at`, `text` en
zijn `author` — óók als die author "Stefan Wobben" of het e-mailadres is. Dat is bewust: de
auteur-id is vastgelegde herkomst, en "wie zei dit" mag een opruiming niet veranderen. Alle acht
dragen bovendien `author.type == "role"`, en die renderen sowieso al als "Someone"; er verandert
dus ook niets aan wat je ziet.

DE VOLGORDE IS EENDUIDIG, gecontroleerd vóór dit bestand er was: 8 berichten, 8 verschillende
`at`-waarden, 8 verschillende id's, geen ontbrekende tijdstempel, geen bijlagen of reacties, en
geen enkele `gezien`- of `gevolgd`-stand die naar de twee op te heffen kanalen wijst. Zou één van
die dingen niet kloppen, dan hoorde dit script er niet te zijn maar een vraag aan een mens.

Discipline van pijplijnstap 6: vingerafdruk vooraf, droge run standaard, veldvergelijking achteraf.

    python -m nooch_village.village dm_samenvoegen            # droge run
    python -m nooch_village.village dm_samenvoegen --apply
"""
from __future__ import annotations

import json
import logging
import os

from nooch_village.radar_archief import sha256

log = logging.getLogger("village.dm_samenvoegen")

#: De twee die opgaan in de derde. Expliciet en niet afgeleid: een regel die "alles wat op Stefan
#: lijkt" samenvoegt, voegt op een dag iets samen wat dat niet is.
BRONNEN = ("dm:Stefan Wobben|dc5685eb2074", "dm:dc5685eb2074|stefan@nooch.earth")
DOEL = "dm:dc5685eb2074|dc5685eb2074"


def _laad(data_dir: str) -> dict:
    pad = os.path.join(data_dir, "channels.json")
    if not os.path.exists(pad):
        return {}
    with open(pad, encoding="utf-8") as fh:
        return (json.load(fh) or {}).get("kanalen", {}) or {}


def plan(data_dir: str) -> dict:
    """Wat zou er gebeuren? Read-only."""
    kan = _laad(data_dir)
    bron_n = {k: len(kan.get(k) or []) for k in BRONNEN}
    doel_n = len(kan.get(DOEL) or [])
    verplaats = [e for k in BRONNEN for e in (kan.get(k) or [])]
    return {"bronnen": bron_n, "doel_voor": doel_n, "verplaatst": len(verplaats),
            "doel_na": doel_n + len(verplaats),
            "sha": sha256(os.path.join(data_dir, "channels.json"))}


def blokkades(data_dir: str) -> list[str]:
    """Wat maakt samenvoegen NIET eenduidig? Leeg = veilig.

    Dit is de poort die bepaalt of dit script überhaupt mag draaien. Hij staat er omdat de vraag
    "kan dit eenduidig" niet één keer beantwoord moet worden maar bij elke run opnieuw — de data
    kan intussen veranderd zijn."""
    kan = _laad(data_dir)
    alle = [e for k in (*BRONNEN, DOEL) for e in (kan.get(k) or [])]
    uit = []
    zonder_at = [e.get("id") for e in alle if not e.get("at")]
    if zonder_at:
        uit.append(f"{len(zonder_at)} bericht(en) zonder tijdstempel: niet op volgorde te zetten")
    ids = [e.get("id") for e in alle]
    dubbel = {i for i in ids if i and ids.count(i) > 1}
    if dubbel:
        uit.append(f"dubbele bericht-id's: {sorted(dubbel)}")
    ats = [e.get("at") for e in alle]
    if len(set(ats)) != len(ats):
        uit.append("twee berichten met exact dezelfde tijdstempel: volgorde is een gok")
    if not kan.get(DOEL) and not any(kan.get(k) for k in BRONNEN):
        uit.append("geen van de drie kanalen bestaat nog")
    return uit


def verschil_berichten(voor: dict, na: dict) -> list[str]:
    """Is er ONDERWEG iets aan een bericht veranderd? Per bericht-id, veld voor veld.

    Een sha256 zegt alleen dát het bestand anders is — dat is hier per definitie zo. De vraag die
    ertoe doet is of een bericht ánders is dan het was, en dat is deze vergelijking."""
    def plat(kanalen: dict) -> dict:
        uit = {}
        for k in (*BRONNEN, DOEL):
            for e in (kanalen.get(k) or []):
                uit[e.get("id")] = e
        return uit

    a, b = plat(voor), plat(na)
    uit = []
    for bid in sorted(set(a) | set(b)):
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

    v = {**plan(data_dir), "toegepast": bool(apply),
         "blokkades": blokkades(data_dir), "onverwacht": []}
    if v["blokkades"] or not apply:
        return v

    voor = _laad(data_dir)
    st = ChannelStore(os.path.join(data_dir, "channels.json"))
    samen = [e for k in (*BRONNEN, DOEL) for e in (st._data.get("kanalen") or {}).get(k) or []]
    samen.sort(key=lambda e: float(e.get("at") or 0))
    st._data.setdefault("kanalen", {})[DOEL] = samen
    for k in BRONNEN:
        st._data["kanalen"].pop(k, None)
    st._save()

    na = _laad(data_dir)
    v["onverwacht"] = verschil_berichten(voor, na)      # hoort leeg te zijn: alleen verplaatst
    v["sha_na"] = sha256(os.path.join(data_dir, "channels.json"))
    v["doel_werkelijk"] = len(na.get(DOEL) or [])
    v["bronnen_weg"] = [k for k in BRONNEN if k not in na]
    return v


def rapport(data_dir: str, *, apply: bool = False) -> dict:
    v = voer_uit(data_dir, apply=apply)
    print(f"channels.json sha256 {v['sha'][:16]}…")
    for k, n in v["bronnen"].items():
        print(f"   {n:3d} bericht(en)  {k}")
    print(f"   {v['doel_voor']:3d} bericht(en)  {DOEL}   (doel)")
    if v["blokkades"]:
        print("\nNIET EENDUIDIG — er wordt niets samengevoegd:")
        for b in v["blokkades"]:
            print(f"   ✗ {b}")
        return v
    print(f"\n{'samengevoegd' if apply else 'zou samenvoegen'}: "
          f"{v['verplaatst']} bericht(en) → {v['doel_na']} in totaal")
    if apply:
        print(f"   werkelijk in het doel : {v.get('doel_werkelijk')}")
        print(f"   bronkanalen weg       : {len(v.get('bronnen_weg', []))}/2")
        print(f"   sha256 ná             : {v.get('sha_na','')[:16]}…")
        print(f"   gewijzigde berichten  : {len(v['onverwacht'])}"
              + ("" if not v["onverwacht"] else f" → {v['onverwacht'][:5]}"))
    else:
        print("\nDROGE RUN — er is niets geschreven. Draai met --apply.")
    return v
