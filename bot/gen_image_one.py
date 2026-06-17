import os
import sys
import json
import uuid
import tempfile
import requests
import urllib.parse

def main():
    # 1. On récupère le texte tapé sur Telegram
    prompt = os.environ.get("LEO_PROMPT")
    if not prompt:
        print(json.dumps({"ok": False, "error": "Aucun texte fourni pour l'image."}))
        return

    try:
        # 2. HACK : Utilisation d'une IA sans blocage Cloudflare
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

        # 3. Téléchargement de l'image générée
        img_res = requests.get(image_url, timeout=30)
        img_res.raise_for_status()

        # 4. Création du fichier sur ton serveur
        gen_id = str(uuid.uuid4())
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"img_{gen_id}.jpg")

        with open(file_path, 'wb') as f:
            f.write(img_res.content)

        # 5. Envoi direct à Telegram
        print(json.dumps({
            "ok": True,
            "gen_id": gen_id,
            "files": [file_path],
            "prompt": prompt
        }))

    except Exception as e:
        # En cas d'erreur, on réduit le message pour ne pas faire planter Telegram
        err_msg = str(e)[:300]
        print(json.dumps({"ok": False, "error": f"Erreur de génération : {err_msg}"}))

if __name__ == "__main__":
    main()
