#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: markdown_validator.py
# Created Date: 2026-02-02
# Last Updated Date: 2026-11-08
# Version: v2.1
# Status: Production Validated (Single Source of Truth)
# Target Scope: HevyOne, HevyHitter, nsg_lab_tracker, PDF_REPO, and all 22 Tracked Repositories
# Summary: Canonical zero-horizontal-scroll Markdown quality validator and auto-fixer enforcing compact | --- | tables, no space-padding, <=5/<=3 column consolidation, short basename links, Mermaid syntax, and Intel(R) Ethernet Branding Rules D1-D5 v2.2.
# === METADATA_HEADER_END ===
"""
Single Source of Truth Markdown Quality Validator & Auto-Fixer (v2.1).

Enforces across all repositories:
  1. D5-SEP (Compact Table Separator): Always use `| --- |` with single-space margins;
     never use `| ------ |`, `| :--- |`, `|---:|`, or `|---|`.
  2. D5-PAD (No Space-Padded Table Alignment): Never pad table cells with trailing/leading
     spaces (`.ljust()`) to visually align vertical pipes (`|`) across rows.
  3. D5-COLS (Zero Horizontal Scroll Column Count): Keep tables to `<= 5` columns in
     standard repo docs (or `<= 3` columns in `--strict-3col` portrait PDF mode) by
     consolidating secondary columns vertically with `<br>`.
  4. D5-TOKEN (No Unbreakable Table Tokens or Multi-Word Prose Backticks):
     - Shorten long inline-code link labels (`[path/to/file.py](url)` -> `[file.py](url)`).
     - Unwrap multi-word prose descriptions wrapped in backticks inside table cells.
     - Prevent unbreakable single tokens (`> 40` chars in 3+ column tables) inside table cells.
  5. D1-D4 (Intel(R) Ethernet Branding): Prohibit internal codenames (`Columbiaville`) in prose.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "ice-2.7.7",
    "irdma-2.7.201",
    "dpdk",
    "dpdk-pmd",
    "html",
    "pdf",
    "archive",
    "AntigravityFiles",
    "DO_NOT_COMMIT_TO_GITHUB",
}

SUPPORTED_MERMAID_TYPES = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "stateDiagram-v2",
    "stateDiagram",
    "classDiagram",
    "erDiagram",
    "xychart-beta",
)


def _split_table_row(line: str) -> List[str]:
    r"""Split a Markdown table row `| a | b |` into raw cell strings, respecting escaped `\|` and pipes inside inline backticks `` `...` ``."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith(r"\|"):
        s = s[:-1]
    cells: List[str] = []
    cur: List[str] = []
    in_tick = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "`" and (i == 0 or s[i - 1] != "\\"):
            in_tick = not in_tick
            cur.append(ch)
        elif ch == "|" and not in_tick and (i == 0 or s[i - 1] != "\\"):
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur))
    return cells


def _is_separator_row(cells: List[str]) -> bool:
    if not cells:
        return False
    non_empty = [c.strip().replace(" ", "") for c in cells if c.strip()]
    if not non_empty:
        return False
    return all(bool(re.match(r"^:?-{2,}:?$", c)) for c in non_empty)


def _chunk_long_identifier(text: str, chunk_size: int = 26) -> str:
    """Split a long identifier (`0001-ice-snc-numa-...`) at delimiter boundaries into `<= chunk_size` segments separated by `<wbr>`."""
    parts = re.split(r"([/_\-.:,])", text)
    segments: List[str] = []
    cur = ""
    for p in parts:
        if len(cur) + len(p) > chunk_size and cur:
            segments.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        segments.append(cur)
    final_segs: List[str] = []
    for seg in segments:
        if len(seg) <= chunk_size:
            final_segs.append(seg)
        else:
            for j in range(0, len(seg), chunk_size):
                final_segs.append(seg[j : j + chunk_size])
    return "<wbr>".join(final_segs)


