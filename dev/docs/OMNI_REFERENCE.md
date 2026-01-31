# OMNI Test Reference Guide

**Version**: 2.7.1+  
**Phase**: 3 - Advanced Features  
**Last Updated**: January 31, 2026

---

## Overview

OMNI is the modern unified test framework in netperf that replaces the classic TCP_STREAM, TCP_RR, UDP_STREAM, etc. tests with a single flexible test type that can emulate all patterns.

**Why OMNI?**
- Single test implementation for all protocols and patterns
- Extensible output formatting
- More consistent behavior across test types
- Easier to maintain and enhance
- Default test type as of Phase 1 modernization

---

## Basic Usage

### Simple OMNI Test
```bash
# Default: TCP send/stream test
netperf -H server1

# Equivalent to old TCP_STREAM
netperf -H server1 -t OMNI

# With explicit direction
netperf -H server1 -t OMNI -- -d send
```

### Classic Test Migration
```bash
# Old style                    # New OMNI equivalent
TCP_STREAM                     OMNI -d send -T tcp
TCP_MAERTS                     OMNI -d recv -T tcp
TCP_RR                         OMNI -d rr -T tcp
TCP_CRR                        OMNI -d rr -T tcp -c
UDP_STREAM                     OMNI -d send -T udp
UDP_RR                         OMNI -d rr -T udp
SCTP_STREAM                    OMNI -d send -T sctp
```

---

## OMNI-Specific Options

OMNI tests use the global `-t OMNI` option, then test-specific options after `--`.

### Direction Option: `-d <direction>`

Controls the test pattern and direction relative to netperf process.

**Syntax**: `-d <direction>` (case-insensitive)

#### Stream/Send Patterns
Send data from netperf to netserver (unidirectional):

```bash
-d send       # Send data (most common)
-d stream     # Alias for send
-d transmit   # Alias for send
-d xmit       # Alias for send
-d 2          # Numeric form
```

**Use Cases**:
- Maximum throughput testing (client sending)
- Upload bandwidth measurement
- Transmit buffer tuning

**Example**:
```bash
netperf -H server1 -- -d send
```

#### Receive/MAERTS Patterns
Send data from netserver to netperf (reverse direction):

```bash
-d recv       # Receive data
-d receive    # Alias for recv
-d maerts     # "stream" backwards (classic name)
-d 4          # Numeric form
```

**Use Cases**:
- Download bandwidth measurement
- Receive buffer tuning
- Server-to-client throughput

**Example**:
```bash
netperf -H server1 -- -d recv
```

#### Request/Response Patterns
Bidirectional transaction-based testing:

```bash
-d rr         # Request/response
-d 6          # Numeric form
```

**Use Cases**:
- Latency measurement
- Transaction rate testing
- Request/response workloads (web, database, etc.)

**Example**:
```bash
netperf -H server1 -- -d rr
```

#### Combined Directions
Combine multiple directions with `|` (OR operation):

```bash
-d "send|recv"    # Bidirectional (both directions)
-d "Send|Recv"    # Case-insensitive
```

**Use Cases**:
- Analyzing output from request/response tests
- Parsing DIRECTION output selector
- Custom test patterns

---

### Protocol Option: `-T <protocol>`

Explicitly sets the protocol for the test.

**Syntax**: `-T <protocol>` (case-insensitive)

#### Supported Protocols

##### TCP (Transmission Control Protocol)
```bash
-T tcp        # Default for most tests
-T TCP        # Case-insensitive
```

**Characteristics**:
- Connection-oriented
- Reliable delivery
- In-order delivery
- Flow control
- Congestion control

**Use Cases**:
- General purpose throughput/latency testing
- Most common network workloads
- Baseline performance measurement

##### UDP (User Datagram Protocol)
```bash
-T udp
-T UDP
```

**Characteristics**:
- Connectionless
- Unreliable (no retransmissions)
- No flow control
- Lower overhead than TCP

**Use Cases**:
- Streaming media simulation
- Real-time applications
- Maximum packet rate testing
- Low-latency scenarios

**Important**: UDP streams need careful message size selection:
```bash
# Avoid fragmentation (Ethernet MTU 1500 - headers)
netperf -H server1 -- -T udp -d send -m 1472
```

##### SCTP (Stream Control Transport Protocol)
```bash
-T sctp
-T SCTP
```

**Characteristics**:
- Connection-oriented like TCP
- Message-oriented (preserves boundaries)
- Multi-streaming
- Multi-homing support

**Use Cases**:
- Signaling protocols (SS7, Diameter)
- Multi-stream applications
- Applications requiring message boundaries

**Note**: Requires kernel SCTP support (Linux: `modprobe sctp`)

