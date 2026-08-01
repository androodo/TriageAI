FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copy project
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
