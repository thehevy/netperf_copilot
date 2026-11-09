#!/usr/bin/env python3
# === METADATA_HEADER_START ===
# File: scripts/doc_template_scaffolder.py
# Created Date: 2026-11-09
# Last Updated Date: 2026-11-09
# Version: v3.2
# Status: Active
# Target Scope: Intel(R) Technical Document Template Scaffolder (Rules D1-D10 v3.2)
# Summary: Lists and scaffolds canonical Intel(R) technical documents from templates/TEMPLATE_01..06_*.md with synchronized Header/Footer Document IDs (D7-ID-MATCH).
# === METADATA_HEADER_END ===

import argparse
from datetime import date
from pathlib import Path
import re
import sys
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

TEMPLATE_MAP: Dict[str, Tuple[str, str]] = {
    "report": (
        "TEMPLATE_01_Engineering_Validation_and_Executive_Report.md",
        "Executive Engineering, Patch & A/B Hardware Validation Report (TEMPLATE-01)",
    ),
    "config-guide": (
        "TEMPLATE_02_Configuration_Guide_and_BKM_Runbook.md",
        "Configuration Guide & Best Known Method (BKM) Runbook (TEMPLATE-02)",
    ),
    "white-paper": (
        "TEMPLATE_03_Architecture_White_Paper_and_Benchmark_Study.md",
        "Architecture White Paper & Empirical Benchmark Study (TEMPLATE-03)",
    ),
    "playbook": (
        "TEMPLATE_04_Troubleshooting_and_Root_Cause_Playbook.md",
        "Troubleshooting & Root-Cause Diagnostic Playbook (TEMPLATE-04)",
    ),
    "dossier": (
        "TEMPLATE_05_Repository_Dossier_and_README.md",
        "Repository Executive Dossier & Project README.md (TEMPLATE-05)",
    ),
    "wiki-page": (
        "TEMPLATE_06_GitHub_Wiki_5_Page_Pack.md",
        "GitHub Wiki Page & 5-Page Repository Wiki Pack (TEMPLATE-06)",
    ),
}


def list_templates() -> int:
    print("Available Canonical Intel(R) Technical Document Templates (Rules D1-D10 v3.2):")
    for key, (filename, desc) in TEMPLATE_MAP.items():
        exists = (TEMPLATES_DIR / filename).exists()
        status = "OK" if exists else "MISSING"
        print(f"  {key:14s} -> templates/{filename} [{status}] ({desc})")
    return 0


def create_from_template(
    doc_type: str,
    doc_id: str,
    output_path: Path,
    title: str = "",
    scope: str = "",
) -> int:
    if doc_type not in TEMPLATE_MAP:
        print(f"Error: Unknown template type '{doc_type}'. Valid types: {list(TEMPLATE_MAP)}", file=sys.stderr)
        return 1
    template_file = TEMPLATES_DIR / TEMPLATE_MAP[doc_type][0]
    if not template_file.exists():
        print(f"Error: Template file not found: {template_file}", file=sys.stderr)
        return 1

    text = template_file.read_text(encoding="utf-8")
    today = date.today().isoformat()

    if title:
        text = re.sub(r"^#\s+.*$", f"# {title}", text, count=1, flags=re.MULTILINE)

    # Replace Document ID in header and footer (D7-ID-MATCH)
    old_id_match = re.search(r"\*\*Document ID\*\*:\s*`([^`]+)`", text)
    old_id = old_id_match.group(1) if old_id_match else ""
    if old_id:
        text = text.replace(f"`{old_id}`", f"`{doc_id}`")
    else:
        text = re.sub(r"(\*\*Document ID\*\*:\s*)`[^`]*`", rf"\g<1>`{doc_id}`", text)

    text = re.sub(r"(\*\*Created Date\*\*:\s*)`[^`]+`", rf"\g<1>`{today}`", text)
    text = re.sub(r"(\*\*Last Updated Date\*\*:\s*)`[^`]+`", rf"\g<1>`{today}`", text)
    if scope:
        text = re.sub(r"(\*\*Target Scope\*\*:\s*).*$", rf"\g<1>{scope}", text, count=1, flags=re.MULTILINE)

    rel_out = str(output_path).replace("\\", "/")
    try:
        rel_out = str(output_path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        pass
    text = re.sub(
        r"(\|\s*\*\*File Path\*\*\s*\|\s*)[^|]+(\|)",
        rf"\g<1>`{rel_out}` \2",
        text,
    )
    text = re.sub(
        r"(\|\s*\*\*Created / Last Updated\*\*\s*\|\s*)[^|]+(\|)",
        rf"\g<1>`{today}` / `{today}` \2",
        text,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Scaffolded {doc_type} document '{doc_id}' -> {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold Intel(R) Technical Documents from Canonical Templates (Rules D1-D10 v3.2)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List all 6 canonical Intel(R) document templates")

    p_create = sub.add_parser("create", help="Create a new document from a canonical template")
    p_create.add_argument("--type", required=True, choices=list(TEMPLATE_MAP), help="Canonical template type")
    p_create.add_argument("--doc-id", required=True, help="Document ID (synchronized across Header and Footer)")
    p_create.add_argument("--title", default="", help="Optional H1 title override")
    p_create.add_argument("--scope", default="", help="Optional Target Scope override")
    p_create.add_argument("--output", required=True, help="Output Markdown file path")

    args = parser.parse_args()
    if args.cmd == "list":
        return list_templates()
    return create_from_template(
        doc_type=args.type,
        doc_id=args.doc_id,
        output_path=Path(args.output),
        title=args.title,
        scope=args.scope,
    )


if __name__ == "__main__":
    sys.exit(main())

# === METADATA_FOOTER_START ===
# Search Keywords: doc_template_scaffolder.py, canonical templates, TEMPLATE-01..06, Rules D1-D10 v3.2, D7-ID-MATCH
# Drivers & Subsystems: Linux networking, netperf_copilot documentation
# Related Units / Patches: DOC-TEMPLATE-SUITE-INDEX-000, D1-D10 v3.2
# Created / Last-Updated: 2026-11-09 / 2026-11-09
# === METADATA_FOOTER_END ===
