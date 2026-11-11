#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: scripts/surgical_host_coexistence.py
# Created Date: 2026-11-11
# Last Updated Date: 2026-11-11
# Version: v1.0
# Status: Production Validated
# Target Scope: Generic Linux 100GbE-800GbE Network & Power Coexistence Utility
# Summary: Configures per-core PM QoS resume latency, scoped irqbalance interrupt shielding, NUMA balancing scan amortization, and per-interface NAPI deferral for high-speed Linux network benchmarking without host-wide collateral damage.
# === METADATA_HEADER_END ===
"""Generic Linux Surgical Network & Power Coexistence Utility (`surgical_host_coexistence.py`).

Replaces host-wide sledgehammer overrides (`systemctl stop irqbalance`, `kernel.numa_balancing=0`,
and global `/dev/cpu_dma_latency=0`) with scoped per-interface and per-CPU Linux kernel controls:

1. Per-Core PM QoS Resume Latency (`pm_qos_resume_latency_us`):
   In upstream Linux `drivers/base/power/sysfs.c` (`pm_qos_resume_latency_us_store()`):
   - Writing `"n/a"` sets `PM_QOS_RESUME_LATENCY_NO_CONSTRAINT_VALUE` (`0 us`), which forces the CPU
     into `C0` polling and blocks deep idle states (`C6`).
   - Writing `"0"` sets `PM_QOS_RESUME_LATENCY_NO_CONSTRAINT` (`S32_MAX`), allowing non-datapath
     CPUs to enter deep package/core sleep states (`C6`).
   This utility writes `"10"` (`10 us`, permitting `C1`/`C1E` while blocking `C6` exit latency)
   strictly to CPUs servicing `${NETDEV}` queues, and `"0"` (`NO_CONSTRAINT`) to all other CPUs.

2. Active `irqbalance` Coexistence Shield (`IRQBALANCE_BANNED_INTERRUPTS`):
   Discovers MSI-X IRQ numbers for target `${NETDEV}` interfaces via
   `/sys/class/net/${NETDEV}/device/msi_irqs` and `/proc/interrupts`, emitting
   `IRQBALANCE_BANNED_INTERRUPTS` so `irqbalance` remains active for storage and housekeeping IRQs
   without migrating pinned network queues.

3. Scoped `kernel.numa_balancing` Scan Rate Amortization & NAPI Deferral:
   Keeps `kernel.numa_balancing=1` active for background workloads while tuning
   `/sys/kernel/debug/sched/numa_balancing/scan_delay_ms=5000` and `scan_period_min_ms=2000`,
   and sets per-interface `napi_defer_hard_irqs=2` and `gro_flush_timeout=20000`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Set


def parse_cpu_list(cpu_spec: str) -> Set[int]:
    """Parse a Linux CPU list string (e.g., '0-3,8,12-15') into a set of CPU IDs."""
    cpus: Set[int] = set()
    for part in cpu_spec.strip().split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            cpus.update(range(int(lo_s), int(hi_s) + 1))
        else:
            cpus.add(int(part))
    return cpus


def discover_netdev_irqs(netdev: str, sysfs_root: Path = Path("/sys")) -> List[int]:
    """Return sorted MSI-X IRQ numbers associated with `netdev`."""
    irqs: Set[int] = set()
    msi_dir = sysfs_root / "class" / "net" / netdev / "device" / "msi_irqs"
    if msi_dir.is_dir():
        for entry in msi_dir.iterdir():
            if entry.name.isdigit():
                irqs.add(int(entry.name))
    proc_irqs = Path("/proc/interrupts")
    if proc_irqs.is_file():
        pattern = re.compile(rf"\b{re.escape(netdev)}(?:[-_:]|\b)")
        for line in proc_irqs.read_text(encoding="utf-8", errors="ignore").splitlines():
            if pattern.search(line):
                head = line.split(":", 1)[0].strip()
                if head.isdigit():
                    irqs.add(int(head))
    return sorted(irqs)


def discover_netdev_irq_cpus(netdev: str) -> Set[int]:
    """Return the set of CPUs pinned to `netdev` IRQs via `effective_affinity_list` or `smp_affinity_list`."""
    cpus: Set[int] = set()
    for irq in discover_netdev_irqs(netdev):
        for fname in ("effective_affinity_list", "smp_affinity_list"):
            aff_file = Path(f"/proc/irq/{irq}/{fname}")
            if aff_file.is_file():
                try:
                    cpus.update(parse_cpu_list(aff_file.read_text(encoding="utf-8")))
                    break
                except (OSError, ValueError):
                    continue
    return cpus


def configure_per_core_pm_qos(
    datapath_cpus: Set[int],
    active_latency_us: int = 10,
    dry_run: bool = False,
    sysfs_cpu_root: Path = Path("/sys/devices/system/cpu"),
) -> Dict[str, object]:
    """Set `pm_qos_resume_latency_us` to `active_latency_us` on datapath CPUs and `'0'` (`NO_CONSTRAINT`) elsewhere."""
    updated_active: List[int] = []
    updated_idle: List[int] = []
    if sysfs_cpu_root.is_dir():
        for cpu_dir in sorted(sysfs_cpu_root.glob("cpu[0-9]*")):
            m = re.match(r"^cpu(\d+)$", cpu_dir.name)
            if not m:
                continue
            cpu_id = int(m.group(1))
            qos_path = cpu_dir / "power" / "pm_qos_resume_latency_us"
            target_val = str(active_latency_us) if cpu_id in datapath_cpus else "0"
            if cpu_id in datapath_cpus:
                updated_active.append(cpu_id)
            else:
                updated_idle.append(cpu_id)
            if not dry_run and qos_path.is_file():
                try:
                    qos_path.write_text(target_val, encoding="utf-8")
                except OSError:
                    pass
    return {
        "active_latency_us": str(active_latency_us),
        "non_datapath_value": "0",
        "datapath_cpus": sorted( updated_active or list(datapath_cpus) ),
        "non_datapath_cpu_count": len(updated_idle),
        "sysfs_note": "Writing '0' sets PM_QOS_RESUME_LATENCY_NO_CONSTRAINT (deep C6 enabled); never write 'n/a' (0 us C0 poll).",
    }


def build_irqbalance_env(netdevs: List[str]) -> Dict[str, object]:
    """Generate `IRQBALANCE_BANNED_INTERRUPTS` environment configuration for `netdevs`."""
    banned_irqs: Set[int] = set()
    for dev in netdevs:
        banned_irqs.update(discover_netdev_irqs(dev))
    irq_str = " ".join(str(i) for i in sorted(banned_irqs))
    return {
        "netdevs": netdevs,
        "banned_irqs": sorted(banned_irqs),
        "env_line": f'IRQBALANCE_BANNED_INTERRUPTS="{irq_str}"',
    }


def configure_numa_and_napi(
    netdevs: List[str],
    scan_delay_ms: int = 5000,
    scan_period_min_ms: int = 2000,
    napi_defer_hard_irqs: int = 2,
    gro_flush_timeout: int = 20000,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Configure `kernel.numa_balancing` scan amortization and per-interface NAPI deferral."""
    actions: List[str] = [
        "sysctl -w kernel.numa_balancing=1",
        f"echo {scan_delay_ms} > /sys/kernel/debug/sched/numa_balancing/scan_delay_ms",
        f"echo {scan_period_min_ms} > /sys/kernel/debug/sched/numa_balancing/scan_period_min_ms",
    ]
    if not dry_run and os.name == "posix" and os.geteuid() == 0:
        subprocess.run(
            ["sysctl", "-qw", "kernel.numa_balancing=1"],
            capture_output=True,
            text=True,
            timeout=2.0,
            shell=False,
        )
        nb_dir = Path("/sys/kernel/debug/sched/numa_balancing")
        if nb_dir.is_dir():
            for name, val in (
                ("scan_delay_ms", scan_delay_ms),
                ("scan_period_min_ms", scan_period_min_ms),
            ):
                p = nb_dir / name
                if p.is_file():
                    try:
                        p.write_text(str(val), encoding="utf-8")
                    except OSError:
                        pass

    for dev in netdevs:
        actions.append(f"echo {napi_defer_hard_irqs} > /sys/class/net/{dev}/napi_defer_hard_irqs")
        actions.append(f"echo {gro_flush_timeout} > /sys/class/net/{dev}/gro_flush_timeout")
        if not dry_run:
            for attr, val in (
                ("napi_defer_hard_irqs", napi_defer_hard_irqs),
                ("gro_flush_timeout", gro_flush_timeout),
            ):
                p = Path(f"/sys/class/net/{dev}/{attr}")
                if p.is_file():
                    try:
                        p.write_text(str(val), encoding="utf-8")
                    except OSError:
                        pass

    return {
        "numa_balancing": 1,
        "scan_delay_ms": scan_delay_ms,
        "scan_period_min_ms": scan_period_min_ms,
        "napi_defer_hard_irqs": napi_defer_hard_irqs,
        "gro_flush_timeout": gro_flush_timeout,
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure generic Linux surgical network & power coexistence for high-speed netperf benchmarking."
    )
    parser.add_argument(
        "--netdev",
        "-i",
        default=os.environ.get("NETDEV", "eth0"),
        help="Comma-separated network interface names (default: ${NETDEV} or eth0).",
    )
    parser.add_argument(
        "--cpus",
        default="",
        help="Optional explicit datapath CPU list (e.g. '0-15'). Auto-detected from IRQ affinity if omitted.",
    )
    parser.add_argument(
        "--latency-us",
        type=int,
        default=10,
        help="Per-core PM QoS resume latency in microseconds for active datapath CPUs (default: 10).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned configuration in JSON without writing to /sys or /proc.",
    )
    args = parser.parse_args()

    netdevs = [d.strip() for d in args.netdev.split(",") if d.strip()]
    datapath_cpus: Set[int] = parse_cpu_list(args.cpus) if args.cpus else set()
    if not datapath_cpus:
        for dev in netdevs:
            datapath_cpus.update(discover_netdev_irq_cpus(dev))

    report = {
        "pm_qos": configure_per_core_pm_qos(
            datapath_cpus=datapath_cpus,
            active_latency_us=args.latency_us,
            dry_run=args.dry_run,
        ),
        "irqbalance": build_irqbalance_env(netdevs),
        "numa_and_napi": configure_numa_and_napi(netdevs, dry_run=args.dry_run),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# === METADATA_FOOTER_START ===
# Search Keywords: surgical_host_coexistence, pm_qos_resume_latency_us, irqbalance, numa_balancing, napi_defer_hard_irqs
# Drivers & Subsystems: linux, cpuidle, irqbalance, sched/numa, netdev
# Related Units / Patches: DOC-NETPERF-README
# Created / Last-Updated: 2026-11-11 / 2026-11-11
# === METADATA_FOOTER_END ===
