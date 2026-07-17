"""Accountability-check — dorpsbrede hygiëne op de verantwoordelijkheden per rol.

Draait op een knop (één LLM-call over alle accountabilities, niet bij elke pagina-load) en bewaart de
uitkomst in accountability_check.json. Toont dubbelingen (twee rollen die hetzelfde claimen) en zwak
geformuleerde accountabilities met een herformulering. Hangt samen met het pull-systeem: rollen matchen
kansen op hun eigen accountabilities, dus die moeten scherp en niet-overlappend zijn.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _name, _nav


def roles_with_accountabilities(st) -> list[dict]:
    out = []
    for rec in st.records.all():
        d = getattr(rec, "definition", None)
        accs = (getattr(d, "accountabilities", None) or []) if d is not None else []
        if accs and not getattr(rec, "archived", False):
            out.append({"role": _name(rec), "id": rec.id, "accountabilities": list(accs)})
    return out


def _dup_block(dups: list) -> str:
    if not dups:
        return "<p class='muted'>Geen dubbelingen gevonden.</p>"
    rows = []
    for d in dups:
        roles = "".join(f"<span class='chip amber'>{_e(str(r))}</span>" for r in (d.get("roles") or []))
        rows.append(f"<div class='card'><div class='rdr-sig'>{_e(str(d.get('accountability', '')))}</div>"
                    f"<div class='rdr-meta'>{roles}</div>"
                    f"<div class='muted'>{_e(str(d.get('advies', '')))}</div></div>")
    return "".join(rows)


def _weak_block(weak: list) -> str:
    if not weak:
        return "<p class='muted'>Geen zwak geformuleerde accountabilities gevonden.</p>"
    rows = []
    for w in weak:
        rows.append(f"<div class='card'><div class='rdr-meta'><span class='chip'>{_e(str(w.get('role', '')))}</span></div>"
                    f"<div class='muted'>nu: {_e(str(w.get('accountability', '')))}</div>"
                    f"<div class='rdr-sig'>→ {_e(str(w.get('herformulering', '')))}</div>"
                    f"<div class='muted'>{_e(str(w.get('waarom', '')))}</div></div>")
    return "".join(rows)


def _roles_overview(roles: list[dict]) -> str:
    rows = []
    for r in roles:
        accs = "".join(f"<li>{_e(str(a))}</li>" for a in r["accountabilities"])
        rows.append(f"<div class='card'><div class='rdr-sig'>{_e(r['role'])}</div><ul>{accs}</ul></div>")
    return "".join(rows)


def render_accountabilities(st, data_dir: str, csrf_token: str = "") -> str:
    roles = roles_with_accountabilities(st)
    res = {}
    path = os.path.join(data_dir, "accountability_check.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                res = json.load(f)
        except Exception:
            res = {}
    knop = ""
    if csrf_token:
        knop = (f"<form method='post' action='/action' class='emo-f'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='next' value='/accountabilities'>"
                f"<button class='btn ok sm' name='action' value='acc_check'>Check uitvoeren</button></form>")
    result_block = ""
    if res:
        result_block = (f"<h2>Dubbelingen ({len(res.get('duplicates') or [])})</h2>{_dup_block(res.get('duplicates') or [])}"
                        f"<h2>Formulering ({len(res.get('weak') or [])})</h2>{_weak_block(res.get('weak') or [])}")
    main = (f"<div class='c2-main'><div class='cl-head'><h1>Accountability-check</h1>"
            f"<span class='kc-actions'>{knop}</span></div>"
            f"<p class='muted'>Controleert alle {len(roles)} rollen met accountabilities op dubbele "
            f"verantwoordelijkheden en zwakke formulering. Draai de check om een verse analyse te maken.</p>"
            f"{result_block}"
            f"<h2>Alle accountabilities per rol</h2>{_roles_overview(roles)}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Accountability-check", inner)
