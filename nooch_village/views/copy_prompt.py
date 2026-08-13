"""Copy Prompt Generator — de policies van een rol als kant-en-klare prompt voor een extern model.

Waarom deze view bestaat: de copywriter schrijft in ChatGPT/Gemini/Claude, maar de tone of voice
en de position statements leven als governance-eigendom in de cockpit. Zonder brug knipt en plakt
iemand die tekst handmatig, en dan drijft de kopie af van het origineel. Deze pagina bouwt de
prompt bij elke lading opnieuw uit de AttachmentStore, zodat er precies één waarheid blijft
(CLAUDE.md, reference-don't-copy).

Er staat hier daarom GEEN policy-tekst en geen policy-id. Alles komt uit
`artefacts.serialize_context()` — dezelfde bron als `/context`, de systeemprompt voor AI-vervullers.
Wijzig een policy in de UI en de volgende prompt draagt de nieuwe tekst; archiveer hem en hij
verdwijnt.

Governeerde view: alle vormgeving komt uit het designsysteem (`nooch.css`). Referentie is de
Claims-checker (`views/claims.py`): formulier, knop, gegenereerd blok, kopieerknop. Geen inline
styles, geen eigen klasse-familie.
"""
from __future__ import annotations

import re
import urllib.parse

from nooch_village import artefacts
from nooch_village.cockpit2_util import _DS_LINK, _nav, _name
from nooch_village.web_base import _e, _field, _page

# ── De drie selectors ────────────────────────────────────────────────────────────────────────
#
# Formaat was de verkeerde hoofdas: email/social/product verschilt in VORM, nauwelijks in inhoud.
# De as die de tekst wél stuurt is doel × lezer × formaat-als-stem.
#
# Alles hieronder is een KEUZELIJST met uitleg, geen schrijfregel. De schrijfregels staan in de
# policies (COPYCHECK-001, TONEOFVOICE-001, POSITIONSTAT-001) en worden daar gelezen — hier staat
# alleen wat de gebruiker kiest en hoe die keuze in de prompt landt. Zou de craft-tekst hier staan,
# dan drijft hij af van de policy zodra iemand er een bijwerkt.

# 1. DOEL — gegrond in de Open Door-pillar: informeer, overtuig niet, laat de lezer concluderen.
# Er staat bewust geen 'hard sell' in de lijst: een optie die er staat, wordt gekozen.
DOELEN = [
    ("informeren", "The reader knows something afterwards they did not know before. No ask."),
    ("nieuwsgierig maken", "The reader wants to read on. Curiosity, not a purchase."),
    ("zacht overtuigen", "Two worlds side by side; the logic does the work. Never a hard sell."),
]

# 2. AWARENESS — hoe ver de lezer is. De standaard-Nooch-lezer vond Nooch zonder te zoeken: geen
# activist, geen insider, nieuwsgierig maar niet overtuigd. Het ONWETENDE uiteinde staat rijk
# beschreven; verderop laat je de bruggen weg en veronderstel je meer.
AWARENESS = [
    ("just browsing",
     "Found Nooch without looking for it. Does NOT know that sneakers are made from oil, what a "
     "batch is, that vegan is not the same as plastic-free, that a minimum order quantity exists, "
     "or that 'biodegradable' is a regulated claim. Build every bridge; assume nothing."),
    ("knows approximately",
     "Knows the problem (plastic, throwaway shoes) but not the details. Skip the basic bridges; "
     "still answer the four questions explicitly."),
    ("knows exactly",
     "Existing customer. Do not explain the problem again. Explain what is NEW, and be concrete."),
]

# De vier vragen die deze lezer heeft. Ze zijn de doel-ankers van elke tekst: een tekst die er geen
# enkele beantwoordt, informeert niet — hij vult ruimte.
LEZERSVRAGEN = [
    "What makes this different?",
    "Why do I have to wait?",
    "Is this for me?",
    "Is it real?",
]

# 3. FORMAAT → STEM. Formaat is niet dood, maar het is een jasje: elke keuze zet de STEM, en de
# stem doet het werk dat het losse register eerst deed.
FORMATEN = [
    ("homepage / product", "Brand voice. Short, factual, no build-up."),
    ("email", "Stefan and Lotte, personally. Warm, direct, never PR."),
    ("character social", "A dry one-liner. The observation carries it, not a joke."),
    ("field note", "Stefan, honest — including the bad news. No polish over a setback."),
]

