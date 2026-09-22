"""Basis web-chrome + HTML-escaping — de gedeelde bouwstenen voor álle actieve views.

Geëxtraheerd uit de legacy `cockpit.py` (`_e`/`_banner`/`_page` + de basis-chrome `_FONTS`/`_CSS`)
zodat de views hier uit importeren i.p.v. uit de 4018-regel-legacy-module. Puur herordening,
geen gedragswijziging.

BEWUST geen afhankelijkheid op andere nooch_village-modules — alleen stdlib `html` — zodat hier
nooit een circulaire import kan ontstaan (dit is de bodem van de import-graaf).
"""
from __future__ import annotations
import hashlib as _hashlib
import html
import os as _os


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


# ── Nooch design system (tokens uit nooch-shop/assets/design-tokens.css) ──────

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Bricolage+Grotesque:wght@600;800&family=DM+Sans:wght@400;500;700&display=swap">'
)

_CSS = """
:root{
 --ink:#1B1B1B;--gray:#4A4A4A;--subtle:#7A7A7A;--muted:#9A9483;
 --green:#1F9D55;--green-dark:#14713C;--green-tint:#D3EFDD;
 --cream:#FCFAF4;--cream-2:#FBF6EA;--cream-3:#FFF7E8;--sand:#F1ECDF;--surface:#fff;
 --yellow:#FFCE2E;--yellow-light:#FFF1B8;--coral:#FF6B5B;--border:#DDD4C0;--error-tint:#FDEAEA;
 /* De vier kolomtinten van het projectbord. HIER, bij de andere tokens, en niet in een
    tweede :root in nooch.css: de `.nu`-laag verwijst er ook naar, en een token dat op twee
    plekken gedefinieerd staat is precies het geval waar `reference, don't copy` over gaat.
    'wacht' is rood sinds 22 sept 2026 (founder-besluit, was amber). */
 --col-actief:#eef3fb;--colb-actief:#d3e0f4;
 --col-wacht:#FDEAEA;--colb-wacht:#FF6B5B;
 --col-done:#D3EFDD;--colb-done:#cfe8d6;
 --col-toekomst:#f2f1ee;--colb-toekomst:#e5e2db;
 /* De badge per uitkomst-soort op het verwerken-scherm. Zelfde aanpak als de kolomtinten
    hierboven: waarde één keer, beide CSS-lagen verwijzen ernaar. Een PROJECT deelt zijn
    tint met de Active-kolom van het bord — hetzelfde soort ding, dus dezelfde waarde en
    geen tweede hex die er toevallig op lijkt. */
 --uk-actie:#D3EFDD;--ukt-actie:#14713C;
 --uk-project:var(--col-actief);--ukt-project:#2A4FA0;
 --uk-gov:#F3E8FB;--ukt-gov:#7A2AA0;
 --neon:#2bff6f;   /* call bar: speaking-glow (enige bar-specifieke token) */
 --goal:#6a4fa0;--goal-tint:#ece5f6;   /* doelen: het paars uit docs/MITH_doelen_incockpit.html */
 --font-display:'Bricolage Grotesque',system-ui,sans-serif;
 --font-body:'DM Sans',system-ui,sans-serif;
 --radius:9px;--radius-pill:999px;
 --shadow:0 1px 2px rgba(27,27,27,.06),0 2px 8px rgba(27,27,27,.04);
}
*{box-sizing:border-box}
/* Toetsenbord-zichtbaarheid: één focusregel voor de hele app. :focus-visible i.p.v. :focus,
   zodat muisklikken geen ring tekenen maar Tab-navigatie altijd zichtbaar is (WCAG 2.4.7). */
:focus-visible{outline:2px solid var(--green-dark);outline-offset:2px}
/* Het `hidden`-attribuut moet ALTIJD winnen van een author `display:`-regel (bijv. .kc-radio{display:block}),
   anders werkt geen enkele hidden-gebaseerde show/hide (categorie-filter, .kc-mode, .kc-cond, .tile-back-flip). */
[hidden]{display:none!important}
body{font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--ink);
 background:var(--cream);margin:0;padding:1.6rem 2rem;max-width:1180px}
h1{font-family:var(--font-display);font-weight:800;font-size:1.5rem;margin:0}
h2{font-family:var(--font-display);font-weight:800;font-size:.95rem;text-transform:uppercase;
 letter-spacing:.03em;margin:1.8rem 0 .5rem;color:var(--green-dark)}
a{color:var(--green-dark)}
.bar{color:var(--gray);margin:.4rem 0 1.2rem;font-size:13px}
.badge{font-size:.66rem;text-transform:uppercase;letter-spacing:.05em;font-weight:700;
 padding:.18rem .55rem;border-radius:var(--radius-pill);vertical-align:middle;margin-left:.4rem}
.badge.ro{background:var(--sand);color:var(--gray)}
.badge.rw{background:var(--green-tint);color:var(--green-dark)}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--surface);
 border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
th,td{border-bottom:1px solid var(--border);padding:.5rem .6rem;text-align:left;vertical-align:top}
th{background:var(--cream-2);font-family:var(--font-display);font-weight:700;
 text-transform:uppercase;font-size:11px;letter-spacing:.03em;color:var(--gray)}
tr:last-child td{border-bottom:none}
tr.archived td{opacity:.45}
tr.st-pending td{background:var(--yellow-light)}
tr.st-blocked td{background:var(--error-tint)}
tr.st-running td{background:var(--green-tint)}
tr.st-future td{opacity:.55}
.chip{display:inline-block;background:var(--green-tint);color:var(--green-dark);
 border-radius:var(--radius-pill);padding:.1rem .55rem;margin:.06rem;font-size:12px}
.muted{color:var(--muted)}
.btn{font-family:var(--font-body);font-weight:600;font-size:12px;border:1px solid rgba(27,27,27,.14);
 border-radius:var(--radius-pill);background:transparent;color:var(--ink);
 padding:.3rem .85rem;margin:.12rem;cursor:pointer;display:inline-block;text-decoration:none}
.btn:hover{background:rgba(27,27,27,.05)}
.btn.ok{background:var(--green);border-color:var(--green);color:#fff}
.btn.ok:hover{background:var(--green-dark);border-color:var(--green-dark)}
.btn.no{background:#fff;border-color:var(--coral);color:var(--coral)}
.tension{background:var(--cream-3);border:1px solid var(--border);border-radius:var(--radius);
 padding:.7rem .9rem;margin:.6rem 0 1.4rem}
details{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
 margin:.5rem 0;padding:.3rem .9rem;box-shadow:var(--shadow)}
details[open]{padding-bottom:.8rem}
details>summary{cursor:pointer;font-family:var(--font-display);font-weight:700;padding:.45rem 0}
.pf label{display:block;margin:.6rem 0 .2rem;font-size:13px;color:var(--gray)}
.pf input,.pf select{width:100%;padding:.45rem;border:1px solid var(--border);
 border-radius:var(--radius);font:inherit;background:#fff}
.flash{background:var(--green-tint);border:1px solid var(--green);color:var(--green-dark);
 border-radius:var(--radius);padding:.5rem .8rem;margin:.4rem 0 1rem;font-weight:600}
.flash.err{background:var(--error-tint);border-color:var(--coral);color:#A8322A}
/* Fullscreen-overlay (bv. de Snake-easter-egg): draait als iframe OP de huidige pagina i.p.v. een
   navigatie. Dat patroon ontstond om de call bar niet weg te gooien; die is 11 aug 2026 uit de
   shell gehaald en de bijbehorende verberg-regel hier met 'm mee. De overlay-aanpak zelf blijft —
   een navigatie voor een easter-egg is nog steeds zonde. */
"""


