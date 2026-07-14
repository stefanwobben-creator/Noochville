from __future__ import annotations
from abc import ABC, abstractmethod
import logging

log = logging.getLogger("village.skill")


def resolve_source_scope(payload_scope: str, config_scope: str, *, veld: str, config_key: str) -> tuple:
    """Gedeeld scope-contract voor externe-bron-skills (community_listening, competitor_discover, …).

    De SCOPE van een bron (wat zoek ik: een onderwerp, een termen-set, merken) is projectkennis, geen code.
    Hij komt uit het PROJECT (payload, door de planner afgeleid uit het doel) of uit de CONFIG (een staande
    monitor), maar NOOIT uit een in de code gebakken default — want een code-default gokt een categorie en
    dat is precies de klasse bug die dit contract sluit (de vegan-in-plaats-van-barefoot-fout).

    Voorrang: payload > config > zichtbaar weigeren. Geeft (scope, "") bij succes, of ("", reden) als er
    geen scope is; de skill hoort dan fail-closed te weigeren i.p.v. iets te gokken. Zo krijgt élke bron
    zijn scope op dezelfde, gegronde manier, en valt de volgende bron er vanzelf goed uit.

    NB: skills met een RIJKERE scope (bv. community_listening's monitor-set vs discovery-queries) hoeven
    deze helper niet letterlijk te gebruiken — ze volgen het contract via hun eigen validate_payload/
    required_payload. Het contract is het PRINCIPE (project/config, nooit code-default, fail-visible); deze
    helper is de gemaksvorm voor het meest voorkomende geval: één vrije scope met config-fallback."""
    p = (payload_scope or "").strip()
    if p:
        return p, ""
    c = (config_scope or "").strip()
    if c:
        return c, ""
    return "", (f"geen {veld}: geef het mee via het project of zet '{config_key}' in de config — "
                f"de skill gokt bewust geen scope (fail-closed)")


class Skill(ABC):
    """Een echte vaardigheid. Inwoners krijgen skills geinjecteerd."""
    name: str = "abstract"
    needs_secret: bool = False
    description: str = ""

    required_env: tuple[str, ...] = ()
    """Env-/settings-sleutels die deze skill HARD nodig heeft. Ontbreekt er één, dan faalt
    de skill closed (geen verzonnen output). Het opstart-rapport leest dit zelfbeschrijvend
    uit, zodat je bij een run in één oogopslag ziet welke skills 'scherp staan'."""

    optional_env: tuple[str, ...] = ()
    """Env-/settings-sleutels die de skill VERBETEREN maar niet vereist zijn (hogere limiet,
    courtesy-mailto). Afwezig = de skill werkt nog, in beperkte modus."""

    cost: str | None = None
    """Puls-veiligheid en gemeten externe call-kost die de (toekomstige) puls-gate bewaakt.
    Verplicht voor elke concrete subklasse; None is niet toegestaan in productie.
      "free"         — veilig herhaald in de puls (lokale I/O, eigen API, geen quota)
      "rate_limited" — mag in de puls met backoff (onofficieel endpoint, throttling)
      "credits"      — gemeten/ongebonden kost, niet in de continue puls
    NB: kleine begrensde LLM-tokenkost wordt hier bewust niet gevlagd; daarom blijven
    field_note en bulletin_schrijven "free".
    """

    side_effect_free: bool = True
    """True = run() leest alleen en muteert geen state, intern noch extern.
    Schrijft de skill een bestand/record of doet hij een externe actie, dan False.
    """

    input_schema: str = ""
    """Beschrijving van de verwachte payload-sleutels (proza of pseudo-schema).
    Zie run()-docstring voor details.
    """

    output_schema: str = ""
    """Beschrijving van de teruggegeven dict-sleutels (proza of pseudo-schema).
    Zie run()-docstring voor details.
    """

    required_payload: tuple[str, ...] = ()
    """De payload-sleutels die VERPLICHT (aanwezig én niet-leeg) moeten zijn om zinvol te draaien —
    machine-leesbaar, zodat het uitvoer-primitief een onvolledige checklist-payload fail-fast herkent bij
    het opstellen (i.p.v. de skill leeg te laten draaien). Optionele velden (limit, days, country) staan
    hier NIET in. Leeg = geen validatie mogelijk (fail-soft: item blijft uitvoerbaar)."""

    def validate_payload(self, payload: dict, context) -> list:
        """Grondings-poort op de payload (opt-in). Geeft REDENEN terug waarom deze payload niet kan
        draaien, náást het loutere aanwezig-zijn van verplichte velden (dat dekt required_payload al):
        typisch een VERWIJZEND veld dat naar iets niet-bestaands wijst (een door de planner verzonnen id).
        Default: geen extra check. Skills met verwijzingen overschrijven dit, zodat een spook-verwijzing
        niet als 'uitvoerbaar' de plan-fase in glipt en pas live sterft. Fail-soft: bij twijfel [] terug."""
        return []

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """Optioneel: map het skill-RESULTAAT naar EvidenceLedger-records (De Kroniek — de brug naar fase 2).
        Default: niets. De meeste skills leveren geen bewijs. Een grounding-/verificatie-skill overschrijft
        dit zodat de dispatch-laag zijn bevestigd/leeg/fout in het register schrijft. De skill blijft
        side-effect-free: hij BESCHRIJFT alleen de records ({role_id, skill, query, source, status,
        result_ref}); de inhabitant schrijft ze. Onbekende/lege uitkomst → []. Zo voedt élke bewijs-skill
        de Kroniek zonder dat de uitvoer-keten per skill hoeft te weten hoe zijn output eruitziet."""
        return []

    def available_metrics(self, context=None) -> list[str]:
        """De ruwe veldsleutels die deze skill oplevert (voor het catalogus-koppelscherm). Default
        leeg: een skill die géén meetbare velden declareert, levert niets te koppelen. Geen API-call.
        `context` is optioneel voor bronnen met DYNAMISCHE velden (bv. Trends-termen uit de config);
        vaste-veld-bronnen negeren 'm. Backward-compatible: bestaande callers geven niets door."""
        return []

    @abstractmethod
    def run(self, payload: dict, context) -> dict:
        ...


