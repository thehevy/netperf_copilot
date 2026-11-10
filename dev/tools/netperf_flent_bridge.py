#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: dev/tools/netperf_flent_bridge.py
# Created Date: 2026-11-10
# Last Updated Date: 2026-11-10
# Version: v3.2
# Status: Active
# Target Scope: netperf_copilot High-Speed 100GbE-400GbE Flent v3 Working-Latency & Step-Burst Bridge
# Summary: Generic open-source Flent v3 (.flent.gz) time-series and working-latency (RRUL) bridge powered by Modernized Netperf v3.0 OMNI (-M -- -J, -D interval demo, -T CPU pinning, -Y DSCP, -Z zero-copy).
# === METADATA_HEADER_END ===
"""Flent v3 Working-Latency (RRUL) & Burst-Convergence Bridge for Modernized Netperf v3.0.

Provides topology-aware stream specifications, interim `-D` + final `-M -- -J` output
parsing, Jain's fairness index calculation, and standard Flent v3 `.flent.gz` export
for 100GbE-400GbE Linux `net_dim` working-latency and step-burst evaluations.
"""
from __future__ import annotations

import datetime
import gzip
import json
import math
import os
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional

DSCP_TOS_MAP: Dict[str, str] = {
    "CS0": "0x00",
    "BE": "0x00",
    "CS1": "0x20",
    "AF11": "0x28",
    "AF21": "0x48",
    "CS3": "0x60",
    "AF31": "0x68",
    "CS4": "0x80",
    "AF41": "0x88",
    "CS5": "0xa0",
    "EF": "0xb8",
    "CS6": "0xc0",
}

OMNI_LATENCY_SELECTORS = (
    "THROUGHPUT,THROUGHPUT_UNITS,ELAPSED_TIME,TRANS_RATE,"
    "RT_LATENCY,MIN_LATENCY,MAX_LATENCY,P50_LATENCY,P90_LATENCY,P99_LATENCY,STDDEV_LATENCY,"
    "LOCAL_SEND_RETRANS,LOCAL_CPU_UTIL,REMOTE_CPU_UTIL,LOCAL_SD,REMOTE_SD,UUID"
)

INTERIM_DEMO_RE = re.compile(
    r"Interim result:\s*([0-9.]+)\s*(\S+)?\s*after\s*([0-9.]+)\s*seconds(?:\s*ending at\s*([0-9.]+))?",
    re.IGNORECASE,
)


def resolve_tos_hex(dscp_or_tos: str) -> str:
    """Resolves symbolic DSCP ('EF', 'AF21', 'CS1', 'CS0') or hex string to '0xNN,0xNN'."""
    if not dscp_or_tos:
        return ""
    spec = str(dscp_or_tos).strip()
    if "," in spec:
        left, right = spec.split(",", 1)
        return f"{resolve_tos_hex(left).split(',')[0]},{resolve_tos_hex(right).split(',')[0]}"
    upper = spec.upper()
    if upper in DSCP_TOS_MAP:
        hx = DSCP_TOS_MAP[upper]
        return f"{hx},{hx}"
    if upper.startswith("0X"):
        return f"{spec.lower()},{spec.lower()}"
    if spec.isdigit():
        val = int(spec)
        hx = f"0x{(val & 0x3f) << 2:02x}" if val <= 63 else f"0x{val & 0xff:02x}"
        return f"{hx},{hx}"
    return f"{spec},{spec}"


def compute_jains_fairness_index(values: List[float]) -> float:
    """Computes Jain's Fairness Index: (sum(x_i))^2 / (n * sum(x_i^2)) in [0.0, 1.0]."""
    clean = [float(v) for v in values if v is not None and float(v) >= 0.0]
    n = len(clean)
    if n == 0:
        return 0.0
    denom = n * sum(x * x for x in clean)
    if denom <= 0.0:
        return 0.0
    total = sum(clean)
    return round((total * total) / denom, 6)


