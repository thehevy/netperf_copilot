### 📖 Netperf Wiki

* **[🏠 Home](Home)**
* **[📊 Executive Summary](Executive-Summary)**
* **[📄 Technical White Paper](Technical-White-Paper)**
  * [Why Modernize Netperf?](Technical-White-Paper#1-introduction-the-100g800g-benchmarking-crisis)
  * [Legacy Bottlenecks](Technical-White-Paper#2-anatomy-of-legacy-bottlenecks-in-netperf-270)
  * [200G–600G Case Studies](Technical-White-Paper#7-empirical-results-case-studies--end-to-end-workflows)
* **[🚀 Getting Started & Installation](Getting-Started-and-Installation)**
  * [Building From Source](Getting-Started-and-Installation#2-building-from-source)
  * [Verifying Your Installation](Getting-Started-and-Installation#4-verifying-your-installation)
* **[⚙️ Core C Engine & OMNI Guide](Core-Engine-and-OMNI-Guide)**
  * [Legacy vs. OMNI (`-M`)](Core-Engine-and-OMNI-Guide#1-backwards-compatibility-vs-modern-omni-mode--m)
  * [Output Formats & Presets](Core-Engine-and-OMNI-Guide#2-output-formats--j--o--k--o)
  * [Zero-Copy (`-Z`) & 4 MB Buffers](Core-Engine-and-OMNI-Guide#4-high-speed-c-engine-enhancements-src)
* **[⚡ 200G–800G & Multi-Core Guide](High-Speed-200G-800G-and-Xeon6-Guide)**
  * [P-Core vs. E-Core Topology](High-Speed-200G-800G-and-Xeon6-Guide#1-intel-xeon-6-p-core-vs-e-core-topology-strategies)
  * [Per-Core `netserver` Pool](High-Speed-200G-800G-and-Xeon6-Guide#2-eliminating-the-3-load-partner-netserver-bottlenecks)
  * [Multi-NIC & DSCP Recipes](High-Speed-200G-800G-and-Xeon6-Guide#4-bidirectional-bx-multi-nic-600g-and-ocp-8x25g-breakout-workflows)
* **[🛠️ CLI Tools Reference](CLI-Tools-Reference)**
  * [`netperf-multi`](CLI-Tools-Reference#1-netperf-multi--multi-instance-multi-port--directional-runner)
  * [`netserver-manager`](CLI-Tools-Reference#2-netserver-manager--per-core-pinned-netserver-pool-manager)
  * [`netperf-preflight` & `netperf-tuner`](CLI-Tools-Reference#3-netperf-preflight--24-rule-hardware--driver-pre-flight-checker)
  * [`netperf-catalog` & `netperf-profile`](CLI-Tools-Reference#5-netperf-catalog--qualification-test-matrix-generator--runner)
  * [`netperf-orchestrate` & `netperf-monitor`](CLI-Tools-Reference#7-netperf-orchestrate--multi-host-ssh--rocev2-co-orchestrator)
* **[📋 Profiles & Qualification Catalog](Test-Profiles-and-Qualification-Catalog)**
  * [15 Built-In YAML Profiles](Test-Profiles-and-Qualification-Catalog#1-built-in-yaml-profiles-devprofiles)
  * [4 Qualification Catalog Suites](Test-Profiles-and-Qualification-Catalog#2-qualification-catalog-suites-netperf-catalog)
* **[🛡️ Pre-Flight & Fault Monitoring](Pre-Flight-Checks-and-Fault-Monitoring)**
  * [24 Anti-Affinity Rules (`AA-001`–`AA-024`)](Pre-Flight-Checks-and-Fault-Monitoring#1-the-24-feature-anti-affinity-rules-netperf-preflight)
  * [Kernel & NIC Fault Gate (`U1`–`U13`)](Pre-Flight-Checks-and-Fault-Monitoring#3-u1u13-kernel--driver-fault-gate-netperf_reportpy)
