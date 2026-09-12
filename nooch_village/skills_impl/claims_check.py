"""claims_check — toets tekst tegen de eigen claims-database (EmpCo 2024/825 + ACM).

Puur lokaal: leest `config/claims_database.json` via `nooch_village.claims_db` en doet geen enkele
netwerk-aanroep. Fail-closed bij een ontbrekend of corrupt bestand — een claimtoets die stilzwijgend
'geen bevindingen' meldt is gevaarlijker dan een zichtbare fout.

De juridische inhoud van de database is compliance-domein; deze skill leest alleen.

Uitvoervorm (scope 56). De drie uitkomsten van de brief:
  {"ok": False, "error": …}          de database is onleesbaar of er is geen tekst
  {"no_data": True, "reason": …}     getoetst, geen gevlagde term — en `reason` zegt expliciet dat
                                     dit GEEN goedkeuring is (de lege-run-regel uit `betekenis_van`)
  {"ok": True, "bevindingen": […]}   elke bevinding draagt `oordeel` ("red — source A: …") en
                                     `citaat` (wat er gevonden is + waarom), zodat de wall-note en
                                     het verslag het stoplicht tonen en niet alleen de termnaam
De regel-gebaseerde eerlijkheidsregels heten `toelichting` (metadata voor de uitvoerlaag): tot scope
56 heetten ze `betekenis`, en die lijst won als 'langste lijst' van de bevindingen — de note toonde
dan vier disclaimers en verzweeg de rode treffer (skill-review 12-09-2026).
"""
from __future__ import annotations

from nooch_village import claims_db
from nooch_village.skills import Skill

# De herkomst van een Kroniek-record uit deze skill. Bewust NIET de skill-naam: de termenlijst is de
# bron, de skill is de lezer. En hij staat in `claims_substantiatie.EIGEN_RUNS`, want een record
# dat zegt "wij toetsten deze tekst" is geen bewijs dat een externe bron de claim draagt.
KRONIEK_BRON = "claims_db"

_STOPLICHT_EN = {"red": "red", "orange": "orange", "green": "green",
                 claims_db.ESCALEREN: "to be judged"}


class ClaimsCheckSkill(Skill):
    name = "claims_check"
    cost = "free"
    side_effect_free = True
    required_env = ()
    description = ("Checks text against the Nooch claims database (EmpCo 2024/825 + ACM): per "
                   "flagged term the traffic light (red/orange/green/to-be-judged), the legal source, "
                   "why it is a risk and a safer alternative, plus a compliance score. Local, no "
                   "network, no model. No flagged term is NOT an approval — it only tests the term list.")
    input_schema = ("text: str (the copy to check) OR terms: list[str] (checked as one text) — "
                    "one of the two is required; nothing else.")
    output_schema = ("ok, score, rood, oranje, groen, escaleren, versie, text, "
                     "bevindingen[{term, stoplicht, categorie, waarom, alternatief, gevonden[], bron, "
                     "bron_detail, oordeel, citaat}], toelichting[] | no_data+reason | error")
    # "text OF terms" — een disjunctie, geen platte lijst. Als ("text","terms") zou de poort BEIDE
    # eisen en de skill op de andere manier breken; de skill accepteert er één. Zonder declaratie gaf
    # de poort groen en weigerde de skill alsnog bij het draaien, en dat kostte de onderzoekspas zijn
    # tweede bron. Zie `skills.ontbrekende_velden`.
    required_payload = (("text", "terms"),)

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        tekst = (payload.get("text") or "").strip()
        if not tekst:
            terms = payload.get("terms") or []
            if isinstance(terms, str):                 # de planner geeft soms één term als string
                terms = [terms]
            tekst = "\n".join(str(t) for t in terms if t).strip()
        if not tekst:
            return {"ok": False, "error": "geef 'text' of 'terms' mee"}
        try:
            uitslag = claims_db.check_tekst(tekst, data_dir=getattr(context, "data_dir", None))
        except claims_db.ClaimsDbError as e:
            return {"ok": False, "error": str(e)}
        toelichting = betekenis_van(uitslag, tekst)
        bevindingen = [verrijk(b) for b in uitslag.get("bevindingen") or []]
        uit = {"ok": True, **uitslag, "bevindingen": bevindingen, "toelichting": toelichting,
               "_tekst": tekst[:200]}
        if not bevindingen:
            # De lege run boekt als 📭 "reported, nothing found", niet als geslaagd resultaat met
            # een disclaimer als antwoord. De reden IS de lege-run-regel: niets gevonden is geen
            # goedkeuring, en die zin reist mee naar wall, Kroniek en verslag.
            uit["no_data"] = True
            uit["reason"] = toelichting[0] if toelichting else (
                "no listed term found — this is not an approval; the check only tests the term list")
            return uit
        uit["text"] = kop_tekst(uit)
        return uit

    # ── De Kroniek-brug ────────────────────────────────────────────────────────
    # Zonder deze haak schreef de onderzoekspas voor élke run — ook een lege — een record
    # `status=bevestigd, source=claims_check` (de fallback in `onderzoekspas._naar_kroniek`). Dat zijn
    # precies de cirkel-records waar `claims_substantiatie.EIGEN_RUNS` tegen moet filteren, en tot
    # scope 56 filterde alleen `claim_oordeel` ze; de site-scan las ze als bewijs.
    def evidence_records(self, result: dict, *, role_id: str) -> list:
        if not isinstance(result, dict) or result.get("error") or result.get("ok") is False:
            return []
        query = str(result.get("_tekst") or "")[:200] or "(claims check)"
        bevindingen = [b for b in (result.get("bevindingen") or []) if isinstance(b, dict)]
        if result.get("no_data") or not bevindingen:
            return [{"role_id": role_id, "skill": self.name, "query": query, "source": KRONIEK_BRON,
                     "status": "leeg", "result_ref": ""}]
        ref = ", ".join(f"{b.get('term', '?')} ({b.get('stoplicht', '?')})" for b in bevindingen)
        return [{"role_id": role_id, "skill": self.name, "query": query, "source": KRONIEK_BRON,
                 "status": "bevestigd", "result_ref": ref[:200]}]


