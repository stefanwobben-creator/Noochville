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
        kleur, uitleg = "rood", f"HTTP {code or 'geen antwoord'}"
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


def run_en_bewaar(st, ctx, registry, *, url: str = "", doel: str = "live") -> tuple[dict, list[dict]]:
    """De CLI- en (later) klok-ingang: draai, vergelijk met de vorige run van HETZELFDE doel, bewaar."""
    staat = SiteAuditStaat(pad_voor(getattr(st, "dd", "") or getattr(ctx, "data_dir", "data"), doel))
    vorige = staat.laatste()
    snapshot = draai(st, ctx, registry, url=url, doel=doel)
    wissels = verschil(vorige, snapshot)
    snapshot["wissels"] = wissels
    staat.noteer(snapshot)
    return snapshot, wissels