def _field(label: str, name: str, *, kind: str = "text", value: str = "",
           fid: str = "", required: bool = False, placeholder: str = "",
           attrs: str = "", label_cls: str = "att-lbl") -> str:
    """Label + veld als onlosmakelijk paar: de <label for> wijst ALTIJD naar de veld-id.

    Dit is de structurele fix voor het patroon "label zonder for / input zonder id"
    (label-klik doet niets, screenreader ziet een los veld). Gebruik deze helper voor
    elk nieuw formulierveld; losse <label>/<input>-paren worden door de ratchet
    (tests/test_ui_ratchets.py) op hun huidige aantal bevroren.

    kind: een input-type ("text", "email", "number", "date", …) of "textarea".
    fid:  expliciete id; default "f-<name>". Meerdere velden met dezelfde name op één
          pagina? Geef dan zelf een unieke fid mee.
    attrs: extra rauwe attributen (bv. "min='0' step='1'" of "form='filepost'").
    """
    fid = fid or f"f-{name}"
    req = " required" if required else ""
    ph = f' placeholder="{_e(placeholder)}"' if placeholder else ""
    extra = f" {attrs}" if attrs else ""
    lab = f'<label class="{_e(label_cls)}" for="{_e(fid)}">{_e(label)}</label>'
    if kind == "textarea":
        veld = (f'<textarea id="{_e(fid)}" name="{_e(name)}"{ph}{req}{extra}>'
                f'{_e(value)}</textarea>')
    else:
        veld = (f'<input type="{_e(kind)}" id="{_e(fid)}" name="{_e(name)}" '
                f'value="{_e(value)}"{ph}{req}{extra}>')
    return lab + veld


