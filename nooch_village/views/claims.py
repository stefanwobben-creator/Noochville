"""Claims-checker — de EmpCo/ACM-toets als gewoon dorpsscherm.

Governeerde view: alles komt uit het designsysteem (`nooch.css`), geen inline styles en geen
eigen klasse-familie. Het statische prototype (v1) was de visuele referentie; de pariteitstabel
staat in de PR. Waar het prototype een eigen vormtaal had (eigen kleurenpalet, serif-koppen,
gekleurde markeringen), wint het designsysteem — CLAUDE.md.

De data komt uit `claims_db` (config/claims_database.json). Deze view leest alleen; cureren
loopt via de dispatch-takken achter `_role_gate("compliance")`.
"""
from __future__ import annotations

import urllib.parse

from nooch_village import claims_db
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.web_base import _banner, _e, _field, _page

# Stoplicht → designsysteem-chip. Het prototype had een eigen rood/oranje/groen-palet;
# de chip-varianten dekken exact dezelfde drie betekenissen.
_CHIP = {"red": ("chip coral", "🔴 forbidden"),
         "orange": ("chip amber", "🟠 risk"),
         "green": ("chip", "🟢 safe"),
         # Escaleren is geen kleur maar een weigering te oordelen: neutrale outline, zodat het
         # visueel niet meedoet in de rood-oranje-groen-schaal waar het ook inhoudelijk buiten valt.
         "escaleren": ("chip outline", "⚖️ compliance decides")}

_TABS = [("check", "Claim check"), ("werklijst", "Site-audit worklist"),
         ("database", "Term database"), ("landen", "By country")]

_MARKTEN = ("NL", "DE", "BE")


def bron_badge(bevinding: dict) -> str:
    """Waar komt dit oordeel vandaan? Bron-letter als badge, de letterlijke onderbouwing als
    tooltip. Zonder deze badge is een A-oordeel (de wet zegt het) niet te onderscheiden van
    een C-oordeel (iemand leidde het af) — en dat verschil bepaalt hoe hard je moet ingrijpen."""
    letter = bevinding.get("bron") or ""
    if not letter:
        return ""
    detail = bevinding.get("bron_detail") or ""
    titel = f" title='{_e(detail)}'" if detail else ""
    return f"<span class='chip muted'{titel}>source {_e(letter)}</span>"


def onderbouwing_badge(bevinding: dict) -> str:
    """Is deze claim onderbouwd? Chip met de reden als tooltip.

    Alleen zichtbaar als het bewijs-oordeel er is (de wekelijkse site-scan zet het; een losse
    tekst-check zonder site-context niet) — nooit een chip die iets belooft wat niet getoetst is."""
    from nooch_village.claims_substantiatie import AMBIGU, ONDERBOUWD, ONTBREEKT
    stand = bevinding.get("onderbouwing")
    if stand not in (ONDERBOUWD, ONTBREEKT, AMBIGU):
        return ""
    klasse, tekst = (("chip", "🧾 substantiated") if stand == ONDERBOUWD else
                     ("chip amber", "🧾 evidence unclear") if stand == AMBIGU else
                     ("chip coral", "🧾 no evidence"))
    reden = bevinding.get("onderbouwing_reden") or ""
    titel = f" title='{_e(reden)}'" if reden else ""
    return f"<span class='{klasse}'{titel}>{tekst}</span>"


def rol_voor(categorie: str) -> str:
    """Welke rol pakt deze bevinding op? Eén definitie, gedeeld door de view, de
    taak-koppeling en de wekelijkse scan — de routing mag nooit uiteenlopen."""
    if categorie == "Labels":
        return "visual designer"
    if categorie in ("Vergelijkend", "Statistiek"):
        return "marketeer"
    if categorie == "Framing":
        return "copywriter + compliance"
    if categorie == "Sociaal":
        return "compliance"
    return "copywriter"


