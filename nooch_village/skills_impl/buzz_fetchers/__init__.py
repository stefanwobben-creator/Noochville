"""Fetcher-registry voor community_listening: platform → fetcher.

Nieuwe bron toevoegen = een BuzzFetcher-subklasse + één entry hieronder. De skill
(CommunityListeningSkill) dispatcht per actief platform van de zoek-set naar de juiste fetcher;
store, dedup, 6u-cache en wall-post blijven bron-onafhankelijk.
"""
from __future__ import annotations

from nooch_village.skills_impl.buzz_fetchers.base import BuzzFetcher
from nooch_village.skills_impl.buzz_fetchers.reddit import RedditFetcher
from nooch_village.skills_impl.buzz_fetchers.youtube import YouTubeFetcher
from nooch_village.skills_impl.buzz_fetchers.bluesky import BlueskyFetcher

FETCHERS: dict[str, BuzzFetcher] = {
    f.platform: f for f in (RedditFetcher(), YouTubeFetcher(), BlueskyFetcher())
}


def get_fetcher(platform: str) -> BuzzFetcher | None:
    return FETCHERS.get(platform)
