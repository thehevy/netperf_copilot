#!/bin/bash
# Quick Integration Test for Phase 3

SERVER="192.168.18.2"
NP="/opt/netperf/build/src/netperf"
TOOLS="/opt/netperf/dev/tools"

echo "=== Phase 3 Integration Tests ==="
echo "Server: $SERVER"
echo ""

# Test 1: Basic netperf
echo "Test 1: Basic OMNI test..."
timeout 15 $NP -H $SERVER -- -d send -l 10 | grep "THROUGHPUT=" && echo "✓ PASS" || echo "✗ FAIL"

# Test 2: netperf-multi
echo "Test 2: netperf-multi..."
timeout 30 $TOOLS/netperf-multi -n 4 -H $SERVER --netperf $NP -- -d send -l 10 | grep "Successful:" && echo "✓ PASS" || echo "✗ FAIL"

# Test 3: netperf_stats.py
echo "Test 3: netperf_stats.py..."
echo -e "9000\n9100\n9200\n9300" | python3 $TOOLS/netperf_stats.py - | grep "Sample size:" && echo "✓ PASS" || echo "✗ FAIL"

# Test 4: netperf-profile  
echo "Test 4: netperf-profile..."
$TOOLS/netperf-profile -p baseline -H $SERVER --netperf $NP --dry-run | grep "Would execute:" && echo "✓ PASS" || echo "✗ FAIL"

# Test 5: netperf-template
echo "Test 5: netperf-template..."
echo '[{"test_name":"T","direction":"send","throughput":9500,"latency":0,"cpu_local":45,"cpu_remote":32}]' | \
  $TOOLS/netperf-template -t markdown-report /dev/stdin | grep "Netperf Test Report" && echo "✓ PASS" || echo "✗ FAIL"

echo ""
echo "=== Tests Complete ==="
