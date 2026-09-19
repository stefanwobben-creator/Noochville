"""Screenshots van de herbouwde schermen (fase 9-eindcheck), desktop + mobiel.

Draaien vanuit de repo-wortel:

    ./venv/bin/pip install -r requirements-dev.txt
    ./venv/bin/python -m playwright install chromium
    ./venv/bin/python claude/fase9_screenshots/maak_screenshots.py claude/fase9_screenshots

Hij zet een eigen wegwerp-datamap op met wat demo-inhoud, start de cockpit in gast-modus op
poort 8807 en schiet elk scherm op twee breedtes. Raakt `data/` niet aan.
"""
import sys, tempfile, threading, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from nooch_village import cockpit2, channels

UIT = pathlib.Path(sys.argv[1]); UIT.mkdir(parents=True, exist_ok=True)
dd = tempfile.mkdtemp(); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)
ik = st.people.add("Demo Een", "een@demo.nl"); jij = st.people.add("Demo Twee", "twee@demo.nl")
OWNER = "mother_earth__nooch__creator_of_shoes"
pids = {}
for titel in ("Website re-design", "Seedpack voor schoenendoos", "Marktstand materiaal-expo",
              "Afhaalfeest uitnodiging"):
    pids[titel] = st.projects.create(OWNER, titel, "human", status="running")
st.projects.start(pids["Marktstand materiaal-expo"])
st.projects.mark_awaiting_review(pids["Marktstand materiaal-expo"])
st.att.add(OWNER, "note", title="Selco (supplier)", body="Portugese partner voor Batch 4.")
st.att.add("mother_earth__nooch", "policy", title="Stance", domain="Governance", body="Hoe we staan.")
st.att.add("mother_earth__nooch", "tool", title="Copy checker", url="https://x")
st.channels.post(channels.circle_kanaal("mother_earth__nooch"), "Selco belde net.", author_id=ik.id)
st.channels.post(channels.dm_kanaal(ik.id, jij.id), "Kijk jij naar de mockup?", author_id=jij.id)
st.projects.add_feed_entry(pids["Marktstand materiaal-expo"], "Selco levert in drie weken.",
                           kind="comment", author_type="human", author_id=ik.id)

# AUTH UIT. `serve()` zet altijd een SessionStore en dan is elke route een login-redirect; de
# eerste ronde screenshots was daardoor acht keer dezelfde loginpagina. `make_handler(..., None)`
# is de guest-modus die de suite ook gebruikt.
import http.server, socketserver
csrf = "SHOOT-CSRF"
handler = cockpit2.make_handler(dd, csrf, None, None)
httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 8807), handler)
httpd.daemon_threads = True
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(1.5)

from playwright.sync_api import sync_playwright
PAGINAS = [("projects", "/projects"), ("messages", "/messages"),
           ("wiki", "/wiki"), ("circle", "/node?id=mother_earth__nooch"),
           ("circle-wiki", "/node?id=mother_earth__nooch&tab=wiki"),
           ("project", f"/project?id={pids['Marktstand materiaal-expo']}"),
           ("admin", "/admin"), ("claims-geparkeerd", "/claims")]
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for naam, breedte, hoogte in (("desktop", 1280, 900), ("mobiel", 390, 844)):
        pg = b.new_page(viewport={"width": breedte, "height": hoogte})
        for slug, pad in PAGINAS:
            try:
                pg.goto(f"http://127.0.0.1:8807{pad}", wait_until="networkidle", timeout=15000)
                pg.screenshot(path=str(UIT / f"{slug}-{naam}.png"), full_page=True)
                nu = pg.evaluate("document.body.classList.contains('nu')")
                print(f"  {slug:22s} {naam:8s} nu-scope={nu}")
            except Exception as e:
                print(f"  {slug:22s} {naam:8s} FOUT: {type(e).__name__}: {str(e)[:60]}")
        pg.close()
    b.close()
print("\nscreenshots in", UIT)
