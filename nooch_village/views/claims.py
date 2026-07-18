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
_CHIP = {"red": ("chip coral", "🔴 verboden"),
         "orange": ("chip amber", "🟠 risico"),
         "green": ("chip", "🟢 veilig"),
         # Escaleren is geen kleur maar een weigering te oordelen: neutrale outline, zodat het
         # visueel niet meedoet in de rood-oranje-groen-schaal waar het ook inhoudelijk buiten valt.
         "escaleren": ("chip outline", "⚖️ compliance beslist")}

_TABS = [("check", "Claim check"), ("werklijst", "Werklijst site-audit"),
         ("database", "Termendatabase"), ("landen", "Per land")]

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
    return f"<span class='chip muted'{titel}>bron {_e(letter)}</span>"


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
        return f"<div class='card'><b>De scan lukte niet</b><p class='muted'>{_e(uitslag['error'])}</p></div>"

    bevindingen = uitslag.get("bevindingen", [])
    rood, oranje, groen = uitslag.get("rood", 0), uitslag.get("oranje", 0), uitslag.get("groen", 0)
    escaleren = uitslag.get("escaleren", 0)
    score = uitslag.get("score", 100)
    oordeel = ("niet publiceerbaar — vervang de verboden termen" if rood else
               "publiceerbaar zolang het genoemde bewijs erbij staat" if oranje else
               "publiceerbaar (na de gebruikelijke legal-eindcheck)")
    if escaleren:
        oordeel += f" · {escaleren} punt(en) wachten op een oordeel van compliance"

    kop = (f"<div class='kpi-card'><div class='kpi-body'>"
           f"<span class='kpi-val'>{score}<span class='kpi-unit'>/100</span></span> "
           f"<span class='{_CHIP['red'][0]}'>{rood} verboden</span> "
           f"<span class='{_CHIP['orange'][0]}'>{oranje} risico</span> "
           f"<span class='{_CHIP['green'][0]}'>{groen} veilig</span>"
           + (f" <span class='{_CHIP['escaleren'][0]}'>{escaleren} te beoordelen</span>"
              if escaleren else "")
           + f"</div><div class='muted'>compliance-score — escaleren telt niet mee, daar heeft "
             f"de tool geen oordeel over{_e(' · ' + bron if bron else '')}</div></div>")

    landen = _landnotities(uitslag, markten or [], db)

    if not bevindingen:
        lijst = ("<div class='card'><p>Geen vlagwoorden gevonden.</p>"
                 "<p class='muted'>Let op: dit toetst alleen bekende termen. Nieuwe of creatieve "
                 "formuleringen gaan altijd langs compliance.</p></div>")
    else:
        volgorde = {"red": 0, "escaleren": 1, "orange": 2, "green": 3}
        rijen = ""
        for b in sorted(bevindingen, key=lambda x: volgorde.get(x["stoplicht"], 9)):
            cls, label = _CHIP.get(b["stoplicht"], _CHIP["green"])
            alt = (f"<div class='muted'><b>Alternatief:</b> {_e(b['alternatief'])}</div>"
                   if b["stoplicht"] != "green" else "")
            advies = (f"<div class='muted'>Advies als je tóch moet kiezen: "
                      f"{_e(b.get('stoplicht_advies', ''))}</div>"
                      if b.get("stoplicht_advies") else "")
            rijen += (f"<div class='c2-sec'>"
                      f"<span class='{cls}'>{label}</span> <b>{_e(b['term'])}</b>"
                      f"<span class='pill'>{_e(b['categorie'])}</span>"
                      f"<span class='pill'>rol: {_e(_rol_label(b))}</span>"
                      f"{bron_badge(b)}"
                      f"<div>Gevonden: <i>{_e(', '.join(b['gevonden']))}</i> — {_e(b['waarom'])}</div>"
                      f"{alt}{advies}</div>")
        lijst = f"<div class='card'><h3>Bevindingen</h3>{rijen}</div>"

    preview = _preview(uitslag.get("tekst", ""), bevindingen)
    acties = _rapport_acties(uitslag, csrf_token, kan_bord, bron)
    return (f"<div class='card'>{kop}<p class='muted'>Eindoordeel: {_e(oordeel)}</p>{acties}</div>"
            f"{landen}{lijst}{preview}")


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
               "Kopieer rapport</button>")
    if kan_bord and csrf_token:
        payload = urllib.parse.quote(_bord_payload(uitslag, bron))
        knoppen += (f"<form method='post' action='/action' class='qadd-row'>"
                    f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='next' value='/claims'>"
                    f"<input type='hidden' name='bron' value='{_e(bron)}'>"
                    f"<input type='hidden' name='bevindingen' value='{_e(payload)}'>"
                    f"<button class='btn sm ok' name='action' value='claims_to_board'>"
                    f"Zet op het bord</button></form>")
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
    return f"<div class='card'><h3>Marktspecifiek</h3>{''.join(regels)}</div>"


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
    afgekapt = "<p class='muted'>(tekst afgekapt op 8000 tekens)</p>" if len(tekst) > 8000 else ""
    return (f"<div class='card'><h3>Tekst met markeringen</h3>"
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
        meer = (f"<p class='muted'>{totaal - len(aangemaakt)} verder aangemaakt, "
                f"zichtbaar op het bord.</p>" if totaal > len(aangemaakt) else "")
        kop = f"<h3>{totaal} taak/taken aangemaakt → {per}</h3>{meer}"
    else:
        rijen = ""
        kop = (f"<h3>0 nieuw</h3><p class='muted'>Alle "
               f"{rapport.get('overgeslagen', 0)} bevinding(en) staan al als taak of "
               f"werklijst-item.</p>")
    if lopend:
        bestaand = "".join(
            (f"<div class='c2-sec'><a href='/project?pid={_e(x['pid'])}'>{_e(x['titel'])}</a>"
             f"<span class='pill'>bestaande taak</span></div>")
            if x.get("soort") == "taak" else
            (f"<div class='c2-sec'><a href='/claims?tab=werklijst'>#{_e(str(x.get('nr')))} "
             f"{_e(x['titel'])}</a><span class='pill'>werklijst</span></div>")
            for x in lopend)
        rijen += f"<h3>Loopt al</h3>{bestaand}"
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
            f"<h3>Check een pagina of een stuk tekst</h3>"
            f"<form method='post' action='/claims/scan' class='qadd-form' id='claims-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"{_field('URL (optioneel)', 'url', kind='url', value=url, fid='f-claims-url', placeholder='https://nooch.earth/')}"
            f"{_field('Of plak de tekst', 'tekst', kind='textarea', value=tekst, fid='f-claims-tekst', placeholder='Copy, social post, productbeschrijving…')}"
            f"<span class='att-lbl'>Markt</span><div class='chip-wrap'>{vinkjes}</div>"
            f"<div class='qadd-row'>"
            f"<button class='btn ok' type='submit' id='claims-knop'>Check claims</button>"
            f"<span class='muted' id='claims-status'></span></div>"
            f"</form>"
            f"<p class='muted'>Een URL wordt door de server opgehaald, niet door je browser — "
            f"interne adressen worden geweigerd.</p></div>"
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
                   f"<button class='btn sm' name='action' value='claims_work_status'>Zet</button>"
                   f"</form>")
        else:
            cel = f"<span class='chip muted'>{_e(w.get('status', 'open'))}</span>"
        rijen += (f"<tr><td class='num'>{w['nr']}</td>"
                  f"<td>{_e(w.get('claim', ''))}<div class='muted'>{_e(w.get('herformulering', ''))}</div></td>"
                  f"<td><span class='{cls}'>{label}</span></td><td>{cel}</td></tr>")
    return (f"<div class='card'><h3>Site-audit nooch.earth</h3>"
            f"<p class='muted'>Statuswijzigingen zijn compliance-domein en worden in de "
            f"claims-database opgeslagen — ze overleven een herstart.</p>"
            f"<table class='mtab'>{rijen}</table></div>")


