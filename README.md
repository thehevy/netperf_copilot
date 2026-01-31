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

### 1. Modern Default Test (OMNI)
- **OMNI is now the default test** instead of TCP_STREAM
- More flexible output with customizable field selection
- Unified framework supporting all protocol patterns

### 2. Better Output Formats
- **Key-value format is now default** (easier to parse than columnar)
- **JSON output support** via `-- -J` for modern tooling integration
- **CSV output** via `-- -o` for spreadsheet analysis  
- Original columnar format still available via `-- -O`

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

### 3. Improved User Experience
- **Interval reporting enabled by default** - see progress during long tests
- **Pre-defined output presets** in `dev/catalog/output-presets/`
- **Command line included in output** for reproducibility
- Enhanced build scripts with multiple build types

### 4. Better Defaults
- OMNI test framework with sensible output fields
- Burst mode enabled for realistic request-response tests
- Demo/interval support enabled out of the box
- CPU measurement auto-configured per platform

### 5. Support for Large Systems
- **MAXCPUS increased to 2048** (was 512)
- Tested on systems with 288-512 CPU cores
- Scales to modern high-core-count servers

### 6. Modern Build System
- Intelligent `configure-optimized.sh` with presets
- Enhanced `build.sh` with debug/release/optimized modes
- Convenience `Makefile` with common development tasks
- Comprehensive build configuration documentation

## 📚 Documentation

- **[BUILD_CONFIGURATION.md](dev/docs/BUILD_CONFIGURATION.md)** - Complete guide to configure options
- **[UPGRADING.md](UPGRADING.md)** - Migration guide from upstream netperf
- **[Phase 1 Project Plan](dev/plans/phase-1-progress.md)** - Development roadmap and progress
- **[Original Manual](doc/netperf.txt)** - Upstream documentation (still relevant)

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
# Default (OMNI with keyval output)
netperf -H remotehost

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
├── dev/              # Development tools (NEW)
│   ├── catalog/      # Output presets, config analysis
│   ├── docs/         # Developer documentation
│   ├── plans/        # Project roadmap
│   ├── scripts/      # Build and utility scripts
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
- **This Fork**: Modernization and usability improvements
- **Version**: 2.7.1+ (fork development branch)

## 📞 Contact & Contributing

This is a personal fork focused on modernization and improved defaults. 

For the original upstream netperf:
- Mailing list: netperf-talk@netperf.org
- Subscription: netperf-talk-request@netperf.org

## 🗺️ Roadmap

**Phase 1 (COMPLETE)**: Modernize defaults and output
- ✅ OMNI as default test
- ✅ Better output formats (keyval, JSON, CSV)
- ✅ Interval reporting by default
- ✅ Improved build system
- ✅ Comprehensive documentation

**Phase 2 (Planned)**: Enhanced testing capabilities
- Advanced output formats and templates
- Test automation framework
- Result comparison and regression detection

See [Phase 1 Progress](dev/plans/phase-1-progress.md) for detailed development status.

---

**BE SURE TO READ THE MANUAL** (see [doc/netperf.txt](doc/netperf.txt)) for comprehensive usage information, even though some sections reference older defaults.
