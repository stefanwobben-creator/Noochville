"""Mijn acties — het scherm bij `acties.py`. Typen, Enter, klaar.

DE HELE UX IS DE SNELHEID. Alles wat hier staat dient één ding: dat opschrijven net zo weinig kost
als in een papieren schrift. Elke keuze hieronder volgt daaruit:

  * het invoerveld staat BOVENAAN en is het enige verplichte veld. Eén `<input>` in een formulier
    verstuurt bij Enter uit zichzelf — geen JavaScript, geen knop die je moet zoeken;
  * koppelen aan een project zit achter een `<details>`. Dichtgeklapt is het één grijs linkje van
    vier woorden; opengeklapt een select. Zo staat de mogelijkheid er wel, maar niet in de weg;
  * afgevinkte acties zakken naar een ingeklapt blokje onderaan, met één knop om ze te wissen.

GEEN NIEUWE CSS, GEEN INLINE STYLES (harde regel uit CLAUDE.md). Alles hergebruikt bestaande
klassen, en de afbeelding die ze samen maken is precies het prototype:

    laag       klasse            waar hij al vandaan komt
    ─────────────────────────────────────────────────────────────────────────────
    atoom      .ck-box           het afvinkbolletje van de projectchecklist
    atoom      .ck-txt/.ck-done  de tekst, doorgestreept als hij af is
    atoom      .flink/.dellink   een tekstlinkje in een formulier
    atoom      .cl-filter.pill   het project-labeltje
    molecuul   .ck-item          één regel: bolletje + tekst + meta
    molecuul   .qadd-form        het snelinvoer-blok
    patroon    .card             de lijst als geheel

WAT HIER NIET STAAT: geen filters, geen sortering, geen deadline-kolom, geen groepering per
project. Elk daarvan is een scherm-element dat je moet lezen vóór je kunt schrijven.
"""
from __future__ import annotations

import urllib.parse

from nooch_village import acties as _A
from nooch_village.cockpit2_util import _DS_LINK, _nav, _name
from nooch_village.web_base import _e, _page


def _projectnaam(st, pid: str) -> str:
    """De leesbare naam van een gekoppeld project, of het id als het weg is.

    EEN VERDWENEN PROJECT LAAT DE ACTIE STAAN. Hij is van jou; dat het project is opgeruimd zegt
    niets over de regel die je opschreef. Wel zie je het id in plaats van een naam, en dat is
    precies het signaal dat er iets niet meer klopt."""
    p = st.projects.get(pid) if pid else None
    if p is None:
        return pid or ""
    sc = p.get("scope")
    return (sc if isinstance(sc, str) and sc.strip() else "") or pid


def _eigenaarnaam(st, owner: str) -> str:
    """De leesbare naam van een project-eigenaar, voor de kop boven een groep.

    DRIE VORMEN, want dat zijn de drie die een eigenaar kan hebben: een rol, een cirkel, of een
    Individueel Initiatief (`ii:<cirkel>`). Die laatste heeft geen eigen record — hij hoort bij
    de cirkel uit zijn prefix, en zo heet hij ook op het bord.

    Valt terug op het kale id: een groep zonder kop is erger dan een lelijke kop, want dan weet je
    niet waar de projecten eronder vandaan komen."""
    from nooch_village.cockpit2 import _II_PREFIX
    if owner.startswith(_II_PREFIX):
        cirkel = st.records.get(owner[len(_II_PREFIX):])
        naam = _name(cirkel) if cirkel is not None else ""
        return f"{naam or owner} — eigen initiatief" if naam else owner
    rec = st.records.get(owner)
    return (_name(rec) if rec is not None else "") or owner or "—"


#: De projectstatussen die "hier wordt aan gewerkt" betekenen. Een actie hang je aan iets dat
#: loopt; aan een toekomstig of afgerond project hoort geen volgende stap.
_LOPEND = ("running", "blocked")


