# Object Paint Agent - CPU-only, production image
FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV (minimal for headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Prefer uv for install; fallback to pip
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system -e . \
    || pip install --no-cache-dir -e .

COPY app/ ./app/
COPY scripts/ ./scripts/

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "python -m app.main --host 0.0.0.0 --port ${PORT}"]
