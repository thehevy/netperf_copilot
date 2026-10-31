#!/usr/bin/env python3
"""
Unit & Integration Tests for Netperf Modernization (Steps 1-5)

Runnable via either standard library unittest (`python dev/tests/test_modernization.py`)
or pytest (`python -m pytest dev/tests/test_modernization.py`).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "dev" / "tools"
PROFILES_DIR = REPO_ROOT / "dev" / "profiles"
SRC_DIR = REPO_ROOT / "src"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from netperf_catalog import QualificationCatalog
from netperf_preflight import ANTI_AFFINITY_RULES, PreflightChecker
from netperf_report import (
    AIValidationReporter,
    compute_counter_deltas,
    parse_ethtool_stats,
    scan_kmsg_events,
)
from netperf_topology import TopologyAnalyzer
from netperf_tuner import NetperfTuner
from netserver_manager import NetserverPoolManager


def _load_script_module(module_name: str, script_path: Path) -> Any:
    loader = importlib.machinery.SourceFileLoader(module_name, str(script_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


netperf_multi = _load_script_module("netperf_multi_mod", TOOLS_DIR / "netperf-multi")
netperf_profile = _load_script_module("netperf_profile_mod", TOOLS_DIR / "netperf-profile")
netperf_orchestrate = _load_script_module("netperf_orchestrate_mod", TOOLS_DIR / "netperf-orchestrate")


CWF_288_ECORE_SNAPSHOT = """
=== CPU_MODEL ===
Intel(R) Xeon(R) 6980E+
=== NUMA ===
node0: 0-143
node1: 144-287
=== L2_CLUSTERS ===
0-3
4-7
8-11
12-15
16-19
20-23
24-27
28-31
32-35
36-39
40-43
44-47
48-51
52-55
56-59
60-63
=== NIC_INFO ===
ens801f0np0 numa=0 bdf=0000:8a:00.0 speed=32.0 GT/s PCIe width=16 link_mbps=200000 mtu=9000 driver=ice
"""

GNR_PCORE_SMT_SNAPSHOT = """
=== CPU_MODEL ===
Intel(R) Xeon(R) 6980P
=== NUMA ===
node0: 0-63,128-191
node1: 64-127,192-255
=== THREAD_SIBLINGS ===
0,128
1,129
2,130
3,131
4,132
5,133
6,134
7,135
8,136
9,137
10,138
11,139
12,140
13,141
14,142
15,143
16,144
17,145
18,146
19,147
20,148
21,149
22,150
23,151
24,152
25,153
26,154
27,155
28,156
29,157
30,158
31,159
=== NIC_INFO ===
ens7np0 numa=0 bdf=0000:17:00.0 speed=32.0 GT/s PCIe width=16 link_mbps=200000 mtu=9000 driver=ice
"""


class TestNetperfModernization(unittest.TestCase):
    """Comprehensive verification for Steps 1 through 5."""

    def test_step1_netperf_multi_omni_flag_ordering(self) -> None:
        """Verify -M, -T, -Y, -p, -l appear BEFORE '--' and -d, -J, -m appear AFTER '--'."""
        inst = netperf_multi.NetperfInstance(
            instance_id=0,
            host="192.168.10.2",
            test_type="OMNI",
            duration=30,
            output_format="json",
            direction="tx",
            cpu_affinity=4,
            remote_cpu_affinity=12,
            control_port=18600,
            tos="0xb8",
            extra_args=["-m", "65536", "-D"],
        )
        cmd = inst.build_command()
        self.assertIn("--", cmd)
        sep_idx = cmd.index("--")
        global_part = cmd[:sep_idx]
        omni_part = cmd[sep_idx + 1 :]

        self.assertIn("-M", global_part)
        self.assertEqual(global_part[global_part.index("-p") + 1], "18600")
        self.assertEqual(global_part[global_part.index("-T") + 1], "4,12")
        self.assertEqual(global_part[global_part.index("-Y") + 1], "0xb8,0xb8")

        self.assertIn("-J", omni_part)
        self.assertEqual(omni_part[omni_part.index("-d") + 1], "stream")
        self.assertEqual(omni_part[omni_part.index("-m") + 1], "65536")
        self.assertNotIn("json", omni_part)

    def test_step1_expand_hosts_and_dscp(self) -> None:
        """Verify multi-subnet IP range expansion and DSCP/ToS symbolic mapping."""
        hosts = netperf_multi.expand_host_targets("192.168.10..17.74")
        self.assertEqual(len(hosts), 8)
        self.assertEqual(hosts[0], "192.168.10.74")
        self.assertEqual(hosts[-1], "192.168.17.74")

        self.assertEqual(netperf_multi.resolve_tos_value("EF"), "0xb8")
        self.assertEqual(netperf_multi.resolve_tos_value("CS3"), "0x60")
        self.assertEqual(netperf_multi.resolve_tos_value("AF21"), "0x48")
        self.assertEqual(netperf_multi.resolve_tos_value("CS0"), "0x00")

    def test_step1_bx_disjoint_core_allocation(self) -> None:
        """Verify bidirectional BX mode allocates disjoint TX and RX cores and per-core ports."""
        runner = netperf_multi.MultiNetperf(
            host="192.168.10.2",
            instances=4,
            test_type="OMNI",
            direction="bx",
            use_affinity=True,
            per_core_netserver=True,
            base_port=18600,
            lp_start_cpu=0,
            tos="EF,CS3,AF21,CS0",
        )
        runner.create_instances()
        self.assertEqual(len(runner.instances), 8)
        tx_instances = [i for i in runner.instances if i.direction == "tx"]
        rx_instances = [i for i in runner.instances if i.direction == "rx"]
        self.assertEqual(len(tx_instances), 4)
        self.assertEqual(len(rx_instances), 4)

        tx_cores = {i.cpu_affinity for i in tx_instances}
        rx_cores = {i.cpu_affinity for i in rx_instances}
        self.assertTrue(tx_cores.isdisjoint(rx_cores))

        ports = [i.control_port for i in runner.instances]
        self.assertEqual(len(set(ports)), 8)

    def test_step1_profile_command_generation_and_validation(self) -> None:
        """Verify netperf-profile builds valid OMNI commands and validates all YAML profiles."""
        profiles = netperf_profile.ProfileLoader.list_builtin_profiles()
        profile_names = {name for name, _ in profiles}
        expected_new = {
            "e835-200g-gnr-pcore",
            "e835-200g-cwf-ecore",
            "e835-3x200g-multiport",
            "e835-mtu1500-smallpkt",
            "ocp-8x25g-lag-qos",
        }
        self.assertTrue(expected_new.issubset(profile_names))

        for name, path in profiles:
            loaded = netperf_profile.ProfileLoader.load_file(path)
            valid, errors = netperf_profile.ProfileValidator.validate(loaded)
            self.assertTrue(valid, f"Profile {name} failed validation: {errors}")

        cwf_path = netperf_profile.ProfileLoader.find_builtin_profile("e835-200g-cwf-ecore")
        self.assertIsNotNone(cwf_path)
        cwf_profile = netperf_profile.ProfileLoader.load_file(cwf_path)
        runner = netperf_profile.ProfileRunner(cwf_profile, host="192.168.10.2", dry_run=True)
        cmd = runner._build_netperf_command(cwf_profile["tests"][0], duration=30, output_format="json")
        sep = cmd.index("--")
        self.assertIn("-M", cmd[:sep])
        self.assertIn("-J", cmd[sep + 1 :])

    def test_step1_orchestrate_command_normalization(self) -> None:
        """Verify netperf-orchestrate normalizes OMNI global vs test-specific flags."""
        cmd_tokens = netperf_orchestrate.RemoteOrchestrator.build_remote_netperf_command(
            netperf_path="/usr/local/bin/netperf",
            server_address="192.168.10.2",
            test_args=["-l", "30", "-p", "18600", "-d", "stream", "-m", "65536", "-J"],
        )
        self.assertIn("--", cmd_tokens)
        sep = cmd_tokens.index("--")
        self.assertIn("-M", cmd_tokens[:sep])
        self.assertIn("-p", cmd_tokens[:sep])
        self.assertIn("-J", cmd_tokens[sep + 1 :])
        self.assertIn("-m", cmd_tokens[sep + 1 :])

    def test_step2_c_engine_modernization_invariants(self) -> None:
        """Verify C source files contain the Step 2 high-speed & high-core-count upgrades."""
        netlib_h = (SRC_DIR / "netlib.h").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("#define         MAXMESSAGESIZE  4194304", netlib_h)
        self.assertIn("float active_cpu_util;", netlib_h)
        self.assertIn("int   active_cpu_count;", netlib_h)

        procstat_c = (SRC_DIR / "netcpu_procstat.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("#define CPU_LINE_LENGTH 256", procstat_c)
        self.assertIn("lib_local_cpu_stats.active_cpu_util", procstat_c)
        self.assertIn("lib_local_cpu_stats.peak_cpu_id", procstat_c)

        netslot_c = (SRC_DIR / "netslot_linux.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("find_interface_pcie_info", netslot_c)
        self.assertIn("current_link_speed", netslot_c)

        netsys_c = (SRC_DIR / "netsys_linux.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("/sys/class/dmi/id/product_name", netsys_c)
        self.assertIn("scaling_cur_freq", netsys_c)

        ethtool_c = (SRC_DIR / "netdrv_ethtool.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("find_driver_ext_info", ethtool_c)
        self.assertIn("ETHTOOL_GLINKSETTINGS", ethtool_c)

        omni_c = (SRC_DIR / "nettest_omni.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("use_zerocopy", omni_c)
        self.assertIn("MSG_ZEROCOPY", omni_c)
        self.assertIn("local_active_cpu_util", omni_c)

    def test_step3_topology_cwf_ecore_snapshot(self) -> None:
        """Verify Clearwater Forest 6980E+ snapshot detects ecore, 4-core L2 modules, and spread_l2."""
        topo = TopologyAnalyzer.from_topology_snapshot(CWF_288_ECORE_SNAPSHOT)
        self.assertEqual(topo.arch_type, "ecore")
        self.assertFalse(topo.smt_enabled)
        self.assertAlmostEqual(
            topo.interfaces["ens801f0np0"].pcie_effective_bw_gbps, 504.12, delta=0.5
        )

        cores = TopologyAnalyzer.allocate_flow_cores(
            topo, interface="ens801f0np0", num_flows=8, layout="spread_l2"
        )
        self.assertEqual(len(cores), 8)
        irq_set = set(topo.core_pools[0].irq_cores)
        self.assertTrue(set(cores).isdisjoint(irq_set))

    def test_step3_topology_gnr_pcore_smt_snapshot(self) -> None:
        """Verify Granite Rapids 6980P snapshot filters SMT siblings and selects physical P-cores."""
        topo = TopologyAnalyzer.from_topology_snapshot(GNR_PCORE_SMT_SNAPSHOT)
        self.assertEqual(topo.arch_type, "pcore")
        self.assertTrue(topo.smt_enabled)
        self.assertTrue(all(c < 128 for c in topo.physical_cores_per_node[0]))

        tx_cores, rx_cores = TopologyAnalyzer.allocate_bx_cores(
            topo, interface="ens7np0", num_tx=4, num_rx=4
        )
        self.assertEqual(len(tx_cores), 4)
        self.assertEqual(len(rx_cores), 4)
        self.assertTrue(set(tx_cores).isdisjoint(set(rx_cores)))

    def test_step3_netserver_pool_manager_per_core_plan(self) -> None:
        """Verify NetserverPoolManager plans 16 per-core netserver daemons on non-IRQ cores."""
        topo = TopologyAnalyzer.from_topology_snapshot(CWF_288_ECORE_SNAPSHOT)
        mgr = NetserverPoolManager(topology=topo, base_port=18600)
        plan = mgr.plan_pool(topo=topo, count=16, min_core=24)
        self.assertEqual(len(plan.instances), 16)
        first_inst = plan.instances[0]
        self.assertEqual(first_inst.port, 18600 + first_inst.core)
        self.assertIn(f"numactl --physcpubind={first_inst.core}", first_inst.command)
        self.assertIn(f"-p {first_inst.port}", first_inst.command)

    def test_step4_preflight_24_anti_affinity_rules_and_gates(self) -> None:
        """Verify all 24 anti-affinity rules, noisy process check, warmup gate, and swap check."""
        self.assertEqual(len(ANTI_AFFINITY_RULES), 24)
        checker = PreflightChecker(interface="ens801f0np0")

        ps_text = """
        1042 code-server /usr/lib/code-server --bind-addr 0.0.0.0:8080
        1199 irqbalance /usr/sbin/irqbalance --foreground
        """
        proc_findings = checker.check_noisy_processes(ps_output=ps_text)
        ids = {f.check_id for f in proc_findings}
        self.assertIn("PROC-VSCODE", ids)
        self.assertIn("PROC-IRQBALANCE", ids)

        bad_state = {
            "adq_enabled": True,
            "rocev2_enabled": True,
            "tx_ring": 256,
            "link_speed_mbps": 200000,
            "nic_numa_node": 0,
            "p0_irq_numa_node": 1,
            "pcie_speed": "16.0 GT/s",
            "pcie_width": "8",
            "cpu_governor": "powersave",
        }
        report = checker.run_all(state_override=bad_state)
        self.assertFalse(report.passed)
        finding_ids = {f.check_id for f in report.findings}
        self.assertTrue({"AA-001", "AA-006", "AA-015", "AA-016", "AA-017", "AA-018"}.issubset(finding_ids))

        stable_gate = PreflightChecker.evaluate_warmup_stability([189.1, 189.4, 188.9, 189.2, 189.0])
        self.assertEqual(stable_gate.severity, "PASS")
        bimodal_gate = PreflightChecker.evaluate_warmup_stability([189.0, 95.0, 188.5, 92.0, 189.2])
        self.assertEqual(bimodal_gate.severity, "FAIL")

        swap_warn = PreflightChecker.evaluate_dut_lp_swap(135.0, 190.0)
        self.assertEqual(swap_warn.severity, "WARN")

    def test_step4_tuner_bkm_profiles_and_ab_sweep(self) -> None:
        """Verify NetperfTuner selects TX=512 on CWF E-core vs TX=2048 on GNR P-core and runs A/B sweeps."""
        cwf_topo = TopologyAnalyzer.from_topology_snapshot(CWF_288_ECORE_SNAPSHOT)
        cwf_tuner = NetperfTuner(interface="ens801f0np0", topology=cwf_topo)
        cwf_plan = cwf_tuner.build_tuning_plan("auto")
        self.assertEqual(cwf_plan.profile, "cwf-ecore")
        self.assertEqual(cwf_plan.parameters["tx_ring"], 512)
        self.assertEqual(cwf_plan.parameters["rx_ring"], 4096)
        self.assertEqual(cwf_plan.parameters["tx_scheduling_layers"], 5)

        gnr_topo = TopologyAnalyzer.from_topology_snapshot(GNR_PCORE_SMT_SNAPSHOT)
        gnr_tuner = NetperfTuner(interface="ens7np0", topology=gnr_topo)
        gnr_plan = gnr_tuner.build_tuning_plan("auto")
        self.assertEqual(gnr_plan.profile, "gnr-pcore")
        self.assertEqual(gnr_plan.parameters["tx_ring"], 2048)

        applied_cmds = []
        sim_scores = {
            256: [142.0, 140.5, 141.2],
            512: [189.2, 189.5, 189.1],
            2048: [186.0, 185.8, 186.2],
        }
        sweep_res = cwf_tuner.run_ab_sweep(
            knob="tx_ring",
            values=[256, 512, 2048],
            benchmark_fn=lambda v: sim_scores[v],
            apply_fn=lambda cmd: applied_cmds.append(cmd) or 0,
        )
        self.assertEqual(sweep_res["winner_value"], 512)
        self.assertEqual(applied_cmds[-1], ["ethtool", "-G", "ens801f0np0", "tx", "512"])

    def test_step5_qualification_catalog_suites(self) -> None:
        """Verify all 4 QualificationCatalog suites generate valid test cases."""
        topo = TopologyAnalyzer.from_topology_snapshot(CWF_288_ECORE_SNAPSHOT)
        cat = QualificationCatalog(host="192.168.10.2", interface="ens801f0np0", topology=topo)

        flow_cases = cat.build_suite("flow-scaling")
        self.assertEqual(len(flow_cases), 42)

        loc_cases = cat.build_suite("core-locality")
        self.assertEqual(len(loc_cases), 4)
        self.assertEqual(
            [c.test_case_id for c in loc_cases],
            ["LOC-SAME-CORE", "LOC-SAME-L2", "LOC-LOCAL-NUMA", "LOC-CROSS-NUMA"],
        )

        matrix_cases = cat.build_suite("ring-coalesce-matrix")
        self.assertEqual(len(matrix_cases), 20)

        lag_cases = cat.build_suite("lag-failover-qos")
        self.assertEqual(len(lag_cases), 2)

    def test_step5_ai_validation_reporter_and_kmsg_scanner(self) -> None:
        """Verify U1-U13 kmsg scanning, ethtool -S deltas, result.json schema, and dashboard.md."""
        kmsg = """
        [ 1012.114] ice 0000:8a:00.0: Malicious Driver Detection event 1 on TX queue 4
        [ 1013.002] NETDEV WATCHDOG: ens801f0np0 (ice): transmit queue 4 timed out
        """
        events = scan_kmsg_events(kmsg)
        codes = {e.code for e in events}
        self.assertIn("U3", codes)
        self.assertIn("U4", codes)

        before = parse_ethtool_stats("tx_restart_queue: 10\nrx_dropped: 0\nrx_crc_errors: 0\n")
        after = parse_ethtool_stats("tx_restart_queue: 35\nrx_dropped: 2\nrx_crc_errors: 0\n")
        deltas = compute_counter_deltas(before, after)
        self.assertEqual(deltas["tx_restart_queue"], 25)
        self.assertEqual(deltas["rx_dropped"], 2)

        res = AIValidationReporter.build_result_json(
            test_case_id="FLOW-TX-16S-MTU9000",
            suite_name="flow-scaling",
            metrics={"throughput_gbps": 189.4, "cv_pct": 0.42},
            environment={
                "cpu_model": "Intel(R) Xeon(R) 6980E+",
                "arch_type": "ecore",
                "interface": "ens801f0np0",
            },
            kmsg_text="",
            counter_deltas=deltas,
            target_gbps=190.0,
        )
        self.assertEqual(res["verdict"], "PASS")
        self.assertTrue(res["unexpected_event_scan"]["passed"])

        md = AIValidationReporter.render_dashboard_markdown(
            "flow-scaling",
            [
                {
                    "test_case_id": "FLOW-TX-16S-MTU9000",
                    "direction": "tx",
                    "streams": 16,
                    "mtu": 9000,
                    "throughput_gbps": 189.4,
                    "cv_pct": 0.42,
                    "verdict": "PASS",
                }
            ],
        )
        self.assertIn("FLOW-TX-16S-MTU9000", md)
        self.assertIn("189.40 Gbps", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
