# Phase 1: Core Defaults & Build Optimization - Implementation Plan

## Overview

This phase focuses on changing netperf defaults to be more useful out-of-the-box while maintaining backward compatibility.

**Duration:** 2 weeks  
**Risk:** Low  
**Dependencies:** None  

---

## Task Breakdown

### Task 1.1: Change Default Test to OMNI (2 days)

#### Files to Modify

1. **src/netsh.c** (line ~129)

   ```c
   // OLD:
   test_name[BUFSIZ] = "TCP_STREAM",
   
   // NEW:
   test_name[BUFSIZ] = "OMNI",
   ```

2. **src/netsh.h** (if constant exists)

   ```c
   #define DEFAULT_TEST "OMNI"
   ```

#### Testing Checklist

- [ ] `./netperf -H localhost` runs OMNI
- [ ] `./netperf -H localhost -t TCP_STREAM` still works
- [ ] All existing test names work via `-t` option
- [ ] No performance regression

#### Validation Commands

```bash
# Build in test directory
./dev/scripts/build.sh

# Test default behavior
cd build
./src/netserver -D &
SERVER_PID=$!

# Should run OMNI by default
./src/netperf -H localhost

# Test backward compatibility
./src/netperf -H localhost -t TCP_STREAM
./src/netperf -H localhost -t TCP_RR
./src/netperf -H localhost -t UDP_STREAM

kill $SERVER_PID
```

---

### Task 1.2: Define Default OMNI Output Selectors (3 days)

#### Research Phase

Review `doc/omni_output_list.txt` and determine optimal defaults based on:

- Most commonly needed metrics
- Balance of information vs. readability
- Industry standard benchmarking practices

#### Recommended Default Selectors

```
THROUGHPUT,THROUGHPUT_UNITS,ELAPSED_TIME,PROTOCOL,DIRECTION,
LOCAL_CPU_UTIL,REMOTE_CPU_UTIL,LOCAL_SEND_SIZE,LOCAL_RECV_SIZE,
REMOTE_SEND_SIZE,REMOTE_RECV_SIZE,LOCAL_SEND_CALLS,LOCAL_RECV_CALLS,
REMOTE_SEND_CALLS,REMOTE_RECV_CALLS
```

#### Optional Extended Defaults (with -v verbose flag)

```
Add: MEAN_LATENCY,P50_LATENCY,P90_LATENCY,P99_LATENCY,MAX_LATENCY,
     LOCAL_BYTES_SENT,LOCAL_BYTES_RECVD,REMOTE_BYTES_SENT,REMOTE_BYTES_RECVD,
     TRANSPORT_MSS,LOCAL_SOCKET_TOS,REMOTE_SOCKET_TOS
```

#### Implementation

**Option A: Hardcode defaults in nettest_omni.c**

```c
// In nettest_omni.c, add after includes
#define DEFAULT_OUTPUT_SELECTORS \
  "THROUGHPUT,THROUGHPUT_UNITS,ELAPSED_TIME,PROTOCOL,DIRECTION," \
  "LOCAL_CPU_UTIL,REMOTE_CPU_UTIL,LOCAL_SEND_SIZE,LOCAL_RECV_SIZE"

// In print_omni_output() or equivalent
if (output_selectors == NULL || strlen(output_selectors) == 0) {
  output_selectors = DEFAULT_OUTPUT_SELECTORS;
}
```

**Option B: Add preset modes**

```c
// Add new command-line option: -k <preset>
// Presets: default, verbose, minimal, all

switch(output_preset) {
  case OUTPUT_MINIMAL:
    selectors = "THROUGHPUT,THROUGHPUT_UNITS,ELAPSED_TIME";
    break;
  case OUTPUT_DEFAULT:
    selectors = DEFAULT_OUTPUT_SELECTORS;
    break;
  case OUTPUT_VERBOSE:
    selectors = VERBOSE_OUTPUT_SELECTORS;
    break;
  case OUTPUT_ALL:
    selectors = "all";
    break;
}
```

#### Files to Modify

1. **src/nettest_omni.c**
   - Add default selector constants
   - Modify output selector initialization
   - Add preset mode handling

2. **src/netsh.c** (if adding preset option)
   - Add command-line parsing for `-k <preset>`
   - Document in help text

3. **doc/netperf.man** and other docs
   - Document new defaults
   - Explain preset modes

#### Testing Checklist

- [ ] Default output includes essential metrics
- [ ] `-k` option still allows custom selectors
- [ ] Preset modes work correctly
- [ ] Output is readable and well-formatted
- [ ] CSV output still works with new defaults

