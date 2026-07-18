"""Radar → kennisbank: een goedgekeurd signaal promoveren tot kenniskaartje (atoom).

De brug tussen de Radar (gecureerde feed-signalen per rol) en laag 1 van de kennislaag (de
atomen-bibliotheek in notes.json). Eén klik op een goedgekeurd signaal maakt er een kaartje
van — claim = de signal-content letterlijk (geen LLM), herkomst = source/link/publicatiedatum
van het signaal. Alles loopt via de bestaande store-paden (NotesStore/RadarStore), append-only.

Ontwerpkeuzes:
- Duplicaat-detectie vóór aanmaken: dezelfde stable_id-basis (genormaliseerde content +
  genormaliseerde bron, kennisbank_intake.stable_id) of dezelfde genormaliseerde reference-URL
  op een niet-gearchiveerd atoom → GEEN tweede kaartje; de signal-herkomst stapelt dan op het
  bestaande atoom (NotesStore.stack_provenance, hetzelfde "; "-mechanisme als merge_into).
- Idempotent: het radar-item krijgt promoted_atom_id zodra gepromoveerd; een tweede promotie
  is een nette banner, nooit een duplicaat.
- Fail-soft: onbekend item, niet-goedgekeurd, leeg → (None, reden-banner), nooit een crash.
"""
from __future__ import annotations

import configparser
import os
import re

from nooch_village.insight import Insight
from nooch_village.kennisbank_intake import stable_id

# Herkomst-type op de trustladder (kennisbank.PROVENANCE_TRUST): radar-signalen komen uit
# nieuws-/vakbladfeeds — 'media' tot een curator de herkomst preciezer duidt.
_PROVENANCE = "media"


def norm_ref(url: str) -> str:
    """Genormaliseerde artikel-URL voor duplicaat-detectie: schema, www., query/fragment en
    trailing slash eraf, lowercase. Zo matcht dezelfde link ook met utm-staart of http/https-
    variant. Leeg blijft leeg (en matcht dus nooit). Interne links (beginnen met '/', zoals
    "/project?id=<pid>" van projectsignalen) houden hun query: die IS daar de identiteit —
    strippen zou alle projectsignalen op '/project' laten samenvallen."""
    u = (url or "").strip().lower()
    if not u:
        return ""
    if u.startswith("/"):
        return u.split("#")[0].rstrip("/") or "/"
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.split("?")[0].split("#")[0].rstrip("/")


def parse_source_date(published_at: str) -> str:
    """Publicatiedatum van de feed (RFC3339) → ISO-datum (YYYY-MM-DD) voor source_date;
    alleen als hij echt parsebaar is, anders leeg (geen gok-datums in de bibliotheek)."""
    from datetime import date
    s = (published_at or "").strip()[:10]
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return ""


def find_duplicate(notes, content: str, source: str, link: str) -> str | None:
    """Bestaand niet-gearchiveerd atoom dat dit signaal al dekt: zelfde stable_id-basis
    (content+bron) óf zelfde genormaliseerde reference-URL (ook als segment van een
    "; "-gestapelde reference). None als er niets matcht."""
    aid = stable_id(content, source)
    bestaand = notes.get(aid)
    if bestaand is not None and not bestaand.archived:
        return aid
    doel = norm_ref(link)
    if not doel:
        return None
    for a in notes.all():
        if a.archived:
            continue
        for deel in (a.reference or "").split(";"):
            if norm_ref(deel) == doel:
                return a.id
    return None


def promote_signal(st, rid: str) -> tuple[str | None, str]:
    """Promoveer één goedgekeurd radar-signaal tot kenniskaartje. Geeft (atom_id, banner)
    terug; atom_id is None als er niets gebeurde (de banner zegt waarom). Schrijft
    uitsluitend via de store-methodes; het radar-item krijgt de promoted_atom_id-marker."""
    it = st.radar.get(rid)
    if it is None:
        return None, "✗ onbekend radar-signaal"
    if it.get("promoted_atom_id"):
        return None, "Al gepromoveerd — dit signaal staat al in de kennisbank"
    if it.get("status") != "goedgekeurd":
        return None, "✗ alleen goedgekeurde signalen kunnen naar de kennisbank"
    content = (it.get("content") or "").strip()
    if not content:
        return None, "✗ leeg signaal — niets om te promoveren"
    source = ((it.get("source") or "").strip() or (it.get("feed") or "").strip() or "radar")
    link = (it.get("link") or "").strip()

    dup = find_duplicate(st.notes, content, source, link)
    if dup is not None:
        # Geen tweede kaartje: de signal-herkomst stapelt op het bestaande atoom
        # (zelfde "; "-mechanisme als merge_into voor source/reference).
        st.notes.stack_provenance(dup, source=source, reference=link)
        st.notes.add_tags(dup, ["signal"])
        st.radar.mark_promoted(rid, dup)
        return dup, "🔗 samengevoegd met bestaand kaartje — herkomst gekoppeld"

    aid = stable_id(content, source)
    kaart = Insight(id=aid, claim=content[:500], source=source[:160],
                    reference=(link[:200] or None),
                    source_date=(parse_source_date(it.get("published_at", "")) or None),
                    tags=["signal"], evidence_type="reported",
                    provenance=_PROVENANCE, version=1)
    try:
        st.notes.add(kaart)
    except ValueError:
        # Race/archief-rand: id bestaat al (bv. gearchiveerd atoom met zelfde basis) —
        # fail-soft: herkomst koppelen i.p.v. crashen op de append-only bibliotheek.
        st.notes.stack_provenance(aid, source=source, reference=link)
        st.notes.add_tags(aid, ["signal"])
        st.radar.mark_promoted(rid, aid)
        return aid, "🔗 samengevoegd met bestaand kaartje — herkomst gekoppeld"
    st.radar.mark_promoted(rid, aid)
    return aid, "🧠 kenniskaartje gemaakt — dit signaal telt nu mee in de kennisbank"


def auto_promote_enabled(data_dir: str) -> bool:
    """Config-vlag radar_auto_promote (config/settings.ini naast de data-map, zelfde
    precedentie als config.load_context: [DEFAULT] eerst, secties overschrijven).
    Default 0/uit — het bestaande approve-gedrag verandert dus niet. Fail-soft: elke
    leesfout telt als uit."""
    try:
        base = os.path.dirname(os.path.abspath(data_dir))
        ini = os.path.join(base, "config", "settings.ini")
        if not os.path.exists(ini):
            return False
        cp = configparser.ConfigParser()
        cp.read(ini)
        v = cp.defaults().get("radar_auto_promote", "")
        for section in cp.sections():
            if cp.has_option(section, "radar_auto_promote"):
                v = cp.get(section, "radar_auto_promote")
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
