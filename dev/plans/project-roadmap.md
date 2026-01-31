# Netperf Enhancement Project Roadmap

## Project Vision

Modernize netperf with enhanced automation, multi-instance testing, comprehensive output formats, and intelligent configuration management while maintaining backward compatibility.

## Core Objectives

### Primary Goal

- Change default test from TCP_STREAM to OMNI with sensible default output selectors
- Enable interval reporting (--enable-demo) by default
- Optimize default build configuration

### Enhancement Goals

1. Multi-format output (human-readable, CSV, JSON)
2. Multi-instance parallel testing with aggregate reporting
3. Directional testing (Tx/Rx/Bx) with independent metrics
4. Automated configuration testing and tuning agent
5. Advanced netserver deployment and binding management
6. Pre-defined test catalog for CPU/NUMA/PCIe optimization

---

## Phase 0: Analysis & Preparation (Week 1-2)

### 0.1 Current State Analysis

**Deliverables:**

- [ ] Document current default build configuration
- [ ] Analyze all configure options and their impact
- [ ] Review existing OMNI output selectors
- [ ] Document current test invocation patterns
- [ ] Create baseline performance measurements

**Location:** `dev/docs/analysis/`

**Tasks:**

```bash
# Document current configure defaults
./configure --help > dev/docs/analysis/configure-options.txt

# Test current OMNI capabilities
./src/netperf -H localhost -t OMNI -- -k all > dev/docs/analysis/omni-all-outputs.txt

# Baseline performance tests
./dev/scripts/test-basic.sh > dev/reports/baseline-performance.txt
```

### 0.2 Requirements Documentation

**Deliverables:**

- [ ] Technical requirements for each enhancement
- [ ] Backward compatibility requirements
- [ ] Performance impact assessment criteria
- [ ] User acceptance criteria

**Location:** `dev/docs/requirements/`

---

## Phase 1: Core Defaults & Build Optimization (Week 3-4)

### 1.1 Change Default Test to OMNI

**Impact:** Low risk, high value
**Files to modify:**

- `src/netsh.c` - Change test_name default from "TCP_STREAM" to "OMNI"
- `src/netsh.h` - Update default constant

**Implementation:**

```c
// src/netsh.c line ~129
test_name[BUFSIZ] = "OMNI",   // Changed from TCP_STREAM
```

**Testing:**

- Verify `./netperf -H localhost` runs OMNI by default
- Verify `-t TCP_STREAM` still works (backward compat)
- Update documentation

### 1.2 Define Default OMNI Output Selectors

**Research:** Review `doc/omni_output_list.txt` for optimal defaults

**Recommended defaults:**

```bash
-k THROUGHPUT,THROUGHPUT_UNITS,MEAN_LATENCY,P50_LATENCY,P90_LATENCY,P99_LATENCY,\
LOCAL_CPU_UTIL,REMOTE_CPU_UTIL,LOCAL_SEND_CALLS,LOCAL_RECV_CALLS,\
ELAPSED_TIME,PROTOCOL,DIRECTION,SOCKET_TYPE
```

**Files to modify:**

- `src/nettest_omni.c` - Add default output selector initialization
- Create new test-specific option for "default" vs "verbose" vs "minimal"

**Implementation approach:**

- Add global variable for default output format
- When `-k` not specified, use sensible defaults
- Add `-k default`, `-k verbose`, `-k minimal` presets

### 1.3 Enable Interval Reporting by Default

**Files to modify:**

- `configure.ac` - Change --enable-demo to default yes
- Test performance impact
- Document how to disable if needed

**Implementation:**

```bash
# In configure.ac, around line 200
case "$enable_demo" in
     yes)
  use_demo=true
  ;;
     no)
  use_demo=false
  ;;
     '')
  use_demo=true    # Changed from false
  ;;
```

### 1.4 Review & Optimize Build Configuration

**Analysis needed:**

