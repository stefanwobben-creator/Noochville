"""Punt 1b — het vierde kanaalsoort: een los, zelf te noemen kanaal.

**Dit draait een eerder besluit om.** Bij fase 8 (19 september 2026) is expliciet gekozen: "één
cirkelkanaal per bestaande cirkel, geen vrije onderwerp-kanalen zoals #batch-4". Op 20 september is
dat herzien omdat Messages met 442 projectkanalen onbruikbaar is zonder zoeken én zonder zelf een
kanaal te kunnen beginnen. De herziening staat in de brief; deze tests leggen het gedrag vast.

Twee eigenschappen dragen de hele keuze en staan daarom apart getest:

1. **Het id is geen slug.** `topic:<id>` met de naam apart, niet `topic:<naam>`. Zelfde argument
   als bij het gesorteerde DM-id: identiteit hoort niet aan een weergavestring te hangen.
   Hernoemen mag de trail dus niet breken.
2. **Aanmaken is idempotent op de genormaliseerde naam.** "Batch 4" naast "batch-4" zou twee halve
   gesprekken geven — precies het probleem dat losse kanalen horen op te lossen.
"""
from __future__ import annotations

import re
import tempfile

import pytest

from nooch_village import channels, cockpit2


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Topic Tester", "topic@test.nl")
    return st, mens, dd


def _ctx(st, dd, velden, username):
    return cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/messages",
                         form=velden, username=username, action="topic_add", data_dir=dd)


# ── de twee dragende eigenschappen ───────────────────────────────────────────

def test_het_id_is_geen_slug_en_hernoemen_breekt_de_trail_niet(dorp):
    st, mens, _ = dorp
    k = st.channels.maak_topic("Batch 4", door=mens.id)
    assert channels.soort_van(k) == channels.TOPIC
    assert "batch" not in k.lower(), "de naam zit in het id — dan breekt hernoemen de trail"
    st.channels.post(k, "eerste bericht", author_id=mens.id)
    assert st.channels.hernoem_topic(k, "Batch vier")
    assert st.channels.naam_van(k) == "Batch vier"
    assert len(st.channels.trail(k)) == 1          # hetzelfde gesprek, andere naam


def test_aanmaken_is_idempotent_op_de_genormaliseerde_naam(dorp):
    st, mens, _ = dorp
    eerste = st.channels.maak_topic("Batch 4", door=mens.id)
    for variant in ("batch-4", "  BATCH   4 ", "Batch  4"):
        assert st.channels.maak_topic(variant, door=mens.id) == eerste, variant
    assert len(st.channels.topics()) == 1


# ── de poort ─────────────────────────────────────────────────────────────────

def test_iedere_herkende_ingelogde_mag_er_een_maken(dorp):
    """Besluit: iedereen-ingelogd, zelfde niveau als `_claims_gate`. Dit VOEGT toe."""
    st, mens, dd = dorp
    nxt, msg = cockpit2.ACTIONS["topic_add"](_ctx(st, dd, {"naam": "Packaging"}, mens.email))
    assert msg.startswith("💬") and "/messages?k=topic" in nxt
    assert st.channels.topics()


def test_zonder_herkende_persoon_geen_kanaal(dorp):
    """Fail-closed: van elk kanaal hoort een maker bekend te zijn."""
    st, _, dd = dorp
    nxt, msg = cockpit2.ACTIONS["topic_add"](_ctx(st, dd, {"naam": "Packaging"}, "niemand@x.nl"))
    assert msg.startswith("✗") and st.channels.topics() == []


def test_een_kanaal_zonder_naam_bestaat_niet(dorp):
    st, mens, dd = dorp
    for leeg in ("", "   "):
        _nxt, msg = cockpit2.ACTIONS["topic_add"](_ctx(st, dd, {"naam": leeg}, mens.email))
        assert msg.startswith("✗")
    assert st.channels.topics() == []


def test_de_authz_keuze_staat_als_comment_bij_de_tak():
    """CLAUDE.md, harde regel: geen nieuwe dispatch-tak zonder expliciet AUTHZ-label."""
    bron = (cockpit2.__file__ or "")
    with open(bron, encoding="utf-8") as fh:
        src = fh.read()
    blok = re.search(r"def _act_topic_add\(c\):(.*?)\ndef ", src, re.S)
    assert blok, "_act_topic_add is niet te vinden"
    assert re.search(r"# AUTHZ: iedereen-ingelogd —", blok.group(1))


# ── het scherm ───────────────────────────────────────────────────────────────

def test_een_leeg_topic_staat_toch_in_de_lijst(dorp):
    """Een kanaal dat je net hebt aangemaakt en niet ziet staan, lijkt mislukt. Projectkanalen
    hebben die regel juist andersom (een leeg project is geen gesprek maar een project)."""
    from nooch_village.views.messages import render_messages
    st, mens, _ = dorp
    st.channels.maak_topic("Trade fair", door=mens.id)
    html = render_messages(st, ik=mens.id, csrf_token="t")
    # De groep heet sinds 21 september "Channels": Goals kreeg zijn eigen laag, en
    # "Topics" naast "Goals" las als twee woorden voor hetzelfde soort ding.
    assert "Channels" in html and "Trade fair" in html


def test_er_is_geen_lidmaatschap_begrip(dorp):
    """Besluit: iedereen ziet alle losse kanalen. Een tweede persoon ziet wat de eerste maakte."""
    st, mens, _ = dorp
    ander = st.people.add("Tweede Mens", "tweede@test.nl")
    st.channels.maak_topic("Packaging", door=mens.id)
    from nooch_village.views.messages import _kanalen
    groepen, _t, _g = _kanalen(st, ander.id, "")
    assert len(groepen["Channels"]) == 1
