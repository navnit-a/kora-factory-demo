#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="$(git rev-parse --short HEAD)"
docker build -t "localhost:5001/factory-tools:latest" -t "localhost:5001/factory-tools:${TAG}" .
docker push --quiet "localhost:5001/factory-tools:latest"
docker push --quiet "localhost:5001/factory-tools:${TAG}"

uv run python scripts/render-secrets.py
kubectl apply -f deploy/generated/secrets.yaml
kubectl apply -k deploy/tools
if [ -f deploy/generated/github-connection.yaml ]; then
  kubectl apply -f deploy/generated/github-connection.yaml
fi

for name in trello telegram transport places; do
  kubectl rollout restart "deployment/tools-${name}" -n kora-tenant-example >/dev/null
done
for name in trello telegram transport places; do
  kubectl rollout status "deployment/tools-${name}" -n kora-tenant-example --timeout=180s
done
