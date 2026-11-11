# Engineering Patch, Architecture & A/B Hardware Validation Report Template

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-ENG-AB-REPORT-001` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Executive Engineering Reports, Code Audits, and Multi-Node A/B Validation Reports
- **Summary**: Canonical technical report template for `100GbE`–`800GbE` network adapter and multi-core server validation reports under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!IMPORTANT]
> **Mandatory Authoring Rules (`D1`–`D10` v3.2)**:
>
> 1. **Wrap Lines at `<= 120` Characters (`MD013` / `D5-WRAP`)**: Wrap all prose, numbered or bulleted lists, and
>    blockquotes at `<= 120` characters with exact list continuation indentation (`MD007`) and blank lines around lists
>    (`MD032`).
> 2. **Zero-Scroll Tables (`D5-COLS` `<= 3–4` Cols & `D5-TOKEN` `<= 40` Chars)**: Keep report tables to `3` columns (`4`
>    columns max for A/B testbed matrices). Stack secondary fields vertically with `<br>`, use short file basenames for
>    link labels (`[netperf_tuner.py](dev/tools/netperf_tuner.py)`), and split long identifiers at `<wbr>` boundaries
>    (`<= 24` chars per segment).
> 3. **Synchronize Header & Footer `Document ID` (`D7-ID-MATCH`)**: The `Document ID` in `METADATA_HEADER_START..END`
>    must appear verbatim (never truncated) in the `Validation / Patch IDs` row of `METADATA_FOOTER_START..END`.
> 4. **Validate Before Completion**: Run `python scripts/markdown_validator.py <report.md> --fix` and verify `0`
>    violations (`100/100` quality score).

---

## 1. Executive Summary & Decision Disposition

State the engineering objective, target hardware (`100GbE`/`200GbE` network adapters on multi-socket NUMA hosts), and
the pass/fail gate outcome in `<= 25` words per sentence using active voice (`Rule D6`).

- **Primary Deliverable**: Summarize the validated code changes, firmware/driver version, or tuning profile.
- **3-Bucket Validation Accounting**:
  1. **Live Hardware Executed (`PASS` / `FAIL`)**: `<N> / <Total>` tests executed on 2-node Linux hardware testbeds.
  2. **Static / Config Verified**: `<N>` static schema, linter, or compilation checks passed.
  3. **Skipped (Topology Not Present)**: `<N>` tests skipped with explicit hardware topology reason.
- **Zero-Tolerance `dmesg` Gate (`DMAR=0` / `MDD=0`)**: Confirmed `0` new `DMAR`, `MDD`, `Oops`, `BUG:`, `WARNING:`, or
  `tx_timeout` events across all participating hosts.

---

## 2. Validated Code & Configuration Inventory (`3`-Column Zero-Scroll Layout)

Use a `3`-column table for patch series or component inventories. Always use compact basename link labels (`<= 28`
characters) and stack commit SHAs, subsystems, and line counts with `<br>`.

| Change ID & Short Basename Link | Target Module, Subsystem & Architectural Fix | Verification Gate & Status |
| --- | --- | --- |
| **`Change 0001`**<br>[`netperf_topology.py`](../dev/tools/netperf_topology.py)<br>Module: `topology` | **NUMA Node-Local Core & IRQ Partitioning**:<br>Partitions physical cores into disjoint IRQ, application, and background isolation pools per NUMA node. | **Status**: `VERIFIED_APPLIED`<br>**Gate**: `DMAR=0`, `MDD=0`<br>**Gain**: `+28%` throughput |
| **`Change 0002`**<br>[`nettest_omni.c`](../src/nettest_omni.c)<br>Module: `omni` | **Zero-Copy (`MSG_ZEROCOPY`) Completion Drain**:<br>Enables `SO_ZEROCOPY` and drains `MSG_ERRQUEUE` completions to reduce sender CPU utilization at `200GbE`. | **Status**: `VERIFIED_APPLIED`<br>**Gate**: `DMAR=0`, `MDD=0`<br>**Check**: `gcc -Wall` `0` err |

---

## 3. Root-Cause Analysis & Disproved / Rejected Claims (`3`-Column Zero-Scroll Layout)

When documenting falsified hypotheses or rejected bug claims, consolidate `Claim ID` and `Source Artifact` into Column
1 (splitting long filenames with `<wbr>` so each segment is `<= 24` characters) and stack `Original Claim` and
`Empirical Falsification` vertically with `<br>` in Column 2.

| Claim ID & Source Artifact | Original Claim vs. Empirical Hardware Falsification | Disposition & Action |
| --- | --- | --- |
| **`CLAIM-01`**<br>Artifact: [netperf_preflight.py](../dev/tools/netperf_preflight.py)<br>Subsystem: `802.3ad` / `VLAN` | **Original Claim**: Hardware TX VLAN insertion corrupts LACPDU frames on breakout ports.<br>**Empirical Falsification**: Packet capture (`tcpdump -xx`) proved untagged LACPDUs received a priority-tagged `VLAN 0` header only when `tx-vlan-offload` was enabled without a switch trunk native VLAN. | **`REJECTED_FALSIFIED`**<br>Keep `tx-vlan-offload` off in pure DSCP mode or configure native VLAN on the switch trunk. |
| **`CLAIM-02`**<br>Artifact: [netcpu_procstat.c](../src/netcpu_procstat.c)<br>Subsystem: `procstat` | **Original Claim**: A single `read()` call on `/proc/stat` always returns all CPU lines.<br>**Empirical Falsification**: On `256+` core systems, `/proc/stat` exceeds a single page read and truncates upper CPU lines unless read in a loop. | **`FIXED_IN_SOURCE`**<br>Loop `read()` until `proc_stat_buflen` or `EOF` (`netcpu_procstat.c`). |

---

## 4. Master Multi-Node A/B Validation Summary (`4`-Column Max Matrix)

For multi-node A/B comparisons, use at most `4` columns by combining **Baseline (`State A`)** and **Tuned (`State B`)**
in Column 3 with `<br>` and combining **Delta**, **Pass Gate**, and **`dmesg` Status** in Column 4.

| Testbed & Hardware Topology | Workload & Metric | Baseline (`State A`) vs. Tuned (`State B`) | Measured Delta & Pass Gate |
| --- | --- | --- | --- |
| **`Node-Pair A` — P-Core (`SMT`)**<br>Dual `200GbE` (`PCIe Gen5 x16`)<br>Multi-Node NUMA | **16-Stream `TCP_STREAM`**<br>MTU: `9000` (`30s` sync)<br>Pinning: Node-local `spread_step2` | **State A (Baseline)**: `148.2Gb/s` (`Retrans: 0.14%`)<br>**State B (Tuned)**: `191.4Gb/s` (`Retrans: 0.00%`) | **Delta**: `+29.1%` (`+43.2Gb/s`)<br>**Gate**: `PASS` (`>= 188Gb/s`)<br>**`dmesg`**: `DMAR=0`, `MDD=0` |
| **`Node-Pair B` — E-Core (`Shared-L2`)**<br>Dual `200GbE` (`PCIe Gen5 x16`)<br>`4`-Core L2 Modules | **16-Stream `TCP_STREAM`**<br>MTU: `9000` (`30s` sync)<br>Pinning: `spread_l2` (`TX=512`) | **State A (Baseline)**: `139.5Gb/s` (`CV: 8.4%`)<br>**State B (Tuned)**: `189.4Gb/s` (`CV: 0.42%`) | **Delta**: `+35.8%` (`CV <= 1%`)<br>**Gate**: `PASS` (`0` queue stalls)<br>**`dmesg`**: `DMAR=0`, `MDD=0` |

---

## 5. Reproducibility Commands & Mandatory `dmesg` Zero-Tolerance Gate (`Rule D8`)

Always parameterize shell commands with `${NETDEV}` and `${PCI_DEV}`, include `set -Eeuo pipefail`, and capture
pre-test and post-test `dmesg` baselines:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${NETDEV:?Specify NETDEV (e.g., eth0)}"
: "${PCI_DEV:?Specify PCI_DEV (e.g., 0000:17:00.0)}"

DMESG_BEFORE=$(dmesg | wc -l)
timeout 2s ethtool -i "${NETDEV}"
python3 dev/tools/netperf_preflight.py -i "${NETDEV}"

# Post-test zero-tolerance dmesg verification gate
dmesg -T | tail -n +"$((DMESG_BEFORE + 1))" | tail -n 40
if dmesg -T | tail -n +"$((DMESG_BEFORE + 1))" | grep -iE "DMAR|fault|DRHD|Oops|BUG:|WARNING:|Call Trace|MDD|Malicious|hw_error|reset|tx_timeout"; then
  echo "HARD FAILURE: New kernel/hardware fault detected in dmesg" >&2
  exit 1
fi
```

