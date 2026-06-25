#!/usr/bin/env bash
# Eén commando dat de cockpit volledig ververst:
#   1) enrich_volumes → keyword-volumes/kans, GSC-stand, 5-jaars seed-trend + opleving-signalen
#   2) één dag-puls  → Field Note + Noochie's dagrapport + concurrent-nieuws, én Harry/scout
#                      onderzoeken de zojuist gesignaleerde seed-oplevingen
#
# enrich vóór de puls, zodat een verse opleving in dezelfde run wordt onderzocht.
# Draaien vanuit de noochville-map:  ./refresh.sh
set -e
cd "$(dirname "$0")"
PY="./venv/bin/python"
[ -x "$PY" ] || PY="python"   # val terug op systeem-python als de venv ontbreekt

echo "📐 1/2 — woorden verrijken (volume, kans, GSC-stand, 5-jaars seed-trend, opleving-signalen)..."
"$PY" -m nooch_village.village enrich_volumes

echo
echo "🌅 2/3 — dag-puls draaien (Field Note, Noochie, concurrent-nieuws; Harry/scout duiden oplevingen)..."
"$PY" -m nooch_village.village once

echo
echo "🔗 3/4 — Synthesist: creatieve links leggen tussen kennis-kaartjes..."
"$PY" -m nooch_village.village synthesize 3

echo
echo "💬 4/5 — openstaande vragen aan rollen gebundeld beantwoorden..."
"$PY" -m nooch_village.village answer_questions

echo
echo "🛍️  5/5 — Shopify-verkoopindicatoren ophalen (website watcher-dashboard)..."
"$PY" -m nooch_village.village shopify || echo "   (overgeslagen: geen SHOPIFY_STORE/SHOPIFY_TOKEN in .env)"

echo
echo "✅ Klaar. Herlaad de cockpit (http://127.0.0.1:8765) — weekrapport, Noochie,"
echo "   keyword-volumes/kans, seed-trendtoestanden en beantwoorde vragen staan nu vers."
