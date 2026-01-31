# Remote Test Orchestration Guide

## Overview

`netperf-orchestrate` coordinates netperf tests across multiple remote hosts using SSH-based execution. It automatically deploys netserver, manages processes, and collects results from distributed test infrastructure.

## Features

- **Multi-Host Testing**: Run tests from multiple clients to multiple servers (full matrix)
- **SSH-Based Execution**: Automatic SSH connection management (subprocess or paramiko)
- **netserver Management**: Deploy, start, stop, and monitor netserver processes
- **Host Inventory**: YAML-based or text file host configuration
- **Parallel Execution**: Run multiple tests simultaneously with configurable workers
- **Result Aggregation**: Centralized result collection and JSON export
- **Error Handling**: Retry logic, timeout protection, and graceful degradation

## Installation

```bash
chmod +x dev/tools/netperf-orchestrate

# Optional dependencies for enhanced SSH support
pip install paramiko pyyaml
```

## Host Inventory

### YAML Format (Recommended)

Create a `hosts.yaml` file:

```yaml
hosts:
  - name: server1
    address: 10.0.1.10
    role: server
    ssh_user: root
    ssh_port: 22
    ssh_key: ~/.ssh/id_rsa
    
  - name: client1
    address: 10.0.1.20
    role: client
    ssh_user: root
    ssh_key: ~/.ssh/id_rsa
```

**Host Roles**:

- `server`: Can only act as netserver (receives tests)
- `client`: Can only act as netperf client (initiates tests)
- `both`: Can act as either client or server

### Text Format

Simple list of IP addresses (one per line):

**clients.txt**:

```
10.0.1.20
10.0.1.21
10.0.1.22
```

**servers.txt**:

```
10.0.1.10
10.0.1.11
```

## Basic Usage

### 1. Check Connectivity

Verify SSH access to all hosts:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml --check
```

Output:

```
Checking connectivity to all hosts...
  ✓ server1            (10.0.1.10)
  ✓ server2            (10.0.1.11)
  ✓ client1            (10.0.1.20)
  ✓ client2            (10.0.1.21)

Result: 4/4 hosts online
```

### 2. Deploy netserver

Copy netserver binary to all server hosts:

```bash
# Deploy from local binary
./dev/tools/netperf-orchestrate --hosts hosts.yaml --deploy \
    --local-netserver ./build/src/netserver

# Or assume already installed
./dev/tools/netperf-orchestrate --hosts hosts.yaml --deploy
```

### 3. Start netserver

Start netserver daemons on all server hosts:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml --start
```

Output:

```
Starting netserver on 2 hosts...
  ✓ server1: Started (PID 12345)
  ✓ server2: Started (PID 12346)

Result: 2/2 netservers started
```

### 4. Run Tests

#### Using Host Inventory

Run OMNI tests with custom arguments:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml -- \
    -d send -l 30 -o THROUGHPUT,P50_LATENCY,P99_LATENCY
```

#### Using Matrix Mode

Test all clients against all servers:

```bash
./dev/tools/netperf-orchestrate --matrix clients.txt servers.txt -- \
    -d send -l 30
```

This creates a full matrix (4 clients × 2 servers = 8 tests).

### 5. Stop netserver

Stop netserver on all server hosts:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml --stop
```

### 6. Get Status

Check netserver status:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml --status
```

Output:

```
Netserver Status:
  server1             : Running (PID 12345)
  server2             : Running (PID 12346)
```

## Advanced Usage

### Profile Integration

Run tests using a profile:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml --profile throughput
```

### Parallel vs Sequential

```bash
# Parallel execution (default, faster)
./dev/tools/netperf-orchestrate --hosts hosts.yaml --parallel -- -d send -l 30

# Sequential execution (easier to debug)
./dev/tools/netperf-orchestrate --hosts hosts.yaml --sequential -- -d send -l 30
```

### Export Results

Save results to JSON file for post-processing:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml --export results.json -- \
    -d send -l 30 -o JSON
