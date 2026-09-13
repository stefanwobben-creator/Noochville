"""site_watch — merk of een publieke pagina veranderd is sinds de vorige keer.

WAAROM DEZE SKILL BESTAAT. `concurrentiedossier.md` (12 sept) liet zien dat `competitor_news`
(nieuws/RSS) een concurrent mist die zonder persbericht zijn prijs, materiaalclaim of certificering
aanpast — precies het soort stille wijziging die het meest zegt over wat een concurrent daadwerkelijk
doet. De bouwstenen liggen er al: `safe_fetch` (dezelfde SSRF-guardrail, backoff en Retry-After als
`haal_pagina`) haalt een pagina op, maar niets in het dorp onthield wat er de VORIGE keer stond.

WAT HIJ DOET. Eén URL, elke keer opnieuw aangeroepen: haalt de leesbare tekst op, vergelijkt hem
regel-voor-regel met de laatst bewaarde versie van diezelfde URL (`data/site_watch/<hash>.json`), en
meldt wat is toegevoegd en wat is verdwenen. De nieuwe versie wordt de nieuwe basislijn — dit is dus
altijd "wat veranderde SINDS DE VORIGE CHECK", niet "sinds het allereerste bezoek".

DE GRENZEN, in dezelfde geest als `haal_pagina`:
- **Alleen lezen.** Geen formulieren, geen login. Zelfde SSRF-guardrail via `safe_fetch`.
- **Fail-closed op het ophalen.** Een netwerkfout is een fout, geen 'geen wijziging'.
- **`no_data` ≠ nul.** Geen wijziging gevonden is een ANTWOORD (de pagina is gecontroleerd en stabiel
  gebleken), geen storing. De EERSTE keer op een URL is ook `no_data`: er is nog niets om tegen af te
  zetten — dat is een basislijn vastleggen, geen "geen wijziging" (die zou een concurrent die zijn
  site al twee keer veranderd had vóór het dorp meekeek, ten onrechte 'stabiel' laten lezen).
- **Geen oordeel.** Deze skill signaleert een verschil en citeert de gewijzigde regels; of dat verschil
  ergens toe doet (een prijswijziging, een nieuwe claim) beoordeelt de lezer of `lead_beoordeling`.
- **Whitespace-ruis genegeerd.** Regels worden vergeleken na `strip()`; een pagina die alleen anders
  is ingesprongen meldt geen wijziging.

Geen sleutel nodig: dezelfde `safe_fetch`-laag als `haal_pagina`, dus meteen te gebruiken.
"""
from __future__ import annotations

import difflib
import hashlib
import os
from datetime import datetime, timezone

from nooch_village import safe_fetch, web_read
from nooch_village.skills import Skill
from nooch_village.util import JsonStore

_MAX_GEWIJZIGD = 25            # zoveel regels tonen we er hooguit van elke soort (niet de hele pagina)
_MAX_REGEL = 300               # één getoonde regel; langer is geen citaat meer


class _SnapshotStore(JsonStore):
    """Eén bestand = de laatst geziene versie van ÉÉN URL. Erft `JsonStore` i.p.v. zelf
    `atomic_write_json` aan te roepen (guard-test `test_geen_ongelockte_write`): elke JSON-schrijf
    in het dorp gaat via `JsonStore._save`, zodat een gelijktijdige tweede schrijver nooit een
    lost update veroorzaakt. `_items` is hier gewoon de snapshot-dict zelf, geen collectie — dat is
    een geldig gebruik van de basisklasse, ze eist geen meervoudige items."""
    _WRITE_METHODS = ("zet",)

    def leeg(self) -> bool:
        return not str(self._items.get("tekst") or "").strip()

    def zet(self, url: str, tekst: str, nu: str) -> None:
        self._items = {"url": url, "tekst": tekst, "laatst_gecontroleerd": nu}
        self._save()