def _clean_cell_tokens(cell: str, max_token_len: int = 40) -> Tuple[str, List[str]]:
    """
    Normalize a single table cell to prevent horizontal scrolling:
      1. Normalize `<br/>` / `<br />` to `<br>`
      2. Shorten Markdown link labels that are long file paths or raw URLs
      3. Unwrap multi-word prose sentences erroneously wrapped in backticks inside table cells
      4. Insert `<wbr>` or space breakpoints in remaining unbreakable tokens > max_token_len
    """
    fixes: List[str] = []
    updated = re.sub(r"<br\s*/?>", "<br>", cell.strip(), flags=re.IGNORECASE)

    def _shorten_link_label(m: re.Match[str]) -> str:
        raw_label = m.group(1).strip()
        url = m.group(2).strip()
        inner = raw_label.strip("`").strip("*")
        if inner.startswith(("http://", "https://")) and len(inner) > 28:
            segs = [s for s in inner.split("://", 1)[-1].rstrip("/").split("/") if s]
            short_lbl = f"{segs[0]}/{segs[-1][:18]}" if len(segs) >= 2 else inner[:28]
            fixes.append(f"Shortened URL link label '{inner[:28]}...' -> '{short_lbl}'")
            return f"[{short_lbl}]({url})"
        if "/" in inner and len(inner) > 24:
            base = posixpath.basename(inner.rstrip("/"))
            if base and len(base) >= 3:
                fixes.append(f"Shortened path link label '{inner}' -> '{base}'")
                if len(base) >= max_token_len - 4:
                    base = _chunk_long_identifier(base, chunk_size=20)
                if raw_label.startswith("`") and raw_label.endswith("`") and "<wbr>" not in base:
                    return f"[`{base}`]({url})"
                return f"[{base}]({url})"
        if " " not in inner and len(inner) >= max_token_len - 4:
            human = inner.replace("_", " ").replace("-", " ")
            fixes.append(f"Humanized long link label '{inner[:28]}...'")
            return f"[{human}]({url})"
        return m.group(0)

    while re.search(r"\]\(\[[^\]]*\]\(([^)]+)\)\)", updated):
        updated = re.sub(r"\]\(\[[^\]]*\]\(([^)]+)\)\)", r"](\1)", updated)
        fixes.append("Repaired nested markdown link wrapper")

    updated = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _shorten_link_label, updated)

    protected_links: List[str] = []

    def _save_link(m: re.Match[str]) -> str:
        idx = len(protected_links)
        protected_links.append(m.group(0))
        return f"@@LINK_{idx}@@"

    updated = re.sub(r"\[[^\]]+\]\([^)]+\)", _save_link, updated)

    def _unwrap_or_break_backticks(m: re.Match[str]) -> str:
        inner = m.group(1)
        words = inner.split()
        if (
            len(words) >= 6
            and len(inner) > max_token_len
            and not any(ch in inner for ch in ("--", "$", "=", "|", ";", "&&", "/", "\\"))
        ):
            fixes.append(f"Unwrapped multi-word prose backticks: '{inner[:30]}...'")
            return inner
        if any(len(w) >= max_token_len - 10 for w in re.split(r"[\s]|<wbr>", inner)):
            if " " not in inner:
                if "/" in inner and not inner.startswith(("http://", "https://", "/sys/", "/proc/", "/dev/", "/lib/", "/etc/")):
                    base = posixpath.basename(inner.rstrip("/"))
                    if base and len(base) >= 4 and "." in base and len(base) < max_token_len - 4:
                        fixes.append(f"Shortened inline code path '{inner}' -> '{base}'")
                        return f"`{base}`"
                if "," in inner:
                    fixes.append(f"Spaced comma-separated code token '{inner[:28]}...'")
                    return "`" + "`, `".join(p.strip() for p in inner.split(",") if p.strip()) + "`"
                if inner.endswith(".md"):
                    stem = inner[:-3].replace("_", " ").replace("-", " ")
                    fixes.append(f"Humanized long .md code token '{inner[:28]}...'")
                    return f"**{stem}** (`.md`)"
                chunked = _chunk_long_identifier(inner.replace("<wbr>", ""), chunk_size=20)
                fixes.append(f"Added <wbr> breakpoints to long code token '{inner[:28]}...'")
                return f"`{chunked}`"
            else:
                new_w = [
                    _chunk_long_identifier(w.replace("<wbr>", ""), chunk_size=20)
                    if len(w.replace("<wbr>", "")) >= max_token_len - 4
                    else w
                    for w in words
                ]
                return "`" + " ".join(new_w) + "`"
        return m.group(0)

    updated = re.sub(r"`([^`]+)`", _unwrap_or_break_backticks, updated)

    def _linkify_bare_url(m: re.Match[str]) -> str:
        prefix = m.group(1)
        url = m.group(2).rstrip(".,;)")
        trailing = m.group(2)[len(url) :]
        if len(url) <= 36:
            return m.group(0)
        parsed_path = url.split("://", 1)[-1].rstrip("/")
        segs = [s for s in parsed_path.split("/") if s]
        if len(segs) >= 3 and segs[0] == "github.com":
            if len(segs) >= 5 and segs[3] in ("blob", "tree"):
                lbl = segs[-1][:26]
            else:
                lbl = f"{segs[1]}/{segs[2]}"[:26]
        elif len(segs) >= 2:
            lbl = f"{segs[0]}/{segs[-1][:16]}"[:28]
        else:
            lbl = segs[0][:26] if segs else "Link"
        fixes.append(f"Converted bare URL '{url[:28]}...' -> '[{lbl}](...)'")
        return f"{prefix}[{lbl}]({url}){trailing}"

    temp = re.sub(r'(^|[\s(>])(https?://[^\s)<>"]+)', _linkify_bare_url, updated)
    parts = temp.split("<br>")
    new_parts: List[str] = []
    for part in parts:
        tokens = part.split(" ")
        new_tokens: List[str] = []
        for tok in tokens:
            sub_toks = [st.replace("**", "").replace("*", "") for st in tok.split("<wbr>")]
            if "@@LINK_" in tok or all(len(st) <= max_token_len for st in sub_toks):
                new_tokens.append(tok)
            else:
                chunked = _chunk_long_identifier(tok, chunk_size=20)
                fixes.append(f"Added <wbr> in '{tok[:28]}...'")
                new_tokens.append(chunked)
        new_parts.append(" ".join(new_tokens))
    temp = "<br>".join(new_parts)
    for idx, lnk in enumerate(protected_links):
        temp = temp.replace(f"@@LINK_{idx}@@", lnk)

    return temp, fixes


