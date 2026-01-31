#!/bin/bash
# Phase 1 validation tests
# Tests that Task 1.1 (Backwards Compatibility) works correctly
# Default is TCP_STREAM, -M enables OMNI

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"

echo "=== Phase 1 Task 1.1 Validation Tests ==="
echo "Testing backwards compatibility (TCP_STREAM default, -M for OMNI)"
echo ""

# Check if build exists
if [ ! -d "${BUILD_DIR}" ]; then
    echo "❌ Build directory not found. Run ./dev/scripts/build.sh first."
    exit 1
fi

cd "${BUILD_DIR}"

if [ ! -f "src/netperf" ] || [ ! -f "src/netserver" ]; then
    echo "❌ Binaries not found. Run ./dev/scripts/build.sh first."
    exit 1
fi

# Start netserver
echo "Starting netserver..."
./src/netserver -D -p 12865 &
NETSERVER_PID=$!
sleep 2

cleanup() {
    echo ""
    echo "Cleaning up..."
    if kill -0 $NETSERVER_PID 2>/dev/null; then
        kill $NETSERVER_PID
        wait $NETSERVER_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo ""
echo "=== Test 1: Default test is TCP_STREAM (backwards compatibility) ==="
OUTPUT=$(./src/netperf -H localhost -l 1 2>&1)
if echo "$OUTPUT" | grep -qi "TCP STREAM"; then
    echo "✅ PASS: Default test is TCP_STREAM"
else
    echo "❌ FAIL: Default test is not TCP_STREAM"
    echo "Output: $OUTPUT"
    exit 1
fi

echo ""
echo "=== Test 2: -M flag enables OMNI ==="
OUTPUT=$(./src/netperf -H localhost -M -l 1 2>&1)
if echo "$OUTPUT" | grep -qi "OMNI"; then
    echo "✅ PASS: -M flag enables OMNI"
else
    echo "❌ FAIL: -M flag did not enable OMNI"
    echo "Output: $OUTPUT"
    exit 1
fi

echo ""
echo "=== Test 3: Explicit TCP_STREAM still works ==="
if ./src/netperf -H localhost -t TCP_STREAM -l 1 >/dev/null 2>&1; then
    echo "✅ PASS: Explicit TCP_STREAM works"
else
    echo "❌ FAIL: TCP_STREAM test failed"
    exit 1
fi

echo ""
echo "=== Test 4: Backward compatibility - TCP_RR ==="
if ./src/netperf -H localhost -t TCP_RR -l 1 >/dev/null 2>&1; then
    echo "✅ PASS: TCP_RR still works via -t option"
else
    echo "❌ FAIL: TCP_RR test failed"
    exit 1
fi

echo ""
echo "=== Test 5: Backward compatibility - UDP_STREAM ==="
if ./src/netperf -H localhost -t UDP_STREAM -l 1 >/dev/null 2>&1; then
    echo "✅ PASS: UDP_STREAM still works via -t option"
else
    echo "❌ FAIL: UDP_STREAM test failed"
    exit 1
fi

echo ""
echo "=== Test 6: UDP_RR ==="
if ./src/netperf -H localhost -t UDP_RR -l 1 >/dev/null 2>&1; then
    echo "✅ PASS: UDP_RR still works"
else
    echo "❌ FAIL: UDP_RR test failed"
    exit 1
fi

echo ""
echo "=== Test 7: OMNI explicit invocation ==="
if ./src/netperf -H localhost -t OMNI -l 1 >/dev/null 2>&1; then
    echo "✅ PASS: Explicit OMNI test works"
else
    echo "❌ FAIL: Explicit OMNI test failed"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ All Phase 1 Task 1.1 tests PASSED!"
echo "========================================="
echo ""
echo "Summary:"
echo "  - Default test is TCP_STREAM (backwards compatible)"
echo "  - -M flag enables modern OMNI test"
echo "  - All classic test names still work"
echo "  - Full backwards compatibility maintained"
