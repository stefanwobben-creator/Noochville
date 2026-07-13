# Deploy & ingest — runbook

Kort operationeel spoorboekje voor NoochVille (village.nooch.earth). Bedoeld om
niet elke keer opnieuw uit te hoeven zoeken waar wat staat.

## De setup in één blik

- **Live server (Hetzner):** `root@138.201.154.162` (host `ubuntu-4gb-fsn1-1`).
- **Repo op de server:** `/opt/noochville` (hier staat `.git`).
- **GitHub:** `git@github.com:stefanwobben-creator/Noochville.git`, branch `main`.
- **Virtualenv op de server:** `/opt/noochville/venv` — let op: `venv`, NIET `.venv`.
  De system-`python3` mist de dependencies (o.a. `pydantic`), dus gebruik altijd
  de venv-python voor losse commando's.
- **Services (systemd):**
  - `noochville-cockpit2` — het webdashboard.
  - `noochville-village` — de puls/daemon.

## Deployen (nieuwe code live zetten)

1. **Lokaal (je Mac):** commit is al gemaakt, push naar GitHub.
   ```
   cd ~/noochville && git push origin main
   ```
2. **Op de server:** inloggen, pullen, herstarten.
   ```
   ssh root@138.201.154.162
   cd /opt/noochville
   git pull
   systemctl restart noochville-cockpit2 noochville-village
   ```
3. **Controleren dat ze draaien** (twee keer `active` verwacht):
   ```
   systemctl is-active noochville-cockpit2 noochville-village
   ```

Bij een schone `git pull` zie je `Fast-forward` en de gewijzigde bestanden. Zie
je `Already up to date` terwijl je een push deed, dan wees je naar de verkeerde
remote/branch of is de push nog niet doorgekomen.

## Inoreader-ingest draaien (Radar-signalen ophalen)

Draai met de **venv-python** ÉN als de service-gebruiker `nooch` (NIET als root),
vanuit de repo-root:

```
cd /opt/noochville
sudo -u nooch /opt/noochville/venv/bin/python -m nooch_village.inoreader_ingest --limit 20 --debug
```

> ⚠️ **Draai NOOIT als root.** De ingest schrijft `data/radar.json`. Als root dat
> bestand aanmaakt, wordt het `root:root` en kan de webservice (draait als `nooch`)
> het niet meer lezen → elke pagina crasht met een 502 (`Permission denied:
> data/radar.json`). Overkwam ons op 13-07. Herstel als het tóch gebeurde:
> `chown nooch:nooch /opt/noochville/data/radar.json && systemctl restart noochville-cockpit2 noochville-village`.
> De venv-python zonder `sudo -u nooch` (dus als root) laadt `.env` wél, dus de
> ingest lijkt te slagen — het venijn zit pas in de volgende paginaload.

- `--debug` toont per artikel de titel + het oordeel (kaart/seed/doelwit/concurrent/geen),
  handig om te zien of de distill goed filtert.
- `--limit N` begrenst het aantal artikelen per feed.
- `--reset` leegt `data/radar.json` vóór de run (schone start; gebruik spaarzaam,
  je gooit dan ook goedgekeurde/afgewezen signalen weg).

De feed-URL's staan in `/opt/noochville/.env` als `INOREADER_*_JSON_URL`. De
routing (welke feed → welke rol) staat in `nooch_village/radar_store.py`
(`_DEFAULT_FEEDS`), te overschrijven met `data/feeds.json`.

Na de run zie je de signalen in het dashboard bij de gekoppelde rol onder
**Tools** → Radar-blok: wachtrij goedkeuren (✓) of wegklikken (✗); goedgekeurd
belandt in het archief dat de rol als context meeleest.

## Valkuilen

- `python: command not found` → gebruik `python3` of, voor de village-code, de
  venv-python `/opt/noochville/venv/bin/python`.
- `No module named 'pydantic'` bij de ingest → je draaide met de system-python;
  gebruik de venv-python.
- `502 Bad Gateway` na een deploy/ingest → bijna altijd een rechten-probleem op een
  `data/*.json`-bestand dat als root is aangemaakt. Check `ls -l /opt/noochville/data/`
  en trek de eigenaar recht met `chown nooch:nooch <bestand>`. Zie de ingest-waarschuwing.
- Push kan niet vanuit de Cowork-sandbox (geen netwerk): pushen doe je vanaf je
  eigen Mac, de server pullt.
