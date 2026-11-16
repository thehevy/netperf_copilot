#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: dev/tools/netperf_pcm_bridge.py
# Created Date: 2026-11-16
# Last Updated Date: 2026-11-16
# Version: v3.2
# Status: Active
# Target Scope: netperf_copilot High-Speed 100GbE-200GbE Intel(R) PCM Silicon Telemetry & /proc/stat CPU Ground-Truth Bridge
# Summary: Collects and parses Intel(R) Performance Counter Monitor (pcm, pcm-pcie -e, pcm-memory, pcm-numa, pcm-power) CSV counters and /proc/stat CPU utilization ground truth to compute DDIO hit rate, UPI/DRAM bandwidth, Gbps/Watt, and tool CPU reporting error.
# === METADATA_HEADER_END ===
"""Intel(R) PCM Silicon Telemetry & /proc/stat Ground-Truth Bridge for netperf_copilot.

Provides:
1. ``IntelPCMCollector``:
   - Live collection mode: launches ``pcm``, ``pcm-pcie -e``, ``pcm-memory``,
     ``pcm-numa``, and ``pcm-power`` in CSV output mode for the duration of a
     benchmark window and terminates them cleanly when the run finishes.
   - Offline/replay mode (``--pcm-csv-dir``): deterministically parses saved
     Intel(R) PCM CSV artifacts for reproducible post-processing and CI tests.
   - Explicit, auditable counter equations:
     * ``ddio_hit_pct = ((pcirdcur_hit + itomcachenear_hit) / (pcirdcur_total + itomcachenear_total)) * 100.0``
     * ``gbps_per_watt = throughput_gbps / package_power_watts``
     * ``local_numa_traffic_pct = (local_dram_gbps / (local_dram_gbps + remote_dram_gbps)) * 100.0``
2. ``ProcStatGroundTruth``:
   - Reads whole-host and per-core ``/proc/stat`` jiffies before and after a
     benchmark run to compute ground-truth active CPU utilization and exact
     relative error against any benchmark tool's self-reported CPU utilization:
     * ``cpu_error_pct = abs(tool_reported_cpu_pct - procstat_cpu_pct) / max(procstat_cpu_pct, 1e-6) * 100.0``
"""

import argparse
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PCM_COUNTER_FORMULAS: Dict[str, str] = {
    "ddio_hit_pct": "((pcirdcur_hit + itomcachenear_hit) / (pcirdcur_total + itomcachenear_total)) * 100.0",
    "gbps_per_watt": "throughput_gbps / package_power_watts",
    "local_numa_traffic_pct": "(local_dram_gbps / (local_dram_gbps + remote_dram_gbps)) * 100.0",
    "cpu_error_pct": "(abs(tool_reported_cpu_pct - procstat_cpu_pct) / procstat_cpu_pct) * 100.0",
}


