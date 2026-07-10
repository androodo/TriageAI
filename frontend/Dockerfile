FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy project
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
