"""Auth — sessie- en wachtwoordbeheer voor cockpit2.

people.json is de enige bron van waarheid. UserStore leest het bestand en bouwt
een email-index op records met zowel een email- als een password_hash-veld.
"""
from __future__ import annotations
import json, os, secrets, time
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
            return False
        return bcrypt.checkpw(password.encode(), u["password_hash"].encode())

    def get_by_email(self, email: str) -> dict | None:
        return self._by_email().get(email.lower())

    def empty(self) -> bool:
        return not bool(self._by_email())


class SessionStore:
    def __init__(self, ttl: int = SESSION_TTL):
        self._ttl = ttl
        self._sessions: dict[str, tuple[str, float]] = {}

    def create(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = (username, time.monotonic() + self._ttl)
        return token

    def get_username(self, token: str) -> str | None:
        entry = self._sessions.get(token)
        if not entry:
            return None
        username, expires = entry
        if time.monotonic() > expires:
            del self._sessions[token]
            return None
        return username

    def delete(self, token: str) -> None:
        self._sessions.pop(token, None)

    def invalidate_user(self, username: str, keep_token: str | None = None) -> int:
        """Haak: verbreek alle sessies van een gebruiker (bijv. na een wachtwoordwijziging), behalve
        `keep_token` (de eigen, net-vernieuwde sessie). NO-OP in deze in-memory store — de call-site
        bestaat alvast zodat een toekomstige PERSISTENTE SessionStore dit invult zonder de aanroepers te
        herbouwen. Geeft het aantal verbroken sessies terug (nu 0)."""
        return 0


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


def login_page(next_url: str = "/", error: str = "") -> str:
    err = f'<p style="color:#c0392b;margin:0 0 1rem">{error}</p>' if error else ""
    nxt = next_url.replace('"', '%22')
    return f"""<!doctype html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inloggen — NoochVille</title>
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
  <h1>NoochVille — inloggen</h1>
  {err}
  <form method="post" action="/login">
    <input type="hidden" name="next" value="{nxt}">
    <label for="u">E-mailadres</label>
    <input type="email" id="u" name="email" autocomplete="email" autofocus required>
    <label for="p">Wachtwoord</label>
    <input type="password" id="p" name="password" autocomplete="current-password" required>
    <button type="submit">Inloggen</button>
  </form>
</div></body></html>"""


def password_change_page(next_url: str = "/", error: str = "", forced: bool = False) -> str:
    """Self-service wachtwoord-wijzigen (dezelfde auth-interstitial-stijl als login_page). `forced=True`
    bij een verplichte eerste-login-wijziging (temp-wachtwoord)."""
    err = f'<p style="color:#c0392b;margin:0 0 1rem">{error}</p>' if error else ""
    intro = ('<p style="color:#5a5a5a;font-size:.9rem;margin:-.75rem 0 1.5rem">Je gebruikt een tijdelijk '
             'wachtwoord. Kies nu een eigen wachtwoord om verder te gaan.</p>') if forced else ""
    nxt = next_url.replace('"', '%22')
    # Bij een VERPLICHTE wijziging geen 'huidig wachtwoord'-veld: de gebruiker is net via login
    # geauthenticeerd (die verifieerde het temp al), en het veld lokt browser-autofill van het OUDE
    # wachtwoord uit → een onmogelijk-op-te-lossen loop. Voor een vrijwillige wijziging blijft het staan.
    current_field = "" if forced else (
        '<label for="c">Huidig wachtwoord</label>'
        '<input type="password" id="c" name="current" autocomplete="current-password" autofocus required>')
    new_focus = " autofocus" if forced else ""
    return f"""<!doctype html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wachtwoord wijzigen — NoochVille</title>
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
  <h1>Wachtwoord wijzigen</h1>
  {intro}{err}
  <form method="post" action="/wachtwoord">
    <input type="hidden" name="next" value="{nxt}">
    {current_field}
    <label for="n">Nieuw wachtwoord</label>
    <input type="password" id="n" name="new" autocomplete="new-password"{new_focus} required>
    <label for="n2">Nieuw wachtwoord (bevestig)</label>
    <input type="password" id="n2" name="confirm" autocomplete="new-password" required>
    <button type="submit">Opslaan</button>
  </form>
</div></body></html>"""
