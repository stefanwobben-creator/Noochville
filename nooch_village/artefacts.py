"""Artefacten — de domein-logica bovenop de AttachmentStore (geen aparte opslag!).

Een *artefact* is een attachment van soort note | policy | tool. Dit module beantwoordt de twee
vragen die opslag niet hoort te weten:

1. **Wie mag schrijven?** — `can_write_artefact`: alleen de huidige vervuller van de eigenaar-rol,
   of de Circle Lead van de omvattende cirkel. Identiek voor mens (person) en AI-vervuller
   (persona): de `Filler`-abstractie maakt ze niet te onderscheiden — dát is precies waarom
   "AI mag hetzelfde als een mens" gratis klopt.
2. **Wat erft een rol?** — `own_and_inherited`: eigen artefacten + die van alle voorouders langs
   de breadcrumb waar `inherit=True` en `status="active"`, elk getagd met hun herkomst.

De data leeft op één plek (attachments.json via AttachmentStore); dit is puur leeslogica +
autorisatie, geen tweede waarheid.
"""
from __future__ import annotations

import json
import os
import time

from nooch_village import org
from nooch_village.util import file_lock


def _name(rec) -> str:
    """Weergavenaam van een record voor het herkomst-pad; valt terug op de id."""
    if rec is None:
        return ""
    d = getattr(rec, "definition", None)
    return (getattr(d, "name", "") or "").strip() or getattr(rec, "id", "")


#: De wortelcirkel. Hij stond op drie plekken in `cockpit2.py` als kale string ("mother_earth",
#: in `_anchor_gate`, `mag_kanaal_verwijderen` en `wis_namens`); dit is de eerste plek waar hij
#: een naam krijgt. Nieuwe code verwijst hierheen — `reference, don't copy`. De drie bestaande
#: plekken blijven staan tot iemand er toch aan werkt (het ratchet-principe uit CLAUDE.md).
ANCHOR_CIRCLE = "mother_earth"

#: WAAR EEN TOOL-ARTEFACT STANDAARD HANGT, en waarom dat een cirkel is en geen rol.
#:
#: Een tool is dorpsbreed bruikbaar: de copy-prompt-generator en de decision coach staan open voor
#: iedereen. Hem onder de rol hángen die hem "het meest" gebruikt maakt van die rol een poortwachter
#: die niemand bedoeld heeft — en het bepaalt wie hem mag bewerken, want `can_write_artefact`
#: kijkt naar de eigenaar-rol. Op de anchor-cirkel is dat voor iedereen gelijk.
#:
#: DIT IS EEN ALGEMENE REGEL, GEEN OORDEEL PER TOOL (besluit Stefan, 27 september 2026). Een derde
#: tool volgt hem zonder dat iemand opnieuw hoeft te beslissen: hij leest deze constante.
TOOL_ANCHOR = ANCHOR_CIRCLE


def verhuis_tools_naar_anchor(store, data_dir: str = "", records=None) -> list[tuple[str, str]]:
    """Elk tool-artefact hangt aan `TOOL_ANCHOR`. Idempotent; geeft terug wat er verhuisde.

    DE REGEL STOND ALLEEN IN DE ZAAI-WEG (28 september 2026). `TOOL_ANCHOR` bepaalde waar een
    ZAAD-tool landde, maar bestaande artefacten van vóór die regel bleven hangen waar ze stonden —
    op prod drie stuks, waarvan één (het Website Handboek) met echte, door een mens geschreven
    inhoud. Een regel die alleen voor nieuwe gevallen geldt is geen regel maar een gewoonte.

    WAAROM VERHUIZEN EN NIET WEGGOOIEN. De inhoud is van de rol die hem schreef en blijft
    ongewijzigd; alleen het bezit verschuift naar de cirkel, precies zoals `TOOL_ANCHOR` uitlegt:
    een tool is dorpsbreed, en hem onder één rol hangen maakt de vervuller van die rol tot
    poortwachter van iets dat voor iedereen open staat.

    HET ID BLIJFT, dus elke permalink en elke verwijzing blijft werken (zie `verplaats`).

    Fail-soft per artefact: een store die één verhuizing weigert houdt de rest niet tegen. Draait
    bij elke start mee met de andere migraties, en doet vanaf de tweede keer niets."""
    verhuisd: list[tuple[str, str]] = []
    for a in store.by_kind("tool", include_archived=True):
        oud = getattr(a, "anchor", "") or ""
        if oud == TOOL_ANCHOR:
            continue
        nieuw = store.verplaats(a.id, TOOL_ANCHOR, actor_id="system", actor_type="persona",
                                change_note=f"tools horen bij de cirkel: verhuisd van {oud}")
        if nieuw is None:
            continue
        verhuisd.append((a.id, oud))
        if data_dir and records is not None:
            log_change(data_dir, action="edit", artefact=nieuw, records=records,
                       actor_id="system", actor_type="persona",
                       governance_ref=f"role:{TOOL_ANCHOR}")
    return verhuisd


