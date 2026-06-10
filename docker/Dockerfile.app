# Stage 1: Build Vue frontend
FROM node:22-alpine AS frontend-builder
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV NO_PROXY=$NO_PROXY

WORKDIR /build
COPY autofe-frontend/package.json autofe-frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps && npm install splitpanes --legacy-peer-deps
COPY autofe-frontend/ ./
RUN npm run build-only

# Stage 2: Application image
FROM python:3.9-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV NO_PROXY=$NO_PROXY

# Install system dependencies
# g++ and postgresql-server-dev-14 are needed for runtime C++ UDF compilation
# graphviz is needed by pygraphviz
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    g++ \
    libpq-dev \
    libarmadillo-dev \
    libopenblas-dev \
    libmlpack-dev \
    libgomp1 \
    graphviz \
    graphviz-dev \
    curl \
    gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pg-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pg-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    postgresql-server-dev-14 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (torch CPU-only to keep image size manageable)
COPY requirements-docker.txt /adda/requirements-docker.txt
RUN pip install --no-cache-dir \
    flask==2.3.3 \
    flask-cors==4.0.0 \
    flask-socketio==5.3.6 \
    simple-websocket==1.0.0 \
    && pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip freeze | grep -E '^torch==' > /tmp/constraints.txt \
    && pip install --no-cache-dir -r /adda/requirements-docker.txt -c /tmp/constraints.txt

# Copy Vue frontend build output
COPY --from=frontend-builder /build/dist /adda/static

# Copy application source code
COPY src/ /adda/src/
COPY frontend/ /adda/frontend/
COPY pd2sql/ /adda/pd2sql/

# Copy and configure Nginx
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default && \
    mkdir -p /adda/static && \
    echo "daemon off;" >> /etc/nginx/nginx.conf

# Create directories
RUN mkdir -p /adda/test/store /adda/dataset/task /adda/src/clib/lib

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
WORKDIR /adda

ENTRYPOINT ["/entrypoint.sh"]