def _kort(s: str, n: int = _MAX_REGEL) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _sleutel(url: str) -> str:
    """Bestandsveilige naam voor deze URL: een korte hash, niet de URL zelf (kan rare tekens
    bevatten en te lang worden voor een bestandsnaam op sommige filesystems)."""
    return hashlib.sha256((url or "").strip().encode("utf-8")).hexdigest()[:24]


def _pad(data_dir: str, url: str) -> str:
    return os.path.join(data_dir, "site_watch", f"{_sleutel(url)}.json")


def _regels(tekst: str) -> list[str]:
    return [r.strip() for r in (tekst or "").split("\n") if r.strip()]


def vergelijk(oud: str, nieuw: str) -> tuple[list[str], list[str]]:
    """(toegevoegd, verwijderd) — regels die alleen in `nieuw` resp. alleen in `oud` staan, in
    volgorde van voorkomen. `SequenceMatcher` i.p.v. een setverschil: een verplaatste regel (dezelfde
    tekst, andere plek) telt dan niet als 'gewijzigd', alleen ECHT nieuwe/verdwenen regels doen dat."""
    oude_regels = _regels(oud)
    nieuwe_regels = _regels(nieuw)
    sm = difflib.SequenceMatcher(a=oude_regels, b=nieuwe_regels, autojunk=False)
    toegevoegd: list[str] = []
    verwijderd: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            verwijderd.extend(oude_regels[i1:i2])
        if tag in ("replace", "insert"):
            toegevoegd.extend(nieuwe_regels[j1:j2])
    return toegevoegd[:_MAX_GEWIJZIGD], verwijderd[:_MAX_GEWIJZIGD]


