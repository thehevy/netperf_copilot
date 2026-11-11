# High-Speed 200GbE–800GbE and Intel® Xeon® 6 Guide

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-HIGH-SPEED-200GBE-800GBE` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for High-Speed 200GbE–800GbE and Intel Xeon 6 Guide under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


Achieving deterministic line rate at **200GbE (189–192 Gbps TCP goodput)**, **400GbE**, and **600GbE–800GbE multi-port**
on
modern **Intel® Xeon® 6 Processor** platforms requires aligning CPU microarchitecture, L2/LLC cache topology, network
adapter ring sizes, and
Load Partner (`netserver`) core pinning.

---

## 1. Intel® Xeon® 6 P-Core vs. E-Core Topology Strategies

`netperf_topology.py` automatically detects whether the host CPU is an **Intel Xeon 6 P-Core** (Multi-Core P-Core, or
earlier x86 P-Core generations) or an **Intel Xeon 6 E-Core** (Shared-L2 E-Core 288-core / 144-core E-Core) and applies
the optimal core layout:

| Platform / Microarchitecture | Core Architecture | Optimal Layout Strategy / Optimal `ice` TX Ring / Stream Sweet Spot (200GbE) |
| --- | --- | --- |
| **Xeon 6 Shared-L2 E-Core** (`Xeon 6 E-Core`) | E-Core (No SMT, 4 cores share 4 MB L2 module) | `spread_l2` (1–2 cores per 4-core L2 module before filling siblings)<br>**Optimal `ice` TX Ring**: **512** (`rx 4096`)<br>**Stream Sweet Spot (200GbE)**: **16 streams** (~35 Gbps/flow, ~189.4 Gbps aggregate) |
| **Xeon 6 Multi-Core P-Core** (`Xeon 6 P-Core`) | P-Core (2-way SMT, dedicated 2 MB L2 per core) | `spread_step2` (physical cores only, filtering SMT siblings >= 128)<br>**Optimal `ice` TX Ring**: **2048** (`rx 4096`)<br>**Stream Sweet Spot (200GbE)**: **8–16 streams** (~52 Gbps/flow, ~191.2 Gbps aggregate) |

### Why E-Core Needs `tx_ring=512` and `spread_l2`

- **L2 Cache Contention**: On Shared-L2 E-Core, 4 consecutive physical cores (`[0,1,2,3]`, `[4,5,6,7]`
  , ...) share a single L2 cache and L2-to-mesh interface. Packing 8 streams onto cores `0..7` saturates two L2 modules
  while leaving 34 other L2 modules idle. `spread_l2` round-robins across distinct 4-core L2 modules first (`0, 4, 8,
  12, ...`).
- **Descriptor Footprint**: Setting `tx_ring=512` on E-core keeps the active TX descriptor working set compact inside
  the shared L2 module while avoiding the `tx_restart_queue` stalls seen at the default `tx_ring=256` .

---

## 2. Eliminating the 3 Load Partner (`netserver`) Bottlenecks

In 200GbE+ qualification testing, the Load Partner (LP) running `netserver` is frequently the hidden bottleneck:

1. **Single-Port `accept()` Serialization**: Spawning 16–64 streams against a single `netserver -p 12865` daemon
   serializes control handshakes and risks socket lock contention (`AA-022`).
2. **IRQ / Application Core Collision**: If `netserver` lands on a core handling `ice` MSI-X interrupts (e.g., Queue 0 /
   Vector 0), throughput drops by **30–55%** and run-to-run variance spikes (`CV > 15%`).
3. **Cross-NUMA Memory Allocation**: If `netserver` forks without `--membind=<nic_numa>` , socket receive buffers
   allocate on a remote NUMA node across UPI/mesh links.

### Solution: `netserver-manager` Per-Core Pool (`18600 + core`)
Run `netserver-manager` on the Load Partner to launch one `numactl` -pinned `netserver` daemon per non-IRQ physical core
on the NIC's local NUMA node:

```bash
# Plan the pool (dry-run inspection)
./dev/tools/netserver-manager --plan -i ens801f0np0 --base-port 18600 --count 32

