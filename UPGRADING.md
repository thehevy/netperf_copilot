# Upgrading to the Modernized Netperf Fork

This guide helps users migrate from upstream netperf to this modernized fork, covering what's changed, what stays the same, and how to adapt your workflows.

## TL;DR - Quick Migration

**Good news**: This fork is **100% backward compatible**. Your existing scripts and workflows will continue to work unchanged.

**Optional improvements**: You can opt into new features (JSON output, better defaults) when ready.

### Command Path Conventions

This guide uses two command formats:
- **Build directory**: `./build/src/netperf` - Run from build directory without installation
- **Installed**: `netperf` - Run after `make install` (typically in `/usr/local/bin`)

All examples show complete commands with full paths when applicable.

## What's Changed

### Default Test Type

**Upstream**: TCP_STREAM (classic BSD sockets test)
```bash
# Using installed version
netperf -H host

# Using build directory
./build/src/netperf -H host

# Output (columnar format)
# MIGRATED TCP STREAM TEST from...
# Recv   Send    Send                          
# Socket Socket  Message  Elapsed              
# Size   Size    Size     Time     Throughput  
# bytes  bytes   bytes    secs.    10^6bits/sec
```

**This Fork**: TCP_STREAM (same as upstream - full backwards compatibility)
```bash
# Using installed version
netperf -H host

# Using build directory
./build/src/netperf -H host

# Output (columnar format - same as upstream)
# MIGRATED TCP STREAM TEST from...
# Recv   Send    Send                          
# Socket Socket  Message  Elapsed              
# Size   Size    Size     Time     Throughput  
# bytes  bytes   bytes    secs.    10^6bits/sec
```

**Modern OMNI Test**: Use the `-M` flag
```bash
# Using installed version
netperf -H host -M

# Using build directory
./build/src/netperf -H host -M

# Output (keyval format)
# OMNI Send TEST from...
# THROUGHPUT=54623.45
# THROUGHPUT_UNITS=10^6bits/s
# ELAPSED_TIME=1.00
```

### Default Output Format

**Upstream**: Columnar/tabular format (HUMAN mode)
```bash
# Command
netperf -H host -l 10

# Output
# Local   Remote  Local   Elapsed Throughput
# Send    Recv    Send    Time    
# Socket  Socket  Size    (sec)   
# Size    Size    (bytes)         
# bytes   bytes                   10^6bits/s
# 87380   87380   16384   10.00   9387.23
```

**This Fork (Default)**: Same columnar format (backwards compatible)
```bash
# Using installed version
netperf -H host -l 10

# Using build directory
./build/src/netperf -H host -l 10

# Output (same as upstream)
# MIGRATED TCP STREAM TEST from...
# Recv   Send    Send                          
# Socket Socket  Message  Elapsed              
# Size   Size    Size     Time     Throughput  
# bytes  bytes   bytes    secs.    10^6bits/sec
```

**This Fork (OMNI with -M)**: Key-value format (easier to parse)
```bash
# Using installed version
netperf -H host -M -l 10

# Using build directory
./build/src/netperf -H host -M -l 10

# Output (keyval format)
# THROUGHPUT=9387.23
# THROUGHPUT_UNITS=10^6bits/s
# ELAPSED_TIME=10.00
# PROTOCOL=TCP
# DIRECTION=Send
```

### Interval/Demo Support

**Upstream**: Disabled by default (requires `--enable-demo` at configure time)

**This Fork**: Enabled by default (shows progress during long tests)
```bash
# Using installed version
netperf -H host -M -l 30

# Using build directory
./build/src/netperf -H host -M -l 30

# Output with interim results
# OMNI Send TEST... : demo
# [progress shown every second]
# THROUGHPUT=9234.56  # Final result
```

**Migration**: To disable interim results (for cleaner output in scripts):
```bash
# Using installed version
netperf -H host -M -l 30 -D -1

# Using build directory
./build/src/netperf -H host -M -l 30 -D -1
```

### MAXCPUS Limit

**Upstream**: 512 CPU cores maximum

**This Fork**: 2048 CPU cores maximum

**Migration**: No action needed. Systems with >512 cores will now work with `-c -C` options.

## What Hasn't Changed

### Command-Line Compatibility

