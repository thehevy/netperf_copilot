# Netperf Output Formats Reference

Complete reference for all output formats supported by netperf.

**Version:** 2.7.1-fork (Phase 2)  
**Last Updated:** 2026-01-30

---

## Overview

Netperf supports four primary output formats:

1. **KEYVAL** (Key-Value) - Human-readable, parseable (default)
2. **CSV** - Comma-Separated Values with headers and escaping
3. **JSON** - Structured JSON with metadata
4. **HUMAN** - Traditional columnar format

---

## Format Comparison

| Feature | KEYVAL | CSV | JSON | HUMAN |
|---------|--------|-----|------|-------|
| Default | ✓ | | | |
| Headers | No | Yes | Yes (metadata) | Yes |
| Parseable | ✓ | ✓ | ✓ | |
| Structured | | | ✓ | |
| Metadata | | | ✓ | |
| Append-friendly | ✓ | ✓ | | |
| Excel-compatible | | ✓ | | |
| Machine-readable | ✓ | ✓ | ✓ | |
| Human-readable | ✓ | | | ✓ |

---

## 1. KEYVAL Format (Default)

**Description:** Simple key=value pairs, one per line.

**When to use:**
- Default output format
- Simple scripts and automation
- Grepping for specific values
- Appending to log files

**Example:**
```
THROUGHPUT=9420.15
THROUGHPUT_UNITS=10^6bits/s
ELAPSED_TIME=10.00
LOCAL_CPU_UTIL=12.4
REMOTE_CPU_UTIL=15.8
PROTOCOL=TCP
COMMAND_LINE=./netperf -H 192.168.10.2 -l 10 -c -C
```

**Usage:**
```bash
# KEYVAL is the default
netperf -H host

# Extract specific value
netperf -H host | grep THROUGHPUT= | cut -d= -f2
```

**Parsing (shell):**
```bash
while IFS='=' read -r key value; do
    case $key in
        THROUGHPUT) throughput=$value ;;
        LOCAL_CPU_UTIL) cpu=$value ;;
    esac
done < results.txt
```

**Parsing (Python):**
```python
results = {}
with open('results.txt') as f:
    for line in f:
        if '=' in line:
            key, value = line.strip().split('=', 1)
            results[key] = value
```

---

## 2. CSV Format

**Description:** Comma-separated values with header row and proper RFC 4180 escaping.

**When to use:**
- Excel/spreadsheet import
- Database imports
- Time-series data collection
- Batch processing multiple tests

**Example:**
```csv
THROUGHPUT,THROUGHPUT_UNITS,ELAPSED_TIME,LOCAL_CPU_UTIL,REMOTE_CPU_UTIL,PROTOCOL
9420.15,10^6bits/s,10.00,12.4,15.8,TCP
9385.22,10^6bits/s,10.00,12.1,15.9,TCP
9456.78,10^6bits/s,10.00,12.6,15.7,TCP
```

**Usage:**
```bash
# CSV output with header
netperf -H host -- -o csv

# Multiple tests to same file
for i in {1..10}; do
    netperf -H host -- -o csv >> results.csv
done
```

**Features:**
- **Header row:** First line contains field names
- **Field escaping:** Handles quotes, commas, newlines
- **Header management:** Header printed only once
- **Delimiter:** Comma (customizable in future)

**Escaping Rules:**
- Fields containing `,` → quoted with `"`
- Fields containing `"` → quotes doubled (`""`)
- Fields containing newlines → quoted
- Empty fields → empty (not NULL)

**Example with escaping:**
```csv
TEST_NAME,COMMAND_LINE,THROUGHPUT
TCP_STREAM,"./netperf -H host -t TCP_STREAM -- -m 1024,1024",9420.15
"TCP,UDP_MIX","./netperf -H ""special"" host",8500.32
```

**Parsing (Python):**
```python
import csv
with open('results.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        throughput = float(row['THROUGHPUT'])
        cpu = float(row['LOCAL_CPU_UTIL'])
```

---

## 3. JSON Format

**Description:** Structured JSON with metadata and hierarchical organization.

**When to use:**
- API integrations
- Modern monitoring systems (Prometheus, Grafana)
- Complex data analysis
- Archival with full context

**Example:**
```json
{
  "metadata": {
    "netperf_version": "2.7.1-fork",
    "timestamp": "2026-01-30T10:15:32Z",
    "hostname": "testclient.local",
    "platform": "Linux 6.12.0 x86_64"
  },
  "results": {
    "THROUGHPUT": 9420.15,
    "THROUGHPUT_UNITS": "10^6bits/s",
    "ELAPSED_TIME": 10.00,
    "LOCAL_CPU_UTIL": 12.4,
    "REMOTE_CPU_UTIL": 15.8,
    "PROTOCOL": "TCP",
    "COMMAND_LINE": "./netperf -H 192.168.10.2 -l 10 -c -C"
  }
}
```

