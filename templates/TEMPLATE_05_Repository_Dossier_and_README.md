# Intel® Repository Executive Dossier & Project `README.md` Template (`Diátaxis Overview`)

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-DOSSIER-README-005` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Repository Dossiers (`repos/<category>/<RepoName>.md`) and Project Root `README.md` Files
- **Summary**: Canonical repository overview and executive dossier template for **Intel® Ethernet 800 Series** (**Intel® Ethernet Controller E835** and **Intel® Ethernet Network Adapter E835-CC**) and **Intel® Xeon® 6 Processor** repositories under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> **One-Line Summary**: Concise `1`-sentence statement of the repository's engineering purpose, target hardware
> (**Intel® Ethernet Network Adapter E835-CC** / **Intel® Xeon® 6 Processor**), and primary deliverables.

| Field | Value |
| --- | --- |
| **Repository** | [Example_Repo](https://github.com/intel-sandbox/HevyOne) |
| **Category** | `intel-sandbox` (Private (`intel-sandbox`)) |
| **Strategic Theme** | High-Speed Networking, Kernel Driver Alignment & AI Validation |
| **Status** | **Active — Production Validated (`100/100` `D1`–`D10` v3.2 Compliance)** |
| **Current Focus** | Summarize the active sprint milestone, hardware testbed target (`TB1`–`TB5`), and verification gate. |
| **Target Audience / Use Case** | Linux Kernel & RDMA Engineers, Validation Architects, Multi-Agent AI Sessions |
| **Last Updated (GitHub Push)** | `2026-11-09` |

---

## 1. Quick Share Block (Copy-Paste for Co-workers / Teams / Email)

> Copy the block below to share this repository's purpose and status with co-workers:

```markdown
**<Repository Name> — <Short Engineering Subtitle>** (`<owner>/<repo>`)
- **What it is**: 1-sentence overview of the repository and how it integrates with `intel-sandbox/HevyOne`.
- **Key Capabilities**:
  1. **Capability 1**: Summarize core functionality, driver subsystem (`ice`/`irdma`/`iavf`), or automation script.
  2. **Capability 2**: Summarize hardware validation coverage (`3-Bucket Accounting`, `DMAR=0` gate).
  3. **Capability 3**: Summarize MCP tools, CLI entrypoints, or published `PDF_REPO` deliverables.
- **Repo Link**: https://github.com/<owner>/<repo>
```

---

## 2. Executive Summary

Write `2` concise paragraphs (`<= 25` words per sentence, `>= 90%` active voice) explaining the engineering problem this
repository solves for the **Intel® Ethernet 800 Series**, **Intel® Ethernet Controller E835**, and **Intel® Xeon® 6
Processor** portfolio, and how its outputs connect to `HevyOne`, `PDF_REPO` (`http://10.166.84.133/`), and `HevyHitter`
(`http://10.166.84.133:8000/`).

---

## 3. Key Technical Insights & Repository Layout (`3`-Column Zero-Scroll Table)

Use a `3`-column table with short basename links (`<= 28` characters) to document the repository's key modules:

| Component & Basename Link | Role & Architectural Responsibility | CLI Entrypoint & Validation Gate |
| --- | --- | --- |
| **Core Validator**<br>[markdown_validator.py](../scripts/markdown_validator.py) | Enforces `D1`–`D10` `v3.2`, `<= 120`-column line wrapping (`MD013`), list indent (`MD007`), and `<= 3–4` column tables (`D5-COLS`). | `python scripts/markdown_validator.py . --fix`<br>Score: `100/100` (`0` violations) |
| **Wiki Maintainer**<br>[wiki_monitor_agent.py](../scripts/wiki_monitor_agent.py) | Synchronizes the `12`-page central wiki and `23` per-repo `5`-page wiki packs against commit SHAs and dossier hashes. | `python scripts/wiki_monitor_agent.py check --strict` |

---

## 4. Plans & Next Steps (Roadmap)

- [ ] **Milestone 1**: Describe the next concrete engineering deliverable with a measurable verification gate.
- [ ] **Milestone 2**: Describe the planned testbed validation sweep (`TB1`–`TB5`, `labctl checkout`, `DMAR=0`).
- [ ] **Milestone 3**: Describe downstream integration with `HevyOne`, `PDF_REPO`, and `HevyHitter`.

---

## 5. Activity & Repository Snapshot

<!-- AUTO-SYNC-ACTIVITY:START -->
- **Last Activity**: `2026-11-09` | **Default Branch**: `main` (1 branch: `main`)
- **Languages / Stack**: Python, Bash, C, Markdown | **Tracked Files**: `100`

### Recent Commits

| Date & Commit | Author | Commit Summary |
| --- | --- | --- |
| `2026-11-09` · `a1b2c3d4` | Engineering Team | Enforce `D1`–`D10` `v3.2` templates, `<= 120`-col wrapping (`MD013`), and `D7-ID-MATCH` |
<!-- AUTO-SYNC-ACTIVITY:END -->

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_05_Repository_<wbr>Dossier_and_README.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `Repository Dossier Template`, `Project README Template`, `Diataxis Overview`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `irdma`, `iavf`, `HevyOne`, `wiki_monitor_agent.py`, `markdown_validator.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-DOSSIER-README-005`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
