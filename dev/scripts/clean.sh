#!/bin/bash
# Clean build artifacts
# Usage: ./dev/scripts/clean.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"

if [ -d "${BUILD_DIR}" ]; then
    echo "Removing build directory: ${BUILD_DIR}"
    rm -rf "${BUILD_DIR}"
    echo "Build directory removed."
else
    echo "Build directory does not exist: ${BUILD_DIR}"
fi

echo "Clean complete."
