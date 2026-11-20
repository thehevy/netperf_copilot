#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: dev/tools/netperf_report.py
# Created Date: 2026-11-05
# Last Updated Date: 2026-11-16
# Version: v2.0
# Status: Active
# Target Scope: AI-Driven Validation Schema Reporter, U1-U13 Event Scanner & Step 8/9 Telemetry Dashboard Generator
# Summary: Produces result.json, summary.csv, and compact zero-scroll Markdown dashboards with Step 8/9 pooled tail latency, per-flow core collision matrix, Intel PCM telemetry, and Flent working latency.
# === METADATA_HEADER_END ===
"""
netperf_report - AI-Driven Validation Schema Reporter, U1-U13 Event Scanner & Dashboard Generator

Produces:
1. result.json compliant with Intel_Ethernet_AI_Driven_Validation result.schema.json + Step 8/9 telemetry
2. U1-U13 unexpected kernel/driver/hardware event scan (kmsg/dmesg + ethtool -S deltas)
3. summary.csv and Markdown dashboard.md with Step 8/9 telemetry and ASCII throughput scaling bars
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from netperf_tunings import extract_non_default_tunings


# U1-U13 Unexpected Event Signatures from Intel_Ethernet_AI_Driven_Validation
UNEXPECTED_EVENT_PATTERNS: List[Tuple[str, str, str]] = [
    ("U1", "kernel_oops_bug", r"\b(BUG:|Oops:|Kernel panic|general protection fault)\b"),
    ("U2", "pcie_aer_error", r"\b(AER:|PCIe Bus Error|Uncorrectable.*Error)\b"),
    ("U3", "netdev_watchdog", r"NETDEV WATCHDOG:.*transmit queue \d+ timed out"),
    ("U4", "ice_tx_hang_mdd", r"\bice\b.*(Malicious Driver Detection|Tx hang|FW reset|EMP reset|rebuild failed)"),
    ("U5", "rdma_drv_qp_error", r"\brdma_drv\b.*(Async Event|AE_.*ERROR|QP fatal|CQP timeout)"),
    ("U6", "link_flap", r"(NIC Link is Down|carrier lost)"),
    ("U7", "page_alloc_failure", r"(page allocation failure:|Out of memory:)"),
    ("U8", "cpu_soft_lockup", r"(watchdog: BUG: soft lockup|rcu_sched self-detected stall)"),
    ("U9", "mce_hardware_error", r"(Machine check events logged|Hardware Error:)"),
    ("U10", "lacp_bond_flap", r"bond\d+:.*(link status definitely down|LACP.*timeout)"),
    ("U11", "pfc_storm_watchdog", r"(PFC storm|pfc_watchdog)"),
    ("U12", "thermal_throttle", r"(Package temperature above threshold|cpu clock throttled)"),
    ("U13", "irq_nobody_cared", r"irq \d+: nobody cared"),
]


CRITICAL_COUNTER_PATTERNS: Dict[str, str] = {
    "tx_restart_queue": r"^(?:tx_restart_queue|tx_busy)\s*:\s*(\d+)",
    "rx_dropped": r"^rx_dropped\s*:\s*(\d+)",
    "rx_missed_errors": r"^rx_missed_errors\s*:\s*(\d+)",
    "rx_crc_errors": r"^rx_crc_errors\s*:\s*(\d+)",
    "tx_errors": r"^tx_errors\s*:\s*(\d+)",
    "rx_xoff_frames": r"^rx_priority_\d+_xoff.*\s*:\s*(\d+)",
    "tx_xoff_frames": r"^tx_priority_\d+_xoff.*\s*:\s*(\d+)",
}


@dataclass
class UnexpectedEventMatch:
    code: str
    category: str
    line: str


def scan_kmsg_events(kmsg_text: str) -> List[UnexpectedEventMatch]:
    """Scan dmesg / /dev/kmsg text for U1-U13 unexpected kernel/driver events."""
    matches: List[UnexpectedEventMatch] = []
    for line in kmsg_text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        for code, category, pattern in UNEXPECTED_EVENT_PATTERNS:
            if re.search(pattern, line_str, re.IGNORECASE):
                matches.append(UnexpectedEventMatch(code=code, category=category, line=line_str))
    return matches


def parse_ethtool_stats(ethtool_s_output: str) -> Dict[str, int]:
    """Parse key error/stall/flow-control counters from `ethtool -S <if>` output."""
    totals: Dict[str, int] = {k: 0 for k in CRITICAL_COUNTER_PATTERNS}
    for line in ethtool_s_output.splitlines():
        s = line.strip()
        for key, pat in CRITICAL_COUNTER_PATTERNS.items():
            m = re.match(pat, s)
            if m:
                totals[key] += int(m.group(1))
    return totals


def compute_counter_deltas(
    before: Dict[str, int],
    after: Dict[str, int],
) -> Dict[str, int]:
    """Compute non-negative counter deltas between pre-test and post-test snapshots."""
    keys = set(before.keys()) | set(after.keys())
    return {k: max(0, int(after.get(k, 0)) - int(before.get(k, 0))) for k in sorted(keys)}


class AIValidationReporter:
    """Builds AI-Driven Validation result.json, summary.csv, and dashboard.md."""

    SCHEMA_VERSION = "1.1.0"

    STEP8_STEP9_KEYS: Tuple[str, ...] = (
        "steady_state_throughput_gbps",
        "pooled_p50_latency_us",
        "pooled_p90_latency_us",
        "pooled_p99_latency_us",
        "pooled_p999_latency_us",
        "worst_flow_p99_latency_us",
        "worst_flow_p999_latency_us",
        "jains_fairness_index",
        "core_overlap_count",
        "core_overlap_pct",
        "per_flow_core_matrix",
        "pcm_telemetry",
        "flent_working_latency",
    )

    @classmethod
    def extract_step8_step9_telemetry(cls, source: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Step 8/9 telemetry fields from a metrics or netperf-multi summary dictionary."""
        telemetry: Dict[str, Any] = {}
        for key in cls.STEP8_STEP9_KEYS:
            if key in source and source[key] is not None:
                telemetry[key] = source[key]
        return telemetry

    @classmethod
    def build_result_json(
        cls,
        test_case_id: str,
        suite_name: str,
        metrics: Dict[str, Any],
        environment: Optional[Dict[str, Any]] = None,
        kmsg_text: str = "",
        counter_deltas: Optional[Dict[str, int]] = None,
        target_gbps: float = 0.0,
        max_cv_pct: float = 5.0,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        duration_sec: float = 30.0,
        non_default_tunings: Optional[Dict[str, Any]] = None,
        explicit_tunings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        events = scan_kmsg_events(kmsg_text)
        deltas = counter_deltas or {}

        throughput_gbps = float(
            metrics.get("steady_state_throughput_gbps")
            or metrics.get("throughput_gbps", 0.0)
            or 0.0
        )
        cv_pct = float(metrics.get("cv_pct", 0.0) or 0.0)

        failure_reasons: List[str] = []
        warn_reasons: List[str] = []

        if events:
            codes = sorted({e.code for e in events})
            failure_reasons.append(f"Unexpected kernel/driver events: {', '.join(codes)}")

        if throughput_gbps <= 0.0 and float(metrics.get("transaction_rate_tps", 0.0) or 0.0) <= 0.0:
            failure_reasons.append("Zero throughput / transaction rate")
        elif target_gbps > 0.0 and throughput_gbps < target_gbps * 0.90:
            failure_reasons.append(
                f"Throughput {throughput_gbps:.2f} Gbps below 90% of target ({target_gbps:.2f} Gbps)"
            )
        elif target_gbps > 0.0 and throughput_gbps < target_gbps * 0.95:
            warn_reasons.append(
                f"Throughput {throughput_gbps:.2f} Gbps between 90-95% of target ({target_gbps:.2f} Gbps)"
            )

        if cv_pct > max_cv_pct:
            warn_reasons.append(f"Run-to-run CV {cv_pct:.2f}% exceeds {max_cv_pct:.1f}%")

        if deltas.get("rx_crc_errors", 0) > 0 or deltas.get("tx_errors", 0) > 0:
            failure_reasons.append("Physical/MAC error counters incremented during test")
        if deltas.get("tx_restart_queue", 0) > 1000:
            warn_reasons.append(f"High tx_restart_queue delta ({deltas['tx_restart_queue']})")

        if failure_reasons:
            verdict = "FAIL"
        elif warn_reasons:
            verdict = "WARN"
        else:
            verdict = "PASS"

        step8_9 = cls.extract_step8_step9_telemetry(metrics)
        if non_default_tunings is not None:
            tunings = non_default_tunings
        else:
            env_iface = (environment or {}).get("interface")
            ifaces = [env_iface] if env_iface and env_iface != "unknown" else None
            tunings = extract_non_default_tunings(interfaces=ifaces, explicit_overrides=explicit_tunings)

        return {
            "schema_version": cls.SCHEMA_VERSION,
            "test_case_id": test_case_id,
            "suite_name": suite_name,
            "verdict": verdict,
            "start_time": start_time or now_iso,
            "end_time": end_time or now_iso,
            "duration_sec": duration_sec,
            "environment": environment or {},
            "non_default_tunings": tunings,
            "metrics": metrics,
            "step8_step9_telemetry": step8_9,
            "counter_deltas": deltas,
            "unexpected_event_scan": {
                "passed": len(events) == 0,
                "event_count": len(events),
                "events": [asdict(e) for e in events],
            },
            "failure_signature": "; ".join(failure_reasons + warn_reasons) if (failure_reasons or warn_reasons) else None,
        }

    @staticmethod
    def render_summary_csv(rows: List[Dict[str, Any]]) -> str:
        """Render a list of test result dicts into a CSV string (including Step 8/9 telemetry columns)."""
        fieldnames = [
            "test_case_id",
            "direction",
            "streams",
            "mtu",
            "throughput_gbps",
            "steady_state_throughput_gbps",
            "tx_throughput_gbps",
            "rx_throughput_gbps",
            "pooled_p99_latency_us",
            "pooled_p999_latency_us",
            "worst_flow_p999_latency_us",
            "jains_fairness_index",
            "core_overlap_pct",
            "cv_pct",
            "verdict",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buf.getvalue()

    @staticmethod
    def render_dashboard_markdown(
        suite_name: str,
        rows: List[Dict[str, Any]],
        environment: Optional[Dict[str, Any]] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        non_default_tunings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Render a Markdown qualification dashboard with Step 8/9 telemetry and ASCII scaling bars."""
        lines: List[str] = [
            f"# Netperf Qualification Dashboard: `{suite_name}`",
            "",
        ]
        if environment:
            cpu = environment.get("cpu_model", "Unknown CPU")
            arch = environment.get("arch_type", "unknown")
            nic = environment.get("interface", "unknown")
            lines.append(f"- **Platform CPU**: {cpu} (`{arch}`)")
            lines.append(f"- **Interface**: `{nic}`")
            lines.append("")

        lines.extend([
            "## Summary Table",
            "",
            "| Test Case | Direction | Streams / MTU | Throughput (Gbps) | Verdict |",
            "| --- | --- | --- | --- | --- |",
        ])

        max_tput = max((float(r.get("throughput_gbps", 0.0) or 0.0) for r in rows), default=200.0)
        if max_tput <= 0:
            max_tput = 200.0

        for r in rows:
            tc = r.get("test_case_id", "test")
            direction = str(r.get("direction", "tx")).upper()
            streams = r.get("streams", 1)
            mtu = r.get("mtu", 9000)
            tput = float(r.get("throughput_gbps", 0.0) or 0.0)
            steady = r.get("steady_state_throughput_gbps")
            cv = float(r.get("cv_pct", 0.0) or 0.0)
            verdict = r.get("verdict", "PASS")
            tput_cell = f"{tput:.2f} Gbps (CV {cv:.2f}%)"
            if steady is not None:
                tput_cell += f"<br>Steady: {float(steady):.2f} Gbps"
            lines.append(
                f"| `{tc}` | {direction} | {streams}F / MTU {mtu} | {tput_cell} | **{verdict}** |"
            )

        # Aggregate Step 8/9 telemetry from explicit telemetry dict or rows
        merged_tel: Dict[str, Any] = dict(telemetry or {})
        for r in rows:
            for k in AIValidationReporter.STEP8_STEP9_KEYS:
                if k not in merged_tel and r.get(k) is not None:
                    merged_tel[k] = r[k]

        has_tail_or_steady = any(
            merged_tel.get(k) is not None
            for k in (
                "steady_state_throughput_gbps",
                "pooled_p99_latency_us",
                "pooled_p999_latency_us",
                "worst_flow_p999_latency_us",
                "jains_fairness_index",
                "core_overlap_pct",
            )
        )
        if has_tail_or_steady:
            lines.extend([
                "",
                "## Step 8/9 Pooled Tail Latency & Fairness Telemetry",
                "",
                "| Metric | Value | Notes |",
                "| --- | --- | --- |",
            ])
            if merged_tel.get("steady_state_throughput_gbps") is not None:
                lines.append(
                    f"| Steady-State Throughput (`--omit`) | {float(merged_tel['steady_state_throughput_gbps']):.2f} Gbps | Warm-up ramp excluded |"
                )
            if merged_tel.get("pooled_p99_latency_us") is not None:
                lines.append(
                    f"| Pooled p99 Latency | {float(merged_tel['pooled_p99_latency_us']):.2f} us | Transaction-weighted across flows |"
                )
            if merged_tel.get("pooled_p999_latency_us") is not None:
                lines.append(
                    f"| Pooled p99.9 Latency | {float(merged_tel['pooled_p999_latency_us']):.2f} us | 99.9th percentile tail latency |"
                )
            if merged_tel.get("worst_flow_p999_latency_us") is not None:
                lines.append(
                    f"| Worst-Flow p99.9 Latency | {float(merged_tel['worst_flow_p999_latency_us']):.2f} us | Straggler flow upper bound |"
                )
            if merged_tel.get("jains_fairness_index") is not None:
                lines.append(
                    f"| Jain's Fairness Index ($J$) | {float(merged_tel['jains_fairness_index']):.4f} | Inter-flow bandwidth balance |"
                )
            if merged_tel.get("core_overlap_pct") is not None:
                lines.append(
                    f"| Core Overlap (`core_overlap_pct`) | {float(merged_tel['core_overlap_pct']):.1f}% | Same-core / SMT / IRQ collision rate |"
                )

        core_matrix = merged_tel.get("per_flow_core_matrix")
        if isinstance(core_matrix, list) and core_matrix:
            lines.extend([
                "",
                "## Per-Flow Core Residency & Collision Matrix",
                "",
                "| Flow ID | CPU (`target` -> `exec`) | Throughput & Tail (`p99` / `p99.9`) | Collision Status |",
                "| --- | --- | --- | --- |",
            ])
            for entry in core_matrix:
                if not isinstance(entry, dict):
                    continue
                fid = entry.get("flow_id", "F00")
                t_cpu = entry.get("target_cpu", "unpinned")
                e_cpu = entry.get("exec_cpu", -1)
                fgbps = float(entry.get("throughput_gbps", 0.0) or 0.0)
                fp99 = float(entry.get("p99_latency_us", 0.0) or 0.0)
                fp999 = float(entry.get("p999_latency_us", 0.0) or 0.0)
                ctype = entry.get("collision_type", "NONE")
                outlier_tag = " (**OUTLIER**)" if entry.get("is_outlier") else ""
                lines.append(
                    f"| `{fid}` | `{t_cpu}` -> `{e_cpu}` | {fgbps:.2f} Gbps (`{fp99:.1f}` / `{fp999:.1f}` us) | `{ctype}`{outlier_tag} |"
                )

        pcm = merged_tel.get("pcm_telemetry")
        if isinstance(pcm, dict) and pcm:
            lines.extend([
                "",
                "## Intel® PCM Hardware Telemetry",
                "",
                "| Hardware Counter Metric | Value | Architectural Target |",
                "| --- | --- | --- |",
                f"| DDIO / LLC Hit Ratio (`ddio_hit_pct`) | {float(pcm.get('ddio_hit_pct', 0.0) or 0.0):.2f}% | `>= 95.0%` on local NUMA node |",
                f"| Cross-Socket UPI Traffic (`upi_traffic_gbps`) | {float(pcm.get('upi_traffic_gbps', 0.0) or 0.0):.2f} GB/s | `< 0.50 GB/s` (zero remote DMA) |",
                f"| Total DRAM Bandwidth (`total_dram_gbps`) | {float(pcm.get('total_dram_gbps', 0.0) or 0.0):.2f} GB/s | Minimal LLC miss spill |",
                f"| Package Power (`package_watts`) | {float(pcm.get('package_watts', 0.0) or 0.0):.1f} W | Efficiency: {float(pcm.get('gbps_per_watt', 0.0) or 0.0):.4f} Gbps/W |",
            ])

        flent = merged_tel.get("flent_working_latency")
        if isinstance(flent, dict) and flent:
            lines.extend([
                "",
                "## Flent Working Latency Under Load",
                "",
                "| Percentile | Latency (ms) |",
                "| --- | --- |",
                f"| Median (`p50_ms`) | {float(flent.get('p50_ms', 0.0) or 0.0):.3f} ms |",
                f"| 99th Percentile (`p99_ms`) | {float(flent.get('p99_ms', 0.0) or 0.0):.3f} ms |",
                f"| 99.9th Percentile (`p999_ms`) | {float(flent.get('p999_ms', 0.0) or 0.0):.3f} ms |",
            ])

        tunings_block = non_default_tunings or merged_tel.get("non_default_tunings")
        summary_rows = tunings_block.get("summary_rows") if isinstance(tunings_block, dict) else None
        if summary_rows:
            lines.extend([
                "",
                "## Active Non-Default Tunings",
                "",
                "| Parameter | Active Value | Baseline Default |",
                "| --- | --- | --- |",
            ])
            for item in summary_rows:
                lines.append(
                    f"| `{item.get('parameter', '')}` | `{item.get('value', '')}` | `{item.get('default', '')}` |"
                )

        lines.extend([
            "",
            "## Throughput Scaling Chart",
            "",
            "```text",
        ])
        for r in rows:
            tc = str(r.get("test_case_id", "test"))[:28].ljust(28)
            tput = float(r.get("throughput_gbps", 0.0) or 0.0)
            bar_len = int(round((tput / max_tput) * 40)) if max_tput > 0 else 0
            bar = "#" * max(0, min(40, bar_len))
            lines.append(f"{tc} | {bar:<40} {tput:7.2f} Gbps")
        lines.append("```")
        lines.append("")
        return "\n".join(lines)


# === METADATA_FOOTER_START ===
# Search Keywords: netperf_report, AIValidationReporter, Step 8/9 telemetry, pooled_p999_latency_us, per_flow_core_matrix, pcm_telemetry
# Drivers & Subsystems: ice, irdma, mlx5_core, idpf, netperf, nettest_omni.c
# Related Units / Patches: COLLAB-012, DOC-WP-NETPERF-COPILOT-BENCHMARK-STUDY-001
# Created / Last-Updated: 2026-11-05 / 2026-11-16
# === METADATA_FOOTER_END ===
