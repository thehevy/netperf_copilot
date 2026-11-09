---
description: Ground all tuning, validation, debug, driver development, and documentation work in the Centralized Knowledge Base (kb/)
trigger: always_on
---

# Centralized Knowledge Base (`kb/`) Grounding & Branding Rule

1. **Always Consult `kb/` First**:
   - Before generating tuning scripts, switch configs, driver patches, white papers, or validation tests, consult
     `kb/INDEX.md` or run `python scripts/kb_query.py search "<topic>"`.
2. **Enforce Intel® Ethernet Branding (`D1`–`D4` v2.1)**:
   - Follow `kb/documentation/intel_ethernet_branding_and_parameter_standards.md`: use **Intel® Ethernet 800 Series**,
     **Intel® Ethernet Controller E835**, **Intel® Ethernet Network Adapter E835-CC**, and **Intel® Xeon® 6 Processor**
     on first mention, and parameterize shell snippets with `${NETDEV}`, `${PORT0}`, `${PORT1}`, and `${PCI_DEV}`.
