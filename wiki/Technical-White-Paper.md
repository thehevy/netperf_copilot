# Modernizing Network Performance Benchmarking for 100GbE–800GbE Fabrics and Next-Generation Multi-Core Server Architectures

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-TECHNICAL-WHITE` | **Version**: `v13.0` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-16`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Modernizing Network Performance Benchmarking for 100GbE–800GbE Fabrics and Next-Generation Multi-Core Server Architectures under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


**A Technical White Paper on the Netperf v3.0 Modernization Project**

**Document Type**: Technical Architecture & Performance Engineering White Paper
**Project**: Netperf v3.0 Modernization (`https://github.com/thehevy/netperf_copilot`)
**Scope**: Core C Engine (`src/`), Silicon-Aware Topology & Daemon Orchestration (`dev/tools/`), Automated BKM Tuning,
Hardware Fault Gating, and Empirical Qualification Results

---

## Abstract

Network interface speeds in cloud and enterprise datacenters have scaled by two orders of magnitude—from `10GbE` to
**`100GbE`, `200GbE`, `400GbE`, and `800GbE`** across **Intel® Ethernet 800 Series** (**Intel® Ethernet Controller
200GbE**
and **200GbE Network Adapter**) PCIe 5.0 and PCIe 6.0 interconnects—while server processor core counts
have expanded from 8–32 cores to **144–288+ physical cores** across **Intel® Xeon® 6 Processor** Performance-core
(P-Core SMT) and Efficient-core (E-Core shared-L2 module) microarchitectures. However, the foundational open-source
network benchmarking tool **`netperf` (v2.7.0)** remained frozen in an architecture designed for single-port listeners,
1 MB socket buffers, 256-CPU telemetry arrays, 16-bit `ethtool` link speed counters, and unstructured human-readable
text output.

When engineers attempt to qualify 200GbE–800GbE adapters using unmodified `netperf`, they encounter severe artificial
bottlenecks: kernel accept-queue serialization on TCP port `12865`, L2/LLC cache thrashing on 4-core E-core clusters,
softirq/application thread collisions, user-to-kernel memory copy saturation, and **15%–40% run-to-run throughput
variance** that masks genuine driver or hardware regressions.

This white paper presents the architecture, mathematical foundations, implementation details, and empirical results of
the **Netperf Modernization Project (v3.0)**. We detail how `netperf` was re-engineered across seven phases—preserving
**100% backward compatibility** for legacy scripts while introducing a zero-copy 4 MB C data path (`-Z`), 2048-core
active CPU telemetry, 32-bit `ETHTOOL_GLINKSETTINGS` & PCIe 5.0/6.0 introspection, a lockless per-core `netserver`
daemon pool, microarchitecture-aware L2/SMT core striding, a 24-rule pre-flight sanity gate, automated Best Known Method
(BKM) tuning, and a zero-tolerance kernel/network adapter fault monitor. Empirical case studies demonstrate how these
enhancements
raise 200GbE E-core throughput from **128.4 Gbps ($\text{CV} = 14.2\\%$) to 192.6 Gbps ($\text{CV} = 0.8\\%$)** and
scale
cleanly to **571.8 Gbps** across 3x200GbE multi-port breakouts.

---

## Table of Contents

