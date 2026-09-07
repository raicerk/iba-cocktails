import os
import re
import json
import torch
import numpy as np
from typing import Optional, List
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Cocktail Knowledge Base & Local RAG API",
    version="1.0.0",
    description="API RESTful unificada con endpoints de consulta y RAG local."
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mensaje estandarizado para consultas fuera de dominio
OUT_OF_DOMAIN_RESPONSE = "Lo siento, solo puedo responder preguntas relacionadas con el catálogo de coctelería y sus ingredientes."

# ------------------------------------------------------------------------------
# 1. CARGA DE DATOS Y CONFIGURACIÓN DEL RAG LOCAL
# ------------------------------------------------------------------------------

DATA_PATH = "/app/data/cocktails_parsed.json"

try:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        COCKTAILS_DB: List[dict] = raw_data.get("cocktails", [])
except FileNotFoundError:
    print(f"WARNING: {DATA_PATH} not found. Starting with empty cocktail DB.")
    COCKTAILS_DB = []

def normalize_string(text: str) -> str:
    return text.lower().strip()

ALL_INGREDIENTS: set[str] = set()
INGREDIENT_WORD_INDEX: dict[str, set[str]] = {}
_STOP_WORDS = {
    "fresh", "juice", "simple", "sugar", "syrup", "cream", "dry", "old",
    "sweet", "double", "single", "strong", "light", "dark", "white", "red",
    "of", "de", "del", "la", "el", "los", "las", "un", "una", "and", "or",
    "ml", "cl", "oz", "dash", "dashes", "drop", "drops", "slice", "wedge",
    "top", "up", "with", "con", "que", "para", "por",
}

for c in COCKTAILS_DB:
    for i in c.get("ingredients", []):
        raw = i.get("ingredient", "")
        if not raw:
            continue
        normalized = normalize_string(raw)
        ALL_INGREDIENTS.add(normalized)
        for word in normalized.split():
            if len(word) >= 3 and word not in _STOP_WORDS:
                INGREDIENT_WORD_INDEX.setdefault(word, set()).add(normalized)

print(f"Ingredientes indexados: {len(ALL_INGREDIENTS)}, palabras clave: {len(INGREDIENT_WORD_INDEX)}")

# Preparar los documentos del catálogo
documents = []
for c in COCKTAILS_DB:
    ing_str = ", ".join([f"{i.get('amount', '')} {i.get('unit', '')} {i.get('ingredient', '')}".strip() for i in c.get("ingredients", [])])
    doc_text = f"Nombre: {c.get('name')}. Categoría: {c.get('category')}. Ingredientes: {ing_str}. Preparación: {c.get('preparation', '')} Decoración: {c.get('garnish', '')}"
    documents.append({
        "slug": c.get("slug", ""),
        "name": c.get("name", ""),
        "category": c.get("category", ""),
        "text": doc_text
    })

# Cargar Modelo de Embeddings e Indexar Vectores
print("Cargando modelo local de embeddings...")
embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
doc_texts = [d["text"] for d in documents]
doc_embeddings = embedder.encode(doc_texts, convert_to_tensor=True)

# Cargar Modelo Generativo Local (SLM)
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct" 
print(f"Cargando modelo LLM local ({MODEL_NAME})...")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float32 if not torch.cuda.is_available() else torch.float16,
    device_map="auto"
)
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

# ------------------------------------------------------------------------------
# 2. MODELOS DE DATOS (PYDANTIC)
# ------------------------------------------------------------------------------

class RAGQueryRequest(BaseModel):
    question: str = Field(..., example="¿Qué cóctel refrescante con gin me recomiendas?")

class SourceMetadata(BaseModel):
    slug: str
    name: str
    category: str
    content: str

class RAGResponse(BaseModel):
    question: str
    answer: str
    cocktails: List[dict]

# ------------------------------------------------------------------------------
# 3. ENDPOINTS REST CONVENCIONALES
# ------------------------------------------------------------------------------

@app.get("/api/v1/cocktails", summary="Listar todos los cócteles")
def get_cocktails(
    name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    ingredient: Optional[str] = Query(None)
):
    results = COCKTAILS_DB

    if name:
        results = [c for c in results if normalize_string(name) in normalize_string(c["name"])]
    if category:
        results = [c for c in results if normalize_string(category) in normalize_string(c["category"])]
    if ingredient:
        results = [
            c for c in results 
            if any(normalize_string(ingredient) in normalize_string(i["ingredient"]) for i in c.get("ingredients", []))
        ]

    return {"total": len(results), "cocktails": results}


@app.get("/api/v1/cocktails/search", summary="Búsqueda por nombre")
def search_cocktails(q: str = Query(...)):
    matches = [c for c in COCKTAILS_DB if normalize_string(q) in normalize_string(c["name"])]
    return {"total": len(matches), "cocktails": matches}


@app.get("/api/v1/cocktails/category/{category_name}", summary="Filtrar por categoría")
def get_by_category(category_name: str):
    target = normalize_string(category_name).replace("-", " ")
    matches = [c for c in COCKTAILS_DB if target in normalize_string(c["category"])]
    return {"category": category_name, "total": len(matches), "cocktails": matches}


