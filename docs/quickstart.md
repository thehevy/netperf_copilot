---
layout: default
title: Quick Start Guide
---

# Quick Start Guide

Get up and running with netperf in minutes.

[← Back to Documentation](index.html)

---

## 5-Minute Quick Start

### Step 1: Build Netperf

```bash
git clone https://github.com/thehevy/netperf_copilot.git
cd netperf_copilot
./dev/scripts/build.sh --type optimized
```

### Step 2: Start Server

```bash
# Start netserver (listening on all interfaces)
./build/src/netserver -D
```

### Step 3: Run Your First Test

```bash
# Basic throughput test (10 seconds)
./build/src/netperf -H localhost -l 10

# Output (keyval format - THIS IS THE DEFAULT):
# OMNI Send TEST from 0.0.0.0...
# THROUGHPUT=45234.67
# THROUGHPUT_UNITS=10^6bits/s
# ELAPSED_TIME=10.00
# PROTOCOL=TCP
# ...
```

**Congratulations!** You've run your first netperf test. 🎉

**ℹ️ Default Format:** netperf defaults to **TCP_STREAM** with columnar output for 100% backwards compatibility. For modern OMNI test with keyval output, use the `-M` flag.

---

## Common Test Scenarios

### Throughput Measurement

```bash
# TCP throughput (send direction)
netperf -H remotehost -l 30

# TCP throughput (receive direction)
netperf -H remotehost -- -d recv -l 30

# UDP throughput
netperf -H remotehost -- -T udp -l 30

# With CPU utilization
netperf -H remotehost -c -C -l 30
```

### Latency Measurement

```bash
# TCP request-response
netperf -H remotehost -t TCP_RR -l 30

# With burst mode (realistic)
netperf -H remotehost -t TCP_RR -- -b 1 -l 30

# UDP request-response
netperf -H remotehost -t UDP_RR -l 30
```

### Different Output Formats

```bash
# Key-value (DEFAULT - easy to parse!)
netperf -H remotehost
# Output: THROUGHPUT=45234.67

# Legacy columnar (for old scripts)
netperf -H remotehost -t TCP_STREAM

# JSON output (best for automation)
netperf -H remotehost -- -J

# OMNI columnar (human-readable)
netperf -H remotehost -- -O
```

**Note:** The default has been keyval since v2.7.x. Legacy scripts expecting columnar format should use `-t TCP_STREAM`. See [Backwards Compatibility Guide](../dev/docs/BACKWARDS_COMPATIBILITY.html).

---

## Using Advanced Tools

### Parallel Testing

### Parallel Testing

Run multiple tests simultaneously:

```bash
# 4 parallel instances with aggregate statistics (from repository)
cd /opt/netperf
./dev/tools/netperf-multi -n 4 -H remotehost --netperf ./build/src/netperf --aggregate

# Output:
# Multi-Instance Test Summary
# Successful: 4/4
# Aggregated Results:
# THROUGHPUT: 135177.79
# avg_per_instance: 33794.45

# For statistical analysis across multiple runs, see Workflow 3 below
```

**Important**: Always use `--netperf` to specify the built netperf binary:

```bash
# Correct: Use the built binary
netperf-multi --netperf ./build/src/netperf -n 4 -H host --aggregate

# System netperf may have different output format
```

### Statistical Analysis

Analyze multiple test runs:

```bash
# Run 20 tests and get statistics (modern OMNI format)
for i in {1..20}; do 
  netperf -H remotehost -M -l 10
done 2>&1 | grep "THROUGHPUT=" | cut -d= -f2 | ./dev/tools/netperf_stats.py -

# Or save to file first
for i in {1..20}; do 
  netperf -H remotehost -M -l 10
done 2>&1 | grep "THROUGHPUT=" | cut -d= -f2 > results.txt

./dev/tools/netperf_stats.py results.txt

# Output:
# Sample size: 20
# Mean: 45234.67 ± 123.45 (95% CI)
# Median: 45189.23
# CV: 2.34%
# Outliers: 0
```

### Using Test Profiles

Quick tests with pre-configured settings:

```bash
# Baseline validation (10 seconds, basic metrics)
netperf-profile -p baseline -H remotehost

# Maximum throughput test (60 seconds)
netperf-profile -p throughput -H remotehost

# Latency-focused test (30 seconds)
netperf-profile -p latency -H remotehost

# List all available profiles
netperf-profile --list
```

