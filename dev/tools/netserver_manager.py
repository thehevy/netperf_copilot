#!/usr/bin/env python3
"""
netserver_manager.py - Topology-Aware Per-Core Netserver Pool Manager

Eliminates the three Load Partner (LP) / DUT netserver bottlenecks identified in
200GbE-800GbE Xeon 6 testing (02_LESSONS_LEARNED.md):
1. Prevents netserver instances from running on NIC IRQ cores (-40% throughput drop).
2. Pins each netserver to a dedicated non-IRQ physical core and local NUMA memory node:
     numactl --physcpubind=<core> --membind=<numa_node> netserver -p $((base_port + core))
3. Provides deterministic (core -> port) mapping so netperf -T <dut_core>,<lp_core>
   connects to -p $((base_port + lp_core)), guaranteeing zero post-fork CPU migration.

Author: Netperf Modernization Project - Phase 6
License: MIT
"""

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from netperf_topology import TopologyAnalyzer, SystemTopology, parse_cpu_list, format_cpu_list


@dataclass
class NetserverInstancePlan:
    """Single pinned netserver instance specification."""
    core: int
    port: int
    numa_node: int
    command: str


@dataclass
class NetserverPoolSpec:
    """Represents a deployed or planned pool of per-core pinned netserver instances."""
    host: str = "localhost"
    numa_node: int = 0
    interface: str = ""
    uarch: str = "generic"
    base_port: int = 18600
    default_port: int = 12865
    irq_cores_excluded: List[int] = field(default_factory=list)
    isolation_cores_excluded: List[int] = field(default_factory=list)
    core_to_port: Dict[int, int] = field(default_factory=dict)
    commands: List[str] = field(default_factory=list)

    @property
    def instances(self) -> List[NetserverInstancePlan]:
        out: List[NetserverInstancePlan] = []
        for core, port in sorted(self.core_to_port.items()):
            cmd = f"numactl --physcpubind={core} --membind={self.numa_node} netserver -p {port}"
            out.append(NetserverInstancePlan(core=core, port=port, numa_node=self.numa_node, command=cmd))
        return out

    def get_port_for_core(self, core: int) -> int:
        return self.core_to_port.get(int(core), self.base_port + int(core))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "numa_node": self.numa_node,
            "interface": self.interface,
            "uarch": self.uarch,
            "base_port": self.base_port,
            "default_port": self.default_port,
            "irq_cores_excluded": self.irq_cores_excluded,
            "isolation_cores_excluded": self.isolation_cores_excluded,
            "core_to_port": {str(k): v for k, v in self.core_to_port.items()},
            "commands": self.commands,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NetserverPoolSpec":
        c2p = {int(k): int(v) for k, v in data.get("core_to_port", {}).items()}
        return cls(
            host=data.get("host", "localhost"),
            numa_node=int(data.get("numa_node", 0)),
            interface=data.get("interface", ""),
            uarch=data.get("uarch", "generic"),
            base_port=int(data.get("base_port", 18600)),
            default_port=int(data.get("default_port", 12865)),
            irq_cores_excluded=[int(c) for c in data.get("irq_cores_excluded", [])],
            isolation_cores_excluded=[int(c) for c in data.get("isolation_cores_excluded", [])],
            core_to_port=c2p,
            commands=list(data.get("commands", [])),
        )


