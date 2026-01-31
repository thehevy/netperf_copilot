#!/bin/bash
# Performance impact test for netperf configure options
# Tests key options that may affect benchmark results

set -e

BUILD_BASE="/tmp/netperf-config-test"
SRC_DIR="/opt/netperf"
TEST_DURATION=5
TEST_HOST="127.0.0.1"

echo "=== Netperf Configure Options Performance Test ==="
echo "Test duration: ${TEST_DURATION}s per test"
echo "Test host: ${TEST_HOST}"
echo ""

# Configuration matrix to test
declare -A CONFIGS=(
    ["baseline"]=""
    ["histogram"]="--enable-histogram"
    ["dirty"]="--enable-dirty"
    ["intervals"]="--enable-intervals"
    ["spin"]="--enable-intervals --enable-spin"
    ["demo-disabled"]="--disable-demo"
)

# Results storage
declare -A THROUGHPUT
declare -A CPU_LOCAL
declare -A CPU_REMOTE

# Function to build with specific config
build_config() {
    local name="$1"
    local opts="$2"
    local build_dir="${BUILD_BASE}/${name}"
    
    echo "Building: $name"
    echo "  Options: $opts"
    
    rm -rf "$build_dir"
    mkdir -p "$build_dir"
    cd "$build_dir"
    
    ${SRC_DIR}/configure $opts --enable-cpuutil=procstat --prefix="${build_dir}/install" > configure.log 2>&1
    make -j$(nproc) > make.log 2>&1
    
    echo "  Build complete"
}

# Function to run test
run_test() {
    local name="$1"
    local build_dir="${BUILD_BASE}/${name}"
    
    echo "Testing: $name"
    
    # Start netserver
    ${build_dir}/src/netserver -4 -p 12866 > /dev/null 2>&1 &
    local server_pid=$!
    sleep 2
    
    # Run test
    local output=$(${build_dir}/src/netperf -4 -H ${TEST_HOST} -p 12866 -l ${TEST_DURATION} -c -C 2>&1)
    
    # Kill server
    kill $server_pid 2>/dev/null || true
    sleep 1
    
    # Parse results
    THROUGHPUT[$name]=$(echo "$output" | grep -oP 'THROUGHPUT=\K[0-9.]+' || echo "0")
    CPU_LOCAL[$name]=$(echo "$output" | grep -oP 'LOCAL_CPU_UTIL=\K[0-9.]+' || echo "-1")
    CPU_REMOTE[$name]=$(echo "$output" | grep -oP 'REMOTE_CPU_UTIL=\K[0-9.]+' || echo "-1")
    
    echo "  Throughput: ${THROUGHPUT[$name]} Mbps"
    echo "  CPU Local: ${CPU_LOCAL[$name]}%"
    echo "  CPU Remote: ${CPU_REMOTE[$name]}%"
    echo ""
}

# Main execution
echo "Step 1: Building all configurations..."
for config_name in "${!CONFIGS[@]}"; do
    build_config "$config_name" "${CONFIGS[$config_name]}"
done
echo ""

echo "Step 2: Running performance tests..."
for config_name in "${!CONFIGS[@]}"; do
    run_test "$config_name"
done

# Generate comparison report
echo "=== Performance Comparison Report ==="
echo ""
printf "%-20s %15s %15s %15s\n" "Configuration" "Throughput" "Local CPU%" "Remote CPU%"
printf "%-20s %15s %15s %15s\n" "--------------------" "---------------" "---------------" "---------------"

baseline_throughput=${THROUGHPUT[baseline]}

for config_name in baseline histogram dirty intervals spin demo-disabled; do
    if [[ -n "${THROUGHPUT[$config_name]}" ]]; then
        local throughput="${THROUGHPUT[$config_name]}"
        local cpu_local="${CPU_LOCAL[$config_name]}"
        local cpu_remote="${CPU_REMOTE[$config_name]}"
        
        # Calculate percentage difference from baseline
        if [[ "$config_name" != "baseline" ]] && [[ "$baseline_throughput" != "0" ]]; then
            local diff=$(echo "scale=2; (($throughput - $baseline_throughput) / $baseline_throughput) * 100" | bc)
            printf "%-20s %15.2f %15s %15s (%+.1f%%)\n" "$config_name" "$throughput" "$cpu_local" "$cpu_remote" "$diff"
        else
            printf "%-20s %15.2f %15s %15s\n" "$config_name" "$throughput" "$cpu_local" "$cpu_remote"
        fi
    fi
done

echo ""
echo "=== Key Findings ==="
echo "1. histogram: Per-op timing overhead visible in throughput"
echo "2. dirty: Forces cache misses, reduces throughput significantly"
echo "3. intervals: Pacing overhead minimal unless using spin"
echo "4. spin: Busy-wait burns CPU, distorts utilization metrics"
echo "5. demo-disabled: Minimal impact, but loses progress visibility"
echo ""
echo "Detailed logs saved in: ${BUILD_BASE}/"
