# Netperf - Modern Fork

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-README` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Netperf - Modern Fork under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


A modernized fork of the netperf network performance benchmarking tool with improved defaults, better output formats,
and enhanced usability.

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
- **netperf-profile** - 15 built-in test profiles (baseline, throughput, latency, stress, cloud, datacenter, wireless,
  jitter, lossy, mixed-workload, plus 5 high-speed 200G–600G/OCP profiles)
- **netperf-orchestrate** - Multi-host test coordination with YAML inventory
- **netperf-monitor** - Real-time monitoring with terminal UI
- **netperf-template** - Report generation in 5 formats (markdown, HTML, JSON, CSV, text)
- **100% integration tested** against live netperf infrastructure

### Output Examples

```bash
# Default TCP_STREAM (columnar - backwards compatible)
./build/src/netperf -H host
# MIGRATED TCP STREAM TEST from 0.0.0.0...
# Recv   Send    Send                          
# Socket Socket  Message  Elapsed              
# Size   Size    Size     Time     Throughput  
# bytes  bytes   bytes    secs.    10^6bits/sec

# Modern OMNI keyval output (requires -M flag)
./build/src/netperf -H host -M
# THROUGHPUT=54623.45
# ELAPSED_TIME=1.00
# PROTOCOL=TCP

# JSON output (requires -M flag)
./build/src/netperf -H host -M -- -J
# {"THROUGHPUT": 54623.45, "ELAPSED_TIME": 1.00, ...}

# CSV output (requires -M flag)
./build/src/netperf -H host -M -- -o
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
- **[DOCUMENTATION_STANDARDS.md](dev/docs/DOCUMENTATION_STANDARDS.md)** - Markdown quality standards
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

# 10-second OMNI test with CSV output
netperf -H remotehost -M -l 10 -- -o

# With CPU utilization measurement
netperf -H remotehost -c -C
```

### Request-Response Latency

```bash
# TCP request-response
netperf -H remotehost -t TCP_RR

# OMNI request-response with JSON output
netperf -H remotehost -M -- -d rr -J
```

### Using Output Presets

```bash
# Minimal output (throughput only)
netperf -H remotehost -M -- -k minimal

# Verbose output (all fields)
netperf -H remotehost -M -- -k verbose

# Latency-focused output
netperf -H remotehost -M -- -d rr -k latency
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
| --- | --- | --- | --- |
| **Keyval** (default) | None | Scripting, grep-friendly | `THROUGHPUT=54623.45` |
| **JSON** | `-- -J` | Modern tools, APIs | `{"THROUGHPUT": 54623.45}` |
| **CSV** | `-- -o` | Spreadsheets, analysis | `54623.45,1.00,TCP` |
| **Columnar** | `-- -O` | Human reading | Traditional table format |

## 🛠️ Development

### Project Structure

```text
netperf/
├── src/              # Source code
├── doc/              # Documentation
├── wiki/             # Comprehensive Project Wiki (9 guides & references)
├── dev/              # Development tools and advanced features
│   ├── catalog/      # Output presets, config analysis
│   ├── docs/         # Developer documentation (Phase 1-3 guides)
│   ├── examples/     # Usage examples and sample configs
│   ├── plans/        # Project roadmap and progress tracking
│   ├── profiles/     # Built-in test profiles (15 profiles)
│   ├── scripts/      # Build and utility scripts
│   ├── tests/        # Integration & unit test suites
│   ├── tools/        # Advanced tools (11 production tools)
│   └── Makefile      # Convenience wrapper
└── build/            # Build output (generated)
```

## 📚 Project Wiki

Comprehensive documentation is maintained in the [`wiki/`](wiki/Home.md) directory:

- **[Wiki Home & Architecture Overview](wiki/Home.md)**
- **[Executive Summary](wiki/Executive-Summary.md)** ([dev/docs/EXECUTIVE_SUMMARY.md](dev/docs/EXECUTIVE_SUMMARY.md))
- **[Technical White Paper (100G–800G & Multi-Core Modernization)](wiki/Technical-White-Paper.md)**
  ([dev/docs/TECHNICAL_WHITE_PAPER.md](dev/docs/TECHNICAL_WHITE_PAPER.md))
- **[Getting Started & Installation](wiki/Getting-Started-and-Installation.md)**
- **[Core Engine & OMNI Guide](wiki/Core-Engine-and-OMNI-Guide.md)**
- **[High-Speed 200G–800G & Intel Xeon 6 Guide](wiki/High-Speed-200G-800G-and-Xeon6-Guide.md)**
- **[CLI Tools Reference](wiki/CLI-Tools-Reference.md)**
- **[Test Profiles & Qualification Catalog](wiki/Test-Profiles-and-Qualification-Catalog.md)**
- **[Pre-Flight Checks & Fault Monitoring](wiki/Pre-Flight-Checks-and-Fault-Monitoring.md)**

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