```

Result structure:

```json
[
  {
    "client": "client1",
    "server": "server1",
    "client_address": "10.0.1.20",
    "server_address": "10.0.1.10",
    "success": true,
    "exit_code": 0,
    "elapsed_time": 31.2,
    "stdout": "...",
    "command": "netperf -H 10.0.1.10 -d send -l 30"
  },
  ...
]
```

### Custom Binary Paths

Specify netperf/netserver paths on remote hosts:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml \
    --netperf /opt/netperf/bin/netperf \
    --netserver /opt/netperf/bin/netserver \
    --start
```

### Verbose Output

Get detailed execution information:

```bash
./dev/tools/netperf-orchestrate --hosts hosts.yaml -v -- -d send -l 30
```

## Complete Workflow

Typical testing workflow:

```bash
# 1. Check connectivity
./dev/tools/netperf-orchestrate --hosts hosts.yaml --check

# 2. Deploy netserver (first time only)
./dev/tools/netperf-orchestrate --hosts hosts.yaml --deploy \
    --local-netserver ./build/src/netserver

# 3. Start netserver
./dev/tools/netperf-orchestrate --hosts hosts.yaml --start

# 4. Run throughput tests
./dev/tools/netperf-orchestrate --hosts hosts.yaml --export throughput.json -- \
    -d send -l 60 -o JSON,THROUGHPUT,LOCAL_CPU_UTIL,REMOTE_CPU_UTIL

# 5. Run latency tests
./dev/tools/netperf-orchestrate --hosts hosts.yaml --export latency.json -- \
    -d rr -l 60 -o JSON,MEAN_LATENCY,P50_LATENCY,P99_LATENCY

# 6. Stop netserver (if needed)
./dev/tools/netperf-orchestrate --hosts hosts.yaml --stop
```

## Matrix Testing Examples

### Full Matrix

Test every client against every server:

```bash
# 4 clients × 2 servers = 8 tests
./dev/tools/netperf-orchestrate --matrix clients.txt servers.txt -- \
    -d send -l 30
```

### Regional Testing

Test clients in one region against servers in another:

**us-east-clients.txt**:

```
10.0.1.20
10.0.1.21
```

**us-west-servers.txt**:

```
10.0.2.10
10.0.2.11
```

```bash
./dev/tools/netperf-orchestrate \
    --matrix us-east-clients.txt us-west-servers.txt \
    --export cross-region.json -- \
    -d send -l 120
```

### Scaled Testing

Large-scale matrix for capacity testing:

```bash
# Generate client list
seq 1 100 | xargs -I{} echo "10.0.{}.1" > 100-clients.txt

# Generate server list
seq 1 10 | xargs -I{} echo "192.168.{}.1" > 10-servers.txt

# Run full matrix (100 × 10 = 1000 tests)
./dev/tools/netperf-orchestrate \
    --matrix 100-clients.txt 10-servers.txt \
    --parallel \
    --export scaled-results.json -- \
    -d send -l 30
```

## SSH Configuration

### Key-Based Authentication

Ensure passwordless SSH access:

```bash
# Generate key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/netperf_test

# Copy to all hosts
for host in 10.0.1.{10,11,20,21}; do
    ssh-copy-id -i ~/.ssh/netperf_test.pub root@$host
done
```

Update `hosts.yaml`:

```yaml
hosts:
  - name: server1
    address: 10.0.1.10
    ssh_key: ~/.ssh/netperf_test
```

### SSH Config File

Use `~/.ssh/config` for host-specific settings:

```
Host netperf-*
    User root
    IdentityFile ~/.ssh/netperf_test
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ConnectTimeout 10

Host netperf-server1
    HostName 10.0.1.10

Host netperf-client1
    HostName 10.0.1.20
```

Then use aliases in inventory:

```yaml
hosts:
  - name: server1
    address: netperf-server1
    role: server
```

## Troubleshooting

### SSH Connection Failures

