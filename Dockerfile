# The Girl House — image Docker (Flask + Gunicorn)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data (SQLite) & upload gambar disimpan di volume agar tidak hilang saat rebuild
RUN mkdir -p /app/instance /app/app/static/uploads

EXPOSE 8000

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
