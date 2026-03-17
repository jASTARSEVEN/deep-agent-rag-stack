FROM node:20-alpine

WORKDIR /app

# Copy package files first to leverage Docker cache
COPY apps/web/package.json apps/web/package-lock.json* /app/

# Install dependencies
RUN npm install

# Copy the rest of the source code
COPY apps/web /app

EXPOSE 3000

CMD ["npm", "run", "dev"]
