"""De onderzoekspas: een rol onderzoekt zelf en legt een gegrond voorstel voor.

Vervángt de menu-naar-founder-route voor claim-items. Dat is geen parallel kanaal: waar de founder
eerst een lijstje opties kreeg en zelf het werk moest doen, krijgt hij nu één concreet voorstel met
het bewijs eronder — of, als het bewijs het niet draagt, de eerlijke bevinding zonder aanbeveling.

**Orkestratie, geen nieuwe capaciteit.** Alles hieronder bestaat al:

  onderzoek   `claims_check` + `claim_evidence` uit de eigen skill-lijst, plus `kennis_voor()`
              (die draait `weten_we_dit_al` al als pre-flight — apart aanroepen zou dubbel zijn)
  vastleggen  het `evidence_ledger` (De Kroniek), via de bestaande `evidence_records`-haak
  synthese    één LLM-call op de hoog-inzet-ladder, in de vaste vorm van `voorstel_vorm`
  poort       `missie_critic.beoordeel` — dezelfde vier assen als op het einddocument
  beslissing  de Founder Flow (`voorstel_oordeel`), niet een nieuwe inbox

**Rolgrens.** Compliance stelt de gegronde substantie en richting voor; de copywriter schrijft de
copy. Compliance schrijft geen eindtekst — bij goedkeuring gaat het via `projectverzoek` naar de
copywriter. Dat is dezelfde cross-rol-route die al draait, geen nieuwe.

**De gegrond-as is hard.** Zakt hij, dan degradeert het voorstel (`voorstel_vorm.degradeer`) naar
bevindingen zonder aanbeveling. Nooit een verzonnen aanbeveling — dat is de kernles van deze week.
"""
from __future__ import annotations

import json
import logging
import time

from nooch_village import voorstel_vorm as vv

log = logging.getLogger("village.onderzoekspas")

BESTAND = "voorstellen.jsonl"

# De skills die de onderzoekspas mag aanroepen. Bewust een expliciete lijst en geen "alles wat de rol
# heeft": een onderzoekspas hoort te lezen en te toetsen, niet te schrijven of te escaleren. Een rol
# die er een mist slaat die stap over — fail-soft, met een regel in het log (geen stille cap).
ONDERZOEK_SKILLS = ("claims_check", "claim_evidence")


def _payload_voor(inhabitant, skill: str, vraag: str) -> tuple[dict | None, str]:
    """Leid de payload AF uit het `input_schema` van de skill. Geen geraden dict.

    De eerste versie gaf een vaste `{text, term, claim, query}` mee en hoopte dat het paste. Bij
    `claim_evidence` paste het niet ("geef brands (niet-leeg) en een claim op"), dus draaide juist
    de bron níet die de concrete actie had kunnen leveren — en het voorstel rustte op één bron.
    Precies de zonde die `_herstel_payloads` repareert, dus hergebruiken we die machinerie hier
    meteen in plaats van hem een tweede keer te maken."""
    from nooch_village.skills import ontbrekende_velden
    obj = inhabitant.registry.get(skill) if inhabitant.registry else None
    schema = (getattr(obj, "input_schema", "") or "").strip() if obj else ""
    # Via de gedeelde lezer, niet de rauwe tuple: sinds de disjunctie kan `required_payload` een
    # tuple-element bevatten (("text","terms")), en `_payload_opnieuw` joint deze lijst tot tekst.
    # De rauwe vorm doorgeven gaf "expected str instance, tuple found" — en dus draaide claims_check
    # opnieuw niet. Precies de fout die de gedeelde lezer moest voorkomen, door hem niet te gebruiken.
    verplicht = ontbrekende_velden(getattr(obj, "required_payload", ()) if obj else (), {})
    try:
        payload = inhabitant._payload_opnieuw(skill, vraag, schema, verplicht, {})
    except Exception as e:                                   # noqa: BLE001
        return None, f"'{skill}': payload afleiden faalde ({e})"
    if not isinstance(payload, dict) or not payload:
        return None, f"'{skill}': geen payload af te leiden uit de vraag"
    mist = inhabitant._missing_required(skill, payload)
    issues = inhabitant._payload_issues(skill, payload)
    if mist or issues:
        return None, f"'{skill}': payload haalt de poort niet ({'; '.join(mist + issues)[:120]})"
    return payload, ""