- `--enable-histogram` - Per-op timing, may affect performance
- `--enable-dirty` - Write to buffers each time
- `--enable-intervals` - Paced operation support
- `--enable-burst` - Initial RR burst support
- `--enable-omni` - Should be default yes (already is)
- `--enable-unixdomain` - Unix socket tests
- `--enable-sctp` - SCTP protocol support

**Recommendations:**

```bash
# Optimal default configure
./configure \
  --enable-demo \           # Interval reporting: YES (Phase 1.3)
  --enable-omni \           # OMNI tests: YES (already default)
  --enable-intervals \      # Paced operations: YES (useful for modern testing)
  --disable-histogram \     # Per-op timing: NO (performance impact)
  --enable-sctp \           # SCTP: YES (if available)
  --enable-unixdomain       # Unix sockets: YES (common use case)
```

**Deliverables:**

- [ ] Updated configure.ac with new defaults
- [ ] Documentation: `dev/docs/build-configuration.md`
- [ ] Script: `dev/scripts/configure-optimized.sh`
- [ ] Performance comparison report

---

## Phase 2: Output Format Enhancement (Week 5-7)

### 2.1 JSON Output Support

**Priority:** High - Industry standard format
**Files to create:**

- `src/netlib_json.c` - JSON formatting functions
- `src/netlib_json.h` - JSON output interface

**Implementation approach:**

1. Add `-f json` or `-o json` global option
2. Create JSON structure for test results
3. Support nested objects for multi-iteration results
4. Include metadata (timestamp, hostname, version)

**JSON Schema:**

```json
{
  "netperf_version": "2.7.1",
  "timestamp": "2026-01-30T10:00:00Z",
  "test_type": "OMNI",
  "protocol": "TCP",
  "direction": "SEND",
  "configuration": {
    "local_host": "client.example.com",
    "remote_host": "server.example.com",
    "test_duration": 10,
    "socket_size": 87380
  },
  "results": {
    "throughput": 9420.15,
    "throughput_units": "Mbps",
    "latency_mean": 106.2,
    "latency_p50": 98.5,
    "latency_p99": 245.7,
    "local_cpu_util": 12.4,
    "remote_cpu_util": 15.8
  },
  "iterations": [...]
}
```

### 2.2 CSV Output Enhancement

**Priority:** High - Common for spreadsheet analysis
**Current state:** OMNI already supports CSV-like output with `-P`

**Enhancement:**

1. Add proper CSV headers option
2. Ensure proper escaping of fields
3. Add `-o csv-header` option
4. Support output to file directly: `-O results.csv`

### 2.3 Output to File

**Global options to add:**

- `-O <filename>` - Output results to file
- `-F <format>` - Format: human|csv|json (default: human)
- Combine: `netperf -H host -O results.json -F json`

**Files to modify:**

- `src/netsh.c` - Add command-line parsing
- `src/netlib.c` - Add file output functions
- All test files - Support output redirection

**Implementation:**

```c
// Add global variables
char output_file[PATH_MAX] = "";
char output_format[32] = "human";

// Add to command-line processing
case 'O':
  strncpy(output_file, optarg, sizeof(output_file)-1);
  break;
case 'F':
  strncpy(output_format, optarg, sizeof(output_format)-1);
  break;
```

**Deliverables:**

- [ ] JSON output implementation
- [ ] CSV with headers
- [ ] File output support
- [ ] Unit tests for each format
- [ ] Documentation: `dev/docs/output-formats.md`
- [ ] Example outputs: `dev/docs/examples/`

---

## Phase 3: Multi-Instance Testing (Week 8-11)

### 3.1 Multi-Instance Test Controller

**Priority:** High - Core new feature
**New component:** `netperf-multi`

**Architecture:**

```
netperf-multi (orchestrator)
├── Spawns multiple netperf instances
├── Each targets different adapter/port
├── Collects results from all instances
├── Generates aggregate report
└── Outputs: individual + combined results
```

**Implementation approach:**

