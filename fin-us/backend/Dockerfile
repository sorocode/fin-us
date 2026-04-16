# SPDX-FileCopyrightText: Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Build context: fin-us/ (parent of this file). Python deps: uv + uv.lock.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /uvx /bin/

WORKDIR /app

COPY mcp-news/package*.json ./mcp-news/
WORKDIR /app/mcp-news
RUN npm ci && npx playwright install --with-deps chromium

WORKDIR /app
COPY mcp-trading/package*.json ./mcp-trading/
WORKDIR /app/mcp-trading
RUN npm ci

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev

WORKDIR /app
COPY . .

WORKDIR /app/backend
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
