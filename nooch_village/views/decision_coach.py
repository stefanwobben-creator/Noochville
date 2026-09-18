"""Decision Coach — een beslissing wordt een prompt voor je eigen chat, en het sheet komt terug.

Drie panelen op één pagina, en de volgorde is de werkvolgorde:

  A. de generator      vul in wat je weet, kopieer de prompt, plak hem in je eigen chat;
  B. het logboek       plak het decision sheet terug; alleen dát, nooit het thinking report;
  C. de cirkel         wat anderen besloten, nieuwste eerst.

NUL TOKENS. Deze pagina roept geen model aan. Ze vult een door mensen onderhouden sjabloon in
(`prompts/decision_coach_en.md`) en toont de tekst. Het coachen gebeurt in de chat van het lid.

PRIVACY IS HIER GEEN TOOLTIP. Het thinking report blijft in die chat: er is geen veld voor, geen
route naartoe, en de parser weigert een plakactie waarin hij opduikt. Dat staat in gewone woorden
bóven het logboek-paneel, want een regel die je moet aanwijzen om te lezen is geen afspraak.

Governeerde view: alles komt uit het designsysteem (`nooch.css`). Referentie is `/copy-prompt`
(`views/copy_prompt.py`): formulier → gegenereerd blok → kopieerknop, plus `.card`, `.qadd-form`,
`.cl-filter`-chips, `.ptitle`, `.muted`. Geen inline styles, geen nieuwe klasse-familie.
"""
from __future__ import annotations

import datetime as _dt

from nooch_village import decision_coach as dc
from nooch_village import decision_sheets as ds
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.web_base import _e, _field, _page


def _chips(naam: str, opties, huidig: str) -> str:
    """Segmented picker als submit-knoppen — identiek aan `copy_prompt._cl_knoppen`.

    Bewust submit-knoppen en geen radio's: een klik herbouwt de prompt meteen, en de al ingetypte
    tekst blijft staan omdat het hele formulier meegaat."""
    uit = "<div class='cl-bar'>"
    for waarde in opties:
        aan = " on" if waarde == huidig else ""
        uit += (f"<button class='cl-filter pill{aan}' type='submit' name='set_{_e(naam)}' "
                f"value='{_e(waarde)}'>{_e(waarde)}</button>")
    return uit + "</div>"


def _generator(waarden: dict, base_dir: str) -> str:
    """Paneel A. Drie velden zijn verplicht; de rest mag leeg en wordt `not provided`."""
    f = (f"<form class='qadd-form' method='get' action='/decision-coach'>"
         + "".join(f"<input type='hidden' name='{_e(n)}' value='{_e(str(waarden.get(n, '')))}'>"
                   for n in ("reversibility", "confidence", "mode"))
         + _field("The decision you face, in one line", "decision", value=waarden.get("decision", ""),
                  fid="dc-decision", required=True,
                  placeholder="Do we switch the outsole supplier for the next batch?")
         + _field("Deadline", "deadline", kind="date", value=waarden.get("deadline", ""),
                  fid="dc-deadline", required=True)
         + _field("The options you see (one per line)", "options", kind="textarea",
                  value=waarden.get("options", ""), fid="dc-options", required=True,
                  attrs="rows='4'")
         + "<p class='ptitle'>How reversible is it?</p>"
         + _chips("reversibility", dc.REVERSIBILITY, waarden.get("reversibility", ""))
         + "<p class='ptitle'>How sure are you right now?</p>"
         + _chips("confidence", dc.CONFIDENCE, waarden.get("confidence", ""))
         + "<p class='muted'>Percent. A number you can be wrong about is worth more than a "
           "feeling you cannot check later.</p>"
         + "<p class='ptitle'>How long do you want to take?</p>"
         + _chips("mode", dc.MODES, waarden.get("mode", ""))
         + "<p class='muted'>FULL is about 30 minutes, SHORT about 10.</p>"
         + _field("What is at stake", "stakes", value=waarden.get("stakes", ""), fid="dc-stakes")
         + _field("What you leaning towards", "leaning", value=waarden.get("leaning", ""),
                  fid="dc-leaning")
         + _field("Who decides", "decider", value=waarden.get("decider", ""), fid="dc-decider")
         + _field("Who else is affected", "stakeholders", value=waarden.get("stakeholders", ""),
                  fid="dc-stakeholders")
         + _field("Your role", "role", value=waarden.get("role", ""), fid="dc-role")
         + _field("Facts you already have (paste anything)", "facts", kind="textarea",
                  value=waarden.get("facts", ""), fid="dc-facts", attrs="rows='6'")
         + "<button class='btn' type='submit'>Build the prompt</button></form>")

    verplicht_leeg = [n for n in ("decision", "deadline", "options")
                      if not str(waarden.get(n, "")).strip()]
    if verplicht_leeg:
        uitvoer = ("<div class='card'><p class='ptitle'>Your prompt</p>"
                   "<p class='muted'>Fill in the decision, the deadline and the options, then "
                   "press Build the prompt. Everything else is optional — the coach will ask.</p>"
                   "</div>")
        return f"<p class='ptitle'>1. Your decision</p>{f}{uitvoer}"

    try:
        prompt, _v = dc.bouw_prompt(base_dir, waarden)
    except dc.SjabloonOntbreekt as e:
        # FAIL-CLOSED EN ZICHTBAAR. Geen sjabloon = geen prompt; iets verzinnen zou een coach
        # opleveren die de afgesproken methode niet volgt, en dat zie je niet aan de uitvoer.
        uitvoer = ("<div class='card'><p class='ptitle'>Your prompt</p>"
                   f"<p class='muted'>No prompt: {_e(str(e))}</p></div>")
        return f"<p class='ptitle'>1. Your decision</p>{f}{uitvoer}"

    uitvoer = ("<div class='card'>"
               "<p class='ptitle'>Your prompt</p>"
               "<button class='btn ok' type='button' data-dc-kopieer>Copy the whole prompt</button>"
               "<p class='muted'>Paste this into ChatGPT, Gemini or Claude. Nothing is sent from "
               "here — this page only builds text. Edit it first if you want.</p>"
               + _field("Prompt", "prompt", kind="textarea", value=prompt, fid="dc-prompt",
                        attrs="rows='24' class='editor mono'")
               + "</div>")
    return f"<p class='ptitle'>1. Your decision</p>{f}{uitvoer}"