LAAG_BODEM, LAAG_KADER, LAAG_MERK, LAAG_ROL = "bodem", "kader", "merk", "rol"

LAAG_LABEL = {
    LAAG_KADER: "Circle governance",
    LAAG_MERK: "Brand voice",
    LAAG_ROL: "This role's policies",
}
# Standaard aan/uit per laag. `bodem` staat er niet in: die is niet uitzetbaar.
LAAG_DEFAULT = {LAAG_KADER: False, LAAG_MERK: True, LAAG_ROL: True}

# Waaraan herken je de merk-laag? Aan het domein dat de rol houdt, niet aan zijn id — een id kan
# hernoemd worden, een domein is governance. Fail-soft: geen match → de policy valt in `kader`.
_MERK_DOMEINEN = ("brand positioning", "design system")


def _laag_van(item: dict, wortel_id: str, records) -> str:
    """In welke laag hoort deze policy? Bepaald uit de HERKOMST, niet uit de titel."""
    herkomst = item.get("origin_id") or ""
    if not herkomst:
        return LAAG_ROL                                   # eigen policy van de schrijvende rol
    if herkomst == wortel_id:
        return LAAG_KADER
    rec = records.get(herkomst)
    domeinen = {str(d).lower() for d in (getattr(getattr(rec, "definition", None), "domains", None) or [])}
    return LAAG_MERK if domeinen & set(_MERK_DOMEINEN) else LAAG_KADER


def _policy_items(ctx: dict, records=None, *, uit: set | None = None) -> list[dict]:
    """Eigen + geërfde policies, elk met zijn laag en of hij AAN staat.

    Volgorde: geërfd eerst (de wortel bepaalt het kader), daarna de eigen policies van de rol.
    `uit` = expliciet uitgezette policy-ids; die overrulen de laag-default."""
    blok = ctx.get("policies") or {}
    uit = uit or set()
    wortel = ""
    if records is not None:
        try:
            from nooch_village import org
            keten = org.breadcrumb(records.all(), (ctx.get("role") or {}).get("id") or "")
            wortel = keten[0] if keten else ""
        except Exception:                                 # noqa: BLE001 — weergave mag nooit breken
            wortel = ""
    items = []
    for a in blok.get("inherited") or []:
        items.append({**a, "herkomst": a.get("origin_path") or ""})
    for a in blok.get("own") or []:
        items.append({**a, "herkomst": "", "origin_id": ""})
    for it in items:
        laag = _laag_van(it, wortel, records) if records is not None else LAAG_ROL
        it["laag"] = laag
        it["aan"] = LAAG_DEFAULT.get(laag, True) and it.get("id") not in uit
    return items


def _strategie_regels() -> list[str]:
    """De strategie uit `config/strategy.json` — mens-bewerkbaar, één bron. Fail-soft: geen bestand
    of kapotte json → geen strategie-blok, nooit een verzonnen vervanger."""
    import json as _json
    import os as _os
    pad = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                        "config", "strategy.json")
    try:
        with open(pad, encoding="utf-8") as fh:
            data = _json.load(fh)
    except (OSError, ValueError):
        return []
    return [str(x) for x in (data.get("strategy") or []) if str(x).strip()][:8]


def _uitleg(opties: list, keuze: str) -> str:
    return dict(opties).get(keuze, "")


