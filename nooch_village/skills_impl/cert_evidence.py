"""cert_evidence — een ingelezen certificaat wordt een extern bewijsrecord.

De enige weg waarlangs bewijs de Kroniek binnenkomt met een herkomst die NIET van onszelf is. De
claim-pas telt alleen `external_certificate` als onderbouwing; alle andere records zijn onze eigen
skill-runs en die kunnen een claim niet dragen (dat was de cirkelredenering die de dry-run ving).

Leest wat er in `data/certificaten/` ligt, of één stuk tekst uit de payload. Regel-gebaseerd: het
feit, de uitgever en de vervaldatum worden GELEZEN, nooit afgeleid. Ontbreekt het feit of de
vervaldatum, dan komt er geen record — een certificaat waarvan niemand kan zeggen wat het draagt of
tot wanneer, is geen bewijs.

De koppeling naar claims (`claims`) komt van de mens: welk Nooch-onderdeel welk materiaal bevat
weet alleen de founder. Het dorp parseert en ontsluit; het raadt niet.
"""
from __future__ import annotations

import os

from nooch_village import cert_register as cr
from nooch_village.skills import Skill


class CertEvidenceSkill(Skill):
    name = "cert_evidence"
    cost = "free"
    description = ("Leest een certificaat (tekst of bestand in data/certificaten/) en schrijft het "
                   "onderbouwde feit als extern bewijsrecord in de Kroniek. Degradeert eerlijk: "
                   "geen leesbaar feit of geen vervaldatum → geen record.")
    input_schema = ("text: str (de certificaat-tekst) OF bestand: str (pad in data/certificaten/); "
                    "optioneel claims: list[str] — welke claims dit cert draagt")
    required_payload = ((("text", "bestand"),))

    def validate_payload(self, payload: dict, context) -> list[str]:
        if not str((payload or {}).get("text") or "").strip() and \
           not str((payload or {}).get("bestand") or "").strip():
            return ["geef 'text' (de certificaat-tekst) of 'bestand' (pad in data/certificaten/)"]
        return []

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        tekst = str(payload.get("text") or "")
        bron = str(payload.get("bestand") or "")
        data_dir = getattr(context, "data_dir", "") if context is not None else ""

        if bron and not tekst:
            pad = bron if os.path.isabs(bron) else os.path.join(cr.pad(data_dir), bron)
            try:
                with open(pad, encoding="utf-8", errors="replace") as fh:
                    tekst = fh.read()
            except OSError as e:
                # Fail-closed en luid: een onleesbaar certificaat is geen "geen bewijs", het is een
                # bron die we niet konden openen. Dat verschil moet zichtbaar blijven.
                return {"error": f"certificaat niet te lezen: {e}", "bestand": bron}

        if not tekst.strip():
            return {"no_data": True, "reason": "leeg certificaat — niets te lezen", "bestand": bron}

        cert = cr.lees_cert(tekst, bron_pdf=bron)
        claims = [str(c) for c in (payload.get("claims") or []) if str(c).strip()]
        cert["claims"] = claims

        ledger = getattr(context, "evidence", None) if context is not None else None
        record = cr.naar_evidence(cert, ledger) if ledger is not None else None
        uit = {"cert": cert, "ontbreekt": cert.get("ontbreekt") or [],
               "record_id": (record or {}).get("id", ""), "geschreven": bool(record)}
        if not record:
            uit["reason"] = ("geen bewijsrecord geschreven: " +
                             (", ".join(cert.get("ontbreekt") or []) or "geen ledger beschikbaar"))
        if not claims:
            # Een cert zonder claim-koppeling is een feit dat nog nergens aan hangt. Bewust geen
            # gok: de koppeling is founder-input (CLAUDE.md), geen skill-uitvoer.
            uit.setdefault("let_op", []).append(
                "geen claims gekoppeld — dit certificaat draagt nog geen enkele claim")
        return uit
