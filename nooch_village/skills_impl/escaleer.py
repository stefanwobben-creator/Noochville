"""escaleer — routeer bewust naar de juiste plek, met onderscheid tussen bevinding en beslissing.

De knel (founder 23 jul): élke escalatie belandde als spanning in de inbox van de mens, ook een
eerlijke UITKOMST van eigen werk ("geen enkel alternatief voor elastan voldoet aan de eisen"). Er was
geen verschil tussen "dit is mijn bevinding, leg vast" en "ik heb een keuze van jou nodig". Daardoor
liep de founder vol met dingen die geen beslissing waren, en werden gesloten-kunnende projecten open
gehouden.

De fix maakt dat onderscheid structureel, in het ene punt waar alle escalaties langskomen:

- aard='bevinding' — een uitkomst/conclusie van je eigen werk (óók een eerlijke nul-uitkomst). Dit is
  GEEN vraag aan de mens: het wordt vastgelegd als antwoord van je project (tekst-deliverable → het
  einddocument, checklist-item af → project richting review/afsluiten). Er gaat NIETS naar de founder.

- aard='beslissing' — je hebt echt een keuze van een mens (of andere rol) nodig die jij niet mag/kunt
  maken. Alleen dit landt als notificatie bij de doel-rol, en de reden wordt als EXPLICIETE keuze
  geformuleerd ("eisen loslaten: ja of nee?") zodat het meteen beantwoordbaar is.

Kiest de rol geen aard, dan classificeert de skill zelf (LLM), fail-OPEN naar 'beslissing': een
uitkomst die per ongeluk een verborgen vraag draagt is minder erg zichtbaar bij de mens dan een echte
keuze die stil wordt weggeslikt (veiligheid > accuratesse). Een bevinding is nooit verstopt: hij staat
transparant op het projectbord en in De Kroniek.

SCOPE 57 (skill-review 12-09-2026, live: 121 escaleer-items, 20 beslissingen, 0 als mens-taak). Een
beslissing gaf `{aard, naar, reden, notif_id}` terug: `reden` is metadata voor de uitvoerlaag, dus de
wall toonde letterlijk "beslissing", het item werd afgevinkt alsof de vraag beantwoord was, en de
notificatie droeg geen project_id — de tensie-poort maakte er een NIEUW rol-project van dat opnieuw
een escaleer-item plande. Nu draagt een beslissing zijn vraag onder `text`, zegt `wacht_op_mens`, en
neemt het project-id mee naar de notificatie; `_execute_checklist` zet zo'n item als mens-taak neer
in plaats van het af te vinken. Een bevinding is alleen nog de tekst zelf: de vaste zin "vastgelegd
als projectuitkomst" dook op in einddocument en critic als ware het de bevinding.
"""
from __future__ import annotations

import os

from nooch_village.skills import Skill

# Aliassen voor de mens-aan-het-roer: alles wat "founder/farmer/mens" betekent → the_source.
# Gedeeld met projectverzoek/handoff via `rol_id_voor` (één waarheid voor 'wie is de founder').
_FOUNDER = frozenset({"founder", "founding farmer", "the_source", "the source", "mens", "human",
                      "stefan", "@founding farmer"})
FOUNDER_ROL = "the_source"
_AARDEN = {"bevinding", "beslissing"}


def rol_id_voor(naam: str, records=None) -> str:
    """De rol-id waar een naam naar wijst, of "" als er geen eenduidige rol is.

    Drie treden, smal naar breed: (1) een founder-alias → `the_source`; (2) de exacte id bestaat in
    de records; (3) precies één rol-id eindigt op `__<naam>` (de cirkel-prefix weggelaten — live
    schreef de planner `mother_earth__nooch__copywriter` waar de id
    `mother_earth__nooch__noochville__copywriter` was). Twee of meer suffix-treffers = geen keuze:
    dan raadt niemand. Zonder records-store: alleen de alias-trede en de naam zelf (niet-weten is
    geen bezwaar; de aanroeper beslist wat een onbekende store betekent).

    Gedeeld door escaleer, projectverzoek.validate_payload én project_items.handoff — de founder-
    aliassen leefden alleen hier, en projectverzoek weigerde 'founder' terwijl escaleer het aannam
    (twee waarheden, skill-review 12-09-2026). Een kapotte store gooit: de aanroeper beslist wat
    niet-kunnen-lezen betekent (de poort: geen bezwaar; de overdracht: een zichtbare fout)."""
    n = (naam or "").strip()
    if not n:
        return ""
    if n.lower() in _FOUNDER:
        return FOUNDER_ROL
    if records is None:
        return n
    if records.get(n) is not None:
        return n
    alle = getattr(records, "all", None)
    if not callable(alle):
        return ""                                        # geen lijst om een suffix in te zoeken
    laag = n.lower()
    treffers = [r.id for r in alle()
                if not getattr(r, "archived", False)
                and str(r.id).lower().endswith("__" + laag)]
    return treffers[0] if len(treffers) == 1 else ""


