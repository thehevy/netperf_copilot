# Netperf AI Agent Instructions

## Project Overview

Netperf is a network performance benchmarking tool for measuring TCP, UDP, SCTP, DLPI, and Unix Domain socket performance. It operates in a client-server model where `netperf` (client) connects to `netserver` (daemon) to conduct performance tests and measure throughput, latency, and CPU utilization.

**License**: MIT (Hewlett Packard Enterprise Development LP)  
**Version**: 2.7.1  
**Language**: C (ANSI C with platform-specific extensions)

## Architecture

### Core Components

- **netperf** ([src/netperf.c](../src/netperf.c)): Client-side test initiator and results reporter
- **netserver** ([src/netserver.c](../src/netserver.c)): Server-side daemon handling test requests
- **netlib** ([src/netlib.c](../src/netlib.c), [src/netlib.h](../src/netlib.h)): Shared library with common utilities (control protocol, CPU measurement, statistics)
- **netsh** ([src/netsh.c](src/netsh.h)): Command-line parsing and test dispatching

### Test Framework Architecture

#### Classic vs OMNI Tests

The codebase contains two test architectures:

- **Classic tests**: Original implementations in `nettest_bsd.c`, `nettest_unix.c`, `nettest_dlpi.c`, `nettest_xti.c`, `nettest_sctp.c`, `nettest_sdp.c`
- **OMNI tests** ([src/nettest_omni.c](../src/nettest_omni.c)): Modern unified framework that can emulate all classic tests with extensible output formatting. OMNI is the preferred test type (7699 lines, single file handling multiple protocols/patterns).

When `WANT_MIGRATION` is defined, classic test names (TCP_STREAM, TCP_RR, etc.) automatically map to OMNI equivalents.

#### Test Types by Pattern

- **STREAM**: Unidirectional bulk transfer (throughput measurement)
- **RR** (Request-Response): Bidirectional latency/transaction rate measurement
- **CRR** (Connect-Request-Response): Includes connection establishment overhead
- **MAERTS**: Reverse direction STREAM (server to client)

### Platform Abstraction Layer

#### CPU Utilization Measurement (netcpu_*.c)

Netperf implements platform-specific CPU measurement via pluggable modules selected at **configure time** via `--enable-cpuutil=<method>`:

- **netcpu_procstat.c**: Linux `/proc/stat` (default for Linux)
- **netcpu_pstat.c / pstatnew.c**: HP-UX `pstat()` interface
- **netcpu_perfstat.c**: AIX `perfstat()` interface  
- **netcpu_kstat.c / kstat10.c**: Solaris `kstat` interface
- **netcpu_sysctl.c**: BSD/MacOS `sysctl()` interface
- **netcpu_osx.c**: MacOS X `host_info()` interface
- **netcpu_looper.c**: Portable soaker processes (fallback for systems without native counters)
- **netcpu_none.c**: Stub implementation (no CPU measurement)

The Makefile uses `USE_CPU_SOURCE=netcpu_@NETCPU_SOURCE@.c` to select the appropriate implementation. All modules implement the same interface defined in [src/netcpu.h](../src/netcpu.h).

#### Other Platform Modules

Similar pattern for: `netsys_*.c` (system info), `netdrv_*.c` (driver stats), `netsec_*.c` (security contexts), `netslot_*.c` (slot affinity), `netfirewall_*.c` (firewall rules).

## Build System (GNU Autotools)

### Configuration Workflow

```bash
./autogen.sh          # Generate configure script (if building from git)
./configure [options] # Platform detection and feature selection
make                  # Compile netperf and netserver
make install          # Install binaries
```

### Key Configure Options

Configure selects CPU method automatically based on platform but can be overridden:

```bash
--enable-cpuutil={procstat|pstat|perfstat|kstat|sysctl|osx|looper|none}
--enable-histogram      # Per-operation timing (affects performance)
--enable-omni           # Include OMNI tests (default: enabled)
--enable-unixdomain     # Unix domain socket tests
--enable-sctp           # SCTP protocol support
--enable-intervals      # Paced operation support
--enable-demo           # Interim results during test runs
```

### Build Artifacts

- **config.h**: Platform feature detection results (HAVE_*, USE_*, WANT_* macros)
- **src/netperf_version.h**: Auto-generated version header
- **Binaries**: `src/netperf`, `src/netserver`

## Coding Conventions

### Preprocessor Patterns

- **Feature detection**: `HAVE_*` (from autoconf, e.g., `HAVE_GETADDRINFO`, `HAVE_LINUX_TCP_H`)
- **Test enablement**: `WANT_*` (e.g., `WANT_OMNI`, `WANT_UNIX`, `WANT_SCTP`, `WANT_HISTOGRAM`)
- **Platform methods**: `USE_*` (e.g., `USE_PROC_STAT`, `USE_PSTAT`, `USE_LOOPER`)