def circle_of(owner_role_id: str, records) -> str | None:
    """De omvattende cirkel van een eigenaar: een cirkel → zichzelf; een rol → zijn ouder.
    Spiegelt `resolve_circle_id` maar zonder de "ii:"-prefix (een artefact-eigenaar is altijd
    een echt rol-/cirkel-record)."""
    rec = records.get(owner_role_id)
    if rec is None:
        return None
    return owner_role_id if org.is_circle(rec) else getattr(rec, "parent", None)


def requires_governance_ref(owner_role_id: str, records) -> bool:
    """True als de eigenaar de anchor-cirkel is (parent is None). Elke schrijfactie op de anchor
    vereist een niet-lege governance_ref (audittrail naar het governance-besluit)."""
    rec = records.get(owner_role_id)
    return rec is not None and not getattr(rec, "parent", None)


def alle_domeinen(records) -> list[str]:
    """Elk domein dat governance vandaag aan een WAKKERE, niet-gearchiveerde rol heeft toegewezen.

    ÉÉN BRON VOOR TWEE DINGEN: de keuzelijst op het scherm, én de controle op de server. Zou de
    server een andere lijst hanteren dan het formulier aanbiedt, dan is er een keuze die je kunt
    maken en die daarna wordt geweigerd — of, erger, andersom.

    Een SLAPENDE rol telt niet mee, om dezelfde reden als bij `_role_options`: een domein bij een
    rol die stilstaat is een bureau waar niemand zit. Ontdubbeld en op alfabet, want twee rollen
    kunnen hetzelfde domein houden (een governance-fout, maar hij komt voor)."""
    uit = set()
    for r in records.all():
        if getattr(r, "archived", False) or getattr(r, "slaapt", False):
            continue
        for d in (getattr(getattr(r, "definition", None), "domains", None) or []):
            naam = str(d).strip()
            if naam:
                uit.add(naam)
    return sorted(uit, key=str.lower)


