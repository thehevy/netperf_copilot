# Pre-Flight Checks and Fault Monitoring

High-speed 200G–800G qualification requires strict pre-test configuration hygiene and zero-tolerance post-test kernel/hardware fault verification.

---

## 1. The 24 Feature Anti-Affinity Rules (`netperf-preflight`)

`dev/tools/netperf_preflight.py` evaluates live system state (or a state snapshot) against 24 hardware, topology, and driver anti-affinity rules (`AA-001` through `AA-024`):

| Rule ID | Severity | Feature A vs. Feature B | Description & Remediation |
| :--- | :---: | :--- | :--- |
| **`AA-001`** | `FAIL` | `adq` vs `rocev2` | ADQ (`tc-mqprio hw 1`) and RoCEv2 (`irdma`) cannot coexist on the same PF. Remove `mqprio` or unload `irdma`. |
| **`AA-002`** | `FAIL` | `adq` vs `dcb_pfc_ets` | ADQ hardware traffic classes conflict with IEEE DCB PFC/ETS scheduler. |
| **`AA-003`** | `FAIL` | `adq` vs `sriov_vf` | ADQ cannot be enabled concurrently with SR-IOV Virtual Functions (`sriov_numvfs > 0`). |
| **`AA-004`** | `FAIL` | `adq` vs `active_active_lag` | ADQ hardware queue sets cannot be bound across bonded LACP LAG ports. Use RSS + XPS. |
| **`AA-005`** | `FAIL` | `adq` vs `xdp` | ADQ hardware traffic classes conflict with XDP / `AF_XDP` zero-copy queues. |
| **`AA-006`** | `WARN` | `adq` vs `eol_notice` | Intel ADQ reached EOL in April 2025; migrate to `netperf-tuner --apply-bkm auto` (RSS + XPS + 5-layer scheduler). |
| **`AA-007`** | `FAIL` | `rocev2` vs `sriov_lag` | RoCEv2 (`irdma`) over SR-IOV VF LAG is unsupported when `switchdev` eswitch mode is active. |
| **`AA-008`** | `FAIL` | `rocev2` vs `mtu_mismatch` | RoCEv2 active QPs suffer severe packet drop when PF MTU < IB QP path MTU. |
| **`AA-009`** | `FAIL` | `dcb_pfc` vs `link_pause` | IEEE 802.1Qbb PFC cannot be enabled simultaneously with IEEE 802.3x Global Flow Control (`ethtool -A rx off tx off`). |
| **`AA-010`** | `WARN` | `xps_cpus` vs `xps_rxqs_conflict` | Having both `xps_cpus != 0` and `xps_rxqs != 0` degrades TX queue selection on E835. Clear `xps_cpus=0`. |
| **`AA-011`** | `WARN` | `adaptive_coalesce` vs `deterministic_benchmark` | Adaptive RX/TX moderation causes bimodal variance across 30s runs. Set `adaptive-rx off adaptive-tx off rx-usecs 10 tx-usecs 20`. |
| **`AA-012`** | `FAIL` | `irqbalance` vs `manual_irq_pinning` | Running `irqbalance` overwrites manual SMP IRQ affinity masks mid-test. Stop `irqbalance`. |
| **`AA-013`** | `WARN` | `numa_balancing` vs `pinned_netperf` | Kernel automatic NUMA balancing migrates memory pages during pinned runs (`sysctl -w kernel.numa_balancing=0`). |
| **`AA-014`** | `WARN` | `busy_poll` vs `high_stream_ecore` | `busy_poll > 0` on E-core 32–64 stream tests starves softirq. Set `busy_poll=0` for bulk throughput. |
| **`AA-015`** | `FAIL` | `tx_ring_256` vs `200g_line_rate` | Default `ice` TX ring (`256`) causes `tx_restart_queue` stalls at 100G/200G. Increase TX ring `>= 512`. |
| **`AA-016`** | `FAIL` | `p0_irq_cross_numa` vs `local_numa_affinity` | Queue 0 / Vector 0 IRQ pinned to a remote NUMA node degrades 1–8 stream throughput by 30–55%. |
| **`AA-017`** | `FAIL` | `pcie_bw_bottleneck` vs `line_rate_target` | PCIe effective BW (`Speed * Width * 128/130`) is below NIC link speed. Check riser/slot bifurcation. |
| **`AA-018`** | `FAIL` | `powersave_governor` vs `high_speed_netperf` | CPU scaling governor `powersave`/`ondemand` causes P-state ramp lag (`cpupower frequency-set -g performance`). |
| **`AA-019`** | `WARN` | `gro_off` vs `200g_tcp_rx` | Disabling GRO on 100G/200G TCP RX limits single-core RX throughput (`ethtool -K <if> gro on`). |
| **`AA-020`** | `WARN` | `tso_off` vs `200g_tcp_tx` | Disabling TSO on 100G/200G TCP TX increases CPU service demand by 3–5x (`ethtool -K <if> tso on`). |
| **`AA-021`** | `WARN` | `ecore_smt_assumption` vs `cwf_srf_topology` | Assuming SMT siblings on E-core (CWF/SRF) misaligns L2 4-core modules. Use `spread_l2`. |
| **`AA-022`** | `WARN` | `shared_netserver_lock` vs `high_stream_count` | Using a single `netserver` daemon on port 12865 for `>= 16` streams serializes control accepts. Use `netserver-manager`. |
| **`AA-023`** | `WARN` | `small_rmem_wmem` vs `high_bdp_200g` | Default `rmem_max`/`wmem_max` (`212992`) throttles TCP window scaling at 100G–800G. Set to `2147483647`. |
| **`AA-024`** | `INFO` | `tx_sched_9layer` vs `low_latency_200g` | Default 9-layer `ice` TX scheduler adds burst latency compared to 5-layer `devlink` `tx_scheduling_layers=5`. |

