#!/bin/bash
# === METADATA_HEADER_START ===
# File: dev/tests/quick-test.sh
# Created Date: 2026-01-30
# Last Updated Date: 2026-11-06
# Version: 2.0.0
# Status: Active
# Target Scope: Phase 3-7 OMNI C Engine & Python Automation Integration Smoke Suite
# Summary: Executes a 5-step live integration smoke test across netperf OMNI, netperf-multi, netperf_stats.py, netperf-profile, and netperf-template.
# === METADATA_HEADER_END ===

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SERVER="${1:-192.168.18.2}"
DURATION="${2:-3}"

if [ -x "$REPO_ROOT/src/netperf" ]; then
  NP="$REPO_ROOT/src/netperf"
elif [ -x "/opt/netperf/build/src/netperf" ]; then
  NP="/opt/netperf/build/src/netperf"
else
  NP="$(command -v netperf)"
fi

if [ -d "$REPO_ROOT/dev/tools" ]; then
  TOOLS="$REPO_ROOT/dev/tools"
else
  TOOLS="/opt/netperf/dev/tools"
fi

echo "=== Phase 3 Integration Tests ==="
echo "Server: $SERVER"
echo "Binary: $NP"
echo ""

# Test 1: Basic netperf
echo "Test 1: Basic OMNI test..."
timeout 15 "$NP" -H "$SERVER" -M -l "$DURATION" -- -d send -k | grep -q "THROUGHPUT=" && echo "✓ PASS" || echo "✗ FAIL"

# Test 2: netperf-multi
echo "Test 2: netperf-multi..."
timeout 30 "$TOOLS/netperf-multi" -n 4 -H "$SERVER" --netperf "$NP" -l "$DURATION" -t OMNI -- -d send | grep -q "Successful:" && echo "✓ PASS" || echo "✗ FAIL"

# Test 3: netperf_stats.py
echo "Test 3: netperf_stats.py..."
echo -e "9000\n9100\n9200\n9300" | python3 "$TOOLS/netperf_stats.py" - | grep -q "Count:" && echo "✓ PASS" || echo "✗ FAIL"

# Test 4: netperf-profile
echo "Test 4: netperf-profile..."
"$TOOLS/netperf-profile" -p baseline -H "$SERVER" --netperf "$NP" --dry-run | grep -q "Command:" && echo "✓ PASS" || echo "✗ FAIL"

# Test 5: netperf-template
echo "Test 5: netperf-template..."
echo '[{"test_name":"T","direction":"send","throughput":9500,"latency":0,"cpu_local":45,"cpu_remote":32}]' | \
  "$TOOLS/netperf-template" -t markdown-report /dev/stdin | grep -q "Netperf Test Report" && echo "✓ PASS" || echo "✗ FAIL"

echo ""
echo "=== Tests Complete ==="

# === METADATA_FOOTER_START ===
# Search Keywords: quick-test.sh, integration smoke test, netperf OMNI, netperf-multi, netperf-profile, netperf-template
# Drivers & Subsystems: Linux TCP/UDP stack, ice, netperf OMNI engine
# Related Units / Patches: Phase 3-7 Modernization Validation Suite
# Created / Last-Updated: 2026-01-30 / 2026-11-06
# === METADATA_FOOTER_END ===
