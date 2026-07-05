"""Basis web-chrome + HTML-escaping — de gedeelde bouwstenen voor álle actieve views.

Geëxtraheerd uit de legacy `cockpit.py` (`_e`/`_banner`/`_page` + de basis-chrome `_FONTS`/`_CSS`)
zodat de views hier uit importeren i.p.v. uit de 4018-regel-legacy-module. Puur herordening,
geen gedragswijziging.

BEWUST geen afhankelijkheid op andere nooch_village-modules — alleen stdlib `html` — zodat hier
nooit een circulaire import kan ontstaan (dit is de bodem van de import-graaf).
"""
from __future__ import annotations
import html


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
 --font-display:'Bricolage Grotesque',system-ui,sans-serif;
 --font-body:'DM Sans',system-ui,sans-serif;
 --radius:9px;--radius-pill:999px;
 --shadow:0 1px 2px rgba(27,27,27,.06),0 2px 8px rgba(27,27,27,.04);
}
*{box-sizing:border-box}
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
"""


def _banner(msg) -> str:
    if not msg:
        return ""
    cls = "flash err" if str(msg).lstrip().startswith("✗") else "flash"
    return f'<div class="{cls}">{_e(msg)}</div>'


def _page(title: str, inner: str) -> str:
    return (f'<!doctype html><html lang="nl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)}</title>{_FONTS}<style>{_CSS}</style></head>'
            f'<body>{inner}</body></html>')
