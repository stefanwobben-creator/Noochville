"""De wekelijkse Noochie-memo: het hele dorp naast de missie, als bericht aan de founder.

DRIE DINGEN DIE DEZE TOETSEN BEWAKEN, en ze zijn alle drie een GRENS en geen feature:

  1. HIJ SCHRIJFT EN VERSTUURT, VERDER NIETS. Geen spanning, geen actie, geen wiki-edit, geen
     projectwijziging, geen rol-toewijzing. Een bericht aan een mens heeft geen organisatorisch
     effect — dat is precies wat "AI is instrument, geen rol" toestaat, en alles daarbuiten niet.
  2. ÉÉN KAPOTTE BRON MAAKT DE WEEK NIET STIL. Wat er misging staat in het rapport en dus in de
     memo: een lezer moet een storing kunnen onderscheiden van een rustige week.
  3. GEEN MODEL = GEEN MEMO, en de week wordt dan NIET afgevinkt. De weekmemo stuurt bij een
     stille ladder zijn kale opsomming door (die memo ís een verzameling signalen); hier is de
     synthese het product, en een dump die zich voordoet als Noochies blik leert je hem ongeopend
     weg te klikken.

Mock-patroon uit `test_noochie_weigh_in.py`: het model wordt geïnjecteerd (`reason_fn`), zodat
deze toetsen meten wat de code doet en niet wat een provider die dag zegt.
"""
from __future__ import annotations

import time

import pytest

from nooch_village import cockpit2, noochie_memo, wiki

ROL = "mother_earth__nooch__website_developer"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Stefan", "s@nooch.earth")
    return dd, cockpit2._Stores(dd), ik


def _vul(st, nu=None):
    """Een dorp met iets te zien: een lopend project, twee acties (één oud) en een wiki-feit."""
    nu = nu or time.time()
    # DE VOLGORDE VAN AANMAKEN IS BEWUST DE VERKEERDE: het project dat niets met de strategie te
    # maken heeft komt EERST. Zo meet de sorteertoets hieronder het sorteren, en niet de toevallige
    # volgorde van de store — dat verschil bleek uit een mutatie: met de sortering eruit bleef de
    # toets groen zolang het goede project toevallig vooraan stond.
    st.projects.create(ROL, "Nieuwsbrief-template opschonen", "human", status="running")
    st.projects.create(ROL, "Composteerbare zool testen bij de leverancier", "human",
                       status="running")
    ik = st.people.all()[0]
    st.acties.add(ik.id, "Transparantie-pagina schrijven over de keten", herkomst="werkoverleg")
    oud = st.acties.add(ik.id, "Leverancier bellen over plasticvrije zolen", herkomst="werkoverleg")
    # HANDMATIG VEROUDEREN. `add` zet `at` op nu; de ouderdom is precies wat we willen meten.
    st.acties._items[oud["id"]]["at"] = nu - 30 * 86400
    st.acties._save()
    return cockpit2._Stores(st.dd if hasattr(st, "dd") else "")


def _nep(antwoord="Observatie een.\n\nVRAAG: waar kijk je weg?"):
    gezien = {}

    def reason_fn(prompt, **kw):
        gezien["prompt"] = prompt
        gezien["kw"] = kw
        return antwoord
    return reason_fn, gezien


