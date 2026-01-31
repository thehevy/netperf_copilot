#!/bin/bash
# Phase 3 Integration Test Suite - Quick Version
# Tests Phase 3 tools with live netperf server at 192.168.18.2

set -e

SERVER="192.168.18.2"
NETPERF="/opt/netperf/build/src/netperf"
TOOLS_DIR="/opt/netperf/dev/tools"
RESULTS_DIR="/opt/netperf/dev/tests/results"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TOTAL=0
PASSED=0

mkdir -p "$RESULTS_DIR"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Phase 3 Integration Tests - Server: $SERVER       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

test_result() {
    TOTAL=$((TOTAL + 1))
    if [ $1 -eq 0 ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓ PASS${NC}: $2"
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
    fi
}

# Test 1: Basic connectivity
echo -e "\n${YELLOW}Test 1: Server Connectivity${NC}"
if ping -c 2 -W 2 $SERVER > /dev/null 2>&1; then
    test_result 0 "Server reachable"
else
    test_result 1 "Server unreachable"
    exit 1
fi

# Test 2: Basic OMNI test
echo -e "\n${YELLOW}Test 2: Basic OMNI TCP Send${NC}"
if timeout 15 $NETPERF -H $SERVER -- -d send -l 10 > "$RESULTS_DIR/test2.txt" 2>&1; then
    if grep -q "THROUGHPUT=" "$RESULTS_DIR/test2.txt"; then
        TP=$(grep "THROUGHPUT=" "$RESULTS_DIR/test2.txt" | head -1 | sed 's/.*THROUGHPUT=//; s/ .*//')
        test_result 0 "Basic test OK (Throughput: $TP Mbps)"
    else
        test_result 1 "No throughput data"
    fi
else
    test_result 1 "Basic test failed"
fi

# Test 3: netperf-multi
echo -e "\n${YELLOW}Test 3: netperf-multi (4 parallel instances)${NC}"
if timeout 30 $TOOLS_DIR/netperf-multi -n 4 -H $SERVER --netperf $NETPERF -- \
    -d send -l 10 > "$RESULTS_DIR/test3.txt" 2>&1; then
    if grep -q "Successful:" "$RESULTS_DIR/test3.txt"; then
        SUCC=$(grep "Successful:" "$RESULTS_DIR/test3.txt" | awk '{print $2}')
        test_result 0 "Parallel execution OK ($SUCC/4 successful)"
    else
        test_result 1 "No success metrics"
    fi
else
    test_result 1 "netperf-multi failed"
fi

# Test 4: netperf_stats.py
echo -e "\n${YELLOW}Test 4: netperf_stats.py (Statistical Analysis)${NC}"
seq 9000 100 9900 > "$RESULTS_DIR/test4-data.txt"
if python3 $TOOLS_DIR/netperf_stats.py "$RESULTS_DIR/test4-data.txt" > "$RESULTS_DIR/test4.txt" 2>&1; then
    if grep -q "Sample size:" "$RESULTS_DIR/test4.txt"; then
        test_result 0 "Statistical analysis OK"
    else
        test_result 1 "Incomplete statistics output"
    fi
else
    test_result 1 "netperf_stats.py failed"
fi

# Test 5: netperf-profile
echo -e "\n${YELLOW}Test 5: netperf-profile (Baseline profile dry-run)${NC}"
if timeout 20 $TOOLS_DIR/netperf-profile -p baseline -H $SERVER --netperf $NETPERF \
    --dry-run > "$RESULTS_DIR/test5.txt" 2>&1; then
    if grep -q "Would execute:" "$RESULTS_DIR/test5.txt"; then
        NUM=$(grep -c "Would execute:" "$RESULTS_DIR/test5.txt")
        test_result 0 "Profile validation OK ($NUM tests)"
    else
        test_result 1 "Profile validation failed"
    fi
else
    test_result 1 "netperf-profile failed"
fi

# Test 6: netperf-template
echo -e "\n${YELLOW}Test 6: netperf-template (Markdown report)${NC}"
cat > "$RESULTS_DIR/test6-data.json" << EOF
[{"test_name":"Test","direction":"send","throughput":9500,"latency":0,"cpu_local":45,"cpu_remote":32}]
EOF
if $TOOLS_DIR/netperf-template -t markdown-report "$RESULTS_DIR/test6-data.json" \
    > "$RESULTS_DIR/test6.md" 2>&1; then
    if grep -q "Netperf Test Report" "$RESULTS_DIR/test6.md"; then
        test_result 0 "Template rendering OK"
    else
        test_result 1 "Report incomplete"
    fi
else
    test_result 1 "netperf-template failed"
fi

# Test 7: KEYVAL output format
echo -e "\n${YELLOW}Test 7: KEYVAL Output Format${NC}"
if timeout 15 $NETPERF -H $SERVER -- -d send -l 10 -k THROUGHPUT,LOCAL_CPU_UTIL \
    > "$RESULTS_DIR/test7.txt" 2>&1; then
    if grep -q "THROUGHPUT=" "$RESULTS_DIR/test7.txt"; then
        test_result 0 "KEYVAL format OK"
    else
        test_result 1 "KEYVAL format invalid"
    fi
else
    test_result 1 "KEYVAL test failed"
fi

# Test 8: Request-Response pattern
echo -e "\n${YELLOW}Test 8: Request-Response (RR) Pattern${NC}"
if timeout 15 $NETPERF -H $SERVER -- -d rr -l 10 > "$RESULTS_DIR/test8.txt" 2>&1; then
    if grep -qE "TRANSACTION_RATE=|MEAN_LATENCY=|Latency|Transaction Rate" "$RESULTS_DIR/test8.txt"; then
        test_result 0 "RR pattern OK"
    else
        test_result 1 "RR output unexpected"
    fi
else
    test_result 1 "RR test failed"
fi

# Test 9: UDP traffic
echo -e "\n${YELLOW}Test 9: UDP Traffic${NC}"
if timeout 15 $NETPERF -H $SERVER -- -d send -T udp -l 10 > "$RESULTS_DIR/test9.txt" 2>&1; then
    if grep -q "THROUGHPUT=" "$RESULTS_DIR/test9.txt"; then
        test_result 0 "UDP test OK"
    else
        test_result 1 "UDP output unexpected"
    fi
else
    test_result 1 "UDP test failed"
fi

# Test 10: Multiple output selectors
echo -e "\n${YELLOW}Test 10: Multiple Output Selectors${NC}"
if timeout 15 $NETPERF -H $SERVER -- -d send -l 10 -k THROUGHPUT,LOCAL_CPU_UTIL,REMOTE_CPU_UTIL \
    > "$RESULTS_DIR/test10.txt" 2>&1; then
    if grep -q "THROUGHPUT=" "$RESULTS_DIR/test10.txt" && \
       grep -q "LOCAL_CPU_UTIL=" "$RESULTS_DIR/test10.txt"; then
        test_result 0 "Multiple selectors OK"
    else
        test_result 1 "Missing selectors"
    fi
else
    test_result 1 "Multi-selector test failed"
fi

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  Test Summary                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Total Tests: $TOTAL"
echo -e "${GREEN}Passed:      $PASSED${NC}"
echo -e "${RED}Failed:      $((TOTAL - PASSED))${NC}"

if [ $PASSED -eq $TOTAL ]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ ALL TESTS PASSED - Phase 3 is production-ready!       ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 0
else
    echo ""
    echo -e "${YELLOW}Success Rate: $(echo "scale=1; $PASSED * 100 / $TOTAL" | bc)%${NC}"
    echo ""
    echo "Results saved in: $RESULTS_DIR"
    exit 1
fi
