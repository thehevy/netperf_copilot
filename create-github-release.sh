#!/bin/bash
# Create GitHub Release using API
# This script creates a GitHub release for v3.0.0

set -e

REPO_OWNER="thehevy"
REPO_NAME="netperf_copilot"
TAG="v3.0.0"
RELEASE_NAME="Release v3.0.0: Phase 3 Complete - Advanced Tools"

# Check for GitHub token
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable not set"
    echo "Please set it with: export GITHUB_TOKEN=your_token"
    echo ""
    echo "Or create the release manually at:"
    echo "https://github.com/$REPO_OWNER/$REPO_NAME/releases/new?tag=$TAG"
    exit 1
fi

# Read release notes
RELEASE_BODY=$(cat RELEASE_NOTES_v3.0.0.md)

# Create JSON payload
cat > /tmp/release_payload.json <<EOF
{
  "tag_name": "$TAG",
  "name": "$RELEASE_NAME",
  "body": $(echo "$RELEASE_BODY" | jq -Rs .),
  "draft": false,
  "prerelease": false
}
EOF

echo "Creating GitHub release..."
echo "Repository: $REPO_OWNER/$REPO_NAME"
echo "Tag: $TAG"
echo "Name: $RELEASE_NAME"
echo ""

# Create release using GitHub API
RESPONSE=$(curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases" \
  -d @/tmp/release_payload.json)

# Check if successful
if echo "$RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    RELEASE_URL=$(echo "$RESPONSE" | jq -r '.html_url')
    echo "✅ Release created successfully!"
    echo "URL: $RELEASE_URL"
else
    echo "❌ Failed to create release"
    echo "Response:"
    echo "$RESPONSE" | jq .
    exit 1
fi

# Cleanup
rm -f /tmp/release_payload.json

echo ""
echo "Release v3.0.0 is now live on GitHub!"
