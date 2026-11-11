# Technical Document, Report & Wiki Template Suite (`Rules D1`–`D10` v3.2)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-SUITE-INDEX-000` | **Version**: `v3.2` | **Status**: `Active (Single Source of Truth)`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Public & Open-Source Technical Documentation, Engineering Reports, and GitHub Wikis
- **Summary**: Canonical technical documentation, engineering report, white paper, configuration guide, troubleshooting playbook, dossier, and GitHub Wiki templates enforcing Rules `D1`–`D10` `v3.2` (`100/100` zero-violation score).
<!-- METADATA_HEADER_END -->

> [!IMPORTANT]
> **Mandatory Template & Validation Gate**:
> Every report, configuration guide, white paper, troubleshooting playbook, repository dossier, or wiki page created or
> updated in this repository **must** use one of the 6 canonical templates in this directory (or be scaffolded via
> `python scripts/doc_template_scaffolder.py create`) and pass `python scripts/markdown_validator.py <file> --fix` with
> **`0` violations (`100/100`)** before completion.

---

## 1. Canonical Technical Document Templates (`templates/`)

| Template ID & Basename Link | Target Document Type (`Diátaxis` Standard) | Table & Formatting Rules Enforced |
| --- | --- | --- |
| **`TEMPLATE-01`**<br>[TEMPLATE_01_Engineerin<wbr>g_Validation_and_Execu<wbr>tive_Report.md](TEMPLATE_01_Engineering_Validation_and_Executive_Report.md) | **Executive Engineering, Patch & A/B Hardware Validation Report**<br>(`A/B` Reports, Sprint Audits) | • `3`-col Patch & Falsified Claims tables<br>• `4`-col max A/B Testbed Matrix (`State A` vs. `State B`)<br>• `3`-Bucket Test Accounting & `DMAR=0` gate |
| **`TEMPLATE-02`**<br>[TEMPLATE_02_Configurat<wbr>ion_Guide_and_BKM_Runb<wbr>ook.md](TEMPLATE_02_Configuration_Guide_and_BKM_Runbook.md) | **Configuration Guide & Best Known Method (`BKM`) Runbook**<br>(Host/Switch Deployment Guides) | • `Step 0` pre-flight hardware gate<br>• `${NETDEV}` / `${PCI_DEV}` variable table<br>• `<= 20`-word imperative `ASD-STE100` steps<br>• `D8` Bash + `D9` quoted YAML 1.2 |
| **`TEMPLATE-03`**<br>[TEMPLATE_03_Architectu<wbr>re_White_Paper_and_Ben<wbr>chmark_Study.md](TEMPLATE_03_Architecture_White_Paper_and_Benchmark_Study.md) | **Architecture White Paper & Empirical Benchmark Study**<br>(Architecture & Multi-Core Studies) | • `3`-col Portrait PDF tables (`--strict-3col`)<br>• RFC 5737 (`192.0.2.x`) IP sanitization<br>• Quoted Mermaid diagrams & `Evidence Tier 1` |
| **`TEMPLATE-04`**<br>[TEMPLATE_04_Troublesho<wbr>oting_and_Root_Cause_<wbr>Playbook.md](TEMPLATE_04_Troubleshooting_and_Root_Cause_Playbook.md) | **Troubleshooting & Root-Cause Diagnostic Playbook**<br>(Kernel Driver, LACP LAG, PCIe/IOMMU Triage) | • `3`-part STE `> [!CAUTION]` safety header<br>• `3`-col Symptom Triage Matrix<br>• Strict `4`-bullet Symptom -> Root Cause -> Verification -> Fix |
| **`TEMPLATE-05`**<br>[TEMPLATE_05_Repository_<wbr>Dossier_and_README.md](TEMPLATE_05_Repository_Dossier_and_README.md) | **Repository Executive Dossier & Project `README.md`**<br>(Project Overview & Root `README.md`) | • `2`-col Overview Metadata Table<br>• Quick Share Block & `3`-col Module Table<br>• Auto-Sync Commit Snapshot block |
| **`TEMPLATE-06`**<br>[TEMPLATE_06_GitHub_Wik<wbr>i_5_Page_Pack.md](TEMPLATE_06_GitHub_Wiki_5_Page_Pack.md) | **GitHub Wiki Page & 5-Page Repository Wiki Pack**<br>(`wiki/*.md`) | • `5`-page Wiki Pack (`Home`, `Architecture`, `Commits`, `_Sidebar`, `_Footer`)<br>• `<= 3`-col tables (`260px` sidebar clearance) |

