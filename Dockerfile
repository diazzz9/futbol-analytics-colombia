FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# La demo pública usa SQLite construido en la imagen; en local se usa PostgreSQL con docker compose
ENV DATABASE_URL=sqlite:////app/futbol.db
RUN python src/load_db.py
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