# Start the per-core pinned pool on the LP
./dev/tools/netserver-manager --start -i ens801f0np0 --base-port 18600 --count 32

# Verify running instances and confirm zero IRQ core collisions
./dev/tools/netserver-manager --verify -i ens801f0np0
```

Each instance on core `C` listens on port `18600 + C` . When `netperf-multi` runs with
`--per-core-netserver --base-port 18600` , each flow pinned to LP core `C` (`-T <dut_core>,<C>`) connects directly to
`-p $((18600 + C))` , guaranteeing zero post-fork CPU migration.

---

## 3. Automated Platform & `ice` Driver BKM Tuning (`netperf-tuner`)

Use `netperf-tuner` to apply all validated Intel 100GbE/200GbE (`ice`) and Linux kernel BKMs in one step:

```bash
# Preview the auto-detected BKM plan (ecore or pcore)
./dev/tools/netperf-tuner -i ens801f0np0 --apply-bkm auto --dry-run

# Apply the BKM plan on a live host
sudo ./dev/tools/netperf-tuner -i ens801f0np0 --apply-bkm auto
```

What `netperf-tuner` configures:

1. Stops `irqbalance` (`systemctl stop irqbalance`) and sets `cpupower frequency-set -g performance`.
2. Configures `devlink` parameters: `msix_vec_per_pf_max=65` and `tx_scheduling_layers=5` (5-layer TX scheduler).
3. Sets RSS combined channels (`ethtool -L <if> combined 32`).
4. Sets descriptor rings (`ethtool -G <if> tx 512 rx 4096` on E-core; `tx 2048 rx 4096` on P-core).
5. Disables adaptive interrupt coalescing for deterministic runs (`ethtool -C <if> adaptive-rx off adaptive-tx off
   rx-usecs 10 tx-usecs 20`).
6. Enables `tso on gso on gro on lro off` and sets `mtu 9000` (or `1500` with `--apply-bkm mtu1500`).
7. Clears `xps_cpus=0` and sets `xps_rxqs=ffff` across `/sys/class/net/<if>/queues/tx-*`.
8. Pins NIC IRQs to the local NUMA node (`set_irq_affinity_bynode.sh`).
9. Applies 2 GB socket buffer sysctls (`rmem_max=2147483647`, `wmem_max=2147483647` , `kernel.numa_balancing=0` ,
   `net.core.busy_poll=0` ).

---

## 4. Bidirectional (`bx`), Multi-Adapter (600GbE), and OCP 8x25GbE Breakout Workflows

### Simultaneous Bidirectional (`--direction bx`)
Allocates disjoint TX and RX physical cores so sender and receiver streams never contend on the same core or L2 module:
```bash
./dev/tools/netperf-multi -H 192.168.10.2 -i ens801f0np0 -t OMNI \
    --direction bx -n 16 -l 30 --affinity --per-core-netserver --base-port 18600 \
    -- -m 65536 -D
```

### Multi-Adapter Aggregate 3x200GbE (600GbE Total)
Distributes flows across 3 local 200GbE network adapters, automatically pinning each port's flows to that adapter's
local NUMA node:
```bash
./dev/tools/netperf-multi -H 192.168.10.2,192.168.20.2,192.168.21.2 \
    -i ens7np0,ens23np0,ens27np0 -t OMNI --direction tx -n 16 -l 30 \
    --affinity --per-core-netserver --base-port 18600 -- -m 65536 -D
```

### OCP 8x25GbE Multi-Subnet Breakout with 4-Traffic-Class DSCP QoS
Expands IP ranges (`192.168.10..17.74`) and round-robins symbolic DSCP markings (`EF`=`0xb8`, `CS3` =`0x60`, `AF21`
=`0x48`, `CS0` =`0x00`):
```bash
./dev/tools/netperf-multi -H 192.168.10..17.74 -t OMNI --direction tx -n 4 -l 30 \
    --dscp EF,CS3,AF21,CS0 --affinity --per-core-netserver --base-port 18600 \
    -- -m 65536 -D
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | wiki/High-Speed-200GbE-800<wbr>GbE-and-Xeon6-Guide.md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet 200GbE`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-HIGH-SPEED-200GBE-800GBE`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
