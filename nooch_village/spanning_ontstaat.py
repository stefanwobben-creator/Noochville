"""Wat er gebeurt op het moment dat een spanning ontstaat.

Eén call, één keer, bij het ontstaan — en alles daarna leest mee. Geen batch en geen vergadering:
wie de spanning later opent, leest de al-geschreven bevinding en het al-bepaalde type.

Dit is de haak die `NotifStore.add` aanroept. De store blijft dom; deze module weet van het model
en van de typering, en hij is fail-soft: gaat er iets mis, dan blijft de rauwe notificatie gewoon
staan. Een spanning die niet verrijkt kon worden is nog steeds een spanning.
"""
from __future__ import annotations

import logging

log = logging.getLogger("village.spanning")

def maak_verrijker(records, assignments, data_dir: str = "", reason_fn=None,
                   herschrijf: bool = True):
    """Bouw de haak. Geeft een functie die één verse notificatie verrijkt.

    TWEE HANDELINGEN, EN ZE ZIJN NIET HETZELFDE — dat bleek pas toen een test omviel:

      * TYPEREN (`zelf_verwerking`) zegt wát dit is: een vraag aan een rol, een besluit, een
        melding. Het is een classificatie NAAST de tekst; er verandert geen woord.
      * HERSCHRIJVEN (`bevinding`) maakt de zin die de lezer te zien krijgt IN PLAATS VAN de rauwe
        signalering (zie `views/inbox.py::_regel`). Dat is een vervanging, geen aanvulling.

    Alleen die tweede raakt de woorden van wie het typte. `herschrijf=False` laat dus de tekst met
    rust en typeert wél — precies wat een mens-getypte spanning nodig heeft: hij is al leesbaar, hij
    moet alleen nog ergens heen. Zonder dit onderscheid zou 'nooit andermans woorden herschrijven'
    stilzwijgend ook de routering uitzetten, en dan is een principe een storing geworden."""
    from nooch_village import bevinding as bv, zelf_verwerking as zv

    def _verrijk(n: dict) -> dict:
        # WIE DIT LEEST is de poort, en die staat in `NotifStore.add` (`_is_mens_lezer`). Hier stond
        # dezelfde vraag nog eens, maar strenger: alleen rollen (personen vielen af) en alleen als
        # de AFZENDER niet sliep. Twee rol-hulpje-regels die niet standhouden zodra dit een
        # communicatielaag is — het puls-wacht-alarm heeft geen afzender-rol, en 17 notificaties
        # gaan naar een persoon. De lezer wint. Deze functie doet nu alleen nog de INHOUD.
        rol = str(n.get("by") or "")
        # DE VOLLE TEKST, niet de preview. Dit las `snippet` — de afgekapte kopie — en herschreef
        # dus een spanning die al halverwege een zin ophield. De herschrijver kon nooit compleet
        # maken wat hem incompleet werd aangereikt.
        from nooch_village.notifications import volledig
        tekst = volledig(n)
        if not tekst.strip():
            return {}
        b = bv.herschrijf(tekst, rol=rol, records=records, reason_fn=reason_fn) if herschrijf else {}
        t = zv.verwerk(tekst, rol=rol, records=records, reason_fn=reason_fn,
                       voorstel=b.get("voorstel") or "", data_dir=data_dir)
        log.info("spanning van %s getypeerd als %s (bevinding %s)", rol or "?",
                 t.get("uitkomst"), ("ok" if b.get("ok") else "geweigerd") if herschrijf
                 else "eigen woorden")
        uit = {"type": t.get("uitkomst"), "type_reden": t.get("reden")}
        if herschrijf:
            uit["bevinding"] = b
        return uit

    return _verrijk
