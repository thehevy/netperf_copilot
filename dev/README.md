# Development Directory

<!-- METADATA_HEADER_START -->
- **Document ID**: `DOC-NETPERF-DEV-README` | **Version**: `v3.2` | **Status**: `Active`
- **Created Date**: `2026-11-05` | **Last Updated Date**: `2026-11-09`
- **Target Scope**: `netperf_copilot` High-Speed 100GbE–800GbE Qualification & Automation Suite
- **Summary**: Technical documentation for Development Directory under Rules `D1`–`D10` `v3.2`.
<!-- METADATA_HEADER_END -->


This directory contains development work, documentation, and tooling that is separate from the core netperf project
structure.

## Structure

- **docs/** - Development documentation, design notes, and technical specifications
- **plans/** - Project plans, roadmaps, and feature proposals
- **scripts/** - Development and testing scripts (build automation, test runners, etc.)
- **reports/** - Test reports, benchmark results, and analysis documents

## Build Process

All compilation should be done in the `build/` directory (at project root level):

```bash
# Create and use build directory
mkdir -p build
cd build

# Configure from build directory
../configure [options]

# Build
make

# Test
./src/netserver -D &
./src/netperf -H localhost

# Clean up when done
cd ..
rm -rf build
```

This keeps compiled binaries, object files, and build artifacts separate from the source tree.

## Workflow

1. Document plans and designs in `dev/docs/` or `dev/plans/`
2. Create development scripts in `dev/scripts/`
3. Build and test in `build/` directory
4. Document results in `dev/reports/`
5. Once validated, integrate changes into main source tree
6. Clean up or archive build directory

## Notes

- The `build/` directory is git-ignored and can be safely deleted
- All work in `dev/` is tracked but isolated from the core project
- Original netperf structure remains clean and unchanged

---

<!-- METADATA_FOOTER_START -->
### Document Search & Discovery Metadata

| Field | Value |
| --- | --- |
| **File Path** | `dev/README.md` |
| **Created / Last Updated** | `2026-11-05` / `2026-11-09` |
| **Keywords / Search Tags** | `netperf_copilot`, `OMNI`, `100GbE-800GbE`, `Intel Ethernet 200GbE`, `Intel® Xeon® 6`, `Rules D1-D10 v3.2` |
| **Drivers & Subsystems** | `ice`, `netperf`, `netserver`, `netperf-multi`, `netperf-preflight` |
| **Validation / Patch IDs** | `DOC-NETPERF-DEV-README`, `D1-D10 v3.2`, `MD013`, `D7-ID-MATCH` |
<!-- METADATA_FOOTER_END -->
