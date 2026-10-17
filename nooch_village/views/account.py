"""`/account` — je eigen mailvoorkeuren (17 oktober 2026, besluit Stefan).

Twee schakelaars: de weekmail en het verslag na een overleg. De stand staat er als TEKST ("On" /
"Off" in een `chip`), niet alleen als kleur. Een knop verstuurt een POST naar `/action`
(`mail_voorkeur_zet`, CSRF verplicht); deze pagina zelf wijzigt nooit iets — ook niet via de
afmeldlink uit een mail (`/account?uit=week`): die zet die ene schakelaar bovenaan, de klik doe je zelf.

HERGEBRUIKT PATROON (geen nieuwe klassen, geen inline style): de opbouw van `/today`
(`c2-wrap` → `c2-main` → `h1.ptitle` + `p.muted` → `c2-sec`), per voorkeur een `card` met de atomen
`chip` / `chip muted` en `btn sm` in een `qadd-row` — dezelfde formuliervorm als de knoppen elders.
Lagen: atomen (chip, btn) → molecuul (de kaart per voorkeur) → patroon (deze pagina)."""
from __future__ import annotations

from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.people import MAIL_SOORTEN
from nooch_village.web_base import _banner, _e, _page

#: Per soort de naam en de uitleg op het scherm. De sleutels zijn `people.MAIL_SOORTEN`.
_TEKST = {
    "week": ("Weekly mail", "Once a week: your open actions, unread messages and your projects."),
    "verslag": ("Meeting notes", "After a tactical or governance meeting you attended: what was decided."),
}


def _kaart(soort: str, aan: bool, csrf_token: str) -> str:
    naam, uitleg = _TEKST[soort]
    stand = ("<span class='chip'>On</span>" if aan else "<span class='chip muted'>Off</span>")
    knop = "Turn off" if aan else "Turn on"
    return (f"<div class='card' id='mail-{_e(soort)}'>"
            f"<p><strong>{_e(naam)}</strong> {stand}</p>"
            f"<p class='muted'>{_e(uitleg)}</p>"
            f"<form method='post' action='/action' class='qadd-row'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='soort' value='{_e(soort)}'>"
            f"<input type='hidden' name='aan' value='{'0' if aan else '1'}'>"
            f"<input type='hidden' name='next' value='/account#mail-{_e(soort)}'>"
            f"<button class='btn sm' type='submit' name='action' value='mail_voorkeur_zet'>{knop}</button>"
            f"</form></div>")


def render_account(st, ik: str = "", csrf_token: str = "", uit: str = "", msg: str = "") -> str:
    """`ik` = het persoon-id van de kijker (leeg = geen mens, bijv. auth uit); `uit` = de soort uit
    een afmeldlink, die bovenaan komt."""
    if not ik:
        inhoud = "<p class='muted'>Sign in as a person to manage your mail preferences.</p>"
    else:
        volgorde = sorted(MAIL_SOORTEN, key=lambda s: s != uit)          # de afmeld-soort eerst
        kaarten = "".join(_kaart(s, st.people.mail_voorkeur(ik, s), csrf_token) for s in volgorde)
        hint = ("<p class='muted'>You followed the unsubscribe link: use the button below to stop "
                "this mail.</p>" if uit in MAIL_SOORTEN and st.people.mail_voorkeur(ik, uit) else "")
        inhoud = f"{hint}<div class='c2-sec'>{kaarten}</div>"
    main = (f"<div class='c2-main'><h1 class='ptitle'>Account</h1>"
            f"<p class='muted'>Which mails Village sends you.</p>{_banner(msg) if msg else ''}"
            f"{inhoud}</div>")
    return _page("Account", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