@app.get("/api/v1/cocktails/ingredient/{ingredient_name}", summary="Filtrar por ingrediente")
def get_by_ingredient(ingredient_name: str):
    target = normalize_string(ingredient_name)
    matches = [
        c for c in COCKTAILS_DB 
        if any(target in normalize_string(i["ingredient"]) for i in c.get("ingredients", []))
    ]
    return {"ingredient": ingredient_name, "total": len(matches), "cocktails": matches}


@app.get("/api/v1/cocktails/{slug}", summary="Obtener detalle por slug")
def get_cocktail_by_slug(slug: str):
    cocktail = next((c for c in COCKTAILS_DB if c.get("slug") == slug), None)
    if not cocktail:
        raise HTTPException(status_code=404, detail="Cóctel no encontrado.")
    return cocktail

# ------------------------------------------------------------------------------
# 4. ENDPOINT RAG LOCAL (BÚSQUEDA COSENO + INFERENCIA LOCAL CON GUARDRAILS)
# ------------------------------------------------------------------------------

def _detect_ingredient(question: str) -> str | None:
    """Detecta dinámicamente un ingrediente en la pregunta usando el índice
    construido a partir de los datos del scraping (INGREDIENT_WORD_INDEX)."""
    lower_q = question.lower()
    question_words = set(re.findall(r"\w+", lower_q))

    for word in question_words:
        if word in INGREDIENT_WORD_INDEX:
            return word

    m = re.search(r"(?:con|with)\s+(\w+)", lower_q)
    if m:
        candidate = m.group(1)
        if candidate in INGREDIENT_WORD_INDEX:
            return candidate

    return None


@app.post("/api/v1/cocktails/rag", response_model=RAGResponse, summary="Consulta RAG local")
def query_rag(request: RAGQueryRequest):
    try:
        # 1. Calcular embedding de la pregunta y validar similitud con la BD de cócteles
        query_embedding = embedder.encode(request.question, convert_to_tensor=True)
        cos_scores = torch.nn.functional.cosine_similarity(query_embedding, doc_embeddings)
        max_score = torch.max(cos_scores).item()

        # GUARDRAIL 1: Si la similitud máxima es menor a 0.30, la pregunta no trata de cócteles
        if max_score < 0.30:
            return RAGResponse(
                question=request.question,
                answer=OUT_OF_DOMAIN_RESPONSE,
                cocktails=[]
            )

        # 2. Detectar si la pregunta especifica un ingrediente en particular
        asked_ingredient = _detect_ingredient(request.question)

        if asked_ingredient:
            filtered_cocktails = [
                c for c in COCKTAILS_DB
                if any(
                    asked_ingredient in normalize_string(i.get("ingredient", ""))
                    for i in c.get("ingredients", [])
                )
            ]
        else:
            top_results = torch.topk(cos_scores, k=min(10, len(COCKTAILS_DB)))
            filtered_cocktails = [COCKTAILS_DB[idx.item()] for idx in top_results.indices]

        if not filtered_cocktails:
            return RAGResponse(
                question=request.question,
                answer=OUT_OF_DOMAIN_RESPONSE,
                cocktails=[]
            )

        # 3. Construir contexto limitando a los 5 más relevantes
        filtered_names = {c.get("name") for c in filtered_cocktails[:5]}
        context = "\n---\n".join(
            d["text"] for d in documents if d["name"] in filtered_names
        )

        # GUARDRAIL 2: Prompt estructurado en formato ChatML oficial para Qwen
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente virtual especializado EXCLUSIVAMENTE en coctelería y recetas de bebidas.\n"
                    "REGLAS ESTRITAS:\n"
                    "1. Responde ÚNICAMENTE basándote en la información del contexto proporcionado.\n"
                    "2. Si la pregunta trata sobre programación (Java, Python, C++, etc.), matemáticas o cualquier tema ajeno a los cócteles, responde exactamente: "
                    f"'{OUT_OF_DOMAIN_RESPONSE}'\n"
                    "3. No generes código fuente de programación bajo ninguna circunstancia."
                )
            },
            {
                "role": "user",
                "content": f"Contexto:\n{context}\n\nPregunta: {request.question}"
            }
        ]

        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # 4. Inferencia con baja temperatura para evitar alucinaciones/desvíos
        output = generator(
            formatted_prompt,
            max_new_tokens=150,
            temperature=0.01,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

        generated_text = output[0]["generated_text"]

        # Parsear la respuesta descartando el prompt del sistema y del usuario
        if "<|im_start|>assistant\n" in generated_text:
            answer = generated_text.split("<|im_start|>assistant\n")[-1].replace("<|im_end|>", "").strip()
        else:
            answer = generated_text[len(formatted_prompt):].strip()

        # GUARDRAIL 3: Post-filtro para detener respuestas que intenten incluir sintaxis de código
        code_keywords = ["public class", "import java", "void main", "```java", "```python", "System.out"]
        if any(kw in answer for kw in code_keywords):
            answer = OUT_OF_DOMAIN_RESPONSE

        return RAGResponse(
            question=request.question,
            answer=answer,
            cocktails=filtered_cocktails if answer != OUT_OF_DOMAIN_RESPONSE else [],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el RAG local: {str(e)}")

# ------------------------------------------------------------------------------
# EJECUCIÓN DEL SERVIDOR
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
