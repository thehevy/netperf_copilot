#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: scripts/markdown_validator.py
# Created Date: 2026-11-09
# Last Updated Date: 2026-11-09
# Version: v3.2
# Status: Active
# Target Scope: Single Source of Truth Markdown Validator & Auto-Fixer (Rules D1-D10 v3.2)
# Summary: Enforces Rules D1-D10 v3.2 including compact | --- | tables (D5-SEP/D5-PAD), column limits (D5-COLS), token <wbr> breakpoints (D5-TOKEN), <= 120-char wrapping (D5-WRAP/MD013/MD007/MD032), ASD-STE100 (D6), and Header/Footer Document ID sync (D7/D7-ID-MATCH).
# === METADATA_HEADER_END ===

import argparse
from datetime import date
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_METADATA_FILES = {"_Sidebar.md", "_Footer.md"}

STE_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\butilize\b", re.IGNORECASE), "use"),
    (re.compile(r"\butilizes\b", re.IGNORECASE), "uses"),
    (re.compile(r"\butilized\b", re.IGNORECASE), "used"),
    (re.compile(r"\butilizing\b", re.IGNORECASE), "using"),
    (re.compile(r"\bprior to\b", re.IGNORECASE), "before"),
    (re.compile(r"\bsubsequent to\b", re.IGNORECASE), "after"),
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bensure that\b", re.IGNORECASE), "make sure that"),
    (re.compile(r"\bensures that\b", re.IGNORECASE), "makes sure that"),
]


