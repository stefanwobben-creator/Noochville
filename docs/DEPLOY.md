# Deployen naar prod

Eén pad, geen improvisatie. De hele reden hierachter: main stond deze zomer 25 commits rood
omdat niets de "volle suite groen"-poort afdwong, en losse ssh-deploys braken prod (root-chown,
verkeerde python). Dit legt de veilige route vast.

## De flow (elke wijziging)

1. **Branch** van `origin/main`.
2. **Volle suite lokaal groen** vóór je pusht (CLAUDE.md-eis).
3. **PR** → CI draait de volle suite. main is branch-protected: rood kan niet mergen, ook admins niet.
4. **Merge** naar main (squash).
5. **Deploy**: één commando (zie onder). Nooit meer met de hand `git pull && restart` op de server.

Zo is wat live gaat per definitie een geteste, gemergede commit.

## Deployen

```
ssh root@138.201.154.162 'bash /opt/noochville/scripts/deploy.sh'
```

`scripts/deploy.sh` doet, veilig en idempotent:

- git-acties draaien als **nooch** (niet root) → bestandsrechten blijven goed, geen PermissionError-crash;
- alleen **fast-forward naar origin/main** (gedivergeerd of vuil → stop, geen stille merge);
- `requirements.txt` gewijzigd? → dependencies bijwerken in de venv;
- `systemctl restart`, dan een **health-check** op `127.0.0.1:8766`;
- **faalt de health-check → automatische rollback** naar de vorige commit + herstart, met melding.

Uitkomsten: `✅ live op <commit>` (goed), `teruggerold…` (deploy brak, site draait weer op de vorige
versie — zoek uit wat de nieuwe commit brak), of `handmatig ingrijpen nodig` (ook de rollback is stuk;
`systemctl status noochville-cockpit2` + `journalctl -u noochville-cockpit2 -n 50`).

## Bewust (nog) niet

- **Geen staging.** Bij ~4 interne gebruikers is dat overkill; je ziet het resultaat op live en de
  auto-rollback vangt een kapotte deploy. Zet staging op zodra er echte klanten of meer mensen zijn.
- **Geen automatische deploy bij merge.** Kan later: een GitHub Action (workflow_dispatch of on-merge)
  die exact ditzelfde script over ssh aanroept. De logica zit al in `deploy.sh`, de knop is dan dun.
