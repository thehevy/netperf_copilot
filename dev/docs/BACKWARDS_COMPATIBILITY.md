# Backwards Compatibility Guide

## The Problem

Different netperf output formats can break existing parsing scripts:

### TCP_STREAM (Legacy) Output
```
Recv   Send    Send                          
Socket Socket  Message  Elapsed              
Size   Size    Size     Time     Throughput  
bytes  bytes   bytes    secs.    10^6bits/sec
87380  65536  65536    5.00     45234.67
```

### OMNI (Modern) Demo Output  
```
Local   Remote  Local  Elapsed Throughput Throughput
Send    Recv    Send   Time               Units
Socket  Socket  Size   (sec)                         
Final   Final                                        
65536   87380   65536  5.00    45234.67   10^6bits/s
```

### OMNI Keyval Output (Recommended for New Scripts)
```
THROUGHPUT=45234.67
THROUGHPUT_UNITS=10^6bits/s
ELAPSED_TIME=5.00
PROTOCOL=TCP
...
```

**Scripts expecting TCP_STREAM columnar format will break with OMNI demo output!**

---

## Solution: Explicit Output Control

### Option 1: Always Specify Test Type (Recommended for Compatibility)

```bash
# Force legacy TCP_STREAM behavior (100% compatible)
netperf -H host -t TCP_STREAM -l 30

# Existing scripts should be updated:
# OLD: netperf -H host
# NEW: netperf -H host -t TCP_STREAM
```

### Option 2: Use Keyval Format (Recommended for New Scripts)

```bash
# Modern keyval format - easier to parse
netperf -H host -t OMNI -o keyval -l 30

# Extract values easily:
netperf -H host -t OMNI -o keyval | grep "^THROUGHPUT=" | cut -d= -f2
```

### Option 3: Environment Variable Configuration

Set defaults via environment variables:

```bash
# Force keyval output for all netperf commands
export NETPERF_OUTPUT_FORMAT=keyval

# Now this returns keyval format:
netperf -H host -l 30

# Or in scripts:
NETPERF_OUTPUT_FORMAT=keyval netperf -H host -l 30
```

### Option 4: Wrapper Script

Create a wrapper that enforces your preferred defaults:

```bash
#!/bin/bash
# /usr/local/bin/netperf-legacy
# Wrapper for 100% backwards compatible behavior

exec /path/to/netperf -t TCP_STREAM "$@"
```

```bash
#!/bin/bash
# /usr/local/bin/netperf-modern
# Wrapper for modern keyval output

exec /path/to/netperf -o keyval "$@"
```

---

## Recommendations by Use Case

### Existing Production Scripts
**Use explicit `-t TCP_STREAM`**
```bash
# Update existing scripts:
for i in {1..10}; do
  netperf -H host -t TCP_STREAM -l 30
done | awk '/^[0-9]/ {print $5}'  # Extract throughput
```

### New Scripts/Automation
**Use keyval format with explicit parsing**
```bash
# Better for new scripts:
for i in {1..10}; do
  netperf -H host -o keyval -l 30
done | grep "^THROUGHPUT=" | cut -d= -f2
```

### CI/CD Pipelines
**Use JSON format for structured data**
```bash
# Best for automation:
netperf -H host -- -J > results.json
jq '.THROUGHPUT' results.json
```

### Interactive Testing
**Use demo mode (OMNI default) for human-readable output**
```bash
# Good for human reading:
netperf -H host -l 30
# Shows columnar format with headers
```

---

## Migration Strategy

### Step 1: Audit Existing Scripts

Find scripts that call netperf:
```bash
grep -r "netperf " /path/to/scripts/
```

### Step 2: Test Output Format

Check what format your scripts expect:
```bash
# Run existing script with debug
bash -x your_script.sh 2>&1 | tee debug.log

# Check parsing logic
grep -A5 "netperf" your_script.sh
```

### Step 3: Update Scripts

Add explicit test type:
```bash
# Before:
netperf -H $HOST

# After (legacy compatible):
netperf -H $HOST -t TCP_STREAM

# Or (modern, easier parsing):
netperf -H $HOST -o keyval | grep "^THROUGHPUT=" | cut -d= -f2
```

### Step 4: Add Format Checks

Make scripts robust:
```bash
#!/bin/bash
OUTPUT=$(netperf -H host -t TCP_STREAM -l 5)

# Check if output looks correct
if echo "$OUTPUT" | grep -q "Throughput"; then
  RESULT=$(echo "$OUTPUT" | awk '/^[0-9]/ {print $5}')
  echo "Throughput: $RESULT"
else
  echo "ERROR: Unexpected output format" >&2
  exit 1
fi
```

---

## Coexistence with System Netperf

If netperf is installed via package manager (yum/apt):

### Check System Version
```bash
# Find system netperf
which netperf

# Check version
netperf -V

# Check default behavior
netperf -H localhost -l 1 2>&1 | head -5
```

### Use Absolute Paths
```bash
# Use built version explicitly
/opt/netperf/build/src/netperf -H host

# Or add to PATH
export PATH="/opt/netperf/build/src:$PATH"
which netperf  # Should show /opt/netperf/build/src/netperf
```

### Service Detection

Check if netserver is running as system service:
```bash
# SystemD
systemctl status netserver

# Process check
ps aux | grep netserver

# Don't start conflicting netserver:
# System: /usr/bin/netserver (port 12865)
# Built:  /opt/netperf/build/src/netserver (use different port)
/opt/netperf/build/src/netserver -p 12866
```

---

## Configuration File Support (Future)

Planned feature for v3.1:

```bash
# ~/.netperfrc or /etc/netperf.conf
default_output_format=keyval
default_test_type=OMNI
default_duration=30
```

```bash
# Would allow:
netperf -H host  # Uses keyval output automatically
```

---

## Quick Reference

| Goal | Command |
|------|---------|
| Legacy compatible | `netperf -H host -t TCP_STREAM` |
| Easy parsing | `netperf -H host -o keyval` |
| JSON output | `netperf -H host -- -J` |
| Human readable | `netperf -H host` (default demo) |
| 100% backwards | Create wrapper script with `-t TCP_STREAM` |

---

## Testing Compatibility

Test your scripts with both formats:

```bash
# Test 1: Legacy TCP_STREAM
OUTPUT=$(netperf -H host -t TCP_STREAM -l 5)
echo "$OUTPUT" | awk '/^[0-9]/ {print "TCP_STREAM:", $5}'

# Test 2: OMNI demo (current default)
OUTPUT=$(netperf -H host -l 5)
echo "$OUTPUT" | grep -A1 "Final" | tail -1 | awk '{print "OMNI:", $4}'

# Test 3: OMNI keyval  
OUTPUT=$(netperf -H host -o keyval -l 5)
echo "$OUTPUT" | grep "^THROUGHPUT=" | cut -d= -f2
```

If all three produce numbers, your parsing is format-agnostic!

---

## Support

- File issues: https://github.com/thehevy/netperf_copilot/issues
- Tag with: `backwards-compatibility`
- Include: netperf version, expected vs actual output