---

### Task 1.3: Enable Interval Reporting by Default (1 day)

#### Files to Modify

1. **configure.ac** (around line 200)

   ```bash
   # OLD:
   '')
       # whatever
       use_demo=false
       ;;
   
   # NEW:
   '')
       use_demo=true
       ;;
   ```

2. Document the change in configure help text

#### Performance Impact Assessment

Before enabling by default, test:

```bash
# Test with demo disabled
./configure --disable-demo
make clean && make
./dev/scripts/test-basic.sh > results-no-demo.txt

# Test with demo enabled
./configure --enable-demo
make clean && make
./dev/scripts/test-basic.sh > results-with-demo.txt

# Compare performance
diff results-no-demo.txt results-with-demo.txt
```

**Expected:** Minimal impact (<1% overhead)  
**If overhead >2%:** Consider leaving as opt-in

#### Testing Checklist

- [ ] Interval reporting works by default
- [ ] Can be disabled with `--disable-demo`
- [ ] Performance impact <1%
- [ ] Documentation updated

---

### Task 1.4: Review Build Configuration (3 days)

#### Analysis Spreadsheet

Create: `dev/docs/analysis/configure-options-analysis.md`

| Option | Current Default | Recommended | Reason | Performance Impact |
|--------|----------------|-------------|--------|-------------------|
| --enable-demo | no | **yes** | Useful by default | <1% |
| --enable-omni | yes | yes | Core feature | N/A |
| --enable-histogram | no | no | 5-10% overhead | High |
| --enable-intervals | no | **yes** | Modern feature | <2% |
| --enable-burst | no | **yes** | Useful for RR tests | None |
| --enable-sctp | no | **yes** | If available | None |
| --enable-unixdomain | no | **yes** | Common use case | None |
| --enable-dlpi | no | no | Specialized | None |
| --enable-xti | no | no | Legacy | None |
| --enable-dirty | no | no | Testing only | None |

#### Recommended Default Configure

```bash
#!/bin/bash
# dev/scripts/configure-optimized.sh

../configure \
  --enable-demo \
  --enable-omni \
  --enable-intervals \
  --enable-burst \
  --enable-sctp \
  --enable-unixdomain \
  --disable-histogram \
  --disable-dirty \
  "$@"
```

#### Testing Matrix

Test each configuration combination on:

- Linux (Ubuntu, RHEL)
- FreeBSD
- MacOS (if available)

#### Deliverables

- [ ] Analysis document
- [ ] Optimized configure script
- [ ] Performance comparison report
- [ ] Recommendation document

---

### Task 1.5: Update Build Scripts (1 day)

#### Update dev/scripts/build.sh

```bash
#!/bin/bash
# Enhanced build script with optimized defaults

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"

# Parse options
CONFIGURE_OPTS=""
USE_OPTIMIZED=1

while [[ $# -gt 0 ]]; do
  case $1 in
    --no-optimize)
      USE_OPTIMIZED=0
      shift
      ;;
    *)
      CONFIGURE_OPTS="$CONFIGURE_OPTS $1"
      shift
      ;;
  esac
done

echo "=== Netperf Development Build ==="

# Create build directory
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# Run configure
echo "=== Running configure ==="
if [ $USE_OPTIMIZED -eq 1 ]; then
  echo "Using optimized defaults"
  "${PROJECT_ROOT}/dev/scripts/configure-optimized.sh" $CONFIGURE_OPTS
else
  echo "Using standard configure"
  "${PROJECT_ROOT}/configure" $CONFIGURE_OPTS
fi

# Build
echo "=== Building ==="
make -j$(nproc)

echo "=== Build complete ==="
echo "Binaries: ${BUILD_DIR}/src/"
```

#### Create Makefile Wrapper

```makefile
# dev/Makefile
# Convenience wrapper for out-of-source builds

.PHONY: all build clean test configure

all: build

configure:
 @./scripts/configure-optimized.sh

build:
 @./scripts/build.sh

clean:
 @./scripts/clean.sh

test:
 @./scripts/test-basic.sh

help:
 @echo "Development Makefile"
 @echo ""
 @echo "Targets:"
 @echo "  configure - Run optimized configure"
 @echo "  build     - Build with optimized settings"
 @echo "  clean     - Remove build directory"
 @echo "  test      - Run basic test suite"
 @echo ""
 @echo "Usage:"
 @echo "  make build"
 @echo "  make test"
```

---

### Task 1.6: Documentation (2 days)

#### Create Documentation Files

**1. dev/docs/build-configuration.md**

