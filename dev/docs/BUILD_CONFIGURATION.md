# Netperf Build Configuration Guide

## Overview

Netperf uses GNU Autotools (autoconf/automake) for platform-portable builds. The `configure` script provides numerous options that control which tests are compiled, how CPU utilization is measured, and whether certain features that may affect benchmark results are enabled.

This guide provides comprehensive documentation of all configuration options, their performance impact, and recommendations for different use cases.

## Quick Start

### Recommended Build (Optimized)

```bash
./dev/scripts/configure-optimized.sh
cd build
make -j$(nproc)
```

This provides the best balance of performance, usability, and protocol coverage.

### Minimal Build

```bash
./configure --enable-omni --enable-demo --disable-histogram --disable-dirty --disable-intervals
make
```

### Full-Featured Build

```bash
./configure --enable-omni --enable-demo --enable-sctp --enable-unixdomain --enable-burst
make
```

## Configuration Options Reference

### Performance-Critical Options

These options directly affect benchmark results and should be chosen carefully:

#### `--enable-histogram` (default: **no**)
- **Impact**: HIGH - Adds per-operation timing overhead
- **Affects Results**: YES - May reduce throughput by 5-15%
- **Purpose**: Records detailed per-operation latency histograms
- **Recommendation**: Only enable for detailed latency analysis
- **Use case**: When you need percentile latency (p50, p95, p99)

```bash
# Enable histogram for latency analysis
./configure --enable-histogram
```

#### `--enable-dirty` (default: **no**)
- **Impact**: MEDIUM - Forces cache misses
- **Affects Results**: YES - Reduces throughput significantly (20-40%)
- **Purpose**: Writes to buffers each time to avoid cache effects
- **Recommendation**: Only for testing real-world scenarios with dirty buffers
- **Use case**: Measuring performance with cold cache

```bash
# Enable dirty buffers
./configure --enable-dirty
```

#### `--enable-intervals` (default: **no**)
- **Impact**: MEDIUM - Adds pacing/throttling overhead
- **Affects Results**: YES - May reduce throughput by 1-5%
- **Purpose**: Enables paced/throttled operations for rate limiting
- **Recommendation**: Enable if testing rate-limited scenarios
- **Use case**: Traffic shaping, QoS testing

```bash
# Enable paced operations
./configure --enable-intervals
```

#### `--enable-spin` (default: **no**)
- **Impact**: HIGH - Busy-waits instead of sleeping
- **Affects Results**: YES - Distorts CPU utilization dramatically
- **Purpose**: Makes paced operations busy-wait
- **Recommendation**: **AVOID** - Burns CPU cycles unnecessarily
- **Requires**: `--enable-intervals`

```bash
# DO NOT USE unless you have a specific need
./configure --enable-intervals --enable-spin
```

### User Experience Options

#### `--enable-demo` (default: **yes** as of Phase 1)
- **Impact**: LOW - Minimal overhead
- **Affects Results**: MAYBE - Slight I/O overhead for interim output
- **Purpose**: Shows interim results during test runs
- **Recommendation**: **RECOMMENDED** - Enabled by default
- **Use case**: All tests - provides progress feedback

```bash
# Disable if you want absolutely minimal overhead
./configure --disable-demo
```

#### `--enable-burst` (default: **yes**)
- **Impact**: LOW - Changes test behavior, not overhead
- **Affects Results**: MAYBE - Models TCP slow-start
- **Purpose**: Enables initial burst in request-response tests
- **Recommendation**: **RECOMMENDED** - Useful for realistic workloads
- **Use case**: Request-response latency tests

### Protocol Options

#### `--enable-omni` (default: **yes**)
- **Impact**: NONE - Core test framework
- **Affects Results**: NO
- **Purpose**: Includes modern OMNI test framework
- **Recommendation**: **REQUIRED** - Always enable
- **Note**: Also enables `WANT_MIGRATION` for classic test compatibility

#### `--enable-sctp` (default: **no**)
- **Impact**: NONE - Just adds test code
- **Affects Results**: NO
- **Purpose**: Includes SCTP protocol tests
- **Recommendation**: Enable if testing SCTP
- **Dependencies**: Requires `netinet/sctp.h`, may need `libsctp`

```bash
./configure --enable-sctp
```

