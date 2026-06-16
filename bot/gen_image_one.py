import os
import sys
import json
import uuid
import tempfile
import requests

def main():
    # 1. On récupère le texte tapé par l'utilisateur sur Telegram
    prompt = os.environ.get("LEO_PROMPT")
    if not prompt:
        print(json.dumps({"ok": False, "error": "Aucun texte fourni pour l'image."}))
        return

    # 2. On récupère tes clés de sécurité configurées sur Render
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(json.dumps({"ok": False, "error": "Erreur serveur : Clé API manquante."}))
        return

    api_base = os.environ.get("OPENAI_BASE_URL", "https://ccapi.us/v1")
    if api_base.endswith('/'):
        api_base = api_base[:-1]

    # Par défaut, on utilise DALL-E 3 pour une qualité maximale
    model = os.environ.get("LEO_MODEL", "dall-e-3")
    if model.lower() in ["auto", ""]:
        model = "dall-e-3"

    url = f"{api_base}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # On prépare la commande pour CCAPI
    payload = {
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "model": model
    }

    try:
        # 3. On demande la création de l'image à l'IA
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        res.raise_for_status()
        data = res.json()
        
        # On récupère le lien de l'image créée
        image_url = data['data'][0]['url']
        
        # 4. On la télécharge pour l'envoyer proprement sur Telegram
        img_res = requests.get(image_url, timeout=30)
        img_res.raise_for_status()
        
        gen_id = str(uuid.uuid4())
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"img_{gen_id}.png")
        
        with open(file_path, 'wb') as f:
            f.write(img_res.content)
            
        # 5. On confirme la réussite au bot qui va afficher l'image
        print(json.dumps({
            "ok": True,
            "gen_id": gen_id,
            "files": [file_path],
            "prompt": prompt
        }))
        
    except Exception as e:
        err_msg = str(e)
        if 'res' in locals() and hasattr(res, 'text'):
            err_msg += f" | Réponse API: {res.text}"
        print(json.dumps({"ok": False, "error": f"Erreur du moteur IA : {err_msg}"}))

if __name__ == "__main__":
    main()