class DataSourceSkill(Skill):
    """Een databron die de dag-puls generiek kan uitlezen: hij declareert zijn velden
    (`available_metrics`) én levert per veld een dagwaarde (`daily_values`). Zo hoeft de puls niets
    per bron/veld te hardcoden — hij itereert over de actieve DataSourceSkills en schrijft elk veld
    weg onder `<SOURCE>_<field>_day`.

    `SOURCE` = de catalogus-bron-id (= observation-`bron`), bewust los van `name` (de skill-id).
    """
    SOURCE: str = ""
    DEFAULT_FREQUENCY: str = "daily"

    kind: str = "flux"
    """'flux' = de dagwaarde is de gebeurtenis van die dag (bezoekers, orders) → de tegel toont de
    waarde zelf. 'snapshot' = de dagwaarde is een cumulatieve STAND (citaties, publicaties) → de tegel
    toont standaard de genormaliseerde delta (bijv. +80/week), niet de oplopende stand. Declaratief:
    tegel-render, vers-signaal en delta-afleiding sturen hierop, i.p.v. het uit daily_values te raden."""

    lag_days: int = 0
    """Hoeveel dagen deze bron structureel achterloopt. De verwachte periode schuift zoveel terug:
    de collector haalt de meest recente BESCHIKBARE dag op (today − 1 − lag_days), niet blind gisteren.
    Zo vult een bron met vertraging (GSC ~2-3 dagen) wél, en 'geen datapunt voor gisteren' is normaal —
    geen teken van 'dood'. De 7-daagse vers-drempel vangt de lag op (een lag-dag telt nog als recent)."""

    def frequency(self, field: str) -> str:
        """Hoe vaak dit veld hoort te vullen ('daily' voor de huidige drie bronnen). De puls checkt
        per veld of er al een datapunt is voor de verwachte periode (idempotent + zelfherstellend),
        niet 'dagen sinds laatste ophaal'. Trage bronnen (Semantic Scholar) overschrijven dit
        later per veld; curator-override + koppeling aan de vers-drempel zijn een latere fase."""
        return self.DEFAULT_FREQUENCY

    def is_configured(self, context) -> bool:
        """Creds aanwezig? Generiek via `required_env` — geen per-bron hardcoding. Actief-maar-niet-
        geconfigureerd is een eigen zichtbare status (los van 'dood')."""
        import os
        return all((context.settings.get(k) or os.getenv(k)) for k in self.required_env)

    @abstractmethod
    def daily_values(self, context, datum: str) -> dict:
        """{field: value|None} voor de gedeclareerde velden op `datum` (fail-closed per veld: None bij
        ontbrekend/fout, geen mock). Sleutels ⊆ available_metrics()."""
        ...

    def observation_meta(self, context, datum: str, field: str) -> dict:
        """Bron-specifieke herkomst-metadata voor de observatie van dit veld op deze dag (source_version,
        endpoint, timeframe/termenset/geo, …). De collector hangt dit aan elke geschreven observatie.
        Default leeg: bestaande bronnen (Plausible/Shopify) veranderen niet."""
        return {}

    def expected_datum(self, today):
        """Optionele datum-override voor de due-check ÉN het datumlabel van de observatie. Default None →
        de collector gebruikt `_expected_period` (de pulsperiode). Een bron die een specifieke meetperiode
        beschrijft (bijv. Trends: de laatste COMPLETE week, niet de lopende partiële week) geeft hier de
        datum die de observatie moet dragen — essentieel voor latere lead/lag-analyse. Deterministisch uit
        `today`, zodat de due-check en de write dezelfde sleutel gebruiken (idempotent, geen dag-refetch)."""
        return None

    def collect_series(self, context, today, obs):
        """Optioneel EIGEN collectie-pad. Default None → de collector gebruikt de generieke totaal-/
        dimensie-paden. Een bron met afwijkende semantiek (custom metric-naam, label, meta of telvenster —
        bijv. OpenAlex' 90/30-flow-venster) schrijft z'n reeksen hier ZELF via `obs.record_daily`
        (idempotent) en geeft een lijst geschreven `(bron, veld, datum)`-tuples terug. Een niet-None
        return (óók een lege lijst) betekent 'ik bezit deze bron' → de collector slaat de generieke paden
        én de lege-velden-guard over."""
        return None

    def collect_extra_series(self, context, today, obs):
        """Optionele ADDITIEVE reeksen NAAST de generieke totaal-/dimensie-paden (die blijven draaien —
        anders dan collect_series die ze vervangt). Voor een dimensie met eigen selectie-logica die niet in
        het fixed-list-dimensiepad past (bijv. Plausible page_path: een pagina komt in de meetset zodra hij
        één dag ≥3 bezoeken haalt, daarna de volledige dagreeks). Schrijft zelf via `obs.record_daily`
        (idempotent), geeft geschreven `(bron, veld, datum)`-tuples terug. Default: niets."""
        return []


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        log.info("skill geregistreerd: %s", skill.name)

    def get(self, name: str):
        return self._skills.get(name)

    def names(self) -> list[str]:
        return list(self._skills)

    def all(self) -> list[Skill]:
        return list(self._skills.values())