1. Create new binary: `src/netperf-multi.c`
2. Configuration file format (JSON or YAML)
3. Fork/exec management for parallel tests
4. IPC for result collection
5. Aggregate statistics calculation

**Configuration file example:**

```json
{
  "test_name": "multi_adapter_throughput",
  "duration": 10,
  "instances": [
    {
      "adapter": "eth0",
      "local_ip": "192.168.1.10",
      "remote_host": "192.168.1.20",
      "remote_port": 12865,
      "test_type": "OMNI",
      "direction": "send"
    },
    {
      "adapter": "eth1",
      "local_ip": "192.168.2.10",
      "remote_host": "192.168.2.20",
      "remote_port": 12866,
      "test_type": "OMNI",
      "direction": "send"
    }
  ]
}
```

**Features:**

- Synchronized start across all instances
- Real-time progress monitoring
- Individual and aggregate throughput
- Per-adapter CPU utilization
- Failed instance handling and retry

### 3.2 Aggregate Reporting

**Statistics to aggregate:**

- Total throughput (sum)
- Average latency (weighted by transaction count)
- Max/min per-instance throughput
- Total CPU utilization across all CPUs
- Per-adapter efficiency metrics

**Output formats:**

- Summary table (human-readable)
- JSON aggregate results
- CSV for time-series analysis
- Visualization data (for future graphing)

**Deliverables:**

- [ ] netperf-multi implementation
- [ ] Configuration schema and parser
- [ ] Aggregate statistics module
- [ ] Documentation: `dev/docs/multi-instance-testing.md`
- [ ] Example configs: `dev/docs/examples/multi-*.json`
- [ ] Test script: `dev/scripts/test-multi-instance.sh`

---

## Phase 4: Directional Testing (Week 12-13)

### 4.1 Tx/Rx/Bx Test Modes

**Current state:** OMNI supports `-d send` and `-d recv`
**Enhancement:** Add intelligent test mode with separate reporting

**Implementation:**

```bash
# New test option: -T <mode>
netperf -H host -T tx    # Send only (client -> server)
netperf -H host -T rx    # Recv only (server -> client)
netperf -H host -T bx    # Bidirectional (both directions sequentially)
netperf -H host -T simul # Simultaneous bidirectional
```

**Files to modify:**

- `src/netsh.c` - Add -T option parsing
- `src/nettest_omni.c` - Implement test modes
- Add separate results structure for each direction

### 4.2 Independent Direction Reporting

**For Bx mode, report:**

```
Direction: Send (Tx)
  Throughput: 9420 Mbps
  CPU: 12.4%
  Latency: N/A

Direction: Recv (Rx)
  Throughput: 9380 Mbps
  CPU: 15.1%
  Latency: N/A

Direction: Bidirectional (Simul)
  Throughput TX: 4710 Mbps
  Throughput RX: 4690 Mbps
  Total: 9400 Mbps
  CPU: 24.8%
```

**JSON output structure:**

```json
{
  "test_mode": "bidirectional",
  "results": {
    "tx": { "throughput": 9420, "cpu": 12.4 },
    "rx": { "throughput": 9380, "cpu": 15.1 },
    "simultaneous": {
      "tx": { "throughput": 4710 },
      "rx": { "throughput": 4690 },
      "total": 9400,
      "cpu": 24.8
    }
  }
}
```

**Deliverables:**

- [ ] Directional test modes implementation
- [ ] Independent reporting for each direction
- [ ] Documentation: `dev/docs/directional-testing.md`
- [ ] Test scripts for all modes

---

## Phase 5: Automated Configuration Testing Agent (Week 14-17)

### 5.1 Test Scenario Definition Language

**Create DSL for test scenarios:**

**Example scenario file:** `dev/docs/examples/scenario-mtu-tuning.yaml`