def allocate_topology_core_pairs(
    numa_cpus: List[int],
    num_bulk_tx: int,
    num_bulk_rx: int,
    num_rr_probes: int,
    is_l2_clustered: bool = False,
    irq_reserved_count: int = 0,
) -> Dict[str, List[int]]:
    """Partitions NUMA-local physical CPUs into disjoint pools for Bulk TX, Bulk RX, and RR probes."""
    avail = list(numa_cpus[irq_reserved_count:]) if irq_reserved_count < len(numa_cpus) else list(numa_cpus)
    if not avail:
        avail = list(range(0, max(16, num_bulk_tx + num_bulk_rx + num_rr_probes)))

    if is_l2_clustered:
        even_stride = [c for idx, c in enumerate(avail) if idx % 2 == 0]
        odd_stride = [c for idx, c in enumerate(avail) if idx % 2 == 1]
        ordered = even_stride + odd_stride
    else:
        ordered = avail

    def _take(start_idx: int, count: int) -> List[int]:
        return [ordered[(start_idx + i) % len(ordered)] for i in range(count)]

    return {
        "bulk_tx_cores": _take(0, num_bulk_tx),
        "bulk_rx_cores": _take(num_bulk_tx, num_bulk_rx),
        "rr_probe_cores": _take(num_bulk_tx + num_bulk_rx, num_rr_probes),
    }


@dataclass
class ModernNetperfStreamSpec:
    """Specification for a single Modernized Netperf v3.0 stream inside a Flent test."""

    stream_id: str
    role: str  # 'bulk_tx', 'bulk_rx', 'rr_tcp', 'rr_udp'
    host: str
    local_ip: str = ""
    interface: str = ""
    duration_sec: float = 10.0
    delay_start_sec: float = 0.0
    step_interval_sec: float = 0.2
    local_cpu: Optional[int] = None
    remote_cpu: Optional[int] = None
    control_port: int = 12865
    data_port: Optional[int] = None
    dscp: str = "CS0"
    zerocopy: bool = False
    msg_size_bytes: int = 0
    req_resp_size: str = "1,1"
    use_modern_omni: bool = True
    netperf_bin: str = "netperf"

    def build_command(self) -> List[str]:
        """Builds the Modernized Netperf v3.0 command with interim demo (-D) and JSON/OMNI selectors."""
        cmd: List[str] = []
        if self.delay_start_sec > 0:
            cmd.extend(["sleep", f"{self.delay_start_sec:.2f}", "&&"])

        cmd.append(self.netperf_bin)
        cmd.extend(["-H", self.host])
        if self.local_ip:
            cmd.extend(["-L", self.local_ip])
        if self.control_port:
            cmd.extend(["-p", str(self.control_port)])

        if self.step_interval_sec > 0:
            cmd.extend(["-D", f"{self.step_interval_sec:.2f}"])

        cmd.extend(["-l", str(int(math.ceil(self.duration_sec)))])

        if self.local_cpu is not None and self.remote_cpu is not None:
            cmd.extend(["-T", f"{self.local_cpu},{self.remote_cpu}"])
        elif self.local_cpu is not None:
            cmd.extend(["-T", str(self.local_cpu)])

        if self.dscp:
            cmd.extend(["-Y", resolve_tos_hex(self.dscp)])

        if self.zerocopy and self.role in ("bulk_tx", "bulk_rx"):
            cmd.append("-Z")

        if self.use_modern_omni:
            cmd.append("-M")
        else:
            legacy_map = {
                "bulk_tx": "TCP_STREAM",
                "bulk_rx": "TCP_MAERTS",
                "rr_tcp": "TCP_RR",
                "rr_udp": "UDP_RR",
            }
            cmd.extend(["-t", legacy_map.get(self.role, "TCP_STREAM")])

        cmd.append("--")
        if self.use_modern_omni:
            if self.role == "bulk_tx":
                cmd.extend(["-d", "stream", "-T", "tcp"])
            elif self.role == "bulk_rx":
                cmd.extend(["-d", "maerts", "-T", "tcp"])
            elif self.role == "rr_udp":
                cmd.extend(["-d", "rr", "-T", "udp", "-r", self.req_resp_size])
            else:
                cmd.extend(["-d", "rr", "-T", "tcp", "-r", self.req_resp_size])
            cmd.extend(["-J", "-k", OMNI_LATENCY_SELECTORS])
        else:
            if self.role in ("rr_tcp", "rr_udp"):
                cmd.extend(["-r", self.req_resp_size, "-k", OMNI_LATENCY_SELECTORS])

        if self.msg_size_bytes > 0 and self.role in ("bulk_tx", "bulk_rx"):
            cmd.extend(["-m", str(self.msg_size_bytes)])

        if self.data_port is not None:
            cmd.extend(["-P", f"{self.data_port},{self.data_port}"])

        return cmd


