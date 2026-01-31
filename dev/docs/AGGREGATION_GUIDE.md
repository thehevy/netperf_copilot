# Netperf Aggregation Guide

Complete guide to using the `netperf-aggregate` tool for result analysis.

**Version:** 1.0.0  
**Last Updated:** 2026-01-30

---

## Overview

`netperf-aggregate` is a Python tool for parsing, aggregating, comparing, and reporting netperf test results across multiple runs.

**Features:**

- Parse JSON, CSV, and key=value formats
- Calculate comprehensive statistics
- Compare baseline vs current results
- Detect performance regressions
- Generate reports in multiple formats

---

## Installation

The tool is included with netperf fork and requires Python 3.6+:

```bash
# Already included in dev/tools/
chmod +x dev/tools/netperf-aggregate

# Add to PATH (optional)
sudo ln -s /opt/netperf/dev/tools/netperf-aggregate /usr/local/bin/
```

**Dependencies:** Python 3.6+ standard library only (no external packages required)

---

## Quick Start

```bash
# Aggregate multiple test runs
netperf-aggregate results/*.json --stats

# Compare baseline vs current
netperf-aggregate baseline.json current.json --compare

# Generate report
netperf-aggregate results/*.json --report markdown -o report.md
```

---

## Command Reference

### Syntax

```
netperf-aggregate [options] file [file ...]
```

### Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Show help message |
| `-o, --output FILE` | Output file (default: stdout or auto-named) |
| `--stats` | Calculate and display statistics |
| `--compare` | Compare first file (baseline) vs rest (current) |
| `--report FORMAT` | Generate report (text, json, markdown, md) |
| `-v, --version` | Show version information |

---

## Usage Examples

### 1. Basic Aggregation

Collect statistics from multiple test runs:

```bash
# Run multiple tests
for i in {1..10}; do
    netperf -H host -l 10 -- -J > test_${i}.json
done

# Aggregate results
netperf-aggregate test_*.json --stats
```

**Output:**

```
============================================================
Netperf Aggregated Statistics
============================================================

THROUGHPUT:
  Count:   10
  Mean:    9420.34
  Median:  9418.50
  StdDev:  45.23
  Min:     9350.10
  Max:     9489.90
  P50:     9418.50
  P90:     9475.20
  P95:     9482.30
  P99:     9489.90

LATENCY:
  Count:   10
  Mean:    42.15
  Median:  41.80
  StdDev:  2.34
  Min:     38.90
  Max:     46.20
  P50:     41.80
  P90:     45.10
  P95:     45.80
  P99:     46.20
```

### 2. Comparison Mode

Compare a baseline test against current results:

```bash
# Establish baseline
netperf -H host -l 60 -- -J > baseline.json

# Run current tests
netperf -H host -l 60 -- -J > current.json

# Compare
netperf-aggregate baseline.json current.json --compare
```

**Output:**

```
============================================================
Netperf Results Comparison
============================================================

THROUGHPUT:
  Baseline Mean: 9500.00
  Current Mean:  9420.34
  Change:        -79.66 (-0.8%)
  Status:        → STABLE

LATENCY:
  Baseline Mean: 40.50
  Current Mean:  42.15
  Change:        +1.65 (+4.1%)
  Status:        → STABLE

LOCAL_CPU:
  Baseline Mean: 12.0
  Current Mean:  15.2
  Change:        +3.2 (+26.7%)
  Status:        ⚠ REGRESSION
```

### 3. Report Generation

#### JSON Report

```bash
netperf-aggregate results/*.json --stats --report json -o stats.json
```

**Output (stats.json):**

```json
{
  "throughput": {
    "count": 10,
    "mean": 9420.34,
    "median": 9418.50,
    "stddev": 45.23,
    "min": 9350.10,
    "max": 9489.90,
    "p50": 9418.50,
    "p90": 9475.20,
    "p95": 9482.30,
    "p99": 9489.90,
    "variance": 2045.75,
    "range": 139.80,
    "coefficient_of_variation": 0.48
  }
}
```

#### Markdown Report

```bash
netperf-aggregate results/*.json --stats --report markdown -o report.md
```

**Output (report.md):**

```markdown
# Netperf Aggregated Statistics

Generated: 2026-01-30 10:15:32

## THROUGHPUT

| Statistic | Value |
|-----------|-------|
| Count | 10 |
| Mean | 9420.34 |
| Median | 9418.50 |
| Std Dev | 45.23 |
| Min | 9350.10 |
| Max | 9489.90 |
| P50 | 9418.50 |
| P90 | 9475.20 |
| P95 | 9482.30 |
| P99 | 9489.90 |
```

