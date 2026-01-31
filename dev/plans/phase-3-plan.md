# Phase 3: Advanced Features - Implementation Plan

**Branch**: `dev/phase-3-advanced-features`  
**Status**: In Progress  
**Start Date**: January 31, 2026  
**Estimated Duration**: 20 days

## Overview

Phase 3 adds advanced capabilities for production deployments, including multi-instance testing, enhanced statistics, performance profiles, remote orchestration, real-time monitoring, and advanced templating.

## Prerequisites

- Phase 1: Modernized Defaults ✅
- Phase 2: Output Format Enhancement ✅
- Python 3.6+ available
- SSH access for remote orchestration
- Terminal with Unicode support (for monitoring UI)
- Understanding of OMNI test options (see `dev/docs/OMNI_REFERENCE.md`)

## Tasks

### Task 3.1: Multi-Instance Test Runner ⏳

**Priority**: High  
**Estimated Time**: 3 days  
**Dependencies**: Phase 2 aggregation tool

**Objectives**:

- Create `netperf-multi` tool for parallel test execution
- Support N simultaneous netperf instances
- Automatic result collection and aggregation
- CPU/memory affinity control
- Coordinated start/stop across instances

**Deliverables**:

- `dev/tools/netperf-multi` (Python script)
- Parallel execution engine
- Resource management (CPU pinning, memory limits)
- Automatic result aggregation
- Documentation in `MULTI_INSTANCE.md`

**Implementation Details**:

```python
# Usage examples
netperf-multi -H server1 -n 4                  # 4 parallel OMNI tests (default)
netperf-multi -H server1 -n 8 --affinity       # With CPU pinning
netperf-multi -H server1 -n 16 --aggregate     # Auto-aggregate results
```

**Key Features**:

- Process spawning with `subprocess`
- CPU affinity with `psutil` (optional)
- Barrier synchronization for coordinated start
- Result collection from all instances
- Aggregated statistics (sum throughput, avg latency)

---

### Task 3.2: Enhanced Statistics Engine ⏳

**Priority**: High  
**Estimated Time**: 4 days  
**Dependencies**: Phase 2 aggregation tool

**Objectives**:

- Add confidence intervals (95%, 99%)
- Variance and coefficient of variation
- Outlier detection (IQR, Z-score methods)
- Statistical significance testing (t-test, Mann-Whitney)
- Distribution analysis (normality tests)

**Deliverables**:

- Enhanced `netperf-aggregate` statistics module
- Confidence interval calculation
- Outlier detection and filtering
- Hypothesis testing for comparisons
- Distribution visualization (ASCII histograms)
- Documentation in `STATISTICS.md`

**Implementation Details**:

```python
# New statistics
- Mean with 95% CI: 9500.2 ± 124.5 Mbps
- Coefficient of variation: 2.3%
- Outliers detected: 2/100 (removed)
- Normal distribution: Yes (Shapiro-Wilk p=0.42)
- Significance vs baseline: p < 0.001 (highly significant)
```

**Key Features**:

- Use `statistics` and `math` modules (stdlib only)
- Bootstrap method for CI when appropriate
- Multiple outlier detection methods
- Regression detection with confidence levels
- ASCII box plots and histograms

---

### Task 3.3: Performance Profiles System ⏳

**Priority**: Medium  
**Estimated Time**: 3 days  
**Dependencies**: Task 3.1

**Objectives**:

- Pre-configured test suites for common scenarios
- Profile templates (throughput, latency, stress, cloud)
- Profile manager for custom profiles
- YAML-based profile definitions
- Quick benchmark mode

**Deliverables**:

- `dev/profiles/` directory with 10+ profiles
- Profile definitions:
  - `throughput.yaml` - Maximum bandwidth testing
  - `latency.yaml` - Low-latency optimization
  - `stress.yaml` - Maximum load testing
  - `cloud.yaml` - Cloud networking patterns
  - `datacenter.yaml` - Datacenter optimization
  - `wireless.yaml` - Wireless network testing
  - `lossy.yaml` - Lossy network conditions
  - `jitter.yaml` - Jitter and consistency testing
- `netperf-profile` runner tool
- Profile validator
- Documentation in `PROFILES.md`

**Implementation Details**:

```yaml
# Example: throughput.yaml
name: Maximum Throughput
description: Optimized for maximum bandwidth measurement
tests:
  - pattern: stream        # OMNI stream pattern
    protocol: tcp
    duration: 30
    instances: 4
    socket_size: 262144
    direction: send
  - pattern: stream        # OMNI UDP stream
    protocol: udp
    duration: 30
    instances: 2
    message_size: 1472
output:
  format: json
  preset: monitoring
```

