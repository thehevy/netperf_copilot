# CLI Tools Reference

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-CLI-TOOLS-REFERENCE` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for CLI Tools Reference under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


All tools are located in `dev/tools/` and require only Python 3.8+ standard library modules.

---

## 1. `netperf-multi` — Multi-Instance, Multi-Port & Directional Runner

Coordinates parallel `netperf` streams across 1 to 8+ NIC ports with Xeon 6 topology-aware CPU affinity, per-core
`netserver` port mapping, directional (`tx`, `rx` , `bx` , `bx-seq` ) orchestration, DSCP QoS marking, and `dmesg`
/`ethtool -S` fault gating.

```bash
./dev/tools/netperf-multi -H <host_or_range> -n <streams> [options] [-- <omni_args>]
```

| Flag | Description |
| --- | --- |
| `-H`, `--host` | Single IP, comma-separated list (`10.0.1.2,10.0.2.2`), or octet range (`192.168.10..17.74`) |
| `-n`, `--instances` | Number of streams per port/direction (or total streams distributed across `-i` interfaces) |
| `-t`, `--test` | Test type: `OMNI` (recommended for 100G+), `TCP_STREAM`, `TCP_MAERTS`, `TCP_RR`, `UDP_STREAM` |
| `-d`, `--direction` | `tx` (send), `rx` (maerts/receive), `bx` (simultaneous TX+RX on disjoint cores), `bx-seq` (sequential TX then RX) |
| `-i`, `--interfaces` | Comma-separated local NICs (e.g. `ens7np0,ens23np0,ens27np0`) for NUMA/core locality |
| `-Y`, `--dscp`, `--tos` | Symbolic DSCP (`EF,CS3,AF21,CS0`), `dscp:46`, or hex ToS (`0xb8`) |
| `--affinity` | Enable NUMA-local, non-IRQ physical core pinning (`-T <dut_core>[,<lp_core>]`) |
| `--layout` | `auto` (default), `spread_l2` (E-core 4-core L2 modules), `spread_step2` (P-core SMT filter), `sequential` |
| `--per-core-netserver` | Connect each flow to `-p $((base_port + lp_core))` |
| `--base-port` | Base control port for per-core `netserver` pool (default: `18600`) |
| `--lp-start-cpu` | Minimum starting CPU on Load Partner (e.g. `0` or `43`) |
| `--check-kmsg` | Capture `dmesg -T` and `ethtool -S` before/after the run and fail on `U1`–`U13` faults |
| `--export <file.json>` | Export per-instance and aggregated TX/RX/BX results + fault scan to JSON |

---

## 2. `netserver-manager` — Per-Core Pinned Netserver Pool Manager

Plans, starts, stops, and audits per-core `numactl`-pinned `netserver` pools locally or over SSH.

```bash
# Plan per-core pool for interface ens801f0np0
./dev/tools/netserver-manager --plan -i ens801f0np0 --base-port 18600 --count 32

# Start pool on remote Load Partner via SSH
./dev/tools/netserver-manager --start -H 192.168.10.2 -i ens801f0np0 --base-port 18600 --count 32

# Audit running pool (checks for unpinned PIDs or IRQ core collisions)
./dev/tools/netserver-manager --verify -H 192.168.10.2 -i ens801f0np0

# Stop all netserver instances
./dev/tools/netserver-manager --stop -H 192.168.10.2
```

---

## 3. `netperf-preflight` — 24-Rule Hardware & Driver Pre-Flight Checker

Validates platform state, noisy background processes (`vscode`, `kipmi0` , `irqbalance` , `pmlogger` ), PCIe link
effective bandwidth vs. NIC link speed, P0 IRQ NUMA locality, and all 24 Intel E835 feature anti-affinity rules
(`AA-001`–`AA-024`).

```bash
# Run live pre-flight check on ens801f0np0
./dev/tools/netperf-preflight -i ens801f0np0

# Emit JSON report
./dev/tools/netperf-preflight -i ens801f0np0 --json

