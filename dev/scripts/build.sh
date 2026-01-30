#!/bin/bash
# Build script for netperf development
# Usage: ./dev/scripts/build.sh [configure-options]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"

echo "=== Netperf Development Build ==="
echo "Project root: ${PROJECT_ROOT}"
echo "Build directory: ${BUILD_DIR}"

# Create build directory
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# Run configure from build directory
echo ""
echo "=== Running configure ==="
"${PROJECT_ROOT}/configure" "$@"

# Build
echo ""
echo "=== Building ==="
make -j$(nproc)

echo ""
echo "=== Build complete ==="
echo "Binaries are in: ${BUILD_DIR}/src/"
echo ""
echo "To run tests:"
echo "  cd ${BUILD_DIR}"
echo "  ./src/netserver -D &"
echo "  ./src/netperf -H localhost"
