# Agent Collaboration Hub (`Antigravity` <-> `GitHub Copilot`)

<!-- === METADATA_HEADER_START === -->
- **Document ID**: `DOC-NETPERF-AGENT-COLLAB-HUB-001`
- **Version**: `v3.1`
- **Status**: `Active`
- **Created Date**: `2026-11-16`
- **Last Updated Date**: `2026-11-16`
- **Target Scope**: Multi-agent coordination protocol, local clone topology map, Step 8/9 code review ledger, and shared
  task queue between Antigravity and GitHub Copilot across `thehevy/netperf_copilot`.
- **Summary**: Defines the shared communication workspace (`dev/collab/`), documents the two local Git clones on the
  workstation, evaluates GitHub Copilot's Step 8/9 PCM/Flent/Benchmark Study implementations, and tracks joint fixes.
<!-- === METADATA_HEADER_END === -->

## 1. Purpose & Multi-Agent Coordination Protocol

This folder (`dev/collab/`) is the shared communication and task-coordination hub between **Antigravity** and **GitHub
Copilot** when collaborating on `thehevy/netperf_copilot`.

### 1.1 Why Two Agents Saw Different Files Earlier (`Clone A` vs. `Clone B`)

Two local clones of `https://github.com/thehevy/netperf_copilot.git` exist on this workstation:

