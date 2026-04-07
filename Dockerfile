FROM python:3.11-slim

# Install uv 
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# HF Spaces requirements
RUN useradd -m -u 1000 user
WORKDIR /app

# Install curl for the validator's healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy package config first
COPY --chown=user pyproject.toml uv.lock ./

# Install dependencies into the system python
RUN uv pip install --system --frozen .

# Copy the rest of your code
COPY --chown=user . .

# Final install to register the 'server' entry point
RUN uv pip install --system --frozen .

EXPOSE 7860
USER user

# This command now works because of [project.scripts] in pyproject.toml
CMD ["server"]
