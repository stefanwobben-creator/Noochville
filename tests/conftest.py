"""Gedeelde fixtures voor de NoochVillage test-suite."""
from __future__ import annotations
import os
import re
import pytest
from nooch_village.governance import Records
from nooch_village.models import Record, RoleDefinition, RecordType


@pytest.fixture(autouse=True)
def _isolate_village_data(monkeypatch):
    """Geen test schrijft ooit in de échte data/. Wijs BASE_DIR naar een eigen tmp-map (verse
    data), met de echte config gesymlinkt zodat settings/strategy blijven laden. Eigen tmp-map
    (niet de test-tmp_path) om botsing met tests te vermijden. Voorkomt dat een test die een
    volledige Village() bouwt de productie-inbox/records vervuilt ('nonexistent_test_rol')."""
    import tempfile
    import shutil
    import nooch_village.village as village
    real_cfg = os.path.join(village.BASE_DIR, "config")
    base = tempfile.mkdtemp(prefix="nv_test_base_")
    os.makedirs(os.path.join(base, "data"), exist_ok=True)
    if os.path.isdir(real_cfg):
        try:
            os.symlink(real_cfg, os.path.join(base, "config"))
        except OSError:
            shutil.copytree(real_cfg, os.path.join(base, "config"))
    monkeypatch.setattr(village, "BASE_DIR", base)
    yield
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_llm_usage(monkeypatch):
    """Het usage-log ook los van de échte data/ trekken.

    `llm_usage._PATH` is een module-singleton die alleen Village() zet (village.py:94). Zonder
    Village valt hij terug op het RELATIEVE 'data/llm_usage.jsonl' (llm_usage.py:34) — dus op de
    productiemap, want dat pad hangt aan de CWD en niet aan de BASE_DIR-isolatie hierboven. Elke
    test die reason() liet slagen schreef zo synthetische tredes ('gemini:x', 'mistral:m1',
    'openrouter:meta/llama') in het echte log; die tellen daarna mee als ongeschatte calls in de
    CO2-KPI en als onbekende prijs in llm_keuze.verbruik. Eigen tmp-map (niet tmp_path) om te
    voorkomen dat tests die op tmp_path-inhoud asserten hier last van krijgen."""
    import tempfile
    import shutil
    from nooch_village import llm_usage
    d = tempfile.mkdtemp(prefix="nv_test_usage_")
    monkeypatch.setattr(llm_usage, "_PATH", os.path.join(d, "llm_usage.jsonl"))
    yield
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_llm_throttle():
    """Tests mogen nooit écht wachten op de LLM-rate-limiter. Zet 'm op 'geen limiet'
    (de throttle-logica zelf wordt los getest in test_llm_throttle met een nep-klok)."""
    import nooch_village.llm as llm
    saved = llm.LIMITER
    llm.LIMITER = llm.RateLimiter(0)
    llm.reset_cooldowns()       # geen cooldown-lek tussen tests (de ladder slaat treden over)
    yield
    llm.LIMITER = saved
    llm.reset_cooldowns()


@pytest.fixture(autouse=True)
def _isolate_llm_keys(monkeypatch):
    """Test-only: verwijder echte LLM-provider-keys uit os.environ vóór elke test.

    config.load_context() doet os.environ.setdefault(...) uit .env (config.py:38) — dat lekt de
    echte keys process-globaal en blijft plakken tussen tests. No-key/heuristiek-tests falen dan
    order-afhankelijk: de ladder valt door naar een provider die de test zelf niet delenv't (bijv.
    Mistral) en geeft een echt antwoord. Deze fixture raakt PRODUCTIE NIET aan (load_context blijft
    ongewijzigd); ze schoont enkel de test-env, zodat de suite deterministisch is ongeacht een
    lokale/CI-.env."""
    for _k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(_k, raising=False)
    # EN NIEMAND ZET ZE TERUG (opruimlijst punt 8, 13 oktober 2026). `cockpit2._claims_scan` roept
    # bij elke aanroep `cockpit2._load_env()` aan, en die las de `.env` van de repo in os.environ —
    # midden in de test, ná het wissen hierboven. Zo belde `test_claims_v2::test_scan_van_tekst`
    # lokaal echt Gemini (in CI is er geen `.env`). In tests leest niets de `.env`; productie
    # verandert niet.
    from nooch_village import cockpit2 as _c2
    monkeypatch.setattr(_c2, "_load_env", lambda: None)


