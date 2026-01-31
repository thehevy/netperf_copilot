# Real-Time Monitoring Guide

## Overview

`netperf-monitor` provides real-time visualization of netperf tests with a terminal-based dashboard showing live metrics, progress tracking, and statistical analysis.

## Features

- **Live Metrics Display**: Real-time throughput, latency, and CPU utilization
- **ASCII Visualizations**: Sparkline graphs, progress bars, and statistics
- **Progress Tracking**: ETA calculation and completion status
- **Statistical Analysis**: Min/Max/Avg/P50/P95/P99 percentiles
- **No External Dependencies**: Pure Python stdlib with ANSI terminal support
- **Flexible Modes**: Live monitoring, file following, and multi-test dashboard

## Installation

```bash
chmod +x dev/tools/netperf-monitor

# No external dependencies required
# Works with Python 3.6+ stdlib only
```

## Basic Usage

### Live Test Monitoring

Monitor a netperf test in real-time:

```bash
./dev/tools/netperf-monitor -H 192.168.1.10 -- -d send -l 60
```

Output displays:

```
 ═══════════════════════ Netperf Live Monitor ═══════════════════════
 2026-01-31 14:23:45
 ────────────────────────────────────────────────────────────────────

 netperf -H 192.168.1.10 [Running]
  [██████████████████████░░░░░░░░░░░░░░░░░░] 60.2%  00:00:36 / 00:00:24

  Throughput  :    9473.56 Mbps  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▃▄▅▆▇█▇▆▅▄▃▂▃▄▅▆▇
                Min: 9200.00 Avg: 9450.32 Max: 9500.00  P50: 9460.00  P95: 9490.00  P99: 9498.00

  Latency     :      125.43 us   ▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█
                Min: 120.00 Avg: 125.10 Max: 130.00  P50: 125.00  P95: 128.00  P99: 129.50

  CPU Local   :       45.20 %    ▅▆▇█▇▆▅▄▃▄▅▆▇█▇▆▅▄▃▄▅▆▇█▇▆▅▄▃
                Min: 42.00 Avg: 45.00 Max: 48.00  P50: 45.00  P95: 47.00  P99: 47.80
```

### Custom Test Duration

```bash
./dev/tools/netperf-monitor -H server -l 120 -- -d send
```

### Custom Refresh Rate

Update display more/less frequently:

```bash
# Fast refresh (250ms)
./dev/tools/netperf-monitor -H server --refresh 0.25 -- -d send -l 60

# Slow refresh (2s)
./dev/tools/netperf-monitor -H server --refresh 2.0 -- -d send -l 60
```

### Different Test Types

```bash
# TCP send (throughput)
./dev/tools/netperf-monitor -H server -- -d send -l 60

# TCP recv (reverse throughput)
./dev/tools/netperf-monitor -H server -- -d recv -l 60

# TCP request-response (latency)
./dev/tools/netperf-monitor -H server -- -d rr -l 60

# UDP throughput
./dev/tools/netperf-monitor -H server -- -d send -T udp -l 60
```

## Advanced Features

### File Following Mode (Not Yet Implemented)

Monitor pre-recorded netperf output:

```bash
# Follow file like tail -f
./dev/tools/netperf-monitor --follow test.log
```

This will be useful for:
- Analyzing historical tests
- Monitoring tests running in screen/tmux
- Post-processing existing output

### Dashboard Mode (Not Yet Implemented)

Monitor multiple tests simultaneously:

```bash
# Multi-test dashboard
./dev/tools/netperf-monitor --dashboard tests.json
```

**tests.json** format:
```json
[
  {
    "name": "Client1 → Server1",
    "host": "192.168.1.10",
    "args": ["-d", "send", "-l", "60"]
  },
  {
    "name": "Client1 → Server2",
    "host": "192.168.1.11",
    "args": ["-d", "send", "-l", "60"]
  }
]
```

Dashboard layout:
```
 ════════════════════════ Netperf Dashboard ════════════════════════
 2026-01-31 14:23:45              4 Tests Running

 Client1 → Server1 [Running]
  [██████████████████████░░░░░░] 70.0%  Throughput: 9473.56 Mbps

 Client1 → Server2 [Running]
  [████████████████████████░░░░] 80.0%  Throughput: 9512.32 Mbps

 Client2 → Server1 [Running]
  [██████████████░░░░░░░░░░░░░░] 50.0%  Throughput: 9401.78 Mbps

 Client2 → Server2 [Complete]
  [████████████████████████████] 100%   Throughput: 9489.11 Mbps (Avg)
```