def bouw_prompt(ctx: dict, *, soort: str = "", brief: str = "", items: list | None = None,
                doel: str = "", awareness: str = "") -> str:
    """De prompt als platte tekst. Elke policy-body gaat er letterlijk in; deze functie
    interpreteert of verkort niets, want dan zou ze de policy herschrijven."""
    rol = ctx.get("role") or {}
    L = ["You are writing copy for the role below.", "",
         "Everything between the POLICIES markers is governance-owned text from the Nooch "
         "cockpit. It is not advice and not a starting point. Follow it literally.", "",
         "=== ROLE ===",
         f"Name: {rol.get('name') or '—'}",
         f"Purpose: {rol.get('purpose') or '—'}"]
    accs = rol.get("accountabilities") or []
    if accs:
        L.append("Accountabilities:")
        L += [f"- {a}" for a in accs]

    # De bodem: waar Nooch voor bestaat. Altijd mee, niet uitzetbaar — een tekst die hierbuiten
    # valt is geen Nooch-tekst.
    from nooch_village.mission import ANCHOR_PURPOSE
    L += ["", "=== WHAT NOOCH IS FOR (always applies) ===", ANCHOR_PURPOSE]
    strat = _strategie_regels()
    if strat:
        L += ["Strategy:"] + [f"- {r}" for r in strat]

    # === READER === — wie leest dit, en wat weet hij niet. Dit blok bepaalt hoeveel je uitlegt;
    # zonder hem schrijft het model voor een insider die niet bestaat.
    aw_uitleg = _uitleg(AWARENESS, awareness)
    L += ["", "=== READER ==="]
    if awareness:
        L += [f"Where they are: {awareness}", aw_uitleg]
    else:
        L.append("Not specified — assume the default Nooch reader: found us without looking, "
                 "curious but not convinced, no insider knowledge.")
    L += ["The four questions this reader has, in this order:"] + [f"- {v}" for v in LEZERSVRAGEN]
    if awareness == AWARENESS[0][0]:
        L.append("Answer all four explicitly. Build every bridge — assume no prior knowledge.")
    elif awareness == AWARENESS[-1][0]:
        L.append("Do not re-explain the problem. Focus on what is new and be concrete.")

    L += ["", "=== ASSIGNMENT ==="]
    if doel:
        L.append(f"Goal: {doel} — {_uitleg(DOELEN, doel)}")
    L.append(f"Format and voice: {soort or '(not specified)'}"
             + (f" — {_uitleg(FORMATEN, soort)}" if _uitleg(FORMATEN, soort) else ""))
    L += ["Brief:", (brief or "(no brief given)").strip()]

    # Alleen wat AAN staat. Een uitgezette policy verdwijnt echt: hij mag niet als "uitgezet maar
    # toch meegestuurd" in de prompt blijven staan, want dan is de knop een leugen.
    alle_items = items if items is not None else _policy_items(ctx)
    items = [a for a in alle_items if a.get("aan", True)]
    L += ["", f"=== POLICIES ({len(items)}) ==="]
    if not items:
        # Twee verschillende situaties, en ze horen verschillend te lezen: een rol ZONDER policies
        # is een governance-gat (ga het halen), alles uitgezet is een keuze van de gebruiker (zet
        # er een aan). Ze op één zin gooien verbergt het eerste achter het tweede.
        L.append("(none — this role has no policies; ask the domain owner before writing)"
                 if not alle_items else
                 "(all policies are switched off — switch at least one on, or you are writing "
                 "without any governance)")
    for a in items:
        herkomst = f" ({a['herkomst']})" if a.get("herkomst") else ""
        L += ["", f"--- {a.get('id', '')} · {a.get('title') or ''}{herkomst} ---",
              (a.get("body") or "").strip()]


    # Twee versies in plaats van één. Reden: elke check in de policies is een verbod, dus één
    # versie convergeert naar de vlakste tekst die niets overtreedt en de stem verdampt.
    # Twee polen op dezelfde feiten maken de spanwijdte zichtbaar en laten de mens kiezen of
    # monteren. Géén derde "normale" versie: die is de vlakke tekst waar de klacht over ging, en
    # het ijkpunt staat al in de policies (de calibratietekst).
    # De twee polen hangen nu aan de STEM (het formaat) en het DOEL, niet aan een los register:
    # die twee zetten de toon al, en een derde as ernaast liet de schrijver kiezen tussen twee
    # dingen die hetzelfde bedoelden.
    stem = _uitleg(FORMATEN, soort) or "the voice the policies describe"
    L += ["", "=== OUTPUT ===",
          "Write two versions of the same text. Same brief, same facts, same claims. Only the "
          "emotional charge differs. Both obey every policy above, including every hard limit. A "
          "version that breaks a hard limit is not a bolder version, it is a rejected one.",
          "",
          f"1. VERSION A — {stem} at the limit.",
          "   That voice at the highest intensity that still passes every check. Walk up to the "
          "fence the hard limits set and stop there. Not louder: sharper. The reference for how "
          "far is the calibration text named in the policies, not your own instinct.",
          "",
          "2. VERSION B — opposite charge.",
          "   The same facts with the emotional charge inverted. Where A makes the reader bristle, "
          "this one makes them grin at the same absurdity, or the other way round. Same voice, "
          "same goal — only the charge flips.",
          "",
          "Then a line containing only ---",
          "",
          "Then one check table for both versions: one row per check that is actually named in "
          "the policies, with PASS or FAIL per version (A, B). For every FAIL, quote the sentence "
          "and give a rewrite. Do not invent checks the policies do not name.",
          "",
          "If the brief and a policy contradict each other, follow the policy and say so in one "
          "line under the table."]
    return "\n".join(L)


