# Documentation Standards

This document defines the quality standards for all markdown documentation in the netperf project.

## Quality Tool

We use `markdown_validator.py` to enforce consistent documentation standards across the project.

**Location**: `dev/tools/markdown_validator.py`

## Usage

### Validate All Documentation

```bash
# Check all markdown files
./dev/tools/markdown_validator.py

# Get quality score
./dev/tools/markdown_validator.py . --score

# Auto-fix issues
./dev/tools/markdown_validator.py . --fix
```

### Validate Single File

```bash
# Check specific file
./dev/tools/markdown_validator.py README.md

# Auto-fix specific file
./dev/tools/markdown_validator.py README.md --fix
```

## Quality Standards

The validator enforces markdownlint rules including:

### Heading Standards
- **MD022**: Headings must be surrounded by blank lines
- **MD025**: Only one H1 heading per document
- **MD041**: First line must be a top-level heading

### List Standards
- **MD032**: Lists must be surrounded by blank lines
- **MD030**: Consistent spacing after list markers

### Code Block Standards
- **MD031**: Fenced code blocks must be surrounded by blank lines
- **MD040**: Fenced code blocks should have a language specified

### Link Standards
- **MD034**: No bare URLs (use proper markdown links)

### Formatting Standards
- **MD009**: No trailing spaces
- **MD012**: No multiple consecutive blank lines

## Pre-Commit Integration

To automatically validate documentation before commits:

```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
./dev/tools/markdown_validator.py
if [ $? -ne 0 ]; then
    echo "❌ Documentation quality check failed"
    echo "Run: ./dev/tools/markdown_validator.py . --fix"
    exit 1
fi
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
# Example GitHub Actions
- name: Validate Documentation
  run: |
    python3 dev/tools/markdown_validator.py
```

## Current Status

As of January 31, 2026:
- ✅ All 33 markdown files pass quality checks
- ✅ Average quality score: 100/100
- ✅ Zero violations detected

## Quality Score

The validator calculates a quality score (0-100):
- **100**: Perfect - no violations
- **90-99**: Excellent - minor issues
- **70-89**: Good - some improvements needed
- **50-69**: Fair - significant issues
- **<50**: Poor - major quality problems

**Formula**: `score = max(0, 100 - (violations × 2))`

## Common Fixes

### Missing Blank Lines Around Headings

```markdown
<!-- Wrong -->
Some text
### Heading
More text

<!-- Right -->
Some text

### Heading

More text
```

### Missing Blank Lines Around Lists

```markdown
<!-- Wrong -->
Some text
- Item 1
- Item 2
More text

<!-- Right -->
Some text

- Item 1
- Item 2

More text
```

### Code Blocks Without Language

```markdown
<!-- Wrong -->
```
code here
```

<!-- Right -->
```bash
code here
```
```

### Bare URLs

```markdown
<!-- Wrong -->
Visit http://example.com

<!-- Right -->
Visit [example website](http://example.com)
```

## Excluding Files

The validator automatically excludes:
- `.git` directory
- `node_modules`
- `venv` and `.venv`
- `dist` and `build` directories
- Any directory starting with `.`

## Dependencies

Requires `markdownlint-cli`:

```bash
# Install globally
npm install -g markdownlint-cli

# Or use npx (no install needed)
npx markdownlint file.md
```

## See Also

- [Markdown Guide](https://www.markdownguide.org/)
- [markdownlint Rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md)
- [Project README](../../README.md)

---

**Maintained By**: Documentation Enforcer Agent  
**Last Updated**: January 31, 2026
