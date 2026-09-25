"""Een bestand aan een wiki-pagina hangen (26 september 2026).

EIS 6 UIT HET ONTWERPDOCUMENT: een PDF kan als blok aan een pagina worden toegevoegd —
geüpload, getoond als downloadbare kaart met de bestandsnaam.

NIETS NIEUWS GEBOUWD VOOR DE OPSLAG, en dat was de opdracht ("eerst onderzoeken of er al iets
bestaat"). Er staat al een gehard patroon:

    multipart in de request-laag, CSRF-gecheckt, `_upload_error` vóór het wegschrijven
    `BIJLAGE_TYPES`  allowlist op EXTENSIE (niet op wat de browser beweert), mét inline-ja/nee
    20 MB in de app, 25 MB in nginx — de app lager, zodat de app de nette fout geeft
    opslag       data/attachments/<eigenaar>/<uuid8>_<veilige-naam>
    serveren     per verzoek een eigen poort (`/bijlage` voor kanalen, `/file` voor projecten)

Wat hier bij komt is de DERDE consument: dezelfde ontvangst, dezelfde allowlist, dezelfde limiet,
plus een serveerroute met de poort die bij een artefact hoort.

DE BODY BLIJFT DE ENIGE BRON VAN WAARHEID (eis uit het document). Er komt geen tweede store en
geen bijlagelijst: het bestand gaat naar schijf en de UPLOAD SCHRIJFT EEN MARKDOWN-LINK in de
body. Wat je daarna ziet is gewoon het embed-blok uit de bloklaag-sprint.

DAT ÉÉN DING MOEST WIJKEN. `_md` weigert een link zonder `http(s)`-schema — fail-closed tegen
`javascript:`-urls. Onze eigen bestanden zijn ROOT-RELATIEF (`/wiki-bestand?…`), dus zonder
aanpassing linkt de renderer ze niet. De poort gaat daarom open voor precies één vorm extra: een
url die met `/` begint en NIET met `//`. Dat tweede is geen detail — `//evil.nl/x` is
protocol-relatief en gaat naar een ándere host.

VERWEESDE BESTANDEN ZIJN EEN BEWUSTE RUIL. Haalt iemand de link uit de tekst, dan blijft het
bestand op schijf staan. Dat volgt uit "de body is de enige waarheid"; een opruimer zou een tweede
administratie nodig hebben en precies het tweede-waarheid-probleem introduceren dat dit ontwerp
vermijdt.
"""
from __future__ import annotations

import os

import pytest

from nooch_village import channels, cockpit2
from nooch_village.cockpit2_util import _md, _md_naar_bron


def _zonder_commentaar(bron: str) -> str:
    """Python-commentaar eruit.

    WAAROM DIT ER MOET ZIJN. Drie mutaties bleven groen omdat mijn toetsen op een IDENTIFIER
    zochten die óók in het commentaar erboven stond: het blok legt uit dat de poort
    `_artefact_gate` is en dat `basename` de enige veilige samenvoeging is. De toets mat dus de
    uitleg en niet de code — en die uitleg blijft staan als je de regel eronder sloopt."""
    import re as _re
    return "\n".join(_re.sub(r"#.*$", "", r) for r in bron.split("\n"))


def _route_bron() -> str:
    """De hele serveerroute, geknipt op de VOLGENDE route en niet op een aantal tekens.

    Dat laatste heeft me in deze sprint al drie keer een toets laten falen op iets dat er wél
    stond: de commentaarregels zijn langer dan het venster. Een venster op tekens is geen venster
    op een functie."""
    import inspect
    bron = inspect.getsource(cockpit2)
    return _zonder_commentaar(
        bron.split('path.startswith("/wiki-bestand/")')[1].split('if path == "/file":')[0])


def _upload_bron() -> str:
    """Idem voor de upload-tak: knip op de volgende `action`-tak."""
    import inspect
    bron = inspect.getsource(cockpit2)
    return _zonder_commentaar(bron.split('fields.get("action") == "wiki_bijlage"')[1].split(
        'fields.get("action") == "kanaal_bijlage"')[0])


# ── 1. De renderer mag onze eigen bestanden linken ───────────────────────────
def test_een_eigen_bestand_wordt_een_link():
    """Root-relatief, want de host hoort niet in de inhoud te staan."""
    html = _md("zie [uittreksel.pdf](/wiki-bestand/NOTE-1/abc_uittreksel.pdf)")
    assert "<a " in html and "/wiki-bestand/NOTE-1/" in html


def test_een_protocol_relatieve_url_wordt_niet_gelinkt():
    """DE VAL IN DEZE VERSOEPELING. `//evil.nl/x` begint óók met een `/` maar gaat naar een
    ANDERE host. Wie alleen op de eerste slash toetst, zet een open deur op zijn eigen origin."""
    html = _md("[nep](//evil.nl/x.pdf)")
    assert "<a " not in html
    assert "//evil.nl" in html, "de tekst hoort gewoon te blijven staan"