def _tab_database(db: dict, zoek: str) -> str:
    naald = zoek.lower().strip()
    rijen = ""
    getoond = 0
    for t in db.get("termen", []):
        hooi = f"{t.get('term','')}{t.get('categorie','')}{t.get('waarom','')}{t.get('alternatief','')}".lower()
        if naald and naald not in hooi:
            continue
        getoond += 1
        cls, label = _CHIP.get(t.get("stoplicht", ""), _CHIP["green"])
        rijen += (f"<tr><td><b>{_e(t.get('term',''))}</b>"
                  f"<div class='muted'>{_e(t.get('waarom',''))}</div></td>"
                  f"<td><span class='{cls}'>{label}</span></td>"
                  f"<td>{_e(t.get('categorie',''))}</td>"
                  f"<td class='muted'>{_e(t.get('alternatief',''))}</td></tr>")
    leeg = "<p class='muted'>Geen term gevonden.</p>" if not getoond else ""
    return (f"<div class='card'><h3>Termendatabase</h3>"
            f"<form method='get' action='/claims'>"
            f"<input type='hidden' name='tab' value='database'>"
            f"<label class='att-lbl' for='f-claims-zoek'>Zoeken</label>"
            f"<input class='kn-searchbox' type='search' id='f-claims-zoek' name='q' "
            f"value='{_e(zoek)}' placeholder='duurzaam, carbon, recycled…'>"
            f"</form>"
            f"<p class='muted'>{getoond} van {len(db.get('termen', []))} termen</p>"
            f"<table class='mtab'>{rijen}</table>{leeg}</div>")


