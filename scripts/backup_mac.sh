#!/usr/bin/env bash
# NoochVille back-up — haal elke dag een snapshot van prod `data/` naar deze Mac (10 oktober 2026).
#
# WAAROM DIT BESTAAT. Op de server draaide geen enkele back-up: geen cron, geen timer, geen tool.
# De losse .bak-kopieën en /opt/noochville/backups staan op DEZELFDE schijf als de data, dus een
# kapotte server neemt ze mee. Stefans keuze (10 oktober 2026): de back-up komt naar zijn Mac.
#
# Hoe:
#   - een dagsnapshot in $DOEL/<datum>/data, met `rsync --link-dest` naar de vorige: een bestand dat
#     niet veranderde is een hardlink en kost geen extra ruimte, en elke dag is toch een volledige map;
#   - eerst naar <datum>.bezig, pas na een geslaagde rsync hernoemd — een halve snapshot telt nooit
#     als back-up;
#   - snapshots ouder dan $BEWAAR_DAGEN worden verwijderd, maar nooit de laatste;
#   - na elke run de herstel-toets (`backup_herstel_toets.py`): een back-up waarvan niemand weet of
#     hij terug te zetten is, is geen back-up;
#   - mislukt iets: een macOS-melding en een niet-nul exit, en het log zegt wat.
#
# Gebruik:   bash scripts/backup_mac.sh --label pre-apply   (handmatig: een EIGEN map)
# Dagelijks: scripts/launchd/nl.nooch.backup.plist (zie de kop van dat bestand) — zonder argumenten.
#
# HANDMATIG = MET EEN LABEL (11 oktober 2026). Zonder argumenten schrijft het script de DAGMAP
# (<datum>), en een tweede run op dezelfde dag verving die: zo verdween bij de uitrol van 11 oktober
# de snapshot van vlak vóór de uitrol onder een snapshot van erna. Met `--label <naam>` komt de
# snapshot in <datum>_<tijd>_<naam>, en bestaat die map al, dan stopt het script — hij overschrijft
# nooit. Gelabelde snapshots ruimt de opruimronde niet op (die kijkt alleen naar dagmappen): een
# snapshot met een reden blijft staan tot een mens hem weghaalt.
#
# LET OP: dit zijn prod-gegevens, straks ook finance-PDF's. Ze staan versleuteld zolang FileVault
# aan staat (Systeeminstellingen → Privacy en beveiliging → FileVault).
set -euo pipefail

SERVER="${NOOCH_SERVER:-root@138.201.154.162}"
BRON="${NOOCH_DATA:-/opt/noochville/data/}"
DOEL="${NOOCH_BACKUP_DIR:-$HOME/NoochVille-backups}"
BEWAAR_DAGEN="${NOOCH_BACKUP_DAGEN:-30}"
# NOOCH_REPO: launchd draait een VASTE KOPIE van dit script buiten de repo (~/NoochVille-backups/bin),
# want in de repo bestaat het alleen zolang de juiste branch is uitgecheckt. De repo levert dan alleen
# nog de venv en de stores voor de herstel-toets. De toets zelf staat naast dit script.
REPO="${NOOCH_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
HIER="$(cd "$(dirname "$0")" && pwd)"
PY="$REPO/venv/bin/python"

label=""
if [ "${1:-}" = "--label" ]; then
  label="$(printf '%s' "${2:-}" | tr -c 'A-Za-z0-9-' '-' | sed 's/-*$//' | cut -c1-40)"
  [ -n "$label" ] || { echo "gebruik: $0 --label <naam>" >&2; exit 2; }
elif [ -n "${1:-}" ]; then
  echo "gebruik: $0 [--label <naam>]" >&2; exit 2
fi
stamp="$(date +%Y-%m-%d)"
if [ -n "$label" ]; then stamp="$(date +%Y-%m-%d_%H%M%S)_$label"; fi
log(){ printf '%s  %s\n' "$(date '+%F %T')" "$*" | tee -a "$DOEL/backup.log"; }
# NOOCH_BACKUP_STIL: geen macOS-melding (de toets van dit script mag geen melding op het scherm zetten).
meld(){ [ -n "${NOOCH_BACKUP_STIL:-}" ] && return 0; /usr/bin/osascript -e "display notification \"$1\" with title \"NoochVille back-up\"" 2>/dev/null || true; }
faal(){ log "MISLUKT: $*"; meld "Back-up mislukt: $*"; exit 1; }

mkdir -p "$DOEL"
if [ -n "$label" ] && [ -e "$DOEL/$stamp" ]; then
  faal "$stamp bestaat al — een handmatige snapshot overschrijft nooit"
fi
vorige="$(ls -1d "$DOEL"/20??-??-?? 2>/dev/null | grep -v "/$stamp$" | tail -1 || true)"
werk="$DOEL/$stamp.bezig"
rm -rf "$werk"
mkdir -p "$werk"

log "start: $SERVER:$BRON → $DOEL/$stamp${vorige:+ (hardlinks naar $(basename "$vorige"))}"
link=()
[ -n "$vorige" ] && link=(--link-dest="$vorige/data")
# -a: rechten/tijden mee · --delete: binnen de snapshot exact gelijk aan de bron ·
# --numeric-ids: geen gebruikersnamen vertalen tussen server en Mac.
# `${link[@]+...}`: macOS draait bash 3.2, en daar is een LEGE array onder `set -u` een fout.
rsync -a --delete --numeric-ids ${link[@]+"${link[@]}"} \
      -e "ssh -o BatchMode=yes -o ConnectTimeout=20" \
      "$SERVER:$BRON" "$werk/data/" >>"$DOEL/backup.log" 2>&1 || faal "rsync gaf een fout (zie backup.log)"

if [ -n "$label" ]; then
  # Nog één keer kijken, vlak voor het hernoemen: ook een gelijktijdige run mag niets overschrijven.
  if [ -e "$DOEL/$stamp" ]; then faal "$stamp bestaat al — een handmatige snapshot overschrijft nooit"; fi
else
  rm -rf "$DOEL/$stamp"
fi
mv "$werk" "$DOEL/$stamp"
log "snapshot klaar: $(du -sh "$DOEL/$stamp" | cut -f1) ($(find "$DOEL/$stamp/data" -type f | wc -l | tr -d ' ') bestanden)"

NOOCH_REPO="$REPO" "$PY" "$HIER/backup_herstel_toets.py" "$DOEL/$stamp/data" >>"$DOEL/backup.log" 2>&1 \
  || faal "de herstel-toets op $stamp faalde (zie backup.log)"
log "herstel-toets OK"

# Oude snapshots weg, maar NOOIT de nieuwste (ook niet als de klok verkeerd staat).
find "$DOEL" -maxdepth 1 -type d -name '20??-??-??' -mtime +"$BEWAAR_DAGEN" -print0 \
  | while IFS= read -r -d '' oud; do
      [ "$oud" = "$DOEL/$stamp" ] && continue
      rm -rf "$oud" && log "opgeruimd: $(basename "$oud")"
    done
log "klaar"
