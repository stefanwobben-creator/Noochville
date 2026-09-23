"""Brok 4 en 5: de indeling toepassen, en de index die erop groepeert (23 september 2026).

BROK 4 IS GEEN BACKFILL, en dat is het gevolg van variant C. Het bakje wordt afgeleid, dus er valt
niets weg te schrijven voor 121 pagina's. Wat overblijft is twee dingen: een RAPPORT (waar landt
alles) en een WERKLIJST (wat valt in Overig omdat de eigenaar-rol twee kanten op wijst). De drie
pagina's op die werklijst zijn met de hand beoordeeld op hun INHOUD, en alle drie bleken een
bestaand governance-domein te hebben dat hun onderwerp dekt — dus het zijn gewone
domein-toewijzingen, geen kunstgreep, en ze verschuiven mee als zo'n domein ooit anders wordt
geclassificeerd.

BROK 5 VERANDERT WAT JE ZIET. De kolom groepeerde al per domein, maar op `a.domain` — een veld dat
tot brok 2 alleen voor policies bestond. Nu komt het bakje uit `domeinen.bakje_van`, staan de
bakjes in KETENVOLGORDE in plaats van alfabetisch, en blijven lege bakjes weg.
"""
from __future__ import annotations

import re

from nooch_village import cockpit2, domeinen, wiki_domein
from nooch_village.views.wiki import render_wiki_index


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    return dd, st, st.records.all()[0].id


