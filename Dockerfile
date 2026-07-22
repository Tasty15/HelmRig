FROM python:3.14-slim

WORKDIR /app

# Installera systemberoenden
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Installera rtk, headroom, composio
RUN curl -fsSL https://rtk.dev/install | bash && \
    curl -fsSL https://headroom.dev/install | bash && \
    curl -fsSL https://composio.dev/install | bash

# Kopiera och installera Python-paket
COPY agents/pyproject.toml agents/
COPY agents/agentkit/ agents/agentkit/
RUN pip install --no-cache-dir -e agents/ composio-core

# Kopiera resten
COPY agents/ agents/
COPY .env .env 2>/dev/null || true

# Se till att CLI-verktygen finns i PATH
ENV PATH="/root/.local/bin:${PATH}"

# Portar: dashboard (5050)
EXPOSE 5050

# Default: starta dashboard + overlord
CMD ["sh", "-c", "python3 agents/.overlord/overlord.py & exec python3 agents/dashboard/app.py"]
