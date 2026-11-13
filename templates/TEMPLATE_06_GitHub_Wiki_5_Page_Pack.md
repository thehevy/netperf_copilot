# GitHub Wiki Page & 5-Page Repository Wiki Pack Template

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-TEMPLATE-GITHUB-WIKI-006` | **Version**: `v3.2` | **Status**: `Canonical Template`
- **Created Date**: `2026-11-09` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: Repository GitHub Wiki (`wiki/*.md`)
- **Summary**: Canonical GitHub Wiki page and multi-page wiki pack template for high-speed networking repositories under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->

> [!IMPORTANT]
> **GitHub Wiki Formatting & Link Rules**:
>
> 1. **Multi-Page Repository Wiki Standard**: Repository wiki packs in `wiki/` contain `Home.md`, architecture/white
>    paper pages, CLI/configuration guides, `_Sidebar.md`, and `_Footer.md`.
> 2. **Zero-Scroll `<= 3`-Column Tables**: GitHub Wiki renders a persistent right-hand `_Sidebar.md` column, reducing
>    horizontal viewport width by `260px`. Keep all Wiki tables to `<= 3` columns (`D5-COLS`) and tokens `<= 36`
>    characters (`D5-TOKEN`).
> 3. **Wiki-Safe Internal Links**: Link between wiki pages within the same wiki using page slugs (`[Executive
>    Summary](Executive-Summary)`) or full GitHub URLs (`https://github.com/thehevy/netperf_copilot/blob/master/...`)
>    for source-tree files; never use relative `../` paths that escape the `.wiki.git` root.

---

## 1. Canonical Repository Wiki Structure (`3`-Column Table)

| Wiki File Name | Required Sections & Content | Synchronization & Validation Rule |
| --- | --- | --- |
| **`Home.md`** | 1. H1 Title + `METADATA_HEADER_START..END`<br>2. `2`-Column Repository Overview Table<br>3. Quick-Start Workflow & Executive Summary<br>4. Wiki Navigation Table + `METADATA_FOOTER_START..END` | Must pass `python scripts/markdown_validator.py wiki/Home.md --strict-3col`. |
| **`Executive-Summary.md` & `Technical-White-Paper.md`** | 1. H1 Title + `METADATA_HEADER_START..END`<br>2. Key Technical Insights & Architecture<br>3. Empirical Benchmark Summary + Footer | Must pass `D1`–`D10` `v3.2` (`0` `D5-COLS`, `D5-TOKEN`, `MD013`, or `D7-ID-MATCH` issues). |
| **`Modernization-Tools.md` & `Installation-and-Quick-Start.md`** | 1. H1 Title + `METADATA_HEADER_START..END`<br>2. Build & CLI Reference Tables (`<= 3` cols)<br>3. End-to-End Examples + Footer | All source links must use full [github.com/netperf_](https://github.com/thehevy/netperf_)<wbr>copilot/<wbr>... URLs. |
| **`_Sidebar.md` & `_Footer.md`** | Compact navigation links (`Home`, `Executive-Summary`, `Technical-White-Paper`, `Modernization-Tools`). | Excluded from `METADATA_HEADER_START` requirement per Global Rule #4. |

---

## 2. Wiki Page Content Skeleton (`Home.md` / `Technical-White-Paper.md`)

Use this exact structure when creating or updating a standalone Wiki page:

1. Start with an H1 `# <Repository or Topic Title> — Wiki` heading followed immediately by `METADATA_HEADER_START..END`.
2. Provide a `2`-column or `3`-column summary table using `| --- |` compact separators and single-space margins.
3. Wrap all prose and list items at `<= 120` characters (`MD013`) with exact list continuation indentation (`MD007`).
4. Close with `METADATA_FOOTER_START..END` containing the exact same `Document ID` as the header (`D7-ID-MATCH`).

---

## 3. Wiki Validation Commands

Run these commands to validate all wiki pages in `wiki/` before pushing to `netperf_copilot.wiki.git`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Validate all wiki pages in strict 3-column mode (<= 120-char line wrap + D7-ID-MATCH)
python scripts/markdown_validator.py wiki --strict-3col --fix
```

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | templates/<wbr>TEMPLATE_06_GitHub_Wiki_5_<wbr>Page_Pack.md |
| **Created / Last Updated** | `2026-11-09` / `2026-11-09` |
| **Keywords / Search Tags** | `GitHub Wiki Template`, `5-Page Wiki Pack`, `Zero-Scroll 3-Column Wiki`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `netperf_copilot`, `wiki`, `markdown_validator.py` |
| **Validation / Patch IDs** | `DOC-TEMPLATE-GITHUB-WIKI-006`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
