FROM python:3.11-slim AS docs-builder

WORKDIR /build

# Install MkDocs and dependencies
COPY docs/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy docs content and configuration
COPY mkdocs.yml .
COPY docs ./docs

# Build MkDocs site
RUN mkdocs build

# Frontend builder stage
FROM node:20-slim AS frontend-builder

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy frontend source code
COPY frontend/. .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built frontend
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

    # Copy built docs
    COPY --from=docs-builder /build/site /usr/share/nginx/html/docs

# Copy nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