```yaml
name: "MTU Optimization Test"
description: "Test different MTU sizes to find optimal value"
target_host: "192.168.1.20"

variables:
  mtu_values: [1500, 4000, 9000]
  
pre_test_setup:
  - command: "sudo ip link set dev eth0 mtu ${mtu_value}"
    applies_to: ["local", "remote"]
  - command: "sleep 2"  # Allow link to stabilize

test:
  type: "OMNI"
  duration: 30
  direction: "bidirectional"
  output_format: "json"
  output_file: "results/mtu-${mtu_value}.json"

post_test_cleanup:
  - command: "sudo ip link set dev eth0 mtu 1500"
    applies_to: ["local", "remote"]

iterations:
  loop_over: mtu_values
  repeat_count: 3
  
analysis:
  compare_metric: "throughput"
  goal: "maximize"
  generate_report: "results/mtu-optimization-report.html"
```

### 5.2 Configuration Testing Engine

**New component:** `netperf-tuner`

**Features:**

- Parse scenario files
- Execute pre-test configuration
- Run netperf tests
- Collect and store results
- Execute cleanup
- Iterate through all configurations
- Generate comparative analysis

**Architecture:**

```
netperf-tuner
├── Scenario Parser (YAML/JSON)
├── Configuration Manager
│   ├── Local config executor
│   └── Remote config executor (SSH)
├── Test Executor (netperf wrapper)
├── Results Collector
├── Analysis Engine
│   ├── Statistical comparison
│   ├── Trend analysis
│   └── Recommendation generator
└── Report Generator (HTML/PDF)
```

### 5.3 Remote Configuration Support

**Requirements:**

- SSH key-based authentication
- Sudo capabilities on remote host
- Safety checks before executing commands
- Rollback capability on failure

**Implementation:**

```python
# Use Python for scripting flexibility
class RemoteConfigManager:
    def __init__(self, host, user, key_file):
        self.ssh_client = paramiko.SSHClient()
        
    def apply_config(self, commands):
        # Execute with safety checks
        # Store previous state for rollback
        
    def rollback(self):
        # Restore previous configuration
```

### 5.4 Analysis and Recommendations

**Analysis capabilities:**

- Statistical significance testing (t-test, ANOVA)
- Trend detection (linear, polynomial fitting)
- Outlier detection
- Performance regression detection
- Cost-benefit analysis (performance vs. resource usage)

**Recommendation engine:**

```
Analysis Results:
✓ MTU 9000 provides 15% better throughput vs baseline
✓ Statistically significant (p < 0.01, n=3)
⚠ CPU utilization increased by 3%
✓ Latency decreased by 8%

Recommendation:
→ Use MTU 9000 for maximum throughput
→ Performance gain: +15% throughput, -8% latency
→ Trade-off: +3% CPU usage (acceptable)
→ Confidence: High (consistent across all iterations)
```

**Deliverables:**

- [ ] Scenario definition format and parser
- [ ] netperf-tuner implementation (Python)
- [ ] Remote configuration manager
- [ ] Analysis engine with statistics
- [ ] Recommendation generator
- [ ] HTML/PDF report templates
- [ ] Example scenarios: MTU, ring buffer, interrupt coalescing, etc.
- [ ] Documentation: `dev/docs/automated-tuning.md`

---

## Phase 6: Advanced Netserver Management (Week 18-20)

### 6.1 Netserver Configuration Tool

**New component:** `netserver-manager`

**Features:**

- Start multiple netserver instances
- CPU affinity binding
- Memory binding (NUMA)
- Unique port assignment
- Instance naming for result tracking
- Systemd service file generation

**Usage:**

```bash
# Single instance with CPU binding
netserver-manager start --cpu 0 --port 12865 --name "netserver-cpu0"

# Multiple instances across NUMA nodes
netserver-manager start-multi \
  --config multi-netserver.json

# Configuration file
{
  "instances": [
    {
      "name": "netserver-numa0-core0",
      "port": 12865,
      "cpu_affinity": [0],
      "numa_node": 0,
      "memory_binding": "strict"
    },
    {
      "name": "netserver-numa1-core8",
      "port": 12866,
      "cpu_affinity": [8],
      "numa_node": 1,
      "memory_binding": "strict"
    }
  ]
}
```

