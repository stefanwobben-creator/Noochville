"""Inline code met enkele backticks (25 september 2026).

WAT DIT TOEVOEGT. `_md` kende `**vet**`, `*cursief*` en `~~doorhalen~~`, maar geen `` `code` ``.
Op prod staan tien backtick-paren, allemaal op DESIGNSYSTEM-001 en allemaal hexkleuren in een
TABELCEL (`| Brand Green | ``#00FF00`` | … |`) — precies waar je inline code voor gebruikt, en
precies de plek die vandaag gewoon `#00FF00` met backticks eromheen toont.

Gemeten vóór ik begon: 44 backtick-tekens totaal = 20 (de tien paren) + 24 (acht hekregels van
drie). Die som klopt exact, dus er staat nergens een losse backtick die per ongeluk een stuk tekst
zou opslokken.

EN EEN BUG DIE ER AL ZAT. De inline-regexes draaien bovenaan `_md` over de HELE string, dus vóór
de regellus die codeblokken herkent. Gevolg: `**niet vet**` ín een codeblok werd gewoon vet —
zichtbaar fout, al bleef de rondgang heel omdat `_BRON_INLINE` er weer `**` van maakt. Voor
backticks zou diezelfde volgorde erger uitpakken: een `` ` `` in een codeblok wordt dan een
`<code>` BINNEN `<pre><code>`, en de weg terug (die een `<code>` in een `<pre>` bewust negeert)
laat hem dan vallen. Dat is geen lelijke weergave meer maar inhoudsverlies.

De fix is er één, niet twee: de inhoud van een codeblok gaat met een plaatshouder uit de tekst
vóór de inline-pas en komt er daarna weer in — dezelfde truc die `_md_rijk` al toepast. Daarmee is
de nieuwe backtick veilig én is het oude lek dicht.
"""
from __future__ import annotations

from nooch_village.cockpit2_util import _md, _md_naar_bron


def _rondgang(bron: str) -> bool:
    eerste = _md(bron)
    return _md(_md_naar_bron(eerste)) == eerste


# ── 1. De weergave ───────────────────────────────────────────────────────────
def test_een_backtick_paar_wordt_code():
    assert "<code>x</code>" in _md("een `x` erin")


def test_de_backticks_zelf_verdwijnen_van_het_scherm():
    assert "`" not in _md("een `x` erin")


def test_meerdere_paren_op_een_regel():
    html = _md("`een` en `twee`")
    assert html.count("<code>") == 2


def test_een_losse_backtick_blijft_tekst():
    """DE GRENS. Zou één backtick al iets openen, dan slokt hij de rest van de regel op."""
    assert "<code>" not in _md("een ` losse backtick")
    assert "`" in _md("een ` losse backtick")


def test_lege_backticks_maken_geen_leeg_codeblokje():
    assert "<code></code>" not in _md("twee `` achter elkaar")


def test_een_backtick_paar_over_twee_regels_telt_niet():
    """Inline is inline. Een paar dat over een regelovergang heen grijpt is bijna altijd een
    ongeluk, en het resultaat zou een halve alinea in een codevorm zijn."""
    assert "<code>" not in _md("open `hier\nen dicht` daar")


# ── 2. Wat er ín de code staat blijft letterlijk ─────────────────────────────
def test_opmaak_binnen_inline_code_blijft_letterlijk():
    """`` `**x**` `` is twee sterretjes, geen vet. Draait de vet-regex eerst, dan staat er
    `<code><strong>x</strong></code>` en is de bron na één ronde veranderd."""
    html = _md("zie `**x**` hier")
    assert "<code>**x**</code>" in html
    assert "<strong>" not in html


def test_een_sterretje_binnen_inline_code_blijft_staan():
    html = _md("`a*b*c`")
    assert "<code>a*b*c</code>" in html
    assert "<em>" not in html


def test_html_binnen_inline_code_blijft_onschadelijk():
    """De escaping staat vóór alles; inline code mag daar geen gat in maken."""
    html = _md("`<script>kwaad()</script>`")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ── 3. Het codeblok: de bug die er al zat ────────────────────────────────────
def test_opmaak_in_een_codeblok_blijft_letterlijk():
    """DIT WAS STUK VOORDAT IK IETS AANRAAKTE. `**niet vet**` in een codeblok werd vet. De
    rondgang bleef heel (de weg terug maakt er weer `**` van), dus het was alleen te zien op het
    scherm — maar in een codeblok is elk teken inhoud."""
    html = _md("```\nzie **niet vet** hier\n```")
    assert "<strong>" not in html
    assert "**niet vet**" in html


def test_een_backtick_in_een_codeblok_blijft_een_backtick():
    """HET ERGE GEVAL. Zonder de plaatshouder wordt dit een `<code>` binnen `<pre><code>`, en de
    weg terug negeert een `<code>` in een `<pre>` bewust — dan verdwijnt de inhoud."""
    bron = "```\necho `datum`\n```"
    html = _md(bron)
    assert html.count("<code>") == 1, "er staat een tweede <code> in het codeblok"
    assert "`datum`" in html
    assert _md_naar_bron(html).strip() == bron


def test_een_niet_gesloten_codeblok_is_ook_beschermd():
    """`_md` sluit een openstaand hek zelf aan het eind. De bescherming moet dat volgen, anders
    is precies het laatste blok van een pagina onbeschermd."""
    html = _md("```\n**niet vet** en `geen code`")
    assert "<strong>" not in html
    assert html.count("<code>") == 1


