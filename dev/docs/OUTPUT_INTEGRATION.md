# Netperf Output Integration Guide

Guide for integrating netperf with monitoring, logging, and analysis systems.

**Version:** 2.7.1-fork (Phase 2)  
**Last Updated:** 2026-01-30

---

## Quick Integration Matrix

| System | Format | Method | Difficulty |
|--------|--------|--------|------------|
| Prometheus | JSON/Template | Push Gateway / Textfile Collector | Easy |
| Grafana | JSON | Via Prometheus or JSON API | Easy |
| ELK Stack | JSON | Filebeat → Logstash → Elasticsearch | Medium |
| Splunk | KEYVAL/JSON | Universal Forwarder | Easy |
| InfluxDB | JSON | Telegraf exec plugin | Easy |
| TimescaleDB | CSV/JSON | COPY command or pg_insert | Easy |
| Custom Scripts | Any | Direct parse | Easy |

---

## 1. Prometheus Integration

### Method 1: Node Exporter Textfile Collector

**Best for:** Periodic testing, cron jobs

**Setup:**

1. Configure Node Exporter with textfile collector:
```bash
node_exporter --collector.textfile.directory=/var/lib/node_exporter/textfile
```

2. Create netperf export script:
```bash
#!/bin/bash
# /usr/local/bin/netperf-prometheus-export.sh

OUTPUT_DIR="/var/lib/node_exporter/textfile"
TEMP_FILE="$OUTPUT_DIR/netperf.prom.$$"
PROM_FILE="$OUTPUT_DIR/netperf.prom"

# Run netperf and convert to Prometheus format
netperf -H $1 -l 10 -- -J | python3 -c '
import json, sys
data = json.load(sys.stdin)
r = data["results"]
m = data["metadata"]

print(f"""# TYPE netperf_throughput_mbps gauge
# HELP netperf_throughput_mbps Network throughput in Mbps
netperf_throughput_mbps{{host=\"{r.get("REMOTE_HOST","unknown")}\"}} {r.get("THROUGHPUT",0)}

# TYPE netperf_latency_us gauge
# HELP netperf_latency_us Mean latency in microseconds  
netperf_latency_us{{host=\"{r.get("REMOTE_HOST","unknown")}\"}} {r.get("MEAN_LATENCY",0)}

# TYPE netperf_cpu_utilization_percent gauge
# HELP netperf_cpu_utilization_percent CPU utilization percentage
netperf_cpu_utilization_percent{{host=\"{r.get("REMOTE_HOST","unknown")}\",side=\"local\"}} {r.get("LOCAL_CPU_UTIL",0)}
netperf_cpu_utilization_percent{{host=\"{r.get("REMOTE_HOST","unknown")}\",side=\"remote\"}} {r.get("REMOTE_CPU_UTIL",0)}
""")
' > "$TEMP_FILE"

# Atomic move
mv "$TEMP_FILE" "$PROM_FILE"
```

3. Add to cron:
```cron
*/5 * * * * /usr/local/bin/netperf-prometheus-export.sh netserver-host
```

### Method 2: Pushgateway

**Best for:** Short-lived jobs, on-demand testing

```bash
#!/bin/bash
# Push netperf results to Pushgateway

PUSHGATEWAY="http://pushgateway.local:9091"
JOB="netperf"
INSTANCE=$(hostname)

# Run test
RESULT=$(netperf -H $1 -l 10 -- -J)

# Extract metrics and push
echo "$RESULT" | python3 -c '
import json, sys, requests
data = json.load(sys.stdin)
r = data["results"]

metrics = f"""
netperf_throughput_mbps {r.get("THROUGHPUT", 0)}
netperf_latency_us {r.get("MEAN_LATENCY", 0)}
netperf_cpu_local {r.get("LOCAL_CPU_UTIL", 0)}
netperf_cpu_remote {r.get("REMOTE_CPU_UTIL", 0)}
"""

requests.post(
    f"$PUSHGATEWAY/metrics/job/$JOB/instance/$INSTANCE",
    data=metrics
)
'
```

