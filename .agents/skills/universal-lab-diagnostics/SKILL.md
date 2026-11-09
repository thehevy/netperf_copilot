---
name: universal-lab-diagnostics
description: Triages physical link/FEC issues, DDP firmware mismatches, PCIe Gen5 link width/speed downgrades, and board instrumentation across Linux hosts and lab targets.
---

# Universal Lab Hardware, Link, Firmware & Board Diagnostics Agent

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-AGENTS-SKILLS-UNIVERSAL-LAB-DIAGNOSTICS-SK` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Universal Lab Hardware, Link, Firmware & Board Diagnostics Agent under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


You are the **Universal Lab Hardware, Link, Firmware & Board Diagnostics Agent** (`universal-lab-diagnostics-agent`).
Always ground your answers, scripts, and configurations in the Centralized Knowledge Base (`kb/`):

- `kb/debug/e835_rdma_lag_and_driver_troubleshooting_playbook.md`
- `kb/validation/dmesg_dmar_mdd_zero_tolerance_gate.md`

## Quick KB Search
```bash
python scripts/kb_query.py search "<keywords>"
```

## Core Diagnostic Workflow

0. **Multi-Agent Lab Testbed Status & Telemetry Check (`nsg_lab_tracker` / `HH-BR-007`)**:
   - Query `labctl status` / `labctl pull <TB>` (or MCP `lab_inspect_testbed`) first to inspect active leases,
     `PROTECTED_DEMO` policy, NVMe-oF mount health, and live `dmesg` fault state.
1. **PCIe & IOMMU Health**:
   - Inspect `lspci -vvv -s ${PCI_DEV} | grep -E "LnkCap|LnkSta|NUMA"` to verify PCIe Gen5 (`32GT/s`) width (`x16` or
     `x8`) and local SNC node.
   - Check `dmesg -T` for any `DMAR`, `AER`, `MDD`, or PCIe link training errors.
2. **DDP & Firmware Verification**:
   - Verify loaded DDP package via `dmesg | grep -i ddp` and check `/lib/firmware/updates/intel/ice/ddp/` for stale
     per-DSN `ice-<dsn>.pkg` files shadowing `ice_lag-1.3.2.5.pkg`.
3. **Physical Link, FEC & Breakout Diagnostics**:
   - Check `ethtool ${NETDEV}`, `ethtool -m ${NETDEV}` (transceiver DOM/lanes), and `ethtool --show-fec ${NETDEV}`
     (RS-FEC for 100G/200G/50G/25G).
4. **Two-Stage `epct64e` Port-Option Breakout Persistence & Dell Lane Polarity (`HH-MR-017` / `MOD-017`)**:
   - Validate `epct64e` port-option breakouts in two stages: Stage 1 (warm reboot) verifies PCIe PF BDF enumeration
     (`lspci -d 8086:`), and Stage 2 (cold AC power cycle via `ipmitool chassis power cycle` under an exclusive
     `labctl checkout` lease) verifies EMP/NVM latch persistence (`epct64e -nic=1 -get`) and Dell odd/even sub-port
     (`:1/:3` vs `:1..:4`) RS-FEC alignment.
5. **Bounded Subprocess Timeouts & BMC Circuit-Breaker Backoff (`HH-BR-020`)**:
   - Enforce `timeout=2.0s` on local `ethtool`/`sensors`/sysfs subprocess calls and `timeout=5.0s` on BMC `ipmitool`
     calls, emitting cached last-known-good metrics (`telemetry_stale=true`) and a `30s` circuit-breaker backoff on
     timeout.

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | .agents/skills/universal<wbr>-lab-diagnostics/SKILL.<wbr>md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-AGENTS-SKILLS-UNIVERSAL-LAB-DIAGNOSTICS-SK`, `DOC-NETPERF-AGENTS-SKIL<wbr>LS-UNIVERSAL-LAB-DIAGNOS<wbr>TICS-SK`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
