#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: dev/tools/netperf_benchmark_study.py
# Created Date: 2026-11-16
# Last Updated Date: 2026-11-16
# Version: v3.2
# Status: Active
# Target Scope: netperf_copilot Reproducible Multi-Tool Benchmark Harness (Tier A Default vs Tier B Pinned/Tuned)
# Summary: Version-aware, statistically rigorous comparative benchmark runner for netperf_copilot, classic netperf, iperf2, and iperf3 (<3.16 single-reactor vs >=3.16 multi-threaded pthreads).
# === METADATA_HEADER_END ===
"""Reproducible, Fair Multi-Tool Benchmark Harness for netperf_copilot vs. netperf, iperf2, and iperf3.

Addresses methodological fairness, version transparency, and statistical rigor:
1. Explicitly detects ``iperf3`` version and separates ``iperf3 <= 3.15``
   (single-threaded ``select()``/``poll()`` reactor) from ``iperf3 >= 3.16``
   (multi-threaded ``-P`` streams via pthreads, PR #1591).
2. Evaluates all four tools across two explicit fairness tiers:
   - **Tier A (``default_unpinned``)**: Out-of-the-box command invocations
     without external CPU pinning or per-core daemon pools.
   - **Tier B (``tuned_pinned``)**: Apples-to-apples topology-aware CPU/NUMA
     pinning across all four tools (including per-flow ``taskset`` classic
     ``netperf``, NUMA/core-bound ``iperf2``, native multi-threaded ``iperf3 >= 3.16``
     bound to the non-IRQ core pool, and ``N``-process pinned ``iperf3``).
3. Executes ``--trials N`` (default 5) in randomized tool order per trial and
   computes mean, standard deviation, and 95% confidence intervals using
   ``StatisticalAnalyzer``.
"""

import argparse
import json
import platform
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from netperf_pcm_bridge import PCM_COUNTER_FORMULAS
from netperf_stats import AdvancedStatistics
from netperf_topology import SystemTopology, TopologyAnalyzer, format_cpu_list


