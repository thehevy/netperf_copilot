---
layout: default
title: Installation Guide
---

# Installation Guide

Complete guide to installing and building the modernized netperf fork.

[← Back to Documentation](index.html)

---

## System Requirements

### Minimum Requirements

- **OS**: Linux, macOS, BSD, Solaris, AIX, HP-UX
- **Compiler**: GCC 4.8+ or Clang 3.5+
- **Build Tools**: GNU Make, autoconf, automake
- **Memory**: 64 MB RAM
- **Disk**: 50 MB free space

### Recommended Requirements

- **OS**: Linux 4.x+ or macOS 10.14+
- **Compiler**: GCC 9+ or Clang 10+
- **Python**: 3.8+ (for advanced tools)
- **Memory**: 256 MB RAM
- **Network**: High-speed link (1 Gbps+)

### Optional Dependencies

For advanced tools functionality:

```bash
# Python packages
pip3 install jinja2 numpy matplotlib pyyaml

# Or using system packages (Debian/Ubuntu)
sudo apt install python3-jinja2 python3-numpy python3-matplotlib python3-yaml

# Or using system packages (RHEL/CentOS)
sudo yum install python3-jinja2 python3-numpy python3-matplotlib python3-pyyaml
```

---

## Quick Installation

### Method 1: Standard Build (Recommended)

```bash
# Clone repository
git clone https://github.com/thehevy/netperf_copilot.git
cd netperf_copilot

# Build with optimized configuration
./dev/scripts/build.sh --type optimized

# Install binaries
cd build
sudo make install

# Install advanced tools
sudo cp ../dev/tools/* /usr/local/bin/
sudo cp -r ../dev/profiles /usr/local/share/netperf/
```

### Method 2: Using Convenience Makefile

```bash
cd netperf_copilot/dev

# Build
make build

# Or optimized build
make optimized

# Run tests
make test
```

---

## Detailed Build Process

### Step 1: Clone Repository

```bash
# Latest release (recommended)
git clone https://github.com/thehevy/netperf_copilot.git
cd netperf_copilot
git checkout v3.0.0

# Or development branch
git clone https://github.com/thehevy/netperf_copilot.git
cd netperf_copilot
git checkout master
```

### Step 2: Generate Build System

If building from git (not needed for release tarballs):

```bash
./autogen.sh
```

### Step 3: Configure Build

#### Quick Configure (Recommended)

```bash
./dev/scripts/build.sh --type optimized
```

#### Manual Configure

```bash
./configure \
  --enable-omni \
  --enable-demo \
  --enable-histogram \
  --enable-intervals \
  --enable-burst \
  CFLAGS="-O3 -march=native -DMAXCPUS=2048"
```

#### Configuration Options

See [BUILD_CONFIGURATION.md](../dev/docs/BUILD_CONFIGURATION.html) for comprehensive guide.

Common options:

- `--enable-omni` - OMNI test framework (default: enabled)
- `--enable-demo` - Interval reporting (default: enabled)
- `--enable-histogram` - Per-operation timing (affects performance)
- `--enable-sctp` - SCTP protocol support
- `--enable-unixdomain` - Unix domain sockets
- `--enable-intervals` - Paced operations

### Step 4: Compile

```bash
make -j$(nproc)
```

### Step 5: Test (Optional)

```bash
# Basic test
cd build
./src/netserver -D &
./src/netperf -H localhost

# Run test suites
cd ../dev
make test
```

### Step 6: Install

```bash
cd build
sudo make install

# Default installation paths:
# - /usr/local/bin/netperf
# - /usr/local/bin/netserver
# - /usr/local/share/man/man1/netperf.1
```

---

## Advanced Tools Installation

After installing netperf binaries, install the Phase 3 advanced tools:

### Install to System Path

```bash
# Install all tools
sudo cp dev/tools/netperf-multi /usr/local/bin/
sudo cp dev/tools/netperf_stats.py /usr/local/bin/
sudo cp dev/tools/netperf-profile /usr/local/bin/
sudo cp dev/tools/netperf-orchestrate /usr/local/bin/
sudo cp dev/tools/netperf-monitor /usr/local/bin/
sudo cp dev/tools/netperf-template /usr/local/bin/

# Install test profiles
sudo mkdir -p /usr/local/share/netperf
sudo cp -r dev/profiles /usr/local/share/netperf/

# Make executable
sudo chmod +x /usr/local/bin/netperf-*
sudo chmod +x /usr/local/bin/netperf_stats.py
```

### Install to User Directory

```bash
# Install to ~/.local/bin (no sudo needed)
mkdir -p ~/.local/bin ~/.local/share/netperf

cp dev/tools/netperf-* ~/.local/bin/
cp dev/tools/netperf_stats.py ~/.local/bin/
cp -r dev/profiles ~/.local/share/netperf/

chmod +x ~/.local/bin/netperf-*
chmod +x ~/.local/bin/netperf_stats.py

# Add to PATH (if not already)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## Platform-Specific Notes

### Linux (Debian/Ubuntu)

```bash
# Install dependencies
sudo apt update
sudo apt install build-essential autoconf automake texinfo

