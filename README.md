# AI API Service

<p>
  <img src="assets/ai-api-service.png" alt="AI API Service" width="500"/>
</p>

API de servicios de IA con **FastAPI** optimizada para dispositivos de bajos recursos. Incluye generación de texto, transcripción de audio, embeddings, OCR y capacidades de **Business AI** (clasificación, sentimiento, NER, resumen y traducción).

---

## 🚀 Inicio Rápido (Baremetal - Linux)

```bash
# 1. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu configuración (modelos, API keys, etc.)

# 4. Crear primera clave de administrador
python init_admin.py

# 5. Ejecutar la API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Windows:** Reemplazar `python3` por `python`, `cp` por `copy`, y `source venv/bin/activate` por `venv\Scripts\activate`.

**Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)

**Autenticación:**
Agregar header `X-API-Key: tu_api_key_aqui`.

---

## 📡 Endpoints Principales

### Generación de Texto

`POST /generate/chat`
Ejemplo con curl:

```bash
curl -X POST "http://localhost:8000/generate/chat" \
  -H "X-API-Key: TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hola"}]}'
```

### Transcripción de Audio

`POST /transcribe/`

```bash
curl -X POST "http://localhost:8000/transcribe/" \
  -H "X-API-Key: TU_API_KEY" \
  -F "file=@audio.mp3"
```

### Embeddings

`POST /embeddings/`

```bash
curl -X POST "http://localhost:8000/embeddings/" \
  -H "X-API-Key: TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"texts":["Texto de ejemplo"]}'
```

### OCR

`POST /ocr/recognize`

```bash
curl -X POST "http://localhost:8000/ocr/recognize" \
  -H "X-API-Key: TU_API_KEY" \
  -F "image=@documento.jpg"
```

---

## 🏢 Business AI Endpoints

Todos requieren `X-API-Key`.

| Endpoint                          | Método | Descripción                                                                |
| --------------------------------- | ------ | -------------------------------------------------------------------------- |
| `/business/classify`              | POST   | Clasificación de texto en categorías personalizadas (multi-label opcional) |
| `/business/sentiment`             | POST   | Análisis de sentimiento y emociones                                        |
| `/business/entities`              | POST   | Extracción de entidades nombradas (NER)                                    |
| `/business/summarize`             | POST   | Resumen de texto (abstractive o extractive)                                |
| `/business/translate`             | POST   | Traducción de texto (es↔en)                                                |
| `/business/analyze/comprehensive` | POST   | Análisis completo: sentimiento + entidades + resumen                       |
| `/business/health`                | GET    | Verificación del estado de todos los servicios de Business AI              |

> Cada endpoint incluye ejemplos y parámetros en Swagger UI.

---

## 📦 Modelos Compatibles

| Tipo                                   | Modelo                                             | Ubicación / Descarga                      |
| -------------------------------------- | -------------------------------------------------- | ----------------------------------------- |
| **LLM (GGUF)**                         | Ej: `mistral-7b-instruct-v0.2.Q4_K_M.gguf`         | `data/models/llm/` (manual)               |
| **STT (Whisper, PyTorch)**             | tiny → large-v3                                    | Descarga automática                       |
| **Embeddings (Sentence Transformers)** | `all-MiniLM-L12-v2`                                | Descarga automática                       |
| **OCR (EasyOCR)**                      | Español, inglés +80 idiomas                        | Descarga automática                       |
| **Business AI**                        | Classifier, Sentiment, NER, Summarizer, Translator | Descarga automática (según configuración) |

> Modelos GGUF deben colocarse manualmente; el resto se descarga al primer uso.

---

## 🔧 Configuración

Editar `.env` para personalizar:

* **API:** versión, host, puerto
* **Modelos:** rutas y habilitación
* **Seguridad:** rate limiting, CORS
* **Rutas:** directorios de datos y logs

---

## 🔐 Administración de API Keys

Endpoint: `/admin/keys/`
Permite:

* Crear nuevas API keys con permisos específicos
* Listar / revocar / activar keys existentes
* Ver estadísticas de uso

> Guarda las API keys al crearlas; no se pueden recuperar después.

---

## 🐳 Docker

### Levantar con Docker Compose

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu configuración

# 2. Construir y levantar
docker compose up -d --build

# 3. Ver logs
docker compose logs -f api

# 4. Detener
docker compose down
```

### Build manual (sin compose)

```bash
docker build -t ai-api-service .
docker run -d \
  --name ai_api \
  -p 8000:8000 \
  -v $(pwd)/data/models:/app/data/models \
  -v $(pwd)/.env:/app/.env:ro \
  ai-api-service
```

### Multi-plataforma (amd64 + arm64)

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t ai-api-service .
```

### Hot reload (desarrollo)

Descomentar en `docker-compose.yml`:

```yaml
volumes:
  - ./app:/app/app
```

### Dockerfile (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
# ... instala gcc, torch CPU, requirements
FROM python:3.11-slim
# ... instala ffmpeg, copia solo binarios del builder
```

> Los modelos se montan como volumen (`./data/models:/app/data/models`) para persistir entre rebuilds.

---

## 📄 Licencia

Copyright © 2026 **Andy Clemente Gago**

Licenciado bajo **GNU GPL v3.0**

* ✅ Uso, modificación y distribución permitida
* ✅ Uso comercial permitido
* ⚠️ Trabajos derivados también deben ser **open source** bajo GPL v3

Archivo completo: [LICENSE](LICENSE)