def _tabbalk(actief: str) -> str:
    knoppen = "".join(
        f"<a class='chip-opt{' on' if sleutel == actief else ''}' "
        f"href='/claims?tab={sleutel}'>{_e(label)}</a>"
        for sleutel, label in _TABS)
    return f"<div class='chip-wrap'>{knoppen}</div>"


# ── Het rapport (gedeeld door de directe POST en het JS-fragment) ────────────

def render_rapport(uitslag: dict, markten: list[str] | None = None,
                   bron: str = "", csrf_token: str = "", kan_bord: bool = False,
                   db: dict | None = None) -> str:
    """De bevindingen van één scan. Los renderbaar, zodat de live scan hetzelfde
    HTML terugkrijgt als een gewone paginavernieuwing — één opmaak, geen kopie in JS."""
    if uitslag.get("error"):
        return f"<div class='card'><b>The scan failed</b><p class='muted'>{_e(uitslag['error'])}</p></div>"

    bevindingen = uitslag.get("bevindingen", [])
    rood, oranje, groen = uitslag.get("rood", 0), uitslag.get("oranje", 0), uitslag.get("groen", 0)
    escaleren = uitslag.get("escaleren", 0)
    score = uitslag.get("score", 100)
    oordeel = ("not publishable — replace the forbidden terms" if rood else
               "publishable as long as the stated evidence is included" if oranje else
               "publishable (after the usual legal final check)")
    if escaleren:
        oordeel += f" · {escaleren} item(s) awaiting a verdict from compliance"

    kop = (f"<div class='kpi-card'><div class='kpi-body'>"
           f"<span class='kpi-val'>{score}<span class='kpi-unit'>/100</span></span> "
           f"<span class='{_CHIP['red'][0]}'>{rood} forbidden</span> "
           f"<span class='{_CHIP['orange'][0]}'>{oranje} risk</span> "
           f"<span class='{_CHIP['green'][0]}'>{groen} safe</span>"
           + (f" <span class='{_CHIP['escaleren'][0]}'>{escaleren} to be judged</span>"
              if escaleren else "")
           + f"</div><div class='muted'>compliance score — escalations do not count, the tool "
             f"has no verdict on those{_e(' · ' + bron if bron else '')}</div></div>")

    landen = _landnotities(uitslag, markten or [], db)

    if not bevindingen:
        lijst = ("<div class='card'><p>No flagged words found.</p>"
                 "<p class='muted'>Note: this only checks known terms. New or creative "
                 "wordings always go past compliance.</p></div>")
    else:
        volgorde = {"red": 0, "escaleren": 1, "orange": 2, "green": 3}
        rijen = ""
        for b in sorted(bevindingen, key=lambda x: volgorde.get(x["stoplicht"], 9)):
            cls, label = _CHIP.get(b["stoplicht"], _CHIP["green"])
            alt = (f"<div class='muted'><b>Alternative:</b> {_e(b['alternatief'])}</div>"
                   if b["stoplicht"] != "green" else "")
            advies = (f"<div class='muted'>Advice if you must choose anyway: "
                      f"{_e(b.get('stoplicht_advies', ''))}</div>"
                      if b.get("stoplicht_advies") else "")
            rijen += (f"<div class='c2-sec'>"
                      f"<span class='{cls}'>{label}</span> <b>{_e(b['term'])}</b>"
                      f"<span class='pill'>{_e(b['categorie'])}</span>"
                      f"<span class='pill'>role: {_e(_rol_label(b))}</span>"
                      f"{bron_badge(b)}{onderbouwing_badge(b)}"
                      f"<div>Found: <i>{_e(', '.join(b['gevonden']))}</i> — {_e(b['waarom'])}</div>"
                      f"{alt}{advies}</div>")
        lijst = f"<div class='card'><h3>Findings</h3>{rijen}</div>"

    incontext_html = _in_context(uitslag.get("in_context", []))
    ctx_noot = ""
    if (rood or oranje) and not uitslag.get("context_beoordeeld", False):
        ctx_noot = ("<p class='muted'>⚠ Context not judged automatically (no LLM available) — "
                    "every flagged term counts, including where it is only discussed.</p>")

    preview = _preview(uitslag.get("tekst", ""), bevindingen)
    acties = _rapport_acties(uitslag, csrf_token, kan_bord, bron)
    return (f"<div class='card'>{kop}<p class='muted'>Final verdict: {_e(oordeel)}</p>{ctx_noot}{acties}</div>"
            f"{landen}{lijst}{incontext_html}{preview}")