def test_javascript_urls_blijven_dicht():
    """De reden dat die poort er überhaupt staat."""
    assert "<a " not in _md("[klik](javascript:alert(1))")
    assert "<a " not in _md("[klik](data:text/html,<script>)")


def test_een_eigen_pdf_op_een_eigen_regel_wordt_een_kaart():
    """Het embed-blok uit de bloklaag-sprint doet dit al; de soort komt uit de EXTENSIE.

    DAAROM STAAT DE BESTANDSNAAM IN HET PAD en niet in een query. `_embed_soort` knipt een `?`
    eraf vóór hij naar de extensie kijkt — met `/wiki-bestand?f=x.pdf` was de soort "link"
    geweest en had ik die functie moeten aanpassen. Met `/wiki-bestand/<pagina>/<bestand>.pdf`
    werkt alles wat er al staat, ongewijzigd."""
    html = _md("/wiki-bestand/NOTE-1/abc_uittreksel.pdf")
    assert "wb-emb--pdf" in html or "<figure" in html


def test_de_rondgang_houdt_een_bestandslink_heel():
    for bron in ("[uittreksel.pdf](/wiki-bestand/NOTE-1/abc_uittreksel.pdf)",
                 "tekst\n\n[a.pdf](/wiki-bestand/X/b_a.pdf)\n\nmeer tekst"):
        eerste = _md(bron, blokken=True)
        assert _md(_md_naar_bron(eerste), blokken=True) == eerste, f"breekt op {bron!r}"


# ── 2. De upload zelf ────────────────────────────────────────────────────────
def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    a = st.att.add(rol, "note", title="Company info", body="Bestaande tekst.")
    return dd, st, a


def test_de_upload_hangt_aan_het_bestaande_patroon():
    """Geen tweede allowlist, geen tweede limiet. Zou die er komen, dan lopen ze uit elkaar en is
    de ene ruimer dan de andere zonder dat iemand dat besluit."""
    tak = _upload_bron()
    assert "_upload_error" in tak, "de upload valideert niet met de gedeelde controle"
    assert "_upload_max_bytes" in tak, "de upload heeft een eigen limiet"
    assert "bijlage_type" in tak, "de upload heeft een eigen typelijst"


def test_de_poort_is_die_van_het_artefact():
    """Schrijven op een pagina is een artefact-schrijfactie: rolvervuller of Circle Lead. Dezelfde
    poort als bij het bewerken van de tekst, want dit ís de tekst bewerken."""
    # TWEE VERSCHILLENDE VRAGEN, dus twee bronnen. Of de poort er STAAT lees je in de code, en
    # dan moet het commentaar eruit — anders matcht de uitleg erboven ("de poort is
    # `_artefact_gate`") en blijft de toets groen terwijl de regel weg is. Of de KEUZE benoemd is
    # lees je juist in het commentaar, want daar hoort die regel.
    assert "_artefact_gate" in _upload_bron(), "de poort staat er niet"
    import inspect
    ruw = inspect.getsource(cockpit2).split('fields.get("action") == "wiki_bijlage"')[1].split(
        'fields.get("action") == "kanaal_bijlage"')[0]
    assert "AUTHZ:" in ruw, "elke nieuwe tak benoemt zijn autorisatiekeuze"


def test_het_bestand_belandt_onder_zijn_eigen_pagina(tmp_path):
    """Eén map per artefact: zo is bij het serveren te controleren dat een bestand bij de pagina
    hoort waar de url over spreekt, zonder een tweede administratie."""
    tak = _upload_bron()
    assert '"attachments"' in tak and '"wiki"' in tak


# ── 3. Het serveren ──────────────────────────────────────────────────────────
def test_de_serveerroute_heeft_een_eigen_poort():
    """`/file` stond hier ooit zónder leescheck en 48 projectbestanden lagen open. Die les is de
    reden dat deze toets bestaat vóór de route gebouwd is."""
    # PREFIX-MATCH, want de bestandsnaam staat ín het pad (`/wiki-bestand/<pagina>/<naam>`) —
    # dat is wat `_embed_soort` zijn extensie laat zien zonder dat die functie iets hoeft te weten.
    route = _route_bron()
    assert "username is None" in route, "de route kijkt niet wie er vraagt"


def test_de_route_serveert_alleen_wat_op_de_allowlist_staat():
    route = _route_bron()
    assert "bijlage_type" in route


def test_de_route_laat_niet_uit_de_map_ontsnappen():
    """`..%2F..%2Fetc%2Fpasswd` mag nooit een pad worden. `basename` is de enige samenvoeging die
    hier veilig is."""
    route = _route_bron()
    assert route.count("basename") >= 2, "pagina-id én bestandsnaam moeten allebei ontdaan worden"
    assert "st.att.get(" in route, "er wordt niet gecontroleerd of de pagina bestaat"


def test_pdf_gaat_inline_en_de_rest_als_download():
    """De allowlist bepaalt dat, niet de route. Een `.pdf` opent in de browser; een `.docx` niet —
    zodat een bestand nooit als pagina op onze origin uitkomt."""
    assert channels.bijlage_type("x.pdf") == ("application/pdf", True)
    assert channels.bijlage_type("x.docx")[1] is False
    assert channels.bijlage_type("x.exe") is None