### 6.2 CPU and NUMA Binding

**Platform support:**

- Linux: `sched_setaffinity()`, `numactl`, `taskset`
- Detect NUMA topology automatically
- Validate CPU/NUMA availability before binding

**Implementation:**

```c
// In netserver.c
#ifdef HAVE_SCHED_SETAFFINITY
void bind_to_cpu(int cpu_id) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(cpu_id, &cpuset);
    sched_setaffinity(0, sizeof(cpuset), &cpuset);
}
#endif

#ifdef HAVE_NUMA
void bind_to_numa_node(int node) {
    struct bitmask *nodemask = numa_allocate_nodemask();
    numa_bitmask_setbit(nodemask, node);
    numa_bind(nodemask);
    numa_free_nodemask(nodemask);
}
#endif
```

**Command-line options for netserver:**

```bash
netserver \
  -p 12865 \              # Port
  -C 0,1,2,3 \           # CPU affinity list
  -N 0 \                 # NUMA node
  -n "netserver-numa0" \ # Instance name (for logging)
  -D                      # Foreground mode
```

### 6.3 Service Management

**Generate systemd service files:**

```bash
netserver-manager generate-systemd \
  --config multi-netserver.json \
  --output /etc/systemd/system/

# Creates:
# - netserver-numa0-core0.service
# - netserver-numa1-core8.service
# - netserver-multi.target (to manage all)
```

**Service file template:**

```ini
[Unit]
Description=Netserver Instance numa0-core0
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/netserver -p 12865 -C 0 -N 0 -D
Restart=always
CPUAffinity=0
NUMAPolicy=bind
NUMAMask=0

[Install]
WantedBy=multi-user.target
```

**Deliverables:**

- [ ] netserver CPU/NUMA binding implementation
- [ ] netserver-manager tool
- [ ] Systemd service generation
- [ ] NUMA topology detection
- [ ] Documentation: `dev/docs/netserver-management.md`
- [ ] Example configs: `dev/docs/examples/netserver-*.json`

---

## Phase 7: Predefined Test Catalog (Week 21-23)

### 7.1 Test Catalog Structure

**Location:** `dev/catalog/`

**Categories:**

1. **CPU Localization Tests** - Same CPU, cross-CPU, cross-package
2. **NUMA Tests** - Local node, remote node, cross-node
3. **PCIe Tests** - Same PCIe root, different root, NIC alignment
4. **Queue Tests** - Single queue, multi-queue, RSS/RFS validation
5. **Tuning Validation** - Interrupt coalescing, ring buffers, offloads

### 7.2 CPU Localization Tests

**Test suite:** `dev/catalog/cpu-localization/`

**Tests:**

```yaml
# test-1-same-core.yaml
name: "Same CPU Core Test"
description: "Netperf and netserver on same physical core"
setup:
  netserver:
    cpu_affinity: [0]
    port: 12865
  netperf:
    cpu_affinity: [0]
    target: "localhost:12865"
expected_result: "Highest throughput, lowest latency"

# test-2-sibling-cores.yaml
name: "Sibling Cores Test (SMT/HT)"
description: "Netperf and netserver on sibling hyperthreads"
setup:
  netserver:
    cpu_affinity: [0]    # Core 0, Thread 0
  netperf:
    cpu_affinity: [1]    # Core 0, Thread 1 (sibling)
expected_result: "Slightly lower than same core due to shared L1/L2"

# test-3-same-package.yaml
name: "Same Package, Different Core"
setup:
  netserver:
    cpu_affinity: [0]
  netperf:
    cpu_affinity: [2]    # Same package, different core
expected_result: "Shared L3 cache, moderate latency"

# test-4-different-package.yaml
name: "Different CPU Package"
setup:
  netserver:
    cpu_affinity: [0]    # Package 0
  netperf:
    cpu_affinity: [8]    # Package 1
expected_result: "Higher latency due to inter-package communication"
```