def _banner(msg) -> str:
    if not msg:
        return ""
    cls = "flash err" if str(msg).lstrip().startswith("✗") else "flash"
    return f'<div class="{cls}">{_e(msg)}</div>'


# Verborgen easter-egg-trigger op elke ingelogde cockpit-pagina (login gebruikt _page NIET): de
# ── De gedeelde fragment-mechaniek (static/nooch.js) ─────────────────────────
# Eén script voor de klasse "een stuk pagina vervangt zichzelf": wachtrij voor typ-en-Enter-velden,
# opnieuw bedraden van verse formulieren (idempotent), cursor-herstel en tellers. Elke volle pagina
# krijgt hem; modal-fragmenten erven hem van de pagina waarin ze geopend worden. Zelfde recept als
# _DS_LINK: echt bestand + inhoud-hash in de URL, dus lang cachebaar en toch nooit stale.
_JS_PATH = _os.path.join(_os.path.dirname(__file__), "static", "nooch.js")
with open(_JS_PATH, encoding="utf-8") as _js_f:
    _JS_SRC = _js_f.read()
_JS_VERSION = _hashlib.md5(_JS_SRC.encode("utf-8")).hexdigest()[:10]
_JS_LINK = f'<script src="/static/nooch.js?v={_JS_VERSION}" defer></script>'


#: Projectstatus → (Nooch UI-variant, woord). De VORM zit in de CSS (`.nu-status--*`), het WOORD
#: staat er altijd bij. Nooit kleur alleen: een gekleurd vlakje zegt niets tegen wie kleur niet
#: goed ziet, en niets in zwart-wit.
_STATUS_VORM = {
    "running": ("ok", "Active"),
    "blocked": ("wait", "Waiting"),
    "done":    ("ok", "Done"),
    "future":  ("open", "Future"),
    "proposed": ("open", "Proposed"),
    "draft":   ("open", "Draft"),
}


def _status(status: str, label: str = "") -> str:
    """Eén statuslabel als VORM plus WOORD (Nooch UI v1, fase 9).

    Buiten een `.nu`-scherm rendert dit als een gewone inline-span: de klassen doen dan niets, de
    tekst blijft leesbaar. Zo kan hij gebruikt worden op een scherm dat nog niet meedoet zonder er
    half-nieuw uit te zien."""
    soort, woord = _STATUS_VORM.get(str(status or "").lower(), ("open", status or "—"))
    return f"<span class='nu-status nu-status--{soort}'>{_e(label or woord)}</span>"


def _page(title: str, inner: str, body_cls: str = "") -> str:
    """De hele pagina. `body_cls` is voor wat alleen op body-niveau te regelen is.

    ER IS ER PRECIES ÉÉN NODIG, en daarom is dit een parameter en geen nieuw mechanisme:
    `body{max-width:1180px}` hierboven geldt voor de hele app, en de Projects-stap van het
    werkoverleg is het enige scherm dat er echt buiten moet (vier kolommen naast elkaar, zie
    `views/werkoverleg.py`). Een breedte die op body staat, kun je niet van binnenuit
    overschrijven — elke poging met `100vw` of negatieve marges rekent de scrollbar mis.

    `cockpit2._nu_body` VOEGT ZIJN KLASSE TOE aan wat hier staat en vervangt hem niet; dat is
    de reden dat die functie sinds deze parameter met een regex werkt."""
    # <main> als landmark om de pagina-inhoud: screenreaders en toetsenbord-gebruikers kunnen
    # direct naar de inhoud springen. De chrome (Noochie-rail, call bar) wordt door _send ná
    # </main> geïnjecteerd en blijft zo buiten de hoofdinhoud.
    cls = f' class="{_e(body_cls)}"' if body_cls else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)}</title>{_FONTS}<style>{_CSS}</style></head>'
            f'<body{cls}><main>{inner}</main>{_JS_LINK}</body></html>')
