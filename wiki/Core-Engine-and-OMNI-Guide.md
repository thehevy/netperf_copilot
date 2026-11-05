# Core C Engine and OMNI Guide

This page documents the C engine enhancements in `src/` and how to use the `-M` OMNI test framework, structured output formats (`JSON`, `CSV`, `KEYVAL`, `HUMAN`), output presets, and high-speed socket options.

---

## 1. Backwards Compatibility vs. Modern OMNI Mode (`-M`)

To preserve 100% compatibility with existing benchmarks and scripts:
- **Without `-M`**: `netperf -H <host>` runs classic `TCP_STREAM` with traditional columnar output.
- **With `-M`** (or `-t OMNI`): Enables the unified OMNI test engine with `KEYVAL` output by default and unlocks `-- -J` (JSON), `-- -o` (CSV), `-- -k` (KEYVAL), and `-- -O` (HUMAN).

> **Important Flag Ordering Rule (`src/netsh.c` vs `src/nettest_omni.c`)**:
> - **Global flags** MUST appear **before** `--`:
>   `-H <host>`, `-L <local_ip>`, `-p <control_port>`, `-M` (or `-t <test>`), `-l <duration>`, `-T <local_cpu>[,<remote_cpu>]`, `-Y <local_tos>,<remote_tos>`, `-D <interval>`, `-c`, `-C`
> - **Test-specific OMNI flags** MUST appear **after** `--`:
>   `-d <stream|maerts|rr>`, `-T <tcp|udp|sctp>`, `-J [preset]`, `-o [preset]`, `-k [preset]`, `-O [preset]`, `-m <send_size>`, `-s <sock_buf>`, `-S <remote_sock_buf>`, `-r <req>,<rsp>`, `-b <burst>`, `-P <data_port>`, `-q <pacing_rate>`, `-D` (`TCP_NODELAY`), `-Z` (`MSG_ZEROCOPY`)

---

## 2. Output Formats (`-J`, `-o`, `-k`, `-O`)

### Key-Value (`-k`, Default with `-M`)
```bash
netperf -H 192.168.10.2 -M -l 10 -- -d stream -m 65536
```
Output:
```ini
THROUGHPUT=48921.34
THROUGHPUT_UNITS=10^6bits/s
ELAPSED_TIME=10.00
PROTOCOL=TCP
DIRECTION=Send
```

### Enhanced JSON (`-J`)
`netperf -M -- -J` emits a valid, RFC 8259-escaped JSON document containing both a `"metadata"` object (timestamps, hostname, interface telemetry, active/peak CPU utilization, softirq percentage) and a `"results"` object:

```bash
NETPERF_INTERFACE=ens801f0np0 netperf -H 192.168.10.2 -M -l 10 -c -C -- -d stream -m 65536 -J
```
Output:
```json
{
  "metadata": {
    "timestamp": "2026-11-05T19:30:00Z",
    "netperf_version": "2.7.1",
    "hostname": "dut-cwf-01",
    "test_name": "OMNI",
    "interface": "ens801f0np0",
    "driver": "ice",
    "firmware": "4.70 0x80020543",
    "bus_info": "0000:8a:00.0",
    "link_speed_mbps": 200000,
    "local_active_cpu_util": 38.42,
    "remote_active_cpu_util": 35.10,
    "local_active_cpu_count": 2,
    "remote_active_cpu_count": 2,
    "local_peak_cpu_id": 4,
    "remote_peak_cpu_id": 4,
    "local_peak_cpu_util": 64.20,
    "remote_peak_cpu_util": 58.90,
    "local_softirq_pct": 12.15,
    "remote_softirq_pct": 18.40
  },
  "results": {
    "THROUGHPUT": 35420.18,
    "THROUGHPUT_UNITS": "10^6bits/s",
    "ELAPSED_TIME": 10.00,
    "LOCAL_CPU_UTIL": 0.27,
    "REMOTE_CPU_UTIL": 0.24
  }
}
```

### CSV (`-o`) and Columnar Human (`-O`)
```bash
# CSV output
netperf -H 192.168.10.2 -M -l 10 -- -d stream -o

# Human-readable columnar table
netperf -H 192.168.10.2 -M -l 10 -- -d stream -O
```

---

## 3. Built-In Output Presets (`dev/catalog/output-presets/`)

You can pass a preset name directly to `-k`, `-J`, `-o`, or `-O` without needing the full file path or `.out` suffix:

| Preset Name | File | Description |
| :--- | :--- | :--- |
| `default` | `default.out` | Balanced set of 20 throughput, socket, MSS, CPU, and transport fields (loaded automatically by `-M`) |
| `minimal` | `minimal.out` | Core throughput, units, elapsed time, protocol, and direction (5 fields) |
| `throughput` | `throughput.out` | Bandwidth, socket buffers, message size, MSS, and byte/send counters |
| `latency` | `latency.out` | `RT_LATENCY`, `MEAN_LATENCY`, `MIN_LATENCY`, `MAX_LATENCY`, `P50`/`P90`/`P99_LATENCY`, `STDDEV_LATENCY`, and `TRANSACTION_RATE` |
| `cpu` | `cpu.out` | Local/remote CPU utilization, service demand (`SD_TIME`), and CPU model/frequency |
| `verbose` | `verbose.out` | Comprehensive 45+ field diagnostic dump including PCIe slot, driver, and UUID |

Examples:
```bash
netperf -H 192.168.10.2 -M -l 10 -- -d stream -J throughput
netperf -H 192.168.10.2 -M -l 10 -- -d rr -r 64,64 -J latency
```

---

## 4. High-Speed C Engine Enhancements (`src/`)

1. **4 MB Maximum Message Size (`src/netlib.h`)**:
   - `MAXMESSAGESIZE` is `4194304` (4 MB), enabling `-m 65536` through `-m 4194304` for 200G–800G bulk transfers.
2. **Zero-Copy Transmit (`-- -Z` in `src/nettest_omni.c`)**:
   - Enables `SO_ZEROCOPY` on the data socket and passes `MSG_ZEROCOPY` to `send()` / `sendto()`.
   - Automatically drains completion notifications from `MSG_ERRQUEUE` (`drain_zerocopy_completions()`) every 32 sends and on `ENOBUFS`/`ENOMEM` so socket `optmem_max` never deadlocks on long 200GbE runs.
3. **High-Core-Count CPU Telemetry (`src/netcpu_procstat.c`)**:
   - On 288-core Clearwater Forest or 256-thread Granite Rapids systems, whole-machine `LOCAL_CPU_UTIL` for a single pinned stream is `< 0.5%`.
   - `netcpu_procstat.c` now tracks **active-core CPU utilization** (`active_cpu_util` across cores with `>= 5%` busy time), **peak core ID & utilization** (`peak_cpu_id`, `peak_cpu_util`), and **softirq percentage** (`softirq_pct`).
4. **Modern Linux Hardware & Link Discovery (`src/netslot_linux.c`, `src/netsys_linux.c`, `src/netdrv_ethtool.c`)**:
   - Uses `ETHTOOL_GLINKSETTINGS` (32-bit `speed`) so 100GbE (`100000`), 200GbE (`200000`), 400GbE (`400000`), and 800GbE (`800000`) links are never truncated at 65535 Mbps.
   - Reads PCIe BDF, NUMA node, `current_link_speed` (`32.0 GT/s PCIe`), and `current_link_width` (`x16`) directly from `/sys/class/net/<if>/device/`.
   - Reads DMI system vendor/product from `/sys/class/dmi/id/` and CPU frequency from `cpufreq/scaling_cur_freq` without requiring external `libsmbios`.