def verrijk(b: dict) -> dict:
    """Eén bevinding mét `oordeel` en `citaat`, zodat de uitvoerlaag (wall-note, verslag) het
    stoplicht en de bron toont. Tot scope 56 rendert het verslag alleen de termnaam: "• planet-safe"
    zonder rood, bron of waarom (project_verslag kent alleen title/url/extract-achtige velden;
    `oordeel` + `citaat` rendert hij als "oordeel — “citaat”")."""
    stoplicht = str(b.get("stoplicht") or "")
    bron = str(b.get("bron") or "").strip()
    detail = str(b.get("bron_detail") or "").strip()
    oordeel = _STOPLICHT_EN.get(stoplicht, stoplicht or "?")
    if bron:
        oordeel += f" — source {bron}" + (f": {detail}" if detail else "")
    gevonden = [str(g) for g in (b.get("gevonden") or []) if str(g).strip()]
    # Enkele aanhalingstekens: het verslag zet het citaat zelf al tussen “…”.
    citaat = f"found '{gevonden[0]}'" if gevonden else "found"
    if len(gevonden) > 1:
        citaat += f" (+{len(gevonden) - 1} more)"
    if b.get("waarom"):
        citaat += f" — {b['waarom']}"
    return {**b, "oordeel": oordeel, "citaat": citaat}


def kop_tekst(uit: dict) -> str:
    """De leeswijzer: de kerncijfers in één zin, in het Engels (de wall en het verslag lezen Engels).
    "3 findings: 1 red (planet-safe / …), 2 orange (natuurlijk, gerecycled) — score 83/100"."""
    bevindingen = list(uit.get("bevindingen") or [])
    delen = []
    for kleur, label in (("red", "red"), ("orange", "orange"), (claims_db.ESCALEREN, "to be judged"),
                         ("green", "green")):
        termen = [str(b.get("term") or "?") for b in bevindingen if b.get("stoplicht") == kleur]
        if termen:
            namen = ", ".join(termen[:3]) + (f", +{len(termen) - 3}" if len(termen) > 3 else "")
            delen.append(f"{len(termen)} {label} ({namen})")
    n = len(bevindingen)
    kop = f"{n} finding{'s' if n != 1 else ''}: " + ", ".join(delen)
    if uit.get("score") is not None:
        kop += f" — score {uit['score']}/100"
    return kop