def mag_schrijven_op_domein(st, domein: str, actor_id: str, *, circle_id: str = "") -> bool:
    """Mag deze persoon schrijven op DIT DOMEIN? Één regel, twee gebruikers.

    HET BEWERKRECHT HANGT AAN HET DOMEIN EN NIET MEER AAN DE ROL (26 september 2026). Een pagina
    hoorde bij een rol, en alleen wie die rol vervulde mocht eraan schrijven — ook als de pagina
    over niets in het bijzonder ging. Dat maakte het dorp nodeloos gesloten: je moest een mandaat
    hebben om een aantekening te maken.

    Wat je wél beschermt is een DOMEIN. Dat is een verklaring ("deze rol bezit dit onderwerp"),
    en wie daarin schrijft raakt iets wat een ander in beheer heeft.

        geen domein        → elke herkende persoon mag schrijven
        domein met één     → de vervuller van die rol, of de Circle Lead, of de ANCHOR-LEAD
        eigenaar-rol
        configuratiefout   → open, zoals `domein_eigenaar` zelf ook terugvalt

    EEN CONFIGURATIEFOUT SLUIT NIEMAND BUITEN. `domein_eigenaar` geeft een lege rol terug als het
    domein niet bestaat, niemand het houdt, of twee rollen het allebei houden. Dat zijn fouten in
    de governance-administratie en die horen daar opgelost te worden — niet doordat een pagina
    stilzwijgend op slot gaat en niemand meer weet waarom.

    GEMETEN WAT DAT VANDAAG BETEKENT (prod, 26 september, 13 actieve artefacten): 5 komen open te
    staan en 8 blijven gegated. Eén van die 5 is een POLICY op een domein dat nul houders heeft —
    fail-open maakt die dus voor iedereen bewerkbaar. Dat is de prijs van "een governance-fout
    sluit niemand buiten", en hij hoort zichtbaar te zijn.

    `circle_id` IS DE CIRKEL WAARVAN DE LEAD ER SOWIESO BIJ MAG. De aanroeper weet welke dat is —
    die van de eigenaar-rol van het artefact — en hier is die niet af te leiden, want het domein
    kan bij een rol in een andere cirkel horen.

    Verwijderen loopt hier NIET langs: `_act_artefact_delete` blijft Circle-Lead-only, ongeacht
    domein. Weggooien is onomkeerbaar en dat is een andere vraag dan schrijven."""
    from nooch_village import triage_rol

    if not actor_id:
        return False
    d = (domein or "").strip()
    if not d:
        return True
    houder = (triage_rol.domein_eigenaar(st, d) or {}).get("rol") or ""
    if not houder:
        return True                                   # configuratiefout — zie de docstring
    if any(f.type == "person" and f.id == actor_id
           for f in st.assign.fillers_of(houder, st.records.get(houder))):
        return True
    if not circle_id:
        circle_id = circle_of(houder, st.records) or ""
    if circle_id and _is_lead("person", actor_id, circle_id, st.records, st.assign):
        return True
    # DE ANCHOR-LEAD MAG ALTIJD — dezelfde derde trede als in `can_write_artefact`, en om dezelfde
    # reden. Deze functie is de SERVER-poort (`_artefact_gate`) waar `can_write_artefact` het
    # SCHERM is; alleen de ene verruimen laat de knop verschijnen op iets wat de server daarna
    # weigert. Dat verschil kostte #610 al een ronde, en het is precies andersom even stuk.
    return _is_lead("person", actor_id, ANCHOR_CIRCLE, st.records, st.assign)


def can_write_artefact(actor_type: str, actor_id: str, owner_role_id: str,
                       records, assignments) -> bool:
    """Mag deze actor artefacten van `owner_role_id` aanmaken/bewerken/archiveren?

    Regel (identiek voor person en persona) — DRIE treden, elk voldoende:

      1. actor is huidige filler van de eigenaar-rol;
      2. actor is filler van de Circle Lead-rol van de OMVATTENDE cirkel;
      3. actor is de ANCHOR-LEAD — Circle Lead van de wortelcirkel — en dan op elk artefact,
         ongeacht in welke cirkel de eigenaar-rol zit.

    DE DERDE IS NIEUW (27 september 2026, besluit Stefan) en is GEEN nieuw governance-begrip: het
    is dezelfde terugval die `mag_kanaal_verwijderen` en `wis_namens` al gebruiken — wie de hele
    organisatie leidt, kan overal opruimen. Zonder deze trede liep opruimwerk in de wiki telkens
    vast op een artefact van een rol twee cirkels verderop, terwijl de anchor-lead die rol wel
    mag opheffen. Dat is niet consistent: mogen dat een rol bestaat, maar niet dat zijn notitie
    bijgewerkt wordt.

    TREDE 2 DEKT DE ANCHOR NIET VANZELF. Voor een artefact op `mother_earth` zelf geeft
    `circle_of` de anchor terug en valt het samen; voor een rol in een SUBcirkel is de Circle Lead
    van die subcirkel iemand anders. Dat verschil is precies het gat.

    Geërfde artefacten zijn nooit schrijfbaar — daar is `owner_role_id` niet de eigen rol, dus
    valt de check vanzelf weg.
    """
    if actor_type not in ("person", "persona") or not actor_id or not owner_role_id:
        return False
    rec = records.get(owner_role_id)
    if rec is None:
        return False
    if any(f.type == actor_type and f.id == actor_id
           for f in assignments.fillers_of(owner_role_id, rec)):
        return True
    circle_id = circle_of(owner_role_id, records)
    if circle_id and _is_lead(actor_type, actor_id, circle_id, records, assignments):
        return True
    return _is_lead(actor_type, actor_id, ANCHOR_CIRCLE, records, assignments)