def _consolidate_table_rows(rows: List[List[str]], max_cols: int) -> List[List[str]]:
    """
    Consolidate a parsed table (header + body rows, excluding separator) so each row
    has at most `max_cols` columns by stacking columns `max_cols - 1 .. N` into the last column
    using `<br><strong>Header:</strong> Value`.
    """
    if not rows or max(len(r) for r in rows) <= max_cols:
        return rows
    headers = [c.strip() for c in rows[0]]
    keep = max_cols - 1
    head_kept = headers[:keep]
    merged_header = " / ".join(h for h in headers[keep:] if h) or "Details"
    new_rows: List[List[str]] = [head_kept + [merged_header]]

    for r in rows[1:]:
        padded = [c.strip() for c in r] + [""] * (len(headers) - len(r))
        row_kept = padded[:keep]
        tail_parts: List[str] = []
        for col_idx in range(keep, len(headers)):
            val = padded[col_idx].strip()
            hdr = headers[col_idx].strip().strip("*")
            if not val or val in ("-", "—", "N/A"):
                continue
            if hdr:
                tail_parts.append(f"**{hdr}**: {val}")
            else:
                tail_parts.append(val)
        merged_cell = "<br>".join(tail_parts) if tail_parts else (padded[keep] if keep < len(padded) else "—")
        new_rows.append(row_kept + [merged_cell])
    return new_rows


def _extract_unbroken_tokens(cell: str) -> List[str]:
    """Return visible unbroken tokens in `cell` after splitting on spaces, `<br>`, `<br/>`, and `<wbr>`."""
    vis = re.sub(r"\]\([^)]+\)", "]", cell)
    vis = re.sub(r"<(?:br|wbr)\s*/?>", " ", vis, flags=re.IGNORECASE)
    vis = vis.replace("**", "").replace("*", "")
    return vis.split()