```bash
# Test manual SSH
ssh root@10.0.1.10 'echo test'

# Check SSH keys
ssh -v root@10.0.1.10

# Use verbose mode
./dev/tools/netperf-orchestrate --hosts hosts.yaml -v --check
```

### netserver Won't Start

```bash
# Check if already running
./dev/tools/netperf-orchestrate --hosts hosts.yaml --status

# Stop and restart
./dev/tools/netperf-orchestrate --hosts hosts.yaml --stop
./dev/tools/netperf-orchestrate --hosts hosts.yaml --start

# Manual check
ssh root@10.0.1.10 'netserver -D'
ssh root@10.0.1.10 'pgrep netserver'
```

### Test Failures

```bash
# Run sequential for easier debugging
./dev/tools/netperf-orchestrate --hosts hosts.yaml --sequential -v -- -d send -l 10

# Test manually
ssh root@10.0.1.20 'netperf -H 10.0.1.10 -d send -l 10'

# Check firewall
ssh root@10.0.1.10 'iptables -L -n | grep 12865'
```

## Integration with Other Tools

### With netperf-multi

Run multiple instances per client:

```bash
# Generate commands
./dev/tools/netperf-orchestrate --hosts hosts.yaml -- \
    -d send -l 30 > commands.txt

# Run with netperf-multi (on each client)
ssh root@10.0.1.20 'netperf-multi -n 4 -H 10.0.1.10 -- -d send -l 30'
```

### With netperf-profile

Run profiles across hosts:

```bash
# First, copy profile to all hosts
for host in 10.0.1.{20,21}; do
    scp dev/profiles/throughput.yaml root@$host:/tmp/
done

# Run profile on each client
./dev/tools/netperf-orchestrate --hosts hosts.yaml --profile throughput
```

### With netperf_stats.py

Analyze orchestrated test results:

```bash
# Run tests and export
./dev/tools/netperf-orchestrate --hosts hosts.yaml --export results.json -- \
    -d send -l 30 -o THROUGHPUT

# Extract throughput values
jq -r '.[] | select(.success) | .stdout' results.json > throughput.txt

# Analyze
python3 dev/tools/netperf_stats.py throughput.txt
```

## Best Practices

1. **Connectivity First**: Always run `--check` before other operations
2. **Deploy Once**: Deploy netserver once, then reuse across test runs
3. **Parallel Testing**: Use parallel mode for large matrices (faster)
4. **Export Results**: Always use `--export` for later analysis
5. **Stop When Done**: Use `--stop` to clean up netserver processes
6. **Firewall Rules**: Ensure port 12865 (netserver) is open on all hosts
7. **Time Sync**: Ensure NTP is configured on all hosts for accurate timestamps
8. **SSH Keys**: Use key-based auth, not passwords
9. **Host Naming**: Use descriptive names in inventory for clarity
10. **Version Consistency**: Use same netperf version on all hosts

## Performance Tips

- **Parallel Workers**: Adjust with ThreadPoolExecutor max_workers (default: 4)
- **Test Duration**: Longer tests (60s+) provide more stable results
- **Stagger Tests**: For very large matrices, consider running in batches
- **Network Isolation**: Avoid running interfering traffic during tests
- **Resource Monitoring**: Monitor CPU/network on hosts during tests

## Security Considerations

- Use SSH keys, not passwords
- Restrict SSH access to test infrastructure
- Use dedicated test user accounts
- Consider using SSH bastion/jump hosts
- Rotate SSH keys regularly
- Audit SSH logs after test runs
- Use network segmentation for test traffic
- Clean up netserver processes after testing

## Examples

See `dev/examples/` for complete working examples:

- `hosts.yaml`: Sample host inventory
- `clients.txt`, `servers.txt`: Text-based inventory
- orchestration scripts demonstrating common patterns

## See Also

- [OMNI_REFERENCE.md](OMNI_REFERENCE.md) - OMNI test framework guide
- [phase-3-plan.md](../plans/phase-3-plan.md) - Phase 3 implementation plan
- netperf-multi(1) - Multi-instance test runner
- netperf-profile(1) - Profile-based test execution