def _tab_landen(db: dict) -> str:
    kaarten = ""
    for code, land in (db.get("landen") or {}).items():
        if code.startswith("_"):
            continue
        punten = "".join(f"<li>{_e(p)}</li>" for p in land.get("punten", []))
        kaarten += (f"<div class='card'><h3>{_e(land.get('name', code))}</h3>"
                    f"<ul>{punten}</ul></div>")
    kaarten += ("<div class='card'><h3>Concurrenten checken</h3>"
                "<p>Mag, voor intern marktinzicht en onderbouwing van "
                "\"voor zover wij weten\"-claims. Nooit publiek maken als \"merk X pleegt "
                "greenwashing\": dat is zelf een vergelijkende claim en in Duitsland een "
                "uitnodiging voor een tegen-Abmahnung.</p></div>")
    return kaarten


def _blok_beheer(db: dict, csrf_token: str) -> str:
    """Term toevoegen — alleen zichtbaar voor wie hem ook mag opslaan."""
    categorieen = sorted({t.get("categorie", "") for t in db.get("termen", []) if t.get("categorie")})
    opties = "".join(f"<option>{_e(c)}</option>" for c in categorieen)
    stoplichten = "".join(f"<option value='{_e(s)}'>{_e(_CHIP[s][1])}</option>"
                          for s in claims_db.STOPLICHTEN)
    return (f"<div class='card'><h3>Term toevoegen aan de database</h3>"
            f"<p class='muted'>Je schrijft in de claims-database: de bron voor deze checker én "
            f"voor de <code>claims_check</code>-skill. De wijziging bumpt de versie en komt in "
            f"de audit-trail.</p>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='next' value='/claims?tab=werklijst'>"
            f"{_field('Term', 'term', fid='f-nt-term', required=True, placeholder='gifvrij / toxin-free')}"
            f"{_field('Zoekpatroon (regex)', 'patroon', fid='f-nt-patroon', required=True, placeholder='gifvrij|toxin.?free')}"
            f"<label class='att-lbl' for='f-nt-stoplicht'>Stoplicht</label>"
            f"<select id='f-nt-stoplicht' name='stoplicht'>{stoplichten}</select>"
            f"<label class='att-lbl' for='f-nt-categorie'>Categorie</label>"
            f"<select id='f-nt-categorie' name='categorie'>{opties}</select>"
            f"{_field('Waarom (regelgeving/bron)', 'waarom', fid='f-nt-waarom')}"
            f"{_field('Veilig alternatief', 'alternatief', fid='f-nt-alternatief')}"
            f"<div class='qadd-row'><button class='btn ok' name='action' value='claims_term_add'>"
            f"Voeg toe</button></div></form></div>")


