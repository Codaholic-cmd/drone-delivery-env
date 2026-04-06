FROM python:3.11-slim

# HF Spaces runs as a non-root user — create one
RUN useradd -m -u 1000 user
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# HF Spaces REQUIRES port 7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

USER user

# Use port 7860 for HF Spaces
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
