---
description: Ground all tuning, validation, debug, driver development, and documentation work in the Centralized Knowledge Base (kb/)
trigger: always_on
---

# Centralized Knowledge Base (`kb/`) Grounding & Branding Rule

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-AGENTS-RULES-KB-GROUNDING-RULE` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Centralized Knowledge Base (`kb/`) Grounding & Branding Rule under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


1. **Always Consult `kb/` First**:
   - Before generating tuning scripts, switch configs, driver patches, white papers, or validation tests, consult
     `kb/INDEX.md` or run `python scripts/kb_query.py search "<topic>"`.
2. **Enforce Intel® Ethernet Branding (`D1`–`D4` v2.1)**:
   - Follow `kb/documentation/intel_ethernet_branding_and_parameter_standards.md`: use **Intel® Ethernet 800 Series**,
     **Intel® Ethernet Controller E835**, **Intel® Ethernet Network Adapter E835-CC**, and **Intel® Xeon® 6 Processor**
     on first mention, and parameterize shell snippets with `${NETDEV}`, `${PORT0}`, `${PORT1}`, and `${PCI_DEV}`.

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `.agents/rules/kb-grounding-rule.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-AGENTS-RULES-KB-GROUNDING-RULE`, `DOC-NETPERF-AGENTS-RULE<wbr>S-KB-GROUNDING-RULE`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