##### SDP (Sockets Direct Protocol)
```bash
-T sdp
-T SDP
```

**Characteristics**:
- TCP-like semantics
- RDMA acceleration
- Kernel bypass

**Use Cases**:
- InfiniBand networks
- High-performance computing
- Low-latency data centers

**Requirements**: InfiniBand hardware and SDP-enabled kernel

##### DCCP (Datagram Congestion Control Protocol)
```bash
-T dccp
-T DCCP
```

**Characteristics**:
- Unreliable like UDP
- Congestion control like TCP
- Message-oriented

**Use Cases**:
- Streaming with congestion control
- Real-time applications needing fairness

**Note**: Less commonly available, check kernel support

##### UDP Lite
```bash
-T udplite
-T UDPLITE
```

**Characteristics**:
- UDP variant
- Partial checksum coverage
- Tolerates some corruption

**Use Cases**:
- Error-tolerant multimedia
- Wireless networks with bit errors

---

### Connection Option: `-c`

Includes connection establishment and tear-down in the test.

**Syntax**: `-c` (flag, no argument)

**Effect**: 
- Each transaction includes TCP connect/close
- Equivalent to classic TCP_CRR test
- Measures connection overhead

**Use Cases**:
- Web server simulation (new connection per request)
- Connection establishment performance
- Connection rate testing
- SYN/SYN-ACK latency measurement

**Example**:
```bash
# Request/response with connections (like TCP_CRR)
netperf -H server1 -- -d rr -c

# Connection rate test
netperf -H server1 -- -d rr -c -r 1,1
```

**Performance Impact**:
- Significantly higher latency per transaction
- Tests TCP handshake performance
- Stresses ephemeral port allocation
- Tests TIME_WAIT handling

---

## Common OMNI Test Patterns

### Maximum Throughput (TCP)
```bash
# Send direction (upload)
netperf -H server1 -- -d send -T tcp

# Receive direction (download)  
netperf -H server1 -- -d recv -T tcp

# With large buffers
netperf -H server1 -- -d send -T tcp -s 262144 -S 262144
```

### Latency Testing (TCP)
```bash
# Basic request/response
netperf -H server1 -- -d rr -T tcp

# Small messages (1 byte each direction)
netperf -H server1 -- -d rr -T tcp -r 1,1

# Burst mode (10 back-to-back transactions)
netperf -H server1 -- -d rr -T tcp -b 10
```

### Connection Rate Testing
```bash
# Connections per second
netperf -H server1 -- -d rr -T tcp -c -r 1,1

# HTTP-like pattern (request + response)
netperf -H server1 -- -d rr -T tcp -c -r 64,1024
```

### UDP Throughput
```bash
# UDP send with optimal message size
netperf -H server1 -- -d send -T udp -m 1472

# UDP receive test
netperf -H server1 -- -d recv -T udp -m 1472
```

### UDP Latency
```bash
# UDP request/response
netperf -H server1 -- -d rr -T udp -r 1,1
```

### SCTP Testing
```bash
# SCTP stream
netperf -H server1 -- -d send -T sctp

# SCTP request/response
netperf -H server1 -- -d rr -T sctp
```

---

## OMNI with Output Formats

### JSON Output
```bash
# OMNI test with JSON output
netperf -H server1 -J -- -d send

# With metadata
netperf -H server1 -J -- -d send -T tcp
```

### CSV Output
```bash
# CSV with headers
netperf -H server1 -o csv -- -d send

# Custom output selectors
netperf -H server1 -o csv -k THROUGHPUT,MEAN_LATENCY -- -d rr
```

### KEYVAL Output (Default)
```bash
# Default keyval format
netperf -H server1 -- -d send

# With specific selectors
netperf -H server1 -o keyval -k THROUGHPUT,LOCAL_CPU_UTIL -- -d send
```

---

## OMNI Output Selectors

OMNI provides extensive output selectors via `-k` option:

### Throughput Selectors
- `THROUGHPUT` - Throughput in configured units
- `THROUGHPUT_UNITS` - Units (e.g., Mbps, trans/s)
- `LOCAL_SEND_THROUGHPUT` - Send-side throughput
- `REMOTE_RECV_THROUGHPUT` - Receive-side throughput

### Latency Selectors
- `MEAN_LATENCY` - Mean latency (microseconds)
- `MIN_LATENCY` - Minimum latency
- `MAX_LATENCY` - Maximum latency
- `P50_LATENCY` - 50th percentile (median)
- `P90_LATENCY` - 90th percentile
- `P99_LATENCY` - 99th percentile

