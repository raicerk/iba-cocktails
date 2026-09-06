FROM python:3.10-slim

# Evitar que Python escriba archivos .pyc y forzar logs sin buffer
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

# Instalar dependencias del sistema necesarias para PyTorch/Transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente y la base de datos
COPY api/main.py .


EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]