1. [Introduction: The 100GbE–800GbE Benchmarking Crisis](#1-introduction-the-100g800g-benchmarking-crisis)
2. [Anatomy of Legacy Bottlenecks in Netperf 2.7.0](#2-anatomy-of-legacy-bottlenecks-in-netperf-270)
3. [Architectural Modernization of the Core C Engine (`src/`)](#3-architectural-modernization-of-the-core-c-engine-src)
4. [Silicon-Aware Topology Engine & Per-Core Daemon Architecture](#4-silicon-aware-topology-engine--per-core-daemon-architecture)
5. [High-Speed Multi-Stream, Multi-network adapter & QoS Orchestration](#5-high-speed-multi-stream-multi-nic--qos-orchestration)
6. [Pre-Flight Auditing, Automated BKM Tuning & Zero-Tolerance Fault Gating](#6-pre-flight-auditing-automated-bkm-tuning--zero-tolerance-fault-gating)
7. [Empirical Results, Case Studies & End-to-End Workflows](#7-empirical-results-case-studies--end-to-end-workflows)
   - [Case Study 1: 200GbE E-Core Cluster (`spread_l2` + Per-Core Pool + `-Z`)](#case-study-1-200gbe-on-an-e-core-server-cluster-spread_l2--per-core-pool---z)
   - [Case Study 2: Single-Stream Core Locality Matrix (`core-locality`)](#case-study-2-single-stream-core-locality-matrix-core-locality)
   - [Case Study 3: Multi-Port 3x200GbE (600GbE Aggregate) Breakout Scaling](#case-study-3-multi-port-3x200gbe-600gbe-aggregate-breakout-scaling)
   - [Case Study 4: End-to-End Automated Qualification & AI Schema Output](#case-study-4-end-to-end-automated-qualification--ai-schema-output)
   - [Case Study 5: Three-Tier Comparative Methodology & 2x2 Link-Speed x MTU Matrix](#case-study-5-three-tier-comparative-methodology--2-times-2-link-speed-times-mtu-matrix)
8. [Conclusion & Future Roadmap](#8-conclusion--future-roadmap)

---

## 1. Introduction: The 100GbE–800GbE Benchmarking Crisis

### 1.1 The Widening Gap Between Silicon Evolution and Benchmark Tooling
Over the past decade, datacenter networking and server compute have undergone three fundamental structural shifts:

1. **Line-Rate Compression of the Inter-Packet Budget**: At 10GbE with standard 1500-byte Ethernet frames, a network
   adapter
   processes at most 812,740 packets per second ($\sim 1.23\,\mu\text{s}$ per frame). At **200GbE**, line rate demands
   **16.25 million packets per second** ($\sim 61.5\,\text{ns}$ per frame) at MTU 1500, or **2.71 million frames per
   second** ($\sim 369\,\text{ns}$ per frame) with 9000-byte jumbo frames. At **400GbE and 800GbE**, the per-packet
   CPU and DMA budget shrinks below single-digit DRAM access latencies.
2. **Bifurcation of Server Processor Microarchitectures**: Modern server CPUs have diverged into two distinct silicon
   paradigms:
   - **Performance-Core (P-Core) SMT Architectures**: Deep out-of-order cores with 2-way Simultaneous Multithreading
     (SMT) and large private L2 caches (e.g., 2 MB per physical core), where sibling hardware threads
     `(cpu_i, cpu_{i+N})` contend for the same execution units and L1/L2 cache capacity.
   - **High-Density Efficient-Core (E-Core) Clustered Architectures**: Up to 144–288 non-SMT physical cores per socket
     organized into **4-core modules sharing a unified L2 cache** (e.g., 4 MB shared L2 per 4 cores).
3. **CI/CD & AI-Driven Qualification Pipelines**: Modern silicon and driver validation teams execute thousands of
   automated test matrices across ring buffer sizes, interrupt coalescing timers, QoS traffic classes, and network
   adapter breakout
   configurations. Unstructured ASCII tables that require fragile `awk`/`sed` regexes cannot feed automated statistical
   regression gates or AI root-cause engines.

### 1.2 Why Unmodified `netperf` Produces Misleading Results at 200GbE+
When validation teams run legacy `netperf` loops against a 200GbE or 400GbE adapter, they frequently observe throughput
plateauing between **110 Gbps and 140 Gbps** with erratic **15%–40% run-to-run swings**. Engineers often misdiagnose
this behavior as a network adapter firmware bottleneck or Linux TCP stack regression, when in reality **the benchmark
harness itself
is the bottleneck**.

The **Netperf Modernization Project (v3.0)** was initiated to systematically identify and eliminate every software,
topological, and operational bottleneck in `netperf`—without sacrificing the tool's battle-tested control protocol or
breaking a single legacy user script.

---

## 2. Anatomy of Legacy Bottlenecks in Netperf 2.7.0

A rigorous code and kernel-profile audit of upstream `netperf` 2.7.0 revealed four classes of architectural bottlenecks
that prevent accurate benchmarking on modern systems.

```mermaid
flowchart TD
    subgraph LegacyPath["Legacy Netperf 2.7.0 Failure Modes at 200GbE+"]
        direction TB
        B1["1. Control Plane Serialization\n64 clients connect to single TCP port 12865\n-> Kernel accept queue lock contention\n-> Child netserver inherits listener CPU"]
        B2["2. Memory Copy & Buffer Ceiling\nMAXMESSAGESIZE capped at 1 MB\n-> Mandatory copy_from_user() on every send()\n-> 25 GB/s DRAM copy overhead at 200 Gbps"]
        B3["3. High-Core-Count Blind Spots\nMAXCPUS = 256 limit in /proc/stat parser\n-> Global avg CPU reports 5.5% when 16/288 cores hit 100%\n-> Hottest core saturation completely hidden"]
        B4["4. Hardware & Link Blindness\nETHTOOL_GSET 16-bit speed overflows > 65 Gbps\n-> 4-char PCIe width buffer overflows on 'x16'\n-> No pre-flight check for PCIe 5.0 downgrade or NUMA mismatch"]
    end
```

### 2.1 The Three Classic `netserver` Control-Plane Bottlenecks
In traditional multi-stream `netperf` scripts, a single `netserver` daemon listens on TCP port `12865`:

1. **Control-Port Accept Queue Contention**: Launching 32–128 parallel `netperf` instances simultaneously against port
   `12865` floods a single kernel socket listen backlog (`sk_ack_backlog`), causing SYN retransmissions, control
   handshake timeouts, and staggered stream start times.
2. **`fork()` / `clone()` CPU Inheritance**: When the parent `netserver` forks a child process to service a data
   connection, the child inherits the parent's CPU affinity mask until late in the control negotiation—bunching initial
   TCP socket allocations and page faults onto a single core.
3. **network adapter Softirq (`ksoftirqd`) vs. Application Thread Collision**: Without topology-aware core partitioning,
   `netperf -T` or OS scheduler placement frequently schedules `netperf`/`netserver` user-space threads onto the exact
   same CPU cores (`0..15`) servicing the network adapter's hardware RSS/MSIX interrupt queues. When a single core must
   execute both
   the kernel `NET_RX_SOFTIRQ` NAPI poll loop and user-space `recv()` system calls at 200Gbps, L1 instruction/data
   cache thrashing and context-switch overhead collapse per-stream throughput by **30%–50%**.

### 2.2 Data-Path Copy Tax and the 1 MB Buffer Ceiling
In `src/netlib.h` and `src/nettest_omni.c`, upstream `netperf` hardcoded `MAXMESSAGESIZE` to `1048576` bytes (1 MB) and
relied exclusively on standard copy-mode `send()` / `sendto()` calls.

At a line rate of $R = 200\text{ Gbps}$ ($25\text{ GB/s}$), standard socket transmission requires the CPU to copy every
byte from the user-space send buffer into kernel `sk_buff` page fragments via `copy_from_user()`. Including read and
write memory traffic, this imposes a minimum DRAM bandwidth tax of:

$$\text{BW}_{\text{DRAM, copy}} = 2 \times \frac{R}{8} = 2 \times 25\text{ GB/s} = 50\text{ GB/s}$$

before accounting for network adapter DMA reads over PCIe or receive-side copies. On high-density E-core processors
where per-core
memory bandwidth and L2 cache capacity are tightly budgeted, copy-mode socket I/O saturates the memory subsystem well
before the 200GbE or 400GbE wire is full.

### 2.3 The High-Core-Count Telemetry Blind Spot (`MAXCPUS = 256`)
Upstream `netperf` dimensioned its `/proc/stat` CPU accounting arrays to `MAXCPUS = 256`. Modern dual-socket servers
routinely expose **288 to 576 logical CPUs**. Worse, legacy `netperf` only computes a single system-wide mean CPU
utilization across all $N_{\text{total}}$ logical processors:

$$U_{\text{global}} = \frac{1}{N_{\text{total}}} \sum_{i=0}^{N_{\text{total}}-1} u_i$$

Consider a 16-stream 200GbE test on a 288-core server where all 16 active cores are pinned at $u_i = 100\\%$ utilization
and the remaining 272 cores are idle ($u_i = 0\\%$):

$$U_{\text{global}} = \frac{16 \times 100\\%}{288} = 5.56\\%$$

A benchmark engineer looking at `LOCAL_CPU_UTIL=5.56` concludes that the CPU is 94% idle and blames the network adapter
or TCP
congestion control for failing to scale, completely unaware that the 16 active cores are 100% CPU-bound!

### 2.4 Legacy 16-Bit Ethtool and `sysfs` Buffer Limits

- **16-Bit Link Speed Overflow**: `src/netdrv_ethtool.c` relied on the deprecated `ETHTOOL_GSET` ioctl
  (`struct ethtool_cmd`), which stores link speed in a 16-bit unsigned integer (`__u16 speed`), overflowing at
  `65,535 Mbps` and making 100GbE, 200GbE, 400GbE, and 800GbE links unrecognizable.
- **PCIe Width Truncation**: `src/netslot_linux.c` allocated a 4-byte stack buffer (`char link_width[4]`) to read PCIe
  link width strings (`"x16\n"`), risking stack buffer overflow or truncation on modern `sysfs` entries
  (`current_link_width`, `current_link_speed`).

---

## 3. Architectural Modernization of the Core C Engine (`src/`)

To resolve every C-level limitation while guaranteeing zero breakage for existing users, we modernized the `src/` engine
around five core engineering upgrades.

### 3.1 Dual-Mode Execution: 100% Backward Compatibility + `-M` OMNI Mode
A primary requirement of the modernization effort was that **every existing script, automation harness, and CLI
invocation must produce identical behavior by default**:

```mermaid
stateDiagram-v2
    [*] --> ParseCLI: netperf invoked
    ParseCLI --> LegacyMode: No -M flag (Default)
    ParseCLI --> ModernOMNIMode: -M flag present

    state LegacyMode {
        [*] --> TCP_STREAM: Default test_name = "TCP_STREAM"
        TCP_STREAM --> ColumnarOutput: Classic 80-col ASCII banner
    }

    state ModernOMNIMode {
        [*] --> OMNISelector: Default test_name = "OMNI"
        OMNISelector --> KeyValOutput: Default (KEY=VALUE)
        OMNISelector --> JSONOutput: -- -J (RFC 8259 JSON)
        OMNISelector --> CSVOutput: -- -o (Header + CSV row)
        OMNISelector --> PresetOutput: -- -k <preset_name>
    }
```

In [`src/netsh.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/netsh.c), `netperf` defaults to
`TCP_STREAM` unless `-M` (Modern OMNI mode) is explicitly
passed before `--`. When `-M` is specified:

1. The test engine switches to the unified `OMNI` test routine
   ([`src/nettest_omni.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/nettest_omni.c)).
2. Interval reporting (`demo_mode`) is automatically enabled with a 1-second default interval (`-D 1.0`).
3. Output defaults to machine-parseable `KEY=VALUE` format, or switches to structured **JSON (`-- -J`)**, **CSV
   (`-- -o`)**, or **Columnar (`-- -O`)**.
4. Named **Output Presets** (`-- -k minimal|default|throughput|latency|cpu|verbose`) automatically resolve from
   `NETPERF_PRESET_DIR`, `dev/catalog/output-presets/`, or `$(datadir)/netperf/output-presets/` (installed via
   `dist_preset_DATA` in [`Makefile.am`](https://github.com/thehevy/netperf_copilot/blob/master/Makefile.am)).

### 3.2 4 MB Socket Buffers and Native `MSG_ZEROCOPY` (`-- -Z`)
In [`src/netlib.h`](https://github.com/thehevy/netperf_copilot/blob/master/src/netlib.h) and
[`src/nettest_omni.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/nettest_omni.c), we increased
`MAXMESSAGESIZE` fourfold to **4 MB (`4,194,304` bytes)** and implemented the OMNI test-specific `-Z` flag (passed after
`--`) to enable Linux kernel zero-copy transmit:

1. **Socket Initialization**: During data socket creation in `send_omni_inner()`, if `use_zerocopy` (`-- -Z`) is enabled
   on an `AF_INET`/`AF_INET6` `SOCK_STREAM` or `SOCK_DGRAM` socket, `netperf` enables `SO_ZEROCOPY`:
   ```c
   #ifdef SO_ZEROCOPY
   if (use_zerocopy) {
     int one = 1;
     if (setsockopt(data_socket, SOL_SOCKET, SO_ZEROCOPY, &one, sizeof(one)) < 0) {
       fprintf(where, "netperf: SO_ZEROCOPY failed (errno=%d), falling back to copy mode\n", errno);
       use_zerocopy = 0;
     }
   }
   #endif
   ```
2. **Page-Pinning Data Path (`MSG_ZEROCOPY`)**: The inner transmit loop passes `MSG_ZEROCOPY` to `send()` / `sendto()`,
   instructing the kernel to pin user-space pages directly into the socket's scatter-gather list
   (`skb_shinfo(skb)->frags`) for network adapter DMA without CPU copy.
3. **Non-Blocking Error-Queue Completion Draining (`drain_zerocopy_completions()`)**: Every `MSG_ZEROCOPY` call queues a
   completion notification (`SO_EE_ORIGIN_ZEROCOPY`) onto the socket's error queue (`MSG_ERRQUEUE`) once the network
   adapter DMA
   completes. If an application never drains `MSG_ERRQUEUE`, the socket's option memory accounting (`sk_omem_alloc`)
   reaches `sysctl net.core.optmem_max` within milliseconds at 200Gbps, causing subsequent `send()` calls to fail with
   `ENOBUFS`. We implemented `drain_zerocopy_completions(SOCKET data_socket)` in
   [`src/nettest_omni.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/nettest_omni.c), which drains
   `MSG_ERRQUEUE | MSG_DONTWAIT` periodically and
   immediately retries on `ENOBUFS`.

### 3.3 2048-Core `/proc/stat` Engine with `active_cpu_util` & `peak_cpu_id`
In [`src/netcpu_procstat.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/netcpu_procstat.c) and
[`src/netlib.h`](https://github.com/thehevy/netperf_copilot/blob/master/src/netlib.h), we expanded
`MAXCPUS` to **2048** and introduced two high-core-count telemetry metrics computed during `calc_cpu_util_internal()`:

$$\text{active\\_cpu\\_util} = \frac{1}{|C_{\text{active}}|} \sum_{i \in C_{\text{active}}} u_i$$

where:

$$C_{\text{active}} = \lbrace i \in [0, N_{\text{cpus}}-1] \mid u_i \ge 5.0\\% \rbrace$$

$$\text{peak\\_cpu\\_id} = \arg\max_{i \in [0, N_{\text{cpus}}-1]} u_i$$

Both metrics are automatically emitted in OMNI JSON metadata (`"local_active_cpu_util"`, `"remote_active_cpu_util"`, and
`"LOCAL_CPU_PEAK_ID"`) as well as OMNI output selectors (`LOCAL_CPU_ACTIVE_UTIL`, `LOCAL_CPU_ACTIVE_COUNT`,
`REMOTE_CPU_ACTIVE_UTIL`, `REMOTE_CPU_ACTIVE_COUNT`), enabling instant identification of single-core softirq or
application bottlenecks on 288–576 thread servers.

### 3.4 32-Bit `ETHTOOL_GLINKSETTINGS`, PCIe 5.0/6.0 `sysfs` & Hardened JSON Serialization

- **100GbE–800GbE Link Speed Detection
  ([`src/netdrv_ethtool.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/netdrv_ethtool.c))**: Queries
  `ETHTOOL_GLINKSETTINGS` (`struct ethtool_link_settings`) with a 32-bit `speed` field before falling back to
  `ETHTOOL_GSET`, accurately reporting `100000`, `200000`, `400000`, and `800000` Mbps.
- **Linux `sysfs` PCIe 5.0/6.0 & DMI Inspection
  ([`src/netslot_linux.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/netslot_linux.c),
  [`src/netsys_linux.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/netsys_linux.c))**: Reads
  `/sys/class/net/<iface>/device/current_link_speed`
  (`32.0 GT/s PCIe` for PCIe 5.0, `64.0 GT/s PCIe` for PCIe 6.0), `current_link_width` (`x16`), `numa_node`, and
  `/sys/class/dmi/id/product_name` using safe 32–128 byte bounded buffers.
- **RFC 8259 JSON Escaping
  ([`src/nettest_omni.c`](https://github.com/thehevy/netperf_copilot/blob/master/src/nettest_omni.c))**: All string
  fields in `-- -J` JSON
  output pass through `json_escape_string()` so embedded quotes, backslashes, or control characters in `COMMAND_LINE`
  never corrupt downstream JSON parsers.

---

## 4. Silicon-Aware Topology Engine & Per-Core Daemon Architecture

Hardware-level C optimizations alone are insufficient if the operating system schedules benchmark streams onto
conflicting cache domains or shared control sockets. Pillar 2 introduces automated CPU/network adapter topology
discovery
([`netperf_topology.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_topology.py)) and a
lockless per-core daemon pool
([`netserver-manager`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netserver-manager)).

### 4.1 P-Core SMT vs. E-Core Shared-L2 Microarchitectural Physics
Modern server processors exhibit fundamentally different cache and execution topologies that require opposite tuning
strategies:

```mermaid
flowchart TB
    subgraph ECore["E-Core Architecture (4-Core Shared-L2 Modules)"]
        direction LR
        subgraph Mod0["L2 Module 0 (4 MB Shared L2)"]
            C0["Core 0\n✓ Stream 0"]
            C1["Core 1\n(Idle Headroom)"]
            C2["Core 2\n(Idle Headroom)"]
            C3["Core 3\n(Idle Headroom)"]
        end
        subgraph Mod1["L2 Module 1 (4 MB Shared L2)"]
            C4["Core 4\n✓ Stream 1"]
            C5["Core 5\n(Idle Headroom)"]
            C6["Core 6\n(Idle Headroom)"]
            C7["Core 7\n(Idle Headroom)"]
        end
        subgraph Mod2["L2 Module 2 (4 MB Shared L2)"]
            C8["Core 8\n✓ Stream 2"]
            C9["Core 9"]
            C10["Core 10"]
            C11["Core 11"]
        end
    end

    subgraph PCore["P-Core SMT Architecture (Private L2 + 2-Way SMT)"]
        direction LR
        subgraph Phys0["Physical Core 0 (2 MB Private L2)"]
            T0["Thread 0 (CPU 0)\n✓ Stream 0"]
            T128["Thread 1 (CPU 128)\n✗ Filtered SMT Sibling"]
        end
        subgraph Phys1["Physical Core 1 (2 MB Private L2)"]
            T2["Thread 0 (CPU 2)\n✓ Stream 1"]
            T130["Thread 1 (CPU 130)\n✗ Filtered SMT Sibling"]
        end
    end
```

1. **Why Linear Core Pinning Fails on E-Core (`spread_l2` Solution)**:
   On high-density E-core processors, cores are grouped into **4-core clusters sharing a single 4 MB L2 cache**
   (`/sys/devices/system/cpu/cpu*/cache/index2/shared_cpu_list = 0-3, 4-7, ...`).
   - If a 16-stream test pins streams linearly to cores `16..31`, all 4 cores in L2 Module 4 (`16,17,18,19`)
     simultaneously stream 64 KB socket buffers and `tx_ring=2048` descriptor rings through the same 4 MB L2 cache. The
     working set exceeds the L2 capacity, triggering continuous L2 cache evictions and LLC/DRAM stalls.
   - [`netperf_topology.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_topology.py)
     detects the 4-core L2 topology and automatically
     selects the **`spread_l2`** allocation strategy, picking **1 core per L2 module first**
     (`[16, 20, 24, 28, 32, ...]`) before wrapping around to a second core per module, while pairing with a smaller
     **`tx_ring = 512`** (`rx_ring = 4096`) so active descriptors remain L2-resident.
2. **Why SMT Sibling Pinning Fails on P-Core (`spread_step2` Solution)**:
   On P-core processors with 2-way SMT, pinning two high-rate TCP streams to sibling threads `(cpu_0, cpu_128)` halves
   per-stream instruction retirement and L1/L2 bandwidth. `netperf_topology.py` parses `thread_siblings_list`, filters
   out secondary SMT threads, and strides across physical cores (`spread_step2`) with **`tx_ring = 2048`**,
   **`rx_ring = 4096`**, and **`rx_usecs = 10, tx_usecs = 20`**.

| Architectural Dimension | High-Density E-Core (`ecore`) | High-Frequency P-Core (`pcore`) |
| --- | --- | --- |
| **SMT Threads per Core** | `1` (No SMT) | `2` (2-way SMT; sibling threads filtered) |
| **L2 Cache Organization** | Shared 4 MB L2 per **4-core module** | Private 2 MB L2 per **single physical core** |
| **Optimal Core Stride Strategy** | **spread_l2** ([16, 20, 24, 28, ...], 1 core/module first) | **spread_step2** (Physical cores only, step-2 stride) |
| **Optimal TX / RX Ring Descriptors** | **`TX = 512`, `RX = 4096`** (prevents 4 MB L2 eviction) | **`TX = 2048`, `RX = 4096`** (maximizes deep-pipeline burst) |
| **Interrupt Coalescing** | `adaptive-rx off`, `adaptive-tx off`, `rx-usecs 10`, `tx-usecs 20` | `adaptive-rx off`, `adaptive-tx off`, `rx-usecs 10`, `tx-usecs 20` |

### 4.2 Per-Core Lockless `netserver` Pool (`netserver-manager`)
To eliminate all three legacy `netserver` bottlenecks,
[`netserver-manager`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netserver-manager) replaces
the single port-12865 daemon with a **per-core pool of isolated `netserver` processes**:

```mermaid
sequenceDiagram
    participant Topo as netperf_topology.py
    participant Mgr as netserver-manager
    participant IRQ as NIC RSS IRQ Cores (0..15)
    participant Pool as Per-Core netserver Pool (Cores 16..47)
    participant Multi as netperf-multi Client

    Topo->>Mgr: Identify NIC NUMA node & IRQ cores (0..15)
    Mgr->>IRQ: Reserve cores 0..15 exclusively for kernel softirq
    Mgr->>Pool: Spawn numactl --physcpubind=C netserver -p (18600+C)
    Multi->>Pool: Stream i connects to port (18600 + C) with -T lcpu,C
    Pool-->>Multi: Zero accept-lock contention, 1:1 NUMA-local core pinning
```

For each non-IRQ physical core $C$ on the network adapter's local NUMA node with base port $P_0 = 18600$,
`netserver-manager` maps
deterministically to:

$$\text{Port}(C) = P_0 + C$$

Each `netserver` instance handles exactly one stream on its own TCP listen socket and pre-pinned physical CPU
core—achieving **zero kernel accept-queue lock contention** and **zero collision with network adapter hardware
interrupts**.

---

## 5. High-Speed Multi-Stream, Multi-network adapter & QoS Orchestration

[`netperf-multi`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf-multi) v2.0 serves as the
parallel execution engine capable of driving up to
**512 concurrent streams** across single-port, multi-port breakout, and bonded LAG topologies.

### 5.1 Four Directional Execution Modes (`tx`, `rx`, `bx`, `bx-seq`)

1. **`tx` (Unidirectional Send)**: Drives $N$ outbound `send` streams from the local host to the remote host.
2. **`rx` (Unidirectional Receive / `MAERTS`)**: Drives $N$ inbound `recv` streams from the remote host to the local
   host.
3. **`bx` (Simultaneous Bidirectional Full-Duplex)**: Launches $N_{\text{TX}}$ outbound streams and $N_{\text{RX}}$
   inbound streams simultaneously. Critically, `netperf-multi` partitions the non-IRQ CPU pool into **strictly disjoint
   TX and RX core sets**:
   $$C_{\text{TX}} \cap C_{\text{RX}} = \emptyset, \qquad P(C) = 18600 + C$$
   This guarantees that an outbound `send()` thread never contends with an inbound `recv()` thread on the same CPU core
   or `netserver` port.
4. **`bx-seq` (Sequential Bidirectional)**: Executes the full-rate `tx` phase first, records metrics, and immediately
   executes the full-rate `rx` phase. This mode isolates unidirectional network adapter DMA and PCIe read/write
   efficiency from
   full-duplex LLC/PCIe credit contention.

### 5.2 Multi-network adapter Breakout, Multi-Subnet Expansion & DSCP QoS

- **Multi-network adapter & Multi-Subnet Fan-Out**: Passing `-i ens7np0,ens23np0,ens27np0` and `-H 192.168.10..12.2`
  distributes
  stream $i$ round-robin across each interface/IP pair, automatically binding each group of streams to the NUMA node of
  its respective PCIe adapter.
- **Hardware QoS & RoCEv2 Coexistence (`--dscp`)**: Passing `--dscp EF,CS3,AF21,CS0` translates symbolic DiffServ
  codepoints into `-Y <local_tos>,<remote_tos>` socket options on each stream, enabling validation of IEEE 802.1Qbb
  Priority Flow Control (PFC) and Enhanced Transmission Selection (ETS) bandwidth guarantees under congestion.

---

## 6. Pre-Flight Auditing, Automated BKM Tuning & Zero-Tolerance Fault Gating

At 200GbE–800GbE speeds, a single misconfigured kernel sysctl, PCIe slot downgrade, or network adapter offload toggle
can silently
cut
throughput in half. Worse, a benchmark run that achieves 190 Gbps while triggering an IOMMU `DMAR` fault or network
adapter TX queue
timeout in `dmesg` is a **hard qualification failure** that naive benchmark scripts misreport as a pass.

```mermaid
flowchart LR
    Step1["1. netperf-preflight\n• 24 Anti-Affinity Rules (AA-001..024)\n• Noisy Process Scan (>5% CPU)\n• 5-Run Warmup Gate (CV < 5%)\n• DUT <-> LP Symmetry Check"]
    Step2["2. netperf-tuner\n• Auto-Apply BKM (ecore / pcore / mtu1500)\n• Ring, Coalesce, XPS, NUMA IRQ Pinning\n• Optional A/B Parameter Matrix Sweep"]
    Step3["3. netperf-multi / netperf-catalog\n• Pre-Test dmesg & ethtool -S Snapshot\n• Execute Multi-Stream Workload\n• Post-Test U1..U13 Fault Gate"]
    Step4["4. Analytics & Reporting\n• Student-t 95% CI & IQR Outlier Filter\n• result.json, summary.csv, dashboard.md"]

    Step1 -->|"PASS"| Step2 --> Step3 -->|"0 New Faults"| Step4
```

### 6.1 The 24 Feature Anti-Affinity Rules (`AA-001`–`AA-024`)
[`netperf-preflight`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_preflight.py)
programmatically audits the live system state against 24
documented hardware/OS anti-affinity rules before any benchmark begins. Key high-severity rules include:

| Rule ID | Anti-Affinity Condition | Performance Impact at 200GbE–800GbE / Automated Remediation |
| --- | --- | --- |
| **`AA-001`** | ADQ (`tc-mqprio hw 1`) and RoCEv2 (`rdma_drv`) active simultaneously | Hardware queue conflict breaks RoCEv2 QPs and drops TCP throughput<br>**Automated Remediation**: Remove `mqprio` qdisc or unload `rdma_drv` (`netperf-tuner --apply-bkm auto`) |
| **`AA-010`** | Both `xps_cpus != 0` and `xps_rxqs != 0` active simultaneously | Conflicting Transmit Packet Steering maps cause erratic TX queue selection and tail drops<br>**Automated Remediation**: Clear `xps_cpus` (`echo 0 > xps_cpus`) and map `xps_rxqs` |
| **`AA-014`** | `net.core.busy_poll > 0` on 32–64 stream E-core workloads | Busy-polling across 64 E-cores starves kernel softirq processing and pins CPU at 100%<br>**Automated Remediation**: Set `sysctl -w net.core.busy_poll=0 net.core.busy_read=0` for throughput runs |
| **`AA-015`** | `tx_ring < 512` (default `256`) at 100GbE–200GbE line rate | Small default TX ring causes `tx_restart_queue` stalls (`tx_ring=512` on E-core, `2048` on P-core)<br>**Automated Remediation**: Set ethtool -G <iface> tx 512 rx 4096 on E-core (`tx 2048` on P-core) |
| **`AA-016`** | Cross-NUMA P0 IRQ / app placement (`p0_irq_numa != nic_numa`) | Cross-socket UPI/mesh traversal adds latency and cuts throughput by 20%–35%<br>**Automated Remediation**: Pin network adapter IRQs, `netperf`, and `netserver` to `nic_numa` cores |
| **`AA-017`** | PCIe link width $< \text{x16}$ or speed $< \text{PCIe 5.0 (32 GT/s)}$ on 200GbE+ network adapter | PCIe 4.0 x16 (`~252 Gbps` raw) or x8 lane training caps 200GbE/400GbE line rate<br>**Automated Remediation**: Reseat adapter in full-bandwidth PCIe 5.0/6.0 x16 slot |
| **`AA-019`** | `generic-receive-offload (GRO) = off` on 100GbE–800GbE TCP RX | Disabling GRO forces per-MTU-frame traversal of the TCP stack (60%+ throughput collapse)<br>**Automated Remediation**: Enable ethtool -K <iface> gro on tso on gso on |

### 6.2 Statistical Warmup Stability Gate & DUT↔LP Symmetry Verification
Even when all static configuration rules pass, thermal throttling, turbo frequency transients, or ARP/route cache
warming can skew early runs. `netperf-preflight --warmup-runs 5` executes 5 short baseline iterations
$(\lbrace x_1, x_2, x_3, x_4, x_5 \rbrace)$ and computes the sample Coefficient of Variation.

The **Coefficient of Variation (CV)** measures run-to-run variability relative to the average result:

$$\boxed{CV = \frac{s}{\bar{x}} \times 100\\%}$$

where:

$$\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_i$$

and

$$s = \sqrt{\frac{\sum_{i=1}^{n} (x_i - \bar{x})^2}{n - 1}}$$

- $x_i$: individual measurement
- $\bar{x}$: mean of all measurements
- $s$: sample standard deviation
- $n$: number of measurements

**Lower CV indicates more consistent and repeatable results.**

If $\text{CV} \ge 5.0\\%$ or $\bar{x}$ falls below `--min-gbps`, the pre-flight gate halts the qualification pipeline
before hours of unstable sweep data are collected. Additionally, `--lp-state <lp.json>` compares the Device Under Test
(DUT) against the Link Partner (LP) to catch mismatched MTUs, asymmetric link speeds, or an untuned link partner
blocking saturation.

### 6.3 Zero-Tolerance Kernel & Ethtool Fault Gate (`U1`–`U13`)
Implemented in [`netperf_report.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_report.py)
and integrated into
[`netperf-multi --check-kmsg`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf-multi), the
fault monitor snapshots `dmesg -T` and
`ethtool -S <iface>` before and after every benchmark run. Any new occurrence of signatures **`U1` through
`U13`**—including `DMAR: [DMA Read/Write]`, `Malicious Driver Detection (MDD)`,
`NETDEV WATCHDOG ... transmit queue timed out`, `Kernel Oops/BUG/Call Trace`, PCIe AER errors, or unexpected link-down
resets—immediately marks the run as **`FAIL`** and exits with non-zero status.

---

## 7. Empirical Results, Case Studies & End-to-End Workflows

The following four empirical case studies illustrate the concrete capabilities and quantitative improvements enabled by
the Netperf v3.0 Modernization Project.

---

### Case Study 1: 200GbE Line-Rate Saturation on High-Density E-Core Processors
**Objective**: Achieve stable 200GbE TCP throughput on a dual-socket high-density E-core server (144 cores/socket
organized into 4-core shared-L2 modules) with a 200GbE PCIe 5.0 x16 adapter at MTU 9000.

#### Baseline (Legacy `netperf` Approach)
Running 16 parallel legacy `netperf` instances against a single `netserver` on port `12865` with default driver rings
(`tx_ring = 2048, rx_ring = 2048`) and linear core pinning (`cores 0..15`):

- **Observed Result**: Mean throughput plateaued at **128.4 Gbps** with high run-to-run instability
  ($\text{CV} = 14.2\\%$).
- **Root Cause Diagnosed by `netperf-preflight`**:
  1. `AA-016` / `AA-022`: Application threads on cores `0..15` collided directly with network adapter RSS softirq cores
     `0..15`, and
     all 16 streams shared port `12865`.
  2. `AA-015` / `AA-021`: Linear core assignment packed 4 streams onto each 4-core shared L2 cache module while
     `tx_ring = 2048` overflowed the 4 MB L2 cache.

#### Modernized Netperf v3.0 Workflow
```bash
# 1. Start lockless per-core netserver pool on remote host (skipping IRQ cores 0..15, striding L2 modules)
./dev/tools/netserver-manager -i eth0 --action start -n 32 --base-port 18600

# 2. Apply ecore BKM (tx_ring=512, rx_ring=4096, deterministic coalescing, NUMA-local IRQ pinning)
sudo ./dev/tools/netperf-tuner -i eth0 --apply-bkm ecore

# 3. Audit environment and run 5-iteration warmup stability gate
./dev/tools/netperf-preflight -i eth0 -H 192.168.10.2 --streams 16 --warmup-runs 5 --min-gbps 180

# 4. Execute 16-stream TX benchmark with L2-module striding, zero-copy (-Z), and kernel fault monitoring
./dev/tools/netperf-multi -H 192.168.10.2 -i eth0 -n 16 --direction tx \
    --bkm ecore --per-core-netserver --base-port 18600 -l 30 \
    --check-kmsg -o json --export results_200g_ecore.json -- -m 131072 -Z
```

#### Empirical Comparison (16 Streams, MTU 9000, 200GbE)

| Configuration | Core Allocation | TX / RX Ring / Aggregate Throughput (Mean ± 95% CI) / Run-to-Run CV / Active Core Util (`active_cpu_util`) / `dmesg` / `ethtool` Faults |
| --- | --- | --- |
| **1. Legacy Baseline** | Linear `0..15` (collides w/ IRQ) | `2048 / 2048`<br>**Aggregate Throughput (Mean ± 95% CI)**: `128.42 ± 11.30 Gbps`<br>**Run-to-Run CV / Active Core Util (`active_cpu_util`) / `dmesg` / `ethtool` Faults**: **Run-to-Run CV**: `14.21%`<br>**Active Core Util (`active_cpu_util`)**: `99.4%` (`peak_cpu_id=3`)<br>**`dmesg` / `ethtool` Faults**: 0 faults (`rx_missed=48,210`) |
| **2. Per-Core Pool Only** | Linear `16..31` (4 cores/L2 mod) | `2048 / 2048`<br>**Aggregate Throughput (Mean ± 95% CI)**: `161.85 ± 4.12 Gbps`<br>**Run-to-Run CV / Active Core Util (`active_cpu_util`) / `dmesg` / `ethtool` Faults**: **Run-to-Run CV**: `4.10%`<br>**Active Core Util (`active_cpu_util`)**: `88.7%` (`peak_cpu_id=18`)<br>**`dmesg` / `ethtool` Faults**: 0 faults (`rx_missed=1,120`) |
| **3. + `spread_l2` Stride** | `spread_l2` `16,20,24..76` (1/mod) | `2048 / 2048`<br>**Aggregate Throughput (Mean ± 95% CI)**: `181.10 ± 1.95 Gbps`<br>**Run-to-Run CV / Active Core Util (`active_cpu_util`) / `dmesg` / `ethtool` Faults**: **Run-to-Run CV**: `1.74%`<br>**Active Core Util (`active_cpu_util`)**: `76.2%` (`peak_cpu_id=24`)<br>**`dmesg` / `ethtool` Faults**: 0 faults (`rx_missed=0`) |
| **4. Full v3.0 (`ecore` + `-Z`)** | **`spread_l2` `16,20,24..76`** | **`512 / 4096`**<br>**Aggregate Throughput (Mean ± 95% CI)**: **`192.64 ± 0.96 Gbps`**<br>**Run-to-Run CV / Active Core Util (`active_cpu_util`) / `dmesg` / `ethtool` Faults**: **Run-to-Run CV**: **`0.80%`**<br>**Active Core Util (`active_cpu_util`)**: **`61.8%` (`peak_cpu_id=20`)**<br>**`dmesg` / `ethtool` Faults**: **0 faults (`PASS`)** |

> **Key Takeaway**: Combining per-core `netserver` isolation, `spread_l2` 1-core-per-L2-module striding,
> `tx_ring = 512`, and `-Z` zero-copy increased throughput by **+64.2 Gbps (+50.0%)** while reducing run-to-run variance
> from **14.21% down to 0.80%** and lowering active CPU utilization by **37.6 percentage points**.

---

### Case Study 2: Core Locality Qualification Matrix (`netperf-catalog -s core-locality`)
**Objective**: Quantify the exact throughput and CPU efficiency impact of process-to-IRQ core placement across four
architectural locality zones using
[`netperf-catalog`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf-catalog).

#### Command Execution
```bash
./dev/tools/netperf-catalog -H 192.168.10.2 -i eth0 -s core-locality \
    --duration 30 --output-dir ./qual_locality
```

#### Single-Stream Locality Results (`qual_locality/dashboard.md`)

| Test ID | Placement Zone | Client Core (`-T`) / Relative to Queue-0 IRQ Core (`CPU 0`) / Single-Stream Throughput / `active_cpu_util` / Efficiency (`Gbps / %CPU`) |
| --- | --- | --- |
| **`LOC-SAME-CORE`** | Exact Same Core | `-T 0,0`<br>**Relative to Queue-0 IRQ Core (`CPU 0`)**: Collides with Queue-0 hardirq/softirq on `CPU 0`<br>**Single-Stream Throughput / `active_cpu_util` / Efficiency (`Gbps / %CPU`)**: **Single-Stream Throughput**: `26.40 Gbps`<br>**`active_cpu_util`**: `100.0%`<br>**Efficiency (`Gbps / %CPU`)**: `0.264 Gbps/%` |
| **`LOC-SAME-L2`** | L2 Module Sibling | `-T 1,1`<br>**Relative to Queue-0 IRQ Core (`CPU 0`)**: Shares 4 MB L2 cache with `CPU 0` (`CPUs 0–3`)<br>**Single-Stream Throughput / `active_cpu_util` / Efficiency (`Gbps / %CPU`)**: **Single-Stream Throughput**: `41.85 Gbps`<br>**`active_cpu_util`**: `84.2%`<br>**Efficiency (`Gbps / %CPU`)**: `0.497 Gbps/%` |
| **`LOC-LOCAL-NUMA`** | Disjoint Local NUMA | `-T 16,16`<br>**Relative to Queue-0 IRQ Core (`CPU 0`)**: Dedicated L2 module on network adapter local `NUMA 0`<br>**Single-Stream Throughput / `active_cpu_util` / Efficiency (`Gbps / %CPU`)**: **Single-Stream Throughput**: **`46.24 Gbps`**<br>**`active_cpu_util`**: **`78.5%`**<br>**Efficiency (`Gbps / %CPU`)**: **`0.589 Gbps/%`** |
| **`LOC-CROSS-NUMA`** | Remote Socket NUMA | `-T 144,144`<br>**Relative to Queue-0 IRQ Core (`CPU 0`)**: Crosses inter-socket interconnect (`NUMA 1`)<br>**Single-Stream Throughput / `active_cpu_util` / Efficiency (`Gbps / %CPU`)**: **Single-Stream Throughput**: `31.12 Gbps`<br>**`active_cpu_util`**: `94.6%`<br>**Efficiency (`Gbps / %CPU`)**: `0.329 Gbps/%` |

> **Key Takeaway**: Disjoint local-NUMA L2 placement (`LOC-LOCAL-NUMA`) delivers **+75.1% higher single-stream
> throughput** than colliding on the IRQ core (`LOC-SAME-CORE`) and **+48.6% higher throughput** than cross-NUMA
> placement (`LOC-CROSS-NUMA`).

---

### Case Study 3: 3x200GbE (600Gbps) Multi-Port Breakout & Simultaneous vs. Sequential Bidirectional
**Objective**: Validate aggregate PCIe 5.0 and memory subsystem scaling across three 200GbE ports (`ens7np0`,
`ens23np0`, `ens27np0` mapped to `192.168.10.2`, `192.168.11.2`, `192.168.12.2`) under unidirectional TX, unidirectional
RX, simultaneous bidirectional (`bx`), and sequential bidirectional (`bx-seq`) modes.

#### Command Execution
```bash
# Run built-in 3x200GbE multi-port qualification profile
./dev/tools/netperf-profile -p 3x200g-multiport -H 192.168.10..12.2

# Or invoke netperf-multi directly for 48 streams (16 streams per 200GbE NIC)
./dev/tools/netperf-multi -H 192.168.10..12.2 -i ens7np0,ens23np0,ens27np0 \
    -n 48 --direction bx --per-core-netserver --base-port 18600 \
    -l 30 --check-kmsg -o json --export multiport_bx.json -- -m 131072
```

#### Empirical Multi-Port Scaling Results (3 × 200GbE = 600Gbps Wire Capacity)

| Workload Mode | Streams (`3 × 16`) | Port 0 (`ens7np0`) / Port 1 (`ens23np0`) / Port 2 (`ens27np0`) / Aggregate Throughput / Line-Rate Efficiency |
| --- | --- | --- |
| **Unidirectional `tx`** | `48 TX` | `191.8 Gbps`<br>**Port 1 (`ens23np0`)**: `190.4 Gbps`<br>**Port 2 (`ens27np0`) / Aggregate Throughput / Line-Rate Efficiency**: **Port 2 (`ens27np0`)**: `189.6 Gbps`<br>**Aggregate Throughput**: **`571.8 Gbps`**<br>**Line-Rate Efficiency**: **95.3% of 600GbE** |
| **Unidirectional `rx`** | `48 RX` | `190.9 Gbps`<br>**Port 1 (`ens23np0`)**: `189.8 Gbps`<br>**Port 2 (`ens27np0`) / Aggregate Throughput / Line-Rate Efficiency**: **Port 2 (`ens27np0`)**: `188.7 Gbps`<br>**Aggregate Throughput**: **`569.4 Gbps`**<br>**Line-Rate Efficiency**: **94.9% of 600GbE** |
| **Sequential `bx-seq`** | `48 TX` then `48 RX` | `191.5 / 190.6 Gbps`<br>**Port 1 (`ens23np0`)**: `190.1 / 189.4 Gbps`<br>**Port 2 (`ens27np0`) / Aggregate Throughput / Line-Rate Efficiency**: **Port 2 (`ens27np0`)**: `189.2 / 188.5 Gbps`<br>**Aggregate Throughput**: **`570.8Gb TX / 568.5Gb RX`**<br>**Line-Rate Efficiency**: **95.0% Unidirectional** |
| **Simultaneous `bx` (Disjoint Cores)** | `24 TX + 24 RX` | `172.4Gb TX + 168.9Gb RX`<br>**Port 1 (`ens23np0`)**: `170.8Gb TX + 167.2Gb RX`<br>**Port 2 (`ens27np0`) / Aggregate Throughput / Line-Rate Efficiency**: **Port 2 (`ens27np0`)**: `169.5Gb TX + 166.1Gb RX`<br>**Aggregate Throughput**: **`1,014.9 Gbps` Total**<br>**Line-Rate Efficiency**: **84.6% of 1.2 Tbps Full-Duplex** |

---

### Case Study 4: Automated Statistical Confidence & Direction-Aware Regression Gating
**Objective**: Compare a candidate kernel driver build against a golden baseline across both throughput
(`higher-is-better`) and request-response tail latency (`lower-is-better`) using
[`netperf_stats.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_stats.py) and
[`netperf-aggregate`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf-aggregate).

#### Statistical Foundations (`netperf_stats.py`)
For sample size $n < 30$, `netperf_stats.py` uses the exact two-tailed Student's *t*-distribution critical value
$t_{\alpha/2, n-1}$ rather than a normal $z$-approximation:

$$\text{CI}_{95\\%} = \bar{x} \pm t_{0.025, n-1} \cdot \frac{s}{\sqrt{n}}$$

Outliers are automatically flagged using Tukey's Interquartile Range (IQR) fence
($[Q_1 - 1.5\text{ IQR},\; Q_3 + 1.5\text{ IQR}]$), and both raw and outlier-cleaned means
are reported alongside skewness,
excess kurtosis, and normality test $p$-values.

#### Automated Baseline vs. Candidate Comparison (`netperf-aggregate`)
```bash
# Compare candidate run against baseline (automatically treats latency/CPU reductions as improvements)
./dev/tools/netperf-aggregate --compare baseline_rr.json candidate_rr.json -o comparison.json
```

```json
{
  "differences": {
    "throughput": {
      "baseline_mean": 184210.5,
      "current_mean": 192640.2,
      "absolute_diff": 8429.7,
      "percent_diff": 4.58,
      "is_improvement": true,
      "is_regression": false
    },
    "latency": {
      "baseline_mean": 14.82,
      "current_mean": 11.40,
      "absolute_diff": -3.42,
      "percent_diff": -23.08,
      "is_improvement": true,
      "is_regression": false
    }
  }
}
```

---

### Case Study 5: Three-Tier Comparative Methodology & $2 \times 2$ Link-Speed $\times$ MTU Matrix

**Objective**: Establish a confounder-free, reproducible comparative methodology across `netperf_copilot`, classic
`netperf 2.7.0`, `iperf2`, and `iperf3` (`<= 3.15` vs. `>= 3.16`) across the full **$2 \times 2$ Link-Speed $\times$
MTU matrix (`100GbE` & `200GbE` at both `MTU 1500` and `MTU 9000`)** using
[`netperf_benchmark_study.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_benchmark_study.py),
[`netperf_pcm_bridge.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_pcm_bridge.py), and
[`netperf_flent_bridge.py`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_flent_bridge.py).
(See also the standalone companion white paper:
[`Benchmark-Study-vs-iperf2-iperf3-netperf`](https://github.com/thehevy/netperf_copilot/wiki/Benchmark-Study-vs-iperf2-iperf3-netperf)
/
[`WP_NETPERF_COPILOT_VS_IPERF2_IPERF3_NETPERF_BENCHMARK_STUDY.md`](https://github.com/thehevy/netperf_copilot/blob/master/dev/docs/WP_NETPERF_COPILOT_VS_IPERF2_IPERF3_NETPERF_BENCHMARK_STUDY.md).)

#### 1. Three-Tier Experimental Design (`Tier A` $\to$ `Tier B1` $\to$ `Tier B2`) & `2x2` MTU Coverage

| Tier | Configuration | Purpose & Tool Equivalence |
| --- | --- | --- |
| **`Tier A: Default Unpinned`** | No explicit CPU pinning; default single daemon listener (`12865` / `5001` / `5201`); `1`–`64` streams. | Quantifies out-of-the-box user experience and scheduler/listener bottlenecks across tools. |
| **`Tier B1: Shared taskset Pool`** | Identical `numactl --cpunodebind=<node> taskset -c <core_list>` non-IRQ pool applied to **all 4 tools** (including `netperf-multi` without 1:1 `--affinity`, `--per-core-netserver`, or `-Z`). | Strict apples-to-apples engine comparison under identical shared-pool OS scheduling (`17%`–`22%` intra-pool overlap across all tools). |
| **Tier B2: 1:1 Pinned + Full Capabilities** | 1:1 per-flow core pinning (`--affinity` `spread_l2`/`spread_step2` + `--per-core-netserver` + `-Z` `MSG_ZEROCOPY` vs. 1:1 `taskset -c` classic `netperf` and $N$-process `iperf3`). | Quantifies the incremental gain unlocked by `netperf_copilot`'s 1:1 topology striding, lockless daemon pool, and zero-copy (`+19.55 Gbps` at `200GbE MTU 1500`). |

#### 2. Head-to-Head Capability, Accuracy & Observability Matrix

| Evaluation Dimension | `netperf_copilot` (`OMNI` + `Flent` + `PCM`) | Classic `netperf` (`2.7.1`) · `iperf2` (`2.1.x`) · `iperf3` (`>= 3.16` / `<= 3.15`) |
| --- | --- | --- |
| **Multi-Flow Execution Model** | **Barrier-synced `OMNI` processes** (`< 5 ms` skew) pinned 1:1 to disjoint cores | **Classic `netperf`**: Single-flow process (requires external `taskset` + `-w` loop)<br>**`iperf2` / `iperf3 >= 3.16`**: Multi-threaded `pthread_create` (`<= 3.15`: single reactor) |
| **Runtime Core Residency & Overlap** | **Yes (`LOCAL_CPU_BIND` vs. `LOCAL_CPU_EXEC` + `LOCAL_CPU_MIGRATIONS`)** | **Classic `netperf`**: Exposes `LOCAL_CPU_BIND` & `LOCAL_CPU_PEAK_ID` for 1 flow only<br>**`iperf2` / `iperf3`**: **No** per-thread core residency (`iperf3 -A` pins all `-P` threads to 1 core) |
| **CPU Utilization & Service Demand** | **High (`< 1%` error)**: Per-core + whole-host `/proc/stat` + `LOCAL_SD` (`us/KB`, `us/Tran`) | **Classic `netperf`**: **High** (kernel `/proc/stat` across all cores)<br>**`iperf2`**: **Low (`18%–55%` error)** · **`iperf3`**: **Poor (`42%–87%` error)** (`getrusage` misses `softirq`) |
| **Tail Latency (`p50`/`p90`/`p99`/`p99.9`)** | **Yes (Microsecond Histogram)**: Per-flow & pooled `P50`, `P90`, `P99`, `P999` + worst-flow bound | **Classic `netperf`**: Per-flow `P50`/`P90`/`P99` (`--enable-histogram`); no `P999` or multi-flow pooling<br>**`iperf2` / `iperf3`**: **No** RPC `p99`/`p99.9` histogram (`TCP_INFO` mean RTT / UDP jitter only) |
| **Warm-Up Omit & Firewall Ports** | **Yes**: `--omit <sec>` steady-state filter + `--data-port-base` (`-P`) | **Classic `netperf`**: `-w <sec>` pre-traffic sleep only; `-P` per instance<br>**`iperf2` / `iperf3`**: `--omit` (`-O`) supported; single port `5001` / `5201` |
| **Uncore & Cache Visibility (`DDIO`/`UPI`)** | **Yes (`netperf_pcm_bridge.py`)**: `DDIO Hit %`, `IPC`, `L3 Hit %`, `DRAM`/`UPI GB/s`, `Watts` | **Classic `netperf` / `iperf2` / `iperf3`**: **None** (Network socket metrics only) |

#### 3. `100GbE` Empirical Matrix: `MTU 1500` (`94.15 Gbps` Ceiling) vs. `MTU 9000` (`98.96 Gbps` Ceiling)

```mermaid
xychart-beta
    title "100GbE 64F: MTU 1500 (Bar) vs MTU 9000 (Line)"
    x-axis ["NC-B2", "NP-B2", "i3-B2", "NC-B1", "i3-B1", "i2-B1", "NC-A", "i3-A", "i2-A", "i3.15"]
    y-axis "Throughput (Gbps)" 40 --> 100
    bar [94.13, 93.85, 93.70, 93.55, 93.40, 92.90, 87.10, 82.40, 81.50, 58.20]
    line [98.95, 98.84, 98.78, 98.40, 98.20, 97.90, 93.80, 90.40, 89.50, 71.40]
```

| Tier & Tool Configuration | `100GbE` `16F` / `64F` Throughput (`Mean ± 95% CI`) | `64F` (`MTU 1500`) Fairness, Overlap, `DDIO Hit %` & CPU Error |
| --- | --- | --- |
| **Tier B2: `netperf_copilot` (1:1 Pinned + Pool + `-Z`)** | **`MTU 1500`**: **`94.15 ± 0.11` / `94.13 ± 0.14 Gbps`**<br>**`MTU 9000`**: **`98.96 ± 0.08` / `98.95 ± 0.10 Gbps`** | **`Jain = 0.996`** · `0.0%` Overlap<br>**`99.41%` DDIO Hit** · **`0.9%` CPU Error** |
| **Tier B2: Classic `netperf` (1:1 `taskset` + Pool)** | **`MTU 1500`**: `94.08 ± 0.18` / `93.85 ± 0.31 Gbps`<br>**`MTU 9000`**: `98.92 ± 0.12` / `98.84 ± 0.19 Gbps` | `Jain = 0.991` · `0.0%` Overlap<br>`98.90%` DDIO Hit · `1.4%` CPU Error |
| **Tier B2: `iperf3 >= 3.16` ($N$-Process 1:1 `taskset`)** | **`MTU 1500`**: `94.02 ± 0.22` / `93.70 ± 0.38 Gbps`<br>**`MTU 9000`**: `98.90 ± 0.14` / `98.78 ± 0.22 Gbps` | `Jain = 0.988` · `0.0%` Overlap<br>`98.40%` DDIO Hit · **`64.2%` CPU Error** |
| **Tier B1: `netperf_copilot` (Shared `taskset` Pool)** | **`MTU 1500`**: `93.96 ± 0.31` / `93.55 ± 0.68 Gbps`<br>**`MTU 9000`**: `98.88 ± 0.21` / `98.40 ± 0.48 Gbps` | `Jain = 0.954` · `17.2%` Pool Overlap<br>`89.10%` DDIO Hit · **`0.9%` CPU Error** |
| **Tier B1: Classic `netperf` (Shared `taskset` Pool)** | **`MTU 1500`**: `93.92 ± 0.34` / `93.45 ± 0.72 Gbps`<br>**`MTU 9000`**: `98.85 ± 0.24` / `98.30 ± 0.52 Gbps` | `Jain = 0.950` · `18.8%` Pool Overlap<br>`88.50%` DDIO Hit · `2.1%` CPU Error |
| **Tier B1: `iperf3 >= 3.16` (Shared `taskset` Pool)** | **`MTU 1500`**: `93.90 ± 0.35` / `93.40 ± 0.74 Gbps`<br>**`MTU 9000`**: `98.82 ± 0.25` / `98.20 ± 0.55 Gbps` | `Jain = 0.948` · `18.8%` Pool Overlap<br>`88.20%` DDIO Hit · **`68.4%` CPU Error** |
| **Tier B1: `iperf2` (Shared `taskset` Pool)** | **`MTU 1500`**: `93.80 ± 0.42` / `92.90 ± 0.89 Gbps`<br>**`MTU 9000`**: `98.75 ± 0.30` / `97.90 ± 0.64 Gbps` | `Jain = 0.936` · `21.9%` Pool Overlap<br>`86.40%` DDIO Hit · **`38.4%` CPU Error** |
| **Tier A: `netperf_copilot` (Default Unpinned)** | **`MTU 1500`**: `93.68 ± 0.79` / `87.10 ± 2.25 Gbps`<br>**`MTU 9000`**: `98.50 ± 0.54` / `93.80 ± 1.65 Gbps` | `Jain = 0.758` · `67.2%` Overlap<br>`51.20%` DDIO Hit · **`1.1%` CPU Error** |
| **Tier A: Classic `netperf` (Default Unpinned Loop)** | **`MTU 1500`**: `93.60 ± 0.84` / `86.40 ± 2.40 Gbps`<br>**`MTU 9000`**: `98.40 ± 0.58` / `93.10 ± 1.78 Gbps` | `Jain = 0.745` · `68.8%` Overlap<br>`48.90%` DDIO Hit · `21.8%` CPU Error |
| **Tier A: `iperf3 >= 3.16` (`-P N` Unpinned Pthreads)** | **`MTU 1500`**: `93.50 ± 0.92` / `82.40 ± 2.85 Gbps`<br>**`MTU 9000`**: `98.10 ± 0.68` / `90.40 ± 2.10 Gbps` | `Jain = 0.702` · `71.9%` Overlap<br>`42.10%` DDIO Hit · **`72.1%` CPU Error** |
| **Tier A: `iperf2` (`-P N` Unpinned Pthreads)** | **`MTU 1500`**: `93.40 ± 0.98` / `81.50 ± 3.10 Gbps`<br>**`MTU 9000`**: `97.90 ± 0.74` / `89.50 ± 2.30 Gbps` | `Jain = 0.684` · `73.4%` Overlap<br>`39.60%` DDIO Hit · **`54.8%` CPU Error** |
| **Tier A/B1: `iperf3 <= 3.15` (Single Reactor)** | **`MTU 1500`**: `88.90 ± 1.45` / `58.20 ± 2.95 Gbps`<br>**`MTU 9000`**: `94.20 ± 1.10` / `71.40 ± 2.60 Gbps` | `Jain = 0.462` · `100.0%` Overlap<br>`22.40%` DDIO Hit · **`86.9%` CPU Error** |

#### 4. `200GbE` Empirical Matrix: `MTU 1500` (`188.30 Gbps` Ceiling) vs. `MTU 9000` (`197.97 Gbps` Ceiling)

```mermaid
xychart-beta
    title "200GbE 64F: MTU 1500 (Bar) vs MTU 9000 (Line)"
    x-axis ["NC-B2", "NP-B2", "i3-B2", "NC-B1", "i3-B1", "i2-B1", "NC-A", "i3-A", "i2-A", "i3.15"]
    y-axis "Throughput (Gbps)" 50 --> 200
    bar [187.95, 179.80, 178.60, 168.40, 165.90, 163.20, 141.20, 129.60, 126.80, 61.80]
    line [197.94, 196.10, 195.60, 192.10, 191.20, 189.60, 178.20, 162.40, 159.80, 89.60]
```

| Tier & Tool Configuration | `200GbE` `16F` / `64F` Throughput (`Mean ± 95% CI`) | `64F` Fairness, Overlap & Intel® PCM `DDIO Hit %` (`MTU 1500` / `9000`) |
| --- | --- | --- |
| **Tier B2: `netperf_copilot` (1:1 Pinned + Pool + `-Z`)** | **`MTU 1500`**: **`188.10 ± 0.42` / `187.95 ± 0.51 Gbps`**<br>**`MTU 9000`**: **`197.97 ± 0.38` / `197.94 ± 0.45 Gbps`** | **`Jain = 0.994`** · `0.0%` Overlap<br>**`98.92%` / `99.48%` DDIO Hit** |
| **Tier B2: Classic `netperf` (1:1 `taskset` + Pool, Copy)** | **`MTU 1500`**: `181.40 ± 0.85` / `179.80 ± 1.12 Gbps`<br>**`MTU 9000`**: `197.40 ± 0.62` / `196.10 ± 0.88 Gbps` | `Jain = 0.985` · `0.0%` Overlap<br>`96.40%` / `98.60%` DDIO Hit |
| **Tier B2: `iperf3 >= 3.16` ($N$-Process 1:1 `taskset`)** | **`MTU 1500`**: `180.90 ± 0.92` / `178.60 ± 1.24 Gbps`<br>**`MTU 9000`**: `197.10 ± 0.68` / `195.60 ± 0.95 Gbps` | `Jain = 0.982` · `0.0%` Overlap<br>`95.80%` / `98.10%` DDIO Hit |
| **Tier B1: `netperf_copilot` (Shared `taskset` Pool)** | **`MTU 1500`**: `174.20 ± 1.45` / `168.40 ± 2.10 Gbps`<br>**`MTU 9000`**: `196.20 ± 1.05` / `192.10 ± 1.75 Gbps` | `Jain = 0.928` · `17.2%` Pool Overlap<br>`82.40%` / `89.40%` DDIO Hit |
| **Tier B1: Classic `netperf` (Shared `taskset` Pool)** | **`MTU 1500`**: `173.50 ± 1.52` / `167.10 ± 2.25 Gbps`<br>**`MTU 9000`**: `195.95 ± 1.10` / `191.50 ± 1.85 Gbps` | `Jain = 0.922` · `18.8%` Pool Overlap<br>`81.60%` / `88.70%` DDIO Hit |
| **Tier B1: `iperf3 >= 3.16` (Shared `taskset` Pool)** | **`MTU 1500`**: `172.80 ± 1.60` / `165.90 ± 2.38 Gbps`<br>**`MTU 9000`**: `195.80 ± 1.15` / `191.20 ± 1.92 Gbps` | `Jain = 0.918` · `18.8%` Pool Overlap<br>`80.90%` / `88.20%` DDIO Hit |
| **Tier B1: `iperf2` (Shared `taskset` Pool)** | **`MTU 1500`**: `170.90 ± 1.78` / `163.20 ± 2.65 Gbps`<br>**`MTU 9000`**: `194.90 ± 1.34` / `189.60 ± 2.15 Gbps` | `Jain = 0.904` · `21.9%` Pool Overlap<br>`78.50%` / `86.40%` DDIO Hit |
| **Tier A: `netperf_copilot` (Default Unpinned)** | **`MTU 1500`**: `164.80 ± 2.80` / `141.20 ± 4.90 Gbps`<br>**`MTU 9000`**: `194.60 ± 1.95` / `178.20 ± 4.50 Gbps` | `Jain = 0.712` · `67.2%` Overlap<br>`44.60%` / `52.40%` DDIO Hit |
| **Tier A: Classic `netperf` (Default Unpinned Loop)** | **`MTU 1500`**: `163.20 ± 2.95` / `138.90 ± 5.15 Gbps`<br>**`MTU 9000`**: `194.20 ± 2.10` / `176.40 ± 4.85 Gbps` | `Jain = 0.698` · `68.8%` Overlap<br>`42.80%` / `48.90%` DDIO Hit |
| **Tier A: `iperf3 >= 3.16` (`-P N` Unpinned Pthreads)** | **`MTU 1500`**: `158.40 ± 3.40` / `129.60 ± 5.80 Gbps`<br>**`MTU 9000`**: `190.10 ± 2.65` / `162.40 ± 5.40 Gbps` | `Jain = 0.654` · `71.9%` Overlap<br>`36.40%` / `42.10%` DDIO Hit |
| **Tier A: `iperf2` (`-P N` Unpinned Pthreads)** | **`MTU 1500`**: `156.10 ± 3.65` / `126.80 ± 6.10 Gbps`<br>**`MTU 9000`**: `188.50 ± 2.90` / `159.80 ± 5.75 Gbps` | `Jain = 0.638` · `73.4%` Overlap<br>`34.10%` / `39.60%` DDIO Hit |
| **Tier A/B1: `iperf3 <= 3.15` (Single Reactor)** | **`MTU 1500`**: `96.40 ± 3.10` / `61.80 ± 3.90 Gbps`<br>**`MTU 9000`**: `142.10 ± 3.80` / `89.60 ± 4.60 Gbps` | `Jain = 0.428` · `100.0%` Overlap<br>`19.80%` / `22.40%` DDIO Hit |

#### 5. Runtime Per-Flow Core Residency (`LOCAL_CPU_EXEC`) vs. Configured Affinity (`LOCAL_CPU_BIND`)

`netperf_copilot` explicitly separates **configured affinity** (`LOCAL_CPU_BIND` / `REMOTE_CPU_BIND` from `-T
<local>,<remote>`) from **observed runtime CPU execution** (`LOCAL_CPU_EXEC`, `REMOTE_CPU_EXEC`, and
`LOCAL_CPU_MIGRATIONS` sampled via `sched_getcpu()` inside `src/nettest_omni.c` and `200 ms` `/proc/<pid>/stat` field 39
polling in `netperf-multi`):

| Flow ID | `netperf_copilot` (Tier B2 Pinned)<br>`BIND` / `EXEC` · `MIGR` · BW · `SD` · `p99` / `p99.9` | `iperf2` / `iperf3 >= 3.16` (Tier A Unpinned) & `iperf3 <= 3.15` (Single Reactor) |
| --- | --- | --- |
| **`F00`** | **`CPU 00 / 00`** (`0` mig)<br>`5.89 Gbps` · `0.16 us/KB` · `31 / 44 us` | **`iperf2`/`3.16` (Tier A)**: **`CPU 04`** (Shared w/ `F01`! `7.42 Gbps` · **Core Collision**)<br>**`iperf3 <= 3.15`**: **`CPU 00`** (`8.12 Gbps` · **16-Way Multiplex**) |
| **`F01`** | **`CPU 02 / 02`** (`0` mig)<br>`5.88 Gbps` · `0.16 us/KB` · `32 / 46 us` | **`iperf2`/`3.16` (Tier A)**: **`CPU 04`** (Collides w/ `F00`! **`3.81 Gbps` · `-48.7%` Outlier**)<br>**`iperf3 <= 3.15`**: **`CPU 00`** (**`3.44 Gbps` · `-57.6%` Starved**) |
| **`F02`** | **`CPU 04 / 04`** (`0` mig)<br>`5.90 Gbps` · `0.15 us/KB` · `30 / 43 us` | **`iperf2`/`3.16` (Tier A)**: **`CPU 07`** (Isolated · `6.95 Gbps` · Nominal)<br>**`iperf3 <= 3.15`**: **`CPU 00`** (`7.65 Gbps` · **16-Way Multiplex**) |
| **`F03`** | **`CPU 06 / 06`** (`0` mig)<br>`5.88 Gbps` · `0.16 us/KB` · `33 / 47 us` | **`iperf2`/`3.16` (Tier A)**: **`CPU 12`** (Shared w/ `F04`! `6.88 Gbps` · **Core Collision**)<br>**`iperf3 <= 3.15`**: **`CPU 00`** (**`4.18 Gbps` · `-48.5%` Starved**) |

#### 6. Independent `/proc/stat` & Intel® PCM Ground Truth (`netperf_pcm_bridge.py`)

To verify the accuracy of each benchmark's internal CPU utilization telemetry without circular self-reference:

1. [`ProcStatGroundTruth`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_pcm_bridge.py)
   snapshots `/proc/stat` before and after each trial (`cpu_error_pct = (abs(tool_reported_cpu_pct - procstat_cpu_pct) /
   max(procstat_cpu_pct, 1e-6)) * 100.0`).
2. [`IntelPCMCollector`](https://github.com/thehevy/netperf_copilot/blob/master/dev/tools/netperf_pcm_bridge.py)
   collects hardware PMU counters (`ddio_hit_pct = ((PCIRdCur_hit + ItoMCacheNear_hit) / (PCIRdCur_total +
   ItoMCacheNear_total)) * 100.0`, `IPC`, `L2`/`L3` cache hit ratio, `DRAM` and `UPI` bandwidth, and `gbps_per_watt`).

#### 7. Five Engineering Improvements Over Stock `netperf`, `iperf2`, and `iperf3 >= 3.16` (`IMP-001`–`IMP-005`)

| ID | Baseline Gap Across Stock `netperf`, `iperf2`, and `iperf3 >= 3.16` | Implemented & Verified Upgrade in `netperf_copilot` |
| --- | --- | --- |
| **`IMP-001`** | `iperf3 -O <sec>` excludes TCP slow-start warm-up; stock `netperf -w <sec>` only sleeps before traffic starts. | Added `-O` / `--omit <sec>` to `netperf-multi` (`-D 0.20` interim filtering into `steady_state_throughput_gbps`). |
| **`IMP-002`** | Stock `netperf` lacks `P99.9` and multi-flow pooling; `iperf2` and `iperf3` lack RPC `p99`/`p99.9` histograms. | Added `P999_LATENCY` in `src/nettest_omni.c` plus `pooled_p50/p90/p99/p999_latency_us` and `worst_flow_p99/p999_latency_us`. |
| **`IMP-003`** | `iperf3` uses single port `5201`; stock `netperf` opens random ephemeral data ports across firewalls. | Standardized `--data-port-base <port>` (`-P <port+i>,<port+i>`) in `netperf-multi` and Tier B study runs. |
| **`IMP-004`** | Shell loops of stock `netperf` suffer `150–400 ms` sequential fork skew vs. `iperf2`/`iperf3 >= 3.16` pthreads. | Implemented `threading.Barrier(N)` parallel launch (`launch_skew_ms < 5 ms`) + `-w` post-handshake sync. |
| **`IMP-005`** | Harnesses invoke `iperf3 -P N` without checking for `<= 3.15` single-reactor builds or `-A <cpu> -P N` traps. | Added BenchmarkStudyHarness.<wbr><wbr>check_iperf3_version_<wbr><wbr>gate() enforcing `iperf3 >= 3.16` and rejecting `-A <cpu> -P N`. |

```bash
# Execute the three-tier comparative study (5 randomized trials per tool per tier) with PCM and Flent working latency
python dev/tools/netperf_benchmark_study.py --host 198.51.100.20 --interface ens801f0np0 \
    --flows 1,4,8,16,32,64 --duration 30 --trials 5 --execute --output-json study_report.json
```
---

## 8. Conclusion & Future Roadmap

The **Netperf Modernization Project (v3.0)** demonstrates that a foundational UNIX systems benchmark can be brought into
the 100GbE–800GbE and 288+-core era without breaking compatibility with decades of existing engineering workflows. By
pairing low-level C engine enhancements (`MSG_ZEROCOPY`, 4 MB buffers, 2048-core active CPU telemetry, 32-bit
`ETHTOOL_GLINKSETTINGS`, PCIe 5.0/6.0 `sysfs` introspection, and structured JSON/CSV/Preset output) with silicon-aware
Python orchestration (`netserver-manager`, `netperf-multi`, `netperf-preflight`, `netperf-tuner`, and
`netperf-catalog`), the project eliminates artificial harness bottlenecks and turns network performance qualification
into a repeatable, statistically rigorous engineering discipline.

### Key Takeaways for Platform & Network Engineers

1. **Never Share a Single `netserver` Listener at 100GbE+**: Always deploy a per-core `netserver` pool
   (`netserver-manager`) on NUMA-local cores disjoint from network adapter RSS IRQ cores.
2. **Respect Microarchitectural Cache Topology**: Use `spread_l2` (1 core per 4-core L2 module) and `tx_ring = 512` on
   high-density E-core processors to prevent L2 cache thrashing; use `spread_step2` (filtering SMT siblings) and
   `tx_ring = 2048` on P-core SMT processors.
3. **Gate Every Benchmark on Pre-Flight Sanity and Kernel Faults**: Run `netperf-preflight` (24 anti-affinity rules +
   5-run warmup gate) before testing and enforce `--check-kmsg` (`U1`–`U13` `dmesg` & `ethtool -S` verification) on
   every run.
4. **Monitor `active_cpu_util` and `peak_cpu_id`, Not Global CPU Average**: On 128–576 thread servers, global CPU
   utilization hides single-core softirq and application saturation.

### References & Project Documentation

- **Project Wiki**: [`wiki/Home.md`](https://github.com/thehevy/netperf_copilot/wiki)
- **Executive Summary**:
  [`dev/docs/EXECUTIVE_SUMMARY.md`](https://github.com/thehevy/netperf_copilot/blob/master/dev/docs/EXECUTIVE_SUMMARY.md)
- **High-Speed 200GbE–800GbE & Multi-Core Guide**:
  [`wiki/High-Speed-200GbE-800GbE-and-Xeon6-Guide.md`](https://github.com/thehevy/netperf_copilot/wiki/High-Speed-200GbE-800GbE-and-Xeon6-Guide)
- **Pre-Flight Rules & Fault Signatures (`AA-001`–`AA-024`, `U1`–`U13`)**:
  [`wiki/Pre-Flight-Checks-and-Fault-Monitoring.md`](https://github.com/thehevy/netperf_copilot/wiki/Pre-Flight-Checks-and-Fault-Monitoring)
- **CLI Tools Reference**:
  [`wiki/CLI-Tools-Reference.md`](https://github.com/thehevy/netperf_copilot/wiki/CLI-Tools-Reference)

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `wiki/Technical-White-Paper.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-16` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet 200GbE`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-TECHNICAL-WHITE`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
