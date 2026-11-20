#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: dev/tools/netperf_tunings.py
# Created Date: 2026-11-20
# Last Updated Date: 2026-11-20
# Version: v1.0
# Status: Active
# Target Scope: netperf_copilot Host & NIC Non-Default Tuning Provenance Collector
# Summary: Probes and diffs Linux sysctl, kernel cmdline, CPU/IRQ, driver module, NIC ethtool/tc, and CLI execution overrides against baseline defaults so every benchmark result records active non-default tunings.
# === METADATA_HEADER_END ===
"""Host & NIC non-default tuning collector for `netperf_copilot` reports and sweeps."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

BASELINE_SYSCTL_DEFAULTS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "net.ipv4.tcp_notsent_lowat": ("4294967295", ("4294967295",)),
    "net.ipv4.tcp_limit_output_bytes": ("1048576", ("262144", "1048576")),
    "net.core.netdev_budget": ("300", ("300",)),
    "net.core.netdev_budget_usecs": ("2000", ("2000",)),
    "net.core.gro_normal_batch": ("8", ("8",)),
    "net.core.netdev_max_backlog": ("1000", ("1000",)),
    "net.core.rmem_max": ("212992", ("212992",)),
    "net.core.wmem_max": ("212992", ("212992",)),
    "net.core.rmem_default": ("212992", ("212992",)),
    "net.core.wmem_default": ("212992", ("212992",)),
    "net.core.optmem_max": ("81920", ("20480", "81920")),
    "net.core.somaxconn": ("4096", ("128", "4096")),
    "net.core.busy_poll": ("0", ("0",)),
    "net.core.busy_read": ("0", ("0",)),
    "net.core.default_qdisc": ("fq_codel", ("pfifo_fast", "fq_codel")),
    "net.ipv4.tcp_rmem": ("4096 131072 6291456", ("4096 87380 6291456", "4096 131072 6291456")),
    "net.ipv4.tcp_wmem": ("4096 16384 4194304", ("4096 16384 4194304", "4096 65536 4194304")),
    "net.ipv4.tcp_congestion_control": ("cubic", ("cubic",)),
    "net.ipv4.tcp_mtu_probing": ("0", ("0",)),
    "net.ipv4.tcp_slow_start_after_idle": ("1", ("1",)),
    "net.ipv4.tcp_fastopen": ("1", ("1",)),
    "net.ipv4.tcp_no_metrics_save": ("0", ("0",)),
    "net.ipv4.tcp_moderate_rcvbuf": ("1", ("1",)),
    "net.ipv4.tcp_window_scaling": ("1", ("1",)),
    "net.ipv4.ip_forward": ("0", ("0",)),
    "kernel.numa_balancing": ("1", ("1",)),
    "vm.swappiness": ("60", ("60",)),
    "vm.zone_reclaim_mode": ("0", ("0",)),
}

NON_DEFAULT_CMDLINE_PREFIXES: Tuple[str, ...] = (
    "iommu=",
    "intel_iommu=",
    "amd_iommu=",
    "isolcpus=",
    "nohz_full=",
    "rcu_nocbs=",
    "irqaffinity=",
    "mitigations=",
    "intel_idle.",
    "processor.max_cstate=",
    "idle=",
    "default_hugepagesz=",
    "hugepagesz=",
    "hugepages=",
)


def _norm(val: Any) -> str:
    return " ".join(str(val).strip().split())


def _run_short(cmd: List[str], timeout_sec: float = 2.0) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
        return proc.stdout.strip()
    except Exception:
        return ""


def collect_local_raw_tunings(
    interfaces: Optional[Sequence[str]] = None,
    driver_modules: Sequence[str] = ("ice", "irdma", "mlx5_core", "idpf"),
) -> Dict[str, Any]:
    """Probe local Linux kernel, sysctl, platform, and NIC state cleanly."""
    if not sys.platform.startswith("linux"):
        return {"probe_supported": False, "platform": sys.platform}

    sysctls: Dict[str, str] = {}
    for key in BASELINE_SYSCTL_DEFAULTS:
        p = pathlib.Path("/proc/sys") / key.replace(".", "/")
        if p.exists():
            try:
                sysctls[key] = _norm(p.read_text(errors="replace"))
            except OSError:
                pass

    cmdline = ""
    cp = pathlib.Path("/proc/cmdline")
    if cp.exists():
        try:
            cmdline = _norm(cp.read_text(errors="replace"))
        except OSError:
            pass

    govs = sorted({
        g.read_text(errors="replace").strip()
        for g in pathlib.Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor")
        if g.exists()
    })
    irqbalance = _run_short(["systemctl", "is-active", "irqbalance"]) or "unknown"

    mod_params: Dict[str, Dict[str, str]] = {}
    for mod in driver_modules:
        pdir = pathlib.Path(f"/sys/module/{mod}/parameters")
        if pdir.is_dir():
            mp: Dict[str, str] = {}
            for pf in sorted(pdir.iterdir()):
                try:
                    mp[pf.name] = pf.read_text(errors="replace").strip()
                except OSError:
                    pass
            if mp:
                mod_params[mod] = mp

    nics: Dict[str, Dict[str, Any]] = {}
    for dev in (interfaces or []):
        dev = str(dev).strip()
        if not dev:
            continue
        nd = pathlib.Path(f"/sys/class/net/{dev}")
        if not nd.exists():
            continue
        entry: Dict[str, Any] = {}
        for fname, key in (("mtu", "mtu"), ("tx_queue_len", "txqueuelen")):
            fp = nd / fname
            if fp.exists():
                val = fp.read_text(errors="replace").strip()
                entry[key] = int(val) if val.isdigit() else val
        ipl = _run_short(["ip", "-d", "-j", "link", "show", "dev", dev])
        if ipl.startswith("["):
            try:
                d0 = json.loads(ipl)[0]
                entry["gso_max_size"] = d0.get("gso_max_size")
                entry["gro_max_size"] = d0.get("gro_max_size")
                entry["qdisc"] = d0.get("qdisc")
            except Exception:
                pass
        el = _run_short(["ethtool", "-l", dev])
        cur_sec = pre_sec = False
        for ln in el.splitlines():
            s = ln.strip()
            if s.startswith("Pre-set maximums:"):
                pre_sec, cur_sec = True, False
            elif s.startswith("Current hardware settings:"):
                cur_sec, pre_sec = True, False
            elif s.startswith("Combined:"):
                toks = s.split()
                if len(toks) >= 2 and toks[1].isdigit():
                    entry["channels_max" if pre_sec else "channels_combined"] = int(toks[1])
        eg = _run_short(["ethtool", "-g", dev])
        cur_sec = pre_sec = False
        for ln in eg.splitlines():
            s = ln.strip()
            if s.startswith("Pre-set maximums:"):
                pre_sec, cur_sec = True, False
            elif s.startswith("Current hardware settings:"):
                cur_sec, pre_sec = True, False
            elif cur_sec and s.startswith(("RX:", "TX:")):
                k, v = s.split(":", 1)
                if v.strip().isdigit():
                    entry[f"ring_{k.lower()}"] = int(v.strip())
        ec = _run_short(["ethtool", "-c", dev])
        coal: Dict[str, Any] = {}
        for ln in ec.splitlines():
            s = ln.strip()
            if "Adaptive RX:" in s:
                coal["adaptive_rx"] = "on" if "Adaptive RX: on" in s else "off"
                coal["adaptive_tx"] = "on" if "Adaptive TX: on" in s else "off"
            elif s.startswith(("rx-usecs:", "tx-usecs:", "rx-usecs-high:")):
                k, v = s.split(":", 1)
                coal[k.replace("-", "_")] = int(v.strip()) if v.strip().isdigit() else v.strip()
        if coal:
            entry["coalesce"] = coal
        nics[dev] = entry

    return {
        "probe_supported": True,
        "platform": sys.platform,
        "sysctls": sysctls,
        "cmdline": cmdline,
        "cpu_governors": govs,
        "irqbalance": irqbalance,
        "module_params": mod_params,
        "nics": nics,
    }


def extract_non_default_tunings(
    raw_probe: Optional[Mapping[str, Any]] = None,
    interfaces: Optional[Sequence[str]] = None,
    explicit_overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute non-default tunings against Linux defaults and merge explicit overrides."""
    raw = dict(raw_probe) if raw_probe is not None else collect_local_raw_tunings(interfaces=interfaces)

    sysctls_raw = raw.get("sysctls") or {}
    sysctl_overrides: Dict[str, Dict[str, str]] = {}
    for key, (canon_def, accepted_defs) in BASELINE_SYSCTL_DEFAULTS.items():
        if key not in sysctls_raw:
            continue
        actual = _norm(sysctls_raw[key])
        if actual not in accepted_defs:
            sysctl_overrides[key] = {"value": actual, "default": canon_def}

    exp_sysctls = (explicit_overrides or {}).get("sysctls")
    if isinstance(exp_sysctls, Mapping):
        for key, val in exp_sysctls.items():
            actual = _norm(sysctls_raw.get(key, val))
            canon_def = BASELINE_SYSCTL_DEFAULTS.get(str(key), ("kernel_default", ()))[0]
            if actual != canon_def and str(key) not in sysctl_overrides:
                sysctl_overrides[str(key)] = {"value": actual, "default": canon_def}

    cmdline_flags = [
        tok for tok in str(raw.get("cmdline") or "").split() if tok.startswith(NON_DEFAULT_CMDLINE_PREFIXES)
    ]

    nic_overrides: Dict[str, Dict[str, Any]] = {}
    for dev, ninfo in (raw.get("nics") or {}).items():
        if not isinstance(ninfo, Mapping):
            continue
        ov: Dict[str, Any] = {}
        mtu = ninfo.get("mtu")
        if mtu is not None and mtu != 1500:
            ov["mtu"] = {"value": mtu, "default": 1500}
        qlen = ninfo.get("txqueuelen")
        if qlen is not None and qlen != 1000:
            ov["txqueuelen"] = {"value": qlen, "default": 1000}
        for skey in ("gso_max_size", "gro_max_size"):
            if ninfo.get(skey) is not None and ninfo.get(skey) != 65536:
                ov[skey] = {"value": ninfo[skey], "default": 65536}
        qdisc = ninfo.get("qdisc")
        if qdisc and qdisc not in ("fq_codel", "mq"):
            ov["qdisc"] = {"value": qdisc, "default": "fq_codel/mq"}
        if ninfo.get("channels_combined") is not None and ninfo.get("channels_max") is not None:
            if ninfo["channels_combined"] != ninfo["channels_max"]:
                ov["channels_combined"] = {
                    "value": ninfo["channels_combined"],
                    "default": ninfo["channels_max"],
                }
        for rk in ("ring_rx", "ring_tx"):
            if ninfo.get(rk) is not None and ninfo.get(rk) != 2048:
                ov[rk] = {"value": ninfo[rk], "default": 2048}
        if ninfo.get("coalesce"):
            ov["coalesce"] = ninfo["coalesce"]
        if ov:
            nic_overrides[str(dev)] = ov

    platform_overrides: Dict[str, Any] = {}
    if cmdline_flags:
        platform_overrides["cmdline_flags"] = cmdline_flags
    govs = raw.get("cpu_governors") or []
    if govs and any(g not in ("powersave", "schedutil") for g in govs):
        platform_overrides["cpu_governors"] = {"value": govs, "default": ["powersave/schedutil"]}
    irqbal = str(raw.get("irqbalance") or "").strip()
    if irqbal and irqbal != "active" and raw.get("probe_supported"):
        platform_overrides["irqbalance"] = {"value": irqbal, "default": "active"}

    cleaned_explicit: Dict[str, Any] = {}
    if explicit_overrides:
        for k, v in explicit_overrides.items():
            if k == "sysctls" or v is None or v == "" or v == [] or v == {}:
                continue
            cleaned_explicit[str(k)] = v

    summary_rows: List[Dict[str, str]] = []
    for k, info in sorted(sysctl_overrides.items()):
        summary_rows.append({
            "parameter": f"sysctl:{k}",
            "value": str(info.get("value", "")),
            "default": str(info.get("default", "")),
        })
    for dev, nov in sorted(nic_overrides.items()):
        for k, info in sorted(nov.items()):
            if isinstance(info, Mapping) and "value" in info:
                val_s, def_s = str(info["value"]), str(info.get("default", "default"))
            else:
                val_s, def_s = json.dumps(info, sort_keys=True), "driver_default"
            summary_rows.append({"parameter": f"nic:{dev}.{k}", "value": val_s, "default": def_s})
    if cmdline_flags:
        summary_rows.append({"parameter": "kernel:cmdline", "value": " ".join(cmdline_flags), "default": "(none)"})
    if "cpu_governors" in platform_overrides:
        summary_rows.append({
            "parameter": "cpu:governor",
            "value": ",".join(platform_overrides["cpu_governors"]["value"]),
            "default": "powersave/schedutil",
        })
    if "irqbalance" in platform_overrides:
        summary_rows.append({
            "parameter": "service:irqbalance",
            "value": str(platform_overrides["irqbalance"]["value"]),
            "default": "active",
        })
    for k, v in sorted(cleaned_explicit.items()):
        summary_rows.append({"parameter": f"run:{k}", "value": str(v), "default": "auto/default"})

    return {
        "probe_supported": bool(raw.get("probe_supported", False)),
        "sysctl_overrides": sysctl_overrides,
        "nic_overrides": nic_overrides,
        "platform_overrides": platform_overrides,
        "driver_module_params": raw.get("module_params") or {},
        "explicit_overrides": cleaned_explicit,
        "summary_rows": summary_rows,
    }


# === METADATA_FOOTER_START ===
# Search Keywords: netperf_tunings, non_default_tunings, sysctl_overrides, nic_overrides, provenance
# Drivers & Subsystems: ice, irdma, mlx5_core, idpf, sysctl, ethtool
# Related Units / Patches: RULE-NON-DEFAULT-TUNINGS
# Created / Last-Updated: 2026-11-20 / 2026-11-20
# === METADATA_FOOTER_END ===