def test_tekst_tussen_twee_codeblokken_wordt_wel_opgemaakt():
    """De bescherming mag niet doorlopen van het ene blok naar het andere."""
    html = _md("```\na\n```\n\n**wel vet** en `wel code`\n\n```\nb\n```")
    assert "<strong>wel vet</strong>" in html
    assert "<code>wel code</code>" in html


def test_de_taal_tag_blijft_werken():
    html = _md("```python\nx = 1\n```")
    assert "data-taal='python'" in html


# ── 4. De rondgang ───────────────────────────────────────────────────────────
def test_de_rondgang_houdt_inline_code_heel():
    for bron in ("een `x` erin",
                 "`een` en `twee`",
                 "zie `**x**` hier",
                 "`a*b*c`",
                 "### Kop\n\nmet `code` erin\n\n- lijst met `code`"):
        assert _rondgang(bron), f"de rondgang breekt op {bron!r}"


def test_de_rondgang_in_een_tabelcel():
    """DE ECHTE VORM VAN PROD. Alle tien de paren staan in een tabelcel, en een cel loopt langs
    een eigen buffer in `_md_naar_bron` — dus dit is geen herhaling van de toets hierboven."""
    bron = ("| Kleur | Waarde |\n|---|---|\n"
            "| Brand Green | `#00FF00` | \n| Black | `#000000` |")
    html = _md(bron)
    assert html.count("<code>") == 2, "de cellen kregen geen inline code"
    assert _rondgang(bron)


def test_een_code_in_een_pre_levert_geen_backticks_op():
    """De weg terug kende `<code>` alleen als het kind van een `<pre>` en deed daar bewust niets
    ('het hek staat op de <pre>'). Nu hij ook los bestaat, moet dat onderscheid expliciet zijn."""
    assert _md_naar_bron("<pre><code>x = 1</code></pre>").strip() == "```\nx = 1\n```"
    assert _md_naar_bron("<p>een <code>x</code> erin</p>").strip() == "een `x` erin"


def test_de_weg_terug_kent_de_tag_ook_zonder_pre_eromheen():
    """Een browser kan `<code>` los opleveren (plakken uit een andere pagina). Zonder deze regel
    valt hij buiten de whitelist en wordt het platte tekst — stil verlies."""
    assert _md_naar_bron("een <code>x</code> erin").strip() == "een `x` erin"


# ── 5. Het blokmodel merkt hier niets van ────────────────────────────────────
def test_inline_code_maakt_geen_blok():
    """Inline is inline: `` `x` `` in een alinea houdt die alinea een alinea."""
    html = _md("een `x` erin", blokken=True)
    assert "data-blok='p'" in html
    assert html.count("class='wb'") == 1


def test_een_gewone_pagina_verandert_niet():
    bron = "### Kop\n\n- een\n- twee\n\nEen alinea zonder backticks."
    assert _rondgang(bron)
    assert "<code>" not in _md(bron)


# ── 6. Twee gaten die een mutatie vond, niet ik ──────────────────────────────
def test_een_dubbele_backtick_blijft_tekst():
    """DE LOOKAROUNDS IN `_INLINE_CODE_RE`. Ik had hun reden wel in een comment gezet en niet in
    een toets — een mutatie die ze weghaalde bleef groen. Zonder lookarounds matcht ``a ``b`` c``
    op de binnenste twee backticks en blijft er aan weerszijden een losse staan:
    ``a `<code>b</code>` c``. Nu blijft het gewoon wat de schrijver typte."""
    assert _md("a ``b`` c") == "a ``b`` c"
    assert "<code>" not in _md("a ``b`` c")


def test_een_nulteken_in_de_tekst_kan_de_plaatshouder_niet_kapen():
    """DE PLAATSHOUDER IS `\\x00<n>\\x00`, en precies dat kan een schrijver zelf typen. Zonder de
    strip vooraan `_md` zijn er twee uitkomsten, allebei gemeten:

      - een index die bestaat → de INHOUD VAN HET CODEBLOK wordt midden in de zin geplakt
        (`zin met GEHEIM erin`);
      - een index die niet bestaat → `IndexError`, en dus een 500 op de pagina.

    Het teken rendert nergens, dus weghalen kost niets.

    DEZE TOETS STOND HIER EERST TE ZWAK. Hij keek of "gewone tekst" er nog stond en of er geen
    `\\x00` in de uitvoer zat — allebei waar mét het lek. En het tweede geval had geen codeblok,
    dus de `if bewaard:`-poort sloeg de herstelstap over en er viel niets te knallen. Een mutatie
    bleef daardoor groen. Nu toetst hij waar het om gaat: de inhoud blijft ín zijn blok."""
    bron = "```\nGEHEIM\n```\n\nzin met \x000\x00 erin"
    html = _md(bron)
    assert "<pre><code>GEHEIM</code></pre>" in html
    na_blok = html.split("</pre>", 1)[1]
    assert "GEHEIM" not in na_blok, "de inhoud van het codeblok lekt de zin in"
    assert "zin met" in na_blok and "\x00" not in html

    # EN MÉT een codeblok, zodat de herstelstap echt draait: een index die niet bestaat.
    assert "blijft staan" in _md("```\nX\n```\n\nalles \x0099\x00 blijft staan")