### Prometheus Queries

```promql
# Average throughput last hour
avg_over_time(netperf_throughput_mbps[1h])

# P95 latency
histogram_quantile(0.95, netperf_latency_us)

# Alert on throughput drop
(netperf_throughput_mbps - netperf_throughput_mbps offset 1d) / netperf_throughput_mbps offset 1d < -0.1
```

---

## 2. Grafana Dashboard

### Provisioning Dashboard

```json
{
  "dashboard": {
    "title": "Netperf Network Performance",
    "panels": [
      {
        "title": "Throughput",
        "targets": [
          {
            "expr": "netperf_throughput_mbps",
            "legendFormat": "{{host}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Latency",
        "targets": [
          {
            "expr": "netperf_latency_us",
            "legendFormat": "{{host}}"
          }
        ],
        "type": "graph"  
      },
      {
        "title": "CPU Utilization",
        "targets": [
          {
            "expr": "netperf_cpu_utilization_percent",
            "legendFormat": "{{host}} - {{side}}"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

### Import JSON Results

Use JSON API datasource plugin:

```javascript
// Grafana JSON datasource query
{
  "targets": [
    {
      "target": "throughput",
      "type": "timeseries"
    }
  ]
}

// Backend implementation
app.post('/query', (req, res) => {
  const results = fs.readdirSync('results')
    .filter(f => f.endsWith('.json'))
    .map(f => {
      const data = JSON.parse(fs.readFileSync(`results/${f}`));
      return {
        target: 'throughput',
        datapoints: [[
          data.results.THROUGHPUT,
          new Date(data.metadata.timestamp).getTime()
        ]]
      };
    });
  res.json(results);
});
```

---

## 3. ELK Stack (Elasticsearch, Logstash, Kibana)

### Filebeat Configuration

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/netperf/*.json
  json.keys_under_root: true
  json.add_error_key: true

output.logstash:
  hosts: ["logstash.local:5044"]
```

### Logstash Configuration  

```ruby
# logstash-netperf.conf
input {
  beats {
    port => 5044
  }
}

filter {
  json {
    source => "message"
  }
  
  date {
    match => ["metadata.timestamp", "ISO8601"]
    target => "@timestamp"
  }
  
  mutate {
    rename => {
      "[results][THROUGHPUT]" => "throughput"
      "[results][MEAN_LATENCY]" => "latency"
      "[results][LOCAL_CPU_UTIL]" => "cpu_local"
      "[results][REMOTE_CPU_UTIL]" => "cpu_remote"
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch.local:9200"]
    index => "netperf-%{+YYYY.MM.dd}"
  }
}
```

### Kibana Visualization

1. Create index pattern: `netperf-*`
2. Add visualizations:
   - Line chart: `throughput` over time
   - Gauge: Current `latency`
   - Bar chart: `cpu_local` vs `cpu_remote`

---

## 4. Splunk Integration

### Universal Forwarder

```ini
# /opt/splunkforwarder/etc/apps/netperf/local/inputs.conf
[monitor:///var/log/netperf/*.json]
disabled = false
sourcetype = netperf:json
index = network_performance

[monitor:///var/log/netperf/*.txt]
disabled = false  
sourcetype = netperf:keyval
index = network_performance
```

### Props Configuration

```ini
# props.conf
[netperf:json]
SHOULD_LINEMERGE = false
KV_MODE = json
TIME_PREFIX = "timestamp"\s*:\s*"
TIME_FORMAT = %Y-%m-%dT%H:%M:%SZ
MAX_TIMESTAMP_LOOKAHEAD = 25

[netperf:keyval]
SHOULD_LINEMERGE = false
KV_MODE = auto
FIELD_DELIMITER = =
```

### Splunk Queries