# Python tools (optional)
sudo apt install python3 python3-pip
sudo apt install python3-jinja2 python3-numpy python3-matplotlib python3-yaml

# Build
./dev/scripts/build.sh --type optimized
cd build && sudo make install
```

### Linux (RHEL/CentOS/Fedora)

```bash
# Install dependencies
sudo yum groupinstall "Development Tools"
sudo yum install autoconf automake texinfo

# Python tools (optional)
sudo yum install python3 python3-pip
sudo yum install python3-jinja2 python3-numpy python3-matplotlib python3-pyyaml

# Build
./dev/scripts/build.sh --type optimized
cd build && sudo make install
```

### macOS

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install Homebrew (if not already)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install autoconf automake

# Python tools (optional)
brew install python3
pip3 install jinja2 numpy matplotlib pyyaml

# Build
./dev/scripts/build.sh --type optimized
cd build && sudo make install
```

### Solaris

```bash
# Install dependencies
pkg install developer/gcc developer/build/make developer/build/autoconf

# Build with proper CPU measurement
./configure --enable-cpuutil=kstat
make
sudo make install
```

---

## Verification

### Verify Installation

```bash
# Check netperf version
netperf -V

# Check netserver
netserver -V

# Verify tools
which netperf-multi
which netperf_stats.py
which netperf-profile

# List installed profiles
ls /usr/local/share/netperf/profiles/
# or
ls ~/.local/share/netperf/profiles/
```

### Run Basic Tests

```bash
# Start server
netserver -D

# Run basic test
netperf -H localhost -l 5

# Test advanced tools
netperf-profile -p baseline -H localhost --dry-run
echo "100 200 300" | tr ' ' '\n' | netperf_stats.py -
netperf-template --sample
```

---

## Build Types

### Release Build (Default)

Standard build with optimizations:

```bash
./dev/scripts/build.sh
# or
./dev/scripts/build.sh --type release
```

### Optimized Build (Recommended)

Maximum performance with aggressive optimizations:

```bash
./dev/scripts/build.sh --type optimized
```

Includes:

- `-O3` optimization level
- `-march=native` CPU-specific optimizations
- `MAXCPUS=2048` for large systems
- All features enabled

### Debug Build

For development and troubleshooting:

```bash
./dev/scripts/build.sh --type debug
```

Includes:

- `-g` debug symbols
- `-O0` no optimization
- Extra error checking

---

## Troubleshooting

### Configure Fails

**Problem**: `configure: error: C compiler cannot create executables`

**Solution**:

```bash
# Install build tools
sudo apt install build-essential  # Debian/Ubuntu
sudo yum groupinstall "Development Tools"  # RHEL/CentOS
```

### Missing Dependencies

**Problem**: `configure: error: makeinfo is missing`

**Solution**:

```bash
# Install texinfo
sudo apt install texinfo  # Debian/Ubuntu
sudo yum install texinfo  # RHEL/CentOS

# Or skip documentation
./configure --without-docs
```

### Python Tools Not Working

**Problem**: `ModuleNotFoundError: No module named 'jinja2'`

**Solution**:

```bash
# Install Python dependencies
pip3 install jinja2 numpy matplotlib pyyaml

# Or install system packages
sudo apt install python3-jinja2 python3-numpy  # Debian/Ubuntu
```

### Permission Denied

**Problem**: `Permission denied` when running tools

**Solution**:

```bash
# Make tools executable
chmod +x dev/tools/*

# Or after installation
sudo chmod +x /usr/local/bin/netperf-*
```

---

## Uninstallation

### Uninstall Binaries

```bash
cd build
sudo make uninstall

# Or manually
sudo rm /usr/local/bin/netperf
sudo rm /usr/local/bin/netserver
sudo rm /usr/local/share/man/man1/netperf.1
```

### Uninstall Advanced Tools

```bash
sudo rm /usr/local/bin/netperf-multi
sudo rm /usr/local/bin/netperf_stats.py
sudo rm /usr/local/bin/netperf-profile
sudo rm /usr/local/bin/netperf-orchestrate
sudo rm /usr/local/bin/netperf-monitor
sudo rm /usr/local/bin/netperf-template
sudo rm -rf /usr/local/share/netperf
```

---

## Next Steps

- [Quick Start Guide](quickstart.html) - Basic usage examples
- [OMNI Reference](../dev/docs/OMNI_REFERENCE.html) - Complete test framework guide
- [Output Formats](../dev/docs/OUTPUT_FORMATS.html) - Learn about different output options
- [Advanced Tools](../dev/docs/) - Phase 3 tools documentation

---

[← Back to Documentation](index.html)