# ── De pagina ───────────────────────────────────────────────────────────────

def render_claims(csrf_token: str = "", msg: str = "", tab: str = "check",
                  kan_cureren: bool = False, zoek: str = "", url: str = "",
                  tekst: str = "", markten: list[str] | None = None,
                  rapport: str = "", bordresultaat: dict | None = None) -> str:
    """De hele checker als één governeerd scherm."""
    try:
        db = claims_db.load()
    except claims_db.ClaimsDbError as e:
        # Fail-closed: zonder database geen toets. Liever een zichtbare fout dan een stille 0.
        inner = (f"{_DS_LINK}{_nav()}<div class='c2-wrap'><div class='c2-main'>"
                 f"<h1>Claims-checker</h1>"
                 f"<div class='card'><b>De claims-database kon niet geladen worden</b>"
                 f"<p class='muted'>{_e(str(e))} — de checker doet bewust niets zonder database.</p>"
                 f"</div></div></div>")
        return _page("Claims-checker", inner)

    markten = markten if markten is not None else ["NL"]
    if tab == "check":
        body = render_bordresultaat(bordresultaat or {}) + _tab_check(
            csrf_token, url, tekst, markten, rapport)
    elif tab == "werklijst":
        body = _tab_werklijst(db, csrf_token, kan_cureren)
        if kan_cureren and csrf_token:
            body += _blok_beheer(db, csrf_token)
    elif tab == "database":
        body = _tab_database(db, zoek)
    else:
        body = _tab_landen(db)

    versie = (db.get("meta") or {}).get("versie", "?")
    kader = " · ".join((db.get("meta") or {}).get("regelgeving", {}).values())
    main = (f"<div class='c2-main'><h1>Claims-checker</h1>"
            f"<p class='muted'>EU EmpCo 2024/825 + ACM-leidraad · database v{_e(versie)} · "
            f"beheer: compliance · geen juridisch advies</p>"
            f"{_banner(msg)}{_tabbalk(tab)}{body}"
            f"<p class='muted'>{_e(kader)}</p></div>")
    return _page("Claims-checker", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>{_SCAN_JS}")


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
   fase(heeftUrl?'Pagina ophalen…':'Scannen…');
   if(heeftUrl){timers.push(setTimeout(function(){fase('Scannen…');},1200));}
   timers.push(setTimeout(function(){fase('Rapport opmaken…');},2600));
   var body=new FormData(f);body.set('frag','1');
   fetch('/claims/scan',{method:'POST',body:new URLSearchParams(body),credentials:'same-origin'})
    .then(function(r){return r.text();})
    .then(function(h){doel.innerHTML=h;klaar();doel.scrollIntoView({block:'nearest'});})
    .catch(function(){doel.innerHTML="<div class='card'><b>De scan lukte niet</b>"+
      "<p class='muted'>Geen verbinding met de server. Plak de tekst handmatig en probeer opnieuw.</p></div>";
      klaar();});
 });
 document.addEventListener('click',function(e){
   var k=e.target.closest&&e.target.closest('[data-claims-kopieer]');if(!k)return;
   var r=document.getElementById('claims-rapport');if(!r||!navigator.clipboard)return;
   navigator.clipboard.writeText(r.innerText).then(function(){
     k.textContent='Gekopieerd';setTimeout(function(){k.textContent='Kopieer rapport';},1600);});
 });
})();</script>"""