All upstream command-line options work identically:
```bash
# These all work exactly as before (installed)
netperf -H host -l 10 -t TCP_RR
netperf -H host -l 10 -c -C
netperf -H host -P 1 -v 2
netperf -H host -f g

# Or from build directory
./build/src/netperf -H host -l 10 -t TCP_RR
./build/src/netperf -H host -l 10 -c -C
./build/src/netperf -H host -P 1 -v 2
./build/src/netperf -H host -f g
```

### Test Names

All classic test names still work:
- TCP_STREAM
- TCP_RR (request-response)
- TCP_CRR (connect-request-response)
- TCP_MAERTS (reverse direction)
- UDP_STREAM
- UDP_RR
- And all others

### Network Protocol

Client and server remain compatible:
- This fork's netperf can talk to upstream netserver
- Upstream netperf can talk to this fork's netserver
- No protocol changes

### Installation Paths

Default installation remains `/usr/local`:
```bash
make install          # Installs to /usr/local
make install PREFIX=/opt/netperf  # Custom location
```

## New Features (Opt-In)

### JSON Output

Perfect for modern tooling, APIs, and automation (requires `-M` flag):

```bash
# Using installed version
netperf -H host -M -- -J

# Using build directory
./build/src/netperf -H host -M -- -J
```

Output:
```json
{
  "THROUGHPUT": 54623.45,
  "THROUGHPUT_UNITS": "10^6bits/s",
  "ELAPSED_TIME": 1.00,
  "PROTOCOL": "TCP",
  "DIRECTION": "Send",
  "LOCAL_CPU_UTIL": 12.34,
  "REMOTE_CPU_UTIL": 23.45
}
```

**Use cases**:
- REST APIs
- Modern monitoring systems
- Data pipelines
- Configuration management tools

### CSV Output

Great for spreadsheet analysis (requires `-M` flag):

```bash
# Using installed version
netperf -H host -M -- -o

# Using build directory
./build/src/netperf -H host -M -- -o
```

Output:
```csv
Throughput,Throughput Units,Elapsed Time,Protocol,Direction
54623.45,10^6bits/s,1.00,TCP,Send
```

**Use cases**:
- Excel/LibreOffice analysis
- Data visualization
- Statistical analysis

### Output Presets

Pre-configured field selections for common use cases (requires `-M` flag):

```bash
# Minimal output (just throughput) - installed
netperf -H host -M -- -k dev/catalog/output-presets/minimal.out

# Minimal output - from build directory
./build/src/netperf -H host -M -- -k ../../dev/catalog/output-presets/minimal.out

# Verbose output (all available fields) - installed
netperf -H host -M -- -k dev/catalog/output-presets/verbose.out

# Latency-focused (for RR tests with OMNI) - installed
netperf -H host -M -- -P TCP_RR -k dev/catalog/output-presets/latency.out
```

Available presets:
- `minimal.out` - Throughput and time only
- `default.out` - Balanced set of common fields
- `verbose.out` - All available fields
- `latency.out` - Latency and transaction metrics
- `throughput.out` - Bandwidth-focused metrics
- `cpu.out` - CPU utilization focused

### Enhanced Build System

#### Build Types
```bash
# Release build (default, optimized)
./dev/scripts/build.sh

# Debug build (symbols, no optimization)
./dev/scripts/build.sh --type debug

# Optimized build (recommended configure options)
./dev/scripts/build.sh --type optimized
```

#### Convenience Makefile
```bash
cd dev

make build         # Standard build
make debug         # Debug build
make test          # Run tests
make test-formats  # Test all output formats
make clean         # Clean build
```

## Migration Scenarios

### Scenario 1: Existing Automation Scripts

**You have**: Scripts that parse netperf output

**Migration options**:

1. **No changes needed**: Default is TCP_STREAM columnar (backwards compatible)
```bash
# Using installed version
netperf -H host -t TCP_STREAM > results.txt

# Using build directory
./build/src/netperf -H host -t TCP_STREAM > results.txt

# Your existing parser works unchanged
```

2. **Modernize gradually**: Switch to JSON for new scripts (requires -M)
```bash
# Using installed version
netperf -H host -M -- -J > results.json

# Using build directory
./build/src/netperf -H host -M -- -J > results.json

# Parse JSON with jq, Python, etc.
jq .THROUGHPUT results.json
```

