#!/usr/bin/env python3
"""Eenmalige her-autorisatie van het GSC-token op een account mét toegang (de eigenaar).

De app logt in met een OAuth-token (gsc_token.json). Dat token hoort bij een account dat zijn
toegang tot de property kwijt is. Dit script maakt een vers token op een account dat je zelf
kiest bij het inloggen (kies de EIGENAAR van nooch.earth).

Draaien met SSH-poortforward, zodat de browser-redirect de server bereikt:

  1) Mac:     ssh -L 8765:localhost:8765 root@138.201.154.162
  2) server:  cd /opt/noochville
              sudo -u nooch /opt/noochville/venv/bin/python gsc_reauth.py
  3) Open de geprinte URL in je Mac-browser, log in als de eigenaar, sta toe.

Het nieuwe token overschrijft gsc_token.json (de oude wordt geback-upt).
"""
import json
import os
import shutil
import sys
import time

TOKEN = os.path.join(os.getcwd(), "gsc_token.json")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
PORT = 8765


def main() -> int:
    if not os.path.exists(TOKEN):
        print(f"gsc_token.json niet gevonden in {os.getcwd()} — draai dit vanuit /opt/noochville.")
        return 1
    old = json.load(open(TOKEN))
    cid, csec = old.get("client_id"), old.get("client_secret")
    if not (cid and csec):
        print("client_id/client_secret ontbreken in het token — kan zo niet her-autoriseren.")
        return 1
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("google-auth-oauthlib ontbreekt. Installeer 'm eenmalig en draai opnieuw:")
        print("  sudo /opt/noochville/venv/bin/pip install google-auth-oauthlib")
        return 1

    cfg = {"installed": {
        "client_id": cid, "client_secret": csec,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]}}
    flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
    creds = flow.run_local_server(
        host="localhost", port=PORT, open_browser=False,
        authorization_prompt_message="\n>>> Open deze URL in je Mac-browser en log in als de EIGENAAR:\n\n{url}\n",
        success_message="Gelukt — je kunt dit tabblad sluiten en terug naar de terminal.")

    shutil.copy2(TOKEN, TOKEN + ".bak-" + time.strftime("%Y%m%d%H%M%S"))
    with open(TOKEN, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN, 0o600)
    print("\nNieuw token weggeschreven naar", TOKEN)

    # Bevestig meteen dat dit account de property nu wél mag lezen.
    try:
        from googleapiclient.discovery import build
        svc = build("webmasters", "v3", credentials=creds)
        print("Toegang van het nieuwe account:")
        for s in svc.sites().list().execute().get("siteEntry", []):
            print("  ", s["siteUrl"], "->", s["permissionLevel"])
    except Exception as e:
        print("kon de toegang niet direct bevestigen:", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