### CPU Selectors
- `LOCAL_CPU_UTIL` - Local CPU utilization (%)
- `REMOTE_CPU_UTIL` - Remote CPU utilization (%)
- `LOCAL_SERVICE_DEMAND` - CPU per unit throughput
- `REMOTE_SERVICE_DEMAND` - Remote service demand

### Test Configuration Selectors
- `PROTOCOL` - Protocol used (TCP, UDP, SCTP)
- `DIRECTION` - Test direction (Send, Recv, Send|Recv)
- `SOCKET_SIZE` - Socket buffer size
- `MESSAGE_SIZE` - Message/transaction size
- `TEST_TYPE` - Test type (OMNI)

### Example with Custom Selectors
```bash
netperf -H server1 -o keyval \
  -k THROUGHPUT,MEAN_LATENCY,LOCAL_CPU_UTIL,PROTOCOL,DIRECTION \
  -- -d send -T tcp
```

**See Also**: `doc/omni_output_list.txt` for complete selector list

---

## OMNI with Multi-Instance Testing

OMNI works seamlessly with the multi-instance runner:

### Parallel Throughput
```bash
# 4 parallel OMNI send tests
netperf-multi -H server1 -n 4 -- -d send

# 8 parallel with CPU affinity
netperf-multi -H server1 -n 8 --affinity -- -d send
```

### Parallel Latency
```bash
# 4 parallel request/response tests
netperf-multi -H server1 -n 4 -- -d rr

# With custom message sizes
netperf-multi -H server1 -n 4 -- -d rr -r 64,64
```

### Mixed Protocols
```bash
# TCP tests on multiple instances
netperf-multi -H server1 -n 4 -- -d send -T tcp

# UDP tests
netperf-multi -H server1 -n 4 -- -d send -T udp -m 1472
```

---

## Advanced OMNI Options

### Socket Options
```bash
-s <size>     # Local socket send buffer size
-S <size>     # Local socket recv buffer size
-m <size>     # Message/request size
-M <size>     # Response size (for RR tests)
-r <req,rsp>  # Request and response sizes
```

### Test Control
```bash
-l <seconds>  # Test duration (default: 10)
-i <max>,<min> # Maximum and minimum iterations
-b <burst>    # Burst size (back-to-back transactions)
-w <usec>     # Wait time between bursts
```

### CPU Binding
```bash
-T <cpu>      # Bind netperf to CPU (local)
-t <cpu>      # Bind netserver to CPU (remote)
```

### Advanced Features
```bash
-F <file>     # Send from file (file I/O testing)
-f <format>   # Output format (deprecated, use global -o)
-P <port>     # Data port (normally dynamic)
-4            # Force IPv4
-6            # Force IPv6
```

---

## OMNI Performance Tuning

### Throughput Optimization

#### Large Socket Buffers
```bash
# Increase socket buffers for high-bandwidth links
netperf -H server1 -- -d send -s 4M -S 4M
```

#### Multiple Streams
```bash
# Aggregate bandwidth across multiple connections
netperf-multi -H server1 -n 4 -- -d send
```

#### Protocol Selection
```bash
# UDP for maximum packet rate
netperf -H server1 -- -d send -T udp -m 1472

# TCP for reliable throughput
netperf -H server1 -- -d send -T tcp
```

### Latency Optimization

#### Small Messages
```bash
# Minimum latency with 1-byte messages
netperf -H server1 -- -d rr -r 1,1
```

#### Burst Testing
```bash
# Test queueing effects with bursts
netperf -H server1 -- -d rr -b 10 -r 1,1
```

#### TCP_NODELAY
```bash
# Disable Nagle's algorithm (enabled by default in OMNI)
# OMNI automatically enables TCP_NODELAY for RR tests
netperf -H server1 -- -d rr
```

---

## OMNI Migration from Classic Tests

### TCP_STREAM → OMNI
```bash
# Old
netperf -H server1 -t TCP_STREAM -l 30

# New (OMNI default is send direction)
netperf -H server1 -l 30

# Explicit
netperf -H server1 -- -d send -T tcp
```

### TCP_MAERTS → OMNI
```bash
# Old
netperf -H server1 -t TCP_MAERTS

# New
netperf -H server1 -- -d recv
```

### TCP_RR → OMNI
```bash
# Old
netperf -H server1 -t TCP_RR -- -r 1,1

# New
netperf -H server1 -- -d rr -r 1,1
```

### TCP_CRR → OMNI
```bash
# Old
netperf -H server1 -t TCP_CRR -- -r 1,1

# New
netperf -H server1 -- -d rr -c -r 1,1
```

### UDP_STREAM → OMNI
```bash
# Old
netperf -H server1 -t UDP_STREAM -- -m 1472

# New
netperf -H server1 -- -d send -T udp -m 1472
```