---

## 6. Artifact & Repository Reference Ledger (`3`-Column Basename Links)

Never use `50+` character link labels or unverified relative paths. Use short file basenames (`<= 28` characters) for
link text.

| Reference ID & Category | Artifact Basename Link | Scope & Verification Note |
| --- | --- | --- |
| **`REF-01` — Executive Summary** | [EXECUTIVE_SUMMARY.md](../dev/docs/EXECUTIVE_SUMMARY.md) | Executive summary of the `netperf_copilot` modernization architecture. |
| **`REF-02` — White Paper** | [TECHNICAL_WHITE_PAPER.md](../dev/docs/TECHNICAL_WHITE_PAPER.md) | Deep-dive technical white paper covering C engine and Python tooling. |
| **`REF-03` — Validator** | [markdown_validator.py](../scripts/markdown_validator.py) | Single Source of Truth `D1`–`D10` `v3.2` Markdown validator (`100/100`). |

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_<wbr>01<wbr>_Engineering_<wbr>Validation_and_<wbr>Executive_<wbr>Report<wbr>.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Engineering Report Template`, `A/B Validation Report`, `Zero-Scroll 3-Column Table`, `Rules D1-D10 v3.2`, `ASD-STE100` |
| **Drivers & Subsystems** | `Linux networking`, `ethtool`, `devlink`, `netperf_copilot`, `markdown_validator.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-ENG-AB-REPORT-001`, `D1-D10 v3.2`, `MD013`, `MD007`, `MD032`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