### 7.3 NUMA Tests

**Test suite:** `dev/catalog/numa-alignment/`

**Tests:**

```yaml
# numa-local.yaml
name: "NUMA Local Access"
description: "NIC and netperf on same NUMA node"
topology_required:
  numa_nodes: 2
  nics_per_node: 1
setup:
  netserver:
    numa_node: 0
    nic: "eth0"  # Must be on NUMA node 0
  netperf:
    numa_node: 0
    bind_memory: strict
expected_result: "Optimal memory bandwidth, lowest latency"

# numa-remote.yaml
name: "NUMA Remote Access"
description: "NIC on node 0, netperf on node 1"
setup:
  netserver:
    numa_node: 0
    nic: "eth0"  # NUMA node 0
  netperf:
    numa_node: 1  # Different node
    bind_memory: strict
expected_result: "QPI/UPI overhead, 20-40% performance degradation"
```

### 7.4 PCIe Tests

**Test suite:** `dev/catalog/pcie-alignment/`

**Tests:**

```yaml
# pcie-optimal.yaml
name: "Optimal PCIe Configuration"
description: "CPU, memory, and NIC on same PCIe root complex"
topology_detection:
  run: "lspci -tv"
  parse: "Find NIC PCIe root complex"
setup:
  netserver:
    cpu_affinity: "same_pcie_root_as_nic"
    numa_node: "same_as_nic"
  netperf:
    cpu_affinity: "same_pcie_root_as_nic"
expected_result: "Maximum PCIe bandwidth utilization"

# pcie-cross-root.yaml
name: "Cross PCIe Root Complex"
description: "NIC and CPU on different PCIe roots"
setup:
  netserver:
    cpu_affinity: "different_pcie_root_from_nic"
expected_result: "Additional PCIe hop, measurable latency increase"
```

### 7.5 Test Runner and Analyzer

**New tool:** `netperf-catalog`

**Usage:**

```bash
# Run entire category
netperf-catalog run cpu-localization --output results/

# Run specific test
netperf-catalog run cpu-localization/test-1-same-core.yaml

# Run all tests and generate comparison report
netperf-catalog run-all --analyze --report results/report.html

# Detect optimal configuration
netperf-catalog detect-optimal --category numa-alignment
```

**Output:**

```
Test Results Summary:
========================================
Category: CPU Localization

✓ Same Core:            9850 Mbps (100% baseline)
✓ Sibling Cores:        9620 Mbps (98% baseline)
✓ Same Package:         9200 Mbps (93% baseline)
⚠ Different Package:    7800 Mbps (79% baseline)

Analysis:
- Cross-package communication adds ~20% overhead
- SMT/HT siblings perform within 2% of same core
- Recommendation: Bind netperf to same package as NIC

Next Steps:
→ Run NUMA alignment tests
→ Verify NIC is on optimal PCIe root
```

**Deliverables:**

- [ ] Test catalog structure and format
- [ ] 20+ predefined tests across all categories
- [ ] netperf-catalog runner tool
- [ ] Topology detection scripts
- [ ] Analysis and comparison engine
- [ ] HTML report generator with visualizations
- [ ] Documentation: `dev/docs/test-catalog.md`
- [ ] Quick start: `dev/docs/catalog-quickstart.md`

---

## Phase 8: Documentation and Polish (Week 24-25)

### 8.1 Comprehensive Documentation

**Create/update:**

- [ ] User guide with all new features
- [ ] API documentation for new tools
- [ ] Migration guide from old netperf
- [ ] Best practices guide
- [ ] Troubleshooting guide
- [ ] Performance tuning cookbook

### 8.2 Example Repository

**Location:** `dev/docs/examples/`

- Complete working examples for every feature
- Sample output files
- Configuration templates
- Shell scripts for common scenarios