def _projectopties(st, ik: str, huidig: str) -> str:
    """De projecten waaruit deze mens kiest: wat LOOPT, onder zijn EIGEN rollen.

    HIER STOND "alles wat je mag lezen" (27 september 2026, teruggedraaid). Dat was technisch de
    goede grens — hij spiegelde de zichtbaarheidsregel — maar als keuzelijst onbruikbaar: op prod
    staan honderden projecten, en de kans dat het jouwe erbij staat verdwijnt in het scrollen. Een
    keuzelijst hoort te helpen kiezen, niet te bewijzen dat je mag.

    DRIE FILTERS, van breed naar smal:

      1. leesbaar        — de zichtbaarheidsregel blijft de buitengrens (zie hieronder);
      2. lopend          — `running` of `blocked`; niet future, niet afgerond, niet gearchiveerd;
      3. onder jouw rol  — eigenaar is een rol die JÍJ vervult, de cirkel eromheen, of je eigen
                           Individueel Initiatief.

    DE BUITENGRENS BLIJFT DE ZICHTBAARHEID, en dat is geen dubbeling maar een vangnet: filter 3
    werkt op eigenaarschap, en een priévé project van een rol die je vervult zou je anders nooit
    kunnen kiezen — terwijl je hem wél mag zien. Kon je koppelen aan iets wat je niet mag lezen,
    dan zou je je eigen actie uit je eigen lijst laten verdwijnen.

    HET HUIDIGE PROJECT STAAT ER ALTIJD BIJ, ook als het inmiddels buiten de filters valt. Anders
    wist een select die je opent om te ontkoppelen stilzwijgend de koppeling die er stond."""
    from nooch_village.views.messages import mag_project_lezen
    from nooch_village.cockpit2 import _II_PREFIX, resolve_circle_id

    mijn_rollen = set(st.assign.roles_of("person", ik)) if ik else set()
    mijn_cirkels = {c for c in (resolve_circle_id(r, st.records) for r in mijn_rollen) if c}
    van_mij = mijn_rollen | mijn_cirkels | {f"{_II_PREFIX}{c}" for c in mijn_cirkels}

    per_eigenaar: dict[str, list[tuple[str, str]]] = {}
    for p in st.projects.all():
        pid = p.get("id") or ""
        if not pid or p.get("archived"):
            continue
        eigen_keuze = pid == huidig
        if not eigen_keuze:
            if p.get("status") not in _LOPEND or (p.get("owner") or "") not in van_mij:
                continue
        if not mag_project_lezen(st, pid, ik):
            continue
        sc = p.get("scope")
        per_eigenaar.setdefault(str(p.get("owner") or ""), []).append(
            (pid, (sc if isinstance(sc, str) else "") or pid))

    # GEGROEPEERD PER EIGENAAR, met `<optgroup>` — native HTML, geen JavaScript.
    #
    # WAAROM DIT NODIG IS, gemeten op prod: van Stefans 46 keuzes hangen er 35 aan één rol
    # (Strategic Lead & Founder Steward). De filter klópt — 46 van 168 — maar een platte lijst van
    # 46 waarvan 35 uit dezelfde hoek komen leest als "alles". Een kop per rol maakt van één brij
    # vier stapels, en dan zie je meteen in welke je moet zijn.
    #
    # GEEN JAVASCRIPT, en dat is geen toevalligheid maar de architectuur van dit scherm: typen +
    # Enter werkt hier omdat de browser het zelf doet. Een zoek-dropdown zou daar het eerste
    # script introduceren; `<optgroup>` kost er nul.
    opties = "<option value=''>no project&hellip;</option>"
    for eigenaar in sorted(per_eigenaar, key=lambda o: _eigenaarnaam(st, o).lower()):
        rij = sorted(per_eigenaar[eigenaar], key=lambda x: x[1].lower())
        opties += f"<optgroup label='{_e(_eigenaarnaam(st, eigenaar))}'>"
        for pid, naam in rij:
            aan = " selected" if pid == huidig else ""
            opties += f"<option value='{_e(pid)}'{aan}>{_e(naam[:70])}</option>"
        opties += "</optgroup>"
    return opties


