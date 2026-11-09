---
description: "Enforce compact zero-horizontal-scroll Markdown tables (| --- |), <= 120-column line wrapping (MD013/MD007/MD032), canonical technical document templates (templates/), ASD-STE100 (Rule D6), and Rules D1-D10 v3.2"
trigger: always_on
---

# Compact Markdown Tables, Canonical Templates & External Documentation Sanitization (`Rules D1`–`D10` v3.2)

## 1. Mandatory Technical Document Templates (`templates/`)

Whenever creating or updating an engineering report, configuration guide, white paper, troubleshooting playbook,
repository dossier, or GitHub Wiki page:

1. **Start from a Canonical Template (`templates/TEMPLATE_01..06_*.md`)**:
   - Scaffold via
     `python scripts/doc_template_scaffolder.py create --type <report|config-guide|white-paper|playbook|dossier|wiki-page> --doc-id <ID> --output <path>`.
   - Reference [`templates/README.md`](../../templates/README.md) for the 6 canonical templates (`TEMPLATE-01`
     Engineering/A-B Report, `TEMPLATE-02` Config Guide/BKM, `TEMPLATE-03` White Paper, `TEMPLATE-04` Troubleshooting
     Playbook, `TEMPLATE-05` Dossier/README, `TEMPLATE-06` 5-Page Wiki Pack).
2. **`D7-ID-MATCH` — Synchronize Header & Footer `Document ID`**:
   - Make sure the `Document ID` in `METADATA_HEADER_START..END` matches `METADATA_FOOTER_START..END` (`Validation /
     Patch IDs`) verbatim without truncation.

## 2. Compact, No-Horizontal-Scroll Markdown Tables & `<= 120`-Char Wrapping (`Rule D5` v3.2)

1. **`D5-PAD` & `D5-SEP`**: Use single-space cell margins (`| cell |`) and compact `| --- |` separator rows. Never pad
   cells with spaces (`.ljust()`) or use `| ------ |` / `:---` separators.
2. **`D5-COLS` — Prevent Left-to-Right Scrolling**: Keep tables to `<= 3` columns in reports, white papers, and portrait
   PDF deliverables (`<= 4` columns max for A/B testbed matrices; `<= 5` in general docs) by stacking secondary fields
   vertically with `<br>`.
3. **`D5-TOKEN` — Short Basenames & `<wbr>` Breakpoints**:
   - Use short file basenames for links (`[example-patch.patch](path/to/file.patch)` `<= 28` chars) instead of long
     inline-code paths inside table cells.
   - Split unbreakable identifiers (`> 40` chars) at `<wbr>` boundaries (`<= 24` chars per segment), and never wrap
     multi-word prose sentences (`>= 6` words) in backticks inside table cells.
4. **`D5-WRAP` (`MD013` / `MD007` / `MD032`) — `<= 120`-Column Line Wrapping & List Indentation**:
   - Wrap all prose, numbered/bulleted lists, and blockquotes at `<= 120` characters (`MD013`).
   - Align wrapped list continuation lines to the exact list marker width (`2` spaces for `- `, `3` spaces for `1. `,
     `5` spaces for `   - `, `>    ` for `> 1. `) (`MD007`) and place a blank line before every list (`MD032`).
5. **Single Source of Truth Validator**: Run `python scripts/markdown_validator.py <path> --fix` and verify `100/100`
   (`0` violations) before completion.

## 3. ASD-STE100 Simplified Technical English (`Rule D6`) & Code/Config Hardening (`Rules D7`–`D10` v3.2)

1. **`Rule D6` (ASD-STE100 Simplified Technical English)**:
   - Keep procedural sentences `<= 20` words (one instruction per sentence, starting with an imperative verb) and
     descriptive sentences `<= 25` words (`>= 90%` active voice).
   - Use approved STE words (`use`, `before`, `after`, `to`, `make sure`, and `must`/`can` instead of ambiguous
     `should`/`may`/`might` in procedural steps).
2. **`Rule D8` (Google Shell Style + ShellCheck Defensive Bash)**:
   - Enforce `#!/usr/bin/env bash`, `set -Eeuo pipefail`, `trap cleanup EXIT`, quoted `"${NETDEV}"`, `timeout <sec>`
     on hardware commands, and `dmesg` (`DMAR=0`) gates.
3. **`Rule D9` (JSON Schema Draft 2020-12 & YAML 1.2 Strict Configs)**:
   - Include `"$schema"` and `"schema_version"`, quote YAML boolean/sexagesimal strings (`"on"`, `"off"`, `"0:0 3:3"`,
     PCI BDFs), and enforce hardware queue bounds (`queues <= 63`).
4. **`Rule D10` (Python Subprocess Timeout & Proxy Bypass)**:
   - Pass explicit `timeout=` (`2.0s` local / `5.0s` remote) to `subprocess.run(..., shell=False)` and use RFC 5737 /
     RFC 2544 documentation subnets (`192.0.2.x` / `198.51.100.x`) in public examples.

---
