# Intel® Configuration Guide & Best Known Method (BKM) Runbook Template (`Diátaxis Task`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-CONFIG-GUIDE-002` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Host, Switch, RoCEv2 LAG, Auto-Tune, and Subfunction Configuration Guides (`CG-*`)
- **Summary**: Canonical **ASD-STE100** task-oriented configuration guide template for **Intel® Ethernet 800 Series** (**Intel® Ethernet Controller E835** and **Intel® Ethernet Network Adapter E835-CC**) and **Intel® Xeon® 6 Processor** deployments under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!WARNING]
> **NVMe-oF & Active Testbed Lease Safety (`Rule D6-WARN`)**:
> Do not unload `irdma` or `ice` while NVMe-oF filesystems (`/run/Videos`) are mounted. Unloading RDMA or LAN drivers
> during active I/O aborts the EXT4 journal and faults the host. Run `labctl status` and `labctl checkout <TB>
> --reconfig true` before you modify any interface or driver state.

---

## 1. Prerequisites & Pre-Flight Hardware Gate (`Step 0`)

Complete these pre-flight checks before you apply host or switch configuration changes (`<= 20` words per procedural
sentence):

1. Check shared testbed availability and acquire an exclusive reconfiguration lease via `labctl checkout`.
2. Verify both **Intel® Ethernet Network Adapter E835-CC** ports reside on the same physical PCIe ASIC (`domain:bus`).
3. Confirm the active Dynamic Device Personalization (DDP) package is `ice_lag-1.3.2.5.pkg` in `dmesg`.
4. Verify `cat /sys/module/irdma/version` matches the installed `libirdma` userspace provider (`rdma-core-61.0`).

---

## 2. Parameterized Environment Variables (`Rule D1`–`D4` & Section 2)

Never hardcode lab-specific network interface names (`ens10f0np0`) or management IPv4 addresses (`10.x.x.x`) in customer
procedures. Use RFC 2544 (`198.18.x.x`) documentation IPs and parameterized shell variables:

| Variable Name | Default / Example Value | Description & Hardware Constraint |
| --- | --- | --- |
| **`${PCI_DEV}` / `${BDF0}`** | `"0000:b1:00.0"` | Primary PCIe Gen5 (`32GT/s`) Function 0 BDF on the local SNC NUMA node. |
| **`${PORT0}` / `${PORT1}`** | `"eth0"` / `"eth1"` | Dual-port bond member interfaces on the same E835 ASIC. |
| **`${BOND_IP}`** | `"198.18.10.11/24"` | RFC 2544 test subnet IPv4 address assigned to `bond0` or `bond0.${VLAN_ID}`. |
| **`${QUEUES}`** | `32` (`<= 63` max) | Combined queue count clamped to `min(req, ethtool_max, local_numa_cores)`. |

---

## 3. Step-by-Step Configuration Procedure (`ASD-STE100` `<= 20` Words/Step)

1. Export the target PCIe BDF, interface names, and RFC 2544 IPv4 address in your shell session.
2. Stop `lldpad` and disable the firmware LLDP agent on both member ports before you configure DCB.
3. Unload `irdma` and set `tx_scheduling_layers` to `5` via `devlink` before you create `bond0`.
4. Reload both PFs via `devlink dev reload` and wait for carrier readiness (`operstate == up`).
5. Create `bond0` in `802.3ad` mode (`lacp_rate fast`, `xmit_hash_policy layer3+4`) and enslave both ports.
6. Reload `irdma` and verify that the auxiliary RoCEv2 device binds cleanly with `0` `dmesg` faults.

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${BDF0:?Specify BDF0 (e.g., 0000:b1:00.0)}"
: "${BDF1:?Specify BDF1 (e.g., 0000:b1:00.1)}"
: "${PORT0:?Specify PORT0}"
: "${PORT1:?Specify PORT1}"

cleanup_on_exit() {
  local rc=$1
  if (( rc != 0 )); then
    echo "Configuration failed (rc=${rc}); inspect dmesg for DMAR/MDD faults." >&2
  fi
}
trap 'cleanup_on_exit $?' EXIT ERR INT TERM

DMESG_BASELINE=$(dmesg | wc -l)

systemctl stop lldpad || true
timeout 2s ethtool --set-priv-flags "${PORT0}" fw-lldp-agent off
timeout 2s ethtool --set-priv-flags "${PORT1}" fw-lldp-agent off

modprobe -r irdma || true
for bdf in "${BDF0}" "${BDF1}"; do
  devlink dev param set "pci/${bdf}" name tx_scheduling_layers value 5 cmode runtime
  devlink dev reload "pci/${bdf}"
done

modprobe irdma
dmesg -T | tail -n +"$((DMESG_BASELINE + 1))" | tail -n 40
```

---

## 4. Strict YAML 1.2 / JSON Schema Configuration Block (`Rule D9`)

Always quote boolean-like strings (`"on"`, `"off"`, `"yes"`, `"no"`), colon-delimited QoS maps (`"0:0 3:3"`), and PCIe
BDFs in YAML configuration examples:

```yaml
$schema: "../../schemas/site_lag_config.schema.json"
schema_version: "1.0.0"
host:
  adapter_model: "Intel(R) Ethernet Network Adapter E835-CC"
  pci_bdf_port0: "0000:b1:00.0"
  pci_bdf_port1: "0000:b1:00.1"
  mtu: 9000
  queues: 32
  adaptive_rx: "on"
  adaptive_tx: "on"
qos:
  trust_mode: "DSCP"
  rocev2_dscp: 26
  pfc_enabled_tc: "3"
  prio_tc_map: "0:0 1:1 2:2 3:3"
  ets_bandwidth_map: "0:40 3:60"
```

---

## 5. Verification & Idempotent Rollback Gate

Run these checks to confirm the configuration is active and hardware-clean:

| Check Item | Verification Command | Expected Pass Output |
| --- | --- | --- |
| **1. LACP Partner Sync** | `cat /proc/net/bonding/bond0` | Both ports show `Aggregator ID` match and `MII Status: up`. |
| **2. Hardware LAG Recipes** | `cat` /sys/kernel/debug/ice/<wbr><wbr>${BDF0}/lag_recipes | `sw_recipes_used <= 64` (`0` allocation failures). |
| **3. Kernel Fault Gate** | dmesg -T \| grep -iE "DMAR\|MDD\|Oops\|WARNING" | `0` new lines (`DMAR=0`, `MDD=0`). |

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_<wbr>02<wbr>_Configuration_<wbr><wbr>Guide_<wbr>and_BKM_<wbr>Runbook.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Configuration Guide Template`, `BKM Runbook`, `Diataxis Task`, `ASD-STE100`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `devlink`, `802.3ad`, `RoCEv2`, `DCB`, `PFC`, `ETS` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-CONFIG-GUIDE-002`, `D1-D10 v3.2`, `D6-STE100`, `D8-SH`, `D9-CFG` |
<!-- METADATA_FOOTER_END -->