def parse_modern_netperf_output(raw_stdout: str, start_epoch: float = 0.0) -> Dict[str, Any]:
    """Parses both interim `-D` time-series samples and the final Modernized Netperf JSON/KeyVal payload."""
    samples: List[Dict[str, float]] = []
    elapsed_cursor = 0.0

    for line in (raw_stdout or "").splitlines():
        m = INTERIM_DEMO_RE.search(line)
        if m:
            val = float(m.group(1))
            dt = float(m.group(3))
            end_ts = float(m.group(4)) if m.group(4) else (start_epoch + elapsed_cursor + dt)
            elapsed_cursor += dt
            samples.append({"t": round(end_ts, 4), "elapsed": round(elapsed_cursor, 4), "val": val})
            continue
        if line.startswith("NETPERF_INTERIM_RESULT"):
            val_m = re.search(r"(?:=\s*|\[)([0-9.]+)\s*$", line)
            if val_m:
                samples.append(
                    {
                        "t": round(start_epoch + (len(samples) + 1) * 0.2, 4),
                        "elapsed": round((len(samples) + 1) * 0.2, 4),
                        "val": float(val_m.group(1)),
                    }
                )

    summary: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

    text = (raw_stdout or "").strip()
    brace_idx = text.find("{")
    if brace_idx >= 0:
        try:
            parsed = json.loads(text[brace_idx:])
            if isinstance(parsed, dict):
                if isinstance(parsed.get("results"), dict):
                    summary.update(parsed["results"])
                else:
                    summary.update(parsed)
                if isinstance(parsed.get("metadata"), dict):
                    metadata.update(parsed["metadata"])
                    for k, v in metadata.items():
                        summary.setdefault(k, v)
        except Exception:
            pass

    if not summary:
        for line in text.splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                try:
                    summary[k] = float(v)
                except ValueError:
                    summary[k] = v

    return {
        "samples": samples,
        "summary": summary,
        "metadata": metadata,
    }


