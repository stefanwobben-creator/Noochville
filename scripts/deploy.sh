#!/usr/bin/env bash
# NoochVille deploy — veilig uitrollen van origin/main naar prod, met health-check en auto-rollback.
#
# Draai dit OP de server, als root (zoals je nu al inlogt):
#   ssh root@138.201.154.162 'bash /opt/noochville/scripts/deploy.sh'
#
# Wat het borgt (precies de dingen die deze zomer misgingen):
#   - Git-acties draaien als de service-gebruiker (nooch), NOOIT als root → geen kapotte
#     bestandsrechten meer (de PermissionError-crash op radar.json/kennisbank_intake.json).
#   - Alleen fast-forward naar origin/main. main is branch-protected en CI-groen, dus wat hier
#     landt is per definitie een geteste commit. Een gedivergeerde of vuile working tree → stop.
#   - ALLE services die deze code draaien worden herstart (cockpit EN daemon). Alleen de cockpit
#     herstarten laat de daemon op oude code draaien: de deploy lijkt geslaagd, maar de helft van
#     de wijziging is niet live.
#   - Na de restart een health-check op web EN daemon; faalt die, dan rolt het automatisch terug
#     naar de vorige commit en herstart. Een kapotte deploy heelt zichzelf in seconden i.p.v. de
#     site plat te leggen.
set -euo pipefail

# ── Config (pas alleen hier aan als iets verhuist) ──────────────────────────────────────────────
REPO="/opt/noochville"
# BEIDE services draaien deze code. De cockpit is wat je ziet, maar de daemon is waar de tend-lus,
# de bord-puls en het rolwerk draaien. Herstart je alleen de cockpit, dan draait de daemon rustig
# door op de OUDE code en lijkt de deploy geslaagd terwijl de helft van de wijziging niet live is —
# precies wat er op 29 juli 2026 gebeurde met de park-fix (de zombie-projecten bleven staan tot de
# daemon apart herstart werd). Nieuwe service erbij? Zet 'm in deze lijst.
SERVICES=("noochville-cockpit2" "noochville-village")
WEB_SERVICE="noochville-cockpit2"        # de enige met een HTTP-health-endpoint
RUN_USER="nooch"
VENV_PY="/opt/noochville/venv/bin/python"
HEALTH_URL="http://127.0.0.1:8766/"
# DE TWEEDE CHECK, EN DE REDEN DAT HIJ ER IS. Op 20 september 2026 stond de site een uur op 502
# terwijl `HEALTH_URL` keurig 303 gaf: `/` redirect naar de login zonder ooit `people.json` aan te
# raken, en dát bestand was onleesbaar geworden. Een health-check die de datalaag niet aanraakt,
# toetst alleen of het proces leeft — niet of de app werkt. `/login` leest people.json (`auth.py::
# _by_email`), dus hij valt om op precies de klasse fouten die `/` doorlaat.
DIEPTE_URL="http://127.0.0.1:8766/login"
HEALTH_RETRIES=10          # ~20s totale boot-marge
HEALTH_SLEEP=2
DAEMON_SETTLE=8            # de daemon mag even booten; een import-fout is binnen die tijd zichtbaar

