FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# slide_generator.py caches platform logos in /app/assets at runtime.
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000

# One worker keeps the in-process caches and rate limiters consistent.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
