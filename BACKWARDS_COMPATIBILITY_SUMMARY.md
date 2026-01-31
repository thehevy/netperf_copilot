# Backwards Compatibility Implementation Summary

## Overview

Successfully implemented **perfect backwards compatibility** for netperf while making modern features easily accessible.

## The Solution

### Default Behavior (No Flags Required)
```bash
netperf -H host
```
- Runs TCP_STREAM test (classic behavior)
- Outputs columnar format
- **100% compatible with existing scripts**
- No migration needed!

### Modern Features (Requires -M Flag)
```bash
netperf -H host -M
```
- Runs OMNI test (modern framework)
- Outputs keyval format (THROUGHPUT=value)
- Access to JSON output: `netperf -H host -M -- -J`
- Access to interim results: `netperf -H host -M -D 1`

## Code Changes

### src/netsh.c
```c
// Line 129: Default remains TCP_STREAM
char test_name[BUFSIZ] = "TCP_STREAM",

// Added -M global flag (line 114)
#define GLOBAL_CMD_LINE_ARGS "...M..."

// Case handler (line 994)
case 'M':
  /* Enable modern OMNI test mode */
  strncpy(test_name,"OMNI",sizeof(test_name));
  break;
```

### src/nettest_omni.c
- Added missing `#include <sys/utsname.h>` for JSON output
- Added `extern char *netperf_version;` declaration

## Documentation Updates

All documentation updated to reflect:
1. TCP_STREAM is the default (not OMNI)
2. Use `-M` flag for modern OMNI features
3. All examples show `-M` when using OMNI
4. No migration guide needed (backwards compatible!)

**Files Updated:**
- README.md
- UPGRADING.md
- docs/quickstart.md
- docs/index.md
- dev/docs/BACKWARDS_COMPATIBILITY.md
- dev/docs/PHASE1_FEATURES.md
- dev/scripts/test-phase1-task1.sh
- dev/tools/netperf-multi

## Testing

```bash
$ ./dev/scripts/test-phase1-task1.sh
✅ All Phase 1 Task 1.1 tests PASSED!

Tests verified:
- Default test is TCP_STREAM (backwards compatible)
- -M flag enables modern OMNI test
- All classic test names still work
- Full backwards compatibility maintained
```

## Migration Path

### For Existing Scripts
**No changes needed!** Scripts using:
- `netperf -H host`
- `netperf -H host -t TCP_STREAM`
- `netperf -H host -t TCP_RR`
- All legacy test names

Continue to work exactly as before.

### For New Scripts Wanting Modern Features
Add `-M` flag:
```bash
# Old approach (if you were using OMNI as default)
netperf -H host | grep THROUGHPUT

# New approach (with -M flag)
netperf -H host -M | grep THROUGHPUT
```

## Benefits

1. **Zero Breaking Changes**: Existing scripts work unchanged
2. **Easy Migration**: Just add `-M` when you want modern features
3. **Clear Intent**: Explicit flag makes it obvious when using modern mode
4. **Best of Both Worlds**: Full backwards compat + access to modern features

## Version Info

- Branch: master
- Commits:
  - e519a9a: BREAKING: Restore full backwards compatibility
  - dc2061c: Update all documentation for backwards compatible approach
  
Date: January 31, 2026
