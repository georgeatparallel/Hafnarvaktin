FROM python:3.12-slim

WORKDIR /app

# build tools needed by torch wheel resolution; trimmed after pip install
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-warm the embedding model so the first tool call doesn't pay download cost
RUN python -c "from sentence_transformers import SentenceTransformer; \
               SentenceTransformer('intfloat/multilingual-e5-base')"

COPY server.py ./

CMD ["python", "-u", "server.py"]