#: Het vaste publieke adres waar de nep-resolver elke gewone hostnaam heen stuurt (example.com).
#: Publiek, dus de SSRF-poort laat hem door — precies wat een echte publieke host zou doen.
NEP_PUBLIEK_IP = "93.184.215.14"


@pytest.fixture(autouse=True)
def _geen_echte_dns(monkeypatch):
    """Geen test zoekt ooit echt een hostnaam op (opruimlijst punt 7, 13 oktober 2026).

    `safe_fetch.controleer_url` toetst elke URL met `socket.getaddrinfo` — óók als de test het
    ophalen zelf nabootst met `_fetch`. Bij een DNS-hapering op de machine of in CI vielen daardoor
    36 claims-tests tegelijk om. Deze resolver is vast en netwerkloos:
      - een IP-adres gaat door naar de echte functie (die doet voor een letterlijk adres geen DNS);
      - `localhost` → 127.0.0.1, zodat de poort hem blijft weigeren;
      - `.invalid`, `.test`, `.example` (RFC 2606) bestaan nooit → `gaierror`;
      - elke andere naam → één vast publiek adres (`NEP_PUBLIEK_IP`).
    Een test die zelf `socket.getaddrinfo` patcht, overschrijft dit gewoon (monkeypatch stapelt).

    EN GEEN VERBINDING NAAR BUITEN. Een verbinding met `NEP_PUBLIEK_IP` wordt meteen geweigerd. Bij
    het invoeren hiervan bleek `test_claims_v2::test_scan_van_tekst` lokaal écht Gemini aan te
    roepen: `load_context` zet de sleutels uit `.env` terug nadat `_isolate_llm_keys` ze wiste. Met
    alleen een nep-adres hing die verbinding een minuut; nu faalt hij direct, zoals zonder sleutel."""
    import ipaddress
    import socket
    echt = socket.getaddrinfo

    def nep(host, port, family=0, type=0, proto=0, flags=0):
        naam = host.decode() if isinstance(host, bytes) else (host or "")
        try:
            ipaddress.ip_address(naam.strip("[]"))
            return echt(host, port, family, type, proto, flags)
        except ValueError:
            pass
        if naam.lower().rstrip(".") == "localhost":
            return echt("127.0.0.1", port, family, type, proto, flags)
        if naam.lower().rstrip(".").rsplit(".", 1)[-1] in ("invalid", "test", "example"):
            raise socket.gaierror(socket.EAI_NONAME, "nep-resolver: bestaat niet")
        return echt(NEP_PUBLIEK_IP, port, family, type, proto, flags)

    monkeypatch.setattr(socket, "getaddrinfo", nep)

    echt_connect, echt_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def _naar_buiten(adres) -> bool:
        return isinstance(adres, tuple) and adres and adres[0] == NEP_PUBLIEK_IP

    def connect(self, adres):
        if _naar_buiten(adres):
            raise ConnectionRefusedError("tests gaan niet het netwerk op (conftest._geen_echte_dns)")
        return echt_connect(self, adres)

    def connect_ex(self, adres):
        if _naar_buiten(adres):
            import errno
            return errno.ECONNREFUSED
        return echt_connect_ex(self, adres)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


@pytest.fixture
def records(tmp_path):
    """Lege Records backed by een tijdelijk bestand."""
    return Records(str(tmp_path / "governance.json"))


