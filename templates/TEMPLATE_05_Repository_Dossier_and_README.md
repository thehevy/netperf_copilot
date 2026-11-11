# Repository Executive Dossier & Project `README.md` Template (`Diátaxis Overview`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-DOSSIER-README-005` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Repository Overview Dossiers and Project Root `README.md` Files
- **Summary**: Canonical repository overview and `README.md` template for high-speed networking and benchmark repositories under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> **One-Line Summary**: Concise `1`-sentence statement of the repository's engineering purpose, target network speeds
> (`100GbE`–`800GbE`), and primary deliverables.

| Field | Value |
| --- | --- |
| **Repository** | [netperf_copilot](https://github.com/thehevy/netperf_copilot) |
| **Category** | Open-Source Network Performance Benchmarking & Automation |
| **Strategic Theme** | High-Speed `100GbE`–`800GbE` Benchmarking, Topology-Aware Pinning & AI Validation |
| **Status** | **Active — Production Validated (`100/100` `D1`–`D10` v3.2 Compliance)** |
| **Current Focus** | Summarize the active milestone, hardware qualification suites, and verification gate. |
| **Target Audience / Use Case** | Linux Network Engineers, Performance Architects, Automated Validation Pipelines |
| **Last Updated (GitHub Push)** | `2026-11-09` |

---

## 1. Quick Share Block (Copy-Paste for Co-workers / Teams / Email)

> Copy the block below to share this repository's purpose and status:

```markdown
**<Repository Name> — <Short Engineering Subtitle>** (`<owner>/<repo>`)
- **What it is**: 1-sentence overview of the repository and its high-speed networking scope.
- **Key Capabilities**:
  1. **Capability 1**: Summarize core C engine enhancements (`4` MB buffers, `MSG_ZEROCOPY`, active CPU telemetry).
  2. **Capability 2**: Summarize topology-aware Python orchestration (`netperf-multi`, `netperf_topology.py`, `netperf_preflight.py`).
  3. **Capability 3**: Summarize automated qualification suites (`netperf_catalog.py`) and structured `result.json` reporting.
- **Repo Link**: https://github.com/<owner>/<repo>
```

---

## 2. Executive Summary

Write `2` concise paragraphs (`<= 25` words per sentence, `>= 90%` active voice) explaining the engineering problem this
repository solves for `100GbE`–`800GbE` network adapters and multi-core Linux servers, and how its C engine and Python
automation tools work together.

---

## 3. Key Technical Insights & Repository Layout (`3`-Column Zero-Scroll Table)

Use a `3`-column table with short basename links (`<= 28` characters) to document the repository's key modules:

| Component & Basename Link | Role & Architectural Responsibility | CLI Entrypoint & Validation Gate |
| --- | --- | --- |
| **Core Validator**<br>[markdown_validator.py](../scripts/markdown_validator.py) | Enforces `D1`–`D10` `v3.2`, `<= 120`-column line wrapping (`MD013`), list indent (`MD007`), and `<= 3–4` column tables (`D5-COLS`). | `python scripts/markdown_validator.py . --fix`<br>Score: `100/100` (`0` violations) |
| **Topology Engine**<br>[netperf_topology.py](../dev/tools/netperf_topology.py) | Discovers NUMA nodes, SMT siblings, L2 cache modules, PCIe 5.0/6.0 effective bandwidth, and disjoint IRQ/App core pools. | `python dev/tests/test_modernization.py` |

---

## 4. Plans & Next Steps (Roadmap)

- [ ] **Milestone 1**: Describe the next concrete engineering deliverable with a measurable verification gate.
- [ ] **Milestone 2**: Describe the planned hardware validation sweep (`flow-scaling`, `core-locality`, `DMAR=0`).
- [ ] **Milestone 3**: Describe documentation and GitHub Wiki synchronization gates.

---

## 5. Activity & Repository Snapshot

<!-- AUTO-SYNC-ACTIVITY:START -->
- **Last Activity**: `2026-11-09` | **Default Branch**: `master` (1 branch: `master`)
- **Languages / Stack**: C, Python, Bash, Markdown | **Tracked Files**: `100`

### Recent Commits

| Date & Commit | Author | Commit Summary |
| --- | --- | --- |
| `2026-11-09` · `a1b2c3d4` | `thehevy` | Enforce `D1`–`D10` `v3.2` templates, `<= 120`-col wrapping (`MD013`), and `D7-ID-MATCH` |
<!-- AUTO-SYNC-ACTIVITY:END -->

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_05_Repository_<wbr>Dossier_and_README.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Repository Dossier Template`, `Project README Template`, `Diataxis Overview`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `Linux networking`, `netperf_copilot`, `markdown_validator.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-DOSSIER-README-005`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