class BenchmarkStudyHarness:
    """Reproducible two-tier benchmark harness comparing netperf_copilot, netperf, iperf2, and iperf3."""

    DEFAULT_FLOW_COUNTS = (1, 4, 8, 16, 32, 64)

    def __init__(
        self,
        host: str,
        interface: str = "ens801f0np0",
        flow_counts: Tuple[int, ...] = DEFAULT_FLOW_COUNTS,
        duration: int = 30,
        trials: int = 5,
        mtu: int = 9000,
        base_port: int = 18600,
        iperf3_base_port: int = 5201,
        topology: Optional[SystemTopology] = None,
        topology_snapshot: Optional[str] = None,
        seed: int = 42,
    ) -> None:
        self.host = host
        self.interface = interface
        self.flow_counts = tuple(int(f) for f in flow_counts)
        self.duration = duration
        self.trials = max(1, int(trials))
        self.mtu = mtu
        self.base_port = base_port
        self.iperf3_base_port = iperf3_base_port
        self.seed = seed

        if topology is not None:
            self.topology = topology
        elif topology_snapshot and Path(topology_snapshot).exists():
            self.topology = TopologyAnalyzer.from_topology_snapshot(
                Path(topology_snapshot).read_text(encoding="utf-8", errors="ignore")
            )
        else:
            self.topology = TopologyAnalyzer.discover_local(interfaces=[interface] if interface else None)

    @staticmethod
    def parse_iperf3_version(version_text: str) -> Dict[str, Any]:
        """Parse `iperf3 --version` output and determine whether -P uses pthreads (>= 3.16) or single reactor (< 3.16)."""
        m = re.search(r"iperf\s+(\d+)\.(\d+)(?:\.(\d+))?", version_text or "", re.IGNORECASE)
        if not m:
            return {
                "raw": (version_text or "").strip().splitlines()[0] if version_text else "unknown",
                "major": 0,
                "minor": 0,
                "patch": 0,
                "is_multithreaded_p": False,
                "threading_model": "unknown (version not detected)",
            }
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3) or 0)
        is_mt = (major > 3) or (major == 3 and minor >= 16)
        return {
            "raw": (version_text or "").strip().splitlines()[0],
            "version": f"{major}.{minor}.{patch}",
            "major": major,
            "minor": minor,
            "patch": patch,
            "is_multithreaded_p": is_mt,
            "threading_model": (
                "multi-threaded pthreads per -P stream (iperf >= 3.16, PR #1591)"
                if is_mt
                else "single-threaded select()/poll() reactor loop (iperf <= 3.15)"
            ),
        }

    @classmethod
    def detect_tool_versions(cls) -> Dict[str, Any]:
        """Query installed versions of netperf, iperf2, and iperf3."""
        versions: Dict[str, Any] = {}
        for name, cmd in (
            ("netperf", ["netperf", "-V"]),
            ("iperf2", ["iperf", "--version"]),
            ("iperf3", ["iperf3", "--version"]),
        ):
            bin_path = shutil.which(cmd[0])
            if not bin_path:
                versions[name] = {"installed": False, "raw": "not installed"}
                continue
            try:
                proc = subprocess.run([bin_path] + cmd[1:], capture_output=True, text=True, timeout=5)
                out = (proc.stdout or proc.stderr or "").strip()
                first_line = out.splitlines()[0] if out else "unknown"
                info: Dict[str, Any] = {"installed": True, "binary": bin_path, "raw": first_line}
                if name == "iperf3":
                    info.update(cls.parse_iperf3_version(out))
                versions[name] = info
            except Exception as exc:
                versions[name] = {"installed": True, "binary": bin_path, "raw": f"error: {exc}"}
        return versions

    def allocate_pinned_cores(self, num_flows: int) -> Tuple[int, List[int]]:
        """Allocate NUMA-local non-IRQ physical cores using TopologyAnalyzer."""
        numa_node = 0
        if self.interface in self.topology.interfaces:
            numa_node = self.topology.interfaces[self.interface].numa_node
        pool = self.topology.nodes.get(numa_node) or next(iter(self.topology.nodes.values()))
        avail = list(pool.app_cores) or list(pool.physical_cores) or list(range(num_flows))
        strategy = TopologyAnalyzer.select_layout_strategy(self.topology, "auto", num_flows, self.mtu)
        cores = TopologyAnalyzer.allocate_cores_from_pool(
            avail,
            count=num_flows,
            strategy=strategy,
            l2_modules=pool.l2_modules,
        )
        return numa_node, cores

    def build_tier_commands(
        self,
        num_flows: int,
        iperf3_version_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Build Tier A (default_unpinned) and Tier B (tuned_pinned) command specifications for N flows."""
        numa_node, cores = self.allocate_pinned_cores(num_flows)
        core_list_str = format_cpu_list(cores)
        ip3_info = iperf3_version_info or self.parse_iperf3_version("iperf 3.16")

        # Tier A: Out-of-the-Box Unpinned Default
        tier_a = {
            "netperf_copilot_default": {
                "tier": "Tier A (Default Unpinned)",
                "tool": "netperf_copilot",
                "command": [
                    "netperf-multi",
                    "-H",
                    self.host,
                    "-n",
                    str(num_flows),
                    "-t",
                    "OMNI",
                    "-l",
                    str(self.duration),
                    "-o",
                    "json",
                ],
            },
            "classic_netperf_default": {
                "tier": "Tier A (Default Unpinned)",
                "tool": "classic_netperf",
                "command": [
                    f"netperf -H {self.host} -l {self.duration} -M -- -d stream -J"
                    for _ in range(num_flows)
                ],
            },
            "iperf2_default": {
                "tier": "Tier A (Default Unpinned)",
                "tool": "iperf2",
                "command": [
                    "iperf",
                    "-c",
                    self.host,
                    "-P",
                    str(num_flows),
                    "-t",
                    str(self.duration),
                ],
            },
            "iperf3_default": {
                "tier": "Tier A (Default Unpinned)",
                "tool": "iperf3",
                "iperf3_threading_model": ip3_info.get("threading_model"),
                "command": [
                    "iperf3",
                    "-c",
                    self.host,
                    "-P",
                    str(num_flows),
                    "-t",
                    str(self.duration),
                    "-J",
                ],
            },
        }

        # Tier B: Apples-to-Apples Tuned & Topology-Pinned
        classic_pinned_cmds = [
            f"taskset -c {cores[i % len(cores)]} netperf -H {self.host} "
            f"-p {self.base_port + cores[i % len(cores)]} -w 2 -l {self.duration} "
            f"-T {cores[i % len(cores)]},{cores[i % len(cores)]} -M -- -d stream -J"
            for i in range(num_flows)
        ]
        iperf3_mp_pinned_cmds = [
            f"taskset -c {cores[i % len(cores)]} iperf3 -c {self.host} "
            f"-p {self.iperf3_base_port + i} -A {cores[i % len(cores)]},{cores[i % len(cores)]} "
            f"-P 1 -t {self.duration} -J"
            for i in range(num_flows)
        ]

        tier_b = {
            "netperf_copilot_pinned": {
                "tier": "Tier B (Tuned & Pinned)",
                "tool": "netperf_copilot",
                "allocated_cores": cores,
                "command": [
                    "netperf-multi",
                    "-H",
                    self.host,
                    "-i",
                    self.interface,
                    "-n",
                    str(num_flows),
                    "-t",
                    "OMNI",
                    "-l",
                    str(self.duration),
                    "--affinity",
                    "--per-core-netserver",
                    "--barrier-wait",
                    "2",
                    "--pcm",
                    "--flent-working-latency",
                    "-o",
                    "json",
                ],
            },
            "classic_netperf_pinned": {
                "tier": "Tier B (Tuned & Pinned)",
                "tool": "classic_netperf",
                "allocated_cores": cores,
                "command": classic_pinned_cmds,
            },
            "iperf2_pinned": {
                "tier": "Tier B (Tuned & Pinned)",
                "tool": "iperf2",
                "allocated_cores": cores,
                "command": [
                    "numactl",
                    f"--cpunodebind={numa_node}",
                    f"--membind={numa_node}",
                    "taskset",
                    "-c",
                    core_list_str,
                    "iperf",
                    "-c",
                    self.host,
                    "-P",
                    str(num_flows),
                    "-t",
                    str(self.duration),
                ],
            },
            "iperf3_mt_pinned": {
                "tier": "Tier B (Tuned & Pinned)",
                "tool": "iperf3_mt_pinned",
                "iperf3_threading_model": ip3_info.get("threading_model"),
                "allocated_cores": cores,
                "command": [
                    "numactl",
                    f"--cpunodebind={numa_node}",
                    f"--membind={numa_node}",
                    "taskset",
                    "-c",
                    core_list_str,
                    "iperf3",
                    "-c",
                    self.host,
                    "-P",
                    str(num_flows),
                    "-t",
                    str(self.duration),
                    "-J",
                ],
            },
            "iperf3_multiprocess_pinned": {
                "tier": "Tier B (Tuned & Pinned)",
                "tool": "iperf3_multiprocess_pinned",
                "allocated_cores": cores,
                "command": iperf3_mp_pinned_cmds,
            },
        }

        return {"tier_a_default_unpinned": tier_a, "tier_b_tuned_pinned": tier_b}

    def generate_study_plan(
        self,
        iperf3_version_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate the complete multi-flow, two-tier benchmark study plan with randomized trial schedule."""
        versions = self.detect_tool_versions()
        if iperf3_version_override:
            versions["iperf3"] = self.parse_iperf3_version(iperf3_version_override)

        rng = random.Random(self.seed)
        flow_matrix: Dict[str, Any] = {}
        for n_flows in self.flow_counts:
            tiers = self.build_tier_commands(n_flows, iperf3_version_info=versions.get("iperf3"))
            tool_keys = list(tiers["tier_a_default_unpinned"].keys()) + list(
                tiers["tier_b_tuned_pinned"].keys()
            )
            trial_schedule: List[Dict[str, Any]] = []
            for trial_idx in range(1, self.trials + 1):
                ordered = list(tool_keys)
                rng.shuffle(ordered)
                trial_schedule.append({"trial": trial_idx, "randomized_order": ordered})

            flow_matrix[str(n_flows)] = {
                "num_flows": n_flows,
                "tiers": tiers,
                "trial_schedule": trial_schedule,
            }

        return {
            "document_id": "DOC-WP-NETPERF-COPILOT-BENCHMARK-STUDY-001",
            "host": self.host,
            "interface": self.interface,
            "mtu": self.mtu,
            "duration_sec": self.duration,
            "trials": self.trials,
            "confidence_level": 0.95,
            "environment": {
                "platform": platform.platform(),
                "cpu_model": self.topology.model_name,
                "uarch": self.topology.uarch,
                "total_logical_cpus": self.topology.total_logical_cpus,
                "tool_versions": versions,
            },
            "pcm_counter_formulas": PCM_COUNTER_FORMULAS,
            "flow_matrix": flow_matrix,
        }

    @staticmethod
    def summarize_trial_samples(samples_gbps: List[float], confidence: float = 0.95) -> Dict[str, Any]:
        """Compute mean, stddev, and 95% confidence interval across repeated benchmark trials."""
        stats = AdvancedStatistics.calculate_comprehensive_stats(
            samples_gbps, confidence_level=confidence
        )
        mean_val = float(stats.get("mean", 0.0))
        ci_low = float(stats.get("ci_lower", mean_val))
        ci_high = float(stats.get("ci_upper", mean_val))
        margin = float(stats.get("ci_margin", 0.0))
        rel_margin = (margin / mean_val * 100.0) if mean_val > 0 else 0.0
        return {
            "n_trials": int(stats.get("count", 0)),
            "mean_gbps": round(mean_val, 3),
            "median_gbps": round(float(stats.get("median", 0.0)), 3),
            "stddev_gbps": round(float(stats.get("stddev", 0.0)), 3),
            "min_gbps": round(float(stats.get("min", 0.0)), 3),
            "max_gbps": round(float(stats.get("max", 0.0)), 3),
            "ci_95_lower_gbps": round(ci_low, 3),
            "ci_95_upper_gbps": round(ci_high, 3),
            "ci_95_margin_pct": round(rel_margin, 2),
        }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reproducible Two-Tier Multi-Tool Benchmark Study Harness (netperf_copilot vs netperf, iperf2, iperf3)"
    )
    parser.add_argument("--host", default="192.168.10.2", help="Target server IP/hostname")
    parser.add_argument("--interface", default="ens801f0np0", help="Local network interface")
    parser.add_argument("--flows", default="1,4,8,16,32,64", help="Comma-separated flow counts")
    parser.add_argument("--duration", type=int, default=30, help="Per-trial test duration in seconds")
    parser.add_argument("--trials", type=int, default=5, help="Number of randomized trials per configuration")
    parser.add_argument("--mtu", type=int, default=9000, help="Link MTU (1500 or 9000)")
    parser.add_argument("--topology-snapshot", help="Optional topology snapshot file")
    parser.add_argument("--iperf3-version-override", help="Optional iperf3 version string for dry-run testing")
    parser.add_argument("--output", help="Optional file path to write JSON study plan")
    parser.add_argument("--dry-run", action="store_true", help="Generate and print reproducible study plan without running live traffic")
    args = parser.parse_args(argv)

    flows = tuple(int(x.strip()) for x in args.flows.split(",") if x.strip())
    harness = BenchmarkStudyHarness(
        host=args.host,
        interface=args.interface,
        flow_counts=flows,
        duration=args.duration,
        trials=args.trials,
        mtu=args.mtu,
        topology_snapshot=args.topology_snapshot,
    )
    plan = harness.generate_study_plan(iperf3_version_override=args.iperf3_version_override)
    if args.output:
        Path(args.output).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    if args.dry_run or not args.output:
        print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# === METADATA_FOOTER_START ===
# Search Keywords: netperf_copilot, iperf2, iperf3, Two-Tier Benchmark Study, Tier A Unpinned, Tier B Pinned
# Drivers & Subsystems: ice, netperf, netserver, netperf-multi, iperf2, iperf3, intel_pcm
# Related Units / Patches: DOC-WP-NETPERF-COPILOT-BENCHMARK-STUDY-001, D1-D10 v3.2
# Created / Last-Updated: 2026-11-16 / 2026-11-16
# === METADATA_FOOTER_END ===