class ProcStatGroundTruth:
    """Whole-host and per-core /proc/stat CPU utilization ground-truth sampler."""

    def __init__(self, active_threshold_pct: float = 5.0) -> None:
        self.active_threshold_pct = active_threshold_pct
        self.start_snapshot: Dict[str, Tuple[int, ...]] = {}
        self.end_snapshot: Dict[str, Tuple[int, ...]] = {}

    @staticmethod
    def parse_proc_stat_text(text: str) -> Dict[str, Tuple[int, ...]]:
        """Parse /proc/stat content into a map of cpu label -> integer counter tuple."""
        snapshots: Dict[str, Tuple[int, ...]] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("cpu"):
                continue
            parts = line.split()
            label = parts[0]
            try:
                values = tuple(int(v) for v in parts[1:])
                if len(values) >= 4:
                    snapshots[label] = values
            except ValueError:
                continue
        return snapshots

    @classmethod
    def read_system_proc_stat(cls) -> Dict[str, Tuple[int, ...]]:
        proc_stat = Path("/proc/stat")
        if not proc_stat.exists():
            return {}
        try:
            return cls.parse_proc_stat_text(proc_stat.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return {}

    def start(self, override_text: Optional[str] = None) -> None:
        if override_text is not None:
            self.start_snapshot = self.parse_proc_stat_text(override_text)
        else:
            self.start_snapshot = self.read_system_proc_stat()

    def stop(self, override_text: Optional[str] = None) -> Dict[str, Any]:
        if override_text is not None:
            self.end_snapshot = self.parse_proc_stat_text(override_text)
        else:
            self.end_snapshot = self.read_system_proc_stat()
        return self.compute_delta()

    @staticmethod
    def _core_utilization_from_tuples(t0: Tuple[int, ...], t1: Tuple[int, ...]) -> Dict[str, float]:
        """Compute total, user, system, irq, softirq, and iowait % from two /proc/stat tuples."""
        length = min(len(t0), len(t1))
        deltas = [max(0, t1[i] - t0[i]) for i in range(length)]
        total_jiffies = sum(deltas)
        if total_jiffies <= 0:
            return {
                "total_util_pct": 0.0,
                "user_pct": 0.0,
                "system_pct": 0.0,
                "iowait_pct": 0.0,
                "irq_pct": 0.0,
                "softirq_pct": 0.0,
            }
        user = deltas[0] + (deltas[1] if length > 1 else 0)
        system = deltas[2] if length > 2 else 0
        idle = deltas[3] if length > 3 else 0
        iowait = deltas[4] if length > 4 else 0
        irq = deltas[5] if length > 5 else 0
        softirq = deltas[6] if length > 6 else 0
        busy = max(0, total_jiffies - idle - iowait)
        return {
            "total_util_pct": round((busy / total_jiffies) * 100.0, 2),
            "user_pct": round((user / total_jiffies) * 100.0, 2),
            "system_pct": round((system / total_jiffies) * 100.0, 2),
            "iowait_pct": round((iowait / total_jiffies) * 100.0, 2),
            "irq_pct": round((irq / total_jiffies) * 100.0, 2),
            "softirq_pct": round((softirq / total_jiffies) * 100.0, 2),
        }

    def compute_delta(self) -> Dict[str, Any]:
        if not self.start_snapshot or not self.end_snapshot:
            return {
                "available": False,
                "host_cpu_util_pct": 0.0,
                "active_cpu_util_pct": 0.0,
                "active_cpu_count": 0,
                "peak_cpu_id": -1,
                "peak_cpu_util_pct": 0.0,
                "host_softirq_pct": 0.0,
            }

        host_stats = {"total_util_pct": 0.0, "softirq_pct": 0.0, "irq_pct": 0.0, "user_pct": 0.0, "system_pct": 0.0}
        if "cpu" in self.start_snapshot and "cpu" in self.end_snapshot:
            host_stats = self._core_utilization_from_tuples(self.start_snapshot["cpu"], self.end_snapshot["cpu"])

        per_core_util: Dict[int, float] = {}
        per_core_softirq: Dict[int, float] = {}
        for label, start_vals in self.start_snapshot.items():
            if label == "cpu" or not label.startswith("cpu"):
                continue
            if label not in self.end_snapshot:
                continue
            try:
                cpu_id = int(label[3:])
            except ValueError:
                continue
            c_stats = self._core_utilization_from_tuples(start_vals, self.end_snapshot[label])
            per_core_util[cpu_id] = c_stats["total_util_pct"]
            per_core_softirq[cpu_id] = c_stats["softirq_pct"]

        active_cores = [u for u in per_core_util.values() if u >= self.active_threshold_pct]
        active_util = round(sum(active_cores) / len(active_cores), 2) if active_cores else host_stats["total_util_pct"]
        peak_cpu_id = max(per_core_util, key=per_core_util.get) if per_core_util else -1
        peak_cpu_util = per_core_util.get(peak_cpu_id, 0.0) if peak_cpu_id >= 0 else 0.0

        return {
            "available": True,
            "host_cpu_util_pct": host_stats["total_util_pct"],
            "host_user_pct": host_stats["user_pct"],
            "host_system_pct": host_stats["system_pct"],
            "host_irq_pct": host_stats["irq_pct"],
            "host_softirq_pct": host_stats["softirq_pct"],
            "active_cpu_util_pct": active_util,
            "active_cpu_count": len(active_cores),
            "peak_cpu_id": peak_cpu_id,
            "peak_cpu_util_pct": round(peak_cpu_util, 2),
            "per_core_util_pct": per_core_util,
            "per_core_softirq_pct": per_core_softirq,
        }

    @staticmethod
    def compute_cpu_reporting_error(
        tool_reported_cpu_pct: float,
        ground_truth_cpu_pct: float,
    ) -> Dict[str, float]:
        """Compute absolute and relative (%) error between tool-reported CPU % and /proc/stat ground truth."""
        abs_err = abs(float(tool_reported_cpu_pct) - float(ground_truth_cpu_pct))
        denom = max(abs(float(ground_truth_cpu_pct)), 1e-6)
        rel_err_pct = (abs_err / denom) * 100.0
        return {
            "tool_reported_cpu_pct": round(float(tool_reported_cpu_pct), 2),
            "procstat_ground_truth_cpu_pct": round(float(ground_truth_cpu_pct), 2),
            "absolute_error_pct_points": round(abs_err, 2),
            "relative_error_pct": round(rel_err_pct, 2),
        }


class IntelPCMCollector:
    """Collector and parser for Intel(R) Performance Counter Monitor (PCM) hardware telemetry."""

    PCM_TOOLS = (
        ("pcm", ["pcm", "1.0", "-csv"]),
        ("pcm_pcie", ["pcm-pcie", "1.0", "-e", "-csv"]),
        ("pcm_memory", ["pcm-memory", "1.0", "-csv"]),
        ("pcm_numa", ["pcm-numa", "1.0", "-csv"]),
        ("pcm_power", ["pcm-power", "1.0", "-csv"]),
    )

    def __init__(
        self,
        csv_dir: Optional[str] = None,
        sample_interval_sec: float = 1.0,
    ) -> None:
        self.csv_dir = Path(csv_dir) if csv_dir else None
        self.sample_interval_sec = sample_interval_sec
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self._processes: Dict[str, Tuple[subprocess.Popen, Any]] = {}
        self._active_dir: Optional[Path] = None

    @staticmethod
    def compute_ddio_hit_rate(
        pcirdcur_hit: float,
        pcirdcur_total: float,
        itomcachenear_hit: float = 0.0,
        itomcachenear_total: float = 0.0,
    ) -> float:
        """Compute PCIe DDIO LLC cache hit rate (%) from pcm-pcie -e counters.

        Formula:
            DDIO Hit % = ((PCIRdCur_hit + ItoMCacheNear_hit) / (PCIRdCur_total + ItoMCacheNear_total)) * 100.0
        """
        total = float(pcirdcur_total) + float(itomcachenear_total)
        if total <= 0.0:
            return 0.0
        hits = float(pcirdcur_hit) + float(itomcachenear_hit)
        return round(min(100.0, max(0.0, (hits / total) * 100.0)), 2)

    @staticmethod
    def compute_gbps_per_watt(throughput_gbps: float, package_power_watts: float) -> float:
        """Compute energy efficiency in Gbps/Watt."""
        if package_power_watts <= 0.0:
            return 0.0
        return round(float(throughput_gbps) / float(package_power_watts), 4)

    def start_live_collection(self) -> bool:
        """Start available Intel(R) PCM tools in the background writing CSV files."""
        if self.csv_dir and self.csv_dir.exists():
            self._active_dir = self.csv_dir
            return True

        self._temp_dir = tempfile.TemporaryDirectory(prefix="netperf_pcm_")
        self._active_dir = Path(self._temp_dir.name)
        started_any = False

        for key, base_cmd in self.PCM_TOOLS:
            bin_name = base_cmd[0]
            bin_path = shutil.which(bin_name)
            if not bin_path:
                continue
            out_file = self._active_dir / f"{key}.csv"
            cmd = [bin_path, str(self.sample_interval_sec)] + base_cmd[2:]
            try:
                fh = open(out_file, "w", encoding="utf-8")
                proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.DEVNULL, text=True)
                self._processes[key] = (proc, fh)
                started_any = True
            except Exception:
                continue
        return started_any

    def stop_and_collect(self, throughput_gbps: float = 0.0) -> Dict[str, Any]:
        """Stop any running PCM processes and parse collected or replay CSV files."""
        for _, (proc, fh) in list(self._processes.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                fh.close()
            except Exception:
                pass
        self._processes.clear()

        target_dir = self.csv_dir if (self.csv_dir and self.csv_dir.exists()) else self._active_dir
        summary = self.parse_csv_directory(target_dir, throughput_gbps=throughput_gbps)

        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None

        return summary

    @classmethod
    def parse_csv_directory(
        cls,
        csv_dir: Optional[Path],
        throughput_gbps: float = 0.0,
    ) -> Dict[str, Any]:
        """Parse a directory of PCM CSV files (pcm.csv, pcm_pcie.csv, pcm_memory.csv, pcm_numa.csv, pcm_power.csv)."""
        if csv_dir is None or not csv_dir.exists():
            return {
                "available": False,
                "formulas": PCM_COUNTER_FORMULAS,
                "reason": "No Intel PCM CSV directory or live PCM binaries available",
            }

        metrics: Dict[str, Any] = {
            "available": False,
            "source_dir": str(csv_dir),
            "formulas": PCM_COUNTER_FORMULAS,
            "ipc": None,
            "l2_hit_pct": None,
            "l3_hit_pct": None,
            "ddio_hit_pct": None,
            "upi_traffic_gbps": None,
            "local_dram_gbps": None,
            "remote_dram_gbps": None,
            "total_dram_gbps": None,
            "local_numa_traffic_pct": None,
            "package_power_watts": None,
            "gbps_per_watt": None,
        }

        # 1. Core / Socket PCM (pcm.csv)
        pcm_file = csv_dir / "pcm.csv"
        if pcm_file.exists():
            rows = cls._read_key_value_csv(pcm_file)
            if rows:
                metrics["available"] = True
                metrics["ipc"] = cls._mean_float(rows, ("IPC", "ipc"))
                l2_hit = cls._mean_float(rows, ("L2HIT", "l2_hit_ratio", "L2Hit%"))
                if l2_hit is not None:
                    metrics["l2_hit_pct"] = round(l2_hit * 100.0 if l2_hit <= 1.0 else l2_hit, 2)
                l3_hit = cls._mean_float(rows, ("L3HIT", "l3_hit_ratio", "L3Hit%"))
                if l3_hit is not None:
                    metrics["l3_hit_pct"] = round(l3_hit * 100.0 if l3_hit <= 1.0 else l3_hit, 2)
                upi_gbps = cls._mean_float(rows, ("UPI_GBPS", "upi_gbps", "TotalUPI_GB/s"))
                if upi_gbps is not None:
                    metrics["upi_traffic_gbps"] = round(upi_gbps, 2)
                pkg_watts = cls._mean_float(rows, ("Proc Energy (Joules)", "Package_Watts", "pkg_watts"))
                if pkg_watts is not None:
                    metrics["package_power_watts"] = round(pkg_watts, 2)

        # 2. PCIe DDIO counters (pcm_pcie.csv)
        pcie_file = csv_dir / "pcm_pcie.csv"
        if pcie_file.exists():
            rows = cls._read_key_value_csv(pcie_file)
            if rows:
                metrics["available"] = True
                direct_ddio = cls._mean_float(rows, ("DDIO_HIT_PCT", "ddio_hit_pct"))
                if direct_ddio is not None:
                    metrics["ddio_hit_pct"] = round(direct_ddio, 2)
                else:
                    rd_hit = cls._sum_float(rows, ("PCIRdCur_hit", "pcirdcur_hit"))
                    rd_tot = cls._sum_float(rows, ("PCIRdCur_total", "pcirdcur_total"))
                    itom_hit = cls._sum_float(rows, ("ItoMCacheNear_hit", "itomcachenear_hit"))
                    itom_tot = cls._sum_float(rows, ("ItoMCacheNear_total", "itomcachenear_total"))
                    if (rd_tot + itom_tot) > 0:
                        metrics["ddio_hit_pct"] = cls.compute_ddio_hit_rate(
                            rd_hit, rd_tot, itom_hit, itom_tot
                        )
                        metrics["pcirdcur_hit"] = int(rd_hit)
                        metrics["pcirdcur_total"] = int(rd_tot)
                        metrics["itomcachenear_hit"] = int(itom_hit)
                        metrics["itomcachenear_total"] = int(itom_tot)

        # 3. Memory & NUMA bandwidth (pcm_memory.csv / pcm_numa.csv)
        for mem_name in ("pcm_memory.csv", "pcm_numa.csv"):
            mem_file = csv_dir / mem_name
            if mem_file.exists():
                rows = cls._read_key_value_csv(mem_file)
                if rows:
                    metrics["available"] = True
                    loc_bw = cls._mean_float(rows, ("Local_DRAM_GB/s", "local_dram_gbps", "Local_MB/s"))
                    rem_bw = cls._mean_float(rows, ("Remote_DRAM_GB/s", "remote_dram_gbps", "Remote_MB/s"))
                    if loc_bw is not None:
                        metrics["local_dram_gbps"] = round(loc_bw, 2)
                    if rem_bw is not None:
                        metrics["remote_dram_gbps"] = round(rem_bw, 2)

        if metrics["local_dram_gbps"] is not None or metrics["remote_dram_gbps"] is not None:
            loc = float(metrics["local_dram_gbps"] or 0.0)
            rem = float(metrics["remote_dram_gbps"] or 0.0)
            tot = loc + rem
            metrics["total_dram_gbps"] = round(tot, 2)
            if tot > 0.0:
                metrics["local_numa_traffic_pct"] = round((loc / tot) * 100.0, 2)

        # 4. Package power (pcm_power.csv)
        power_file = csv_dir / "pcm_power.csv"
        if power_file.exists():
            rows = cls._read_key_value_csv(power_file)
            if rows:
                metrics["available"] = True
                watts = cls._mean_float(rows, ("Package_Watts", "pkg_watts", "Watts"))
                if watts is not None:
                    metrics["package_power_watts"] = round(watts, 2)

        if metrics["package_power_watts"] and throughput_gbps > 0.0:
            metrics["gbps_per_watt"] = cls.compute_gbps_per_watt(
                throughput_gbps, float(metrics["package_power_watts"])
            )

        return metrics

    @staticmethod
    def _read_key_value_csv(path: Path) -> List[Dict[str, str]]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                return []
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]
        except Exception:
            return []

    @staticmethod
    def _mean_float(rows: List[Dict[str, str]], keys: Tuple[str, ...]) -> Optional[float]:
        vals: List[float] = []
        for r in rows:
            for k in keys:
                if k in r and r[k] not in (None, ""):
                    try:
                        vals.append(float(str(r[k]).strip()))
                        break
                    except ValueError:
                        continue
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)

    @staticmethod
    def _sum_float(rows: List[Dict[str, str]], keys: Tuple[str, ...]) -> float:
        total = 0.0
        for r in rows:
            for k in keys:
                if k in r and r[k] not in (None, ""):
                    try:
                        total += float(str(r[k]).strip())
                        break
                    except ValueError:
                        continue
        return total


