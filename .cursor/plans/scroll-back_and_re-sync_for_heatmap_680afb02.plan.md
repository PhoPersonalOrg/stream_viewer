---
name: Scroll-back and re-sync for heatmap
overview: Add scroll-back functionality to HeatmapPG renderer in Scroll mode, allowing users to scroll back through recent spectrogram data. When scrolled back, the view de-syncs from the active time window. A re-sync button in the control panel allows quick return to the current time.
todos:
  - id: add_sync_state_tracking
    content: Add instance variables and methods to track manual scrolling state in HeatmapPG
    status: completed
  - id: detect_manual_scroll
    content: Implement signal connection to detect when user manually changes x-axis range
    status: completed
    dependencies:
      - add_sync_state_tracking
  - id: implement_desync
    content: Unlink x-axes and stop auto-updating when user manually scrolls back
    status: completed
    dependencies:
      - detect_manual_scroll
  - id: implement_resync
    content: Add sync_to_present() method to re-link axes and jump to current time
    status: completed
    dependencies:
      - add_sync_state_tracking
  - id: add_resync_button
    content: Add re-sync button to HeatmapControlPanel with proper enabled/disabled states
    status: completed
  - id: connect_button_to_renderer
    content: Connect re-sync button to renderer method and handle state updates
    status: completed
    dependencies:
      - add_resync_button
      - implement_resync
  - id: handle_mode_changes
    content: Reset sync state when plot mode changes between Sweep and Scroll
    status: completed
    dependencies:
      - add_sync_state_tracking
---

# Scroll-back and Re-sync Feature for Heatmap Renderer

## Overview

Add scroll-back functionality to the `HeatmapPG` renderer that allows users to scroll back through recent spectrogram data in Scroll mode. When the user manually scrolls back, the view will de-sync from the active time window. A re-sync button in the control panel will allow users to quickly return to the current time.

## Implementation Details

### 1. Add Re-sync Button to HeatmapControlPanel

**File**: `stream_viewer/stream_viewer/widgets/heatmap_ctrl.py`

- Add a "Re-sync to Present" button with a left arrow (←) icon/text in the control panel
- Place it after the Apply/Revert buttons section
- The button should:
- Only be enabled when in Scroll mode
- Be disabled when already synced to present time
- Call a renderer method to re-sync the view

### 2. Track Sync State in HeatmapPG

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Add instance variables:
- `_is_manually_scrolled`: Boolean flag to track if user has manually scrolled
- `_last_auto_xrange`: Tuple storing the last automatically set x-axis range
- Add method `_on_xrange_changed()` to detect manual x-axis range changes
- Connect to pyqtgraph's `sigRangeChanged` signal on plot items to detect manual scrolling

### 3. Implement De-sync on Manual Scroll

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- In `update_visualization()`, only auto-update x-axis range when `_is_manually_scrolled` is False
- When user manually changes x-axis range (detected via signal):
- Set `_is_manually_scrolled = True`
- Unlink x-axes using `setXLink(None)` on all plot items
- Enable the re-sync button in the control panel (via signal/event)

### 4. Implement Re-sync Functionality

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Add method `sync_to_present()` that:
- Sets `_is_manually_scrolled = False`
- Re-links all x-axes to the bottom plot item
- Updates x-axis range to current time window (same logic as in `update_visualization()`)
- Disables the re-sync button in control panel

### 5. Update Control Panel Integration

**File**: `stream_viewer/stream_viewer/widgets/heatmap_ctrl.py`

- Add re-sync button widget in `_init_widgets()`
- Connect button click to renderer's `sync_to_present()` method
- Update button enabled state based on:
- Plot mode (only enabled in Scroll mode)
- Sync state from renderer (disabled when already synced)
- Add signal/slot mechanism or direct method call to update button state from renderer

### 6. Handle Mode Changes

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- When plot mode changes from Scroll to Sweep:
- Reset `_is_manually_scrolled = False`
- Re-link x-axes
- Disable re-sync button
- When plot mode changes from Sweep to Scroll:
- Reset sync state
- Enable re-sync button if needed

## Technical Considerations

- Use pyqtgraph's `sigRangeChanged` signal to detect manual x-axis changes
- The signal may fire during programmatic range changes, so filter by checking if the change matches the expected auto-update range
- Store the last auto-update range to compare against manual changes
- Only enable scroll-back in Scroll mode (as per user requirement)
- The re-sync button should be visually distinct (arrow icon) and clearly labeled

## Files to Modify