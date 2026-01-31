#!/bin/bash
# Build script for netperf development
# Enhanced with build options, types, and parallel control

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
MAKE_JOBS=$(nproc)
BUILD_TYPE="release"
CONFIGURE_OPTS=""
VERBOSE=false
CLEAN_FIRST=false

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo "Usage: $0 [OPTIONS] [-- CONFIGURE_OPTIONS]"
    echo ""
    echo "Build Options:"
    echo "  -t, --type TYPE       Build type: release (default), debug, optimized"
    echo "  -j, --jobs N          Number of parallel make jobs (default: $(nproc))"
    echo "  -c, --clean           Clean before building"
    echo "  -v, --verbose         Verbose build output"
    echo "  -h, --help            Show this help"
    echo ""
    echo "Build Types:"
    echo "  release               Standard build with optimizations"
    echo "  debug                 Debug build with symbols, no optimization"
    echo "  optimized             Use configure-optimized.sh preset"
    echo ""
    echo "Examples:"
    echo "  $0                              # Standard release build"
    echo "  $0 --type debug                 # Debug build"
    echo "  $0 --type optimized             # Use configure-optimized.sh"
    echo "  $0 --clean --jobs 8             # Clean build with 8 jobs"
    echo "  $0 -- --enable-histogram        # Pass options to configure"
    echo "  $0 --type debug -- --disable-demo  # Debug with custom options"
    echo ""
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            BUILD_TYPE="$2"
            shift 2
            ;;
        -j|--jobs)
            MAKE_JOBS="$2"
            shift 2
            ;;
        -c|--clean)
            CLEAN_FIRST=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            print_usage
            ;;
        --)
            shift
            CONFIGURE_OPTS="$@"
            break
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Netperf Development Build ===${NC}"
echo "Project root: ${PROJECT_ROOT}"
echo "Build directory: ${BUILD_DIR}"
echo "Build type: ${BUILD_TYPE}"
echo "Make jobs: ${MAKE_JOBS}"

# Clean if requested
if [ "$CLEAN_FIRST" = true ]; then
    echo ""
    echo -e "${YELLOW}Cleaning build directory...${NC}"
    rm -rf "${BUILD_DIR}"
fi

# Create build directory
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# Configure based on build type
echo ""
echo -e "${YELLOW}=== Running configure ===${NC}"

case "$BUILD_TYPE" in
    release)
        echo "Build type: Release (standard configure)"
        if [ -n "$CONFIGURE_OPTS" ]; then
            echo "Extra options: $CONFIGURE_OPTS"
        fi
        "${PROJECT_ROOT}/configure" $CONFIGURE_OPTS
        ;;
    debug)
        echo "Build type: Debug (CFLAGS=-g -O0)"
        CFLAGS="-g -O0" "${PROJECT_ROOT}/configure" $CONFIGURE_OPTS
        ;;
    optimized)
        echo "Build type: Optimized (using configure-optimized.sh)"
        if [ -n "$CONFIGURE_OPTS" ]; then
            "${PROJECT_ROOT}/dev/scripts/configure-optimized.sh" --build-dir "${BUILD_DIR}" $CONFIGURE_OPTS
        else
            "${PROJECT_ROOT}/dev/scripts/configure-optimized.sh" --build-dir "${BUILD_DIR}"
        fi
        ;;
    *)
        echo -e "${RED}Error: Unknown build type: $BUILD_TYPE${NC}"
        echo "Valid types: release, debug, optimized"
        exit 1
        ;;
esac

# Build
echo ""
echo -e "${YELLOW}=== Building with $MAKE_JOBS parallel jobs ===${NC}"

if [ "$VERBOSE" = true ]; then
    make -j${MAKE_JOBS} V=1
else
    make -j${MAKE_JOBS}
fi

# Check if build succeeded (look for binaries despite doc errors)
if [ -f "${BUILD_DIR}/src/netperf" ] && [ -f "${BUILD_DIR}/src/netserver" ]; then
    echo ""
    echo -e "${GREEN}=== Build complete ===${NC}"
    echo "Binaries:"
    ls -lh "${BUILD_DIR}/src/netperf" "${BUILD_DIR}/src/netserver"
    echo ""
    echo "To run tests:"
    echo "  cd ${BUILD_DIR}"
    echo "  ./src/netserver -4 &"
    echo "  ./src/netperf -H 127.0.0.1"
else
    echo ""
    echo -e "${RED}=== Build failed ===${NC}"
    echo "Binaries not found in ${BUILD_DIR}/src/"
    exit 1
fi