Available profiles:

- `baseline` - Quick validation
- `throughput` - Maximum bandwidth
- `latency` - Request-response focus
- `stress` - System limits (5 minutes)
- `cloud` - Cloud networking
- `datacenter` - High-speed DC (jumbo frames)
- `wireless` - WiFi/mobile networks
- `jitter` - Latency variation
- `lossy` - High packet loss
- `mixed-workload` - Combined TCP/UDP

### Real-Time Monitoring

Watch tests in real-time:

```bash
# Terminal 1: Start monitoring
netperf-monitor --host remotehost --interval 1

# Terminal 2: Run tests
netperf -H remotehost -l 300

# Or demo mode to see UI
netperf-monitor --demo
```

### Report Generation

Create formatted reports:

```bash
# Run test with JSON output
netperf -H remotehost -- -J > results.json

# Generate markdown report
netperf-template -t markdown-report results.json > report.md

# Generate HTML dashboard
netperf-template -t html-dashboard results.json > dashboard.html
```

---

## Common Workflows

### Workflow 1: Quick Network Validation

```bash
# 1. Run baseline profile
netperf-profile -p baseline -H remotehost

# 2. If issues, check latency
netperf -H remotehost -t TCP_RR -- -J

# 3. Compare with UDP
netperf -H remotehost -- -T udp
```

### Workflow 2: Performance Benchmarking

```bash
# 1. Run multiple iterations (modern OMNI with -M flag)
for i in {1..10}; do
  netperf -H remotehost -M -l 60
done 2>&1 | grep "THROUGHPUT=" | cut -d= -f2 > results.txt

# 2. Analyze statistics
./dev/tools/netperf_stats.py results.txt

# 3. Generate report
# (convert to JSON format first if needed)
netperf-template -t markdown-report results.json > benchmark.md
```

### Workflow 3: Statistical Analysis with Parallel Tests

```bash
# 1. Run multiple parallel test runs for statistical analysis
for i in {1..20}; do
  ./dev/tools/netperf-multi -n 4 -H remotehost --netperf ./build/src/netperf --aggregate 2>/dev/null | \
    grep "^THROUGHPUT" | awk '{print $3}'
done | ./dev/tools/netperf_stats.py -

# Note: Use --netperf to specify the built netperf binary (e.g., ./build/src/netperf)
# Each iteration runs 4 parallel instances and reports aggregate throughput
# The statistics show mean, median, confidence intervals, and outliers

# 2. Save results for later analysis
for i in {1..20}; do
  ./dev/tools/netperf-multi -n 4 -H remotehost --netperf ./build/src/netperf --aggregate 2>/dev/null | \
    grep "^THROUGHPUT" | awk '{print $3}'
done > throughputs.txt

./dev/tools/netperf_stats.py throughputs.txt

# 3. Customize analysis
./dev/tools/netperf_stats.py throughputs.txt --confidence 0.99 --bins 15 --no-outliers
```

### Workflow 4: Multi-Host Testing

```bash
# 1. Create inventory
cat > hosts.yaml << 'EOF'
hosts:
  - name: server1
    address: 192.168.1.10
    role: server
  - name: client1
    address: 192.168.1.20
    role: client
    target: 192.168.1.10
    profile: throughput
EOF

# 2. Run orchestrated tests
netperf-orchestrate -i hosts.yaml --parallel

# 3. Collect results
# (results stored per host)
```

---

## Output Format Examples

### Key-Value Format (Default)

```
THROUGHPUT=45234.67
THROUGHPUT_UNITS=Mbps
ELAPSED_TIME=10.00
PROTOCOL=TCP
DIRECTION=send
LOCAL_CPU_UTIL=12.34
REMOTE_CPU_UTIL=23.45
```

**Use case**: Easy to grep, parse, script

### JSON Format

```json
{
  "THROUGHPUT": 45234.67,
  "THROUGHPUT_UNITS": "Mbps",
  "ELAPSED_TIME": 10.00,
  "PROTOCOL": "TCP",
  "DIRECTION": "send",
  "LOCAL_CPU_UTIL": 12.34,
  "REMOTE_CPU_UTIL": 23.45
}
```

