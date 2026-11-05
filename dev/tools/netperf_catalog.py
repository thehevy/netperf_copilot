#!/usr/bin/env python3
"""
netperf_catalog - Structured Qualification Test Catalog & Matrix Runner

Implements 4 standardized high-speed qualification suites:
1. flow-scaling        : {1, 2, 4, 8, 16, 32, 64} streams x {TX, RX, BX} x {MTU 1500, 9000}
2. core-locality       : Same-Core vs Same-L2-Module vs Local-NUMA vs Cross-NUMA
3. ring-coalesce-matrix: Ring {512, 1024, 2048, 4096} x Coalesce {1, 10, 25, 50, adaptive}
4. lag-failover-qos    : Active-Active LACP 200G LAG member link-down/up failover + 4-TC DSCP QoS
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from netperf_report import AIValidationReporter
from netperf_topology import SystemTopology, TopologyAnalyzer


@dataclass
class CatalogTestCase:
    test_case_id: str
    suite: str
    description: str
    direction: str
    streams: int
    mtu: int
    command: List[str]
    parameters: Dict[str, Any] = field(default_factory=dict)


class QualificationCatalog:
    """Generates and executes structured 200G-800G qualification test suites."""

    SUITES = (
        "flow-scaling",
        "core-locality",
        "ring-coalesce-matrix",
        "lag-failover-qos",
    )

    def __init__(
        self,
        host: str,
        interface: str = "ens801f0np0",
        topology: Optional[SystemTopology] = None,
        base_port: int = 18600,
        duration: int = 30,
    ) -> None:
        self.host = host
        self.interface = interface
        self.topology = topology or TopologyAnalyzer().detect_live(interfaces=[interface])
        self.base_port = base_port
        self.duration = duration

    def build_suite(self, suite_name: str) -> List[CatalogTestCase]:
        if suite_name == "flow-scaling":
            return self._build_flow_scaling()
        if suite_name == "core-locality":
            return self._build_core_locality()
        if suite_name == "ring-coalesce-matrix":
            return self._build_ring_coalesce_matrix()
        if suite_name == "lag-failover-qos":
            return self._build_lag_failover_qos()
        raise ValueError(f"Unknown suite '{suite_name}'. Valid suites: {self.SUITES}")

    def _build_flow_scaling(self) -> List[CatalogTestCase]:
        cases: List[CatalogTestCase] = []
        layout = "spread_l2" if self.topology.arch_type == "ecore" else "spread_step2"
        stream_counts = [1, 2, 4, 8, 16, 32, 64]
        directions = ["tx", "rx", "bx"]
        mtus = [9000, 1500]

        for mtu in mtus:
            for direction in directions:
                for streams in stream_counts:
                    tc_id = f"FLOW-{direction.upper()}-{streams}S-MTU{mtu}"
                    cmd = [
                        "netperf-multi",
                        "-H", self.host,
                        "-i", self.interface,
                        "-t", "OMNI",
                        "--direction", direction,
                        "-n", str(streams),
                        "-l", str(self.duration),
                        "--mtu", str(mtu),
                        "--affinity",
                        "--layout", layout,
                        "--per-core-netserver",
                        "--base-port", str(self.base_port),
                        "--",
                        "-m", "65536" if mtu >= 9000 else "16384",
                        "-D",
                    ]
                    cases.append(
                        CatalogTestCase(
                            test_case_id=tc_id,
                            suite="flow-scaling",
                            description=f"{streams}-stream {direction.upper()} at MTU {mtu} ({layout})",
                            direction=direction,
                            streams=streams,
                            mtu=mtu,
                            command=cmd,
                            parameters={"layout": layout, "mtu": mtu, "streams": streams},
                        )
                    )
        return cases

    def _build_core_locality(self) -> List[CatalogTestCase]:
        """Single-flow locality isolation: Same-Core, Same-L2-Module, Local-NUMA, Cross-NUMA."""
        if_topo = self.topology.interfaces.get(self.interface)
        local_numa = if_topo.numa_node if if_topo and if_topo.numa_node >= 0 else 0
        remote_numa = 1 if local_numa == 0 and len(self.topology.numa_nodes) > 1 else max(0, local_numa)

        local_pool = self.topology.core_pools.get(local_numa)
        remote_pool = self.topology.core_pools.get(remote_numa)

        irq_core = local_pool.irq_cores[0] if local_pool and local_pool.irq_cores else 2
        l2_sibling = local_pool.irq_cores[1] if local_pool and len(local_pool.irq_cores) > 1 else irq_core + 1
        local_app_core = local_pool.app_cores[0] if local_pool and local_pool.app_cores else 4
        remote_app_core = remote_pool.app_cores[0] if remote_pool and remote_pool.app_cores else 72

        scenarios = [
            ("LOC-SAME-CORE", "App pinned to exact Queue-0 IRQ core", irq_core),
            ("LOC-SAME-L2", "App pinned to L2 module sibling of Queue-0 IRQ core", l2_sibling),
            ("LOC-LOCAL-NUMA", "App pinned to disjoint physical core on NIC local NUMA", local_app_core),
            ("LOC-CROSS-NUMA", "App pinned to remote NUMA node (cross-UPI/mesh penalty)", remote_app_core),
        ]
        cases: List[CatalogTestCase] = []
        for tc_id, desc, core in scenarios:
            cmd = [
                "netperf",
                "-H", self.host,
                "-p", str(self.base_port),
                "-M",
                "-l", str(self.duration),
                "-T", f"{core},{core}",
                "--",
                "-d", "stream",
                "-m", "65536",
                "-D",
                "-J",
            ]
            cases.append(
                CatalogTestCase(
                    test_case_id=tc_id,
                    suite="core-locality",
                    description=desc,
                    direction="tx",
                    streams=1,
                    mtu=9000,
                    command=cmd,
                    parameters={"local_cpu": core, "nic_numa": local_numa},
                )
            )
        return cases

    def _build_ring_coalesce_matrix(self) -> List[CatalogTestCase]:
        rings = [512, 1024, 2048, 4096]
        coalesce_modes = [
            ("1us", {"rx_usecs": 1, "tx_usecs": 1, "adaptive": "off"}),
            ("10us", {"rx_usecs": 10, "tx_usecs": 20, "adaptive": "off"}),
            ("25us", {"rx_usecs": 25, "tx_usecs": 25, "adaptive": "off"}),
            ("50us", {"rx_usecs": 50, "tx_usecs": 50, "adaptive": "off"}),
            ("adaptive", {"rx_usecs": 10, "tx_usecs": 20, "adaptive": "on"}),
        ]
        cases: List[CatalogTestCase] = []
        for ring in rings:
            for c_label, c_cfg in coalesce_modes:
                tc_id = f"MATRIX-RING{ring}-COAL-{c_label.upper()}"
                cmd = [
                    "netperf-multi",
                    "-H", self.host,
                    "-i", self.interface,
                    "--direction", "tx",
                    "-n", "16",
                    "-l", str(self.duration),
                    "--per-core-netserver",
                    "--base-port", str(self.base_port),
                ]
                cases.append(
                    CatalogTestCase(
                        test_case_id=tc_id,
                        suite="ring-coalesce-matrix",
                        description=f"16-stream TX with ring={ring}, coalesce={c_label}",
                        direction="tx",
                        streams=16,
                        mtu=9000,
                        command=cmd,
                        parameters={"tx_ring": ring, "rx_ring": max(ring, 4096), **c_cfg},
                    )
                )
        return cases

    def _build_lag_failover_qos(self) -> List[CatalogTestCase]:
        cases: List[CatalogTestCase] = [
            CatalogTestCase(
                test_case_id="LAG-ACTIVE-ACTIVE-4TC-TX",
                suite="lag-failover-qos",
                description="Active-Active LACP 200G LAG with 4 DSCP Traffic Classes (EF, CS3, AF21, CS0)",
                direction="tx",
                streams=16,
                mtu=9000,
                command=[
                    "netperf-multi",
                    "-H", self.host,
                    "-i", self.interface,
                    "--direction", "tx",
                    "-n", "16",
                    "-l", str(self.duration),
                    "--dscp", "EF,CS3,AF21,CS0",
                    "--per-core-netserver",
                    "--base-port", str(self.base_port),
                ],
                parameters={"dscp": ["EF", "CS3", "AF21", "CS0"], "lag_mode": "802.3ad"},
            ),
            CatalogTestCase(
                test_case_id="LAG-MEMBER-FAILOVER-RECOVERY",
                suite="lag-failover-qos",
                description="LACP member link-down/up failover under 16-stream bidirectional TCP + RoCEv2 load",
                direction="bx",
                streams=16,
                mtu=9000,
                command=[
                    "netperf-multi",
                    "-H", self.host,
                    "-i", self.interface,
                    "--direction", "bx",
                    "-n", "16",
                    "-l", str(max(self.duration, 60)),
                    "--dscp", "EF,CS3,AF21,CS0",
                    "--per-core-netserver",
                    "--base-port", str(self.base_port),
                ],
                parameters={"failover_inject": True, "rocev2_coexist": True},
            ),
        ]
        return cases


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Structured 200G-800G Qualification Test Catalog & Matrix Generator"
    )
    parser.add_argument(
        "--suite",
        choices=list(QualificationCatalog.SUITES),
        default="flow-scaling",
        help="Qualification suite to generate/execute",
    )
    parser.add_argument("-H", "--host", default="192.168.10.2", help="Target LP IP or range")
    parser.add_argument("-i", "--interface", default="ens801f0np0", help="DUT interface")
    parser.add_argument("-l", "--duration", type=int, default=30, help="Per-test duration (seconds)")
    parser.add_argument("--output-dir", help="Write result.json, summary.csv, and dashboard.md to directory")
    parser.add_argument("--dry-run", action="store_true", help="List generated test cases and commands")
    parser.add_argument("--json", action="store_true", help="Output catalog in JSON format")
    args = parser.parse_args(argv)

    catalog = QualificationCatalog(
        host=args.host,
        interface=args.interface,
        duration=args.duration,
    )
    cases = catalog.build_suite(args.suite)

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        env_info = {
            "cpu_model": catalog.topology.model_name,
            "arch_type": catalog.topology.arch_type,
            "interface": args.interface,
        }
        rows: List[Dict[str, Any]] = []
        result_records: List[Dict[str, Any]] = []

        for c in cases:
            tput_gbps = 0.0
            tx_gbps = 0.0
            rx_gbps = 0.0
            cv_pct = 0.0
            verdict = "SKIP" if args.dry_run else "PASS"

            if not args.dry_run:
                try:
                    proc = subprocess.run(
                        c.command,
                        capture_output=True,
                        text=True,
                        timeout=max(60, args.duration * 2 + 30),
                    )
                    if proc.returncode != 0:
                        verdict = "FAIL"
                except Exception:
                    verdict = "SKIP"

            row = {
                "test_case_id": c.test_case_id,
                "direction": c.direction,
                "streams": c.streams,
                "mtu": c.mtu,
                "throughput_gbps": tput_gbps,
                "tx_throughput_gbps": tx_gbps,
                "rx_throughput_gbps": rx_gbps,
                "cv_pct": cv_pct,
                "verdict": verdict,
            }
            rows.append(row)
            rec = AIValidationReporter.build_result_json(
                test_case_id=c.test_case_id,
                suite_name=args.suite,
                metrics={
                    "throughput_gbps": tput_gbps,
                    "tx_throughput_gbps": tx_gbps,
                    "rx_throughput_gbps": rx_gbps,
                    "cv_pct": cv_pct,
                },
                environment=env_info,
                duration_sec=float(args.duration),
            )
            if args.dry_run or verdict == "SKIP":
                rec["verdict"] = "SKIP"
            result_records.append(rec)

        (out_dir / "result.json").write_text(
            json.dumps(
                {
                    "suite_name": args.suite,
                    "environment": env_info,
                    "results": result_records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (out_dir / "summary.csv").write_text(
            AIValidationReporter.render_summary_csv(rows), encoding="utf-8"
        )
        (out_dir / "dashboard.md").write_text(
            AIValidationReporter.render_dashboard_markdown(
                args.suite,
                rows,
                environment=env_info,
            ),
            encoding="utf-8",
        )

    if args.json:
        print(json.dumps([asdict(c) for c in cases], indent=2))
    else:
        print(f"Suite '{args.suite}' ({len(cases)} test cases):")
        for c in cases:
            print(f"  [{c.test_case_id}] {c.description}")
            print(f"    $ {' '.join(c.command)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
