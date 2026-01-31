# GitHub Release Guide for v3.0.0

Since the GitHub CLI is not available, you can create the release using one of these methods:

## Method 1: GitHub Web Interface (Recommended)

1. **Navigate to Releases**:

   ```
   https://github.com/thehevy/netperf_copilot/releases/new?tag=v3.0.0
   ```

2. **Fill in the form**:
   - **Tag**: v3.0.0 (should auto-populate)
   - **Release title**: `Release v3.0.0: Phase 3 Complete - Advanced Tools`
   - **Description**: Copy content from `RELEASE_NOTES_v3.0.0.md`

3. **Click "Publish release"**

---

## Method 2: Using the API Script

If you have a GitHub Personal Access Token:

```bash
# Set your GitHub token
export GITHUB_TOKEN=your_personal_access_token

# Run the script
chmod +x create-github-release.sh
./create-github-release.sh
```

To create a Personal Access Token:

1. Go to: <https://github.com/settings/tokens>
2. Click "Generate new token (classic)"
3. Select scope: `public_repo`
4. Copy the token

---

## Method 3: Manual cURL Command

```bash
export GITHUB_TOKEN=your_token

curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/thehevy/netperf_copilot/releases \
  -d '{
    "tag_name": "v3.0.0",
    "name": "Release v3.0.0: Phase 3 Complete - Advanced Tools",
    "body": "See RELEASE_NOTES_v3.0.0.md for full details",
    "draft": false,
    "prerelease": false
  }'
```

---

## What to Include in Release Description

Use the content from `RELEASE_NOTES_v3.0.0.md`, which includes:

### Key Highlights

- 6 production-ready advanced tools
- 10 built-in test profiles
- 100% integration testing (11/11 tests passed)
- 4 comprehensive documentation guides
- Complete backward compatibility

### Tools Overview

1. **netperf-multi** - Parallel execution (2-16 instances)
2. **netperf_stats.py** - Statistical analysis with CI
3. **netperf-profile** - Pre-configured test profiles
4. **netperf-orchestrate** - Multi-host coordination
5. **netperf-monitor** - Real-time TUI monitoring
6. **netperf-template** - Report generation (5 formats)

### Statistics

- **46 files** added (8,396 insertions)
- **2,023 lines** of documentation
- **100% pass rate** on integration tests
- **19-52 Gbps** performance validated

---

## After Creating the Release

The release will be visible at:

```
https://github.com/thehevy/netperf_copilot/releases/tag/v3.0.0
```

Users can:

- Download source code (zip/tar.gz)
- View comprehensive release notes
- Access all Phase 3 tools and documentation
- See integration testing results

---

## Quick Links

- **Tag**: <https://github.com/thehevy/netperf_copilot/releases/tag/v3.0.0>
- **Comparison**: <https://github.com/thehevy/netperf_copilot/compare/netperf-2.7.0...v3.0.0>
- **Repository**: <https://github.com/thehevy/netperf_copilot>
- **Documentation**: <https://github.com/thehevy/netperf_copilot/tree/master/dev/docs>
