"""Rapport-view — het volledige einddocument van een project (`/rapport?pid=…`).

De projectkaart droeg het hele rapport inline. Dat maakte de kaart onscanbaar: je opent een
project om te zien waar het staat en krijgt een document van vijf schermen. De kaart houdt nu de
essentie (`project_essentie`) en wijst hierheen.

WAAROM EEN EIGEN ROUTE EN GEEN UITKLAPPER. Het dorp heeft die vraag al beantwoord voor rol-notes:
`/pagina?id=NOTE-…` — de note ÍS de pagina, met een permalink. Een projectrapport is net zo goed
een document. Een `<details>` op de kaart zou zeggen dat het een uitklapbaar stukje kaart is, en
zou bovendien precies de klapper-in-een-sectie terugbrengen die met reden uit de herindeling ging.
Dit is ook de enige vorm waarin "de kaart wijst naar het document" letterlijk waar is.

Hergebruik, geen nieuw idioom: `_md_doc` + `.einddoc-body` dragen dezelfde leeslaag-typografie als
op de kaart (#441), de acties zijn letterlijk dezelfde dispatch-takken (`proj_doc_edit`,
`proj_regen_doc`) met dezelfde formulieren, en de pagina-schil komt uit `/pagina`.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import _DS_LINK, _nav, _md_doc, _name, md_editor
from nooch_village import projects as _projects


def _terug(pid: str, back: str) -> str:
    """Terug naar de kaart. `back` draagt de plek waar de bezoeker vandáán kwam, zodat de weg
    terug niet bij een generieke homepage eindigt — zelfde gedrag als de kaart zelf."""
    import urllib.parse
    q = f"?pid={urllib.parse.quote(pid)}"
    if back:
        q += "&back=" + urllib.parse.quote(back, safe="")
    return f"/project{q}"


def render_rapport(st, pid: str, csrf_token: str = "", username: str | None = None,
                   msg: str = "", back: str = "/") -> str:
    """Het volledige einddocument van één project."""
    p = st.projects.get(pid)
    if p is None:
        main = ("<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
                "<h1>Report not found</h1><p class='muted'>This project no longer exists.</p></div>")
        return _page("Report not found", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")

    store = getattr(st, "project_docs", None)
    doc = store.read(pid) if store is not None else ""
    titel = (p.get("scope") or p.get("label") or pid)
    orec = st.records.get(p.get("owner", "")) if p.get("owner") else None
    rol_chip = (f" <a class='chip' href='/node?id={_e(p.get('owner',''))}'>{_e(_name(orec))}</a>"
                if orec is not None else "")
    rw = bool(csrf_token)

    # De model-herkomst hoort bij het document, dus hij reist mee naar waar het document woont.
    # Dezelfde functie als op de kaart — één definitie van "welk model schreef dit".
    from nooch_village.views.projects import _herkomst_chip
    kop = (f"<div class='c2-bar'><a href='{_e(_terug(pid, back))}'>← project</a></div>"
           f"<h1>📄 {_e(titel)}{rol_chip} {_herkomst_chip(st, pid)}</h1>")

    # DRIE TOESTANDEN, DRIE ZINNEN. Een document dat nog alleen de opdracht is, is iets anders dan
    # geen document — en beide zijn iets anders dan een geschreven rapport. Ze op één hoop gooien
    # is precies wat de kaart hiervóór deed.
    if not doc.strip():
        body = ("<div class='card'><p class='muted'>No end document yet — the assigned inhabitant "
                "writes it on every successful pulse.</p></div>")
    elif _projects.is_seed_document(p, doc):
        body = (f"<div class='card'><p class='muted'>No report written yet — this is still the "
                f"assignment as it was set. The assigned inhabitant writes towards the answer "
                f"below it on every successful pulse.</p>"
                f"<div class='einddoc-body einddoc-vol'>{_md_doc(doc)}</div></div>")
    else:
        body = f"<div class='card'><div class='einddoc-body einddoc-vol'>{_md_doc(doc)}</div></div>"

    acties = ""
    if rw:
        # DEZELFDE TAKKEN als op de kaart stonden, met `next` terug naar deze route zodat je na
        # opslaan of verversen bij het document blijft in plaats van op de kaart te belanden.
        nxt = f"/rapport?pid={_e(pid)}"
        hid = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
               f"<input type='hidden' name='pid' value='{_e(pid)}'>"
               f"<input type='hidden' name='next' value='{nxt}'>")
        acties = (f"<div class='card'>"
                  f"<details class='cardmenu'><summary class='flink'>Edit document</summary>"
                  f"<form method='post' action='/action' class='pf'>{hid}"
                  # Een uitleg, geen veldlabel: deze zin hoort bij het formulier maar labelt
                  # geen invoerveld. Als label zonder for= zou hij een koppeling beloven die er
                  # niet is — de ratchet ving dat.
                  f"<p class='muted att-hint'>The AI updates this document; give lasting "
                  f"instructions via a #task comment on the project wall.</p>"
                  f"{md_editor('doc', value=doc, rows=16, help=True)}"
                  f"<button class='btn ok sm' type='submit' name='action' value='proj_doc_edit'>"
                  f"Save document</button></form></details>"
                  f"<form method='post' action='/action' class='pf einddoc-regen'>{hid}"
                  f"<button class='flink' type='submit' name='action' value='proj_regen_doc' "
                  f"onclick=\"return confirm('Regenerate the report from the latest deliverables? "
                  f"This overwrites the current text.')\">Refresh from deliverables</button>"
                  f"</form></div>")

    main = f"<div class='c2-main'>{kop}{_banner(msg)}{body}{acties}</div>"
    return _page(f"Report · {titel}", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
