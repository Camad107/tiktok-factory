# Kie.ai — Documentation API & Référence

API Key : `1839ebc2fecc9b2ba957b4b211b390bd`
Base URL : `https://api.kie.ai`

---

## Crédits

- $5 = 1 000 crédits
- 1 crédit = $0.005

---

## Authentification

Tous les appels API nécessitent :
```
Authorization: Bearer <API_KEY>
```

---

## Common API

### Vérifier le solde
```
GET /api/v1/chat/credit
→ { "code": 200, "data": 100 }   (data = crédits restants)
```

### Créer une tâche (Jobs)
```
POST /api/v1/jobs/createTask
Content-Type: multipart/form-data

Champs :
  model    : <model_id>
  input    : JSON string des paramètres spécifiques au modèle
  prompt   : texte du prompt
  image    : fichier binaire (pour les modèles image-to-image)

Réponse :
{ "code": 200, "data": { "taskId": "xxx" } }
```

### Polling d'une tâche
```
GET /api/v1/jobs/recordInfo?taskId=<taskId>

Réponse :
{
  "code": 200,
  "data": {
    "taskId": "xxx",
    "state": "waiting|queuing|generating|success|fail",
    "resultJson": "{...}",   // JSON string à parser
    "failMsg": "..."         // si state == fail
  }
}
```

**États possibles :**
- `waiting` — en attente
- `queuing` — dans la file
- `generating` — en cours de génération
- `success` — terminé avec succès
- `fail` — erreur

**Extraction URL depuis resultJson :**
```python
import json
result = json.loads(data["resultJson"])
url = (result.get("url") or result.get("imageUrl") or
       result.get("image_url") or
       (result.get("images") or [None])[0] or
       (result.get("resultUrls") or [None])[0])
```

### Obtenir une URL de téléchargement (OBLIGATOIRE)
Les URLs dans `resultJson` sont temporaires et **ne se téléchargent pas directement**.
Il faut d'abord les convertir :

```
POST /api/v1/common/download-url
Content-Type: application/json
Body: { "url": "<url_kie_ai>" }

→ { "code": 200, "data": "https://tempfile.xxx" }
```
L'URL retournée dans `data` est valide **20 minutes**.

### Webhook sécurité (HMAC-SHA256)
```
Signature = base64(HMAC-SHA256(taskId + "." + timestamp, webhookHmacKey))
Headers requis : X-Webhook-Timestamp, X-Webhook-Signature
```

---

## File Upload API (OBLIGATOIRE pour passer des images à Seedream)

> **Base URL différente** : `https://kieai.redpandaai.co` (pas api.kie.ai)
> Même clé API Bearer. Upload **gratuit**. Fichiers supprimés après **3 jours**.

Les modèles comme Seedream 4.5 Edit attendent des URLs publiques dans `image_urls`.
Puisque notre serveur a une basic_auth, il faut d'abord uploader sur kieai.redpandaai.co
pour obtenir une URL publique temporaire.

### File Stream Upload (binaire multipart — recommandé)
```
POST https://kieai.redpandaai.co/api/file-stream-upload
Authorization: Bearer <API_KEY>
Content-Type: multipart/form-data

Champs :
  file        : fichier binaire (requis)
  uploadPath  : chemin sans slashes (requis) ex: "retournement"
  fileName    : nom fichier optionnel (même nom = écrase l'ancien)

Réponse :
{
  "success": true, "code": 200,
  "data": {
    "fileName": "xxx.jpg",
    "downloadUrl": "https://tempfile.redpandaai.co/xxx/retournement/xxx.jpg",
    "fileSize": 154832,
    "mimeType": "image/jpeg",
    "uploadedAt": "2025-01-01T12:00:00Z"
  }
}
→ Utiliser data.downloadUrl comme image_urls[0] pour Seedream
```

### URL Upload (depuis URL distante)
```
POST https://kieai.redpandaai.co/api/file-url-upload
Content-Type: application/json
{ "fileUrl": "https://...", "uploadPath": "retournement", "fileName": "opt.jpg" }
→ data.downloadUrl
```

### Base64 Upload (petits fichiers)
```
POST https://kieai.redpandaai.co/api/file-base64-upload
Content-Type: application/json
{ "base64Data": "data:image/jpeg;base64,...", "uploadPath": "retournement" }
→ data.downloadUrl
```

