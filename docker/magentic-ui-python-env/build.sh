#!/bin/bash

IMAGE_NAME=magentic-ui-python-image
IMAGE_VERSION=0.0.1
REGISTRY=tangent

# Check if --push flag is provided or PUSH environment variable is set
PUSH_FLAG=""
OUTPUT_FLAG=""
if [[ "$1" == "--push" ]] || [[ "${PUSH}" == "true" ]]; then
    PUSH_FLAG="--push"
    echo "Building and pushing images..."
    # No output flag needed when pushing
else
    echo "Building images locally..."
    OUTPUT_FLAG="--output=type=docker"
fi

# --platform linux/amd64,linux/arm64 \
docker buildx build \
    --platform linux/arm64 \
    -t "${REGISTRY}/${IMAGE_NAME}:latest" \
    -t "${REGISTRY}/${IMAGE_NAME}:${IMAGE_VERSION}" \
    ${PUSH_FLAG} \
    ${OUTPUT_FLAG} \
    .