### UDP_RR → OMNI
```bash
# Old
netperf -H server1 -t UDP_RR -- -r 1,1

# New
netperf -H server1 -- -d rr -T udp -r 1,1
```

---

## OMNI Troubleshooting

### Issue: Test Hangs or Times Out

**Possible Causes**:
1. Netserver not running on target
2. Firewall blocking connection
3. Wrong IP address/hostname

**Solutions**:
```bash
# Verify netserver is running
ssh server1 pgrep netserver

# Start netserver if needed
ssh server1 netserver -D

# Test connectivity
ping server1
telnet server1 12865  # netperf control port
```

### Issue: UDP Test Shows 0 Throughput

**Cause**: Message size too large, causing IP fragmentation and drops

**Solution**: Use MTU-appropriate message size
```bash
# Ethernet MTU 1500 - 20 IP - 8 UDP = 1472
netperf -H server1 -- -d send -T udp -m 1472

# Jumbo frames (MTU 9000)
netperf -H server1 -- -d send -T udp -m 8972
```

### Issue: SCTP Test Fails

**Cause**: SCTP module not loaded

**Solution**:
```bash
# Load SCTP module
sudo modprobe sctp

# Verify
lsmod | grep sctp
```

### Issue: Connection Refused on Data Port

**Cause**: Ephemeral port range exhausted (common with TCP_CRR/connection tests)

**Solution**: Increase ephemeral port range
```bash
# Linux
echo "1024 65535" > /proc/sys/net/ipv4/ip_local_port_range

# Or tune TIME_WAIT recycling
echo 1 > /proc/sys/net/ipv4/tcp_tw_reuse
```

---

## OMNI Best Practices

### 1. Use OMNI as Default
OMNI is the modern, maintained test framework. Classic tests are legacy.

### 2. Specify Direction and Protocol Explicitly
```bash
# Good: explicit and clear
netperf -H server1 -- -d send -T tcp

# Avoid: relies on defaults
netperf -H server1
```

### 3. Match Test to Workload
- **Stream (-d send/recv)**: Bulk transfer, file downloads, backups
- **Request/Response (-d rr)**: Web, database, API calls
- **Connection (-c)**: Connection rate, HTTP, short-lived connections

### 4. Use Appropriate Protocols
- **TCP**: Most applications, reliable delivery needed
- **UDP**: Streaming, real-time, low latency priority
- **SCTP**: Signaling, multi-stream requirements

### 5. Tune Socket Buffers for Long-Haul
```bash
# Calculate: bandwidth (Mbps) × RTT (ms) / 8 = buffer (KB)
# Example: 1 Gbps × 50ms RTT = 6.25 MB buffer
netperf -H server1 -- -d send -s 8M -S 8M
```

### 6. Use Multi-Instance for Parallel Tests
```bash
# Multiple streams for aggregate bandwidth
netperf-multi -H server1 -n 4 -- -d send
```

### 7. Enable JSON Output for Automation
```bash
# Easy to parse programmatically
netperf -H server1 -J -- -d send | jq '.throughput'
```

### 8. Use Output Selectors for Specific Metrics
```bash
# Only get what you need
netperf -H server1 -o keyval -k THROUGHPUT,MEAN_LATENCY -- -d rr
```

---

## References

- **Full Output Selector List**: `doc/omni_output_list.txt`
- **Netperf Manual**: `doc/netperf.txt` (section 9.1)
- **Phase 1 Defaults**: `dev/docs/PHASE1_FEATURES.md`
- **Output Formats**: `dev/docs/OUTPUT_FORMATS.md`
- **Multi-Instance Guide**: `dev/docs/MULTI_INSTANCE.md`

---

## Quick Reference Card

```bash
# OMNI Test Patterns
netperf -H <host> -- -d send           # Upload throughput
netperf -H <host> -- -d recv           # Download throughput
netperf -H <host> -- -d rr             # Request/response latency
netperf -H <host> -- -d rr -c          # Connection rate

# Protocol Selection
... -- -T tcp       # TCP (default)
... -- -T udp       # UDP
... -- -T sctp      # SCTP

# Common Options
-l <sec>           # Test duration
-r <req>,<rsp>     # Request/response sizes
-b <num>           # Burst size
-s/-S <size>       # Socket buffer sizes
-m <size>          # Message size (UDP)

# Output Formats
-J                 # JSON output
-o csv             # CSV output
-o keyval          # KEYVAL (default)
-k <selectors>     # Custom output selectors

# Multi-Instance
netperf-multi -H <host> -n <N> -- <omni-options>
```

---

**End of OMNI Reference Guide**
