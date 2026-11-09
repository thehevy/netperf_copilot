# Netperf Output Selection Presets

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-DEV-CATALOG-OUTPUT-PRESETS-README` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Netperf Output Selection Presets under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


This directory contains predefined output selection templates for netperf OMNI tests.

## Available Presets

### minimal.out

Essential metrics only - throughput, time, CPU
**Use case:** Quick performance checks, automated testing
**Fields:** THROUGHPUT, THROUGHPUT_UNITS, ELAPSED_TIME, PROTOCOL, DIRECTION, LOCAL_CPU_UTIL, REMOTE_CPU_UTIL

### default.out (recommended)

Balanced output with commonly needed metrics
**Use case:** General performance testing, benchmarking
**Fields:** Throughput, CPU, socket sizes, calls, MSS, TOS

### verbose.out

Comprehensive output including latency percentiles
**Use case:** Detailed analysis, performance troubleshooting
**Fields:** All default fields plus latency stats, throughput breakdown, congestion control

### latency.out

Focus on latency metrics and transaction rates
**Use case:** Request-response tests, latency analysis
**Fields:** Transaction rate, RTT, latency percentiles, burst size

### throughput.out

Focus on throughput and data transfer metrics
**Use case:** Bulk transfer tests, bandwidth testing
**Fields:** Directional throughput, bytes sent/received, retransmissions

### cpu.out

Focus on CPU utilization and service demand
**Use case:** CPU efficiency analysis, system load testing
**Fields:** Detailed CPU breakdown, per-core stats, service demand

## Usage

### Using a preset

```bash
# Use default preset
netperf -H host -t OMNI -- -o /path/to/default.out

# Use minimal preset
netperf -H host -t OMNI -- -o /path/to/minimal.out
```

### Installing presets system-wide

```bash
# Copy to netperf data directory
sudo mkdir -p /usr/share/netperf/output-presets
sudo cp *.out /usr/share/netperf/output-presets/
```

### Creating custom presets

1. Copy an existing preset as a template
2. Modify the comma-separated list of output selectors
3. See available selectors: `netperf -H host -t OMNI -- -o '?'`

### Preset File Format

- Single line of comma-separated output selector names
- No spaces (unless part of selector name)
- Names must match exactly (case-sensitive)
- Comments not supported in preset files

## Integration with Phase 1

The default.out preset will be set as the built-in default when no -o option is specified.
This provides sensible defaults while maintaining flexibility.

## Examples

### Compare presets

```bash
# Minimal output
netperf -H server -t OMNI -- -o minimal.out

# Detailed output
netperf -H server -t OMNI -- -o verbose.out
```

### Multi-instance with different presets

```bash
# CPU-focused test
netperf -H server -p 12865 -t OMNI -- -o cpu.out &

# Throughput-focused test
netperf -H server -p 12866 -t OMNI -- -o throughput.out &
```

## Future Enhancements

- JSON format presets
- Category-specific presets (NUMA, PCIe, etc.)
- Test-type optimized presets (STREAM vs RR)
- Preset validation tool

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `dev/catalog/output-presets/README.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-DEV-CATALOG-OUTPUT-PRESETS-README`, `DOC-NETPERF-DEV-CATALOG<wbr>-OUTPUT-PRESETS-README`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
