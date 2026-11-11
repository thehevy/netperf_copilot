# Configuration Guide & Best Known Method (BKM) Runbook Template (`Diátaxis Task`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-CONFIG-GUIDE-002` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Host, Switch, LACP LAG, and Auto-Tune Configuration Guides (`CG-*`)
- **Summary**: Canonical **ASD-STE100** task-oriented configuration guide template for `100GbE`–`800GbE` network adapters and multi-core Linux servers under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!WARNING]
> **Active Storage & Network Interface Safety (`Rule D6-WARN`)**:
> Do not unload network or RDMA kernel modules while network filesystems or NVMe-oF volumes are mounted. Unloading
> drivers during active storage I/O aborts the filesystem journal and faults the host. Verify that no active storage
> mounts use the target interface before you modify driver state.

---

## 1. Prerequisites & Pre-Flight Hardware Gate (`Step 0`)

Complete these pre-flight checks before you apply host or switch configuration changes (`<= 20` words per procedural
sentence):

1. Run `netperf_preflight.py -i "${NETDEV}"` to verify PCIe link width, NUMA locality, and background process isolation.
2. Verify both network adapter ports reside on the expected local PCIe Root Complex (`domain:bus`).
3. Confirm the network driver and firmware versions match across the Device Under Test (DUT) and Load Partner (LP).
4. Record the baseline `dmesg -T | wc -l` line count before applying any `devlink`, `ethtool`, or `sysctl` changes.

---

## 2. Parameterized Environment Variables (`Rule D1`–`D4` & Section 2)

Never hardcode host-specific network interface names or private management IPv4 addresses (`10.x.x.x`) in public
procedures. Use RFC 5737 (`192.0.2.x`) or RFC 2544 (`198.51.100.x`) documentation IPs and parameterized shell variables:

| Variable Name | Default / Example Value | Description & Hardware Constraint |
| --- | --- | --- |
| **`${PCI_DEV}` / `${BDF0}`** | `"0000:17:00.0"` | Primary PCIe Gen5 (`32GT/s`) Function 0 BDF on the local NUMA node. |
| **`${PORT0}` / `${PORT1}`** | `"eth0"` / `"eth1"` | Dual-port bond member interfaces on the target network adapter. |
| **`${BOND_IP}`** | `"192.0.2.11/24"` | RFC 5737 documentation IPv4 address assigned to `bond0`. |
| **`${QUEUES}`** | `32` (`<= 63` max) | Combined queue count clamped to `min(req, ethtool_max, local_numa_cores)`. |

---

## 3. Step-by-Step Configuration Procedure (`ASD-STE100` `<= 20` Words/Step)

1. Export the target PCIe BDF, interface names, and RFC 5737 IPv4 address in your shell session.
2. Stop `irqbalance` so the OS does not overwrite manual SMP IRQ affinity masks during the benchmark.
3. Set the CPU frequency scaling governor to `performance` on all online cores.
4. Configure combined RSS channels, descriptor ring sizes, and static interrupt coalescing via `ethtool`.
5. Configure `2` GB maximum TCP socket buffers (`rmem_max`, `wmem_max`, `tcp_rmem`, `tcp_wmem`) via `sysctl`.
6. Pin interface queue IRQs to the adapter's local NUMA node and verify `0` new `dmesg` faults.

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${PCI_DEV:?Specify PCI_DEV (e.g., 0000:17:00.0)}"
: "${NETDEV:?Specify NETDEV (e.g., eth0)}"

cleanup_on_exit() {
  local rc=$1
  if (( rc != 0 )); then
    echo "Configuration failed (rc=${rc}); inspect dmesg for DMAR/MDD faults." >&2
  fi
}
trap 'cleanup_on_exit $?' EXIT ERR INT TERM

DMESG_BASELINE=$(dmesg | wc -l)

systemctl stop irqbalance || true
cpupower frequency-set -g performance || true

timeout 2s ethtool -L "${NETDEV}" combined 32
timeout 2s ethtool -G "${NETDEV}" tx 2048 rx 4096
timeout 2s ethtool -C "${NETDEV}" adaptive-rx off adaptive-tx off rx-usecs 10 tx-usecs 20
timeout 2s ip link set dev "${NETDEV}" mtu 9000

dmesg -T | tail -n +"$((DMESG_BASELINE + 1))" | tail -n 40
```

---

## 4. Strict YAML 1.2 / JSON Schema Configuration Block (`Rule D9`)

Always quote boolean-like strings (`"on"`, `"off"`, `"yes"`, `"no"`), colon-delimited QoS maps (`"0:0 3:3"`), and PCIe
BDFs in YAML configuration examples:

```yaml
$schema: "../schemas/profile.schema.json"
schema_version: "2.0.0"
host:
  adapter_speed: "200GbE"
  pci_bdf_port0: "0000:17:00.0"
  pci_bdf_port1: "0000:17:00.1"
  mtu: 9000
  queues: 32
  adaptive_rx: "off"
  adaptive_tx: "off"
qos:
  trust_mode: "DSCP"
  dscp_classes: "EF,CS3,AF21,CS0"
  prio_tc_map: "0:0 1:1 2:2 3:3"
```

---

## 5. Verification & Idempotent Rollback Gate

Run these checks to confirm the configuration is active and hardware-clean:

| Check Item | Verification Command | Expected Pass Output |
| --- | --- | --- |
| **1. Pre-Flight Audit** | `python3 dev/tools/netperf_preflight.py -i "${NETDEV}"` | `passed: true` (`0` `FAIL` anti-affinity findings). |
| **2. Ring & Coalesce State** | ethtool -g "${NETDEV}" && ethtool -c "${NETDEV}" | `TX: 512/2048`, `RX: 4096`, `Adaptive RX: off`, `Adaptive TX: off`. |
| **3. Kernel Fault Gate** | dmesg -T \| grep -iE "DMAR\|MDD\|Oops\|WARNING" | `0` new lines (`DMAR=0`, `MDD=0`). |

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_<wbr>02<wbr>_Configuration_<wbr>Guide_<wbr>and_BKM_<wbr>Runbook.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Configuration Guide Template`, `BKM Runbook`, `Diataxis Task`, `ASD-STE100`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `Linux networking`, `ethtool`, `devlink`, `802.3ad`, `QoS`, `netperf_tuner.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-CONFIG-GUIDE-002`, `D1-D10 v3.2`, `D6-STE100`, `D8-SH`, `D9-CFG` |
<!-- METADATA_FOOTER_END -->
