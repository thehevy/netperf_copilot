# Post-Update Repository Audit & Remediation Plan

**Audit Date**: November 2026  
**Audited Commits**: `26e1f28`, `1759249`, `1924593`  
**Scope**: Core C Engine (`src/`), Python CLI Tools (`dev/tools/`), YAML Profiles (`dev/profiles/`), Test Suite (`dev/tests/`), Documentation (`dev/docs/`, `README.md`), and Project Wiki (`wiki/`)

---

## 1. Executive Summary of Audit Findings

A comprehensive code and documentation audit of the updated repository identified **4 categories of issues**:
1. **Critical Functional Bugs in Code (`src/` & `dev/tools/`)**:
   - `netperf-catalog` live runs hardcoded `tput_gbps = 0.0` (never parsing `proc.stdout`), causing `AIValidationReporter` to mark 100% of live runs as `FAIL` (`"Zero throughput / transaction rate"`).
   - `netperf-catalog` `core-locality` suite connected all 4 locality tests to `-p 18600` instead of per-core `-p $((18600 + core))`, and on single-NUMA hosts selected the identical core (`4`) for both `LOC-LOCAL-NUMA` and `LOC-CROSS-NUMA`.
   - `netperf-catalog` `ring-coalesce-matrix` suite recorded ring and coalescing parameters in metadata without executing `ethtool -G` / `ethtool -C` pre-commands during live runs.
   - `netperf-orchestrate` checked `if args.profile or args.netperf_args:` but completely ignored `args.profile`, running bare `netperf` with empty arguments when `--profile` was passed.
   - `netperf_topology.py` `select_layout_strategy()` and `get_bkm_parameters()` returned `spread_step2` and `tx_ring=4096` for E-core and `sequential` for P-core, contradicting `netperf_tuner.py`, `netperf_catalog.py`, and the technical documentation (`spread_l2` and `tx_ring=512` on E-core; `spread_step2` and `tx_ring=2048` on P-core).
   - In `src/Makefile.am`, `src/netdrv_ethtool.c`, `src/netslot_linux.c`, and `src/netsys_linux.c` were not included in build sources (`COMMON_SRC`), even though `src/nettest_omni.c` calls `find_driver_ext_info()` on Linux, which would cause a linker error (`undefined reference to find_driver_ext_info`) when building on Linux.
   - In `src/nettest_omni.c` and `src/nettest_bsd.h`, `active_cpu_util` and `active_cpu_count` were emitted in JSON `metadata` for the local host only, but were not registered as OMNI output selectors (`LOCAL_CPU_ACTIVE_UTIL`, `LOCAL_CPU_ACTIVE_COUNT`, `REMOTE_CPU_ACTIVE_UTIL`, `REMOTE_CPU_ACTIVE_COUNT`) or transmitted in `omni_results_struct`.
2. **CLI Flag Mismatches Between Tools and Documentation/Wiki**:
   - `netperf-multi`: Docs used `--bkm cwf-ecore` (missing flag), `-o <file.json>` instead of `-o json --export <file.json>`, and `-l 30` *after* `--` (where OMNI `getopt` interprets `-l` as `multicast_ttl` rather than test duration).
   - `netserver-manager`: Docs used `--action start -n 32` and `--count 32`, whereas `netserver_manager.py` only defined `--start|--stop|--verify|--plan` and `--max-instances`.
   - `netperf-preflight`: Docs used `-H <host> --streams 16 --warmup-runs 5 --min-gbps 180` and `--lp-state <file>`, which were implemented in `PreflightChecker` methods but not wired into `argparse` in `main()`.
   - `netperf-catalog`: Docs used `-s core-locality`, whereas `netperf_catalog.py` only accepted `--suite`.
   - `netperf-profile`: Docs used `--export <file.json>`, whereas `netperf-profile` only accepted `--save-results`.
   - `netperf-monitor`: Docstrings and docs passed `-l 60` after `--` instead of before `--` (or via `-d 60`).
3. **Technical & Data Contradictions Between Docs and Code**:
   - `dev/docs/TECHNICAL_WHITE_PAPER.md` (and `wiki/Technical-White-Paper.md`) listed mismatched rule IDs in its Section 6.1 `AA-001`–`AA-024` table, contradicted `netperf_tuner.py` on `cwf-ecore` `rx_ring` (`2048` vs `4096`) and `adaptive-rx` (`on` vs `off`), and showed a `netperf-aggregate --compare` JSON schema that did not match `ResultComparator.compare()`.
   - `src/netcpu_procstat.c` used `>= 1.0f` for `active_cpu_util` while docs stated `>= 5.0%` (`> 5%`), and used `>=` for `peak_cpu_util` causing idle CPUs (`0.0%`) to report `peak_cpu_id = num_cpus - 1`.
4. **Broken Wiki Sidebar Anchors & Formatting Issues**:
   - `wiki/_Sidebar.md` contained subsection anchor links that did not match the actual markdown heading slugs in the wiki files.
   - `README.md` had inconsistent profile counts (`10` vs `15`), wiki guide counts (`8` vs `9`), and a corrupted Unicode heading character on line 300.

