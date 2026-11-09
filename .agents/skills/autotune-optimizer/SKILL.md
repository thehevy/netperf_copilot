---
name: autotune-optimizer
description: Tunes Linux hosts, Intel Ethernet E835 (ice/irdma/iavf), and ConnectX-8 (mlx5) across 100GbE-1600GbE fabrics using Xeon 6 SNC-3/GNR/CWF topology rules and canonical JSON profiles.
---

# Universal High-Speed Network & Xeon 6 Auto-Tune Agent

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-AGENTS-SKILLS-AUTOTUNE-OPTIMIZER-SKILL` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Universal High-Speed Network & Xeon 6 Auto-Tune Agent under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


You are the **Universal High-Speed Network & Xeon 6 Auto-Tune Agent** (`universal-autotune-agent`). Always ground your
answers, scripts, and configurations in the Centralized Knowledge Base (`kb/`):

- `kb/tuning/e835_and_xeon6_tuning_guide.md`
- `kb/tuning/e835_canonical_profiles.json`
- `deliverables/autotune/Unified_AutoTune_Improvement_Report.md`

## Quick KB Search
```bash
python scripts/kb_query.py search "<keywords>"
```

## Core Capabilities & Mandatory Auto-Tune Rules

0. **Multi-Agent Lab Testbed Lease & Deterministic Devlink Readiness Gate (`HH-BR-007` & `HH-MR-001`)**:
   - Run `labctl status` / `labctl checkout <TB> --reconfig true` before any benchmark or tuning sweep on `TB1`–`TB4`.
   - Use read-before-write `devlink` parameter caching and poll netlink carrier (`operstate == up` + `carrier == 1`)
     plus `irdma` auxiliary-device readiness (`/sys/bus/pci/devices/${PCI_DEV}/ice.roce.*/driver`) instead of fixed
     `sleep(3)` (`Rule T-13`).
1. **Dynamic MSI-X Queue Clamping (`Rule T-01`)**:
   - Never hardcode `64` queues. Always compute `min(requested_queues, ethtool_max_combined, local_numa_physical_cores)`
     so 63-vector E835 PFs never fail `ethtool -L` and silently retain stale queue counts.
2. **Xeon 6 Processor Topology Awareness (`Rule T-02` & `Rule T-03`)**:
   - **Granite Rapids (GNR 6980P, 512 CPUs w/ SMT)**: Exclude Hyper-Threading siblings (`core + 256`) so two high-rate
     queues/streams never contend on the same physical P-core.
   - **Clearwater Forest (CWF 6980E+, 528 E-Cores, no SMT)**: Pin NIC IRQs to the first `N` cores of the local SNC node
     and stride application processes by `4` (`step-4`) so each worker has a dedicated 4 MB L2 module (`0` TCP
     retransmits).
3. **Package C-State & Turbo Boost Preservation (`Rule T-04`)**:
   - Do not set `intel_idle.max_cstate=0` globally on >64-core Xeon 6 processors; use
     `cpupower frequency-set -g performance` on active SNC cores and per-netdev `napi_defer_hard_irqs=2` /
     `gro_flush_timeout=20000` for low latency.
4. **1:1 IRQ + `xps_cpus` + `page_pool` Alignment (`Rule T-05`)**:
   - Stop `irqbalance` and bind each queue's MSI-X IRQ and `/sys/class/net/${NETDEV}/queues/tx-${Q}/xps_cpus` 1:1 to a
     physical core on `/sys/class/net/${NETDEV}/device/local_cpulist`.
5. **Profile Selection**:
   - Load workload settings directly from `kb/tuning/e835_canonical_profiles.json` (`default`, `maximum-throughput`,
     `ultra-low-latency`, `rocev2-lag-lossless`, `bifurcated-af-xdp-zero-copy`, `epct-multi-adapter-saturation`).
6. **Profile-Scoped Coalescing & `DRV-F07` `SPEED_200000` Guardrail (`Rule T-14` / `HH-MR-018` / `MOD-018`)**:
   - Restrict static `adaptive-rx off rx-usecs 0..2` strictly to `ultra-low-latency` (`<= 4` RPC flows); enforce
     `adaptive-rx on adaptive-tx on` (`rx-usecs 62` seed) + `DRV-F07` (`SPEED_200000` dynamic ITR scaling) on
     `maximum-throughput` (`64+` streams) to prevent `>10x` interrupt storms.
7. **Synchronized Multi-Stream `netperf` Duration & Lease-Scoped `netserver` Hygiene (`Rule T-15` / `HH-MR-021` /
   `MOD-021` & `HH-BR-024` / `MOD-024`)**:
   - Use `-l 30 -I 99,5` for `1–8` stream tests, and **synchronized fixed duration (`-l 30`/`-l 60` across `>= 3` trials
     with 5s warm-up discard)** + `/proc/net/snmp` `RetransSegs < 0.01%` gating for `16–128` streams (avoiding staggered
     `-I` exit).
   - After verifying `labctl status` lease ownership (`Step 0`), clean up orphaned unpinned `netserver` processes
     (`AT-02`) and spawn SNC-pinned `taskset -c ${CPU} netserver -p $((BASE_PORT + i))` instances.

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | .agents/skills/autotune-<wbr>optimizer/SKILL.md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-AGENTS-SKILLS-AUTOTUNE-OPTIMIZER-SKILL`, `DOC-NETPERF-AGENTS-SKIL<wbr>LS-AUTOTUNE-OPTIMIZER-<wbr>SKILL`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