```spl
# Average throughput last hour
index=network_performance sourcetype=netperf:json
| stats avg(results.THROUGHPUT) as avg_throughput by metadata.hostname

# Latency trend
index=network_performance sourcetype=netperf:json
| timechart avg(results.MEAN_LATENCY) by metadata.hostname

# Alert on performance degradation
index=network_performance sourcetype=netperf:json
| eventstats avg(results.THROUGHPUT) as baseline
| eval degradation = (baseline - results.THROUGHPUT) / baseline * 100
| where degradation > 10
```

---

## 5. InfluxDB Integration

### Using Telegraf

```toml
# telegraf.conf
[[inputs.exec]]
  commands = ["/usr/local/bin/netperf-influx.sh"]
  timeout = "30s"
  data_format = "json"
  json_name_key = "measurement"
  json_string_fields = ["PROTOCOL", "COMMAND_LINE"]
  tag_keys = ["metadata_hostname", "results_PROTOCOL"]
  json_time_key = "metadata_timestamp"
  json_time_format = "2006-01-02T15:04:05Z07:00"

[[outputs.influxdb_v2]]
  urls = ["http://influxdb.local:8086"]
  token = "$INFLUX_TOKEN"
  organization = "myorg"
  bucket = "netperf"
```

### Netperf Script for Telegraf

```bash
#!/bin/bash
# /usr/local/bin/netperf-influx.sh

netperf -H $TARGET_HOST -l 10 -- -J | jq '{
  measurement: "network_performance",
  metadata_hostname: .metadata.hostname,
  metadata_timestamp: .metadata.timestamp,
  results_THROUGHPUT: .results.THROUGHPUT,
  results_MEAN_LATENCY: .results.MEAN_LATENCY,
  results_LOCAL_CPU_UTIL: .results.LOCAL_CPU_UTIL,
  results_REMOTE_CPU_UTIL: .results.REMOTE_CPU_UTIL,
  results_PROTOCOL: .results.PROTOCOL
}'
```

### Flux Queries

```flux
from(bucket: "netperf")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "network_performance")
  |> filter(fn: (r) => r._field == "results_THROUGHPUT")
  |> mean()
```

---

## 6. TimescaleDB / PostgreSQL

### Table Schema

```sql
CREATE TABLE netperf_results (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    hostname VARCHAR(255),
    platform VARCHAR(255),
    throughput NUMERIC,
    throughput_units VARCHAR(50),
    latency NUMERIC,
    cpu_local NUMERIC,
    cpu_remote NUMERIC,
    protocol VARCHAR(50),
    command_line TEXT
);

-- For TimescaleDB
SELECT create_hypertable('netperf_results', 'timestamp');

-- Indexes
CREATE INDEX idx_netperf_timestamp ON netperf_results(timestamp DESC);
CREATE INDEX idx_netperf_hostname ON netperf_results(hostname);
```

### Import CSV

```bash
# Generate CSV
netperf -H host -l 10 -- -o csv > results.csv

# Import to PostgreSQL
psql -d mydb -c "\COPY netperf_results(throughput,latency,cpu_local,cpu_remote,protocol) FROM 'results.csv' CSV HEADER"
```

### Import JSON

```python
import json, psycopg2

conn = psycopg2.connect("dbname=mydb")
cur = conn.cursor()

with open('results.json') as f:
    data = json.load(f)
    
cur.execute("""
    INSERT INTO netperf_results 
    (timestamp, hostname, throughput, latency, cpu_local, cpu_remote, protocol, command_line)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""", (
    data['metadata']['timestamp'],
    data['metadata']['hostname'],
    data['results'].get('THROUGHPUT'),
    data['results'].get('MEAN_LATENCY'),
    data['results'].get('LOCAL_CPU_UTIL'),
    data['results'].get('REMOTE_CPU_UTIL'),
    data['results'].get('PROTOCOL'),
    data['results'].get('COMMAND_LINE')
))

conn.commit()
```

---

