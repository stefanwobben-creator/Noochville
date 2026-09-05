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
from nooch_village.cockpit2_util import (_DS_LINK, _nav, _md_doc, _name, inline_edit,
                                          inline_edit_knop, md_editor)
from nooch_village import projects as _projects


def _terug(pid: str, back: str) -> str:
    """Terug naar de kaart. `back` draagt de plek waar de bezoeker vandáán kwam, zodat de weg
    terug niet bij een generieke homepage eindigt — zelfde gedrag als de kaart zelf."""
    import urllib.parse
    q = f"?pid={urllib.parse.quote(pid)}"
    if back:
        q += "&back=" + urllib.parse.quote(back, safe="")
    return f"/project{q}"


def render_projectrapport(st, pid: str, csrf_token: str = "", username: str | None = None,
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

    # HET WACHTENDE CONCEPT, BOVEN HET DOCUMENT. Niet eroverheen: zolang niemand bevestigd heeft,
    # is dit een afleiding en niet de waarheid. De provenance staat erbij omdat een mens die een
    # tekst bevestigt, moet kunnen zien waaruit hij is samengesteld — anders bevestigt hij proza.
    concept = ""
    c = store.concept(pid) if store is not None else {}
    if (c.get("tekst") or "").strip():
        bronnen = [str(b) for b in (c.get("bronnen") or [])]
        tel = (f"assembled from {len(bronnen)} source{'s' if len(bronnen) != 1 else ''}: "
               + ", ".join(_e(b) for b in bronnen)) if bronnen else "assembled without sources"
        # De voorzet in het ENGELSE label, niet de opgeslagen sleutel: die sleutel is mechaniek.
        # Hij staat erbij omdat een mens die straks bevestigt moet zien wat er is voorgesteld —
        # en of het verslag die voorzet volgt of tegenspreekt.
        from nooch_village.project_verslag import label_voor
        _v = (c.get("voorzet") or "").strip()
        voorzet = (f"<span class='chip outline' title='Provisional guess from the checklist'>"
                   f"result: {_e(label_voor(_v))}</span>") if _v else ""
        knoppen = ""
        if rw:
            _hid = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                    f"<input type='hidden' name='next' value='/rapport?pid={_e(pid)}'>")
            # HETZELFDE COMPONENT als de comment-edit op de wall (cockpit2_util.inline_edit):
            # het bewerkveld neemt de plek van het GERENDERDE rapport in. En de balk staat
            # ERONDER, niet ernaast — het rapport ís het formulier.
            from nooch_village.views.projects import result_balk

            def _hidf():
                return _hid
            knoppen = result_balk(pid, c, _hidf,
                                  edit_knop=inline_edit_knop("Edit before confirming"))
        _weergave = f"<div class='einddoc-body'>{_md_doc(c.get('tekst') or '')}</div>"
        _blok = (inline_edit(_weergave,
                             md_editor("tekst", value=c.get("tekst") or "", rows=14, help=True),
                             sleutel=f"concept-{pid}", opslaan="verslag_bijwerken",
                             opslaan_label="Save draft", verborgen=_hid)
                 if rw else _weergave)
        concept = (f"<div class='einddoc-banner'>📄 Draft report — read it, tweak if needed, "
                   f"confirm below</div>"
                   f"<div class='card einddoc-concept editor-inline'>"
                   f"<div class='einddoc-ckop'><span class='chip amber'>not confirmed yet</span>"
                   f"{voorzet}</div>"
                   f"<p class='muted einddoc-prov'>{tel}</p>"
                   f"<p class='muted einddoc-vervangt'>The current report stays as it is until you "
                   f"confirm this draft.</p>"
                   f"{_blok}{knoppen}</div>")

    # OF-OF, NOOIT ALLEBEI. Het concept en het bestaande document stonden onder elkaar op één
    # pagina: twee versies van hetzelfde rapport, en de lezer moest raden welke telt. Er wás geen
    # keuze — `body` werd altijd gebouwd en `main` plakte ze achter elkaar.
    #
    # Wacht er een concept, dan is dát het onderwerp van deze pagina en de rest ruis. Het bestaande
    # document blijft gewoon bestaan op dataniveau; pas bevestigen vervangt het. Dit is puur de
    # weergave, en de kop hieronder zegt dat met zoveel woorden zodat niemand denkt dat het oude
    # verslag al weg is.
    if concept:
        body = ""
    elif not doc.strip():
        body = ("<div class='card'><p class='muted'>No end document yet — the assigned inhabitant "
                "writes it on every successful pulse.</p></div>")
    elif _projects.heeft_seed_vorm(doc):
        body = (f"<div class='card'><p class='muted'>No report written yet — this is still the "
                f"assignment as it was set. The assigned inhabitant writes towards the answer "
                f"below it on every successful pulse.</p>"
                f"<div class='einddoc-body'>{_md_doc(doc)}</div></div>")
    else:
        body = f"<div class='card'><div class='einddoc-body'>{_md_doc(doc)}</div></div>"

    # Ook de document-acties horen bij het document. Wacht er een concept, dan werk je aan het
    # CONCEPT (dat heeft zijn eigen Edit) en zou "Edit document" een tekst bewerken die niet eens
    # in beeld staat.
    acties = ""
    if rw and not concept:
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
                  # De tekst zegt nu wat er gebeurt: een CONCEPT, geen overschrijving. De oude
                  # tekst beloofde "this overwrites the current text" — dat doet hij niet meer, en
                  # een knop die iets anders zegt dan hij doet is de vals-succes-familie.
                  f"onclick=\"return confirm('Assemble a fresh draft report? "
                  f"It waits for your confirmation; the current text stays until then.')\">"
                  f"Re-assemble draft</button>"
                  f"</form></div>")

    main = f"<div class='c2-main'>{kop}{_banner(msg)}{concept}{body}{acties}</div>"
    return _page(f"Report · {titel}", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
