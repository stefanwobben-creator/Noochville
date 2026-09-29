"""noochie_memo — één keer per week kijkt Noochie naar het HELE dorp en schrijft de founder.

WAT DIT IS, EN WAT HET NIET IS. Noochie oordeelt al per dag over één Field Note
(`roles.Noochie._weigh_in`): een smalle blik op wat er die dag langskwam. Deze memo is de andere
kant: één keer per week, breed, en met de vraag die geen enkele dagelijkse blik kan stellen —
**staat het dorp nog in de richting van de missie?** Daarvoor moet je projecten, acties, wiki en
governance naast elkáár zien, en dat doet niets anders in dit dorp.

    dagelijks  smal en vaak   → drift in één stuk tekst
    wekelijks  breed en rijk  → drift in wat het dorp DOET

DE GRENS IS ABSOLUUT: schrijven en versturen, verder niets. Geen spanning, geen actie, geen
wiki-edit, geen projectwijziging, geen rol-toewijzing. Een bericht aan de founder heeft geen
organisatorisch effect — de mens leest en beslist — en dat is precies wat "AI is instrument, geen
rol" toestaat. Downstream automatisering is een apart besluit, niet een gevolg van deze memo.

VIJF BRONNEN, ELK FAIL-SOFT. Eén kapotte store mag de week niet stil maken; wat er misging komt in
het rapport en dus in de memo. Dezelfde discipline als `weekmemo._veilig`, en om dezelfde reden:
een lezer moet een STORING kunnen onderscheiden van een rustige week.

EEN DETERMINISTISCHE VOORSORTERING VÓÓR HET MODEL. `mission.strategie_relevantie` is gratis en
herhaalbaar; die bepaalt welke projecten/acties/pagina's bovenaan de samenvatting komen. Het model
krijgt dus een geordend beeld in plaats van vijf ruwe dumps, en hoeft zijn aandacht niet te
verdelen over honderd regels waarvan de helft niets met de missie te maken heeft.

WAT DE DATA NIET KAN, EN DAT STAAT OOK IN DE MEMO. Een actie (`acties.py`) heeft BEWUST geen
deadline en geen prioriteit — dat staat in de kop van die module als ontwerpkeuze. "Dit sleept al
weken" is hier dus geen meting maar een benadering op ouderdom (`SLEEPT_DAGEN`), en de prompt zegt
dat met zoveel woorden. Een model dat niet weet dat het een aanname leest, schrijft hem op als feit.
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("village.noochie_memo")

#: Het ritme leeft in een EIGEN bestand, los van de weekmemo. Ze draaien allebei op de dagpuls en
#: allebei één keer per week, maar ze horen niet aan elkaar vast te zitten: valt de een uit, dan
#: hoort de ander gewoon te lopen.
STATE = "noochie_memo_staat.json"

CALL_SITE = "noochie_memo"
AFZENDER = "noochie"

#: De rol waar de persona aan hangt die dit brein kiest (`llm_keuze.llm_voorkeur`). Eén constante,
#: want `village.CLASS_MAP` kent hem onder dezelfde sleutel.
NOOCHIE_ROL = "noochie"

#: Wanneer een OPEN actie "sleept". Geen meting maar een aanname — zie de kop van deze module.
SLEEPT_DAGEN = 14

#: Hoeveel regels per bron hoogstens in de samenvatting komen. Een model dat honderd losse feiten
#: moet wegen doet dat slechter dan twintig; wat erbuiten valt wordt GETELD, niet verzwegen
#: (dezelfde afweging als `weekmemo.PROMPT_CAP`).
CAP = 20


# ── De bronnen ───────────────────────────────────────────────────────────────

def _veilig(bron: str, rapport: dict, haal, leeg):
    """Eén bron ophalen zonder dat zijn val de andere vier meesleept."""
    try:
        uit = haal()
    except Exception as e:                                        # noqa: BLE001
        log.warning("noochie_memo: bron %r kon niet verzameld worden", bron, exc_info=True)
        rapport[bron] = {"fout": f"{type(e).__name__}: {e}"}
        return leeg
    rapport[bron] = {"aantal": len(uit) if hasattr(uit, "__len__") else 1}
    return uit


def _dagen(sinds: float | None, nu: float) -> int:
    """Hele dagen tussen `sinds` en nu. Geen tijdstempel → -1, en dat betekent "onbekend"."""
    try:
        return int(max(0.0, nu - float(sinds)) // 86400) if sinds else -1
    except (TypeError, ValueError):
        return -1


def projecten(st, nu: float) -> list[dict]:
    """De lopende projecten, met hoe lang ze lopen en hoe ver ze zijn.

    `tijdlijn()` weet of een datum uit de status-historie komt of een benadering is; die nuance
    reist mee als `datum_bron`, zodat de memo "loopt 40 dagen" niet als harde meting presenteert
    voor een project van vóór 12 september 2026 (die hebben geen log)."""
    from nooch_village.projects import checklist_progress, tijdlijn
    from nooch_village.mission import strategie_relevantie

    uit = []
    for p in st.projects.active():
        tl = tijdlijn(p, nu)
        gestart = tl.get("gestart") or tl.get("aangemaakt")
        items = [it for cl in (p.get("checklists") or []) for it in cl.get("items", [])]
        af, telbaar = checklist_progress(items)
        titel = str(p.get("scope") or p.get("id") or "")
        score, themas = strategie_relevantie(f"{titel} {p.get('description') or ''}")
        uit.append({"titel": titel, "status": str(p.get("status") or ""),
                    "dagen": _dagen(gestart, nu), "datum_bron": tl.get("bron") or "log",
                    "af": af, "telbaar": telbaar, "score": score, "themas": themas,
                    "eigenaar": str(p.get("owner") or "")})
    uit.sort(key=lambda r: (-r["score"], -r["dagen"]))
    return uit


def acties(st, nu: float) -> list[dict]:
    """De OPEN acties uit het werkoverleg, met hun ouderdom.

    ALLE MENSEN, NIET ÉÉN. `ActieStore.voor(person)` is het perspectief van één scherm; de memo
    kijkt naar het dorp. Daarom hier de hele store, met de eigenaar als veld."""
    from nooch_village.mission import strategie_relevantie

    uit = []
    for a in st.acties.alle():
        if a.get("done"):
            continue
        dagen = _dagen(a.get("at"), nu)
        tekst = str(a.get("tekst") or "")
        score, themas = strategie_relevantie(tekst)
        uit.append({"tekst": tekst, "dagen": dagen, "sleept": dagen >= SLEEPT_DAGEN,
                    "person": str(a.get("person") or ""), "project": str(a.get("project") or ""),
                    "herkomst": str(a.get("herkomst") or ""), "score": score, "themas": themas})
    uit.sort(key=lambda r: (-int(r["sleept"]), -r["score"], -r["dagen"]))
    return uit


def wiki_beeld(st) -> dict:
    """Wat er in de wiki staat, en hoe stevig het staat.

    DE GROND IS HET INTERESSANTE, niet het aantal pagina's. Een pagina met tien ongegronde feiten
    is iets anders dan een pagina met tien gegronde — en dat verschil is precies wat een
    missie-blik zou moeten opvallen."""
    from nooch_village import wiki

    ledger = getattr(st, "evidence", None)
    paginas, gronden = [], {}
    for a in wiki.verwijsbaar(st.att):
        if getattr(a, "archived", False):
            continue
        tel = wiki.telling(a, ledger=ledger, store=st.att)
        for status, n in tel.items():
            gronden[status] = gronden.get(status, 0) + n
        if tel:
            paginas.append({"titel": str(a.title or a.id), "feiten": sum(tel.values()),
                            "grond": tel})
    paginas.sort(key=lambda r: -r["feiten"])
    return {"paginas": len(list(wiki.verwijsbaar(st.att))), "met_feiten": paginas,
            "grond_totaal": gronden}


def governance_beeld(st, data_dir: str) -> dict:
    """Wat er structureel ligt: rollen zonder vervuller, en wat op de founder wacht.

    DE HUMAN INBOX IS GEEN BIJZAAK. Daar staat per definitie werk dat alleen een mens kan
    afmaken; een stapel die groeit is een signaal over het dorp, niet over de inbox."""
    from nooch_village.human_inbox import HumanInbox

    rollen = [r for r in st.records.all() if not getattr(r, "archived", False)]
    onbemand = []
    for r in rollen:
        try:
            if not st.assign.fillers_of(r.id, record=r):
                onbemand.append(str(getattr(r, "id", "")))
        except Exception:                                         # noqa: BLE001
            continue
    inbox = HumanInbox(os.path.join(data_dir or ".", "human_inbox.json"))
    wacht = inbox.pending()
    soorten: dict[str, int] = {}
    for it in wacht:
        soorten[str(it.get("type") or "?")] = soorten.get(str(it.get("type") or "?"), 0) + 1
    return {"rollen": len(rollen), "onbemand": onbemand,
            "inbox_open": len(wacht), "inbox_soorten": soorten}


def verzamel(data_dir: str, *, omgeving=None, nu: float | None = None) -> tuple[dict, dict]:
    """(beeld, rapport) over vier bronnen. Elke bron valt apart om, niet samen."""
    from nooch_village import materiaal_memo

    nu = time.time() if nu is None else nu
    st = omgeving if getattr(omgeving, "records", None) is not None else materiaal_memo._stores(data_dir)
    rapport: dict = {}
    beeld = {
        "projecten": _veilig("projecten", rapport, lambda: projecten(st, nu), []),
        "acties": _veilig("acties", rapport, lambda: acties(st, nu), []),
        "wiki": _veilig("wiki", rapport, lambda: wiki_beeld(st), {}),
        "governance": _veilig("governance", rapport, lambda: governance_beeld(st, data_dir), {}),
    }
    return beeld, rapport


# ── De voorsortering ─────────────────────────────────────────────────────────

def samenvatting(beeld: dict, rapport: dict) -> str:
    """Het beeld als geordende tekst — deterministisch, zonder model.

    DIT IS OOK DE TERUGVAL. Draait het model niet, dan is dit wat er ligt; het is geen memo, maar
    het is wel waar. Vandaar dat hij als losse functie bestaat en niet in de prompt-string."""
    d = []
    pr = beeld.get("projecten") or []
    d.append(f"PROJECTEN ({len(pr)} lopend)")
    for p in pr[:CAP]:
        thema = ", ".join(p["themas"]) if p["themas"] else "raakt geen strategiethema"
        loopt = f"{p['dagen']}d" if p["dagen"] >= 0 else "onbekend hoe lang"
        bron = "" if p["datum_bron"] == "log" else " (datum is een benadering)"
        check = f"checklist {p['af']}/{p['telbaar']}" if p["telbaar"] else "geen checklist"
        d.append(f"- [{p['status']}] {p['titel']} — {loopt}{bron}, {check} · {thema}")
    if len(pr) > CAP:
        d.append(f"  (+{len(pr) - CAP} projecten niet in deze lijst)")

    ac = beeld.get("acties") or []
    sleept = [a for a in ac if a["sleept"]]
    d.append(f"\nACTIES uit het werkoverleg ({len(ac)} open, waarvan {len(sleept)} ouder dan "
             f"{SLEEPT_DAGEN} dagen)")
    for a in ac[:CAP]:
        thema = ", ".join(a["themas"]) if a["themas"] else "raakt geen strategiethema"
        oud = f"{a['dagen']}d oud" if a["dagen"] >= 0 else "ouderdom onbekend"
        d.append(f"- {a['tekst'][:160]} — {oud} · {thema}")
    if len(ac) > CAP:
        d.append(f"  (+{len(ac) - CAP} acties niet in deze lijst)")

    w = beeld.get("wiki") or {}
    grond = ", ".join(f"{k}: {v}" for k, v in sorted((w.get("grond_totaal") or {}).items()))
    d.append(f"\nWIKI ({w.get('paginas', 0)} pagina's; feiten per grond — {grond or 'geen feiten'})")
    for p in (w.get("met_feiten") or [])[:CAP]:
        d.append(f"- {p['titel']} — {p['feiten']} feit(en): "
                 + ", ".join(f"{k} {v}" for k, v in sorted(p["grond"].items())))

    g = beeld.get("governance") or {}
    soorten = ", ".join(f"{k}: {v}" for k, v in sorted((g.get("inbox_soorten") or {}).items()))
    d.append(f"\nGOVERNANCE ({g.get('rollen', 0)} rollen, {len(g.get('onbemand') or [])} zonder "
             f"vervuller; {g.get('inbox_open', 0)} beslissing(en) wachten op de founder"
             + (f" — {soorten}" if soorten else "") + ")")
    for r in (g.get("onbemand") or [])[:CAP]:
        d.append(f"- onbemand: {r}")

    stuk = [f"{b}: {v['fout']}" for b, v in sorted(rapport.items()) if v.get("fout")]
    if stuk:
        d.append("\nNIET GELEZEN (storing, geen stilte): " + "; ".join(stuk))
    return "\n".join(d)


# ── De memo ──────────────────────────────────────────────────────────────────

def _ladder(omgeving):
    """Het brein voor deze memo: de per-taak-voorkeur van Noochie's persona.

    `noochie_memo` staat in `PREMIUM_ONLY`, dus zonder goedkope staart eronder. Dat is hier de
    bedoeling: één call per week, en een goedkoop antwoord dat als weekoordeel gelezen wordt is
    erger dan geen antwoord."""
    try:
        from nooch_village.llm_keuze import llm_voorkeur
        return llm_voorkeur(omgeving, NOOCHIE_ROL, CALL_SITE)
    except Exception:                                             # noqa: BLE001
        return None


def stel_op(data_dir: str, *, omgeving=None, reason_fn=None, nu: float | None = None
            ) -> tuple[str, dict]:
    """(memo, rapport). Lege memo = het model had niets te zeggen of was niet bereikbaar.

    GEEN KALE TERUGVAL ALS MEMO. De weekmemo stuurt bij een stille ladder zijn opsomming door, en
    daar klopt dat: die memo IS een verzameling signalen. Hier is de synthese het product — "kijk
    naar het geheel en vergelijk met de missie" — en een dump van 60 regels die zich voordoet als
    Noochies blik leert de lezer hem ongeopend weg te klikken. Geen model, geen memo; de ronde
    meldt dat, zodat het zichtbaar is in plaats van stil."""
    from nooch_village.mission import ANCHOR_PURPOSE

    beeld, rapport = verzamel(data_dir, omgeving=omgeving, nu=nu)
    kaal = samenvatting(beeld, rapport)
    prompt = (
        "Je bent Noochie, de missiestem van Nooch.earth. Eén keer per week kijk je naar het HELE "
        "dorp en schrijf je de founder.\n\n"
        f"DE MISSIE:\n{ANCHOR_PURPOSE}\n\n"
        "WAT JE KRIJGT: de stand van het dorp op vier bronnen — lopende projecten, open acties uit "
        "het werkoverleg, de wiki met de hardheid van zijn feiten, en de governance-stand. Ze zijn "
        "al gesorteerd op hoeveel ze de strategiethema's uit de missie raken.\n\n"
        "WAT JE DOET: je vergelijkt wat het dorp DOET met waar het voor bestaat. Niet per item, "
        "maar als geheel.\n\n"
        "REGELS:\n"
        "- Maximaal 500 woorden, Nederlands.\n"
        "- Noem alleen wat in het beeld staat. Verzin geen cijfers, namen, deadlines of partners.\n"
        "- Drie tot vijf observaties, elk met het bewijs eruit. Daarna één of twee eigen IDEEËN — "
        "als voorstel, niet als opdracht.\n"
        "- OUDERDOM IS GEEN PRIORITEIT. Acties hebben in dit dorp bewust geen deadline en geen "
        "prioriteitsveld; 'ouder dan "
        f"{SLEEPT_DAGEN} dagen' is dus een aanname over aandacht, geen meting over urgentie. "
        "Schrijf er nooit over alsof het een deadline is.\n"
        "- Wat er NIET gelezen kon worden, noem je als blinde vlek. Een storing is geen rustige "
        "week.\n"
        "- Geen taken, geen toewijzingen, geen 'ik ga'. De founder beslist.\n"
        "- Sluit af met één scherpe vraag aan de founder.\n\n"
        f"DE STAND VAN HET DORP:\n{kaal}")
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn        # noqa: PLC0415
    try:
        uit = reason_fn(prompt, call_site=CALL_SITE, max_tokens=1600, ladder=_ladder(omgeving))
    except Exception:                                             # noqa: BLE001
        log.warning("noochie_memo: model niet bereikbaar — geen memo deze week", exc_info=True)
        return "", rapport
    tekst = str(uit or "").strip()
    if not tekst:
        return "", rapport
    return f"🌱 Noochie kijkt naar het dorp\n\n{tekst}", rapport


def _bezorg_bij_de_founder(data_dir: str, tekst: str, omgeving=None) -> list[str]:
    """De memo als DM bij de founder. Geeft de kanalen terug waarin hij landde (leeg = nergens).

    VAST ADRES, GEEN LOOKUP — letterlijk dezelfde weg als `weekmemo._bezorg_bij_de_founder`. Wie
    de founder-rol vervult is een governance-feit; een model kiest hier niets."""
    from nooch_village import signaal
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    # Zelfde reden als bij de weekmemo: de afzender ("noochie") heeft geen Person-record, dus
    # zonder volgen staat dit gesprek in een groep die niemand ziet.
    return signaal.stuur_en_volg(data_dir, "role", FOUNDER_ROLE_ID, tekst,
                                 by=AFZENDER, omgeving=omgeving)


def _staat(data_dir: str):
    """Het ritme-bestand. HERGEBRUIKT `weekmemo._Staat`: dezelfde vraag ("deze periode al
    gedraaid?"), hetzelfde slot, ander bestand. Een tweede kopie van die klasse zou betekenen dat
    een fix aan de ene helft de andere niet bereikt."""
    from nooch_village.weekmemo import _Staat
    return _Staat(os.path.join(data_dir or ".", STATE))


def al_gedraaid(data_dir: str, periode: str) -> bool:
    return _staat(data_dir).gedraaid_in(periode)


def ronde(data_dir: str, *, omgeving=None, periode: str = "", nu: float | None = None,
          reason_fn=None, bezorg=None, force: bool = False, dry: bool = False) -> dict:
    """Eén weekronde: verzamelen → memo → bij de founder.

    DE VOLGORDE IS DE VEILIGHEID, net als bij de weekmemo: markeren gebeurt ALS LAATSTE en alleen
    na een geslaagde bezorging. Andersom verliest een week stil zodra de DM niet aankomt.

    GEEN 'AL VOORGELEGD'-BOEK. De weekmemo houdt bij welke signalen al eens in een memo stonden,
    want daar is elk signaal een losstaande vondst. Hier is het onderwerp de STAND van het dorp:
    dat een project ook vorige week al liep, is juist de observatie."""
    from nooch_village.checklists import period_key

    periode = periode or period_key("week")
    uit = {"periode": periode, "gedraaid": False, "reden": "", "rapport": {}, "tekst": "",
           "kanalen": []}
    if not force and al_gedraaid(data_dir, periode):
        uit["reden"] = "deze week al gedraaid"
        return uit

    tekst, rapport = stel_op(data_dir, omgeving=omgeving, reason_fn=reason_fn, nu=nu)
    uit["rapport"] = rapport
    uit["tekst"] = tekst
    if not tekst:
        # NIET MARKEREN. Zonder model is er geen memo, en dan hoort de volgende dagpuls het
        # opnieuw te proberen in plaats van de week als gedaan te boeken.
        uit["reden"] = "geen memo — het model gaf niets terug"
        return uit
    if dry:
        uit["reden"] = "droge run — niets bezorgd"
        return uit

    kanalen = (bezorg or _bezorg_bij_de_founder)(data_dir, tekst, omgeving)
    uit["kanalen"] = list(kanalen or [])
    if not uit["kanalen"]:
        log.warning("noochie_memo %s: bezorging kwam nergens aan — week NIET gemarkeerd", periode)
        uit["reden"] = "bezorging mislukt — week niet gemarkeerd"
        return uit

    _staat(data_dir).markeer_gedraaid(periode, aantal=1)
    uit.update(gedraaid=True, reden=f"memo bezorgd in {', '.join(uit['kanalen'])}")
    log.info("🌱 noochie_memo %s: bezorgd (%s)", periode, ", ".join(uit["kanalen"]))
    return uit