---

## 2. Warmup Sanity Gate & DUT↔LP Swap Isolation

`PreflightChecker` also provides two diagnostic gates:
- **5-Iteration Warmup Sanity Gate (`evaluate_warmup_stability()`)**: Runs 5 × 10s single-flow warmup iterations and fails (`WARMUP-BIMODAL`) if the Coefficient of Variation (`CV`) exceeds **5.0%**, catching unpinned IRQs or `netserver` collisions before a long qualification suite starts.
- **DUT↔LP Directional Swap Check (`evaluate_dut_lp_swap()`)**: Compares forward (`DUT -> LP`) vs. reverse (`LP -> DUT`) TX throughput and flags `SWAP-ASYMMETRY` if directional asymmetry exceeds **15%**, isolating sender TX ring limits from receiver GRO/IRQ bottlenecks.

---

## 3. `U1`–`U13` Kernel & Driver Fault Gate (`netperf_report.py`)

When running `netperf-multi --check-kmsg` or generating reports with `AIValidationReporter`, `dmesg -T` and `ethtool -S` are scanned before and after every test run for 13 fatal/unexpected event signatures:

| Code | Category | Signature Pattern |
| :--- | :--- | :--- |
| **`U1`** | `kernel_oops_bug` | `BUG:`, `Oops:`, `Kernel panic`, `general protection fault` |
| **`U2`** | `pcie_aer_error` | `AER:`, `PCIe Bus Error`, `Uncorrectable.*Error` |
| **`U3`** | `netdev_watchdog` | `NETDEV WATCHDOG:.*transmit queue \d+ timed out` |
| **`U4`** | `ice_tx_hang_mdd` | `ice.*(Malicious Driver Detection\|Tx hang\|FW reset\|EMP reset\|rebuild failed)` |
| **`U5`** | `irdma_qp_error` | `irdma.*(Async Event\|AE_.*ERROR\|QP fatal\|CQP timeout)` |
| **`U6`** | `link_flap` | `NIC Link is Down`, `carrier lost` |
| **`U7`** | `page_alloc_failure` | `page allocation failure:`, `Out of memory:` |
| **`U8`** | `cpu_soft_lockup` | `watchdog: BUG: soft lockup`, `rcu_sched self-detected stall` |
| **`U9`** | `mce_hardware_error` | `Machine check events logged`, `Hardware Error:` |
| **`U10`** | `lacp_bond_flap` | `bond\d+:.*(link status definitely down\|LACP.*timeout)` |
| **`U11`** | `pfc_storm_watchdog` | `PFC storm`, `pfc_watchdog` |
| **`U12`** | `thermal_throttle` | `Package temperature above threshold`, `cpu clock throttled` |
| **`U13`** | `irq_nobody_cared` | `irq \d+: nobody cared` |

Any match in `U1`–`U13` or any non-zero `rx_crc_errors` / `tx_errors` delta automatically flips the test `verdict` to **`FAIL`** and records the exact offending `dmesg` lines in `result.json`.