# ── 4. Wat er in de pagina terechtkomt ───────────────────────────────────────
def test_de_link_komt_in_de_body_en_nergens_anders(tmp_path):
    """DE EIS: markdown blijft de enige bron van waarheid. Geen bijlagelijst, geen tweede store."""
    dd, st, a = _dorp(tmp_path)
    from nooch_village.cockpit2 import _wiki_bijlage_regel
    regel = _wiki_bijlage_regel(a.id, "abc123_uittreksel.pdf", "uittreksel.pdf")
    assert regel.startswith("[uittreksel.pdf](/wiki-bestand/")
    assert a.id in regel and "abc123_uittreksel.pdf" in regel
    # en hij rendert als kaart
    assert "<figure" in _md(regel)


def test_de_regel_ontsnapt_niet_uit_de_markdown(tmp_path):
    """Een bestandsnaam met een `]` of een `)` erin zou het link-patroon breken en de rest van de
    regel als tekst laten staan."""
    from nooch_village.cockpit2 import _wiki_bijlage_regel
    regel = _wiki_bijlage_regel("NOTE-1", "abc_raar(1)[x].pdf", "raar(1)[x].pdf")
    html = _md(regel)
    assert "<a " in html or "<figure" in html, f"de link brak: {regel!r}"


def test_alleen_ons_eigen_voorvoegsel_gaat_door_de_poort():
    """MIJN EERSTE VERSIE WAS TE RUIM: "elk pad dat met een slash begint". Twee bestaande toetsen
    wezen hem terecht af — `_md` weigert een intern pad BEWUST
    (`test_link_niet_http_geen_link_failclosed`, `test_een_link_zonder_http_wordt_geen_embed`).

    Gemeten op prod: **nul** pagina's hebben vandaag een relatieve markdown-link. De brede variant
    loste dus niets op en gaf wél een fail-closed-houding op voor alles wat morgen getypt wordt.
    Dit is het kleinste gat dat de eis dekt."""
    assert "<a " in _md("[x](/wiki-bestand/NOTE-1/a_x.pdf)")
    for pad in ("/intern/route", "/decision-coach", "/projects?pid=1", "//evil.nl/x.pdf",
                "/wiki-bestandje/NOTE-1/x.pdf"):
        assert "<a " not in _md(f"[x]({pad})"), f"{pad} kwam toch door de poort"


def test_de_drie_plekken_kennen_hetzelfde_voorvoegsel():
    """`_md`, de weg terug en de embed-regex moeten het over hetzelfde hebben. Zou dat uiteen
    lopen, dan rendert een bijlage wél en komt hij niet terug uit de rondgang (of andersom) —
    stil verlies bij de eerste bewerkronde."""
    from nooch_village.cockpit2_util import EIGEN_BESTAND, _EMBED_KAAL_RE, _EMBED_LINK_RE
    assert EIGEN_BESTAND == "/wiki-bestand/"
    assert EIGEN_BESTAND.strip("/") in _EMBED_KAAL_RE.pattern
    assert EIGEN_BESTAND.strip("/") in _EMBED_LINK_RE.pattern
    # en de route serveert precies dat voorvoegsel. (Hier stond `... or True` achter — een
    # altijd-ware assert, de val waar dit project al eerder in liep. Eén regel is genoeg.)
    import inspect
    assert f'path.startswith("{EIGEN_BESTAND}")' in inspect.getsource(cockpit2)


def test_de_opgeslagen_naam_kan_de_link_niet_breken():
    """DE SANITISER ZELF, en niet alleen de regel die hem gebruikt. Mijn eerste toets gaf een al
    schoongemaakte naam door aan `_wiki_bijlage_regel` en raakte `_wiki_bijlage_naam` dus nooit —
    een mutatie die de vertaaltabel leegmaakte bleef groen.

    Een `)` in de bestandsnaam sluit de markdown-link vroeg af en laat de rest van de regel als
    tekst staan; een `]` breekt het label. We MUNTEN die naam zelf, dus we maken hem veilig in
    plaats van te hopen."""
    from nooch_village.cockpit2 import _wiki_bijlage_naam, _wiki_bijlage_regel
    veilig = _wiki_bijlage_naam("KVK uittreksel (2026) [definitief].pdf")
    for teken in "()[]<>\"'`| ":
        assert teken not in veilig, f"{teken!r} zit nog in {veilig!r}"
    assert veilig.endswith(".pdf"), "de extensie moet heel blijven — de allowlist leest hem"
    # en de hele keten: de gemunte naam levert een link op die rendert
    assert "<figure" in _md(_wiki_bijlage_regel("NOTE-1", veilig, "x.pdf"))


def test_een_pad_in_de_bestandsnaam_overleeft_niet():
    """`../../etc/passwd` als opgestuurde naam mag nooit een pad worden."""
    from nooch_village.cockpit2 import _wiki_bijlage_naam
    assert "/" not in _wiki_bijlage_naam("../../etc/passwd")
    assert _wiki_bijlage_naam("../../etc/passwd") == "passwd"
