# Intel® Engineering Patch, Architecture & A/B Hardware Validation Report Template

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-ENG-AB-REPORT-001` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Executive Engineering Reports, Kernel Patch Audits, and Multi-Testbed A/B Validation Reports
- **Summary**: Canonical Intel® technical report template for **Intel® Ethernet 800 Series** (**Intel® Ethernet Controller E835** and **Intel® Ethernet Network Adapter E835-CC**) and **Intel® Xeon® 6 Processor** validation reports under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!IMPORTANT]
> **Mandatory Authoring Rules (`D1`–`D10` v3.2)**:
>
> 1. **Wrap Lines at `<= 120` Characters (`MD013` / `D5-WRAP`)**: Wrap all prose, numbered or bulleted lists, and
>    blockquotes at `<= 120` characters with exact list continuation indentation (`MD007`) and blank lines around lists
>    (`MD032`).
> 2. **Zero-Scroll Tables (`D5-COLS` `<= 3–4` Cols & `D5-TOKEN` `<= 40` Chars)**: Keep report tables to `3` columns (`4`
>    columns max for A/B testbed matrices). Stack secondary fields vertically with `<br>`, use short file basenames for
>    link labels (`[0001-snc-numa.patch](path/to/patch)`), and split long identifiers at `<wbr>` boundaries (`<= 24`
>    chars per segment).
> 3. **Synchronize Header & Footer `Document ID` (`D7-ID-MATCH`)**: The `Document ID` in `METADATA_HEADER_START..END`
>    must appear verbatim (never truncated) in the `Validation / Patch IDs` row of `METADATA_FOOTER_START..END`.
> 4. **Validate Before Completion**: Run `python scripts/markdown_validator.py <report.md> --fix` and verify `0`
>    violations (`100/100` quality score).

---

## 1. Executive Summary & Decision Disposition

State the engineering objective, target hardware (**Intel® Ethernet Network Adapter E835-CC** on **Intel® Xeon® 6
Processor** hosts), and the pass/fail gate outcome in `<= 25` words per sentence using active voice (`Rule D6`).

- **Primary Deliverable**: Summarize the validated patch series, firmware/DDP package (`ice_lag-1.3.2.5.pkg`), or
  configuration profile.
- **3-Bucket Validation Accounting (`HH-MR-008`)**:
  1. **Live Hardware Executed (`PASS` / `FAIL`)**: `<N> / <Total>` tests executed on leased lab hardware (`TB1`–`TB5`).
  2. **Static / Config Verified**: `<N>` static schema, `checkpatch.pl --strict`, or compilation checks passed.
  3. **Skipped (Topology Not Present)**: `<N>` tests skipped with explicit hardware topology reason.
- **Zero-Tolerance `dmesg` Gate (`DMAR=0` / `MDD=0`)**: Confirmed `0` new `DMAR`, `MDD`, `Oops`, `BUG:`, `WARNING:`, or
  `tx_timeout` events across all participating hosts.

---

## 2. Validated Kernel Patch & Configuration Inventory (`3`-Column Zero-Scroll Layout)

Use a `3`-column table for patch series or component inventories. Always use compact basename link labels (`<= 28`
characters) and stack commit SHAs, subsystems, and line counts with `<br>`.

| Patch ID & Short Basename Link | Target Driver, Subsystem & Architectural Fix | Verification Gate & Status |
| --- | --- | --- |
| **`Patch 0001`**<br>[`0001-ice-snc-numa.patch`](../kb/development/e835_linux_kernel_alignment_and_bifurcation_architecture.md)<br>Driver: `ice` (`DRV-F01`) | **SNC-3 Node-Local Ring & Vector Spread**:<br>Replaces global CPU spread with `cpumask_local_spread()` and `netif_napi_set_irq()` for local NUMA affinity. | **Status**: `VERIFIED_APPLIED`<br>**Gate**: `DMAR=0`, `MDD=0`<br>**Gain**: `+28%` throughput |
| **`Patch 0002`**<br>[`0002-ice-bifurc-vsi.patch`](../kb/development/e835_linux_kernel_alignment_and_bifurcation_architecture.md)<br>Driver: `ice` (`DRV-BIF-01`) | **Bifurcated Subfunction (`ICE_VSI_BIFURC`)**:<br>Maps XSK zero-copy UMEM DMA against `ice_pf_to_dev(pf)` and disables per-QSet `QRX_CTRL(pf_q)` on teardown. | **Status**: `VERIFIED_APPLIED`<br>**Gate**: `DMAR=0`, `MDD=0`<br>**Check**: `checkpatch.pl` `0` err |

---

## 3. Root-Cause Analysis & Disproved / Rejected Claims (`3`-Column Zero-Scroll Layout)

When documenting falsified hypotheses or rejected bug claims, consolidate `Claim ID` and `Source Artifact` into Column
1 (splitting long filenames with `<wbr>` so each segment is `<= 24` characters) and stack `Original Claim` and
`Empirical Falsification` vertically with `<br>` in Column 2.

| Claim ID & Source Artifact | Original Claim vs. Empirical Hardware Falsification | Disposition & Action |
| --- | --- | --- |
| **`CLAIM-01`**<br>Artifact: BUG_ice_tx_vlan_<wbr><wbr><wbr>offload_frame_<wbr><wbr><wbr>corruption_e835.<wbr>md<br>Subsystem: `ice` / `802.3ad` | **Original Claim**: Hardware TX VLAN insertion corrupts LACPDU frames on 8x25G breakout ports.<br>**Empirical Falsification**: Packet capture (`tcpdump -xx`) proved untagged LACPDUs received a priority-tagged `VLAN 0` header only when `tx-vlan-offload` was enabled in DSCP mode without a switch trunk native VLAN. | **`REJECTED_FALSIFIED`**<br>Keep `tx-vlan-offload` off in pure DSCP mode or use L2-PCP trunk mode (`CG-001`). |
| **`CLAIM-02`**<br>Artifact: ice_vsi_stop_lan_rx_ring<wbr>s_teardown.c<br>Subsyste<wbr>m: `ice_sf_eth` | **Original Claim**: Subfunction teardown must call `ice_vsi_stop_lan_rx_rings(main_vsi)` to flush DMA.<br>**Empirical Falsification**: Stopping `main_vsi` drops PF management traffic across all active subfunctions; disabling per-QSet `QRX_CTRL(pf_q)` cleanly stops only the target subfunction queues. | **`SUPERSEDED_BY_PATCH`**<br>Enforce per-QSet `QRX_CTRL` poll (`HH-BR-002`). |

---

## 4. Master Multi-Testbed A/B Validation Summary (`4`-Column Max Matrix)

For multi-testbed A/B comparisons (`TB1`–`TB5`), use at most `4` columns by combining **Baseline (`State A`)** and
**Patched (`State B`)** in Column 3 with `<br>` and combining **Delta**, **Pass Gate**, and **`dmesg` Status** in Column
4.

| Testbed & Hardware Topology | Workload & Metric | Baseline (`State A`) vs. Patched (`State B`) | Measured Delta & Pass Gate |
| --- | --- | --- | --- |
| **`TB1` — Xeon 6 (`GNR`)**<br>Dual E835-CC (`2x200GbE`)<br>SNC-3 (`3` NUMA nodes/socket) | **64-Stream `TCP_STREAM`**<br>MTU: `9000` (`30s` sync)<br>Pinning: Node-local `cpulist` | **State A (Baseline)**: `148.2Gb/s` (`Retrans: 0.14%`)<br>**State B (Patched)**: `194.6Gb/s` (`Retrans: 0.00%`) | **Delta**: `+31.3%` (`+46.4Gb/s`)<br>**Gate**: `PASS` (`>= 190Gb/s`)<br>**`dmesg`**: `DMAR=0`, `MDD=0` |
| **`TB2` — Xeon 6 (`CWF`)**<br>Dual E835-CC (`2x100GbE`)<br>LACP RoCEv2 (`Dell OS10`) | **Dual-Port `ib_write_bw`**<br>QP Count: `8` (`-T 104 -R`)<br>DDP: `ice_lag-1.3.2.5.pkg` | **State A (Baseline)**: `96.4Gb/s` (single-port polarized)<br>**State B (Patched)**: `191.8Gb/s` (active-active LAG) | **Delta**: `+98.9%` (`2x` line rate)<br>**Gate**: `PASS` (`0` PFC deadlocks)<br>**`dmesg`**: `DMAR=0`, `MDD=0` |

---

## 5. Reproducibility Commands & Mandatory `dmesg` Zero-Tolerance Gate (`Rule D8`)

Always parameterize shell commands with `${NETDEV}`, `${PCI_DEV}`, and `${TB_ID}`, include `set -Eeuo pipefail`, and
capture pre-test and post-test `dmesg` baselines:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${TB_ID:?Specify TB_ID (e.g., TB1)}"
: "${NETDEV:?Specify NETDEV (e.g., eth0)}"
: "${PCI_DEV:?Specify PCI_DEV (e.g., 0000:b1:00.0)}"

# Step 0: Acquire exclusive testbed lease before driver/network changes
labctl status
labctl checkout "${TB_ID}" --agent antigravity --purpose "A/B validation run" --reconfig true

DMESG_BEFORE=$(dmesg | wc -l)
timeout 2s ethtool -i "${NETDEV}"
cat "/sys/kernel/debug/irdma/${PCI_DEV}/qp_connections" 2>/dev/null || true

# Post-test zero-tolerance dmesg verification gate
dmesg -T | tail -n +"$((DMESG_BEFORE + 1))" | tail -n 40
if dmesg -T | tail -n +"$((DMESG_BEFORE + 1))" | grep -iE "DMAR|fault|DRHD|Oops|BUG:|WARNING:|Call Trace|MDD|Malicious|hw_error|reset|tx_timeout"; then
  echo "HARD FAILURE: New kernel/hardware fault detected in dmesg" >&2
  exit 1
fi
```

