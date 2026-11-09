---
description: Mandatory dmesg DMAR, MDD, and kernel fault zero-tolerance monitoring gate on all Linux test hosts
trigger: always_on
---

# Mandatory `dmesg` Error & Hardware Fault Monitoring Rule

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-AGENTS-RULES-DMESG-MONITORING` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Mandatory `dmesg` Error & Hardware Fault Monitoring Rule under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


Whenever you load/reload a kernel module, configure NIC/RDMA/bond/subfunction state, start a daemon, or execute any test
or benchmark on a Linux host:

1. **Pre-Test Baseline**: Capture the baseline `dmesg -T` line count before the test
   (`DMESG_BASELINE=$(dmesg | wc -l)`).
2. **Post-Test & Post-Daemon Check**: Immediately after the test (and 5-10 seconds after starting any background
   daemon), run:
   ```bash
   dmesg -T | tail -n 40
   dmesg -T | grep -iE "DMAR|fault|DRHD|Oops|BUG:|WARNING:|Call Trace|MDD|Malicious|hw_error|reset|tx_timeout" | tail -n 20
   ```
3. **Zero-Tolerance Pass Gate**: Never report a test or configuration as passing if any new `DMAR` fault, `MDD` event,
   kernel `Oops`/`BUG`/`WARNING`/`Call Trace`, or unexpected hardware reset appeared in `dmesg`. Refer to
   `kb/validation/dmesg_dmar_mdd_zero_tolerance_gate.md` for root-cause remediation.

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `.agents/rules/dmesg-monitoring.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-AGENTS-RULES-DMESG-MONITORING`, `DOC-NETPERF-AGENTS-RULE<wbr>S-DMESG-MONITORING`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
