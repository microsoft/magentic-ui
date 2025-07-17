#!/bin/bash

CWD="$(pwd)"
if [[ "${CWD##*/}" != "docker" ]]; then
    echo "Error: Must run this script from the docker folder."
    exit 1
fi

# Run both build scripts in parallel in their respective directories
(
    cd magentic-ui-browser-docker && sh build.sh
) &

(
    cd magentic-ui-python-env && sh build.sh
) &

wait
echo "Both builds completed."