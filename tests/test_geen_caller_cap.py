"""De cap hoort op één plek, en dat is niet bij de aanroeper.

#389 haalde de harde `[:160]` uit `NotifStore.add` en verving hem door twee velden met één
waarheid: `tekst` volledig, `snippet` afgeleid. Maar VIJF aanroepers droegen hun eigen kopie van die
cap en kapten dus nog steeds af vóór de store hem ooit zag:

    inhabitant.py      _notify_founder      ← het HOOFDKANAAL van de daemon naar de founder
    human_inbox.py     founder-melding
    skills_impl/escaleer.py
    cockpit2.py        route_werk           ← elke actie uit inbox, wizard en werkoverleg
    cockpit2.py        meld_opdrachtgever

Dat is dezelfde fout als de bug zelf, één laag hoger: één feit (hoe lang mag dit zijn) op zes
plekken. De reparatie in de store werkte, en werd door de aanroepers meteen ongedaan gemaakt.

DEZE RATCHET TELT DE VORM, niet de plek — zoals de conventie-ratchet dat na #375 doet. Een nieuwe
aanroeper die zijn eigen cap meebrengt valt op, ook als hij ergens anders staat.

SINDS B2 (20 september 2026) heet het veld anders. `NotifStore` is opgeheven en een melding is een
DM: `signaal.stuur(..., tekst)` → `ChannelStore.post(kanaal, tekst)`. De ratchet kijkt daarom naar
`tekst=` naast `snippet=` — de vorm is identiek en de fout dus ook mogelijk. De store bewaart
1500 tekens (`channels.TEKST_MAX`, een opslaggrens) en kapt niet op 160; wie bij de aanroeper op
160 kapt gooit het origineel weg vóór de store hem ooit ziet.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

# De functies die een BERICHT versturen. Een cap in hun argumenten is een cap op de enige kopie.
VERZENDERS = {"stuur", "stuur_op_pad", "_signaleer", "post"}


def _naam(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _caps_in(node: ast.AST) -> bool:
    """Staat er een `[:n]` in deze uitdrukking die NIET in een f-string-interpolatie zit?

    ONDERSCHEID DAT ERTOE DOET: `f"{kop} op '{ander[:70]}'"` kapt een AANGEHAALD fragment af binnen
    een groter bericht. Dat is geen cap op de eigen tekst maar een citaat, en dat hoort kort. Een
    ratchet die daarop afgaat wordt genegeerd — dus alles onder een `JoinedStr` telt niet mee."""
    for kind in ast.walk(node):
        if isinstance(kind, ast.JoinedStr):
            continue                                   # citaat-in-een-f-string, zie hierboven
        if isinstance(kind, ast.Subscript) and isinstance(kind.slice, ast.Slice):
            boven = kind.slice.upper
            if isinstance(boven, ast.Constant) and isinstance(boven.value, int):
                # zit deze subscript ónder een f-string in dezelfde uitdrukking?
                if not any(isinstance(x, ast.JoinedStr) and kind in set(ast.walk(x))
                           for x in ast.walk(node)):
                    return True
    return False


def _treffers() -> list[str]:
    uit = []
    for f in sorted(ROOT.rglob("*.py")):
        boom = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(boom):
            if not isinstance(node, ast.Call) or _naam(node.func) not in VERZENDERS:
                continue
            args = list(node.args) + [k.value for k in node.keywords
                                      if k.arg in ("tekst", "snippet", "text")]
            if any(_caps_in(a) for a in args):
                uit.append(f"{f.relative_to(ROOT)}:{node.lineno}: "
                           f"{_naam(node.func)}(...) kapt zijn eigen tekst af")
    return uit


def test_geen_enkele_aanroeper_kapt_zelf_af():
    treffers = _treffers()
    assert treffers == [], (
        "een aanroeper kapt de tekst zelf af. De store bewaart de VOLLEDIGE tekst en leidt de "
        "preview af; hier nog eens kappen maakt die reparatie ongedaan en het origineel is dan "
        "weg. Geef de hele tekst mee.\n" + "\n".join(treffers))


def test_een_citaat_in_een_bericht_mag_wel():
    """Onderscheid dat ertoe doet: een `[:70]` op een AANGEHAALD fragment binnen een groter bericht
    is geen cap op de eigen tekst maar een citaat, en dat hoort kort. De ratchet mag daar niet op
    afgaan, anders wordt hij genegeerd."""
    citaat = ast.parse("""_signaleer(st, "role", o, f"{kop} op '{(n.get('tekst') or '')[:70]}'")""")
    aanroep = next(n for n in ast.walk(citaat) if isinstance(n, ast.Call)
                   and _naam(n.func) == "_signaleer")
    assert not any(_caps_in(a) for a in aanroep.args), \
        "de ratchet gaat af op een citaat, en dan wordt hij genegeerd"


def test_een_echte_cap_valt_wel_op():
    """De keerzijde: zonder deze helft bewijst de test hierboven alleen dat de ratchet niets ziet."""
    echt = ast.parse('_signaleer(st, "role", o, tekst[:160])')
    aanroep = next(n for n in ast.walk(echt) if isinstance(n, ast.Call))
    assert any(_caps_in(a) for a in aanroep.args)


def test_de_afleiding_is_en_blijft_de_enige_plek():
    from nooch_village.tekstpreview import PREVIEW_MAX, preview
    assert preview("x" * 500) != "x" * 500
    assert len(preview("x" * 500)) <= PREVIEW_MAX


def test_het_founderkanaal_bewaart_nu_de_volle_tekst(tmp_path):
    """Het pad waar het het meest kostte: de daemon die de founder iets meldt.

    Sinds B2 loopt dat pad via `signaal.stuur_op_pad` naar een DM. De eis is onveranderd: wat de
    founder leest is de HELE zin, niet de eerste 160 tekens ervan."""
    from nooch_village import channels, cockpit2, signaal
    lang = ("De dagpuls draaide gisteren niet en harry_hemp gaf geen teken van leven, "
            "waarschijnlijk draait zijn service niet meer; kun je kijken of hij nog loopt? " * 2)
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    gelande = signaal.stuur_op_pad(dd, "role", "harry_hemp", lang, by="puls-wacht")
    assert gelande, "de melding landde nergens — dan is de test niets waard"
    st = signaal._MiniStores(dd)
    teksten = [e.get("text") or "" for k in gelande for e in st.channels.trail(k)]
    assert lang.strip() in teksten
    assert len(teksten[0]) > 200
    assert all(channels.soort_van(k) == channels.DM for k in gelande)
