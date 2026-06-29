# NoochVille deployen op Hetzner CX22

## Eenmalige voorbereiding (lokaal)

1. Koop een Hetzner CX22 (Ubuntu 24.04, regio Amsterdam of Falkenstein)
2. Voeg je SSH-key toe tijdens het aanmaken van de server
3. Wijs een DNS A-record toe:
   `village.nooch.earth → <server-IP>`
   Wacht tot DNS propageert: `dig village.nooch.earth`

## Installatie op de server

```bash
# SSH naar de server als root
ssh root@<server-IP>

# Deploy-script ophalen en draaien
# (de repo bevat het script al; kloon eerst of upload het script handmatig)
bash /opt/noochville/deploy/deploy.sh
```

Het script doet automatisch:
- apt-installaties (python3, nginx, certbot, git, ufw)
- Firewall instellen (SSH + HTTP/HTTPS open)
- Gebruiker `nooch` aanmaken
- Code clonen naar `/opt/noochville`
- Virtualenv aanmaken en dependencies installeren
- `data/output/` aanmaken
- Systemd-services registreren en enablen
- nginx configureren en herladen
- SSL-certificaat ophalen via Certbot

## Secrets uploaden (lokaal uitvoeren, na het script)

```bash
scp .env root@<server-IP>:/opt/noochville/.env
scp gsc_token.json root@<server-IP>:/opt/noochville/gsc_token.json
ssh root@<server-IP> "chown nooch:nooch /opt/noochville/.env /opt/noochville/gsc_token.json"
```

## Services starten

```bash
ssh root@<server-IP>
systemctl start noochville-village noochville-cockpit2
systemctl status noochville-village noochville-cockpit2
```

## Verificatie

```bash
# Village logs live volgen
journalctl -u noochville-village -f

# Cockpit lokaal bereikbaar op de server?
curl -s http://127.0.0.1:8766 | head -5

# Publiek bereikbaar?
# Open https://village.nooch.earth in de browser
```

## Updates deployen

```bash
ssh root@<server-IP>
git -C /opt/noochville pull
/opt/noochville/venv/bin/pip install -q -r /opt/noochville/deploy/requirements.txt
systemctl restart noochville-village noochville-cockpit2
```

## Dagelijks beheer

| Actie | Commando |
|-------|---------|
| Village logs | `journalctl -u noochville-village -f` |
| Cockpit logs | `journalctl -u noochville-cockpit2 -f` |
| Service herstarten | `systemctl restart noochville-village` |
| Inbox bekijken | `sudo -u nooch /opt/noochville/venv/bin/python -m nooch_village.inbox` |
| Status beide services | `systemctl status noochville-*` |
| Certbot verlenging testen | `certbot renew --dry-run` |

## Aandachtspunten

- `.env` en `gsc_token.json` staan niet in de repo — altijd handmatig uploaden via `scp`
- GSC OAuth-token (`gsc_token.json`) vervalt periodiek — vernieuw lokaal en upload opnieuw
- Shopify-token toevoegen zodra OAuth geregeld is:
  voeg `SHOPIFY_TOKEN=shpat_...` toe aan `.env` op de server en herstart village
- SSL-certificaat verlengt automatisch via de Certbot-cronjob (check: `systemctl status certbot.timer`)
- De `data/`-map is de enige runtime-state — maak periodiek een backup:
  `tar -czf noochville-data-$(date +%F).tar.gz /opt/noochville/data/`
