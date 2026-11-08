---
description: Single Source of Truth Compact Markdown Tables (| --- |), Zero Horizontal Scroll, and Customer Sanitization
trigger: always_on
---

# Compact Markdown Tables & External Documentation Sanitization (`Rule D5` v2.2)

## 1. Compact, No-Horizontal-Scroll Markdown Tables (`| --- |`)

Whenever authoring or formatting Markdown (`.md`) files or Python Markdown generators:
1. **`D5-PAD` — Never Space-Pad Table Columns**: Use single-space cell margins (`| cell |`). Do not pad cells with spaces (`.ljust()`) to align vertical pipes across rows.
2. **`D5-SEP` — Compact Separator Rows**: Always use `| --- |` separator rows; never generate `| ----------- |` or `:---` separator lines.
3. **`D5-COLS` — Prevent Left-to-Right Scrolling**: Keep tables to `<= 5` columns in general repo docs (`<= 3` columns in portrait PDF deliverables) by stacking secondary fields vertically with `<br>`.
4. **`D5-TOKEN` — Short Basenames & Natural Wrapping**:
   - Use short file basenames for links (`[filename.py](path/to/filename.py)`) instead of long inline-code paths inside table cells.
   - Only wrap short identifiers, flags, or symbol names in backticks inside table cells; never wrap multi-word prose sentences (`>= 6` words) in backticks.
5. **Single Source of Truth Validator**: Run `python markdown_validator.py . --fix` (`thehevy/markdown_quality_validator` v2.0) or MCP tool `validate_markdown_doc` (`hevyone-kb-mcp`).
