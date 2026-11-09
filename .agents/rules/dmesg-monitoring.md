---
description: "Mandatory dmesg DMAR, MDD, and kernel fault zero-tolerance monitoring gate on all Linux test hosts"
trigger: always_on
---

# Mandatory `dmesg` Error & Hardware Fault Monitoring Rule

Whenever you load or reload a kernel module, configure network adapter state, start a daemon, or execute any test or
benchmark on a Linux host:

1. **Pre-Test Baseline**: Capture the baseline `dmesg -T` line count before the test
   (`DMESG_BASELINE=$(dmesg | wc -l)`).
2. **Post-Test & Post-Daemon Check**: Immediately after the test (and 5-10 seconds after starting any background
   daemon), run:
   ```bash
   dmesg -T | tail -n 40
   dmesg -T | grep -iE "DMAR|fault|DRHD|Oops|BUG:|WARNING:|Call Trace|MDD|Malicious|hw_error|reset|tx_timeout" | tail -n 20
   ```
3. **Zero-Tolerance Pass Gate**: Never report a test or configuration as passing if any new `DMAR` fault, `MDD` event,
   kernel `Oops`/`BUG`/`WARNING`/`Call Trace`, or unexpected hardware reset appeared in `dmesg`. Immediately stop the
   offending process and resolve the root cause.

---