### 4. Mixed Format Input

Tool auto-detects format based on file extension:

```bash
netperf-aggregate \
    results.json \
    results.csv \
    results.txt \
    --stats
```

Supported formats:

- `.json` - JSON format
- `.csv` - CSV with headers
- `.txt`, `.dat` - Key=value format
- No extension - Tries key=value, then JSON

---

## Statistics Reference

### Calculated Metrics

| Statistic | Description | Formula |
|-----------|-------------|---------|
| **count** | Number of samples | n |
| **mean** | Average value | Σx / n |
| **median** | Middle value | x[n/2] |
| **stddev** | Standard deviation | sqrt(Σ(x-μ)² / (n-1)) |
| **variance** | Variance | Σ(x-μ)² / (n-1) |
| **min** | Minimum value | min(x) |
| **max** | Maximum value | max(x) |
| **range** | Value range | max - min |
| **p50** | 50th percentile | Median |
| **p90** | 90th percentile | Value at 90% |
| **p95** | 95th percentile | Value at 95% |
| **p99** | 99th percentile | Value at 99% |
| **coefficient_of_variation** | Relative variability | (stddev / mean) × 100 |

### Tracked Metrics

Automatically tracked from netperf output:

- **throughput** - Network throughput (THROUGHPUT field)
- **latency** - Mean latency (MEAN_LATENCY or RT_LATENCY field)
- **local_cpu** - Local CPU utilization (LOCAL_CPU_UTIL field)
- **remote_cpu** - Remote CPU utilization (REMOTE_CPU_UTIL field)

---

## Comparison Thresholds

When using `--compare`, changes are classified as:

| Change | Threshold | Status |
|--------|-----------|--------|
| > +5% | Increase > 5% | ✓ IMPROVEMENT |
| -5% to +5% | Within ±5% | → STABLE |
| < -5% | Decrease > 5% | ⚠ REGRESSION |

These thresholds are designed for throughput metrics. Latency uses inverted logic (lower is better).

---

## Integration Examples

### 1. CI/CD Pipeline

```bash
#!/bin/bash
# ci-performance-check.sh

BASELINE="baseline/throughput.json"
THRESHOLD=5  # 5% regression threshold

# Run current test
netperf -H $TEST_HOST -l 60 -- -J > current.json

# Compare and check for regression
netperf-aggregate $BASELINE current.json --compare --report json -o comparison.json

# Parse results
CHANGE=$(jq -r '.differences.throughput.percent_change' comparison.json)

if (( $(echo "$CHANGE < -$THRESHOLD" | bc -l) )); then
    echo "FAIL: Performance regression detected: ${CHANGE}%"
    exit 1
else
    echo "PASS: Performance within acceptable range: ${CHANGE}%"
    exit 0
fi
```

### 2. Nightly Performance Report

```bash
#!/bin/bash
# nightly-performance-report.sh

LOG_DIR="/var/log/netperf"
REPORT_DIR="/var/www/reports"
DATE=$(date +%Y-%m-%d)

# Aggregate yesterday's results
netperf-aggregate $LOG_DIR/$(date -d yesterday +%Y%m%d)_*.json \
    --stats \
    --report markdown \
    -o $REPORT_DIR/report_${DATE}.md

# Generate summary statistics
netperf-aggregate $LOG_DIR/$(date -d yesterday +%Y%m%d)_*.json \
    --stats \
    --report json \
    -o $REPORT_DIR/stats_${DATE}.json

# Email report
mail -s "Netperf Daily Report - $DATE" \
    -a $REPORT_DIR/report_${DATE}.md \
    team@example.com < /dev/null
```

### 3. Continuous Monitoring with Alerting

```python
#!/usr/bin/env python3
# monitor-and-alert.py

import subprocess, json, sys

BASELINE_FILE = "baseline.json"
THRESHOLD = 10  # 10% degradation triggers alert

def run_test(host):
    result = subprocess.run(
        ['netperf', '-H', host, '-l', '60', '--', '-J'],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def compare_with_baseline(current_file):
    result = subprocess.run(
        ['netperf-aggregate', BASELINE_FILE, current_file, 
         '--compare', '--report', 'json', '-o', 'comparison.json'],
        capture_output=True
    )
    
    with open('comparison.json') as f:
        return json.load(f)

def send_alert(metric, change):
    # Send alert via email, Slack, PagerDuty, etc.
    print(f"ALERT: {metric} degraded by {abs(change):.1f}%")

# Run test
current = run_test('test-host')
with open('current.json', 'w') as f:
    json.dump(current, f)

# Compare
comparison = compare_with_baseline('current.json')

# Check thresholds
for metric, data in comparison['differences'].items():
    if data['is_regression']:
        change = data['percent_change']
        if abs(change) > THRESHOLD:
            send_alert(metric, change)
```