**Use case**: Modern tools, APIs, databases

### CSV Format

```csv
Throughput,Units,Elapsed Time,Protocol,Direction,Local CPU,Remote CPU
45234.67,Mbps,10.00,TCP,send,12.34,23.45
```

**Use case**: Spreadsheets, plotting tools

### Columnar Format (Traditional)

```
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    Mbps

131072  16384  16384    10.00    45234.67
```

**Use case**: Human reading, backwards compatibility

---

## Tips & Tricks

### Tip 1: Use Output Presets

Instead of remembering specific metrics:

```bash
# Minimal output (throughput only)
netperf -H host -- -k dev/catalog/output-presets/minimal.out

# Verbose output (all metrics)
netperf -H host -- -k dev/catalog/output-presets/verbose.out

# Latency-focused
netperf -H host -t TCP_RR -- -k dev/catalog/output-presets/latency.out
```

### Tip 2: Save Command History

Output includes the command line used:

```bash
netperf -H remotehost -l 30 -- -d send

# Output includes:
# COMMAND_LINE=netperf -H remotehost -l 30 -- -d send
```

### Tip 3: Use Intervals for Long Tests

```bash
# See progress every 5 seconds
netperf -H remotehost -l 300 -- -i 5

# Output shows interim results during test
```

### Tip 4: Combine Tools for Statistical Analysis

```bash
# Parallel tests with statistics (recommended for speed)
for i in {1..10}; do 
  ./dev/tools/netperf-multi -n 4 -H host --netperf ./build/src/netperf --aggregate 2>/dev/null | \
    grep "^THROUGHPUT" | awk '{print $3}'
done | ./dev/tools/netperf_stats.py -

# Sequential tests with statistics (modern OMNI)
for i in {1..10}; do 
  netperf -H host -M -l 30
done 2>&1 | grep "THROUGHPUT=" | cut -d= -f2 | ./dev/tools/netperf_stats.py -

# Save results and generate custom analysis
for i in {1..20}; do netperf -H host -M -l 30; done 2>&1 | \
  grep "THROUGHPUT=" | cut -d= -f2 > results.txt

./dev/tools/netperf_stats.py results.txt --confidence 0.99 --bins 20
```

### Tip 5: Test Both Directions

```bash
# Send direction
netperf -H remotehost -- -d send

# Receive direction
netperf -H remotehost -- -d recv

# Or use MAERTS test (reverse)
netperf -H remotehost -t TCP_MAERTS
```

---

## Troubleshooting Quick Fixes

### Problem: Connection Refused

```bash
# Check if netserver is running
ps aux | grep netserver

# Start netserver if not running
netserver -D

# Check firewall
sudo iptables -L | grep 12865  # default port
```

### Problem: Low Throughput

```bash
# Check CPU utilization
netperf -H host -c -C

# Try different message sizes
netperf -H host -- -m 65536  # larger messages

# Check for packet loss
netperf -H host -- -T udp
```

### Problem: High Latency

```bash
# Measure request-response
netperf -H host -t TCP_RR

# Check with burst mode
netperf -H host -t TCP_RR -- -b 1

# Compare protocols
netperf -H host -t TCP_RR
netperf -H host -t UDP_RR
```

---

## Next Steps

### Learn More

- [OMNI Test Framework](../dev/docs/OMNI_REFERENCE.html) - Complete guide
- [Output Formats](../dev/docs/OUTPUT_FORMATS.html) - Detailed format reference
- [Build Configuration](../dev/docs/BUILD_CONFIGURATION.html) - Customize your build

### Advanced Features

- [Statistical Analysis Guide](tools/netperf-stats.html) - Deep dive into statistics
- [Test Profiles Reference](tools/netperf-profile.html) - All profile details
- [Orchestration Guide](../dev/docs/ORCHESTRATION.html) - Multi-host testing
- [Monitoring Guide](../dev/docs/MONITORING.html) - Real-time visualization

### Get Help

- Read the [full documentation](../dev/docs/)
- Check the [examples directory](https://github.com/thehevy/netperf_copilot/tree/master/dev/examples)
- Review [integration test results](../dev/docs/INTEGRATION_TESTING.html)

---

[← Back to Documentation](index.html)
