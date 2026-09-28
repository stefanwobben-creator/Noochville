"""Linkbuilding — de gidsen waar Nooch in vermeld wil worden, en wat we ermee doen.

HET SCHERM IS OPNIEUW GEBOUWD (28 september 2026). Er stond er ooit een; die is in #516 met 26.000
andere regels opgeruimd, samen met zijn `LinkTargetQueue`-store. Dit is geen restore van die code: het
volgt het patroon dat sindsdien is uitgewerkt voor de site-audit (#634), en dat is wat de oude
versie miste.

DRIE DINGEN DIE DE OUDE NIET HAD, en ze zijn de reden dat dit bestand bestaat:

  1. DE ZOEKOPDRACHT DUURT. SerpAPI plus acht pagina's lezen is tientallen seconden. Dat hoort niet
     in een POST-handler: die blokkeert een serverthread, geeft een pagina die hangt zonder te
     zeggen waarom, en loopt tegen elke proxy-timeout aan. Hij draait in een achtergrondthread.
  2. TWEE KEER TEGELIJK IS NIET DUBBEL WERK. Twee zoekopdrachten schrijven door elkaar heen in
     dezelfde lijst. Eén slot (`util.Werkslot`, gedeeld met de site-audit), atomair genomen in de
     verzoek-thread — niet in de werk-thread, want dan ontdekken twee kliks pas binnenin dat ze te
     laat zijn.
  3. EEN MISLUKTE ZOEKTOCHT LAAT EEN SPOOR. Een achtergrondthread heeft geen scherm om op te
     vallen; zonder dit is "geen sleutel" niet te onderscheiden van "nog niet geklikt".

EEN BESLUIT IS VAN EEN MENS. De skill rangschikt (hoog/midden/laag/onbekend) — dat is een meting
op de tekst van de gids. Pitchen of negeren is een oordeel, en dat schrijft alleen een mens hier
weg. Er is geen automatische tak die dat voor je doet.
"""
from __future__ import annotations

import logging
import os
import time

from nooch_village.util import JsonStore, Werkslot

log = logging.getLogger("village.linkbuilding")

#: De prioriteiten die de skill toekent, in de volgorde waarin je ze wilt zien. "hoog" = de gids
#: noemt je concurrenten maar Nooch niet — de sterkste pitch die er is.
PRIORITEITEN = ("hoog", "midden", "laag", "onbekend")

#: Wat een mens met een doelwit kan doen. `open` is de stand waarin de skill hem achterlaat.
BESLUITEN = ("pursue", "ignore")


class LinkTargetQueue(JsonStore):
    """De gevonden gidsen, met het menselijke besluit erbij. Gededupliceerd op de URL.

    HIJ HEET BEWUST NIET `LinkTargets`. Zo heette de store die in #516 is verwijderd, en die komt
    niet terug: andere vorm (`{candidates, pursued, ignored}` met lijsten ernaast), ander bestand
    (`linkbuilding_targets.json`), en geen JsonStore. Een gelijke naam zou lezen als een restore.
    Die oude data staat er op productie trouwens nog — 68 kandidaten en 4 genegeerde — maar
    importeren is een besluit, geen bijvangst van deze bouw.

    EEN NIEUWE ZOEKOPDRACHT OVERSCHRIJFT GEEN BESLUIT. Dat is de hele reden dat dit een store is en
    niet een lijst in het geheugen: je zoekt vaker dan je beslist, en een gids die je vorige week
    genegeerd hebt hoort niet elke ronde opnieuw bovenaan te staan. De MEETWAARDEN (prioriteit,
    mentions, snippet) worden wél bijgewerkt — die zijn een waarneming en die kan veranderen."""

    _STATE = "_items"
    _default = dict
    _EXPECT = dict
    _WRITE_METHODS = ("zet_vondsten", "beslis")

    def zet_vondsten(self, targets: list[dict], query: str) -> tuple[int, int]:
        """Schrijf een zoekresultaat weg. Geeft (nieuw, bijgewerkt)."""
        nieuw = bij = 0
        for t in targets or []:
            link = str((t or {}).get("link") or "").strip()
            if not link:
                continue
            bestaand = self._items.get(link)
            rij = {
                "link": link,
                "title": str(t.get("title") or "").strip()[:200],
                "source": str(t.get("source") or "").strip()[:120],
                "snippet": str(t.get("snippet") or "").strip()[:400],
                "priority": t.get("priority") if t.get("priority") in PRIORITEITEN else "onbekend",
                "mentions": [str(m)[:60] for m in (t.get("mentions") or [])][:12],
                "query": query or "",
                "gezien_op": time.time(),
            }
            if bestaand:
                # HET BESLUIT BLIJFT VAN DE MENS, de meting is van de skill.
                rij["status"] = bestaand.get("status") or "open"
                rij["door"] = bestaand.get("door") or ""
                rij["besloten_op"] = bestaand.get("besloten_op") or 0
                rij["gevonden_op"] = bestaand.get("gevonden_op") or rij["gezien_op"]
                bij += 1
            else:
                rij.update({"status": "open", "door": "", "besloten_op": 0,
                            "gevonden_op": rij["gezien_op"]})
                nieuw += 1
            self._items[link] = rij
        if nieuw or bij:
            self._save()
        return nieuw, bij

    def beslis(self, link: str, besluit: str, door: str = "") -> bool:
        """Pitchen of negeren. Onbekend besluit of onbekende link → False (fail-closed)."""
        link = (link or "").strip()
        if besluit not in BESLUITEN or link not in self._items:
            return False
        rij = self._items[link]
        rij["status"] = besluit
        rij["door"] = door or "onbekend"
        rij["besloten_op"] = time.time()
        self._save()
        return True

    # ── lezen (lock-vrij) ──
    def alle(self) -> list[dict]:
        """Alles, gesorteerd: open eerst, daarbinnen op prioriteit, daarbinnen nieuwste eerst.

        WAAROM OPEN EERST. Dit scherm is een werklijst, geen archief: wat je nog moet beoordelen
        hoort boven wat je al hebt afgehandeld. De beslissingen blijven staan — ze zijn het
        geheugen dat voorkomt dat dezelfde gids elke ronde terugkomt."""
        volgorde = {p: i for i, p in enumerate(PRIORITEITEN)}
        return sorted(self._items.values(),
                      key=lambda r: (r.get("status") != "open",
                                     volgorde.get(r.get("priority"), 9),
                                     -float(r.get("gevonden_op") or 0)))

    def telling(self) -> dict:
        rijen = self._items.values()
        return {"open": sum(1 for r in rijen if r.get("status") == "open"),
                "pursue": sum(1 for r in rijen if r.get("status") == "pursue"),
                "ignore": sum(1 for r in rijen if r.get("status") == "ignore")}