def _in_context(incontext: list[dict]) -> str:
    """De termen die de contextlaag als 'geen claim' beoordeelde: zichtbaar maar apart, en ze
    tellen niet mee in de score. Transparant, zodat compliance een verkeerd oordeel kan zien."""
    if not incontext:
        return ""
    rijen = ""
    for b in incontext:
        cls, label = _CHIP.get(b.get("stoplicht", ""), _CHIP["green"])
        rijen += (f"<div class='c2-sec'>"
                  f"<span class='{cls}'>{label}</span> <b>{_e(b.get('term', ''))}</b>"
                  f"<span class='pill'>{_e(b.get('categorie', ''))}</span>"
                  f"<div>Found: <i>{_e(', '.join(b.get('gevonden', [])))}</i></div>"
                  + (f"<div class='muted'><b>In context, no claim:</b> {_e(b.get('context_reden', ''))}</div>"
                     if b.get("context_reden") else "")
                  + "</div>")
    return (f"<div class='card'><h3>In context — no claim ({len(incontext)})</h3>"
            f"<p class='muted'>These terms do occur, but no claim is being made with them "
            f"(criticism, denial, quote or explanation). They do not count towards the score. Spot-check "
            f"them if you have doubts.</p>{rijen}</div>")


def _rol_label(bevinding: dict) -> str:
    """Het rol-label zoals het in het rapport staat — escaleren gaat altijd naar compliance."""
    if bevinding.get("stoplicht") == "escaleren":
        return "compliance"
    return rol_voor(bevinding.get("categorie", ""))


def _rapport_acties(uitslag: dict, csrf_token: str, kan_bord: bool, bron: str) -> str:
    """'Zet op het bord' is compliance-werk; de klembord-export mag iedereen (extern gebruik)."""
    if not (uitslag.get("rood") or uitslag.get("oranje") or uitslag.get("escaleren")):
        return ""
    knoppen = ("<button class='btn sm ghost' type='button' data-claims-kopieer='1'>"
               "Copy report</button>")
    if kan_bord and csrf_token:
        payload = urllib.parse.quote(_bord_payload(uitslag, bron))
        knoppen += (f"<form method='post' action='/action' class='qadd-row'>"
                    f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='next' value='/claims'>"
                    f"<input type='hidden' name='bron' value='{_e(bron)}'>"
                    f"<input type='hidden' name='bevindingen' value='{_e(payload)}'>"
                    f"<button class='btn sm ok' name='action' value='claims_to_board'>"
                    f"Put on the board</button></form>")
    return f"<div class='qadd-row'>{knoppen}</div>"


def _bord_payload(uitslag: dict, bron: str) -> str:
    """Compacte, URL-veilige samenvatting van de bevindingen voor de bord-actie.
    Alleen wat de taak nodig heeft — de rest staat in de database."""
    import json
    kern = [{"term": b["term"], "stoplicht": b["stoplicht"], "categorie": b["categorie"],
             "gevonden": b["gevonden"][:3], "alternatief": b["alternatief"],
             "bron": b.get("bron", ""), "bron_detail": b.get("bron_detail", "")[:200],
             "stoplicht_advies": b.get("stoplicht_advies", "")}
            for b in uitslag.get("bevindingen", [])
            if b["stoplicht"] in ("red", "orange", "escaleren")]
    return json.dumps({"bron": bron, "bevindingen": kern}, ensure_ascii=False)


