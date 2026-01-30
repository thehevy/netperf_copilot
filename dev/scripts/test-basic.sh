#!/bin/bash
# Basic netperf test suite
# Usage: ./dev/scripts/test-basic.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"

if [ ! -d "${BUILD_DIR}" ]; then
    echo "Error: Build directory not found. Run ./dev/scripts/build.sh first."
    exit 1
fi

cd "${BUILD_DIR}"

if [ ! -f "src/netperf" ] || [ ! -f "src/netserver" ]; then
    echo "Error: netperf binaries not found. Run ./dev/scripts/build.sh first."
    exit 1
fi

echo "=== Starting Netperf Test Suite ==="
echo ""

# Start netserver in background
echo "Starting netserver..."
./src/netserver -D -p 12865 &
NETSERVER_PID=$!
sleep 2

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Cleaning up..."
    if kill -0 $NETSERVER_PID 2>/dev/null; then
        kill $NETSERVER_PID
        wait $NETSERVER_PID 2>/dev/null || true
    fi
    echo "Tests complete."
}
trap cleanup EXIT

# Run basic tests
echo "=== Test 1: TCP_STREAM ==="
./src/netperf -H localhost -p 12865 -t TCP_STREAM -l 5

echo ""
echo "=== Test 2: TCP_RR ==="
./src/netperf -H localhost -p 12865 -t TCP_RR -l 5

echo ""
echo "=== Test 3: UDP_STREAM ==="
./src/netperf -H localhost -p 12865 -t UDP_STREAM -l 5

echo ""
echo "=== All tests passed ==="