### 4. Weekly Trend Analysis

```bash
#!/bin/bash
# weekly-trend-analysis.sh

RESULTS_DIR="/var/log/netperf"
REPORT_FILE="weekly_trend_$(date +%Y_W%V).md"

# Get all results from last 7 days
find $RESULTS_DIR -name "*.json" -mtime -7 -print0 | \
    xargs -0 netperf-aggregate --stats --report markdown -o $REPORT_FILE

# Generate comparison vs previous week
LAST_WEEK=$(date -d "7 days ago" +%Y_W%V)
if [ -f "weekly_trend_${LAST_WEEK}.json" ]; then
    # Get this week's aggregate
    find $RESULTS_DIR -name "*.json" -mtime -7 -print0 | \
        xargs -0 netperf-aggregate --stats --report json -o this_week.json
    
    # Compare
    netperf-aggregate \
        weekly_trend_${LAST_WEEK}.json \
        this_week.json \
        --compare >> $REPORT_FILE
fi
```

---

## Advanced Usage

### Custom Metric Extraction

You can extend the tool to track additional metrics:

```python
# Example: Track custom metrics
class NetperfResult:
    def get_custom_metric(self) -> Optional[float]:
        """Extract custom metric from results"""
        for key in ['CUSTOM_METRIC', 'MY_FIELD']:
            if key in self.results:
                return float(self.results[key])
        return None
```

### Batch Processing

Process large numbers of files efficiently:

```bash
# Group by host
for host in host1 host2 host3; do
    netperf-aggregate results_${host}_*.json \
        --stats \
        --report json \
        -o stats_${host}.json
done

# Aggregate all hosts
netperf-aggregate stats_*.json \
    --stats \
    --report markdown \
    -o overall_summary.md
```

### Integration with Data Analysis

```python
#!/usr/bin/env python3
# advanced-analysis.py

import json, pandas as pd, matplotlib.pyplot as plt

# Load aggregated statistics
with open('stats.json') as f:
    stats = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(stats).T

# Plot
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# Throughput
axes[0,0].bar(df.index, df['mean'])
axes[0,0].set_title('Mean Throughput by Metric')
axes[0,0].set_ylabel('Mbps')

# Distribution
axes[0,1].boxplot([df['min'], df['median'], df['max']])
axes[0,1].set_title('Distribution')

# Variability
axes[1,0].bar(df.index, df['coefficient_of_variation'])
axes[1,0].set_title('Coefficient of Variation')
axes[1,0].set_ylabel('%')

# Percentiles
axes[1,1].plot(df.index, df['p90'], label='P90')
axes[1,1].plot(df.index, df['p95'], label='P95')
axes[1,1].plot(df.index, df['p99'], label='P99')
axes[1,1].legend()
axes[1,1].set_title('Latency Percentiles')

plt.tight_layout()
plt.savefig('analysis.png', dpi=300)
```

---

## Troubleshooting

### No Results Found

**Problem:** `Error: No valid results found in input files`

**Causes:**

1. File format not recognized
2. JSON parse errors
3. Empty or corrupted files

**Solutions:**

```bash
# Check file format
file results.json

# Validate JSON
jq . results.json

# Check file contents
head -20 results.json

# Try explicit format
netperf-aggregate results.txt --format keyval
```

### Missing Metrics

**Problem:** Some metrics show no data in aggregation

**Cause:** Field names don't match expected names

**Solution:** Check field names in source files:

```bash
# For JSON
jq '.results | keys' results.json

# For keyval
grep -E "^[A-Z_]+=" results.txt | cut -d= -f1 | sort -u
```

### Performance with Large Datasets

**Problem:** Slow processing of many files

**Solutions:**

```bash
# Process in batches
for batch in batch_*; do
    netperf-aggregate $batch/*.json --stats -o ${batch}_summary.json
done

# Parallel processing
parallel 'netperf-aggregate {} --stats -o {.}_summary.json' ::: *.json
```

---

## See Also

- [OUTPUT_FORMATS.md](OUTPUT_FORMATS.md) - Output format details
- [OUTPUT_INTEGRATION.md](OUTPUT_INTEGRATION.md) - Integration examples
- [PHASE2_FEATURES.md](PHASE2_FEATURES.md) - Technical implementation
