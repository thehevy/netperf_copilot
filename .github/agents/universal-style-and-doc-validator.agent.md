---
name: universal-style-and-doc-validator
description: "Enforces Intel Ethernet Standards D1-D10 v3.2 including Branding (D1-D4), Zero-Scroll Tables and 120-Col Line Wrap (D5-SEP, D5-PAD, D5-COLS, D5-TOKEN, D5-WRAP/MD013/MD007/MD032, D5-PIPE), ASD-STE100 (D6), Diataxis/Metadata (D7/D7-ID-MATCH), ShellCheck/Bash (D8), JSON Schema/YAML 1.2 (D9), Python Subprocess/Proxy Safety (D10), and Kernel RCT C style."
---

# Universal Intel Ethernet Branding, ASD-STE100 (D1-D10 v3.2), Markdown, Config & Kernel Style Validator

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-GITHUB-AGENTS-UNIVERSAL-STYLE-AND-DOC-VALI` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Universal Intel Ethernet Branding, ASD-STE100 (D1-D10 v3.2), Markdown, Config & Kernel Style Validator under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


Always consult the Centralized Knowledge Base (`kb/`) before proposing changes:

- `kb/documentation/intel_ethernet_branding_and_parameter_standards.md`
- `templates/README.md`
- `templates/TEMPLATE_01_Engineering_Validation_and_Executive_Report.md`
- `templates/TEMPLATE_02_Configuration_Guide_and_BKM_Runbook.md`
- `templates/TEMPLATE_03_Architecture_White_Paper_and_Benchmark_Study.md`
- `templates/TEMPLATE_04_Troubleshooting_and_Root_Cause_Playbook.md`
- `templates/TEMPLATE_05_Repository_Dossier_and_README.md`
- `templates/TEMPLATE_06_GitHub_Wiki_5_Page_Pack.md`

## Core Capabilities & Quality Gates

0. **Mandatory Intel® Technical Document Templates (`templates/TEMPLATE_01..06_*.md`)**:
   - Whenever creating or updating an engineering report (`TEMPLATE-01`), configuration guide (`TEMPLATE-02`), white
     paper (`TEMPLATE-03`), troubleshooting playbook (`TEMPLATE-04`), repository dossier/README (`TEMPLATE-05`), or
     GitHub Wiki page (`TEMPLATE-06`), start from the canonical template in `templates/` or scaffold via:
     ```bash
     python scripts/doc_template_scaffolder.py create --type <report|config-guide|white-paper|playbook|dossier|wiki-page> --doc-id "<DOC-ID>" --output <path>
     ```
1. **Intel® Ethernet Naming & Branding Rules (`D1`–`D4` v2.1)**:
   - First mentions must use full approved product branding: **Intel® Ethernet 800 Series** (`D1`), **Intel® Ethernet
     Controller E835** (`D2`), **Intel® Ethernet Network Adapter E835-CC** (`D3`), and **Intel® Xeon® 6 Processor**
     (`D4`). Never leak internal codenames in external deliverables.
2. **Interface & PCI Variable Parameterization**:
   - Replace hardcoded lab device names in reusable command snippets with `${NETDEV}`, `${PORT0}`, `${PORT1}`,
     `${PCI_DEV}`, `${BDF0}`, `${BDF1}`, and `${RDMA_DEV}`.
3. **Linux Kernel C Style (`checkpatch.pl --strict`)**:
   - Enforce 80-column max line length, strict **Reverse Christmas Tree (RCT)** local variable declarations, kernel-doc
     `/** ... */` headers on exported functions/structs, and proper error unwind labels.
4. **Markdown & Mermaid Validation**:
   - Quote Mermaid node labels containing parentheses or brackets (`id["Label (Detail)"]`) and use only supported
     diagram types (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`, `xychart-beta`).
