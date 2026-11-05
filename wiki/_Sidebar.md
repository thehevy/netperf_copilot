### 📖 Netperf Wiki

* **[🏠 Home](Home)**
* **[📊 Executive Summary](Executive-Summary)**
* **[📄 Technical White Paper](Technical-White-Paper)**
  * [Why Modernize Netperf?](Technical-White-Paper#1-introduction-the-100g800g-benchmarking-crisis)
  * [Legacy Bottlenecks](Technical-White-Paper#2-anatomy-of-legacy-bottlenecks-in-netperf-270)
  * [200G–600G Case Studies](Technical-White-Paper#7-empirical-results-case-studies--end-to-end-workflows)
* **[🚀 Getting Started & Installation](Getting-Started-and-Installation)**
  * [Build Profiles](Getting-Started-and-Installation#2-build-profiles)
  * [Verification Suite](Getting-Started-and-Installation#4-running-the-verification-suite)
* **[⚙️ Core C Engine & OMNI Guide](Core-Engine-and-OMNI-Guide)**
  * [Legacy vs. OMNI (`-M`)](Core-Engine-and-OMNI-Guide#1-two-operating-modes-legacy-vs-modern-omni--m)
  * [Output Formats & Presets](Core-Engine-and-OMNI-Guide#3-output-formats)
  * [Zero-Copy (`-Z`) & 4 MB Buffers](Core-Engine-and-OMNI-Guide#5-high-speed-c-engine-enhancements)
* **[⚡ 200G–800G & Multi-Core Guide](High-Speed-200G-800G-and-Xeon6-Guide)**
  * [P-Core vs. E-Core Topology](High-Speed-200G-800G-and-Xeon6-Guide#1-intel-xeon-6-architecture-e-core-vs-p-core)
  * [Per-Core `netserver` Pool](High-Speed-200G-800G-and-Xeon6-Guide#2-eliminating-the-3-classic-netserver-bottlenecks)
  * [Multi-NIC & DSCP Recipes](High-Speed-200G-800G-and-Xeon6-Guide#4-high-speed-multi-stream--multi-nic-recipes)
* **[🛠️ CLI Tools Reference](CLI-Tools-Reference)**
  * [`netperf-multi`](CLI-Tools-Reference#1-netperf-multi--parallel-multi-stream--multi-nic-engine)
  * [`netserver-manager`](CLI-Tools-Reference#2-netserver-manager--per-core-daemon-pool-manager)
  * [`netperf-preflight` & `netperf-tuner`](CLI-Tools-Reference#3-netperf-preflight--24-rule-anti-affinity--sanity-gate)
  * [`netperf-catalog` & `netperf-profile`](CLI-Tools-Reference#5-netperf-catalog--4-suite-qualification-runner)
  * [`netperf-orchestrate` & `netperf-monitor`](CLI-Tools-Reference#7-netperf-orchestrate--multi-host-ssh-coordinator)
* **[📋 Profiles & Qualification Catalog](Test-Profiles-and-Qualification-Catalog)**
  * [15 Built-In YAML Profiles](Test-Profiles-and-Qualification-Catalog#1-built-in-yaml-test-profiles-devprofiles)
  * [4 Qualification Catalog Suites](Test-Profiles-and-Qualification-Catalog#2-qualification-catalog-suites-netperf-catalog)
* **[🛡️ Pre-Flight & Fault Monitoring](Pre-Flight-Checks-and-Fault-Monitoring)**
  * [24 Anti-Affinity Rules (`AA-001`–`AA-024`)](Pre-Flight-Checks-and-Fault-Monitoring#1-the-24-feature-anti-affinity-rules-aa-001aa-024)
  * [Kernel & NIC Fault Gate (`U1`–`U13`)](Pre-Flight-Checks-and-Fault-Monitoring#4-kernel-dmesg--ethtool--s-fault-monitoring-u1u13)
