"""Een veld dat 'samenvatting' heet maar de enige kopie is, is geen samenvatting maar een amputatie.

GEMETEN OP PROD, 30 aug 2026. `NotifStore.add` schreef `snippet=(snippet or "")[:160]` — één veld,
gecapt, en tegelijk de enige plek waar de tekst stond:

    566 notificaties · 220 exact 160 tekens · langste tekst in de hele store: 160
    223 afgekapt, waarvan 30 nog elders (project-feed) terug te vinden en 193 NIET
    voorbeeld: snippet 160 tekens, dezelfde tekst in de feed 587 tekens

En het verergerde zichzelf: `spanning_ontstaat` las `snippet` om de spanning te laten herschrijven,
dus de herschrijver kreeg de amputatie aangereikt en kon nooit compleet maken wat al incompleet was.

Nu twee velden met ÉÉN waarheid: `tekst` is volledig, `snippet` is de afgeleide preview voor de
lijst. Geen twee feiten — de afleiding staat op één plek (`preview`), dus verander die en alles
verandert mee.
"""
from __future__ import annotations

from nooch_village.notifications import NotifStore, PREVIEW_MAX, preview, volledig

LANG = ("De leverancier reageert al drie weken niet op onze vragen over de zoolmaterialen, "
        "waardoor de hele levering van de nieuwe collectie stilligt en we niet kunnen bepalen "
        "of we de deadline van het najaar nog halen. Ik heb een besluit nodig over een alternatief.")


def test_de_volle_tekst_wordt_bewaard(tmp_path):
    st = NotifStore(str(tmp_path / "n.json"))
    n = st.add("role", "r", "", by="rol", snippet=LANG)
    assert n["tekst"] == LANG
    assert volledig(n) == LANG
    assert len(LANG) > PREVIEW_MAX, "de testtekst moet langer zijn dan de preview-cap"


def test_de_preview_is_afgeleid_en_kort(tmp_path):
    st = NotifStore(str(tmp_path / "n.json"))
    n = st.add("role", "r", "", by="rol", snippet=LANG)
    assert len(n["snippet"]) <= PREVIEW_MAX
    assert n["snippet"].endswith("…")
    assert LANG.startswith(n["snippet"][:40])


def test_de_preview_kapt_op_een_woordgrens():
    """Een halve zin leest als een defect, niet als een samenvatting — dezelfde les als bij de
    herkomst-regel van de laatste meter."""
    kort = preview(LANG)
    assert not kort[:-1].endswith(" ")
    assert " " not in kort[-2:]


def test_een_korte_tekst_krijgt_geen_ellips(tmp_path):
    st = NotifStore(str(tmp_path / "n.json"))
    n = st.add("role", "r", "", by="rol", snippet="kort en klaar")
    assert n["snippet"] == "kort en klaar" and n["tekst"] == "kort en klaar"


def test_oude_items_zonder_tekst_blijven_leesbaar():
    """Items van vóór deze fix hebben geen `tekst`, en hun origineel is weg. Beter de afgekapte
    waarheid dan een leeg scherm — maar het is wél afgekapt, en dat is waarom dit veld bestaat."""
    assert volledig({"snippet": "oud en afgekapt"}) == "oud en afgekapt"
    assert volledig({}) == ""


def test_de_verrijker_krijgt_de_volle_tekst_niet_de_preview():
    """Dit las `snippet`. De herschrijver kon dus nooit compleet maken wat hem incompleet werd
    aangereikt — de amputatie plantte zich voort in de herschreven spanning."""
    import inspect

    from nooch_village import spanning_ontstaat as so
    bron = inspect.getsource(so.maak_verrijker)
    assert "volledig(n)" in bron
    assert 'n.get("snippet")' not in bron


def test_de_verwerkpagina_toont_de_volle_tekst(tmp_path):
    """De LIJST houdt de preview — daar is hij voor. De verwerk-kant leest de waarheid."""
    from nooch_village import cockpit2
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    n = st.notif.add("person", st.people.all()[0].id, "", by="rol", snippet=LANG)
    html = cockpit2.render_verwerk(st, st.notif._find(n["id"]), csrf_token="t")
    assert LANG[-60:] in html, "het einde van de spanning staat niet op het scherm"
    # en de lijst houdt het kort
    lijst = cockpit2.render_inbox(st, [("person", st.people.all()[0].id)], csrf_token="t")
    assert LANG[-60:] not in lijst


def test_er_is_één_afleidingsplek():
    """`reference, don't copy`: de preview is een AFLEIDING, geen tweede feit. Wordt hij ergens
    anders opnieuw uitgerekend, dan lopen ze uit de pas."""
    import inspect

    from nooch_village import notifications as nf
    bron = inspect.getsource(nf.NotifStore.add)
    assert "preview(volledig)" in bron
    assert "[:160]" not in bron, "de oude harde cap staat er nog"
