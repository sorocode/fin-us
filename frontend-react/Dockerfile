# Vite Frontend Dockerfile
FROM node:20-slim

WORKDIR /app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Exposure port
EXPOSE 5173

# Command to run the application (use dev script for hot reload)
# Vite needs --host to be accessible from outside the container
CMD ["npm", "run", "dev", "--", "--host"]
