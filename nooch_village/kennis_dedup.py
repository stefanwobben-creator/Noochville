"""kennis_dedup — de voorkant-poort: weet-ik-dit-al vóór een kaartje geboren wordt (founder 23 jul).

De knel (gemeten op de 23-juli-data): de kennislaag verzadigt. Signalen klonteren op een handvol
materialen (mycelium 29x, bio-based 23x, PHA 11x in de radar) terwijl PHA en bio-based al geborgd zijn
als standpunt met tientallen bewijzen. En over de 337 laag-1 kaartjes staan 15 tot 23 samenvoegbare
clusters: bijna-woordelijke duplicaten ("EU Ecolabel koppelt textiel aan de circulaire economie" x2,
"Ghanese biobased rubber (NR)" x2). Oorzaak: ELK aanmaakpad (radar_promote, intake, staging-commit)
dedupt alleen EXACT — dezelfde genormaliseerde content+bron, dezelfde claim, of dezelfde URL. Een
near-duplicaat (andere bron, iets andere formulering, NL vs EN) glipt er dus doorheen en wordt een
tweede kaartje.

Deze poort vult dat gat met één herbruikbare beoordeling die de aanmaakpaden aanroepen VOORDAT ze een
kaartje toevoegen. Ze leunt op wat er al is (`find_claim_equal` voor exact, `gelijkende` voor lexicale
overlap) en zet er één betekenis-check (LLM) bovenop voor het grijze gebied, want juist parafrase en
NL/EN missen de lexicale checks.

FAIL-OPEN, bewust asymmetrisch (zelfde principe als de escaleer-splitsing): bij twijfel maak je een
NIEUW kaartje, nooit stil stapelen. Een gemist duplicaat kost je één klik bij de merge-lus; een echt-
nieuw inzicht dat stil op een bestaand kaartje wordt gestapeld ben je kwijt. Daarom stapelt de poort
alleen bij exacte gelijkheid, zeer hoge overlap, of een expliciet LLM-"zelfde"; al het andere is 'nieuw'
(en in de grijze band zonder LLM: 'twijfel' = nieuw kaartje mét markering, zodat de mens het ziet).

Pure functies, injecteerbare reason_fn (testbaar zonder netwerk).
"""
from __future__ import annotations

# Drempels op de Jaccard-woordoverlap van `NotesStore.gelijkende`:
#   >= _STAPEL_HARD : near-woordelijk gelijk → deterministisch stapelen, geen LLM nodig.
#   [_BAND, _STAPEL_HARD) : grijs gebied → laat een LLM beslissen (parafrase/NL-EN).
#   <  _BAND : te ver uit elkaar → nieuw kaartje.
_STAPEL_HARD = 0.80
_BAND = 0.35

# Semantische laag (kennis_embeddings): cosinus-drempels op de betekenis-buur.
#   >= _SEM_KANDIDAAT : dicht genoeg in de betekenisruimte om als kandidaat aan de LLM voor te leggen.
#   >= _SEM_TWIJFEL   : zó dichtbij dat we het zonder LLM-oordeel toch markeren (twijfel), i.p.v. negeren.
# Embeddings stapelen NOOIT deterministisch: alleen een expliciet LLM-"zelfde" stapelt (twee feiten over
# hetzelfde onderwerp liggen dicht bij elkaar maar zijn geen duplicaat).
_SEM_KANDIDAAT = 0.82
_SEM_TWIJFEL = 0.90


def _llm_zelfde(nieuw: str, bestaand: str, reason_fn) -> str | None:
    """Vraagt de LLM of twee claims HETZELFDE inzicht uitdrukken. Geeft 'zelfde', 'anders' of None
    (geen LLM). Streng: alleen 'zelfde' als het echt dezelfde bewering is, niet slechts hetzelfde
    onderwerp — twee feiten over mycelium zijn 'anders'."""
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn
    try:
        prompt = (
            "Twee kennis-kaartjes. Drukken ze HETZELFDE inzicht uit (zou het tweede een duplicaat van "
            "het eerste zijn), of zijn het verschillende beweringen (ook als ze over hetzelfde onderwerp "
            "gaan)?\n"
            "Streng: alleen 'ZELFDE' als de kernbewering echt dezelfde is. Zelfde onderwerp maar een "
            "ander feit, cijfer, of andere invalshoek = 'ANDERS'.\n\n"
            f"KAART 1 (bestaand): {bestaand[:400]}\n"
            f"KAART 2 (nieuw):    {nieuw[:400]}\n\n"
            "Antwoord met EXACT één woord: ZELFDE of ANDERS.")
        out = reason_fn(prompt, call_site="kennis_dedup", max_tokens=8)
    except Exception:
        return None
    if not out:
        return None
    low = out.strip().lower()
    if "zelfde" in low:
        return "zelfde"
    if "anders" in low:
        return "anders"
    return None