def _cl_knoppen(naam: str, opties: list[tuple[str, str]], huidig: str) -> str:
    """Segmented picker als submit-knoppen: klikken verstuurt het formulier met die waarde, zodat
    de al ingetypte brief niet verloren gaat. Zonder JS, zonder nieuwe klasse (`.cl-filter`)."""
    uit = "<div class='cl-bar'>"
    for waarde, label in opties:
        aan = " on" if waarde == huidig else ""
        uit += (f"<button class='cl-filter{aan}' type='submit' name='set_{_e(naam)}' "
                f"value='{_e(waarde)}'>{_e(label)}</button>")
    return uit + "</div>"


def _rolkiezer(st) -> str:
    """Geen rol meegegeven: toon de rollen en cirkels die zelf policies hebben. Zo hoeft er nergens
    een rol-id in de code te staan — de organisatie bepaalt de lijst."""
    rijen = ""
    for rec in st.records.all():
        pols = st.att.list(rec.id, "policy")
        if not pols:
            continue
        q = urllib.parse.urlencode({"rol": rec.id})
        rijen += (f"<div class='card'><b>{_e(_name(rec))}</b> "
                  f"<span class='pill'>{len(pols)}</span>"
                  f"<p class='muted'>{_e(', '.join(p.id for p in pols))}</p>"
                  f"<a class='btn sm' href='/copy-prompt?{q}'>Use these policies</a></div>")
    if not rijen:
        rijen = "<div class='card'><p class='muted'>No role has policies yet.</p></div>"
    return ("<p class='ptitle'>Whose policies should the prompt carry?</p>"
            "<p class='muted'>Pick the role that owns the copy policies. The generator reads "
            "them live, including everything that role inherits.</p>" + rijen)