def _skill_uitvoer(inhabitant, skill: str, payload: dict) -> tuple[dict | None, str]:
    """Draai één onderzoeks-skill. (resultaat, reden-als-overgeslagen)."""
    if skill not in (inhabitant.dna.skills or []):
        return None, f"'{skill}' zit niet in de skill-lijst van {inhabitant.id}"
    obj = inhabitant.registry.get(skill) if inhabitant.registry else None
    if obj is None:
        return None, f"'{skill}' staat niet in de registry"
    try:
        return obj.run(payload, inhabitant.context), ""
    except Exception as e:                                   # noqa: BLE001 — één dode bron ≠ dode pas
        log.warning("onderzoekspas: %s faalde: %s", skill, e)
        return None, f"'{skill}' faalde: {e}"


def onderzoek(inhabitant, vraag: str, *, term: str = "") -> dict:
    """Draai de onderzoekspas. Geeft {bewijs, overgeslagen, kennis}.

    `bewijs` = [{bron, citaat, kroniek}] — het materiaal waarop het voorstel mag steunen.
    `overgeslagen` = wat er NIET gedraaid heeft en waarom. Geen stille cap: wat wegvalt staat erbij,
    en het reist mee naar het voorstel zodat de founder ziet waarop het níet rust."""
    uit = {"bewijs": [], "overgeslagen": [], "kennis": ""}
    from nooch_village.citeerbaar import velden_van

    for skill in ONDERZOEK_SKILLS:
        payload, waarom = _payload_voor(inhabitant, skill, vraag)
        if payload is None:
            uit["overgeslagen"].append(waarom)
            continue
        res, waarom = _skill_uitvoer(inhabitant, skill, payload)
        if res is None:
            uit["overgeslagen"].append(waarom)
            continue
        if not isinstance(res, dict) or res.get("error"):
            uit["overgeslagen"].append(f"'{skill}': {str((res or {}).get('error'))[:120]}")
            continue
        if res.get("no_data"):
            # Legitiem leeg is een ANTWOORD, geen gat — zelfde regel als bij de deliverables.
            uit["bewijs"].append({"bron": skill, "citaat": f"geen resultaat: "
                                                           f"{str(res.get('reason') or res.get('reden') or '')[:200]}",
                                  "kroniek": ""})
            continue
        kroniek_id = _naar_kroniek(inhabitant, skill, vraag, res)
        for _s, veld, waarde in velden_van(skill, res)[:6]:
            uit["bewijs"].append({"bron": skill, "citaat": f"{veld} = {waarde}", "kroniek": kroniek_id})

    try:
        from nooch_village.kennis_context import kennis_blok, kennis_voor
        uit["kennis"] = kennis_blok(kennis_voor(inhabitant.context.data_dir, vraag))
    except Exception as e:                                   # noqa: BLE001
        uit["overgeslagen"].append(f"kennislaag: {e}")
    if uit["overgeslagen"]:
        log.info("onderzoekspas '%s': %d bron(nen) overgeslagen — %s",
                 vraag[:40], len(uit["overgeslagen"]), "; ".join(uit["overgeslagen"])[:200])
    return uit


def _naar_kroniek(inhabitant, skill: str, vraag: str, resultaat: dict) -> str:
    """Leg de skill-run vast in De Kroniek en geef het record-id terug.

    Via de bestaande `evidence_records`-haak van de skill als die er is; anders een regel met de
    drie eersteklas statussen. Het id maakt elk citaat in het voorstel herleidbaar."""
    try:
        import os
        from nooch_village.evidence_ledger import EvidenceLedger
        led = EvidenceLedger(os.path.join(inhabitant.context.data_dir, "evidence_ledger.jsonl"))
        obj = inhabitant.registry.get(skill)
        maker = getattr(obj, "evidence_records", None)
        records = list(maker(resultaat, role_id=inhabitant.id) or []) if callable(maker) else []
        if not records:
            records = [{"role_id": inhabitant.id, "skill": skill, "query": vraag[:200],
                        "source": skill, "status": "bevestigd", "result_ref": "", "meta": {}}]
        eerste = ""
        for r in records:
            rec = led.record(**r) if hasattr(led, "record") else None
            eerste = eerste or str((rec or {}).get("id") or "")
        return eerste
    except Exception as e:                                   # noqa: BLE001 — vastleggen mag nooit blokkeren
        log.warning("onderzoekspas: Kroniek-vastlegging faalde: %s", e)
        return ""