def _split_table_row(line: str) -> List[str]:
    """Split a Markdown table row on unescaped pipes outside inline backticks (D5-PIPE)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith(r"\|"):
        s = s[:-1]

    cells: List[str] = []
    cur: List[str] = []
    in_code = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(ch)
            cur.append(s[i + 1])
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
            cur.append(ch)
            i += 1
            continue
        if ch == "|" and not in_code:
            cells.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def _is_separator_row(cells: List[str]) -> bool:
    if not cells:
        return False
    return all(bool(re.match(r"^:?-{2,}:?$", c.strip())) for c in cells if c.strip() != "") and any(
        c.strip() != "" for c in cells
    )


def _max_cols_for_file(filepath: Path) -> int:
    name_upper = filepath.name.upper()
    parts_lower = [p.lower() for p in filepath.parts]
    if "wiki" in parts_lower or "white_paper" in name_upper or "WHITE-PAPER" in name_upper:
        return 3
    if "executive_summary" in name_upper.lower() or "report" in name_upper.lower() or "template" in parts_lower:
        return 4
    return 5


def _insert_wbr_in_token(token: str, max_seg: int = 22) -> str:
    """Split long unbreakable tokens (> 40 chars) with <wbr> outside markdown links."""
    if len(token.replace("<wbr>", "")) <= 38:
        return token
    if token.startswith("[") and "](" in token:
        # Shorten link label if > 28 chars
        m = re.match(r"^\[([^\]]+)\]\(([^)]+)\)(.*)$", token)
        if m:
            label, url, tail = m.group(1), m.group(2), m.group(3)
            clean_label = label.strip("`")
            if len(clean_label) > 28 and "/" in clean_label:
                clean_label = clean_label.rsplit("/", 1)[-1]
            if len(clean_label) > 28:
                clean_label = _insert_wbr_raw(clean_label, max_seg)
            return f"[{clean_label}]({url}){tail}"
        return token
    if token.startswith("`") and token.endswith("`") and len(token) > 40:
        inner = token[1:-1]
        return _insert_wbr_raw(inner, max_seg)
    return _insert_wbr_raw(token, max_seg)


def _insert_wbr_raw(text: str, max_seg: int = 22) -> str:
    if "<wbr>" in text and all(len(p) <= max_seg + 4 for p in text.split("<wbr>")):
        return text
    raw = text.replace("<wbr>", "")
    out: List[str] = []
    cur = ""
    for ch in raw:
        cur += ch
        if len(cur) >= max_seg and ch in ("_", "-", "/", "."):
            out.append(cur)
            cur = ""
        elif len(cur) >= max_seg + 2:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return "<wbr>".join(out)


def _format_cell(cell: str) -> str:
    c = " ".join(cell.strip().split())
    # Unwrap multi-word prose (>= 6 words) wrapped in backticks inside table cells
    def _unwrap_long_backtick(m: re.Match) -> str:
        inner = m.group(1)
        if len(inner.split()) >= 6:
            return inner
        return m.group(0)

    c = re.sub(r"`([^`]+)`", _unwrap_long_backtick, c)

    # Shorten markdown link labels > 28 chars inside cell
    def _fix_link(m: re.Match) -> str:
        lbl, url = m.group(1), m.group(2)
        clean = lbl.strip("`")
        if "/" in clean and len(clean) > 24:
            base = clean.rsplit("/", 1)[-1]
            lbl = f"`{base}`" if lbl.startswith("`") and lbl.endswith("`") else base
            clean = base
        if len(clean.replace("<wbr>", "")) > 28:
            lbl = _insert_wbr_raw(clean, 20)
        return f"[{lbl}]({url})"

    c = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _fix_link, c)

    # Split standalone tokens > 40 chars outside markdown links
    tokens = c.split(" ")
    fixed_tokens: List[str] = []
    for tok in tokens:
        if "](" in tok or tok.startswith("http://") or tok.startswith("https://"):
            fixed_tokens.append(tok)
        elif len(tok.replace("<wbr>", "")) > 40:
            fixed_tokens.append(_insert_wbr_in_token(tok))
        else:
            fixed_tokens.append(tok)
    return " ".join(fixed_tokens)


def _normalize_table_block(table_lines: List[str], max_cols: int) -> List[str]:
    if len(table_lines) < 2:
        return table_lines
    rows = [_split_table_row(ln) for ln in table_lines]
    hdr = rows[0]
    num_cols = len(hdr)
    if num_cols == 0:
        return table_lines

    target_cols = min(num_cols, max_cols)
    out_lines: List[str] = []
    for r_idx, cells in enumerate(rows):
        if _is_separator_row(cells):
            out_lines.append("| " + " | ".join(["---"] * target_cols) + " |")
            continue
        # Pad or consolidate cells to target_cols
        while len(cells) < num_cols:
            cells.append("")
        if num_cols > target_cols:
            kept = cells[: target_cols - 1]
            tail_cells = cells[target_cols - 1 :]
            if r_idx == 0:
                merged_last = " / ".join(c for c in tail_cells if c)
            else:
                parts: List[str] = []
                for idx_offset, val in enumerate(tail_cells):
                    if not val:
                        continue
                    col_idx = target_cols - 1 + idx_offset
                    col_hdr = hdr[col_idx].strip("*` ") if col_idx < len(hdr) else ""
                    if idx_offset == 0:
                        parts.append(val)
                    elif col_hdr:
                        parts.append(f"**{col_hdr}**: {val}")
                    else:
                        parts.append(val)
                merged_last = "<br>".join(parts)
            row_final = kept + [merged_last]
        else:
            row_final = cells[:target_cols]
        formatted_cells = [_format_cell(c) for c in row_final]
        out_lines.append("| " + " | ".join(formatted_cells) + " |")
    return out_lines


def _tokenize_preserving_spans(text: str) -> List[str]:
    """Split text into whitespace-delimited tokens while keeping [label](url) and `code` intact."""
    pattern = re.compile(r"\[[^\]]+\]\([^)]+\)|`[^`]+`|\S+")
    return pattern.findall(text)


def _wrap_line_120(line: str, width: int = 120) -> List[str]:
    if len(line) <= width:
        return [line]
    stripped = line.lstrip()
    if (
        stripped.startswith("#")
        or stripped.startswith("|")
        or stripped.startswith("<!--")
        or stripped.startswith("```")
        or stripped.startswith("---")
        or stripped.startswith("===")
    ):
        return [line]

    # Identify prefix and continuation indent (MD007)
    m_bq_list = re.match(r"^(>\s*(?:\d+\.\s+|[-*+]\s+))(.*)$", line)
    m_bq = re.match(r"^(>\s*)(.*)$", line)
    m_list = re.match(r"^(\s*(?:\d+\.\s+|[-*+]\s+))(.*)$", line)
    m_indent = re.match(r"^(\s+)(.*)$", line)

    if m_bq_list:
        first_prefix = m_bq_list.group(1)
        body = m_bq_list.group(2)
        # e.g. "> 1. " -> ">    "
        marker_after_gt = re.sub(r"^>\s*", "", first_prefix)
        cont_prefix = "> " + (" " * len(marker_after_gt))
    elif m_bq:
        first_prefix = m_bq.group(1)
        body = m_bq.group(2)
        if not first_prefix.endswith(" "):
            first_prefix += " "
        cont_prefix = first_prefix
    elif m_list:
        first_prefix = m_list.group(1)
        body = m_list.group(2)
        cont_prefix = " " * len(first_prefix)
    elif m_indent:
        first_prefix = m_indent.group(1)
        body = m_indent.group(2)
        cont_prefix = first_prefix
    else:
        first_prefix = ""
        body = line
        cont_prefix = ""

    tokens = _tokenize_preserving_spans(body.strip())
    if not tokens:
        return [line]

    wrapped: List[str] = []
    cur_prefix = first_prefix
    cur_tokens: List[str] = []
    for tok in tokens:
        candidate = cur_prefix + (" ".join(cur_tokens + [tok]))
        if len(candidate) <= width or not cur_tokens:
            cur_tokens.append(tok)
        else:
            wrapped.append(cur_prefix + " ".join(cur_tokens))
            cur_prefix = cont_prefix
            cur_tokens = [tok]
    if cur_tokens:
        wrapped.append(cur_prefix + " ".join(cur_tokens))
    return wrapped


def _derive_doc_id(filepath: Path) -> str:
    try:
        rel = filepath.resolve().relative_to(REPO_ROOT)
        stem = "_".join(rel.with_suffix("").parts)
    except ValueError:
        stem = filepath.stem
    clean = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    return f"DOC-NETPERF-{clean[:42]}"


def _ensure_header_and_footer(text: str, filepath: Path) -> str:
    if filepath.name in EXCLUDED_METADATA_FILES:
        return text

    today = date.today().isoformat()
    try:
        rel_path = str(filepath.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        rel_path = filepath.name
    rel_display = _insert_wbr_raw(rel_path, 22) if len(rel_path) > 36 else f"`{rel_path}`"

    # Extract or generate Document ID
    hdr_id_m = re.search(r"\*\*Document ID\*\*:\s*`([^`]+)`", text)
    doc_id = hdr_id_m.group(1) if hdr_id_m else _derive_doc_id(filepath)

    # 1. Ensure METADATA_HEADER_START .. END exists below H1
    if "<!-- METADATA_HEADER_START -->" not in text:
        lines = text.splitlines()
        h1_idx = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), -1)
        title_str = lines[h1_idx][2:].strip() if h1_idx >= 0 else filepath.stem
        header_block = [
            "",
            "<!-- METADATA_HEADER_START -->",
            f"- **Document ID**: `{doc_id}` | **Version**: `v3.2` | **Status**: `Active`",
            f"- **Created Date**: `2026-11-05` | **Last Updated Date**: `{today}`",
            "- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite",
            f"- **Summary**: Technical documentation for {title_str} under Rules `D1`–`D10` `v3.2`.",
            "<!-- METADATA_HEADER_END -->",
            "",
        ]
        if h1_idx >= 0:
            lines = lines[: h1_idx + 1] + header_block + lines[h1_idx + 1 :]
        else:
            lines = [f"# {filepath.stem}"] + header_block + lines
        text = "\n".join(lines)
    else:
        # Update Last Updated Date
        text = re.sub(
            r"(\*\*Last Updated Date\*\*:\s*)`[^`]+`",
            rf"\g<1>`{today}`",
            text,
            count=1,
        )

    # Re-read doc_id from header to guarantee D7-ID-MATCH
    hdr_id_m = re.search(r"\*\*Document ID\*\*:\s*`([^`]+)`", text)
    if hdr_id_m:
        doc_id = hdr_id_m.group(1)

    # 2. Ensure METADATA_FOOTER_START .. END exists at end of file and contains exact doc_id
    if "<!-- METADATA_FOOTER_START -->" not in text:
        footer_block = (
            "\n\n---\n\n"
            "<!-- METADATA_FOOTER_START -->\n"
            "### Document Search & Discovery Metadata\n\n"
            "| Field | Value |\n"
            "| --- | --- |\n"
            f"| **File Path** | {rel_display} |\n"
            f"| **Created / Last Updated** | `2026-11-05` / `{today}` |\n"
            "| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet E835`, `Xeon 6`, `Rules D1-D10 v3.2` |\n"
            "| **Drivers & Subsystems** | `ice`, `irdma`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |\n"
            f"| **Validation / Patch IDs** | `{doc_id}`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |\n"
            "<!-- METADATA_FOOTER_END -->\n"
        )
        text = text.rstrip() + footer_block
    else:
        # Ensure exact doc_id appears in Validation / Patch IDs row of footer (D7-ID-MATCH)
        f_start = text.find("<!-- METADATA_FOOTER_START -->")
        footer_part = text[f_start:]
        if f"`{doc_id}`" not in footer_part:
            footer_part = re.sub(
                r"(\|\s*\*\*Validation / Patch IDs\*\*\s*\|\s*)([^|]+)(\|)",
                rf"\g<1>`{doc_id}`, \2\3",
                footer_part,
                count=1,
            )
            text = text[:f_start] + footer_part

    return text


def fix_markdown_text(text: str, filepath: Path) -> str:
    text = text.replace("\r\n", "\n")
    text = _ensure_header_and_footer(text, filepath)

    lines = text.splitlines()
    max_cols = _max_cols_for_file(filepath)

    # Pass 1: Process code fences, tables, STE replacements, data-rate spacing
    out_pass1: List[str] = []
    in_fence = False
    table_buf: List[str] = []

    def _flush_table() -> None:
        nonlocal table_buf
        if table_buf:
            out_pass1.extend(_normalize_table_block(table_buf, max_cols))
            table_buf = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            _flush_table()
            in_fence = not in_fence
            out_pass1.append(line)
            continue

        if in_fence:
            out_pass1.append(line)
            continue

        # Detect table row
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            table_buf.append(line)
            continue
        else:
            _flush_table()

        # Apply STE replacements and data-rate spacing outside code spans
        if not stripped.startswith("<!--"):
            for pat, repl in STE_REPLACEMENTS:
                line = pat.sub(repl, line)
            line = re.sub(r"\b(\d+)\s+(GbE|Gb/s)\b", r"\1\2", line)

        out_pass1.append(line)

    _flush_table()

    # Pass 2: MD032 (blank line before lists) and MD013/MD007 (<= 120-col line wrap)
    out_pass2: List[str] = []
    in_fence = False
    in_header = False
    for idx, line in enumerate(out_pass1):
        stripped = line.strip()
        if stripped == "<!-- METADATA_HEADER_START -->":
            in_header = True
        elif stripped == "<!-- METADATA_HEADER_END -->":
            in_header = False

        if stripped.startswith("```"):
            in_fence = not in_fence
            out_pass2.append(line)
            continue

        if in_fence or in_header:
            out_pass2.append(line)
            continue

        # MD032: Ensure blank line before start of a list if previous line is non-empty prose
        is_list_item = bool(re.match(r"^\s*(?:\d+\.\s+|[-*+]\s+)", line))
        if is_list_item and out_pass2:
            prev = out_pass2[-1].strip()
            prev_is_list = bool(re.match(r"^\s*(?:\d+\.\s+|[-*+]\s+)", out_pass2[-1])) or out_pass2[-1].startswith(
                "  "
            )
            if (
                prev != ""
                and not prev_is_list
                and not prev.startswith("<!--")
                and not prev.startswith(">")
            ):
                out_pass2.append("")

        wrapped = _wrap_line_120(line, width=120)
        out_pass2.extend(wrapped)

    return "\n".join(out_pass2).rstrip() + "\n"


def validate_file(filepath: Path, auto_fix: bool = False) -> Tuple[int, List[str]]:
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    if auto_fix:
        fixed = fix_markdown_text(raw, filepath)
        if fixed != raw.replace("\r\n", "\n"):
            filepath.write_text(fixed, encoding="utf-8", newline="\n")
        raw = fixed

    violations: List[str] = []
    lines = raw.replace("\r\n", "\n").splitlines()
    max_cols = _max_cols_for_file(filepath)

    if filepath.name not in EXCLUDED_METADATA_FILES:
        if "<!-- METADATA_HEADER_START -->" not in raw:
            violations.append("D7-HDR: Missing METADATA_HEADER_START..END block")
        if "<!-- METADATA_FOOTER_START -->" not in raw:
            violations.append("D7-FTR: Missing METADATA_FOOTER_START..END block")
        hdr_id_m = re.search(r"\*\*Document ID\*\*:\s*`([^`]+)`", raw)
        if hdr_id_m:
            doc_id = hdr_id_m.group(1)
            f_start = raw.find("<!-- METADATA_FOOTER_START -->")
            if f_start >= 0 and f"`{doc_id}`" not in raw[f_start:]:
                violations.append(f"D7-ID-MATCH: Header Document ID '{doc_id}' not found verbatim in Footer")

    in_fence = False
    in_header = False
    for i, line in enumerate(lines, start=1):
        s = line.strip()
        if s == "<!-- METADATA_HEADER_START -->":
            in_header = True
        elif s == "<!-- METADATA_HEADER_END -->":
            in_header = False
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            cells = _split_table_row(line)
            if len(cells) > max_cols:
                violations.append(f"L{i} D5-COLS: Table row has {len(cells)} columns (max {max_cols})")
            if _is_separator_row(cells):
                if any(c != "---" for c in cells):
                    violations.append(f"L{i} D5-SEP: Non-compact separator row '{line}'")
        elif not in_header and not s.startswith("#") and not s.startswith("<!--"):
            if len(line) > 120 and "http://" not in line and "https://" not in line and "](" not in line:
                violations.append(f"L{i} MD013/D5-WRAP: Line length {len(line)} > 120 chars")

    score = max(0, 100 - len(violations) * 5)
    return score, violations


def collect_markdown_files(target: Path) -> List[Path]:
    if target.is_file():
        return [target]
    return sorted(
        p
        for p in target.rglob("*.md")
        if ".git" not in p.parts and "node_modules" not in p.parts
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Single Source of Truth Markdown Validator & Auto-Fixer (Rules D1-D10 v3.2)"
    )
    parser.add_argument("path", help="Markdown file or directory to validate")
    parser.add_argument("--fix", action="store_true", help="Auto-fix D1-D10 v3.2 formatting violations in place")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    files = collect_markdown_files(target)
    total_violations = 0
    for f in files:
        score, viols = validate_file(f, auto_fix=args.fix)
        total_violations += len(viols)
        rel = f.relative_to(REPO_ROOT) if f.is_relative_to(REPO_ROOT) else f
        if viols:
            print(f"[FAIL] {rel}: {score}/100 ({len(viols)} violation(s))")
            for v in viols[:5]:
                print(f"       - {v}")
        else:
            print(f"[PASS] {rel}: 100/100 (0 violations)")

    print(f"\nValidated {len(files)} Markdown file(s): {total_violations} total violation(s).")
    return 0 if total_violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

# === METADATA_FOOTER_START ===
# Search Keywords: markdown_validator.py, Rules D1-D10 v3.2, D5-COLS, D5-SEP, D5-TOKEN, MD013, MD007, MD032, D7-ID-MATCH, ASD-STE100
# Drivers & Subsystems: ice, irdma, iavf, HevyOne, netperf_copilot documentation
# Related Units / Patches: DOC-TEMPLATE-SUITE-INDEX-000, D1-D10 v3.2
# Created / Last-Updated: 2026-11-09 / 2026-11-09
# === METADATA_FOOTER_END ===