# List all 24 anti-affinity rules
./dev/tools/netperf-preflight -i ens801f0np0 --list-rules
```

---

## 4. `netperf-tuner` — BKM Tuner & A/B Parameter Sweep Engine

Applies validated Intel Xeon 6 + `ice` driver Best Known Methods or runs automated A/B parameter sweeps with statistical
significance testing and automatic rollback.

```bash
# Preview or apply BKM profile ({auto, cwf-ecore, gnr-pcore, mtu1500})
./dev/tools/netperf-tuner -i ens801f0np0 --apply-bkm auto --dry-run
sudo ./dev/tools/netperf-tuner -i ens801f0np0 --apply-bkm cwf-ecore

# Sweep TX descriptor ring sizes and lock in the lowest-CV winner
sudo ./dev/tools/netperf-tuner -i ens801f0np0 --sweep tx_ring --values 256,512,1024,2048 --json
```

Supported `--sweep` knobs: `tx_ring` , `rx_ring` , `rx_usecs` , `tx_usecs` , `channels` , `mtu` , `congestion_control` ,
`tx_sched_layers` .

---

## 5. `netperf-catalog` — Qualification Test Matrix Generator & Runner

Generates and executes the 4 standardized 200G–800G qualification suites and writes `result.json` , `summary.csv` , and
`dashboard.md` .

```bash
# Preview the 42-case flow-scaling suite
./dev/tools/netperf-catalog --suite flow-scaling -H 192.168.10.2 -i ens801f0np0 --dry-run

# Generate result.json, summary.csv, and dashboard.md in ./qual_out/
./dev/tools/netperf-catalog --suite core-locality -H 192.168.10.2 -i ens801f0np0 \
    --output-dir ./qual_out --dry-run
```

---

## 6. `netperf-profile` — YAML Profile Test Runner

Loads and executes built-in or custom YAML test profiles (works with or without `PyYAML` installed).

```bash
# List all 15 built-in profiles
./dev/tools/netperf-profile --list

# Validate and dry-run a 200GbE Clearwater Forest profile
./dev/tools/netperf-profile -p e835-200g-cwf-ecore -H 192.168.10.2 --dry-run

# Run a profile and export results
./dev/tools/netperf-profile -p e835-200g-gnr-pcore -H 192.168.10.2 --export gnr_results.json
```

---

## 7. `netperf-orchestrate` — Multi-Host SSH & RoCEv2 Co-Orchestrator

Manages multi-host test inventories (`hosts.yaml`), deploys/starts per-core `netserver` pools across servers, optionally
starts concurrent RoCEv2 (`ib_write_bw`) traffic, and runs client-to-server matrix tests.

```bash
# Check SSH connectivity across all hosts in inventory
./dev/tools/netperf-orchestrate --hosts dev/examples/hosts.yaml --check

# Start per-core pinned netserver pool on all server hosts
./dev/tools/netperf-orchestrate --hosts dev/examples/hosts.yaml --start --per-core-netserver --base-port 18600

# Run matrix tests with concurrent RoCEv2 coexistence traffic
./dev/tools/netperf-orchestrate --hosts dev/examples/hosts.yaml --rdma-coexist \
    --rdma-device irdma0 -- -d stream -l 30 -m 65536 -J
```

---

## 8. `netperf-monitor`, `netperf_stats.py`, `netperf-aggregate`, `netperf-template`

- **`netperf-monitor`**: Live ANSI terminal dashboard with sparklines and ETA progress bars.
  ```bash
  ./dev/tools/netperf-monitor -d 60 -H 192.168.10.2 -- -d send
  ./dev/tools/netperf-monitor --follow test.log
  ```
- **`netperf_stats.py`**: Calculates mean, median, standard deviation, CV%, 95%/99% confidence intervals, IQR/Z-score
  outliers, and ASCII histograms/boxplots.
  ```bash
  python3 ./dev/tools/netperf_stats.py results.txt
  ```
- **`netperf-aggregate`**: Aggregates multiple JSON/CSV/KEYVAL result files and compares baseline vs. current runs
  (automatically treating lower latency/CPU as improvements and higher throughput as improvements).
  ```bash
  ./dev/tools/netperf-aggregate baseline.json current.json --compare
  ```
- **`netperf-template`**: Renders JSON test results into `markdown-report` , `html-report` , `csv-export` ,
  `latex-table` , or `json-summary` (using Jinja2 or built-in stdlib engine).
  ```bash
  ./dev/tools/netperf-template -t markdown-report results.json -o report.md
  ```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `wiki/CLI-Tools-Reference.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-CLI-TOOLS-REFERENCE`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
