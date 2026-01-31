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

# Output (keyval format):
# THROUGHPUT=45234.67
# ELAPSED_TIME=10.00
# PROTOCOL=TCP
# ...
```

**Congratulations!** You've run your first netperf test. 🎉

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
# Key-value (default, easy to parse)
netperf -H remotehost

# JSON output
netperf -H remotehost -- -J

# CSV output
netperf -H remotehost -- -o

# Traditional columnar
netperf -H remotehost -- -O
```

---

## Using Advanced Tools

### Parallel Testing

Run multiple tests simultaneously:

```bash
# 4 parallel instances (from repository)
cd /opt/netperf
./dev/tools/netperf-multi -n 4 -H remotehost -- -d send -l 30

# Or after installation
netperf-multi -n 4 -H remotehost -- -d send -l 30

# Output:
# Multi-Instance Test Summary
# Successful: 4
# Failed: 0
# Average Throughput: 42567.89 Mbps
```

**Note**: For statistical analysis, use sequential netperf runs (netperf-multi shows only a summary):

```bash
# Sequential tests for statistical analysis
for i in {1..10}; do 
  ./build/src/netperf -H remotehost -- -d send -l 30
done 2>&1 | grep "THROUGHPUT=" | cut -d= -f2 | ./dev/tools/netperf_stats.py -
```

### Statistical Analysis

Analyze multiple test runs:

```bash
# Run 20 tests and get statistics
for i in {1..20}; do 
  netperf -H remotehost -l 10
done | netperf_stats.py -

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
# 1. Run multiple iterations
for i in {1..10}; do
  netperf -H remotehost -l 60 -- -d send
done > results.txt

# 2. Analyze statistics
netperf_stats.py results.txt --histogram chart.png

# 3. Generate report
# (convert to JSON format first if needed)
netperf-template -t markdown-report results.json > benchmark.md
```

### Workflow 3: Statistical Analysis of Multiple Runs

```bash
# 1. Run multiple sequential tests
for i in {1..20}; do
  netperf -H remotehost -l 30 -- -d send
done 2>&1 | tee raw-results.txt

# 2. Extract throughput values
grep "THROUGHPUT=" raw-results.txt | cut -d= -f2 > throughputs.txt

# 3. Get statistics with histogram
netperf_stats.py throughputs.txt --histogram results.png

# Or in one pipeline:
for i in {1..20}; do netperf -H remotehost -l 30; done 2>&1 | \
  grep "THROUGHPUT=" | cut -d= -f2 | \
  netperf_stats.py -
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
### Tip 4: Combine Tools

```bash
# Sequential tests + Statistics (recommended)
for i in {1..10}; do netperf -H host -l 30 -- -d send; done 2>&1 | \
  grep "THROUGHPUT=" | cut -d= -f2 | \
  netperf_stats.py - | \
  tee stats-report.txt

# With histogram
for i in {1..20}; do netperf -H host -l 30; done 2>&1 | \
  grep "THROUGHPUT=" | cut -d= -f2 | \
  netperf_stats.py - --histogram chart.png
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
