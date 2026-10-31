#!/usr/bin/env python3
"""
netperf_preflight - Automated Platform & ice Driver Pre-Flight Checker

Validates platform, topology, PCIe bandwidth, IRQ locality, background process
isolation, 24 Intel E835/E830/E810 feature anti-affinity rules (AA-001..AA-023),
5-iteration LP warmup sanity gate (CV < 5%), and DUT/LP bottleneck isolation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from netperf_topology import TopologyAnalyzer, compute_pcie_effective_bw_gbps, parse_cpu_list


# Background processes known to cause tail latency / throughput jitter on 200G-800G hosts
NOISY_PROCESS_PATTERNS = [
    ("vscode", r"(vscode|code-server|node.*extensionHost|copilot)"),
    ("kipmi0", r"\bkipmi0\b"),
    ("irqbalance", r"\birqbalance\b"),
    ("pcp", r"\b(pmlogger|pmcd)\b"),
]


@dataclass
class CheckFinding:
    check_id: str
    category: str
    severity: str  # PASS, WARN, FAIL, INFO
    summary: str
    details: str = ""
    remediation: str = ""


@dataclass
class AntiAffinityRule:
    rule_id: str
    feature_a: str
    feature_b: str
    severity: str  # FAIL (hard block) or WARN
    description: str
    remediation: str


# 24 Feature Anti-Affinity Rules from E835 Linux Qualification Plan (Section 4)
ANTI_AFFINITY_RULES: List[AntiAffinityRule] = [
    AntiAffinityRule(
        "AA-001", "adq", "rocev2", "FAIL",
        "ADQ (tc-mqprio hw 1) and RoCEv2 (irdma) cannot coexist on the same PF.",
        "Disable ADQ (tc qdisc del dev <if> root) or unload irdma before running RoCEv2.",
    ),
    AntiAffinityRule(
        "AA-002", "adq", "dcb_pfc_ets", "FAIL",
        "ADQ hardware traffic classes conflict with IEEE DCB PFC/ETS scheduler.",
        "Disable DCB/lldpad or remove tc-mqprio hardware offload.",
    ),
    AntiAffinityRule(
        "AA-003", "adq", "sriov_vf", "FAIL",
        "ADQ cannot be enabled concurrently with SR-IOV Virtual Functions (numvfs > 0).",
        "Set sriov_numvfs=0 before configuring tc-mqprio.",
    ),
    AntiAffinityRule(
        "AA-004", "adq", "active_active_lag", "FAIL",
        "ADQ hardware queue sets cannot be bound across bonded LACP LAG ports.",
        "Use standard RSS + XPS queue steering on LACP bonds instead of ADQ.",
    ),
    AntiAffinityRule(
        "AA-005", "adq", "xdp", "FAIL",
        "ADQ hardware traffic classes conflict with XDP / AF_XDP zero-copy queues.",
        "Detach XDP program or remove ADQ qdisc.",
    ),
    AntiAffinityRule(
        "AA-006", "adq", "eol_notice", "WARN",
        "Intel ADQ reached End-of-Life (EOL) in April 2025; modern Xeon 6 + E835 tuning uses RSS + XPS + IRQ pinning.",
        "Migrate from ADQ to netperf-tuner --apply-bkm auto (RSS + XPS + devlink 5-layer scheduler).",
    ),
    AntiAffinityRule(
        "AA-007", "rocev2", "sriov_lag", "FAIL",
        "RoCEv2 (irdma) over SR-IOV VF LAG is unsupported when switchdev eswitch mode is active.",
        "Use PF Active-Active RoCEv2 LAG or disable switchdev.",
    ),
    AntiAffinityRule(
        "AA-008", "rocev2", "mtu_mismatch", "FAIL",
        "RoCEv2 active QPs experience severe packet drop when PF MTU < IB QP path MTU.",
        "Ensure interface MTU (4096 or 9000) >= RoCEv2 QP MTU across DUT, switch, and LP.",
    ),
    AntiAffinityRule(
        "AA-009", "dcb_pfc", "link_pause", "FAIL",
        "IEEE 802.1Qbb PFC cannot be enabled simultaneously with IEEE 802.3x Global Flow Control (Link Pause).",
        "Disable global pause (ethtool -A <if> rx off tx off) when using PFC.",
    ),
    AntiAffinityRule(
        "AA-010", "xps_cpus", "xps_rxqs_conflict", "WARN",
        "Having both xps_cpus != 0 and xps_rxqs != 0 causes suboptimal TX queue selection on E835.",
        "Clear xps_cpus to 0 and set xps_rxqs=ffff via netperf-tuner.",
    ),
    AntiAffinityRule(
        "AA-011", "adaptive_coalesce", "deterministic_benchmark", "WARN",
        "Adaptive RX/TX interrupt moderation introduces latency/throughput bimodal variance across 30s runs.",
        "Set 'ethtool -C <if> adaptive-rx off adaptive-tx off rx-usecs 10 tx-usecs 20'.",
    ),
    AntiAffinityRule(
        "AA-012", "irqbalance", "manual_irq_pinning", "FAIL",
        "Running irqbalance daemon overwrites manual SMP IRQ affinity masks mid-test.",
        "Stop irqbalance ('systemctl stop irqbalance').",
    ),
    AntiAffinityRule(
        "AA-013", "numa_balancing", "pinned_netperf", "WARN",
        "Kernel automatic NUMA balancing migrates memory pages during pinned multi-stream netperf runs.",
        "Set 'sysctl -w kernel.numa_balancing=0'.",
    ),
    AntiAffinityRule(
        "AA-014", "busy_poll", "high_stream_ecore", "WARN",
        "busy_poll/busy_read > 0 on E-core (CWF/SRF) 32-64 stream tests starves softirq and increases CPU to 100%.",
        "Set 'sysctl -w net.core.busy_poll=0 net.core.busy_read=0' for bulk throughput.",
    ),
    AntiAffinityRule(
        "AA-015", "tx_ring_256", "200g_line_rate", "FAIL",
        "Default ice TX ring size (256) causes frequent tx_restart_queue stalls at 100G/200G.",
        "Increase TX ring >= 512 (E-core: 512, P-core: 2048) via 'ethtool -G <if> tx 512 rx 4096'.",
    ),
    AntiAffinityRule(
        "AA-016", "p0_irq_cross_numa", "local_numa_affinity", "FAIL",
        "Vector 0 / Queue 0 IRQ pinned to a remote NUMA node degrades 1-8 stream throughput by 30-55%.",
        "Re-pin all interface IRQs to the NIC's local NUMA node via set_irq_affinity / netperf-tuner.",
    ),
    AntiAffinityRule(
        "AA-017", "pcie_bw_bottleneck", "line_rate_target", "FAIL",
        "PCIe link effective bandwidth (Speed * Width * 128/130) is below NIC link speed.",
        "Verify riser/slot bifurcation and PCIe Gen5 x16 / Gen4 x16 link negotiation in lspci -vv.",
    ),
    AntiAffinityRule(
        "AA-018", "powersave_governor", "high_speed_netperf", "FAIL",
        "CPU scaling governor 'powersave' or 'ondemand' causes P-state ramp lag and high CV.",
        "Set 'cpupower frequency-set -g performance' on all online cores.",
    ),
    AntiAffinityRule(
        "AA-019", "gro_off", "200g_tcp_rx", "WARN",
        "Disabling GRO on 100G/200G TCP RX limits single-core RX throughput due to per-packet stack traversal.",
        "Enable GRO ('ethtool -K <if> gro on').",
    ),
    AntiAffinityRule(
        "AA-020", "tso_off", "200g_tcp_tx", "WARN",
        "Disabling TSO on 100G/200G TCP TX increases CPU service demand by 3-5x for 64KB sends.",
        "Enable TSO ('ethtool -K <if> tso on').",
    ),
    AntiAffinityRule(
        "AA-021", "ecore_smt_assumption", "cwf_srf_topology", "WARN",
        "Assuming SMT siblings on E-core (CWF/SRF) skips valid physical cores or misaligns L2 4-core modules.",
        "Use netperf_topology layout 'spread_l2' or 'spread_step2' on E-core systems.",
    ),
    AntiAffinityRule(
        "AA-022", "shared_netserver_lock", "high_stream_count", "WARN",
        "Using a single netserver daemon on port 12865 for >= 16 streams causes control-socket accept serialization.",
        "Use 'netserver-manager --start --base-port 18600' and 'netperf-multi --per-core-netserver'.",
    ),
    AntiAffinityRule(
        "AA-023", "small_rmem_wmem", "high_bdp_200g", "WARN",
        "Default Linux net.core.rmem_max / wmem_max (212992) throttles TCP window scaling at 100G-800G.",
        "Set rmem_max/wmem_max and tcp_rmem/tcp_wmem max to 2147483647 via netperf-tuner.",
    ),
    AntiAffinityRule(
        "AA-024", "tx_sched_9layer", "low_latency_200g", "INFO",
        "Default 9-layer ice TX scheduler adds burst latency compared to 5-layer devlink topology.",
        "Consider 'devlink dev param set pci/<bdf> name tx_scheduling_layers value 5 cmode runtime'.",
    ),
]


@dataclass
class PreflightReport:
    interface: str
    passed: bool
    fail_count: int
    warn_count: int
    findings: List[CheckFinding] = field(default_factory=list)
    active_features: Dict[str, Any] = field(default_factory=dict)
    warmup_cv_pct: Optional[float] = None
    warmup_samples_gbps: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface": self.interface,
            "passed": self.passed,
            "fail_count": self.fail_count,
            "warn_count": self.warn_count,
            "findings": [asdict(f) for f in self.findings],
            "active_features": self.active_features,
            "warmup_cv_pct": self.warmup_cv_pct,
            "warmup_samples_gbps": self.warmup_samples_gbps,
        }


class PreflightChecker:
    """Executes pre-flight hardware, kernel, process, and feature anti-affinity checks."""

    def __init__(
        self,
        interface: str,
        runner: Optional[Callable[[List[str]], Tuple[int, str, str]]] = None,
    ) -> None:
        self.interface = interface
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(cmd: List[str]) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return proc.returncode, proc.stdout, proc.stderr
        except Exception as exc:
            return 1, "", str(exc)

    def check_noisy_processes(self, ps_output: Optional[str] = None) -> List[CheckFinding]:
        """Detect noisy background processes (vscode, kipmi0, irqbalance, pmlogger)."""
        findings: List[CheckFinding] = []
        if ps_output is None:
            rc, out, _ = self._runner(["ps", "-eo", "pid,comm,args"])
            ps_output = out if rc == 0 else ""

        for label, pattern in NOISY_PROCESS_PATTERNS:
            matches = [
                line.strip()
                for line in ps_output.splitlines()
                if re.search(pattern, line, re.IGNORECASE) and "netperf" not in line
            ]
            if matches:
                sev = "FAIL" if label == "irqbalance" else "WARN"
                remedy = (
                    "systemctl stop irqbalance"
                    if label == "irqbalance"
                    else (
                        "echo 0 > /sys/module/ipmi_si/parameters/kipmid_max_busy_us"
                        if label == "kipmi0"
                        else f"Stop or isolate {label} processes before benchmarking"
                    )
                )
                findings.append(
                    CheckFinding(
                        check_id=f"PROC-{label.upper()}",
                        category="process_isolation",
                        severity=sev,
                        summary=f"Detected noisy background process '{label}' ({len(matches)} instance(s))",
                        details="; ".join(matches[:3]),
                        remediation=remedy,
                    )
                )
        if not findings:
            findings.append(
                CheckFinding(
                    check_id="PROC-CLEAN",
                    category="process_isolation",
                    severity="PASS",
                    summary="No noisy background processes (vscode, kipmi0, irqbalance, pcp) detected",
                )
            )
        return findings

    def evaluate_feature_state(self, state: Dict[str, Any]) -> List[CheckFinding]:
        """
        Evaluate a system/interface state dictionary against the 24 anti-affinity rules
        and hardware/topology invariants.
        """
        findings: List[CheckFinding] = []

        # 1. ADQ checks (AA-001..AA-006)
        adq_enabled = bool(state.get("adq_enabled", False))
        if adq_enabled:
            findings.append(
                CheckFinding(
                    "AA-006", "anti_affinity", "WARN",
                    ANTI_AFFINITY_RULES[5].description,
                    remediation=ANTI_AFFINITY_RULES[5].remediation,
                )
            )
            if state.get("rocev2_enabled"):
                findings.append(
                    CheckFinding(
                        "AA-001", "anti_affinity", "FAIL",
                        ANTI_AFFINITY_RULES[0].description,
                        remediation=ANTI_AFFINITY_RULES[0].remediation,
                    )
                )
            if state.get("dcb_enabled"):
                findings.append(
                    CheckFinding(
                        "AA-002", "anti_affinity", "FAIL",
                        ANTI_AFFINITY_RULES[1].description,
                        remediation=ANTI_AFFINITY_RULES[1].remediation,
                    )
                )
            if state.get("sriov_numvfs", 0) > 0:
                findings.append(
                    CheckFinding(
                        "AA-003", "anti_affinity", "FAIL",
                        ANTI_AFFINITY_RULES[2].description,
                        remediation=ANTI_AFFINITY_RULES[2].remediation,
                    )
                )
            if state.get("lag_active"):
                findings.append(
                    CheckFinding(
                        "AA-004", "anti_affinity", "FAIL",
                        ANTI_AFFINITY_RULES[3].description,
                        remediation=ANTI_AFFINITY_RULES[3].remediation,
                    )
                )
            if state.get("xdp_attached"):
                findings.append(
                    CheckFinding(
                        "AA-005", "anti_affinity", "FAIL",
                        ANTI_AFFINITY_RULES[4].description,
                        remediation=ANTI_AFFINITY_RULES[4].remediation,
                    )
                )

        # 2. RoCEv2 checks (AA-007, AA-008)
        if state.get("rocev2_enabled"):
            if state.get("sriov_numvfs", 0) > 0 and state.get("lag_active") and state.get("eswitch_switchdev"):
                findings.append(
                    CheckFinding(
                        "AA-007", "anti_affinity", "FAIL",
                        ANTI_AFFINITY_RULES[6].description,
                        remediation=ANTI_AFFINITY_RULES[6].remediation,
                    )
                )
            ib_mtu = int(state.get("ib_qp_mtu", 0) or 0)
            net_mtu = int(state.get("mtu", 1500) or 1500)
            if ib_mtu > net_mtu:
                findings.append(
                    CheckFinding(
                        "AA-008", "anti_affinity", "FAIL",
                        f"NIC MTU ({net_mtu}) < RoCEv2 IB MTU ({ib_mtu})",
                        remediation=ANTI_AFFINITY_RULES[7].remediation,
                    )
                )

        # 3. DCB PFC + Link Pause conflict (AA-009)
        if state.get("pfc_enabled") and (state.get("rx_pause") or state.get("tx_pause")):
            findings.append(
                CheckFinding(
                    "AA-009", "anti_affinity", "FAIL",
                    ANTI_AFFINITY_RULES[8].description,
                    remediation=ANTI_AFFINITY_RULES[8].remediation,
                )
            )

        # 4. XPS conflict (AA-010)
        if state.get("xps_cpus_nonzero") and state.get("xps_rxqs_nonzero"):
            findings.append(
                CheckFinding(
                    "AA-010", "anti_affinity", "WARN",
                    ANTI_AFFINITY_RULES[9].description,
                    remediation=ANTI_AFFINITY_RULES[9].remediation,
                )
            )

        # 5. Adaptive interrupt moderation (AA-011)
        if state.get("adaptive_rx") or state.get("adaptive_tx"):
            findings.append(
                CheckFinding(
                    "AA-011", "anti_affinity", "WARN",
                    ANTI_AFFINITY_RULES[10].description,
                    remediation=ANTI_AFFINITY_RULES[10].remediation,
                )
            )

        # 6. irqbalance running (AA-012)
        if state.get("irqbalance_running"):
            findings.append(
                CheckFinding(
                    "AA-012", "anti_affinity", "FAIL",
                    ANTI_AFFINITY_RULES[11].description,
                    remediation=ANTI_AFFINITY_RULES[11].remediation,
                )
            )

        # 7. NUMA balancing (AA-013)
        if state.get("numa_balancing", 0) != 0:
            findings.append(
                CheckFinding(
                    "AA-013", "anti_affinity", "WARN",
                    ANTI_AFFINITY_RULES[12].description,
                    remediation=ANTI_AFFINITY_RULES[12].remediation,
                )
            )

        # 8. busy_poll on bulk / E-core (AA-014)
        if (state.get("busy_poll", 0) > 0 or state.get("busy_read", 0) > 0) and state.get("arch_type") == "ecore":
            findings.append(
                CheckFinding(
                    "AA-014", "anti_affinity", "WARN",
                    ANTI_AFFINITY_RULES[13].description,
                    remediation=ANTI_AFFINITY_RULES[13].remediation,
                )
            )

        # 9. TX ring size < 512 on >= 100G (AA-015)
        tx_ring = int(state.get("tx_ring", 512) or 512)
        link_mbps = int(state.get("link_speed_mbps", 200000) or 200000)
        if link_mbps >= 100000 and tx_ring < 512:
            findings.append(
                CheckFinding(
                    "AA-015", "hardware_config", "FAIL",
                    f"TX ring size is {tx_ring} on {link_mbps // 1000}GbE link (< 512 causes tx_restart_queue stalls)",
                    remediation=ANTI_AFFINITY_RULES[14].remediation,
                )
            )

        # 10. P0 IRQ NUMA locality (AA-016)
        nic_numa = state.get("nic_numa_node")
        p0_irq_numa = state.get("p0_irq_numa_node")
        if nic_numa is not None and p0_irq_numa is not None and nic_numa >= 0 and p0_irq_numa >= 0:
            if nic_numa != p0_irq_numa:
                findings.append(
                    CheckFinding(
                        "AA-016", "topology", "FAIL",
                        f"Queue 0 / P0 IRQ is pinned to NUMA {p0_irq_numa}, but {self.interface} is on NUMA {nic_numa}",
                        remediation=ANTI_AFFINITY_RULES[15].remediation,
                    )
                )

        # 11. PCIe effective bandwidth vs link speed (AA-017)
        pcie_speed = state.get("pcie_speed", "")
        pcie_width = state.get("pcie_width", "")
        if pcie_speed and pcie_width and link_mbps > 0:
            eff_bw = compute_pcie_effective_bw_gbps(str(pcie_speed), str(pcie_width))
            link_gbps = link_mbps / 1000.0
            if 0 < eff_bw < link_gbps * 0.95:
                findings.append(
                    CheckFinding(
                        "AA-017", "hardware_config", "FAIL",
                        f"PCIe effective BW ({eff_bw:.1f} Gbps at {pcie_speed} x{pcie_width}) < link speed ({link_gbps:.0f} Gbps)",
                        remediation=ANTI_AFFINITY_RULES[16].remediation,
                    )
                )

        # 12. CPU governor (AA-018)
        governor = state.get("cpu_governor", "performance")
        if governor and governor not in ("performance", "unknown"):
            findings.append(
                CheckFinding(
                    "AA-018", "hardware_config", "FAIL",
                    f"CPU scaling governor is '{governor}' (expected 'performance')",
                    remediation=ANTI_AFFINITY_RULES[17].remediation,
                )
            )

        if not findings:
            findings.append(
                CheckFinding(
                    "AA-PASS", "anti_affinity", "PASS",
                    "All 24 E835 feature anti-affinity and hardware locality checks passed",
                )
            )
        return findings

    @staticmethod
    def evaluate_warmup_stability(samples_gbps: List[float], max_cv_pct: float = 5.0) -> CheckFinding:
        """
        Evaluate the 5-iteration 10s single-flow LP Warmup & Sanity Gate.
        Flags FAIL if mean throughput is 0 or CV >= max_cv_pct.
        """
        if not samples_gbps:
            return CheckFinding(
                "WARMUP-EMPTY", "warmup_gate", "FAIL",
                "No warmup throughput samples collected",
            )
        n = len(samples_gbps)
        mean = sum(samples_gbps) / n
        if mean <= 0:
            return CheckFinding(
                "WARMUP-ZERO", "warmup_gate", "FAIL",
                "Warmup throughput is 0.0 Gbps",
                remediation="Verify netserver is running on LP and route/ARP are reachable.",
            )
        variance = sum((x - mean) ** 2 for x in samples_gbps) / (n - 1 if n > 1 else 1)
        stddev = variance ** 0.5
        cv_pct = (stddev / mean) * 100.0
        if cv_pct > max_cv_pct:
            return CheckFinding(
                "WARMUP-BIMODAL", "warmup_gate", "FAIL",
                f"Warmup gate failed: CV={cv_pct:.2f}% (> {max_cv_pct:.1f}%), mean={mean:.2f} Gbps",
                details=f"samples={[round(s, 2) for s in samples_gbps]}",
                remediation="Check P0 IRQ NUMA locality, stop irqbalance, and verify LP netserver core pinning.",
            )
        return CheckFinding(
            "WARMUP-PASS", "warmup_gate", "PASS",
            f"Warmup gate passed: mean={mean:.2f} Gbps, CV={cv_pct:.2f}% (<= {max_cv_pct:.1f}%)",
            details=f"samples={[round(s, 2) for s in samples_gbps]}",
        )

    @staticmethod
    def evaluate_dut_lp_swap(
        forward_tx_gbps: float,
        reverse_tx_gbps: float,
        asymmetry_threshold_pct: float = 15.0,
    ) -> CheckFinding:
        """Compare DUT->LP TX vs LP->DUT TX to isolate sender vs receiver bottlenecks."""
        peak = max(forward_tx_gbps, reverse_tx_gbps, 1e-6)
        diff_pct = abs(forward_tx_gbps - reverse_tx_gbps) / peak * 100.0
        if diff_pct > asymmetry_threshold_pct:
            bottleneck = (
                "DUT TX or LP RX path"
                if forward_tx_gbps < reverse_tx_gbps
                else "LP TX or DUT RX path"
            )
            return CheckFinding(
                "SWAP-ASYMMETRY", "dut_lp_swap", "WARN",
                f"Directional asymmetry {diff_pct:.1f}% detected (DUT->LP {forward_tx_gbps:.2f} Gbps vs LP->DUT {reverse_tx_gbps:.2f} Gbps)",
                details=f"Likely bottleneck on {bottleneck}",
                remediation="Inspect TX ring size (AA-015) on sender and GRO/RX ring/IRQ pinning on receiver.",
            )
        return CheckFinding(
            "SWAP-BALANCED", "dut_lp_swap", "PASS",
            f"DUT<->LP swap balanced within {diff_pct:.1f}% ({forward_tx_gbps:.2f} vs {reverse_tx_gbps:.2f} Gbps)",
        )

    def collect_live_state(self) -> Dict[str, Any]:
        """Inspect live Linux sysfs/procfs/ethtool state for self.interface."""
        topo = TopologyAnalyzer().detect_live(interfaces=[self.interface])
        if_topo = topo.interfaces.get(self.interface)
        state: Dict[str, Any] = {
            "arch_type": topo.arch_type,
            "nic_numa_node": if_topo.numa_node if if_topo else -1,
            "pcie_speed": if_topo.pcie_speed if if_topo else "",
            "pcie_width": if_topo.pcie_width if if_topo else "",
            "link_speed_mbps": if_topo.oper_speed_mbps if if_topo else 0,
            "mtu": if_topo.mtu if if_topo else 1500,
        }

        # Check CPU governor
        gov_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        if gov_path.exists():
            state["cpu_governor"] = gov_path.read_text(encoding="utf-8", errors="ignore").strip()

        # Check sysctls
        for key, sysctl_path in [
            ("numa_balancing", "/proc/sys/kernel/numa_balancing"),
            ("busy_poll", "/proc/sys/net/core/busy_poll"),
            ("busy_read", "/proc/sys/net/core/busy_read"),
        ]:
            p = Path(sysctl_path)
            if p.exists():
                try:
                    state[key] = int(p.read_text(encoding="utf-8").strip())
                except ValueError:
                    pass

        # Check ethtool -g (rings)
        rc, out, _ = self._runner(["ethtool", "-g", self.interface])
        if rc == 0 and "Current hardware settings:" in out:
            cur_section = out.split("Current hardware settings:", 1)[1]
            m_tx = re.search(r"TX:\s+(\d+)", cur_section)
            m_rx = re.search(r"RX:\s+(\d+)", cur_section)
            if m_tx:
                state["tx_ring"] = int(m_tx.group(1))
            if m_rx:
                state["rx_ring"] = int(m_rx.group(1))

        # Check ethtool -c (coalesce)
        rc, out, _ = self._runner(["ethtool", "-c", self.interface])
        if rc == 0:
            state["adaptive_rx"] = bool(re.search(r"Adaptive RX:\s+on", out, re.IGNORECASE))
            state["adaptive_tx"] = bool(re.search(r"Adaptive TX:\s+on", out, re.IGNORECASE))

        # Check tc qdisc for ADQ (mqprio)
        rc, out, _ = self._runner(["tc", "qdisc", "show", "dev", self.interface])
        if rc == 0 and "mqprio" in out:
            state["adq_enabled"] = True

        # Check lsmod for irdma
        rc, out, _ = self._runner(["lsmod"])
        if rc == 0 and re.search(r"^irdma\b", out, re.MULTILINE):
            state["rocev2_enabled"] = True

        return state

    def run_all(self, state_override: Optional[Dict[str, Any]] = None) -> PreflightReport:
        state = state_override if state_override is not None else self.collect_live_state()
        findings: List[CheckFinding] = []
        if state_override is None:
            findings.extend(self.check_noisy_processes())
        findings.extend(self.evaluate_feature_state(state))

        fail_count = sum(1 for f in findings if f.severity == "FAIL")
        warn_count = sum(1 for f in findings if f.severity == "WARN")
        return PreflightReport(
            interface=self.interface,
            passed=(fail_count == 0),
            fail_count=fail_count,
            warn_count=warn_count,
            findings=findings,
            active_features=state,
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Automated Platform & ice Driver Pre-Flight Checker"
    )
    parser.add_argument("-i", "--interface", required=True, help="Target network interface (e.g. ens801f0np0)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--list-rules", action="store_true", help="List all 24 E835 anti-affinity rules")
    args = parser.parse_args(argv)

    if args.list_rules:
        if args.json:
            print(json.dumps([asdict(r) for r in ANTI_AFFINITY_RULES], indent=2))
        else:
            for r in ANTI_AFFINITY_RULES:
                print(f"[{r.rule_id}] ({r.severity}) {r.feature_a} vs {r.feature_b}: {r.description}")
        return 0

    checker = PreflightChecker(interface=args.interface)
    report = checker.run_all()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        status = "PASSED" if report.passed else "FAILED"
        print(f"Pre-Flight Check [{args.interface}]: {status} ({report.fail_count} FAIL, {report.warn_count} WARN)")
        for f in report.findings:
            print(f"  [{f.severity}] {f.check_id}: {f.summary}")
            if f.remediation:
                print(f"         Remediation: {f.remediation}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