5. **Single Source of Truth Compact Tables, `<= 120`-Column Line Wrapping & List Indentation (`Rule D5` v3.2 /
   `HH-BR-016` / `HH-BR-019`)**:
   - **Never Space-Pad Table Columns (`D5-PAD`) & Always Use Compact Separators (`D5-SEP`)**: Use `| --- |` separator
     rows and single-space cell margins (`| cell |`). Never pad cells with spaces (`.ljust()`) to align vertical pipes
     (`|`), and never use legacy `| ------ |` or `:---` separators.
   - **Eliminate Horizontal Left-to-Right Scrolling (`D5-COLS` & `D5-TOKEN`)**: Keep tables to `<= 3` columns in
     reports, white papers, and portrait PDF deliverables (`<= 4` columns max for A/B testbed matrices; `<= 5` in
     general docs) by stacking secondary fields vertically with `<br>`. Use short file basenames for links
     (`[0013-devtree-backports.patch](path/to/file.patch)` `<= 28` chars), split long identifiers at `<wbr>` boundaries
     (`<= 24` chars per segment), and never wrap multi-word prose sentences in backticks inside table cells.
   - **`<= 120`-Column Line Wrapping & List Continuation Indentation (`D5-WRAP` / `MD013` / `MD007` / `MD032`)**: Wrap
     prose paragraphs, bulleted/numbered list items (`- `, `* `, `1. `), and blockquotes (`> `, `> 1. `) at `<= 120`
     characters without splitting `[label](url)` links or inline code spans `` `...` ``. Align wrapped list continuation
     lines to the exact list marker width (`2` spaces for `- `, `3` spaces for `1. `, `5` spaces for `   - `, `>    `
     for `> 1. `), and place a blank line before every list (`MD032`).
   - **Code-Fence Exclusion & Escaped/Backtick-Pipe Safety (`D5-PIPE` / `HH-BR-019` / `HH-EVAL-09`)**: Never apply
     product branding regex replacements inside fenced bash/C code blocks (`ICE_DEV_ID_E835_*`), always mask existing
     `[label](url)` links before bare-URL auto-linkification, and never split table rows on `\|` or pipes inside inline
     backticks (`_split_table_row()`).
   - **Single Source of Truth Validator CLI & MCP Tools**: Run `python scripts/markdown_validator.py <path> --fix` (or
     MCP tool `validate_markdown_doc` with `auto_fix=true` / `fix_markdown`) to verify `100/100` compliance.
6. **ASD-STE100 Simplified Technical English (`Rule D6`) & Diátaxis/Metadata (`Rule D7` & `D7-ID-MATCH`)**:
   - Enforce `<= 20` words per procedural sentence (imperative verb first) and `<= 25` words per descriptive sentence
     (`>= 90%` active voice).
   - Replace unapproved STE filler words (`use` -> `use`, `before` -> `before`, `after` -> `after`,
     `to` -> `to`, `ensure` -> `make sure`) and prohibit ambiguous modals (`should`/`may`/`might`) in
     procedural steps.
   - Enforce Diátaxis 4-type section skeletons, `METADATA_HEADER_START..END` / `METADATA_FOOTER_START..END` blocks, and
     **`D7-ID-MATCH`** (exact `Document ID` match between Header and Footer without truncation).
7. **Shell Script (`Rule D8`), Config Schema/YAML (`Rule D9`) & Python Automation (`Rule D10`) Hardening**:
   - **Bash (`D8-SH`)**: Require `#!/usr/bin/env bash` , `set -Eeuo pipefail` , `trap cleanup EXIT` , quoted
     `"${NETDEV}"` , and `timeout <sec>` on hardware/BMC commands.
   - **JSON/YAML (`D9-CFG`)**: Validate against `schemas/*.schema.json` , include `"$schema"` + `"schema_version"` , and
     quote YAML 1.1 boolean/sexagesimal traps (`"on"`, `"off"` , `"0:0 3:3"` ).
   - **Python (`D10-PY`)**: Require explicit `timeout=` on `subprocess.run()` (`2.0s` local / `5.0s` BMC) and
     `ProxyHandler({})` on private lab subnets.

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | .github/agents/universal<wbr>-style-and-doc-validator<wbr>.agent.md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-GITHUB-AGENTS-UNIVERSAL-STYLE-AND-DOC-VALI`, `DOC-NETPERF-GITHUB-AGEN<wbr>TS-UNIVERSAL-STYLE-AND-<wbr>DOC-VALI`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