# ── Wat de cijfers NIET vaststellen ──────────────────────────────────────────
#
# Deze skill gaf rauwe velden terug: `score=100`, `rood=0`, `bevindingen=[]`. Een lezer moet dan zelf
# invullen wat dat betekent, en dat ging structureel mis: 16 van 28 gedegradeerde voorstellen rustten
# op een claims_check die niets vond en dat als "score 100" rapporteerde. De synthese las dat als
# "compliant", de critic zag een ongegronde gevolgtrekking, en beide hadden gelijk — de betekenis
# stond nergens.
#
# Dus levert de bron zijn eigen betekenis mee. REGEL-GEBASEERD: elke string volgt uit een
# vergelijking op de data, nooit uit een model dat interpreteert — een geraden betekenis zou
# confabulatie bij de bron zijn, en dat is erger dan geen betekenis.
#
# De strings zeggen wat de data NIET vaststelt. Liever te terughoudend dan te toeschietelijk: een te
# sterke string ("de claim is compliant") is precies de fout die we hier weghalen, alleen dan met
# gezag van de bron erachter.

def betekenis_van(uitslag: dict, onderzochte_claim: str = "") -> list[str]:
    """Deterministische betekenis-regels bij deze uitslag. Leeg = niets bijzonders te melden."""
    uit: list[str] = []
    bevindingen = list(uitslag.get("bevindingen") or [])
    tellers = [int(uitslag.get(k) or 0) for k in ("rood", "oranje", "groen", "escaleren")]
    score = uitslag.get("score")

    if not bevindingen and not any(tellers):
        if str(score) == "100":
            uit.append("score=100 met alle tellers op 0 en geen bevindingen betekent dat er geen "
                       "enkele claim inhoudelijk is getoetst — dit is een lege run, GEEN goedkeuring "
                       "en geen uitspraak over of de claim houdbaar is")
        else:
            uit.append("geen gevlagde term gevonden — dat is niet hetzelfde als compliant; deze scan "
                       "toetst alleen tegen de termenlijst en zegt niets over de inhoud van de claim")
    elif not bevindingen:
        uit.append("geen gevlagde term gevonden — dat is niet hetzelfde als compliant; deze scan "
                   "toetst alleen tegen de termenlijst en zegt niets over de inhoud van de claim")

    claim_tekst = _plat(onderzochte_claim)
    claim = _norm(onderzochte_claim)
    for n, b in enumerate(bevindingen):
        term = str(b.get("term") or "")
        if claim and term and not _raakt(b, claim_tekst, claim):
            uit.append(f"bevindingen[{n}] gaat over de term '{term}', niet over de onderzochte "
                       f"claim — deze bevinding zegt niets over die claim")
        if str(b.get("alternatief") or "").strip():
            uit.append(f"bevindingen[{n}].alternatief is een VOORGESTELD alternatief uit de "
                       f"claims-database, geen goedgekeurde vervangtekst — het is niet getoetst op "
                       f"deze context en niet door legal gezien")
    return uit


def _plat(tekst: str) -> str:
    import re as _re
    return " ".join(_re.split(r"[^\w]+", (tekst or "").lower())).strip()


def _norm(tekst: str) -> set:
    import re as _re
    return {w for w in _re.split(r"[^\w]+", (tekst or "").lower()) if len(w) >= 4}


def _raakt(bevinding: dict, claim_tekst: str, claim_woorden: set) -> bool:
    """Gaat deze bevinding over de onderzochte claim?

    Drie trappen, elk ruimer dan de vorige. Bewust ruim: bij twijfel géén melding, want een
    onterechte "gaat over een andere term" duwt een correcte bevinding weg — de duurdere fout.
      1. Het gevonden fragment staat letterlijk in de claim → ja (de regex matchte immers dáár).
      2. De term deelt een heel woord (≥ 4 tekens) met de claim → ja.
      3. Stam-vergelijking: een woord van de term is een deel van een claimwoord of andersom
         ('gerecycled' ↔ 'recycled', 'plasticvrij' ↔ 'plastic'). Tot scope 56 ontbrak deze trap en
         drukte de skill bij elke morfologische variant een foute "niet over de onderzochte claim"-
         regel af (skill-review 12-09-2026, gereproduceerd met 'gerecycled' vs 'recycled')."""
    if not claim_woorden:
        return True
    for g in (bevinding.get("gevonden") or []):
        frag = _plat(str(g))
        if frag and frag in claim_tekst:
            return True
    termwoorden = _norm(str(bevinding.get("term") or ""))
    if termwoorden & claim_woorden:
        return True
    return any(t in c or c in t for t in termwoorden for c in claim_woorden)
