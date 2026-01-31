# Netperf - Modern Fork

A modernized fork of the netperf network performance benchmarking tool with improved defaults, better output formats, and enhanced usability.

## 🚀 Quick Start

```bash
# Build with optimized configuration
./dev/scripts/build.sh --type optimized

# Or use the convenience Makefile
cd dev
make build

# Run a basic test
./build/src/netserver -4 &
./build/src/netperf -H localhost -l 5
```

## ✨ What's New in This Fork

This fork modernizes netperf with several key improvements while maintaining full backward compatibility:

### Phase 1: Modern Defaults & Output
- **TCP_STREAM remains the default** for full backwards compatibility (use `-M` flag for modern OMNI test)
- **Key-value format is now default** (easier to parse than columnar)
- **JSON output support** via `-- -J` for modern tooling integration
- **CSV output** via `-- -o` for spreadsheet analysis
- **Interval reporting enabled by default** - see progress during long tests
- **MAXCPUS increased to 2048** (was 512) for large systems

### Phase 2: Output Enhancement
- **Output presets catalog** in `dev/catalog/output-presets/`
- **netperf-aggregate tool** for combining multiple test results
- **Template system** for custom output formats
- Enhanced build scripts with multiple build types

### Phase 3: Advanced Tools (NEW!)
- **netperf-multi** - Parallel test execution (2-16 instances)
- **netperf_stats.py** - Statistical analysis with CI and outliers
- **netperf-profile** - 10 built-in test profiles (baseline, throughput, latency, stress, cloud, datacenter, wireless, jitter, lossy, mixed-workload)
- **netperf-orchestrate** - Multi-host test coordination with YAML inventory
- **netperf-monitor** - Real-time monitoring with terminal UI
- **netperf-template** - Report generation in 5 formats (markdown, HTML, JSON, CSV, text)
- **100% integration tested** against live netperf infrastructure

### Output Examples

```bash
# Default keyval output
./netperf -H host
# THROUGHPUT=54623.45
# ELAPSED_TIME=1.00
# PROTOCOL=TCP

# JSON output
./netperf -H host -- -J
# {"THROUGHPUT": 54623.45, "ELAPSED_TIME": 1.00, ...}

# CSV output  
./netperf -H host -- -o
# Throughput,Elapsed Time,Protocol
# 54623.45,1.00,TCP
```

### Improved User Experience
- Command line included in output for reproducibility
- Pre-defined output presets in `dev/catalog/output-presets/`
- Burst mode enabled for realistic request-response tests
- Demo/interval support enabled out of the box
- CPU measurement auto-configured per platform

## 📚 Documentation

### Core Documentation
- **[BUILD_CONFIGURATION.md](dev/docs/BUILD_CONFIGURATION.md)** - Complete guide to configure options
- **[UPGRADING.md](UPGRADING.md)** - Migration guide from upstream netperf
- **[Original Manual](doc/netperf.txt)** - Upstream documentation (still relevant)

### Phase 3 Tools Documentation
- **[OMNI_REFERENCE.md](dev/docs/OMNI_REFERENCE.md)** - Comprehensive OMNI test guide
- **[MONITORING.md](dev/docs/MONITORING.md)** - Real-time monitoring and TUI
- **[ORCHESTRATION.md](dev/docs/ORCHESTRATION.md)** - Multi-host test coordination
- **[INTEGRATION_TESTING.md](dev/docs/INTEGRATION_TESTING.md)** - Integration test results

### Development Plans
- **[Phase 1 Progress](dev/plans/phase-1-progress.md)** - Initial modernization (complete)
- **[Phase 2 Progress](dev/plans/phase-2-progress.md)** - Output enhancements (complete)
- **[Phase 3 Progress](dev/plans/phase-3-progress.md)** - Advanced tools (complete)

## 🔧 Building

### Quick Build
```bash
./dev/scripts/build.sh
```

### Build Types
```bash
# Release build (default)
./dev/scripts/build.sh

# Debug build with symbols
./dev/scripts/build.sh --type debug

# Optimized build with recommended options
./dev/scripts/build.sh --type optimized

# Custom configure options
./dev/scripts/build.sh -- --enable-histogram --enable-sctp
```

### Using the Makefile
```bash
cd dev
make help          # Show all available targets
make build         # Standard build
make debug         # Debug build
make test          # Run functional tests
make test-formats  # Test all output formats
```

## 📦 Installation

```bash
cd build
sudo make install

# Or specify custom prefix
sudo make install PREFIX=/usr/local
```

## 🧪 Testing

```bash
# Basic tests
cd dev
make test

# Test all output formats
make test-formats

# Test multiple protocols
make test-protocols

# Performance benchmark
make benchmark
```

## 📋 Examples

### Basic Throughput Test
```bash
# Default (TCP_STREAM with columnar output - backwards compatible)
netperf -H remotehost

# Modern OMNI (requires -M flag)
netperf -H remotehost -M

# 10-second test with CSV output
netperf -H remotehost -l 10 -- -o

# With CPU utilization measurement
netperf -H remotehost -c -C
```

### Request-Response Latency
```bash
# TCP request-response
netperf -H remotehost -t TCP_RR

# With JSON output
netperf -H remotehost -t TCP_RR -- -J
```

### Using Output Presets
```bash
# Minimal output (throughput only)
netperf -H remotehost -- -k dev/catalog/output-presets/minimal.out

# Verbose output (all fields)
netperf -H remotehost -- -k dev/catalog/output-presets/verbose.out

# Latency-focused output
netperf -H remotehost -t TCP_RR -- -k dev/catalog/output-presets/latency.out
```

## 🔄 Backward Compatibility