### 8.3 Testing and Validation

- [ ] Unit tests for all new code
- [ ] Integration tests for multi-component features
- [ ] Performance regression tests
- [ ] Platform compatibility matrix
- [ ] CI/CD pipeline setup

### 8.4 Release Preparation

- [ ] Version bump to 3.0.0
- [ ] Release notes
- [ ] Migration guide
- [ ] Package for common distributions
- [ ] Docker container images

---

## Implementation Priority Matrix

| Phase | Feature | Impact | Complexity | Priority |
|-------|---------|--------|------------|----------|
| 1 | OMNI default + intervals | High | Low | P0 |
| 2 | JSON/CSV output | High | Medium | P0 |
| 3 | Multi-instance testing | High | High | P1 |
| 4 | Directional testing | Medium | Low | P1 |
| 5 | Config testing agent | High | High | P1 |
| 6 | Netserver management | Medium | Medium | P2 |
| 7 | Test catalog | Medium | Medium | P2 |

---

## Resource Requirements

### Development Team

- **Phase 1-2:** 1 C developer (core netperf changes)
- **Phase 3-5:** 1 C developer + 1 Python developer
- **Phase 6-7:** 1 C developer + 1 Python/DevOps engineer
- **Phase 8:** Technical writer + QA engineer

### Infrastructure

- Test lab with multi-NUMA systems
- Multiple network adapters (10G, 25G, 100G)
- Various OS platforms for compatibility testing
- CI/CD infrastructure

### Timeline

- **Fast track:** 15-18 weeks (focused team)
- **Standard:** 20-25 weeks (part-time resources)
- **With comprehensive testing:** 28-30 weeks

---

## Risk Mitigation

### Backward Compatibility

- Maintain all existing command-line options
- Default behavior changes are opt-out
- Provide migration tools and documentation

### Performance Impact

- Benchmark before and after each phase
- Ensure new features don't degrade baseline performance
- Make advanced features opt-in if performance cost

### Code Maintainability

- Follow existing code style
- Comprehensive inline documentation
- Modular design for new features
- Unit test coverage >80%

---

## Success Metrics

### Phase 1-2 Success Criteria

- [ ] Default netperf invocation uses OMNI with useful output
- [ ] JSON output validates against schema
- [ ] No performance regression vs. baseline
- [ ] Documentation complete

### Phase 3-4 Success Criteria

- [ ] Multi-instance testing demonstrates linear scaling
- [ ] Aggregate reporting accuracy >99%
- [ ] Directional tests show expected asymmetry

### Phase 5 Success Criteria

- [ ] Automated tuning discovers optimal configuration
- [ ] Recommendations match manual testing results
- [ ] Can run full tuning suite unattended

### Phase 6-7 Success Criteria

- [ ] Netserver binding reduces latency by measurable amount
- [ ] Test catalog demonstrates NUMA impact clearly
- [ ] All tests run reliably across platforms

---

## Next Steps

### Immediate Actions (Next 7 days)

1. Review and approve this roadmap
2. Set up development branch: `git checkout -b dev/phase-1`
3. Create detailed task breakdown for Phase 0 and Phase 1
4. Set up project tracking (GitHub Issues/Projects)
5. Begin current state analysis

### Week 2-3 Actions

1. Complete Phase 0 analysis
2. Begin Phase 1 implementation
3. Create unit test framework
4. Set up CI pipeline for automated testing

---

## Questions for Review

1. **Backward Compatibility:** Should OMNI as default be opt-in for 2.x releases?
2. **Output Format:** JSON schema - any specific requirements?
3. **Multi-instance:** Should this be a separate binary or integrated into netperf?
4. **Remote Config:** SSH-based or require agent installation?
5. **Test Catalog:** Should catalog tests be built-in or plugin architecture?
6. **Priority:** Any phase priority changes based on business needs?

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-30  
**Status:** Draft for Review
