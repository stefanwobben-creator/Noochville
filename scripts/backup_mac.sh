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
# Gebruik:   bash scripts/backup_mac.sh            (handmatig)
# Dagelijks: scripts/launchd/nl.nooch.backup.plist (zie de kop van dat bestand).
#
# LET OP: dit zijn prod-gegevens, straks ook finance-PDF's. Ze staan versleuteld zolang FileVault
# aan staat (Systeeminstellingen → Privacy en beveiliging → FileVault).
set -euo pipefail

SERVER="${NOOCH_SERVER:-root@138.201.154.162}"
BRON="${NOOCH_DATA:-/opt/noochville/data/}"
DOEL="${NOOCH_BACKUP_DIR:-$HOME/NoochVille-backups}"
BEWAAR_DAGEN="${NOOCH_BACKUP_DAGEN:-30}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/venv/bin/python"

stamp="$(date +%Y-%m-%d)"
log(){ printf '%s  %s\n' "$(date '+%F %T')" "$*" | tee -a "$DOEL/backup.log"; }
meld(){ /usr/bin/osascript -e "display notification \"$1\" with title \"NoochVille back-up\"" 2>/dev/null || true; }
faal(){ log "MISLUKT: $*"; meld "Back-up mislukt: $*"; exit 1; }

mkdir -p "$DOEL"
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

rm -rf "$DOEL/$stamp"
mv "$werk" "$DOEL/$stamp"
log "snapshot klaar: $(du -sh "$DOEL/$stamp" | cut -f1) ($(find "$DOEL/$stamp/data" -type f | wc -l | tr -d ' ') bestanden)"

"$PY" "$REPO/scripts/backup_herstel_toets.py" "$DOEL/$stamp/data" >>"$DOEL/backup.log" 2>&1 \
  || faal "de herstel-toets op $stamp faalde (zie backup.log)"
log "herstel-toets OK"

# Oude snapshots weg, maar NOOIT de nieuwste (ook niet als de klok verkeerd staat).
find "$DOEL" -maxdepth 1 -type d -name '20??-??-??' -mtime +"$BEWAAR_DAGEN" -print0 \
  | while IFS= read -r -d '' oud; do
      [ "$oud" = "$DOEL/$stamp" ] && continue
      rm -rf "$oud" && log "opgeruimd: $(basename "$oud")"
    done
log "klaar"
