"""'Snaker' (voorheen 'De Veter') — verborgen snake-easter-egg in de cockpit. Puur voor fun, bewust LOS van alles:
raakt geen dispatch-authz, geen kritieke stores, geen governance. Eigen JSON-store + één GET-pagina
(/snake) + één POST-score-route (/snake/score), beide achter de sessie-auth van do_GET/do_POST.

Beveiliging: de score-eigenaar komt UITSLUITEND uit de sessie-gebruiker (nooit uit de request-body),
en er wordt alleen geschreven als de nieuwe score hoger is dan het bestaande record.
"""
from __future__ import annotations
import json
import os

from nooch_village.util import atomic_write_json


class SnakeScores:
    """`data/snake_scores.json`: {"scores": {"<persoon_id>": {"score": int, "datum": "YYYY-MM-DD"}}}.
    Alleen je eigen hoogste score wordt bewaard (higher-only write)."""

    def __init__(self, path: str):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self._d = (json.load(f) or {}).get("scores", {})
        except Exception:
            self._d = {}

    def best(self, person_id: str) -> int:
        return int((self._d.get(person_id) or {}).get("score", 0))

    def record(self, person_id: str, score, datum: str) -> int:
        """Schrijf alleen als `score` hoger is dan het bestaande record. Geeft de (nieuwe) beste terug."""
        try:
            s = int(score)
        except (TypeError, ValueError):
            return self.best(person_id)
        if not person_id or s <= self.best(person_id):
            return self.best(person_id)
        self._d[person_id] = {"score": s, "datum": datum}
        atomic_write_json(self.path, {"scores": self._d})
        return s

    def all(self) -> dict:
        return dict(self._d)


def _store(st) -> SnakeScores:
    return SnakeScores(os.path.join(st.dd, "snake_scores.json"))


def _veteranen(st, scores: SnakeScores) -> list[dict]:
    """[{id, naam, score}] gesorteerd op score desc; naam uit de people-store, fallback op de id."""
    out = []
    for pid, rec in scores.all().items():
        p = st.people.get(pid)
        out.append({"id": pid, "naam": (p.name if p else pid), "score": int(rec.get("score", 0))})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


def _today() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()


def handle_score(st, username: str | None, score) -> dict:
    """Schrijf de score ONDER de sessie-gebruiker (nooit een meegestuurde naam), higher-only. Geeft de
    nieuwe veteranen-lijst + het eigen record terug. Guest/onbekend → geen schrijfactie."""
    scores = _store(st)
    actor = st.people.by_email(username) if username and username != "guest" else None
    if actor is not None:
        scores.record(actor.id, score, _today())
    me_id = actor.id if actor is not None else ""
    return {"best": scores.best(me_id) if me_id else 0, "me": me_id, "vets": _veteranen(st, scores)}


def render_snake_page(st, username: str | None, csrf: str = "") -> str:
    """De volledige /snake-pagina (overlay-stijl: dimscherm + cream egg-box + donker canvas). Bewuste
    afwijking van het prototype: een eigen route i.p.v. een in-page-overlay, zodat de easter-egg
    volledig los van de cockpit-shell staat en vanzelf achter de sessie-auth valt. Visueel identiek."""
    scores = _store(st)
    actor = st.people.by_email(username) if username and username != "guest" else None
    me_id = actor.id if actor is not None else ""
    data = json.dumps({"me": me_id, "best": scores.best(me_id) if me_id else 0,
                       "vets": _veteranen(st, scores), "csrf": csrf})
    return (
        "<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Snaker</title><style>" + _SNAKE_CSS + "</style></head><body>"
        "<div class='egg-box'>"
        "<button class='sluit' id='egg-sluit' aria-label='Sluiten'>×</button>"
        "<h2>🥾 Snaker</h2>"
        "<div class='tag'>Een verdwaalde schoenveter met honger naar sneakers. Pijltjes of WASD.</div>"
        "<canvas id='c' width='440' height='330'></canvas>"
        "<div class='statusrow'><span>Sneakers gegeten: <b id='score'>0</b></span>"
        "<span>Jouw record: <b id='best'>0</b></span></div>"
        "<div class='gameover' id='over'>De veter zit in de knoop. Spatie voor nog een potje.</div>"
        "<div class='vets'><h3>Veteranen · aller tijden</h3><div id='vetlijst'></div></div>"
        "</div>"
        # In een <script> is de inhoud raw text (entities worden NIET gedecodeerd) → niet HTML-escapen,
        # wél `<` naar de JSON-escape \\u003c zodat een naam met '</script>' niet uitbreekt.
        f"<script id='snake-data' type='application/json'>{data.replace('<', chr(92) + 'u003c')}</script>"
        "<script>" + _SNAKE_JS + "</script></body></html>")


