---
description: "Mandatory inclusion of all active non-default system, kernel, driver, and NIC tunings and values in all benchmark test results"
trigger: always_on
---

# Mandatory Non-Default Tunings & Values in Test Results

Across **all `netperf_copilot` benchmarks, qualification suites, A/B parameter sweeps, and generated reports**:

1. **Always Capture Active Non-Default Tunings With Every Test Result**:
   - Whenever emitting `result.json`, `netperf-multi --export` JSON payloads, `--sweep` reports, or Markdown qualification
     dashboards (`AIValidationReporter`), probe and record every runtime tuning parameter that differs from baseline
     Linux/driver defaults alongside its exact measured value and baseline default.
   - Record **measured** host state rather than trusting requested CLI/BKM profile flags alone.
2. **Minimum Required Non-Default Tuning Scope**:
   - **Network & Kernel Sysctls**: Diff active sysctls (`net.ipv4.tcp_notsent_lowat`, `tcp_limit_output_bytes`, `tcp_rmem`,
     `tcp_wmem`, `tcp_mem`, `tcp_congestion_control`, `tcp_mtu_probing`, `tcp_slow_start_after_idle`, `tcp_fastopen`,
     `ip_forward`, `net.core.rmem_max`, `wmem_max`, `netdev_max_backlog`, `netdev_budget`, `netdev_budget_usecs`,
     `gro_normal_batch`, `busy_poll`, `busy_read`, `default_qdisc`, `kernel.numa_balancing`, `vm.swappiness`) against Linux
     defaults and record `{value, default}` for every non-default setting.
   - **Kernel Cmdline & CPU/IRQ State**: Record relevant `/proc/cmdline` flags (`iommu=pt`, `isolcpus`, `nohz_full`,
     `rcu_nocbs`, `idle`, `mitigations`), CPU `scaling_governor`, `irqbalance` service state, and driver module parameters.
   - **Interface & Link-Layer Settings (`ethtool` / `tc` / `sysfs`)**: Record non-default `MTU` (`!= 1500`), combined
     channels, RX/TX ring sizes, interrupt coalescing (`adaptive-rx`/`tx`, `rx-usecs`, `tx-usecs`), flow control,
     offloads (`lro`, `tso`, `gso`, `gro`), active root `tc qdisc`, `gso_max_size`, and XPS/IRQ steering configuration.
   - **Applied Tuning Profile & Workload Overrides**: Include applied `--apply-bkm` / `--sweep` settings, stream count,
     core-pinning mask/layout, and buffer/zero-copy flags (`-w`, `-Z`).
3. **Report Visibility**:
   - Include `non_default_tunings` in JSON artifacts (`result.json`, `netperf-multi --export`) and render a compact
     (`<= 4` columns, `| --- |`) non-default tunings table in generated Markdown dashboards whenever overrides are present.

---
