FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

COPY . .

RUN mkdir -p logs

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "portals.portal_a.main:app", "--host", "0.0.0.0", "--port", "8000"]