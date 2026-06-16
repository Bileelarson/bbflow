import os
import sys
import json
import uuid
import tempfile
import requests
import base64

def main():
    prompt = os.environ.get("LEO_PROMPT")
    if not prompt:
        print(json.dumps({"ok": False, "error": "Aucun texte fourni pour l'image."}))
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(json.dumps({"ok": False, "error": "Erreur serveur : Clé API manquante."}))
        return

    api_base = os.environ.get("OPENAI_BASE_URL", "https://ccapi.us/v1")
    if api_base.endswith('/'):
        api_base = api_base[:-1]

    model = os.environ.get("LEO_MODEL", "dall-e-3")
    if model.lower() in ["auto", ""]:
        model = "dall-e-3"

    url = f"{api_base}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "model": model
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        res.raise_for_status()
        data = res.json()
        
        item = data['data'][0]
        gen_id = str(uuid.uuid4())
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"img_{gen_id}.png")
        
        if 'b64_json' in item:
            img_data = base64.b64decode(item['b64_json'])
            with open(file_path, 'wb') as f:
                f.write(img_data)
        elif 'url' in item:
            image_url = item['url']
            if image_url.startswith('data:image'):
                header, encoded = image_url.split(",", 1)
                img_data = base64.b64decode(encoded)
                with open(file_path, 'wb') as f:
                    f.write(img_data)
            else:
                img_res = requests.get(image_url, timeout=30)
                img_res.raise_for_status()
                with open(file_path, 'wb') as f:
                    f.write(img_res.content)
        else:
            raise ValueError("Réponse API invalide de CCAPI.")

        print(json.dumps({
            "ok": True,
            "gen_id": gen_id,
            "files": [file_path],
            "prompt": prompt
        }))
        
    except Exception as e:
        err_msg = str(e)
        if 'res' in locals() and hasattr(res, 'text'):
            err_msg += f" | API: {res.text}"
            
        if len(err_msg) > 300:
            err_msg = err_msg[:300] + "... (Erreur trop longue, tronquée)"
            
        print(json.dumps({"ok": False, "error": f"CCAPI Error: {err_msg}"}))

if __name__ == "__main__":
    main()