| Clone ID | Local Workspace Path | Primary Agent | Role & Sync Policy |
| --- | --- | --- | --- |
| `Clone A` | .../Netperf_<wbr><wbr>Modernization_Project<wbr>/<wbr>netperf_copilot | Antigravity | Primary build, style validation (`D1`-`D10`), and Wiki sync workspace. |
| `Clone B` | .../Network_Performance/<wbr><wbr>github_projects/<wbr>netperf_<wbr>copilot | GitHub Copilot | Secondary workspace where Copilot authored the Step 8/9 PCM/Flent/Study enhancements. |
| `Remote` | [github.com/netperf_copilot.gi](https://github.com/thehevy/netperf_copilot.git) | Both Agents | Keep both `origin/master` and `origin/main` synchronized at identical commit SHAs. |

Earlier on `2026-11-16`, `Clone B` was checked out at an older commit (`8bef0f1c`) before
`dev/tools/netperf_flent_bridge.py` was added in `Clone A` (`ce357b0`), and `origin/main` trailed `origin/master`. Both
clones and both remote branches (`master` and `main`) are now kept in lockstep via this collaboration hub.

### 1.2 Mandatory Coordination Rules for All Agents

1. **Read `dev/collab/SHARED_TASK_QUEUE.json` First**: Before creating or modifying files in `dev/tools/`, `src/`,
   `dev/docs/`, or `wiki/`, check `dev/collab/SHARED_TASK_QUEUE.json` to see active tasks and file ownership.
2. **Synchronize Both Local Clones (`Clone A` and `Clone B`)**: Whenever either agent completes a task, sync the changes
   across both `Clone A` and `Clone B` (or push to `origin/master` + `origin/main` and pull in the peer clone).
3. **Enforce Documentation & Code Standards (`Rules D1`-`D10` v3.2)**:
   - Always use `GbE` or `Gb` (never standalone `G`) when noting Ethernet speeds (`200GbE`, `800GbE`, `570.8Gb`).
   - Always use `PCIe 3.0`, `PCIe 4.0`, `PCIe 5.0`, `PCIe 6.0` (never `Gen3`, `Gen4`, `Gen5`, `Gen6`).
   - Update `Last Updated Date` to the current US Pacific date (`YYYY-MM-DD`) in `METADATA_HEADER_START..END` and
     `METADATA_FOOTER_START..END` whenever a file is modified.
   - Include `# Search Keywords:` in every Python/Bash script footer (`METADATA_FOOTER_START..END`).
   - Run `python scripts/markdown_validator.py . --fix` and `python dev/tests/test_modernization.py` before committing.

---

## 2. Technical Evaluation of GitHub Copilot's Step 8 & Step 9 Changes

Antigravity reviewed all Step 8 and Step 9 files authored by GitHub Copilot across `Clone B` and `Clone A`. Below is the
structured evaluation of what Copilot built, what works well, and the `10` joint items (`COLLAB-001`..`COLLAB-010`)
completed together.

### 2.1 Component-by-Component Assessment

| File / Component | Lines | Evaluation Summary | Status |
| --- | --- | --- | --- |
| [`netperf_pcm_bridge.py`](../tools/netperf_pcm_bridge.py) | `535` | Clean zero-dependency implementation of `IntelPCMCollector` (live background CSV collection + offline `--pcm-csv-dir` replay for `pcm`, `pcm-pcie -e`, `pcm-memory`, `pcm-numa`, `pcm-power`), `ProcStatGroundTruth` (`/proc/stat` jiffy delta + `compute_cpu_reporting_error()`), `PCM_COUNTER_FORMULAS`, and `--self-test`. | Verified (`PASS`) |
| [`netperf_benchmark_study.py`](../tools/netperf_benchmark_study.py) | `723` | Rigorous 2-tier comparative benchmark study harness (`BenchmarkStudyHarness`) comparing `netperf_copilot`, classic `netperf`, `iperf2`, and `iperf3` (`<= 3.15` reactor vs. `>= 3.16` multi-threaded `-P` PR #1591) across Tier A (`default_unpinned`) and Tier B (`tuned_pinned`) with `check_iperf3_version_gate()`, `parse_iperf3_json_output()`, `parse_iperf2_output()`, and `--self-test`. | Verified (`PASS`) |
| [`netperf_flent_bridge.py`](../tools/netperf_flent_bridge.py) | `537` | Added `FlentWorkingLatencyProbe` to run a concurrent `TCP_RR` working-latency probe during multi-stream bulk transfers and parse `P50`/`P99`/`P99.9` (`P999_LATENCY`) + `working_latency_inflation_ratio` plus `run_self_test()` and `--self-test` CLI support. | Enhanced & Verified (`PASS`) |
| [`netperf-multi`](../tools/netperf-multi) | `1510` | Added `threading.Barrier` synchronized stream start (`launch_skew_ms`), `-w`/`--barrier-wait`, `-O`/`--omit` steady-state filter (`steady_state_throughput_gbps`), `--data-port-base`, transaction-weighted `pooled_p50/p90/p99/p999_latency_us`, `--pcm`, `--flent-working-latency`, `sample_runtime_cpu()`, and `audit_core_residency_and_fairness()`. | Fixed & Verified (`PASS`) |
| [`nettest_omni.c`](../../src/nettest_omni.c) & Presets | `8235` | Added `P999_LATENCY` (`HIST_get_percentile(time_hist, 0.999)`), `LOCAL_CPU_EXEC` (`sched_getcpu()` + `/proc/self/stat` fallback), `REMOTE_CPU_EXEC`, and `LOCAL_CPU_MIGRATIONS` (including mid-loop `& 0xfff == 0` sampling in `send_omni()`) to OMNI output selectors, JSON output, and [`latency.out`](../catalog/output-presets/latency.out), [`cpu.out`](../catalog/output-presets/cpu.out), and [`verbose.out`](../catalog/output-presets/verbose.out). | Verified (`PASS`) |
| [`test_modernization.py`](../tests/test_modernization.py) | `840` | Added Step 8 and Step 9 unit tests (`test_step8_*` + test_step9_omit_pooled_<wbr><wbr>tail_latency_and_<wbr>iperf3_<wbr>gate) plus all three bridge `--self-test` modes (`24/24` unit tests passing). | Verified (`24/24 PASS`) |
| [WP_NETPERF_COPILOT_VS_<wbr>IPERF2_IPERF3_NETPERF_<wbr>BENCHMARK_STUDY.md](../docs/WP_NETPERF_COPILOT_VS_IPERF2_IPERF3_NETPERF_BENCHMARK_STUDY.md) | `225` | Published `v4.0` benchmark study white paper (DOC-WP-NETPERF-COPILOT-<wbr><wbr>BENCHMARK-STUDY-001) documenting `IMP-001`..`IMP-005`, `iperf3 <= 3.15` vs. `>= 3.16`, Tier A vs. Tier B scaling (`1` to `64` flows at `100GbE` and `200GbE`), and `/proc/stat` + `Intel® PCM` verification. | Verified (`100/100`) |

### 2.2 Joint Bug Fixes & Style Alignment Ledger (`COLLAB-001`..`COLLAB-010`)

| Finding ID | Target File(s) | Issue Identified During Review | Joint Resolution Applied |
| --- | --- | --- | --- |
| `COLLAB-001` | [`netperf-multi`](../tools/netperf-multi) | Line 979 called AdvancedStatistics.<wbr><wbr>detect_outliers(tputs<wbr>_<wbr>gbps, `method='iqr')`, but only `StatisticalAnalyzer` was imported on Line 53, causing a silent `NameError` inside `try/except` and skipping IQR outlier flow detection. | Updated import on Line 53 to `from netperf_stats import AdvancedStatistics, StatisticalAnalyzer`. |
| `COLLAB-002` | [`netperf_flent_bridge.py`](../tools/netperf_flent_bridge.py) | Copilot noted that both bridge scripts should support `--self-test`, and implemented `run_self_test()` in `netperf_pcm_bridge.py`, but `netperf_flent_bridge.py` lacked `run_self_test()` and a CLI `main()` entrypoint. | Added `run_self_test()` (validating `FlentIngester`, `FlentExporter`, and FlentWorkingLatencyProbe<w<wbr>br><wbr>._parse_rr_output()) and `--self-test` CLI support to `netperf_flent_bridge.py`. |
| `COLLAB-003` | [`netperf-multi`](../tools/netperf-multi), [`netperf_flent_bridge.py`](../tools/netperf_flent_bridge.py) | When `--flent-working-latency` is combined with `--per-core-netserver` (as in `netperf_benchmark_study.py` Tier B), `FlentWorkingLatencyProbe` defaulted to `control_port=12865`, which fails if only per-core `netserver` ports (`18600 + core`) are listening. | Passed control_port=(args.base_port + 0 if args.per_core_netserver else 12865) from `netperf-multi` into `FlentWorkingLatencyProbe`. |
| `COLLAB-004` | [`netperf_pcm_bridge.py`](../tools/netperf_pcm_bridge.py), [`netperf_benchmark_study.py`](../tools/netperf_benchmark_study.py) | Script footers (`METADATA_FOOTER_START..END`) were missing `# Search Keywords:` required by Global Rule 4. | Added `# Search Keywords:` to both script metadata footers. |
| `COLLAB-005` | [`TECHNICAL_WHITE_PAPER.md`](../docs/TECHNICAL_WHITE_PAPER.md), [`Technical-White-Paper.md`](../../wiki/Technical-White-Paper.md) | `Clone B` white paper edits were based on `1762f32` before the `Gb`/`GbE` speed notation fix (`8ae1736`), reintroducing standalone `G` (`570.8G TX`, `172.4G TX`) and `Last Updated Date: 2026-11-13`. | Merged Case Study 5 with the `Gb`/`GbE` (`570.8Gb TX`, `172.4Gb TX`) and `PCIe 5.0`/`6.0` fixes and updated `Last Updated Date` to `2026-11-16`. |
| `COLLAB-006` | [`README.md`](../../README.md), [`CLI-Tools-Reference.md`](../../wiki/CLI-Tools-Reference.md) | New Step 8 CLI scripts (`netperf_pcm_bridge.py`, `netperf_flent_bridge.py`, `netperf_benchmark_study.py`) and `netperf-multi` flags (`--pcm`, `--pcm-csv-dir`, `--flent-working-latency`, `--barrier-wait`) needed documentation in `README.md` and `wiki/CLI-Tools-Reference.md`. | Added CLI reference entries and updated `Last Updated Date: 2026-11-16`. |
| `COLLAB-007` | [`nettest_omni.c`](../../src/nettest_omni.c) | Sampling `get_current_runtime_cpu()` only at `cpu_start()` and `cpu_stop()` could miss mid-run scheduler migrations that return to the starting CPU before test completion. | Added low-overhead bitwise (`& 0xfff == 0`) runtime CPU sampling inside `send_omni()` to capture mid-run core migrations in `LOCAL_CPU_MIGRATIONS`. |
| `COLLAB-008` | [`netperf_benchmark_study.py`](../tools/netperf_benchmark_study.py), [`test_modernization.py`](../tests/test_modernization.py) | `netperf_benchmark_study.py` generated the 2-tier command plan but needed deterministic output parsers for `iperf3 -J` and `iperf2 -P N` plus a `--self-test` CLI flag matching the other two Step 8 bridges. | Added `parse_iperf3_json_output()`, `parse_iperf2_output()`, `run_self_test()`, and `--self-test` CLI support to `netperf_benchmark_study.py`. |
| `COLLAB-009` | [`netperf-multi`](../tools/netperf-multi), [`netperf_benchmark_study.py`](../tools/netperf_benchmark_study.py), [WP_NETPERF_COPILOT_VS_<wbr>IPERF2_IPERF3_NETPERF_<wbr>BENCHMARK_STUDY.md](../docs/WP_NETPERF_COPILOT_VS_IPERF2_IPERF3_NETPERF_BENCHMARK_STUDY.md) | Identified 5 improvement opportunities (`IMP-001`..`IMP-005`) over stock `netperf`, `iperf2`, and `iperf3 >= 3.16`: warm-up exclusion (`--omit`), pooled multi-flow `p99`/`p99.9` tail latency, deterministic `--data-port-base`, `< 5 ms` barrier launch, and `iperf3 >= 3.16` version gating. | Implemented all 5 improvements (`IMP-001`..`IMP-005`), added `test_step9`, and published WP_NETPERF_COPILOT_VS_<wbr><wbr>IPERF2_IPERF3_NETPERF<wbr>_<wbr>BENCHMARK_STUDY.md (`v4.0`). |
| `COLLAB-010` | `auto_tune`, `HevyOne`, `TestCases`, `E835_DRIVER_POC`, `HevyHitter` Harnesses | Portfolio test harnesses invoking `iperf3 -P N` must verify `iperf3 >= 3.16` (`3.17.1+` with multi-threaded `-P` pthreads, PR #1591) and never combine `-A <single_cpu>` with `-P N` ($N > 1$). | Upgraded `validation_harness_v2.py` (`v2.2`, Rule `HH-VAL-005`) across all 5 repos (`auto_tune`, `HevyOne`, `TestCases`, `E835_DRIVER_POC`, `HevyHitter`), wired `check_iperf3_version_gate()` into `auto_tune` and 11 `E835_DRIVER_POC` harnesses, rebuilt & replicated `HevyDocLib` (`v4.0`), and closed `COP-003` (`AGY-003`). |

---

## 3. How to Hand Off Follow-Up Work Between Agents

When either **GitHub Copilot** or **Antigravity** starts a new task:

1. Add or update an entry in [`SHARED_TASK_QUEUE.json`](SHARED_TASK_QUEUE.json) with `"status": "in_progress"` and
   `"assigned_agent": "github_copilot"` or `"antigravity"`.
2. Record any architectural notes, test outputs, or open questions in Section 2.2 of this document.
3. Run the verification suite before marking the task `"completed"`:

```bash
python dev/tools/netperf_pcm_bridge.py --self-test
python dev/tools/netperf_flent_bridge.py --self-test
python dev/tools/netperf_benchmark_study.py --self-test
python dev/tests/test_modernization.py
python scripts/markdown_validator.py . --fix
```

<!-- === METADATA_FOOTER_START === -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| File Path | `dev/collab/AGENT_COLLABORATION_HUB.md` |
| Created / Last Updated | `2026-11-16` / `2026-11-16` |
| Keywords / Search Tags | `agent collaboration`, `Antigravity`, `GitHub Copilot`, `netperf_pcm_bridge`, `netperf_flent_bridge`, `netperf_benchmark_study`, `Step 8`, `Step 9` |
| Drivers & Subsystems | `ice`, `irdma`, `mlx5_core`, `idpf`, `netperf-multi`, `Intel PCM`, `Flent` |
| Validation / Patch IDs | `DOC-NETPERF-AGENT-COLLAB-HUB-001` |
<!-- === METADATA_FOOTER_END === -->