## Display Elements

### Progress Bar

Shows test completion with ETA:

```
[████████████████████░░░░░░░░░░░] 65.3%  00:00:39 / 00:00:21
 ▲ Filled portion      ▲ Progress  ▲ Elapsed / Remaining
```

### Sparkline Graph

Visualizes metric trends:

```
▁▂▃▄▅▆▇█▇▆▅▄▃▂▃▄▅▆▇█▇▆▅▄▃▂▃▄▅▆▇
▲ Recent history (last N samples)
```

Sparkline characters (8 levels):
- `▁` = Lowest value
- `▂▃▄▅▆▇` = Intermediate values
- `█` = Highest value

### Statistics Row

Comprehensive metric summary:

```
Min: 9200.00 Avg: 9450.32 Max: 9500.00  P50: 9460.00  P95: 9490.00  P99: 9498.00
 ▲ Minimum    ▲ Mean     ▲ Maximum      ▲ Median      ▲ 95th %ile    ▲ 99th %ile
```

## Metrics Displayed

### Throughput

- **Unit**: Mbps (Megabits per second)
- **Source**: OMNI `-o THROUGHPUT` or interim results
- **Interpretation**: Higher is better
- **Typical Range**: 100-10000 Mbps (depending on network)

### Latency

- **Unit**: us (microseconds)
- **Source**: OMNI `-o MEAN_LATENCY` or RR tests
- **Interpretation**: Lower is better
- **Typical Range**: 10-1000 us (depending on network and distance)

### CPU Utilization

- **Unit**: % (percentage)
- **Source**: OMNI `-o LOCAL_CPU_UTIL,REMOTE_CPU_UTIL`
- **Components**:
  - CPU Local: CPU usage on client (this system)
  - CPU Remote: CPU usage on server
- **Typical Range**: 0-100%

## Integration Examples

### With netperf-multi

Monitor multi-instance test:

```bash
# Start multi-instance test with demo mode
./dev/tools/netperf-multi -n 4 -H server --demo-mode -- -d send -l 60 &

# Monitor in another terminal (future enhancement)
./dev/tools/netperf-monitor --follow /tmp/netperf-multi.log
```

### With netperf-profile

Monitor profile execution:

```bash
# Run profile and monitor first test
./dev/tools/netperf-monitor -H server -- \
    -d send -l 60 $(grep -A10 "test:" throughput.yaml | head -20)
```

### With netperf-orchestrate

Monitor orchestrated test (future):

```bash
# Orchestrate with monitoring
./dev/tools/netperf-orchestrate --hosts hosts.yaml --monitor -- -d send -l 60
```

## Terminal Compatibility

### Supported Terminals

- ✅ xterm, xterm-256color
- ✅ Linux console
- ✅ macOS Terminal.app
- ✅ iTerm2
- ✅ GNOME Terminal
- ✅ Konsole
- ✅ Windows Terminal
- ✅ tmux
- ✅ screen

### ANSI Color Support

The monitor uses ANSI escape codes for:
- Cursor positioning
- Screen clearing
- Color (91-97 bright colors)
- Text formatting (bold, dim)

If colors don't display correctly, check `$TERM`:

```bash
echo $TERM
# Should be: xterm-256color, screen-256color, etc.

# Fix if needed
export TERM=xterm-256color
```

## Troubleshooting

### No Interim Results Displayed

**Problem**: Monitor shows progress bar but no metrics update.

**Solution**: Ensure `--demo-mode` is passed to netperf:

```bash
# The monitor automatically adds --demo-mode
./dev/tools/netperf-monitor -H server -- -d send -l 60

# But if calling netperf directly, add it manually
netperf -H server --demo-mode -- -d send -l 60
```

### Display Flickers

**Problem**: Screen flickers or updates too quickly.

**Solution**: Increase refresh rate:

```bash
./dev/tools/netperf-monitor -H server --refresh 1.0 -- -d send -l 60
```

### Terminal Size Too Small

**Problem**: Display truncated or overlaps.

**Solution**: Resize terminal to at least 80x24:

```bash
# Check current size
stty size

# Resize terminal window or use larger terminal
```

### Colors Not Displaying

**Problem**: See escape codes like `^[[92m` instead of colors.

**Solution**: Verify ANSI support:

```bash
# Test ANSI colors
echo -e "\033[92mGreen\033[0m"

# Set proper TERM
export TERM=xterm-256color
```

### Test Completes Too Quickly

**Problem**: Monitor exits before you can see results.

**Solution**: Use longer test duration:

```bash
./dev/tools/netperf-monitor -H server -l 120 -- -d send
```

## Performance Impact

### CPU Overhead

- **Display Rendering**: < 1% CPU (terminal I/O)
- **Metric Parsing**: Negligible
- **Statistics**: < 0.1% CPU (simple math)

The monitor runs in a separate thread and does not affect netperf performance.

### Refresh Rate Recommendations

- **High-frequency trading**: 0.1s (10 Hz)
- **Normal monitoring**: 0.5s (2 Hz) - **Default**
- **Low-bandwidth terminals**: 1.0s (1 Hz)
- **Background monitoring**: 2.0s (0.5 Hz)

## Keyboard Controls (Future Enhancement)

Planned interactive controls:

- **Space**: Pause/resume display updates
- **Q**: Quit monitoring
- **R**: Reset statistics
- **+/-**: Adjust refresh rate
- **S**: Save snapshot
- **H**: Toggle help overlay

## Export Formats (Future Enhancement)

Planned export capabilities:

### Prometheus

Export metrics to Prometheus:

```bash
./dev/tools/netperf-monitor -H server --export-prometheus :9090 -- -d send -l 60
```

Metrics exposed:
```
netperf_throughput_mbps{host="server"} 9473.56
netperf_latency_us{host="server"} 125.43
netperf_cpu_local_pct{host="server"} 45.20
netperf_cpu_remote_pct{host="server"} 32.10
```

### StatsD

Send metrics to StatsD:

```bash
./dev/tools/netperf-monitor -H server --export-statsd localhost:8125 -- -d send -l 60
```

### InfluxDB Line Protocol

Stream to InfluxDB:

```bash
./dev/tools/netperf-monitor -H server --export-influx localhost:8086 -- -d send -l 60
```

## Best Practices

1. **Test Duration**: Use at least 30s for stable metrics (60s+ recommended)
2. **Refresh Rate**: Default 0.5s works for most cases
3. **Terminal Size**: Use at least 80x24 for proper display
4. **ANSI Support**: Ensure terminal supports ANSI escape codes
5. **Demo Mode**: Always use with netperf `--demo-mode` for interim results
6. **Background Jobs**: Don't run in background; use tmux/screen instead
7. **Monitoring Overhead**: Monitor adds < 1% overhead
8. **Long Tests**: For tests > 10 minutes, use higher refresh rate (1-2s)

## Comparison with Other Tools

### vs `watch netperf`

- ✅ Real-time metrics (not just final results)
- ✅ Progress tracking with ETA
- ✅ Statistical analysis (percentiles)
- ✅ Sparkline visualizations
- ✅ No flicker (smart terminal updates)

### vs Grafana

- ✅ No infrastructure required (just terminal)
- ✅ Works over SSH
- ✅ Instant startup
- ✗ Not persistent (no historical data)
- ✗ Single test focus (no long-term trends)

### vs `netperf --demo-mode`

- ✅ Visual progress bar
- ✅ Live statistics (min/max/avg/percentiles)
- ✅ Sparkline graphs
- ✅ Better formatting
- ✅ ETA calculation

## Examples

### Quick Throughput Check

```bash
./dev/tools/netperf-monitor -H 192.168.1.10 -l 30 -- -d send
```

### Latency Monitoring

```bash
./dev/tools/netperf-monitor -H 192.168.1.10 -l 60 -- -d rr
```

### High-Resolution Monitoring

```bash
./dev/tools/netperf-monitor -H server --refresh 0.1 -l 120 -- -d send
```

### UDP Throughput

```bash
./dev/tools/netperf-monitor -H server -l 60 -- -d send -T udp
```

### Remote Server

```bash
./dev/tools/netperf-monitor -H remote.example.com -l 60 -- -d send
```

## See Also

- [OMNI_REFERENCE.md](OMNI_REFERENCE.md) - OMNI test framework guide
- [phase-3-plan.md](../plans/phase-3-plan.md) - Phase 3 implementation plan
- netperf-multi(1) - Multi-instance test runner
- netperf-profile(1) - Profile-based test execution
- netperf-orchestrate(1) - Remote test orchestration