### Pattern Python — upload + Seedream
```python
KIE_UPLOAD_BASE = "https://kieai.redpandaai.co"

def upload_to_kie(client, image_path: str) -> str:
    """Upload local → URL publique temporaire (3 jours)."""
    with open(image_path, "rb") as f:
        r = client.post(
            f"{KIE_UPLOAD_BASE}/api/file-stream-upload",
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            files={"file": (Path(image_path).name, f, "image/jpeg")},
            data={"uploadPath": "retournement"},
            timeout=60,
        )
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Upload failed: {data}")
    return data["data"]["downloadUrl"]

# Puis dans createTask Seedream :
image_url = upload_to_kie(client, local_path)
json_body = {
    "model": "seedream/4.5-edit",
    "input": {
        "prompt": "...",
        "image_urls": [image_url],
        "aspect_ratio": "9:16",
        "quality": "basic",
    }
}
```

---

## Modèles disponibles

### Images

| Modèle | ID API | Usage | Coût estimé |
|--------|--------|-------|-------------|
| Seedream 4.5 Edit | `seedream/4.5-edit` | Image-to-image, édition | ~10-20 cr/image |

**Seedream 4.5 Edit — paramètres `input` :**
```json
{ "aspect_ratio": "9:16", "quality": "basic" }
```
Quality options : `basic`, `standard`, `quality`

**Seedream 4.5 Edit — multipart form :**
```
model   = seedream/4.5-edit
input   = {"aspect_ratio":"9:16","quality":"basic"}
prompt  = description de la transformation souhaitée
image   = <fichier image>
```

### Vidéo

Tous les modèles vidéo utilisent `POST /api/v1/jobs/createTask` avec `Content-Type: application/json` (pas multipart) et le body `{ "model": "...", "input": { ... } }`.
Poll : `GET /api/v1/jobs/recordInfo?taskId=xxx` → `data.state` + `data.videoInfo.videoUrl` (pas de resultJson pour la vidéo).

**Prix pour 5s portrait 9:16 720p :**

| Modèle | ID API | 5s 720p | 10s 720p | Notes |
|--------|--------|---------|---------|-------|
| **Runway** | endpoint dédié | **12 cr ($0.06)** | 30 cr ($0.15) | ✅ Le moins cher |
| **Grok Imagine** | `grok-imagine/text-to-video` | **6s = 20 cr ($0.10)** | 30 cr ($0.15) | Min 6s |
| **Kling v2.1 Standard** | `kling/v2-1-standard` | **25 cr ($0.125)** | 50 cr ($0.25) | |
| **Bytedance V1 Pro** | `bytedance/v1-pro-image-to-video` | **30 cr ($0.15)** | 60 cr ($0.30) | 6 cr/s à 720p |
| **Hailuo 2.3 Standard** | `hailuo/2-3-image-to-video-standard` | **6s = 30 cr ($0.15)** | 50 cr ($0.26) | Min 6s |
| **Sora 2** | `sora-2-text-to-video` | — | **10s = 30 cr ($0.15)** | Min 10s, audio inclus |
| **Bytedance Seedance 1.5 Pro** | `bytedance/seedance-1.5-pro` | **4s = 14 cr ($0.07)** | — | Min 4s, 8s=28cr |
| Wan v2.2-a14b Turbo | `wan/v2.2-a14b-turbo` | 80 cr ($0.40) | — | |
| Veo 3.1 Fast | `veo/3.1-fast` | ~80 cr ($0.40) | — | |
| Veo 3.1 Quality | `veo/3.1-quality` | ~400 cr ($2.00) | — | |
| Kling O3 | `kling/o3` | — | — | WF Video Tarot |
| Kling 2.5 | `kling/2.5` | — | — | WF Satisfying |

> **Top-ups high-tier** (+10% bonus crédits) : tarif effectif ~10% moins cher sur tous les modèles.

**Classement 5s 720p portrait du moins cher au plus cher :**
1. 🥇 Runway — $0.06
2. 🥈 Grok Imagine — $0.10 (6s minimum)
3. 🥉 Kling v2.1 Standard — $0.125
4. Bytedance V1 Pro / Hailuo 2.3 — $0.15
5. Wan / Veo Fast — $0.40

#### Runway — endpoint dédié (différent des autres)

