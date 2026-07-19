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


def _signaal_guards(st, rid: str) -> tuple[dict | None, str]:
    """Gedeelde vangnetten voor promoveren én klaarzetten: geeft (item, "") of (None, reden)."""
    it = st.radar.get(rid)
    if it is None:
        return None, "✗ onbekend radar-signaal"
    if it.get("promoted_atom_id"):
        return None, "Al gepromoveerd — dit signaal staat al in de kennisbank"
    if it.get("status") != "goedgekeurd":
        return None, "✗ alleen goedgekeurde signalen kunnen naar de kennisbank"
    if not (it.get("content") or "").strip():
        return None, "✗ leeg signaal — niets om te promoveren"
    return it, ""


_BRON_ATOM_CAP = 12   # bovengrens per gelezen bron: geen ontploffing in mini-kaartjes


def _atomen_uit_bron(it: dict) -> list[dict] | None:
    """Lees de gelinkte bron van een signaal en atomiseer hem tot voorstellen (dezelfde
    pijplijn als "Verwerk de bron": kennisbank_sources → atomiser, met cap). Fail-closed:
    geen link, fetch-fout of geen LLM → None, en de aanroeper valt terug op de signaaltekst.
    De atomen dragen géén radar_rids; dat zet de aanroeper erbij."""
    link = (it.get("link") or "").strip()
    if not link.lower().startswith("http"):
        return None
    try:
        from nooch_village.kennisbank_intake import atomiseer
        from nooch_village.kennisbank_sources import detect_and_extract
        res = detect_and_extract(text=link)
        if not res.get("chunks"):
            return None
        atoms: list[dict] = []
        for raw, label in res["chunks"]:
            got = atomiseer(raw, label, tabular=res.get("tabular", False))
            if got:
                atoms += got
            if len(atoms) >= _BRON_ATOM_CAP:
                atoms = atoms[:_BRON_ATOM_CAP]
                break
        return atoms or None
    except Exception:
        return None


def stage_signal(st, rid: str) -> tuple[str | None, str]:
    """Zet een goedgekeurd radar-signaal klaar bij "Even nakijken" (staging) in plaats van
    direct een kaartje te maken. De stap probeert de GELINKTE BRON te lezen en te atomiseren
    tot losse voorstellen (atomic insights) — de signaaltekst is het vangnet als dat niet
    lukt (geen link, fetch-fout, geen LLM). De mens kan alles daar bewerken, samenvoegen of
    weggooien; pas bij commit ontstaan de kaartjes (via hetzelfde dedupe/marker-pad als de
    directe promotie — zie kennisbank_staging._commit_signaal_atoom).

    Meerdere signalen landen in DEZELFDE open signalen-batch, zodat ze daar samen te mergen
    zijn. Idempotent: een signaal dat al klaarstaat wordt niet nogmaals toegevoegd.
    Geeft (batch_id, banner); batch_id None als er niets gebeurde (de banner zegt waarom)."""
    it, reden = _signaal_guards(st, rid)
    if it is None:
        return None, reden
    # Staat dit signaal al klaar? (dubbelklik / tweede bezoek) — wijs naar die batch.
    for b in st.staging.open_batches():
        for a in b.get("atoms", []):
            if rid in (a.get("radar_rids") or []):
                return b["id"], "Dit signaal staat al klaar bij Even nakijken"
    bron = ((it.get("source") or "").strip()
            or (it.get("feed") or "").strip() or "radar")
    link = (it.get("link") or "").strip() or None
    datum = parse_source_date(it.get("published_at", "")) or None
    gelezen = _atomen_uit_bron(it)
    if gelezen:
        atomen = [{"content": a.get("content"), "body": a.get("body"),
                   "subject": a.get("subject"),
                   "source": (a.get("source") or bron),
                   "reference": (a.get("reference") or link),
                   "source_date": (a.get("source_date") or datum),
                   "provenance": a.get("provenance") or _PROVENANCE,
                   "provenance_note": a.get("provenance_note"),
                   "flags": a.get("flags") or [],
                   "van_bron": True,
                   "radar_rids": [rid]}
                  for a in gelezen]
        banner = (f"📖 bron gelezen: {len(atomen)} voorstellen staan klaar bij "
                  f"Even nakijken — bewerk, voeg samen of bevestig")
    else:
        atomen = [{"content": (it.get("content") or "").strip(),
                   "source": bron, "reference": link, "source_date": datum,
                   "provenance": _PROVENANCE, "radar_rids": [rid]}]
        banner = ("🔎 signaal staat klaar bij Even nakijken (bron niet leesbaar of geen "
                  "LLM — de signaaltekst is het voorstel)")
    for b in st.staging.open_batches():
        if b.get("kind") == "signaal":
            ok = all(st.staging.append_atom(b["id"], a) for a in atomen)
            if ok:
                return b["id"], banner
    bid = st.staging.create("signaal", "signalen", atomen)
    return bid, banner


def promote_signal(st, rid: str) -> tuple[str | None, str]:
    """Promoveer één goedgekeurd radar-signaal tot kenniskaartje. Geeft (atom_id, banner)
    terug; atom_id is None als er niets gebeurde (de banner zegt waarom). Schrijft
    uitsluitend via de store-methodes; het radar-item krijgt de promoted_atom_id-marker."""
    it, reden = _signaal_guards(st, rid)
    if it is None:
        return None, reden
    content = (it.get("content") or "").strip()
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
