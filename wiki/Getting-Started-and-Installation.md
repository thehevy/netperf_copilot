# Getting Started and Installation

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-GETTING-STARTED-AND` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Getting Started and Installation under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


This guide covers building the modernized `netperf` C engine (`src/`), configuring compile-time options, installing
output presets, and setting up the Python CLI tool suite (`dev/tools/`).

---

## 1. System Requirements

### Build Dependencies

- **OS**: Linux (kernel 4.18+ recommended for `SO_ZEROCOPY` and `ETHTOOL_GLINKSETTINGS`), macOS, BSD, Solaris
- **Compiler**: GCC 4.8+ or Clang 3.5+
- **Autotools**: `autoconf`, `automake`, `make`
- **Python**: Python 3.8+ (all tools in `dev/tools/` work out-of-the-box with the Python standard library; `pyyaml` ,
  `jinja2` , `psutil` , and `paramiko` are optional enhancements)

### Recommended Linux Packages for 100G–800G Testing
```bash
# RHEL / CentOS / Rocky / Fedora
sudo dnf install -y gcc make autoconf automake numactl ethtool iproute procps-ng python3

# Ubuntu / Debian
sudo apt-get install -y build-essential autoconf automake numactl ethtool iproute2 procps python3
```

---

## 2. Building From Source

### Option A: Automated Build Script (Recommended)
The `dev/scripts/build.sh` wrapper supports `release` , `debug` , and `optimized` build profiles and builds out-of-tree
in `./build/` :

```bash
# Optimized build (-O3 -march=native, OMNI, demo intervals, burst, histogram)
./dev/scripts/build.sh --type optimized

# Standard release build
./dev/scripts/build.sh

# Debug build (-g -O0)
./dev/scripts/build.sh --type debug
```

### Option B: Convenience Developer Makefile
```bash
cd dev
make optimized   # Build optimized binaries in ../build/src/
make test        # Run functional loopback smoke tests
make test-formats # Verify KEYVAL, CSV, JSON, and HUMAN output modes
```

### Option C: Manual Autotools Build
```bash
./autogen.sh
mkdir -p build && cd build
../configure \
    --enable-omni \
    --enable-demo \
    --enable-burst \
    --enable-intervals \
    --enable-histogram \
    CFLAGS="-O3 -march=native"
make -j$(nproc)
```

---

## 3. Installing Binaries, Output Presets & Python Tools

```bash
# Install netperf, netserver, info/man pages, and output presets (/usr/local/share/netperf/output-presets/*.out)
cd build
sudo make install

# Install the Python CLI tools and modules to /usr/local/bin
cd ..
sudo cp dev/tools/netperf-* dev/tools/*.py dev/tools/netserver-manager /usr/local/bin/
sudo chmod +x /usr/local/bin/netperf-* /usr/local/bin/netserver-manager

# Install built-in YAML test profiles
sudo mkdir -p /usr/local/share/netperf/profiles
sudo cp dev/profiles/*.yaml /usr/local/share/netperf/profiles/
```

---

## 4. Verifying Your Installation

Run the self-contained unit & modernization test suite (requires no root privileges or external Python libraries):

```bash
python3 dev/tests/test_modernization.py
```

Expected output:
```text
Ran 18 tests in 0.07s
OK
```

To run live loopback verification on a Linux host:
```bash
cd dev
make test
make test-formats
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | wiki/Getting-Started-and<wbr>-Installation.md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet 200GbE`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-GETTING-STARTED-AND`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
