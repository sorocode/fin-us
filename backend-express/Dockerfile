# Express Backend Dockerfile
FROM node:20-slim

WORKDIR /app

# 1. Install main backend and MCP dependencies
COPY backend-express/package*.json ./backend-express/
RUN cd ./backend-express && npm install

COPY mcp-news/package*.json ./mcp-news/
RUN cd ./mcp-news && npm install

COPY mcp-trading/package*.json ./mcp-trading/
RUN cd ./mcp-trading && npm install

# 2. Install Playwright & System dependencies
RUN npx playwright install --with-deps chromium

# 3. Copy source code and build
COPY . .
RUN cd ./backend-express && npm run build

WORKDIR /app/backend-express
EXPOSE 3000

# Command to run the application
CMD ["npm", "run", "dev"]