def _semantiek_voor(notes, semantiek):
    """Bepaal de te gebruiken SemantiekIndex. `semantiek` expliciet meegegeven → die (of False = uit).
    None → bouw de default naast notes.json. Fail-soft: import/pad-fout → geen semantische laag."""
    if semantiek is not None:
        return semantiek or None
    try:
        from nooch_village.kennis_embeddings import SemantiekIndex
        return SemantiekIndex(getattr(notes, "_path", "data/notes.json"))
    except Exception:
        return None


def beoordeel_kaart(claim: str, notes, *, reason_fn=None, semantiek=None,
                    stapel_hard: float = _STAPEL_HARD, band: float = _BAND) -> dict:
    """Weet-ik-dit-al-poort voor één kandidaat-claim tegen de bestaande bibliotheek.

    Twee kandidaat-ophalers voeden één LLM-oordeler: lexicaal (`gelijkende`, woord-overlap) en
    semantisch (`SemantiekIndex`, betekenis-buur via embeddings — vangt parafrase en NL/EN die
    lexicaal onzichtbaar zijn). Embeddings stapelen nooit uit zichzelf: alleen een LLM-"zelfde"
    stapelt. `semantiek`: None = default-index naast notes.json; False = puur lexicaal; of een
    eigen index-object (test).

    Geeft een dict met 'verdict':
      - 'nieuw'   : geen match → maak een nieuw kaartje.
      - 'stapel'  : dit staat er al → koppel de herkomst aan 'kaart_id' i.p.v. een tweede kaartje.
      - 'twijfel' : dichtbij (lexicaal of sterk semantisch) maar geen LLM-bevestiging → maak een
                    NIEUW kaartje, maar markeer het (fail-open: nooit stil stapelen).
    Extra velden waar zinvol: 'kaart_id', 'score', 'reden'. Fail-open: elke fout → 'nieuw'.
    """
    claim = (claim or "").strip()
    if not claim:
        return {"verdict": "nieuw"}
    try:
        exact = notes.find_claim_equal(claim)
        if exact:
            return {"verdict": "stapel", "kaart_id": exact, "score": 1.0, "reden": "exacte claim"}
        g = notes.gelijkende(claim, drempel=band)
    except Exception:
        return {"verdict": "nieuw"}
    # Near-woordelijk gelijk: deterministisch stapelen (geen LLM nodig).
    if g and g[2] >= stapel_hard:
        return {"verdict": "stapel", "kaart_id": g[0], "score": g[2],
                "reden": f"near-woordelijk gelijk ({g[2]:.2f})"}

    # Kandidaten verzamelen: lexicaal (grijze band) + semantisch (betekenis-buur).
    kandidaten: list[tuple[str, str, float, str]] = []   # (note_id, claim, score, bron)
    if g and g[2] >= band:
        kandidaten.append((g[0], g[1], g[2], "lex"))
    idx = _semantiek_voor(notes, semantiek)
    if idx is not None:
        try:
            sem = idx.candidate(claim, notes, drempel=_SEM_KANDIDAAT)
        except Exception:
            sem = None
        if sem:
            kandidaten.append((sem[0], sem[1], sem[2], "sem"))
    if not kandidaten:
        return {"verdict": "nieuw"}

    # Per kaart de sterkste score houden, hoogste eerst; hooguit 2 langs de LLM (bounded kost).
    beste: dict[str, tuple[str, float, str]] = {}
    for nid, ncl, sco, bron in kandidaten:
        if nid not in beste or sco > beste[nid][1]:
            beste[nid] = (ncl, sco, bron)
    gerangschikt = sorted(([nid, *v] for nid, v in beste.items()), key=lambda r: r[2], reverse=True)[:2]

    twijfel: tuple[str, float, str] | None = None   # sterkste kandidaat die markering verdient
    for nid, ncl, sco, bron in gerangschikt:
        oordeel = _llm_zelfde(claim, ncl, reason_fn)
        if oordeel == "zelfde":
            return {"verdict": "stapel", "kaart_id": nid, "score": sco,
                    "reden": f"LLM: zelfde inzicht ({bron})"}
        if oordeel is None:                          # geen LLM-oordeel: onthoud als twijfel-kandidaat
            markeer = (bron == "lex") or (bron == "sem" and sco >= _SEM_TWIJFEL)
            if markeer and (twijfel is None or sco > twijfel[1]):
                twijfel = (nid, sco, bron)
        # oordeel == 'anders' → deze kaart is het niet; door naar de volgende kandidaat
    if twijfel is not None:
        return {"verdict": "twijfel", "kaart_id": twijfel[0], "score": twijfel[1],
                "reden": f"dichtbij ({twijfel[2]}), geen LLM-bevestiging"}
    return {"verdict": "nieuw"}
