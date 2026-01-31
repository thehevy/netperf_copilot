#!/usr/bin/env python3
"""
Standalone Markdown Quality Validator
Portable across any project with markdown documentation.
"""

import subprocess
import json
import sys
import os
from pathlib import Path
from typing import Dict, List

def check_markdown_quality(file_path: str, auto_fix: bool = False) -> Dict:
    """Analyzes markdown file for style violations."""
    import re
    
    violations = []
    
    # Run markdownlint
    try:
        result = subprocess.run(
            ["markdownlint", "--json", file_path],
            capture_output=True,
            text=True
        )
        if result.stdout:
            violations = json.loads(result.stdout)
    except FileNotFoundError:
        return {"error": "markdownlint-cli not installed. Run: npm install -g markdownlint-cli"}
    except Exception as e:
        return {"error": str(e)}
    
    if auto_fix and violations:
        # Auto-fix using markdownlint --fix
        subprocess.run(["markdownlint", "--fix", file_path], check=False)
        
        # Re-check
        result = subprocess.run(
            ["markdownlint", "--json", file_path],
            capture_output=True,
            text=True
        )
        new_violations = json.loads(result.stdout) if result.stdout else []
        fixed_count = len(violations) - len(new_violations)
        
        return {
            "file": file_path,
            "original_violations": len(violations),
            "remaining_violations": len(new_violations),
            "fixes_applied": fixed_count,
            "quality_score": calculate_quality_score(new_violations)
        }
    
    return {
        "file": file_path,
        "violations": len(violations),
        "details": violations[:10],
        "quality_score": calculate_quality_score(violations)
    }

def calculate_quality_score(violations: List) -> int:
    """Returns 0-100 quality score."""
    if not violations:
        return 100
    score = 100 - (len(violations) * 2)
    return max(0, score)

def validate_all_documentation(root_dir: str = ".") -> Dict:
    """Scans directory tree for markdown quality issues."""
    markdown_files = list(Path(root_dir).rglob("*.md"))
    
    # Exclude common ignored directories
    excluded = {'.git', 'node_modules', 'venv', '.venv', 'dist', 'build'}
    markdown_files = [
        f for f in markdown_files 
        if not any(part.startswith('.') or part in excluded for part in f.parts)
    ]
    
    results = []
    total_violations = 0
    
    for md_file in markdown_files:
        result = check_markdown_quality(str(md_file), auto_fix=False)
        if 'violations' in result and result['violations'] > 0:
            total_violations += result['violations']
            results.append({
                "file": str(md_file),
                "violations": result['violations'],
                "score": result['quality_score']
            })
    
    avg_score = sum(r['score'] for r in results) / len(results) if results else 100
    
    return {
        "total_files": len(markdown_files),
        "files_with_issues": len(results),
        "total_violations": total_violations,
        "average_score": round(avg_score, 1),
        "problem_files": sorted(results, key=lambda x: x['violations'], reverse=True)[:10]
    }

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Markdown Quality Validator")
    parser.add_argument("path", nargs="?", default=".", help="File or directory to check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--score", action="store_true", help="Show quality score only")
    
    args = parser.parse_args()
    
    if os.path.isfile(args.path):
        # Single file
        result = check_markdown_quality(args.path, auto_fix=args.fix)
        if args.score:
            print(f"Quality Score: {result['quality_score']}/100")
        else:
            print(json.dumps(result, indent=2))
    else:
        # Directory scan
        result = validate_all_documentation(args.path)
        print(json.dumps(result, indent=2))
        
        if result['files_with_issues'] > 0:
            print(f"\n⚠️  Found issues in {result['files_with_issues']} files")
            if args.fix:
                print("\n🔧 Run with --fix to auto-correct")
            sys.exit(1)
        else:
            print("\n✅ All documentation meets quality standards!")
            sys.exit(0)

if __name__ == "__main__":
    main()