class EscaleerSkill(Skill):
    name = "escaleer"
    cost = "free"                  # lokale notificatie-append + begrensde LLM (classify/herformuleer)
    side_effect_free = False       # 'beslissing' schrijft één notificatie; 'bevinding' legt een uitkomst vast
    # De planner ziet description[:160] + het hele input_schema: de kern (beide aarden) staat vooraan.
    description = ("Record a FINDING as the project's answer (aard='bevinding') or ask a human or "
                   "role for a DECISION (aard='beslissing'; the item waits until answered). "
                   "A finding is written from your own evidence, never invented; a decision is one "
                   "explicit, answerable choice. Nothing else reaches the founder.")
    input_schema = ("aard: str (required — 'bevinding' | 'beslissing'; missing → classified by a model, "
                    "fail-open to 'beslissing'); "
                    "reden: str (required — bevinding: the outcome in one to three sentences, grounded in "
                    "what the project found; beslissing: the explicit choice as a question with options, "
                    "e.g. 'drop the elastane requirement: yes or no?'); "
                    "naar: str (optional, beslissing only — target role id, or 'founder' for the "
                    "Founding Farmer; default: the founder); "
                    "van: str (optional — the escalating role, shown as sender)")
    required_payload = ("reden",)  # 'naar' alleen bij beslissing; ontbrekende 'aard' wordt geclassificeerd
    output_schema = ("ok, aard ('bevinding'|'beslissing'), text (the finding, or 'Decision requested "
                     "from <role>: <choice>'), reden | beslissing: naar, notif_id, wacht_op_mens=True")

    def validate_payload(self, payload: dict, context) -> list:
        """`aard` is een enum: een verzonnen waarde ('vraag', 'finding') zou live stil naar de
        LLM-classificatie vallen en fail-open als beslissing bij de founder landen. Bij het plannen
        tegenhouden is goedkoper dan een verkeerde notificatie. Leeg/afwezig blijft toegestaan
        (dan classificeert de skill zelf, zoals de docstring belooft)."""
        aard = str((payload or {}).get("aard") or "").strip().lower()
        if aard and aard not in _AARDEN:
            return [f"'aard' must be 'bevinding' or 'beslissing', not {aard!r}"]
        # `naar` is een verwijzing: een verzonnen rol-id laat de vraag bij niemand landen.
        naar = str((payload or {}).get("naar") or "").strip()
        recs = getattr(context, "records", None) if context is not None else None
        if naar and recs is not None:
            try:
                if not rol_id_voor(naar, recs):
                    return [f"'naar' refers to a role that does not exist ({naar!r}); use a role id "
                            f"from the roster or 'founder'"]
            except Exception:                            # noqa: BLE001 — kapotte store = geen oordeel
                return []
        return []

    def run(self, payload: dict, context=None) -> dict:
        reden = ((payload or {}).get("reden") or "").strip()
        if not reden:
            return {"error": "ontbrekende parameter: 'reden' is verplicht"}
        aard = ((payload or {}).get("aard") or "").strip().lower()
        if aard not in _AARDEN:
            aard = self._classify(reden, context)     # LLM, fail-open → 'beslissing'
        if aard == "bevinding":
            return self._bevinding(reden)
        return self._beslissing(reden, payload or {}, context)

    # ── bevinding: uitkomst van eigen werk → vastleggen, geen mensbeslissing ──────────────────────
    def _bevinding(self, reden: str) -> dict:
        """Een bevinding is het ANTWOORD van je project, geen vraag. Teruggeven als tekst-uitkomst: de
        checklist maakt er een deliverable van (→ einddocument) en vinkt het item af, zodat het project
        naar review/afsluiten kan. Er gaat bewust niets naar de founder-inbox.

        Alleen `text` draagt inhoud (`reden` en `aard` zijn metadata voor de uitvoerlaag): de vaste
        samenvattingszin die hier stond won bij korte bevindingen de wall en het verslag."""
        return {"ok": True, "aard": "bevinding", "reden": reden[:2000], "text": reden[:2000]}

    # ── beslissing: echte keuze → naar de doel-rol, expliciet geformuleerd ────────────────────────
    def _beslissing(self, reden: str, payload: dict, context) -> dict:
        naar_raw = (payload.get("naar") or "").strip()
        # Leeg of een founder-alias → de mens-aan-het-roer; anders de opgegeven rol (een suffix-naam
        # wordt via de records naar de echte id gebracht; onbekend blijft zoals opgegeven — de
        # notificatie landt dan op die id en is zichtbaar, niet stil weg).
        naar = (rol_id_voor(naar_raw, getattr(context, "records", None)) or naar_raw
                if naar_raw else FOUNDER_ROL)
        van = (payload.get("van") or "").strip() or "een rol"
        keuze = self._als_keuze(reden)                # herformuleer tot een expliciete keuze, fail-soft
        # Het project waar deze vraag bij hoort. De uitvoerlaag geeft het mee als `_project_id`
        # (run-context, geen inhoud); zonder project-id kon de tensie-poort de notificatie nergens
        # aan hangen en maakte er een nieuw project van — de lus uit de skill-review.
        pid = str(payload.get("_project_id") or payload.get("project_id") or "")
        dd = getattr(context, "data_dir", ".") or "."
        try:
            from nooch_village.notifications import NotifStore
            notif = NotifStore(os.path.join(dd, "notifications.json"))
            # Geen eigen cap: de store bewaart de volle tekst en leidt de preview af (#389).
            n = notif.add("role", naar, pid, by=van, snippet=f"⤴ beslissing gevraagd: {keuze}")
        except Exception as e:
            return {"error": f"escalatie kon niet landen: {e}"}
        return {"ok": True, "aard": "beslissing", "naar": naar, "reden": keuze,
                "text": f"Decision requested from {naar}: {keuze}",
                "wacht_op_mens": True,                # de uitvoerlaag: mens-taak, niet afvinken
                "notif_id": n.get("id", "")}

    # ── LLM-hulpjes (begrensd, fail-soft) ─────────────────────────────────────────────────────────
    @staticmethod
    def _classify(reden: str, context=None) -> str:
        """Bevinding of beslissing? Fail-OPEN naar 'beslissing': liever een keuze zichtbaar bij de mens
        dan stil weggeslikt. Geen LLM → 'beslissing'."""
        try:
            from nooch_village.llm import reason
            prompt = (
                "An autonomous role wants to escalate something. Decide what it IS:\n"
                "- FINDING: an outcome or conclusion of its own work, including an honest null result "
                "('nothing qualifies', 'no source found'). It asks no choice of a human.\n"
                "- DECISION: a choice is needed that the role itself may not make "
                "('may we drop the requirement?', 'which of these two?').\n\n"
                f"Text: \"{reden[:400]}\"\n\n"
                "Answer with EXACTLY one word: FINDING or DECISION.")
            out = reason(prompt, call_site="escaleer_classify", max_tokens=8)
            low = (out or "").strip().lower()
            if "finding" in low or "bevinding" in low:       # de oude NL-token blijft herkend
                return "bevinding"
        except Exception:
            pass
        return "beslissing"

    @staticmethod
    def _als_keuze(reden: str) -> str:
        """Herformuleer een reden tot een EXPLICIETE, beantwoordbare keuze. Leest het al als een vraag
        (bevat '?'), dan onveranderd. Geen LLM → onveranderd (fail-soft; de reden gaat er hoe dan ook op)."""
        if "?" in reden:
            return reden[:300]
        try:
            from nooch_village.llm import reason
            prompt = (
                "Rewrite the escalation below as ONE explicit, answerable choice for the founder: name "
                "the situation briefly, then ask the concrete question (preferably yes/no or a choice "
                "between options). Two sentences at most, end with a question, no preamble. Use only "
                "what the escalation says; add no facts.\n\n"
                f"Escalation: \"{reden[:400]}\"")
            out = reason(prompt, call_site="escaleer_keuze", max_tokens=120)
            out = (out or "").strip()
            return out[:300] if out else reden[:300]
        except Exception:
            return reden[:300]

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """Beide aarden zijn een Kroniek-feit ('bevestigd'): een bevinding is vastgelegd, een beslissing is
        doorgezet. De aard staat in de meta, zodat later zichtbaar is welke rol een uitkomst vastlegde en
        welke een echte keuze bij een mens/andere rol neerlegde (leren: waar loopt het vast, wie sluit af)."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        aard = result.get("aard") or "beslissing"
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("reden") or "")[:200], "source": "escaleer",
                 "status": "bevestigd", "result_ref": result.get("notif_id", ""),
                 "meta": {"aard": aard, "naar": result.get("naar")}}]