## 7. CI/CD Integration

### GitHub Actions

```yaml
name: Network Performance Test

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  network-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install netperf
        run: |
          sudo apt-get update
          sudo apt-get install -y netperf
      
      - name: Run performance test
        run: |
          netperf -H ${{ secrets.TEST_HOST }} -l 60 -- -J > results.json
      
      - name: Check thresholds
        run: |
          THROUGHPUT=$(jq -r '.results.THROUGHPUT' results.json)
          if (( $(echo "$THROUGHPUT < 9000" | bc -l) )); then
            echo "::error::Throughput $THROUGHPUT below threshold 9000"
            exit 1
          fi
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: netperf-results
          path: results.json
      
      - name: Post to monitoring
        run: |
          curl -X POST ${{ secrets.MONITORING_ENDPOINT }} \
            -H "Content-Type: application/json" \
            -d @results.json
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    triggers {
        cron('H */6 * * *')
    }
    stages {
        stage('Network Test') {
            steps {
                sh '''
                    netperf -H ${TEST_HOST} -l 60 -- -J > results.json
                '''
            }
        }
        stage('Analyze') {
            steps {
                script {
                    def results = readJSON file: 'results.json'
                    def throughput = results.results.THROUGHPUT
                    
                    if (throughput < 9000) {
                        error("Throughput ${throughput} below threshold")
                    }
                    
                    currentBuild.description = "Throughput: ${throughput} Mbps"
                }
            }
        }
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'results.json'
            }
        }
    }
    post {
        always {
            sh 'curl -X POST ${INFLUX_URL} --data-binary @results.json'
        }
    }
}
```

---

## 8. Automation Scripts

### Continuous Monitoring

```bash
#!/bin/bash
# continuous-netperf-monitor.sh - Run netperf continuously

LOG_DIR="/var/log/netperf"
INTERVAL=300  # 5 minutes
TARGETS="host1 host2 host3"

mkdir -p "$LOG_DIR"

while true; do
    for target in $TARGETS; do
        timestamp=$(date +%Y%m%d_%H%M%S)
        output_file="$LOG_DIR/${target}_${timestamp}.json"
        
        echo "Testing $target..."
        netperf -H $target -l 60 -- -J > "$output_file" 2>&1
        
        # Send to monitoring
        curl -X POST http://monitoring.local/api/netperf \
            -H "Content-Type: application/json" \
            -d @"$output_file"
    done
    
    # Cleanup old results (keep last 7 days)
    find "$LOG_DIR" -name "*.json" -mtime +7 -delete
    
    sleep $INTERVAL
done
```

### Performance Regression Detection

```python
#!/usr/bin/env python3
# detect-regression.py

import sys, json, statistics

def load_baseline(file):
    with open(file) as f:
        return json.load(f)

def check_regression(current, baseline, threshold=0.05):
    current_tp = current['results']['THROUGHPUT']
    baseline_tp = baseline['results']['THROUGHPUT']
    
    change = (current_tp - baseline_tp) / baseline_tp
    
    if change < -threshold:
        print(f"REGRESSION: Throughput dropped by {abs(change)*100:.1f}%")
        print(f"Baseline: {baseline_tp:.2f}, Current: {current_tp:.2f}")
        return 1
    elif change > threshold:
        print(f"IMPROVEMENT: Throughput increased by {change*100:.1f}%")
    else:
        print(f"STABLE: Within {threshold*100}% of baseline")
    
    return 0

if __name__ == '__main__':
    baseline = load_baseline(sys.argv[1])
    current = load_baseline(sys.argv[2])
    sys.exit(check_regression(current, baseline))
```

---

## See Also

- [OUTPUT_FORMATS.md](OUTPUT_FORMATS.md) - Output format reference
- [AGGREGATION_GUIDE.md](AGGREGATION_GUIDE.md) - Result aggregation
- [PHASE2_FEATURES.md](PHASE2_FEATURES.md) - Technical details
