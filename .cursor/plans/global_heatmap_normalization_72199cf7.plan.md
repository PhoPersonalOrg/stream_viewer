---
name: Global Heatmap Normalization
overview: Implement global normalization for heatmap colormap that tracks the highest (and lowest) values seen across all sources, and use this for color scaling by default when auto_scale is enabled.
todos:
  - id: add_global_tracking
    content: Add _global_min and _global_max instance variables in __init__ method
    status: completed
  - id: reset_global_values
    content: Reset global min/max to None in reset_renderer method
    status: completed
    dependencies:
      - add_global_tracking
  - id: update_color_levels
    content: Modify _update_color_levels to use global min/max when auto_scale is enabled
    status: completed
    dependencies:
      - add_global_tracking
  - id: track_global_values
    content: Update global min/max in update_visualization after heatmap updates
    status: completed
    dependencies:
      - add_global_tracking
      - update_color_levels
---

# Global Heatmap Normalization Implementation

## Problem

The current heatmap renderer normalizes color levels per-source when auto_scale is enabled, causing inconsistent scaling across different data sources. In Scroll mode (and Sweep mode), the colormap should be globally normalized to the highest value seen across all sources for consistent visualization.

## Solution

Implement persistent global min/max tracking across all sources and use these values for color level normalization when auto_scale is enabled.

## Changes Required

### 1. Add Global Tracking Variables

In `__init__` method of [heatmap_pg.py](stream_viewer/stream_viewer/renderers/heatmap_pg.py), add instance variables to track global min/max:

- `_global_min`: Persistent minimum value seen across all sources (initialized to None)
- `_global_max`: Persistent maximum value seen across all sources (initialized to None)

### 2. Reset Global Values

In `reset_renderer` method, reset global min/max to None when renderer is reset.

### 3. Update Color Level Calculation

Modify `_update_color_levels` method to:

- When `auto_scale != 'none'`, use global min/max instead of per-source locked levels
- If global min/max are not yet set, initialize them from the current heatmap data
- Ensure global_max never decreases (persistent tracking)
- Ensure global_min never increases (persistent tracking)
- Fall back to DEFAULT_DB_FLOOR/DEFAULT_DB_CEILING if no data available

### 4. Track Global Values During Updates

In `update_visualization` method, after updating each source's heatmap:

- Check if the heatmap has valid data
- Update `_global_max` if current max > existing global_max (never decrease)
- Update `_global_min` if current min < existing global_min (never increase)
- This should happen after `_update_heatmap_columns` but before `_prepare_display_heatmap`

### 5. Default Behavior

The global normalization will automatically be used when `auto_scale != 'none'` (which appears to be the default based on the base class), so no additional changes needed for default behavior.

## Implementation Details