"""Auth — sessie- en wachtwoordbeheer voor cockpit2.

people.json is de enige bron van waarheid. UserStore leest het bestand en bouwt
een email-index op records met zowel een email- als een password_hash-veld.
"""
from __future__ import annotations
import hashlib, html, json, logging, os, re, secrets, time, urllib.parse

from nooch_village.util import JsonStore
import bcrypt

SESSION_COOKIE = "nv_session"
SESSION_TTL    = 7 * 24 * 3600   # 1 week

_TEMP_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # geen 0/O/l/1 verwarring


class UserStore:
    """Leest people.json en biedt email-gebaseerde authenticatie.

    Werkt op elk JSON-bestand waarvan de waarden een 'email'- én
    'password_hash'-veld hebben — ongeacht de sleutelvorm (person_id of username).
    """

    def __init__(self, path: str):
        self._path = path

    def _by_email(self) -> dict:
        """Lees people.json vers in: nieuw toegevoegde mensen kunnen meteen inloggen,
        zonder herstart."""
        raw: dict = json.load(open(self._path, encoding="utf-8")) if os.path.exists(self._path) else {}
        return {
            rec["email"].lower(): rec
            for rec in raw.values()
            if rec.get("email") and rec.get("password_hash")
        }

    def verify_by_email(self, email: str, password: str) -> bool:
        u = self._by_email().get(email.lower())
        if not u:
            # GEEN SNELLE "NEE" (17 oktober 2026). Zonder bcrypt antwoordt een onbekend adres in
            # microseconden en een bekend adres in ~0,2 s: de responstijd verraadt dan wie een account
            # heeft. Dezelfde vergelijking tegen een vaste dummy-hash maakt beide even traag.
            bcrypt.checkpw(password.encode(), _dummy_hash())
            return False
        return bcrypt.checkpw(password.encode(), u["password_hash"].encode())

    def get_by_email(self, email: str) -> dict | None:
        return self._by_email().get(email.lower())

    def empty(self) -> bool:
        return not bool(self._by_email())


def _lees_in(store) -> None:
    """Lees de store van schijf in zijn state-attribuut, fail-open naar leeg.

    LET OP EEN VALKUIL IN DE BASIS: `JsonStore._load()` ZET het state-attribuut en geeft `None`
    terug. `self._items = self._load()` zet je state dus op None. Bij SessionStore maskeerde
    `_prune()` dat toevallig — die is een schrijfmethode en herlaadt onder het slot — maar de
    csrf-store las daardoor altijd leeg, en dat kostte precies de winst die deze PR maakt.

    FAIL-OPEN, MAAR LUID. `read_json` gooit bewust op een corrupt bestand: stil leeg opstarten en
    dan overschrijven is hoe je data verliest (zie util.read_json). Die regel geldt voor RECORDS.
    Sessies en het csrf-token zijn een CACHE: raak je ze kwijt, dan logt iedereen opnieuw in — de
    situatie van vóór deze wijziging. Een cockpit die niet start is strikt erger.

    Dus: leeg beginnen mag, stil beginnen niet. De waarschuwing is het verschil tussen fail-open en
    wegkijken."""
    try:
        store._load()
    except (OSError, ValueError, RuntimeError) as e:
        logging.getLogger("village.auth").warning(
            "%s onleesbaar (%s) — leeg gestart; iedereen logt opnieuw in", store.path, e)
        setattr(store, store._STATE, store._default())
        # HET KAPOTTE BESTAND MOET WEG, niet alleen genegeerd. Elke schrijfmethode herlaadt onder
        # het slot (`synchronized`), dus laat je het staan, dan knalt niet de start maar de eerste
        # schrijf — en dan kan niemand meer inloggen. Erger dan wat we repareerden.
        try:
            store._save()
        except OSError:
            pass


