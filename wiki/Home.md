# Netperf Modernized Fork Wiki

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-HOME` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Netperf Modernized Fork Wiki under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


Welcome to the official Wiki for **`netperf_copilot`** — the modernized, high-speed (`10GbE` to `800GbE`) and
multi-core server (**Intel® Xeon® 6 Processor** P-Core SMT & E-Core Shared-L2) ready fork of the classic `netperf`
network performance benchmark for **Intel® Ethernet 800 Series** (**200GbE Ethernet Controller** / **Intel®
Ethernet Network Adapter 200GbE**) fabrics.

| Field | Value |
| --- | --- |
| **Repository** | [github.com/netperf_copilot](https://github.com/thehevy/netperf_copilot) |
| **Wiki** | [github.com/wiki](https://github.com/thehevy/netperf_copilot/wiki) |
| **Latest Commit** | `baefaf4` (`master`, Phases 1–7 Complete) |
| **Validation Status** | `49/49` automated & live hardware checks passing (`0` `dmesg` faults) |

### Quick Share Block

```text
Repo: https://github.com/thehevy/netperf_copilot
Wiki: https://github.com/thehevy/netperf_copilot/wiki
Clone: git clone https://github.com/thehevy/netperf_copilot.git
```

---

## 🌟 Highlights at a Glance

- **100% Backwards Compatible**: Running `netperf -H <host>` without `-M` executes the classic `TCP_STREAM` columnar
  test so existing scripts never break.
- **Modern OMNI Mode (`-M`)**: Enables structured `KEYVAL` (default with `-M` ), `JSON` (`-- -J`), `CSV` (`-- -o`), and
  `HUMAN` (`-- -O`) output, plus named output presets (`minimal`, `default` , `throughput` , `latency` , `cpu` ,
  `verbose` ).
- **100GbE–800GbE Core C Engine Upgrades (`src/`)**:
  - `MAXCPUS` scaled to **2048** cores with `/proc/stat` softirq/active-CPU tracking (`active_cpu_util`, `peak_cpu_id`).
  - `MAXMESSAGESIZE` raised from 1 MB to **4 MB** (`4194304` bytes) for high-BDP and zero-copy transfers.
  - Native **`SO_ZEROCOPY` / `MSG_ZEROCOPY`** (`-Z`) support with automatic `MSG_ERRQUEUE` completion draining.
  - Direct Linux `ETHTOOL_GLINKSETTINGS` (100GbE/200GbE/400GbE/800GbE link speed, driver, firmware) and sysfs PCIe
    Gen5/Gen6
    (`32.0 GT/s`, `64.0 GT/s` , `x16` , NUMA node) telemetry.
- **Production Python Tooling (`dev/tools/`)**:
  - Zero mandatory external dependencies (pure Python 3 stdlib fallbacks for YAML, Jinja2, and SSH).
  - Topology-aware multi-flow runner (`netperf-multi`), per-core `netserver` pool manager (`netserver-manager`), 24-rule
    pre-flight checker (`netperf-preflight`), automated BKM tuner & A/B sweep engine (`netperf-tuner`), 4-suite
    qualification catalog (`netperf-catalog`), YAML profile runner (`netperf-profile`), multi-host SSH orchestrator
    (`netperf-orchestrate`), live ANSI dashboard (`netperf-monitor`), statistical analyzer (`netperf_stats.py`), result
    aggregator (`netperf-aggregate`), and report template engine (`netperf-template`).

---

## 📖 Wiki Navigation

1. **[Home](https://github.com/thehevy/netperf_copilot/wiki)** — Project overview, architecture diagram, and quick links
2. **[Architecture and Insights](https://github.com/thehevy/netperf_copilot/wiki/Architecture-and-Insights)** — Core
   architecture, mathematical insights, and 49/49
   live validation accounting
3. **[Commit Log and Roadmap](https://github.com/thehevy/netperf_copilot/wiki/Commit-Log-and-Roadmap)** — Chronological
   commit log (`baefaf4`), live 2-node Linux
   testbed fixes, and
   Phases 1–8 engineering roadmap
4. **[Executive Summary](https://github.com/thehevy/netperf_copilot/wiki/Executive-Summary)** — Strategic overview of
   the modernization project, the four engineering
   pillars, and quantified before-vs-after impact
5. **[Technical White Paper](https://github.com/thehevy/netperf_copilot/wiki/Technical-White-Paper)** — In-depth 10-page
   architectural white paper explaining why
   `netperf` modernization is essential at 100GbE–800GbE, mathematical models, and 4 empirical case studies
6. **[Getting Started & Installation](https://github.com/thehevy/netperf_copilot/wiki/Getting-Started-and-Installation)**
   — Building `netperf`, configure options,
   and installing `dev/tools/`
7. **[Core Engine & OMNI Guide](https://github.com/thehevy/netperf_copilot/wiki/Core-Engine-and-OMNI-Guide)** — Using
   `-M` OMNI mode, JSON/CSV/KEYVAL formats, output
   presets, and `-Z` zero-copy
8. **[High-Speed 200GbE–800GbE & Multi-Core Guide](https://github.com/thehevy/netperf_copilot/wiki/High-Speed-200GbE-800GbE-and-Xeon6-Guide)**
   — P-Core SMT (`spread_step2`)
   vs. E-Core Shared-L2 (`spread_l2`) topology layout, per-core `netserver-manager`, and driver tuning
9. **[CLI Tools Reference](https://github.com/thehevy/netperf_copilot/wiki/CLI-Tools-Reference)** — Complete reference
   for all 11 tools in `dev/tools/`
10. **[Test Profiles & Qualification Catalog](https://github.com/thehevy/netperf_copilot/wiki/Test-Profiles-and-Qualification-Catalog)**
    — All 15 built-in YAML
    profiles and the 4 standardized qualification suites (`flow-scaling`, `core-locality`, `ring-coalesce-matrix`,
    `lag-failover-qos`)
11. **[Pre-Flight Checks & Fault Monitoring](https://github.com/thehevy/netperf_copilot/wiki/Pre-Flight-Checks-and-Fault-Monitoring)**
    — All 24 anti-affinity rules
    (`AA-001`–`AA-024`), `U1`–`U13` `dmesg`/`ethtool -S` fault gates, and AI-Driven Validation `result.json` schema

---

## 🏗️ Modernization Architecture

```mermaid
flowchart TD
    subgraph UserCLI["User / Automation CLI (dev/tools/)"]
        Preflight["netperf-preflight\n(24 Anti-Affinity Rules & Warmup Gate)"]
        Tuner["netperf-tuner\n(ecore / pcore / mtu1500 BKM + A/B Sweep)"]
        PoolMgr["netserver-manager\n(Per-Core Pinned Pool 18600..18663)"]
        Catalog["netperf-catalog & netperf-profile\n(4 Qualification Suites + 15 YAML Profiles)"]
        Multi["netperf-multi & netperf-orchestrate\n(TX / RX / BX, Multi-NIC, Multi-Subnet, DSCP QoS)"]
        Report["netperf_report.py / netperf-aggregate / netperf-template\n(result.json, summary.csv, dashboard.md, U1-U13 kmsg Gate)"]
    end

    subgraph CoreEngine["Core C Engine (src/)"]
        Netperf["netperf (-M OMNI / Legacy TCP_STREAM)\n• 4MB MAXMESSAGESIZE & -Z MSG_ZEROCOPY\n• 2048-Core /proc/stat Active & Peak CPU\n• ETHTOOL_GLINKSETTINGS & PCIe Gen5/Gen6 sysfs"]
        Netserver["netserver (-p 18600+core)\n• NUMA-Local & Non-IRQ Core Pinned"]
    end

    Preflight --> Tuner
    Tuner --> PoolMgr
    PoolMgr --> Catalog
    Catalog --> Multi
    Multi --> Netperf
    Netperf <-->|"100GbE / 200GbE / 400GbE / 800GbE Data Socket"| Netserver
    Multi --> Report
```

---

## ⚡ 60-Second Quick Start

```bash
# 1. Build optimized binaries
./dev/scripts/build.sh --type optimized

# 2. Run pre-flight hardware/driver check on your high-speed NIC
./dev/tools/netperf-preflight -i eth0

# 3. Apply driver BKM tuning (or --dry-run to preview)
./dev/tools/netperf-tuner -i eth0 --apply-bkm auto --dry-run

# 4. Start per-core pinned netserver pool on the Link Partner (LP)
./dev/tools/netserver-manager -i eth0 --action start -n 32 --base-port 18600

# 5. Run 16-stream bidirectional (16 TX + 16 RX) 200GbE test with dmesg fault gate
./dev/tools/netperf-multi -H 192.168.10.2 -i eth0 -t OMNI \
    --direction bx -n 16 -l 30 --affinity --per-core-netserver \
    --base-port 18600 --check-kmsg -o json --export bx_16flows.json -- -m 65536 -D
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `wiki/Home.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet 200GbE`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-HOME`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
