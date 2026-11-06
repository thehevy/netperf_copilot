#!/usr/bin/env python3
"""
netperf_topology.py - Architecture-Aware CPU, Cache, NUMA & NIC Topology Engine

Provides hardware discovery and core-pool partitioning for Intel Xeon 6
(Granite Rapids P-core, Sierra Forest / Clearwater Forest E-core) and modern
100G/200G/400G/800G Ethernet adapters (Intel E835/E830/E810 ice driver).

Key Capabilities:
- Detects E-core (4 cores / 4MB L2 module) vs P-core (1 physical core / 2MB L2)
- Parses NUMA nodes, Sub-NUMA Clustering (SNC), and filters out SMT sibling threads
- Queries NIC sysfs for PCIe Gen4/Gen5/Gen6 link speed/width & effective bandwidth
- Partitions per-NUMA cores into disjoint pools:
    1. IRQ Core Pool (NIC queue interrupts, e.g. cores 0..23)
    2. Non-IRQ App / Netserver Core Pool (strictly disjoint from IRQ cores)
    3. Background Isolation Core Pool (top cores reserved for vscode/kipmi0/daemons)
- Provides architecture-aware core allocators:
    - 'spread_step2' (E-core L2 module spread, +16% TX / +19% RX at 4 flows)
    - 'spread_l2'    (1 core per L2 module round-robin)
    - 'sequential'   (P-core contiguous physical cores)
- Allocates disjoint TX and RX core sets for concurrent bidirectional (BX) runs
- Computes per-core netserver port mappings (base_port + lp_core, default 18600 + c)

Author: Netperf Modernization Project - Phase 4/6
License: MIT
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


def parse_cpu_list(cpu_list_str: str) -> List[int]:
    """Parse Linux CPU range string (e.g. '0-71,144-215') into sorted unique ints."""
    if not cpu_list_str or not cpu_list_str.strip():
        return []
    cpus: List[int] = []
    for part in cpu_list_str.strip().split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            bounds = part.split('-')
            start, end = int(bounds[0]), int(bounds[1])
            step = int(bounds[2]) if len(bounds) > 2 else 1
            cpus.extend(range(start, end + 1, step))
        else:
            cpus.append(int(part))
    return sorted(set(cpus))


def format_cpu_list(cpus: List[int]) -> str:
    """Format a list of CPU IDs into compact Linux range notation (e.g. '0-23,26,28')."""
    if not cpus:
        return ""
    sorted_cpus = sorted(set(cpus))
    ranges: List[str] = []
    start = prev = sorted_cpus[0]
    for cpu in sorted_cpus[1:]:
        if cpu == prev + 1:
            prev = cpu
        else:
            ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = prev = cpu
    ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ",".join(ranges)


def compute_pcie_bw_and_gen(speed_str: str, width: Any) -> Tuple[float, int]:
    """Compute effective PCIe bandwidth in Gbps and PCIe generation from sysfs speed and width.

    Uses 128b/130b encoding for PCIe Gen3 (8 GT/s), Gen4 (16 GT/s), Gen5 (32 GT/s),
    and PAM4 FLIT encoding (~240/256) for PCIe Gen6 (64 GT/s).
    """
    try:
        w_str = str(width).strip().lower().lstrip('x')
        w_int = int(w_str) if w_str else 0
    except ValueError:
        w_int = 0
    if w_int <= 0:
        return (0.0, 0)
    match = re.search(r'(\d+(?:\.\d+)?)\s*GT/s', str(speed_str or ""), re.IGNORECASE)
    if not match:
        return (0.0, 0)
    gts = float(match.group(1))
    if gts >= 60.0:
        gen = 6
        bw = gts * w_int * (240.0 / 256.0)
    elif gts >= 30.0:
        gen = 5
        bw = gts * w_int * (128.0 / 130.0)
    elif gts >= 15.0:
        gen = 4
        bw = gts * w_int * (128.0 / 130.0)
    elif gts >= 7.5:
        gen = 3
        bw = gts * w_int * (128.0 / 130.0)
    else:
        gen = 2
        bw = gts * w_int * 0.8
    return (round(bw, 2), gen)


def compute_pcie_effective_bw_gbps(speed_str: str, width: Any) -> float:
    """Compute effective PCIe bandwidth in Gbps from sysfs speed string and lane width."""
    bw, _ = compute_pcie_bw_and_gen(speed_str, width)
    return bw


@dataclass
class InterfaceTopology:
    """Hardware and driver topology for a network interface."""
    name: str
    numa_node: int = 0
    pci_bdf: str = ""
    driver: str = ""
    firmware: str = ""
    link_speed_mbps: int = 0
    mtu: int = 1500
    pcie_current_speed: str = ""
    pcie_max_speed: str = ""
    pcie_current_width: int = 0
    pcie_max_width: int = 0
    pcie_gen: int = 0
    pcie_effective_bw_gbps: float = 0.0
    rx_ring: int = 0
    tx_ring: int = 0
    combined_channels: int = 0
    irq_cores: List[int] = field(default_factory=list)

    @property
    def pcie_speed(self) -> str:
        return self.pcie_current_speed

    @property
    def pcie_width(self) -> str:
        return str(self.pcie_current_width) if self.pcie_current_width else ""

    @property
    def oper_speed_mbps(self) -> int:
        return self.link_speed_mbps


@dataclass
class NodeCorePools:
    """Partitioned physical core pools for a single NUMA node."""
    numa_node: int
    all_logical_cpus: List[int] = field(default_factory=list)
    physical_cores: List[int] = field(default_factory=list)
    smt_siblings: List[int] = field(default_factory=list)
    l2_modules: List[List[int]] = field(default_factory=list)
    irq_cores: List[int] = field(default_factory=list)
    app_cores: List[int] = field(default_factory=list)
    isolation_cores: List[int] = field(default_factory=list)


@dataclass
class SystemTopology:
    """Complete CPU, cache, NUMA, and NIC topology of a host."""
    hostname: str = "localhost"
    model_name: str = "Unknown CPU"
    uarch: str = "generic"  # 'ecore' (CWF/SRF), 'pcore' (GNR/SPR/EMR), or 'generic'
    total_logical_cpus: int = 1
    threads_per_core: int = 1
    l2_cores_per_module: int = 1
    num_numa_nodes: int = 1
    snc_enabled: bool = False
    governor: str = "unknown"
    nodes: Dict[int, NodeCorePools] = field(default_factory=dict)
    interfaces: Dict[str, InterfaceTopology] = field(default_factory=dict)

    @property
    def arch_type(self) -> str:
        return self.uarch

    @property
    def l2_sharing_count(self) -> int:
        return self.l2_cores_per_module

    @property
    def numa_nodes(self) -> Dict[int, List[int]]:
        return {nid: pool.all_logical_cpus for nid, pool in self.nodes.items()}

    @property
    def core_pools(self) -> Dict[int, NodeCorePools]:
        return self.nodes

    @property
    def smt_enabled(self) -> bool:
        return self.threads_per_core >= 2

    @property
    def physical_cores_per_node(self) -> Dict[int, List[int]]:
        return {nid: pool.physical_cores for nid, pool in self.nodes.items()}

    def get_physical_cores(self, numa_node: int = 0) -> List[int]:
        pool = self.nodes.get(numa_node) or (next(iter(self.nodes.values())) if self.nodes else None)
        return list(pool.physical_cores) if pool else []

    def get_non_irq_app_cores(
        self, numa_node: int = 0, irq_reserve: Optional[int] = None, isolation_reserve: Optional[int] = None
    ) -> List[int]:
        pool = self.nodes.get(numa_node) or (next(iter(self.nodes.values())) if self.nodes else None)
        if not pool:
            return []
        if irq_reserve is not None or isolation_reserve is not None:
            phys = list(pool.physical_cores)
            irq_n = irq_reserve if irq_reserve is not None else len(pool.irq_cores)
            iso_n = isolation_reserve if isolation_reserve is not None else len(pool.isolation_cores)
            rem = phys[irq_n:] if irq_n < len(phys) else phys
            if iso_n > 0 and iso_n < len(rem):
                rem = rem[:-iso_n]
            return rem
        return list(pool.app_cores)

    def allocate_cores(
        self,
        count: int,
        numa_node: int = 0,
        layout: str = "auto",
        irq_reserve: Optional[int] = None,
        min_core: Optional[int] = None,
        mtu: int = 9000,
    ) -> List[int]:
        pool = self.nodes.get(numa_node) or (next(iter(self.nodes.values())) if self.nodes else None)
        if not pool:
            return list(range(count))
        candidates = self.get_non_irq_app_cores(numa_node=numa_node, irq_reserve=irq_reserve)
        if min_core is not None:
            filtered = [c for c in candidates if c >= min_core]
            if filtered:
                candidates = filtered
        resolved_strategy = TopologyAnalyzer.select_layout_strategy(self, layout, count, mtu)
        return TopologyAnalyzer.allocate_cores_from_pool(
            candidates, count=count, strategy=resolved_strategy, l2_modules=pool.l2_modules
        )

    def allocate_bx_cores(
        self,
        count_per_dir: int,
        numa_node: int = 0,
        layout: str = "auto",
        irq_reserve: Optional[int] = None,
        min_core: Optional[int] = None,
        mtu: int = 9000,
    ) -> Tuple[List[int], List[int]]:
        combined = self.allocate_cores(
            count=count_per_dir * 2,
            numa_node=numa_node,
            layout=layout,
            irq_reserve=irq_reserve,
            min_core=min_core,
            mtu=mtu,
        )
        return (combined[:count_per_dir], combined[count_per_dir:count_per_dir * 2])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'hostname': self.hostname,
            'model_name': self.model_name,
            'uarch': self.uarch,
            'arch_type': self.uarch,
            'total_logical_cpus': self.total_logical_cpus,
            'threads_per_core': self.threads_per_core,
            'l2_cores_per_module': self.l2_cores_per_module,
            'num_numa_nodes': self.num_numa_nodes,
            'snc_enabled': self.snc_enabled,
            'governor': self.governor,
            'nodes': {str(k): asdict(v) for k, v in self.nodes.items()},
            'interfaces': {k: asdict(v) for k, v in self.interfaces.items()},
        }


class TopologyAnalyzer:
    """Discovers and analyzes system topology and allocates optimal core sets."""

    DEFAULT_NETSERVER_BASE_PORT = 18600

    @staticmethod
    def classify_uarch(model_name: str, threads_per_core: int = 1,
                       l2_cores_per_module: int = 1) -> Tuple[str, int]:
        """Classify CPU microarchitecture as 'ecore', 'pcore', or 'generic'.

        Returns:
            (uarch, inferred_l2_cores_per_module)
        """
        model_upper = (model_name or "").upper()
        # Explicit sysfs L2 module sharing (4 physical cores sharing L2 = Xeon E-core)
        if l2_cores_per_module >= 4:
            return ('ecore', l2_cores_per_module)

        # Xeon 6 E-core model numbers end with E or E+ (e.g., 6980E+, 6780E, 6766E)
        if re.search(r'\b6\d{3}E\+?\b', model_upper) or 'CLEARWATER' in model_upper or 'SIERRA FOREST' in model_upper:
            return ('ecore', 4)

        # Xeon 6 P-core model numbers end with P (e.g., 6980P, 6960P, 6787P, 6530P)
        if re.search(r'\b6\d{3}P\b', model_upper) or 'GRANITE RAPIDS' in model_upper:
            return ('pcore', 1)

        # Other Intel Xeon Scalable P-core generations
        if 'XEON' in model_upper:
            if threads_per_core == 1 and l2_cores_per_module >= 2:
                return ('ecore', l2_cores_per_module)
            return ('pcore', 1)

        return ('generic', max(1, l2_cores_per_module))

    @classmethod
    def from_topology_snapshot(cls, text: str, default_irq_cores_per_node: int = 24,
                               isolation_cores_per_node: int = 8) -> SystemTopology:
        """Parse a topology snapshot file (such as cwf_dut_topology.txt, lscpu output, or section blocks)."""
        topo = SystemTopology()
        numa_cpus: Dict[int, List[int]] = {}
        current_iface: Optional[InterfaceTopology] = None
        current_section: str = ""
        l2_cluster_sizes: List[int] = []
        sibling_group_sizes: List[int] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Section header: === CPU_MODEL ===
            sec_match = re.match(r'^===\s*(\S+)\s*===$', line)
            if sec_match:
                current_section = sec_match.group(1).upper()
                current_iface = None
                continue

            # Interface section header: --- ens7np0 ---
            iface_match = re.match(r'^---\s*(\S+)\s*---$', line)
            if iface_match:
                ifname = iface_match.group(1)
                current_iface = InterfaceTopology(name=ifname)
                topo.interfaces[ifname] = current_iface
                current_section = ""
                continue

            if current_section == "CPU_MODEL":
                topo.model_name = line
                continue
            elif current_section == "NUMA":
                m_node = re.match(r'^node(\d+):\s*(.+)$', line, re.IGNORECASE)
                if m_node:
                    numa_cpus[int(m_node.group(1))] = parse_cpu_list(m_node.group(2))
                continue
            elif current_section == "L2_CLUSTERS":
                cpus = parse_cpu_list(line)
                if cpus:
                    l2_cluster_sizes.append(len(cpus))
                continue
            elif current_section == "THREAD_SIBLINGS":
                cpus = parse_cpu_list(line)
                if cpus:
                    sibling_group_sizes.append(len(cpus))
                continue
            elif current_section == "NIC_INFO":
                parts = line.split()
                if parts:
                    ifname = parts[0]
                    iface = InterfaceTopology(name=ifname)
                    m_numa = re.search(r'numa=(-?\d+)', line)
                    if m_numa:
                        iface.numa_node = max(0, int(m_numa.group(1)))
                    m_bdf = re.search(r'bdf=([0-9a-fA-F:.]+)', line)
                    if m_bdf:
                        iface.pci_bdf = m_bdf.group(1)
                    m_spd = re.search(r'speed=([0-9.]+\s*GT/s(?:\s*PCIe)?)', line)
                    if m_spd:
                        iface.pcie_current_speed = m_spd.group(1)
                    m_wid = re.search(r'width=(\d+)', line)
                    if m_wid:
                        iface.pcie_current_width = int(m_wid.group(1))
                    m_lmbps = re.search(r'link_mbps=(\d+)', line)
                    if m_lmbps:
                        iface.link_speed_mbps = int(m_lmbps.group(1))
                    m_mtu = re.search(r'mtu=(\d+)', line)
                    if m_mtu:
                        iface.mtu = int(m_mtu.group(1))
                    m_drv = re.search(r'driver=(\S+)', line)
                    if m_drv:
                        iface.driver = m_drv.group(1)
                    iface.pcie_effective_bw_gbps, iface.pcie_gen = compute_pcie_bw_and_gen(
                        iface.pcie_current_speed, iface.pcie_current_width
                    )
                    topo.interfaces[ifname] = iface
                continue

            if current_iface is not None:
                if line.startswith('NUMA:'):
                    val = line.split(':', 1)[1].strip()
                    try:
                        current_iface.numa_node = max(0, int(val))
                    except ValueError:
                        current_iface.numa_node = 0
                    continue
                elif line.startswith('PCI:'):
                    bdf_match = re.search(r'([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d)', line)
                    if bdf_match:
                        current_iface.pci_bdf = bdf_match.group(1)
                    continue
                elif line.startswith('Speed:'):
                    spd_match = re.search(r'(\d+)\s*Mb/s', line)
                    if spd_match:
                        current_iface.link_speed_mbps = int(spd_match.group(1))
                    continue
                elif line.startswith('Driver:'):
                    parts = line.split(':')
                    current_iface.driver = parts[-1].strip()
                    continue
                elif line.startswith('FW:'):
                    fw_match = re.search(r'firmware-version:\s*(.+)$', line)
                    if fw_match:
                        current_iface.firmware = fw_match.group(1).strip()
                    continue

            # Top-level lscpu / host fields
            if line.startswith('CPU(s):') and 'scaling' not in line and 'list' not in line:
                try:
                    topo.total_logical_cpus = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith('Model name:'):
                topo.model_name = line.split(':', 1)[1].strip()
            elif line.startswith('Thread(s) per core:'):
                try:
                    topo.threads_per_core = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith('NUMA node(s):'):
                try:
                    topo.num_numa_nodes = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith('Hostname:'):
                topo.hostname = line.split(':', 1)[1].strip()
            else:
                numa_match = re.match(r'^NUMA node(\d+) CPU\(s\):\s*(.+)$', line)
                if numa_match:
                    node_id = int(numa_match.group(1))
                    numa_cpus[node_id] = parse_cpu_list(numa_match.group(2))

        if sibling_group_sizes:
            topo.threads_per_core = max(sibling_group_sizes)
        l2_hint = max(l2_cluster_sizes) if l2_cluster_sizes else 1

        if not numa_cpus:
            numa_cpus[0] = list(range(topo.total_logical_cpus))
        else:
            topo.total_logical_cpus = sum(len(v) for v in numa_cpus.values())

        topo.uarch, topo.l2_cores_per_module = cls.classify_uarch(
            topo.model_name, topo.threads_per_core, l2_hint
        )
        topo.num_numa_nodes = len(numa_cpus)
        topo.snc_enabled = topo.num_numa_nodes > 2

        cls._populate_node_pools(
            topo,
            numa_cpus=numa_cpus,
            irq_cores_by_node={},
            default_irq_cores_per_node=default_irq_cores_per_node,
            isolation_cores_per_node=isolation_cores_per_node
        )
        return topo

    @classmethod
    def discover_local(cls, interfaces: Optional[List[str]] = None,
                       default_irq_cores_per_node: int = 24,
                       isolation_cores_per_node: int = 8,
                       sysfs_root: str = "/") -> SystemTopology:
        """Discover topology from local Linux sysfs / procfs (or fall back on non-Linux)."""
        root = Path(sysfs_root)
        cpu_root = root / "sys/devices/system/cpu"
        node_root = root / "sys/devices/system/node"
        net_root = root / "sys/class/net"

        topo = SystemTopology()
        try:
            import socket
            topo.hostname = socket.gethostname()
        except Exception:
            topo.hostname = "localhost"

        # If sysfs is not present (e.g. Windows dev workstation), build a fallback topology
        if not cpu_root.exists():
            cpu_count = os.cpu_count() or 16
            topo.total_logical_cpus = cpu_count
            topo.model_name = "Local Development CPU"
            topo.uarch = "generic"
            numa_cpus = {0: list(range(cpu_count))}
            cls._populate_node_pools(
                topo,
                numa_cpus=numa_cpus,
                irq_cores_by_node={},
                default_irq_cores_per_node=min(4, max(1, cpu_count // 4)),
                isolation_cores_per_node=min(2, max(0, cpu_count // 8))
            )
            return topo

        # 1. Parse /proc/cpuinfo for model name
        proc_cpuinfo = root / "proc/cpuinfo"
        if proc_cpuinfo.exists():
            try:
                for line in proc_cpuinfo.read_text(errors='ignore').splitlines():
                    if line.lower().startswith('model name'):
                        topo.model_name = line.split(':', 1)[1].strip()
                        break
            except Exception:
                pass

        # 2. Online CPUs
        online_file = cpu_root / "online"
        if online_file.exists():
            online_cpus = parse_cpu_list(online_file.read_text().strip())
            topo.total_logical_cpus = len(online_cpus)
        else:
            online_cpus = list(range(os.cpu_count() or 1))
            topo.total_logical_cpus = len(online_cpus)

        # 3. Governor
        gov_file = cpu_root / "cpu0/cpufreq/scaling_governor"
        if gov_file.exists():
            try:
                topo.governor = gov_file.read_text().strip()
            except Exception:
                pass

        # 4. Threads per core and L2 cache sharing on cpu0
        siblings_file = cpu_root / "cpu0/topology/thread_siblings_list"
        if siblings_file.exists():
            try:
                sibs = parse_cpu_list(siblings_file.read_text().strip())
                topo.threads_per_core = max(1, len(sibs))
            except Exception:
                pass

        l2_shared_file = cpu_root / "cpu0/cache/index2/shared_cpu_list"
        l2_physical_count = 1
        if l2_shared_file.exists():
            try:
                l2_cpus = parse_cpu_list(l2_shared_file.read_text().strip())
                l2_physical_count = max(1, len(l2_cpus) // max(1, topo.threads_per_core))
            except Exception:
                pass

        topo.uarch, topo.l2_cores_per_module = cls.classify_uarch(
            topo.model_name, topo.threads_per_core, l2_physical_count
        )

        # 5. NUMA nodes
        numa_cpus: Dict[int, List[int]] = {}
        if node_root.exists():
            for node_dir in sorted(node_root.glob("node[0-9]*")):
                m = re.match(r'^node(\d+)$', node_dir.name)
                if not m:
                    continue
                nid = int(m.group(1))
                cpulist_file = node_dir / "cpulist"
                if cpulist_file.exists():
                    numa_cpus[nid] = parse_cpu_list(cpulist_file.read_text().strip())

        if not numa_cpus:
            numa_cpus[0] = online_cpus

        topo.num_numa_nodes = len(numa_cpus)
        topo.snc_enabled = topo.num_numa_nodes > 2

        # 6. Network interfaces & IRQ mappings
        irq_cores_by_node: Dict[int, List[int]] = {}
        if net_root.exists():
            candidate_ifaces = interfaces or [
                p.name for p in sorted(net_root.iterdir())
                if p.name != "lo" and (p / "device").exists()
            ]
            for ifname in candidate_ifaces:
                if_dir = net_root / ifname
                if not if_dir.exists():
                    continue
                if_topo = cls._discover_interface_sysfs(ifname, if_dir, root)
                topo.interfaces[ifname] = if_topo
                if if_topo.irq_cores:
                    existing = irq_cores_by_node.setdefault(if_topo.numa_node, [])
                    existing.extend(if_topo.irq_cores)

        cls._populate_node_pools(
            topo,
            numa_cpus=numa_cpus,
            irq_cores_by_node=irq_cores_by_node,
            default_irq_cores_per_node=default_irq_cores_per_node,
            isolation_cores_per_node=isolation_cores_per_node
        )
        return topo

    @classmethod
    def _discover_interface_sysfs(cls, ifname: str, if_dir: Path, root: Path) -> InterfaceTopology:
        """Read sysfs and /proc/interrupts metadata for a network interface."""
        info = InterfaceTopology(name=ifname)
        dev_dir = if_dir / "device"

        def _read_str(p: Path) -> str:
            try:
                return p.read_text().strip() if p.exists() else ""
            except Exception:
                return ""

        # Speed & MTU
        spd = _read_str(if_dir / "speed")
        if spd and spd.lstrip('-').isdigit():
            info.link_speed_mbps = max(0, int(spd))
        mtu_str = _read_str(if_dir / "mtu")
        if mtu_str.isdigit():
            info.mtu = int(mtu_str)

        if dev_dir.exists():
            numa_str = _read_str(dev_dir / "numa_node")
            if numa_str.lstrip('-').isdigit():
                info.numa_node = max(0, int(numa_str))
            try:
                real_dev = os.path.realpath(str(dev_dir))
                info.pci_bdf = os.path.basename(real_dev)
            except Exception:
                pass
            drv_link = dev_dir / "driver"
            if drv_link.exists():
                try:
                    info.driver = os.path.basename(os.path.realpath(str(drv_link)))
                except Exception:
                    pass
            info.pcie_current_speed = _read_str(dev_dir / "current_link_speed")
            info.pcie_max_speed = _read_str(dev_dir / "max_link_speed")
            cur_w = _read_str(dev_dir / "current_link_width")
            max_w = _read_str(dev_dir / "max_link_width")
            if cur_w.isdigit():
                info.pcie_current_width = int(cur_w)
            if max_w.isdigit():
                info.pcie_max_width = int(max_w)
            info.pcie_effective_bw_gbps, info.pcie_gen = compute_pcie_bw_and_gen(
                info.pcie_current_speed, info.pcie_current_width
            )

        # Parse /proc/interrupts for interface queues (e.g., ice-ens7np0-TxRx-*)
        proc_intr = root / "proc/interrupts"
        if proc_intr.exists():
            irq_cores: List[int] = []
            try:
                for line in proc_intr.read_text(errors='ignore').splitlines():
                    if ifname in line:
                        irq_num = line.strip().split(':', 1)[0].strip()
                        if irq_num.isdigit():
                            aff_file = root / f"proc/irq/{irq_num}/smp_affinity_list"
                            aff_str = _read_str(aff_file)
                            if aff_str:
                                irq_cores.extend(parse_cpu_list(aff_str))
            except Exception:
                pass
            info.irq_cores = sorted(set(irq_cores))

        return info

    @classmethod
    def _populate_node_pools(cls, topo: SystemTopology,
                             numa_cpus: Dict[int, List[int]],
                             irq_cores_by_node: Dict[int, List[int]],
                             default_irq_cores_per_node: int = 24,
                             isolation_cores_per_node: int = 8) -> None:
        """Partition each NUMA node's CPUs into physical, SMT, L2 modules, IRQ, App, and Isolation pools."""
        topo.nodes = {}
        for node_id, all_cpus in sorted(numa_cpus.items()):
            all_sorted = sorted(all_cpus)
            if topo.threads_per_core >= 2 and len(all_sorted) >= 2:
                # In Linux on Xeon P-core (e.g. 0-71,144-215), the first half of the node's
                # CPU list is primary physical threads and the second half is SMT siblings.
                half = len(all_sorted) // topo.threads_per_core
                physical = all_sorted[:half]
                smt = all_sorted[half:]
            else:
                physical = list(all_sorted)
                smt = []

            # Group physical cores into L2 cache modules
            l2_size = max(1, topo.l2_cores_per_module)
            l2_modules = [
                physical[i:i + l2_size]
                for i in range(0, len(physical), l2_size)
            ]

            # Determine IRQ cores on this node
            discovered_irqs = sorted(set(irq_cores_by_node.get(node_id, [])))
            if discovered_irqs:
                irq_cores = [c for c in discovered_irqs if c in physical]
            else:
                irq_count = min(default_irq_cores_per_node, max(0, len(physical) // 4))
                irq_cores = physical[:irq_count]

            # Determine Isolation cores at the top of physical cores
            remaining = [c for c in physical if c not in set(irq_cores)]
            iso_count = min(isolation_cores_per_node, max(0, len(remaining) // 8))
            if iso_count > 0:
                isolation_cores = remaining[-iso_count:]
                app_cores = remaining[:-iso_count]
            else:
                isolation_cores = []
                app_cores = remaining

            topo.nodes[node_id] = NodeCorePools(
                numa_node=node_id,
                all_logical_cpus=all_sorted,
                physical_cores=physical,
                smt_siblings=smt,
                l2_modules=l2_modules,
                irq_cores=irq_cores,
                app_cores=app_cores,
                isolation_cores=isolation_cores,
            )

    @classmethod
    def select_layout_strategy(cls, topo: SystemTopology, strategy: str = "auto",
                               num_flows: int = 8, mtu: int = 9000) -> str:
        """Resolve 'auto' layout strategy based on CPU microarchitecture, flow count, and MTU.

        BKM Rules from 01_MULTI_TESTBED_FINDINGS.md & 07_ECORE_PCORE_COMPARISON.md:
        - Xeon 6 E-core (CWF/SRF): 'spread_step2' spaces threads across 4-core L2 modules
          (+16% TX, +19% RX at 4 flows). At MTU 1500 small packets with 16 flows, tight
          contiguous 'sequential' placement on local tiles is optimal.
        - Xeon 6 P-core (GNR): Dedicated 2MB L2 per core -> 'sequential' is optimal.
        """
        if strategy and strategy != "auto":
            return strategy
        if topo.uarch == "ecore":
            if mtu <= 1500 and num_flows >= 16:
                return "sequential"
            return "spread_l2"
        if topo.uarch == "pcore":
            return "spread_step2"
        return "sequential"

    @classmethod
    def allocate_cores_from_pool(cls, app_cores: List[int], count: int,
                                 strategy: str = "sequential",
                                 l2_modules: Optional[List[List[int]]] = None,
                                 offset: int = 0) -> List[int]:
        """Select `count` physical cores from `app_cores` using the requested layout strategy."""
        if not app_cores or count <= 0:
            return []

        pool = app_cores[offset:] if offset < len(app_cores) else list(app_cores)
        if not pool:
            pool = list(app_cores)

        if strategy == "spread_step2":
            # Take every 2nd physical core first (e.g., 24, 26, 28, 30...), then odd indices if needed
            even_step = pool[0::2]
            odd_step = pool[1::2]
            ordered = even_step + odd_step
        elif strategy == "spread_l2" and l2_modules:
            app_set = set(pool)
            filtered_mods = [[c for c in mod if c in app_set] for mod in l2_modules]
            filtered_mods = [m for m in filtered_mods if m]
            ordered = []
            max_len = max((len(m) for m in filtered_mods), default=0)
            for idx in range(max_len):
                for mod in filtered_mods:
                    if idx < len(mod):
                        ordered.append(mod[idx])
        else:
            # 'sequential'
            ordered = list(pool)

        selected: List[int] = []
        while len(selected) < count:
            for c in ordered:
                if len(selected) >= count:
                    break
                selected.append(c)
        return selected

    @classmethod
    def allocate_flow_cores(cls, topo: SystemTopology, num_flows: int = 8,
                            numa_node: int = 0, interface: Optional[str] = None,
                            strategy: str = "auto", mtu: int = 9000,
                            min_core_override: Optional[int] = None,
                            layout: Optional[str] = None) -> List[int]:
        """Allocate non-IRQ physical cores for `num_flows` streams on the target NUMA node."""
        effective_strategy = layout if layout is not None else strategy
        if interface and interface in topo.interfaces:
            numa_node = topo.interfaces[interface].numa_node

        node_pool = topo.nodes.get(numa_node) or next(iter(topo.nodes.values()))
        candidate_cores = list(node_pool.app_cores) or list(node_pool.physical_cores)
        if min_core_override is not None:
            filtered = [c for c in candidate_cores if c >= min_core_override]
            if filtered:
                candidate_cores = filtered

        resolved_strategy = cls.select_layout_strategy(topo, effective_strategy, num_flows, mtu)
        return cls.allocate_cores_from_pool(
            candidate_cores,
            count=num_flows,
            strategy=resolved_strategy,
            l2_modules=node_pool.l2_modules,
        )

    @classmethod
    def allocate_bx_cores(cls, topo: SystemTopology, num_tx_flows: int = 4, num_rx_flows: int = 4,
                          numa_node: int = 0, interface: Optional[str] = None,
                          strategy: str = "auto", mtu: int = 9000,
                          min_core_override: Optional[int] = None,
                          num_tx: Optional[int] = None,
                          num_rx: Optional[int] = None,
                          layout: Optional[str] = None) -> Tuple[List[int], List[int]]:
        """Allocate strictly disjoint TX and RX non-IRQ core lists for concurrent BX tests.

        Prevents TX and RX threads from contending on the same physical core or L2 module
        (fixing the E-core RX starvation under BX load documented in 07_ECORE_PCORE_COMPARISON.md).
        """
        eff_tx = num_tx if num_tx is not None else num_tx_flows
        eff_rx = num_rx if num_rx is not None else num_rx_flows
        eff_strategy = layout if layout is not None else strategy
        total = eff_tx + eff_rx
        combined = cls.allocate_flow_cores(
            topo,
            num_flows=total,
            numa_node=numa_node,
            interface=interface,
            strategy=eff_strategy,
            mtu=mtu,
            min_core_override=min_core_override,
        )
        tx_cores = combined[:eff_tx]
        rx_cores = combined[eff_tx:eff_tx + eff_rx]
        return (tx_cores, rx_cores)

    @classmethod
    def get_bkm_parameters(cls, topo: SystemTopology, num_flows: int = 8,
                           mtu: int = 9022) -> Dict[str, Any]:
        """Return architecture-specific Best Known Methods (BKM) tuning parameters.

        Directly encodes findings from 01_MULTI_TESTBED_FINDINGS.md and 03_BKM_DEPLOYMENT_GUIDE.md:
        - Xeon 6 E-core (CWF/SRF):
            * 4-6 flows @ MTU 9022 -> ring=512 (8KB ring fits in 4MB L2), spread_step2
            * 8+ flows  @ MTU 9022 -> ring=4096, spread_step2
            * MTU 1500             -> ring=2048, compact IRQ cores, 16 flows
        - Xeon 6 P-core (GNR):
            * NEVER ring=512 (-33% throughput drop on GNR!)
            * ring=2048 (or 4096 at 8+ flows), sequential core placement, 4-8 flows
        """
        if topo.uarch == "ecore":
            if mtu <= 1500:
                rx_ring, tx_ring = 2048, 2048
                app_layout = "sequential"
                irq_layout = "compact"
                rec_flows = 16
            else:
                rx_ring, tx_ring = 4096, 512
                app_layout = "spread_l2"
                irq_layout = "compact"
                rec_flows = 16 if num_flows >= 8 else 8
        else:
            # P-core (GNR) or generic
            rx_ring = 4096
            tx_ring = 2048
            app_layout = "spread_step2" if topo.uarch == "pcore" else "sequential"
            irq_layout = "sequential"
            rec_flows = 8 if mtu >= 9000 else 16

        return {
            'uarch': topo.uarch,
            'model_name': topo.model_name,
            'mtu': mtu,
            'rx_ring': rx_ring,
            'tx_ring': tx_ring,
            'rx_usecs': 10,
            'tx_usecs': 20,
            'adaptive_rx': 'off',
            'adaptive_tx': 'off',
            'app_core_layout': app_layout,
            'irq_core_layout': irq_layout,
            'recommended_flows_per_port': rec_flows,
            'msix_vec_per_pf_max': 65,
            'tx_scheduling_layers': 5,
            'tcp_congestion_control': 'cubic',
            'busy_poll': 0,
            'busy_read': 0,
            'numa_balancing': 0,
        }

    @classmethod
    def get_netserver_port_for_core(cls, core_id: int,
                                    base_port: int = DEFAULT_NETSERVER_BASE_PORT) -> int:
        """Compute deterministic control port for a pinned per-core netserver instance."""
        return base_port + int(core_id)

    # Aliases for convenience across preflight, tuner, and catalog tools
    detect_live = discover_local
    parse_snapshot_text = from_topology_snapshot


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Analyze CPU, L2 cache, NUMA, and NIC topology for netperf_copilot"
    )
    parser.add_argument("--snapshot", metavar="FILE",
                        help="Parse topology from a saved topology snapshot file")
    parser.add_argument("-i", "--interface", action="append", dest="interfaces",
                        help="Interface(s) to inspect (can be specified multiple times)")
    parser.add_argument("-n", "--flows", type=int, default=8,
                        help="Number of flows to allocate cores for (default: 8)")
    parser.add_argument("--mtu", type=int, default=9022,
                        help="Target MTU for BKM lookup (default: 9022)")
    parser.add_argument("--strategy", choices=["auto", "spread_step2", "spread_l2", "sequential"],
                        default="auto", help="Core allocation strategy (default: auto)")
    parser.add_argument("--json", action="store_true",
                        help="Output full topology and BKM recommendation as JSON")
    args = parser.parse_args()

    if args.snapshot:
        text = Path(args.snapshot).read_text()
        topo = TopologyAnalyzer.from_topology_snapshot(text)
    else:
        topo = TopologyAnalyzer.discover_local(interfaces=args.interfaces)

    primary_if = args.interfaces[0] if args.interfaces else (
        next(iter(topo.interfaces.keys()), None)
    )
    tx_cores, rx_cores = TopologyAnalyzer.allocate_bx_cores(
        topo, args.flows, args.flows, interface=primary_if,
        strategy=args.strategy, mtu=args.mtu
    )
    bkm = TopologyAnalyzer.get_bkm_parameters(topo, num_flows=args.flows, mtu=args.mtu)

    if args.json:
        out = topo.to_dict()
        out["allocation"] = {
            "interface": primary_if,
            "flows": args.flows,
            "strategy": TopologyAnalyzer.select_layout_strategy(
                topo, args.strategy, args.flows, args.mtu
            ),
            "tx_cores": tx_cores,
            "rx_cores": rx_cores,
        }
        out["bkm"] = bkm
        print(json.dumps(out, indent=2))
        return 0

    print(f"{'='*70}")
    print(f"Host Topology: {topo.hostname} ({topo.model_name})")
    print(f"{'='*70}")
    print(f"Microarchitecture:  {topo.uarch.upper()} ({topo.l2_cores_per_module} physical core(s)/L2 module)")
    print(f"Logical CPUs:       {topo.total_logical_cpus} ({topo.threads_per_core} thread(s)/core)")
    print(f"NUMA Nodes:         {topo.num_numa_nodes} (SNC: {'Yes' if topo.snc_enabled else 'No'})")
    print(f"CPU Governor:       {topo.governor}")
    for nid, pool in sorted(topo.nodes.items()):
        print(f"\n  NUMA Node {nid}:")
        print(f"    Physical Cores ({len(pool.physical_cores)}): {format_cpu_list(pool.physical_cores)}")
        print(f"    IRQ Core Pool  ({len(pool.irq_cores)}): {format_cpu_list(pool.irq_cores)}")
        print(f"    App Core Pool  ({len(pool.app_cores)}): {format_cpu_list(pool.app_cores)}")
        print(f"    Isolation Pool ({len(pool.isolation_cores)}): {format_cpu_list(pool.isolation_cores)}")
    if topo.interfaces:
        print(f"\n  Interfaces:")
        for ifname, if_topo in topo.interfaces.items():
            print(f"    {ifname:12s}: NUMA {if_topo.numa_node} | PCI {if_topo.pci_bdf or 'N/A'} | "
                  f"{if_topo.link_speed_mbps // 1000}GbE ({if_topo.driver}) | "
                  f"PCIe {if_topo.pcie_current_speed or 'N/A'} x{if_topo.pcie_current_width} "
                  f"({if_topo.pcie_effective_bw_gbps} Gbps eff)")
    print(f"\n  Allocated Non-IRQ Cores ({args.flows} TX + {args.flows} RX, strategy="
          f"{TopologyAnalyzer.select_layout_strategy(topo, args.strategy, args.flows, args.mtu)}):")
    print(f"    TX Cores: {format_cpu_list(tx_cores)} -> {tx_cores}")
    print(f"    RX Cores: {format_cpu_list(rx_cores)} -> {rx_cores}")
    print(f"  Recommended BKM: ring RX={bkm['rx_ring']}/TX={bkm['tx_ring']}, "
          f"coalesce rx-usecs={bkm['rx_usecs']}/tx-usecs={bkm['tx_usecs']}, "
          f"scheduler={bkm['tx_scheduling_layers']}-layer")
    print(f"{'='*70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