**Key Features**:

- YAML profile parsing (PyYAML or stdlib)
- Profile inheritance
- Variable substitution (${HOST}, ${DURATION})
- Profile validation before execution
- Custom profile creation wizard

---

### Task 3.4: Remote Test Orchestration ⏳

**Priority**: High  
**Estimated Time**: 4 days  
**Dependencies**: Task 3.1, Task 3.3

**Objectives**:

- Coordinate tests across multiple hosts
- SSH-based remote execution
- Automatic netserver deployment
- Result collection from remote hosts
- Multi-host test scenarios (client-server matrix)

**Deliverables**:

- `dev/tools/netperf-orchestrate` (Python script)
- SSH connection manager
- Remote netserver deployment
- Host inventory management
- Multi-host test coordination
- Result aggregation across hosts
- Documentation in `ORCHESTRATION.md`

**Implementation Details**:

```bash
# Usage examples
netperf-orchestrate --hosts hosts.yaml --profile throughput
netperf-orchestrate --matrix clients.txt servers.txt
netperf-orchestrate --deploy  # Auto-deploy netserver to hosts
```

**Host Inventory (YAML)**:

```yaml
hosts:
  - name: server1
    address: 10.0.1.10
    role: server
    ssh_user: root
    ssh_key: ~/.ssh/id_rsa
  - name: client1
    address: 10.0.1.20
    role: client
    ssh_user: root
```

**Key Features**:

- Paramiko for SSH (optional, fallback to subprocess ssh)
- SCP for file transfer
- Remote netserver management (start/stop/status)
- Parallel execution across hosts
- Error handling and retry logic
- Result collection and centralized aggregation

---

### Task 3.5: Real-time Monitoring Dashboard ⏳

**Priority**: Medium  
**Estimated Time**: 3 days  
**Dependencies**: Task 3.1

**Objectives**:

- Live test monitoring with terminal UI
- Real-time metrics streaming
- Progress bars and live graphs
- Multi-test dashboard view
- Export live data to monitoring systems

**Deliverables**:

- `dev/tools/netperf-monitor` (Python script)
- Terminal UI with curses or rich library
- Live metrics display (throughput, latency, CPU)
- ASCII charts and graphs
- Multi-pane dashboard for parallel tests
- Prometheus/StatsD export during execution
- Documentation in `MONITORING.md`

**Implementation Details**:

```
┌─────────────────────────────────────────────────────────────┐
│ Netperf Live Monitor - 4 Active Tests                      │
├─────────────────────────────────────────────────────────────┤
│ Test 1: TCP_STREAM to 10.0.1.10                            │
│ Throughput: 9,432.1 Mbps  [████████████████░░] 88%        │
│ CPU Usage:  45.2%                                           │
│ Elapsed:    25.3s / 30s                                     │
├─────────────────────────────────────────────────────────────┤
│ Test 2: TCP_RR to 10.0.1.10                                │
│ Trans/sec:  12,345.6  [██████████████████░] 92%            │
│ Latency:    81.0 μs (avg)                                   │
│ Elapsed:    27.7s / 30s                                     │
├─────────────────────────────────────────────────────────────┤
│ Graph: Throughput (last 30s)                               │
│  10Gb ┤     ╭──╮                                            │
│   8Gb ┤   ╭─╯  ╰─╮                                          │
│   6Gb ┤  ╭╯      ╰╮                                         │
│   4Gb ┤╭─╯        ╰─╮                                       │
│       └─────────────────────────────────────                │
│        0s    10s    20s    30s                              │
└─────────────────────────────────────────────────────────────┘
```

**Key Features**:

- Rich library for modern terminal UI (optional)
- Fallback to basic curses UI
- Parse netperf interval output (`-P` flag)
- Live graph updates
- Multi-test monitoring
- Keyboard controls (pause, abort, zoom)

---

### Task 3.6: Advanced Template Engine ⏳

**Priority**: Low  
**Estimated Time**: 3 days  
**Dependencies**: Phase 2 templates

**Objectives**:

- Full-featured template engine (Jinja2-style)
- Conditional logic and loops
- Filters and functions
- Custom output format creation
- Template inheritance

**Deliverables**:

- Enhanced template system in `netperf-aggregate`
- Template syntax documentation
- 10+ advanced template examples
- Template library system
- Template validator
- Documentation in `TEMPLATES.md`