```
POST /api/v1/runway/generate
Content-Type: application/json

{
  "prompt": "...",
  "duration": 5,          // ou 10 (10s = 720p uniquement)
  "quality": "720p",      // ou "1080p" (5s seulement)
  "aspectRatio": "9:16",  // 16:9, 9:16, 1:1, 4:3, 3:4
  "imageUrl": "...",      // optionnel (image-to-video)
  "waterMark": ""         // optionnel
}

Poll : GET /api/v1/runway/record-detail?taskId=xxx
→ data.state (wait|queueing|generating|success|fail)
→ data.videoInfo.videoUrl  (sur success)
→ data.videoInfo.imageUrl  (thumbnail)
→ data.expireFlag (0=valide, 1=expiré — expire après 14 jours)

Extension vidéo :
POST /api/v1/runway/extend
{ "taskId": "...", "prompt": "...", "quality": "720p" }
```

#### Kling v2.1 Standard — paramètres input

```json
{
  "model": "kling/v2-1-standard",
  "input": {
    "prompt": "...",
    "image_url": "https://...",
    "duration": "5",
    "negative_prompt": "blur, distort, low quality",
    "cfg_scale": 0.5
  }
}
```

#### Bytedance V1 Pro — paramètres input

```json
{
  "model": "bytedance/v1-pro-image-to-video",
  "input": {
    "prompt": "...",
    "image_url": "https://...",
    "resolution": "720p",
    "duration": "5",
    "camera_fixed": false,
    "seed": -1
  }
}
```

#### Bytedance Seedance 1.5 Pro — prix détaillés

| Résolution | Durée | Sans audio | Avec audio |
|-----------|-------|-----------|-----------|
| 480P | 4s | 7 cr ($0.035) | 14 cr ($0.07) |
| 480P | 8s | 14 cr ($0.07) | 28 cr ($0.14) |
| 480P | 12s | 19 cr ($0.095) | 38 cr ($0.19) |
| **720P** | **4s** | **14 cr ($0.07)** | 28 cr ($0.14) |
| **720P** | **8s** | **28 cr ($0.14)** | 56 cr ($0.28) |
| **720P** | **12s** | **42 cr ($0.21)** | 84 cr ($0.42) |
| 1080P | 4s | 30 cr ($0.15) | 60 cr ($0.30) |
| 1080P | 8s | 60 cr ($0.30) | 120 cr ($0.60) |
| 1080P | 12s | 90 cr ($0.45) | 180 cr ($0.90) |

#### Bytedance Seedance 1.5 Pro — paramètres input

```json
{
  "model": "bytedance/seedance-1.5-pro",
  "input": {
    "prompt": "...",
    "input_urls": ["https://..."],  // 0-2 images, optionnel
    "aspect_ratio": "9:16",
    "resolution": "720p",
    "duration": 8,
    "fixed_lens": false,
    "generate_audio": false         // true = coût supérieur
  }
}
```

#### Hailuo 2.3 Standard — paramètres input

```json
{
  "model": "hailuo/2-3-image-to-video-standard",
  "input": {
    "prompt": "...",
    "image_url": "https://...",
    "duration": "6",
    "resolution": "768P"
  }
}
```

#### Grok Imagine — paramètres input

```json
{
  "model": "grok-imagine/text-to-video",
  "input": {
    "prompt": "...",
    "aspect_ratio": "9:16",
    "mode": "normal",        // fun | normal | spicy
    "duration": "6",
    "resolution": "480p"
  }
}
```

#### Sora 2 — paramètres input

```json
{
  "model": "sora-2-text-to-video",
  "input": {
    "prompt": "...",
    "aspect_ratio": "portrait",   // portrait | landscape
    "n_frames": "10",             // 10 | 15
    "remove_watermark": true,
    "upload_method": "s3"
  }
}
```

#### Résultat vidéo (tous sauf Runway)

Poll via `GET /api/v1/jobs/recordInfo?taskId=xxx` :
```json
{
  "data": {
    "state": "success",
    "videoInfo": {
      "videoUrl": "https://...",
      "imageUrl": "https://..."
    }
  }
}
```
→ Appliquer `download-url` avant téléchargement.

### Audio / TTS (via ElevenLabs hébergé sur kie.ai)

| Modèle | ID API | Notes |
|--------|--------|-------|
| ElevenLabs Multilingual v2 | `elevenlabs/text-to-speech-multilingual-v2` | Même voix qu'ElevenLabs direct |
| ElevenLabs Turbo 2.5 | `elevenlabs/text-to-speech-turbo-2-5` | Plus rapide, légèrement moins qualitatif |