---

## 6. Artifact & Cross-Repository Reference Ledger (`3`-Column Basename Links)

Never use `50+` character link labels or unverified cross-repository relative paths. Use short file basenames (`<= 28`
characters) for link text.

| Reference ID & Category | Artifact Basename Link | Scope & Verification Note |
| --- | --- | --- |
| **`REF-01` — Standards** | [intel_ethernet_brandin<wbr>g_and_parameter_standa<wbr>rds.md](../kb/documentation/intel_ethernet_branding_and_parameter_standards.md) | Rules `D1`–`D10` `v3.2` (`MD013`, `D5-COLS`, `D6` STE-100, `D7-ID-MATCH`). |
| **`REF-02` — DMAR Gate** | [dmesg_dmar_mdd_zero_<wbr>tolerance_gate.md](../kb/validation/dmesg_dmar_mdd_zero_tolerance_gate.md) | Mandatory pre/post `dmesg` zero-tolerance hardware fault gate. |
| **`REF-03` — Architecture** | [e835_linux_kernel_alig<wbr>nment_and_bifurcation_<wbr>architecture.md](../kb/development/e835_linux_kernel_alignment_and_bifurcation_architecture.md) | `DRV-F01`–`DRV-F13`, `DRV-LAG-01`–`12`, and `DRV-BIF-01`–`10` reference. |

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_<wbr>01<wbr>_Engineering_<wbr><wbr><wbr>Validation_and_<wbr><wbr>Executive_<wbr>Report<wbr>.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Engineering Report Template`, `A/B Validation Report`, `Zero-Scroll 3-Column Table`, `Rules D1-D10 v3.2`, `ASD-STE100` |
| **Drivers & Subsystems** | `ice`, `irdma`, `iavf`, `ICE_VSI_BIFURC`, `HevyOne`, `PDF_REPO`, `HevyHitter` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-ENG-AB-REPORT-001`, `D1-D10 v3.2`, `MD013`, `MD007`, `MD032`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