---

## 2. Remediation Plan & Execution Checklist

### Phase A: Core C Engine & Build System Fixes (`src/`)
- [x] **A.1 Fix Linux Build Linkage (`src/Makefile.am`, `src/netdrv_ethtool.c`, `src/netslot_linux.c`, `src/netsys_linux.c`)**:
  - Guard Linux-specific headers/implementations in `netdrv_ethtool.c`, `netslot_linux.c`, and `netsys_linux.c` with `#if defined(__linux)` and provide portable fallbacks so they compile cleanly on all targets.
  - Add `netdrv_ethtool.c`, `netslot_linux.c`, and `netsys_linux.c` to `COMMON_SRC` in `src/Makefile.am` and fix the `libcompat.ap` typo to `libcompat.a`.
- [x] **A.2 Expose Active CPU Telemetry in OMNI Selectors (`src/nettest_bsd.h`, `src/nettest_omni.c`, `src/netcpu_procstat.c`, `dev/catalog/output-presets/cpu.out`)**:
  - Add `active_cpu_util` and `active_cpu_count` to `struct omni_results_struct` (`OMNI_RESULTS_CONV_CUTOFF` updated from `27` to `29`).
  - Add `LOCAL_CPU_ACTIVE_UTIL`, `LOCAL_CPU_ACTIVE_COUNT`, `REMOTE_CPU_ACTIVE_UTIL`, and `REMOTE_CPU_ACTIVE_COUNT` to `src/nettest_omni.c` and `dev/catalog/output-presets/cpu.out`.
  - Align active CPU threshold in `src/netcpu_procstat.c` and `src/netlib.h` to `>= 5.0f` (`5.0%`) and change peak comparison to strict `>` so idle CPUs default to `peak_cpu_id = 0`.

### Phase B: Python CLI Tools Fixes (`dev/tools/`)
- [x] **B.1 `netperf_topology.py`**:
  - Align `select_layout_strategy()` and `get_bkm_parameters()` with `netperf_tuner.py` (`spread_l2` and `rx_ring=4096, tx_ring=512` for E-core; `spread_step2` and `rx_ring=4096, tx_ring=2048` for P-core).
- [x] **B.2 `netperf-multi`**:
  - Add `--bkm {auto,cwf-ecore,gnr-pcore,mtu1500}` option to automatically select the matching core layout strategy.
- [x] **B.3 `netserver_manager.py`**:
  - Add `--action {start,stop,verify,plan}` and `-n / --count` CLI options in `argparse` alongside existing flags; use `self.netserver_path` consistently in `plan_pool()`.
- [x] **B.4 `netperf_preflight.py`**:
  - Wire `-H / --host`, `--streams`, `--warmup-runs`, `--min-gbps`, `--lp-state`, and `--save-state` into `main()`.
- [x] **B.5 `netperf_catalog.py`**:
  - Add `-s` short option for `--suite`.
  - Parse `proc.stdout` JSON/text in live runs to populate `tput_gbps`, `tx_gbps`, `rx_gbps`, and `cv_pct`.
  - Fix `_build_core_locality()` to use per-core port `self.base_port + core` and distinct fallback core for `LOC-CROSS-NUMA`.
  - Add `pre_commands` (`ethtool -G` and `ethtool -C`) to `_build_ring_coalesce_matrix()` and execute them in live runs.
- [x] **B.6 `netperf-orchestrate`, `netperf-profile`, and `netperf-monitor`**:
  - Resolve `--profile` in `netperf-orchestrate` `main()` using `dev/profiles/<profile>.yaml`.
  - Add `--export` alias for `--save-results` in `netperf-profile`.
  - Fix `-l` placement in `netperf-monitor` examples.

### Phase C: Documentation & Wiki Alignment (`dev/docs/`, `wiki/`, `README.md`)
- [x] **C.1 `dev/docs/TECHNICAL_WHITE_PAPER.md` & `wiki/Technical-White-Paper.md`**:
  - Align `AA-001`–`AA-024` table with `netperf_preflight.py`.
  - Align `cwf-ecore` and `gnr-pcore` ring/coalesce tables with `netperf_tuner.py` (`rx_ring=4096`, `adaptive-rx off`, `rx-usecs 10`, `tx-usecs 20`).
  - Fix CLI invocations (`--export` instead of `-o <file.json>`, `-l` before `--`, `-Z` documented as OMNI test-specific flag) and `netperf-aggregate --compare` JSON output example.
- [x] **C.2 `wiki/_Sidebar.md`, `wiki/Home.md`, `wiki/CLI-Tools-Reference.md`, `README.md`, `dev/docs/EXECUTIVE_SUMMARY.md`, `wiki/Executive-Summary.md`**:
  - Fix all section anchor links in `wiki/_Sidebar.md`.
  - Fix CLI examples in `wiki/Home.md`, `wiki/CLI-Tools-Reference.md`, and `README.md`.
  - Update profile count (`15`) and wiki guide count (`9`) and remove corrupted character in `README.md`.