def _landnotities(uitslag: dict, markten: list[str], db: dict | None) -> str:
    db = db if db is not None else {}
    landen = db.get("landen") or {}
    rood, oranje = uitslag.get("rood", 0), uitslag.get("oranje", 0)
    regels = []
    for code in markten:
        land = landen.get(code) or {}
        tekst = land.get("note_rood") if rood else land.get("note_oranje") if oranje else None
        if tekst:
            regels.append(f"<div class='c2-sec'><b>{_e(code)}</b> — {_e(tekst)}</div>")
    if not regels:
        return ""
    return f"<div class='card'><h3>Market-specific</h3>{''.join(regels)}</div>"


def _preview(tekst: str, bevindingen: list[dict]) -> str:
    """De gescande tekst met de vondsten gemarkeerd. Het prototype kleurde rood en oranje
    verschillend; het designsysteem kent één <mark>, dus het stoplicht gaat als emoji mee
    de markering in — zelfde informatie, geen nieuwe CSS-klasse."""
    if not tekst.strip() or not bevindingen:
        return ""
    merk = {}
    for b in bevindingen:
        if b["stoplicht"] == "green":
            continue
        teken = "🔴" if b["stoplicht"] == "red" else "🟠"
        for gevonden in b["gevonden"]:
            if gevonden:
                merk[gevonden] = teken
    stukken = _e(tekst[:8000])
    for gevonden, teken in sorted(merk.items(), key=lambda kv: -len(kv[0])):
        stukken = stukken.replace(_e(gevonden), f"<mark>{teken} {_e(gevonden)}</mark>")
    afgekapt = "<p class='muted'>(text truncated at 8000 characters)</p>" if len(tekst) > 8000 else ""
    return (f"<div class='card'><h3>Text with markings</h3>"
            f"<div class='editor'><p>{stukken}</p></div>{afgekapt}</div>")


# ── De tabbladen ────────────────────────────────────────────────────────────

def render_bordresultaat(rapport: dict) -> str:
    """Wat de klik op 'Zet op het bord' heeft opgeleverd, met links.

    Ook bij nul: dan tóón je waar de bevindingen al liggen. Een klik die niets zichtbaars doet
    voelt als een kapotte knop, ook als hij precies het juiste deed."""
    if not rapport:
        return ""
    aangemaakt = rapport.get("aangemaakt") or []
    lopend = rapport.get("lopend") or []
    if aangemaakt:
        per = ", ".join(f"@{_e(naam)} ({n})" for naam, n in _per_rol(aangemaakt))
        rijen = "".join(
            f"<div class='c2-sec'><a href='/project?pid={_e(t['pid'])}'>{_e(t['titel'])}</a>"
            f"<span class='pill'>@{_e(t['owner'].split('__')[-1])}</span></div>"
            for t in aangemaakt)
        totaal = rapport.get("totaal", len(aangemaakt))
        meer = (f"<p class='muted'>{totaal - len(aangemaakt)} more created, "
                f"visible on the board.</p>" if totaal > len(aangemaakt) else "")
        kop = f"<h3>{totaal} task(s) created → {per}</h3>{meer}"
    else:
        rijen = ""
        kop = (f"<h3>0 new</h3><p class='muted'>All "
               f"{rapport.get('overgeslagen', 0)} finding(s) already exist as a task or "
               f"worklist item.</p>")
    if lopend:
        bestaand = "".join(
            (f"<div class='c2-sec'><a href='/project?pid={_e(x['pid'])}'>{_e(x['titel'])}</a>"
             f"<span class='pill'>existing task</span></div>")
            if x.get("soort") == "taak" else
            (f"<div class='c2-sec'><a href='/claims?tab=werklijst'>#{_e(str(x.get('nr')))} "
             f"{_e(x['titel'])}</a><span class='pill'>worklist</span></div>")
            for x in lopend)
        rijen += f"<h3>Already running</h3>{bestaand}"
    return f"<div class='card'>{kop}{rijen}</div>"


