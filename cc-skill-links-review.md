# CC-vervolg: skill-links — reviewpunten vóór de merge

**Voor:** Claude Code, op de bestaande branch `skill-links` (niet gepusht, herschrijven mag).
Review is gedaan; het ontwerp staat. Drie punten, dan pushen.

## 1. Herformulering laat koppelingen wees achter (ontwerp-gaatje in taak 0)

Governance kent geen "bewerk": een herformulering is remove + add in één change, en
`governance.py` herkent dat al expliciet (de orphan-check op verweesd werk wordt dan
overgeslagen). Maar `acc_ids.apply_accountability_change` munt voor de nieuwe tekst een nieuw
id — bestaande koppelingen (AI-taken én skill-links) raken bij een herformulering dus alsnog
wees. Ze tonen als "—" in de UI, maar niemand wordt gewaarschuwd.

- Bij een change met precies één remove en één add binnen dezelfde rol: laat het id van de
  verwijderde tekst meereizen naar de nieuwe tekst (zelfde belofte, nieuwe woorden).
- In alle andere gevallen waar een remove een acc_id met bestaande koppelingen raakt: meld het
  in het gate-scherm vóór adoptie ("deze ronde maakt N koppelingen wees") en log het luid.
- Tests: herformulering behoudt de link; pure verwijdering toont de waarschuwing.

## 2. Rommel uit de commits (vóór de PR, branch mag herschreven)

De branch bevat bestanden die er niet in horen: `:mem:` (gewijzigd door testruns),
`notifications.json`, `village-core.zip` (1,5 MB), vijf tarballs onder `_to_delete/` (ruim
19 MB samen), de `kb-*.patch`-bestanden en de losse briefbestanden in de root. Haal ze uit de
commits (interactieve herschrijf of schone re-commit; er is nog niet gepusht).

Extra: `:mem:` blijkt al getrackt op main. Neem in deze branch een definitieve opruiming mee:
`git rm --cached ':(literal):mem:'` plus een `.gitignore`-regel, anders komt hij bij elke
testrun terug. Zelfde check voor `notifications.json`.

Vuistregel blijft: nooit `git add -A`; benoem bestanden expliciet en controleer de
bestandenlijst van elke commit vóór de push.

## 3. Geen codewerk: de Lara-vraag is beantwoord

`keywords_everywhere` bij librarian hoort bij "kandidaat-woorden beoordelen" (verrijken mét
zoekvolume dient het beoordelen; tekst-overlap kan dat verband niet zien). Dat wordt straks
een handmatige link via de dialoog door de founder — het opdroog-commando hoeft hier niets
te raden. Niets aan doen dus; dit staat er alleen zodat je het niet alsnog gaat "fixen".

## Afronding

Na punt 1 en 2: volle suite groen (vlag uit én aan), bestandenlijst van elke commit
controleren, dan push + PR. De vlag `skill_links_active` blijft op 0; die gaat pas om na een
paar dagen schone prod-logs.