class _CsrfStore(JsonStore):
    """Piepklein, maar wél via de bewaakte schrijfroute.

    Mijn eerste versie riep `atomic_write_json` rechtstreeks aan en werd terecht geweigerd door
    `test_geen_ongelockte_write`: er is ÉÉN bewaakte schrijfroute per store (CONVENTIES, #419).
    Een bestand van één sleutel is geen uitzondering op die regel — juist de kleine schrijfacties
    glippen anders langs het slot."""

    _WRITE_METHODS = ("zet",)

    def __init__(self, path: str):
        self.path = path
        self._items = {}
        _lees_in(self)                               # `_load()` ZET het attribuut, hij geeft niets terug

    def lees(self) -> str:
        token = self._items.get("csrf") or ""
        return token if isinstance(token, str) and len(token) >= 32 else ""

    def zet(self, token: str) -> None:
        self._items["csrf"] = token
        self._save()


def load_or_create_csrf(path: str) -> str:
    """Het CSRF-token van de server, bewaard zodat het een herstart overleeft.

    ZONDER DIT IS DE PERSISTENTE SESSIE HALF WERK. Sessie én CSRF-token leefden allebei in het
    procesgeheugen. Maak je alleen de sessie persistent, dan blijft een tab die openstond tijdens
    een deploy 403 krijgen — nu niet meer met "Not logged in" maar met "CSRF token invalid". Voor
    de mens is dat hetzelfde: toevoegen werkt niet.

    AFWEGING, bewust genomen: dit is een SERVER-BREED token, zoals het al was — het wordt nu alleen
    niet meer bij elke herstart vervangen. Dat is geen verzwakking van het ontwerp maar een langere
    levensduur van hetzelfde ontwerp. De sterkere vorm is een token per sessie (HMAC over het
    sessietoken), en die is een aparte stap: hij raakt elke csrf-vergelijking in cockpit2.

    Bestandsrechten 0600, zelfde route als de sessies. Onleesbaar of leeg → een vers token, en dan
    is het gedrag exact zoals vóór deze wijziging."""
    store = _CsrfStore(path)
    bestaand = store.lees()
    if bestaand:
        return bestaand
    token = secrets.token_urlsafe(32)
    try:
        store.zet(token)
    except OSError:
        pass                                         # niet kunnen bewaren mag de start niet breken
    return token


