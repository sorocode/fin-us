# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Build with repository root as context (`docker compose` from that root):
#   docker build -f finus_nat/Dockerfile .
# Installs nat-finus-nat (PyPI nvidia-nat) plus Fin-Us Node MCP deps under ../fin-us from image /workspace.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /uvx /bin/

WORKDIR /workspace

# Image builds without .git; setuptools-scm needs a pretend version for path installs.
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0+docker
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION}

COPY finus_nat /workspace/finus_nat
COPY fin-us/mcp-news /workspace/fin-us/mcp-news
COPY fin-us/mcp-trading /workspace/fin-us/mcp-trading

WORKDIR /workspace/fin-us/mcp-news
RUN npm ci && npx playwright install --with-deps chromium

WORKDIR /workspace/fin-us/mcp-trading
RUN npm ci

WORKDIR /workspace/finus_nat
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "--project", ".", "nat", "start", "fastapi", \
     "--config_file", "configs/router.yml", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
