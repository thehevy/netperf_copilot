# Agent Collaboration Hub (`Antigravity` <-> `GitHub Copilot`)

<!-- === METADATA_HEADER_START === -->
- **Document ID**: `DOC-NETPERF-AGENT-COLLAB-HUB-001`
- **Version**: `1.0`
- **Status**: `Active`
- **Created Date**: `2026-11-16`
- **Last Updated Date**: `2026-11-16`
- **Target Scope**: Multi-agent coordination protocol, local clone topology map, Step 8 code review ledger, and shared
  task queue between Antigravity and GitHub Copilot across `thehevy/netperf_copilot`.
- **Summary**: Defines the shared communication workspace (`dev/collab/`), documents the two local Git clones on the
  workstation, evaluates GitHub Copilot's Step 8 PCM/Flent/Benchmark Study implementations, and tracks joint fixes.
<!-- === METADATA_HEADER_END === -->

## 1. Purpose & Multi-Agent Coordination Protocol

This folder (`dev/collab/`) is the shared communication and task-coordination hub between **Antigravity** and **GitHub
Copilot** when collaborating on `thehevy/netperf_copilot`.

### 1.1 Why Two Agents Saw Different Files Earlier (`Clone A` vs. `Clone B`)

Two local clones of `https://github.com/thehevy/netperf_copilot.git` exist on this workstation:

| Clone ID | Local Workspace Path | Primary Agent | Role & Sync Policy |
| --- | --- | --- | --- |
| `Clone A` | .../Netperf_<wbr><wbr>Modernization_Project<wbr>/<wbr>netperf_copilot | Antigravity | Primary build, style validation (`D1`-`D10`), and Wiki sync workspace. |
| `Clone B` | .../Network_Performance/<wbr><wbr>github_projects/<wbr>netperf_<wbr>copilot | GitHub Copilot | Secondary workspace where Copilot authored the Step 8 PCM/Flent/Study enhancements. |
| `Remote` | [github.com/netperf_copilot.gi](https://github.com/thehevy/netperf_copilot.git) | Both Agents | Keep both `origin/master` and `origin/main` synchronized at identical commit SHAs. |

Earlier on `2026-11-16`, `Clone B` was checked out at an older commit (`8bef0f1c`) before
`dev/tools/netperf_flent_bridge.py`
was added in `Clone A` (`ce357b0`), and `origin/main` trailed `origin/master`. Both clones and both remote branches
(`master` and `main`) are now kept in lockstep via this collaboration hub.

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

## 2. Technical Evaluation of GitHub Copilot's Step 8 Changes

Antigravity reviewed all `8` uncommitted Step 8 files authored by GitHub Copilot in `Clone B`. Below is the structured
evaluation of what Copilot built, what works well, and the `5` issues resolved jointly.

### 2.1 Component-by-Component Assessment

| File / Component | Lines | Evaluation Summary | Status |
| --- | --- | --- | --- |
| [`netperf_pcm_bridge.py`](../tools/netperf_pcm_bridge.py) | `535` | Clean zero-dependency implementation of `IntelPCMCollector` (live background CSV collection + offline `--pcm-csv-dir` replay for `pcm`, `pcm-pcie -e`, `pcm-memory`, `pcm-numa`, `pcm-power`), `ProcStatGroundTruth` (`/proc/stat` jiffy delta + `compute_cpu_reporting_error()`), `PCM_COUNTER_FORMULAS`, and `--self-test`. | Verified (`PASS`) |
| [`netperf_benchmark_study.py`](../tools/netperf_benchmark_study.py) | `435` | Rigorous 2-tier comparative benchmark study harness (`BenchmarkStudyHarness`) comparing `netperf_copilot`, classic `netperf`, `iperf2`, and `iperf3` (`<= 3.15` reactor vs. `>= 3.16` multi-threaded `-P` PR #1591) across Tier A (`default_unpinned`) and Tier B (`tuned_pinned`) with randomized trial order and 95% Student-$t$ CIs. | Verified (`PASS`) |
| [`netperf_flent_bridge.py`](../tools/netperf_flent_bridge.py) | `537` | Added `FlentWorkingLatencyProbe` to run a concurrent `TCP_RR` working-latency probe during multi-stream bulk transfers and parse `P50`/`P99`/`P99.9` (`P999_LATENCY`) + `working_latency_inflation_ratio`. Antigravity added `run_self_test()` and `--self-test` CLI support. | Enhanced & Verified (`PASS`) |
| [`netperf-multi`](../tools/netperf-multi) | `1452` | Added `threading.Barrier` synchronized stream start (`launch_skew_ms`, `-w`/`--barrier-wait`), `--pcm`, `--pcm-csv-dir`, `--flent-working-latency`, `sample_runtime_cpu()` (`200 ms` `/proc/<pid>/stat` field 39 polling), and `audit_core_residency_and_fairness()`. Fixed missing `AdvancedStatistics` import and per-core port selection. | Fixed & Verified (`PASS`) |
| [`nettest_omni.c`](../../src/nettest_omni.c) & Presets | `8227` | Added `P999_LATENCY` (`HIST_get_percentile(time_hist, 0.999)`), `LOCAL_CPU_EXEC` (`sched_getcpu()` + `/proc/self/stat` fallback), `REMOTE_CPU_EXEC`, and `LOCAL_CPU_MIGRATIONS` to OMNI output selectors, JSON output, and [`latency.out`](../catalog/output-presets/latency.out), [`cpu.out`](../catalog/output-presets/cpu.out), and [`verbose.out`](../catalog/output-presets/verbose.out). | Verified (`PASS`) |
| [`test_modernization.py`](../tests/test_modernization.py) | `755` | Added 4 Step 8 unit tests (test_step8_pcm_bridge_<wbr><wbr>and_proc_stat_ground_<wbr><wbr>truth, test_step8_core_<wbr><wbr>residency_and_<wbr>fairness_<wbr>audit, test_step8_benchmark_<wbr><wbr>study_two_tier_<wbr><wbr>methodology, test_step8_omni_c_p999_<wbr><wbr>and_runtime_cpu_<wbr><wbr>telemetry) plus Flent bridge self-test coverage (`30` total tests). | Verified (`30/30 PASS`) |
| [`TECHNICAL_WHITE_PAPER.md`](../docs/TECHNICAL_WHITE_PAPER.md) | `660` | Added Case Study 5 (*Two-Tier Comparative Benchmark Methodology & Reproducibility Appendix*) covering Tier A vs. Tier B, `iperf3` version regime split, `/proc/stat` + PCM ground truth, and core-residency auditing. | Fixed `D1`-`D7` & Verified (`100/100`) |

### 2.2 Joint Bug Fixes & Style Alignment Ledger (`COLLAB-001`..`COLLAB-006`)

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
| Keywords / Search Tags | `agent collaboration`, `Antigravity`, `GitHub Copilot`, `netperf_pcm_bridge`, `netperf_flent_bridge`, `netperf_benchmark_study`, `Step 8` |
| Drivers & Subsystems | `ice`, `irdma`, `mlx5_core`, `idpf`, `netperf-multi`, `Intel PCM`, `Flent` |
| Validation / Patch IDs | `DOC-NETPERF-AGENT-COLLAB-HUB-001` |
<!-- === METADATA_FOOTER_END === -->
