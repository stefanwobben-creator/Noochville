"""dekking — de cijfers van CN3 "Substantiated pages" als dag-observatiebron (10 oktober 2026).

Elke dag één punt per veld (`dekking_<veld>_day`, bron `dekking`), uit `wiki_dekking.cijfers`:
dezelfde berekening als de sectie Coverage op /bom en de lijst met open vragen. De TEGEL rekent
live; deze bron bewaart alleen de reeks, zodat "Open questions" een trend heeft. Geen sleutel
nodig; standaard actief via `collector.migrate_data_sources`.
"""
from __future__ import annotations

import datetime
import os
import types

from nooch_village.skills import DataSourceSkill

#: De velden die als reeks worden bewaard (sleutels uit `wiki_dekking.cijfers`).
VELDEN = ("gestaafd_pct", "gestaafd", "paginas_totaal", "cellen_open", "met_leverancier",
          "materialen", "paginas_zonder_placeholder", "cellen_checked", "cellen_unchecked",
          "cellen_conflict")


def cijfers_uit_map(data_dir: str) -> dict:
    """De CN3-cijfers vandaag, uit de stores in `data_dir` (een skill haalt de cockpit niet binnen)."""
    from nooch_village import wiki_dekking
    from nooch_village.evidence_ledger import EvidenceLedger
    from nooch_village.skills_impl.bom_co2 import _bom_stores
    from nooch_village.views.wiki import _bijlage_bestaat
    att, lev, mat = _bom_stores(data_dir)
    ledger = EvidenceLedger(os.path.join(data_dir, "evidence_ledger.jsonl"))
    dek, ctx = wiki_dekking.uit_stores(att, lev, mat, ledger=ledger,
                                       bestaat=_bijlage_bestaat(types.SimpleNamespace(dd=data_dir)))
    return wiki_dekking.cijfers(dek, **ctx)


class DekkingSource(DataSourceSkill):
    name = "dekking"
    SOURCE = "dekking"
    CATALOG_LABEL = "Substantiated pages (materials & suppliers)"
    cost = "free"
    side_effect_free = True
    kind = "flux"                 # de dagwaarde is een stand-per-vandaag, geen oplopende som
    required_env = ()
    description = ("Daily snapshot of how well the material and supplier pages of the bill of "
                   "materials are substantiated: pages whose facts are all checked, open questions, "
                   "materials with a supplier, pages without placeholders, and question cells by "
                   "status. Computed from the wiki, the same as the Coverage section on /bom.")
    input_schema = "(none)"
    output_schema = "ok, text, " + ", ".join(VELDEN)

    def available_metrics(self, context=None) -> list[str]:
        return list(VELDEN)

    def expected_datum(self, today):
        return today.isoformat()      # een stand van vandaag; de wiki heeft geen vertraging

    def daily_values(self, context, datum: str) -> dict:
        c = cijfers_uit_map(getattr(context, "data_dir", None) or ".")
        return {v: c.get(v) for v in VELDEN}

    def run(self, payload: dict, context=None) -> dict:
        c = cijfers_uit_map(getattr(context, "data_dir", None) or ".")
        return {"ok": True, "text": (f"{c['gestaafd']} of {c['paginas_totaal']} pages substantiated; "
                                     f"{c['cellen_open']} open questions"), **c}