class SessionStore(JsonStore):
    """Sessies die een HERSTART OVERLEVEN.

    WAAROM DIT PERSISTENT IS (2 sep 2026): sessies én het CSRF-token leefden in het procesgeheugen.
    Vijf deploys op één werkdag herstartten de cockpit, en elke openstaande tab kreeg daarna 403 op
    zijn POST — zonder dat iets dat zei. De drawer is inmiddels luid (#425), maar dat TOONT het
    probleem alleen. Dit neemt het weg.

    Drie dingen die niet mogen verslonzen:

    1. **Op schijf staat alleen een HASH van het token**, nooit het token zelf. Wie het bestand
       leest kan er geen sessie mee kapen. SHA-256 en niet bcrypt: dit draait bij élk request, en
       het token is 32 bytes uit `secrets` — er valt niets te raden, dus rekt vertragen heeft geen
       doel.
    2. **`time.time()`, niet `time.monotonic()`.** Monotonic telt vanaf het opstarten van de
       machine en heeft geen betekenis in een volgend proces. Persistent maken met monotonic zou
       elke sessie ná een herstart als verlopen (of juist eeuwig geldig) lezen — precies de bug die
       we oplossen, maar dan stiller.
    3. **Bestandsrechten 0600.** Die komen uit `atomic_write_json` (mkstemp maakt 0600 aan en
       `os.replace` behoudt de mode), dus ze zijn geen losse chmod die iemand kan vergeten — maar
       ze worden wél getest, want "het gebeurt vanzelf" is geen garantie.

    `path=None` houdt de store in het geheugen. Dat is geen tweede implementatie maar dezelfde
    code met een lege schrijfroute: tests en de niet-persistente modus delen alle logica."""

    _WRITE_METHODS = ("create", "delete", "invalidate_user", "_prune")
    _STATE = "_sessions"

    def __init__(self, path: str | None = None, ttl: int = SESSION_TTL):
        self.path = path or ""
        self._ttl = ttl
        self._sessions: dict[str, dict] = {}
        if self.path:
            _lees_in(self)                           # zie `_lees_in`: `_load()` retourneert None
            self._prune()

    # ── schijf ────────────────────────────────────────────────────────────────────────────────
    def _load(self) -> None:
        """In geheugen-modus is er niets om te lezen — en herlezen zou WISSEN.

        `synchronized` roept `_load()` aan onder het slot vóór elke schrijfmethode, zodat twee
        processen elkaars schrijf niet overschrijven. Zonder pad leest die read een niet-bestaand
        bestand en zet de staat op leeg. `create` overleefde dat toevallig (hij voegt daarna toe),
        `invalidate_user` niet: die vond niets meer om in te trekken."""
        if not self.path:
            return
        super()._load()

    def _save(self) -> None:
        if not self.path:
            return                                   # geheugen-modus: geen schrijfroute
        super()._save()

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256((token or "").encode()).hexdigest()

    def _prune(self) -> None:
        """Verlopen sessies weg. Ook de enige plek waar het bestand krimpt."""
        nu = time.time()
        weg = [h for h, e in self._sessions.items() if float(e.get("expires", 0)) <= nu]
        for h in weg:
            del self._sessions[h]
        if weg:
            self._save()

    # ── de bestaande interface, ongewijzigd voor elke aanroeper ───────────────────────────────
    def create(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[self._hash(token)] = {"username": username,
                                             "expires": time.time() + self._ttl}
        self._save()
        return token                                 # het token zelf verlaat deze methode en
                                                     # belandt in een cookie; op schijf staat de hash

    def get_username(self, token: str) -> str | None:
        if not token:
            return None
        h = self._hash(token)
        entry = self._sessions.get(h)
        if not entry:
            return None
        if time.time() > float(entry.get("expires", 0)):
            self._sessions.pop(h, None)
            self._save()
            return None
        return entry.get("username")

    def delete(self, token: str) -> None:
        if self._sessions.pop(self._hash(token), None) is not None:
            self._save()

    def invalidate_user(self, username: str, keep_token: str | None = None) -> int:
        """Verbreek alle sessies van een gebruiker (bijv. na een wachtwoordwijziging), behalve
        `keep_token` (de eigen, net-vernieuwde sessie). Geeft het aantal verbroken sessies terug.

        Was een NO-OP zolang de store in het geheugen leefde; nu de sessies persistent zijn kan hij
        echt werken — en moet hij dat ook, want een sessie die een herstart overleeft, overleeft
        anders ook een wachtwoordwijziging."""
        houden = self._hash(keep_token) if keep_token else None
        weg = [h for h, e in self._sessions.items()
               if e.get("username") == username and h != houden]
        for h in weg:
            del self._sessions[h]
        if weg:
            self._save()
        return len(weg)



_DUMMY_HASH: bytes | None = None


def _dummy_hash() -> bytes:
    """Een vaste bcrypt-hash met dezelfde kosten als echte wachtwoorden (`hash_password`), één keer
    per proces gemaakt. Het wachtwoord erachter is willekeurig en wordt nergens bewaard."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt(12))
    return _DUMMY_HASH


#: Een anker dat over de login heen mag: `#vraag-plastic`, `#feit-1a2b`, `#m-<id>`, `#kop=…`.
_ANKER_RE = re.compile(r"^#[A-Za-z0-9_.:=%-]{1,200}$")


def veilig_pad(waarde) -> str:
    """Een terugkeer-adres na inloggen (`next`), of "/" (17 oktober 2026, besluit Stefan).

    ALLEEN EEN RELATIEF PAD DAT MET ÉÉN `/` BEGINT. Alles wat de browser als een ander domein of
    als code kan lezen valt weg: `//host` en `/\\host` (protocol-relatief), elk schema
    (`https:`, `javascript:`), een backslash, witruimte en stuurtekens. Ook GECODEERD: `/%2f%2fhost`
    of `%2F%2Fhost` wordt herhaald gedecodeerd en dan opnieuw getoetst — een filter dat alleen de
    ruwe tekst bekijkt, laat precies die varianten door. Ongeldig is nooit een fout, maar "/"."""
    p = waarde if isinstance(waarde, str) else ""
    if not p or len(p) > 2000:
        return "/"
    vormen, d = [p], p
    for _ in range(5):                                   # tot hij niet meer verandert
        nd = urllib.parse.unquote(d)
        if nd == d:
            break
        vormen.append(nd)
        d = nd
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in p):  # ruwe witruimte/stuurtekens
        return "/"
    for v in vormen:
        # Elke vorm moet met precies één `/` beginnen: dat sluit ook elk schema uit. Een gecodeerde
        # spatie (`%20` in een zoekopdracht) is wél goed; stuurtekens (tab, regeleinde) niet.
        if (not v.startswith("/") or v.startswith("//") or "\\" in v
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in v)):
            return "/"
    return p


def veilig_anker(waarde) -> str:
    """Een `#anker` dat na het inloggen terug mag, of "". Alleen letters, cijfers en `_.:=%-`."""
    a = waarde if isinstance(waarde, str) else ""
    return a if _ANKER_RE.match(a) else ""


def doorstuur_pagina(pad) -> str:
    """De tussenpagina `/l?p=<pad>` voor links in een mail (17 oktober 2026, besluit Stefan).

    WAAROM. De sessiecookie is `SameSite=Strict`: een klik vanuit Gmail-web is een navigatie van een
    andere site, en dan stuurt de browser de cookie niet mee — wie al ingelogd is ziet toch het
    inlogscherm. Deze pagina zelf heeft geen cookie nodig. Het `location.replace` dat hij doet start
    op Village, is dus same-site, en draagt de cookie wél. Het `#anker` van de mail-link reist mee
    (`p + location.hash`). De cookie blijft Strict; dat is precies de bedoeling.

    WAT HIJ NIET DOET: iets tonen, iets wijzigen, of ergens anders heen sturen dan een relatief pad
    binnen Village — dezelfde toets als `next` na het inloggen (`veilig_pad`); ongeldig → "/".
    Zonder JavaScript een gewone link (`noscript`)."""
    doel = veilig_pad(pad)
    # json.dumps geeft een JS-string; `<` als \u003c zodat `</script>` in een pad niets kan sluiten.
    js = json.dumps(doel).replace("<", "\\u003c")
    attr = html.escape(doel, quote=True)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="referrer" content="no-referrer">
<title>NoochVille</title>
<script>location.replace({js} + location.hash);</script>
</head><body>
<noscript><p><a href="{attr}">Continue to NoochVille</a></p></noscript>
</body></html>"""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def generate_temp_password(length: int = 10) -> str:
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))


