"""SSRF-guardrail en HTML→tekst. De guardrail is de reden dat deze module bestaat:
de cockpit staat in een datacenter en mag zijn interne bereik niet uitlenen aan een
gebruiker die een URL intypt."""
from __future__ import annotations

import pytest

from nooch_village import safe_fetch as sf


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8766",                       # de cockpit zelf
    "http://localhost/admin",
    "http://192.168.1.1/",
    "http://10.0.0.5/",
    "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data/",    # cloud-metadata: de klassieke SSRF-buit
    "http://[::1]/",
])
def test_prive_adressen_worden_geweigerd(url):
    with pytest.raises(sf.FetchGeweigerd):
        sf.controleer_url(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://nooch.earth/", "gopher://x/",
                                 "javascript:alert(1)", "", "   ", "http://"])
def test_alleen_http_en_https(url):
    with pytest.raises(sf.FetchGeweigerd):
        sf.controleer_url(url)


def test_publieke_url_mag():
    assert sf.controleer_url("https://nooch.earth/") == "https://nooch.earth/"


def test_onbekende_hostnaam_wordt_geweigerd():
    with pytest.raises(sf.FetchGeweigerd):
        sf.controleer_url("https://deze-host-bestaat-echt-niet-12345.invalid/")


def test_guardrail_geldt_ook_bij_geinjecteerde_fetch():
    """De injectie voor tests mag de poort niet omzeilen."""
    with pytest.raises(sf.FetchGeweigerd):
        sf.haal_tekst("http://127.0.0.1/", _fetch=lambda u: (200, "<html>x</html>"))


# ── HTML → tekst ────────────────────────────────────────────────────────────

_PAGINA = """<html><head><title>Zero Waste  Footwear &ndash; NOOCH</title>
<meta name="description" content="100% planet-safe &amp; plant-based">
<style>body{color:red}</style></head>
<body><script>var x = "duurzaam";</script>
<h1>Onze schoenen</h1><p>Biologisch afbreekbaar.</p></body></html>"""


def test_titel_meta_en_body_komen_mee():
    titel, tekst = sf.naar_tekst(_PAGINA)
    assert titel == "Zero Waste Footwear – NOOCH"        # entiteit + dubbele spatie opgeruimd
    assert "100% planet-safe & plant-based" in tekst      # meta-description telt mee
    assert "Biologisch afbreekbaar." in tekst
    assert tekst.startswith(titel)                        # titel eerst: claims staan vaak in de <title>


def test_script_en_style_tellen_niet_mee():
    """Anders zou een claim in JavaScript-code als paginatekst worden gescand."""
    _, tekst = sf.naar_tekst(_PAGINA)
    assert "duurzaam" not in tekst
    assert "color:red" not in tekst


def test_lege_pagina_valt_niet_om():
    assert sf.naar_tekst("") == ("", "")


def test_haal_tekst_met_injectie():
    uit = sf.haal_tekst("https://nooch.earth/", _fetch=lambda u: (200, _PAGINA))
    assert uit["status"] == 200
    assert uit["titel"].startswith("Zero Waste")
    assert "afbreekbaar" in uit["tekst"]


def test_http_fout_is_geen_lege_scan():
    """Fail-closed: een 404 mag nooit als 'geen claims gevonden' doorgaan."""
    with pytest.raises(sf.FetchMislukt):
        sf.haal_tekst("https://nooch.earth/", _fetch=lambda u: (404, "<html>weg</html>"))


def test_een_hostnaam_die_naar_een_intern_adres_resolvet_wordt_geweigerd(monkeypatch):
    """De poort kijkt naar het adres, niet naar de naam. De nep-resolver uit conftest stuurt elke
    naam naar een publiek adres; hier wijst één naam naar binnen, zoals bij DNS-rebinding."""
    import socket
    echt = socket.getaddrinfo
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda h, p, *a, **k: echt("10.0.0.7" if h == "intern.nooch.earth" else h, p, *a, **k))
    with pytest.raises(sf.FetchGeweigerd):
        sf.controleer_url("https://intern.nooch.earth/")


def test_de_suite_zoekt_niets_echt_op():
    """De autouse-resolver in conftest: een gewone naam krijgt het vaste nep-adres, zonder netwerk."""
    import socket
    from tests.conftest import NEP_PUBLIEK_IP
    assert socket.getaddrinfo("nooch.earth", 443)[0][4][0] == NEP_PUBLIEK_IP


def test_de_suite_gaat_niet_het_netwerk_op():
    """Een verbinding met het nep-adres wordt meteen geweigerd, in plaats van te hangen."""
    import socket
    import time
    t = time.monotonic()
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("nooch.earth", 443), timeout=30)
    assert time.monotonic() - t < 2


def test_een_claims_scan_in_een_test_zet_geen_llm_sleutels():
    """Opruimlijst punt 8: `_claims_scan` riep `_load_env()` aan, en die zette de `.env`-sleutels
    terug in os.environ nadat conftest ze had gewist. In tests is `_load_env` een no-op."""
    import os
    from nooch_village import cockpit2
    cockpit2._claims_scan({"tekst": ["zero waste en klimaatneutraal"]})
    # Alleen de NAMEN vergelijken: een assert op `os.environ` zelf zet bij falen alle waarden
    # (sleutels!) in de testuitvoer en het CI-log.
    gezet = [k for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY")
             if k in os.environ]
    assert gezet == []
