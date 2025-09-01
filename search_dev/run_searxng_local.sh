# docker run --name searxng -d \
#     -p 8888:8080 \
#     -v "./searxng/config/:/etc/searxng/" \
#     -v "./searxng/data/:/var/cache/searxng/" \
#     docker.io/searxng/searxng:latest



#!/bin/bash

# Clean up existing containers and network
echo "Cleaning up existing containers and network..."
docker stop valkey searxng 2>/dev/null || true
docker rm valkey searxng 2>/dev/null || true
docker network rm searx-net 2>/dev/null || true

# 1) Create network
echo "Creating Docker network..."
if ! docker network create searx-net; then
    echo "Failed to create network"
    exit 1
fi

# 2) Run Valkey (Redis compatible) - no port binding needed since it communicates internally
echo "Starting Valkey container..."
if ! docker run -d --name valkey \
  --network searx-net \
  --restart unless-stopped \
  valkey/valkey:latest; then
    echo "Failed to start Valkey container"
    exit 1
fi

docker run -d --name searxng \
  --network searx-net \
  -p 8888:8080 \
  -v "$PWD/searxng/config/:/etc/searxng/:ro" \
  -v "$PWD/searxng/data/:/var/cache/searxng/" \
  -e SEARXNG_LIMITER=1 \
  -e SEARXNG_PUBLIC_INSTANCE=false \
  -e SEARXNG_BASE_URL="http://localhost:8888/" \
  --ulimit nofile=65535:65535 \
  docker.io/searxng/searxng:latest

echo "Setup complete!"
echo "SearXNG should be available at: http://localhost:8888"
echo "Valkey (Redis) is running internally for SearXNG"

