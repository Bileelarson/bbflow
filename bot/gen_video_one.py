import os
import sys
import json
import uuid
import tempfile
import requests

def main():
    # 1. Récupération des données
    prompt = os.environ.get("LEO_PROMPT")
    if not prompt:
        print(json.dumps({"ok": False, "error": "No prompt provided."}))
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    api_base = os.environ.get("OPENAI_BASE_URL", "https://ccapi.us/v1")
    if api_base.endswith('/'):
        api_base = api_base[:-1]

    model = os.environ.get("LEO_MOTION_MODEL", "kling-3.0")
    
    # 2. Préparation de la requête pour CCAPI
    url = f"{api_base}/videos/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "prompt": prompt,
        "model": model
    }

    try:
        # 3. Appel de l'Intelligence Artificielle
        res = requests.post(url, json=payload, headers=headers, timeout=120)
        
        # Si la clé ne gère pas la vidéo ou bloque, on gère l'erreur proprement
        if res.status_code != 200:
            print(json.dumps({"ok": False, "error": f"Video service is currently under maintenance. (API Error {res.status_code})"}))
            return
            
        data = res.json()
        video_url = data['data'][0]['url']
        
        # 4. Téléchargement de la vidéo
        vid_res = requests.get(video_url, headers={"User-Agent": headers["User-Agent"]}, timeout=120)
        vid_res.raise_for_status()
        
        gen_id = str(uuid.uuid4())
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"vid_{gen_id}.mp4")
        
        with open(file_path, 'wb') as f:
            f.write(vid_res.content)

        # 5. Envoi à Telegram
        print(json.dumps({
            "ok": True,
            "gen_id": gen_id,
            "files": [file_path],
            "prompt": prompt
        }))
        
    except Exception as e:
        # SÉCURITÉ : Message propre en cas de crash
        print(json.dumps({"ok": False, "error": "Video API is currently overloaded or in maintenance. Please try again later."}))

if __name__ == "__main__":
    main()