def _per_rol(aangemaakt: list[dict]) -> list[tuple[str, int]]:
    from nooch_village.claims_board import per_rol
    return per_rol(aangemaakt)


def _tab_check(csrf_token: str, url: str, tekst: str, markten: list[str], rapport: str) -> str:
    vinkjes = "".join(
        f"<label class='chip-opt' for='f-markt-{m}'>"
        f"<input type='checkbox' id='f-markt-{m}' name='markt' value='{m}'"
        f"{' checked' if m in markten else ''}> {m}</label>"
        for m in _MARKTEN)
    return (f"<div class='card'>"
            f"<h3>Check a page or a piece of text</h3>"
            f"<form method='post' action='/claims/scan' class='qadd-form' id='claims-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"{_field('URL (optional)', 'url', kind='url', value=url, fid='f-claims-url', placeholder='https://nooch.earth/')}"
            f"{_field('Or paste the text', 'tekst', kind='textarea', value=tekst, fid='f-claims-tekst', placeholder='Copy, social post, product description…')}"
            f"<span class='att-lbl'>Market</span><div class='chip-wrap'>{vinkjes}</div>"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit' id='claims-knop'>Check claims</button>"
            f"<span class='muted' id='claims-status'></span></div>"
            f"</form>"
            f"<p class='muted'>A URL is fetched by the server, not by your browser — "
            f"internal addresses are refused.</p></div>"
            f"<div id='claims-rapport'>{rapport}</div>")


def _tab_werklijst(db: dict, csrf_token: str, kan_cureren: bool) -> str:
    statussen = claims_db.werk_statussen(db)
    rijen = ""
    for w in db.get("werklijst", []):
        cls, label = _CHIP.get(w.get("oordeel", ""), _CHIP["green"])
        if kan_cureren and csrf_token:
            opties = "".join(f"<option value='{_e(s)}'{' selected' if s == w.get('status') else ''}>"
                             f"{_e(s)}</option>" for s in statussen)
            cel = (f"<form method='post' action='/action' class='qadd-row'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                   f"<input type='hidden' name='next' value='/claims?tab=werklijst'>"
                   f"<input type='hidden' name='nr' value='{w['nr']}'>"
                   f"<label class='att-lbl' for='f-st-{w['nr']}'>Status #{w['nr']}</label>"
                   f"<select id='f-st-{w['nr']}' name='status'>{opties}</select>"
                   f"<button class='btn sm' name='action' value='claims_work_status'>Set</button>"
                   f"</form>")
        else:
            cel = f"<span class='chip muted'>{_e(w.get('status', 'open'))}</span>"
        rijen += (f"<tr><td class='num'>{w['nr']}</td>"
                  f"<td>{_e(w.get('claim', ''))}<div class='muted'>{_e(w.get('herformulering', ''))}</div></td>"
                  f"<td><span class='{cls}'>{label}</span></td><td>{cel}</td></tr>")
    return (f"<div class='card'><h3>Site audit nooch.earth</h3>"
            f"<p class='muted'>Status changes are compliance domain and are stored in the "
            f"claims database — they survive a restart.</p>"
            f"<table class='mtab'>{rijen}</table></div>")


def _intrek_knop(patroon: str, csrf_token: str) -> str:
    """De 'intrekken'-actie per term (alleen voor wie mag cureren). Hergebruikt qadd-row + btn;
    de curator ziet aan de conflict-melding of een seed-term bleef staan (aanwezigheid wint)."""
    return (f"<form method='post' action='/action' class='qadd-row'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='/claims?tab=database'>"
            f"<input type='hidden' name='patroon' value='{_e(patroon)}'>"
            f"<button class='btn' name='action' value='claims_term_retract' "
            f"title='Retract this term (an in-git seed term stays)'>Retract</button></form>")


