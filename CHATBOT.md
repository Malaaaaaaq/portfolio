# Chatbot du portfolio

## En local

La cle API Gemini est lue depuis le fichier local `.env`. Demarre le site avec :

```powershell
python chat_server.py
```

## Sur Vercel

1. Dans le projet Vercel, ouvre Settings > Environment Variables.
2. Ajoute `GEMINI_API_KEY` comme nom et colle la cle Gemini comme valeur. Coche Production (et Preview si souhaite).
3. Enregistre la variable.
4. Envoie les changements du projet vers la branche GitHub connectee a Vercel pour lancer un nouveau deploiement.

Ne place jamais la cle API dans le code ni dans GitHub. Le chatbot utilise Gemini Flash en offre gratuite, avec des quotas. Les prompts du niveau gratuit peuvent etre utilises pour ameliorer les produits Google; evite les informations privees.