### Scenario 2: Continuous Integration

**You have**: CI/CD pipeline running netperf tests

**Migration**:

1. Update build in CI:
```bash
# Old
./configure && make

# New (optional)
./dev/scripts/build.sh --type optimized
```

2. Keep existing test commands (they work as-is):
```bash
# Using installed version
netperf -H $TARGET_HOST -l 10 -t TCP_STREAM

# Using build directory
./build/src/netperf -H $TARGET_HOST -l 10 -t TCP_STREAM
```

3. Or modernize output (requires -M for JSON):
```bash
# Using installed version
netperf -H $TARGET_HOST -M -l 10 -- -J | jq .THROUGHPUT

# Using build directory
./build/src/netperf -H $TARGET_HOST -M -l 10 -- -J | jq .THROUGHPUT
```

### Scenario 3: Performance Monitoring

**You have**: Cron job or monitoring agent running netperf

**Migration**:

Keep existing commands, optionally add JSON for easier parsing:

```bash
# Default columnar format (backwards compatible)
# Using installed version
netperf -H monitor-target | tail -1 | awk '{print $5}'

# Using build directory
./build/src/netperf -H monitor-target | tail -1 | awk '{print $5}'

# Modern OMNI with keyval (requires -M)
netperf -H monitor-target -M | grep -oP 'THROUGHPUT=\K[0-9.]+'

# Modern JSON (requires -M, easiest to parse)
# Using installed version
netperf -H monitor-target -M -- -J | jq -r .THROUGHPUT

# Using build directory
./build/src/netperf -H monitor-target -M -- -J | jq -r .THROUGHPUT
```

### Scenario 4: Manual Testing

**You have**: Interactive testing workflows

**Benefits**: Interim results provide better feedback (with -M flag)

```bash
# Long tests show progress with OMNI (requires -M)
# Using installed version
netperf -H host -M -l 300

# Using build directory
./build/src/netperf -H host -M -l 300

# Output
# OMNI Send TEST... : demo
# [See progress every second instead of waiting 5 minutes]
```

To disable for cleaner output:
```bash
# Using installed version
netperf -H host -M -l 300 -D -1

# Using build directory
./build/src/netperf -H host -M -l 300 -D -1
```

## Compatibility Matrix

| Feature | Upstream | This Fork | Compatible? |
|---------|----------|-----------|-------------|
| Command-line options | ✓ | ✓ | ✅ Yes |
| Test names | ✓ | ✓ | ✅ Yes |
| Network protocol | v2.7 | v2.7 | ✅ Yes |
| Columnar output | Default | `-- -O` | ✅ Yes |
| Key-value output | `-- -k` | Default | ✅ Yes |
| JSON output | ✗ | `-- -J` | ⚠️ New |
| CSV output | `-- -o` | `-- -o` | ✅ Yes |
| Interval reporting | Optional | Default | ⚠️ Changed |
| MAXCPUS | 512 | 2048 | ✅ Compatible |
| Build system | autoconf | autoconf+ | ✅ Compatible |

## Common Issues and Solutions

### Issue: Output looks different

**Note**: This shouldn't happen - default is TCP_STREAM columnar (same as upstream)

**Solution**: If you see keyval output, you may be using `-M` flag. Remove it for columnar:
```bash
# Default TCP_STREAM columnar (backwards compatible)
netperf -H host
./build/src/netperf -H host
```

### Issue: Getting interim results I don't want

**Cause**: Demo/interval support enabled with `-M` flag and long tests

**Solution**: Disable with `-D -1`
```bash
# Using installed version
netperf -H host -M -l 60 -D -1

# Using build directory
./build/src/netperf -H host -M -l 60 -D -1
```

### Issue: Scripts expecting TCP_STREAM behavior

**Note**: TCP_STREAM is the default - scripts should work unchanged

**Solution**: Ensure you're not using `-M` flag
```bash
# Default TCP_STREAM (backwards compatible)
netperf -H host
./build/src/netperf -H host

# Or specify explicitly
netperf -H host -t TCP_STREAM
./build/src/netperf -H host -t TCP_STREAM
```