def _tab_database(db: dict, zoek: str, csrf_token: str = "", kan_cureren: bool = False) -> str:
    naald = zoek.lower().strip()
    cureren = bool(kan_cureren and csrf_token)
    rijen = ""
    getoond = 0
    for t in db.get("termen", []):
        hooi = f"{t.get('term','')}{t.get('categorie','')}{t.get('waarom','')}{t.get('alternatief','')}".lower()
        if naald and naald not in hooi:
            continue
        getoond += 1
        cls, label = _CHIP.get(t.get("stoplicht", ""), _CHIP["green"])
        actie = f"<td>{_intrek_knop(t.get('patroon',''), csrf_token)}</td>" if cureren else ""
        rijen += (f"<tr><td><b>{_e(t.get('term',''))}</b>"
                  f"<div class='muted'>{_e(t.get('waarom',''))}</div></td>"
                  f"<td><span class='{cls}'>{label}</span></td>"
                  f"<td>{_e(t.get('categorie',''))}</td>"
                  f"<td class='muted'>{_e(t.get('alternatief',''))}</td>{actie}</tr>")
    leeg = "<p class='muted'>No term found.</p>" if not getoond else ""
    return (f"<div class='card'><h3>Term database</h3>"
            f"<form method='get' action='/claims'>"
            f"<input type='hidden' name='tab' value='database'>"
            f"<label class='att-lbl' for='f-claims-zoek'>Search</label>"
            f"<input class='kn-searchbox' type='search' id='f-claims-zoek' name='q' "
            f"value='{_e(zoek)}' placeholder='duurzaam, carbon, recycled…'>"
            f"</form>"
            f"<p class='muted'>{getoond} of {len(db.get('termen', []))} terms</p>"
            f"<table class='mtab'>{rijen}</table>{leeg}</div>")


def _tab_landen(db: dict) -> str:
    kaarten = ""
    for code, land in (db.get("landen") or {}).items():
        if code.startswith("_"):
            continue
        punten = "".join(f"<li>{_e(p)}</li>" for p in land.get("punten", []))
        kaarten += (f"<div class='card'><h3>{_e(land.get('name', code))}</h3>"
                    f"<ul>{punten}</ul></div>")
    kaarten += ("<div class='card'><h3>Checking competitors</h3>"
                "<p>Allowed, for internal market insight and to substantiate "
                "\"as far as we know\" claims. Never publish it as \"brand X commits "
                "greenwashing\": that is itself a comparative claim and in Germany an "
                "invitation for a counter-Abmahnung.</p></div>")
    return kaarten


def _blok_beheer(db: dict, csrf_token: str) -> str:
    """Term toevoegen — alleen zichtbaar voor wie hem ook mag opslaan."""
    categorieen = sorted({t.get("categorie", "") for t in db.get("termen", []) if t.get("categorie")})
    opties = "".join(f"<option>{_e(c)}</option>" for c in categorieen)
    stoplichten = "".join(f"<option value='{_e(s)}'>{_e(_CHIP[s][1])}</option>"
                          for s in claims_db.STOPLICHTEN)
    return (f"<div class='card'><h3>Add a term to the database</h3>"
            f"<p class='muted'>You are writing into the claims database: the source for this checker and "
            f"for the <code>claims_check</code> skill. The change bumps the version and lands in "
            f"the audit trail.</p>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='/claims?tab=werklijst'>"
            f"{_field('Term', 'term', fid='f-nt-term', required=True, placeholder='gifvrij / toxin-free')}"
            f"{_field('Search pattern (regex)', 'patroon', fid='f-nt-patroon', required=True, placeholder='gifvrij|toxin.?free')}"
            f"<label class='att-lbl' for='f-nt-stoplicht'>Traffic light</label>"
            f"<select id='f-nt-stoplicht' name='stoplicht'>{stoplichten}</select>"
            f"<label class='att-lbl' for='f-nt-categorie'>Category</label>"
            f"<select id='f-nt-categorie' name='categorie'>{opties}</select>"
            f"{_field('Why (regulation/source)', 'waarom', fid='f-nt-waarom')}"
            f"{_field('Safe alternative', 'alternatief', fid='f-nt-alternatief')}"
            f"<div class='qadd-row'><button class='btn ok' name='action' value='claims_term_add'>"
            f"Add</button></div></form></div>")


