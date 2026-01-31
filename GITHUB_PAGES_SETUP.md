# GitHub Pages Setup Instructions

The documentation site has been created and pushed to the repository. Follow these steps to enable it on GitHub:

## Enable GitHub Pages

1. **Go to Repository Settings**:

   ```
   https://github.com/thehevy/netperf_copilot/settings/pages
   ```

2. **Configure Source**:
   - **Source**: Deploy from a branch
   - **Branch**: `master`
   - **Folder**: `/docs`

3. **Click "Save"**

4. **Wait for Deployment** (2-5 minutes)

GitHub will automatically build and deploy your site using Jekyll.

## Access Your Site

Once deployed, your site will be available at:

```
https://thehevy.github.io/netperf_copilot/
```

## Site Structure

```
netperf_copilot/
├── _config.yml                 # Jekyll configuration
└── docs/
    ├── index.md               # Landing page
    ├── installation.md        # Installation guide
    └── quickstart.md          # Quick start guide
```

## Features

### Landing Page (docs/index.md)

- Feature overview (Phases 1-3)
- Quick start section
- Tool documentation links
- Code examples
- Resource links

### Installation Guide (docs/installation.md)

- System requirements
- Multiple installation methods
- Platform-specific instructions
- Troubleshooting
- Build types explained

### Quick Start Guide (docs/quickstart.md)

- 5-minute tutorial
- Common test scenarios
- Advanced tool examples
- Common workflows
- Output format examples
- Tips and tricks

## Theme

Using **Cayman** theme:

- Clean, modern design
- Responsive layout
- Syntax highlighting
- Professional appearance

## Customization

### Change Theme

Edit `_config.yml`:

```yaml
theme: jekyll-theme-minimal  # or slate, architect, etc.
```

Available themes:

- cayman (current)
- minimal
- slate
- architect
- modernist
- midnight

### Add Google Analytics

Edit `_config.yml`:

```yaml
google_analytics: UA-XXXXXXXXX-X
```

### Add Custom Domain

1. Add `CNAME` file to `docs/`:

   ```
   docs.netperf.example.com
   ```

2. Configure DNS:

   ```
   CNAME docs.netperf.example.com -> thehevy.github.io
   ```

3. Update in GitHub Settings → Pages → Custom domain

## Navigation

The site uses relative links between pages:

- `[Installation](installation.html)` - Within docs/
- `[OMNI Reference](../dev/docs/OMNI_REFERENCE.html)` - To dev/docs/
- `[Back to Documentation](index.html)` - Return to main

## Automatic Updates

Any push to the `master` branch automatically triggers a rebuild. Changes appear within 2-5 minutes.

## Local Preview

Test the site locally before pushing:

```bash
# Install Jekyll
gem install bundler jekyll

# Create Gemfile
cat > Gemfile << 'EOF'
source "https://rubygems.org"
gem "github-pages", group: :jekyll_plugins
EOF

# Install dependencies
bundle install

# Serve locally
bundle exec jekyll serve --source docs

# Visit http://localhost:4000
```

## Verify Deployment

After enabling GitHub Pages:

1. **Check Actions Tab**:

   ```
   https://github.com/thehevy/netperf_copilot/actions
   ```

   Look for "pages build and deployment" workflow

2. **Check Deployment Status**:

   ```
   https://github.com/thehevy/netperf_copilot/deployments
   ```

3. **Visit Site**:

   ```
   https://thehevy.github.io/netperf_copilot/
   ```

## Troubleshooting

### Site Not Building

- Check Actions tab for build errors
- Verify `_config.yml` syntax
- Ensure markdown files have proper frontmatter

### 404 Errors

- Check file paths are correct
- Use `.html` extension in links (not `.md`)
- Verify files are in `docs/` directory

### Theme Not Loading

- Verify theme name in `_config.yml`
- Check GitHub Pages supports the theme
- Try a different supported theme

## Additional Pages

To add more pages, create markdown files in `docs/`:

```markdown
---
layout: default
title: My New Page
---

# My New Page

Content here...
```

Update navigation in `docs/index.md` to link to new page.

## Next Steps

After enabling GitHub Pages:

1. ✅ Visit <https://thehevy.github.io/netperf_copilot/>
2. ✅ Test all navigation links
3. ✅ Verify theme rendering
4. ✅ Check mobile responsiveness
5. ✅ Add more documentation pages as needed
6. ✅ Promote the documentation site in README.md

## Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Jekyll Themes](https://pages.github.com/themes/)
- [Markdown Guide](https://www.markdownguide.org/)
- [Jekyll Documentation](https://jekyllrb.com/docs/)
