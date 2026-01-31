---
layout: default
title: Netperf Modern Fork
---

# Netperf - Modern Fork

A modernized fork of the netperf network performance benchmarking tool with improved defaults, better output formats, and advanced testing capabilities.

**Current Version**: v3.0.0 | **License**: MIT | **Status**: Production Ready

---

## 🚀 Quick Start

```bash
# Clone and build
git clone https://github.com/thehevy/netperf_copilot.git
cd netperf_copilot
./dev/scripts/build.sh --type optimized

# Run a basic test
./build/src/netserver -4 &
./build/src/netperf -H localhost -l 5
```

## ✨ What's New

### Phase 1: Modern Defaults ✅

- Full backwards compatibility (TCP_STREAM default, use `-M` for modern OMNI)
- Key-value output format (parseable)
- JSON and CSV output support
- Interval reporting enabled
- MAXCPUS increased to 2048

### Phase 2: Output Enhancement ✅

- Output preset catalog
- netperf-aggregate tool
- Template system
- Enhanced build scripts

### Phase 3: Advanced Tools ✅ NEW

- **netperf-multi** - Parallel test execution
- **netperf_stats.py** - Statistical analysis
- **netperf-profile** - 10 built-in test profiles
- **netperf-orchestrate** - Multi-host coordination
- **netperf-monitor** - Real-time TUI monitoring
- **netperf-template** - Report generation

---

## 📚 Documentation

### Getting Started

- [Installation & Building](docs/installation.html)
- [Quick Start Guide](docs/quickstart.html)
- [Upgrading from Upstream](UPGRADING.html)

### Core Features

- [OMNI Test Framework](dev/docs/OMNI_REFERENCE.html)
- [Output Formats Guide](dev/docs/OUTPUT_FORMATS.html)
- [Build Configuration](dev/docs/BUILD_CONFIGURATION.html)

### Advanced Tools (Phase 3)

- [Parallel Testing (netperf-multi)](docs/tools/netperf-multi.html)
- [Statistical Analysis (netperf_stats.py)](docs/tools/netperf-stats.html)
- [Test Profiles (netperf-profile)](docs/tools/netperf-profile.html)
- [Multi-Host Orchestration](dev/docs/ORCHESTRATION.html)
- [Real-Time Monitoring](dev/docs/MONITORING.html)
- [Report Generation](docs/tools/netperf-template.html)

### Development

- [Phase 1 Progress](dev/plans/phase-1-progress.html)
- [Phase 2 Progress](dev/plans/phase-2-progress.html)
- [Phase 3 Progress](dev/plans/phase-3-progress.html)
- [Project Roadmap](dev/plans/project-roadmap.html)
- [Integration Testing Results](dev/docs/INTEGRATION_TESTING.html)

---

## 🎯 Key Features

### Parallel Test Execution

```bash
# Run 4 parallel instances
netperf-multi -n 4 -H remotehost -- -d send -l 10
```

### Statistical Analysis

```bash
# Analyze 20 test runs with confidence intervals
for i in {1..20}; do netperf -H host; done | netperf_stats.py -
```

### Pre-Configured Profiles

```bash
# Run baseline validation profile
netperf-profile -p baseline -H remotehost

# Available profiles:
# baseline, throughput, latency, stress, cloud, datacenter,
# wireless, jitter, lossy, mixed-workload
```

### Multi-Host Orchestration

```bash
# Run tests across multiple hosts
netperf-orchestrate -i hosts.yaml -p throughput --parallel
```

### Real-Time Monitoring

```bash
# Monitor live tests with TUI
netperf-monitor --host remotehost --interval 1
```

### Report Generation

```bash
# Generate markdown report
netperf-template -t markdown-report results.json
```

---

## 📊 Performance

**Integration Testing**: 100% pass rate (11/11 tests)  
**Performance Validated**: 19-52 Gbps throughput  
**Test Server**: Live datacenter infrastructure  
**Profiles Available**: 10 built-in scenarios

---

## 🔧 Tools Overview

