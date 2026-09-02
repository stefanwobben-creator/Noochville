"""Copy checker — laag 1: wat deterministisch te toetsen is tegen de copy-policies.

De tweelingpagina van `/copy-prompt`. De generator zet de policies VOORAF in een prompt; deze
pagina toetst een tekst ACHTERAF tegen dezelfde policies. Beide lezen uit de AttachmentStore, dus
wijzig een policy en beide veranderen mee (CLAUDE.md, reference-don't-copy).

Drie dingen die deze view bewust wél doet, en waarom:

1. **De dekkingsregel komt uit `regels_uit()`**, niet uit `COPY_POLICIES`. Een policy zonder
   structuurblok wordt dus NIET als dekking geclaimd. STANCE-001 heeft er bewust geen — al zijn
   statements zijn houdingen, geen letterlijke nooit-schrijven-lijsten — en "gecheckt tegen STANCE"
   zou een dekking beweren die niet bestaat. Valse dekking is erger dan geen dekking.

2. **Groeperen per zin gebeurt HIER, niet in `copycheck.py`.** De checker blijft eerlijk en
   dedupet niet: noemen twee policies dezelfde zin, dan zijn dat twee bevindingen met twee
   bronpolicies. Presentatie mag samenvatten, de meting niet.

3. **Laag 2 is een knop in dezelfde kaart**, geen tweede scherm. Wat laag 1 niet kan tellen
   (houding, drift, "lasts versus lasts") gaat naar een model — met de volledige policy-tekst
   erbij, STANCE incluis, want daar wéégt hij juist wel.

Governeerde view: alle vormgeving uit het designsysteem (`nooch.css`), patroon overgenomen van
`views/claims.py` (formulier, knop, rapport) en `views/copy_prompt.py` (kopieerknop). Geen inline
styles, geen eigen klasse-familie.
"""
from __future__ import annotations

from nooch_village import copycheck
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.web_base import _e, _field, _page

#: De rol die de copy-policies bezit. Alleen gebruikt om de lezer te vertellen wáár hij moet zijn
#: als hij een regel wil wijzigen — de checker zelf schrijft niets.
EIGENAAR_ROL = "mother_earth__nooch__community_and_email"


def _groepeer(bevindingen: list[dict], tekst: str = "") -> list[dict]:
    """Bevindingen op citaat, in de volgorde waarin de zinnen in de TEKST staan.

    Eén regel per zin op het scherm, met álle bronpolicies eronder. De onderliggende lijst blijft
    ongemoeid: dit is een presentatiekeuze, geen filter.

    De volgorde is bewust die van de tekst en niet die van de bevindingen. `check_alles` loopt per
    POLICY, dus de tweede zin van een tekst kan als laatste terugkomen als alleen de derde policy
    hem noemt. Dan leest het scherm als een lijst klachten in plaats van als de tekst zelf, en moet
    de schrijver zoeken waar hij is."""
    per: dict[str, list[dict]] = {}
    for b in bevindingen:
        per.setdefault(b.get("citaat", ""), []).append(b)
    zinnen = sorted(per, key=lambda c: ((tekst or "").find(c), c))
    return [{"citaat": c, "items": per[c],
             "policies": sorted({i.get("policy", "") for i in per[c] if i.get("policy")})}
            for c in zinnen]


def _dekking(att) -> list[str]:
    """De policies die daadwerkelijk een structuurblok dragen. Dit is de enige lijst die de pagina
    als dekking mag noemen — zie punt 1 in de moduledocstring."""
    return [pid for pid, _blok in copycheck.regels_uit(att)]


def _laag2_prompt(att, tekst: str) -> str:
    """De prompt voor het oordeel dat laag 1 niet kan geven.

    Hier tellen ALLE copy-policies mee, ook die zonder blok: STANCE-001 draagt geen letterlijke
    termen maar bepaalt wel de houding, en dat is precies wat een model kan wegen."""
    delen = ["You are reviewing a piece of Nooch copy against the policies below.",
             "",
             "The deterministic checks have already run: forbidden terms, claims that need a "
             "source, counted limits. Do NOT repeat those. Judge what counting cannot reach: "
             "stance, drift, whether a word means here what the policy means by it, and whether "
             "the text would pass as Nooch if nobody told you.",
             "",
             "Quote before you judge, and say which policy grounds each remark. If a remark has "
             "no policy behind it, leave it out — that is your opinion, not our standard.",
             ""]
    for pid in copycheck.COPY_POLICIES:
        a = att.get(pid)
        if a is None:
            continue
        delen += [f"### {pid} — {(a.title or '').strip()}", (a.body or "").strip(), ""]
    delen += ["### The text", (tekst or "").strip(), ""]
    return "\n".join(delen)