# ── De zoekopdracht: slot in de ene thread, werk in de andere ────────────────

def slot(data_dir: str) -> Werkslot:
    return Werkslot(os.path.join(data_dir, "linkbuilding.lock"))


def _fout_pad(data_dir: str) -> str:
    return os.path.join(data_dir, "linkbuilding.fout.json")


def laatste_fout(data_dir: str) -> dict | None:
    """De laatste mislukte poging, of None. Wordt gewist zodra er weer een zoektocht slaagt."""
    try:
        import json
        with open(_fout_pad(data_dir), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return None


def _noteer_fout(data_dir: str, fout: str) -> None:
    try:
        import json
        with open(_fout_pad(data_dir), "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "fout": fout[:400]}, fh)
    except OSError:
        log.warning("linkbuilding: fout niet te noteren", exc_info=True)


def _wis_fout(data_dir: str) -> None:
    try:
        os.remove(_fout_pad(data_dir))
    except OSError:
        pass


def merken(context) -> list[str]:
    """De concurrentmerken waarop de skill rangschikt: de BEVESTIGDE uit `context.competitors`.

    KANDIDATEN TELLEN NIET MEE, en dat is geen strengheid maar dezelfde regel als overal in dit
    dorp: een kandidaat is een waarneming, bevestigen is een besluit. Ze meesturen zou dat besluit
    stilzwijgend nemen, en de prioriteit "hoog" ("deze gids noemt je concurrenten maar jou niet")
    zou dan op een merk kunnen leunen dat niemand ooit als concurrent heeft aangewezen."""
    comp = getattr(context, "competitors", None)
    if comp is None:
        return []
    try:
        return [b for b in comp.confirmed() if b]
    except Exception:                                    # noqa: BLE001 — een lege lijst is bruikbaar
        log.warning("linkbuilding: concurrenten niet te lezen", exc_info=True)
        return []


def sleutel_aanwezig(context) -> bool:
    """Is er een SerpAPI-sleutel? De skill heeft hem nodig (`required_env`).

    HET SCHERM VRAAGT DIT VOORAF, zodat een ontbrekende sleutel een zin op het scherm wordt in
    plaats van een knop die altijd faalt. De skill blijft zelf ook fail-closed — dit is de
    vriendelijke helft, niet de poort."""
    return bool((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
                or os.getenv("SERPAPI_API_KEY"))


def zoek_en_bewaar(store: LinkTargetQueue, context, registry, *, topic: str = "") -> dict:
    """Draai de skill en schrijf de vondsten weg. Geeft het skill-antwoord terug.

    GEEN NIEUWE ZOEKLOGICA: dit roept `linkbuilding_targets` aan zoals elke andere aanroeper, met
    de merken uit `context.competitors` en het onderwerp uit het formulier of de config. Wat deze
    functie toevoegt is de OPSLAG — de skill is bewust side-effect-free."""
    skill = registry.get("linkbuilding_targets") if registry else None
    if skill is None:
        return {"ok": False, "error": "de skill linkbuilding_targets is niet geregistreerd"}
    payload = {"brands": merken(context)}
    if (topic or "").strip():
        payload["topic"] = topic.strip()
    uit = skill.run(payload, context) or {}
    if uit.get("ok") and uit.get("targets"):
        store.zet_vondsten(uit["targets"], uit.get("query") or topic)
    return uit


def start_achtergrond(data_dir: str, context, registry, *, topic: str = "",
                      door: str = "") -> bool:
    """Pak het slot in DEZE thread, zoek in een andere. False = er liep er al een.

    HET SLOT VÓÓR DE THREAD — zie de kop van dit bestand. De store wordt IN de thread gebouwd: hij
    leest een bestand, en die toestand hoort bij de thread die hem gebruikt."""
    import threading

    if not slot(data_dir).pak(door or "de knop"):
        return False

    def _werk() -> None:
        try:
            store = LinkTargetQueue(os.path.join(data_dir, "link_targets.json"))
            uit = zoek_en_bewaar(store, context, registry, topic=topic)
            if not uit.get("ok"):
                _noteer_fout(data_dir, str(uit.get("error") or "onbekende fout"))
            else:
                _wis_fout(data_dir)
        except Exception as exc:                          # noqa: BLE001
            log.warning("linkbuilding: zoekopdracht mislukt: %s", exc, exc_info=True)
            _noteer_fout(data_dir, f"{type(exc).__name__}: {exc}")
        finally:
            slot(data_dir).geef()

    threading.Thread(target=_werk, name="linkbuilding", daemon=True).start()
    return True
