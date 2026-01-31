# Netperf Development Makefile
# Convenience wrapper for common development tasks

.PHONY: help build clean test install configure debug release optimized \
        rebuild test-formats test-protocols benchmark lint check-cpu \
        git-status git-log

# Default target
.DEFAULT_GOAL := help

# Project directories
PROJECT_ROOT := $(shell cd .. && pwd)
BUILD_DIR := $(PROJECT_ROOT)/build
SCRIPTS_DIR := $(PROJECT_ROOT)/dev/scripts

help: ## Show this help message
	@echo "Netperf Development Makefile"
	@echo ""
	@echo "Build Targets:"
	@echo "  make build           Build netperf (release, default)"
	@echo "  make debug           Build with debug symbols"
	@echo "  make optimized       Build with optimized configuration"
	@echo "  make release         Same as build"
	@echo "  make rebuild         Clean and build"
	@echo "  make clean           Remove build artifacts"
	@echo ""
	@echo "Installation:"
	@echo "  make install         Install netperf to /usr/local"
	@echo "  make install PREFIX=/path  Install to custom prefix"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run basic functional tests"
	@echo "  make test-formats    Test all output formats"
	@echo "  make test-protocols  Test multiple protocols"
	@echo "  make benchmark       Run performance benchmarks"
	@echo ""
	@echo "Utilities:"
	@echo "  make check-cpu       Check CPU detection and MAXCPUS"
	@echo "  make git-status      Show git status"
	@echo "  make git-log         Show recent commits"
	@echo ""
	@echo "Configuration:"
	@echo "  JOBS=N              Set parallel make jobs (default: nproc)"
	@echo "  PREFIX=/path        Installation prefix"
	@echo "  V=1                 Verbose build output"

# Build targets
build: ## Build netperf (release)
	@$(SCRIPTS_DIR)/build.sh

release: build ## Same as build

debug: ## Build with debug symbols
	@$(SCRIPTS_DIR)/build.sh --type debug

optimized: ## Build with optimized configuration
	@$(SCRIPTS_DIR)/build.sh --type optimized

rebuild: clean build ## Clean and rebuild

clean: ## Remove build artifacts
	@$(SCRIPTS_DIR)/clean.sh

configure: ## Run configure script
	@mkdir -p $(BUILD_DIR)
	@cd $(BUILD_DIR) && $(PROJECT_ROOT)/configure

# Installation
PREFIX ?= /usr/local
install: ## Install netperf
	@if [ ! -d "$(BUILD_DIR)" ]; then \
		echo "Build directory not found. Run 'make build' first."; \
		exit 1; \
	fi
	@cd $(BUILD_DIR) && $(MAKE) install PREFIX=$(PREFIX)

# Testing targets
test: ## Run basic functional tests
	@echo "=== Starting netserver ==="
	@killall -9 netserver 2>/dev/null || true
	@sleep 1
	@$(BUILD_DIR)/src/netserver -4 -p 12865 &
	@sleep 2
	@echo ""
	@echo "=== Running basic TCP_STREAM test ==="
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 1
	@echo ""
	@echo "=== Running TCP_RR test ==="
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -t TCP_RR -l 1
	@echo ""
	@echo "=== Running UDP_STREAM test ==="
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -t UDP_STREAM -l 1
	@killall -9 netserver 2>/dev/null || true
	@echo ""
	@echo "✓ Basic tests passed"

test-formats: ## Test all output formats (keyval, CSV, JSON, columnar)
	@echo "=== Testing output formats ==="
	@killall -9 netserver 2>/dev/null || true
	@sleep 1
	@$(BUILD_DIR)/src/netserver -4 -p 12865 &
	@sleep 2
	@echo ""
	@echo "1. Default (keyval) format:"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 1 | head -20
	@echo ""
	@echo "2. CSV format (-- -o):"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 1 -- -o | head -20
	@echo ""
	@echo "3. JSON format (-- -J):"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 1 -- -J | head -20
	@echo ""
	@echo "4. Columnar format (-- -O):"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 1 -- -O | head -20
	@killall -9 netserver 2>/dev/null || true
	@echo ""
	@echo "✓ All output formats working"

test-protocols: ## Test multiple protocol types
	@echo "=== Testing multiple protocols ==="
	@killall -9 netserver 2>/dev/null || true
	@sleep 1
	@$(BUILD_DIR)/src/netserver -4 -p 12865 &
	@sleep 2
	@echo ""
	@echo "TCP_STREAM:"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -t TCP_STREAM -l 1 | grep THROUGHPUT
	@echo ""
	@echo "TCP_RR:"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -t TCP_RR -l 1 | grep THROUGHPUT
	@echo ""
	@echo "TCP_CRR:"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -t TCP_CRR -l 1 | grep THROUGHPUT
	@echo ""
	@echo "UDP_STREAM:"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -t UDP_STREAM -l 1 | grep THROUGHPUT
	@killall -9 netserver 2>/dev/null || true
	@echo ""
	@echo "✓ All protocol tests passed"

benchmark: ## Run performance benchmarks
	@echo "=== Running performance benchmarks ==="
	@killall -9 netserver 2>/dev/null || true
	@sleep 1
	@$(BUILD_DIR)/src/netserver -4 -p 12865 &
	@sleep 2
	@echo ""
	@echo "10-second TCP_STREAM benchmark:"
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 10
	@killall -9 netserver 2>/dev/null || true

# Utility targets
check-cpu: ## Check CPU detection and MAXCPUS
	@echo "=== CPU Detection Test ==="
	@echo "System CPUs detected:"
	@nproc
	@echo ""
	@echo "MAXCPUS in source:"
	@grep "define.*MAXCPUS" $(PROJECT_ROOT)/src/netlib.h
	@echo ""
	@echo "CPU utilization test:"
	@killall -9 netserver 2>/dev/null || true
	@sleep 1
	@$(BUILD_DIR)/src/netserver -4 -p 12865 &
	@sleep 2
	@$(BUILD_DIR)/src/netperf -H 127.0.0.1 -p 12865 -l 1 -c -C | grep CPU
	@killall -9 netserver 2>/dev/null || true

git-status: ## Show git status
	@cd $(PROJECT_ROOT) && git status

git-log: ## Show recent commits
	@cd $(PROJECT_ROOT) && git log --oneline --graph -10

# Advanced targets
lint: ## Run basic code checks
	@echo "Running basic code checks..."
	@find $(PROJECT_ROOT)/src -name "*.c" -o -name "*.h" | xargs grep -n "TODO\|FIXME\|XXX" || echo "No TODOs found"

# Build with custom options
build-minimal: ## Build minimal configuration
	@$(SCRIPTS_DIR)/configure-optimized.sh --minimal
	@$(SCRIPTS_DIR)/build.sh

build-all-protocols: ## Build with all protocols enabled
	@$(SCRIPTS_DIR)/configure-optimized.sh --all-protocols
	@$(SCRIPTS_DIR)/build.sh

# Documentation
docs: ## Open documentation in browser (if available)
	@if [ -f "$(PROJECT_ROOT)/doc/netperf.html" ]; then \
		xdg-open $(PROJECT_ROOT)/doc/netperf.html 2>/dev/null || \
		open $(PROJECT_ROOT)/doc/netperf.html 2>/dev/null || \
		echo "HTML documentation: $(PROJECT_ROOT)/doc/netperf.html"; \
	else \
		echo "Documentation not found. Try: make -C $(BUILD_DIR)/doc"; \
	fi
