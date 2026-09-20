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

# WAT HIER WEG IS (B2, 20 september 2026): 6 test(s) over `NotifStore` zelf. Die store bestaat
# niet meer. De twee tekst-hulpjes die hij droeg — `preview` en `volledig` — zijn verhuisd naar
# `tekstpreview.py` en worden hier nog volledig getoetst: de afkap-regel is de les uit 566
# notificaties waarvan er 193 onherstelbaar waren geamputeerd, en die les hoort niet mee te
# verdwijnen met de store die hem veroorzaakte.


# WAT HIER WEG IS (B2, 20 september 2026): 1 test(s) over het inbox-scherm. `/inbox`,
# `/inbox/verwerk`, de lade en `NotifStore` bestaan niet meer — de wachtrij is een
# DM-stroom geworden. Verwijderd omdat hun onderwerp weg is, niet omdat ze faalden.

from __future__ import annotations

from nooch_village.tekstpreview import PREVIEW_MAX, preview, volledig

LANG = ("De leverancier reageert al drie weken niet op onze vragen over de zoolmaterialen, "
        "waardoor de hele levering van de nieuwe collectie stilligt en we niet kunnen bepalen "
        "of we de deadline van het najaar nog halen. Ik heb een besluit nodig over een alternatief.")













def test_de_preview_kapt_op_een_woordgrens():
    """Een halve zin leest als een defect, niet als een samenvatting — dezelfde les als bij de
    herkomst-regel van de laatste meter."""
    kort = preview(LANG)
    assert not kort[:-1].endswith(" ")
    assert " " not in kort[-2:]


def test_een_korte_tekst_krijgt_geen_ellips():
    assert preview("kort en klaar") == "kort en klaar"


def test_oude_items_zonder_tekst_blijven_leesbaar():
    """Items van vóór deze fix hebben geen `tekst`, en hun origineel is weg. Beter de afgekapte
    waarheid dan een leeg scherm — maar het is wél afgekapt, en dat is waarom dit veld bestaat.

    `volledig` leest nog steeds een dict met `tekst`/`snippet`: de 371 gemigreerde notificaties
    dragen die vorm in hun DM-herkomst, en de afslank-rapporten lezen hem."""
    assert volledig({"snippet": "oud en afgekapt"}) == "oud en afgekapt"
    assert volledig({"tekst": "compleet", "snippet": "comp…"}) == "compleet"
    assert volledig({}) == ""


def test_de_store_bewaart_de_volle_tekst():
    """De kern van de meting, nu op de store die de berichten wél bewaart.

    `ChannelStore.post` kapt op `TEKST_MAX` (1500) — dat is een opslaggrens, geen samenvatting. De
    fout van 30 aug was een cap van 160 op het ENIGE veld, en die mag hier niet terugkeren: wie een
    lijstweergave wil, leidt hem af met `preview`."""
    import inspect

    from nooch_village import channels
    bron = inspect.getsource(channels.ChannelStore.post)
    assert "TEKST_MAX" in bron
    assert "[:160]" not in bron, "de oude harde cap staat er weer"
    assert channels.TEKST_MAX > PREVIEW_MAX * 5


def test_er_is_één_afleidingsplek():
    """`reference, don't copy`: de preview is een AFLEIDING, geen tweede feit. Wordt hij ergens
    anders opnieuw uitgerekend, dan lopen ze uit de pas."""
    import ast
    import pathlib

    wortel = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"
    plekken = []
    for f in sorted(wortel.rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef) and node.name == "preview":
                plekken.append(str(f.relative_to(wortel)))
    assert plekken == ["tekstpreview.py"], (
        f"de preview wordt op meer dan één plek uitgerekend: {plekken}")