This fork is **fully backward compatible** with upstream netperf:

- All classic test names still work (TCP_STREAM, TCP_RR, etc.)
- Original command-line options unchanged
- Can use columnar output with `-- -O` flag
- Compatible with existing netserver instances
- Scripts and automation work unchanged

## 📊 Output Formats Comparison

| Format | Flag | Use Case | Example |
|--------|------|----------|---------|
| **Keyval** (default) | None | Scripting, grep-friendly | `THROUGHPUT=54623.45` |
| **JSON** | `-- -J` | Modern tools, APIs | `{"THROUGHPUT": 54623.45}` |
| **CSV** | `-- -o` | Spreadsheets, analysis | `54623.45,1.00,TCP` |
| **Columnar** | `-- -O` | Human reading | Traditional table format |

## 🛠️ Development

### Project Structure
```
netperf/
├── src/              # Source code
├── doc/              # Documentation
├── dev/              # Development tools and advanced features
│   ├── catalog/      # Output presets, config analysis
│   ├── docs/         # Developer documentation (Phase 1-3 guides)
│   ├── examples/     # Usage examples and sample configs
│   ├── plans/        # Project roadmap and progress tracking
│   ├── profiles/     # Built-in test profiles (10 profiles)
│   ├── scripts/      # Build and utility scripts
│   ├── tests/        # Integration test suites
│   ├── tools/        # Advanced tools (6 production tools)
│   └── Makefile      # Convenience wrapper
└── build/            # Build output (generated)
```

### Build Configuration
See [BUILD_CONFIGURATION.md](dev/docs/BUILD_CONFIGURATION.md) for comprehensive documentation on:
- All configure options and their impact
- Performance implications of different settings
- Use-case specific configurations
- Platform-specific considerations

## 🐛 Known Issues

- Documentation build requires `makeinfo` (optional, binaries build fine)
- CPU measurement with `-c -C` requires compatible netserver version
- Some legacy test options may show deprecation warnings

## 📜 License

This fork maintains the original MIT license from Hewlett Packard Enterprise Development LP.

## 🙏 Credits

- **Original Author**: Rick Jones (Hewlett-Packard)
- **Original License**: MIT (Hewlett Packard Enterprise Development LP)
- **This Fork**: Modernization, usability improvements, and advanced tooling
- **Version**: 2.7.1+ / v3.0.0 (with Phase 3 complete)

## 📞 Contact & Contributing

This is a personal fork focused on modernization and improved defaults. 

For the original upstream netperf:
- Mailing list: netperf-talk@netperf.org
- Subscription: netperf-talk-request@netperf.org

## �️ Advanced Tools (Phase 3)

This fork includes powerful tools for advanced network testing:

### netperf-multi
Parallel test execution across multiple instances:
```bash
# Run 4 parallel tests
netperf-multi -n 4 -H remotehost -- -d send -l 10

# With custom netperf binary
netperf-multi -n 8 --netperf ./build/src/netperf -H remotehost
```

### netperf_stats.py
Statistical analysis with confidence intervals and outlier detection:
```bash
# Analyze multiple test runs
for i in {1..20}; do netperf -H host; done | netperf_stats.py -

# Generate histogram
netperf_stats.py results.txt --histogram histogram.png
```

### netperf-profile
Pre-configured test profiles for common scenarios:
```bash
# Run baseline profile (10 built-in profiles)
netperf-profile -p baseline -H remotehost

# Custom profile with YAML
netperf-profile -p my-profile.yaml -H remotehost --dry-run
```

### netperf-orchestrate
Multi-host test orchestration:
```bash
# Run tests across multiple hosts
netperf-orchestrate -i hosts.yaml -p throughput --parallel

# Generate inventory
netperf-orchestrate --generate-inventory > hosts.yaml
```

### netperf-monitor
Real-time monitoring with terminal UI:
```bash
# Monitor ongoing tests
netperf-monitor --host remotehost --interval 1

# Demo mode
netperf-monitor --demo
```

### netperf-template
Report generation in multiple formats:
```bash
# Generate markdown report
netperf-template -t markdown-report results.json

# Custom Jinja2 template
netperf-template -t my-template.j2 results.json -o report.html
```

See [dev/docs/](dev/docs/) for comprehensive documentation on all tools.

## 🗺️ Roadmap

**Phase 1 (COMPLETE)**: Modernize defaults and output
- ✅ Full backwards compatibility (TCP_STREAM default, -M flag for OMNI)
- ✅ Better output formats (keyval, JSON, CSV)
- ✅ Interval reporting by default
- ✅ Improved build system
- ✅ Comprehensive documentation

**Phase 2 (COMPLETE)**: Enhanced testing capabilities
- ✅ Advanced output formats and templates
- ✅ Output preset catalog
- ✅ Aggregation tools (netperf-aggregate)
- ✅ Template system for custom formats

**Phase 3 (COMPLETE)**: Advanced Tools & Orchestration
- ✅ Multi-instance parallel execution (netperf-multi)
- ✅ Statistical analysis with CI (netperf_stats.py)
- ✅ Test profiles system (10 built-in profiles)
- ✅ Multi-host orchestration (netperf-orchestrate)
- ✅ Real-time monitoring TUI (netperf-monitor)
- ✅ Report generation engine (netperf-template)
- ✅ 100% integration testing validated

**Phase 4 (Future)**: Enterprise Features
- Web-based dashboard
- Historical result database
- Automated regression detection
- Cloud provider integration

See development plans in [dev/plans/](dev/plans/) for detailed progress.

---

**BE SURE TO READ THE MANUAL** (see [doc/netperf.txt](doc/netperf.txt)) for comprehensive usage information, even though some sections reference older defaults.