| Tool | Purpose | Status |
|------|---------|--------|
| **netperf-multi** | Parallel execution (2-16 instances) | ✅ Production |
| **netperf_stats.py** | Statistical analysis with CI | ✅ Production |
| **netperf-profile** | Pre-configured test profiles | ✅ Production |
| **netperf-orchestrate** | Multi-host coordination | ✅ Production |
| **netperf-monitor** | Real-time TUI monitoring | ✅ Production |
| **netperf-template** | Report generation (5 formats) | ✅ Production |

---

## 📦 Installation

### Prerequisites

- GCC or compatible C compiler
- GNU Make
- Python 3.6+ (for advanced tools)
- Optional: jinja2, numpy, matplotlib, pyyaml

### Build from Source

```bash
# Standard build
./dev/scripts/build.sh

# Optimized build (recommended)
./dev/scripts/build.sh --type optimized

# Debug build
./dev/scripts/build.sh --type debug
```

### Install Tools

```bash
# Install netperf binaries
cd build
sudo make install

# Install advanced tools
sudo cp dev/tools/* /usr/local/bin/
sudo cp -r dev/profiles /usr/local/share/netperf/
```

---

## 🧪 Testing

### Run Integration Tests

```bash
# Comprehensive test suite
./dev/tests/integration-test.sh

# Quick smoke tests
./dev/tests/quick-test.sh
```

### Test Output Formats

```bash
# Default TCP_STREAM (backwards compatible)
netperf -H host

# JSON output (requires -M)
netperf -H host -M -- -J

# CSV output (requires -M)
netperf -H host -M -- -o
```

---

## 📖 Examples

### Basic Throughput Test

```bash
netperf -H remotehost -l 10
```

### Request-Response Latency

```bash
# Traditional TCP_RR (columnar output)
netperf -H remotehost -t TCP_RR

# OMNI request-response with JSON (requires -M)
netperf -H remotehost -M -- -P TCP_RR -J
```

### Using Output Presets

```bash
# OMNI output presets (requires -M)
netperf -H remotehost -M -- -k dev/catalog/output-presets/verbose.out
```

### Parallel Testing with Statistics

```bash
# netperf-multi passes -M automatically when using OMNI options
netperf-multi -n 4 -H host -- -M -d send -l 30 | netperf_stats.py -
```

---

## 🗺️ Roadmap

**Phase 1** ✅ Complete - Modern defaults and output formats  
**Phase 2** ✅ Complete - Enhanced output and templates  
**Phase 3** ✅ Complete - Advanced tools and orchestration  
**Phase 4** 🔜 Planned - Enterprise features (web dashboard, database, regression detection)

---

## 🤝 Contributing

Contributions welcome! This is an active modernization project.

- **Report Issues**: [GitHub Issues](https://github.com/thehevy/netperf_copilot/issues)
- **Submit PRs**: [Pull Requests](https://github.com/thehevy/netperf_copilot/pulls)
- **Documentation**: See [dev/docs/](https://github.com/thehevy/netperf_copilot/tree/master/dev/docs)

---

## 📜 License

MIT License - Copyright Hewlett Packard Enterprise Development LP

This fork maintains the original license while adding modernization and usability improvements.

---

## 🔗 Resources

- **GitHub Repository**: [thehevy/netperf_copilot](https://github.com/thehevy/netperf_copilot)
- **Latest Release**: [v3.0.0](https://github.com/thehevy/netperf_copilot/releases/tag/v3.0.0)
- **Documentation**: [dev/docs/](https://github.com/thehevy/netperf_copilot/tree/master/dev/docs)
- **Examples**: [dev/examples/](https://github.com/thehevy/netperf_copilot/tree/master/dev/examples)
- **Upstream Netperf**: [github.com/HewlettPackard/netperf](https://github.com/HewlettPackard/netperf)

---

## 📞 Contact

- **Author**: Modernization project maintainer
- **Original Author**: Rick Jones (Hewlett-Packard)
- **Upstream Mailing List**: <netperf-talk@netperf.org>

---

**⭐ Star this repository** if you find it useful!

**Last Updated**: January 31, 2026 | **Version**: v3.0.0
