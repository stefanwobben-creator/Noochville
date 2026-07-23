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
"""
from __future__ import annotations

import os

from nooch_village.skills import Skill

# Aliassen voor de mens-aan-het-roer: alles wat "founder/farmer/mens" betekent → the_source.
_FOUNDER = {"founder", "founding farmer", "the_source", "the source", "mens", "human",
            "stefan", "@founding farmer"}
_AARDEN = {"bevinding", "beslissing"}


class EscaleerSkill(Skill):
    name = "escaleer"
    cost = "free"                  # lokale notificatie-append + begrensde LLM (classify/herformuleer)
    side_effect_free = False       # 'beslissing' schrijft één notificatie; 'bevinding' legt een uitkomst vast
    description = ("Routeer bewust naar de juiste plek. Kies EERST de aard. "
                   "aard='bevinding': een UITKOMST van je eigen werk (ook een eerlijke nul-uitkomst, bv. "
                   "'geen enkel alternatief voldoet aan de eisen'). Dit is GEEN vraag aan de mens — het "
                   "wordt vastgelegd als antwoord van je project en het project kan sluiten. Gebruik dit "
                   "als je klaar bent en niets meer van een ander nodig hebt. "
                   "aard='beslissing': je hebt echt een KEUZE van een mens of andere rol nodig die jij "
                   "niet mag maken; formuleer die keuze expliciet ('eisen loslaten: ja of nee?'). Alleen "
                   "dit landt bij de founder. Twijfel je? Kies 'beslissing'.")
    input_schema = ("aard: str (verplicht — 'bevinding' of 'beslissing', zie beschrijving); "
                    "reden: str (verplicht — de uitkomst (bevinding) of de expliciete keuze (beslissing)); "
                    "naar: str (bij beslissing — doel-rol-id, of 'founder' voor de Founding Farmer; "
                    "leeg = de founder); "
                    "van: str (optioneel — de escalerende rol, voor de afzender-label)")
    required_payload = ("reden",)  # 'naar' alleen bij beslissing; ontbrekende 'aard' wordt geclassificeerd
    output_schema = "ok, aard ('bevinding'|'beslissing'), reden, [text | naar, notif_id]"

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
        naar review/afsluiten kan. Er gaat bewust niets naar de founder-inbox."""
        return {"ok": True, "aard": "bevinding", "reden": reden[:2000],
                "text": reden[:2000],
                "samenvatting": "vastgelegd als projectuitkomst (geen mensbeslissing nodig)"}

    # ── beslissing: echte keuze → naar de doel-rol, expliciet geformuleerd ────────────────────────
    def _beslissing(self, reden: str, payload: dict, context) -> dict:
        naar_raw = (payload.get("naar") or "").strip()
        # Leeg of een founder-alias → de mens-aan-het-roer; anders de opgegeven rol.
        naar = "the_source" if (not naar_raw or naar_raw.lower() in _FOUNDER) else naar_raw
        van = (payload.get("van") or "").strip() or "een rol"
        keuze = self._als_keuze(reden)                # herformuleer tot een expliciete keuze, fail-soft
        dd = getattr(context, "data_dir", ".") or "."
        try:
            from nooch_village.notifications import NotifStore
            notif = NotifStore(os.path.join(dd, "notifications.json"))
            n = notif.add("role", naar, "", by=van, snippet=f"⤴ beslissing gevraagd: {keuze}"[:160])
        except Exception as e:
            return {"error": f"escalatie kon niet landen: {e}"}
        return {"ok": True, "aard": "beslissing", "naar": naar, "reden": keuze,
                "notif_id": n.get("id", "")}

    # ── LLM-hulpjes (begrensd, fail-soft) ─────────────────────────────────────────────────────────
    @staticmethod
    def _classify(reden: str, context=None) -> str:
        """Bevinding of beslissing? Fail-OPEN naar 'beslissing': liever een keuze zichtbaar bij de mens
        dan stil weggeslikt. Geen LLM → 'beslissing'."""
        try:
            from nooch_village.llm import reason
            prompt = (
                "Een autonome rol wil iets escaleren. Bepaal wat het IS:\n"
                "- BEVINDING: een uitkomst/conclusie van eigen werk, ook een eerlijke nul-uitkomst "
                "('niets voldoet', 'geen bron gevonden'). Vraagt geen keuze van een mens.\n"
                "- BESLISSING: er is een keuze nodig die de rol zelf niet mag maken "
                "('mogen we de eis loslaten?', 'welke van deze twee?').\n\n"
                f"Tekst: \"{reden[:400]}\"\n\n"
                "Antwoord met EXACT één woord: BEVINDING of BESLISSING.")
            out = reason(prompt, call_site="escaleer_classify", max_tokens=8)
            if out and "bevinding" in out.strip().lower():
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
                "Herschrijf de onderstaande escalatie tot ÉÉN expliciete, beantwoordbare keuze voor de "
                "founder: benoem de situatie kort en stel dan de concrete vraag (bij voorkeur ja/nee of "
                "een keuze uit opties). Max twee zinnen, eindig met een vraag. Geen omhaal.\n\n"
                f"Escalatie: \"{reden[:400]}\"")
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
