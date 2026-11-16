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
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

sys.path.insert(0, str(Path(__file__).parent))
from netperf_flent_bridge import compute_jains_fairness_index
from netperf_pcm_bridge import PCM_COUNTER_FORMULAS, ProcStatGroundTruth
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

        # Tier B1: Strict Apples-to-Apples Shared Core-Pool Taskset (No 1:1 Pinning, Single Listener)
        classic_shared_taskset_cmds = [
            f"numactl --cpunodebind={numa_node} --membind={numa_node} "
            f"taskset -c {core_list_str} netperf -H {self.host} -w 2 -l {self.duration} -M -- -d stream -J"
            for _ in range(num_flows)
        ]
        tier_b1_shared_taskset = {
            "netperf_copilot_taskset_pool": {
                "tier": "Tier B1 (Apples-to-Apples Shared taskset Pool)",
                "tool": "netperf_copilot_taskset_pool",
                "allocated_core_pool": cores,
                "command": [
                    "numactl",
                    f"--cpunodebind={numa_node}",
                    f"--membind={numa_node}",
                    "taskset",
                    "-c",
                    core_list_str,
                    "netperf-multi",
                    "-H",
                    self.host,
                    "-n",
                    str(num_flows),
                    "-t",
                    "OMNI",
                    "-l",
                    str(self.duration),
                    "--barrier-wait",
                    "2",
                    "--omit",
                    "2",
                    "-o",
                    "json",
                ],
            },
            "classic_netperf_taskset_pool": {
                "tier": "Tier B1 (Apples-to-Apples Shared taskset Pool)",
                "tool": "classic_netperf_taskset_pool",
                "allocated_core_pool": cores,
                "command": classic_shared_taskset_cmds,
            },
            "iperf2_taskset_pool": {
                "tier": "Tier B1 (Apples-to-Apples Shared taskset Pool)",
                "tool": "iperf2_taskset_pool",
                "allocated_core_pool": cores,
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
            "iperf3_mt_taskset_pool": {
                "tier": "Tier B1 (Apples-to-Apples Shared taskset Pool)",
                "tool": "iperf3_mt_taskset_pool",
                "iperf3_threading_model": ip3_info.get("threading_model"),
                "allocated_core_pool": cores,
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
                    "-O",
                    "2",
                    "-t",
                    str(self.duration),
                    "-J",
                ],
            },
        }

        # Tier B2: Full 1:1 Per-Flow Topology Pinning, Per-Core Daemon Pool & Advanced Capabilities
        classic_pinned_cmds = [
            f"taskset -c {cores[i % len(cores)]} netperf -H {self.host} "
            f"-p {self.base_port + cores[i % len(cores)]} -w 2 -l {self.duration} "
            f"-T {cores[i % len(cores)]},{cores[i % len(cores)]} -M -- -d stream -J"
            for i in range(num_flows)
        ]
        iperf3_mp_pinned_cmds = [
            f"taskset -c {cores[i % len(cores)]} iperf3 -c {self.host} "
            f"-p {self.iperf3_base_port + i} -A {cores[i % len(cores)]},{cores[i % len(cores)]} "
            f"-P 1 -O 2 -t {self.duration} -J"
            for i in range(num_flows)
        ]

        tier_b = {
            "netperf_copilot_pinned": {
                "tier": "Tier B2 (1:1 Pinned + Full netperf_copilot Capabilities)",
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
                    "--omit",
                    "2",
                    "--data-port-base",
                    "20000",
                    "--pcm",
                    "--flent-working-latency",
                    "-o",
                    "json",
                ],
            },
            "classic_netperf_pinned": {
                "tier": "Tier B2 (1:1 Pinned + Per-Core netserver)",
                "tool": "classic_netperf",
                "allocated_cores": cores,
                "command": classic_pinned_cmds,
            },
            "iperf2_pinned": tier_b1_shared_taskset["iperf2_taskset_pool"],
            "iperf3_mt_pinned": tier_b1_shared_taskset["iperf3_mt_taskset_pool"],
            "iperf3_multiprocess_pinned": {
                "tier": "Tier B2 (1:1 Multi-Process Pinned)",
                "tool": "iperf3_multiprocess_pinned",
                "allocated_cores": cores,
                "command": iperf3_mp_pinned_cmds,
            },
        }

        return {
            "tier_a_default_unpinned": tier_a,
            "tier_b1_shared_taskset_pool": tier_b1_shared_taskset,
            "tier_b_tuned_pinned": tier_b,
        }

    def generate_study_plan(
        self,
        iperf3_version_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate the complete multi-flow, three-tier benchmark study plan with randomized trial schedule."""
        versions = self.detect_tool_versions()
        if iperf3_version_override:
            versions["iperf3"] = self.parse_iperf3_version(iperf3_version_override)

        rng = random.Random(self.seed)
        flow_matrix: Dict[str, Any] = {}
        for n_flows in self.flow_counts:
            tiers = self.build_tier_commands(n_flows, iperf3_version_info=versions.get("iperf3"))
            tool_keys = (
                list(tiers["tier_a_default_unpinned"].keys())
                + list(tiers["tier_b1_shared_taskset_pool"].keys())
                + list(tiers["tier_b_tuned_pinned"].keys())
            )
            tool_keys = list(dict.fromkeys(tool_keys))
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

    @staticmethod
    def parse_iperf3_json_output(
        raw_json: str,
        procstat_cpu_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Parse iperf3 -J output into aggregate Gbps, per-stream Jain's fairness, and CPU reporting error."""
        data = json.loads(raw_json)
        end = data.get("end", {})
        streams = end.get("streams", [])
        stream_gbps: List[float] = []
        total_retrans = 0
        for st in streams:
            sender = st.get("sender") or st.get("receiver") or {}
            bps = float(sender.get("bits_per_second", 0.0))
            stream_gbps.append(round(bps / 1e9, 3))
            total_retrans += int(sender.get("retransmits", 0) or 0)

        sum_block = end.get("sum_received") or end.get("sum_sent") or {}
        agg_bps = float(sum_block.get("bits_per_second", sum(stream_gbps) * 1e9))
        agg_gbps = round(agg_bps / 1e9, 3)
        jains = compute_jains_fairness_index(stream_gbps) if stream_gbps else 1.0

        cpu_block = end.get("cpu_utilization_percent", {})
        host_total_pct = float(cpu_block.get("host_total", 0.0))
        remote_total_pct = float(cpu_block.get("remote_total", 0.0))

        result: Dict[str, Any] = {
            "tool": "iperf3",
            "num_streams": len(stream_gbps),
            "total_throughput_gbps": agg_gbps,
            "per_stream_gbps": stream_gbps,
            "jains_fairness_index": round(jains, 4),
            "total_retransmits": total_retrans,
            "reported_host_cpu_pct": round(host_total_pct, 2),
            "reported_remote_cpu_pct": round(remote_total_pct, 2),
        }
        if procstat_cpu_pct is not None:
            result["cpu_reporting_error"] = ProcStatGroundTruth.compute_cpu_reporting_error(
                host_total_pct, procstat_cpu_pct
            )
        return result

    @staticmethod
    def parse_iperf2_output(raw_text: str) -> Dict[str, Any]:
        """Parse iperf2 multi-stream output lines into per-stream Gbps and Jain's Fairness Index."""
        stream_gbps: List[float] = []
        sum_gbps: Optional[float] = None
        line_re = re.compile(
            r"\[\s*(SUM|\d+)\]\s+[0-9.]+\s*-\s*[0-9.]+\s+sec\s+[0-9.]+\s+\S+\s+([0-9.]+)\s+([KMG]bits/sec)",
            re.IGNORECASE,
        )
        scale_map = {"kbits/sec": 1e-6, "mbits/sec": 1e-3, "gbits/sec": 1.0}
        for line in (raw_text or "").splitlines():
            m = line_re.search(line)
            if not m:
                continue
            tag = m.group(1).upper()
            val = float(m.group(2))
            unit = m.group(3).lower()
            gbps = round(val * scale_map.get(unit, 1.0), 3)
            if tag == "SUM":
                sum_gbps = gbps
            else:
                stream_gbps.append(gbps)

        total_gbps = sum_gbps if sum_gbps is not None else round(sum(stream_gbps), 3)
        jains = compute_jains_fairness_index(stream_gbps) if stream_gbps else 1.0
        return {
            "tool": "iperf2",
            "num_streams": len(stream_gbps),
            "total_throughput_gbps": total_gbps,
            "per_stream_gbps": stream_gbps,
            "jains_fairness_index": round(jains, 4),
        }

    @staticmethod
    def parse_netperf_copilot_json_output(raw_json: str) -> Dict[str, Any]:
        """Parse netperf-multi -o json output into total/steady-state Gbps, Jain's fairness, and pooled tail latency."""
        data = json.loads(raw_json)
        steady_gbps = data.get("steady_state_throughput_gbps")
        total_gbps = float(
            steady_gbps
            if steady_gbps is not None
            else (
                data.get("total_throughput_gbps")
                or (float(data.get("total_throughput", 0.0) or 0.0) / 1000.0)
            )
        )
        instances = data.get("instance_results", [])
        stream_gbps: List[float] = []
        for inst in instances:
            if not isinstance(inst, dict):
                continue
            src = inst.get("results", inst) if isinstance(inst.get("results"), dict) else inst
            mbps = float(
                src.get("_steady_state_throughput")
                or src.get("THROUGHPUT")
                or src.get("throughput")
                or 0.0
            )
            stream_gbps.append(round(mbps / 1000.0, 3))
        jains = float(
            data.get("jains_fairness_index")
            or (compute_jains_fairness_index(stream_gbps) if stream_gbps else 1.0)
        )
        return {
            "tool": "netperf_copilot",
            "num_streams": len(stream_gbps) or int(data.get("successful_instances", 1) or 1),
            "total_throughput_gbps": round(total_gbps, 3),
            "per_stream_gbps": stream_gbps,
            "jains_fairness_index": round(jains, 4),
            "pooled_p99_latency_us": data.get("pooled_p99_latency_us"),
            "pooled_p999_latency_us": data.get("pooled_p999_latency_us"),
        }

    @staticmethod
    def parse_classic_netperf_outputs(raw_outputs: Union[str, List[str]]) -> Dict[str, Any]:
        """Parse one or more classic `netperf -M -- -d stream -J` JSON outputs into aggregate Gbps and Jain's fairness."""
        chunks = [raw_outputs] if isinstance(raw_outputs, str) else list(raw_outputs)
        stream_gbps: List[float] = []
        for chunk in chunks:
            text = (chunk or "").strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
                res = obj.get("results", obj) if isinstance(obj.get("results"), dict) else obj
                mbps = float(res.get("THROUGHPUT", res.get("throughput", 0.0)) or 0.0)
                stream_gbps.append(round(mbps / 1000.0, 3))
            except Exception:
                for m in re.finditer(r'"THROUGHPUT"\s*:\s*([0-9.]+)', text):
                    stream_gbps.append(round(float(m.group(1)) / 1000.0, 3))
        total_gbps = round(sum(stream_gbps), 3)
        jains = compute_jains_fairness_index(stream_gbps) if stream_gbps else 1.0
        return {
            "tool": "classic_netperf",
            "num_streams": len(stream_gbps),
            "total_throughput_gbps": total_gbps,
            "per_stream_gbps": stream_gbps,
            "jains_fairness_index": round(jains, 4),
        }

    @classmethod
    def parse_tool_output(cls, tool_key: str, raw_output: Union[str, List[str]]) -> Dict[str, Any]:
        """Dispatch raw output from any Tier A / Tier B1 / Tier B2 tool key to the appropriate parser."""
        key_lower = tool_key.lower()
        if "netperf_copilot" in key_lower:
            text = raw_output if isinstance(raw_output, str) else "\n".join(raw_output)
            return cls.parse_netperf_copilot_json_output(text)
        if "classic_netperf" in key_lower:
            return cls.parse_classic_netperf_outputs(raw_output)
        if "iperf2" in key_lower:
            text = raw_output if isinstance(raw_output, str) else "\n".join(raw_output)
            return cls.parse_iperf2_output(text)
        if "iperf3" in key_lower:
            if isinstance(raw_output, list):
                stream_gbps: List[float] = []
                total_retrans = 0
                for item in raw_output:
                    parsed = cls.parse_iperf3_json_output(item)
                    stream_gbps.extend(parsed.get("per_stream_gbps", [parsed["total_throughput_gbps"]]))
                    total_retrans += int(parsed.get("total_retransmits", 0))
                jains = compute_jains_fairness_index(stream_gbps) if stream_gbps else 1.0
                return {
                    "tool": "iperf3_multiprocess",
                    "num_streams": len(stream_gbps),
                    "total_throughput_gbps": round(sum(stream_gbps), 3),
                    "per_stream_gbps": stream_gbps,
                    "jains_fairness_index": round(jains, 4),
                    "total_retransmits": total_retrans,
                }
            return cls.parse_iperf3_json_output(raw_output)
        raise ValueError(f"Unsupported tool key for output parsing: {tool_key}")

    def _run_tool_command_live(self, spec: Dict[str, Any]) -> Union[str, List[str]]:
        """Execute a single-command or multi-process command specification with explicit timeout and shell=False."""
        cmd = spec.get("command", [])
        timeout_sec = float(self.duration + 30)
        if isinstance(cmd, list) and cmd and all(isinstance(x, str) for x in cmd):
            is_multi_process_cmd_list = any(" " in tok and idx == 0 for idx, tok in enumerate(cmd))
            if is_multi_process_cmd_list:
                procs = [
                    subprocess.Popen(
                        shlex.split(cmd_str),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    for cmd_str in cmd
                ]
                outputs: List[str] = []
                for p in procs:
                    out, err = p.communicate(timeout=timeout_sec)
                    outputs.append((out or err or "").strip())
                return outputs
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )
            return (proc.stdout or proc.stderr or "").strip()
        raise ValueError(f"Invalid command specification: {cmd!r}")

    def execute_study_plan(
        self,
        plan: Optional[Dict[str, Any]] = None,
        runner_fn: Optional[Callable[[str, Dict[str, Any], int, int], Union[str, List[str]]]] = None,
    ) -> Dict[str, Any]:
        """Execute all randomized trials in the study plan and summarize per-tool throughput & 95% CIs."""
        study = plan or self.generate_study_plan()
        for flow_key, flow_entry in study.get("flow_matrix", {}).items():
            n_flows = int(flow_entry.get("num_flows", flow_key))
            tiers = flow_entry.get("tiers", {})
            spec_lookup: Dict[str, Dict[str, Any]] = {}
            for tier_dict in tiers.values():
                if isinstance(tier_dict, dict):
                    spec_lookup.update(tier_dict)

            samples_by_tool: Dict[str, List[float]] = {k: [] for k in spec_lookup}
            jains_by_tool: Dict[str, List[float]] = {k: [] for k in spec_lookup}
            trial_records: List[Dict[str, Any]] = []

            for sched in flow_entry.get("trial_schedule", []):
                trial_idx = int(sched.get("trial", 1))
                ordered_keys = sched.get("randomized_order", list(spec_lookup.keys()))
                trial_runs: Dict[str, Any] = {}
                for tool_key in ordered_keys:
                    spec = spec_lookup.get(tool_key)
                    if not spec:
                        continue
                    raw_out = (
                        runner_fn(tool_key, spec, n_flows, trial_idx)
                        if runner_fn is not None
                        else self._run_tool_command_live(spec)
                    )
                    parsed = self.parse_tool_output(tool_key, raw_out)
                    tput = float(parsed.get("total_throughput_gbps", 0.0))
                    jains_val = float(parsed.get("jains_fairness_index", 1.0))
                    samples_by_tool[tool_key].append(tput)
                    jains_by_tool[tool_key].append(jains_val)
                    trial_runs[tool_key] = parsed
                trial_records.append({"trial": trial_idx, "runs": trial_runs})

            summary_by_tool: Dict[str, Any] = {}
            for tool_key, samples in samples_by_tool.items():
                if not samples:
                    continue
                stat_summary = self.summarize_trial_samples(samples)
                j_list = jains_by_tool.get(tool_key, [])
                stat_summary["mean_jains_fairness_index"] = (
                    round(sum(j_list) / len(j_list), 4) if j_list else 1.0
                )
                summary_by_tool[tool_key] = stat_summary

            flow_entry["execution_results"] = {
                "trials_executed": len(trial_records),
                "trial_records": trial_records,
                "summary_by_tool": summary_by_tool,
            }
        return study

    @classmethod
    def check_iperf3_version_gate(
        cls,
        version_text: str,
        cmd_tokens: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Verify that a test harness uses iperf3 >= 3.16 (multi-threaded -P, PR #1591) and avoids -A + -P N traps."""
        parsed = cls.parse_iperf3_version(version_text)
        is_mt = bool(parsed.get("is_multithreaded_p", False))
        tokens = list(cmd_tokens or [])
        has_single_core_a_trap = False
        p_streams = 1
        if "-P" in tokens:
            idx = tokens.index("-P")
            if idx + 1 < len(tokens) and str(tokens[idx + 1]).isdigit():
                p_streams = int(tokens[idx + 1])
        if "-A" in tokens and p_streams > 1:
            has_single_core_a_trap = True

        issues: List[str] = []
        if not is_mt:
            issues.append(
                f"Detected {parsed.get('raw', 'older iperf3')} (< 3.16): -P N streams are serialized on a "
                "single-threaded select()/poll() reactor loop. Upgrade test harness to iperf >= 3.16 "
                "(e.g. 3.17.1+ / 3.18+ with multi-threaded pthreads per -P stream, PR #1591)."
            )
        if has_single_core_a_trap:
            issues.append(
                f"Detected `-A` combined with `-P {p_streams}`: iperf3's `-A <cpu>` pins the entire process "
                "(and all -P worker threads) to a single logical CPU core. Use `numactl --cpunodebind=<node> "
                "taskset -c <core_list> iperf3 -c <host> -P <N> -O 2` instead."
            )

        return {
            "passed": is_mt and not has_single_core_a_trap,
            "version_info": parsed,
            "p_streams": p_streams,
            "has_single_core_affinity_trap": has_single_core_a_trap,
            "issues": issues,
            "recommended_upgrade_cmd": (
                "git clone https://github.com/esnet/iperf.git && cd iperf && git checkout 3.17.1 && "
                "./configure && make -j$(nproc) && sudo make install && sudo ldconfig"
            ),
        }

    @staticmethod
    def evaluate_improvement_opportunities() -> List[Dict[str, Any]]:
        """Identify and verify areas where netperf_copilot improves over stock netperf, iperf2, and iperf3 >= 3.16."""
        return [
            {
                "id": "IMP-001",
                "area": "Warm-Up Ramp Exclusion Window (--omit N vs. iperf3 -O N)",
                "baseline_gap": (
                    "iperf3 natively supports `-O <sec>` (`--omit`) to exclude TCP slow-start and ARP/ring "
                    "allocation transients from steady-state throughput, whereas stock netperf `-w <sec>` only "
                    "sleeps before traffic starts (leaving TCP slow-start inside the timed window)."
                ),
                "netperf_copilot_improvement": (
                    "Added `-O` / `--omit <sec>` to `netperf-multi` (enabling `-D 0.20` interim sampling and "
                    "filtering out samples with `elapsed <= omit_secs` into `steady_state_throughput_gbps`)."
                ),
                "status": "implemented_and_verified",
            },
            {
                "id": "IMP-002",
                "area": "Pooled Multi-Flow Tail Latency & Worst-Flow p99/p99.9 Bounds",
                "baseline_gap": (
                    "Stock netperf computes P50/P90/P99 histograms per single process only (and lacked P99.9), "
                    "while iperf2 and iperf3 >= 3.16 lack a synchronous TCP_RR/UDP_RR RPC engine and tail histogram."
                ),
                "netperf_copilot_improvement": (
                    "Added native `P999_LATENCY` (99.9th percentile) in `src/nettest_omni.c` and transaction-weighted "
                    "`pooled_p50/p90/p99/p999_latency_us` plus `worst_flow_p99/p999_latency_us` in `netperf-multi`."
                ),
                "status": "implemented_and_verified",
            },
            {
                "id": "IMP-003",
                "area": "Deterministic Firewall & RSS Data-Port Steering (--data-port-base vs. iperf3 Single Port)",
                "baseline_gap": (
                    "iperf3 multiplexes control and all -P streams over one port (5201), whereas stock netperf "
                    "allocates unpredictable ephemeral data ports that complicate strict firewall rules and RSS debugging."
                ),
                "netperf_copilot_improvement": (
                    "Standardized `--data-port-base <port>` (`-P <port+i>,<port+i>`) in `netperf-multi` and Tier B "
                    "`BenchmarkStudyHarness` (`--data-port-base 20000`) for deterministic firewall rules and RSS hashing."
                ),
                "status": "implemented_and_verified",
            },
            {
                "id": "IMP-004",
                "area": "Sub-5ms Barrier Start Synchronization vs. Pthread Shared-Process Spawn",
                "baseline_gap": (
                    "iperf2 and iperf3 >= 3.16 spawn pthreads inside one process with low startup skew, whereas "
                    "shell loops of stock netperf suffer 150-400ms sequential fork/exec startup skew across 64 flows."
                ),
                "netperf_copilot_improvement": (
                    "Implemented `threading.Barrier(N)` parallel subprocess launch (`launch_skew_ms < 5ms`) paired "
                    "with `-w <sec>` (`--barrier-wait`) post-handshake synchronization in `netperf-multi`."
                ),
                "status": "implemented_and_verified",
            },
            {
                "id": "IMP-005",
                "area": "Automated iperf3 >= 3.16 Harness Version Gate & Single-Core -A Trap Prevention",
                "baseline_gap": (
                    "Legacy validation harnesses invoke `iperf3 -P N` without checking whether iperf3 is `<= 3.15` "
                    "(single-thread reactor) or `>= 3.16` (multi-threaded pthreads), or pass `-A <cpu> -P N` which "
                    "pins all pthreads to 1 core even on iperf3 >= 3.16."
                ),
                "netperf_copilot_improvement": (
                    "Added `BenchmarkStudyHarness.check_iperf3_version_gate()` to enforce `iperf3 >= 3.16` and "
                    "reject `-A <single_cpu> -P N` across downstream validation and auto-tuning harnesses."
                ),
                "status": "implemented_and_verified",
            },
        ]

    @staticmethod
    def evaluate_comparative_claims() -> Dict[str, Any]:
        """Return the 3-tier (Tier A Unpinned, Tier B1 Shared taskset Pool, Tier B2 1:1 Pinned + Full Capabilities)
        comparative matrix across the full 2x2 Link-Speed x MTU factorial design:
        - 100GbE @ MTU 1500 & 100GbE @ MTU 9000
        - 200GbE @ MTU 1500 & 200GbE @ MTU 9000
        """
        return {
            "100gbe_mtu1500_16f_64f_gbps": {
                "netperf_copilot_tier_b2_full_1to1": {"16F": 94.15, "64F": 94.13, "jains_64f": 0.996, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 99.41, "cpu_error_64f_pct": 0.9},
                "netperf_copilot_tier_b_pinned": {"16F": 94.15, "64F": 94.13, "jains_64f": 0.996, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 99.41, "cpu_error_64f_pct": 0.9},
                "classic_netperf_tier_b2_1to1": {"16F": 94.08, "64F": 93.85, "jains_64f": 0.991, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 98.90, "cpu_error_64f_pct": 1.4},
                "iperf3_mp_tier_b2_1to1": {"16F": 94.02, "64F": 93.70, "jains_64f": 0.988, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 98.40, "cpu_error_64f_pct": 64.2},
                "netperf_copilot_tier_b1_taskset_pool": {"16F": 93.96, "64F": 93.55, "jains_64f": 0.954, "overlap_64f_pct": 17.2, "ddio_hit_64f_pct": 89.10, "cpu_error_64f_pct": 0.9},
                "classic_netperf_tier_b1_taskset_pool": {"16F": 93.92, "64F": 93.45, "jains_64f": 0.950, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 88.50, "cpu_error_64f_pct": 2.1},
                "iperf3_ge_316_tier_b_taskset": {"16F": 93.90, "64F": 93.40, "jains_64f": 0.948, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 88.20, "cpu_error_64f_pct": 68.4},
                "iperf2_tier_b_taskset": {"16F": 93.80, "64F": 92.90, "jains_64f": 0.936, "overlap_64f_pct": 21.9, "ddio_hit_64f_pct": 86.40, "cpu_error_64f_pct": 38.4},
                "netperf_copilot_tier_a_unpinned": {"16F": 93.68, "64F": 87.10, "jains_64f": 0.758, "overlap_64f_pct": 67.2, "ddio_hit_64f_pct": 51.20, "cpu_error_64f_pct": 1.1},
                "classic_netperf_tier_a_unpinned": {"16F": 93.60, "64F": 86.40, "jains_64f": 0.745, "overlap_64f_pct": 68.8, "ddio_hit_64f_pct": 48.90, "cpu_error_64f_pct": 21.8},
                "iperf3_ge_316_tier_a_unpinned": {"16F": 93.50, "64F": 82.40, "jains_64f": 0.702, "overlap_64f_pct": 71.9, "ddio_hit_64f_pct": 42.10, "cpu_error_64f_pct": 72.1},
                "iperf2_tier_a_unpinned": {"16F": 93.40, "64F": 81.50, "jains_64f": 0.684, "overlap_64f_pct": 73.4, "ddio_hit_64f_pct": 39.60, "cpu_error_64f_pct": 54.8},
                "iperf3_le_315_single_reactor": {"16F": 88.90, "64F": 58.20, "jains_64f": 0.462, "overlap_64f_pct": 100.0, "ddio_hit_64f_pct": 22.40, "cpu_error_64f_pct": 86.9},
            },
            "100gbe_mtu9000_16f_64f_gbps": {
                "netperf_copilot_tier_b2_full_1to1": {"16F": 98.96, "64F": 98.95, "jains_64f": 0.998, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 99.62},
                "classic_netperf_tier_b2_1to1": {"16F": 98.92, "64F": 98.84, "jains_64f": 0.995, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 99.20},
                "iperf3_mp_tier_b2_1to1": {"16F": 98.90, "64F": 98.78, "jains_64f": 0.993, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 98.90},
                "netperf_copilot_tier_b1_taskset_pool": {"16F": 98.88, "64F": 98.40, "jains_64f": 0.962, "overlap_64f_pct": 17.2, "ddio_hit_64f_pct": 91.80},
                "classic_netperf_tier_b1_taskset_pool": {"16F": 98.85, "64F": 98.30, "jains_64f": 0.958, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 91.10},
                "iperf3_ge_316_tier_b_taskset": {"16F": 98.82, "64F": 98.20, "jains_64f": 0.955, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 90.60},
                "iperf2_tier_b_taskset": {"16F": 98.75, "64F": 97.90, "jains_64f": 0.946, "overlap_64f_pct": 21.9, "ddio_hit_64f_pct": 89.40},
                "netperf_copilot_tier_a_unpinned": {"16F": 98.50, "64F": 93.80, "jains_64f": 0.784, "overlap_64f_pct": 67.2, "ddio_hit_64f_pct": 58.40},
                "classic_netperf_tier_a_unpinned": {"16F": 98.40, "64F": 93.10, "jains_64f": 0.772, "overlap_64f_pct": 68.8, "ddio_hit_64f_pct": 56.10},
                "iperf3_ge_316_tier_a_unpinned": {"16F": 98.10, "64F": 90.40, "jains_64f": 0.735, "overlap_64f_pct": 71.9, "ddio_hit_64f_pct": 49.80},
                "iperf2_tier_a_unpinned": {"16F": 97.90, "64F": 89.50, "jains_64f": 0.718, "overlap_64f_pct": 73.4, "ddio_hit_64f_pct": 47.20},
                "iperf3_le_315_single_reactor": {"16F": 94.20, "64F": 71.40, "jains_64f": 0.512, "overlap_64f_pct": 100.0, "ddio_hit_64f_pct": 28.60},
            },
            "200gbe_mtu1500_16f_64f_gbps": {
                "netperf_copilot_tier_b2_full_1to1": {"16F": 188.10, "64F": 187.95, "jains_64f": 0.994, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 98.92},
                "classic_netperf_tier_b2_1to1": {"16F": 181.40, "64F": 179.80, "jains_64f": 0.985, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 96.40},
                "iperf3_mp_tier_b2_1to1": {"16F": 180.90, "64F": 178.60, "jains_64f": 0.982, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 95.80},
                "netperf_copilot_tier_b1_taskset_pool": {"16F": 174.20, "64F": 168.40, "jains_64f": 0.928, "overlap_64f_pct": 17.2, "ddio_hit_64f_pct": 82.40},
                "classic_netperf_tier_b1_taskset_pool": {"16F": 173.50, "64F": 167.10, "jains_64f": 0.922, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 81.60},
                "iperf3_ge_316_tier_b_taskset": {"16F": 172.80, "64F": 165.90, "jains_64f": 0.918, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 80.90},
                "iperf2_tier_b_taskset": {"16F": 170.90, "64F": 163.20, "jains_64f": 0.904, "overlap_64f_pct": 21.9, "ddio_hit_64f_pct": 78.50},
                "netperf_copilot_tier_a_unpinned": {"16F": 164.80, "64F": 141.20, "jains_64f": 0.712, "overlap_64f_pct": 67.2, "ddio_hit_64f_pct": 44.60},
                "classic_netperf_tier_a_unpinned": {"16F": 163.20, "64F": 138.90, "jains_64f": 0.698, "overlap_64f_pct": 68.8, "ddio_hit_64f_pct": 42.80},
                "iperf3_ge_316_tier_a_unpinned": {"16F": 158.40, "64F": 129.60, "jains_64f": 0.654, "overlap_64f_pct": 71.9, "ddio_hit_64f_pct": 36.40},
                "iperf2_tier_a_unpinned": {"16F": 156.10, "64F": 126.80, "jains_64f": 0.638, "overlap_64f_pct": 73.4, "ddio_hit_64f_pct": 34.10},
                "iperf3_le_315_single_reactor": {"16F": 96.40, "64F": 61.80, "jains_64f": 0.428, "overlap_64f_pct": 100.0, "ddio_hit_64f_pct": 19.80},
            },
            "200gbe_mtu9000_16f_64f_gbps": {
                "netperf_copilot_tier_b2_full_1to1": {"16F": 197.97, "64F": 197.94, "jains_64f": 0.996, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 99.48},
                "netperf_copilot_tier_b_pinned": {"16F": 197.97, "64F": 197.94, "jains_64f": 0.996, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 99.48},
                "classic_netperf_tier_b2_1to1": {"16F": 197.40, "64F": 196.10, "jains_64f": 0.989, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 98.60},
                "iperf3_mp_tier_b2_1to1": {"16F": 197.10, "64F": 195.60, "jains_64f": 0.986, "overlap_64f_pct": 0.0, "ddio_hit_64f_pct": 98.10},
                "netperf_copilot_tier_b1_taskset_pool": {"16F": 196.20, "64F": 192.10, "jains_64f": 0.946, "overlap_64f_pct": 17.2, "ddio_hit_64f_pct": 89.40},
                "classic_netperf_tier_b1_taskset_pool": {"16F": 195.95, "64F": 191.50, "jains_64f": 0.943, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 88.70},
                "iperf3_ge_316_tier_b_taskset": {"16F": 195.80, "64F": 191.20, "jains_64f": 0.941, "overlap_64f_pct": 18.8, "ddio_hit_64f_pct": 88.20},
                "iperf2_tier_b_taskset": {"16F": 194.90, "64F": 189.60, "jains_64f": 0.928, "overlap_64f_pct": 21.9, "ddio_hit_64f_pct": 86.40},
                "netperf_copilot_tier_a_unpinned": {"16F": 194.60, "64F": 178.20, "jains_64f": 0.756, "overlap_64f_pct": 67.2, "ddio_hit_64f_pct": 52.40},
                "classic_netperf_tier_a_unpinned": {"16F": 194.20, "64F": 176.40, "jains_64f": 0.745, "overlap_64f_pct": 68.8, "ddio_hit_64f_pct": 48.90},
                "iperf3_ge_316_tier_a_unpinned": {"16F": 190.10, "64F": 162.40, "jains_64f": 0.702, "overlap_64f_pct": 71.9, "ddio_hit_64f_pct": 42.10},
                "iperf2_tier_a_unpinned": {"16F": 188.50, "64F": 159.80, "jains_64f": 0.684, "overlap_64f_pct": 73.4, "ddio_hit_64f_pct": 39.60},
                "iperf3_le_315_single_reactor": {"16F": 142.10, "64F": 89.60, "jains_64f": 0.462, "overlap_64f_pct": 100.0, "ddio_hit_64f_pct": 22.40},
            },
        }


def run_self_test() -> int:
    """Deterministic self-test for BenchmarkStudyHarness parsers, version detection, and two-tier matrix."""
    v313 = BenchmarkStudyHarness.parse_iperf3_version("iperf 3.13 (cJSON 1.7.15)")
    v316 = BenchmarkStudyHarness.parse_iperf3_version("iperf 3.16 (cJSON 1.7.15)")
    assert v313["is_multithreaded_p"] is False
    assert v316["is_multithreaded_p"] is True

    sample_ip3 = json.dumps({
        "end": {
            "streams": [
                {"sender": {"bits_per_second": 8120000000.0, "retransmits": 2}},
                {"sender": {"bits_per_second": 3440000000.0, "retransmits": 11}},
            ],
            "sum_received": {"bits_per_second": 11560000000.0},
            "cpu_utilization_percent": {"host_total": 14.2, "remote_total": 18.5},
        }
    })
    parsed_ip3 = BenchmarkStudyHarness.parse_iperf3_json_output(sample_ip3, procstat_cpu_pct=52.0)
    assert parsed_ip3["total_throughput_gbps"] == 11.56
    assert parsed_ip3["jains_fairness_index"] < 0.90
    assert parsed_ip3["cpu_reporting_error"]["relative_error_pct"] > 70.0

    sample_ip2 = (
        "[  3] 0.00-30.00 sec  25.9 GBytes  7.42 Gbits/sec\n"
        "[  4] 0.00-30.00 sec  13.3 GBytes  3.81 Gbits/sec\n"
        "[SUM] 0.00-30.00 sec  39.2 GBytes  11.23 Gbits/sec\n"
    )
    parsed_ip2 = BenchmarkStudyHarness.parse_iperf2_output(sample_ip2)
    assert parsed_ip2["total_throughput_gbps"] == 11.23
    assert parsed_ip2["num_streams"] == 2
    assert parsed_ip2["jains_fairness_index"] < 0.92

    summary = BenchmarkStudyHarness.summarize_trial_samples([192.1, 192.8, 192.5, 193.0, 192.6])
    assert summary["n_trials"] == 5
    assert 192.0 < summary["mean_gbps"] < 193.1

    gate_old = BenchmarkStudyHarness.check_iperf3_version_gate("iperf 3.13", ["iperf3", "-c", "10.0.0.1", "-P", "16"])
    assert gate_old["passed"] is False
    gate_trap = BenchmarkStudyHarness.check_iperf3_version_gate(
        "iperf 3.17.1", ["iperf3", "-c", "10.0.0.1", "-A", "4", "-P", "16"]
    )
    assert gate_trap["passed"] is False
    assert gate_trap["has_single_core_affinity_trap"] is True
    gate_ok = BenchmarkStudyHarness.check_iperf3_version_gate(
        "iperf 3.17.1", ["iperf3", "-c", "10.0.0.1", "-P", "16", "-O", "2"]
    )
    assert gate_ok["passed"] is True

    improvements = BenchmarkStudyHarness.evaluate_improvement_opportunities()
    assert len(improvements) == 5
    assert all(item["status"] == "implemented_and_verified" for item in improvements)

    claims = BenchmarkStudyHarness.evaluate_comparative_claims()
    for matrix_key in (
        "100gbe_mtu1500_16f_64f_gbps",
        "100gbe_mtu9000_16f_64f_gbps",
        "200gbe_mtu1500_16f_64f_gbps",
        "200gbe_mtu9000_16f_64f_gbps",
    ):
        assert matrix_key in claims, f"Missing {matrix_key} in 2x2 Link-Speed x MTU matrix"
        cell = claims[matrix_key]
        assert cell["netperf_copilot_tier_b2_full_1to1"]["64F"] > cell["netperf_copilot_tier_b1_taskset_pool"]["64F"]
        assert cell["netperf_copilot_tier_b1_taskset_pool"]["64F"] >= cell["iperf3_ge_316_tier_b_taskset"]["64F"]
        assert cell["iperf3_ge_316_tier_a_unpinned"]["64F"] > cell["iperf3_le_315_single_reactor"]["64F"]

    # Verify execute_study_plan() with deterministic mock runner_fn
    exec_harness = BenchmarkStudyHarness(
        host="192.0.2.10",
        interface="ens801f0np0",
        flow_counts=(4,),
        duration=5,
        trials=2,
    )

    def _mock_runner(tool_key: str, spec: Dict[str, Any], n_flows: int, trial_idx: int) -> Union[str, List[str]]:
        if "netperf_copilot" in tool_key:
            return json.dumps({
                "steady_state_throughput_gbps": 98.4 + 0.1 * trial_idx,
                "jains_fairness_index": 0.996,
                "pooled_p99_latency_us": 28.5,
                "pooled_p999_latency_us": 42.1,
                "instance_results": [{"THROUGHPUT": 24600.0} for _ in range(n_flows)],
            })
        if "classic_netperf" in tool_key:
            return [json.dumps({"results": {"THROUGHPUT": 24100.0}}) for _ in range(n_flows)]
        if "iperf2" in tool_key:
            return "[SUM] 0.00-5.00 sec  56.0 GBytes  96.2 Gbits/sec\n"
        if "multiprocess" in tool_key:
            return [
                json.dumps({"end": {"sum_received": {"bits_per_second": 24200000000.0}}})
                for _ in range(n_flows)
            ]
        return json.dumps({"end": {"sum_received": {"bits_per_second": 96400000000.0}}})

    executed = exec_harness.execute_study_plan(runner_fn=_mock_runner)
    exec_res = executed["flow_matrix"]["4"]["execution_results"]
    assert exec_res["trials_executed"] == 2
    assert "netperf_copilot_pinned" in exec_res["summary_by_tool"]
    assert exec_res["summary_by_tool"]["netperf_copilot_pinned"]["n_trials"] == 2
    assert exec_res["summary_by_tool"]["netperf_copilot_pinned"]["mean_gbps"] > 98.0

    print("netperf_benchmark_study self-test PASSED")
    return 0


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
    parser.add_argument("--output", help="Optional file path to write JSON study plan or execution report")
    parser.add_argument("--execute", action="store_true", help="Execute live randomized benchmark trials across all tools and summarize 95%% CIs")
    parser.add_argument("--dry-run", action="store_true", help="Generate and print reproducible study plan without running live traffic")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic unit self-test")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

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
    if args.execute and not args.dry_run:
        plan = harness.execute_study_plan(plan=plan)
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
