#!/bin/bash
# Optimized configure script for netperf
# Based on analysis of all configure options and their performance impact
#
# This configuration provides the best balance of:
# - Performance (accurate measurements with minimal overhead)
# - Usability (helpful output and progress feedback)
# - Protocol coverage (common protocols enabled)
# - CPU measurement (automatic platform detection)

set -e

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Netperf Optimized Build Configuration ===${NC}"
echo ""

# Default recommended options
ENABLE_OPTIONS=(
    "--enable-omni"          # Modern OMNI test framework (REQUIRED)
    "--enable-demo"          # Interim results during test runs (default now)
    "--enable-burst"         # Initial burst in RR tests (realistic workload)
    "--enable-sctp"          # SCTP protocol support
    "--enable-unixdomain"    # Unix domain socket tests
)

DISABLE_OPTIONS=(
    "--disable-histogram"    # Avoid per-op timing overhead
    "--disable-dirty"        # Avoid forced cache misses
    "--disable-intervals"    # Avoid pacing overhead unless needed
    "--disable-spin"         # Never busy-wait
)

# Auto-detect CPU measurement method (platform-specific)
echo -e "${YELLOW}Detecting optimal CPU measurement method...${NC}"
# configure.ac will auto-detect: procstat (Linux), pstat (HP-UX), 
# perfstat (AIX), kstat (Solaris), sysctl (BSD), osx (macOS)

# Parse command-line arguments for overrides
EXTRA_OPTS=""
BUILD_DIR=""
INSTALL_PREFIX="/usr/local"

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Optimized configuration options (already set):"
    echo "  --enable-omni           Modern OMNI test framework"
    echo "  --enable-demo           Interim results (user feedback)"
    echo "  --enable-burst          Initial burst in RR tests"
    echo "  --enable-sctp           SCTP protocol support"
    echo "  --enable-unixdomain     Unix domain socket tests"
    echo "  --disable-histogram     Avoid timing overhead"
    echo "  --disable-dirty         Avoid cache effects"
    echo ""
    echo "Override options:"
    echo "  --with-histogram        Enable per-operation timing"
    echo "  --with-dirty            Enable dirty buffer testing"
    echo "  --with-intervals        Enable paced operations"
    echo "  --minimal               Minimal build (OMNI + demo only)"
    echo "  --all-protocols         Enable all protocol tests"
    echo ""
    echo "Build options:"
    echo "  --build-dir DIR         Build in specific directory"
    echo "  --prefix DIR            Install prefix (default: /usr/local)"
    echo "  --help                  Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                      # Standard optimized build"
    echo "  $0 --with-intervals     # Enable paced operations"
    echo "  $0 --minimal            # Minimal footprint"
    echo "  $0 --all-protocols      # Maximum protocol coverage"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-histogram)
            ENABLE_OPTIONS+=("--enable-histogram")
            DISABLE_OPTIONS=("${DISABLE_OPTIONS[@]/--disable-histogram/}")
            echo -e "${YELLOW}Override: Enabling histogram (may affect results)${NC}"
            shift
            ;;
        --with-dirty)
            ENABLE_OPTIONS+=("--enable-dirty")
            DISABLE_OPTIONS=("${DISABLE_OPTIONS[@]/--disable-dirty/}")
            echo -e "${YELLOW}Override: Enabling dirty buffers (may affect results)${NC}"
            shift
            ;;
        --with-intervals)
            ENABLE_OPTIONS+=("--enable-intervals")
            DISABLE_OPTIONS=("${DISABLE_OPTIONS[@]/--disable-intervals/}")
            echo -e "${YELLOW}Override: Enabling paced operations${NC}"
            shift
            ;;
        --minimal)
            ENABLE_OPTIONS=("--enable-omni" "--enable-demo")
            DISABLE_OPTIONS=("--disable-histogram" "--disable-dirty" "--disable-intervals" 
                           "--disable-unixdomain" "--disable-sctp" "--disable-burst")
            echo -e "${YELLOW}Minimal build: OMNI + demo only${NC}"
            shift
            ;;
        --all-protocols)
            ENABLE_OPTIONS+=("--enable-dlpi" "--enable-dccp" "--enable-xti" "--enable-sdp")
            echo -e "${YELLOW}Enabling all protocol tests${NC}"
            shift
            ;;
        --build-dir)
            BUILD_DIR="$2"
            shift 2
            ;;
        --prefix)
            INSTALL_PREFIX="$2"
            shift 2
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            EXTRA_OPTS="$EXTRA_OPTS $1"
            shift
            ;;
    esac
done

# Get source directory (script location)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo -e "${GREEN}Source directory:${NC} $SRC_DIR"
echo -e "${GREEN}Install prefix:${NC} $INSTALL_PREFIX"

# Setup build directory
if [[ -n "$BUILD_DIR" ]]; then
    echo -e "${GREEN}Build directory:${NC} $BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
else
    echo -e "${GREEN}Build directory:${NC} $SRC_DIR/build (default)"
    BUILD_DIR="$SRC_DIR/build"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
fi

echo ""
echo -e "${GREEN}Configuration options:${NC}"
echo "  Enable: ${ENABLE_OPTIONS[@]}"
echo "  Disable: ${DISABLE_OPTIONS[@]}"
if [[ -n "$EXTRA_OPTS" ]]; then
    echo "  Extra: $EXTRA_OPTS"
fi
echo ""

# Run configure
echo -e "${YELLOW}Running configure...${NC}"
CONFIG_CMD="$SRC_DIR/configure ${ENABLE_OPTIONS[@]} ${DISABLE_OPTIONS[@]} --prefix=$INSTALL_PREFIX $EXTRA_OPTS"

if $CONFIG_CMD; then
    echo ""
    echo -e "${GREEN}✓ Configuration successful!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. make -j\$(nproc)     # Build with parallel jobs"
    echo "  2. make check           # Run tests (if available)"
    echo "  3. sudo make install    # Install to $INSTALL_PREFIX"
    echo ""
    echo "Or use the build script:"
    echo "  cd $SRC_DIR"
    echo "  ./dev/scripts/build.sh"
else
    echo ""
    echo -e "${RED}✗ Configuration failed!${NC}"
    echo "Check config.log for details: $BUILD_DIR/config.log"
    exit 1
fi
