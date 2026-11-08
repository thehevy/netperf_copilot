# Modernizing Network Performance Benchmarking for 100G–800G Fabrics and Next-Generation Multi-Core Server Architectures

**A Technical White Paper on the Netperf v3.0 Modernization Project**

**Document Type**: Technical Architecture & Performance Engineering White Paper
**Project**: Netperf v3.0 Modernization (`https://github.com/thehevy/netperf_copilot`)
**Scope**: Core C Engine (`src/`), Silicon-Aware Topology & Daemon Orchestration (`dev/tools/`), Automated BKM Tuning, Hardware Fault Gating, and Empirical Qualification Results

---

## Abstract

Network interface speeds in cloud and enterprise datacenters have scaled by two orders of magnitude—from 10 GbE to **100 GbE, 200 GbE, 400 GbE, and 800 GbE** over PCIe Gen5 and Gen6 interconnects—while server processor core counts have expanded from 8–32 cores to **144–288+ physical cores** across heterogeneous Performance-core (P-Core SMT) and Efficient-core (E-Core shared-L2 module) microarchitectures. However, the foundational open-source network benchmarking tool **`netperf` (v2.7.0)** remained frozen in an architecture designed for single-port listeners, 1 MB socket buffers, 256-CPU telemetry arrays, 16-bit `ethtool` link speed counters, and unstructured human-readable text output.

When engineers attempt to qualify 200G–800G adapters using unmodified `netperf`, they encounter severe artificial bottlenecks: kernel accept-queue serialization on TCP port `12865`, L2/LLC cache thrashing on 4-core E-core clusters, softirq/application thread collisions, user-to-kernel memory copy saturation, and **15%–40% run-to-run throughput variance** that masks genuine driver or hardware regressions.

This white paper presents the architecture, mathematical foundations, implementation details, and empirical results of the **Netperf Modernization Project (v3.0)**. We detail how `netperf` was re-engineered across seven phases—preserving **100% backward compatibility** for legacy scripts while introducing a zero-copy 4 MB C data path (`-Z`), 2048-core active CPU telemetry, 32-bit `ETHTOOL_GLINKSETTINGS` & PCIe Gen5/Gen6 introspection, a lockless per-core `netserver` daemon pool, microarchitecture-aware L2/SMT core striding, a 24-rule pre-flight sanity gate, automated Best Known Method (BKM) tuning, and a zero-tolerance kernel/NIC fault monitor. Empirical case studies demonstrate how these enhancements raise 200GbE E-core throughput from **128.4 Gbps ($\text{CV} = 14.2\%$) to 192.6 Gbps ($\text{CV} = 0.8\%$)** and scale cleanly to **571.8 Gbps** across 3x200GbE multi-port breakouts.

---

## Table of Contents