**Implementation Details**:

```jinja2
{# Advanced template example #}
{% if test_type == "TCP_STREAM" %}
## Throughput Test Results
**Bandwidth**: {{ throughput | format_bps }}
{% elif test_type == "TCP_RR" %}
## Latency Test Results
**Transaction Rate**: {{ trans_rate | format_num }} trans/sec
**Latency**: {{ latency_us | format_latency }}
{% endif %}

{% if statistics.outliers > 0 %}
⚠️  **Warning**: {{ statistics.outliers }} outliers detected
{% endif %}

### Historical Comparison
{% for baseline in baselines %}
- {{ baseline.name }}: {{ compare_percent(current, baseline) }}
{% endfor %}
```

**Key Features**:

- Jinja2-compatible syntax (use Jinja2 if available, or minimal implementation)
- Conditionals: `{% if %}`, `{% elif %}`, `{% else %}`
- Loops: `{% for item in list %}`
- Filters: `{{ value | filter_name }}`
- Built-in filters: format_bps, format_latency, format_num, format_percent
- Custom filter registration
- Template inheritance: `{% extends "base.tmpl" %}`
- Include directive: `{% include "header.tmpl" %}`

---

## Testing Strategy

### Unit Tests

- Each tool should have comprehensive tests
- Use Python `unittest` framework
- Mock external dependencies (SSH, processes)
- Test edge cases and error handling

### Integration Tests

- End-to-end test scenarios
- Real netperf execution tests
- Multi-host test validation
- Performance regression tests

### Documentation Tests

- All examples must be executable
- Automated documentation validation
- Link checking
- Code sample validation

---

## Documentation Requirements

Each task must include:

1. **User Guide**: How to use the feature
2. **API Reference**: Detailed function/option documentation
3. **Examples**: At least 5 working examples
4. **Integration Guide**: How to integrate with existing tools
5. **Troubleshooting**: Common issues and solutions

---

## Performance Targets

- Multi-instance overhead: < 5% per instance
- Statistics calculation: < 1s for 10,000 samples
- Profile loading: < 100ms
- Remote orchestration latency: < 500ms setup overhead
- Live monitoring refresh: 10 Hz minimum
- Template rendering: < 50ms for complex templates

---

## Backward Compatibility

All Phase 3 features are additive:

- No changes to core netperf/netserver binaries
- No breaking changes to Phase 1/2 tools
- All Phase 3 tools are optional
- Graceful degradation when dependencies missing

---

## Dependencies

### Required (stdlib only for core features)

- Python 3.6+
- Standard library modules: subprocess, threading, statistics, json, csv

### Optional (enhanced features)

- `psutil` - CPU affinity and system monitoring
- `paramiko` - SSH without external ssh binary
- `rich` - Modern terminal UI
- `pyyaml` - YAML profile parsing
- `jinja2` - Advanced template engine

### Fallback Strategy

If optional dependencies unavailable:

- CPU affinity: Skip pinning, log warning
- Paramiko: Use subprocess ssh/scp
- Rich: Use basic curses or plain text
- PyYAML: Use JSON profiles instead
- Jinja2: Use basic template engine

---

## Success Criteria

Phase 3 complete when:

- [ ] All 6 tasks implemented and tested
- [ ] 2,500+ lines of documentation written
- [ ] All tools work without optional dependencies
- [ ] Zero regressions from Phase 1/2
- [ ] Performance targets met
- [ ] Examples validated on 3+ platforms
- [ ] Code committed and pushed to GitHub

---

## Risk Assessment

### High Risk

- Remote orchestration security (SSH key management)
- Real-time monitoring performance impact
- Template engine complexity

### Mitigation

- Secure SSH key handling with user warnings
- Monitoring as separate process (no impact on tests)
- Simple template engine first, Jinja2 optional enhancement

---

## Timeline

| Week | Tasks | Deliverables |
|------|-------|-------------|
| 1 | 3.1, 3.2 | Multi-instance runner, Statistics engine |
| 2 | 3.3, 3.4 | Profiles system, Remote orchestration |
| 3 | 3.5, 3.6 | Live monitoring, Template engine |
| 4 | Testing, Docs | Final validation, Documentation completion |

---

## Next Phase Preview

**Phase 4: Cloud & Container Integration** (Future)

- Kubernetes operator for netperf
- Docker containers with automation
- Cloud provider integrations (AWS, GCP, Azure)
- Terraform modules
- CI/CD pipeline templates