def _blok_bewijs(csrf_token: str, bewijzen: list[dict] | None) -> str:
    """Onderbouwing vastleggen — het schrijfpad naar de Kroniek.

    Hergebruikt exact het patroon van `_blok_beheer` (card + qadd-form + `_field` + qadd-row/btn) en
    de `mtab`-tabel van de werklijst; geen nieuwe klasse-familie, geen inline styles. Bestaat omdat de
    wekelijkse scan sinds deze versie bewijs eist: zonder schrijfpad blijft elke claim eeuwig oranje."""
    bewijzen = bewijzen or []
    rijen = "".join(
        f"<tr><td>{_e(str((r.get('meta') or {}).get('claim') or r.get('query', '')))}</td>"
        f"<td class='muted'>{_e(str(r.get('result_ref', ''))[:120])}</td>"
        f"<td><a href='{_e(str(r.get('source', '')))}'>source</a></td></tr>"
        for r in bewijzen)
    tabel = (f"<p class='muted'>Recorded so far ({len(bewijzen)} most recent):</p>"
             f"<table class='mtab'>{rijen}</table>" if rijen else
             "<p class='muted'>Nothing recorded yet — so every environmental claim on the site "
             "currently counts as unsubstantiated and comes out orange. That is the evidence gap, "
             "not a bug in the scan.</p>")
    return (f"<div class='card'><h3>Record evidence for a claim</h3>"
            f"<p class='muted'>You are writing a confirmed record into the Kroniek (the evidence "
            f"ledger). The weekly site scan reads it: a claim with a confirmed record is substantiated, "
            f"anything else comes out orange. Append-only — a correction is a new record, and the quote "
            f"must be literal so a later reader can check it.</p>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='/claims?tab=werklijst'>"
            f"{_field('Claim (as it appears on the site)', 'claim', fid='f-bw-claim', required=True, placeholder='plastic-free / plasticvrij')}"
            f"{_field('Source (URL or where the proof lives)', 'bron', fid='f-bw-bron', required=True, placeholder='https://… certificate, lab report, standard')}"
            f"{_field('Literal quote from that source', 'citaat', kind='textarea', fid='f-bw-citaat', required=True, placeholder='Paste the sentence that actually proves it — at least 20 characters.')}"
            f"<div class='qadd-row'><button class='btn ok' name='action' value='claims_bewijs_link'>"
            f"Record evidence</button></div></form>{tabel}</div>")


# ── De pagina ───────────────────────────────────────────────────────────────