def _rolkeuze(rollen: list[tuple[str, str]]) -> str:
    """Vanuit WELKE rol is dit besloten? In een Holacracy-substraat is dat geen metadata.

    Eén rol → ingevuld, geen vraag. Meer dan één → de mens kiest, want alleen hij weet het; een
    lijst van al zijn rollen in het logboek verplaatst dat raadsel alleen naar de lezer. Geen rol →
    niets te kiezen, en het veld blijft leeg."""
    if not rollen:
        return "<input type='hidden' name='rol' value=''>"
    if len(rollen) == 1:
        rid, label = rollen[0]
        return (f"<input type='hidden' name='rol' value='{_e(rid)}'>"
                f"<p class='muted'>Logged from your role <b>{_e(label)}</b>.</p>")
    rijen = "".join(
        f"<div class='rdr-row'><input type='radio' id='dc-rol-{i}' name='rol' value='{_e(rid)}'>"
        f"<label for='dc-rol-{i}'>{_e(label)}</label></div>"
        for i, (rid, label) in enumerate(rollen))
    return ("<p class='ptitle'>Which role did you decide from?</p>"
            f"<div class='qadd-row'>{rijen}</div>")


def _logboek(csrf_token: str, melding: str, fout: str,
             rollen: list[tuple[str, str]] | None = None) -> str:
    """Paneel B. Eén textarea, één knop, en de privacy-afspraak in gewone woorden erboven."""
    bericht = ""
    if fout:
        bericht = f"<p class='card muted'>⚠ {_e(fout)}</p>"
    elif melding:
        bericht = f"<p class='card muted'>✓ {_e(melding)}</p>"
    form = ""
    if csrf_token:
        form = (f"<form method='post' action='/action' class='qadd-form'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='action' value='decision_sheet_log'>"
                f"<input type='hidden' name='next' value='/decision-coach'>"
                + _field("Paste the decision sheet", "sheet", kind="textarea", fid="dc-sheet",
                         attrs="rows='12'",
                         placeholder="=== DECISION SHEET ===\n…\n=== END DECISION SHEET ===")
                + _rolkeuze(rollen or [])
                + "<button class='btn' type='submit'>Log this decision</button></form>")
    return ("<p class='ptitle'>2. Log your decision</p>"
            "<p class='muted'>Your thinking report stays in your own chat. There is no field for "
            "it here and no way for the village to receive it: paste only the block between "
            "<b>=== DECISION SHEET ===</b> and <b>=== END DECISION SHEET ===</b>. If a thinking "
            "report shows up in the paste, nothing is saved and you get it back.</p>"
            f"{bericht}{form}")


