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
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.skills_impl.library_skills import LibraryLookupSkill, KeywordReviewSkill, LibraryListSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill
from nooch_village.skills_impl.gsc_report import GscReportSkill
from nooch_village.skills_impl.ngram import NgramCultureSkill
from nooch_village.skills_impl.openlibrary_search_inside import OpenlibrarySearchInsideSkill
from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
from nooch_village.skills_impl.openalex import OpenalexSkill
from nooch_village.skills_impl.epo_patents import EpoPatentsSkill
from nooch_village.skills_impl.google_patents import GooglePatentsSkill
from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill
from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill
from nooch_village.skills_impl.alphavantage import AlphaVantageIndexSkill
from nooch_village.skills_impl.trends_categorie import TrendsCategorieSkill
from nooch_village.skills_impl.gdelt_tone import GdeltToneSkill
from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill
from nooch_village.skills_impl.competitor_discover import CompetitorDiscoverSkill
from nooch_village.skills_impl.community_listening import CommunityListeningSkill
from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
from nooch_village.skills_impl.verband_voorstel import VerbandVoorstelSkill
from nooch_village.skills_impl.onderzoeksvraag import OnderzoeksvraagSkill
from nooch_village.skills_impl.content_schrijven import ContentSchrijvenSkill
from nooch_village.skills_impl.content_check import ContentCheckSkill
from nooch_village.skills_impl.curate import CurateSkill
from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill


def build_skill_registry() -> SkillRegistry:
    """Bouw een verse SkillRegistry met alle geregistreerde skills. De daemon gebruikt dit bij opstart;
    het cockpit-proces gebruikt het (via `shared_registry`) alleen voor match-metadata."""
    reg = SkillRegistry()
    for skill in (
        SiteHealthSkill(), PlausibleSkill(), TrendsSkill(), SerpapiTrendsSkill(),
        FieldNoteSkill(), LibraryLookupSkill(), LibraryListSkill(), KeywordReviewSkill(),
        GscPerformanceSkill(), GscReportSkill(),
        NgramCultureSkill(),
        OpenlibrarySearchInsideSkill(),
        SemanticScholarSkill(),
        OpenalexSkill(),
        EpoPatentsSkill(),
        GooglePatentsSkill(),          # alternatief pad voor de skill-ladder als EPO OPS faalt
        BulletinSchrijvenSkill(),
        KeywordsEverywhereSkill(),
        AlphaVantageIndexSkill(),
        TrendsCategorieSkill(), GdeltToneSkill(),
        CompetitorNewsSkill(),
        CompetitorDiscoverSkill(),
        CommunityListeningSkill(),
        LinkbuildingTargetsSkill(),
        VerbandVoorstelSkill(),
        OnderzoeksvraagSkill(),
        ContentSchrijvenSkill(),
        ContentCheckSkill(),
        CurateSkill(),
        VoorstelSchrijvenSkill(),
        ShopifySalesSkill(),
    ):
        reg.register(skill)
    return reg


@lru_cache(maxsize=1)
def shared_registry() -> SkillRegistry:
    """Gecachete registry voor het cockpit-proces: één keer bouwen, hergebruiken over match-calls.
    Alleen voor metadata — zie de module-grens hierboven; nooit `run()` vanuit het cockpit."""
    return build_skill_registry()