def render_copy_prompt(st, rol: str = "", soort: str = "", brief: str = "", uit: str = "",
                       doel: str = "", awareness: str = "") -> str:
    """De pagina. `st` is `_Stores`; alle inhoud komt uit de records en de AttachmentStore."""
    if not rol or st.records.get(rol) is None:
        binnen = _rolkiezer(st)
        return _page("Copy prompt", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>"
                                    f"<h1 class='ptitle'>Copy prompt</h1>{binnen}</div>")

    ctx = artefacts.serialize_context(rol, st.records, st.att)
    uit_set = {x.strip() for x in (uit or "").split(",") if x.strip()}
    items = _policy_items(ctx, st.records, uit=uit_set)
    aan = [a for a in items if a.get("aan")]

    # De flow: drie stappen, dan de prompt. Elke stap is één vraag met uitleg onder de knoppen —
    # de gebruiker moet kunnen zien wát hij kiest, niet alleen een label.
    def _stap(nr, titel, naam, opties, huidig, hulp=""):
        knoppen = _cl_knoppen(naam, [(n, n) for n, _ in opties], huidig)
        uitleg = _uitleg(opties, huidig)
        blok = f"<p class='ptitle'>{nr}. {_e(titel)}</p>{knoppen}"
        if uitleg:
            blok += f"<p class='muted'>{_e(uitleg)}</p>"
        elif hulp:
            blok += f"<p class='muted'>{_e(hulp)}</p>"
        return blok

    formulier = (
        f"<form class='qadd-form' method='get' action='/copy-prompt'>"
        f"<input type='hidden' name='rol' value='{_e(rol)}'>"
        f"<input type='hidden' name='doel' value='{_e(doel)}'>"
        f"<input type='hidden' name='awareness' value='{_e(awareness)}'>"
        f"<input type='hidden' name='soort' value='{_e(soort)}'>"
        f"<input type='hidden' name='uit' value='{_e(uit)}'>"
        + _stap(1, "What should this text do?", "doel", DOELEN, doel,
                "Inform, don't convert — the reader draws their own conclusion.")
        + _stap(2, "Who is reading it?", "awareness", AWARENESS, awareness,
                "The default Nooch reader found us without looking, and knows none of the jargon.")
        + _stap(3, "Where does it go?", "soort", FORMATEN, soort,
                "Format is a jacket: it sets the voice, not the content."))

    briefveld = _field("What is this text about? What must the reader know or do afterwards?",
                       "brief", kind="textarea", value=brief, fid="cp-brief",
                       attrs="rows='8'")
    formulier += "<p class='ptitle'>4. The brief</p>" + briefveld

    formulier += "<button class='btn ok' type='submit'>Generate prompt</button></form>"

    # De stack, per laag, met een schakelaar per policy. Een uitgezette policy verdwijnt uit de
    # PROMPT — de knop is geen filter op de weergave maar op wat het model te lezen krijgt.
    stack = ["<div class='card'><b>Policy stack</b>"
             "<p class='muted'>Always on: what Nooch is for, plus the strategy. Everything below "
             "is a choice — switch one off and it leaves the prompt.</p>"]
    for laag in (LAAG_ROL, LAAG_MERK, LAAG_KADER):
        in_laag = [a for a in items if a.get("laag") == laag]
        if not in_laag:
            continue
        stack.append(f"<p class='ptitle'>{_e(LAAG_LABEL[laag])}</p>")
        knoppen = []
        for a in in_laag:
            pid = a.get("id", "")
            nieuw = (uit_set - {pid}) if pid in uit_set else (uit_set | {pid})
            q = urllib.parse.urlencode({"rol": rol, "doel": doel, "awareness": awareness,
                                        "soort": soort, "brief": brief,
                                        "uit": ",".join(sorted(nieuw))})
            aan_nu = a.get("aan")
            knoppen.append(
                f"<a class='cl-filter{" on" if aan_nu else ""}' href='/copy-prompt?{q}'>"
                f"{"✓" if aan_nu else "○"} {_e(a.get("title") or pid)}</a>")
        stack.append("<div class='cl-filters'>" + "".join(knoppen) + "</div>")
    stack.append("</div>")

    herkomst = "".join(
        f"<span class='chip'>{_e(a.get('id', ''))}{_e(' ' + a['herkomst'] if a.get('herkomst') else '')}</span>"
        for a in aan)
    prompt = bouw_prompt(ctx, soort=soort, brief=brief, items=items, doel=doel,
                         awareness=awareness)
    uitvoer = (
        "<div class='card'>"
        "<b>Your prompt</b> <button class='btn sm' type='button' data-cp-kopieer>Copy prompt</button>"
        f"<p class='muted'>Built from {len(aan)} live policies: {herkomst or '—'}. "
        "Paste it into ChatGPT, Gemini or Claude. Change a policy in the cockpit and the next "
        "prompt carries the change.</p>"
        + _field("Prompt", "prompt", kind="textarea", value=prompt, fid="cp-prompt",
                 attrs="readonly rows='24'")
        + "</div>")

    hoofd = (f"<h1 class='ptitle'>Copy prompt</h1>"
             f"<p class='muted'>Policies of {_e(_name(st.records.get(rol)))}. "
             f"<a href='/node?id={_e(urllib.parse.quote(rol))}&tab=policies'>Read or change them</a> "
             f"(governance-owned: not everyone may edit).</p>"
             f"{''.join(stack)}{formulier}{uitvoer}")
    return _page("Copy prompt",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{hoofd}</div>{_KOPIEER_JS}")


# Kopiëren via de clipboard-API, identiek aan het patroon in views/claims.py. Zonder JS blijft de
# tekst gewoon selecteerbaar in het tekstvak — progressive enhancement.
_KOPIEER_JS = """<script>(function(){
 document.addEventListener('click',function(e){
   var k=e.target.closest&&e.target.closest('[data-cp-kopieer]');if(!k)return;
   var t=document.getElementById('cp-prompt');if(!t||!navigator.clipboard)return;
   navigator.clipboard.writeText(t.value).then(function(){
     k.textContent='Copied';setTimeout(function(){k.textContent='Copy prompt';},1600);});
 });
})();</script>"""