def synthetiseer(inhabitant, vraag: str, onderzoek_uit: dict, *, doel: str = "") -> dict | None:
    """Zet het bewijs om in een voorstel in de vaste vorm. None = geen bruikbaar antwoord."""
    from nooch_village.llm import reason
    from nooch_village.llm_keuze import ladder_voor
    bewijs = "\n".join(f"- {b['bron']}: {b['citaat']}" for b in (onderzoek_uit.get("bewijs") or []))
    weg = "; ".join(onderzoek_uit.get("overgeslagen") or [])
    prompt = (
        "Je bent compliance bij Nooch (duurzame veganistische schoenen). Je hebt onderzoek gedaan en "
        "legt de founder één CONCREET voorstel voor. Hij moet er in tien seconden op kunnen "
        "beslissen.\n\n"
        f"DE VRAAG: {vraag}\n"
        + (f"HET DOEL: {doel}\n" if doel else "")
        + f"\nBEWIJS DAT IK OPHAALDE (dit is alles wat je mag aanhalen):\n{bewijs or '(niets)'}\n"
        + (f"\nWAT NIET GEDRAAID HEEFT: {weg}\n" if weg else "")
        + (f"\nWAT HET DORP AL WEET:\n{onderzoek_uit.get('kennis')}\n"
           if onderzoek_uit.get("kennis") else "")
        + "\nJE ROLGRENS: jij stelt de gegronde SUBSTANTIE en RICHTING voor. Je schrijft GEEN "
          "eindcopy — dat doet de copywriter na goedkeuring. Beschrijf dus wát er moet veranderen "
          "en waarom, niet de definitieve zin.\n\n"
          "Vul deze vijf velden:\n"
          "- actie: één concrete stap, geformuleerd als AANBEVELING die op de founder wacht. Begin "
          "met 'Mijn voorstel: ' en beschrijf wat er moet gebeuren. Schrijf het NIET als een "
          "handeling die je al doet of gedaan hebt ('ik geef opdracht', 'ik heb vervangen') — dat "
          "is een bewering over de werkelijkheid die je niet kunt onderbouwen, en de critic keurt "
          "hem terecht af. Geen vraag, geen keuzemenu.\n"
          "- bewijs: laat leeg, die vul ik zelf met de bronnen hierboven.\n"
          "- risico: wat dit kost of kán misgaan. Kort, en in VOORWAARDELIJKE vorm ('als X, dan "
          "kan Y') — geen stellige uitspraak over hoe de wereld is. Een feit dat je voorstel "
          "DRAAGT hoort in de actie of in het bewijs, niet hier.\n"
          "- nodig_van_jou: LEEG LATEN tenzij je echt iets van de founder nodig hebt dat je zelf "
          "niet kunt halen. Dan specifiek: wélk gegeven, en waarom jij er niet bij kunt.\n"
          "- onzeker: wat je NIET hebt kunnen vaststellen, met wat het zou weerleggen. Negatieve "
          "vorm: dit veld zegt wat je niet weet, niet wat waar is.\n\n"
          "Verzin geen cijfer, status, percentage of wetsartikel dat niet in het bewijs staat. "
          "Heb je het specifieke niet, zeg dan wát je wél hebt.\n"
          "Schrijf de ACTIE en het BEWIJS, en leg niets uit, veronderstel niets en impliceer niets "
          "dat je niet uit een deliverable of de opdracht kunt gronden. Geen interpretatie van wat "
          "cijfers betekenen, geen oorzaak waarom een bron leeg bleef, geen zijstap naar een andere "
          "claim dan die in de opdracht staat. Bij twijfel: laat het weg. Leaner en volledig "
          "gegrond verslaat rijk en gedegradeerd.\n\n"
          "GROND VERSLAAT INDRUK. Reik niet naar een indrukwekkend alternatief dat het bewijs niet "
          "draagt. Weet je uit het bewijs dát een term vaag of onhoudbaar is, maar niet wélke "
          "concrete invulling erachter zit — bijvoorbeeld omdat dat interne kennis is die in geen "
          "enkele bron staat — stel dan het BESCHEIDEN voorstel voor dat wél gegrond is: de term "
          "schrappen, of de term laten staan totdat de founder je de concrete invulling geeft die "
          "jij dan verifieert. Een voorstel 'verwijder deze term, want hij is niet te onderbouwen' "
          "is een goed voorstel. Een voorstel dat een materiaal, proces of richting noemt die "
          "nergens in het bewijs staat, is dat niet — hoe redelijk het ook klinkt.\n"
          'Antwoord UITSLUITEND met JSON: {"actie":"...","risico":"...","nodig_van_jou":"","onzeker":"..."}')
    raw = reason(prompt, call_site="voorstel_synthese", ladder=ladder_voor("skill_voorstel"),
                 json_mode=True, max_tokens=1500)
    if not raw:
        return None
    s = str(raw)
    try:
        data = json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        log.warning("onderzoekspas: synthese gaf geen bruikbare JSON (%d tekens)", len(s))
        return None
    return {"soort": vv.SOORT_VOORSTEL,
            "actie": str(data.get("actie") or "").strip(),
            "bewijs": list(onderzoek_uit.get("bewijs") or []),
            "risico": str(data.get("risico") or "").strip(),
            "nodig_van_jou": str(data.get("nodig_van_jou") or "").strip(),
            "onzeker": str(data.get("onzeker") or "").strip(),
            "overgeslagen": list(onderzoek_uit.get("overgeslagen") or [])}