# ── Visuele pariteit met snake-easteregg-prototype.html ─────────────────────────────────────
_SNAKE_CSS = """
:root{--groen:#41573D;--groen-licht:#5a7354;--cream:#F6F4EC;--card:#FFFFFF;--ring:#B9B6A9;
 --ink:#2A2A26;--muted:#7d7a6e;--rood:#B03A2E;}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:rgba(42,42,38,.85);
 color:var(--ink);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.egg-box{position:relative;background:var(--cream);border:1.5px solid var(--groen);border-radius:14px;
 padding:20px 22px;box-shadow:0 12px 40px rgba(0,0,0,.25);text-align:center}
.egg-box h2{font-size:16px;color:var(--groen);margin-bottom:2px}
.egg-box .tag{font-size:11px;color:var(--muted);margin-bottom:12px}
canvas{background:#1E241C;border:1px solid var(--ring);border-radius:10px;display:block;margin:0 auto}
.statusrow{display:flex;justify-content:space-between;align-items:center;max-width:440px;margin:10px auto 0;font-size:13px}
.statusrow b{color:var(--groen);font-variant-numeric:tabular-nums}
.sluit{position:absolute;top:8px;right:12px;background:none;border:none;font-size:22px;color:var(--muted);cursor:pointer}
.vets{max-width:440px;margin:14px auto 0;text-align:left}
.vets h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
.vet{display:flex;justify-content:space-between;font-size:13px;padding:5px 0;border-bottom:1px dashed #e2dfd4}
.vet:last-child{border-bottom:none}
.vet .naam{display:flex;align-items:center;gap:8px}
.vet .avatar{width:20px;height:20px;border-radius:50%;background:var(--groen);color:#fff;font-size:9px;
 font-weight:700;display:flex;align-items:center;justify-content:center}
.vet .score{font-weight:700;color:var(--groen);font-variant-numeric:tabular-nums}
.vet.jij{background:#EFF4EE;border-radius:6px;padding:5px 8px}
.gameover{color:var(--rood);font-weight:700;font-size:14px;margin-top:8px;display:none}
"""

