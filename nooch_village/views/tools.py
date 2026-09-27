"""Tools — al het gereedschap van het dorp op één plek (`/tools`).

WAAROM DIT GEEN DERDE PLEK IS. Dat was de zorg bij de Tensions/Actions-discussie: een nieuw scherm
dat náást bestaande komt te staan, en dan moet je weten waar iets ooit is neergezet. Hier gebeurt
het omgekeerde — gereedschap gaat WEG uit de wiki-tab per cirkel en komt op precies één plek te
staan. Van twee plekken naar één.

WAAROM EEN TOOL DAT VERDIENT. Hij is al een eigen soort in de data (`kind="tool"`), en hij is het
enige artefact-soort met een `url`: een note en een policy zijn er om te LEZEN, een tool om te
GEBRUIKEN. Die twee horen niet door hetzelfde filter — je zoekt een tool niet op "bij welke rol
stond hij ook alweer", je zoekt hem omdat je hem nodig hebt.

TWEE SOORTEN GEREEDSCHAP, en ze staan hier naast elkaar omdat ze voor de gebruiker hetzelfde zijn:

  1. TOOL-ARTEFACTEN uit de AttachmentStore (`by_kind("tool")`, dorpsbreed). Die kun je bewerken
     als je op hun eigenaar mag schrijven.
  2. SCHERM-TOOLS uit `_ROLE_TOOLS`/`_DOMAIN_TOOLS` in `views/overview.py`: vaste links die bij een
     rol of een domein horen. Die zijn code, geen data — ze staan hier alleen gegroepeerd.

De tabellen worden GE\xcfMPORTEERD en niet gekopieerd: \xe9\xe9n plek waar staat welk scherm bij welke rol
hoort, precies zoals `TOOL_ANCHOR` \xe9\xe9n plek is voor waar een tool-artefact hangt.
"""
from __future__ import annotations

from nooch_village import artefacts
from nooch_village.cockpit2_util import _DS_LINK, _nav, _name
from nooch_village.web_base import _e, _page


def _eigenaar(st, anchor: str) -> str:
    rec = st.records.get(anchor or "")
    return (_name(rec) if rec is not None else "") or anchor or "—"


def _kaart(st, a, mag_bewerken: bool) -> str:
    """E\xe9n tool-artefact. De TITEL IS DE LINK als er een url is — een tool open je, je leest hem
    niet. Zonder url blijft het een kaart met tekst; dat is geen fout maar een tool die nog geen
    scherm heeft."""
    url = (getattr(a, "url", "") or "").strip()
    titel = _e(a.title or a.id)
    kop = (f"<a href='{_e(url)}'><b>\U0001f6e0 {titel}</b></a>" if url
           else f"<b>\U0001f6e0 {titel}</b>")
    body = (a.body or "").strip()
    # DE EIGENAAR BLIJFT ZICHTBAAR, ook nu de tool niet meer onder zijn rol staat. Wie hem mag
    # bewerken hangt eraan, en dat weten is de helft van "mag ik hier iets aan veranderen".
    bij = (f"<a class='chip' href='/node?id={_e(a.anchor)}&tab=wiki'>"
           f"{_e(_eigenaar(st, a.anchor))}</a>")
    bewerk = ""
    if mag_bewerken:
        # NAAR DE ROL OM TE BEWERKEN, net als vanaf de wiki-permalink. Een tool is geen
        # wiki-pagina: hij heeft een url en een beschrijving, geen lopende tekst om in te typen.
        bewerk = (f" <a class='flink' href='/node?id={_e(a.anchor)}&tab=wiki&kind=tool'>"
                  f"edit on the role</a>")
    return (f"<div class='card'>{kop} {bij}{bewerk}"
            f"{f'<div class=muted>{_e(body)}</div>' if body else ''}</div>")


def render_tools(st, csrf_token: str = "", username: str | None = None, msg: str = "") -> str:
    """Alle tools van het dorp. Lezen is vrij; bewerken blijft bij de eigenaar van het artefact."""
    from nooch_village.views.overview import _DOMAIN_TOOLS, _ROLE_TOOLS, _banner, _tool_kaart

    actor = st.people.by_email(username) if username and username != "guest" else None
    actor_id = getattr(actor, "id", "")

    # ── 1. de tool-artefacten, dorpsbreed ────────────────────────────────────
    rij = sorted(st.att.by_kind("tool"), key=lambda a: (a.title or "").lower())
    kaarten = "".join(
        _kaart(st, a, bool(actor_id) and artefacts.can_write_artefact(
            "person", actor_id, a.anchor, st.records, st.assign))
        for a in rij)
    artefact_blok = (f"<div class='c2-sec'><h2>Tools</h2>{kaarten}</div>" if kaarten else
                     "<div class='c2-sec'><h2>Tools</h2>"
                     "<p class='muted'>No tools in the village yet.</p></div>")

    # ── 2. de scherm-tools per rol en per domein ─────────────────────────────
    #
    # GE\xcfMPORTEERD, NIET GEKOPIEERD. Zou deze view zijn eigen lijst houden, dan is een tool die
    # elders wordt toegevoegd hier onzichtbaar — en precies dat "twee plekken"-probleem lost dit
    # scherm juist op.
    per_rol: list[tuple[str, str]] = []
    for rec in sorted(st.records.all(), key=lambda r: (_name(r) or r.id).lower()):
        if getattr(rec, "archived", False):
            continue
        tools = list(_ROLE_TOOLS.get(rec.id, []))
        for d in (getattr(getattr(rec, "definition", None), "domains", None) or []):
            for label, desc, href in _DOMAIN_TOOLS.get(" ".join(str(d).split()).lower(), []):
                tools.append((label, desc, href.replace("{rol}", _e(rec.id))))
        if tools:
            per_rol.append((_name(rec) or rec.id,
                            "".join(_tool_kaart(l, d2, h) for l, d2, h in tools)))
    scherm_blok = ""
    if per_rol:
        blokken = "".join(f"<div class='c2-sec'><h3>{_e(naam)}</h3>"
                          f"<div class='tile-grid'>{kaarten2}</div></div>"
                          for naam, kaarten2 in per_rol)
        scherm_blok = (f"<div class='c2-sec'><h2>Screens per role</h2>"
                       f"<p class='muted'>Built-in screens that belong to a role or a domain.</p>"
                       f"{blokken}</div>")

    main = (f"<div class='c2-main'><h1 class='ptitle'>Tools</h1>"
            f"<p class='muted'>Everything in the village you can <em>use</em>, on one page. "
            f"A tool is not something to read &mdash; it is something to open.</p>"
            f"{_banner(msg)}{artefact_blok}{scherm_blok}</div>")
    return _page("Tools", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