def _verborgen(csrf_token: str, aid: str = "") -> str:
    """De velden die elke actie op deze pagina nodig heeft."""
    idveld = f"<input type='hidden' name='aid' value='{_e(aid)}'>" if aid else ""
    return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>{idveld}"
            f"<input type='hidden' name='next' value='/acties'>")


def _meta(st, it: dict, ik: str, csrf_token: str) -> str:
    """De regel onder de tekst: het project-labeltje, of het linkje om er een te kiezen.

    HIJ STAAT ER ALLEEN BIJ EEN OPEN ACTIE. Een afgevinkte regel hoef je niet meer te koppelen, en
    een lijst afgeronde items met allemaal een uitnodiging eronder is precies de ruis waar het
    ingeklapte blokje ze voor wegzet."""
    pid = str(it.get("project") or "")
    if pid:
        af = (f"<form method='post' action='/action' class='fentry-inline'>"
              f"{_verborgen(csrf_token, it['id'])}"
              f"<input type='hidden' name='project' value=''>"
              f"<button class='dellink' type='submit' name='action' value='actie_koppel' "
              f"title='Unlink'>&times;</button></form>")
        return (f"<span class='ck-meta'>"
                f"<a class='cl-filter pill' href='/project?id={_e(pid)}'>"
                f"{_e(_projectnaam(st, pid))}</a>{af}</span>")
    if it.get("done"):
        return ""
    # `<details>` EN GEEN JAVASCRIPT: dichtgeklapt is dit één grijs linkje, open een select. De
    # browser doet het openklappen zelf, en daarmee werkt het ook als er iets met een script
    # misgaat — zelfde keuze als bij de wiki-secties.
    return (f"<details class='ck-meta'><summary class='flink'>+ link to a project</summary>"
            f"<form method='post' action='/action' class='ck-doorgeef'>"
            f"{_verborgen(csrf_token, it['id'])}"
            f"<label class='sr' for='pj-{_e(it['id'])}'>Project</label>"
            f"<select id='pj-{_e(it['id'])}' name='project'>"
            f"{_projectopties(st, ik, str(it.get('project') or ''))}</select>"
            f"<button class='btn sm' type='submit' name='action' value='actie_koppel'>Link</button>"
            f"</form></details>")


def _regel(st, it: dict, ik: str, csrf_token: str) -> str:
    """Eén actie: bolletje, tekst, meta. Hetzelfde molecuul als een checklist-item."""
    klaar = bool(it.get("done"))
    bol = (f"<form method='post' action='/action' class='fentry-inline'>"
           f"{_verborgen(csrf_token, it['id'])}"
           f"<input type='hidden' name='done' value='{'0' if klaar else '1'}'>"
           f"<button class='ck-box{' on' if klaar else ''}' type='submit' name='action' "
           f"value='actie_zet' aria-label='{'Reopen' if klaar else 'Tick off'}'>"
           f"{'&check;' if klaar else ''}</button></form>")
    herk = (f"<span class='muted'> &middot; {_e(str(it.get('herkomst'))[:40])}</span>"
            if it.get("herkomst") else "")
    weg = (f"<form method='post' action='/action' class='fentry-inline'>"
           f"{_verborgen(csrf_token, it['id'])}"
           f"<button class='dellink' type='submit' name='action' value='actie_weg' "
           f"onclick=\"return confirm('Remove this action?')\">remove</button></form>")
    return (f"<div class='ck-item'>{bol}<span class='ck-txt'>"
            f"<span class='{'ck-done' if klaar else ''}'>{_e(it.get('tekst') or '')}</span>{herk}"
            f"{_meta(st, it, ik, csrf_token)}</span>{weg}</div>")