def validate_and_fix_markdown_text(
    text: str,
    auto_fix: bool = False,
    max_cols: int = 5,
    max_token_len: int = 40,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Validate (and optionally auto-fix) Markdown content against the Single Source of Truth
    Zero-Horizontal-Scroll & Intel(R) Ethernet Branding Rules (D1-D5 v2.2).
    """
    lines = text.splitlines()
    issues: List[Dict[str, Any]] = []
    out_lines: List[str] = []
    in_code = False

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            in_code = not in_code
            out_lines.append(line.rstrip())
            i += 1
            continue

        if in_code:
            out_lines.append(line)
            i += 1
            continue

        if re.search(r"\bColumbiaville\b", line, re.IGNORECASE):
            lower_line = line.lower()
            if not any(
                kw in lower_line
                for kw in ("prohibited", "codename", "incorrect", "never", "instead of", "resolver", "columbiaville ->")
            ):
                issues.append(
                    {
                        "rule": "D2 (Prohibited Internal Codename)",
                        "line": i + 1,
                        "message": "Use 'Intel® Ethernet Controller E835' instead of internal codenames.",
                    }
                )
                if auto_fix:
                    line = re.sub(r"\bColumbiaville-2\b", "Intel® Ethernet Controller E835", line, flags=re.IGNORECASE)
                    line = re.sub(r"\bColumbiaville\b", "Intel® Ethernet Controller E835", line, flags=re.IGNORECASE)

        if s.startswith("|") and s.endswith("|") and len(s) > 2:
            tbl_lines: List[Tuple[int, str]] = []
            while i < n:
                cur_s = lines[i].strip()
                if cur_s.startswith("|") and cur_s.endswith("|") and len(cur_s) > 2:
                    cur_ln = lines[i]
                    if auto_fix and "columbiaville" in cur_ln.lower() and not any(
                        kw in cur_ln.lower()
                        for kw in ("prohibited", "codename", "incorrect", "never", "instead of", "resolver", "columbiaville ->")
                    ):
                        cur_ln = re.sub(r"\bColumbiaville-2\b", "Intel® Ethernet Controller E835", cur_ln, flags=re.IGNORECASE)
                        cur_ln = re.sub(r"\bColumbiaville\b", "Intel® Ethernet Controller E835", cur_ln, flags=re.IGNORECASE)
                    tbl_lines.append((i + 1, cur_ln))
                    i += 1
                else:
                    break

            parsed_rows: List[Tuple[int, List[str], bool]] = []
            has_sep = False
            for line_no, raw_ln in tbl_lines:
                raw_cells = _split_table_row(raw_ln)
                is_sep = _is_separator_row(raw_cells)
                if is_sep:
                    has_sep = True
                parsed_rows.append((line_no, raw_cells, is_sep))

            data_rows_only: List[List[str]] = []
            for line_no, raw_cells, is_sep in parsed_rows:
                stripped_cells = [c.strip() for c in raw_cells]
                if is_sep:
                    if any(c != "---" for c in stripped_cells) or any(rc != " --- " for rc in raw_cells):
                        issues.append(
                            {
                                "rule": "D5-SEP (Non-Compact Table Separator)",
                                "line": line_no,
                                "message": "Table separator row must use compact '| --- |' cells without ':---' or multi-dash padding.",
                            }
                        )
                else:
                    if any(
                        (len(rc) - len(rc.lstrip(" ")) >= 2) or (len(rc) - len(rc.rstrip(" ")) >= 2)
                        for rc in raw_cells
                        if rc.strip()
                    ):
                        issues.append(
                            {
                                "rule": "D5-PAD (Space-Padded Table Alignment)",
                                "line": line_no,
                                "message": "Table cells must use single-space margins ('| cell |') without space-padding to align pipes.",
                            }
                        )
                    if len(stripped_cells) > max_cols:
                        issues.append(
                            {
                                "rule": f"D5-COLS (Max {max_cols} Table Columns)",
                                "line": line_no,
                                "message": f"Table row has {len(stripped_cells)} columns (max allowed is {max_cols} to prevent horizontal scrolling).",
                            }
                        )
                    eff_limit = max_token_len if len(stripped_cells) >= 3 else 68
                    for c in stripped_cells:
                        for tok in _extract_unbroken_tokens(c):
                            if len(tok) > eff_limit:
                                issues.append(
                                    {
                                        "rule": "D5-TOKEN (Unbreakable Table Token)",
                                        "line": line_no,
                                        "message": f"Unbreakable token of length {len(tok)} in table cell: '{tok[:50]}'",
                                    }
                                )
                    data_rows_only.append(stripped_cells)

            if auto_fix and has_sep and data_rows_only:
                if max(len(r) for r in data_rows_only) > max_cols:
                    data_rows_only = _consolidate_table_rows(data_rows_only, max_cols=max_cols)
                col_count = len(data_rows_only[0])
                eff_limit = max_token_len if col_count >= 3 else 68
                cleaned_rows: List[List[str]] = []
                for r in data_rows_only:
                    padded = r + [""] * (col_count - len(r))
                    cleaned_cells = [_clean_cell_tokens(c, max_token_len=eff_limit)[0] for c in padded[:col_count]]
                    cleaned_rows.append(cleaned_cells)
                out_lines.append("| " + " | ".join(cleaned_rows[0]) + " |")
                out_lines.append("| " + " | ".join(["---"] * col_count) + " |")
                for r in cleaned_rows[1:]:
                    out_lines.append("| " + " | ".join(r) + " |")
            else:
                for _lno, raw_ln in tbl_lines:
                    out_lines.append(raw_ln.rstrip())
            continue

        out_lines.append(line.rstrip())
        i += 1

    fixed_text = "\n".join(out_lines)
    if text.endswith("\n"):
        fixed_text += "\n"

    if auto_fix:
        _, remaining = validate_and_fix_markdown_text(
            fixed_text, auto_fix=False, max_cols=max_cols, max_token_len=max_token_len
        )
        return fixed_text, remaining

    return fixed_text, issues


def validate_mermaid_blocks(markdown_text: str) -> Dict[str, Any]:
    """Validate Mermaid fenced code blocks for supported diagram types."""
    issues: List[Dict[str, Any]] = []
    in_mermaid = False
    block_start = 0
    buf: List[str] = []

    for idx, line in enumerate(markdown_text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```mermaid"):
            in_mermaid = True
            block_start = idx
            buf = []
            continue
        if in_mermaid and s.startswith("```"):
            in_mermaid = False
            non_comment = [ln.strip() for ln in buf if ln.strip() and not ln.strip().startswith("%%")]
            if non_comment:
                first = non_comment[0].split()[0]
                if first not in SUPPORTED_MERMAID_TYPES:
                    issues.append(
                        {
                            "rule": "MERMAID-TYPE",
                            "line": block_start + 1,
                            "message": f"Unsupported Mermaid diagram type '{first}'. Allowed: {', '.join(SUPPORTED_MERMAID_TYPES)}",
                        }
                    )
            continue
        if in_mermaid:
            buf.append(line)

    return {"valid": len(issues) == 0, "issue_count": len(issues), "issues": issues}


def check_relative_links(file_path: Path) -> Dict[str, Any]:
    """Check relative Markdown file links in `file_path`."""
    if not file_path.exists():
        return {"valid": False, "error": f"File not found: {file_path}"}
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    broken: List[Dict[str, Any]] = []
    in_code = False
    for idx, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", line):
            target = m.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#", "conversation://")):
                continue
            clean = target.split("#", 1)[0].split("?", 1)[0].strip()
            if not clean:
                continue
            if clean.startswith("file:///"):
                resolved = Path(urllib.parse.unquote(clean[len("file:///") :]))
            else:
                resolved = (file_path.parent / clean).resolve()
            if not resolved.exists():
                broken.append({"line": idx, "target": target})
    return {"valid": len(broken) == 0, "broken_count": len(broken), "broken_links": broken}


def calculate_quality_score(violations: List[Any]) -> int:
    """Returns 0-100 quality score."""
    if not violations:
        return 100
    score = 100 - (len(violations) * 2)
    return max(0, score)


def check_markdown_quality(
    file_path: str,
    auto_fix: bool = False,
    max_cols: int = 5,
    max_token_len: int = 40,
) -> Dict[str, Any]:
    """Analyze a Markdown file for table scroll, padding, separator, and branding violations."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {"error": f"File not found: {file_path}", "quality_score": 0}

    original_text = p.read_text(encoding="utf-8", errors="ignore")
    _, initial_issues = validate_and_fix_markdown_text(
        original_text, auto_fix=False, max_cols=max_cols, max_token_len=max_token_len
    )

    if auto_fix:
        fixed_text, remaining_issues = validate_and_fix_markdown_text(
            original_text, auto_fix=True, max_cols=max_cols, max_token_len=max_token_len
        )
        if fixed_text != original_text:
            p.write_text(fixed_text, encoding="utf-8")
        return {
            "file": str(p),
            "valid": len(remaining_issues) == 0,
            "original_violations": len(initial_issues),
            "remaining_violations": len(remaining_issues),
            "fixes_applied": max(0, len(initial_issues) - len(remaining_issues)),
            "details": remaining_issues[:15],
            "quality_score": calculate_quality_score(remaining_issues),
        }

    return {
        "file": str(p),
        "valid": len(initial_issues) == 0,
        "violations": len(initial_issues),
        "details": initial_issues[:15],
        "quality_score": calculate_quality_score(initial_issues),
    }


def validate_all_documentation(
    root_dir: str = ".",
    auto_fix: bool = False,
    max_cols: int = 5,
    max_token_len: int = 40,
) -> Dict[str, Any]:
    """Scan directory tree for Markdown quality issues and optionally auto-fix all files."""
    root_path = Path(root_dir).resolve()
    markdown_files: List[Path] = []
    for r, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in sorted(files):
            if f.endswith(".md"):
                markdown_files.append(Path(r) / f)

    results: List[Dict[str, Any]] = []
    total_violations = 0
    total_fixes = 0

    for md_file in markdown_files:
        res = check_markdown_quality(
            str(md_file), auto_fix=auto_fix, max_cols=max_cols, max_token_len=max_token_len
        )
        v_count = res.get("remaining_violations" if auto_fix else "violations", 0)
        total_fixes += res.get("fixes_applied", 0)
        if v_count > 0:
            total_violations += v_count
            results.append(
                {
                    "file": md_file.relative_to(root_path).as_posix(),
                    "violations": v_count,
                    "score": res["quality_score"],
                    "details": res.get("details", [])[:5],
                }
            )

    scores = [100] * (len(markdown_files) - len(results)) + [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 100.0

    return {
        "root_dir": str(root_path),
        "max_cols": max_cols,
        "total_files": len(markdown_files),
        "files_with_issues": len(results),
        "total_violations": total_violations,
        "total_fixes_applied": total_fixes,
        "average_score": round(avg_score, 1),
        "problem_files": sorted(results, key=lambda x: x["violations"], reverse=True)[:15],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single Source of Truth Markdown Quality Validator & Zero-Scroll Table Fixer (v2.1)"
    )
    parser.add_argument("path", nargs="?", default=".", help="File or directory to check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix compact tables, cell padding, wide columns, and long tokens")
    parser.add_argument("--score", action="store_true", help="Show quality score only")
    parser.add_argument("--max-cols", type=int, default=5, help="Maximum allowed columns per table (default: 5; use 3 for portrait PDF mode)")
    parser.add_argument("--strict-3col", action="store_true", help="Shortcut for --max-cols 3 (portrait PDF Rule D5)")
    parser.add_argument("--max-token-len", type=int, default=40, help="Max unbroken token length in table cells (default: 40)")

    args = parser.parse_args()
    max_cols = 3 if args.strict_3col else args.max_cols

    if os.path.isfile(args.path):
        result = check_markdown_quality(
            args.path, auto_fix=args.fix, max_cols=max_cols, max_token_len=args.max_token_len
        )
        if args.score:
            print(f"Quality Score: {result['quality_score']}/100")
        else:
            print(json.dumps(result, indent=2))
    else:
        result = validate_all_documentation(
            args.path, auto_fix=args.fix, max_cols=max_cols, max_token_len=args.max_token_len
        )
        if args.score:
            print(f"Quality Score: {result['average_score']}/100")
        else:
            print(json.dumps(result, indent=2))

        if result["files_with_issues"] > 0:
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()

# === METADATA_FOOTER_START ===
# Search Keywords: markdown_validator, D5-SEP, D5-PAD, D5-COLS, D5-TOKEN, compact tables, zero horizontal scroll
# Drivers & Subsystems: documentation, markdownlint, mcp-markdown-server, hevyone-kb-mcp
# Related Units / Patches: HH-BR-016, HH-BR-019, Rule D1-D5 v2.2
# Created / Last-Updated: 2026-02-02 / 2026-11-08
# === METADATA_FOOTER_END ===
