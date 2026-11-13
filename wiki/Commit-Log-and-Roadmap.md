# Netperf Modernization (`netperf_copilot`) — Commit Log & Roadmap — Wiki

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-COMMITS-ROADMAP-003` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-13`
- **Target Scope**: `netperf_copilot` Central Wiki & 5-Page Repository Wiki Pack (`TEMPLATE-06`)
- **Summary**: Completed Phases 1–7 engineering milestones, live hardware validation commits, and upcoming qualification roadmap for `netperf_copilot` on **Intel® Ethernet 800 Series** (**200GbE Ethernet Controller** and **200GbE Network Adapter**) and **Intel® Xeon® 6 Processor** systems.
<!-- METADATA_HEADER_END -->

---

## 1. Completed Engineering Phases & Next-Step Roadmap

- [x] **Phase 1–2 (Core OMNI Defaults, Output Presets & Aggregator)**: Preserved default `TCP_STREAM` backwards
  compatibility while adding `-M` OMNI key-value, JSON (`-- -J`), CSV (`-- -o`), and `6` named output presets.
- [x] **Phase 3 (Multi-Stream, Profile, Orchestration & Template CLI Suite)**: Delivered `netperf-multi`,
  `netperf_stats.py`, `netperf-profile`, `netperf-orchestrate`, `netperf-monitor`, `netperf-aggregate`, and
  `netperf-template` with zero mandatory external dependencies.
- [x] **Phase 4–7 (100GbE–800GbE C Engine, Xeon 6 Topology, 24-Rule Pre-Flight & Qualification Catalog)**: Upgraded C
  engine to `4 MB` buffers, `SO_ZEROCOPY`/`MSG_ZEROCOPY` (`-Z`), `2048`-core active CPU tracking,
  `ETHTOOL_GLINKSETTINGS`,
  and PCIe/DMI `sysfs` telemetry; added `netserver-manager`, `netperf-preflight`, `netperf-tuner`, and
  `netperf-catalog`.
- [x] **Live Testbed Hardware Compilation & Sweep (`2-node Linux testbed`)**: Compiled C engine on Linux with `0`
  warnings/errors,
  validated all C and Python tools over `25GbE`/`100GbE` `802.3ad` LAG with `0` `dmesg` faults (`DMAR=0`, `MDD=0`), and
  enforced `Rules D1`–`D10` `v3.2`.
- [ ] **Next Milestone — Multi-Testbed `200GbE`/`400GbE` Automated CI Sweep
  (`2-node 200GbE testbed`–`2-node 25GbE testbed`)**: Schedule recurring
  `netperf-catalog` regression sweeps across SNC-3 P-Core and 288-core E-Core clusters with testbed automation lease
  coordination.

---

## 2. Recent Repository Commits (`3`-Column Zero-Scroll Table)

| Date & Commit SHA | Author | Commit Summary & Verification Gate |
| --- | --- | --- |
| `2026-11-09` · `baefaf4` | Engineering Team | **Live Hardware Validation Fixes (`2-node Linux testbed`)**: Quote hex `0xffffffff` TOS fields in `print_omni_json()`, wire DMI/PCIe `sysfs` into `-J`, add live LP per-core port probing in `netperf-multi`, and verify `19/19` unit + `5/5` live integration tests (`DMAR=0`). |
| `2026-11-05` · `718898f` | Engineering Team | **Executive Summary & Technical White Paper**: Add Executive Summary and 10-page Technical White Paper across `dev/docs/` and `wiki/`. |
| `2026-11-05` · `1924593` | Engineering Team | **Sanitization & Wiki Navigation**: Redact internal lab hostnames/IPs to RFC 2544 (`198.18.x.x`) and add GitHub Wiki `_Sidebar.md`. |
| `2026-11-05` · `1e0b1ef` | Engineering Team | **Phase 4–7 Remediation & 200GbE–800GbE Modernization**: Link `netdrv_ethtool.c`/nets<wbr>lot_linux.c/netsys_lin<wbr>ux.c, add `active_cpu_util` wire marshalling, and complete `AA-001`–`AA-024` pre-flight rules. |

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `wiki/Commit-Log-and-Roadmap.md` |
| **Created / Last Updated** | `2026-11-09` / `2026-11-13` |
| **Keywords / Search Tags** | `Commit Log and Roadmap`, `netperf_copilot Wiki`, `Phase 1-7 Modernization`, `Live 2-node Linux testbed Validation`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `netperf`, `netserver`, `netperf-multi`, `netperf-catalog` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-COMMITS-ROADMAP-003`, `baefaf4`, `718898f`, `1924593`, `1e0b1ef`, `D1-D10 v3.2` |
<!-- METADATA_FOOTER_END -->