**Usage:**
```bash
# JSON output
netperf -H host -- -J

# Pretty-print with jq
netperf -H host -- -J | jq .

# Extract specific field
netperf -H host -- -J | jq -r '.results.THROUGHPUT'
```

**Schema:**

The JSON output follows this structure:

```typescript
{
  metadata: {
    netperf_version: string;      // Version string
    timestamp: string;             // ISO 8601 UTC timestamp
    hostname: string;              // Client hostname
    platform?: string;             // OS platform info
  },
  results: {
    [metric: string]: number | string;  // All test metrics
  }
}
```

**Type Handling:**
- Numeric values: Not quoted (JSON numbers)
- String values: Quoted (JSON strings)
- No trailing commas (valid JSON)

**Parsing (Python):**
```python
import json
with open('results.json') as f:
    data = json.load(f)
    
print(f"Test run at: {data['metadata']['timestamp']}")
print(f"Throughput: {data['results']['THROUGHPUT']}")
```

**Parsing (jq examples):**
```bash
# Extract throughput
jq -r '.results.THROUGHPUT' results.json

# Get metadata
jq '.metadata' results.json

# Multiple files
jq -s '.' *.json  # Combine into array
```

---

## 4. HUMAN Format (Columnar)

**Description:** Traditional netperf columnar output with aligned columns.

**When to use:**
- Terminal/console viewing
- Legacy scripts expecting old format
- Visual inspection

**Example:**
```
MIGRATED TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 192.168.10.2 () port 0 AF_INET
Recv   Send    Send                          
Socket Socket  Message  Elapsed              
Size   Size    Size     Time     Throughput  
bytes  bytes   bytes    secs.    10^6bits/s  

 87380  16384  16384    10.00        9420.15   
```

**Usage:**
```bash
# Explicitly request HUMAN format
netperf -H host -- -O human

# Or use -P 1 for print headers
netperf -H host -P 1
```

---

## Format Selection

### Command-Line Options

```bash
# KEYVAL (default)
netperf -H host

# CSV
netperf -H host -- -o csv

# JSON  
netperf -H host -- -J

# HUMAN/Columnar
netperf -H host -- -O human
```

### Output Presets

Use `-k` or `-P` with preset files:

```bash
# Use preset with any format
netperf -H host -- -k /path/to/preset.txt -J       # JSON with preset
netperf -H host -- -k /path/to/preset.txt -o csv   # CSV with preset
```

---

## Field Reference

### Common Fields

| Field | Type | Description | Units |
|-------|------|-------------|-------|
| THROUGHPUT | float | Network throughput | 10^6bits/s |
| THROUGHPUT_UNITS | string | Units for throughput | varies |
| ELAPSED_TIME | float | Test duration | seconds |
| LOCAL_CPU_UTIL | float | Local CPU utilization | percent |
| REMOTE_CPU_UTIL | float | Remote CPU utilization | percent |
| PROTOCOL | string | Protocol used | TCP/UDP/SCTP |
| SOCKET_SIZE_SEND | int | Send socket buffer | bytes |
| SOCKET_SIZE_RECV | int | Receive socket buffer | bytes |
| SEND_SIZE | int | Send message size | bytes |
| RECV_SIZE | int | Receive message size | bytes |
| REQUEST_SIZE | int | Request size (RR tests) | bytes |
| RESPONSE_SIZE | int | Response size (RR tests) | bytes |
| TRANSACTION_RATE | float | Transactions per second | tps |
| MEAN_LATENCY | float | Mean latency | microseconds |
| MIN_LATENCY | float | Minimum latency | microseconds |
| MAX_LATENCY | float | Maximum latency | microseconds |
| P50_LATENCY | float | 50th percentile latency | microseconds |
| P90_LATENCY | float | 90th percentile latency | microseconds |
| P99_LATENCY | float | 99th percentile latency | microseconds |
| LOCAL_SEND_CALLS | int | Number of send calls | count |
| LOCAL_RECV_CALLS | int | Number of receive calls | count |
| LOCAL_BYTES_SENT | int | Total bytes sent | bytes |
| LOCAL_BYTES_RECVD | int | Total bytes received | bytes |
| REMOTE_BYTES_SENT | int | Remote bytes sent | bytes |
| REMOTE_BYTES_RECVD | int | Remote bytes received | bytes |
| CONFIDENCE_LEVEL | int | Confidence level | percent |
| CONFIDENCE_INTERVAL | float | Confidence interval | percent |
| COMMAND_LINE | string | Full command line | string |

### Interval Fields (with -D)

When using interval reporting (`-D`), additional fields:

| Field | Type | Description |
|-------|------|-------------|
| INTERVAL_ID | int | Interval number |
| INTERVAL_THROUGHPUT | float | Throughput for this interval |
| INTERVAL_DURATION | float | Actual interval duration |
| CUMULATIVE_THROUGHPUT | float | Cumulative average throughput |

---

## Output Presets

Presets control which fields are included in output.

### Built-in Presets

Located in `dev/catalog/output-presets/`:

1. **minimal.txt** - Essential metrics only
2. **default.txt** - Standard metrics (active by default)
3. **verbose.txt** - All available metrics
4. **latency.txt** - Latency-focused metrics
5. **throughput.txt** - Throughput-focused metrics  
6. **cpu.txt** - CPU utilization focused

### Using Presets

```bash
# Use built-in preset
netperf -H host -- -k throughput

# Use custom preset file
netperf -H host -- -k /path/to/my-preset.txt

# Preset with format
netperf -H host -- -k throughput -J      # JSON
netperf -H host -- -k latency -o csv     # CSV
```

### Creating Custom Presets

Create a text file with field names (one per line):

```
# my-preset.txt
THROUGHPUT
THROUGHPUT_UNITS  
ELAPSED_TIME
LOCAL_CPU_UTIL
REMOTE_CPU_UTIL
MEAN_LATENCY
P99_LATENCY
COMMAND_LINE
```

---

## Best Practices

### For Automation

1. **Use KEYVAL or JSON** - Both are easily parseable
2. **Always include COMMAND_LINE** - Documents how test was run
3. **Add timestamps** - JSON includes this automatically
4. **Use presets** - Consistent fields across tests

### For Archival

1. **Use JSON format** - Includes full metadata
2. **Compress old results** - `gzip *.json` works well
3. **Use descriptive filenames** - Include date/host/test type

### For Analysis

1. **Use CSV for time-series** - Easy to import to Excel/pandas
2. **Use JSON for single tests** - Best for detailed analysis
3. **Use netperf-aggregate tool** - Built-in statistics and comparison

### For CI/CD

1. **Use JSON** - Easiest for programmatic parsing
2. **Compare with baselines** - Use netperf-aggregate --compare
3. **Set thresholds** - Parse JSON and fail if below threshold

---

## Examples

### Collect Time-Series Data

```bash
#!/bin/bash
# Collect TCP throughput every minute for 1 hour

echo "Starting throughput monitoring..."
for i in {1..60}; do
    netperf -H $HOST -l 10 -- -o csv >> throughput.csv
    sleep 50  # 10s test + 50s wait = 1 minute
done
echo "Done. Results in throughput.csv"
```

### Parse and Alert

```bash
#!/bin/bash
# Run test and alert if throughput drops below threshold

THRESHOLD=8000  # Mbps

RESULT=$(netperf -H $HOST -- -J)
THROUGHPUT=$(echo $RESULT | jq -r '.results.THROUGHPUT')

if (( $(echo "$THROUGHPUT < $THRESHOLD" | bc -l) )); then
    echo "ALERT: Throughput $THROUGHPUT < $THRESHOLD" | mail -s "Network Alert" admin@example.com
fi
```

### Multi-Host Testing

```bash
#!/bin/bash
# Test multiple hosts and aggregate

HOSTS="host1 host2 host3"

for host in $HOSTS; do
    netperf -H $host -l 60 -- -J > results_${host}.json
done

# Aggregate results
netperf-aggregate results_*.json --stats --report markdown -o summary.md
```

---

## Troubleshooting

### CSV Headers Appearing Multiple Times

**Problem:** Headers appear in output multiple times  
**Solution:** Headers are printed only on first call. If running in a loop, they appear once per process.

```bash
# Wrong - headers in every iteration
for i in {1..10}; do
    netperf -H host -- -o csv > result_${i}.csv
done

# Right - single output file
for i in {1..10}; do
    netperf -H host -- -o csv >> results.csv
done
```

### JSON Parsing Errors

**Problem:** JSON parsing fails  
**Cause:** Likely output mixed with debug/error messages

**Solution:**
```bash
# Redirect stderr to separate file
netperf -H host -- -J 2> errors.log > results.json

# Or suppress debug output
netperf -H host -d 0 -- -J > results.json
```

### KEYVAL Parsing Issues

**Problem:** Values contain `=` character  
**Solution:** Split on first `=` only

```bash
# Wrong
IFS='=' read key value <<< "$line"

# Right
key="${line%%=*}"
value="${line#*=}"
```

---

## See Also

- [OUTPUT_INTEGRATION.md](OUTPUT_INTEGRATION.md) - Integration with monitoring systems
- [PHASE2_FEATURES.md](PHASE2_FEATURES.md) - Phase 2 technical details
- [README.md](../README.md) - Main documentation
- [netperf man page](netperf.man) - Complete options reference
