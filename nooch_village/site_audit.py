"""Site audit — de lampjes van nooch.earth op één scherm, met de uitleg erachter.

Aanleiding (11 september 2026). Stefan, na de eerste Lighthouse-run: "ik denk dat dit een soort
tooling moet zijn: een wekelijkse of dagelijkse check, een soort site audit: veiligheidslekken,
claims die niet mogen, is de HTML semantisch, mobile friendly. Automatisch, met een metric in
groen, oranje, rood, en als je klikt een uitleg."

Dit is de SAMENSTELLING, niet een nieuwe meting. Elke check bestaat als losse skill of bron en
blijft dat; hier worden hun uitkomsten met expliciete drempels vertaald naar een lampje (kleur,
waarde, uitleg, bevindingen, eigenaar) en per run als snapshot bewaard, zodat je het verloop ziet
en niet alleen de stand. Wat er vandaag in zit:

- **bereikbaar** — `site_health` (echte GET): 200 = groen, 3xx/4xx = oranje, 5xx/storing = rood.
- **snelheid, toegankelijkheid, best practices, seo** — `mobiel_audit` (Lighthouse via
  PageSpeed, mobiel), met Google's eigen banden: 90+ groen, 50 tot 89 oranje, onder 50 rood. In
  de uitleg van snelheid staan LCP, CLS en TBT met de Core-Web-Vitals-drempels.
- **claims** — de werklijst van de claims-database (het eigendom van Compliance): een rood
  oordeel dat nog niet live is = rood, alleen oranje = oranje, alles live = groen; met de datum
  van de laatste wekelijkse site-scan erbij, en "over tijd" als die te oud is.

Wat er bewust NIET in zit, met de reden: veiligheid (scope 46, na verificatie van de bron) en het
zoeken naar nieuwe best practices (scope 48; een skill mag zichzelf geen checks geven, harde regel
10). De weekklok is scope 47: nu draait dit op afroep (`village site_audit`), en het scherm zegt
wanneer de laatste run was in plaats van te doen alsof het vanzelf ging.

Drie regels:
1. **Een check die faalt wordt grijs, met de reden.** Nooit groen omdat er niets gemeten is, en de
   andere lampjes gaan gewoon door.
2. **Drempels staan hier, één keer, met bron.** Niet in de view en niet in de skill.
3. **De snapshot is append-only** (zoals de draaistaat): een lampje dat van kleur wisselt is het
   signaal, en dat kun je alleen zien als de vorige run bewaard is.
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("village.site_audit")

#: Twee doelen, twee reeksen. `live` is de shop zoals klanten hem krijgen (de wekelijkse reeks en de
#: lampjes); `dev` is het preview-thema op afroep (`village site_audit --dev`), met een eigen bestand,
#: zodat een dev-run nooit als "gewisseld" naast een live-run komt te staan.
DOELEN = ("live", "dev")
BESTAND = "site_audit.jsonl"
BESTAND_DEV = "site_audit_dev.jsonl"
KLEUREN = ("groen", "oranje", "rood", "grijs")
#: Hoeveel runs het scherm als verloop toont.
VERLOOP = 12

#: Drempels, met bron. Lighthouse-categorieën: Google's scorebanden. Core Web Vitals: web.dev
#: (LCP goed ≤ 2,5 s, matig ≤ 4 s; CLS goed ≤ 0,1, matig ≤ 0,25). TBT: Lighthouse' eigen banden
#: (goed ≤ 200 ms, slecht > 600 ms).
LIGHTHOUSE_GROEN, LIGHTHOUSE_ORANJE = 90, 50
LCP_GROEN_MS, LCP_ORANJE_MS = 2500, 4000
CLS_GROEN, CLS_ORANJE = 0.1, 0.25
TBT_GROEN_MS, TBT_ORANJE_MS = 200, 600
#: Een claims-scan ouder dan dit is "over tijd" (twee weekperiodes, zoals role_rhythm).
CLAIMS_SCAN_MAX_WEKEN = 2
#: Bevindingen per lampje op het scherm; de volledige lijst staat in de bron (skill-uitvoer, /claims).
MAX_BEVINDINGEN = 16


def pad_voor(data_dir: str, doel: str = "live") -> str:
    return os.path.join(data_dir, BESTAND_DEV if doel == "dev" else BESTAND)


# ── drempels ─────────────────────────────────────────────────────────────────

def lamp_score(score) -> str:
    if score is None:
        return "grijs"
    return "groen" if score >= LIGHTHOUSE_GROEN else "oranje" if score >= LIGHTHOUSE_ORANJE else "rood"


def lamp_lcp(ms) -> str:
    if ms is None:
        return "grijs"
    return "groen" if ms <= LCP_GROEN_MS else "oranje" if ms <= LCP_ORANJE_MS else "rood"


def lamp_cls(v) -> str:
    if v is None:
        return "grijs"
    return "groen" if v <= CLS_GROEN else "oranje" if v <= CLS_ORANJE else "rood"


def lamp_tbt(ms) -> str:
    if ms is None:
        return "grijs"
    return "groen" if ms <= TBT_GROEN_MS else "oranje" if ms <= TBT_ORANJE_MS else "rood"


def _ergste(kleuren) -> str:
    rang = {"rood": 3, "oranje": 2, "groen": 1, "grijs": 0}
    return max(kleuren, key=lambda k: rang.get(k, 0)) if kleuren else "grijs"


def _lamp(sleutel: str, naam: str, kleur: str, *, waarde: str = "", uitleg: str = "",
          bevindingen: list | None = None, eigenaar: str = "", bron: str = "") -> dict:
    return {"sleutel": sleutel, "naam": naam, "kleur": kleur if kleur in KLEUREN else "grijs",
            "waarde": waarde, "uitleg": uitleg, "bevindingen": list(bevindingen or [])[:MAX_BEVINDINGEN],
            "eigenaar": eigenaar, "bron": bron}


# ── de checks ────────────────────────────────────────────────────────────────

def _check_bereikbaar(registry, ctx, url: str, eigenaar: str) -> list[dict]:
    skill = registry.get("site_health") if registry else None
    if skill is None:
        return [_lamp("bereikbaar", "Bereikbaar", "grijs", uitleg="skill site_health niet geregistreerd",
                      eigenaar=eigenaar, bron="site_health")]
    try:
        r = skill.run({"url": url}, ctx) or {}
    except Exception as exc:                          # noqa: BLE001
        return [_lamp("bereikbaar", "Bereikbaar", "rood", uitleg=f"niet bereikbaar: {type(exc).__name__}: {exc}"[:200],
                      eigenaar=eigenaar, bron="site_health")]
    code = int(r.get("status_code") or 0)
    if 200 <= code < 300:
        kleur, uitleg = "groen", f"HTTP {code}, titel “{r.get('title') or '?'}”, {int(r.get('bytes') or 0) // 1024} KiB"
    elif 300 <= code < 500:
        kleur, uitleg = "oranje", f"HTTP {code}: de pagina antwoordt, maar niet met inhoud"
    else:
        # Sinds scope 58 vangt site_health een netwerkfout zelf (`error` + status_code 0); de reden
        # hoort op het lampje, niet alleen in het skill-resultaat.
        kleur, uitleg = "rood", f"HTTP {code or 'geen antwoord'}" + (f": {str(r.get('error'))[:160]}" if r.get("error") else "")
    return [_lamp("bereikbaar", "Bereikbaar", kleur, waarde=str(code or "-"), uitleg=uitleg,
                  eigenaar=eigenaar, bron="site_health")]


def _check_mobiel(registry, ctx, url: str, eigenaar: str) -> list[dict]:
    """Vier lampjes uit één Lighthouse-run. Faalt de run, dan vier keer grijs met dezelfde reden:
    dat is eerlijker dan één grijs lampje 'mobiel' waarachter vier metingen schuilgaan."""
    namen = (("snelheid", "Snelheid (mobiel)", "performance"),
             ("toegankelijkheid", "Toegankelijkheid", "accessibility"),
             ("best_practices", "Best practices", "best_practices"),
             ("seo", "SEO", "seo"))
    skill = registry.get("mobiel_audit") if registry else None
    if skill is None:
        return [_lamp(s, n, "grijs", uitleg="skill mobiel_audit niet geregistreerd", eigenaar=eigenaar,
                      bron="mobiel_audit") for s, n, _ in namen]
    try:
        r = skill.run({"url": url}, ctx) or {}
    except Exception as exc:                          # noqa: BLE001
        r = {"error": f"{type(exc).__name__}: {exc}"}
    if not r.get("ok"):
        reden = str(r.get("error") or "geen uitkomst")[:200]
        return [_lamp(s, n, "grijs", uitleg=reden, eigenaar=eigenaar, bron="mobiel_audit") for s, n, _ in namen]
    scores = r.get("scores") or {}
    lab = r.get("lab") or {}
    # Een preview-URL waarvan de skill het preview-thema niet in de requests terugzag: dan is het
    # mogelijk gewoon live gemeten. Dat hoort op alle vier de lampjes, niet in een logregel.
    pv = r.get("preview") or {}
    let_op = (" Let op: preview-thema niet herkend in de netwerkrequests; mogelijk is live gemeten."
              if pv.get("gevraagd") and not pv.get("herkend") else "")
    per_cat: dict[str, list] = {}
    for b in r.get("bevindingen") or []:
        per_cat.setdefault(b.get("categorie"), []).append(
            f"{b.get('titel')}" + (f" ({b.get('weergave')})" if b.get("weergave") else ""))
    uit = []
    for sleutel, naam, cat in namen:
        score = scores.get(cat)
        uitleg = (f"Lighthouse {cat.replace('_', ' ')} {score if score is not None else '?'} van 100 "
                  f"(groen vanaf {LIGHTHOUSE_GROEN}, rood onder {LIGHTHOUSE_ORANJE}).{let_op}")
        bev = list(per_cat.get(cat, []))
        if cat == "performance":
            lcp, cls, tbt = (lab.get("lcp_ms") or {}), (lab.get("cls") or {}), (lab.get("tbt_ms") or {})
            delen = [f"LCP {lcp.get('weergave') or '?'} ({lamp_lcp(lcp.get('waarde'))}, goed ≤ 2,5 s)",
                     f"CLS {cls.get('weergave') or '?'} ({lamp_cls(cls.get('waarde'))}, goed ≤ 0,1)",
                     f"TBT {tbt.get('weergave') or '?'} ({lamp_tbt(tbt.get('waarde'))}, goed ≤ 200 ms)"]
            uitleg += " " + " · ".join(delen) + "."
            # Volgorde van de bevindingen: eerst wat je kunt DOEN (de LCP-checklist van Lighthouse 13:
            # niet "LCP is traag" maar "de banner staat op loading=lazy"; dan de kansen met gemeten
            # winst), daarna de falende audits. De lijst is begrensd, dus het bruikbaarste vooraan.
            voorop: list[str] = []
            le = r.get("lcp_element") or {}
            if le.get("element"):
                from nooch_village.skills_impl.mobiel_audit import _fase_zin   # één zin, één plek
                uitleg += f" LCP-element: {le['element']}{_fase_zin(le)}."
                voorop += [f"LCP-afbeelding: {a}" for a in le.get("aanwijzingen") or []]
            v = r.get("veld") or {}
            uitleg += (" Velddata (echte gebruikers, p75): " + str(v.get("oordeel") or "?") + "."
                       if v.get("bron") else " Geen velddata van echte gebruikers (te weinig Chrome-verkeer).")
            kans_titels = set()
            for k in r.get("kansen") or []:
                if k.get("winst_ms") or k.get("winst_bytes"):
                    w = f"{k['winst_ms']} ms" if k.get("winst_ms") else f"{k['winst_bytes'] // 1024} KiB"
                    voorop.append(f"Kans: {k['titel']} ({w})")
                    kans_titels.add(k["titel"])
            # een audit die al als kans staat (met winst) niet nog eens als kale titel
            bev = voorop + [b for b in bev if b.split(" (")[0] not in kans_titels]
        uit.append(_lamp(sleutel, naam, lamp_score(score), waarde=str(score if score is not None else "-"),
                         uitleg=uitleg, bevindingen=bev, eigenaar=eigenaar, bron="mobiel_audit"))
    return uit


def _check_claims(st, data_dir: str, records) -> list[dict]:
    """De claims-werklijst is de waarheid van Compliance; wij lezen hem, we oordelen niet opnieuw."""
    eigenaar = ""
    try:
        from nooch_village import claims_board
        eigenaar = claims_board.claims_rol(records) or ""
    except Exception:                                 # noqa: BLE001
        pass
    try:
        from nooch_village import claims_db
        db = claims_db.load(data_dir=data_dir)
    except Exception as exc:                          # noqa: BLE001
        return [_lamp("claims", "Claims (EmpCo)", "grijs", uitleg=f"claims-database onleesbaar: {exc}"[:200],
                      eigenaar=eigenaar, bron="claims_db")]
    wl = db.get("werklijst") or []
    open_ = [i for i in wl if str(i.get("status") or "open") != "live"]
    rood = [i for i in open_ if i.get("oordeel") == "red"]
    oranje = [i for i in open_ if i.get("oordeel") == "orange"]
    kleur = "rood" if rood else "oranje" if oranje else "groen"
    handhaving = ((db.get("meta") or {}).get("regelgeving") or {}).get("empco", "")
    uitleg = (f"{len(wl)} claims op de werklijst: {len(rood)} rood en {len(oranje)} oranje nog niet live, "
              f"{len(wl) - len(open_)} live.")
    if handhaving:
        uitleg += f" {handhaving}."
    # De laatste wekelijkse site-scan: wanneer, en of dat te lang geleden is.
    try:
        from nooch_village.skills_impl.claims_site_scan import laatste_run
        from nooch_village.role_rhythm import _periodes_geleden
        run = laatste_run(data_dir)
        if run.get("at"):
            achter = _periodes_geleden(run.get("last_week", ""), "week")
            uitleg += f" Laatste site-scan: {time.strftime('%-d %b %Y', time.localtime(float(run['at'])))}"
            uitleg += f", {achter} weken geleden: over tijd." if achter >= CLAIMS_SCAN_MAX_WEKEN else "."
        else:
            uitleg += " De wekelijkse site-scan heeft nog niet gedraaid."
    except Exception:                                 # noqa: BLE001
        pass
    bev = [f"{'🔴' if i.get('oordeel') == 'red' else '🟠'} {str(i.get('claim') or '')[:90]} [{i.get('status') or 'open'}]"
           for i in rood + oranje]
    return [_lamp("claims", "Claims (EmpCo)", kleur, waarde=f"{len(rood)}/{len(oranje)}", uitleg=uitleg,
                  bevindingen=bev, eigenaar=eigenaar, bron="claims_db")]


# ── de run ───────────────────────────────────────────────────────────────────

class GeenDevUrl(ValueError):
    """`--dev` zonder `mobiel_audit_dev_url`: niets meten, niets bewaren, wél zeggen wat er mist."""


def _url(ctx, doel: str = "live") -> str:
    from nooch_village.skills_impl.mobiel_audit import DEFAULT_URL
    settings = getattr(ctx, "settings", {}) or {}
    if doel == "dev":
        url = str(settings.get("mobiel_audit_dev_url") or "").strip()
        if not url:
            raise GeenDevUrl("geen mobiel_audit_dev_url in config/settings.ini: plak daar de share-preview-link "
                             "van het thema (https://nooch.earth/?preview_theme_id=…)")
        return url
    return str(settings.get("mobiel_audit_url") or DEFAULT_URL).strip()


def draai(st, ctx, registry, *, url: str = "", eigenaar_site: str = "", doel: str = "live") -> dict:
    """Eén audit-run: alle checks, elk fail-soft, één snapshot. Geeft de snapshot terug."""
    if doel not in DOELEN:
        raise ValueError(f"onbekend doel {doel!r}; kies uit {DOELEN}")
    url = url or _url(ctx, doel)
    if not eigenaar_site:
        from nooch_village.cockpit2_util import WEBSITE_DEVELOPER_ROLE   # één plek voor dat id
        eigenaar_site = WEBSITE_DEVELOPER_ROLE
    t0 = time.time()
    lampjes = []
    lampjes += _check_bereikbaar(registry, ctx, url, eigenaar_site)
    lampjes += _check_mobiel(registry, ctx, url, eigenaar_site)
    lampjes += _check_claims(st, getattr(st, "dd", "") or getattr(ctx, "data_dir", ""), getattr(st, "records", None))
    snapshot = {"ts": time.time(), "datum": time.strftime("%Y-%m-%d"), "url": url, "doel": doel,
                "lampjes": lampjes, "totaal": _ergste([l["kleur"] for l in lampjes if l["kleur"] != "grijs"]),
                "duur_s": round(time.time() - t0, 1)}
    return snapshot


class SiteAuditStaat:
    """Append-only: elke run één regel. Lezen is alles; het verloop en het verschil zijn afgeleid."""

    def __init__(self, pad: str):
        self.pad = pad

    def noteer(self, snapshot: dict) -> None:
        os.makedirs(os.path.dirname(self.pad) or ".", exist_ok=True)
        with open(self.pad, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

    def alles(self) -> list[dict]:
        try:
            with open(self.pad, encoding="utf-8") as f:
                uit = []
                for regel in f:
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue
                return uit
        except FileNotFoundError:
            return []

    def laatste(self) -> dict | None:
        alle = self.alles()
        return alle[-1] if alle else None

    def verloop(self, n: int = VERLOOP) -> list[dict]:
        return self.alles()[-n:]


def verschil(vorige: dict | None, nu: dict) -> list[dict]:
    """Welke lampjes van kleur wisselden sinds de vorige run. Dat is het signaal; de stand is
    het scherm. Grijs telt niet als wissel (niet gemeten is geen verandering)."""
    if not vorige:
        return []
    oud = {l["sleutel"]: l["kleur"] for l in vorige.get("lampjes") or []}
    uit = []
    for l in nu.get("lampjes") or []:
        was = oud.get(l["sleutel"])
        if was and was != l["kleur"] and "grijs" not in (was, l["kleur"]):
            uit.append({"sleutel": l["sleutel"], "naam": l["naam"], "was": was, "nu": l["kleur"]})
    return uit


class ScanDraaitAl(RuntimeError):
    """Er loopt al een scan. Niets gedaan, niets bewaard, en wél gezegd sinds wanneer."""


#: Na hoeveel tijd een slot als achtergebleven geldt. Een run duurt 20-60 seconden (Lighthouse);
#: een kwartier is ruim genoeg om een trage run niet af te kappen en kort genoeg om een proces dat
#: halverwege sneuvelde niet tot de volgende deploy in de weg te laten liggen. Zonder deze grens is
#: één harde crash genoeg om de knop voorgoed dood te leggen.
SLOT_VERVALT_S = 15 * 60


def slot_pad(data_dir: str, doel: str = "live") -> str:
    return os.path.join(data_dir, f"site_audit_{doel}.lock")


def slot_staat(data_dir: str, doel: str = "live") -> dict | None:
    """Wie draait er, sinds wanneer? None = vrij. Een vervallen slot leest als vrij."""
    try:
        with open(slot_pad(data_dir, doel), encoding="utf-8") as fh:
            d = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return None
    if time.time() - float(d.get("sinds") or 0) > SLOT_VERVALT_S:
        return None
    return d


def _neem_slot(data_dir: str, doel: str, door: str) -> bool:
    """Atomair pakken: `O_CREAT | O_EXCL` slaagt bij precies één van twee gelijktijdige pogingen.

    GEEN "bestaat het al?"-CHECK GEVOLGD DOOR SCHRIJVEN, want dat is precies de race die dit moet
    afvangen: twee kliks binnen een milliseconde zien allebei niets en starten allebei."""
    pad = slot_pad(data_dir, doel)
    if slot_staat(data_dir, doel) is None:
        try:
            os.remove(pad)                       # vervallen slot van een gesneuvelde run
        except OSError:
            pass
    try:
        fd = os.open(pad, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    except OSError:
        return True                              # geen schrijfrechten: liever draaien dan blokkeren
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"sinds": time.time(), "door": door}, fh)
    return True


def _geef_slot(data_dir: str, doel: str) -> None:
    try:
        os.remove(slot_pad(data_dir, doel))
    except OSError:
        pass


def run_en_bewaar(st, ctx, registry, *, url: str = "", doel: str = "live",
                  door: str = "") -> tuple[dict, list[dict]]:
    """De ingang voor CLI, klok én knop: draai, vergelijk met de vorige run van HETZELFDE doel, bewaar.

    HET SLOT ZIT HIER EN NIET BIJ DE AANROEPER (28 september 2026). Sinds de knop op de
    handboek-pagina bestaat er een derde ingang, en een slot per ingang beschermt alleen tegen
    zichzelf: een klik tijdens een CLI-run zou dan gewoon een tweede scan starten. Eén poort voor
    alle drie, dus ook de klok van scope 47 krijgt hem gratis.

    TWEE SCANS TEGELIJK IS NIET "DUBBEL WERK" MAAR VUILE DATA: allebei schrijven ze een snapshot in
    dezelfde append-only reeks, en `verschil()` vergelijkt met de LAATSTE — twee runs op hetzelfde
    moment leveren dus een "wissel" op tussen twee metingen van dezelfde minuut."""
    data_dir = getattr(st, "dd", "") or getattr(ctx, "data_dir", "data")
    if not _neem_slot(data_dir, doel, door or "onbekend"):
        bezet = slot_staat(data_dir, doel) or {}
        raise ScanDraaitAl(f"er loopt al een scan [{doel}], gestart door "
                           f"{bezet.get('door') or 'onbekend'}")
    try:
        return _draai_met_slot(st, ctx, registry, url=url, doel=doel, data_dir=data_dir)
    finally:
        # ALTIJD TERUGGEVEN, ook als `draai` ontploft: een netwerkfout hoort de knop niet een kwartier
        # dood te leggen. De vervaltijd hierboven is het vangnet voor een proces dat er zelf niet
        # meer is om dit uit te voeren.
        _geef_slot(data_dir, doel)


def _draai_met_slot(st, ctx, registry, *, url: str, doel: str,
                    data_dir: str) -> tuple[dict, list[dict]]:
    """De run zelf, zonder slot-beheer — zodat de twee ingangen hetzelfde doen.

    Aparte functie omdat de knop het slot in de VERZOEK-thread pakt (anders zou een dubbelklik twee
    threads starten die pas binnenin ontdekken dat ze te laat zijn) en het pas in de WERK-thread
    weer loslaat."""
    staat = SiteAuditStaat(pad_voor(data_dir, doel))
    vorige = staat.laatste()
    snapshot = draai(st, ctx, registry, url=url, doel=doel)
    wissels = verschil(vorige, snapshot)
    snapshot["wissels"] = wissels
    staat.noteer(snapshot)
    _wis_fout(data_dir, doel)
    return snapshot, wissels


#: De pagina die de scanknop draagt, en het regeltje dat hem daar zet.
#:
#: WAAROM DIT EEN EENMALIGE DATA-WIJZIGING IS EN GEEN `if titel == …` IN DE VIEW. De knop verschijnt
#: op elke pagina die naar `/site-audit` VERWIJST — dat is dezelfde koppeling als bij de decision
#: coach, en om dezelfde reden: geen titel en geen artefact-id in de rendercode, want een titel is
#: een naam die iemand herschrijft. Maar dan moet die verwijzing er wel staan, en in het Website
#: Handboek stond hij niet.
#:
#: DE TITEL MAG HIER WÉL STAAN, want dit is een BESLUIT en geen regel: "de scanknop hoort in het
#: handboek" is precies zo'n keuze als de inclusies in `_COPY_STACK_ZAAD` ("een besluit dat je
#: afleidt uit een regel is geen besluit meer"). Hij staat één keer, in een zaai-functie, en niet in
#: de weg van de rendercode.
#:
#: EN HET IS OMKEERBAAR DOOR EEN MENS: haal de regel uit de pagina en de knop is weg. Dat is meer
#: dan een vlag in de data zou geven, want daar is geen scherm voor.
HANDBOEK_TITEL = "WEBSITE HANDBOEK"
_KNOP_REGEL = ("\n\n## Site audit\n\n"
               "The lights for reachability, speed, accessibility, SEO and claims of the live shop "
               "live on [Site audit](/site-audit). The **Run scan** button at the bottom of this "
               "page starts a fresh measurement (20-60 seconds).\n")


def zorg_voor_knop_verwijzing(store, *, titel: str = HANDBOEK_TITEL) -> str:
    """Zet één verwijzing naar de site audit in het handboek, zodat het de scanknop draagt.

    Idempotent, en met drie guards die hem klein houden: alleen een TOOL met precies deze titel,
    alleen als de verwijzing er nog niet staat, en alleen als er al tekst in staat — een lege
    pagina vullen is geen koppeling leggen maar schrijven, en dat is niet aan het dorp.

    Geeft het id terug als er iets is geschreven, anders "".
    """
    from nooch_village import artefacts

    for a in store.by_kind("tool", include_archived=True):
        if artefacts.norm_titel(a.title) != artefacts.norm_titel(titel):
            continue
        body = a.body or ""
        if "/site-audit" in body or not body.strip():
            return ""
        store.update(a.id, body=body.rstrip() + _KNOP_REGEL, actor_id="system",
                     actor_type="persona",
                     change_note="scanknop gekoppeld: verwijzing naar /site-audit toegevoegd")
        log.info("site audit: verwijzing toegevoegd aan %s (%s)", a.id, a.title)
        return a.id
    return ""


# ── De knop-ingang: pakken in de ene thread, draaien in de andere ────────────
#
# WAAROM NIET GEWOON SYNCHROON IN DE POST-HANDLER. `draai` doet echte netwerkchecks (een GET op de
# shop, een Lighthouse-run via PageSpeed) en duurt 20 tot 60 seconden. Een POST die zo lang open
# blijft staan geeft een pagina die hangt zonder te zeggen waarom, houdt een thread van de
# `ThreadingHTTPServer` bezet, en loopt tegen elke proxy-timeout aan die ertussen zit.

def _fout_pad(data_dir: str, doel: str) -> str:
    return os.path.join(data_dir, f"site_audit_{doel}.fout.json")


def laatste_fout(data_dir: str, doel: str = "live") -> dict | None:
    """De laatste mislukte poging, of None. Wordt gewist zodra er weer een run slaagt.

    WAAROM DIT BESTAAT: een scan die in de achtergrond sneuvelt is anders volkomen stil — het slot
    valt weg, de tijdstempel van de laatste run beweegt niet, en het scherm ziet er precies zo uit
    als vóór de klik. "Er is niets gebeurd" en "het is misgegaan" horen niet hetzelfde te lezen."""
    try:
        with open(_fout_pad(data_dir, doel), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return None


def _noteer_fout(data_dir: str, doel: str, fout: str) -> None:
    try:
        with open(_fout_pad(data_dir, doel), "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "fout": fout[:400]}, fh)
    except OSError:
        log.warning("site audit: fout niet te noteren", exc_info=True)


def _wis_fout(data_dir: str, doel: str) -> None:
    try:
        os.remove(_fout_pad(data_dir, doel))
    except OSError:
        pass


def start_achtergrond(data_dir: str, *, doel: str = "live", door: str = "",
                      url: str = "") -> bool:
    """Pak het slot in DEZE thread, draai de scan in een andere. False = er liep er al een.

    HET SLOT VÓÓR DE THREAD, en dat is de hele reden dat deze functie bestaat: zou de werk-thread
    hem pakken, dan starten twee kliks twee threads die allebei pas binnenin ontdekken dat ze te
    laat zijn — de tweede sterft dan stil, en de klikker krijgt twee keer "gestart" te zien.

    De stores worden IN de thread gebouwd, niet meegegeven: `_Stores` leest bestanden en die
    toestand hoort bij de thread die hem gebruikt, niet bij het verzoek dat hem startte."""
    import threading

    if not _neem_slot(data_dir, doel, door or "knop"):
        return False

    def _werk() -> None:
        try:
            from nooch_village.cockpit2 import _Stores, _context_of
            from nooch_village.registry_factory import shared_registry
            st = _Stores(data_dir)
            ctx = _context_of(data_dir)
            _draai_met_slot(st, ctx, shared_registry(), url=url, doel=doel, data_dir=data_dir)
        except Exception as exc:                          # noqa: BLE001
            # LOGGEN ÉN NOTEREN. Een achtergrondthread heeft geen scherm om op te vallen; zonder
            # dit tweede spoor is een mislukte scan niet van "nog niet geklikt" te onderscheiden.
            log.warning("site audit [%s] mislukt: %s", doel, exc, exc_info=True)
            _noteer_fout(data_dir, doel, f"{type(exc).__name__}: {exc}")
        finally:
            _geef_slot(data_dir, doel)

    threading.Thread(target=_werk, name=f"site-audit-{doel}", daemon=True).start()
    return True
