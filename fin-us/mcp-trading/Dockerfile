# MCP Trading Server Dockerfile
FROM node:20-slim

WORKDIR /app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Since MCP Trading is called via stdio, it doesn't strictly need a CMD.
CMD ["node", "index.js"]
