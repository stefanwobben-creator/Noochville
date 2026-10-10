"""bom — CO2e per paar uit de stuklijst, als dag-observatiebron (10 oktober 2026).

Per model (269 Lo, 269 Hi) één punt per dag: `bom_co2e_per_paar_day::<model>`, bron `bom`. De waarde
rekent `bom_co2.co2_per_paar` uit dezelfde `bom_reken.bereken` als het scherm `/bom`; de meta draagt
de volledigheid (hoeveel materialen een factor hebben, welke niet, hoeveel componenten een gewicht)
en de vingerafdruk van de samenstelling. Zie `bom_co2` voor waarom dat een markering is en geen
reeksbreuk.

Telt er niets mee (geen enkel gewicht met een factor), dan schrijft hij NIETS voor dat model: geen
data is geen nul. Geen sleutel nodig; standaard actief via `collector.migrate_data_sources`.
"""
from __future__ import annotations

import datetime
import os

from nooch_village.skills import DataSourceSkill

VELD = "co2e_per_paar"


def _bom_stores(data_dir: str):
    """De drie stores die /bom leest, los geopend — een skill haalt de cockpit niet binnen."""
    from nooch_village.attachments import AttachmentStore
    from nooch_village.bom_leveranciers import BomLeverancierStore
    from nooch_village.bom_materialen import BomMateriaalStore
    return (AttachmentStore(os.path.join(data_dir, "attachments.json")),
            BomLeverancierStore(os.path.join(data_dir, "bom_leveranciers.json")),
            BomMateriaalStore(os.path.join(data_dir, "bom_materialen.json")))


def per_model(data_dir: str) -> dict[str, dict]:
    """{model: uitkomst van `bom_co2.co2_per_paar`} op modelniveau (zonder kleurvariant)."""
    from nooch_village import bom_co2, bom_reken, wiki
    from nooch_village.data_bom import MODELLEN
    att, lev, mat = _bom_stores(data_dir)
    pags = wiki.paginas(att)
    return {m: bom_co2.co2_per_paar(bom_reken.bereken(MODELLEN[m]["master"], pags, lev.alle(),
                                                      afwijkingen=mat.afwijkingen(m, "")))
            for m in MODELLEN}


class BomCo2Source(DataSourceSkill):
    name = "bom_co2"
    SOURCE = "bom"
    CATALOG_LABEL = "Product footprint (bill of materials)"
    cost = "free"
    side_effect_free = True
    # 'flux' en niet 'snapshot': de dagwaarde is GEEN oplopende stand. Een snapshot-tegel toont
    # standaard de delta per periode; hier is de waarde zelf het antwoord.
    kind = "flux"
    required_env = ()
    description = ("CO2e per pair of shoes from the materials on the bill of materials (/bom): weight "
                   "times the CO2e per kg on each material page, per model. Materials only, not a full "
                   "LCA. When a material has no factor or a component no weight, the number is a lower "
                   "bound and says so; when nothing counts there is no number, never a zero.")
    input_schema = "(none)"
    output_schema = "ok, text, per model: kg, ondergrens, met_factor, materialen, zonder_factor, ..."

    def available_metrics(self, context=None) -> list[str]:
        return [VELD]

    def expected_datum(self, today):
        # Een stand van VANDAAG, niet van gisteren: de stuklijst heeft geen vertraging.
        return today.isoformat()

    def daily_values(self, context, datum: str) -> dict:
        return {}                     # het eigen pad (`collect_series`) schrijft per model

    def collect_series(self, context, today, obs):
        dd = getattr(context, "data_dir", None) or "."
        datum = today.isoformat() if isinstance(today, datetime.date) else str(today)
        geschreven = []
        for model, res in per_model(dd).items():
            if res["kg"] is None:
                continue              # geen data is geen nul
            meta = {k: v for k, v in res.items() if k != "kg"}
            metric = f"{self.SOURCE}_{VELD}_day::{model}"
            if obs.record_daily(self.SOURCE, metric, res["kg"], bron=self.SOURCE, datum=datum,
                                meta=meta):
                geschreven.append((self.SOURCE, f"{VELD}::{model}", datum))
        return geschreven

    def run(self, payload: dict, context=None) -> dict:
        from nooch_village import bom_co2
        from nooch_village.data_bom import MODELLEN
        res = per_model(getattr(context, "data_dir", None) or ".")
        text = " ".join(f"{MODELLEN[m]['naam']}: {bom_co2.tekst(r)}" for m, r in res.items())
        return {"ok": True, "text": text, "per_model": res}