def _koppen(html: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<summary>([^<]+)<span class='muted'>", html)]


# ── Brok 4: het rapport en de toewijzingen ───────────────────────────────────
def test_het_rapport_telt_alles_en_wijst_de_werklijst_aan(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    st.att.add(rol, "note", title="Met domein", domain="Materials")
    rap = wiki_domein.rapport(st)
    assert rap["totaal"] >= 1
    assert sum(len(v) for v in rap["per_bak"].values()) == rap["totaal"]


def test_elke_handmatige_toewijzing_draagt_zijn_reden():
    """Zonder reden is een handmatige indeling over een half jaar niet meer na te rekenen — dan
    staat er een domein en weet niemand meer waarom."""
    for aid, (domein, reden) in wiki_domein.TOEWIJZINGEN.items():
        assert len(reden) > 30, f"{aid} heeft geen bruikbare reden"
        assert domein in domeinen.DOMEIN_BAKJE, f"{aid} wijst naar een onbekend domein"


def test_de_dry_run_schrijft_niets(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="How we decide here")
    wiki_domein.TOEWIJZINGEN_BACKUP = dict(wiki_domein.TOEWIJZINGEN)
    wiki_domein.TOEWIJZINGEN.clear()
    wiki_domein.TOEWIJZINGEN[a.id] = ("Decision Making", "x" * 40)
    try:
        acties = wiki_domein.pas_toe(st, apply=False)
        assert acties[0][1] == "zou zetten"
        assert (st.att.get(a.id).domain or "") == "", "de dry-run heeft geschreven"
    finally:
        wiki_domein.TOEWIJZINGEN.clear()
        wiki_domein.TOEWIJZINGEN.update(wiki_domein.TOEWIJZINGEN_BACKUP)


def test_apply_zet_het_domein_en_is_idempotent(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="How we decide here")
    bewaard = dict(wiki_domein.TOEWIJZINGEN)
    wiki_domein.TOEWIJZINGEN.clear()
    wiki_domein.TOEWIJZINGEN[a.id] = ("Decision Making", "x" * 40)
    try:
        wiki_domein.pas_toe(st, apply=True)
        assert st.att.get(a.id).domain == "Decision Making"
        # en de pagina landt nu waar hij hoort
        assert domeinen.bakje_van(st.att.get(a.id), st.records.all())[0] == "hr-organisatie"
        # tweede keer: niets meer te doen
        opnieuw = wiki_domein.pas_toe(st, apply=True)
        assert opnieuw[0][1] == "staat al goed"
    finally:
        wiki_domein.TOEWIJZINGEN.clear()
        wiki_domein.TOEWIJZINGEN.update(bewaard)


def test_een_domein_buiten_de_tabel_wordt_geweigerd(tmp_path):
    """Fail-closed: anders staat er een domein en valt de pagina alsnog in Overig, terwijl het
    rapport zegt dat hij geplaatst is."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X")
    bewaard = dict(wiki_domein.TOEWIJZINGEN)
    wiki_domein.TOEWIJZINGEN.clear()
    wiki_domein.TOEWIJZINGEN[a.id] = ("Bestaat Niet", "y" * 40)
    try:
        acties = wiki_domein.pas_toe(st, apply=True)
        assert acties[0][1] == "geweigerd"
        assert (st.att.get(a.id).domain or "") == ""
    finally:
        wiki_domein.TOEWIJZINGEN.clear()
        wiki_domein.TOEWIJZINGEN.update(bewaard)


def test_een_domeinwijziging_komt_in_de_historie(tmp_path):
    """Anders dan het machine-onderhoud van `set_meta`: een domein bepaalt waar latere
    bewerkingen tegen gelogd worden, dus verplaatsen is een controleerbare wijziging."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X")
    voor = len(st.att.get(a.id).versions)
    st.att.update(a.id, domain="Materials", change_note="domein gezet: proef")
    na = st.att.get(a.id)
    assert na.domain == "Materials"
    assert len(na.versions) == voor + 1
    assert "domein gezet" in na.versions[-1]["change_note"]


# ── Brok 5: de index ─────────────────────────────────────────────────────────
def test_de_kolom_staat_in_ketenvolgorde_en_niet_alfabetisch(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    st.att.add(rol, "note", title="Een tool-pagina", domain="Nooch.earth")   # Tech & platform
    st.att.add(rol, "note", title="Een materiaal", domain="Materials")       # Shoe development
    koppen = _koppen(render_wiki_index(st, csrf_token="T"))
    volgorde = [label for _, label in domeinen.BAKJES]
    posities = [volgorde.index(k) for k in koppen if k in volgorde]
    assert posities == sorted(posities), f"de kolom staat niet in ketenvolgorde: {koppen}"
    # HIER STOND EEN ASSERT MET `or True` ERACHTER, en die was dus altijd waar — precies de val
    # waar dit project al vaker in liep. De volgorde-assert hierboven is wat deze toets bedoelt;
    # dit erbij is de controle dat er überhaupt twee verschillende bakjes in de kolom staan.
    assert len(posities) >= 2, f"te weinig bakjes om een volgorde te kunnen meten: {koppen}"


def test_lege_bakjes_staan_niet_in_de_kolom(tmp_path):
    """Een kopje waar nooit iets in zit is navigatie-ruis; op prod zijn dat er vandaag twee."""
    dd, st, rol = _dorp(tmp_path)
    st.att.add(rol, "note", title="Een materiaal", domain="Materials")
    koppen = _koppen(render_wiki_index(st, csrf_token="T"))
    assert "Fulfillment" not in koppen
    assert "Service" not in koppen


def test_de_kolom_toont_de_weergavenaam_en_niet_de_sleutel(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    st.att.add(rol, "note", title="Een materiaal", domain="Materials")
    html = render_wiki_index(st, csrf_token="T")
    assert "Shoe development" in html
    assert "shoe-development" not in html, "de interne sleutel lekt naar het scherm"


def test_een_pagina_zonder_eigen_domein_landt_via_zijn_rol(tmp_path):
    """DE HELE WINST VAN DEZE SCOPE. Vroeger viel zo'n pagina in "No domain yet"; nu volgt hij het
    domein van zijn eigenaar-rol."""
    dd, st, rol = _dorp(tmp_path)
    rec = st.records.get(rol)
    rec.definition.domains = ["Materials"]
    st.records.put(rec)
    st.att.add(rol, "note", title="Zonder eigen domein")
    koppen = _koppen(render_wiki_index(st, csrf_token="T"))
    assert "Shoe development" in koppen
    assert "No domain yet" not in koppen


def test_de_kaart_toont_hetzelfde_bakje_als_de_kolom(tmp_path):
    """Twee verschillende antwoorden op "waar hoort dit" op één scherm is precies de verwarring
    die deze scope opruimt."""
    dd, st, rol = _dorp(tmp_path)
    st.att.add(rol, "note", title="Een materiaal", domain="Materials")
    html = render_wiki_index(st, csrf_token="T")
    assert "no domain" not in html.lower(), "de kaart valt terug op de oude tekst"
    assert html.count("Shoe development") >= 2, "kolom en kaart zeggen niet hetzelfde"
