# Test Profiles and Qualification Catalog

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-WIKI-TEST-PROFILES-AND-Q` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Test Profiles and Qualification Catalog under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


`netperf_copilot` provides two complementary layers for structured testing:

1. **15 Built-In YAML Profiles (`dev/profiles/`)** run via `netperf-profile`
2. **4 Standardized Qualification Suites (`dev/tools/netperf_catalog.py`)** run via `netperf-catalog`

---

## 1. Built-In YAML Profiles (`dev/profiles/`)

Run any profile with:
```bash
./dev/tools/netperf-profile -p <profile_name> -H <target_ip> [--dry-run]
```

### High-Speed 200GbE–600GbE & OCP Qualification Profiles (v2.0)

| Profile Name | Target Scenario | Streams & Direction / Key Settings |
| --- | --- | --- |
| **`200g-ecore`** | Intel 200GbE 200GbE on Intel® Xeon® 6 Shared-L2 E-Core E-Core (`Xeon E-Core`) | 1, 8, 16, 32 TX; 16 RX; 16 BX<br>**Key Settings**: `mtu: 9000`, `layout: spread_l2`, `per_core_netserver: true`, `tx_ring: 512`, `message_size: 65536` |
| **`200g-pcore`** | Intel 200GbE 200GbE on Xeon 6 Multi-Core P-Core P-Core (`Xeon P-Core`/`Xeon P-Core`) | 1, 8, 16 TX; 16 RX; 16 BX<br>**Key Settings**: `mtu: 9000`, `layout: spread_step2`, `per_core_netserver: true`, `tx_ring: 2048`, `nodelay: true` |
| **`3x200g-multiport`** | Aggregate 3x200GbE (600GbE Total) Multi-network adapter / Multi-NUMA | 48 TX (16/network adapter), 48 RX (16/network adapter), 24 BX<br>**Key Settings**: `interfaces: "ens7np0,ens23np0,ens27np0"`, `layout: spread_l2`, `per_core_netserver: true` |
| **`200g-mtu1500-smallpkt`** | Standard MTU 1500 Small-Packet PPS & Tail-Latency RR | 1B TCP_RR, 16-flow 64B TCP_RR, 16-flow 16KB TCP_STREAM, 8-flow 64B UDP_STREAM<br>**Key Settings**: `mtu: 1500`, `layout: spread_step2`, `per_core_netserver: true`, `nodelay: true` |
| **`ocp-8x25g-lag-qos`** | OCP 8x25GbE Breakout & Active-Active LACP LAG + 4-TC DSCP QoS | 16 TX, 8 BX, 1 EF low-latency TCP_RR<br>**Key Settings**: `dscp: "EF,CS3,AF21,CS0"`, `layout: spread_step2`, `per_core_netserver: true` |

### General-Purpose Network Profiles

| Profile Name | Category | Description |
| --- | --- | --- |
| **`baseline`** | `baseline` | Quick 30s baseline: 1-flow TCP Send, TCP Recv, TCP RR (64B), and UDP Send (1472B) |
| **`throughput`** | `throughput` | 4-stream TCP Upload/Download (256KB socket, 64KB message) and 2-stream UDP |
| **`latency`** | `latency` | 1B, 64B, and 1KB TCP/UDP request-response latency characterization |
| **`datacenter`** | `datacenter` | 8-stream 10GbE/25GbE/100GbE line rate, East-West rack traffic, 4KB DB RR, and 1MB storage transfer |
| **`stress`** | `stress` | 300s sustained load: 32-stream TCP, 16-stream connection storm (`-c`), and 16-stream UDP flood |
| **`cloud`** | `cloud` | Virtualized/cloud VM network validation across small and medium payload sizes |
| **`jitter`** | `jitter` | Latency variation and inter-packet arrival stability benchmarking |
| **`lossy`** | `lossy` | Resilient TCP/UDP testing under simulated or WAN packet loss |
| **`wireless`** | `wireless` | High-RTT / variable-capacity wireless link characterization |
| **`mixed-workload`** | `mixed` | Bulk transfer + interactive RR + DB query RR + UDP streaming + `-c` API calls |

---

## 2. Qualification Catalog Suites (`netperf-catalog`)

`dev/tools/netperf_catalog.py` generates four deterministic test matrices designed for automated network adapter/driver
qualification:

### Suite 1: `flow-scaling` (42 Test Cases)
Sweeps `{1, 2, 4, 8, 16, 32, 64}` streams × `{tx, rx, bx}` directions × `{MTU 9000, MTU 1500}` using topology-aware core
layout (`spread_l2` on E-core, `spread_step2` on P-core) and per-core `netserver` ports.

- **Test Case IDs**: `FLOW-TX-1S-MTU9000` .. `FLOW-BX-64S-MTU1500`

### Suite 2: `core-locality` (4 Test Cases)
Isolates single-stream throughput sensitivity to CPU cache and NUMA placement:

- `LOC-SAME-CORE`: Application pinned to the exact Queue-0 IRQ core (measures softirq vs. user starvation)
- `LOC-SAME-L2`: Application pinned to an L2 module sibling of the Queue-0 IRQ core
- `LOC-LOCAL-NUMA`: Application pinned to a disjoint physical core on the network adapter's local NUMA node (optimal
  baseline)
- `LOC-CROSS-NUMA`: Application pinned to a remote NUMA node (measures cross-UPI / cross-mesh penalty)

### Suite 3: `ring-coalesce-matrix` (20 Test Cases)
Sweeps TX descriptor ring sizes `{512, 1024, 2048, 4096}` × interrupt moderation profiles
`{1us, 10us, 25us, 50us, adaptive}` at 16-stream 200GbE TX.

- **Test Case IDs**: `MATRIX-RING512-COAL-1US` .. `MATRIX-RING4096-COAL-ADAPTIVE`

### Suite 4: `lag-failover-qos` (2 Test Cases)
Validates Active-Active 802.3ad LACP 200GbE LAG with 4 DSCP traffic classes (`EF`, `CS3` , `AF21` , `CS0` ) under
steady-state TX (`LAG-ACTIVE-ACTIVE-4TC-TX`) and member link-down/up failover (`LAG-MEMBER-FAILOVER-RECOVERY`).

### Suite 5: Flent v3 Working-Latency (`RRUL`) & `net_dim` Burst Convergence (`netperf_flent_bridge.py`)
Pairs `OMNI` (`-M -- -J`), sub-second interim demo reporting (`-D 0.20`), disjoint CPU core pinning (`-T lcpu,rcpu`),
DiffServ markings (`-Y CS0/CS1/AF21/EF`), and `MSG_ZEROCOPY` (`-Z`) to export standard Flent v3 `.flent.gz` files for
`100GbE`–`400GbE` working-latency (`RRUL`) and `15s` step-burst convergence analysis (see
[FLENT_V3_WORKING_LATENCY_INTEGRATION.md](https://github.com/thehevy/netperf_copilot/blob/master/dev/docs/FLENT_V3_WORKING_LATENCY_INTEGRATION.md)).

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | wiki/Test-Profiles-and-<wbr>Qualification-Catalog.<wbr>md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet 200GbE`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-WIKI-TEST-PROFILES-AND-Q`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
