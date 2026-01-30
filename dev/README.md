# Development Directory

This directory contains development work, documentation, and tooling that is separate from the core netperf project structure.

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