Example from [src/nettest_omni.c](../src/nettest_omni.c):

```c
#ifdef WANT_OMNI
#ifdef HAVE_LINUX_TCP_H
#include <linux/tcp.h>
#else
#include <netinet/tcp.h>
#endif
```

### Error Handling

- Extensive use of `fprintf(where, ...)` for diagnostics (where = stderr or debug file)
- `Set_errno()` wrapper for cross-platform errno handling
- Graceful degradation: tests proceed even if optional features unavailable

### Control Protocol Pattern

Client-server communication uses a request-response pattern with predefined message types in [src/netlib.h](../src/netlib.h):

```c
#define DO_TCP_STREAM           10
#define TCP_STREAM_RESPONSE     11
#define TCP_STREAM_RESULTS      12
```

Functions: `send_request()`, `recv_response()`, `send_response()`, `recv_request()`

## Development Workflows

### Running Tests Locally

```bash
# Start server (run as daemon or foreground)
./src/netserver -D         # Debug mode (foreground)
./src/netserver            # Daemon mode

# Run client tests
./src/netperf -H localhost                    # Basic TCP_STREAM test
./src/netperf -H localhost -t TCP_RR          # Request-response latency
./src/netperf -H localhost -t OMNI -- -d send # OMNI unidirectional send
```

### Example Scripts

Comprehensive test examples in [doc/examples/](../doc/examples/):

- `tcp_stream_script`, `tcp_rr_script`, `udp_stream_script`: Shell-based test harnesses
- `*.py` scripts: Python post-processing utilities
- `runemomni*.sh`: Aggregated OMNI test suites

### Debugging

- Global `-d` option increases debug level (see `debug` variable in [src/netsh.h](../src/netsh.h))
- Check `lib_num_loc_cpus` initialization in CPU modules for CPU detection issues
- OMNI output selectors documented in [doc/omni_output_list.txt](../doc/omni_output_list.txt)

## Common Patterns

### Adding a New Test Type

1. Choose OMNI or classic framework (prefer OMNI for new tests)
2. Define message types in [src/netlib.h](../src/netlib.h) (e.g., `DO_MY_TEST`, `MY_TEST_RESPONSE`)
3. Implement test logic in appropriate `nettest_*.c` file
4. Add test name mapping in [src/netsh.c](../src/netsh.c) `scan_cmd_line()`
5. Update [configure.ac](../configure.ac) if new dependencies/options needed

### Platform-Specific Code

When adding platform support, follow the existing pattern:

1. Create new `netcpu_<platform>.c` implementing the standard interface
2. Add configure detection case in [configure.ac](../configure.ac) around line 660
3. Update `EXTRA_DIST` in [src/Makefile.am](../src/Makefile.am)
4. Test with `./configure --enable-cpuutil=<your-method>`

### CPU Affinity/Binding

Multiple platform-specific mechanisms detected via autoconf:

- Linux: `sched_setaffinity()`
- HP-UX: `mpctl()`
- Solaris: `processor_bind()`
- AIX: `bindprocessor()`

Usage controlled by `cpu_binding_requested` global variable.

## Key Files Reference

| File | Purpose |
|------|---------|
| [src/nettest_omni.c](../src/nettest_omni.c) | Modern unified test framework (7699 lines) |
| [src/netlib.c](../src/netlib.c) | Core networking utilities (5002 lines) |
| [src/netserver.c](../src/netserver.c) | Server daemon implementation (1561 lines) |
| [configure.ac](../configure.ac) | Autoconf configuration logic (750 lines) |
| [doc/netperf.txt](../doc/netperf.txt) | Primary documentation (outdated but useful) |
| [doc/omni_output_list.txt](../doc/omni_output_list.txt) | OMNI output selector reference |

## Historical Context

- Pre-2.0: Separate test files for each protocol/pattern combination
- 2.x: Introduction of OMNI unified framework with flexible output formatting
- 2.6.0+: Removal of peripheral features (driver stats, DNS tests) to focus on core mission
- 2.7.0+: Improved interim results, symbolic IP_TOS manipulation, bits/s throughput units

## Notes for AI Agents

- **Always check config.h conditionals** before suggesting platform-specific code
- **OMNI tests are preferred** over adding new classic test types
- **CPU measurement is compile-time selected** - cannot be changed at runtime
- **Statistics and confidence intervals** are complex - see [src/netlib.c](../src/netlib.c) around line 4700
- **Windows support exists** but is secondary - primary development targets Unix-like systems