**Avantage :** Pas besoin de compte ElevenLabs séparé — tout passe par la clé kie.ai.

---

## Utilisation dans TikTok Factory

### WF Retournement Tarot
- Agent `agent_seedream.py` — Seedream 4.5 Edit en chaîne (3 appels)
- Entrée : photo source (3 cartes face cachée)
- Sortie : Image A (carte gauche révélée) → B (+ centre) → C (+ droite)

### WF Video Tarot
- Kling O3 image-to-video

### WF Satisfying ASMR
- Kling 2.5

### Potentiel : agent_voice.py via kie.ai
Au lieu d'un compte ElevenLabs direct, utiliser `elevenlabs/text-to-speech-multilingual-v2`
via la même clé kie.ai — unifie tous les appels IA sous une seule API.

---

## Pattern de code Python

```python
import httpx, json, time
from pathlib import Path

KIE_API_KEY = "1839ebc2fecc9b2ba957b4b211b390bd"
KIE_BASE = "https://api.kie.ai"

def create_task(client, model, prompt, input_params, image_path=None):
    data = {"model": model, "input": json.dumps(input_params), "prompt": prompt}
    files = {}
    if image_path:
        suffix = Path(image_path).suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        files = {"image": (Path(image_path).name, open(image_path, "rb"), mime)}
    r = client.post(
        f"{KIE_BASE}/api/v1/jobs/createTask",
        headers={"Authorization": f"Bearer {KIE_API_KEY}"},
        data=data, files=files, timeout=60
    )
    return r.json()["data"]["taskId"]

def poll_task(client, task_id, max_wait=300):
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(8)
        r = client.get(
            f"{KIE_BASE}/api/v1/jobs/recordInfo",
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            params={"taskId": task_id}, timeout=30
        )
        data = r.json().get("data", {})
        state = data.get("state", "")
        if state == "success":
            result = json.loads(data.get("resultJson", "{}"))
            return (result.get("url") or result.get("imageUrl") or
                    (result.get("images") or [None])[0] or
                    (result.get("resultUrls") or [None])[0])
        if state == "fail":
            raise RuntimeError(data.get("failMsg"))
    raise RuntimeError(f"Timeout {task_id}")

def get_download_url(client, kie_url):
    r = client.post(
        f"{KIE_BASE}/api/v1/common/download-url",
        headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
        json={"url": kie_url}, timeout=30
    )
    return r.json()["data"]

def download(client, kie_url, dest_path):
    dl_url = get_download_url(client, kie_url)
    r = client.get(dl_url, timeout=60, follow_redirects=True)
    Path(dest_path).write_bytes(r.content)
    return str(dest_path)
```

---

## Callbacks (alternative au polling)

Tous les modèles acceptent `callBackUrl` dans le body :
```json
{ "model": "...", "callBackUrl": "https://your-server.com/webhook", "input": { ... } }
```
Le système POST le résultat final quand la génération est terminée.
Vérification HMAC-SHA256 : `base64(HMAC-SHA256(taskId + "." + timestamp, webhookHmacKey))`

---

## Codes d'erreur HTTP

| Code | Signification |
|------|--------------|
| 200 | Succès |
| 401 | API key invalide/manquante |
| 402 | Crédits insuffisants |
| 404 | Ressource introuvable |
| 422 | Erreur de validation des paramètres |
| 429 | Rate limit dépassé |
| 455 | Service en maintenance |
| 500 | Erreur serveur |
| 501 | Génération échouée |
| 505 | Fonctionnalité désactivée |

---

## Limites & Notes

- Les URLs résultat expirent rapidement — toujours passer par `download-url` avant téléchargement
- L'URL `download-url` est valide **20 min** maximum
- Vidéos Runway : stockées **14 jours** puis suppression auto (`expireFlag: 1` si expiré)
- Polling recommandé : 8s entre chaque appel pour les images, 30s pour les vidéos
- Timeout suggéré : 300s pour les images, 600s pour les vidéos
- `resultJson` (images via recordInfo) : JSON string à parser — clés variables selon modèle
- `videoInfo.videoUrl` (vidéos via recordInfo) : URL directe (encore passer par download-url)
- Seedance 1.5 Pro avec `generate_audio: true` = coût plus élevé
- Runway 1080p = 5s seulement (10s uniquement en 720p)
