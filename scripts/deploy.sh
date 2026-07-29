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
HEALTH_RETRIES=10          # ~20s totale boot-marge
HEALTH_SLEEP=2
DAEMON_SETTLE=8            # de daemon mag even booten; een import-fout is binnen die tijd zichtbaar

log(){ printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
fout(){ printf '\n\033[31m✗ %s\033[0m\n' "$*" >&2; }
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
  health_ok || return 1
  for svc in "${SERVICES[@]}"; do
    [ "$svc" = "$WEB_SERVICE" ] && continue
    daemon_ok "$svc" || return 1
  done
  return 0
}

# ── 0. Sanity: draaien we als root en bestaat de repo? ──────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || { fout "draai dit als root (ssh root@...)"; exit 1; }
[ -d "$REPO/.git" ] || { fout "geen git-repo op $REPO"; exit 1; }

# ── 1. Vuile working tree? Niet clobberen. ──────────────────────────────────────────────────────
# --untracked-files=no: alleen TRACKED wijzigingen blokkeren (bv. onbewaarde curatie in
# config/claims_database.json — die willen we juist beschermen). Untracked runtime-ruis (.cache/ en
# wat er in de toekomst bijkomt) mag een deploy nooit tegenhouden; robuuster dan elk mapje los ignoren.
if [ -n "$(git_nooch status --porcelain --untracked-files=no)" ]; then
  fout "de working tree op de server heeft ongecommitte wijzigingen aan tracked bestanden — eerst opruimen, deploy gestopt"
  git_nooch status --short --untracked-files=no; exit 1
fi

# ── 2. Op main + verse origin ophalen ───────────────────────────────────────────────────────────
BRANCH="$(git_nooch rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || { fout "server staat op '$BRANCH', niet op main — deploy gestopt"; exit 1; }
log "origin ophalen…"
git_nooch fetch --quiet origin main

OUD="$(git_nooch rev-parse HEAD)"
NIEUW="$(git_nooch rev-parse origin/main)"
if [ "$OUD" = "$NIEUW" ]; then
  log "al up-to-date ($OUD) — niets te deployen. (Herstart forceren? systemctl restart ${SERVICES[*]})"; exit 0
fi

# Alleen fast-forward: als main en de server uit elkaar lopen, stoppen we (geen stille merge).
if ! git_nooch merge-base --is-ancestor "$OUD" "$NIEUW"; then
  fout "server en origin/main zijn gedivergeerd — handmatig uitzoeken, deploy gestopt"; exit 1
fi

# ── 3. Uitrollen (als nooch, dus rechten blijven goed) ──────────────────────────────────────────
log "uitrollen: ${OUD:0:9} → ${NIEUW:0:9}"
git_nooch merge --ff-only origin/main

# Deps alleen bijwerken als requirements.txt echt veranderde (scheelt tijd + verrassingen).
if [ -f "$REPO/requirements.txt" ] && ! git_nooch diff --quiet "$OUD" "$NIEUW" -- requirements.txt; then
  log "requirements.txt gewijzigd → dependencies bijwerken"
  sudo -u "$RUN_USER" "$VENV_PY" -m pip install -q -r "$REPO/requirements.txt"
fi

log "services herstarten…"
restart

# ── 4. Health-check (web ÉN daemon); faalt hij, automatisch terugrollen ─────────────────────────
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
