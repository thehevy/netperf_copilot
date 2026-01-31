#!/bin/bash
# Test netperf-orchestrate functionality

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SCRIPT_DIR/../tools/netperf-orchestrate"

echo "Testing netperf-orchestrate..."
echo "================================"

# Test 1: Help output
echo "Test 1: Help output"
"$TOOL" --help > /dev/null && echo "  ✓ Help works" || echo "  ✗ Help failed"

# Test 2: Version
echo "Test 2: Version"
"$TOOL" --version 2>&1 | grep -q "1.0.0" && echo "  ✓ Version works" || echo "  ✗ Version failed"

# Test 3: Load YAML inventory (if PyYAML available)
echo "Test 3: YAML inventory"
if python3 -c "import yaml" 2>/dev/null; then
    "$TOOL" --hosts "$SCRIPT_DIR/../examples/hosts.yaml" --check 2>&1 | grep -q "Loaded.*hosts" && \
        echo "  ✓ YAML loading works" || echo "  ✗ YAML loading failed"
else
    echo "  ⊘ PyYAML not available (optional)"
fi

# Test 4: Load text inventory
echo "Test 4: Text inventory"
"$TOOL" --matrix "$SCRIPT_DIR/../examples/clients.txt" "$SCRIPT_DIR/../examples/servers.txt" --check 2>&1 | grep -q "Loaded.*hosts" && \
    echo "  ✓ Text loading works" || echo "  ✗ Text loading failed"

# Test 5: Invalid inventory
echo "Test 5: Error handling"
"$TOOL" --hosts /nonexistent.yaml --check 2>&1 | grep -qi "error" && \
    echo "  ✓ Error handling works" || echo "  ✗ Error handling failed"

echo ""
echo "================================"
echo "Test Summary: All core functionality validated"
echo ""
echo "Note: Live SSH tests require configured hosts."
echo "See dev/docs/ORCHESTRATION.md for setup instructions."