_SNAKE_JS = """
(function(){
 // Sluiten: als embedded (overlay-iframe) → parent laten sluiten via postMessage; anders (directe
 // /snake-route als fallback) → history.back(). × en Escape roepen beide closeEgg aan.
 function closeEgg(){
   if(window.parent&&window.parent!==window){try{window.parent.postMessage({type:'snake-close'},location.origin);}catch(e){}}
   else{history.back();}
 }
 var _sl=document.getElementById('egg-sluit');if(_sl)_sl.addEventListener('click',closeEgg);
 document.addEventListener('keydown',function(e){if((e.key||'')==='Escape')closeEgg();});
 var D=JSON.parse(document.getElementById('snake-data').textContent);
 var vets=D.vets||[], best=D.best||0;
 var cv=document.getElementById('c'), ctx=cv.getContext('2d');
 var CELL=22, COLS=cv.width/CELL, ROWS=cv.height/CELL;
 var veter,dir,nextDir,sneaker,score,dood,timer,speed;
 document.getElementById('best').textContent=best;

 function renderVets(){
   vets.sort(function(a,b){return b.score-a.score;});
   document.getElementById('vetlijst').innerHTML=vets.map(function(v,i){
     var av=(v.naam||'?').slice(0,2).toUpperCase();
     return "<div class='vet "+(v.id===D.me?'jij':'')+"'><span class='naam'><span class='avatar'>"+av+
       "</span>"+(i+1)+". "+esc(v.naam)+"</span><span class='score'>"+v.score+"</span></div>";
   }).join('');
 }
 function esc(s){var d=document.createElement('div'); d.textContent=s==null?'':String(s); return d.innerHTML;}

 function reset(){
   veter=[{x:5,y:7},{x:4,y:7},{x:3,y:7}];
   dir={x:1,y:0}; nextDir=dir; score=0; dood=false; speed=170;
   document.getElementById('score').textContent=0;
   document.getElementById('over').style.display='none';
   dropSneaker(); clearInterval(timer); timer=setInterval(tick,speed);
 }
 function dropSneaker(){
   do{ sneaker={x:Math.floor(Math.random()*COLS),y:Math.floor(Math.random()*ROWS)}; }
   while(veter.some(function(s){return s.x===sneaker.x&&s.y===sneaker.y;}));
 }
 function tick(){
   dir=nextDir;
   var kop={x:veter[0].x+dir.x,y:veter[0].y+dir.y};
   if(kop.x<0||kop.y<0||kop.x>=COLS||kop.y>=ROWS||veter.some(function(s){return s.x===kop.x&&s.y===kop.y;}))
     return gameOver();
   veter.unshift(kop);
   if(kop.x===sneaker.x&&kop.y===sneaker.y){
     score++; document.getElementById('score').textContent=score; dropSneaker();
     if(speed>70){ speed-=6; clearInterval(timer); timer=setInterval(tick,speed); }
   } else { veter.pop(); }
   draw();
 }
 function draw(){
   ctx.fillStyle='#1E241C'; ctx.fillRect(0,0,cv.width,cv.height);
   ctx.shadowBlur=0; ctx.font=(CELL-2)+'px serif'; ctx.textBaseline='top';
   ctx.fillText('\\uD83D\\uDC5F', sneaker.x*CELL+1, sneaker.y*CELL+1);
   ctx.shadowColor='#39FF14'; ctx.shadowBlur=12; ctx.strokeStyle='#39FF14';
   ctx.lineWidth=CELL-8; ctx.lineCap='round'; ctx.lineJoin='round'; ctx.beginPath();
   veter.forEach(function(s,i){var x=s.x*CELL+CELL/2,y=s.y*CELL+CELL/2; i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});
   ctx.stroke();
   ctx.shadowBlur=0; ctx.strokeStyle='#B6FF8E'; ctx.lineWidth=3; ctx.stroke();
   var kop=veter[0], kx=kop.x*CELL+CELL/2, ky=kop.y*CELL+CELL/2;
   ctx.fillStyle='#7CFF3F'; ctx.shadowColor='#39FF14'; ctx.shadowBlur=16;
   ctx.beginPath(); ctx.arc(kx,ky,CELL/2-3,0,Math.PI*2); ctx.fill();
   ctx.shadowBlur=0; ctx.fillStyle='#E8E2D0'; ctx.fillRect(kx-2+dir.x*8, ky-2+dir.y*8, 4,4);
 }
 function gameOver(){
   dood=true; clearInterval(timer);
   document.getElementById('over').style.display='block';
   if(score>best){ best=score; document.getElementById('best').textContent=best; submit(score); }
 }
 function submit(sc){
   var body='csrf='+encodeURIComponent(D.csrf)+'&score='+encodeURIComponent(sc);
   fetch('/snake/score',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body})
     .then(function(r){return r.ok?r.json():null;})
     .then(function(j){ if(j){ vets=j.vets||vets; best=j.best||best;
       document.getElementById('best').textContent=best; renderVets(); } }).catch(function(){});
 }
 document.addEventListener('keydown',function(e){
   var m={ArrowUp:[0,-1],ArrowDown:[0,1],ArrowLeft:[-1,0],ArrowRight:[1,0],w:[0,-1],s:[0,1],a:[-1,0],d:[1,0]};
   var k=e.key.length===1?e.key.toLowerCase():e.key;
   if(m[k]){ e.preventDefault(); var x=m[k][0],y=m[k][1]; if(x!==-dir.x||y!==-dir.y) nextDir={x:x,y:y}; }
   if(k===' '&&dood){ e.preventDefault(); reset(); }
   if(k==='Escape'){ history.back(); }
 });
 renderVets(); reset();
})();
"""
