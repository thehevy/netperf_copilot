# Troubleshooting & Root-Cause Diagnostic Playbook Template (`Diátaxis Reference`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-PLAYBOOK-004` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-13`
- **Target Scope**: High-Speed Network Performance, PCIe/NUMA Locality, and Pre-Flight Troubleshooting Playbooks
- **Summary**: Canonical 4-step (`Symptom -> Root Cause -> Verification -> Fix`) diagnostic playbook template for `100GbE`–`800GbE` network benchmarking under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!CAUTION]
> **Zero-Tolerance Hardware Fault Gate (`Rule D6-WARN`)**:
> Do not continue benchmark or stress runs if a `DMAR` fault, `MDD` event, or kernel `Oops`/`WARNING` appears in
> `dmesg`. Continuing traffic after an IOMMU or hardware queue fault masks the root-cause descriptor state. Stop the
> workload immediately, capture `dmesg -T | tail -n 40`, and resolve the root cause first.

---

## 1. Quick Symptom-to-Signature Triage Matrix (`3`-Column Zero-Scroll Layout)

Use a `3`-column triage matrix to map observable failure signatures to their root-cause section and verification
command:

| Failure ID & Observable Symptom | Primary Root-Cause Subsystem | Diagnostic Section & Fix Reference |
| --- | --- | --- |
| **`DIAG-01` — Bimodal Throughput (`CV > 5%`)**<br>Warmup gate fails (`WARMUP-BIMODAL`) | Cross-NUMA Queue 0 IRQ affinity (`AA-016`) or active `irqbalance` (`AA-012`) | See **Section 2.1** (Stop `irqbalance` and pin IRQs to the adapter's local NUMA node). |
| **`DIAG-02` — `tx_restart_queue` Stalls**<br>Throughput caps at `135–145Gb/s` on `200GbE` | Default `TX=256` descriptor ring exhaustion (`AA-015`) | See **Section 2.2** (Increase `tx_ring` to `512` on E-core or `2048` on P-core via `ethtool -G`). |
| **`DIAG-03` — High-Stream Accept Timeouts**<br>`>= 16` parallel streams fail control connect | Single `netserver` daemon accept queue contention on port `12865` (`AA-022`) | See **Section 2.3** (Launch per-core `netserver-manager` pool on ports `18600 + core`). |

---

## 2. Diagnostic Playbook Entries (`Symptom -> Root Cause -> Verification -> Fix`)

Structure every troubleshooting entry using the mandatory `4`-bullet Diátaxis Reference pattern (`Rule D7-ARCH`):

### 2.1 `DIAG-01`: Bimodal Run-to-Run Variance (`CV > 5%`) Due to Cross-NUMA IRQ Affinity

- **Symptom**: Single-stream or 8-stream `200GbE` throughput fluctuates between `95Gb/s` and `189Gb/s` across runs,
  failing `WARMUP-BIMODAL` (`CV > 5%`).
- **Root Cause**: The `irqbalance` daemon migrated Queue 0 / Vector 0 (`p0_irq`) to a remote NUMA node, or application
  threads were scheduled onto IRQ-handling cores.
- **Verification**: Run `netperf_preflight.py` and inspect `/proc/irq/<irq>/smp_affinity_list`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${NETDEV:?Specify NETDEV (e.g., eth0)}"
python3 dev/tools/netperf_preflight.py -i "${NETDEV}"
```

- **Fix**: Stop `irqbalance` and apply local NUMA IRQ pinning and disjoint core allocation via `netperf_tuner.py`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${NETDEV:?Specify NETDEV (e.g., eth0)}"
python3 dev/tools/netperf_tuner.py -i "${NETDEV}" --apply-bkm auto
```

---

### 2.2 `DIAG-02`: TX Ring Exhaustion (`tx_restart_queue`) on `100GbE`–`200GbE` Links

- **Symptom**: `TCP_STREAM` throughput plateaus below line rate while `ethtool -S` shows rapidly incrementing
  `tx_restart_queue` or `tx_busy` counters.
- **Root Cause**: A `256`-descriptor TX ring cannot absorb `64` KB TSO bursts at `200GbE` line rate (`AA-015`).
- **Verification**: Check current ring settings and counter deltas:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${NETDEV:?Specify NETDEV (e.g., eth0)}"
timeout 2s ethtool -g "${NETDEV}"
timeout 2s ethtool -S "${NETDEV}" | grep -E "restart|busy|drop" || true
```

- **Fix**: Set `tx_ring=512` on shared-L2 E-core hosts or `tx_ring=2048` on P-core hosts, with `rx_ring=4096`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${NETDEV:?Specify NETDEV (e.g., eth0)}"
timeout 2s ethtool -G "${NETDEV}" tx 2048 rx 4096
```

---

### 2.3 `DIAG-03`: Control-Socket Serialization at `16`–`64` Parallel Streams

- **Symptom**: Launching `32` or `64` parallel `netperf` instances against a single `netserver` on port `12865` causes
  connection retries or uneven stream start times.
- **Root Cause**: A single `netserver` listener serializes `accept()` and control handshake processing across all
  streams (`AA-022`).
- **Verification**: Check how many `netserver` listeners are active on the Load Partner:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

python3 dev/tools/netserver_manager.py --action status --base-port 18600
```

- **Fix**: Start a per-core `netserver` pool on the Load Partner (`18600 + core_id`) and pass `--per-core-netserver` to
  `netperf-multi`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

python3 dev/tools/netserver_manager.py --action start --count 32 --base-port 18600
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_<wbr>04<wbr>_Troubleshooting_<wbr>and_<wbr>Root_Cause_<wbr>Playbook.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-13` |
| **Keywords / Search Tags** | `Troubleshooting Playbook Template`, `Diataxis Reference`, `DMAR=0 Gate`, `Symptom Root Cause Verification Fix`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `Linux networking`, `ethtool`, `netperf_preflight.py`, `netperf_tuner.py`, `DMAR`, `MDD` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-PLAYBOOK-004`, `D1-D10 v3.2`, `AA-001..AA-024`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
