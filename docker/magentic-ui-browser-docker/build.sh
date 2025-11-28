#!/bin/bash

IMAGE_NAME=magentic-ui-browser
IMAGE_VERSION=0.0.2
REGISTRY=ghcr.io/microsoft

# Check if --push flag is provided or PUSH environment variable is set
PUSH_FLAG=""
if [[ "$1" == "--push" ]] || [[ "${PUSH}" == "true" ]]; then
    PUSH_FLAG="--push"
    echo "Building and pushing images..."
else
    echo "Building images locally..."
fi

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "${REGISTRY}/${IMAGE_NAME}:latest" \
    -t "${REGISTRY}/${IMAGE_NAME}:${IMAGE_VERSION}" \
    ${PUSH_FLAG} \
    .