- Mailing list: <netperf-talk@netperf.org>
- Subscription: <netperf-talk-request@netperf.org>

## �️ Advanced Tools (Phase 3)

This fork includes powerful tools for advanced network testing:

### netperf-multi

Parallel test execution across multiple instances:

```bash
# Run 4 parallel tests
netperf-multi -n 4 -l 10 -H remotehost -- -d send

# With custom netperf binary
netperf-multi -n 8 --netperf ./build/src/netperf -H remotehost
```

### netperf_stats.py

Statistical analysis with confidence intervals and outlier detection:

```bash
# Analyze multiple test runs
for i in {1..20}; do netperf -H host -M -- -k THROUGHPUT | grep THROUGHPUT= | cut -d= -f2; done | netperf_stats.py -

# Display ASCII histogram and boxplot
netperf_stats.py results.txt
```

### netperf-profile

Pre-configured test profiles for common scenarios:

```bash
# Run baseline profile (15 built-in profiles)
netperf-profile -p baseline -H remotehost

# Custom profile with YAML
netperf-profile --profile-file my-profile.yaml -H remotehost --dry-run
```

### netperf-orchestrate

Multi-host test orchestration:

```bash
# Run tests across multiple hosts
netperf-orchestrate --hosts hosts.yaml -- -d stream -l 30 -J

# Check connectivity and status
netperf-orchestrate --hosts hosts.yaml --check
netperf-orchestrate --hosts hosts.yaml --status
```

### netperf-monitor

Real-time monitoring with terminal UI:

```bash
# Monitor ongoing tests
netperf-monitor -H remotehost -d 60 --refresh 0.5 -- -d send

# Follow an existing log file
netperf-monitor --follow test.log
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
- ✅ Test profiles system (15 built-in profiles)
- ✅ Multi-host orchestration (netperf-orchestrate)
- ✅ Real-time monitoring TUI (netperf-monitor)
- ✅ Report generation engine (netperf-template)
- ✅ 100% integration testing validated

**Phase 4-7 (COMPLETE)**: 100G–800G High-Speed & Intel Xeon 6 Platform Modernization

- ✅ **Directional & Multi-Port Engine (`netperf-multi` v2.0)**: TX, RX, simultaneous bidirectional (`--direction bx`),
  sequential BX (`bx-seq`), multi-NIC (`-i ens7np0,ens23np0,ens27np0`), multi-subnet (`-H 192.168.10..17.74`), DSCP/ToS
  QoS (`--dscp EF,CS3,AF21,CS0`), and up to 512 streams
- ✅ **Core C Engine Modernization (`src/`)**: `MAXMESSAGESIZE` raised to 4 MB, `-Z` (`SO_ZEROCOPY`/`MSG_ZEROCOPY`),
  512–2048 core `/proc/stat` parser with `active_cpu_util` & `peak_cpu_id` , sysfs PCIe Gen5/Gen6 link & DMI detection,
  and `ETHTOOL_GLINKSETTINGS` (100G–800G)
- ✅ **Xeon 6 Topology & Per-Core `netserver-manager` **: Automatic P-core (Granite Rapids SMT filtering) vs E-core
  (Clearwater Forest / Sierra Forest 4-core L2 module `spread_l2` ) core allocation and per-core `netserver` pool
  (`18600..18663`)
- ✅ **Pre-Flight & Automated BKM Tuner (`netperf-preflight`, `netperf-tuner` )**: 24 E835 feature anti-affinity rules
  (`AA-001`..`AA-024`), background process isolation, 5-run warmup sanity gate (`CV < 5%`), `ice` BKM profiles
  (`cwf-ecore`, `gnr-pcore` , `mtu1500` ), and A/B parameter sweep runner
- ✅ **High-Speed Profiles, Qualification Catalog & AI Validation Reporting (`netperf-catalog`, `netperf_report.py` )**:
  5 new 200G–600G/OCP YAML profiles, 4 qualification suites (`flow-scaling`, `core-locality` , `ring-coalesce-matrix` ,
  `lag-failover-qos` ), and `U1` –`U13` kmsg/ethtool counter delta reporting

- Web-based dashboard
- Historical result database
- Automated regression detection
- Cloud provider integration

See development plans in [dev/plans/](dev/plans/) for detailed progress.

---

**BE SURE TO READ THE MANUAL** (see [doc/netperf.txt](doc/netperf.txt) ) for comprehensive usage information, even
though some sections reference older defaults.

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `README.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-README`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