def _rapport(att, tekst: str) -> str:
    bevindingen = copycheck.check_alles(tekst, att)
    dekking = _dekking(att)
    dekkingszin = (f"Checked against {', '.join(dekking)}" if dekking
                   else "No policy carries a structure block — nothing was checked")

    if not bevindingen:
        # SCHOON IS EEN UITSLAG, GEEN STILTE. "Niets gevonden" zonder te zeggen waartegen, laat de
        # lezer denken dat alles gedekt is. De dekking staat er daarom altijd bij, en met de
        # policies die er echt een blok hebben.
        kop = (f"<p class='ptitle'>✓ Nothing found</p>"
               f"<p class='muted'>{_e(dekkingszin)} — nothing found. "
               f"That is layer 1: literal terms, claims that need a source, counted limits. "
               f"Stance and drift are not counted here.</p>")
    else:
        groepen = _groepeer(bevindingen, tekst)
        rijen = ""
        for g in groepen:
            chips = "".join(f"<span class='chip'>{_e(p)}</span> " for p in g["policies"])
            regels = "".join(
                f"<li><b>{_e(i.get('regel', ''))}</b> — {_e(i.get('suggestie', ''))} "
                f"<span class='muted'>· {_e(i.get('policy', ''))}</span></li>"
                for i in g["items"])
            rijen += (f"<div class='card'><p class='ptitle'>“{_e(g['citaat'])}”</p>"
                      f"<div>{chips}</div><ul class='clean'>{regels}</ul></div>")
        kop = (f"<p class='ptitle'>{len(groepen)} sentence(s) to look at</p>"
               f"<p class='muted'>{_e(dekkingszin)}. Every finding names the policy it comes "
               f"from; a finding without one cannot exist.</p>{rijen}")

    # Laag 2 in DEZELFDE kaart: geen tweede scherm, geen tweede plakactie. De prompt draagt de
    # volledige policy-tekst mee, STANCE incluis.
    prompt = _laag2_prompt(att, tekst)
    laag2 = ("<details class='card'><summary><b>Layer 2 — the judgement counting cannot make</b>"
             "</summary>"
             "<p class='muted'>Stance, drift, whether a word means here what the policy means by "
             "it. Copy this prompt into ChatGPT, Gemini or Claude. It carries every copy policy, "
             "including the ones without a structure block.</p>"
             "<button class='btn' type='button' data-cc-kopieer>Copy the layer 2 prompt</button>"
             + _field("Layer 2 prompt", "laag2", kind="textarea", value=prompt, fid="cc-laag2",
                      attrs="rows='14' class='editor mono'")
             + "</details>")
    return f"<div class='c2-sec'>{kop}</div>{laag2}"


def render_copy_check(st, csrf_token: str = "", tekst: str = "") -> str:
    """De pagina. `st` is `_Stores`; alles komt uit de AttachmentStore."""
    formulier = (
        f"<div class='card'><h3>Check a text</h3>"
        f"<form method='post' action='/copy-check' class='qadd-form'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        + _field("Paste the copy", "tekst", kind="textarea", value=tekst, fid="cc-tekst",
                 placeholder="Email, social post, product description…", attrs="rows='10'")
        + "<div class='qadd-row'><button class='btn ok' type='submit'>Check</button></div>"
        "</form>"
        "<p class='muted'>Reads the copy policies and reports. It changes nothing — a rule is "
        "changed in the policy that carries it, not here.</p></div>")

    rapport = _rapport(st.att, tekst) if (tekst or "").strip() else ""
    hoofd = (f"<h1 class='ptitle'>Copy checker</h1>"
             f"<p class='muted'>Layer 1 checks what can be counted, grounded in the policies "
             f"themselves. Writing a new text instead? Use the "
             f"<a href='/copy-prompt'>copy prompt generator</a>.</p>"
             f"{formulier}{rapport}")
    return _page("Copy checker",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>"
                 f"<div class='c2-main roomy'>{hoofd}</div></div>{_KOPIEER_JS}")


# Kopiëren via de clipboard-API, hetzelfde patroon als views/copy_prompt.py en views/claims.py.
# Zonder JS blijft de tekst gewoon selecteerbaar — progressive enhancement.
_KOPIEER_JS = """<script>(function(){
 document.addEventListener('click',function(e){
   var k=e.target.closest&&e.target.closest('[data-cc-kopieer]');if(!k)return;
   var t=document.getElementById('cc-laag2');if(!t||!navigator.clipboard)return;
   navigator.clipboard.writeText(t.value).then(function(){
     k.textContent='Copied';setTimeout(function(){k.textContent='Copy the layer 2 prompt';},1600);});
 });
})();</script>"""
