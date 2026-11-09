---
description: Enforce compact zero-horizontal-scroll Markdown tables (| --- |), <= 120-column line wrapping (MD013/MD007/MD032), canonical Intel technical document templates (templates/), ASD-STE100 (Rule D6), and Rules D1-D10 v3.2
trigger: always_on
---

# Compact Markdown Tables, Canonical Templates & External Documentation Sanitization (`Rules D1`–`D10` v3.2)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-AGENTS-RULES-MARKDOWN-AND-SANITIZATION` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Compact Markdown Tables, Canonical Templates & External Documentation Sanitization (`Rules D1`–`D10` v3.2) under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


## 1. Mandatory Intel® Technical Document Templates (`templates/`)

Whenever creating or updating an engineering report, configuration guide, white paper, troubleshooting playbook,
repository dossier, or GitHub Wiki page:

1. **Start from a Canonical Template (`templates/TEMPLATE_01..06_*.md`)**:
   - Scaffold via
     `python scripts/doc_template_scaffolder.py create --type <report|config-guide|white-paper|playbook|dossier|wiki-page> --doc-id <ID> --output <path>`
     (or MCP tool `validate_markdown_doc` with `scaffold_template`).
   - Reference [`templates/README.md`](../../templates/README.md) for the 6 canonical templates (`TEMPLATE-01`
     Engineering/A-B Report, `TEMPLATE-02` Config Guide/BKM, `TEMPLATE-03` White Paper, `TEMPLATE-04` Troubleshooting
     Playbook, `TEMPLATE-05` Dossier/README, `TEMPLATE-06` 5-Page Wiki Pack).
2. **`D7-ID-MATCH` — Synchronize Header & Footer `Document ID`**:
   - Ensure the `Document ID` in `METADATA_HEADER_START..END` matches `METADATA_FOOTER_START..END` (`Validation / Patch
     IDs`) verbatim without truncation.

## 2. Compact, No-Horizontal-Scroll Markdown Tables & `<= 120`-Char Wrapping (`Rule D5` v3.2)

1. **`D5-PAD` & `D5-SEP` **: Use single-space cell margins (`| cell |`) and compact `| --- |` separator rows. Never pad
   cells with spaces (`.ljust()`) or use `| ------ |` / `:---` separators.
2. **`D5-COLS` — Prevent Left-to-Right Scrolling**: Keep tables to `<= 3` columns in reports, white papers, and portrait
   PDF deliverables (`<= 4` columns max for A/B testbed matrices; `<= 5` in general docs) by stacking secondary fields
   vertically with `<br>` .
3. **`D5-TOKEN` — Short Basenames & `<wbr>` Breakpoints**:
   - Use short file basenames for links (`[0013-devtree-backports.patch](path/to/file.patch)` `<= 28` chars) instead of
     long inline-code paths inside table cells.
   - Split unbreakable identifiers (`> 40` chars) at `<wbr>` boundaries (`<= 24` chars per segment), and never wrap
     multi-word prose sentences (`>= 6` words) in backticks inside table cells.
4. **`D5-WRAP` (`MD013` / `MD007` / `MD032`) — `<= 120`-Column Line Wrapping & List Indentation**:
   - Wrap all prose, numbered/bulleted lists, and blockquotes at `<= 120` characters (`MD013`).
   - Align wrapped list continuation lines to the exact list marker width (`2` spaces for `- ` , `3` spaces for `1. ` ,
     `5` spaces for `   - ` , `>    ` for `> 1. ` ) (`MD007`) and place a blank line before every list (`MD032`).
5. **Single Source of Truth Validator**: Run `python scripts/markdown_validator.py <path> --fix` (or MCP tool
   `validate_markdown_doc` with `auto_fix=true` ) and verify `100/100` (`0` violations) before completion.

## 3. ASD-STE100 Simplified Technical English (`Rule D6`) & Code/Config Hardening (`Rules D7`–`D10` v3.2)

1. **`Rule D6` (ASD-STE100 Simplified Technical English)**:
   - Keep procedural sentences `<= 20` words (one instruction per sentence, starting with an imperative verb) and
     descriptive sentences `<= 25` words (`>= 90%` active voice).
   - Use approved STE words (`use` instead of `use` , `before` instead of `before` , `after` instead of `after` , `to`
     instead of `to` , `make sure` instead of `ensure` , `must` /`can` instead of ambiguous `should` /`may`/`might` in
     steps).
2. **`Rule D8` (Google Shell Style + ShellCheck Defensive Bash)**:
   - Enforce `#!/usr/bin/env bash` , `set -Eeuo pipefail` , `trap cleanup EXIT` , quoted `"${NETDEV}"` , `timeout <sec>`
     on hardware/BMC commands, and `dmesg` (`DMAR=0`) gates.
3. **`Rule D9` (JSON Schema Draft 2020-12 & YAML 1.2 Strict Configs)**:
   - Include `"$schema"` and `"schema_version"` , quote YAML boolean/sexagesimal strings (`"on"`, `"off"` , `"0:0 3:3"`
     , PCI BDFs), and enforce E835 hardware bounds (`queues <= 63`).
4. **`Rule D10` (Python Subprocess Timeout & Proxy Bypass)**:
   - Pass explicit `timeout=` (`2.0s` local / `5.0s` BMC) to `subprocess.run(..., shell=False)` and bypass corporate
     proxies (`ProxyHandler({})`) on private lab subnets (`10.x.x.x` / `198.18.x.x` ).

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | .agents/rules/markdown-<wbr>and-sanitization.md |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-AGENTS-RULES-MARKDOWN-AND-SANITIZATION`, `DOC-NETPERF-AGENTS-RULE<wbr>S-MARKDOWN-AND-SANITIZAT<wbr>ION`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
