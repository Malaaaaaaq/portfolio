"""Portfolio web server and Gemini free-tier API bridge."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json, os, time

ROOT=Path(__file__).resolve().parent
MODEL=os.environ.get("GEMINI_MODEL","gemini-3.1-flash-lite")
GUIDE="""You are Malak's friendly portfolio assistant. Answer naturally in French, or in Moroccan Darija if the visitor uses it. Be warm and concise, but answer the question directly. The portfolio facts below are the source of truth. Never invent projects or details.

Malak Tamrani is a full-stack web developer in Casablanca. She has a Digital Development diploma, Web Full Stack specialization, from OFPPT, and is in year 3 of the Computer Science and Networks engineering cycle at EMSI.

The portfolio shows these three projects. When asked about her projects, list these three with their descriptions instead of giving a generic introduction:
1. Maritime Billing Management System for the National Ports Agency (ANP): a platform for submitting, processing, and billing ship manifests; Excel is listed as a tool.
2. Casa Italiana (2025): an Italian restaurant showcase website with menu, atmosphere, and practical information; built with HTML, CSS, and PHP.
3. ParLak (2026): a parking reservation and management platform with live tracking, statistics, and email notifications.

Skills shown: HTML, CSS, JavaScript, PHP, Python, OOP, React, Laravel, Bootstrap, Tailwind CSS, Figma, Word, Excel, PowerPoint, Agile/Scrum, MySQL, NoSQL, XAMPP, GitHub, VS Code, Git, Docker. Contact: malaktamrani2@gmail.com.
If you do not know a fact, say so and point the visitor to the portfolio. You are the portfolio assistant, not a human."""
def api_key():
    key=os.environ.get("GEMINI_API_KEY","").strip()
    if key: return key
    try:
        for line in (ROOT/".env").read_text(encoding="utf-8").splitlines():
            name,sep,value=line.partition("=")
            if sep and name.strip()=="GEMINI_API_KEY": return value.strip().strip("\"'")
    except OSError: pass
    return ""


def generate(key,data):
    models=[MODEL]
    if MODEL=="gemini-3.1-flash-lite": models.append("gemini-3.5-flash")
    for index,model in enumerate(models):
        for attempt in range(2):
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            req=Request(url,data=data,headers={"x-goog-api-key":key,"Content-Type":"application/json"},method="POST")
            try:
                with urlopen(req,timeout=50) as response: return json.loads(response.read().decode())
            except HTTPError as error:
                if error.code==503 and attempt==0:
                    time.sleep(1)
                    continue
                if error.code==503 and index<len(models)-1:
                    break
                raise
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_POST(self):
        if self.path!="/api/chat": self.send_error(404); return
        key=api_key()
        if not key: self.answer(503,{"error":"Ajoute GEMINI_API_KEY dans le fichier .env."}); return
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size<1 or size>24000: self.answer(413,{"error":"Message vide ou trop long."}); return
            incoming=json.loads(self.rfile.read(size)).get("messages",[])
            if not isinstance(incoming,list) or not 1<=len(incoming)<=12: self.answer(400,{"error":"Historique invalide."}); return
            contents=[]
            for item in incoming:
                role=item.get("role") if isinstance(item,dict) else None
                text=item.get("content") if isinstance(item,dict) else None
                if role not in ("user","assistant") or not isinstance(text,str) or not text.strip() or len(text)>1000:
                    self.answer(400,{"error":"Message invalide."}); return
                contents.append({"role":"model" if role=="assistant" else "user","parts":[{"text":text.strip()}]})
            if incoming[-1].get("role")!="user": self.answer(400,{"error":"Un message utilisateur est requis."}); return
            data=json.dumps({"systemInstruction":{"parts":[{"text":GUIDE}]},"contents":contents,"generationConfig":{"maxOutputTokens":700}}).encode()
            result=generate(key,data)
            reply="\n".join(p.get("text","") for c in result.get("candidates",[]) for p in c.get("content",{}).get("parts",[]) if p.get("text")).strip()
            if not reply: self.answer(502,{"error":"Gemini n’a pas renvoyé de réponse. Réessaie."}); return
            self.answer(200,{"reply":reply})
        except HTTPError as e:
            try: status=json.loads(e.read().decode()).get("error",{}).get("status","")
            except Exception: status=""
            print("Gemini API HTTP",e.code,status,flush=True)
            if e.code==429: msg="La limite gratuite Gemini est atteinte pour le moment. Réessaie plus tard."
            elif e.code in (400,401,403): msg="Clé Gemini invalide ou accès API non activé. Vérifie la clé et son projet Google AI Studio."
            elif e.code==404: msg="Modèle Gemini indisponible pour ce projet."
            elif e.code==503: msg="Gemini est temporairement indisponible. Le serveur a reessaie; attends un instant et reessaie."
            self.answer(502,{"error":msg})
        except (URLError,TimeoutError) as e:
            print("Gemini connection error:",e,flush=True); self.answer(502,{"error":"Connexion à Gemini impossible. Réessaie."})
        except (ValueError,json.JSONDecodeError): self.answer(400,{"error":"Requête invalide."})
        except Exception as e:
            print("Chat server error:",e,flush=True); self.answer(500,{"error":"Erreur inattendue du serveur."})
    def answer(self,status,obj):
        body=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)

if __name__=="__main__":
    server=ThreadingHTTPServer(("127.0.0.1",8000),Handler)
    print("Portfolio et chatbot Gemini gratuit : http://127.0.0.1:8000")
    print("GEMINI_API_KEY présente :",bool(api_key()))
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