def _is_lead(actor_type: str, actor_id: str, circle_id: str, records, assignments) -> bool:
    """Vervult deze actor de Circle Lead-rol van `circle_id`? Stond twee keer uitgeschreven zodra
    de anchor-trede erbij kwam; één vorm, twee aanroepers."""
    lead_role = f"{circle_id}__circle_lead"
    return any(f.type == actor_type and f.id == actor_id
               for f in assignments.fillers_of(lead_role, records.get(lead_role)))


def erfketen(anchor: str, inherit: bool, records) -> list[str]:
    """De rollen die dit artefact 'zien': de eigenaar zelf, plus — als het erft — al zijn nazaten.
    Dit is de referentie die de seen-markering (brok 5) nodig heeft om te weten wélke rollen in de
    keten een 'gewijzigd sinds laatst gezien'-stip krijgen."""
    chain = [anchor]
    if inherit:
        chain += [r.id for r in org.descendants(records.all(), anchor)]
    return chain


def norm_titel(titel) -> str:
    """De titel zoals een zaai-routine hem vergelijkt: één regel, kleine letters, geen dubbele
    spaties. Stond drie keer uitgeschreven (`wiki_seed._bestaat` en de twee `zorg_voor_tool`'s);
    nu één vorm, want een tombstone die net anders normaliseert dan de bestaat-check is geen
    tombstone."""
    return " ".join(str(titel or "").split()).lower()