# Het doel waartegen de critic een VOORSTEL toetst. Niet het uitvoeringsdoel van het project.
#
# Gemeten op het debuut: `done_when` van 549f8e98404f is "de herformulering is live en door legal
# gezien", en de grond-as rekende het niet-bereikt-zijn daarvan aan als ongegronde bewering —
# "impliciete claim dat de herformulering al live staat". Voor een einddocument klopt die toets: dat
# hóórt het doel te halen. Voor een voorstel is het doel per definitie nog niet bereikt; dat is
# waarom het een voorstel is.
#
# Leegmaken is óók fout: dan slaagt de beantwoordt-as leeg (`_overlap` geeft 1.0 bij een lege
# done-when) en meet die niets meer. Dus een eigen doel dat wél toetsbaar is.
# Bewust in de woorden van de VASTE VORM. `_beantwoordt` meet woord-overlap, dus een doel dat
# abstract beschrijft wat een voorstel is ("onderbouwd", "welke wijziging") haalt die overlap nooit
# en laat de as op élk voorstel zakken — gemeten toen ik het eerst zo formuleerde. Met deze woorden
# toetst de as iets echts: zijn de velden van de vorm daadwerkelijk gevuld?
VOORSTEL_DOEL = ("een concreet voorstel voor deze claim, met bewijs, risico en wat nog onzeker is")

# Een voorstel is bondig — vijf velden, geen rapport. De einddocument-drempel van 400 tekens zou een
# goed voorstel op LENGTE laten zakken, nog vóór de grond-as draait. 150 vangt nog steeds het lege
# voorstel (een actiezin plus één bron haalt dat ruim) zonder bondigheid af te straffen.
MIN_VOORSTEL_CHARS = 150


def gegeven_van(project: dict) -> str:
    """De feiten die de OPDRACHT zelf vaststelt — toelaatbaar bewijs voor de grond-as.

    Een voorstel dat verwijst naar de pagina uit zijn eigen taak zakte hierop ("de onderbouwing
    noemt geen paginalocatie of FAQ") terwijl die URL letterlijk in de opdracht staat. De opdracht
    is een gegeven; hem uitsluiten is toetsen met te weinig materiaal.

    Strak begrensd: alleen wat de taak vaststelt, en geen enkele bewering die iemand daarover doet.
    De kader-tekst maakt dat onderscheid expliciet."""
    regels = []
    for veld, label in (("scope", "onderzochte claim/opdracht"), ("description", "toelichting"),
                        ("done_when", "gevraagde uitkomst"), ("goes_to", "gaat naar")):
        waarde = str((project or {}).get(veld) or "").strip()
        if waarde:
            regels.append(f"- {label}: {waarde[:300]}")
    for cl in ((project or {}).get("checklists") or []):
        for it in (cl.get("items") or []):
            tekst = str(it.get("text") or "").strip()
            if tekst:
                regels.append(f"- taak: {tekst[:200]}")
    return "\n".join(regels[:14])


