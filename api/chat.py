"""Vercel serverless endpoint for the portfolio chat."""
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
import json

from chat_server import GUIDE, MODEL, api_key, generate


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        key = api_key()
        if not key:
            self.send_json(503, {"error": "Configure GEMINI_API_KEY dans les variables d'environnement Vercel."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 24000:
                self.send_json(413, {"error": "Message vide ou trop long."})
                return

            incoming = json.loads(self.rfile.read(length)).get("messages", [])
            if not isinstance(incoming, list) or not 1 <= len(incoming) <= 12:
                self.send_json(400, {"error": "Historique de conversation invalide."})
                return

            contents = []
            for item in incoming:
                role = item.get("role") if isinstance(item, dict) else None
                text = item.get("content") if isinstance(item, dict) else None
                if role not in ("user", "assistant") or not isinstance(text, str) or not text.strip() or len(text) > 1000:
                    self.send_json(400, {"error": "Message invalide."})
                    return
                contents.append({
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": text.strip()}]
                })

            if incoming[-1].get("role") != "user":
                self.send_json(400, {"error": "Un message utilisateur est requis."})
                return

            payload = json.dumps({
                "systemInstruction": {"parts": [{"text": GUIDE}]},
                "contents": contents,
                "generationConfig": {"maxOutputTokens": 700}
            }).encode("utf-8")
            result = generate(key, payload)
            answer = "\n".join(
                part.get("text", "")
                for candidate in result.get("candidates", [])
                for part in candidate.get("content", {}).get("parts", [])
                if part.get("text")
            ).strip()

            if not answer:
                self.send_json(502, {"error": "Gemini n'a pas renvoye de reponse. Reessaie."})
                return
            self.send_json(200, {"reply": answer})

        except HTTPError as error:
            try:
                status = json.loads(error.read().decode("utf-8")).get("error", {}).get("status", "")
            except Exception:
                status = ""
            print("Gemini API HTTP", error.code, status)
            if error.code == 429:
                message = "La limite gratuite Gemini est atteinte. Reessaie plus tard."
            elif error.code in (400, 401, 403):
                message = "Cle Gemini invalide ou acces API non active. Verifie la cle dans Vercel et son projet AI Studio."
            elif error.code == 503:
                message = "Gemini est temporairement indisponible. Reessaie dans un instant."
            else:
                message = "Gemini a refuse la requete. Verifie le projet et la cle dans AI Studio."
            self.send_json(502, {"error": message})
        except (URLError, TimeoutError) as error:
            print("Gemini connection error:", error)
            self.send_json(502, {"error": "Connexion a Gemini impossible. Reessaie."})
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"error": "Requete JSON invalide."})
        except Exception as error:
            print("Portfolio chat function error:", error)
            self.send_json(500, {"error": "Erreur inattendue du serveur du chatbot."})

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
