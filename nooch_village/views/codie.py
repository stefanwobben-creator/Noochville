"""Codie-backlog — de oogst van wat het dorp niet kán, als probleemstellingen.

Elke keer dat werk vastloopt omdat niemand het kan uitvoeren, schrijft de escalatie-router een
capaciteit-gat-record. Dit scherm aggregeert die records: geclusterd per ontbrekende capaciteit,
gerangschikt op hoeveel PROJECTEN elk cluster blokkeerde, met de rollen die er tegenaan liepen.

Twee bewuste keuzes:

**Probleemstelling, geen code-spec.** Elk cluster leest als "dit gebeurde, zo vaak, bij deze rollen,
en dit zou een oplossing moeten opleveren" — niet als een technisch ontwerp. Dát denkwerk is precies
wat je niet wilt automatiseren. Codie draft hiermee, een mens beoordeelt, en pas daarna schrijft
iemand code.

**Read-only.** De mens-poort van deze keten zit op het pad van gat naar code-wijziging, niet op het
routeren. Er staan hier dus geen knoppen: dit scherm laat zien wat er is, het besluit ligt elders.

Alleen `missing_capability` voedt de dev-backlog. Mens-/extern werk (`human_external`) staat er apart
onder als context — hoeveel mens-werk zit er in de keten? — maar is nooit een feature-verzoek.
"""
from __future__ import annotations

import time

from nooch_village import gap_ledger
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.web_base import _e, _page


def _rol(rol_id: str) -> str:
    return (rol_id or "?").split("__")[-1]


def _sinds(ts: float) -> str:
    try:
        dagen = int((time.time() - float(ts)) // 86400)
    except (TypeError, ValueError):
        return ""
    if dagen <= 0:
        return "vandaag"
    return f"{dagen} dag{'en' if dagen != 1 else ''} geleden"


def _cluster_card(c: dict, rang: int) -> str:
    rollen = " ".join(f"<span class='chip outline'>{_e(_rol(r))} ({n}×)</span>"
                      for r, n in c["rollen"][:6])
    voorbeelden = "".join(f"<li class='muted'>{_e((r.get('item_text') or '')[:160])}</li>"
                          for r in c["records"][:3])
    n_p = c["n_projecten"]
    keten = ""
    sporen = [" → ".join(_rol(x) for x in r.get("hop_trail") or []) for r in c["records"]]
    sporen = sorted({s for s in sporen if s})
    if sporen:
        keten = (f"<div class='rdr-meta muted'>Ging eerst langs: "
                 f"{_e('; '.join(sporen[:3]))} — en liep daar ook vast.</div>")
    return (
        f"<div class='card'>"
        f"<div class='rdr-sig'>{rang}. {_e(c['capability'])}</div>"
        f"<div><b>Blokkeerde {n_p} project{'en' if n_p != 1 else ''}</b> "
        f"({c['n_records']} keer vastgelopen, laatst {_e(_sinds(c['laatst']))}).</div>"
        f"<div class='rdr-meta'>{rollen}</div>"
        f"{keten}"
        f"<div class='rdr-meta'><b>Wat er nu gebeurt:</b> het werk loopt vast en wacht op een mens. "
        f"<b>Wat een oplossing zou moeten opleveren:</b> dat een rol dit zelf kan uitvoeren.</div>"
        f"<details class='box-details'><summary>Voorbeelden uit de projecten</summary>"
        f"<ul class='clean'>{voorbeelden}</ul></details>"
        f"</div>")


def _mens_blok(data_dir: str) -> str:
    """Mens-/extern werk apart: context, geen backlog. Het zegt iets over hoeveel handwerk er in de
    keten zit, maar er valt niets aan te bouwen."""
    mens = gap_ledger.clusters(data_dir, reason=gap_ledger.HUMAN_EXTERNAL)
    if not mens:
        return ""
    rijen = "".join(
        f"<li>{_e(c['capability'] if c['capability'] != '(geen label)' else (c['records'][0].get('item_text') or '')[:120])}"
        f" <span class='muted'>· {c['n_projecten']} project(en) · "
        f"{_e(', '.join(_rol(r) for r, _n in c['rollen'][:3]))}</span></li>" for c in mens[:10])
    totaal = sum(c["n_records"] for c in mens)
    return (f"<div class='c2-sec'><h3>Mens- of extern werk ({totaal})</h3>"
            f"<p class='muted'>Geen backlog: hier valt niets te bouwen. Wel het antwoord op "
            f"'hoeveel handwerk zit er in deze keten?'</p><ul class='clean'>{rijen}</ul></div>")


def render_codie(data_dir: str) -> str:
    clusters = gap_ledger.clusters(data_dir)
    kaarten = "".join(_cluster_card(c, i + 1) for i, c in enumerate(clusters[:25]))
    if not clusters:
        kaarten = ("<p class='muted'>Nog geen capaciteitsgaten geoogst. Er ontstaat een record zodra "
                   "werk vastloopt omdat geen enkele rol het kan uitvoeren — dus geen records "
                   "betekent: er liep niets vast, of de dorpspuls draait niet.</p>")
    geblokkeerd = len({p for c in clusters for p in c["projecten"]})
    main = (f"<div class='c2-main'><h1>Codie-backlog</h1>"
            f"<p class='muted'>Wat het dorp niet kán, geoogst op het moment dat het pijn deed. "
            f"{len(clusters)} capaciteit(en) hielden samen {geblokkeerd} project(en) tegen, "
            f"gerangschikt op hoe vaak ze in de weg zaten.</p>"
            f"<p class='muted'>Dit zijn probleemstellingen, geen specs: Codie draft, een mens "
            f"beoordeelt, en pas daarna gaat er code in. Het dorp stelt voor, het merget zichzelf "
            f"niet.</p>"
            f"{kaarten}{_mens_blok(data_dir)}</div>")
    return _page("Codie-backlog", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