log(){ printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
fout(){ printf '\n\033[31m✗ %s\033[0m\n' "$*" >&2; }
# Geel, en met een eigen teken. Een no-op deploy PRINTTE al dat er niets te doen was, maar in
# dezelfde neutrale ▸-stijl als elke geslaagde stap — dus hij las als "klaar" en niet als "er is
# niets gebeurd". Dat kostte een ronde: er werd gedeployd, er veranderde niets, en niemand zag het.
niets(){ printf '\n\033[33m◌ %s\033[0m\n' "$*"; }
git_nooch(){ sudo -u "$RUN_USER" git -C "$REPO" "$@"; }

# curl de app; "gezond" = een HTTP-status < 500 (200/302/401/403 = app leeft; leeg/5xx = stuk).
health_ok(){
  local code
  for _ in $(seq 1 "$HEALTH_RETRIES"); do
    # NIET `|| echo 000`: curl print bij connection-refused via -w al "000" én laat de || nóg een
    # "000" echoën → code werd "000\n000" (weergegeven als "000000"), wat de poort hieronder ten
    # onrechte als gezond passeerde en de rollback ondermijnde. Vang de exit-code los af.
    code="$(curl -o /dev/null -s -w '%{http_code}' --max-time 5 "$HEALTH_URL")" || code=000
    if [ "$code" != "000" ] && [ "$code" -lt 500 ]; then
      log "health-check OK (HTTP $code)"; return 0
    fi
    sleep "$HEALTH_SLEEP"
  done
  fout "health-check faalde (laatste code: ${code:-geen})"; return 1
}

# DE DATALAAG ÉCHT AANRAKEN. Zie de toelichting bij DIEPTE_URL: een 3xx van `/` zegt alleen dat er
# een proces luistert. Deze doet een request die people.json moet openen.
diepte_ok(){
  local code
  code="$(curl -o /dev/null -s -w '%{http_code}' --max-time 5 "$DIEPTE_URL")" || code=000
  if [ "$code" != "000" ] && [ "$code" -lt 500 ]; then
    log "diepte-check OK ($DIEPTE_URL → HTTP $code, datalaag leesbaar)"; return 0
  fi
  fout "diepte-check faalde ($DIEPTE_URL → ${code:-geen}) — het proces leeft, de app niet"
  return 1
}

# CONSISTENTIE. De health-check doet één request en kijkt naar de status: dat zegt dat er íéts
# luistert, niet dat het de zojuist uitgerolde code is. Op 27 september meldde de deploy "live op
# <commit>" terwijl een scherm er nog oud uitzag — en er was geen enkele manier om dat vóór het
# rapport te zien. Deze check doet er twee dingen aan:
#
#   1. TWAALF OPEENVOLGENDE REQUESTS, en de uitgeleverde inhoud moet twaalf keer identiek zijn.
#      Wisselt hij, dan serveren er meerdere processen verschillende code (of er staat iets
#      te cachen dat niet zou moeten) — precies de hypothese die je anders handmatig moet
#      uitsluiten.
#   2. WAT HET PROCES IN HET GEHEUGEN HEEFT versus WAT ER OP SCHIJF LIGT. `/version` geeft de
#      commit uit `.git` en de inhoud-hash van de stylesheet zoals het DRAAIENDE proces die bij
#      import berekende. Wijkt één van beide af van de checkout, dan draait er oude code en is
#      de deploy niet geslaagd, hoe groen de status ook is.
#
# `/version` antwoordt alleen zonder `X-Forwarded-For`, dus alleen vanaf de machine zelf.
consistentie_ok(){
  local url="http://127.0.0.1:8766/version" body eerste n=12 i
  eerste="$(curl -s --max-time 5 "$url")" || eerste=""
  if [ -z "$eerste" ]; then
    fout "consistentie-check: /version gaf niets terug"; return 1
  fi
  for i in $(seq 2 "$n"); do
    body="$(curl -s --max-time 5 "$url")" || body=""
    if [ "$body" != "$eerste" ]; then
      fout "consistentie-check: request $i wijkt af van request 1 — er serveren meerdere versies"
      printf '  1: %s\n  %d: %s\n' "$eerste" "$i" "$body"
      return 1
    fi
  done

  local live_commit disk_commit live_ds disk_ds
  live_commit="$(printf '%s' "$eerste" | sed -n 's/.*"commit": *"\([^"]*\)".*/\1/p')"
  live_ds="$(printf '%s' "$eerste" | sed -n 's/.*"ds": *"\([^"]*\)".*/\1/p')"
  disk_commit="$(git_nooch rev-parse HEAD)"
  disk_ds="$(md5sum "$REPO/nooch_village/static/nooch.css" | cut -c1-10)"

  if [ "$live_commit" != "$disk_commit" ]; then
    fout "consistentie-check: het proces draait $live_commit, op schijf staat $disk_commit"
    return 1
  fi
  if [ "$live_ds" != "$disk_ds" ]; then
    fout "consistentie-check: stylesheet in het geheugen ($live_ds) ≠ op schijf ($disk_ds)"
    return 1
  fi
  log "consistentie-check OK ($n identieke requests; commit én stylesheet gelijk aan de checkout)"
  return 0
}

# EIGENDOM IN data/. De klasse fout waar de diepte-check het symptoom van vangt: een script dat als
# root draaide laat een bestand achter dat de service niet meer kan lezen. Dat is deze zomer al
# gebeurd (radar.json, kennisbank_intake.json) en op 20 september opnieuw (people.json, door een
# "read-only" diagnose die sinds die dag wél schrijft).
#
# Herstellen en het LUID zeggen, niet stil repareren: een 502 laten staan is erger, maar wie dit in
# de log ziet moet weten dat er iets als root heeft gedraaid.
eigendom_ok(){
  local fout_lijst
  fout_lijst="$(find "$REPO/data" -maxdepth 2 ! -user "$RUN_USER" -printf '%u %p\n' 2>/dev/null || true)"
  if [ -z "$fout_lijst" ]; then
    log "eigendom-check OK (alles in data/ is van $RUN_USER)"; return 0
  fi
  fout "eigendom in data/ klopt niet — dit hoort NOOIT te gebeuren:"
  printf '%s\n' "$fout_lijst" >&2
  chown -R "$RUN_USER:$RUN_USER" "$REPO/data"
  fout "hersteld naar $RUN_USER. Zoek uit welk script als root draaide."
  return 0
}

# Een service zonder HTTP-endpoint (de daemon) toetsen we op wat er wél te weten valt: draait hij
# nog ná de boot-marge? Een import- of configfout laat 'm meteen sneuvelen; met Restart=always staat
# hij dan op 'activating (auto-restart)' of 'failed', nooit op 'active'.
daemon_ok(){
  local svc="$1" state
  sleep "$DAEMON_SETTLE"
  state="$(systemctl is-active "$svc" 2>/dev/null || true)"
  if [ "$state" = "active" ]; then
    log "daemon-check OK ($svc: $state)"; return 0
  fi
  fout "daemon-check faalde ($svc: ${state:-onbekend})"; return 1
}

restart(){
  for svc in "${SERVICES[@]}"; do
    log "herstarten: $svc"
    systemctl restart "$svc"
  done
}

# Gezond = de webapp antwoordt ÉN elke niet-web service draait nog. Beide, want een deploy die de
# daemon sloopt terwijl de site het doet, is geen geslaagde deploy.
alles_gezond(){
  eigendom_ok || return 1
  health_ok || return 1
  diepte_ok || return 1
  consistentie_ok || return 1
  for svc in "${SERVICES[@]}"; do
    [ "$svc" = "$WEB_SERVICE" ] && continue
    daemon_ok "$svc" || return 1
  done
  return 0
}

# ── 0. Sanity: draaien we als root en bestaat de repo? ──────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || { fout "draai dit als root (ssh root@...)"; exit 1; }
[ -d "$REPO/.git" ] || { fout "geen git-repo op $REPO"; exit 1; }

# ── 1. Uit de vuurlinie: verder draaien vanaf een kopie ─────────────────────────────────────────
#
# WAT ER MISGING (27 september 2026). Dit script ligt IN de repo die het zelf uitrolt, en bash leest
# een script INCREMENTEEL: hij onthoudt een positie in het bestand en haalt de volgende opdracht op
# als hij eraan toe is. Wijzigt `git merge` het script terwijl het draait, dan leest de lopende run
# vanaf die positie verder in de NIEUWE bytes. Bij een wijziging van vijftig regels bovenin schuift
# alles op en voert bash willekeurige stukken uit — of niets meer. De deploy van die dag is daarom
# met de hand omzeild: de nieuwe versie naar /tmp gekopieerd en die gedraaid.
#
# DE WISSEL. Vóór de pull kopieert het script zichzelf naar een pad BUITEN de repo en gaat daar
# verder (`exec`, dus geen tweede proces en dezelfde exit-code). Wat git daarna met het origineel
# doet raakt de lopende run niet meer. `NOOCH_DEPLOY_KOPIE` voorkomt dat de kopie dat opnieuw doet;
# zonder die vlag is dit een oneindige lus.
#
# WAAROM DE KOPIE BLIJFT STAAN. Hem aan het eind weggooien is precies dezelfde fout: een bestand
# weghalen dat op dat moment wordt uitgevoerd. Het is een vast pad, dus de volgende deploy
# overschrijft hem — er blijft nooit meer dan één liggen.
KOPIE="${NOOCH_DEPLOY_KOPIE_PAD:-/tmp/noochville-deploy-actief.sh}"
if [ -z "${NOOCH_DEPLOY_KOPIE:-}" ] && [ "$(readlink -f "${BASH_SOURCE[0]}")" != "$(readlink -f "$KOPIE" 2>/dev/null || echo "$KOPIE")" ]; then
  cp -f "${BASH_SOURCE[0]}" "$KOPIE"
  chmod 700 "$KOPIE"
  log "verder vanaf een kopie: $KOPIE (het origineel wordt zo door de pull overschreven)"
  export NOOCH_DEPLOY_KOPIE="$KOPIE"
  exec bash "$KOPIE" "$@"
fi
log "draait vanaf de kopie — een wijziging aan deploy.sh tijdens de pull raakt deze run niet"

# ── 2. Vuile working tree? Niet clobberen. ──────────────────────────────────────────────────────
# --untracked-files=no: alleen TRACKED wijzigingen blokkeren (bv. onbewaarde curatie in
# config/claims_database.json — die willen we juist beschermen). Untracked runtime-ruis (.cache/ en
# wat er in de toekomst bijkomt) mag een deploy nooit tegenhouden; robuuster dan elk mapje los ignoren.
if [ -n "$(git_nooch status --porcelain --untracked-files=no)" ]; then
  fout "de working tree op de server heeft ongecommitte wijzigingen aan tracked bestanden — eerst opruimen, deploy gestopt"
  git_nooch status --short --untracked-files=no; exit 1
fi

# ── 3. Op main + verse origin ophalen ───────────────────────────────────────────────────────────
BRANCH="$(git_nooch rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || { fout "server staat op '$BRANCH', niet op main — deploy gestopt"; exit 1; }
log "origin ophalen…"
git_nooch fetch --quiet origin main

OUD="$(git_nooch rev-parse HEAD)"
NIEUW="$(git_nooch rev-parse origin/main)"
if [ "$OUD" = "$NIEUW" ]; then
  niets "GEEN NIEUWE COMMIT — NIETS GEDEPLOYED."
  printf '  server en origin/main staan allebei op %s\n' "${OUD:0:9}"
  printf '  is dit onverwacht? Dan is je merge naar main waarschijnlijk nog niet gedaan.\n'
  printf '  alleen de services herstarten: systemctl restart %s\n' "${SERVICES[*]}"
  exit 0
fi

# Alleen fast-forward: als main en de server uit elkaar lopen, stoppen we (geen stille merge).
if ! git_nooch merge-base --is-ancestor "$OUD" "$NIEUW"; then
  fout "server en origin/main zijn gedivergeerd — handmatig uitzoeken, deploy gestopt"; exit 1
fi

# ── 4. Uitrollen (als nooch, dus rechten blijven goed) ──────────────────────────────────────────
log "uitrollen: ${OUD:0:9} → ${NIEUW:0:9}"
git_nooch merge --ff-only origin/main

# Deps alleen bijwerken als requirements.txt echt veranderde (scheelt tijd + verrassingen).
if [ -f "$REPO/requirements.txt" ] && ! git_nooch diff --quiet "$OUD" "$NIEUW" -- requirements.txt; then
  log "requirements.txt gewijzigd → dependencies bijwerken"
  sudo -u "$RUN_USER" "$VENV_PY" -m pip install -q -r "$REPO/requirements.txt"
fi

log "services herstarten…"
restart

# ── 5. Health-check (web ÉN daemon); faalt hij, automatisch terugrollen ─────────────────────────
if alles_gezond; then
  echo "$NIEUW" > "$REPO/.last_deploy" 2>/dev/null || true
  log "✅ live op ${NIEUW:0:9}"
  exit 0
fi

fout "deploy ongezond — terugrollen naar ${OUD:0:9}"
git_nooch reset --hard "$OUD"
restart
if alles_gezond; then
  fout "teruggerold naar ${OUD:0:9}; de site draait weer op de vorige versie. Zoek uit wat ${NIEUW:0:9} brak."
  exit 1
fi
fout "OOK de rollback is ongezond — handmatig ingrijpen nodig (systemctl status ${SERVICES[*]}; journalctl -u ${SERVICES[0]} -n 50)"
exit 2