#### `--enable-unixdomain` (default: **no**)
- **Impact**: NONE
- **Affects Results**: NO
- **Purpose**: Includes Unix domain socket tests
- **Recommendation**: Enable if testing IPC performance
- **Use case**: Inter-process communication benchmarking

```bash
./configure --enable-unixdomain
```

#### `--enable-dccp` (default: **no**)
- **Impact**: NONE
- **Affects Results**: NO
- **Purpose**: Includes DCCP (Datagram Congestion Control Protocol) tests
- **Recommendation**: Enable if testing DCCP
- **Dependencies**: Requires kernel DCCP support

#### `--enable-dlpi` (default: **no**)
- **Impact**: NONE
- **Affects Results**: NO
- **Purpose**: Includes DLPI (Data Link Provider Interface) tests
- **Recommendation**: Only for link-layer testing on Solaris
- **Note**: Rarely used, very specialized

#### `--enable-xti` (default: **no**)
- **Impact**: NONE
- **Affects Results**: NO
- **Purpose**: Includes XTI (X/Open Transport Interface) tests
- **Recommendation**: Only for legacy systems
- **Note**: XTI is deprecated, use BSD sockets instead

#### `--enable-sdp` (default: **no**)
- **Impact**: NONE
- **Affects Results**: NO
- **Purpose**: Includes SDP (Sockets Direct Protocol) tests
- **Recommendation**: Enable if testing InfiniBand/RDMA
- **Dependencies**: Requires `libsdp`

#### `--enable-exs` (default: **no**)
- **Impact**: NONE
- **Affects Results**: NO
- **Purpose**: Includes ICSC-EXS async socket tests
- **Recommendation**: Only for ICSC hardware
- **Dependencies**: Requires `sys/exs.h` and `libexs`
- **Note**: Very specialized, rare hardware

### CPU Measurement Options

#### `--enable-cpuutil=METHOD` (default: **auto**)
- **Impact**: NONE - Measurement method
- **Affects Results**: NO
- **Purpose**: Selects CPU utilization measurement method
- **Recommendation**: Let configure auto-detect

Platform-specific methods:
- **procstat** - Linux `/proc/stat` interface
- **pstat/pstatnew** - HP-UX `pstat()` interface
- **perfstat** - AIX `perfstat()` interface
- **kstat/kstat10** - Solaris `kstat` interface
- **sysctl** - BSD/FreeBSD `sysctl()` interface
- **osx** - macOS X `host_info()` interface
- **looper** - Portable soaker processes (fallback)
- **none** - No CPU measurement

```bash
# Usually not needed - auto-detection works well
./configure --enable-cpuutil=procstat  # Linux
./configure --enable-cpuutil=osx       # macOS
./configure --enable-cpuutil=none      # Disable CPU measurement
```

## Configuration Recommendations by Use Case

### High-Precision Throughput Testing

Maximum throughput with minimal overhead:

```bash
./configure \
  --enable-omni \
  --enable-demo \
  --disable-histogram \
  --disable-dirty \
  --disable-intervals
```

### Detailed Latency Analysis

Per-operation timing with histograms:

```bash
./configure \
  --enable-omni \
  --enable-demo \
  --enable-histogram \
  --enable-burst
```

**Warning**: Histogram overhead may skew results. Compare with baseline.

### Real-World Scenario Testing

Dirty buffers to model production workloads:

```bash
./configure \
  --enable-omni \
  --enable-demo \
  --enable-dirty \
  --enable-burst
```

### Rate-Limited/QoS Testing

Paced operations for traffic shaping:

```bash
./configure \
  --enable-omni \
  --enable-demo \
  --enable-intervals \
  --enable-burst
```

### Multi-Protocol Testing

All common protocols:

```bash
./configure \
  --enable-omni \
  --enable-demo \
  --enable-sctp \
  --enable-unixdomain \
  --enable-dccp \
  --enable-burst
```

### Minimal Footprint

Smallest binary size:

```bash
./configure \
  --enable-omni \
  --disable-demo \
  --disable-histogram \
  --disable-dirty \
  --disable-intervals \
  --disable-burst \
  --disable-unixdomain \
  --disable-sctp
```

## Performance Impact Testing

To measure the performance impact of different configuration options, use:

```bash
./dev/scripts/test-configure-impact.sh
```

This script builds netperf with various configurations and compares throughput and CPU utilization.

### Typical Performance Impacts

Based on internal testing on Linux x86_64:

| Option | Throughput Impact | CPU Impact | Notes |
|--------|------------------|------------|-------|
| histogram | -5% to -15% | Minimal | Per-op timing overhead |
| dirty | -20% to -40% | Minimal | Forces cache misses |
| demo | -0% to -2% | Minimal | I/O for interim results |
| intervals | -1% to -5% | Minimal | Pacing overhead |
| spin | Variable | **HIGH** | Burns CPU cycles |
| burst | ±5% | Minimal | Changes behavior, not overhead |

## Configuration File Reference

All configuration options are documented in:
- **configure.ac** - Autoconf input (source of truth)
- **dev/catalog/configure-options.csv** - Spreadsheet analysis
- **config.h** - Generated C preprocessor definitions

Key preprocessor macros:
- `WANT_OMNI` - OMNI tests enabled
- `WANT_DEMO` - Interim results enabled
- `WANT_HISTOGRAM` - Per-operation timing enabled
- `DIRTY` - Dirty buffer support enabled
- `WANT_INTERVALS` - Paced operations enabled
- `WANT_SPIN` - Busy-wait pacing enabled
- `WANT_FIRST_BURST` - Initial burst enabled
- `WANT_SCTP` - SCTP tests enabled
- `WANT_UNIX` - Unix domain socket tests enabled
- `USE_PROC_STAT` / `USE_PSTAT` / `USE_PERFSTAT` / etc. - CPU method

## Build Scripts

### configure-optimized.sh

Recommended configuration with sensible defaults:

```bash
./dev/scripts/configure-optimized.sh
```

Options:
- `--minimal` - Minimal build (OMNI + demo only)
- `--all-protocols` - Enable all protocol tests
- `--with-histogram` - Override: enable histogram
- `--with-dirty` - Override: enable dirty buffers
- `--with-intervals` - Override: enable paced operations
- `--build-dir DIR` - Build in specific directory
- `--prefix DIR` - Install prefix

### build.sh

Standard build script (uses current configuration):

```bash
./dev/scripts/build.sh
```

### clean.sh

Clean build artifacts:

```bash
./dev/scripts/clean.sh
```

## Regenerating Configure Script

If you modify `configure.ac`:

```bash
./autogen.sh
```

This runs:
1. `aclocal` - Generate `aclocal.m4` from m4 macros
2. `autoheader` - Generate `config.h.in` template
3. `automake` - Generate `Makefile.in` templates
4. `autoconf` - Generate `configure` script

## Troubleshooting

### Missing CPU Utilization Measurements

If CPU utilization shows `-1.00`:

1. Check which method was selected:
   ```bash
   grep USE_ build/config.h | grep CPU
   ```

2. Try different methods:
   ```bash
   ./configure --enable-cpuutil=looper  # Fallback method
   ```

### Compilation Errors with Protocol Tests

If SCTP/DCCP/etc. fail to compile:

1. Check dependencies:
   ```bash
   dpkg -l | grep libsctp    # Debian/Ubuntu
   rpm -qa | grep lksctp     # RHEL/CentOS
   ```

2. Disable problematic protocols:
   ```bash
   ./configure --disable-sctp
   ```

### Performance Anomalies

If results seem wrong:

1. Check for performance-affecting options:
   ```bash
   grep -E 'WANT_HISTOGRAM|DIRTY|WANT_SPIN' build/config.h
   ```

2. Rebuild with baseline configuration:
   ```bash
   ./dev/scripts/configure-optimized.sh
   ./dev/scripts/build.sh
   ```

## References

- [configure.ac](../../configure.ac) - Configuration source
- [dev/catalog/configure-options.csv](../catalog/configure-options.csv) - Options analysis
- [Autoconf Manual](https://www.gnu.org/software/autoconf/manual/)
- [Automake Manual](https://www.gnu.org/software/automake/manual/)

## Summary

**Recommended default configuration** (already implemented in Phase 1):
```bash
./dev/scripts/configure-optimized.sh
```

This enables:
- ✅ OMNI test framework
- ✅ Interim results (demo)
- ✅ Initial burst in RR tests
- ✅ SCTP and Unix domain socket tests
- ✅ Auto-detected CPU measurement
- ❌ No histogram overhead
- ❌ No dirty buffer overhead
- ❌ No interval/spin overhead

For specific needs, see the use-case recommendations above.
