# 🍸 IBA Cocktails

Aplicación full-stack que **scrapea, procesa y sirve** las recetas oficiales de cócteles de la [IBA (International Bartenders Association)](https://iba-world.com/), con un **bartender con IA** local (RAG) capaz de recomendar tragos a partir de preguntas en lenguaje natural.

El proyecto está compuesto por tres servicios orquestados con Docker Compose:

| Servicio | Tecnología | Puerto | Rol |
|----------|-----------|--------|-----|
| **scraper** | Python + Playwright | — | Extrae los ~102 cócteles oficiales desde iba-world.com |
| **cocktail-rag-api** | FastAPI + Transformers | `8000` | API REST + endpoint RAG con LLM local |
| **web-app** | Next.js 16 + React 19 | `3000` | Frontend: catálogo, detalle y chat con el bartender IA |

---

## 🏗️ Arquitectura

```text
                 ┌─────────────┐
                 │   scraper   │  (se ejecuta una vez y termina)
                 │  Playwright │
                 └──────┬──────┘
                        │ escribe cocktails_parsed.json
                        ▼
   Navegador      ┌──────────────────┐
  localhost:3000  │ cocktail-rag-api │  FastAPI + Qwen2.5-0.5B
   ┌──────────┐   │   (puerto 8000)  │  + sentence-transformers
   │ web-app  │──►│                  │  (embeddings en memoria)
   │ Next.js  │   └──────────────────┘
   └──────────┘
```

El flujo de arranque respeta las dependencias:
`scraper` → (al completar) → `cocktail-rag-api` → `web-app`.

---

## 📁 Estructura del proyecto

```text
iba-cocktails/
├── Docker-compose.yaml          # Orquestación de los 3 servicios
├── api/                         # Servicio FastAPI + RAG
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── scraping-iba/                # Pipeline de scraping
│   ├── Dockerfile
│   ├── scraper.py               # 1. Listado de cócteles
│   ├── scrape_details.py        # 2. Detalle de cada receta
│   ├── parse_ingredients.py     # 3. Estructura los ingredientes
│   ├── cocktails.json           # Datos crudos scrapeados
│   └── cocktails_parsed.json    # Datos estructurados (consumidos por la API)
└── web-app/                     # Frontend Next.js
    └── app/
        ├── page.tsx             # Redirige a /cocktails
        ├── cocktails/page.tsx   # Catálogo con filtros
        ├── cocktails/[slug]/page.tsx  # Detalle de un cóctel
        └── rag/page.tsx         # Bartender IA (chat)
```

---

## 🚀 Puesta en marcha

### Requisitos

- [Docker](https://www.docker.com/) y Docker Compose

### Levantar todo con Docker Compose

```bash
docker compose -f Docker-compose.yaml up --build
```

Esto ejecuta, en orden:

1. **scraper** — recorre iba-world.com y genera `cocktails_parsed.json`.
2. **cocktail-rag-api** — carga los datos, construye los *embeddings* y el LLM local en memoria, y expone la API en `:8000`.
3. **web-app** — sirve el frontend en `:3000`.

> ⏱️ El primer arranque puede tardar varios minutos: el scraper recorre ~102 páginas y la API descarga los modelos de HuggingFace. La caché de modelos se persiste en el volumen `hf_cache`, por lo que reinicios posteriores son más rápidos.

Una vez arriba:

- **Catálogo:** http://localhost:3000/cocktails
- **Detalle:** http://localhost:3000/cocktails/mojito
- **Bartender IA:** http://localhost:3000/rag
- **API (docs):** http://localhost:8000/docs

---

## 🧩 Servicios en detalle

### 1. Scraper (`scraping-iba/`)

Pipeline de tres pasos que se ejecutan en secuencia dentro del contenedor:

```dockerfile
CMD python scraper.py && python scrape_details.py && python parse_ingredients.py
```

| Paso | Script | Salida |
|------|--------|--------|
| 1. Listado | `scraper.py` | Nombre, slug, url, categoría, imagen y vistas de cada cóctel |
| 2. Detalle | `scrape_details.py` | Ingredientes (crudos), método, garnish y video |
| 3. Parseo | `parse_ingredients.py` | Ingredientes estructurados: `{ ingredient, quantity, unit, original }` |

Usa **Playwright (Chromium headless)** para renderizar el contenido cargado por JavaScript (lazy-loading de Elementor) e incluye reintentos, esperas anti-throttling y descarte del *age gate*.

**Formato de salida** (`cocktails_parsed.json`):

```json
{
  "cocktails": [
    {
      "name": "Alexander",
      "slug": "alexander",
      "category": "The Unforgettables",
      "ingredients": [
        { "ingredient": "Cognac", "quantity": 30.0, "unit": "ml", "original": "30 ml Cognac" }
      ],
      "method": "Pour all ingredients into cocktail shaker...",
      "garnish": "Sprinkle fresh ground nutmeg on top.",
      "video_link": "https://www.youtube.com/watch?v=..."
    }
  ]
}
```

### 2. API + RAG (`api/`)

API REST construida con **FastAPI**. Carga `cocktails_parsed.json` en memoria, genera *embeddings* con **sentence-transformers** (`paraphrase-multilingual-MiniLM-L12-v2`) y responde preguntas con el LLM local **Qwen2.5-0.5B-Instruct**.

**Endpoints REST:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/cocktails` | Lista todos los cócteles. Filtros opcionales: `?name=`, `?category=`, `?ingredient=` |
| `GET` | `/api/v1/cocktails/search?q=` | Búsqueda por nombre |
| `GET` | `/api/v1/cocktails/category/{category_name}` | Filtra por categoría |
| `GET` | `/api/v1/cocktails/ingredient/{ingredient_name}` | Filtra por ingrediente |
| `GET` | `/api/v1/cocktails/{slug}` | Detalle completo de un cóctel |
| `POST` | `/api/v1/cocktails/rag` | **Bartender IA** |

**Ejemplo de consulta RAG:**

```bash
curl -X POST http://localhost:8000/api/v1/cocktails/rag \
  -H "Content-Type: application/json" \
  -d '{ "question": "¿Qué cóctel refrescante con gin me recomiendas?" }'
```

```json
{
  "question": "¿Qué cóctel refrescante con gin me recomiendas?",
  "answer": "Te recomiendo el ...",
  "cocktails": [ /* cócteles relacionados */ ]
}
```

El endpoint detecta el ingrediente en la pregunta (índice dinámico, sin listas hardcodeadas), filtra o hace búsqueda por similitud vectorial, y genera la respuesta con el LLM local.

### 3. Web App (`web-app/`)

Frontend en **Next.js 16 / React 19** con **TailwindCSS 4** y **TypeScript**.

| Ruta | Descripción |
|------|-------------|
| `/` | Redirige a `/cocktails` |
| `/cocktails` | Catálogo con búsqueda por nombre y filtros por categoría/ingrediente |
| `/cocktails/[slug]` | Detalle: imagen, ingredientes, método, garnish y video |
| `/rag` | Chat con el bartender IA |

---

## ⚙️ Configuración

### Variables de entorno

**web-app**

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1/cocktails` | URL base de la API consumida desde el navegador |

**cocktail-rag-api**

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `HF_HOME` | `/root/.cache/huggingface` | Caché de modelos HuggingFace |

> La API monta `./scraping-iba` en `/app/data` para leer `cocktails_parsed.json`, y tiene CORS habilitado para todos los orígenes.

---

## 🛠️ Desarrollo local (sin Docker)

### API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

> Requiere que exista `cocktails_parsed.json` accesible en la ruta de datos configurada. Ejecuta primero el pipeline de scraping.

### Scraper

```bash
cd scraping-iba
pip install playwright
playwright install chromium --with-deps
python scraper.py && python scrape_details.py && python parse_ingredients.py
```

### Web App

```bash
cd web-app
npm install
npm run dev      # desarrollo
npm run build    # build de producción
npm run start    # servir producción
npm run lint     # ESLint
```

---

## 🧰 Stack tecnológico

- **Scraping:** Python 3.10, Playwright (Chromium)
- **Backend:** FastAPI, Uvicorn, PyTorch, Transformers, sentence-transformers, Qwen2.5-0.5B-Instruct
- **Frontend:** Next.js 16, React 19, TailwindCSS 4, TypeScript 5
- **Infraestructura:** Docker, Docker Compose

---

## 📄 Fuente de datos

Todos los datos provienen de [iba-world.com](https://iba-world.com/cocktails/all-cocktails/). Este proyecto es de carácter educativo/demostrativo.
