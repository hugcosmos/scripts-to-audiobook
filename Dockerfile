# ============================================
# Scripts to Audiobook - Docker Image
# ============================================

# ---- Frontend Build Stage ----
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install frontend dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend code and build
COPY frontend/ ./
COPY catalog/ ../catalog/
RUN npm run build

# ---- Production Stage ----
FROM python:3.11-slim AS production

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    edge-tts \
    fastapi \
    uvicorn \
    pydub \
    python-dotenv \
    aiosqlite \
    websocket-client

# Copy backend code
COPY backend/ ./backend/
COPY catalog/ ./catalog/

# Copy frontend build artifacts
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
COPY --from=frontend-builder /app/frontend/server ./frontend/server
COPY --from=frontend-builder /app/frontend/package*.json ./frontend/

# Install frontend production dependencies
RUN cd frontend && npm ci --production && npm cache clean --force

# Create necessary directories
RUN mkdir -p data/outputs data/outputs_test logs

# Create empty .env file (will be overridden by environment variables or volume mount)
RUN touch .env

# Expose ports
EXPOSE 8000 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Startup script
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