def is_gewist(data_dir: str, anchor: str, titel: str) -> bool:
    """Is deze plek — (eigenaar, titel) — met opzet leeggemaakt? Dan hoort er niets terug te groeien.

    HET GAT DAT DIT DICHT. Elke zaai-routine controleert of het artefact er al staat, `archief
    meegerekend`. Dat dekt archiveren, maar een HARD verwijderd artefact (`AttachmentStore.remove`)
    laat helemaal geen rij achter — dus de eerstvolgende zaai-run ziet een lege plek en zaait
    opnieuw. Stefan verwijderde TOOL-STRATE-001 vier keer op één dag; hij kwam vier keer terug.

    GEGROND OP HET CHANGELOG, niet op een nieuwe store. `log_change` schrijft de verwijdering al
    weg vóór de rij verdwijnt (zie `_act_artefact_delete`), dus het spoor is er — het droeg alleen
    de titel niet. Een aparte tombstone-store zou hetzelfde feit op een tweede plek zetten, en dat
    is precies wat `reference, don't copy` verbiedt.

    DE LAATSTE ACTIE TELT, niet of er ooit een delete was. Maakt een mens daarna bewust opnieuw
    een artefact met die titel, dan staat er een `add` ná de `delete` en is de plek weer levend.
    Zo heft de tombstone zichzelf op zonder dat iemand hem hoeft te \"wissen\" — en zo blijft de
    harde eis overeind dat dit alleen de SEEDER tegenhoudt en nooit de mens.

    REGELS ZONDER TITEL TELLEN NIET MEE. Het veld bestaat pas sinds 27 september 2026; alles wat
    daarvóór is verwijderd draagt hem niet en is langs deze weg niet te herkennen. Dat is bewust
    fail-OPEN: liever een seeder die één keer te vaak zaait dan een tombstone die op een lege
    vergelijking dichtslaat en een tool voorgoed onvindbaar maakt.

    Fail-soft op het bestand: geen changelog, een stukke regel of een leesfout → niets gewist."""
    doel = norm_titel(titel)
    if not (anchor and doel):
        return False
    path = os.path.join(data_dir or ".", "artefact_changelog.jsonl")
    laatste = ""
    try:
        with open(path, encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    rij = json.loads(regel)
                except ValueError:
                    continue
                if rij.get("anchor") != anchor or norm_titel(rij.get("title")) != doel:
                    continue
                laatste = str(rij.get("action") or "")
    except OSError:
        return False
    return laatste == "delete"


def is_gewist_bij(store, anchor: str, titel: str) -> bool:
    """`is_gewist`, maar met de datamap afgeleid uit de STORE. Zaai-routines krijgen geen
    `data_dir` mee — ze krijgen een `AttachmentStore`, en die weet waar hij staat
    (`<data_dir>/attachments.json`). Zo hoeft geen enkele seeder-signatuur te veranderen.

    Fail-soft: een store zonder pad levert "niet gewist" op, en dan gedraagt de seeder zich als
    voorheen."""
    pad = getattr(store, "path", "") or ""
    return bool(pad) and is_gewist(os.path.dirname(pad), anchor, titel)


def log_change(data_dir: str, *, action: str, artefact, records,
               actor_id: str = "", actor_type: str = "", governance_ref: str = "") -> dict:
    """Append-only changelog van artefact-mutaties (`data/artefact_changelog.jsonl`).

    Elke regel legt vast: tijdstip, actie (add|edit|archive), artefact-id, eigenaar (anchor),
    de erfketen-snapshot (welke rollen dit zien) en de governance_ref. Dit is de databron voor de
    'gewijzigd sinds laatst gezien'-markering in brok 5.

    De append staat bewust onder hetzelfde per-pad slot (`util.file_lock`) als de store-mutaties,
    zodat regel-atomiciteit gegarandeerd is en niet toevallig van de regellengte afhangt.
    """
    entry = {
        "ts": time.time(),
        "action": action,
        "artefact_id": getattr(artefact, "id", ""),
        # DE TITEL, sinds 27 september 2026. Een zaai-routine kent het ID niet dat een artefact
        # ooit had — hij kent alleen de plek en de naam. Zonder dit veld is een verwijdering dus
        # niet terug te vinden vanuit de seeder, en zaait hij gewoon opnieuw. Zie `is_gewist`.
        "title": getattr(artefact, "title", "") or "",
        "anchor": getattr(artefact, "anchor", ""),
        "kind": getattr(artefact, "kind", ""),
        "inherit": bool(getattr(artefact, "inherit", False)),
        "actor_id": actor_id or "",
        "actor_type": actor_type or "",
        "governance_ref": governance_ref or "",
        "erfketen": erfketen(getattr(artefact, "anchor", ""),
                             bool(getattr(artefact, "inherit", False)), records),
    }
    path = os.path.join(data_dir, "artefact_changelog.jsonl")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with file_lock(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _feiten_van(a, store, ledger) -> list[dict]:
    """De feiten van een wiki-pagina (kind="note") mét hun grond, LIVE bepaald.

    Een AI-vervuller leest deze context als systeemprompt. Zonder de grond erbij zou hij een feit
    citeren zonder te kunnen zeggen waar het vandaan komt — en zonder te zien dat het certificaat
    eronder verlopen is. Daarom reist de uitkomst mee, niet het oordeel van gisteren."""
    from nooch_village import wiki

    if a.kind != wiki.PAGINA_KIND:
        return []
    uit = []
    for f in wiki.feiten(a):
        g = wiki.grond_status(f, ledger=ledger, store=store)
        uit.append({"tekst": f.get("tekst") or "", "grond": g["status"],
                    "grond_label": g["label"], "grond_detail": g["detail"],
                    "bron": g.get("url") or "", "citaat": g.get("citaat") or ""})
    return uit


def _art_item(a, *, editable: bool, store=None, ledger=None) -> dict:
    """Eén artefact als serialisatie-dict. `editable` = mag deze rol het bewerken (eigen=True,
    geërfd=False). `mutation_path="artefact"`: te wijzigen via de artefact-routes (bij de eigenaar)."""
    d = {"id": a.id, "kind": a.kind, "title": a.title, "body": a.body,
         "status": a.status, "editable": editable, "mutation_path": "artefact",
         "updated_at": getattr(a, "updated_at", 0)}
    if a.kind == "policy":
        d["domain"] = getattr(a, "domain", "")
    if a.kind == "tool":
        d["url"] = a.url
    if a.kind == "note":
        d["feiten"] = _feiten_van(a, store, ledger)
    return d


def _art_block(role_id: str, kind: str, records, store, ledger=None) -> dict:
    """{"own": [...], "inherited": [...]} voor één artefact-soort; geërfde items dragen het
    herkomst-pad ("via <naam>")."""
    oi = own_and_inherited(role_id, kind, records, store)
    own = [_art_item(a, editable=True, store=store, ledger=ledger) for a in oi["own"]]
    inherited = []
    for it in oi["inherited"]:
        item = _art_item(it["artefact"], editable=False, store=store, ledger=ledger)
        item["origin_id"] = it["origin_id"]
        item["origin_name"] = it["origin_name"]
        item["origin_path"] = f"via {it['origin_name']}"
        inherited.append(item)
    return {"own": own, "inherited": inherited}


def serialize_context(role_id: str, records, store, ledger=None) -> dict:
    """De volledige rol-context als structuur: overview (purpose/domains/accountabilities) +
    policies (eigen + geërfd; alle domein-gescopeerd en governance-eigendom) + notes + tools.
    Bron voor het /context-endpoint (json en markdown).

    `ledger` (de Kroniek) is optioneel: zónder ledger kunnen feiten die naar een Kroniek-record of
    certificaat wijzen niet gecontroleerd worden, en heten ze `ontbreekt` in plaats van dat ze er
    goed uitzien. Aanroepers die de Kroniek hebben, geven hem mee."""
    rec = records.get(role_id)
    if rec is None:
        return {}
    d = rec.definition
    role = {
        "id": role_id, "name": _name(rec), "purpose": getattr(d, "purpose", "") or "",
        "domains": list(getattr(d, "domains", None) or []),
        "accountabilities": list(getattr(d, "accountabilities", None) or []),
    }
    return {
        "role": role,
        "policies": _art_block(role_id, "policy", records, store),
        "notes": _art_block(role_id, "note", records, store, ledger),
        "tools": _art_block(role_id, "tool", records, store),
    }


# Grond-status → een teken dat in één blik het verschil laat zien tussen bewijs en herkomst.
# Zelfde vocabulaire als op het scherm; een AI-vervuller leest hetzelfde als de mens.
_GROND_TEKEN = {"gegrond": "✓", "ongecontroleerd": "◌", "vervallen": "⌛",
                "ontbreekt": "✗", "ongegrond": "—"}


def _feit_regels(a: dict) -> list[str]:
    """De feiten van een pagina als ingesprongen regels, elk met zijn grond. Een feit zonder bewijs
    zegt dat ook: wie hieruit citeert moet kunnen zien wat hij citeert."""
    regels = []
    for f in a.get("feiten") or []:
        teken = _GROND_TEKEN.get(f.get("grond") or "", "—")
        grond = f.get("grond_label") or f.get("grond") or ""
        detail = f" ({f['grond_detail']})" if f.get("grond_detail") else ""
        bron = f" <{f['bron']}>" if f.get("bron") else ""
        regels.append(f"  - {teken} {f.get('tekst') or ''} — {grond}{detail}{bron}")
    return regels


def _md_section(block: dict, *, tool: bool = False) -> list[str]:
    """Markdown voor 'Van deze rol' + 'Geldend hier (geërfd)' van één artefact-soort."""
    def line(a: dict, inherited: bool) -> list[str]:
        pagina = a.get("kind") == "note"
        if tool and a.get("url"):
            extra = f" — {a['url']}"
        elif a.get("body") and not pagina:
            extra = f" — {a['body']}"
        else:
            extra = ""
        # Ook een pagina (note) draagt zijn id: daarmee kan een AI-vervuller ernaar verwijzen
        # ([[NOTE-…]]) in plaats van de tekst over te schrijven.
        prefix = f"`{a['id']}` " if a.get("kind") in ("policy", "note") else ""
        tag = f" _({a['origin_path']})_" if inherited else ""
        regels = [f"- {prefix}**{a.get('title') or a['id']}**{extra}{tag}"]
        if pagina and a.get("body"):
            # De body van een pagina is een DOCUMENT (met eigen koppen en lijstjes). Inline achter
            # een streepje zou die koppen in de structuur van dit document laten vallen — dan
            # concurreert '## Gebruikt in' met '## Notes'. Als blok eronder blijft beide leesbaar.
            regels += [f"  > {r}" for r in str(a["body"]).splitlines()]
        return regels + _feit_regels(a)

    out = ["### Van deze rol"]
    eigen = [r for a in block["own"] for r in line(a, False)]
    out += eigen or ["- —"]
    out.append("### Geldend hier (geërfd)")
    geerfd = [r for a in block["inherited"] for r in line(a, True)]
    out += geerfd or ["- —"]
    return out


def render_context_markdown(ctx: dict) -> str:
    """Systeemprompt-bron voor AI-vervullers (Wendy Words): de vier blokken als geldige markdown."""
    if not ctx:
        return "# Onbekende rol\n"
    role = ctx["role"]
    L = [f"# Rol-context: {role['name']}", "", "## Overzicht",
         f"**Purpose:** {role['purpose']}",
         f"**Domeinen:** {', '.join(role['domains']) or '—'}",
         "**Accountabilities:**"]
    L += [f"- {a}" for a in role["accountabilities"]] or ["- —"]
    L += ["", "## Policies", "_Alle policies zijn governance-eigendom (domein-voorwaarden): "
          "volg ze, stel wijzigingen alleen voor via de domein-eigenaar._"]
    L += _md_section(ctx["policies"])
    L += ["", "## Notes (wiki-pagina's)",
          "_Elke note is een pagina: verwijs ernaar met [[titel]] of [[id]] in plaats van de tekst "
          "over te schrijven. Feiten staan eronder met hun grond — ✓ bewijs, ◌ herkomst maar niet "
          "gecontroleerd, ⌛ vervallen, ✗ grond niet gevonden, — geen bron._"]
    L += _md_section(ctx["notes"])
    L += ["", "## Tools"]
    L += _md_section(ctx["tools"], tool=True)
    L.append("")
    return "\n".join(L) + "\n"


def read_changelog(data_dir: str) -> list[dict]:
    """Lees de append-only artefact-changelog (`data/artefact_changelog.jsonl`) als lijst dicts.
    Corrupte regels worden overgeslagen (fail-open per regel). Bron voor de seen-markering."""
    path = os.path.join(data_dir, "artefact_changelog.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def own_and_inherited(role_id: str, kind: str, records, store) -> dict:
    """Eigen + geërfde artefacten van één soort voor een rol/cirkel.

    Retour: {"own": [Attachment, ...], "inherited": [{"artefact", "origin_id", "origin_name"}, ...]}.
    'own' = actieve artefacten op de rol zelf. 'inherited' = actieve, inherit=True artefacten van
    elke voorouder langs de breadcrumb (wortel eerst), getagd met de herkomst-rol.
    """
    own = store.list(role_id, kind)  # list() laat archief al weg
    chain = org.breadcrumb(records.all(), role_id)  # [wortel, ..., role_id]
    inherited: list[dict] = []
    for anc_id in chain[:-1]:  # alle voorouders (niet de rol zelf)
        rec = records.get(anc_id)
        origin_name = _name(rec)
        for a in store.list(anc_id, kind):
            if a.inherit:
                inherited.append({"artefact": a, "origin_id": anc_id, "origin_name": origin_name})
    return {"own": own, "inherited": inherited}