class SiteWatchSkill(Skill):
    name = "site_watch"
    cost = "rate_limited"          # publieke pagina, beleefde backoff via safe_fetch — geen credits
    side_effect_free = False       # bewaart de laatst geziene versie in data/site_watch/
    description = ("Reads ONE public page you already have the URL of and reports what changed on it "
                    "since the last time this skill checked that same URL — added lines and removed "
                    "lines, whitespace-only differences ignored. The first check on a new URL only "
                    "records a baseline (no_data, nothing to compare yet); every check after that "
                    "compares against the PREVIOUS check, not the very first one. Use it to watch a "
                    "competitor's pricing, product or claims page for silent changes. Read-only, "
                    "fail-closed, no judgement about whether a change matters.")
    input_schema = ("url: str (required — a real http(s) address, never a placeholder); "
                     "label: str (optional — a short human name for this page, e.g. 'Veja pricing', "
                     "used only in the report text; default the domain)")
    required_payload = ("url",)
    output_schema = ("ok, url, label, eerste_keer: bool, aantal_toegevoegd, aantal_verwijderd, "
                      "toegevoegd[str], verwijderd[str], vorige_check: str|None, text | "
                      "no_data + reason (baseline vastgelegd, of geen wijziging) | "
                      "error + tijdelijk (on fetch failure)")

    def __init__(self, haal=None):
        # Injecteerbaar, zelfde reden als bij HaalPaginaSkill: een test bewijst dit zonder netwerk.
        self._haal = haal or safe_fetch.haal_tekst_geduldig

    def validate_payload(self, payload: dict, context) -> list:
        """Zelfde grond als `HaalPaginaSkill.validate_payload`: een URL die de planner zelf nog niet
        kent (een afhankelijkheid op een eerdere stap) wordt hier bewust geen 'geen skill' maar een
        zichtbare planningsfout — zie het PLACEHOLDER-incident van 8 september in haal_pagina.py."""
        rauw = (payload or {}).get("url")
        url = str(rauw or "").strip()
        if not url:
            return []                                    # afwezigheid dekt `required_payload` al
        if not url.lower().startswith(("http://", "https://")):
            kort = url if len(url) <= 60 else url[:57] + "…"
            return [f"'url' is geen adres maar tekst ({kort!r}) — een stap die de URL pas uit een "
                    f"eerdere stap kan halen, hoort een mens-taak te zijn of te wachten"]
        return []

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        url = (payload.get("url") or "").strip()
        if not url:
            return {"error": "ontbrekende parameter: 'url' is verplicht"}
        label = str(payload.get("label") or "").strip() or web_read.domain_of(url)

        try:
            gehaald = self._haal(url)
        except safe_fetch.FetchGeweigerd as e:
            return {"error": f"URL geweigerd: {e}", "url": url, "tijdelijk": False}
        except safe_fetch.FetchMislukt as e:
            return {"error": f"ophalen mislukt: {e}", "url": url,
                    "tijdelijk": bool(safe_fetch.is_tijdelijk(e)),
                    "status": getattr(e, "status", None)}
        except Exception as e:                       # onverwacht: nooit als lege uitkomst doorgeven
            return {"error": f"onverwachte fout bij ophalen: {type(e).__name__}: {e}",
                    "url": url, "tijdelijk": False}

        gehaald = gehaald if isinstance(gehaald, dict) else {}
        tekst = gehaald.get("tekst") or ""
        gelezen_url = gehaald.get("url") or url
        basis = {"ok": True, "url": gelezen_url, "label": label}

        if not tekst.strip():
            # Zelfde onderscheid als haal_pagina: opgehaald maar niets leesbaars is een antwoord
            # ("niets te vergelijken"), geen storing.
            return {**basis, "no_data": True,
                    "reason": "page has no readable text (probably JavaScript-only or empty) — "
                              "nothing to compare"}

        data_dir = getattr(context, "data_dir", None) if context is not None else None
        if not data_dir:
            return {**basis, "error": "no data_dir in context — cannot remember the previous version "
                                       "of this page, so a change cannot be detected"}

        store = _SnapshotStore(_pad(data_dir, gelezen_url))
        nu = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if store.leeg():
            store.zet(gelezen_url, tekst, nu)
            return {**basis, "eerste_keer": True, "no_data": True,
                    "reason": f"baseline recorded for {label} — nothing to compare yet; the next "
                              f"check will report what changed since today"}

        vorige_tekst = str(store._items.get("tekst") or "")
        vorige_check = store._items.get("laatst_gecontroleerd")
        toegevoegd, verwijderd = vergelijk(vorige_tekst, tekst)
        # Elke check herschrijft de basislijn naar de HUIDIGE versie: het volgende verschil is dus
        # weer 'sinds de vorige check', niet 'sinds ooit' — anders stapelt elke kleine wijziging op
        # tot één onleesbare mega-diff die na een paar checks niets meer zegt.
        store.zet(gelezen_url, tekst, nu)

        if not toegevoegd and not verwijderd:
            return {**basis, "eerste_keer": False, "vorige_check": vorige_check, "no_data": True,
                    "reason": f"no change on {label} since the last check"
                              + (f" ({vorige_check})" if vorige_check else "")}

        uit = {**basis, "eerste_keer": False, "vorige_check": vorige_check,
               "aantal_toegevoegd": len(toegevoegd), "aantal_verwijderd": len(verwijderd),
               "toegevoegd": [_kort(r) for r in toegevoegd],
               "verwijderd": [_kort(r) for r in verwijderd]}
        uit["text"] = self._als_tekst(label, toegevoegd, verwijderd)
        return uit

    @staticmethod
    def _als_tekst(label: str, toegevoegd: list[str], verwijderd: list[str]) -> str:
        kop = f"{label}: {len(toegevoegd)} line(s) added, {len(verwijderd)} line(s) removed since last check."
        voorbeeld = (toegevoegd or verwijderd or [""])[0]
        soort = "added" if toegevoegd else "removed"
        return kop + (f" First {soort}: “{_kort(voorbeeld, 160)}”." if voorbeeld else "")
