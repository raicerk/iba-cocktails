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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUT_OF_DOMAIN_RESPONSE = "Lo siento, solo puedo responder preguntas relacionadas con el catálogo de coctelería y sus ingredientes."

OUT_OF_DOMAIN_KEYWORDS = [
    "java", "python", "javascript", "c++", "c#", "php", "sql", "html", "css",
    "código", "codigo", "algoritmo", "función", "funcion", "clase", "array",
    "matemática", "matematica", "ecuación", "ecuacion", "ejercicio de"
]

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

def contains_exact_word(target_word: str, text: str) -> bool:
    """Verifica si target_word existe como palabra completa dentro del texto,
    evitando coincidencias parciales como 'citron' o 'strong' para 'ron'."""
    pattern = r'\b' + re.escape(normalize_string(target_word)) + r'\b'
    return bool(re.search(pattern, normalize_string(text)))

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

print("Cargando modelo local de embeddings...")
embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
doc_texts = [d["text"] for d in documents]
doc_embeddings = embedder.encode(doc_texts, convert_to_tensor=True)

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
# 3. ENDPOINTS REST CONVENCIONALES (CORREGIDOS CON PALABRA EXACTA)
# ------------------------------------------------------------------------------

@app.get("/api/v1/cocktails", summary="Listar todos los cócteles")
def get_cocktails(
    name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    ingredient: Optional[str] = Query(None)
):
    results = COCKTAILS_DB

    if name:
        results = [c for c in results if contains_exact_word(name, c["name"])]
    if category:
        results = [c for c in results if contains_exact_word(category, c["category"])]
    if ingredient:
        results = [
            c for c in results 
            if any(contains_exact_word(ingredient, i.get("ingredient", "")) for i in c.get("ingredients", []))
        ]

    return {"total": len(results), "cocktails": results}


@app.get("/api/v1/cocktails/search", summary="Búsqueda por nombre")
def search_cocktails(q: str = Query(...)):
    matches = [c for c in COCKTAILS_DB if contains_exact_word(q, c["name"])]
    return {"total": len(matches), "cocktails": matches}


@app.get("/api/v1/cocktails/category/{category_name}", summary="Filtrar por categoría")
def get_by_category(category_name: str):
    target = category_name.replace("-", " ")
    matches = [c for c in COCKTAILS_DB if contains_exact_word(target, c["category"])]
    return {"category": category_name, "total": len(matches), "cocktails": matches}


@app.get("/api/v1/cocktails/ingredient/{ingredient_name}", summary="Filtrar por ingrediente")
def get_by_ingredient(ingredient_name: str):
    matches = [
        c for c in COCKTAILS_DB 
        if any(contains_exact_word(ingredient_name, i.get("ingredient", "")) for i in c.get("ingredients", []))
    ]
    return {"ingredient": ingredient_name, "total": len(matches), "cocktails": matches}


@app.get("/api/v1/cocktails/{slug}", summary="Obtener detalle por slug")
def get_cocktail_by_slug(slug: str):
    cocktail = next((c for c in COCKTAILS_DB if c.get("slug") == slug), None)
    if not cocktail:
        raise HTTPException(status_code=404, detail="Cóctel no encontrado.")
    return cocktail

# ------------------------------------------------------------------------------
# 4. ENDPOINT RAG LOCAL (MATCH EXACTO DE INGREDIENTES)
# ------------------------------------------------------------------------------

def _detect_ingredient(question: str) -> str | None:
    """Detecta ingredientes en la pregunta mediante limites de palabra exactos."""
    question_words = set(re.findall(r"\b\w+\b", question.lower()))

    # Manejar sinónimos/traducciones comunes
    if "ron" in question_words or "rum" in question_words:
        return "rum"

    for word in question_words:
        if word in INGREDIENT_WORD_INDEX:
            return word

    m = re.search(r"\b(?:con|with)\s+(\w+)\b", question.lower())
    if m:
        candidate = m.group(1)
        if candidate in INGREDIENT_WORD_INDEX:
            return candidate

    return None


@app.post("/api/v1/cocktails/rag", response_model=RAGResponse, summary="Consulta RAG local")
def query_rag(request: RAGQueryRequest):
    try:
        lower_question = request.question.lower()

        # GUARDRAIL 0: Intercepta código/programación directo
        if any(keyword in lower_question for keyword in OUT_OF_DOMAIN_KEYWORDS):
            return RAGResponse(
                question=request.question,
                answer=OUT_OF_DOMAIN_RESPONSE,
                cocktails=[]
            )

        # 1. Similitud Vectorial
        query_embedding = embedder.encode(request.question, convert_to_tensor=True)
        cos_scores = torch.nn.functional.cosine_similarity(query_embedding, doc_embeddings)
        max_score = torch.max(cos_scores).item()

        if max_score < 0.25:
            return RAGResponse(
                question=request.question,
                answer=OUT_OF_DOMAIN_RESPONSE,
                cocktails=[]
            )

        # 2. Filtrado de Cócteles con Verificación Exacta de Palabras
        asked_ingredient = _detect_ingredient(request.question)

        if asked_ingredient:
            # Aceptar "rum" o "ron" interchangeablemente
            target_words = ["rum", "ron"] if asked_ingredient in ["rum", "ron"] else [asked_ingredient]
            
            filtered_cocktails = [
                c for c in COCKTAILS_DB
                if any(
                    any(contains_exact_word(tw, i.get("ingredient", "")) for tw in target_words)
                    for i in c.get("ingredients", [])
                )
            ]
        else:
            top_results = torch.topk(cos_scores, k=min(5, len(COCKTAILS_DB)))
            filtered_cocktails = [COCKTAILS_DB[idx.item()] for idx in top_results.indices]

        if not filtered_cocktails:
            return RAGResponse(
                question=request.question,
                answer=f"No encontré cócteles en el catálogo que contengan el ingrediente solicitado.",
                cocktails=[]
            )

        # 3. Formatear Contexto Limpio
        filtered_names = {c.get("name") for c in filtered_cocktails[:5]}
        context = "\n---\n".join(
            d["text"] for d in documents if d["name"] in filtered_names
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un bartender experto y amigable. Tu función es recomendar cócteles e indicar sus ingredientes "
                    "y preparación basándote EXCLUSIVAMENTE en el contexto provisto.\n"
                    "Responde con tono servicial, detallando la receta recomendada."
                )
            },
            {
                "role": "user",
                "content": f"Contexto disponible:\n{context}\n\nPregunta del cliente: {request.question}"
            }
        ]

        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
        eos_ids = [tokenizer.eos_token_id]
        if im_end_id is not None:
            eos_ids.append(im_end_id)

        output = generator(
            formatted_prompt,
            max_new_tokens=400,
            temperature=0.3,
            top_p=0.9,
            repetition_penalty=1.1,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=eos_ids,
        )

        generated_text = output[0]["generated_text"]

        if "<|im_start|>assistant\n" in generated_text:
            answer = generated_text.split("<|im_start|>assistant\n")[-1].replace("<|im_end|>", "").strip()
        else:
            answer = generated_text[len(formatted_prompt):].strip()

        code_keywords = ["public class", "import java", "void main", "```java", "```python", "system.out"]
        if any(kw in answer.lower() for kw in code_keywords):
            answer = OUT_OF_DOMAIN_RESPONSE

        return RAGResponse(
            question=request.question,
            answer=answer,
            cocktails=filtered_cocktails,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el RAG local: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)