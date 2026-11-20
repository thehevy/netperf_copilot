#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: dev/tests/test_modernization.py
# Created Date: 2026-11-05
# Last Updated Date: 2026-11-16
# Version: 2.1.0
# Status: Validated
# Target Scope: Unit and integration test suite for Netperf Modernization Steps 1-8.
# Summary: Validates topology discovery, preflight rules, C OMNI selectors, Intel PCM bridge, Flent bridge, and two-tier benchmark study harness.
# === METADATA_HEADER_END ===
"""
Unit & Integration Tests for Netperf Modernization (Steps 1-8)

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
netperf_template = _load_script_module("netperf_template_mod", TOOLS_DIR / "netperf-template")
netperf_aggregate = _load_script_module("netperf_aggregate_mod", TOOLS_DIR / "netperf-aggregate")
netperf_monitor = _load_script_module("netperf_monitor_mod", TOOLS_DIR / "netperf-monitor")


ECORE_288_SNAPSHOT = """
=== CPU_MODEL ===
Multi-Core E-Core Processor (288C)
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

PCORE_SMT_SNAPSHOT = """
=== CPU_MODEL ===
Multi-Core P-Core Processor (128C/256T)
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
            "200g-pcore",
            "200g-ecore",
            "3x200g-multiport",
            "200g-mtu1500-smallpkt",
            "ocp-8x25g-lag-qos",
        }
        self.assertTrue(expected_new.issubset(profile_names))

        for name, path in profiles:
            loaded = netperf_profile.ProfileLoader.load_file(path)
            valid, errors = netperf_profile.ProfileValidator.validate(loaded)
            self.assertTrue(valid, f"Profile {name} failed validation: {errors}")

        ecore_path = netperf_profile.ProfileLoader.find_builtin_profile("200g-ecore")
        self.assertIsNotNone(ecore_path)
        ecore_profile = netperf_profile.ProfileLoader.load_file(ecore_path)
        runner = netperf_profile.ProfileRunner(ecore_profile, host="192.168.10.2", dry_run=True)
        cmd = runner._build_netperf_command(ecore_profile["tests"][0], duration=30, output_format="json")
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

    def test_step3_topology_ecore_snapshot(self) -> None:
        """Verify Shared-L2 E-Core E-Core-288C snapshot detects ecore, 4-core L2 modules, and spread_l2."""
        topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
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

    def test_step3_topology_pcore_smt_snapshot(self) -> None:
        """Verify Multi-Core P-Core P-Core-128C snapshot filters SMT siblings and selects physical P-cores."""
        topo = TopologyAnalyzer.from_topology_snapshot(PCORE_SMT_SNAPSHOT)
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
        topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
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
        """Verify NetperfTuner selects TX=512 on E-core vs TX=2048 on P-core and runs A/B sweeps."""
        ecore_topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        ecore_tuner = NetperfTuner(interface="ens801f0np0", topology=ecore_topo)
        ecore_plan = ecore_tuner.build_tuning_plan("auto")
        self.assertEqual(ecore_plan.profile, "ecore")
        self.assertEqual(ecore_plan.parameters["tx_ring"], 512)
        self.assertEqual(ecore_plan.parameters["rx_ring"], 4096)
        self.assertEqual(ecore_plan.parameters["tx_scheduling_layers"], 5)

        pcore_topo = TopologyAnalyzer.from_topology_snapshot(PCORE_SMT_SNAPSHOT)
        pcore_tuner = NetperfTuner(interface="ens7np0", topology=pcore_topo)
        pcore_plan = pcore_tuner.build_tuning_plan("auto")
        self.assertEqual(pcore_plan.profile, "pcore")
        self.assertEqual(pcore_plan.parameters["tx_ring"], 2048)

        applied_cmds = []
        sim_scores = {
            256: [142.0, 140.5, 141.2],
            512: [189.2, 189.5, 189.1],
            2048: [186.0, 185.8, 186.2],
        }
        sweep_res = ecore_tuner.run_ab_sweep(
            knob="tx_ring",
            values=[256, 512, 2048],
            benchmark_fn=lambda v: sim_scores[v],
            apply_fn=lambda cmd: applied_cmds.append(cmd) or 0,
        )
        self.assertEqual(sweep_res["winner_value"], 512)
        self.assertEqual(applied_cmds[-1], ["ethtool", "-G", "ens801f0np0", "tx", "512"])

    def test_step5_qualification_catalog_suites(self) -> None:
        """Verify all 4 QualificationCatalog suites generate valid test cases."""
        topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
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
                "cpu_model": "Multi-Core E-Core Processor (288C)",
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

    def test_step6_c_engine_security_and_preset_fixes(self) -> None:
        """Verify Phase 1 C engine fixes: link_width[32], json_escape_string, preset dirs, drain_zerocopy_completions."""
        netslot_c = (SRC_DIR / "netslot_linux.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("static char interface_address[32];", netslot_c)
        self.assertIn("char link_width[32];", netslot_c)

        netsys_c = (SRC_DIR / "netsys_linux.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("if (target != NULL) {\n\t    fclose(proccpu);", netsys_c)

        omni_c = (SRC_DIR / "nettest_omni.c").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("json_escape_string", omni_c)
        self.assertIn("drain_zerocopy_completions", omni_c)
        self.assertIn("MSG_ERRQUEUE | MSG_DONTWAIT", omni_c)
        self.assertIn("./dev/catalog/output-presets", omni_c)
        self.assertIn("-Z                Enable SO_ZEROCOPY / MSG_ZEROCOPY", omni_c)

    def test_step6_preflight_rules_aa019_through_aa024(self) -> None:
        """Verify AA-019 through AA-024 are evaluated by PreflightChecker.evaluate_feature_state."""
        checker = PreflightChecker(interface="ens801f0np0")
        state = {
            "arch_type": "ecore",
            "link_speed_mbps": 200000,
            "tx_ring": 512,
            "gro_off": True,
            "tso_off": True,
            "ecore_smt_assumption": True,
            "shared_netserver_lock": True,
            "rmem_max": 212992,
            "tx_scheduling_layers": 9,
        }
        findings = checker.evaluate_feature_state(state)
        ids = {f.check_id for f in findings}
        for rule_id in ("AA-019", "AA-020", "AA-021", "AA-022", "AA-023", "AA-024"):
            self.assertIn(rule_id, ids, f"Expected {rule_id} in findings")

    def test_step6_multi_json_flattening_and_multi_nic_distribution(self) -> None:
        """Verify NetperfInstance._parse_json flattens 'results' and MultiNetperf distributes flows across NICs."""
        inst = netperf_multi.NetperfInstance(instance_id=0, host="192.168.10.2")
        sample_json = """
        {
          "metadata": {
            "local_active_cpu_util": 41.5,
            "local_softirq_pct": 12.3
          },
          "results": {
            "THROUGHPUT": 24500.0,
            "MEAN_LATENCY": 18.2
          }
        }
        """
        parsed = inst._parse_json(sample_json)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["THROUGHPUT"], 24500.0)
        self.assertEqual(parsed["MEAN_LATENCY"], 18.2)
        self.assertEqual(parsed["local_active_cpu_util"], 41.5)

        # Multi-NIC with 1 host and 3 interfaces and instances=48 -> 16 per NIC = 48 total streams
        runner = netperf_multi.MultiNetperf(
            host="192.168.10.2",
            instances=48,
            interfaces="ens7np0,ens23np0,ens27np0",
            direction="tx",
        )
        runner.create_instances()
        self.assertEqual(len(runner.instances), 48)
        ifaces = [i.interface for i in runner.instances]
        self.assertEqual(ifaces.count("ens7np0"), 16)
        self.assertEqual(ifaces.count("ens23np0"), 16)
        self.assertEqual(ifaces.count("ens27np0"), 16)

    def test_step6_template_and_aggregate_fixes(self) -> None:
        """Verify SimpleTemplateEngine loop rendering and ResultComparator lower-is-better latency direction."""
        simple = netperf_template.SimpleTemplateEngine()
        rendered = simple.render(
            "{% for item in results %}{{ item.test_name }}={{ item.throughput }};{% endfor %}",
            {"results": [{"test_name": "t1", "throughput": 100}, {"test_name": "t2", "throughput": 200}]},
        )
        self.assertEqual(rendered, "t1=100;t2=200;")

        base_res = [netperf_aggregate.NetperfResult({"THROUGHPUT": 10000.0, "MEAN_LATENCY": 50.0})]
        curr_res = [netperf_aggregate.NetperfResult({"THROUGHPUT": 12000.0, "MEAN_LATENCY": 25.0})]
        comp = netperf_aggregate.ResultComparator.compare(base_res, curr_res)
        self.assertTrue(comp["differences"]["throughput"]["is_improvement"])
        self.assertFalse(comp["differences"]["throughput"]["is_regression"])
        # Latency decreased by 50% -> improvement, not regression
        self.assertTrue(comp["differences"]["latency"]["is_improvement"])
        self.assertFalse(comp["differences"]["latency"]["is_regression"])

    def test_step6_catalog_output_dir_and_orchestrate_yaml(self) -> None:
        """Verify netperf_catalog --output-dir --dry-run writes result.json, summary.csv, and dashboard.md."""
        import tempfile
        import shutil
        from netperf_catalog import main as catalog_main

        tmp_dir = Path(tempfile.mkdtemp(prefix="netperf_cat_test_"))
        try:
            rc = catalog_main([
                "--suite", "core-locality",
                "--host", "192.168.10.2",
                "--interface", "ens801f0np0",
                "--output-dir", str(tmp_dir),
                "--dry-run",
            ])
            self.assertEqual(rc, 0)
            self.assertTrue((tmp_dir / "result.json").exists())
            self.assertTrue((tmp_dir / "summary.csv").exists())
            self.assertTrue((tmp_dir / "dashboard.md").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        hosts_yaml = REPO_ROOT / "dev" / "examples" / "hosts.yaml"
        inv = netperf_orchestrate.HostInventory.from_yaml(hosts_yaml)
        self.assertEqual(len(inv.hosts), 5)

    def test_step7_post_update_audit_fixes(self) -> None:
        """Verify all C linkage, OMNI active CPU selectors, BKM alignment, and CLI flag fixes."""
        makefile_am = (SRC_DIR / "Makefile.am").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("netdrv_ethtool.c netslot_linux.c netsys_linux.c", makefile_am)
        self.assertIn("netserver_LDADD = missing/libcompat.a", makefile_am)
        self.assertNotIn("libcompat.ap", makefile_am)

        bsd_h = (SRC_DIR / "nettest_bsd.h").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("active_cpu_util;", bsd_h)
        self.assertIn("active_cpu_count;", bsd_h)
        self.assertIn("#define OMNI_RESULTS_CONV_CUTOFF 29", bsd_h)

        omni_c = (SRC_DIR / "nettest_omni.c").read_text(encoding="utf-8", errors="ignore")
        for sel in ("LOCAL_CPU_ACTIVE_UTIL", "LOCAL_CPU_ACTIVE_COUNT", "REMOTE_CPU_ACTIVE_UTIL", "REMOTE_CPU_ACTIVE_COUNT"):
            self.assertIn(sel, omni_c)

        cpu_out = (REPO_ROOT / "dev" / "catalog" / "output-presets" / "cpu.out").read_text(encoding="utf-8")
        self.assertIn("LOCAL_CPU_ACTIVE_UTIL", cpu_out)
        self.assertIn("REMOTE_CPU_ACTIVE_UTIL", cpu_out)

        # Verify TopologyAnalyzer BKM & layout alignment
        ecore_topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        pcore_topo = TopologyAnalyzer.from_topology_snapshot(PCORE_SMT_SNAPSHOT)
        self.assertEqual(TopologyAnalyzer.select_layout_strategy(ecore_topo, "auto", num_flows=8, mtu=9000), "spread_l2")
        self.assertEqual(TopologyAnalyzer.select_layout_strategy(pcore_topo, "auto", num_flows=8, mtu=9000), "spread_step2")
        self.assertEqual(TopologyAnalyzer.get_bkm_parameters(ecore_topo)["tx_ring"], 512)
        self.assertEqual(TopologyAnalyzer.get_bkm_parameters(pcore_topo)["tx_ring"], 2048)

        # Verify QualificationCatalog per-core ports and ring-coalesce pre_commands
        cat = QualificationCatalog(host="192.168.10.2", interface="ens801f0np0", topology=ecore_topo, base_port=18600)
        loc_cases = cat.build_suite("core-locality")
        for lc in loc_cases:
            core = lc.parameters["local_cpu"]
            p_idx = lc.command.index("-p")
            self.assertEqual(lc.command[p_idx + 1], str(18600 + core))

        matrix_cases = cat.build_suite("ring-coalesce-matrix")
        self.assertEqual(len(matrix_cases[0].pre_commands), 2)
        self.assertEqual(matrix_cases[0].pre_commands[0][:3], ["ethtool", "-G", "ens801f0np0"])

        # Verify NetserverPoolManager custom binary path and CLI --action / -n flags
        from netserver_manager import main as ns_main
        mgr = NetserverPoolManager(topology=ecore_topo, base_port=18600, netserver_path="/opt/netperf/netserver")
        spec = mgr.plan_pool(topo=ecore_topo, count=4)
        self.assertIn("/opt/netperf/netserver -p", spec.instances[0].command)
        rc = ns_main(["--action", "plan", "-n", "4", "--netserver", "/opt/netperf/netserver"])
        self.assertEqual(rc, 0)
        self.assertIn('strncasecmp(tmpval, "0x", 2) == 0', omni_c)
        self.assertIn("print_headers && (netperf_output_mode != JSON)", omni_c)

    def test_step8_omni_p999_and_runtime_cpu_exec(self) -> None:
        """Verify P999_LATENCY, LOCAL_CPU_EXEC, REMOTE_CPU_EXEC, and LOCAL_CPU_MIGRATIONS in C engine and presets."""
        omni_c = (SRC_DIR / "nettest_omni.c").read_text(encoding="utf-8", errors="ignore")
        for selector in ("P999_LATENCY", "LOCAL_CPU_EXEC", "REMOTE_CPU_EXEC", "LOCAL_CPU_MIGRATIONS"):
            self.assertIn(selector, omni_c)
        self.assertIn("HIST_get_percentile(time_hist, 0.999)", omni_c)
        self.assertIn("get_current_runtime_cpu", omni_c)

        latency_out = (REPO_ROOT / "dev" / "catalog" / "output-presets" / "latency.out").read_text(encoding="utf-8")
        cpu_out = (REPO_ROOT / "dev" / "catalog" / "output-presets" / "cpu.out").read_text(encoding="utf-8")
        verbose_out = (REPO_ROOT / "dev" / "catalog" / "output-presets" / "verbose.out").read_text(encoding="utf-8")
        self.assertIn("P999_LATENCY", latency_out)
        self.assertIn("LOCAL_CPU_EXEC", cpu_out)
        self.assertIn("LOCAL_CPU_MIGRATIONS", cpu_out)
        self.assertIn("REMOTE_CPU_EXEC", cpu_out)
        self.assertIn("P999_LATENCY", verbose_out)
        self.assertIn("LOCAL_CPU_EXEC", verbose_out)

    def test_step8_barrier_sync_and_core_collision_matrix(self) -> None:
        """Verify barrier wait (-w), Jain's Fairness Index, core/SMT/IRQ collision detection, and outlier flags."""
        inst = netperf_multi.NetperfInstance(
            instance_id=0,
            host="192.168.10.2",
            test_type="OMNI",
            duration=10,
            output_format="json",
            cpu_affinity=16,
            remote_cpu_affinity=16,
            barrier_wait_secs=2,
        )
        cmd = inst.build_command()
        sep = cmd.index("--")
        self.assertIn("-w", cmd[:sep])
        self.assertEqual(cmd[cmd.index("-w") + 1], "2")

        runner = netperf_multi.MultiNetperf(
            host="192.168.10.2",
            instances=4,
            test_type="OMNI",
            use_affinity=True,
            barrier_wait=2,
        )
        runner.dut_topo = TopologyAnalyzer.from_topology_snapshot(PCORE_SMT_SNAPSHOT)
        synthetic_results = [
            {"THROUGHPUT": 7420.0, "_local_cpu": 4, "LOCAL_CPU_EXEC": 4, "LOCAL_SD": 0.16, "P50_LATENCY": 15, "P99_LATENCY": 31, "P999_LATENCY": 45},
            {"THROUGHPUT": 3810.0, "_local_cpu": 4, "LOCAL_CPU_EXEC": 4, "LOCAL_SD": 0.31, "P50_LATENCY": 28, "P99_LATENCY": 74, "P999_LATENCY": 112},
            {"THROUGHPUT": 7100.0, "_local_cpu": 6, "LOCAL_CPU_EXEC": 6, "LOCAL_SD": 0.16, "P50_LATENCY": 14, "P99_LATENCY": 30, "P999_LATENCY": 44},
            {"THROUGHPUT": 7050.0, "_local_cpu": 134, "LOCAL_CPU_EXEC": 134, "LOCAL_SD": 0.17, "P50_LATENCY": 16, "P99_LATENCY": 33, "P999_LATENCY": 49},
        ]
        audit = runner.audit_core_residency_and_fairness(synthetic_results)
        self.assertLess(audit["jains_fairness_index"], 0.96)
        self.assertEqual(audit["core_overlap_count"], 4)
        self.assertEqual(audit["core_overlap_pct"], 100.0)
        self.assertIn("F01", audit["outlier_flow_ids"])
        matrix = audit["per_flow_core_matrix"]
        self.assertEqual(matrix[0]["collision_type"], "SAME_LOGICAL_CORE")
        self.assertEqual(matrix[1]["collision_type"], "SAME_LOGICAL_CORE")
        self.assertEqual(matrix[2]["collision_type"], "SMT_SIBLING")
        self.assertEqual(matrix[3]["collision_type"], "SMT_SIBLING")
        self.assertTrue(matrix[1]["is_outlier"])

    def test_step8_intel_pcm_collector_and_cpu_error_math(self) -> None:
        """Verify IntelPCMCollector DDIO/UPI/DRAM/Watts CSV parsing and ProcStatGroundTruth CPU error math."""
        import tempfile
        from netperf_pcm_bridge import IntelPCMCollector, ProcStatGroundTruth, run_self_test as pcm_self_test
        from netperf_flent_bridge import run_self_test as flent_self_test

        self.assertEqual(pcm_self_test(), 0)
        self.assertEqual(flent_self_test(), 0)

        with tempfile.TemporaryDirectory(prefix="test_pcm_") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "pcm.csv").write_text(
                "IPC,L2HIT,L3HIT,UPI_GBPS\n0.90,0.88,0.93,0.19\n",
                encoding="utf-8",
            )
            (tmp_path / "pcm_pcie.csv").write_text(
                "PCIRdCur_hit,PCIRdCur_total,ItoMCacheNear_hit,ItoMCacheNear_total\n"
                "99790,100000,199580,200000\n",
                encoding="utf-8",
            )
            (tmp_path / "pcm_memory.csv").write_text(
                "Local_DRAM_GB/s,Remote_DRAM_GB/s\n0.83,0.02\n",
                encoding="utf-8",
            )
            (tmp_path / "pcm_power.csv").write_text(
                "Package_Watts\n250.0\n",
                encoding="utf-8",
            )
            collector = IntelPCMCollector(csv_dir=str(tmp_path))
            res = collector.stop_and_collect(throughput_gbps=94.15)
            self.assertTrue(res["available"])
            self.assertAlmostEqual(res["ddio_hit_pct"], 99.79, places=2)
            self.assertAlmostEqual(res["upi_traffic_gbps"], 0.19, places=2)
            self.assertAlmostEqual(res["total_dram_gbps"], 0.85, places=2)
            self.assertAlmostEqual(res["gbps_per_watt"], round(94.15 / 250.0, 4), places=4)

        err = ProcStatGroundTruth.compute_cpu_reporting_error(tool_reported_cpu_pct=14.2, ground_truth_cpu_pct=52.0)
        self.assertAlmostEqual(err["relative_error_pct"], 72.69, places=1)

    def test_step8_fair_benchmark_study_harness(self) -> None:
        """Verify BenchmarkStudyHarness version detection (<3.16 vs >=3.16) and Tier A / Tier B command generation."""
        from netperf_benchmark_study import BenchmarkStudyHarness

        v_old = BenchmarkStudyHarness.parse_iperf3_version("iperf 3.13 (cJSON 1.7.15)")
        v_new = BenchmarkStudyHarness.parse_iperf3_version("iperf 3.16 (cJSON 1.7.15)")
        self.assertFalse(v_old["is_multithreaded_p"])
        self.assertTrue(v_new["is_multithreaded_p"])

        ecore_topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        harness = BenchmarkStudyHarness(
            host="192.168.10.2",
            interface="ens801f0np0",
            flow_counts=(1, 4, 16),
            duration=30,
            trials=5,
            topology=ecore_topo,
        )
        plan = harness.generate_study_plan(iperf3_version_override="iperf 3.17.1")
        self.assertTrue(plan["environment"]["tool_versions"]["iperf3"]["is_multithreaded_p"])
        self.assertIn("16", plan["flow_matrix"])
        f16 = plan["flow_matrix"]["16"]
        self.assertEqual(len(f16["trial_schedule"]), 5)
        tier_a = f16["tiers"]["tier_a_default_unpinned"]
        tier_b1 = f16["tiers"]["tier_b1_shared_taskset_pool"]
        tier_b = f16["tiers"]["tier_b_tuned_pinned"]
        self.assertIn("iperf3_default", tier_a)
        self.assertIn("netperf_copilot_taskset_pool", tier_b1)
        self.assertIn("classic_netperf_taskset_pool", tier_b1)
        self.assertIn("iperf2_taskset_pool", tier_b1)
        self.assertIn("iperf3_mt_taskset_pool", tier_b1)
        self.assertIn("taskset", tier_b1["netperf_copilot_taskset_pool"]["command"])
        self.assertNotIn("--affinity", tier_b1["netperf_copilot_taskset_pool"]["command"])
        self.assertIn("netperf_copilot_pinned", tier_b)
        self.assertIn("classic_netperf_pinned", tier_b)
        self.assertIn("iperf2_pinned", tier_b)
        self.assertIn("iperf3_mt_pinned", tier_b)
        self.assertIn("iperf3_multiprocess_pinned", tier_b)
        self.assertEqual(len(tier_b["iperf3_multiprocess_pinned"]["command"]), 16)

        claims = BenchmarkStudyHarness.evaluate_comparative_claims()
        for key in (
            "100gbe_mtu1500_16f_64f_gbps",
            "100gbe_mtu9000_16f_64f_gbps",
            "200gbe_mtu1500_16f_64f_gbps",
            "200gbe_mtu9000_16f_64f_gbps",
        ):
            self.assertIn(key, claims)

        from netperf_benchmark_study import run_self_test as study_self_test
        self.assertEqual(study_self_test(), 0)

    def test_step9_omit_pooled_tail_latency_and_iperf3_gate(self) -> None:
        """Verify --omit steady-state filtering, pooled p99/p99.9 tail latency, and iperf3 >= 3.16 version gate."""
        from netperf_benchmark_study import BenchmarkStudyHarness

        inst = netperf_multi.NetperfInstance(
            instance_id=0,
            host="192.168.10.2",
            test_type="OMNI",
            duration=10,
            output_format="json",
            omit_secs=2,
            data_port=20000,
        )
        cmd = inst.build_command()
        sep = cmd.index("--")
        self.assertIn("-D", cmd[:sep])
        self.assertIn("-P", cmd[sep + 1 :])
        self.assertEqual(cmd[cmd.index("-P") + 1], "20000,20000")

        runner = netperf_multi.MultiNetperf(
            host="192.168.10.2",
            instances=2,
            test_type="OMNI",
            omit_secs=2,
        )
        runner.create_instances()
        runner.instances[0].returncode = 0
        runner.instances[0].result = {
            "THROUGHPUT": 5800.0,
            "_steady_state_throughput": 5920.0,
            "TRANSACTION_RATE": 20000.0,
            "P50_LATENCY": 15.0,
            "P90_LATENCY": 22.0,
            "P99_LATENCY": 30.0,
            "P999_LATENCY": 44.0,
            "_direction_role": "tx",
        }
        runner.instances[1].returncode = 0
        runner.instances[1].result = {
            "THROUGHPUT": 5600.0,
            "_steady_state_throughput": 5880.0,
            "TRANSACTION_RATE": 10000.0,
            "P50_LATENCY": 18.0,
            "P90_LATENCY": 28.0,
            "P99_LATENCY": 60.0,
            "P999_LATENCY": 92.0,
            "_direction_role": "tx",
        }
        agg = runner.aggregate_results()
        self.assertIsNotNone(agg)
        self.assertAlmostEqual(agg["steady_state_throughput_gbps"], 11.80, places=2)
        self.assertAlmostEqual(agg["pooled_p99_latency_us"], 40.0, places=2)
        self.assertAlmostEqual(agg["pooled_p999_latency_us"], 60.0, places=2)
        self.assertAlmostEqual(agg["worst_flow_p99_latency_us"], 60.0, places=2)
        self.assertAlmostEqual(agg["worst_flow_p999_latency_us"], 92.0, places=2)

        gate_315 = BenchmarkStudyHarness.check_iperf3_version_gate("iperf 3.15", ["iperf3", "-c", "10.0.0.2", "-P", "16"])
        self.assertFalse(gate_315["passed"])
        gate_317_trap = BenchmarkStudyHarness.check_iperf3_version_gate(
            "iperf 3.17.1", ["iperf3", "-c", "10.0.0.2", "-A", "0", "-P", "16"]
        )
        self.assertFalse(gate_317_trap["passed"])
        self.assertTrue(gate_317_trap["has_single_core_affinity_trap"])
        gate_317_ok = BenchmarkStudyHarness.check_iperf3_version_gate(
            "iperf 3.17.1", ["iperf3", "-c", "10.0.0.2", "-P", "16", "-O", "2"]
        )
        self.assertTrue(gate_317_ok["passed"])

        improvements = BenchmarkStudyHarness.evaluate_improvement_opportunities()
        self.assertEqual(len(improvements), 5)

    def test_step9_report_and_template_step89_telemetry(self) -> None:
        """Verify COLLAB-012: netperf_report and netperf-template render Step 8/9 telemetry fields."""
        metrics_with_telemetry = {
            "throughput_gbps": 197.4,
            "steady_state_throughput_gbps": 197.94,
            "pooled_p99_latency_us": 29.4,
            "pooled_p999_latency_us": 44.8,
            "worst_flow_p999_latency_us": 51.2,
            "jains_fairness_index": 0.996,
            "core_overlap_pct": 0.0,
            "cv_pct": 0.25,
            "per_flow_core_matrix": [
                {
                    "flow_id": "F00",
                    "target_cpu": 4,
                    "exec_cpu": 4,
                    "throughput_gbps": 12.37,
                    "p99_latency_us": 28.9,
                    "p999_latency_us": 43.5,
                    "collision_type": "NONE",
                    "is_outlier": False,
                }
            ],
            "pcm_telemetry": {
                "ddio_hit_pct": 99.48,
                "upi_traffic_gbps": 0.14,
                "total_dram_gbps": 0.82,
                "package_watts": 248.0,
                "gbps_per_watt": 0.7981,
            },
            "flent_working_latency": {
                "p50_ms": 0.042,
                "p99_ms": 0.118,
                "p999_ms": 0.194,
            },
        }
        res_json = AIValidationReporter.build_result_json(
            test_case_id="FLOW-TX-16S-MTU9000",
            suite_name="flow-scaling",
            metrics=metrics_with_telemetry,
            target_gbps=195.0,
        )
        self.assertEqual(res_json["verdict"], "PASS")
        self.assertIn("step8_step9_telemetry", res_json)
        self.assertEqual(res_json["step8_step9_telemetry"]["pooled_p999_latency_us"], 44.8)
        self.assertEqual(res_json["step8_step9_telemetry"]["pcm_telemetry"]["ddio_hit_pct"], 99.48)

        dash_md = AIValidationReporter.render_dashboard_markdown(
            "flow-scaling",
            [
                {
                    "test_case_id": "FLOW-TX-16S-MTU9000",
                    "direction": "tx",
                    "streams": 16,
                    "mtu": 9000,
                    **metrics_with_telemetry,
                    "verdict": "PASS",
                }
            ],
        )
        self.assertIn("Step 8/9 Pooled Tail Latency & Fairness Telemetry", dash_md)
        self.assertIn("44.80 us", dash_md)
        self.assertIn("Per-Flow Core Residency & Collision Matrix", dash_md)
        self.assertIn("Intel® PCM Hardware Telemetry", dash_md)
        self.assertIn("99.48%", dash_md)
        self.assertIn("Flent Working Latency Under Load", dash_md)

        # Verify netperf-template normalize_input_context + MARKDOWN_REPORT / HTML_REPORT rendering
        sample_multi_summary = {
            "steady_state_throughput_gbps": 197.94,
            "pooled_p99_latency_us": 29.4,
            "pooled_p999_latency_us": 44.8,
            "worst_flow_p999_latency_us": 51.2,
            "jains_fairness_index": 0.996,
            "core_overlap_pct": 0.0,
            "per_flow_core_matrix": metrics_with_telemetry["per_flow_core_matrix"],
            "pcm_telemetry": metrics_with_telemetry["pcm_telemetry"],
            "flent_working_latency": metrics_with_telemetry["flent_working_latency"],
            "instance_results": [
                {
                    "THROUGHPUT": 12371.25,
                    "_steady_state_throughput": 12371.25,
                    "MEAN_LATENCY": 14.2,
                    "P99_LATENCY": 28.9,
                    "P999_LATENCY": 43.5,
                    "LOCAL_CPU_UTIL": 38.5,
                    "REMOTE_CPU_UTIL": 41.2,
                }
            ],
        }
        ctx = netperf_template.normalize_input_context(sample_multi_summary)
        self.assertEqual(ctx["pooled_p999_latency_us"], 44.8)
        self.assertEqual(ctx["steady_state_throughput_gbps"], 197.94)
        engine = netperf_template.TemplateEngine()
        md_rendered = engine.render_template(
            netperf_template.TemplateLibrary.get_template("markdown-report"), ctx
        )
        self.assertIn("197.94 Gbps", md_rendered)
        self.assertIn("44.8 us", md_rendered)
        self.assertIn("99.48%", md_rendered)
        html_rendered = engine.render_template(
            netperf_template.TemplateLibrary.get_template("html-report"), ctx
        )
        self.assertIn("Pooled p99.9 Latency", html_rendered)
        self.assertIn("Per-Flow Core Residency", html_rendered)

    def test_step9_benchmark_study_execute_runner(self) -> None:
        """Verify COLLAB-011: BenchmarkStudyHarness.execute_study_plan runs randomized trials and computes 95% CIs."""
        from netperf_benchmark_study import BenchmarkStudyHarness

        ecore_topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        harness = BenchmarkStudyHarness(
            host="192.0.2.10",
            interface="ens801f0np0",
            flow_counts=(4,),
            duration=5,
            trials=3,
            topology=ecore_topo,
        )

        def mock_runner(tool_key: str, spec: dict, n_flows: int, trial_idx: int):
            if "netperf_copilot" in tool_key:
                return '{"steady_state_throughput_gbps": 197.8, "jains_fairness_index": 0.996, "instance_results": [{"THROUGHPUT": 49450.0}]}'
            if "classic_netperf" in tool_key:
                return ['{"results": {"THROUGHPUT": 49100.0}}' for _ in range(n_flows)]
            if "iperf2" in tool_key:
                return "[SUM] 0.00-5.00 sec  114 GBytes  195.8 Gbits/sec\n"
            if "multiprocess" in tool_key:
                return ['{"end": {"sum_received": {"bits_per_second": 49150000000.0}}}' for _ in range(n_flows)]
            return '{"end": {"sum_received": {"bits_per_second": 195600000000.0}}}'

        plan = harness.generate_study_plan(iperf3_version_override="iperf 3.17.1")
        executed = harness.execute_study_plan(plan=plan, runner_fn=mock_runner)
        exec_block = executed["flow_matrix"]["4"]["execution_results"]
        self.assertEqual(exec_block["trials_executed"], 3)
        summary = exec_block["summary_by_tool"]
        self.assertIn("netperf_copilot_pinned", summary)
        self.assertEqual(summary["netperf_copilot_pinned"]["n_trials"], 3)
        self.assertAlmostEqual(summary["netperf_copilot_pinned"]["mean_gbps"], 197.8, places=2)
        self.assertAlmostEqual(summary["classic_netperf_pinned"]["mean_gbps"], 196.4, places=2)

    def test_step10_orchestrate_hardening_and_profile_no_yaml(self) -> None:
        """Verify orchestrate --profile works without PyYAML, quotes args, checks deploy, and cleans RDMA."""
        import tempfile
        from unittest import mock

        cli_host = netperf_orchestrate.RemoteHost("cli1", "192.0.2.10", role="client")
        srv_host = netperf_orchestrate.RemoteHost("srv1", "192.0.2.11", role="server")
        inv = netperf_orchestrate.HostInventory([cli_host, srv_host])

        # 1) _run_single_test quotes args and scales timeout dynamically with duration (-l)
        mock_conn = mock.MagicMock()
        mock_conn.execute.return_value = (0, "ok", "")
        with mock.patch.object(cli_host, "get_connection", return_value=mock_conn):
            orch = netperf_orchestrate.RemoteOrchestrator(inv)
            res = orch._run_single_test(cli_host, srv_host, ["-l", "100", "--", "-d", "stream;echo_pwn"])
        self.assertTrue(res["success"])
        called_cmd, called_kwargs = mock_conn.execute.call_args[0][0], mock_conn.execute.call_args[1]
        self.assertIn("'stream;echo_pwn'", called_cmd)
        self.assertGreaterEqual(called_kwargs["timeout"], 260)

        # 2) deploy_netserver fails safely when local_netserver is missing
        deploy_res = orch.deploy_netserver(local_netserver="/nonexistent/netserver")
        self.assertEqual(deploy_res, {"srv1": False})

        # 3) --profile works with HAS_YAML=False, runs all tests, and calls stop_rdma_background on error
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            hosts_file = tmp_path / "hosts.yaml"
            hosts_file.write_text("hosts:\n  - name: cli1\n    address: 192.0.2.10\n    role: client\n  - name: srv1\n    address: 192.0.2.11\n    role: server\n", encoding="utf-8")
            prof_file = tmp_path / "multi_test.yaml"
            prof_file.write_text(
                "name: multi\nglobal:\n  duration: 5\ntests:\n  - name: t1\n    direction: tx\n  - name: t2\n    direction: rx\n",
                encoding="utf-8",
            )

            seen_batches = []
            stop_calls = []

            def fake_run_matrix(self_obj, clients, servers, test_args, parallel=True):
                seen_batches.append(list(test_args))
                if len(seen_batches) == 2:
                    raise RuntimeError("boom on second test")
                return [{"success": True}]

            with mock.patch.object(netperf_orchestrate, "HAS_YAML", False), \
                 mock.patch.object(netperf_orchestrate.RemoteOrchestrator, "start_rdma_background", return_value={"base_port": 18515}), \
                 mock.patch.object(netperf_orchestrate.RemoteOrchestrator, "stop_rdma_background", side_effect=lambda h: stop_calls.append(h)), \
                 mock.patch.object(netperf_orchestrate.RemoteOrchestrator, "run_matrix_tests", autospec=True, side_effect=fake_run_matrix), \
                 mock.patch.object(sys, "argv", ["netperf-orchestrate", "--hosts", str(hosts_file), "--profile", str(prof_file), "--rdma-coexist"]):
                with self.assertRaises(RuntimeError):
                    netperf_orchestrate.main()

            self.assertEqual(len(seen_batches), 2)
            self.assertEqual(len(stop_calls), 1)

    def test_step10_tuner_apply_error_propagation(self) -> None:
        """Verify netperf_tuner --apply-bkm returns exit code 1 when subprocess command fails."""
        import subprocess
        from unittest import mock
        import netperf_tuner

        topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        failed_proc = subprocess.CompletedProcess(args=["ethtool"], returncode=1, stdout="", stderr="Operation not permitted")
        with mock.patch.object(TopologyAnalyzer, "discover_local", return_value=topo), \
             mock.patch.object(netperf_tuner.subprocess, "run", return_value=failed_proc):
            rc = netperf_tuner.main(["--interface", "eth0", "--apply-bkm", "auto"])
        self.assertEqual(rc, 1)

    def test_step10_multi_timeout_cleanup_and_shared_tos(self) -> None:
        """Verify netperf-multi shares resolve_tos_value, kills hung processes, and runs finally cleanup."""
        import subprocess
        from unittest import mock

        self.assertEqual(netperf_multi.resolve_tos_value("AF41"), "0x88")

        inst = netperf_multi.NetperfInstance(instance_id=0, host="192.0.2.10", duration=5)
        fake_proc = mock.MagicMock()
        fake_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["netperf"], timeout=70),
            ("", "timed out cleanly"),
        ]
        fake_proc.returncode = -9
        inst.process = fake_proc
        inst.wait()
        fake_proc.kill.assert_called_once()
        self.assertEqual(inst.returncode, -9)

        mn = netperf_multi.MultiNetperf(host="192.0.2.10", instances=1, duration=5, enable_pcm=True)
        stop_all_calls = []
        pcm_stop_calls = []
        with mock.patch.object(mn, "create_instances"), \
             mock.patch.object(mn, "start_all"), \
             mock.patch.object(mn, "wait_all", side_effect=RuntimeError("wait failure")), \
             mock.patch.object(mn, "stop_all", side_effect=lambda: stop_all_calls.append(True)), \
             mock.patch.object(netperf_multi.IntelPCMCollector, "start_live_collection"), \
             mock.patch.object(netperf_multi.IntelPCMCollector, "stop_and_collect", side_effect=lambda **kw: pcm_stop_calls.append(kw) or {}):
            with self.assertRaises(RuntimeError):
                mn.run(aggregate=False)
        self.assertGreaterEqual(len(stop_all_calls), 1)
        self.assertEqual(len(pcm_stop_calls), 1)

    def test_step10_monitor_interim_parsing(self) -> None:
        """Verify netperf-monitor parses 10^6bits/s, 10^9bits/s, Trans/s, and usec interim output."""
        mon = netperf_monitor.TestMonitor("unit", duration=10)
        netperf_monitor.NetperfMonitor._parse_interim_line(
            "Interim result: 9473.56 10^6bits/s over 0.500 seconds ending at 1.500", mon
        )
        self.assertAlmostEqual(mon.throughput.current(), 9473.56, places=2)
        netperf_monitor.NetperfMonitor._parse_interim_line(
            "Interim result: 9.45 10^9bits/s over 0.500 seconds ending at 2.000", mon
        )
        self.assertAlmostEqual(mon.throughput.current(), 9450.0, places=2)
        netperf_monitor.NetperfMonitor._parse_interim_line(
            "Interim result: 18500.00 Trans/s over 0.500 seconds ending at 2.500", mon
        )
        self.assertAlmostEqual(mon.throughput.current(), 18500.0, places=2)
        netperf_monitor.NetperfMonitor._parse_interim_line(
            "Interim result: 14.20 usec latency over 0.500 seconds ending at 3.000", mon
        )
        self.assertAlmostEqual(mon.latency.current(), 14.20, places=2)

    def test_step10_catalog_precmd_throughput_and_verdict(self) -> None:
        """Verify netperf_catalog fails on pre_commands error and distinguishes Mbps vs Gbps keys."""
        import json
        import subprocess
        import tempfile
        from unittest import mock
        import netperf_catalog

        topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.object(TopologyAnalyzer, "discover_local", return_value=topo):
            out_dir = Path(tmpdir) / "out"

            # 1) Failing pre_commands marks ring-coalesce-matrix cases FAIL without launching netperf-multi
            fail_proc = subprocess.CompletedProcess(args=["ethtool"], returncode=1, stdout="", stderr="Permission denied")
            with mock.patch.object(netperf_catalog.subprocess, "run", return_value=fail_proc) as m_run:
                rc = netperf_catalog.main([
                    "--suite", "ring-coalesce-matrix",
                    "--host", "192.0.2.10",
                    "--interface", "eth0",
                    "--output-dir", str(out_dir),
                ])
            self.assertEqual(rc, 1)
            self.assertTrue(all("netperf-multi" not in str(c) for c in m_run.call_args_list))
            res_json = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(res_json["results"][0]["verdict"], "FAIL")

            # 2) Valid execution with 1500.0 Mbps THROUGHPUT scales cleanly to 1.5 Gbps and matches report verdict
            ok_dir = Path(tmpdir) / "out_ok"

            def ok_subproc(cmd, **kwargs):
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=json.dumps({"results": {"THROUGHPUT": 1500.0}}),
                    stderr="",
                )

            with mock.patch.object(netperf_catalog.subprocess, "run", side_effect=ok_subproc):
                rc2 = netperf_catalog.main([
                    "--suite", "flow-scaling",
                    "--host", "192.0.2.10",
                    "--interface", "eth0",
                    "--output-dir", str(ok_dir),
                ])
            self.assertEqual(rc2, 0)
            csv_txt = (ok_dir / "summary.csv").read_text(encoding="utf-8")
            self.assertIn(",1.5,", csv_txt)
            ok_json = json.loads((ok_dir / "result.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(ok_json["results"][0]["metrics"]["throughput_gbps"], 1.5, places=3)
            self.assertEqual(ok_json["results"][0]["verdict"], "PASS")

    def test_step10_stats_and_pool_scoping(self) -> None:
        """Verify exact Student-t critical values and pool-scoped netserver PID stop/strict SSH flags."""
        from unittest import mock
        from netperf_stats import AdvancedStatistics

        self.assertAlmostEqual(AdvancedStatistics._t_critical(1, 0.95), 12.706, places=3)
        self.assertAlmostEqual(AdvancedStatistics._t_critical(4, 0.95), 2.776, places=3)
        self.assertAlmostEqual(AdvancedStatistics._t_critical(20, 0.80), 1.325, delta=0.01)

        topo = TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT)
        mgr = NetserverPoolManager(host="192.0.2.11", base_port=18700, strict_host_key=True, topology=topo)
        with mock.patch.object(mgr, "_run_cmd", return_value=(0, "", "")) as mock_cmd:
            ok, msg = mgr.stop_pool()
        self.assertTrue(ok)
        self.assertIn("/tmp/netserver_pool_18700.pids", mock_cmd.call_args[0][0])
        self.assertNotIn("pkill -9 netserver", mock_cmd.call_args[0][0])

        with mock.patch("netserver_manager.subprocess.run") as mock_ssh:
            mock_ssh.return_value = mock.MagicMock(returncode=0, stdout="", stderr="")
            mgr._run_cmd("echo ok")
        ssh_argv = mock_ssh.call_args[0][0]
        self.assertIn("StrictHostKeyChecking=yes", ssh_argv)

    def test_step10_monitor_live_stops_display_thread(self) -> None:
        """Verify monitor_live stops and joins its daemon display thread on completion."""
        import io
        import threading
        from unittest import mock

        mon_runner = netperf_monitor.NetperfMonitor(netperf_path="netperf")
        fake_proc = mock.MagicMock()
        fake_proc.stdout = iter([
            "Interim result: 12345.67 10^6bits/s over 0.500 seconds ending at 1700000000.000\n",
            "NETPERF_INTERIM_RESULT[0]=48705.72\n",
            "NETPERF_UNITS[0]=10^6bits/s\n",
            "NETPERF_INTERIM_RESULT[1]=49.00\n",
            "NETPERF_UNITS[1]=10^9bits/s\n",
            "LOCAL_CPU_UTIL=-1.00\n",
        ])
        fake_proc.returncode = 0
        fake_proc.wait.return_value = 0

        spawned_threads = []
        real_thread = threading.Thread

        def _capture_thread(*args, **kwargs):
            t = real_thread(*args, **kwargs)
            spawned_threads.append(t)
            return t

        with mock.patch.object(netperf_monitor.subprocess, "Popen", return_value=fake_proc), \
             mock.patch.object(netperf_monitor.threading, "Thread", side_effect=_capture_thread), \
             mock.patch.object(netperf_monitor.sys, "stdout", new_callable=io.StringIO):
            mon_runner.monitor_live("192.0.2.10", ["-t", "TCP_STREAM"], duration=1)

        self.assertEqual(len(mon_runner.display.monitors), 1)
        result = mon_runner.display.monitors[0]
        self.assertFalse(mon_runner.display.running)
        self.assertFalse(result.running)
        self.assertTrue(result.completed)
        self.assertEqual(result.throughput.count, 3)
        self.assertAlmostEqual(result.throughput.samples[2], 49000.0, places=2)
        self.assertEqual(result.cpu_local.count, 0)
        self.assertEqual(len(spawned_threads), 1)
        self.assertTrue(spawned_threads[0].daemon)
        self.assertFalse(spawned_threads[0].is_alive())

    def test_step11_non_default_tunings_in_results(self) -> None:
        """Verify non-default tunings rule and automatic provenance capture in result payloads and dashboards."""
        import json
        import tempfile
        from unittest import mock
        from netperf_tunings import extract_non_default_tunings

        rule_path = REPO_ROOT / ".agents" / "rules" / "non-default-tunings-in-results.md"
        self.assertTrue(rule_path.is_file())
        rule_txt = rule_path.read_text(encoding="utf-8")
        self.assertIn("Mandatory Non-Default Tunings", rule_txt)
        self.assertIn("non_default_tunings", rule_txt)

        raw = {
            "probe_supported": True,
            "sysctls": {
                "net.core.rmem_max": "2147483647",
                "net.core.netdev_budget": "600",
                "net.ipv4.tcp_limit_output_bytes": "1048576",
            },
            "cmdline": "BOOT_IMAGE=/vmlinuz iommu=pt isolcpus=2-15",
            "cpu_governors": ["performance"],
            "irqbalance": "inactive",
            "nics": {"eth0": {"mtu": 9000, "ring_rx": 4096, "qdisc": "fq"}},
            "module_params": {},
        }
        diffed = extract_non_default_tunings(raw_probe=raw, explicit_overrides={"layout": "spread_step2"})
        self.assertEqual(diffed["sysctl_overrides"]["net.core.rmem_max"]["value"], "2147483647")
        self.assertEqual(diffed["sysctl_overrides"]["net.core.netdev_budget"]["value"], "600")
        self.assertNotIn("net.ipv4.tcp_limit_output_bytes", diffed["sysctl_overrides"])
        self.assertEqual(diffed["nic_overrides"]["eth0"]["mtu"]["value"], 9000)

        rec = AIValidationReporter.build_result_json(
            test_case_id="T-TUNINGS-01",
            suite_name="flow-scaling",
            metrics={"throughput_gbps": 188.25, "cv_pct": 0.4},
            non_default_tunings=diffed,
        )
        self.assertIn("non_default_tunings", rec)
        self.assertEqual(rec["non_default_tunings"]["nic_overrides"]["eth0"]["mtu"]["value"], 9000)

        md = AIValidationReporter.render_dashboard_markdown(
            "flow-scaling",
            [{"test_case_id": "T-TUNINGS-01", "direction": "tx", "streams": 16, "mtu": 9000, "throughput_gbps": 188.25, "cv_pct": 0.4, "verdict": "PASS"}],
            non_default_tunings=diffed,
        )
        self.assertIn("## Active Non-Default Tunings", md)
        self.assertIn("sysctl:net.core.netdev_budget", md)

        multi = netperf_multi.MultiNetperf(host="192.0.2.10", instances=4, direction="tx", mtu=9000, interfaces="eth0")
        payload = multi.build_output_payload(aggregate=False)
        self.assertIn("non_default_tunings", payload)

        tuner = NetperfTuner(interface="eth0", topology=TopologyAnalyzer.from_topology_snapshot(ECORE_288_SNAPSHOT))
        sweep = tuner.run_ab_sweep(knob="mtu", values=[1500, 9000])
        self.assertIn("non_default_tunings", sweep)

        import netperf_catalog
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = netperf_catalog.main(["--suite", "flow-scaling", "--host", "192.0.2.10", "--interface", "eth0", "--dry-run", "--output-dir", tmpdir])
            self.assertEqual(rc, 0)
            cat_json = json.loads((Path(tmpdir) / "result.json").read_text(encoding="utf-8"))
            self.assertIn("non_default_tunings", cat_json)
            self.assertIn("non_default_tunings", cat_json["results"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

# === METADATA_FOOTER_START ===
# Search Keywords: unit tests, test_modernization, Intel PCM, Flent working latency, two-tier benchmark study
# Drivers & Subsystems: ice, irdma, mlx5_core, idpf, nettest_omni.c
# Related Units / Patches: DOC-NETPERF-STEP8-BENCHMARK-METHODOLOGY
# Created / Last-Updated: 2026-11-05 / 2026-11-16
# === METADATA_FOOTER_END ===