def render_acties(st, ik: str = "", csrf_token: str = "", msg: str = "") -> str:
    """De pagina. Zonder herkende mens geen lijst — een actie hoort bij iemand."""
    from nooch_village.views.overview import _banner
    if not ik:
        binnen = ("<div class='c2-main'><h1 class='ptitle'>My actions</h1>"
                  "<p class='muted'>Log in as a person to keep a list &mdash; an action belongs "
                  "to someone.</p></div>")
        return _page("My actions", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{binnen}</div>")

    rij = st.acties.voor(ik)
    open_rij = [a for a in rij if not a.get("done")]
    klaar_rij = [a for a in rij if a.get("done")]

    # HET INVOERVELD IS HET ENIGE DAT ER MOET ZIJN. `autofocus` zodat je meteen kunt typen: kom je
    # op dit scherm, dan kom je om iets op te schrijven.
    toevoegen = (f"<form method='post' action='/action' class='qadd-form'>"
                 f"{_verborgen(csrf_token)}"
                 f"<div class='qadd-row'>"
                 f"<label class='sr' for='actie-tekst'>New action</label>"
                 f"<input id='actie-tekst' name='tekst' autocomplete='off' autofocus "
                 f"placeholder='Type an action and press Enter&hellip;'>"
                 f"<button class='btn ok sm' type='submit' name='action' value='actie_add'>"
                 f"Add</button></div></form>")

    lijst = ("".join(_regel(st, a, ik, csrf_token) for a in open_rij) if open_rij
             else "<p class='muted'>Nothing open. Quiet.</p>")

    # AFGEVINKT BLIJFT GEWOON STAAN, doorgestreept, direct onder de open regels.
    #
    # HIER ZAT EEN `<details>`-BLOKJE, dichtgeklapt (besluit teruggedraaid, 27 september 2026).
    # De gedachte was "af is af, ruim het op"; de uitwerking was dat een afgevinkte actie
    # VÓÓLDE alsof hij verdween — je moest een blokje openklikken om te zien dat hij er nog
    # stond. Op papier streep je een regel door en hij blijft staan; dat je hem nog ziet is
    # precies wat "gedaan" bevredigend maakt.
    #
    # DE SCHEIDING BLIJFT WEL: een kopregel met de teller en de wis-knop. Zonder streep lopen
    # open en klaar in elkaar over, en dan is de lijst één grijze massa.
    klaar = ""
    if klaar_rij:
        wis = (f"<form method='post' action='/action' class='fentry-inline'>"
               f"{_verborgen(csrf_token)}"
               f"<button class='flink' type='submit' name='action' value='actie_wis' "
               f"onclick=\"return confirm('Clear {len(klaar_rij)} finished action"
               f"{'s' if len(klaar_rij) != 1 else ''}? This cannot be undone.')\">"
               f"clear finished</button></form>")
        klaar = (f"<div class='ck-klaar-kop'><span class='muted'>{len(klaar_rij)} done</span>"
                 f"{wis}</div>"
                 f"{''.join(_regel(st, a, ik, csrf_token) for a in klaar_rij)}")

    # `c2-smal` — EEN BREEDTE-VARIANT VOOR DIT SCHERM, en met opzet geen wijziging aan `.c2-main`
    # of `.c2-wrap` zelf: die dragen de rest van de site, waar volle breedte wél klopt (het bord,
    # een tabel, de organisatieboom). Een lijst met éénregelige acties leest slecht over 1100px —
    # het oog moet na elke regel helemaal terug. Smal en gecentreerd, zoals het prototype.
    #
    # BINNEN DE BESTAANDE `c2-`-FAMILIE en niet als eigen `act-*`-prefix: `test_ui_ratchets`
    # bevriest het aantal klasse-families, en een breedte-variant van de contentkolom hóórt bij
    # de layout-familie. Hetzelfde geldt voor `.ck-klaar-kop`, dat tussen checklist-items staat.
    main = (f"<div class='c2-main c2-smal'><h1 class='ptitle'>My actions</h1>"
            f"<p class='muted'>Jot it down like on paper. Link it to a project only if you want "
            f"to &mdash; then the people on that project see it too.</p>"
            f"{_banner(msg)}"
            f"<div class='card'>{toevoegen}{lijst}{klaar}</div></div>")
    return _page("My actions", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
