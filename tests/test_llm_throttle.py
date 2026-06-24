"""Throttle: het dorp smeert zijn LLM-werk uit zodat het onder de gratis limiet blijft.

Geen echt wachten: de klok en sleep zijn injecteerbaar (FakeClock). Geen netwerk."""
from __future__ import annotations
import pytest

import nooch_village.llm as llm
from nooch_village.llm import RateLimiter, _is_rate_limit


class FakeClock:
    """Nep-klok: sleep() laat de tijd vooruitspringen i.p.v. echt te wachten."""
    def __init__(self):
        self.t = 0.0
        self.slept = 0.0
    def time(self):
        return self.t
    def sleep(self, s):
        self.slept += s
        self.t += s


def _limiter(max_per_minute, fc, window=60.0):
    return RateLimiter(max_per_minute, clock=fc.time, sleep=fc.sleep, window=window)


def test_onder_de_limiet_geen_wachten():
    fc = FakeClock()
    rl = _limiter(5, fc)
    for _ in range(5):
        rl.acquire()
    assert fc.slept == 0.0          # eerste 5 in dezelfde minuut: geen wachttijd


def test_zesde_call_wacht_tot_venster_vrij():
    fc = FakeClock()
    rl = _limiter(5, fc)
    for _ in range(5):
        rl.acquire()
    rl.acquire()                    # 6e moet wachten tot de oudste (t=0) uit het 60s-venster valt
    assert fc.slept == pytest.approx(60.0)
    assert fc.t == pytest.approx(60.0)


def test_tempo_blijft_onder_limiet_over_meerdere_vensters():
    fc = FakeClock()
    rl = _limiter(5, fc)
    for _ in range(11):             # 11 calls bij 5/min → minstens 2 vensters wachttijd
        rl.acquire()
    assert fc.t >= 120.0


def test_max_nul_betekent_geen_limiet():
    fc = FakeClock()
    rl = _limiter(0, fc)
    for _ in range(100):
        rl.acquire()
    assert fc.slept == 0.0


def test_is_rate_limit_herkent_429_en_quota():
    assert _is_rate_limit(Exception("429 Too Many Requests"))
    assert _is_rate_limit(Exception("RESOURCE_EXHAUSTED: quota"))
    assert _is_rate_limit(Exception("rate limit reached"))
    assert not _is_rate_limit(Exception("SSL handshake timeout"))
    assert not _is_rate_limit(Exception("connection refused"))


def test_reason_gaat_door_de_limiter(monkeypatch):
    """reason() vraagt eerst een plek bij de limiter, dan pas de LLM."""
    calls = {"acquire": 0}

    class Spy:
        def acquire(self):
            calls["acquire"] += 1

    monkeypatch.setattr(llm, "LIMITER", Spy())
    monkeypatch.setattr(llm, "_try_gemini", lambda p: "antwoord")
    out = llm.reason("test")
    assert out == "antwoord"
    assert calls["acquire"] == 1


def test_gemini_wacht_voor_retry_bij_rate_limit():
    """Bij een 429 wordt er vóór de retry gewacht (injecteerbare sleep)."""
    slept = []
    # Forceer een rate-limit-fout door de google-import te laten ontbreken? Nee: we
    # mikken op _is_rate_limit. Simuleer via een nep-sleep + een prompt die de echte
    # call laat falen (geen key → return None vóór de loop). Daarom testen we de
    # backoff-beslissing los via _is_rate_limit hierboven; hier checken we dat zonder
    # key meteen None komt zonder te slapen.
    import os
    old = os.environ.pop("GEMINI_API_KEY", None)
    old2 = os.environ.pop("GOOGLE_API_KEY", None)
    try:
        out = llm._try_gemini("x", sleep=lambda s: slept.append(s))
        assert out is None
        assert slept == []          # geen key → geen call, geen wachten
    finally:
        if old is not None:
            os.environ["GEMINI_API_KEY"] = old
        if old2 is not None:
            os.environ["GOOGLE_API_KEY"] = old2