```markdown
# Netperf Build Configuration Guide

## Quick Start
```bash
# Optimized build (recommended)
./dev/scripts/build.sh

# Standard build
mkdir build && cd build
../configure
make
```

## Configuration Options

### Recommended Defaults

- `--enable-demo`: Interval reporting
- `--enable-intervals`: Paced operations
- `--enable-burst`: RR burst support
...

### Performance Impact

| Option | Overhead | Use Case |
|--------|----------|----------|
| demo | <1% | Always |
| histogram | 5-10% | Debugging only |
...

```

**2. Update main README.md**
Add section about new defaults:
```markdown
## What's New in 3.0

### Better Defaults
- OMNI test runs by default (more flexible than TCP_STREAM)
- Sensible output metrics selected automatically
- Interval reporting enabled for progress monitoring

### Backward Compatibility
All existing test names and options still work:
`netperf -H host -t TCP_STREAM` works exactly as before
```

**3. UPGRADING.md**

```markdown
# Upgrading from Netperf 2.x to 3.0

## Breaking Changes
None - 3.0 is fully backward compatible

## Behavior Changes
1. Default test changed from TCP_STREAM to OMNI
   - To use old behavior: `netperf -H host -t TCP_STREAM`
2. Interval reporting enabled by default
   - To disable: configure with `--disable-demo`
...
```

---

## Testing Strategy

### Unit Tests

Create: `dev/tests/test-phase1.sh`

```bash
#!/bin/bash
set -e

echo "=== Phase 1 Unit Tests ==="

# Test 1: Default test is OMNI
./src/netperf -H localhost | grep -q "OMNI" || exit 1

# Test 2: Backward compatibility
./src/netperf -H localhost -t TCP_STREAM >/dev/null || exit 1

# Test 3: Default output includes key metrics
OUTPUT=$(./src/netperf -H localhost)
echo "$OUTPUT" | grep -q "THROUGHPUT" || exit 1
echo "$OUTPUT" | grep -q "CPU" || exit 1

# Test 4: All tests still work
for test in TCP_STREAM TCP_RR UDP_STREAM UDP_RR; do
  ./src/netperf -H localhost -t $test >/dev/null || exit 1
done

echo "All tests passed!"
```

### Integration Tests

```bash
# Test across all supported platforms
for platform in ubuntu-20.04 ubuntu-22.04 rhel8 rhel9 freebsd13; do
  docker run -v $(pwd):/netperf $platform /netperf/dev/tests/test-phase1.sh
done
```

### Performance Regression Tests

```bash
# Compare 2.7.1 vs 3.0.0
./dev/scripts/performance-comparison.sh \
  --baseline 2.7.1 \
  --current 3.0.0 \
  --iterations 10 \
  --output dev/reports/phase1-performance.html
```

---

## Acceptance Criteria

### Must Have

- [ ] Default test is OMNI
- [ ] Default OMNI output includes 10-15 useful metrics
- [ ] Backward compatibility: all existing tests work
- [ ] Performance regression <1%
- [ ] Builds on Linux, FreeBSD, MacOS
- [ ] Documentation complete and accurate

### Nice to Have

- [ ] Preset output modes (minimal, default, verbose)
- [ ] HTML performance report
- [ ] CI/CD pipeline running tests

### Success Metrics

- OMNI default reduces need for `-t` flag by 80%
- Default output eliminates need for `-k` flag for 90% of users
- Zero user complaints about backward compatibility

---

## Rollout Plan

### Week 1

- Days 1-2: Implement Task 1.1 (OMNI default)
- Days 3-5: Implement Task 1.2 (default output selectors)

### Week 2

- Day 1: Implement Task 1.3 (interval reporting)
- Days 2-4: Complete Task 1.4 (config review)
- Day 5: Task 1.5 (build scripts) and start Task 1.6 (docs)

### Week 3 (buffer)

- Complete documentation
- Run full test matrix
- Performance validation
- Prepare for Phase 2

---

## Git Branch Strategy

```bash
# Create phase 1 branch
git checkout -b dev/phase-1-defaults

# Sub-branches for major features
git checkout -b feature/omni-default
git checkout -b feature/default-output-selectors
git checkout -b feature/optimized-build

# Merge to dev/phase-1-defaults
# Then merge to master when complete
```

---

## Next Steps

1. Review and approve this implementation plan
2. Create GitHub issues for each task
3. Set up project board for tracking
4. Begin Task 1.1: Change default test to OMNI

---

**Document Version:** 1.0  
**Status:** Ready for Implementation  
**Last Updated:** 2026-01-30