def persoon_chips(rijen: list[dict], persoon: str, basis: str = "/decision-coach") -> str:
    """De filterchips per persoon. `basis` is de pagina waarop ze staan.

    Losgetrokken van de kaartjes omdat de wikipagina ze allebei nodig heeft maar het plakformulier
    niet. Eén renderer voor twee plekken; een tweede kopie zou na één wijziging uit de pas lopen."""
    mensen = sorted({str(r.get("decider") or "") for r in rijen if r.get("decider")})
    koppel = "&" if "?" in basis else "?"
    chips = (f"<div class='cl-bar'><a class='cl-filter pill{'' if persoon else ' on'}' "
             f"href='{_e(basis)}'>everyone</a>")
    for m in mensen:
        aan = " on" if m == persoon else ""
        chips += (f"<a class='cl-filter pill{aan}' "
                  f"href='{_e(basis)}{koppel}persoon={_e(m)}'>{_e(m)}</a>")
    return chips + "</div>"


def kaarten(rijen: list[dict]) -> str:
    """De gelogde besluiten als kaartjes. Puur renderen — geen filter-UI, geen formulier.

    De wikipagina toont precies deze kaartjes; het plakformulier met csrf en rolkeuze blijft op
    /decision-coach, want dat is een schrijfhandeling en een wikipagina leest."""
    if not rijen:
        return "<p class='muted'>No decision sheets logged yet.</p>"
    uit = []
    for r in rijen:
        wanneer = _datum(r.get("timestamp"))
        wie = _e(str(r.get("decider") or "unknown"))
        rol = _e(str(r.get("role") or ""))
        # De id ZICHTBAAR en kopieerbaar. Een id die alleen in het bestand staat is een
        # databasesleutel, geen handvat: in een werkoverleg moet je naar één besluit kunnen
        # wijzen, en vanaf een wikipagina ernaartoe kunnen linken.
        rid = str(r.get("id") or "")
        idblok = (f"<code class='pill'>{_e(rid)}</code> "
                  f"<button class='btn' type='button' data-dc-id='{_e(rid)}'>Copy id</button>"
                  if rid else "<span class='muted'>no id (logged before ids existed)</span>")
        uit.append(
            "<div class='card'>"
            f"<p class='muted'>{wie}{' · ' + rol if rol else ''} · {_e(wanneer)}</p>"
            f"<p class='ptitle'>{_e(str(r.get('decision') or ''))}</p>"
            f"<p class='muted'>{idblok}</p>"
            f"<p><b>Chose:</b> {_e(str(r.get('chosen_option') or ''))}</p>"
            f"<p><b>Predicted:</b> {_e(str(r.get('prediction') or ''))}</p>"
            f"<p><b>Stops if:</b> {_e(str(r.get('stop_signal') or ''))}</p>"
            "</div>")
    return "".join(uit)


def _cirkel(rijen: list[dict], persoon: str, vanaf: str, tot: str) -> str:
    """Paneel C. Lezen mag iedereen: elk lid ziet elk sheet. Geen bewerken, geen verwijderen."""
    chips = persoon_chips(rijen, persoon)

    filter_form = (f"<form class='qadd-form' method='get' action='/decision-coach'>"
                   f"<input type='hidden' name='persoon' value='{_e(persoon)}'>"
                   + _field("From", "vanaf", kind="date", value=vanaf, fid="dc-vanaf")
                   + _field("Until", "tot", kind="date", value=tot, fid="dc-tot")
                   + "<button class='btn' type='submit'>Filter</button></form>")

    lijst = kaarten(rijen)
    return (f"<p class='ptitle'>3. What the circle decided</p>"
            f"<p class='muted'>Everyone sees everyone's sheets. That is the point: a prediction "
            f"only teaches you something if someone can check it later.</p>"
            f"{chips}{filter_form}{lijst}")


def _datum(ts) -> str:
    try:
        return _dt.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:                                      # noqa: BLE001
        return ""


def _filter(rijen: list[dict], persoon: str, vanaf: str, tot: str) -> list[dict]:
    """Persoon en datumbereik. Een onleesbare datum filtert niet — hij mag nooit stil alles wissen."""
    uit = rijen
    if persoon:
        uit = [r for r in uit if str(r.get("decider") or "") == persoon]
    def _dag(r):
        return _datum(r.get("timestamp"))[:10]
    if vanaf:
        uit = [r for r in uit if _dag(r) and _dag(r) >= vanaf]
    if tot:
        uit = [r for r in uit if _dag(r) and _dag(r) <= tot]
    return uit