def build_flent_gz_payload(
    test_name: str,
    title: str,
    duration_sec: float,
    step_sec: float,
    dut_host: str,
    lp_host: str,
    interface: str,
    stream_results: Dict[str, Dict[str, Any]],
    hw_telemetry_samples: Optional[List[Dict[str, Any]]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Formats Modernized Netperf + NIC hardware telemetry into a Flent v3 `.flent.gz` schema."""
    num_steps = max(1, int(math.ceil(duration_sec / max(step_sec, 0.05))))
    x_values = [round((i + 1) * step_sec, 3) for i in range(num_steps)]

    results_series: Dict[str, List[Optional[float]]] = {}
    raw_values: Dict[str, List[Dict[str, Any]]] = {}

    bulk_tx_grid = [0.0] * num_steps
    bulk_rx_grid = [0.0] * num_steps
    rr_tps_grid: List[List[float]] = [[] for _ in range(num_steps)]

    for sid, sdata in stream_results.items():
        role = sdata.get("role", "bulk_tx")
        samples = sdata.get("samples", [])
        raw_values[sid] = samples
        delay_start_sec = float(sdata.get("delay_start_sec", 0.0) or 0.0)
        start_idx = max(0, min(num_steps, int(round(delay_start_sec / max(step_sec, 0.05)))))
        dur_sec = float(sdata.get("duration_sec", duration_sec - delay_start_sec) or (duration_sec - delay_start_sec))
        max_stream_steps = max(0, min(num_steps - start_idx, int(math.ceil(dur_sec / max(step_sec, 0.05)))))

        grid: List[Optional[float]] = [0.0 if role in ("bulk_tx", "bulk_rx") and start_idx > 0 else None] * num_steps
        for rel_idx, pt in enumerate(samples[:max_stream_steps]):
            idx = start_idx + rel_idx
            if idx >= num_steps:
                break
            val = float(pt.get("val", 0.0))
            grid[idx] = val
            if role == "bulk_tx":
                bulk_tx_grid[idx] += val
            elif role == "bulk_rx":
                bulk_rx_grid[idx] += val
            elif role in ("rr_tcp", "rr_udp") and val > 0:
                rr_tps_grid[idx].append(val)

        summ = sdata.get("summary", {})
        fallback_val = float(summ.get("THROUGHPUT", summ.get("TRANS_RATE", 0.0)) or 0.0)
        if not samples and fallback_val > 0:
            for idx in range(start_idx, min(num_steps, start_idx + max_stream_steps)):
                grid[idx] = fallback_val
                if role == "bulk_tx":
                    bulk_tx_grid[idx] += fallback_val
                elif role == "bulk_rx":
                    bulk_rx_grid[idx] += fallback_val
                elif role in ("rr_tcp", "rr_udp"):
                    rr_tps_grid[idx].append(fallback_val)

        results_series[sid] = grid

    results_series["TCP upload sum"] = [round(v, 3) for v in bulk_tx_grid]
    results_series["TCP download sum"] = [round(v, 3) for v in bulk_rx_grid]
    results_series["TCP bidirectional sum"] = [
        round(bulk_tx_grid[i] + bulk_rx_grid[i], 3) for i in range(num_steps)
    ]

    rr_rtt_ms_series: List[Optional[float]] = []
    for bucket in rr_tps_grid:
        if bucket:
            mean_tps = mean(bucket)
            rr_rtt_ms_series.append(round(1000.0 / mean_tps, 4) if mean_tps > 0 else None)
        else:
            rr_rtt_ms_series.append(None)
    results_series["Ping (ms) avg"] = rr_rtt_ms_series

    if hw_telemetry_samples:
        irq_series: List[Optional[float]] = [None] * num_steps
        rx_itr_series: List[Optional[float]] = [None] * num_steps
        for idx, hw in enumerate(hw_telemetry_samples[:num_steps]):
            irq_series[idx] = hw.get("irqs_per_sec")
            rx_itr_series[idx] = hw.get("rx_usecs")
        results_series["NIC IRQ/s"] = irq_series
        results_series["NIC RX ITR (us)"] = rx_itr_series
        raw_values["nic_hw_telemetry"] = hw_telemetry_samples

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "VERSION": 3,
        "NAME": test_name,
        "TITLE": title,
        "TIME": now_iso,
        "LOCAL_HOST": dut_host,
        "HOST": lp_host,
        "INTERFACE": interface,
        "TOTAL_LENGTH": duration_sec,
        "STEP_SIZE": step_sec,
        "ENGINE": "Modernized Netperf v3.0 (netperf_copilot OMNI) + Flent v3 Bridge",
    }
    if extra_metadata:
        meta.update(extra_metadata)

    return {
        "version": 3,
        "x_values": x_values,
        "results": results_series,
        "raw_values": raw_values,
        "metadata": meta,
    }


def save_flent_gz(payload: Dict[str, Any], out_path: str) -> str:
    """Writes a Flent v3 payload to disk as `.flent.gz` (or `.json` if not `.gz`)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    raw_bytes = json.dumps(payload, indent=2).encode("utf-8")
    if out_path.endswith(".gz"):
        with gzip.open(out_path, "wb") as gf:
            gf.write(raw_bytes)
    else:
        with open(out_path, "wb") as f:
            f.write(raw_bytes)
    return out_path


# === METADATA_FOOTER_START ===
# Search Keywords: netperf_copilot, Flent v3, RRUL, Working Latency, Burst Convergence, OMNI, net_dim
# Drivers & Subsystems: ice, net_dim, netperf, netserver, flent
# Related Units / Patches: DOC-NETPERF-FLENT-V3-INTEGRATION, D1-D10 v3.2
# Created / Last-Updated: 2026-11-10 / 2026-11-10
# === METADATA_FOOTER_END ===