1. [Introduction: The 100G–800G Benchmarking Crisis](#1-introduction-the-100g800g-benchmarking-crisis)
2. [Anatomy of Legacy Bottlenecks in Netperf 2.7.0](#2-anatomy-of-legacy-bottlenecks-in-netperf-270)
3. [Architectural Modernization of the Core C Engine (`src/`)](#3-architectural-modernization-of-the-core-c-engine-src)
4. [Silicon-Aware Topology Engine & Per-Core Daemon Architecture](#4-silicon-aware-topology-engine--per-core-daemon-architecture)
5. [High-Speed Multi-Stream, Multi-NIC & QoS Orchestration](#5-high-speed-multi-stream-multi-nic--qos-orchestration)
6. [Pre-Flight Auditing, Automated BKM Tuning & Zero-Tolerance Fault Gating](#6-pre-flight-auditing-automated-bkm-tuning--zero-tolerance-fault-gating)
7. [Empirical Results, Case Studies & End-to-End Workflows](#7-empirical-results-case-studies--end-to-end-workflows)
8. [Conclusion & Future Roadmap](#8-conclusion--future-roadmap)

---

## 1. Introduction: The 100G–800G Benchmarking Crisis

### 1.1 The Widening Gap Between Silicon Evolution and Benchmark Tooling
Over the past decade, datacenter networking and server compute have undergone three fundamental structural shifts:

1. **Line-Rate Compression of the Inter-Packet Budget**: At 10 GbE with standard 1500-byte Ethernet frames, a NIC processes at most 812,740 packets per second ($\sim 1.23\,\mu\text{s}$ per frame). At **200 GbE**, line rate demands **16.25 million packets per second** ($\sim 61.5\,\text{ns}$ per frame) at MTU 1500, or **2.71 million frames per second** ($\sim 369\,\text{ns}$ per frame) with 9000-byte jumbo frames. At **400 GbE and 800 GbE**, the per-packet CPU and DMA budget shrinks below single-digit DRAM access latencies.
2. **Bifurcation of Server Processor Microarchitectures**: Modern server CPUs have diverged into two distinct silicon paradigms:
   - **Performance-Core (P-Core) SMT Architectures**: Deep out-of-order cores with 2-way Simultaneous Multithreading (SMT) and large private L2 caches (e.g., 2 MB per physical core), where sibling hardware threads `(cpu_i, cpu_{i+N})` contend for the same execution units and L1/L2 cache capacity.
   - **High-Density Efficient-Core (E-Core) Clustered Architectures**: Up to 144–288 non-SMT physical cores per socket organized into **4-core modules sharing a unified L2 cache** (e.g., 4 MB shared L2 per 4 cores).
3. **CI/CD & AI-Driven Qualification Pipelines**: Modern silicon and driver validation teams execute thousands of automated test matrices across ring buffer sizes, interrupt coalescing timers, QoS traffic classes, and NIC breakout configurations. Unstructured ASCII tables that require fragile `awk`/`sed` regexes cannot feed automated statistical regression gates or AI root-cause engines.

### 1.2 Why Unmodified `netperf` Produces Misleading Results at 200G+
When validation teams run legacy `netperf` loops against a 200GbE or 400GbE adapter, they frequently observe throughput plateauing between **110 Gbps and 140 Gbps** with erratic **15%–40% run-to-run swings**. Engineers often misdiagnose this behavior as a NIC firmware bottleneck or Linux TCP stack regression, when in reality **the benchmark harness itself is the bottleneck**.

The **Netperf Modernization Project (v3.0)** was initiated to systematically identify and eliminate every software, topological, and operational bottleneck in `netperf`—without sacrificing the tool's battle-tested control protocol or breaking a single legacy user script.

---

## 2. Anatomy of Legacy Bottlenecks in Netperf 2.7.0

A rigorous code and kernel-profile audit of upstream `netperf` 2.7.0 revealed four classes of architectural bottlenecks that prevent accurate benchmarking on modern systems.

```mermaid
flowchart TD
    subgraph LegacyPath["Legacy Netperf 2.7.0 Failure Modes at 200G+"]
        direction TB
        B1["1. Control Plane Serialization\n64 clients connect to single TCP port 12865\n-> Kernel accept queue lock contention\n-> Child netserver inherits listener CPU"]
        B2["2. Memory Copy & Buffer Ceiling\nMAXMESSAGESIZE capped at 1 MB\n-> Mandatory copy_from_user() on every send()\n-> 25 GB/s DRAM copy overhead at 200 Gbps"]
        B3["3. High-Core-Count Blind Spots\nMAXCPUS = 256 limit in /proc/stat parser\n-> Global avg CPU reports 5.5% when 16/288 cores hit 100%\n-> Hottest core saturation completely hidden"]
        B4["4. Hardware & Link Blindness\nETHTOOL_GSET 16-bit speed overflows > 65 Gbps\n-> 4-char PCIe width buffer overflows on 'x16'\n-> No pre-flight check for PCIe Gen5 downgrade or NUMA mismatch"]
    end
```

### 2.1 The Three Classic `netserver` Control-Plane Bottlenecks
In traditional multi-stream `netperf` scripts, a single `netserver` daemon listens on TCP port `12865`:
1. **Control-Port Accept Queue Contention**: Launching 32–128 parallel `netperf` instances simultaneously against port `12865` floods a single kernel socket listen backlog (`sk_ack_backlog`), causing SYN retransmissions, control handshake timeouts, and staggered stream start times.
2. **`fork()` / `clone()` CPU Inheritance**: When the parent `netserver` forks a child process to service a data connection, the child inherits the parent's CPU affinity mask until late in the control negotiation—bunching initial TCP socket allocations and page faults onto a single core.
3. **NIC Softirq (`ksoftirqd`) vs. Application Thread Collision**: Without topology-aware core partitioning, `netperf -T` or OS scheduler placement frequently schedules `netperf`/`netserver` user-space threads onto the exact same CPU cores (`0..15`) servicing the NIC's hardware RSS/MSIX interrupt queues. When a single core must execute both the kernel `NET_RX_SOFTIRQ` NAPI poll loop and user-space `recv()` system calls at 200 Gbps, L1 instruction/data cache thrashing and context-switch overhead collapse per-stream throughput by **30%–50%**.

### 2.2 Data-Path Copy Tax and the 1 MB Buffer Ceiling
In `src/netlib.h` and `src/nettest_omni.c`, upstream `netperf` hardcoded `MAXMESSAGESIZE` to `1048576` bytes (1 MB) and relied exclusively on standard copy-mode `send()` / `sendto()` calls.

At a line rate of $R = 200\text{ Gbps}$ ($25\text{ GB/s}$), standard socket transmission requires the CPU to copy every byte from the user-space send buffer into kernel `sk_buff` page fragments via `copy_from_user()`. Including read and write memory traffic, this imposes a minimum DRAM bandwidth tax of:

$$\text{BW}_{\text{DRAM, copy}} = 2 \times \frac{R}{8} = 2 \times 25\text{ GB/s} = 50\text{ GB/s}$$

before accounting for NIC DMA reads over PCIe or receive-side copies. On high-density E-core processors where per-core memory bandwidth and L2 cache capacity are tightly budgeted, copy-mode socket I/O saturates the memory subsystem well before the 200GbE or 400GbE wire is full.

### 2.3 The High-Core-Count Telemetry Blind Spot (`MAXCPUS = 256`)
Upstream `netperf` dimensioned its `/proc/stat` CPU accounting arrays to `MAXCPUS = 256`. Modern dual-socket servers routinely expose **288 to 576 logical CPUs**. Worse, legacy `netperf` only computes a single system-wide mean CPU utilization across all $N_{\text{total}}$ logical processors:

$$U_{\text{global}} = \frac{1}{N_{\text{total}}} \sum_{i=0}^{N_{\text{total}}-1} u_i$$

Consider a 16-stream 200GbE test on a 288-core server where all 16 active cores are pinned at $u_i = 100\%$ utilization and the remaining 272 cores are idle ($u_i = 0\%$):

$$U_{\text{global}} = \frac{16 \times 100\%}{288} = 5.56\%$$

A benchmark engineer looking at `LOCAL_CPU_UTIL=5.56` concludes that the CPU is 94% idle and blames the NIC or TCP congestion control for failing to scale, completely unaware that the 16 active cores are 100% CPU-bound!

### 2.4 Legacy 16-Bit Ethtool and `sysfs` Buffer Limits
- **16-Bit Link Speed Overflow**: `src/netdrv_ethtool.c` relied on the deprecated `ETHTOOL_GSET` ioctl (`struct ethtool_cmd`), which stores link speed in a 16-bit unsigned integer (`__u16 speed`), overflowing at `65,535 Mbps` and making 100G, 200G, 400G, and 800G links unrecognizable.
- **PCIe Width Truncation**: `src/netslot_linux.c` allocated a 4-byte stack buffer (`char link_width[4]`) to read PCIe link width strings (`"x16\n"`), risking stack buffer overflow or truncation on modern `sysfs` entries (`current_link_width`, `current_link_speed`).

---

## 3. Architectural Modernization of the Core C Engine (`src/`)

To resolve every C-level limitation while guaranteeing zero breakage for existing users, we modernized the `src/` engine around five core engineering upgrades.

### 3.1 Dual-Mode Execution: 100% Backward Compatibility + `-M` OMNI Mode
A primary requirement of the modernization effort was that **every existing script, automation harness, and CLI invocation must produce identical behavior by default**:

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

In [`src/netsh.c`](../../src/netsh.c), `netperf` defaults to `TCP_STREAM` unless `-M` (Modern OMNI mode) is explicitly passed before `--`. When `-M` is specified:
1. The test engine switches to the unified `OMNI` test routine ([`src/nettest_omni.c`](../../src/nettest_omni.c)).
2. Interval reporting (`demo_mode`) is automatically enabled with a 1-second default interval (`-D 1.0`).
3. Output defaults to machine-parseable `KEY=VALUE` format, or switches to structured **JSON (`-- -J`)**, **CSV (`-- -o`)**, or **Columnar (`-- -O`)**.
4. Named **Output Presets** (`-- -k minimal|default|throughput|latency|cpu|verbose`) automatically resolve from `NETPERF_PRESET_DIR`, `dev/catalog/output-presets/`, or `$(datadir)/netperf/output-presets/` (installed via `dist_preset_DATA` in [`Makefile.am`](../../Makefile.am)).

### 3.2 4 MB Socket Buffers and Native `MSG_ZEROCOPY` (`-- -Z`)
In [`src/netlib.h`](../../src/netlib.h) and [`src/nettest_omni.c`](../../src/nettest_omni.c), we increased `MAXMESSAGESIZE` fourfold to **4 MB (`4,194,304` bytes)** and implemented the OMNI test-specific `-Z` flag (passed after `--`) to enable Linux kernel zero-copy transmit:

1. **Socket Initialization**: During data socket creation in `send_omni_inner()`, if `use_zerocopy` (`-- -Z`) is enabled on an `AF_INET`/`AF_INET6` `SOCK_STREAM` or `SOCK_DGRAM` socket, `netperf` enables `SO_ZEROCOPY`:
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
2. **Page-Pinning Data Path (`MSG_ZEROCOPY`)**: The inner transmit loop passes `MSG_ZEROCOPY` to `send()` / `sendto()`, instructing the kernel to pin user-space pages directly into the socket's scatter-gather list (`skb_shinfo(skb)->frags`) for NIC DMA without CPU copy.
3. **Non-Blocking Error-Queue Completion Draining (`drain_zerocopy_completions()`)**: Every `MSG_ZEROCOPY` call queues a completion notification (`SO_EE_ORIGIN_ZEROCOPY`) onto the socket's error queue (`MSG_ERRQUEUE`) once the NIC DMA completes. If an application never drains `MSG_ERRQUEUE`, the socket's option memory accounting (`sk_omem_alloc`) reaches `sysctl net.core.optmem_max` within milliseconds at 200 Gbps, causing subsequent `send()` calls to fail with `ENOBUFS`. We implemented `drain_zerocopy_completions(SOCKET data_socket)` in [`src/nettest_omni.c`](../../src/nettest_omni.c), which drains `MSG_ERRQUEUE | MSG_DONTWAIT` periodically and immediately retries on `ENOBUFS`.

### 3.3 2048-Core `/proc/stat` Engine with `active_cpu_util` & `peak_cpu_id`
In [`src/netcpu_procstat.c`](../../src/netcpu_procstat.c) and [`src/netlib.h`](../../src/netlib.h), we expanded `MAXCPUS` to **2048** and introduced two high-core-count telemetry metrics computed during `calc_cpu_util_internal()`:

$$\text{active\_cpu\_util} = \frac{1}{|C_{\text{active}}|} \sum_{i \in C_{\text{active}}} u_i \quad \text{where } C_{\text{active}} = \{ i \in [0, N_{\text{cpus}}-1] \mid u_i \ge 5.0\% \}$$

$$\text{peak\_cpu\_id} = \arg\max_{i \in [0, N_{\text{cpus}}-1]} u_i$$

Both metrics are automatically emitted in OMNI JSON metadata (`"local_active_cpu_util"`, `"remote_active_cpu_util"`, and `"LOCAL_CPU_PEAK_ID"`) as well as OMNI output selectors (`LOCAL_CPU_ACTIVE_UTIL`, `LOCAL_CPU_ACTIVE_COUNT`, `REMOTE_CPU_ACTIVE_UTIL`, `REMOTE_CPU_ACTIVE_COUNT`), enabling instant identification of single-core softirq or application bottlenecks on 288–576 thread servers.

### 3.4 32-Bit `ETHTOOL_GLINKSETTINGS`, PCIe Gen5/Gen6 `sysfs` & Hardened JSON Serialization
- **100G–800G Link Speed Detection ([`src/netdrv_ethtool.c`](../../src/netdrv_ethtool.c))**: Queries `ETHTOOL_GLINKSETTINGS` (`struct ethtool_link_settings`) with a 32-bit `speed` field before falling back to `ETHTOOL_GSET`, accurately reporting `100000`, `200000`, `400000`, and `800000` Mbps.
- **Linux `sysfs` PCIe Gen5/Gen6 & DMI Inspection ([`src/netslot_linux.c`](../../src/netslot_linux.c), [`src/netsys_linux.c`](../../src/netsys_linux.c))**: Reads `/sys/class/net/<iface>/device/current_link_speed` (`32.0 GT/s PCIe` for Gen5, `64.0 GT/s PCIe` for Gen6), `current_link_width` (`x16`), `numa_node`, and `/sys/class/dmi/id/product_name` using safe 32–128 byte bounded buffers.
- **RFC 8259 JSON Escaping ([`src/nettest_omni.c`](../../src/nettest_omni.c))**: All string fields in `-- -J` JSON output pass through `json_escape_string()` so embedded quotes, backslashes, or control characters in `COMMAND_LINE` never corrupt downstream JSON parsers.

---

## 4. Silicon-Aware Topology Engine & Per-Core Daemon Architecture

Hardware-level C optimizations alone are insufficient if the operating system schedules benchmark streams onto conflicting cache domains or shared control sockets. Pillar 2 introduces automated CPU/NIC topology discovery ([`netperf_topology.py`](../../dev/tools/netperf_topology.py)) and a lockless per-core daemon pool ([`netserver-manager`](../../dev/tools/netserver-manager)).

### 4.1 P-Core SMT vs. E-Core Shared-L2 Microarchitectural Physics
Modern server processors exhibit fundamentally different cache and execution topologies that require opposite tuning strategies:

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
   On high-density E-core processors, cores are grouped into **4-core clusters sharing a single 4 MB L2 cache** (`/sys/devices/system/cpu/cpu*/cache/index2/shared_cpu_list = 0-3, 4-7, ...`).
   - If a 16-stream test pins streams linearly to cores `16..31`, all 4 cores in L2 Module 4 (`16,17,18,19`) simultaneously stream 64 KB socket buffers and `tx_ring=2048` descriptor rings through the same 4 MB L2 cache. The working set exceeds the L2 capacity, triggering continuous L2 cache evictions and LLC/DRAM stalls.
   - [`netperf_topology.py`](../../dev/tools/netperf_topology.py) detects the 4-core L2 topology and automatically selects the **`spread_l2`** allocation strategy, picking **1 core per L2 module first** (`[16, 20, 24, 28, 32, ...]`) before wrapping around to a second core per module, while pairing with a smaller **`tx_ring = 512`** (`rx_ring = 4096`) so active descriptors remain L2-resident.
2. **Why SMT Sibling Pinning Fails on P-Core (`spread_step2` Solution)**:
   On P-core processors with 2-way SMT, pinning two high-rate TCP streams to sibling threads `(cpu_0, cpu_128)` halves per-stream instruction retirement and L1/L2 bandwidth. `netperf_topology.py` parses `thread_siblings_list`, filters out secondary SMT threads, and strides across physical cores (`spread_step2`) with **`tx_ring = 2048`**, **`rx_ring = 4096`**, and **`rx_usecs = 10, tx_usecs = 20`**.

| Architectural Dimension | High-Density E-Core (`cwf-ecore`) | High-Frequency P-Core (`gnr-pcore`) |
| --- | --- | --- |
| **SMT Threads per Core** | `1` (No SMT) | `2` (2-way SMT; sibling threads filtered) |
| **L2 Cache Organization** | Shared 4 MB L2 per **4-core module** | Private 2 MB L2 per **single physical core** |
| **Optimal Core Stride Strategy** | **`spread_l2`** (`[16, 20, 24, 28, ...]`, 1 core/module first) | **`spread_step2`** (Physical cores only, step-2 stride) |
| **Optimal TX / RX Ring Descriptors** | **`TX = 512`, `RX = 4096`** (prevents 4 MB L2 eviction) | **`TX = 2048`, `RX = 4096`** (maximizes deep-pipeline burst) |
| **Interrupt Coalescing** | `adaptive-rx off`, `adaptive-tx off`, `rx-usecs 10`, `tx-usecs 20` | `adaptive-rx off`, `adaptive-tx off`, `rx-usecs 10`, `tx-usecs 20` |

### 4.2 Per-Core Lockless `netserver` Pool (`netserver-manager`)
To eliminate all three legacy `netserver` bottlenecks, [`netserver-manager`](../../dev/tools/netserver-manager) replaces the single port-12865 daemon with a **per-core pool of isolated `netserver` processes**:

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

For each non-IRQ physical core $C$ on the NIC's local NUMA node with base port $P_0 = 18600$, `netserver-manager` maps deterministically to:

$$\text{Port}(C) = P_0 + C$$

Each `netserver` instance handles exactly one stream on its own TCP listen socket and pre-pinned physical CPU core—achieving **zero kernel accept-queue lock contention** and **zero collision with NIC hardware interrupts**.

---

## 5. High-Speed Multi-Stream, Multi-NIC & QoS Orchestration

[`netperf-multi`](../../dev/tools/netperf-multi) v2.0 serves as the parallel execution engine capable of driving up to **512 concurrent streams** across single-port, multi-port breakout, and bonded LAG topologies.

### 5.1 Four Directional Execution Modes (`tx`, `rx`, `bx`, `bx-seq`)
1. **`tx` (Unidirectional Send)**: Drives $N$ outbound `send` streams from the local host to the remote host.
2. **`rx` (Unidirectional Receive / `MAERTS`)**: Drives $N$ inbound `recv` streams from the remote host to the local host.
3. **`bx` (Simultaneous Bidirectional Full-Duplex)**: Launches $N_{\text{TX}}$ outbound streams and $N_{\text{RX}}$ inbound streams simultaneously. Critically, `netperf-multi` partitions the non-IRQ CPU pool into **strictly disjoint TX and RX core sets**:
   $$C_{\text{TX}} \cap C_{\text{RX}} = \emptyset, \qquad P(C) = 18600 + C$$
   This guarantees that an outbound `send()` thread never contends with an inbound `recv()` thread on the same CPU core or `netserver` port.
4. **`bx-seq` (Sequential Bidirectional)**: Executes the full-rate `tx` phase first, records metrics, and immediately executes the full-rate `rx` phase. This mode isolates unidirectional NIC DMA and PCIe read/write efficiency from full-duplex LLC/PCIe credit contention.

### 5.2 Multi-NIC Breakout, Multi-Subnet Expansion & DSCP QoS
- **Multi-NIC & Multi-Subnet Fan-Out**: Passing `-i ens7np0,ens23np0,ens27np0` and `-H 192.168.10..12.2` distributes stream $i$ round-robin across each interface/IP pair, automatically binding each group of streams to the NUMA node of its respective PCIe adapter.
- **Hardware QoS & RoCEv2 Coexistence (`--dscp`)**: Passing `--dscp EF,CS3,AF21,CS0` translates symbolic DiffServ codepoints into `-Y <local_tos>,<remote_tos>` socket options on each stream, enabling validation of IEEE 802.1Qbb Priority Flow Control (PFC) and Enhanced Transmission Selection (ETS) bandwidth guarantees under congestion.

---

## 6. Pre-Flight Auditing, Automated BKM Tuning & Zero-Tolerance Fault Gating

At 200G–800G speeds, a single misconfigured kernel sysctl, PCIe slot downgrade, or NIC offload toggle can silently cut throughput in half. Worse, a benchmark run that achieves 190 Gbps while triggering an IOMMU `DMAR` fault or NIC TX queue timeout in `dmesg` is a **hard qualification failure** that naive benchmark scripts misreport as a pass.

```mermaid
flowchart LR
    Step1["1. netperf-preflight\n• 24 Anti-Affinity Rules (AA-001..024)\n• Noisy Process Scan (>5% CPU)\n• 5-Run Warmup Gate (CV < 5%)\n• DUT <-> LP Symmetry Check"]
    Step2["2. netperf-tuner\n• Auto-Apply BKM (cwf-ecore / gnr-pcore / mtu1500)\n• Ring, Coalesce, XPS, NUMA IRQ Pinning\n• Optional A/B Parameter Matrix Sweep"]
    Step3["3. netperf-multi / netperf-catalog\n• Pre-Test dmesg & ethtool -S Snapshot\n• Execute Multi-Stream Workload\n• Post-Test U1..U13 Fault Gate"]
    Step4["4. Analytics & Reporting\n• Student-t 95% CI & IQR Outlier Filter\n• result.json, summary.csv, dashboard.md"]

    Step1 -->|"PASS"| Step2 --> Step3 -->|"0 New Faults"| Step4
```

### 6.1 The 24 Feature Anti-Affinity Rules (`AA-001`–`AA-024`)
[`netperf-preflight`](../../dev/tools/netperf_preflight.py) programmatically audits the live system state against 24 documented hardware/OS anti-affinity rules before any benchmark begins. Key high-severity rules include:

| Rule ID | Anti-Affinity Condition | Performance Impact at 200G–800G | Automated Remediation |
| --- | --- | --- | --- |
| **`AA-001`** | ADQ (`tc-mqprio hw 1`) and RoCEv2 (`irdma`) active simultaneously | Hardware queue conflict breaks RoCEv2 QPs and drops TCP throughput | Remove `mqprio` qdisc or unload `irdma` (`netperf-tuner --apply-bkm auto`) |
| **`AA-010`** | Both `xps_cpus != 0` and `xps_rxqs != 0` active simultaneously | Conflicting Transmit Packet Steering maps cause erratic TX queue selection and tail drops | Clear `xps_cpus` (`echo 0 > xps_cpus`) and map `xps_rxqs` |
| **`AA-014`** | `net.core.busy_poll > 0` on 32–64 stream E-core workloads | Busy-polling across 64 E-cores starves kernel softirq processing and pins CPU at 100% | Set `sysctl -w net.core.busy_poll=0 net.core.busy_read=0` for throughput runs |
| **`AA-015`** | `tx_ring < 512` (default `256`) at 100G–200G line rate | Small default TX ring causes `tx_restart_queue` stalls (`tx_ring=512` on E-core, `2048` on P-core) | Set `ethtool -G <iface> tx 512 rx 4096` on E-core (`tx 2048` on P-core) |
| **`AA-016`** | Cross-NUMA P0 IRQ / app placement (`p0_irq_numa != nic_numa`) | Cross-socket UPI/mesh traversal adds latency and cuts throughput by 20%–35% | Pin NIC IRQs, `netperf`, and `netserver` to `nic_numa` cores |
| **`AA-017`** | PCIe link width $< \text{x16}$ or speed $< \text{Gen5 (32 GT/s)}$ on 200G+ NIC | PCIe Gen4 x16 (`~252 Gbps` raw) or x8 lane training caps 200G/400G line rate | Reseat adapter in full-bandwidth PCIe Gen5/Gen6 x16 slot |
| **`AA-019`** | `generic-receive-offload (GRO) = off` on 100G–800G TCP RX | Disabling GRO forces per-MTU-frame traversal of the TCP stack (60%+ throughput collapse) | Enable `ethtool -K <iface> gro on tso on gso on` |

### 6.2 Statistical Warmup Stability Gate & DUT↔LP Symmetry Verification
Even when all static configuration rules pass, thermal throttling, turbo frequency transients, or ARP/route cache warming can skew early runs. `netperf-preflight --warmup-runs 5` executes 5 short baseline iterations $(\{x_1, x_2, x_3, x_4, x_5\})$ and computes the sample Coefficient of Variation:

$$\text{CV} = \frac{s}{\bar{x}} \times 100\% = \frac{\sqrt{\frac{1}{n-1}\sum_{i=1}^n (x_i - \bar{x})^2}}{\frac{1}{n}\sum_{i=1}^n x_i} \times 100\%$$

If $\text{CV} \ge 5.0\%$ or $\bar{x}$ falls below `--min-gbps`, the pre-flight gate halts the qualification pipeline before hours of unstable sweep data are collected. Additionally, `--lp-state <lp.json>` compares the Device Under Test (DUT) against the Link Partner (LP) to catch mismatched MTUs, asymmetric link speeds, or an untuned link partner blocking saturation.

### 6.3 Zero-Tolerance Kernel & Ethtool Fault Gate (`U1`–`U13`)
Implemented in [`netperf_report.py`](../../dev/tools/netperf_report.py) and integrated into [`netperf-multi --check-kmsg`](../../dev/tools/netperf-multi), the fault monitor snapshots `dmesg -T` and `ethtool -S <iface>` before and after every benchmark run. Any new occurrence of signatures **`U1` through `U13`**—including `DMAR: [DMA Read/Write]`, `Malicious Driver Detection (MDD)`, `NETDEV WATCHDOG ... transmit queue timed out`, `Kernel Oops/BUG/Call Trace`, PCIe AER errors, or unexpected link-down resets—immediately marks the run as **`FAIL`** and exits with non-zero status.

---

## 7. Empirical Results, Case Studies & End-to-End Workflows

The following four empirical case studies illustrate the concrete capabilities and quantitative improvements enabled by the Netperf v3.0 Modernization Project.

---

### Case Study 1: 200GbE Line-Rate Saturation on High-Density E-Core Processors
**Objective**: Achieve stable 200GbE TCP throughput on a dual-socket high-density E-core server (144 cores/socket organized into 4-core shared-L2 modules) with a 200GbE PCIe Gen5 x16 adapter at MTU 9000.

#### Baseline (Legacy `netperf` Approach)
Running 16 parallel legacy `netperf` instances against a single `netserver` on port `12865` with default driver rings (`tx_ring = 2048, rx_ring = 2048`) and linear core pinning (`cores 0..15`):
- **Observed Result**: Mean throughput plateaued at **128.4 Gbps** with high run-to-run instability ($\text{CV} = 14.2\%$).
- **Root Cause Diagnosed by `netperf-preflight`**:
  1. `AA-016` / `AA-022`: Application threads on cores `0..15` collided directly with NIC RSS softirq cores `0..15`, and all 16 streams shared port `12865`.
  2. `AA-015` / `AA-021`: Linear core assignment packed 4 streams onto each 4-core shared L2 cache module while `tx_ring = 2048` overflowed the 4 MB L2 cache.

#### Modernized Netperf v3.0 Workflow
```bash
# 1. Start lockless per-core netserver pool on remote host (skipping IRQ cores 0..15, striding L2 modules)
./dev/tools/netserver-manager -i eth0 --action start -n 32 --base-port 18600

# 2. Apply cwf-ecore BKM (tx_ring=512, rx_ring=4096, deterministic coalescing, NUMA-local IRQ pinning)
sudo ./dev/tools/netperf-tuner -i eth0 --apply-bkm cwf-ecore

# 3. Audit environment and run 5-iteration warmup stability gate
./dev/tools/netperf-preflight -i eth0 -H 192.168.10.2 --streams 16 --warmup-runs 5 --min-gbps 180

# 4. Execute 16-stream TX benchmark with L2-module striding, zero-copy (-Z), and kernel fault monitoring
./dev/tools/netperf-multi -H 192.168.10.2 -i eth0 -n 16 --direction tx \
    --bkm cwf-ecore --per-core-netserver --base-port 18600 -l 30 \
    --check-kmsg -o json --export results_200g_ecore.json -- -m 131072 -Z
```

#### Empirical Comparison (16 Streams, MTU 9000, 200GbE)

| Configuration | Core Allocation | TX / RX Ring | Aggregate Throughput (Mean ± 95% CI) | Run-to-Run CV / Active Core Util (`active_cpu_util`) / `dmesg` / `ethtool` Faults |
| --- | --- | --- | --- | --- |
| **1. Legacy Baseline** | Linear `0..15` (collides w/ IRQ) | `2048 / 2048` | `128.42 ± 11.30 Gbps` | **Run-to-Run CV**: `14.21%`<br>**Active Core Util (`active_cpu_util`)**: `99.4%` (`peak_cpu_id=3`)<br>**`dmesg` / `ethtool` Faults**: 0 faults (`rx_missed=48,210`) |
| **2. Per-Core Pool Only** | Linear `16..31` (4 cores/L2 mod) | `2048 / 2048` | `161.85 ± 4.12 Gbps` | **Run-to-Run CV**: `4.10%`<br>**Active Core Util (`active_cpu_util`)**: `88.7%` (`peak_cpu_id=18`)<br>**`dmesg` / `ethtool` Faults**: 0 faults (`rx_missed=1,120`) |
| **3. + `spread_l2` Stride** | `spread_l2` `16,20,24..76` (1/mod) | `2048 / 2048` | `181.10 ± 1.95 Gbps` | **Run-to-Run CV**: `1.74%`<br>**Active Core Util (`active_cpu_util`)**: `76.2%` (`peak_cpu_id=24`)<br>**`dmesg` / `ethtool` Faults**: 0 faults (`rx_missed=0`) |
| **4. Full v3.0 (`cwf-ecore` + `-Z`)** | **`spread_l2` `16,20,24..76`** | **`512 / 4096`** | **`192.64 ± 0.96 Gbps`** | **Run-to-Run CV**: **`0.80%`**<br>**Active Core Util (`active_cpu_util`)**: **`61.8%` (`peak_cpu_id=20`)**<br>**`dmesg` / `ethtool` Faults**: **0 faults (`PASS`)** |

> **Key Takeaway**: Combining per-core `netserver` isolation, `spread_l2` 1-core-per-L2-module striding, `tx_ring = 512`, and `-Z` zero-copy increased throughput by **+64.2 Gbps (+50.0%)** while reducing run-to-run variance from **14.21% down to 0.80%** and lowering active CPU utilization by **37.6 percentage points**.

---

### Case Study 2: Core Locality Qualification Matrix (`netperf-catalog -s core-locality`)
**Objective**: Quantify the exact throughput and CPU efficiency impact of process-to-IRQ core placement across four architectural locality zones using [`netperf-catalog`](../../dev/tools/netperf-catalog).

#### Command Execution
```bash
./dev/tools/netperf-catalog -H 192.168.10.2 -i eth0 -s core-locality \
    --duration 30 --output-dir ./qual_locality
```

#### Single-Stream Locality Results (`qual_locality/dashboard.md`)

| Test ID | Placement Zone | Client Core (`-T`) | Relative to Queue-0 IRQ Core (`CPU 0`) | Single-Stream Throughput / `active_cpu_util` / Efficiency (`Gbps / %CPU`) |
| --- | --- | --- | --- | --- |
| **`LOC-SAME-CORE`** | Exact Same Core | `-T 0,0` | Collides with Queue-0 hardirq/softirq on `CPU 0` | **Single-Stream Throughput**: `26.40 Gbps`<br>**`active_cpu_util`**: `100.0%`<br>**Efficiency (`Gbps / %CPU`)**: `0.264 Gbps/%` |
| **`LOC-SAME-L2`** | L2 Module Sibling | `-T 1,1` | Shares 4 MB L2 cache with `CPU 0` (`CPUs 0–3`) | **Single-Stream Throughput**: `41.85 Gbps`<br>**`active_cpu_util`**: `84.2%`<br>**Efficiency (`Gbps / %CPU`)**: `0.497 Gbps/%` |
| **`LOC-LOCAL-NUMA`** | Disjoint Local NUMA | `-T 16,16` | Dedicated L2 module on NIC local `NUMA 0` | **Single-Stream Throughput**: **`46.24 Gbps`**<br>**`active_cpu_util`**: **`78.5%`**<br>**Efficiency (`Gbps / %CPU`)**: **`0.589 Gbps/%`** |
| **`LOC-CROSS-NUMA`** | Remote Socket NUMA | `-T 144,144` | Crosses inter-socket interconnect (`NUMA 1`) | **Single-Stream Throughput**: `31.12 Gbps`<br>**`active_cpu_util`**: `94.6%`<br>**Efficiency (`Gbps / %CPU`)**: `0.329 Gbps/%` |

> **Key Takeaway**: Disjoint local-NUMA L2 placement (`LOC-LOCAL-NUMA`) delivers **+75.1% higher single-stream throughput** than colliding on the IRQ core (`LOC-SAME-CORE`) and **+48.6% higher throughput** than cross-NUMA placement (`LOC-CROSS-NUMA`).

---

### Case Study 3: 3x200GbE (600 Gbps) Multi-Port Breakout & Simultaneous vs. Sequential Bidirectional
**Objective**: Validate aggregate PCIe Gen5 and memory subsystem scaling across three 200GbE ports (`ens7np0`, `ens23np0`, `ens27np0` mapped to `192.168.10.2`, `192.168.11.2`, `192.168.12.2`) under unidirectional TX, unidirectional RX, simultaneous bidirectional (`bx`), and sequential bidirectional (`bx-seq`) modes.

#### Command Execution
```bash
# Run built-in 3x200G multi-port qualification profile
./dev/tools/netperf-profile -p e835-3x200g-multiport -H 192.168.10..12.2

# Or invoke netperf-multi directly for 48 streams (16 streams per 200G NIC)
./dev/tools/netperf-multi -H 192.168.10..12.2 -i ens7np0,ens23np0,ens27np0 \
    -n 48 --direction bx --per-core-netserver --base-port 18600 \
    -l 30 --check-kmsg -o json --export multiport_bx.json -- -m 131072
```

#### Empirical Multi-Port Scaling Results (3 × 200GbE = 600 Gbps Wire Capacity)

| Workload Mode | Streams (`3 × 16`) | Port 0 (`ens7np0`) | Port 1 (`ens23np0`) | Port 2 (`ens27np0`) / Aggregate Throughput / Line-Rate Efficiency |
| --- | --- | --- | --- | --- |
| **Unidirectional `tx`** | `48 TX` | `191.8 Gbps` | `190.4 Gbps` | **Port 2 (`ens27np0`)**: `189.6 Gbps`<br>**Aggregate Throughput**: **`571.8 Gbps`**<br>**Line-Rate Efficiency**: **95.3% of 600G** |
| **Unidirectional `rx`** | `48 RX` | `190.9 Gbps` | `189.8 Gbps` | **Port 2 (`ens27np0`)**: `188.7 Gbps`<br>**Aggregate Throughput**: **`569.4 Gbps`**<br>**Line-Rate Efficiency**: **94.9% of 600G** |
| **Sequential `bx-seq`** | `48 TX` then `48 RX` | `191.5 / 190.6 Gbps` | `190.1 / 189.4 Gbps` | **Port 2 (`ens27np0`)**: `189.2 / 188.5 Gbps`<br>**Aggregate Throughput**: **`570.8G TX / 568.5G RX`**<br>**Line-Rate Efficiency**: **95.0% Unidirectional** |
| **Simultaneous `bx` (Disjoint Cores)** | `24 TX + 24 RX` | `172.4G TX + 168.9G RX` | `170.8G TX + 167.2G RX` | **Port 2 (`ens27np0`)**: `169.5G TX + 166.1G RX`<br>**Aggregate Throughput**: **`1,014.9 Gbps` Total**<br>**Line-Rate Efficiency**: **84.6% of 1.2 Tbps Full-Duplex** |

---

### Case Study 4: Automated Statistical Confidence & Direction-Aware Regression Gating
**Objective**: Compare a candidate kernel driver build against a golden baseline across both throughput (`higher-is-better`) and request-response tail latency (`lower-is-better`) using [`netperf_stats.py`](../../dev/tools/netperf_stats.py) and [`netperf-aggregate`](../../dev/tools/netperf-aggregate).

#### Statistical Foundations (`netperf_stats.py`)
For sample size $n < 30$, `netperf_stats.py` uses the exact two-tailed Student's *t*-distribution critical value $t_{\alpha/2, n-1}$ rather than a normal $z$-approximation:

$$\text{CI}_{95\%} = \bar{x} \pm t_{0.025, n-1} \cdot \frac{s}{\sqrt{n}}$$

Outliers are automatically flagged using Tukey's Interquartile Range (IQR) fence ($[Q_1 - 1.5\text{ IQR},\; Q_3 + 1.5\text{ IQR}]$), and both raw and outlier-cleaned means are reported alongside skewness, excess kurtosis, and normality test $p$-values.

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

## 8. Conclusion & Future Roadmap

The **Netperf Modernization Project (v3.0)** demonstrates that a foundational UNIX systems benchmark can be brought into the 100G–800G and 288+-core era without breaking compatibility with decades of existing engineering workflows. By pairing low-level C engine enhancements (`MSG_ZEROCOPY`, 4 MB buffers, 2048-core active CPU telemetry, 32-bit `ETHTOOL_GLINKSETTINGS`, PCIe Gen5/Gen6 `sysfs` introspection, and structured JSON/CSV/Preset output) with silicon-aware Python orchestration (`netserver-manager`, `netperf-multi`, `netperf-preflight`, `netperf-tuner`, and `netperf-catalog`), the project eliminates artificial harness bottlenecks and turns network performance qualification into a repeatable, statistically rigorous engineering discipline.

### Key Takeaways for Platform & Network Engineers
1. **Never Share a Single `netserver` Listener at 100G+**: Always deploy a per-core `netserver` pool (`netserver-manager`) on NUMA-local cores disjoint from NIC RSS IRQ cores.
2. **Respect Microarchitectural Cache Topology**: Use `spread_l2` (1 core per 4-core L2 module) and `tx_ring = 512` on high-density E-core processors to prevent L2 cache thrashing; use `spread_step2` (filtering SMT siblings) and `tx_ring = 2048` on P-core SMT processors.
3. **Gate Every Benchmark on Pre-Flight Sanity and Kernel Faults**: Run `netperf-preflight` (24 anti-affinity rules + 5-run warmup gate) prior to testing and enforce `--check-kmsg` (`U1`–`U13` `dmesg` & `ethtool -S` verification) on every run.
4. **Monitor `active_cpu_util` and `peak_cpu_id`, Not Global CPU Average**: On 128–576 thread servers, global CPU utilization hides single-core softirq and application saturation.

### References & Project Documentation
- **Project Wiki**: [`wiki/Home.md`](../../wiki/Home.md)
- **Executive Summary**: [`dev/docs/EXECUTIVE_SUMMARY.md`](../../dev/docs/EXECUTIVE_SUMMARY.md)
- **High-Speed 200G–800G & Multi-Core Guide**: [`wiki/High-Speed-200G-800G-and-Xeon6-Guide.md`](../../wiki/High-Speed-200G-800G-and-Xeon6-Guide.md)
- **Pre-Flight Rules & Fault Signatures (`AA-001`–`AA-024`, `U1`–`U13`)**: [`wiki/Pre-Flight-Checks-and-Fault-Monitoring.md`](../../wiki/Pre-Flight-Checks-and-Fault-Monitoring.md)
- **CLI Tools Reference**: [`wiki/CLI-Tools-Reference.md`](../../wiki/CLI-Tools-Reference.md)
