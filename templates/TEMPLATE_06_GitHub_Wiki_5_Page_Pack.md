# Intel® GitHub Wiki Page & 5-Page Repository Wiki Pack Template

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-GITHUB-WIKI-006` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Central Hub Wiki (`wiki/*.md`) and All 23 Per-Repository Wiki Packs (`dist/repo-wikis/<RepoName>/*.md`)
- **Summary**: Canonical GitHub Wiki page and 5-page wiki pack template for **Intel® Ethernet 800 Series** (**Intel® Ethernet Controller E835** and **Intel® Ethernet Network Adapter E835-CC**) and **Intel® Xeon® 6 Processor** repositories under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!IMPORTANT]
> **GitHub Wiki Formatting & Link Rules (`wiki_monitor_agent.py`)**:
>
> 1. **5-Page Repository Wiki Pack Standard**: Every repository wiki pack in `dist/repo-wikis/<RepoName>/` must contain
>    exactly `5` files: `Home.md`, `Architecture-and-Insights.md`, `Commit-Log-and-Roadmap.md`, `_Sidebar.md`, and
>    `_Footer.md`.
> 2. **Zero-Scroll `<= 3`-Column Tables**: GitHub Wiki renders a persistent right-hand `_Sidebar.md` column, reducing
>    horizontal viewport width by `260px`. Keep all Wiki tables to `<= 3` columns (`D5-COLS`) and tokens `<= 36`
>    characters (`D5-TOKEN`).
> 3. **Wiki-Safe Internal Links**: Link between wiki pages within the same wiki using page slugs (`[Architecture &
>    Insights](Architecture-and-Insights)`) or full GitHub URLs for source-tree files; never use broken `../` paths
>    that escape the `.wiki.git` root.

---

## 1. Canonical `5`-Page Repository Wiki Pack Structure (`3`-Column Table)

| Wiki File Name | Required Sections & Content | Synchronization & Validation Rule |
| --- | --- | --- |
| **`Home.md`** | 1. H1 Title + `METADATA_HEADER_START..END`<br>2. `2`-Column Repository Overview Table<br>3. Quick Share Block & Executive Summary<br>4. Wiki Navigation Table + `METADATA_FOOTER_START..END` | Auto-synced from `repos/<cat>/<RepoName>.md` via `python scripts/wiki_monitor_agent.py sync --all`. |
| **`Architecture-and-Insights.md`** | 1. H1 Title + `METADATA_HEADER_START..END`<br>2. Key Technical Insights & Architecture<br>3. Grounded `HevyOne` `kb/` References + Footer | Must pass `D1`–`D10` `v3.2` (`0` `D5-COLS`, `D5-TOKEN`, `MD013`, or `D7-ID-MATCH` issues). |
| **`Commit-Log-and-Roadmap.md`** | 1. H1 Title + `METADATA_HEADER_START..END`<br>2. Plans & Next Steps (Roadmap)<br>3. `3`-Column Recent Commits Table + Footer | Synced against `recent_commits[0].sha` in `data/repo_snapshots.json`. |
| **`_Sidebar.md` & `_Footer.md`** | Compact navigation links (`Home`, `Architecture-and-Insights`, `Commit-Log-and-Roadmap`, and `HevyOne` Hub link). | Excluded from `METADATA_HEADER_START` requirement per Global Rule #4. |

---

## 2. Wiki Page Content Skeleton (`Home.md` / `Architecture-and-Insights.md`)

Use this exact structure when creating or updating a standalone Wiki page:

1. Start with an H1 `# <Repository or Topic Title> — Wiki` heading followed immediately by `METADATA_HEADER_START..END`.
2. Provide a `2`-column or `3`-column summary table using `| --- |` compact separators and single-space margins.
3. Wrap all prose and list items at `<= 120` characters (`MD013`) with exact list continuation indentation (`MD007`).
4. Close with `METADATA_FOOTER_START..END` containing the exact same `Document ID` as the header (`D7-ID-MATCH`).

---

## 3. Wiki Sync & Strict Verification Commands

Run these commands in `HevyOne` to synchronize and validate all `12` central wiki pages and all `23` per-repository wiki
packs (`115` repo wiki files + `12` central wiki files = `127` wiki files):

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# 1. Check commit SHA, dossier SHA-256, and D1-D10 v3.2 compliance across all 23 repo wikis
python scripts/wiki_monitor_agent.py status

# 2. Regenerate any stale or drifted wiki pages and enforce strict zero-violation gate
python scripts/wiki_monitor_agent.py sync --all
python scripts/wiki_monitor_agent.py check --strict
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_06_GitHub_Wiki_5_<wbr>Page_Pack.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `GitHub Wiki Template`, `5-Page Wiki Pack`, `wiki_monitor_agent.py`, `Zero-Scroll 3-Column Wiki`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `HevyOne`, `wiki`, `dist/repo-wikis`, `markdown_validator.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-GITHUB-WIKI-006`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