def render_decision_coach(st, *, base_dir: str, data_dir: str, csrf_token: str = "",
                          waarden: dict | None = None, melding: str = "", fout: str = "",
                          persoon: str = "", vanaf: str = "", tot: str = "",
                          rollen: list[tuple[str, str]] | None = None) -> str:
    """De pagina. `waarden` zijn de ingevulde formuliervelden (query-parameters).

    `rollen` zijn de rollen van de INGELOGDE mens als (id, label) — waaruit hij kiest bij het
    loggen. Ze komen van de aanroeper en niet uit deze view, zodat de pagina geen eigen idee van
    bemensing ontwikkelt naast `assignments`."""
    waarden = waarden or {}
    rijen = _filter(ds.alle(data_dir), persoon, vanaf, tot)
    hoofd = ("<h1 class='ptitle'>Decision coach</h1>"
             "<p class='muted'>Turn a decision you face into a coaching prompt for your own chat, "
             "then log what you decided. This page never calls a model and never stores your "
             "thinking.</p>"
             + _generator(waarden, base_dir)
             + _logboek(csrf_token, melding, fout, rollen)
             + _cirkel(rijen, persoon, vanaf, tot))
    return _page("Decision coach",
                 f"{_DS_LINK}{_nav()}<div class='c2-wrap'>"
                 f"<div class='c2-main roomy'>{hoofd}</div></div>{_KOPIEER_JS}")


# Kopiëren via de clipboard-API, identiek aan `views/copy_prompt.py`. Zonder JS blijft de tekst
# gewoon selecteerbaar — progressive enhancement, geen afhankelijkheid.
_KOPIEER_JS = """<script>(function(){
 function flits(k,tekst){var was=k.textContent;k.textContent='Copied';
   setTimeout(function(){k.textContent=was;},1600);}
 document.addEventListener('click',function(e){
   var k=e.target.closest&&e.target.closest('[data-dc-kopieer]');
   if(k){var t=document.getElementById('dc-prompt');
     if(t&&navigator.clipboard)navigator.clipboard.writeText(t.value).then(function(){flits(k);});
     return;}
   var i=e.target.closest&&e.target.closest('[data-dc-id]');
   if(i&&navigator.clipboard)navigator.clipboard.writeText(i.getAttribute('data-dc-id'))
     .then(function(){flits(i);});
 });
})();</script>"""


# ── De tool als artefact op de rol ───────────────────────────────────────────────────────────

#: De rol die dit gereedschap draagt. De Decision Coach is dorpsbreed bruikbaar, maar een tool die
#: alleen als URL bestaat, bestaat niet: je moet weten dát hij er is. Hij hangt daarom onder de rol
#: die het besluit-domein houdt — zelfde bezit-model als de copy-prompt-generator.
TOOL_ROL = "mother_earth__nooch__strategic_lead_founder_steward"
TOOL_TITEL = "Decision coach"
TOOL_BODY = (
    "Turns a decision you face into a coaching prompt for your own chat, and takes the decision "
    "sheet back afterwards. The village never calls a model here and never stores your thinking "
    "report — that stays in your chat.\n\n"
    "Open to every member: anyone can build a prompt and log a decision, and everyone sees "
    "everyone's sheets. A prediction only teaches you something if someone can check it later."
)


def zorg_voor_tool(records, store, rol_id: str = TOOL_ROL) -> str:
    """Zet de Decision Coach als tool-artefact op de rol. Idempotent.

    Geeft het artefact-id terug, of "" als de rol niet bestaat — fail-soft, want een ontbrekende
    rol is een governance-feit en geen reden om de cockpit op te houden."""
    if records.get(rol_id) is None:
        return ""
    for a in store.list(rol_id, "tool"):
        if (a.title or "").strip().lower() == TOOL_TITEL.lower():
            return a.id                                   # bestaat al
    art = store.add(rol_id, "tool", title=TOOL_TITEL, body=TOOL_BODY, url="/decision-coach",
                    inherit=False,                        # dorpsbreed bruikbaar, rol-eigen bezit
                    actor_id="system", actor_type="persona",
                    change_note="decision coach ontsloten op de rol die het besluit-domein houdt")
    return getattr(art, "id", "") or ""