def get_session_token(headers) -> str | None:
    for part in headers.get("Cookie", "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == SESSION_COOKIE:
            return value.strip() or None
    return None


def set_cookie(token: str, max_age: int = SESSION_TTL) -> str:
    return f"{SESSION_COOKIE}={token}; Max-Age={max_age}; Path=/; HttpOnly; Secure; SameSite=Strict"


def clear_cookie() -> str:
    return f"{SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Strict"


def login_page(next_url: str = "/", error: str = "", anker: str = "") -> str:
    err = f'<p style="color:#c0392b;margin:0 0 1rem">{error}</p>' if error else ""
    nxt = html.escape(veilig_pad(next_url), quote=True)
    # HET ANKER REIST MEE (17 oktober 2026). `#feit-…` bereikt de server nooit, dus de pagina zelf
    # zet `location.hash` in een verborgen veld; de server plakt hem (getoetst) achter `next`. Na een
    # fout wachtwoord staat het anker niet meer in de adresbalk (de POST ging naar /login), dus dan
    # rendert de server het veld al gevuld.
    ank = html.escape(veilig_anker(anker), quote=True)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in — NoochVille</title>
<style>
:root{{--bg:#f8f6f2;--card:#fff;--border:#d4cfc8;--accent:#2d6a4f;--text:#1a1a1a}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);display:flex;align-items:center;justify-content:center;
     min-height:100vh;font-family:system-ui,sans-serif;color:var(--text)}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;
      padding:2.5rem;width:100%;max-width:360px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
h1{{font-size:1.25rem;margin-bottom:1.75rem}}
label{{display:block;font-size:.85rem;font-weight:600;margin-bottom:.35rem}}
input[type=email],input[type=password]{{width:100%;padding:.6rem .75rem;
  border:1px solid var(--border);border-radius:4px;font-size:1rem;
  margin-bottom:1.25rem;background:#fafaf8}}
input:focus{{outline:2px solid var(--accent);border-color:transparent}}
button{{width:100%;padding:.7rem;background:var(--accent);color:#fff;border:none;
       border-radius:4px;font-size:1rem;cursor:pointer;font-weight:600}}
button:hover{{opacity:.9}}
</style></head><body>
<div class="card">
  <h1>NoochVille — sign in</h1>
  {err}
  <form method="post" action="/login">
    <input type="hidden" name="next" value="{nxt}">
    <input type="hidden" name="anker" id="anker" value="{ank}">
    <label for="u">Email address</label>
    <input type="email" id="u" name="email" autocomplete="email" autofocus required>
    <label for="p">Password</label>
    <input type="password" id="p" name="password" autocomplete="current-password" required>
    <button type="submit">Sign in</button>
  </form>
</div>
<script>(function(){{var a=document.getElementById('anker');if(a&&location.hash&&!a.value)a.value=location.hash;}})();</script>
</body></html>"""


def password_change_page(next_url: str = "/", error: str = "", forced: bool = False) -> str:
    """Self-service wachtwoord-wijzigen (dezelfde auth-interstitial-stijl als login_page). `forced=True`
    bij een verplichte eerste-login-wijziging (temp-wachtwoord)."""
    err = f'<p style="color:#c0392b;margin:0 0 1rem">{error}</p>' if error else ""
    intro = ('<p style="color:#5a5a5a;font-size:.9rem;margin:-.75rem 0 1.5rem">You are using a temporary '
             'password. Choose your own password now to continue.</p>') if forced else ""
    nxt = html.escape(veilig_pad(next_url), quote=True)
    # Bij een VERPLICHTE wijziging geen 'huidig wachtwoord'-veld: de gebruiker is net via login
    # geauthenticeerd (die verifieerde het temp al), en het veld lokt browser-autofill van het OUDE
    # wachtwoord uit → een onmogelijk-op-te-lossen loop. Voor een vrijwillige wijziging blijft het staan.
    current_field = "" if forced else (
        '<label for="c">Current password</label>'
        '<input type="password" id="c" name="current" autocomplete="current-password" autofocus required>')
    new_focus = " autofocus" if forced else ""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Change password — NoochVille</title>
<style>
:root{{--bg:#f8f6f2;--card:#fff;--border:#d4cfc8;--accent:#2d6a4f;--text:#1a1a1a}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);display:flex;align-items:center;justify-content:center;
     min-height:100vh;font-family:system-ui,sans-serif;color:var(--text)}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;
      padding:2.5rem;width:100%;max-width:360px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
h1{{font-size:1.25rem;margin-bottom:1.75rem}}
label{{display:block;font-size:.85rem;font-weight:600;margin-bottom:.35rem}}
input[type=password]{{width:100%;padding:.6rem .75rem;
  border:1px solid var(--border);border-radius:4px;font-size:1rem;
  margin-bottom:1.25rem;background:#fafaf8}}
input:focus{{outline:2px solid var(--accent);border-color:transparent}}
button{{width:100%;padding:.7rem;background:var(--accent);color:#fff;border:none;
       border-radius:4px;font-size:1rem;cursor:pointer;font-weight:600}}
button:hover{{opacity:.9}}
</style></head><body>
<div class="card">
  <h1>Change password</h1>
  {intro}{err}
  <form method="post" action="/wachtwoord">
    <input type="hidden" name="next" value="{nxt}">
    {current_field}
    <label for="n">New password</label>
    <input type="password" id="n" name="new" autocomplete="new-password"{new_focus} required>
    <label for="n2">New password (confirm)</label>
    <input type="password" id="n2" name="confirm" autocomplete="new-password" required>
    <button type="submit">Save</button>
  </form>
</div></body></html>"""