---

## 2. Real-World Anti-Patterns Prevented by These Templates

The table below documents the `5` recurring formatting failures observed in technical reports and how `templates/` +
`markdown_validator.py` (`v3.2`) eliminate them:

| Rule ID & Anti-Pattern Observed | Why It Failed in Technical Reports | Mandatory Template & Validator Fix (`v3.2`) |
| --- | --- | --- |
| **`D5-TOKEN` & `D5-COLS`**<br>Wide 5-Column Falsification Tables | Used `5` columns where Column 2 had `46–55` char inline-code filenames next to two wide prose columns, forcing horizontal scrollbars. | Use **`TEMPLATE-01` Section 3** (`3` columns: Claim ID & Source Artifact \| Original Claim vs. Empirical Falsification \| Disposition), split tokens with <wbr> (`<= 24` chars), and stack Claim + Falsification with `<br>`. |
| **`D5-COLS`**<br>6-Column A/B Testbed Matrices | Used `6` columns (Testbed \| Workload \| State A \| State B \| Delta \| Status), violating `D5-COLS` and overflowing GitHub and PDF viewports. | Use **`TEMPLATE-01` Section 4** (`4` columns max): stack **State A (Baseline)** and **State B (Patched)** with `<br>` in Column 3, and stack **Delta + Pass Gate + `dmesg`** in Column 4. |
| **`D5-TOKEN` & `D5-LINK`**<br>Long Link Labels & Broken Paths | Used `54`-char link labels, `47`-char unbreakable debugfs paths, and broken relative paths. | Shorten link labels to compact basenames (`[netperf_tuner.py]` `<= 28` chars), split long paths at <wbr>, and verify all relative links via `check_relative_links()`. |
| **`MD013` / `D5-WRAP`, `MD007` & `MD032`**<br>Unwrapped `515`-Char Lines | Wrote single-line paragraphs, list items, and blockquotes up to `515` chars long without blank lines before lists (`MD032`) or proper continuation indent (`MD007`). | Wrap all prose, list items, and `> [!IMPORTANT]` blockquotes at `<= 120` chars (`MD013`), align list continuation lines (`2`/`3`/`5` spaces or `> `), and insert blank lines before lists. |
| **`Rule D6` & `D7-ID-MATCH`**<br>Mismatched Header/Footer IDs | Exceeded the `25`-word STE sentence cap and truncated the footer `Document ID`, mismatching the header `Document ID`. | Enforce `<= 20`w procedural / `<= 25`w descriptive STE sentences and auto-verify/sync the exact header `Document ID` into the footer (`D7-ID-MATCH` in `markdown_validator.py` `v3.2`). |

---

## 3. Quick-Start CLI Scaffolding Commands

Scaffold a pre-validated document from any template and run the Single Source of Truth validator:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# 1. List all 6 canonical document templates
python scripts/doc_template_scaffolder.py list

# 2. Scaffold a new Executive Engineering & A/B Validation Report
python scripts/doc_template_scaffolder.py create \
  --type report \
  --doc-id "DOC-NETPERF-AB-REPORT-2026-11" \
  --title "High-Speed 200GbE Network Performance & A/B Validation Report" \
  --scope "netperf_copilot 100GbE-800GbE Qualification" \
  --output dev/docs/EXAMPLE_AB_VALIDATION_REPORT.md

# 3. Validate and auto-fix any existing Markdown file or directory (D1-D10 v3.2)
python scripts/markdown_validator.py <path_to_file_or_dir> --fix
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `templates/README.md` |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Technical Document Templates`, `Engineering Report Template`, `Config Guide Template`, `White Paper Template`, `Wiki Template`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `Linux networking`, `ethtool`, `devlink`, `netperf_copilot`, `markdown_validator.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-SUITE-INDEX-000`, `D1-D10 v3.2`, `MD013`, `MD007`, `MD032`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
