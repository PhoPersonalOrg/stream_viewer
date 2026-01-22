---
name: Setup uv-deps-switcher for stream_viewer
overview: Configure uv-deps-switcher to switch phopymnehelper and phopyqthelper between local editable paths (dev) and git URLs (release), update template fragments to match current pyproject.toml dependencies, and configure repo groups.
todos:
  - id: update_dev_template
    content: Update templating/pyproject_template_dev.toml_fragment with phopymnehelper and phopyqthelper local paths
    status: completed
  - id: update_release_template
    content: Update templating/pyproject_template_release.toml_fragment with phopymnehelper and phopyqthelper git URLs
    status: completed
  - id: update_switcher_config
    content: Update uv-deps-switcher.toml to include stream_viewer in appropriate groups
    status: completed
isProject: false
---

# Setup uv-deps-switcher for stream_viewer

## Current State Analysis

- `pyproject.toml` currently has:
  - `phopymnehelper = { path = "../PhoPyMNEHelper", editable = true }` (local)
  - `phopyqthelper = { git = "https://github.com/CommanderPho/phopyqthelper.git" }` (git)
  - `mne = { path = "../../mne-python", editable = true }` (local, auto-detected by script)
- Template fragments exist but contain wrong packages:
  - Dev template has: `lab-recorder-python`, `whisper-timestamped`, `phopylslhelper`, `phopyqthelper`
  - Release template has: same packages with git URLs
  - Missing: `phopymnehelper` in both templates
- `uv-deps-switcher.toml` has example groups but doesn't include `stream_viewer`

## Implementation Steps

### 1. Update Template Fragments

Update `templating/pyproject_template_dev.toml_fragment` to include:

- `phopymnehelper = { path = "../PhoPyMNEHelper", editable = true }`
- `phopyqthelper = { path = "../phopyqthelper", editable = true }`

Note: Exclude `mne` from templates since it's auto-detected by `update_mne_path.py` script.

Update `templating/pyproject_template_release.toml_fragment` to include:

- `phopymnehelper = { git = "https://github.com/CommanderPho/PhoPyMNEHelper.git" }`
- `phopyqthelper = { git = "https://github.com/CommanderPho/phopyqthelper.git" }`

### 2. Update uv-deps-switcher.toml Configuration

Update `uv-deps-switcher.toml` to:

- Add `stream_viewer` to appropriate groups (e.g., `main` or `all` group)
- Keep existing groups for other repos
- Ensure groups reference actual repo names that match directory names

### 3. Verify pyproject.toml Structure

Ensure `pyproject.toml` has a `[tool.uv.sources]` section that can be properly replaced by the switcher tool. The tool merges template entries with existing ones, so any non-template entries (like `mne`) will be preserved.

## Files to Modify

1. `templating/pyproject_template_dev.toml_fragment` - Update with correct local paths
2. `templating/pyproject_template_release.toml_fragment` - Update with correct git URLs
3. `uv-deps-switcher.toml` - Add stream_viewer to groups

## Expected Result

After setup:

- Running `switch-uv-deps dev` will set both packages to local editable paths
- Running `switch-uv-deps release` will set both packages to git URLs
- The `mne` entry will remain unchanged (handled by update_mne_path.py script)
- `stream_viewer` can be included in group operations with other repos