# ══ 1. Het beeld ═════════════════════════════════════════════════════════════
def test_alle_vier_de_bronnen_komen_terug(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    beeld, rapport = noochie_memo.verzamel(dd)
    assert set(beeld) == {"projecten", "acties", "wiki", "governance"}
    assert set(rapport) == set(beeld)
    assert all("fout" not in v for v in rapport.values()), rapport


def test_een_kapotte_bron_sleept_de_rest_niet_mee(tmp_path, monkeypatch):
    """DE HELE REDEN DAT ELKE BRON APART WORDT OPGEHAALD. Zonder dit zou één stukke store de week
    stil maken — en stilte leest als "niets aan de hand"."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)

    def kapot(*a, **k):
        raise RuntimeError("store onleesbaar")
    monkeypatch.setattr(noochie_memo, "wiki_beeld", kapot)
    beeld, rapport = noochie_memo.verzamel(dd)
    assert rapport["wiki"]["fout"].startswith("RuntimeError")
    assert beeld["projecten"] and beeld["acties"], "de andere bronnen zijn meegesleept"
    # …en de lezer ziet het terug, niet als stilte maar als storing.
    assert "NIET GELEZEN" in noochie_memo.samenvatting(beeld, rapport)


def test_de_missie_sorteert_het_beeld(tmp_path):
    """DE VOORSORTERING IS GRATIS EN HERHAALBAAR (`mission.strategie_relevantie`, geen model). Een
    project dat drie strategiethema's raakt hoort boven een dat er geen raakt te staan — anders
    verdeelt het model zijn aandacht over honderd regels waarvan de helft niets met de missie te
    maken heeft."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    beeld, _ = noochie_memo.verzamel(dd)
    titels = [p["titel"] for p in beeld["projecten"]]
    assert titels[0].startswith("Composteerbare zool"), titels
    assert beeld["projecten"][0]["themas"], "het thema staat er niet bij"
    assert beeld["projecten"][-1]["score"] <= beeld["projecten"][0]["score"]


def test_ouderdom_is_een_aanname_en_geen_deadline(tmp_path):
    """`acties.py` sluit deadline en prioriteit BEWUST uit (zie de kop van die module). "Sleept al
    weken" is hier dus een benadering op ouderdom — en dat moet de prompt zeggen, anders schrijft
    het model hem op als urgentie."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    beeld, _ = noochie_memo.verzamel(dd)
    sleept = [a for a in beeld["acties"] if a["sleept"]]
    assert len(sleept) == 1 and sleept[0]["dagen"] >= noochie_memo.SLEEPT_DAGEN
    assert beeld["acties"][0]["sleept"], "de oudste staat niet bovenaan"

    reason_fn, gezien = _nep()
    noochie_memo.stel_op(dd, reason_fn=reason_fn)
    prompt = gezien["prompt"]
    assert "geen meting over urgentie" in prompt
    assert "OUDERDOM IS GEEN PRIORITEIT" in prompt


def test_acties_van_het_hele_dorp(tmp_path):
    """De store houdt de acties van IEDEREEN; `voor(person)` is het perspectief van één scherm.
    Een dorpsbrede lezer die per mens zou optellen, mist de acties van wie niet meer in `people`
    staat."""
    dd, st, ik = _dorp(tmp_path)
    ander = st.people.add("Ander", "a@nooch.earth")
    st.acties.add(ik.id, "Van mij")
    st.acties.add(ander.id, "Van een ander")
    # EN EEN ACTIE VAN EEN MENS DIE NIET (MEER) BESTAAT. Precies het geval dat een lus over
    # `people` stil laat vallen: hij hoort bij niemand, en dus zou niemand hem ooit nog zien.
    st.acties.add("verdwenen-persoon-id", "Van iemand die weg is")
    teksten = [a["tekst"] for a in noochie_memo.acties(cockpit2._Stores(dd), time.time())]
    assert {"Van mij", "Van een ander", "Van iemand die weg is"} <= set(teksten)


# ══ 2. De memo ═══════════════════════════════════════════════════════════════
def test_de_memo_krijgt_de_missie_en_het_beeld_mee(tmp_path):
    from nooch_village.mission import ANCHOR_PURPOSE
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    reason_fn, gezien = _nep()
    tekst, rapport = noochie_memo.stel_op(dd, reason_fn=reason_fn)
    assert ANCHOR_PURPOSE in gezien["prompt"]
    assert "Composteerbare zool" in gezien["prompt"]
    assert gezien["kw"]["call_site"] == "noochie_memo"
    assert tekst.startswith("🌱 Noochie kijkt naar het dorp")
    assert "Observatie een." in tekst


def test_zonder_model_geen_memo_en_de_week_blijft_open(tmp_path):
    """GEEN KALE TERUGVAL. En even belangrijk: de week wordt niet afgevinkt, zodat de volgende
    dagpuls het opnieuw probeert in plaats van een week stil over te slaan."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    uit = noochie_memo.ronde(dd, reason_fn=lambda *a, **k: None)
    assert uit["tekst"] == "" and uit["gedraaid"] is False
    assert "geen memo" in uit["reden"]
    assert not noochie_memo.al_gedraaid(dd, uit["periode"])


def test_een_model_dat_opblaast_stopt_de_memo_maar_niet_het_dorp(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)

    def boem(*a, **k):
        raise RuntimeError("provider down")
    uit = noochie_memo.ronde(dd, reason_fn=boem)
    assert uit["tekst"] == "" and uit["gedraaid"] is False
    assert uit["rapport"], "het beeld is niet eens verzameld"


# ══ 3. De ronde: ritme, bezorging en de grens ════════════════════════════════
def test_hij_landt_als_bericht_bij_de_founder(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    gezien = {}

    def bezorg(data_dir, tekst, omgeving=None):
        gezien["tekst"] = tekst
        return ["dm:stefan"]
    reason_fn, _ = _nep()
    uit = noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=bezorg)
    assert uit["gedraaid"] and uit["kanalen"] == ["dm:stefan"]
    assert gezien["tekst"] == uit["tekst"]


def test_de_week_gaat_pas_dicht_na_een_geslaagde_bezorging(tmp_path):
    """DE VOLGORDE IS DE VEILIGHEID. Andersom (eerst markeren, dan sturen) verliest een week stil
    zodra de DM nergens aankomt: het ritme zegt dan "deze week gedaan" terwijl niemand iets zag."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    reason_fn, _ = _nep()
    uit = noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=lambda *a, **k: [])
    assert uit["gedraaid"] is False and "bezorging mislukt" in uit["reden"]
    assert not noochie_memo.al_gedraaid(dd, uit["periode"])


def test_een_tweede_ronde_in_dezelfde_week_doet_niets(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    reason_fn, gezien = _nep()
    eerste = noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=lambda *a, **k: ["dm:stefan"])
    assert eerste["gedraaid"]
    gezien.clear()
    tweede = noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=lambda *a, **k: ["dm:stefan"])
    assert tweede["gedraaid"] is False and tweede["reden"] == "deze week al gedraaid"
    assert "prompt" not in gezien, "hij heeft het model tóch aangeroepen"


def test_force_negeert_de_weekpoort(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    reason_fn, _ = _nep()
    noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=lambda *a, **k: ["dm:stefan"])
    weer = noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=lambda *a, **k: ["dm:stefan"],
                              force=True)
    assert weer["gedraaid"] and weer["tekst"]


def test_een_droge_run_bezorgt_niets_en_vinkt_niets_af(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    reason_fn, _ = _nep()

    def nooit(*a, **k):
        raise AssertionError("een droge run hoort niets te bezorgen")
    uit = noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=nooit, dry=True)
    assert uit["tekst"] and uit["kanalen"] == []
    assert not noochie_memo.al_gedraaid(dd, uit["periode"])


def test_hij_raakt_niets_aan_in_het_dorp(tmp_path):
    """DE GRENS, GEMETEN EN NIET BELOOFD. Na een volledige ronde staan projecten, acties, records
    en de human inbox er precies zo bij als ervoor."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    voor = cockpit2._Stores(dd)
    stand = (
        sorted((p["id"], p["status"]) for p in voor.projects.all()),
        sorted((a["id"], a["done"]) for a in voor.acties.alle()),
        sorted(r.id for r in voor.records.all()),
        len(voor.projects.active()),
    )
    reason_fn, _ = _nep()
    noochie_memo.ronde(dd, reason_fn=reason_fn, bezorg=lambda *a, **k: ["dm:stefan"])
    na = cockpit2._Stores(dd)
    assert stand == (
        sorted((p["id"], p["status"]) for p in na.projects.all()),
        sorted((a["id"], a["done"]) for a in na.acties.alle()),
        sorted(r.id for r in na.records.all()),
        len(na.projects.active()),
    )


def test_de_grens_staat_ook_in_de_prompt(tmp_path):
    """Een model dat niet weet dat het alleen mag schrijven, stelt taken voor die als opdracht
    gelezen worden."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    reason_fn, gezien = _nep()
    noochie_memo.stel_op(dd, reason_fn=reason_fn)
    assert "Geen taken, geen toewijzingen" in gezien["prompt"]
    assert "De founder beslist" in gezien["prompt"]


# ══ 4. Het brein ═════════════════════════════════════════════════════════════
def test_de_call_site_draait_zonder_goedkope_staart():
    """`noochie_memo` staat in `PREMIUM_ONLY`: één call per week, en een goedkoop antwoord dat als
    weekoordeel gelezen wordt is erger dan geen antwoord."""
    from nooch_village.llm_keuze import HOOG_INZET, PREMIUM_ONLY
    assert "noochie_memo" in PREMIUM_ONLY
    assert "noochie_memo" in HOOG_INZET, "zonder hoog-inzet valt hij terug op de dorpsladder"


def test_de_persona_voorkeur_wint_en_blijft_alleen(tmp_path):
    """MET EEN PER-TAAK-KEUZE draait hij op precies dat model, zonder staart eronder. Zo is de
    ladder te sturen vanuit `personas.json` in plaats van vanuit code."""
    from nooch_village.llm_keuze import ladder_voor
    import types
    persona = types.SimpleNamespace(
        id="noochie_persona",
        llm={"default": "anthropic:claude-haiku-4-5",
             "per_taak": {"noochie_memo": "anthropic:claude-opus-4-8"}})
    assert ladder_voor("noochie_memo", persona) == "anthropic:claude-opus-4-8"
    # …en zonder die keuze valt hij op de dorpsbrede hoog-inzet-kop terug, niet op haiku.
    kaal = types.SimpleNamespace(id="x", llm={"default": "anthropic:claude-haiku-4-5"})
    assert ladder_voor("noochie_memo", kaal) != "anthropic:claude-haiku-4-5"


def test_het_model_hangt_aan_noochies_rol(tmp_path):
    """De ladder komt van de persona OP DE ROL (`llm_voorkeur`), niet uit een constante hier."""
    import inspect
    bron = inspect.getsource(noochie_memo._ladder)
    assert "llm_voorkeur" in bron and "NOOCHIE_ROL" in bron
    assert noochie_memo.NOOCHIE_ROL == "noochie"


# ══ 5. De daemon en de hand ══════════════════════════════════════════════════
def test_de_dagpuls_tikt_hem_aan():
    """Op de dagcadans, met zijn eigen weekpoort — net als de weekmemo. Zou hij aan een rol
    hangen, dan hing zijn ritme af van wie die rol toevallig draagt."""
    import inspect
    from nooch_village.village import Village
    bron = inspect.getsource(Village)
    assert "_veilig_noochie_memo" in bron
    assert 'self.bus.subscribe("dag_begint", lambda e: self._veilig_noochie_memo())' in bron


def test_er_is_een_cli_met_dezelfde_vlaggen():
    import pathlib
    cli = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "cli.py").read_text()
    blok = cli.split('elif mode == "noochie_memo":')[1].split("elif mode ==")[0]
    assert "--doen" in blok and "--force" in blok
    assert "dry=not doen" in blok, "de droge run is niet de standaard"
    assert "noochie_memo" in cli.split("Geldige modes")[1]


def test_het_ritmebestand_staat_los_van_de_weekmemo():
    """Twee memo's op dezelfde dagcadans; valt de een uit, dan hoort de ander gewoon te lopen."""
    from nooch_village import weekmemo
    assert noochie_memo.STATE != weekmemo.STATE
    assert noochie_memo.STATE == "noochie_memo_staat.json"


# ══ 6. Hij is ook echt te VINDEN ═════════════════════════════════════════════
#
# HET GEVAL, GEMETEN OP PRODUCTIE (30 september 2026): drie weekmemo's stonden er, in een DM met
# afzender `village`. Dat kanaal stond niet in de zijbalk onder "Direct" en kwam niet boven in de
# zoekbalk — alleen met een handgebouwde URL kwam je erin. `_dm_groepen` splitst op `_is_mens`, en
# een afzender zonder Person-record valt in de rol/systeem-groep die sinds 22 september bewust niet
# meer getoond wordt. De pijplijn werkte feilloos; niemand kon het zien.
#
# DE FIX GAAT NIET OVER DE GROEP MAAR OVER DE LIJST: wie een kanaal VOLGT, ziet het onder Direct —
# hetzelfde mechanisme dat projecten al gebruiken. De twee memo's zetten die vlag bij de eerste
# bezorging.
def _ontvanger(st):
    """WIE DE MEMO ECHT KRIJGT, uit de governance en niet uit de fixture. Het zaad-dorp vult de
    founder-rol al; een tweede vervuller erbij zetten verandert niet wie `ontvangers` kiest, en
    een toets die dat aanneemt meet zijn eigen aanname."""
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    from nooch_village import signaal
    wie, _ = signaal.ontvangers(st, "role", FOUNDER_ROLE_ID)
    assert wie, "de founder-rol heeft geen mens — dan is er niets te bezorgen"
    return wie[0]


def test_de_ontvanger_volgt_het_kanaal_na_de_eerste_memo(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    wie = _ontvanger(cockpit2._Stores(dd))
    reason_fn, _ = _nep()
    uit = noochie_memo.ronde(dd, reason_fn=reason_fn)
    assert uit["kanalen"], uit["reden"]
    st = cockpit2._Stores(dd)
    for kanaal in uit["kanalen"]:
        assert st.people.volgt(wie, kanaal), f"{kanaal} staat niet in zijn lijst"


def test_en_dan_staat_hij_onder_Direct(tmp_path):
    """DE ANDERE HELFT VAN DEZELFDE FIX. Volgen zonder dat de lijst ernaar kijkt verandert niets."""
    from nooch_village.views.messages import _dm_groepen
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    wie = _ontvanger(cockpit2._Stores(dd))
    reason_fn, _ = _nep()
    uit = noochie_memo.ronde(dd, reason_fn=reason_fn)
    st = cockpit2._Stores(dd)
    direct, rollen = _dm_groepen(st, wie)
    for kanaal in uit["kanalen"]:
        assert kanaal in direct, f"{kanaal} staat nog in de onzichtbare groep"
        assert kanaal not in rollen


def test_zonder_de_fix_zou_hij_onzichtbaar_zijn(tmp_path):
    """DE MUTATIE, ALS TOETS. Haal het volgen weg en hetzelfde kanaal valt terug in de groep die
    niemand ziet — dat is precies wat er op productie gebeurde."""
    from nooch_village.views.messages import _dm_groepen
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    wie = _ontvanger(cockpit2._Stores(dd))
    reason_fn, _ = _nep()
    uit = noochie_memo.ronde(dd, reason_fn=reason_fn)
    st = cockpit2._Stores(dd)
    for kanaal in uit["kanalen"]:
        st.people.ontvolg(wie, kanaal)
    direct, rollen = _dm_groepen(cockpit2._Stores(dd), wie)
    for kanaal in uit["kanalen"]:
        assert kanaal in rollen and kanaal not in direct


def test_een_ander_rolkanaal_blijft_wel_onzichtbaar(tmp_path):
    """DE GRENS. Zou élke rol-DM zich in je lijst zetten, dan staan de 37 systeemafzenders er
    morgen weer allemaal bij — precies wat het verbergen van die groep oploste."""
    from nooch_village import signaal
    from nooch_village.views.messages import _dm_groepen
    dd, st, ik = _dorp(tmp_path)
    # Een gewone melding, via de ONGEWIJZIGDE weg (`stuur_op_pad`, niet `stuur_en_volg`).
    kanalen = signaal.stuur_op_pad(dd, "person", ik.id, "Een losse melding", by="claims-checker")
    assert kanalen
    st = cockpit2._Stores(dd)
    direct, rollen = _dm_groepen(st, ik.id)
    for kanaal in kanalen:
        assert kanaal in rollen and kanaal not in direct
        assert not st.people.volgt(ik.id, kanaal)


# ══ 7. Governance-hygiëne: drie stillere signalen ════════════════════════════
#
# WAT ER AL WAS: onbemande rollen en het inbox-stuwmeer. Dat zijn de LUIDE signalen — een rol
# zonder vervuller roept vanzelf. De drie hieronder fluisteren, en juist daarom hoort een
# wekelijkse blik ze op te pikken:
#
#   1. een rol MET vervuller die al een maand geen spoor achterlaat;
#   2. een project dat wel LOOPT maar niet BEWEEGT (dezelfde sleept-vlag als een actie, ruimere maat);
#   3. een wiki-pagina met een kapotte grond waar al een maand niemand naar omkeek.
#
# Alle drie leveren alleen DATA aan de memo. Ze wijzen niemand aan, sturen geen spanning en
# wijzigen niets — de grens van deze module verandert niet.
def _oud(nu=None, dagen=40):
    return (nu or time.time()) - dagen * 86400


def test_een_project_dat_loopt_maar_niet_beweegt_sleept(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    nu = time.time()
    pid = st.projects.create(ROL, "Zit al een maand op dezelfde stand", "human", status="running")
    p = st.projects.get(pid)
    p["status_log"] = [{"naar": "running", "at": _oud(nu, 45)}]
    st.projects._save()
    rijen = noochie_memo.projecten(cockpit2._Stores(dd), nu)
    rij = next(r for r in rijen if r["titel"].startswith("Zit al"))
    assert rij["sleept"] is True and rij["stil_dagen"] >= noochie_memo.PROJECT_SLEEPT_DAGEN


def test_een_project_dat_net_bewoog_sleept_niet(tmp_path):
    """MUTATIE-CONTROLE: "hoe lang loopt dit al" is iets anders dan "beweegt het nog". Een project
    van 90 dagen dat vorige week een stap zette is gezond."""
    dd, st, ik = _dorp(tmp_path)
    nu = time.time()
    pid = st.projects.create(ROL, "Loopt lang maar bewoog net", "human", status="running")
    p = st.projects.get(pid)
    p["created_at"] = _oud(nu, 90)
    p["status_log"] = [{"naar": "queued", "at": _oud(nu, 90)},
                       {"naar": "running", "at": _oud(nu, 3)}]
    st.projects._save()
    rij = next(r for r in noochie_memo.projecten(cockpit2._Stores(dd), nu)
               if r["titel"].startswith("Loopt lang"))
    assert rij["sleept"] is False
    assert rij["stil_dagen"] <= 5, "de statuswijziging van drie dagen geleden telt niet mee"
    # EN `dagen` MEET IETS ANDERS: `tijdlijn` neemt de EERSTE overgang naar `running`, dus voor dit
    # project (90 dagen geleden aangemaakt, 3 dagen geleden gestart) staat daar 3. Dat is geen bug
    # maar het verschil tussen "hoe lang loopt het" en "hoe lang bestaat het" — en precies waarom
    # de sleept-vlag op de laatste BEWEGING kijkt en niet op de leeftijd.
    assert rij["dagen"] <= 5


def test_een_afgerond_project_sleept_nooit(tmp_path):
    """`active()` levert alleen niet-terminale projecten; een afgerond project beweegt per definitie
    niet meer en dat "slepend" noemen zou de lijst vullen met werk dat juist af is."""
    dd, st, ik = _dorp(tmp_path)
    nu = time.time()
    pid = st.projects.create(ROL, "Allang af", "human", status="running")
    p = st.projects.get(pid)
    p["status_log"] = [{"naar": "running", "at": _oud(nu, 200)}]
    st.projects._save()
    st.projects.complete(pid, "behaald", door=ik.id)
    titels = [r["titel"] for r in noochie_memo.projecten(cockpit2._Stores(dd), nu)]
    assert "Allang af" not in titels


def test_de_laatste_beweging_komt_uit_de_statushistorie(tmp_path):
    """NIET UIT `updated_at`: dat bumpt bij elke aanraking — een comment, een vinkje, een
    hernoeming. Juist een project met veel gepraat en geen voortgang is het signaal."""
    dd, st, ik = _dorp(tmp_path)
    nu = time.time()
    pid = st.projects.create(ROL, "Veel gepraat, geen stap", "human", status="running")
    p = st.projects.get(pid)
    p["status_log"] = [{"naar": "running", "at": _oud(nu, 60)}]
    p["updated_at"] = nu                                  # vandaag nog een comment geplaatst
    st.projects._save()
    rij = next(r for r in noochie_memo.projecten(cockpit2._Stores(dd), nu)
               if r["titel"].startswith("Veel gepraat"))
    assert rij["sleept"] is True, "de comment van vandaag telde als beweging"


def test_een_bemande_rol_zonder_spoor_is_stil(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    st.assign.assign(ROL, "person", ik.id)
    beeld, _ = noochie_memo.verzamel(dd)
    stil = {r["rol"] for r in beeld["governance"]["stil"]}
    assert ROL in stil
    assert ROL not in beeld["governance"]["onbemand"], "hij heeft juist wél een vervuller"


def test_een_rol_met_recent_werk_is_niet_stil(tmp_path):
    """DRIE SPOREN, en elk telt op zichzelf: een project, een wiki-artefact of een actie van een
    mens die de rol vervult."""
    dd, st, ik = _dorp(tmp_path)
    st.assign.assign(ROL, "person", ik.id)
    st.projects.create(ROL, "Iets wat vandaag bewoog", "human", status="running")
    beeld, _ = noochie_memo.verzamel(dd)
    assert ROL not in {r["rol"] for r in beeld["governance"]["stil"]}


def test_een_actie_van_de_vervuller_telt_voor_zijn_rol(tmp_path):
    """`acties.py` kent bewust geen rol-veld, dus de brug loopt via de vervullers. Ruim, en die
    kant op is de juiste: liever een levende rol niet flaggen dan een dode missen."""
    dd, st, ik = _dorp(tmp_path)
    st.assign.assign(ROL, "person", ik.id)
    st.acties.add(ik.id, "Vandaag iets gedaan", herkomst="werkoverleg")
    beeld, _ = noochie_memo.verzamel(dd)
    assert ROL not in {r["rol"] for r in beeld["governance"]["stil"]}


def test_een_pagina_met_een_kapotte_grond_die_blijft_liggen(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    nu = time.time()
    a = st.att.add(ROL, "note", title="Beweert iets zonder bron", body="x")
    meta = dict(a.meta or {})
    meta["feiten"] = [wiki.maak_feit("Onze zolen zijn composteerbaar")]     # geen grond → ongegrond
    st.att.update(a.id, meta=meta)
    st.att._items[a.id]["updated_at"] = _oud(nu, 60)
    st.att._save()
    w = noochie_memo.wiki_beeld(cockpit2._Stores(dd), nu)
    assert "Beweert iets zonder bron" in w["blijft_liggen"]


def test_een_verse_pagina_met_dezelfde_fout_wordt_niet_geflagd(tmp_path):
    """Een feit dat vorige week ongegrond werd is werk in uitvoering. Pas als niemand er een maand
    naar omkijkt, beweert de pagina iets wat niemand nakijkt."""
    dd, st, ik = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Net geschreven", body="x")
    meta = dict(a.meta or {})
    meta["feiten"] = [wiki.maak_feit("Onze zolen zijn composteerbaar")]
    st.att.update(a.id, meta=meta)
    w = noochie_memo.wiki_beeld(cockpit2._Stores(dd), time.time())
    assert w["blijft_liggen"] == []


def test_een_oude_pagina_met_gegronde_feiten_blijft_ongemoeid(tmp_path):
    """Oud is geen defect. Alleen een KAPOTTE grond telt — en `ongecontroleerd` hoort daar bewust
    niet bij, anders flagt elke pagina met een bronverwijzing."""
    dd, st, ik = _dorp(tmp_path)
    nu = time.time()
    a = st.att.add(ROL, "note", title="Oud maar netjes", body="x")
    meta = dict(a.meta or {})
    meta["feiten"] = [wiki.maak_feit("Uit een bron", soort="bron", ref="p",
                                     citaat="ergens", url="https://x.test/y")]
    st.att.update(a.id, meta=meta)
    st.att._items[a.id]["updated_at"] = _oud(nu, 200)
    st.att._save()
    w = noochie_memo.wiki_beeld(cockpit2._Stores(dd), nu)
    rij = next(p for p in w["met_feiten"] if p["titel"] == "Oud maar netjes")
    assert rij["zwak"] == 0 and rij["blijft_liggen"] is False
    assert "ongecontroleerd" in rij["grond"], "de bron is herkomst, geen bewijs — dat blijft zo"


def test_de_drempels_zijn_constanten_en_geen_verstopte_getallen():
    """Instelbaar op één plek, zoals `SLEEPT_DAGEN` dat al was — anders staat de maat van 'stil'
    ergens in een vergelijking waar niemand hem vindt."""
    for naam in ("SLEEPT_DAGEN", "PROJECT_SLEEPT_DAGEN", "STIL_DAGEN", "ONGEGROND_DAGEN"):
        assert isinstance(getattr(noochie_memo, naam), int)
    assert noochie_memo.PROJECT_SLEEPT_DAGEN > noochie_memo.SLEEPT_DAGEN, \
        "een project beweegt trager dan een actie; die maat hoort ruimer"


def test_de_oude_signalen_staan_er_nog_precies_zo(tmp_path):
    """REGRESSIE. De twee die er al waren (onbemand, inbox_open) veranderen niet van vorm, en de
    memo blijft dezelfde velden leveren."""
    dd, st, ik = _dorp(tmp_path)
    _vul(st)
    beeld, rapport = noochie_memo.verzamel(dd)
    g = beeld["governance"]
    assert set(g) == {"rollen", "onbemand", "stil", "inbox_open", "inbox_soorten"}
    assert isinstance(g["onbemand"], list) and all(isinstance(x, str) for x in g["onbemand"])
    assert isinstance(g["inbox_open"], int)
    assert all("fout" not in v for v in rapport.values()), rapport
