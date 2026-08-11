"""Copy Prompt Generator — de policies van een rol als kant-en-klare prompt voor een extern model.

Waarom deze view bestaat: de copywriter schrijft in ChatGPT/Gemini/Claude, maar de tone of voice
en de position statements leven als governance-eigendom in de cockpit. Zonder brug knipt en plakt
iemand die tekst handmatig, en dan drijft de kopie af van het origineel. Deze pagina bouwt de
prompt bij elke lading opnieuw uit de AttachmentStore, zodat er precies één waarheid blijft
(CLAUDE.md, reference-don't-copy).

Er staat hier daarom GEEN policy-tekst, geen policy-id en geen lijst met registers. Alles komt uit
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

# Contenttypes zijn een keuze van deze view, geen feit dat elders woont: ze staan in geen enkele
# policy en in geen enkele store. Vandaar wél een literal (anders dan de registers hieronder).
_SOORTEN = ["Email", "Social post", "Product page", "Pillar page", "FAQ", "Field Note"]

# Een register-bullet in een policy-body: "* THINK: huh, ik had er nog nooit zo naar gekeken".
# De naam is ALL-CAPS zodat een gewone Do/Don't-bullet er nooit per ongeluk in valt.
_REGISTER_BULLET = re.compile(r"^\s*[*-]\s*([A-Z][A-Z0-9 ]{1,15}?)\s*:\s*(.*)$")


def _kopregel(regel: str) -> str:
    """Genormaliseerde kop van een policy-regel: markdown-opmaak eraf, kleingeschreven.
    "**Register**" en "## Register:" worden allebei "register"."""
    return regel.strip().strip("*#").strip().rstrip(":").strip().lower()


def registers_uit_policies(bodies: list[str]) -> list[tuple[str, str]]:
    """De registers zoals ze in de policy-tekst staan, niet zoals deze view ze zou verzinnen.

    Contract met de policy-schrijver: onder een kop `Register` staan bullets in de vorm
    `* NAAM: omschrijving`, met NAAM in hoofdletters. Verandert de policy de registers, dan
    verandert de picker mee. Vindt de parser niets, dan valt de UI terug op een vrij tekstveld —
    fail-soft, want een tool die breekt bij een policy-wijziging is erger dan een tool zonder
    knopjes.
    """
    gevonden: list[tuple[str, str]] = []
    gezien: set[str] = set()
    for body in bodies:
        regels = (body or "").splitlines()
        i = 0
        while i < len(regels):
            if _kopregel(regels[i]) != "register":
                i += 1
                continue
            aantal_in_blok = 0
            j = i + 1
            while j < len(regels):
                m = _REGISTER_BULLET.match(regels[j])
                if m:
                    naam = m.group(1).strip()
                    if naam.isupper():
                        aantal_in_blok += 1
                        if naam not in gezien:
                            gezien.add(naam)
                            gevonden.append((naam, m.group(2).strip()))
                elif regels[j].strip() and aantal_in_blok:
                    break          # eerste gewone regel ná de bullets sluit het blok
                j += 1
            i = j + 1
    return gevonden


def _policy_items(ctx: dict) -> list[dict]:
    """Eigen + geërfde policies als één vlakke lijst, elk met zijn herkomst. Volgorde: geërfd
    eerst (de wortel bepaalt het kader), daarna de eigen policies van de rol."""
    blok = ctx.get("policies") or {}
    items = []
    for a in blok.get("inherited") or []:
        items.append({**a, "herkomst": a.get("origin_path") or ""})
    for a in blok.get("own") or []:
        items.append({**a, "herkomst": ""})
    return items


def bouw_prompt(ctx: dict, *, soort: str = "", register: str = "", register_uitleg: str = "",
                brief: str = "") -> str:
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

    items = _policy_items(ctx)
    L += ["", f"=== POLICIES ({len(items)}) ==="]
    if not items:
        L.append("(none — this role has no policies; ask the domain owner before writing)")
    for a in items:
        herkomst = f" ({a['herkomst']})" if a.get("herkomst") else ""
        L += ["", f"--- {a.get('id', '')} · {a.get('title') or ''}{herkomst} ---",
              (a.get("body") or "").strip()]

    L += ["", "=== ASSIGNMENT ==="]
    L.append(f"Content type: {soort or '(not specified)'}")
    if register:
        L.append(f"Register: {register}" + (f" — {register_uitleg}" if register_uitleg else ""))
    L += ["Brief:", (brief or "(no brief given)").strip()]

    L += ["", "=== OUTPUT ===",
          "1. Write the copy. Start with it. No preamble, no explanation of your approach.",
          "2. Then a line containing only ---",
          "3. Then a check table. Read the policies above, find every named check in them, and "
          "list each one with PASS or FAIL. For every FAIL, quote the offending sentence and give "
          "a rewrite.",
          "4. If the brief and a policy contradict each other, follow the policy and say so in "
          "one line under the table."]
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


def render_copy_prompt(st, rol: str = "", soort: str = "", register: str = "",
                       brief: str = "") -> str:
    """De pagina. `st` is `_Stores`; alle inhoud komt uit de records en de AttachmentStore."""
    if not rol or st.records.get(rol) is None:
        binnen = _rolkiezer(st)
        return _page("Copy prompt", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>"
                                    f"<h1 class='ptitle'>Copy prompt</h1>{binnen}</div>")

    ctx = artefacts.serialize_context(rol, st.records, st.att)
    items = _policy_items(ctx)
    registers = registers_uit_policies([a.get("body") or "" for a in items])
    reg_uitleg = dict(registers).get(register, "")

    formulier = (
        f"<form class='qadd-form' method='get' action='/copy-prompt'>"
        f"<input type='hidden' name='rol' value='{_e(rol)}'>"
        f"<input type='hidden' name='soort' value='{_e(soort)}'>"
        f"<input type='hidden' name='register' value='{_e(register)}'>"
        f"<p class='ptitle'>1. What are you writing?</p>"
        f"{_cl_knoppen('soort', [(s, s) for s in _SOORTEN], soort)}"
        f"<p class='ptitle'>2. Register</p>")
    if registers:
        formulier += (_cl_knoppen("register", [(n, n) for n, _ in registers], register)
                      + (f"<p class='muted'>{_e(reg_uitleg)}</p>" if reg_uitleg else ""))
    else:
        # Fail-soft: geen register-blok in de policies gevonden → vrij veld in plaats van niets.
        formulier += (_field("Register", "register", value=register, fid="cp-reg",
                             placeholder="no register block found in the policies")
                      + "<p class='muted'>No register list in the policies. Add a "
                        "<b>Register</b> heading with <b>* NAME: description</b> bullets and this "
                        "picker fills itself.</p>")
    briefveld = _field("What is this text about? What must the reader know or do afterwards?",
                       "brief", kind="textarea", value=brief, fid="cp-brief",
                       attrs="rows='8'")
    formulier += ("<p class='ptitle'>3. The brief</p>" + briefveld
                  + "<button class='btn ok' type='submit'>Generate prompt</button></form>")

    herkomst = "".join(
        f"<span class='chip'>{_e(a.get('id', ''))}{_e(' ' + a['herkomst'] if a.get('herkomst') else '')}</span>"
        for a in items)
    prompt = bouw_prompt(ctx, soort=soort, register=register, register_uitleg=reg_uitleg,
                         brief=brief)
    uitvoer = (
        "<div class='card'>"
        "<b>Your prompt</b> <button class='btn sm' type='button' data-cp-kopieer>Copy prompt</button>"
        f"<p class='muted'>Built from {len(items)} live policies: {herkomst or '—'}. "
        "Paste it into ChatGPT, Gemini or Claude. Change a policy in the cockpit and the next "
        "prompt carries the change.</p>"
        + _field("Prompt", "prompt", kind="textarea", value=prompt, fid="cp-prompt",
                 attrs="readonly rows='24'")
        + "</div>")

    hoofd = (f"<h1 class='ptitle'>Copy prompt</h1>"
             f"<p class='muted'>Policies of {_e(_name(st.records.get(rol)))}. "
             f"<a href='/node?id={_e(urllib.parse.quote(rol))}&tab=policies'>Read or change them</a> "
             f"(governance-owned: not everyone may edit).</p>"
             f"{formulier}{uitvoer}")
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
