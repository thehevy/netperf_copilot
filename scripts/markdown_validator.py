#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: scripts/markdown_validator.py
# Created Date: 2026-02-02
# Last Updated Date: 2026-11-09
# Version: v3.1
# Status: Production Validated (Single Source of Truth)
# Target Scope: Public & Open-Source Technical Documentation (Rules D1-D10 v3.2)
# Summary: Canonical zero-horizontal-scroll Markdown quality validator and auto-fixer enforcing compact | --- | tables, D5-WRAP 120-column prose/list wrapping (MD013/MD007/MD032), escaped-pipe safety (D5-PIPE), Mermaid syntax, and Documentation Rules D1-D10 v3.2.
# === METADATA_HEADER_END ===
"""
Single Source of Truth Markdown, ASD-STE100 Simplified Technical English & Config/Script Validator (v3.1).

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
  5. D5-WRAP & D5-PIPE (MD013 120-Char Line Wrapping, MD007 List Indentation, MD032 List Blank Lines, Pipe Safety):
     - Wrap prose, list items, and blockquotes at `<= 120` chars (`--max-line-len 120`) without
       splitting Markdown links `[label](url)` or inline code spans `` `...` ``.
     - Align list continuation lines to the exact marker width (`MD007`) and enforce blank lines
       around lists (`MD032`, including `>` before lists inside blockquotes).
     - Preserve escaped pipes (`\\|`) and pipes inside inline backticks in table rows (`D5-PIPE`).
  6. D1-D4 (Intel(R) Ethernet Branding) & D6-D10 (ASD-STE100, Metadata, Bash, YAML, Python Safety).
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
        "dpdk",
    "dpdk-pmd",
    "html",
    "pdf",
    "archive",
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

_ATOMIC_SPAN_RE = re.compile(
    r"(`+[^`]+`+|!?\[(?:[^\[\]]|`[^`]*`|\*\*[^*]+\*\*)+\]\([^)\s]+\))"
)


def _sanitize_table_line(line: str) -> str:
    """Repair truncated backticks in link labels and corrupted `\\ |` splits inside inline backticks."""
    s = re.sub(r"\(`\.\.\.\]", "...]", line)
    s = re.sub(r"`([^`|]*?)\.\.\.\]", r"\1...]", s)
    s = re.sub(
        r"`([^`]*?)\\\s+\|\s+([^`]*?)`",
        r"`\1 \\| \2`",
        s,
    )
    return s


# ASD-STE100 (Rule D6-LEX) deterministic prose replacements (case-preserving)
STE_LEXICAL_RULES: List[Tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\butilizes\b", re.IGNORECASE), "uses", "utilizes -> uses"),
    (re.compile(r"\butilized\b", re.IGNORECASE), "used", "utilized -> used"),
    (re.compile(r"\butilizing\b", re.IGNORECASE), "using", "utilizing -> using"),
    (re.compile(r"\butilize\b", re.IGNORECASE), "use", "utilize -> use"),
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to", "in order to -> to"),
    (re.compile(r"\bprior to\b", re.IGNORECASE), "before", "prior to -> before"),
    (re.compile(r"\bsubsequent to\b", re.IGNORECASE), "after", "subsequent to -> after"),
]


def _apply_ste_lexical_replacements(line: str) -> Tuple[str, List[str]]:
    """Apply deterministic ASD-STE100 (Rule D6-LEX) replacements to prose outside inline code and URLs."""
    s = line.strip()
    if not s or s.startswith(("<!--", "```", "|")):
        return line, []

    protected: List[str] = []

    def _mask(m: re.Match[str]) -> str:
        idx = len(protected)
        protected.append(m.group(0))
        return f"@@STE_PROT_{idx}@@"

    masked = re.sub(r"`[^`]+`|\[[^\]]+\]\([^)]+\)|https?://\S+", _mask, line)
    applied: List[str] = []

    for pat, repl, desc in STE_LEXICAL_RULES:
        def _case_repl(m: re.Match[str], r: str = repl) -> str:
            orig = m.group(0)
            if orig.isupper():
                return r.upper()
            if orig[0].isupper():
                return r.capitalize()
            return r

        if pat.search(masked):
            masked = pat.sub(_case_repl, masked)
            applied.append(desc)

    for idx, val in enumerate(protected):
        masked = masked.replace(f"@@STE_PROT_{idx}@@", val)
    return masked, applied


def evaluate_ste_and_code_blocks(markdown_text: str) -> Dict[str, Any]:
    """
    Evaluate a Markdown document against Rules D6-D10 (v3.1):
      - D6 (ASD-STE100 Simplified Technical English): sentence length (<=20w procedural, <=25w descriptive),
        active voice, unambiguous modals, and controlled STE vocabulary.
      - D7 (Diataxis/DITA & Uniform Metadata): METADATA_HEADER_START and METADATA_FOOTER_START presence.
      - D8 (Bash/ShellCheck): strict mode (`set -Eeuo pipefail` / `set -euo pipefail`) in multi-line scripts.
      - D9 (YAML 1.2 / JSON Schema): quoted boolean/sexagesimal traps (`"on"`, `"off"`, `"0:0 3:3"`).
      - D10 (Python Automation Safety): explicit `timeout=` on `subprocess.run` / `check_output`.
    """
    in_code = False
    code_lang = ""
    code_start = 0
    code_buf: List[str] = []

    unapproved_ste_hits: List[Dict[str, Any]] = []
    procedural_over_20w = 0
    descriptive_over_25w = 0
    passive_voice_hits = 0
    ambiguous_modal_hits = 0
    total_sentences = 0
    total_words = 0
    code_config_warnings: List[Dict[str, Any]] = []

    passive_re = re.compile(
        r"\b(?:is|are|was|were|be|been|being)\s+(?:configured|set|executed|performed|utilized|created|triggered|caused)\b",
        re.IGNORECASE,
    )
    modal_re = re.compile(r"\b(?:should|might|ought to)\b", re.IGNORECASE)

    lines = markdown_text.splitlines()
    for idx, raw_line in enumerate(lines, 1):
        s = raw_line.strip()
        if s.startswith("```"):
            if not in_code:
                in_code = True
                code_lang = s[3:].strip().lower().split()[0] if len(s) > 3 else ""
                code_start = idx
                code_buf = []
            else:
                block_text = "\n".join(code_buf)
                if code_lang in ("yaml", "yml"):
                    for b_idx, b_ln in enumerate(code_buf, code_start + 1):
                        if re.search(r":\s+(?:on|off|yes|no)\s*(?:#.*)?$", b_ln, re.IGNORECASE):
                            code_config_warnings.append(
                                {
                                    "rule": "D9-YAML (Unquoted Boolean Trap)",
                                    "line": b_idx,
                                    "message": "Quote YAML boolean-like string scalars (on, off, yes, no) to prevent YAML 1.1 Norway-problem coercion.",
                                }
                            )
                        if re.search(r":\s+\d+:\d+(?:\s+\d+:\d+)*\s*$", b_ln):
                            code_config_warnings.append(
                                {
                                    "rule": "D9-YAML (Unquoted Sexagesimal Colon Map)",
                                    "line": b_idx,
                                    "message": "Quote colon-delimited QoS/PCI maps (e.g., 0:0 3:3) in YAML.",
                                }
                            )
                elif code_lang in ("bash", "sh", "shell"):
                    has_shebang = any(ln.strip().startswith("#!") for ln in code_buf[:2])
                    if has_shebang and len(code_buf) >= 6:
                        if not any("set -" in ln and "pipefail" in ln for ln in code_buf[:12]):
                            code_config_warnings.append(
                                {
                                    "rule": "D8-STRICT (Missing Bash Strict Mode)",
                                    "line": code_start + 1,
                                    "message": "Multi-line shell scripts with shebang must include 'set -Eeuo pipefail' (or 'set -euo pipefail').",
                                }
                            )
                elif code_lang in ("python", "py"):
                    if ("subprocess.run(" in block_text or "subprocess.check_output(" in block_text) and "timeout=" not in block_text:
                        code_config_warnings.append(
                            {
                                "rule": "D10-SUBPROC (Missing Subprocess Timeout)",
                                "line": code_start + 1,
                                "message": "Python subprocess.run/check_output calls must specify an explicit timeout= parameter (DOC-RULE-D5).",
                            }
                        )
                in_code = False
                code_lang = ""
                code_buf = []
            continue

        if in_code:
            code_buf.append(raw_line)
            continue

        if not s or s.startswith(("#", "|", "<!--", "---", "> [!")):
            continue

        clean = re.sub(r"`[^`]+`", "CODE_TOK", s)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        for pat, _repl, desc in STE_LEXICAL_RULES:
            if pat.search(clean):
                unapproved_ste_hits.append({"rule": "D6-LEX (Unapproved STE Term)", "line": idx, "message": f"Use STE approved term ({desc})."})

        is_proc = bool(re.match(r"^(?:\d+\.|[-*])\s+", clean))
        clean_body = re.sub(r"^(?:\d+\.|[-*])\s+", "", clean)
        for sent in re.split(r"(?<=[.!?])\s+", clean_body):
            words = [w for w in sent.split() if any(ch.isalpha() for ch in w)]
            if len(words) < 3:
                continue
            total_sentences += 1
            total_words += len(words)
            if is_proc and len(words) > 20:
                procedural_over_20w += 1
            elif not is_proc and len(words) > 25:
                descriptive_over_25w += 1
            if passive_re.search(sent):
                passive_voice_hits += 1
            if is_proc and modal_re.search(sent):
                ambiguous_modal_hits += 1

    has_header = "METADATA_HEADER_START" in markdown_text
    has_footer = "METADATA_FOOTER_START" in markdown_text
    header_doc_id: Optional[str] = None
    id_match = True
    if has_header:
        m_hdr = re.search(
            r"METADATA_HEADER_START.*?METADATA_HEADER_END",
            markdown_text,
            flags=re.DOTALL,
        )
        if m_hdr:
            m_id = re.search(r"\*\*Document ID\*\*:\s*`([^`]+)`", m_hdr.group(0))
            if m_id:
                header_doc_id = m_id.group(1).strip()
    if has_header and has_footer and header_doc_id:
        m_ftr = re.search(
            r"METADATA_FOOTER_START.*?METADATA_FOOTER_END",
            markdown_text,
            flags=re.DOTALL,
        )
        if m_ftr and header_doc_id not in m_ftr.group(0):
            id_match = False
            code_config_warnings.append(
                {
                    "rule": "D7-ID-MATCH (Header/Footer Document ID Mismatch)",
                    "line": len(lines),
                    "message": f"Header Document ID '{header_doc_id}' is missing or truncated in METADATA_FOOTER_START..END.",
                }
            )
    avg_words = round(total_words / total_sentences, 1) if total_sentences else 0.0
    penalty = (
        len(unapproved_ste_hits) * 3
        + len(code_config_warnings) * 4
        + min(10, procedural_over_20w)
        + min(10, passive_voice_hits)
        + min(10, ambiguous_modal_hits)
    )
    ste_score = max(0, 100 - penalty)
    return {
        "standard_version": "D1-D10 v3.2 (ASD-STE100 Issue 9 + MD013/MD007/MD032 + D7-ID-MATCH)",
        "ste_score": ste_score,
        "ste_compliant": len(unapproved_ste_hits) == 0 and len(code_config_warnings) == 0,
        "avg_sentence_words": avg_words,
        "total_sentences": total_sentences,
        "procedural_sentences_over_20w": procedural_over_20w,
        "descriptive_sentences_over_25w": descriptive_over_25w,
        "passive_voice_count": passive_voice_hits,
        "ambiguous_modal_count": ambiguous_modal_hits,
        "unapproved_ste_terms": unapproved_ste_hits,
        "code_and_config_warnings": code_config_warnings,
        "metadata_standard_d7": {
            "has_header": has_header,
            "has_footer": has_footer,
            "header_document_id": header_doc_id,
            "id_match": id_match,
        },
    }


def _split_table_row(line: str) -> List[str]:
    r"""Split a Markdown table row `| a | b |` into raw cell strings, respecting escaped `\|` and pipes inside inline backticks `` `...` ``."""
    s = _sanitize_table_line(line).strip()
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
    """Split a long identifier (`example-long-identifier-...`) at delimiter boundaries into `<= chunk_size` segments separated by `<wbr>`."""
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
            if base and len(base) < len(inner):
                fixes.append(f"Shortened path link label '{inner}' -> '{base}'")
                if raw_label.startswith("`") and raw_label.endswith("`"):
                    return f"[`{base}`]({url})"
                return f"[{base}]({url})"
        if len(inner) > max_token_len and " " not in inner and "<wbr>" not in inner:
            chunked = _chunk_long_identifier(inner, chunk_size=26)
            fixes.append(f"Chunked long link label '{inner[:30]}...'")
            return f"[{chunked}]({url})"
        return m.group(0)

    updated = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _shorten_link_label, updated)

    def _unwrap_or_split_backtick(m: re.Match[str]) -> str:
        inner = m.group(1)
        words = inner.split()
        if len(words) >= 6:
            fixes.append(f"Unwrapped {len(words)}-word prose backtick span")
            return inner
        inner_limit = max(24, max_token_len - 4)
        if any(len(w) > inner_limit for w in words):
            new_words: List[str] = []
            for w in words:
                if len(w) > inner_limit:
                    new_words.append(f"`{_chunk_long_identifier(w, chunk_size=24)}`")
                else:
                    new_words.append(f"`{w}`")
            fixes.append(f"Split long token inside backtick span '{inner[:30]}...'")
            return " ".join(new_words)
        return m.group(0)

    updated = re.sub(r"`([^`]+)`", _unwrap_or_split_backtick, updated)

    protected: List[str] = []

    def _protect(m: re.Match[str]) -> str:
        idx = len(protected)
        protected.append(m.group(0))
        return f"@@PROT{idx}@@"

    masked = re.sub(r"\[[^\]]+\]\([^)]+\)|`[^`]+`", _protect, updated)

    def _break_bare_url(m: re.Match[str]) -> str:
        url = m.group(0).rstrip(".,;)")
        trailing = m.group(0)[len(url) :]
        if len(url) <= max_token_len:
            return m.group(0)
        segs = [s for s in url.split("://", 1)[-1].rstrip("/").split("/") if s]
        label = f"{segs[0]}/{segs[-1][:18]}" if len(segs) >= 2 else url[:28]
        fixes.append(f"Converted long bare URL '{url[:30]}...' to compact link")
        return f"[{label}]({url}){trailing}"

    masked = re.sub(r"https?://[^\s<>\"|`]+", _break_bare_url, masked)

    parts = re.split(r"(\s+|<br>|<wbr>)", masked)
    rebuilt: List[str] = []
    for p in parts:
        if not p or p.isspace() or p in ("<br>", "<wbr>") or "@@PROT" in p:
            rebuilt.append(p)
            continue
        vis_len = len(p.replace("**", "").replace("*", ""))
        if vis_len > max_token_len:
            rebuilt.append(_chunk_long_identifier(p, chunk_size=26))
            fixes.append(f"Inserted <wbr> in long token '{p[:30]}...'")
        else:
            rebuilt.append(p)
    masked = "".join(rebuilt)

    for idx, orig in enumerate(protected):
        if orig.startswith("`") and orig.endswith("`") and len(orig) > max_token_len:
            inner = orig[1:-1]
            if " " not in inner:
                orig = _chunk_long_identifier(inner, chunk_size=26)
                fixes.append(f"Converted long single-token code '{inner[:30]}...' to <wbr>-wrapped text")
        masked = masked.replace(f"@@PROT{idx}@@", orig)

    return masked, fixes


def _consolidate_table_rows(rows: List[List[str]], max_cols: int) -> List[List[str]]:
    """Consolidate a table with `> max_cols` columns into `max_cols` columns by stacking overflow columns with `<br>`."""
    if not rows or max(len(r) for r in rows) <= max_cols:
        return rows

    headers = [h.strip() for h in rows[0]]
    keep = max_cols - 1
    tail_headers = [h for h in headers[keep:] if h]
    merged_header = " / ".join(tail_headers) if tail_headers else headers[-1]
    if len(merged_header) > 52 and len(tail_headers) >= 2:
        merged_header = f"{tail_headers[0]} & {tail_headers[-1]}"

    new_rows: List[List[str]] = [headers[:keep] + [merged_header]]
    for r in rows[1:]:
        padded = r + [""] * (len(headers) - len(r))
        row_kept = [c.strip() for c in padded[:keep]]
        tail_parts: List[str] = []
        for h, c in zip(headers[keep:], padded[keep:]):
            val = c.strip()
            if not val or val in ("-", "—", "N/A"):
                continue
            clean_h = h.replace("**", "").strip()
            if clean_h and not val.lower().startswith(clean_h.lower()[:8]):
                tail_parts.append(f"**{clean_h}**: {val}")
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


def _split_top_level_words(text: str) -> List[str]:
    """Split `text` on whitespace while keeping inline code (`...`) and Markdown links (`[...](...)`) atomic."""
    masked = _ATOMIC_SPAN_RE.sub(lambda m: m.group(0).replace(" ", "\x00"), text)
    return [tok.replace("\x00", " ") for tok in masked.split() if tok]


def _parse_wrappable_line_prefix(line: str, in_meta_header: bool = False) -> Optional[Tuple[str, str, str]]:
    """
    If `line` is a wrappable prose, list, or blockquote line, return `(first_prefix, cont_prefix, body)`.
    Returns `None` for headings, tables, comments, horizontal rules, metadata header bullets, or alert headers.
    """
    if in_meta_header:
        return None
    s = line.strip()
    if not s:
        return None
    if s.startswith(("#", "|", "<!--", "```", "~~~")) or s.endswith("-->"):
        return None
    if re.match(r"^(?:-{3,}|\*{3,}|_{3,})$", s):
        return None
    if re.match(r"^\[[^\]]+\]:\s+\S+", s):
        return None
    if re.match(r"^>\s*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", s, re.IGNORECASE):
        return None

    m_bql = re.match(r"^(\s*(?:>\s*)+)((?:[-*+]|\d+\.)\s+)(.*)$", line)
    if m_bql:
        bq = m_bql.group(1)
        marker = m_bql.group(2)
        return bq + marker, bq + (" " * len(marker)), m_bql.group(3)

    m_bq = re.match(r"^(\s*(?:>\s*)+)(.*)$", line)
    if m_bq:
        bq = m_bq.group(1)
        body = m_bq.group(2)
        if not body.strip():
            return None
        return bq, bq, body

    m_lst = re.match(r"^(\s*)((?:[-*+]|\d+\.)\s+)(.*)$", line)
    if m_lst:
        indent = m_lst.group(1)
        marker = m_lst.group(2)
        return indent + marker, indent + (" " * len(marker)), m_lst.group(3)

    m_prose = re.match(r"^(\s*)(.*)$", line)
    if m_prose:
        indent = m_prose.group(1)
        return indent, indent, m_prose.group(2)
    return None


def _wrap_markdown_line(line: str, max_line_len: int = 120, in_meta_header: bool = False) -> Tuple[List[str], bool]:
    """
    Wrap a single Markdown prose/list/blockquote line to `<= max_line_len` characters (`MD013` / `D5-WRAP`),
    preserving atomic `[label](url)` links and `` `code` `` spans and aligning continuation indent (`MD007`).
    Returns `(wrapped_lines, has_breakable_overflow)`.
    """
    if max_line_len <= 0 or len(line) <= max_line_len:
        return [line], False

    parsed = _parse_wrappable_line_prefix(line, in_meta_header=in_meta_header)
    if not parsed:
        return [line], False

    first_prefix, cont_prefix, body = parsed
    words = _split_top_level_words(body)
    if len(words) <= 1:
        return [line], False

    wrapped: List[str] = []
    cur_prefix = first_prefix
    cur_words: List[str] = [words[0]]
    cur_len = len(cur_prefix) + len(words[0])

    for w in words[1:]:
        if cur_len + 1 + len(w) <= max_line_len:
            cur_words.append(w)
            cur_len += 1 + len(w)
        else:
            if re.match(r"^(?:[-*+]|\d+\.)$", w) and len(cur_words) >= 2:
                carry = cur_words.pop()
                wrapped.append(cur_prefix + " ".join(cur_words))
                cur_prefix = cont_prefix
                cur_words = [carry, w]
                cur_len = len(cur_prefix) + len(carry) + 1 + len(w)
            else:
                wrapped.append(cur_prefix + " ".join(cur_words))
                cur_prefix = cont_prefix
                cur_words = [w]
                cur_len = len(cur_prefix) + len(w)

    if cur_words:
        wrapped.append(cur_prefix + " ".join(cur_words))

    return wrapped, len(wrapped) > 1


def validate_and_fix_markdown_text(
    text: str,
    auto_fix: bool = False,
    max_cols: int = 5,
    max_token_len: int = 40,
    max_line_len: int = 120,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Validate (and optionally auto-fix) Markdown content against the Single Source of Truth
    Zero-Horizontal-Scroll, Line-Length Wrapping (MD013/MD007/MD032), and Intel(R) Ethernet Branding Rules (D1-D5 v3.1).
    """
    lines = text.splitlines()
    issues: List[Dict[str, Any]] = []
    out_lines: List[str] = []
    in_code = False
    in_meta_header = False
    active_list_cont_indent: Optional[int] = None

    i = 0
    n = len(lines)
    if n >= 3 and lines[0].strip() == "---":
        fm_end = None
        for idx in range(1, min(n, 100)):
            if lines[idx].strip() == "---":
                fm_end = idx
                break
        if fm_end is not None:
            out_lines.append("---")
            fm_lines: List[str] = []
            for idx in range(1, fm_end):
                raw_fm = lines[idx].rstrip()
                if not raw_fm.strip():
                    continue
                is_yaml_key = bool(re.match(r"^[A-Za-z0-9_-]+\s*:", raw_fm.lstrip()))
                is_yaml_list = raw_fm.lstrip().startswith("- ")
                if not is_yaml_key and not is_yaml_list:
                    if auto_fix and fm_lines:
                        prev_fm = re.sub(r":\s*[>|][-+]?\s*$", ":", fm_lines[-1].rstrip())
                        fm_lines[-1] = prev_fm + " " + raw_fm.strip()
                    else:
                        issues.append(
                            {
                                "rule": "D9-FRONTMATTER (Wrapped or Invalid YAML Frontmatter Line)",
                                "line": idx + 1,
                                "message": "YAML frontmatter key-value pairs must not wrap across unindented lines.",
                            }
                        )
                        fm_lines.append(raw_fm)
                else:
                    fm_lines.append(raw_fm)
            for fm_i, fm_ln in enumerate(fm_lines):
                m_kv = re.match(r"^(\s*[A-Za-z0-9_-]+\s*:\s*)(.+)$", fm_ln)
                if m_kv:
                    k_prefix, v_str = m_kv.group(1), m_kv.group(2).strip()
                    if re.match(r"^[>|][-+]?\s+\S", v_str):
                        if auto_fix:
                            v_str = re.sub(r"^[>|][-+]?\s+", "", v_str)
                            fm_lines[fm_i] = f"{k_prefix}{v_str}"
                        else:
                            issues.append(
                                {
                                    "rule": "D9-FRONTMATTER (Inline Block Scalar Indicator in YAML Frontmatter)",
                                    "line": fm_i + 2,
                                    "message": "Inline '>-' or '|-' block scalar indicator before single-line text is invalid YAML.",
                                }
                            )
                    if not (v_str.startswith(('"', "'", "[")) and v_str.endswith(('"', "'", "]"))) and ": " in v_str:
                        if auto_fix:
                            escaped_v = v_str.replace('"', '\\"')
                            fm_lines[fm_i] = f'{k_prefix}"{escaped_v}"'
                        else:
                            issues.append(
                                {
                                    "rule": "D9-FRONTMATTER (Unquoted Colon in YAML Frontmatter Scalar)",
                                    "line": fm_i + 2,
                                    "message": "Unquoted ': ' inside YAML frontmatter value breaks YAML parsers; quote the value or remove ': '.",
                                }
                            )
            out_lines.extend(fm_lines)
            out_lines.append("---")
            i = fm_end + 1

    while i < n:
        line = lines[i]
        s = line.strip()

        if "METADATA_HEADER_START" in s:
            in_meta_header = True
        elif "METADATA_HEADER_END" in s:
            in_meta_header = False

        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            out_lines.append(line.rstrip())
            active_list_cont_indent = None
            i += 1
            continue

        if in_code:
            out_lines.append(line)
            i += 1
            continue

        if s.startswith("|") and s.endswith("|") and len(s) > 2:
            active_list_cont_indent = None
            tbl_lines: List[Tuple[int, str]] = []
            while i < n:
                cur_s = lines[i].strip()
                if cur_s.startswith("|") and cur_s.endswith("|") and len(cur_s) > 2:
                    cur_ln = lines[i]
                    if re.search(r"`[^`]*?\\\s+\|\s+[^`]*?`", cur_ln):
                        issues.append(
                            {
                                "rule": "D5-PIPE (Corrupted Pipe Inside Table Backtick)",
                                "line": i + 1,
                                "message": "Escaped pipe inside inline code was split into '\\ |'; use '\\|' or '+' inside table backticks.",
                            }
                        )
                    tbl_lines.append((i + 1, cur_ln))
                    i += 1
                else:
                    break

            parsed_rows: List[Tuple[int, List[str], bool]] = []
            has_sep = False
            for line_no, raw_ln in tbl_lines:
                raw_ln = _sanitize_table_line(raw_ln)
                raw_cells = _split_table_row(raw_ln)
                is_sep = _is_separator_row(raw_cells)
                if is_sep:
                    has_sep = True
                parsed_rows.append((line_no, raw_cells, is_sep))

            data_rows_only: List[List[str]] = []
            header_cols = len(parsed_rows[0][1]) if parsed_rows else 0
            for line_no, raw_cells, is_sep in (parsed_rows if has_sep else []):
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
                    eff_limit = max_token_len if min(header_cols, max_cols) >= 3 else 68
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

        if auto_fix:
            line, _ = _apply_ste_lexical_replacements(line)
        line = line.rstrip()
        s = line.strip()

        # Check MD032 (blank line before top-level or blockquote list) & MD007 (list continuation indent)
        if not in_meta_header:
            m_bql = re.match(r"^(\s*>)\s*(?:[-*+]|\d+\.)\s+", line)
            m_top_lst = re.match(r"^(\s*)((?:[-*+]|\d+\.)\s+)", line)
            if m_bql and out_lines:
                prev = out_lines[-1]
                prev_s = prev.strip()
                if (
                    prev_s.startswith(">")
                    and prev_s != ">"
                    and not re.match(r"^\s*>\s*(?:[-*+]|\d+\.)\s+", prev)
                    and not re.match(r"^\s*>\s{2,}\S", prev)
                ):
                    issues.append(
                        {
                            "rule": "MD032 (Missing Blank Line Before Blockquote List)",
                            "line": i + 1,
                            "message": "Lists inside blockquotes must be preceded by a blank '>' line (MD032).",
                        }
                    )
                    if auto_fix:
                        out_lines.append(m_bql.group(1))
                active_list_cont_indent = None
            elif m_top_lst:
                indent_str, marker_str = m_top_lst.group(1), m_top_lst.group(2)
                if len(indent_str) == 0 and out_lines:
                    prev = out_lines[-1]
                    prev_s = prev.strip()
                    if (
                        prev_s
                        and not prev_s.startswith(("<!--", "#"))
                        and not re.match(r"^\s*(?:[-*+]|\d+\.)\s+", prev)
                        and not prev.startswith("  ")
                    ):
                        issues.append(
                            {
                                "rule": "MD032 (Missing Blank Line Before List)",
                                "line": i + 1,
                                "message": "Lists should be surrounded by blank lines (MD032).",
                            }
                        )
                        if auto_fix:
                            out_lines.append("")
                active_list_cont_indent = len(indent_str) + len(marker_str)
            elif not s or s.startswith(("#", "<!--", "---", ">")):
                active_list_cont_indent = None
            elif active_list_cont_indent is not None:
                m_cont = re.match(r"^( +)(\S.*)$", line)
                if m_cont:
                    actual_indent = len(m_cont.group(1))
                    if actual_indent != active_list_cont_indent and abs(actual_indent - active_list_cont_indent) <= 2:
                        issues.append(
                            {
                                "rule": "MD007 (List Continuation Indentation)",
                                "line": i + 1,
                                "message": f"List continuation line indented by {actual_indent} spaces (expected {active_list_cont_indent} spaces).",
                            }
                        )
                        if auto_fix:
                            line = (" " * active_list_cont_indent) + m_cont.group(2)
                else:
                    active_list_cont_indent = None

        # Check MD013 / D5-WRAP (120-column line length for prose, list items, and blockquotes)
        if max_line_len > 0 and len(line) > max_line_len:
            wrapped_lines, can_wrap = _wrap_markdown_line(
                line, max_line_len=max_line_len, in_meta_header=in_meta_header
            )
            if can_wrap:
                issues.append(
                    {
                        "rule": f"MD013 / D5-WRAP (Line Length > {max_line_len})",
                        "line": i + 1,
                        "message": f"Line length is {len(line)} chars (max {max_line_len}). Wrap prose and list items cleanly.",
                    }
                )
                if auto_fix:
                    out_lines.extend(wrapped_lines)
                    i += 1
                    continue

        out_lines.append(line)
        i += 1

    fixed_text = "\n".join(out_lines)
    if text.endswith("\n"):
        fixed_text += "\n"

    # Rule D7-ID-MATCH: Ensure Header Document ID matches Footer Document ID / Validation IDs
    if "METADATA_HEADER_START" in fixed_text and "METADATA_FOOTER_START" in fixed_text:
        m_hdr = re.search(r"METADATA_HEADER_START.*?METADATA_HEADER_END", fixed_text, flags=re.DOTALL)
        m_ftr = re.search(r"METADATA_FOOTER_START.*?METADATA_FOOTER_END", fixed_text, flags=re.DOTALL)
        if m_hdr and m_ftr:
            m_id = re.search(r"\*\*Document ID\*\*:\s*`([^`]+)`", m_hdr.group(0))
            if m_id:
                hdr_id = m_id.group(1).strip()
                ftr_txt = m_ftr.group(0)
                if hdr_id and hdr_id not in ftr_txt:
                    issues.append(
                        {
                            "rule": "D7-ID-MATCH (Header/Footer Document ID Mismatch)",
                            "line": len(out_lines),
                            "message": f"Header Document ID '{hdr_id}' does not appear in METADATA_FOOTER_START..END.",
                        }
                    )
                    if auto_fix:
                        def _sync_footer_id(m: re.Match[str]) -> str:
                            col1 = m.group(1)
                            if "Document ID" in col1:
                                return f"{col1}`{hdr_id}` {m.group(3)}"
                            return f"{col1}`{hdr_id}`, {m.group(2).strip()} {m.group(3)}"

                        new_ftr = re.sub(
                            r"(\|\s*\*\*(?:Validation / Patch IDs|Document ID)\*\*\s*\|\s*)([^|\n]+)(\|)",
                            _sync_footer_id,
                            ftr_txt,
                            count=1,
                        )
                        if new_ftr != ftr_txt:
                            fixed_text = fixed_text[: m_ftr.start()] + new_ftr + fixed_text[m_ftr.end() :]

    if auto_fix:
        _, remaining = validate_and_fix_markdown_text(
            fixed_text,
            auto_fix=False,
            max_cols=max_cols,
            max_token_len=max_token_len,
            max_line_len=max_line_len,
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
        line_no_inline_code = re.sub(r"`+[^`]+`+", "", line)
        for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", line_no_inline_code):
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
    max_line_len: int = 120,
) -> Dict[str, Any]:
    """Analyze a Markdown file for table scroll, padding, separator, line-length, list, and branding violations."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {"error": f"File not found: {file_path}", "quality_score": 0}

    original_text = p.read_text(encoding="utf-8", errors="ignore")
    _, initial_issues = validate_and_fix_markdown_text(
        original_text,
        auto_fix=False,
        max_cols=max_cols,
        max_token_len=max_token_len,
        max_line_len=max_line_len,
    )

    if auto_fix:
        fixed_text, remaining_issues = validate_and_fix_markdown_text(
            original_text,
            auto_fix=True,
            max_cols=max_cols,
            max_token_len=max_token_len,
            max_line_len=max_line_len,
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
    max_line_len: int = 120,
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
            str(md_file),
            auto_fix=auto_fix,
            max_cols=max_cols,
            max_token_len=max_token_len,
            max_line_len=max_line_len,
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
        "max_line_len": max_line_len,
        "total_files": len(markdown_files),
        "files_with_issues": len(results),
        "total_violations": total_violations,
        "total_fixes_applied": total_fixes,
        "average_score": round(avg_score, 1),
        "problem_files": sorted(results, key=lambda x: x["violations"], reverse=True)[:15],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single Source of Truth Markdown Quality Validator, Line Wrapper & Zero-Scroll Table Fixer (v3.1)"
    )
    parser.add_argument("path", nargs="?", default=".", help="File or directory to check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix compact tables, line wrapping (<=120), list indent/blanks, wide columns, and long tokens")
    parser.add_argument("--score", action="store_true", help="Show quality score only")
    parser.add_argument("--max-cols", type=int, default=5, help="Maximum allowed columns per table (default: 5; use 3 for portrait PDF mode)")
    parser.add_argument("--strict-3col", action="store_true", help="Shortcut for --max-cols 3 (portrait PDF Rule D5)")
    parser.add_argument("--max-token-len", type=int, default=40, help="Max unbroken token length in table cells (default: 40)")
    parser.add_argument("--max-line-len", type=int, default=120, help="Maximum line length for prose, list items, and blockquotes (default: 120; 0 to disable)")

    args = parser.parse_args()
    max_cols = 3 if args.strict_3col else args.max_cols

    if os.path.isfile(args.path):
        result = check_markdown_quality(
            args.path,
            auto_fix=args.fix,
            max_cols=max_cols,
            max_token_len=args.max_token_len,
            max_line_len=args.max_line_len,
        )
        if args.score:
            print(f"Quality Score: {result['quality_score']}/100")
        else:
            print(json.dumps(result, indent=2))
    else:
        result = validate_all_documentation(
            args.path,
            auto_fix=args.fix,
            max_cols=max_cols,
            max_token_len=args.max_token_len,
            max_line_len=args.max_line_len,
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
# Search Keywords: markdown_validator, D5-SEP, D5-PAD, D5-COLS, D5-TOKEN, D5-WRAP, D5-PIPE, MD013, MD007, MD032, compact tables
# Drivers & Subsystems: documentation, markdownlint, netperf_copilot
# Related Units / Patches: DOC-RULE-D5, DOC-RULE-D5, Rule D1-D10 v3.1
# Created / Last-Updated: 2026-02-02 / 2026-11-09
# === METADATA_FOOTER_END ===
