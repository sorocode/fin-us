# MCP News Server Dockerfile
FROM node:20-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm install

# Install Playwright browsers
RUN npx playwright install --with-deps chromium

# Copy source code
COPY . .

# Since MCP News is called via stdio, it doesn't strictly need a CMD 
# if it's just meant to be a library/script for other containers.
# But if it's meant to be its own service (over network), it would need one.
# For now, let's just make it available.
CMD ["node", "index.js"]
