# Intel® Troubleshooting & Root-Cause Diagnostic Playbook Template (`Diátaxis Reference`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-PLAYBOOK-004` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Kernel Driver, RoCEv2 LAG, PCIe/IOMMU (`DMAR`), and Switch Fabric Troubleshooting Playbooks
- **Summary**: Canonical 4-step (`Symptom -> Root Cause -> Verification -> Fix`) diagnostic playbook template for **Intel® Ethernet 800 Series** (**Intel® Ethernet Controller E835** and **Intel® Ethernet Network Adapter E835-CC**) and **Intel® Xeon® 6 Processor** systems under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!CAUTION]
> **Zero-Tolerance Hardware Fault Gate (`Rule D6-WARN`)**:
> Do not continue benchmark or stress runs if a `DMAR` fault, `MDD` event, or kernel `Oops`/`WARNING` appears in
> `dmesg`. Continuing traffic after an IOMMU or Malicious Driver Detection fault masks the root-cause descriptor state.
> Stop the workload immediately, capture `dmesg -T | tail -n 40`, and resolve the root cause first.

---

## 1. Quick Symptom-to-Signature Triage Matrix (`3`-Column Zero-Scroll Layout)

Use a `3`-column triage matrix to map observable failure signatures to their root-cause section and verification
command:

| Failure ID & Observable Symptom | Primary Root-Cause Subsystem | Diagnostic Section & Fix Reference |
| --- | --- | --- |
| **`DIAG-01` — `DMAR` Fault on XSK Close**<br>`dmesg`: `DMAR: [DMA Write] Request device` | `ice` (`ICE_VSI_BIFURC` / `AF_XDP` UMEM unmap ordering) | See **Section 2.1** (`DRV-BIF-02` per-QSet `QRX_CTRL` quiesce before unmap). |
| **`DIAG-02` — `devlink reload` Hang**<br>INFO: task devlink: blocked > 120s | `ice` (`pf->lag_mutex` vs. `irdma` auxiliary bus `device_lock`) | See **Section 2.2** (`DRV-LAG-12` `cancel_work_sync` + workqueue flush). |
| **`DIAG-03` — `8x25G` LAG Recipe `-ENOSPC`**<br>`ice_add_adv_rule` returns `-28` | `ice` (`64`-recipe hardware switch limit exhausted at probe) | See **Section 2.3** (`HH-BR-003` lazy LAG recipe allocation patch). |

---

## 2. Diagnostic Playbook Entries (`Symptom -> Root Cause -> Verification -> Fix`)

Structure every troubleshooting entry using the mandatory `4`-bullet Diátaxis Reference pattern (`Rule D7-ARCH`):

### 2.1 `DIAG-01`: IOMMU `DMAR` Fault During Zero-Copy `AF_XDP` Subfunction Teardown

- **Symptom**: Closing an `AF_XDP` zero-copy socket on a bifurcated subfunction (`ice_sf_eth`) logs `DMAR: [DMA Write]`
  or `MDD` events in `dmesg -T`.
- **Root Cause**: The driver unmapped the XSK UMEM DMA pages against the auxiliary child device or before hardware RX/TX
  rings finished in-flight DMA completions.
- **Verification**: Inspect `dmesg -T` and check per-QSet ring enable registers:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

dmesg -T | grep -iE "DMAR|fault|DRHD|MDD|WARNING" | tail -n 20
```

- **Fix**: Map all `ICE_VSI_BIFURC` DMA addresses against `ice_pf_to_dev(pf)` (`DRV-BIF-01`) and poll per-QSet
  `QRX_CTRL(pf_q)` until disabled (`<= 50 us`) before unmapping UMEM (`DRV-BIF-02` / `HH-BR-002`).

---

### 2.2 `DIAG-02`: Deadlock or Workqueue Race During `devlink dev reload`

- **Symptom**: Running `devlink dev reload pci/${PCI_DEV}` hangs in `D` state when an `802.3ad` bond and `irdma`
  auxiliary device are active.
- **Root Cause**: `ice_lag_event_handler` work items or `pf->serv_task` run concurrently with `ice_devlink_reload_down`
  and contend on `pf->lag_mutex` and `device_lock`.
- **Verification**: Check blocked kernel stacks and verify the pre-bond `tx_scheduling_layers=5` sequence:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${PCI_DEV:?Specify PCI_DEV (e.g., 0000:b1:00.0)}"
timeout 2s devlink dev param show "pci/${PCI_DEV}" name tx_scheduling_layers
```

- **Fix**: Apply `DRV-LAG-12` (`set_bit(ICE_SERVICE_DIS, pf->state)`, `cancel_work_sync(&pf->serv_task)`, and
  `flush_workqueue(pf->lag->workqueue)` in `ice_devlink_reload_down`), and always configure `tx_scheduling_layers=5`
  before creating `bond0` (`HH-MR-001` / `HH-MR-023`).

---

### 2.3 `DIAG-03`: Switch Recipe Exhaustion (`-ENOSPC`) on `8x25G` Breakout Cards

- **Symptom**: Creating a `4`-bond LACP topology across an `8x25G` breakout adapter fails with `-ENOSPC` (`-28`) in
  `dmesg`.
- **Root Cause**: Pre-allocating LAG switch recipes across all `8` PFs at probe time exceeds the `64`-recipe hardware
  table on the **Intel® Ethernet Controller E835**.
- **Verification**: Read the active hardware switch recipe counter in `debugfs`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${PCI_DEV:?Specify PCI_DEV (e.g., 0000:b1:00.0)}"
cat "/sys/kernel/debug/ice/${PCI_DEV}/lag_recipes" 2>/dev/null || true
```

- **Fix**: Apply `ice-lag-recipe-limit-fix-v2.patch` so the driver allocates LAG recipes lazily only when a PF joins an
  active `bond0` master (`HH-BR-003`).

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_<wbr>04<wbr>_Troubleshooting_<wbr><wbr>and_<wbr>Root_Cause_<wbr>Playbook.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Troubleshooting Playbook Template`, `Diataxis Reference`, `DMAR=0 Gate`, `Symptom Root Cause Verification Fix`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `iavf`, `ICE_VSI_BIFURC`, `devlink`, `IOMMU`, `DMAR`, `MDD` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-PLAYBOOK-004`, `D1-D10 v3.2`, `HH-MR-001`, `HH-BR-002`, `HH-BR-003` |
<!-- METADATA_FOOTER_END -->