def run_self_test() -> int:
    """Deterministic self-test for IntelPCMCollector and ProcStatGroundTruth formulas."""
    with tempfile.TemporaryDirectory(prefix="pcm_selftest_") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "pcm.csv").write_text(
            "IPC,L2HIT,L3HIT,UPI_GBPS\n0.91,0.885,0.934,0.18\n0.89,0.875,0.926,0.20\n",
            encoding="utf-8",
        )
        (tmp_path / "pcm_pcie.csv").write_text(
            "PCIRdCur_hit,PCIRdCur_total,ItoMCacheNear_hit,ItoMCacheNear_total\n"
            "99800,100000,498950,500000\n",
            encoding="utf-8",
        )
        (tmp_path / "pcm_memory.csv").write_text(
            "Local_DRAM_GB/s,Remote_DRAM_GB/s\n0.83,0.02\n0.87,0.02\n",
            encoding="utf-8",
        )
        (tmp_path / "pcm_power.csv").write_text(
            "Package_Watts\n285.0\n",
            encoding="utf-8",
        )

        collector = IntelPCMCollector(csv_dir=str(tmp_path))
        res = collector.stop_and_collect(throughput_gbps=94.15)
        assert res["available"] is True, "Expected PCM summary to be available"
        assert abs(res["ipc"] - 0.90) < 1e-3, f"Unexpected IPC: {res['ipc']}"
        assert abs(res["ddio_hit_pct"] - 99.79) < 0.02, f"Unexpected DDIO hit %: {res['ddio_hit_pct']}"
        assert abs(res["upi_traffic_gbps"] - 0.19) < 1e-3, f"Unexpected UPI GB/s: {res['upi_traffic_gbps']}"
        assert abs(res["total_dram_gbps"] - 0.87) < 0.05, f"Unexpected DRAM GB/s: {res['total_dram_gbps']}"
        assert res["gbps_per_watt"] > 0.30, f"Unexpected Gbps/W: {res['gbps_per_watt']}"

        proc_start = (
            "cpu  1000 0 1000 8000 0 100 400 0 0 0\n"
            "cpu0 500 0 500 0 0 50 200 0 0 0\n"
            "cpu1 500 0 500 8000 0 50 200 0 0 0\n"
        )
        proc_end = (
            "cpu  2000 0 2000 10000 0 200 900 0 0 0\n"
            "cpu0 1400 0 1400 100 0 100 600 0 0 0\n"
            "cpu1 600 0 600 9900 0 100 300 0 0 0\n"
        )
        gt = ProcStatGroundTruth()
        gt.start(override_text=proc_start)
        delta = gt.stop(override_text=proc_end)
        assert delta["available"] is True
        assert delta["peak_cpu_id"] == 0
        err = ProcStatGroundTruth.compute_cpu_reporting_error(28.0, delta["host_cpu_util_pct"])
        assert err["relative_error_pct"] > 40.0

    print("netperf_pcm_bridge self-test PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Intel(R) PCM Silicon Telemetry & /proc/stat CPU Ground-Truth Bridge"
    )
    parser.add_argument("--pcm-csv-dir", help="Directory containing PCM CSV files to parse")
    parser.add_argument("--throughput-gbps", type=float, default=0.0, help="Measured throughput in Gbps")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic unit self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    collector = IntelPCMCollector(csv_dir=args.pcm_csv_dir)
    summary = collector.stop_and_collect(throughput_gbps=args.throughput_gbps)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# === METADATA_FOOTER_START ===
# Search Keywords: netperf_copilot, Intel PCM, DDIO hit rate, UPI bandwidth, DRAM bandwidth, Gbps per Watt, proc/stat
# Drivers & Subsystems: ice, netperf, netserver, intel_pcm
# Related Units / Patches: DOC-WP-NETPERF-COPILOT-BENCHMARK-STUDY-001, D1-D10 v3.2
# Created / Last-Updated: 2026-11-16 / 2026-11-16
# === METADATA_FOOTER_END ===
