---
name: Integrate sources list dock
overview: Ensure the sources list (StreamStatusQMLWidget) is always docked in the left area of the main window and cannot float as a separate window. Modify the dock setup to prevent floating and ensure proper integration.
todos:
  - id: modify-setup-status-panel
    content: Update setup_status_panel() to ensure dock is always docked and set minimum width
    status: completed
  - id: update-restore-startup
    content: Modify restoreOnStartup() to ignore floating state and always dock the status panel
    status: completed
  - id: update-save-settings
    content: Update saveSettings() to always save status dock as non-floating
    status: completed
---

# Integrate Sources List into Main Window

## Current State

The `LSLViewer` class in [`applications/main.py`](applications/main.py) already creates the sources list as a dock widget in the left dock area (lines 121-126). However, the dock can be made floating based on saved settings (lines 170-183), which may cause it to appear as a separate window.

## Changes Required

### 1. Modify `setup_status_panel()` method

In [`applications/main.py`](applications/main.py), update the `setup_status_panel()` method (lines 121-126) to:

- Ensure the dock is always docked (not floating)
- Optionally prevent the dock from being undocked by setting appropriate dock widget features
- Set a minimum width for better usability

### 2. Update `restoreOnStartup()` method

In [`applications/main.py`](applications/main.py), modify the `restoreOnStartup()` method (lines 168-183) to:

- Ignore saved floating state for the status dock
- Always ensure the dock is docked in the left area on startup
- Still restore size and position if docked

### 3. Update `saveSettings()` method

In [`applications/main.py`](applications/main.py), modify the `saveSettings()` method (lines 339-348) to:

- Always save the dock as non-floating (or remove floating state from saved settings)
- Ensure dock area is always saved as LeftDockWidgetArea

## Implementation Details

The key changes will be:

1. Set `dock.setFeatures()` to prevent floating (or allow it but force docked state)
2. Remove or ignore floating state restoration for the status dock
3. Ensure the dock is always added to the left dock area on startup
4. Set a reasonable minimum width for the status dock (e.g., 300px)

## Files to Modify

- [`applications/main.py`](applications/main.py): Update `setup_status_panel()`, `restoreOnStartup()`, and `saveSettings()` methods