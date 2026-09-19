"""Gedeelde SkillRegistry-factory: één authoritatieve skill-lijst voor zowel de daemon (Village) als
het cockpit-proces (skill-match).

HARDE GRENS — het cockpit-proces gebruikt deze registry UITSLUITEND voor skill-METADATA (description +
input_schema + required_payload) om een checklist-item tegen een rol-DNA te matchen. Het cockpit mag
NOOIT `skill.run()` aanroepen: uitvoering van skills blijft exclusief bij de daemon
(`Inhabitant._execute_checklist`). Het construeren van de skill-objecten hier is goedkoop en doet geen
I/O; I/O gebeurt pas in `run()`, en dat pad loopt alleen in de daemon.
"""
from __future__ import annotations

from functools import lru_cache

from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.site_health import SiteHealthSkill
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.serpapi_trends import SerpapiTrendsSkill
from nooch_village.skills_impl.library_skills import LibraryLookupSkill, KeywordReviewSkill, LibraryListSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill
from nooch_village.skills_impl.gsc_report import GscReportSkill
from nooch_village.skills_impl.openalex import OpenalexSkill
from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
from nooch_village.skills_impl.epo_patents import EpoPatentsSkill
from nooch_village.skills_impl.google_patents import GooglePatentsSkill
from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill
from nooch_village.skills_impl.alphavantage import AlphaVantageIndexSkill
from nooch_village.skills_impl.trends_categorie import TrendsCategorieSkill
from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
from nooch_village.skills_impl.claim_evidence import ClaimEvidenceSkill
from nooch_village.skills_impl.cert_evidence import CertEvidenceSkill
from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
from nooch_village.skills_impl.claims_site_scan import ClaimsSiteScanSkill
from nooch_village.materiaal_memo import MateriaalKwartaalSkill, MateriaalShortlistSkill
from nooch_village.skills_impl.regulation_watch import RegulationWatchSkill
from nooch_village.skills_impl.weten_we_dit_al import WetenWeDitAlSkill
from nooch_village.skills_impl.escaleer import EscaleerSkill
from nooch_village.skills_impl.tegenspraak import TegenspraakSkill
from nooch_village.skills_impl.projectverzoek import ProjectverzoekSkill
from nooch_village.skills_impl.co2_village import Co2VillageSource
from nooch_village.skills_impl.haal_pagina import HaalPaginaSkill
from nooch_village.skills_impl.web_zoek import WebZoekSkill
from nooch_village.skills_impl.mobiel_audit import MobielAuditSkill

def build_skill_registry() -> SkillRegistry:
    """Bouw een verse SkillRegistry met alle geregistreerde skills. De daemon gebruikt dit bij opstart;
    het cockpit-proces gebruikt het (via `shared_registry`) alleen voor match-metadata."""
    reg = SkillRegistry()
    for skill in (
        SiteHealthSkill(), HaalPaginaSkill(), PlausibleSkill(), TrendsSkill(), SerpapiTrendsSkill(),
        LibraryLookupSkill(), LibraryListSkill(), KeywordReviewSkill(),
        GscPerformanceSkill(), GscReportSkill(),
        OpenalexSkill(),
        SemanticScholarSkill(),   # tweede trede van de bewijs-ladder onder openalex_evidence
        EpoPatentsSkill(),
        GooglePatentsSkill(),          # alternatief pad voor de skill-ladder als EPO OPS faalt
        KeywordsEverywhereSkill(),
        AlphaVantageIndexSkill(),
        TrendsCategorieSkill(),        LinkbuildingTargetsSkill(),
        VoorstelSchrijvenSkill(),
        ShopifySalesSkill(),
        CertEvidenceSkill(), ClaimEvidenceSkill(), ClaimsCheckSkill(), ClaimsSiteScanSkill(), RegulationWatchSkill(),
        # De radar-uitgang (#436/#437). Zonder registratie is een grant een lege
        # verwijzing: de rol draagt dan een capability-naam die nergens op wijst.
        MateriaalKwartaalSkill(), MateriaalShortlistSkill(),
        WetenWeDitAlSkill(),
        EscaleerSkill(),
        TegenspraakSkill(),
        ProjectverzoekSkill(),
        # Sid's eerste stap: bepaal HOE je zoekt voordat je zoekt. Zijn resultaat laat
        # `_herplan_na_strategie` de volgende uitvoerlijst schrijven.
        # De bron die het dorp niet had: vrij zoeken op het open web. SerpAPI zat er drie keer
        # in, elke keer vastgeklonken aan één doel; dit is de losse toegang.
        WebZoekSkill(),
        # De stap die een mens ná het zoeken doet: een naam opzoeken, de site lezen en zeggen of
        # hij past, met een citaat (scope 51). Ronde twee van een onderzoek plant hem per lead.
        MobielAuditSkill(),           # Lighthouse op mobiel via PageSpeed Insights; ook meetbron (wekelijks)
        Co2VillageSource(),
    ):
        reg.register(skill)
    return reg

@lru_cache(maxsize=1)
def shared_registry() -> SkillRegistry:
    """Gecachete registry voor het cockpit-proces: één keer bouwen, hergebruiken over match-calls.
    Alleen voor metadata — zie de module-grens hierboven; nooit `run()` vanuit het cockpit."""
    return build_skill_registry()