@pytest.fixture
def records_with_root(records):
    """Records met een wortelcirkel (noochville) als baseline voor gate-tests."""
    root = Record(
        id="noochville",
        type=RecordType.CIRCLE,
        parent=None,
        definition=RoleDefinition(
            purpose=(
                "Nooch.earth is het duurzaamste schoenenmerk ter wereld. "
                "Kernwaarden: geen plastic, geen leer, in Europa geproduceerd."
            ),
            policies=["geen plastic", "geen leer", "alleen nooch.earth"],
        ),
        source="seed",
    )
    records.put(root)
    return records


# ── JS lezen zonder de uitleg (26 september 2026) ────────────────────────────
#: Vijf toetsbestanden lazen `nooch.js` met hun eigen kopie van deze regex, en die kopie had een
#: fout die ze alle vijf deelden: `//` werd overal als commentaar gelezen, óók in `"https://"` en
#: aan het eind van een regex-literal (`/^https?:\/\//i`). Wat er dan overbleef was afgeknot, en
#: een assertie op zo'n stuk meet iets anders dan er staat — één toets sloeg daardoor rood uit op
#: code die wél klopte, en de andere vier hadden om dezelfde reden groen kunnen blijven op code
#: die niet klopte.
#:
#: DE UITZONDERING IS ÉÉN LOOKBEHIND: een `//` dat volgt op `:` (een url) of op `\` of `/` (het
#: einde van een regex) is geen commentaar. Geen JS-parser, wel genoeg voor dit bestand.
_JS_UITLEG = re.compile(r"(?<![:\\/])//[^\n]*|/\*.*?\*/", re.S)


def js_zonder_uitleg(bron: str) -> str:
    """`nooch.js` zonder commentaar, zodat een assertie de CODE meet en niet de uitleg erboven."""
    return _JS_UITLEG.sub("", bron)


def py_zonder_uitleg(bron: str) -> str:
    """Python-broncode zonder `#`-commentaar. Nodig zodra een toets een NAAM verbiedt in een stuk
    code: de uitleg erboven noemt die naam juist vaak, om te vertellen waar hij heen is. Zelfde
    reden als `js_zonder_uitleg` hierboven — een toets op de vorm van code hoort de code te lezen,
    niet het verhaal eromheen.

    Ruw maar voldoende: een `#` binnen een string blijft staan als commentaar-start. Dat is hier
    veilig, want deze helper wordt gebruikt om AFWEZIGHEID te toetsen, en te veel wegstrepen kan
    zo'n toets alleen strenger maken, nooit losser."""
    import re as _re
    return "\n".join(_re.sub(r"#.*$", "", regel) for regel in bron.splitlines())


#: De grens tussen de twee helften van `static/nooch.css`, sinds ze op 28 september 2026 zijn
#: samengevoegd. Alles ná deze regel is het designsysteem (voorheen `nooch-ui.css`).
DS_MARKERING = "/* ═══ Nooch UI v1 — samengevoegd"


def _css_pad():
    import pathlib as _pl
    return _pl.Path(__file__).resolve().parents[1] / "nooch_village" / "static" / "nooch.css"


def designsysteem_css() -> str:
    """Alleen de designsysteem-helft van nooch.css.

    WAAROM DIT BESTAAT. Een reeks toetsen meet eigenschappen van HET DESIGNSYSTEEM — "geen ronde
    hoeken", "koppen in hoofdletters", "elke regel draagt zijn scope". Die vragen gaan over de
    NIEUWE laag, niet over de oudere componentlaag eronder, die precies het tegenovergestelde doet
    (ronde hoeken, kleine kapitalen). Zolang de twee in aparte bestanden stonden viel dat samen met
    "het bestand"; nu is het een sectie, en dan moet de toets zeggen welke helft hij bedoelt."""
    tekst = _css_pad().read_text(encoding="utf-8")
    assert DS_MARKERING in tekst, "de designsysteem-helft is niet te vinden in nooch.css"
    return tekst[tekst.index(DS_MARKERING):]


def basis_css() -> str:
    """De componentlaag: alles VÓÓR de designsysteem-helft."""
    tekst = _css_pad().read_text(encoding="utf-8")
    return tekst[:tekst.index(DS_MARKERING)]
