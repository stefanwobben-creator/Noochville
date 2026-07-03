# INFRA — waar draait wat

## NoochVille (het dorp + de cockpit) — Hetzner

- **Host:** `village.nooch.earth` (`138.201.154.162`) — Hetzner CX22 (Ubuntu 24.04).
- **Service-user:** `nooch`. **Repo:** `/opt/noochville` (draait `origin/main`).
- **Twee systemd-services** (config in `deploy/`):
  - `noochville-cockpit2` — het web-dashboard. Bindt op `127.0.0.1:8766`, achter nginx (reverse proxy `deploy/nginx.conf`, TLS via certbot).
  - `noochville-village` — de autonome dorp-puls.
  - Beheer: `sudo systemctl {status,restart} noochville-cockpit2` · logs: `journalctl -u noochville-cockpit2 -f`.
- **Secrets:** `/opt/noochville/.env` (gitignored). Ingeladen als systemd `EnvironmentFile` én via `_load_env()`. Bevat o.a. de LLM-keys, GSC-token-pad en de LiveKit-creds (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`).

### ⚠️ Geen aanhalingstekens in `.env`

Systemd's `EnvironmentFile` **stript geen quotes** — aanhalingstekens worden onderdeel van de waarde. Zet creds dus **kaal, zonder quotes**:

```
LIVEKIT_API_SECRET=abc123…       # goed
LIVEKIT_API_SECRET="abc123…"     # FOUT — de quotes komen in het secret terecht
```

### Deploy (kort; volledig protocol in `docs/werkwijze_en_deploy.md`)

```bash
cd /opt/noochville
tar czf backups/data_$(date +%F_%H%M).tgz data/   # snapshot (vangnet)
git pull                                          # code bijwerken (data/ blijft, is gitignored)
./venv/bin/pip install -r requirements.txt        # nieuwe deps
sudo systemctl restart noochville-cockpit2 noochville-village
```

## Impact App — apart, op Render + Neon

De **Impact App** draait op een **aparte stack**: **Render** (hosting) + **Neon** (Postgres). Los van de Hetzner-server hierboven — eigen secrets en eigen deploy.
