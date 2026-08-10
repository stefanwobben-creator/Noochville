"""founder_flow.py — de graduele-autonomie-trainingslus van de founder.

Geen checklist. Elke beslissing die de founder hier neemt is een **gelabeld voorbeeld**, en de
lus meet of de AI dat voorbeeld inmiddels reproduceert. Haalt de meting de lat, dan mag de taak
een trede klimmen; klimt hij, dan kost hij de founder minder minuten. Dat is de hele bedoeling:
de succesmetriek is niet "alles afgevinkt", maar "minder founder-minuten per week per taak".

Drie taken, drie rijpheidsniveaus die LOS van elkaar klimmen:

    A  jij beslist            (de AI kijkt mee, zwijgt)
    B  AI stelt voor, jij keurt
    C  AI doet, jij auditeert
    D  AI doet stil

## Twee harde ontwerpregels

**1. Blind-eerst op A/B.** Het AI-voorstel wordt wél berekend maar NIET getoond vóórdat de mens
zijn oordeel heeft vastgelegd. Twee redenen, en ze wegen allebei zwaar:
  - *automation bias* — een zichtbaar voorstel trekt het menselijke oordeel naar zich toe; je
    meet dan de invloed van de AI op de mens, niet de overeenstemming.
  - *schone labels* — een besmet label is geen trainingsdata maar een echo.
Op C/D draait het om: dáár is het voorstel de default en is de mens de controle. Behalve in de
auditsteekproef, die ook op C/D blind blijft — anders verdwijnt de enige schone meetreeks precies
op het moment dat drift het gevaarlijkst wordt.

**2. Correctie is één klik.** Even goedkoop als goedkeuren. Een correctie die duurder is dan
akkoord gaan, produceert stilzwijgende instemming en dus een te rooskleurige meting.

## De meting: alleen op de held-out steekproef

Een label telt pas mee voor promotie als het **blind** tot stand kwam: het voorstel bestond, maar
was niet zichtbaar. Dat is de held-out set. Labels waar het voorstel wél vooraf zichtbaar was
(C/D, niet-audit) worden geregistreerd en getoond, maar meten NIET mee — ze zijn besmet.

Daarom draagt elk label twee velden waar de opdracht er één noemt: `ai` (het voorstel, altijd
vastgelegd als het berekend kon worden) én `ai_getoond` (was het zichtbaar vóór de beslissing).
Zonder het eerste is promotie niet te meten; zonder het tweede is niet te zien of de meting schoon
is. "Ai-voorstel indien getoond" is dus `ai` mét `ai_getoond=True`.

De poort beslist op de ONDERGRENS van het Wilson-95%-interval, niet op het punt — hetzelfde
patroon (en dezelfde functie, `stats.wilson`) als de Stage-0-dismiss-precision. Bij dertig
beslissingen is 90% niet van 75% te onderscheiden; promoveren op het punt is promoveren op ruis.

## Opslag

- `data/founder_labels.jsonl` — append-only, één regel per gebeurtenis (claims_labels-patroon).
  Een label is een waarneming met een tijdstip, geen state die je muteert. Fail-soft: een label
  mag een klik nooit laten klappen.
- `data/founder_flow.json` — het huidige niveau per taak + de promotie-/demotie-historie.
- `config/founder_flow.json` — de lat per taak. Mens-bewerkbaar, net als `config/strategy.json`;
  niet via governance, want dit is een instelling van de founder over zijn eigen werk.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time

from nooch_village.stats import wilson
from nooch_village.util import JsonStore

log = logging.getLogger("village.founder_flow")

BESTAND = "founder_labels.jsonl"
NIVEAU_BESTAND = "founder_flow.json"
CONFIG_BESTAND = "founder_flow.json"

# ── De drie taken. Strikt deze drie; geen vierde erbij zonder expliciet besluit. ──────────────
RADAR = "radar_triage"
CLAIM = "claim_oordeel"
CONTENT = "content_goedkeuring"
TAKEN = (RADAR, CLAIM, CONTENT)

TAAK_LABEL = {
    RADAR: "Radar triage",
    CLAIM: "Claim judgement",
    CONTENT: "Content approval",
}

# Per taak de toegestane oordelen. Dit is tegelijk de sleutelruimte van de labels: een oordeel
# buiten deze set wordt geweigerd, zodat de meting nooit op typefouten telt.
#
# De radar-as is bewust veranderd van relevantie (keep/dismiss) naar NIEUWHEID. Reden: relevantie
# is een smaakoordeel dat per week verschuift, nieuwheid is een uitspraak over de wereld die je kunt
# nakijken — en het is het oordeel dat de founder feitelijk maakt als hij een signaal bekijkt
# ("hebben we dit al?"). De clustering en de bronnen-teller nemen de relevantie-vraag over: een
# onderwerp dat uit zeven bronnen komt is aantoonbaar relevant zonder dat iemand dat hoefde te vinden.
#
# Gevolg voor de meting, en dat is met opzet: labels van vóór deze omslag dragen 'keep'/'dismiss',
# vallen dus buiten `OORDELEN[RADAR]` en tellen NIET meer mee in de overeenstemming. Ze blijven in de
# append-only log staan (er wordt niets herschreven), maar het zou onzin zijn om een relevantie-
# oordeel af te zetten tegen een nieuwheids-voorstel. De radar-teller begint dus opnieuw bij nul.
OORDELEN = {
    RADAR: ("nieuw", "bekend"),
    CLAIM: ("bewijs", "fix", "scientist"),
    CONTENT: ("publiceer", "corrigeer"),
}

OORDEEL_LABEL = {
    "nieuw": "new to us", "bekend": "we already have this",
    "bewijs": "bank evidence", "fix": "fix copy", "scientist": "to Scientist",
    "publiceer": "approve", "corrigeer": "correct",
}

NIVEAUS = ("A", "B", "C", "D")
NIVEAU_UITLEG = {
    "A": "you decide — the AI watches in silence",
    "B": "the AI proposes, you judge (blind first)",
    "C": "the AI acts, you audit afterwards",
    "D": "the AI acts silently — only the audit sample reaches you",
}

# ── De lat per taak (defaults; overschrijfbaar in config/founder_flow.json) ───────────────────
# `lat`       — vereiste ondergrens van de overeenstemming (Wilson-95%) vóór promotie.
# `min_n`     — minimaal aantal held-out labels; onder dit aantal zegt een percentage niets.
# `venster`   — hoeveel van de recentste held-out labels meetellen (drift zichtbaar houden).
# `audit_pct` — welk deel van de items op C/D blind aan de mens wordt voorgelegd.
# `dag_cap`   — hoeveel items de dagelijkse (korte) ronde per taak toont; de weekronde toont alles.
#
# De claim- en content-lat liggen hoger dan de radar-lat: een verkeerd weggeveegd radar-signaal
# kost een gemiste kans, een verkeerd beoordeelde claim of gepubliceerde tekst kost een
# handhavingsrisico. De prijs van een fout hoort in de lat te zitten, niet in goede bedoelingen.
# `cluster_drempel` en `cluster_venster_dagen` horen bij de radar-taak maar zijn GEEN poort: de
# clustering en de bronnen-teller zijn een berekening, geen oordeel, en klimmen dus geen tredes.
# Ze staan hier omdat de founder ze op één plek wil kunnen bijstellen. 0.0 = de default van
# `radar_clusters` (die kent het verschil tussen de semantische en de lexicale drempel).
_DEFAULTS = {
    RADAR: {"lat": 0.85, "min_n": 30, "venster": 60, "audit_pct": 20, "dag_cap": 5,
            "cluster_drempel": 0.0, "cluster_venster_dagen": 30},
    CLAIM: {"lat": 0.90, "min_n": 20, "venster": 60, "audit_pct": 25, "dag_cap": 3},
    CONTENT: {"lat": 0.90, "min_n": 15, "venster": 60, "audit_pct": 30, "dag_cap": 3},
}

# Een item dat langer dan dit open stond telt niet als "besteed" — dan lag het tabblad open.
# Zonder plafond maakt één vergeten tab de founder-minuten van een hele week onleesbaar.
_MAX_SECONDEN = 300.0


# ── Instellingen ─────────────────────────────────────────────────────────────────────────────

def config_pad(data_dir: str) -> str:
    """`config/founder_flow.json` naast `config/strategy.json` — mens-bewerkbaar, in git."""
    return os.path.join(data_dir, "..", "config", CONFIG_BESTAND)


def instellingen(data_dir: str, taak: str = "") -> dict:
    """De lat per taak: defaults, overschreven door config/founder_flow.json waar aanwezig.

    Fail-soft naar de defaults: een kapot configbestand mag het scherm niet slopen, maar mag de
    lat ook niet stiekem verlagen — daarom vullen we alleen aan, we vervangen nooit een default
    door iets onleesbaars."""
    uit = {t: dict(v) for t, v in _DEFAULTS.items()}
    try:
        with open(config_pad(data_dir), encoding="utf-8") as f:
            rauw = json.load(f)
        for t in TAKEN:
            for sleutel, waarde in (rauw.get(t) or {}).items():
                if sleutel in uit[t] and isinstance(waarde, (int, float)):
                    uit[t][sleutel] = waarde
    except FileNotFoundError:
        pass
    except Exception as e:                           # noqa: BLE001 — weergave mag nooit breken
        log.warning("founder_flow-config onleesbaar (defaults blijven gelden): %s", e)
    return uit[taak] if taak else uit


# ── De labels: append-only, één regel per gebeurtenis ────────────────────────────────────────

def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def leg_vast(data_dir: str, *, taak: str, item: str, mens: str | None, ai: str | None = None,
             ai_getoond: bool = False, niveau: str = "A", door: str = "", seconden: float = 0.0,
             correctie: bool = False, audit: bool = False, titel: str = "") -> dict | None:
    """Leg één gebeurtenis vast. Geeft het record terug, of None bij een ongeldige invoer.

    `mens=None` betekent: de AI heeft dit item zelf afgehandeld (niveau C/D). Zo'n regel is geen
    label van een menselijk oordeel, maar hoort wél in dezelfde stroom — anders is "welk aandeel
    nam de AI over" niet af te leiden uit één bron. De meetfuncties filteren erop.

    Fail-soft: een mislukte schrijf mag een klik nooit breken (claims_labels-patroon)."""
    if taak not in TAKEN or not (item or "").strip():
        log.warning("founder-label NIET vastgelegd: onbekende taak %r of leeg item", taak)
        return None
    if mens is not None and mens not in OORDELEN[taak]:
        log.warning("founder-label NIET vastgelegd: oordeel %r hoort niet bij %s", mens, taak)
        return None
    if ai is not None and ai not in OORDELEN[taak]:
        ai = None                                    # onbekend voorstel telt als "geen voorstel"
    rij = {"taak": taak, "item": str(item)[:200], "mens": mens, "ai": ai,
           "ai_getoond": bool(ai_getoond), "niveau": niveau if niveau in NIVEAUS else "A",
           "audit": bool(audit), "correctie": bool(correctie),
           "door": door or ("ai" if mens is None else "?"),
           "seconden": round(max(0.0, min(float(seconden or 0.0), _MAX_SECONDEN)), 1),
           "titel": (titel or "")[:160], "ts": time.time()}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(rij, ensure_ascii=False) + "\n")
    except Exception as e:                           # noqa: BLE001 — labelen mag een klik nooit breken
        log.warning("founder-label niet weggeschreven: %s", e)
        return None
    log.info("🏷 founder-label [%s] %s → mens=%s ai=%s (niveau %s)",
             taak, rij["item"], mens, ai, rij["niveau"])
    return rij


def alle(data_dir: str) -> list[dict]:
    """Alle regels, oudste eerst. Kapotte regels worden overgeslagen, niet fataal."""
    uit: list[dict] = []
    try:
        with open(pad(data_dir), encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = json.loads(regel)
                except ValueError:
                    continue
                if isinstance(rij, dict) and rij.get("taak") in TAKEN:
                    uit.append(rij)
    except FileNotFoundError:
        return []
    except Exception as e:                           # noqa: BLE001
        log.warning("founder-labelbestand onleesbaar: %s", e)
        return []
    return uit


def beoordeelde_items(labels: list[dict], taak: str) -> set[str]:
    """Elk item waarover al iets is vastgelegd (mens óf AI) — de wachtrij toont het niet opnieuw."""
    return {r["item"] for r in labels if r.get("taak") == taak and r.get("item")}


def laatste_per_item(labels: list[dict], taak: str) -> dict[str, dict]:
    """Het meest recente record per item — de stand van zaken, inclusief correcties."""
    uit: dict[str, dict] = {}
    for r in sorted((x for x in labels if x.get("taak") == taak), key=lambda x: x.get("ts", 0)):
        uit[r["item"]] = r
    return uit


# ── Blind-eerst en de auditsteekproef ────────────────────────────────────────────────────────

def in_auditsteekproef(taak: str, item: str, audit_pct: float) -> bool:
    """Hoort dit item in de blinde auditsteekproef?

    Deterministisch uit een hash van (taak, item) — géén random. Twee redenen: een item mag niet
    van steekproef wisselen tussen twee page-loads (dan lekt het voorstel alsnog), en de keuze
    moet reproduceerbaar zijn bij het naspelen van de log."""
    pct = max(0.0, min(100.0, float(audit_pct or 0)))
    if pct <= 0:
        return False
    h = int(hashlib.sha1(f"{taak}:{item}".encode("utf-8")).hexdigest()[:8], 16)
    return (h % 100) < pct


def toont_voorstel_vooraf(niveau: str, audit: bool) -> bool:
    """De blind-eerst-regel op één plek.

    A/B → nooit vooraf (de mens legt eerst vast, daarna komt de onthulling).
    C/D → wél vooraf, want daar is het voorstel de default en is de mens de controle —
    behalve in de auditsteekproef, die blind blijft zodat drift meetbaar blijft."""
    if niveau not in ("C", "D"):
        return False
    return not audit


def ai_handelt_zelf(niveau: str, audit: bool) -> bool:
    """Mag de lus dit item zonder mens afhandelen? Alleen op C/D en nooit in de auditsteekproef."""
    return niveau in ("C", "D") and not audit


# ── De meting ────────────────────────────────────────────────────────────────────────────────

def held_out(labels: list[dict], taak: str) -> list[dict]:
    """De schone meetreeks: een menselijk oordeel, met een berekend voorstel dat NIET vooraf
    zichtbaar was, en geen correctie-op-een-onthulling. Alles wat besmet is valt hier af."""
    return [r for r in labels
            if r.get("taak") == taak
            and r.get("mens") in OORDELEN[taak]
            and r.get("ai") in OORDELEN[taak]
            and not r.get("ai_getoond")
            and not r.get("correctie")]


def overeenstemming(labels: list[dict], taak: str, venster: int = 60,
                    sinds: float = 0.0) -> dict:
    """Overeenstemming tussen AI-voorstel en menselijk oordeel op de held-out steekproef.

    Geeft {n, akkoord, ratio, lo, hi}: het aantal meetbare labels in het venster, hoeveel
    daarvan overeenkwamen, de puntschatting, en het Wilson-95%-interval. `lo` is de waarde
    waarop de promotiepoort beslist — nooit `ratio`.

    `sinds` begrenst de reeks aan de onderkant (alleen labels ná dat tijdstip). De demotie-poort
    zet daar het moment van de laatste tree-wissel in: na een terugval hoor je het nieuwe niveau
    op nieuw bewijs te beoordelen, niet op de metingen die de terugval veroorzaakten. Zonder die
    grens zou één slechte reeks een taak in opeenvolgende klikken helemaal naar beneden trappen."""
    rijen = sorted((r for r in held_out(labels, taak) if r.get("ts", 0) > sinds),
                   key=lambda r: r.get("ts", 0))
    rijen = rijen[-max(1, int(venster)):] if rijen else []
    n = len(rijen)
    akkoord = sum(1 for r in rijen if r["mens"] == r["ai"])
    lo, hi = wilson(akkoord, n)
    return {"n": n, "akkoord": akkoord, "ratio": (akkoord / n if n else 0.0), "lo": lo, "hi": hi}


def promoveerbaar(labels: list[dict], taak: str, niveau: str, cfg: dict) -> tuple[bool, str]:
    """Mag deze taak een trede klimmen? Geeft (ja/nee, leesbare reden).

    De reden is geen decoratie: hij vertelt de founder wát er nog ontbreekt (meer voorbeelden,
    of betere overeenstemming), zodat een geblokkeerde promotie geen raadsel is."""
    if niveau not in NIVEAUS:
        return False, "unknown level"
    if niveau == "D":
        return False, "already at D — the AI handles this on its own"
    meting = overeenstemming(labels, taak, cfg["venster"])
    lat, min_n = float(cfg["lat"]), int(cfg["min_n"])
    if meting["n"] < min_n:
        return False, (f"{meting['n']}/{min_n} blind examples — decide {min_n - meting['n']} more "
                       f"before the measurement means anything")
    if meting["lo"] < lat:
        return False, (f"agreement {meting['ratio'] * 100:.0f}% (95% lower bound "
                       f"{meting['lo'] * 100:.0f}%) is below the bar of {lat * 100:.0f}%")
    return True, (f"agreement {meting['ratio'] * 100:.0f}% over {meting['n']} blind examples, "
                  f"lower bound {meting['lo'] * 100:.0f}% ≥ bar {lat * 100:.0f}%")


def drift_drempel(cfg: dict) -> int:
    """Vanaf hoeveel blinde audit-labels de WAARSCHUWING iets mag beweren.

    De helft van de promotie-eis, vloer 5. Bewust lager dan de demotie-drempel: eerder zien mag
    goedkoop zijn, want kijken kost niets; eerder ingrijpen is dat niet."""
    return max(5, int(cfg["min_n"]) // 2)


def demoveerbaar(labels: list[dict], taak: str, niveau: str, cfg: dict,
                 sinds: float = 0.0) -> tuple[bool, str]:
    """Moet deze taak een trede terug? Geeft (ja/nee, leesbare reden).

    De regel: **een trede blijft precies zolang staan als het bewijs hem zou toekennen.** Deze
    poort is dus de letterlijke negatie van `promoveerbaar` — dezelfde lat, dezelfde `min_n`,
    dezelfde Wilson-ondergrens — maar op de labels sinds de laatste tree-wissel.

    Waarom niet "ondergrens onder de lat" bij een lagere drempel, wat de directe formulering zou
    zijn: dan degradeert een FOUTLOZE reeks. De ondergrens van 21/21 goed is 84,5% en dus onder
    een lat van 85%; een taak zou terugvallen op perfect werk, puur omdat de steekproef klein is.
    Een ondergrens meet "hoe zeker weten we dat het góéd is" — dat is iets anders dan bewijs dat
    het slecht is, en dat verschil is precies wat er misgaat als je de drempel verlaagt maar de
    toets gelijk houdt. Door dezelfde `min_n` te eisen als bij promotie valt die val weg: bij
    n≥30 heeft een foutloze reeks een ondergrens van 88,6%, ruim boven de lat.

    De prijs is dat een terugval bewijs nodig heeft en dus niet bij de eerste misser komt. Dat
    gat vult `drift()`: die waarschuwt al vanaf de halve drempel, en de founder kan altijd zelf
    in één klik terugzetten.

    Alleen op C/D, want alleen daar voert de AI zelf uit: demotie trekt draaiende autonomie in.
    Nooit onder B — daar stelt de AI alleen voor en valt er niets in te trekken; A is een keuze
    van de founder, geen uitkomst van een meting."""
    if niveau not in ("C", "D"):
        return False, ""
    meting = overeenstemming(labels, taak, cfg["venster"], sinds=sinds)
    min_n, lat = int(cfg["min_n"]), float(cfg["lat"])
    if meting["n"] < min_n:
        return False, (f"{meting['n']}/{min_n} blind audit decisions since the last level "
                       f"change — not enough to withdraw the level")
    if meting["lo"] >= lat:
        return False, (f"agreement {_pctstr(meting['ratio'])} in the audit sample, lower bound "
                       f"{_pctstr(meting['lo'])} ≥ bar {_pctstr(lat)}")
    return True, (f"agreement in the audit sample dropped to {_pctstr(meting['ratio'])} "
                  f"(95% lower bound {_pctstr(meting['lo'])}) over {meting['n']} blind "
                  f"decisions, below the bar of {_pctstr(lat)} — this level would no longer "
                  f"be granted on this evidence")


def _pctstr(x: float) -> str:
    return f"{x * 100:.0f}%"


def drift(labels: list[dict], taak: str, niveau: str, cfg: dict, sinds: float = 0.0) -> str:
    """De vroege waarschuwing, vóór de poort dicht kan. Lege string = niets aan de hand.

    Kijkt naar de PUNTSCHATTING vanaf de halve drempel: "de overeenstemming ligt onder je lat".
    Dat is bewust een zwakkere uitspraak dan de demotie-poort doet — hij mag ook aangaan als het
    nog ruis kan zijn, want hij verandert niets. Hij bestaat om de founder te laten ingrijpen
    (één klik terug) vóórdat er genoeg bewijs is om het systeem het te laten doen."""
    if niveau not in ("C", "D"):
        return ""
    meting = overeenstemming(labels, taak, cfg["venster"], sinds=sinds)
    lat = float(cfg["lat"])
    if meting["n"] < drift_drempel(cfg) or meting["ratio"] >= lat:
        return ""
    return (f"drift: agreement in the audit sample is {_pctstr(meting['ratio'])} over "
            f"{meting['n']} blind decisions, below the bar of {_pctstr(lat)}. The automatic "
            f"step-back needs {int(cfg['min_n'])} decisions before it can act — you can step "
            f"back yourself in one click.")


def laatste_wissel(niveaus: "NiveauStore", taak: str) -> float:
    """Wanneer wisselde deze taak voor het laatst van trede? 0.0 = nooit."""
    rijen = niveaus.historie(taak)
    return float(rijen[-1].get("ts", 0.0)) if rijen else 0.0


def pas_demotie_toe(niveaus: "NiveauStore", labels: list[dict], taak: str, cfg: dict,
                    door: str = "auto") -> str:
    """Zet de taak een trede terug als de audit-meting daarom vraagt. Geeft de melding, of "".

    Dit is de enige plek waar een niveau ZONDER menselijke klik verandert, en dat is met opzet
    asymmetrisch: omhoog vereist een handtekening (autonomie uitbreiden is onomkeerbaar genoeg om
    een mens te vragen), omlaag gebeurt vanzelf (autonomie intrekken is de veilige kant, en
    wachten op een mens betekent dat een afwijkend model ondertussen doorwerkt).

    Aanroepen ná het vastleggen van een label: een nieuw blind audit-oordeel is precies het
    moment waarop het bewijs verandert."""
    niveau = niveaus.niveau(taak)
    moet, reden = demoveerbaar(labels, taak, niveau, cfg, sinds=laatste_wissel(niveaus, taak))
    if not moet:
        return ""
    nieuw = vorige(niveau)
    if not niveaus.zet(taak, nieuw, door=door, reden=f"auto-demotion — {reden}"):
        return ""
    log.warning("⤓ auto-demotie %s: %s → %s (%s)", taak, niveau, nieuw, reden)
    return f"⤓ {TAAK_LABEL[taak]} stepped back to level {nieuw} automatically — {reden}"


def volgende(niveau: str) -> str:
    i = NIVEAUS.index(niveau) if niveau in NIVEAUS else 0
    return NIVEAUS[min(i + 1, len(NIVEAUS) - 1)]


def vorige(niveau: str) -> str:
    i = NIVEAUS.index(niveau) if niveau in NIVEAUS else 0
    return NIVEAUS[max(i - 1, 0)]


# ── De succesmetriek: founder-minuten per week + het aandeel dat de AI overnam ────────────────

def _week(ts: float) -> str:
    """ISO-week als 'YYYY-Www' — stabiel over jaargrenzen, anders dan een naïeve /7."""
    return time.strftime("%G-W%V", time.localtime(ts or 0))


def weekcijfers(labels: list[dict], taak: str, weken: int = 6) -> list[dict]:
    """Per ISO-week: founder-minuten aan deze taak, het aantal beslissingen, en het aandeel
    items dat de AI zelf afhandelde. Nieuwste week laatst, zodat de reeks als trend leest.

    De minuten tellen alleen menselijke beslissingen — dat is precies de tijd die moet dalen."""
    rijen = [r for r in labels if r.get("taak") == taak]
    per: dict[str, dict] = {}
    for r in rijen:
        wk = _week(r.get("ts", 0))
        vak = per.setdefault(wk, {"week": wk, "seconden": 0.0, "mens": 0, "ai": 0})
        if r.get("mens") is None:
            vak["ai"] += 1
        else:
            vak["mens"] += 1
            vak["seconden"] += float(r.get("seconden") or 0.0)
    uit = []
    for wk in sorted(per)[-max(1, int(weken)):]:
        vak = per[wk]
        totaal = vak["mens"] + vak["ai"]
        uit.append({"week": wk, "minuten": round(vak["seconden"] / 60.0, 1),
                    "beslissingen": vak["mens"], "ai": vak["ai"],
                    "ai_aandeel": (vak["ai"] / totaal) if totaal else 0.0})
    return uit


def trend(cijfers: list[dict]) -> str:
    """'dalend' / 'stijgend' / 'vlak' / '' over de founder-minuten. Vergelijkt de laatste week
    met de week ervoor — geen regressie over een reeks van drie punten, dat suggereert
    precisie die er niet is."""
    if len(cijfers) < 2:
        return ""
    nieuw, oud = cijfers[-1]["minuten"], cijfers[-2]["minuten"]
    if abs(nieuw - oud) < 0.1:
        return "vlak"
    return "dalend" if nieuw < oud else "stijgend"


# ── Het niveau per taak (state, geen config) ─────────────────────────────────────────────────

class NiveauStore(JsonStore):
    """Het huidige rijpheidsniveau per taak + de historie van elke tree-wissel.

    De historie is geen luxe: een niveau dat verandert verandert wat de AI zelfstandig mag doen,
    en dat hoort net zo terug te lezen te zijn als een governance-wijziging."""

    _WRITE_METHODS = ("zet",)
    _STATE = "_data"
    _EXPECT = dict

    def _load(self) -> None:
        super()._load()
        self._data.setdefault("niveaus", {})
        self._data.setdefault("historie", [])

    def niveau(self, taak: str) -> str:
        n = (self._data.get("niveaus") or {}).get(taak)
        return n if n in NIVEAUS else "A"

    def alles(self) -> dict:
        return {t: self.niveau(t) for t in TAKEN}

    def historie(self, taak: str = "") -> list[dict]:
        rijen = self._data.get("historie") or []
        return [r for r in rijen if not taak or r.get("taak") == taak]

    def zet(self, taak: str, niveau: str, *, door: str = "", reden: str = "") -> bool:
        """Zet het niveau en noteer waarom. False bij een onbekende taak of trede."""
        if taak not in TAKEN or niveau not in NIVEAUS:
            return False
        oud = self.niveau(taak)
        if oud == niveau:
            return False
        self._data["niveaus"][taak] = niveau
        self._data["historie"].append({"taak": taak, "van": oud, "naar": niveau,
                                       "door": door or "?", "reden": (reden or "")[:300],
                                       "ts": time.time()})
        self._save()
        log.info("🎚 founder-flow %s: %s → %s (%s)", taak, oud, niveau, reden or "geen reden")
        return True
