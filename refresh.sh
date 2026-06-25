#!/usr/bin/env bash
# Eén commando dat de cockpit volledig ververst:
#   1) één dag-puls  → Field Note + Noochie's dagverdict + vers concurrent-nieuws
#   2) enrich_volumes → keyword-volumes/kans, GSC-stand én de 5-jaars seed-trendtoestand
#
# Draaien vanuit de noochville-map:  ./refresh.sh
set -e
cd "$(dirname "$0")"
PY="./venv/bin/python"
[ -x "$PY" ] || PY="python"   # val terug op systeem-python als de venv ontbreekt

echo "🌅 1/2 — dag-puls draaien (Field Note, Noochie, concurrent-nieuws)..."
"$PY" -m nooch_village.village once

echo
echo "📐 2/2 — woorden verrijken (volume, kans, GSC-stand, 5-jaars seed-trend)..."
"$PY" -m nooch_village.village enrich_volumes

echo
echo "✅ Klaar. Herlaad de cockpit (http://127.0.0.1:8765) — weekrapport, Noochie,"
echo "   keyword-volumes/kans en seed-trendtoestanden staan nu vers."
