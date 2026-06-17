"""Controleert dat Village noochie_weighed_in observeert — verwijderen van de
subscribe-regel in village.py maakt deze test rood."""
from __future__ import annotations
from nooch_village.village import Village


def test_village_observeert_noochie_weighed_in():
    v = Village(heartbeat_seconds=0)
    handlers = v.bus._subs.get("noochie_weighed_in", [])
    assert v._observe in handlers, (
        "Village moet noochie_weighed_in via _observe observeren — "
        "voeg toe: self.bus.subscribe('noochie_weighed_in', self._observe)"
    )