def poort(voorstel: dict, *, project: dict, skill=None, context=None) -> tuple[dict, dict]:
    """De critic-poort. Geeft (voorstel-zoals-het-uitgaat, critic-oordeel).

    Zakt de gegrond-as, dan degradeert het voorstel — het gaat wél uit, maar als bevinding zonder
    aanbeveling. Zakken de goedkope assen, dan draait de dure toets niet, precies zoals op het
    einddocument."""
    from nooch_village import missie_critic as mc
    document = vv.render(voorstel)
    deliverables = [{"id": "", "skill": b.get("bron"), "summary": b.get("citaat")}
                    for b in (voorstel.get("bewijs") or [])]
    toets_project = dict(project or {})
    toets_project["done_when"] = VOORSTEL_DOEL
    toets_project.pop("dod_outcome", None)               # anders lekt het uitvoeringsdoel alsnog
    oordeel = mc.beoordeel(project=toets_project, document=document, deliverables=deliverables,
                           checklist=None, skill=skill, context=context,
                           min_chars=MIN_VOORSTEL_CHARS,
                           kader_extra=vv.KADER_VOORSTEL,
                           gegeven=gegeven_van(project))
    if oordeel["oordelen"].get("gegrond") is True:
        return voorstel, oordeel
    reden = next((r for r in (oordeel.get("redenen") or []) if r.startswith("gegrond")),
                 "de grondings-toets gaf geen groen licht")
    return vv.degradeer(voorstel, reden.replace("gegrond: ", "")), oordeel


def leg_vast(data_dir: str, *, project_id: str, rol: str, vraag: str,
             voorstel: dict, oordeel: dict) -> dict:
    """Bewaar het voorstel append-only, zodat /founder het kan tonen en de meting het kan tellen."""
    import os
    rij = {"id": f"{project_id}-{int(time.time())}", "project": project_id, "rol": rol,
           "vraag": str(vraag)[:300], "voorstel": voorstel,
           "critic": {"geslaagd": oordeel.get("geslaagd"), "oordelen": oordeel.get("oordelen"),
                      "redenen": (oordeel.get("redenen") or [])[:3]},
           "ts": time.time()}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, BESTAND), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rij, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("voorstel niet vastgelegd: %s", e)
    return rij


def alle(data_dir: str) -> list[dict]:
    import os
    pad = os.path.join(data_dir, BESTAND)
    uit = []
    try:
        with open(pad, encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if regel:
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue
    except FileNotFoundError:
        return []
    except OSError as e:
        log.warning("voorstellen onleesbaar: %s", e)
    return uit


def draai(inhabitant, project: dict, vraag: str, *, term: str = "") -> dict:
    """De volle pas voor één item: onderzoek → synthese → pre-check → critic → vastleggen."""
    pid = project.get("id", "")
    res = onderzoek(inhabitant, vraag, term=term)
    voorstel = synthetiseer(inhabitant, vraag, res, doel=str(project.get("done_when") or ""))
    if voorstel is None:
        log.warning("onderzoekspas '%s': geen synthese — niets naar de founder", pid)
        return {}
    ok, waarom = vv.keur(voorstel)
    if not ok:
        # Terug voor nog een pas is hier (nog) niet geautomatiseerd: één ronde, en dan eerlijk
        # melden dat het geen voorstel werd. Beter dan een menu doorlaten.
        log.info("onderzoekspas '%s': pre-check afgewezen (%s) — degradeert naar bevinding", pid, waarom)
        voorstel = vv.degradeer(voorstel, f"pre-check: {waarom}")
    uitgaand, oordeel = poort(voorstel, project=project, context=inhabitant.context)
    return leg_vast(inhabitant.context.data_dir, project_id=pid, rol=inhabitant.id,
                    vraag=vraag, voorstel=uitgaand, oordeel=oordeel)