class NetserverPoolManager:
    """Plans, starts, stops, and audits per-core pinned netserver pools."""

    def __init__(self, host: Optional[str] = None, ssh_user: Optional[str] = None,
                 ssh_port: int = 22, ssh_key: Optional[str] = None,
                 netserver_path: str = "netserver", base_port: int = 18600,
                 verbose: bool = False, topology: Optional[SystemTopology] = None,
                 netserver_binary: Optional[str] = None,
                 ssh_host: Optional[str] = None):
        self.host = ssh_host or host or "localhost"
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_key = ssh_key
        self.netserver_path = netserver_binary or netserver_path
        self.base_port = base_port
        self.verbose = verbose
        self.topology = topology

    def is_remote(self) -> bool:
        return self.host not in ("localhost", "127.0.0.1", "::1", "")

    def _run_cmd(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
        """Run a shell command locally or via SSH on self.host."""
        if not self.is_remote():
            try:
                res = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=timeout
                )
                return (res.returncode, res.stdout, res.stderr)
            except Exception as e:
                return (-1, "", str(e))

        ssh_cmd = [
            "ssh",
            "-p", str(self.ssh_port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={min(timeout, 15)}",
        ]
        if self.ssh_key:
            ssh_cmd.extend(["-i", self.ssh_key])
        target = f"{self.ssh_user}@{self.host}" if self.ssh_user else self.host
        ssh_cmd.append(target)
        ssh_cmd.append(cmd)
        try:
            res = subprocess.run(
                ssh_cmd, capture_output=True, text=True, timeout=timeout
            )
            return (res.returncode, res.stdout, res.stderr)
        except Exception as e:
            return (-1, "", str(e))

    def plan_pool(self, topo: Optional[SystemTopology] = None, interface: Optional[str] = None,
                  numa_node: Optional[int] = None, max_instances: int = 64,
                  min_core_override: Optional[int] = None,
                  strategy: str = "auto", mtu: int = 9022,
                  count: Optional[int] = None, min_core: Optional[int] = None,
                  layout: Optional[str] = None) -> NetserverPoolSpec:
        """Build a deterministic per-core netserver launch plan from system topology."""
        topo = topo or self.topology or TopologyAnalyzer.discover_local(
            interfaces=[interface] if interface else None
        )
        effective_max = count if count is not None else max_instances
        effective_min_core = min_core if min_core is not None else min_core_override
        effective_strategy = layout if layout is not None else strategy

        if interface and interface in topo.interfaces:
            resolved_numa = topo.interfaces[interface].numa_node
        elif numa_node is not None:
            resolved_numa = numa_node
        else:
            resolved_numa = 0

        node_pool = topo.nodes.get(resolved_numa) or next(iter(topo.nodes.values()))
        candidate_cores = list(node_pool.app_cores) or list(node_pool.physical_cores)
        if effective_min_core is not None:
            filtered = [c for c in candidate_cores if c >= effective_min_core]
            if filtered:
                candidate_cores = filtered

        num_cores = min(effective_max, len(candidate_cores))
        resolved_strategy = TopologyAnalyzer.select_layout_strategy(
            topo, strategy=effective_strategy, num_flows=num_cores, mtu=mtu
        )
        selected_cores = TopologyAnalyzer.allocate_cores_from_pool(
            candidate_cores,
            count=num_cores,
            strategy=resolved_strategy,
            l2_modules=node_pool.l2_modules,
        )
        # Preserve ascending core order for pool startup while ensuring all selected cores are covered
        selected_unique = sorted(set(selected_cores))

        core_to_port: Dict[int, int] = {}
        commands: List[str] = []

        # Also start a fallback default netserver on port 12865 pinned to the first non-IRQ core
        if selected_unique:
            first_core = selected_unique[0]
            commands.append(
                f"numactl --physcpubind={first_core} --membind={resolved_numa} "
                f"{self.netserver_path} -p 12865"
            )

        for core in selected_unique:
            port = TopologyAnalyzer.get_netserver_port_for_core(core, self.base_port)
            core_to_port[core] = port
            commands.append(
                f"numactl --physcpubind={core} --membind={resolved_numa} "
                f"{self.netserver_path} -p {port}"
            )

        return NetserverPoolSpec(
            host=self.host,
            numa_node=resolved_numa,
            interface=interface or "",
            uarch=topo.uarch,
            base_port=self.base_port,
            default_port=12865,
            irq_cores_excluded=list(node_pool.irq_cores),
            isolation_cores_excluded=list(node_pool.isolation_cores),
            core_to_port=core_to_port,
            commands=commands,
        )

    def start_pool(self, spec: NetserverPoolSpec, dry_run: bool = False,
                   kill_existing: bool = True) -> Tuple[bool, str]:
        """Start the planned per-core netserver pool on target host."""
        if dry_run:
            return (True, f"[DRY RUN] Planned {len(spec.core_to_port)} pinned netserver instances")

        batch_cmds: List[str] = []
        if kill_existing:
            batch_cmds.append("pkill -9 netserver 2>/dev/null || true")
            batch_cmds.append("sleep 0.5")

        for cmd in spec.commands:
            batch_cmds.append(f"{cmd} >/dev/null 2>&1")

        batch_cmds.append("pgrep -c netserver || true")
        joined = " ; ".join(batch_cmds)
        rc, stdout, stderr = self._run_cmd(joined, timeout=60)
        if rc != 0:
            return (False, f"Failed to start netserver pool on {self.host}: {stderr}")

        lines = [ln.strip() for ln in stdout.strip().splitlines() if ln.strip().isdigit()]
        running_count = int(lines[-1]) if lines else 0
        expected = len(spec.core_to_port)
        if running_count < expected:
            return (
                False,
                f"Only {running_count}/{expected} netserver instances started on {self.host}"
            )
        return (True, f"Started {running_count} pinned netserver instances on {self.host} (NUMA {spec.numa_node})")

    def stop_pool(self, dry_run: bool = False) -> Tuple[bool, str]:
        """Stop all netserver processes on target host."""
        if dry_run:
            return (True, f"[DRY RUN] Would stop all netserver processes on {self.host}")
        rc, _, stderr = self._run_cmd("pkill -9 netserver 2>/dev/null || true", timeout=15)
        if rc != 0:
            return (False, f"Failed to stop netserver on {self.host}: {stderr}")
        return (True, f"Stopped all netserver instances on {self.host}")

    def verify_pool(self, spec: Optional[NetserverPoolSpec] = None,
                    min_instances: int = 1) -> Dict[str, Any]:
        """Audit running netserver processes and verify none are pinned to IRQ cores."""
        check_cmd = (
            "for p in $(pgrep netserver 2>/dev/null); do "
            "aff=$(taskset -pc $p 2>/dev/null | awk -F': ' '{print $2}'); "
            "args=$(ps -o args= -p $p 2>/dev/null); "
            "echo \"$p|$aff|$args\"; "
            "done"
        )
        rc, stdout, stderr = self._run_cmd(check_cmd, timeout=20)
        if rc != 0:
            return {
                "host": self.host,
                "healthy": False,
                "running_count": 0,
                "irq_collisions": [],
                "unpinned_pids": [],
                "error": stderr.strip(),
            }

        irq_set = set(spec.irq_cores_excluded) if spec else set()
        instances = []
        irq_collisions = []
        unpinned_pids = []

        for line in stdout.strip().splitlines():
            if "|" not in line:
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            pid_str, aff_str, args_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
            cpus = parse_cpu_list(aff_str)
            port_match = re.search(r'-p\s+(\d+)', args_str)
            port = int(port_match.group(1)) if port_match else 12865

            if len(cpus) > 2:
                unpinned_pids.append(int(pid_str))
            overlap = [c for c in cpus if c in irq_set]
            if overlap:
                irq_collisions.append({"pid": int(pid_str), "port": port, "irq_cores": overlap})

            instances.append({
                "pid": int(pid_str),
                "cpus": cpus,
                "port": port,
                "args": args_str,
            })

        healthy = (
            len(instances) >= min_instances
            and len(irq_collisions) == 0
            and len(unpinned_pids) == 0
        )
        return {
            "host": self.host,
            "healthy": healthy,
            "running_count": len(instances),
            "irq_collisions": irq_collisions,
            "unpinned_pids": unpinned_pids,
            "instances": instances,
        }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Manage topology-aware per-core pinned netserver pools (DUT & Load Partner)"
    )
    parser.add_argument("-H", "--host", default="localhost",
                        help="Target host (default: localhost, or SSH hostname/IP)")
    parser.add_argument("-u", "--ssh-user", help="SSH username for remote host")
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--ssh-key", help="SSH private key path")
    parser.add_argument("-i", "--interface", help="Bind netservers to NIC's local NUMA node")
    parser.add_argument("--numa-node", type=int, help="Explicit NUMA node override")
    parser.add_argument("--base-port", type=int, default=18600,
                        help="Base port for per-core netserver: port = base_port + core (default: 18600)")
    parser.add_argument("--max-instances", type=int, default=64,
                        help="Maximum per-core netserver instances to spawn (default: 64)")
    parser.add_argument("--min-core", type=int,
                        help="Minimum core ID override (e.g. 43 on LP if cores 0-42 handle IRQs)")
    parser.add_argument("--snapshot", metavar="FILE",
                        help="Use a topology snapshot file instead of live discovery")
    parser.add_argument("--netserver", default="netserver",
                        help="Path to netserver binary (default: netserver)")
    parser.add_argument("--export-map", metavar="FILE",
                        help="Write core-to-port mapping JSON to FILE")

    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--start", action="store_true", help="Start per-core pinned netserver pool")
    action.add_argument("--stop", action="store_true", help="Stop all netserver instances")
    action.add_argument("--verify", action="store_true", help="Verify running netserver pool hygiene")
    action.add_argument("--plan", action="store_true", help="Print planned per-core commands without executing")

    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.snapshot:
        topo = TopologyAnalyzer.from_topology_snapshot(Path(args.snapshot).read_text())
    else:
        topo = TopologyAnalyzer.discover_local(
            interfaces=[args.interface] if args.interface else None
        )

    mgr = NetserverPoolManager(
        host=args.host,
        ssh_user=args.ssh_user,
        ssh_port=args.ssh_port,
        ssh_key=args.ssh_key,
        netserver_path=args.netserver,
        base_port=args.base_port,
        verbose=args.verbose,
    )

    spec = mgr.plan_pool(
        topo,
        interface=args.interface,
        numa_node=args.numa_node,
        max_instances=args.max_instances,
        min_core_override=args.min_core,
    )

    if args.export_map:
        Path(args.export_map).write_text(json.dumps(spec.to_dict(), indent=2))
        print(f"Exported netserver core-to-port map to {args.export_map}")

    if args.plan:
        print(f"Planned {len(spec.core_to_port)} per-core netservers on {spec.host} "
              f"(NUMA {spec.numa_node}, uarch={spec.uarch}, IRQ cores excluded="
              f"{format_cpu_list(spec.irq_cores_excluded)}):")
        for cmd in spec.commands[:12]:
            print(f"  {cmd}")
        if len(spec.commands) > 12:
            print(f"  ... ({len(spec.commands) - 12} more commands)")
        return 0

    if args.stop:
        ok, msg = mgr.stop_pool(dry_run=args.dry_run)
        print(msg)
        return 0 if ok else 1

    if args.start:
        ok, msg = mgr.start_pool(spec, dry_run=args.dry_run)
        print(msg)
        return 0 if ok else 1

    if args.verify:
        report = mgr.verify_pool(spec)
        print(json.dumps(report, indent=2))
        return 0 if report.get("healthy") else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