### Issue: Need JSON/keyval output but getting columnar

**Cause**: Need to use `-M` flag for OMNI features

**Solution**: Add `-M` flag:
```bash
# For keyval output
netperf -H host -M
./build/src/netperf -H host -M

# For JSON output
netperf -H host -M -- -J
./build/src/netperf -H host -M -- -J
```

### Issue: CPU measurement not working

**Cause**: Incompatible netserver version (old vs new)

**Solution**: Update both netperf and netserver to same version
```bash
# On server (using installed version)
killall netserver
netserver -4

# On server (using build directory)
killall netserver
./build/src/netserver -4

# On client (using installed version)
netperf -H server -l 10 -c -C

# On client (using build directory)
./build/src/netperf -H server -l 10 -c -C
```

## Performance Considerations

### Build Configuration

This fork enables some features by default. For absolute minimum overhead:

```bash
./configure \
  --enable-omni \
  --disable-demo \
  --disable-histogram \
  --disable-dirty
make
```

Or use the provided script:
```bash
./dev/scripts/configure-optimized.sh --minimal
```

### Demo/Interval Overhead

Interim results add minimal overhead (~0-2% throughput impact) but provide better UX with OMNI mode. Disable for benchmarking:

```bash
# Using installed version
netperf -H host -M -l 60 -D -1

# Using build directory
./build/src/netperf -H host -M -l 60 -D -1
```

## Best Practices

### For Production Use

1. **Use full paths**: Be explicit about binary location
   ```bash
   # Installed
   /usr/local/bin/netperf -H host -t TCP_STREAM
   
   # Build directory
   /opt/netperf/build/src/netperf -H host -t TCP_STREAM
   ```

2. **Explicit test types**: Specify `-t TEST_NAME` for clarity
   ```bash
   netperf -H host -t TCP_STREAM
   ```

3. **Explicit output format**: Use `-M` flag when you need OMNI features
   ```bash
   # Columnar (default)
   netperf -H host -t TCP_STREAM
   
   # JSON (requires -M)
   netperf -H host -M -- -J
   ```

4. **Version consistency**: Use same version for netperf and netserver
5. **Document scripts**: Note which fork/version you're using

### For Development

1. **Use JSON output**: Easier to parse in scripts
2. **Use output presets**: Standardize field selection
3. **Enable demo mode**: Better feedback during testing
4. **Use build types**: Debug builds for troubleshooting

### For CI/CD

1. **Pin versions**: Use specific git commit or tag
2. **Use JSON output**: Easier integration with tools
3. **Explicit flags**: Don't rely on defaults changing
4. **Test compatibility**: Verify with your specific use case

## Rollback Plan

If you need to revert to upstream netperf:

1. **Uninstall this fork**:
```bash
cd /opt/netperf/build
sudo make uninstall
```

2. **Build upstream**:
```bash
git clone https://github.com/HewlettPackard/netperf.git
cd netperf
./configure
make
sudo make install
```

3. **Verify**:
```bash
netperf -V  # Check version
```

## Getting Help

### For This Fork
- Check [README.md](README.md) for feature documentation
- Review [BUILD_CONFIGURATION.md](dev/docs/BUILD_CONFIGURATION.md) for build options
- See [Phase 1 Progress](dev/plans/phase-1-progress.md) for development status

### For Upstream Netperf
- Mailing list: netperf-talk@netperf.org
- Original documentation: [doc/netperf.txt](doc/netperf.txt)
- Website: http://www.netperf.org (archived)

## Summary

**Key Takeaways**:
1. ✅ **Fully backward compatible** - existing scripts work unchanged
2. 🎁 **New features are opt-in** - use when ready
3. 📊 **Better defaults** - improved out-of-box experience
4. 🔄 **Easy migration** - add flags for old behavior
5. 📈 **Enhanced output** - JSON and CSV for modern tools

**Recommended Migration Path**:
1. Build and install fork alongside upstream
2. Test with existing workflows using `-- -O` flag
3. Gradually adopt new features (JSON, presets)
4. Update documentation to reflect new capabilities
5. Share improvements with your team

---

**Questions?** The fork maintains backward compatibility by design. If something doesn't work as expected with existing scripts, it's likely a bug - please report it.