def render_claims(csrf_token: str = "", msg: str = "", tab: str = "check",
                  kan_cureren: bool = False, zoek: str = "", url: str = "",
                  tekst: str = "", markten: list[str] | None = None,
                  rapport: str = "", bordresultaat: dict | None = None,
                  data_dir: str | None = None, bewijzen: list[dict] | None = None) -> str:
    """De hele checker als één governeerd scherm."""
    try:
        db = claims_db.load(data_dir=data_dir)
    except claims_db.ClaimsDbError as e:
        # Fail-closed: zonder database geen toets. Liever een zichtbare fout dan een stille 0.
        inner = (f"{_DS_LINK}{_nav()}<div class='c2-wrap'><div class='c2-main'>"
                 f"<h1>Claims checker</h1>"
                 f"<div class='card'><b>The claims database could not be loaded</b>"
                 f"<p class='muted'>{_e(str(e))} — the checker deliberately does nothing without a database.</p>"
                 f"</div></div></div>")
        return _page("Claims checker", inner)

    markten = markten if markten is not None else ["NL"]
    if tab == "check":
        body = render_bordresultaat(bordresultaat or {}) + _tab_check(
            csrf_token, url, tekst, markten, rapport)
    elif tab == "werklijst":
        body = _tab_werklijst(db, csrf_token, kan_cureren)
        if kan_cureren and csrf_token:
            body += _blok_beheer(db, csrf_token) + _blok_bewijs(csrf_token, bewijzen)
    elif tab == "database":
        body = _tab_database(db, zoek, csrf_token, kan_cureren)
    else:
        body = _tab_landen(db)

    # Conflictmelding (zichtbaar, bewust): een runtime-retractie die een in-git seed-term raakte is
    # genegeerd — aanwezigheid wint, zodat een juridische term nooit stil verdwijnt.
    conflict = ""
    for c in (db.get("_conflicten") or []):
        conflict += (f"<div class='card'><b>Retraction ignored</b>"
                     f"<p class='muted'>“{_e(c)}” is in the seed (via git) and therefore stays; "
                     f"a runtime retraction cannot override an in-git term. Retract it via a PR "
                     f"on the seed if you need to.</p></div>")

    versie = (db.get("meta") or {}).get("versie", "?")
    kader = " · ".join((db.get("meta") or {}).get("regelgeving", {}).values())
    main = (f"<div class='c2-main'><h1>Claims checker</h1>"
            f"<p class='muted'>EU EmpCo 2024/825 + ACM guidance · database v{_e(versie)} · "
            f"owner: compliance · not legal advice</p>"
            f"{_banner(msg)}{conflict}{_tabbalk(tab)}{body}"
            f"<p class='muted'>{_e(kader)}</p></div>")
    return _page("Claims checker", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>{_SCAN_JS}")


# Voortgang zonder full-page-wachtscherm: de scan gaat via fetch, de knop gaat op slot en de
# fasen lopen mee ("ophalen → scannen → rapport"). Zonder JS werkt hetzelfde formulier gewoon
# als POST — dan rendert de server de pagina mét rapport. Progressive enhancement.
_SCAN_JS = """<script>(function(){
 var f=document.getElementById('claims-form');if(!f)return;
 var knop=document.getElementById('claims-knop'),st=document.getElementById('claims-status'),
     doel=document.getElementById('claims-rapport'),bezig=false,timers=[];
 function fase(t){if(st)st.textContent=t;}
 function klaar(){bezig=false;if(knop)knop.disabled=false;timers.forEach(clearTimeout);timers=[];fase('');}
 f.addEventListener('submit',function(e){
   if(bezig){e.preventDefault();return;}
   if(!window.fetch)return;                      // geen fetch → gewone POST, server rendert alles
   e.preventDefault();bezig=true;if(knop)knop.disabled=true;
   var heeftUrl=(f.elements['url']&&f.elements['url'].value.trim())!=='';
   fase(heeftUrl?'Fetching page…':'Scanning…');
   if(heeftUrl){timers.push(setTimeout(function(){fase('Scanning…');},1200));}
   timers.push(setTimeout(function(){fase('Building report…');},2600));
   var body=new FormData(f);body.set('frag','1');
   fetch('/claims/scan',{method:'POST',body:new URLSearchParams(body),credentials:'same-origin'})
    .then(function(r){return r.text();})
    .then(function(h){doel.innerHTML=h;klaar();doel.scrollIntoView({block:'nearest'});})
    .catch(function(){doel.innerHTML="<div class='card'><b>The scan failed</b>"+
      "<p class='muted'>No connection to the server. Paste the text manually and try again.</p></div>";
      klaar();});
 });
 document.addEventListener('click',function(e){
   var k=e.target.closest&&e.target.closest('[data-claims-kopieer]');if(!k)return;
   var r=document.getElementById('claims-rapport');if(!r||!navigator.clipboard)return;
   navigator.clipboard.writeText(r.innerText).then(function(){
     k.textContent='Copied';setTimeout(function(){k.textContent='Copy report';},1600);});
 });
})();</script>"""
