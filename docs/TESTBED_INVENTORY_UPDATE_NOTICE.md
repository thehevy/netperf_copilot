# Authoritative `lab_tracker` Testbed Inventory Update Notice (`netperf_copilot`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TESTBED-NOTICE-NETPERF-COPILOT` | **Version**: `v1.0` | **Status**: `Active Engineering Advisory`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot | Shared Hardware Testbeds (TB1, TB2, TB3, TB4)`
- **Summary**: Notification of corrected testbed names, logical CPU counts, and Intel® Ethernet 800 Series adapter inventories in nsg_lab_tracker across TB1 through TB5.
<!-- METADATA_HEADER_END -->

---

## 1. Why You Are Receiving This Notice

Live hardware discovery in **Intel® Ethernet Lab Tracker (`nsg_lab_tracker`)** (`efb014c`, `d0c0e44`, and `c834fc1`)
identified stale testbed names, CPU core/thread counts, and network adapter inventories in earlier configuration
templates and shared schemas.

Because **`netperf_copilot`** references testbeds **`TB1, TB2, TB3, TB4`**, review and update the affected
files listed in Section 2 to match the authoritative hardware inventory in Section 3.

---

## 2. Specific Impact & Required Action in `netperf_copilot`

| Field | Details |
| --- | --- |
| **Repository** | `netperf_copilot` |
| **Testbeds Referenced** | `TB1, TB2, TB3, TB4` |
| **Files to Review / Update** | README.md, benchmarks/results/TESTB<wbr>ED_157_153_BENCHMARK_REP<wbr>ORT.md, wiki/ |
| **Required Remediation** | Update TB3 (198.18.84.157/.153) benchmark report headers from '288 E-cores / 256 threads' to '528 CPUs (2x264C/1T) on Xeon 6980E+ / 512 CPUs (2x128C/2T) on Xeon 6980P' with 5x E835-CC (19 ports). |

---

## 3. Authoritative `TB1`–`TB5` Hardware Inventory (`nsg_lab_tracker` Single Source of Truth)

| Testbed ID & Official Name | Authoritative CPU / NUMA & Network Adapter Inventory | Stale Values to Replace | Stale Values to Replace |
| --- | --- | --- | --- |
| **`TB1`** (`tb1-e835-b2b`)<br>**Testbed #1 — Xeon 6 GNR-AP (6960P) E835-CC 2x100GbE Direct B2B**<br>S1: 198.18.84.106 (tb1-gnr-node-1) | S2: 198.18.84.107 (tb1-gnr-node-2) | Switch: null (Direct B2B) | **CPU**: Dual-Socket Intel® Xeon® 6960P (Granite Rapids-AP GNR-AP, 288 CPUs — 2x72C/2T, 2 NUMA nodes)<br>**Adapters**: S1: 2x Intel® Ethernet Network Adapter E835-CCDA2 (2x100GbE QSFP, 0000:2a:00.0/.1 ens3f0np0/f1np1 + 0000:6e:00.0/.1 ens9f0np0/f1np1) |
| **`TB2`** (`tb2-e835-dell`)<br>**Testbed #2 — Xeon SPR (8480+) 4x E835-CC (2x100GbE + 20x25GbE) + Dell Z9264F-ON Switch**<br>S1: 198.18.84.118 (tb2-spr-node-1) | S2: 198.18.84.120 (tb2-spr-node-2) | Switch: Dell Networking Z9264F-ON (OS10) (198.18.84.178) | **CPU**: Dual-Socket Intel® Xeon® Platinum 8480+ (Sapphire Rapids SPR, 224 CPUs — 2x56C/2T, 2 NUMA nodes)<br>**Adapters**: 4x Intel® Ethernet Network Adapter E835-CC (22 ports/host: 2x100GbE + 20x25GbE — 0000:1f:00.0..7 8x25G ens1f0np0..f7np7, 0000:32:00.0..3 4x25G, 0000:84:00.0..7 8x25G ens104f0np0..f7np7, 0000:ac:00.0/.1 S1 2x100G ens4f0np0/f1np1, 0000:c0:00.0/.1 S2 2x100G ens5f0np0/f1np1; bonds bond1..bond5) |
| **`TB3`** (`tb3-cwf-gnrap-e835-b2b`)<br>**Testbed #3 — Xeon 6 CWF (6980E+) & GNR-AP (6980P) 5x E835-CC Direct B2B**<br>S1: 198.18.84.157 (tb3-cwf-node-1) | S2: 198.18.84.153 (tb3-gnrap-node-2) | Switch: null (Direct B2B) | **CPU**: S1: Dual-Socket Intel® Xeon® 6980E+ (Clearwater Forest CWF, 528 CPUs — 2x264C/1T, 2 NUMA nodes) |
| **`TB4`** (`tb4-ocp-arista`)<br>**Testbed #4 — Xeon 6 CWF (6960E+) E835 8x25GbE + 2x100GbE + Arista 7060CX2**<br>S1: 198.18.176.73 (tb4-cwf-target-1) | S2: 198.18.176.74 (tb4-cwf-initiator-2) | Switch: Arista 7060CX2-32S (EOS) (198.18.176.75) | **CPU**: Dual-Socket Intel® Xeon® 6960E+ (Clearwater Forest CWF, 288 CPUs — 2x144C/1T, 6 NUMA nodes SNC-3)<br>**Adapters**: Intel® Ethernet Network Adapter E835 Dual-PEP (8x25GbE, 0000:3b:00.0..7 ens4047f0np0..f7np7, bond40..43) + E835-CC (2x100GbE Direct B2B, 0000:c9:00.0/.1 ens513f0np0/f1np1) |
| **`TB5`** (`tb5-spr-e835`)<br>**Testbed #5 — Xeon SPR 8480+ 3x E835-CC 8x25GbE Breakout**<br>S1: 198.18.84.115 (tb5-spr-node-1) | S2: 198.18.84.116 (tb5-spr-node-2) | Switch: null | **CPU**: Dual-Socket Intel® Xeon® Platinum 8480+ (Sapphire Rapids SPR, 224 CPUs — 2x56C/2T, 2 NUMA nodes)<br>**Adapters**: 3x Intel® Ethernet Network Adapter E835-CC (8x25GbE Breakout = 24 ports/host: 0000:45:00.0..7 ens2f0np0..f7np7, 0000:84:00.0..7 ens104f0np0..f7np7, 0000:c0:00.0..7 ens5f0np0..f7np7; bonds bond40..bond43) |

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | docs/TESTBED_INVENTORY_<wbr>UPDATE_NOTICE.md |
| **Document ID** | `DOC-TESTBED-NOTICE-NETPERF-COPILOT` |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | netperf_copilot, Testbed Inventory Update, nsg_lab_tracker, TB1, TB2, TB3, TB4, TB5, E835-CC |
| **Drivers & Subsystems** | ice, irdma, iavf, bonding, lab_tracker, auto_tune |
| **Validation / Patch IDs** | `DOC-TESTBED-NOTICE-NETPERF-COPILOT` |
<!-- METADATA_FOOTER_END -->
