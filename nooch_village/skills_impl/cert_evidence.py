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

Drie uitkomsten (scope 56), fail-closed:
  {"ok": True, "cert": …, "record_id": …}   het record staat in de Kroniek (mét `verlopen`-vlag als
                                            het certificaat al verlopen is — het wordt wél bewaard,
                                            want de wachtlijst zegt dan "vernieuw", maar het draagt
                                            geen claim: de leeskant vergelijkt `geldig_tot` opnieuw)
  {"ok": False, "error": …}                 niets geschreven — onleesbaar bestand, geen tekstlaag, geen
                                            feit of vervaldatum, of geen Kroniek. Tot scope 56 boekte
                                            "niet geschreven" als gelukt: de `cert`-dict won de
                                            inhoudsrace en het item werd afgevinkt (skill-review).
"""
from __future__ import annotations

import os

from nooch_village import cert_register as cr
from nooch_village.skills import Skill


def lees_pdf(pad: str) -> str:
    """De tekstlaag van een PDF, via pypdf (staat in requirements). Lazy geïmporteerd en fail-closed:
    ontbreekt pypdf, dan is dat een zichtbare fout en geen 'leeg certificaat'.

    Tot scope 56 werd een PDF als utf-8-tekst gelezen; de regexen vinden in PDF-bytes niets, dus
    eindigde élke echte certificaat-PDF met `ontbreekt=[feit, instantie, geldig_tot]`."""
    try:
        from pypdf import PdfReader
    except ImportError as e:                               # pragma: no cover — omgeving zonder pypdf
        raise RuntimeError("pypdf ontbreekt — een PDF-certificaat is niet te lezen "
                           "(pip install pypdf), of geef de tekst mee via 'text'") from e
    reader = PdfReader(pad)
    paginas = [(p.extract_text() or "") for p in reader.pages]
    return "\n\n".join(t.strip() for t in paginas if t.strip())


class CertEvidenceSkill(Skill):
    name = "cert_evidence"
    cost = "free"
    side_effect_free = False      # schrijft een record in de Kroniek
    description = ("Reads one certificate (text, or a .txt/.pdf file in data/certificaten/) and writes "
                   "the certified fact as an EXTERNAL evidence record in the Kroniek — the only kind "
                   "of record that can substantiate a claim. Rule-based reading, no model: fact, "
                   "issuer and expiry date are read, never inferred; no fact or no expiry date → no "
                   "record. Reports an already-expired certificate as such.")
    input_schema = ("text: str (the certificate text) OR bestand: str (file name in data/certificaten/, "
                    ".txt or .pdf; must exist) — one of the two is required · "
                    "claims: list[str] (optional — which claims this certificate carries, verbatim; "
                    "without it the record carries no claim yet)")
    output_schema = ("ok, text, cert{feit, instantie, leverancier, materiaal, niveau, geldig_tot, "
                     "bron_pdf, claims, ontbreekt[]}, record_id, geschreven, verlopen, let_op[] | "
                     "error (+reason)")
    required_payload = ((("text", "bestand"),))

    def validate_payload(self, payload: dict, context) -> list[str]:
        p = payload or {}
        tekst = str(p.get("text") or "").strip()
        bron = str(p.get("bestand") or "").strip()
        if not tekst and not bron:
            return ["geef 'text' (de certificaat-tekst) of 'bestand' (pad in data/certificaten/)"]
        if bron and not tekst:
            # Een verzonnen bestandsnaam sneuvelt bij het PLANNEN, niet pas live. Zonder data_dir
            # (geen context) is er niets te toetsen — fail-soft, de skill zelf faalt dan closed.
            data_dir = getattr(context, "data_dir", "") if context is not None else ""
            if data_dir and not os.path.isfile(self._pad(bron, data_dir)):
                return [f"bestand '{bron}' bestaat niet in {cr.pad(data_dir)} — leg het certificaat "
                        f"daar neer of geef de tekst mee via 'text'"]
        return []

    @staticmethod
    def _pad(bron: str, data_dir: str) -> str:
        return bron if os.path.isabs(bron) else os.path.join(cr.pad(data_dir), bron)

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        tekst = str(payload.get("text") or "")
        bron = str(payload.get("bestand") or "")
        data_dir = getattr(context, "data_dir", "") if context is not None else ""

        if bron and not tekst:
            pad = self._pad(bron, data_dir)
            try:
                if pad.lower().endswith(".pdf"):
                    tekst = lees_pdf(pad)
                    if not tekst.strip():
                        # Een scan zonder tekstlaag is niet 'leeg', hij is niet te lezen: OCR
                        # valt buiten deze skill en de mens moet dat weten.
                        return {"ok": False, "bestand": bron,
                                "error": f"PDF '{bron}' heeft geen tekstlaag (scan?) — OCR wordt "
                                         f"niet ondersteund; geef de tekst mee via 'text'"}
                else:
                    with open(pad, encoding="utf-8", errors="replace") as fh:
                        tekst = fh.read()
            except (OSError, RuntimeError, ValueError) as e:
                # Fail-closed en luid: een onleesbaar certificaat is geen "geen bewijs", het is een
                # bron die we niet konden openen. Dat verschil moet zichtbaar blijven.
                return {"ok": False, "error": f"certificaat niet te lezen: {e}", "bestand": bron}

        if not tekst.strip():
            return {"ok": False, "error": "leeg certificaat — niets te lezen", "bestand": bron}

        cert = cr.lees_cert(tekst, bron_pdf=bron)
        claims = payload.get("claims") or []
        if isinstance(claims, str):
            claims = [claims]
        claims = [str(c) for c in claims if str(c).strip()]
        cert["claims"] = claims

        from nooch_village.evidence_ledger import van_context
        ledger = van_context(context)
        if ledger is None:
            return {"ok": False, "cert": cert, "ontbreekt": cert.get("ontbreekt") or [],
                    "geschreven": False,
                    "error": "geen bewijsrecord geschreven: geen Kroniek beschikbaar (geen context "
                             "of data_dir)"}
        record = cr.naar_evidence(cert, ledger)
        if not record:
            ontbreekt = ", ".join(cert.get("ontbreekt") or []) or "feit of vervaldatum niet leesbaar"
            reden = f"geen bewijsrecord geschreven: {ontbreekt} niet te lezen uit het certificaat"
            return {"ok": False, "cert": cert, "ontbreekt": cert.get("ontbreekt") or [],
                    "geschreven": False, "error": reden, "reason": reden}

        uit = {"ok": True, "cert": cert, "ontbreekt": cert.get("ontbreekt") or [],
               "record_id": record.get("id", ""), "geschreven": True,
               "verlopen": cr.verlopen(cert) is True}
        let_op = []
        if uit["verlopen"]:
            # Wél bewaard (de wachtlijst zegt dan "vernieuw bij <leverancier>"), maar het draagt
            # geen claim — en dat moet de mens hier lezen, niet pas in de claim-pas.
            let_op.append(f"certificaat verlopen ({cert.get('geldig_tot')}) — het draagt geen enkele "
                          f"claim; vernieuw het bij {cert.get('leverancier') or 'de leverancier'}")
        if not claims:
            # Een cert zonder claim-koppeling is een feit dat nog nergens aan hangt. Bewust geen
            # gok: de koppeling is founder-input (CLAUDE.md), geen skill-uitvoer.
            let_op.append("geen claims gekoppeld — dit certificaat draagt nog geen enkele claim")
        if let_op:
            uit["let_op"] = let_op
        uit["text"] = self._kop(cert, uit)
        return uit

    @staticmethod
    def _kop(cert: dict, uit: dict) -> str:
        """De leeswijzer: wat er gelezen is en of het bewijs draagt, in één zin."""
        kop = (f"certificate read: “{str(cert.get('feit') or '?')[:120]}” — issued by "
               f"{cert.get('instantie') or '?'}, valid until {cert.get('geldig_tot') or '?'}; "
               f"evidence record {uit.get('record_id') or '?'} written")
        if uit.get("verlopen"):
            kop += f" — EXPIRED on {cert.get('geldig_tot')}: carries no claim until renewed"
        if cert.get("claims"):
            kop += " (claims: " + ", ".join(cert["claims"][:3]) + ")"
        else:
            kop += " (no claims linked yet)"
        if cert.get("ontbreekt"):
            kop += " — not readable: " + ", ".join(cert["ontbreekt"])
        return kop
