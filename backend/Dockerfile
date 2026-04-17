# Python FastAPI backend Dockerfile
FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Install MCP dependencies
COPY mcp-news/package*.json ./mcp-news/
RUN cd ./mcp-news && npm install

COPY mcp-trading/package*.json ./mcp-trading/
RUN cd ./mcp-trading && npm install

# 2. Install Playwright & System dependencies (must run inside mcp-news; playwright is not a root dependency)
RUN cd ./mcp-news && npx playwright install --with-deps chromium

# 3. Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# 4. Copy source code
COPY . .

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
